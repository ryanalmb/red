# Story 7.11: Causal Chain Depth Validation

Status: done

## Story

As a **developer**,
I want **causal chain depth validated to ensure 3+ hops exist**,
so that **we can prove emergent multi-step attack chains from stigmergic coordination (NFR36)**.

> [!IMPORTANT]
> **HARD GATE:** NFR36 requires at least one causal chain with 3+ hops (Finding→Action→Finding→Action→Finding). This story implements the `CausalChainValidator` that analyzes attack paths and validates the depth requirement.

## Acceptance Criteria

1. **CausalChainValidator class implementation**
   - `CausalChainValidator` class in `src/cyberred/orchestration/emergence/causal.py`
   - `validate_chain_depth(paths: list[AttackPath], min_depth: int = 3) -> ChainDepthResult` method
   - `find_deepest_chain(paths: list[AttackPath]) -> AttackPath | None` method
   - `get_chains_by_depth(paths: list[AttackPath]) -> dict[int, list[AttackPath]]` method

2. **ChainDepthResult dataclass**
   - `passed: bool` — whether NFR36 hard gate passed (at least one chain >= min_depth)
   - `min_required_depth: int` — the minimum depth required (3 for NFR36)
   - `max_observed_depth: int` — maximum depth found in any chain
   - `chains_meeting_requirement: int` — count of chains with depth >= min_depth
   - `total_chains: int` — total number of chains analyzed
   - `deepest_chain: AttackPath | None` — the chain with maximum depth
   - `depth_distribution: dict[int, int]` — count of chains at each depth level
   - `message: str` — human-readable result message

3. **Chain depth calculation**
   - Depth = number of hops in the chain (len(path.steps))
   - A 3-hop chain: Finding₁ → Action₁ → Finding₂ → Action₂ → Finding₃
   - Each `PathStep` represents one hop in the chain
   - Chains with depth < 1 are ignored (empty chains)

4. **Chain structure validation**
   - `validate_chain_structure(path: AttackPath) -> ChainStructureResult` method
   - Verify chain has valid root finding (first step has finding_id)
   - Verify each link references valid parent (decision_context traces back)
   - Verify no cycles exist in chain (no repeated action_ids)
   - Return detailed validation result with any errors found

5. **Decision context traceability**
   - `trace_chain_to_root(path: AttackPath) -> list[str]` method
   - Return ordered list of finding_ids from leaf to root
   - Verify 100% of steps have decision_context populated (NFR37 compliance)
   - Log warning if any step missing decision_context

6. **Prometheus metrics (OBS12)**
   - `cyberred_causal_chain_max_depth` gauge — maximum chain depth observed
   - `cyberred_causal_chain_count_3plus` gauge — count of chains with 3+ hops
   - `cyberred_causal_chain_hard_gate_passed` gauge — 1 if passed, 0 if failed
   - Labels: `engagement_id`, `run_id`

7. **Integration with EmergenceComparisonFramework**
   - `CausalChainValidator` can be used standalone or by comparison framework
   - Add `validate_causal_depth()` method to `EmergenceComparisonFramework`
   - Existing emergence tests updated to include causal chain validation

8. **Quality gates**
   - 100% unit test coverage for `src/cyberred/orchestration/emergence/causal.py`
   - All placeholder tests in `tests/emergence/test_causal_chains.py` implemented
   - Integration tests verify chain extraction from real agent actions

## Tasks / Subtasks

### Phase 1 (RED): Tests first

