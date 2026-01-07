# Story 0.7: Safety & Emergence Test Framework

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **dedicated test structures for safety and emergence validation**,
So that **hard-gate tests (NFR35-37) have proper framework from day one**.

## Acceptance Criteria

1. **Given** Story 0.2 is complete
2. **When** I examine `tests/safety/` and `tests/emergence/`
3. **Then** `tests/safety/` contains placeholder files for scope, kill switch, auth tests
4. **And** `tests/emergence/` contains placeholder files for emergence score, causal chains, decision_context
5. **And** safety tests are marked with `@pytest.mark.safety` (always run)
6. **And** emergence tests are marked with `@pytest.mark.emergence`
7. **And** README.md in each directory explains the test category purpose

## Tasks / Subtasks

- [x] Create Safety Test Placeholders <!-- id: 0 -->
  - [x] Create `tests/safety/test_scope_blocks.py` - Scope violation scenarios (AC: #3)
  - [x] Create `tests/safety/test_killswitch.py` - Kill switch timing (<1s) (AC: #3)
  - [x] Create `tests/safety/test_auth_required.py` - Lateral movement authorization (AC: #3)
- [x] Create Emergence Test Placeholders <!-- id: 1 -->
  - [x] Create `tests/emergence/test_emergence_score.py` - >20% novel chains hard gate (AC: #4)
  - [x] Create `tests/emergence/test_causal_chains.py` - 3+ hop chain validation (AC: #4)
  - [x] Create `tests/emergence/test_decision_context.py` - decision_context population (AC: #4)
- [x] Verify Markers in conftest.py <!-- id: 2 -->
  - [x] Confirm `@pytest.mark.safety` marker is registered (AC: #5)
  - [x] Confirm `@pytest.mark.emergence` marker is registered (AC: #6)
- [x] Create README Documentation <!-- id: 3 -->
  - [x] Create `tests/safety/README.md` explaining safety test purpose (AC: #7)
  - [x] Create `tests/emergence/README.md` explaining emergence test purpose (AC: #7)
- [x] Verify Test Discovery <!-- id: 4 -->
  - [x] Run `pytest --collect-only -m safety` to verify safety tests are discoverable
  - [x] Run `pytest --collect-only -m emergence` to verify emergence tests are discoverable

## Dev Notes

### Architecture Context

This story establishes the **test framework** for two critical categories:

1. **Safety Tests (`tests/safety/`)**: Hard-gate tests that MUST NEVER FAIL
   - Scope violation prevention (ERR6, FR20-FR21)
   - Kill switch <1s response (NFR2, FR17-FR18)
   - Authorization enforcement (FR13-FR16)
   
2. **Emergence Tests (`tests/emergence/`)**: Stigmergic validation (NFR35-37)
   - Emergence score >20% (Novel chains / Total paths)
   - Causal chain 3+ hop validation
   - 100% decision_context population

Per architecture (lines 1003-1005):

| Category | Location | Marker | Purpose |
|----------|----------|--------|---------|
| Safety | `tests/safety/` | `@pytest.mark.safety` | Gate tests (always run) |
| Emergence | `tests/emergence/` | `@pytest.mark.emergence` | Stigmergic validation (hard gate) |

### Emergence Test Protocol

Per architecture (lines 1030-1037):

1. **Isolated Run:** 100 agents, no stigmergic pub/sub, record all findings + attack paths
2. **Stigmergic Run:** 100 agents, full pub/sub enabled, record all findings + attack paths + decision_context
3. **Emergence Calculation:**
   - Novel chains = paths in stigmergic NOT in isolated
   - Emergence Score = len(novel_chains) / len(total_stigmergic_paths)
   - **HARD GATE: Emergence Score > 0.20**

### Expected Test Files

Per architecture (lines 909-936):

**Safety Tests:**
- `test_scope_blocks.py` - Scope violation scenarios
- `test_killswitch.py` - Kill switch timing (<1s)
- `test_auth_required.py` - Lateral movement auth
- `test_ssh_disconnect.py` - Engagement survives SSH drop *(future)*
- `test_pause_resume.py` - Pause/resume <1s verification *(future)*
- `test_message_integrity.py` - HMAC validation, AiTM mitigation *(future)*

**Emergence Tests:**
- `test_emergence_score.py` - >20% novel chains hard gate
- `test_causal_chains.py` - 3+ hop chain validation
- `test_decision_context.py` - decision_context population

### Placeholder Test Format

Placeholder tests should use `pytest.skip("Not implemented")` or `pass` with clear docstrings:

```python
import pytest

@pytest.mark.safety
def test_scope_blocks_out_of_range_ip():
    """Verify scope validator blocks IP outside allowed CIDR range."""
    pytest.skip("Not implemented - Story 1.8")
```

### Current State

- `tests/safety/__init__.py` exists (comment only)
- `tests/emergence/__init__.py` exists (comment only)
- Markers already registered in `tests/conftest.py` (lines 21-27)
- Story 0.2 established directory structure, this story adds placeholder content

### Previous Story Context (0-6)

Story 0-6 created the cyber-range test environment with:
- `cyber-range/docker-compose.yml` with 4 vulnerable services
- `cyber-range/expected-findings.json` (20 known vulnerabilities)
- `cyber-range/emergence-baseline.json` (isolated vs stigmergic comparison baseline)

The emergence tests in this story will eventually use the cyber-range and emergence-baseline.json.

### Git History Context

Recent commits:
- `873b553` - Refactor: Move to src/cyberred and enforce 100% coverage gates (Story 0.4)

### Project Structure Notes

- Location: `tests/safety/`, `tests/emergence/` (per architecture)
- Aligns with test category structure in conftest.py
- Markers already defined: `@pytest.mark.safety`, `@pytest.mark.emergence`

### References

- [Source: docs/3-solutioning/epics-stories.md#Story 0.7: Safety & Emergence Test Framework]
- [Source: docs/3-solutioning/architecture.md#Test Categories]
- [Source: docs/3-solutioning/architecture.md#Emergence Test Protocol]

## Dev Agent Record

### Agent Model Used

Antigravity (Google DeepMind)

### Debug Log References

- `pytest --collect-only -m safety`: 42 safety tests collected
- `pytest --collect-only -m emergence`: 40 emergence tests collected
- `pytest tests/unit tests/integration`: 18 passed (no regressions)
- Coverage check N/A: Story adds infrastructure files only, no `src/cyberred/` code

### Completion Notes List

- Created 3 safety test placeholder files:
  - `test_scope_blocks.py`: 11 test methods across 8 test classes covering IP range, hostname, port, protocol, logging, fail-closed, Unicode normalization, and ScopeViolationError scenarios
  - `test_killswitch.py`: 11 test methods across 4 test classes covering timing, tri-path execution, atomic flag, and resilience
  - `test_auth_required.py`: 13 test methods across 5 test classes covering authorization required, modal responses, queue, auto-pause, and deputy operator
- Created 3 emergence test placeholder files:
  - `test_emergence_score.py`: 11 test methods across 5 test classes covering score calculation, >20% hard gate, isolated run, stigmergic run, and comparison
  - `test_causal_chains.py`: 12 test methods across 4 test classes covering 3+ hop depth, chain structure, decision_context, and gate enforcement
  - `test_decision_context.py`: 14 test methods across 5 test classes covering 100% population, format, traceability, stigmergic proof, and CI validation
- Verified markers registered in `conftest.py` (lines 21-27)
- Created `tests/safety/README.md` with purpose, test categories, running instructions, and CI integration
- Created `tests/emergence/README.md` with purpose, test protocol, hard gates, and cyber-range integration
- Verified test discovery: 42 safety tests, 40 emergence tests discoverable via pytest markers
- All 18 existing tests pass (no regressions)

### File List

- `tests/safety/test_scope_blocks.py` (NEW)
- `tests/safety/test_killswitch.py` (NEW)
- `tests/safety/test_auth_required.py` (NEW)
- `tests/safety/README.md` (NEW)
- `tests/emergence/test_emergence_score.py` (NEW)
- `tests/emergence/test_causal_chains.py` (NEW)
- `tests/emergence/test_decision_context.py` (NEW)
- `tests/emergence/README.md` (NEW)

## Change Log

| Date | Change |
|------|--------|
| 2025-12-31 | Story created with comprehensive context for safety and emergence test framework |
| 2025-12-31 | Implemented all tasks: 6 test placeholder files, 2 README docs. 42 safety + 40 emergence tests discoverable. All 18 existing tests pass. |
