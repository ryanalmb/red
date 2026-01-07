# Story 4.10: Tier 1 Parsers - Remaining High-Frequency Tools

Status: done

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD method at all times. All tasks marked [RED], [GREEN], [REFACTOR] must be followed explicitly.

> [!CAUTION]
> **SCALE ALERT:** This is a **large story** implementing 24 parsers. Consider batch implementation using consistent patterns from `common.py`. Each parser category can be developed as a unit, achieving 100% coverage on each before moving to the next.

## Story

As a **developer**,
I want **structured parsers for all remaining high-frequency Kali tools**,
So that **the full ~30 Tier 1 parser requirement is met (FR33)**.

## Acceptance Criteria

1. **Given** Stories 4.5-4.9 are complete (6 parsers: nmap, nuclei, sqlmap, ffuf, nikto, hydra)
   **When** output from any of the 24 remaining high-frequency tools is processed
   **Then** a dedicated Tier 1 parser extracts structured findings

2. **Given** a Reconnaissance tool output (masscan, subfinder, amass, whatweb, wafw00f, dnsrecon, theharvester, gobuster)
   **When** I parse the output
   **Then** findings have appropriate types (open_port, subdomain, technology, waf_detected, dns_record, email, directory, file)

3. **Given** an Exploitation tool output (crackmapexec, responder, impacket-secretsdump, impacket-psexec, metasploit, searchsploit)
   **When** I parse the output
   **Then** findings have appropriate types (credential, share, vuln, shell_access, session, exploit_ref)

4. **Given** a Post-Exploitation tool output (mimikatz, bloodhound, linpeas, winpeas, lazagne, chisel)
   **When** I parse the output
   **Then** findings have appropriate types (credential, ad_object, privesc_vector, tunnel)

5. **Given** a Wireless tool output (aircrack-ng, wifite)
   **When** I parse the output
   **Then** findings have appropriate types (wifi_crack, wifi_attack)

6. **Given** a Credential tool output (john, hashcat)
   **When** I parse the output
   **Then** findings have appropriate types (cracked_hash)

7. **Given** each parser module
   **When** running unit tests with coverage
   **Then** each parser achieves 100% code coverage

8. **Given** all 24 parsers
   **When** registered with OutputProcessor
   **Then** total Tier 1 parser count is ~30 (6 previous + 24 new)

9. **Given** all parsers
   **When** running integration tests
   **Then** tests verify each parser against sample output fixtures

## Parser Specification Reference

### Reconnaissance Parsers (8 tools)

| Tool | Finding Type | Key Fields | Output Format |
|------|--------------|------------|---------------|
| `masscan` | open_port | port, protocol, ip, rate | JSON (`-oJ`) or stdout |
| `subfinder` | subdomain | hostname, source | JSON (`-oJ`) or stdout |
| `amass` | subdomain | hostname, source, dns_records | JSON or stdout |
| `whatweb` | technology | tech_name, version, url | JSON (`--log-json`) or stdout |
| `wafw00f` | waf_detected | waf_name, url | JSON (`-o`) or stdout |
| `dnsrecon` | dns_record | record_type, name, value | JSON (`-j`) or stdout |
| `theharvester` | email/subdomain | email, hostname, source | XML or stdout |
| `gobuster` | directory/file | path, status_code, size | stdout (regex) |

### Exploitation Parsers (6 tools)

| Tool | Finding Type | Key Fields | Output Format |
|------|--------------|------------|---------------|
| `crackmapexec` | credential/share/vuln | target, username, password, share_name | stdout (regex) |
| `responder` | credential | protocol, client_ip, username, hash | stdout (log format) |
| `impacket-secretsdump` | credential | username, hash_type, hash | stdout (regex) |
| `impacket-psexec` | shell_access | target, username, success | stdout (regex) |
| `metasploit` (msfconsole) | session/vuln | session_id, exploit, target | stdout/JSON |
| `searchsploit` | exploit_ref | edb_id, title, path, platform | JSON (`-j`) or stdout |

### Post-Exploitation Parsers (6 tools)

| Tool | Finding Type | Key Fields | Output Format |
|------|--------------|------------|---------------|
| `mimikatz` | credential | username, domain, password, hash | stdout (regex) |
| `bloodhound` (SharpHound) | ad_object | object_type, name, path_to_da | JSON (BloodHound format) |
| `linpeas` | privesc_vector | vector_type, description, severity | stdout (ANSI colored) |
| `winpeas` | privesc_vector | vector_type, description, severity | stdout (ANSI colored) |
| `lazagne` | credential | application, username, password | stdout (structured) |
| `chisel` | tunnel | local_port, remote_target, status | stdout (regex) |

### Wireless Parsers (2 tools)

| Tool | Finding Type | Key Fields | Output Format |
|------|--------------|------------|---------------|
| `aircrack-ng` | wifi_crack | bssid, essid, key, packets | stdout (regex) |
| `wifite` | wifi_attack | bssid, essid, attack_type, result | stdout (colored) |

