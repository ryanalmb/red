"""Unit tests for wafw00f parser."""
import pytest
import uuid
from cyberred.tools.parsers import wafw00f


@pytest.mark.unit
class TestWafw00fParser:
    """Tests for wafw00f parser functionality."""

    def test_wafw00f_parser_signature(self):
        """Test that wafw00f_parser matches the ParserFn signature."""
        assert hasattr(wafw00f, 'wafw00f_parser')
        assert callable(wafw00f.wafw00f_parser)
        
        result = wafw00f.wafw00f_parser(stdout='', stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        assert isinstance(result, list)

    def test_wafw00f_json_parsing(self):
        """Test parsing wafw00f JSON output."""
        wafw00f_json = '''[{"url":"http://example.com","detected":true,"firewall":"Cloudflare"}]'''
        
        findings = wafw00f.wafw00f_parser(stdout=wafw00f_json, stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        
        assert len(findings) == 1
        assert findings[0].type == "waf_detected"
        assert "Cloudflare" in findings[0].evidence

    def test_wafw00f_stdout_parsing(self):
        """Test parsing wafw00f stdout format."""
        stdout = '''
[*] Checking http://example.com
[+] The site http://example.com is behind Cloudflare WAF.
'''
        
        findings = wafw00f.wafw00f_parser(stdout=stdout, stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        
        assert len(findings) == 1
        assert "Cloudflare" in findings[0].evidence

    def test_wafw00f_no_waf(self):
        """Test handling of no WAF detected."""
        stdout = '''
[*] Checking http://example.com
[-] No WAF detected by the generic detection
'''
        
        findings = wafw00f.wafw00f_parser(stdout=stdout, stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        assert findings == []

    def test_wafw00f_empty_output(self):
        """Test handling of empty output."""
        findings = wafw00f.wafw00f_parser(stdout="", stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        assert findings == []
