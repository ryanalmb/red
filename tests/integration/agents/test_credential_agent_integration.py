"""Integration tests for CredentialAgent (Story 7.22).

Tests agent integration with the stigmergic communication layer.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.integration
class TestCredentialAgentIntegration:
    """Integration tests for CredentialAgent stigmergic communication."""

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock event bus with async methods."""
        bus = AsyncMock()
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        return bus

    @pytest.fixture
    def credential_agent(self, mock_event_bus):
        """Create CredentialAgent for integration testing."""
        from cyberred.agents.credential import CredentialAgent

        return CredentialAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-integration-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_stigmergic_credential_publish_flow(self, credential_agent, mock_event_bus):
        """Test full credential publish flow via stigmergic channel."""
        credential = {"username": "admin", "password": "secret123", "hash_type": "ntlm"}

        await credential_agent._publish_cracked_credential(credential)

        mock_event_bus.publish.assert_called_once()
        call_args = mock_event_bus.publish.call_args
        channel = call_args[0][0]
        payload = call_args[0][1]

        assert "credentials:eng-integration-1:cracked" == channel
        assert payload["credential"] == credential
        assert payload["agent_id"] == credential_agent.agent_id

    @pytest.mark.asyncio
    async def test_stigmergic_finding_publish_flow(self, credential_agent, mock_event_bus):
        """Test finding publish to stigmergic channel."""
        from cyberred.core.models import Finding

        finding = Finding(
            id=str(uuid.uuid4()),
            type="credential",
            severity="high",
            target="192.168.1.100",
            evidence="Cracked: admin:password",
            agent_id=credential_agent.agent_id,
            timestamp="2026-01-26T00:00:00Z",
            tool="hashcat",
            topic="findings:test:credential",
            signature="test-sig",
        )

        await credential_agent.on_finding(finding)

        mock_event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_stigmergic_hash_reception(self, credential_agent):
        """Test receiving hashes from other agents via stigmergic signal."""
        # Simulate ADAgent publishing a Kerberos ticket
        data = {
            "hash": "$krb5tgs$23$*svc$DOMAIN$spn*$hash",
            "hash_type": "kerberos_tgs",
            "agent_id": "ad-agent-001",
            "spn": "MSSQLSvc/db01.corp.local",
        }

        await credential_agent.on_signal("credentials:eng-integration-1:kerberos", data)

        assert len(credential_agent._pending_hashes) == 1
        assert credential_agent._pending_hashes[0]["hash_type"] == "kerberos_tgs"
        assert credential_agent._pending_hashes[0]["spn"] == "MSSQLSvc/db01.corp.local"

    @pytest.mark.asyncio
    async def test_stigmergic_strategy_update(self, credential_agent):
        """Test strategy update via stigmergic signal."""
        assert credential_agent.current_strategy == "standard"

        await credential_agent.on_signal(
            "strategies:eng-integration-1",
            {"strategy": "stealth"}
        )

        assert credential_agent.current_strategy == "stealth"

    @pytest.mark.asyncio
    async def test_end_to_end_attack_flow(self, credential_agent, mock_event_bus):
        """Test end-to-end credential attack with mocked execution."""
        credential_agent.max_iterations = 1
        credential_agent.phase_complete_threshold = 10

        tool_selection = MagicMock()
        tool_selection.tool_name = "hydra"
        tool_selection.command = "hydra -l admin -P wordlist.txt ssh://192.168.1.100"
        tool_selection.confidence = 0.9

        result = MagicMock()
        result.success = True
        result.stdout = "login: admin password: password123"
        result.stderr = ""
        result.exit_code = 0

        with patch.object(credential_agent, "select_tool", new_callable=AsyncMock, return_value=tool_selection), \
             patch("cyberred.agents.credential.kali_execute", new_callable=AsyncMock, return_value=result):

            findings, actions = await credential_agent.execute_credential_attack(
                "192.168.1.100",
                {"service": "ssh", "attack_type": "spray"}
            )

        # Verify findings and actions
        assert len(findings) == 1
        assert len(actions) == 1
        assert actions[0].action_type == "credential:hydra"

        # Verify cracked credentials were stored and published
        assert len(credential_agent._cracked_credentials) >= 1
        assert mock_event_bus.publish.call_count >= 1

    @pytest.mark.asyncio
    async def test_subscription_setup(self, credential_agent, mock_event_bus):
        """Test credential channel subscription setup."""
        await credential_agent._setup_credential_subscriptions()

        mock_event_bus.subscribe.assert_called_once()
        call_args = mock_event_bus.subscribe.call_args
        pattern = call_args[0][0]

        assert "credentials:eng-integration-1:*" == pattern