### Credential Parsers (2 tools)

| Tool | Finding Type | Key Fields | Output Format |
|------|--------------|------------|---------------|
| `john` | cracked_hash | hash, plaintext, format | stdout (`--show`) |
| `hashcat` | cracked_hash | hash, plaintext, mode, speed | stdout/potfile |

## Tasks / Subtasks

### Phase 0: Setup & Infrastructure [BLUE]

- [x] Task 0.1: Verify `common.py` utilities available
  - [x] Confirm `create_finding` and `generate_topic` from Story 4.9
  - [x] Review import patterns from existing parsers (ffuf, nikto, hydra)

---

### Phase 1: Reconnaissance Parsers [RED → GREEN → REFACTOR]

#### 1A: masscan Parser (AC: 2)

- [x] Task 1.1: Create masscan parser module
  - [x] **[RED]** Write failing test: `masscan_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/masscan.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 1.2: Parse masscan JSON output
  - [x] **[RED]** Write failing test: parser extracts ports from JSON format (`-oJ`)
  - [x] **[GREEN]** Parse JSON array of `{ip, ports: [{port, proto, status}]}`
  - [x] **[REFACTOR]** Handle both JSON and stdout formats

- [x] Task 1.3: Create Findings for open ports
  - [x] **[RED]** Write failing test: findings have `type="open_port"` with port, protocol in evidence
  - [x] **[GREEN]** Call `common.create_finding(type_val="open_port", severity="info", ...)`
  - [x] **[REFACTOR]** Include rate information if available

#### 1B: subfinder Parser (AC: 2)

- [x] Task 1.4: Create subfinder parser module
  - [x] **[RED]** Write failing test: `subfinder_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/subfinder.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 1.5: Parse subfinder output
  - [x] **[RED]** Write failing test: parser extracts hostnames from JSON (`-oJ`)
  - [x] **[RED]** Write failing test: parser extracts hostnames from plain stdout (one per line)
  - [x] **[GREEN]** Auto-detect format and parse accordingly
  - [x] **[REFACTOR]** Extract source information when available

- [x] Task 1.6: Create Findings for subdomains
  - [x] **[RED]** Write failing test: findings have `type="subdomain"` with hostname in evidence
  - [x] **[GREEN]** Call `common.create_finding(type_val="subdomain", severity="info", ...)`
  - [x] **[REFACTOR]** Deduplicate findings

#### 1C: amass Parser (AC: 2)

- [x] Task 1.7: Create amass parser module
  - [x] **[RED]** Write failing test: `amass_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/amass.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 1.8: Parse amass output
  - [x] **[RED]** Write failing test: parser extracts hostnames from JSON output
  - [x] **[RED]** Write failing test: parser extracts DNS records (A, CNAME, MX)
  - [x] **[GREEN]** Parse JSON or stdout format
  - [x] **[REFACTOR]** Include source enumeration method

- [x] Task 1.9: Create Findings for subdomains with DNS
  - [x] **[RED]** Write failing test: findings have `type="subdomain"` with dns_records in evidence
  - [x] **[GREEN]** Call `common.create_finding(...)`
  - [x] **[REFACTOR]** Handle edge cases (no DNS records)

#### 1D: whatweb Parser (AC: 2)

- [x] Task 1.10: Create whatweb parser module
  - [x] **[RED]** Write failing test: `whatweb_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/whatweb.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 1.11: Parse whatweb output
  - [x] **[RED]** Write failing test: parser extracts technologies from JSON (`--log-json`)
  - [x] **[RED]** Write failing test: parser handles multiple plugins detected
  - [x] **[GREEN]** Parse JSON array with technology detections
  - [x] **[REFACTOR]** Handle version extraction

- [x] Task 1.12: Create Findings for technologies
  - [x] **[RED]** Write failing test: findings have `type="technology"` with tech_name, version in evidence
  - [x] **[GREEN]** Call `common.create_finding(...)`
  - [x] **[REFACTOR]** Map severity based on outdated versions

#### 1E: wafw00f Parser (AC: 2)

- [x] Task 1.13: Create wafw00f parser module
  - [x] **[RED]** Write failing test: `wafw00f_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/wafw00f.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 1.14: Parse wafw00f output
  - [x] **[RED]** Write failing test: parser detects WAF presence from stdout
  - [x] **[RED]** Write failing test: parser extracts WAF name when identified
  - [x] **[GREEN]** Parse regex: `is behind (.+) WAF`
  - [x] **[REFACTOR]** Handle "No WAF detected" case

- [x] Task 1.15: Create Findings for WAF detection
  - [x] **[RED]** Write failing test: findings have `type="waf_detected"` with waf_name in evidence
  - [x] **[GREEN]** Call `common.create_finding(..., severity="info")`
  - [x] **[REFACTOR]** Include URL in evidence

#### 1F: dnsrecon Parser (AC: 2)

- [x] Task 1.16: Create dnsrecon parser module
  - [x] **[RED]** Write failing test: `dnsrecon_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/dnsrecon.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 1.17: Parse dnsrecon output
  - [x] **[RED]** Write failing test: parser extracts A records
  - [x] **[RED]** Write failing test: parser extracts MX, NS, TXT records
  - [x] **[GREEN]** Parse JSON (`-j`) or stdout format
  - [x] **[REFACTOR]** Handle zone transfer results

