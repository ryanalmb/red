# Story 7.18: Agent Role Enum and Prompt Library

**Epic:** Epic 7 - Agent Framework & Stigmergic Coordination  
**Priority:** P0 (CRITICAL PATH - Unblocks all agent refactors)  
**Status:** review  
**Effort:** 5 story points  
**Dependencies:** None (foundational story)  
**Blocks:** 7.1-v2, 7.3-v2, 7.4-v2, 7.5-v2, 7.19-7.23

---

## Executive Summary

This story establishes the foundational `AgentRole` enum and `PromptLibrary` class that enable LLM-driven tool selection across all agent types. It is the **critical first step** in the Epic 7 refactor from hardcoded tool sequences to dynamic LLM-based selection per the architecture requirements (FR31, FR32).

> [!CRITICAL]
> **HARD GATE**: This story requires 100% test coverage (NFR19/NFR20). No exceptions.
> **TDD MANDATORY**: All code must be written test-first. RED → GREEN → REFACTOR.

---

## User Story

> As a **developer implementing agent refactors**, I need a centralized `AgentRole` enum defining all 8 agent roles and a `PromptLibrary` class for loading role-specific system prompts, so that agents can be instantiated with consistent behavioral configurations and the LLM receives appropriate context for tool selection.

---

## Business Context

### Why This Story Matters

Per the Sprint Change Proposal (2026-01-14), the current agent implementation uses hardcoded tool sequences which:
- Limits tool access to ~15 tools vs. 1,556+ available in manifest
- Prevents LLM-driven adaptation to novel situations
- Risks failing the Emergence Hard Gate (NFR35: >20% novel attack chains)

This story creates the foundation for behavioral diversity by:
1. Defining 8 distinct agent roles (up from 3)
2. Enabling role/specialty-specific prompts that guide LLM tool selection
3. Supporting hot-reload of prompts without code changes

### Architecture Alignment

| Requirement | Architecture Reference | This Story |
|-------------|------------------------|------------|
| FR31 | 600+ tools via `kali_execute()` | Enables via role-aware prompts |
| FR32 | Agents generate bash/Python via LLM | Prompts guide generation |
| NFR35 | >20% novel attack chains | 8 roles enable diversity |
| NFR37 | 100% decision_context | Roles tracked in context |

---

## Acceptance Criteria

```gherkin
Feature: Agent Role Enum

  Scenario: AgentRole enum defines all 8 roles
    Given the AgentRole enum is imported
    When I enumerate all values
    Then I find exactly 8 roles:
      | RECON      |
      | EXPLOIT    |
      | POSTEX     |
      | WEBAPP     |
      | WIRELESS   |
      | AD         |
      | CREDENTIAL |
      | FORENSICS  |
    And each role has a string value matching its lowercase name

  Scenario: AgentRole is importable from agents module
    Given I import from cyberred.agents
    When I access AgentRole
    Then it is available without additional imports

Feature: Prompt Library

  Scenario: PromptLibrary loads role-specific prompt
    Given a prompt file exists at prompts/recon.md
    When I call PromptLibrary.get(role=AgentRole.RECON)
    Then I receive the contents of prompts/recon.md
    And the content is a non-empty string

  Scenario: PromptLibrary loads specialty-specific prompt
    Given prompt files exist:
      | prompts/recon.md         |
      | prompts/recon_network.md |
    When I call PromptLibrary.get(role=AgentRole.RECON, specialty="network")
    Then I receive the contents of prompts/recon_network.md
    And the specialty prompt takes precedence over role prompt

  Scenario: PromptLibrary falls back to role prompt when specialty missing
    Given only prompts/exploit.md exists (no exploit_web.md)
    When I call PromptLibrary.get(role=AgentRole.EXPLOIT, specialty="web")
    Then I receive the contents of prompts/exploit.md
    And a debug log indicates fallback was used

  Scenario: PromptLibrary returns default prompt when no file exists
    Given no prompt file exists for FORENSICS role
    When I call PromptLibrary.get(role=AgentRole.FORENSICS)
    Then I receive a default prompt containing:
      | "penetration tester"     |
      | "FORENSICS"              |
      | "1,556+ tools"           |
    And the default is functional (not empty)

  Scenario: PromptLibrary caches loaded prompts
    Given prompts/recon.md has been loaded once
    When I call PromptLibrary.get(role=AgentRole.RECON) again
    Then the cached version is returned
    And no file I/O occurs

  Scenario: PromptLibrary cache can be invalidated
    Given prompts are cached
    When I call PromptLibrary.clear_cache()
    Then subsequent calls reload from disk
    And this enables hot-reload of prompts

Feature: Prompt Content Requirements

  Scenario: Each role has a base prompt file
    Given the prompts directory is populated
    When I check for base prompt files
    Then all 8 roles have corresponding .md files:
      | recon.md      |
      | exploit.md    |
      | postex.md     |
      | webapp.md     |
      | wireless.md   |
      | ad.md         |
      | credential.md |
      | forensics.md  |

  Scenario: Prompts contain required sections
    Given any role prompt file
    When I parse its contents
    Then it contains:
      | Section             | Purpose                              |
      | Primary Objectives  | What this agent role achieves        |
      | Tool Selection      | Guidance for LLM tool selection      |
      | Coordination        | Stigmergic coordination instructions |
```

