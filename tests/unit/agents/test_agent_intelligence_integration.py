"""Unit tests for intelligence integration in all agents.

Tests the CachedIntelligenceAggregator integration pattern across all 6 agents
that were updated to include intelligence support:
- WebAppAgent
- WirelessAgent
- ADAgent
- CredentialAgent
- ForensicsAgent
- ReconAgent

These tests verify:
1. Constructor accepts intel_aggregator parameter
2. _query_intelligence method works correctly
3. _select_intel returns highest priority result
4. decision_context includes intelligence data
5. Graceful handling when aggregator is None or fails
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_event_bus() -> MagicMock:
    """Create mock EventBus."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock()
    return bus


@pytest.fixture
def mock_llm_gateway() -> MagicMock:
    """Create mock LLMGateway."""
    gateway = MagicMock()
    gateway.agent_complete = AsyncMock()
    return gateway


@pytest.fixture
def mock_manifest_loader() -> MagicMock:
    """Create mock ManifestLoader."""
    loader = MagicMock()
    loader.get_by_category = MagicMock(return_value=[])
    return loader


@pytest.fixture
def mock_intel_aggregator() -> MagicMock:
    """Create mock CachedIntelligenceAggregator."""
    aggregator = MagicMock()
    aggregator.query = AsyncMock(return_value=[])
    return aggregator


@pytest.fixture
def mock_intel_result() -> MagicMock:
    """Create mock IntelResult with priority."""
    result = MagicMock()
    result.priority = 1
    result.source = "kev"
    result.cve_id = "CVE-2024-0001"
    return result


# ============================================================================
# WebAppAgent Tests
# ============================================================================


class TestWebAppAgentIntelligence:
    """Tests for WebAppAgent intelligence integration."""

    @pytest.fixture
    def create_agent(self, mock_event_bus, mock_llm_gateway, mock_manifest_loader):
        """Factory fixture for WebAppAgent."""
        def _create(intel_aggregator=None):
            from cyberred.agents.webapp import WebAppAgent
            with patch("cyberred.agents.webapp.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    engagement=MagicMock(scope_path=None)
                )
                return WebAppAgent(
                    agent_id="webapp-test-001",
                    engagement_id="eng-test",
                    event_bus=mock_event_bus,
                    llm_gateway=mock_llm_gateway,
                    manifest_loader=mock_manifest_loader,
                    intel_aggregator=intel_aggregator,
                )
        return _create

    def test_accepts_intel_aggregator(self, create_agent, mock_intel_aggregator):
        """WebAppAgent accepts intel_aggregator in constructor."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        assert agent._intel_aggregator == mock_intel_aggregator

    def test_intel_aggregator_defaults_to_none(self, create_agent):
        """WebAppAgent defaults intel_aggregator to None."""
        agent = create_agent()
        assert agent._intel_aggregator is None

    @pytest.mark.asyncio
    async def test_query_intelligence_calls_aggregator(self, create_agent, mock_intel_aggregator):
        """_query_intelligence calls aggregator.query()."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        mock_intel_aggregator.query.return_value = []

        result = await agent._query_intelligence("http", "Apache 2.4")

        mock_intel_aggregator.query.assert_called_once_with("http", "Apache 2.4")
        assert result == []

    @pytest.mark.asyncio
    async def test_query_intelligence_returns_empty_without_aggregator(self, create_agent):
        """_query_intelligence returns empty list without aggregator."""
        agent = create_agent()
        result = await agent._query_intelligence("http", "2.4")
        assert result == []

    @pytest.mark.asyncio
    async def test_query_intelligence_returns_empty_without_service(self, create_agent, mock_intel_aggregator):
        """_query_intelligence returns empty list without service."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        result = await agent._query_intelligence("", "2.4")
        assert result == []
        mock_intel_aggregator.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_query_intelligence_handles_exception(self, create_agent, mock_intel_aggregator):
        """_query_intelligence returns empty on exception."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        mock_intel_aggregator.query.side_effect = Exception("Connection error")

        result = await agent._query_intelligence("http", "2.4")
        assert result == []

    @pytest.mark.asyncio
    async def test_select_intel_returns_highest_priority(self, create_agent, mock_intel_result):
        """_select_intel returns highest priority (lowest number)."""
        agent = create_agent()
        results = [
            MagicMock(priority=3, source="nvd"),
            mock_intel_result,  # priority=1
            MagicMock(priority=2, source="msf"),
        ]

        result = await agent._select_intel(results)
        assert result.source == "kev"

    @pytest.mark.asyncio
    async def test_select_intel_returns_none_for_empty(self, create_agent):
        """_select_intel returns None for empty list."""
        agent = create_agent()
        result = await agent._select_intel([])
        assert result is None

    @pytest.mark.asyncio
    async def test_select_intel_returns_none_for_none(self, create_agent):
        """_select_intel returns None for None input."""
        agent = create_agent()
        result = await agent._select_intel(None)
        assert result is None


