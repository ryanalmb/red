"""WebAppAgent - LLM-driven web application testing agent (Story 7.19)."""
import asyncio
import hashlib
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
from cyberred.tools.scope import ScopeConfig, ScopeValidator

if TYPE_CHECKING:
    from cyberred.agents.rag_escalator import AgentRAGEscalator
    from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
    from cyberred.intelligence.base import IntelResult
    from cyberred.llm.gateway import LLMGateway
    from cyberred.tools.manifest import ManifestLoader

log = structlog.get_logger().bind(component="webapp_agent")
DEFAULT_HMAC_KEY = b"cyber-red-webapp-agent-key-v1"
INTELLIGENCE_TIMEOUT = 5.0


class WebAppAgent(StigmergicAgent):
    """LLM-driven web application testing agent - thin subclass setting role=WEBAPP."""

    DEFAULT_MAX_ITERATIONS: int = 8
    DEFAULT_PHASE_COMPLETE_THRESHOLD: int = 30

    def __init__(self, agent_id: str, engagement_id: str, event_bus: EventBus,
                 specialty: str = "general", llm_gateway: "LLMGateway | None" = None,
                 manifest_loader: "ManifestLoader | None" = None,
                 intel_aggregator: "CachedIntelligenceAggregator | None" = None,
                 rag_escalator: "AgentRAGEscalator | None" = None,
                 max_iterations: int | None = None,
                 phase_complete_threshold: int | None = None,
                 hmac_key: bytes = DEFAULT_HMAC_KEY, **kwargs: Any) -> None:
        super().__init__(agent_name="WebAppAgent", agent_id=agent_id, engagement_id=engagement_id,
                         event_bus=event_bus, role=AgentRole.WEBAPP, specialty=specialty,
                         llm_gateway=llm_gateway, manifest_loader=manifest_loader, **kwargs)
        self._log = log.bind(agent_id=agent_id, engagement_id=engagement_id)
        self._hmac_key = hmac_key
        self._intel_aggregator = intel_aggregator
        self._rag_escalator = rag_escalator
        self._failure_counts: dict[str, int] = {}
        self._current_target: str = ""
        self._current_service: str = ""
        self.max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
        self.phase_complete_threshold = phase_complete_threshold or self.DEFAULT_PHASE_COMPLETE_THRESHOLD
        self.current_strategy, self._finding_buffer = "standard", []
        self._stop_event, self._waf_detected, self._waf_type = asyncio.Event(), False, None

    async def execute_webapp_scan(
        self, target: str, target_info: dict[str, Any]
    ) -> tuple[list[Finding], list[AgentAction]]:
        """Execute LLM-driven web application scan against target."""
        self._validate_target_scope(target)
        if self._stop_event.is_set():
            return [], []

        self._current_target = target
        self._current_service = target_info.get("service", "http")
        await self._detect_waf(target)

        all_findings: list[Finding] = []
        all_actions: list[AgentAction] = []
        has_credentials = bool(target_info.get("credentials"))

        # Query intelligence for web application CVEs
        service = target_info.get("service", "http")
        version = target_info.get("version", "")
        intel = await self._select_intel(await self._query_intelligence(service, version))

        context = ToolSelectionContext(
            objective="Test web application for OWASP Top 10 vulnerabilities",
            target_info={"target": target, "phase": "webapp", "strategy": self.current_strategy,
                         "waf_detected": self._waf_detected, "waf_type": self._waf_type, **target_info},
            available_tools=[],
            phase="webapp",
            constraints=self._get_constraints(),
            previous_results=[],
        )

        for _ in range(self.max_iterations):
            if self._stop_event.is_set() or await self._phase_complete(context):
                break

            decision_context = self.get_decision_context().copy() or [f"initial_spawn:{self.agent_id}"]
            if self._waf_detected and self._waf_type:
                decision_context.append(f"waf:{self._waf_type}")
            if has_credentials:
                decision_context.append("auth:credentials_provided")
            if intel:
                decision_context.append(f"intel:{intel.source}:{intel.cve_id or 'unknown'}")

            action_id = str(uuid.uuid4())
            result_finding_id: str | None = None
            tool_name = "unknown"

            try:
                selection = await self.select_tool(context)
                tool_name = selection.tool_name
                self._log.info("executing_tool", tool=tool_name, command=selection.command[:80])
                result = await kali_execute(selection.command)

                if result.success and result.stdout:
                    finding = self._create_finding(target, selection, result, intel)
                    all_findings.append(finding)
                    await self.on_finding(finding)
                    result_finding_id = finding.id
                elif not result.success:
                    alt = await self._handle_webapp_failure(selection.tool_name)
                    if alt:
                        decision_context.append(f"rag_escalation:{selection.tool_name}:{alt}")

                context = ToolSelectionContext(
                    objective=context.objective,
                    target_info=context.target_info,
                    available_tools=[],
                    phase=context.phase,
                    constraints=context.constraints,
                    previous_results=[asdict(f) for f in all_findings],
                )
            except Exception as e:
                self._log.error("webapp_iteration_error", error=str(e))

            all_actions.append(AgentAction(
                id=action_id,
                agent_id=str(self.agent_id),
                action_type=f"webapp:{tool_name}",
                target=target,
                timestamp=datetime.now(UTC).isoformat(),
                decision_context=decision_context,
                result_finding_id=result_finding_id,
            ))

        return all_findings, all_actions

    async def _query_intelligence(self, service: str = "", version: str = "") -> list["IntelResult"]:
        """Query intelligence aggregator for web application CVEs."""
        if not self._intel_aggregator or not service:
            return []
        try:
            return await asyncio.wait_for(
                self._intel_aggregator.query(service, version),
                timeout=INTELLIGENCE_TIMEOUT
            )
        except Exception:
            return []

    async def _select_intel(self, results: list["IntelResult"] | None) -> "IntelResult | None":
        """Select highest priority intelligence result."""
        if not results:
            return None
        return sorted(results, key=lambda r: r.priority)[0]

    def _create_finding(self, target: str, selection: Any, result: Any, intel: "IntelResult | None" = None) -> Finding:
        import json
        finding_data = {
            "id": str(uuid.uuid4()), "target": target, "type": "webapp",
            "tool": selection.tool_name, "severity": "medium",
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_id": str(self.agent_id),
            "topic": f"findings:{self._hash_target(target)}:webapp",
            "evidence": json.dumps({
                "stdout": result.stdout[:2000] if result.stdout else "",
                "cve_id": intel.cve_id if intel else None
            }),
        }
        finding_data["signature"] = compute_hmac_signature(
            {k: v for k, v in finding_data.items() if k != "signature"}, self._hmac_key
        )
        return Finding(**finding_data)

    async def _detect_waf(self, target: str) -> None:
        """Detect WAF presence via wafw00f."""
        try:
            result = await kali_execute(f"wafw00f {target}")
            if result.success and result.stdout:
                output = result.stdout.lower()
                if "detected" in output and "no waf" not in output:
                    self._waf_detected = True
                    for waf in ["cloudflare", "akamai", "aws", "imperva", "f5", "mod_security"]:
                        if waf in output:
                            self._waf_type = waf
                            break
                    if self._waf_type is None:
                        self._waf_type = "unknown"
        except Exception as e:
            self._log.warning("waf_detection_failed", error=str(e))
            self._waf_detected = False

    async def _handle_webapp_failure(self, technique_id: str) -> str | None:
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
                target_service=self._current_service or "web application",
                target_hash=target_hash,
                failed_techniques=tuple(t for t, c in self._failure_counts.items() if c >= 3),
                failure_count=failure_count,
                environment={"target": self._current_target, "waf": self._waf_type or "none"},
                engagement_id=self.engagement_id,
            )
            try:
                rag_result = await self._rag_escalator.escalate(context)
                if rag_result.was_successful:
                    return rag_result.selected_technique
            except Exception:
                pass
        return None

    async def _phase_complete(self, context: ToolSelectionContext) -> bool:
        return len(context.previous_results) >= self.phase_complete_threshold

    def _get_constraints(self) -> list[str]:
        """Get operational constraints based on strategy and WAF detection."""
        constraints = []
        if self.current_strategy == "stealth":
            constraints.extend(["low_rate", "avoid_detection", "passive_preferred"])
        elif self.current_strategy == "aggressive":
            constraints.extend(["high_throughput", "comprehensive"])
        if self._waf_detected:
            constraints.append(f"waf_evasion:{self._waf_type or 'generic'}")
        return constraints

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

    def _hash_target(self, target: str) -> str:
        return hashlib.md5(target.encode()).hexdigest()[:8]

    async def on_finding(self, finding: Finding) -> None:
        target_hash = self._hash_target(finding.target)
        message = asdict(finding)
        if self._finding_buffer:
            await self._flush_buffer()
        try:
            await self._publish_to_swarm(target_hash, "webapp", message)
        except Exception:
            channel = f"findings:{target_hash}:webapp"
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
                self._log.info("strategy_updated", old=self.current_strategy, new=strategy)
                self.current_strategy = strategy

    async def stop(self) -> None:
        self._stop_event.set()
        if self._finding_buffer:
            await self._flush_buffer()
