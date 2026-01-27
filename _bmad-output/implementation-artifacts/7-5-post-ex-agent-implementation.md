# Story 7.5: PostExAgent Implementation

**Status:** done
**Estimation:** 8 story points
**Epic:** 7 - Agent Framework & Stigmergic Coordination
**Priority:** P0 - Critical Hard Gate

---

## Story

As a **developer**,
I want **a post-exploitation agent for lateral movement and persistence**,
So that **the swarm can achieve deeper objectives (FR2)**.

---

## ⚠️ CRITICAL REQUIREMENTS - HARD GATE

> **THIS STORY IS A CRITICAL HARD GATE FOR EPIC 7**
>
> **NFR19 & NFR20: 100% Test Coverage Required**
> - Unit tests: 100% line coverage
> - Integration tests: 100% branch coverage
> - NO CODE SHIPS WITHOUT COMPLETE TEST COVERAGE
>
> **STRICT TDD METHODOLOGY REQUIRED**
> - Phase 1 (RED): Write ALL failing tests FIRST
> - Phase 2 (GREEN): Implement MINIMAL code to pass tests
> - Phase 3 (REFACTOR): Optimize while maintaining 100% coverage
>
> **NFR37: 100% decision_context Population**
> - Every PostExAgent action MUST include decision_context
> - Tracks stigmergic signals that influenced decisions
> - Required for emergence validation (NFR35-37)
>
> **FR13: Authorization Required for Lateral Movement**
> - PostExAgent MUST request authorization before lateral movement
> - Agent enters WAITING_AUTHORIZATION state until response
> - Implements Story 7.16 authorization handling pattern
>
> **RAG Escalation After 3+ Failures (Story 6.10)**
> - PostExAgent MUST integrate AgentRAGEscalator
> - Escalate to RAG when post-ex attempts fail 3+ times
> - Record failures and successes for threshold tracking

---

## Acceptance Criteria

### AC1: PostExAgent Extends StigmergicAgent
- **Given** Story 7.1 (StigmergicAgent base class) is complete
- **When** PostExAgent is instantiated
- **Then** PostExAgent extends `StigmergicAgent` from `agents/base.py`
- **And** PostExAgent inherits all stigmergic lifecycle hooks
- **And** PostExAgent inherits self-throttling from Story 7.2

### AC2: Compromised System Access Initialization
- **Given** a compromised target with shell/credential access (from ExploitAgent findings)
- **When** PostExAgent receives target assignment
- **Then** agent validates target against scope (Story 1.8)
- **And** agent parses access credentials/shell data from stigmergic signals
- **And** agent logs spawn event with `agent_id`, `engagement_id`, `target`, `access_type`
- **And** agent initializes post-exploitation task queue

### AC3: Post-Exploitation Enumeration via kali_execute()
- **Given** PostExAgent has access to compromised system
- **When** agent performs post-exploitation enumeration
- **Then** agent uses `kali_execute()` from Story 4.3
- **And** agent generates appropriate bash/Python code for tools
- **And** tools used include: linpeas, winpeas, bloodhound, mimikatz, lazagne
- **And** scope validation occurs BEFORE every tool execution
- **And** agent discovers: credentials, privileges, network shares, domain info

### AC4: Privilege Escalation Attempts
- **Given** PostExAgent has standard user access
- **When** agent detects privilege escalation opportunity
- **Then** agent attempts escalation using appropriate tools
- **And** agent uses: linpeas/winpeas for vuln detection, known exploits for escalation
- **And** successful escalation is logged with evidence
- **And** escalation findings published to `findings:{target_hash}:postex`

### AC5: Lateral Movement Discovery and Authorization (FR13)
- **Given** PostExAgent discovers lateral movement opportunity
- **When** agent prepares lateral movement action
- **Then** agent publishes authorization request to `authorization:{request_id}`
- **And** agent enters `WAITING_AUTHORIZATION` state
- **And** agent waits indefinitely for response (FR16 - no auto-deny)
- **When** operator grants authorization
- **Then** agent proceeds with lateral movement
- **When** operator denies authorization
- **Then** agent logs denial and selects alternative action
- **And** authorization outcome logged in `decision_context`

### AC6: Stigmergic Finding Publication
- **Given** post-exploitation succeeds
- **When** finding is processed
- **Then** finding is published to `findings:{target_hash}:postex`
- **And** finding includes all 10 required fields per `core/models.py`
- **And** finding signature is generated (HMAC-SHA256)
- **And** credential findings trigger swarm-wide notification
- **And** other agents can subscribe and react to finding

### AC7: Intelligence Layer Integration (Epic 5)
- **Given** PostExAgent discovers services or credentials
- **When** agent prepares escalation/lateral movement
- **Then** agent queries `IntelligenceAggregator` for technique options
- **And** agent receives prioritized results (CISA KEV > Critical CVE > High CVE)
- **And** agent selects highest-priority technique with available path
- **And** intelligence query is non-blocking (5s timeout per source)

### AC8: RAG Escalation After 3+ Failures (Story 6.10)
- **Given** post-ex attempt fails
- **When** failure count for target/technique reaches 3
- **Then** agent calls `AgentRAGEscalator.escalate()` with context
- **And** agent receives alternative methodologies from RAG (LOLBAS, GTFOBins, HackTricks)
- **And** agent selects new technique from RAG results
- **And** agent logs escalation event with `decision_context`

