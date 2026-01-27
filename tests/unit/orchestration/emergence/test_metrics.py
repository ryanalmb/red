import pytest
from unittest.mock import Mock, patch
from datetime import datetime

# Import assuming existence (Red phase)
from cyberred.orchestration.emergence.metrics import EmergenceMetrics, EmergenceScore, HardGateResult
from cyberred.orchestration.emergence.models import RunResult, AttackPath, PathStep

@pytest.fixture
def metrics():
    return EmergenceMetrics()

def create_mock_path(target, technique, is_novel=False):
    step = PathStep(target=target, technique=technique, finding_id="f1", action_id="a1", decision_context=[])
    path = AttackPath(steps=[step], is_novel=is_novel)
    return path

def test_calculate_emergence_score_basic(metrics):
    # Isolated: A
    # Stigmergic: A, B (B is novel)
    
    path_a_iso = create_mock_path("1.1.1.1", "scan")
    path_a_stig = create_mock_path("1.1.1.1", "scan")
    path_b_stig = create_mock_path("2.2.2.2", "exploit")
    
    isolated = RunResult(
        run_id="iso1", mode="isolated", agent_count=1, findings=[], 
        attack_paths=[path_a_iso], actions=[], duration_ms=1000
    )
    stigmergic = RunResult(
        run_id="stig1", mode="stigmergic", agent_count=1, findings=[], 
        attack_paths=[path_a_stig, path_b_stig], actions=[], duration_ms=1000
    )
    
    score = metrics.calculate_emergence_score(isolated, stigmergic)
    
    assert score.novel_path_count == 1
    assert score.shared_path_count == 1
    assert score.total_stigmergic_paths == 2
    assert score.total_isolated_paths == 1
    assert score.score == 0.5
    assert len(score.novel_paths) == 1
    assert score.novel_paths[0].steps[0].target == "2.2.2.2"

def test_calculate_emergence_score_empty_stigmergic(metrics):
    isolated = RunResult(
        run_id="iso1", mode="isolated", agent_count=1, findings=[], 
        attack_paths=[create_mock_path("1.1.1.1", "scan")], actions=[], duration_ms=1000
    )
    stigmergic = RunResult(
        run_id="stig1", mode="stigmergic", agent_count=1, findings=[], 
        attack_paths=[], actions=[], duration_ms=1000
    )
    
    score = metrics.calculate_emergence_score(isolated, stigmergic)
    assert score.score == 0.0
    assert score.total_stigmergic_paths == 0

def test_calculate_emergence_score_all_novel(metrics):
    isolated = RunResult(
        run_id="iso1", mode="isolated", agent_count=1, findings=[], 
        attack_paths=[], actions=[], duration_ms=1000
    )
    stigmergic = RunResult(
        run_id="stig1", mode="stigmergic", agent_count=1, findings=[], 
        attack_paths=[create_mock_path("2.2.2.2", "exploit")], actions=[], duration_ms=1000
    )
    
    score = metrics.calculate_emergence_score(isolated, stigmergic)
    assert score.score == 1.0
    assert score.novel_path_count == 1

def test_validate_hard_gate_pass(metrics):
    # Mock a score object
    score_obj = Mock(spec=EmergenceScore)
    score_obj.score = 0.25 # > 0.20
    
    result = metrics.validate_hard_gate(score_obj)
    
    assert result.passed is True
    assert result.score == 0.25
    assert result.threshold == 0.20
    assert result.margin == pytest.approx(0.05)
    assert "PASSED" in result.message

def test_validate_hard_gate_fail(metrics):
    score_obj = Mock(spec=EmergenceScore)
    score_obj.score = 0.15 # < 0.20
    
    result = metrics.validate_hard_gate(score_obj)
    
    assert result.passed is False
    assert result.score == 0.15
    assert result.margin == pytest.approx(-0.05)
    assert "FAILED" in result.message

def test_prometheus_export(metrics):
    # Mock the gauges if they exist, or patch them
    # Since metrics are initialized in __init__, we might need to patch prometheus_client there
    # But for unit test of export method, we can mock the gauges on the instance
    
    metrics._prometheus_available = True
    metrics._emergence_score_gauge = Mock()
    metrics._novel_paths_gauge = Mock()
    metrics._total_paths_gauge = Mock()
    metrics._hard_gate_gauge = Mock()
    
    score_obj = Mock(spec=EmergenceScore)
    score_obj.score = 0.5
    score_obj.novel_path_count = 5
    score_obj.total_stigmergic_paths = 10
    
    metrics.export_prometheus_metrics(score_obj, "eng1", "run1")
    
    metrics._emergence_score_gauge.labels.assert_called_with(engagement_id="eng1", run_id="run1")
    metrics._emergence_score_gauge.labels.return_value.set.assert_called_with(0.5)
    
    metrics._hard_gate_gauge.labels.return_value.set.assert_called_with(1) # Passed because 0.5 > 0.2


