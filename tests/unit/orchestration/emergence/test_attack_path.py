import json
import uuid
import pytest
from cyberred.orchestration.emergence.models import (
    AttackPath,
    ComparisonResult,
    PathStep,
    RunResult,
)

class TestAttackPathModels:
    def test_path_step_creation(self):
        """Test PathStep dataclass creation."""
        step = PathStep(
            target="192.168.1.10",
            technique="sqli",
            finding_id="finding-123",
            action_id="action-456",
            decision_context=["signal-789"]
        )
        assert step.target == "192.168.1.10"
        assert step.technique == "sqli"
        assert step.decision_context == ["signal-789"]

    def test_attack_path_defaults(self):
        """Test AttackPath default values."""
        path = AttackPath()
        assert path.path_id is not None
        assert isinstance(path.steps, list)
        assert len(path.steps) == 0
        assert path.depth == 0
        assert path.is_novel is False

    def test_attack_path_depth_calculation(self):
        """Test AttackPath depth calculation."""
        step1 = PathStep("t1", "tech1", "f1", "a1", [])
        step2 = PathStep("t2", "tech2", "f2", "a2", [])
        
        path = AttackPath(steps=[step1, step2])
        # __post_init__ should calculate depth
        assert path.depth == 2

    def test_run_result_creation(self):
        """Test RunResult dataclass."""
        result = RunResult(
            run_id="run-1",
            mode="isolated",
            agent_count=10,
            findings=[],
            attack_paths=[],
            actions=[],
            duration_ms=1000
        )
        assert result.mode == "isolated"
        assert result.agent_count == 10

    def test_comparison_result_creation(self):
        """Test ComparisonResult dataclass."""
        run_res = RunResult(
            run_id="run-1",
            mode="isolated",
            agent_count=10,
            findings=[],
            attack_paths=[],
            actions=[],
            duration_ms=1000
        )
        
        comp = ComparisonResult(
            isolated_result=run_res,
            stigmergic_result=run_res,
            novel_paths=[],
            shared_paths=[],
            emergence_score=0.5,
            metrics={"avg_depth": 2.0}
        )
        assert comp.emergence_score == 0.5
        assert comp.metrics["avg_depth"] == 2.0
