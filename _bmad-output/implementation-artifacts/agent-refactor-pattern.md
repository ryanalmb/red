# Agent LLM-Driven Refactor Pattern (v2)

> **STRICT PATTERN** - All agent refactors (7.3-v2, 7.4-v2, 7.5-v2, etc.) MUST follow this pattern exactly.

## Overview

This document defines the mandatory pattern for refactoring agents from hardcoded tool sequences to LLM-driven tool selection. This pattern was established during story 7.3-v2 (ReconAgent) and is **required** for all subsequent agent refactors.

---

## Pattern Requirements

### 1. Thin Subclass Architecture (~50-100 lines ideal, <300 max)

The refactored agent MUST be a thin subclass of `StigmergicAgent`:

```python
class RefactoredAgent(StigmergicAgent):
    """Thin subclass - role-specific configuration only."""
    
    # Class constants for configurability
    DEFAULT_MAX_ITERATIONS: int = 20
    DEFAULT_PHASE_COMPLETE_THRESHOLD: int = 50
    
    def __init__(
        self,
        agent_id: str,
        engagement_id: str,
        event_bus: EventBus,
        specialty: str = "default",  # Role-specific
        llm_gateway: "LLMGateway | None" = None,
        manifest_loader: "ManifestLoader | None" = None,
        max_iterations: int | None = None,
        phase_complete_threshold: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            agent_name="RefactoredAgent",
            agent_id=agent_id,
            engagement_id=engagement_id,
            event_bus=event_bus,
            role=AgentRole.SPECIFIC_ROLE,  # Set appropriate role
            specialty=specialty,
            llm_gateway=llm_gateway,
            manifest_loader=manifest_loader,
            **kwargs,
        )
        # Minimal agent-specific initialization
        self.max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
        self.phase_complete_threshold = phase_complete_threshold or self.DEFAULT_PHASE_COMPLETE_THRESHOLD
```

### 2. REMOVE These Elements

**MANDATORY DELETIONS:**
- [ ] `tool_sequence` attribute (hardcoded list of tools)
- [ ] All `_generate_*_command()` methods
- [ ] Hardcoded tool selection logic
- [ ] Phase-specific tool routing

### 3. KEEP These Elements

**MANDATORY PRESERVATIONS:**
- [x] `on_finding()` - Stigmergic finding publication
- [x] `on_signal()` - Signal handling (strategy updates, etc.)
- [x] `_flush_buffer()` - Degraded mode resilience
- [x] `stop()` - Graceful shutdown via `_stop_event`
- [x] Scope validation via `_validate_target_scope()`

### 4. Execute Method Pattern

```python
async def execute_<role>(self, target: str) -> tuple[list[Finding], list[AgentAction]]:
    """LLM-driven execution - target as parameter, not constructor."""
    self._validate_target_scope(target)
    
    all_findings: list[Finding] = []
    all_actions: list[AgentAction] = []
    
    context = ToolSelectionContext(
        objective="Role-specific objective",
        target_info={"target": target, "phase": "<role>", "strategy": self.current_strategy},
        available_tools=[],
        phase="<role>",
        constraints=self._get_constraints(),
        previous_results=[],
    )
    
    for iteration in range(self.max_iterations):
        if self._stop_event.is_set():
            break
        if await self._phase_complete(context):
            break
            
        # NFR37: Capture decision context BEFORE action
        decision_context = self.get_decision_context().copy() or [f"initial_spawn:{self.agent_id}"]
        
        try:
            # LLM selects tool from manifest
            selection = await self.select_tool(context)
            result = await kali_execute(selection.command)
            # Process output and publish findings
            ...
        except Exception as e:
            self._log.error("iteration_error", error=str(e))
        
        # Create AgentAction with decision_context (NFR37 - REQUIRED)
        action = AgentAction(
            id=str(uuid.uuid4()),
            agent_id=str(self.agent_id),
            action_type=f"<role>:{tool_name}",
            target=target,
            timestamp=datetime.now(UTC).isoformat(),
            decision_context=decision_context,  # NEVER empty
            result_finding_id=result_finding_id,
        )
        all_actions.append(action)
    
    return all_findings, all_actions
```

---

## Test Requirements (HARD GATES)

### Coverage: 100% Required

```bash
# MUST achieve 100% on the agent module
pytest tests/unit/agents/test_<agent>*.py --cov=src/cyberred/agents/<agent> --cov-report=term-missing --cov-fail-under=100
```

### Required Test Categories

