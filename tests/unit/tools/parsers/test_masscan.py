"""Unit tests for masscan parser."""
import pytest
import uuid
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import masscan


@pytest.mark.unit
class TestMasscanParser:
    """Tests for masscan parser functionality."""

    def test_masscan_parser_signature(self):
        """Test that masscan_parser matches the ParserFn signature."""
        assert hasattr(masscan, 'masscan_parser')
        assert callable(masscan.masscan_parser)
        
        result = masscan.masscan_parser(
            stdout='[]',
            stderr='',
            exit_code=0,
            agent_id=str(uuid.uuid4()),
            target="test-target"
        )
        assert isinstance(result, list)

    def test_masscan_json_parsing(self):
        """Test parsing masscan JSON output (-oJ format)."""
        masscan_json = '''[
            {
                "ip": "192.168.1.1",
                "timestamp": "1609459200",
                "ports": [
                    {"port": 80, "proto": "tcp", "status": "open", "reason": "syn-ack", "ttl": 64}
                ]
            },
            {
                "ip": "192.168.1.2",
                "timestamp": "1609459201",
                "ports": [
                    {"port": 443, "proto": "tcp", "status": "open", "reason": "syn-ack", "ttl": 64},
                    {"port": 22, "proto": "tcp", "status": "open", "reason": "syn-ack", "ttl": 64}
                ]
            }
        ]'''
        
        agent_id = str(uuid.uuid4())
        findings = masscan.masscan_parser(
            stdout=masscan_json,
            stderr='',
            exit_code=0,
            agent_id=agent_id,
            target="192.168.1.0/24"
        )
        
        assert len(findings) == 3
        
        # Check port 80 finding
        port80 = next((f for f in findings if "80" in f.evidence and "192.168.1.1" in f.evidence), None)
        assert port80 is not None
        assert port80.type == "open_port"
        assert port80.severity == "info"
        assert port80.tool == "masscan"
        assert "tcp" in port80.evidence.lower()

    def test_masscan_stdout_parsing(self):
        """Test parsing masscan stdout format (non-JSON)."""
        stdout = '''
Discovered open port 80/tcp on 192.168.1.1
Discovered open port 443/tcp on 192.168.1.1
Discovered open port 22/tcp on 192.168.1.2
'''
        
        findings = masscan.masscan_parser(
            stdout=stdout,
            stderr='',
            exit_code=0,
            agent_id=str(uuid.uuid4()),
            target="192.168.1.0/24"
        )
        
        assert len(findings) == 3
        
        # Check findings have correct type
        for f in findings:
            assert f.type == "open_port"
            assert f.severity == "info"

    def test_masscan_empty_output(self):
        """Test handling of empty output."""
        findings = masscan.masscan_parser(
            stdout="",
            stderr='',
            exit_code=0,
            agent_id=str(uuid.uuid4()),
            target="192.168.1.1"
        )
        
        assert findings == []

    def test_masscan_invalid_json(self):
        """Test handling of invalid JSON gracefully."""
        findings = masscan.masscan_parser(
            stdout="not valid json",
            stderr='',
            exit_code=0,
            agent_id=str(uuid.uuid4()),
            target="192.168.1.1"
        )
        
        # Should try stdout parsing as fallback, but if no matches, return empty
        assert isinstance(findings, list)

    def test_masscan_finding_fields(self):
        """Test that findings have all required fields."""
        masscan_json = '''[
            {
                "ip": "10.0.0.1",
                "ports": [{"port": 8080, "proto": "tcp", "status": "open"}]
            }
        ]'''
        
        agent_id = str(uuid.uuid4())
        findings = masscan.masscan_parser(
            stdout=masscan_json,
            stderr='',
            exit_code=0,
            agent_id=agent_id,
            target="10.0.0.1"
        )
        
        assert len(findings) == 1
        finding = findings[0]
        
        # Check required Finding fields
        assert finding.id is not None
        assert finding.agent_id == agent_id
        assert finding.timestamp is not None
        assert finding.target == "10.0.0.1"
        assert finding.type == "open_port"
        assert finding.severity == "info"
        assert finding.evidence is not None
        assert finding.tool == "masscan"
        assert finding.topic is not None
        assert "open_port" in finding.topic

    def test_masscan_udp_ports(self):
        """Test parsing UDP ports."""
        masscan_json = '''[
            {
                "ip": "192.168.1.1",
                "ports": [
                    {"port": 53, "proto": "udp", "status": "open"}
                ]
            }
        ]'''
        
        findings = masscan.masscan_parser(
            stdout=masscan_json,
            stderr='',
            exit_code=0,
            agent_id=str(uuid.uuid4()),
            target="192.168.1.1"
        )
        
        assert len(findings) == 1
        assert "udp" in findings[0].evidence.lower()
