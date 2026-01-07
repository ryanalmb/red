# Story 3.10: LLM Gateway (Singleton)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **a singleton LLM gateway that manages all requests**,
So that **rate limiting and routing are centralized**.

## Acceptance Criteria

1. **Given** Stories 3.6 (NIM Provider), 3.7 (Rate Limiter), 3.8 (Model Router), 3.9 (Priority Queue) are complete
2. **When** any component needs LLM completion
3. **Then** request goes through `LLMGateway.complete()` or `director_complete()` / `agent_complete()`
4. **And** gateway applies rate limiting via `RateLimiter`
5. **And** gateway routes to appropriate model via `ModelRouter`
6. **And** gateway respects priority queue ordering via `LLMPriorityQueue`
7. **And** gateway handles provider timeout with retry (ERR2: 3x with exponential backoff)
8. **And** unit tests verify all gateway functionality with 100% coverage
9. **And** integration tests verify end-to-end gateway flow

## Tasks / Subtasks

> [!IMPORTANT]
> **TDD REQUIRED:** Each task MUST follow the Red-Green-Refactor cycle. Use phase markers:
> - `[RED]` — Write failing test first (test must fail before implementation)
> - `[GREEN]` — Write minimal code to make test pass
> - `[REFACTOR]` — Clean up code while keeping tests green

### Phase 1: Gateway Core Structure

