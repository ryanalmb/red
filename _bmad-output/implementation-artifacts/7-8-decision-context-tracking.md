# Story 7.8: Decision Context Tracking

Status: done

## Story

As a **developer**,
I want **100% decision_context population for all agent actions**,
so that **we can validate emergence behavior and maintain audit trails (NFR37)**.

> [!IMPORTANT]
> **HARD GATE:** NFR37 requires 100% of agent actions to include `decision_context` linking to influencing stigmergic signals. This is CRITICAL for emergence validation and proves agents are responding to shared information, not acting in isolation.

## Acceptance Criteria

1. **DecisionContextTracker class implementation**
   - `tracker = DecisionContextTracker(engagement_id, event_bus)` creates tracker instance
   - `tracker.record_signal(agent_id, signal_id, signal_type, source)` records incoming signal
   - `tracker.get_context(agent_id) -> list[str]` returns signal IDs that influenced agent
   - `tracker.attach_to_action(action: AgentAction) -> AgentAction` populates decision_context
   - Tracker maintains per-agent signal history with timestamps
   - Signal history is bounded (configurable max, default 100 per agent)

2. **Signal types tracked**
   - `finding:*` - Findings published by other agents
   - `strategy:*` - Director Ensemble strategy publications
   - `intel:*` - Intelligence enrichment results
   - `rag:*` - RAG escalation results
   - `phase:*` - Phase transition signals
   - Each signal type has weight for relevance scoring

3. **Integration with StigmergicAgent base class**
   - `on_signal()` method automatically records to tracker
   - `execute()` method automatically attaches context to returned AgentAction
   - `get_decision_context()` delegates to tracker for current context
   - Context is cleared after action completion (fresh for next action)

4. **Audit stream integration**
   - All context attachments published to `audit:decision_context` stream
   - Audit entries include: agent_id, action_id, context_ids, timestamp
   - Audit stream supports replay for post-engagement analysis

5. **Validation gate implementation**
   - `validate_decision_context(actions: list[AgentAction]) -> ValidationResult`
   - Returns pass/fail with percentage populated
   - Hard gate: 100% required for NFR37 compliance
   - Gate integrated into CI pipeline

6. **Isolated mode support**
   - When `stigmergic_enabled=False`, decision_context contains only `["isolated_mode"]`
   - This differentiates isolated runs from stigmergic runs in emergence testing
   - Isolated mode is configurable via engagement config

7. **Quality gates**
   - 100% unit test coverage for `src/cyberred/orchestration/emergence/tracker.py`
   - Integration tests verify context flows through agent lifecycle
   - Placeholder tests in `tests/emergence/test_decision_context.py` fully implemented

## Tasks / Subtasks

### Phase 1 (RED): Tests first

- [x] Create `tests/unit/orchestration/emergence/test_tracker.py`
  - [x] `DecisionContextTracker` instantiation with engagement_id and event_bus
  - [x] `record_signal()` stores signal with agent_id, signal_id, type, source, timestamp
  - [x] `record_signal()` respects max history bound (drops oldest)
  - [x] `get_context()` returns list of signal IDs for agent
  - [x] `get_context()` returns empty list for unknown agent
  - [x] `attach_to_action()` populates decision_context field
  - [x] `attach_to_action()` clears context after attachment
  - [x] `clear_context()` removes all signals for agent
  - [x] Signal type weights affect relevance ordering
  - [x] Isolated mode returns `["isolated_mode"]` only

- [x] Create `tests/unit/orchestration/emergence/test_validator.py`
  - [x] `validate_decision_context()` returns 100% for fully populated actions
  - [x] `validate_decision_context()` returns 0% for empty decision_context
  - [x] `validate_decision_context()` calculates correct percentage
  - [x] Validation fails if any action has empty decision_context (non-isolated)
  - [x] Validation passes if isolated_mode actions have `["isolated_mode"]`

- [x] Update `tests/emergence/test_decision_context.py`
  - [x] Remove `pytest.skip()` from all placeholder tests
  - [x] Implement `test_decision_context_100_percent_population()`
  - [x] Implement `test_decision_context_not_empty()`
  - [x] Implement `test_decision_context_contains_finding_ids()`
  - [x] Implement `test_decision_context_ids_are_valid()`
  - [x] Implement `test_decision_context_traceable_to_source()`
  - [x] Implement `test_decision_context_reflects_pubsub_signals()`
  - [x] Implement `test_decision_context_different_in_isolated_mode()`

- [x] Create `tests/integration/orchestration/emergence/test_tracker_integration.py`
  - [x] Tracker + EventBus integration (real pub/sub)
  - [x] Tracker + StigmergicAgent integration
  - [x] Audit stream receives context attachments
  - [x] Full lifecycle: signal → record → action → audit

