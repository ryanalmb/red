
import pytest
from cyberred.tools.parsers.base import ParserFn
from cyberred.tools.parsers.nmap import nmap_parser


@pytest.mark.unit
class TestNmapParserSignature:
    """Task 1: Parser signature tests."""
    
    def test_nmap_parser_signature(self):
        """Task 1 [RED]: Verify nmap_parser exists and matches ParserFn signature."""
        # Verify it's a callable
        assert callable(nmap_parser)
        
        # Verify signature annotations match ParserFn
        annotations = nmap_parser.__annotations__
        assert annotations['stdout'] == str
        assert annotations['exit_code'] == int
        assert 'return' in annotations


@pytest.mark.unit
class TestNmapParserXml:
    """Task 2-8: XML parsing tests."""
    
    def test_nmap_parser_invalid_xml(self):
        """Task 2 [RED]: Parser returns empty list for invalid/empty XML."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        findings = nmap_parser("invalid xml", "", 0, uuid_str, "target-1")
        assert findings == []
        
        findings = nmap_parser("", "", 0, uuid_str, "target-1")
        assert findings == []

    def test_nmap_parser_basic_structure(self):
        """Task 2 [RED]: Parser correctly parses <nmaprun> root element."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        xml = """<?xml version="1.0"?>
        <nmaprun scanner="nmap" args="nmap -sV -oX - 127.0.0.1" start="1672531200">
        </nmaprun>
        """
        findings = nmap_parser(xml, "", 0, uuid_str, "target-1")
        assert isinstance(findings, list)
        # Even empty nmaprun should process without error

    def test_nmap_parser_open_ports(self):
        """Task 3 [RED]: Parser extracts open ports from XML."""
        xml = """<?xml version="1.0"?>
        <nmaprun scanner="nmap" args="nmap -sV -oX - 127.0.0.1" start="1672531200">
          <host>
            <status state="up"/>
            <address addr="127.0.0.1" addrtype="ipv4"/>
            <ports>
              <port protocol="tcp" portid="22">
                <state state="open"/>
                <service name="ssh" product="OpenSSH" version="8.9"/>
              </port>
              <port protocol="tcp" portid="80">
                <state state="closed"/>
              </port>
            </ports>
          </host>
        </nmaprun>
        """
        # Needs 1 finding (port 22 open)
        agent_id = "00000000-0000-0000-0000-000000000001"
        findings = nmap_parser(xml, "", 0, agent_id, "127.0.0.1")
        
        port_findings = [f for f in findings if f.type == "open_port"]
        assert len(port_findings) == 1
        f = port_findings[0]
        assert f.type == "open_port"
        assert f.target == "127.0.0.1"
        assert f.agent_id == agent_id
        assert "22/tcp open ssh OpenSSH 8.9" in f.evidence

    def test_nmap_parser_host_status(self):
        """Task 6 [RED]: Parser detects host up/down from <status>."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        xml = """<?xml version="1.0"?>
        <nmaprun scanner="nmap" args="nmap -sV -oX - 127.0.0.1" start="1672531200">
          <host>
            <status state="up"/>
            <address addr="10.0.0.1" addrtype="ipv4"/>
            <ports></ports>
          </host>
        </nmaprun>
        """
        findings = nmap_parser(xml, "", 0, uuid_str, "127.0.0.1")
        
        # Should have 1 finding for host status
        host_status_findings = [f for f in findings if f.type == "host_status"]
        assert len(host_status_findings) == 1
        f = host_status_findings[0]
        assert f.type == "host_status"
        assert f.target == "10.0.0.1"  # Should extract addr
        assert f.severity == "info"
        assert "Host is up" in f.evidence

    def test_nmap_parser_os_detection(self):
        """Task 7 [RED]: Parser extracts OS detection results."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        xml = """<?xml version="1.0"?>
        <nmaprun scanner="nmap" args="nmap -O -oX - 127.0.0.1" start="1672531200">
          <host>
            <status state="up"/>
            <address addr="10.0.0.1" addrtype="ipv4"/>
            <os>
              <portused state="open" proto="tcp" portid="22"/>
              <osmatch name="Linux 5.4" accuracy="100" line="65535">
                <osclass type="general purpose" vendor="Linux" osfamily="Linux" osgen="5.X" accuracy="100"/>
              </osmatch>
              <osmatch name="Linux 4.19" accuracy="95" line="65535"/>
            </os>
            <ports></ports>
          </host>
        </nmaprun>
        """
        findings = nmap_parser(xml, "", 0, uuid_str, "127.0.0.1")
        
        # Needs host_status + os_detection
        os_findings = [f for f in findings if f.type == "os_detection"]
        assert len(os_findings) == 1
        f = os_findings[0]
        assert f.target == "10.0.0.1"
        assert f.evidence == "OS Match: Linux 5.4 (100%)"

    def test_nmap_parser_nse_scripts(self):
        """Task 8 [RED]: Parser extracts NSE script output."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        xml = """<?xml version="1.0"?>
        <nmaprun scanner="nmap" args="nmap -sC -oX - 127.0.0.1" start="1672531200">
          <host>
            <status state="up"/>
            <address addr="10.0.0.1" addrtype="ipv4"/>
            <ports>
              <port protocol="tcp" portid="22">
                <state state="open"/>
                <script id="ssh-hostkey" output="key data..."/>
              </port>
            </ports>
          </host>
        </nmaprun>
        """
        findings = nmap_parser(xml, "", 0, uuid_str, "127.0.0.1")
        
        # Needs host_status + open_port + nse_script
        script_findings = [f for f in findings if f.type == "nse_script"]
        assert len(script_findings) == 1
        f = script_findings[0]
        assert f.target == "10.0.0.1"
        assert "Script: ssh-hostkey" in f.evidence
        assert "key data..." in f.evidence

    def test_nmap_parser_direct_host_script(self):
        """Test parser extracts direct <script> under <host> (line 77-78 coverage)."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        xml = """<?xml version="1.0"?>
        <nmaprun scanner="nmap" args="nmap -sC -oX - 192.168.1.50">
          <host>
            <status state="up"/>
            <address addr="192.168.1.50" addrtype="ipv4"/>
            <script id="broadcast-ping" output="Host 192.168.1.1 is up."/>
            <ports></ports>
          </host>
        </nmaprun>
        """
        findings = nmap_parser(xml, "", 0, uuid_str, "192.168.1.50")
        
        script_findings = [f for f in findings if f.type == "nse_script"]
        assert len(script_findings) == 1
        f = script_findings[0]
        assert "broadcast-ping" in f.evidence
        assert "Host 192.168.1.1 is up" in f.evidence

    def test_nmap_parser_hostscript_element(self):
        """Test parser extracts scripts under <hostscript> (line 81-82 coverage)."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        xml = """<?xml version="1.0"?>
        <nmaprun scanner="nmap" args="nmap -sC -oX - 192.168.1.12">
          <host>
            <status state="up"/>
            <address addr="192.168.1.12" addrtype="ipv4"/>
            <ports></ports>
            <hostscript>
                <script id="smb-os-discovery" output="OS: Windows 10"/>
            </hostscript>
          </host>
        </nmaprun>
        """
        findings = nmap_parser(xml, "", 0, uuid_str, "192.168.1.12")
        
        script_findings = [f for f in findings if f.type == "nse_script"]
        assert len(script_findings) == 1
        f = script_findings[0]
        assert "smb-os-discovery" in f.evidence
        assert "Windows 10" in f.evidence

    def test_nmap_parser_host_no_address(self):
        """Test parser uses target when no address element present."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        xml = """<?xml version="1.0"?>
        <nmaprun scanner="nmap" args="nmap -sV -oX - 10.0.0.99">
          <host>
            <status state="up"/>
            <ports></ports>
          </host>
        </nmaprun>
        """
        findings = nmap_parser(xml, "", 0, uuid_str, "10.0.0.99")
        
        host_status_findings = [f for f in findings if f.type == "host_status"]
        assert len(host_status_findings) == 1
        assert host_status_findings[0].target == "10.0.0.99"

    def test_nmap_parser_host_no_status(self):
        """Test parser handles host without status element."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        xml = """<?xml version="1.0"?>
        <nmaprun scanner="nmap" args="nmap -sV -oX - 10.0.0.99">
          <host>
            <address addr="10.0.0.99" addrtype="ipv4"/>
            <ports>
              <port protocol="tcp" portid="22">
                <state state="open"/>
              </port>
            </ports>
          </host>
        </nmaprun>
        """
        findings = nmap_parser(xml, "", 0, uuid_str, "10.0.0.99")
        
        # Should have open port but no host_status
        host_status_findings = [f for f in findings if f.type == "host_status"]
        assert len(host_status_findings) == 0
        port_findings = [f for f in findings if f.type == "open_port"]
        assert len(port_findings) == 1

    def test_nmap_parser_os_no_match(self):
        """Test parser handles OS element without osmatch (line 60 coverage)."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        xml = """<?xml version="1.0"?>
        <nmaprun scanner="nmap" args="nmap -O -oX - 10.0.0.99">
          <host>
            <status state="up"/>
            <address addr="10.0.0.99" addrtype="ipv4"/>
            <os>
              <portused state="open" proto="tcp" portid="22"/>
            </os>
            <ports></ports>
          </host>
        </nmaprun>
        """
        findings = nmap_parser(xml, "", 0, uuid_str, "10.0.0.99")
        
        os_findings = [f for f in findings if f.type == "os_detection"]
        assert len(os_findings) == 0

    def test_nmap_parser_os_no_accuracy(self):
        """Test parser handles OS match without accuracy."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        xml = """<?xml version="1.0"?>
        <nmaprun scanner="nmap" args="nmap -O -oX - 10.0.0.99">
          <host>
            <status state="up"/>
            <address addr="10.0.0.99" addrtype="ipv4"/>
            <os>
              <osmatch name="Linux 5.x"/>
            </os>
            <ports></ports>
          </host>
        </nmaprun>
        """
        findings = nmap_parser(xml, "", 0, uuid_str, "10.0.0.99")
        
        os_findings = [f for f in findings if f.type == "os_detection"]
        assert len(os_findings) == 1
        # No accuracy suffix
        assert os_findings[0].evidence == "OS Match: Linux 5.x"

    def test_nmap_parser_port_no_service(self):
        """Test parser handles port without service element."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        xml = """<?xml version="1.0"?>
        <nmaprun scanner="nmap" args="nmap -sS -oX - 10.0.0.99">
          <host>
            <status state="up"/>
            <address addr="10.0.0.99" addrtype="ipv4"/>
            <ports>
              <port protocol="tcp" portid="8080">
                <state state="open"/>
              </port>
            </ports>
          </host>
        </nmaprun>
        """
        findings = nmap_parser(xml, "", 0, uuid_str, "10.0.0.99")
        
        port_findings = [f for f in findings if f.type == "open_port"]
        assert len(port_findings) == 1
        assert "8080/tcp open" in port_findings[0].evidence

    def test_nmap_parser_port_no_state_element(self):
        """Test parser skips port without state element."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        xml = """<?xml version="1.0"?>
        <nmaprun scanner="nmap" args="nmap -sS -oX - 10.0.0.99">
          <host>
            <status state="up"/>
            <address addr="10.0.0.99" addrtype="ipv4"/>
            <ports>
              <port protocol="tcp" portid="8080">
              </port>
            </ports>
          </host>
        </nmaprun>
        """
        findings = nmap_parser(xml, "", 0, uuid_str, "10.0.0.99")
        
        port_findings = [f for f in findings if f.type == "open_port"]
        assert len(port_findings) == 0


@pytest.mark.unit
class TestNmapParserGrepable:
    """Task 9: Grepable format parsing tests."""

    def test_grepable_format_detection(self):
        """Task 9 [RED]: Parser detects grepable format."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        grepable = """# Nmap 7.94 scan initiated Mon Jan  6 02:49:00 2026 as: nmap -oG - 192.168.1.100
