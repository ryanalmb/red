"""Base agent class for Cyber-Red stigmergic coordination.

This module implements the StigmergicAgent base class which extends the
swarms.Agent to add P2P coordination capabilities via Redis Pub/Sub
and LLM-driven tool selection (Story 7.1.v2).
"""

import asyncio
import contextlib
import json
import time
import uuid
from collections import deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

import structlog
from swarms import Agent

from cyberred.agents.prompts import PromptLibrary
from cyberred.agents.roles import AgentRole
from cyberred.core.config import get_settings
from cyberred.core.events import EventBus
from cyberred.core.sharding import ShardedEventBus
from cyberred.core.exceptions import ThrottleTimeoutError, ToolSelectionError
from cyberred.core.models import AgentAction, ToolSelection, ToolSelectionContext

if TYPE_CHECKING:
    from cyberred.orchestration.emergence.strategy import EmergentStrategy
    from cyberred.llm.gateway import LLMGateway
    from cyberred.tools.manifest import ManifestLoader
    from cyberred.orchestration.emergence.tracker import DecisionContextTracker
    from cyberred.storage.checkpoint import CheckpointManager, AgentState

log = structlog.get_logger().bind(component="stigmergic_agent")

# Role to tool categories mapping for select_tool()
ROLE_CATEGORIES: dict[AgentRole, list[str]] = {
    AgentRole.RECON: ["recon", "discovery", "enumeration", "osint"],
    AgentRole.EXPLOIT: ["exploit", "vulnerability", "injection", "web"],
    AgentRole.POSTEX: ["postex", "privesc", "lateral", "persistence"],
    AgentRole.WEBAPP: ["web", "injection", "auth", "api"],
    AgentRole.WIRELESS: ["wireless", "wifi", "bluetooth"],
    AgentRole.AD: ["activedirectory", "kerberos", "ldap", "smb"],
    AgentRole.CREDENTIAL: ["credential", "password", "hash", "brute"],
    AgentRole.FORENSICS: ["forensics", "memory", "disk", "artifact"],
}

# ATT&CK Technique to Tool Category Mapping (Story 7.17)
# Maps MITRE ATT&CK technique IDs to relevant tool categories and example tools
ATTCK_TECHNIQUE_TOOL_MAP: dict[str, list[str]] = {
    # Reconnaissance
    "T1595": ["recon", "scanning"],  # Active Scanning
    "T1592": ["recon", "enumeration"],  # Gather Victim Host Information
    "T1589": ["osint", "recon"],  # Gather Victim Identity Information
    # Discovery
    "T1046": ["recon", "discovery"],  # Network Service Discovery (nmap, masscan)
    "T1018": ["recon", "enumeration"],  # Remote System Discovery (nbtscan, enum4linux)
    "T1082": ["postex", "enumeration"],  # System Information Discovery (linpeas, winpeas)
    "T1016": ["postex", "enumeration"],  # System Network Configuration Discovery
    # Credential Access
    "T1078": ["credential", "auth"],  # Valid Accounts (hydra, medusa)
    "T1110": ["credential", "brute"],  # Brute Force
    "T1003": ["credential", "postex"],  # OS Credential Dumping (mimikatz, secretsdump)
    # Initial Access
    "T1190": ["web", "exploit"],  # Exploit Public-Facing Application (sqlmap, nuclei)
    "T1133": ["exploit", "network"],  # External Remote Services
    # Lateral Movement
    "T1021": ["lateral", "exploit"],  # Remote Services (crackmapexec, psexec)
    "T1550": ["lateral", "credential"],  # Use Alternate Authentication Material
    # Execution
    "T1059": ["postex", "exploit"],  # Command and Scripting Interpreter
    # Privilege Escalation
    "T1068": ["privesc", "exploit"],  # Exploitation for Privilege Escalation
    "T1548": ["privesc", "postex"],  # Abuse Elevation Control Mechanism
    # Persistence
    "T1136": ["persistence", "postex"],  # Create Account
    "T1053": ["persistence", "postex"],  # Scheduled Task/Job
}


class _PublishedStrategyWrapper:
    """Wrapper to provide compatible interface for PublishedStrategy (Story 8.10).
    
    This class provides a consistent interface for accessing strategy data
    when receiving PublishedStrategy messages from DirectorEnsemble.
    Defined at module level for efficiency (avoids class recreation on each call).
    """
    __slots__ = (
        'id', 'engagement_id', 'objectives', 'avoid_targets', 'confidence',
        'timestamp', 'recommended_techniques', 'priorities', 'contributing_roles',
        'rationale'
    )
    
    def __init__(self, data: dict[str, Any], strategy_id: str):
        self.id = strategy_id
        self.engagement_id = data.get("engagement_id", "")
        self.objectives = data.get("objectives", [])
        self.avoid_targets = data.get("avoid_list", [])
        self.confidence = data.get("confidence", 0.0)
        self.timestamp = data.get("timestamp", "")
        # Extract technique IDs from recommended_techniques list of dicts
        techniques = data.get("recommended_techniques", [])
        self.recommended_techniques = [
            t.get("technique_id", t) if isinstance(t, dict) else t
            for t in techniques
        ]
        self.priorities = data.get("priorities", [])
        self.contributing_roles = data.get("contributing_roles", [])
        self.rationale = data.get("rationale", "")


