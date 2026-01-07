"""Unit tests for IPC protocol module.

Tests cover:
- IPCCommand StrEnum members and validation
- IPCRequest serialization/deserialization
- IPCResponse serialization/deserialization and factory methods
- Wire protocol encoding/decoding
- Error handling for malformed messages
"""

import json
import uuid

import pytest

from cyberred.core.exceptions import IPCProtocolError
from cyberred.daemon.ipc import (
    IPCCommand,
    IPCRequest,
    IPCResponse,
    build_request,
    decode_message,
    encode_message,
)


class TestIPCCommand:
    """Tests for IPCCommand StrEnum."""

    def test_enum_members_exist(self) -> None:
        """Test that all expected command members exist."""
        assert IPCCommand.SESSIONS_LIST == "sessions.list"
        assert IPCCommand.ENGAGEMENT_START == "engagement.start"
        assert IPCCommand.ENGAGEMENT_ATTACH == "engagement.attach"
        assert IPCCommand.ENGAGEMENT_DETACH == "engagement.detach"
        assert IPCCommand.ENGAGEMENT_PAUSE == "engagement.pause"
        assert IPCCommand.ENGAGEMENT_RESUME == "engagement.resume"
        assert IPCCommand.ENGAGEMENT_STOP == "engagement.stop"
        assert IPCCommand.DAEMON_STOP == "daemon.stop"

    def test_enum_count(self) -> None:
        """Test that exactly 8 commands are defined."""
        assert len(IPCCommand) == 8

    def test_enum_iteration(self) -> None:
        """Test that enum can be iterated."""
        commands = list(IPCCommand)
        assert len(commands) == 8
        assert IPCCommand.SESSIONS_LIST in commands
        assert IPCCommand.DAEMON_STOP in commands

    def test_valid_command_lookup(self) -> None:
        """Test valid command string lookup via enum constructor."""
        cmd = IPCCommand("sessions.list")
        assert cmd == IPCCommand.SESSIONS_LIST

    def test_invalid_command_raises_valueerror(self) -> None:
        """Test invalid command string raises ValueError."""
        with pytest.raises(ValueError):
            IPCCommand("invalid.command")

    def test_command_string_equality(self) -> None:
        """Test that enum values equal their string representations."""
        assert IPCCommand.SESSIONS_LIST == "sessions.list"
        assert str(IPCCommand.SESSIONS_LIST) == "sessions.list"


class TestIPCRequest:
    """Tests for IPCRequest dataclass."""

    def test_serialization_roundtrip(self) -> None:
        """Test JSON serialization/deserialization preserves data."""
        req = IPCRequest(
            command="sessions.list",
            params={},
            request_id="test-uuid-123",
        )
        json_str = req.to_json()
        restored = IPCRequest.from_json(json_str)

        assert restored.command == req.command
        assert restored.params == req.params
        assert restored.request_id == req.request_id

    def test_to_json_format(self) -> None:
        """Test JSON output has correct structure."""
        req = IPCRequest(
            command="engagement.start",
            params={"config_path": "/path/to/config.yaml"},
            request_id="abc-123",
        )
        parsed = json.loads(req.to_json())

        assert parsed["command"] == "engagement.start"
        assert parsed["params"]["config_path"] == "/path/to/config.yaml"
        assert parsed["request_id"] == "abc-123"

    def test_from_json_with_complex_params(self) -> None:
        """Test deserialization with nested params."""
        json_str = json.dumps({
            "command": "engagement.start",
            "params": {
                "config": {"scope": ["10.0.0.0/8"], "timeout": 3600},
                "options": ["verbose"],
            },
            "request_id": "nested-test",
        })
        req = IPCRequest.from_json(json_str)

        assert req.params["config"]["timeout"] == 3600
        assert "verbose" in req.params["options"]

    def test_forward_compatibility(self) -> None:
        """Test that unknown fields are ignored (forward compatibility)."""
        json_str = json.dumps({
            "command": "sessions.list",
            "params": {},
            "request_id": "compat-test",
            "future_field": "should be ignored"
        })
        req = IPCRequest.from_json(json_str)

        assert req.command == "sessions.list"
        assert req.request_id == "compat-test"
        # future_field should be filtered out, preventing TypeError

    def test_invalid_json_type_raises_typeerror(self) -> None:
        """Test that non-dict JSON raises TypeError."""
        # List instead of dict
        with pytest.raises(TypeError, match="JSON data must be a dictionary object"):
            IPCRequest.from_json("[]")
        
        # String instead of dict
        with pytest.raises(TypeError, match="JSON data must be a dictionary object"):
            IPCRequest.from_json('"string"')


    def test_empty_command_raises_valueerror(self) -> None:
        """Test that empty command raises ValueError."""
        with pytest.raises(ValueError, match="command must not be empty"):
            IPCRequest(command="", params={}, request_id="test")

    def test_empty_request_id_raises_valueerror(self) -> None:
        """Test that empty request_id raises ValueError."""
        with pytest.raises(ValueError, match="request_id must not be empty"):
            IPCRequest(command="sessions.list", params={}, request_id="")

    def test_equality(self) -> None:
        """Test dataclass equality comparison."""
        req1 = IPCRequest(command="sessions.list", params={}, request_id="abc")
        req2 = IPCRequest(command="sessions.list", params={}, request_id="abc")
        assert req1 == req2


