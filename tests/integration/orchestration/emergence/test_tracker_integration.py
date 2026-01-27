import pytest
from unittest.mock import MagicMock, AsyncMock, ANY
from cyberred.orchestration.emergence.tracker import DecisionContextTracker
from cyberred.core.events import EventBus
from cyberred.core.models import AgentAction
from cyberred.agents.base import StigmergicAgent
from cyberred.agents.roles import AgentRole
import uuid
import asyncio
from datetime import datetime, UTC

@pytest.fixture
def event_bus():
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock()
    return bus

@pytest.fixture
def tracker(event_bus):
    return DecisionContextTracker(
        engagement_id="test-integration",
        event_bus=event_bus
    )

class ConcreteStigmergicAgent(StigmergicAgent):
    """Concrete implementation for testing."""
    pass

@pytest.mark.asyncio
@pytest.mark.integration
async def test_tracker_publishes_to_audit(tracker, event_bus):
    agent_id = str(uuid.uuid4())
    tracker.record_signal(agent_id, "sig-1", "finding", "src")
    
    action = AgentAction(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        action_type="execute",
        target="192.168.1.1",
        timestamp=datetime.now(UTC).isoformat()
    )
    
    tracker.attach_to_action(agent_id, action)
    
    # Wait for background task
    await asyncio.sleep(0.1)
    
    # Verify publish called
    event_bus.publish.assert_called_once()
    args = event_bus.publish.call_args[0]
    channel = args[0]
    data = args[1]
    
    assert channel == "audit:decision_context"
    assert data["engagement_id"] == "test-integration"
    assert data["agent_id"] == agent_id
    assert data["action_id"] == action.id
    assert data["context_ids"] == ["sig-1"]
    assert "timestamp" in data

@pytest.mark.asyncio
@pytest.mark.integration
async def test_stigmergic_agent_integration(event_bus, tracker):
    # Initialize agent with mocked dependencies
    agent = ConcreteStigmergicAgent(
        agent_name="test-agent",
        agent_id=str(uuid.uuid4()),
        engagement_id="test-integration",
        event_bus=event_bus,
        role=AgentRole.RECON,
        llm_gateway=MagicMock(),
        context_tracker=tracker
    )
    
    # Simulate receiving a signal
    channel = "findings:target:sqli"
    data = {"signal_id": "sig-found-1", "agent_id": "other-agent"}
    
    await agent.on_signal(channel, data)
    
    # Check if tracker recorded it
    context = tracker.get_context(agent.agent_id)
    assert "sig-found-1" in context
    
    # Now simulate execute and verify context attachment
    action = await agent.execute("192.168.1.1")
    assert action.decision_context == ["sig-found-1"]
    
    # Context should be cleared after attachment
    assert tracker.get_context(agent.agent_id) == []
