# Story 12.2: C2 Message Protocol

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **a structured C2 message protocol**,
So that **commands, results, and heartbeats have consistent format (FR24)**.

## Acceptance Criteria

1. **Given** Story 12.1 is complete (mTLS C2 server implemented)
   - **When** C2 sends/receives messages
   - **Then** messages follow schema: `{type, id, timestamp, payload, signature}`

2. **Given** a message is constructed
   - **When** the type field is set
   - **Then** type is one of: `command`, `result`, `heartbeat`

3. **Given** a message with payload
   - **When** signature is computed
   - **Then** signature is HMAC-SHA256 of payload

4. **Given** a message is received
   - **When** signature validation fails
   - **Then** message is rejected and logged with rejection reason

5. **Given** implementation is complete
   - **Then** unit tests verify protocol serialization/deserialization
   - **And** unit tests verify HMAC signature generation and validation
   - **And** unit tests verify rejection of tampered messages
   - **And** all tests pass in CI with 100% coverage on new code

## Tasks / Subtasks

**⚠️ CRITICAL: Test-Driven Development (TDD) Required**

> This story MUST follow strict TDD methodology:
> 1. **RED Phase**: Write failing tests FIRST before any implementation
> 2. **GREEN Phase**: Write minimal code to make tests pass
> 3. **REFACTOR Phase**: Clean up code while keeping tests green
>
> **🎯 COVERAGE REQUIREMENT**
> - All new code MUST achieve 100% test coverage
> - Run targeted coverage checks per file/module

**⚠️ CRITICAL: Python Environment**

> Use `venv` (not `.venv`) for activating the Python virtual environment:
> ```bash
> source venv/bin/activate
> ```

