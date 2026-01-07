"""Unit Tests for Core Data Models.

Tests for Finding, AgentAction, and ToolResult dataclasses
ensuring proper instantiation, JSON serialization, and validation.
"""

import json
import pytest
import uuid
from typing import Optional

from cyberred.core.models import Finding, AgentAction, ToolResult


# Valid UUIDs for testing
VALID_UUID_1 = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
VALID_UUID_2 = "550e8400-e29b-41d4-a716-446655440000"
VALID_UUID_3 = str(uuid.uuid4())


class TestFinding:
    """Tests for Finding dataclass including new validation logic."""

    def test_finding_instantiation_all_fields(self) -> None:
        """Finding can be instantiated with all 10 required fields and valid data."""
        finding = Finding(
            id=VALID_UUID_1,
            type="sqli",
            severity="critical",
            target="192.168.1.100",
            evidence="Parameter 'id' is vulnerable...",
            agent_id=VALID_UUID_2,
            timestamp="2025-12-27T23:30:00Z",
            tool="sqlmap",
            topic="findings:a1b2c3:sqli",
            signature="a3f2b1c4d5e6f7890abcdef",
        )

        assert finding.id == VALID_UUID_1
        assert finding.target == "192.168.1.100"

    def test_finding_validation_invalid_uuid(self) -> None:
        """Finding raises ValueError for invalid UUID."""
        with pytest.raises(ValueError, match="Invalid UUID"):
            Finding(
                id="not-a-uuid",
                type="test",
                severity="info",
                target="127.0.0.1",
                evidence="N/A",
                agent_id=VALID_UUID_2, 
                timestamp="2025-12-31T00:00:00Z",
                tool="tool",
                topic="topic",
                signature="sig",
            )

    def test_finding_validation_invalid_timestamp(self) -> None:
        """Finding raises ValueError for invalid timestamp."""
        with pytest.raises(ValueError, match="Invalid ISO 8601"):
            Finding(
                id=VALID_UUID_1,
                type="test",
                severity="info",
                target="127.0.0.1",
                evidence="N/A",
                agent_id=VALID_UUID_2,
                timestamp="2025/12/31",  # Invalid format
                tool="tool",
                topic="topic",
                signature="sig",
            )

    def test_finding_validation_invalid_target(self) -> None:
        """Finding raises ValueError for invalid target (empty or bad chars)."""
        with pytest.raises(ValueError, match="Field 'target' cannot be empty"):
            Finding(
                id=VALID_UUID_1,
                type="test",
                severity="info",
                target="",  # Empty
                evidence="N/A",
                agent_id=VALID_UUID_2,
                timestamp="2025-12-31T00:00:00Z",
                tool="tool",
                topic="topic",
                signature="sig",
            )
        
        # Test whitespace rejection
        with pytest.raises(ValueError, match="cannot contain whitespace"):
             Finding(
                id=VALID_UUID_1,
                type="test",
                severity="info",
                target="http://invalid url with spaces", 
                evidence="N/A",
                agent_id=VALID_UUID_2,
                timestamp="2025-12-31T00:00:00Z",
                tool="tool",
                topic="topic",
                signature="sig",
            )

    def test_finding_to_json(self) -> None:
        """Finding.to_json() produces valid JSON."""
        finding = Finding(
            id=VALID_UUID_1,
            type="xss",
            severity="high",
            target="https://example.com",
            evidence="evidence",
            agent_id=VALID_UUID_2,
            timestamp="2025-12-31T00:00:00Z",
            tool="nuclei",
            topic="topic",
            signature="sig123",
        )

        json_str = finding.to_json()
        parsed = json.loads(json_str)

        assert parsed["id"] == VALID_UUID_1
        assert parsed["target"] == "https://example.com"

    def test_finding_from_json_round_trip(self) -> None:
        """Finding.from_json() reconstructs object from JSON."""
        original = Finding(
            id=VALID_UUID_1,
            type="open_port",
            severity="info",
            target="10.0.0.1",
            evidence="evidence",
            agent_id=VALID_UUID_2,
            timestamp="2025-12-31T12:00:00Z",
            tool="nmap",
            topic="topic",
            signature="sig",
        )

        json_str = original.to_json()
        reconstructed = Finding.from_json(json_str)

        assert reconstructed.id == original.id


