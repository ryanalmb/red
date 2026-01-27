import pytest
import uuid
from datetime import datetime, UTC
from cyberred.orchestration.emergence.validator import validate_decision_context, ValidationResult, check_hard_gate
from cyberred.core.models import AgentAction

def create_action(context=None):
    if context is None:
        context = []
    return AgentAction(
        id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        action_type="execute",
        target="192.168.1.1",
        timestamp=datetime.now(UTC).isoformat(),
        decision_context=context
    )

class TestDecisionContextValidator:
    def test_validate_decision_context_pass(self):
        actions = [
            create_action(["sig-1"]),
            create_action(["sig-2"]),
        ]
        result = validate_decision_context(actions)
        assert result.passed is True
        assert result.percentage == 100.0
        assert check_hard_gate(result) is True

    def test_validate_decision_context_fail(self):
        a1 = create_action(["sig-1"])
        a2 = create_action([])
        actions = [a1, a2]
        
        result = validate_decision_context(actions)
        assert result.passed is False
        assert result.percentage == 50.0
        assert result.failed_actions == [a2.id]
        assert check_hard_gate(result) is False

    def test_validate_empty_actions(self):
        result = validate_decision_context([])
        assert result.passed is True
        assert result.percentage == 100.0

    def test_isolated_mode_pass(self):
        actions = [
            create_action(["isolated_mode"]),
        ]
        result = validate_decision_context(actions, isolated_mode=True)
        assert result.passed is True
        assert check_hard_gate(result) is True

    def test_isolated_mode_fail(self):
        a1 = create_action(["other_signal"])
        actions = [a1]
        result = validate_decision_context(actions, isolated_mode=True)
        assert result.passed is False
        assert result.failed_actions == [a1.id]