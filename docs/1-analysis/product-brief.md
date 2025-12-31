---
stepsCompleted: [1, 2, 3, 4, 5, 6]
status: complete
completedAt: '2025-12-26'
inputDocuments:
  - docs/archive/v1/1-analysis/product-brief.md
  - docs/archive/v1/research/dragon-stack.md
  - docs/archive/v1/3-solutioning/architecture.md
  - docs/archive/v1/2-plan/prd.md
workflowType: 'product-brief'
lastStep: 5
project_name: 'Cyber-Red'
user_name: 'Root'
date: '2025-12-26'
version: '2.0'
migration_from: 'v1.0'
---

# Product Brief: Cyber-Red v2.0

**Date:** 2025-12-26
**Author:** Root

---

## Executive Summary

In cybersecurity, the attacker only needs to be right once. The defender must be right every time. **Cyber-Red v2.0** shifts this asymmetry — deploying an infinite army of AI agents that find ***every*** vulnerability before your adversaries do. Not some. Not most. ***Every.***

Cyber-Red v2 is not a tool. It is the **first stigmergic multi-agent offensive security platform** — achieving total attack surface coverage that would require a 1,000-person red team, in hours, not months. While competitors like Terra Security and RunSybil use centralized orchestration with dozens of agents, Cyber-Red's decentralized P2P coordination enables emergent attack strategies at 10,000+ agent scale. Built on the Swarms framework with a Multi-LLM Director Ensemble (DeepSeek v3.2, Kimi K2, MiniMax M2), v2 evolves from the v1 "Army in a Box" into an **infinite-scale, objective-driven penetration platform**.

Unlike scanners that enumerate CVEs, Cyber-Red operates with mission directives: *"Log in as admin and extract this data"* — deploying thousands of coordinated AI agents that share findings in real-time through stigmergic P2P coordination, enabling emergent attack strategies no individual agent could devise. It serves governments, critical infrastructure operators, and enterprises where security breaches carry **national security implications** or **billions in potential loss** — contexts where finding every vulnerability isn't optional, it's existential.

**The question isn't "Should we buy Cyber-Red or another scanner?"** — it's **"Should we hire 50 more pentesters or deploy Cyber-Red?"**

---

## Core Vision

### Problem Statement

**Security breaches must be found before adversaries find them. There is no alternative.**

Organizations face an asymmetric threat landscape where:
- **Attackers have infinite time and automation** — defenders have limited attention and resources
- **Human red teams cannot achieve total coverage** — they sample attack surfaces, missing ports, endpoints, parameters, and attack chains
- **Traditional tools follow linear logic** — they break when WAFs block them, they can't reason, adapt, or pivot
- **A single missed vulnerability** can result in national security compromise or billions in damages

For governments defending critical infrastructure, enterprises protecting sensitive data, and organizations facing state-level threats, **incomplete security validation is not an option**.

### Problem Impact

| Stakeholder | Impact of Missed Vulnerability |
|-------------|--------------------------------|
| **Governments & Defense** | National security compromise, state-secret exposure, critical infrastructure attacks |
| **Critical Infrastructure** | Service disruption, physical safety risks, cascading system failures |
| **Fortune 500 Enterprises** | Billions in revenue loss, ransomware, regulatory penalties, reputation destruction |
| **High-Value Targets** | Sensitive data breach, operational compromise, existential business risk |

### Why Existing Solutions Fall Short

**Human Red Teams:**
- Cannot physically test every port, API endpoint, and parameter simultaneously
- Skill bottleneck: no single expert masters SQLi, Cloud, AD, IoT, Wireless, and every attack vector
- Scale linearly with headcount — 50 experts still sample, they don't exhaust
- Limited by working hours, fatigue, and cognitive load

**Traditional Tools (Scanners, Cobalt Strike, Burp Suite):**
- Follow linear scripts that break when blocked
- Lack reasoning to pivot, adapt, or chain exploits creatively
- Report vulnerabilities without proving exploitability
- Cannot execute mission objectives — only enumerate findings
- Operate in isolation — no shared awareness between tool instances

**The Gap:** No existing solution combines **cognitive diversity**, **infinite scale**, **adaptive reasoning**, **emergent coordination**, and **objective completion** in a single deployable capability.

### Proposed Solution

**Cyber-Red v2.0: The AI-Native Offensive Security Capability**

A Swarms-based autonomous attack platform that:

