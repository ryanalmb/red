"""Streaming Protocol for TUI-Daemon Real-Time Communication.

This module defines the streaming protocol types and utilities for
real-time event streaming between daemon and attached TUI clients.

Event Types:
- AGENT_STATUS: Agent state changes
- FINDING: New vulnerability discoveries
- AUTH_REQUEST: Authorization prompts
- STATE_CHANGE: Engagement state transitions
- HEARTBEAT: Keep-alive signals

Usage:
    from cyberred.daemon.streaming import (
        StreamEvent, StreamEventType,
        encode_stream_event, decode_stream_event
    )

    # Create and encode event
    event = StreamEvent(
        event_type=StreamEventType.FINDING,
        data={"finding_id": "abc123", "severity": "HIGH"},
    )
    wire_data = encode_stream_event(event)

    # Decode from wire
    decoded = decode_stream_event(wire_data)
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
import json


class StreamEventType(StrEnum):
    """Stream event type constants.

    All valid event types that can be streamed from daemon to TUI client.
    Uses StrEnum for type safety and JSON serialization.
    """

    AGENT_STATUS = "agent_status"
    FINDING = "finding"
    AUTH_REQUEST = "auth_request"
    STATE_CHANGE = "state_change"
    HEARTBEAT = "heartbeat"
    DAEMON_SHUTDOWN = "daemon_shutdown"  # Story 2.11: Graceful shutdown notification


@dataclass
class StreamEvent:
    """A streaming event from daemon to TUI client.

    Attributes:
        event_type: Type of event (see StreamEventType).
        data: Event payload as key-value pairs.
        timestamp: ISO-formatted UTC timestamp.
    """

    event_type: str
    data: dict[str, Any]
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        """Validate event fields after initialization."""
        if not self.event_type:
            raise ValueError("StreamEvent.event_type must not be empty")
        # Validate event_type is valid enum value
        try:
            StreamEventType(self.event_type)
        except ValueError:
            valid_types = [t.value for t in StreamEventType]
            raise ValueError(
                f"Invalid event type: '{self.event_type}'. "
                f"Valid types: {valid_types}"
            ) from None

    def to_json(self) -> str:
        """Serialize event to JSON string.

        Returns:
            JSON string representation of the event.
        """
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "StreamEvent":
        """Deserialize event from JSON string.

        Args:
            data: JSON string to parse.

        Returns:
            StreamEvent instance.

        Raises:
            json.JSONDecodeError: If JSON is invalid.
            TypeError: If JSON is not an object or fields are missing.
            ValueError: If fields are invalid.
        """
        parsed = json.loads(data)
        if not isinstance(parsed, dict):
            raise TypeError("JSON data must be a dictionary object")

        # Forward compatibility: Filter out unknown fields
        known_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in parsed.items() if k in known_fields}

        return cls(**filtered)


def encode_stream_event(event: StreamEvent) -> bytes:
    """Encode streaming event to wire format (JSON + newline, UTF-8).

    Args:
        event: StreamEvent to encode.

    Returns:
        UTF-8 encoded bytes with newline delimiter.
    """
    return (event.to_json() + "\n").encode("utf-8")


def decode_stream_event(data: bytes) -> StreamEvent:
    """Decode streaming event from wire format.

    Args:
        data: UTF-8 encoded bytes (JSON with optional newline).

    Returns:
        StreamEvent instance.

    Raises:
        StreamProtocolError: If message cannot be decoded.
    """
    from cyberred.core.exceptions import StreamProtocolError

    try:
        text = data.decode("utf-8").strip()
        return StreamEvent.from_json(text)

    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise StreamProtocolError(f"Failed to decode stream event: {e}") from e
    except (TypeError, KeyError) as e:
        raise StreamProtocolError(f"Invalid stream event structure: {e}") from e
    except ValueError as e:
        raise StreamProtocolError(f"Stream event validation failed: {e}") from e


# Type alias for subscription callbacks
StreamCallback = type("StreamCallback", (), {})  # Callable[[StreamEvent], None]