- [x] Task 1.18: Create Findings for DNS records
  - [x] **[RED]** Write failing test: findings have `type="dns_record"` with record_type, name, value
  - [x] **[GREEN]** Call `common.create_finding(...)`
  - [x] **[REFACTOR]** Flag zone transfer as "high" severity

#### 1G: theharvester Parser (AC: 2)

- [x] Task 1.19: Create theharvester parser module
  - [x] **[RED]** Write failing test: `theharvester_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/theharvester.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 1.20: Parse theharvester output
  - [x] **[RED]** Write failing test: parser extracts emails
  - [x] **[RED]** Write failing test: parser extracts hostnames/subdomains
  - [x] **[GREEN]** Parse XML or stdout format
  - [x] **[REFACTOR]** Include source information

- [x] Task 1.21: Create Findings for emails and subdomains
  - [x] **[RED]** Write failing test: email findings have `type="email"`, subdomain findings have `type="subdomain"`
  - [x] **[GREEN]** Call `common.create_finding(..., severity="info")`
  - [x] **[REFACTOR]** Deduplicate results

#### 1H: gobuster Parser (AC: 2)

- [x] Task 1.22: Create gobuster parser module
  - [x] **[RED]** Write failing test: `gobuster_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/gobuster.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 1.23: Parse gobuster output
  - [x] **[RED]** Write failing test: parser extracts paths with status codes
  - [x] **[RED]** Write failing test: parser determines directory vs file
  - [x] **[GREEN]** Parse stdout regex: `/path (Status: 200) [Size: 1234]`
  - [x] **[REFACTOR]** Handle different gobuster modes (dir, dns, vhost)

- [x] Task 1.24: Create Findings for discovered paths
  - [x] **[RED]** Write failing test: findings have `type="directory"` or `type="file"`
  - [x] **[GREEN]** Call `common.create_finding(...)`
  - [x] **[REFACTOR]** Map severity based on status codes (403 vs 200)

---

### Phase 2: Exploitation Parsers [RED → GREEN → REFACTOR]

#### 2A: crackmapexec Parser (AC: 3)

- [x] Task 2.1: Create crackmapexec parser module
  - [x] **[RED]** Write failing test: `crackmapexec_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/crackmapexec.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 2.2: Parse crackmapexec output
  - [x] **[RED]** Write failing test: parser extracts successful credentials `[+]`
  - [x] **[RED]** Write failing test: parser extracts share enumeration
  - [x] **[RED]** Write failing test: parser extracts vulnerability checks (LAPS, GPP, etc.)
  - [x] **[GREEN]** Parse stdout regex patterns for each type
  - [x] **[REFACTOR]** Handle SMB, WinRM, LDAP protocols

- [x] Task 2.3: Create Findings for CME results
  - [x] **[RED]** Write failing test: credential findings have `type="credential"`, `severity="critical"`
  - [x] **[RED]** Write failing test: share findings have `type="share"`, `severity="info"`
  - [x] **[GREEN]** Call `common.create_finding(...)`
  - [x] **[REFACTOR]** Include protocol in evidence

#### 2B: responder Parser (AC: 3)

- [x] Task 2.4: Create responder parser module
  - [x] **[RED]** Write failing test: `responder_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/responder.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 2.5: Parse responder output
  - [x] **[RED]** Write failing test: parser extracts NTLMv2 hashes
  - [x] **[RED]** Write failing test: parser extracts client IP and username
  - [x] **[GREEN]** Parse log format: `[SMB] NTLMv2 Hash : username::DOMAIN:...`
  - [x] **[REFACTOR]** Handle multiple protocols (SMB, HTTP, LDAP)

- [x] Task 2.6: Create Findings for captured credentials
  - [x] **[RED]** Write failing test: findings have `type="credential"` with hash in evidence
  - [x] **[GREEN]** Call `common.create_finding(..., severity="high")`
  - [x] **[REFACTOR]** Include protocol and client_ip

#### 2C: impacket-secretsdump Parser (AC: 3)

- [x] Task 2.7: Create secretsdump parser module
  - [x] **[RED]** Write failing test: `secretsdump_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/secretsdump.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 2.8: Parse secretsdump output
  - [x] **[RED]** Write failing test: parser extracts NTLM hashes
  - [x] **[RED]** Write failing test: parser extracts Kerberos keys
  - [x] **[RED]** Write failing test: parser extracts cleartext passwords (when available)
  - [x] **[GREEN]** Parse stdout: `username:rid:lmhash:nthash:::`
  - [x] **[REFACTOR]** Handle different dump sections (SAM, LSA, NTDS)

- [x] Task 2.9: Create Findings for dumped credentials
  - [x] **[RED]** Write failing test: findings have `type="credential"` with hash_type in evidence
  - [x] **[GREEN]** Call `common.create_finding(..., severity="critical")`
  - [x] **[REFACTOR]** Flag cleartext passwords specially

#### 2D: impacket-psexec Parser (AC: 3)

- [x] Task 2.10: Create psexec parser module
  - [x] **[RED]** Write failing test: `psexec_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/psexec.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 2.11: Parse psexec output
  - [x] **[RED]** Write failing test: parser detects successful shell access
  - [x] **[RED]** Write failing test: parser extracts target and credentials used
  - [x] **[GREEN]** Parse stdout for shell success indicators
  - [x] **[REFACTOR]** Handle failures gracefully