Host: 192.168.1.100 ()	Status: Up
Host: 192.168.1.100 ()	Ports: 22/open/tcp//ssh//OpenSSH 8.9p1/
# Nmap done at Mon Jan  6 02:49:05 2026 -- 1 IP address (1 host up) scanned in 5.00 seconds
"""
        findings = nmap_parser(grepable, "", 0, uuid_str, "192.168.1.100")
        
        # Should have host_status and open_port findings
        assert len(findings) >= 2
        
        host_status = [f for f in findings if f.type == "host_status"]
        assert len(host_status) == 1
        assert "up" in host_status[0].evidence.lower()
        
        port_findings = [f for f in findings if f.type == "open_port"]
        assert len(port_findings) == 1
        assert "22/tcp" in port_findings[0].evidence
        assert "ssh" in port_findings[0].evidence

    def test_grepable_format_multiple_ports(self):
        """Task 9: Parser extracts multiple ports from grepable format."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        grepable = """# Nmap 7.94 scan initiated Mon Jan  6 02:49:00 2026
Host: 192.168.1.100 ()	Ports: 22/open/tcp//ssh//OpenSSH 8.9/, 80/open/tcp//http//Apache/, 443/closed/tcp//https//
# Nmap done
"""
        findings = nmap_parser(grepable, "", 0, uuid_str, "192.168.1.100")
        
        port_findings = [f for f in findings if f.type == "open_port"]
        # Only open ports should be included (22 and 80), not 443 (closed)
        assert len(port_findings) == 2
        evidence_str = " ".join([f.evidence for f in port_findings])
        assert "22/tcp" in evidence_str
        assert "80/tcp" in evidence_str

    def test_grepable_format_not_detected_for_xml(self):
        """Verify XML is not misidentified as grepable."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        xml = """<?xml version="1.0"?>
        <nmaprun scanner="nmap">
          <host>
            <status state="up"/>
            <address addr="10.0.0.1" addrtype="ipv4"/>
            <ports></ports>
          </host>
        </nmaprun>
        """
        findings = nmap_parser(xml, "", 0, uuid_str, "10.0.0.1")
        
        # Should parse as XML and find host_status
        host_status = [f for f in findings if f.type == "host_status"]
        assert len(host_status) == 1

    def test_grepable_empty_ports_line(self):
        """Test grepable parser handles lines without ports gracefully."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        grepable = """# Nmap 7.94 scan
