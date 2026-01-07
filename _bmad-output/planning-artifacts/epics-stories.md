---
stepsCompleted: [1, 2, 3]
inputDocuments:
  - docs/2-plan/prd.md
  - docs/3-solutioning/architecture.md
  - docs/2-plan/ux-design.md
workflowType: 'epics-and-stories'
project_name: 'Cyber-Red'
user_name: 'root'
date: '2025-12-31'
party_mode_review: true
lastEpicCompleted: 15
storiesComplete: true
---

# Cyber-Red v2.0 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Cyber-Red v2.0, decomposing the requirements from the PRD, UX Design, and Architecture into implementable stories. This structure was refined through Party Mode analysis with Winston (Architect), Mary (Analyst), John (PM), Murat (TEA), Bob (SM), and Amelia (Dev).

## Requirements Inventory

### Functional Requirements (85 FRs)

**Agent Orchestration (FR1-FR6)**
- FR1: Operator can issue mission directives in natural language
- FR2: System can deploy and coordinate 10,000+ concurrent agents
- FR3: Director Ensemble can synthesize strategies from three LLMs (DeepSeek, Kimi K2, MiniMax)
- FR4: Agents can share findings in real-time via stigmergic P2P coordination
- FR5: System can route tasks to appropriate swarm types (recon, exploit, post-ex)
- FR6: Agents can trigger emergent attack strategies based on collective findings

**War Room TUI (FR7-FR12, FR85)**
- FR7: Operator can view virtualized list of 10,000+ agents
- FR8: System can bubble anomalies and attention-required agents to top
- FR9: Operator can view real-time finding stream (separate from agent status)
- FR10: Operator can view Director Ensemble outputs (all three perspectives)
- FR11: Operator can view stigmergic connections between agents (Hive Matrix)
- FR12: Operator can access drop box status panel
- FR85: Operator can access RAG management panel (update button, ingestion status, corpus stats)

**Authorization & Governance (FR13-FR19)**
- FR13: System can prompt for human authorization on lateral movement
- FR14: System can prompt for human authorization on scope expansion (e.g., DDoS)
- FR15: Operator can respond to authorization requests with Yes/No + additional constraints
- FR16: System can maintain authorization requests as pending (no auto-approve/deny on timeout)
- FR17: Operator can trigger kill switch to halt all operations (<1s under load)
- FR18: Kill switch can execute hybrid control (instant halt + graceful shutdown)
- FR19: Operator can adjust scope validator rules at runtime

**Scope Enforcement (FR20-FR23)**
- FR20: System can enforce hard-gate scope validation (deterministic, not AI-based)
- FR21: System can log all scope checks to audit trail
- FR22: System can surface situational awareness alerts for unexpected discoveries
- FR23: Operator can respond to situational alerts with Continue/Stop + notes

**Drop Box Operations (FR24-FR30)**
- FR24: System can generate cross-platform drop box binaries (Go, zero dependencies)
- FR25: Operator can configure drop box deployment via natural language TUI
- FR26: System can execute deterministic pre-flight protocol (PING→EXEC_TEST→STREAM_TEST→NET_ENUM→READY)
- FR27: System can display heartbeat indicator for C2 link status
- FR28: Operator can trigger one-click abort/remote wipe of drop box
- FR29: Drop box can relay commands to target network and stream results back
- FR30: Drop box can execute WiFi toolkit commands locally (aircrack-ng, wifite, kismet)

**Tool Integration (FR31-FR35)**
- FR31: System exposes 600+ tools via Swarms-native `kali_execute()` code execution
- FR32: Agents generate bash/Python code executed in isolated Kali containers
- FR33: Output processor returns structured findings (Tier 1 parsers ~30 tools) or LLM summaries (Tier 2)
- FR34: Output parsers hot-reloadable without restart
- FR35: Container pool supports mock mode (CI-safe) and real mode (validation)

**Vulnerability Intelligence Layer (FR65-FR75)**
- FR65: System can query unified intelligence aggregator for exploit data across all sources
- FR66: Intelligence aggregator can query CISA KEV for known exploited vulnerabilities (priority targeting)
- FR67: Intelligence aggregator can query NVD via nvdlib for CVE details, CVSS scores, affected versions
- FR68: Intelligence aggregator can query ExploitDB via searchsploit for proof-of-concept exploits
- FR69: Intelligence aggregator can query Nuclei template index for detection/exploitation templates
- FR70: Intelligence aggregator can query Metasploit via msfrpcd RPC for modules, payloads, aux scanners
- FR71: Agents can request intelligence enrichment when discovering services/versions
- FR72: Intelligence results include prioritization (CISA KEV > Critical CVE > High CVE > PoC available)
- FR73: Intelligence layer caches results in Redis for offline capability (configurable TTL)
- FR74: Metasploit RPC connection supports session management for post-exploitation coordination
- FR75: Intelligence queries are non-blocking — agents continue if sources timeout

**RAG Escalation Layer (FR76-FR84)**
- FR76: System provides RAG layer for advanced methodology retrieval when intelligence layer exhausted
- FR77: RAG corpus includes MITRE ATT&CK, Atomic Red Team, HackTricks, PayloadsAllTheThings, LOLBAS, GTFOBins
- FR78: Director Ensemble can query RAG for strategic pivot methodologies
- FR79: Individual agents can query RAG when repeated exploit attempts fail
- FR80: RAG uses LanceDB (embedded, self-hosted) with ATT&CK-BERT embeddings (CPU-only)
- FR81: Operator can trigger RAG update via TUI "Update RAG" button
- FR82: System supports scheduled RAG refresh (weekly for core sources)
- FR83: RAG queries return methodology with metadata (source, date, technique IDs)
- FR84: RAG results include ATT&CK technique mapping for kill chain correlation

**Evidence & Deliverables (FR36-FR41)**
- FR36: System can capture screenshots as evidence
- FR37: *(Deferred to v2.1)* System can record video for complex multi-step exploits
- FR38: System can generate cryptographic proof (SHA-256 + signature) for each finding
- FR39: System can generate vulnerability reports with reproducible steps
- FR40: System can export findings in multiple formats (MD, JSON, SARIF, CSV, HTML, STIX)
- FR41: System can generate client-facing submission report with full objective documentation

**Data Management (FR42-FR45)**
- FR42: Operator can access all exfiltrated data via TUI menu
- FR43: System stores data encrypted at rest (AES-256)
- FR44: System cannot auto-delete or schedule deletion of any data
- FR45: Operator can manually delete data through TUI

**Configuration & Modes (FR46-FR49)**
- FR46: Operator can configure system via layered config (system, engagement, runtime, secrets)
- FR47: Operator can run in interactive mode (TUI, real-time authorization)
- FR48: Operator can run in scriptable mode (CLI args, headless, pre-approved actions)
- FR49: External systems can integrate via REST/WebSocket API

**Session & Execution Persistence (FR55-FR61)**
- FR55: System operates as a background daemon that survives operator SSH disconnection
- FR56: Operator can pause engagement (agents suspended, state preserved in memory for instant resume)
- FR57: Operator can resume paused engagement instantly (<1s, no checkpoint reload required)
- FR58: Operator can attach TUI to running or paused engagement
- FR59: Operator can detach TUI without stopping engagement (Ctrl+D or `detach` command)
- FR60: Operator can list all engagements with status (initializing/running/paused/stopped/completed)
- FR61: System can run multiple concurrent engagements (resource-permitting)

**Emergence & Coordination (FR62-FR64)**
- FR62: All agent actions must log which stigmergic signals influenced the decision (decision_context field)
- FR63: System supports Deputy Operator role for authorization backup when primary operator unavailable
- FR64: System auto-pauses engagement after 24h of pending authorization requests without response

**Audit & Compliance (FR50-FR54)**
- FR50: System can maintain timestamped audit trail (NTP-synchronized, cryptographically signed)
- FR51: System can log all authorization decisions with operator acknowledgment
- FR52: System can generate liability waiver acknowledgment at engagement start
- FR53: System can produce tamper-evident evidence records
- FR54: System can resume engagement from saved state after interruption

### Non-Functional Requirements (37 NFRs)

**Performance (NFR1-NFR5)**
- NFR1: Agent coordination latency <1s stigmergic propagation (Hard)
- NFR2: Kill switch response <1s halt all operations under 10K agent load (Hard)
- NFR3: Engagement speed 10x faster than v1 baseline (Hard)
- NFR4: TUI responsiveness <100ms for UI interactions with 10K agents rendered (Hard)
- NFR5: WebSocket push latency <500ms authorization request delivery (Soft)

**Scalability (NFR6-NFR9)**
- NFR6: Agent concurrency 10,000+ simultaneous agents (Hard)
- NFR7: Scale limit hardware-bounded only, no artificial limits (Hard)
- NFR8: Memory efficiency stigmergic coordination O(1), not O(n) (Hard)
- NFR9: Graceful degradation 10x agent load causes <20% performance degradation (Soft)

**Reliability (NFR10-NFR13)**
- NFR10: System stability 99.9% uptime during engagement (Hard)
- NFR11: C2 resilience drop box reconnects within 30s on network interruption (Hard)
- NFR12: State preservation graceful shutdown preserves 100% of findings (Hard)
- NFR13: Agent recovery failed agents restart without losing context (Soft)

**Security (NFR14-NFR18)**
- NFR14: Data encryption AES-256 at rest for all exfiltrated data (Hard)
- NFR15: Evidence integrity SHA-256 + cryptographic signature on all findings (Hard)
- NFR16: Timestamp integrity NTP-synchronized, cryptographically signed (Hard)
- NFR17: C2 channel security mTLS or equivalent for drop box communication (Hard)
- NFR18: Secret management API keys never logged or exposed in output (Hard)

**Testability (NFR19-NFR24)**
- NFR19: Unit test coverage 100% (Hard gate — no ship without)
- NFR20: Integration test coverage 100% (Hard gate — no ship without)
- NFR21: E2E test coverage full attack chain validation in cyber range (Hard)
- NFR22: Safety test coverage scope enforcement, kill switch, authorization (Hard)
- NFR23: Scale test validation 100-agent scale test passes, 10K stress test (Hard)
- NFR24: Mock mode coverage all adapters testable without real tools (Hard)

**Maintainability (NFR25-NFR27)**
- NFR25: Adapter hot reload add/update adapters without system restart (Hard)
- NFR26: Config flexibility no hardcoded provider configs (Hard)
- NFR27: Swarms compatibility don't fork — extend and contribute back (Soft)

**Redis & LLM (NFR28-NFR29)**
- NFR28: Redis must support high-availability deployment (Sentinel/Cluster)
- NFR29: System degrades gracefully when LLM providers are unavailable

**Session Persistence (NFR30-NFR34)**
- NFR30: Engagement persistence — engagement survives operator SSH disconnect indefinitely (Hard)
- NFR31: Pause-to-resume latency <1s (hot state in memory, no checkpoint reload) (Hard)
- NFR32: TUI attach latency <2s from attach command to operational TUI with full state (Hard)
- NFR33: System restart recovery — all paused/stopped engagements recoverable after daemon restart (Hard)
- NFR34: Concurrent engagements — support 5+ simultaneous engagements (resource-dependent) (Soft)

**Emergence Validation (NFR35-NFR37)**
- NFR35: Emergence score — stigmergic swarm produces >20% novel attack chains vs isolated agents (Hard gate — no ship without)
- NFR36: Causal chain depth — at least one emergence chain with 3+ hops (Finding→Action→Finding→Action) (Hard)
- NFR37: Emergence traceability — 100% of agent actions include decision_context linking to influencing signals (Hard)

### Additional Requirements

**Error Handling (ERR1-ERR6 from PRD):**
- ERR1: Tool execution failure — log error, return structured result, agent continues
- ERR2: LLM provider timeout — retry 3x with exponential backoff, use available models only
- ERR3: Redis connection loss — buffer messages locally (10s max), reconnect with exponential backoff
- ERR4: Drop box connection loss — retry for 30s, surface "C2 lost" alert
- ERR5: Agent crash — log crash, spawn replacement, resume from last checkpoint
- ERR6: Scope validator failure — fail-closed, block action, alert operator, log incident

**From Architecture:**
- Swarms v8.0.0+ framework integration (Python 3.11+)
- Redis Sentinel (3-node) for stigmergic pub/sub
- Tri-path kill switch: Redis pub/sub + SIGTERM cascade + Docker API
- NFKC Unicode normalization for command injection prevention
- mTLS with certificate pinning and 24-hour rotation for C2
- Pre-flight checks (REDIS_CHECK, LLM_CHECK, SCOPE_CHECK, DISK_CHECK, MEMORY_CHECK, CERT_CHECK)
- SQLite (WAL mode) for checkpoints with async write queue
- Checkpoint verification (SHA-256 signature, scope hash validation)
- structlog for JSON-formatted logging
- Prometheus metrics (optional)
- systemd integration
- All tests run against real Kali tools (no mocks for behavior)
- Cyber range test environment with standardized targets

**From UX Design:**
- Textual TUI framework with TCSS theming
- Dark mode "Command & Control" aesthetic
- Three-pane War Room layout: Targets | Hive Matrix | Strategy Stream
- F-key navigation (F1-F6) for screen switching
- Dual-path input (keyboard + mouse)
- Kill switch always visible (ESC + sticky button)
- HiveMatrix with virtualized agent list, anomaly bubbling, filter bar
- StrategyStream showing Director Ensemble + stigmergic activity
- AuthorizationModal with swarm state snapshot, auth batching
- HeartbeatIndicator with latency granularity
- WCAG 2.1 Level AA accessibility

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 8 | NL directive parsing |
| FR2 | Epic 7 | 10,000+ agent deployment |
| FR3 | Epic 8 | Director Ensemble synthesis |
| FR4 | Epic 7 | Stigmergic P2P coordination |
| FR5 | Epic 8 | Swarm routing |
| FR6 | Epic 7 | Emergent attack strategies |
| FR7-FR9 | Epic 9 | War Room core visualization |
| FR10 | Epic 11 | Director Ensemble display |
| FR11 | Epic 9 | Hive Matrix |
| FR12 | Epic 11 | Drop box status panel |
| FR13-FR16 | Epic 10 | Authorization prompts/responses |
| FR17-FR18 | Epic 1 + 10 | Kill switch (core + UI) |
| FR19 | Epic 10 | Runtime scope adjustment |
| FR20-FR21 | Epic 1 | Scope enforcement core |
| FR22-FR23 | Epic 10 | Situational alerts |
| FR24-FR30 | Epic 12 | Drop box operations |
| FR31-FR35 | Epic 4 | Tool execution |
| FR36 | Epic 13 | Screenshot evidence |
| FR37 | *v2.1* | Video recording (deferred) |
| FR38-FR41 | Epic 13 | Crypto proof, reports, export |
| FR42, FR45 | Epic 11 | Data browser |
| FR43-FR44 | Epic 13 | Data encryption, no auto-delete |
| FR46 | Epic 2 | Configuration loading |
| FR47 | Epic 9 | Interactive mode |
| FR48-FR49 | Epic 14 | Scriptable/API modes |
| FR50-FR54 | Epic 13 | Audit & compliance |
| FR55-FR61 | Epic 2 | Session persistence |
| FR62 | Epic 7 | Decision context logging |
| FR63-FR64 | Epic 14 | Deputy operator, auto-pause |
| FR65-FR75 | Epic 5 | Intelligence layer |
| FR76-FR84 | Epic 6 | RAG escalation |
| FR85 | Epic 11 | RAG management panel |

### Error Handling Coverage

| Error | Epic | Handling |
|-------|------|----------|
| ERR1 | Epic 4 | Tool execution failure |
| ERR2 | Epic 3 | LLM provider timeout |
| ERR3 | Epic 3 | Redis connection loss |
| ERR4 | Epic 12 | Drop box connection loss |
| ERR5 | Epic 7 | Agent crash recovery |
| ERR6 | Epic 1 | Scope validator failure |

---

## Epic List

### Epic 0: Testing & CI Infrastructure
**User Outcome:** Development team has production-grade testing infrastructure enabling TDD from day one.

**Scope:**
- pytest + pytest-asyncio configuration
- testcontainers-python for real Kali containers
- Self-hosted GitHub Actions runner with Docker
- Test fixtures structure (`tests/fixtures/`)
- Coverage gates (100% unit, 100% integration)
- Cyber-range docker-compose with standardized targets
- Emergence test framework structure (`tests/emergence/`)
- Safety test structure (`tests/safety/`)

**Why First:** Every subsequent epic requires tests. No epic completion without passing tests.

---

### Epic 1: Core Framework & Safety Foundation
**User Outcome:** Operator has safety-critical controls (kill switch, scope validation) and core infrastructure that enable all future capabilities.

**FRs:** FR17, FR18, FR20, FR21
**NFRs:** NFR2, NFR14-NFR18, NFR26
**Errors:** ERR6

**Components:**
- `core/exceptions.py` — CyberRedError hierarchy
- `core/models.py` — Finding, AgentAction, ToolResult dataclasses
- `core/config.py` — YAML config loader
- `core/killswitch.py` — Tri-path kill switch (Redis + SIGTERM + Docker)
- `core/keystore.py` — PBKDF2 key derivation
- `core/ca_store.py` — CA key storage
- `core/time.py` — NTP sync wrapper with drift detection
- `protocols/` — ABCs (AgentProtocol, StorageProtocol, LLMProviderProtocol)
- `tools/scope.py` — Hard-gate scope validator (fail-closed)

---

### Epic 2: Daemon & Session Management
**User Outcome:** Operator can start Cyber-Red daemon, manage multiple engagements, attach/detach TUI without losing state.

**FRs:** FR46, FR55-FR61
**NFRs:** NFR30-NFR34

**Components:**
- `daemon/server.py` — Unix socket server
- `daemon/session_manager.py` — Multi-engagement orchestration
- `daemon/state_machine.py` — Engagement lifecycle (INITIALIZING→RUNNING↔PAUSED→STOPPED→COMPLETED)
- `daemon/ipc.py` — IPC protocol
- `cli.py` — Entry point (`cyber-red daemon start/stop`, `sessions`, `attach`, `detach`, etc.)
- systemd integration (`cyber-red.service`)
- Pre-flight check framework

---

### Epic 3: Communication Infrastructure
**User Outcome:** System has Redis connectivity, LLM gateway, and event bus for all inter-component communication.

**FRs:** (Infrastructure for FR4, FR50)
**NFRs:** NFR1, NFR28, NFR29
**Errors:** ERR2, ERR3

**Components:**
- `storage/redis_client.py` — Redis Sentinel connection with reconnect logic
- `core/events.py` — Redis pub/sub + streams wrapper with HMAC-SHA256 signatures
- `llm/provider.py` — LLMProvider ABC
- `llm/nim.py` — NVIDIA NIM implementation
- `llm/gateway.py` — Singleton LLM gateway (all agent requests)
- `llm/rate_limiter.py` — Token bucket, 30 RPM global cap
- `llm/router.py` — Task complexity → model selection (FAST/STANDARD/COMPLEX)
- `llm/priority_queue.py` — Director-priority request queue

**Why Here:** Tools, Intelligence, RAG, and Agents ALL require Redis and LLM access.

---

### Epic 4: Tool Execution Layer
**User Outcome:** Agents can execute 600+ Kali tools in isolated containers with scope enforcement and structured output parsing.

**FRs:** FR31-FR35
**NFRs:** NFR24, NFR25
**Errors:** ERR1

**Components:**
- `tools/kali_executor.py` — Swarms-native `kali_execute()` tool
- `tools/container_pool.py` — Kali container pool (20-50 containers, mock + real modes)
- `tools/manifest.py` — Auto-generated tool manifest from Kali
- `tools/output.py` — Output processor (Tier 1 parsers + LLM summarization)
- `tools/parsers/` — ~30 high-frequency tool parsers (nmap, nuclei, sqlmap, ffuf, etc.)
- Hot-reload support for parsers

---

### Epic 5: Vulnerability Intelligence Layer
**User Outcome:** Agents can query real-time exploit intelligence from 5 sources with prioritized results and Redis caching.

**FRs:** FR65-FR75
**NFRs:** (Uses NFR28 Redis caching)

**Components:**
- `intelligence/aggregator.py` — Unified query interface (parallel queries, 5s timeout)
- `intelligence/cache.py` — Redis-backed caching (configurable TTL, offline-capable)
- `intelligence/sources/cisa_kev.py` — CISA KEV JSON feed (highest priority)
- `intelligence/sources/nvd.py` — NVD via nvdlib
- `intelligence/sources/exploitdb.py` — SearchSploit wrapper
- `intelligence/sources/nuclei.py` — Nuclei template index
- `intelligence/sources/metasploit.py` — MSF RPC (msgpack-rpc:55553, session management)

**Prioritization:** CISA KEV > Critical CVE > High CVE > MSF module > Nuclei template > PoC

---

### Epic 6: RAG Escalation Layer
**User Outcome:** When standard intelligence is exhausted, system can query advanced methodologies from ATT&CK, HackTricks, and other offensive security knowledge bases.

**FRs:** FR76-FR84

**Components:**
- `rag/store.py` — LanceDB vector store (embedded, ~70K vectors)
- `rag/embeddings.py` — ATT&CK-BERT (CPU-only) + all-mpnet-base-v2 fallback
- `rag/query.py` — Semantic search interface
- `rag/ingest.py` — Document ingestion pipeline
- `rag/sources/mitre_attack.py` — ATT&CK STIX ingestion
- `rag/sources/atomic_red.py` — Atomic Red Team YAML
- `rag/sources/hacktricks.py` — HackTricks markdown
- `rag/sources/payloads.py` — PayloadsAllTheThings
- `rag/sources/lolbas.py` — LOLBAS + GTFOBins YAML

**Triggers:** Intelligence returns nothing, agent fails 3+ attempts, Director requests pivot

---

### Epic 7: Agent Framework & Stigmergic Coordination
**User Outcome:** 10,000+ LLM-powered agents coordinate via P2P stigmergic signals with provable emergence (>20% novel attack chains).

**FRs:** FR2, FR4, FR6, FR62
**NFRs:** NFR1, NFR6-NFR8, NFR35-NFR37
**Errors:** ERR5

**Components:**
- `agents/base.py` — StigmergicAgent base class (LLM-powered, self-throttling)
- `agents/recon.py` — ReconAgent
- `agents/exploit.py` — ExploitAgent
- `agents/postex.py` — PostExAgent
- `orchestration/router.py` — SwarmRouter wrapper
- `orchestration/spawner.py` — Dynamic agent scaling (10K ceiling, attack surface based)
- `orchestration/emergence/tracker.py` — decision_context tracking
- `orchestration/emergence/validator.py` — Isolated vs stigmergic comparison
- `orchestration/emergence/metrics.py` — Emergence score calculation

**HARD GATE:** NFR35-37 emergence validation MUST pass (>20% novel chains, 3+ hop depth, 100% decision_context).

---

### Epic 8: Director Ensemble & Strategy Synthesis
**User Outcome:** Three LLMs (DeepSeek, Kimi K2, MiniMax) synthesize attack strategies with cognitive diversity and automatic re-planning.

