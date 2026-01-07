---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
inputDocuments:
  - docs/1-analysis/product-brief.md
  - docs/research/v2-migration-research.md
documentCounts:
  briefs: 1
  research: 1
  brainstorming: 0
  projectDocs: 0
workflowType: 'prd'
lastStep: 12
project_name: 'Cyber-Red'
user_name: 'Root'
date: '2025-12-27'
gapAnalysisUpdate: '2025-12-29 - Added RAG Escalation Layer (FR76-84), Intelligence Layer (FR65-75), TUI RAG management'
---


# Product Requirements Document - Cyber-Red

**Author:** Root
**Date:** 2025-12-27

---

## Executive Summary

Cyber-Red v2.0 is the **first stigmergic multi-agent offensive security platform** — not a tool that competes with scanners, but a capability that replaces the need to hire a 1,000-person red team. While competitors (Terra Security, RunSybil, XBOW) use centralized orchestration limited to dozens of agents, Cyber-Red's decentralized P2P coordination enables emergent attack strategies at 10,000+ scale. Built on the Swarms framework with a Multi-LLM Director Ensemble, v2 addresses the fundamental limitations of v1.

**The stakes are existential:** For governments, critical infrastructure operators, and enterprises where a single breach carries national security implications or billion-dollar consequences ($100M-$1B+ per incident), incomplete security validation is not an option. The cost of a missed vulnerability dwarfs the cost of any tool — but it doesn't dwarf the cost of the security team you'd need to achieve the same coverage. That's the comparison that matters.

This PRD defines the requirements for the v1 → v2 migration: replacing the central orchestrator bottleneck with Swarms-based coordination, eliminating the veto-based Council of Experts in favor of synthesis-based multi-LLM decision-making, and implementing stigmergic P2P agent coordination for emergent attack strategies.

### What Makes This Special

1. **Capability, not tool** — Competes with hiring security teams, not with purchasing scanners. The question is "hire 50 pentesters or deploy Cyber-Red?" not "buy Cyber-Red or Burp Suite?" This reframes the category entirely — making traditional tool comparisons irrelevant.

2. **Dual objectives** — Achieves both comprehensive attack surface exhaustion (find every vulnerability) AND mission completion (log in as admin and extract the data). Total coverage plus proven exploitability.

3. **Cognitive diversity** — Multi-LLM Director Ensemble (DeepSeek v3.2, Kimi K2, MiniMax M2) synthesizes three perspectives into action. No vetoes — aggregation and synthesis only.

4. **Emergent coordination** — Stigmergic P2P communication enables agents to share findings in real-time, triggering emergent attack strategies no individual agent could devise.

5. **Zero false positives** — 100% exploit verification. Every reported vulnerability is proven exploitable.

6. **Deterministic governance** — Hard-gate scope validation replaces AI semantic analysis. Clear "is this in scope?" rules, not fuzzy "is this safe?" judgments.

## Project Classification

| Attribute | Value |
|-----------|-------|
| **Project Type** | CLI/TUI Platform + Agent Orchestration Framework |
| **Domain** | Cybersecurity / Offensive Security (specialized) |
| **Complexity** | High |
| **Project Context** | Brownfield - major refactor (v1 → v2) |

**Migration scope:** Replace core orchestration (Council → Director Ensemble, Orchestrator → SwarmRouter), add stigmergic layer, scale to 10,000+ agents. Redis is *extended* to serve as the backbone for stigmergic pub/sub coordination. Preserve and build upon working components (WorkerPool, container pool). Replace MCP adapters with Swarms-native code execution.

---

## Success Criteria

### User Success (Operator)

| Criteria | Measurement |
|----------|-------------|
| **Incremental wins** | Every discovered vulnerability is an "aha moment" — success is continuous, not just at objective completion |
| **Objective achievement** | Mission directive completed comprehensively — not "vulnerabilities found" but "data extracted" or "access achieved" |
| **Total control** | Full authority over scope, authorization, and kill switch at every moment |
| **Emotional arc** | Restlessness during engagement, resolution upon objective completion |

### Client Success

| Criteria | Measurement |
|----------|-------------|
| **Objective completion** | The specific objective they defined is achieved — e.g., "extract confidential documentation from target" — comprehensively |
| **Proven exploitability** | Every finding comes with reproduction steps, not theoretical risk ratings |
| **Actionable deliverables** | Clear remediation path for every vulnerability |

### Business Success

| Criteria | Measurement |
|----------|-------------|
| **ASAP** | Full v2.0 kit operational — working system is the only priority |
| **Reputation** | Established through successful high-stakes engagements |
| **Evolution** | Social engineering at scale capabilities (v2.1+) to better achieve objectives |

### Technical Success

| Criteria | Target | Gate |
|----------|--------|------|
| **Agent scale** | 10,000+ concurrent agents | Hard |
| **Speed** | 10x faster than v1 | Hard |
| **Coordination latency** | <1s stigmergic propagation | Hard |
| **Stability** | 99.9% uptime during engagement | Hard |
| **Test coverage** | 100% (unit, integration, E2E, safety) | **Hard gate — no ship without** |
| **WiFi pivot** | Operational with drop box at launch | Hard |
| **Kill switch** | <1s halt all operations | Hard |

## Product Scope

### v2.0 Complete Scope (No MVP)

The MVP mindset is explicitly rejected. v2.0 ships complete or it doesn't ship.

**Core Architecture:**
- Swarms framework integration (replacing custom orchestrator)
- Multi-LLM Director Ensemble (DeepSeek v3.2, Kimi K2, MiniMax M2)
- Stigmergic P2P coordination (Redis-backed)
- Hard-gate scope validator (replacing AI Critic)
- 10,000+ agent scaling

**Capabilities:**
- Full Kali tool suite (600+ tools via Universal Kali Gateway)
- WiFi pivot via pre-deployed drop box
- War Room TUI (upgraded visualization)
- Human authorization flow (lateral movement, scope expansion)

**Quality:**
- 100% test coverage (hard gate)
- Cyber range E2E validation
- Safety tests (scope enforcement, kill switch)
- Scale tests (10,000 agent stress testing)

### Future Vision (v2.1+)

| Feature | Description |
|---------|-------------|
| **Social engineering at scale** | Automated phishing, pretexting, vishing to better achieve objectives |
| **Cloud deployment** | AWS/GCP/Azure native for elastic compute |
| **Advanced drop box** | Mesh networking, auto-discovery, stealth capabilities |
| **AI model expansion** | Additional LLMs as they become capable |

---

## User Journeys

### Journey 1: Root — The Engagement (Success Path)

Root receives the greenlight from the authorization support team. A high-profile client — a European defense ministry — needs comprehensive penetration testing of their external infrastructure with a specific objective: verify whether an attacker could access classified operational planning documents.

Root sits down at the War Room TUI and issues the directive in natural language: *"Log into defense-ministry.example.gov as an administrator. Avoid long-running bruteforce unless necessary. Locate and extract operational planning documents related to Project Northern Shield."*

The swarm awakens. The TUI lights up with 10,000+ agents initializing — reconnaissance specialists fan out across the attack surface while the Director Ensemble (DeepSeek strategizing, Kimi K2 analyzing, MiniMax finding creative angles) synthesizes their approach. The agent list is **virtualized** to handle scale — Root can't click through 10,000 agents, so **anomaly bubbling** surfaces agents that need attention at the top. Findings stream to a dedicated section, separate from agent status.

The incremental wins stream in. A dedicated TUI section pulses with each discovery: exposed subdomain, misconfigured S3 bucket, outdated WordPress plugin, SQL injection vector. Each vulnerability is an "aha moment" — proof the swarm is working. Root feels the restlessness, the anticipation building.

An authorization request appears via **WebSocket push** (real-time, not polling). An agent has discovered credentials and wants to pivot into an internal subnet. The TUI presents: summary of what's been identified, proposed next steps, Yes/No buttons, and a field for additional instructions. Root reviews, adds a note to avoid the HR systems, and authorizes. The swarm pivots.

Three hours later, the objective is achieved. The Director Ensemble confirms: administrative access obtained, Project Northern Shield documents located and extracted with full chain-of-custody evidence. Root exhales. Resolution.

The deliverables generate automatically: MD files documenting the entire process, every vulnerability with evidence and reproducible steps, and the main submission file — the client-facing report that walks them through everything, comprehensively detailing the objective and its achievement.

### Journey 2: Drop Box — Deployment & WiFi Pivot Operation

The engagement requires internal network access via WiFi. Root needs to deploy a drop box on-site.

**Pre-Engagement: Drop Box Script Preparation**

During Cyber-Red v2 development, a pre-compiled drop box binary is created and tested. **Built in Go for zero runtime dependencies and minimal footprint.** The binary:
- **Tier 1 Support:** Android, Windows, macOS, Linux (full support, tested)
- **Tier 2 Support:** iOS (compromised devices only — stock iOS cannot run background servers)
- Launches the relay server on any capable device (phone, tablet, PC, Pi, smart fridge)
- Is lightweight with no external dependencies
- Auto-configures networking and establishes secure C2 channel back to Cyber-Red

**Deployment: Natural Language Setup via TUI**

Root opens the War Room TUI and initiates drop box setup. The system guides through configuration using natural language:

*"I need to deploy a drop box for the Ministry engagement. The device is an Android phone."*

Cyber-Red responds with step-by-step instructions:
1. Download link for the Android drop box binary
2. Installation commands (or tap-to-install APK)
3. Network configuration requirements
4. How to launch the relay server in background mode

