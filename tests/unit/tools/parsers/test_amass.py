"""Unit tests for amass parser."""
import pytest
import uuid
from cyberred.tools.parsers import amass


@pytest.mark.unit
class TestAmassParser:
    """Tests for amass parser functionality."""

    def test_amass_parser_signature(self):
        """Test that amass_parser matches the ParserFn signature."""
        assert hasattr(amass, 'amass_parser')
        assert callable(amass.amass_parser)
        
        result = amass.amass_parser(stdout='', stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        assert isinstance(result, list)

    def test_amass_json_parsing(self):
        """Test parsing amass JSON output."""
        amass_json = '''{"name":"api.example.com","source":"DNS","addresses":[{"ip":"192.168.1.1"}]}
{"name":"www.example.com","source":"cert","addresses":[{"ip":"192.168.1.2"}]}'''
        
        findings = amass.amass_parser(stdout=amass_json, stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        
        assert len(findings) == 2
        assert all(f.type == "subdomain" for f in findings)

    def test_amass_plain_text(self):
        """Test parsing plain text output."""
        stdout = '''api.example.com
www.example.com'''
        
        findings = amass.amass_parser(stdout=stdout, stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        assert len(findings) == 2

    def test_amass_empty_output(self):
        """Test handling of empty output."""
        findings = amass.amass_parser(stdout="", stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        assert findings == []