### AC9: Decision Context Logging (FR62, NFR37)
- **Given** any PostExAgent action
- **When** action is executed
- **Then** action logs `decision_context` field
- **And** decision_context contains IDs of influencing stigmergic signals
- **And** decision_context includes intelligence source IDs
- **And** decision_context includes authorization request/response IDs
- **And** 100% of actions have non-empty decision_context (verifiable)

### AC10: Director Strategy Subscription
- **Given** PostExAgent spawns
- **When** initialization completes
- **Then** agent subscribes to `strategies:{engagement_id}` channel
- **And** agent can receive Director Ensemble guidance
- **And** agent adapts post-ex strategy based on directives (stealth vs aggressive)

### AC11: Integration Tests in Cyber Range
- **Given** cyber range environment (Story 0.6)
- **When** integration tests run
- **Then** PostExAgent performs real post-exploitation against compromised targets
- **And** discovers expected findings from `expected-findings.json`
- **And** tests verify stigmergic signal propagation
- **And** tests verify authorization flow
- **And** tests verify RAG escalation flow

### AC12: 100% Test Coverage
- **Given** PostExAgent implementation is complete
- **When** `pytest --cov` runs
- **Then** unit test coverage is 100% for `agents/postex.py`
- **And** integration test coverage is 100%
- **And** all edge cases and error paths are tested

---

## Tasks / Subtasks

### Phase 1: RED - Write Failing Tests First (TDD)

> **⚠️ MANDATORY: All tests MUST be written and fail BEFORE any implementation**

#### Task 1: Create Test File Structure (AC: #12)
- [ ] 1.1 Create `tests/unit/agents/test_postex_agent.py`
- [ ] 1.2 Create `tests/integration/agents/test_postex_agent_integration.py`
- [ ] 1.3 Create test fixtures in `tests/fixtures/postex/`
- [ ] 1.4 Verify tests fail with `ModuleNotFoundError` (expected)

#### Task 2: Write Unit Tests for PostExAgent Class (AC: #1, #2)
- [ ] 2.1 Test `PostExAgent` extends `StigmergicAgent`
- [ ] 2.2 Test `__init__` requires `target`, `agent_id`, `engagement_id`, `event_bus`, `access_data`
- [ ] 2.3 Test `__init__` validates target against scope
- [ ] 2.4 Test `__init__` raises `ScopeViolationError` for out-of-scope target
- [ ] 2.5 Test spawn initializes post-ex task queue
- [ ] 2.6 Test spawn logs correctly with structlog (including access_type)
- [ ] 2.7 Test inherits self-throttling from Story 7.2
- [ ] 2.8 Test access_data parsing from stigmergic signals (shell, credentials, session)

#### Task 3: Write Unit Tests for Enumeration Execution (AC: #3)
- [ ] 3.1 Test `execute_postex()` calls `kali_execute()` with correct commands
- [ ] 3.2 Test linpeas command generation for Linux enumeration
- [ ] 3.3 Test winpeas command generation for Windows enumeration
- [ ] 3.4 Test bloodhound command generation for AD enumeration
- [ ] 3.5 Test mimikatz command generation for credential dumping
- [ ] 3.6 Test lazagne command generation for credential extraction
- [ ] 3.7 Test scope validation called BEFORE each tool execution
- [ ] 3.8 Test output parsing via Tier 1 parsers
- [ ] 3.9 Test fallback to Tier 2 LLM summarization
- [ ] 3.10 Test discovery extraction: credentials, privileges, shares, domain info

#### Task 4: Write Unit Tests for Privilege Escalation (AC: #4)
- [ ] 4.1 Test `_attempt_privesc()` detects escalation opportunities
- [ ] 4.2 Test Linux privesc via linpeas findings
- [ ] 4.3 Test Windows privesc via winpeas findings
- [ ] 4.4 Test escalation success detection and logging
- [ ] 4.5 Test escalation failure handling
- [ ] 4.6 Test escalation finding publication to correct channel

#### Task 5: Write Unit Tests for Lateral Movement Authorization (AC: #5)
- [ ] 5.1 Test `_request_authorization()` publishes to `authorization:{request_id}`
- [ ] 5.2 Test agent enters `WAITING_AUTHORIZATION` state
- [ ] 5.3 Test agent subscribes to `authorization:{request_id}:response`
- [ ] 5.4 Test authorization grant triggers action resumption
- [ ] 5.5 Test authorization deny triggers alternative path selection
- [ ] 5.6 Test authorization timeout behavior (indefinite wait per FR16)
- [ ] 5.7 Test authorization outcome logged in decision_context
- [ ] 5.8 Test lateral movement tools: psexec, wmiexec, smbexec, evil-winrm

#### Task 6: Write Unit Tests for Stigmergic Integration (AC: #6, #10)
- [ ] 6.1 Test `on_finding()` publishes to `findings:{target_hash}:postex`
- [ ] 6.2 Test finding contains all 10 required fields
- [ ] 6.3 Test finding signature is generated (HMAC-SHA256)
- [ ] 6.4 Test credential findings trigger swarm-wide notification
- [ ] 6.5 Test subscription to `strategies:{engagement_id}`
- [ ] 6.6 Test `on_signal()` handles Director strategy updates
- [ ] 6.7 Test strategy adaptation (stealth vs aggressive mode)

