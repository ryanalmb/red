"""
Cyber-Red v2.0 Emergence Tests: Decision Context Validation

Tests for 100% decision_context population (NFR37).
All tests are marked with @pytest.mark.emergence and are hard gate tests.
"""

import pytest
import uuid
from datetime import datetime, UTC
from cyberred.core.models import AgentAction
from cyberred.orchestration.emergence.validator import validate_decision_context

def create_action(context=None):
    if context is None:
        context = []
    return AgentAction(
        id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        action_type="test",
        target="192.168.1.1",
        timestamp=datetime.now(UTC).isoformat(),
        decision_context=context
    )

@pytest.mark.emergence
class TestDecisionContextPopulation:
    """Test decision_context is populated for all agent actions."""

    def test_decision_context_100_percent_population(self):
        """Verify 100% of agent actions have decision_context populated (HARD GATE: NFR37)."""
        actions = [
            create_action(["s1"]),
            create_action(["s2"]),
        ]
        result = validate_decision_context(actions)
        assert result.passed
        assert result.percentage == 100.0

    def test_decision_context_not_empty(self):
        """Verify decision_context is not an empty list for stigmergic actions."""
        action = create_action([])
        result = validate_decision_context([action])
        assert not result.passed
        assert result.failed_actions == [action.id]

    def test_decision_context_population_gate_fails_on_missing(self):
        """Verify gate fails if any action is missing decision_context."""
        actions = [
            create_action(["s1"]),
            create_action([]),
        ]
        result = validate_decision_context(actions)
        assert not result.passed
        assert result.percentage == 50.0

@pytest.mark.emergence
class TestDecisionContextFormat:
    """Test decision_context format and structure."""

    def test_decision_context_contains_finding_ids(self):
        """Verify decision_context contains IDs of influencing findings."""
        action = create_action(["finding:123"])
        assert "finding:123" in action.decision_context
        assert isinstance(action.decision_context, list)
        assert isinstance(action.decision_context[0], str)

    def test_decision_context_is_list_of_strings(self):
        """Verify decision_context is List[str] format."""
        action = create_action(["s1", "s2"])
        assert isinstance(action.decision_context, list)
        assert all(isinstance(x, str) for x in action.decision_context)

@pytest.mark.emergence
class TestDecisionContextStigmergic:
    """Test decision_context reflects stigmergic coordination."""

    def test_decision_context_different_in_isolated_mode(self):
        """Verify decision_context is minimal/different in isolated (non-stigmergic) mode."""
        actions = [
            create_action(["isolated_mode"]),
        ]
        result = validate_decision_context(actions, isolated_mode=True)
        assert result.passed

    def test_decision_context_ids_are_valid(self):
        """Verify decision_context IDs follow expected format (non-empty strings)."""
        # Valid IDs should be non-empty strings
        valid_ids = ["finding:abc123", "strategy:xyz", "intel:cve-2024-1234"]
        action = create_action(valid_ids)
        
        # All IDs should be valid strings
        for ctx_id in action.decision_context:
            assert isinstance(ctx_id, str)
            assert len(ctx_id) > 0
            # IDs should not contain null bytes or be whitespace-only
            assert "\x00" not in ctx_id
            assert ctx_id.strip() == ctx_id
        
        result = validate_decision_context([action])
        assert result.passed

    def test_decision_context_traceable_to_source(self):
        """Verify decision_context IDs can be traced back to signal sources."""
        from cyberred.orchestration.emergence.tracker import DecisionContextTracker
        from unittest.mock import AsyncMock
        
        # Create tracker and record signals with known sources
        event_bus = AsyncMock()
        tracker = DecisionContextTracker("test-eng", event_bus)
        
        # Record signals from different sources
        tracker.record_signal("agent-1", "finding:sqli-001", "finding", "recon-agent-1")
        tracker.record_signal("agent-1", "strategy:exploit-web", "strategy", "director-ensemble")
        tracker.record_signal("agent-1", "intel:cve-2024-5678", "intel", "nvd-source")
        
        # Get context and verify all recorded signals are present
        context = tracker.get_context("agent-1")
        
        assert "finding:sqli-001" in context
        assert "strategy:exploit-web" in context
        assert "intel:cve-2024-5678" in context
        
        # Verify we can trace back - signals are retrievable
        assert len(context) == 3

    def test_decision_context_reflects_pubsub_signals(self):
        """Verify decision_context accurately reflects received pub/sub signals."""
        from cyberred.orchestration.emergence.tracker import DecisionContextTracker
        from unittest.mock import AsyncMock
        
        event_bus = AsyncMock()
        tracker = DecisionContextTracker("test-eng", event_bus)
        
        # Simulate pub/sub signal reception pattern
        pubsub_signals = [
            {"agent_id": "agent-1", "signal_id": "sig-pub-1", "type": "finding", "source": "other-agent", "channel": "findings:target:sqli"},
            {"agent_id": "agent-1", "signal_id": "sig-pub-2", "type": "strategy", "source": "director", "channel": "strategies:eng-1"},
            {"agent_id": "agent-1", "signal_id": "sig-pub-3", "type": "phase", "source": "orchestrator", "channel": "phase:transition"},
        ]
        
        # Record each signal as if received via pub/sub
        for sig in pubsub_signals:
            tracker.record_signal(
                agent_id=sig["agent_id"],
                signal_id=sig["signal_id"],
                signal_type=sig["type"],
                source=sig["source"],
                channel=sig["channel"],
            )
        
        # Get context and verify it reflects all pub/sub signals
        context = tracker.get_context("agent-1")
        
        # All signal IDs should be present
        for sig in pubsub_signals:
            assert sig["signal_id"] in context, f"Missing signal: {sig['signal_id']}"
        
        # Context should be ordered by weight (finding > strategy > phase)
        assert context.index("sig-pub-1") < context.index("sig-pub-3")  # finding before phase
