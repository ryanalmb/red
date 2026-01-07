"""Unit tests for whatweb parser."""
import pytest
import uuid
from cyberred.tools.parsers import whatweb


@pytest.mark.unit
class TestWhatwebParser:
    """Tests for whatweb parser functionality."""

    def test_whatweb_parser_signature(self):
        """Test that whatweb_parser matches the ParserFn signature."""
        assert hasattr(whatweb, 'whatweb_parser')
        assert callable(whatweb.whatweb_parser)
        
        result = whatweb.whatweb_parser(stdout='', stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        assert isinstance(result, list)

    def test_whatweb_json_parsing(self):
        """Test parsing whatweb JSON output."""
        whatweb_json = '''[{"target":"http://example.com","plugins":{"Apache":{"version":["2.4.41"]},"PHP":{"version":["7.4"]},"jQuery":{}}}]'''
        
        findings = whatweb.whatweb_parser(stdout=whatweb_json, stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        
        assert len(findings) >= 2  # At least Apache and PHP
        assert all(f.type == "technology" for f in findings)

    def test_whatweb_empty_output(self):
        """Test handling of empty output."""
        findings = whatweb.whatweb_parser(stdout="", stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        assert findings == []

    def test_whatweb_version_extraction(self):
        """Test that versions are extracted properly."""
        whatweb_json = '''[{"target":"http://example.com","plugins":{"nginx":{"version":["1.18.0"]}}}]'''
        
        findings = whatweb.whatweb_parser(stdout=whatweb_json, stderr='', exit_code=0, agent_id=str(uuid.uuid4()), target="example.com")
        
        assert len(findings) == 1
        assert "1.18.0" in findings[0].evidence