#### Task 7: Write Unit Tests for Intelligence Integration (AC: #7)
- [ ] 7.1 Test `_query_intelligence()` calls `IntelligenceAggregator.query()`
- [ ] 7.2 Test intelligence query with service and OS extraction
- [ ] 7.3 Test prioritized result selection (CISA KEV first)
- [ ] 7.4 Test handling of empty intelligence results
- [ ] 7.5 Test intelligence timeout handling (5s per source)
- [ ] 7.6 Test non-blocking intelligence query (agent continues on timeout)

#### Task 8: Write Unit Tests for RAG Escalation (AC: #8)
- [ ] 8.1 Test failure recording via `AgentRAGEscalator.record_failure()`
- [ ] 8.2 Test success recording via `AgentRAGEscalator.record_success()`
- [ ] 8.3 Test `should_escalate()` returns True after 3 failures
- [ ] 8.4 Test `escalate()` is called when threshold reached
- [ ] 8.5 Test `AgentRAGContext` construction with correct fields
- [ ] 8.6 Test alternative technique selection from RAG results (LOLBAS, GTFOBins)
- [ ] 8.7 Test escalation logging includes decision_context
- [ ] 8.8 Test handling of RAG timeout (`RAGQueryTimeout`)

#### Task 9: Write Unit Tests for Decision Context (AC: #9)
- [ ] 9.1 Test `decision_context` populated for ALL actions
- [ ] 9.2 Test `decision_context` includes stigmergic signal IDs
- [ ] 9.3 Test `decision_context` includes intelligence source IDs
- [ ] 9.4 Test `decision_context` includes authorization request/response IDs
- [ ] 9.5 Test `decision_context` includes RAG escalation trigger (when applicable)
- [ ] 9.6 Test 100% decision_context population (no empty contexts)
- [ ] 9.7 Test `get_decision_context()` returns accumulated signals

#### Task 10: Write Unit Tests for Error Handling (AC: #12)
- [ ] 10.1 Test tool execution timeout handling
- [ ] 10.2 Test tool execution failure handling (ERR1)
- [ ] 10.3 Test Redis connection loss during publish (ERR3 - buffer)
- [ ] 10.4 Test throttle timeout handling (`ThrottleTimeoutError`)
- [ ] 10.5 Test graceful shutdown during post-exploitation
- [ ] 10.6 Test recovery after partial failure
- [ ] 10.7 Test intelligence layer unavailable (graceful degradation)
- [ ] 10.8 Test access loss mid-operation (session died)

#### Task 11: Write Integration Tests (AC: #11, #12)
- [ ] 11.1 Test PostExAgent against cyber range compromised target (real tools)
- [ ] 11.2 Test credential dumping with mimikatz/lazagne
- [ ] 11.3 Test privilege escalation flow
- [ ] 11.4 Test lateral movement authorization flow
- [ ] 11.5 Test stigmergic signal propagation between agents
- [ ] 11.6 Test finding publication and subscription flow
- [ ] 11.7 Test Director strategy reception and adaptation
- [ ] 11.8 Test RAG escalation flow with real RAG queries
- [ ] 11.9 Test intelligence integration with real aggregator
- [ ] 11.10 Verify expected findings from `cyber-range/expected-findings.json`

### Phase 2: GREEN - Implement Minimal Code

> **⚠️ MANDATORY: Implement ONLY what is needed to pass failing tests**

#### Task 12: Create PostExAgent Class (AC: #1, #2)
- [ ] 12.1 Create `src/cyberred/agents/postex.py`
- [ ] 12.2 Implement `PostExAgent` extending `StigmergicAgent`
- [ ] 12.3 Implement `__init__` with target and access_data validation
- [ ] 12.4 Implement post-ex task queue initialization
- [ ] 12.5 Implement scope validation integration
- [ ] 12.6 Add structlog context binding (agent_id, engagement_id, target, access_type)

#### Task 13: Implement Enumeration Methods (AC: #3)
- [ ] 13.1 Implement `execute_postex()` main method
- [ ] 13.2 Implement `_generate_linpeas_command()`
- [ ] 13.3 Implement `_generate_winpeas_command()`
- [ ] 13.4 Implement `_generate_bloodhound_command()`
- [ ] 13.5 Implement `_generate_mimikatz_command()`
- [ ] 13.6 Implement `_generate_lazagne_command()`
- [ ] 13.7 Integrate with `kali_execute()` from Story 4.3
- [ ] 13.8 Implement output parsing with Tier 1/2 fallback
- [ ] 13.9 Implement discovery extraction logic

#### Task 14: Implement Privilege Escalation (AC: #4)
- [ ] 14.1 Implement `_attempt_privesc()` method
- [ ] 14.2 Implement Linux privesc detection and execution
- [ ] 14.3 Implement Windows privesc detection and execution
- [ ] 14.4 Implement escalation success/failure handling
- [ ] 14.5 Implement escalation finding publication

