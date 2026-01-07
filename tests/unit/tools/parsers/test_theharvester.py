"""Unit tests for theharvester parser."""
import pytest
import uuid
from cyberred.tools.parsers import theharvester


@pytest.mark.unit
class TestTheHarvesterParser:
    """Tests for theharvester parser functionality."""

    def test_theharvester_parser_signature(self):
        """Test that theharvester_parser matches the ParserFn signature."""
        assert hasattr(theharvester, 'theharvester_parser')
        assert callable(theharvester.theharvester_parser)
        
        result = theharvester.theharvester_parser(stdout='', stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        assert isinstance(result, list)

    def test_theharvester_xml_parsing(self):
        """Test parsing theharvester XML output."""
        xml_output = '''<?xml version="1.0"?>
<theHarvester>
    <email>admin@example.com</email>
    <email>info@example.com</email>
    <host>www.example.com</host>
</theHarvester>'''
        
        findings = theharvester.theharvester_parser(stdout=xml_output, stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        
        emails = [f for f in findings if f.type == "email"]
        hosts = [f for f in findings if f.type == "subdomain"]
        
        assert len(emails) == 2
        assert len(hosts) == 1

    def test_theharvester_stdout_emails(self):
        """Test parsing emails from stdout."""
        stdout = '''
[*] Emails found:
admin@example.com
info@example.com
'''
        
        findings = theharvester.theharvester_parser(stdout=stdout, stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        
        emails = [f for f in findings if f.type == "email"]
        assert len(emails) >= 2

    def test_theharvester_empty_output(self):
        """Test handling of empty output."""
        findings = theharvester.theharvester_parser(stdout="", stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        assert findings == []