class TestIPCResponse:
    """Tests for IPCResponse dataclass."""

    def test_ok_factory(self) -> None:
        """Test IPCResponse.create_ok() factory method."""
        resp = IPCResponse.create_ok({"id": "eng-1", "state": "RUNNING"}, "req-123")

        assert resp.status == "ok"
        assert resp.data == {"id": "eng-1", "state": "RUNNING"}
        assert resp.error is None
        assert resp.request_id == "req-123"

    def test_error_factory(self) -> None:
        """Test IPCResponse.create_error() factory method."""
        resp = IPCResponse.create_error("Engagement not found", "req-456")

        assert resp.status == "error"
        assert resp.data is None
        assert resp.error == "Engagement not found"
        assert resp.request_id == "req-456"

    def test_serialization_roundtrip(self) -> None:
        """Test JSON serialization/deserialization preserves data."""
        resp = IPCResponse(
            status="ok",
            data={"engagements": [{"id": "eng-1"}, {"id": "eng-2"}]},
            error=None,
            request_id="test-uuid",
        )
        json_str = resp.to_json()
        restored = IPCResponse.from_json(json_str)

        assert restored.status == resp.status
        assert restored.data == resp.data
        assert restored.error == resp.error
        assert restored.request_id == resp.request_id

    def test_to_json_format(self) -> None:
        """Test JSON output has correct structure."""
        resp = IPCResponse.create_ok({"count": 5}, "xyz-789")
        parsed = json.loads(resp.to_json())

        assert parsed["status"] == "ok"
        assert parsed["data"]["count"] == 5
        assert parsed["error"] is None
        assert parsed["request_id"] == "xyz-789"

    def test_invalid_status_raises_valueerror(self) -> None:
        """Test that invalid status raises ValueError."""
        with pytest.raises(ValueError, match="must be 'ok' or 'error'"):
            IPCResponse(status="invalid", data=None, error=None, request_id="test")

    def test_forward_compatibility(self) -> None:
        """Test that unknown fields are ignored (forward compatibility)."""
        json_str = json.dumps({
            "status": "ok",
            "request_id": "compat-resp-test",
            "data": {},
            "error": None,
            "new_v2_field": 123
        })
        resp = IPCResponse.from_json(json_str)

        assert resp.status == "ok"
        assert resp.request_id == "compat-resp-test"
        # new_v2_field should be filtered out

    def test_invalid_json_type_raises_typeerror(self) -> None:
        """Test that non-dict JSON raises TypeError."""
        with pytest.raises(TypeError, match="JSON data must be a dictionary object"):
            IPCResponse.from_json("123")

    def test_empty_request_id_raises_valueerror(self) -> None:
        """Test that empty request_id raises ValueError."""
        with pytest.raises(ValueError, match="request_id must not be empty"):
            IPCResponse(status="ok", data={}, error=None, request_id="")


class TestBuildRequest:
    """Tests for build_request helper function."""

    def test_builds_request_with_valid_command(self) -> None:
        """Test building request with valid command."""
        req = build_request(IPCCommand.SESSIONS_LIST)

        assert req.command == "sessions.list"
        assert req.params == {}
        # request_id should be valid UUID
        uuid.UUID(req.request_id)

    def test_builds_request_with_params(self) -> None:
        """Test building request with keyword parameters."""
        req = build_request(
            IPCCommand.ENGAGEMENT_START,
            config_path="/path/to/config.yaml",
            force=True,
        )

        assert req.command == "engagement.start"
        assert req.params["config_path"] == "/path/to/config.yaml"
        assert req.params["force"] is True

    def test_invalid_command_raises_valueerror(self) -> None:
        """Test that invalid command raises ValueError."""
        with pytest.raises(ValueError, match="Invalid IPC command"):
            build_request("invalid.command")

    def test_accepts_command_string(self) -> None:
        """Test that string command is accepted."""
        req = build_request("sessions.list")
        assert req.command == "sessions.list"

    def test_each_call_generates_unique_request_id(self) -> None:
        """Test that each call generates a unique request_id."""
        req1 = build_request(IPCCommand.SESSIONS_LIST)
        req2 = build_request(IPCCommand.SESSIONS_LIST)
        assert req1.request_id != req2.request_id