class StigmergicAgent(Agent):
    """Base agent with stigmergic pub/sub hooks and LLM-driven tool selection.

    Extends the swarms.Agent to provide hooks for:
    - Publishing findings to the swarm
    - Reacting to signals from other agents
    - Coordinating via the EventBus
    - LLM-driven tool selection from 1,556+ Kali tools (Story 7.1.v2)
    """

    def __init__(
        self,
        agent_name: str,
        agent_id: str,
        engagement_id: str,
        event_bus: EventBus,
        role: AgentRole,
        specialty: str | None = None,
        llm_gateway: Optional["LLMGateway"] = None,
        manifest_loader: Optional["ManifestLoader"] = None,
        context_tracker: Optional["DecisionContextTracker"] = None,
        sharded_event_bus: Optional[ShardedEventBus] = None,
        *args,
        **kwargs,
    ):
        """Initialize the StigmergicAgent.

        Args:
            agent_name: Human readable name.
            agent_id: Unique identifier for this agent instance.
            engagement_id: ID of the current engagement.
            event_bus: EventBus instance for communication.
            role: Agent role (required for prompt selection).
            specialty: Optional specialty for prompt customization.
            llm_gateway: Optional LLMGateway for tool selection (uses singleton if not provided).
            manifest_loader: Optional ManifestLoader for tool lookup (creates default if not provided).
            context_tracker: Optional DecisionContextTracker for NFR37 emergence validation.
            sharded_event_bus: Optional ShardedEventBus for sharded findings pub/sub (Story 7.13).
            *args: Passthrough to swarms.Agent
            **kwargs: Passthrough to swarms.Agent (llm, system_prompt, etc.)
        """
        # Store role/specialty before super().__init__ which might overwrite
        _role = role
        _specialty = specialty
        self.system_prompt = PromptLibrary.get(role, specialty)

        # Ensure name and system_prompt are passed to swarms.Agent
        kwargs["agent_name"] = agent_name
        if "system_prompt" not in kwargs:
            kwargs["system_prompt"] = self.system_prompt

        # Provide defaults for required swarms params if not present, to avoid super() errors
        if "llm" not in kwargs and not args:
            # This might be risky if swarms validates strictly, but we assume caller provides it
            # or we handle it. pure base class might be instantiated with mocks.
            pass

        super().__init__(*args, **kwargs)

        # Re-assign after super().__init__ in case parent class has role attribute
        self.role = _role
        self.specialty = _specialty

        self.agent_id = agent_id
        self.engagement_id = engagement_id
        self.event_bus = event_bus
        self._decision_context: list[str] = []
        self._context_tracker = context_tracker
        self._status = "idle"
        self._pending_auth_request_id: str | None = None  # Story 7.16: Track active authorization
        # Bind context for structured logging per architecture requirement
        self._log = log.bind(agent_id=agent_id, engagement_id=engagement_id)
        self._throttle_monitor_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None  # Story 7.12

        # LLM tool selection components (Story 7.1.v2)
        self._llm_gateway = llm_gateway
        self._manifest = manifest_loader
        self._tool_help_cache: dict[str, str] = {}

        # Sharded event bus for findings (Story 7.13)
        self._sharded_bus = sharded_event_bus
        self._finding_cache: set[str] = set()  # Local dedupe cache
        self._swarm_findings: deque = deque(maxlen=50)  # Bounded buffer of findings from other agents
        
        # Director-Agent Feedback Loop (Story 7.17)
        self.__active_strategy: Optional["EmergentStrategy"] = None

    async def _publish_status(self, status: str) -> None:
        """Publish agent status to swarm:status for TUI visualization."""
        if self.event_bus:
            await self.event_bus.publish("swarm:status", {
                "agent_id": self.agent_id,
                "status": status,
                "role": self.role.value if self.role else "unknown",
            })

    async def _publish_terminal(self, command: str, output: str, tool_name: str = "kali") -> None:
        """Publish command + output to swarm:terminal for TUI TerminalStream."""
        if self.event_bus:
            await self.event_bus.publish("swarm:terminal", {
                "source": tool_name,
                "text": f"$ {command}\n{(output or '')[:500]}",
            })

    async def _kali_execute_and_publish(self, command: str, tool_name: str = "kali", timeout: int | None = None):
        """Execute via kali_execute and publish result to swarm:terminal.

        Resolves kali_execute from the subclass module so that test patches
        on e.g. ``cyberred.agents.ad.kali_execute`` are respected.
        """
        import sys
        caller_module = sys.modules.get(type(self).__module__)
        execute_fn = getattr(caller_module, "kali_execute", None) if caller_module else None
        if execute_fn is None:
            from cyberred.tools.kali_executor import kali_execute as execute_fn
        result = await execute_fn(command, timeout=timeout)
        await self._publish_terminal(command, result.stdout or result.stderr or "", tool_name)
        return result

    async def spawn(self):
        """Initialize async components and subscriptions."""
        await self._setup_subscriptions()
        await self._start_throttle_monitor()
        await self._start_heartbeat()  # Story 7.12
        self._status = "active"
        await self._publish_status("active")
        self._log.info("agent_spawned", status="active")

    async def _setup_subscriptions(self):
        """Subscribe to relevant stigmergic channels.

        Story 7.13: Uses ShardedEventBus for findings if available,
        falling back to non-sharded wildcard subscription.
        """
        # Subscribe to findings (sharded if available, per Story 7.13)
        if self._sharded_bus:
            await self._sharded_bus.subscribe_findings(
                self._handle_sharded_finding,
                finding_type="*",
            )
        else:
            # psubscribe for glob pattern — callback receives (channel, data)
            await self.event_bus.psubscribe("findings:*", self._handle_message)

        # Exact channels — wrap callback to match (channel, data) signature
        # subscribe() passes callback(data), _handle_message expects (channel, data)
        strategy_ch = f"strategies:{self.engagement_id}"
        await self.event_bus.subscribe(
            strategy_ch,
            lambda data, _ch=strategy_ch: self._handle_message(_ch, data),
        )
        kill_ch = "control:kill"
        await self.event_bus.subscribe(
            kill_ch,
            lambda data, _ch=kill_ch: self._handle_message(_ch, data),
        )

    async def _handle_message(self, channel: str, message):
        """Internal callback for EventBus subscriptions.

        Deserializes message and dispatches to on_signal.
        Handles both pre-parsed dicts (from psubscribe) and raw strings (from subscribe).

        Args:
            channel: The channel the message was received on.
            message: Parsed dict (psubscribe) or raw JSON string (subscribe wrapper).
        """
        # Guard against None/empty messages
        if message is None:
            self._log.warning("null_message_received", channel=channel)
            return

        try:
            if isinstance(message, dict):
                data = message
            else:
                try:
                    data = json.loads(message)
                except (json.JSONDecodeError, TypeError):
                    data = {"raw_content": str(message)}

            await self.on_signal(channel, data)
        except Exception as e:
            self._log.error("message_handling_error", channel=channel, error=str(e), exc_info=True)

    async def _handle_sharded_finding(self, channel: str, message: dict) -> None:
        """Handle finding from sharded channel with local deduplication.
        
        Story 7.13: Processes findings from sharded channels with local
        cache to prevent duplicate processing of the same finding.
        
        Args:
            channel: The sharded channel name.
            message: The finding message (may be dict or string).
        """
        # Handle string messages
        if isinstance(message, str):
            try:
                message = json.loads(message)
            except (json.JSONDecodeError, TypeError):
                message = {"raw_content": message}
        
        finding_id = message.get("id") or message.get("data", {}).get("id", "")
        
        # Local cache to prevent duplicate processing
        if finding_id and finding_id in self._finding_cache:
            return
        
        if finding_id:
            self._finding_cache.add(finding_id)
            # Keep cache bounded with random eviction (set is unordered)
            if len(self._finding_cache) > 10000:
                # Remove half of entries (random eviction since set is unordered)
                to_remove = list(self._finding_cache)[:5000]
                for item in to_remove:
                    self._finding_cache.discard(item)
        
        # Delegate to on_signal directly since message is already parsed
        await self.on_signal(channel, message)

    async def on_finding(self, target_hash: str, finding_type: str, content: dict[str, Any]):
        """Publish a finding to the swarm.
        
        Story 7.13: Uses ShardedEventBus for sharded publishing if available,
        otherwise falls back to non-sharded channel.

        Args:
            target_hash: Hash of the target (host/service).
            finding_type: Type of finding (e.g., 'sqli', 'open_port').
            content: The finding data.
        """
        message = {"agent_id": self.agent_id, "engagement_id": self.engagement_id, "data": content}
        
        if self._sharded_bus:
            # Story 7.13: Sharded publishing
            await self._sharded_bus.publish_finding(target_hash, finding_type, message)
            self._log.info("finding_published_sharded", finding_type=finding_type)
        else:
            # Fallback to non-sharded (backward compatibility)
            channel = f"findings:{target_hash}:{finding_type}"
            await self.event_bus.publish(channel, message)
            self._log.info("finding_published", channel=channel, finding_type=finding_type)

    async def _publish_to_swarm(self, target_hash: str, finding_type: str, message: dict[str, Any]) -> None:
        """Publish finding through sharded bus or fallback to direct publish.

        Subclasses should call this instead of event_bus.publish() for findings
        so that ShardedEventBus routing is used when available.

        Args:
            target_hash: Hash of the target.
            finding_type: Type of finding (e.g., 'exploit', 'open_port').
            message: The finding message payload.
        """
        if self._sharded_bus:
            wrapped = {"agent_id": self.agent_id, "engagement_id": self.engagement_id, "data": message}
            await self._sharded_bus.publish_finding(target_hash, finding_type, wrapped)
            self._log.info("finding_published_sharded", finding_type=finding_type)
        else:
            channel = f"findings:{target_hash}:{finding_type}"
            await self.event_bus.publish(channel, message)
            self._log.info("finding_published", channel=channel, finding_type=finding_type)

    async def on_signal(self, channel: str, data: dict[str, Any]):
        """Handle incoming stigmergic signal.

        Override this in subclasses to react to specific signals.

        Args:
            channel: The channel the signal was received on.
            data: The signal payload.
        """
        self._log.debug("signal_received", channel=channel)

        # Story 7.17: Handle strategy channel updates
        if channel.startswith("strategies:"):
            await self._handle_strategy_update(data)
            return

        # Stigmergic finding consumption — store findings from other agents
        # so the LLM can adapt tool selection based on swarm awareness
        if channel.startswith("findings:"):
            source_agent = data.get("agent_id", "")
            if source_agent and source_agent != self.agent_id:
                finding_data = data.get("data", {})
                self._swarm_findings.append({
                    "type": finding_data.get("type", "unknown"),
                    "target": finding_data.get("target", ""),
                    "tool": finding_data.get("tool", ""),
                    "severity": finding_data.get("severity", ""),
                    "evidence": str(finding_data.get("evidence", ""))[:200],
                })
                self._log.debug(
                    "swarm_finding_received",
                    source=source_agent,
                    finding_type=finding_data.get("type"),
                )
            # Still track signal_id for NFR37 decision context below

        # Base implementation tracking decision context if present in data
        # Handles NFR37 emergence validation
        signal_id = data.get("signal_id") or data.get("id")

        if signal_id:
            if self._context_tracker:
                source = data.get("agent_id", "unknown")
                signal_type = self._infer_signal_type(channel)

                self._context_tracker.record_signal(
                    agent_id=self.agent_id,
                    signal_id=signal_id,
                    signal_type=signal_type,
                    source=source,
                    channel=channel,
                )
            else:
                self._decision_context.append(signal_id)

    def _infer_signal_type(self, channel: str) -> str:
        """Infer signal type from channel name."""
        if channel.startswith("findings:"):
            return "finding"
        elif channel.startswith("strategies:"):
            return "strategy"
        elif channel.startswith("intel:"):
            return "intel"
        elif channel.startswith("rag:"):
            return "rag"
        elif channel.startswith("authorization:") or channel.startswith("auth:"):
            return "authorization"
        elif "phase" in channel:
            return "phase"
        else:
            return "status"

    # === Director-Agent Feedback Loop Methods (Story 7.17) ===

    def hydrate_context(self, findings: list[dict], strategy: dict | None = None) -> None:
        """Bulk-load swarm findings and strategy into agent (for respawn hydration).

        Populates _swarm_findings so the tool selection prompt includes
        predecessor knowledge. Optionally sets active strategy.

        Args:
            findings: List of finding dicts with type/target/tool/severity/evidence.
            strategy: Optional strategy dict to set as active strategy.
        """
        for f in findings:
            self._swarm_findings.append(f)
        if strategy is not None:
            self.__active_strategy = strategy
        self._log.info(
            "context_hydrated",
            findings_count=len(findings),
            has_strategy=strategy is not None,
        )

    @property
    def _active_strategy(self) -> Optional["EmergentStrategy"]:
        """Currently active strategy from Director.
        
        Returns:
            The EmergentStrategy if one is active, None otherwise.
        """
        return self.__active_strategy

    async def _handle_strategy_update(self, data: dict[str, Any]) -> None:
        """Process incoming strategy from Director.
        
        Handles both EmergentStrategy (Story 7.15) and PublishedStrategy (Story 8.10)
        formats. Parses the strategy data, stores it as the active strategy,
        and records it in the decision context for NFR37 tracking.
        
        For non-strategy messages on strategy channel (e.g., simple signals),
        falls back to basic signal tracking via signal_id.
        
        Args:
            data: Strategy data dictionary from EventBus message.
        """
        try:
            # Story 8.10: Check if this is a PublishedStrategy (from DirectorEnsemble)
            # PublishedStrategy has 'rationale' at top level but no 'pattern' field
            if "rationale" in data and "pattern" not in data:
                await self._handle_published_strategy(data)
            elif "pattern" in data:
                # Story 7.15: EmergentStrategy format (has 'pattern' field)
                await self._handle_emergent_strategy(data)
            else:
                # Fallback: Not a strategy message, just track signal_id if present
                signal_id = data.get("signal_id") or data.get("id")
                if signal_id:
                    if self._context_tracker:
                        self._context_tracker.record_signal(
                            agent_id=self.agent_id,
                            signal_id=signal_id,
                            signal_type="strategy",
                            source=data.get("agent_id", "unknown"),
                            channel=f"strategies:{self.engagement_id}",
                        )
                    else:
                        self._decision_context.append(signal_id)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            # Handle expected parsing/validation errors
            self._log.error("strategy_parse_error", error=str(e), exc_info=True)
        except Exception as e:
            # Log unexpected errors but re-raise to avoid silently swallowing critical issues
            self._log.error("strategy_update_unexpected_error", error=str(e), exc_info=True)
            raise

    async def _handle_emergent_strategy(self, data: dict[str, Any]) -> None:
        """Handle EmergentStrategy format (Story 7.15).
        
        Args:
            data: EmergentStrategy data dictionary.
        """
        from cyberred.orchestration.emergence.strategy import EmergentStrategy
        
        strategy = EmergentStrategy.from_json(data)
        self.__active_strategy = strategy
        
        # Validate and warn about unknown ATT&CK technique IDs
        if strategy.recommended_techniques:
            unknown_techniques = [
                t for t in strategy.recommended_techniques 
                if t not in ATTCK_TECHNIQUE_TOOL_MAP
            ]
            if unknown_techniques:
                self._log.warning(
                    "unknown_attck_techniques",
                    techniques=unknown_techniques,
                    strategy_id=strategy.id,
                )
        
        # Record in decision context (AC #5: type "director_strategy")
        if self._context_tracker:
            self._context_tracker.record_signal(
                agent_id=self.agent_id,
                signal_id=strategy.id,
                signal_type="director_strategy",
                source="director",
                channel=f"strategies:{self.engagement_id}",
            )
        else:
            self._decision_context.append(strategy.id)
        
        self._log.info(
            "strategy_received",
            strategy_id=strategy.id,
            objectives=strategy.objectives,
            avoid_targets=strategy.avoid_targets,
            recommended_techniques=strategy.recommended_techniques,
        )

    async def _handle_published_strategy(self, data: dict[str, Any]) -> None:
        """Handle PublishedStrategy format from DirectorEnsemble (Story 8.10).
        
        Converts PublishedStrategy to internal format and updates decision context.
        Per AC #5: agents incorporate strategy in decision_context.
        
        Args:
            data: PublishedStrategy data dictionary with keys:
                - engagement_id, objectives, priorities, recommended_techniques,
                - avoid_list, confidence, timestamp, contributing_roles, rationale
        """
        # Extract strategy ID or generate one
        strategy_id = data.get("id") or f"pub-strategy-{int(data.get('timestamp', time.time()))}"
        
        # Use module-level wrapper class for efficiency (avoids class recreation)
        strategy = _PublishedStrategyWrapper(data, strategy_id)
        self.__active_strategy = strategy  # type: ignore[assignment]
        
        # Validate and warn about unknown ATT&CK technique IDs
        if strategy.recommended_techniques:
            unknown_techniques = [
                t for t in strategy.recommended_techniques 
                if t not in ATTCK_TECHNIQUE_TOOL_MAP
            ]
            if unknown_techniques:
                self._log.warning(
                    "unknown_attck_techniques",
                    techniques=unknown_techniques,
                    strategy_id=strategy.id,
                )
        
        # Record in decision context (AC #5: type "director_strategy")
        if self._context_tracker:
            self._context_tracker.record_signal(
                agent_id=self.agent_id,
                signal_id=strategy.id,
                signal_type="director_strategy",
                source="director",
                channel=f"strategies:{self.engagement_id}",
            )
        else:
            self._decision_context.append(strategy.id)
        
        self._log.info(
            "published_strategy_received",
            strategy_id=strategy.id,
            objectives=strategy.objectives,
            avoid_targets=strategy.avoid_targets,
            recommended_techniques=strategy.recommended_techniques,
            contributing_roles=strategy.contributing_roles,
        )

    def _get_strategy_context(self) -> str:
        """Build strategy context string for LLM prompt.
        
        Formats the active strategy's objectives, recommended techniques,
        and avoid targets into a string suitable for LLM prompt injection.
        Sanitizes inputs to prevent prompt injection attacks.
        
        Returns:
            Formatted strategy context string, or empty string if no strategy.
        """
        if not self.__active_strategy:
            return ""
        
        def _sanitize(text: str) -> str:
            """Sanitize text to prevent LLM prompt injection."""
            # Remove common prompt injection patterns
            sanitized = text.replace("```", "")
            sanitized = sanitized.replace("ignore previous", "[FILTERED]")
            sanitized = sanitized.replace("disregard", "[FILTERED]")
            # Limit length to prevent token exhaustion
            return sanitized[:500] if len(sanitized) > 500 else sanitized
        
        parts = []
        if self.__active_strategy.objectives:
            sanitized_objectives = [_sanitize(obj) for obj in self.__active_strategy.objectives]
            parts.append(f"Objectives: {', '.join(sanitized_objectives)}")
        if self.__active_strategy.recommended_techniques:
            # Technique IDs should be alphanumeric only (T####)
            valid_techniques = [
                t for t in self.__active_strategy.recommended_techniques
                if t and len(t) <= 10 and t[0] == 'T'
            ]
            if valid_techniques:
                parts.append(f"Recommended ATT&CK: {', '.join(valid_techniques)}")
        if self.__active_strategy.avoid_targets:
            sanitized_targets = [_sanitize(t) for t in self.__active_strategy.avoid_targets]
            parts.append(f"Avoid targets: {', '.join(sanitized_targets)}")
        
        return "\n".join(parts)

    def _is_target_avoided(self, target: str) -> bool:
        """Check if target is in strategy avoid list.
        
        Supports exact matching and CIDR subnet matching for IP addresses.
        
        Args:
            target: Target IP, hostname, or URL to check.
            
        Returns:
            True if target should be avoided per strategy, False otherwise.
        """
        if not self.__active_strategy or not self.__active_strategy.avoid_targets:
            return False
        
        # Check exact match first
        if target in self.__active_strategy.avoid_targets:
            self._log.info(
                "target_avoided",
                target=target,
                reason="strategy_avoid_list",
                strategy_id=self.__active_strategy.id,
            )
            return True
        
        # Check CIDR subnet matching for IP addresses
        import ipaddress
        try:
            target_ip = ipaddress.ip_address(target)
            for avoid_entry in self.__active_strategy.avoid_targets:
                try:
                    # Check if avoid_entry is a CIDR network
                    if "/" in avoid_entry:
                        network = ipaddress.ip_network(avoid_entry, strict=False)
                        if target_ip in network:
                            self._log.info(
                                "target_avoided",
                                target=target,
                                reason="strategy_avoid_list",
                                strategy_id=self.__active_strategy.id,
                                matched_cidr=avoid_entry,
                            )
                            return True
                except ValueError:
                    continue  # Not a valid network, skip
        except ValueError:
            pass  # Target is not an IP address, skip CIDR check
        
        return False

    def _get_technique_tools(self, techniques: list[str]) -> list[str]:
        """Get tool names that map to ATT&CK technique IDs.
        
        Uses ATTCK_TECHNIQUE_TOOL_MAP to find tool categories,
        then queries the manifest for tools in those categories.
        
        Args:
            techniques: List of ATT&CK technique IDs (e.g., ["T1190", "T1078"]).
            
        Returns:
            List of tool names that match the techniques.
        """
        if not techniques:
            return []
        
        # Gather all categories for the techniques
        categories: set[str] = set()
        for technique in techniques:
            if technique in ATTCK_TECHNIQUE_TOOL_MAP:
                categories.update(ATTCK_TECHNIQUE_TOOL_MAP[technique])
        
        if not categories or not self._manifest:
            return []
        
        # Query manifest for tools in those categories
        tools: list[str] = []
        for category in categories:
            try:
                category_tools = self._manifest.get_by_category(category)
                tools.extend([t.name for t in category_tools])
            except Exception:
                pass  # Category might not exist in manifest
        
        return list(set(tools))  # Deduplicate

    async def on_complete(self, status: str, result: dict[str, Any]):
        """Publish completion status.

        Args:
            status: Completion status (e.g. 'success', 'failed').
            result: Result data.
        """
        channel = f"agents:{self.agent_id}:status"
        message = {
            "agent_id": self.agent_id,
            "engagement_id": self.engagement_id,
            "status": status,
            "result": result,
        }
        await self.event_bus.publish(channel, message)
        self._status = "idle"
        await self._publish_status(status)

    # AgentProtocol Implementation

    async def execute(self, task: str) -> AgentAction:
        """Execute a task using the underlying swarms Agent.

        This base implementation returns a stub AgentAction. Subclasses
        should override to integrate with swarms.Agent.run() or custom
        execution logic.

        Args:
            task: The task description to execute.

        Returns:
            AgentAction representing the execution result.

        Raises:
            Exception: Re-raises any execution errors after setting error status.
        """
        self._status = "active"

        # Check throttling (Story 7.2)
        try:
            is_throttled = await self._check_throttle()
            if is_throttled:
                self._status = "waiting"
                self._log.info("task_execution_throttled", task=task[:100] if task else None)

                settings = get_settings()
                max_wait = settings.agents.throttle.max_wait
                interval = settings.agents.throttle.check_interval
                start_wait = time.monotonic()

                while is_throttled:
                    if time.monotonic() - start_wait > max_wait:
                        raise ThrottleTimeoutError(agent_id=self.agent_id, wait_time=max_wait)

                    await asyncio.sleep(interval)
                    is_throttled = await self._check_throttle()

                self._status = "active"
                self._log.info("task_execution_resumed")

        except ThrottleTimeoutError:
            # Re-raise throttle timeout - this should not be swallowed
            raise
        except Exception as e:
            # Other errors in throttle logic -> log and proceed (Fail Open)
            self._log.error("throttle_logic_error", error=str(e))

        self._log.info("task_execution_started", task=task[:100] if task else None)

        try:
            # Base class returns a stub AgentAction.
            # Subclasses (e.g., GhostAgent) override this to call swarms.Agent.run()
            # and transform results into proper AgentAction instances.
            import datetime
            import uuid

            action = AgentAction(
                id=str(uuid.uuid4()),
                agent_id=self.agent_id,
                action_type="execute",
                target=task,
                timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
            )
            
            # Attach decision context (NFR37)
            if self._context_tracker:
                action = self._context_tracker.attach_to_action(self.agent_id, action)
            else:
                action.decision_context = self._decision_context
                # Clear local context after attachment
                self._decision_context = []
                
            return action

        except Exception as e:
            self._status = "error"
            self._log.error("task_execution_failed", error=str(e))
            raise

    async def reason(self, context: list[str]) -> str:
        """Generate reasoning."""
        # Simple base implementation
        return f"Reasoning based on {len(context)} signals."

    def get_id(self) -> str:
        return self.agent_id

    def get_status(self) -> str:
        return self._status

    def get_decision_context(self) -> list[str]:
        """Return the list of signal IDs that influenced this agent's decisions.

        This method supports NFR37 (Emergence Validation) by providing
        an audit trail of stigmergic signals that contributed to the
        agent's reasoning and actions.

        Returns:
            List of signal_id strings from received stigmergic signals.
        """
        if self._context_tracker:
            return self._context_tracker.get_context(self.agent_id)
        return self._decision_context

    async def shutdown(self) -> None:
        """Cleanup resources."""
        self._status = "shutdown"
        if self._throttle_monitor_task:
            self._throttle_monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._throttle_monitor_task
            self._throttle_monitor_task = None
        # Story 7.12: Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._heartbeat_task
            self._heartbeat_task = None
        # Unsubscribe if needed
        self._log.info("agent_shutdown")

    async def _start_throttle_monitor(self):
        """Start the background throttle monitoring task."""
        if self._throttle_monitor_task is None:
            self._throttle_monitor_task = asyncio.create_task(self._throttle_monitor_loop())

    # === Heartbeat Methods (Story 7.12) ===

    async def _start_heartbeat(self) -> None:
        """Start periodic heartbeat task."""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        """Send heartbeat every 10s.
        
        Sends an immediate heartbeat on start, then continues every 10s.
        Errors are logged but do not stop the loop to maintain crash detection.
        """
        # Send immediate heartbeat on start to register with crash monitor
        try:
            await self.send_heartbeat()
        except Exception as e:
            self._log.error("initial_heartbeat_error", error=str(e))
        
        while True:
            try:
                await asyncio.sleep(10)
                await self.send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.error("heartbeat_error", error=str(e))

    async def send_heartbeat(self) -> None:
        """Send heartbeat to crash monitor.
        
        Publishes heartbeat data to EventBus for crash detection.
        Per Story 7.12: heartbeat includes agent_id, engagement_id, task_id.
        """
        await self.event_bus.publish(
            f"agent:{self.agent_id}:heartbeat",
            {
                "agent_id": self.agent_id,
                "engagement_id": self.engagement_id,
                "task_id": getattr(self, "_current_task_id", None),
                "status": self._status,
            }
        )

    # === Checkpoint Methods (Story 7.12) ===

    async def save_checkpoint(self, checkpoint_manager: "CheckpointManager") -> None:
        """Save agent state to checkpoint for crash recovery.
        
        Args:
            checkpoint_manager: CheckpointManager instance for persistence.
        """
        from cyberred.storage.checkpoint import AgentState
        
        state = AgentState(
            agent_id=self.agent_id,
            agent_type=self.role.value,
            state={
                "specialty": self.specialty,
                "status": self._status,
                "tool_help_cache": self._tool_help_cache,
                "current_task_id": getattr(self, "_current_task_id", None),
            },
            last_action_id=getattr(self, "_last_action_id", None),
            decision_context=",".join(self._decision_context) if self._decision_context else None,
        )
        await checkpoint_manager.save_agent_state(self.engagement_id, state)
        self._log.info("agent_checkpoint_saved")

    async def restore_from_checkpoint(self, agent_state: "AgentState") -> None:
        """Restore agent state from checkpoint.
        
        Args:
            agent_state: AgentState loaded from checkpoint.
        """
        self._status = agent_state.state.get("status", "active")
        self._tool_help_cache = agent_state.state.get("tool_help_cache", {})
        self._current_task_id = agent_state.state.get("current_task_id")
        self._last_action_id = agent_state.last_action_id
        if agent_state.decision_context:
            self._decision_context = agent_state.decision_context.split(",")
        else:
            self._decision_context = []
        self._log.info("agent_restored_from_checkpoint", last_action=self._last_action_id)

    async def _throttle_monitor_loop(self):
        """Monitor throttle status and log transitions."""
        last_throttle_state = False

        while self._status != "shutdown":
            try:
                # Get check interval from settings
                settings = get_settings()
                interval = settings.agents.throttle.check_interval
                threshold = settings.agents.throttle.threshold

                # Get actual queue depth for accurate logging
                try:
                    from cyberred.llm.gateway import get_gateway
                    gateway = get_gateway()
                    actual_queue_depth = gateway.queue_depth
                except Exception:
                    actual_queue_depth = -1  # Unknown

                is_throttled = await self._check_throttle()

                if is_throttled and not last_throttle_state:
                    self._log.info(
                        "agent_throttled",
                        queue_depth=actual_queue_depth,
                        threshold=threshold,
                    )
                elif not is_throttled and last_throttle_state:
                    self._log.info(
                        "agent_unthrottled",
                        queue_depth=actual_queue_depth,
                        threshold=threshold,
                    )

                last_throttle_state = is_throttled

                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.error("throttle_monitor_error", error=str(e))
                await asyncio.sleep(5.0)  # Backoff on error

    async def _check_throttle(self) -> bool:
        """Check if agent should throttle execution.

        Logic:
        1. Get current queue depth from LLMGateway.
        2. Get throttle configuration (threshold).
        3. If threshold < 1.0, calculate max capacity based on `engagement.max_agents`.
           - This assumes max_agents is a rough proxy for "full load".
           - Threshold becomes `threshold * max_agents`.
        4. If threshold >= 1.0, use as raw count.
        5. Return True if queue_depth >= threshold.

        Fail-open: If gateway unavailable, return False.

        Returns:
            True if should throttle, False otherwise.
        """
        try:
            # Import here to avoid top-level circular imports
            from cyberred.llm.gateway import get_gateway

            gateway = get_gateway()
            queue_depth = gateway.queue_depth

            settings = get_settings()
            throttle_config = settings.agents.throttle

            threshold = throttle_config.threshold

            # Normalize threshold
            if threshold < 1.0:
                max_agents = settings.engagement.max_agents
                # Ensure at least 1 if max_agents is small
                target_depth = max(1, int(threshold * max_agents))
            else:
                target_depth = int(threshold)

            return queue_depth >= target_depth

        except Exception as e:
            # Fail-open strategy
            self._log.warning("throttle_check_failed", error=str(e))
            return False

    # === LLM Tool Selection Methods (Story 7.1.v2) ===

    def _get_role_categories(self) -> list[str]:
        """Get tool categories relevant for this agent's role.

        Returns:
            List of category strings for manifest lookup.
        """
        return ROLE_CATEGORIES.get(self.role, ["recon"])

    def _build_tool_selection_prompt(self, context: ToolSelectionContext) -> str:
        """Build LLM prompt for tool selection.

        Args:
            context: Tool selection context with target info and available tools.

        Returns:
            Formatted prompt string for LLM.
        """
        tools_list = ", ".join(context.available_tools[:50])  # Limit for token budget
        # Cap previous results to prevent prompt bloat over long engagements
        capped_results = context.previous_results[-15:] if context.previous_results else []
        previous_results_str = json.dumps(capped_results) if capped_results else "None"

        base_prompt = f"""Select the best tool for this objective and generate a complete command.

**Phase:** {context.phase}
**Target Info:** {json.dumps(context.target_info)}
**Objective:** {context.objective}
**Constraints:** {", ".join(context.constraints) or "None"}
**Previous Results (own, last 15):** {previous_results_str}

**Available Tools:** {tools_list}"""

        # Stigmergic swarm awareness — inject findings from other agents
        if self._swarm_findings:
            swarm_items = list(self._swarm_findings)[-20:]  # Last 20 only
            swarm_summary = "\n".join(
                f"- [{f['severity']}] {f['type']} on {f['target']} via {f['tool']}: {f['evidence']}"
                for f in swarm_items
            )
            base_prompt += f"\n\n**Swarm Findings (from other agents):**\n{swarm_summary}"
            base_prompt += "\nAvoid duplicating work already done. Target services/vulnerabilities not yet covered."
            self._log.info(
                "swarm_context_injected",
                swarm_finding_count=len(swarm_items),
            )

        # Story 7.17: Include strategy context if active
        strategy_context = self._get_strategy_context()
        if strategy_context:
            base_prompt += f"\n\n**Director Strategy:**\n{strategy_context}"

        base_prompt += """

COMMAND RULES:
- Generate a single tool command. You may pipe output through filters (e.g. | grep, | sort, | head).
- Do NOT use semicolons (;) to chain unrelated commands.
- Do NOT use $(), backticks, or variable substitution.
- Quote arguments containing special characters with single quotes.

Respond with JSON only:
{"tool_name": "...", "command": "...", "rationale": "...", "expected_output_type": "json|xml|text", "confidence": 0.0-1.0, "priority": 1-10, "alternatives": []}"""

        return base_prompt

    def _parse_tool_selection(self, response: str) -> ToolSelection:
        """Parse LLM response into ToolSelection.

        Args:
            response: Raw LLM response string.

        Returns:
            Parsed ToolSelection dataclass.

        Raises:
            ToolSelectionError: If response cannot be parsed.
        """
        try:
            # Try to extract JSON from response
            response = response.strip()

            # Strip <think>...</think> tags (MiniMax M2 reasoning model)
            import re
            response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()

            if response.startswith("```"):
                # Handle markdown code blocks
                lines = response.split("\n")
                json_lines = [line for line in lines if not line.startswith("```")]
                response = "\n".join(json_lines)

            # Extract JSON object if surrounded by other text
            if not response.startswith("{"):
                match = re.search(r"\{.*\}", response, flags=re.DOTALL)
                if match:
                    response = match.group(0)

            data = json.loads(response)
            return ToolSelection(
                tool_name=data["tool_name"],
                command=data["command"],
                rationale=data["rationale"],
                expected_output_type=data["expected_output_type"],
                confidence=float(data.get("confidence", 0.8)),
                priority=int(data.get("priority", 5)),
                alternatives=data.get("alternatives", []),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ToolSelectionError(
                agent_id=self.agent_id, reason=f"Failed to parse LLM response: {e}"
            ) from e

    async def select_tool(self, context: ToolSelectionContext) -> ToolSelection:
        """Select tool from manifest using LLM reasoning.

        Args:
            context: Context including target info, objective, available_tools, phase.

        Returns:
            ToolSelection with chosen tool, command, and rationale.

        Raises:
            ToolSelectionError: If LLM fails to select valid tool.
        """
        # If available_tools not provided in context, populate from manifest based on role
        if not context.available_tools and self._manifest:
            categories = self._get_role_categories()
            available_tools: list[str] = []
            for category in categories:
                tools = self._manifest.get_by_category(category)
                available_tools.extend([t.name for t in tools])
            # Update context with available tools
            context = ToolSelectionContext(
                objective=context.objective,
                target_info=context.target_info,
                available_tools=available_tools,
                phase=context.phase,
                constraints=context.constraints,
                previous_results=context.previous_results,
            )

        # Build selection prompt
        prompt = self._build_tool_selection_prompt(context)

        # Publish "thinking" status for TUI
        await self._publish_status("thinking")

        # Query LLM
        if self._llm_gateway:
            from cyberred.llm.provider import LLMRequest

            request = LLMRequest(
                prompt=prompt,
                model="default",  # Router will select appropriate model
                system_prompt=self.system_prompt,
                max_tokens=5000,  # Thinking models (MiniMax) need room for <think> + JSON
            )
            response = await self._llm_gateway.agent_complete(request)
            # Detect gateway error responses (content="" with error finish_reason)
            if response.finish_reason and response.finish_reason.startswith("error:"):
                raise ToolSelectionError(
                    agent_id=self.agent_id,
                    reason=f"LLM call failed: {response.finish_reason}",
                )
            response_text = response.content
        else:
            raise ToolSelectionError(agent_id=self.agent_id, reason="No LLM gateway configured")

        # Parse and validate response
        selection = self._parse_tool_selection(response_text)

        # Track in decision_context (NFR37) - use tracker if available
        if self._context_tracker:
            self._context_tracker.record_signal(
                agent_id=self.agent_id,
                signal_id=selection.selection_id,
                signal_type="strategy",  # Tool selection is a strategic decision
                source=self.agent_id,
                channel="tool_selection",
            )
        else:
            self._decision_context.append(selection.selection_id)

        self._log.info(
            "tool_selected",
            tool=selection.tool_name,
            rationale=selection.rationale[:100],
            selection_id=selection.selection_id,
        )

        # Publish to swarm:brain for TUI BrainStream widget
        if self.event_bus:
            await self.event_bus.publish("swarm:brain", {
                "category": "THINKING",
                "text": f"[{self.agent_name}] -> {selection.tool_name}: {selection.command[:80]}",
            })

        # Publish "scanning" status for TUI
        await self._publish_status("scanning")

        return selection

    def _validate_command(self, command: str, tool: str) -> str:
        """Validate generated command.

        Args:
            command: Generated command string.
            tool: Expected tool name.

        Returns:
            Validated command string.

        Raises:
            ValueError: If command validation fails.
        """
        command = command.strip()
        if not command.startswith(tool):
            raise ValueError(f"Generated command must start with '{tool}', got: {command[:50]}")
        return command

    async def generate_command(
        self, tool: str, target: str, options: dict[str, Any] | None = None
    ) -> str:
        """Generate tool command using LLM and --help output.

        Args:
            tool: Tool name (e.g., "nmap").
            target: Target specification.
            options: Additional options (stealth, output format, etc.).

        Returns:
            Complete command string ready for kali_execute().

        Raises:
            ValueError: If generated command is invalid.
        """
        # Get cached --help output
        help_output = await self._get_tool_help(tool)

        # Build command generation prompt
        prompt = f"""Generate a {tool} command for target: {target}

Tool help output:
```
{help_output}
```

Requirements:
- Target: {target}
- Options: {options or "default"}
- Output format: Prefer structured output (JSON/XML) if available

Return ONLY the command, no explanation."""

        # Query LLM
        if self._llm_gateway:
            from cyberred.llm.provider import LLMRequest

            request = LLMRequest(
                prompt=prompt,
                model="default",  # Router will select appropriate model
                system_prompt=self.system_prompt,
                max_tokens=200,
            )
            response = await self._llm_gateway.agent_complete(request)
            command = response.content.strip()
        else:
            # Fallback if no gateway
            command = f"{tool} {target}"

        # Validate command
        return self._validate_command(command, tool)

    async def _get_tool_help(self, tool: str) -> str:
        """Get tool --help output, cached per session.

        Args:
            tool: Tool name.

        Returns:
            Help output string (truncated to 80 lines).
        """
        if tool in self._tool_help_cache:
            return self._tool_help_cache[tool]

        try:
            # Execute --help and capture output
            from cyberred.tools.kali_executor import kali_execute

            result = await kali_execute(f"{tool} --help 2>&1 | head -80", timeout=10)

            help_text = result.stdout if result.success else f"No help available for {tool}"
        except Exception as e:
            self._log.warning("tool_help_failed", tool=tool, error=str(e))
            help_text = f"No help available for {tool}"

        # Truncate to 80 lines max
        lines = help_text.split("\n")
        if len(lines) > 80:
            help_text = "\n".join(lines[:80])

        self._tool_help_cache[tool] = help_text

        self._log.debug("tool_help_cached", tool=tool, length=len(help_text))

        return help_text

    # === Authorization Methods (Story 7.16) ===

    async def _request_authorization(
        self,
        action: str,
        target: str,
        justification: str,
        alternative_on_denial: bool = True,
    ) -> bool:
        """Request operator authorization for sensitive actions (FR13, FR15).

        Publishes authorization request and waits for operator response.
        Agent enters WAITING_AUTHORIZATION state while waiting.
        Per FR16, wait is indefinite (no auto-deny).

        Args:
            action: Action requiring authorization (e.g., "lateral_movement").
            target: Target of the action (e.g., IP address, hostname).
            justification: Reason for the action.
            alternative_on_denial: If True, calls _select_alternative_action() on denial.

        Returns:
            True if authorization granted, False if denied.
            Note: When denied with alternative_on_denial=True and an alternative
            is found, status becomes "active" but still returns False.
        """
        request_id = str(uuid.uuid4())
        previous_status = self._status
        
        try:
            self._pending_auth_request_id = request_id
            
            # Transition to WAITING_AUTHORIZATION state
            self._status = "waiting_authorization"
            self._log.info(
                "authorization_requested",
                request_id=request_id,
                action=action,
                target=target,
                status=self._status,
            )

            # Publish authorization request
            request_channel = f"authorization:{request_id}"
            request_payload = {
                "request_id": request_id,
                "agent_id": self.agent_id,
                "engagement_id": self.engagement_id,
                "action": action,
                "target": target,
                "justification": justification,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            await self.event_bus.publish(request_channel, request_payload)

            # Wait for response on auth:{request_id}:response channel
            # Per FR16: timeout=None means wait indefinitely (no auto-deny)
            response_channel = f"auth:{request_id}:response"
            response = await self.event_bus.subscribe_once(response_channel, timeout=None)

            # Process response
            granted = response.get("granted", False) if response else False
            reason = response.get("reason", "") if response else "no_response"

            # Record authorization decision in decision_context (NFR37)
            auth_signal_id = f"auth:{request_id}:{'granted' if granted else 'denied'}"
            if self._context_tracker:
                self._context_tracker.record_signal(
                    agent_id=self.agent_id,
                    signal_id=auth_signal_id,
                    signal_type="authorization",
                    source=response.get("operator_id", "operator") if response else "system",
                    channel=response_channel,
                )
            else:
                self._decision_context.append(auth_signal_id)

            if granted:
                # Transition back to RUNNING state
                self._status = "active"
                self._log.info(
                    "authorization_granted",
                    request_id=request_id,
                    action=action,
                    target=target,
                )
            else:
                self._log.info(
                    "authorization_denied",
                    request_id=request_id,
                    action=action,
                    target=target,
                    reason=reason,
                )
                
                if alternative_on_denial:
                    # Select alternative action
                    alternative = await self._select_alternative_action(action, reason)
                    if alternative:
                        self._status = "active"  # ALTERNATIVE_PATH -> RUNNING
                    else:
                        self._status = previous_status  # Restore previous state
                else:
                    self._status = previous_status

            return granted
        finally:
            # Always clear pending request, even on exception
            self._pending_auth_request_id = None

    async def _select_alternative_action(
        self,
        original_action: str,
        denial_reason: str,
    ) -> str | None:
        """Select alternative action after authorization denial.

        Uses select_tool() with modified context indicating the denial,
        allowing the LLM to suggest a different approach.

        Args:
            original_action: The action that was denied.
            denial_reason: Reason provided for denial.

        Returns:
            Alternative action/tool name, or None if no alternative found.
        """
        self._log.info(
            "selecting_alternative_action",
            original_action=original_action,
            denial_reason=denial_reason,
        )

        if not self._llm_gateway:
            self._log.warning("no_llm_gateway_for_alternative")
            return None

        # Build context for alternative selection
        context = ToolSelectionContext(
            objective=f"Find alternative to denied action: {original_action}",
            target_info={
                "denied_action": original_action,
                "denial_reason": denial_reason,
                "phase": "alternative_selection",
            },
            available_tools=[],  # Will be populated by select_tool based on role
            phase="postex",
            constraints=["avoid_lateral_movement", "lower_privilege_required"],
            previous_results=[],
        )

        try:
            selection = await self.select_tool(context)
            alternative = selection.tool_name

            # Log alternative selection in decision_context
            alt_signal_id = f"alternative:{original_action}:{alternative}"
            if self._context_tracker:
                self._context_tracker.record_signal(
                    agent_id=self.agent_id,
                    signal_id=alt_signal_id,
                    signal_type="strategy",
                    source=self.agent_id,
                    channel="alternative_selection",
                )
            else:
                self._decision_context.append(alt_signal_id)

            self._log.info(
                "alternative_action_selected",
                original_action=original_action,
                alternative=alternative,
                rationale=selection.rationale[:100] if selection.rationale else "",
            )

            return alternative

        except ToolSelectionError as e:
            self._log.warning(
                "alternative_selection_failed",
                original_action=original_action,
                error=str(e),
            )
            return None
