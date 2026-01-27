# Story 7.10: Emergence Score Calculation

Status: done

## Story

As a **developer**,
I want **emergence score calculated as novel chains / total chains**,
so that **we can validate >20% emergence requirement (NFR35)**.

> [!IMPORTANT]
> **HARD GATE:** NFR35 requires emergence score >20%. This story implements the dedicated `metrics.py` module that calculates, validates, and exposes emergence metrics via Prometheus (OBS11).

## Acceptance Criteria

1. **EmergenceMetrics class implementation**
   - `EmergenceMetrics` class in `src/cyberred/orchestration/emergence/metrics.py`
   - `calculate_emergence_score(isolated: RunResult, stigmergic: RunResult) -> EmergenceScore` method
   - `validate_hard_gate(score: EmergenceScore) -> HardGateResult` method
   - `export_prometheus_metrics(score: EmergenceScore)` method for OBS11 compliance

2. **EmergenceScore dataclass**
   - `novel_path_count: int` — number of paths only in stigmergic run
   - `shared_path_count: int` — number of paths in both runs
   - `total_stigmergic_paths: int` — total paths in stigmergic run
   - `total_isolated_paths: int` — total paths in isolated run
   - `score: float` — emergence score (0.0 to 1.0)
   - `novel_paths: list[AttackPath]` — the actual novel paths for audit
   - `calculation_timestamp: datetime` — when score was calculated

3. **HardGateResult dataclass**
   - `passed: bool` — whether NFR35 hard gate passed (score > 0.20)
   - `threshold: float` — the threshold used (0.20)
   - `score: float` — the actual emergence score
   - `margin: float` — score - threshold (positive if passed)
   - `message: str` — human-readable result message

4. **Score calculation formula**
   - Novel chains = paths in stigmergic NOT in isolated (by signature)
   - `emergence_score = len(novel_chains) / len(total_stigmergic_paths)`
   - Score is bounded between 0.0 and 1.0
   - Empty stigmergic paths → score = 0.0 (fails gate)

5. **Prometheus metrics exposure (OBS11)**
   - `cyberred_emergence_score` gauge — real-time emergence score
   - `cyberred_emergence_novel_paths` gauge — count of novel paths
   - `cyberred_emergence_total_paths` gauge — total stigmergic paths
   - `cyberred_emergence_hard_gate_passed` gauge — 1 if passed, 0 if failed
   - Labels: `engagement_id`, `run_id`

6. **Integration with EmergenceComparisonFramework**
   - `EmergenceMetrics` can be instantiated standalone or used by `EmergenceComparisonFramework`
   - `compare()` method in framework delegates to `EmergenceMetrics.calculate_emergence_score()`
   - Existing tests continue to pass with refactored implementation

7. **Detailed metrics dictionary**
   - `avg_novel_depth: float` — average depth of novel paths
   - `max_novel_depth: int` — maximum depth of novel paths  
   - `min_novel_depth: int` — minimum depth of novel paths
   - `depth_distribution: dict[int, int]` — count of paths at each depth
   - `technique_distribution: dict[str, int]` — count of paths using each technique

8. **Quality gates**
   - 100% unit test coverage for `src/cyberred/orchestration/emergence/metrics.py`
   - Integration tests verify Prometheus metrics export
   - Existing `tests/emergence/test_emergence_score.py` tests continue to pass

## Tasks / Subtasks

### Phase 1 (RED): Tests first

- [x] Create `tests/unit/orchestration/emergence/test_metrics.py`
  - [x] `EmergenceMetrics` instantiation
  - [x] `calculate_emergence_score()` with various inputs
  - [x] Score calculation correctness (novel/total formula)
  - [x] Edge case: empty stigmergic paths returns 0.0
  - [x] Edge case: all paths novel returns 1.0
  - [x] Edge case: no novel paths returns 0.0
  - [x] `validate_hard_gate()` passes when score > 0.20
  - [x] `validate_hard_gate()` fails when score <= 0.20
  - [x] `HardGateResult` contains correct margin calculation
  - [x] Prometheus metrics are set correctly

