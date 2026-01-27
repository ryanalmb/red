# Story 7.1.v2: StigmergicAgent Base Class with LLM-Driven Tool Selection

**Epic:** Epic 7 - Agent Framework & Stigmergic Coordination  
**Priority:** P0 (CRITICAL PATH - Foundation for all agents)  
**Status:** ready-for-dev  
**Effort:** 8 story points  
**Dependencies:** Story 7.18 (AgentRole + PromptLibrary) ✅ COMPLETE  
**Blocks:** 7.3-v2, 7.4-v2, 7.5-v2, 7.19-7.23 (all agent implementations)

---

## Executive Summary

This story refactors the existing `StigmergicAgent` base class to add **LLM-driven tool selection** capabilities. The current implementation (Story 7.1) provides stigmergic pub/sub hooks but lacks the critical ability for agents to intelligently select from the full 1,556+ tool manifest. This refactor enables dynamic, context-aware tool selection via LLM reasoning rather than hardcoded tool sequences.

> [!CRITICAL]
> **HARD GATE**: This story requires **100% test coverage** (NFR19/NFR20). No exceptions.
> **TDD MANDATORY**: All code must be written test-first. RED → GREEN → REFACTOR.
> **EMERGENCE GATE**: This foundation directly impacts NFR35-37 (>20% novel attack chains).

---

## User Story

> As a **developer implementing specialized agents**, I need the `StigmergicAgent` base class to provide LLM-driven tool selection capabilities with cached `--help` output generation, so that all agents can intelligently select from 1,556+ Kali tools based on context rather than hardcoded sequences, enabling the emergence and behavioral diversity required by NFR35-37.

---

## Business Context

### Why This Story Matters

The current agent implementation uses hardcoded tool sequences which:
- Limits tool access to ~15 tools vs. 1,556+ available in manifest
- Prevents LLM-driven adaptation to novel situations  
- Risks failing the **Emergence Hard Gate** (NFR35: >20% novel attack chains)
- Violates FR31 (600+ tools via `kali_execute()`) and FR32 (agents generate code via LLM)

This refactor enables:
1. **Full manifest access** - Any tool available based on context
2. **LLM-driven selection** - Intelligent tool choice via reasoning
3. **Role-aware behavior** - Prompts guide selection per agent type
4. **Emergence enablement** - Diverse tool usage enables novel attack chains

### Architecture Alignment

| Requirement | Architecture Reference | This Story |
|-------------|------------------------|------------|
| FR4 | Stigmergic P2P coordination | Preserves existing pub/sub hooks |
| FR31 | 600+ tools via `kali_execute()` | `select_tool()` accesses full manifest |
| FR32 | Agents generate bash/Python via LLM | `generate_command()` uses LLM + `--help` |
| FR62 | decision_context logging | All tool selections logged |
| NFR35 | >20% novel attack chains | LLM selection enables diversity |
| NFR37 | 100% decision_context | Tool selection IDs tracked |

---

## Acceptance Criteria

```gherkin
Feature: LLM-Driven Tool Selection

  Scenario: Agent selects tool from manifest using LLM
    Given a StigmergicAgent with role=RECON and context about a target
    When agent calls select_tool(context)
    Then LLM receives: role prompt + context + manifest categories
    And LLM returns a ToolSelection with tool_name and reasoning
    And selection is logged in decision_context

  Scenario: Agent generates command using tool's --help
    Given a selected tool "nmap"
    When agent calls generate_command(tool="nmap", target="192.168.1.0/24")
    Then agent retrieves nmap --help output (cached if available)
    And LLM generates syntactically correct command using help output
    And command includes proper flags for the context

  Scenario: Tool help output is cached per session
    Given agent has not used "nuclei" before
    When agent calls generate_command for nuclei twice
    Then kali_execute("nuclei --help") is called only once
    And second call uses cached output
    And cache key is tool name

  Scenario: Agent loads role-specific system prompt
    Given AgentRole.RECON and specialty="network"
    When StigmergicAgent is instantiated
    Then PromptLibrary.get(RECON, "network") provides system prompt
    And prompt guides LLM tool selection behavior

  Scenario: Agent accesses full tool manifest
    Given ManifestLoader is available
    When agent needs to discover available tools
    Then agent can query manifest by category (recon, exploit, etc.)
    And manifest returns tool names for LLM consideration
    And manifest has 1,556+ tools available

  Scenario: All existing stigmergic hooks preserved
    Given the refactored StigmergicAgent
    When lifecycle methods are called
    Then on_finding() publishes to Redis (unchanged)
    And on_signal() reacts to swarm state (unchanged)
    And on_complete() updates status (unchanged)
    And spawn() sets up subscriptions (unchanged)

Feature: TDD and Coverage Requirements

  Scenario: 100% code coverage enforced
    Given all new code in base.py
    When pytest --cov runs
    Then coverage is 100% for new methods
    And coverage gate fails if below 100%

  Scenario: Strict TDD workflow followed
    Given each new method
    When implementing
    Then failing test written first (RED)
    And minimal code to pass (GREEN)
    And refactored for quality (REFACTOR)
```

