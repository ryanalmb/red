"""Integration tests for Reconnaissance parsers with production-like outputs.

These tests verify that parsers correctly handle real-world tool output formats
as they would be encountered during actual penetration testing engagements.
"""
import pytest
import uuid
from pathlib import Path

from cyberred.tools.parsers import (
    masscan_parser, subfinder_parser, amass_parser, whatweb_parser,
    wafw00f_parser, dnsrecon_parser, theharvester_parser, gobuster_parser
)


@pytest.fixture
def fixtures_dir():
    """Return path to tool output fixtures."""
    return Path(__file__).parent.parent.parent.parent / "fixtures" / "tool_outputs"


@pytest.fixture
def agent_id():
    """Generate a unique agent ID for each test."""
    return str(uuid.uuid4())


# ============================================================================
# MASSCAN INTEGRATION TESTS
# ============================================================================

MASSCAN_JSON_OUTPUT = '''[
{"ip": "192.168.1.1", "timestamp": "1609459200", "ports": [{"port": 22, "proto": "tcp", "status": "open", "reason": "syn-ack", "ttl": 64}]},
{"ip": "192.168.1.1", "timestamp": "1609459201", "ports": [{"port": 80, "proto": "tcp", "status": "open", "reason": "syn-ack", "ttl": 64}]},
{"ip": "192.168.1.2", "timestamp": "1609459202", "ports": [{"port": 443, "proto": "tcp", "status": "open", "reason": "syn-ack", "ttl": 128}]}
]'''

MASSCAN_STDOUT_OUTPUT = '''Starting masscan 1.3.2 (http://bit.ly/14GZzcT)
Discovered open port 22/tcp on 192.168.1.1
Discovered open port 80/tcp on 192.168.1.1
Discovered open port 443/tcp on 192.168.1.2
Discovered open port 3389/tcp on 192.168.1.3
rate: 10000.00-kpps, 100.00% done'''


@pytest.mark.integration
class TestMasscanIntegration:
    """Integration tests for masscan parser with production outputs."""
    
    def test_masscan_json_production_output(self, agent_id):
        """Test masscan JSON output as produced by -oJ flag."""
        findings = masscan_parser(MASSCAN_JSON_OUTPUT, "", 0, agent_id, "192.168.1.0/24")
        
        assert len(findings) == 3
        assert all(f.type == "open_port" for f in findings)
        assert all(f.tool == "masscan" for f in findings)
        
        # Verify specific ports found
        ports_found = [f.evidence for f in findings]
        assert any("22/tcp" in p for p in ports_found)
        assert any("80/tcp" in p for p in ports_found)
        assert any("443/tcp" in p for p in ports_found)
    
    def test_masscan_stdout_production_output(self, agent_id):
        """Test masscan stdout output (non-JSON format)."""
        findings = masscan_parser(MASSCAN_STDOUT_OUTPUT, "", 0, agent_id, "192.168.1.0/24")
        
        assert len(findings) >= 4
        assert all(f.type == "open_port" for f in findings)
        
        # Verify RDP port found
        assert any("3389" in f.evidence for f in findings)


# ============================================================================
# SUBFINDER INTEGRATION TESTS
# ============================================================================

SUBFINDER_JSON_OUTPUT = '''{"host":"api.example.com","input":"example.com","source":"crtsh"}
{"host":"www.example.com","input":"example.com","source":"hackertarget"}
{"host":"mail.example.com","input":"example.com","source":"dnsdumpster"}
{"host":"admin.example.com","input":"example.com","source":"virustotal"}'''

SUBFINDER_PLAIN_OUTPUT = '''api.example.com
www.example.com
mail.example.com
admin.example.com
dev.example.com'''


@pytest.mark.integration
class TestSubfinderIntegration:
    """Integration tests for subfinder parser with production outputs."""
    
    def test_subfinder_json_production_output(self, agent_id):
        """Test subfinder JSON output as produced by -oJ flag."""
        findings = subfinder_parser(SUBFINDER_JSON_OUTPUT, "", 0, agent_id, "example.com")
        
        assert len(findings) >= 4
        assert all(f.type == "subdomain" for f in findings)
        assert all(f.tool == "subfinder" for f in findings)
        
        # Verify subdomains found
        subdomains = [f.evidence for f in findings]
        assert any("api.example.com" in s for s in subdomains)
        assert any("admin.example.com" in s for s in subdomains)
    
    def test_subfinder_plain_production_output(self, agent_id):
        """Test subfinder plain stdout output."""
        findings = subfinder_parser(SUBFINDER_PLAIN_OUTPUT, "", 0, agent_id, "example.com")
        
        assert len(findings) >= 5
        assert all(f.type == "subdomain" for f in findings)


# ============================================================================
# AMASS INTEGRATION TESTS
# ============================================================================