Host: 192.168.1.100 ()	Status: Up
# Nmap done
"""
        findings = nmap_parser(grepable, "", 0, uuid_str, "192.168.1.100")
        
        # Only host status, no ports
        assert len(findings) == 1
        assert findings[0].type == "host_status"

    def test_grepable_short_port_entry(self):
        """Test grepable parser skips malformed short port entries."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        grepable = """# Nmap 7.94 scan
Host: 192.168.1.100 ()	Ports: 22/open, 80/open/tcp//http//
# Nmap done
"""
        findings = nmap_parser(grepable, "", 0, uuid_str, "192.168.1.100")
        
        # Only port 80 should be parsed (22 is malformed)
        port_findings = [f for f in findings if f.type == "open_port"]
        assert len(port_findings) == 1
        assert "80/tcp" in port_findings[0].evidence

    def test_grepable_malformed_host_line(self):
        """Test grepable parser skips malformed Host: lines (line 204 coverage)."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        # This Host: line has unusual format that doesn't match the regex
        grepable = """# Nmap 7.94 scan
Host:
Host: 192.168.1.100 ()	Status: Up
# Nmap done
"""
        findings = nmap_parser(grepable, "", 0, uuid_str, "192.168.1.100")
        
        # Should parse the valid host line
        assert len(findings) == 1
        assert findings[0].type == "host_status"

    def test_grepable_ports_line_no_match(self):
        """Test grepable parser handles Ports line with no valid content (line 223 coverage)."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        grepable = """# Nmap 7.94 scan
