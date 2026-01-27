# Story 7.5.v2: PostExAgent LLM-Driven Refactor

**Epic:** Epic 7 - Agent Framework & Stigmergic Coordination  
**Priority:** P0 (CRITICAL PATH - Emergence Hard Gate)  
**Status:** done  
**Effort:** 8 story points  
**Dependencies:** Story 7.1.v2 (StigmergicAgent LLM Selection) ✅ DONE, Story 7.18 (AgentRole + PromptLibrary) ✅ DONE  
**Blocks:** 7.6 (Swarm Router Integration), Epic 15 (E2E Validation)

---

## Story

As a **penetration tester using Cyber-Red**,
I want the PostExAgent to intelligently select post-exploitation tools from the full 1,556+ tool manifest using LLM reasoning based on access context and privilege level,
so that the swarm can adapt lateral movement and persistence strategies to novel situations and achieve the emergence required by NFR35-37.

## Acceptance Criteria

### AC1: Thin Subclass Architecture
- PostExAgent is a thin subclass of StigmergicAgent (<300 lines)
- Constructor sets `role=AgentRole.POSTEX`
- Constructor accepts `specialty` parameter (default: "linux", valid: "linux", "windows", "ad")
- NO `target` or `access_data` in constructor (passed to `execute_postex()`)

### AC2: Hardcoded Methods REMOVED
- NO `_generate_linpeas_command()` method
- NO `_generate_winpeas_command()` method
- NO `_generate_bloodhound_command()` method
- NO `_generate_mimikatz_command()` method
- NO `_generate_lazagne_command()` method
- NO `_generate_psexec_command()` method
- NO `_generate_wmiexec_command()` method
- NO `_generate_smbexec_command()` method
- NO `_generate_evilwinrm_command()` method
- NO `_generate_privesc_command()` method
- All commands generated via inherited `select_tool()` and LLM

### AC3: LLM-Driven Tool Selection
- `execute_postex(target, access_data)` uses inherited `select_tool()` from StigmergicAgent
- LLM selects from full manifest based on OS type, privilege level, and access type
- Tool commands generated via LLM using `--help` output (inherited `generate_command()`)

### AC4: NFR37 Decision Context (HARD GATE)
- ALL AgentActions have non-empty `decision_context`
- Minimum context: `initial_spawn:{agent_id}`
- Intel context added when available: `intel:{source}:{cve_id}`
- RAG context added on escalation: `rag:{failed_technique}:{alternative}`
- Authorization context added: `auth:{request_id}:{granted|denied}`

### AC5: Preserved Functionality
- Intelligence integration preserved (`_query_intelligence()`, `_select_technique()`)
- RAG escalation preserved (`_handle_postex_failure()` after 3+ failures)
- Authorization flow preserved (`_request_authorization()` for lateral movement - FR13)
- Stigmergic hooks preserved (`on_finding()`, `on_signal()`, `_flush_buffer()`, `stop()`)
- Scope validation preserved (via `_validate_target_scope()`)

### AC6: Strategy Handling
- `on_signal()` handles Director strategy updates (stealth/standard/aggressive)
- Strategy influences tool selection context (passed to LLM)

### AC7: Quality Gates (HARD REQUIREMENTS)
- **100% test coverage** on `postex.py` - `pytest --cov=src/cyberred/agents/postex --cov-fail-under=100`
- `ruff check` passes with no errors
- All unit tests pass
- All integration tests pass (with mocked `kali_execute`)

## Tasks / Subtasks

### Phase 1: RED - Write Failing Tests First (TDD)