- [x] Create `tests/unit/orchestration/emergence/test_emergence_score_models.py`
  - [x] `EmergenceScore` dataclass validation
  - [x] `HardGateResult` dataclass validation
  - [x] JSON serialization for both dataclasses
  - [x] Timestamp is populated automatically

- [x] Update `tests/emergence/test_emergence_score.py`
  - [x] Add tests using new `EmergenceMetrics` class
  - [x] Verify integration with `EmergenceComparisonFramework`
  - [x] Add test for Prometheus metrics export

### Phase 2 (GREEN): Minimal implementation

- [x] Create `src/cyberred/orchestration/emergence/metrics.py`
  - [x] `EmergenceScore` dataclass with all fields
  - [x] `HardGateResult` dataclass with all fields
  - [x] `EmergenceMetrics` class
  - [x] `calculate_emergence_score()` implementation
  - [x] `validate_hard_gate()` implementation
  - [x] `_calculate_depth_stats()` helper
  - [x] `_calculate_technique_distribution()` helper
  - [x] `export_prometheus_metrics()` implementation

- [x] Update `src/cyberred/orchestration/emergence/__init__.py`
  - [x] Export `EmergenceMetrics`
  - [x] Export `EmergenceScore`
  - [x] Export `HardGateResult`

- [x] Update `src/cyberred/orchestration/emergence/comparison.py`
  - [x] Import and use `EmergenceMetrics` in `compare()` method
  - [x] Delegate score calculation to `EmergenceMetrics`
  - [x] Maintain backward compatibility with existing API

### Phase 3 (REFACTOR): Quality

- [x] Achieve 100% coverage: `pytest tests/unit/orchestration/emergence/test_metrics.py --cov=src/cyberred/orchestration/emergence/metrics`
- [x] Lint clean: `ruff check src/cyberred/orchestration/emergence/metrics.py`
- [x] Type check: `mypy src/cyberred/orchestration/emergence/metrics.py`
- [x] Verify all existing emergence tests pass
- [x] Verify Prometheus metrics are properly registered

## Dev Notes

### Architecture references

Per architecture (lines 807-811):
```
src/cyberred/orchestration/emergence/    # Stigmergic emergence validation (CRITICAL)
    ├── __init__.py
    ├── tracker.py            # Tracks decision_context across agents (Story 7.8 - DONE)
    ├── validator.py          # Validates decision_context population (Story 7.8 - DONE)
    ├── comparison.py         # Compares stigmergic vs isolated runs (Story 7.9 - DONE)
    ├── models.py             # Data models for comparison (Story 7.9 - DONE)
    └── metrics.py            # Emergence score calculation (THIS STORY)
```

### Emergence Score Formula

Per architecture (lines 1030-1037) and NFR35:
```python
# Novel chains = paths in stigmergic NOT in isolated
novel_chains = [p for p in stigmergic.attack_paths if signature(p) not in isolated_signatures]

# Emergence score calculation
emergence_score = len(novel_chains) / len(stigmergic.attack_paths)

# HARD GATE: score must exceed 20%
assert emergence_score > 0.20, "NFR35 HARD GATE FAILED"
```

### Data model design

