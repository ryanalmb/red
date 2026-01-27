# Story 7.22: CredentialAgent Implementation

**Epic:** Epic 7 - Agent Framework & Stigmergic Coordination  
**Priority:** P1  
**Status:** in-progress  
**Effort:** 5 story points  
**Dependencies:** Story 7.1.v2 (StigmergicAgent LLM Selection) ✅ DONE, Story 7.18 (AgentRole + PromptLibrary) ✅ DONE  
**Blocks:** 7.6 (SwarmRouter Integration), 7.24 (Unified Agent Test Suite), Epic 15 (E2E Validation)

---

## Story

As a **penetration tester using Cyber-Red**,
I want a specialized CredentialAgent for credential harvesting and cracking that uses LLM-driven tool selection from the full 1,556+ tool manifest,
so that authentication attacks are performed with expert-level adaptive tool selection and the swarm achieves emergence required by NFR35-37.

## Acceptance Criteria

### AC1: Thin Subclass Architecture
- CredentialAgent is a thin subclass of StigmergicAgent (545 lines - **exceeds 300 limit, approved by user**)
- Constructor sets `role=AgentRole.CREDENTIAL`
- Constructor accepts `specialty` parameter (default: "general", valid: "general", "harvesting", "cracking", "spraying")
- NO `target` in constructor (passed to `execute_credential_attack()`)

### AC2: Hardcoded Methods REMOVED
- NO `_generate_hashcat_command()` method
- NO `_generate_hydra_command()` method
- NO `_generate_john_command()` method
- NO `_generate_mimikatz_command()` method
- NO `tool_sequence` attribute
- All commands generated via inherited `select_tool()` and LLM

### AC3: LLM-Driven Tool Selection
- `execute_credential_attack(target, context)` uses inherited `select_tool()` from StigmergicAgent
- LLM selects from full manifest based on hash type, target service, and credential context
- Tool commands generated via LLM using `--help` output (inherited `generate_command()`)

### AC4: NFR37 Decision Context (HARD GATE)
- ALL AgentActions have non-empty `decision_context`
- Minimum context: `initial_spawn:{agent_id}`
- Hash context added: `hash_type:{hash_type}` (e.g., NTLM, Kerberos, bcrypt)
- Target service context added: `service:{service_name}` (e.g., ssh, smb, web)
- Cracked credential context added: `cracked:{username}`

### AC5: Password Spraying
- `_execute_password_spray(target, users, passwords)` performs intelligent spraying
- Respects lockout policies via configurable `lockout_threshold` and `lockout_window`
- Supports spray-and-wait pattern for lockout evasion
- Uses tools: hydra, crackmapexec, kerbrute, spray

### AC6: Hash Cracking
- `_crack_hashes(hashes, hash_type)` selects appropriate cracking approach
- Auto-detects hash type from format (NTLM, Kerberos TGS, AS-REP, bcrypt, etc.)
- Selects hashcat mode or john format based on hash type
- Wordlist and rule selection via LLM recommendation
- Cracked credentials stored in `_cracked_credentials` list

### AC7: Credential Harvesting
- `_harvest_credentials(target, access_type)` extracts credentials from compromised systems
- Windows: mimikatz, secretsdump, lsassy
- Linux: /etc/shadow parsing, SSH key collection
- Web: browser credential extraction, config file parsing
- Harvested credentials stored in `_harvested_credentials` list

### AC8: Stigmergic Credential Sharing
- Cracked credentials published to `credentials:{engagement_id}:cracked` channel
- Subscribes to `credentials:{engagement_id}:*` for hashes from other agents (ADAgent, PostExAgent)
- Receives Kerberos tickets from ADAgent via `credentials:{engagement_id}:kerberos`
- Findings published to `findings:{target_hash}:credential`

### AC9: Preserved Functionality
- Stigmergic hooks preserved (`on_finding()`, `on_signal()`, `_flush_buffer()`, `stop()`)
- Strategy updates handled (stealth/standard/aggressive)

### AC10: Quality Gates (HARD REQUIREMENTS)
- **100% test coverage** on `credential.py`
- `ruff check` passes with no errors
- All unit and integration tests pass

## Tasks / Subtasks

### Phase 1: RED - Write Failing Tests First (TDD)

