# Story 3.9: LLM Priority Queue

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **Director requests prioritized over agent requests**,
So that **strategic re-planning is never starved by agent volume**.

## Acceptance Criteria

1. **Given** Story 3.7 is complete (RateLimiter exists)
2. **When** Director and agents submit concurrent requests
3. **Then** Director requests are processed first (priority: 0)
4. **And** Agent requests follow (priority: 1)
5. **And** within same priority, FIFO ordering is maintained
6. **And** queue depth per priority is exposed for monitoring
7. **And** unit tests verify priority ordering with 100% coverage

## Tasks / Subtasks

> [!IMPORTANT]
> **TDD REQUIRED:** Each task MUST follow the Red-Green-Refactor cycle. Use phase markers:
> - `[RED]` — Write failing test first (test must fail before implementation)
> - `[GREEN]` — Write minimal code to make test pass
> - `[REFACTOR]` — Clean up code while keeping tests green

### Phase 1: Core Data Structures

- [x] Task 1: Create RequestPriority enum (AC: #3, #4) <!-- id: 0 -->
  - [x] [RED] Write failing test: `test_request_priority_enum_values`
  - [x] [GREEN] Implement `RequestPriority` enum in `src/cyberred/llm/priority_queue.py`:
    - Values: `DIRECTOR = 0`, `AGENT = 1`
    - Enum inherits from `int, Enum` for comparison/ordering
    - Add docstring explaining priority semantics (lower = higher priority)
  - [x] [REFACTOR] Ensure Enum values are correctly ordered for PriorityQueue
  - [x] Verification: Test confirms enum values and ordering

- [x] Task 2: Create PriorityRequest dataclass (AC: #3, #4, #5) <!-- id: 1 -->
  - [x] [RED] Write failing test: `test_priority_request_dataclass`
  - [x] [GREEN] Implement `PriorityRequest` dataclass:
    - Fields: `request: LLMRequest`, `priority: RequestPriority`, `sequence: int`, `future: asyncio.Future`
    - Implement `__lt__()` for comparison: first by priority, then by sequence (FIFO within priority)
    - `sequence` is monotonically increasing counter for FIFO ordering
    - `future` is for async result delivery
  - [x] [REFACTOR] Add type hints and docstrings
  - [x] Verification: Test confirms dataclass comparison works correctly

### Phase 2: Priority Queue Core

- [x] Task 3: Create LLMPriorityQueue class skeleton (AC: #2) <!-- id: 2 -->
  - [x] [RED] Write failing test: `test_priority_queue_creation`
  - [x] [GREEN] Implement `LLMPriorityQueue` class:
    - Constructor: `__init__(maxsize: int = 0)`
    - Internal: `asyncio.PriorityQueue` for request storage
    - Internal: `_sequence_counter: int` for FIFO ordering (atomic increment)
    - Internal: `threading.Lock()` for thread-safe sequence generation
  - [x] [REFACTOR] Use clear naming and add class docstring
  - [x] Verification: Test confirms queue instantiation

- [x] Task 4: Implement enqueue methods (AC: #2, #3, #4) <!-- id: 3 -->
  - [x] [RED] Write failing test: `test_enqueue_director_request`
  - [x] [GREEN] Implement `enqueue_director(request: LLMRequest) -> asyncio.Future`:
    - Create `PriorityRequest` with `RequestPriority.DIRECTOR`
    - Assign monotonically increasing sequence number
    - Create and return `asyncio.Future` for result
    - Put into internal PriorityQueue
    - Log enqueue event with `structlog`
  - [x] [RED] Write failing test: `test_enqueue_agent_request`
  - [x] [GREEN] Implement `enqueue_agent(request: LLMRequest) -> asyncio.Future`:
    - Same as director but with `RequestPriority.AGENT`
  - [x] [REFACTOR] Extract common logic to `_enqueue()` helper
  - [x] Verification: Test confirms both enqueue methods work

- [x] Task 5: Implement dequeue method (AC: #3, #4, #5) <!-- id: 4 -->
  - [x] [RED] Write failing test: `test_dequeue_returns_highest_priority`
  - [x] [GREEN] Implement `dequeue() -> PriorityRequest`:
    - Async method that awaits `get()` from internal PriorityQueue
    - Returns `PriorityRequest` (highest priority first, FIFO within priority)
    - Log dequeue event with priority and sequence
  - [x] [RED] Write failing test: `test_dequeue_respects_fifo_within_priority`
  - [x] [GREEN] Verify FIFO ordering for same-priority requests
  - [x] [REFACTOR] Add timeout parameter for non-blocking dequeue option
  - [x] Verification: Test confirms priority + FIFO ordering

### Phase 3: Priority Ordering Validation

- [x] Task 6: Implement priority ordering tests (AC: #3, #4, #5) <!-- id: 5 -->
  - [x] [RED] Write failing test: `test_director_processed_before_agents`
  - [x] [GREEN] Enqueue agent request first, then director request:
    - Dequeue should return director first (priority 0)
    - Then agent (priority 1)
  - [x] [RED] Write failing test: `test_multiple_directors_fifo`
  - [x] [GREEN] Enqueue multiple director requests:
    - Dequeue should return in FIFO order
  - [x] [RED] Write failing test: `test_mixed_priority_ordering`
  - [x] [GREEN] Complex scenario: agents → director → agents → director
    - Verify directors come first (FIFO within directors)
    - Then agents (FIFO within agents)
  - [x] Verification: All priority ordering tests pass

### Phase 4: Monitoring & Metrics (AC: #6)

- [x] Task 7: Implement queue depth monitoring (AC: #6) <!-- id: 6 -->
  - [x] [RED] Write failing test: `test_queue_depth_per_priority`
  - [x] [GREEN] Implement monitoring properties:
    - `director_queue_depth -> int` — count of pending director requests
    - `agent_queue_depth -> int` — count of pending agent requests
    - `total_queue_depth -> int` — total pending requests
  - [x] [GREEN] Track counts internally on enqueue/dequeue
  - [x] [REFACTOR] Use atomic operations for thread safety
  - [x] Verification: Test confirms queue depths are accurate

- [x] Task 8: Implement queue statistics (AC: #6) <!-- id: 7 -->
  - [x] [RED] Write failing test: `test_queue_stats`
  - [x] [GREEN] Implement statistics properties:
    - `total_enqueued: int` — total requests enqueued since init
    - `total_dequeued: int` — total requests dequeued since init
    - `director_enqueued: int` — director requests enqueued
    - `agent_enqueued: int` — agent requests enqueued
  - [x] [REFACTOR] Thread-safe counters using `threading.Lock()`
  - [x] Verification: Test confirms all stats accessible and accurate

### Phase 5: Result Delivery

- [x] Task 9: Implement result delivery mechanism (AC: #2) <!-- id: 8 -->
  - [x] [RED] Write failing test: `test_result_delivery_via_future`
  - [x] [GREEN] Implement result delivery:
    - `complete_request(priority_request: PriorityRequest, response: LLMResponse)`:
      - Set result on the `future` from `PriorityRequest`
      - Log completion event
    - `fail_request(priority_request: PriorityRequest, exception: Exception)`:
      - Set exception on the `future`
      - Log failure event
  - [x] [REFACTOR] Add validation for completed/cancelled futures
  - [x] Verification: Test confirms result delivery works for both success and failure

### Phase 6: Integration Patterns

- [x] Task 10: Implement async context manager (AC: #2) <!-- id: 9 -->
  - [x] [RED] Write failing test: `test_queue_context_manager`
  - [x] [GREEN] Implement `__aenter__` and `__aexit__`:
    - Allow queue to be used as async context manager
    - Clean up pending requests on exit (optional graceful shutdown)
  - [x] [REFACTOR] Add `shutdown()` method for explicit cleanup
  - [x] Verification: Test confirms context manager works

### Phase 7: Module Exports & Testing

- [x] Task 11: Export from llm package (AC: all) <!-- id: 10 -->
  - [x] [GREEN] Update `src/cyberred/llm/__init__.py`:
    - Add `LLMPriorityQueue` to imports and exports
    - Add `RequestPriority` to imports and exports
    - Add `PriorityRequest` to imports and exports
  - [x] [REFACTOR] Update `__all__` list
  - [x] Verification: Test confirms imports work from package

- [x] Task 12: Unit tests with comprehensive coverage (AC: #7) <!-- id: 11 -->
  - [x] Create `tests/unit/llm/test_priority_queue.py`:
    - Test RequestPriority enum values and ordering
    - Test PriorityRequest dataclass and comparison
    - Test LLMPriorityQueue creation
    - Test enqueue for director and agent
    - Test dequeue priority ordering
    - Test FIFO within same priority
    - Test queue depth monitoring
    - Test statistics tracking
    - Test result delivery (success and failure)
    - Test context manager
  - [x] Run: `pytest tests/unit/llm/test_priority_queue.py -v`
  - [x] Verification: All unit tests pass

- [x] Task 13: Verify 100% coverage (AC: #7) <!-- id: 12 -->
  - [x] Run: `pytest --cov=src/cyberred/llm/priority_queue --cov-report=term-missing tests/unit/llm/`
  - [x] Verify 100% line coverage on `llm/priority_queue.py`
  - [x] Add any missing edge case tests
  - [x] Verification: Coverage report shows 100%

## Dev Notes

### Architecture Context

Per architecture (lines 131, 828-836):
- Global rate limit: **30 RPM** shared across swarm
- Located in `src/cyberred/llm/priority_queue.py`
- Prevents agent "flash crowd" from blocking Director strategic re-planning

> [!NOTE]
> Director Ensemble uses separate synthesis models (DeepSeek V3.2, Kimi K2, MiniMax M2) — but still needs priority access to LLM gateway.

Per architecture (line 141):
> **Agent Self-Throttling:** When LLM queue depth exceeds threshold, agents enter WAITING state to prevent queue starvation.

This means the queue depth monitoring (AC #6) is critical for self-throttling behavior.

### Existing LLM Infrastructure (Stories 3.5, 3.6, 3.7, 3.8)

Located at `src/cyberred/llm/`:
- `provider.py` — `LLMProvider` ABC, `LLMRequest`, `LLMResponse`, `TokenUsage`, `HealthStatus`
- `nim.py` — `NIMProvider` with `MODELS` dict and `for_tier()` factory
- `rate_limiter.py` — `RateLimiter` and `RateLimitedProvider`
- `router.py` — `ModelRouter`, `TaskComplexity`, `ModelConfig` for tier selection
- `__init__.py` — Package exports (currently exports: `LLMProvider`, `LLMRequest`, `LLMResponse`, `TokenUsage`, `HealthStatus`, `MockLLMProvider`, `NIMProvider`, `RateLimiter`, `RateLimitedProvider`, `ModelRouter`, `TaskComplexity`, `ModelConfig`)

### Integration with Future LLMGateway (Story 3.10)

The `LLMPriorityQueue` will be used by `LLMGateway` (Story 3.10):
```python
# Future usage in llm/gateway.py (Story 3.10)
class LLMGateway:
    def __init__(self):
        self._queue = LLMPriorityQueue()
        self._router = ModelRouter(...)
        self._rate_limiter = RateLimiter()
    
    async def director_complete(self, request: LLMRequest) -> LLMResponse:
        future = self._queue.enqueue_director(request)
        return await future
    
    async def agent_complete(self, request: LLMRequest) -> LLMResponse:
        future = self._queue.enqueue_agent(request)
        return await future
```

### Exception Handling

Located in `src/cyberred/core/exceptions.py`:
- `LLMRateLimitExceeded(LLMError)` — Use when queue is full
- `LLMTimeoutError(LLMError)` — Use for dequeue timeout

> [!IMPORTANT]
> **Use existing exceptions from `core/exceptions.py`.** Do NOT define new exception classes.

### Previous Story Learnings (Stories 3.7 & 3.8)

From Story 3.7 (RateLimiter):
- Use `asyncio.Condition()` for async waiting patterns
- Use `threading.Lock()` for thread-safe counters
- Use `time.monotonic()` for timing measurements
- Async methods should use `async with self._condition:`
- All dataclasses validated in `__post_init__()`
- Properties for monitoring metrics are essential

From Story 3.8 (ModelRouter):
- Use `structlog` for logging: `log = structlog.get_logger()`
- Thread-safe implementation using `threading.Lock()`
- Export all public types via `__init__.py`
- Achieve 100% test coverage on all new modules
- Use `# pragma: no cover` for unreachable code paths

### Code Patterns to Follow

**RequestPriority Enum:**
```python
from enum import Enum

class RequestPriority(int, Enum):
    """Request priority levels for LLM queue.
    
    Lower numeric value = higher priority.
    DIRECTOR (0) always processes before AGENT (1).
    """
    DIRECTOR = 0  # Strategic re-planning, never starved
    AGENT = 1     # Individual agent requests
```

**PriorityRequest Dataclass:**
```python
import asyncio
from dataclasses import dataclass

from cyberred.llm.provider import LLMRequest

@dataclass
class PriorityRequest:
    """Wrapper for prioritized LLM request.
    
    Comparison is first by priority, then by sequence (FIFO).
    """
    request: LLMRequest
    priority: RequestPriority
    sequence: int
    future: asyncio.Future
    
    def __lt__(self, other: "PriorityRequest") -> bool:
        # First by priority (lower = higher priority)
        if self.priority != other.priority:
            return self.priority < other.priority
        # Then by sequence (FIFO within priority)
        return self.sequence < other.sequence
```

**LLMPriorityQueue Pattern:**
```python
import asyncio
import threading
from typing import Optional

import structlog

from cyberred.llm.provider import LLMRequest, LLMResponse
from cyberred.core.exceptions import LLMTimeoutError

log = structlog.get_logger()

class LLMPriorityQueue:
    """Priority queue for LLM requests.
    
    Director requests (priority 0) always processed before agent requests (priority 1).
    Within same priority, FIFO ordering is maintained.
    
    Per architecture: Prevents agent flash crowd from blocking Director.
    """
    
    def __init__(self, maxsize: int = 0) -> None:
        self._queue: asyncio.PriorityQueue[PriorityRequest] = asyncio.PriorityQueue(maxsize)
        self._sequence_counter = 0
        self._lock = threading.Lock()
        
        # Metrics
        self._director_pending = 0
        self._agent_pending = 0
        self._total_enqueued = 0
        self._director_enqueued = 0
        self._agent_enqueued = 0
        self._total_dequeued = 0
    
    def _next_sequence(self) -> int:
        """Get next sequence number (thread-safe)."""
        with self._lock:
            seq = self._sequence_counter
            self._sequence_counter += 1
            return seq
    
    async def enqueue_director(self, request: LLMRequest) -> asyncio.Future:
        """Enqueue a Director request with highest priority."""
        return await self._enqueue(request, RequestPriority.DIRECTOR)
    
    async def enqueue_agent(self, request: LLMRequest) -> asyncio.Future:
        """Enqueue an Agent request with normal priority."""
        return await self._enqueue(request, RequestPriority.AGENT)
    
    async def _enqueue(self, request: LLMRequest, priority: RequestPriority) -> asyncio.Future:
        """Internal enqueue helper."""
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        seq = self._next_sequence()
        
        priority_request = PriorityRequest(
            request=request,
            priority=priority,
            sequence=seq,
            future=future,
        )
        
        await self._queue.put(priority_request)
        
        with self._lock:
            self._total_enqueued += 1
            if priority == RequestPriority.DIRECTOR:
                self._director_enqueued += 1
                self._director_pending += 1
            else:
                self._agent_enqueued += 1
                self._agent_pending += 1
        
        log.info(
            "request_enqueued",
            priority=priority.name,
            sequence=seq,
            queue_depth=self.total_queue_depth,
        )
        
        return future
    
    async def dequeue(self, timeout: Optional[float] = None) -> PriorityRequest:
        """Dequeue next request by priority, FIFO within priority."""
        if timeout is not None:
            try:
                priority_request = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                raise LLMTimeoutError("Dequeue timeout")
        else:
            priority_request = await self._queue.get()
        
        with self._lock:
            self._total_dequeued += 1
            if priority_request.priority == RequestPriority.DIRECTOR:
                self._director_pending -= 1
            else:
                self._agent_pending -= 1
        
        log.info(
            "request_dequeued",
            priority=priority_request.priority.name,
            sequence=priority_request.sequence,
        )
        
        return priority_request
    
    @property
    def director_queue_depth(self) -> int:
        """Return pending Director requests."""
        with self._lock:
            return self._director_pending
    
    @property
    def agent_queue_depth(self) -> int:
        """Return pending Agent requests."""
        with self._lock:
            return self._agent_pending
    
    @property
    def total_queue_depth(self) -> int:
        """Return total pending requests."""
        with self._lock:
            return self._director_pending + self._agent_pending
```

### Testing Patterns

**Priority Queue Test Pattern:**
```python
import asyncio
import pytest

from cyberred.llm.priority_queue import (
    LLMPriorityQueue,
    RequestPriority,
    PriorityRequest,
)
from cyberred.llm.provider import LLMRequest


class TestPriorityOrdering:
    @pytest.mark.asyncio
    async def test_director_processed_before_agent(self):
        queue = LLMPriorityQueue()
        
        # Enqueue agent first, then director
        agent_request = LLMRequest(prompt="agent task", model="test")
        director_request = LLMRequest(prompt="director task", model="test")
        
        await queue.enqueue_agent(agent_request)
        await queue.enqueue_director(director_request)
        
        # Dequeue should return director first (even though queued second)
        first = await queue.dequeue()
        assert first.priority == RequestPriority.DIRECTOR
        
        second = await queue.dequeue()
        assert second.priority == RequestPriority.AGENT
    
    @pytest.mark.asyncio
    async def test_fifo_within_same_priority(self):
        queue = LLMPriorityQueue()
        
        req1 = LLMRequest(prompt="first", model="test")
        req2 = LLMRequest(prompt="second", model="test")
        req3 = LLMRequest(prompt="third", model="test")
        
        await queue.enqueue_agent(req1)
        await queue.enqueue_agent(req2)
        await queue.enqueue_agent(req3)
        
        first = await queue.dequeue()
        assert first.request.prompt == "first"
        
        second = await queue.dequeue()
        assert second.request.prompt == "second"
        
        third = await queue.dequeue()
        assert third.request.prompt == "third"


class TestQueueMetrics:
    @pytest.mark.asyncio
    async def test_queue_depth_tracking(self):
        queue = LLMPriorityQueue()
        
        assert queue.total_queue_depth == 0
        assert queue.director_queue_depth == 0
        assert queue.agent_queue_depth == 0
        
        await queue.enqueue_director(LLMRequest(prompt="d1", model="test"))
        assert queue.director_queue_depth == 1
        assert queue.total_queue_depth == 1
        
        await queue.enqueue_agent(LLMRequest(prompt="a1", model="test"))
        assert queue.agent_queue_depth == 1
        assert queue.total_queue_depth == 2
        
        await queue.dequeue()  # Dequeues director first
        assert queue.director_queue_depth == 0
        assert queue.total_queue_depth == 1
```

### Library Versions

- Python: 3.11+
- asyncio: stdlib (use `PriorityQueue`)
- structlog: Already in project
- threading: stdlib

### Project Structure Notes

Files to create:
- `src/cyberred/llm/priority_queue.py`
- `tests/unit/llm/test_priority_queue.py`

Files to modify:
- `src/cyberred/llm/__init__.py` — Add `LLMPriorityQueue`, `RequestPriority`, `PriorityRequest` exports

### References

- [Source: docs/3-solutioning/architecture.md#line-131] 30 RPM global rate limit
- [Source: docs/3-solutioning/architecture.md#line-141] Agent Self-Throttling
- [Source: docs/3-solutioning/architecture.md#line-836] priority_queue.py location
- [Source: _bmad-output/planning-artifacts/epics-stories.md#line-1601-1621] Story 3.9 requirements
- [Source: src/cyberred/llm/rate_limiter.py] Existing async patterns
- [Source: _bmad-output/implementation-artifacts/3-8-llm-model-router.md] Previous story patterns

## Dev Agent Record

### Agent Model Used

gemini-2.0-flash

### Debug Log References

### Completion Notes List

- Achieved 100% test coverage for `src/cyberred/llm/priority_queue.py`.
- Implemented `LLMPriorityQueue`, `RequestPriority`, and `PriorityRequest`.
- Added idempotent completion handling in `complete_request` and `fail_request`.
- Fixed `LLMTimeoutError` invocation signature.
- Verified priority ordering (Director > Agent, FIFO within same priority).
- **[Code Review 2026-01-05]** Fixed deprecated `asyncio.get_event_loop()` → `asyncio.get_running_loop()`.

### File List

- `src/cyberred/llm/priority_queue.py`
- `tests/unit/llm/test_priority_queue.py`
- `src/cyberred/llm/__init__.py`