- [x] Update `tests/emergence/test_causal_chains.py` - implement all placeholder tests
  - [x] `TestCausalChainDepth.test_causal_chain_minimum_3_hops` — verify 3+ hop detection
  - [x] `TestCausalChainDepth.test_causal_chain_discovery_to_exploitation` — verify recon→exploit hop
  - [x] `TestCausalChainDepth.test_causal_chain_exploitation_to_postex` — verify exploit→postex hop
  - [x] `TestCausalChainDepth.test_causal_chain_depth_exceeds_3_hops` — verify 4+ hop chains
  - [x] `TestCausalChainStructure.test_causal_chain_has_root_finding` — verify root finding exists
  - [x] `TestCausalChainStructure.test_causal_chain_links_are_valid` — verify parent references
  - [x] `TestCausalChainStructure.test_causal_chain_no_cycles` — verify no circular references
  - [x] `TestCausalChainDecisionContext.test_chain_action_has_decision_context` — verify context populated
  - [x] `TestCausalChainDecisionContext.test_decision_context_references_parent_findings` — verify parent refs
  - [x] `TestCausalChainDecisionContext.test_decision_context_traceable_to_root` — verify root traceability
  - [x] `TestCausalChainGate.test_causal_chain_gate_passes_with_3_hops` — verify gate passes
  - [x] `TestCausalChainGate.test_causal_chain_gate_fails_under_3_hops` — verify gate fails

- [x] Create `tests/unit/orchestration/emergence/test_causal.py`
  - [x] `CausalChainValidator` instantiation
  - [x] `validate_chain_depth()` with various inputs
  - [x] Edge case: empty paths list returns failed result
  - [x] Edge case: all paths depth < 3 returns failed result
  - [x] Edge case: single path with depth >= 3 returns passed result
  - [x] `find_deepest_chain()` returns correct path
  - [x] `get_chains_by_depth()` returns correct distribution
  - [x] `validate_chain_structure()` detects invalid structures
  - [x] `trace_chain_to_root()` returns correct order
  - [x] Prometheus metrics are set correctly

- [x] Create `tests/unit/orchestration/emergence/test_causal_models.py`
  - [x] `ChainDepthResult` dataclass validation
  - [x] `ChainStructureResult` dataclass validation
  - [x] JSON serialization for both dataclasses

### Phase 2 (GREEN): Minimal implementation

- [x] Create `src/cyberred/orchestration/emergence/causal.py`
  - [x] `ChainDepthResult` dataclass with all fields
  - [x] `ChainStructureResult` dataclass with all fields
  - [x] `CausalChainValidator` class
  - [x] `validate_chain_depth()` implementation
  - [x] `find_deepest_chain()` implementation
  - [x] `get_chains_by_depth()` implementation
  - [x] `validate_chain_structure()` implementation
  - [x] `trace_chain_to_root()` implementation
  - [x] `_setup_prometheus_metrics()` helper
  - [x] `export_prometheus_metrics()` implementation

- [x] Update `src/cyberred/orchestration/emergence/__init__.py`
  - [x] Export `CausalChainValidator`
  - [x] Export `ChainDepthResult`
  - [x] Export `ChainStructureResult`
  - [x] Export `NFR36_MIN_CHAIN_DEPTH` constant

- [x] Update `src/cyberred/orchestration/emergence/comparison.py`
  - [x] Import `CausalChainValidator`
  - [x] Add `validate_causal_chains()` method
  - [x] Call causal validation in `compare()` method (optional, log result)

### Phase 3 (REFACTOR): Quality

- [x] Achieve 100% coverage: `pytest tests/unit/orchestration/emergence/test_causal.py --cov=src/cyberred/orchestration/emergence/causal`
- [x] Lint clean: `ruff check src/cyberred/orchestration/emergence/causal.py`
- [x] Type check: `mypy src/cyberred/orchestration/emergence/causal.py`
- [x] Verify all emergence tests pass (including updated test_causal_chains.py)
- [x] Verify Prometheus metrics are properly registered

## Dev Notes

### Architecture references

Per architecture (lines 807-811, 909-911):
```
src/cyberred/orchestration/emergence/    # Stigmergic emergence validation (CRITICAL)
    ├── __init__.py
    ├── tracker.py            # Tracks decision_context across agents (Story 7.8 - DONE)
    ├── validator.py          # Validates decision_context population (Story 7.8 - DONE)
    ├── comparison.py         # Compares stigmergic vs isolated runs (Story 7.9 - DONE)
    ├── models.py             # Data models for comparison (Story 7.9 - DONE)
    ├── metrics.py            # Emergence score calculation (Story 7.10 - DONE)
    └── causal.py             # Causal chain depth validation (THIS STORY)

tests/emergence/
    ├── test_emergence_score.py   # >20% novel chains hard gate (Story 7.10 - DONE)
    ├── test_causal_chains.py     # 3+ hop chain validation (THIS STORY)
    └── test_decision_context.py  # decision_context population (Story 7.8 - DONE)
```

