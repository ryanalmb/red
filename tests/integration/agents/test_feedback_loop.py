"""Integration tests for Director-Agent Feedback Loop (Story 7.17, AC #6).

Tests the complete feedback loop between Director strategy publication
and agent behavior changes, using real EventBus with mock Redis.

Test scenarios:
1. Publish "prioritize web apps" strategy → verify agent shifts to web tools
2. Publish avoid_targets → verify target exclusion
3. Publish recommended_techniques → verify tool priority change
"""

import asyncio
import json
import pytest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from cyberred.agents.base import StigmergicAgent, ATTCK_TECHNIQUE_TOOL_MAP
from cyberred.agents.roles import AgentRole
from cyberred.core.events import EventBus
from cyberred.core.models import ToolSelectionContext
from cyberred.orchestration.emergence.strategy import (
    EmergentStrategy,
    EmergentStrategyPublisher,
)
from cyberred.orchestration.emergence.patterns import EmergentPattern, PatternType
from cyberred.orchestration.emergence.tracker import DecisionContextTracker


# === Fixtures ===

@pytest.fixture
def mock_redis_client():
    """Create a mock RedisClient for EventBus."""
    from cyberred.storage.redis_client import RedisClient
    
    client = MagicMock(spec=RedisClient)
    client.publish = AsyncMock(return_value=1)
    client.subscribe = AsyncMock()
    client.psubscribe = AsyncMock()
    client.get_pubsub = MagicMock()
    
    # Mock pubsub
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.psubscribe = AsyncMock()
    pubsub.get_message = AsyncMock(return_value=None)
    client.get_pubsub.return_value = pubsub
    
    return client


@pytest.fixture
def event_bus(mock_redis_client):
    """Create an EventBus with mock Redis for testing."""
    bus = EventBus(redis_client=mock_redis_client)
    return bus


@pytest.fixture
def context_tracker(event_bus):
    """Create a DecisionContextTracker."""
    return DecisionContextTracker(
        engagement_id="integration-test-engagement",
        event_bus=event_bus,
    )


@pytest.fixture
def mock_llm_gateway():
    """Create a mock LLM gateway that returns tool selections."""
    gateway = MagicMock()
    
    async def mock_complete(request):
        # Return web tool when strategy mentions web
        response = MagicMock()
        response.content = json.dumps({
            "tool_name": "sqlmap",
            "command": "sqlmap -u http://target.com",
            "rationale": "Selected based on Director strategy objective",
            "expected_output_type": "text",
            "confidence": 0.9,
            "priority": 1,
            "alternatives": ["nuclei"]
        })
        return response
    
    gateway.agent_complete = mock_complete
    return gateway


@pytest.fixture
def mock_manifest_loader():
    """Create a mock ManifestLoader with tool data."""
    loader = MagicMock()
    
    # Mock tools for different categories
    web_tool = MagicMock()
    web_tool.name = "sqlmap"
    
    recon_tool = MagicMock()
    recon_tool.name = "nmap"
    
    exploit_tool = MagicMock()
    exploit_tool.name = "nuclei"
    
    def get_by_category(category):
        if category in ["web", "injection"]:
            return [web_tool, exploit_tool]
        elif category in ["recon", "discovery"]:
            return [recon_tool]
        elif category in ["exploit"]:
            return [exploit_tool]
        return []
    
    loader.get_by_category = get_by_category
    return loader


@pytest.fixture
def sample_pattern():
    """Create a sample EmergentPattern for strategy creation."""
    return EmergentPattern(
        id="pattern-integration-123",
        pattern_type=PatternType.SERVICE_CORRELATION,
        confidence=0.85,
        contributing_findings=["finding-1", "finding-2"],
        recommended_actions=["Exploit web application vulnerabilities"],
        timestamp=datetime.now(UTC).isoformat(),
    )


@pytest.fixture
def web_strategy(sample_pattern):
    """Create a strategy that prioritizes web application testing."""
    return EmergentStrategy(
        id="strategy-web-456",
        engagement_id="integration-test-engagement",
        pattern=sample_pattern,
        objectives=["prioritize web vulnerabilities", "focus on SQL injection"],
        recommended_techniques=["T1190"],  # Exploit Public-Facing Application
        avoid_targets=[],
        confidence=0.85,
        timestamp=datetime.now(UTC).isoformat(),
    )


