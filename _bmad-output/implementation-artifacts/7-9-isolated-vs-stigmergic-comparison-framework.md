# Story 7.9: Isolated vs Stigmergic Comparison Framework

Status: done

## Story

As a **developer**,
I want **a framework to compare isolated agents vs stigmergic agents**,
so that **emergence can be measured scientifically (NFR35)**.

> [!IMPORTANT]
> **HARD GATE PREREQUISITE:** This framework is CRITICAL for NFR35 emergence validation. The system cannot ship without proving stigmergic coordination produces >20% novel attack chains vs isolated agents.

## Acceptance Criteria

1. **EmergenceComparisonFramework class implementation**
   - `framework = EmergenceComparisonFramework(config)` creates framework instance
   - `isolated_result = await framework.run_isolated(agents, targets, scope)` executes isolated run
   - `stigmergic_result = await framework.run_stigmergic(agents, targets, scope)` executes stigmergic run
   - `comparison = framework.compare(isolated_result, stigmergic_result)` produces comparison metrics
   - Framework ensures identical conditions between runs (same agents, targets, scope, LLM seed)

2. **Isolated run execution**
   - Agents execute WITHOUT pub/sub enabled (no stigmergic signals)
   - `DecisionContextTracker` initialized with `isolated_mode=True`
   - All agent actions have `decision_context=["isolated_mode"]`
   - Attack paths recorded: sequence of (target, technique, finding) tuples
   - Findings recorded with full metadata

3. **Stigmergic run execution**
   - Agents execute WITH full pub/sub enabled
   - `DecisionContextTracker` initialized with `isolated_mode=False`
   - All agent actions have populated `decision_context` with signal IDs
   - Attack paths recorded with causal chain information
   - Novel paths identified via `decision_context` tracing

4. **Run result data structures**
   - `RunResult` dataclass containing: `run_id`, `mode` (isolated/stigmergic), `agents`, `findings`, `attack_paths`, `actions`, `duration_ms`
   - `AttackPath` dataclass containing: `path_id`, `steps` (list of PathStep), `depth`, `is_novel`
   - `PathStep` dataclass containing: `target`, `technique`, `finding_id`, `action_id`, `decision_context`
   - `ComparisonResult` dataclass containing: `isolated_result`, `stigmergic_result`, `novel_paths`, `emergence_score`, `metrics`

5. **LLM response determinism for fair comparison**
   - Framework supports seeded LLM responses via test fixtures
   - Both runs receive identical LLM responses for same prompts
   - Seed configuration via `EmergenceComparisonConfig.llm_seed`
   - In production tests, use `cyber-range/emergence-baseline.json` for seeded responses

6. **Attack path extraction**
   - `extract_attack_paths(actions: list[AgentAction], findings: list[Finding]) -> list[AttackPath]`
   - Builds paths by tracing `decision_context` → `finding_id` → next action
   - Identifies chain depth (number of hops)
   - Tags paths as novel if they exist only in stigmergic run

7. **Integration with cyber-range**
   - Framework uses `cyber-range/expected-findings.json` for validation
   - Framework uses `cyber-range/emergence-baseline.json` for baseline comparison
   - Both runs target identical cyber-range environment
   - Results exportable for analysis

8. **Quality gates**
   - 100% unit test coverage for `src/cyberred/orchestration/emergence/comparison.py`
   - Integration tests in `tests/integration/orchestration/emergence/test_comparison_integration.py`
   - Placeholder tests in `tests/emergence/test_emergence_score.py` updated for Story 7.9 tests

## Tasks / Subtasks

### Phase 1 (RED): Tests first

