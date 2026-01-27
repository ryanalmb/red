from dataclasses import dataclass

from cyberred.core.models import AgentAction


@dataclass
class ValidationResult:
    """Result of decision_context validation.

    Attributes:
        passed: Whether validation passed (100% populated).
        percentage: Percentage of actions with decision_context.
        failed_actions: List of action IDs missing decision_context.
        total_actions: Total number of actions validated.
    """
    passed: bool
    percentage: float
    failed_actions: list[str]
    total_actions: int


def validate_decision_context(
    actions: list[AgentAction],
    isolated_mode: bool = False,
) -> ValidationResult:
    """Validate that all actions have decision_context populated.

    NFR37 HARD GATE: 100% of agent actions must have decision_context.

    Args:
        actions: List of AgentAction instances to validate.
        isolated_mode: If True, accepts ["isolated_mode"] as valid.

    Returns:
        ValidationResult with pass/fail and statistics.
    """
    if not actions:
        return ValidationResult(
            passed=True,
            percentage=100.0,
            failed_actions=[],
            total_actions=0,
        )

    failed_actions: list[str] = []

    for action in actions:
        if not action.decision_context:
            failed_actions.append(action.id)
        elif isolated_mode and action.decision_context != ["isolated_mode"]:
            # In isolated mode, context should be exactly ["isolated_mode"]
            failed_actions.append(action.id)

    populated = len(actions) - len(failed_actions)
    percentage = (populated / len(actions)) * 100.0

    return ValidationResult(
        passed=len(failed_actions) == 0,
        percentage=percentage,
        failed_actions=failed_actions,
        total_actions=len(actions),
    )


def check_hard_gate(result: ValidationResult) -> bool:
    """Check if result passes NFR37 hard gate (100% required).

    Args:
        result: ValidationResult to check.

    Returns:
        True if 100% decision_context population, False otherwise.
    """
    return result.passed and result.percentage == 100.0
