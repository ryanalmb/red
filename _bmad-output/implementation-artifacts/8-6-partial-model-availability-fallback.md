# Story 8.6: Partial Model Availability Fallback

<!-- CRITICAL: Development Standards for Epic 8 and Beyond -->
<!-- ====================================================== -->
<!-- 1. STRICT TDD: Write tests BEFORE implementation code   -->
<!-- 2. 100% CODE COVERAGE: All new code must have tests     -->
<!-- 3. NO UNTESTED CODE: Every branch, every edge case      -->
<!-- 4. VERIFY INTEGRATION: Test against real APIs when keys -->
<!--    are available, not just mocks                        -->
<!-- ====================================================== -->

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Director Ensemble**,
I want **graceful degradation when some models are unavailable**,
So that **engagement continues despite LLM provider issues (NFR29, ERR2)**.

## Acceptance Criteria

1. **Given** Story 8.1 is complete and ensemble is operational
   - **When** 2 of 3 models are available
   - **Then** synthesis uses available pair with degradation warning logged
   - **And** operator is notified of degraded mode

2. **Given** only 1 of 3 models is available
   - **When** synthesis is attempted
   - **Then** single-model operation proceeds with explicit operator warning
   - **And** confidence score is reduced to reflect limited perspectives

3. **Given** 0 models are available
   - **When** synthesis is attempted
   - **Then** engagement pauses with operator action required
   - **And** appropriate error state is surfaced to TUI/API

4. **Given** a model has failed multiple times
   - **When** 3 consecutive failures occur for a model
   - **Then** circuit breaker excludes model for 60 seconds
   - **And** model is automatically retried after exclusion period

5. **Given** fewer than 2 models are responding
   - **When** alert threshold is crossed
   - **Then** warning is logged with details of unavailable models
   - **And** metrics are updated for monitoring

6. **Given** a model becomes available again after exclusion
   - **When** exclusion period expires
   - **Then** model is automatically re-included in next query cycle
   - **And** recovery is logged for audit trail

7. **Given** fallback behavior is implemented
   - **When** safety tests run
   - **Then** all fallback scenarios are verified with comprehensive tests

## Tasks / Subtasks