1. **Deploys 10,000+ coordinated AI agents** — scaling limited only by hardware (with human-authorized lateral expansion through compromised devices)
2. **Achieves mission objectives** — not just "find vulns" but "log in as admin and extract this data"
3. **Proves every vulnerability** — 100% exploit verification, zero false positives
4. **Coordinates through stigmergic P2P communication** — agents share findings in real-time, enabling emergent attack strategies that no individual agent could devise
5. **Maintains strict governance** — human-authorized scope expansion, hard-gate RoE enforcement, no unauthorized lateral movement
6. **Runs persistently and independently** — daemon-based execution survives operator disconnection, with pause/resume and session management for multi-day engagements

**Architecture Evolution (v1 → v2):**

| Aspect | v1 | v2 |
|--------|----|----|
| Orchestration | Central bottleneck | Swarms Director Ensemble |
| Decision Model | Veto-based Council (caused refusals) | Synthesis-based Multi-LLM (no vetoes) |
| Agent Coordination | Isolated (agents unaware of each other) | Stigmergic P2P (real-time shared context) |
| Scale | ~100 agents (ID cycling limit) | 10,000+ agents (hardware-bounded) |
| Safety | AI Critic (over-blocked) | Hard-gate scope validator (deterministic) |
| Execution Model | Foreground process (dies with SSH) | Daemon-based (survives disconnect, pause/resume) |

### Key Differentiators

| Differentiator | Cyber-Red v2 | Competition |
|----------------|--------------|-------------|
| **Positioning** | AI-native *capability* (competes with hiring) | Tools (compete with other tools) |
| **Scale** | 10,000+ agents, hardware-bounded | Fixed team size or license limits |
| **Coverage** | 1,000-person red team coverage in hours | Sampling-based, incomplete |
| **Objective-Driven** | Completes missions, proves exploitability | Enumerates vulnerabilities only |
| **Cognitive Diversity** | Multi-LLM Ensemble (DeepSeek, Kimi K2, MiniMax) | Single model or rule-based |
| **Agent Awareness** | Stigmergic coordination — emergent strategies | Isolated agents, no shared context |
| **Exploit Verification** | 100% proven exploitability | High false-positive rates |
| **Governance** | Human-authorized lateral movement | All-or-nothing scope |
| **Persistence** | Daemon survives disconnect, pause/resume anytime | Dies with terminal, restart from scratch |

### Target Market Segmentation

| Tier | Segment | Characteristics |
|------|---------|-----------------|
| **Tier 1 (Day 1)** | Government/Defense, Critical Infrastructure | Existential need, budget available, tolerates early-adopter friction, becomes case study |
| **Tier 2 (Growth)** | Fortune 500 Security Teams, MSSPs | High-value targets, sophisticated buyers, enterprise sales cycle |
| **Tier 3 (Scale)** | Elite Security Consultancies, Broader Enterprise | Wider adoption, productized offering, self-service potential |

---

## Target Users

### Primary User: The Operator (Root)

**Profile:**
- **Role:** Sole operator of Cyber-Red — the human intelligence behind the swarm
- **Skill Level:** Senior cybersecurity strategist with deep offensive security expertise
- **Context:** Previously would have required coordinating hundreds of specialists over months; now wields Cyber-Red as a one-person capability

**Day-to-Day:**
- Receives engagement requests from high-profile clients (governments, enterprises, critical infrastructure)
- Reviews authorization documentation with support team (internally, before launch)
- Configures Cyber-Red with mission objectives and scope constraints
- Monitors War Room during operations, authorizes lateral movement when requested
- Pauses engagements when stepping away, resumes seamlessly when returning
- Manages multiple concurrent engagements across different clients
- Interprets findings and prepares comprehensive client deliverables

**Success Vision:**
- "This single tool makes possible what previously required an army"
- Complete attack surface coverage without hiring hundreds of specialists
- Proven exploits, not theoretical vulnerabilities
- Total control over scope and authorization at every step
- Engagements that run for days without babysitting — pause, disconnect, resume anytime

### Secondary Users: Authorization Support Team

**Profile:**
- **Role:** Trusted employees who assist with pre-engagement verification
- **Responsibilities:**
  - Verify client ownership documentation
  - Validate authorization paperwork
  - Assess ethical dilemmas and edge cases
  - Ensure all engagement parameters are authentic before Root launches

**Interaction with Cyber-Red:**
- Do not operate the tool directly
- Work is completed **before** Cyber-Red is launched
- May assist with report preparation after engagement

### Tertiary Users: Clients (Engagement Recipients)

