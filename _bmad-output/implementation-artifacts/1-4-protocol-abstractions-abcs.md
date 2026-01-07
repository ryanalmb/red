# Story 1.4: Protocol Abstractions (ABCs)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **abstract base classes for Agent, Storage, and LLMProvider**,
So that **components can be swapped via dependency injection**.

## Acceptance Criteria

1. **Given** Story 1.1 is complete (exception hierarchy exists)
2. **When** I import from `protocols/`
3. **Then** `AgentProtocol` ABC defines agent interface methods
4. **And** `StorageProtocol` ABC defines storage interface methods
5. **And** `LLMProviderProtocol` ABC defines LLM provider interface
6. **And** all protocols use `typing.Protocol` or `abc.ABC`
7. **And** unit tests verify protocol compliance checking
8. **And** protocols are exported from `src/cyberred/protocols/__init__.py`

## Tasks / Subtasks

- [x] Create Protocols Directory Structure <!-- id: 0 -->
  - [x] Create `src/cyberred/protocols/` directory with `__init__.py`
  - [x] Verify directory is a proper Python package

- [x] Implement AgentProtocol (AC: #3, #6) <!-- id: 1 -->
  - [x] Create `src/cyberred/protocols/agent.py`
  - [x] Define `AgentProtocol` using `typing.Protocol` (runtime checkable)
  - [x] Define essential agent methods:
    - [x] `async def execute(self, task: str) -> AgentAction` — Execute a task
    - [x] `async def reason(self, context: List[str]) -> str` — Generate reasoning
    - [x] `def get_id(self) -> str` — Return agent identifier
    - [x] `def get_status(self) -> str` — Return agent status
    - [x] `def get_decision_context(self) -> List[str]` — Return stigmergic influences (NFR37)
    - [x] `async def shutdown(self) -> None` — Graceful cleanup of resources
  - [x] Add docstrings describing each method's contract
  - [x] Import `AgentAction` from `core.models`

- [x] Implement StorageProtocol (AC: #4, #6) <!-- id: 2 -->
  - [x] Create `src/cyberred/protocols/storage.py`
  - [x] Define `StorageProtocol` using `typing.Protocol` (runtime checkable)
  - [x] Define essential storage methods:
    - [x] `async def save(self, key: str, data: dict) -> bool` — Persist data
    - [x] `async def load(self, key: str) -> Optional[dict]` — Retrieve data
    - [x] `async def delete(self, key: str) -> bool` — Remove data
    - [x] `async def exists(self, key: str) -> bool` — Check existence
    - [x] `async def list_keys(self, prefix: str) -> List[str]` — List keys with prefix
  - [x] Add docstrings describing each method's contract

- [x] Implement LLMProviderProtocol (AC: #5, #6) <!-- id: 3 -->
  - [x] Create `src/cyberred/protocols/provider.py`
  - [x] Define `LLMProviderProtocol` using `typing.Protocol` (runtime checkable)
  - [x] Define essential LLM provider methods:
    - [x] `async def generate(self, prompt: str, **kwargs) -> str` — Generate completion
    - [x] `async def generate_structured(self, prompt: str, schema: dict, **kwargs) -> dict` — Structured output
    - [x] `def get_model_name(self) -> str` — Return model identifier
    - [x] `def get_rate_limit(self) -> int` — Return rate limit (RPM)
    - [x] `def get_token_usage(self) -> dict` — Return usage metrics (prompts/completion tokens)
    - [x] `def is_available(self) -> bool` — Check provider availability
  - [x] Add docstrings describing each method's contract
  - [x] Document NFR29 graceful degradation requirement

- [x] Export Protocols (AC: #8) <!-- id: 4 -->
  - [x] Update `src/cyberred/protocols/__init__.py` to export:
    - [x] `AgentProtocol`
    - [x] `StorageProtocol`
    - [x] `LLMProviderProtocol`
  - [x] Verify imports work: `from cyberred.protocols import AgentProtocol`

- [x] Create Unit Tests (AC: #7) <!-- id: 5 -->
  - [x] Create `tests/unit/protocols/` directory
  - [x] Create `tests/unit/protocols/test_agent.py`
    - [x] Test that compliant class passes `isinstance()` check
    - [x] Test that non-compliant class fails check
    - [x] Test method signatures match expected types
    - [x] Test `shutdown()` method presence and signature
  - [x] Create `tests/unit/protocols/test_storage.py`
    - [x] Test protocol compliance checking
    - [x] Test async method signatures
  - [x] Create `tests/unit/protocols/test_provider.py`
    - [x] Test protocol compliance checking
    - [x] Test async method signatures
  - [x] Use `@runtime_checkable` decorator for isinstance() support

- [x] Update Core Package Exports <!-- id: 6 -->
  - [x] Verify `src/cyberred/__init__.py` can import from protocols (no circular imports)
  - [x] Add `protocols` to documented public API

## Dev Notes

### Architecture Context

This story implements **protocol abstractions** per architecture (lines 788-792) using `typing.Protocol` for structural subtyping. These ABCs enable dependency injection and allow swapping implementations without modifying client code.

**Why `typing.Protocol` over `abc.ABC`:**
- Structural ("duck") typing instead of nominal inheritance
- `@runtime_checkable` enables `isinstance()` checks
- Better IDE/mypy support for interface contracts
- No need for explicit inheritance in implementations

### Protocol Location

Per architecture section 5.4:
```
src/cyberred/protocols/
├── __init__.py           # Re-exports all protocols
├── agent.py             # AgentProtocol
├── storage.py           # StorageProtocol
└── provider.py          # LLMProviderProtocol
```

### Implementation Pattern

```python
from typing import Protocol, runtime_checkable, List, Optional

@runtime_checkable
class AgentProtocol(Protocol):
    """Protocol for all Cyber-Red agents.
    
    All agent implementations must satisfy this interface.
    Use isinstance(agent, AgentProtocol) for runtime validation.
    """
    
    async def execute(self, task: str) -> AgentAction:
        """Execute a task and return the resulting action."""
        ...
    
    def get_id(self) -> str:
        """Return unique agent identifier."""
        ...

    async def shutdown(self) -> None:
        """Cleanup resources and shut down agent gracefully."""
        ...
```

### Architectural Boundaries (Critical)

Per architecture lines 982-994:
- **Core ↔ Everything**: Core has no dependencies on agents, tools, tui, api, c2, daemon
- **LLM ↔ Ensemble**: All LLM calls through `LLMProvider` protocol
- **Protocols depend only on**: `core.models` (for `AgentAction`, etc.)

### Previous Story Patterns (1-3-yaml-configuration-loader)

From reviewing the completed story:
- Use `from __future__ import annotations` for forward references
- Create test directory mirroring source: `tests/unit/protocols/`
- Export via `__init__.py` with explicit `__all__`
- 100% test coverage required (NFR19)

### Key References

- [Architecture: Protocol Directory](file:///root/red/docs/3-solutioning/architecture.md#L788-792)
- [Architecture: Boundaries](file:///root/red/docs/3-solutioning/architecture.md#L978-994)
- [Core Models](file:///root/red/src/cyberred/core/models.py) — `AgentAction` definition
- [Core Exceptions](file:///root/red/src/cyberred/core/exceptions.py) — `CyberRedError` hierarchy

### Naming Conventions

Per architecture section 5.1:
- Classes: PascalCase (`AgentProtocol`, `StorageProtocol`)
- Functions/Methods: snake_case (`get_id()`, `generate()`)
- Constants: UPPER_SNAKE_CASE
- Files: lowercase_underscore (`agent.py`, `storage.py`)

### Testing Strategy

```python
# Example test pattern for runtime_checkable protocols
import pytest
from cyberred.protocols import AgentProtocol

class CompliantAgent:
    """A minimal compliant implementation for testing."""
    
    async def execute(self, task: str) -> AgentAction:
        return AgentAction(...)
    
    def get_id(self) -> str:
        return "test-agent"
    
    # ... other methods

def test_compliant_agent_passes_isinstance():
    agent = CompliantAgent()
    assert isinstance(agent, AgentProtocol)

def test_non_compliant_fails_isinstance():
    class NonCompliant:
        pass
    
    obj = NonCompliant()
    assert not isinstance(obj, AgentProtocol)
```

### Dependencies

No new dependencies required. Uses Python stdlib only:
- `typing.Protocol` (Python 3.8+)
- `typing.runtime_checkable`

### Project Structure Notes

- Location: `src/cyberred/protocols/`
- Test location: `tests/unit/protocols/`
- Exports: `AgentProtocol`, `StorageProtocol`, `LLMProviderProtocol`

### LLM Provider Requirements (NFR29)

The `LLMProviderProtocol` must support graceful degradation:
- `is_available()` method allows circuit-breaker patterns
- Rate limit exposure enables client-side throttling
- Architecture requires 30 RPM global cap shared across swarm

### Related Future Stories

- Story 1.5+ in Epic 1 will use these protocols
- Story 3.6 (NVIDIA NIM Provider) implements `LLMProviderProtocol`
- Epic 7 agents implement `AgentProtocol`

## Dev Agent Record

### Agent Model Used

Gemini 2.5 Pro

### Debug Log References

### Completion Notes List

- ✅ Created `src/cyberred/protocols/` package with `__init__.py` exporting all protocols
- ✅ Implemented `AgentProtocol` with 6 methods: execute, reason, get_id, get_status, get_decision_context, shutdown
- ✅ Implemented `StorageProtocol` with 5 async methods: save, load, delete, exists, list_keys
- ✅ Implemented `LLMProviderProtocol` with 6 methods including get_token_usage for observability
- ✅ All protocols use `@runtime_checkable` decorator for isinstance() support
- ✅ Created comprehensive test suite with 41 tests covering compliance checking and async methods
- ✅ All 41 tests pass
- ✅ Verified imports work with no circular dependencies

### File List

- `src/cyberred/protocols/__init__.py` (NEW)
- `src/cyberred/protocols/agent.py` (NEW)
- `src/cyberred/protocols/storage.py` (NEW)
- `src/cyberred/protocols/provider.py` (NEW)
- `tests/unit/protocols/__init__.py` (NEW)
- `tests/unit/protocols/test_agent.py` (NEW)
- `tests/unit/protocols/test_storage.py` (NEW)
- `tests/unit/protocols/test_provider.py` (NEW)

## Change Log

| Date | Change |
|------|--------|
| 2026-01-01 | Story created with comprehensive context from architecture.md, epics-stories.md, and previous story patterns. |
| 2026-01-01 | Implementation complete: All protocols created with @runtime_checkable, 41 tests passing, ready for review. |
| 2026-01-01 | Code Review: Fixed critical export issue in `src/cyberred/__init__.py`, improved docstrings for `shutdown` (exceptions) and `list_keys` (performance). |
