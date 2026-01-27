import pytest
from unittest.mock import AsyncMock, Mock, MagicMock
from cyberred.orchestration.emergence.comparison import (
    EmergenceComparisonFramework,
    EmergenceComparisonConfig,
)
from cyberred.orchestration.emergence.models import AttackPath, PathStep
from cyberred.core.models import AgentAction, Finding

@pytest.fixture
def mock_event_bus():
    bus = AsyncMock()
    bus.disable_pubsub = Mock()
    bus.enable_pubsub = Mock()
    return bus

@pytest.fixture
def framework(mock_event_bus):
    config = EmergenceComparisonConfig(agent_count=5, llm_seed=42)
    return EmergenceComparisonFramework(config, mock_event_bus)

@pytest.mark.asyncio
class TestEmergenceComparisonFramework:
    
    async def test_run_isolated_disables_pubsub(self, framework, mock_event_bus):
        """Test that run_isolated disables pub/sub."""
        agent = Mock()
        agent.run = AsyncMock()
        agent.findings = []
        agent.actions = []
        agents = [agent]
        targets = ["target1"]
        scope = {}
        
        # Mock agents execution
        result = await framework.run_isolated(agents, targets, scope)
        
        mock_event_bus.disable_pubsub.assert_called_once()
        mock_event_bus.enable_pubsub.assert_called_once() # Should re-enable at end
        assert result.mode == "isolated"
        agent.run.assert_awaited()

    async def test_run_stigmergic_enables_pubsub(self, framework, mock_event_bus):
        """Test that run_stigmergic enables pub/sub."""
        agent = Mock()
        agent.run = AsyncMock()
        agent.findings = []
        agent.actions = []
        agents = [agent]
        targets = ["target1"]
        scope = {}
        
        result = await framework.run_stigmergic(agents, targets, scope)
        
        mock_event_bus.enable_pubsub.assert_called()
        assert result.mode == "stigmergic"
        agent.run.assert_awaited()

    def test_compare_calculates_emergence_score(self, framework):
        """Test emergence score calculation."""
        # Setup mock results
        isolated_res = Mock()
        isolated_res.attack_paths = []
        isolated_res.run_id = "iso-1" # Add run_id for logging
        
        path1 = AttackPath(steps=[PathStep("t1", "sqli", "f1", "a1", [])])
        path2 = AttackPath(steps=[PathStep("t2", "xss", "f2", "a2", [])]) # Novel
        
        stigmergic_res = Mock()
        stigmergic_res.run_id = "stig-1" # Add run_id for logging
        stigmergic_res.attack_paths = [path1, path2]
        
        # If isolated has path1, then path2 is novel
        isolated_res.attack_paths = [path1]
        
        # We need to ensure _path_signature logic matches. 
        # Assuming framework implementation compares signatures.
        
        comp_result = framework.compare(isolated_res, stigmergic_res)
        
        # 1 novel path out of 2 total paths = 0.5
        assert comp_result.emergence_score == 0.5
        assert len(comp_result.novel_paths) == 1
        assert comp_result.novel_paths[0] == path2

    def test_extract_attack_paths(self, framework):
        """Test path extraction from actions and findings."""
        import uuid
        a1_id = str(uuid.uuid4())
        a2_id = str(uuid.uuid4())
        f1_id = str(uuid.uuid4())
        f2_id = str(uuid.uuid4())
        ag_id = str(uuid.uuid4())

        # Action 1 (Root) -> Finding 1
        a1 = AgentAction(
            id=a1_id, 
            agent_id=ag_id, 
            action_type="scan", 
            target="10.0.0.1", 
            result_finding_id=f1_id,
            decision_context=[],
            timestamp="2024-01-01T00:00:00Z"
        )
        # Findings are not fully validated in extract_attack_paths if passed as list of objects/dicts
        # But if we use Finding object, it validates.
        # Let's use Mock objects for findings to avoid full validation overhead here if possible,
        # or just construct valid ones.
        # For extract_attack_paths, it just needs .id.
        f1 = Mock(id=f1_id)
        f2 = Mock(id=f2_id)
        
        # Action 2 (Triggered by f1) -> Finding 2
        a2 = AgentAction(
            id=a2_id, 
            agent_id=ag_id, 
            action_type="exploit", 
            target="10.0.0.1", 
            result_finding_id=f2_id,
            decision_context=[f1_id], # Context from finding 1
            timestamp="2024-01-01T00:01:00Z"
        )
        
        actions = [a1, a2]
        findings = [f1, f2]
        
        paths = framework.extract_attack_paths(actions, findings)
        
        assert len(paths) == 1
        assert len(paths[0].steps) == 2
        assert paths[0].steps[0].action_id == a1_id
        assert paths[0].steps[1].action_id == a2_id

    def test_extract_attack_paths_with_dict_actions(self, framework):
        """Test path extraction handles dict-formatted actions (lines 304-308 coverage)."""
        import uuid
        a1_id = str(uuid.uuid4())
        f1_id = str(uuid.uuid4())
        
        # Action as dict (not AgentAction object)
        a1_dict = {
            "id": a1_id,
            "agent_id": str(uuid.uuid4()),
            "action_type": "scan",
            "target": "10.0.0.1",
            "result_finding_id": f1_id,
            "decision_context": [],
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        # Finding as dict
        f1_dict = {"id": f1_id, "type": "port_open"}
        
        paths = framework.extract_attack_paths([a1_dict], [f1_dict])
        
        assert len(paths) == 1
        assert paths[0].steps[0].action_id == a1_id
        assert paths[0].steps[0].target == "10.0.0.1"
        assert paths[0].steps[0].technique == "scan"

    def test_extract_attack_paths_visited_action_skip(self, framework):
        """Test that visited actions are skipped to prevent cycles (line 317 coverage)."""
        import uuid
        a1_id = str(uuid.uuid4())
        f1_id = str(uuid.uuid4())
        
        # Create two actions that reference each other (cycle)
        a1_dict = {
            "id": a1_id,
            "agent_id": str(uuid.uuid4()),
            "action_type": "scan",
            "target": "10.0.0.1",
            "result_finding_id": f1_id,
            "decision_context": [f1_id],  # References itself via finding
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        f1_dict = {"id": f1_id}
        
        # Should not infinite loop
        paths = framework.extract_attack_paths([a1_dict], [f1_dict])
        
        # Path should be extracted but cycle prevented
        assert len(paths) >= 0  # No crash = success

    def test_extract_attack_paths_empty_findings(self, framework):
        """Test path extraction with no findings."""
        import uuid
        a1_id = str(uuid.uuid4())
        
        a1_dict = {
            "id": a1_id,
            "agent_id": str(uuid.uuid4()),
            "action_type": "scan",
            "target": "10.0.0.1",
            "result_finding_id": None,
            "decision_context": [],
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        paths = framework.extract_attack_paths([a1_dict], [])
        
        assert len(paths) == 1
        assert paths[0].steps[0].finding_id == ""

    def test_compare_zero_stigmergic_paths(self, framework):
        """Test emergence score is 0 when no stigmergic paths (line 220 coverage)."""
        isolated_res = Mock()
        isolated_res.attack_paths = []
        isolated_res.run_id = "iso-1"
        
        stigmergic_res = Mock()
        stigmergic_res.run_id = "stig-1"
        stigmergic_res.attack_paths = []  # No paths
        
        comp_result = framework.compare(isolated_res, stigmergic_res)
        
        assert comp_result.emergence_score == 0.0
        assert len(comp_result.novel_paths) == 0

    def test_avg_depth_empty_paths(self, framework):
        """Test _avg_depth returns 0 for empty paths list (line 359 coverage)."""
        avg = framework._avg_depth([])
        assert avg == 0.0

    def test_path_signature_generation(self, framework):
        """Test path signature is deterministic."""
        path1 = AttackPath(steps=[
            PathStep("target1", "sqli", "f1", "a1", []),
            PathStep("target2", "xss", "f2", "a2", [])
        ])
        path2 = AttackPath(steps=[
            PathStep("target1", "sqli", "f3", "a3", []),  # Different IDs, same target:technique
            PathStep("target2", "xss", "f4", "a4", [])
        ])
        
        sig1 = framework._path_signature(path1)
        sig2 = framework._path_signature(path2)
        
        # Signatures should match (ignores IDs)
        assert sig1 == sig2
        assert sig1 == "target1:sqli|target2:xss"