Root follows the instructions, relaying each step. The TUI displays a **deployment countdown** — visual tension while waiting for the callback. An **abort option** is always visible — one-click remote wipe if something feels wrong.

The device confirms: *"Server running. Awaiting connection from Cyber-Red."*

**Connection: Server-Side Configuration & Testing**

Root almost always connects to the target local network **through** the drop box device — this simplifies routing and ensures all traffic flows through the relay.

From the Cyber-Red server side, a **deterministic pre-flight protocol** executes:

```
PING → EXEC_TEST → STREAM_TEST → NET_ENUM → READY
```

1. **PING** — Verify drop box is reachable
2. **EXEC_TEST** — Execute simple command, confirm response
3. **STREAM_TEST** — Verify bidirectional streaming works
4. **NET_ENUM** — Enumerate network interfaces on drop box
5. **READY** — All tests passed, objective can commence

The TUI displays a **heartbeat indicator** — continuous pulse showing the C2 link is alive throughout the engagement. Not just "connected" but actively monitored.

TUI displays: *"Drop box connected. Pre-flight passed. Ready for objective."*

Only after server-side configuration and testing confirms commands can be run and streamed back does the objective commence.

**Operation: Relay Mode**

The drop box operates as a pure relay:
- Commands flow: Cyber-Red → Drop Box → Target Network
- Results flow: Target Network → Drop Box → Cyber-Red
- Heavy compute (cracking, analysis) stays server-side
- Drop box executes WiFi toolkit commands (aircrack-ng, wifite, kismet) locally but streams captures back for processing

**Objective Completion**

When internal access is achieved and the engagement concludes:
- Drop box can be remotely wiped (optional)
- Device is physically retrieved
- No traces remain on the device or network

### Journey 3: Root — Edge Case (Blocked Paths & Authorization Gates)

The swarm hits resistance. A sophisticated WAF blocks the primary attack vector. The TUI shows agents attempting, failing, adapting. The Director Ensemble doesn't give up — "there is always a way." Agents reiterate: trying different encodings, timing attacks, alternative endpoints, chained vulnerabilities. The stigmergic layer shares each failed attempt so no agent repeats it.

Eventually, a creative path emerges — MiniMax suggests an unconventional vector through a forgotten API endpoint. The swarm pivots. Progress resumes.

Later, an agent determines that completing the objective may require a large-scale DDoS to overwhelm a rate-limiting defense. This is a last resort — all other avenues explored. The authorization request appears via **WebSocket push** in Root's TUI: summary of the situation, why DDoS is needed, proposed scope and duration, Yes/No buttons, additional info field. **Timeout behavior is defined** — if Root doesn't respond within configurable window, request remains pending (no auto-approve, no auto-deny). Root weighs the decision, adds constraints ("max 60 seconds, target only the rate-limiter"), and authorizes.

Something unexpected happens. An agent begins targeting an out-of-scope system — a misconfiguration in the scope validator. Root sees it immediately and hits the kill switch. The **hybrid control** activates: instant halt for the rogue agent, graceful shutdown for the others preserving state and findings. Crisis averted in under one second.

Root reviews the incident, adjusts the scope validator rules, and resumes the engagement.

### Journey Requirements Summary

These journeys reveal the following capability requirements:

| Journey | Capabilities Required |
|---------|----------------------|
| **Engagement Flow** | Natural language directive parsing, War Room TUI with virtualized agent list, anomaly bubbling, real-time finding stream, MD deliverable generation |
| **Authorization Gates** | WebSocket-based authorization request (real-time push), timeout handling, lateral movement control, DDoS authorization |
| **Drop Box Operation** | Go binary (zero deps, cross-platform Tier 1/2), natural language TUI setup, deterministic pre-flight protocol (`PING→EXEC_TEST→STREAM_TEST→NET_ENUM→READY`), heartbeat indicator, one-click abort/wipe |
| **Edge Cases** | Persistent retry logic ("always a way"), hybrid kill switch (instant + graceful, <1s under load), scope validator with runtime adjustment |
| **Session Persistence** | Daemon execution (survives SSH disconnect), pause/resume, attach/detach TUI, multi-engagement management, session listing |
| **Deliverables** | Full process MD, vulnerability evidence + repro steps, client-facing submission report |

### Testing Requirements (from Journeys)

| Requirement | Test Approach |
|-------------|---------------|
| **Drop box pre-flight** | Mock drop box environment in CI for automated testing without physical hardware |
| **Kill switch <1s** | Stress test: 10,000 agents active, trigger kill switch, measure time to full stop |
| **Authorization flow** | E2E tests: timeout behavior, network interruption mid-auth, TUI closure during pending request |
| **Agent virtualization** | Performance test: TUI responsiveness with 10,000+ agents rendered |
| **Session persistence** | Daemon survives simulated SSH disconnect, engagement continues |
| **Pause/resume latency** | Measure pause-to-resume time under load, verify <1s |
| **Attach/detach cycle** | TUI attach → detach → reattach with state consistency verification |
| **Multi-engagement** | Run 3+ concurrent engagements, verify isolation and resource sharing |

---

## Domain-Specific Requirements

### Offensive Security Domain Overview

Cyber-Red operates in a specialized domain with unique compliance and operational requirements. Unlike regulated industries (healthcare, fintech), offensive security compliance is defined by **Rules of Engagement (RoE)**, **authorization protocols**, and **evidence standards** rather than government regulations.

The tool's ethical framework is deliberately external: the authorization support team makes ethical decisions *before* Cyber-Red is launched. The tool executes what it's authorized to do — no internal ethical gatekeeping beyond hard-gate scope validation. However, **situational awareness alerts** surface unexpected discoveries to the operator for human decision-making.

### Notification Requirements

Real-time operator awareness is critical during engagements:

| Notification Type | Delivery | Priority |
|-------------------|----------|----------|
| **Discovered vulnerabilities** | Real-time stream to TUI | High |
| **Important swarm updates** | Real-time stream to TUI | Medium |
| **Director Ensemble outputs** | Real-time stream to TUI | High |
| **Situational awareness alerts** | Modal dialogue requiring response | Critical |

**Situational Awareness Alerts:**
When the swarm discovers something unexpected that may affect engagement ethics (e.g., target appears to be healthcare infrastructure, civilian systems detected), Cyber-Red presents an alert to Root:
- Context summary of what was discovered
- "Continue? Yes/No" with additional info field
- Root decides — system does not auto-decide on ethical edge cases
- This is situational awareness, not ethical gatekeeping

All notifications must be non-blocking (except situational alerts) — operator can review while engagement continues.

### Authorization Protocol

**Pre-Engagement Authorization:**
- Support team completes external verification (ownership docs, authorization paperwork, ethical review)
- Root launches Cyber-Red
- System presents authorization dialogue:
  - Summary of engagement scope
  - **Liability waiver acknowledgment:** "I accept responsibility for this engagement"
  - Yes/No buttons
  - Additional info field for notes/constraints
  - **Timestamped** confirmation logged to audit trail (NTP-synchronized)

**Mid-Engagement Authorization (Lateral Movement, DDoS, etc.):**
- Same dialogue pattern: summary, Yes/No, additional info
- All authorizations timestamped (NTP-synchronized) and logged
- No auto-approve, no auto-deny on timeout

**Timestamp Integrity:**
- All timestamps synchronized via NTP
- Timestamp cannot be spoofed or backdated
- Cryptographically signed with authorization record

### Evidence Standards

All findings must meet chain-of-custody requirements for client deliverables:

| Evidence Type | Required | Notes |
|---------------|----------|-------|
| **Screenshots** | Yes | Visual proof of access/vulnerability |
| **Video** | Yes | For complex multi-step exploits |
| **Cryptographic proof** | Yes | SHA-256 hash + signature at discovery time |
| **Reproducible steps** | Yes | Clear instructions to reproduce finding |
| **Command logs** | No | Too verbose — reproducible steps preferred |
| **Relevant context** | Yes | Any info that supports the finding |

**Tamper-Evident Evidence:**
- Every finding receives SHA-256 hash at discovery time
- Hash signed with Cyber-Red private key (derived from operator passphrase via PBKDF2, never stored in plaintext)
- Creates tamper-evident chain: if client challenges "you fabricated this," cryptographic proof demonstrates timestamp and content integrity
- Evidence must be reproducible: can the finding be reproduced from the evidence alone?

**Inter-Agent Message Integrity:**
- All stigmergic messages authenticated with HMAC-SHA256 (mitigates Agent-in-the-Middle attacks)
- Invalid/unsigned messages rejected and logged as security events

### Data Handling & Protection

**Exfiltrated Data Policy:**

| Principle | Implementation |
|-----------|----------------|
| **Operator control** | All exfiltrated data accessible via TUI menu |
| **No auto-deletion** | System is NOT authorized to delete any data |
| **Manual review** | Team reviews exfiltrated data through TUI |
| **Manual deletion** | Team manually deletes data when appropriate |
| **Full access** | Operator has complete control over all stored data |

**Storage & Encryption:**
- Exfiltrated data saved locally on Cyber-Red infrastructure
- Accessible through dedicated TUI menu option
- **Encrypted at rest: AES-256**
- **Key derivation:** From operator passphrase
- **HSM support:** Hardware Security Module integration if available
- Retention until manually deleted by team

**Deletion Constraint Enforcement:**
- System cannot auto-purge data
- System cannot schedule deletion
- All deletion requires explicit manual operator action through TUI
- Negative tests verify: attempted auto-purge fails, attempted scheduled deletion fails

### Ethical Framework

**Explicit Design Decision:** Cyber-Red does NOT implement internal ethical gatekeeping — with one exception: **situational awareness**.