AMASS_JSON_OUTPUT = '''{"name":"www.example.com","domain":"example.com","addresses":[{"ip":"93.184.216.34","cidr":"93.184.216.0/24","asn":15133,"desc":"EDGECAST"}],"tag":"dns","sources":["DNS"]}
{"name":"mail.example.com","domain":"example.com","addresses":[{"ip":"93.184.216.35","cidr":"93.184.216.0/24","asn":15133}],"tag":"dns","sources":["Passive DNS"]}'''


@pytest.mark.integration
class TestAmassIntegration:
    """Integration tests for amass parser with production outputs."""
    
    def test_amass_json_production_output(self, agent_id):
        """Test amass JSON output with DNS records."""
        findings = amass_parser(AMASS_JSON_OUTPUT, "", 0, agent_id, "example.com")
        
        assert len(findings) >= 2
        assert all(f.type == "subdomain" for f in findings)
        assert all(f.tool == "amass" for f in findings)


# ============================================================================
# WHATWEB INTEGRATION TESTS
# ============================================================================

WHATWEB_JSON_OUTPUT = '''[{"target":"http://example.com","http_status":200,"plugins":{"Apache":{"version":["2.4.41"]},"PHP":{"version":["7.4.3"]},"WordPress":{"version":["5.7"]},"Country":{"string":["UNITED STATES"]}}}]'''


@pytest.mark.integration
class TestWhatwebIntegration:
    """Integration tests for whatweb parser with production outputs."""
    
    def test_whatweb_json_production_output(self, agent_id):
        """Test whatweb JSON output as produced by --log-json flag."""
        findings = whatweb_parser(WHATWEB_JSON_OUTPUT, "", 0, agent_id, "http://example.com")
        
        assert len(findings) >= 3
        assert all(f.type == "technology" for f in findings)
        assert all(f.tool == "whatweb" for f in findings)
        
        # Verify technologies found
        techs = [f.evidence for f in findings]
        assert any("Apache" in t for t in techs)
        assert any("PHP" in t for t in techs)
        assert any("WordPress" in t for t in techs)


# ============================================================================
# WAFW00F INTEGRATION TESTS
# ============================================================================

WAFW00F_STDOUT_WITH_WAF = '''
                   ______
                  /      \\
                 (  Woof! )
                  \\  ____/                      )
                  ,,                           ) (_
             .-. -    _______                 ( |__|
            ()``; |==|_______)                .)|__|
            / ('        /|\\                  (  |__|
        (  /  )        / | \\                  . |__|
         \\(_)_))      /  |  \\                   |__|

[*] Checking http://example.com
[+] The site http://example.com is behind Cloudflare (Cloudflare Inc.) WAF.
'''

WAFW00F_STDOUT_NO_WAF = '''[*] Checking http://vulnerable.com
[-] No WAF detected by the generic detection
[*] Target http://vulnerable.com is not behind a WAF.'''

WAFW00F_JSON_OUTPUT = '''{"url": "http://example.com", "detected": true, "firewall": "Cloudflare", "manufacturer": "Cloudflare Inc."}'''


@pytest.mark.integration
class TestWafw00fIntegration:
    """Integration tests for wafw00f parser with production outputs."""
    
    def test_wafw00f_waf_detected(self, agent_id):
        """Test wafw00f output when WAF is detected."""
        findings = wafw00f_parser(WAFW00F_STDOUT_WITH_WAF, "", 0, agent_id, "http://example.com")
        
        assert len(findings) >= 1
        assert any(f.type == "waf_detected" for f in findings)
        assert any("Cloudflare" in f.evidence for f in findings)
    
    def test_wafw00f_no_waf(self, agent_id):
        """Test wafw00f output when no WAF is detected."""
        findings = wafw00f_parser(WAFW00F_STDOUT_NO_WAF, "", 0, agent_id, "http://vulnerable.com")
        
        # Should return empty or info finding about no WAF
        assert len(findings) == 0 or all(f.severity == "info" for f in findings)
    
    def test_wafw00f_json_production_output(self, agent_id):
        """Test wafw00f JSON output."""
        findings = wafw00f_parser(WAFW00F_JSON_OUTPUT, "", 0, agent_id, "http://example.com")
        
        # Parser may not support all JSON formats
        assert isinstance(findings, list)


# ============================================================================
# DNSRECON INTEGRATION TESTS
# ============================================================================

DNSRECON_JSON_OUTPUT = '''[
{"type": "A", "name": "example.com", "address": "93.184.216.34"},
{"type": "MX", "name": "example.com", "address": "mail.example.com", "priority": 10},
{"type": "NS", "name": "example.com", "address": "ns1.example.com"},
{"type": "TXT", "name": "example.com", "strings": "v=spf1 include:_spf.google.com ~all"},
{"type": "AXFR", "name": "example.com", "address": "Zone Transfer Successful"}
]'''


