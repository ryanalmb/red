import pytest
from datetime import datetime
from cyberred.orchestration.emergence.metrics import EmergenceScore, HardGateResult
from cyberred.orchestration.emergence.models import AttackPath

def test_emergence_score_creation():
    score = EmergenceScore(
        novel_path_count=1,
        shared_path_count=2,
        total_stigmergic_paths=3,
        total_isolated_paths=2,
        score=0.33,
        novel_paths=[]
    )
    
    assert score.score == 0.33
    assert isinstance(score.calculation_timestamp, datetime)
    # AC7: Check new field defaults
    assert score.avg_novel_depth == 0.0
    assert score.max_novel_depth == 0
    assert score.min_novel_depth == 0
    assert score.depth_distribution == {}
    assert score.technique_distribution == {}
    
    d = score.to_dict()
    assert d["score"] == 0.33
    assert d["score_percentage"] == "33.0%"
    assert "calculation_timestamp" in d
    # AC7: Check new fields in to_dict()
    assert "avg_novel_depth" in d
    assert "max_novel_depth" in d
    assert "min_novel_depth" in d
    assert "depth_distribution" in d
    assert "technique_distribution" in d


def test_emergence_score_with_depth_distribution():
    """Test EmergenceScore with AC7 detailed metrics."""
    score = EmergenceScore(
        novel_path_count=5,
        shared_path_count=3,
        total_stigmergic_paths=8,
        total_isolated_paths=3,
        score=0.625,
        novel_paths=[],
        avg_novel_depth=2.4,
        max_novel_depth=4,
        min_novel_depth=1,
        depth_distribution={1: 1, 2: 2, 3: 1, 4: 1},
        technique_distribution={"scan": 3, "exploit": 2},
    )
    
    assert score.avg_novel_depth == 2.4
    assert score.max_novel_depth == 4
    assert score.min_novel_depth == 1
    assert score.depth_distribution == {1: 1, 2: 2, 3: 1, 4: 1}
    assert score.technique_distribution == {"scan": 3, "exploit": 2}
    
    d = score.to_dict()
    assert d["avg_novel_depth"] == 2.4
    assert d["depth_distribution"] == {1: 1, 2: 2, 3: 1, 4: 1}


def test_hard_gate_result_creation():
    result = HardGateResult.from_score(0.25)
    assert result.passed
    assert result.margin == pytest.approx(0.05)
    
    result_fail = HardGateResult.from_score(0.10)
    assert not result_fail.passed
    assert result_fail.margin == pytest.approx(-0.10)


def test_hard_gate_result_exact_threshold():
    """Test edge case: score exactly at threshold fails (must EXCEED)."""
    result = HardGateResult.from_score(0.20)
    assert not result.passed  # Must be > 0.20, not >=
    assert result.margin == pytest.approx(0.0)