- [x] Task 1: Define C2 message data models (AC: #1, #2)
  - [x] Subtask 1.1: RED - Write failing tests for `C2MessageType` enum (command, result, heartbeat)
  - [x] Subtask 1.2: GREEN - Implement `C2MessageType` enum in `src/cyberred/c2/protocol.py`
  - [x] Subtask 1.3: RED - Write failing tests for `C2Message` dataclass with required fields
  - [x] Subtask 1.4: GREEN - Implement `C2Message` dataclass with: type, id, timestamp, payload, signature

- [x] Task 2: Implement HMAC-SHA256 signature (AC: #3)
  - [x] Subtask 2.1: RED - Write failing tests for `sign_payload()` function
  - [x] Subtask 2.2: GREEN - Implement `sign_payload(payload: dict, secret: bytes) -> str` using HMAC-SHA256
  - [x] Subtask 2.3: RED - Write failing tests for `verify_signature()` function
  - [x] Subtask 2.4: GREEN - Implement `verify_signature(message: C2Message, secret: bytes) -> bool`

- [x] Task 3: Implement message serialization (AC: #1)
  - [x] Subtask 3.1: RED - Write failing tests for `C2Message.to_json()` method
  - [x] Subtask 3.2: GREEN - Implement JSON serialization with ISO8601 timestamp
  - [x] Subtask 3.3: RED - Write failing tests for `C2Message.from_json()` class method
  - [x] Subtask 3.4: GREEN - Implement JSON deserialization with validation

- [x] Task 4: Implement message factory functions (AC: #1, #2)
  - [x] Subtask 4.1: RED - Write failing tests for `create_command_message()`
  - [x] Subtask 4.2: GREEN - Implement factory for command messages
  - [x] Subtask 4.3: RED - Write failing tests for `create_result_message()`
  - [x] Subtask 4.4: GREEN - Implement factory for result messages
  - [x] Subtask 4.5: RED - Write failing tests for `create_heartbeat_message()`
  - [x] Subtask 4.6: GREEN - Implement factory for heartbeat messages

- [x] Task 5: Implement signature validation with rejection logging (AC: #4)
  - [x] Subtask 5.1: RED - Write failing tests for invalid signature rejection
  - [x] Subtask 5.2: GREEN - Implement `validate_and_parse_message()` that rejects invalid signatures
  - [x] Subtask 5.3: Add structlog logging for rejection events with reason
  - [x] Subtask 5.4: RED - Write tests for tampered payload detection
  - [x] Subtask 5.5: GREEN - Verify tampered messages are rejected

- [x] Task 6: Integrate protocol with C2Server (AC: #1, #4)
  - [x] Subtask 6.1: Update `C2Server._connection_handler()` to use protocol for message handling
  - [x] Subtask 6.2: Add shared secret configuration to `C2ServerConfig`
  - [x] Subtask 6.3: Implement message dispatch based on type (command/result/heartbeat)

- [x] Task 7: Write comprehensive unit tests (AC: #5)
  - [x] Subtask 7.1: Test all message types serialize/deserialize correctly
  - [x] Subtask 7.2: Test HMAC signature is deterministic for same payload
  - [x] Subtask 7.3: Test signature verification passes for valid messages
  - [x] Subtask 7.4: Test signature verification fails for tampered messages
  - [x] Subtask 7.5: Test rejection logging includes message ID and rejection reason
  - [x] Subtask 7.6: Verify ≥100% coverage on `src/cyberred/c2/protocol.py`

- [x] Task 8: Final validation and cleanup
  - [x] Subtask 8.1: Run full test suite (`pytest tests/unit/c2 -v`)
  - [x] Subtask 8.2: Run coverage check (`pytest --cov=src/cyberred/c2/protocol --cov-report=term-missing`)
  - [x] Subtask 8.3: Verify all AC met
  - [x] Subtask 8.4: Update sprint-status.yaml to "review"

## Dev Notes

### Architecture Context

This is **Story 12.2 of Epic 12: Drop Box & C2 Operations**. This story implements the structured message protocol that enables secure, verifiable communication between the C2 server (implemented in Story 12.1) and remote drop boxes.

**From PRD (lines 1712-1721) - Message Format:**
```json
{
  "type": "command|result|heartbeat",
  "id": "uuid",
  "timestamp": "ISO8601",
  "payload": { ... },
  "signature": "HMAC-SHA256"
}
```

**From Architecture - Security Hardening:**
- HMAC-SHA256 signature on all C2 messages for integrity verification
- Message integrity prevents AiTM (Adversary-in-the-Middle) attacks
- Per architecture: `NFR Security: Message Integrity` → HMAC-SHA256 in `core/events.py` pattern

**System Architecture Position:**
```
┌────────────────┐     WebSocket     ┌───────────────────┐     mTLS WS      ┌──────────────┐
│  Textual TUI   │◄──────────────────►│   Cyber-Red Core  │◄────────────────►│   Drop Box   │
│  (operator)    │    127.0.0.1:8080  │   (asyncio)       │   0.0.0.0:8444   │   (remote)   │
└────────────────┘                    └───────────────────┘                   └──────────────┘
                                              │
                                              ▼
                                      C2 Message Protocol
                                      (this story)
```

### Existing Code to Build Upon

**C2Server (src/cyberred/c2/server.py) - From Story 12.1:**
```python
async def _connection_handler(self, websocket: WebSocketServerProtocol) -> None:
    """Handle incoming WebSocket connection."""
    client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"
    log.info("c2_client_connected", client_ip=client_ip)
    self._connections.add(websocket)

    try:
        async for message in websocket:
            # Message handling will be implemented in Story 12.2  <-- THIS STORY
            log.debug("c2_message_received", client_ip=client_ip, size=len(message))
    except websockets.exceptions.ConnectionClosed:
        log.info("c2_client_disconnected", client_ip=client_ip)
    finally:
        self._connections.discard(websocket)
```

**CAStore HMAC Pattern (for reference):**
```python
import hmac
import hashlib

def sign_payload(payload: dict, secret: bytes) -> str:
    """Generate HMAC-SHA256 signature for payload."""
    payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
    return hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()

def verify_signature(message: C2Message, secret: bytes) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = sign_payload(message.payload, secret)
    return hmac.compare_digest(message.signature, expected)
```

### Implementation Pattern

**C2 Protocol Module Structure (`src/cyberred/c2/protocol.py`):**
```python
"""C2 message protocol for drop box communication.

Per FR24: Commands, results, and heartbeats have consistent format.
Per PRD: Message format with HMAC-SHA256 signature.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import structlog

log = structlog.get_logger()


class C2MessageType(Enum):
    """Types of C2 messages."""
    COMMAND = "command"
    RESULT = "result"
    HEARTBEAT = "heartbeat"


@dataclass
class C2Message:
    """Structured C2 message with HMAC-SHA256 signature.
    
    Attributes:
        type: Message type (command, result, heartbeat)
        id: Unique message identifier (UUID)
        timestamp: ISO8601 timestamp
        payload: Message payload (type-specific content)
        signature: HMAC-SHA256 signature of payload
    """
    type: C2MessageType
    id: str
    timestamp: str
    payload: dict[str, Any]
    signature: str
    
    def to_json(self) -> str:
        """Serialize message to JSON string."""
        return json.dumps({
            "type": self.type.value,
            "id": self.id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "signature": self.signature,
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> "C2Message":
        """Deserialize message from JSON string.
        
        Raises:
            ValueError: If JSON is invalid or missing required fields
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        
        required_fields = {"type", "id", "timestamp", "payload", "signature"}
        missing = required_fields - set(data.keys())
        if missing:
            raise ValueError(f"Missing required fields: {missing}")
        
        try:
            msg_type = C2MessageType(data["type"])
        except ValueError:
            raise ValueError(f"Invalid message type: {data['type']}")
        
        return cls(
            type=msg_type,
            id=data["id"],
            timestamp=data["timestamp"],
            payload=data["payload"],
            signature=data["signature"],
        )


def sign_payload(payload: dict[str, Any], secret: bytes) -> str:
    """Generate HMAC-SHA256 signature for payload.
    
    Args:
        payload: The message payload to sign
        secret: Shared secret for HMAC
        
    Returns:
        Hexadecimal signature string
    """
    # Sort keys for deterministic serialization
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()


def verify_signature(message: C2Message, secret: bytes) -> bool:
    """Verify HMAC-SHA256 signature of message.
    
    Args:
        message: The message to verify
        secret: Shared secret for HMAC
        
    Returns:
        True if signature is valid, False otherwise
    """
    expected = sign_payload(message.payload, secret)
    return hmac.compare_digest(message.signature, expected)


def create_command_message(
    command: str,
    args: dict[str, Any],
    secret: bytes,
    message_id: Optional[str] = None,
) -> C2Message:
    """Create a command message with signature.
    
    Args:
        command: Command name to execute
        args: Command arguments
        secret: Shared secret for signing
        message_id: Optional custom message ID
        
    Returns:
        Signed C2Message
    """
    payload = {"command": command, "args": args}
    return C2Message(
        type=C2MessageType.COMMAND,
        id=message_id or str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        payload=payload,
        signature=sign_payload(payload, secret),
    )


def create_result_message(
    command_id: str,
    success: bool,
    output: Any,
    secret: bytes,
    message_id: Optional[str] = None,
) -> C2Message:
    """Create a result message with signature.
    
    Args:
        command_id: ID of the command this result is for
        success: Whether command succeeded
        output: Command output/result
        secret: Shared secret for signing
        message_id: Optional custom message ID
        
    Returns:
        Signed C2Message
    """
    payload = {"command_id": command_id, "success": success, "output": output}
    return C2Message(
        type=C2MessageType.RESULT,
        id=message_id or str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        payload=payload,
        signature=sign_payload(payload, secret),
    )


def create_heartbeat_message(
    drop_box_id: str,
    status: str,
    secret: bytes,
    message_id: Optional[str] = None,
) -> C2Message:
    """Create a heartbeat message with signature.
    
    Args:
        drop_box_id: Identifier of the drop box
        status: Current drop box status
        secret: Shared secret for signing
        message_id: Optional custom message ID
        
    Returns:
        Signed C2Message
    """
    payload = {"drop_box_id": drop_box_id, "status": status}
    return C2Message(
        type=C2MessageType.HEARTBEAT,
        id=message_id or str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        payload=payload,
        signature=sign_payload(payload, secret),
    )


def validate_and_parse_message(
    json_str: str,
    secret: bytes,
) -> tuple[Optional[C2Message], Optional[str]]:
    """Parse and validate a C2 message.
    
    Args:
        json_str: Raw JSON message string
        secret: Shared secret for signature verification
        
    Returns:
        Tuple of (message, error). If valid, message is set and error is None.
        If invalid, message is None and error contains rejection reason.
    """
    try:
        message = C2Message.from_json(json_str)
    except ValueError as e:
        log.warning("c2_message_rejected", reason=str(e), raw_size=len(json_str))
        return None, str(e)
    
    if not verify_signature(message, secret):
        log.warning(
            "c2_message_rejected",
            reason="invalid_signature",
            message_id=message.id,
            message_type=message.type.value,
        )
        return None, "invalid_signature"
    
    return message, None
```

### Message Type Payloads

**Command Payload:**
```json
{
  "command": "exec",
  "args": {
    "tool": "nmap",
    "target": "192.168.1.0/24",
    "options": ["-sV", "-sC"]
  }
}
```

**Result Payload:**
```json
{
  "command_id": "uuid-of-original-command",
  "success": true,
  "output": {
    "stdout": "...",
    "stderr": "",
    "exit_code": 0
  }
}
```

**Heartbeat Payload:**
```json
{
  "drop_box_id": "dropbox-alpha-01",
  "status": "healthy"
}
```

### Security Considerations

1. **HMAC-SHA256**: Constant-time comparison via `hmac.compare_digest()` prevents timing attacks
2. **Deterministic Serialization**: `sort_keys=True` ensures consistent signature across serializations
3. **Secret Management**: Shared secret should be derived from engagement CA or securely exchanged
4. **Rejection Logging**: All invalid messages logged with reason for audit trail (per ERR4 handling)
5. **No Payload Encryption**: mTLS provides transport encryption; HMAC provides integrity only

### Error Handling

| Error | Handling |
|-------|----------|
| Invalid JSON | Reject message, log "Invalid JSON" |
| Missing fields | Reject message, log missing field names |
| Invalid message type | Reject message, log invalid type value |
| Invalid signature | Reject message, log "invalid_signature" with message ID |
| Tampered payload | Same as invalid signature (HMAC mismatch) |

### Dependencies

**Required Python Packages (already in requirements.txt):**
- `structlog>=23.0.0` - Structured logging

**Standard Library (no additional deps):**
- `hmac` - HMAC computation
- `hashlib` - SHA256 hash
- `json` - JSON serialization
- `uuid` - Message ID generation
- `dataclasses` - Data models

**Internal Dependencies:**
- Story 12.1: C2Server (mTLS WebSocket server) - **COMPLETED** ✓

### Testing Strategy

**Unit Tests (`tests/unit/c2/test_protocol.py`):**
- `test_c2_message_type_enum` - All three types defined
- `test_c2_message_dataclass` - All fields present
- `test_c2_message_to_json` - Correct JSON serialization
- `test_c2_message_from_json_valid` - Correct deserialization
- `test_c2_message_from_json_invalid_json` - Raises ValueError
- `test_c2_message_from_json_missing_fields` - Raises ValueError with field names
- `test_c2_message_from_json_invalid_type` - Raises ValueError
- `test_sign_payload_deterministic` - Same payload + secret = same signature
- `test_sign_payload_different_secrets` - Different secrets = different signatures
- `test_verify_signature_valid` - Returns True for valid signature
- `test_verify_signature_invalid` - Returns False for invalid signature
- `test_verify_signature_tampered_payload` - Returns False when payload modified
- `test_create_command_message` - Correct structure and signature
- `test_create_result_message` - Correct structure and signature
- `test_create_heartbeat_message` - Correct structure and signature
- `test_validate_and_parse_message_valid` - Returns message, no error
- `test_validate_and_parse_message_invalid_json` - Returns None, error
- `test_validate_and_parse_message_invalid_signature` - Returns None, "invalid_signature"
- `test_rejection_logging` - Verify structlog captures rejection events

**Test Fixtures:**
```python
import pytest

@pytest.fixture
def shared_secret() -> bytes:
    """Test shared secret for HMAC."""
    return b"test_secret_key_for_hmac_signing"

@pytest.fixture
def sample_command_payload() -> dict:
    """Sample command payload."""
    return {"command": "exec", "args": {"tool": "nmap", "target": "127.0.0.1"}}

@pytest.fixture
def sample_heartbeat_payload() -> dict:
    """Sample heartbeat payload."""
    return {"drop_box_id": "test-dropbox-01", "status": "healthy"}
```

### Project Structure Notes

**New Files:**
- `src/cyberred/c2/protocol.py` - C2 message protocol implementation
- `tests/unit/c2/test_protocol.py` - Unit tests for protocol

**Modified Files:**
- `src/cyberred/c2/__init__.py` - Add protocol exports
- `src/cyberred/c2/server.py` - Integrate protocol in message handler (Task 6)

**Alignment with Architecture:**
- Location: `src/cyberred/c2/protocol.py` per architecture directory structure
- Naming: `C2Message`, `C2MessageType` follow PascalCase convention
- Logging: Uses `structlog` per architecture logging pattern
- Security: HMAC-SHA256 per architecture security requirements

### References

- [Source: _bmad-output/planning-artifacts/prd.md#Drop Box C2 Protocol Specification] - Message format (lines 1712-1721)
- [Source: _bmad-output/planning-artifacts/architecture.md#Security Hardening] - HMAC-SHA256 message integrity
- [Source: _bmad-output/planning-artifacts/architecture.md#API Design] - C2 Protocol: mTLS WebSocket
- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 12.2] - Acceptance criteria
- [Source: src/cyberred/c2/server.py] - C2Server implementation (Story 12.1)
- [Source: _bmad-output/implementation-artifacts/12-1-mtls-c2-server.md] - Previous story learnings

### Previous Story Learnings (from 12.1)

From Story 12.1 code review:
1. **Use built-in `set[]` not `Set` from typing** - Python 3.12+ style
2. **Use `datetime.now(timezone.utc)` not `datetime.utcnow()`** - Deprecated method
3. **Implement `from_yaml()` if config loading is specified** - Don't mark tasks done prematurely
4. **Add logging for rejection events** - Audit trail requirement

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

- All 51 protocol unit tests pass
- All 94 C2 module tests pass (protocol + server)
- 100% test coverage on `src/cyberred/c2/protocol.py`

### Completion Notes List

- Implemented C2MessageType enum with COMMAND, RESULT, HEARTBEAT types
- Implemented C2Message dataclass with type, id, timestamp, payload, signature fields
- Implemented HMAC-SHA256 signing via sign_payload() with deterministic serialization (sort_keys=True)
- Implemented verify_signature() using constant-time hmac.compare_digest() to prevent timing attacks
- Implemented to_json()/from_json() serialization with full validation
- Implemented factory functions: create_command_message, create_result_message, create_heartbeat_message
- Implemented validate_and_parse_message() with structlog rejection logging
- Integrated protocol with C2Server._connection_handler() for message dispatch
- Added shared_secret field to C2ServerConfig with YAML loading support
- Updated src/cyberred/c2/__init__.py to export all protocol classes and functions
- [Review Fix] Added input validation to sign_payload(): payload must be dict, secret cannot be empty
- [Review Fix] Added tests for shared_secret loading in C2ServerConfig.from_yaml() (hex string, None, empty)
- [Review Fix] Added integration tests for _connection_handler protocol dispatch (command, result, heartbeat)
- [Review Fix] Added shared_secret fixture to tests/unit/c2/conftest.py

### Change Log

- 2026-02-02: Initial implementation of C2 message protocol (Story 12.2)
- 2026-02-02: Code review fixes - Added input validation (payload must be dict, secret cannot be empty), added 11 new tests for shared_secret YAML loading, _connection_handler protocol integration, and input validation edge cases

### File List

**New Files:**
- `src/cyberred/c2/protocol.py` - C2 message protocol implementation (240 lines, 100% coverage)
- `tests/unit/c2/test_protocol.py` - Comprehensive unit tests (51 tests)

**Modified Files:**
- `src/cyberred/c2/__init__.py` - Added protocol exports
- `src/cyberred/c2/server.py` - Integrated protocol in _connection_handler, added shared_secret to config
