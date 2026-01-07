# Story 3.5: LLM Provider Protocol

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **an abstract LLM provider interface**,
so that **different LLM backends can be swapped without code changes**.

## Acceptance Criteria

1. **Given** Epic 1.4 protocols are complete (LLMProviderProtocol exists in `protocols/provider.py`)
2. **When** I import from `llm.provider`
3. **Then** `LLMProvider` ABC defines: `complete()`, `complete_async()`, `health_check()`
4. **And** `LLMRequest` dataclass defines: prompt, model, temperature, max_tokens
5. **And** `LLMResponse` dataclass defines: content, model, usage, latency_ms
6. **And** unit tests verify protocol compliance

## Tasks / Subtasks

> [!IMPORTANT]
> **TDD REQUIRED:** Each task MUST follow the Red-Green-Refactor cycle. Use phase markers:
> - `[RED]` — Write failing test first (test must fail before implementation)
> - `[GREEN]` — Write minimal code to make test pass
> - `[REFACTOR]` — Clean up code while keeping tests green

> [!WARNING]
> **NO MOCKS POLICY:** Tests must use real components via testcontainers. Mocks are only acceptable for:
> - External APIs with rate limits (e.g., LLM providers)
> - System boundaries explicitly marked in architecture
> - Never mock internal modules or database operations

### Phase 1: Data Models