- [ ] Task 1.1: Constructor Tests (AC: #1)
  - [ ] `test_sets_role_to_credential`
  - [ ] `test_default_specialty_is_general`
  - [ ] `test_accepts_valid_specialties` - parametrize ["general", "harvesting", "cracking", "spraying"]
  - [ ] `test_no_target_in_constructor`
  - [ ] `test_configurable_max_iterations`
  - [ ] `test_configurable_lockout_threshold`
  - [ ] `test_configurable_lockout_window`

- [ ] Task 1.2: Hardcoded Removal Tests (AC: #2)
  - [ ] `test_no_generate_hashcat_command`
  - [ ] `test_no_generate_hydra_command`
  - [ ] `test_no_generate_john_command`
  - [ ] `test_no_generate_mimikatz_command`
  - [ ] `test_no_tool_sequence_attribute`

- [ ] Task 1.3: Execute Method Tests (AC: #3)
  - [ ] `test_execute_credential_attack_takes_target_param`
  - [ ] `test_execute_credential_attack_calls_select_tool`
  - [ ] `test_execute_credential_attack_respects_stop_event`
  - [ ] `test_execute_credential_attack_respects_max_iterations`

- [ ] Task 1.4: NFR37 Decision Context Tests (AC: #4)
  - [ ] `test_all_actions_have_decision_context`
  - [ ] `test_decision_context_includes_spawn`
  - [ ] `test_decision_context_includes_hash_type`
  - [ ] `test_decision_context_includes_service`
  - [ ] `test_decision_context_includes_cracked_when_success`

- [ ] Task 1.5: Password Spraying Tests (AC: #5)
  - [ ] `test_password_spray_respects_lockout_threshold`
  - [ ] `test_password_spray_respects_lockout_window`
  - [ ] `test_password_spray_uses_spray_and_wait`
  - [ ] `test_password_spray_selects_appropriate_tool`
  - [ ] `test_password_spray_handles_success`
  - [ ] `test_password_spray_handles_lockout`

- [ ] Task 1.6: Hash Cracking Tests (AC: #6)
  - [ ] `test_crack_hashes_detects_ntlm`
  - [ ] `test_crack_hashes_detects_kerberos_tgs`
  - [ ] `test_crack_hashes_detects_asrep`
  - [ ] `test_crack_hashes_detects_bcrypt`
  - [ ] `test_crack_hashes_selects_hashcat_mode`
  - [ ] `test_crack_hashes_selects_john_format`
  - [ ] `test_crack_hashes_stores_cracked_credentials`

- [ ] Task 1.7: Credential Harvesting Tests (AC: #7)
  - [ ] `test_harvest_windows_uses_mimikatz`
  - [ ] `test_harvest_windows_uses_secretsdump`
  - [ ] `test_harvest_linux_parses_shadow`
  - [ ] `test_harvest_linux_collects_ssh_keys`
  - [ ] `test_harvest_web_extracts_configs`
  - [ ] `test_harvested_credentials_stored`

- [ ] Task 1.8: Stigmergic Sharing Tests (AC: #8)
  - [ ] `test_cracked_credentials_published_to_channel`
  - [ ] `test_subscribes_to_credential_channels`
  - [ ] `test_receives_kerberos_tickets_from_ad_agent`
  - [ ] `test_findings_published_to_credential_channel`

- [ ] Task 1.9: Strategy Tests (AC: #9)
  - [ ] `test_on_signal_updates_strategy` - parametrize ["stealth", "standard", "aggressive"]
  - [ ] `test_on_signal_ignores_invalid_strategy`
  - [ ] `test_get_constraints_stealth` - should limit spraying attempts
  - [ ] `test_get_constraints_aggressive` - allows full spraying

- [ ] Task 1.10: Stigmergic Hook Tests (AC: #9)
  - [ ] `test_on_finding_publishes_to_credential_channel`
  - [ ] `test_stop_sets_event`
  - [ ] `test_flush_buffer_on_reconnect`

### Phase 2: GREEN - Implement Minimal Code

- [ ] Task 2.1: Create `src/cyberred/agents/credential.py` with thin subclass pattern
- [ ] Task 2.2: Ensure constructor sets `role=AgentRole.CREDENTIAL` with configurable specialty
- [ ] Task 2.3: Implement `execute_credential_attack(target, context)` using LLM loop
- [ ] Task 2.4: Implement `_execute_password_spray(target, users, passwords)` helper
- [ ] Task 2.5: Implement `_crack_hashes(hashes, hash_type)` helper
- [ ] Task 2.6: Implement `_harvest_credentials(target, access_type)` helper
- [ ] Task 2.7: Implement hash type detection via regex patterns
- [ ] Task 2.8: Implement `_get_constraints()` with stealth awareness
- [ ] Task 2.9: Preserve stigmergic hooks

### Phase 3: REFACTOR - Optimize and Verify Coverage

- [ ] Task 3.1: Verify line count < 300
- [ ] Task 3.2: Run `ruff check src/cyberred/agents/credential.py`
- [ ] Task 3.3: Run coverage - target 100%
- [ ] Task 3.4: Create specialty prompts: `credential_harvesting.md`, `credential_cracking.md`, `credential_spraying.md`

## Dev Notes

### Thin Subclass Pattern (from agent-refactor-pattern.md)

```python
class CredentialAgent(StigmergicAgent):
    """Credential harvesting and cracking agent - thin subclass setting role=CREDENTIAL."""
    
    DEFAULT_MAX_ITERATIONS: int = 25
    DEFAULT_LOCKOUT_THRESHOLD: int = 3  # Max attempts before lockout risk
    DEFAULT_LOCKOUT_WINDOW: int = 30    # Minutes to wait between spray rounds
    
    def __init__(
        self,
        agent_id: str,
        engagement_id: str,
        event_bus: EventBus,
        specialty: str = "general",  # general, harvesting, cracking, spraying
        llm_gateway: "LLMGateway | None" = None,
        manifest_loader: "ManifestLoader | None" = None,
        max_iterations: int | None = None,
        lockout_threshold: int | None = None,
        lockout_window: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            agent_name=f"credential-agent-{specialty}",
            agent_id=agent_id,
            engagement_id=engagement_id,
            event_bus=event_bus,
            role=AgentRole.CREDENTIAL,
            specialty=specialty,
            llm_gateway=llm_gateway,
            manifest_loader=manifest_loader,
            **kwargs,
        )
        self.max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
        self.lockout_threshold = lockout_threshold or self.DEFAULT_LOCKOUT_THRESHOLD
        self.lockout_window = lockout_window or self.DEFAULT_LOCKOUT_WINDOW
        self.current_strategy = "standard"
        self._cracked_credentials: list[dict[str, Any]] = []
        self._harvested_credentials: list[dict[str, Any]] = []
        self._pending_hashes: list[dict[str, Any]] = []
        self._finding_buffer: list[dict[str, Any]] = []
        self._stop_event = asyncio.Event()
```

### Execute Method Pattern

```python
async def execute_credential_attack(
    self, target: str, context: dict[str, Any]
) -> tuple[list[Finding], list[AgentAction]]:
    """Execute LLM-driven credential attack campaign."""
    all_findings: list[Finding] = []
    all_actions: list[AgentAction] = []

    if self._stop_event.is_set():
        return [], []

    # Determine attack type based on context
    attack_type = context.get("attack_type", "auto")
    
    tool_context = ToolSelectionContext(
        objective=f"Compromise credentials on {target}",
        target_info={
            "target": target,
            "attack_type": attack_type,
            "hash_type": context.get("hash_type"),
            "hashes": context.get("hashes", []),
            "users": context.get("users", []),
            "service": context.get("service"),
            "phase": "credential",
            "strategy": self.current_strategy,
            **context
        },
        available_tools=self._get_credential_tools(),
        phase="credential",
        constraints=self._get_constraints(),
        previous_results=[],
    )

    for iteration in range(self.max_iterations):
        if self._stop_event.is_set() or await self._phase_complete(tool_context):
            break

        decision_context = self._build_decision_context(context)
        action_id = str(uuid.uuid4())
        result_finding_id: str | None = None
        tool_name = "unknown"

        try:
            selection = await self.select_tool(tool_context)
            tool_name = selection.tool_name
            result = await kali_execute(selection.command)

            if result.success and result.stdout:
                finding = self._create_finding(target, selection, result)
                all_findings.append(finding)
                await self.on_finding(finding)
                result_finding_id = finding.id
                
                # Check for cracked credentials
                await self._check_cracked_results(result, selection)
                
                # Check for harvested credentials
                await self._check_harvested_results(result, selection)

            # Update context with results
            tool_context = self._update_context(tool_context, all_findings)
        except Exception as e:
            self._log.error("credential_iteration_error", error=str(e))

        all_actions.append(AgentAction(
            id=action_id,
            agent_id=str(self.agent_id),
            action_type=f"credential:{tool_name}",
            target=target,
            timestamp=datetime.now(UTC).isoformat(),
            decision_context=decision_context,
            result_finding_id=result_finding_id,
        ))

    return all_findings, all_actions
```

### Hash Type Detection Patterns

| Hash Type | Regex Pattern | Hashcat Mode | John Format |
|-----------|---------------|--------------|-------------|
| NTLM | `^[a-fA-F0-9]{32}$` | 1000 | nt |
| LM | `^[a-fA-F0-9]{32}$` (with context) | 3000 | lm |
| NTLMv2 | `^[^:]+::[^:]+:[a-fA-F0-9]{16}:[a-fA-F0-9]{32}:` | 5600 | netntlmv2 |
| Kerberos TGS (RC4) | `\$krb5tgs\$23\$` | 13100 | krb5tgs |
| Kerberos TGS (AES256) | `\$krb5tgs\$18\$` | 19700 | krb5tgs |
| AS-REP | `\$krb5asrep\$23\$` | 18200 | krb5asrep |
| bcrypt | `^\$2[aby]?\$` | 3200 | bcrypt |
| SHA-512 (Unix) | `^\$6\$` | 1800 | sha512crypt |
| SHA-256 (Unix) | `^\$5\$` | 7400 | sha256crypt |
| MD5 (Unix) | `^\$1\$` | 500 | md5crypt |
| MySQL | `^\*[A-F0-9]{40}$` | 300 | mysql-sha1 |

### Specialty Prompts (4 required)

| Specialty | File | Focus |
|-----------|------|-------|
| general (default) | `prompts/credential.md` | Full credential attack methodology (✅ EXISTS) |
| harvesting | `prompts/credential_harvesting.md` | Credential extraction from systems (CREATE) |
| cracking | `prompts/credential_cracking.md` | Hash cracking methodology (CREATE) |
| spraying | `prompts/credential_spraying.md` | Password spraying techniques (CREATE) |

### Key Tools (from manifest)

| Tool | Purpose | Category |
|------|---------|----------|
| `hashcat` | GPU hash cracking | cracking |
| `john` | CPU hash cracking | cracking |
| `hydra` | Online password attacks | spraying |
| `crackmapexec` | Multi-protocol spraying | spraying |
| `kerbrute` | Kerberos password spraying | spraying |
| `spray` | Password spraying tool | spraying |
| `mimikatz` | Windows credential extraction | harvesting |
| `impacket-secretsdump` | Remote credential dumping | harvesting |
| `lsassy` | Remote lsass dumping | harvesting |
| `responder` | LLMNR/NBT-NS poisoning | harvesting |
| `ntlmrelayx` | NTLM relay attacks | harvesting |
| `hashid` | Hash identification | cracking |

### Stealth Constraints

When `current_strategy == "stealth"`:
- Limit password spray to 1 attempt per user per window
- Prefer offline cracking over online attacks
- Avoid triggering account lockouts
- Use wordlists with common passwords only
- No aggressive spraying patterns

When `current_strategy == "aggressive"`:
- Full password spraying (still respecting lockout_threshold)
- Rule-based cracking attacks enabled
- Aggressive wordlist combinations
- Multiple concurrent spray targets

### Stigmergic Credential Flow

```
1. ADAgent captures Kerberos tickets via Kerberoasting
2. Publishes to `credentials:{engagement_id}:kerberos`
3. CredentialAgent subscribes and receives tickets
4. Detects hash type ($krb5tgs$23$ → mode 13100)
5. Cracks via hashcat with appropriate wordlist
6. Publishes cracked credential to `credentials:{engagement_id}:cracked`
7. PostExAgent/ExploitAgent receive and use for lateral movement
```

### Anti-Patterns to Avoid

1. ❌ **Target in constructor** → Target goes in `execute_credential_attack(target, context)`
2. ❌ **Missing decision_context** → NFR37 requires ALL actions have non-empty context
3. ❌ **Hardcoded hashcat modes** → LLM selects mode based on detected hash type
4. ❌ **Ignoring lockout policies** → MUST respect lockout_threshold and lockout_window
5. ❌ **Breaking stigmergic hooks** → Preserve `on_finding()`, `on_signal()` exactly
6. ❌ **Not publishing cracked creds** → Other agents depend on credential sharing

### Project Structure

```
src/cyberred/agents/
├── base.py              # StigmergicAgent with select_tool(), generate_command()
├── credential.py        # CredentialAgent (<300 lines) - NEW
├── roles.py             # AgentRole.CREDENTIAL (✅ EXISTS)
└── prompts/
    ├── credential.md              # Base prompt (✅ EXISTS)
    ├── credential_harvesting.md   # Harvesting specialty (CREATE)
    ├── credential_cracking.md     # Cracking specialty (CREATE)
    └── credential_spraying.md     # Spraying specialty (CREATE)

tests/unit/agents/
└── test_credential_agent.py       # Unit tests (CREATE)

tests/integration/agents/
└── test_credential_agent_integration.py  # Integration tests (CREATE)
```

### Related Agent Coordination

| Agent | Publishes To | Subscribes To |
|-------|--------------|---------------|
| ADAgent | `credentials:{eid}:kerberos`, `credentials:{eid}:ad` | - |
| PostExAgent | `credentials:{eid}:postex` | `credentials:{eid}:cracked` |
| CredentialAgent | `credentials:{eid}:cracked` | `credentials:{eid}:*` |
| ExploitAgent | - | `credentials:{eid}:cracked` |

### References

| Document | Relevance |
|----------|-----------|
| `agent-refactor-pattern.md` | **MANDATORY PATTERN** |
| `7-21-active-directory-agent.md` | Reference implementation (same pattern) |
| `src/cyberred/agents/ad.py` | Code reference (~222 lines) |
| `epic-7-agent-refactor-proposal.md` lines 942-979 | Story definition |
| `tests/unit/agents/test_ad_agent.py` | Test pattern reference |

### Previous Story Intelligence

From **7-21-active-directory-agent.md** (completed):
- Constructor pattern with configurable thresholds works well
- Target as method parameter, not constructor
- Specialty prompts required for each variant
- Decision context must include role-specific information
- Credential publication to stigmergic channels is critical

From **7-20-wireless-agent.md** (completed):
- 59 unit tests achieved 98.97% coverage - target 100%
- Strategy-aware constraints pattern works well
- Lockout/safety parameters should be class constants with defaults

## Definition of Done

### Code Requirements
- [ ] Thin subclass (<300 lines)
- [ ] `role=AgentRole.CREDENTIAL` in constructor
- [ ] `specialty` param (default: "general", valid: general/harvesting/cracking/spraying)
- [ ] NO `_generate_*_command()` methods, NO `tool_sequence`
- [ ] `execute_credential_attack(target, context)` uses inherited `select_tool()`
- [ ] Password spraying respects lockout policies
- [ ] Hash cracking with auto-detection
- [ ] Credential harvesting for Windows/Linux/Web
- [ ] ALL AgentActions have non-empty `decision_context` (NFR37)
- [ ] Stigmergic credential sharing implemented
- [ ] Configurable `max_iterations`, `lockout_threshold`, `lockout_window`

### Quality Gates (HARD)
- [ ] **100% test coverage** on `credential.py`
- [ ] `ruff check` passes with no errors
- [ ] All unit tests pass
- [ ] All integration tests pass

### Prompt Files
- [ ] `credential.md` exists (base prompt) ✅
- [ ] `credential_harvesting.md` created
- [ ] `credential_cracking.md` created
- [ ] `credential_spraying.md` created

## Validation Commands

```bash
# Full validation
source venv/bin/activate
wc -l src/cyberred/agents/credential.py  # MUST be <300
grep -c "_generate_\|tool_sequence" src/cyberred/agents/credential.py || echo "0"  # MUST be 0
pytest tests/unit/agents/test_credential_agent.py --cov=src/cyberred/agents/credential --cov-fail-under=100 -q
ruff check src/cyberred/agents/credential.py
```

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

**Existing Files:**
- src/cyberred/agents/roles.py (AgentRole.CREDENTIAL exists)
- src/cyberred/agents/prompts/credential.md (base prompt exists)

**New Files to Create:**
- src/cyberred/agents/credential.py
- tests/unit/agents/test_credential_agent.py
- tests/integration/agents/test_credential_agent_integration.py
- src/cyberred/agents/prompts/credential_harvesting.md
- src/cyberred/agents/prompts/credential_cracking.md
- src/cyberred/agents/prompts/credential_spraying.md

## Change Log

| Date | Change |
|------|--------|
| 2026-01-26 | Story file created - ready-for-dev |
