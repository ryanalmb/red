"""Legacy compatibility tests for ReconAgent (Story 7.3 → 7.3-v2 migration).

These tests ensure backward compatibility and verify preserved behaviors
after the v2 refactor that removed hardcoded tool sequences.

NOTE: Tests for hardcoded command generation methods have been REMOVED
as those methods no longer exist in the refactored ReconAgent.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid

from cyberred.agents.recon import ReconAgent
from cyberred.agents.base import StigmergicAgent
from cyberred.agents.roles import AgentRole


@pytest.mark.unit
class TestReconAgent:
    """Unit tests for ReconAgent - updated for v2 refactor."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def valid_target(self):
        return "192.168.1.10"

    @pytest.fixture
    def mock_scope_validator(self):
        with patch("cyberred.agents.recon.ScopeValidator") as mock:
            instance = mock.return_value
            instance.validate.return_value = True
            yield instance

    @pytest.fixture
    def mock_kali_execute(self):
        with patch("cyberred.agents.recon.kali_execute") as mock:
            result = MagicMock()
            result.success = True
            result.stdout = "output"
            result.stderr = ""
            result.exit_code = 0
            mock.return_value = result
            yield mock

    @pytest.fixture
    def recon_agent(self, mock_event_bus, mock_scope_validator, mock_kali_execute):
        """Create a ReconAgent using v2 constructor (no target in constructor)."""
        agent = ReconAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        return agent

    def test_extends_stigmergic_agent(self):
        """ReconAgent extends StigmergicAgent."""
        assert issubclass(ReconAgent, StigmergicAgent)

    def test_init_sets_role_to_recon(self, mock_event_bus, mock_scope_validator):
        """ReconAgent constructor sets role=AgentRole.RECON."""
        agent = ReconAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert agent.role == AgentRole.RECON

    def test_init_default_specialty(self, mock_event_bus, mock_scope_validator):
        """ReconAgent default specialty is 'network'."""
        agent = ReconAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert agent.specialty == "network"

    @pytest.mark.asyncio
    async def test_on_finding_publishes_to_channel(self, recon_agent, mock_event_bus):
        """Test on_finding publishes to correct channel pattern."""
        target_hash = "abc123hash"
        finding_type = "open_port"
        content = {"port": 80}

        await recon_agent.on_finding(target_hash, finding_type, content)

        expected_channel = f"findings:{target_hash}:{finding_type}"
        from unittest.mock import ANY
        mock_event_bus.publish.assert_called_with(expected_channel, ANY)

    def test_decision_context_population(self, recon_agent):
        """Test decision_context populated for actions."""
        recon_agent._decision_context = ["signal-1", "signal-2"]

        context = recon_agent.get_decision_context()
        assert "signal-1" in context
        assert "signal-2" in context

    @pytest.mark.asyncio
    async def test_on_signal_strategy_update(self, recon_agent):
        """Test on_signal handling for strategies."""
        channel = "strategies:eng-1"
        data = {"strategy": "stealth"}

        with patch.object(recon_agent, "_log") as mock_log:
            await recon_agent.on_signal(channel, data)
            from unittest.mock import ANY
            mock_log.info.assert_any_call("strategy_updated", old="standard", new="stealth")

    @pytest.mark.asyncio
    async def test_stop_sets_event(self, recon_agent):
        """Test graceful shutdown."""
        await recon_agent.stop()
        assert recon_agent._stop_event.is_set()

    def test_scope_validator_fallback(self, recon_agent, mock_kali_execute):
        """Test scope file loading failure handling returns default validator."""
        with patch("cyberred.agents.recon.get_settings") as mock_settings:
            mock_settings.return_value.engagement.scope_path = "/bad/path"
            with patch("cyberred.agents.recon.ScopeValidator") as MockValidator:
                MockValidator.from_file.side_effect = ValueError("Bad file")

                validator = recon_agent._get_scope_validator()

                assert validator is not None
                MockValidator.from_file.assert_called_with("/bad/path")