### NFR36 Requirements

Per architecture and PRD:
```
NFR36: Causal chain depth — at least one emergence chain with 3+ hops 
       (Finding→Action→Finding→Action→Finding) (Hard)
```

A valid 3-hop causal chain example:
```
Hop 1: ReconAgent discovers open port 22 (Finding₁: open_port)
       ↓ Finding₁ published to stigmergic layer
Hop 2: ExploitAgent sees Finding₁, attempts SSH brute force (Action₁)
       → Produces Finding₂: valid_credentials
       ↓ Finding₂ published to stigmergic layer  
Hop 3: PostExAgent sees Finding₂, escalates privileges (Action₂)
       → Produces Finding₃: root_access
```

### Data model design

```python
@dataclass
class ChainDepthResult:
    """NFR36 validation result."""
    passed: bool                         # At least one chain >= min_depth
    min_required_depth: int              # 3 for NFR36
    max_observed_depth: int              # Deepest chain found
    chains_meeting_requirement: int      # Count of chains >= min_depth
    total_chains: int
    deepest_chain: AttackPath | None
    depth_distribution: dict[int, int]   # {depth: count}
    message: str
    
    @classmethod
    def from_paths(cls, paths: list[AttackPath], min_depth: int = 3) -> "ChainDepthResult":
        """Create from paths list. Returns failed result if empty."""
        if not paths:
            return cls(False, min_depth, 0, 0, 0, None, {}, "NFR36 HARD GATE FAILED: No chains")
        
        depth_dist = {d: sum(1 for p in paths if p.depth == d) for d in set(p.depth for p in paths)}
        deepest = max(paths, key=lambda p: p.depth)
        meeting_req = sum(1 for p in paths if p.depth >= min_depth)
        passed = meeting_req > 0
        msg = f"NFR36 {'PASSED' if passed else 'FAILED'}: {meeting_req} chain(s) >= {min_depth} hops, max={deepest.depth}"
        return cls(passed, min_depth, deepest.depth, meeting_req, len(paths), deepest, depth_dist, msg)

@dataclass  
class ChainStructureResult:
    """Chain structure validation result."""
    valid: bool
    has_root_finding: bool
    all_links_valid: bool
    has_cycles: bool
    missing_decision_context: list[str]  # action_ids missing context
    errors: list[str]
```

### CausalChainValidator class structure