---

## Technical Design

### 1. New Methods to Add to StigmergicAgent

| Method | Signature | Purpose |
|--------|-----------|---------|
| `select_tool` | `async (context: ToolSelectionContext) -> ToolSelection` | LLM selects tool from manifest |
| `generate_command` | `async (tool: str, target: str, options: dict) -> str` | LLM generates command using --help |
| `_get_tool_help` | `async (tool: str) -> str` | Get cached --help output |
| `_build_tool_selection_prompt` | `(context: ToolSelectionContext) -> str` | Build LLM prompt for selection |

### 2. New Data Models (`src/cyberred/core/models.py`)

```python
@dataclass
class ToolSelectionContext:
    """Context for LLM tool selection."""
    target: str                      # Target IP/hostname/URL
    target_info: Dict[str, Any]      # Known info (ports, services, OS)
    objective: str                   # What agent is trying to achieve
    previous_tools: List[str]        # Tools already used on this target
    constraints: List[str]           # Stealth requirements, timeouts, etc.
    stigmergic_signals: List[str]    # Recent relevant findings from swarm

@dataclass  
class ToolSelection:
    """Result of LLM tool selection."""
    tool_name: str                   # Selected tool (e.g., "nmap")
    reasoning: str                   # LLM's reasoning for selection
    category: str                    # Tool category from manifest
    confidence: float                # 0.0-1.0 confidence score
    alternatives: List[str]          # Other considered tools
    selection_id: str                # UUID for decision_context tracking
```

### 3. Constructor Changes

```python
class StigmergicAgent(Agent):
    def __init__(
        self,
        agent_name: str,
        agent_id: str,
        engagement_id: str,
        event_bus: EventBus,
        role: AgentRole,                    # NEW: Required role
        specialty: Optional[str] = None,    # NEW: Optional specialty
        llm_gateway: Optional[LLMGateway] = None,  # NEW: For tool selection
        manifest_loader: Optional[ManifestLoader] = None,  # NEW: Tool manifest
        *args,
        **kwargs
    ):
        self.role = role
        self.specialty = specialty
        self.system_prompt = PromptLibrary.get(role, specialty)
        self._llm_gateway = llm_gateway or get_gateway()
        self._manifest = manifest_loader or ManifestLoader()
        self._tool_help_cache: Dict[str, str] = {}
        # ... existing init code ...
```

### 4. select_tool() Implementation Pattern

```python
async def select_tool(self, context: ToolSelectionContext) -> ToolSelection:
    """Select tool from manifest using LLM reasoning.
    
    Args:
        context: Context including target info, objective, constraints
        
    Returns:
        ToolSelection with chosen tool and reasoning
        
    Raises:
        ToolSelectionError: If LLM fails to select valid tool
    """
    # 1. Get relevant tool categories based on role
    categories = self._get_role_categories()
    available_tools = self._manifest.get_tools_by_categories(categories)
    
    # 2. Build selection prompt
    prompt = self._build_tool_selection_prompt(context, available_tools)
    
    # 3. Query LLM (STANDARD tier for selection)
    response = await self._llm_gateway.complete(
        prompt=prompt,
        system_prompt=self.system_prompt,
        tier="STANDARD"
    )
    
    # 4. Parse and validate response
    selection = self._parse_tool_selection(response)
    
    # 5. Track in decision_context (NFR37)
    self._decision_context.append(selection.selection_id)
    
    self._log.info("tool_selected", 
        tool=selection.tool_name,
        reasoning=selection.reasoning[:100],
        selection_id=selection.selection_id
    )
    
    return selection
```

### 5. generate_command() Implementation Pattern

