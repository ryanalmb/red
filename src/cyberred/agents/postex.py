"""PostExAgent - LLM-driven post-exploitation agent (Story 7.5-v2).

Thin subclass of StigmergicAgent using inherited LLM tool selection.
Supports Linux, Windows, and Active Directory post-exploitation phases.
"""
import asyncio
import contextlib
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
from cyberred.core.events import EventBus
from cyberred.core.hashing import compute_hmac_signature
from cyberred.core.models import AgentAction, Finding, ToolSelectionContext
from cyberred.tools.kali_executor import kali_execute
from cyberred.tools.output import OutputProcessor
from cyberred.tools.parsers.linpeas import linpeas_parser
from cyberred.tools.scope import ScopeConfig, ScopeValidator

if TYPE_CHECKING:
    from cyberred.agents.rag_escalator import AgentRAGEscalator
    from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
    from cyberred.intelligence.base import IntelResult
    from cyberred.llm.gateway import LLMGateway
    from cyberred.tools.manifest import ManifestLoader

log = structlog.get_logger().bind(component="postex_agent")
DEFAULT_HMAC_KEY = b"cyber-red-postex-agent-key-v1"
INTELLIGENCE_TIMEOUT = 5.0


class PostExAgent(StigmergicAgent):
    """LLM-driven post-exploitation agent - thin subclass setting role=POSTEX."""

    DEFAULT_MAX_ITERATIONS: int = 2
    DEFAULT_PHASE_COMPLETE_THRESHOLD: int = 50

    def __init__(
        self, agent_id: str, engagement_id: str, event_bus: EventBus, specialty: str = "linux",
        llm_gateway: "LLMGateway | None" = None, manifest_loader: "ManifestLoader | None" = None,
        intel_aggregator: "CachedIntelligenceAggregator | None" = None,
        rag_escalator: "AgentRAGEscalator | None" = None, max_iterations: int | None = None,
        phase_complete_threshold: int | None = None, hmac_key: bytes = DEFAULT_HMAC_KEY, **kwargs: Any,
    ) -> None:
        super().__init__(
            agent_name="PostExAgent", agent_id=agent_id, engagement_id=engagement_id,
            event_bus=event_bus, role=AgentRole.POSTEX, specialty=specialty,
            llm_gateway=llm_gateway, manifest_loader=manifest_loader, **kwargs,
        )
        self._log = log.bind(agent_id=agent_id, engagement_id=engagement_id)
        self._hmac_key = hmac_key
        self._intel_aggregator = intel_aggregator
        self._rag_escalator = rag_escalator
        self._failure_counts: dict[str, int] = {}
        self.output_processor = OutputProcessor()
        with contextlib.suppress(Exception):
            self.output_processor.register_parser("linpeas", linpeas_parser)
        self.max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
        self.phase_complete_threshold = phase_complete_threshold or self.DEFAULT_PHASE_COMPLETE_THRESHOLD
        self.current_strategy = "standard"
        self._finding_buffer: list[dict[str, Any]] = []
        self._stop_event = asyncio.Event()
        self._current_target: str = ""
        self._current_os_type: str = ""

    async def execute_postex(
        self, target: str, access_data: dict[str, Any]
    ) -> tuple[list[Finding], list[AgentAction]]:
        """Execute LLM-driven post-exploitation against target."""
        self._validate_target_scope(target)
        if self._stop_event.is_set():
            return [], []

        all_findings: list[Finding] = []
        all_actions: list[AgentAction] = []
        os_type = access_data.get("os_type", "linux")
        privilege_level = access_data.get("privilege_level", "user")
        access_type = access_data.get("access_type", "shell")
        self._current_target = target
        self._current_os_type = os_type
        intel = await self._select_technique(await self._query_intelligence(os_type, access_type))

        context = ToolSelectionContext(
            objective=f"Post-exploitation on {os_type} system",
            target_info={"target": target, "phase": "postex", "strategy": self.current_strategy,
                         "os_type": os_type, "privilege_level": privilege_level, "access_type": access_type},
            available_tools=[], phase="postex", constraints=self._get_constraints(), previous_results=[],
        )

        for _ in range(self.max_iterations):
            if self._stop_event.is_set() or await self._phase_complete(context):
                break
            decision_context = self.get_decision_context().copy() or [f"initial_spawn:{self.agent_id}"]
            if intel:
                decision_context.append(f"intel:{intel.source}:{intel.cve_id or 'unknown'}")
            action_id, result_finding_id, tool_name = str(uuid.uuid4()), None, "unknown"

            try:
                selection = await self.select_tool(context)
                tool_name = selection.tool_name
                self._log.info("executing_tool", tool=tool_name, command=selection.command[:80])
                result = await self._kali_execute_and_publish(selection.command, selection.tool_name)
                if result.success:
                    finding = await self._process_postex_result(target, selection, result, access_data, intel)
                    if finding:
                        all_findings.append(finding)
                        await self.on_finding(finding)
                        result_finding_id = finding.id
                else:
                    alt = await self._handle_postex_failure(tool_name)
                    if alt:
                        decision_context.append(f"rag_escalation:{tool_name}:{alt}")
                context = ToolSelectionContext(
                    objective=context.objective, target_info=context.target_info, available_tools=[],
                    phase=context.phase, constraints=context.constraints,
                    previous_results=[asdict(f) for f in all_findings],
                )
            except Exception as e:
                self._log.error("postex_iteration_error", error=str(e))

            all_actions.append(AgentAction(
                id=action_id, agent_id=str(self.agent_id), action_type=f"postex:{tool_name}",
                target=target, timestamp=datetime.now(UTC).isoformat(),
                decision_context=decision_context, result_finding_id=result_finding_id,
            ))
        return all_findings, all_actions

    async def _process_postex_result(
        self, target: str, selection: Any, result: Any, access_data: dict[str, Any], intel: "IntelResult | None"
    ) -> Finding | None:
        finding_data = {
            "id": str(uuid.uuid4()), "target": target, "type": "postex", "tool": selection.tool_name,
            "severity": "high", "timestamp": datetime.now(UTC).isoformat(),
            "agent_id": str(self.agent_id), "topic": f"findings:{self._hash_target(target)}:postex",
            "evidence": json.dumps({"stdout": result.stdout[:2000] if result.stdout else "",
                                    "command": selection.command, "cve_id": intel.cve_id if intel else None,
                                    "os_type": access_data.get("os_type")}),
        }
        finding_data["signature"] = self._generate_finding_signature(finding_data)
        return Finding(**finding_data)

    async def _phase_complete(self, context: ToolSelectionContext) -> bool:
        return len(context.previous_results) >= self.phase_complete_threshold

    def _get_constraints(self) -> list[str]:
        if self.current_strategy == "stealth":
            return ["low_rate", "avoid_detection"]
        elif self.current_strategy == "aggressive":
            return ["high_throughput", "comprehensive"]
        return []

    def _validate_target_scope(self, target: str) -> None:
        self._get_scope_validator().validate(target=target)

    def _get_scope_validator(self) -> ScopeValidator:
        settings = get_settings()
        if settings.engagement.scope_path:
            try:
                return ScopeValidator.from_file(settings.engagement.scope_path)
            except Exception:
                pass
        return ScopeValidator(ScopeConfig())

    async def _query_intelligence(self, os_type: str = "", access_type: str = "") -> list["IntelResult"]:
        if not self._intel_aggregator:
            return []
        try:
            return await asyncio.wait_for(
                self._intel_aggregator.query(os_type, access_type), timeout=INTELLIGENCE_TIMEOUT)
        except Exception:
            return []

    async def _select_technique(self, results: list["IntelResult"] | None) -> "IntelResult | None":
        return sorted(results, key=lambda r: r.priority)[0] if results else None

    async def _handle_postex_failure(self, technique_id: str) -> str | None:
        if not self._rag_escalator:
            return None
        target_hash = self._hash_target(self._current_target) if self._current_target else "target"
        failure_count = await self._rag_escalator.record_failure(target_hash, technique_id)
        self._failure_counts[technique_id] = failure_count
        if await self._rag_escalator.should_escalate(target_hash, technique_id):
            from cyberred.agents.rag_escalator import AgentRAGContext
            context = AgentRAGContext(
                agent_id=str(self.agent_id),
                target_service=f"{self._current_os_type} privilege escalation" if self._current_os_type else "linux post-exploitation",
                target_hash=target_hash,
                failed_techniques=tuple(t for t, c in self._failure_counts.items() if c >= 3),
                failure_count=failure_count,
                environment={"os": self._current_os_type, "target": self._current_target},
                engagement_id=self.engagement_id,
            )
            try:
                rag_result = await self._rag_escalator.escalate(context)
                if rag_result.was_successful:
                    return rag_result.selected_technique
            except Exception:
                pass
        return None

    # Note: _request_authorization() is inherited from StigmergicAgent base class (Story 7.16)
    # The base implementation provides state management, decision context tracking,
    # and alternative action selection on denial.

    def _generate_finding_signature(self, finding_data: dict[str, Any]) -> str:
        return compute_hmac_signature({k: v for k, v in finding_data.items() if k != "signature"}, self._hmac_key)

    def _hash_target(self, target: str) -> str:
        return hashlib.md5(target.encode()).hexdigest()[:8]

    async def on_finding(self, finding: Finding) -> None:
        target_hash = self._hash_target(finding.target)
        message = asdict(finding)
        if self._finding_buffer:
            await self._flush_buffer()
        try:
            await self._publish_to_swarm(target_hash, "postex", message)
        except Exception:
            channel = f"findings:{target_hash}:postex"
            self._finding_buffer.append({"channel": channel, "message": message})

    async def _flush_buffer(self) -> None:
        remaining = []
        for item in self._finding_buffer:
            try:
                await self.event_bus.publish(item["channel"], item["message"])
            except Exception:
                remaining.append(item)
        self._finding_buffer = remaining

    async def on_signal(self, channel: str, data: dict[str, Any]) -> None:
        await super().on_signal(channel, data)
        if "strategies" in channel:
            strategy = data.get("strategy")
            if strategy in ("stealth", "standard", "aggressive"):
                self.current_strategy = strategy

    async def stop(self) -> None:
        self._stop_event.set()
        if self._finding_buffer:
            await self._flush_buffer()
