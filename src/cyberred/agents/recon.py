"""ReconAgent - LLM-driven reconnaissance agent (Story 7.3-v2).

Thin subclass of StigmergicAgent that sets role=AgentRole.RECON and uses
inherited LLM tool selection from the full 1,556+ Kali tool manifest.

Story 7.3-v2 Refactor:
    - Removed hardcoded tool_sequence and _generate_*_command() methods
    - Uses inherited select_tool() and generate_command() from StigmergicAgent
    - Constructor sets role=AgentRole.RECON and accepts specialty parameter
    - execute_recon() takes target as parameter and uses LLM loop
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from cyberred.agents.base import StigmergicAgent
from cyberred.agents.roles import AgentRole
from cyberred.core.config import get_settings
from cyberred.core.events import EventBus
from cyberred.core.models import AgentAction, Finding, ToolSelectionContext
from cyberred.tools.kali_executor import kali_execute
from cyberred.tools.output import OutputProcessor
from cyberred.tools.parsers.nmap import nmap_parser
from cyberred.tools.scope import ScopeConfig, ScopeValidator

if TYPE_CHECKING:
    from cyberred.llm.gateway import LLMGateway
    from cyberred.tools.manifest import ManifestLoader

log = structlog.get_logger().bind(component="recon_agent")


class ReconAgent(StigmergicAgent):
    """LLM-driven reconnaissance agent - thin subclass setting role=RECON.

    Attributes:
        specialty: Reconnaissance specialty (network, osint, dns, subdomain).
        current_strategy: Scan intensity ('standard', 'stealth', 'aggressive').
    """

    #: Default max iterations for recon loop
    DEFAULT_MAX_ITERATIONS: int = 20
    #: Default findings threshold to consider phase complete
    DEFAULT_PHASE_COMPLETE_THRESHOLD: int = 50

    def __init__(
        self,
        agent_id: str,
        engagement_id: str,
        event_bus: EventBus,
        specialty: str = "network",
        llm_gateway: "LLMGateway | None" = None,
        manifest_loader: "ManifestLoader | None" = None,
        max_iterations: int | None = None,
        phase_complete_threshold: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize ReconAgent.

        Args:
            agent_id: Unique agent identifier.
            engagement_id: Engagement identifier.
            event_bus: EventBus instance for stigmergic communication.
            specialty: Reconnaissance specialty (default: "network").
                       Valid: network, osint, dns, subdomain.
            llm_gateway: Optional LLMGateway for tool selection.
            manifest_loader: Optional ManifestLoader for tool lookup.
            max_iterations: Max LLM selection iterations (default: 20).
            phase_complete_threshold: Findings count to end phase (default: 50).
            **kwargs: Additional kwargs for StigmergicAgent.
        """
        super().__init__(
            agent_name="ReconAgent",
            agent_id=agent_id,
            engagement_id=engagement_id,
            event_bus=event_bus,
            role=AgentRole.RECON,
            specialty=specialty,
            llm_gateway=llm_gateway,
            manifest_loader=manifest_loader,
            **kwargs,
        )
        self._log = log.bind(agent_id=agent_id, engagement_id=engagement_id)
        self.output_processor = OutputProcessor()
        self.output_processor.register_parser("nmap", nmap_parser)

        # Configurable limits
        self.max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
        self.phase_complete_threshold = phase_complete_threshold or self.DEFAULT_PHASE_COMPLETE_THRESHOLD

        # Stigmergic coordination state
        self.current_strategy = "standard"
        self._finding_buffer: list[dict[str, Any]] = []
        self._stop_event = asyncio.Event()

    async def execute_recon(self, target: str) -> tuple[list[Finding], list[AgentAction]]:
        """Execute LLM-driven reconnaissance against target.

        Args:
            target: Target IP, hostname, CIDR, or domain to scan.

        Returns:
            Tuple of (findings, actions) discovered during reconnaissance.
        """
        self._validate_target_scope(target)

        all_findings: list[Finding] = []
        all_actions: list[AgentAction] = []

        context = ToolSelectionContext(
            objective="Discover hosts, services, and attack surface",
            target_info={"target": target, "phase": "recon", "strategy": self.current_strategy},
            available_tools=[],
            phase="reconnaissance",
            constraints=self._get_constraints(),
            previous_results=[],
        )

        for iteration in range(self.max_iterations):
            if self._stop_event.is_set():
                self._log.info("recon_stopped_gracefully", iteration=iteration)
                break

            if await self._phase_complete(context):
                break

            decision_context = self.get_decision_context().copy() or [f"initial_spawn:{self.agent_id}"]
            action_id = str(uuid.uuid4())
            result_finding_id: str | None = None
            tool_name = "unknown"

            try:
                selection = await self.select_tool(context)
                tool_name = selection.tool_name

                self._log.info("executing_tool", tool=tool_name, command=selection.command[:80], confidence=selection.confidence)
                result = await kali_execute(selection.command)

                if not result.success:
                    self._log.warning("tool_execution_failed", tool=tool_name, error=result.stderr[:200] if result.stderr else "")

                processed = self.output_processor.process(
                    stdout=result.stdout,
                    stderr=result.stderr,
                    tool=tool_name,
                    exit_code=result.exit_code,
                    agent_id=str(self.agent_id),
                    target=target,
                    error_type=getattr(result, "error_type", None),
                )

                for finding in processed.findings:
                    await self.on_finding(target, finding.type, finding.model_dump())
                    all_findings.append(finding)
                    if result_finding_id is None:
                        result_finding_id = finding.id

                context = ToolSelectionContext(
                    objective=context.objective,
                    target_info=context.target_info,
                    available_tools=[],
                    phase=context.phase,
                    constraints=context.constraints,
                    previous_results=[f.model_dump() for f in all_findings],
                )

            except Exception as e:
                self._log.error("recon_iteration_error", error=str(e), iteration=iteration)

            action = AgentAction(
                id=action_id,
                agent_id=str(self.agent_id),
                action_type=f"recon:{tool_name}",
                target=target,
                timestamp=datetime.now(UTC).isoformat(),
                decision_context=decision_context,
                result_finding_id=result_finding_id,
            )
            all_actions.append(action)

        return all_findings, all_actions

    async def _phase_complete(self, context: ToolSelectionContext) -> bool:
        """Check if reconnaissance phase is complete."""
        return len(context.previous_results) >= self.phase_complete_threshold

    def _get_constraints(self) -> list[str]:
        """Get operational constraints for tool selection based on strategy."""
        if self.current_strategy == "stealth":
            return ["low_rate", "avoid_detection", "passive_preferred"]
        elif self.current_strategy == "aggressive":
            return ["high_throughput", "comprehensive"]
        return []

    def _validate_target_scope(self, target: str) -> None:
        """Validate target against engagement scope."""
        validator = self._get_scope_validator()
        validator.validate(target=target)

    def _get_scope_validator(self) -> ScopeValidator:
        """Load scope validator from configured file."""
        settings = get_settings()
        path = settings.engagement.scope_path
        if path:
            try:
                return ScopeValidator.from_file(path)
            except Exception as e:
                self._log.warning("failed_to_load_scope_file", path=path, error=str(e))
        return ScopeValidator(ScopeConfig())

    async def stop(self) -> None:
        """Gracefully stop the agent."""
        self._stop_event.set()
        self._log.info("agent_stopping")

    async def on_finding(self, target_hash: str, finding_type: str, content: dict[str, Any]) -> None:
        """Publish finding to event bus with degraded mode buffering."""
        channel = f"findings:{target_hash}:{finding_type}"
        message = {"agent_id": str(self.agent_id), "engagement_id": self.engagement_id, "data": content}

        if self._finding_buffer:
            await self._flush_buffer()

        try:
            await self.event_bus.publish(channel, message)
        except Exception as e:
            self._log.warning("publish_failed_buffering", error=str(e), channel=channel)
            self._finding_buffer.append({"channel": channel, "message": message})

    async def _flush_buffer(self) -> None:
        """Attempt to flush buffered findings."""
        remaining = []
        for item in self._finding_buffer:
            try:
                await self.event_bus.publish(item["channel"], item["message"])
            except Exception:
                remaining.append(item)

        flushed_count = len(self._finding_buffer) - len(remaining)
        if flushed_count > 0:
            self._log.info("buffer_flushed", count=flushed_count)
        self._finding_buffer = remaining

    async def on_signal(self, channel: str, data: dict[str, Any]) -> None:
        """Handle incoming stigmergic signals, updating strategy if applicable."""
        await super().on_signal(channel, data)
        if "strategies" in channel:
            strategy = data.get("strategy")
            if strategy in ("stealth", "standard", "aggressive"):
                self._log.info("strategy_updated", old=self.current_strategy, new=strategy)
                self.current_strategy = strategy
