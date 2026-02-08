"""Unit tests for C2 message protocol.

Tests follow TDD methodology - written before implementation.
Per Story 12.2: C2 Message Protocol (FR24)
"""

import json
import pytest
from datetime import datetime, timezone


class TestC2MessageTypeEnum:
    """Tests for C2MessageType enum (AC: #2)."""

    def test_c2_message_type_command_exists(self):
        """Test COMMAND type is defined."""
        from cyberred.c2.protocol import C2MessageType
        
        assert C2MessageType.COMMAND.value == "command"

    def test_c2_message_type_result_exists(self):
        """Test RESULT type is defined."""
        from cyberred.c2.protocol import C2MessageType
        
        assert C2MessageType.RESULT.value == "result"

    def test_c2_message_type_heartbeat_exists(self):
        """Test HEARTBEAT type is defined."""
        from cyberred.c2.protocol import C2MessageType
        
        assert C2MessageType.HEARTBEAT.value == "heartbeat"

    def test_c2_message_type_only_three_types(self):
        """Test only three message types exist."""
        from cyberred.c2.protocol import C2MessageType
        
        assert len(C2MessageType) == 3


class TestC2MessageDataclass:
    """Tests for C2Message dataclass (AC: #1)."""

    def test_c2_message_has_type_field(self):
        """Test C2Message has type field."""
        from cyberred.c2.protocol import C2Message, C2MessageType
        
        msg = C2Message(
            type=C2MessageType.COMMAND,
            id="test-id",
            timestamp="2026-02-02T00:00:00Z",
            payload={"test": "data"},
            signature="abc123",
        )
        assert msg.type == C2MessageType.COMMAND

    def test_c2_message_has_id_field(self):
        """Test C2Message has id field."""
        from cyberred.c2.protocol import C2Message, C2MessageType
        
        msg = C2Message(
            type=C2MessageType.COMMAND,
            id="unique-msg-id",
            timestamp="2026-02-02T00:00:00Z",
            payload={},
            signature="sig",
        )
        assert msg.id == "unique-msg-id"

    def test_c2_message_has_timestamp_field(self):
        """Test C2Message has timestamp field."""
        from cyberred.c2.protocol import C2Message, C2MessageType
        
        msg = C2Message(
            type=C2MessageType.HEARTBEAT,
            id="id",
            timestamp="2026-02-02T12:30:00+00:00",
            payload={},
            signature="sig",
        )
        assert msg.timestamp == "2026-02-02T12:30:00+00:00"

    def test_c2_message_has_payload_field(self):
        """Test C2Message has payload field."""
        from cyberred.c2.protocol import C2Message, C2MessageType
        
        payload = {"command": "exec", "args": {"tool": "nmap"}}
        msg = C2Message(
            type=C2MessageType.COMMAND,
            id="id",
            timestamp="2026-02-02T00:00:00Z",
            payload=payload,
            signature="sig",
        )
        assert msg.payload == payload

    def test_c2_message_has_signature_field(self):
        """Test C2Message has signature field."""
        from cyberred.c2.protocol import C2Message, C2MessageType
        
        msg = C2Message(
            type=C2MessageType.RESULT,
            id="id",
            timestamp="2026-02-02T00:00:00Z",
            payload={},
            signature="hmac-sha256-signature",
        )
        assert msg.signature == "hmac-sha256-signature"