#### Task 15: Implement Lateral Movement with Authorization (AC: #5)
- [ ] 15.1 Implement `_discover_lateral_targets()` method
- [ ] 15.2 Implement `_request_authorization()` method
- [ ] 15.3 Implement `WAITING_AUTHORIZATION` state handling
- [ ] 15.4 Implement authorization response subscription
- [ ] 15.5 Implement `_execute_lateral_movement()` method
- [ ] 15.6 Implement `_generate_psexec_command()`
- [ ] 15.7 Implement `_generate_wmiexec_command()`
- [ ] 15.8 Implement `_generate_smbexec_command()`
- [ ] 15.9 Implement `_generate_evilwinrm_command()`
- [ ] 15.10 Implement alternative path selection on denial

#### Task 16: Implement Intelligence Integration (AC: #7)
- [ ] 16.1 Implement `_query_intelligence(service, os)` method
- [ ] 16.2 Integrate `CachedIntelligenceAggregator` from `intelligence/aggregator.py`
- [ ] 16.3 Implement prioritized technique selection
- [ ] 16.4 Implement timeout handling with graceful degradation

#### Task 17: Implement RAG Escalation (AC: #8)
- [ ] 17.1 Initialize `AgentRAGEscalator` in `__init__`
- [ ] 17.2 Implement failure tracking per target/technique
- [ ] 17.3 Implement `_handle_postex_failure()` method
- [ ] 17.4 Implement technique selection from RAG results (LOLBAS, GTFOBins)
- [ ] 17.5 Implement escalation decision_context tracking

#### Task 18: Implement Stigmergic Integration (AC: #6, #9, #10)
- [ ] 18.1 Override `on_finding()` for postex-specific publishing
- [ ] 18.2 Override `on_signal()` for strategy handling
- [ ] 18.3 Implement decision_context accumulation (signals + intel + auth + RAG)
- [ ] 18.4 Implement strategy adaptation logic (stealth vs aggressive)
- [ ] 18.5 Implement credential finding swarm notification
- [ ] 18.6 Ensure 100% decision_context population

#### Task 19: Implement Error Handling (AC: #12)
- [ ] 19.1 Implement timeout handling with configurable limits
- [ ] 19.2 Implement failure recovery (ERR1 pattern)
- [ ] 19.3 Implement Redis buffer for degraded mode (ERR3)
- [ ] 19.4 Implement graceful shutdown handling
- [ ] 19.5 Implement intelligence unavailable fallback
- [ ] 19.6 Implement session loss detection and handling

### Phase 3: REFACTOR - Optimize and Harden

> **⚠️ MANDATORY: Maintain 100% coverage while refactoring**

#### Task 20: Code Quality and Optimization (AC: #12)
- [ ] 20.1 Run `pytest --cov` and verify 100% coverage
- [ ] 20.2 Add missing tests for any uncovered lines
- [ ] 20.3 Optimize command generation for efficiency
- [ ] 20.4 Add comprehensive docstrings (Google style)
- [ ] 20.5 Run mypy and fix type errors
- [ ] 20.6 Run ruff and fix linting issues

#### Task 21: Documentation and Exports (AC: #12)
- [ ] 21.1 Update `agents/__init__.py` exports
- [ ] 21.2 Add usage examples in docstrings
- [ ] 21.3 Document configuration options
- [ ] 21.4 Update story Dev Agent Record

---

## Dev Notes

### Architecture Patterns & Constraints

**Class Hierarchy (per architecture line 795-800):**
```python
from swarms import Agent  # kyegomez/swarms v8.0.0+
from cyberred.agents.base import StigmergicAgent

class PostExAgent(StigmergicAgent):
    """Post-exploitation agent for lateral movement and persistence.
    
    Performs:
    - System enumeration (linpeas, winpeas)
    - Credential dumping (mimikatz, lazagne)
    - Active Directory enumeration (bloodhound)
    - Privilege escalation
    - Lateral movement (psexec, wmiexec, smbexec, evil-winrm)
    
    Publishes findings to: findings:{target_hash}:postex
    Subscribes to: strategies:{engagement_id}
    
    Integrates:
    - IntelligenceAggregator (Epic 5) for technique selection
    - AgentRAGEscalator (Story 6.10) for 3+ failure escalation
    - Authorization flow (FR13) for lateral movement approval
    
    CRITICAL: Lateral movement REQUIRES authorization (FR13).
    Agent enters WAITING_AUTHORIZATION state and waits indefinitely (FR16).
    """
```