**FRs:** FR1, FR3, FR5
**NFRs:** NFR29

**Components:**
- `agents/director.py` — DirectorEnsemble (extends Swarms MixtureOfAgents)
- `llm/ensemble.py` — 3-model synthesis (no voting, aggregation only)
- `orchestration/aggregator.py` — Batch findings for Director re-plan
- `orchestration/replan_triggers.py` — Timer (5min), critical finding, phase complete, objective met, operator override
- MiniMax M2 interleaved thinking (`<think>` tag handling)

---

### Epic 9: War Room TUI - Core
**User Outcome:** Operator can monitor swarm via Hive Matrix, view real-time findings, and navigate between screens.

**FRs:** FR7-FR9, FR11, FR47
**NFRs:** NFR4

**Components:**
- `tui/app.py` — Main TUI application (Textual)
- `tui/screens/war_room.py` — Three-pane layout
- `tui/widgets/agent_list.py` — Virtualized DataTable (10K+)
- `tui/widgets/finding_stream.py` — Real-time finding display
- `tui/widgets/hive_matrix.py` — Agent grid with status colors, anomaly bubbling, filter bar
- F-key navigation (F1-F6)
- TCSS theming ("Command & Control" dark aesthetic)
- Responsive breakpoints (80x24 min, 120x40 optimal)

---

### Epic 10: War Room TUI - Authorization & Control
**User Outcome:** Operator can respond to authorization requests, trigger kill switch, pause/resume engagements, and adjust scope at runtime.

**FRs:** FR13-FR16, FR17 (UI), FR18 (UI), FR19, FR22, FR23
**NFRs:** NFR5

**Components:**
- `tui/screens/authorization.py` — Authorization modal screen
- `tui/widgets/authorization_modal.py` — Y/N/M/S with swarm state snapshot, auth batching, timeout
- `tui/widgets/situational_alert.py` — Interruptive modal for unexpected discoveries
- `tui/widgets/sticky_kill_button.py` — Always-visible kill switch
- `core/alerts.py` — Situational awareness alert triggering
- Kill switch UI (ESC key + button)
- Pause/resume controls (F5/F6)
- Live scope modification with confirmation modal

---

### Epic 11: War Room TUI - Data & Strategy
**User Outcome:** Operator can view Director Ensemble strategies, access exfiltrated data browser, manage RAG updates, and monitor drop box status.

**FRs:** FR10, FR12, FR42, FR45, FR85

**Components:**
- `tui/widgets/strategy_stream.py` — Director Ensemble + stigmergic activity display
- `tui/screens/data_browser.py` — Exfiltrated data access menu
- `tui/widgets/rag_manager.py` — Update RAG button, ingestion status, corpus stats
- `tui/widgets/heartbeat_indicator.py` — C2 status (● healthy / ◐ degraded / ○ critical)
- `tui/widgets/timeline_scrubber.py` — Engagement history review
- Catch-up Mode for missed events during disconnect

---

### Epic 12: Drop Box & C2 Operations
**User Outcome:** Operator can deploy cross-platform drop boxes, establish mTLS C2 channels, and enable WiFi pivot capabilities.

**FRs:** FR24-FR30
**NFRs:** NFR11, NFR17
**Errors:** ERR4

**Components:**
- `c2/server.py` — mTLS WebSocket server (port 8444)
- `c2/protocol.py` — C2 message protocol (command/result/heartbeat)
- `c2/cert_manager.py` — Certificate generation, rotation (24h validity), pinning
- `dropbox/` (Go module):
  - `main.go` — Entry point
  - `c2/` — mTLS WebSocket client
  - `wifi/` — WiFi toolkit wrapper (aircrack-ng, wifite, kismet)
  - Cross-compile for Android, Windows, macOS, Linux (Tier 1), iOS (Tier 2)
- `tui/screens/dropbox.py` — NL setup wizard, pre-flight display, abort/wipe
- Pre-flight protocol: PING → EXEC_TEST → STREAM_TEST → NET_ENUM → READY
- Heartbeat monitoring (5s interval, 30s reconnect timeout)

---

### Epic 13: Evidence, Reporting & Audit
**User Outcome:** Operator can capture evidence, generate cryptographic proofs, export reports in multiple formats, and maintain tamper-evident audit trail.

**FRs:** FR36, FR38-FR41, FR43, FR44, FR50-FR54
**NFRs:** NFR15, NFR16

**Components:**
- `storage/evidence.py` — Evidence files + SHA-256 manifest
- `storage/audit.py` — Append-only audit log (Redis Streams consumer group)
- `storage/checkpoint.py` — SQLite checkpoints (WAL mode, async write queue)
- `templates/report_md.jinja2` — Markdown report
- `templates/report_html.jinja2` — HTML report with embedded screenshots
- `templates/sarif.jinja2` — SARIF format (GitHub/Azure DevOps)
- `templates/stix.jinja2` — STIX/TAXII format
- CSV/Excel export
- Pre-engagement liability waiver flow
- Timestamp integrity (NTP sync, crypto signatures)

**Note:** FR37 (video recording) deferred to v2.1.

---

### Epic 14: External API & Advanced Governance
**User Outcome:** External systems can integrate via REST/WebSocket API; advanced authorization governance with deputy operator and auto-pause.

**FRs:** FR48, FR49, FR63, FR64

**Components:**
- `api/server.py` — FastAPI application (port 8443)
- `api/routes/engagements.py` — CRUD + start/stop
- `api/routes/findings.py` — Query findings
- `api/routes/health.py` — Health check endpoint
- `api/auth.py` — Token-based authentication
- `api/schemas.py` — Pydantic request/response models
- Rate limiting
- Deputy Operator role support
- Auto-pause after 24h pending authorization

---

### Epic 15: End-to-End Integration & Validation
**User Outcome:** Complete engagement workflow validated end-to-end; all hard gates pass; system ready to ship.

**FRs:** All (validation)
**NFRs:** NFR3, NFR10, NFR19-NFR23, NFR35-NFR37

**Scope:**
- Full engagement E2E test in cyber range (complete kill chain)
- 100-agent scale test (CI gate)
- 10K agent stress test (ceiling discovery, degradation curve)
- Kill switch <1s validation under load
- Emergence >20% validation (stigmergic vs isolated)
- Causal chain 3+ hop validation
- 100% decision_context validation
- v1 baseline comparison (NFR3: 10x faster) — requires v1 benchmark data
- All safety tests passing
- 100% unit + integration coverage gates
- TUI <100ms responsiveness validation
- Pause/resume <1s validation
- Attach <2s validation
- Multi-engagement isolation test

---

## Epic Dependency Graph

```
Epic 0 (Testing Infrastructure)
    │
    ▼
Epic 1 (Core Framework & Safety)
    │
    ▼
Epic 2 (Daemon & Session Management)
    │
    ▼
Epic 3 (Communication Infrastructure) ◄── Redis, LLM Gateway
    │
    ├──────────────┬──────────────┐
    ▼              ▼              ▼
Epic 4         Epic 5         Epic 6
(Tools)    (Intelligence)     (RAG)
    │              │              │
    └──────────────┴──────────────┘
                   │
                   ▼
Epic 7 (Agent Framework & Stigmergic) ◄── HARD GATE: Emergence
    │
    ▼
Epic 8 (Director Ensemble)
    │
    ├──────────────┬──────────────┐
    ▼              ▼              ▼
Epic 9         Epic 10        Epic 11
(TUI Core)   (TUI Auth)    (TUI Data)
    │              │              │
    └──────────────┴──────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
Epic 12       Epic 13        Epic 14
(Drop Box)  (Evidence)       (API)
    │              │              │
    └──────────────┴──────────────┘
                   │
                   ▼
Epic 15 (E2E Integration & Validation) ◄── ALL HARD GATES
```

---

## Summary

| Epic | Title | FRs | Stories (Est.) |
|------|-------|-----|----------------|
| 0 | Testing & CI Infrastructure | - | 5-7 |
| 1 | Core Framework & Safety | 4 | 8-10 |
| 2 | Daemon & Session Management | 8 | 10-12 |
| 3 | Communication Infrastructure | 2 | 8-10 |
| 4 | Tool Execution Layer | 5 | 8-10 |
| 5 | Vulnerability Intelligence | 11 | 10-12 |
| 6 | RAG Escalation Layer | 9 | 8-10 |
| 7 | Agent Framework & Stigmergic | 4 | 12-15 |
| 8 | Director Ensemble | 3 | 6-8 |
| 9 | War Room TUI - Core | 5 | 10-12 |
| 10 | War Room TUI - Auth & Control | 7 | 9 |
| 11 | War Room TUI - Data & Strategy | 5 | 6-8 |
| 12 | Drop Box & C2 | 7 | 10-12 |
| 13 | Evidence, Reporting & Audit | 11 | 10-12 |
| 14 | External API & Governance | 4 | 11 |
| 15 | E2E Integration & Validation | All | 8-10 |

**Total: 16 Epics, 85 FRs, 168 Stories**

---

## Epic 0: Testing & CI Infrastructure

**User Outcome:** Development team has production-grade testing infrastructure enabling TDD from day one.

**FRs Covered:** (Infrastructure - enables all FRs)
**NFRs Covered:** NFR19, NFR20, NFR21, NFR22, NFR23, NFR24

---

### Story 0.1: pytest Core Configuration

As a **developer**,
I want **pytest and pytest-asyncio configured with proper project structure**,
So that **I can write and run async tests from day one**.

**Acceptance Criteria:**

- **Given** a fresh clone of the repository
- **When** I run `pytest`
- **Then** pytest discovers tests in `tests/` directory
- **And** pytest-asyncio handles async test functions automatically
- **And** pytest.ini or pyproject.toml contains proper configuration
- **And** conftest.py exists with basic shared fixtures

**Technical Notes:**
- Python 3.11+ compatibility
- asyncio_mode = "auto" for pytest-asyncio
- Test discovery pattern: `test_*.py`

---

### Story 0.2: Test Directory Structure & Fixtures

As a **developer**,
I want **organized test directories with shared fixtures**,
So that **tests are consistent and reusable across the codebase**.

**Acceptance Criteria:**

