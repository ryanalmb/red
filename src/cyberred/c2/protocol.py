"""C2 message protocol for drop box communication.

Per FR24: Commands, results, and heartbeats have consistent format.
Per PRD: Message format with HMAC-SHA256 signature.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
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
        return json.dumps(
            {
                "type": self.type.value,
                "id": self.id,
                "timestamp": self.timestamp,
                "payload": self.payload,
                "signature": self.signature,
            }
        )

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

    Raises:
        ValueError: If payload is not a dict or secret is empty
    """
    if not isinstance(payload, dict):
        raise ValueError(f"Payload must be a dict, got {type(payload).__name__}")
    if not secret:
        raise ValueError("Secret cannot be empty")
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