```python
async def generate_command(
    self, 
    tool: str, 
    target: str, 
    options: Optional[Dict[str, Any]] = None
) -> str:
    """Generate tool command using LLM and --help output.
    
    Args:
        tool: Tool name (e.g., "nmap")
        target: Target specification
        options: Additional options (stealth, output format, etc.)
        
    Returns:
        Complete command string ready for kali_execute()
    """
    # 1. Get cached --help output
    help_output = await self._get_tool_help(tool)
    
    # 2. Build command generation prompt
    prompt = f"""Generate a {tool} command for target: {target}

Tool help output:
```
{help_output}
```

Requirements:
- Target: {target}
- Options: {options or 'default'}
- Output format: Prefer structured output (JSON/XML) if available

Return ONLY the command, no explanation."""

    # 3. Query LLM (FAST tier for command generation)
    response = await self._llm_gateway.complete(
        prompt=prompt,
        system_prompt=self.system_prompt,
        tier="FAST"
    )
    
    # 4. Validate command (basic sanity checks)
    command = self._validate_command(response.strip(), tool)
    
    return command
```

### 6. _get_tool_help() with Caching

```python
async def _get_tool_help(self, tool: str) -> str:
    """Get tool --help output, cached per session.
    
    Args:
        tool: Tool name
        
    Returns:
        Help output string (truncated to 80 lines)
    """
    if tool in self._tool_help_cache:
        return self._tool_help_cache[tool]
    
    # Execute --help and capture output
    from cyberred.tools.kali_executor import kali_execute
    
    result = await kali_execute(
        f"{tool} --help 2>&1 | head -80",
        timeout=10
    )
    
    help_text = result.stdout if result.success else f"No help available for {tool}"
    self._tool_help_cache[tool] = help_text
    
    self._log.debug("tool_help_cached", tool=tool, length=len(help_text))
    
    return help_text
```

---

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/cyberred/agents/base.py` | MODIFY | Add select_tool, generate_command, _get_tool_help, role/specialty params |
| `src/cyberred/core/models.py` | ✅ ALREADY DONE | `ToolSelectionContext`, `ToolSelection` already exist (lines 247-322) |
| `src/cyberred/core/exceptions.py` | ✅ ALREADY DONE | `ToolSelectionError` already exists (line 928) |
| `src/cyberred/core/__init__.py` | **MODIFY** | Export `ToolSelectionContext`, `ToolSelection`, `ToolSelectionError` |
| `src/cyberred/agents/__init__.py` | **MODIFY** | Updated exports for new components |
| `tests/unit/agents/test_stigmergic_base.py` | MODIFY | Add tests for new methods |
| `tests/unit/agents/test_tool_selection.py` | CREATE | Dedicated tool selection tests |
| `tests/unit/core/test_models_tool_selection.py` | CREATE | Tests for ToolSelectionContext, ToolSelection |
| `tests/integration/agents/test_tool_selection_integration.py` | CREATE | Integration tests with real LLM |

### `src/cyberred/core/__init__.py` Required Updates

**Add to imports (after line 23):**
```python
from cyberred.core.models import (
    Finding,
    AgentAction,
    ToolResult,
    ToolSelectionContext,  # NEW
    ToolSelection,         # NEW
)
```

**Add to exceptions import (after line 18):**
```python
from cyberred.core.exceptions import (
    # ... existing ...
    ToolSelectionError,    # NEW
)
```

**Add to `__all__` list:**
```python
# Data Models section (after line 74)
"ToolSelectionContext",
"ToolSelection",

# Exceptions section (after line 70)
"ToolSelectionError",
```

---

## TDD Implementation Plan

> [!IMPORTANT]
> **STRICT TDD**: Write failing tests FIRST, then implement. No exceptions.
> **Coverage Gate**: 100% line and branch coverage required on all new code.

### Phase 1: RED - Write Failing Tests

#### Task 1.1: ToolSelectionContext and ToolSelection Model Tests
**File:** `tests/unit/core/test_models_tool_selection.py`

```python
# Test cases to write FIRST:
def test_tool_selection_context_required_fields():
    """ToolSelectionContext requires target and objective."""
    
def test_tool_selection_context_serializable():
    """ToolSelectionContext is JSON serializable."""
    
def test_tool_selection_has_selection_id():
    """ToolSelection auto-generates UUID selection_id."""
    
def test_tool_selection_confidence_bounds():
    """ToolSelection.confidence must be 0.0-1.0."""
