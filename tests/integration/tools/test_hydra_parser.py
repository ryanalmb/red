import pytest
import uuid
from pathlib import Path
from cyberred.tools.parsers import hydra_parser

FIXTURES_DIR = Path("/root/red/fixtures/tool_outputs")

def test_hydra_integration_fixture():
    """Verify hydra parser handles the verification fixture correctly."""
    fixture_path = FIXTURES_DIR / "hydra_results.txt"
    if not fixture_path.exists():
        pytest.skip("hydra fixture not found")
        
    with open(fixture_path, "r") as f:
        content = f.read()
        
    findings = hydra_parser(content, str(uuid.uuid4()), "192.168.1.5")
    assert len(findings) == 2
    assert findings[0].tool == "hydra"