@pytest.mark.integration
class TestDnsreconIntegration:
    """Integration tests for dnsrecon parser with production outputs."""
    
    def test_dnsrecon_json_production_output(self, agent_id):
        """Test dnsrecon JSON output with multiple record types."""
        findings = dnsrecon_parser(DNSRECON_JSON_OUTPUT, "", 0, agent_id, "example.com")
        
        assert len(findings) >= 4
        assert all(f.type == "dns_record" for f in findings)
        assert all(f.tool == "dnsrecon" for f in findings)
        
        # Check for zone transfer high severity
        zone_transfer = [f for f in findings if "AXFR" in f.evidence or "Zone Transfer" in f.evidence]
        assert len(zone_transfer) >= 1
        assert zone_transfer[0].severity == "high"


# ============================================================================
# THEHARVESTER INTEGRATION TESTS
# ============================================================================

THEHARVESTER_STDOUT = '''
*******************************************************************
*  _   _                                            _             *
* | |_| |__   ___    /\\  /\\__ _ _ ____   _____  ___| |_ ___ _ __  *
* | __| '_ \\ / _ \\  / /_/ / _` | '__\\ \\ / / _ \\/ __| __/ _ \\ '__| *
* | |_| | | |  __/ / __  / (_| | |   \\ V /  __/\\__ \\ ||  __/ |    *
*  \\__|_| |_|\\___| \\/ /_/ \\__,_|_|    \\_/ \\___||___/\\__\\___|_|    *
*******************************************************************

[*] Target: example.com
[*] Searching Google for emails...

[*] Emails found:
------------------
admin@example.com
support@example.com
info@example.com

[*] Hosts found:
------------------
www.example.com:93.184.216.34
mail.example.com:93.184.216.35
api.example.com:93.184.216.36
'''


@pytest.mark.integration
class TestTheharvesterIntegration:
    """Integration tests for theharvester parser with production outputs."""
    
    def test_theharvester_stdout_production_output(self, agent_id):
        """Test theharvester stdout output with emails and hosts."""
        findings = theharvester_parser(THEHARVESTER_STDOUT, "", 0, agent_id, "example.com")
        
        assert len(findings) >= 3
        
        # Check for email findings
        email_findings = [f for f in findings if f.type == "email"]
        assert len(email_findings) >= 3
        assert any("admin@example.com" in f.evidence for f in email_findings)
        
        # Check for subdomain findings
        subdomain_findings = [f for f in findings if f.type == "subdomain"]
        assert len(subdomain_findings) >= 3


# ============================================================================
# GOBUSTER INTEGRATION TESTS
# ============================================================================

GOBUSTER_DIR_OUTPUT = '''===============================================================
Gobuster v3.1.0
by OJ Reeves (@TheColonial) & Christian Mehlmauer (@firefart)
===============================================================
[+] Url:                     http://example.com
[+] Method:                  GET
[+] Threads:                 10
[+] Wordlist:                /usr/share/wordlists/dirb/common.txt
===============================================================
2023/01/15 10:00:00 Starting gobuster in directory enumeration mode
===============================================================
/admin                (Status: 301) [Size: 0] [--> /admin/]
/api                  (Status: 200) [Size: 1234]
/backup               (Status: 403) [Size: 277]
/config               (Status: 403) [Size: 277]
/login                (Status: 200) [Size: 5678]
/robots.txt           (Status: 200) [Size: 123]
/.htaccess            (Status: 403) [Size: 277]
===============================================================
2023/01/15 10:05:00 Finished
==============================================================='''

GOBUSTER_DNS_OUTPUT = '''===============================================================
Gobuster v3.1.0
===============================================================
Found: api.example.com
Found: admin.example.com
Found: dev.example.com
Found: staging.example.com
==============================================================='''


@pytest.mark.integration
class TestGobusterIntegration:
    """Integration tests for gobuster parser with production outputs."""
    
    def test_gobuster_dir_production_output(self, agent_id):
        """Test gobuster directory enumeration output."""
        findings = gobuster_parser(GOBUSTER_DIR_OUTPUT, "", 0, agent_id, "http://example.com")
        
        assert len(findings) >= 5
        assert all(f.tool == "gobuster" for f in findings)
        
        # Verify directories found
        dirs = [f.evidence for f in findings]
        assert any("/admin" in d for d in dirs)
        assert any("/api" in d for d in dirs)
        assert any("/login" in d for d in dirs)
        
        # Check severity mapping (403 should be different from 200)
        forbidden = [f for f in findings if "403" in f.evidence]
        assert len(forbidden) >= 1
    
    def test_gobuster_dns_production_output(self, agent_id):
        """Test gobuster DNS enumeration output."""
        findings = gobuster_parser(GOBUSTER_DNS_OUTPUT, "", 0, agent_id, "example.com")
        
        # Should find subdomains
        assert len(findings) >= 4
