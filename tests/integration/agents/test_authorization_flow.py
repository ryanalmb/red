"""Integration tests for Agent Authorization Flow (Story 7.16).

Tests the complete authorization lifecycle including:
- Authorization request publishing
- Waiting for operator response
- Grant/deny handling
- State transitions
- Decision context population
"""

import asyncio
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# Create a proper mock class for swarms.Agent that can be subclassed
class MockSwarmsAgent:
    """Mock swarms.Agent base class for testing."""
    def __init__(self, *args, **kwargs):
        self.agent_name = kwargs.get("agent_name", "mock-agent")
        self.system_prompt = kwargs.get("system_prompt", "")


# Mock swarms before importing agents to avoid MCP import error
if "swarms" not in sys.modules:
    mock_swarms_module = MagicMock()
    mock_swarms_module.Agent = MockSwarmsAgent
    sys.modules["swarms"] = mock_swarms_module
else:
    # Ensure Agent is a proper class that can be inherited
    sys.modules["swarms"].Agent = MockSwarmsAgent


class TestAuthorizationGrantFlow:
    """Test authorization grant scenarios."""

    @pytest.mark.asyncio
    async def test_authorization_grant_full_flow(self):
        """Test complete authorization grant flow with EventBus."""
        from cyberred.core.events import EventBus
        from cyberred.storage.redis_client import PubSubSubscription

        # Setup mock Redis
        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)
        
        captured_callback = None
        async def capture_subscribe(channel, callback):
            nonlocal captured_callback
            captured_callback = callback
            return PubSubSubscription(pattern=channel, unsubscribe=AsyncMock())
        
        mock_redis.subscribe = AsyncMock(side_effect=capture_subscribe)
        
        event_bus = EventBus(mock_redis)
        
        # Simulate operator grant response
        async def simulate_grant():
            await asyncio.sleep(0.05)
            if captured_callback:
                await captured_callback(
                    "auth:test-req:response",
                    '{"granted": true, "operator_id": "op-1", "reason": "approved"}'
                )
        
        # Start grant simulation and subscribe_once concurrently
        grant_task = asyncio.create_task(simulate_grant())
        result = await event_bus.subscribe_once("auth:test-req:response", timeout=5.0)
        await grant_task
        
        assert result is not None
        assert result["granted"] is True
        assert result["operator_id"] == "op-1"

    @pytest.mark.asyncio
    async def test_authorization_denial_full_flow(self):
        """Test complete authorization denial flow."""
        from cyberred.core.events import EventBus
        from cyberred.storage.redis_client import PubSubSubscription

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)
        
        captured_callback = None
        async def capture_subscribe(channel, callback):
            nonlocal captured_callback
            captured_callback = callback
            return PubSubSubscription(pattern=channel, unsubscribe=AsyncMock())
        
        mock_redis.subscribe = AsyncMock(side_effect=capture_subscribe)
        
        event_bus = EventBus(mock_redis)
        
        # Simulate operator denial
        async def simulate_deny():
            await asyncio.sleep(0.05)
            if captured_callback:
                await captured_callback(
                    "auth:test-req:response",
                    '{"granted": false, "operator_id": "op-1", "reason": "out of scope"}'
                )
        
        deny_task = asyncio.create_task(simulate_deny())
        result = await event_bus.subscribe_once("auth:test-req:response", timeout=5.0)
        await deny_task
        
        assert result is not None
        assert result["granted"] is False
        assert result["reason"] == "out of scope"


class TestStateTransitions:
    """Test agent state transitions during authorization."""

    @pytest.mark.asyncio
    async def test_state_transition_running_to_waiting(self):
        """Test RUNNING -> WAITING_AUTHORIZATION state transition."""
        from cyberred.core.events import EventBus
        from cyberred.agents.roles import AgentRole
        from cyberred.agents.base import StigmergicAgent

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)
        event_bus = EventBus(mock_redis)

        agent = StigmergicAgent(
            agent_name="StateTestAgent",
            agent_id="state-agent-1",
            engagement_id="eng-state-1",
            event_bus=event_bus,
            role=AgentRole.POSTEX,
        )
        agent._status = "active"  # Set initial state

        # Mock subscribe_once to capture state during wait
        states_observed = []

        async def mock_subscribe_once(channel, timeout=None):
            # Record state when waiting starts
            states_observed.append(("waiting_started", agent._status))
            await asyncio.sleep(0.01)
            return {"granted": True, "operator_id": "op-1"}

        # Use patch to replace the method
        event_bus.subscribe_once = mock_subscribe_once

        await agent._request_authorization(
            action="lateral_movement",
            target="192.168.1.50",
            justification="Test",
            alternative_on_denial=False,
        )

        # Verify state was WAITING_AUTHORIZATION during wait
        assert ("waiting_started", "waiting_authorization") in states_observed
        # Verify final state is active (after grant)
        assert agent._status == "active"

    @pytest.mark.asyncio
    async def test_state_transition_waiting_to_running_on_grant(self):
        """Test WAITING_AUTHORIZATION -> RUNNING on grant."""
        from cyberred.core.events import EventBus
        from cyberred.agents.roles import AgentRole
        from cyberred.agents.base import StigmergicAgent

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)
        event_bus = EventBus(mock_redis)

        agent = StigmergicAgent(
            agent_name="StateTestAgent",
            agent_id="state-agent-2",
            engagement_id="eng-state-2",
            event_bus=event_bus,
            role=AgentRole.POSTEX,
        )

        async def mock_subscribe_once(channel, timeout=None):
            return {"granted": True}

        event_bus.subscribe_once = mock_subscribe_once

        result = await agent._request_authorization(
            action="lateral_movement",
            target="test",
            justification="test",
            alternative_on_denial=False,
        )

        assert result is True
        assert agent._status == "active"


