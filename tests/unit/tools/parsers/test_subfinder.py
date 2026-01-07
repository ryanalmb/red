"""Unit tests for subfinder parser."""
import pytest
import uuid
from cyberred.tools.parsers import subfinder


@pytest.mark.unit
class TestSubfinderParser:
    """Tests for subfinder parser functionality."""

    def test_subfinder_parser_signature(self):
        """Test that subfinder_parser matches the ParserFn signature."""
        assert hasattr(subfinder, 'subfinder_parser')
        assert callable(subfinder.subfinder_parser)
        
        result = subfinder.subfinder_parser(
            stdout='',
            stderr='',
            exit_code=0,
            agent_id=str(uuid.uuid4()),
            target="example.com"
        )
        assert isinstance(result, list)

    def test_subfinder_json_parsing(self):
        """Test parsing subfinder JSON output (-oJ format)."""
        subfinder_json = '''{"host":"api.example.com","input":"example.com","source":"crtsh"}
{"host":"www.example.com","input":"example.com","source":"dnsdumpster"}
{"host":"mail.example.com","input":"example.com","source":"hackertarget"}'''
        
        findings = subfinder.subfinder_parser(
            stdout=subfinder_json,
            stderr='',
            exit_code=0,
            agent_id=str(uuid.uuid4()),
            target="example.com"
        )
        
        assert len(findings) == 3
        hosts = [f.evidence for f in findings]
        assert any("api.example.com" in h for h in hosts)
        assert any("www.example.com" in h for h in hosts)
        assert any("mail.example.com" in h for h in hosts)

    def test_subfinder_stdout_parsing(self):
        """Test parsing subfinder plain stdout (one hostname per line)."""
        stdout = '''api.example.com
www.example.com
mail.example.com
dev.example.com'''
        
        findings = subfinder.subfinder_parser(
            stdout=stdout,
            stderr='',
            exit_code=0,
            agent_id=str(uuid.uuid4()),
            target="example.com"
        )
        
        assert len(findings) == 4
        for f in findings:
            assert f.type == "subdomain"
            assert f.severity == "info"

    def test_subfinder_empty_output(self):
        """Test handling of empty output."""
        findings = subfinder.subfinder_parser(
            stdout="",
            stderr='',
            exit_code=0,
            agent_id=str(uuid.uuid4()),
            target="example.com"
        )
        assert findings == []

    def test_subfinder_deduplication(self):
        """Test that duplicate subdomains are deduplicated."""
        stdout = '''api.example.com
api.example.com
www.example.com
api.example.com'''
        
        findings = subfinder.subfinder_parser(
            stdout=stdout,
            stderr='',
            exit_code=0,
            agent_id=str(uuid.uuid4()),
            target="example.com"
        )
        
        # Should have unique findings
        hosts = [f.evidence for f in findings]
        assert len(findings) == 2

    def test_subfinder_finding_fields(self):
        """Test that findings have all required fields."""
        stdout = "test.example.com"
        agent_id = str(uuid.uuid4())
        
        findings = subfinder.subfinder_parser(
            stdout=stdout,
            stderr='',
            exit_code=0,
            agent_id=agent_id,
            target="example.com"
        )
        
        assert len(findings) == 1
        finding = findings[0]
        
        assert finding.id is not None
        assert finding.agent_id == agent_id
        assert finding.type == "subdomain"
        assert finding.severity == "info"
        assert finding.tool == "subfinder"
        assert "subdomain" in finding.topic
