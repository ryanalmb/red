# Story 7.21: ActiveDirectoryAgent Implementation

**Epic:** Epic 7 - Agent Framework & Stigmergic Coordination  
**Priority:** P1  
**Status:** ready-for-dev  
**Effort:** 5 story points  
**Dependencies:** Story 7.1.v2 (StigmergicAgent LLM Selection) ✅ DONE, Story 7.18 (AgentRole + PromptLibrary) ✅ DONE  
**Blocks:** 7.6 (SwarmRouter Integration), 7.24 (Unified Agent Test Suite), Epic 15 (E2E Validation)

---

## Story

As a **penetration tester using Cyber-Red**,
I want an Active Directory attack agent that uses LLM-driven tool selection from the full 1,556+ tool manifest,
so that domain environments are tested with expert-level adaptive tool selection and the swarm achieves emergence required by NFR35-37.

## Acceptance Criteria

### AC1: Thin Subclass Architecture
- ADAgent is a thin subclass of StigmergicAgent (<300 lines)
- Constructor sets `role=AgentRole.AD`
- Constructor accepts `specialty` parameter (default: "general", valid: "general", "enumeration", "kerberos", "lateral")
- NO `target` in constructor (passed to `execute_ad_attack()`)

### AC2: Hardcoded Methods REMOVED
- NO `_generate_bloodhound_command()` method
- NO `_generate_rubeus_command()` method
- NO `_generate_impacket_command()` method
- NO `_generate_crackmapexec_command()` method
- NO `tool_sequence` attribute
- All commands generated via inherited `select_tool()` and LLM

### AC3: LLM-Driven Tool Selection
- `execute_ad_attack(domain_controller, context)` uses inherited `select_tool()` from StigmergicAgent
- LLM selects from full manifest based on domain info, discovered users, SPNs, and obtained tickets
- Tool commands generated via LLM using `--help` output (inherited `generate_command()`)

### AC4: NFR37 Decision Context (HARD GATE)
- ALL AgentActions have non-empty `decision_context`
- Minimum context: `initial_spawn:{agent_id}`
- Domain context added: `domain:{domain_name}`
- Ticket context added when obtained: `ticket:{ticket_type}:{spn}`
- Credential context added when harvested: `creds:{username}`

### AC5: Domain Enumeration
- `_enumerate_domain(domain_controller, credentials)` performs initial LDAP enumeration
- Domain info stored in `_domain_info` dict (domain_name, forest, functional_level)
- Discovered users stored in `_discovered_users` list
- Discovered SPNs stored in `_discovered_spns` list

### AC6: Kerberos Attack Coordination
- Kerberoasting tickets published to `credentials:{engagement_id}:kerberos` channel
- AS-REP roasting hashes published to same channel
- CredentialAgent can subscribe and crack Kerberos tickets
- Obtained tickets stored in `_obtained_tickets` dict

### AC7: Credential Publication
- NTLM hashes published to `credentials:{engagement_id}:ad` channel
- Domain admin findings published to `findings:{target_hash}:domainadmin` with severity=critical
- All credentials stored in `_obtained_credentials` list

### AC8: Preserved Functionality
- Stigmergic hooks preserved (`on_finding()`, `on_signal()`, `_flush_buffer()`, `stop()`)
- Findings published to `findings:{target_hash}:ad`
- Strategy updates handled (stealth/standard/aggressive)

### AC9: Quality Gates (HARD REQUIREMENTS)
- **100% test coverage** on `ad.py`
- `ruff check` passes with no errors
- All unit and integration tests pass

## Tasks / Subtasks

### Phase 1: RED - Write Failing Tests First (TDD)

