# Story 3.7: LLM Rate Limiter

Status: done


<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **a global rate limiter for LLM requests**,
So that **the system respects API rate limits (30 RPM)**.

## Acceptance Criteria

1. **Given** Story 3.5 is complete (`LLMProvider` ABC exists in `llm/provider.py`)
2. **When** requests exceed 30 RPM
3. **Then** additional requests are queued
4. **And** token bucket algorithm controls request flow
5. **And** requests are released at sustainable rate
6. **And** queue depth is exposed for monitoring
7. **And** unit tests verify rate limiting behavior with 100% coverage

## Tasks / Subtasks

> [!IMPORTANT]
> **TDD REQUIRED:** Each task MUST follow the Red-Green-Refactor cycle. Use phase markers:
> - `[RED]` — Write failing test first (test must fail before implementation)
> - `[GREEN]` — Write minimal code to make test pass
> - `[REFACTOR]` — Clean up code while keeping tests green

### Phase 1: Core Rate Limiter

- [x] Task 1: Create RateLimiter class skeleton (AC: #2, #4) <!-- id: 0 -->
  - [x] [RED] Write failing test: `test_rate_limiter_creation`
  - [x] [GREEN] Implement `RateLimiter` in `src/cyberred/llm/rate_limiter.py`:
    - Constructor: `__init__(rpm: int = 30, burst: int = 5)`
    - Validate `rpm > 0` and `burst >= 1` (raise ValueError)
    - Store `rpm`, `burst`, `tokens`, `last_refill` as instance attributes
    - Use `threading.Lock()` for thread safety
    - Use `asyncio.Condition` for efficient async waiting
    - Implement context managers (`__enter__`, `__exit__`, `__aenter__`, `__aexit__`)
  - [x] [REFACTOR] Add docstrings and type hints
  - [x] Verification: Test confirms RateLimiter instantiation and context manager usage

- [x] Task 2: Implement token bucket refill logic (AC: #4, #5) <!-- id: 1 -->
  - [x] [RED] Write failing test: `test_rate_limiter_token_refill`
  - [x] [GREEN] Implement `_refill()` method:
    - Calculate elapsed time since last refill
    - Add tokens: `elapsed_seconds * (rpm / 60.0)`
    - Cap tokens at `burst` limit
    - Update `last_refill` timestamp
    - Notify waiting tasks via Condition if tokens added
  - [x] [REFACTOR] Use `time.monotonic()` for accurate timing
  - [x] Verification: Test confirms tokens accumulate over time

- [x] Task 3: Implement synchronous acquire() (AC: #3, #4) <!-- id: 2 -->
  - [x] [RED] Write failing test: `test_rate_limiter_acquire_blocks_when_empty`
  - [x] [GREEN] Implement `acquire(timeout: float = None) -> bool`:
    - Call `_refill()` to update token count
    - If tokens >= 1: consume token, return True
    - If timeout provided: wait using Condition (efficient wake-up)
    - If timeout expired: return False
  - [x] [REFACTOR] Ensure thread-safety with lock/condition
  - [x] Verification: Test confirms blocking behavior when tokens exhausted

- [x] Task 4: Implement asynchronous acquire_async() (AC: #3, #4) <!-- id: 3 -->
  - [x] [RED] Write failing test: `test_rate_limiter_acquire_async`
  - [x] [GREEN] Implement `async acquire_async(timeout: float = None) -> bool`:
    - Async version using `asyncio.Condition`
    - Wait efficiently for token refill signal
    - Handle timeout using `asyncio.wait_for`
  - [x] [REFACTOR] Share token logic with sync version
  - [x] Verification: Test confirms async acquire works correctly

### Phase 2: Queue Management & Monitoring

- [x] Task 5: Implement queue depth tracking (AC: #6) <!-- id: 4 -->
  - [x] [RED] Write failing test: `test_rate_limiter_queue_depth`
  - [x] [GREEN] Implement queue depth tracking:
    - Add `_waiting_count` counter (atomic int or lock-protected)
    - Increment when waiting for token
    - Decrement when token acquired or timeout
    - Property `queue_depth -> int` returns current waiting count
  - [x] [REFACTOR] Ensure thread-safe counter updates
  - [x] Verification: Test confirms accurate queue depth reporting

- [x] Task 6: Implement try_acquire() for non-blocking (AC: #4) <!-- id: 5 -->
  - [x] [RED] Write failing test: `test_rate_limiter_try_acquire_non_blocking`
  - [x] [GREEN] Implement `try_acquire() -> bool`:
    - Non-blocking version: returns immediately
    - Returns True if token consumed, False otherwise
  - [x] [REFACTOR] Simplify by calling `acquire(timeout=0)`
  - [x] Verification: Test confirms non-blocking behavior

- [x] Task 7: Implement metrics properties (AC: #6) <!-- id: 6 -->
  - [x] [RED] Write failing test: `test_rate_limiter_metrics`
  - [x] [GREEN] Implement monitoring properties:
    - `available_tokens -> float`: Current token count
    - `requests_per_minute -> int`: Configured RPM
    - `burst_limit -> int`: Configured burst
  - [x] [REFACTOR] Add thread-safe read access
  - [x] Verification: Test confirms all metrics accessible

### Phase 3: Rate-Limited Provider Wrapper

- [x] Task 8: Create RateLimitedProvider wrapper (AC: #3, #5) <!-- id: 7 -->
  - [x] [RED] Write failing test: `test_rate_limited_provider_wraps_calls`
  - [x] [GREEN] Implement `RateLimitedProvider` class:
    - Constructor: `__init__(provider: LLMProvider, rate_limiter: RateLimiter)`
    - Inherit from `LLMProvider` ABC or use composition
    - Delegate all calls to wrapped provider after acquiring token
  - [x] [REFACTOR] Use composition pattern (preferred)
  - [x] Verification: Test confirms calls pass through rate limiter

- [x] Task 9: Implement rate-limited complete() (AC: #3, #5) <!-- id: 8 -->
  - [x] [RED] Write failing test: `test_rate_limited_provider_complete`
  - [x] [GREEN] Implement `complete(request: LLMRequest) -> LLMResponse`:
    - Call `rate_limiter.acquire()` before delegating
    - Handle acquire timeout → raise `LLMRateLimitExceeded`
    - Delegate to wrapped provider
  - [x] [REFACTOR] Configure timeout from constructor
  - [x] Verification: Test confirms rate limiting applied to complete()

- [x] Task 10: Implement rate-limited complete_async() (AC: #3, #5) <!-- id: 9 -->
  - [x] [RED] Write failing test: `test_rate_limited_provider_complete_async`
  - [x] [GREEN] Implement `async complete_async(request: LLMRequest) -> LLMResponse`:
    - Call `rate_limiter.acquire_async()` before delegating
    - Handle acquire timeout → raise `LLMRateLimitExceeded`
  - [x] [REFACTOR] Share timeout logic with sync version
  - [x] Verification: Test confirms async rate limiting works

### Phase 4: Module Exports & Integration

- [x] Task 11: Export from llm package (AC: all) <!-- id: 10 -->
  - [x] [GREEN] Update `src/cyberred/llm/__init__.py`:
    - Add `RateLimiter` to imports and exports
    - Add `RateLimitedProvider` to imports and exports
  - [x] [REFACTOR] Update `__all__` list
  - [x] Verification: Test confirms imports work from package

### Phase 5: Testing & Coverage

- [x] Task 12: Unit tests with comprehensive coverage (AC: #7) <!-- id: 11 -->
  - [x] Create `tests/unit/llm/test_rate_limiter.py`:
    - Test token bucket basics (refill, consume, empty)
    - Test synchronous acquire with timeout
    - Test async acquire with timeout
    - Test queue depth tracking under concurrent load
    - Test try_acquire non-blocking behavior
    - Test RateLimitedProvider wrapper
    - Test metrics properties
  - [x] Run: `pytest tests/unit/llm/test_rate_limiter.py -v`
  - [x] Verification: All unit tests pass

- [x] Task 13: Verify 100% coverage (AC: #7) <!-- id: 12 -->
  - [x] Run: `pytest --cov=src/cyberred/llm/rate_limiter --cov-report=term-missing tests/unit/llm/`
  - [x] Verify 100% line coverage on `llm/rate_limiter.py`
  - [x] Add any missing edge case tests
  - [x] Verification: Coverage report shows 100%

## Dev Notes

### Architecture Context

Per architecture (line 834):
```
│   ├── llm/                          # LLM provider abstraction
│   │   ├── rate_limiter.py           # Token bucket, 30 RPM global cap
```

Per architecture (line 131):
> Global rate limit: **30 RPM** shared across swarm.

Per architecture (line 141):
> **Agent Self-Throttling:** When LLM queue depth exceeds threshold, agents enter WAITING state to prevent queue starvation.

### Existing LLM Infrastructure (Stories 3.5 & 3.6)

Located at `src/cyberred/llm/`:
- `provider.py` — `LLMProvider` ABC, `LLMRequest`, `LLMResponse`, `TokenUsage`, `HealthStatus`
- `nim.py` — `NIMProvider` implementation (async-ready, uses `httpx`)
- `__init__.py` — Package exports

### LLM Exceptions (use these, don't create new ones)

Located in `src/cyberred/core/exceptions.py`:
- `LLMRateLimitExceeded(LLMError)` — Rate limit hit (raise when acquire timeout)

> [!IMPORTANT]
> **Use existing `LLMRateLimitExceeded` exception from `core/exceptions.py`.**
> Do NOT define new exception classes.

### Token Bucket Algorithm Reference

```python
class TokenBucket:
    """Classic token bucket rate limiter.
    
    Tokens accumulate at rate = rpm / 60 per second.
    Burst allows N tokens above baseline for request spikes.
    """
    def __init__(self, rpm: int = 30, burst: int = 5):
        self.rpm = rpm  # 30 requests per minute
        self.burst = burst  # Allow 5 burst above steady state
        self.tokens = float(burst)  # Start with burst capacity
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()
    
    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        # Accumulate tokens: (30 RPM / 60 sec) = 0.5 tokens/sec
        self.tokens = min(self.burst, self.tokens + elapsed * (self.rpm / 60.0))
        self.last_refill = now
    
    def try_acquire(self) -> bool:
        with self._lock:
            self._refill()
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False
```

### Previous Story Learnings (Story 3.6)

From Story 3.6 implementation:
- Use `structlog` for logging: `log = structlog.get_logger()`
- Thread-safe implementation using `threading.Lock()`
- Export all public types via `__init__.py`
- Achieve 100% test coverage on all new modules
- Use `httpx` patterns for async compatibilty (though rate limiter itself doesn't use HTTP)
- All dataclasses validated in `__post_init__()` if applicable

### Code Patterns to Follow

**RateLimiter Pattern:**
```python
import threading
import time
import asyncio
from typing import Optional

import structlog

log = structlog.get_logger()

class RateLimiter:
    """Token bucket rate limiter for LLM requests.
    
    Per architecture: 30 RPM global cap shared across swarm.
    """
    
    def __init__(self, rpm: int = 30, burst: int = 5) -> None:
        if rpm <= 0:
            raise ValueError("rpm must be positive")
        if burst < 1:
            raise ValueError("burst must be at least 1")
            
        self._rpm = rpm
        self._burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        
        self._lock = threading.Lock()
        self._async_condition = asyncio.Condition()
        self._waiting_count = 0

    def __enter__(self):
        """Context manager support."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        pass

    async def __aenter__(self):
        """Async context manager support."""
        await self.acquire_async()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        pass
```

**RateLimitedProvider Pattern:**
```python
from cyberred.llm.provider import LLMProvider, LLMRequest, LLMResponse
from cyberred.core.exceptions import LLMRateLimitExceeded

class RateLimitedProvider:
    """Wrapper that applies rate limiting to any LLM provider."""
    
    def __init__(
        self, 
        provider: LLMProvider, 
        rate_limiter: "RateLimiter",
        acquire_timeout: float = 60.0
    ) -> None:
        self._provider = provider
        self._rate_limiter = rate_limiter
        self._acquire_timeout = acquire_timeout
    
    def complete(self, request: LLMRequest) -> LLMResponse:
        if not self._rate_limiter.acquire(timeout=self._acquire_timeout):
            raise LLMRateLimitExceeded("Rate limit acquire timeout")
        return self._provider.complete(request)
```

### Testing Patterns

**Rate Limiter Test Pattern:**
```python
import pytest
import time
import asyncio
from cyberred.llm.rate_limiter import RateLimiter, RateLimitedProvider

class TestRateLimiter:
    def test_creation_with_defaults(self):
        limiter = RateLimiter()
        assert limiter.requests_per_minute == 30
        assert limiter.burst_limit == 5
    
    def test_try_acquire_consumes_token(self):
        limiter = RateLimiter(rpm=30, burst=5)
        initial_tokens = limiter.available_tokens
        assert limiter.try_acquire() is True
        assert limiter.available_tokens < initial_tokens
    
    def test_try_acquire_fails_when_exhausted(self):
        limiter = RateLimiter(rpm=30, burst=1)
        assert limiter.try_acquire() is True  # Consume only token
        assert limiter.try_acquire() is False  # No tokens left
    
    @pytest.mark.asyncio
    async def test_acquire_async_waits_for_token(self):
        limiter = RateLimiter(rpm=60, burst=1)  # 1 token/sec refill
        limiter.try_acquire()  # Exhaust tokens
        start = time.monotonic()
        result = await limiter.acquire_async(timeout=2.0)
        elapsed = time.monotonic() - start
        assert result is True
        assert elapsed >= 0.9  # Should have waited ~1 second for refill
```

### Library Versions

- Python: 3.11+
- structlog: Already in project
- threading: stdlib
- asyncio: stdlib

### Project Structure Notes

Files to create:
- `src/cyberred/llm/rate_limiter.py`
- `tests/unit/llm/test_rate_limiter.py`

Files to modify:
- `src/cyberred/llm/__init__.py` — Add `RateLimiter`, `RateLimitedProvider` exports

### References

- [Source: docs/3-solutioning/architecture.md#line-834] LLM rate_limiter.py location
- [Source: docs/3-solutioning/architecture.md#line-131] 30 RPM global rate limit
- [Source: docs/3-solutioning/architecture.md#line-141] Agent self-throttling on queue depth
- [Source: _bmad-output/planning-artifacts/epics-stories.md#line-1555-1575] Story 3.7 requirements
- [Source: src/cyberred/llm/provider.py] LLMProvider ABC (Story 3.5)
- [Source: src/cyberred/llm/nim.py] NIMProvider patterns (Story 3.6)
- [Source: _bmad-output/implementation-artifacts/3-6-nvidia-nim-provider.md] Previous story learnings

## Dev Agent Record

### Agent Model Used

Gemini 2.5 Pro (Code Review Agent)

### Debug Log References

N/A

### Completion Notes List

- Code review identified thread-safety issue in `available_tokens` property — fixed by acquiring lock before `_refill()`
- Added 4 additional tests to achieve 100% coverage (negative rpm, async no-timeout, zero elapsed time, mocked time)
- 20 unit tests now pass with 100% line and branch coverage

### File List

- `src/cyberred/llm/rate_limiter.py` (created) — RateLimiter and RateLimitedProvider classes
- `tests/unit/llm/test_rate_limiter.py` (created) — 20 unit tests with 100% coverage
- `src/cyberred/llm/__init__.py` (modified) — Added RateLimiter, RateLimitedProvider exports