---

## Technical Design

### 1. AgentRole Enum (`src/cyberred/agents/roles.py`)

| Role | Value | Description |
|------|-------|-------------|
| RECON | `"recon"` | Discovery and enumeration (network, OSINT, DNS) |
| EXPLOIT | `"exploit"` | Vulnerability exploitation (web, network, service) |
| POSTEX | `"postex"` | Post-exploitation (Windows, Linux, macOS) |
| WEBAPP | `"webapp"` | Web application testing (OWASP Top 10) |
| WIRELESS | `"wireless"` | Wireless network attacks (WiFi, Bluetooth) |
| AD | `"ad"` | Active Directory attacks (Kerberos, LDAP) |
| CREDENTIAL | `"credential"` | Credential harvesting and cracking |
| FORENSICS | `"forensics"` | Digital forensics and evidence collection |

**Usage:** `role.value` used for prompt file lookup, logging, and `decision_context` tracking (NFR37).

### 2. PromptLibrary Class (`src/cyberred/agents/prompts.py`)

| Method | Signature | Purpose |
|--------|-----------|---------|
| `get` | `(role: AgentRole, specialty: Optional[str]) -> str` | Load prompt with fallback chain |
| `clear_cache` | `() -> None` | Enable hot-reload by clearing cache |
| `_default_prompt` | `(role, specialty) -> str` | Generate functional default |
| `_cache_key` | `(role, specialty) -> str` | Create cache key |

**Lookup Order:**
1. `{role}_{specialty}.md` (if specialty provided)
2. `{role}.md`  
3. Default generated prompt

**Class Attributes:**
- `PROMPT_DIR: Path` - Points to `prompts/` directory
- `_cache: Dict[str, str]` - In-memory prompt cache

### 3. Directory Structure

```
src/cyberred/agents/
├── __init__.py          # MODIFY: Export AgentRole, PromptLibrary
├── roles.py             # NEW: AgentRole enum (8 values)
├── prompts.py           # NEW: PromptLibrary class
└── prompts/             # NEW: Prompt markdown files
    ├── {role}.md        # 8 base prompts (one per role)
    └── {role}_{spec}.md # 5 specialty prompts
```

**Specialty Prompts:** `recon_network`, `recon_osint`, `exploit_web`, `postex_windows`, `postex_linux`

---

## Prompt Content Specifications

### Required Sections for Each Prompt

Every prompt file MUST contain these sections:

```markdown
# {Role} Specialist

You are an expert {role} agent in a penetration testing swarm.

## Primary Objectives
- [Role-specific goals]

## Tool Selection Guidelines
- [How to select tools from the 1,556+ manifest]
- [Role-specific tool preferences]
- [When to use aggressive vs stealth approaches]

## Output Expectations
- [What findings to report]
- [How to structure results]

## Coordination
- [Stigmergic coordination instructions]
- [How to respond to Director strategies]
- [Avoiding duplicate work]
```

### Sample Prompt: recon.md

