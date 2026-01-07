import pytest
import uuid
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import nikto

def test_nikto_parser_signature():
    """Test that nikto_parser matches the ParserFn signature."""
    assert hasattr(nikto, 'nikto_parser')
    assert callable(nikto.nikto_parser)
    
    try:
        # Pass empty string for now
        result = nikto.nikto_parser(
            stdout="",
            agent_id=str(uuid.uuid4()),
            target="test-target"
        )
        assert isinstance(result, list)
    except Exception as e:
        pytest.fail(f"nikto_parser raised unexpected exception: {e}")

def test_nikto_parsing_osvdb_cve():
    """Test parsing of Nikto output with OSVDB and CVE references."""
    stdout = """
+ OSVDB-1234: /admin/: Potentially interesting archive/cert file found.
+ OSVDB-5678: /path/to/file: Some description.
+ CVE-2023-9999: /vulnerable: Critical vulnerability found.
+ /no/ref: Just a finding without explicit ref code.
    """
    
    findings = nikto.nikto_parser(
        stdout=stdout,
        agent_id=str(uuid.uuid4()),
        target="example.com"
    )
    
    # Check OSVDB finding
    osvdb = next((f for f in findings if "OSVDB-1234" in f.evidence), None)
    assert osvdb is not None
    assert osvdb.type == "web_vuln"
    assert "/admin/" in osvdb.evidence
    # Expect medium severity for non-CVE (as per plan/dev notes)
    # The plan says "severity = 'high' if 'CVE' in ref else 'medium'"
    assert osvdb.severity == "medium"
    
    # Check CVE finding
    cve = next((f for f in findings if "CVE-2023-9999" in f.evidence), None)
    assert cve is not None
    assert cve.severity == "high"
    assert "/vulnerable" in cve.evidence

def test_nikto_parsing_no_plus_prefix():
    """Test parsing logic handles lines that might miss the + prefix."""
    stdout = """
OSVDB-1111: /test: Finding without plus.
+ OSVDB-2222: /test2: Finding with plus.
    """
    findings = nikto.nikto_parser(
        stdout=stdout,
        agent_id=str(uuid.uuid4()),
        target="example.com"
    )
    
    assert len(findings) == 2
    f1 = next((f for f in findings if "OSVDB-1111" in f.evidence), None)
    assert f1 is not None