### Phase 2 (GREEN): Minimal implementation

- [x] Create `src/cyberred/orchestration/emergence/__init__.py`
  - [x] Export `DecisionContextTracker`
  - [x] Export `validate_decision_context`
  - [x] Export `ValidationResult`

- [x] Create `src/cyberred/orchestration/emergence/tracker.py`
  - [x] `SIGNAL_TYPE_WEIGHTS` constants for relevance scoring
  - [x] `SignalRecord` dataclass (signal_id, signal_type, source, timestamp, weight)
  - [x] `DecisionContextTracker` class
  - [x] `__init__(engagement_id, event_bus, max_history=100, isolated_mode=False)`
  - [x] `record_signal(agent_id, signal_id, signal_type, source) -> None`
  - [x] `get_context(agent_id) -> list[str]`
  - [x] `attach_to_action(agent_id, action: AgentAction) -> AgentAction`
  - [x] `clear_context(agent_id) -> None`
  - [x] `get_all_agents() -> list[str]`
  - [x] `get_signal_count(agent_id) -> int`
  - [x] `_publish_audit(agent_id, action_id, context_ids) -> None`

- [x] Create `src/cyberred/orchestration/emergence/validator.py`
  - [x] `ValidationResult` dataclass (passed, percentage, failed_actions, total_actions)
  - [x] `validate_decision_context(actions: list[AgentAction], isolated_mode=False) -> ValidationResult`
  - [x] `check_hard_gate(result: ValidationResult) -> bool` (100% required)

- [x] Update `src/cyberred/agents/base.py`
  - [x] Add `_context_tracker: DecisionContextTracker | None` attribute
  - [x] Update `__init__()` to accept optional tracker
  - [x] Update `on_signal()` to call `tracker.record_signal()` if tracker present
  - [x] Update `execute()` to call `tracker.attach_to_action()` if tracker present
  - [x] Update `get_decision_context()` to use tracker if present

- [x] Update `src/cyberred/orchestration/__init__.py`
  - [x] Export emergence submodule

### Phase 3 (REFACTOR): Quality

- [x] Achieve 100% coverage: `pytest tests/unit/orchestration/emergence/ tests/integration/orchestration/emergence/ --cov=src/cyberred/orchestration/emergence`
- [x] Lint clean: `ruff check src/cyberred/orchestration/emergence/`
- [x] Type check: `mypy src/cyberred/orchestration/emergence/`
- [x] Update all placeholder tests in `tests/emergence/test_decision_context.py`

## Dev Notes

### Signal type weights (relevance scoring)

```python
SIGNAL_TYPE_WEIGHTS: dict[str, float] = {
    "finding": 1.0,      # Direct findings from other agents - highest weight
    "strategy": 0.9,     # Director Ensemble strategies - high weight
    "intel": 0.8,        # Intelligence enrichment results
    "rag": 0.7,          # RAG escalation results
    "phase": 0.6,        # Phase transitions
    "status": 0.3,       # Agent status updates - low weight
}
```

### SignalRecord dataclass

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class SignalRecord:
    """Record of a stigmergic signal received by an agent.
    
    Attributes:
        signal_id: Unique identifier for the signal (Finding.id, strategy.id, etc.)
        signal_type: Type of signal (finding, strategy, intel, rag, phase, status)
        source: Source agent/component ID
        timestamp: When signal was received
        weight: Relevance weight based on signal_type
        channel: Original Redis channel the signal came from
    """
    signal_id: str
    signal_type: str
    source: str
    timestamp: datetime
    weight: float
    channel: str
```

### DecisionContextTracker class structure

```python
from collections import defaultdict
from datetime import datetime, UTC
from typing import Any

import structlog

from cyberred.core.events import EventBus
from cyberred.core.models import AgentAction

log = structlog.get_logger().bind(component="decision_context_tracker")