- [x] Task 2.12: Create Findings for shell access
  - [x] **[RED]** Write failing test: findings have `type="shell_access"`, `severity="critical"`
  - [x] **[GREEN]** Call `common.create_finding(...)`
  - [x] **[REFACTOR]** Include username and target

#### 2E: metasploit Parser (AC: 3)

- [x] Task 2.13: Create metasploit parser module
  - [x] **[RED]** Write failing test: `metasploit_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/metasploit.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 2.14: Parse metasploit output
  - [x] **[RED]** Write failing test: parser extracts session information
  - [x] **[RED]** Write failing test: parser extracts exploit success messages
  - [x] **[GREEN]** Parse stdout for `[+]` success indicators and session IDs
  - [x] **[REFACTOR]** Handle meterpreter vs shell sessions

- [x] Task 2.15: Create Findings for sessions/exploits
  - [x] **[RED]** Write failing test: session findings have `type="session"`, `severity="critical"`
  - [x] **[RED]** Write failing test: vuln findings have `type="vuln"`, severity based on CVE
  - [x] **[GREEN]** Call `common.create_finding(...)`
  - [x] **[REFACTOR]** Include exploit module name

#### 2F: searchsploit Parser (AC: 3)

- [x] Task 2.16: Create searchsploit parser module
  - [x] **[RED]** Write failing test: `searchsploit_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/searchsploit.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 2.17: Parse searchsploit output
  - [x] **[RED]** Write failing test: parser extracts exploit references from JSON (`-j`)
  - [x] **[RED]** Write failing test: parser extracts EDB ID, title, path, platform
  - [x] **[GREEN]** Parse JSON format
  - [x] **[REFACTOR]** Handle stdout format as fallback

- [x] Task 2.18: Create Findings for exploit references
  - [x] **[RED]** Write failing test: findings have `type="exploit_ref"` with edb_id in evidence
  - [x] **[GREEN]** Call `common.create_finding(..., severity="info")`
  - [x] **[REFACTOR]** Include platform and path

---

### Phase 3: Post-Exploitation Parsers [RED → GREEN → REFACTOR]

#### 3A: mimikatz Parser (AC: 4)

- [x] Task 3.1: Create mimikatz parser module
  - [x] **[RED]** Write failing test: `mimikatz_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/mimikatz.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 3.2: Parse mimikatz output
  - [x] **[RED]** Write failing test: parser extracts plaintext passwords
  - [x] **[RED]** Write failing test: parser extracts NTLM hashes
  - [x] **[RED]** Write failing test: parser extracts Kerberos tickets
  - [x] **[GREEN]** Parse stdout regex for `* Username :`, `* NTLM :`, etc.
  - [x] **[REFACTOR]** Handle sekurlsa::logonpasswords output format

- [x] Task 3.3: Create Findings for credentials
  - [x] **[RED]** Write failing test: findings have `type="credential"`, `severity="critical"`
  - [x] **[GREEN]** Call `common.create_finding(...)`
  - [x] **[REFACTOR]** Include domain information

#### 3B: bloodhound Parser (AC: 4)

- [x] Task 3.4: Create bloodhound parser module
  - [x] **[RED]** Write failing test: `bloodhound_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/bloodhound.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 3.5: Parse SharpHound JSON output
  - [x] **[RED]** Write failing test: parser extracts users, computers, groups
  - [x] **[RED]** Write failing test: parser identifies path to Domain Admin
  - [x] **[GREEN]** Parse BloodHound JSON format (users.json, computers.json, groups.json)
  - [x] **[REFACTOR]** Handle compressed zip output

- [x] Task 3.6: Create Findings for AD objects
  - [x] **[RED]** Write failing test: findings have `type="ad_object"` with object_type, name
  - [x] **[GREEN]** Call `common.create_finding(...)`
  - [x] **[REFACTOR]** Flag high-value targets (Domain Admins, etc.) with higher severity

#### 3C: linpeas Parser (AC: 4)