**Tool Execution Pattern (per architecture lines 716-760):**
```python
# Agents generate bash code executed via kali_execute()
async def execute_postex(self) -> tuple[List[Finding], List[AgentAction]]:
    findings = []
    actions = []
    
    # 1. Enumeration phase
    enum_cmd = self._generate_enumeration_command()
    result = await kali_execute(enum_cmd)
    enum_findings = self._parse_enumeration(result)
    findings.extend(enum_findings)
    
    # 2. Credential extraction
    cred_cmd = self._generate_credential_command()
    result = await kali_execute(cred_cmd)
    cred_findings = self._parse_credentials(result)
    findings.extend(cred_findings)
    
    # 3. Privilege escalation (if not already privileged)
    if not self._is_privileged:
        privesc_findings = await self._attempt_privesc()
        findings.extend(privesc_findings)
    
    # 4. Lateral movement discovery
    lateral_targets = self._discover_lateral_targets(enum_findings)
    
    # 5. Authorization request for lateral movement (FR13 - CRITICAL)
    if lateral_targets:
        for target in lateral_targets:
            auth_granted = await self._request_authorization(
                action="lateral_movement",
                target=target,
                justification=f"Discovered via {self.target}"
            )
            if auth_granted:
                lateral_findings = await self._execute_lateral_movement(target)
                findings.extend(lateral_findings)
            else:
                self._log.info("lateral_movement_denied", target=target)
    
    # 6. Handle failures → RAG escalation after 3 attempts
    if self._failure_count >= 3:
        rag_result = await self._escalate_to_rag()
        if rag_result:
            # Try alternative technique from RAG
            alt_findings = await self._try_alternative(rag_result)
            findings.extend(alt_findings)
    
    # 7. Publish findings stigmergically
    for finding in findings:
        await self.on_finding(
            target_hash=self._hash_target(self.target),
            finding_type="postex",
            content=finding.to_dict()
        )
        # Credential findings get swarm-wide notification
        if finding.type == "credential":
            await self._notify_credential_found(finding)
    
    return findings, actions
```

**Authorization Flow Pattern (FR13, FR15, FR16 - CRITICAL):**
```python
async def _request_authorization(
    self, 
    action: str, 
    target: str, 
    justification: str
) -> bool:
    """Request operator authorization for sensitive action.
    
    Per FR13: Lateral movement requires human authorization.
    Per FR16: No auto-approve/deny on timeout - wait indefinitely.
    
    Args:
        action: Action type (e.g., "lateral_movement")
        target: Target of the action
        justification: Why this action is requested
        
    Returns:
        True if authorized, False if denied.
    """
    request_id = str(uuid.uuid4())
    
    # Publish authorization request
    await self._event_bus.publish(
        channel=f"authorization:{request_id}",
        message={
            "request_id": request_id,
            "agent_id": self.agent_id,
            "engagement_id": self.engagement_id,
            "action": action,
            "target": target,
            "source": self.target,
            "justification": justification,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    
    # Enter waiting state
    previous_status = self._status
    self._status = "waiting_authorization"
    self._log.info(
        "authorization_requested",
        request_id=request_id,
        action=action,
        target=target,
    )
    
    # Subscribe to response channel and wait indefinitely (FR16)
    response = await self._event_bus.subscribe_once(
        channel=f"authorization:{request_id}:response",
        timeout=None  # Indefinite wait per FR16
    )
    
    # Process response
    granted = response.get("granted", False)
    
    # Log outcome in decision_context
    self._decision_context.append(
        f"auth:{request_id}:{'granted' if granted else 'denied'}"
    )
    
    # Restore status
    self._status = previous_status if granted else "active"
    
    self._log.info(
        "authorization_response",
        request_id=request_id,
        granted=granted,
        constraints=response.get("constraints"),
    )
    
    return granted
```

**Intelligence Integration Pattern (per Story 5.7):**
```python
from cyberred.intelligence.aggregator import CachedIntelligenceAggregator

# Query returns prioritized results for post-ex techniques:
# CISA KEV (P0) > Critical CVE (P1) > High CVE (P2) > MSF module (P3)
async def _query_intelligence(self, service: str, os_type: str) -> List[IntelResult]:
    results = await self._intel_aggregator.query(
        service=service,
        version=self._target_version,
        os=os_type,
        query_type="postex"  # Filters for privilege escalation, lateral movement
    )
    return results
```

**RAG Escalation Pattern (per Story 6.10):**
```python
from cyberred.agents.rag_escalator import AgentRAGEscalator, AgentRAGContext

# Initialize in __init__
self._rag_escalator = AgentRAGEscalator(rag_interface)

# After post-ex failure
async def _handle_postex_failure(self, target_hash: str, technique_id: str):
    await self._rag_escalator.record_failure(target_hash, technique_id)
    
    if await self._rag_escalator.should_escalate(target_hash, technique_id):
        context = AgentRAGContext(
            agent_id=self.agent_id,
            target_service=self._target_service,
            target_hash=target_hash,
            failed_techniques=tuple(self._failed_techniques),
            failure_count=len(self._failed_techniques),
            environment={"os": self._target_os, "access_level": self._access_level},
            engagement_id=self.engagement_id,
        )
        result = await self._rag_escalator.escalate(context)
        # RAG returns LOLBAS, GTFOBins, HackTricks techniques
        if result.was_successful and result.selected_technique:
            return result.selected_technique
    return None
```

