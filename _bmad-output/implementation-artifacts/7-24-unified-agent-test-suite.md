# Story 7.24: Unified Agent Test Suite

Status: done

## Story

As a **developer**,
I want **a unified test suite for all 8 agent types**,
so that **agent behavior is consistently validated with one testing pattern**.

## Acceptance Criteria

1. **Protocol compliance tests for all 8 agent types**
   - All agents pass `isinstance(agent, AgentProtocol)` check at runtime.
   - Parametrized tests cover: RECON, EXPLOIT, POSTEX, WEBAPP, WIRELESS, AD, CREDENTIAL, FORENSICS.
   - Tests verify each agent implements: `execute()`, `reason()`, `get_id()`, `get_status()`, `get_decision_context()`, `shutdown()`.

2. **Instantiation tests with role and specialty**
   - All agents can be instantiated with their correct `AgentRole`.
   - All agents accept optional `specialty` parameter.
   - Constructor correctly sets `role` and `specialty` attributes.
   - Constructor calls `PromptLibrary.get(role, specialty)` for system prompt.

3. **LLM tool selection tests with mock LLM responses**
   - Mock LLM gateway returns deterministic tool selection responses.
   - `select_tool()` correctly parses mock LLM JSON responses.
   - `generate_command()` uses cached `--help` output from mock executor.
   - Tool selection respects role-specific categories from `ROLE_CATEGORIES`.

4. **Command generation validation for each agent type**
   - Each agent type can generate valid commands for their domain tools.
   - Commands are validated (must start with tool name).
   - Help cache is populated and reused within session.

5. **Parametrized tests cover all 8 roles**
   - Single test function with `@pytest.mark.parametrize("role", list(AgentRole))`.
   - Factory function `create_agent(role)` creates appropriate agent subclass.
   - Tests verify thin subclass pattern (agent sets correct role).

6. **Integration tests verify LLM tool selection with real LLM (optional CI gate)**
   - Integration tests use real LLM gateway (when available).
   - Tests are skipped gracefully when LLM is unavailable.
   - Tests verify end-to-end tool selection flow.

7. **100% test coverage for unified test utilities**
   - Coverage for test factory functions and fixtures.
   - Coverage for parametrized test execution paths.

## Tasks / Subtasks

### Phase 1 (RED): Write failing tests first