class TestDecisionContextTracking:
    """Test decision context population for authorization events."""

    @pytest.mark.asyncio
    async def test_authorization_grant_recorded_in_context(self):
        """Test authorization grant is recorded in decision_context."""
        from cyberred.core.events import EventBus
        from cyberred.agents.roles import AgentRole
        from cyberred.agents.base import StigmergicAgent

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)
        event_bus = EventBus(mock_redis)

        agent = StigmergicAgent(
            agent_name="ContextTestAgent",
            agent_id="ctx-agent-1",
            engagement_id="eng-ctx-1",
            event_bus=event_bus,
            role=AgentRole.POSTEX,
        )

        async def mock_subscribe_once(channel, timeout=None):
            return {"granted": True, "operator_id": "op-1"}

        event_bus.subscribe_once = mock_subscribe_once

        await agent._request_authorization(
            action="lateral_movement",
            target="test",
            justification="test",
            alternative_on_denial=False,
        )

        context = agent.get_decision_context()
        # Should contain auth:{request_id}:granted
        assert any("auth:" in c and ":granted" in c for c in context)

    @pytest.mark.asyncio
    async def test_authorization_denial_recorded_in_context(self):
        """Test authorization denial is recorded in decision_context."""
        from cyberred.core.events import EventBus
        from cyberred.agents.roles import AgentRole
        from cyberred.agents.base import StigmergicAgent

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)
        event_bus = EventBus(mock_redis)

        agent = StigmergicAgent(
            agent_name="ContextTestAgent",
            agent_id="ctx-agent-2",
            engagement_id="eng-ctx-2",
            event_bus=event_bus,
            role=AgentRole.POSTEX,
        )

        async def mock_subscribe_once(channel, timeout=None):
            return {"granted": False, "reason": "denied"}

        event_bus.subscribe_once = mock_subscribe_once

        await agent._request_authorization(
            action="lateral_movement",
            target="test",
            justification="test",
            alternative_on_denial=False,
        )

        context = agent.get_decision_context()
        # Should contain auth:{request_id}:denied
        assert any("auth:" in c and ":denied" in c for c in context)

    @pytest.mark.asyncio
    async def test_decision_context_tracker_records_authorization(self):
        """Test DecisionContextTracker records authorization signal type."""
        from cyberred.core.events import EventBus
        from cyberred.agents.roles import AgentRole
        from cyberred.agents.base import StigmergicAgent
        from cyberred.orchestration.emergence.tracker import DecisionContextTracker

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)
        event_bus = EventBus(mock_redis)

        tracker = DecisionContextTracker(
            engagement_id="eng-tracker-1",
            event_bus=event_bus,
        )

        agent = StigmergicAgent(
            agent_name="TrackerTestAgent",
            agent_id="tracker-agent-1",
            engagement_id="eng-tracker-1",
            event_bus=event_bus,
            role=AgentRole.POSTEX,
            context_tracker=tracker,
        )

        async def mock_subscribe_once(channel, timeout=None):
            return {"granted": True, "operator_id": "op-1"}

        event_bus.subscribe_once = mock_subscribe_once

        await agent._request_authorization(
            action="lateral_movement",
            target="test",
            justification="test",
            alternative_on_denial=False,
        )

        # Verify tracker has the authorization signal
        context = tracker.get_context("tracker-agent-1")
        assert any("auth:" in c and ":granted" in c for c in context)


