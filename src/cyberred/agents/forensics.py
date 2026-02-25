"""Forensics Agent - thin subclass with LLM-driven tool selection (Story 7.23)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections import deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from cyberred.agents.base import StigmergicAgent
from cyberred.agents.roles import AgentRole
from cyberred.core.finding_policy import assess_finding_payload
from cyberred.core.models import AgentAction, Finding, ToolSelectionContext
from cyberred.tools.kali_executor import kali_execute

if TYPE_CHECKING:
    from cyberred.agents.rag_escalator import AgentRAGEscalator
    from cyberred.core.events import EventBus
    from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
    from cyberred.intelligence.base import IntelResult


class ForensicsAgent(StigmergicAgent):
    """Digital forensics agent with chain-of-custody tracking."""

    DEFAULT_MAX_ITERATIONS: int = 2  # Reduced for respawn testing
    DEFAULT_PHASE_COMPLETE_THRESHOLD: int = 50  # Prevents infinite collection loops
    INTELLIGENCE_TIMEOUT: float = 5.0

    def __init__(
        self,
        agent_id: str,
        engagement_id: str,
        event_bus: EventBus,
        specialty: str = "general",
        max_iterations: int | None = None,
        phase_complete_threshold: int | None = None,
        intel_aggregator: "CachedIntelligenceAggregator | None" = None,
        rag_escalator: "AgentRAGEscalator | None" = None,
        **kwargs: Any,
    ) -> None:
        """Initialize ForensicsAgent with role=FORENSICS and optional specialty."""
        super().__init__(
            agent_name=f"forensics-agent-{specialty}",
            agent_id=agent_id,
            engagement_id=engagement_id,
            event_bus=event_bus,
            role=AgentRole.FORENSICS,
            specialty=specialty,
            **kwargs,
        )
        self.specialty = specialty
        self.max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
        self.phase_complete_threshold = (
            phase_complete_threshold or self.DEFAULT_PHASE_COMPLETE_THRESHOLD
        )
        self.current_strategy = "standard"
        self._intel_aggregator = intel_aggregator
        self._rag_escalator = rag_escalator
        self._failure_counts: dict[str, int] = {}
        self._current_target: str = ""
        self._current_os_type: str = ""
        self._collected_artifacts: deque[dict[str, Any]] = deque(maxlen=200)
        self._finding_buffer: list[dict[str, Any]] = []
        self._stop_event = asyncio.Event()

    async def execute_forensics_collection(
        self, target: str, context: dict[str, Any]
    ) -> tuple[list[Finding], list[AgentAction]]:
        """Execute LLM-driven forensics collection on target."""
        findings: list[Finding] = []
        actions: list[AgentAction] = []

        if self._stop_event.is_set():
            return findings, actions

        self._current_target = target
        self._current_os_type = context.get("os_type", "")

        # Query intelligence for persistence mechanisms and artifact locations
        os_type = context.get("os_type", "")
        artifact_type = context.get("artifact_type", "")
        intel = await self._select_intel(await self._query_intelligence(os_type, artifact_type))

        tool_context = self._build_tool_context(target, context, actions)

        for _iteration in range(self.max_iterations):
            if self._stop_event.is_set():
                break

            if await self._phase_complete(tool_context):
                break

            decision_context = self._build_decision_context(target, context, intel)
            action_id = str(uuid.uuid4())
            result_finding_id: str | None = None
            tool_name = "unknown"
            iteration_findings = 0

            try:
                selection = await self.select_tool(tool_context)
                tool_name = selection.tool_name
                result = await self._kali_execute_and_publish(selection.command, selection.tool_name)

                if result.success and result.stdout:
                    finding = self._create_finding(target, selection, result)
                    if finding:
                        findings.append(finding)
                        await self.on_finding(finding)
                        result_finding_id = finding.id
                        iteration_findings += 1
                    else:
                        decision_context.append(f"tool_failed:{tool_name}")
                        alt = await self._handle_forensics_failure(tool_name)
                        if alt:
                            decision_context.append(f"rag_escalation:{tool_name}:{alt}")

                    # Create chain-of-custody record for collected artifact
                    custody_record = self._create_custody_record(
                        artifact_path=f"/evidence/{self.engagement_id}/{tool_name}_{action_id[:8]}.out",
                        source_target=target,
                        acquisition_method=selection.command,
                        sha256=self._compute_sha256(result.stdout.encode()),
                    )
                    self._collected_artifacts.append(custody_record)
                elif not result.success:
                    # Log failed execution for audit trail (NFR37 compliance)
                    self._log.warning(
                        "forensics_tool_failed",
                        tool=tool_name,
                        exit_code=getattr(result, "exit_code", None),
                        stderr=result.stderr[:200] if result.stderr else None,
                    )
                    decision_context.append(f"tool_failed:{tool_name}")
                    if result.stderr:
                        decision_context.append(f"stderr:{result.stderr[:100]}")
                    alt = await self._handle_forensics_failure(tool_name)
                    if alt:
                        decision_context.append(f"rag_escalation:{tool_name}:{alt}")

                # Update context with results
                tool_context = self._build_tool_context(target, context, actions)

            except Exception as e:
                self._log.error("forensics_iteration_error", error=str(e))
                actions.append(
                    AgentAction(
                        id=action_id,
                        agent_id=self.agent_id,
                        action_type="forensics:unknown",
                        target=target,
                        timestamp=self._get_timestamp(),
                        decision_context=[
                            f"initial_spawn:{self.agent_id}",
                            f"target:{target}",
                            f"error:{e}",
                        ],
                    )
                )
                break

            streak = self._record_iteration_findings(iteration_findings)
            if streak >= self._no_finding_streak_threshold:
                decision_context.append(f"yield_streak:{streak}")
                alt = await self._handle_forensics_failure("yield_no_finding")
                if alt:
                    decision_context.append(f"rag_escalation:yield_no_finding:{alt}")
                await self._publish_swarm_log(
                    "YIELD_GUARD",
                    "Forensics no-yield streak triggered escalation",
                    role="forensics",
                    tool=tool_name,
                    target=target,
                    streak=streak,
                    agent_id=str(self.agent_id),
                )

            # Always record action for audit trail (NFR37) - both success and failure
            actions.append(
                AgentAction(
                    id=action_id,
                    agent_id=self.agent_id,
                    action_type=f"forensics:{tool_name}",
                    target=target,
                    timestamp=self._get_timestamp(),
                    decision_context=decision_context,
                    result_finding_id=result_finding_id,
                )
            )

        return findings, actions

    async def _query_intelligence(self, os_type: str = "", artifact_type: str = "") -> list["IntelResult"]:
        """Query intelligence aggregator for persistence mechanisms and artifact locations."""
        if not self._intel_aggregator:
            return []
        query_os = (os_type or self._current_os_type or "host").strip()
        query_artifact = (artifact_type or self._current_target or "").strip()
        try:
            return await asyncio.wait_for(
                self._intel_aggregator.query(query_os, query_artifact),
                timeout=self.INTELLIGENCE_TIMEOUT,
            )
        except Exception:
            return []

    async def _select_intel(self, results: list["IntelResult"] | None) -> "IntelResult | None":
        """Select highest priority intelligence result."""
        return sorted(results, key=lambda r: r.priority)[0] if results else None

    def _build_decision_context(self, target: str, context: dict[str, Any], intel: "IntelResult | None" = None) -> list[str]:
        """Build decision context list for NFR37 compliance."""
        ctx = [f"initial_spawn:{self.agent_id}", f"target:{target}"]
        if context.get("memory_image"):
            ctx.append(f"memory_image:{context['memory_image']}")
        for artifact in list(self._collected_artifacts)[-3:]:
            ctx.append(f"artifact:{artifact.get('artifact_id', 'unknown')[:8]}")
        if intel:
            ctx.append(f"intel:{intel.source}:{intel.cve_id or 'unknown'}")
        return ctx

    def _build_tool_context(
        self, target: str, context: dict[str, Any], actions: list[AgentAction]
    ) -> ToolSelectionContext:
        """Build tool selection context for LLM."""
        # Determine available tools based on context
        available_tools = self._get_available_tools(context)

        return ToolSelectionContext(
            objective=f"Collect and analyze digital evidence from {target}",
            phase="forensics",
            constraints=self._get_constraints(),
            target_info={
                "target": target,
                "memory_image": context.get("memory_image"),
                "artifact_paths": context.get("artifact_paths", []),
                "strategy": self.current_strategy,
                "specialty": self.specialty,
                **context,
            },
            available_tools=available_tools,
            previous_results=self.get_recent_tool_results(limit=30),
        )

    def _get_available_tools(self, context: dict[str, Any]) -> list[str]:
        """Get available forensics tools based on context."""
        tools = ["strings", "binwalk", "file", "xxd", "hexdump", "find", "grep", "sha256sum", "md5sum"]  # fmt: skip
        if context.get("memory_image"):
            tools.extend(["volatility", "volatility3", "rekall"])
        if self.specialty in ("disk", "general"):
            tools.extend(["sleuthkit", "autopsy", "foremost", "scalpel", "photorec"])
        tools.extend(["tcpdump", "tshark", "wireshark"])
        return tools

    def _get_constraints(self) -> list[str]:
        """Get constraints based on current strategy."""
        constraints: list[str] = []
        if self.current_strategy == "stealth":
            constraints.extend([
                "Preserve evidence integrity at all costs",
                "Use read-only operations when possible",
                "Document all access with timestamps",
                "Minimize system impact",
            ])
        elif self.current_strategy == "aggressive":
            constraints.extend([
                "Full evidence collection permitted",
                "Deep analysis allowed",
                "Live memory acquisition enabled",
            ])
        # Standard strategy: balanced approach with baseline forensic discipline
        if self.current_strategy == "standard":
            constraints.extend([
                "Document all evidence collection operations",
                "Compute hashes for all extracted artifacts",
                "Maintain chain-of-custody records",
            ])
        if self._no_finding_streak >= 2:
            constraints.append("pivot artifact sources and analysis techniques from recent no-yield runs")
        if self._no_finding_streak >= self._no_finding_streak_threshold:
            constraints.append("choose materially different forensic collection scope and tooling")
        return constraints

    MAX_EVIDENCE_SIZE: int = 500  # Truncate large outputs with indicator

    def _create_finding(self, target: str, selection: Any, result: Any) -> Finding | None:
        """Create a Finding from tool execution result."""
        evidence = ""
        if result.stdout:
            if len(result.stdout) > self.MAX_EVIDENCE_SIZE:
                evidence = result.stdout[:self.MAX_EVIDENCE_SIZE] + f"... [TRUNCATED: {len(result.stdout)} bytes total]"
            else:
                evidence = result.stdout
        execution = self._execution_metadata(result, selection.command)
        evidence_payload: dict[str, Any] = {
            "raw_evidence": evidence,
            "command": selection.command,
            "execution": execution,
            "specialty": self.specialty,
        }
        assessment = assess_finding_payload(
            {
                "type": "forensics",
                "severity": "medium",
                "target": target,
                "tool": selection.tool_name,
                "evidence": evidence_payload,
                "execution": execution,
            }
        )
        evidence_payload["validation"] = assessment
        if assessment["outcome_status"] == "failed":
            return None
        return Finding(
            id=str(uuid.uuid4()),
            type="forensics",
            severity=assessment["severity"],
            target=target,
            evidence=json.dumps(evidence_payload),
            agent_id=self.agent_id,
            timestamp=self._get_timestamp(),
            tool=selection.tool_name,
            topic=f"findings:{self._hash_target(target)}:forensics",
            signature=f"forensics-{selection.tool_name}-{uuid.uuid4().hex[:8]}",
        )

    # === Chain of Custody Methods ===

    def _create_custody_record(
        self,
        artifact_path: str,
        source_target: str,
        acquisition_method: str,
        sha256: str,
    ) -> dict[str, Any]:
        """Create chain-of-custody metadata record with required fields."""
        return {
            "artifact_id": str(uuid.uuid4()),
            "source_target": source_target,
            "collected_at": self._get_timestamp(),
            "collector_agent_id": self.agent_id,
            "acquisition_method": acquisition_method,
            "sha256": sha256,
            "path": artifact_path,
        }

    def _compute_sha256(self, content: bytes) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content).hexdigest()

    # === Stigmergic Communication Methods ===

    async def on_signal(self, channel: str, data: dict[str, Any]) -> None:
        """Handle incoming stigmergic signal."""
        await super().on_signal(channel, data)
        # Handle strategy updates
        if "strategies" in channel and data.get("strategy") in (
            "stealth",
            "standard",
            "aggressive",
        ):
            self.current_strategy = data["strategy"]
            return

        # Handle incoming artifact requests from other agents
        if "forensics" in channel and data.get("artifact_request"):
            self._log.info("artifact_request_received", request=data["artifact_request"])

    async def on_finding(self, finding: Finding) -> None:
        """Publish finding to forensics channel."""
        if self._finding_buffer:
            await self._flush_buffer()

        target_hash = self._hash_target(finding.target)
        message = {
            "id": finding.id,
            "type": finding.type,
            "target": finding.target,
            "severity": finding.severity,
            "evidence": finding.evidence,
            "tool": finding.tool,
        }
        try:
            await self._publish_to_swarm(target_hash, "forensics", message)
        except Exception:
            self._buffer_finding_retry(
                self._finding_buffer,
                target_hash=target_hash,
                finding_type="forensics",
                message=message,
            )

    async def _flush_buffer(self) -> None:
        """Flush buffered findings on reconnect."""
        self._finding_buffer = await self._flush_buffered_findings(self._finding_buffer)

    async def stop(self) -> None:
        """Stop the agent gracefully."""
        if self._finding_buffer:
            await self._flush_buffer()
        self._stop_event.set()

    async def _handle_forensics_failure(self, technique_id: str) -> str | None:
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
                target_service=f"{self._current_os_type} forensics" if self._current_os_type else "digital forensics",
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

    async def _phase_complete(self, context: ToolSelectionContext) -> bool:
        """Check if forensics collection phase is complete."""
        return len(context.previous_results) >= self.phase_complete_threshold

    def _hash_target(self, target: str) -> str:
        """Hash target string for channel naming (8-char SHA256 prefix)."""
        return hashlib.sha256(target.encode()).hexdigest()[:8]

    def _get_timestamp(self) -> str:
        """Get current UTC timestamp in ISO format."""
        return datetime.now(UTC).isoformat()