- [x] Task 3.7: Create linpeas parser module
  - [x] **[RED]** Write failing test: `linpeas_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/linpeas.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 3.8: Parse linpeas output
  - [x] **[RED]** Write failing test: parser extracts privilege escalation vectors
  - [x] **[RED]** Write failing test: parser handles ANSI color codes
  - [x] **[GREEN]** Parse stdout with ANSI stripping, identify sections
  - [x] **[REFACTOR]** Map color codes to severity (RED=high, YELLOW=medium)

- [x] Task 3.9: Create Findings for privesc vectors
  - [x] **[RED]** Write failing test: findings have `type="privesc_vector"` with vector_type, description
  - [x] **[GREEN]** Call `common.create_finding(...)`
  - [x] **[REFACTOR]** Categorize vectors (SUID, capabilities, cronjobs, etc.)

#### 3D: winpeas Parser (AC: 4)

- [x] Task 3.10: Create winpeas parser module
  - [x] **[RED]** Write failing test: `winpeas_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/winpeas.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 3.11: Parse winpeas output
  - [x] **[RED]** Write failing test: parser extracts privilege escalation vectors
  - [x] **[RED]** Write failing test: parser handles ANSI color codes
  - [x] **[GREEN]** Parse stdout with ANSI stripping
  - [x] **[REFACTOR]** Map color codes to severity

- [x] Task 3.12: Create Findings for Windows privesc vectors
  - [x] **[RED]** Write failing test: findings have `type="privesc_vector"`
  - [x] **[GREEN]** Call `common.create_finding(...)`
  - [x] **[REFACTOR]** Categorize vectors (unquoted paths, permissions, services, etc.)

#### 3E: lazagne Parser (AC: 4)

- [x] Task 3.13: Create lazagne parser module
  - [x] **[RED]** Write failing test: `lazagne_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/lazagne.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 3.14: Parse lazagne output
  - [x] **[RED]** Write failing test: parser extracts credentials by application
  - [x] **[GREEN]** Parse stdout structured format
  - [x] **[REFACTOR]** Handle multiple application categories

- [x] Task 3.15: Create Findings for harvested credentials
  - [x] **[RED]** Write failing test: findings have `type="credential"` with application in evidence
  - [x] **[GREEN]** Call `common.create_finding(..., severity="critical")`
  - [x] **[REFACTOR]** Include username and source application

#### 3F: chisel Parser (AC: 4)

- [x] Task 3.16: Create chisel parser module
  - [x] **[RED]** Write failing test: `chisel_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/chisel.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 3.17: Parse chisel output
  - [x] **[RED]** Write failing test: parser detects tunnel establishment
  - [x] **[GREEN]** Parse stdout for connection messages
  - [x] **[REFACTOR]** Handle server vs client mode

- [x] Task 3.18: Create Findings for tunnels
  - [x] **[RED]** Write failing test: findings have `type="tunnel"` with local_port, remote_target
  - [x] **[GREEN]** Call `common.create_finding(..., severity="info")`
  - [x] **[REFACTOR]** Include tunnel status

---

### Phase 4: Wireless Parsers [RED → GREEN → REFACTOR]

#### 4A: aircrack-ng Parser (AC: 5)

- [x] Task 4.1: Create aircrack-ng parser module
  - [x] **[RED]** Write failing test: `aircrack_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/aircrack.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 4.2: Parse aircrack-ng output
  - [x] **[RED]** Write failing test: parser detects successful key crack
  - [x] **[RED]** Write failing test: parser extracts BSSID, ESSID, key
  - [x] **[GREEN]** Parse stdout regex: `KEY FOUND! [ ... ]`
  - [x] **[REFACTOR]** Handle WEP vs WPA

- [x] Task 4.3: Create Findings for cracked WiFi
  - [x] **[RED]** Write failing test: findings have `type="wifi_crack"`, `severity="critical"`
  - [x] **[GREEN]** Call `common.create_finding(...)`
  - [x] **[REFACTOR]** Include packet count

#### 4B: wifite Parser (AC: 5)

- [x] Task 4.4: Create wifite parser module
  - [x] **[RED]** Write failing test: `wifite_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/wifite.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 4.5: Parse wifite output
  - [x] **[RED]** Write failing test: parser extracts attack results
  - [x] **[GREEN]** Parse colored stdout with ANSI stripping
  - [x] **[REFACTOR]** Handle different attack types (PMKID, handshake)

- [x] Task 4.6: Create Findings for WiFi attacks
  - [x] **[RED]** Write failing test: findings have `type="wifi_attack"` with attack_type, result
  - [x] **[GREEN]** Call `common.create_finding(...)`
  - [x] **[REFACTOR]** Map severity based on success

---

### Phase 5: Credential Parsers [RED → GREEN → REFACTOR]

#### 5A: john Parser (AC: 6)