| Layer | Responsibility |
|-------|----------------|
| **External (Team)** | Decides what engagements to accept, ethical boundaries, target restrictions |
| **Internal (Cyber-Red)** | Executes authorized scope via hard-gate validator |
| **Situational Awareness** | Surfaces unexpected discoveries to Root for human decision |

The authorization support team is responsible for:
- Refusing engagements targeting hospitals, civilian infrastructure, etc. (if that's their policy)
- Verifying legitimate ownership and authorization
- Assessing ethical dilemmas before greenlight

Cyber-Red's job: Execute what it's authorized to do, within the defined scope, with full operator control. Surface situational alerts when unexpected ethical considerations emerge mid-engagement.

### Liability Framework

**Explicit Liability Allocation:**

| Party | Liability Scope |
|-------|-----------------|
| **Cyber-Red (Tool)** | None — tool executes within authorized scope |
| **Operator (Root)** | Accepts responsibility via pre-engagement waiver |
| **Client** | Per engagement agreement with operator |

**Liability Protection Mechanisms:**
1. **Audit trail** — Cryptographic proof that all actions were within authorized scope
2. **Authorization timestamps** — NTP-synchronized, signed, tamper-evident
3. **Scope validation logs** — Every scope check recorded
4. **Liability waiver** — Pre-engagement acknowledgment: "I accept responsibility for this engagement"

**No Warranty of Safety:**
Cyber-Red performs offensive security operations as directed. The tool makes no warranty that operations will not cause collateral damage. Responsibility rests with the operator per the liability waiver.

### Audit & Compliance

| Audit Requirement | Implementation |
|-------------------|----------------|
| **Authorization log** | All Yes/No decisions timestamped (NTP-sync'd), signed |
| **Liability waivers** | Pre-engagement acknowledgments logged |
| **Scope validation log** | All scope checks recorded |
| **Finding log** | All vulnerabilities with SHA-256 hash + signature |
| **Situational alerts** | All alerts and operator responses logged |
| **Action log** | All agent actions (summarized, not verbose) |
| **Deliverable generation** | Automated MD reports with full audit trail |

### Testing Requirements (Domain-Specific)

| Requirement | Test Approach |
|-------------|---------------|
| **Timestamp integrity** | Verify NTP sync, test spoofing attempts fail |
| **Never-delete constraint** | Negative tests: auto-purge fails, scheduled deletion fails |
| **Evidence reproducibility** | Validate findings can be reproduced from evidence alone |
| **Crypto signatures** | Verify SHA-256 + signature integrity on all findings |
| **Situational alerts** | E2E tests for alert triggering and operator response flow |

---

## Innovation & Novel Patterns

### Innovation Stack Architecture

Cyber-Red v2's innovations form an interdependent stack — each layer enables the one above:

```
Layer 4: Category Positioning ("Capability vs Tool")
   ↑ emergent property of
Layer 3: Unprecedented Scale (10,000+ agents)
   ↑ enabled by
Layer 2: Stigmergic P2P Coordination
   ↑ enabled by
Layer 1: Multi-LLM Director Ensemble (synthesis, no vetoes)
```

This is not a collection of features — it's an architectural innovation where the whole exceeds the sum of parts.

### Detected Innovation Areas

#### 1. Stigmergic Coordination (Novel Application)

**What it is:** Agents coordinate indirectly through environmental signals (Redis pub/sub), like ants leaving pheromone trails. Findings propagate through the swarm, triggering emergent attack strategies no individual agent could devise.

**Why it's novel:** Research confirms stigmergy is established in robotics, blockchain, and reinforcement learning — but **no prior art exists applying stigmergic coordination to offensive security**. This is a genuine blue ocean.

**What it enables:**
- Emergent attack strategies from collective intelligence
- O(1) coordination cost (vs O(n) for centralized)
- Context window independence — agents respond to signals, not full context
- Resilience — no single point of failure

#### 2. Multi-LLM Director Ensemble (Differentiated Approach)

**What it is:** Three LLMs (DeepSeek v3.2, Kimi K2, MiniMax M2) synthesize perspectives into unified action. No voting. No vetoes. Aggregation and synthesis only.

**Why it's differentiated:** Existing multi-agent systems (VulnBot, RedTeamLLM, CHECKMATE) use phased approaches — different agents for different stages. Cyber-Red's Director Ensemble makes **real-time collaborative decisions** on the same problem, synthesizing cognitive diversity.

**What it enables:**
- Cognitive diversity without veto paralysis (v1's Council problem)
- Strategy synthesis > strategy selection
- Each model contributes strengths: DeepSeek (strategy), Kimi K2 (deep reasoning), MiniMax (creative evasion)

#### 3. Scale as Category Differentiator (10,000+ Agents)

**What it is:** Operating 10,000+ concurrent AI agents when competitors operate dozens or hundreds.

**Why it's category-defining:**

| Competitor | Scale | Architecture |
|------------|-------|--------------|
| Terra Security (2024, $30M) | "Thousands of tests" | Centralized orchestration |
| RunSybil | Multi-agent | Centralized orchestrator + phase agents |
| XBOW | Multi-agent | Centralized orchestration |
| RedTeamLLM | Single-agent decomposition | ReAct/ADaPT patterns |
| **Cyber-Red v2** | **10,000+** | **Stigmergic P2P (decentralized)** |

**What enables this (that others can't easily replicate):**
- Stigmergic coordination eliminates central bottleneck
- SwarmRouter replaces orchestrator — no serialization point
- Redis pub/sub — distributed state, not centralized
- P2P architecture — coordination cost doesn't scale with agent count

#### 4. Category Creation ("Capability vs Tool")

**What it is:** Positioning Cyber-Red as a capability that competes with hiring security teams, not as a tool that competes with scanners.

**Why it's not just marketing:** The "capability" framing is an emergent property of the architecture:
- 10,000 agents = coverage equivalent to large human team
- Emergent strategies = human-like adaptive reasoning
- Objective completion = outcomes, not just findings
- 100% exploit verification = no false positives (human-level quality)

The architecture enables the positioning. Competitors can't claim "capability" without the architectural stack.

### Market Context & Competitive Landscape

**2025 Offensive Security AI Trends:**

| Trend | Implication for Cyber-Red |
|-------|---------------------------|
| Time-to-exploit dropping (32 days → 5 days → 5 minutes predicted) | Speed advantage from swarm parallelization |
| Nation-states adopting AI agents for offensive ops | Market validation for AI offensive security |
| Context window limits cited as major challenge | Stigmergic architecture sidesteps this |
| Multi-agent systems emerging (VulnBot, RedTeamLLM) | Competition entering space — first-mover advantage matters |
| Regulatory attention (EU AI Act, US Executive Order) | Audit trail and governance already designed in |

**Competitive Moat:**
1. **Stigmergic architecture** — No cybersecurity prior art; competitors must rebuild from scratch
2. **Scale** — 100x more agents requires architectural innovation, not just more compute
3. **Director Ensemble** — Synthesis approach is differentiated from voting/phased systems
4. **Integration** — Full stack from coordination to governance to deliverables

### Validation Approach

Each innovation layer requires specific validation:

| Layer | Innovation | Validation Method |
|-------|------------|-------------------|
| **Layer 1** | Director Ensemble | Compare decision quality: synthesis vs single-LLM vs voting |
| **Layer 2** | Stigmergic Coordination | Benchmark emergent strategy discovery vs centralized coordination |
| **Layer 3** | 10,000+ Scale | Stress testing: measure degradation curve, find actual ceiling |
| **Layer 4** | Capability Positioning | Market validation: do clients perceive and pay for "capability" value? |

**Validation success criteria:**
- Director Ensemble produces measurably better attack strategies than alternatives
- Stigmergic swarm discovers attack chains that single-agent or centralized systems miss
- System maintains performance at 10,000 agents (latency, coordination, stability)
- Client contracts reflect "capability" pricing (engagement fees, not license fees)

### Risk Mitigation

**Critical Innovation — No Fallback:**

| Innovation | Risk Posture |
|------------|--------------|
| **Stigmergic coordination** | **MUST WORK — No fallback.** This is the core differentiator. Failure to achieve provable emergence is project failure, not graceful degradation. |
| Scale bottlenecks | Optimize architecture, document actual ceiling per deployment |
| Synthesis underperforms voting | Add voting mode as option alongside synthesis |
| Market doesn't perceive "capability" | Reposition as premium tool, adjust pricing model |

**Stigmergic emergence is non-negotiable.** The architecture must provably demonstrate emergent attack strategies. Testing validates this with hard gates (NFR35-37).

### Innovation Dependencies

**Critical path for innovation realization:**

```
Swarms Framework Integration
    ↓
SwarmRouter + Redis Pub/Sub Operational
    ↓
Stigmergic Layer Producing Emergent Behavior (validate)
    ↓
Director Ensemble Synthesizing Effectively (validate)
    ↓
10,000+ Agent Scale Stable (validate)
    ↓
Market Positioning as Capability (validate)
```

Each validation gate must pass before claiming the innovation above it.

---

## Platform-Specific Requirements

### Project-Type Overview

Cyber-Red v2 is a hybrid platform combining:
- **CLI/TUI Platform** — War Room interactive interface with scriptable mode
- **Agent Orchestration Framework** — 10,000+ AI agents via Swarms integration
- **Tool Integration Layer** — 600+ tools via Universal Kali Gateway

This hybrid architecture requires considerations from both CLI tools (interaction modes, configuration) and developer tools (SDK patterns, extensibility).

### TUI Interaction Model

**Mode:** Hybrid — interactive by default, scriptable for automation, daemon-based execution

| Mode | Use Case | Implementation |
|------|----------|----------------|
| **Interactive** | Standard engagements with Root at keyboard | War Room TUI attached to daemon |
| **Scriptable** | Pre-configured engagements, overnight scans | CLI args + config files, daemon executes |
| **API** | External orchestration, custom automation | REST/WebSocket API layer to daemon |
| **Daemon** | Background execution, survives disconnect | `cyber-red daemon start`, TUI attach/detach |

**Execution Model:**
- All engagements run inside the daemon process (background)
- TUI is a client that attaches to daemon, not the execution host
- Operator can disconnect TUI (or lose SSH) without stopping engagement
- Multiple TUI clients can attach to same daemon (different engagements)

**Scriptable mode example:**
```bash
cyber-red --config engagements/ministry.yaml \
          --headless \
          --auth-mode prompt-on-critical
```

**Authorization handling in scriptable mode:**
- Critical authorizations (lateral movement, DDoS) → pause and prompt
- Pre-approved actions defined in engagement config
- Optional: `--auto-approve-lateral` for trusted scenarios

### Output Formats

**Comprehensive output format support:**

| Format | Use Case | Implementation |
|--------|----------|----------------|
| **Markdown** | Primary deliverables, human-readable | Native, default |
| **JSON** | Machine-readable, integrations | Structured findings export |
| **SARIF** | Security industry standard, GitHub/Azure DevOps | Static Analysis Results Interchange Format |
| **CSV/Excel** | Client stakeholders, non-technical audiences | Tabular vulnerability lists |
| **HTML** | Polished reports, embedded screenshots | Interactive navigation |
| **STIX/TAXII** | Threat intelligence sharing | CTI format for intel platforms |
| **Structured Logs** | SIEM integration (Splunk, Elastic) | JSON-LD format |

**Output generation:**
- All formats generated from single internal data model
- Format selection via TUI menu or CLI flag
- Template customization for client branding

### Configuration Architecture

**Layered configuration model:**

| Layer | Storage | Managed By | Contents |
|-------|---------|------------|----------|
| **System** | YAML + env files | Manual / deployment | LLM API keys, Redis connection, paths, defaults |
| **Engagement** | TUI wizard → YAML | Per-project via TUI | Target scope, objectives, RoE, constraints |
| **Runtime** | TUI settings | Per-session via TUI | Concurrency limits, timeouts, verbosity |
| **Secrets** | Environment vars | Secure vault / env | API keys, credentials |

**Configuration files:**
```
~/.cyber-red/
├── config.yaml              # System configuration
├── .env                     # Secrets (gitignored)
└── engagements/
    ├── ministry-2025.yaml   # Saved engagement config
    └── templates/
        └── standard.yaml    # Engagement templates
```

**TUI Configuration Wizard:**
- Guided engagement setup with validation
- Save/load engagement configurations
- Runtime adjustments without restart

**Automation priority:**
- Auto-detect LLM provider availability
- Auto-configure Redis connection
- Smart defaults for common scenarios
- Minimal manual configuration required

### Swarms Framework Integration

**Integration approach:** Selective adoption — use proven components, build custom where needed

| Swarms Component | Usage | Rationale |
|------------------|-------|-----------|
| **MixtureOfAgents** | ✅ Use as-is | Perfect fit for Director Ensemble synthesis |
| **SwarmRouter** | ✅ Use as-is | Unified routing between swarm types |
| **Agent base class** | ⚠️ Extend | Add stigmergic pub/sub hooks to lifecycle |
| **Memory (ChromaDB)** | ❌ Replace | Build custom Redis-based stigmergic memory |
| **Scale layer** | ❌ Build custom | 10,000+ agent optimization not in Swarms |

**Integration architecture:**

```
┌─────────────────────────────────────────────────┐
│              Cyber-Red Core Layer               │
├─────────────────────────────────────────────────┤
│  Director Ensemble                              │
│  └─ Swarms MixtureOfAgents                     │
│      ├─ DeepSeek v3.2 Agent (strategy)         │
│      ├─ Kimi K2 Agent (deep reasoning)         │
│      └─ MiniMax M2 Agent (creative evasion)    │
│      → Aggregator synthesizes into action       │
├─────────────────────────────────────────────────┤
│  Swarm Routing                                  │
│  └─ SwarmRouter                                │
│      ├─ Recon Swarm (ConcurrentWorkflow)       │
│      ├─ Exploit Swarm (SequentialWorkflow)     │
│      └─ Post-Ex Swarm (ConcurrentWorkflow)     │
├─────────────────────────────────────────────────┤
│  Stigmergic Layer (Custom)                      │
│  └─ Redis pub/sub P2P coordination             │
│      ├─ Finding propagation                     │
│      ├─ Strategy emergence                      │
│      └─ Swarm-wide state signals               │
├─────────────────────────────────────────────────┤
│  Extended Agent (Custom)                        │
│  └─ Swarms Agent + stigmergic hooks            │
│      ├─ on_finding() → publish to Redis        │
│      ├─ on_signal() → react to swarm state     │
│      └─ on_complete() → update stigmergic map  │
└─────────────────────────────────────────────────┘
```

**Version management:**
- Pin Swarms version in requirements
- Monitor upstream for breaking changes
- Contribute fixes back when possible

### Tool Execution Architecture

> **Architecture Decision (2025-12-29):** Swarms-native code execution. Agents generate bash/Python code directly, executed in isolated Kali containers. This approach achieves 98% token reduction vs MCP tool definitions, enables composition via pipes/loops, and leverages LLM training data knowledge of CLI tools. Research validates: Anthropic Engineering shows code execution outperforms tool calling at scale; PentestMCP paper demonstrates 4 tools complete full kill chains; Microsoft Research found 85% performance degradation with large tool spaces.

**Strategy:** Single `kali_execute()` Swarms tool + code generation

**Core Insight:** LLMs already know bash and Kali tools from training data. Instead of 60 semantic tool definitions (~6,000 tokens), we provide ONE execution tool (~200 tokens). Agents compose complex operations via pipes, loops, and standard Unix patterns.

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    SWARMS AGENT (LLM-Powered)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Agent receives task from Director Ensemble or stigmergic    │
│  2. LLM reasons about approach using training data knowledge    │
│  3. Agent generates bash/Python code for execution              │
│  4. Calls: kali_execute("nmap -sV target | grep open")         │
│                                                                  │
└─────────────────────────────────────┬───────────────────────────┘
                                      │
                    tool call: kali_execute(code)
                                      ↓
┌─────────────────────────────────────────────────────────────────┐
│                    KALI EXECUTOR (Swarms Tool)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SCOPE VALIDATOR (Hard-Gate, Pre-Execution)                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Parse command → extract targets (IPs, URLs, hostnames)      ││
│  │ Validate targets against engagement scope                   ││
│  │ Block forbidden actions (rm -rf, format, etc.)              ││
│  │ DETERMINISTIC: No AI/LLM in validation path                 ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
│  KALI CONTAINER POOL (20-50 containers, async queue)           │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Execute code in isolated kali-linux-everything container    ││
│  │ Timeout enforcement (300s default)                          ││
│  │ Network namespace isolation per engagement                   ││
│  │ Backpressure at 80% queue depth → agent self-throttling     ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
│  OUTPUT PROCESSING                                               │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Tier 1: Structured parsers (~30 high-frequency tools)       ││
│  │ Tier 2: LLM summarization (all other tools)                 ││
│  │ Tier 3: Raw truncated output (fallback/debug)               ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
│  STIGMERGIC PUBLICATION                                         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Findings → Redis pub/sub (findings:{hash}:{type})           ││
│  │ Other agents subscribe and react                            ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
# src/tools/kali_executor.py — Swarms-compatible tool

from swarms import Agent
import json

class KaliExecutor:
    """Swarms-native tool for Kali command execution."""

    def __init__(
        self,
        scope_validator: ScopeValidator,
        container_pool: KaliContainerPool,
        output_processor: OutputProcessor,
        event_bus: EventBus,
        engagement_id: str
    ):
        self.scope = scope_validator
        self.containers = container_pool
        self.parser = output_processor
        self.events = event_bus
        self.engagement_id = engagement_id

    def kali_execute(self, code: str) -> str:
        """Execute bash/Python code in Kali Linux container.

        Args:
            code: Bash command(s) to execute. Supports pipes, loops,
                  and standard Unix patterns. Can chain multiple tools.

        Returns:
            JSON string with structured findings and execution result.

        Examples:
            kali_execute("nmap -sV 192.168.1.1 -oX -")
            kali_execute("sqlmap -u 'http://target/page?id=1' --batch --forms")
            kali_execute("nmap -sV target | grep open | cut -d/ -f1")
        """
        # 1. Parse and validate scope (HARD GATE - deterministic)
        targets = self._extract_targets(code)
        if not self.scope.are_targets_allowed(targets):
            return json.dumps({
                "success": False,
                "error": "SCOPE_VIOLATION",
                "blocked_targets": targets,
                "message": "Command targets out-of-scope systems"
            })

        # 2. Execute in isolated container
        container = self.containers.acquire()
        try:
            result = container.execute(
                code,
                timeout=300,
                capture_output=True
            )
        finally:
            self.containers.release(container)

        # 3. Parse output (detect tool, apply parser)
        tool = self._detect_tool(code)
        structured = self.parser.process(
            stdout=result.stdout,
            stderr=result.stderr,
            tool=tool,
            exit_code=result.exit_code
        )

        # 4. Publish findings to stigmergic layer
        if structured.findings:
            for finding in structured.findings:
                self.events.publish_finding(
                    finding=finding,
                    engagement_id=self.engagement_id
                )

        # 5. Return structured result to agent
        return json.dumps({
            "success": result.exit_code == 0,
            "tool": tool,
            "findings": [f.to_dict() for f in structured.findings],
            "summary": structured.summary,
            "raw_truncated": result.stdout[:2000] if len(result.stdout) > 2000 else result.stdout
        })


# Creating a Swarms agent with kali_execute
def create_recon_agent(engagement_config: EngagementConfig) -> Agent:
    """Create a reconnaissance agent with Kali execution capability."""

    executor = KaliExecutor(
        scope_validator=ScopeValidator(engagement_config.scope),
        container_pool=KaliContainerPool.get_instance(),
        output_processor=OutputProcessor(),
        event_bus=EventBus.get_instance(),
        engagement_id=engagement_config.id
    )

    return Agent(
        agent_name=f"recon-{uuid.uuid4().hex[:8]}",
        model_name="deepseek-ai/deepseek-v3_2",
        tools=[executor.kali_execute],  # ONE tool, 600+ capabilities
        system_prompt=RECON_AGENT_PROMPT,
        max_loops=10,
        tool_retry_attempts=3,
    )
```

**How Agents Use Tools:**

```
Agent: "I need to scan the target for open ports and check for vulnerabilities"

# Agent generates code (leveraging training data knowledge):
kali_execute("""
nmap -sV 192.168.1.1 -oX /tmp/scan.xml && \
nuclei -t cves/ -u http://192.168.1.1 -j
""")

# Returns structured result:
{
  "success": true,
  "tool": "nmap+nuclei",
  "findings": [
    {"type": "open_port", "port": 22, "service": "ssh"},
    {"type": "open_port", "port": 80, "service": "http"},
    {"type": "vulnerability", "cve": "CVE-2021-44228", "severity": "critical"}
  ],
  "summary": "Found 2 open ports and 1 critical vulnerability (Log4Shell)"
}

# Complex chained operations in ONE call:
kali_execute("""
nmap -sV 192.168.1.0/24 -oG - | grep 'open' | awk '{print $2}' | \
xargs -I {} sqlmap -u "http://{}/" --batch --forms --output-dir=/tmp/sqli
""")
```

**Why Code Execution > Tool Definitions:**

| Aspect | MCP Tool Definitions | Swarms Code Execution |
|--------|---------------------|----------------------|
| **Token overhead** | 60 tools × ~100 tokens = 6,000 | 1 tool × ~200 tokens = 200 |
| **Tool coverage** | 60 semantic tools | 600+ (all Kali CLI tools) |
| **Composition** | Multiple round-trips | Pipes, loops in ONE call |
| **New tools** | Requires adapter development | Immediate (LLM knows bash) |
| **Success rate** | Standard | ~20% higher on complex tasks (CodeAct research) |
| **Round-trips** | One per tool | ~30% fewer (CodeAct research) |

**Scope Enforcement:**

The `scope_validator` applies hard-gate rules BEFORE execution:

```python
class ScopeValidator:
    def are_targets_allowed(self, targets: List[str]) -> bool:
        """
        Deterministic scope validation.
        Returns False to block execution.
        No AI/LLM in this path — pure code validation.
        """
        for target in targets:
            # Check IP/CIDR ranges
            if self._is_ip(target):
                if not self._ip_in_scope(target):
                    return False

            # Check hostnames/URLs
            elif self._is_hostname(target):
                if not self._hostname_in_scope(target):
                    return False

        return True

    def _extract_targets(self, command: str) -> List[str]:
        """Parse command to extract all target references."""
        # Uses regex + AST parsing, not LLM
        targets = []
        targets.extend(self._extract_ips(command))
        targets.extend(self._extract_urls(command))
        targets.extend(self._extract_hostnames(command))
        return targets
```

**Integration with Existing Infrastructure:**

- **WorkerPool:** Unchanged — Kali container runs as a worker
- **EventBus:** Unchanged — Executor publishes findings to event bus
- **Swarms Framework:** Native — `kali_execute()` is a standard Swarms tool
- **Stigmergic Memory:** Unchanged — Findings published to Redis
- **Container Pool:** Unchanged — Isolated execution environment

**Testing (No Mocks):**

```python
# tests/integration/test_kali_executor.py

def test_nmap_scan_real_target(kali_executor, cyber_range):
    """Real nmap scan against cyber range target."""
    result = json.loads(kali_executor.kali_execute(
        f"nmap -sV {cyber_range.target_ip}"
    ))
    assert result["success"]
    assert len(result["findings"]) > 0

def test_scope_blocks_out_of_scope(kali_executor):
    """Verify scope validator blocks out-of-scope targets."""
    result = json.loads(kali_executor.kali_execute(
        "nmap -sV 8.8.8.8"  # Google DNS, never in scope
    ))
    assert not result["success"]
    assert result["error"] == "SCOPE_VIOLATION"

def test_complex_chain_execution(kali_executor, cyber_range):
    """Test multi-tool chain in single execution."""
    result = json.loads(kali_executor.kali_execute(f"""
        nmap -sV {cyber_range.target_ip} -oG - | \\
        grep 'open' | \\
        awk '{{print $2}}'
    """))
    assert result["success"]
```

**Tool Manifest (Reference for Agent Prompts):**

```yaml
# tools/manifest.yaml — Auto-generated at Docker build time
# Used in agent system prompts for capability awareness
categories:
  reconnaissance:
    - nmap, masscan, subfinder, amass, whatweb, wafw00f, dnsrecon
  web_application:
    - nuclei, nikto, ffuf, dirb, gobuster, wpscan, sqlmap
  exploitation:
    - metasploit, hydra, medusa, crackmapexec, impacket-*
  post_exploitation:
    - mimikatz, bloodhound, linpeas, winpeas
  wireless:
    - aircrack-ng, kismet, wifite, reaver
  # ... 600+ total tools
```

### Vulnerability Intelligence Layer Architecture

**Purpose:** Real-time exploit intelligence that agents query when discovering targets. Aggregates CISA KEV, NVD, ExploitDB, Nuclei, and Metasploit into prioritized results.

**Intelligence Flow:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT discovers "Apache/2.4.49" on port 443                                │
│      │                                                                       │
│      ▼                                                                       │
│  intelligence.query(service="apache", version="2.4.49")                     │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INTELLIGENCE AGGREGATOR                              │
│                                                                              │
│  ┌─────────┐  ┌─────────┐  ┌───────────┐  ┌─────────┐  ┌───────────────┐   │
│  │CISA KEV │  │   NVD   │  │ ExploitDB │  │ Nuclei  │  │ Metasploit    │   │
│  │(JSON)   │  │(nvdlib) │  │(searchspl)│  │(index)  │  │ (msfrpcd RPC) │   │
│  └────┬────┘  └────┬────┘  └─────┬─────┘  └────┬────┘  └───────┬───────┘   │
│       └────────────┴─────────────┴─────────────┴───────────────┘           │
│                                   ↓                                         │
│  PRIORITIZATION: KEV > Critical+Exploit > High+Exploit > MSF > Nuclei > PoC│
│                                   ↓                                         │
│  CACHE: Redis (TTL: 1hr) ──► Return IntelligenceResult                     │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  AGENT receives prioritized exploits:                                        │
│    CVE-2021-41773 (P1: CISA KEV) → msf:exploit/multi/http/apache_normalize  │
│    CVE-2021-42013 (P2: Critical) → nuclei:cves/2021/CVE-2021-42013.yaml     │
│      │                                                                       │
│      ▼                                                                       │
│  Agent executes highest-priority exploit → publishes finding to stigmergic  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Metasploit RPC:** Connects via msgpack-rpc (port 55553) for module search, payload generation, and session management. Enables post-exploitation coordination across swarm.

**Stigmergic Integration:** Intelligence results published to `findings:{target_hash}:intel_enriched` so other agents skip redundant queries.

### RAG Escalation Layer Architecture

**Purpose:** Advanced methodology retrieval when standard intelligence exhausted. Triggered by Director (strategy pivots) or agents (repeated failures).

**Escalation Flow:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Intelligence Layer returns no viable exploits OR agent fails 3+ attempts   │
│      │                                                                       │
│      ▼                                                                       │
│  rag.query("lateral movement techniques for hardened Windows Server 2022")  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RAG LAYER                                       │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    LanceDB (embedded, ~70K vectors)                    │  │
│  │                    ATT&CK-BERT embeddings (CPU-only)                   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                   │                                          │
│  ┌─────────┐ ┌────────────┐ ┌───────────┐ ┌─────────┐ ┌─────────┐          │
│  │ ATT&CK  │ │Atomic Red  │ │HackTricks │ │Payloads │ │LOLBAS/  │          │
│  │         │ │Team        │ │           │ │AllThe   │ │GTFOBins │          │
│  └─────────┘ └────────────┘ └───────────┘ └─────────┘ └─────────┘          │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  Returns methodology chunks with metadata:                                   │
│    - ATT&CK technique IDs (T1021.002, T1550.002)                            │
│    - Source + last_updated                                                   │
│    - Relevance score                                                         │
│  Director/Agent incorporates into next action planning                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Stack:** LanceDB (embedded) + ATT&CK-BERT (CPU) + sentence-transformers

**Update:** TUI button triggers `rag.update()` → fetches latest from GitHub sources → re-embeds changed documents.

### LLM Provider Management

**Current Implementation: NVIDIA NIM**

Cyber-Red v2 uses NVIDIA NIM as the unified LLM provider for the Director Ensemble. All three models are available through NIM's OpenAI-compatible API, simplifying integration and ensuring consistent performance.

| Model | NIM Identifier | Role in Ensemble |
|-------|----------------|------------------|
| **DeepSeek v3.2** | `deepseek-ai/deepseek-v3_2` | Strategic planning, methodology |
| **Kimi K2** | `moonshot-ai/kimi-k2` | Deep reasoning, analysis |
| **MiniMax M2** | `minimaxai/minimax-m2` | Creative approaches, evasion (interleaved thinking) |

**Why NVIDIA NIM:**
- Unified API endpoint for all Director Ensemble models
- OpenAI-compatible interface — standard integration pattern
- TensorRT-LLM optimization — low latency for real-time synthesis
- All models currently available on build.nvidia.com
- Future: self-hosted on NVIDIA GPUs when needed

**Current configuration:**
```yaml
# ~/.cyber-red/config.yaml
llm_provider:
  type: nvidia_nim
  base_url: https://integrate.api.nvidia.com/v1
  api_key: ${NVIDIA_NIM_API_KEY}

director_ensemble:
  models:
    strategist:
      model: deepseek-ai/deepseek-v3_2
      role: "Strategic planning and methodology"
      timeout: 30
    analyst:
      model: moonshot-ai/kimi-k2
      role: "Deep reasoning and analysis"
      timeout: 45
    creative:
      model: minimaxai/minimax-m2
      role: "Creative approaches and evasion"
      timeout: 30
      # Note: M2 uses interleaved thinking with <think>...</think> tags

  aggregation:
    strategy: synthesis  # not voting
    timeout: 60
    preserve_thinking_tags: true  # For M2 reasoning visibility
```

**Future: Stable Provider Migration**

When transitioning to stable/direct providers:

| Current (NIM) | Future (Direct) | Migration Path |
|---------------|-----------------|----------------|
| NIM DeepSeek v3.2 | DeepSeek API direct | Swap `base_url`, same model ID |
| NIM Kimi K2 | Moonshot API direct | Swap `base_url`, same model ID |
| NIM MiniMax M2 | MiniMax API direct | Swap `base_url`, same model ID |

**Provider abstraction layer:**
```python
class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages, model) -> Response

class NIMProvider(LLMProvider):
    # Current implementation

class DirectProvider(LLMProvider):
    # Future: direct API calls to each provider
```

The abstraction ensures migration to stable providers requires only config changes, not code changes.

**Resilience (current NIM setup):**
- Single API key for all models
- Unified rate limiting and error handling
- Health check: `GET /v1/models` to verify availability
- Fallback: If NIM unavailable, graceful degradation with warning

**MiniMax M2 Special Handling:**
MiniMax M2 uses interleaved thinking (`<think>...</think>` tags). The Director Ensemble aggregator must:
- Preserve thinking tags in conversation history
- Extract reasoning from `<think>` blocks for synthesis
- Present final output without tags to operator (unless debug mode)

### Implementation Considerations

**Critical implementation priorities:**

| Priority | Component | Why |
|----------|-----------|-----|
| 1 | Stigmergic Redis layer | Core innovation enabler |
| 2 | Director Ensemble (MixtureOfAgents) | Decision-making core |
| 3 | SwarmRouter integration | Swarm type management |
| 4 | Agent extension (stigmergic hooks) | P2P coordination |
| 5 | Kali Executor + Output Parsers | Tool integration foundation |
| 6 | TUI wizard | User experience |
| 7 | Output format generators | Deliverable quality |

**Technical debt to avoid:**
- Don't fork Swarms — extend and contribute back
- Don't build monolithic adapters — keep SDK thin
- Don't hardcode provider configs — keep flexible
- Don't skip hot reload — mid-engagement updates matter

---

## Functional Requirements

### Agent Orchestration

- **FR1**: Operator can issue mission directives in natural language
- **FR2**: System can deploy and coordinate 10,000+ concurrent agents
- **FR3**: Director Ensemble can synthesize strategies from three LLMs (DeepSeek, Kimi K2, MiniMax)
- **FR4**: Agents can share findings in real-time via stigmergic P2P coordination
- **FR5**: System can route tasks to appropriate swarm types (recon, exploit, post-ex)
- **FR6**: Agents can trigger emergent attack strategies based on collective findings

### War Room TUI

- **FR7**: Operator can view virtualized list of 10,000+ agents
- **FR8**: System can bubble anomalies and attention-required agents to top
- **FR9**: Operator can view real-time finding stream (separate from agent status)
- **FR10**: Operator can view Director Ensemble outputs (all three perspectives)
- **FR11**: Operator can view stigmergic connections between agents (Hive Matrix)
- **FR12**: Operator can access drop box status panel
- **FR85**: Operator can access RAG management panel (update button, ingestion status, corpus stats)

### Authorization & Governance

- **FR13**: System can prompt for human authorization on lateral movement
- **FR14**: System can prompt for human authorization on scope expansion (e.g., DDoS)
- **FR15**: Operator can respond to authorization requests with Yes/No + additional constraints
- **FR16**: System can maintain authorization requests as pending (no auto-approve/deny on timeout)
- **FR17**: Operator can trigger kill switch to halt all operations (<1s under load)
- **FR18**: Kill switch can execute hybrid control (instant halt + graceful shutdown)
- **FR19**: Operator can adjust scope validator rules at runtime

### Scope Enforcement

- **FR20**: System can enforce hard-gate scope validation (deterministic, not AI-based)
- **FR21**: System can log all scope checks to audit trail
- **FR22**: System can surface situational awareness alerts for unexpected discoveries
- **FR23**: Operator can respond to situational alerts with Continue/Stop + notes

### Drop Box Operations

- **FR24**: System can generate cross-platform drop box binaries (Go, zero dependencies)
- **FR25**: Operator can configure drop box deployment via natural language TUI
- **FR26**: System can execute deterministic pre-flight protocol (PING→EXEC_TEST→STREAM_TEST→NET_ENUM→READY)
- **FR27**: System can display heartbeat indicator for C2 link status
- **FR28**: Operator can trigger one-click abort/remote wipe of drop box
- **FR29**: Drop box can relay commands to target network and stream results back
- **FR30**: Drop box can execute WiFi toolkit commands locally (aircrack-ng, wifite, kismet)

### Tool Integration

- **FR31**: System exposes 600+ tools via Swarms-native `kali_execute()` code execution
- **FR32**: Agents generate bash/Python code executed in isolated Kali containers
- **FR33**: Output processor returns structured findings (Tier 1 parsers ~30 tools) or LLM summaries (Tier 2)
- **FR34**: Output parsers hot-reloadable without restart
- **FR35**: Container pool supports mock mode (CI-safe) and real mode (validation)

### Vulnerability Intelligence Layer

- **FR65**: System can query unified intelligence aggregator for exploit data across all sources
- **FR66**: Intelligence aggregator can query CISA KEV for known exploited vulnerabilities (priority targeting)
- **FR67**: Intelligence aggregator can query NVD via nvdlib for CVE details, CVSS scores, affected versions
- **FR68**: Intelligence aggregator can query ExploitDB via searchsploit for proof-of-concept exploits
- **FR69**: Intelligence aggregator can query Nuclei template index for detection/exploitation templates
- **FR70**: Intelligence aggregator can query Metasploit via msfrpcd RPC for modules, payloads, aux scanners
- **FR71**: Agents can request intelligence enrichment when discovering services/versions
- **FR72**: Intelligence results include prioritization (CISA KEV > Critical CVE > High CVE > PoC available)
- **FR73**: Intelligence layer caches results in Redis for offline capability (configurable TTL)
- **FR74**: Metasploit RPC connection supports session management for post-exploitation coordination
- **FR75**: Intelligence queries are non-blocking — agents continue if sources timeout

### RAG Escalation Layer

- **FR76**: System provides RAG layer for advanced methodology retrieval when intelligence layer exhausted
- **FR77**: RAG corpus includes MITRE ATT&CK, Atomic Red Team, HackTricks, PayloadsAllTheThings, LOLBAS, GTFOBins
- **FR78**: Director Ensemble can query RAG for strategic pivot methodologies
- **FR79**: Individual agents can query RAG when repeated exploit attempts fail
- **FR80**: RAG uses LanceDB (embedded, self-hosted) with ATT&CK-BERT embeddings (CPU-only)
- **FR81**: Operator can trigger RAG update via TUI "Update RAG" button
- **FR82**: System supports scheduled RAG refresh (weekly for core sources)
- **FR83**: RAG queries return methodology with metadata (source, date, technique IDs)
- **FR84**: RAG results include ATT&CK technique mapping for kill chain correlation

### Evidence & Deliverables

- **FR36**: System can capture screenshots as evidence
- **FR37**: *(Deferred to v2.1)* System can record video for complex multi-step exploits
- **FR38**: System can generate cryptographic proof (SHA-256 + signature) for each finding
- **FR39**: System can generate vulnerability reports with reproducible steps
- **FR40**: System can export findings in multiple formats (MD, JSON, SARIF, CSV, HTML, STIX)
- **FR41**: System can generate client-facing submission report with full objective documentation

### Data Management

- **FR42**: Operator can access all exfiltrated data via TUI menu
- **FR43**: System stores data encrypted at rest (AES-256)
- **FR44**: System cannot auto-delete or schedule deletion of any data
- **FR45**: Operator can manually delete data through TUI

### Configuration & Modes

- **FR46**: Operator can configure system via layered config (system, engagement, runtime, secrets)
- **FR47**: Operator can run in interactive mode (TUI, real-time authorization)
- **FR48**: Operator can run in scriptable mode (CLI args, headless, pre-approved actions)
- **FR49**: External systems can integrate via REST/WebSocket API

### Session & Execution Persistence

- **FR55**: System operates as a background daemon that survives operator SSH disconnection
- **FR56**: Operator can pause engagement (agents suspended, state preserved in memory for instant resume)
- **FR57**: Operator can resume paused engagement instantly (<1s, no checkpoint reload required)
- **FR58**: Operator can attach TUI to running or paused engagement
- **FR59**: Operator can detach TUI without stopping engagement (Ctrl+D or `detach` command)
- **FR60**: Operator can list all engagements with status (initializing/running/paused/stopped/completed)
- **FR61**: System can run multiple concurrent engagements (resource-permitting)

### Emergence & Coordination

- **FR62**: All agent actions must log which stigmergic signals influenced the decision (decision_context field)
- **FR63**: System supports Deputy Operator role for authorization backup when primary operator unavailable
- **FR64**: System auto-pauses engagement after 24h of pending authorization requests without response

### Audit & Compliance

- **FR50**: System can maintain timestamped audit trail (NTP-synchronized, cryptographically signed)
- **FR51**: System can log all authorization decisions with operator acknowledgment
- **FR52**: System can generate liability waiver acknowledgment at engagement start
- **FR53**: System can produce tamper-evident evidence records

---

## Non-Functional Requirements

### Performance

| NFR | Metric | Gate |
|-----|--------|------|
| **NFR1**: Agent coordination latency | <1s stigmergic propagation | Hard |
| **NFR2**: Kill switch response | <1s halt all operations under 10K agent load | Hard |
| **NFR3**: Engagement speed | 10x faster than v1 baseline | Hard |
| **NFR4**: TUI responsiveness | <100ms for UI interactions with 10K agents rendered | Hard |
| **NFR5**: WebSocket push latency | <500ms authorization request delivery | Soft |

### Scalability

| NFR | Metric | Gate |
|-----|--------|------|
| **NFR6**: Agent concurrency | 10,000+ simultaneous agents | Hard |
| **NFR7**: Scale limit | Hardware-bounded only, no artificial limits | Hard |
| **NFR8**: Memory efficiency | Stigmergic coordination O(1), not O(n) | Hard |
| **NFR9**: Graceful degradation | 10x agent load causes <20% performance degradation | Soft |

### Reliability

| NFR | Metric | Gate |
|-----|--------|------|
| **NFR10**: System stability | 99.9% uptime during engagement | Hard |
| **NFR11**: C2 resilience | Drop box reconnects within 30s on network interruption | Hard |
| **NFR12**: State preservation | Graceful shutdown preserves 100% of findings | Hard |
| **NFR13**: Agent recovery | Failed agents restart without losing context | Soft |

### Security

| NFR | Metric | Gate |
|-----|--------|------|
| **NFR14**: Data encryption | AES-256 at rest for all exfiltrated data | Hard |
| **NFR15**: Evidence integrity | SHA-256 + cryptographic signature on all findings | Hard |
| **NFR16**: Timestamp integrity | NTP-synchronized, cryptographically signed | Hard |
| **NFR17**: C2 channel security | mTLS or equivalent for drop box communication | Hard |
| **NFR18**: Secret management | API keys never logged or exposed in output | Hard |

### Testability

| NFR | Metric | Gate |
|-----|--------|------|
| **NFR19**: Unit test coverage | 100% | **Hard gate — no ship without** |
| **NFR20**: Integration test coverage | 100% | **Hard gate — no ship without** |
| **NFR21**: E2E test coverage | Full attack chain validation in cyber range | Hard |
| **NFR22**: Safety test coverage | Scope enforcement, kill switch, authorization | Hard |
| **NFR23**: Scale test validation | 10,000 agent stress testing | Hard |
| **NFR24**: Mock mode coverage | All adapters testable without real tools | Hard |

### Maintainability

| NFR | Metric | Gate |
|-----|--------|------|
| **NFR25**: Adapter hot reload | Add/update adapters without system restart | Hard |
| **NFR26**: Config flexibility | No hardcoded provider configs | Hard |
| **NFR27**: Swarms compatibility | Don't fork — extend and contribute back | Soft |

### Session Persistence

| NFR | Metric | Gate |
|-----|--------|------|
| **NFR30**: Engagement persistence | Engagement survives operator SSH disconnect indefinitely | Hard |
| **NFR31**: Pause-to-resume latency | <1s (hot state in memory, no checkpoint reload) | Hard |
| **NFR32**: TUI attach latency | <2s from attach command to operational TUI with full state | Hard |
| **NFR33**: System restart recovery | All paused/stopped engagements recoverable after daemon restart | Hard |
| **NFR34**: Concurrent engagements | Support 5+ simultaneous engagements (resource-dependent) | Soft |

### Emergence Validation

| NFR | Metric | Gate |
|-----|--------|------|
| **NFR35**: Emergence score | Stigmergic swarm produces >20% novel attack chains vs isolated agents | **Hard gate — no ship without** |
| **NFR36**: Causal chain depth | At least one emergence chain with 3+ hops (Finding→Action→Finding→Action) | Hard |
| **NFR37**: Emergence traceability | 100% of agent actions include decision_context linking to influencing signals | Hard |

---

## Supplementary Requirements (Gap Analysis Resolution)

*This section addresses gaps identified during multi-agent PRD review (2025-12-27).*

### Scale Testing vs Production Capacity

**Clarification:** The 10,000+ agent scale is hardware-bound — no artificial limits in code. However, test validation uses practical thresholds:

| Environment | Agent Scale | Purpose |
|-------------|-------------|---------|
| **Unit/Integration Tests** | 10-50 | Fast CI validation |
| **Scale Tests (Success Gate)** | **100 agents** | Validates architecture patterns hold under load |
| **Stress Tests (Ceiling Discovery)** | 1,000+ | Find degradation curve, document actual ceiling |
| **Production** | **10,000+ (hardware-bound)** | No code limits — scales with available compute/Redis capacity |

**Acceptance Criteria (NFR23 clarified):**
- ✅ 100-agent scale test passes with <1s stigmergic latency
- ✅ No artificial agent count limits in codebase
- ✅ Degradation curve documented from stress testing
- ✅ Actual ceiling documented (hardware-specific)

---

### Error Handling Requirements

| Requirement | Scope | Behavior |
|-------------|-------|----------|
| **ERR1**: Tool execution failure | Kali Executor | Log error, return structured error result, agent continues with next action |
| **ERR2**: LLM provider timeout | Director Ensemble | Retry 3x with exponential backoff, then use available models only |
| **ERR3**: Redis connection loss | Stigmergic layer | Buffer messages locally (10s max), reconnect with exponential backoff |
| **ERR4**: Drop box connection loss | C2 channel | Retry for 30s, then surface "C2 lost" alert to operator |
| **ERR5**: Agent crash | Worker pool | Log crash, spawn replacement agent, resume from last checkpoint |
| **ERR6**: Scope validator failure | Hard-gate | Fail-closed — block action, alert operator, log incident |

**Principle:** Fail-safe for safety-critical components (scope, authorization), fail-forward for operational components (adapters, agents).

---

### Network Interruption Recovery

| Scenario | Recovery Behavior |
|----------|-------------------|
| **Operator network loss** | TUI reconnects automatically; pending authorizations remain pending |
| **Redis network loss** | Agents buffer findings locally, replay on reconnect (30s max buffer) |
| **Drop box network loss** | C2 attempts reconnect for 30s; operator alerted if reconnection fails |
| **LLM provider network loss** | Director Ensemble degrades to available models; operator warned |

**State Preservation:**
- All findings persisted to local storage before stigmergic publish
- Agent state checkpointed every 60s (configurable)
- Engagement can resume from checkpoint after full system restart

---

### Partial Engagement Resume Capability

**FR54**: System can resume engagement from saved state after interruption

| State Component | Persistence Location | Resume Behavior |
|-----------------|---------------------|-----------------|
| Agent assignments | Redis + local checkpoint | Restore agent→task mappings |
| Findings | Local SQLite + Redis | Deduplicate on resume |
| Authorization history | Local audit log | Replay to restore permissions |
| Scope validator config | Engagement YAML | Reload from config |
| Drop box state | C2 negotiates on reconnect | Re-establish channel |

**Resume Command:**
```bash
cyber-red resume --engagement ministry-2025 --from-checkpoint latest
```

---

### Engagement Lifecycle & Session Management

**Engagement State Machine:**

```
                    ┌─────────────┐
                    │ INITIALIZING│
                    └──────┬──────┘
                           │ start
                           ▼
              ┌───────────────────────┐
         ┌───►│       RUNNING         │◄───┐
         │    └───────────┬───────────┘    │
         │                │                │
    resume│          pause│           resume
         │                ▼                │
         │    ┌───────────────────────┐    │
         └────│       PAUSED          │────┘
              └───────────┬───────────┘
                          │ stop
                          ▼
              ┌───────────────────────┐
              │       STOPPED         │
              └───────────┬───────────┘
                          │ (objective achieved or manual)
                          ▼
              ┌───────────────────────┐
              │      COMPLETED        │
              └───────────────────────┘
```

**State Definitions:**

| State | Description | Agent Status | Memory State | Resume Method |
|-------|-------------|--------------|--------------|---------------|
| **INITIALIZING** | Loading config, spawning agents | Starting | Allocating | N/A |
| **RUNNING** | Active engagement, agents working | Active | Hot | N/A (already running) |
| **PAUSED** | Operator paused, agents suspended | Suspended | Hot (in memory) | Instant resume (<1s) |
| **STOPPED** | Halted, state checkpointed to disk | Terminated | Cold (on disk) | Checkpoint resume |
| **COMPLETED** | Objective achieved, final state | Terminated | Archived | Start new engagement |

**CLI Commands for Session Management:**

```bash
# Daemon management
cyber-red daemon start              # Start background daemon (systemd or manual)
cyber-red daemon stop               # Stop daemon (pauses all engagements first)
cyber-red daemon status             # Show daemon health and active engagements

# Session listing
cyber-red sessions                  # List all engagements with status
cyber-red sessions --active         # List running/paused only
cyber-red sessions --format json    # Machine-readable output

# Engagement lifecycle
cyber-red start <engagement.yaml>   # Start new engagement
cyber-red attach <engagement-id>    # Attach TUI to running/paused engagement
cyber-red detach                    # Detach TUI without stopping (Ctrl+D shortcut)
cyber-red pause <engagement-id>     # Pause engagement (instant, keeps state hot)
cyber-red resume <engagement-id>    # Resume paused engagement (instant)
cyber-red stop <engagement-id>      # Stop engagement (checkpoint to disk)
cyber-red restart <engagement-id>   # Resume from last checkpoint (cold start)
```

**Daemon Architecture:**

```
┌──────────────────────────────────────────────────────────────────────┐
│                        OPERATOR TERMINAL                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐          │
│  │ cyber-red      │  │ cyber-red      │  │ cyber-red      │          │
│  │ attach eng-1   │  │ attach eng-2   │  │ sessions       │          │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘          │
└──────────┼───────────────────┼───────────────────┼───────────────────┘
           │                   │                   │
           │    Unix Socket / Named Pipe           │
           ▼                   ▼                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     CYBER-RED DAEMON (background)                     │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    SESSION MANAGER                               │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │ │
│  │  │ Engagement 1│  │ Engagement 2│  │ Engagement 3│              │ │
│  │  │ RUNNING     │  │ PAUSED      │  │ STOPPED     │              │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                              │                                        │
│  ┌───────────────────────────▼───────────────────────────────────┐   │
│  │ CORE: Agents, Stigmergic Layer, Director Ensemble, Tools      │   │
│  └───────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
                               │
               Survives SSH disconnect
               Persists across terminal sessions
```

**TUI Attach/Detach Protocol:**

| Action | Behavior |
|--------|----------|
| `attach` | Connect TUI to daemon, sync full engagement state, begin receiving real-time updates |
| `detach` (Ctrl+D) | Disconnect TUI cleanly, daemon continues execution, no state loss |
| SSH disconnect | Same as detach — daemon continues, can reattach later |
| `pause` | Suspend all agents, keep state in memory, await resume |
| `stop` | Checkpoint state to disk, terminate agents, can restart from checkpoint |

**Authorization During Detached Execution:**

| Scenario | Behavior |
|----------|----------|
| Authorization request while TUI detached | Request queued in daemon, await operator attach |
| Operator attaches | Pending authorization requests displayed immediately |
| Timeout on authorization | Configurable: queue indefinitely (default) or timeout with deny |

---

### Monitoring & Observability Requirements

| Requirement | Implementation | Metric Format |
|-------------|----------------|---------------|
| **OBS1**: Agent count (active/idle/failed) | Prometheus metrics | `cyberred_agents_total{state}` |
| **OBS2**: Stigmergic message rate | Prometheus metrics | `cyberred_stigmergic_messages_per_second` |
| **OBS3**: Finding rate | Prometheus metrics | `cyberred_findings_total` |
| **OBS4**: LLM latency per model | Prometheus histograms | `cyberred_llm_latency_seconds{model}` |
| **OBS5**: Redis health | Health endpoint | `/health/redis` |
| **OBS6**: Drop box health | Heartbeat status | TUI indicator + `/health/dropbox` |
| **OBS7**: Structured logging | JSON to stdout/file | ELK/Loki compatible |
| **OBS8**: Distributed tracing | OpenTelemetry | Trace ID per agent action |
| **OBS9**: Disk space monitoring | Prometheus gauge | `cyberred_disk_usage_bytes`, alert at 90% |
| **OBS10**: Memory per engagement | Prometheus gauge | `cyberred_engagement_memory_bytes{id}` |
| **OBS11**: Emergence score | Prometheus gauge | `cyberred_emergence_score`, real-time emergence tracking |

**Operator Dashboard (TUI):**
- Real-time agent count, finding count, stigmergic activity
- Health indicators for all external dependencies
- Alert stream for warning/error conditions

---

### Redis High Availability

**NFR28**: Redis must support high-availability deployment

| Mode | Configuration | Use Case |
|------|---------------|----------|
| **Single instance** | Default local dev | Development, testing |
| **Sentinel** | 3-node Sentinel | Production HA |
| **Cluster** | 6-node cluster | High-scale production (10K+ agents) |

**Configuration:**
```yaml
redis:
  mode: sentinel  # single | sentinel | cluster
  sentinel:
    master_name: cyberred-master
    nodes:
      - redis-sentinel-1:26379
      - redis-sentinel-2:26379
      - redis-sentinel-3:26379
  failover_timeout: 5s
```

**Behavior on Failover:**
- Automatic reconnection to new master
- Stigmergic messages buffered during failover (5s window)
- No data loss for in-flight messages

---

### Agent Recovery Semantics

**NFR13 (clarified)**: Failed agents restart without losing context

| Recovery Scenario | Mechanism |
|-------------------|-----------|
| **Agent process crash** | Worker pool spawns replacement, loads last checkpoint |
| **Agent OOM** | Container restart with increased memory allocation (up to limit) |
| **Agent stuck (timeout)** | Watchdog kills agent, spawns replacement |
| **Network partition** | Agent continues locally, syncs on reconnect |

**Checkpoint Contents:**
- Current task/subtask assignment
- Accumulated context from stigmergic signals
- Local findings not yet published
- Retry count for current action

**Checkpoint Frequency:** Every 60s or after major state change (configurable)

---

### LLM Provider Fallback Strategy

**NFR29**: System degrades gracefully when LLM providers are unavailable

| Provider Status | Director Ensemble Behavior |
|-----------------|---------------------------|
| All 3 models available | Full synthesis from DeepSeek + Kimi K2 + MiniMax M2 |
| 2 models available | Synthesis from available pair, log degradation warning |
| 1 model available | Single-model operation, operator warned |
| 0 models available | Pause engagement, require operator action |

**Fallback Configuration:**
```yaml
director_ensemble:
  fallback:
    min_models: 1  # Minimum to continue operation
    retry_interval: 30s  # Retry unavailable providers
    alert_threshold: 2  # Alert operator if fewer than N models
```

**Future: Direct Provider Migration**
- NIM → Direct API calls when stable
- Config change only, no code changes required
- Provider abstraction layer already in architecture

---

### Drop Box C2 Protocol Specification

**Protocol:** mTLS (mutual TLS) over WebSocket

| Parameter | Value |
|-----------|-------|
| **Transport** | WSS (WebSocket Secure) |
| **Authentication** | mTLS — both ends present certificates |
| **Certificate Authority** | Self-signed CA generated per engagement |
| **Certificate Rotation** | 24-hour validity, auto-renewal |
| **Fallback** | None — C2 security is non-negotiable |

**Message Format:**
```json
{
  "type": "command|result|heartbeat",
  "id": "uuid",
  "timestamp": "ISO8601",
  "payload": { ... },
  "signature": "HMAC-SHA256"
}
```

**Heartbeat:**
- Interval: 5s
- Missed heartbeats before alert: 3 (15s)
- Missed heartbeats before "C2 lost": 6 (30s)

---

### Disaster Recovery Requirements

| Scenario | Recovery Procedure | RTO | RPO |
|----------|-------------------|-----|-----|
| **Cyber-Red server crash** | Restart from checkpoint, resume engagement | <5 min | 60s (checkpoint interval) |
| **Redis data loss** | Restore from Redis snapshot, replay local buffers | <10 min | Last snapshot + buffer |
| **Drop box lost** | Deploy new drop box, operator reconfigures | Manual | N/A (stateless relay) |
| **Full infrastructure loss** | Rebuild from config, findings preserved in local storage | <30 min | Last checkpoint |

**Backup Strategy:**
- Redis: RDB snapshots every 5 min, AOF for sub-second recovery
- Findings: Written to local SQLite before Redis publish
- Config: Version controlled (git), not in backup scope
- Evidence: Replicated to external storage (configurable)

---

### v1 Performance Baselines

*Required to validate "10x faster than v1" (NFR3)*

| Metric | v1 Baseline | v2 Target | Measurement Method |
|--------|-------------|-----------|-------------------|
| **Agent startup time** | TBD — require v1 benchmark run | <10% of v1 | Stopwatch from init to first action |
| **Finding propagation** | TBD — isolated agents, no propagation | <1s | Time from discovery to TUI display |
| **Engagement completion (standard scope)** | TBD — require v1 benchmark run | <10% of v1 time | Full engagement stopwatch |
| **Memory per agent** | TBD — require v1 profiling | <50% of v1 | Container memory metrics |

**Action Required:** Before architecture phase, run v1 baseline benchmarks and document results.

---

## Requirements Traceability Note

Each FR and NFR above should be mapped to:
1. **Architecture component** (during Architecture phase)
2. **Epic/Story** (during Epics & Stories phase)
3. **Test case** (during Test Strategy phase)

Traceability matrix to be generated during `/bmad-bmm-workflows-testarch-trace`.

