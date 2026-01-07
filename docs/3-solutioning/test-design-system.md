# System-Level Test Design

## Testability Assessment

- **Controllability**: **PASS**
  - **Strengths**: The architecture relies on standard, seedable data stores (Redis for state/signals, SQLite for persistence). The decision to use `testcontainers-python` for the Kali layer provides excellent controllability, allowing individual tool execution in isolated, disposable environments.
  - **Notes**: `kali_execute()` wrapping standard CLI tools means we can easily mock inputs/outputs or use real tools in consistent containerized environments.

- **Observability**: **PASS**
  - **Strengths**: `structlog` provides structured JSON logging with context binding (agent_id, etc.) which is critical for debugging 10,000 parallel agents. Metrics (Prometheus) are planned.
  - **Notes**: Stigmergic signal tracing (`decision_context`) is a built-in observability mechanism that will simplify emergence validation.

- **Reliability**: **PASS**
  - **Strengths**: Architecture is async-native (Python 3.11+, asyncio) with strict isolation rules (Docker per engagement/tests).
  - **Notes**: Stateless agent design (checkpointed to SQLite) simplifies test setups and tear-downs.

## Architecturally Significant Requirements (ASRs)

These requirements drive the testing strategy due to their high risk and complexity:

| ASR ID | Requirement | Risk Score | Category | Rationale |
|--------|-------------|------------|----------|-----------|
| **ASR-01** | **10,000+ Agent Scale** (NFR6) | **9** (High) | **PERF** | Hardware-bounded scaling is unproven at this magnitude. Requires specialized stress testing on high-spec runners. |
| **ASR-02** | **<1s Kill Switch** (NFR2) | **9** (Critical) | **SEC** | Safety-critical control. Failure here could cause uncontrolled damage. Must be tested under max load. |
| **ASR-03** | **Emergence >20%** (NFR35) | **6** (High) | **TECH** | The core innovation claim. Hard to measure deterministically. Requires a baseline comparison framework. |
| **ASR-04** | **100% Coverage / No Mocks** (NFR19/20) | **6** (Medium) | **MAINT** | "No mocked tests" for adapters implies heavy integration testing load. CI duration risk. |
| **ASR-05** | **Evidence Integrity** (NFR15) | **6** (High) | **SEC** | Chain-of-custody relies on correct crypto implementation. Testing must verify signature validity against tamper attempts. |

## Test Levels Strategy

Given the "Ability, not tool" positioning and high criticality:

- **Unit Tests (60%)**
  - **Focus**: Business logic, Stigmergic routing rules, Scope validation (Safety), Protocol parsing.
  - **Rationale**: Fast feedback loops are essential for the complex logic within the Director and Agents. Strict TDD here.

- **Integration Tests (30%)**
  - **Focus**: `kali_execute()` wrapper (real containers), Redis Pub/Sub mechanics, Checkpoint/Resume persistence, API endpoints.
  - **Rationale**: The interactions between agents and the infrastructure (Redis/Docker) are the primary failure points. `testcontainers` makes this viable.

- **E2E / Cyber Range Tests (10%)**
  - **Focus**: Full kill chains (Recon -> Exploit -> Post-Ex), Emergence validation, Multi-agent coordination, Scale stress tests.
  - **Rationale**: Validates the "emergent behavior" and "mission completion" goals which cannot be seen in isolated components.

## NFR Testing Approach

- **Security (SEC)**
  - **Auth/Authz**: Automated tests for TUI/API auth triggers.
  - **Scope Enforcement**: Property-based testing to throw millions of random targets at the `ScopeValidator` to ensure it never fails open.
  - **Integrity**: Validation of SHA-256 signatures and audit stream consistency.

- **Performance (PERF)**
  - **Scale Testing**: Custom `scale_test.py` harnessing 1,000 -> 5,000 -> 10,000 minimal-footprint agents (sleeping/echoing) to measure coordination overhead (Redis CPU, Latency).
  - **Tools**: Custom asyncio harness + Prometheus metrics.

- **Reliability (REL)**
  - **Chaos Testing**: Terminate Redis Sentinel node mid-operation; Verify system degrades/recovers. Kill Daemon process; verify session resume.
  - **Latency**: Measure TUI response time under load via synthetic events.

- **Maintainability (MAINT)**
  - **Strict Gates**: 100% Coverage enforced by CI.
  - **Structure**: Tests mirror source directory. `tests/fixtures` heavily used for consistent environments.

## Test Environment Requirements

To support "No Mocks" and "Simulated 10K agents":

1.  **CI Runner**: Self-hosted GitHub Action Runner (High CPU/RAM). Standard Cloud runners will choke on 10K asyncio tasks + Docker.
2.  **Cyber Range**: Docker Compose environment (DVWA, Metasploitable-like targets) used in E2E tests.
3.  **Kali Image**: Local registry mirror for `kalilinux/kali-linux-docker` to avoid pull rate limits and speed up tests.

## Testability Concerns

1.  **CI Resource Limits**: simulating 10,000 agents, even lightweight ones, requires significant RAM and file descriptors. Standard CI runners may fail, leading to flaky "Performance" failures.
    *   *Mitigation*: Use a dedicated large runner for the "Scale Test" workflow (scheduled weekly), use smaller scale (100-1000) for PR checks.

2.  **Kali Container Latency**: Spinning up a real Kali container for *every* integration test is slow.
    *   *Mitigation*: Use shared container pool for integration tests (clean up state between runs) or use "exec" into persistent container rather than "run new container".

## Recommendations for Sprint 0

1.  **Infrastructure**: Provision the Self-Hosted Runner immediately.
2.  **Framework**: Initialize `tests/` structure with `conftest.py` setting up the `kali_container` fixture (optimized for reuse).
3.  **Baseline**: Create the `scale_test` harness early to establish the "Empty Agent" performance baseline before adding logic.