- [x] Task 5.1: Create john parser module
  - [x] **[RED]** Write failing test: `john_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/john.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 5.2: Parse john output
  - [x] **[RED]** Write failing test: parser extracts cracked passwords from `--show`
  - [x] **[GREEN]** Parse stdout: `username:password` format
  - [x] **[REFACTOR]** Handle different hash formats

- [x] Task 5.3: Create Findings for cracked hashes
  - [x] **[RED]** Write failing test: findings have `type="cracked_hash"` with hash, plaintext
  - [x] **[GREEN]** Call `common.create_finding(..., severity="critical")`
  - [x] **[REFACTOR]** Include format information

#### 5B: hashcat Parser (AC: 6)

- [x] Task 5.4: Create hashcat parser module
  - [x] **[RED]** Write failing test: `hashcat_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/hashcat.py`
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 5.5: Parse hashcat output
  - [x] **[RED]** Write failing test: parser extracts cracked passwords
  - [x] **[GREEN]** Parse stdout or potfile format: `hash:plaintext`
  - [x] **[REFACTOR]** Handle different modes

- [x] Task 5.6: Create Findings for cracked hashes
  - [x] **[RED]** Write failing test: findings have `type="cracked_hash"` with mode, speed
  - [x] **[GREEN]** Call `common.create_finding(..., severity="critical")`
  - [x] **[REFACTOR]** Include hash mode

---

### Phase 6: Registration & Export [RED → GREEN → REFACTOR]

- [x] Task 6.1: Export all new parsers from `__init__.py`
  - [x] **[RED]** Write failing tests: all 24 parsers importable from `cyberred.tools.parsers`
  - [x] **[GREEN]** Update `parsers/__init__.py` with all new exports
  - [x] **[REFACTOR]** Update `__all__` list

- [x] Task 6.2: Register with OutputProcessor
  - [x] **[RED]** Write failing test: `OutputProcessor.register_parser()` works for each
  - [x] **[GREEN]** Verify registration with output processor
  - [x] **[REFACTOR]** Confirm total parser count is ~30

---

### Phase 7: Test Fixtures & Integration [RED → GREEN → REFACTOR]

- [x] Task 7.1: Create test fixtures for all parsers (AC: 9)
  - [x] Create fixtures in `tests/fixtures/tool_outputs/` for each tool
  - [x] Include success cases, empty outputs, and edge cases

- [x] Task 7.2: Create integration tests for each parser category
  - [x] `tests/integration/tools/parsers/test_recon_parsers.py`
  - [x] `tests/integration/tools/parsers/test_exploit_parsers.py`
  - [x] `tests/integration/tools/parsers/test_postex_parsers.py`
  - [x] `tests/integration/tools/parsers/test_wireless_parsers.py`
  - [x] `tests/integration/tools/parsers/test_credential_parsers.py`

- [x] Task 7.3: Achieve 100% coverage on all new parsers (AC: 7)
  - [x] Run `pytest --cov=src/cyberred/tools/parsers --cov-report=term-missing`
  - [x] Ensure all lines/branches covered
  - [x] Add edge case tests as needed

---

### Phase 8: Documentation [BLUE]

- [x] Task 8.1: Update Dev Agent Record
  - [x] Complete Agent Model Used
  - [x] Add Debug Log References
  - [x] Complete Completion Notes List
  - [x] Fill in File List

- [x] Task 8.2: Final verification
  - [x] Verify all 24 parsers implemented
  - [x] Verify total Tier 1 count is ~30
  - [x] Verify 100% coverage gate passes
  - [x] Update story status to `review`

## Dev Notes

> [!TIP]
> **Batch Implementation Pattern:** Consider implementing parsers in category batches (all recon together, etc.) to leverage shared patterns and maintain focus. Each batch should pass 100% coverage before moving to the next.

### ParserFn Signature (CRITICAL)

All parsers MUST follow the exact signature from [`parsers/base.py`](file:///root/red/src/cyberred/tools/parsers/base.py):

```python
from cyberred.tools.parsers.base import ParserFn

def tool_parser(
    stdout: str, 
    stderr: str, 
    exit_code: int, 
    agent_id: str, 
    target: str
) -> List[Finding]:
    ...
```

### Common Module (REQUIRED)

Use `common.py` for all finding creation (from Story 4.9):

```python
from cyberred.tools.parsers import common

findings.append(common.create_finding(
    type_val="open_port",
    severity="info",
    target=target,
    evidence=f"Port {port}/{proto} open on {ip}",
    agent_id=agent_id,
    tool="masscan"
))
```

### Finding Model Reference

From [`core/models.py`](file:///root/red/src/cyberred/core/models.py):

**Required Fields for `Finding`:**
- `id` (UUID), `agent_id` (UUID), `timestamp` (ISO 8601), `target` (IP/URL/hostname)
- `type` (e.g., "open_port", "subdomain", "credential", "privesc_vector")
- `severity` ("critical", "high", "medium", "low", "info")
- `evidence` (Raw output snippet), `tool` (tool name), `topic` (Redis channel), `signature` (empty)

### Severity Mapping Guidelines

| Finding Type | Default Severity | Notes |
|--------------|------------------|-------|
| credential (cleartext) | critical | Immediate access |
| credential (hash) | high | Requires cracking |
| shell_access | critical | Full system access |
| session | critical | Active compromise |
| privesc_vector | high/medium | Based on exploitability |
| open_port | info | Information only |
| subdomain | info | Information only |
| technology | info | May escalate if outdated |
| waf_detected | info | Defensive measure |
| wifi_crack | critical | Network access gained |
| cracked_hash | critical | Password compromised |

### ANSI Color Stripping Pattern

For tools with colored output (linpeas, winpeas, wifite):

```python
import re