```

#### Task 1.2: StigmergicAgent Constructor Tests
**File:** `tests/unit/agents/test_stigmergic_base.py` (extend)

```python
def test_init_requires_role():
    """StigmergicAgent requires AgentRole parameter."""

def test_init_loads_prompt_from_library():
    """Constructor calls PromptLibrary.get(role, specialty)."""

def test_init_accepts_optional_specialty():
    """Specialty parameter is optional, defaults to None."""

def test_init_creates_empty_tool_help_cache():
    """Constructor initializes _tool_help_cache as empty dict."""

def test_init_accepts_custom_manifest_loader():
    """ManifestLoader can be injected for testing."""
```

#### Task 1.3: select_tool() Tests
**File:** `tests/unit/agents/test_tool_selection.py` (create)

```python
@pytest.mark.asyncio
async def test_select_tool_returns_tool_selection():
    """select_tool returns ToolSelection dataclass."""

@pytest.mark.asyncio
async def test_select_tool_queries_llm_with_context():
    """LLM receives context in prompt."""

@pytest.mark.asyncio
async def test_select_tool_uses_role_system_prompt():
    """LLM call uses agent's role-specific system prompt."""

@pytest.mark.asyncio
async def test_select_tool_tracks_decision_context():
    """selection_id added to _decision_context (NFR37)."""

@pytest.mark.asyncio
async def test_select_tool_logs_selection():
    """Tool selection is logged with structlog."""

@pytest.mark.asyncio
async def test_select_tool_raises_on_invalid_tool():
    """ToolSelectionError raised if LLM returns invalid tool."""

@pytest.mark.asyncio
async def test_select_tool_filters_by_role_categories():
    """Only role-appropriate tool categories are offered to LLM."""
```

#### Task 1.4: generate_command() Tests
**File:** `tests/unit/agents/test_tool_selection.py` (continue)

```python
@pytest.mark.asyncio
async def test_generate_command_returns_string():
    """generate_command returns command string."""

@pytest.mark.asyncio
async def test_generate_command_includes_target():
    """Generated command includes target specification."""

@pytest.mark.asyncio
async def test_generate_command_uses_help_output():
    """LLM prompt includes tool's --help output."""

@pytest.mark.asyncio
async def test_generate_command_validates_output():
    """Basic validation ensures command starts with tool name."""
```

#### Task 1.5: _get_tool_help() Caching Tests
**File:** `tests/unit/agents/test_tool_selection.py` (continue)

```python
@pytest.mark.asyncio
async def test_get_tool_help_caches_result():
    """Second call uses cache, not kali_execute."""

@pytest.mark.asyncio
async def test_get_tool_help_cache_key_is_tool_name():
    """Cache key is exactly the tool name."""

@pytest.mark.asyncio
async def test_get_tool_help_truncates_to_80_lines():
    """Help output is truncated to 80 lines max."""

@pytest.mark.asyncio
async def test_get_tool_help_handles_missing_tool():
    """Graceful fallback if tool has no --help."""
