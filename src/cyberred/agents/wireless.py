"""WirelessAgent - LLM-driven wireless network testing agent (Story 7.20)."""
import asyncio
import hashlib
import uuid
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
    from cyberred.llm.gateway import LLMGateway
    from cyberred.tools.manifest import ManifestLoader

log = structlog.get_logger().bind(component="wireless_agent")
DEFAULT_HMAC_KEY = b"cyber-red-wireless-agent-key-v1"


class WirelessAgent(StigmergicAgent):
    """LLM-driven wireless network testing agent - thin subclass setting role=WIRELESS."""

    DEFAULT_MAX_ITERATIONS: int = 20
    DEFAULT_PHASE_COMPLETE_THRESHOLD: int = 15

    def __init__(self, agent_id: str, engagement_id: str, event_bus: EventBus,
                 specialty: str = "general", llm_gateway: "LLMGateway | None" = None,
                 manifest_loader: "ManifestLoader | None" = None, max_iterations: int | None = None,
                 phase_complete_threshold: int | None = None,
                 hmac_key: bytes = DEFAULT_HMAC_KEY, **kwargs: Any) -> None:
        super().__init__(agent_name="WirelessAgent", agent_id=agent_id, engagement_id=engagement_id,
                         event_bus=event_bus, role=AgentRole.WIRELESS, specialty=specialty,
                         llm_gateway=llm_gateway, manifest_loader=manifest_loader, **kwargs)
        self._log = log.bind(agent_id=agent_id, engagement_id=engagement_id)
        self._hmac_key = hmac_key
        self.max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
        self.phase_complete_threshold = phase_complete_threshold or self.DEFAULT_PHASE_COMPLETE_THRESHOLD
        self.current_strategy, self._finding_buffer = "standard", []
        self._stop_event = asyncio.Event()
        self._monitor_enabled: bool = False
        self._original_interface: str | None = None
        self._discovered_networks: list[dict[str, Any]] = []
        self._captured_handshakes: dict[str, str] = {}  # bssid -> path

    async def execute_wireless_scan(
        self, interface: str, target_info: dict[str, Any]
    ) -> tuple[list[Finding], list[AgentAction]]:
        """Execute LLM-driven wireless network scan."""
        if self._stop_event.is_set():
            return [], []

        await self._enable_monitor_mode(interface)

        all_findings: list[Finding] = []
        all_actions: list[AgentAction] = []

        context = ToolSelectionContext(
            objective="Discover and test wireless networks for vulnerabilities",
            target_info={"interface": interface, "phase": "wireless", "strategy": self.current_strategy,
                         "monitor_enabled": self._monitor_enabled,
                         "discovered_networks": self._discovered_networks, **target_info},
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

            action_id = str(uuid.uuid4())
            result_finding_id: str | None = None
            tool_name = "unknown"

            try:
                selection = await self.select_tool(context)
                tool_name = selection.tool_name
                self._log.info("executing_tool", tool=tool_name, command=selection.command[:80])
                result = await kali_execute(selection.command)

                if result.success and result.stdout:
                    finding = self._create_finding(interface, selection, result)
                    all_findings.append(finding)
                    await self.on_finding(finding)
                    result_finding_id = finding.id
                    await self._check_handshake_capture(result, selection)

                context = ToolSelectionContext(
                    objective=context.objective,
                    target_info={**context.target_info, "discovered_networks": self._discovered_networks},
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

    def _create_finding(self, interface: str, selection: Any, result: Any) -> Finding:
        finding_data = {
            "id": str(uuid.uuid4()), "target": interface, "type": "wireless",
            "tool": selection.tool_name, "severity": "medium",
            "timestamp": datetime.now(UTC).isoformat(),
            "agent_id": str(self.agent_id),
            "topic": f"findings:{self._hash_target(interface)}:wireless",
            "evidence": result.stdout[:2000] if result.stdout else "",
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
        channel = f"findings:{self._hash_target(finding.target)}:wireless"
        message = asdict(finding) if hasattr(finding, "__dataclass_fields__") else finding.model_dump()
        if self._finding_buffer:
            await self._flush_buffer()
        try:
            await self.event_bus.publish(channel, message)
        except Exception:
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