- **Given** Story 0.1 is complete
- **When** I examine the test directory structure
- **Then** I find `tests/unit/`, `tests/integration/`, `tests/safety/`, `tests/emergence/`, `tests/e2e/`, `tests/chaos/`, `tests/load/`
- **And** `tests/fixtures/` contains sample data directories (engagements/, findings/, scope/)
- **And** `tests/conftest.py` provides shared fixtures for all test types
- **And** pytest markers are defined: `@pytest.mark.integration`, `@pytest.mark.safety`, `@pytest.mark.emergence`, `@pytest.mark.e2e`, `@pytest.mark.chaos`, `@pytest.mark.load`
- **And** `pyproject.toml` includes `swarms>=8.0.0` dependency ([kyegomez/swarms](https://github.com/kyegomez/swarms))

**Technical Notes:**
- **Framework:** `pip install swarms>=8.0.0` — this is kyegomez/swarms, NOT OpenAI's experimental "Swarm"
- Verify with: `python -c "import swarms; print(swarms.__version__)"`

---

### Story 0.3: testcontainers Kali Integration

As a **developer**,
I want **testcontainers-python configured to spin up real Kali containers**,
So that **integration tests run against actual Kali tools without mocks**.

**Acceptance Criteria:**

- **Given** Story 0.2 is complete
- **When** I run an integration test that requires Kali
- **Then** testcontainers automatically pulls and starts `kalilinux/kali-linux-docker`
- **And** the container is accessible from the test
- **And** the container is cleaned up after the test completes
- **And** a `kali_container` fixture is available in conftest.py
- **And** container startup time is logged for performance tracking

**Technical Notes:**
- Use `testcontainers-python` library
- Container image: `kalilinux/kali-linux-docker` or equivalent
- Network isolation per test

---

### Story 0.4: Coverage Gates Configuration

As a **developer**,
I want **100% coverage gates enforced in CI**,
So that **no code ships without complete test coverage (NFR19, NFR20)**.

**Acceptance Criteria:**

- **Given** Story 0.1 is complete
- **When** I run `pytest --cov`
- **Then** coverage report is generated for `src/cyberred/`
- **And** coverage threshold is set to 100% for unit tests
- **And** coverage threshold is set to 100% for integration tests
- **And** CI fails if coverage drops below threshold
- **And** coverage report excludes test files and `__pycache__`

**Technical Notes:**
- Use pytest-cov
- Configure in pyproject.toml
- Separate coverage targets for unit vs integration

---

### Story 0.5: GitHub Actions CI Pipeline

As a **developer**,
I want **self-hosted GitHub Actions with Docker support**,
So that **CI can run real Kali containers for integration tests**.

**Acceptance Criteria:**

- **Given** Stories 0.1-0.4 are complete
- **When** I push code to the repository
- **Then** GitHub Actions workflow triggers on `.github/workflows/ci.yml`
- **And** workflow runs on self-hosted runner with Docker
- **And** unit tests run first (fast feedback)
- **And** integration tests run with testcontainers
- **And** safety tests run (marked as required)
- **And** coverage gates are enforced
- **And** workflow fails if any test fails or coverage drops

**Technical Notes:**
- Self-hosted runner required for Docker-in-Docker
- Parallel job execution where possible
- Cache pip dependencies

---

### Story 0.6: Cyber Range Test Environment

As a **developer**,
I want **a standardized cyber-range docker-compose with vulnerable targets**,
So that **E2E and emergence tests have reproducible targets to attack**.

**Acceptance Criteria:**

- **Given** Docker is available
- **When** I run `docker-compose -f cyber-range/docker-compose.yml up`
- **Then** vulnerable web application starts (DVWA-like)
- **And** vulnerable network services start (SSH, SMB, FTP)
- **And** `cyber-range/expected-findings.json` documents all known vulnerabilities
- **And** `cyber-range/emergence-baseline.json` provides baseline for emergence comparison
- **And** targets are isolated in a dedicated Docker network

**Technical Notes:**
- Use existing vulnerable images (DVWA, Metasploitable, etc.)
- Document all expected vulnerabilities for validation
- Network: `cyber-range-net`

---

### Story 0.7: Safety & Emergence Test Framework

As a **developer**,
I want **dedicated test structures for safety and emergence validation**,
So that **hard-gate tests (NFR35-37) have proper framework from day one**.

**Acceptance Criteria:**

- **Given** Story 0.2 is complete
- **When** I examine `tests/safety/` and `tests/emergence/`
- **Then** `tests/safety/` contains placeholder files for scope, kill switch, auth tests
- **And** `tests/emergence/` contains placeholder files for emergence score, causal chains, decision_context
- **And** safety tests are marked with `@pytest.mark.safety` (always run)
- **And** emergence tests are marked with `@pytest.mark.emergence`
- **And** README.md in each directory explains the test category purpose

**Technical Notes:**
- Placeholder tests can be `pass` or `pytest.skip("Not implemented")`
- Structure enables TDD for subsequent epics

---

## Epic 1: Core Framework & Safety Foundation

**User Outcome:** Operator has safety-critical controls (kill switch, scope validation) and core infrastructure that enable all future capabilities.

**FRs Covered:** FR17, FR18, FR20, FR21
**NFRs Covered:** NFR2, NFR14-NFR18, NFR26
**Errors Handled:** ERR6

---

### Story 1.1: Exception Hierarchy

As a **developer**,
I want **a structured exception hierarchy for Cyber-Red**,
So that **error handling is consistent and meaningful across the codebase**.

**Acceptance Criteria:**

- **Given** the `src/cyberred/core/` directory exists
- **When** I import from `core.exceptions`
- **Then** `CyberRedError` base exception is available
- **And** `ScopeViolationError` extends CyberRedError
- **And** `KillSwitchTriggered` extends CyberRedError
- **And** `ConfigurationError` extends CyberRedError
- **And** `CheckpointIntegrityError` extends CyberRedError
- **And** all exceptions include meaningful default messages
- **And** unit tests verify exception hierarchy

**Technical Notes:**
- Follow architecture pattern (lines 662-679)
- Exceptions are system-critical, not expected tool failures

---

### Story 1.2: Core Data Models

As a **developer**,
I want **standardized dataclasses for Finding, AgentAction, and ToolResult**,
So that **all components use consistent data structures**.

**Acceptance Criteria:**

- **Given** Story 1.1 is complete
- **When** I import from `core.models`
- **Then** `Finding` dataclass has 10 required fields (id, type, severity, target, evidence, agent_id, timestamp, tool, topic, signature)
- **And** `AgentAction` dataclass has 7 fields (id, agent_id, action_type, target, timestamp, decision_context, result_finding_id)
- **And** `ToolResult` dataclass has 5 fields (success, stdout, stderr, exit_code, duration_ms)
- **And** all models are JSON-serializable
- **And** unit tests validate serialization/deserialization

**Technical Notes:**
- Use Python dataclasses with `@dataclass`
- `decision_context` is List[str] for stigmergic traceability (NFR37)
- Follow architecture Finding format (lines 610-650)

---

### Story 1.3: YAML Configuration Loader

As an **operator**,
I want **layered YAML configuration loading**,
So that **I can configure system, engagement, and runtime settings separately (FR46)**.

**Acceptance Criteria:**

- **Given** `~/.cyber-red/config.yaml` exists
- **When** I call `config.load()`
- **Then** system config is loaded from `~/.cyber-red/config.yaml`
- **And** engagement config can override system config
- **And** runtime config can override engagement config
- **And** secrets are loaded from `.env` via python-dotenv
- **And** `ConfigurationError` is raised for invalid YAML
- **And** missing optional keys use sensible defaults
- **And** unit tests cover all config layers

**Technical Notes:**
- Use PyYAML + python-dotenv
- Config structure per architecture (lines 497-522)
- No hardcoded provider configs (NFR26)

---

### Story 1.4: Protocol Abstractions (ABCs)

As a **developer**,
I want **abstract base classes for Agent, Storage, and LLMProvider**,
So that **components can be swapped via dependency injection**.

**Acceptance Criteria:**

- **Given** Story 1.1 is complete
- **When** I import from `protocols/`
- **Then** `AgentProtocol` ABC defines agent interface methods
- **And** `StorageProtocol` ABC defines storage interface methods
- **And** `LLMProviderProtocol` ABC defines LLM provider interface
- **And** all protocols use `typing.Protocol` or `abc.ABC`
- **And** unit tests verify protocol compliance checking

**Technical Notes:**
- Located in `src/cyberred/protocols/`
- Enable type checking with mypy
- Follow architecture boundary rules (lines 983-994)

---

### Story 1.5: NTP Time Synchronization

As a **developer**,
I want **NTP-synchronized timestamps with drift detection**,
So that **audit trails have cryptographically verifiable timestamps (NFR16)**.

**Acceptance Criteria:**

- **Given** NTP servers are reachable
- **When** I call `time.now()`
- **Then** timestamp is NTP-synchronized (not local system time)
- **And** timestamps are ISO 8601 formatted
- **And** drift detection warns if local clock diverges >1s
- **And** `time.sign_timestamp()` produces cryptographic signature
- **And** integration test verifies NTP sync

**Technical Notes:**
- Use ntplib or similar
- Fallback to local time with warning if NTP unreachable
- Located in `core/time.py`

---

### Story 1.6: Keystore (PBKDF2 Key Derivation)

As an **operator**,
I want **secure key derivation for encryption keys**,
So that **data at rest is protected with AES-256 (NFR14)**.

**Acceptance Criteria:**

- **Given** a master password is provided
- **When** I call `keystore.derive_key(password, salt)`
- **Then** AES-256 compatible key is derived using PBKDF2
- **And** iteration count is configurable (default: 100,000)
- **And** keys are never stored in plaintext
- **And** `keystore.encrypt()` and `keystore.decrypt()` use derived keys
- **And** unit tests verify encryption/decryption round-trip

**Technical Notes:**
- Use `cryptography` library
- PBKDF2-HMAC-SHA256
- Located in `core/keystore.py`

---

### Story 1.7: CA Key Storage

As an **operator**,
I want **secure CA key storage for mTLS certificate generation**,
So that **C2 channels are secured with proper certificate authority (NFR17)**.

**Acceptance Criteria:**

- **Given** keystore (Story 1.6) is available
- **When** I initialize CA store
- **Then** CA private key is encrypted at rest with keystore
- **And** CA certificate is stored alongside (can be plaintext)
- **And** `ca_store.generate_cert()` creates signed certificates
- **And** certificates include proper extensions for mTLS
- **And** unit tests verify certificate chain validation

**Technical Notes:**
- Use `cryptography` library (x509)
- Located in `core/ca_store.py`
- Supports HSM path for future (not implemented in v2.0)

---

### Story 1.8: Scope Validator (Hard-Gate)

As an **operator**,
I want **deterministic scope validation that blocks out-of-scope actions**,
So that **the system never attacks unauthorized targets (FR20, FR21)**.

**Acceptance Criteria:**

- **Given** a scope configuration with allowed targets/ports/protocols
- **When** any tool attempts execution
- **Then** `scope.validate(command, target)` is called BEFORE execution
- **And** validation is deterministic (code, not AI)
- **And** out-of-scope attempts raise `ScopeViolationError`
- **And** ALL scope checks are logged to audit trail
- **And** scope supports CIDR ranges, hostnames, ports, protocols
- **And** scope validation is fail-closed (deny on error)
- **And** safety tests verify scope blocking (ERR6)

**Technical Notes:**
- Located in `tools/scope.py`
- NFKC Unicode normalization before validation (prevent bypass)
- This is SAFETY-CRITICAL — extensive test coverage required

---

### Story 1.9: Kill Switch Core (Tri-Path)

As an **operator**,
I want **a kill switch that halts all operations in <1s under 10K agent load**,
So that **I maintain absolute control over the engagement (FR17, FR18, NFR2)**.

**Acceptance Criteria:**

- **Given** an engagement is running with agents active
- **When** `killswitch.trigger()` is called
- **Then** Path 1: Redis pub/sub `control:kill` is published
- **And** Path 2: SIGTERM cascade via process group is sent
- **And** Path 3: Docker API `container.stop()` is called (500ms timeout then kill)
- **And** atomic "engagement frozen" flag is set before any path executes
- **And** all three paths execute in parallel
- **And** kill switch completes in <1s (hard requirement)
- **And** safety tests verify <1s under simulated load

**Technical Notes:**
- Located in `core/killswitch.py`
- Tri-path per architecture (lines 91-92)
- SAFETY-CRITICAL — must work even if Redis is offline

---

### Story 1.10: Kill Switch Resilience Testing

As a **developer**,
I want **comprehensive kill switch safety tests**,
So that **we can verify <1s response under all failure modes**.

**Acceptance Criteria:**

- **Given** Story 1.9 is complete
- **When** safety tests run
- **Then** kill switch triggers in <1s with Redis available
- **And** kill switch triggers in <1s with Redis unavailable (fallback paths)
- **And** kill switch triggers in <1s under simulated 100-agent load
- **And** kill switch triggers in <1s under simulated container load
- **And** all safety tests are in `tests/safety/test_killswitch.py`
- **And** tests are marked `@pytest.mark.safety`

**Technical Notes:**
- Use pytest timing assertions
- Mock agent/container counts for load simulation
- This validates NFR2 hard gate

---

## Epic 2: Daemon & Session Management

**User Outcome:** Operator can start Cyber-Red daemon, manage multiple engagements, attach/detach TUI without losing state.

**FRs Covered:** FR46, FR55-FR61
**NFRs Covered:** NFR30-NFR34

---

### Story 2.1: CLI Entry Point & Command Structure

As an **operator**,
I want **a `cyber-red` CLI command with subcommands**,
So that **I can control the daemon and engagements from the terminal**.

**Acceptance Criteria:**

- **Given** Cyber-Red is installed
- **When** I run `cyber-red --help`
- **Then** I see available subcommands: `daemon`, `sessions`, `attach`, `detach`, `new`, `pause`, `resume`, `stop`
- **And** `cyber-red daemon start` starts the daemon
- **And** `cyber-red daemon stop` stops the daemon gracefully
- **And** `cyber-red daemon status` shows daemon state
- **And** CLI uses Click or Typer for argument parsing
- **And** unit tests verify command structure

**Technical Notes:**
- Located in `src/cyberred/cli.py`
- Use Click or Typer library
- Commands delegate to daemon via IPC

---

### Story 2.2: IPC Protocol Definition

As a **developer**,
I want **a well-defined IPC protocol for TUI-daemon communication**,
So that **all clients communicate consistently with the daemon**.

**Acceptance Criteria:**

- **Given** Story 2.1 is complete
- **When** I import from `daemon.ipc`
- **Then** `IPCRequest` and `IPCResponse` dataclasses are available
- **And** commands are defined: `sessions.list`, `engagement.start`, `engagement.attach`, `engagement.detach`, `engagement.pause`, `engagement.resume`, `engagement.stop`
- **And** responses include status, data, and error fields
- **And** protocol uses JSON serialization over Unix socket
- **And** unit tests verify protocol serialization

**Technical Notes:**
- Follow architecture IPC protocol (lines 419-427)
- Message format: `{command, params, request_id}`
- Response format: `{status, data, error, request_id}`

---

### Story 2.3: Unix Socket Server

As an **operator**,
I want **the daemon to listen on a Unix socket**,
So that **TUI clients can connect locally without network exposure**.

**Acceptance Criteria:**

- **Given** Story 2.2 is complete
- **When** daemon starts
- **Then** Unix socket is created at `~/.cyber-red/daemon.sock`
- **And** socket permissions are restricted (owner only)
- **And** server accepts multiple concurrent client connections
- **And** server handles client disconnection gracefully
- **And** server responds to IPC protocol commands
- **And** integration tests verify socket communication

**Technical Notes:**
- Use asyncio for concurrent connections
- Located in `daemon/server.py`
- Clean up socket file on shutdown

---

### Story 2.4: Engagement State Machine

As a **developer**,
I want **a strict engagement state machine**,
So that **engagements follow predictable lifecycle transitions (FR55-FR61)**.

**Acceptance Criteria:**

- **Given** Story 2.2 is complete
- **When** an engagement is created
- **Then** it starts in `INITIALIZING` state
- **And** valid transitions are: INITIALIZING→RUNNING, RUNNING↔PAUSED, RUNNING→STOPPED, PAUSED→STOPPED, STOPPED→COMPLETED
- **And** invalid transitions raise `InvalidStateTransition` error
- **And** state changes emit events for subscribers
- **And** unit tests verify all valid/invalid transitions

**Technical Notes:**
- Located in `daemon/state_machine.py`
- States: INITIALIZING, RUNNING, PAUSED, STOPPED, COMPLETED
- Per architecture state machine (lines 407-416)

---

### Story 2.5: Session Manager (Multi-Engagement)

As an **operator**,
I want **to run multiple concurrent engagements**,
So that **I can manage several targets simultaneously (NFR34)**.

**Acceptance Criteria:**

- **Given** Stories 2.3 and 2.4 are complete
- **When** I start multiple engagements
- **Then** session manager tracks all engagements by ID
- **And** `sessions.list` returns all engagements with state, agent count, finding count
- **And** engagements are isolated (no cross-engagement state leakage)
- **And** resource limits prevent over-allocation
- **And** integration tests verify multi-engagement isolation

**Technical Notes:**
- Located in `daemon/session_manager.py`
- Target: 5+ concurrent engagements (NFR34)
- Engagement ID format: `{name}-{timestamp}`

---

### Story 2.6: Engagement Start & Pre-Flight Checks

As an **operator**,
I want **pre-flight validation before engagement starts**,
So that **I don't start an engagement with missing dependencies**.

**Acceptance Criteria:**

- **Given** Story 2.5 is complete
- **When** I run `cyber-red new --config engagement.yaml`
- **Then** pre-flight checks execute in sequence:
  - REDIS_CHECK: Verify Redis Sentinel reachable
  - LLM_CHECK: Verify at least 1 Director model responds
  - SCOPE_CHECK: Validate scope file exists and parses
  - DISK_CHECK: Verify >10% free disk space
  - MEMORY_CHECK: Verify sufficient RAM for target agent count
  - CERT_CHECK: Verify mTLS certs valid (>24h remaining)
- **And** P0 check failure blocks engagement start
- **And** P1 check failure shows warning, requires acknowledgment
- **And** integration tests verify pre-flight sequence

**Technical Notes:**
- Pre-flight per architecture (lines 437-453)
- Each check returns: PASS, WARN, FAIL
- Located in `daemon/preflight.py`

---

### Story 2.7: Pause & Resume (Hot State)

As an **operator**,
I want **instant pause/resume without checkpoint reload**,
So that **I can quickly halt and continue engagements (NFR31)**.

**Acceptance Criteria:**

- **Given** an engagement is RUNNING
- **When** I run `cyber-red pause {id}`
- **Then** engagement transitions to PAUSED in <1s
- **And** agent state is preserved in memory (hot state)
- **And** no checkpoint file is written on pause
- **When** I run `cyber-red resume {id}`
- **Then** engagement transitions to RUNNING in <1s
- **And** agents resume from memory state immediately
- **And** safety tests verify <1s pause/resume latency

**Technical Notes:**
- Hot state = RAM, no disk I/O
- NFR31: <1s pause-to-resume latency
- Contrast with STOPPED which uses cold checkpoint

---

### Story 2.8: Stop & Checkpoint (Cold State)

As an **operator**,
I want **to stop an engagement with checkpoint for later resume**,
So that **I can recover from system restarts (FR54, NFR33)**.

**Acceptance Criteria:**

- **Given** an engagement is RUNNING or PAUSED
- **When** I run `cyber-red stop {id}`
- **Then** engagement transitions to STOPPED
- **And** full state is written to SQLite checkpoint file
- **And** checkpoint includes agent states, findings, scope hash
- **And** checkpoint is signed with SHA-256 for integrity
- **When** daemon restarts
- **Then** stopped engagements are listed and resumable
- **And** integration tests verify checkpoint/restore cycle

**Technical Notes:**
- Checkpoint file: `~/.cyber-red/engagements/{id}/checkpoint.sqlite`
- SQLite WAL mode for concurrent reads
- Verify scope hash on restore (security)

---

### Story 2.9: Attach & Detach (TUI Client)

As an **operator**,
I want **to attach/detach TUI from running engagements**,
So that **I can disconnect SSH without stopping the engagement (FR58, FR59)**.

**Acceptance Criteria:**

- **Given** an engagement is RUNNING
- **When** I run `cyber-red attach {id}`
- **Then** TUI connects to daemon via Unix socket
- **And** TUI receives real-time state stream
- **And** attach completes in <2s (NFR32)
- **When** I press Ctrl+D or run `detach`
- **Then** TUI disconnects cleanly
- **And** engagement continues running in daemon
- **And** safety tests verify SSH disconnect doesn't stop engagement

**Technical Notes:**
- Attach streams: agent status, findings, authorization requests
- Multiple TUI clients can attach to same engagement
- Per architecture daemon model (lines 369-405)

---

### Story 2.10: systemd Integration

As an **operator**,
I want **systemd service for daemon auto-start**,
So that **Cyber-Red starts on boot and restarts on failure**.

**Acceptance Criteria:**

- **Given** Cyber-Red is installed on a systemd Linux system
- **When** I run `systemctl enable cyber-red`
- **Then** daemon starts automatically on boot
- **And** daemon restarts automatically on failure
- **And** `systemctl status cyber-red` shows daemon state
- **And** `journalctl -u cyber-red` shows daemon logs
- **And** service runs as dedicated `cyberred` user (not root)

**Technical Notes:**
- Service file: `/etc/systemd/system/cyber-red.service`
- Per architecture systemd config (lines 471-485)
- Type=simple, Restart=on-failure

---

### Story 2.11: Daemon Graceful Shutdown

As an **operator**,
I want **graceful daemon shutdown that preserves all engagements**,
So that **no data is lost on daemon stop**.

**Acceptance Criteria:**

- **Given** daemon has active engagements
- **When** I run `cyber-red daemon stop` or `systemctl stop cyber-red`
- **Then** all RUNNING engagements are paused first
- **And** all PAUSED engagements are checkpointed to STOPPED
- **And** all TUI clients are notified and disconnected
- **And** Unix socket is cleaned up
- **And** daemon exits cleanly with code 0
- **And** integration tests verify graceful shutdown sequence

**Technical Notes:**
- Shutdown sequence: signal handlers → pause all → checkpoint all → cleanup
- Handle SIGTERM and SIGINT
- Maximum shutdown time: 30s before forced exit

---

### Story 2.12: Engagement Database Schema

As a **developer**,
I want **a defined SQLite schema for engagement data**,
So that **all components use consistent data structures**.

**Acceptance Criteria:**

- **Given** engagement is created
- **When** database is initialized
- **Then** schema includes tables: engagements, agents, findings, checkpoints, audit
- **And** foreign keys enforce referential integrity
- **And** indexes exist for: engagement_id, agent_id, timestamp
- **And** migrations framework supports schema evolution
- **And** unit tests verify schema creation

**Technical Notes:**
- Located in `storage/schema.py`
- Use Alembic for migrations
- SQLite WAL mode enabled by default

---

### Story 2.13: Configuration Hot Reload

As an **operator**,
I want **configuration changes to take effect without restart**,
So that **I can adjust settings during engagement (FR46)**.

**Acceptance Criteria:**

- **Given** engagement is running
- **When** I modify `config.yaml`
- **Then** daemon detects change within 5s
- **And** safe config values are reloaded (timeouts, thresholds)
- **And** unsafe values require restart (ports, credentials)
- **And** reload event is logged
- **And** integration tests verify hot reload

**Technical Notes:**
- Located in `core/config.py`
- Use inotify/watchdog for file change detection
- Per FR46: "Configuration hot reload"

---

## Epic 3: Communication Infrastructure

**User Outcome:** System has Redis connectivity, LLM gateway, and event bus for all inter-component communication.

**FRs Covered:** (Infrastructure for FR4, FR50)
**NFRs Covered:** NFR1, NFR28, NFR29
**Errors Handled:** ERR2, ERR3

---

### Story 3.1: Redis Sentinel Client

As a **developer**,
I want **a Redis Sentinel client with automatic failover**,
So that **the system maintains high availability for stigmergic coordination (NFR28)**.

**Acceptance Criteria:**

- **Given** Redis Sentinel cluster is running (3-node)
- **When** I create a `RedisClient` instance
- **Then** client connects to Sentinel and discovers master
- **And** client automatically fails over to new master on failure
- **And** connection pool is configurable (default: 10 connections)
- **And** client exposes `publish()`, `subscribe()`, and `xadd()` methods
- **And** integration tests verify failover behavior

**Technical Notes:**
- Use `redis-py` with Sentinel support
- Located in `storage/redis_client.py`
- Per architecture Redis HA (lines 81-84, 147-152)

---

### Story 3.2: Redis Reconnection Logic

As a **developer**,
I want **automatic Redis reconnection with local buffering**,
So that **temporary network issues don't lose messages (ERR3)**.

**Acceptance Criteria:**

- **Given** Story 3.1 is complete
- **When** Redis connection is lost
- **Then** messages are buffered locally for up to 10s
- **And** exponential backoff reconnection attempts (1s, 2s, 4s, 8s, 10s max)
- **And** buffered messages are sent on reconnection
- **And** `RedisConnectionLost` event is emitted for monitoring
- **And** integration tests simulate connection loss/recovery

**Technical Notes:**
- Local buffer: in-memory queue, max 1000 messages
- Per architecture degraded mode (lines 95)
- ERR3 error handling pattern

---

### Story 3.3: Event Bus (Pub/Sub)

As a **developer**,
I want **a Redis pub/sub wrapper for real-time stigmergic signals**,
So that **agents can coordinate via fire-and-forget messages (NFR1)**.

**Acceptance Criteria:**

- **Given** Stories 3.1 and 3.2 are complete
- **When** I call `events.publish(channel, message)`
- **Then** message is published to Redis pub/sub
- **And** message includes HMAC-SHA256 signature for integrity
- **And** subscribers receive messages in <1s (NFR1)
- **When** I call `events.subscribe(pattern)`
- **Then** callback is invoked for matching messages
- **And** signature is validated on receipt
- **And** integration tests verify pub/sub latency <1s

**Technical Notes:**
- Channel naming: `findings:{target_hash}:{type}`, `agents:{id}:status`, `control:kill`
- Per architecture event naming (lines 686-700)
- Located in `core/events.py`

---

### Story 3.4: Event Bus (Streams for Audit)

As a **developer**,
I want **Redis Streams for persistent audit events**,
So that **audit trail has at-least-once delivery guarantee**.

**Acceptance Criteria:**

- **Given** Story 3.3 is complete
- **When** I call `events.audit(event)`
- **Then** event is added to `audit:stream` Redis Stream
- **And** consumer group `audit-consumers` processes events
- **And** events are acknowledged after processing
- **And** unacknowledged events are redelivered
- **And** all messages include HMAC-SHA256 signature for integrity validation
- **And** invalid signatures are rejected and logged as security events
- **And** integration tests verify no message loss on consumer restart
- **And** integration tests verify HMAC validation rejects tampered messages

**Technical Notes:**
- Redis Streams for durability
- Consumer group per architecture (line 1079)
- Stream name: `audit:stream`
- HMAC key derived from engagement master key

---

### Story 3.5: LLM Provider Protocol

As a **developer**,
I want **an abstract LLM provider interface**,
So that **different LLM backends can be swapped without code changes**.

**Acceptance Criteria:**

- **Given** Epic 1.4 protocols are complete
- **When** I import from `llm.provider`
- **Then** `LLMProvider` protocol defines: `complete()`, `complete_async()`, `health_check()`
- **And** `LLMRequest` dataclass defines: prompt, model, temperature, max_tokens
- **And** `LLMResponse` dataclass defines: content, model, usage, latency_ms
- **And** unit tests verify protocol compliance

**Technical Notes:**
- Located in `llm/provider.py`
- Extends LLMProviderProtocol from `protocols/`
- Support both sync and async completion

---

### Story 3.6: NVIDIA NIM Provider

As a **developer**,
I want **an NVIDIA NIM LLM provider implementation**,
So that **agents can use NIM-hosted models for reasoning**.

**Acceptance Criteria:**

- **Given** Story 3.5 is complete
- **When** I create `NIMProvider` with API key
- **Then** provider connects to NVIDIA NIM API
- **And** `complete()` sends requests and returns responses
- **And** `health_check()` verifies API availability
- **And** provider handles rate limit responses gracefully
- **And** integration tests verify real NIM API calls

**Technical Notes:**
- Located in `llm/nim.py`
- API key from config/secrets
- Models: Nemotron family, DeepSeek, Qwen3-Coder

---

### Story 3.7: LLM Rate Limiter

As a **developer**,
I want **a global rate limiter for LLM requests**,
So that **the system respects API rate limits (30 RPM)**.

**Acceptance Criteria:**

- **Given** Story 3.5 is complete
- **When** requests exceed 30 RPM
- **Then** additional requests are queued
- **And** token bucket algorithm controls request flow
- **And** requests are released at sustainable rate
- **And** queue depth is exposed for monitoring
- **And** unit tests verify rate limiting behavior

**Technical Notes:**
- Located in `llm/rate_limiter.py`
- Token bucket: 30 tokens/minute, burst: 5
- Per architecture 30 RPM cap (line 131)

---

### Story 3.8: LLM Model Router

As a **developer**,
I want **automatic model selection based on task complexity**,
So that **simple tasks use fast models and complex tasks use powerful models**.

**Acceptance Criteria:**

- **Given** Stories 3.5 and 3.6 are complete
- **When** I call `router.select_model(task_complexity)`
- **Then** FAST tier returns Nemotron-3-Nano-30B for parsing
- **And** STANDARD tier returns Llama Nemotron Super 49B for reasoning
- **And** COMPLEX tier returns DeepSeek-R1 or Qwen3-Coder for exploit chaining
- **And** router respects model availability (skip unavailable)
- **And** unit tests verify tier selection logic

**Technical Notes:**
- Located in `llm/router.py`
- Tiers per architecture (lines 135-139)
- Fallback to available models if preferred unavailable

---

### Story 3.9: LLM Priority Queue

As a **developer**,
I want **Director requests prioritized over agent requests**,
So that **strategic re-planning is never starved by agent volume**.

**Acceptance Criteria:**

- **Given** Story 3.7 is complete
- **When** Director and agents submit concurrent requests
- **Then** Director requests are processed first (priority: 0)
- **And** Agent requests follow (priority: 1)
- **And** within same priority, FIFO ordering is maintained
- **And** queue depth per priority is exposed for monitoring
- **And** unit tests verify priority ordering

**Technical Notes:**
- Located in `llm/priority_queue.py`
- Use `asyncio.PriorityQueue`
- Prevents agent "flash crowd" from blocking Director

---

### Story 3.10: LLM Gateway (Singleton)

As a **developer**,
I want **a singleton LLM gateway that manages all requests**,
So that **rate limiting and routing are centralized**.

**Acceptance Criteria:**

- **Given** Stories 3.6, 3.7, 3.8, 3.9 are complete
- **When** any component needs LLM completion
- **Then** request goes through `LLMGateway.complete()`
- **And** gateway applies rate limiting
- **And** gateway routes to appropriate model
- **And** gateway respects priority queue
- **And** gateway handles provider timeout with retry (ERR2)
- **And** integration tests verify end-to-end gateway flow

**Technical Notes:**
- Located in `llm/gateway.py`
- Singleton pattern via module-level instance
- ERR2: 3x retry with exponential backoff

---

### Story 3.11: LLM Provider Timeout & Retry

As a **developer**,
I want **automatic retry for LLM provider timeouts**,
So that **transient failures don't crash agents (ERR2)**.

**Acceptance Criteria:**

- **Given** Story 3.10 is complete
- **When** LLM provider times out
- **Then** request is retried up to 3 times
- **And** exponential backoff: 1s, 2s, 4s
- **And** if all retries fail, graceful error is returned
- **And** circuit breaker excludes failing models temporarily (3 failures)
- **And** integration tests simulate timeout scenarios

**Technical Notes:**
- Per architecture ERR2 handling (lines 199)
- Circuit breaker: 3 failures → exclude for 60s
- Timeout: 100s per model, 180s aggregate for ensemble

---

## Epic 4: Tool Execution Layer

**User Outcome:** Agents can execute 600+ Kali tools in isolated containers with scope enforcement and structured output parsing.

**FRs Covered:** FR31, FR32, FR33, FR34, FR35
**NFRs Covered:** NFR24, NFR25
**Errors Handled:** ERR1

**Required Context for Agents:**
- `docs/best-practices/kali-containers.md` - Mandatory for all execution stories
- `docs/best-practices/async-patterns.md` - Mandatory for async implementations

---

### Story 4.1: Kali Container Pool (Mock Mode)

As a **developer**,
I want **a container pool that simulates Kali execution without real containers**,
So that **CI tests can run fast without Docker dependencies (NFR24)**.

**Acceptance Criteria:**

- **Given** the container pool is initialized with `mode="mock"`
- **When** I call `pool.acquire()`
- **Then** a mock container instance is returned immediately (no Docker)
- **And** the mock container has `execute(code)` method that returns predefined responses
- **And** mock responses are configurable via fixture files in `tests/fixtures/tool_outputs/`
- **And** `pool.release(container)` returns the mock to the pool
- **And** unit tests verify mock mode works without Docker installed

**Technical Notes:**
- Located in `tools/container_pool.py`
- Mock container reads from `tests/fixtures/tool_outputs/{tool}.txt`
- Supports configurable latency simulation for timing tests
- **Reference:** See `docs/best-practices/kali-containers.md` for mock vs real patterns

---

### Story 4.2: Kali Container Pool (Real Mode)

As a **developer**,
I want **a pool of real Kali Linux containers for tool execution**,
So that **integration tests and production run against actual tools (FR35)**.

**Acceptance Criteria:**

- **Given** Docker is available and `kalilinux/kali-linux-docker` image exists
- **When** I initialize `ContainerPool(mode="real", size=20)`
- **Then** pool pre-warms 20 Kali containers
- **And** `pool.acquire()` returns an available container (blocks if none available)
- **And** `pool.release(container)` returns container to pool for reuse
- **And** containers have network isolation per engagement
- **And** backpressure triggers at 80% queue depth (exposed via `pool.pressure` property)
- **And** integration tests verify real container execution

**Technical Notes:**
- Container image: `kalilinux/kali-linux-docker` or custom `kali-linux-everything`
- Pool size configurable: 20-50 containers
- Async queue for container requests
- **Reference:** See `docs/best-practices/kali-containers.md` and `docs/best-practices/async-patterns.md`

---

### Story 4.3: Kali Executor Core

As an **agent**,
I want **a `kali_execute()` tool that runs code in Kali containers**,
So that **I can execute any of 600+ Kali tools via code generation (FR31, FR32)**.

**Acceptance Criteria:**

- **Given** Story 4.2 is complete and container pool is available
- **When** I call `kali_execute("nmap -sV 192.168.1.1")`
- **Then** code executes in an isolated Kali container
- **And** execution has configurable timeout (default: 300s)
- **And** stdout, stderr, and exit_code are captured
- **And** result is returned as JSON with `success`, `stdout`, `stderr`, `exit_code`, `duration_ms`
- **And** container is released back to pool after execution
- **And** integration tests verify real nmap execution in cyber range

**Technical Notes:**
- Located in `tools/kali_executor.py`
- Swarms-compatible tool signature
- Scope validation integrated from Epic 1 Story 1.8
- **Reference:** Use `asyncio.TaskGroup` for concurrency (see `docs/best-practices/async-patterns.md`)

---

### Story 4.4: Tool Manifest Generation

As a **developer**,
I want **an auto-generated manifest of all available Kali tools**,
So that **agent prompts can reference available capabilities (FR31)**.

**Acceptance Criteria:**

- **Given** a Kali container is available
- **When** I run `scripts/generate_manifest.sh`
- **Then** script scans Kali for all installed tools
- **And** output is written to `tools/manifest.yaml`
- **And** manifest categorizes tools (reconnaissance, web_application, exploitation, post_exploitation, wireless)
- **And** manifest includes ~600 tools with name and category
- **And** manifest is used in agent system prompts for capability awareness
- **And** unit tests verify manifest parsing

**Technical Notes:**
- Script runs at Docker build time
- Manifest structure per PRD (lines 992-1009)
- Located in `tools/manifest.py` for loading

---

### Story 4.5: Output Processor Framework

As a **developer**,
I want **an output processor that routes tool output to appropriate parsers**,
So that **findings are extracted consistently across all tools (FR33)**.

**Acceptance Criteria:**

- **Given** Story 4.3 is complete
- **When** I call `output_processor.process(stdout, stderr, tool, exit_code)`
- **Then** processor detects tool from command or explicit parameter
- **And** processor routes to Tier 1 parser if available
- **And** processor falls back to Tier 2 (LLM summarization) if no parser
- **And** processor falls back to Tier 3 (raw truncated output) if LLM unavailable
- **And** result includes `findings: List[Finding]`, `summary: str`, `raw_truncated: str`
- **And** unit tests verify routing logic

**Technical Notes:**
- Located in `tools/output.py`
- Parser registry pattern for extensibility
- Tier hierarchy: Tier 1 (structured) > Tier 2 (LLM) > Tier 3 (raw)

---

### Story 4.6: Tier 1 Parser - nmap

As a **developer**,
I want **a structured parser for nmap output**,
So that **port scan findings are extracted reliably without LLM (FR33)**.

**Acceptance Criteria:**

- **Given** Story 4.5 is complete
- **When** nmap XML output (`-oX`) is passed to the parser
- **Then** parser extracts all open ports with service, version, state
- **And** parser extracts host status (up/down)
- **And** parser extracts OS detection results if present
- **And** parser extracts script output if NSE scripts were run
- **And** each finding has type="open_port" with port, protocol, service, version
- **And** integration tests verify against real nmap output from cyber range

**Technical Notes:**
- Located in `tools/parsers/nmap.py`
- Supports `-oX` (XML) and `-oG` (grepable) formats
- Uses `xml.etree.ElementTree` for parsing

---

### Story 4.7: Tier 1 Parser - nuclei

As a **developer**,
I want **a structured parser for nuclei output**,
So that **vulnerability findings are extracted with CVE and severity (FR33)**.

**Acceptance Criteria:**

- **Given** Story 4.5 is complete
- **When** nuclei JSON output (`-j`) is passed to the parser
- **Then** parser extracts all template matches
- **And** each finding includes: template_id, severity, CVE (if present), matched_url, extracted_data
- **And** findings are typed by nuclei template type (cve, exposure, misconfiguration)
- **And** CVSS score is included when available
- **And** integration tests verify against real nuclei output from cyber range

**Technical Notes:**
- Located in `tools/parsers/nuclei.py`
- Nuclei outputs one JSON object per line
- Map nuclei severity to Finding severity

---

### Story 4.8: Tier 1 Parser - sqlmap

As a **developer**,
I want **a structured parser for sqlmap output**,
So that **SQL injection findings include injection type and database details (FR33)**.

**Acceptance Criteria:**

- **Given** Story 4.5 is complete
- **When** sqlmap output is passed to the parser
- **Then** parser extracts vulnerable parameters
- **And** parser extracts injection types (boolean-blind, time-blind, UNION, stacked, error-based)
- **And** parser extracts database type and version when detected
- **And** parser extracts table/column enumeration results if performed
- **And** findings have type="sqli" with parameter, injection_type, dbms
- **And** integration tests verify against real sqlmap output from cyber range

**Technical Notes:**
- Located in `tools/parsers/sqlmap.py`
- Parse both stdout and `--output-dir` files
- Handle `--batch` mode output format

---

### Story 4.9: Tier 1 Parsers - Web Fuzzing (ffuf, nikto, hydra)

As a **developer**,
I want **structured parsers for ffuf, nikto, and hydra**,
So that **web fuzzing, scanning, and credential attacks have reliable parsing (FR33)**.

**Acceptance Criteria:**

- **Given** Story 4.5 is complete
- **When** ffuf JSON output is passed to ffuf parser
- **Then** parser extracts discovered paths with status code, size, words, lines
- **And** findings have type="directory" or type="file" with path, status_code

- **When** nikto output is passed to nikto parser
- **Then** parser extracts vulnerabilities with OSVDB/CVE references
- **And** findings have type="web_vuln" with description, reference

- **When** hydra output is passed to hydra parser
- **Then** parser extracts successful credential pairs
- **And** findings have type="credential" with username, password, service, host

- **And** integration tests verify all three parsers against cyber range

**Technical Notes:**
- Located in `tools/parsers/ffuf.py`, `nikto.py`, `hydra.py`
- ffuf: `-o output.json -of json`
- nikto: parse stdout (no structured format)
- hydra: parse stdout for `[service] host: ... login: ... password: ...`

---

### Story 4.10: Tier 1 Parsers - Remaining High-Frequency Tools (~24 parsers)

As a **developer**,
I want **structured parsers for all remaining high-frequency Kali tools**,
So that **the full ~30 Tier 1 parser requirement is met (FR33)**.

**Acceptance Criteria:**

- **Given** Stories 4.5-4.9 are complete (6 parsers: nmap, nuclei, sqlmap, ffuf, nikto, hydra)
- **When** output from any of the following tools is processed
- **Then** a dedicated Tier 1 parser extracts structured findings

**Reconnaissance Parsers (8 tools):**
| Tool | Finding Type | Key Fields |
|------|--------------|------------|
| `masscan` | open_port | port, protocol, ip, rate |
| `subfinder` | subdomain | hostname, source |
| `amass` | subdomain | hostname, source, dns_records |
| `whatweb` | technology | tech_name, version, url |
| `wafw00f` | waf_detected | waf_name, url |
| `dnsrecon` | dns_record | record_type, name, value |
| `theharvester` | email/subdomain | email, hostname, source |
| `gobuster` | directory/file | path, status_code, size |

**Exploitation Parsers (6 tools):**
| Tool | Finding Type | Key Fields |
|------|--------------|------------|
| `crackmapexec` | credential/share/vuln | target, username, password, share_name |
| `responder` | credential | protocol, client_ip, username, hash |
| `impacket-secretsdump` | credential | username, hash_type, hash |
| `impacket-psexec` | shell_access | target, username, success |
| `metasploit` (msfconsole) | session/vuln | session_id, exploit, target |
| `searchsploit` | exploit_ref | edb_id, title, path, platform |

**Post-Exploitation Parsers (6 tools):**
| Tool | Finding Type | Key Fields |
|------|--------------|------------|
| `mimikatz` | credential | username, domain, password, hash |
| `bloodhound` (SharpHound) | ad_object | object_type, name, path_to_da |
| `linpeas` | privesc_vector | vector_type, description, severity |
| `winpeas` | privesc_vector | vector_type, description, severity |
| `lazagne` | credential | application, username, password |
| `chisel` | tunnel | local_port, remote_target, status |

**Wireless Parsers (2 tools):**
| Tool | Finding Type | Key Fields |
|------|--------------|------------|
| `aircrack-ng` | wifi_crack | bssid, essid, key, packets |
| `wifite` | wifi_attack | bssid, essid, attack_type, result |

**Credential Parsers (2 tools):**
| Tool | Finding Type | Key Fields |
|------|--------------|------------|
| `john` | cracked_hash | hash, plaintext, format |
| `hashcat` | cracked_hash | hash, plaintext, mode, speed |

- **And** each parser is located in `tools/parsers/{tool}.py`
- **And** each parser registers with the output processor
- **And** integration tests verify each parser against sample output fixtures
- **And** total Tier 1 parser count is ~30 (6 from 4.6-4.9 + 24 from this story)

**Technical Notes:**
- Parsers should handle common output formats (JSON, XML, stdout patterns)
- Use regex for stdout parsing where no structured format exists
- All parsers follow same interface: `parse(stdout, stderr, exit_code) -> List[Finding]`
- Parsers may be implemented incrementally but story is complete when all 24 are done

---

### Story 4.11: LLM Summarization (Tier 2)

As a **developer**,
I want **LLM-based summarization for tools without dedicated parsers**,
So that **all tool output produces useful findings (FR33)**.

**Acceptance Criteria:**

- **Given** Stories 4.3 and 4.5 are complete and LLM Gateway (Epic 3) is available
- **When** tool output has no Tier 1 parser
- **Then** output is sent to LLM for summarization
- **And** LLM extracts key findings in structured format
- **And** LLM uses FAST tier model (Nemotron-3-Nano) for efficiency
- **And** output is truncated to 4000 chars before LLM call
- **And** summarization timeout is 30s
- **And** if LLM fails, falls back to Tier 3 (raw truncated)
- **And** integration tests verify LLM summarization with real NIM API

**Technical Notes:**
- Located in `tools/output.py`
- Prompt template extracts: findings, severity, recommendations
- Cache LLM responses for identical outputs (hash-based)

---

### Story 4.12: Parser Hot Reload

As an **operator**,
I want **to add or update parsers without restarting the system**,
So that **I can improve parsing mid-engagement (FR34, NFR25)**.

**Acceptance Criteria:**

- **Given** Stories 4.5-4.10 are complete
- **When** I modify a parser file in `tools/parsers/`
- **Then** system detects the change via file watcher
- **And** parser is reloaded without stopping engagement
- **And** new parser version is used for subsequent tool executions
- **When** I add a new parser file
- **Then** it is automatically registered in the parser registry
- **And** logs indicate "Parser {name} reloaded" or "Parser {name} registered"
- **And** integration tests verify hot reload without engagement interruption

**Technical Notes:**
- Use `watchdog` library for file monitoring
- Parser registry maintains module references
- Reload uses `importlib.reload()`

---

### Story 4.13: Tool Execution Error Handling

As an **agent**,
I want **graceful error handling when tool execution fails**,
So that **I can continue operating despite individual tool failures (ERR1)**.

**Acceptance Criteria:**

- **Given** Story 4.3 is complete
- **When** tool execution times out
- **Then** container is killed and released
- **And** result includes `success=False`, `error="TIMEOUT"`, `duration_ms`
- **When** tool returns non-zero exit code
- **Then** result includes `success=False`, `exit_code`, `stderr`
- **And** findings may still be extracted if partial output exists
- **When** container crashes or becomes unresponsive
- **Then** container is removed from pool and replaced
- **And** error is logged with full context
- **And** agent receives structured error result (not exception)
- **And** safety tests verify agents continue after tool failures

**Technical Notes:**
- Per PRD ERR1: "Log error, return structured result, agent continues"
- Never raise exceptions for tool failures (expected behavior)
- Container replacement maintains pool size

---

## Epic 5: Vulnerability Intelligence Layer

**User Outcome:** Agents can query real-time exploit intelligence from multiple sources when discovering targets, prioritizing CISA KEV and critical CVEs.

**FRs Covered:** FR65, FR66, FR67, FR68, FR69, FR70, FR71, FR72, FR73, FR74, FR75
**NFRs Covered:** NFR26 (cache efficiency)
**Errors Handled:** ERR3 (intelligence source timeout)

### Implementation Prerequisites (Pre-Configured)

> [!NOTE]
> The following prerequisites were configured during the Epic 4 Retrospective on 2026-01-07.

**Dependencies Added (`pyproject.toml`):**
```toml
nvdlib = ">=0.7.0"     # NVD API 2.0 client with built-in rate limiting
msgpack = ">=1.0.0"    # MessagePack for Metasploit RPC
# pymetasploit3, pyyaml already present
```

**Secrets Configured (`.env`):**
| Variable | Purpose | Notes |
|----------|---------|-------|
| `NVD_API_KEY` | NVD API authentication | 50 req/30s (vs 5 without key) |
| `MSF_RPC_PASSWORD` | Metasploit RPC auth | Default: `cyber_red_msf_password` |
| `MSF_RPC_HOST` | Metasploit RPC host | Default: `127.0.0.1` |
| `MSF_RPC_PORT` | Metasploit RPC port | Default: `55553` |

**Docker Service (`cyber-range/docker-compose.yml`):**
```bash
# Start Metasploit RPC for Story 5-6 integration tests
docker compose -f cyber-range/docker-compose.yml up -d metasploit
```

**Source Implementation Quick Reference:**
| Source | Library | Auth | Rate Limit | Story |
|--------|---------|------|------------|-------|
| CISA KEV | `requests` | None | None | 5-2 |
| NVD | `nvdlib` | API Key | 50 req/30s | 5-3 |
| ExploitDB | `subprocess` (searchsploit) | None | Local | 5-4 |
| Nuclei | `pyyaml` | None | Local | 5-5 |
| Metasploit | `pymetasploit3` | RPC Password | None | 5-6 |

---

### Story 5.1: Intelligence Source Base Interface

As a **developer**,
I want **a base interface for all intelligence sources**,
So that **sources can be queried uniformly and new sources added easily**.

**Acceptance Criteria:**

- **Given** I need to implement a new intelligence source
- **When** I extend `IntelligenceSource` base class
- **Then** I must implement `query(service: str, version: str) -> List[IntelResult]`
- **And** I must implement `health_check() -> bool`
- **And** base class provides `timeout` property (default 5s per FR74)
- **And** base class provides `priority` property for result ranking
- **And** `IntelResult` dataclass includes: source, cve_id, severity, exploit_available, exploit_path, confidence
- **And** unit tests verify interface contract

**Technical Notes:**
- Located in `intelligence/base.py`
- Abstract base class pattern
- Priority ranking: CISA_KEV=1, NVD_CRITICAL=2, NVD_HIGH=3, MSF=4, NUCLEI=5, EXPLOITDB=6

---

### Story 5.2: CISA KEV Source Integration

As an **agent**,
I want **to query CISA Known Exploited Vulnerabilities catalog**,
So that **I prioritize actively exploited vulnerabilities (FR66)**.

**Acceptance Criteria:**

- **Given** Story 5.1 is complete
- **When** I call `cisa_kev.query("Apache", "2.4.49")`
- **Then** source queries CISA KEV JSON feed
- **And** returns CVEs matching the service/version
- **And** results include: cve_id, vendor, product, vulnerability_name, date_added, due_date
- **And** results have priority=1 (highest)
- **And** source caches KEV catalog locally (updated daily)
- **And** integration tests verify against real CISA KEV feed

**Technical Notes:**
- Located in `intelligence/sources/cisa_kev.py`
- Feed URL: `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json`
- Cache entire catalog, query locally for speed
- Update check: daily or on startup
- **Pre-configured:** No auth required, use `requests` library (already in deps)

---

### Story 5.3: NVD API Source Integration

As an **agent**,
I want **to query the National Vulnerability Database**,
So that **I get comprehensive CVE data with CVSS scores (FR67)**.

**Acceptance Criteria:**

- **Given** Story 5.1 is complete
- **When** I call `nvd.query("OpenSSH", "8.2")`
- **Then** source queries NVD API via `nvdlib`
- **And** returns CVEs matching CPE for service/version
- **And** results include: cve_id, cvss_score, cvss_vector, description, references
- **And** results are prioritized by CVSS (Critical=2, High=3, Medium+=4)
- **And** API key is used if configured (higher rate limit)
- **And** integration tests verify against real NVD API

**Technical Notes:**
- Located in `intelligence/sources/nvd.py`
- Uses `nvdlib` Python library
- Rate limit: 5 requests/30s without key, 50 requests/30s with key
- CPE matching for accurate version correlation
- **Pre-configured:** `nvdlib>=0.7.0` installed, API key in `.env` as `NVD_API_KEY`

---

### Story 5.4: ExploitDB Source Integration

As an **agent**,
I want **to query ExploitDB for available exploits**,
So that **I find public exploits for discovered services (FR68)**.

**Acceptance Criteria:**

- **Given** Story 5.1 is complete
- **When** I call `exploitdb.query("vsftpd", "2.3.4")`
- **Then** source queries via `searchsploit` CLI wrapper
- **And** returns matching exploits with: edb_id, title, path, platform, type
- **And** exploit code path is included for agent reference
- **And** results have priority=6
- **And** integration tests verify against local searchsploit database

**Technical Notes:**
- Located in `intelligence/sources/exploitdb.py`
- Wraps `searchsploit --json` command
- Requires exploitdb package in Kali container
- Update via `searchsploit -u`
- **Pre-configured:** `searchsploit` available in Kali containers, use `subprocess`

---

### Story 5.5: Nuclei Template Index Source

As an **agent**,
I want **to query Nuclei template index for detection templates**,
So that **I find relevant vulnerability checks (FR69)**.

**Acceptance Criteria:**

- **Given** Story 5.1 is complete
- **When** I call `nuclei_index.query("WordPress", "5.8")`
- **Then** source queries local Nuclei template index
- **And** returns matching templates with: template_id, severity, tags, cve_ids
- **And** templates are categorized (cve, exposure, misconfiguration, default-login)
- **And** results have priority=5
- **And** integration tests verify against nuclei-templates repository

**Technical Notes:**
- Located in `intelligence/sources/nuclei.py`
- Index built from `nuclei-templates` repository metadata
- Update via `nuclei -ut`
- Parse template YAML frontmatter for metadata
- **Pre-configured:** `pyyaml>=6.0` already in deps

---

### Story 5.6: Metasploit RPC Source Integration

As an **agent**,
I want **to query Metasploit for available exploit modules**,
So that **I find MSF modules matching discovered services (FR70)**.

**Acceptance Criteria:**

- **Given** Story 5.1 is complete and msfrpcd is running
- **When** I call `metasploit.query("Apache Tomcat", "9.0.30")`
- **Then** source queries via msgpack-rpc to msfrpcd (port 55553)
- **And** uses `module.search` RPC method
- **And** returns matching modules with: module_path, name, rank, disclosure_date, cve_ids
- **And** connection pool maintains 5 concurrent RPC connections
- **And** results have priority=4
- **And** integration tests verify against running msfrpcd

**Technical Notes:**
- Located in `intelligence/sources/metasploit.py`
- Protocol: msgpack-rpc over TCP
- Auth: username/password → session token
- Pool size: 5 connections (per architecture)
- **Pre-configured:** `pymetasploit3` + `msgpack` installed, Docker service in `cyber-range/docker-compose.yml`, creds in `.env` (`MSF_RPC_PASSWORD`, `MSF_RPC_HOST`, `MSF_RPC_PORT`)

---

### Story 5.7: Intelligence Aggregator

As an **agent**,
I want **a unified interface to query all intelligence sources in parallel**,
So that **I get comprehensive results efficiently (FR65, FR71)**.

**Acceptance Criteria:**

- **Given** Stories 5.2-5.6 are complete
- **When** I call `aggregator.query("Apache", "2.4.49")`
- **Then** all enabled sources are queried in parallel
- **And** each source has 5s timeout (FR74)
- **And** results are merged and deduplicated by CVE ID
- **And** results are sorted by priority (CISA KEV > Critical > High > MSF > Nuclei > ExploitDB)
- **And** partial results returned if some sources timeout
- **And** aggregation completes within 6s max (5s source + 1s overhead)
- **And** integration tests verify parallel query behavior

**Technical Notes:**
- Located in `intelligence/aggregator.py`
- Uses `asyncio.gather()` with timeout per source
- Deduplication merges data from multiple sources for same CVE
- Returns `IntelligenceResult` with prioritized list

---

### Story 5.8: Redis Intelligence Cache

As a **developer**,
I want **Redis-backed caching for intelligence queries**,
So that **repeated queries are fast and reduce API load (FR72)**.

**Acceptance Criteria:**

- **Given** Story 5.7 is complete and Redis is available
- **When** aggregator queries for a service/version
- **Then** cache is checked first (key: `intel:{service}:{version}`)
- **And** cache hit returns immediately without source queries
- **And** cache miss triggers source queries, then caches result
- **And** TTL is configurable (default: 1 hour per architecture)
- **And** cache can be invalidated per service or globally
- **And** integration tests verify cache hit/miss behavior

**Technical Notes:**
- Located in `intelligence/cache.py`
- Key format: `intel:{hash(service:version)}`
- TTL from config: `intelligence.cache_ttl` (default 3600s)
- JSON serialization for cached results

---

### Story 5.9: Offline Intelligence Mode

As an **operator**,
I want **intelligence queries to work with cached data when sources are unavailable**,
So that **engagements can continue during network issues (FR73)**.

**Acceptance Criteria:**

- **Given** Story 5.8 is complete
- **When** all intelligence sources timeout or fail
- **Then** aggregator returns cached results if available
- **And** results are marked `stale: true` with cache timestamp
- **And** log warns "Intelligence sources unavailable, using cached data"
- **When** cache has no data for query
- **Then** aggregator returns empty result with `offline: true`
- **And** agent proceeds without intelligence enrichment
- **And** integration tests simulate offline scenarios

**Technical Notes:**
- Graceful degradation pattern
- Cache never expires in offline mode (stale > nothing)
- Offline detection: all sources fail within timeout

---

### Story 5.10: Intelligence Stigmergic Publication

As an **agent**,
I want **to publish intelligence results to the stigmergic layer**,
So that **other agents skip redundant queries (FR75)**.

**Acceptance Criteria:**

- **Given** Stories 5.7 and Epic 3 (event bus) are complete
- **When** I receive intelligence results for a target
- **Then** results are published to `findings:{target_hash}:intel_enriched`
- **And** other agents subscribed to this topic receive the intelligence
- **And** agents check stigmergic layer before querying aggregator
- **And** stigmergic intelligence has shorter TTL (5 min) than cache
- **And** integration tests verify swarm-wide intelligence sharing

**Technical Notes:**
- Reduces API load across swarm
- Stigmergic key: `findings:{target_hash}:intel_enriched`
- Check order: stigmergic → cache → sources

---

### Story 5.11: Intelligence Query Error Handling

As an **agent**,
I want **graceful error handling when intelligence sources fail**,
So that **I can continue operating with partial or no intelligence (ERR3)**.

**Acceptance Criteria:**

- **Given** Story 5.7 is complete
- **When** a source times out (>5s)
- **Then** source is skipped, other sources continue
- **And** partial results returned from successful sources
- **When** a source returns invalid data
- **Then** error is logged, source result excluded
- **When** all sources fail
- **Then** fallback to cache (Story 5.9)
- **And** agent receives structured result (never exception)
- **And** safety tests verify agents continue after intelligence failures

**Technical Notes:**
- Per ERR3 pattern: log, return partial, continue
- Never block agent on intelligence failure
- Metrics track source failure rates for monitoring

---

## Epic 6: RAG Escalation Layer

**User Outcome:** When standard intelligence is exhausted, system can query advanced methodologies from ATT&CK, HackTricks, and other offensive security knowledge bases.

**FRs Covered:** FR76, FR77, FR78, FR79, FR80, FR81, FR82, FR83, FR84
**NFRs Covered:** NFR26 (config flexibility)

---

### Story 6.1: LanceDB Vector Store Setup

As a **developer**,
I want **an embedded LanceDB vector store for RAG queries**,
So that **methodology retrieval can happen locally without external dependencies (FR80)**.

**Acceptance Criteria:**

- **Given** LanceDB is configured
- **When** I initialize `RAGStore`
- **Then** LanceDB creates or opens store at `~/.cyber-red/rag/lancedb`
- **And** store supports ~70K vectors (500MB-1GB storage)
- **And** store is disk-based (persists across restarts)
- **And** store supports similarity search with configurable `top_k`
- **And** `store.health_check()` verifies store accessibility
- **And** unit tests verify store initialization and basic operations

**Technical Notes:**
- Located in `rag/store.py`
- LanceDB is embedded (no server process)
- Schema: `{id, text, source, technique_ids, metadata, embedding}`

---

### Story 6.2: ATT&CK-BERT Embedding Model

As a **developer**,
I want **ATT&CK-BERT embeddings optimized for cybersecurity domain**,
So that **methodology queries have high relevance for offensive security (FR80)**.

**Acceptance Criteria:**

- **Given** Story 6.1 is complete
- **When** I call `embeddings.encode(text)`
- **Then** ATT&CK-BERT model generates embeddings
- **And** model runs on CPU only (no GPU required)
- **And** embedding dimension matches LanceDB vector column
- **When** ATT&CK-BERT is unavailable
- **Then** fallback to `all-mpnet-base-v2` (sentence-transformers)
- **And** log warning about fallback
- **And** integration tests verify embedding generation

**Technical Notes:**
- Located in `rag/embeddings.py`
- Primary: `basel/ATTACK-BERT`
- Fallback: `all-mpnet-base-v2`
- Cache model in memory after first load

---

### Story 6.3: RAG Query Interface

As an **agent**,
I want **a semantic search interface for methodology retrieval**,
So that **I can find relevant techniques when standard approaches fail (FR76)**.

**Acceptance Criteria:**

- **Given** Stories 6.1 and 6.2 are complete
- **When** I call `rag.query("lateral movement techniques for Windows Server 2022")`
- **Then** query is embedded using ATT&CK-BERT
- **And** similarity search returns top-k results (default: 5)
- **And** results include: text, source, technique_ids, relevance_score
- **And** results are sorted by relevance_score descending
- **And** query timeout is configurable (default: 10s)
- **And** integration tests verify query returns relevant methodologies

**Technical Notes:**
- Located in `rag/query.py`
- Returns `List[RAGResult]` with metadata
- Chunk size: 512 tokens (configured in ingest)

---

### Story 6.4: Document Ingestion Pipeline

As a **developer**,
I want **a document ingestion pipeline for RAG sources**,
So that **knowledge bases can be loaded and updated (FR77)**.

**Acceptance Criteria:**

- **Given** Stories 6.1 and 6.2 are complete
- **When** I call `ingest.process(source, documents)`
- **Then** documents are chunked (512 tokens, 50 token overlap)
- **And** chunks are embedded using ATT&CK-BERT
- **And** chunks are stored in LanceDB with source metadata
- **And** existing chunks from same source are replaced (upsert)
- **And** ingestion progress is trackable (for TUI display)
- **And** integration tests verify full ingest cycle

**Technical Notes:**
- Located in `rag/ingest.py`
- Chunking: RecursiveCharacterTextSplitter or equivalent
- Track `{source: {last_updated, chunk_count, document_count}}`

---

### Story 6.5: MITRE ATT&CK Source Integration

As a **developer**,
I want **MITRE ATT&CK framework ingestion**,
So that **agents can query technique details and detection methods (FR77)**.

**Acceptance Criteria:**

- **Given** Story 6.4 is complete
- **When** I call `mitre_attack.ingest()`
- **Then** ATT&CK Enterprise STIX bundle is downloaded
- **And** techniques are extracted with: id, name, description, tactics, platforms
- **And** mitigations and detection methods are included
- **And** sub-techniques are linked to parent techniques
- **And** chunks include ATT&CK technique IDs (T####.###)
- **And** integration tests verify ATT&CK ingestion

**Technical Notes:**
- Located in `rag/sources/mitre_attack.py`
- Source: `https://github.com/mitre/cti` (STIX format)
- Parse with `stix2` library

---

### Story 6.6: Atomic Red Team Source Integration

As a **developer**,
I want **Atomic Red Team test ingestion**,
So that **agents can find executable test procedures for techniques (FR77)**.

**Acceptance Criteria:**

- **Given** Story 6.4 is complete
- **When** I call `atomic_red.ingest()`
- **Then** Atomic Red Team YAML tests are downloaded
- **And** tests are extracted with: technique_id, test_name, description, commands
- **And** platform compatibility is included (Windows, Linux, macOS)
- **And** attack_commands and cleanup_commands are captured
- **And** links to ATT&CK technique IDs are preserved
- **And** integration tests verify Atomic Red Team ingestion

**Technical Notes:**
- Located in `rag/sources/atomic_red.py`
- Source: `https://github.com/redcanaryco/atomic-red-team`
- Parse YAML atomics directory

---

### Story 6.7: HackTricks Source Integration

As a **developer**,
I want **HackTricks knowledge base ingestion**,
So that **agents can query practical exploitation techniques (FR77)**.

**Acceptance Criteria:**

- **Given** Story 6.4 is complete
- **When** I call `hacktricks.ingest()`
- **Then** HackTricks markdown files are downloaded
- **And** content is chunked preserving code blocks
- **And** metadata includes: category (pentesting, cloud, mobile), last_modified
- **And** links to external resources are preserved
- **And** integration tests verify HackTricks ingestion

**Technical Notes:**
- Located in `rag/sources/hacktricks.py`
- Source: `https://github.com/HackTricks-wiki/hacktricks`
- Parse markdown, preserve headers as context

---

### Story 6.8: PayloadsAllTheThings & LOLBAS/GTFOBins Integration

As a **developer**,
I want **PayloadsAllTheThings, LOLBAS, and GTFOBins ingestion**,
So that **agents can find payloads and living-off-the-land binaries (FR77)**.

**Acceptance Criteria:**

- **Given** Story 6.4 is complete
- **When** I call `payloads.ingest()`
- **Then** PayloadsAllTheThings repo is processed
- **And** payloads are categorized by attack type
- **When** I call `lolbas.ingest()`
- **Then** LOLBAS YAML (Windows) and GTFOBins YAML (Linux) are processed
- **And** binaries include: name, description, commands, ATT&CK mapping
- **And** integration tests verify all three sources ingest correctly

**Technical Notes:**
- Located in `rag/sources/payloads.py`, `rag/sources/lolbas.py`
- PayloadsAllTheThings: `https://github.com/swisskyrepo/PayloadsAllTheThings`
- LOLBAS: `https://github.com/LOLBAS-Project/LOLBAS`
- GTFOBins: `https://github.com/GTFOBins/GTFOBins.github.io`

---

### Story 6.9: Director Ensemble RAG Integration

As a **Director Ensemble**,
I want **to query RAG for strategic pivot methodologies**,
So that **I can provide advanced guidance when standard intelligence fails (FR78)**.

**Acceptance Criteria:**

- **Given** Stories 6.1-6.3 are complete and Director Ensemble exists
- **When** Director requests strategy pivot
- **Then** Director can call `rag.query()` for methodology suggestions
- **And** RAG results are incorporated into synthesis
- **And** results include ATT&CK technique IDs for kill chain correlation (FR84)
- **And** RAG query is non-blocking (agents continue if RAG slow)
- **And** integration tests verify Director RAG integration

**Technical Notes:**
- Triggered by: repeated swarm failures, phase transition, operator request
- Director formats RAG results into actionable guidance for agents
- RAG is escalation path, not primary intelligence source

---

### Story 6.10: Agent RAG Escalation

As an **agent**,
I want **to query RAG when my exploit attempts repeatedly fail**,
So that **I can discover alternative approaches (FR79)**.

**Acceptance Criteria:**

- **Given** Stories 6.1-6.3 are complete
- **When** agent fails 3+ exploit attempts on same target
- **Then** agent can call `rag.query()` for alternative methodologies
- **And** query context includes: target service, failed techniques, environment
- **And** RAG results suggest alternative attack paths
- **And** agent logs RAG escalation in `decision_context`
- **And** integration tests verify agent RAG escalation triggers

**Technical Notes:**
- Failure counter per target/technique pair
- Reset failure counter after successful exploit
- RAG escalation logged for emergence tracking

---

### Story 6.11: TUI RAG Management Widget

As an **operator**,
I want **to manage RAG updates via TUI**,
So that **I can refresh knowledge bases without CLI access (FR81, FR85)**.

**Acceptance Criteria:**

- **Given** Stories 6.1-6.8 are complete and TUI exists
- **When** I open RAG Management panel
- **Then** I see: corpus stats (total vectors, storage size), per-source status
- **And** I see last update timestamp for each source
- **And** "Update RAG" button triggers full re-ingestion
- **And** ingestion progress is displayed in real-time
- **And** I can update individual sources selectively
- **And** integration tests verify TUI RAG management

**Technical Notes:**
- Located in `tui/widgets/rag_manager.py`
- Display: source name, chunk count, last updated, status
- Non-blocking update (engagement continues during refresh)

---

### Story 6.12: Scheduled RAG Refresh

As an **operator**,
I want **automatic weekly RAG updates**,
So that **knowledge bases stay current without manual intervention (FR82)**.

**Acceptance Criteria:**

- **Given** Stories 6.1-6.8 are complete
- **When** system is running on scheduled day (default: Sunday 3AM)
- **Then** RAG refresh triggers automatically for core sources
- **And** refresh runs in background (no engagement interruption)
- **And** schedule is configurable via `config.yaml`
- **And** refresh failure logs warning but doesn't block operations
- **And** last auto-refresh timestamp is tracked
- **And** integration tests verify scheduled refresh mechanism

**Technical Notes:**
- Use asyncio scheduler or cron-like mechanism
- Config: `rag.update_schedule: "weekly"` or `"manual"`
- Core sources: ATT&CK, Atomic Red Team, HackTricks

---

### Story 6.13: RAG Result Metadata & ATT&CK Mapping

As an **agent**,
I want **RAG results with rich metadata including ATT&CK technique IDs**,
So that **I can correlate methodologies with kill chain phases (FR83, FR84)**.

**Acceptance Criteria:**

- **Given** Stories 6.1-6.3 are complete
- **When** RAG query returns results
- **Then** each result includes: source, last_updated, relevance_score
- **And** results include ATT&CK technique IDs where applicable
- **And** technique IDs are formatted as T#### or T####.### (sub-technique)
- **And** results can be filtered by tactic (e.g., "lateral-movement")
- **And** unit tests verify metadata completeness

**Technical Notes:**
- Metadata stored in LanceDB during ingestion
- ATT&CK mapping extracted from source content or explicit tags
- Enable kill chain phase correlation in Director synthesis

---

## Epic 7: Agent Framework & Stigmergic Coordination

**User Outcome:** 10,000+ LLM-powered agents coordinate via P2P stigmergic signals with provable emergence (>20% novel attack chains).

**FRs Covered:** FR2, FR4, FR5, FR6, FR62
**NFRs Covered:** NFR1, NFR6, NFR7, NFR8, NFR35, NFR36, NFR37
**Errors Handled:** ERR5

> [!IMPORTANT]
> **Framework:** This epic uses [kyegomez/swarms](https://github.com/kyegomez/swarms) v8.0.0+ — the enterprise-grade multi-agent orchestration framework. This is **NOT** OpenAI's experimental "Swarm" project. All agents extend Swarms' native `Agent` class.

> [!CAUTION]
> **HARD GATE EPIC:** NFR35-37 emergence validation MUST pass. System cannot ship without proving stigmergic coordination produces >20% novel attack chains vs isolated agents.

---

### Story 7.1: StigmergicAgent Base Class

As a **developer**,
I want **a base agent class with stigmergic pub/sub hooks**,
So that **all agents can participate in P2P coordination (FR4)**.

**Acceptance Criteria:**

- **Given** Epic 3 (event bus) is complete
- **When** I extend `StigmergicAgent`
- **Then** agent has `on_finding()` lifecycle hook → publishes to Redis
- **And** agent has `on_signal()` lifecycle hook → reacts to swarm state
- **And** agent has `on_complete()` lifecycle hook → updates stigmergic map
- **And** agent subscribes to relevant topic patterns on spawn
- **And** agent includes `agent_id`, `engagement_id` in all messages
- **And** unit tests verify lifecycle hooks fire correctly

**Technical Notes:**
- Located in `agents/base.py`
- **Framework:** [kyegomez/swarms](https://github.com/kyegomez/swarms) v8.0.0+ (NOT OpenAI Swarm)
```python
from swarms import Agent  # kyegomez/swarms

class StigmergicAgent(Agent):
    """Base agent with stigmergic pub/sub hooks."""
```
- Lifecycle: spawn → subscribe → execute → on_signal → on_finding → on_complete

---

### Story 7.2: Agent Self-Throttling

As an **agent**,
I want **to self-throttle when LLM queue depth is high**,
So that **I don't starve the system when many agents are active (NFR8)**.

**Acceptance Criteria:**

- **Given** Story 7.1 is complete
- **When** LLM queue depth exceeds threshold (default: 80%)
- **Then** agent enters WAITING state
- **And** agent checks queue depth periodically (every 5s)
- **And** agent resumes when queue depth drops below threshold
- **And** agent logs throttling events
- **And** integration tests verify throttling behavior

**Technical Notes:**
- Query LLM Gateway for queue depth
- Threshold configurable via `config.yaml`
- Prevents queue starvation under agent flood

---

### Story 7.3: ReconAgent Implementation

As a **developer**,
I want **a reconnaissance agent for discovery and enumeration**,
So that **the swarm can map attack surfaces (FR2)**.

**Acceptance Criteria:**

- **Given** Story 7.1 is complete
- **When** ReconAgent is spawned with a target
- **Then** agent performs reconnaissance using `kali_execute()`
- **And** agent discovers: open ports, services, versions, technologies
- **And** findings are published to `findings:{target_hash}:recon`
- **And** agent subscribes to `strategies:*` for Director guidance
- **And** agent logs `decision_context` for all actions (FR62)
- **And** integration tests verify real reconnaissance in cyber range

**Technical Notes:**
- Located in `agents/recon.py`
- Uses STANDARD tier LLM for reasoning
- Tools: nmap, masscan, whatweb, wafw00f, subfinder

---

### Story 7.4: ExploitAgent Implementation

As a **developer**,
I want **an exploitation agent for vulnerability attacks**,
So that **the swarm can exploit discovered weaknesses (FR2)**.

**Acceptance Criteria:**

- **Given** Story 7.1 is complete
- **When** ExploitAgent receives a target with known vulnerabilities
- **Then** agent queries Intelligence Layer for exploit options
- **And** agent executes exploits via `kali_execute()`
- **And** successful exploits are published to `findings:{target_hash}:exploit`
- **And** agent escalates to RAG after 3+ failures (per Story 6.10)
- **And** agent logs `decision_context` for all actions (FR62)
- **And** integration tests verify real exploitation in cyber range

**Technical Notes:**
- Located in `agents/exploit.py`
- Uses COMPLEX tier LLM for chaining
- Tools: sqlmap, nuclei, metasploit, hydra, crackmapexec

---

### Story 7.5: PostExAgent Implementation

As a **developer**,
I want **a post-exploitation agent for lateral movement and persistence**,
So that **the swarm can achieve deeper objectives (FR2)**.

**Acceptance Criteria:**

- **Given** Story 7.1 is complete
- **When** PostExAgent receives access to a compromised system
- **Then** agent performs post-exploitation enumeration
- **And** agent attempts privilege escalation if applicable
- **And** agent discovers lateral movement opportunities
- **And** findings are published to `findings:{target_hash}:postex`
- **And** lateral movement triggers authorization request (FR13)
- **And** agent logs `decision_context` for all actions (FR62)
- **And** integration tests verify post-exploitation in cyber range

**Technical Notes:**
- Located in `agents/postex.py`
- Uses COMPLEX tier LLM
- Tools: mimikatz, bloodhound, linpeas, winpeas, impacket-*

---

### Story 7.6: SwarmRouter Integration

As a **developer**,
I want **SwarmRouter to route tasks to appropriate swarm types**,
So that **tasks reach the right agent specialization (FR5)**.

**Acceptance Criteria:**

- **Given** Stories 7.3-7.5 are complete
- **When** Director assigns a task
- **Then** SwarmRouter routes to appropriate swarm: recon, exploit, or postex
- **And** routing considers task type and target state
- **And** router supports ConcurrentWorkflow for parallel tasks
- **And** router supports SequentialWorkflow for chained tasks
- **And** integration tests verify correct routing

**Technical Notes:**
- Located in `orchestration/router.py`
- **Framework:** [kyegomez/swarms](https://github.com/kyegomez/swarms) SwarmRouter
```python
from swarms import SwarmRouter  # kyegomez/swarms
```
- Task types: discover, enumerate, exploit, escalate, persist, exfiltrate

---

### Story 7.7: Dynamic Agent Spawner

As a **developer**,
I want **dynamic agent spawning based on attack surface size**,
So that **agent count scales with workload (NFR6, NFR7)**.

**Acceptance Criteria:**

- **Given** Stories 7.3-7.5 are complete
- **When** engagement starts
- **Then** spawner calculates initial agent count based on scope size
- **And** spawner scales agents up as attack surface expands
- **And** spawner enforces ceiling (10K or hardware limit)
- **And** spawner has no artificial limits in code (NFR7)
- **And** spawner logs scaling decisions
- **And** integration tests verify dynamic scaling

**Technical Notes:**
- Located in `orchestration/spawner.py`
- Heuristic: ~10 agents per /24 network, ~5 agents per web app
- Scale up on: new targets discovered, phase transitions

---

### Story 7.8: Decision Context Tracking

As a **developer**,
I want **all agent actions to log which stigmergic signals influenced them**,
So that **emergence can be traced and validated (FR62, NFR37)**.

**Acceptance Criteria:**

- **Given** Story 7.1 is complete
- **When** agent takes any action
- **Then** `AgentAction.decision_context` contains IDs of influencing signals
- **And** decision_context is non-empty when action was influenced by swarm
- **And** 100% of agent actions include decision_context field (NFR37)
- **And** decision_context format: `["signal_id_1", "signal_id_2", ...]`
- **And** emergence tests verify decision_context population

**Technical Notes:**
- Located in `orchestration/emergence/tracker.py`
- Tracks: finding_id → action_id relationships
- Critical for emergence validation

---

### Story 7.9: Isolated vs Stigmergic Comparison Framework

As a **developer**,
I want **a framework to compare isolated agents vs stigmergic agents**,
So that **emergence can be measured scientifically (NFR35)**.

**Acceptance Criteria:**

- **Given** Stories 7.1-7.8 are complete
- **When** emergence test runs
- **Then** isolated run: agents execute without pub/sub (no stigmergic signals)
- **And** stigmergic run: agents execute with full pub/sub enabled
- **And** both runs use identical: targets, scope, agent count, LLM responses
- **And** comparison captures: attack paths, chains, findings
- **And** framework outputs emergence metrics
- **And** emergence tests verify framework correctness

**Technical Notes:**
- Located in `orchestration/emergence/validator.py`
- Isolated mode: disable Redis pub/sub, agents work independently
- Control for LLM randomness via seeded responses in test

---

### Story 7.10: Emergence Score Calculation

As a **developer**,
I want **emergence score calculated as novel chains / total chains**,
So that **we can validate >20% emergence requirement (NFR35)**.

**Acceptance Criteria:**

- **Given** Story 7.9 is complete
- **When** `metrics.calculate_emergence_score(isolated, stigmergic)` is called
- **Then** novel chains = paths in stigmergic NOT in isolated
- **And** emergence score = len(novel_chains) / len(total_stigmergic_paths)
- **And** score is between 0.0 and 1.0
- **And** score >0.20 required for HARD GATE pass
- **And** metrics are exposed via Prometheus (OBS11)
- **And** emergence tests verify score calculation

**Technical Notes:**
- Located in `orchestration/emergence/metrics.py`
- Attack path = sequence of (target, technique, finding) tuples
- Novel = path discovered ONLY through stigmergic coordination

---

### Story 7.11: Causal Chain Depth Validation

As a **developer**,
I want **validation that emergence chains have 3+ hops**,
So that **we prove deep coordination, not shallow signal passing (NFR36)**.

**Acceptance Criteria:**

- **Given** Stories 7.8 and 7.10 are complete
- **When** emergence test runs
- **Then** at least one chain has 3+ hops: Finding→Action→Finding→Action
- **And** hop depth is traced via decision_context links
- **And** chains are logged with full trace for debugging
- **And** HARD GATE fails if no 3+ hop chain exists
- **And** emergence tests verify depth validation

**Technical Notes:**
- Hop = Finding triggers Action triggers Finding triggers Action
- Trace: f1 (agent A) → a2 (agent B via signal) → f2 → a3
- Validates that agents truly build on each other's work

---

### Story 7.12: Agent Crash Recovery

As a **developer**,
I want **crashed agents to be replaced without losing context**,
So that **engagement continues despite individual failures (ERR5)**.

**Acceptance Criteria:**

- **Given** Stories 7.1-7.5 are complete
- **When** agent process crashes
- **Then** worker pool detects crash within 30s
- **And** replacement agent is spawned
- **And** replacement loads last checkpoint (task, context, findings)
- **And** replacement resumes from checkpoint state
- **And** crash is logged with full stack trace
- **And** safety tests verify crash recovery

**Technical Notes:**
- Checkpoint: agent state saved every 60s or on major state change
- Replacement inherits: agent_id, task_assignment, accumulated context
- Per ERR5: "Log crash, spawn replacement, resume from checkpoint"

---

### Story 7.13: Stigmergic Topic Sharding

As a **developer**,
I want **topic sharding to prevent Redis overload at scale**,
So that **10K agents don't overwhelm pub/sub (NFR1, NFR8)**.

**Acceptance Criteria:**

- **Given** Stories 7.1 and Epic 3 are complete
- **When** agent publishes to `findings:{target_hash}:{type}`
- **Then** topic is sharded: `findings:{hash mod 16}:{type}`
- **And** agents subscribe to multiple shards as needed
- **And** sharding is transparent to agent code
- **And** aggregator service batches and deduplicates across shards
- **And** integration tests verify sharding under load

**Technical Notes:**
- Per architecture pre-mortem (line 93)
- 16 shards default (configurable)
- Prevents "stigmergic storm" with 10K subscribers

---

### Story 7.14: Emergence Validation Gate Test

As a **developer**,
I want **a CI gate test that validates emergence requirements**,
So that **we cannot ship without proven stigmergic benefit (NFR35-37)**.

**Acceptance Criteria:**

- **Given** Stories 7.9-7.11 are complete
- **When** CI runs emergence tests
- **Then** test runs in cyber range with 100 agents
- **And** test compares isolated vs stigmergic runs
- **And** test asserts: emergence score > 0.20 (NFR35)
- **And** test asserts: at least one 3+ hop chain (NFR36)
- **And** test asserts: 100% decision_context population (NFR37)
- **And** CI fails if any assertion fails (HARD GATE)

**Technical Notes:**
- Located in `tests/emergence/test_emergence_gate.py`
- Runs against cyber range (real Kali tools)
- This is the SHIP/NO-SHIP gate for v2.0

---

### Story 7.15: Emergent Attack Strategy Triggering

As an **agent**,
I want **to trigger emergent attack strategies based on collective findings**,
So that **the swarm discovers attack paths no individual agent could find (FR6)**.

**Acceptance Criteria:**

- **Given** Stories 7.1-7.8 are complete
- **When** multiple agents publish related findings
- **Then** pattern detection identifies emergent opportunities
- **And** Director synthesizes collective insights into strategy
- **And** strategy is published to `strategies:{engagement_id}`
- **And** agents incorporate strategy into next actions
- **And** emergent paths are logged with full provenance
- **And** emergence tests verify emergent discovery

**Technical Notes:**
- Pattern examples: "Multiple agents found same service version → prioritize"
- Pattern examples: "Credential found + open SMB → lateral movement opportunity"
- Emergence = whole > sum of parts

---

### Story 7.16: Agent Authorization Response Handling

As an **agent**,
I want **to wait for and process authorization responses**,
So that **lateral movement proceeds only when operator approves (FR13, FR15)**.

**Acceptance Criteria:**

- **Given** agent has requested authorization for lateral movement
- **When** authorization request is published
- **Then** agent enters WAITING_AUTHORIZATION state
- **And** agent subscribes to `auth:{request_id}:response`
- **When** operator grants authorization
- **Then** agent receives response and resumes action
- **When** operator denies authorization
- **Then** agent logs denial and selects alternative action
- **And** agent logs authorization outcome in `decision_context`
- **And** integration tests verify authorization wait/resume flow

**Technical Notes:**
- Located in `agents/base.py` (StigmergicAgent)
- Timeout: indefinite (per FR16 — no auto-deny)
- State: WAITING_AUTHORIZATION → RUNNING or ALTERNATIVE_PATH

---

### Story 7.17: Director-Agent Feedback Loop Integration

As a **developer**,
I want **verified integration between Director strategy and agent behavior**,
So that **agents demonstrably change behavior based on Director guidance**.

**Acceptance Criteria:**

- **Given** Director publishes strategy to `strategies:{engagement_id}`
- **When** agents receive strategy update
- **Then** agents adjust priorities based on strategy.objectives
- **And** agents avoid targets in strategy.avoid_list
- **And** agents incorporate strategy.recommended_techniques
- **And** behavior change is logged in `decision_context` (citing strategy_id)
- **And** integration test verifies: strategy publish → agent behavior change
- **And** e2e test captures before/after agent actions

**Technical Notes:**
- Critical for proving Director value
- Test: publish "prioritize web apps" → verify agents shift from network to web
- Located in `tests/integration/test_feedback_loop.py`

---

## Epic 8: Director Ensemble & Strategy Synthesis

**User Outcome:** Operator receives unified strategic guidance synthesized from three specialized LLMs (DeepSeek v3.2, Kimi K2, MiniMax M2), each contributing domain expertise.

**FRs Covered:** FR1, FR3, FR10
**NFRs Covered:** NFR5, NFR29
**Errors Handled:** ERR2

---

### Story 8.1: Director Ensemble Base Architecture

As a **developer**,
I want **an ensemble that coordinates three LLM models for strategy synthesis**,
So that **strategic decisions benefit from multi-perspective analysis (FR3)**.

**Acceptance Criteria:**

- **Given** Epic 3 (LLM Gateway) is complete
- **When** I initialize `DirectorEnsemble`
- **Then** ensemble configures three models: DeepSeek, Kimi K2, MiniMax M2
- **And** each model has defined role: strategist, analyst, creative
- **And** ensemble supports parallel query to all three models
- **And** ensemble supports synthesis of responses into unified strategy
- **And** unit tests verify ensemble initialization

**Technical Notes:**
- Located in `llm/ensemble.py`
- Models via NVIDIA NIM: `deepseek-ai/deepseek-v3_2`, `moonshot-ai/kimi-k2`, `minimaxai/minimax-m2`
- **Framework:** [kyegomez/swarms](https://github.com/kyegomez/swarms) MixtureOfAgents pattern
```python
from swarms import MixtureOfAgents  # kyegomez/swarms – NOT OpenAI Swarm!
```

---

### Story 8.2: DeepSeek Strategist Role

As a **Director Ensemble**,
I want **DeepSeek v3.2 to provide strategic planning and methodology**,
So that **engagements follow proven attack frameworks (FR3)**.

**Acceptance Criteria:**

- **Given** Story 8.1 is complete
- **When** ensemble queries DeepSeek
- **Then** DeepSeek receives: swarm state, findings summary, objective
- **And** DeepSeek returns: strategic recommendations, next phases, priorities
- **And** response includes ATT&CK technique recommendations
- **And** timeout is 30s per config
- **And** integration tests verify DeepSeek strategy output

**Technical Notes:**
- Role prompt: "Strategic planning and methodology"
- Strength: Long-context reasoning, attack chain planning
- Model: `deepseek-ai/deepseek-v3_2`

---

### Story 8.3: Kimi K2 Analyst Role

As a **Director Ensemble**,
I want **Kimi K2 to provide deep reasoning and analysis**,
So that **complex attack surfaces are thoroughly analyzed (FR3)**.

**Acceptance Criteria:**

- **Given** Story 8.1 is complete
- **When** ensemble queries Kimi K2
- **Then** Kimi K2 receives: findings details, target environment, discovered paths
- **And** Kimi K2 returns: analysis of attack surface, risk assessment, gaps
- **And** response identifies overlooked opportunities
- **And** timeout is 45s per config (longer for deep reasoning)
- **And** integration tests verify Kimi K2 analysis output

**Technical Notes:**
- Role prompt: "Deep reasoning and analysis"
- Strength: Complex multi-step reasoning
- Model: `moonshot-ai/kimi-k2`

---

### Story 8.4: MiniMax M2 Creative Role

As a **Director Ensemble**,
I want **MiniMax M2 to provide creative approaches and evasion techniques**,
So that **unconventional attack paths are explored (FR3)**.

**Acceptance Criteria:**

- **Given** Story 8.1 is complete
- **When** ensemble queries MiniMax M2
- **Then** MiniMax M2 receives: current strategy, defenses encountered, failed attempts
- **And** MiniMax M2 returns: creative alternatives, evasion techniques, novel approaches
- **And** response uses interleaved thinking (`<think>...</think>` tags)
- **And** thinking tags are preserved for reasoning visibility
- **And** timeout is 30s per config
- **And** integration tests verify MiniMax M2 creative output

**Technical Notes:**
- Role prompt: "Creative approaches and evasion"
- Strength: Interleaved thinking, lateral problem-solving
- Model: `minimaxai/minimax-m2`
- Special handling for `<think>` tags in response parsing

---

### Story 8.5: Strategy Synthesis Engine

As a **Director Ensemble**,
I want **to synthesize three model outputs into unified strategy**,
So that **agents receive coherent, multi-perspective guidance (FR3)**.

**Acceptance Criteria:**

- **Given** Stories 8.2-8.4 are complete
- **When** all three models return responses
- **Then** synthesizer combines outputs into unified strategy
- **And** synthesis preserves key insights from each perspective
- **And** synthesis resolves conflicting recommendations
- **And** synthesis prioritizes by confidence and consensus
- **And** final strategy is structured: objectives, actions, rationale
- **And** integration tests verify synthesis quality

**Technical Notes:**
- Located in `llm/ensemble.py`
- Synthesis strategy: combine (not vote)
- Uses aggregator LLM call if needed for complex synthesis
- Timeout: 60s aggregate (per architecture)

---

### Story 8.6: Partial Model Availability Fallback

As a **Director Ensemble**,
I want **graceful degradation when some models are unavailable**,
So that **engagement continues despite LLM provider issues (NFR29, ERR2)**.

**Acceptance Criteria:**

- **Given** Story 8.1 is complete
- **When** 2 of 3 models are available
- **Then** synthesis uses available pair with degradation warning
- **When** 1 of 3 models is available
- **Then** single-model operation with operator warning
- **When** 0 models are available
- **Then** engagement pauses, operator action required
- **And** retry interval is 30s for unavailable providers
- **And** alert threshold logs warning if fewer than 2 models
- **And** safety tests verify fallback behavior

**Technical Notes:**
- Per architecture fallback config (lines 1686-1692)
- Min models to continue: 1
- Circuit breaker: 3 failures → exclude model for 60s

---

### Story 8.7: Natural Language Mission Directive

As an **operator**,
I want **to issue mission directives in natural language**,
So that **I can guide the engagement without technical commands (FR1)**.

**Acceptance Criteria:**

- **Given** Story 8.1 is complete
- **When** I type "Focus on web application vulnerabilities, skip network infrastructure"
- **Then** Director Ensemble interprets the directive
- **And** Director translates into agent task priorities
- **And** directive is logged to audit trail
- **And** agents receive updated strategy via `strategies:{engagement_id}`
- **And** integration tests verify natural language interpretation

**Technical Notes:**
- Located in `orchestration/directive.py`
- Director uses context: current scope, findings, agent state
- Validation: directive cannot override scope rules (hard-gate)

---

### Story 8.8: Re-Plan Triggers

As a **Director Ensemble**,
I want **automatic re-planning based on engagement events**,
So that **strategy adapts to discoveries and changes (FR1)**.

**Acceptance Criteria:**

- **Given** Stories 8.1-8.5 are complete
- **When** critical finding is discovered (severity: critical)
- **Then** re-plan trigger fires within 30s
- **When** phase transition occurs (recon → exploit → postex)
- **Then** re-plan trigger fires immediately
- **When** 5-minute timer expires
- **Then** periodic re-plan trigger fires
- **And** aggregator batches findings for re-plan input
- **And** integration tests verify all trigger types

**Technical Notes:**
- Located in `orchestration/replan_triggers.py`
- Triggers: timer (5min), critical finding, phase transition, operator directive
- Per architecture feedback loop (lines 807)

---

### Story 8.9: Finding Aggregation for Director Input

As a **Director Ensemble**,
I want **aggregated findings as input for strategy synthesis**,
So that **Director sees the complete picture, not individual events**.

**Acceptance Criteria:**

- **Given** Epic 7 (agents publishing findings) is complete
- **When** re-plan trigger fires
- **Then** aggregator collects findings since last Director cycle
- **And** findings are deduplicated by target + type
- **And** findings are grouped by category (recon, exploit, postex)
- **And** aggregator produces summary statistics (counts, severities)
- **And** summary is formatted for Director prompt
- **And** unit tests verify aggregation logic

**Technical Notes:**
- Located in `orchestration/aggregator.py`
- Max findings per cycle: 100 (configurable, prevents context overflow)
- Prioritize by severity, then recency

---

### Story 8.10: Strategy Publication to Agents

As a **Director Ensemble**,
I want **to publish synthesized strategy to the swarm**,
So that **agents can incorporate strategic guidance into actions**.

**Acceptance Criteria:**

- **Given** Stories 8.5 and 8.9 are complete
- **When** Director completes strategy synthesis
- **Then** strategy is published to `strategies:{engagement_id}`
- **And** agents subscribed to strategy topic receive update
- **And** strategy includes: objectives, priorities, recommended techniques
- **And** strategy includes: avoid list (targets to skip, failed approaches)
- **And** agents incorporate strategy in `decision_context`
- **And** integration tests verify end-to-end strategy flow

**Technical Notes:**
- Strategy format: JSON with structured fields
- Agents update behavior based on strategy (not hard directives)
- Enables emergent + directed behavior balance

---

### Story 8.11: Director Ensemble TUI Display

As an **operator**,
I want **to view all three Director perspectives in the TUI**,
So that **I understand the strategic reasoning behind decisions (FR10)**.

**Acceptance Criteria:**

- **Given** Stories 8.1-8.5 are complete and TUI exists
- **When** Director produces synthesis
- **Then** TUI displays: DeepSeek strategy view, Kimi K2 analysis view, MiniMax M2 creative view
- **And** TUI displays: synthesized unified strategy
- **And** MiniMax thinking tags are optionally visible (debug mode)
- **And** I can expand/collapse individual perspectives
- **And** updates are real-time via daemon connection
- **And** integration tests verify TUI Director display

**Technical Notes:**
- Located in `tui/widgets/director_display.py`
- Three-column or tabbed layout
- Highlight consensus vs divergent recommendations

---

## Epic 9: War Room TUI Core

**User Outcome:** Operator has a responsive terminal UI for monitoring 10,000+ agents, viewing findings in real-time, and managing engagements via daemon attach/detach.

**FRs Covered:** FR7, FR8, FR9, FR11, FR12, FR47
**NFRs Covered:** NFR4, NFR32

---

### Story 9.1: Textual App Foundation

As a **developer**,
I want **a Textual-based TUI application skeleton**,
So that **the War Room can be built with modern async terminal UI (FR47)**.

**Acceptance Criteria:**

- **Given** Textual framework is installed
- **When** I run `cyber-red attach {id}`
- **Then** TUI application launches in terminal
- **And** app uses Textual's async architecture
- **And** app supports CSS styling via `war_room.css`
- **And** app handles terminal resize gracefully
- **And** unit tests verify app initialization

**Technical Notes:**
- Located in `tui/app.py`
- Textual v0.40.0+ required
- Dark mode "Command & Control" aesthetic per UX spec

---

### Story 9.2: War Room Three-Pane Layout

As an **operator**,
I want **a three-pane War Room layout**,
So that **I can see targets, agents, and strategy simultaneously**.

**Acceptance Criteria:**

- **Given** Story 9.1 is complete
- **When** TUI launches
- **Then** layout shows three panes: Targets (left), Hive Matrix (center), Strategy Stream (right)
- **And** panes are resizable via drag or keyboard
- **And** layout persists across sessions
- **And** F-key navigation switches focus between panes
- **And** integration tests verify layout rendering

**Technical Notes:**
- Per UX spec: three-pane "War Room" layout
- Targets: scope tree, discovered hosts
- Hive Matrix: agent status grid
- Strategy Stream: Director output + findings

---

### Story 9.3: Virtualized Agent List (10K+ Scale)

As an **operator**,
I want **a virtualized list that can display 10,000+ agents**,
So that **UI remains responsive at full scale (FR7, NFR4)**.

**Acceptance Criteria:**

- **Given** Story 9.2 is complete
- **When** 10,000 agents are active
- **Then** agent list renders in <100ms (NFR4)
- **And** only visible rows are rendered (virtualization)
- **And** scrolling is smooth (60fps target)
- **And** Textual's `spatial_map` is used for O(1) visibility queries
- **And** integration tests verify performance at 10K agents

**Technical Notes:**
- Located in `tui/widgets/agent_list.py`
- Per architecture: Textual spatial_map for constant-time visibility
- Display: agent_id, status, target, last_action

---

### Story 9.4: Anomaly Bubbling

As an **operator**,
I want **anomaly and attention-required agents bubbled to the top**,
So that **I notice important agents without scrolling (FR8)**.

**Acceptance Criteria:**

- **Given** Story 9.3 is complete
- **When** agent requires attention (auth pending, error, critical finding)
- **Then** agent row moves to top of list
- **And** attention indicator is visually distinct (color, icon)
- **And** attention types are prioritized: error > auth_pending > critical_finding
- **And** bubbling animation is smooth
- **And** I can dismiss attention to return agent to normal position
- **And** integration tests verify bubbling behavior

**Technical Notes:**
- Attention states: AUTH_PENDING, ERROR, CRITICAL_FINDING, STALLED
- Per UX: "Attention on Demand" principle
- Re-sort on state change, not continuous

---

### Story 9.5: Real-Time Finding Stream

As an **operator**,
I want **a real-time finding stream separate from agent status**,
So that **I see discoveries as they happen (FR9)**.

**Acceptance Criteria:**

- **Given** Stories 9.1-9.2 are complete
- **When** agents publish findings
- **Then** findings appear in Strategy Stream pane
- **And** findings are color-coded by severity (critical=red, high=orange, medium=yellow)
- **And** stream auto-scrolls to show latest (with pause option)
- **And** I can click a finding to see details
- **And** stream updates in <500ms from discovery
- **And** integration tests verify real-time updates

**Technical Notes:**
- Located in `tui/widgets/finding_stream.py`
- WebSocket push from daemon
- Display: timestamp, severity, type, target, summary

---

### Story 9.6: Hive Matrix Agent Grid

As an **operator**,
I want **a visual grid showing agent status and stigmergic connections**,
So that **I can see swarm coordination at a glance (FR11)**.

**Acceptance Criteria:**

- **Given** Story 9.3 is complete
- **When** agents are active
- **Then** Hive Matrix shows agents as grid cells
- **And** cell color indicates status: active=green, idle=blue, error=red
- **And** stigmergic connections are visualized (lines or grouping)
- **And** I can zoom in/out on the matrix
- **And** hover shows agent details
- **And** integration tests verify matrix rendering

**Technical Notes:**
- Located in `tui/widgets/hive_matrix.py`
- Inspired by ant colony visualization
- 10K agents = 100x100 grid or similar density view

---

### Story 9.7: Daemon Unix Socket Client

As a **developer**,
I want **TUI to connect to daemon via Unix socket**,
So that **TUI is a client to the background daemon**.

**Acceptance Criteria:**

- **Given** Daemon is running (Epic 2)
- **When** TUI starts with `attach {id}`
- **Then** TUI connects to `~/.cyber-red/daemon.sock`
- **And** TUI authenticates with engagement ID
- **And** TUI receives initial state sync
- **And** TUI subscribes to real-time updates
- **And** connection failure shows clear error message
- **Given** no daemon activity for 60 seconds
- **When** stale state is detected
- **Then** "No activity for 60s" warning displays in status bar
- **And** warning includes last activity timestamp and refresh prompt
- **And** integration tests verify socket communication
- **And** integration tests verify stale state warning display

**Technical Notes:**
- Located in `tui/daemon_client.py`
- Protocol: JSON over Unix socket
- Async connection with Textual's event loop
- Stale detection: heartbeat-based or activity timestamp

---

### Story 9.8: TUI Attach Latency (<2s)

As an **operator**,
I want **TUI attach to complete in <2s**,
So that **I can quickly connect to running engagements (NFR32)**.

**Acceptance Criteria:**

- **Given** Stories 9.1-9.7 are complete
- **When** I run `cyber-red attach {id}`
- **Then** TUI is operational within 2s
- **And** full engagement state is synced during attach
- **And** attach shows progress indicator
- **And** safety tests verify <2s attach latency

**Technical Notes:**
- State sync: incremental, not full dump
- Priority: agent count, findings count, then details
- Per NFR32: <2s from command to operational TUI

---

### Story 9.9: TUI Detach (Ctrl+D)

As an **operator**,
I want **to detach TUI without stopping the engagement**,
So that **I can disconnect and reattach later (FR59)**.

**Acceptance Criteria:**

- **Given** TUI is attached to engagement
- **When** I press Ctrl+D or type `detach`
- **Then** TUI disconnects cleanly
- **And** daemon continues running engagement
- **And** "Detached from {engagement_id}" message shown
- **And** terminal returns to shell
- **And** safety tests verify detach doesn't stop engagement

**Technical Notes:**
- Detach = graceful disconnect, not kill
- SSH disconnect behaves same as Ctrl+D
- Per FR59: detach without stopping engagement

---

### Story 9.10: Drop Box Status Panel

As an **operator**,
I want **a panel showing drop box status**,
So that **I can monitor C2 link health (FR12)**.

**Acceptance Criteria:**

- **Given** Stories 9.1-9.2 are complete
- **When** drop box is connected
- **Then** panel shows: connection status, last heartbeat, uptime, network info
- **And** heartbeat indicator pulses on each successful heartbeat
- **And** missed heartbeats show warning (3 missed = yellow, 6 = red)
- **And** panel is accessible via F-key shortcut
- **And** integration tests verify drop box status display

**Technical Notes:**
- Located in `tui/screens/dropbox.py`
- Per UX: HeartbeatIndicator widget
- Heartbeat interval: 5s per architecture

---

### Story 9.11: Keyboard Navigation (F-Keys)

As an **operator**,
I want **F-key shortcuts for quick navigation**,
So that **I can switch views without mouse (per UX design)**.

**Acceptance Criteria:**

- **Given** Story 9.2 is complete
- **When** I press F1-F10
- **Then** each F-key switches to designated view/action
- **And** current mapping displayed in footer
- **And** F1=Help, F2=Targets, F3=Agents, F4=Findings, F5=Director, F10=Kill Switch
- **And** mappings are configurable
- **And** unit tests verify all F-key bindings

**Technical Notes:**
- Per UX: F-key navigation is primary
- Dual-path: keyboard + mouse both work
- Kill switch (F10) requires confirmation

---

## Epic 10: TUI Authorization & Control

**User Outcome:** Operator can respond to authorization requests, trigger kill switch, and adjust scope rules through the TUI.

**FRs Covered:** FR13, FR14, FR15, FR16, FR17, FR18, FR19, FR22, FR23, FR63
**NFRs Covered:** NFR2, NFR5

---

### Story 10.1: Authorization Request Modal

As an **operator**,
I want **an interruptive modal for authorization requests**,
So that **I notice and respond to lateral movement and scope expansion requests (FR13, FR14)**.

**Acceptance Criteria:**

- **Given** agent requests lateral movement or scope expansion
- **When** authorization request is created
- **Then** modal appears in TUI with context (target, action, risk)
- **And** modal is interruptive (pauses other actions until dismissed)
- **And** modal shows Y/N/M/S options (Yes/No/More info/Skip for now)
- **And** request delivery is <500ms (NFR5)
- **And** integration tests verify modal display

**Technical Notes:**
- Located in `tui/screens/authorization.py`
- Per UX: Authorization Flow with Y/N/M/S quick responses
- WebSocket push for real-time delivery

---

### Story 10.2: Authorization Response Handling

As an **operator**,
I want **to respond to authorization requests with Yes/No + constraints**,
So that **I control lateral movement with precision (FR15)**.

**Acceptance Criteria:**

- **Given** authorization modal is displayed
- **When** I press Y (Yes)
- **Then** authorization is granted
- **And** I can optionally add constraints (time limit, target limit)
- **When** I press N (No)
- **Then** authorization is denied
- **And** denial is logged with timestamp
- **When** I press M (More info)
- **Then** expanded context is shown (related findings, risk assessment)
- **And** response is logged to audit trail
- **And** integration tests verify all response paths

**Technical Notes:**
- Constraints: max_targets, time_window, specific_hosts_only
- Audit: `{timestamp, operator, decision, constraints, context}`

---

### Story 10.3: Pending Authorization Queue

As an **operator**,
I want **authorization requests to remain pending indefinitely**,
So that **nothing auto-approves or auto-denies without my decision (FR16)**.

**Acceptance Criteria:**

- **Given** authorization request is created
- **When** I don't respond
- **Then** request remains in pending queue
- **And** agent waits indefinitely for response
- **And** pending count is visible in TUI status bar
- **And** I can view all pending requests in queue view
- **And** queue is persisted across TUI detach/attach
- **And** safety tests verify no auto-approve/deny

**Technical Notes:**
- Per FR16: "no auto-approve/deny on timeout"
- Queue stored in daemon, synced to TUI on attach
- After 24h pending: engagement auto-pauses (FR64)

---

### Story 10.4: Kill Switch TUI Integration

As an **operator**,
I want **to trigger kill switch from TUI with <1s response**,
So that **I can halt all operations instantly (FR17, FR18, NFR2)**.

**Acceptance Criteria:**

- **Given** engagement is running
- **When** I press F10 or type `kill`
- **Then** confirmation modal appears
- **When** I confirm
- **Then** kill switch triggers in <1s
- **And** all agents halt immediately
- **And** TUI shows "ENGAGEMENT FROZEN" status
- **And** kill is logged to audit trail
- **And** safety tests verify <1s response under 10K agent load

**Technical Notes:**
- F10 = Kill Switch per UX
- Confirmation prevents accidental trigger
- Per NFR2: <1s halt all operations

---

### Story 10.5: Runtime Scope Adjustment

As an **operator**,
I want **to adjust scope validator rules at runtime**,
So that **I can expand or contract scope during engagement (FR19)**.

**Acceptance Criteria:**

- **Given** engagement is running
- **When** I access scope editor in TUI
- **Then** I can add/remove IP ranges, hostnames, ports
- **And** changes take effect immediately
- **And** agents receive updated scope rules
- **And** scope changes are logged to audit trail
- **And** I cannot remove active targets (must stop agents first)
- **And** production scope changes show 5-second countdown confirmation
- **And** scope changes have 10-second undo window after confirmation
- **And** "Undo" button appears during undo window with countdown
- **And** integration tests verify runtime scope update
- **And** integration tests verify countdown and undo functionality

**Technical Notes:**
- Located in `tui/screens/scope_editor.py`
- Live reload: new rules apply to next agent action
- Validation: CIDR, hostname, port range formats
- Per UX Design lines 438-439: countdown + undo window for safety

---

### Story 10.6: Situational Awareness Alerts

As an **operator**,
I want **situational awareness alerts for unexpected discoveries**,
So that **I'm informed of significant events (FR22)**.

**Acceptance Criteria:**

- **Given** agent discovers unexpected system/network
- **When** discovery doesn't match expected environment
- **Then** situational alert is raised
- **And** alert appears as interruptive modal
- **And** alert includes: discovery details, risk assessment, recommended action
- **And** I can respond with Continue/Stop/Notes
- **And** response is logged to audit trail
- **And** integration tests verify alert flow

**Technical Notes:**
- Located in `tui/widgets/situational_alert.py`
- Triggers: new subnet, domain controller, honeypot indicators
- Per FR22/23: interruptive modal alerts

---

### Story 10.7: Alert Response & Logging

As an **operator**,
I want **to respond to situational alerts with Continue/Stop + notes**,
So that **my decisions are documented (FR23)**.

**Acceptance Criteria:**

- **Given** situational alert is displayed
- **When** I respond with Continue
- **Then** engagement continues
- **And** I can add operator notes
- **When** I respond with Stop
- **Then** engagement pauses
- **And** reason is logged
- **And** all responses are logged to audit trail with timestamp
- **And** integration tests verify all response paths

**Technical Notes:**
- Audit format: `{timestamp, alert_type, operator_response, notes}`
- Stop = engagement.pause(), not kill

---

### Story 10.8: Deputy Operator Configuration

As an **operator**,
I want **to configure a Deputy Operator for authorization backup**,
So that **engagements can continue when I'm unavailable (FR63)**.

**Acceptance Criteria:**

- **Given** engagement configuration
- **When** I configure deputy_operator in engagement.yaml
- **Then** deputy receives authorization requests if primary doesn't respond in configured time
- **And** deputy can respond with same Y/N/M/S options
- **And** deputy responses are logged with deputy identifier
- **And** I can configure escalation_timeout (default: 30 minutes)
- **And** TUI shows which operator is currently primary
- **And** integration tests verify deputy escalation flow

**Technical Notes:**
- Config: `authorization.deputy_operator: "deputy@example.com"`
- Config: `authorization.escalation_timeout: 30m`
- Per FR63: "Deputy Operator role for authorization backup"

---

### Story 10.9: External Authorization Notification

As an **operator**,
I want **webhook/email notifications for pending authorization requests**,
So that **I can respond to critical authorizations when TUI is disconnected**.

**Acceptance Criteria:**

- **Given** engagement is running and TUI is detached
- **When** authorization request is pending for >5 minutes
- **Then** webhook fires to configured endpoint with request details
- **And** optional email notification is sent to configured address
- **And** notification includes: engagement_id, request_type, target, urgency
- **And** notification includes secure link to respond via API
- **Given** webhook endpoint is unavailable
- **When** notification attempt fails
- **Then** retry with exponential backoff (3 attempts)
- **And** failure is logged but engagement continues
- **And** integration tests verify webhook and email delivery
- **And** integration tests verify retry behavior

**Technical Notes:**
- Located in `core/notifications.py`
- Per UX Design line 519: ExternalNotifier widget
- Webhook: HTTP POST with JSON payload, configurable URL
- Email: SMTP configuration in `config.yaml`
- Config: `notifications.webhook_url`, `notifications.email`

---

## Epic 11: TUI Data & Strategy Display

**User Outcome:** Operator can browse exfiltrated data, view Director strategy, and manage RAG through dedicated TUI panels.

**FRs Covered:** FR42, FR85
**NFRs Covered:** NFR4

---

### Story 11.1: Director Ensemble Display (Three Perspectives)

As an **operator**,
I want **to view all three Director perspectives and synthesis**,
So that **I understand strategic reasoning (FR10)**.

**Acceptance Criteria:**

- **Given** Director has produced synthesis
- **When** I open Director panel (F5)
- **Then** I see tabbed/columned view: DeepSeek | Kimi K2 | MiniMax M2
- **And** I see synthesized unified strategy
- **And** each perspective shows: recommendations, rationale, confidence
- **And** MiniMax thinking tags are visible in debug mode
- **And** I can expand/collapse perspectives
- **And** integration tests verify display rendering

**Technical Notes:**
- Located in `tui/widgets/director_display.py`
- Live updates as Director re-plans
- Highlight consensus items

---

### Story 11.2: Exfiltrated Data Browser

As an **operator**,
I want **to browse all exfiltrated data via TUI**,
So that **I can access evidence without leaving the War Room (FR42)**.

**Acceptance Criteria:**

- **Given** engagement has exfiltrated data
- **When** I open Data Browser panel
- **Then** I see categorized list: credentials, documents, configs, other
- **And** I can search/filter by type, target, timestamp
- **And** I can view item details (preview for text, metadata for binary)
- **And** data is encrypted at rest (AES-256) — decrypted for display
- **And** integration tests verify data browser functionality

**Technical Notes:**
- Located in `tui/screens/data_browser.py`
- Per FR42: "access all exfiltrated data via TUI menu"
- No auto-delete per FR44

---

### Story 11.3: Data Export from TUI

As an **operator**,
I want **to export data items from TUI**,
So that **I can save evidence to local filesystem**.

**Acceptance Criteria:**

- **Given** data item is selected in browser
- **When** I choose Export
- **Then** file is decrypted and saved to specified path
- **And** export is logged to audit trail
- **And** I can export multiple items as archive
- **And** export preserves original filename and metadata
- **And** integration tests verify export functionality

**Technical Notes:**
- Export formats: original, JSON metadata, both
- Archive: ZIP with manifest.json

---

### Story 11.4: Manual Data Deletion

As an **operator**,
I want **to manually delete data items through TUI**,
So that **I can clean up sensitive data when required (FR45)**.

**Acceptance Criteria:**

- **Given** data item is selected
- **When** I choose Delete
- **Then** confirmation modal appears with warning
- **When** I confirm
- **Then** data is securely deleted (overwritten)
- **And** deletion is logged to audit trail
- **And** no auto-delete or scheduled deletion exists (FR44)
- **And** integration tests verify secure deletion

**Technical Notes:**
- Secure delete: overwrite with random data before unlink
- Per FR44/45: no auto-delete, operator manual only

---

### Story 11.5: RAG Management Panel

As an **operator**,
I want **to manage RAG updates and view corpus status**,
So that **I can keep knowledge bases current (FR85)**.

**Acceptance Criteria:**

- **Given** TUI is attached
- **When** I open RAG Management panel
- **Then** I see: total vectors, storage size, per-source stats
- **And** I see last update timestamp per source
- **And** "Update RAG" button triggers full refresh
- **And** I can update individual sources
- **And** ingestion progress shows in real-time
- **Given** TUI was detached and reattaches
- **When** events occurred during disconnect
- **Then** Catch-up Mode activates automatically
- **And** missed events are replayed chronologically in Strategy Stream
- **And** catch-up status shows "Catching up: X events" with progress
- **And** I can scrub through engagement history via timeline
- **And** integration tests verify RAG management
- **And** integration tests verify catch-up mode event replay

**Technical Notes:**
- Located in `tui/widgets/rag_manager.py`
- Per Story 6.11: TUI RAG widget
- Non-blocking update
- Catch-up Mode per UX Design lines 105, 114-115

---

### Story 11.6: Engagement Statistics Dashboard

As an **operator**,
I want **a statistics dashboard showing engagement metrics**,
So that **I can track progress at a glance**.

**Acceptance Criteria:**

- **Given** engagement is running
- **When** I view dashboard
- **Then** I see: agent count (active/idle/error), finding count (by severity), coverage %
- **And** I see: uptime, LLM calls made, tools executed
- **And** I see: emergence score (if calculated)
- **And** metrics update in real-time
- **And** integration tests verify dashboard accuracy

**Technical Notes:**
- Located in `tui/widgets/dashboard.py`
- Prometheus metrics as source
- Sparklines for trends

---

## Epic 12: Drop Box & C2 Operations

**User Outcome:** Operator can deploy cross-platform drop boxes, establish mTLS C2 channels, and enable WiFi pivot capabilities.

**FRs Covered:** FR24, FR25, FR26, FR27, FR28, FR29, FR30
**NFRs Covered:** NFR11, NFR17
**Errors Handled:** ERR4

---

### Story 12.1: mTLS C2 Server

As a **developer**,
I want **an mTLS WebSocket server for drop box C2**,
So that **drop boxes communicate securely over encrypted channels (FR24)**.

**Acceptance Criteria:**

- **Given** C2 server is configured
- **When** I start `c2.server.start()`
- **Then** server listens on port 8444 (configurable)
- **And** server requires mutual TLS (both ends present certificates)
- **And** server uses self-signed CA generated per engagement
- **And** server rejects connections without valid client cert
- **And** health endpoint at `/health/c2` reports status
- **And** integration tests verify mTLS handshake

**Technical Notes:**
- Located in `c2/server.py`
- Protocol: WSS (WebSocket Secure)
- Per architecture: mTLS is non-negotiable security requirement

---

### Story 12.2: C2 Message Protocol

As a **developer**,
I want **a structured C2 message protocol**,
So that **commands, results, and heartbeats have consistent format (FR24)**.

**Acceptance Criteria:**

- **Given** Story 12.1 is complete
- **When** C2 sends/receives messages
- **Then** messages follow schema: `{type, id, timestamp, payload, signature}`
- **And** type is one of: command, result, heartbeat
- **And** signature is HMAC-SHA256 of payload
- **And** invalid signatures are rejected and logged
- **And** unit tests verify protocol serialization/deserialization

**Technical Notes:**
- Located in `c2/protocol.py`
- Message format per PRD (lines 1714-1721)
- JSON encoding over WebSocket

---

### Story 12.3: Certificate Manager

As a **developer**,
I want **automated certificate generation and rotation**,
So that **C2 channels maintain security with short-lived certs (FR24)**.

**Acceptance Criteria:**

- **Given** Story 12.1 is complete
- **When** engagement starts
- **Then** CA is generated for this engagement
- **And** server cert is issued with 24h validity
- **And** client certs are issued for each drop box
- **And** certs auto-renew 1h before expiry
- **And** old certs are revoked on rotation
- **And** CRL is distributed to all clients
- **And** integration tests verify cert rotation

**Technical Notes:**
- Located in `c2/cert_manager.py`
- Use `cryptography` library
- Store CA key encrypted at rest

---

### Story 12.4: Heartbeat Monitoring

As an **operator**,
I want **heartbeat monitoring for drop box health**,
So that **I know immediately if C2 link is lost (FR24, NFR11)**.

**Acceptance Criteria:**

- **Given** drop box is connected
- **When** heartbeat is received every 5s
- **Then** connection status shows "healthy"
- **When** 3 heartbeats missed (15s)
- **Then** warning alert is raised
- **When** 6 heartbeats missed (30s)
- **Then** "C2 lost" status and critical alert
- **And** reconnection attempts begin automatically
- **And** integration tests verify heartbeat detection

**Technical Notes:**
- Heartbeat interval: 5s per architecture
- Alert thresholds: 3 (warning), 6 (critical)
- TUI HeartbeatIndicator widget displays status

---

### Story 12.5: Drop Box Go Module Structure

As a **developer**,
I want **Go module structure for cross-platform drop box**,
So that **drop boxes compile for Windows, Linux, macOS, Android (FR26)**.

**Acceptance Criteria:**

- **Given** Go development environment
- **When** I examine `dropbox/` directory
- **Then** I find: `main.go`, `c2/`, `wifi/`, `go.mod`
- **And** `make build-all` cross-compiles for: windows/amd64, linux/amd64, darwin/amd64, android/arm64
- **And** binaries are statically linked (no external deps)
- **And** binaries are stripped and compressed
- **And** integration tests verify each platform binary starts

**Technical Notes:**
- Located in `dropbox/` (Go)
- Use `GOOS` and `GOARCH` for cross-compilation
- Tier 1: Windows, Linux, macOS, Android
- Tier 2 (stretch): iOS

---

### Story 12.6: Drop Box mTLS Client

As a **drop box**,
I want **mTLS WebSocket client connecting to C2 server**,
So that **I can receive commands and send results securely (FR24)**.

**Acceptance Criteria:**

- **Given** drop box has client certificate
- **When** drop box starts
- **Then** it connects to C2 server via mTLS WebSocket
- **And** connection retries on failure (exponential backoff)
- **And** connection validates server certificate
- **And** send heartbeat every 5s
- **And** receive and execute commands
- **And** integration tests verify client-server handshake

**Technical Notes:**
- Located in `dropbox/c2/client.go`
- Embed client cert + CA in binary or load from config
- Reconnection: 1s, 2s, 4s, 8s, 16s, max 30s

---

### Story 12.7: WiFi Toolkit Wrapper

As a **drop box**,
I want **WiFi attack capabilities via toolkit wrappers**,
So that **I enable wireless pivot attacks (FR27, FR28)**.

**Acceptance Criteria:**

- **Given** Story 12.5 is complete
- **When** drop box receives WiFi command
- **Then** wrapper invokes appropriate tool: aircrack-ng, wifite, kismet
- **And** results are parsed and returned via C2
- **And** wrapper handles tool not installed gracefully
- **And** wireless interface is validated before attack
- **And** integration tests verify WiFi commands in cyber range

**Technical Notes:**
- Located in `dropbox/wifi/toolkit.go`
- Commands: scan, deauth, capture, crack
- Requires wireless adapter on drop box host

---

### Story 12.8: Natural Language Drop Box Setup

As an **operator**,
I want **natural language drop box configuration**,
So that **I can deploy drop boxes without technical commands (FR25)**.

**Acceptance Criteria:**

- **Given** TUI is attached
- **When** I type "Deploy a drop box on my Android phone at 192.168.1.100"
- **Then** Director interprets and generates deployment plan
- **And** I'm prompted to confirm target IP and platform
- **And** client cert is generated and displayed/downloadable
- **And** deployment instructions are shown for target platform
- **And** integration tests verify NL interpretation

**Technical Notes:**
- Located in `tui/screens/dropbox_wizard.py`
- Director uses context to infer platform from description
- Generate QR code for mobile deployment

---

### Story 12.9: Pre-Flight Protocol

As an **operator**,
I want **drop box pre-flight validation before operations**,
So that **I confirm the drop box is functional (FR29)**.

**Acceptance Criteria:**

- **Given** drop box connects to C2
- **When** pre-flight is initiated
- **Then** sequence runs: PING → EXEC_TEST → STREAM_TEST → NET_ENUM → READY
- **And** PING validates RTT latency
- **And** EXEC_TEST runs a benign command
- **And** STREAM_TEST validates bidirectional streaming
- **And** NET_ENUM discovers local network info
- **And** pre-flight results displayed in TUI
- **And** integration tests verify pre-flight sequence

**Technical Notes:**
- Per architecture (line 521)
- Timeout per step: 10s
- Fail on any step → drop box marked NOT READY

---

### Story 12.10: Drop Box Abort & Wipe

As an **operator**,
I want **to abort and wipe a drop box remotely**,
So that **I can clean up evidence if compromised (FR30, ERR4)**.

**Acceptance Criteria:**

- **Given** drop box is connected
- **When** I trigger abort from TUI
- **Then** abort command sent via C2
- **And** drop box stops all operations
- **And** drop box wipes: certs, logs, cached data
- **And** drop box self-destructs (process exits, optionally deletes binary)
- **And** abort is logged to audit trail
- **And** safety tests verify wipe completeness

**Technical Notes:**
- Per ERR4: "Log warning, attempt wipe command, mark lost"
- Wipe: overwrite sensitive files with random data
- No recovery after abort/wipe

---

### Story 12.11: Drop Box Reconnection Handling

As a **drop box**,
I want **automatic reconnection with state recovery**,
So that **temporary network outages don't lose context (NFR17)**.

**Acceptance Criteria:**

- **Given** drop box is connected and working
- **When** C2 connection is lost
- **Then** drop box attempts reconnection with exponential backoff
- **And** pending results are queued locally
- **And** on reconnection, queued results are sent
- **And** drop box ID persists across reconnections
- **And** reconnection timeout is 30s before full retry cycle
- **And** integration tests verify reconnection flow

**Technical Notes:**
- Local queue: max 100 messages or 10MB
- Queue persistence: in-memory (lost on process exit)
- Per NFR17: 30s reconnect timeout

---

## Epic 13: Evidence, Reporting & Audit

**User Outcome:** Operator can capture evidence, generate cryptographic proofs, export reports in multiple formats, and maintain tamper-evident audit trail.

**FRs Covered:** FR36, FR38, FR39, FR40, FR41, FR43, FR44, FR50, FR51, FR52, FR53, FR54
**NFRs Covered:** NFR15, NFR16

> [!NOTE]
> FR37 (video recording) deferred to v2.1.

---

### Story 13.1: Evidence File Storage

As a **developer**,
I want **secure evidence storage with SHA-256 manifests**,
So that **collected evidence has cryptographic integrity (FR36)**.

**Acceptance Criteria:**

- **Given** engagement is running
- **When** evidence file is captured (screenshot, log, loot)
- **Then** file is stored in `~/.cyber-red/evidence/{engagement_id}/`
- **And** file is encrypted at rest (AES-256)
- **And** SHA-256 hash is recorded in manifest.json
- **And** manifest includes: filename, hash, timestamp, source_agent
- **And** unit tests verify hash integrity

**Technical Notes:**
- Located in `storage/evidence.py`
- Per FR36: "Evidence files + SHA-256 manifest"
- Encryption key derived from engagement master key

---

### Story 13.2: Append-Only Audit Log

As a **developer**,
I want **an append-only audit log for all operator actions**,
So that **actions are tamper-evident and traceable (FR50, NFR15)**.

**Acceptance Criteria:**

- **Given** engagement is running
- **When** operator performs any action (approve, deny, kill, scope change)
- **Then** action is logged to append-only audit stream
- **And** log entries include: timestamp, operator, action, context, signature
- **And** log is stored in Redis Streams (consumer group)
- **And** log cannot be modified or deleted (append-only)
- **And** safety tests verify tamper resistance

**Technical Notes:**
- Located in `storage/audit.py`
- Redis Streams: `audit:{engagement_id}`
- Per NFR15: tamper-evident audit trail

---

### Story 13.3: SQLite Checkpoint Storage

As a **developer**,
I want **SQLite-based checkpoint storage for session persistence**,
So that **engagement state survives restarts (FR40)**.

**Acceptance Criteria:**

- **Given** engagement is running
- **When** checkpoint interval (60s) elapses or major state change occurs
- **Then** checkpoint is written to SQLite
- **And** SQLite uses WAL mode for concurrent reads
- **And** async write queue prevents blocking main thread
- **And** checkpoint includes: agent states, findings, scope, config
- **And** integration tests verify checkpoint restore

**Technical Notes:**
- Located in `storage/checkpoint.py`
- File: `~/.cyber-red/checkpoints/{engagement_id}.db`
- Per architecture: SQLite WAL mode, async queue

---

### Story 13.4: Markdown Report Generation

As an **operator**,
I want **Markdown report generation**,
So that **I can produce human-readable engagement summaries (FR38)**.

**Acceptance Criteria:**

- **Given** engagement has findings
- **When** I generate report with format=markdown
- **Then** report includes: executive summary, findings by severity, timeline
- **And** report uses Jinja2 template
- **And** report is saved to specified path
- **And** report includes cryptographic signature
- **And** unit tests verify template rendering

**Technical Notes:**
- Located in `templates/report_md.jinja2`
- Sections: Summary, Scope, Findings (Critical/High/Medium/Low), Timeline, Appendix

---

### Story 13.5: HTML Report with Screenshots

As an **operator**,
I want **HTML report with embedded screenshots**,
So that **I can share visual evidence (FR38)**.

**Acceptance Criteria:**

- **Given** Story 13.4 is complete
- **When** I generate report with format=html
- **Then** report includes all Markdown content rendered as HTML
- **And** screenshots are embedded as base64 images
- **And** report includes styling (dark theme to match TUI)
- **And** report is self-contained single HTML file
- **And** integration tests verify screenshot embedding

**Technical Notes:**
- Located in `templates/report_html.jinja2`
- Base64-encode images to avoid external dependencies
- CSS embedded in `<style>` block

---

### Story 13.6: SARIF Export

As a **developer**,
I want **SARIF format export for CI/CD integration**,
So that **findings integrate with GitHub/Azure DevOps (FR39)**.

**Acceptance Criteria:**

- **Given** engagement has findings
- **When** I export with format=sarif
- **Then** output conforms to SARIF v2.1.0 schema
- **And** each finding maps to a SARIF result
- **And** severity maps to SARIF level (error, warning, note)
- **And** output validates against sarif-schema-2.1.0.json
- **And** unit tests verify SARIF compliance

**Technical Notes:**
- Located in `templates/sarif.jinja2`
- Schema: https://docs.oasis-open.org/sarif/sarif/v2.1.0/
- Used for GitHub Security tab integration

---

### Story 13.7: STIX/TAXII Export

As a **developer**,
I want **STIX format export for threat intelligence sharing**,
So that **findings can be shared with STIX-compatible systems (FR39)**.

**Acceptance Criteria:**

- **Given** engagement has findings
- **When** I export with format=stix
- **Then** output conforms to STIX 2.1 specification
- **And** findings map to STIX objects (indicator, attack-pattern, vulnerability)
- **And** ATT&CK technique IDs map to STIX attack-pattern references
- **And** output validates against STIX schema
- **And** unit tests verify STIX compliance

**Technical Notes:**
- Located in `templates/stix.jinja2`
- Use `stix2` library for Python object generation
- Bundle exported as JSON

---

### Story 13.8: CSV/Excel Export

As an **operator**,
I want **CSV and Excel export for spreadsheet analysis**,
So that **I can manipulate findings in familiar tools (FR38)**.

**Acceptance Criteria:**

- **Given** engagement has findings
- **When** I export with format=csv or format=xlsx
- **Then** one row per finding with columns: severity, type, target, description, timestamp
- **And** CSV uses UTF-8 encoding with proper escaping
- **And** Excel includes formatted headers and auto-filter
- **And** unit tests verify export accuracy

**Technical Notes:**
- Use `pandas` or `openpyxl` for Excel generation
- Column order matches common import formats

---

### Story 13.9: Pre-Engagement Liability Waiver

As an **operator**,
I want **pre-engagement liability waiver workflow**,
So that **legal requirements are documented before engagement starts (FR54)**.

**Acceptance Criteria:**

- **Given** new engagement is being created
- **When** engagement init runs
- **Then** waiver prompt appears with legal text
- **And** operator must acknowledge (checkbox + signature)
- **And** acknowledgment is timestamped and logged to audit trail
- **And** engagement cannot start without waiver completion
- **And** waiver text is configurable per organization
- **And** integration tests verify waiver enforcement

**Technical Notes:**
- Located in `tui/screens/waiver.py`
- Per FR54: "Pre-engagement liability waiver flow"
- Store waiver hash in engagement config

---

### Story 13.10: Timestamp Integrity

As a **developer**,
I want **NTP-synced timestamps with crypto signatures**,
So that **evidence timestamps are legally defensible (FR51)**.

**Acceptance Criteria:**

- **Given** engagement is running
- **When** any event is logged (finding, action, checkpoint)
- **Then** timestamp is sourced from NTP-synced clock
- **And** timestamp includes timezone (UTC)
- **And** timestamp is cryptographically signed with engagement key
- **And** clock drift is monitored and alerted if >1s
- **And** unit tests verify timestamp signing

**Technical Notes:**
- Per architecture (line 542): "Timestamp integrity (NTP sync, crypto signatures)"
- Use `ntplib` for NTP verification
- Sign: `{timestamp, event_hash, signature}`

---

### Story 13.11: Evidence Chain of Custody

As an **operator**,
I want **chain of custody tracking for evidence**,
So that **evidence handling is auditable (FR52)**.

**Acceptance Criteria:**

- **Given** evidence file exists
- **When** evidence is accessed, exported, or modified
- **Then** access event is logged to audit trail
- **And** log includes: who, when, what action, file hash before/after
- **And** chain of custody can be reconstructed from audit log
- **And** evidence export includes chain of custody report
- **And** integration tests verify custody tracking

**Technical Notes:**
- Part of `storage/evidence.py`
- Per FR52: chain of custody for legal defensibility
- Export: include `chain_of_custody.json` in evidence ZIP

---

### Story 13.12: Engagement Summary Statistics

As an **operator**,
I want **engagement summary with key statistics**,
So that **I can quickly assess engagement outcomes (FR41)**.

**Acceptance Criteria:**

- **Given** engagement is complete or in progress
- **When** I request summary
- **Then** summary includes: duration, agent count, finding count by severity
- **And** summary includes: coverage %, tools executed, LLM calls
- **And** summary includes: emergence score (if calculated)
- **And** summary is available in all report formats
- **And** unit tests verify statistic accuracy

**Technical Notes:**
- Aggregated from Prometheus metrics + SQLite data
- Per FR41: "Summary with key statistics"

---

## Epic 14: External API & Advanced Governance

**User Outcome:** External systems can integrate via REST/WebSocket API; advanced authorization governance with deputy operator and auto-pause.

**FRs Covered:** FR48, FR49, FR63, FR64
**NFRs Covered:** NFR9

---

### Story 14.1: FastAPI Application Foundation

As a **developer**,
I want **a FastAPI-based REST API server**,
So that **external systems can integrate with Cyber-Red (FR48)**.

**Acceptance Criteria:**

- **Given** API server is configured
- **When** I start `api.server.run()`
- **Then** server listens on port 8443 (configurable)
- **And** server uses HTTPS with TLS certificates
- **And** server exposes OpenAPI spec at `/docs`
- **And** health endpoint at `/health` returns status
- **And** unit tests verify server startup

**Technical Notes:**
- Located in `api/server.py`
- FastAPI with uvicorn
- TLS required (no HTTP)

---

### Story 14.2: API Token Authentication

As a **developer**,
I want **token-based API authentication**,
So that **only authorized systems can access the API (FR48)**.

**Acceptance Criteria:**

- **Given** Story 14.1 is complete
- **When** request includes valid Bearer token
- **Then** request is authenticated
- **When** request lacks token or token is invalid
- **Then** 401 Unauthorized response
- **And** tokens are generated via CLI or TUI
- **And** tokens have configurable expiration
- **And** tokens can be revoked
- **And** integration tests verify auth flow

**Technical Notes:**
- Located in `api/auth.py`
- JWT tokens with configurable TTL
- Store token metadata in SQLite

---

### Story 14.3: Engagement CRUD Endpoints

As an **external system**,
I want **REST endpoints for engagement management**,
So that **I can create, query, and control engagements (FR48)**.

**Acceptance Criteria:**

- **Given** Story 14.2 is complete
- **When** I POST to `/engagements`
- **Then** new engagement is created with provided config
- **When** I GET `/engagements`
- **Then** list of engagements is returned
- **When** I GET `/engagements/{id}`
- **Then** engagement details are returned
- **When** I POST `/engagements/{id}/start`
- **Then** engagement starts (if not already running)
- **When** I POST `/engagements/{id}/stop`
- **Then** engagement stops gracefully
- **And** integration tests verify all CRUD operations

**Technical Notes:**
- Located in `api/routes/engagements.py`
- Pydantic schemas in `api/schemas.py`

---

### Story 14.4: Findings Query Endpoint

As an **external system**,
I want **REST endpoints to query findings**,
So that **I can retrieve engagement results programmatically (FR48)**.

**Acceptance Criteria:**

- **Given** Story 14.2 is complete
- **When** I GET `/engagements/{id}/findings`
- **Then** findings list is returned
- **And** I can filter by severity (critical, high, medium, low)
- **And** I can filter by type (recon, exploit, postex)
- **And** I can paginate with limit/offset
- **And** response includes total count
- **And** integration tests verify query and filters

**Technical Notes:**
- Located in `api/routes/findings.py`
- Default limit: 100, max limit: 1000

---

### Story 14.5: WebSocket Real-Time Stream

As an **external system**,
I want **WebSocket endpoint for real-time updates**,
So that **I can receive findings and events as they happen (FR49)**.

**Acceptance Criteria:**

- **Given** Story 14.1 is complete
- **When** I connect to `/ws/engagements/{id}/stream`
- **Then** WebSocket connection is established
- **And** I receive real-time: findings, agent status changes, alerts
- **And** connection requires authenticated token
- **And** heartbeat keeps connection alive (30s interval)
- **And** integration tests verify streaming

**Technical Notes:**
- Located in `api/routes/stream.py`
- FastAPI WebSocket support
- JSON message format matching C2 protocol

---

### Story 14.6: API Rate Limiting

As a **developer**,
I want **rate limiting on API endpoints**,
So that **API abuse is prevented (NFR9)**.

**Acceptance Criteria:**

- **Given** Story 14.1 is complete
- **When** client exceeds rate limit (default: 100 req/min)
- **Then** 429 Too Many Requests response
- **And** response includes Retry-After header
- **And** rate limits are configurable per endpoint
- **And** rate limits are per-token (not global)
- **And** unit tests verify rate limiting

**Technical Notes:**
- Use `slowapi` or similar
- Config: `api.rate_limit: 100/minute`

---

### Story 14.7: Pydantic Request/Response Schemas

As a **developer**,
I want **Pydantic schemas for all API models**,
So that **requests and responses are validated and documented**.

**Acceptance Criteria:**

- **Given** API endpoints exist
- **When** request body doesn't match schema
- **Then** 422 Validation Error with details
- **And** all endpoints have typed request/response models
- **And** schemas generate accurate OpenAPI spec
- **And** unit tests verify schema validation

**Technical Notes:**
- Located in `api/schemas.py`
- Use Pydantic v2 for performance
- Include examples in schemas for docs

---

### Story 14.8: Deputy Operator API Support

As a **developer**,
I want **API support for deputy operator role**,
So that **authorization can be delegated via API (FR63)**.

**Acceptance Criteria:**

- **Given** Story 10.8 (Deputy Operator) is complete
- **When** primary operator doesn't respond to auth request
- **Then** API can route to deputy operator
- **And** deputy can respond via API endpoint
- **When** I GET `/engagements/{id}/auth/pending`
- **Then** pending authorization requests are returned
- **When** I POST `/engagements/{id}/auth/{request_id}/respond`
- **Then** authorization response is processed
- **And** integration tests verify deputy API flow

**Technical Notes:**
- Located in `api/routes/auth.py`
- Deputy escalation uses same logic as TUI

---

### Story 14.9: Auto-Pause After 24h Pending

As a **developer**,
I want **automatic engagement pause after 24h pending authorization**,
So that **engagements don't run indefinitely without oversight (FR64)**.

**Acceptance Criteria:**

- **Given** authorization request is pending
- **When** 24 hours elapse without response
- **Then** engagement automatically pauses
- **And** pause is logged to audit trail
- **And** operator is notified (if TUI attached)
- **And** API returns paused status
- **And** operator can resume after responding to pending auth
- **And** safety tests verify auto-pause

**Technical Notes:**
- Timer tracked in daemon
- Per FR64: "Auto-pause after 24h pending authorization"
- Resume: respond to all pending auth, then `/engagements/{id}/resume`

---

### Story 14.10: API Health & Metrics Endpoint

As an **external system**,
I want **health and metrics endpoints**,
So that **I can monitor API availability**.

**Acceptance Criteria:**

- **Given** Story 14.1 is complete
- **When** I GET `/health`
- **Then** response includes: status, uptime, version
- **When** I GET `/metrics`
- **Then** Prometheus-format metrics are returned
- **And** metrics include: request count, latency, error rate
- **And** health endpoint works without auth (for load balancers)
- **And** unit tests verify health response

**Technical Notes:**
- Located in `api/routes/health.py`
- Prometheus middleware for metrics
- Health: 200 OK or 503 Service Unavailable

---

### Story 14.11: Distributed Tracing (OpenTelemetry)

As a **developer**,
I want **OpenTelemetry distributed tracing for agent actions**,
So that **complex multi-agent workflows can be traced and debugged (OBS8)**.

**Acceptance Criteria:**

- **Given** tracing is enabled in config
- **When** agent action executes
- **Then** trace ID is generated and propagated across services
- **And** spans include: agent_id, action_type, target, duration_ms
- **And** spans include: parent span for causal chain tracing
- **When** Director Ensemble queries LLMs
- **Then** spans capture: model, latency, token_count
- **And** traces are exportable to Jaeger/Zipkin/OTLP endpoints
- **And** trace sampling rate is configurable (default: 10%)
- **And** tracing disabled by default (opt-in for performance)
- **And** integration tests verify trace propagation

**Technical Notes:**
- Located in `monitoring/tracing.py`
- Per PRD OBS8 (line 1611): "Distributed tracing, OpenTelemetry, Trace ID per agent action"
- Use `opentelemetry-sdk` and `opentelemetry-exporter-*`
- Config: `observability.tracing.enabled`, `observability.tracing.endpoint`

---

## Epic 15: End-to-End Integration & Validation

**User Outcome:** Complete engagement workflow validated end-to-end; all hard gates pass; system ready to ship.

**FRs Covered:** All (validation)
**NFRs Covered:** NFR3, NFR10, NFR19-NFR23, NFR35, NFR36, NFR37

> [!CAUTION]
> **SHIP GATE EPIC:** All tests in this epic MUST pass before v2.0 can ship.

---

### Story 15.1: Full Engagement E2E Test

As a **developer**,
I want **a complete engagement E2E test in cyber range**,
So that **the full kill chain is validated (NFR10)**.

**Acceptance Criteria:**

- **Given** cyber range with vulnerable targets is running
- **When** E2E test executes
- **Then** engagement completes full kill chain: recon → exploit → postex
- **And** findings are discovered and published
- **And** Director synthesizes and publishes strategy
- **And** evidence is captured and stored
- **And** report is generated successfully
- **And** test completes in <30 minutes
- **And** e2e tests validate complete workflow

**Technical Notes:**
- Located in `tests/e2e/test_full_engagement.py`
- Uses cyber range fixtures from Epic 0
- Complete: start → discover → exploit → report → stop

---

### Story 15.2: 100-Agent Scale CI Gate

As a **developer**,
I want **a 100-agent scale test as CI gate**,
So that **basic scaling is validated on every commit (NFR19)**.

**Acceptance Criteria:**

- **Given** CI pipeline runs
- **When** 100-agent scale test executes
- **Then** 100 agents spawn successfully
- **And** agents communicate via stigmergic signals
- **And** findings are published and aggregated
- **And** test completes in <10 minutes
- **And** CI fails if test fails

**Technical Notes:**
- Located in `tests/e2e/test_100_agent_scale.py`
- Runs on every PR merge
- Lighter than full 10K test

---

### Story 15.3: 10K Agent Stress Test

As a **developer**,
I want **a 10K agent stress test for ceiling discovery**,
So that **system limits are known and documented (NFR6, NFR20)**.

**Acceptance Criteria:**

- **Given** dedicated test environment
- **When** 10K agent stress test executes
- **Then** agents spawn to hardware limit or 10K (whichever first)
- **And** degradation curve is captured (agent count vs response time)
- **And** memory per agent is recorded
- **And** ceiling is documented in test output
- **And** graceful degradation is verified (no crashes)
- **And** e2e tests capture stress metrics

**Technical Notes:**
- Located in `tests/e2e/test_10k_stress.py`
- Run manually or nightly (too long for CI gate)
- Output: JSON with degradation curve data

---

### Story 15.4: Kill Switch <1s Validation

As a **developer**,
I want **kill switch to halt all agents in <1s under load**,
So that **safety requirement is validated (NFR2, NFR21)**.

**Acceptance Criteria:**

- **Given** 100+ agents are running
- **When** kill switch is triggered
- **Then** all agents halt in <1s
- **And** no agent actions execute after kill
- **And** Redis pub/sub, SIGTERM, and Docker API paths are all functional
- **And** test measures actual halt latency
- **And** safety tests verify <1s under load

**Technical Notes:**
- Located in `tests/safety/test_kill_switch_latency.py`
- Measure: timestamp of kill → timestamp of last agent halt
- Must pass at 100, 1000, and 5000 agents

---

### Story 15.5: Emergence >20% Validation

As a **developer**,
I want **emergence score validated >20%**,
So that **stigmergic coordination proves value (NFR35)**.

**Acceptance Criteria:**

- **Given** emergence test framework (Story 7.9) is complete
- **When** emergence validation runs
- **Then** isolated run executes without stigmergic signals
- **And** stigmergic run executes with full coordination
- **And** novel attack chains are calculated
- **And** emergence score = novel / total > 0.20
- **And** CI fails if emergence < 20%

**Technical Notes:**
- Located in `tests/emergence/test_emergence_gate.py`
- Per Story 7.14
- HARD GATE: system cannot ship without passing

---

### Story 15.6: Causal Chain 3+ Hop Validation

As a **developer**,
I want **at least one 3+ hop causal chain validated**,
So that **deep coordination is proven (NFR36)**.

**Acceptance Criteria:**

- **Given** emergence test runs
- **When** causal chains are analyzed
- **Then** at least one chain has 3+ hops
- **And** hop sequence is logged: Finding → Action → Finding → Action
- **And** each hop cites decision_context from previous
- **And** CI fails if no 3+ hop chain exists

**Technical Notes:**
- Located in `tests/emergence/test_causal_depth.py`
- Per Story 7.11
- HARD GATE: proves agents build on each other's work

---

### Story 15.7: 100% decision_context Validation

As a **developer**,
I want **100% of agent actions to include decision_context**,
So that **emergence is fully traceable (NFR37)**.

**Acceptance Criteria:**

- **Given** engagement runs with agents
- **When** agent actions are analyzed
- **Then** 100% of actions have non-empty decision_context
- **And** decision_context references valid signal IDs
- **And** CI fails if any action lacks decision_context

**Technical Notes:**
- Located in `tests/emergence/test_decision_context.py`
- Per Story 7.8
- HARD GATE: enables causality tracking

---

### Story 15.8: v1 Baseline Comparison (10x Faster)

As a **developer**,
I want **v2 compared to v1 baseline for 10x improvement**,
So that **performance claims are validated (NFR3)**.

**Acceptance Criteria:**

- **Given** v1 baseline data exists
- **When** v2 performance test runs
- **Then** engagement completion time is compared
- **And** v2 time < v1 time / 10 (10x faster)
- **And** comparison is documented with evidence
- **When** v1 baseline data does not exist
- **Then** test is skipped with warning (requires manual benchmark)

**Technical Notes:**
- Located in `tests/e2e/test_v1_comparison.py`
- Baseline file: `tests/fixtures/v1_baseline.json`
- NFR3: "10x faster than v1"

---

### Story 15.9: TUI <100ms Responsiveness

As a **developer**,
I want **TUI responsiveness validated <100ms**,
So that **operator experience is smooth (NFR4, NFR22)**.

**Acceptance Criteria:**

- **Given** TUI is attached to engagement with 1000 agents
- **When** operator performs actions (scroll, click, type)
- **Then** UI responds in <100ms
- **And** agent list render time is <100ms
- **And** finding stream updates in <500ms
- **And** integration tests verify TUI latency

**Technical Notes:**
- Located in `tests/integration/test_tui_latency.py`
- Per NFR4: <100ms render with 10K agents
- Measure: action timestamp → render complete timestamp

---

### Story 15.10: Pause/Resume <1s Validation

As a **developer**,
I want **pause/resume to complete in <1s**,
So that **operator control is responsive (NFR23)**.

**Acceptance Criteria:**

- **Given** engagement is running
- **When** operator pauses
- **Then** all agents pause in <1s
- **When** operator resumes
- **Then** all agents resume in <1s
- **And** no actions execute between pause command and halt
- **And** safety tests verify pause/resume latency

**Technical Notes:**
- Located in `tests/safety/test_pause_resume.py`
- Measure: command → all agents in PAUSED/RUNNING state

---

### Story 15.11: Attach <2s Validation

As a **developer**,
I want **TUI attach to complete in <2s**,
So that **operator can quickly reconnect (NFR32)**.

**Acceptance Criteria:**

- **Given** daemon is running with engagement
- **When** TUI attaches
- **Then** TUI is operational in <2s
- **And** state sync completes during attach
- **And** test measures actual attach latency
- **And** safety tests verify <2s attach

**Technical Notes:**
- Located in `tests/integration/test_attach_latency.py`
- Per NFR32: <2s from command to operational TUI

---

### Story 15.12: Multi-Engagement Isolation

As a **developer**,
I want **multiple engagements to run in complete isolation**,
So that **cross-engagement data leakage is impossible**.

**Acceptance Criteria:**

- **Given** two engagements are running simultaneously
- **When** agents execute in both
- **Then** findings are isolated by engagement_id
- **And** stigmergic signals are isolated by engagement_id
- **And** evidence is stored in separate directories
- **And** one engagement's kill doesn't affect the other
- **And** safety tests verify complete isolation

**Technical Notes:**
- Located in `tests/safety/test_multi_engagement_isolation.py`
- Redis key prefix: `{engagement_id}:`
- Critical for multi-client scenarios

---

### Story 15.13: All Safety Tests Gate

As a **developer**,
I want **all safety tests to pass as ship gate**,
So that **no safety regression ships**.

**Acceptance Criteria:**

- **Given** CI runs
- **When** safety test suite executes
- **Then** all `tests/safety/*.py` tests pass
- **And** fail-closed scope validation passes
- **And** kill switch tests pass
- **And** credential protection tests pass
- **And** CI fails if any safety test fails

**Technical Notes:**
- `pytest tests/safety/ -v`
- HARD GATE: zero tolerance for safety failures

---

### Story 15.14: 100% Coverage Gate

As a **developer**,
I want **100% unit + integration coverage as ship gate**,
So that **code quality is maintained**.

**Acceptance Criteria:**

- **Given** CI runs
- **When** coverage is calculated
- **Then** unit test coverage is ≥90%
- **And** integration test coverage is ≥80%
- **And** critical paths (scope, kill, auth) are 100% covered
- **And** coverage report is generated
- **And** CI fails if coverage drops below thresholds

**Technical Notes:**
- `pytest --cov=src --cov-report=html`
- Store coverage in artifacts

---

### Story 15.15: Chaos Engineering Tests

As a **developer**,
I want **chaos engineering tests for resilience validation**,
So that **system handles failures gracefully**.

**Acceptance Criteria:**

- **Given** engagement is running
- **When** Redis master fails (network partition simulated)
- **Then** system fails over to new master within failover_timeout
- **And** no data loss for in-flight messages
- **When** LLM provider becomes unavailable
- **Then** Director uses fallback per NFR29
- **When** agent container is killed unexpectedly
- **Then** replacement spawns per ERR5
- **And** chaos tests document recovery times

**Technical Notes:**
- Located in `tests/chaos/`
- Use toxiproxy or similar for network faults
- Run manually or nightly (not CI gate)

---

### Story 15.16: Load Tests (Redis/LLM/API)

As a **developer**,
I want **load tests for critical subsystems**,
So that **throughput limits are known**.

**Acceptance Criteria:**

- **Given** load test environment
- **When** Redis pub/sub load test runs
- **Then** messages/sec throughput is measured at 100, 1K, 10K agents
- **When** LLM Gateway load test runs
- **Then** requests/sec and queue depth are measured
- **When** API load test runs
- **Then** requests/sec at rate limit boundary is verified
- **And** results are documented with degradation curves

**Technical Notes:**
- Located in `tests/load/`
- Use locust or k6 for HTTP load testing
- Redis: measure pub/sub latency percentiles (p50, p95, p99)











