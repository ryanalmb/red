import pytest
import uuid
from typing import List
from cyberred.core.models import Finding
from cyberred.tools.parsers import ffuf

def test_ffuf_parser_signature():
    """Test that ffuf_parser matches the ParserFn signature."""
    # ParserFn: (stdout: str, agent_id: str, target: str) -> List[Finding]
    assert hasattr(ffuf, 'ffuf_parser')
    assert callable(ffuf.ffuf_parser)
    
    # Verify it accepts the arguments and returns list
    # We pass empty JSON to avoid parsing error if already implemented, 
    # but initially it might fail if not implemented.
    # For now just checking signature via invocation
    try:
        result = ffuf.ffuf_parser(
            stdout='{"results": []}',
            agent_id=str(uuid.uuid4()),
            target="test-target"
        )
        assert isinstance(result, list)
    except Exception as e:
        # If it raises NotImplementedError or similar, that's fine for now, 
        # but we want to assert it exists. 
        # Actually creating the file with just the function def is the goal.
        # But for RED test, we expect import error or attribute error.
        pytest.fail(f"ffuf_parser raised unexpected exception: {e}")

def test_ffuf_json_parsing():
    """Test that parser correctly handles ffuf JSON structure."""
    ffuf_json = """
    {
        "commandline": "ffuf -u http://10.10.10.10/FUZZ -w wordlist.txt",
        "time": "2021-01-01T00:00:00Z",
        "results": [
            {
                "input": {"FUZZ": "admin"},
                "position": 1,
                "status": 301,
                "length": 123,
                "words": 20,
                "lines": 5,
                "content_type": "text/html",
                "redirectlocation": "http://10.10.10.10/admin/",
                "resultfile": "",
                "url": "http://10.10.10.10/admin",
                "host": "10.10.10.10"
            }
        ]
    }
    """
    
    agent_id_val = str(uuid.uuid4())
    findings = ffuf.ffuf_parser(
        stdout=ffuf_json,
        agent_id=agent_id_val,
        target="10.10.10.10"
    )
    
    assert len(findings) == 1
    finding = findings[0]
    assert finding.target == "10.10.10.10"
    assert "admin" in finding.evidence
    # Check that it uses the common type/topic logic (to be refined in Task 4, but basic check now)
    # Actually Task 4 is specific about type logic, but for now we expect at least a Finding.

def test_ffuf_invalid_json():
    """Test that parser handles invalid JSON gracefully."""
    invalid_json = "not valid json at all"
    
    findings = ffuf.ffuf_parser(
        stdout=invalid_json,
        agent_id=str(uuid.uuid4()),
        target="example.com"
    )
    
    # Should return empty list on invalid JSON
    assert findings == []


def test_ffuf_finding_types():
    """Test that parser distinguishes between file and directory types."""
    # Sample with trailing slash (directory) and without (file)
    ffuf_json = """
    {
        "results": [
            {
                "input": {"FUZZ": "dir/"},
                "status": 200,
                "length": 0, "words": 0, "lines": 0,
                "url": "http://example.com/dir/",
                "host": "example.com"
            },
            {
                "input": {"FUZZ": "file.txt"},
                "status": 200,
                "length": 0, "words": 0, "lines": 0,
                "url": "http://example.com/file.txt",
                "host": "example.com"
            }
        ]
    }
    """
    
    findings = ffuf.ffuf_parser(
        stdout=ffuf_json,
        agent_id=str(uuid.uuid4()),
        target="example.com"
    )
    
    assert len(findings) == 2
    
    # Check directory finding
    dir_finding = next((f for f in findings if "/dir/" in f.evidence), None)
    assert dir_finding is not None
    assert dir_finding.type == "directory"
    assert "directory" in dir_finding.topic
    
    # Check file finding
    file_finding = next((f for f in findings if "file.txt" in f.evidence), None)
    assert file_finding is not None
    assert file_finding.type == "file"
    assert "file" in file_finding.topic
