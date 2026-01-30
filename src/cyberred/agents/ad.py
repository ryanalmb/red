"""Active Directory Agent implementation (Story 7.21).

Thin subclass following the refactored agent architecture pattern.
All tool selection is LLM-driven - NO hardcoded command generation methods.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from cyberred.agents.base import StigmergicAgent
from cyberred.agents.roles import AgentRole
from cyberred.core.models import AgentAction, Finding, ToolSelectionContext
from cyberred.tools.kali_executor import kali_execute

if TYPE_CHECKING:
    from cyberred.core.event_bus import EventBus
    from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
    from cyberred.intelligence.base import IntelResult


class ADAgent(StigmergicAgent):
    """Active Directory specialist agent - thin subclass with LLM-driven tool selection."""

    INTELLIGENCE_TIMEOUT = 5.0

    def __init__(
        self, agent_id: str, engagement_id: str, event_bus: EventBus,
        specialty: str = "general", max_iterations: int = 30,
        phase_complete_threshold: int = 75,
        intel_aggregator: "CachedIntelligenceAggregator | None" = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            agent_name=f"ad-agent-{specialty}",
            agent_id=agent_id, engagement_id=engagement_id, event_bus=event_bus,
            role=AgentRole.AD, **kwargs,
        )
        self.specialty = specialty
        self.max_iterations = max_iterations
        self.phase_complete_threshold = phase_complete_threshold
        self.current_strategy = "standard"
        self._intel_aggregator = intel_aggregator
        self._domain_info: dict[str, Any] = {}
        self._discovered_users: list[str] = []
        self._discovered_spns: list[dict[str, str]] = []
        self._obtained_tickets: dict[str, str] = {}
        self._obtained_credentials: list[dict[str, Any]] = []
        self._finding_buffer: list[dict[str, Any]] = []
        self._stop_event = asyncio.Event()

    async def execute_ad_attack(
        self, domain_controller: str, context: dict[str, Any],
    ) -> tuple[list[Finding], list[AgentAction]]:
        """Execute AD attack campaign using LLM-driven tool selection."""
        findings, actions, iteration = [], [], 0
        await self._enumerate_domain(domain_controller, context.get("credentials"))

        # Query intelligence for AD/Kerberos attack techniques
        service = context.get("service", "ldap")
        version = context.get("version", "")
        intel = await self._select_intel(await self._query_intelligence(service, version))

        while not self._stop_event.is_set() and iteration < self.max_iterations:
            tool_context = self._build_tool_context(domain_controller, context, actions)
            if await self._phase_complete(tool_context):
                break
            iteration += 1
            try:
                tool_selection = await self.select_tool(tool_context)
                decision_context = self._build_decision_context(tool_selection, intel)
                result = await kali_execute(tool_selection.command)
                action = AgentAction(
                    id=str(uuid.uuid4()), agent_id=self.agent_id,
                    action_type=f"ad:{tool_selection.tool_name}",
                    target=domain_controller, timestamp=self._get_timestamp(),
                    decision_context=decision_context,
                )
                actions.append(action)
                if result.success and result.stdout:
                    findings.append(Finding(
                        id=str(uuid.uuid4()), type="ad", severity="medium",
                        target=domain_controller, evidence=result.stdout[:500], agent_id=self.agent_id,
                        timestamp=self._get_timestamp(), tool=tool_selection.tool_name,
                        topic=f"findings:{self._hash_target(domain_controller)}:ad",
                        signature=f"ad-{tool_selection.tool_name}-{iteration}",
                    ))
                await self._check_kerberos_results(result, tool_selection)
                await self._check_credential_results(result, tool_selection)
            except Exception as e:
                actions.append(AgentAction(
                    id=str(uuid.uuid4()), agent_id=self.agent_id, action_type="ad:unknown",
                    target=domain_controller, timestamp=self._get_timestamp(),
                    decision_context=[f"initial_spawn:{self.agent_id}", f"error:{e}"],
                ))
                break
        return findings, actions

    async def _query_intelligence(self, service: str = "", version: str = "") -> list["IntelResult"]:
        """Query intelligence aggregator for AD/Kerberos attack techniques."""
        if not self._intel_aggregator or not service:
            return []
        try:
            return await asyncio.wait_for(
                self._intel_aggregator.query(service, version),
                timeout=self.INTELLIGENCE_TIMEOUT
            )
        except Exception:
            return []

    async def _select_intel(self, results: list["IntelResult"] | None) -> "IntelResult | None":
        """Select highest priority intelligence result."""
        if not results:
            return None
        return sorted(results, key=lambda r: r.priority)[0]

    async def _enumerate_domain(self, domain_controller: str, credentials: dict[str, str] | None) -> None:
        """Perform initial domain enumeration."""
        try:
            cmd = f"ldapsearch -H ldap://{domain_controller} -x -b '' -s base"
            if credentials:
                cmd = f"ldapsearch -H ldap://{domain_controller} -D '{credentials.get('username', '')}' -w '{credentials.get('password', '')}' -b '' -s base"
            result = await kali_execute(cmd)
            if result.success:
                self._parse_ldap_output(result.stdout)
        except Exception as e:
            self._log.warning("enumerate_domain_failed", error=str(e))

    def _parse_ldap_output(self, output: str) -> None:
        """Parse LDAP output for domain information, users, and SPNs."""
        dc_parts = re.findall(r"DC=([^,\s]+)", output, re.IGNORECASE)
        if dc_parts:
            self._domain_info["domain_name"] = ".".join(dc_parts)
        for user in re.findall(r"sAMAccountName:\s*(\S+)", output, re.IGNORECASE):
            if user not in self._discovered_users:
                self._discovered_users.append(user)
        for spn in re.findall(r"servicePrincipalName:\s*(\S+)", output, re.IGNORECASE):
            if spn not in [s.get("spn") for s in self._discovered_spns]:
                self._discovered_spns.append({"spn": spn})

    async def _check_kerberos_results(self, result: Any, tool_selection: Any) -> None:
        """Check tool output for Kerberos tickets/hashes and publish to channel."""
        output = getattr(result, "stdout", str(result))
        if "$krb5tgs$" in output:
            for spn in re.findall(r"\$krb5tgs\$\d+\$\*([^*]+)\*", output):
                self._obtained_tickets[spn] = "tgs"
                await self._publish_kerberos_ticket(spn, output)
        if "$krb5asrep$" in output:
            for user in re.findall(r"\$krb5asrep\$\d+\$([^@]+)@", output):
                self._obtained_tickets[f"asrep:{user}"] = "asrep"
                await self._publish_kerberos_ticket(f"asrep:{user}", output)
        if "ticket" in output.lower() and ("golden" in output.lower() or "silver" in output.lower()):
            t = "golden" if "golden" in output.lower() else "silver"
            self._obtained_tickets[f"{t}:created"] = t

    async def _publish_kerberos_ticket(self, spn: str, hash_data: str) -> None:
        try:
            await self.event_bus.publish(f"credentials:{self.engagement_id}:kerberos", {"spn": spn, "hash": hash_data[:200], "agent_id": self.agent_id})
        except Exception as e:
            self._log.warning("kerberos_publish_failed", error=str(e))

    async def _check_credential_results(self, result: Any, tool_selection: Any) -> None:
        """Check tool output for credentials and publish."""
        output = getattr(result, "stdout", str(result))
        for match in re.findall(r"(\w+):(\d+):([a-fA-F0-9]{32}):([a-fA-F0-9]{32})", output):
            username, rid, lm_hash, nt_hash = match
            cred = {"username": username, "rid": rid, "lm_hash": lm_hash, "nt_hash": nt_hash, "type": "ntlm"}
            if cred not in self._obtained_credentials:
                self._obtained_credentials.append(cred)
                await self._publish_credential(cred)
            if "admin" in username.lower() or rid == "500":
                await self._publish_domain_admin_finding(self._domain_info.get("domain_name", "unknown"), username)

    async def _publish_credential(self, cred: dict[str, Any]) -> None:
        try:
            await self.event_bus.publish(f"credentials:{self.engagement_id}:ad", {"credential": cred, "agent_id": self.agent_id})
        except Exception as e:
            self._log.warning("credential_publish_failed", error=str(e))

    async def _publish_domain_admin_finding(self, domain: str, username: str) -> None:
        try:
            await self.event_bus.publish(f"findings:{self._hash_target(domain)}:domainadmin", {"domain": domain, "username": username, "agent_id": self.agent_id, "severity": "critical"})
        except Exception as e:
            self._log.warning("domain_admin_publish_failed", error=str(e))

    def _build_decision_context(self, tool_selection: Any, intel: "IntelResult | None" = None) -> list[str]:
        """Build decision context list for NFR37 compliance."""
        ctx = [f"initial_spawn:{self.agent_id}"]
        if self._domain_info.get("domain_name"):
            ctx.append(f"domain:{self._domain_info['domain_name']}")
        for spn, ticket_type in self._obtained_tickets.items():
            ctx.append(f"ticket:{ticket_type}:{spn}")
        for cred in self._obtained_credentials:
            ctx.append(f"creds:{cred.get('username', 'unknown')}")
        if intel:
            ctx.append(f"intel:{intel.source}:{intel.cve_id or 'unknown'}")
        return ctx

    def _build_tool_context(self, dc: str, context: dict[str, Any], actions: list[AgentAction]) -> ToolSelectionContext:
        return ToolSelectionContext(
            objective=f"Compromise AD domain via {dc}", phase="ad", constraints=self._get_constraints(),
            target_info={"domain_controller": dc, "domain_info": self._domain_info, "discovered_users": self._discovered_users, "discovered_spns": self._discovered_spns, **context},
            available_tools=["ldapsearch", "bloodhound-python", "enum4linux-ng", "rpcclient", "impacket-GetUserSPNs", "impacket-GetNPUsers", "impacket-getTGT", "impacket-ticketer", "impacket-secretsdump", "crackmapexec", "impacket-psexec", "impacket-wmiexec", "evil-winrm"],
            previous_results=[{"action": a.action_type, "id": a.id} for a in actions],
        )

    def _get_constraints(self) -> list[str]:
        if self.current_strategy == "stealth":
            return ["Avoid password spraying", "Prefer passive enumeration", "Use stealth techniques"]
        elif self.current_strategy == "aggressive":
            return ["All attack techniques allowed", "Password spraying permitted", "Aggressive enumeration enabled"]
        return []

    async def on_signal(self, channel: str, data: dict[str, Any]) -> None:
        if "strategies" in channel and data.get("strategy") in ("stealth", "standard", "aggressive"):
            self.current_strategy = data["strategy"]

    async def on_finding(self, finding: Finding) -> None:
        if self._finding_buffer:
            await self._flush_buffer()
        channel = f"findings:{self._hash_target(finding.target)}:ad"
        try:
            await self.event_bus.publish(channel, {"id": finding.id, "type": finding.type, "severity": finding.severity, "evidence": finding.evidence})
        except Exception:
            self._finding_buffer.append({"channel": channel, "message": {"id": finding.id}})

    async def _flush_buffer(self) -> None:
        remaining = []
        for item in self._finding_buffer:
            try:
                await self.event_bus.publish(item["channel"], item["message"])
            except Exception:
                remaining.append(item)
        self._finding_buffer = remaining

    async def stop(self) -> None:
        if self._finding_buffer:
            await self._flush_buffer()
        self._stop_event.set()

    async def _phase_complete(self, context: ToolSelectionContext) -> bool:
        return len(context.previous_results) >= self.phase_complete_threshold

    def _hash_target(self, target: str) -> str:
        """Hash target string for channel naming (8-char SHA256 prefix)."""
        return hashlib.sha256(target.encode()).hexdigest()[:8]

    def _get_timestamp(self) -> str:
        """Get current UTC timestamp in ISO format."""
        return datetime.now(UTC).isoformat()