class TestAgentAction:
    """Tests for AgentAction dataclass including new validation logic."""

    def test_agent_action_instantiation_all_fields(self) -> None:
        """AgentAction can be instantiated with all 7 fields."""
        action = AgentAction(
            id=VALID_UUID_1,
            agent_id=VALID_UUID_2,
            action_type="exploit",
            target="192.168.1.100",
            timestamp="2025-12-31T00:00:00Z",
            decision_context=["finding-ID"],
            result_finding_id=VALID_UUID_3,
        )

        assert action.id == VALID_UUID_1
        assert action.result_finding_id == VALID_UUID_3

    def test_agent_action_validation_invalid_finding_id(self) -> None:
        """AgentAction raises ValueError for invalid result_finding_id."""
        with pytest.raises(ValueError, match="Invalid UUID"):
            AgentAction(
                id=VALID_UUID_1,
                agent_id=VALID_UUID_2,
                action_type="scan",
                target="target",
                timestamp="2025-12-31T00:00:00Z",
                result_finding_id="not-a-uuid",
            )

    def test_agent_action_empty_decision_context(self) -> None:
        """AgentAction works with empty decision_context list."""
        action = AgentAction(
            id=VALID_UUID_1,
            agent_id=VALID_UUID_2,
            action_type="scan",
            target="10.0.0.1",
            timestamp="2025-12-31T00:00:00Z",
            decision_context=[],
            result_finding_id=None,
        )
        assert action.decision_context == []

    def test_agent_action_to_json(self) -> None:
        """AgentAction.to_json() produces valid JSON."""
        action = AgentAction(
            id=VALID_UUID_1,
            agent_id=VALID_UUID_2,
            action_type="scan",
            target="10.0.0.1",
            timestamp="2025-12-31T00:00:00Z",
            decision_context=["sig1"],
            result_finding_id=VALID_UUID_3,
        )

        json_str = action.to_json()
        parsed = json.loads(json_str)

        assert parsed["id"] == VALID_UUID_1
        assert parsed["result_finding_id"] == VALID_UUID_3

    def test_agent_action_to_json_with_null_result(self) -> None:
        """AgentAction with None result_finding_id serializes to null."""
        action = AgentAction(
            id=VALID_UUID_1,
            agent_id=VALID_UUID_2,
            action_type="scan",
            target="target",
            timestamp="2025-12-31T00:00:00Z",
            result_finding_id=None,
        )

        json_str = action.to_json()
        parsed = json.loads(json_str)

        assert parsed["result_finding_id"] is None


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_tool_result_instantiation_all_fields(self) -> None:
        """ToolResult can be instantiated (no changes to validation)."""
        result = ToolResult(
            success=True,
            stdout="output",
            stderr="",
            exit_code=0,
            duration_ms=5000,
        )
        assert result.success is True

    def test_tool_result_to_json(self) -> None:
        """ToolResult.to_json() produces valid JSON."""
        result = ToolResult(
            success=True,
            stdout="output",
            stderr="warning",
            exit_code=0,
            duration_ms=1234,
        )
        json_str = result.to_json()
        assert "duration_ms" in json_str

    def test_tool_result_with_error_type(self) -> None:
        """ToolResult accepts optional error_type field."""
        result = ToolResult(
            success=False,
            stdout="",
            stderr="Execution timed out",
            exit_code=-1,
            duration_ms=30000,
            error_type="TIMEOUT",
        )
        assert result.success is False
        assert result.error_type == "TIMEOUT"

    def test_tool_result_without_error_type(self) -> None:
        """ToolResult defaults error_type to None when not provided."""
        result = ToolResult(
            success=True,
            stdout="output",
            stderr="",
            exit_code=0,
            duration_ms=100,
        )
        assert result.error_type is None

    def test_tool_result_error_type_all_values(self) -> None:
        """ToolResult accepts all defined error_type constants."""
        error_types = ["TIMEOUT", "NON_ZERO_EXIT", "CONTAINER_CRASHED", 
                       "EXECUTION_EXCEPTION", "POOL_EXHAUSTED", None]
        for error_type in error_types:
            result = ToolResult(
                success=False,
                stdout="",
                stderr="error",
                exit_code=1,
                duration_ms=0,
                error_type=error_type,
            )
            assert result.error_type == error_type

    def test_tool_result_to_json_includes_error_type(self) -> None:
        """ToolResult.to_json() includes error_type field."""
        result = ToolResult(
            success=False,
            stdout="",
            stderr="Container crashed",
            exit_code=-1,
            duration_ms=0,
            error_type="CONTAINER_CRASHED",
        )
        json_str = result.to_json()
        parsed = json.loads(json_str)
        assert "error_type" in parsed
        assert parsed["error_type"] == "CONTAINER_CRASHED"

    def test_tool_result_from_json_with_error_type(self) -> None:
        """ToolResult.from_json() reconstructs error_type field."""
        original = ToolResult(
            success=False,
            stdout="partial output",
            stderr="Non-zero exit",
            exit_code=1,
            duration_ms=500,
            error_type="NON_ZERO_EXIT",
        )
        json_str = original.to_json()
        reconstructed = ToolResult.from_json(json_str)
        assert reconstructed.error_type == "NON_ZERO_EXIT"
        assert reconstructed.success == original.success

    def test_tool_result_from_json_without_error_type_backwards_compat(self) -> None:
        """ToolResult.from_json() handles missing error_type for backwards compatibility."""
        # Simulate old JSON format without error_type
        old_json = '{"success": true, "stdout": "out", "stderr": "", "exit_code": 0, "duration_ms": 100}'
        result = ToolResult.from_json(old_json)
        assert result.success is True
        assert result.error_type is None


