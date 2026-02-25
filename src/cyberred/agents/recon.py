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
import hashlib
import json
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from cyberred.agents.base import StigmergicAgent
from cyberred.agents.roles import AgentRole
from cyberred.core.config import get_settings
from cyberred.core.exceptions import ScopeViolationError
from cyberred.core.events import EventBus
from cyberred.core.finding_policy import assess_finding_payload
from cyberred.core.models import AgentAction, Finding, ToolSelectionContext
from cyberred.tools.kali_executor import kali_execute
from cyberred.tools.output import OutputProcessor
from cyberred.tools.parsers.nmap import nmap_parser
from cyberred.tools.scope import ScopeConfig, ScopeValidator

if TYPE_CHECKING:
    from cyberred.agents.rag_escalator import AgentRAGEscalator
    from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
    from cyberred.intelligence.base import IntelResult
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
    DEFAULT_MAX_ITERATIONS: int = 2
    #: Default findings threshold to consider phase complete
    DEFAULT_PHASE_COMPLETE_THRESHOLD: int = 50
    #: Intelligence query timeout
    INTELLIGENCE_TIMEOUT: float = 5.0

    def __init__(
        self,
        agent_id: str,
        engagement_id: str,
        event_bus: EventBus,
        specialty: str = "network",
        llm_gateway: "LLMGateway | None" = None,
        manifest_loader: "ManifestLoader | None" = None,
        intel_aggregator: "CachedIntelligenceAggregator | None" = None,
        rag_escalator: "AgentRAGEscalator | None" = None,
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
            intel_aggregator: Optional intelligence aggregator for service intel.
            rag_escalator: Optional RAG escalator for methodology retrieval on failure.
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
        self._intel_aggregator = intel_aggregator
        self._rag_escalator = rag_escalator
        self._failure_counts: dict[str, int] = {}
        self._current_target: str = ""
        self._current_service: str = ""
        self.output_processor = OutputProcessor()
        self.output_processor.register_parser("nmap", nmap_parser)

        # Configurable limits
        self.max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
        self.phase_complete_threshold = phase_complete_threshold or self.DEFAULT_PHASE_COMPLETE_THRESHOLD

        # Stigmergic coordination state
        self.current_strategy = "standard"
        self._finding_buffer: list[dict[str, Any]] = []
        self._stop_event = asyncio.Event()

    async def execute_recon(self, target: str, target_info: dict[str, Any] | None = None) -> tuple[list[Finding], list[AgentAction]]:
        """Execute LLM-driven reconnaissance against target.

        Args:
            target: Target IP, hostname, CIDR, or domain to scan.
            target_info: Optional target info with service/version for intelligence lookup.

        Returns:
            Tuple of (findings, actions) discovered during reconnaissance.
        """
        self._validate_target_scope(target)
        target_info = target_info or {}
        self._current_target = target
        self._current_service = target_info.get("service", "")

        all_findings: list[Finding] = []
        all_actions: list[AgentAction] = []

        # Query intelligence for service fingerprinting info
        service = target_info.get("service", "")
        version = target_info.get("version", "")
        intel = await self._select_intel(await self._query_intelligence(service, version))

        context = ToolSelectionContext(
            objective="Discover hosts, services, and attack surface",
            target_info={"target": target, "phase": "recon", "strategy": self.current_strategy, **target_info},
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
            if intel:
                decision_context.append(f"intel:{intel.source}:{intel.cve_id or 'unknown'}")
            action_id = str(uuid.uuid4())
            result_finding_id: str | None = None
            tool_name = "unknown"
            iteration_findings = 0

            try:
                selection = await self.select_tool(context)
                tool_name = selection.tool_name

                self._log.info("executing_tool", tool=tool_name, command=selection.command[:80], confidence=selection.confidence)
                result = await self._kali_execute_and_publish(selection.command, selection.tool_name)

                if not result.success:
                    self._log.warning("tool_execution_failed", tool=tool_name, error=result.stderr[:200] if result.stderr else "")
                    alt = await self._handle_recon_failure(tool_name)
                    if alt:
                        decision_context.append(f"rag_escalation:{tool_name}:{alt}")

                processed = await self.output_processor.async_process(
                    stdout=result.stdout,
                    stderr=result.stderr,
                    tool=tool_name,
                    exit_code=result.exit_code,
                    agent_id=str(self.agent_id),
                    target=target,
                    error_type=getattr(result, "error_type", None),
                )

                for finding in processed.findings:
                    execution = self._execution_metadata(result, selection.command)
                    evidence_payload: dict[str, Any] = {
                        "raw_evidence": finding.evidence,
                        "summary": processed.summary,
                        "command": selection.command,
                        "execution": execution,
                        "parser_tier": processed.tier,
                    }
                    assessment = assess_finding_payload(
                        {
                            "type": finding.type,
                            "severity": finding.severity,
                            "target": target,
                            "tool": tool_name,
                            "evidence": evidence_payload,
                            "execution": execution,
                        }
                    )
                    evidence_payload["validation"] = assessment
                    if assessment["outcome_status"] == "failed":
                        continue

                    finding.severity = assessment["severity"]
                    finding.evidence = json.dumps(evidence_payload)
                    await self.on_finding(target, finding.type, asdict(finding))
                    all_findings.append(finding)
                    iteration_findings += 1
                    if result_finding_id is None:
                        result_finding_id = finding.id

                context = ToolSelectionContext(
                    objective=context.objective,
                    target_info=context.target_info,
                    available_tools=[],
                    phase=context.phase,
                    constraints=context.constraints,
                    previous_results=[asdict(f) for f in all_findings],
                )

            except ScopeViolationError as e:
                decision_context.append(f"scope_blocked:{e.scope_rule}")
                self._log.warning(
                    "recon_scope_blocked",
                    error=str(e),
                    scope_rule=e.scope_rule,
                    iteration=iteration,
                    tool=tool_name,
                )
            except Exception as e:
                self._log.error("recon_iteration_error", error=str(e), iteration=iteration)

            streak = self._record_iteration_findings(iteration_findings)
            if streak >= self._no_finding_streak_threshold:
                decision_context.append(f"yield_streak:{streak}")
                alt = await self._handle_recon_failure("yield_no_finding")
                if alt:
                    decision_context.append(f"rag_escalation:yield_no_finding:{alt}")
                await self._publish_swarm_log(
                    "YIELD_GUARD",
                    "Recon no-yield streak triggered escalation",
                    role="recon",
                    tool=tool_name,
                    target=target,
                    streak=streak,
                    agent_id=str(self.agent_id),
                )
            context = self._add_novelty_constraints(context, streak)

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

    async def _query_intelligence(self, service: str = "", version: str = "") -> list["IntelResult"]:
        """Query intelligence aggregator for service fingerprinting info."""
        if not self._intel_aggregator:
            return []
        query_service = (service or self._current_service or "network").strip()
        query_version = (version or self._current_target or "").strip()
        try:
            return await asyncio.wait_for(
                self._intel_aggregator.query(query_service, query_version),
                timeout=self.INTELLIGENCE_TIMEOUT
            )
        except Exception:
            return []

    async def _select_intel(self, results: list["IntelResult"] | None) -> "IntelResult | None":
        """Select highest priority intelligence result."""
        if not results:
            return None
        return sorted(results, key=lambda r: r.priority)[0]

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
        """Load scope validator from configured file or engagement directory."""
        settings = get_settings()
        path = settings.engagement.scope_path
        if path:
            try:
                return ScopeValidator.from_file(path)
            except Exception as e:
                self._log.warning("failed_to_load_scope_file", path=path, error=str(e))
        # Fallback: search engagement directory for scope.yaml
        from pathlib import Path as _Path
        eng_dir = _Path.home() / ".cyber-red" / "engagements"
        if eng_dir.exists():
            for scope_file in sorted(eng_dir.glob("*/scope.yaml"), reverse=True):
                try:
                    return ScopeValidator.from_file(scope_file)
                except Exception:
                    continue
        return ScopeValidator(ScopeConfig(allow_private=True))

    async def _handle_recon_failure(self, technique_id: str) -> str | None:
        """Handle tool failure via RAG escalation."""
        if not self._rag_escalator:
            return None
        target_hash = self._hash_target(self._current_target) if self._current_target else "target"
        failure_count = await self._rag_escalator.record_failure(target_hash, technique_id)
        self._failure_counts[technique_id] = failure_count
        if await self._rag_escalator.should_escalate(target_hash, technique_id):
            from cyberred.agents.rag_escalator import AgentRAGContext
            context = AgentRAGContext(
                agent_id=str(self.agent_id),
                target_service=self._current_service or "network reconnaissance",
                target_hash=target_hash,
                failed_techniques=tuple(t for t, c in self._failure_counts.items() if c >= 3),
                failure_count=failure_count,
                environment={"target": self._current_target},
                engagement_id=self.engagement_id,
            )
            try:
                rag_result = await self._rag_escalator.escalate(context)
                if rag_result.was_successful:
                    return rag_result.selected_technique
            except Exception:
                pass
        return None

    def _hash_target(self, target: str) -> str:
        """Hash target string for channel naming."""
        return hashlib.md5(target.encode()).hexdigest()[:8]

    async def stop(self) -> None:
        """Gracefully stop the agent."""
        self._stop_event.set()
        self._log.info("agent_stopping")

    async def on_finding(self, target_hash: str, finding_type: str, content: dict[str, Any]) -> None:
        """Publish finding to swarm with degraded mode buffering."""
        if self._finding_buffer:
            await self._flush_buffer()

        try:
            await self._publish_to_swarm(target_hash, finding_type, content)
        except Exception as e:
            channel = f"findings:{target_hash}:{finding_type}"
            self._log.warning("publish_failed_buffering", error=str(e), channel=channel)
            self._buffer_finding_retry(
                self._finding_buffer,
                target_hash=target_hash,
                finding_type=finding_type,
                message=content,
            )

    async def _flush_buffer(self) -> None:
        """Attempt to flush buffered findings."""
        pending_count = len(self._finding_buffer)
        remaining = await self._flush_buffered_findings(self._finding_buffer)
        flushed_count = pending_count - len(remaining)
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