**Profile:**
- **Who:** Governments, enterprises, critical infrastructure operators
- **Characteristics:**
  - Have resources (budget) but not skills
  - Face existential security threats
  - Require proven, comprehensive security validation

**What They Receive:**
- Comprehensive vulnerability reports
- Proven exploits with reproduction steps
- Remediation guidance and prioritization
- Ongoing engagement support (if contracted)

**What They Don't Receive:**
- Access to Cyber-Red itself
- Operational details of the swarm
- The tool is a **private capability**, not a licensed product

### Authorization Model (System Behavior)

**Pre-Launch (External to Cyber-Red):**
```
Client Request → Root + Employees verify docs internally → All clear
```

**At Launch (Cyber-Red):**
```
Cyber-Red: "Is this engagement authorized?" → Root confirms → Operations proceed
```

**Key Principles:**
- No sensitive authorization documents are loaded into Cyber-Red
- Verification happens **before** the tool is launched, not inside it
- Cyber-Red prompts for human confirmation of authorization status
- Once launched, the tool operates with confidence that everything is verified
- Simple, clean separation: **humans verify, tool confirms and executes**

**During Operations:**
- Lateral movement requests prompt for additional human authorization
- Scope expansion requires explicit Root approval
- Kill switch available at all times
- Pause/resume available at all times (engagement continues in background when TUI detached)
- Operator can disconnect SSH — daemon continues execution until paused or stopped

---

## Success Metrics

### Definition of Success

**A successful engagement means:**
1. **Every vulnerability discovered** — 100% attack surface exhaustion, no gaps
2. **Every objective achieved** — Mission directives completed, not just attempted
3. **Zero unauthorized actions** — All operations within confirmed scope
4. **Proven exploitability** — No false positives, every finding verified

**This is not aspirational. This is the baseline.**

---

### Operational Success Metrics (Operator Perspective)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Objective Completion Rate** | 100% | All mission directives achieved per engagement |
| **Vulnerability Coverage** | 100% | All discoverable vulnerabilities found (validated against manual verification sampling) |
| **False Positive Rate** | 0% | Every reported vulnerability is proven exploitable |
| **Unauthorized Action Count** | 0 | No operations outside confirmed scope |
| **Human Authorization Compliance** | 100% | All lateral movement requests approved before execution |

---

### Technical Success Metrics (System Performance)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Agent Concurrency** | 10,000+ | Maximum simultaneous agents without degradation |
| **Engagement Speed** | 10x faster than v1 | Time to complete equivalent scope |
| **Attack Surface Exhaustion** | 100% | All ports, endpoints, parameters analyzed |
| **System Stability** | 99.9% uptime | No crashes during active engagement |
| **Agent Coordination Latency** | <1s | Time for finding to propagate via stigmergic layer |

---

### Client Success Metrics (Engagement Outcomes)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Objective Conclusion** | 100% | Client-defined mission objectives achieved |
| **Deliverable Completeness** | Full package | Vulnerability report + proven exploits + remediation guidance |
| **Client Understanding** | Clear | Non-technical clients can understand findings and next steps |
| **Actionable Outcomes** | 100% | Every finding has clear remediation path |

---

### Governance Success Metrics (Safety & Compliance)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Scope Compliance** | 100% | Zero out-of-scope operations |
| **Authorization Prompt Response** | 100% | All lateral movement requests get human decision |
| **Kill Switch Effectiveness** | <1s | Time to halt all operations when triggered |
| **Audit Trail Completeness** | 100% | Every action logged and traceable |
| **Session Persistence** | 100% | Engagement survives operator disconnect |
| **Pause/Resume Reliability** | <1s | Time to pause or resume engagement |

---

### Key Performance Indicators (Summary)

| KPI | Description | Target |
|-----|-------------|--------|
| **Mission Success Rate** | Engagements where all objectives achieved | 100% |
| **Coverage Completeness** | Attack surface fully exhausted | 100% |
| **Zero Unauthorized** | Operations within scope | 0 violations |
| **Zero False Positives** | All findings proven | 0% FP rate |
| **10,000+ Scale** | Concurrent agent capacity | Achieved |
| **10x Speed** | vs. v1 baseline | Achieved |

---

## Scope Definition

### v2.0 Complete Scope (No Compromises)

**This is NOT an MVP. This is the full v2.0 release.**

The MVP mindset is explicitly rejected — it's the reason v1 never fully actualized. v2.0 delivers the complete vision.

---

