# Story 5.11: Intelligence Query Error Handling

Status: review

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD methodology at all times. All tasks marked [RED], [GREEN], [REFACTOR] must be followed explicitly. Each task must have a failing test before implementation.

> [!NOTE]
> **DEPENDENCIES:**
> - Story 5.7 (Intelligence Aggregator) - Provides `IntelligenceAggregator` with parallel query
> - Story 5.8 (Redis Cache) - Provides cache fallback capability
> - Story 5.9 (Offline Mode) - Provides stale cache fallback
> - [aggregator.py](file:///root/red/src/cyberred/intelligence/aggregator.py) — Core query logic
> - [exceptions.py](file:///root/red/src/cyberred/core/exceptions.py) — Exception hierarchy

> [!CAUTION]
> **ERR3 PATTERN MANDATORY:** Per architecture, intelligence failures MUST follow the ERR3 pattern: "log error, return partial, continue". Agents MUST NEVER receive exceptions from intelligence queries—only structured results (empty list or partial results).

## Story

As an **agent**,
I want **graceful error handling when intelligence sources fail**,
So that **I can continue operating with partial or no intelligence (ERR3)**.

## Acceptance Criteria

1. **Given** a source times out (>20s)
   **When** the aggregator queries sources
   **Then** the timed-out source is skipped
   **And** partial results are returned from successful sources
   **And** a warning is logged with source name and timeout duration

2. **Given** a source returns invalid data
   **When** the aggregator processes results
   **Then** the error is logged with source name and error details
   **And** the invalid source result is excluded
   **And** valid results from other sources are returned

3. **Given** all sources fail (timeout + errors)
   **When** the aggregator completes
   **Then** fallback to cache is attempted (Story 5.9)
   **And** if cache has data, stale results are returned
   **And** if cache is empty, empty list is returned
   **And** agent receives a structured result (never exception)

4. **Given** an agent queries intelligence
   **When** any combination of source failures occurs
   **Then** the agent NEVER receives an exception
   **And** the agent always receives `List[IntelResult]` (may be empty)

5. **Given** source failures occur
   **When** metrics are tracked
   **Then** per-source failure counts are incremented
   **And** per-source timeout counts are incremented
   **And** metrics are available via `get_error_metrics()` method

6. **Given** safety tests exist
   **When** intelligence failures are simulated
   **Then** agents continue execution without exceptions
   **And** agents make decisions with partial or no intelligence

## Tasks / Subtasks

### Phase 0: Setup [BLUE]

- [x] Task 0.1: Verify prerequisites
  - [x] Confirm Story 5.9 is complete: `pytest tests/unit/intelligence/test_offline_mode.py -v --tb=short`
  - [x] Confirm all 275+ intelligence tests pass: `pytest tests/unit/intelligence/ -v --tb=short`
  - [x] Review existing error handling in [aggregator.py#L80-L114](file:///root/red/src/cyberred/intelligence/aggregator.py#L80-L114)
  - [x] Review ERR3 pattern in [architecture.md#L198-L205](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L198-L205)

- [x] Task 0.2: Analyze existing error handling
  - [x] Verify `_query_source_with_timeout()` catches `TimeoutError` correctly
  - [x] Verify `_query_source_with_timeout()` catches generic `Exception` correctly  
  - [x] Identify missing metrics tracking (current: logging only)
  - [x] Identify missing validation of source return types
  - [x] **Decision:** Extend existing implementation with metrics + validation

---

### Phase 1: Error Metrics Tracking [RED → GREEN → REFACTOR]

#### 1A: Create IntelligenceErrorMetrics Class (AC: 5)

- [x] Task 1.1: Create metrics test file and class skeleton
  - [x] **[RED]** Create `tests/unit/intelligence/test_error_metrics.py`
  - [x] **[RED]** Write failing test: `IntelligenceErrorMetrics` can be instantiated
  - [x] **[RED]** Write failing test: `record_timeout(source_name)` increments timeout counter
  - [x] **[RED]** Write failing test: `record_error(source_name, error_type)` increments error counter
  - [x] **[GREEN]** Create `src/cyberred/intelligence/metrics.py` with skeleton:
    ```python
    class IntelligenceErrorMetrics:
        """Track intelligence source error and timeout rates."""
        
        def __init__(self) -> None:
            self._timeouts: Dict[str, int] = {}
            self._errors: Dict[str, Dict[str, int]] = {}  # source -> {error_type: count}
        
        def record_timeout(self, source_name: str) -> None:
            """Record a source timeout."""
            self._timeouts[source_name] = self._timeouts.get(source_name, 0) + 1
        
        def record_error(self, source_name: str, error_type: str) -> None:
            """Record a source error."""
            if source_name not in self._errors:
                self._errors[source_name] = {}
            self._errors[source_name][error_type] = (
                self._errors[source_name].get(error_type, 0) + 1
            )
    ```
  - [x] **[REFACTOR]** Add docstrings and type hints

- [x] Task 1.2: Implement metrics retrieval (AC: 5)
  - [x] **[RED]** Write failing test: `get_metrics()` returns dict with timeout and error counts
  - [x] **[RED]** Write failing test: `get_source_metrics(source_name)` returns per-source stats
  - [x] **[RED]** Write failing test: `reset()` clears all metrics
  - [x] **[GREEN]** Implement methods:
    ```python
    def get_metrics(self) -> Dict[str, Any]:
        """Get all error metrics."""
        return {
            "timeouts": dict(self._timeouts),
            "errors": {k: dict(v) for k, v in self._errors.items()},
            "total_timeouts": sum(self._timeouts.values()),
            "total_errors": sum(
                sum(v.values()) for v in self._errors.values()
            ),
        }
    
    def get_source_metrics(self, source_name: str) -> Dict[str, Any]:
        """Get metrics for a specific source."""
        return {
            "timeouts": self._timeouts.get(source_name, 0),
            "errors": dict(self._errors.get(source_name, {})),
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self._timeouts.clear()
        self._errors.clear()
    ```
  - [x] **[REFACTOR]** Consider thread-safety if needed (asyncio is single-threaded, so not required)

---

### Phase 2: Integrate Metrics into Aggregator [RED → GREEN → REFACTOR]

#### 2A: Add Metrics to IntelligenceAggregator (AC: 1, 2, 5)

- [x] Task 2.1: Extend aggregator with metrics tracking
  - [x] **[RED]** Write failing test: `IntelligenceAggregator` has `error_metrics` property
  - [x] **[RED]** Write failing test: timeout increments `error_metrics.timeouts[source_name]`
  - [x] **[RED]** Write failing test: exception increments `error_metrics.errors[source_name][error_type]`
  - [x] **[GREEN]** Modify `IntelligenceAggregator.__init__()`:
    ```python
    from cyberred.intelligence.metrics import IntelligenceErrorMetrics
    
    def __init__(self, ...):
        ...
        self._error_metrics = IntelligenceErrorMetrics()
    
    @property
    def error_metrics(self) -> IntelligenceErrorMetrics:
        return self._error_metrics
    ```
  - [x] **[GREEN]** Modify `_query_source_with_timeout()`:
    ```python
    except asyncio.TimeoutError:
        self._error_metrics.record_timeout(source.name)
        log.warning("aggregator_source_timeout", ...)
        return None
    except Exception as e:
        self._error_metrics.record_error(source.name, type(e).__name__)
        log.warning("aggregator_source_error", ...)
        return None
    ```
  - [x] **[REFACTOR]** Ensure CachedIntelligenceAggregator inherits metrics correctly

---

### Phase 3: Source Result Validation [RED → GREEN → REFACTOR]

#### 3A: Validate Source Return Types (AC: 2, 4)

- [x] Task 3.1: Implement return type validation
  - [x] **[RED]** Write failing test: source returning non-list is logged and excluded
  - [x] **[RED]** Write failing test: source returning list with non-IntelResult items is logged and excluded
  - [x] **[RED]** Write failing test: aggregator logs "invalid_result_type" when validation fails
  - [x] **[GREEN]** Add validation in `_query_source_with_timeout()`:
    ```python
    results = await asyncio.wait_for(...)
    
    # Validate result type
    if not isinstance(results, list):
        self._error_metrics.record_error(source.name, "InvalidResultType")
        log.warning("aggregator_invalid_result_type",
                   source=source.name,
                   actual_type=type(results).__name__)
        return None
    
    # Validate list contents (filter invalid items)
    valid_results = []
    for item in results:
        if isinstance(item, IntelResult):
            valid_results.append(item)
        else:
            log.warning("aggregator_invalid_result_item",
                       source=source.name,
                       item_type=type(item).__name__)
    
    return valid_results
    ```
  - [x] **[REFACTOR]** Extract validation to `_validate_results()` helper

---

### Phase 4: Agent Contract Verification [RED → GREEN → REFACTOR]

#### 4A: Ensure No Exceptions Escape (AC: 4)

- [x] Task 4.1: Write contract verification tests
  - [x] **[RED]** Write test: `query()` with all sources timing out returns `List[IntelResult]`
  - [x] **[RED]** Write test: `query()` with all sources raising exceptions returns `List[IntelResult]`
  - [x] **[RED]** Write test: `query()` with source returning `None` explicitly returns `List[IntelResult]`
  - [x] **[RED]** Write test: `query()` NEVER raises any exception to caller
  - [x] **[GREEN]** Verify existing implementation passes (should already pass)
  - [x] **[REFACTOR]** Add docstring to `query()` explicitly stating "never raises exceptions"

---

### Phase 5: Safety Tests [RED → GREEN → REFACTOR]

#### 5A: Create Safety Test File (AC: 6)

- [x] Task 5.1: Create safety tests for agent continuity
  - [x] Create `tests/safety/intelligence/test_agent_continuity.py`
  - [x] **[RED]** Write test: simulate all sources fail, verify agent can make decision
  - [x] **[RED]** Write test: simulate partial failure, verify agent uses partial results
  - [x] **[RED]** Write test: simulate invalid data, verify agent continues with valid sources
  - [x] **[GREEN]** Implement mock agent that:
    1. Calls `aggregator.query()`
    2. Makes decision based on results (or lack thereof)
    3. Continues execution without crash
  - [x] **[REFACTOR]** Add `@pytest.mark.safety` marker to all tests

---

### Phase 6: Module Exports [RED → GREEN]

#### 6A: Update __init__.py (AC: 5)

- [x] Task 6.1: Export metrics class
  - [x] **[RED]** Write test: `from cyberred.intelligence import IntelligenceErrorMetrics` works
  - [x] **[GREEN]** Update `src/cyberred/intelligence/__init__.py`:
    ```python
    from cyberred.intelligence.metrics import IntelligenceErrorMetrics
    
    __all__ = [
        # ... existing exports
        "IntelligenceErrorMetrics",
    ]
    ```
  - [x] **[REFACTOR]** Update module docstring

---

### Phase 7: Integration Tests [RED → GREEN → REFACTOR]

- [x] Task 7.1: Create integration tests
  - [x] Create `tests/integration/intelligence/test_error_handling.py`
  - [x] **[RED]** Write test: real Redis + mock failing sources → graceful degradation
  - [x] **[RED]** Write test: real Redis + timeout simulation → partial results returned
  - [x] **[RED]** Write test: metrics persist across multiple queries
  - [x] **[GREEN]** Implement tests with testcontainers Redis
  - [x] **[REFACTOR]** Add `@pytest.mark.integration` marker

---

### Phase 8: Coverage & Documentation [BLUE]

- [x] Task 8.1: Verify 100% coverage
  - [x] Run: `pytest tests/unit/intelligence/test_error_metrics.py --cov=src/cyberred/intelligence/metrics --cov-report=term-missing`
  - [x] Ensure no untested branches

- [x] Task 8.2: Update Dev Agent Record
  - [x] Fill in agent model and completion notes
  - [x] Run full test suite: `pytest tests/unit/intelligence/ tests/safety/intelligence/ -v --tb=short`
  - [x] Update story status to `review`

## Dev Notes

### Architecture Reference

From [architecture.md#L198-L205](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L198-L205):
```
**Error Handling (ERR1-ERR6 from PRD):**
- ERR3: Redis connection loss — buffer messages locally (10s max), reconnect with exponential backoff
```

From [epics-stories.md#L82](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L82):
```
FR75: Intelligence queries are non-blocking — agents continue if sources timeout
```

### ERR3 Pattern (CRITICAL)

Per PRD Error Handling:
1. **Log** - Always log the error with source name and details
2. **Return partial** - Return whatever results are available
3. **Continue** - Agent continues execution, never blocked

### Existing Error Handling (aggregator.py)

The current implementation at [aggregator.py#L80-L114](file:///root/red/src/cyberred/intelligence/aggregator.py#L80-L114) already handles:
- `asyncio.TimeoutError` → logs warning, returns None
- `Exception` → logs warning, returns None

**What's Missing (to implement):**
1. **Metrics tracking** - No counters for timeout/error rates
2. **Result validation** - No validation of source return types
3. **Safety tests** - No explicit tests for agent continuity
4. **Formal contract** - No explicit guarantee agents never receive exceptions

### Key Learnings from Story 5.10

1. **Use structlog for logging** — NOT `print()` statements
2. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases explicitly
3. **Verify coverage claims** — Run `pytest --cov` before marking done
4. **Use pytest markers** — Always include `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.safety`
5. **Graceful degradation** — Errors should not block agent operation

### Existing Code References

| File | Purpose | Story |
|------|---------|-------|
| [aggregator.py](file:///root/red/src/cyberred/intelligence/aggregator.py) | Core query logic with timeout handling | 5.7 |
| [cache.py](file:///root/red/src/cyberred/intelligence/cache.py) | Redis-backed caching | 5.8 |
| [test_aggregator.py](file:///root/red/tests/unit/intelligence/test_aggregator.py) | Existing aggregator tests | 5.7 |
| [test_offline_mode.py](file:///root/red/tests/unit/intelligence/test_offline_mode.py) | Offline fallback tests | 5.9 |
| [exceptions.py](file:///root/red/src/cyberred/core/exceptions.py) | Exception hierarchy | 1.1 |

### Test File Naming

| Test Type | Location | Marker |
|-----------|----------|--------|
| Unit | `tests/unit/intelligence/test_error_metrics.py` | `@pytest.mark.unit` |
| Safety | `tests/safety/intelligence/test_agent_continuity.py` | `@pytest.mark.safety` |
| Integration | `tests/integration/intelligence/test_error_handling.py` | `@pytest.mark.integration` |

### Example Usage

```python
from cyberred.intelligence import IntelligenceAggregator, IntelligenceErrorMetrics

# Create aggregator with metrics tracking
aggregator = IntelligenceAggregator()
aggregator.add_source(CisaKevSource())
aggregator.add_source(NvdSource())  # May timeout

# Query (agent never receives exceptions)
results = await aggregator.query("Apache", "2.4.49")
# results is ALWAYS List[IntelResult], even if empty

# Check error metrics
metrics = aggregator.error_metrics.get_metrics()
# {
#     "timeouts": {"nvd": 2},
#     "errors": {"nuclei": {"ConnectionError": 1}},
#     "total_timeouts": 2,
#     "total_errors": 1
# }
```

### References

- **Epic 5 Overview:** [epics-stories.md#L2056-L2098](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2056-L2098)
- **Story 5.11 Requirements:** [epics-stories.md#L2352-L2375](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2352-L2375)
- **Story 5.10 Implementation:** [5-10-intelligence-stigmergic-publication.md](file:///root/red/_bmad-output/implementation-artifacts/5-10-intelligence-stigmergic-publication.md)
- **Architecture - Error Handling:** [architecture.md#L198-L205](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L198-L205)
- **Architecture - Result Objects:** [architecture.md#L652-L679](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L652-L679)
- **FR75:** Intelligence queries are non-blocking
- **ERR3:** Log, return partial, continue
- **Observability:** `IntelligenceErrorMetrics` is designed to be extensible for future Prometheus integration (see Architecture NFRs).

## Dev Agent Record

### Agent Model Used

Gemini 2.5 Pro (Antigravity) - 2026-01-08

### Debug Log References

- Code review: Identified 4 HIGH, 3 MEDIUM, 2 LOW issues
- All issues fixed in single session

### Completion Notes List

- All 6 ACs implemented and verified
- `metrics.py` has 100% test coverage
- Safety tests pass (3 tests: total failure, partial failure, invalid data)
- Integration tests pass (3 tests: graceful degradation, partial success, metrics persistence)
- All 304+ unit tests pass

### File List

| Action | File Path |
|--------|-----------|
| [NEW] | `src/cyberred/intelligence/metrics.py` |
| [MODIFY] | `src/cyberred/intelligence/aggregator.py` |
| [MODIFY] | `src/cyberred/intelligence/__init__.py` |
| [NEW] | `tests/unit/intelligence/test_error_metrics.py` |
| [NEW] | `tests/unit/intelligence/test_aggregator_metrics.py` |
| [NEW] | `tests/safety/intelligence/test_agent_continuity.py` |
| [NEW] | `tests/integration/intelligence/test_error_handling.py` |