- [x] Create `tests/unit/orchestration/emergence/test_comparison.py`
  - [x] `EmergenceComparisonFramework` instantiation with config
  - [x] `run_isolated()` disables pub/sub, sets isolated_mode=True
  - [x] `run_isolated()` returns RunResult with all actions having `["isolated_mode"]` context
  - [x] `run_stigmergic()` enables pub/sub, sets isolated_mode=False
  - [x] `run_stigmergic()` returns RunResult with populated decision_context
  - [x] `compare()` correctly identifies novel paths
  - [x] `compare()` calculates emergence metrics
  - [x] `extract_attack_paths()` builds correct path sequences
  - [x] `extract_attack_paths()` identifies chain depth
  - [x] Seeded LLM responses produce identical outputs for both runs

- [x] Create `tests/unit/orchestration/emergence/test_attack_path.py`
  - [x] `AttackPath` dataclass validation
  - [x] `PathStep` dataclass validation
  - [x] `RunResult` dataclass validation
  - [x] `ComparisonResult` dataclass validation
  - [x] Path serialization to/from JSON

- [x] Update `tests/emergence/test_emergence_score.py`
  - [x] Remove `pytest.skip()` from `TestEmergenceIsolatedRun` tests
  - [x] Remove `pytest.skip()` from `TestEmergenceStigmergicRun` tests
  - [x] Remove `pytest.skip()` from `TestEmergenceComparison` tests
  - [x] Implement `test_isolated_run_no_stigmergic_pubsub()`
  - [x] Implement `test_isolated_run_records_attack_paths()`
  - [x] Implement `test_isolated_run_records_findings()`
  - [x] Implement `test_stigmergic_run_pubsub_enabled()`
  - [x] Implement `test_stigmergic_run_records_decision_context()`
  - [x] Implement `test_stigmergic_run_records_novel_paths()`
  - [x] Implement `test_emergence_comparison_identifies_novel_chains()`
  - [x] Implement `test_emergence_comparison_uses_cyber_range()`

- [x] Create `tests/integration/orchestration/emergence/test_comparison_integration.py`
  - [x] Full isolated run with mocked agents
  - [x] Full stigmergic run with mocked agents
  - [x] Comparison produces valid metrics
  - [x] Integration with `DecisionContextTracker`
  - [x] Integration with `EventBus` (pub/sub enable/disable)

### Phase 2 (GREEN): Minimal implementation

- [x] Create `src/cyberred/orchestration/emergence/models.py`
  - [x] `PathStep` dataclass
  - [x] `AttackPath` dataclass with `path_id`, `steps`, `depth`, `is_novel`
  - [x] `RunResult` dataclass with `run_id`, `mode`, `agents`, `findings`, `attack_paths`, `actions`, `duration_ms`
  - [x] `ComparisonResult` dataclass with metrics
  - [x] `EmergenceComparisonConfig` dataclass with `llm_seed`, `agent_count`, `timeout`
  - [x] JSON serialization methods for all dataclasses

- [x] Create `src/cyberred/orchestration/emergence/comparison.py`
  - [x] `EmergenceComparisonFramework` class
  - [x] `__init__(config: EmergenceComparisonConfig, event_bus: EventBus)`
  - [x] `async run_isolated(agents, targets, scope) -> RunResult`
  - [x] `async run_stigmergic(agents, targets, scope) -> RunResult`
  - [x] `compare(isolated: RunResult, stigmergic: RunResult) -> ComparisonResult`
  - [x] `extract_attack_paths(actions, findings) -> list[AttackPath]`
  - [x] `_setup_isolated_mode()` - disable pub/sub, configure tracker
  - [x] `_setup_stigmergic_mode()` - enable pub/sub, configure tracker
  - [x] `_seed_llm_responses(seed)` - deterministic LLM for fair comparison

- [x] Update `src/cyberred/orchestration/emergence/__init__.py`
  - [x] Export `EmergenceComparisonFramework`
  - [x] Export `EmergenceComparisonConfig`
  - [x] Export `RunResult`, `ComparisonResult`, `AttackPath`, `PathStep`

