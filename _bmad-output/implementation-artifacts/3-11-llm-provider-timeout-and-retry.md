# Story 3.11: LLM Provider Timeout & Retry

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **automatic retry for LLM provider timeouts**,
So that **transient failures don't crash agents (ERR2)**.

## Acceptance Criteria

1. **Given** Story 3.10 is complete
2. **When** LLM provider times out
3. **Then** request is retried up to 3 times
4. **And** exponential backoff: 1s, 2s, 4s
5. **And** if all retries fail, graceful error is returned
6. **And** circuit breaker excludes failing models temporarily (3 failures → 60s exclusion)
7. **And** router respects circuit breaker state when selecting models
8. **And** integration tests simulate timeout scenarios

## Tasks / Subtasks

> [!IMPORTANT]
> **TDD REQUIRED:** Each task MUST follow the Red-Green-Refactor cycle. Use phase markers:
> - `[RED]` — Write failing test first (test must fail before implementation)
> - `[GREEN]` — Write minimal code to make test pass
> - `[REFACTOR]` — Clean up code while keeping tests green

### Phase 1: Circuit Breaker Router Integration

> [!NOTE]
> Story 3.10 implemented circuit breaker state tracking in `LLMGateway` but the router doesn't check exclusion state. This story completes the integration.

- [x] Task 1: Add exclusion callback to ModelRouter (AC: #6, #7) <!-- id: 0 -->
  - [x] [RED] Write failing test: `test_router_respects_exclusion_callback`
  - [x] [GREEN] Update `ModelRouter.__init__` to accept optional `exclusion_checker: Callable[[str], bool]`
    - Callback returns True if model_name is currently excluded
    - Default: `lambda _: False` (no exclusions)
  - [x] [REFACTOR] Add docstring explaining exclusion integration
  - [x] Verification: Test confirms callback is invoked during select_model

- [x] Task 2: Integrate exclusion check in select_model (AC: #6, #7) <!-- id: 1 -->
  - [x] [RED] Write failing test: `test_select_model_skips_excluded_provider`
  - [x] [GREEN] Update `ModelRouter.select_model()`:
    - Before returning provider, check `exclusion_checker(model_name)`
    - If excluded, use fallback tier logic
    - Log warning when provider is excluded
  - [x] [REFACTOR] Extract exclusion check to helper method
  - [x] Verification: Test confirms excluded model is not selected

- [x] Task 3: Update _find_available_provider for exclusion (AC: #7) <!-- id: 2 -->
  - [x] [RED] Write failing test: `test_fallback_respects_exclusion`
  - [x] [GREEN] Update `ModelRouter._find_available_provider()`:
    - Check exclusion_checker for each provider in fallback chain
    - Skip excluded providers during fallback
  - [x] [REFACTOR] Add metrics for fallback due to exclusion
  - [x] Verification: Test confirms fallback chain respects exclusions

### Phase 2: Gateway Circuit Breaker Enhancement

- [x] Task 4: Expose is_excluded method on LLMGateway (AC: #6) <!-- id: 3 -->
  - [x] [RED] Write failing test: `test_gateway_is_excluded`
  - [x] [GREEN] Add `is_excluded(model_name: str) -> bool` method:
    - Check `_model_excluded_until` with current time
    - Return True if model is currently excluded
    - Thread-safe with `_cb_lock`
  - [x] [REFACTOR] Add docstring and logging
  - [x] Verification: Test confirms correct exclusion status

- [x] Task 5: Wire exclusion checker to router at gateway init (AC: #6, #7) <!-- id: 4 -->
  - [x] [RED] Write failing test: `test_gateway_router_exclusion_integration`
  - [x] [GREEN] Update gateway/router integration:
    - Pass `gateway.is_excluded` as exclusion_checker to router
    - Or: Set exclusion_checker on router after gateway init
    - Handle circular dependency if needed
  - [x] [REFACTOR] Consider factory pattern for cleaner initialization
  - [x] Verification: Test confirms excluded models are skipped during selection

- [x] Task 6: Add exclusion expiry logging (AC: #6) <!-- id: 5 -->
  - [x] [RED] Write failing test: `test_exclusion_expiry_logging`
  - [x] [GREEN] Log when model exclusion expires (on next `is_excluded` check)
  - [x] [REFACTOR] Add metrics for exclusion expiry events
  - [x] Verification: Test confirms log emitted on expiry

### Phase 3: Retry Policy Abstraction

- [x] Task 7: Create RetryPolicy dataclass (AC: #3, #4, #5) <!-- id: 6 -->
  - [x] [RED] Write failing test: `test_retry_policy_creation`
  - [x] [GREEN] Create `RetryPolicy` in `llm/retry.py`:
    ```python
    @dataclass
    class RetryPolicy:
        max_retries: int = 3
        backoff_delays: Tuple[float, ...] = (1.0, 2.0, 4.0)
        request_timeout: float = 100.0
        cb_failure_threshold: int = 3
        cb_exclusion_duration: float = 60.0
    ```
  - [x] [REFACTOR] Add validation in `__post_init__`
  - [x] Verification: Test confirms policy creation with defaults

- [x] Task 8: Update LLMGateway and Factory to use RetryPolicy (AC: #3, #4, #5) <!-- id: 7 -->
  - [x] [RED] Write failing test: `test_gateway_uses_retry_policy` and `test_initialize_gateway_config`
  - [x] [GREEN] Refactor `LLMGateway.__init__`:
    - Accept `retry_policy: RetryPolicy = RetryPolicy()` parameter
    - Remove individual timeout/retry parameters
  - [x] [GREEN] Update `initialize_gateway` factory:
    - Accept optional `retry_policy`
    - Pass to `LLMGateway` constructor
  - [x] Verification: Test confirms policy is respected and factory accepts config

### Phase 4: Error Handling Enhancement

- [x] Task 9: Add graceful error response on all retries exhausted (AC: #5) <!-- id: 8 -->
  - [x] [RED] Write failing test: `test_graceful_error_after_retries`
  - [x] [GREEN] Ensure `_execute_with_retry` returns LLMError with:
    - Clear message including retry count and last error
    - Structured error fields for monitoring
  - [x] [REFACTOR] Add error categorization (transient vs permanent)
  - [x] Verification: Test confirms structured error on failure

- [x] Task 10: Implement LLMRateLimitExceeded retry behavior (AC: #3) <!-- id: 9 -->
  - [x] [RED] Write failing test: `test_rate_limit_retry_respects_retry_after`
  - [x] [GREEN] When LLMRateLimitExceeded has `retry_after`, use that delay
  - [x] [REFACTOR] Cap retry_after at reasonable maximum (60s)
  - [x] Verification: Test confirms retry_after is respected

### Phase 5: Module Exports & Integration Tests

- [x] Task 11: Export RetryPolicy from llm package (AC: all) <!-- id: 10 -->
  - [x] [GREEN] Update `src/cyberred/llm/__init__.py`:
    - Add `RetryPolicy` to imports and exports
  - [x] [REFACTOR] Update `__all__` list
  - [x] Verification: Test confirms imports work from package

- [x] Task 12: Verify 100% coverage (AC: #3-#7) <!-- id: 11 -->
  - [x] Run: `pytest --cov=src/cyberred/llm/gateway --cov=src/cyberred/llm/router --cov=src/cyberred/llm/retry --cov-report=term-missing tests/unit/llm/`
  - [x] Verify 100% line coverage on all files
  - [x] Add any missing edge case tests
  - [x] Verification: Coverage report shows 100%

- [x] Task 13: Integration tests for timeout scenarios (AC: #8) <!-- id: 12 -->
  - [x] Create/update `tests/integration/test_llm_timeout_retry.py`:
    - Test end-to-end flow with mock provider that times out
    - Test circuit breaker excludes model after 3 failures
    - Test excluded model recovery after 60s
    - Test fallback to different tier when primary excluded
  - [x] Run: `pytest tests/integration/test_llm_timeout_retry.py -v`
  - [x] Verification: All integration tests pass



## Dev Notes

### Architecture Context

Per architecture (lines 199-200):
> ERR2: LLM provider timeout — retry 3x with exponential backoff, use available models only

Per architecture (line 92):
> **100s per-model timeout, 180s aggregate timeout** for entire ensemble. Response validation, circuit breaker (3 failures → exclude temporarily)

Per epics-stories (lines 1665-1667):
- Circuit breaker: 3 failures → exclude for 60s
- Timeout: 100s per model, 180s aggregate for ensemble

### Story 3.10 Implementation Review

Story 3.10 implemented:
- ✅ `_execute_with_retry()` with 3x retry, exponential backoff (1s, 2s, 4s)
- ✅ `_record_failure()` / `_record_success()` for circuit breaker state
- ✅ `_model_failures` and `_model_excluded_until` dicts
- ✅ Calls `router.refresh_availability()` when circuit breaker triggers

**Gap identified:** The circuit breaker records exclusions but the router doesn't check them during model selection. This story completes the integration.

### Existing LLM Infrastructure

Located at `src/cyberred/llm/`:
- `gateway.py` — `LLMGateway` with retry logic and CB state
- `router.py` — `ModelRouter` with tier selection and fallback
- `provider.py` — `LLMProvider` ABC, `LLMRequest`, `LLMResponse`
- `nim.py` — `NIMProvider` with model tiers
- `rate_limiter.py` — `RateLimiter` (30 RPM)
- `priority_queue.py` — `LLMPriorityQueue`

### Exception Hierarchy

From `src/cyberred/core/exceptions.py`:
- `LLMError(CyberRedError)` — Base LLM exception
- `LLMProviderUnavailable(LLMError)` — Provider not reachable
- `LLMRateLimitExceeded(LLMError)` — Rate limit exceeded (30 RPM)
- `LLMTimeoutError(LLMError)` — Request timeout (100s)

> [!IMPORTANT]
> **Use existing exceptions from `core/exceptions.py`.** Do NOT define new exception classes.

### Previous Story Learnings (Story 3.10)

From Story 3.10 (LLMGateway):
- Use `threading.Lock()` for thread-safe counters (`_metrics_lock`, `_cb_lock`)
- Use `structlog` for logging: `log = structlog.get_logger()`
- Use `time.monotonic()` for timing measurements
- Export all public types via `__init__.py`
- Achieve 100% test coverage on all new modules

### Code Patterns to Follow

**Router Exclusion Callback Pattern:**
```python
# In router.py
class ModelRouter:
    def __init__(
        self,
        providers: Dict[TaskComplexity, NIMProvider],
        default_tier: TaskComplexity = TaskComplexity.STANDARD,
        exclusion_checker: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self._providers = providers
        self._default_tier = default_tier
        self._exclusion_checker = exclusion_checker or (lambda _: False)
        # ... rest of init
    
    def select_model(self, complexity: TaskComplexity) -> NIMProvider:
        provider = self._providers.get(complexity)
        
        if provider:
            model_name = getattr(provider, "model_name", None)
            if model_name and self._exclusion_checker(model_name):
                log.warning(
                    "model_excluded_by_circuit_breaker",
                    model=model_name,
                    tier=complexity.value,
                )
                # Fall through to fallback logic
            else:
                # Update metrics and return
                return provider
        
        # Fallback logic...
```

**Gateway Exclusion Check Pattern:**
```python
# In gateway.py
def is_excluded(self, model_name: str) -> bool:
    """Check if a model is currently excluded by circuit breaker.
    
    Args:
        model_name: The model identifier to check.
        
    Returns:
        True if model is excluded, False otherwise.
    """
    with self._cb_lock:
        excluded_until = self._model_excluded_until.get(model_name)
        if excluded_until is None:
            return False
        
        now = time.monotonic()
        if now >= excluded_until:
            # Exclusion expired - clean up
            del self._model_excluded_until[model_name]
            log.info("circuit_breaker_reset", model=model_name)
            return False
        
        return True
```

**RetryPolicy Pattern:**
```python
# In llm/retry.py
from dataclasses import dataclass
from typing import Tuple

@dataclass
class RetryPolicy:
    """Configuration for retry behavior and circuit breaker.
    
    Per ERR2: 3x retry with exponential backoff.
    Per architecture: 100s timeout, 3 failures → 60s exclusion.
    """
    max_retries: int = 3
    backoff_delays: Tuple[float, ...] = (1.0, 2.0, 4.0)
    request_timeout: float = 100.0
    cb_failure_threshold: int = 3
    cb_exclusion_duration: float = 60.0
    
    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be > 0")
        if self.cb_failure_threshold < 1:
            raise ValueError("cb_failure_threshold must be >= 1")
        if self.cb_exclusion_duration <= 0:
            raise ValueError("cb_exclusion_duration must be > 0")
```

### Testing Patterns

**Integration Test Pattern:**
```python
# tests/integration/test_llm_timeout_retry.py
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from cyberred.llm.gateway import (
    LLMGateway, initialize_gateway, shutdown_gateway,
)
from cyberred.llm.provider import LLMRequest, LLMResponse
from cyberred.llm.rate_limiter import RateLimiter
from cyberred.llm.router import ModelRouter, TaskComplexity
from cyberred.llm.priority_queue import LLMPriorityQueue


class TestCircuitBreakerIntegration:
    @pytest.fixture
    def timeout_provider(self):
        """Provider that always times out."""
        provider = AsyncMock()
        provider.model_name = "timeout-model"
        provider.complete_async.side_effect = asyncio.TimeoutError()
        return provider
    
    @pytest.fixture
    def fallback_provider(self):
        """Provider that always succeeds."""
        provider = AsyncMock()
        provider.model_name = "fallback-model"
        provider.complete_async.return_value = LLMResponse(
            content="success",
            model="fallback-model",
            usage=None,
        )
        return provider
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_excludes_model(
        self, timeout_provider, fallback_provider
    ):
        """Test that model is excluded after 3 failures."""
        # Setup with timeout provider
        rate_limiter = RateLimiter(rpm=30, burst=5)
        router = ModelRouter(
            providers={TaskComplexity.STANDARD: timeout_provider}
        )
        queue = LLMPriorityQueue()
        
        gateway = LLMGateway(
            rate_limiter, router, queue, request_timeout=0.1
        )
        
        # Wire exclusion checker
        router._exclusion_checker = gateway.is_excluded
        
        async with gateway:
            # Trigger 3 failures
            for _ in range(3):
                try:
                    await gateway.agent_complete(LLMRequest(
                        prompt="test", model="auto"
                    ))
                except Exception:
                    pass
            
            # Model should now be excluded
            assert gateway.is_excluded("timeout-model")
```

### Library Versions

- Python: 3.11+
- asyncio: stdlib
- structlog: Already in project
- threading: stdlib

### Project Structure Notes

Files to create:
- `src/cyberred/llm/retry.py`
- `tests/integration/test_llm_timeout_retry.py`

Files to modify:
- `src/cyberred/llm/router.py` — Add exclusion_checker parameter
- `src/cyberred/llm/gateway.py` — Add is_excluded method
- `src/cyberred/llm/__init__.py` — Export RetryPolicy
- `tests/unit/llm/test_router.py` — Add exclusion tests
- `tests/unit/llm/test_gateway.py` — Add is_excluded tests

### References

- [Source: docs/3-solutioning/architecture.md#line-92] Director deadlock mitigation, 100s timeout, circuit breaker
- [Source: docs/3-solutioning/architecture.md#line-199-200] ERR2 handling
- [Source: _bmad-output/planning-artifacts/epics-stories.md#line-1648-1668] Story 3.11 requirements
- [Source: src/cyberred/llm/gateway.py] Existing retry and CB implementation
- [Source: src/cyberred/llm/router.py] ModelRouter select_model and fallback logic
- [Source: _bmad-output/implementation-artifacts/3-10-llm-gateway-singleton.md] Previous story patterns

## Dev Agent Record

### Agent Model Used

Code Review Agent (via /code-review workflow)

### Debug Log References

- Integration test mock issues resolved by using `MagicMock` for sync methods instead of `AsyncMock`
- `get_model_name()` returns coroutine with `AsyncMock`, causing router exclusion check to fail

### Completion Notes List

- Task 9: Implemented structured error response in `_process_requests()` with error categorization (transient vs permanent) and structured `finish_reason` field (`error:{type}:{class}`)
- Task 10: Implemented `retry_after` handling in `_execute_with_retry()` for `LLMRateLimitExceeded`, capped at 60s maximum
- Fixed unit tests in `test_router.py` to use `LLMProviderUnavailable` instead of generic `Exception`
- Fixed unit tests in `test_gateway.py` to verify structured error fields
- Created comprehensive integration test suite

### File List

- `src/cyberred/llm/gateway.py` — Added structured error response (Task 9), retry_after handling (Task 10)
- `src/cyberred/llm/retry.py` — RetryPolicy dataclass (from previous tasks)
- `src/cyberred/llm/router.py` — Exclusion callback integration (from previous tasks)
- `tests/unit/llm/test_gateway.py` — Added retry_after tests, updated graceful error test
- `tests/unit/llm/test_router.py` — Fixed exception types from generic `Exception` to `LLMProviderUnavailable`
- `tests/integration/llm/test_llm_timeout_retry.py` — NEW: Comprehensive timeout/retry integration tests
