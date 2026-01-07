"""Unit tests for dnsrecon parser."""
import pytest
import uuid
from cyberred.tools.parsers import dnsrecon


@pytest.mark.unit
class TestDnsreconParser:
    """Tests for dnsrecon parser functionality."""

    def test_dnsrecon_parser_signature(self):
        """Test that dnsrecon_parser matches the ParserFn signature."""
        assert hasattr(dnsrecon, 'dnsrecon_parser')
        assert callable(dnsrecon.dnsrecon_parser)
        
        result = dnsrecon.dnsrecon_parser(stdout='', stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        assert isinstance(result, list)

    def test_dnsrecon_json_parsing(self):
        """Test parsing dnsrecon JSON output."""
        dnsrecon_json = '''[{"type":"A","name":"example.com","address":"93.184.216.34"},{"type":"MX","name":"example.com","target":"mail.example.com"}]'''
        
        findings = dnsrecon.dnsrecon_parser(stdout=dnsrecon_json, stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        
        assert len(findings) == 2
        assert all(f.type == "dns_record" for f in findings)

    def test_dnsrecon_zone_transfer(self):
        """Test zone transfer detection has high severity."""
        dnsrecon_json = '''[{"type":"AXFR","name":"example.com","data":"zone transfer data"}]'''
        
        findings = dnsrecon.dnsrecon_parser(stdout=dnsrecon_json, stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        
        assert len(findings) == 1
        assert findings[0].severity == "high"

    def test_dnsrecon_empty_output(self):
        """Test handling of empty output."""
        findings = dnsrecon.dnsrecon_parser(stdout="", stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        assert findings == []

    def test_dnsrecon_stdout_parsing(self):
        """Test parsing stdout format with DNS records."""
        stdout = '''[*] A example.com 93.184.216.34
[*] MX example.com mail.example.com
Zone Transfer detected: AXFR succeeded'''
        
        findings = dnsrecon.dnsrecon_parser(stdout=stdout, stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        
        assert len(findings) >= 2
        # Should have zone transfer finding with high severity
        zone_findings = [f for f in findings if "Zone Transfer" in f.evidence]
        assert len(zone_findings) >= 1
        assert zone_findings[0].severity == "high"
