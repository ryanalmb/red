"""Credential Agent implementation (Story 7.22).

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
    from cyberred.core.events import EventBus


# Hash type detection patterns
HASH_PATTERNS: dict[str, tuple[str, int, str]] = {
    # pattern: (hash_type, hashcat_mode, john_format)
    "ntlm": (r"^[a-fA-F0-9]{32}$", 1000, "nt"),
    "kerberos_tgs": (r"\$krb5tgs\$\d+\$", 13100, "krb5tgs"),
    "asrep": (r"\$krb5asrep\$\d+\$", 18200, "krb5asrep"),
    "bcrypt": (r"^\$2[aby]?\$", 3200, "bcrypt"),
    "sha512crypt": (r"^\$6\$", 1800, "sha512crypt"),
    "sha256crypt": (r"^\$5\$", 7400, "sha256crypt"),
    "md5crypt": (r"^\$1\$", 500, "md5crypt"),
    "mysql": (r"^\*[A-F0-9]{40}$", 300, "mysql-sha1"),
}


class CredentialAgent(StigmergicAgent):
    """Credential harvesting and cracking agent - thin subclass with LLM-driven tool selection."""

    DEFAULT_MAX_ITERATIONS: int = 25
    DEFAULT_LOCKOUT_THRESHOLD: int = 3  # Max attempts before lockout risk
    DEFAULT_LOCKOUT_WINDOW: int = 30    # Minutes to wait between spray rounds
    DEFAULT_PHASE_COMPLETE_THRESHOLD: int = 75

    def __init__(
        self,
        agent_id: str,
        engagement_id: str,
        event_bus: EventBus,
        specialty: str = "general",
        max_iterations: int | None = None,
        lockout_threshold: int | None = None,
        lockout_window: int | None = None,
        phase_complete_threshold: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the CredentialAgent.

        Args:
            agent_id: Unique identifier for this agent instance.
            engagement_id: ID of the current engagement.
            event_bus: EventBus instance for communication.
            specialty: Agent specialty (general, harvesting, cracking, spraying).
            max_iterations: Maximum iterations per attack campaign.
            lockout_threshold: Max attempts per user before lockout risk.
            lockout_window: Minutes to wait between spray rounds.
            phase_complete_threshold: Number of results before phase considered complete.
            **kwargs: Additional arguments passed to StigmergicAgent.
        """
        super().__init__(
            agent_name=f"credential-agent-{specialty}",
            agent_id=agent_id,
            engagement_id=engagement_id,
            event_bus=event_bus,
            role=AgentRole.CREDENTIAL,
            specialty=specialty,
            **kwargs,
        )
        self.specialty = specialty
        self.max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
        self.lockout_threshold = lockout_threshold or self.DEFAULT_LOCKOUT_THRESHOLD
        self.lockout_window = lockout_window or self.DEFAULT_LOCKOUT_WINDOW
        self.phase_complete_threshold = phase_complete_threshold or self.DEFAULT_PHASE_COMPLETE_THRESHOLD
        self.current_strategy = "standard"
        self._cracked_credentials: list[dict[str, Any]] = []
        self._harvested_credentials: list[dict[str, Any]] = []
        self._pending_hashes: list[dict[str, Any]] = []
        self._finding_buffer: list[dict[str, Any]] = []
        self._stop_event = asyncio.Event()

    async def execute_credential_attack(
        self, target: str, context: dict[str, Any]
    ) -> tuple[list[Finding], list[AgentAction]]:
        """Execute LLM-driven credential attack campaign.

        Args:
            target: Target host/service for credential attacks.
            context: Attack context (hash_type, hashes, users, service, etc.).

        Returns:
            Tuple of (findings, actions) from the attack campaign.
        """
        findings: list[Finding] = []
        actions: list[AgentAction] = []

        if self._stop_event.is_set():
            return findings, actions

        tool_context = self._build_tool_context(target, context, actions)

        for _iteration in range(self.max_iterations):
            if self._stop_event.is_set():
                break

            if await self._phase_complete(tool_context):
                break

            decision_context = self._build_decision_context(context)
            action_id = str(uuid.uuid4())
            result_finding_id: str | None = None
            tool_name = "unknown"

            try:
                selection = await self.select_tool(tool_context)
                tool_name = selection.tool_name
                result = await kali_execute(selection.command)

                if result.success and result.stdout:
                    finding = self._create_finding(target, selection, result)
                    findings.append(finding)
                    await self.on_finding(finding)
                    result_finding_id = finding.id

                    # Check for cracked credentials in output
                    await self._check_cracked_results(result, selection)

                # Update context with results
                tool_context = self._build_tool_context(target, context, actions)

            except Exception as e:
                self._log.error("credential_iteration_error", error=str(e))
                actions.append(AgentAction(
                    id=action_id,
                    agent_id=self.agent_id,
                    action_type="credential:unknown",
                    target=target,
                    timestamp=self._get_timestamp(),
                    decision_context=[f"initial_spawn:{self.agent_id}", f"error:{e}"],
                ))
                break

            actions.append(AgentAction(
                id=action_id,
                agent_id=self.agent_id,
                action_type=f"credential:{tool_name}",
                target=target,
                timestamp=self._get_timestamp(),
                decision_context=decision_context,
                result_finding_id=result_finding_id,
            ))

        return findings, actions

    def _build_decision_context(self, context: dict[str, Any]) -> list[str]:
        """Build decision context list for NFR37 compliance."""
        ctx = [f"initial_spawn:{self.agent_id}"]

        # Add hash type context
        if context.get("hash_type"):
            ctx.append(f"hash_type:{context['hash_type']}")

        # Add service context
        if context.get("service"):
            ctx.append(f"service:{context['service']}")

        # Add cracked credentials context
        for cred in self._cracked_credentials:
            ctx.append(f"cracked:{cred.get('username', 'unknown')}")

        return ctx

    def _build_tool_context(
        self, target: str, context: dict[str, Any], actions: list[AgentAction]
    ) -> ToolSelectionContext:
        """Build tool selection context for LLM."""
        return ToolSelectionContext(
            objective=f"Compromise credentials on {target}",
            phase="credential",
            constraints=self._get_constraints(),
            target_info={
                "target": target,
                "hash_type": context.get("hash_type"),
                "hashes": context.get("hashes", []),
                "users": context.get("users", []),
                "service": context.get("service"),
                "strategy": self.current_strategy,
                **context
            },
            available_tools=[
                "hashcat", "john", "hydra", "crackmapexec", "kerbrute", "spray",
                "mimikatz", "impacket-secretsdump", "lsassy", "responder",
                "ntlmrelayx", "hashid"
            ],
            previous_results=[{"action": a.action_type, "id": a.id} for a in actions],
        )

    def _get_constraints(self) -> list[str]:
        """Get constraints based on current strategy."""
        if self.current_strategy == "stealth":
            return [
                "Limit password spraying to 1 attempt per user",
                "Prefer offline cracking over online attacks",
                "Avoid triggering account lockouts",
                "Use stealth techniques"
            ]
        elif self.current_strategy == "aggressive":
            return [
                "Full password spraying allowed",
                "All attack techniques permitted",
                "Aggressive wordlist combinations enabled"
            ]
        return []

    def _create_finding(self, target: str, selection: Any, result: Any) -> Finding:
        """Create a Finding from tool execution result."""
        return Finding(
            id=str(uuid.uuid4()),
            type="credential",
            severity="high",
            target=target,
            evidence=result.stdout[:500] if result.stdout else "",
            agent_id=self.agent_id,
            timestamp=self._get_timestamp(),
            tool=selection.tool_name,
            topic=f"findings:{self._hash_target(target)}:credential",
            signature=f"credential-{selection.tool_name}-{uuid.uuid4().hex[:8]}",
        )

    # === Hash Detection and Cracking Methods ===

    def _detect_hash_type(self, hash_value: str) -> str:
        """Detect hash type from hash string."""
        for hash_type, (pattern, _, _) in HASH_PATTERNS.items():
            if re.search(pattern, hash_value):
                return hash_type
        return "unknown"

    def _get_hashcat_mode(self, hash_type: str) -> int:
        """Get hashcat mode for hash type."""
        for ht, (_, mode, _) in HASH_PATTERNS.items():
            if ht == hash_type:
                return mode
        return 0

    def _get_john_format(self, hash_type: str) -> str:
        """Get john format for hash type."""
        for ht, (_, _, fmt) in HASH_PATTERNS.items():
            if ht == hash_type:
                return fmt
        return "raw"

    async def _crack_hashes(
        self, hashes: list[str], hash_type: str
    ) -> list[dict[str, Any]]:
        """Crack hashes using appropriate tool.

        Args:
            hashes: List of hash strings to crack.
            hash_type: Type of hash (ntlm, kerberos_tgs, etc.).

        Returns:
            List of cracked credentials.
        """
        cracked: list[dict[str, Any]] = []

        try:
            mode = self._get_hashcat_mode(hash_type)
            tool_context = ToolSelectionContext(
                objective=f"Crack {hash_type} hashes",
                phase="credential",
                constraints=self._get_constraints(),
                target_info={"hashes": hashes, "hash_type": hash_type, "mode": mode},
                available_tools=["hashcat", "john"],
                previous_results=[],
            )

            selection = await self.select_tool(tool_context)
            result = await kali_execute(selection.command)

            if result.success and result.stdout:
                # Parse cracked passwords from output
                for line in result.stdout.split("\n"):
                    if ":" in line:
                        parts = line.strip().split(":")
                        if len(parts) >= 2:
                            cred = {"hash": parts[0], "password": parts[1], "hash_type": hash_type}
                            cracked.append(cred)
                            self._cracked_credentials.append(cred)
                            await self._publish_cracked_credential(cred)

        except Exception as e:
            self._log.error("crack_hashes_error", error=str(e))

        return cracked

    async def _check_cracked_results(self, result: Any, selection: Any) -> None:
        """Check tool output for cracked credentials."""
        output = getattr(result, "stdout", str(result))

        # Look for common cracked credential patterns
        # hydra format: [port][service] host: X login: Y password: Z
        for match in re.finditer(r"login:\s*(\S+)\s+password:\s*(\S+)", output, re.IGNORECASE):
            cred = {"username": match.group(1), "password": match.group(2), "source": selection.tool_name}
            if cred not in self._cracked_credentials:
                self._cracked_credentials.append(cred)
                await self._publish_cracked_credential(cred)

        # hashcat/john format: hash:password
        for match in re.finditer(r"([a-fA-F0-9]{32}):(\S+)", output):
            cred = {"hash": match.group(1), "password": match.group(2), "source": selection.tool_name}
            if cred not in self._cracked_credentials:
                self._cracked_credentials.append(cred)
                await self._publish_cracked_credential(cred)

    # === Password Spraying Methods ===

    async def _execute_password_spray(
        self, target: str, users: list[str], passwords: list[str]
    ) -> list[dict[str, Any]]:
        """Execute password spraying attack with lockout awareness.

        Args:
            target: Target service endpoint.
            users: List of usernames to spray.
            passwords: List of passwords to try.

        Returns:
            List of successful credentials.
        """
        successful: list[dict[str, Any]] = []

        try:
            tool_context = ToolSelectionContext(
                objective=f"Password spray against {target}",
                phase="credential",
                constraints=self._get_constraints(),
                target_info={
                    "target": target,
                    "users": users,
                    "passwords": passwords,
                    "lockout_threshold": self.lockout_threshold
                },
                available_tools=["hydra", "crackmapexec", "kerbrute", "spray"],
                previous_results=[],
            )

            selection = await self.select_tool(tool_context)
            result = await kali_execute(selection.command)

            if result.success and result.stdout:
                # Check for lockout indicators
                if "locked" in result.stdout.lower():
                    self._log.warning("account_lockout_detected", target=target)
                    return successful

                # Parse successful logins
                await self._check_cracked_results(result, selection)
                successful = [c for c in self._cracked_credentials if c.get("source") == selection.tool_name]

        except Exception as e:
            self._log.error("password_spray_error", error=str(e))

        return successful

    # === Credential Harvesting Methods ===

    async def _harvest_credentials(
        self, target: str, access_type: str
    ) -> list[dict[str, Any]]:
        """Harvest credentials from compromised system.

        Args:
            target: Target system.
            access_type: Type of access (windows, linux, web).

        Returns:
            List of harvested credentials.
        """
        harvested: list[dict[str, Any]] = []

        try:
            tool_context = ToolSelectionContext(
                objective=f"Harvest credentials from {access_type} system {target}",
                phase="credential",
                constraints=self._get_constraints(),
                target_info={"target": target, "access_type": access_type},
                available_tools=self._get_harvest_tools(access_type),
                previous_results=[],
            )

            selection = await self.select_tool(tool_context)
            result = await kali_execute(selection.command)

            if result.success and result.stdout:
                # Parse harvested credentials based on access type
                creds = self._parse_harvested_output(result.stdout, access_type)
                for cred in creds:
                    cred["source"] = selection.tool_name
                    cred["access_type"] = access_type
                    harvested.append(cred)
                    self._harvested_credentials.append(cred)

        except Exception as e:
            self._log.error("harvest_credentials_error", error=str(e))

        return harvested

    def _get_harvest_tools(self, access_type: str) -> list[str]:
        """Get appropriate harvesting tools for access type."""
        tools_map = {
            "windows": ["mimikatz", "impacket-secretsdump", "lsassy"],
            "linux": ["cat", "find", "grep"],
            "web": ["grep", "find", "strings"],
        }
        return tools_map.get(access_type, ["grep", "find"])

    def _parse_harvested_output(self, output: str, access_type: str) -> list[dict[str, Any]]:
        """Parse harvested credential output."""
        creds: list[dict[str, Any]] = []

        if access_type == "windows":
            # Parse NTLM hashes: username:rid:lm_hash:nt_hash
            for match in re.finditer(r"(\w+):(\d+):([a-fA-F0-9]{32}):([a-fA-F0-9]{32})", output):
                creds.append({
                    "username": match.group(1),
                    "rid": match.group(2),
                    "lm_hash": match.group(3),
                    "nt_hash": match.group(4),
                    "type": "ntlm"
                })
            # Parse mimikatz output
            for match in re.finditer(r"Username:\s*(\S+).*?NTLM:\s*([a-fA-F0-9]+)", output, re.DOTALL):
                creds.append({"username": match.group(1), "ntlm": match.group(2), "type": "mimikatz"})

        elif access_type == "linux":
            # Parse shadow file entries
            for match in re.finditer(r"^(\w+):(\$\d\$[^:]+):", output, re.MULTILINE):
                creds.append({"username": match.group(1), "hash": match.group(2), "type": "shadow"})
            # Parse SSH key paths
            for match in re.finditer(r"(/[\w/]+/\.ssh/id_\w+)", output):
                creds.append({"path": match.group(1), "type": "ssh_key"})

        elif access_type == "web":
            # Parse config file passwords
            for match in re.finditer(r"password['\"]?\s*[:=]\s*['\"]?(\S+)['\"]?", output, re.IGNORECASE):
                creds.append({"password": match.group(1), "type": "config"})

        return creds

    # === Stigmergic Communication Methods ===

    async def _publish_cracked_credential(self, credential: dict[str, Any]) -> None:
        """Publish cracked credential to stigmergic channel."""
        try:
            channel = f"credentials:{self.engagement_id}:cracked"
            await self.event_bus.publish(channel, {
                "credential": credential,
                "agent_id": self.agent_id,
            })
        except Exception as e:
            self._log.warning("credential_publish_failed", error=str(e))

    async def _setup_credential_subscriptions(self) -> None:
        """Subscribe to credential channels from other agents."""
        await self.event_bus.subscribe(
            f"credentials:{self.engagement_id}:*",
            self._handle_message
        )

    async def on_signal(self, channel: str, data: dict[str, Any]) -> None:
        """Handle incoming stigmergic signal."""
        # Handle strategy updates
        if "strategies" in channel and data.get("strategy") in ("stealth", "standard", "aggressive"):
            self.current_strategy = data["strategy"]
            return

        # Handle incoming hashes from other agents
        if (
            "credentials" in channel
            and channel != f"credentials:{self.engagement_id}:cracked"
            and data.get("hash")
        ):
            self._pending_hashes.append({
                "hash": data["hash"],
                "hash_type": data.get("hash_type", "unknown"),
                "source_agent": data.get("agent_id"),
                "spn": data.get("spn"),
            })

    async def on_finding(self, finding: Finding) -> None:
        """Publish finding to credential channel."""
        if self._finding_buffer:
            await self._flush_buffer()

        channel = f"findings:{self._hash_target(finding.target)}:credential"
        try:
            await self.event_bus.publish(channel, {
                "id": finding.id,
                "type": finding.type,
                "severity": finding.severity,
                "evidence": finding.evidence,
            })
        except Exception:
            self._finding_buffer.append({"channel": channel, "message": {"id": finding.id}})

    async def _flush_buffer(self) -> None:
        """Flush buffered findings on reconnect."""
        remaining = []
        for item in self._finding_buffer:
            try:
                await self.event_bus.publish(item["channel"], item["message"])
            except Exception:
                remaining.append(item)
        self._finding_buffer = remaining

    async def stop(self) -> None:
        """Stop the agent gracefully."""
        if self._finding_buffer:
            await self._flush_buffer()
        self._stop_event.set()

    async def _phase_complete(self, context: ToolSelectionContext) -> bool:
        """Check if credential attack phase is complete."""
        return len(context.previous_results) >= self.phase_complete_threshold

    def _hash_target(self, target: str) -> str:
        """Hash target string for channel naming (8-char SHA256 prefix)."""
        return hashlib.sha256(target.encode()).hexdigest()[:8]

    def _get_timestamp(self) -> str:
        """Get current UTC timestamp in ISO format."""
        return datetime.now(UTC).isoformat()
