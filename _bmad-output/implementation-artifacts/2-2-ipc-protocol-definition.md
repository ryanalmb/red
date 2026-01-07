# Story 2.2: IPC Protocol Definition

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **a well-defined IPC protocol for TUI-daemon communication**,
So that **all clients communicate consistently with the daemon**.

## Acceptance Criteria

1. **Given** Story 2.1 is complete
2. **When** I import from `daemon.ipc`
3. **Then** `IPCRequest` and `IPCResponse` dataclasses are available
4. **And** commands are defined: `sessions.list`, `engagement.start`, `engagement.attach`, `engagement.detach`, `engagement.pause`, `engagement.resume`, `engagement.stop`
5. **And** responses include status, data, and error fields
6. **And** protocol uses JSON serialization over Unix socket
7. **And** unit tests verify protocol serialization

## Tasks / Subtasks

> [!IMPORTANT]
> **DEFINES IPC CONTRACTS — All daemon commands (Story 2.3+) depend on these dataclasses and protocol**

### Phase 1: IPC Dataclasses

- [x] Task 1: Create `daemon/` package structure (AC: #2) <!-- id: 0 -->
  - [x] Create `src/cyberred/daemon/__init__.py`
  - [x] Create `src/cyberred/daemon/ipc.py`
  - [x] Ensure daemon package is importable

- [x] Task 2: Define `IPCRequest` dataclass (AC: #3, #4) <!-- id: 1 -->
  - [x] Define `IPCRequest` with fields:
    - `command: str` — The IPC command (e.g., `sessions.list`, `engagement.start`)
    - `params: Dict[str, Any]` — Command parameters (e.g., `{id: "eng-1"}`)
    - `request_id: str` — UUID for request/response correlation
  - [x] Implement `to_json()` method returning JSON string
  - [x] Implement `from_json(data: str)` classmethod
  - [x] Add validation: command must not be empty

- [x] Task 3: Define `IPCResponse` dataclass (AC: #3, #5) <!-- id: 2 -->
  - [x] Define `IPCResponse` with fields:
    - `status: str` — "ok", "error"
    - `data: Optional[Dict[str, Any]]` — Response payload
    - `error: Optional[str]` — Error message if status is "error"
    - `request_id: str` — Matching request ID for correlation
  - [x] Implement `to_json()` method returning JSON string
  - [x] Implement `from_json(data: str)` classmethod
  - [x] Add factory methods: `ok(data, request_id)`, `error(message, request_id)`

### Phase 2: Command Constants

- [x] Task 4: Define IPC command constants (AC: #4) <!-- id: 3 -->
  - [x] Create `IPCCommand` class inheriting from `enum.StrEnum` (Python 3.11+)
  - [x] Define constants: `SESSIONS_LIST`, `ENGAGEMENT_START`, etc.
  - [x] Use `StrEnum` native capabilities for iteration and validation

### Phase 3: Protocol Utilities

- [x] Task 5: JSON wire protocol helpers (AC: #6) <!-- id: 4 -->
  - [x] Create `encode_message(request_or_response) -> bytes` (UTF-8 + newline delimiter)
  - [x] Create `decode_message(data: bytes) -> Union[IPCRequest, IPCResponse]`
  - [x] Handle malformed JSON with `IPCProtocolError` exception
  - [x] Add `IPCProtocolError` to `core/exceptions.py`

- [x] Task 6: Request builder helper (AC: #3, #4) <!-- id: 5 -->
  - [x] Create `build_request(command: str, **params) -> IPCRequest`
  - [x] Auto-generate UUID for request_id
  - [x] Validate command against `IPCCommand` enum

### Phase 4: Testing

- [x] Task 7: Create unit tests for IPC protocol (AC: #7) <!-- id: 6 -->
  - [x] Create `tests/unit/daemon/__init__.py`
  - [x] Create `tests/unit/daemon/test_ipc.py`
  - [x] Test `IPCRequest` serialization/deserialization round-trip
  - [x] Test `IPCResponse` serialization/deserialization round-trip
  - [x] Test `IPCResponse.ok()` and `IPCResponse.error()` factory methods
  - [x] Test `IPCCommand` constants and validation
  - [x] Test `encode_message()` and `decode_message()`
  - [x] Test malformed JSON raises `IPCProtocolError`
  - [x] Test request_id correlation

- [x] Task 8: Run full test suite <!-- id: 7 -->
  - [x] Run `pytest tests/unit/daemon/test_ipc.py -v`
  - [x] Run `pytest --cov=src/cyberred/daemon --cov-report=term-missing`
  - [x] Verify 100% coverage on `daemon/ipc.py`
  - [x] Verify no test regressions (full suite green)

## Dev Notes

### Architecture Context

This story implements the IPC protocol per architecture (lines 417-427, 774):

```
src/cyberred/daemon/
├── __init__.py
├── ipc.py           # ← THIS STORY: IPCRequest, IPCResponse, protocol
├── server.py        # Story 2.3: Unix socket server
├── session_manager.py  # Story 2.5
└── state_machine.py    # Story 2.4
```

**From Architecture — IPC Protocol (Unix Socket):**

| Command | Request | Response |
|---------|---------|----------|
| `sessions.list` | `{}` | `{engagements: [{id, state, agents, findings}]}` |
| `engagement.start` | `{config_path}` | `{id, state}` |
| `engagement.attach` | `{id}` | Stream: real-time state updates |
| `engagement.detach` | `{id}` | `{success}` |
| `engagement.pause` | `{id}` | `{state: "PAUSED"}` |
| `engagement.resume` | `{id}` | `{state: "RUNNING"}` |
| `engagement.stop` | `{id}` | `{state: "STOPPED", checkpoint_path}` |

### Message Wire Format

Per architecture decisions (lines 225, 543-544):
- **Serialization:** JSON (human-readable, debugging-friendly)
- **Delimiter:** Newline (`\n`) for message framing
- **Encoding:** UTF-8

**Request Format:**
```json
{
  "command": "engagement.start",
  "params": {"config_path": "~/.cyber-red/engagements/ministry.yaml"},
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response Format (Success):**
```json
{
  "status": "ok",
  "data": {"id": "ministry-2025", "state": "INITIALIZING"},
  "error": null,
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response Format (Error):**
```json
{
  "status": "error",
  "data": null,
  "error": "Engagement 'foo' not found",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Implementation Pattern

```python
# src/cyberred/daemon/ipc.py
from dataclasses import dataclass, asdict
from typing import Any, Optional
from enum import StrEnum
import json
import uuid


class IPCCommand(StrEnum):
    """IPC command constants."""
    SESSIONS_LIST = "sessions.list"
    ENGAGEMENT_START = "engagement.start"
    ENGAGEMENT_ATTACH = "engagement.attach"
    ENGAGEMENT_DETACH = "engagement.detach"
    ENGAGEMENT_PAUSE = "engagement.pause"
    ENGAGEMENT_RESUME = "engagement.resume"
    ENGAGEMENT_STOP = "engagement.stop"


@dataclass
class IPCRequest:
    """IPC request from TUI/CLI to daemon."""
    command: str
    params: dict[str, Any]
    request_id: str

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "IPCRequest":
        parsed = json.loads(data)
        return cls(**parsed)


@dataclass  
class IPCResponse:
    """IPC response from daemon to TUI/CLI."""
    status: str
    data: Optional[dict[str, Any]]
    error: Optional[str]
    request_id: str

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "IPCResponse":
        parsed = json.loads(data)
        return cls(**parsed)

    @classmethod
    def ok(cls, data: dict[str, Any], request_id: str) -> "IPCResponse":
        return cls(status="ok", data=data, error=None, request_id=request_id)

    @classmethod
    def error(cls, message: str, request_id: str) -> "IPCResponse":
        return cls(status="error", data=None, error=message, request_id=request_id)


def build_request(command: str, **params: Any) -> IPCRequest:
    """Build an IPC request with auto-generated request_id."""
    try:
        # Validate against enum values
        IPCCommand(command)
    except ValueError:
        raise ValueError(f"Invalid IPC command: {command}")
    return IPCRequest(
        command=command,
        params=params,
        request_id=str(uuid.uuid4())
    )


def encode_message(msg: IPCRequest | IPCResponse) -> bytes:
    """Encode message to wire format (JSON + newline, UTF-8)."""
    return (msg.to_json() + "\n").encode("utf-8")


def decode_message(data: bytes) -> IPCRequest | IPCResponse:
    """Decode message from wire format."""
    from cyberred.core.exceptions import IPCProtocolError
    try:
        text = data.decode("utf-8").strip()
        parsed = json.loads(text)
        if "command" in parsed:
            return IPCRequest.from_json(text)
        return IPCResponse.from_json(text)
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as e:
        raise IPCProtocolError(f"Failed to decode IPC message: {e}") from e
```

### Exception Addition

Add to `src/cyberred/core/exceptions.py`:

```python
class IPCProtocolError(CyberRedError):
    """Invalid or malformed IPC message."""
```

### Test Pattern

```python
# tests/unit/daemon/test_ipc.py
import pytest
import json
from cyberred.daemon.ipc import (
    IPCRequest, IPCResponse, IPCCommand,
    build_request, encode_message, decode_message
)
from cyberred.core.exceptions import IPCProtocolError


class TestIPCRequest:
    def test_serialization_roundtrip(self) -> None:
        req = IPCRequest(
            command="sessions.list",
            params={},
            request_id="test-uuid"
        )
        json_str = req.to_json()
        restored = IPCRequest.from_json(json_str)
        assert restored == req

    def test_to_json_format(self) -> None:
        req = IPCRequest(
            command="engagement.start",
            params={"config_path": "/path/to/config"},
            request_id="abc-123"
        )
        parsed = json.loads(req.to_json())
        assert parsed["command"] == "engagement.start"
        assert parsed["params"]["config_path"] == "/path/to/config"
        assert parsed["request_id"] == "abc-123"


class TestIPCResponse:
    def test_ok_factory(self) -> None:
        resp = IPCResponse.ok({"id": "eng-1"}, "req-123")
        assert resp.status == "ok"
        assert resp.data == {"id": "eng-1"}
        assert resp.error is None
        assert resp.request_id == "req-123"

    def test_error_factory(self) -> None:
        resp = IPCResponse.error("Not found", "req-456")
        assert resp.status == "error"
        assert resp.data is None
        assert resp.error == "Not found"


class TestIPCCommand:
    def test_enum_members(self) -> None:
        assert IPCCommand.SESSIONS_LIST == "sessions.list"
        assert IPCCommand.ENGAGEMENT_START == "engagement.start"
        assert len(IPCCommand) == 7

    def test_validation(self) -> None:
        # Valid member lookup by value
        assert IPCCommand("sessions.list") == IPCCommand.SESSIONS_LIST
        
        # Invalid value raises ValueError
        with pytest.raises(ValueError):
            IPCCommand("invalid.command")


class TestWireProtocol:
    def test_encode_decode_request(self) -> None:
        req = build_request("sessions.list")
        encoded = encode_message(req)
        decoded = decode_message(encoded)
        assert isinstance(decoded, IPCRequest)
        assert decoded.command == req.command

    def test_malformed_json_raises_error(self) -> None:
        with pytest.raises(IPCProtocolError):
            decode_message(b"not valid json")
```

### Dependencies

No additional dependencies required. Uses standard library:
- `dataclasses` (stdlib)
- `json` (stdlib)
- `uuid` (stdlib)
- `typing` (stdlib)

### Previous Story Intelligence

**From Story 2.1 (CLI Entry Point):**
- Project structure uses `src/cyberred/` layout
- 100% coverage gate enforced
- Test patterns in `tests/unit/{module}/test_{file}.py`
- CLI uses Typer, will need integration with IPC in future stories
- Story 2.1 review confirmed config validation patterns work correctly

**CLI → IPC Integration (Future Story 2.3+):**
The CLI commands in `cli.py` (daemon start/stop/status, sessions, attach, etc.) will eventually use these IPC dataclasses to communicate with the daemon. Currently they are stubs.

### Anti-Patterns to Avoid

1. **NEVER** implement actual socket communication in this story (that's Story 2.3)
2. **NEVER** add streaming support yet (attach command streams are Story 2.3/2.9)
3. **NEVER** use pickle or other non-JSON serialization (security risk)
4. **NEVER** skip the `request_id` field (critical for async request/response correlation)
5. **NEVER** hardcode socket paths in this module (IPC protocol only, not transport)

### Project Structure Notes

- Creates new `daemon/` package under `src/cyberred/`
- Aligns with architecture project structure (line 769-774)
- `IPCProtocolError` extends `CyberRedError` (Story 1.1 exception hierarchy)

### References

- [Architecture: IPC Protocol](file:///root/red/docs/3-solutioning/architecture.md#L417-L427)
- [Architecture: Daemon Structure](file:///root/red/docs/3-solutioning/architecture.md#L769-L774)
- [Architecture: Message Serialization](file:///root/red/docs/3-solutioning/architecture.md#L225)
- [Architecture: Daemon Execution Model](file:///root/red/docs/3-solutioning/architecture.md#L365-L405)
- [Epics: Story 2.2](file:///root/red/docs/3-solutioning/epics-stories.md#L1113-L1132)
- [Epics: Story 2.3 (Unix Socket Server)](file:///root/red/docs/3-solutioning/epics-stories.md#L1136-L1156)

## Dev Agent Record

### Agent Model Used

Gemini 2.5 Pro

### Debug Log References

N/A - All tests pass

### Completion Notes List

- **2026-01-01**: Implemented IPC Protocol Definition per Story 2.2 ACs
- Created `src/cyberred/daemon/__init__.py` and `src/cyberred/daemon/ipc.py`
- Implemented `IPCCommand` as `StrEnum` with 7 commands
- Implemented `IPCRequest` and `IPCResponse` dataclasses with JSON serialization
- Added `encode_message()` and `decode_message()` wire protocol utilities
- Added `build_request()` helper with auto-generated UUID
- Added `IPCProtocolError` exception to `core/exceptions.py`
- Created 36 unit tests in `tests/unit/daemon/test_ipc.py`
- **100% coverage achieved on `daemon/ipc.py`**
- All 449 tests pass (54 skipped for future stories), no regressions

### Change Log

- **2026-01-01**: Story 2.2 implemented - IPC protocol dataclasses, StrEnum, wire protocol, comprehensive tests

### File List

- `src/cyberred/daemon/__init__.py` (new)
- `src/cyberred/daemon/ipc.py` (new)
- `src/cyberred/core/exceptions.py` (modified - added `IPCProtocolError`)
- `tests/unit/daemon/__init__.py` (new)
- `tests/unit/daemon/test_ipc.py` (new)