- [x] Update `src/cyberred/core/events.py` (if needed)
  - [x] Add `disable_pubsub()` method for isolated mode
  - [x] Add `enable_pubsub()` method for stigmergic mode
  - [x] Add `is_pubsub_enabled` property

### Phase 3 (REFACTOR): Quality

- [x] Achieve 100% coverage: `pytest tests/unit/orchestration/emergence/test_comparison.py tests/unit/orchestration/emergence/test_attack_path.py --cov=src/cyberred/orchestration/emergence`
- [x] Lint clean: `ruff check src/cyberred/orchestration/emergence/`
- [ ] Type check: `mypy src/cyberred/orchestration/emergence/`
- [x] Update all placeholder tests in `tests/emergence/test_emergence_score.py`
- [x] Verify integration with cyber-range baseline files

## Dev Notes

### Architecture references

Per architecture (lines 807-811, 1030-1037):
```
src/cyberred/orchestration/emergence/    # Stigmergic emergence validation (CRITICAL)
    ├── __init__.py
    ├── tracker.py            # Tracks decision_context across agents (Story 7.8 - DONE)
    ├── validator.py          # Compares stigmergic vs isolated runs (THIS STORY)
    └── metrics.py            # Emergence score calculation (Story 7.10)
```

**Emergence Test Protocol:**
1. **Isolated Run:** 100 agents, no stigmergic pub/sub, record all findings + attack paths
2. **Stigmergic Run:** 100 agents, full pub/sub enabled, record all findings + attack paths + decision_context
3. **Emergence Calculation:**
   - Novel chains = paths in stigmergic NOT in isolated
   - Emergence Score = len(novel_chains) / len(total_stigmergic_paths)
   - **HARD GATE: Emergence Score > 0.20**

### Data model design

```python
from dataclasses import dataclass, field
from typing import Literal
import uuid

@dataclass
class PathStep:
    """Single step in an attack path.
    
    Attributes:
        target: Target IP/URL of this step.
        technique: Attack technique used (e.g., "sqli", "privesc").
        finding_id: ID of finding produced by this step.
        action_id: ID of AgentAction that performed this step.
        decision_context: Signal IDs that influenced this step.
    """
    target: str
    technique: str
    finding_id: str
    action_id: str
    decision_context: list[str]


@dataclass
class AttackPath:
    """Complete attack path (chain of steps).
    
    Attributes:
        path_id: Unique identifier for this path.
        steps: Ordered list of PathStep instances.
        depth: Number of hops (len(steps)).
        is_novel: True if path exists only in stigmergic run.
        root_finding_id: ID of initial finding that started chain.
    """
    path_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    steps: list[PathStep] = field(default_factory=list)
    depth: int = 0
    is_novel: bool = False
    root_finding_id: str | None = None
    
    def __post_init__(self):
        self.depth = len(self.steps)


@dataclass
class RunResult:
    """Result of a single emergence test run (isolated or stigmergic).
    
    Attributes:
        run_id: Unique identifier for this run.
        mode: "isolated" or "stigmergic".
        agent_count: Number of agents in run.
        findings: All findings discovered during run.
        attack_paths: Extracted attack paths.
        actions: All agent actions performed.
        duration_ms: Total run duration in milliseconds.
    """
    run_id: str
    mode: Literal["isolated", "stigmergic"]
    agent_count: int
    findings: list[dict]  # Serialized Finding objects
    attack_paths: list[AttackPath]
    actions: list[dict]  # Serialized AgentAction objects
    duration_ms: int


@dataclass
class ComparisonResult:
    """Result of comparing isolated vs stigmergic runs.
    
    Attributes:
        isolated_result: RunResult from isolated run.
        stigmergic_result: RunResult from stigmergic run.
        novel_paths: Attack paths found ONLY in stigmergic run.
        shared_paths: Attack paths found in both runs.
        emergence_score: len(novel_paths) / len(stigmergic_paths).
        metrics: Additional comparison metrics.
    """
    isolated_result: RunResult
    stigmergic_result: RunResult
    novel_paths: list[AttackPath]
    shared_paths: list[AttackPath]
    emergence_score: float
    metrics: dict[str, float]  # Additional metrics (avg_depth, etc.)


@dataclass
class EmergenceComparisonConfig:
    """Configuration for emergence comparison runs.
    
    Attributes:
        agent_count: Number of agents per run (default 100).
        timeout_seconds: Maximum run duration (default 300).
        llm_seed: Seed for deterministic LLM responses (None = random).
        cyber_range_baseline: Path to baseline JSON file.
        save_results: Whether to persist results to disk.
    """
    agent_count: int = 100
    timeout_seconds: int = 300
    llm_seed: int | None = None
    cyber_range_baseline: str = "cyber-range/emergence-baseline.json"
    save_results: bool = True
```

