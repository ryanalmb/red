"""Base agent class for Cyber-Red stigmergic coordination.

This module implements the StigmergicAgent base class which extends the
swarms.Agent to add P2P coordination capabilities via Redis Pub/Sub
and LLM-driven tool selection (Story 7.1.v2).
"""

import asyncio
import contextlib
import hashlib
import json
import os
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
from cyberred.core.finding_policy import assess_finding_payload
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
    "T1590": ["recon", "osint", "enumeration"],  # Gather Victim Network Information
    "T1593": ["osint", "recon"],  # Search Open Technical Databases
    "T1596": ["osint", "recon", "enumeration"],  # Search Open Websites/Domains
    # Discovery
    "T1046": ["recon", "discovery"],  # Network Service Discovery (nmap, masscan)
    "T1018": ["recon", "enumeration"],  # Remote System Discovery (nbtscan, enum4linux)
    "T1082": ["postex", "enumeration"],  # System Information Discovery (linpeas, winpeas)
    "T1016": ["postex", "enumeration"],  # System Network Configuration Discovery
    "T1087": ["postex", "enumeration", "credential"],  # Account Discovery (net user, enum4linux)
    "T1069": ["postex", "enumeration"],  # Permission Groups Discovery
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
    _unknown_technique_warned: set[tuple[str, tuple[str, ...]]] = set()

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
        self._recent_tool_results: deque[dict[str, Any]] = deque(maxlen=80)
        self._command_fingerprints: deque[str] = deque(maxlen=400)
        self._command_fingerprint_set: set[str] = set()
        self._command_retry_state: dict[str, dict[str, Any]] = {}
        self._selection_context_token = ""
        try:
            self._command_retry_base_cooldown_s = max(
                10,
                int(os.getenv("CYBERRED_COMMAND_RETRY_COOLDOWN_S", "120")),
            )
        except ValueError:
            self._command_retry_base_cooldown_s = 120
        try:
            self._command_retry_max_attempts = max(
                1,
                int(os.getenv("CYBERRED_COMMAND_RETRY_MAX_ATTEMPTS", "3")),
            )
        except ValueError:
            self._command_retry_max_attempts = 3
        self._no_finding_streak = 0
        try:
            self._no_finding_streak_threshold = max(
                2,
                int(os.getenv("CYBERRED_AGENT_NO_FINDING_STREAK", "3")),
            )
        except ValueError:
            self._no_finding_streak_threshold = 3

        # Sharded event bus for findings (Story 7.13)
        self._sharded_bus = sharded_event_bus
        self._finding_cache: set[str] = set()  # Local dedupe cache
        try:
            self._swarm_findings_maxlen = max(
                50,
                int(os.getenv("CYBERRED_SWARM_FINDINGS_MAXLEN", "200")),
            )
        except ValueError:
            self._swarm_findings_maxlen = 200
        self._swarm_findings: deque = deque(maxlen=self._swarm_findings_maxlen)
        self._swarm_finding_details: dict[str, dict[str, Any]] = {}
        try:
            self._swarm_prompt_findings_limit = max(
                10,
                int(os.getenv("CYBERRED_SWARM_PROMPT_FINDINGS", "30")),
            )
        except ValueError:
            self._swarm_prompt_findings_limit = 30
        try:
            self._swarm_auto_expand_count = max(
                1,
                int(os.getenv("CYBERRED_SWARM_AUTO_EXPAND_COUNT", "8")),
            )
        except ValueError:
            self._swarm_auto_expand_count = 8
        try:
            self._swarm_signal_chars = max(
                120,
                int(os.getenv("CYBERRED_SWARM_SIGNAL_CHARS", "280")),
            )
        except ValueError:
            self._swarm_signal_chars = 280
        try:
            self._swarm_expand_signal_chars = max(
                self._swarm_signal_chars,
                int(os.getenv("CYBERRED_SWARM_EXPAND_SIGNAL_CHARS", "700")),
            )
        except ValueError:
            self._swarm_expand_signal_chars = 700

        # Track subscriptions for cleanup on shutdown (prevents Redis connection leaks)
        self._subscriptions: list = []
        
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
        self._record_command_execution(command, tool_name, result)
        await self._publish_terminal(command, result.stdout or result.stderr or "", tool_name)
        return result

    def _execution_metadata(self, result: Any, command: str | None = None) -> dict[str, Any]:
        """Build normalized execution metadata for finding evidence payloads."""
        exit_code_raw = getattr(result, "exit_code", None)
        if isinstance(exit_code_raw, bool):
            exit_code: int | None = int(exit_code_raw)
        elif isinstance(exit_code_raw, int):
            exit_code = exit_code_raw
        elif isinstance(exit_code_raw, str) and exit_code_raw.strip().lstrip("-").isdigit():
            try:
                exit_code = int(exit_code_raw.strip())
            except ValueError:
                exit_code = None
        else:
            exit_code = None

        error_type_raw = getattr(result, "error_type", None)
        error_type = (
            error_type_raw.strip()
            if isinstance(error_type_raw, str) and error_type_raw.strip()
            else None
        )

        duration_raw = getattr(result, "duration_ms", None)
        duration_ms = duration_raw if isinstance(duration_raw, (int, float)) else None

        return {
            "command": str(command or ""),
            "stdout": str(getattr(result, "stdout", "") or "")[:4000],
            "stderr": str(getattr(result, "stderr", "") or "")[:2000],
            "exit_code": exit_code,
            "error_type": error_type,
            "success": bool(getattr(result, "success", False)),
            "duration_ms": duration_ms,
        }

    def _normalize_command(self, command: str) -> str:
        return " ".join((command or "").split()).strip()

    def _selection_target_hint(self, target_info: dict[str, Any]) -> str:
        if not isinstance(target_info, dict):
            return str(getattr(self, "_current_target", "") or "")
        for key in ("target", "domain_controller", "interface", "url", "host"):
            value = target_info.get(key)
            if value:
                return str(value)
        return str(getattr(self, "_current_target", "") or "")

    def _build_command_fingerprints(
        self,
        tool_name: str,
        command: str,
        *,
        phase: str = "",
        target: str = "",
    ) -> tuple[str, str]:
        normalized = self._normalize_command(command)
        base = hashlib.sha1(f"{tool_name}|{normalized}".encode("utf-8")).hexdigest()
        scoped = hashlib.sha1(
            f"{tool_name}|{normalized}|{phase}|{target}".encode("utf-8")
        ).hexdigest()
        return base, scoped

    def _refresh_command_fingerprint_set(self) -> None:
        self._command_fingerprint_set = set(self._command_fingerprints)

    def _build_context_token(
        self,
        context: ToolSelectionContext | None = None,
        *,
        phase: str = "",
        target: str = "",
    ) -> str:
        """Build compact context token for retry gating."""
        if context is not None:
            phase = context.phase or phase
            target = self._selection_target_hint(context.target_info) or target
            constraints = sorted(str(item) for item in (context.constraints or []) if item)
        else:
            constraints = []

        strategy_id = ""
        if self._active_strategy is not None:
            strategy_id = str(
                getattr(self._active_strategy, "id", "")
                or getattr(self._active_strategy, "strategy_id", "")
                or ""
            )

        recent_swarm = [
            (
                str(item.get("type", "")),
                str(item.get("target", "")),
                str(item.get("tool", "")),
            )
            for item in list(self._swarm_findings)[-8:]
            if isinstance(item, dict)
        ]

        payload = {
            "phase": str(phase or ""),
            "target": str(target or ""),
            "strategy": strategy_id,
            "constraints": constraints,
            "recent_swarm": recent_swarm,
        }
        return hashlib.sha1(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def _is_retry_blocked(self, fingerprint: str, context_token: str) -> bool:
        state = self._command_retry_state.get(fingerprint)
        if not isinstance(state, dict):
            return False

        status = str(state.get("status") or "").strip().lower()
        attempts = int(state.get("attempts") or 0)
        last_context = str(state.get("context_token") or "")
        last_attempt_ts = float(state.get("last_attempt_ts") or 0.0)
        now = time.time()

        if status == "success":
            return True

        if context_token and last_context and context_token != last_context:
            return False

        if attempts >= self._command_retry_max_attempts:
            return True

        backoff_multiplier = max(1, 2 ** max(0, attempts - 1))
        cooldown_s = min(
            float(self._command_retry_base_cooldown_s * backoff_multiplier),
            1800.0,
        )
        if (now - last_attempt_ts) < cooldown_s:
            return True
        return False

    def _is_recent_command(
        self,
        tool_name: str,
        command: str,
        *,
        phase: str = "",
        target: str = "",
        context_token: str = "",
    ) -> bool:
        base_fp, scoped_fp = self._build_command_fingerprints(
            tool_name,
            command,
            phase=phase,
            target=target,
        )
        if (base_fp not in self._command_fingerprint_set) and (
            scoped_fp not in self._command_fingerprint_set
        ):
            return False
        if self._is_retry_blocked(scoped_fp, context_token):
            return True
        if self._is_retry_blocked(base_fp, context_token):
            return True
        return False

    def _record_command_execution(self, command: str, tool_name: str, result: Any) -> None:
        target = str(getattr(self, "_current_target", "") or "")
        phase = self.role.value if hasattr(self, "role") and self.role else "unknown"
        base_fp, scoped_fp = self._build_command_fingerprints(
            tool_name,
            command,
            phase=phase,
            target=target,
        )
        self._command_fingerprints.append(base_fp)
        self._command_fingerprints.append(scoped_fp)
        self._refresh_command_fingerprint_set()

        success = bool(getattr(result, "success", False))
        status = "success" if success else "failed"
        context_token = str(
            self._selection_context_token
            or self._build_context_token(phase=phase, target=target)
        )
        now_ts = time.time()
        for fingerprint in (base_fp, scoped_fp):
            previous = self._command_retry_state.get(fingerprint) or {}
            previous_context = str(previous.get("context_token") or "")
            previous_attempts = int(previous.get("attempts") or 0)
            attempts = 1 if context_token != previous_context else previous_attempts + 1
            self._command_retry_state[fingerprint] = {
                "status": status,
                "attempts": attempts,
                "last_attempt_ts": now_ts,
                "context_token": context_token,
            }
        if len(self._command_retry_state) > 3000:
            oldest = sorted(
                self._command_retry_state.items(),
                key=lambda item: float(item[1].get("last_attempt_ts") or 0.0),
            )[:1000]
            for key, _ in oldest:
                self._command_retry_state.pop(key, None)

        exit_code_raw = getattr(result, "exit_code", None)
        if isinstance(exit_code_raw, bool):
            exit_code: int | None = int(exit_code_raw)
        elif isinstance(exit_code_raw, int):
            exit_code = exit_code_raw
        elif isinstance(exit_code_raw, str) and exit_code_raw.strip().lstrip("-").isdigit():
            try:
                exit_code = int(exit_code_raw.strip())
            except ValueError:
                exit_code = None
        else:
            exit_code = None

        result_summary: dict[str, Any] = {
            "tool": tool_name,
            "command": self._normalize_command(command)[:400],
            "success": success,
            "exit_code": exit_code,
            "target": target,
            "phase": phase,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        stdout = getattr(result, "stdout", "")
        stderr = getattr(result, "stderr", "")
        if stdout:
            result_summary["stdout_preview"] = str(stdout)[:200]
        if stderr:
            result_summary["stderr_preview"] = str(stderr)[:200]
        self._recent_tool_results.append(result_summary)

    def get_recent_tool_results(self, limit: int = 30) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        return list(self._recent_tool_results)[-limit:]

    def _record_iteration_findings(self, findings_count: int) -> int:
        """Track consecutive no-yield iterations and return current streak."""
        if findings_count > 0:
            self._no_finding_streak = 0
            return 0
        self._no_finding_streak += 1
        return self._no_finding_streak

    def _add_novelty_constraints(
        self,
        context: ToolSelectionContext,
        streak: int,
    ) -> ToolSelectionContext:
        """Inject progressively stronger novelty constraints after no-yield streaks."""
        if streak < 2:
            return context

        new_constraints = list(context.constraints)
        if streak >= 2:
            novelty_constraint = (
                "pivot to a different tool family or target facet than recent attempts"
            )
            if novelty_constraint not in new_constraints:
                new_constraints.append(novelty_constraint)
        if streak >= self._no_finding_streak_threshold:
            hard_novelty_constraint = (
                "avoid commands similar to prior no-yield runs; choose materially different technique"
            )
            if hard_novelty_constraint not in new_constraints:
                new_constraints.append(hard_novelty_constraint)
        return ToolSelectionContext(
            objective=context.objective,
            target_info=context.target_info,
            available_tools=context.available_tools,
            phase=context.phase,
            constraints=new_constraints,
            previous_results=context.previous_results,
        )

    async def _publish_swarm_log(
        self,
        category: str,
        message: str,
        **metadata: Any,
    ) -> None:
        """Best-effort observability publish."""
        if not self.event_bus:
            return
        payload: dict[str, Any] = {"category": category, "message": message}
        payload.update(metadata)
        try:
            await self.event_bus.publish("swarm:log", payload)
        except Exception as e:
            self._log.debug("swarm_log_publish_failed", error=str(e), category=category)

    def _buffer_finding_retry(
        self,
        buffer_ref: list[dict[str, Any]],
        *,
        target_hash: str,
        finding_type: str,
        message: dict[str, Any],
    ) -> None:
        """Store finding payload for retry while preserving sharding metadata."""
        buffer_ref.append(
            {
                "target_hash": target_hash,
                "finding_type": finding_type,
                "message": dict(message or {}),
                "channel": f"findings:{target_hash}:{finding_type}",
            }
        )

    async def _flush_buffered_findings(
        self,
        buffer_ref: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Flush buffered findings through sharded publish path when possible."""
        remaining: list[dict[str, Any]] = []
        for item in buffer_ref:
            message = item.get("message")
            if not isinstance(message, dict):
                continue

            target_hash = str(item.get("target_hash") or "").strip()
            finding_type = str(item.get("finding_type") or "").strip()
            channel = str(item.get("channel") or "").strip()

            try:
                if target_hash and finding_type:
                    await self._publish_to_swarm(target_hash, finding_type, message)
                elif channel:
                    await self.event_bus.publish(channel, message)
                else:
                    continue
            except Exception:
                remaining.append(item)
        return remaining

    def export_runtime_hydration(self) -> dict[str, Any]:
        retry_state_items = sorted(
            self._command_retry_state.items(),
            key=lambda item: float(item[1].get("last_attempt_ts") or 0.0),
        )[-500:]
        detail_items = sorted(
            self._swarm_finding_details.items(),
            key=lambda item: str(item[1].get("timestamp") or ""),
        )[-300:]
        return {
            "decision_context": list(self._decision_context)[-200:],
            "swarm_findings": list(self._swarm_findings)[-self._swarm_findings_maxlen:],
            "swarm_finding_details": {
                key: value for key, value in detail_items if isinstance(value, dict)
            },
            "previous_results": self.get_recent_tool_results(limit=60),
            "command_fingerprints": list(self._command_fingerprints)[-300:],
            "command_retry_state": {
                key: value for key, value in retry_state_items if isinstance(value, dict)
            },
        }

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

        All subscription handles are stored in ``self._subscriptions``
        so they can be cleanly cancelled in ``shutdown()``, releasing
        the underlying Redis pubsub connections.
        """
        # Subscribe to findings (sharded if available, per Story 7.13)
        if self._sharded_bus:
            shard_subs = await self._sharded_bus.subscribe_findings(
                self._handle_sharded_finding,
                finding_type="*",
            )
            # subscribe_findings may return a list of subscriptions or None
            if shard_subs:
                if isinstance(shard_subs, list):
                    self._subscriptions.extend(shard_subs)
                else:
                    self._subscriptions.append(shard_subs)
        else:
            # psubscribe for glob pattern — callback receives (channel, data)
            sub = await self.event_bus.psubscribe("findings:*", self._handle_message)
            self._subscriptions.append(sub)

        # Exact channels — wrap callback to match (channel, data) signature
        # subscribe() passes callback(data), _handle_message expects (channel, data)
        strategy_ch = f"strategies:{self.engagement_id}"
        sub = await self.event_bus.subscribe(
            strategy_ch,
            lambda data, _ch=strategy_ch: self._handle_message(_ch, data),
        )
        self._subscriptions.append(sub)

        kill_ch = "control:kill"
        sub = await self.event_bus.subscribe(
            kill_ch,
            lambda data, _ch=kill_ch: self._handle_message(_ch, data),
        )
        self._subscriptions.append(sub)

        telemetry_ch = "swarm:findings_telemetry"
        sub = await self.event_bus.subscribe(
            telemetry_ch,
            lambda data, _ch=telemetry_ch: self._handle_message(_ch, data),
        )
        self._subscriptions.append(sub)

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

    def _is_primary_finding(self, finding_data: dict[str, Any]) -> bool:
        """Return True when finding should propagate on primary stigmergy lane."""
        outcome = str(finding_data.get("outcome_status") or "").strip().lower()
        quality = str(finding_data.get("evidence_quality") or "").strip().lower()
        return outcome == "validated" and quality != "low"

    async def _publish_finding_telemetry(
        self,
        *,
        target_hash: str,
        finding_type: str,
        finding_data: dict[str, Any],
    ) -> None:
        """Publish attempted/failed findings to telemetry lane."""
        if not self.event_bus:
            return
        payload = {
            "agent_id": self.agent_id,
            "engagement_id": self.engagement_id,
            "target_hash": target_hash,
            "finding_type": finding_type,
            "outcome_status": finding_data.get("outcome_status", "attempted"),
            "evidence_quality": finding_data.get("evidence_quality", "low"),
            "validation_reason": finding_data.get("validation_reason", ""),
            "validation_confidence": finding_data.get("validation_confidence", 0.0),
            "data": finding_data,
            "timestamp": finding_data.get("timestamp", datetime.now(UTC).isoformat()),
        }
        try:
            await self.event_bus.publish("swarm:findings_telemetry", payload)
            self._log.info(
                "finding_telemetry_published",
                finding_type=finding_type,
                outcome_status=payload["outcome_status"],
            )
        except Exception as e:
            self._log.warning(
                "finding_telemetry_publish_failed",
                finding_type=finding_type,
                error=str(e),
            )

    async def _publish_normalized_finding(
        self,
        *,
        target_hash: str,
        finding_type: str,
        finding_data: dict[str, Any],
    ) -> None:
        await self._maybe_publish_objective_event(finding_type, finding_data)

        if not self._is_primary_finding(finding_data):
            await self._publish_finding_telemetry(
                target_hash=target_hash,
                finding_type=finding_type,
                finding_data=finding_data,
            )
            return

        message = {
            "agent_id": self.agent_id,
            "engagement_id": self.engagement_id,
            "data": finding_data,
        }

        if self._sharded_bus:
            await self._sharded_bus.publish_finding(target_hash, finding_type, message)
            self._log.info("finding_published_sharded", finding_type=finding_type)
        else:
            channel = f"findings:{target_hash}:{finding_type}"
            await self.event_bus.publish(channel, message)
            self._log.info("finding_published", channel=channel, finding_type=finding_type)

    async def on_finding(self, target_hash: str, finding_type: str, content: dict[str, Any]):
        """Publish a finding to the swarm.
        
        Story 7.13: Uses ShardedEventBus for sharded publishing if available,
        otherwise falls back to non-sharded channel.

        Args:
            target_hash: Hash of the target (host/service).
            finding_type: Type of finding (e.g., 'sqli', 'open_port').
            content: The finding data.
        """
        payload = dict(content or {})
        if not (payload.get("target") or payload.get("domain") or payload.get("host")):
            payload["target"] = target_hash
        normalized = self._normalize_finding_message(finding_type, payload)
        if normalized is None:
            self._log.warning(
                "finding_dropped_missing_required_fields",
                finding_type=finding_type,
                target_hash=target_hash,
            )
            return

        await self._publish_normalized_finding(
            target_hash=target_hash,
            finding_type=finding_type,
            finding_data=normalized,
        )

    async def _publish_to_swarm(self, target_hash: str, finding_type: str, message: dict[str, Any]) -> None:
        """Publish finding through sharded bus or fallback to direct publish.

        Subclasses should call this instead of event_bus.publish() for findings
        so that ShardedEventBus routing is used when available.

        Args:
            target_hash: Hash of the target.
            finding_type: Type of finding (e.g., 'exploit', 'open_port').
            message: The finding message payload.
        """
        payload = dict(message or {})
        if not (payload.get("target") or payload.get("domain") or payload.get("host")):
            payload["target"] = target_hash
        normalized = self._normalize_finding_message(finding_type, payload)
        if normalized is None:
            self._log.warning(
                "finding_dropped_missing_required_fields",
                finding_type=finding_type,
                target_hash=target_hash,
            )
            return

        await self._publish_normalized_finding(
            target_hash=target_hash,
            finding_type=finding_type,
            finding_data=normalized,
        )

    def _normalize_finding_message(
        self,
        finding_type: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Normalize finding payload into a consistent schema."""
        raw = dict(payload or {})
        normalized = dict(raw)

        normalized["id"] = str(normalized.get("id") or normalized.get("finding_id") or str(uuid.uuid4()))
        normalized["type"] = str(
            normalized.get("type")
            or normalized.get("finding_type")
            or finding_type
        ).strip().lower()
        normalized["finding_type"] = normalized["type"]

        target = normalized.get("target") or normalized.get("domain") or normalized.get("host")
        if not target:
            return None
        normalized["target"] = str(target)

        severity = str(normalized.get("severity") or "info").strip().lower()
        if severity not in {"critical", "high", "medium", "low", "info"}:
            severity = "info"
        normalized["severity"] = severity

        assessment = assess_finding_payload(normalized)
        normalized["severity"] = assessment["severity"]
        normalized["outcome_status"] = assessment["outcome_status"]
        normalized["evidence_quality"] = assessment["evidence_quality"]
        normalized["validation_reason"] = assessment["validation_reason"]
        normalized["validation_confidence"] = assessment["validation_confidence"]

        if "tool" not in normalized and normalized.get("tool_name"):
            normalized["tool"] = normalized.get("tool_name")

        normalized["agent_id"] = str(normalized.get("agent_id") or self.agent_id)
        normalized["engagement_id"] = str(normalized.get("engagement_id") or self.engagement_id)
        normalized["timestamp"] = str(normalized.get("timestamp") or datetime.now(UTC).isoformat())
        return normalized

    async def _maybe_publish_objective_event(
        self,
        finding_type: str,
        finding_data: dict[str, Any],
    ) -> None:
        """Emit objective completion events from high-value findings."""
        if str(finding_data.get("outcome_status") or "").strip().lower() != "validated":
            return

        resolved_type = str(
            finding_data.get("objective_type")
            or finding_data.get("type")
            or finding_data.get("finding_type")
            or finding_type
        ).strip().lower()

        objective_type: str | None = None
        if resolved_type in {"credential", "credentials", "password", "hash", "kerberos", "domainadmin"}:
            objective_type = "credential_harvested"
        elif resolved_type in {"shell", "session", "reverse_shell", "meterpreter"}:
            objective_type = "shell_obtained"
        elif resolved_type in {"data_access", "data_accessed", "exfil", "exfiltration", "sensitive_data"}:
            objective_type = "data_accessed"

        if not objective_type:
            return

        payload = {
            "objective_type": objective_type,
            "target": finding_data.get("target"),
            "details": {
                "finding_id": finding_data.get("id"),
                "finding_type": finding_data.get("type") or finding_type,
                "severity": finding_data.get("severity"),
                "tool": finding_data.get("tool"),
                "agent_id": self.agent_id,
            },
            "timestamp": time.time(),
        }
        try:
            await self.event_bus.publish(f"objectives:{self.engagement_id}", payload)
        except Exception as e:
            self._log.debug("objective_event_publish_failed", error=str(e), objective_type=objective_type)

    def _safe_json_obj(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("{") and text.endswith("}"):
                try:
                    parsed = json.loads(text)
                except Exception:
                    return {}
                if isinstance(parsed, dict):
                    return parsed
        return {}

    def _build_swarm_finding_views(
        self,
        finding_data: dict[str, Any],
        *,
        lane: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        evidence_obj = self._safe_json_obj(finding_data.get("evidence"))
        execution = evidence_obj.get("execution") if isinstance(evidence_obj.get("execution"), dict) else {}

        finding_id = str(
            finding_data.get("id")
            or finding_data.get("finding_id")
            or str(uuid.uuid4())
        )
        command = str(
            finding_data.get("command")
            or evidence_obj.get("command")
            or execution.get("command")
            or ""
        )
        exit_code = execution.get("exit_code")
        error_type = execution.get("error_type")
        raw_signal = (
            evidence_obj.get("raw_evidence")
            or evidence_obj.get("summary")
            or execution.get("stderr")
            or execution.get("stdout")
            or finding_data.get("evidence")
            or ""
        )
        signal_text = str(raw_signal or "").replace("\n", " ").strip()

        digest = {
            "finding_id": finding_id,
            "type": str(finding_data.get("type") or "unknown"),
            "target": str(finding_data.get("target") or ""),
            "tool": str(finding_data.get("tool") or ""),
            "severity": str(finding_data.get("severity") or ""),
            "outcome_status": str(finding_data.get("outcome_status") or "attempted"),
            "evidence_quality": str(finding_data.get("evidence_quality") or ""),
            "validation_reason": str(finding_data.get("validation_reason") or ""),
            "command": command[:220],
            "exit_code": exit_code,
            "error_type": error_type,
            "lane": lane,
            "evidence": signal_text[: self._swarm_signal_chars],
        }

        details = {
            **digest,
            "command_full": command[:800],
            "evidence_expanded": signal_text[: self._swarm_expand_signal_chars],
            "stderr_preview": str(execution.get("stderr") or "")[:600],
            "stdout_preview": str(execution.get("stdout") or "")[:600],
            "timestamp": str(finding_data.get("timestamp") or datetime.now(UTC).isoformat()),
        }
        return digest, details

    def _store_swarm_finding(
        self,
        finding_data: dict[str, Any],
        *,
        lane: str,
    ) -> None:
        digest, details = self._build_swarm_finding_views(finding_data, lane=lane)
        self._swarm_findings.append(digest)
        finding_id = str(digest.get("finding_id") or "")
        if finding_id:
            self._swarm_finding_details[finding_id] = details
            if len(self._swarm_finding_details) > 2000:
                for old_key in list(self._swarm_finding_details.keys())[:600]:
                    self._swarm_finding_details.pop(old_key, None)

    def _rank_swarm_finding_for_prompt(
        self,
        finding: dict[str, Any],
        *,
        position: int,
        target_hint: str,
        objective: str,
    ) -> float:
        severity_rank = {
            "critical": 5.0,
            "high": 4.0,
            "medium": 3.0,
            "low": 2.0,
            "info": 1.0,
        }
        score = float(position) / 1000.0
        score += severity_rank.get(str(finding.get("severity") or "").lower(), 0.0)

        status = str(finding.get("outcome_status") or "").lower()
        if status == "validated":
            score += 4.0
        elif status == "attempted":
            score += 2.0
        else:
            score += 1.0

        lane = str(finding.get("lane") or "primary")
        if lane == "telemetry":
            score -= 0.8

        finding_target = str(finding.get("target") or "").lower()
        if target_hint and finding_target and (
            target_hint in finding_target or finding_target in target_hint
        ):
            score += 4.0

        finding_type = str(finding.get("type") or "").lower()
        if finding_type and objective and finding_type in objective:
            score += 2.0
        return score

    def _select_swarm_findings_for_prompt(
        self,
        context: ToolSelectionContext,
    ) -> list[dict[str, Any]]:
        if not self._swarm_findings:
            return []

        target_hint = self._selection_target_hint(context.target_info).strip().lower()
        objective = str(context.objective or "").strip().lower()
        scored: list[tuple[float, dict[str, Any]]] = []
        for idx, finding in enumerate(list(self._swarm_findings)):
            if not isinstance(finding, dict):
                continue
            score = self._rank_swarm_finding_for_prompt(
                finding,
                position=idx + 1,
                target_hint=target_hint,
                objective=objective,
            )
            scored.append((score, finding))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for _, finding in scored:
            finding_id = str(finding.get("finding_id") or "")
            if finding_id and finding_id in seen_ids:
                continue
            if finding_id:
                seen_ids.add(finding_id)
            selected.append(finding)
            if len(selected) >= self._swarm_prompt_findings_limit:
                break
        return selected

    def _format_swarm_finding_for_prompt(
        self,
        finding: dict[str, Any],
        *,
        expanded: bool,
    ) -> str:
        finding_id = str(finding.get("finding_id") or "")
        details = self._swarm_finding_details.get(finding_id, {})
        signal = (
            str(details.get("evidence_expanded") or "")
            if expanded
            else str(finding.get("evidence") or "")
        )
        if not signal:
            signal = str(details.get("stderr_preview") or details.get("stdout_preview") or "")
        signal = signal.replace("\n", " ").strip()
        if expanded:
            signal = signal[: self._swarm_expand_signal_chars]
        else:
            signal = signal[: self._swarm_signal_chars]

        command = str(
            details.get("command_full")
            or finding.get("command")
            or ""
        ).replace("\n", " ").strip()[:220]
        exit_code = details.get("exit_code", finding.get("exit_code"))
        error_type = str(details.get("error_type", finding.get("error_type")) or "").strip()

        parts = [
            f"[{finding.get('severity', '')}/{finding.get('outcome_status', '')}]",
            f"{finding.get('type', 'unknown')}",
            f"target={finding.get('target', '')}",
            f"tool={finding.get('tool', '')}",
        ]
        if command:
            parts.append(f"cmd={command}")
        if exit_code is not None:
            parts.append(f"exit={exit_code}")
        if error_type:
            parts.append(f"error={error_type}")
        if finding.get("lane") == "telemetry":
            parts.append("lane=telemetry")
        if signal:
            parts.append(f"signal={signal}")
        return " | ".join(str(part) for part in parts if part)

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
        if channel.startswith("findings:") or channel == "swarm:findings_telemetry":
            finding_data = data.get("data", data)
            if not isinstance(finding_data, dict):
                finding_data = {}
            source_agent = str(
                data.get("agent_id")
                or finding_data.get("agent_id")
                or ""
            )
            if source_agent and source_agent != self.agent_id and finding_data:
                lane = "telemetry" if channel == "swarm:findings_telemetry" else "primary"
                self._store_swarm_finding(finding_data, lane=lane)
                self._log.debug(
                    "swarm_finding_received",
                    source=source_agent,
                    finding_type=finding_data.get("type"),
                    lane=lane,
                    outcome_status=finding_data.get("outcome_status"),
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
        elif channel == "swarm:findings_telemetry":
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

    def hydrate_context(
        self,
        findings: list[dict],
        strategy: dict | None = None,
        runtime_state: dict[str, Any] | None = None,
    ) -> None:
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
        runtime_findings_count = 0
        runtime_finding_detail_count = 0
        runtime_results_count = 0
        runtime_fp_count = 0
        runtime_retry_state_count = 0
        if runtime_state:
            runtime_findings = runtime_state.get("swarm_findings") or []
            for item in runtime_findings:
                if isinstance(item, dict):
                    self._swarm_findings.append(item)
                    runtime_findings_count += 1

            runtime_finding_details = runtime_state.get("swarm_finding_details") or {}
            if isinstance(runtime_finding_details, dict):
                for finding_id, details in runtime_finding_details.items():
                    if not isinstance(finding_id, str) or not finding_id or not isinstance(details, dict):
                        continue
                    self._swarm_finding_details[finding_id] = dict(details)
                    runtime_finding_detail_count += 1

            previous_results = runtime_state.get("previous_results") or []
            for item in previous_results:
                if isinstance(item, dict):
                    self._recent_tool_results.append(item)
                    runtime_results_count += 1

            command_fingerprints = runtime_state.get("command_fingerprints") or []
            for item in command_fingerprints:
                if isinstance(item, str) and item:
                    self._command_fingerprints.append(item)
                    runtime_fp_count += 1
            self._refresh_command_fingerprint_set()

            command_retry_state = runtime_state.get("command_retry_state") or {}
            if isinstance(command_retry_state, dict):
                for fingerprint, state in command_retry_state.items():
                    if not isinstance(fingerprint, str) or not fingerprint or not isinstance(state, dict):
                        continue
                    try:
                        attempts = max(1, int(state.get("attempts") or 1))
                    except (TypeError, ValueError):
                        attempts = 1
                    try:
                        last_attempt_ts = float(state.get("last_attempt_ts") or 0.0)
                    except (TypeError, ValueError):
                        last_attempt_ts = 0.0
                    self._command_retry_state[fingerprint] = {
                        "status": str(state.get("status") or "").strip().lower() or "failed",
                        "attempts": attempts,
                        "last_attempt_ts": last_attempt_ts,
                        "context_token": str(state.get("context_token") or ""),
                    }
                    runtime_retry_state_count += 1

            decision_context = runtime_state.get("decision_context") or []
            if isinstance(decision_context, list):
                for signal_id in decision_context:
                    if isinstance(signal_id, str) and signal_id:
                        self._decision_context.append(signal_id)
                if len(self._decision_context) > 400:
                    self._decision_context = self._decision_context[-400:]
        self._log.info(
            "context_hydrated",
            findings_count=len(findings),
            has_strategy=strategy is not None,
            runtime_findings_count=runtime_findings_count,
            runtime_finding_detail_count=runtime_finding_detail_count,
            runtime_results_count=runtime_results_count,
            runtime_fingerprint_count=runtime_fp_count,
            runtime_retry_state_count=runtime_retry_state_count,
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
        self._warn_unknown_techniques_once(
            strategy.id,
            strategy.recommended_techniques,
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
        self._warn_unknown_techniques_once(
            strategy.id,
            strategy.recommended_techniques,
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

    def _warn_unknown_techniques_once(
        self,
        strategy_id: str,
        recommended_techniques: list[str] | None,
    ) -> None:
        """Log unknown ATT&CK techniques once per strategy payload."""
        if not recommended_techniques:
            return

        unknown_techniques: list[str] = []
        for technique_value in recommended_techniques:
            technique = str(technique_value).strip()
            if not technique:
                continue
            if technique in ATTCK_TECHNIQUE_TOOL_MAP:
                continue
            base_technique = technique.split(".")[0]
            if base_technique in ATTCK_TECHNIQUE_TOOL_MAP:
                continue
            unknown_techniques.append(technique)

        if not unknown_techniques:
            return

        deduped_unknown = tuple(sorted(set(unknown_techniques)))
        cache_key = (strategy_id, deduped_unknown)
        if cache_key in StigmergicAgent._unknown_technique_warned:
            return

        StigmergicAgent._unknown_technique_warned.add(cache_key)
        self._log.warning(
            "unknown_attck_techniques",
            techniques=list(deduped_unknown),
            strategy_id=strategy_id,
        )

    def _get_scope_targets(self) -> list[str]:
        """Load in-scope targets from the engagement scope file.

        Reads the scope.yaml generated by the Orchestrator and returns
        the allowed_targets list so the LLM prompt knows which hosts
        are valid. This prevents agents from hallucinating out-of-scope
        targets like github.com or random RFC1918 ranges.

        Returns:
            List of in-scope target strings (IPs, CIDRs, hostnames),
            or empty list if scope file is unavailable.
        """
        try:
            settings = get_settings()
            scope_path = getattr(settings.engagement, "scope_path", "")
            if not scope_path:
                return []
            from pathlib import Path
            import yaml
            p = Path(scope_path)
            if not p.exists():
                return []
            with p.open() as f:
                data = yaml.safe_load(f) or {}
            scope = data.get("scope", data)
            targets = scope.get("allowed_targets", [])
            return targets[:50]  # Cap for token budget
        except Exception:
            return []

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
            else:
                # Try base technique (e.g. T1059.001 -> T1059)
                base_tech = technique.split('.')[0]
                if base_tech in ATTCK_TECHNIQUE_TOOL_MAP:
                    categories.update(ATTCK_TECHNIQUE_TOOL_MAP[base_tech])
        
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
        await self._cleanup_runtime()

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
        """Cleanup resources and release Redis connections."""
        self._status = "shutdown"
        await self._cleanup_runtime()
        self._log.info("agent_shutdown")

    async def _cleanup_runtime(self) -> None:
        """Cancel monitors and subscriptions for this agent instance."""
        if self._throttle_monitor_task:
            self._throttle_monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._throttle_monitor_task
            self._throttle_monitor_task = None

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._heartbeat_task
            self._heartbeat_task = None

        if self._subscriptions:
            for sub in self._subscriptions:
                with contextlib.suppress(Exception):
                    cancel_fn = getattr(sub, "cancel", None)
                    unsubscribe_fn = getattr(sub, "unsubscribe", None)
                    if callable(cancel_fn):
                        await cancel_fn()
                    elif callable(unsubscribe_fn):
                        await unsubscribe_fn()
            self._subscriptions.clear()

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
        retry_state_items = sorted(
            self._command_retry_state.items(),
            key=lambda item: float(item[1].get("last_attempt_ts") or 0.0),
        )[-500:]
        swarm_detail_items = sorted(
            self._swarm_finding_details.items(),
            key=lambda item: str(item[1].get("timestamp") or ""),
        )[-300:]
        
        state = AgentState(
            agent_id=self.agent_id,
            agent_type=self.role.value,
            state={
                "specialty": self.specialty,
                "status": self._status,
                "tool_help_cache": self._tool_help_cache,
                "current_task_id": getattr(self, "_current_task_id", None),
                "recent_tool_results": list(self._recent_tool_results)[-60:],
                "command_fingerprints": list(self._command_fingerprints)[-300:],
                "swarm_findings": list(self._swarm_findings)[-self._swarm_findings_maxlen:],
                "swarm_finding_details": {
                    key: value for key, value in swarm_detail_items if isinstance(value, dict)
                },
                "command_retry_state": {
                    key: value for key, value in retry_state_items if isinstance(value, dict)
                },
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
        recent_tool_results = agent_state.state.get("recent_tool_results", [])
        if isinstance(recent_tool_results, list):
            self._recent_tool_results = deque(
                [item for item in recent_tool_results if isinstance(item, dict)],
                maxlen=80,
            )
        else:
            self._recent_tool_results = deque(maxlen=80)
        command_fingerprints = agent_state.state.get("command_fingerprints", [])
        if isinstance(command_fingerprints, list):
            self._command_fingerprints = deque(
                [item for item in command_fingerprints if isinstance(item, str) and item],
                maxlen=400,
            )
        else:
            self._command_fingerprints = deque(maxlen=400)
        self._refresh_command_fingerprint_set()
        swarm_findings = agent_state.state.get("swarm_findings", [])
        if isinstance(swarm_findings, list):
            self._swarm_findings = deque(
                [item for item in swarm_findings if isinstance(item, dict)],
                maxlen=self._swarm_findings_maxlen,
            )
        else:
            self._swarm_findings = deque(maxlen=self._swarm_findings_maxlen)
        swarm_finding_details = agent_state.state.get("swarm_finding_details", {})
        self._swarm_finding_details = {}
        if isinstance(swarm_finding_details, dict):
            for finding_id, details in swarm_finding_details.items():
                if isinstance(finding_id, str) and finding_id and isinstance(details, dict):
                    self._swarm_finding_details[finding_id] = dict(details)
        command_retry_state = agent_state.state.get("command_retry_state", {})
        self._command_retry_state = {}
        if isinstance(command_retry_state, dict):
            for fingerprint, state in command_retry_state.items():
                if not isinstance(fingerprint, str) or not fingerprint or not isinstance(state, dict):
                    continue
                try:
                    attempts = max(1, int(state.get("attempts") or 1))
                except (TypeError, ValueError):
                    attempts = 1
                try:
                    last_attempt_ts = float(state.get("last_attempt_ts") or 0.0)
                except (TypeError, ValueError):
                    last_attempt_ts = 0.0
                self._command_retry_state[fingerprint] = {
                    "status": str(state.get("status") or "").strip().lower() or "failed",
                    "attempts": attempts,
                    "last_attempt_ts": last_attempt_ts,
                    "context_token": str(state.get("context_token") or ""),
                }
        self._last_action_id = agent_state.last_action_id
        if agent_state.decision_context:
            self._decision_context = agent_state.decision_context.split(",")
        else:
            self._decision_context = []
        self._log.info(
            "agent_restored_from_checkpoint",
            last_action=self._last_action_id,
            restored_results=len(self._recent_tool_results),
            restored_fingerprints=len(self._command_fingerprints),
            restored_swarm_findings=len(self._swarm_findings),
            restored_swarm_finding_details=len(self._swarm_finding_details),
            restored_retry_state=len(self._command_retry_state),
        )

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
        2. Read throttle mode + threshold from settings.
        3. `queue_depth` mode uses queue pressure thresholds directly.
        4. `legacy_max_agents` mode preserves historic max_agents percentage behavior.
        5. Return True if queue depth exceeds computed threshold.

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

            mode = str(getattr(throttle_config, "mode", "queue_depth")).strip().lower()
            threshold = throttle_config.threshold

            if mode == "legacy_max_agents":
                # Legacy behavior retained for backwards compatibility.
                if threshold < 1.0:
                    max_agents = settings.engagement.max_agents
                    target_depth = max(1, int(threshold * max_agents))
                else:
                    target_depth = max(1, int(threshold))
            else:
                # Queue-depth mode: threshold is interpreted against queue pressure.
                if threshold < 1.0:
                    queue_capacity_hint = int(getattr(throttle_config, "queue_capacity_hint", 20))
                    target_depth = max(1, int(threshold * max(1, queue_capacity_hint)))
                else:
                    target_depth = max(1, int(threshold))

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
        selection_history = context.previous_results or self.get_recent_tool_results(limit=30)
        capped_results = selection_history[-15:] if selection_history else []
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
            swarm_items = self._select_swarm_findings_for_prompt(context)
            expanded_count = min(self._swarm_auto_expand_count, len(swarm_items))
            swarm_summary = "\n".join(
                f"- {self._format_swarm_finding_for_prompt(item, expanded=index < expanded_count)}"
                for index, item in enumerate(swarm_items)
            )
            base_prompt += f"\n\n**Swarm Findings (from other agents):**\n{swarm_summary}"
            base_prompt += (
                "\nAvoid duplicating work already done."
                " Treat lane=telemetry items as anti-repeat and pivot signals."
                " Focus on targets/services with validated evidence and unresolved pivots."
            )
            self._log.info(
                "swarm_context_injected",
                swarm_finding_count=len(swarm_items),
                expanded_finding_count=expanded_count,
            )

        # Story 7.17: Include strategy context if active
        strategy_context = self._get_strategy_context()
        if strategy_context:
            base_prompt += f"\n\n**Director Strategy:**\n{strategy_context}"

        # Scope-aware target list — prevent LLM from hallucinating out-of-scope targets
        scope_targets = self._get_scope_targets()
        if scope_targets:
            base_prompt += f"\n\n**IN-SCOPE TARGETS ONLY:** {', '.join(scope_targets)}"
            base_prompt += "\nDo NOT target any hosts, IPs, or networks not listed above."

        base_prompt += """

COMMAND RULES:
- Generate a single tool command. You may pipe output through filters (e.g. | grep, | sort, | head).
- Do NOT use semicolons (;) to chain unrelated commands.
- Do NOT use $(), backticks, or variable substitution.
- Do NOT use process substitution (<(...), >(...)).
- Do NOT use curl/wget to public internet hosts unless explicitly authorized.
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

        # Publish "thinking" status for TUI
        await self._publish_status("thinking")
        selection: ToolSelection | None = None
        attempt_context = context
        max_attempts = 3

        for attempt in range(max_attempts):
            prompt = self._build_tool_selection_prompt(attempt_context)

            if self._llm_gateway:
                from cyberred.llm.provider import LLMRequest

                request = LLMRequest(
                    prompt=prompt,
                    model="default",
                    system_prompt=self.system_prompt,
                    max_tokens=5000,
                )
                response = await self._llm_gateway.agent_complete(request)
                finish_reason = getattr(response, "finish_reason", None)
                if isinstance(finish_reason, str) and finish_reason.startswith("error:"):
                    raise ToolSelectionError(
                        agent_id=self.agent_id,
                        reason=f"LLM call failed: {finish_reason}",
                    )
                response_text = response.content
            else:
                raise ToolSelectionError(agent_id=self.agent_id, reason="No LLM gateway configured")

            candidate = self._parse_tool_selection(response_text)
            try:
                candidate.command = self._validate_command(
                    candidate.command,
                    candidate.tool_name,
                )
            except ValueError as e:
                raise ToolSelectionError(
                    agent_id=self.agent_id,
                    reason=f"Invalid generated command: {e}",
                ) from e

            target_hint = self._selection_target_hint(attempt_context.target_info)
            context_token = self._build_context_token(
                attempt_context,
                phase=attempt_context.phase,
                target=target_hint,
            )
            if not self._is_recent_command(
                candidate.tool_name,
                candidate.command,
                phase=attempt_context.phase,
                target=target_hint,
                context_token=context_token,
            ):
                selection = candidate
                self._selection_context_token = context_token
                break

            self._log.warning(
                "duplicate_tool_selection_rejected",
                tool=candidate.tool_name,
                attempt=attempt + 1,
                phase=attempt_context.phase,
                target=target_hint,
            )
            if attempt >= max_attempts - 1:
                raise ToolSelectionError(
                    agent_id=self.agent_id,
                    reason="LLM repeatedly selected duplicate command",
                )
            retry_constraints = list(attempt_context.constraints)
            retry_constraints.append("choose a materially different command than prior runs")
            attempt_context = ToolSelectionContext(
                objective=attempt_context.objective,
                target_info=attempt_context.target_info,
                available_tools=attempt_context.available_tools,
                phase=attempt_context.phase,
                constraints=retry_constraints,
                previous_results=attempt_context.previous_results,
            )

        if selection is None:
            raise ToolSelectionError(
                agent_id=self.agent_id,
                reason="LLM did not return a usable tool selection",
            )

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
        import os
        import re
        import shlex

        command = command.strip()
        if not command:
            raise ValueError("Generated command cannot be empty")

        try:
            tokens = shlex.split(command)
        except ValueError as e:
            raise ValueError(f"Generated command is not shell-parseable: {e}") from e

        def _normalize_name(value: str) -> str:
            normalized = os.path.basename((value or "").strip().lower())
            if normalized.endswith(".py"):
                normalized = normalized[:-3]
            normalized = normalized.replace("impacket-", "")
            return re.sub(r"[^a-z0-9]+", "", normalized)

        def _resolve_executable(parts: list[str]) -> str:
            index = 0
            while index < len(parts):
                token = parts[index]
                executable = os.path.basename(token)
                if executable in {"sudo", "nohup", "setsid", "command"}:
                    index += 1
                    continue
                if executable == "env":
                    index += 1
                    while (
                        index < len(parts)
                        and "=" in parts[index]
                        and not parts[index].startswith("-")
                    ):
                        index += 1
                    continue
                if executable == "timeout":
                    index += 1
                    while index < len(parts) and parts[index].startswith("-"):
                        if parts[index] in {"-k", "--kill-after", "-s", "--signal"} and index + 1 < len(parts):
                            index += 2
                        else:
                            index += 1
                    if index < len(parts):
                        index += 1
                    continue
                if executable in {"sh", "bash"} and index + 2 < len(parts) and parts[index + 1] in {"-c", "-lc"}:
                    nested = parts[index + 2]
                    try:
                        nested_tokens = shlex.split(nested)
                    except ValueError:
                        nested_tokens = nested.split()
                    if nested_tokens:
                        return os.path.basename(nested_tokens[0])
                    return ""
                return executable
            return ""

        expected_exec = os.path.basename((tool or "").strip())
        actual_exec = _resolve_executable(tokens)
        expected_norm = _normalize_name(expected_exec)
        actual_norm = _normalize_name(actual_exec)

        valid = actual_norm == expected_norm
        if not valid and expected_norm == "sleuthkit":
            valid = actual_norm in {
                "fls", "mmls", "icat", "tskrecover", "blkls", "ffind", "ifind",
                "fsstat", "istat", "imgstat", "sigfind", "sorter", "jls", "jcat",
                "mmcat", "mmstat", "hfind",
            }
        if (
            not valid
            and expected_norm
            and actual_norm
            and min(len(expected_norm), len(actual_norm)) >= 5
        ):
            valid = actual_norm in expected_norm or expected_norm in actual_norm

        if not valid:
            raise ValueError(
                f"Generated command executable '{actual_exec or '<unknown>'}' "
                f"is not compatible with tool '{tool}'"
            )

        # Guardrail: nmap expects time units for --max-rtt-timeout.
        # Auto-fix bare integer values (e.g. 2000 -> 2000ms) which otherwise
        # imply seconds and cause effectively stuck scans.
        if tool == "nmap":
            command = re.sub(
                r"(--max-rtt-timeout\s+)(\d+)(?=\s|$)",
                r"\1\2ms",
                command,
            )

        # Guardrail: reject common placeholder host files that do not exist in
        # worker containers and lead to immediate no-op errors.
        if tool == "masscan":
            if re.search(r"(?:^|\s)-iL\s+(targets\.txt|hosts\.txt|ips\.txt)(?:\s|$)", command):
                raise ValueError(
                    "masscan command references placeholder input file; use explicit targets instead"
                )

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
                max_tokens=5000,
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