# ============================================================================
# WirelessAgent Tests
# ============================================================================


class TestWirelessAgentIntelligence:
    """Tests for WirelessAgent intelligence integration."""

    @pytest.fixture
    def create_agent(self, mock_event_bus, mock_llm_gateway, mock_manifest_loader):
        """Factory fixture for WirelessAgent."""
        def _create(intel_aggregator=None):
            from cyberred.agents.wireless import WirelessAgent
            return WirelessAgent(
                agent_id="wireless-test-001",
                engagement_id="eng-test",
                event_bus=mock_event_bus,
                llm_gateway=mock_llm_gateway,
                manifest_loader=mock_manifest_loader,
                intel_aggregator=intel_aggregator,
            )
        return _create

    def test_accepts_intel_aggregator(self, create_agent, mock_intel_aggregator):
        """WirelessAgent accepts intel_aggregator in constructor."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        assert agent._intel_aggregator == mock_intel_aggregator

    @pytest.mark.asyncio
    async def test_query_intelligence_calls_aggregator(self, create_agent, mock_intel_aggregator):
        """_query_intelligence calls aggregator with protocol."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        mock_intel_aggregator.query.return_value = []

        result = await agent._query_intelligence("802.11", "WPA2")

        mock_intel_aggregator.query.assert_called_once_with("802.11", "WPA2")

    @pytest.mark.asyncio
    async def test_query_intelligence_returns_empty_without_protocol(self, create_agent, mock_intel_aggregator):
        """_query_intelligence returns empty without protocol."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        result = await agent._query_intelligence("", "WPA2")
        assert result == []

    @pytest.mark.asyncio
    async def test_select_intel_returns_highest_priority(self, create_agent):
        """_select_intel returns highest priority result."""
        agent = create_agent()
        results = [
            MagicMock(priority=2),
            MagicMock(priority=1),
        ]
        result = await agent._select_intel(results)
        assert result.priority == 1


# ============================================================================
# ADAgent Tests
# ============================================================================


class TestADAgentIntelligence:
    """Tests for ADAgent intelligence integration."""

    @pytest.fixture
    def create_agent(self, mock_event_bus):
        """Factory fixture for ADAgent."""
        def _create(intel_aggregator=None):
            from cyberred.agents.ad import ADAgent
            return ADAgent(
                agent_id="ad-test-001",
                engagement_id="eng-test",
                event_bus=mock_event_bus,
                intel_aggregator=intel_aggregator,
            )
        return _create

    def test_accepts_intel_aggregator(self, create_agent, mock_intel_aggregator):
        """ADAgent accepts intel_aggregator in constructor."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        assert agent._intel_aggregator == mock_intel_aggregator

    @pytest.mark.asyncio
    async def test_query_intelligence_calls_aggregator(self, create_agent, mock_intel_aggregator):
        """_query_intelligence calls aggregator with service."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        mock_intel_aggregator.query.return_value = []

        result = await agent._query_intelligence("ldap", "")

        mock_intel_aggregator.query.assert_called_once_with("ldap", "")

    @pytest.mark.asyncio
    async def test_build_decision_context_includes_intel(self, create_agent, mock_intel_result):
        """_build_decision_context includes intel data."""
        agent = create_agent()

        ctx = agent._build_decision_context(MagicMock(), intel=mock_intel_result)

        assert any("intel:" in c for c in ctx)
        assert any("kev" in c for c in ctx)

    @pytest.mark.asyncio
    async def test_build_decision_context_no_intel(self, create_agent):
        """_build_decision_context works without intel."""
        agent = create_agent()

        ctx = agent._build_decision_context(MagicMock(), intel=None)

        assert not any("intel:" in c for c in ctx)


# ============================================================================
# CredentialAgent Tests
# ============================================================================


class TestCredentialAgentIntelligence:
    """Tests for CredentialAgent intelligence integration."""

    @pytest.fixture
    def create_agent(self, mock_event_bus):
        """Factory fixture for CredentialAgent."""
        def _create(intel_aggregator=None):
            from cyberred.agents.credential import CredentialAgent
            return CredentialAgent(
                agent_id="cred-test-001",
                engagement_id="eng-test",
                event_bus=mock_event_bus,
                intel_aggregator=intel_aggregator,
            )
        return _create

    def test_accepts_intel_aggregator(self, create_agent, mock_intel_aggregator):
        """CredentialAgent accepts intel_aggregator in constructor."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        assert agent._intel_aggregator == mock_intel_aggregator

    @pytest.mark.asyncio
    async def test_query_intelligence_calls_aggregator(self, create_agent, mock_intel_aggregator):
        """_query_intelligence calls aggregator with service and hash_type."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        mock_intel_aggregator.query.return_value = []

        result = await agent._query_intelligence("smb", "ntlm")

        mock_intel_aggregator.query.assert_called_once_with("smb", "ntlm")

    @pytest.mark.asyncio
    async def test_build_decision_context_includes_intel(self, create_agent, mock_intel_result):
        """_build_decision_context includes intel data."""
        agent = create_agent()

        ctx = agent._build_decision_context({"service": "smb"}, intel=mock_intel_result)

        assert any("intel:" in c for c in ctx)


# ============================================================================
# ForensicsAgent Tests
# ============================================================================


class TestForensicsAgentIntelligence:
    """Tests for ForensicsAgent intelligence integration."""

    @pytest.fixture
    def create_agent(self, mock_event_bus):
        """Factory fixture for ForensicsAgent."""
        def _create(intel_aggregator=None):
            from cyberred.agents.forensics import ForensicsAgent
            return ForensicsAgent(
                agent_id="forensics-test-001",
                engagement_id="eng-test",
                event_bus=mock_event_bus,
                intel_aggregator=intel_aggregator,
            )
        return _create

    def test_accepts_intel_aggregator(self, create_agent, mock_intel_aggregator):
        """ForensicsAgent accepts intel_aggregator in constructor."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        assert agent._intel_aggregator == mock_intel_aggregator

    @pytest.mark.asyncio
    async def test_query_intelligence_calls_aggregator(self, create_agent, mock_intel_aggregator):
        """_query_intelligence calls aggregator with os_type."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        mock_intel_aggregator.query.return_value = []

        result = await agent._query_intelligence("linux", "memory")

        mock_intel_aggregator.query.assert_called_once_with("linux", "memory")

    @pytest.mark.asyncio
    async def test_build_decision_context_includes_intel(self, create_agent, mock_intel_result):
        """_build_decision_context includes intel data."""
        agent = create_agent()

        ctx = agent._build_decision_context("target", {}, intel=mock_intel_result)

        assert any("intel:" in c for c in ctx)


# ============================================================================
# ReconAgent Tests
# ============================================================================


class TestReconAgentIntelligence:
    """Tests for ReconAgent intelligence integration."""

    @pytest.fixture
    def create_agent(self, mock_event_bus, mock_llm_gateway, mock_manifest_loader):
        """Factory fixture for ReconAgent."""
        def _create(intel_aggregator=None):
            from cyberred.agents.recon import ReconAgent
            with patch("cyberred.agents.recon.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    engagement=MagicMock(scope_path=None)
                )
                return ReconAgent(
                    agent_id="recon-test-001",
                    engagement_id="eng-test",
                    event_bus=mock_event_bus,
                    llm_gateway=mock_llm_gateway,
                    manifest_loader=mock_manifest_loader,
                    intel_aggregator=intel_aggregator,
                )
        return _create

    def test_accepts_intel_aggregator(self, create_agent, mock_intel_aggregator):
        """ReconAgent accepts intel_aggregator in constructor."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        assert agent._intel_aggregator == mock_intel_aggregator

    @pytest.mark.asyncio
    async def test_query_intelligence_calls_aggregator(self, create_agent, mock_intel_aggregator):
        """_query_intelligence calls aggregator with service/version."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        mock_intel_aggregator.query.return_value = []

        result = await agent._query_intelligence("ssh", "OpenSSH 8.0")

        mock_intel_aggregator.query.assert_called_once_with("ssh", "OpenSSH 8.0")

    @pytest.mark.asyncio
    async def test_query_intelligence_returns_empty_without_service(self, create_agent, mock_intel_aggregator):
        """_query_intelligence returns empty without service."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        result = await agent._query_intelligence("", "8.0")
        assert result == []

    @pytest.mark.asyncio
    async def test_select_intel_returns_highest_priority(self, create_agent):
        """_select_intel returns highest priority result."""
        agent = create_agent()
        results = [
            MagicMock(priority=3),
            MagicMock(priority=1),
            MagicMock(priority=2),
        ]
        result = await agent._select_intel(results)
        assert result.priority == 1