@pytest.fixture
def avoid_strategy(sample_pattern):
    """Create a strategy with avoid_targets."""
    return EmergentStrategy(
        id="strategy-avoid-789",
        engagement_id="integration-test-engagement",
        pattern=sample_pattern,
        objectives=["continue enumeration"],
        recommended_techniques=["T1046"],
        avoid_targets=["192.168.1.100", "192.168.1.200", "honeypot.local"],
        confidence=0.85,
        timestamp=datetime.now(UTC).isoformat(),
    )


@pytest.fixture
def technique_strategy(sample_pattern):
    """Create a strategy with recommended ATT&CK techniques."""
    return EmergentStrategy(
        id="strategy-technique-abc",
        engagement_id="integration-test-engagement",
        pattern=sample_pattern,
        objectives=["leverage discovered credentials"],
        recommended_techniques=["T1078", "T1021"],  # Valid Accounts, Remote Services
        avoid_targets=[],
        confidence=0.9,
        timestamp=datetime.now(UTC).isoformat(),
    )


@pytest.fixture
async def agent(event_bus, mock_llm_gateway, mock_manifest_loader, context_tracker):
    """Create a StigmergicAgent for integration testing."""
    agent = StigmergicAgent(
        agent_name="IntegrationTestAgent",
        agent_id="00000000-0000-0000-0000-000000000002",
        engagement_id="integration-test-engagement",
        event_bus=event_bus,
        role=AgentRole.EXPLOIT,
        llm_gateway=mock_llm_gateway,
        manifest_loader=mock_manifest_loader,
        context_tracker=context_tracker,
        llm=MagicMock(),
    )
    # Don't call spawn() to avoid async subscription issues in tests
    return agent


# === Test: Strategy Publication and Reception (AC #6.2) ===

class TestStrategyPublicationReception:
    """Integration tests for strategy publication and agent reception."""

    @pytest.mark.asyncio
    async def test_agent_receives_published_strategy(self, agent, web_strategy):
        """Agent should receive and store strategy published via EventBus."""
        # Publish strategy directly to agent's handler (simulating EventBus delivery)
        strategy_data = web_strategy._to_dict()
        
        await agent._handle_strategy_update(strategy_data)
        
        # Verify agent stored the strategy
        assert agent._active_strategy is not None
        assert agent._active_strategy.id == web_strategy.id
        assert "prioritize web vulnerabilities" in agent._active_strategy.objectives

    @pytest.mark.asyncio
    async def test_strategy_recorded_in_decision_context(self, agent, web_strategy, context_tracker):
        """Strategy should be recorded in decision context tracker."""
        strategy_data = web_strategy._to_dict()
        
        await agent._handle_strategy_update(strategy_data)
        
        # Verify decision context contains strategy
        context = context_tracker.get_context(agent.agent_id)
        assert web_strategy.id in context
        
        # Verify signal type is director_strategy
        signals = context_tracker._signals.get(agent.agent_id, [])
        strategy_signal = next((s for s in signals if s.signal_id == web_strategy.id), None)
        assert strategy_signal is not None
        assert strategy_signal.signal_type == "director_strategy"


# === Test: Web App Prioritization (AC #6.3) ===

class TestWebAppPrioritization:
    """Integration tests for AC #6.3: publish 'prioritize web apps' strategy."""

    @pytest.mark.asyncio
    async def test_tool_selection_prompt_includes_web_objective(self, agent, web_strategy):
        """Tool selection prompt should include web prioritization objective."""
        await agent._handle_strategy_update(web_strategy._to_dict())
        
        context = ToolSelectionContext(
            objective="scan target for vulnerabilities",
            target_info={"ip": "192.168.1.50", "port": 80},
            available_tools=["nmap", "sqlmap", "nuclei", "hydra"],
            phase="exploit",
            constraints=[],
            previous_results=[],
        )
        
        prompt = agent._build_tool_selection_prompt(context)
        
        # Verify web objectives are in prompt
        assert "prioritize web vulnerabilities" in prompt
        assert "Director Strategy" in prompt

    @pytest.mark.asyncio
    async def test_strategy_context_includes_techniques(self, agent, web_strategy):
        """Strategy context should include recommended ATT&CK techniques."""
        await agent._handle_strategy_update(web_strategy._to_dict())
        
        context_str = agent._get_strategy_context()
        
        assert "T1190" in context_str  # Exploit Public-Facing App
        assert "Recommended ATT&CK" in context_str

    @pytest.mark.asyncio
    async def test_agent_behavior_shift_to_web_tools(self, agent, web_strategy, mock_llm_gateway):
        """Agent should shift to web tools when given web-focused strategy."""
        # Capture before state (no strategy)
        assert agent._active_strategy is None
        
        # Apply web strategy
        await agent._handle_strategy_update(web_strategy._to_dict())
        
        # Verify strategy is active
        assert agent._active_strategy is not None
        assert "web" in agent._active_strategy.objectives[0].lower()
        
        # Build prompt and verify web context is included
        context = ToolSelectionContext(
            objective="test target",
            target_info={"ip": "192.168.1.50"},
            available_tools=["nmap", "sqlmap"],
            phase="exploit",
            constraints=[],
            previous_results=[],
        )
        
        prompt = agent._build_tool_selection_prompt(context)
        assert "prioritize web" in prompt.lower()