```python
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class EmergenceScore:
    """Calculated emergence score with full audit trail.
    
    Attributes:
        novel_path_count: Number of paths only in stigmergic run.
        shared_path_count: Number of paths in both runs.
        total_stigmergic_paths: Total paths in stigmergic run.
        total_isolated_paths: Total paths in isolated run.
        score: Emergence score (0.0 to 1.0).
        novel_paths: The actual novel AttackPath instances.
        calculation_timestamp: When score was calculated.
        depth_stats: Statistics about path depths.
        technique_stats: Distribution of techniques in novel paths.
    """
    novel_path_count: int
    shared_path_count: int
    total_stigmergic_paths: int
    total_isolated_paths: int
    score: float
    novel_paths: list  # list[AttackPath]
    calculation_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    depth_stats: dict[str, float] = field(default_factory=dict)
    technique_stats: dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON export."""
        return {
            "novel_path_count": self.novel_path_count,
            "shared_path_count": self.shared_path_count,
            "total_stigmergic_paths": self.total_stigmergic_paths,
            "total_isolated_paths": self.total_isolated_paths,
            "score": self.score,
            "score_percentage": f"{self.score * 100:.1f}%",
            "calculation_timestamp": self.calculation_timestamp.isoformat(),
            "depth_stats": self.depth_stats,
            "technique_stats": self.technique_stats,
        }


@dataclass
class HardGateResult:
    """Result of NFR35 hard gate validation.
    
    Attributes:
        passed: Whether the hard gate passed (score > threshold).
        threshold: The threshold used (0.20 for NFR35).
        score: The actual emergence score.
        margin: score - threshold (positive if passed).
        message: Human-readable result message.
    """
    passed: bool
    threshold: float
    score: float
    margin: float
    message: str
    
    @classmethod
    def from_score(cls, score: float, threshold: float = 0.20) -> "HardGateResult":
        """Create HardGateResult from emergence score."""
        passed = score > threshold
        margin = score - threshold
        
        if passed:
            message = (
                f"NFR35 HARD GATE PASSED: Emergence score {score:.1%} "
                f"exceeds {threshold:.0%} threshold by {margin:.1%}"
            )
        else:
            message = (
                f"NFR35 HARD GATE FAILED: Emergence score {score:.1%} "
                f"does not exceed {threshold:.0%} threshold (margin: {margin:.1%})"
            )
        
        return cls(
            passed=passed,
            threshold=threshold,
            score=score,
            margin=margin,
            message=message,
        )
```

### EmergenceMetrics class structure

