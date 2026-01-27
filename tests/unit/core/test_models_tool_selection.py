"""Unit tests for ToolSelectionContext and ToolSelection dataclasses.

Tests written FIRST as part of TDD RED phase for Story 7.1.v2.
These tests must FAIL until models are implemented.
"""

import json
import uuid

import pytest


@pytest.mark.unit
class TestToolSelectionContext:
    """Tests for ToolSelectionContext dataclass."""

    def test_tool_selection_context_required_fields(self):
        """ToolSelectionContext requires objective, target_info, available_tools, phase."""
        from cyberred.core.models import ToolSelectionContext

        # Should work with required fields
        ctx = ToolSelectionContext(
            objective="Enumerate open ports",
            target_info={"ip": "192.168.1.100", "os": "linux"},
            available_tools=["nmap", "masscan"],
            phase="recon",
        )
        assert ctx.objective == "Enumerate open ports"
        assert ctx.target_info == {"ip": "192.168.1.100", "os": "linux"}
        assert ctx.available_tools == ["nmap", "masscan"]
        assert ctx.phase == "recon"

    def test_tool_selection_context_defaults(self):
        """ToolSelectionContext has correct defaults for optional fields."""
        from cyberred.core.models import ToolSelectionContext

        ctx = ToolSelectionContext(
            objective="Scan network",
            target_info={"ip": "10.0.0.1"},
            available_tools=["nmap"],
            phase="recon",
        )
        # Default values
        assert ctx.constraints == []
        assert ctx.previous_results == []

    def test_tool_selection_context_all_fields(self):
        """ToolSelectionContext accepts all fields."""
        from cyberred.core.models import ToolSelectionContext

        ctx = ToolSelectionContext(
            objective="Web vulnerability scan",
            target_info={"hostname": "example.com", "ports": [80, 443]},
            available_tools=["nuclei", "nikto", "sqlmap"],
            phase="exploit",
            constraints=["stealth", "no-dos"],
            previous_results=[{"tool": "nmap", "ports": [80, 443]}],
        )
        assert ctx.available_tools == ["nuclei", "nikto", "sqlmap"]
        assert ctx.phase == "exploit"
        assert ctx.constraints == ["stealth", "no-dos"]
        assert ctx.previous_results == [{"tool": "nmap", "ports": [80, 443]}]

    def test_tool_selection_context_serializable(self):
        """ToolSelectionContext is JSON serializable via to_json()."""
        from cyberred.core.models import ToolSelectionContext

        ctx = ToolSelectionContext(
            objective="Find vulnerabilities",
            target_info={"ip": "192.168.1.1", "open_ports": [22, 80]},
            available_tools=["nmap", "nuclei"],
            phase="recon",
            previous_results=[{"tool": "masscan", "ports": [22, 80]}],
        )
        
        json_str = ctx.to_json()
        data = json.loads(json_str)
        
        assert data["objective"] == "Find vulnerabilities"
        assert data["available_tools"] == ["nmap", "nuclei"]
        assert data["phase"] == "recon"

    def test_tool_selection_context_from_json(self):
        """ToolSelectionContext can be deserialized from JSON."""
        from cyberred.core.models import ToolSelectionContext

        data = {
            "objective": "Exploit HTTP service",
            "target_info": {"ip": "10.0.0.5", "services": ["ssh", "http"]},
            "available_tools": ["sqlmap", "nuclei"],
            "phase": "exploit",
            "constraints": [],
            "previous_results": [],
        }
        
        ctx = ToolSelectionContext.from_json(data)
        assert ctx.objective == "Exploit HTTP service"
        assert ctx.available_tools == ["sqlmap", "nuclei"]
        assert ctx.phase == "exploit"