- [x] Task 1: Create LLMGateway class skeleton (AC: #2, #3) <!-- id: 0 -->
  - [x] [RED] Write failing test: `test_gateway_creation`
  - [x] [GREEN] Implement `LLMGateway` class in `src/cyberred/llm/gateway.py`:
    - Constructor accepts: `rate_limiter: RateLimiter`, `router: ModelRouter`, `queue: LLMPriorityQueue`
    - Internal state: `_running: bool`, `_worker_task: Optional[asyncio.Task]`
    - Module-level singleton accessor: `get_gateway()` function
    - Add class docstring explaining gateway role (centralized LLM request management)
  - [x] [REFACTOR] Add type hints and logging with `structlog`
  - [x] Verification: Test confirms gateway instantiation

- [x] Task 2: Implement singleton pattern (AC: #3) <!-- id: 1 -->
  - [x] [RED] Write failing test: `test_gateway_singleton`
  - [x] [GREEN] Implement singleton pattern:
    - Module-level `_gateway_instance: Optional[LLMGateway] = None`
    - `initialize_gateway(rate_limiter, router, queue)` → creates and stores instance
    - `get_gateway()` → returns instance (raises if not initialized)
    - `shutdown_gateway()` → gracefully shuts down and clears instance
    - Thread-safe initialization using `threading.Lock()`
  - [x] [REFACTOR] Add docstrings explaining singleton lifecycle
  - [x] Verification: Test confirms same instance returned on multiple calls

### Phase 2: Request Entry Points

- [x] Task 3: Implement director_complete method (AC: #3, #6) <!-- id: 2 -->
  - [x] [RED] Write failing test: `test_director_complete`
  - [x] [GREEN] Implement `async director_complete(request: LLMRequest) -> LLMResponse`:
    - Enqueue via `queue.enqueue_director(request)`
    - Return the awaited future result
    - Log completion event with priority, model, latency
  - [x] [REFACTOR] Add detailed error handling and logging
  - [x] Verification: Test confirms director requests enqueued with priority 0

- [x] Task 4: Implement agent_complete method (AC: #3, #6) <!-- id: 3 -->
  - [x] [RED] Write failing test: `test_agent_complete`
  - [x] [GREEN] Implement `async agent_complete(request: LLMRequest) -> LLMResponse`:
    - Enqueue via `queue.enqueue_agent(request)`
    - Return the awaited future result
    - Log completion event with priority, model, latency
  - [x] [REFACTOR] Extract common logic to `_submit_request()` helper
  - [x] Verification: Test confirms agent requests enqueued with priority 1

- [x] Task 5: Implement generic complete method (AC: #3) <!-- id: 4 -->
  - [x] [RED] Write failing test: `test_generic_complete`
  - [x] [GREEN] Implement `async complete(request: LLMRequest, is_director: bool = False) -> LLMResponse`:
    - Convenience method that delegates to `director_complete()` or `agent_complete()`
    - Default is agent priority
  - [x] [REFACTOR] Use as unified entry point
  - [x] Verification: Test confirms routing to correct method

### Phase 3: Background Worker

- [x] Task 6: Implement request processing worker (AC: #4, #5, #6) <!-- id: 5 -->
  - [x] [RED] Write failing test: `test_worker_processes_requests`
  - [x] [GREEN] Implement `async _process_requests()`:
    - Infinite loop while `_running`:
      - Dequeue from priority queue
      - Apply rate limiting via `rate_limiter.acquire_async()`
      - Route to model via `router.select_model(complexity)`
      - Execute request via `provider.complete_async(request)`
      - Set result on future via `queue.complete_request(priority_request, response)`
    - Handle cancellation gracefully
  - [x] [REFACTOR] Add comprehensive logging at each stage
  - [x] Verification: Test confirms requests processed in priority order

- [x] Task 7: Implement gateway start/stop lifecycle (AC: #2) <!-- id: 6 -->
  - [x] [RED] Write failing test: `test_gateway_lifecycle`
  - [x] [GREEN] Implement lifecycle methods:
    - `async start()`: Create and start `_worker_task`
    - `async stop()`: Set `_running = False`, cancel worker, await cleanup
    - `async __aenter__` and `async __aexit__` for context manager
  - [x] [REFACTOR] Handle edge cases (double start, stop without start)
  - [x] Verification: Test confirms clean start and stop

### Phase 4: Retry Logic (ERR2)

- [x] Task 8: Implement timeout handling (AC: #7) <!-- id: 7 -->
  - [x] [RED] Write failing test: `test_request_timeout`
  - [x] [GREEN] Add timeout for provider calls:
    - Default timeout: 100s per request (from architecture)
    - Use `asyncio.wait_for()` wrapper
    - Raise `LLMTimeoutError` on timeout
  - [x] [REFACTOR] Make timeout configurable
  - [x] Verification: Test confirms timeout raises appropriate exception

- [x] Task 9: Implement exponential backoff retry (AC: #7) <!-- id: 8 -->
  - [x] [RED] Write failing test: `test_retry_with_backoff`
  - [x] [GREEN] Implement retry logic in worker:
    - Retry up to 3 times on timeout or transient errors
    - Backoff: 1s, 2s, 4s (exponential)
    - Log each retry attempt
    - On all retries exhausted, fail request with final exception
  - [x] [REFACTOR] Extract to `_execute_with_retry()` helper
  - [x] Verification: Test confirms correct retry count and delays

- [x] Task 10: Implement circuit breaker integration (AC: #7) <!-- id: 9 -->
  - [x] [RED] Write failing test: `test_circuit_breaker_excludes_model`
  - [x] [GREEN] Implement basic circuit breaker:
    - Track failure count per model
    - After 3 failures, exclude model for 60s
    - Use `router.refresh_availability()` to force recheck
    - Log circuit breaker events
  - [x] [REFACTOR] Add circuit breaker state properties for monitoring
  - [x] Verification: Test confirms model exclusion after failures

### Phase 5: Error Handling & Monitoring

- [x] Task 11: Implement comprehensive error handling (AC: #7) <!-- id: 10 -->
  - [x] [RED] Write failing test: `test_error_handling`
  - [x] [GREEN] Handle all error types:
    - `LLMProviderUnavailable` → Retry with different provider if available
    - `LLMRateLimitExceeded` → Wait and retry (respect retry_after)
    - `LLMTimeoutError` → Retry with backoff (already in Task 9)
    - Other exceptions → Log and fail request
  - [x] [REFACTOR] Centralize error handling in worker
  - [x] Verification: Test confirms appropriate handling for each error type

- [x] Task 12: Implement gateway metrics (AC: #4, #5, #6) <!-- id: 11 -->
  - [x] [RED] Write failing test: `test_gateway_metrics`
  - [x] [GREEN] Add monitoring properties:
    - `total_requests: int` — Total requests processed
    - `total_successes: int` — Successful completions
    - `total_failures: int` — Failed requests
    - `total_retries: int` — Retry events
    - `avg_latency_ms: float` — Average request latency
    - `queue_depth` — Delegate to `queue.total_queue_depth`
  - [x] [REFACTOR] Thread-safe counters using `threading.Lock()`
  - [x] Verification: Test confirms accurate metrics tracking

### Phase 6: Integration & Module Exports

- [x] Task 13: Export from llm package (AC: all) <!-- id: 12 -->
  - [x] [GREEN] Update `src/cyberred/llm/__init__.py`:
    - Add `LLMGateway` to imports and exports
    - Add `get_gateway`, `initialize_gateway`, `shutdown_gateway` to exports
  - [x] [REFACTOR] Update `__all__` list
  - [x] Verification: Test confirms imports work from package

- [x] Task 14: Unit tests with comprehensive coverage (AC: #8) <!-- id: 13 -->
  - [x] Create `tests/unit/llm/test_gateway.py`:
    - Test gateway creation and singleton pattern
    - Test director and agent complete methods
    - Test request priority ordering
    - Test rate limiting integration
    - Test model routing integration
    - Test timeout handling
    - Test retry with exponential backoff
    - Test circuit breaker behavior
    - Test error handling for all exception types
    - Test metrics tracking
    - Test lifecycle (start/stop)
  - [x] Run: `pytest tests/unit/llm/test_gateway.py -v`
  - [x] Verification: All unit tests pass

- [x] Task 15: Verify 100% coverage (AC: #8) <!-- id: 14 -->
  - [x] Run: `pytest --cov=src/cyberred/llm/gateway --cov-report=term-missing tests/unit/llm/`
  - [x] Verify 100% line coverage on `llm/gateway.py`
  - [x] Add any missing edge case tests
  - [x] Verification: Coverage report shows 100%

- [x] Task 16: Integration tests (AC: #9) <!-- id: 15 -->
  - [x] Create `tests/integration/test_llm_gateway.py`:
    - Test end-to-end flow with mock provider
    - Test priority ordering under concurrent load
    - Test retry behavior with simulated timeouts
    - Test circuit breaker with failing provider
  - [x] Run: `pytest tests/integration/test_llm_gateway.py -v`
  - [x] Verification: All integration tests pass

## Dev Notes

### Architecture Context

Per architecture (lines 131, 833-836):
- Global rate limit: **30 RPM** shared across swarm
- Located in `src/cyberred/llm/gateway.py`
- Singleton pattern via module-level instance
- Centralizes all LLM requests from agents and Director Ensemble

> [!NOTE]
> Per architecture (line 990): "All LLM calls through `LLMProvider` protocol"

Per architecture (line 92) - Director Deadlock mitigation:
> **100s per-model timeout, 180s aggregate timeout** for entire ensemble. Response validation, circuit breaker (3 failures → exclude temporarily).

### Error Handling (ERR2)

Per architecture (lines 199-200):
> ERR2: LLM provider timeout — retry 3x with exponential backoff, use available models only

Per epics-stories (lines 1644):
> ERR2: 3x retry with exponential backoff

Retry configuration:
- Max retries: 3
- Backoff delays: 1s, 2s, 4s
- Timeout per request: 100s
- Aggregate timeout for ensemble: 180s
- Circuit breaker: 3 failures → exclude for 60s

### Existing LLM Infrastructure (Stories 3.5-3.9)

Located at `src/cyberred/llm/`:
- `provider.py` — `LLMProvider` ABC, `LLMRequest`, `LLMResponse`, `TokenUsage`, `HealthStatus`, `MockLLMProvider`
- `nim.py` — `NIMProvider` with `MODELS` dict and `for_tier()` factory
- `rate_limiter.py` — `RateLimiter` (token bucket, 30 RPM) and `RateLimitedProvider`
- `router.py` — `ModelRouter`, `TaskComplexity`, `ModelConfig` for tier selection
- `priority_queue.py` — `LLMPriorityQueue`, `RequestPriority`, `PriorityRequest`
- `__init__.py` — Package exports

### Integration with Existing Components

The `LLMGateway` integrates all prior LLM infrastructure:

```python
# Gateway initialization pattern (Story 3.10)
from cyberred.llm import (
    LLMGateway, initialize_gateway, get_gateway, shutdown_gateway,
    RateLimiter, ModelRouter, LLMPriorityQueue, 
    NIMProvider, TaskComplexity,
)

# Create components
rate_limiter = RateLimiter(rpm=30, burst=5)
providers = {
    TaskComplexity.FAST: NIMProvider.for_tier("FAST"),
    TaskComplexity.STANDARD: NIMProvider.for_tier("STANDARD"),
    TaskComplexity.COMPLEX: NIMProvider.for_tier("COMPLEX"),
}
router = ModelRouter(providers)
queue = LLMPriorityQueue()

# Initialize singleton gateway
initialize_gateway(rate_limiter, router, queue)

# Use the gateway
async with get_gateway() as gateway:
    # Director strategic requests (priority 0)
    response = await gateway.director_complete(LLMRequest(
        prompt="Synthesize attack strategy",
        model="auto",  # Router will select
    ))
    
    # Agent requests (priority 1)
    response = await gateway.agent_complete(LLMRequest(
        prompt="Analyze nmap output",
        model="auto",
    ))
```

### Exception Handling

Located in `src/cyberred/core/exceptions.py`:
- `LLMError(CyberRedError)` — Base LLM exception
- `LLMProviderUnavailable(LLMError)` — Provider not reachable
- `LLMRateLimitExceeded(LLMError)` — Rate limit exceeded (30 RPM)
- `LLMTimeoutError(LLMError)` — Request timeout (100s)

> [!IMPORTANT]
> **Use existing exceptions from `core/exceptions.py`.** Do NOT define new exception classes.

`LLMTimeoutError` signature (from exceptions.py):
```python
LLMTimeoutError(
    provider: str,
    timeout_seconds: float,
    request_id: str | None = None,
    message: str | None = None,
)
```

### Previous Story Learnings (Stories 3.7, 3.8, 3.9)

From Story 3.7 (RateLimiter):
- Use `asyncio.Condition()` for async waiting patterns
- Use `threading.Lock()` for thread-safe counters
- Use `time.monotonic()` for timing measurements
- Async methods should use `async with self._condition:`
- All dataclasses validated in `__post_init__()`

From Story 3.8 (ModelRouter):
- Use `structlog` for logging: `log = structlog.get_logger()`
- Thread-safe implementation using `threading.Lock()`
- Export all public types via `__init__.py`
- Achieve 100% test coverage on all new modules

From Story 3.9 (PriorityQueue):
- Use `asyncio.get_running_loop()` (NOT deprecated `get_event_loop()`)
- Implement idempotent completion handling in `complete_request` and `fail_request`
- Log enqueue/dequeue events with priority and sequence

### Code Patterns to Follow

**LLMGateway Pattern:**
```python
import asyncio
import threading
import time
from typing import Optional, Dict

import structlog

from cyberred.llm.provider import LLMRequest, LLMResponse
from cyberred.llm.rate_limiter import RateLimiter
from cyberred.llm.router import ModelRouter, TaskComplexity
from cyberred.llm.priority_queue import LLMPriorityQueue, RequestPriority
from cyberred.core.exceptions import (
    LLMTimeoutError, LLMProviderUnavailable, LLMRateLimitExceeded
)

log = structlog.get_logger()

# Singleton instance
_gateway_instance: Optional["LLMGateway"] = None
_gateway_lock = threading.Lock()


def initialize_gateway(
    rate_limiter: RateLimiter,
    router: ModelRouter,
    queue: LLMPriorityQueue,
) -> "LLMGateway":
    """Initialize the singleton gateway instance."""
    global _gateway_instance
    with _gateway_lock:
        if _gateway_instance is not None:
            raise RuntimeError("Gateway already initialized")
        _gateway_instance = LLMGateway(rate_limiter, router, queue)
        return _gateway_instance


def get_gateway() -> "LLMGateway":
    """Get the singleton gateway instance."""
    if _gateway_instance is None:
        raise RuntimeError("Gateway not initialized - call initialize_gateway() first")
    return _gateway_instance


def shutdown_gateway() -> None:
    """Shutdown and clear the singleton gateway instance."""
    global _gateway_instance
    with _gateway_lock:
        if _gateway_instance is not None:
            # Gateway shutdown handled by caller via async context manager
            _gateway_instance = None


class LLMGateway:
    """Singleton LLM gateway that manages all requests.
    
    Centralizes rate limiting, model routing, and priority queue management.
    Per architecture: All agent and Director LLM requests flow through this gateway.
    
    ERR2 handling: 3x retry with exponential backoff (1s, 2s, 4s).
    """
    
    def __init__(
        self,
        rate_limiter: RateLimiter,
        router: ModelRouter,
        queue: LLMPriorityQueue,
        request_timeout: float = 100.0,
        max_retries: int = 3,
    ) -> None:
        self._rate_limiter = rate_limiter
        self._router = router
        self._queue = queue
        self._request_timeout = request_timeout
        self._max_retries = max_retries
        
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        
        # Metrics
        self._lock = threading.Lock()
        self._total_requests = 0
        self._total_successes = 0
        self._total_failures = 0
        self._total_retries = 0
        self._total_latency_ms = 0.0
        
        # Circuit breaker state per model
        self._model_failures: Dict[str, int] = {}
        self._model_excluded_until: Dict[str, float] = {}
    
    async def director_complete(self, request: LLMRequest) -> LLMResponse:
        """Submit a Director request with highest priority.
        
        Director requests are processed before agent requests.
        """
        future = await self._queue.enqueue_director(request)
        return await future
    
    async def agent_complete(self, request: LLMRequest) -> LLMResponse:
        """Submit an Agent request with normal priority."""
        future = await self._queue.enqueue_agent(request)
        return await future
    
    async def complete(
        self, 
        request: LLMRequest, 
        is_director: bool = False
    ) -> LLMResponse:
        """Submit a request with specified priority.
        
        Args:
            request: The LLM request.
            is_director: If True, use Director priority.
            
        Returns:
            The LLM response.
        """
        if is_director:
            return await self.director_complete(request)
        return await self.agent_complete(request)
    
    async def start(self) -> None:
        """Start the background request processing worker."""
        if self._running:
            log.warning("gateway_already_running")
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._process_requests())
        log.info("gateway_started")
    
    async def stop(self) -> None:
        """Stop the gateway and cleanup."""
        self._running = False
        
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        
        log.info("gateway_stopped")
    
    async def _process_requests(self) -> None:
        """Background worker that processes queued requests."""
        while self._running:
            try:
                # Dequeue with timeout to allow shutdown check
                priority_request = await self._queue.dequeue(timeout=1.0)
            except Exception as e:
                if isinstance(e, asyncio.CancelledError):
                    raise
                # Timeout or other error - continue loop
                continue
            
            start_time = time.monotonic()
            
            try:
                response = await self._execute_with_retry(priority_request.request)
                self._queue.complete_request(priority_request, response)
                
                with self._lock:
                    self._total_requests += 1
                    self._total_successes += 1
                    latency = (time.monotonic() - start_time) * 1000
                    self._total_latency_ms += latency
                
            except Exception as e:
                self._queue.fail_request(priority_request, e)
                
                with self._lock:
                    self._total_requests += 1
                    self._total_failures += 1
    
    async def _execute_with_retry(self, request: LLMRequest) -> LLMResponse:
        """Execute request with retry and exponential backoff.
        
        Per ERR2: 3x retry with exponential backoff (1s, 2s, 4s).
        """
        backoff_delays = [1.0, 2.0, 4.0]
        last_exception: Optional[Exception] = None
        
        for attempt in range(self._max_retries + 1):
            try:
                # Rate limit
                if not await self._rate_limiter.acquire_async(timeout=60.0):
                    raise LLMRateLimitExceeded("gateway", 30)
                
                # Route to model
                # Infer complexity from request or use default
                complexity = self._router.infer_complexity(request.prompt)
                provider = self._router.select_model(complexity)
                
                # Execute with timeout
                response = await asyncio.wait_for(
                    provider.complete_async(request),
                    timeout=self._request_timeout,
                )
                
                return response
                
            except asyncio.TimeoutError:
                last_exception = LLMTimeoutError(
                    provider="gateway",
                    timeout_seconds=self._request_timeout,
                )
            except (LLMProviderUnavailable, LLMTimeoutError) as e:
                last_exception = e
            except Exception as e:
                # Non-retryable error
                raise
            
            # Apply backoff if retry remaining
            if attempt < self._max_retries:
                delay = backoff_delays[attempt]
                
                with self._lock:
                    self._total_retries += 1
                
                log.warning(
                    "gateway_retry",
                    attempt=attempt + 1,
                    max_retries=self._max_retries,
                    delay=delay,
                    error=str(last_exception),
                )
                
                await asyncio.sleep(delay)
        
        # All retries exhausted
        raise last_exception if last_exception else RuntimeError("Unknown error")
    
    @property
    def total_requests(self) -> int:
        """Total requests processed."""
        with self._lock:
            return self._total_requests
    
    @property
    def total_successes(self) -> int:
        """Successful completions."""
        with self._lock:
            return self._total_successes
    
    @property
    def total_failures(self) -> int:
        """Failed requests."""
        with self._lock:
            return self._total_failures
    
    @property
    def total_retries(self) -> int:
        """Total retry events."""
        with self._lock:
            return self._total_retries
    
    @property
    def avg_latency_ms(self) -> float:
        """Average request latency in milliseconds."""
        with self._lock:
            if self._total_successes == 0:
                return 0.0
            return self._total_latency_ms / self._total_successes
    
    @property
    def queue_depth(self) -> int:
        """Current queue depth."""
        return self._queue.total_queue_depth
    
    async def __aenter__(self) -> "LLMGateway":
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
```

### Testing Patterns

**Gateway Test Pattern:**
```python
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cyberred.llm.gateway import (
    LLMGateway, initialize_gateway, get_gateway, shutdown_gateway,
)
from cyberred.llm.provider import LLMRequest, LLMResponse
from cyberred.llm.rate_limiter import RateLimiter
from cyberred.llm.router import ModelRouter, TaskComplexity
from cyberred.llm.priority_queue import LLMPriorityQueue


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.complete_async.return_value = LLMResponse(
        content="test response",
        model="test-model",
        usage=None,
    )
    return provider


@pytest.fixture
def gateway_components(mock_provider):
    rate_limiter = RateLimiter(rpm=30, burst=5)
    router = MagicMock(spec=ModelRouter)
    router.select_model.return_value = mock_provider
    router.infer_complexity.return_value = TaskComplexity.STANDARD
    queue = LLMPriorityQueue()
    return rate_limiter, router, queue


class TestGatewayCreation:
    def test_gateway_creation(self, gateway_components):
        rate_limiter, router, queue = gateway_components
        gateway = LLMGateway(rate_limiter, router, queue)
        
        assert gateway is not None
        assert gateway.total_requests == 0
        assert gateway.queue_depth == 0


class TestGatewaySingleton:
    def test_singleton_pattern(self, gateway_components):
        rate_limiter, router, queue = gateway_components
        
        # Initialize
        g1 = initialize_gateway(rate_limiter, router, queue)
        g2 = get_gateway()
        
        assert g1 is g2
        
        # Cleanup
        shutdown_gateway()


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_retry_with_backoff(self, gateway_components, mock_provider):
        rate_limiter, router, queue = gateway_components
        
        # Configure provider to fail twice then succeed
        mock_provider.complete_async.side_effect = [
            asyncio.TimeoutError(),
            asyncio.TimeoutError(),
            LLMResponse(content="success", model="test", usage=None),
        ]
        
        gateway = LLMGateway(rate_limiter, router, queue)
        
        async with gateway:
            request = LLMRequest(prompt="test", model="test")
            future = await queue.enqueue_agent(request)
            
            # Allow worker to process
            await asyncio.sleep(0.1)
            
            # Verify retries occurred
            assert gateway.total_retries == 2
```

### Library Versions

- Python: 3.11+
- asyncio: stdlib
- structlog: Already in project
- threading: stdlib

### Project Structure Notes

Files to create:
- `src/cyberred/llm/gateway.py`
- `tests/unit/llm/test_gateway.py`
- `tests/integration/test_llm_gateway.py`

Files to modify:
- `src/cyberred/llm/__init__.py` — Add gateway exports

### References

- [Source: docs/3-solutioning/architecture.md#line-131] 30 RPM global rate limit
- [Source: docs/3-solutioning/architecture.md#line-833-836] gateway.py location  
- [Source: docs/3-solutioning/architecture.md#line-92] Director deadlock mitigation, 100s timeout
- [Source: docs/3-solutioning/architecture.md#line-990] All LLM calls through protocol
- [Source: _bmad-output/planning-artifacts/epics-stories.md#line-1624-1645] Story 3.10 requirements
- [Source: src/cyberred/llm/rate_limiter.py] RateLimiter async patterns
- [Source: src/cyberred/llm/priority_queue.py] Priority queue patterns
- [Source: _bmad-output/implementation-artifacts/3-9-llm-priority-queue.md] Previous story patterns

## Dev Agent Record


### Agent Model Used

Gemini 2.0 (via BMad)

### Debug Log References

- Code Review Fixes: `cf34390f-afcd-48ea-9ecc-e3859bdcfa3e` (final test run)

### Completion Notes List

- Fixed Critical Issue: `__init__.py` exported gateway symbols but did not import them.
- Fixed High Issue: Implemented missing metrics (Task 12) in `gateway.py` and added unit tests.
- Fixed High Issue: Created integration tests (Task 16) in `tests/integration/test_llm_gateway.py`.
- Fixed Low Issue: Implemented circuit breaker failure count reset logic (Issue #8) and added test coverage.
- Achieved 100% test coverage for `src/cyberred/llm/gateway.py`.
- Verified end-to-end flow with integration tests.

### File List

- src/cyberred/llm/gateway.py
- src/cyberred/llm/__init__.py
- tests/unit/llm/test_gateway.py
- tests/integration/test_llm_gateway.py