def test_prometheus_export_skipped_when_unavailable(metrics):
    """Test that Prometheus export is skipped gracefully when unavailable."""
    metrics._prometheus_available = False
    
    score_obj = Mock(spec=EmergenceScore)
    score_obj.score = 0.5
    
    # Should not raise
    metrics.export_prometheus_metrics(score_obj, "eng1", "run1")


def test_depth_distribution_calculated(metrics):
    """Test AC7: depth_distribution is calculated correctly."""
    # Create paths with different depths
    path1 = create_mock_path("1.1.1.1", "scan")
    path1.depth = 1
    path2 = create_mock_path("2.2.2.2", "exploit")
    path2.depth = 2
    path3 = create_mock_path("3.3.3.3", "privesc")
    path3.depth = 2
    path4 = create_mock_path("4.4.4.4", "lateral")
    path4.depth = 3
    
    isolated = RunResult(
        run_id="iso1", mode="isolated", agent_count=1, findings=[], 
        attack_paths=[], actions=[], duration_ms=1000
    )
    stigmergic = RunResult(
        run_id="stig1", mode="stigmergic", agent_count=1, findings=[], 
        attack_paths=[path1, path2, path3, path4], actions=[], duration_ms=1000
    )
    
    score = metrics.calculate_emergence_score(isolated, stigmergic)
    
    # All 4 paths are novel (isolated has none)
    assert score.novel_path_count == 4
    assert score.score == 1.0
    
    # AC7: Check depth distribution
    assert score.depth_distribution == {1: 1, 2: 2, 3: 1}
    assert score.avg_novel_depth == pytest.approx(2.0)  # (1+2+2+3)/4 = 2.0
    assert score.max_novel_depth == 3
    assert score.min_novel_depth == 1


def test_technique_distribution_calculated(metrics):
    """Test AC7: technique_distribution is calculated correctly."""
    path1 = create_mock_path("1.1.1.1", "scan")
    path2 = create_mock_path("2.2.2.2", "scan")
    path3 = create_mock_path("3.3.3.3", "exploit")
    
    isolated = RunResult(
        run_id="iso1", mode="isolated", agent_count=1, findings=[], 
        attack_paths=[], actions=[], duration_ms=1000
    )
    stigmergic = RunResult(
        run_id="stig1", mode="stigmergic", agent_count=1, findings=[], 
        attack_paths=[path1, path2, path3], actions=[], duration_ms=1000
    )
    
    score = metrics.calculate_emergence_score(isolated, stigmergic)
    
    # AC7: Check technique distribution
    assert score.technique_distribution == {"scan": 2, "exploit": 1}


def test_shared_paths_is_novel_reset(metrics):
    """Test that shared paths have is_novel explicitly set to False."""
    # Create same path signature for both isolated and stigmergic
    path_iso = create_mock_path("1.1.1.1", "scan")
    path_stig = create_mock_path("1.1.1.1", "scan")
    path_stig.is_novel = True  # Simulate stale state from previous calculation
    
    isolated = RunResult(
        run_id="iso1", mode="isolated", agent_count=1, findings=[], 
        attack_paths=[path_iso], actions=[], duration_ms=1000
    )
    stigmergic = RunResult(
        run_id="stig1", mode="stigmergic", agent_count=1, findings=[], 
        attack_paths=[path_stig], actions=[], duration_ms=1000
    )
    
    score = metrics.calculate_emergence_score(isolated, stigmergic)
    
    # The shared path should have is_novel = False now
    assert score.shared_path_count == 1
    assert score.novel_path_count == 0
    assert path_stig.is_novel is False  # Fixed: explicitly reset


def test_multiple_metrics_instances_no_reregistration_error():
    """Test that creating multiple EmergenceMetrics instances doesn't raise."""
    # This tests the fix for Prometheus gauge re-registration
    m1 = EmergenceMetrics()
    m2 = EmergenceMetrics()  # Should not raise
    m3 = EmergenceMetrics()  # Should not raise
    
    # All should be functional
    assert m1 is not m2
    assert m2 is not m3