class TestSignPayload:
    """Tests for sign_payload() function (AC: #3)."""

    def test_sign_payload_returns_string(self):
        """Test sign_payload returns hex string."""
        from cyberred.c2.protocol import sign_payload
        
        payload = {"test": "data"}
        secret = b"test_secret"
        
        signature = sign_payload(payload, secret)
        
        assert isinstance(signature, str)
        # HMAC-SHA256 produces 64 hex chars
        assert len(signature) == 64

    def test_sign_payload_deterministic(self):
        """Test same payload + secret produces same signature."""
        from cyberred.c2.protocol import sign_payload
        
        payload = {"key": "value", "number": 42}
        secret = b"consistent_secret"
        
        sig1 = sign_payload(payload, secret)
        sig2 = sign_payload(payload, secret)
        
        assert sig1 == sig2

    def test_sign_payload_different_secrets_differ(self):
        """Test different secrets produce different signatures."""
        from cyberred.c2.protocol import sign_payload
        
        payload = {"data": "test"}
        secret1 = b"secret_one"
        secret2 = b"secret_two"
        
        sig1 = sign_payload(payload, secret1)
        sig2 = sign_payload(payload, secret2)
        
        assert sig1 != sig2

    def test_sign_payload_different_payloads_differ(self):
        """Test different payloads produce different signatures."""
        from cyberred.c2.protocol import sign_payload
        
        secret = b"same_secret"
        payload1 = {"a": 1}
        payload2 = {"a": 2}
        
        sig1 = sign_payload(payload1, secret)
        sig2 = sign_payload(payload2, secret)
        
        assert sig1 != sig2

    def test_sign_payload_key_order_independent(self):
        """Test payload key order doesn't affect signature (sort_keys=True)."""
        from cyberred.c2.protocol import sign_payload
        
        secret = b"test_secret"
        # Different key insertion order, same content
        payload1 = {"b": 2, "a": 1}
        payload2 = {"a": 1, "b": 2}
        
        sig1 = sign_payload(payload1, secret)
        sig2 = sign_payload(payload2, secret)
        
        assert sig1 == sig2

    def test_sign_payload_rejects_none_payload(self):
        """Test sign_payload raises ValueError for None payload."""
        from cyberred.c2.protocol import sign_payload
        
        with pytest.raises(ValueError, match="Payload must be a dict"):
            sign_payload(None, b"secret")

    def test_sign_payload_rejects_non_dict_payload(self):
        """Test sign_payload raises ValueError for non-dict payload."""
        from cyberred.c2.protocol import sign_payload
        
        with pytest.raises(ValueError, match="Payload must be a dict"):
            sign_payload("not a dict", b"secret")
        
        with pytest.raises(ValueError, match="Payload must be a dict"):
            sign_payload([1, 2, 3], b"secret")

    def test_sign_payload_rejects_empty_secret(self):
        """Test sign_payload raises ValueError for empty secret."""
        from cyberred.c2.protocol import sign_payload
        
        with pytest.raises(ValueError, match="Secret cannot be empty"):
            sign_payload({"test": "data"}, b"")


class TestVerifySignature:
    """Tests for verify_signature() function (AC: #3, #4)."""

    def test_verify_signature_valid_returns_true(self):
        """Test verify_signature returns True for valid signature."""
        from cyberred.c2.protocol import C2Message, C2MessageType, sign_payload, verify_signature
        
        secret = b"test_secret"
        payload = {"command": "test"}
        signature = sign_payload(payload, secret)
        
        msg = C2Message(
            type=C2MessageType.COMMAND,
            id="test-id",
            timestamp="2026-02-02T00:00:00Z",
            payload=payload,
            signature=signature,
        )
        
        assert verify_signature(msg, secret) is True

    def test_verify_signature_invalid_returns_false(self):
        """Test verify_signature returns False for invalid signature."""
        from cyberred.c2.protocol import C2Message, C2MessageType, verify_signature
        
        secret = b"test_secret"
        
        msg = C2Message(
            type=C2MessageType.COMMAND,
            id="test-id",
            timestamp="2026-02-02T00:00:00Z",
            payload={"command": "test"},
            signature="invalid_signature_not_hmac",
        )
        
        assert verify_signature(msg, secret) is False

    def test_verify_signature_tampered_payload_returns_false(self):
        """Test verify_signature returns False when payload is tampered."""
        from cyberred.c2.protocol import C2Message, C2MessageType, sign_payload, verify_signature
        
        secret = b"test_secret"
        original_payload = {"command": "safe_command"}
        signature = sign_payload(original_payload, secret)
        
        # Create message with tampered payload but original signature
        tampered_payload = {"command": "malicious_command"}
        msg = C2Message(
            type=C2MessageType.COMMAND,
            id="test-id",
            timestamp="2026-02-02T00:00:00Z",
            payload=tampered_payload,
            signature=signature,
        )
        
        assert verify_signature(msg, secret) is False

    def test_verify_signature_wrong_secret_returns_false(self):
        """Test verify_signature returns False with wrong secret."""
        from cyberred.c2.protocol import C2Message, C2MessageType, sign_payload, verify_signature
        
        secret1 = b"correct_secret"
        secret2 = b"wrong_secret"
        payload = {"data": "test"}
        signature = sign_payload(payload, secret1)
        
        msg = C2Message(
            type=C2MessageType.COMMAND,
            id="test-id",
            timestamp="2026-02-02T00:00:00Z",
            payload=payload,
            signature=signature,
        )
        
        assert verify_signature(msg, secret2) is False


