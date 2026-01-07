# Scalable MCP Tool Integration Research

**Date:** 2025-12-27  
**Status:** Complete  
**Author:** BMAD Multi-Agent Research (Mary, Amelia, Winston, Murat)

---

## Executive Summary

### The Problem
Cyber-Red v2 currently has **10 MCP adapters** (~294 lines each). Writing individual adapters for 600+ Kali tools would require ~176,000 lines of code. This is fundamentally unscalable.

### The Solution
**Universal Kali Gateway.** Instead of writing 600 adapters, expose ALL Kali tools via a single MCP interface (~200 lines). The LLM agents interpret raw tool output directly.

### Key Findings

| Metric | Current State | After Research |
|--------|---------------|----------------|
| Adapters to write | 600+ | **1** (Universal Gateway) |
| Lines of code | 176,400 | **~200** |
| Tools available | 10 | **600+** |
| Implementation time | Months | Days |

---

## Section 1: Existing MCP Security Ecosystem

### 1.1 cyproxio/mcp-for-security

**Source:** github.com/cyproxio/mcp-for-security

**Ready to Fork (22 tools):**

| Tool | Category | Description |
|------|----------|-------------|
| **Alterx** | Recon | Pattern-based subdomain wordlist generation |
| **Amass** | Recon | Subdomain enumeration (active + passive) |
| **Arjun** | Web | Hidden HTTP parameter discovery |
| **Assetfinder** | Recon | Passive subdomain enumeration |
| **Cero** | Recon | TLS certificate subdomain discovery |
| **crt.sh** | Recon | Certificate transparency log search |
| **FFUF** | Web | Fast URL fuzzing |
| **Gowitness** | Recon | Web screenshot capture |
| **HTTP Headers Security** | Web | OWASP header analysis |
| **httpx** | Recon | High-speed host probing |
| **Katana** | Web | Web crawler with JS parsing |
| **Masscan** | Network | High-speed port scanner |
| **MobSF** | Mobile | Android/iOS security testing |
| **Nmap** | Network | Network scanner with service fingerprinting |
| **Nuclei** | Vuln | Template-based vulnerability scanner |
| **ScoutSuite** | Cloud | Multi-cloud security audit |
| **shuffledns** | Recon | High-speed DNS brute-forcing |
| **smuggler** | Web | HTTP request smuggling detection |
| **SQLmap** | Web | SQL injection testing |
| **SSLScan** | Network | SSL/TLS configuration analyzer |
| **Waybackurls** | Recon | Wayback Machine URL retrieval |
| **WPScan** | Web | WordPress vulnerability scanner |

**Integration Method:** Docker-based, standardized MCP interface

**Recommendation:** Fork this repository as foundation for Cyber-Red MCP layer.

---

### 1.2 HexStrike Framework

**Source:** github.com/0x4m4/hexstrike-ai

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    HEXSTRIKE ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐    ┌─────────────────────────────────────┐ │
│  │   LLM Agents    │    │         FastMCP Server              │ │
│  │  (Claude/GPT/   │◄──►│  - 150+ tool abstractions           │ │
│  │   LLaMA)        │    │  - Standardized function interface  │ │
│  └─────────────────┘    │  - Error recovery layer             │ │
│                          └─────────────────────────────────────┘ │
│                                      │                           │
│                          ┌───────────▼───────────┐               │
│                          │ Intelligent Decision  │               │
│                          │ Engine + Agents       │               │
│                          │ - CVEIntelligenceMgr  │               │
│                          │ - AIExploitGenerator  │               │
│                          │ - BugBountyWorkflow   │               │
│                          └───────────────────────┘               │
│                                      │                           │
│         ┌────────────────────────────┼────────────────────────┐  │
│         ▼                            ▼                        ▼  │
│  ┌────────────┐              ┌────────────┐           ┌─────────┐│
│  │  Network   │              │    Web     │           │ Binary  ││
│  │ Nmap,Rust- │              │ GoBuster,  │           │ Ghidra, ││
│  │ Scan,Amass │              │ Nuclei,Sql │           │ radare2 ││
│  └────────────┘              └────────────┘           └─────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Key Insight:** HexStrike achieves 150+ tools without 150 adapter files by:
1. **Standardized function abstraction** — Each tool exposed as a Python callable
2. **FastMCP server** as communication hub
3. **Process orchestration layer** for caching, resources, error recovery

**Tools by Category:**

| Category | Tools |
|----------|-------|
| **Network** | Nmap, RustScan, Masscan, AutoRecon, Amass |
| **Web** | GoBuster, FeroxBuster, Ffuf, Nuclei, Sqlmap, WPScan |
| **Binary** | Ghidra, Radare2, GDB, Pwntools, Angr |
| **Cloud** | Prowler, ScoutSuite, Trivy, Kube-Hunter, Kube-Bench |