```python
NFR36_MIN_CHAIN_DEPTH = 3

class CausalChainValidator:
    """Validates causal chain depth (NFR36) and structure (NFR37)."""
    
    def __init__(self, prometheus_registry: Any = None) -> None:
        self._log = structlog.get_logger().bind(component="causal_chain_validator")
        self._registry = prometheus_registry
        self._setup_prometheus_metrics()
    
    def validate_chain_depth(self, paths: list[AttackPath], min_depth: int = 3) -> ChainDepthResult:
        """Validate at least one chain meets min_depth. Returns ChainDepthResult."""
        result = ChainDepthResult.from_paths(paths, min_depth)
        self._log.info("chain_depth_validated", passed=result.passed, max_depth=result.max_observed_depth)
        return result
    
    def find_deepest_chain(self, paths: list[AttackPath]) -> AttackPath | None:
        """Return chain with max depth, or None if empty."""
        return max(paths, key=lambda p: p.depth) if paths else None
    
    def get_chains_by_depth(self, paths: list[AttackPath]) -> dict[int, list[AttackPath]]:
        """Group chains by depth. Returns {depth: [paths]}."""
        result: dict[int, list[AttackPath]] = {}
        for p in paths:
            result.setdefault(p.depth, []).append(p)
        return result
    
    def validate_chain_structure(self, path: AttackPath) -> ChainStructureResult:
        """Validate chain structure: root finding, no cycles, valid links, decision_context."""
        errors, missing_context = [], []
        
        # Check root finding
        has_root = bool(path.steps and path.steps[0].finding_id)
        if not has_root:
            errors.append("Missing root finding")
        
        # Check cycles
        seen, has_cycles = set(), False
        for step in path.steps:
            if step.action_id in seen:
                has_cycles = True
                errors.append(f"Cycle: {step.action_id}")
            seen.add(step.action_id)
        
        # Check decision_context (NFR37)
        missing_context = [s.action_id for s in path.steps if not s.decision_context]
        if missing_context:
            errors.append(f"NFR37: {len(missing_context)} steps missing decision_context")
        
        # Validate links
        all_links_valid, prior_findings = True, set()
        for i, step in enumerate(path.steps):
            if i > 0 and step.decision_context:
                if not any(ctx in prior_findings or ctx == "isolated_mode" for ctx in step.decision_context):
                    all_links_valid = False
                    errors.append(f"Step {i} doesn't reference prior findings")
            if step.finding_id:
                prior_findings.add(step.finding_id)
        
        valid = has_root and not has_cycles and all_links_valid and not missing_context
        return ChainStructureResult(valid, has_root, all_links_valid, has_cycles, missing_context, errors)
    
    def trace_chain_to_root(self, path: AttackPath) -> list[str]:
        """Return finding_ids from leaf to root (reversed)."""
        return list(reversed([s.finding_id for s in path.steps if s.finding_id]))
    
    def export_prometheus_metrics(self, result: ChainDepthResult, engagement_id: str, run_id: str) -> None:
        """Export metrics to Prometheus (OBS12). Noop if prometheus unavailable."""
        if not self._prometheus_available:
            return
        labels = {"engagement_id": engagement_id, "run_id": run_id}
        self._max_depth_gauge.labels(**labels).set(result.max_observed_depth)
        self._count_3plus_gauge.labels(**labels).set(result.chains_meeting_requirement)
        self._hard_gate_gauge.labels(**labels).set(1 if result.passed else 0)
    
    def _setup_prometheus_metrics(self) -> None:
        """Setup Prometheus gauges. Pattern from metrics.py (Story 7.10)."""
        try:
            from prometheus_client import REGISTRY, Gauge
            registry = self._registry or REGISTRY
            
            def get_or_create(name, desc, labels):
                if hasattr(registry, '_names_to_collectors') and name in registry._names_to_collectors:
                    return registry._names_to_collectors[name]
                return Gauge(name, desc, labels, registry=registry)
            
            self._max_depth_gauge = get_or_create("cyberred_causal_chain_max_depth", "Max chain depth", ["engagement_id", "run_id"])
            self._count_3plus_gauge = get_or_create("cyberred_causal_chain_count_3plus", "Chains with 3+ hops", ["engagement_id", "run_id"])
            self._hard_gate_gauge = get_or_create("cyberred_causal_chain_hard_gate_passed", "NFR36 gate (1=pass)", ["engagement_id", "run_id"])
            self._prometheus_available = True
        except ImportError:
            self._prometheus_available = False
```

### Integration with EmergenceComparisonFramework

Add to `comparison.py`:

```python
# In EmergenceComparisonFramework.__init__:
self._causal_validator = CausalChainValidator()

# New method:
def validate_causal_depth(self, stigmergic: RunResult) -> ChainDepthResult:
    result = self._causal_validator.validate_chain_depth(stigmergic.attack_paths)
    self._causal_validator.export_prometheus_metrics(result, stigmergic.run_id, stigmergic.run_id)
    return result
```

### Relationship to Previous Stories

