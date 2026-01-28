"""E2E tests for Director-Agent Feedback Loop (Story 7.17, AC #7).

End-to-end tests that verify:
1. Agent actions before strategy publication
2. Strategy publication with specific objectives
3. Measurable behavior change in subsequent actions
4. Decision context contains strategy_id

These tests use minimal mocking to test the actual feedback loop behavior.
"""

import asyncio
import json
import pytest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from cyberred.agents.base import StigmergicAgent, ATTCK_TECHNIQUE_TOOL_MAP
from cyberred.agents.roles import AgentRole
from cyberred.core.events import EventBus
from cyberred.core.models import ToolSelectionContext, AgentAction
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
    
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.psubscribe = AsyncMock()
    pubsub.get_message = AsyncMock(return_value=None)
    client.get_pubsub.return_value = pubsub
    
    return client


@pytest.fixture
def event_bus(mock_redis_client):
    """Create an EventBus with mock Redis."""
    return EventBus(redis_client=mock_redis_client)


@pytest.fixture
def context_tracker(event_bus):
    """Create a DecisionContextTracker."""
    return DecisionContextTracker(
        engagement_id="e2e-test-engagement",
        event_bus=event_bus,
    )


@pytest.fixture
def mock_llm_gateway():
    """Create a mock LLM gateway with configurable responses."""
    gateway = MagicMock()
    
    # Track call count to vary responses
    call_count = {"value": 0}
    
    async def mock_complete(request):
        call_count["value"] += 1
        response = MagicMock()
        
        # Check if strategy context is in the prompt
        prompt = request.prompt if hasattr(request, 'prompt') else ""
        
        if "prioritize web" in prompt.lower() or "director strategy" in prompt.lower():
            # Web-focused response when strategy is active
            response.content = json.dumps({
                "tool_name": "sqlmap",
                "command": "sqlmap -u http://target.com/vuln",
                "rationale": "Selected sqlmap per Director strategy to prioritize web vulnerabilities",
                "expected_output_type": "text",
                "confidence": 0.95,
                "priority": 1,
                "alternatives": ["nuclei", "nikto"]
            })
        else:
            # Default network-focused response without strategy
            response.content = json.dumps({
                "tool_name": "nmap",
                "command": "nmap -sV 192.168.1.0/24",
                "rationale": "Default network scan for service discovery",
                "expected_output_type": "xml",
                "confidence": 0.8,
                "priority": 5,
                "alternatives": ["masscan"]
            })
        
        return response
    
    gateway.agent_complete = mock_complete
    gateway.call_count = call_count
    return gateway


@pytest.fixture
def mock_manifest_loader():
    """Create a mock ManifestLoader."""
    loader = MagicMock()
    
    web_tool = MagicMock()
    web_tool.name = "sqlmap"
    
    recon_tool = MagicMock()
    recon_tool.name = "nmap"
    
    def get_by_category(category):
        if category in ["web", "injection", "exploit"]:
            return [web_tool]
        elif category in ["recon", "discovery", "scanning"]:
            return [recon_tool]
        return []
    
    loader.get_by_category = get_by_category
    return loader


@pytest.fixture
def sample_pattern():
    """Create a sample EmergentPattern."""
    return EmergentPattern(
        id="e2e-pattern-001",
        pattern_type=PatternType.SERVICE_CORRELATION,
        confidence=0.9,
        contributing_findings=["finding-e2e-1", "finding-e2e-2"],
        recommended_actions=["Focus on web application attack surface"],
        timestamp=datetime.now(UTC).isoformat(),
    )


@pytest.fixture
def web_priority_strategy(sample_pattern):
    """Strategy that prioritizes web application testing."""
    return EmergentStrategy(
        id="e2e-strategy-web-001",
        engagement_id="e2e-test-engagement",
        pattern=sample_pattern,
        objectives=["prioritize web vulnerabilities", "focus on injection attacks"],
        recommended_techniques=["T1190", "T1059"],
        avoid_targets=["192.168.1.254"],  # Avoid the gateway
        confidence=0.9,
        timestamp=datetime.now(UTC).isoformat(),
    )


@pytest.fixture
def agent(event_bus, mock_llm_gateway, mock_manifest_loader, context_tracker):
    """Create a StigmergicAgent for e2e testing."""
    return StigmergicAgent(
        agent_name="E2ETestAgent",
        agent_id="00000000-0000-0000-0000-000000000003",
        engagement_id="e2e-test-engagement",
        event_bus=event_bus,
        role=AgentRole.EXPLOIT,
        llm_gateway=mock_llm_gateway,
        manifest_loader=mock_manifest_loader,
        context_tracker=context_tracker,
        llm=MagicMock(),
    )


# === E2E Test: Full Feedback Loop Verification (AC #7) ===