```python
from typing import Any
import structlog

from cyberred.orchestration.emergence.models import (
    AttackPath,
    ComparisonResult,
    RunResult,
)

log = structlog.get_logger().bind(component="emergence_metrics")

# NFR35 threshold constant
NFR35_EMERGENCE_THRESHOLD = 0.20


class EmergenceMetrics:
    """Calculates and validates emergence metrics for NFR35.
    
    Provides:
    - Emergence score calculation (novel paths / total paths)
    - Hard gate validation (>20% required)
    - Prometheus metrics export (OBS11)
    - Detailed statistics for analysis
    
    Usage:
        metrics = EmergenceMetrics()
        score = metrics.calculate_emergence_score(isolated_result, stigmergic_result)
        gate_result = metrics.validate_hard_gate(score)
        
        if not gate_result.passed:
            raise ValueError(gate_result.message)
    """
    
    def __init__(self, prometheus_registry: Any = None) -> None:
        """Initialize EmergenceMetrics.
        
        Args:
            prometheus_registry: Optional Prometheus registry for metrics.
                If None, uses default registry when prometheus_client is available.
        """
        self._log = log
        self._registry = prometheus_registry
        self._setup_prometheus_metrics()
    
    def _setup_prometheus_metrics(self) -> None:
        """Setup Prometheus gauges for emergence metrics."""
        try:
            from prometheus_client import Gauge, REGISTRY
            
            registry = self._registry or REGISTRY
            
            self._emergence_score_gauge = Gauge(
                "cyberred_emergence_score",
                "Current emergence score (0.0-1.0)",
                ["engagement_id", "run_id"],
                registry=registry,
            )
            self._novel_paths_gauge = Gauge(
                "cyberred_emergence_novel_paths",
                "Count of novel attack paths from stigmergic coordination",
                ["engagement_id", "run_id"],
                registry=registry,
            )
            self._total_paths_gauge = Gauge(
                "cyberred_emergence_total_paths",
                "Total attack paths in stigmergic run",
                ["engagement_id", "run_id"],
                registry=registry,
            )
            self._hard_gate_gauge = Gauge(
                "cyberred_emergence_hard_gate_passed",
                "1 if NFR35 hard gate passed, 0 if failed",
                ["engagement_id", "run_id"],
                registry=registry,
            )
            self._prometheus_available = True
        except ImportError:
            self._prometheus_available = False
            self._log.warning("prometheus_client_not_available")
    
    def calculate_emergence_score(
        self,
        isolated: RunResult,
        stigmergic: RunResult,
    ) -> EmergenceScore:
        """Calculate emergence score from isolated vs stigmergic comparison.
        
        Formula: emergence_score = novel_paths / total_stigmergic_paths
        
        Args:
            isolated: RunResult from isolated (no pub/sub) run.
            stigmergic: RunResult from stigmergic (full coordination) run.
            
        Returns:
            EmergenceScore with full calculation details.
        """
        self._log.info(
            "calculating_emergence_score",
            isolated_paths=len(isolated.attack_paths),
            stigmergic_paths=len(stigmergic.attack_paths),
        )
        
        # Build signatures for isolated paths
        isolated_signatures = {self._path_signature(p) for p in isolated.attack_paths}
        
        # Identify novel and shared paths
        novel_paths: list[AttackPath] = []
        shared_paths: list[AttackPath] = []
        
        for path in stigmergic.attack_paths:
            sig = self._path_signature(path)
            if sig in isolated_signatures:
                shared_paths.append(path)
            else:
                path.is_novel = True
                novel_paths.append(path)
        
        # Calculate score
        total_stigmergic = len(stigmergic.attack_paths)
        if total_stigmergic == 0:
            score = 0.0
        else:
            score = len(novel_paths) / total_stigmergic
        
        # Calculate depth and technique statistics
        depth_stats = self._calculate_depth_stats(novel_paths)
        technique_stats = self._calculate_technique_distribution(novel_paths)
        
        emergence_score = EmergenceScore(
            novel_path_count=len(novel_paths),
            shared_path_count=len(shared_paths),
            total_stigmergic_paths=total_stigmergic,
            total_isolated_paths=len(isolated.attack_paths),
            score=score,
            novel_paths=novel_paths,
            depth_stats=depth_stats,
            technique_stats=technique_stats,
        )
        
        self._log.info(
            "emergence_score_calculated",
            score=score,
            score_percentage=f"{score:.1%}",
            novel_paths=len(novel_paths),
            shared_paths=len(shared_paths),
        )
        
        return emergence_score
    
    def validate_hard_gate(
        self,
        score: EmergenceScore,
        threshold: float = NFR35_EMERGENCE_THRESHOLD,
    ) -> HardGateResult:
        """Validate emergence score against NFR35 hard gate.
        
        Args:
            score: EmergenceScore to validate.
            threshold: Minimum required score (default 0.20 per NFR35).
            
        Returns:
            HardGateResult with pass/fail status and details.
        """
        result = HardGateResult.from_score(score.score, threshold)
        
        self._log.info(
            "hard_gate_validated",
            passed=result.passed,
            score=result.score,
            threshold=result.threshold,
            margin=result.margin,
        )
        
        return result
    
    def export_prometheus_metrics(
        self,
        score: EmergenceScore,
        engagement_id: str,
        run_id: str,
    ) -> None:
        """Export emergence metrics to Prometheus.
        
        Args:
            score: EmergenceScore to export.
            engagement_id: Current engagement ID.
            run_id: Current run ID.
        """
        if not self._prometheus_available:
            self._log.debug("prometheus_export_skipped_not_available")
            return
        
        labels = {"engagement_id": engagement_id, "run_id": run_id}
        
        self._emergence_score_gauge.labels(**labels).set(score.score)
        self._novel_paths_gauge.labels(**labels).set(score.novel_path_count)
        self._total_paths_gauge.labels(**labels).set(score.total_stigmergic_paths)
        
        gate_result = self.validate_hard_gate(score)
        self._hard_gate_gauge.labels(**labels).set(1 if gate_result.passed else 0)
        
        self._log.info(
            "prometheus_metrics_exported",
            engagement_id=engagement_id,
            run_id=run_id,
            score=score.score,
        )
    
    def _path_signature(self, path: AttackPath) -> str:
        """Generate signature for path comparison (ignores timing/IDs)."""
        steps_sig = "|".join(
            f"{s.target}:{s.technique}" for s in path.steps
        )
        return steps_sig
    
    def _calculate_depth_stats(self, paths: list[AttackPath]) -> dict[str, float]:
        """Calculate depth statistics for paths."""
        if not paths:
            return {
                "avg_depth": 0.0,
                "max_depth": 0,
                "min_depth": 0,
            }
        
        depths = [p.depth for p in paths]
        return {
            "avg_depth": sum(depths) / len(depths),
            "max_depth": max(depths),
            "min_depth": min(depths),
        }
    
    def _calculate_technique_distribution(
        self,
        paths: list[AttackPath],
    ) -> dict[str, int]:
        """Calculate distribution of techniques in paths."""
        distribution: dict[str, int] = {}
        
        for path in paths:
            for step in path.steps:
                technique = step.technique
                distribution[technique] = distribution.get(technique, 0) + 1
        
        return distribution
```