class TestFromJsonWithDict:
    """Tests for from_json accepting both string and dict."""

    def test_finding_from_json_with_dict(self) -> None:
        """Finding.from_json() accepts a dict."""
        data = {
            "id": VALID_UUID_1,
            "type": "test",
            "severity": "low",
            "target": "target",
            "evidence": "evidence",
            "agent_id": VALID_UUID_2,
            "timestamp": "2025-12-31T00:00:00Z",
            "tool": "tool",
            "topic": "topic",
            "signature": "sig",
        }
        finding = Finding.from_json(data)
        assert finding.id == VALID_UUID_1

    def test_agent_action_from_json_with_dict(self) -> None:
        """AgentAction.from_json() accepts a dict."""
        data = {
            "id": VALID_UUID_1,
            "agent_id": VALID_UUID_2,
            "action_type": "scan",
            "target": "target",
            "timestamp": "2025-12-31T00:00:00Z",
            "decision_context": ["a"],
            "result_finding_id": None,
        }
        action = AgentAction.from_json(data)
        assert action.id == VALID_UUID_1

    def test_agent_action_from_json_with_string(self) -> None:
        """AgentAction.from_json() accepts a JSON string."""
        data = {
            "id": VALID_UUID_1,
            "agent_id": VALID_UUID_2,
            "action_type": "exploit",
            "target": "192.168.1.1",
            "timestamp": "2025-12-31T00:00:00Z",
            "decision_context": [],
            "result_finding_id": None,
        }
        json_str = json.dumps(data)
        action = AgentAction.from_json(json_str)
        assert action.id == VALID_UUID_1
        assert action.action_type == "exploit"

    def test_tool_result_from_json_with_dict(self) -> None:
        """ToolResult.from_json() accepts a dict."""
        data = {
            "success": True,
            "stdout": "output",
            "stderr": "",
            "exit_code": 0,
            "duration_ms": 100,
            "error_type": None,
        }
        result = ToolResult.from_json(data)
        assert result.success is True


class TestValidationEdgeCases:
    """Tests for validation edge cases to achieve 100% coverage."""

    def test_validate_uuid_with_none_value(self) -> None:
        """_validate_uuid returns early for None value (line 47 coverage)."""
        # AgentAction with result_finding_id=None should not raise
        action = AgentAction(
            id=VALID_UUID_1,
            agent_id=VALID_UUID_2,
            action_type="scan",
            target="127.0.0.1",
            timestamp="2025-12-31T00:00:00Z",
            decision_context=[],
            result_finding_id=None,  # This triggers the None check
        )
        assert action.result_finding_id is None

    def test_finding_invalid_severity_raises_error(self) -> None:
        """Finding raises ValueError for invalid severity (line 132 coverage)."""
        with pytest.raises(ValueError, match="Invalid severity"):
            Finding(
                id=VALID_UUID_1,
                type="test",
                severity="invalid_severity",  # Invalid!
                target="192.168.1.1",
                evidence="test",
                agent_id=VALID_UUID_2,
                timestamp="2025-12-31T00:00:00Z",
                tool="tool",
                topic="topic",
                signature="sig",
            )

    def test_target_invalid_format_raises_error(self) -> None:
        """_validate_target raises ValueError for invalid format (line 91 coverage)."""
        with pytest.raises(ValueError, match="Invalid target format"):
            Finding(
                id=VALID_UUID_1,
                type="test",
                severity="info",
                target="!!!invalid@@@target###",  # Not IP, URL, or hostname
                evidence="test",
                agent_id=VALID_UUID_2,
                timestamp="2025-12-31T00:00:00Z",
                tool="tool",
                topic="topic",
                signature="sig",
            )

    def test_finding_from_json_with_string(self) -> None:
        """Finding.from_json() accepts JSON string (line 151 coverage)."""
        data = {
            "id": VALID_UUID_1,
            "type": "xss",
            "severity": "high",
            "target": "example.com",
            "evidence": "evidence",
            "agent_id": VALID_UUID_2,
            "timestamp": "2025-12-31T00:00:00Z",
            "tool": "tool",
            "topic": "topic",
            "signature": "sig",
        }
        json_str = json.dumps(data)
        finding = Finding.from_json(json_str)
        assert finding.id == VALID_UUID_1
        assert finding.type == "xss"

    def test_tool_result_from_json_string_with_error_type(self) -> None:
        """ToolResult.from_json() with string and error_type field (line 240-241 coverage)."""
        data = {
            "success": False,
            "stdout": "",
            "stderr": "timeout",
            "exit_code": -1,
            "duration_ms": 5000,
            "error_type": "TIMEOUT",
        }
        json_str = json.dumps(data)
        result = ToolResult.from_json(json_str)
        assert result.error_type == "TIMEOUT"