**Decision Context Tracking (NFR37) - CRITICAL:**
```python
# EVERY action must include decision_context - THIS IS A HARD GATE
async def execute_postex(self) -> tuple[List[Finding], List[AgentAction]]:
    # Capture ALL influencing signals BEFORE action
    decision_context = self.get_decision_context().copy()
    
    # Add intelligence source if used
    if intel_result:
        decision_context.append(f"intel:{intel_result.source}:{intel_result.cve_id}")
    
    # Add authorization if requested
    if auth_requested:
        decision_context.append(f"auth:{request_id}:{outcome}")
    
    # Add RAG escalation if triggered
    if rag_escalation_used:
        decision_context.append(f"rag_escalation:{technique_id}")
    
    # Add credential signal if triggered by another agent's finding
    if triggered_by_credential:
        decision_context.append(f"cred_signal:{finding_id}")
    
    # Ensure non-empty (NFR37 requires 100% population)
    if not decision_context:
        decision_context = [f"initial_spawn:{self.agent_id}"]
    
    # Create action with decision_context
    action = AgentAction(
        id=str(uuid.uuid4()),
        agent_id=self.agent_id,
        action_type=f"postex:{tool_name}",
        target=self.target,
        timestamp=datetime.now(timezone.utc).isoformat(),
        decision_context=decision_context,  # REQUIRED - must not be empty
        result_finding_id=finding.id if finding else None
    )
```

**Channel Naming (per architecture lines 686-700):**
| Channel Type | Pattern | Example |
|--------------|---------|---------|
| Findings | `findings:{target_hash}:postex` | `findings:a1b2c3:postex` |
| Credentials | `findings:{target_hash}:credential` | `findings:a1b2c3:credential` |
| Strategies | `strategies:{engagement_id}` | `strategies:ministry-2025` |
| Agent Status | `agents:{agent_id}:status` | `agents:postex-42:status` |
| Authorization | `authorization:{request_id}` | `authorization:req-001` |
| Auth Response | `authorization:{request_id}:response` | `authorization:req-001:response` |

### Existing Code to Reuse/Extend

| Component | Location | Usage |
|-----------|----------|-------|
| `StigmergicAgent` | `src/cyberred/agents/base.py` | Base class to extend |
| `ReconAgent` | `src/cyberred/agents/recon.py` | **REFERENCE IMPLEMENTATION** - follow patterns |
| `ExploitAgent` | `src/cyberred/agents/exploit.py` | **REFERENCE IMPLEMENTATION** - follow patterns |
| `AgentRAGEscalator` | `src/cyberred/agents/rag_escalator.py` | RAG escalation after 3+ failures |
| `AgentRAGContext` | `src/cyberred/agents/rag_escalator.py` | Context for RAG queries |
| `CachedIntelligenceAggregator` | `src/cyberred/intelligence/aggregator.py` | Intelligence queries |
| `IntelResult` | `src/cyberred/intelligence/base.py` | Intelligence result model |
| `KaliExecutor` | `src/cyberred/tools/kali_executor.py` | Tool execution |
| `ScopeValidator` | `src/cyberred/tools/scope.py` | Pre-execution validation |
| `OutputProcessor` | `src/cyberred/tools/output.py` | Tier 1/2 parsing |
| `LinpeasParser` | `src/cyberred/tools/parsers/linpeas.py` | Linpeas output parsing |
| `WinpeasParser` | `src/cyberred/tools/parsers/winpeas.py` | Winpeas output parsing |
| `BloodhoundParser` | `src/cyberred/tools/parsers/bloodhound.py` | Bloodhound output parsing |
| `MimikatzParser` | `src/cyberred/tools/parsers/mimikatz.py` | Mimikatz output parsing |
| `EventBus` | `src/cyberred/core/events.py` | Pub/sub communication |
| `Finding` | `src/cyberred/core/models.py` | Finding dataclass (10 fields) |
| `AgentAction` | `src/cyberred/core/models.py` | Action dataclass with decision_context |
| `compute_hmac_signature` | `src/cyberred/core/hashing.py` | HMAC-SHA256 for findings |

### LLM Tier Configuration

**PostExAgent uses COMPLEX tier (per architecture lines 133-138):**
```yaml
# Agent LLM Model Pool
tiers:
  FAST: Nemotron-3-Nano-30B      # Parsing structured output
  STANDARD: Llama Nemotron 49B   # Agent reasoning (ReconAgent)
  COMPLEX: DeepSeek-R1-0528      # Exploit chaining, post-ex (PostExAgent uses this)
```

### Anti-Patterns to Avoid

1. **DO NOT** skip scope validation — SAFETY-CRITICAL
2. **DO NOT** skip authorization for lateral movement — FR13 HARD REQUIREMENT
3. **DO NOT** auto-approve/deny authorization — FR16 requires indefinite wait
4. **DO NOT** use mock tools in integration tests — real Kali required
5. **DO NOT** create empty decision_context — NFR37 hard gate (100% required)
6. **DO NOT** skip error handling — ERR1/ERR3 patterns required
7. **DO NOT** hardcode tool commands — use configurable templates
8. **DO NOT** fork swarms — extend only (NFR27)
9. **DO NOT** bypass throttling — respect Story 7.2 implementation
10. **DO NOT** skip RAG escalation — must trigger after 3+ failures (Story 6.10)
11. **DO NOT** ignore intelligence results — use prioritized selection
12. **DO NOT** block on intelligence queries — 5s timeout, continue on failure
13. **DO NOT** forget credential notification — swarm-wide alert for creds found

### Testing Standards

**100% Coverage Requirements (NFR19, NFR20):**
```bash
# Unit tests must achieve 100% coverage
pytest tests/unit/agents/test_postex_agent.py --cov=src/cyberred/agents/postex --cov-fail-under=100

# Integration tests must achieve 100% branch coverage
pytest tests/integration/agents/test_postex_agent_integration.py --cov=src/cyberred/agents/postex --cov-branch --cov-fail-under=100
```