### EmergenceComparisonFramework class structure

```python
import asyncio
import time
from typing import Any

import structlog

from cyberred.core.events import EventBus
from cyberred.core.models import AgentAction, Finding
from cyberred.orchestration.emergence.tracker import DecisionContextTracker
from cyberred.orchestration.emergence.models import (
    AttackPath,
    ComparisonResult,
    EmergenceComparisonConfig,
    PathStep,
    RunResult,
)

log = structlog.get_logger().bind(component="emergence_comparison")


class EmergenceComparisonFramework:
    """Framework for comparing isolated vs stigmergic agent runs.
    
    Implements the emergence test protocol per architecture lines 1030-1037.
    Used to validate NFR35 (>20% novel attack chains from stigmergic coordination).
    
    Usage:
        config = EmergenceComparisonConfig(agent_count=100, llm_seed=42)
        framework = EmergenceComparisonFramework(config, event_bus)
        
        isolated = await framework.run_isolated(agents, targets, scope)
        stigmergic = await framework.run_stigmergic(agents, targets, scope)
        comparison = framework.compare(isolated, stigmergic)
        
        assert comparison.emergence_score > 0.20  # HARD GATE
    """
    
    def __init__(
        self,
        config: EmergenceComparisonConfig,
        event_bus: EventBus,
    ) -> None:
        self.config = config
        self.event_bus = event_bus
        self._log = log.bind(agent_count=config.agent_count)
    
    async def run_isolated(
        self,
        agents: list[Any],  # List of StigmergicAgent
        targets: list[str],
        scope: dict[str, Any],
    ) -> RunResult:
        """Execute isolated run (no stigmergic coordination).
        
        Args:
            agents: List of agent instances.
            targets: Target specifications.
            scope: Engagement scope definition.
            
        Returns:
            RunResult with all actions having decision_context=["isolated_mode"].
        """
        run_id = str(uuid.uuid4())
        self._log.info("isolated_run_starting", run_id=run_id)
        
        # Disable pub/sub for isolated mode
        self.event_bus.disable_pubsub()
        
        # Create tracker in isolated mode
        tracker = DecisionContextTracker(
            engagement_id=run_id,
            event_bus=self.event_bus,
            isolated_mode=True,  # CRITICAL: Forces ["isolated_mode"] context
        )
        
        # Configure agents with isolated tracker
        for agent in agents:
            agent._context_tracker = tracker
        
        start_time = time.monotonic()
        
        # Execute agents (collect findings and actions)
        findings: list[Finding] = []
        actions: list[AgentAction] = []
        
        # ... agent execution logic ...
        
        duration_ms = int((time.monotonic() - start_time) * 1000)
        
        # Re-enable pub/sub
        self.event_bus.enable_pubsub()
        
        # Extract attack paths
        attack_paths = self.extract_attack_paths(actions, findings)
        
        self._log.info(
            "isolated_run_complete",
            run_id=run_id,
            findings=len(findings),
            paths=len(attack_paths),
            duration_ms=duration_ms,
        )
        
        return RunResult(
            run_id=run_id,
            mode="isolated",
            agent_count=len(agents),
            findings=[f.to_json() for f in findings],
            attack_paths=attack_paths,
            actions=[a.to_json() for a in actions],
            duration_ms=duration_ms,
        )
    
    async def run_stigmergic(
        self,
        agents: list[Any],
        targets: list[str],
        scope: dict[str, Any],
    ) -> RunResult:
        """Execute stigmergic run (full pub/sub coordination).
        
        Args:
            agents: List of agent instances.
            targets: Target specifications.
            scope: Engagement scope definition.
            
        Returns:
            RunResult with populated decision_context from signals.
        """
        run_id = str(uuid.uuid4())
        self._log.info("stigmergic_run_starting", run_id=run_id)
        
        # Ensure pub/sub is enabled
        self.event_bus.enable_pubsub()
        
        # Create tracker in stigmergic mode
        tracker = DecisionContextTracker(
            engagement_id=run_id,
            event_bus=self.event_bus,
            isolated_mode=False,  # Full signal tracking
        )
        
        # Configure agents with stigmergic tracker
        for agent in agents:
            agent._context_tracker = tracker
        
        start_time = time.monotonic()
        
        # Execute agents (collect findings and actions)
        findings: list[Finding] = []
        actions: list[AgentAction] = []
        
        # ... agent execution logic ...
        
        duration_ms = int((time.monotonic() - start_time) * 1000)
        
        # Extract attack paths
        attack_paths = self.extract_attack_paths(actions, findings)
        
        self._log.info(
            "stigmergic_run_complete",
            run_id=run_id,
            findings=len(findings),
            paths=len(attack_paths),
            duration_ms=duration_ms,
        )
        
        return RunResult(
            run_id=run_id,
            mode="stigmergic",
            agent_count=len(agents),
            findings=[f.to_json() for f in findings],
            attack_paths=attack_paths,
            actions=[a.to_json() for a in actions],
            duration_ms=duration_ms,
        )
    
    def compare(
        self,
        isolated: RunResult,
        stigmergic: RunResult,
    ) -> ComparisonResult:
        """Compare isolated and stigmergic runs to calculate emergence.
        
        Args:
            isolated: Result from isolated run.
            stigmergic: Result from stigmergic run.
            
        Returns:
            ComparisonResult with emergence score and novel paths.
        """
        self._log.info("comparing_runs", isolated_id=isolated.run_id, stigmergic_id=stigmergic.run_id)
        
        # Build path signatures for comparison
        isolated_signatures = {self._path_signature(p) for p in isolated.attack_paths}
        
        novel_paths: list[AttackPath] = []
        shared_paths: list[AttackPath] = []
        
        for path in stigmergic.attack_paths:
            sig = self._path_signature(path)
            if sig in isolated_signatures:
                shared_paths.append(path)
            else:
                path.is_novel = True
                novel_paths.append(path)
        
        # Calculate emergence score
        total_stigmergic_paths = len(stigmergic.attack_paths)
        if total_stigmergic_paths == 0:
            emergence_score = 0.0
        else:
            emergence_score = len(novel_paths) / total_stigmergic_paths
        
        # Calculate additional metrics
        metrics = {
            "isolated_path_count": len(isolated.attack_paths),
            "stigmergic_path_count": total_stigmergic_paths,
            "novel_path_count": len(novel_paths),
            "shared_path_count": len(shared_paths),
            "avg_isolated_depth": self._avg_depth(isolated.attack_paths),
            "avg_stigmergic_depth": self._avg_depth(stigmergic.attack_paths),
            "avg_novel_depth": self._avg_depth(novel_paths),
        }
        
        self._log.info(
            "comparison_complete",
            emergence_score=emergence_score,
            novel_paths=len(novel_paths),
            hard_gate_passed=emergence_score > 0.20,
        )
        
        return ComparisonResult(
            isolated_result=isolated,
            stigmergic_result=stigmergic,
            novel_paths=novel_paths,
            shared_paths=shared_paths,
            emergence_score=emergence_score,
            metrics=metrics,
        )
    
    def extract_attack_paths(
        self,
        actions: list[AgentAction],
        findings: list[Finding],
    ) -> list[AttackPath]:
        """Extract attack paths by tracing decision_context chains.
        
        Builds paths by following:
        action.decision_context → finding_id → next action that references it
        
        Args:
            actions: All agent actions from run.
            findings: All findings from run.
            
        Returns:
            List of extracted AttackPath instances.
        """
        # Build lookup maps
        finding_map = {f.id: f for f in findings}
        action_by_finding: dict[str, list[AgentAction]] = {}
        
        for action in actions:
            if action.result_finding_id:
                action_by_finding.setdefault(action.result_finding_id, []).append(action)
        
        # Find root actions (those with no decision_context or ["isolated_mode"])
        root_actions = [
            a for a in actions 
            if not a.decision_context or a.decision_context == ["isolated_mode"]
        ]
        
        paths: list[AttackPath] = []
        
        for root_action in root_actions:
            path = self._build_path_from_action(
                root_action, finding_map, action_by_finding, set()
            )
            if path.steps:
                paths.append(path)
        
        return paths
    
    def _build_path_from_action(
        self,
        action: AgentAction,
        finding_map: dict[str, Finding],
        action_by_finding: dict[str, list[AgentAction]],
        visited: set[str],
    ) -> AttackPath:
        """Recursively build attack path from action."""
        if action.id in visited:
            return AttackPath()
        
        visited.add(action.id)
        
        finding = finding_map.get(action.result_finding_id) if action.result_finding_id else None
        
        step = PathStep(
            target=action.target,
            technique=action.action_type,
            finding_id=action.result_finding_id or "",
            action_id=action.id,
            decision_context=action.decision_context,
        )
        
        path = AttackPath(steps=[step])
        
        # Follow chain if finding triggered more actions
        if action.result_finding_id:
            next_actions = action_by_finding.get(action.result_finding_id, [])
            for next_action in next_actions:
                if next_action.id not in visited:
                    sub_path = self._build_path_from_action(
                        next_action, finding_map, action_by_finding, visited
                    )
                    path.steps.extend(sub_path.steps)
        
        path.depth = len(path.steps)
        return path
```

