import pytest
from unittest.mock import Mock, AsyncMock, ANY
from datetime import datetime, UTC
import uuid
import asyncio
from cyberred.orchestration.emergence.tracker import DecisionContextTracker
from cyberred.core.models import AgentAction

@pytest.fixture
def event_bus():
    return AsyncMock()

@pytest.fixture
def tracker(event_bus):
    return DecisionContextTracker(
        engagement_id="test-engagement",
        event_bus=event_bus,
        max_history=5
    )

class TestDecisionContextTracker:

    def test_instantiation(self, tracker):
        assert tracker.engagement_id == "test-engagement"
        assert tracker.max_history == 5
        assert tracker.isolated_mode is False

    def test_record_signal(self, tracker):
        tracker.record_signal(
            agent_id="agent-1",
            signal_id="sig-1",
            signal_type="finding",
            source="agent-2"
        )
        
        context = tracker.get_context("agent-1")
        assert "sig-1" in context
        assert tracker.get_signal_count("agent-1") == 1

    def test_record_signal_max_history(self, tracker):
        for i in range(10):
            tracker.record_signal(
                agent_id="agent-1",
                signal_id=f"sig-{i}",
                signal_type="finding",
                source="agent-2"
            )
            
        assert tracker.get_signal_count("agent-1") == 5
        context = tracker.get_context("agent-1")
        # Should contain latest signals (5-9)
        assert "sig-9" in context
        assert "sig-0" not in context

    def test_get_context_sorting(self, tracker):
        # finding (weight 1.0)
        tracker.record_signal(
            "agent-1", "sig-finding", "finding", "src"
        )
        # status (weight 0.3)
        tracker.record_signal(
            "agent-1", "sig-status", "status", "src"
        )
        # strategy (weight 0.9)
        tracker.record_signal(
            "agent-1", "sig-strategy", "strategy", "src"
        )
        
        context = tracker.get_context("agent-1")
        assert context == ["sig-finding", "sig-strategy", "sig-status"]

    @pytest.mark.asyncio
    async def test_attach_to_action(self, tracker):
        agent_uuid = str(uuid.uuid4())
        tracker.record_signal(agent_uuid, "sig-1", "finding", "src")
        
        action_uuid = str(uuid.uuid4())
        
        action = AgentAction(
            id=action_uuid,
            agent_id=agent_uuid,
            action_type="execute",
            target="192.168.1.1",
            timestamp=datetime.now(UTC).isoformat()
        )
        
        updated_action = tracker.attach_to_action(agent_uuid, action)
        
        assert updated_action.decision_context == ["sig-1"]
        # Context should be cleared
        assert tracker.get_signal_count(agent_uuid) == 0
        
        # Wait for background task to publish
        await asyncio.sleep(0.1)
        
        # Audit event should be published
        tracker.event_bus.publish.assert_called_with(
            "audit:decision_context",
            ANY
        )

    @pytest.mark.asyncio
    async def test_isolated_mode(self, event_bus):
        iso_tracker = DecisionContextTracker(
            "eng-1", event_bus, isolated_mode=True
        )
        
        iso_tracker.record_signal("agent-1", "sig-1", "finding", "src")
        
        # Signals should not be recorded
        assert iso_tracker.get_signal_count("agent-1") == 0
        
        # Context should be isolated marker
        assert iso_tracker.get_context("agent-1") == ["isolated_mode"]
        
        agent_uuid = str(uuid.uuid4())
        action_uuid = str(uuid.uuid4())
        
        action = AgentAction(
            id=action_uuid,
            agent_id=agent_uuid,
            action_type="execute",
            target="192.168.1.1",
            timestamp=datetime.now(UTC).isoformat()
        )
        
        updated = iso_tracker.attach_to_action(agent_uuid, action)
        assert updated.decision_context == ["isolated_mode"]
        
        # Wait for async task (even if isolated might not trigger it, but loop is needed)
        await asyncio.sleep(0.1)

    def test_unknown_agent(self, tracker):
        assert tracker.get_context("unknown") == []
        assert tracker.get_signal_count("unknown") == 0

    def test_clear_context(self, tracker):
        tracker.record_signal("agent-1", "sig-1", "finding", "src")
        tracker.clear_context("agent-1")
        assert tracker.get_signal_count("agent-1") == 0

    def test_get_all_agents(self, tracker):
        tracker.record_signal("agent-1", "s1", "finding", "src")
        tracker.record_signal("agent-2", "s2", "finding", "src")
        
        agents = tracker.get_all_agents()
        assert "agent-1" in agents
        assert "agent-2" in agents
        assert len(agents) == 2

    @pytest.mark.asyncio
    async def test_audit_publish_failure(self, tracker):
        # Mock event bus to raise exception
        tracker.event_bus.publish.side_effect = Exception("Publish failed")
        
        agent_uuid = str(uuid.uuid4())
        tracker.record_signal(agent_uuid, "sig-1", "finding", "src")
        
        action = AgentAction(
            id=str(uuid.uuid4()),
            agent_id=agent_uuid,
            action_type="execute",
            target="192.168.1.1",
            timestamp=datetime.now(UTC).isoformat()
        )
        
        # Should not raise exception
        tracker.attach_to_action(agent_uuid, action)
        
        await asyncio.sleep(0.1)
        
        # Verify publish called (and failed gracefully)
        tracker.event_bus.publish.assert_called_once()

def test_attach_to_action_no_event_loop():
    """Test attach_to_action gracefully handles missing event loop (HIGH issue fix)."""
    from cyberred.orchestration.emergence.tracker import DecisionContextTracker
    from cyberred.core.models import AgentAction
    from unittest.mock import MagicMock
    import uuid
    from datetime import datetime, timezone
    
    event_bus = MagicMock()
    tracker = DecisionContextTracker("test-eng", event_bus)
    
    # Record a signal
    tracker.record_signal("agent-1", "sig-1", "finding", "source-1")
    
    # Create action with correct AgentAction fields
    action = AgentAction(
        id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        action_type="test",
        target="192.168.1.1",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    
    # Call attach_to_action WITHOUT a running event loop
    # This should NOT raise RuntimeError - it should log a warning instead
    result = tracker.attach_to_action("agent-1", action)
    
    # Action should still have context attached
    assert "sig-1" in result.decision_context
    # Context should be cleared after attachment
    assert tracker.get_context("agent-1") == []