### Core Architecture (Must Deliver)

| Component | Requirement |
|-----------|-------------|
| **Swarms Framework** | Full integration replacing custom orchestrator |
| **Multi-LLM Director Ensemble** | DeepSeek v3.2 + Kimi K2 + MiniMax M2 with synthesis |
| **Stigmergic P2P Coordination** | Redis-based agent awareness, real-time finding propagation |
| **10,000+ Agent Scaling** | Hardware-bounded only, no artificial limits |
| **Hard-Gate Scope Validator** | Deterministic RoE enforcement, no AI veto blocking |
| **Human Authorization Flow** | Lateral movement prompts, kill switch, scope expansion approval |
| **Remote WiFi Pivot** | Pre-deployed drop box + compromised host support |
| **Daemon Execution Model** | Background service survives SSH disconnect, pause/resume/attach/detach |
| **Session Management** | Multiple concurrent engagements, state machine lifecycle |

---

### WiFi Pivot Capability (v2.0)

**Architecture:**
- Cyber-Red runs on cloud/VPS (no local WiFi access)
- Pre-deployed drop box required for WiFi operations
- Secure C2 channel between Cyber-Red and drop box
- Drop box executes WiFi attacks (aircrack-ng, wifite, kismet)
- Captured credentials/handshakes relayed to main swarm
- Compromised hosts with WiFi can also serve as pivot points

**Preconditions:**
- Drop box must be connected before WiFi scan enabled
- Drop box deployment is a **manual, physical step** by operator
- Authorization required for WiFi scope expansion

**Supported Models:**
1. **Pre-Deployed Drop Box** — Physical device placed on-site (Raspberry Pi, mini PC)
2. **Compromised Host Pivot** — Already-pwned machine with WiFi capability leveraged

---

### Tool Suite (Must Deliver)

**Full Kali Linux Arsenal:**

| Category | Tools | Priority |
|----------|-------|----------|
| **Reconnaissance** | nmap, masscan, subfinder, amass, whatweb, wafw00f, dnsrecon | P1 |
| **Web Application** | nuclei, nikto, ffuf, dirb, gobuster, wpscan, sqlmap, burp-cli | P1 |
| **Exploitation** | metasploit, hydra, medusa, crackmapexec, impacket suite | P1 |
| **Post-Exploitation** | mimikatz, bloodhound, powersploit, linpeas, winpeas | P1 |
| **Network** | responder, bettercap, mitmproxy, tcpdump, wireshark-cli | P2 |
| **Password** | john, hashcat, ophcrack | P2 |
| **Wireless** | aircrack-ng, kismet, wifite, reaver | P1 (via drop box) |
| **Social Engineering** | setoolkit, gophish | P2 |

**All 600+ tools exposed via Swarms-native `kali_execute()` tool — agents generate bash/Python code, executed in isolated Kali containers with hard-gate scope validation. Structured output via Tier 1 parsers (~30 high-frequency tools) + LLM summarization. Zero MCP overhead — LLMs leverage training data knowledge of CLI tools.**

---

### Vulnerability Intelligence Layer (Must Deliver)

**Purpose:** Real-time exploit intelligence that transforms raw findings into actionable attack opportunities.

When agents discover services, ports, or software versions, they don't guess which exploits to try — they query a unified intelligence layer that aggregates multiple authoritative sources:

| Source | Data Provided | Query Example |
|--------|---------------|---------------|
| **CISA KEV** | Known Exploited Vulnerabilities (priority targets) | "Is CVE-2021-44228 actively exploited?" |
| **NVD** | CVE details, CVSS scores, affected versions | "What CVEs affect Apache 2.4.49?" |
| **ExploitDB** | Proof-of-concept exploits, searchsploit | "Find exploits for vsftpd 2.3.4" |
| **Nuclei Templates** | Detection + exploitation templates | "Templates targeting Log4j" |
| **Metasploit** | Exploit modules, payloads, aux scanners | "MSF modules for EternalBlue" |

**Intelligence Flow:**
```
Agent discovers "Apache/2.4.49" on port 443
        ↓
Intelligence Query: "exploits for Apache 2.4.49"
        ↓
Aggregator returns: CVE-2021-41773 (path traversal, CISA KEV)
                    CVE-2021-42013 (RCE, critical)
                    msf:exploit/multi/http/apache_normalize_path_rce
                    nuclei:cves/2021/CVE-2021-41773.yaml
        ↓
Agent prioritizes CISA KEV (known exploited) → executes exploit
        ↓
Finding published to stigmergic layer → other agents adapt
```