```

### Phase 2: GREEN - Implement Minimal Code

#### Task 2.1: Add Data Models
- [ ] Add `ToolSelectionContext` to `src/cyberred/core/models.py`
- [ ] Add `ToolSelection` to `src/cyberred/core/models.py`
- [ ] Add `ToolSelectionError` to `src/cyberred/core/exceptions.py`
- [ ] Run: `pytest tests/unit/core/test_models_tool_selection.py -v`

#### Task 2.2: Update StigmergicAgent Constructor
- [ ] Add `role: AgentRole` required parameter
- [ ] Add `specialty: Optional[str]` parameter
- [ ] Add `PromptLibrary.get()` call for system_prompt
- [ ] Add `_tool_help_cache: Dict[str, str]` initialization
- [ ] Add `_manifest: ManifestLoader` initialization
- [ ] Run: `pytest tests/unit/agents/test_stigmergic_base.py -v`

#### Task 2.3: Implement select_tool()
- [ ] Implement `_get_role_categories()` helper
- [ ] Implement `_build_tool_selection_prompt()` helper
- [ ] Implement `_parse_tool_selection()` helper
- [ ] Implement `select_tool()` main method
- [ ] Run: `pytest tests/unit/agents/test_tool_selection.py::test_select_tool* -v`

#### Task 2.4: Implement generate_command()
- [ ] Implement `generate_command()` method
- [ ] Implement `_validate_command()` helper
- [ ] Run: `pytest tests/unit/agents/test_tool_selection.py::test_generate_command* -v`

#### Task 2.5: Implement _get_tool_help()
- [ ] Implement `_get_tool_help()` with caching
- [ ] Run: `pytest tests/unit/agents/test_tool_selection.py::test_get_tool_help* -v`

### Phase 3: REFACTOR - Optimize and Harden

#### Task 3.1: Code Quality
- [ ] Add comprehensive docstrings to all new methods
- [ ] Add type hints to all parameters and returns
- [ ] Run: `ruff check src/cyberred/agents/base.py`
- [ ] Run: `mypy src/cyberred/agents/base.py`

#### Task 3.2: Coverage Verification
- [ ] Run: `pytest --cov=src/cyberred/agents/base --cov-fail-under=100`
- [ ] Identify any uncovered branches
- [ ] Add tests for edge cases

#### Task 3.3: Integration Tests
- [ ] Create `tests/integration/agents/test_tool_selection_integration.py`
- [ ] Test with mocked LLM responses
- [ ] Test with real LLM (optional CI gate)

---

## Dev Notes

### Architecture Patterns (from `docs/3-solutioning/architecture.md`)

**Naming Conventions:**
- Classes: PascalCase (`ToolSelection`, `ToolSelectionContext`)
- Methods: snake_case (`select_tool`, `generate_command`)
- Files: lowercase_underscore.py (`base.py`, `models.py`)
- Constants: UPPER_SNAKE_CASE (`TOOL_HELP_MAX_LINES = 80`)

**Logging:**
- Use `structlog` with context binding
- Bind: `agent_id`, `engagement_id`, `tool`, `selection_id`
- Log levels: `info` for selections, `debug` for cache hits, `error` for failures

**Error Handling:**
- `ToolSelectionError` for invalid LLM responses
- Fail-open for non-critical errors (cache misses, help unavailable)
- Fail-closed for critical errors (no valid tool selected)

### Existing Code to Reuse

| Component | Location | Usage |
|-----------|----------|-------|
| `AgentRole` | `src/cyberred/agents/roles.py` | Role enum (8 values) |
| `PromptLibrary` | `src/cyberred/agents/prompts.py` | Load system prompts |
| `ManifestLoader` | `src/cyberred/tools/manifest.py` | Access 1,556+ tools |
| `LLMGateway` | `src/cyberred/llm/gateway.py` | LLM completions |
| `kali_execute` | `src/cyberred/tools/kali_executor.py` | Execute --help |
| `EventBus` | `src/cyberred/core/events.py` | Pub/sub (unchanged) |

### Previous Story Learnings

**From Story 7.18 (AgentRole + PromptLibrary):**
- PromptLibrary caches prompts - leverage this
- Specialty prompts override role prompts
- Default prompt generated if file missing

**From Story 7.1 (Original StigmergicAgent):**
- Lifecycle hooks work correctly - don't break them
- `_decision_context` tracking pattern established
- Throttling integration (Story 7.2) must be preserved

**From Story 7.2 (Agent Self-Throttling):**
- `_check_throttle()` pattern for LLM queue management
- Fail-open strategy for non-critical failures
- Background monitor task pattern

### Anti-Patterns to Avoid

1. **DO NOT** hardcode tool lists - always use manifest
2. **DO NOT** skip decision_context tracking - NFR37 requires 100%
3. **DO NOT** make synchronous LLM calls - always async
4. **DO NOT** break existing lifecycle hooks - extend, don't replace
5. **DO NOT** cache --help globally - per-session only (tools may update)
6. **DO NOT** trust LLM output blindly - validate tool names against manifest

### Role Category Mapping

```python
ROLE_CATEGORIES = {
    AgentRole.RECON: ["recon", "discovery", "enumeration", "osint"],
    AgentRole.EXPLOIT: ["exploit", "vulnerability", "injection", "web"],
    AgentRole.POSTEX: ["postex", "privesc", "lateral", "persistence"],
    AgentRole.WEBAPP: ["web", "injection", "auth", "api"],
    AgentRole.WIRELESS: ["wireless", "wifi", "bluetooth"],
    AgentRole.AD: ["activedirectory", "kerberos", "ldap", "smb"],
    AgentRole.CREDENTIAL: ["credential", "password", "hash", "brute"],
    AgentRole.FORENSICS: ["forensics", "memory", "disk", "artifact"],
}
```

### Integration Points

| Consumer | How It Uses This Story |
|----------|------------------------|
| `ReconAgent` (7.3-v2) | Inherits select_tool(), sets role=RECON |
| `ExploitAgent` (7.4-v2) | Inherits generate_command(), sets role=EXPLOIT |
| `PostExAgent` (7.5-v2) | Uses role-specific prompt, sets role=POSTEX |
| `WebAppAgent` (7.19) | New agent, role=WEBAPP |
| All 8 agent types | Thin subclasses setting role parameter |

---

## Definition of Done

### Code Requirements
- [ ] `select_tool()` method implemented with LLM integration
- [ ] `generate_command()` method implemented with --help caching
- [ ] `_get_tool_help()` method implemented with session caching
- [ ] Constructor accepts `role: AgentRole` required parameter
- [ ] Constructor accepts `specialty: Optional[str]` parameter
- [ ] System prompt loaded via `PromptLibrary.get(role, specialty)`
- [ ] All existing lifecycle hooks preserved and working
- [ ] `ToolSelectionContext` and `ToolSelection` dataclasses added

### Quality Gates (HARD REQUIREMENTS)
- [ ] **100% test coverage** on all new/modified code in `base.py`
- [ ] **100% test coverage** on new dataclasses in `models.py`
- [ ] `ruff check` passes with no errors
- [ ] `mypy` passes with no errors
- [ ] All unit tests pass: `pytest tests/unit/agents/test_*.py -v`
- [ ] All integration tests pass: `pytest tests/integration/agents/test_*.py -v`

### Documentation
- [ ] Docstrings on all new public methods
- [ ] Type hints on all parameters and returns
- [ ] This story file updated with completion notes

### Process
- [ ] TDD followed: tests written before implementation
- [ ] Code reviewed
- [ ] Sprint status updated to `done`

---

## Validation Checklist

> Run this checklist before marking story as complete.

```bash
# 1. Run all unit tests for agents
pytest tests/unit/agents/ -v

