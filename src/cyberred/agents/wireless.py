"""WirelessAgent - LLM-driven wireless network testing agent (Story 7.20)."""
import asyncio
import hashlib
import uuid
from collections import deque
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from cyberred.agents.base import StigmergicAgent
from cyberred.agents.roles import AgentRole
from cyberred.core.events import EventBus
from cyberred.core.hashing import compute_hmac_signature
from cyberred.core.models import AgentAction, Finding, ToolSelectionContext
from cyberred.tools.kali_executor import kali_execute

if TYPE_CHECKING:
    from cyberred.agents.rag_escalator import AgentRAGEscalator
    from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
    from cyberred.intelligence.base import IntelResult
    from cyberred.llm.gateway import LLMGateway
    from cyberred.tools.manifest import ManifestLoader

log = structlog.get_logger().bind(component="wireless_agent")
DEFAULT_HMAC_KEY = b"cyber-red-wireless-agent-key-v1"
INTELLIGENCE_TIMEOUT = 5.0


class WirelessAgent(StigmergicAgent):
    """LLM-driven wireless network testing agent - thin subclass setting role=WIRELESS."""

    DEFAULT_MAX_ITERATIONS: int = 2
    DEFAULT_PHASE_COMPLETE_THRESHOLD: int = 15

    def __init__(self, agent_id: str, engagement_id: str, event_bus: EventBus,
                 specialty: str = "general", llm_gateway: "LLMGateway | None" = None,
                 manifest_loader: "ManifestLoader | None" = None,
                 intel_aggregator: "CachedIntelligenceAggregator | None" = None,
                 rag_escalator: "AgentRAGEscalator | None" = None,
                 max_iterations: int | None = None,
                 phase_complete_threshold: int | None = None,
                 hmac_key: bytes = DEFAULT_HMAC_KEY, **kwargs: Any) -> None:
        super().__init__(agent_name="WirelessAgent", agent_id=agent_id, engagement_id=engagement_id,
                         event_bus=event_bus, role=AgentRole.WIRELESS, specialty=specialty,
                         llm_gateway=llm_gateway, manifest_loader=manifest_loader, **kwargs)
        self._log = log.bind(agent_id=agent_id, engagement_id=engagement_id)
        self._hmac_key = hmac_key
        self._intel_aggregator = intel_aggregator
        self._rag_escalator = rag_escalator
        self._failure_counts: dict[str, int] = {}
        self._current_target: str = ""
        self._current_protocol: str = ""
        self.max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
        self.phase_complete_threshold = phase_complete_threshold or self.DEFAULT_PHASE_COMPLETE_THRESHOLD
        self.current_strategy, self._finding_buffer = "standard", []
        self._stop_event = asyncio.Event()
        self._monitor_enabled: bool = False
        self._original_interface: str | None = None
        self._discovered_networks: deque[dict[str, Any]] = deque(maxlen=200)
        self._captured_handshakes: dict[str, str] = {}  # bssid -> path

    async def execute_wireless_scan(
        self, interface: str, target_info: dict[str, Any]
    ) -> tuple[list[Finding], list[AgentAction]]:
        """Execute LLM-driven wireless network scan."""
        if self._stop_event.is_set():
            return [], []

        self._current_target = interface
        self._current_protocol = target_info.get("protocol", "802.11")
        await self._enable_monitor_mode(interface)

        all_findings: list[Finding] = []
        all_actions: list[AgentAction] = []

        # Query intelligence for wireless protocol vulnerabilities
        protocol = target_info.get("protocol", "802.11")
        encryption = target_info.get("encryption", "")
        intel = await self._select_intel(await self._query_intelligence(protocol, encryption))

        context = ToolSelectionContext(
            objective="Discover and test wireless networks for vulnerabilities",
            target_info={"interface": interface, "phase": "wireless", "strategy": self.current_strategy,
                         "monitor_enabled": self._monitor_enabled,
                         "discovered_networks": list(self._discovered_networks), **target_info},
            available_tools=[],
            phase="wireless",
            constraints=self._get_constraints(),
            previous_results=[],
        )

        for _ in range(self.max_iterations):
            if self._stop_event.is_set() or await self._phase_complete(context):
                break

            decision_context = self.get_decision_context().copy() or [f"initial_spawn:{self.agent_id}"]
            decision_context.append(f"interface:{interface}")
            for bssid in self._captured_handshakes:
                decision_context.append(f"handshake:{bssid}")
            if intel:
                decision_context.append(f"intel:{intel.source}:{intel.cve_id or 'unknown'}")

            action_id = str(uuid.uuid4())
            result_finding_id: str | None = None
            tool_name = "unknown"

            try:
                selection = await self.select_tool(context)
                tool_name = selection.tool_name
                self._log.info("executing_tool", tool=tool_name, command=selection.command[:80])
                result = await self._kali_execute_and_publish(selection.command, selection.tool_name)

                if result.success and result.stdout:
                    finding = self._create_finding(interface, selection, result, intel)
                    all_findings.append(finding)
                    await self.on_finding(finding)
                    result_finding_id = finding.id
                    await self._check_handshake_capture(result, selection)
                elif not result.success:
                    alt = await self._handle_wireless_failure(selection.tool_name)
                    if alt:
                        decision_context.append(f"rag_escalation:{selection.tool_name}:{alt}")

                context = ToolSelectionContext(
                    objective=context.objective,
                    target_info={**context.target_info, "discovered_networks": list(self._discovered_networks)},
                    available_tools=[],
                    phase=context.phase,
                    constraints=context.constraints,
                    previous_results=[asdict(f) for f in all_findings],
                )
            except Exception as e:
                self._log.error("wireless_iteration_error", error=str(e))

            all_actions.append(AgentAction(
                id=action_id,
                agent_id=str(self.agent_id),
                action_type=f"wireless:{tool_name}",
                target=interface,
                timestamp=datetime.now(UTC).isoformat(),
                decision_context=decision_context,
                result_finding_id=result_finding_id,
            ))

        return all_findings, all_actions

    async def _query_intelligence(self, protocol: str = "", encryption: str = "") -> list["IntelResult"]:
        """Query intelligence aggregator for wireless protocol vulnerabilities."""
        if not self._intel_aggregator or not protocol:
            return []
        try:
            return await asyncio.wait_for(
                self._intel_aggregator.query(protocol, encryption),
                timeout=INTELLIGENCE_TIMEOUT
            )
        except Exception:
            return []

    async def _select_intel(self, results: list["IntelResult"] | None) -> "IntelResult | None":
        """Select highest priority intelligence result."""
        if not results:
            return None
        return sorted(results, key=lambda r: r.priority)[0]

    def _create_finding(self, interface: str, selection: Any, result: Any, intel: "IntelResult | None" = None) -> Finding:
        import json
        finding_data = {
            "id": str(uuid.uuid4()), "target": interface, "type": "wireless",
            "tool": selection.tool_name, "severity": "medium",
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_id": str(self.agent_id),
            "topic": f"findings:{self._hash_target(interface)}:wireless",
            "evidence": json.dumps({
                "stdout": result.stdout[:2000] if result.stdout else "",
                "cve_id": intel.cve_id if intel else None
            }),
        }
        finding_data["signature"] = compute_hmac_signature(
            {k: v for k, v in finding_data.items() if k != "signature"}, self._hmac_key
        )
        return Finding(**finding_data)

    async def _enable_monitor_mode(self, interface: str) -> None:
        """Enable monitor mode via airmon-ng."""
        if self._monitor_enabled:
            return
        try:
            result = await kali_execute(f"airmon-ng start {interface}")
            if result.success and "monitor mode" in result.stdout.lower():
                self._monitor_enabled = True
                self._original_interface = interface
                self._log.info("monitor_mode_enabled", interface=interface)
        except Exception as e:
            self._log.warning("monitor_mode_failed", error=str(e))
            self._monitor_enabled = False

    async def _discover_networks(self, interface: str) -> None:
        """Discover networks via airodump-ng."""
        try:
            result = await kali_execute(f"timeout 10 airodump-ng {interface} --write-interval 1 2>&1")
            if result.success and result.stdout:
                for line in result.stdout.split("\n"):
                    if ":" in line and len(line) > 40:
                        parts = line.split()
                        if len(parts) >= 6 and ":" in parts[0]:
                            self._discovered_networks.append({
                                "bssid": parts[0], "channel": parts[5] if len(parts) > 5 else "",
                                "encryption": parts[5] if len(parts) > 5 else ""
                            })
        except Exception as e:
            self._log.warning("network_discovery_failed", error=str(e))

    async def _check_handshake_capture(self, result: Any, selection: Any) -> None:
        """Check if handshake was captured in output."""
        if "handshake" in result.stdout.lower():
            import re
            bssid_match = re.search(r"([0-9A-Fa-f:]{17})", result.stdout)
            if bssid_match:
                bssid = bssid_match.group(1).upper()
                cap_path = f"/tmp/capture-{bssid.replace(':', '')}.cap"
                self._captured_handshakes[bssid] = cap_path
                await self._publish_handshake(bssid, cap_path)

    async def _publish_handshake(self, bssid: str, path: str) -> None:
        """Publish captured handshake to credentials channel."""
        channel = f"credentials:{self.engagement_id}:handshake"
        message = {"bssid": bssid, "path": path, "agent_id": str(self.agent_id),
                   "timestamp": datetime.now(UTC).isoformat()}
        try:
            await self.event_bus.publish(channel, message)
            self._log.info("handshake_published", bssid=bssid, channel=channel)
        except Exception as e:
            self._log.warning("handshake_publish_failed", error=str(e))

    async def _handle_wireless_failure(self, technique_id: str) -> str | None:
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
                target_service=f"{self._current_protocol} wireless" if self._current_protocol else "wireless network",
                target_hash=target_hash,
                failed_techniques=tuple(t for t, c in self._failure_counts.items() if c >= 3),
                failure_count=failure_count,
                environment={"protocol": self._current_protocol, "target": self._current_target},
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
        """Get operational constraints based on strategy."""
        constraints = []
        if self.current_strategy == "stealth":
            constraints.extend(["avoid_deauth", "passive_only", "stealth_mode"])
        elif self.current_strategy == "aggressive":
            constraints.extend(["allow_all_attacks", "aggressive_deauth", "mass_deauth_allowed"])
        return constraints

    def _hash_target(self, target: str) -> str:
        return hashlib.md5(target.encode()).hexdigest()[:8]

    async def on_finding(self, finding: Finding) -> None:
        target_hash = self._hash_target(finding.target)
        message = asdict(finding)
        if self._finding_buffer:
            await self._flush_buffer()
        try:
            await self._publish_to_swarm(target_hash, "wireless", message)
        except Exception:
            channel = f"findings:{target_hash}:wireless"
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
        if self._monitor_enabled and self._original_interface:
            try:
                await kali_execute(f"airmon-ng stop {self._original_interface}mon")
                self._monitor_enabled = False
            except Exception as e:
                self._log.warning("monitor_mode_stop_failed", error=str(e))
        if self._finding_buffer:
            await self._flush_buffer()
