"""Unit tests for streaming protocol.

Tests for StreamEvent, StreamEventType, and encode/decode functions.
"""

import json
import pytest
from datetime import datetime, timezone

from cyberred.daemon.streaming import (
    StreamEvent,
    StreamEventType,
    encode_stream_event,
    decode_stream_event,
)
from cyberred.core.exceptions import StreamProtocolError


class TestStreamEventType:
    """Tests for StreamEventType enum."""

    def test_all_event_types_defined(self) -> None:
        """Verify all required event types are defined."""
        assert StreamEventType.AGENT_STATUS == "agent_status"
        assert StreamEventType.FINDING == "finding"
        assert StreamEventType.AUTH_REQUEST == "auth_request"
        assert StreamEventType.STATE_CHANGE == "state_change"
        assert StreamEventType.HEARTBEAT == "heartbeat"

    def test_event_type_is_strenum(self) -> None:
        """Verify StreamEventType is a StrEnum for JSON serialization."""
        event_type = StreamEventType.AGENT_STATUS
        # StrEnum values can be used directly as strings
        assert isinstance(event_type, str)
        assert event_type == "agent_status"


class TestStreamEvent:
    """Tests for StreamEvent dataclass."""

    def test_create_event_with_all_fields(self) -> None:
        """Event can be created with all fields specified."""
        event = StreamEvent(
            event_type="agent_status",
            data={"agent_id": "agent-001", "status": "active"},
            timestamp="2026-01-03T01:00:00+00:00",
        )
        assert event.event_type == "agent_status"
        assert event.data == {"agent_id": "agent-001", "status": "active"}
        assert event.timestamp == "2026-01-03T01:00:00+00:00"

    def test_create_event_with_default_timestamp(self) -> None:
        """Event gets auto-generated timestamp if not provided."""
        event = StreamEvent(
            event_type="finding",
            data={"finding_id": "f-001"},
        )
        assert event.timestamp is not None
        # Should be a valid ISO timestamp
        datetime.fromisoformat(event.timestamp)

    def test_create_event_with_enum_value(self) -> None:
        """Event can be created using StreamEventType enum."""
        event = StreamEvent(
            event_type=StreamEventType.STATE_CHANGE,
            data={"old_state": "RUNNING", "new_state": "PAUSED"},
        )
        assert event.event_type == "state_change"

    def test_create_event_empty_type_raises(self) -> None:
        """Event with empty event_type raises ValueError."""
        with pytest.raises(ValueError, match="event_type must not be empty"):
            StreamEvent(event_type="", data={})

    def test_create_event_invalid_type_raises(self) -> None:
        """Event with invalid event_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid event type"):
            StreamEvent(event_type="invalid_type", data={})

    def test_to_json(self) -> None:
        """Event serializes to valid JSON string."""
        event = StreamEvent(
            event_type="heartbeat",
            data={},
            timestamp="2026-01-03T01:00:00+00:00",
        )
        json_str = event.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["event_type"] == "heartbeat"
        assert parsed["data"] == {}
        assert parsed["timestamp"] == "2026-01-03T01:00:00+00:00"

    def test_from_json(self) -> None:
        """Event deserializes from valid JSON string."""
        json_str = '{"event_type": "auth_request", "data": {"target": "192.168.1.1"}, "timestamp": "2026-01-03T01:00:00+00:00"}'
        event = StreamEvent.from_json(json_str)
        
        assert event.event_type == "auth_request"
        assert event.data == {"target": "192.168.1.1"}
        assert event.timestamp == "2026-01-03T01:00:00+00:00"

    def test_from_json_ignores_unknown_fields(self) -> None:
        """Deserialize ignores unknown fields for forward compatibility."""
        json_str = '{"event_type": "finding", "data": {}, "timestamp": "2026-01-03T01:00:00+00:00", "unknown_field": "value"}'
        event = StreamEvent.from_json(json_str)
        
        assert event.event_type == "finding"
        assert not hasattr(event, "unknown_field")

    def test_from_json_invalid_json_raises(self) -> None:
        """Deserialize with invalid JSON raises JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            StreamEvent.from_json("not valid json")

    def test_from_json_not_dict_raises(self) -> None:
        """Deserialize with non-dict JSON raises TypeError."""
        with pytest.raises(TypeError, match="must be a dictionary"):
            StreamEvent.from_json("[1, 2, 3]")

    def test_roundtrip_serialization(self) -> None:
        """Event survives JSON roundtrip without data loss."""
        original = StreamEvent(
            event_type="agent_status",
            data={"agent_id": "agent-001", "status": "idle", "metrics": {"cpu": 50}},
            timestamp="2026-01-03T01:00:00+00:00",
        )
        json_str = original.to_json()
        restored = StreamEvent.from_json(json_str)
        
        assert restored.event_type == original.event_type
        assert restored.data == original.data
        assert restored.timestamp == original.timestamp