- [ ] Task 1.1: Constructor Tests (AC: #1)
  - [ ] `test_sets_role_to_ad`
  - [ ] `test_default_specialty_is_general`
  - [ ] `test_accepts_valid_specialties` - parametrize ["general", "enumeration", "kerberos", "lateral"]
  - [ ] `test_no_target_in_constructor`
  - [ ] `test_configurable_max_iterations`
  - [ ] `test_configurable_phase_complete_threshold`

- [ ] Task 1.2: Hardcoded Removal Tests (AC: #2)
  - [ ] `test_no_generate_bloodhound_command`
  - [ ] `test_no_generate_rubeus_command`
  - [ ] `test_no_generate_impacket_command`
  - [ ] `test_no_generate_crackmapexec_command`
  - [ ] `test_no_tool_sequence_attribute`

- [ ] Task 1.3: Execute Method Tests (AC: #3)
  - [ ] `test_execute_ad_attack_takes_domain_controller_param`
  - [ ] `test_execute_ad_attack_calls_select_tool`
  - [ ] `test_execute_ad_attack_respects_stop_event`
  - [ ] `test_execute_ad_attack_respects_max_iterations`

- [ ] Task 1.4: NFR37 Decision Context Tests (AC: #4)
  - [ ] `test_all_actions_have_decision_context`
  - [ ] `test_decision_context_includes_spawn`
  - [ ] `test_decision_context_includes_domain`
  - [ ] `test_decision_context_includes_ticket_when_obtained`
  - [ ] `test_decision_context_includes_creds_when_harvested`

- [ ] Task 1.5: Domain Enumeration Tests (AC: #5)
  - [ ] `test_enumerate_domain_populates_domain_info`
  - [ ] `test_enumerate_domain_extracts_users`
  - [ ] `test_enumerate_domain_extracts_spns`
  - [ ] `test_enumerate_domain_handles_failure`
  - [ ] `test_enumerate_domain_with_credentials`

- [ ] Task 1.6: Kerberos Attack Tests (AC: #6)
  - [ ] `test_kerberoast_ticket_published_to_credentials_channel`
  - [ ] `test_asrep_roast_published_to_credentials_channel`
  - [ ] `test_obtained_tickets_stored`
  - [ ] `test_golden_ticket_detection`
  - [ ] `test_silver_ticket_detection`

- [ ] Task 1.7: Credential Publication Tests (AC: #7)
  - [ ] `test_ntlm_hash_published_to_ad_channel`
  - [ ] `test_domain_admin_finding_is_critical`
  - [ ] `test_credentials_stored_in_list`

- [ ] Task 1.8: Strategy Tests (AC: #8)
  - [ ] `test_on_signal_updates_strategy` - parametrize ["stealth", "standard", "aggressive"]
  - [ ] `test_on_signal_ignores_invalid_strategy`
  - [ ] `test_get_constraints_stealth` - should avoid password spraying
  - [ ] `test_get_constraints_aggressive` - allows all attack types

- [ ] Task 1.9: Stigmergic Hook Tests (AC: #8)
  - [ ] `test_on_finding_publishes_to_ad_channel`
  - [ ] `test_stop_sets_event`
  - [ ] `test_flush_buffer_on_reconnect`

### Phase 2: GREEN - Implement Minimal Code

- [ ] Task 2.1: Refactor `src/cyberred/agents/ad.py` to thin subclass pattern
- [ ] Task 2.2: Ensure constructor sets `role=AgentRole.AD` with configurable specialty
- [ ] Task 2.3: Verify `execute_ad_attack(domain_controller, context)` uses LLM loop
- [ ] Task 2.4: Verify `_enumerate_domain(domain_controller, credentials)` helper
- [ ] Task 2.5: Verify Kerberos ticket detection and publication
- [ ] Task 2.6: Verify NTLM credential detection and publication
- [ ] Task 2.7: Implement `_get_constraints()` with stealth awareness
- [ ] Task 2.8: Preserve stigmergic hooks

### Phase 3: REFACTOR - Optimize and Verify Coverage

- [ ] Task 3.1: Verify line count < 300
- [ ] Task 3.2: Run `ruff check src/cyberred/agents/ad.py`
- [ ] Task 3.3: Run coverage - target 100%
- [ ] Task 3.4: Create specialty prompts: `ad_enumeration.md`, `ad_kerberos.md`, `ad_lateral.md`

## Dev Notes

### Thin Subclass Pattern (from agent-refactor-pattern.md)

```python
class ADAgent(StigmergicAgent):
    """Active Directory attack agent - thin subclass setting role=AD."""
    
    DEFAULT_MAX_ITERATIONS: int = 30
    DEFAULT_PHASE_COMPLETE_THRESHOLD: int = 75
    
    def __init__(
        self,
        agent_id: str,
        engagement_id: str,
        event_bus: EventBus,
        specialty: str = "general",  # general, enumeration, kerberos, lateral
        llm_gateway: "LLMGateway | None" = None,
        manifest_loader: "ManifestLoader | None" = None,
        max_iterations: int | None = None,
        phase_complete_threshold: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            agent_name=f"ad-agent-{specialty}",
            agent_id=agent_id,
            engagement_id=engagement_id,
            event_bus=event_bus,
            role=AgentRole.AD,
            specialty=specialty,
            llm_gateway=llm_gateway,
            manifest_loader=manifest_loader,
            **kwargs,
        )
        self.max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
        self.phase_complete_threshold = phase_complete_threshold or self.DEFAULT_PHASE_COMPLETE_THRESHOLD
        self.current_strategy = "standard"
        self._domain_info: dict[str, Any] = {}
        self._discovered_users: list[str] = []
        self._discovered_spns: list[dict[str, str]] = []
        self._obtained_tickets: dict[str, str] = {}
        self._obtained_credentials: list[dict[str, Any]] = []
        self._finding_buffer: list[dict[str, Any]] = []
        self._stop_event = asyncio.Event()
```

### Execute Method Pattern

```python
async def execute_ad_attack(
    self, domain_controller: str, context: dict[str, Any]
) -> tuple[list[Finding], list[AgentAction]]:
    """Execute LLM-driven Active Directory attack campaign."""
    all_findings: list[Finding] = []
    all_actions: list[AgentAction] = []

    # Initial domain enumeration
    await self._enumerate_domain(domain_controller, context.get("credentials"))
    
    if self._stop_event.is_set():
        return [], []

    tool_context = ToolSelectionContext(
        objective=f"Compromise AD domain via {domain_controller}",
        target_info={
            "domain_controller": domain_controller,
            "domain_info": self._domain_info,
            "discovered_users": self._discovered_users,
            "discovered_spns": self._discovered_spns,
            "phase": "ad",
            "strategy": self.current_strategy,
            **context
        },
        available_tools=self._get_ad_tools(),
        phase="ad",
        constraints=self._get_constraints(),
        previous_results=[],
    )

    for iteration in range(self.max_iterations):
        if self._stop_event.is_set() or await self._phase_complete(tool_context):
            break

        decision_context = self._build_decision_context()
        action_id = str(uuid.uuid4())
        result_finding_id: str | None = None
        tool_name = "unknown"

        try:
            selection = await self.select_tool(tool_context)
            tool_name = selection.tool_name
            result = await kali_execute(selection.command)

            if result.success and result.stdout:
                finding = self._create_finding(domain_controller, selection, result)
                all_findings.append(finding)
                await self.on_finding(finding)
                result_finding_id = finding.id
                
                # Check for Kerberos tickets and credentials
                await self._check_kerberos_results(result, selection)
                await self._check_credential_results(result, selection)

            # Update context with results
            tool_context = self._update_context(tool_context, all_findings)
        except Exception as e:
            self._log.error("ad_iteration_error", error=str(e))

        all_actions.append(AgentAction(
            id=action_id,
            agent_id=str(self.agent_id),
            action_type=f"ad:{tool_name}",
            target=domain_controller,
            timestamp=datetime.now(UTC).isoformat(),
            decision_context=decision_context,
            result_finding_id=result_finding_id,
        ))

    return all_findings, all_actions
```

### Specialty Prompts (4 required)

| Specialty | File | Focus |
|-----------|------|-------|
| general (default) | `prompts/ad.md` | Full AD attack methodology (✅ EXISTS) |
| enumeration | `prompts/ad_enumeration.md` | Domain/user/group enumeration only (CREATE) |
| kerberos | `prompts/ad_kerberos.md` | Kerberoasting, AS-REP, ticket attacks (CREATE) |
| lateral | `prompts/ad_lateral.md` | Lateral movement, PTH, DCSync (CREATE) |

### Key Tools (from manifest)

| Tool | Purpose | Category |
|------|---------|----------|
| `ldapsearch` | LDAP enumeration | enumeration |
| `bloodhound-python` | AD relationship mapping | enumeration |
| `enum4linux-ng` | SMB/RPC enumeration | enumeration |
| `rpcclient` | RPC enumeration | enumeration |
| `impacket-GetUserSPNs` | Kerberoasting | kerberos |
| `impacket-GetNPUsers` | AS-REP roasting | kerberos |
| `impacket-getTGT` | TGT requests | kerberos |
| `impacket-ticketer` | Golden/Silver tickets | kerberos |
| `impacket-secretsdump` | Credential dumping | credential |
| `crackmapexec` | Multi-purpose AD tool | general |
| `impacket-psexec` | Remote execution | lateral |
| `impacket-wmiexec` | WMI execution | lateral |
| `evil-winrm` | WinRM access | lateral |
| `kerbrute` | Kerberos bruteforce | kerberos |

### Stealth Constraints

When `current_strategy == "stealth"`:
- Avoid password spraying (triggers lockout detection)
- Prefer passive enumeration (LDAP, BloodHound)
- Use stealth techniques for Kerberoasting
- No DCSync or mass credential dumping
- Avoid noisy SMB scanning

When `current_strategy == "aggressive"`:
- Allow all attack types
- Password spraying permitted (respecting lockout policies)
- DCSync enabled
- Aggressive enumeration enabled

### Kerberos Attack Flow

```
1. Enumerate SPNs via ldapsearch/GetUserSPNs
2. Request TGS tickets for Kerberoasting → $krb5tgs$...
3. Publish to `credentials:{engagement_id}:kerberos` channel
4. CredentialAgent receives and cracks with hashcat mode 13100
5. Cracked password → lateral movement opportunities
```

### NTLM Credential Flow

```
1. Dump credentials via secretsdump/mimikatz
2. Parse NTLM hashes (username:RID:LM:NT:::)
3. Publish to `credentials:{engagement_id}:ad` channel
4. Check for domain admin (RID 500, admin in name)
5. Publish critical finding if domain admin found
```

### Anti-Patterns to Avoid

1. ❌ **Target in constructor** → Domain controller goes in `execute_ad_attack(dc, context)`
2. ❌ **Missing decision_context** → NFR37 requires ALL actions have non-empty context
3. ❌ **Hardcoded iteration limits** → Use configurable class constants
4. ❌ **Using testcontainers directly** → Mock `kali_execute` in integration tests
5. ❌ **Breaking stigmergic hooks** → Preserve `on_finding()`, `on_signal()` exactly
6. ❌ **Ignoring lockout policies** → Stealth mode must avoid password spraying

### Project Structure

```
src/cyberred/agents/
├── base.py              # StigmergicAgent with select_tool(), generate_command()
├── ad.py                # ADAgent (<300 lines after refactor)
├── roles.py             # AgentRole.AD
└── prompts/
    ├── ad.md              # Base prompt (✅ EXISTS)
    ├── ad_enumeration.md  # Enumeration specialty (CREATE)
    ├── ad_kerberos.md     # Kerberos specialty (CREATE)
    └── ad_lateral.md      # Lateral movement specialty (CREATE)

tests/unit/agents/
└── test_ad_agent.py         # Unit tests (EXISTS - 41KB)

tests/integration/agents/
└── test_ad_agent_integration.py  # Integration tests (EXISTS)
```

### Existing Implementation Analysis

The current `src/cyberred/agents/ad.py` implementation (222 lines) **already follows the thin subclass pattern**:

**✅ Correct patterns already in place:**
- Sets `role=AgentRole.AD` in constructor
- Uses `execute_ad_attack(domain_controller, context)` method
- No hardcoded `tool_sequence` attribute
- No `_generate_*_command()` methods
- Kerberos ticket publication to credentials channel
- NTLM credential detection and publication
- Decision context building with domain/ticket/creds info
- Strategy-aware constraints (stealth/standard/aggressive)
- Stigmergic hooks preserved (`on_finding`, `on_signal`, `stop`, `_flush_buffer`)

**🔧 Items to verify/enhance:**
- Verify 100% test coverage achieved
- Create specialty prompt files if missing
- Verify integration tests pass with mocked kali_execute

### References

| Document | Relevance |
|----------|-----------|
| `agent-refactor-pattern.md` | **MANDATORY PATTERN** |
| `7-20-wireless-agent.md` | Reference implementation (same pattern) |
| `src/cyberred/agents/wireless.py` | Code reference (~240 lines) |
| `epics-stories.md` lines 3349-3378 | Original story definition |
| `tests/unit/agents/test_ad_agent.py` | Existing unit tests (41KB) |

### Previous Story Intelligence

From **7-20-wireless-agent.md** (completed):
- Constructor pattern with configurable thresholds works well
- Interface/target as method parameter, not constructor
- Specialty prompts required for each variant
- 59 unit tests achieved 98.97% coverage - target 100%
- Monitor mode pattern adaptable to domain enumeration init

From **existing ad.py implementation**:
- Already follows thin subclass pattern (222 lines)
- Kerberos detection regex patterns established
- Credential parsing regex patterns established
- Domain admin detection logic in place

## Definition of Done

### Code Requirements
- [ ] Thin subclass (<300 lines) - ✅ CURRENT: 222 lines
- [ ] `role=AgentRole.AD` in constructor - ✅ VERIFIED
- [ ] `specialty` param (default: "general", valid: general/enumeration/kerberos/lateral)
- [ ] NO `_generate_*_command()` methods, NO `tool_sequence` - ✅ VERIFIED
- [ ] `execute_ad_attack(domain_controller, context)` uses inherited `select_tool()` - ✅ VERIFIED
- [ ] Domain enumeration via `_enumerate_domain()` - ✅ VERIFIED
- [ ] Kerberos ticket detection and publication - ✅ VERIFIED
- [ ] Credential detection and publication - ✅ VERIFIED
- [ ] ALL AgentActions have non-empty `decision_context` (NFR37) - ✅ VERIFIED
- [ ] Configurable `max_iterations`, `phase_complete_threshold` - ✅ VERIFIED

### Quality Gates (HARD)
- [ ] **100% test coverage** on `ad.py`
- [ ] `ruff check` passes with no errors
- [ ] All unit tests pass
- [ ] All integration tests pass

### Prompt Files
- [ ] `ad.md` exists (base prompt)
- [ ] `ad_enumeration.md` created
- [ ] `ad_kerberos.md` created
- [ ] `ad_lateral.md` created

## Validation Commands

```bash
# Full validation
source venv/bin/activate
wc -l src/cyberred/agents/ad.py  # MUST be <300
grep -c "_generate_\|tool_sequence" src/cyberred/agents/ad.py || echo "0"  # MUST be 0
pytest tests/unit/agents/test_ad_agent.py --cov=src/cyberred/agents/ad --cov-fail-under=100 -q
ruff check src/cyberred/agents/ad.py
```

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

**Existing Files to Verify:**
- src/cyberred/agents/ad.py (222 lines)
- tests/unit/agents/test_ad_agent.py (existing tests)
- tests/integration/agents/test_ad_agent_integration.py (existing)

**New Files to Create:**
- src/cyberred/agents/prompts/ad_enumeration.md
- src/cyberred/agents/prompts/ad_kerberos.md
- src/cyberred/agents/prompts/ad_lateral.md

## Change Log

| Date | Change |
|------|--------|
| 2026-01-26 | Story file created - ready-for-dev |
