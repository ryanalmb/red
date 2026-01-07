import pytest
import uuid
from pathlib import Path
from cyberred.tools.parsers import nikto_parser

FIXTURES_DIR = Path("/root/red/fixtures/tool_outputs")

def test_nikto_integration_fixture():
    """Verify nikto parser handles the verification fixture correctly."""
    fixture_path = FIXTURES_DIR / "nikto_results.txt"
    if not fixture_path.exists():
        pytest.skip("nikto fixture not found")
        
    with open(fixture_path, "r") as f:
        content = f.read()
        
    findings = nikto_parser(content, str(uuid.uuid4()), "example.com")
    assert len(findings) == 3
    assert findings[0].tool == "nikto"