**Test Fixtures Required:**
```
tests/fixtures/postex/
├── linpeas_output.txt            # Linux enumeration output
├── winpeas_output.txt            # Windows enumeration output
├── bloodhound_output.json        # AD enumeration output
├── mimikatz_output.txt           # Credential dump output
├── lazagne_output.json           # Credential extraction output
├── psexec_output.txt             # Lateral movement output
├── wmiexec_output.txt            # WMI execution output
├── access_data_shell.json        # Shell access test data
├── access_data_creds.json        # Credential access test data
├── access_data_session.json      # Session access test data
├── intel_results_mock.json       # Mock intelligence results
├── rag_results_lolbas.json       # Mock RAG LOLBAS results
├── rag_results_gtfobins.json     # Mock RAG GTFOBins results
└── sample_compromised_target.yaml # Test target configuration
```

**Markers:**
```python
@pytest.mark.unit
@pytest.mark.integration
@pytest.mark.safety  # For scope validation and authorization tests
```

### Project Structure

**New Files:**
```
src/cyberred/agents/
├── __init__.py        # UPDATE: Export PostExAgent
├── base.py            # Existing: StigmergicAgent
├── recon.py           # Existing: ReconAgent (REFERENCE)
├── exploit.py         # Existing: ExploitAgent (REFERENCE)
├── postex.py          # NEW: PostExAgent implementation
├── ghost_agent.py     # Existing (legacy)
└── rag_escalator.py   # Existing (Story 6.10)

tests/unit/agents/
├── test_stigmergic_base.py           # Existing (Story 7.1)
├── test_agent_throttling.py          # Existing (Story 7.2)
├── test_recon_agent.py               # Existing (Story 7.3)
├── test_recon_agent_extended.py      # Existing (Story 7.3)
├── test_recon_agent_coverage.py      # Existing (Story 7.3)
├── test_exploit_agent.py             # Existing (Story 7.4)
└── test_postex_agent.py              # NEW: Unit tests

tests/integration/agents/
├── test_stigmergic_integration.py           # Existing (Story 7.1)
├── test_agent_throttling_integration.py     # Existing (Story 7.2)
├── test_recon_agent_integration.py          # Existing (Story 7.3)
├── test_exploit_agent_integration.py        # Existing (Story 7.4)
└── test_postex_agent_integration.py         # NEW: Integration tests

tests/fixtures/postex/
├── linpeas_output.txt               # NEW
├── winpeas_output.txt               # NEW
├── bloodhound_output.json           # NEW
├── mimikatz_output.txt              # NEW
├── lazagne_output.json              # NEW
├── access_data_shell.json           # NEW
└── sample_compromised_target.yaml   # NEW
```

### Configuration

**PostExAgent Config (add to engagement config):**
```yaml
agents:
  postex:
    tools:
      - linpeas
      - winpeas
      - bloodhound
      - mimikatz
      - lazagne
      - impacket-psexec
      - impacket-wmiexec
      - impacket-smbexec
      - evil-winrm
    timeout: 600  # seconds per tool
    parallel_tasks: 2
    llm_tier: COMPLEX
    rag_escalation_threshold: 3  # failures before RAG query
    intelligence_timeout: 5  # seconds per source
    authorization_required:
      - lateral_movement
      - persistence
      - credential_exfil
```

### References

- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story-7.5] — Acceptance criteria
- [Source: _bmad-output/planning-artifacts/architecture.md#Tool-Execution-Architecture] — kali_execute() pattern
- [Source: _bmad-output/planning-artifacts/architecture.md#Agent-Communication-Patterns] — Channel naming
- [Source: _bmad-output/planning-artifacts/architecture.md#Vulnerability-Intelligence-Layer-Integration] — Intelligence integration
- [Source: _bmad-output/planning-artifacts/architecture.md#RAG-Escalation-Layer-Integration] — RAG escalation triggers
- [Source: _bmad-output/planning-artifacts/architecture.md#Mandatory-Rules-for-AI-Agents] — Rule 1: Extend StigmergicAgent
- [Source: _bmad-output/implementation-artifacts/7-1-stigmergic-agent-base-class.md] — Base class implementation
- [Source: _bmad-output/implementation-artifacts/7-2-agent-self-throttling.md] — Throttling implementation
- [Source: _bmad-output/implementation-artifacts/7-3-recon-agent-implementation.md] — **REFERENCE IMPLEMENTATION**
- [Source: _bmad-output/implementation-artifacts/7-4-exploit-agent-implementation.md] — **REFERENCE IMPLEMENTATION**
- [Source: _bmad-output/implementation-artifacts/6-10-agent-rag-escalation.md] — RAG escalation
- [Source: _bmad-output/implementation-artifacts/5-7-intelligence-aggregator.md] — Intelligence aggregator
- [Source: src/cyberred/agents/base.py] — StigmergicAgent source code
- [Source: src/cyberred/agents/recon.py] — ReconAgent source code (follow patterns)
- [Source: src/cyberred/agents/exploit.py] — ExploitAgent source code (follow patterns)
- [Source: src/cyberred/agents/rag_escalator.py] — AgentRAGEscalator source code
- [Source: src/cyberred/intelligence/aggregator.py] — CachedIntelligenceAggregator source code
- [Source: src/cyberred/tools/kali_executor.py] — KaliExecutor source code
- [Source: src/cyberred/tools/scope.py] — ScopeValidator source code

### Story 7.1, 7.2, 7.3, 7.4 Learnings Applied

**From Story 7.1 (StigmergicAgent):**
- TDD phased format (RED/GREEN/REFACTOR) proven effective
- EventBus integration patterns established
- Protocol compliance via structural subtyping
- structlog context binding pattern

**From Story 7.2 (Self-Throttling):**
- Throttle check integrated into execute() flow
- WAITING status when throttled
- ThrottleTimeoutError for max wait exceeded
- Fail-open strategy if gateway unavailable

**From Story 7.3 (ReconAgent) — REFERENCE:**
- `execute_recon()` returns `tuple[List[Finding], List[AgentAction]]` — **follow same pattern**
- Decision context captured BEFORE action, includes `initial_spawn:{agent_id}` as fallback
- Strategy adaptation via `on_signal()` override
- Finding buffer for Redis degraded mode
- Tool command generation via helper methods `_generate_{tool}_command()`
- Output parsing via `OutputProcessor` with registered parsers
- Graceful stop via `_stop_event` asyncio.Event

**From Story 7.4 (ExploitAgent) — REFERENCE:**
- Intelligence integration pattern with 5s timeout
- RAG escalation after 3+ failures (AgentRAGEscalator)
- decision_context includes intel source IDs
- HMAC signature via `compute_hmac_signature()`
- `_finding_buffer` for ERR3 degraded mode
- Comprehensive test fixtures for each tool

**Critical Fix from 7.3/7.4 Code Reviews:**
- `AgentAction` MUST be created for every tool execution (NFR37 violation was found)
- Tests must use proper `ScopeConfig` with `allowed_networks` and `allowed_hostnames`
- 100% coverage requires dedicated coverage test file for edge cases
- Export new agent class in `agents/__init__.py`

### Dependencies

**Prerequisites (all complete):**
- Story 7.1: StigmergicAgent Base Class ✅
- Story 7.2: Agent Self-Throttling ✅
- Story 7.3: ReconAgent Implementation ✅ (REFERENCE)
- Story 7.4: ExploitAgent Implementation ✅ (REFERENCE)
- Story 4.3: Kali Executor Core ✅
- Story 4.10: Tier 1 Parsers Remaining (linpeas, winpeas, bloodhound, mimikatz) ✅
- Story 4.11: Tier 2 LLM Summarization ✅
- Story 5.7: Intelligence Aggregator ✅
- Story 6.10: Agent RAG Escalation ✅
- Story 1.8: Scope Validator ✅
- Story 0.6: Cyber Range Environment ✅

**Blocks:**
- Story 7.6: SwarmRouter Integration
- Story 7.7: Dynamic Agent Spawner
- Story 7.8: Decision Context Tracking (validation)
- Story 7.12: Agent Crash Recovery
- Story 7.14: Emergence Validation Gate Test
- Story 7.16: Agent Authorization Response Handling (validation)

### NFR Traceability

| NFR | Requirement | Implementation |
|-----|-------------|----------------|
| NFR1 | <1s stigmergic propagation | Uses EventBus pub/sub |
| NFR6 | 10,000+ agents | Inherits throttling, O(1) coordination |
| NFR8 | O(1) memory efficiency | No inter-agent state beyond decision_context |
| NFR19 | 100% unit test coverage | TDD Phase 1 ensures coverage |
| NFR20 | 100% integration coverage | Phase 1 Task 11 covers integration |
| NFR35 | >20% novel attack chains | Contributes to emergence via stigmergic findings |
| NFR37 | 100% decision_context | Task 9 + Task 18.3-18.6 ensure compliance |

### FR Traceability

| FR | Requirement | Implementation |
|----|-------------|----------------|
| FR2 | 10,000+ agent deployment | PostExAgent scales via stigmergic coordination |
| FR4 | Real-time P2P coordination | Publishes to `findings:*`, subscribes to `strategies:*` |
| FR13 | Authorization for lateral movement | `_request_authorization()` method, WAITING_AUTHORIZATION state |
| FR15 | Yes/No authorization response | Handles grant/deny in `_request_authorization()` |
| FR16 | No auto-approve/deny timeout | Indefinite wait in authorization subscription |
| FR31 | 600+ tools via kali_execute() | Uses KaliExecutor for tool execution |
| FR62 | decision_context logging | All actions include influencing signals |
| FR65-FR75 | Intelligence layer | Queries CachedIntelligenceAggregator |
| FR76-FR84 | RAG escalation | AgentRAGEscalator after 3+ failures (LOLBAS, GTFOBins) |

### Error Handling (ERR Patterns)

| Error | Pattern | Implementation |
|-------|---------|----------------|
| ERR1 | Tool execution failure | Log error, return structured result, agent continues |
| ERR3 | Redis connection loss | Buffer messages locally (10s max), reconnect |
| ERR5 | Agent crash | Log crash, spawn replacement (handled by spawner) |

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