class TestC2MessageSerialization:
    """Tests for C2Message serialization (AC: #1)."""

    def test_to_json_returns_valid_json(self):
        """Test to_json returns valid JSON string."""
        from cyberred.c2.protocol import C2Message, C2MessageType
        
        msg = C2Message(
            type=C2MessageType.COMMAND,
            id="msg-123",
            timestamp="2026-02-02T00:00:00Z",
            payload={"test": "data"},
            signature="sig123",
        )
        
        json_str = msg.to_json()
        
        # Should be valid JSON
        data = json.loads(json_str)
        assert data["type"] == "command"
        assert data["id"] == "msg-123"
        assert data["timestamp"] == "2026-02-02T00:00:00Z"
        assert data["payload"] == {"test": "data"}
        assert data["signature"] == "sig123"

    def test_to_json_type_is_string_value(self):
        """Test to_json converts enum to string value."""
        from cyberred.c2.protocol import C2Message, C2MessageType
        
        msg = C2Message(
            type=C2MessageType.HEARTBEAT,
            id="id",
            timestamp="ts",
            payload={},
            signature="sig",
        )
        
        data = json.loads(msg.to_json())
        assert data["type"] == "heartbeat"
        assert isinstance(data["type"], str)

    def test_from_json_valid_command(self):
        """Test from_json parses valid command message."""
        from cyberred.c2.protocol import C2Message, C2MessageType
        
        json_str = json.dumps({
            "type": "command",
            "id": "cmd-456",
            "timestamp": "2026-02-02T12:00:00Z",
            "payload": {"command": "exec", "args": {}},
            "signature": "valid_sig",
        })
        
        msg = C2Message.from_json(json_str)
        
        assert msg.type == C2MessageType.COMMAND
        assert msg.id == "cmd-456"
        assert msg.timestamp == "2026-02-02T12:00:00Z"
        assert msg.payload == {"command": "exec", "args": {}}
        assert msg.signature == "valid_sig"

    def test_from_json_valid_result(self):
        """Test from_json parses valid result message."""
        from cyberred.c2.protocol import C2Message, C2MessageType
        
        json_str = json.dumps({
            "type": "result",
            "id": "res-789",
            "timestamp": "2026-02-02T12:00:00Z",
            "payload": {"success": True, "output": "done"},
            "signature": "sig",
        })
        
        msg = C2Message.from_json(json_str)
        
        assert msg.type == C2MessageType.RESULT

    def test_from_json_valid_heartbeat(self):
        """Test from_json parses valid heartbeat message."""
        from cyberred.c2.protocol import C2Message, C2MessageType
        
        json_str = json.dumps({
            "type": "heartbeat",
            "id": "hb-001",
            "timestamp": "2026-02-02T12:00:00Z",
            "payload": {"status": "healthy"},
            "signature": "sig",
        })
        
        msg = C2Message.from_json(json_str)
        
        assert msg.type == C2MessageType.HEARTBEAT

    def test_from_json_invalid_json_raises(self):
        """Test from_json raises ValueError for invalid JSON."""
        from cyberred.c2.protocol import C2Message
        
        with pytest.raises(ValueError, match="Invalid JSON"):
            C2Message.from_json("not valid json {{{")

    def test_from_json_missing_fields_raises(self):
        """Test from_json raises ValueError for missing fields."""
        from cyberred.c2.protocol import C2Message
        
        # Missing 'signature' field
        json_str = json.dumps({
            "type": "command",
            "id": "id",
            "timestamp": "ts",
            "payload": {},
        })
        
        with pytest.raises(ValueError, match="Missing required fields"):
            C2Message.from_json(json_str)

    def test_from_json_invalid_type_raises(self):
        """Test from_json raises ValueError for invalid message type."""
        from cyberred.c2.protocol import C2Message
        
        json_str = json.dumps({
            "type": "invalid_type",
            "id": "id",
            "timestamp": "ts",
            "payload": {},
            "signature": "sig",
        })
        
        with pytest.raises(ValueError, match="Invalid message type"):
            C2Message.from_json(json_str)

    def test_roundtrip_serialization(self):
        """Test to_json -> from_json roundtrip preserves data."""
        from cyberred.c2.protocol import C2Message, C2MessageType
        
        original = C2Message(
            type=C2MessageType.RESULT,
            id="roundtrip-test",
            timestamp="2026-02-02T15:30:00+00:00",
            payload={"nested": {"data": [1, 2, 3]}},
            signature="original_signature",
        )
        
        json_str = original.to_json()
        restored = C2Message.from_json(json_str)
        
        assert restored.type == original.type
        assert restored.id == original.id
        assert restored.timestamp == original.timestamp
        assert restored.payload == original.payload
        assert restored.signature == original.signature