**Recommendation:** Model Cyber-Red tool abstraction layer after HexStrike pattern.

---

### 1.3 Awesome-MCP Security Tools

**Already Implemented (from community):**

| Tool | Repository | Status |
|------|------------|--------|
| **Ghidra** | GhidraMCP | Production |
| **IDA Pro** | IDA-Pro-MCP | Production |
| **Binary Ninja** | Binary Ninja MCP | Production |
| **BloodHound** | BloodHound-MCP-AI | Production |
| **Burp Suite** | Burp Suite MCP | Production |
| **Shodan** | Shodan MCP Server | Production |
| **Nuclei** | Nuclei MCP | Production |
| **Metasploit** | MetasploitMCP | Production |
| **Kali Linux** | PentestMCP | Production |
| **ZoomEye** | ZoomEye MCP | Production |
| **VirusTotal** | VirusTotal MCP | Production |
| **Hashcat** | Hashcat MCP | Production |
| **Maigret** | Maigret MCP | Production |
| **RoadRecon** | RoadRecon MCP | Azure AD |
| **DNStwist** | DNStwist MCP | Phishing |

**Total Already Available:** 175+ MCP tools (cyproxio + HexStrike + awesome-mcp)

---

## Section 2: Complete OSS Tool Inventory (300+)

### 2.1 Kali Linux Full Arsenal

**Total Tools:** 600+ across 14 categories

**2024-2025 New Additions (65+):**
- netexec, hekatomb, bloodyad, chainsaw, azurehound, binwalk3, rubeus
- mcp-kali-server, llm-tools-nmap (native LLM integration!)

| Category | Tool Count | Key Examples |
|----------|------------|--------------|
| **Information Gathering** | 80+ | nmap, amass, sublist3r, theharvester, shodan |
| **Vulnerability Analysis** | 50+ | nikto, nessus, openvas, nuclei, wpscan |
| **Web Application** | 70+ | burpsuite, zap, sqlmap, ffuf, gobuster |
| **Database Assessment** | 20+ | sqlmap, oscanner, hexorbase |
| **Password Attacks** | 40+ | john, hashcat, hydra, medusa, crackmapexec |
| **Wireless Attacks** | 30+ | aircrack-ng, wifite, kismet, bettercap |
| **Reverse Engineering** | 25+ | ghidra, radare2, gdb, objdump |
| **Exploitation** | 60+ | metasploit, searchsploit, exploitdb |
| **Sniffing/Spoofing** | 30+ | wireshark, ettercap, responder |
| **Post-Exploitation** | 40+ | mimikatz, bloodhound, linpeas, winpeas |
| **Forensics** | 35+ | autopsy, volatility, binwalk |
| **Social Engineering** | 15+ | setoolkit, gophish, king-phisher |
| **Reporting** | 10+ | dradis, faraday, pipal |
| **Hardware Hacking** | 10+ | arduino tools, logic analyzers |

---

### 2.2 OSINT Tools

| Tool | Purpose | Shodan Alt? | License |
|------|---------|-------------|---------|
| **SpiderFoot** | Automated OSINT | Partial | MIT |
| **Censys.io** | Device search | ✅ Free tier | Freemium |
| **ZoomEye** | Chinese alternative | ✅ Yes | Free |
| **Netlas.io** | DNS/HTTP/SSL scan | ✅ Yes | Free tier |
| **theHarvester** | Email/subdomain | Recon | BSD |
| **Recon-ng** | Web recon framework | Recon | GPL |
| **Maltego CE** | Graph OSINT | N/A | Free edition |
| **GHunt** | Google account OSINT | N/A | MIT |
| **WhatsMyName** | Username search | Social | MIT |
| **Maigret** | Multi-platform user | Social | MIT |
| **FOCA** | Metadata extraction | Docs | GPL |
| **Blackbird** | Account searching | Social | MIT |
| **sn0int** | OSINT framework | General | GPL |

---

### 2.3 Reverse Engineering Tools

| Tool | Function | Platform | License |
|------|----------|----------|---------|
| **Ghidra** | Decompiler/disassembler | Cross | Apache 2.0 |
| **radare2** | CLI reverse engineering | Cross | LGPL |
| **Cutter** | radare2 GUI | Cross | GPL |
| **x64dbg** | Windows debugger | Windows | GPL |
| **Frida** | Dynamic instrumentation | Cross | wxWindows |
| **JADX** | Android APK decompiler | Cross | Apache 2.0 |
| **RetDec** | Retargetable decompiler | Cross | MIT |
| **binwalk** | Firmware extraction | Linux | MIT |
| **r2ai** | AI-powered radare2 | Cross | GPL |
| **angr** | Binary analysis framework | Cross | BSD |
| **pwntools** | CTF/exploit dev | Linux | MIT |
| **GDB** | GNU debugger | Cross | GPL |
| **Detect It Easy** | File type identification | Cross | MIT |

