import pytest
import uuid
from pathlib import Path
from cyberred.tools.parsers.nuclei import nuclei_parser

@pytest.mark.integration
def test_nuclei_parser_json_integration():
    fixture_path = Path("tests/fixtures/tool_outputs/nuclei_json_basic.json")
    stdout = fixture_path.read_text()
    
    agent_id = str(uuid.uuid4())
    findings = nuclei_parser(stdout, "", 0, agent_id, "192.168.1.1")
    
    assert len(findings) == 1
    f = findings[0]
    assert f.type == "cve"
    assert "CVE: CVE-2021-44228" in f.evidence
    assert f.severity == "critical"
    assert f.agent_id == agent_id

@pytest.mark.integration
def test_nuclei_parser_plain_integration():
    fixture_path = Path("tests/fixtures/tool_outputs/nuclei.txt")
    stdout = fixture_path.read_text()
    
    agent_id = str(uuid.uuid4())
    findings = nuclei_parser(stdout, "", 0, agent_id, "192.168.1.1")
    
    # nuclei.txt contains 2 findings and some logs
    assert len(findings) == 2
    
    f1 = findings[0]
    assert f1.type == "cve"
    assert "CVE-2021-44228" in f1.evidence
    
    f2 = findings[1]
    assert f2.type == "vulnerability"
    assert "Apache/2.4.52" in f2.evidence


@pytest.mark.integration
def test_nuclei_parser_json_multi_integration():
    """Test multi-finding JSON fixture."""
    fixture_path = Path("tests/fixtures/tool_outputs/nuclei_json_multi.json")
    stdout = fixture_path.read_text()
    
    agent_id = str(uuid.uuid4())
    findings = nuclei_parser(stdout, "", 0, agent_id, "192.168.1.1")
    
    assert len(findings) == 2
    assert findings[0].type == "vulnerability"
    assert findings[1].type == "vulnerability"


@pytest.mark.integration
def test_nuclei_parser_json_exposure_integration():
    """Test exposure/misconfiguration findings fixture."""
    fixture_path = Path("tests/fixtures/tool_outputs/nuclei_json_exposure.json")
    stdout = fixture_path.read_text()
    
    agent_id = str(uuid.uuid4())
    findings = nuclei_parser(stdout, "", 0, agent_id, "192.168.1.1")
    
    assert len(findings) == 2
    
    # First finding should be exposure type
    f1 = findings[0]
    assert f1.type == "exposure"
    assert f1.severity == "medium"
    assert "exposed-git" in f1.evidence
    
    # Second finding should be misconfiguration type
    f2 = findings[1]
    assert f2.type == "misconfiguration"
    assert f2.severity == "low"
    assert "php-info" in f2.evidence


@pytest.mark.integration
def test_nuclei_parser_plain_new_fixture_integration():
    """Test the nuclei_plain.txt fixture."""
    fixture_path = Path("tests/fixtures/tool_outputs/nuclei_plain.txt")
    stdout = fixture_path.read_text()
    
    agent_id = str(uuid.uuid4())
    findings = nuclei_parser(stdout, "", 0, agent_id, "192.168.1.1")
    
    assert len(findings) == 3
    
    # CVE finding
    assert findings[0].type == "cve"
    assert findings[0].severity == "critical"
    
    # Exposed-git (not a CVE template)
    assert findings[1].type == "vulnerability"
    assert findings[1].severity == "medium"
    
    # Tech detect
    assert findings[2].type == "vulnerability"
    assert findings[2].severity == "info"