# 2. Run tool selection specific tests
pytest tests/unit/agents/test_tool_selection.py -v

# 3. Check coverage (must be 100% on new code)
pytest --cov=src/cyberred/agents/base --cov=src/cyberred/core/models --cov-report=term-missing

# 4. Run linting
ruff check src/cyberred/agents/base.py src/cyberred/core/models.py

# 5. Run type checking
mypy src/cyberred/agents/base.py src/cyberred/core/models.py

# 6. Verify role parameter required
python -c "
from cyberred.agents.base import StigmergicAgent
try:
    StigmergicAgent(agent_name='test', agent_id='1', engagement_id='e1', event_bus=None)
    print('FAIL: Should require role')
except TypeError as e:
    print('PASS: role is required')
"

# 7. Verify select_tool exists
python -c "
from cyberred.agents.base import StigmergicAgent
assert hasattr(StigmergicAgent, 'select_tool')
print('PASS: select_tool method exists')
"

# 8. Verify generate_command exists
python -c "
from cyberred.agents.base import StigmergicAgent
assert hasattr(StigmergicAgent, 'generate_command')
print('PASS: generate_command method exists')
"

# 9. Integration test with mock LLM
pytest tests/integration/agents/test_tool_selection_integration.py -v

# 10. Verify existing tests still pass
pytest tests/unit/agents/test_stigmergic_base.py -v
pytest tests/integration/agents/test_stigmergic_integration.py -v
```

---

## References

| Document | Section | Relevance |
|----------|---------|-----------|
| `architecture.md` | Lines 793-800 | Agent directory structure |
| `architecture.md` | Lines 559-567 | Naming conventions |
| `architecture.md` | Lines 126-137 | Agent LLM Model Pool tiers |
| `epics-stories.md` | Story 7.1 | Original acceptance criteria |
| `sprint-change-proposal-2026-01-14.md` | Full doc | Rationale for v2 refactor |
| `7-18-agent-role-and-prompt-library.md` | Full doc | Dependency (AgentRole, PromptLibrary) |
| `7-1-stigmergic-agent-base-class.md` | Full doc | Original implementation reference |
| `src/cyberred/agents/base.py` | Full file | Current implementation to extend |
| `src/cyberred/agents/roles.py` | Full file | AgentRole enum |
| `src/cyberred/agents/prompts.py` | Full file | PromptLibrary class |

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