Host: 192.168.1.100 ()	Ports:
# Nmap done
"""
        findings = nmap_parser(grepable, "", 0, uuid_str, "192.168.1.100")
        
        # No ports should be found
        port_findings = [f for f in findings if f.type == "open_port"]
        assert len(port_findings) == 0

    def test_grepable_empty_port_entries_in_list(self):
        """Test grepable parser skips empty entries in port list (line 229 coverage)."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        grepable = """# Nmap 7.94 scan
Host: 192.168.1.100 ()	Ports: 22/open/tcp//ssh//, , , 80/open/tcp//http//
# Nmap done
"""
        findings = nmap_parser(grepable, "", 0, uuid_str, "192.168.1.100")
        
        # Should parse 2 valid ports, skipping empty entries
        port_findings = [f for f in findings if f.type == "open_port"]
        assert len(port_findings) == 2

    def test_grepable_status_no_match(self):
        """Test grepable parser handles Status line that doesn't match regex."""
        uuid_str = "00000000-0000-0000-0000-000000000001"
        grepable = """# Nmap 7.94 scan
Host: 192.168.1.100 ()	Status:
# Nmap done
"""
        findings = nmap_parser(grepable, "", 0, uuid_str, "192.168.1.100")
        
        # Status line exists but has no value, should not create finding
        host_findings = [f for f in findings if f.type == "host_status"]
        assert len(host_findings) == 0