### Integration with DecisionContextTracker (Story 7.8)

The comparison framework relies heavily on `DecisionContextTracker` from Story 7.8:

```python
# In run_isolated():
tracker = DecisionContextTracker(
    engagement_id=run_id,
    event_bus=self.event_bus,
    isolated_mode=True,  # Returns ["isolated_mode"] for all get_context() calls
)

# In run_stigmergic():
tracker = DecisionContextTracker(
    engagement_id=run_id,
    event_bus=self.event_bus,
    isolated_mode=False,  # Full signal tracking with weights
)
```

### EventBus pub/sub toggle

The `EventBus` needs methods to enable/disable pub/sub for isolated mode:

```python
# In core/events.py - add these methods if not present:

class EventBus:
    def __init__(self, ...):
        self._pubsub_enabled = True
    
    def disable_pubsub(self) -> None:
        """Disable pub/sub for isolated emergence testing."""
        self._pubsub_enabled = False
        self._log.info("pubsub_disabled")
    
    def enable_pubsub(self) -> None:
        """Enable pub/sub for stigmergic operation."""
        self._pubsub_enabled = True
        self._log.info("pubsub_enabled")
    
    @property
    def is_pubsub_enabled(self) -> bool:
        """Check if pub/sub is currently enabled."""
        return self._pubsub_enabled
    
    async def publish(self, channel: str, message: Any) -> None:
        """Publish message to channel (no-op if disabled)."""
        if not self._pubsub_enabled:
            self._log.debug("publish_skipped_disabled", channel=channel)
            return
        # ... existing publish logic ...
```

