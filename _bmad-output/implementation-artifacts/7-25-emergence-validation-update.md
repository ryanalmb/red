# Story 7.25: Emergence Validation Update

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **emergence validation tests updated for 8 agent types**,
So that **NFR35-37 are properly validated with diverse agent swarms**.

## Acceptance Criteria

1. **Given** all 8 agent types are implemented (RECON, EXPLOIT, POSTEX, WEBAPP, WIRELESS, AD, CREDENTIAL, FORENSICS)
   **When** emergence comparison runs (stigmergic vs isolated)
   **Then** swarms with 8 diverse roles are tested

2. **Given** emergence score calculation runs
   **When** computing novel chains
   **Then** emergence score calculation considers all agent types in path analysis

3. **Given** causal chain tracking is active
   **When** chains are validated for depth (NFR36)
   **Then** causal chain tracking works across all agent types with proper decision_context propagation

4. **Given** stigmergic actions from diverse agents
   **When** decision_context population is validated (NFR37)
   **Then** decision_context propagation verified for all 8 roles

5. **Given** emergence tests run with role diversity
   **When** comparing 3-role swarm vs 8-role swarm
   **Then** tests verify that diversity improves emergence score

6. **Given** NFR35 hard gate (>20% novel chains)
   **When** emergence gate runs with full agent diversity
   **Then** NFR35 validated with 8 agent types contributing to novel chain discovery

## Tasks / Subtasks

- [x] Task 1: Update emergence test fixtures for 8-role diversity (AC: 1, 5)
  - [x] 1.1 Create `tests/emergence/test_role_diversity.py` with parametrized fixtures for all 8 AgentRole types
  - [x] 1.2 Add `eight_role_stigmergic_result` fixture to `conftest.py` with paths from all 8 agent types
  - [x] 1.3 Add `three_role_stigmergic_result` fixture for baseline comparison (RECON, EXPLOIT, POSTEX only)
  - [x] 1.4 Write unit tests to verify fixture creation for all roles

- [x] Task 2: Update `test_emergence_score.py` for multi-role scoring (AC: 2)
  - [x] 2.1 Add test `test_emergence_score_with_all_8_roles` validating scoring with diverse agent paths
  - [x] 2.2 Add test `test_novel_chains_identified_across_agent_types` verifying novel chain detection spans all roles
  - [x] 2.3 Add test `test_emergence_score_multi_role_vs_single_role` comparing emergence with role diversity
  - [x] 2.4 Write integration test verifying emergence scoring uses real agent role metadata

- [x] Task 3: Update `test_causal_chains.py` for cross-role chain validation (AC: 3)
  - [x] 3.1 Add fixture `cross_role_causal_chain` with chain spanning multiple agent types (e.g., RECON→EXPLOIT→POSTEX→AD)
  - [x] 3.2 Add test `test_causal_chain_spans_multiple_agent_types` validating 3+ hop chains across roles
  - [x] 3.3 Add test `test_decision_context_links_cross_role_findings` verifying context propagates between agent types
  - [x] 3.4 Add test `test_chain_depth_with_8_role_diversity` ensuring depth calculation handles all roles

- [x] Task 4: Update decision_context validation for all roles (AC: 4)
  - [x] 4.1 Add parametrized test `test_decision_context_populated_for_each_role` covering all 8 AgentRole values
  - [x] 4.2 Add test `test_decision_context_references_cross_role_signals` for inter-role signal tracking
  - [x] 4.3 Update `validate_decision_context()` tests in `test_emergence_gate.py` to use 8-role actions

- [x] Task 5: Create diversity comparison tests (AC: 5)
  - [x] 5.1 Add `test_emergence_improvement_with_diversity` comparing 3-role vs 8-role emergence scores
  - [x] 5.2 Add `test_role_diversity_increases_novel_path_discovery` measuring novel path counts
  - [x] 5.3 Add hypothesis test `test_diversity_hypothesis_more_roles_higher_emergence` with statistical validation

- [x] Task 6: Update NFR35 hard gate for full diversity (AC: 6)
  - [x] 6.1 Add test `test_nfr35_with_8_role_swarm` in `test_emergence_gate.py`
  - [x] 6.2 Add test `test_emergence_gate_report_shows_role_breakdown` verifying report includes per-role metrics
  - [x] 6.3 Update `EmergenceGateReport` dataclass to include `role_contributions: dict[AgentRole, int]` field
  - [x] 6.4 Write integration test verifying CI gate uses 8-role swarm data

- [x] Task 7: Run targeted tests and verify 100% coverage (AC: all)
  - [x] 7.1 Run `pytest tests/emergence/ --cov=src/cyberred/orchestration/emergence --cov-report=term-missing`
  - [x] 7.2 Ensure all new test code has 100% coverage
  - [x] 7.3 Verify no regressions in existing emergence tests

## Dev Notes

### Architecture Compliance

- **Test Framework:** pytest with `@pytest.mark.emergence` marker for all emergence tests
- **Test Location:** All emergence tests in `tests/emergence/` directory
- **Agent Roles:** Use `AgentRole` enum from `src/cyberred/agents/roles.py` (8 roles defined)
- **Emergence Framework:** Use existing `EmergenceComparisonFramework` from `src/cyberred/orchestration/emergence/comparison.py`
- **Causal Validation:** Use `CausalChainValidator` from `src/cyberred/orchestration/emergence/causal.py`
- **Models:** Use `AttackPath`, `PathStep`, `RunResult` from `src/cyberred/orchestration/emergence/models.py`

### Existing Code Structure