class TestIndefiniteWait:
    """Test FR16 compliance - indefinite wait (no auto-deny)."""

    @pytest.mark.asyncio
    async def test_subscribe_once_indefinite_wait_no_timeout(self):
        """Test subscribe_once with timeout=None waits indefinitely."""
        from cyberred.core.events import EventBus
        from cyberred.storage.redis_client import PubSubSubscription

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)

        captured_callback = None
        async def capture_subscribe(channel, callback):
            nonlocal captured_callback
            captured_callback = callback
            return PubSubSubscription(pattern=channel, unsubscribe=AsyncMock())

        mock_redis.subscribe = AsyncMock(side_effect=capture_subscribe)

        event_bus = EventBus(mock_redis)

        # Simulate delayed response (longer than typical timeout)
        async def delayed_response():
            await asyncio.sleep(0.5)  # 500ms delay
            if captured_callback:
                await captured_callback(
                    "auth:delayed:response",
                    '{"granted": true}'
                )

        response_task = asyncio.create_task(delayed_response())
        
        # No timeout - should wait for the delayed response
        result = await event_bus.subscribe_once("auth:delayed:response", timeout=None)
        
        await response_task

        assert result is not None
        assert result["granted"] is True


class TestPostExAgentInheritance:
    """Test PostExAgent uses inherited _request_authorization."""

    @pytest.mark.asyncio
    async def test_postex_agent_inherits_request_authorization(self):
        """Test PostExAgent inherits _request_authorization from base class."""
        from cyberred.core.events import EventBus
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.postex import PostExAgent

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)
        event_bus = EventBus(mock_redis)

        agent = PostExAgent(
            agent_id="postex-inherit-1",
            engagement_id="eng-inherit-1",
            event_bus=event_bus,
            specialty="linux",
        )

        # Verify the method comes from base class
        assert hasattr(agent, "_request_authorization")
        
        async def mock_subscribe_once(channel, timeout=None):
            return {"granted": True, "operator_id": "op-1"}

        event_bus.subscribe_once = mock_subscribe_once

        # Call it and verify it works
        result = await agent._request_authorization(
            action="lateral_movement",
            target="192.168.1.50",
            justification="Test credentials found",
            alternative_on_denial=False,
        )

        assert result is True


class TestAlternativeActionSelection:
    """Test alternative action selection on authorization denial."""

    @pytest.mark.asyncio
    async def test_denial_with_alternative_action_selection(self):
        """Test that denial triggers alternative action selection when enabled."""
        from cyberred.core.events import EventBus
        from cyberred.agents.roles import AgentRole
        from cyberred.agents.base import StigmergicAgent

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)
        event_bus = EventBus(mock_redis)

        # Create mock LLM gateway for alternative selection
        mock_gateway = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"tool_name": "linpeas", "command": "linpeas.sh", "rationale": "Local enum instead", "expected_output_type": "text", "confidence": 0.8, "priority": 5}'
        mock_gateway.agent_complete = AsyncMock(return_value=mock_response)

        agent = StigmergicAgent(
            agent_name="AlternativeTestAgent",
            agent_id="alt-agent-1",
            engagement_id="eng-alt-1",
            event_bus=event_bus,
            role=AgentRole.POSTEX,
            llm_gateway=mock_gateway,
        )

        async def mock_subscribe_once(channel, timeout=None):
            return {"granted": False, "reason": "lateral movement denied"}

        event_bus.subscribe_once = mock_subscribe_once

        result = await agent._request_authorization(
            action="lateral_movement",
            target="192.168.1.50",
            justification="Test",
            alternative_on_denial=True,  # Enable alternative selection
        )

        assert result is False
        # Agent should have called LLM for alternative
        mock_gateway.agent_complete.assert_called()
        # State should be active after alternative selection
        assert agent._status == "active"

    @pytest.mark.asyncio
    async def test_denial_without_alternative_selection(self):
        """Test denial without alternative selection returns to previous state."""
        from cyberred.core.events import EventBus
        from cyberred.agents.roles import AgentRole
        from cyberred.agents.base import StigmergicAgent

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock(return_value=1)
        event_bus = EventBus(mock_redis)

        agent = StigmergicAgent(
            agent_name="NoAltTestAgent",
            agent_id="noalt-agent-1",
            engagement_id="eng-noalt-1",
            event_bus=event_bus,
            role=AgentRole.POSTEX,
        )
        agent._status = "active"  # Set initial state

        async def mock_subscribe_once(channel, timeout=None):
            return {"granted": False, "reason": "denied"}

        event_bus.subscribe_once = mock_subscribe_once

        result = await agent._request_authorization(
            action="lateral_movement",
            target="test",
            justification="test",
            alternative_on_denial=False,  # Disable alternative selection
        )

        assert result is False
        # State should be restored to previous
        assert agent._status == "active"