# === Test: Avoid Targets Filtering (AC #6.4) ===

class TestAvoidTargetsFiltering:
    """Integration tests for AC #6.4: publish avoid_targets → verify exclusion."""

    @pytest.mark.asyncio
    async def test_avoided_target_is_filtered(self, agent, avoid_strategy):
        """Agent should filter targets in avoid_targets list."""
        await agent._handle_strategy_update(avoid_strategy._to_dict())
        
        # Check targets that should be avoided
        assert agent._is_target_avoided("192.168.1.100") is True
        assert agent._is_target_avoided("192.168.1.200") is True
        assert agent._is_target_avoided("honeypot.local") is True

    @pytest.mark.asyncio
    async def test_non_avoided_target_passes(self, agent, avoid_strategy):
        """Agent should allow targets not in avoid_targets list."""
        await agent._handle_strategy_update(avoid_strategy._to_dict())
        
        # Check targets that should be allowed
        assert agent._is_target_avoided("192.168.1.50") is False
        assert agent._is_target_avoided("10.0.0.1") is False
        assert agent._is_target_avoided("target.local") is False

    @pytest.mark.asyncio
    async def test_avoid_target_logged_with_reason(self, agent, avoid_strategy):
        """Avoided targets should be logged with 'strategy_avoid_list' reason."""
        await agent._handle_strategy_update(avoid_strategy._to_dict())
        
        with patch.object(agent, '_log') as mock_log:
            agent._is_target_avoided("192.168.1.100")
            
            mock_log.info.assert_called_once()
            call_kwargs = mock_log.info.call_args.kwargs
            assert call_kwargs["reason"] == "strategy_avoid_list"
            assert call_kwargs["strategy_id"] == avoid_strategy.id

    @pytest.mark.asyncio
    async def test_avoid_targets_in_strategy_context(self, agent, avoid_strategy):
        """Strategy context should include avoid_targets for LLM prompt."""
        await agent._handle_strategy_update(avoid_strategy._to_dict())
        
        context_str = agent._get_strategy_context()
        
        assert "Avoid targets:" in context_str
        assert "192.168.1.100" in context_str


# === Test: Technique Prioritization (AC #6.5) ===

class TestTechniquePrioritization:
    """Integration tests for AC #6.5: recommended_techniques → tool priority."""

    @pytest.mark.asyncio
    async def test_technique_maps_to_tool_categories(self, agent, technique_strategy):
        """Recommended techniques should map to tool categories."""
        await agent._handle_strategy_update(technique_strategy._to_dict())
        
        # T1078 (Valid Accounts) maps to credential, auth categories
        # Verify mapping exists in ATTCK_TECHNIQUE_TOOL_MAP
        assert "T1078" in ATTCK_TECHNIQUE_TOOL_MAP
        categories = ATTCK_TECHNIQUE_TOOL_MAP["T1078"]
        assert len(categories) > 0
        
        # T1021 (Remote Services) maps to lateral, exploit categories
        assert "T1021" in ATTCK_TECHNIQUE_TOOL_MAP
        categories = ATTCK_TECHNIQUE_TOOL_MAP["T1021"]
        assert len(categories) > 0

    @pytest.mark.asyncio
    async def test_multiple_techniques_combine_tools(self, agent, technique_strategy):
        """Multiple techniques should combine their tool categories."""
        await agent._handle_strategy_update(technique_strategy._to_dict())
        
        # Both T1078 and T1021 together
        tools = agent._get_technique_tools(["T1078", "T1021"])
        
        # Should have tools from both technique mappings
        assert len(tools) > 0

    @pytest.mark.asyncio
    async def test_techniques_in_strategy_context(self, agent, technique_strategy):
        """Strategy context should include recommended techniques."""
        await agent._handle_strategy_update(technique_strategy._to_dict())
        
        context_str = agent._get_strategy_context()
        
        assert "T1078" in context_str
        assert "T1021" in context_str
        assert "Recommended ATT&CK" in context_str