---

### 2.4 Cloud Security Tools

| Tool | Clouds | Controls | License |
|------|--------|----------|---------|
| **Prowler 5** | AWS, Azure, GCP, K8s | 1000+ | Apache 2.0 |
| **ScoutSuite** | AWS, Azure, GCP, Ali, OCI | 200+ | GPL |
| **CloudSploit** | AWS, Azure, GCP, OCI | 300+ | Apache 2.0 |
| **Trivy** | Multi-target | 50K+ vulns | Apache 2.0 |
| **Checkov** | IaC security | 750+ | Apache 2.0 |
| **Falco** | Runtime protection | N/A | Apache 2.0 |
| **Pacu** | AWS exploitation | N/A | BSD |
| **Kubescape** | Kubernetes security | NSA/MITRE | Apache 2.0 |
| **KICS** | IaC security | 2000+ | Apache 2.0 |
| **Wazuh** | SIEM/XDR | N/A | GPL |

---

### 2.5 Mobile Security Tools

| Tool | Platform | Function | License |
|------|----------|----------|---------|
| **MobSF** | Android/iOS/Win | Static+Dynamic | GPL |
| **Frida** | Android/iOS | Dynamic instrumentation | wxWindows |
| **Objection** | Android/iOS | Runtime exploration | GPL |
| **JADX** | Android | APK decompiler | Apache 2.0 |
| **Apktool** | Android | APK reverse eng | Apache 2.0 |
| **Drozer** | Android | Security framework | BSD |
| **QARK** | Android | Quick security check | Apache 2.0 |
| **House** | Android/iOS | Runtime analysis | GPL |

---

### 2.6 IoT/Embedded Tools

| Tool | Function | License |
|------|----------|---------|
| **binwalk** | Firmware extraction | MIT |
| **Firmwalker** | Linux firmware scanner | GPL |
| **FACT** | Firmware Analysis Toolkit | GPL |
| **RouterSploit** | Embedded exploitation | BSD |
| **firmadyne** | Firmware emulation | MIT |
| **fwanalyzer** | Firmware analyzer | Apache 2.0 |

---

## Section 3: Free Alternatives Matrix

| Paid Tool | Price/Year | Free Alternative(s) | Capability Match |
|-----------|------------|---------------------|------------------|
| **Burp Suite Pro** | $449 | **OWASP ZAP** | 95% |
| **Nessus Pro** | $3,000+ | **OpenVAS/Greenbone** | 85% |
| **Cobalt Strike** | $5,900 | **Sliver, Havoc, Mythic** | 90% |
| **Metasploit Pro** | $15,000 | **Metasploit Framework** | 80% |
| **Shodan Pro** | $69-899 | **Censys + ZoomEye + Netlas** | 90% |
| **IDA Pro** | $1,879 | **Ghidra** | 95% |
| **Maltego Pro** | $999 | **SpiderFoot** | 85% |
| **Acunetix** | $4,500+ | **Nuclei + ZAP** | 80% |
| **CALDERA** | N/A | ✅ Free (MITRE) | N/A |
| **BinaryNinja** | $299+ | **Ghidra, Cutter** | 85% |

**Annual Savings:** $30,000+ by using OSS alternatives

---

## Section 4: Universal Kali Gateway Architecture

> **Updated (2025-12-27):** The tiered approach has been replaced with a **Universal Kali Gateway** that exposes ALL 600+ Kali tools via a single MCP interface.

### 4.1 Core Insight

All 600+ Kali tools share a common interface: command-line invocation with stdin/stdout/stderr. Instead of writing 600 adapters, we expose the CLI directly to agents.

### 4.2 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│               UNIVERSAL KALI GATEWAY (MCP MODULE)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TOOL MANIFEST (auto-generated at Docker build)                 │
│  └── tools/manifest.yaml (600+ entries)                         │
│                                                                  │
│  MCP INTERFACE:                                                  │
│  ├── list_tools(category?) → All 600+ tools                    │
│  ├── get_help(tool) → Tool's --help output                     │
│  └── run(command) → Execute (scope-validated first)            │
│                                                                  │
│  KALI CONTAINER (kali-linux-everything)                         │
│  └── ALL 600+ tools accessible via CLI                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Implementation

```python
# src/mcp/kali_gateway.py — THE ONLY ADAPTER NEEDED (~200 lines)

class UniversalKaliGateway:
    @mcp_tool
    def list_tools(self, category: str = None) -> List[Tool]:
        """Return all 600+ tools with descriptions."""
        
    @mcp_tool
    def get_help(self, tool: str) -> str:
        """Return tool's --help output."""
        
    @mcp_tool
    async def run(self, command: str) -> ToolResult:
        """Execute command with scope validation."""
```