class TestWireProtocol:
    """Tests for encode_message and decode_message functions."""

    def test_encode_request(self) -> None:
        """Test encoding request to wire format."""
        req = IPCRequest(
            command="sessions.list",
            params={},
            request_id="test-123",
        )
        encoded = encode_message(req)

        assert isinstance(encoded, bytes)
        assert encoded.endswith(b"\n")
        assert b"sessions.list" in encoded

    def test_encode_response(self) -> None:
        """Test encoding response to wire format."""
        resp = IPCResponse.create_ok({"count": 0}, "test-456")
        encoded = encode_message(resp)

        assert isinstance(encoded, bytes)
        assert encoded.endswith(b"\n")
        assert b'"status": "ok"' in encoded or b'"status":"ok"' in encoded

    def test_decode_request(self) -> None:
        """Test decoding request from wire format."""
        wire_data = b'{"command": "sessions.list", "params": {}, "request_id": "abc"}\n'
        decoded = decode_message(wire_data)

        assert isinstance(decoded, IPCRequest)
        assert decoded.command == "sessions.list"
        assert decoded.request_id == "abc"

    def test_decode_response(self) -> None:
        """Test decoding response from wire format."""
        wire_data = b'{"status": "ok", "data": {"id": "eng-1"}, "error": null, "request_id": "xyz"}\n'
        decoded = decode_message(wire_data)

        assert isinstance(decoded, IPCResponse)
        assert decoded.status == "ok"
        assert decoded.data == {"id": "eng-1"}

    def test_encode_decode_roundtrip_request(self) -> None:
        """Test full encode/decode roundtrip for request."""
        original = build_request(IPCCommand.ENGAGEMENT_PAUSE, id="eng-1")
        encoded = encode_message(original)
        decoded = decode_message(encoded)

        assert isinstance(decoded, IPCRequest)
        assert decoded.command == original.command
        assert decoded.params == original.params
        assert decoded.request_id == original.request_id

    def test_encode_decode_roundtrip_response(self) -> None:
        """Test full encode/decode roundtrip for response."""
        original = IPCResponse.create_ok({"state": "PAUSED"}, "req-001")
        encoded = encode_message(original)
        decoded = decode_message(encoded)

        assert isinstance(decoded, IPCResponse)
        assert decoded.status == original.status
        assert decoded.data == original.data
        assert decoded.request_id == original.request_id

    def test_malformed_json_raises_ipc_protocol_error(self) -> None:
        """Test that malformed JSON raises IPCProtocolError."""
        with pytest.raises(IPCProtocolError):
            decode_message(b"not valid json")

    def test_invalid_utf8_raises_ipc_protocol_error(self) -> None:
        """Test that invalid UTF-8 raises IPCProtocolError."""
        with pytest.raises(IPCProtocolError):
            decode_message(b"\x80\x81\x82")

    def test_message_too_large_raises_ipc_protocol_error(self) -> None:
        """Test that messages exceeding size limit raise error."""
        from cyberred.daemon.ipc import MAX_MESSAGE_SIZE
        
        # Create a message slightly larger than max allowed
        large_data = b" " * (MAX_MESSAGE_SIZE + 1)
        
        with pytest.raises(IPCProtocolError, match="exceeds limit"):
            decode_message(large_data)

    def test_missing_fields_raises_ipc_protocol_error(self) -> None:
        """Test that missing required fields raises IPCProtocolError."""
        # Missing request_id for request
        with pytest.raises(IPCProtocolError):
            decode_message(b'{"command": "sessions.list", "params": {}}')

    def test_invalid_response_status_raises_ipc_protocol_error(self) -> None:
        """Test that invalid response status raises IPCProtocolError."""
        with pytest.raises(IPCProtocolError):
            decode_message(b'{"status": "invalid", "data": null, "error": null, "request_id": "x"}')


class TestRequestIdCorrelation:
    """Tests for request/response ID correlation."""

    def test_response_ok_preserves_request_id(self) -> None:
        """Test that ok response preserves request_id."""
        request_id = str(uuid.uuid4())
        resp = IPCResponse.create_ok({"result": "success"}, request_id)
        assert resp.request_id == request_id

    def test_response_error_preserves_request_id(self) -> None:
        """Test that error response preserves request_id."""
        request_id = str(uuid.uuid4())
        resp = IPCResponse.create_error("Something failed", request_id)
        assert resp.request_id == request_id

    def test_roundtrip_preserves_request_id(self) -> None:
        """Test that encode/decode roundtrip preserves request_id."""
        original_id = "correlation-test-12345"
        req = IPCRequest(
            command="engagement.stop",
            params={"id": "eng-1"},
            request_id=original_id,
        )

        encoded = encode_message(req)
        decoded = decode_message(encoded)

        assert decoded.request_id == original_id