class TestCreateCommandMessage:
    """Tests for create_command_message() factory (AC: #1, #2)."""

    def test_create_command_message_type(self):
        """Test create_command_message creates COMMAND type."""
        from cyberred.c2.protocol import create_command_message, C2MessageType
        
        msg = create_command_message("exec", {"tool": "nmap"}, b"secret")
        
        assert msg.type == C2MessageType.COMMAND

    def test_create_command_message_payload_structure(self):
        """Test create_command_message creates correct payload structure."""
        from cyberred.c2.protocol import create_command_message
        
        msg = create_command_message("scan", {"target": "192.168.1.1"}, b"secret")
        
        assert msg.payload["command"] == "scan"
        assert msg.payload["args"] == {"target": "192.168.1.1"}

    def test_create_command_message_has_uuid_id(self):
        """Test create_command_message generates UUID id."""
        from cyberred.c2.protocol import create_command_message
        import uuid
        
        msg = create_command_message("test", {}, b"secret")
        
        # Should be valid UUID
        uuid.UUID(msg.id)  # Raises if invalid

    def test_create_command_message_custom_id(self):
        """Test create_command_message accepts custom id."""
        from cyberred.c2.protocol import create_command_message
        
        msg = create_command_message("test", {}, b"secret", message_id="custom-id-123")
        
        assert msg.id == "custom-id-123"

    def test_create_command_message_has_iso_timestamp(self):
        """Test create_command_message creates ISO8601 timestamp."""
        from cyberred.c2.protocol import create_command_message
        from datetime import datetime
        
        msg = create_command_message("test", {}, b"secret")
        
        # Should be parseable ISO8601
        datetime.fromisoformat(msg.timestamp.replace("Z", "+00:00"))

    def test_create_command_message_has_valid_signature(self):
        """Test create_command_message creates valid signature."""
        from cyberred.c2.protocol import create_command_message, verify_signature
        
        secret = b"test_secret"
        msg = create_command_message("exec", {"arg": "value"}, secret)
        
        assert verify_signature(msg, secret) is True


class TestCreateResultMessage:
    """Tests for create_result_message() factory (AC: #1, #2)."""

    def test_create_result_message_type(self):
        """Test create_result_message creates RESULT type."""
        from cyberred.c2.protocol import create_result_message, C2MessageType
        
        msg = create_result_message("cmd-123", True, "output", b"secret")
        
        assert msg.type == C2MessageType.RESULT

    def test_create_result_message_payload_structure(self):
        """Test create_result_message creates correct payload structure."""
        from cyberred.c2.protocol import create_result_message
        
        msg = create_result_message("cmd-456", False, {"error": "failed"}, b"secret")
        
        assert msg.payload["command_id"] == "cmd-456"
        assert msg.payload["success"] is False
        assert msg.payload["output"] == {"error": "failed"}

    def test_create_result_message_has_valid_signature(self):
        """Test create_result_message creates valid signature."""
        from cyberred.c2.protocol import create_result_message, verify_signature
        
        secret = b"test_secret"
        msg = create_result_message("cmd-id", True, "done", secret)
        
        assert verify_signature(msg, secret) is True

    def test_create_result_message_custom_id(self):
        """Test create_result_message accepts custom id."""
        from cyberred.c2.protocol import create_result_message
        
        msg = create_result_message("cmd", True, None, b"secret", message_id="res-custom")
        
        assert msg.id == "res-custom"


class TestCreateHeartbeatMessage:
    """Tests for create_heartbeat_message() factory (AC: #1, #2)."""

    def test_create_heartbeat_message_type(self):
        """Test create_heartbeat_message creates HEARTBEAT type."""
        from cyberred.c2.protocol import create_heartbeat_message, C2MessageType
        
        msg = create_heartbeat_message("dropbox-01", "healthy", b"secret")
        
        assert msg.type == C2MessageType.HEARTBEAT

    def test_create_heartbeat_message_payload_structure(self):
        """Test create_heartbeat_message creates correct payload structure."""
        from cyberred.c2.protocol import create_heartbeat_message
        
        msg = create_heartbeat_message("db-alpha", "degraded", b"secret")
        
        assert msg.payload["drop_box_id"] == "db-alpha"
        assert msg.payload["status"] == "degraded"

    def test_create_heartbeat_message_has_valid_signature(self):
        """Test create_heartbeat_message creates valid signature."""
        from cyberred.c2.protocol import create_heartbeat_message, verify_signature
        
        secret = b"test_secret"
        msg = create_heartbeat_message("dropbox", "healthy", secret)
        
        assert verify_signature(msg, secret) is True

    def test_create_heartbeat_message_custom_id(self):
        """Test create_heartbeat_message accepts custom id."""
        from cyberred.c2.protocol import create_heartbeat_message
        
        msg = create_heartbeat_message("db", "ok", b"secret", message_id="hb-custom")
        
        assert msg.id == "hb-custom"