class TestEncodeStreamEvent:
    """Tests for encode_stream_event function."""

    def test_encode_returns_bytes(self) -> None:
        """Encode returns UTF-8 bytes."""
        event = StreamEvent(
            event_type="heartbeat",
            data={},
            timestamp="2026-01-03T01:00:00+00:00",
        )
        encoded = encode_stream_event(event)
        
        assert isinstance(encoded, bytes)

    def test_encode_ends_with_newline(self) -> None:
        """Encoded message ends with newline delimiter."""
        event = StreamEvent(
            event_type="finding",
            data={"id": "f-001"},
            timestamp="2026-01-03T01:00:00+00:00",
        )
        encoded = encode_stream_event(event)
        
        assert encoded.endswith(b"\n")

    def test_encode_is_utf8_json(self) -> None:
        """Encoded message is valid UTF-8 JSON."""
        event = StreamEvent(
            event_type="state_change",
            data={"old": "running", "new": "paused"},
            timestamp="2026-01-03T01:00:00+00:00",
        )
        encoded = encode_stream_event(event)
        
        decoded_str = encoded.decode("utf-8").strip()
        parsed = json.loads(decoded_str)
        
        assert parsed["event_type"] == "state_change"


class TestDecodeStreamEvent:
    """Tests for decode_stream_event function."""

    def test_decode_valid_event(self) -> None:
        """Decode returns StreamEvent from valid bytes."""
        data = b'{"event_type": "agent_status", "data": {"id": "a1"}, "timestamp": "2026-01-03T01:00:00+00:00"}\n'
        event = decode_stream_event(data)
        
        assert isinstance(event, StreamEvent)
        assert event.event_type == "agent_status"
        assert event.data == {"id": "a1"}

    def test_decode_strips_whitespace(self) -> None:
        """Decode handles trailing whitespace/newlines."""
        data = b'{"event_type": "heartbeat", "data": {}, "timestamp": "2026-01-03T01:00:00+00:00"}  \n  \n'
        event = decode_stream_event(data)
        
        assert event.event_type == "heartbeat"

    def test_decode_invalid_json_raises(self) -> None:
        """Decode raises StreamProtocolError on invalid JSON."""
        data = b"not valid json"
        
        with pytest.raises(StreamProtocolError, match="Failed to decode"):
            decode_stream_event(data)

    def test_decode_invalid_utf8_raises(self) -> None:
        """Decode raises StreamProtocolError on invalid UTF-8."""
        data = b"\xff\xfe\x00\x01"  # Invalid UTF-8 bytes
        
        with pytest.raises(StreamProtocolError, match="Failed to decode"):
            decode_stream_event(data)

    def test_decode_missing_required_field_raises(self) -> None:
        """Decode raises StreamProtocolError when required field missing."""
        data = b'{"data": {}, "timestamp": "2026-01-03T01:00:00+00:00"}'  # Missing event_type
        
        with pytest.raises(StreamProtocolError, match="Invalid stream event structure"):
            decode_stream_event(data)

    def test_encode_decode_roundtrip(self) -> None:
        """Event survives encode/decode roundtrip."""
        original = StreamEvent(
            event_type="finding",
            data={"severity": "HIGH", "description": "SQL Injection"},
            timestamp="2026-01-03T01:00:00+00:00",
        )
        encoded = encode_stream_event(original)
        decoded = decode_stream_event(encoded)
        
        assert decoded.event_type == original.event_type
        assert decoded.data == original.data
        assert decoded.timestamp == original.timestamp

    def test_decode_invalid_event_type_raises(self) -> None:
        """Decode raises StreamProtocolError when event_type is invalid."""
        data = b'{"event_type": "invalid_type", "data": {}, "timestamp": "2026-01-03T01:00:00+00:00"}'
        
        with pytest.raises(StreamProtocolError, match="validation failed"):
            decode_stream_event(data)