class TestE2EFeedbackLoop:
    """E2E tests verifying the complete Director-Agent feedback loop."""

    @pytest.mark.asyncio
    async def test_e2e_behavior_change_before_after_strategy(
        self, agent, web_priority_strategy, mock_llm_gateway, context_tracker
    ):
        """E2E test: verify measurable behavior change with strategy.
        
        AC #7: Test captures before/after agent actions for comparison.
        """
        # === BEFORE: Capture agent behavior without strategy ===
        context_before = ToolSelectionContext(
            objective="scan target for vulnerabilities",
            target_info={"ip": "192.168.1.50", "port": 80},
            available_tools=["nmap", "sqlmap", "nuclei"],
            phase="exploit",
            constraints=[],
            previous_results=[],
        )
        
        prompt_before = agent._build_tool_selection_prompt(context_before)
        
        # Verify no strategy context in prompt
        assert "Director Strategy" not in prompt_before
        assert agent._active_strategy is None
        
        # Get decision context before
        decision_context_before = context_tracker.get_context(agent.agent_id)
        assert web_priority_strategy.id not in decision_context_before
        
        # === STRATEGY PUBLICATION ===
        # Simulate Director publishing strategy
        strategy_data = web_priority_strategy._to_dict()
        await agent._handle_strategy_update(strategy_data)
        
        # === AFTER: Capture agent behavior with strategy ===
        context_after = ToolSelectionContext(
            objective="scan target for vulnerabilities",
            target_info={"ip": "192.168.1.50", "port": 80},
            available_tools=["nmap", "sqlmap", "nuclei"],
            phase="exploit",
            constraints=[],
            previous_results=[],
        )
        
        prompt_after = agent._build_tool_selection_prompt(context_after)
        
        # Verify strategy context IS in prompt
        assert "Director Strategy" in prompt_after
        assert "prioritize web vulnerabilities" in prompt_after
        assert agent._active_strategy is not None
        assert agent._active_strategy.id == web_priority_strategy.id
        
        # Get decision context after
        decision_context_after = context_tracker.get_context(agent.agent_id)
        assert web_priority_strategy.id in decision_context_after

    @pytest.mark.asyncio
    async def test_e2e_strategy_id_in_decision_context(
        self, agent, web_priority_strategy, context_tracker
    ):
        """E2E test: verify decision_context contains strategy_id.
        
        AC #7: Test validates decision_context contains strategy_id.
        """
        # Apply strategy
        await agent._handle_strategy_update(web_priority_strategy._to_dict())
        
        # Verify signal was recorded before execute clears it
        signals_before = context_tracker._signals.get(agent.agent_id, [])
        strategy_signals_before = [s for s in signals_before if s.signal_type == "director_strategy"]
        assert len(strategy_signals_before) > 0
        assert any(s.signal_id == web_priority_strategy.id for s in strategy_signals_before)
        
        # Execute an action (this attaches context and clears it)
        action = await agent.execute("192.168.1.50")
        
        # Verify strategy_id is in action's decision_context
        assert web_priority_strategy.id in action.decision_context

    @pytest.mark.asyncio
    async def test_e2e_tool_selection_with_strategy(
        self, agent, web_priority_strategy, mock_llm_gateway
    ):
        """E2E test: verify tool selection changes with strategy.
        
        Tests that LLM receives strategy context and response reflects it.
        """
        # Apply strategy
        await agent._handle_strategy_update(web_priority_strategy._to_dict())
        
        context = ToolSelectionContext(
            objective="exploit web vulnerability",
            target_info={"ip": "192.168.1.50", "port": 80},
            available_tools=["nmap", "sqlmap", "nuclei"],
            phase="exploit",
            constraints=[],
            previous_results=[],
        )
        
        # Select tool (should reflect strategy)
        selection = await agent.select_tool(context)
        
        # Verify web tool selected due to strategy
        assert selection.tool_name == "sqlmap"
        assert "strategy" in selection.rationale.lower()

    @pytest.mark.asyncio
    async def test_e2e_avoid_targets_enforcement(
        self, agent, web_priority_strategy
    ):
        """E2E test: verify avoid_targets are enforced.
        
        Tests that targets in strategy.avoid_targets are filtered.
        """
        # Apply strategy (includes avoid_targets=["192.168.1.254"])
        await agent._handle_strategy_update(web_priority_strategy._to_dict())
        
        # Test avoid target filtering
        assert agent._is_target_avoided("192.168.1.254") is True
        assert agent._is_target_avoided("192.168.1.50") is False

    @pytest.mark.asyncio
    async def test_e2e_multiple_strategy_updates(
        self, agent, sample_pattern, context_tracker
    ):
        """E2E test: verify agent handles multiple strategy updates.
        
        Tests that agent properly updates when new strategy is received.
        """
        # First strategy: web focus
        strategy1 = EmergentStrategy(
            id="e2e-strategy-001",
            engagement_id="e2e-test-engagement",
            pattern=sample_pattern,
            objectives=["prioritize web vulnerabilities"],
            recommended_techniques=["T1190"],
            avoid_targets=["192.168.1.100"],
            confidence=0.8,
            timestamp=datetime.now(UTC).isoformat(),
        )
        
        await agent._handle_strategy_update(strategy1._to_dict())
        
        assert agent._active_strategy.id == "e2e-strategy-001"
        assert agent._is_target_avoided("192.168.1.100") is True
        
        # Second strategy: credential focus (replaces first)
        strategy2 = EmergentStrategy(
            id="e2e-strategy-002",
            engagement_id="e2e-test-engagement",
            pattern=sample_pattern,
            objectives=["credential harvesting"],
            recommended_techniques=["T1078"],
            avoid_targets=["192.168.1.200"],  # Different avoid list
            confidence=0.9,
            timestamp=datetime.now(UTC).isoformat(),
        )
        
        await agent._handle_strategy_update(strategy2._to_dict())
        
        # Verify second strategy replaced first
        assert agent._active_strategy.id == "e2e-strategy-002"
        assert "credential" in agent._active_strategy.objectives[0].lower()
        
        # Old avoid target no longer avoided (new strategy has different list)
        assert agent._is_target_avoided("192.168.1.100") is False
        assert agent._is_target_avoided("192.168.1.200") is True
        
        # Both strategies should be in context
        context = context_tracker.get_context(agent.agent_id)
        assert "e2e-strategy-001" in context
        assert "e2e-strategy-002" in context