# === Test: Before/After Behavior Comparison ===

class TestBeforeAfterBehavior:
    """Integration tests comparing agent behavior before and after strategy."""

    @pytest.mark.asyncio
    async def test_prompt_changes_with_strategy(self, agent, web_strategy):
        """Tool selection prompt should change when strategy is applied."""
        context = ToolSelectionContext(
            objective="scan target",
            target_info={"ip": "192.168.1.50"},
            available_tools=["nmap", "sqlmap"],
            phase="exploit",
            constraints=[],
            previous_results=[],
        )
        
        # Before: No strategy
        prompt_before = agent._build_tool_selection_prompt(context)
        assert "Director Strategy" not in prompt_before
        
        # Apply strategy
        await agent._handle_strategy_update(web_strategy._to_dict())
        
        # After: With strategy
        prompt_after = agent._build_tool_selection_prompt(context)
        assert "Director Strategy" in prompt_after
        assert "prioritize web vulnerabilities" in prompt_after

    @pytest.mark.asyncio
    async def test_decision_context_before_after(self, agent, web_strategy, context_tracker):
        """Decision context should show strategy influence after application."""
        # Before: Empty context
        context_before = context_tracker.get_context(agent.agent_id)
        assert web_strategy.id not in context_before
        
        # Apply strategy
        await agent._handle_strategy_update(web_strategy._to_dict())
        
        # After: Contains strategy ID
        context_after = context_tracker.get_context(agent.agent_id)
        assert web_strategy.id in context_after

    @pytest.mark.asyncio
    async def test_avoid_filtering_before_after(self, agent, avoid_strategy):
        """Avoid filtering should only apply after strategy is received."""
        target = "192.168.1.100"
        
        # Before: Target not avoided
        assert agent._is_target_avoided(target) is False
        
        # Apply strategy
        await agent._handle_strategy_update(avoid_strategy._to_dict())
        
        # After: Target avoided
        assert agent._is_target_avoided(target) is True


# === Test: Strategy Publisher Integration ===

class TestStrategyPublisherIntegration:
    """Integration tests for EmergentStrategyPublisher."""

    @pytest.mark.asyncio
    async def test_publisher_creates_valid_strategy(self, event_bus, sample_pattern):
        """Publisher should create valid EmergentStrategy from pattern."""
        publisher = EmergentStrategyPublisher(event_bus, confidence_threshold=0.5)
        
        strategy = await publisher.publish_strategy(
            sample_pattern,
            engagement_id="integration-test-engagement",
        )
        
        assert strategy is not None
        assert strategy.pattern.id == sample_pattern.id
        assert len(strategy.objectives) > 0
        assert strategy.engagement_id == "integration-test-engagement"

    @pytest.mark.asyncio
    async def test_publisher_respects_confidence_threshold(self, event_bus, sample_pattern):
        """Publisher should not publish patterns below confidence threshold."""
        publisher = EmergentStrategyPublisher(event_bus, confidence_threshold=0.95)
        
        # Pattern has 0.85 confidence, threshold is 0.95
        strategy = await publisher.publish_strategy(
            sample_pattern,
            engagement_id="integration-test-engagement",
        )
        
        assert strategy is None  # Below threshold

    @pytest.mark.asyncio
    async def test_publisher_publishes_to_event_bus(self, event_bus, sample_pattern, mock_redis_client):
        """Publisher should publish strategy to EventBus."""
        publisher = EmergentStrategyPublisher(event_bus, confidence_threshold=0.5)
        
        await publisher.publish_strategy(
            sample_pattern,
            engagement_id="integration-test-engagement",
        )
        
        # Verify publish was called on the underlying redis client
        mock_redis_client.publish.assert_called()