- [x] Create unified test file: `tests/unit/agents/test_unified_agent_suite.py`
  - [x] Import all 8 agent types and AgentProtocol
  - [x] Create `create_agent(role: AgentRole)` factory function
  - [x] Write `test_agent_protocol_compliance(role)` parametrized test (AC #1)
  - [x] Write `test_agent_instantiation_with_role(role)` parametrized test (AC #2)
  - [x] Write `test_agent_accepts_specialty(role)` parametrized test (AC #2)
  - [x] Write `test_agent_loads_prompt_from_library(role)` parametrized test (AC #2)
  - [x] Write `test_agent_tool_selection_with_mock_llm(role)` parametrized test (AC #3)
  - [x] Write `test_agent_command_generation(role)` parametrized test (AC #4)
  - [x] Write `test_all_roles_have_correct_subclass()` test (AC #5)

- [x] Create integration test file: `tests/integration/agents/test_unified_agent_integration.py`
  - [x] Write `test_agent_llm_tool_selection_real(role)` parametrized test (AC #6)
  - [x] Add skip markers for when LLM is unavailable
  - [ ] Write `test_agent_event_bus_integration(role)` parametrized test (FOLLOW-UP)

### Phase 2 (GREEN): Implement minimal test utilities

- [x] Implement factory function in `tests/unit/agents/test_unified_agent_suite.py`
  - [x] Map `AgentRole` to agent class (ReconAgent, ExploitAgent, etc.)
  - [x] Create agent with mocked dependencies (event_bus, llm_gateway)
  - [x] Return properly configured agent instance

- [x] Implement shared fixtures in `tests/conftest.py` or local conftest
  - [x] `mock_event_bus` fixture
  - [x] `mock_llm_gateway` fixture with deterministic responses
  - [x] `mock_manifest_loader` fixture
  - [x] `mock_kali_execute` fixture

- [x] Run tests and verify all pass (183 tests passed)

### Phase 3 (REFACTOR): Achieve 100% coverage and cleanup

- [x] Targeted coverage runs:
  - [x] `pytest tests/unit/agents/test_unified_agent_suite.py --cov=src/cyberred/agents --cov-report=term-missing`
  - [x] `pytest tests/integration/agents/test_unified_agent_integration.py --cov=src/cyberred/agents --cov-report=term-missing`

- [x] Add any missing edge case tests for full coverage
- [x] Ensure no duplicate tests with existing agent test files
- [x] Document test patterns in docstrings

## Dev Notes

### Agent Type to Class Mapping

```python
from cyberred.agents import (
    ReconAgent, ExploitAgent, PostExAgent, WebAppAgent,
    WirelessAgent, ADAgent, CredentialAgent, ForensicsAgent,
    AgentRole,
)

AGENT_CLASS_MAP: dict[AgentRole, type] = {
    AgentRole.RECON: ReconAgent,
    AgentRole.EXPLOIT: ExploitAgent,
    AgentRole.POSTEX: PostExAgent,
    AgentRole.WEBAPP: WebAppAgent,
    AgentRole.WIRELESS: WirelessAgent,
    AgentRole.AD: ADAgent,
    AgentRole.CREDENTIAL: CredentialAgent,
    AgentRole.FORENSICS: ForensicsAgent,
}
```

### Factory Function Pattern

```python
def create_agent(role: AgentRole, **overrides) -> StigmergicAgent:
    """Factory function to create agent of specified role.
    
    Args:
        role: AgentRole enum value.
        **overrides: Optional kwargs to override defaults.
        
    Returns:
        Agent instance of the appropriate subclass.
    """
    agent_class = AGENT_CLASS_MAP[role]
    defaults = {
        "agent_id": str(uuid.uuid4()),
        "engagement_id": "test-engagement",
        "event_bus": mock_event_bus,
        # Other required params...
    }
    defaults.update(overrides)
    return agent_class(**defaults)
```

### Parametrized Test Pattern

```python
@pytest.mark.parametrize("role", list(AgentRole))
def test_agent_protocol_compliance(role: AgentRole, mock_event_bus):
    """All agents must implement AgentProtocol."""
    from cyberred.protocols import AgentProtocol
    
    agent = create_agent(role, event_bus=mock_event_bus)
    
    # Runtime checkable protocol
    assert isinstance(agent, AgentProtocol)
    
    # Method existence
    assert hasattr(agent, "execute")
    assert hasattr(agent, "reason")
    assert hasattr(agent, "get_id")
    assert hasattr(agent, "get_status")
    assert hasattr(agent, "get_decision_context")
    assert hasattr(agent, "shutdown")
```

### Mock LLM Response for Tool Selection

```python
MOCK_TOOL_SELECTION_RESPONSE = json.dumps({
    "tool_name": "nmap",
    "command": "nmap -sV -sC 192.168.1.1",
    "rationale": "Service version detection for target enumeration",
    "expected_output_type": "xml",
    "confidence": 0.9,
    "priority": 5,
    "alternatives": ["masscan", "rustscan"],
})
```

### Existing Test Files (DO NOT DUPLICATE)

The following test files already exist and should NOT be duplicated:
- `tests/unit/agents/test_stigmergic_base.py` - Base class tests
- `tests/unit/agents/test_roles.py` - AgentRole enum tests
- `tests/unit/agents/test_recon_agent.py` - ReconAgent specific tests
- `tests/unit/agents/test_exploit_agent_v2.py` - ExploitAgent specific tests
- `tests/unit/agents/test_postex_agent_v2.py` - PostExAgent specific tests
- `tests/unit/agents/test_webapp_agent.py` - WebAppAgent specific tests
- `tests/unit/agents/test_wireless_agent.py` - WirelessAgent specific tests
- `tests/unit/agents/test_ad_agent.py` - ADAgent specific tests
- `tests/unit/agents/test_credential_agent.py` - CredentialAgent specific tests
- `tests/unit/agents/test_forensics_agent.py` - ForensicsAgent specific tests

The unified test suite should focus on **cross-agent consistency** tests that verify
all agents behave the same way for common operations, not duplicate individual tests.

### Project Structure Notes

- Test files location: `tests/unit/agents/` and `tests/integration/agents/`
- Agent source: `src/cyberred/agents/`
- Protocol definition: `src/cyberred/protocols/agent.py`
- Role enum: `src/cyberred/agents/roles.py`
- Base class: `src/cyberred/agents/base.py`

### Key Dependencies

- `pytest` for test framework
- `pytest-asyncio` for async test support
- `pytest-cov` for coverage reporting
- `unittest.mock` for mocking

### References

- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 7.24 lines 3446-3474]
- [Source: src/cyberred/protocols/agent.py - AgentProtocol definition]
- [Source: src/cyberred/agents/roles.py - AgentRole enum with 8 values]
- [Source: src/cyberred/agents/base.py - StigmergicAgent base class]
- [Source: _bmad-output/implementation-artifacts/agent-refactor-pattern.md - Thin subclass pattern]
- [Source: tests/unit/agents/test_stigmergic_base.py - Existing protocol compliance test pattern]

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

- Unit tests: 183 passed in 22.39s
- Integration tests: Created with skip markers for LLM unavailability

### Completion Notes List

- All 8 agent types tested for protocol compliance (AC #1)
- Instantiation with role/specialty verified (AC #2)
- Mock LLM tool selection tests implemented (AC #3)
- Command generation and validation tests implemented (AC #4)
- Parametrized tests cover all 8 AgentRole values (AC #5)
- Integration tests created with graceful skip when LLM unavailable (AC #6)
- Factory function and fixtures achieve test utility coverage (AC #7)
- FOLLOW-UP: `test_agent_event_bus_integration(role)` not implemented

### Senior Developer Review (AI)

**Reviewed:** 2026-01-28
**Outcome:** Approved with fixes applied

**Issues Found and Fixed:**
1. ✅ Created missing integration test file (AC #6)
2. ✅ Updated story status from `ready-for-dev` to `done`
3. ✅ Marked all completed tasks as `[x]`
4. ✅ Added AC #6 to docstring coverage note
5. ✅ Fixed magic number - added `VALID_AGENT_STATUSES` constant
6. ✅ Documented File List

**Follow-up Items:**
- [ ] `test_agent_event_bus_integration(role)` - Event bus integration test not implemented

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-28 | Initial implementation - 183 unit tests | Dev Agent |
| 2026-01-28 | Code review fixes - added integration tests, updated tasks | Code Review |

### File List

- `tests/unit/agents/test_unified_agent_suite.py` (NEW) - 650 lines, 183 tests
- `tests/integration/agents/test_unified_agent_integration.py` (NEW) - 160 lines, integration tests with skip markers

