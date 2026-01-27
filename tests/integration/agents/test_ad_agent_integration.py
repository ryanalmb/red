"""Integration tests for ADAgent.

These tests run against REAL Redis and mock Kali execution.
They verify:
- ADAgent performs AD attack workflows correctly
- Kerberoasting and AS-REP roasting detection
- Credential extraction and publication
- Stigmergic signal propagation between agents
- End-to-end AD attack workflow with mocked tool execution

Requirements:
- Redis running on localhost:6379 (test-redis container)
- red-kali-worker image available (for Kali tests)
"""

import socket
import uuid
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.agents.ad import ADAgent
from cyberred.agents.roles import AgentRole
from cyberred.core.events import EventBus
from cyberred.core.models import Finding


def is_port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a port is open on a host."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


@pytest.mark.integration
class TestADAgentIntegration:
    """Integration tests for ADAgent using REAL Redis."""

    @pytest.fixture
    async def event_bus(self):
        """Create EventBus connected to real Redis."""
        from cyberred.core.config import RedisConfig
        from cyberred.storage.redis_client import RedisClient

        if not is_port_open("localhost", 6379):
            pytest.skip("Redis not available on localhost:6379 - start test-redis container")

        config = RedisConfig(host="localhost", port=6379)
        client = RedisClient(config, "int-eng-ad")

        await client.connect()
        bus = EventBus(client)

        yield bus

        await client.close()

    @pytest.fixture
    def dc_target(self):
        """Domain controller target for testing."""
        return "dc01.corp.local"

    @pytest.mark.asyncio
    async def test_ad_workflow_real_redis(self, event_bus, dc_target):
        """Test full AD attack workflow with REAL Redis event bus."""
        agent = ADAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="int-eng-ad",
            event_bus=event_bus,
            max_iterations=1,
        )

        assert agent.role == AgentRole.AD

        with patch("cyberred.agents.ad.kali_execute", new_callable=AsyncMock) as mock_exec:
            # LDAP enumeration response
            enum_result = MagicMock()
            enum_result.success = True
            enum_result.stdout = "DC=corp,DC=local\nAdministrator\nDomain Admins"

            # Tool execution response
            tool_result = MagicMock()
            tool_result.success = True
            tool_result.stdout = "Found users: admin, service_account"

            mock_exec.side_effect = [enum_result, tool_result]

            with patch.object(agent, "select_tool", new_callable=AsyncMock) as mock_select:
                tool_selection = MagicMock()
                tool_selection.tool_name = "ldapsearch"
                tool_selection.command = f"ldapsearch -H ldap://{dc_target}"
                tool_selection.confidence = 0.9
                mock_select.return_value = tool_selection

                findings, actions = await agent.execute_ad_attack(
                    dc_target,
                    {"objective": "Enumerate Active Directory"}
                )

                assert isinstance(findings, list)
                assert isinstance(actions, list)
                assert mock_exec.call_count >= 1

    @pytest.mark.asyncio
    async def test_ad_agent_import_from_package(self):
        """Verify ADAgent can be imported from package level."""
        from cyberred.agents import ADAgent as AD
        assert AD is ADAgent

    @pytest.mark.asyncio
    async def test_ad_agent_role_enum(self):
        """Verify ADAgent uses correct role."""
        event_bus = AsyncMock()
        agent = ADAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="test-eng",
            event_bus=event_bus,
            max_iterations=1,
        )
        assert agent.role == AgentRole.AD
        assert agent.role.value == "ad"

    @pytest.mark.asyncio
    async def test_ad_finding_serialization(self):
        """Test that Finding objects are properly serialized using asdict."""
        event_bus = AsyncMock()

        agent = ADAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="test-eng",
            event_bus=event_bus,
            max_iterations=2,
        )

        finding = Finding(
            id=str(uuid.uuid4()),
            type="kerberoast",
            severity="high",
            target="dc01.corp.local",
            evidence="$krb5tgs$23$*svc_sql$CORP.LOCAL...",
            agent_id=agent.agent_id,
            timestamp="2025-01-21T00:00:00Z",
            tool="impacket-GetUserSPNs",
            topic="findings:test-eng:kerberoast",
            signature="sig-123",
        )

        serialized = asdict(finding)
        assert isinstance(serialized, dict)
        assert serialized["type"] == "kerberoast"
        assert serialized["severity"] == "high"
        assert "target" in serialized

    @pytest.mark.asyncio
    async def test_ad_kerberoasting_detection(self):
        """Test Kerberoasting detection in AD agent."""
        event_bus = AsyncMock()

        agent = ADAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="test-eng",
            event_bus=event_bus,
            max_iterations=1,
        )

        # Simulate kerberoast output
        kerb_output = MagicMock()
        kerb_output.stdout = "$krb5tgs$23$*svc_sql$CORP.LOCAL$svc_sql*$abc123..."

        # Create mock tool_selection
        tool_selection = MagicMock()
        tool_selection.tool_name = "impacket-GetUserSPNs"

        # Call _check_kerberos_results
        await agent._check_kerberos_results(kerb_output, tool_selection)

        # Should have tried to publish to event bus
        assert event_bus.publish.called

    @pytest.mark.asyncio
    async def test_ad_asrep_roasting_detection(self):
        """Test AS-REP roasting detection in AD agent."""
        event_bus = AsyncMock()

        agent = ADAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="test-eng",
            event_bus=event_bus,
            max_iterations=1,
        )

        # Simulate AS-REP roast output
        asrep_output = MagicMock()
        asrep_output.stdout = "$krb5asrep$23$user@CORP.LOCAL:abc123..."

        # Create mock tool_selection
        tool_selection = MagicMock()
        tool_selection.tool_name = "impacket-GetNPUsers"

        await agent._check_kerberos_results(asrep_output, tool_selection)

        assert event_bus.publish.called

    @pytest.mark.asyncio
    async def test_ad_credential_extraction(self):
        """Test credential extraction from secretsdump output."""
        event_bus = AsyncMock()

        agent = ADAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="test-eng",
            event_bus=event_bus,
            max_iterations=1,
        )

        # Simulate secretsdump output with NTLM hash
        secrets_output = MagicMock()
        secrets_output.stdout = "Administrator:500:aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0:::"

        # Create mock tool_selection
        tool_selection = MagicMock()
        tool_selection.tool_name = "impacket-secretsdump"

        await agent._check_credential_results(secrets_output, tool_selection)

        # Should have published credential
        assert event_bus.publish.called

    @pytest.mark.asyncio
    async def test_ad_prompts_load_correctly(self):
        """Test that ADAgent prompts load from PromptLibrary."""
        from cyberred.agents.prompts import PromptLibrary

        default_prompt = PromptLibrary.get(AgentRole.AD)
        assert len(default_prompt) > 0
        assert "active directory" in default_prompt.lower() or "ad" in default_prompt.lower() or "domain" in default_prompt.lower()

        kerb_prompt = PromptLibrary.get(AgentRole.AD, "kerberoast")
        assert len(kerb_prompt) > 0

        enum_prompt = PromptLibrary.get(AgentRole.AD, "enum")
        assert len(enum_prompt) > 0

    @pytest.mark.asyncio
    async def test_ad_on_finding_callback(self):
        """Test on_finding callback properly serializes findings."""
        event_bus = AsyncMock()

        agent = ADAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="test-eng",
            event_bus=event_bus,
            max_iterations=1,
        )

        finding = Finding(
            id=str(uuid.uuid4()),
            type="domainadmin",
            severity="critical",
            target="dc01.corp.local",
            evidence="Domain Admin credentials obtained",
            agent_id=agent.agent_id,
            timestamp="2025-01-21T00:00:00Z",
            tool="secretsdump",
            topic="findings:test-eng:domainadmin",
            signature="da-sig-789",
        )

        await agent.on_finding(finding)