| Story | Provides | Used By This Story |
|-------|----------|-------------------|
| 7.8 | `DecisionContextTracker` | Populates `decision_context` in actions |
| 7.8 | `validator.py` | Validates decision_context is populated |
| 7.9 | `AttackPath`, `PathStep` models | Data structures for chain analysis |
| 7.9 | `extract_attack_paths()` | Extracts paths from actions/findings |
| 7.10 | `EmergenceMetrics` | Pattern for metrics class design |
| 7.10 | Prometheus gauge pattern | Reuse `get_or_create_gauge()` helper |

### Test Implementation Pattern

```python
# Example: tests/emergence/test_causal_chains.py
def test_causal_chain_minimum_3_hops():
    validator = CausalChainValidator()
    path = AttackPath(steps=[
        PathStep("target1", "recon", "f1", "a1", []),        # Hop 1
        PathStep("target1", "exploit", "f2", "a2", ["f1"]),  # Hop 2  
        PathStep("target1", "postex", "f3", "a3", ["f2"]),   # Hop 3
    ])
    result = validator.validate_chain_depth([path])
    assert result.passed and result.max_observed_depth == 3
```

### Project Structure Notes

- **File locations**:
  - `src/cyberred/orchestration/emergence/causal.py` (NEW)
  - `src/cyberred/orchestration/emergence/__init__.py` (UPDATE exports)
  - `src/cyberred/orchestration/emergence/comparison.py` (UPDATE - add causal validation)
- **Test locations**:
  - `tests/unit/orchestration/emergence/test_causal.py` (NEW)
  - `tests/unit/orchestration/emergence/test_causal_models.py` (NEW)
  - `tests/emergence/test_causal_chains.py` (UPDATE - implement placeholders)
- **Dependencies**:
  - `prometheus_client` (optional — graceful degradation if not installed)
  - `structlog` for logging
  - Models from `src/cyberred/orchestration/emergence/models.py`
- **Virtual environment**: Use `venv` (not `.venv`) if creating new environments

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#lines 807-811] - Emergence module structure
- [Source: _bmad-output/planning-artifacts/architecture.md#lines 909-911] - Test structure
- [Source: _bmad-output/planning-artifacts/epics-stories.md#NFR36] - NFR36 requirements
- [Source: _bmad-output/planning-artifacts/epic-7-agent-refactor-proposal.md#line 1263] - Story 7.11 definition
- [Source: tests/emergence/README.md] - Emergence test documentation
- [Source: tests/emergence/test_causal_chains.py] - Placeholder tests to implement
- [Source: src/cyberred/orchestration/emergence/models.py] - AttackPath, PathStep models
- [Source: src/cyberred/orchestration/emergence/metrics.py] - Pattern for metrics class
- [Source: src/cyberred/orchestration/emergence/comparison.py] - Framework to integrate with
- [Source: src/cyberred/orchestration/emergence/tracker.py] - DecisionContextTracker (NFR37)
- [Source: _bmad-output/implementation-artifacts/7-10-emergence-score-calculation.md] - Previous story context

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

- All 58 tests pass
- 100% code coverage on `causal.py`
- Ruff lint clean
- mypy type check clean (after fix)

### Completion Notes List

- Story 7.11 implementation complete
- NFR36 hard gate validation implemented
- Prometheus metrics (OBS12) implemented
- Integration with EmergenceComparisonFramework complete

### File List

**New Files:**
- `src/cyberred/orchestration/emergence/causal.py` - CausalChainValidator, ChainDepthResult, ChainStructureResult
- `tests/unit/orchestration/emergence/test_causal.py` - Unit tests for CausalChainValidator (33 tests)
- `tests/unit/orchestration/emergence/test_causal_models.py` - Unit tests for dataclasses (11 tests)

**Modified Files:**
- `src/cyberred/orchestration/emergence/__init__.py` - Added exports for causal module
- `src/cyberred/orchestration/emergence/comparison.py` - Added validate_causal_chains() method
- `tests/emergence/test_causal_chains.py` - Implemented all placeholder tests (14 tests)

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-27 | Story implementation complete - all ACs met | Dev Agent |
| 2026-01-27 | Code review fixes - mypy type annotation fix | Review Agent |

