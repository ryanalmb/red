"""Base agent class for Cyber-Red stigmergic coordination.

This module implements the StigmergicAgent base class which extends the
swarms.Agent to add P2P coordination capabilities via Redis Pub/Sub
and LLM-driven tool selection (Story 7.1.v2).
"""

import asyncio
import contextlib
import json
import time
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

    async def spawn(self):
        """Initialize async components and subscriptions."""
        await self._setup_subscriptions()
        await self._start_throttle_monitor()
        await self._start_heartbeat()  # Story 7.12
        self._status = "active"
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
            # Fallback to non-sharded (backward compatibility)
            await self.event_bus.subscribe("findings:*", self._handle_message)
        
        # Subscribe to strategy updates for this engagement
        await self.event_bus.subscribe(f"strategies:{self.engagement_id}", self._handle_message)
        # Subscribe to kill switch
        await self.event_bus.subscribe("control:kill", self._handle_message)

    async def _handle_message(self, channel: str, message: str):
        """Internal callback for EventBus subscriptions.

        Deserializes message and dispatches to on_signal.

        Args:
            channel: The channel the message was received on.
            message: The raw message string (may be JSON or plain text).
        """
        # Guard against None/empty messages
        if message is None:
            self._log.warning("null_message_received", channel=channel)
            return

        try:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                # If not JSON, wrap in dict for consistency with on_signal(channel, data: Dict)
                data = {"raw_content": message}

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

    async def on_signal(self, channel: str, data: dict[str, Any]):
        """Handle incoming stigmergic signal.

        Override this in subclasses to react to specific signals.

        Args:
            channel: The channel the signal was received on.
            data: The signal payload.
        """
        self._log.debug("signal_received", channel=channel)
        
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
        elif "phase" in channel:
            return "phase"
        else:
            return "status"

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
        previous_results_str = json.dumps(context.previous_results) if context.previous_results else "None"

        return f"""Select the best tool for this objective and generate a complete command.

**Phase:** {context.phase}
**Target Info:** {json.dumps(context.target_info)}
**Objective:** {context.objective}
**Constraints:** {", ".join(context.constraints) or "None"}
**Previous Results:** {previous_results_str}

**Available Tools:** {tools_list}

Respond with JSON only:
{{"tool_name": "...", "command": "...", "rationale": "...", "expected_output_type": "json|xml|text", "confidence": 0.0-1.0, "priority": 1-10, "alternatives": []}}"""

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
            if response.startswith("```"):
                # Handle markdown code blocks
                lines = response.split("\n")
                json_lines = [line for line in lines if not line.startswith("```")]
                response = "\n".join(json_lines)

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

        # Query LLM
        if self._llm_gateway:
            from cyberred.llm.provider import LLMRequest

            request = LLMRequest(
                prompt=prompt,
                model="default",  # Router will select appropriate model
                system_prompt=self.system_prompt,
                max_tokens=500,
            )
            response = await self._llm_gateway.agent_complete(request)
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