- [x] Task 1: Create LLMRequest dataclass (AC: #4) <!-- id: 0 -->
  - [x] [RED] Write failing test: `test_llm_request_has_required_fields`
  - [x] [GREEN] Implement `LLMRequest` in `src/cyberred/llm/provider.py`:
    - `prompt: str` — The input prompt
    - `model: str` — Model identifier (e.g., "nvidia/nemotron-70b")
    - `temperature: float = 0.7` — Sampling temperature (default 0.7)
    - `max_tokens: int = 1024` — Max response tokens (default 1024)
    - Add optional fields: `system_prompt: Optional[str]`, `stop_sequences: Optional[list[str]]`
  - [x] [REFACTOR] Add field validation (temperature 0.0-1.0, max_tokens > 0)
  - [x] Verification: Test confirms all required and optional fields

- [x] Task 2: Create LLMResponse dataclass (AC: #5) <!-- id: 1 -->
  - [x] [RED] Write failing test: `test_llm_response_has_required_fields`
  - [x] [GREEN] Implement `LLMResponse` in `src/cyberred/llm/provider.py`:
    - `content: str` — The generated text response
    - `model: str` — Model that produced the response
    - `usage: TokenUsage` — Token usage breakdown
    - `latency_ms: int` — Request latency in milliseconds
    - Add optional fields: `finish_reason: Optional[str]`, `request_id: Optional[str]`
  - [x] [REFACTOR] Add helper properties (e.g., `total_tokens`)
  - [x] Verification: Test confirms all fields and helpers work

- [x] Task 3: Create TokenUsage dataclass (AC: #5) <!-- id: 2 -->
  - [x] [RED] Write failing test: `test_token_usage_tracks_costs`
  - [x] [GREEN] Implement `TokenUsage` dataclass:
    - `prompt_tokens: int`
    - `completion_tokens: int`
    - `total_tokens: int` (computed or stored)
  - [x] [REFACTOR] Ensure immutability with frozen=True
  - [x] Verification: Test confirms token computation

### Phase 2: LLMProvider Abstract Base Class

- [x] Task 4: Create LLMProvider ABC with complete() (AC: #3) <!-- id: 3 -->
  - [x] [RED] Write failing test: `test_llm_provider_complete_is_abstract`
  - [x] [GREEN] Implement `LLMProvider` ABC in `src/cyberred/llm/provider.py`:
    - Inherit from `abc.ABC`
    - Define `complete(request: LLMRequest) -> LLMResponse` as abstract method
    - Add docstring explaining synchronous completion semantics
  - [x] [REFACTOR] Add type hints and structured logging placeholder
  - [x] Verification: Test confirms cannot instantiate ABC

- [x] Task 5: Add complete_async() method (AC: #3) <!-- id: 4 -->
  - [x] [RED] Write failing test: `test_llm_provider_complete_async_is_abstract`
  - [x] [GREEN] Add `async complete_async(request: LLMRequest) -> LLMResponse` abstract method
  - [x] [REFACTOR] Document when to use sync vs async
  - [x] Verification: Test confirms async method is abstract

- [x] Task 6: Add health_check() method (AC: #3) <!-- id: 5 -->
  - [x] [RED] Write failing test: `test_llm_provider_health_check_is_abstract`
  - [x] [GREEN] Add `async health_check() -> HealthStatus` abstract method:
    - Return HealthStatus dataclass with: `healthy: bool`, `latency_ms: Optional[int]`, `error: Optional[str]`
  - [x] [REFACTOR] Add HealthStatus dataclass to module
  - [x] Verification: Test confirms health_check is abstract

### Phase 3: Protocol Compliance

- [x] Task 7: Verify LLMProvider satisfies LLMProviderProtocol (AC: #6) <!-- id: 6 -->
  - [x] [RED] Write failing test: `test_llm_provider_satisfies_protocol`
  - [x] [GREEN] Ensure `LLMProvider` ABC explicitly implements protocol methods as wrappers:
    - `async def generate(self, prompt: str, **kwargs) -> str`:
      - Must construct `LLMRequest` from args
      - Call `await self.complete_async(request)`
      - Return `response.content`
    - `async def generate_structured(self, prompt: str, schema: Dict, **kwargs) -> Dict`:
      - Must raise `NotImplementedError` or strictly implement schema validation (defer to next story if complex)
    - `is_available()` → add abstract method matching protocol signature
    - `get_model_name()` / `get_rate_limit()` / `get_token_usage()` matching protocol
  - [x] [REFACTOR] Ensure docstrings verify protocol satisfaction
  - [x] Verification: Test confirms `issubclass(ConcreteProvider, LLMProviderProtocol)` and `generate()` works via wrapper

- [x] Task 8: Create MockLLMProvider for testing (AC: #6) <!-- id: 7 -->
  - [x] [RED] Write failing test: `test_mock_provider_implements_protocol`
  - [x] [GREEN] Implement `MockLLMProvider` in `src/cyberred/llm/provider.py`:
    - Concrete implementation for unit testing
    - Returns configurable responses
    - Tracks call count and usage
  - [x] [REFACTOR] Add factory methods for common test scenarios
  - [x] Verification: Test confirms mock fully implements interface

### Phase 4: Error Handling & Edge Cases

- [x] Task 9: Define LLM-specific exceptions (AC: #3) <!-- id: 8 -->
  - [x] [RED] Write failing test: `test_llm_exceptions_in_hierarchy`
  - [x] [GREEN] Add exceptions to `src/cyberred/core/exceptions.py`:
    - `LLMError(CyberRedError)` — Base LLM exception
    - `LLMProviderUnavailable(LLMError)` — Provider unreachable (NFR29)
    - `LLMRateLimitExceeded(LLMError)` — Rate limit hit (ERR2)
    - `LLMTimeoutError(LLMError)` — Request timeout (ERR2)
    - `LLMResponseError(LLMError)` — Invalid response format
  - [x] [REFACTOR] Add error codes for monitoring
  - [x] Verification: Test confirms exception hierarchy

- [x] Task 10: Validate LLMRequest fields (AC: #4) <!-- id: 9 -->
  - [x] [RED] Write failing test: `test_llm_request_validation`
  - [x] [GREEN] Add validation in `LLMRequest.__post_init__()`:
    - `temperature` must be 0.0-2.0
    - `max_tokens` must be > 0 and <= 32768
    - `prompt` must be non-empty
  - [x] [REFACTOR] Use pydantic-style validation errors
  - [x] Verification: Test confirms invalid inputs raise ValueError

### Phase 5: Module Exports & Integration

- [x] Task 11: Create llm package (AC: #2, #3) <!-- id: 10 -->
  - [x] [GREEN] Create `src/cyberred/llm/__init__.py`:
    - Export: `LLMProvider`, `LLMRequest`, `LLMResponse`, `TokenUsage`, `HealthStatus`
    - Export: `MockLLMProvider` for testing
  - [x] [REFACTOR] Add `__all__` for explicit public API
  - [x] Verification: Test confirms imports work correctly

- [x] Task 12: Export LLM exceptions from core (AC: #6) <!-- id: 11 -->
  - [x] [GREEN] Update `src/cyberred/core/__init__.py`:
    - Export new LLM exceptions
  - [x] [REFACTOR] Ensure backwards compatibility
  - [x] Verification: Test confirms exception imports

### Phase 6: Testing & Coverage

- [x] Task 13: Comprehensive unit tests (AC: #6) <!-- id: 12 -->
  - [x] Create `tests/unit/llm/test_provider.py`:
    - Test all dataclass fields and defaults
    - Test ABC cannot be instantiated
    - Test MockLLMProvider functionality
    - Test validation logic
  - [x] Run: `pytest tests/unit/llm/test_provider.py -v`
  - [x] Verification: All tests pass

- [x] Task 14: Verify 100% coverage (AC: all) <!-- id: 13 -->
  - [x] Run: `pytest --cov=src/cyberred/llm/provider --cov-report=term-missing tests/unit/llm/`
  - [x] Verify 100% line coverage on `llm/provider.py`
  - [x] Add any missing edge case tests
  - [x] Verification: Coverage report shows 100%

## Dev Notes

### Architecture Context

Per architecture (line 830):
- `src/cyberred/llm/provider.py` — LLMProvider ABC

Per architecture (line 990):
- "LLM ↔ Ensemble: All LLM calls through `LLMProvider` protocol"

Per architecture (lines 828-836):
```
├── llm/                          # LLM provider abstraction
│   ├── __init__.py
│   ├── provider.py               # LLMProvider ABC
│   ├── nim.py                    # NVIDIA NIM implementation
│   ├── ensemble.py               # 3-model Director synthesis
│   ├── gateway.py                # Singleton LLM gateway
│   ├── rate_limiter.py           # Token bucket, 30 RPM global cap
│   ├── router.py                 # Task complexity → model selection
│   └── priority_queue.py         # Director-priority request queue
```

### Existing LLMProviderProtocol

A `LLMProviderProtocol` already exists at `src/cyberred/protocols/provider.py` (lines 29-131):
- Uses `typing.Protocol` for structural subtyping
- Defines: `generate()`, `generate_structured()`, `get_model_name()`, `get_rate_limit()`, `get_token_usage()`, `is_available()`
- The new `LLMProvider` ABC should satisfy this protocol

> [!IMPORTANT]
> **The LLMProvider ABC must be compatible with LLMProviderProtocol.**
> Either implement all required methods or provide adapter methods.

### Critical Requirements

> [!WARNING]
> **NFR29: Graceful Degradation**
> When LLM providers are unavailable, providers must return `is_available() = False`.
> The `health_check()` method enables circuit-breaker patterns.

> [!WARNING]
> **ERR2: LLM Provider Timeout**
> Retry 3x with exponential backoff, use available models only.
> Define `LLMTimeoutError` for timeout handling.

### Design Decisions

**Sync vs Async:**
- `complete()` — Synchronous, for simple single-threaded use
- `complete_async()` — Asynchronous, for agent swarm concurrency

**Dataclass Choices:**
- Use `@dataclass(frozen=True)` for immutability where appropriate
- Use `Optional` fields with sensible defaults

**Protocol Compatibility:**
- The `LLMProvider` ABC maps to `LLMProviderProtocol` as follows:
  - `complete_async()` implements `generate()` semantics
  - Add `generate_structured()` for schema-validated output
  - Add property `model_name` and method `get_model_name()`
  - Add `get_rate_limit()` returning 30 RPM default
  - Add `get_token_usage()` for observability
  - Add `is_available()` for circuit breaker

### Previous Story Learnings

From Story 3.4 implementation:
- Follow TDD strictly with `[RED]`/`[GREEN]`/`[REFACTOR]` markers
- Use structlog for consistent logging patterns
- Export all public types via `__init__.py`
- Achieve 100% test coverage on all new modules

### Code Patterns to Follow

**Dataclass Pattern:**
```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass(frozen=True)
class LLMRequest:
    """Request for LLM completion."""
    prompt: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 1024
    system_prompt: Optional[str] = None
    stop_sequences: Optional[list[str]] = field(default=None)
    
    def __post_init__(self) -> None:
        if not self.prompt:
            raise ValueError("prompt cannot be empty")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be 0.0-2.0")
```

**ABC Pattern:**
```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def complete_async(self, request: LLMRequest) -> LLMResponse:
        """Generate completion asynchronously."""
        ...
    
    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate completion synchronously."""
        ...
    
    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Check provider health for circuit breaker."""
        ...
```

### Library Versions

- Python: 3.11+
- No external dependencies for this story (stdlib only)

### Project Structure Notes

Files to create:
- `src/cyberred/llm/__init__.py`
- `src/cyberred/llm/provider.py`
- `tests/unit/llm/__init__.py`
- `tests/unit/llm/test_provider.py`

Files to modify:
- `src/cyberred/core/exceptions.py` — Add LLM exceptions
- `src/cyberred/core/__init__.py` — Export new exceptions

### References

- [Source: docs/3-solutioning/architecture.md#line-828-836] LLM module structure
- [Source: docs/3-solutioning/architecture.md#line-990] LLM ↔ Ensemble boundary
- [Source: src/cyberred/protocols/provider.py#line-29-131] Existing LLMProviderProtocol
- [Source: _bmad-output/planning-artifacts/epics-stories.md#line-1510-1530] Story 3.5 requirements
- [Source: _bmad-output/implementation-artifacts/3-4-event-bus-streams-for-audit.md] Previous story patterns

## Dev Agent Record

### Agent Model Used

Gemini 2.5 Pro

### Debug Log References

N/A

### Completion Notes List

- Implemented `LLMRequest`, `LLMResponse`, `TokenUsage`, `HealthStatus` dataclasses
- Implemented `LLMProvider` ABC with `complete()`, `complete_async()`, `health_check()`, `generate()`, `generate_structured()`
- Implemented `MockLLMProvider` for testing with configurable responses and call tracking
- Added LLM exceptions: `LLMError`, `LLMProviderUnavailable`, `LLMRateLimitExceeded`, `LLMTimeoutError`, `LLMResponseError`
- Protocol compliance: `MockLLMProvider` satisfies `LLMProviderProtocol` via `isinstance` check
- 40 unit tests covering all functionality
- **100% test coverage** on `llm/provider.py` and `llm/__init__.py`
- Addressed code review feedback:
  - Added thread safety to `MockLLMProvider`
  - Added `top_p` and `frequency_penalty` to `LLMRequest`
  - Refactored test imports for cleaner style

### File List

**Created:**
- `src/cyberred/llm/__init__.py`
- `src/cyberred/llm/provider.py`
- `tests/unit/llm/__init__.py`
- `tests/unit/llm/test_provider.py`

**Modified:**
- `src/cyberred/core/exceptions.py` — Added LLM exceptions
- `src/cyberred/core/__init__.py` — Exported LLM exceptions
