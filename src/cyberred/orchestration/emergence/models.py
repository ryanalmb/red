from dataclasses import dataclass, field
from typing import Any, Literal
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
    
    def __post_init__(self) -> None:
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
    findings: list[dict[str, Any]]  # Serialized Finding objects
    attack_paths: list[AttackPath]
    actions: list[dict[str, Any]]  # Serialized AgentAction objects
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