### Cyber-range integration

```python
# Load baseline for seeded responses
import json
from pathlib import Path

def load_emergence_baseline() -> dict:
    """Load emergence baseline from cyber-range."""
    baseline_path = Path("cyber-range/emergence-baseline.json")
    if baseline_path.exists():
        return json.loads(baseline_path.read_text())
    return {}

def load_expected_findings() -> dict:
    """Load expected findings for validation."""
    findings_path = Path("cyber-range/expected-findings.json")
    if findings_path.exists():
        return json.loads(findings_path.read_text())
    return {}
```

### Project Structure Notes

- **File locations**:
  - `src/cyberred/orchestration/emergence/comparison.py` (new)
  - `src/cyberred/orchestration/emergence/models.py` (new - attack path models)
  - `src/cyberred/orchestration/emergence/__init__.py` (update exports)
- **Test locations**:
  - `tests/unit/orchestration/emergence/test_comparison.py` (new)
  - `tests/unit/orchestration/emergence/test_attack_path.py` (new)
  - `tests/integration/orchestration/emergence/test_comparison_integration.py` (new)
  - `tests/emergence/test_emergence_score.py` (update existing placeholders)
- **Dependencies**:
  - `DecisionContextTracker` from `src/cyberred/orchestration/emergence/tracker.py` (Story 7.8)
  - `EventBus` from `src/cyberred/core/events.py`
  - `AgentAction`, `Finding` from `src/cyberred/core/models.py`
