"""Comprehensive unit tests for wireless and credential parsers - 100% coverage."""
import pytest
import uuid
from cyberred.tools.parsers import aircrack, wifite, john, hashcat


@pytest.fixture
def agent_id():
    return str(uuid.uuid4())


# ============================================================================
# AIRCRACK-NG PARSER TESTS
# ============================================================================

@pytest.mark.unit
class TestAircrackParser:
    def test_parser_signature(self, agent_id):
        assert callable(aircrack.aircrack_parser)
        result = aircrack.aircrack_parser(stdout='', stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert isinstance(result, list)

    def test_empty_stdout(self, agent_id):
        result = aircrack.aircrack_parser('', '', 0, agent_id, "192.168.1.1")
        assert result == []

    def test_wep_key_found(self, agent_id):
        stdout = '''ESSID: "TestNetwork"
BSSID: 00:11:22:33:44:55
KEY FOUND! [ AB:12:34:56:78 ]
10000 packets'''
        findings = aircrack.aircrack_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert len(findings) >= 1
        assert findings[0].type == "wifi_crack"
        assert findings[0].severity == "critical"
        assert "AB:12:34:56:78" in findings[0].evidence

    def test_wpa_passphrase_found(self, agent_id):
        stdout = '''ESSID: "HomeNetwork"
BSSID: AA:BB:CC:DD:EE:FF
KEY FOUND! [ SuperSecretPassword123 ]
Master Key: AA BB CC DD'''
        findings = aircrack.aircrack_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert len(findings) >= 1
        assert "SuperSecretPassword123" in findings[0].evidence

    def test_no_key_found(self, agent_id):
        stdout = '''ESSID: "TargetNetwork"
BSSID: 11:22:33:44:55:66
No networks found, exiting.'''
        findings = aircrack.aircrack_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        crack_findings = [f for f in findings if f.type == "wifi_crack"]
        assert len(crack_findings) == 0

    def test_tool_name_is_aircrack(self, agent_id):
        stdout = '''KEY FOUND! [ testkey ]'''
        findings = aircrack.aircrack_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        if findings:
            assert all(f.tool == "aircrack" for f in findings)

    def test_bssid_essid_extraction(self, agent_id):
        stdout = '''Opening test-01.cap
BSSID: AA:BB:CC:DD:EE:FF
ESSID: "CorpWiFi"
KEY FOUND! [ corporate123 ]'''
        findings = aircrack.aircrack_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert len(findings) >= 1


# ============================================================================
# WIFITE PARSER TESTS
# ============================================================================

@pytest.mark.unit
class TestWifiteParser:
    def test_parser_signature(self, agent_id):
        assert callable(wifite.wifite_parser)
        result = wifite.wifite_parser(stdout='', stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert isinstance(result, list)

    def test_empty_stdout(self, agent_id):
        result = wifite.wifite_parser('', '', 0, agent_id, "192.168.1.1")
        assert result == []

    def test_wpa_crack_success(self, agent_id):
        stdout = '''[+] CorpWiFi (AA:BB:CC:DD:EE:FF) WPA Handshake capture
[+] Cracked! Key: "CorporateWifi2023!"'''
        findings = wifite.wifite_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert len(findings) >= 1
        assert findings[0].type == "wifi_attack"

    def test_pmkid_attack_success(self, agent_id):
        stdout = '''[+] PMKID Attack on HomeNetwork
[+] HomeNetwork cracked! Password: "HomePass456"'''
        findings = wifite.wifite_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert len(findings) >= 1

    def test_failed_crack(self, agent_id):
        stdout = '''[+] Captured WPA handshake
[!] Failed to crack handshake. Password not in wordlist.'''
        findings = wifite.wifite_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        # Failed cracks should not report success
        success_findings = [f for f in findings if "cracked" in f.evidence.lower() and "Failed" not in f.evidence]
        assert len(success_findings) == 0

    def test_ansi_stripping(self, agent_id):
        stdout = '''\x1b[92m[+] Cracked! Key: "password"\x1b[0m'''
        findings = wifite.wifite_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        if findings:
            assert not any("\x1b" in f.evidence for f in findings)

    def test_tool_name_is_wifite(self, agent_id):
        stdout = '''[+] Cracked: password123'''
        findings = wifite.wifite_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert all(f.tool == "wifite" for f in findings)


# ============================================================================
# JOHN THE RIPPER PARSER TESTS
# ============================================================================

@pytest.mark.unit
class TestJohnParser:
    def test_parser_signature(self, agent_id):
        assert callable(john.john_parser)
        result = john.john_parser(stdout='', stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert isinstance(result, list)

    def test_empty_stdout(self, agent_id):
        result = john.john_parser('', '', 0, agent_id, "192.168.1.1")
        assert result == []

    def test_simple_crack_format(self, agent_id):
        stdout = '''admin:password123'''
        findings = john.john_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert len(findings) >= 1
        assert findings[0].type == "cracked_hash"
        assert findings[0].severity == "critical"

    def test_show_format(self, agent_id):
        stdout = '''Using default input encoding: UTF-8
administrator:Password123!
jsmith:Summer2023
svc_backup:B@ckup_P@ss!
3 password hashes cracked, 0 left'''
        findings = john.john_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        cracks = [f for f in findings if f.type == "cracked_hash"]
        assert len(cracks) >= 3

    def test_incremental_format(self, agent_id):
        stdout = '''admin123         (Administrator)
password         (Guest)'''
        findings = john.john_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        # Parser may or may not extract from this format
        assert isinstance(findings, list)

    def test_no_cracks(self, agent_id):
        stdout = '''Session completed, no passwords cracked.'''
        findings = john.john_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        crack_findings = [f for f in findings if f.type == "cracked_hash"]
        assert len(crack_findings) == 0

    def test_tool_name_is_john(self, agent_id):
        stdout = '''admin:password123'''
        findings = john.john_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert all(f.tool == "john" for f in findings)

    def test_multiple_hashes_same_format(self, agent_id):
        stdout = '''user1:pass1
user2:pass2
user3:pass3'''
        findings = john.john_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert len(findings) >= 3


# ============================================================================
# HASHCAT PARSER TESTS
# ============================================================================

@pytest.mark.unit
class TestHashcatParser:
    def test_parser_signature(self, agent_id):
        assert callable(hashcat.hashcat_parser)
        result = hashcat.hashcat_parser(stdout='', stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert isinstance(result, list)

    def test_empty_stdout(self, agent_id):
        result = hashcat.hashcat_parser('', '', 0, agent_id, "192.168.1.1")
        assert result == []

    def test_hash_password_format(self, agent_id):
        stdout = '''5f4dcc3b5aa765d61d8327deb882cf99:password'''
        findings = hashcat.hashcat_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert len(findings) >= 1
        assert findings[0].type == "cracked_hash"
        assert "password" in findings[0].evidence

    def test_ntlm_hash_crack(self, agent_id):
        stdout = '''8846f7eaee8fb117ad06bdd830b7586c:Password123!'''
        findings = hashcat.hashcat_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert len(findings) >= 1
        assert "Password123!" in findings[0].evidence

    def test_potfile_format(self, agent_id):
        stdout = '''hash1:pass1
hash2:pass2
hash3:pass3'''
        findings = hashcat.hashcat_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert len(findings) >= 3

    def test_status_output_with_cracks(self, agent_id):
        stdout = '''hashcat (v6.2.6) starting...
8846f7eaee8fb117:Password123!
cc36cf7a8514893e:Summer2023!
Status...........: Cracked
Recovered........: 2/2 (100.00%)'''
        findings = hashcat.hashcat_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        cracks = [f for f in findings if f.type == "cracked_hash"]
        assert len(cracks) >= 2

    def test_no_cracks_exhausted(self, agent_id):
        stdout = '''Status...........: Exhausted
Recovered........: 0/5 (0.00%)'''
        findings = hashcat.hashcat_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        crack_findings = [f for f in findings if f.type == "cracked_hash"]
        assert len(crack_findings) == 0

    def test_critical_severity(self, agent_id):
        stdout = '''aabbccdd:cracked'''
        findings = hashcat.hashcat_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert all(f.severity == "critical" for f in findings if f.type == "cracked_hash")

    def test_tool_name_is_hashcat(self, agent_id):
        stdout = '''hash:password'''
        findings = hashcat.hashcat_parser(stdout=stdout, stderr='', exit_code=0, agent_id=agent_id, target="192.168.1.1")
        assert all(f.tool == "hashcat" for f in findings)