# === E2E Test: Strategy Context in Prompts ===

class TestE2EStrategyPromptContext:
    """E2E tests for strategy context injection into LLM prompts."""

    @pytest.mark.asyncio
    async def test_e2e_full_strategy_context_in_prompt(
        self, agent, web_priority_strategy
    ):
        """Verify all strategy fields appear in tool selection prompt."""
        await agent._handle_strategy_update(web_priority_strategy._to_dict())
        
        context = ToolSelectionContext(
            objective="test",
            target_info={},
            available_tools=["nmap"],
            phase="exploit",
            constraints=[],
            previous_results=[],
        )
        
        prompt = agent._build_tool_selection_prompt(context)
        
        # Verify all strategy components present
        assert "Objectives:" in prompt
        assert "prioritize web vulnerabilities" in prompt
        assert "Recommended ATT&CK:" in prompt
        assert "T1190" in prompt
        assert "Avoid targets:" in prompt
        assert "192.168.1.254" in prompt

    @pytest.mark.asyncio
    async def test_e2e_strategy_context_empty_fields(self, agent, sample_pattern):
        """Verify strategy with empty fields still works."""
        minimal_strategy = EmergentStrategy(
            id="e2e-minimal-strategy",
            engagement_id="e2e-test-engagement",
            pattern=sample_pattern,
            objectives=[],  # Empty
            recommended_techniques=[],  # Empty
            avoid_targets=[],  # Empty
            confidence=0.7,
            timestamp=datetime.now(UTC).isoformat(),
        )
        
        await agent._handle_strategy_update(minimal_strategy._to_dict())
        
        # Should not crash, context should be empty string
        context_str = agent._get_strategy_context()
        assert context_str == ""


# === E2E Test: Decision Context Audit Trail ===

class TestE2EDecisionContextAudit:
    """E2E tests for NFR37 decision context tracking."""

    @pytest.mark.asyncio
    async def test_e2e_action_includes_strategy_in_audit(
        self, agent, web_priority_strategy, context_tracker
    ):
        """Verify action's decision_context includes strategy for audit."""
        await agent._handle_strategy_update(web_priority_strategy._to_dict())
        
        # Perform action
        action = await agent.execute("target.example.com")
        
        # Audit trail should include strategy
        assert len(action.decision_context) > 0
        assert web_priority_strategy.id in action.decision_context

    @pytest.mark.asyncio
    async def test_e2e_signal_type_weight_for_strategy(self, context_tracker):
        """Verify director_strategy has correct weight in tracker."""
        from cyberred.orchestration.emergence.tracker import SIGNAL_TYPE_WEIGHTS
        
        # director_strategy should have high weight (0.95)
        assert "director_strategy" in SIGNAL_TYPE_WEIGHTS
        assert SIGNAL_TYPE_WEIGHTS["director_strategy"] == 0.95

    @pytest.mark.asyncio
    async def test_e2e_strategy_signals_sorted_by_weight(
        self, agent, web_priority_strategy, context_tracker
    ):
        """Verify strategy signals are properly sorted in context."""
        # Record lower-weight signal first
        context_tracker.record_signal(
            agent_id=agent.agent_id,
            signal_id="low-weight-signal",
            signal_type="status",  # Weight: 0.3
            source="other-agent",
            channel="status:test",
        )
        
        # Apply strategy (weight: 0.95)
        await agent._handle_strategy_update(web_priority_strategy._to_dict())
        
        # Get context - strategy should be first due to higher weight
        context = context_tracker.get_context(agent.agent_id)
        
        # Strategy (0.95) should come before status (0.3)
        strategy_idx = context.index(web_priority_strategy.id)
        status_idx = context.index("low-weight-signal")
        assert strategy_idx < status_idx