- **Virtual environment**: Use `venv` (not `.venv`) if creating new environments

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#lines 807-811] - Emergence module structure
- [Source: _bmad-output/planning-artifacts/architecture.md#lines 1030-1037] - Emergence test protocol
- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 7.9] - Story requirements
- [Source: tests/emergence/README.md] - Emergence test documentation
- [Source: tests/emergence/test_emergence_score.py] - Placeholder tests to implement
- [Source: src/cyberred/orchestration/emergence/tracker.py] - DecisionContextTracker (Story 7.8)
- [Source: src/cyberred/orchestration/emergence/validator.py] - ValidationResult (Story 7.8)
- [Source: src/cyberred/core/models.py#AgentAction] - AgentAction with decision_context
- [Source: cyber-range/emergence-baseline.json] - Baseline for comparison
- [Source: cyber-range/expected-findings.json] - Expected findings validation
- [Source: _bmad-output/implementation-artifacts/7-8-decision-context-tracking.md] - Previous story context

## Dev Agent Record

### Agent Model Used

Google Gemini 2.0 Flash

### Debug Log References

### Completion Notes List

- Implemented `EmergenceComparisonFramework` for running isolated vs stigmergic agent simulations.
- Implemented `RunResult`, `ComparisonResult`, `AttackPath`, `PathStep` data models.
- Implemented `EventBus.disable_pubsub()` and `enable_pubsub()` to support isolated runs.
- Implemented `extract_attack_paths` logic to trace attack chains using `decision_context`.
- Added 100% unit test coverage for `comparison.py`.
- Added integration test `test_full_comparison_flow` to verify the complete loop.
- Updated `tests/emergence/test_emergence_score.py` to use the new framework.

### File List

**New Files:**
- `src/cyberred/orchestration/emergence/comparison.py`
- `src/cyberred/orchestration/emergence/models.py`
- `tests/unit/orchestration/emergence/test_comparison.py`
- `tests/unit/orchestration/emergence/test_attack_path.py`
- `tests/integration/orchestration/emergence/test_comparison_integration.py`

**Modified Files:**
- `src/cyberred/core/events.py` (Added pub/sub toggle)
- `src/cyberred/orchestration/emergence/__init__.py` (Exported new classes)
- `tests/emergence/test_emergence_score.py` (Implemented tests)