| Category | Count | Description |
|----------|-------|-------------|
| Constructor tests | 3+ | Default params, custom params, specialty |
| Execute method tests | 5+ | Happy path, stop event, phase complete, failure, exception |
| Strategy tests | 3 | stealth, standard, aggressive constraints |
| Signal handling tests | 3+ | Valid strategy, invalid strategy, non-strategy channel |
| Buffer/degraded mode tests | 3+ | Partial flush, all fail, flush before publish |
| Scope validation tests | 2+ | Valid path, file not found fallback |

### Integration Test Pattern

Integration tests should use **mocked `kali_execute`** to avoid testcontainers issues:

```python
@pytest.mark.asyncio
async def test_integration_workflow(self, event_bus, scope):
    """Integration test with mocked tool execution."""
    agent = RefactoredAgent(
        agent_id=str(uuid.uuid4()),
        engagement_id="test-eng",
        event_bus=event_bus,
        max_iterations=3,  # Limit for test speed
    )
    
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.stdout = "realistic output"
    mock_result.stderr = ""
    mock_result.exit_code = 0
    
    with patch("cyberred.agents.<agent>.kali_execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_result
        findings, actions = await agent.execute_<role>(target="target")
        
        # Verify NFR37
        assert all(a.decision_context for a in actions)
```

---

## Definition of Done Checklist

Copy this checklist into each agent refactor story:

```markdown
### Code Requirements
- [ ] Agent is thin subclass (<300 lines)
- [ ] Constructor sets correct `role=AgentRole.X`
- [ ] Constructor accepts `specialty` parameter
- [ ] NO hardcoded `tool_sequence` attribute
- [ ] NO `_generate_*_command()` methods
- [ ] `execute_<role>()` uses inherited `select_tool()`
- [ ] `execute_<role>()` takes `target` as parameter (NOT constructor)
- [ ] All existing stigmergic hooks preserved
- [ ] All AgentActions have non-empty `decision_context` (NFR37)
- [ ] Configurable `max_iterations` and `phase_complete_threshold`

### Quality Gates (HARD REQUIREMENTS)
- [ ] **100% test coverage** on agent module
- [ ] `ruff check` passes with no errors
- [ ] All unit tests pass
- [ ] All integration tests pass

### Prompt Files Required
For each agent specialty, create prompt files:
- [ ] `<role>.md` - Base role prompt
- [ ] `<role>_<specialty1>.md` - Specialty variant
- [ ] `<role>_<specialty2>.md` - Specialty variant
```

---

## File Structure

```
src/cyberred/agents/
├── base.py                 # StigmergicAgent base class
├── <role>.py               # Refactored agent (~200-300 lines max)
├── roles.py                # AgentRole enum
└── prompts/
    ├── <role>.md           # Base prompt
    ├── <role>_specialty1.md
    └── <role>_specialty2.md

tests/unit/agents/
├── test_<role>_agent.py    # Original tests
└── test_<role>_agent_v2.py # v2 coverage tests (NEW)

tests/integration/agents/
└── test_<role>_agent_integration.py
```

---

## Application to Remaining Stories

| Story | Agent | Status | Notes |
|-------|-------|--------|-------|
| 7.3-v2 | ReconAgent | ✅ DONE | Pattern established |
| 7.4-v2 | ExploitAgent | PENDING | Follow this pattern |
| 7.5-v2 | PostExAgent | PENDING | Follow this pattern |

---

## Common Mistakes to Avoid

1. **Target in constructor** ❌ - Target goes in `execute_<role>(target)` method
2. **Missing decision_context** ❌ - NFR37 requires ALL actions have non-empty context
3. **Hardcoded iteration limits** ❌ - Use configurable class constants
4. **Using testcontainers directly** ❌ - Mock `kali_execute` in integration tests
5. **Forgetting prompt files** ❌ - Each specialty needs a prompt file

---

## Validation Command

Run this command after completing any agent refactor:

```bash
# Full validation
source venv/bin/activate && \
  echo "=== Agent Refactor Validation ===" && \
  echo "1. Line count (should be <300):" && \
  wc -l src/cyberred/agents/<role>.py && \
  echo "2. Hardcoded methods (should be 0):" && \
  grep -c "_generate_\|tool_sequence" src/cyberred/agents/<role>.py || echo "0" && \
  echo "3. Coverage (must be 100%):" && \
  pytest tests/unit/agents/test_<role>_agent*.py --cov=src/cyberred/agents/<role> --cov-report=term-missing -q 2>&1 | grep "src/cyberred/agents/<role>.py" && \
  echo "4. Integration tests:" && \
  pytest tests/integration/agents/test_<role>_agent_integration.py -v --tb=short
```

---

*Pattern Version: 1.0*  
*Established: 2026-01-20*  
*Reference Implementation: Story 7.3-v2 (ReconAgent)*
