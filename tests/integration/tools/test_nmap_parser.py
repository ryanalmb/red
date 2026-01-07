
import pytest
import uuid
from pathlib import Path
from cyberred.tools.parsers.nmap import nmap_parser


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent.parent.parent / "fixtures" / "tool_outputs"


@pytest.mark.integration
def test_nmap_parser_integration_basic(fixtures_dir):
    """Test parsing basic nmap XML fixture."""
    xml_path = fixtures_dir / "nmap_xml_basic.xml"
    content = xml_path.read_text()
    
    agent_id = str(uuid.uuid4())
    target = "192.168.1.10"
    
    findings = nmap_parser(content, "", 0, agent_id, target)
    
    # Check open port finding
    ssh_findings = [f for f in findings if f.type == "open_port" and "22/tcp" in f.evidence]
    assert len(ssh_findings) == 1
    f = ssh_findings[0]
    assert f.target == target
    assert "OpenSSH 8.2p1 Ubuntu" in f.evidence
    
    # Check host status finding
    status_findings = [f for f in findings if f.type == "host_status"]
    assert len(status_findings) == 1
    assert "Host is up" in status_findings[0].evidence


@pytest.mark.integration
def test_nmap_parser_integration_os(fixtures_dir):
    """Test parsing OS detection fixture."""
    xml_path = fixtures_dir / "nmap_xml_os.xml"
    content = xml_path.read_text()
    
    agent_id = str(uuid.uuid4())
    target = "192.168.1.11"
    
    findings = nmap_parser(content, "", 0, agent_id, target)
    
    os_findings = [f for f in findings if f.type == "os_detection"]
    assert len(os_findings) == 1
    assert "Linux 5.4" in os_findings[0].evidence
    assert "(100%)" in os_findings[0].evidence


@pytest.mark.integration
def test_nmap_parser_integration_scripts(fixtures_dir):
    """Test parsing NSE scripts fixture."""
    xml_path = fixtures_dir / "nmap_xml_scripts.xml"
    content = xml_path.read_text()
    
    agent_id = str(uuid.uuid4())
    target = "192.168.1.12"
    
    findings = nmap_parser(content, "", 0, agent_id, target)
    
    # Port script
    port_scripts = [f for f in findings if f.type == "nse_script" and "ssh-hostkey" in f.evidence]
    assert len(port_scripts) == 1
    
    # Host script (via <hostscript><script.../></hostscript>)
    host_scripts = [f for f in findings if f.type == "nse_script" and "smb-os-discovery" in f.evidence]
    assert len(host_scripts) == 1
    assert "Windows 10" in host_scripts[0].evidence


@pytest.mark.integration
def test_nmap_parser_integration_grepable(fixtures_dir):
    """Test parsing grepable format fixture."""
    grepable_path = fixtures_dir / "nmap_grepable.txt"
    content = grepable_path.read_text()
    
    agent_id = str(uuid.uuid4())
    target = "192.168.1.100"
    
    findings = nmap_parser(content, "", 0, agent_id, target)
    
    # Check host status finding
    status_findings = [f for f in findings if f.type == "host_status"]
    assert len(status_findings) == 1
    assert "up" in status_findings[0].evidence.lower()
    
    # Check open port findings (22 and 80 are open, 443 is closed)
    port_findings = [f for f in findings if f.type == "open_port"]
    assert len(port_findings) == 2
    evidence_str = " ".join([f.evidence for f in port_findings])
    assert "22/tcp" in evidence_str
    assert "80/tcp" in evidence_str