- [x] Task 1.1: Constructor Tests (AC: #1)
  - [x] `test_sets_role_to_postex` - assert `agent.role == AgentRole.POSTEX`
  - [x] `test_default_specialty_is_linux` - assert `agent.specialty == "linux"`
  - [x] `test_accepts_windows_specialty` - parametrize `["linux", "windows", "ad"]`
  - [x] `test_no_target_in_constructor` - assert `not hasattr(agent, 'target')`
  - [x] `test_no_access_data_in_constructor` - assert `not hasattr(agent, 'access_data')`
  - [x] `test_loads_prompt_from_library` - verified via base class inheritance

- [x] Task 1.2: Hardcoded Removal Tests (AC: #2)
  - [x] `test_no_generate_linpeas_command` - `assert not hasattr(PostExAgent, '_generate_linpeas_command')`
  - [x] All 16 hardcoded methods verified removed via hasattr tests

- [x] Task 1.3: Execute Method Tests (AC: #3)
  - [x] `test_execute_postex_takes_target_and_access_data_params`
  - [x] `test_execute_postex_calls_select_tool` - mock `select_tool`, verify called
  - [x] `test_execute_postex_respects_stop_event` - set `_stop_event`, assert returns `([], [])`
  - [x] `test_execute_postex_validates_scope` - verify `_validate_target_scope()` called
  - [x] `test_execute_postex_loops_until_phase_complete`
  - [x] `test_execute_postex_respects_max_iterations`

- [x] Task 1.4: NFR37 Decision Context Tests (AC: #4)
  - [x] `test_all_actions_have_decision_context` - `assert all(a.decision_context for a in actions)`
  - [x] `test_decision_context_includes_spawn` - `assert any("initial_spawn" in c for c in dc)`
  - [x] `test_decision_context_includes_intel_when_available`
  - [x] `test_decision_context_includes_rag_on_escalation`
  - [x] `test_decision_context_includes_auth_result`

- [x] Task 1.5: Preserved Functionality Tests (AC: #5)
  - [x] `test_query_intelligence_preserved`
  - [x] `test_select_technique_preserved`
  - [x] `test_handle_postex_failure_triggers_rag_after_3_failures`
  - [x] `test_request_authorization_for_lateral_movement`
  - [x] `test_on_finding_publishes_to_postex_channel`
  - [x] `test_on_signal_handles_strategy_update`
  - [x] `test_flush_buffer_on_redis_reconnect`
  - [x] `test_stop_sets_event_and_flushes`

- [x] Task 1.6: Strategy Tests (AC: #6)
  - [x] `test_on_signal_updates_strategy_stealth`
  - [x] `test_on_signal_updates_strategy_aggressive`
  - [x] `test_on_signal_ignores_invalid_strategy`
  - [x] `test_strategy_passed_to_tool_selection_context`

### Phase 2: GREEN - Implement Minimal Code

- [x] Task 2.1: Refactor Constructor (~50 lines max)
  - [x] Remove `target` parameter
  - [x] Remove `access_data` parameter
  - [x] Add `role=AgentRole.POSTEX` to super().__init__()
  - [x] Add `specialty` parameter (default: "linux")
  - [x] Add `max_iterations` and `phase_complete_threshold` class constants
  - [x] Keep `intel_aggregator` and `rag_escalator` injection points

- [x] Task 2.2: Delete Hardcoded Methods (~950 lines removed)
  - [x] All 16 hardcoded `_generate_*` methods deleted
  - [x] `_detect_privesc_opportunities()` deleted
  - [x] `_attempt_privesc()` deleted
  - [x] `_execute_privesc_technique()` deleted
  - [x] `_parse_enumeration_discoveries()` deleted
  - [x] `_extract_credentials()` deleted
  - [x] `_register_parsers()` deleted

- [x] Task 2.3: Refactor execute_postex() (~80 lines)
  - [x] Change signature to `execute_postex(self, target: str, access_data: dict)`
  - [x] Add scope validation via `self._validate_target_scope(target)`
  - [x] Build `ToolSelectionContext` with access_data, os_type, privilege_level
  - [x] Use inherited `select_tool(context)` in loop
  - [x] Preserve intelligence query integration
  - [x] Preserve RAG escalation flow
  - [x] Preserve authorization flow for lateral movement
  - [x] Create AgentAction with decision_context for each iteration

- [x] Task 2.4: Preserve Essential Methods
  - [x] Keep `_query_intelligence()` - AC5
  - [x] Keep `_select_technique()` - AC5
  - [x] Keep `_handle_postex_failure()` - AC5 (RAG escalation)
  - [x] Keep `_request_authorization()` - AC5 (FR13)
  - [x] Keep `on_finding()` - stigmergic publishing
  - [x] Keep `on_signal()` - strategy updates
  - [x] Keep `_flush_buffer()` - ERR3 pattern
  - [x] Keep `stop()` - graceful shutdown
  - [x] Keep `_hash_target()` - utility
  - [x] Keep `_generate_finding_signature()` - HMAC integrity

- [x] Task 2.5: Ensure NFR37 Compliance
  - [x] Capture decision_context BEFORE each action
  - [x] Include `initial_spawn:{agent_id}` as minimum
  - [x] Include intel context when available
  - [x] Include RAG context on escalation
  - [x] Include auth context on lateral movement

### Phase 3: REFACTOR - Optimize and Verify Coverage

- [x] Task 3.1: Code Quality
  - [x] File is 248 lines (<300 target) - 79% reduction from 1,198
  - [x] `ruff check` passes with no errors

- [x] Task 3.2: Coverage Verification
  - [x] 87 unit tests passing
  - [x] 100% coverage on postex.py
  - [x] All edge cases tested

- [x] Task 3.3: Integration Tests Update
  - [x] Update integration tests to use new API: `execute_postex(target, access_data)`
  - [x] Mock `kali_execute` (no testcontainers per pattern)
  - [x] Run: `pytest tests/integration/agents/test_postex_agent_integration.py -v`

## Dev Notes

### Code Reduction Target

| Metric | Current | Target | Reduction |
|--------|---------|--------|-----------|
| Lines | 1197 | <300 | **75%+** |
| `_generate_*` methods | 10 | 0 | 100% |
| Hardcoded tool logic | ~600 lines | 0 | 100% |

### Methods to DELETE (Hardcoded - ~600 lines)

```python
# DELETE ALL OF THESE - replaced by inherited select_tool() + LLM
_generate_linpeas_command()      # 14 lines
_generate_winpeas_command()      # 12 lines
_generate_bloodhound_command()   # 14 lines
_generate_mimikatz_command()     # 7 lines
_generate_lazagne_command()      # 10 lines
_generate_psexec_command()       # 15 lines
_generate_wmiexec_command()      # 15 lines
_generate_smbexec_command()      # 15 lines
_generate_evilwinrm_command()    # 12 lines
_generate_privesc_command()      # 29 lines
_detect_privesc_opportunities()  # 61 lines
_attempt_privesc()               # 34 lines
_execute_privesc_technique()     # 27 lines
_parse_enumeration_discoveries() # 59 lines
_extract_credentials()           # 27 lines
_register_parsers()              # 25 lines
```

### Methods to PRESERVE (Essential - ~150 lines)

```python
# KEEP - Intelligence/RAG/Auth (exploit-specific logic)
_query_intelligence()           # ~35 lines - AC5
_select_technique()             # ~20 lines - AC5
_handle_postex_failure()        # ~60 lines - RAG escalation
_request_authorization()        # ~55 lines - FR13 lateral movement auth

# KEEP - Stigmergic hooks (unchanged)
on_finding()                    # ~30 lines
on_signal()                     # ~20 lines
_flush_buffer()                 # ~15 lines
stop()                          # ~10 lines

# KEEP - Utilities
_hash_target()                  # ~5 lines
_generate_finding_signature()   # ~5 lines
_create_finding()               # ~25 lines
```

### Thin Subclass Pattern (from agent-refactor-pattern.md)

```python
class PostExAgent(StigmergicAgent):
    """Post-exploitation agent - thin subclass setting role=POSTEX."""
    
    DEFAULT_MAX_ITERATIONS: int = 15
    DEFAULT_PHASE_COMPLETE_THRESHOLD: int = 50
    
    def __init__(
        self,
        agent_id: str,
        engagement_id: str,
        event_bus: EventBus,
        specialty: str = "linux",  # linux, windows, ad
        llm_gateway: LLMGateway | None = None,
        manifest_loader: ManifestLoader | None = None,
        intel_aggregator: CachedIntelligenceAggregator | None = None,
        rag_escalator: AgentRAGEscalator | None = None,
        max_iterations: int | None = None,
        phase_complete_threshold: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            agent_name="PostExAgent",
            agent_id=agent_id,
            engagement_id=engagement_id,
            event_bus=event_bus,
            role=AgentRole.POSTEX,
            specialty=specialty,
            llm_gateway=llm_gateway,
            manifest_loader=manifest_loader,
            **kwargs,
        )
        self._intel_aggregator = intel_aggregator
        self._rag_escalator = rag_escalator
        self.max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
        self.phase_complete_threshold = phase_complete_threshold or self.DEFAULT_PHASE_COMPLETE_THRESHOLD
        self._failure_counts: dict[str, int] = {}
```

### execute_postex() Pattern

```python
async def execute_postex(
    self, target: str, access_data: dict[str, Any]
) -> tuple[list[Finding], list[AgentAction]]:
    """LLM-driven post-exploitation. Target as parameter, NOT constructor."""
    self._validate_target_scope(target)
    
    # Extract access context
    os_type = access_data.get("os_type", "linux")
    privilege_level = access_data.get("privilege_level", "user")
    access_type = access_data.get("access_type", "shell")
    
    # Query intelligence
    intel = await self._select_technique(
        await self._query_intelligence(os_type, access_type)
    )
    
    context = ToolSelectionContext(
        objective=f"Post-exploitation on {os_type} system",
        target_info={
            "target": target,
            "phase": "postex",
            "strategy": self.current_strategy,
            "os_type": os_type,
            "privilege_level": privilege_level,
            "access_type": access_type,
            "intel": intel,
        },
        phase="postex",
        constraints=self._get_constraints(),
        previous_results=[],
    )
    
    all_findings, all_actions = [], []
    
    for iteration in range(self.max_iterations):
        if self._stop_event.is_set():
            break
        if await self._phase_complete(context):
            break
        
        # NFR37: Capture decision context BEFORE action
        decision_context = self.get_decision_context().copy() or [f"initial_spawn:{self.agent_id}"]
        if intel:
            decision_context.append(f"intel:{intel.source}:{intel.cve_id or 'unknown'}")
        
        try:
            selection = await self.select_tool(context)  # Inherited from base
            result = await kali_execute(selection.command)
            
            # Process result and create findings
            if result.success:
                # ... process output, create findings
                pass
            else:
                alt = await self._handle_postex_failure(selection.tool_name)
                if alt:
                    decision_context.append(f"rag:{selection.tool_name}:{alt}")
                    
        except Exception as e:
            self._log.error("postex_iteration_error", error=str(e))
        
        # Create AgentAction with decision_context (NFR37)
        action = AgentAction(
            id=str(uuid.uuid4()),
            agent_id=str(self.agent_id),
            action_type=f"postex:{selection.tool_name if 'selection' in locals() else 'unknown'}",
            target=target,
            timestamp=datetime.now(UTC).isoformat(),
            decision_context=decision_context,
            result_finding_id=all_findings[-1].id if all_findings else None,
        )
        all_actions.append(action)
    
    return all_findings, all_actions
```

### Specialty Prompts (3 required - all exist)

| Specialty | File | Focus |
|-----------|------|-------|
| linux (default) | `prompts/postex_linux.md` | Linux privesc, enumeration |
| windows | `prompts/postex_windows.md` | Windows privesc, credential dumping |
| ad | `prompts/postex.md` | Active Directory, lateral movement |

### Architecture References

| Requirement | Reference | Implementation |
|-------------|-----------|----------------|
| FR4 | Stigmergic P2P coordination | Preserves `on_finding()`, `on_signal()` |
| FR13 | Lateral movement authorization | Preserves `_request_authorization()` |
| FR31 | 600+ tools via `kali_execute()` | Full manifest via inherited `select_tool()` |
| FR32 | LLM-generated commands | Inherited `generate_command()` |
| FR62 | decision_context logging | All actions have non-empty context |
| NFR35 | >20% novel attack chains | LLM selection enables diversity |
| NFR37 | 100% decision_context | HARD GATE - verified in tests |
| ERR3 | Redis reconnect pattern | Preserved `_flush_buffer()` |

### Anti-Patterns to Avoid (from agent-refactor-pattern.md)

1. ❌ **Target in constructor** → Target goes in `execute_postex(target, access_data)`
2. ❌ **Missing decision_context** → NFR37 requires ALL actions have non-empty context
3. ❌ **Hardcoded iteration limits** → Use configurable class constants
4. ❌ **Using testcontainers directly** → Mock `kali_execute` in integration tests
5. ❌ **Forgetting prompt files** → All 3 specialty prompts exist
6. ❌ **Breaking stigmergic hooks** → Preserve `on_finding()`, `on_signal()` exactly
7. ❌ **Breaking authorization flow** → FR13 requires `_request_authorization()` for lateral movement

### Previous Story Learnings

**From Story 7.3-v2 (ReconAgent Refactor):**
- Reduced from 349→255 lines (27% reduction)
- 100% coverage achieved with 57 unit tests
- All 4 specialties supported
- Target passed to `execute_recon(target)` NOT constructor

**From Story 7.4-v2 (ExploitAgent Refactor):**
- Reduced from 796→240 lines (70% reduction)
- 100% coverage achieved with 71 unit tests
- Preserved intelligence and RAG integration
- Target passed to `execute_exploit(target, vuln_data)` NOT constructor

### Project Structure Notes

```
src/cyberred/agents/
├── base.py              # StigmergicAgent with select_tool(), generate_command()
├── postex.py            # PostExAgent (<300 lines after refactor)
├── roles.py             # AgentRole.POSTEX
└── prompts/
    ├── postex.md        # Base/AD prompt
    ├── postex_linux.md  # Linux specialty
    └── postex_windows.md # Windows specialty

tests/unit/agents/
├── test_postex_agent.py     # Original tests (may need update)
└── test_postex_agent_v2.py  # NEW v2 coverage tests

tests/integration/agents/
└── test_postex_agent_integration.py  # Update API calls
```

### References

| Document | Section | Relevance |
|----------|---------|-----------|
| `agent-refactor-pattern.md` | Full doc | **MANDATORY PATTERN** |
| `7-4-v2-exploit-agent-refactor.md` | Full doc | Reference implementation |
| `7-3-v2-recon-agent-refactor.md` | Full doc | First refactor blueprint |
| `7-1-v2-stigmergic-agent-llm-selection.md` | Full doc | Base class with `select_tool()` |
| `architecture.md` | Lines 793-800 | Agent directory structure |
| `architecture.md` | Lines 559-567 | Naming conventions |
| `epics-stories.md` | Lines 2860+ | Original story definition |
| `src/cyberred/agents/postex.py` | Full file | Current 1197-line implementation |

## Definition of Done

### Code Requirements
- [x] Agent is thin subclass (**248 lines** - 79% reduction from 1,198)
- [x] Constructor sets `role=AgentRole.POSTEX`
- [x] Constructor accepts `specialty` parameter (default: "linux")
- [x] NO hardcoded `_generate_*_command()` methods (all 16 deleted)
- [x] `execute_postex()` takes `target` and `access_data` as parameters (NOT constructor)
- [x] `execute_postex()` uses inherited `select_tool()`
- [x] All existing stigmergic hooks preserved (`on_finding()`, `on_signal()`, `_flush_buffer()`, `stop()`)
- [x] All existing intelligence integration preserved (`_query_intelligence()`, `_select_technique()`)
- [x] All existing RAG escalation preserved (`_handle_postex_failure()`)
- [x] All existing authorization preserved (`_request_authorization()` - FR13)
- [x] All AgentActions have non-empty `decision_context` (NFR37)
- [x] Configurable `max_iterations` and `phase_complete_threshold`

### Quality Gates (HARD REQUIREMENTS)
- [x] **100% test coverage** on `postex.py` (87 tests passing)
- [x] `ruff check` passes with no errors
- [x] All unit tests pass: `pytest tests/unit/agents/test_postex_agent_v2.py -v`
- [x] All integration tests pass (with mocked `kali_execute`) - 14 tests passing

### Prompt Files (Already Exist)
- [x] `postex.md` - Base/AD prompt
- [x] `postex_linux.md` - Linux specialty
- [x] `postex_windows.md` - Windows specialty

## Validation Commands

```bash
# Full validation - run all before marking done
source venv/bin/activate && \
  echo "=== PostExAgent Refactor Validation ===" && \
  echo "1. Line count (MUST be <300):" && \
  wc -l src/cyberred/agents/postex.py && \
  echo "2. Hardcoded methods (should be 0):" && \
  grep -c "_generate_linpeas\|_generate_winpeas\|_generate_bloodhound\|_generate_mimikatz\|_generate_lazagne\|_generate_psexec\|_generate_wmiexec\|_generate_smbexec\|_generate_evilwinrm\|_generate_privesc" src/cyberred/agents/postex.py || echo "0" && \
  echo "3. Coverage (MUST be 100%):" && \
  pytest tests/unit/agents/test_postex_agent*.py --cov=src/cyberred/agents/postex --cov-report=term-missing -q 2>&1 | grep "src/cyberred/agents/postex.py" && \
  echo "4. Ruff check:" && \
  ruff check src/cyberred/agents/postex.py && \
  echo "5. Role validation:" && \
  python -c "
from cyberred.agents.postex import PostExAgent
from cyberred.agents.roles import AgentRole
from unittest.mock import MagicMock
agent = PostExAgent(agent_id='test', engagement_id='test', event_bus=MagicMock())
assert agent.role == AgentRole.POSTEX, 'Role must be POSTEX'
print('PASS: role=AgentRole.POSTEX')
" && \
  echo "6. No target in constructor:" && \
  python -c "
from cyberred.agents.postex import PostExAgent
from unittest.mock import MagicMock
agent = PostExAgent(agent_id='test', engagement_id='test', event_bus=MagicMock())
assert not hasattr(agent, 'target'), 'target should NOT be in constructor'
print('PASS: target not in constructor')
" && \
  echo "7. Integration tests:" && \
  pytest tests/integration/agents/test_postex_agent_integration.py -v --tb=short
```

## Dev Agent Record

### Agent Model Used

Claude claude-sonnet-4-20250514

### Debug Log References

### Completion Notes List

- Refactored `postex.py` from 1,198 lines to 248 lines (79% reduction)
- Removed all 16 hardcoded `_generate_*` methods
- Implemented thin subclass pattern with `role=AgentRole.POSTEX`
- `execute_postex()` now takes `target` and `access_data` as parameters (not constructor)
- Uses inherited `select_tool()` for LLM-driven tool selection
- Preserved all essential methods: intelligence, RAG, authorization, stigmergic hooks
- Created `test_postex_agent_v2.py` with 87 tests (100% coverage)
- All unit tests passing, all 14 integration tests passing, ruff check passing
- Deleted obsolete `test_postex_agent.py` (tested deleted methods)
- Updated integration tests to use v2 API: `execute_postex(target, access_data)`

### File List

- `src/cyberred/agents/postex.py` - Refactored thin subclass implementation (248 lines)
- `tests/unit/agents/test_postex_agent_v2.py` - v2 unit test suite (87 tests, 100% coverage)
- `tests/integration/agents/test_postex_agent_integration.py` - Updated integration tests (14 tests)
- `tests/unit/agents/test_postex_agent.py` - DELETED (obsolete, tested deleted methods)

### Change Log

- 2026-01-21: Completed PostExAgent v2 refactor - LLM-driven tool selection
- 2026-01-21: Code review fixes - achieved 100% coverage, fixed integration tests, deleted obsolete tests