class TestValidateAndParseMessage:
    """Tests for validate_and_parse_message() function (AC: #4)."""

    def test_validate_valid_message_returns_message(self):
        """Test validate_and_parse_message returns message for valid input."""
        from cyberred.c2.protocol import (
            validate_and_parse_message,
            create_command_message,
            C2MessageType,
        )
        
        secret = b"test_secret"
        original = create_command_message("test", {"arg": 1}, secret)
        json_str = original.to_json()
        
        msg, error = validate_and_parse_message(json_str, secret)
        
        assert msg is not None
        assert error is None
        assert msg.type == C2MessageType.COMMAND
        assert msg.id == original.id

    def test_validate_invalid_json_returns_error(self):
        """Test validate_and_parse_message returns error for invalid JSON."""
        from cyberred.c2.protocol import validate_and_parse_message
        
        msg, error = validate_and_parse_message("not json {{{", b"secret")
        
        assert msg is None
        assert error is not None
        assert "Invalid JSON" in error

    def test_validate_missing_fields_returns_error(self):
        """Test validate_and_parse_message returns error for missing fields."""
        from cyberred.c2.protocol import validate_and_parse_message
        import json
        
        json_str = json.dumps({"type": "command", "id": "id"})  # Missing fields
        
        msg, error = validate_and_parse_message(json_str, b"secret")
        
        assert msg is None
        assert error is not None
        assert "Missing required fields" in error

    def test_validate_invalid_signature_returns_error(self):
        """Test validate_and_parse_message returns error for invalid signature."""
        from cyberred.c2.protocol import validate_and_parse_message
        import json
        
        json_str = json.dumps({
            "type": "command",
            "id": "msg-id",
            "timestamp": "2026-02-02T00:00:00Z",
            "payload": {"command": "test"},
            "signature": "wrong_signature",
        })
        
        msg, error = validate_and_parse_message(json_str, b"correct_secret")
        
        assert msg is None
        assert error == "invalid_signature"

    def test_validate_tampered_message_returns_error(self):
        """Test validate_and_parse_message detects tampered payload."""
        from cyberred.c2.protocol import validate_and_parse_message, sign_payload
        import json
        
        secret = b"test_secret"
        original_payload = {"command": "safe"}
        signature = sign_payload(original_payload, secret)
        
        # Tamper with payload
        tampered_json = json.dumps({
            "type": "command",
            "id": "msg-id",
            "timestamp": "2026-02-02T00:00:00Z",
            "payload": {"command": "malicious"},  # Tampered!
            "signature": signature,  # Original signature
        })
        
        msg, error = validate_and_parse_message(tampered_json, secret)
        
        assert msg is None
        assert error == "invalid_signature"


class TestRejectionLogging:
    """Tests for rejection logging (AC: #4)."""

    def test_invalid_json_logs_rejection(self):
        """Test invalid JSON rejection is logged."""
        from cyberred.c2.protocol import validate_and_parse_message
        import structlog
        from structlog.testing import capture_logs
        
        with capture_logs() as cap_logs:
            validate_and_parse_message("bad json", b"secret")
        
        assert any(log.get("event") == "c2_message_rejected" for log in cap_logs)

    def test_invalid_signature_logs_rejection_with_id(self):
        """Test invalid signature rejection logs message ID."""
        from cyberred.c2.protocol import validate_and_parse_message
        import json
        from structlog.testing import capture_logs
        
        json_str = json.dumps({
            "type": "command",
            "id": "tracked-msg-id",
            "timestamp": "2026-02-02T00:00:00Z",
            "payload": {},
            "signature": "bad_sig",
        })
        
        with capture_logs() as cap_logs:
            validate_and_parse_message(json_str, b"secret")
        
        # Should log with message_id
        rejection_logs = [log for log in cap_logs if log.get("event") == "c2_message_rejected"]
        assert len(rejection_logs) == 1
        assert rejection_logs[0].get("message_id") == "tracked-msg-id"
