import pytest
import os
import uuid
from pathlib import Path
from cyberred.tools.parsers import ffuf_parser, nikto_parser, hydra_parser

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