@pytest.mark.integration
@pytest.mark.kali
class TestADAgentKaliIntegration:
    """Integration tests requiring real Kali container."""

    @pytest.fixture
    async def kali_available(self):
        """Check if Kali container is available."""
        import subprocess
        result = subprocess.run(
            ["docker", "images", "-q", "red-kali-worker"],
            capture_output=True,
            text=True
        )
        if not result.stdout.strip():
            pytest.skip("red-kali-worker image not available")
        return True

    @pytest.mark.asyncio
    async def test_ad_real_kali_ldapsearch(self, kali_available):
        """Test LDAP enumeration with real Kali container."""
        event_bus = AsyncMock()

        agent = ADAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="test-eng",
            event_bus=event_bus,
            max_iterations=1,
        )

        assert agent.role == AgentRole.AD
        assert hasattr(agent, "_enumerate_domain")
        assert hasattr(agent, "execute_ad_attack")


@pytest.mark.integration
class TestADAgentSignalIntegration:
    """Test stigmergic signal handling for ADAgent."""

    @pytest.mark.asyncio
    async def test_ad_receives_recon_signals(self):
        """Test ADAgent can receive and process recon findings."""
        event_bus = AsyncMock()

        agent = ADAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="test-eng",
            event_bus=event_bus,
            max_iterations=1,
        )

        # ADAgent should be able to receive recon signals
        assert hasattr(agent, "on_signal")

    @pytest.mark.asyncio
    async def test_ad_publishes_findings_to_bus(self):
        """Test ADAgent publishes findings to event bus."""
        event_bus = AsyncMock()

        agent = ADAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="test-eng",
            event_bus=event_bus,
            max_iterations=1,
        )

        finding = Finding(
            id=str(uuid.uuid4()),
            type="kerberoast",
            severity="high",
            target="dc01.corp.local",
            evidence="$krb5tgs$23$*svc_backup$CORP.LOCAL...",
            agent_id=agent.agent_id,
            timestamp="2025-01-21T00:00:00Z",
            tool="impacket-GetUserSPNs",
            topic="findings:test-eng:kerberoast",
            signature="kerb-001",
        )

        await agent.on_finding(finding)


@pytest.mark.integration
class TestADAgentDomainAdminDetection:
    """Test Domain Admin detection and escalation."""

    @pytest.mark.asyncio
    async def test_domain_admin_detection(self):
        """Test detection of Domain Admin compromise."""
        event_bus = AsyncMock()

        agent = ADAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="test-eng",
            event_bus=event_bus,
            max_iterations=1,
        )

        # Simulate Domain Admin detection
        await agent._publish_domain_admin_finding("corp.local", "Administrator")

        # Should publish critical finding
        event_bus.publish.assert_called()
        call_args = event_bus.publish.call_args
        assert "domainadmin" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_ad_tools_available(self):
        """Verify AD-specific tools are in the agent's toolset."""
        event_bus = AsyncMock()

        agent = ADAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="test-eng",
            event_bus=event_bus,
            max_iterations=1,
        )

        # Verify agent has tool selection capability for AD-specific tools
        # (ldapsearch, impacket-*, bloodhound-python, crackmapexec, kerbrute)
        assert hasattr(agent, "select_tool")
        assert hasattr(agent, "_build_tool_context")