@pytest.mark.unit
class TestToolSelection:
    """Tests for ToolSelection dataclass."""

    def test_tool_selection_required_fields(self):
        """ToolSelection requires tool_name, command, rationale, expected_output_type."""
        from cyberred.core.models import ToolSelection

        sel = ToolSelection(
            tool_name="nmap",
            command="nmap -sV -sC 192.168.1.1",
            rationale="Best tool for port scanning",
            expected_output_type="xml",
        )
        assert sel.tool_name == "nmap"
        assert sel.command == "nmap -sV -sC 192.168.1.1"
        assert sel.rationale == "Best tool for port scanning"
        assert sel.expected_output_type == "xml"
        # Defaults
        assert sel.confidence == 0.8
        assert sel.priority == 5

    def test_tool_selection_has_selection_id(self):
        """ToolSelection auto-generates UUID selection_id."""
        from cyberred.core.models import ToolSelection

        sel = ToolSelection(
            tool_name="nuclei",
            command="nuclei -u http://target.com -t cves/",
            rationale="Vulnerability scanner",
            expected_output_type="json",
        )
        
        # Should have auto-generated UUID
        assert sel.selection_id is not None
        # Validate it's a proper UUID
        uuid.UUID(sel.selection_id)

    def test_tool_selection_custom_selection_id(self):
        """ToolSelection accepts custom selection_id."""
        from cyberred.core.models import ToolSelection

        custom_id = str(uuid.uuid4())
        sel = ToolSelection(
            tool_name="sqlmap",
            command="sqlmap -u http://target.com/page?id=1",
            rationale="SQL injection testing",
            expected_output_type="text",
            confidence=0.9,
            selection_id=custom_id,
        )
        assert sel.selection_id == custom_id

    def test_tool_selection_confidence_bounds_valid(self):
        """ToolSelection accepts valid confidence values 0.0-1.0."""
        from cyberred.core.models import ToolSelection

        # Min valid
        sel_min = ToolSelection(
            tool_name="test",
            command="test target",
            rationale="test",
            expected_output_type="text",
            confidence=0.0,
        )
        assert sel_min.confidence == 0.0

        # Max valid
        sel_max = ToolSelection(
            tool_name="test",
            command="test target",
            rationale="test",
            expected_output_type="text",
            confidence=1.0,
        )
        assert sel_max.confidence == 1.0

    def test_tool_selection_confidence_bounds_invalid_high(self):
        """ToolSelection.confidence must be <= 1.0."""
        from cyberred.core.models import ToolSelection

        with pytest.raises(ValueError, match="confidence"):
            ToolSelection(
                tool_name="test",
                command="test target",
                rationale="test",
                expected_output_type="text",
                confidence=1.5,
            )

    def test_tool_selection_confidence_bounds_invalid_low(self):
        """ToolSelection.confidence must be >= 0.0."""
        from cyberred.core.models import ToolSelection

        with pytest.raises(ValueError, match="confidence"):
            ToolSelection(
                tool_name="test",
                command="test target",
                rationale="test",
                expected_output_type="text",
                confidence=-0.1,
            )

    def test_tool_selection_priority_bounds_valid(self):
        """ToolSelection accepts valid priority values 1-10."""
        from cyberred.core.models import ToolSelection

        # Min valid
        sel_min = ToolSelection(
            tool_name="test",
            command="test target",
            rationale="test",
            expected_output_type="text",
            priority=1,
        )
        assert sel_min.priority == 1

        # Max valid
        sel_max = ToolSelection(
            tool_name="test",
            command="test target",
            rationale="test",
            expected_output_type="text",
            priority=10,
        )
        assert sel_max.priority == 10

    def test_tool_selection_priority_bounds_invalid_high(self):
        """ToolSelection.priority must be <= 10."""
        from cyberred.core.models import ToolSelection

        with pytest.raises(ValueError, match="priority"):
            ToolSelection(
                tool_name="test",
                command="test target",
                rationale="test",
                expected_output_type="text",
                priority=11,
            )

    def test_tool_selection_priority_bounds_invalid_low(self):
        """ToolSelection.priority must be >= 1."""
        from cyberred.core.models import ToolSelection

        with pytest.raises(ValueError, match="priority"):
            ToolSelection(
                tool_name="test",
                command="test target",
                rationale="test",
                expected_output_type="text",
                priority=0,
            )

    def test_tool_selection_alternatives_default(self):
        """ToolSelection.alternatives defaults to empty list."""
        from cyberred.core.models import ToolSelection

        sel = ToolSelection(
            tool_name="nmap",
            command="nmap -sV 192.168.1.1",
            rationale="Port scanner",
            expected_output_type="xml",
        )
        assert sel.alternatives == []

    def test_tool_selection_alternatives_provided(self):
        """ToolSelection accepts alternatives list."""
        from cyberred.core.models import ToolSelection

        sel = ToolSelection(
            tool_name="nmap",
            command="nmap -sV 192.168.1.1",
            rationale="Primary choice",
            expected_output_type="xml",
            alternatives=["masscan", "rustscan"],
        )
        assert sel.alternatives == ["masscan", "rustscan"]

    def test_tool_selection_serializable(self):
        """ToolSelection is JSON serializable via to_json()."""
        from cyberred.core.models import ToolSelection

        sel = ToolSelection(
            tool_name="gobuster",
            command="gobuster dir -u http://target.com -w wordlist.txt",
            rationale="Directory brute forcing",
            expected_output_type="text",
            confidence=0.85,
            priority=7,
            alternatives=["dirsearch", "feroxbuster"],
        )
        
        json_str = sel.to_json()
        data = json.loads(json_str)
        
        assert data["tool_name"] == "gobuster"
        assert data["command"] == "gobuster dir -u http://target.com -w wordlist.txt"
        assert data["rationale"] == "Directory brute forcing"
        assert data["expected_output_type"] == "text"
        assert data["confidence"] == 0.85
        assert data["priority"] == 7
        assert data["alternatives"] == ["dirsearch", "feroxbuster"]

    def test_tool_selection_from_json(self):
        """ToolSelection can be deserialized from JSON."""
        from cyberred.core.models import ToolSelection

        sel_id = str(uuid.uuid4())
        data = {
            "tool_name": "hydra",
            "command": "hydra -l admin -P passwords.txt ssh://target",
            "rationale": "Password brute forcing",
            "expected_output_type": "text",
            "confidence": 0.75,
            "priority": 6,
            "alternatives": ["medusa"],
            "selection_id": sel_id,
        }
        
        sel = ToolSelection.from_json(data)
        assert sel.tool_name == "hydra"
        assert sel.command == "hydra -l admin -P passwords.txt ssh://target"
        assert sel.rationale == "Password brute forcing"
        assert sel.confidence == 0.75
        assert sel.priority == 6
        assert sel.selection_id == sel_id
