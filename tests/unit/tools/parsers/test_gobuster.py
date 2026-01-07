"""Unit tests for gobuster parser."""
import pytest
import uuid
from cyberred.tools.parsers import gobuster


@pytest.mark.unit
class TestGobusterParser:
    """Tests for gobuster parser functionality."""

    def test_gobuster_parser_signature(self):
        """Test that gobuster_parser matches the ParserFn signature."""
        assert hasattr(gobuster, 'gobuster_parser')
        assert callable(gobuster.gobuster_parser)
        
        result = gobuster.gobuster_parser(stdout='', stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        assert isinstance(result, list)

    def test_gobuster_dir_mode(self):
        """Test parsing gobuster dir mode output."""
        stdout = '''/admin (Status: 200) [Size: 1234]
/backup/ (Status: 301) [Size: 456]
/config.php (Status: 403) [Size: 789]'''
        
        findings = gobuster.gobuster_parser(stdout=stdout, stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        
        assert len(findings) == 3
        
        admin = next(f for f in findings if "/admin" in f.evidence)
        assert admin.type == "file"  # No trailing slash
        
        backup = next(f for f in findings if "/backup/" in f.evidence)
        assert backup.type == "directory"  # Has trailing slash

    def test_gobuster_dns_mode(self):
        """Test parsing gobuster dns mode output."""
        stdout = '''Found: api.example.com
Found: www.example.com
Found: mail.example.com'''
        
        findings = gobuster.gobuster_parser(stdout=stdout, stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        
        assert len(findings) == 3
        assert all(f.type == "subdomain" for f in findings)

    def test_gobuster_severity_mapping(self):
        """Test that 403 status has low severity."""
        stdout = '''/secret (Status: 403) [Size: 100]'''
        
        findings = gobuster.gobuster_parser(stdout=stdout, stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        
        assert len(findings) == 1
        assert findings[0].severity == "low"

    def test_gobuster_empty_output(self):
        """Test handling of empty output."""
        findings = gobuster.gobuster_parser(stdout="", stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        assert findings == []