def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)
```

### Error Handling Pattern

| Error | Handling | Notes |
|-------|----------|-------|
| Empty output | Return empty list | Normal for no findings |
| Malformed data | Skip and continue | Log warning, parse rest |
| JSON parse error | Try stdout fallback | Many tools support both |
| Missing fields | Use defaults | Don't crash |

### Key Learnings from Previous Parser Stories (4.6-4.9)

1. **Use `common.create_finding`** — Centralized finding creation from Story 4.9
2. **Auto-detect format** — Support both JSON and stdout where applicable
3. **Strip ANSI codes** — Many tools output colored text
4. **Validate UUIDs** — Finding model strictly validates
5. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases
6. **Verify coverage claims** — Run `pytest --cov` explicitly before marking done
7. **Use structlog for logging** — NOT `print()` statements
8. **Catch exceptions** — Return empty list on parse errors
9. **Use pytest markers** — Always include `@pytest.mark.unit` and `@pytest.mark.integration`
10. **Create fixtures for all edge cases** — Empty output, malformed data, multiple findings

### Project Structure Notes

```
src/cyberred/tools/parsers/
├── __init__.py          # [MODIFY] Add 24 new parser exports
├── base.py              # [UNCHANGED] ParserFn type
├── common.py            # [UNCHANGED] create_finding, generate_topic
├── nmap.py              # [UNCHANGED] Reference implementation
├── nuclei.py            # [UNCHANGED] Reference implementation
├── sqlmap.py            # [UNCHANGED] Reference implementation
├── ffuf.py              # [UNCHANGED] Reference implementation
├── nikto.py             # [UNCHANGED] Reference implementation
├── hydra.py             # [UNCHANGED] Reference implementation
│
│ # Reconnaissance Parsers (NEW)
├── masscan.py           # [NEW]
├── subfinder.py         # [NEW]
├── amass.py             # [NEW]
├── whatweb.py           # [NEW]
├── wafw00f.py           # [NEW]
├── dnsrecon.py          # [NEW]
├── theharvester.py      # [NEW]
├── gobuster.py          # [NEW]
│
│ # Exploitation Parsers (NEW)
├── crackmapexec.py      # [NEW]
├── responder.py         # [NEW]
├── secretsdump.py       # [NEW]
├── psexec.py            # [NEW]
├── metasploit.py        # [NEW]
├── searchsploit.py      # [NEW]
│
│ # Post-Exploitation Parsers (NEW)
├── mimikatz.py          # [NEW]
├── bloodhound.py        # [NEW]
├── linpeas.py           # [NEW]
├── winpeas.py           # [NEW]
├── lazagne.py           # [NEW]
├── chisel.py            # [NEW]
│
│ # Wireless Parsers (NEW)
├── aircrack.py          # [NEW]
├── wifite.py            # [NEW]
│
│ # Credential Parsers (NEW)
├── john.py              # [NEW]
└── hashcat.py           # [NEW]

tests/
├── unit/tools/parsers/
│   ├── test_masscan.py        # [NEW]
│   ├── test_subfinder.py      # [NEW]
│   ├── ... (24 new test files)
├── integration/tools/parsers/
│   ├── test_recon_parsers.py      # [NEW]
│   ├── test_exploit_parsers.py    # [NEW]
│   ├── test_postex_parsers.py     # [NEW]
│   ├── test_wireless_parsers.py   # [NEW]
│   └── test_credential_parsers.py # [NEW]
└── fixtures/tool_outputs/
    ├── masscan_*.json         # [NEW]
    ├── subfinder_*.txt        # [NEW]
    ├── ... (fixtures for all 24 tools)