**Metasploit Integration:** Cyber-Red connects to Metasploit Framework via **msfrpcd** (RPC daemon). This enables:
- Module search by CVE, service, or keyword
- Payload generation for specific targets
- Session management for post-exploitation
- Auxiliary scanner orchestration

**Offline Capability:** Intelligence sources are cached in Redis with configurable TTL. Engagements can proceed with cached data if external APIs are unavailable.

---

### RAG Escalation Layer (Must Deliver)

**Purpose:** Advanced methodology knowledge for when standard exploits fail. LLMs lack offensive security training data — RAG injects curated attack methodologies, APT techniques, and complex multi-chain strategies.

**When triggered:** Director Ensemble or agents query RAG when intelligence layer returns no viable options or repeated exploit attempts fail.

| Source | Content | Priority |
|--------|---------|----------|
| **MITRE ATT&CK** | Technique correlation, kill chain mapping | P0 |
| **Atomic Red Team** | Executable technique definitions (YAML) | P0 |
| **HackTricks** | Methodology encyclopedia | P0 |
| **PayloadsAllTheThings** | Payloads, bypasses, evasion | P1 |
| **LOLBAS + GTFOBins** | Living-off-the-land escalation | P1 |
| **APT Reports** | Multi-chain attack strategies (APT28, etc.) | P2 |

**Stack:** LanceDB (embedded, self-hosted) + ATT&CK-BERT embeddings (CPU-only, no GPU required)

**Update mechanism:** Manual via TUI "Update RAG" button + scheduled weekly refresh for core sources.

---

### User Interface (Upgraded)

| Component | Change from v1 |
|-----------|----------------|
| **War Room TUI** | Upgraded — better visualization, real-time agent mesh view |
| **Hive Matrix** | Enhanced — show stigmergic connections between agents |
| **Brain Stream** | Multi-LLM — show all three perspectives (DeepSeek, Kimi, MiniMax) |
| **Authorization Queue** | Streamlined — faster lateral movement approval workflow |
| **Drop Box Status** | New — show connected drop boxes and their capabilities |
| **RAG Management** | New — Update RAG button, ingestion status, knowledge base stats |

---

### Infrastructure (Reworked)

| Component | Change from v1 |
|-----------|----------------|
| **Worker Pool** | Reworked — elastic container scaling based on demand |
| **Container Management** | Optimized — better resource allocation across swarm |
| **Drop Box C2** | New — secure channel for remote device communication |

---

### Testing (100% Coverage)

| Requirement | Target |
|-------------|--------|
| **Unit Test Coverage** | 100% |
| **Integration Test Coverage** | 100% |
| **E2E Tests (Cyber Range)** | Full attack chain validation |
| **Safety Tests** | Scope enforcement, kill switch, authorization |
| **Scale Tests** | 10,000 agent stress testing |
| **WiFi Tests** | Isolated wireless test lab |
| **Drop Box Tests** | C2 channel reliability, command execution |

---

### Out of Scope for v2.0

| Feature | Rationale |
|---------|-----------|
| **Commercial Licensing** | Private capability, not a product |
| **Multi-Tenant Support** | Single operator (Root) only |
| **Client Self-Service Portal** | Clients receive deliverables, not access |
| **Cloud Deployment** | Deferred to v2.1 — local/VPS deployment for v2.0 |

---

### Future Vision (v2.1+)

| Feature | Description |
|---------|-------------|
| **Cloud Deployment** | AWS/GCP/Azure native deployment for elastic compute |
| **Advanced Drop Box** | Auto-discovery, mesh networking between multiple drop boxes |
| **Physical Persistence** | Long-term drop box deployment with stealth capabilities |
| **Advanced Reporting** | Executive dashboards, trend analysis, comparison reports |
| **AI Model Expansion** | Additional LLMs as they become available |

---

### v2.0 Success Criteria

**v2.0 is complete when:**
1. ✅ All core architecture components operational
2. ✅ Full Kali tool suite integrated (600+ tools via Swarms-native code execution)
3. ✅ 10,000+ agents scale without degradation
4. ✅ WiFi pivot capability operational with drop box
5. ✅ 100% test coverage achieved
6. ✅ First real engagement completed successfully
7. ✅ All objectives achieved, all vulnerabilities found
8. ✅ Daemon mode operational — survives SSH disconnect
9. ✅ Pause/resume/attach/detach working seamlessly

---