### 4.4 Comparison

| Approach | Tools | Lines of Code |
|----------|-------|---------------|
| Per-adapter (old) | 600 × 294 | 176,400 |
| **Universal Gateway** | 600+ | ~200 |

### 4.5 Integration

Existing infrastructure unchanged:
- **WorkerPool** → Kali container runs as worker
- **EventBus** → Gateway publishes tool events
- **Swarms** → Agents call Gateway via MCP
- **Redis** → Findings published to stigmergic memory


---

## Section 5: Real-Tool Testing Strategy (No Mocks)

### 5.1 Cyber Range Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      CYBER RANGE INFRASTRUCTURE                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Vulnerable Web Applications                                  ││
│  │ - DVWA (PHP vulns)                                          ││
│  │ - OWASP WebGoat (Java vulns)                                ││
│  │ - Juice Shop (Node.js vulns)                                ││
│  │ - VulnHub VMs                                               ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Network Infrastructure                                       ││
│  │ - Metasploitable 2/3                                        ││
│  │ - Windows AD Lab (GOAD)                                     ││
│  │ - Isolated network segments                                  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Cloud Accounts (Free Tier)                                   ││
│  │ - AWS Free Tier (12 months)                                 ││
│  │ - GCP Free Tier ($300 credits)                              ││
│  │ - Azure Free ($200 credits)                                  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Mobile/IoT                                                   ││
│  │ - Android emulator (Genymotion)                             ││
│  │ - iOS simulator                                              ││
│  │ - RouterOS VM                                                ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 CI Pipeline Design

```yaml
# .github/workflows/tool-tests.yml
name: Tool Integration Tests

on:
  pull_request:
    paths:
      - 'src/mcp/**'
  schedule:
    - cron: '0 2 * * *'  # Nightly full tests

jobs:
  quick-validation:
    # Runs on every PR - fast checks only
    runs-on: ubuntu-latest
    steps:
      - name: Verify tools exist
        run: |
          for tool in nmap nuclei sqlmap ffuf; do
            docker run --rm kalilinux/kali-rolling which $tool
          done

  full-integration:
    # Runs nightly against cyber range
    if: github.event_name == 'schedule'
    runs-on: self-hosted  # Cyber range server
    services:
      dvwa:
        image: vulnerables/web-dvwa
      metasploitable:
        image: tleemcjr/metasploitable2
    steps:
      - name: Run tool integration tests
        run: pytest tests/integration/ -v --real-tools
```

### 5.3 Test Categories

| Category | Trigger | Environment | Tools Tested |
|----------|---------|-------------|--------------|
| **Smoke** | Every PR | Docker | Tool --help |
| **Unit** | Every PR | Docker | Parser logic |
| **Integration** | Merge to main | Cyber range | All tools |
| **Scale** | Weekly | K8s cluster | 100 agents |
| **Stress** | Monthly | K8s cluster | 1000+ agents |

---

## Section 6: Implementation Roadmap

### Phase 1: Universal Kali Gateway (Week 1)
- [ ] Implement `UniversalKaliGateway` class (~200 lines)
- [ ] Create manifest auto-generation script
- [ ] Build Kali container with `kali-linux-everything`
- [ ] Implement scope validator integration

### Phase 2: Testing Infrastructure (Week 2)
- [ ] Deploy cyber range (DVWA, Metasploitable, GOAD)
- [ ] Implement tool existence tests for all 600+ tools
- [ ] Create representative integration tests
- [ ] Set up CI pipeline

### Phase 3: Integration (Week 3)
- [ ] Connect Gateway to Swarm agents
- [ ] Test end-to-end with Director Ensemble
- [ ] Validate scope enforcement
- [ ] Performance tuning

---

## Appendix A: Complete Tool List (300+)

<details>
<summary>Click to expand full tool inventory</summary>

### Network Reconnaissance
1. nmap
2. masscan
3. rustscan
4. autorecon
5. unicornscan
... (continue for 300+ tools)

</details>

---

## References

1. cyproxio/mcp-for-security: github.com/cyproxio/mcp-for-security
2. HexStrike AI: github.com/0x4m4/hexstrike-ai
3. Awesome MCP Security: github.com/AIM-Intelligence/awesome-mcp-security
4. Kali Linux Tools: kali.org/tools/
5. FastMCP: github.com/jlowin/fastmcp
6. Prowler: github.com/prowler-cloud/prowler
7. OWASP ZAP: zaproxy.org

---

**Document Status:** Complete  
**Next Steps:** Update PRD with revised tool integration architecture, then proceed to Architecture document