class DecisionContextTracker:
    """Tracks stigmergic signals that influence agent decisions.
    
    Implements NFR37 requirement for 100% decision_context population.
    Every agent action must have an audit trail of which signals
    influenced the decision.
    
    Attributes:
        engagement_id: Current engagement ID.
        event_bus: EventBus for audit stream publishing.
        max_history: Maximum signals to retain per agent.
        isolated_mode: If True, returns ["isolated_mode"] for all contexts.
        _signals: Per-agent signal history.
    """
    
    def __init__(
        self,
        engagement_id: str,
        event_bus: EventBus,
        max_history: int = 100,
        isolated_mode: bool = False,
    ) -> None:
        self.engagement_id = engagement_id
        self.event_bus = event_bus
        self.max_history = max_history
        self.isolated_mode = isolated_mode
        self._signals: dict[str, list[SignalRecord]] = defaultdict(list)
        self._log = log.bind(engagement_id=engagement_id)
    
    def record_signal(
        self,
        agent_id: str,
        signal_id: str,
        signal_type: str,
        source: str,
        channel: str = "",
    ) -> None:
        """Record a stigmergic signal received by an agent.
        
        Args:
            agent_id: Agent that received the signal.
            signal_id: Unique identifier of the signal.
            signal_type: Type of signal (finding, strategy, etc.).
            source: Source agent/component.
            channel: Redis channel signal came from.
        """
        if self.isolated_mode:
            return  # Don't record signals in isolated mode
        
        weight = SIGNAL_TYPE_WEIGHTS.get(signal_type, 0.5)
        record = SignalRecord(
            signal_id=signal_id,
            signal_type=signal_type,
            source=source,
            timestamp=datetime.now(UTC),
            weight=weight,
            channel=channel,
        )
        
        signals = self._signals[agent_id]
        signals.append(record)
        
        # Enforce max history (drop oldest)
        if len(signals) > self.max_history:
            self._signals[agent_id] = signals[-self.max_history:]
        
        self._log.debug(
            "signal_recorded",
            agent_id=agent_id,
            signal_id=signal_id,
            signal_type=signal_type,
        )
    
    def get_context(self, agent_id: str) -> list[str]:
        """Get signal IDs that influenced agent's pending action.
        
        Returns:
            List of signal_ids sorted by weight (highest first).
            Returns ["isolated_mode"] if isolated_mode is True.
        """
        if self.isolated_mode:
            return ["isolated_mode"]
        
        signals = self._signals.get(agent_id, [])
        # Sort by weight descending, then by timestamp descending
        sorted_signals = sorted(
            signals,
            key=lambda s: (s.weight, s.timestamp),
            reverse=True,
        )
        return [s.signal_id for s in sorted_signals]
    
    def attach_to_action(
        self,
        agent_id: str,
        action: AgentAction,
    ) -> AgentAction:
        """Attach decision context to an agent action.
        
        Populates action.decision_context with signal IDs,
        clears the agent's context, and publishes to audit stream.
        
        Args:
            agent_id: Agent that performed the action.
            action: AgentAction to populate.
            
        Returns:
            AgentAction with decision_context populated.
        """
        context = self.get_context(agent_id)
        action.decision_context = context
        
        # Publish to audit stream
        asyncio.create_task(
            self._publish_audit(agent_id, action.id, context)
        )
        
        # Clear context for next action
        self.clear_context(agent_id)
        
        self._log.info(
            "context_attached",
            agent_id=agent_id,
            action_id=action.id,
            context_count=len(context),
        )
        
        return action
    
    def clear_context(self, agent_id: str) -> None:
        """Clear signal history for an agent."""
        if agent_id in self._signals:
            del self._signals[agent_id]
    
    def get_all_agents(self) -> list[str]:
        """Get all agent IDs with recorded signals."""
        return list(self._signals.keys())
    
    def get_signal_count(self, agent_id: str) -> int:
        """Get number of signals recorded for an agent."""
        return len(self._signals.get(agent_id, []))
    
    async def _publish_audit(
        self,
        agent_id: str,
        action_id: str,
        context_ids: list[str],
    ) -> None:
        """Publish context attachment to audit stream."""
        try:
            await self.event_bus.publish(
                "audit:decision_context",
                {
                    "engagement_id": self.engagement_id,
                    "agent_id": agent_id,
                    "action_id": action_id,
                    "context_ids": context_ids,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
        except Exception as e:
            self._log.error("audit_publish_failed", error=str(e))
```

### ValidationResult and validator

```python
from dataclasses import dataclass

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
```

### Integration with StigmergicAgent

The `StigmergicAgent.on_signal()` method (line 169-181 in base.py) already tracks `signal_id` in `_decision_context`. This story enhances that to:

1. Use the centralized `DecisionContextTracker` instead of local list
2. Record signal metadata (type, source, channel, timestamp)
3. Support relevance weighting
4. Publish to audit stream on action completion

```python
# In StigmergicAgent.__init__():
self._context_tracker: DecisionContextTracker | None = context_tracker

# In StigmergicAgent.on_signal():
async def on_signal(self, channel: str, data: dict[str, Any]):
    """Handle incoming stigmergic signal."""
    self._log.debug("signal_received", channel=channel)
    
    # Extract signal metadata
    signal_id = data.get("signal_id") or data.get("id") or str(uuid.uuid4())
    signal_type = self._infer_signal_type(channel)
    source = data.get("agent_id", "unknown")
    
    # Record to tracker if available
    if self._context_tracker:
        self._context_tracker.record_signal(
            agent_id=self.agent_id,
            signal_id=signal_id,
            signal_type=signal_type,
            source=source,
            channel=channel,
        )
    else:
        # Fallback to local list (backwards compatibility)
        self._decision_context.append(signal_id)

def _infer_signal_type(self, channel: str) -> str:
    """Infer signal type from channel name."""
    if channel.startswith("findings:"):
        return "finding"
    elif channel.startswith("strategies:"):
        return "strategy"
    elif channel.startswith("intel:"):
        return "intel"
    elif channel.startswith("rag:"):
        return "rag"
    elif "phase" in channel:
        return "phase"
    else:
        return "status"
```

### Architecture references

Per architecture (lines 807-811):
```
src/cyberred/orchestration/emergence/    # Stigmergic emergence validation (CRITICAL)
    ├── __init__.py
    ├── tracker.py            # Tracks decision_context across agents
    ├── validator.py          # Compares stigmergic vs isolated runs
    └── metrics.py            # Emergence score calculation (>20% gate)
```

Per architecture (lines 632-633):
```python
decision_context: List[str]  # IDs of stigmergic signals that influenced this action (CRITICAL for emergence validation)
```

### Project Structure Notes

- **File locations**:
  - `src/cyberred/orchestration/emergence/tracker.py` (new)
  - `src/cyberred/orchestration/emergence/validator.py` (new)
  - `src/cyberred/orchestration/emergence/__init__.py` (new)
- **Test locations**:
  - `tests/unit/orchestration/emergence/test_tracker.py` (new)
  - `tests/unit/orchestration/emergence/test_validator.py` (new)
  - `tests/integration/orchestration/emergence/test_tracker_integration.py` (new)
  - `tests/emergence/test_decision_context.py` (update existing placeholders)
- **Dependencies**:
  - `EventBus` from `src/cyberred/core/events.py`
  - `AgentAction` from `src/cyberred/core/models.py`
  - `StigmergicAgent` from `src/cyberred/agents/base.py`
- **Virtual environment**: Use `venv` (not `.venv`) if creating new environments

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#orchestration/emergence/] - File structure
- [Source: _bmad-output/planning-artifacts/architecture.md#lines 632-633] - decision_context definition
- [Source: _bmad-output/planning-artifacts/epics-stories.md#NFR37] - 100% decision_context requirement
- [Source: tests/emergence/README.md] - Emergence test protocol and hard gates
- [Source: tests/emergence/test_decision_context.py] - Placeholder tests to implement
- [Source: src/cyberred/agents/base.py#lines 104, 169-181, 281-291] - Current decision_context handling
- [Source: src/cyberred/core/models.py#AgentAction] - AgentAction dataclass with decision_context field
- [Source: _bmad-output/implementation-artifacts/7-7-dynamic-agent-spawner.md] - NFR37 compliance pattern

## Dev Agent Record

### Agent Model Used

Google Gemini (via Rovo)

### Debug Log References

N/A

### Completion Notes List

- Implemented `DecisionContextTracker` class with configurable history and isolated mode support.
- Implemented `validate_decision_context` function for NFR37 hard gate validation (100% population).
- Integrated tracker with `StigmergicAgent` (in `src/cyberred/agents/base.py`):
  - `on_signal` records incoming signals (findings, strategy, intel, rag, phase, status).
  - `execute` automatically attaches decision context to `AgentAction`.
  - `get_decision_context` delegates to tracker.
- Added 100% unit test coverage for `tracker.py` and `validator.py`.
- Added integration tests verifying context flow from signal reception to action audit publishing.
- Updated `tests/emergence/test_decision_context.py` to use real validation logic.
- Exported new components in `src/cyberred/orchestration/emergence/__init__.py`.

### File List

**New Files Created:**
- `src/cyberred/orchestration/emergence/__init__.py`
- `src/cyberred/orchestration/emergence/tracker.py`
- `src/cyberred/orchestration/emergence/validator.py`
- `tests/unit/orchestration/emergence/test_tracker.py`
- `tests/unit/orchestration/emergence/test_validator.py`
- `tests/integration/orchestration/emergence/test_tracker_integration.py`

**Files Modified:**
- `src/cyberred/agents/base.py` - Integrated DecisionContextTracker
- `src/cyberred/orchestration/__init__.py` - Exported emergence module
- `tests/emergence/test_decision_context.py` - Implemented placeholder tests

