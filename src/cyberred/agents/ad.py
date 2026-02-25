"""Active Directory Agent implementation (Story 7.21).

Thin subclass following the refactored agent architecture pattern.
All tool selection is LLM-driven - NO hardcoded command generation methods.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from collections import deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from cyberred.agents.base import StigmergicAgent
from cyberred.agents.roles import AgentRole
from cyberred.core.exceptions import ScopeViolationError
from cyberred.core.finding_policy import assess_finding_payload
from cyberred.core.models import AgentAction, Finding, ToolSelectionContext
from cyberred.tools.kali_executor import kali_execute

if TYPE_CHECKING:
    from cyberred.agents.rag_escalator import AgentRAGEscalator
    from cyberred.core.event_bus import EventBus
    from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
    from cyberred.intelligence.base import IntelResult


class ADAgent(StigmergicAgent):
    """Active Directory specialist agent - thin subclass with LLM-driven tool selection."""

    INTELLIGENCE_TIMEOUT = 5.0

    def __init__(
        self, agent_id: str, engagement_id: str, event_bus: EventBus,
        specialty: str = "general", max_iterations: int = 2,
        phase_complete_threshold: int = 75,
        intel_aggregator: "CachedIntelligenceAggregator | None" = None,
        rag_escalator: "AgentRAGEscalator | None" = None,
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
        self._rag_escalator = rag_escalator
        self._failure_counts: dict[str, int] = {}
        self._current_target: str = ""
        self._current_service: str = ""
        self._domain_info: dict[str, Any] = {}
        self._discovered_users: deque[str] = deque(maxlen=500)
        self._discovered_spns: deque[dict[str, str]] = deque(maxlen=500)
        self._obtained_tickets: dict[str, str] = {}
        self._obtained_credentials: deque[dict[str, Any]] = deque(maxlen=500)
        self._finding_buffer: list[dict[str, Any]] = []
        self._stop_event = asyncio.Event()

    async def execute_ad_attack(
        self, domain_controller: str, context: dict[str, Any],
    ) -> tuple[list[Finding], list[AgentAction]]:
        """Execute AD attack campaign using LLM-driven tool selection."""
        findings, actions, iteration = [], [], 0
        self._current_target = domain_controller
        self._current_service = context.get("service", "ldap")
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
            tool_name = "unknown"
            decision_context = [f"initial_spawn:{self.agent_id}"]
            iteration_findings = 0
            try:
                tool_selection = await self.select_tool(tool_context)
                tool_name = tool_selection.tool_name
                decision_context = self._build_decision_context(tool_selection, intel)
                result = await self._kali_execute_and_publish(tool_selection.command, tool_selection.tool_name)
                action = AgentAction(
                    id=str(uuid.uuid4()), agent_id=self.agent_id,
                    action_type=f"ad:{tool_selection.tool_name}",
                    target=domain_controller, timestamp=self._get_timestamp(),
                    decision_context=decision_context,
                )
                actions.append(action)
                if result.success and result.stdout:
                    execution = self._execution_metadata(result, tool_selection.command)
                    evidence_payload: dict[str, Any] = {
                        "raw_evidence": result.stdout[:1000],
                        "command": tool_selection.command,
                        "execution": execution,
                        "domain": self._domain_info.get("domain_name"),
                    }
                    assessment = assess_finding_payload(
                        {
                            "type": "ad",
                            "severity": "medium",
                            "target": domain_controller,
                            "tool": tool_selection.tool_name,
                            "evidence": evidence_payload,
                            "execution": execution,
                        }
                    )
                    evidence_payload["validation"] = assessment
                    if assessment["outcome_status"] != "failed":
                        finding = Finding(
                            id=str(uuid.uuid4()), type="ad", severity=assessment["severity"],
                            target=domain_controller, evidence=json.dumps(evidence_payload), agent_id=self.agent_id,
                            timestamp=self._get_timestamp(), tool=tool_selection.tool_name,
                            topic=f"findings:{self._hash_target(domain_controller)}:ad",
                            signature=f"ad-{tool_selection.tool_name}-{iteration}",
                        )
                        findings.append(finding)
                        await self.on_finding(finding)
                        iteration_findings += 1
                    else:
                        alt = await self._handle_ad_failure(tool_selection.tool_name)
                        if alt:
                            decision_context.append(f"rag_escalation:{tool_selection.tool_name}:{alt}")
                elif not result.success:
                    alt = await self._handle_ad_failure(tool_selection.tool_name)
                    if alt:
                        decision_context.append(f"rag_escalation:{tool_selection.tool_name}:{alt}")
                await self._check_kerberos_results(result, tool_selection)
                await self._check_credential_results(result, tool_selection)
            except ScopeViolationError as e:
                self._log.warning(
                    "ad_scope_blocked",
                    error=str(e),
                    scope_rule=e.scope_rule,
                    iteration=iteration,
                    tool=tool_name,
                )
                actions.append(AgentAction(
                    id=str(uuid.uuid4()), agent_id=self.agent_id, action_type="ad:scope_blocked",
                    target=domain_controller, timestamp=self._get_timestamp(),
                    decision_context=decision_context + [f"scope_blocked:{e.scope_rule}"],
                ))
            except Exception as e:
                self._log.error("ad_iteration_error", error=str(e), iteration=iteration, tool=tool_name)
                actions.append(AgentAction(
                    id=str(uuid.uuid4()), agent_id=self.agent_id, action_type=f"ad:{tool_name}",
                    target=domain_controller, timestamp=self._get_timestamp(),
                    decision_context=decision_context + [f"error:{type(e).__name__}:{e}"],
                ))

            streak = self._record_iteration_findings(iteration_findings)
            if streak >= self._no_finding_streak_threshold:
                decision_context.append(f"yield_streak:{streak}")
                alt = await self._handle_ad_failure("yield_no_finding")
                if alt:
                    decision_context.append(f"rag_escalation:yield_no_finding:{alt}")
                await self._publish_swarm_log(
                    "YIELD_GUARD",
                    "AD no-yield streak triggered escalation",
                    role="ad",
                    tool=tool_name,
                    target=domain_controller,
                    streak=streak,
                    agent_id=str(self.agent_id),
                )
        return findings, actions

    async def _query_intelligence(self, service: str = "", version: str = "") -> list["IntelResult"]:
        """Query intelligence aggregator for AD/Kerberos attack techniques."""
        if not self._intel_aggregator:
            return []
        query_service = (service or self._current_service or "ldap").strip()
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

    async def _enumerate_domain(self, domain_controller: str, credentials: dict[str, str] | None) -> None:
        """Perform initial domain enumeration."""
        try:
            cmd = f"ldapsearch -H ldap://{domain_controller} -x -b '' -s base"
            if credentials:
                cmd = f"ldapsearch -H ldap://{domain_controller} -D '{credentials.get('username', '')}' -w '{credentials.get('password', '')}' -b '' -s base"
            result = await self._kali_execute_and_publish(cmd, "ldapsearch")
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
            target_hash = self._hash_target(domain)
            await self._publish_to_swarm(
                target_hash,
                "domainadmin",
                {
                    "target": domain,
                    "type": "domainadmin",
                    "severity": "critical",
                    "domain": domain,
                    "username": username,
                    "evidence": f"domain admin credential candidate: {username}@{domain}",
                    "tool": "adagent",
                    "outcome_status": "validated",
                    "validation_reason": "credential_pattern_matched",
                },
            )
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
        discovered_users = list(self._discovered_users)
        discovered_spns = list(self._discovered_spns)
        previous_results = self.get_recent_tool_results(limit=30)
        if not previous_results and actions:
            previous_results = [
                {
                    "id": action.id,
                    "action": action.action_type,
                    "target": action.target,
                    "timestamp": action.timestamp,
                }
                for action in actions[-30:]
            ]
        return ToolSelectionContext(
            objective=f"Compromise AD domain via {dc}", phase="ad", constraints=self._get_constraints(),
            target_info={
                "domain_controller": dc,
                "domain_info": self._domain_info,
                "discovered_users": discovered_users,
                "discovered_spns": discovered_spns,
                **context,
            },
            available_tools=["ldapsearch", "bloodhound-python", "enum4linux-ng", "rpcclient", "impacket-GetUserSPNs", "impacket-GetNPUsers", "impacket-getTGT", "impacket-ticketer", "impacket-secretsdump", "crackmapexec", "impacket-psexec", "impacket-wmiexec", "evil-winrm"],
            previous_results=previous_results,
        )

    async def _handle_ad_failure(self, technique_id: str) -> str | None:
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
                target_service=self._current_service or "active directory",
                target_hash=target_hash,
                failed_techniques=tuple(t for t, c in self._failure_counts.items() if c >= 3),
                failure_count=failure_count,
                environment={"target": self._current_target, "domain": self._domain_info.get("domain_name", "")},
                engagement_id=self.engagement_id,
            )
            try:
                rag_result = await self._rag_escalator.escalate(context)
                if rag_result.was_successful:
                    return rag_result.selected_technique
            except Exception:
                pass
        return None

    def _get_constraints(self) -> list[str]:
        constraints: list[str] = []
        if self.current_strategy == "stealth":
            constraints.extend(
                ["Avoid password spraying", "Prefer passive enumeration", "Use stealth techniques"]
            )
        elif self.current_strategy == "aggressive":
            constraints.extend(
                ["All attack techniques allowed", "Password spraying permitted", "Aggressive enumeration enabled"]
            )

        if self._no_finding_streak >= 2:
            constraints.append("switch technique family from recent no-yield AD attempts")
        if self._no_finding_streak >= self._no_finding_streak_threshold:
            constraints.append("prioritize materially different AD pathways and targets")
        return constraints

    async def on_signal(self, channel: str, data: dict[str, Any]) -> None:
        await super().on_signal(channel, data)
        if "strategies" in channel and data.get("strategy") in ("stealth", "standard", "aggressive"):
            self.current_strategy = data["strategy"]

    async def on_finding(self, finding: Finding) -> None:
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
            await self._publish_to_swarm(target_hash, "ad", message)
        except Exception:
            self._buffer_finding_retry(
                self._finding_buffer,
                target_hash=target_hash,
                finding_type="ad",
                message=message,
            )

    async def _flush_buffer(self) -> None:
        self._finding_buffer = await self._flush_buffered_findings(self._finding_buffer)

    async def stop(self) -> None:
        if self._finding_buffer:
            await self._flush_buffer()
        self._stop_event.set()

    async def _phase_complete(self, context: ToolSelectionContext) -> bool:
        return len(context.previous_results) >= self.phase_complete_threshold

    def _hash_target(self, target: str) -> str:
        """Hash target string for channel naming (8-char MD5 prefix)."""
        return hashlib.md5(target.encode()).hexdigest()[:8]

    def _get_timestamp(self) -> str:
        """Get current UTC timestamp in ISO format."""
        return datetime.now(UTC).isoformat()