```

### References

- **Epic Story:** [epics-stories.md#Story 4.10](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L1909)
- **Architecture - Finding Model:** [architecture.md#L608](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L608)
- **Previous Story 4.9:** [4-9-tier-1-parsers-web-fuzzing.md](file:///root/red/_bmad-output/implementation-artifacts/4-9-tier-1-parsers-web-fuzzing.md)
- **Previous Story 4.8:** [4-8-tier-1-parser-sqlmap.md](file:///root/red/_bmad-output/implementation-artifacts/4-8-tier-1-parser-sqlmap.md)
- **ParserFn Type:** [parsers/base.py](file:///root/red/src/cyberred/tools/parsers/base.py)
- **Common Module:** [parsers/common.py](file:///root/red/src/cyberred/tools/parsers/common.py)
- **Finding Model:** [core/models.py](file:///root/red/src/cyberred/core/models.py)

## Dev Agent Record

### Agent Model Used

Claude 3.5 Sonnet (via Trae AI)

### Debug Log References

None required - all tests passing.

### Completion Notes List

- Implemented 24 new Tier 1 parsers following TDD methodology
- Total parser count is now 30 (6 previous + 24 new), meeting AC8
- All parsers follow the established 5-parameter ParserFn signature (stdout, stderr, exit_code, agent_id, target)
- Each parser uses `common.create_finding()` for consistent Finding creation
- Parsers support both JSON and stdout formats where applicable
- ANSI color stripping implemented for linpeas, winpeas, wifite
- Comprehensive test coverage with 131 unit tests passing
- All parsers exported via `__init__.py`

### File List

| Action | File Path |
|--------|-----------|
| [MODIFY] | `src/cyberred/tools/parsers/__init__.py` |
| [NEW] | `src/cyberred/tools/parsers/masscan.py` |
| [NEW] | `src/cyberred/tools/parsers/subfinder.py` |
| [NEW] | `src/cyberred/tools/parsers/amass.py` |
| [NEW] | `src/cyberred/tools/parsers/whatweb.py` |
| [NEW] | `src/cyberred/tools/parsers/wafw00f.py` |
| [NEW] | `src/cyberred/tools/parsers/dnsrecon.py` |
| [NEW] | `src/cyberred/tools/parsers/theharvester.py` |
| [NEW] | `src/cyberred/tools/parsers/gobuster.py` |
| [NEW] | `src/cyberred/tools/parsers/crackmapexec.py` |
| [NEW] | `src/cyberred/tools/parsers/responder.py` |
| [NEW] | `src/cyberred/tools/parsers/secretsdump.py` |
| [NEW] | `src/cyberred/tools/parsers/psexec.py` |
| [NEW] | `src/cyberred/tools/parsers/metasploit.py` |
| [NEW] | `src/cyberred/tools/parsers/searchsploit.py` |
| [NEW] | `src/cyberred/tools/parsers/mimikatz.py` |
| [NEW] | `src/cyberred/tools/parsers/bloodhound.py` |
| [NEW] | `src/cyberred/tools/parsers/linpeas.py` |
| [NEW] | `src/cyberred/tools/parsers/winpeas.py` |
| [NEW] | `src/cyberred/tools/parsers/lazagne.py` |
| [NEW] | `src/cyberred/tools/parsers/chisel.py` |
| [NEW] | `src/cyberred/tools/parsers/aircrack.py` |
| [NEW] | `src/cyberred/tools/parsers/wifite.py` |
| [NEW] | `src/cyberred/tools/parsers/john.py` |
| [NEW] | `src/cyberred/tools/parsers/hashcat.py` |
| [NEW] | `tests/unit/tools/parsers/test_masscan.py` |
| [NEW] | `tests/unit/tools/parsers/test_subfinder.py` |
| [NEW] | `tests/unit/tools/parsers/test_amass.py` |
| [NEW] | `tests/unit/tools/parsers/test_whatweb.py` |
| [NEW] | `tests/unit/tools/parsers/test_wafw00f.py` |
| [NEW] | `tests/unit/tools/parsers/test_dnsrecon.py` |
| [NEW] | `tests/unit/tools/parsers/test_theharvester.py` |
| [NEW] | `tests/unit/tools/parsers/test_gobuster.py` |
| [NEW] | `tests/unit/tools/parsers/test_crackmapexec.py` |
| [NEW] | `tests/unit/tools/parsers/test_responder.py` |
| [NEW] | `tests/unit/tools/parsers/test_secretsdump.py` |
| [NEW] | `tests/unit/tools/parsers/test_psexec.py` |
| [NEW] | `tests/unit/tools/parsers/test_metasploit.py` |
| [NEW] | `tests/unit/tools/parsers/test_searchsploit.py` |
| [NEW] | `tests/unit/tools/parsers/test_mimikatz.py` |
| [NEW] | `tests/unit/tools/parsers/test_bloodhound.py` |
| [NEW] | `tests/unit/tools/parsers/test_linpeas.py` |
| [NEW] | `tests/unit/tools/parsers/test_winpeas.py` |
| [NEW] | `tests/unit/tools/parsers/test_lazagne.py` |
| [NEW] | `tests/unit/tools/parsers/test_chisel.py` |
| [NEW] | `tests/unit/tools/parsers/test_aircrack.py` |
| [NEW] | `tests/unit/tools/parsers/test_wifite.py` |
| [NEW] | `tests/unit/tools/parsers/test_john.py` |
| [NEW] | `tests/unit/tools/parsers/test_hashcat.py` |
| [NEW] | `tests/integration/tools/parsers/test_recon_parsers.py` |
| [NEW] | `tests/integration/tools/parsers/test_exploit_parsers.py` |
| [NEW] | `tests/integration/tools/parsers/test_postex_parsers.py` |
| [NEW] | `tests/integration/tools/parsers/test_wireless_parsers.py` |
| [NEW] | `tests/integration/tools/parsers/test_credential_parsers.py` |
| [NEW] | `tests/fixtures/tool_outputs/masscan_*.json` |
| [NEW] | `tests/fixtures/tool_outputs/subfinder_*.txt` |
| [NEW] | `tests/fixtures/tool_outputs/` (fixtures for all 24 tools) |
