# Story 1.2: Core Data Models

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **standardized dataclasses for Finding, AgentAction, and ToolResult**,
So that **all components use consistent data structures**.

## Acceptance Criteria

1. **Given** Story 1.1 is complete
2. **When** I import from `core.models`
3. **Then** `Finding` dataclass has 10 required fields (id, type, severity, target, evidence, agent_id, timestamp, tool, topic, signature)
4. **And** `AgentAction` dataclass has 7 fields (id, agent_id, action_type, target, timestamp, decision_context, result_finding_id)
5. **And** `ToolResult` dataclass has 5 fields (success, stdout, stderr, exit_code, duration_ms)
6. **And** all models are JSON-serializable
7. **And** unit tests validate serialization/deserialization

## Tasks / Subtasks

- [x] Create Data Models Module <!-- id: 0 -->
  - [x] Create `src/cyberred/core/models.py` (AC: #2)
  - [x] Implement `Finding` dataclass with 10 required fields (AC: #3)
    - [x] `id: str` - UUID format
    - [x] `type: str` - Finding type ("sqli", "xss", "open_port", etc.)
    - [x] `severity: str` - One of "critical", "high", "medium", "low", "info" (Validate in `__post_init__`)
    - [x] `target: str` - IP address or URL
    - [x] `evidence: str` - Raw tool output or screenshot path
    - [x] `agent_id: str` - Originating agent identifier
    - [x] `timestamp: str` - ISO 8601 format
    - [x] `tool: str` - Tool that produced finding ("nmap", "sqlmap", etc.)
    - [x] `topic: str` - Redis channel for routing (e.g., "findings:a1b2c3:sqli")
    - [x] `signature: str` - HMAC-SHA256 for message integrity
  - [x] Implement `AgentAction` dataclass with 7 required fields (AC: #4)
    - [x] `id: str` - UUID format
    - [x] `agent_id: str` - Acting agent identifier
    - [x] `action_type: str` - "scan", "exploit", "enumerate", etc.
    - [x] `target: str` - Target of action
    - [x] `timestamp: str` - ISO 8601 format
    - [x] `decision_context: List[str]` - IDs of stigmergic signals that influenced action (CRITICAL for NFR37)
    - [x] `result_finding_id: Optional[str]` - ID of resulting finding, if any
  - [x] Implement `ToolResult` dataclass with 5 required fields (AC: #5)
    - [x] `success: bool` - Whether tool execution succeeded
    - [x] `stdout: str` - Standard output
    - [x] `stderr: str` - Standard error
    - [x] `exit_code: int` - Process exit code
    - [x] `duration_ms: int` - Execution duration in milliseconds
- [x] Export Models <!-- id: 1 -->
  - [x] Update `src/cyberred/core/__init__.py` (AC: #2)
  - [x] Export `Finding`, `AgentAction`, `ToolResult` to package level
- [x] Implement JSON Serialization <!-- id: 2 -->
  - [x] Add `to_json()` method to all dataclasses (AC: #6)
  - [x] Add `from_json()` classmethod to all dataclasses (AC: #6)
  - [x] Ensure timestamp fields serialize as ISO 8601 strings
  - [x] Ensure `decision_context` serializes as JSON array
  - [x] Handle `Optional` fields correctly (null in JSON)
- [x] Create Unit Tests <!-- id: 2 -->
  - [x] Create `tests/unit/core/test_models.py` (AC: #7)
  - [x] Test `Finding` instantiation with all fields
  - [x] Test `AgentAction` instantiation with all fields
  - [x] Test `ToolResult` instantiation with all fields
  - [x] Test `to_json()` produces valid JSON for all models
  - [x] Test `from_json()` round-trip for all models
  - [x] Test JSON output matches expected format from architecture
  - [x] Test edge cases: empty `decision_context`, None `result_finding_id`
  - [x] Test that severity validation accepts only valid values
  - [x] Test that severity validation raises ValueError for invalid values
- [x] Verify Coverage <!-- id: 3 -->
  - [x] Run `pytest --cov=src/cyberred/core/models` to verify 100% coverage
  - [x] Verify no coverage regression on existing code

## Dev Notes

### Architecture Context

This story implements the **core data models** defined in the architecture document (lines 608-650):

```python
# Finding/Message Format (from architecture.md)
@dataclass
class Finding:
    id: str           # UUID
    type: str         # "sqli", "xss", "open_port"
    severity: str     # "critical", "high", "medium", "low", "info"
    target: str       # IP or URL
    evidence: str     # Raw tool output or screenshot path
    agent_id: str     # Originating agent
    timestamp: str    # ISO 8601
    tool: str         # "nmap", "sqlmap", etc.
    topic: str        # Redis channel for routing
    signature: str    # HMAC-SHA256 (mitigates Agent-in-the-Middle attacks)

@dataclass
class AgentAction:
    id: str              # UUID
    agent_id: str        # Acting agent
    action_type: str     # "scan", "exploit", "enumerate", etc.
    target: str          # Target of action
    timestamp: str       # ISO 8601
    decision_context: List[str]  # IDs of stigmergic signals (CRITICAL for emergence)
    result_finding_id: Optional[str]  # ID of resulting finding, if any

@dataclass  
class ToolResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
```

### Critical NFR Requirements

**NFR37 (Emergence Traceability):** The `decision_context` field in `AgentAction` is CRITICAL. Every agent action must log which stigmergic signals influenced the decision. This enables emergence validation (NFR35-37).

Per architecture (lines 633-634):
> `decision_context: List[str]  # IDs of stigmergic signals that influenced this action (CRITICAL for emergence validation)`

**HARD GATE:** 100% of agent actions must include `decision_context` linking to influencing signals.

### JSON Format (Architecture Specification)

Per architecture (lines 637-650), the JSON output MUST match this format:

```json
{
    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "type": "sqli",
    "severity": "critical",
    "target": "192.168.1.100",
    "evidence": "Parameter 'id' is vulnerable...",
    "agent_id": "ghost-42",
    "timestamp": "2025-12-27T23:30:00Z",
    "tool": "sqlmap",
    "topic": "findings:a1b2c3:sqli",
    "signature": "a3f2b1c4d5e6f7..."
}
```

### Error Handling Pattern

Per architecture (lines 653-658, 671-679):
- `ToolResult` is for **expected/tool** errors (success=True/False)
- `Finding` captures vulnerability discoveries
- Exceptions (from Story 1.1) are for **critical/system** errors

This separation is intentional:
> **Expected/Tool** → Result objects (`ToolResult(success=True, stdout=...)`)

### Severity Values

Per architecture, `severity` must be one of:
- `"critical"` - Immediate impact, exploitable
- `"high"` - Serious vulnerability
- `"medium"` - Moderate risk
- `"low"` - Minor issue
- `"info"` - Informational finding

**Requirement:** Validation MUST reject invalid severity values in `__post_init__`.

### Implementation Requirements

1. **Use Python dataclasses** with `@dataclass` decorator
2. **Type hints** for all fields (enables mypy checking)
3. **JSON serialization** via custom `to_json()`/`from_json()` methods
4. **Optional fields** use `Optional[T]` type hint with default `None`
5. **List fields** (`decision_context`) default to empty list with `field(default_factory=list)`

### Previous Story Context

Story 1-1 (Exception Hierarchy) created:
- `src/cyberred/core/exceptions.py` - Exception classes
- `tests/unit/core/test_exceptions.py` - 36 tests

Models should integrate with exceptions:
- `ToolResult` may be returned instead of raising exceptions for tool failures
- `Finding` objects are produced by successful tool executions

### Naming Conventions

Per architecture (lines 559-569):
- Classes: PascalCase (`Finding`, `AgentAction`, `ToolResult`)
- Files: lowercase_underscore.py (`models.py`)
- Fields: snake_case (`agent_id`, `exit_code`, `decision_context`)

### Project Structure Notes

- Location: `src/cyberred/core/models.py` (per architecture line 781)
- Test location: `tests/unit/core/test_models.py`
- `__init__.py` exports: `Finding`, `AgentAction`, `ToolResult`
- Dependencies: Only Python standard library (`dataclasses`, `typing`, `json`, `uuid`)

### Git Context (Recent Commits)

```
873b553 Refactor: Move to src/cyberred and enforce 100% coverage gates
361450f feat: Documentation and agent configurations
```

The project uses `src/cyberred/` layout with 100% coverage enforcement.

### References

- [Source: docs/3-solutioning/architecture.md#Finding/Message Format, lines 608-650]
- [Source: docs/3-solutioning/architecture.md#Error Handling Patterns, lines 653-681]
- [Source: docs/3-solutioning/architecture.md#Project Structure, lines 571-606]
- [Source: docs/3-solutioning/epics-stories.md#Story 1.2: Core Data Models, lines 866-886]

## Dev Agent Record

### Agent Model Used

Gemini (Google DeepMind)

### Debug Log References

- `pytest tests/unit/core/test_models.py -v`: 24 passed in 0.58s
- `pytest tests/unit tests/integration -v`: 78 passed in 2.49s (no regressions)
- `models.py` coverage: 100%

### Completion Notes List

- Created `src/cyberred/core/models.py` with complete data model implementation:
  - `Finding` dataclass with 10 required fields and severity validation in `__post_init__`
  - `AgentAction` dataclass with 7 fields including `decision_context: List[str]` (CRITICAL for NFR37)
  - `ToolResult` dataclass with 5 fields for tool execution results
- All dataclasses have `to_json()` method and `from_json()` classmethod for JSON serialization
- `from_json()` accepts both JSON strings and dicts for flexibility
- Severity validation enforces only valid values: critical, high, medium, low, info
- Updated `src/cyberred/core/__init__.py` to export all models at package level
- Created comprehensive test suite with 24 tests covering:
  - All field instantiation for each dataclass
  - JSON serialization and round-trip deserialization
  - Severity validation (valid and invalid values)
  - Edge cases (empty lists, None values)
  - Architecture specification compliance

### File List

- `src/cyberred/core/models.py` (NEW)
- `src/cyberred/core/__init__.py` (MODIFIED)
- `tests/unit/core/test_models.py` (NEW)

## Change Log

| Date | Change |
|------|--------|
| 2025-12-31 | Story created with comprehensive context from architecture.md and epics-stories.md |
| 2025-12-31 | Validation improvements applied: strict severity validation and module exports |
| 2025-12-31 | Implementation complete: 3 dataclasses with JSON serialization, 24 tests pass, 100% coverage |
| 2025-12-31 | Code Review: Fixed strict validation issues (UUID, ISO8601, Target) |

## Senior Developer Review (AI)

- **Date:** 2025-12-31
- **Reviewer:** Code Review Workflow
- **Status:** Approved
- **Findings:** 3 High (Validation gaps) - FIXED
- **Fixes Applied:** Implemented strict validation for UUIDs, ISO 8601 timestamps, and targets.
