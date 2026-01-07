import pytest
import uuid
from pathlib import Path
from cyberred.tools.parsers import ffuf_parser

FIXTURES_DIR = Path("/root/red/fixtures/tool_outputs")

def test_ffuf_integration_fixture():
    """Verify ffuf parser handles the verification fixture correctly."""
    fixture_path = FIXTURES_DIR / "ffuf_results.json"
    if not fixture_path.exists():
        pytest.skip("ffuf fixture not found")
        
    with open(fixture_path, "r") as f:
        content = f.read()
        
    findings = ffuf_parser(content, str(uuid.uuid4()), "10.10.10.10")
    assert len(findings) == 2
    assert findings[0].tool == "ffuf"