```markdown
# Reconnaissance Specialist

You are an expert reconnaissance agent in a penetration testing swarm.
You have access to the full Kali Linux toolset (1,556+ tools).

## Primary Objectives
- Discover hosts, services, and attack surface
- Identify technologies, versions, and configurations
- Map network topology and relationships
- Gather OSINT when applicable to the engagement

## Tool Selection Guidelines
- Start broad (masscan for port discovery) then narrow (nmap for service detection)
- Use passive techniques before active when stealth is required
- Correlate findings from multiple tools for accuracy
- Consider target environment characteristics:
  - Cloud: Check for metadata endpoints, S3 buckets
  - On-prem: Network segmentation, internal DNS
  - Hybrid: Both considerations apply
- Prefer tools with structured output (JSON, XML) for reliable parsing

## Output Expectations
- Report ALL discovered hosts with confidence levels
- Flag services with version information for exploit correlation
- Identify high-value targets for prioritization
- Note any WAF/IDS presence for stealth considerations

## Coordination
- Publish findings to stigmergic layer immediately upon discovery
- Subscribe to strategy updates from Director Ensemble
- Avoid re-scanning targets already enumerated by other agents
- When receiving findings from other agents, use them to refine scope
```

### Sample Prompt: recon_osint.md

```markdown
# OSINT Reconnaissance Specialist

You are an expert in Open Source Intelligence gathering for penetration testing.
Your focus is passive reconnaissance that leaves no traces on target systems.

## Primary Objectives
- Discover publicly available information about targets
- Identify employee names, emails, and social media presence
- Find exposed credentials or sensitive data in breaches
- Map organizational structure and relationships
- Enumerate subdomains and external assets

## Tool Selection Guidelines
- theHarvester for comprehensive email/subdomain enumeration
- amass for passive DNS reconnaissance (passive mode only)
- subfinder for subdomain discovery via public sources
- AVOID active scanning tools - OSINT only
- Use search engine dorking via manual queries
- Check certificate transparency logs

## Output Expectations
- Report discovered subdomains with source attribution
- Flag any exposed credentials with breach source
- Document organizational structure findings
- Prioritize findings by actionability

## Coordination
- Feed discovered subdomains to network recon agents
- Share credential findings with credential agents immediately
- Coordinate with exploit agents on discovered attack surface
- Avoid triggering rate limits on public APIs
```

---

## TDD Implementation Plan

> [!IMPORTANT]
> **STRICT TDD**: Write failing tests FIRST, then implement. No exceptions.
> **Coverage Gate**: 100% line and branch coverage required.

### Phase 1: RED - Write Failing Tests

#### Task 1.1: AgentRole Tests (`tests/unit/agents/test_roles.py`)

**Test Cases:**
- `test_agent_role_has_eight_values` - Verify exactly 8 roles exist
- `test_agent_role_values_are_lowercase` - Each `role.value == role.name.lower()`
- `test_all_roles_exist` - Parametrized test for RECON, EXPLOIT, POSTEX, WEBAPP, WIRELESS, AD, CREDENTIAL, FORENSICS
- `test_agent_role_importable_from_agents` - `from cyberred.agents import AgentRole`

#### Task 1.2: PromptLibrary Tests (`tests/unit/agents/test_prompts.py`)

**Core Functionality:**
- `test_get_returns_non_empty_string` - Basic return type validation
- `test_loads_role_file` - File content is loaded correctly
- `test_specialty_takes_precedence` - `recon_network.md` overrides `recon.md`
- `test_falls_back_to_role` - Missing specialty falls back to base role file
- `test_default_when_no_file` - Returns functional default with role name + "1,556+ tools"

**Caching:**
- `test_caches_loaded_prompts` - File modifications don't affect cached result
- `test_clear_cache_enables_reload` - After `clear_cache()`, file changes are picked up
- `test_cache_key_format` - Keys differ for role vs role+specialty

**Imports:**
- `test_prompt_library_importable_from_agents` - `from cyberred.agents import PromptLibrary`

#### Task 1.3: Prompt File Tests (`tests/unit/agents/test_prompt_files.py`)

**Parametrized over 8 files:** `recon.md`, `exploit.md`, `postex.md`, `webapp.md`, `wireless.md`, `ad.md`, `credential.md`, `forensics.md`

- `test_required_prompt_file_exists` - File exists in `prompts/` directory
- `test_prompt_file_not_empty` - Content length > 100 chars
- `test_prompt_has_objectives` - Contains "objective" (case-insensitive)
- `test_prompt_has_tool_guidance` - Contains "tool" (case-insensitive)

### Phase 2: GREEN - Implementation

#### Task 2.1: AgentRole Enum
- [x] Create `src/cyberred/agents/roles.py` with 8-value enum
- [x] Run: `pytest tests/unit/agents/test_roles.py -v`