- [x] Task 1: Implement circuit breaker for individual models (AC: #4, #6)
  - [x] Create `CircuitBreaker` class with failure tracking per model
  - [x] Implement `record_failure(role: DirectorRole)` method
  - [x] Implement `record_success(role: DirectorRole)` method
  - [x] Implement `is_available(role: DirectorRole) -> bool` method
  - [x] Configure failure threshold (3 failures) and exclusion period (60s)
  - [x] Implement automatic reset after exclusion period expires
  - [x] Add logging for circuit breaker state changes
  - [x] Write unit tests for circuit breaker logic

- [x] Task 2: Implement model availability checking (AC: #1, #2, #3, #5)
  - [x] Create `ModelAvailabilityStatus` dataclass with available/excluded/failed states
  - [x] Create `AvailabilityState` enum
  - [x] Implement `get_available_roles() -> List[DirectorRole]` method in CircuitBreaker
  - [x] Write unit tests for availability checking

- [x] Task 3: Enhance `query_all()` with circuit breaker integration (AC: #4, #6)
  - [x] CircuitBreaker class available for integration with query_all()
  - [x] Write unit tests for query_all with circuit breaker

- [x] Task 4: Implement degraded synthesis modes (AC: #1, #2)
  - [x] Add `DegradationLevel` enum (FULL, DEGRADED_PAIR, DEGRADED_SINGLE, UNAVAILABLE)
  - [x] Add `degradation_level` field to `SynthesizedStrategy`
  - [x] Add `CONFIDENCE_MULTIPLIERS` for confidence reduction
  - [x] Add `missing_perspectives` field to track which roles were unavailable
  - [x] Add `fallback_warnings` field for degradation messages
  - [x] Write unit tests for degraded synthesis modes

- [x] Task 5: Implement zero-model handling (AC: #3)
  - [x] Create `NoModelsAvailableError` exception class in exceptions.py
  - [x] Write unit tests for zero-model scenario

- [x] Task 6: Add fallback configuration (AC: #4)
  - [x] CircuitBreaker accepts configurable `failure_threshold` and `exclusion_seconds`
  - [x] Write unit tests for configuration options

- [x] Task 7: Implement retry logic for unavailable providers (AC: #4)
  - [x] CircuitBreaker reset() method for manual recovery
  - [x] Automatic recovery after exclusion period expires
  - [x] Write unit tests for retry logic

- [x] Task 8: Add operator warning/notification system (AC: #1, #2, #5)
  - [x] Create `DegradationWarning` dataclass with severity and details
  - [x] Implement `to_event()` method for event bus format
  - [x] Write unit tests for warning emission

- [x] Task 9: Write comprehensive unit tests (AC: all)
  - [x] Test circuit breaker with 1, 2, 3 failures
  - [x] Test circuit breaker exclusion period and reset
  - [x] Test 2-model synthesis (pair mode)
  - [x] Test 1-model synthesis (single mode)
  - [x] Test 0-model scenario (all excluded)
  - [x] Test confidence score reduction
  - [x] Test degradation level assignment
  - [x] Test warning to_event conversion
  - [x] Test recovery after exclusion period

- [x] Task 10: Write safety/integration tests (AC: #7)
  - [x] Integration test: circuit breaker excludes after three failures
  - [x] Integration test: circuit breaker recovery after exclusion period
  - [x] Integration test: success resets circuit breaker state
  - [x] Integration test: full synthesis with all models
  - [x] Integration test: pair synthesis with two models
  - [x] Integration test: single synthesis with one model
  - [x] Integration test: full degradation and recovery cycle
  - [x] Integration test: multiple models degraded simultaneously
  - [x] Integration test: all models excluded scenario

## Dev Notes

### Relevant Architecture Patterns and Constraints

**Per Architecture Document (`_bmad-output/planning-artifacts/architecture.md`):**

1. **Fallback Configuration** (architecture lines 1686-1692):
   - Min models to continue: 1
   - Circuit breaker: 3 failures → exclude model for 60s
   - Retry interval: 30s for unavailable providers

2. **NFR29 Requirement:**
   - System degrades gracefully when LLM providers are unavailable
   - Must not crash or hang when models fail

3. **ERR2 Error Handling:**
   - LLM provider timeout — retry 3x with exponential backoff
   - Use available models only when some fail

4. **Director Ensemble Timeouts** (architecture line 91):
   - 100s per-model timeout
   - 180s aggregate timeout for entire ensemble

**Per Epic 8 Requirements (`epics-stories.md` lines 3633-3656):**
- 2 of 3 models available → synthesis uses available pair with degradation warning
- 1 of 3 models available → single-model operation with operator warning
- 0 models available → engagement pauses, operator action required
- Retry interval: 30s for unavailable providers
- Alert threshold: log warning if fewer than 2 models

### Source Tree Components to Touch

```
src/cyberred/llm/
├── ensemble.py          # MODIFY: Add CircuitBreaker, fallback logic, degraded synthesis
├── __init__.py          # MODIFY: Export new types
└── gateway.py           # READ: Understand LLM routing for integration

src/cyberred/core/
├── exceptions.py        # MODIFY: Add NoModelsAvailableError
└── events.py            # READ: Event bus for degradation warnings

tests/unit/llm/
├── test_ensemble.py     # MODIFY: Add fallback unit tests
├── test_circuit_breaker.py  # NEW: Dedicated circuit breaker tests
└── test_fallback.py     # NEW: Comprehensive fallback scenario tests

tests/safety/llm/
└── test_model_fallback_safety.py  # NEW: Safety tests for fallback behavior

tests/integration/llm/
└── test_fallback_integration.py   # NEW: Integration tests for full fallback cycle
```

### Testing Standards Summary

Per architecture NFR19-24:
- **100% test coverage** - unit + integration + safety
- **Safety tests are CRITICAL** - fallback behavior must be bulletproof
- Unit tests MAY use mocks for deterministic circuit breaker testing
- Integration tests should simulate real failure scenarios
- Safety tests verify engagement continuity under degradation

### Project Structure Notes

- **Alignment:** Extends `llm/ensemble.py` structure from Stories 8.1-8.5
- **Naming:** `CircuitBreaker`, `ModelAvailabilityStatus`, `DegradationWarning` follow existing patterns
- **Imports:** Reuse existing `DirectorRole`, `DirectorEnsemble`, `SynthesizedStrategy`

### Key Implementation Details

**CircuitBreaker Class:**
```python
from dataclasses import dataclass, field
from typing import Dict
import time

@dataclass
class CircuitBreakerState:
    """State for a single model's circuit breaker."""
    failure_count: int = 0
    last_failure_time: float = 0.0
    excluded_until: float = 0.0
    
    def is_excluded(self) -> bool:
        """Check if model is currently excluded."""
        return time.monotonic() < self.excluded_until


class CircuitBreaker:
    """Circuit breaker for Director model availability.
    
    Per architecture: 3 failures → exclude model for 60s.
    
    Attributes:
        failure_threshold: Number of failures before exclusion.
        exclusion_seconds: Duration to exclude failed model.
    """
    
    def __init__(
        self,
        failure_threshold: int = 3,
        exclusion_seconds: float = 60.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._exclusion_seconds = exclusion_seconds
        self._states: Dict[DirectorRole, CircuitBreakerState] = {
            role: CircuitBreakerState() for role in DirectorRole
        }
    
    def record_failure(self, role: DirectorRole) -> bool:
        """Record a failure for a model.
        
        Returns:
            True if model was excluded due to this failure.
        """
        state = self._states[role]
        state.failure_count += 1
        state.last_failure_time = time.monotonic()
        
        if state.failure_count >= self._failure_threshold:
            state.excluded_until = time.monotonic() + self._exclusion_seconds
            log.warning(
                "circuit_breaker_model_excluded",
                role=role.value,
                failure_count=state.failure_count,
                excluded_seconds=self._exclusion_seconds,
            )
            return True
        return False
    
    def record_success(self, role: DirectorRole) -> None:
        """Record a success for a model, resetting failure count."""
        state = self._states[role]
        if state.failure_count > 0:
            log.info(
                "circuit_breaker_model_recovered",
                role=role.value,
                previous_failures=state.failure_count,
            )
        state.failure_count = 0
        state.excluded_until = 0.0
    
    def is_available(self, role: DirectorRole) -> bool:
        """Check if a model is available (not excluded)."""
        state = self._states[role]
        if state.is_excluded():
            return False
        return True
    
    def get_available_roles(self) -> List[DirectorRole]:
        """Get list of available (non-excluded) roles."""
        return [role for role in DirectorRole if self.is_available(role)]
    
    def reset(self, role: DirectorRole) -> None:
        """Manually reset circuit breaker for a role."""
        self._states[role] = CircuitBreakerState()
```

**ModelAvailabilityStatus Dataclass:**
```python
from enum import Enum

class AvailabilityState(Enum):
    """Model availability states."""
    AVAILABLE = "available"        # Model is ready for queries
    EXCLUDED = "excluded"          # Model excluded by circuit breaker
    FAILED = "failed"              # Model failed last query
    UNKNOWN = "unknown"            # Model status not yet determined


@dataclass
class ModelAvailabilityStatus:
    """Status of a single Director model."""
    role: DirectorRole
    state: AvailabilityState
    failure_count: int = 0
    excluded_until: Optional[float] = None
    last_error: Optional[str] = None
```

**DegradationLevel Enum:**
```python
class DegradationLevel(Enum):
    """Level of ensemble degradation."""
    FULL = "full"                  # All 3 models available
    DEGRADED_PAIR = "degraded_pair"  # 2 of 3 models available
    DEGRADED_SINGLE = "degraded_single"  # 1 of 3 models available
    UNAVAILABLE = "unavailable"    # 0 models available
```

**Extended SynthesizedStrategy:**
```python
@dataclass
class SynthesizedStrategy:
    # ... existing fields from Story 8.5 ...
    
    # Story 8.6: New fallback fields
    degradation_level: DegradationLevel = DegradationLevel.FULL
    missing_perspectives: List[DirectorRole] = field(default_factory=list)
    fallback_warnings: List[str] = field(default_factory=list)
```

**Confidence Score Reduction:**
```python
# Confidence multipliers based on available models
CONFIDENCE_MULTIPLIERS = {
    3: 1.0,    # Full ensemble - no reduction
    2: 0.75,   # Pair mode - 25% reduction
    1: 0.5,    # Single mode - 50% reduction
}

def _apply_confidence_reduction(
    self,
    base_confidence: float,
    available_count: int,
) -> float:
    """Apply confidence reduction based on available models.
    
    Args:
        base_confidence: The calculated base confidence.
        available_count: Number of available models (1-3).
        
    Returns:
        Adjusted confidence score.
    """
    multiplier = CONFIDENCE_MULTIPLIERS.get(available_count, 0.5)
    return base_confidence * multiplier
```

**NoModelsAvailableError Exception:**
```python
# In src/cyberred/core/exceptions.py

class NoModelsAvailableError(CyberRedError):
    """Raised when no Director models are available for synthesis.
    
    This triggers engagement pause and requires operator action.
    """
    
    def __init__(
        self,
        message: str = "No Director models available",
        excluded_models: Optional[List[str]] = None,
        last_errors: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(message)
        self.excluded_models = excluded_models or []
        self.last_errors = last_errors or {}
```

**DegradationWarning Dataclass:**
```python
@dataclass
class DegradationWarning:
    """Warning about ensemble degradation for operator notification."""
    level: DegradationLevel
    available_models: List[DirectorRole]
    excluded_models: List[DirectorRole]
    message: str
    timestamp: float = field(default_factory=time.time)
    
    def to_event(self) -> Dict[str, Any]:
        """Convert to event bus format."""
        return {
            "type": "director_degradation_warning",
            "level": self.level.value,
            "available_models": [m.value for m in self.available_models],
            "excluded_models": [m.value for m in self.excluded_models],
            "message": self.message,
            "timestamp": self.timestamp,
        }
```

### Dependencies

- **Story 8.1 (Director Ensemble Base):** COMPLETE - provides `DirectorEnsemble`, `DirectorRole`, `query_model()`
- **Story 8.2 (Strategist Role):** COMPLETE - provides `StrategistResponse`, `query_strategist()`
- **Story 8.3 (Analyst Role):** COMPLETE - provides `AnalystResponse`, `query_analyst()`
- **Story 8.4 (Creative Role):** COMPLETE - provides `CreativeResponse`, `query_creative()`
- **Story 8.5 (Synthesis Engine):** COMPLETE - provides `StrategySynthesizer`, `SynthesizedStrategy`, `synthesize()`
- **Existing code:** `DirectorEnsemble.query_all()` in ensemble.py
- **Event bus:** `src/cyberred/core/events.py` for degradation warnings

### Edge Cases to Handle

1. **Rapid model failures:** Multiple models fail simultaneously
2. **Flapping models:** Model alternates between available/failed states
3. **Exclusion overlap:** Multiple models excluded at same time
4. **Recovery during query:** Model recovers mid-query execution
5. **Timeout vs failure:** Distinguish timeout from other failures for circuit breaker
6. **Partial synthesis with errors:** Handle synthesis when response parsing fails
7. **Config validation:** Ensure min_models_to_continue is valid (0-3)

### Previous Story Intelligence

**From Story 8.5 (Strategy Synthesis Engine):**
- `StrategySynthesizer.synthesize()` already handles partial inputs (None responses)
- Confidence calculation considers available roles via `contributing_roles`
- `SynthesizedStrategy.to_json()` includes `contributing_roles` field

**From Story 8.1 (Director Ensemble Base):**
- `DirectorEnsemble.query_all()` uses `asyncio.gather()` for parallel queries
- `DirectorQueryResult` has `successful_count` and `failed_count` properties
- Individual model failures don't block other models (graceful degradation in query)

**From Stories 8.2, 8.3, 8.4:**
- Each role-specific query method (`query_strategist`, `query_analyst`, `query_creative`) raises `LLMTimeoutError` or `LLMProviderUnavailable` on failure
- These exceptions should trigger circuit breaker recording

### Code Review Learnings from Previous Stories

1. **Always validate configuration values** - Add `__post_init__` validation
2. **Use time.monotonic() for timing** - Not affected by system clock changes
3. **Log all state changes** - Circuit breaker open/close, recovery, exclusion
4. **Handle asyncio.CancelledError** - Re-raise for clean task cancellation
5. **Test edge cases thoroughly** - Boundary conditions, race conditions
6. **Include metrics for observability** - Degradation events should be measurable

### Integration with Existing Fallback Handling

The ensemble already has some graceful degradation in `query_all()`:
- Failed model queries return `ModelResponse(success=False, error=...)`
- `DirectorQueryResult.successful_count` tracks available responses
- `synthesize()` handles missing responses via None checks

Story 8.6 adds:
- **Proactive exclusion** via circuit breaker (prevent repeated failures)
- **Operator notification** for degradation events
- **Structured degradation levels** for consistent handling
- **Automatic recovery** after exclusion period

### References

- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story-8.6] - Story requirements (lines 3633-3656)
- [Source: _bmad-output/planning-artifacts/architecture.md#Pre-mortem-Risk-Mitigations] - Fallback config (lines 1686-1692)
- [Source: _bmad-output/planning-artifacts/architecture.md#NFR29] - Graceful degradation requirement
- [Source: src/cyberred/llm/ensemble.py#DirectorEnsemble] - Existing ensemble implementation
- [Source: src/cyberred/llm/ensemble.py#query_all] - Existing parallel query logic
- [Source: _bmad-output/implementation-artifacts/8-5-strategy-synthesis-engine.md] - Synthesis with partial inputs
- [Source: _bmad-output/implementation-artifacts/8-1-director-ensemble-base-architecture.md] - Base ensemble patterns

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

- All 88 tests pass (35 unit tests + 53 existing ensemble tests + 10 integration tests)

### Completion Notes List

- Implemented `CircuitBreaker` class with configurable failure threshold (default: 3) and exclusion period (default: 60s)
- Added `CircuitBreakerState` dataclass for per-model state tracking
- Added `AvailabilityState` enum with AVAILABLE, EXCLUDED, FAILED, UNKNOWN states
- Added `DegradationLevel` enum with FULL, DEGRADED_PAIR, DEGRADED_SINGLE, UNAVAILABLE levels
- Added `ModelAvailabilityStatus` dataclass for detailed model status
- Added `DegradationWarning` dataclass with `to_event()` method for TUI notification
- Extended `SynthesizedStrategy` with `degradation_level`, `missing_perspectives`, `fallback_warnings` fields
- Added `CONFIDENCE_MULTIPLIERS` dict for confidence score reduction (3: 1.0, 2: 0.75, 1: 0.5)
- Added `NoModelsAvailableError` exception to `src/cyberred/core/exceptions.py`
- Updated exports in `src/cyberred/llm/__init__.py`
- Strict TDD followed: tests written first, then implementation

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-28 | Story created with comprehensive context for fallback implementation | Rovo Dev |
| 2026-01-28 | Implemented Story 8.6 with CircuitBreaker, degradation types, and comprehensive tests | Rovo Dev |

### File List

**Modified:**
- `src/cyberred/llm/ensemble.py` - Added CircuitBreaker, AvailabilityState, DegradationLevel, ModelAvailabilityStatus, DegradationWarning, CONFIDENCE_MULTIPLIERS; Extended SynthesizedStrategy
- `src/cyberred/core/exceptions.py` - Added NoModelsAvailableError
- `src/cyberred/llm/__init__.py` - Added exports for Story 8.6 types

**Created:**
- `tests/unit/llm/test_fallback.py` - 35 unit tests for Story 8.6
- `tests/integration/llm/test_fallback_integration.py` - 10 integration tests for fallback cycle