```
src/cyberred/orchestration/emergence/
├── __init__.py          # Exports: EmergenceComparisonFramework, CausalChainValidator, etc.
├── causal.py            # CausalChainValidator, ChainDepthResult, NFR36_MIN_CHAIN_DEPTH
├── comparison.py        # EmergenceComparisonFramework, EmergenceComparisonConfig
├── metrics.py           # Emergence metrics and Prometheus export
├── models.py            # AttackPath, PathStep, RunResult, ComparisonResult
├── patterns.py          # Pattern detection for emergent behavior
├── strategy.py          # Strategy synthesis from emergence
├── tracker.py           # Decision context tracking
└── validator.py         # Validation utilities

tests/emergence/
├── conftest.py          # Fixtures: emergence_config, comparison_framework, causal_validator
├── test_causal_chains.py    # NFR36 chain depth tests (3+ hops)
├── test_decision_context.py # NFR37 decision_context population tests
├── test_emergence_gate.py   # SHIP/NO-SHIP hard gate tests
├── test_emergence_score.py  # NFR35 >20% novel chains tests
└── README.md            # Emergence testing documentation
```

### Agent Roles (All 8 Implemented)

```python
class AgentRole(Enum):
    RECON = "recon"           # src/cyberred/agents/recon.py
    EXPLOIT = "exploit"       # src/cyberred/agents/exploit.py
    POSTEX = "postex"         # src/cyberred/agents/postex.py
    WEBAPP = "webapp"         # src/cyberred/agents/webapp.py
    WIRELESS = "wireless"     # src/cyberred/agents/wireless.py
    AD = "ad"                 # src/cyberred/agents/ad.py
    CREDENTIAL = "credential" # src/cyberred/agents/credential.py
    FORENSICS = "forensics"   # src/cyberred/agents/forensics.py
```

### Key Constants

- `NFR35_EMERGENCE_THRESHOLD = 0.20` (20% novel chains required)
- `NFR36_MIN_CHAIN_DEPTH = 3` (minimum 3-hop causal chains)
- `AGENT_COUNT = 100` (default for emergence tests, configurable via env)

### Testing Patterns

```python
# Parametrized test for all roles
@pytest.mark.parametrize("role", list(AgentRole))
def test_decision_context_for_role(role: AgentRole):
    ...

# Fixture for 8-role diversity
@pytest.fixture
def eight_role_stigmergic_result() -> RunResult:
    paths = []
    for role in AgentRole:
        paths.append(create_path_for_role(role))
    return RunResult(..., attack_paths=paths, ...)

# Diversity comparison
def test_diversity_improves_emergence(
    three_role_result: RunResult,
    eight_role_result: RunResult,
    comparison_framework: EmergenceComparisonFramework,
):
    score_3 = comparison_framework.compare(isolated, three_role_result).emergence_score
    score_8 = comparison_framework.compare(isolated, eight_role_result).emergence_score
    assert score_8 >= score_3  # More diversity should help or equal
```

### Project Structure Notes

- Tests follow TDD pattern: write failing tests first, then implementation
- All tests use `@pytest.mark.emergence` for selective test execution
- Integration tests should use mock mode by default (`EMERGENCE_MOCK_MODE=true`)
- Coverage requirement: 100% for new test code

### References

- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 7.25]
- [Source: tests/emergence/test_emergence_score.py] - Existing emergence score tests
- [Source: tests/emergence/test_causal_chains.py] - Existing causal chain tests
- [Source: tests/emergence/test_emergence_gate.py] - SHIP/NO-SHIP gate tests
- [Source: tests/emergence/conftest.py] - Shared fixtures
- [Source: src/cyberred/agents/roles.py] - AgentRole enum definition
- [Source: src/cyberred/orchestration/emergence/] - Emergence framework implementation

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

N/A - All tests passed on first run after UUID fix.

### Completion Notes List

1. Created `tests/emergence/test_role_diversity.py` with 34 tests covering all 8 agent roles
2. Added shared fixtures to `tests/emergence/conftest.py`:
   - `create_path_for_role()` - Creates AttackPath for a given AgentRole
   - `create_multi_step_path()` - Creates multi-hop causal chains across roles
   - `all_agent_roles` - Fixture returning all 8 AgentRole values
   - `three_role_list` - Fixture for baseline 3-role comparison
   - `eight_role_stigmergic_result` - Full 8-role RunResult fixture
   - `three_role_stigmergic_result` - Limited 3-role RunResult fixture
   - `isolated_baseline_result` - Minimal isolated run baseline
3. Updated `tests/emergence/test_emergence_score.py` with `TestEmergenceScoreWithRoleDiversity` class (4 new tests)
4. Updated `tests/emergence/test_causal_chains.py` with `TestCrossRoleCausalChains` class (6 new tests)
5. Updated `tests/emergence/test_decision_context.py` with `TestDecisionContextAllRoles` class (4 new tests)
6. Updated `tests/emergence/test_emergence_gate.py`:
   - Added `role_contributions: dict[str, int]` field to `EmergenceGateReport`
   - Updated `from_results()` to calculate per-role contribution metrics
   - Added `TestNFR35With8RoleSwarm` class (5 new tests)

### File List

**New Files:**
- `tests/emergence/test_role_diversity.py` - Main test file for 8-role diversity validation

**Modified Files:**
- `tests/emergence/conftest.py` - Added 8-role fixtures and helper functions
- `tests/emergence/test_emergence_score.py` - Added multi-role scoring tests
- `tests/emergence/test_causal_chains.py` - Added cross-role chain validation tests
- `tests/emergence/test_decision_context.py` - Added 8-role decision_context tests
- `tests/emergence/test_emergence_gate.py` - Added role_contributions to EmergenceGateReport and 8-role gate tests

### Test Summary

- Total emergence tests: 111 (all passing)
- New tests added: ~53 tests for Story 7.25
- Coverage: Emergence module core files at 80-100% coverage