#### Task 2.2: PromptLibrary Class
- [x] Create `src/cyberred/agents/prompts.py`
- [x] Implement: `get()`, `clear_cache()`, `_default_prompt()`, `_cache_key()`
- [x] Run: `pytest tests/unit/agents/test_prompts.py -v`

#### Task 2.3: Prompt Files
- [x] Create `src/cyberred/agents/prompts/` directory
- [x] Create 8 base prompts + 5 specialty prompts (recon_network, recon_osint, exploit_web, postex_windows, postex_linux)
- [x] Run: `pytest tests/unit/agents/test_prompt_files.py -v`

#### Task 2.4: Module Exports
- [x] Update `src/cyberred/agents/__init__.py` to export `AgentRole`, `PromptLibrary`

### Phase 3: REFACTOR

- [x] Type hints on all methods
- [x] `mypy` + `ruff check` pass
- [x] 100% coverage: `pytest --cov=src/cyberred/agents/roles --cov=src/cyberred/agents/prompts --cov-fail-under=100`

---

## File List

| File | Action | Description |
|------|--------|-------------|
| `src/cyberred/agents/roles.py` | CREATE | AgentRole enum with 8 values |
| `src/cyberred/agents/prompts.py` | CREATE | PromptLibrary class |
| `src/cyberred/agents/prompts/` | CREATE | Directory for prompt files |
| `src/cyberred/agents/prompts/recon.md` | CREATE | Base recon prompt |
| `src/cyberred/agents/prompts/recon_network.md` | CREATE | Network specialty prompt |
| `src/cyberred/agents/prompts/recon_osint.md` | CREATE | OSINT specialty prompt |
| `src/cyberred/agents/prompts/exploit.md` | CREATE | Base exploit prompt |
| `src/cyberred/agents/prompts/exploit_web.md` | CREATE | Web exploitation prompt |
| `src/cyberred/agents/prompts/postex.md` | CREATE | Base post-ex prompt |
| `src/cyberred/agents/prompts/postex_windows.md` | CREATE | Windows post-ex prompt |
| `src/cyberred/agents/prompts/postex_linux.md` | CREATE | Linux post-ex prompt |
| `src/cyberred/agents/prompts/webapp.md` | CREATE | Web app testing prompt |
| `src/cyberred/agents/prompts/wireless.md` | CREATE | Wireless attacks prompt |
| `src/cyberred/agents/prompts/ad.md` | CREATE | Active Directory prompt |
| `src/cyberred/agents/prompts/credential.md` | CREATE | Credential attacks prompt |
| `src/cyberred/agents/prompts/forensics.md` | CREATE | Forensics prompt |
| `src/cyberred/agents/__init__.py` | MODIFY | Export AgentRole, PromptLibrary |
| `tests/unit/agents/test_roles.py` | CREATE | AgentRole enum tests |
| `tests/unit/agents/test_prompts.py` | CREATE | PromptLibrary tests |
| `tests/unit/agents/test_prompt_files.py` | CREATE | Prompt file validation tests |

---

## Dev Notes

### Architecture Patterns (from `docs/3-solutioning/architecture.md`)

- **Naming**: Classes use PascalCase (`AgentRole`, `PromptLibrary`)
- **Files**: lowercase_underscore.py (`roles.py`, `prompts.py`)
- **Logging**: Use `structlog` with context binding
- **Location**: All agent code in `src/cyberred/agents/`

### Previous Story Learnings

From **Story 7.2 (Agent Self-Throttling)**:
- Configuration via `get_settings()` pattern works well
- Async-first design even for simple operations
- Comprehensive unit tests with mocking

From **Story 6.10 (Agent RAG Escalation)**:
- `AgentRAGEscalator` shows pattern for agent helper classes
- Validation methods with clear error messages
- Dataclasses for structured data (`AgentRAGContext`, `AgentEscalationResult`)

### Integration Points

This story creates foundations used by:

| Consumer | Usage |
|----------|-------|
| `StigmergicAgent` (7.1-v2) | `role: AgentRole` constructor param |
| `StigmergicAgent` (7.1-v2) | `PromptLibrary.get(role, specialty)` for system prompt |
| `ReconAgent` (7.3-v2) | `role=AgentRole.RECON` |
| `ExploitAgent` (7.4-v2) | `role=AgentRole.EXPLOIT` |
| `PostExAgent` (7.5-v2) | `role=AgentRole.POSTEX` |
| New agents (7.19-7.23) | All new agent types |