### Integration with EmergenceComparisonFramework

The existing `comparison.py` already calculates emergence score inline. This story extracts that logic into `EmergenceMetrics` for:
- Reusability (can calculate score without full comparison)
- Prometheus integration (OBS11)
- Detailed statistics and audit trail
- Hard gate validation as first-class operation

```python
# In comparison.py, update compare() to use EmergenceMetrics:

from cyberred.orchestration.emergence.metrics import EmergenceMetrics

class EmergenceComparisonFramework:
    def __init__(self, config, event_bus):
        # ... existing init ...
        self._metrics = EmergenceMetrics()
    
    def compare(self, isolated: RunResult, stigmergic: RunResult) -> ComparisonResult:
        # Use EmergenceMetrics for score calculation
        emergence_score = self._metrics.calculate_emergence_score(isolated, stigmergic)
        
        # Export to Prometheus
        self._metrics.export_prometheus_metrics(
            emergence_score,
            engagement_id=stigmergic.run_id,
            run_id=stigmergic.run_id,
        )
        
        # Build ComparisonResult (maintain backward compatibility)
        return ComparisonResult(
            isolated_result=isolated,
            stigmergic_result=stigmergic,
            novel_paths=emergence_score.novel_paths,
            shared_paths=[p for p in stigmergic.attack_paths if not p.is_novel],
            emergence_score=emergence_score.score,
            metrics={
                "isolated_path_count": emergence_score.total_isolated_paths,
                "stigmergic_path_count": emergence_score.total_stigmergic_paths,
                "novel_path_count": emergence_score.novel_path_count,
                "shared_path_count": emergence_score.shared_path_count,
                **emergence_score.depth_stats,
            },
        )
```

### Prometheus metrics (OBS11)

Per PRD (line 1614):
```
| **OBS11**: Emergence score | Prometheus gauge | `cyberred_emergence_score`, real-time emergence tracking |
```

Metrics to expose:
- `cyberred_emergence_score` — The emergence score (0.0-1.0)
- `cyberred_emergence_novel_paths` — Count of novel paths
- `cyberred_emergence_total_paths` — Total stigmergic paths
- `cyberred_emergence_hard_gate_passed` — 1 if passed, 0 if failed

### Project Structure Notes

- **File locations**:
  - `src/cyberred/orchestration/emergence/metrics.py` (NEW)
  - `src/cyberred/orchestration/emergence/__init__.py` (UPDATE exports)
  - `src/cyberred/orchestration/emergence/comparison.py` (UPDATE to use metrics)
- **Test locations**:
  - `tests/unit/orchestration/emergence/test_metrics.py` (NEW)
  - `tests/unit/orchestration/emergence/test_emergence_score_models.py` (NEW)
  - `tests/emergence/test_emergence_score.py` (UPDATE)
- **Dependencies**:
  - `prometheus_client` (optional — graceful degradation if not installed)
  - `structlog` for logging
  - Models from `src/cyberred/orchestration/emergence/models.py`