# ============================================================================
# Cross-Agent Intelligence Integration Tests
# ============================================================================


class TestCrossAgentIntelligencePatterns:
    """Tests verifying consistent intelligence patterns across all agents."""

    @pytest.mark.asyncio
    async def test_all_agents_have_query_intelligence(self, mock_event_bus, mock_llm_gateway, mock_manifest_loader):
        """All 6 agents have _query_intelligence method."""
        from cyberred.agents.webapp import WebAppAgent
        from cyberred.agents.wireless import WirelessAgent
        from cyberred.agents.ad import ADAgent
        from cyberred.agents.credential import CredentialAgent
        from cyberred.agents.forensics import ForensicsAgent
        from cyberred.agents.recon import ReconAgent

        agents = [WebAppAgent, WirelessAgent, ADAgent, CredentialAgent, ForensicsAgent, ReconAgent]

        for agent_cls in agents:
            assert hasattr(agent_cls, "_query_intelligence"), f"{agent_cls.__name__} missing _query_intelligence"
            assert callable(getattr(agent_cls, "_query_intelligence"))

    @pytest.mark.asyncio
    async def test_all_agents_have_select_intel(self, mock_event_bus):
        """All 6 agents have _select_intel method."""
        from cyberred.agents.webapp import WebAppAgent
        from cyberred.agents.wireless import WirelessAgent
        from cyberred.agents.ad import ADAgent
        from cyberred.agents.credential import CredentialAgent
        from cyberred.agents.forensics import ForensicsAgent
        from cyberred.agents.recon import ReconAgent

        agents = [WebAppAgent, WirelessAgent, ADAgent, CredentialAgent, ForensicsAgent, ReconAgent]

        for agent_cls in agents:
            assert hasattr(agent_cls, "_select_intel"), f"{agent_cls.__name__} missing _select_intel"
            assert callable(getattr(agent_cls, "_select_intel"))

    def test_all_agents_accept_intel_aggregator_in_init(self):
        """All 6 agents accept intel_aggregator parameter."""
        import inspect
        from cyberred.agents.webapp import WebAppAgent
        from cyberred.agents.wireless import WirelessAgent
        from cyberred.agents.ad import ADAgent
        from cyberred.agents.credential import CredentialAgent
        from cyberred.agents.forensics import ForensicsAgent
        from cyberred.agents.recon import ReconAgent

        agents = [WebAppAgent, WirelessAgent, ADAgent, CredentialAgent, ForensicsAgent, ReconAgent]

        for agent_cls in agents:
            sig = inspect.signature(agent_cls.__init__)
            params = list(sig.parameters.keys())
            assert "intel_aggregator" in params, f"{agent_cls.__name__} missing intel_aggregator param"