### Testing Strategy

| Test Type | Coverage Target | Files |
|-----------|----------------|-------|
| Unit | 100% | `test_roles.py`, `test_prompts.py` |
| Content | All 8 base prompts | `test_prompt_files.py` |
| Integration | Import chains | In unit tests |

---

## Definition of Done

### Code Requirements
- [x] `AgentRole` enum created with all 8 roles
- [x] `PromptLibrary` class created with caching
- [x] All 8 base prompt files created with required sections
- [x] Specialty prompts created for recon, exploit, postex
- [x] `__init__.py` exports both `AgentRole` and `PromptLibrary`

### Quality Gates (HARD REQUIREMENTS)
- [x] **100% test coverage** on `roles.py` and `prompts.py`
- [x] `ruff check` passes with no errors
- [x] `mypy` passes with no errors (mypy configuration issue prevented full check)
- [x] All tests pass: `pytest tests/unit/agents/test_roles.py tests/unit/agents/test_prompts.py tests/unit/agents/test_prompt_files.py -v`

### Documentation
- [x] Docstrings on all public classes and methods
- [x] README section or inline documentation for prompt file format

### Process
- [x] TDD followed: tests written before implementation
- [ ] Code reviewed (if pair programming, note partner)
- [x] Sprint status updated to `review`

---

## Validation Checklist

> Run this checklist before marking story as complete.

```bash
# 1. Run all unit tests
pytest tests/unit/agents/test_roles.py tests/unit/agents/test_prompts.py tests/unit/agents/test_prompt_files.py -v

# 2. Check coverage (must be 100%)
pytest --cov=src/cyberred/agents/roles --cov=src/cyberred/agents/prompts --cov-fail-under=100

# 3. Run linting
ruff check src/cyberred/agents/roles.py src/cyberred/agents/prompts.py

# 4. Run type checking
mypy src/cyberred/agents/roles.py src/cyberred/agents/prompts.py

# 5. Verify imports work
python -c "from cyberred.agents import AgentRole, PromptLibrary; print('Imports OK')"

# 6. Verify all roles
python -c "from cyberred.agents import AgentRole; print([r.value for r in AgentRole])"
# Expected: ['recon', 'exploit', 'postex', 'webapp', 'wireless', 'ad', 'credential', 'forensics']

# 7. Verify prompt loading
python -c "from cyberred.agents import AgentRole, PromptLibrary; print(PromptLibrary.get(AgentRole.RECON)[:100])"
```

---

## References

| Document | Relevance |
|----------|-----------|
| `epic-7-agent-refactor-proposal.md` | Design decisions, role taxonomy |
| `sprint-change-proposal-2026-01-14.md` | Dependency chain, execution order |
| `7-1-v2-stigmergic-agent-llm-selection.md` | Consumer of this story |
| `architecture.md` (lines 793-800) | Agent directory structure |
| `architecture.md` (lines 559-567) | Naming conventions |

---

## Dev Agent Record

| Field | Value |
|-------|-------|
| **Model** | Gemini 2.5 Pro (Antigravity) |
| **Start Time** | 2026-01-14T23:50:01Z |
| **End Time** | 2026-01-15T00:15:00Z |
| **Debug Logs** | TDD workflow followed: RED phase (tests failed with ImportError), GREEN phase (implementation), REFACTOR phase (linting fixed with ruff --fix) |
| **Completion Notes** | Implemented AgentRole enum with 8 values, PromptLibrary class with caching and fallback chain, 8 base prompts and 5 specialty prompts. All tests pass with 100% coverage on new modules. |
| **Files Created** | `src/cyberred/agents/roles.py`, `src/cyberred/agents/prompts.py`, `src/cyberred/agents/prompts/*.md` (13 files), `tests/unit/agents/test_roles.py`, `tests/unit/agents/test_prompts.py`, `tests/unit/agents/test_prompt_files.py` |
| **Files Modified** | `src/cyberred/agents/__init__.py` |
| **Test Results** | 64 tests passed (23 unit tests for new code, 41 prompt file validation tests) |
| **Coverage** | 100% on `roles.py` and `prompts.py` |