- **Virtual environment**: Use `venv` (not `.venv`) if creating new environments

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#lines 807-811] - Emergence module structure
- [Source: _bmad-output/planning-artifacts/architecture.md#lines 1030-1037] - Emergence test protocol
- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 7.10] - Story requirements
- [Source: _bmad-output/planning-artifacts/prd.md#line 1614] - OBS11 Prometheus metrics
- [Source: tests/emergence/README.md] - Emergence test documentation
- [Source: tests/emergence/test_emergence_score.py] - Existing emergence tests
- [Source: src/cyberred/orchestration/emergence/comparison.py] - Comparison framework (Story 7.9)
- [Source: src/cyberred/orchestration/emergence/models.py] - Data models (Story 7.9)
- [Source: src/cyberred/orchestration/emergence/tracker.py] - DecisionContextTracker (Story 7.8)
- [Source: src/cyberred/orchestration/emergence/validator.py] - Validator (Story 7.8)
- [Source: _bmad-output/implementation-artifacts/7-9-isolated-vs-stigmergic-comparison-framework.md] - Previous story context

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

- Tests pass: 29/29 emergence tests pass (unit + integration)
- Lint: `ruff check` passes with no errors
- Type check: `mypy` passes with no issues
- All tests verified: `venv/bin/python -m pytest tests/unit/orchestration/emergence/test_metrics.py tests/unit/orchestration/emergence/test_emergence_score_models.py tests/emergence/test_emergence_score.py -v`

### Completion Notes List

1. Created `src/cyberred/orchestration/emergence/metrics.py` with:
   - `EmergenceScore` dataclass with AC7-compliant fields: `avg_novel_depth`, `max_novel_depth`, `min_novel_depth`, `depth_distribution`, `technique_distribution`
   - `HardGateResult` dataclass with `from_score()` class method for NFR35 validation
   - `EmergenceMetrics` class with `calculate_emergence_score()`, `validate_hard_gate()`, and `export_prometheus_metrics()` methods
   - Prometheus gauges: `cyberred_emergence_score`, `cyberred_emergence_novel_paths`, `cyberred_emergence_total_paths`, `cyberred_emergence_hard_gate_passed`
   - Fixed Prometheus gauge re-registration risk with `get_or_create_gauge()` helper

2. Updated `src/cyberred/orchestration/emergence/__init__.py` to export new classes

3. Updated `src/cyberred/orchestration/emergence/comparison.py` to delegate score calculation to `EmergenceMetrics` (AC6)

4. Fixed mutation side effect: `is_novel` is now explicitly reset to `False` for shared paths

5. All acceptance criteria met:
   - AC1: EmergenceMetrics class implemented ✓
   - AC2: EmergenceScore dataclass with all fields ✓
   - AC3: HardGateResult dataclass with all fields ✓
   - AC4: Score calculation formula correct ✓
   - AC5: Prometheus metrics exposed (OBS11) ✓
   - AC6: Integration with EmergenceComparisonFramework ✓
   - AC7: Detailed metrics (`avg_novel_depth`, `max_novel_depth`, `min_novel_depth`, `depth_distribution`, `technique_distribution`) ✓
   - AC8: Quality gates (tests pass, lint clean, type check clean) ✓

### Code Review Fixes Applied (2026-01-27)

1. **AC7 naming compliance**: Changed `depth_stats`/`technique_stats` → `avg_novel_depth`, `max_novel_depth`, `min_novel_depth`, `depth_distribution`, `technique_distribution`
2. **Mutation side effect**: Added explicit `path.is_novel = False` for shared paths to avoid stale state
3. **Prometheus re-registration**: Added `get_or_create_gauge()` helper to handle repeated instantiation gracefully
4. **New tests added**: `test_depth_distribution_calculated`, `test_technique_distribution_calculated`, `test_shared_paths_is_novel_reset`, `test_multiple_metrics_instances_no_reregistration_error`, `test_hard_gate_result_exact_threshold`

### File List

**Created:**
- `src/cyberred/orchestration/emergence/metrics.py`
- `tests/unit/orchestration/emergence/test_metrics.py`
- `tests/unit/orchestration/emergence/test_emergence_score_models.py`

**Modified:**
- `src/cyberred/orchestration/emergence/__init__.py` - Added exports for EmergenceMetrics, EmergenceScore, HardGateResult, NFR35_EMERGENCE_THRESHOLD
- `src/cyberred/orchestration/emergence/comparison.py` - Integrated EmergenceMetrics, updated to use new field names
- `tests/emergence/test_emergence_score.py` - Uses EmergenceComparisonFramework with EmergenceMetrics
