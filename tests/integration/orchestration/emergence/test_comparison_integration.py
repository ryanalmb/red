import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, MagicMock
from cyberred.orchestration.emergence.comparison import EmergenceComparisonFramework, EmergenceComparisonConfig
from cyberred.core.models import AgentAction, Finding

@pytest.mark.asyncio
async def test_full_comparison_flow():
    """Test full flow: isolated run -> stigmergic run -> comparison."""
    import uuid
    
    # Mock EventBus
    event_bus = AsyncMock()
    event_bus.disable_pubsub = Mock()
    event_bus.enable_pubsub = Mock()
    
    config = EmergenceComparisonConfig(agent_count=2)
    framework = EmergenceComparisonFramework(config, event_bus)
    
    # Create Mock Agents
    agent1 = Mock()
    agent1.id = str(uuid.uuid4())
    agent1.run = AsyncMock()
    
    agent2 = Mock()
    agent2.id = str(uuid.uuid4())
    agent2.run = AsyncMock()
    
    agents = [agent1, agent2]
    
    # Helper to create valid Finding
    def create_finding(fid, target, ftype, aid):
        return Finding(
            id=fid,
            type=ftype,
            severity="medium",
            target=target,
            evidence="evidence",
            agent_id=aid,
            timestamp="2024-01-01T00:00:00Z",
            tool="nmap",
            topic="findings:topic",
            signature="sig"
        )
        
    # --- ISOLATED RUN DATA ---
    f1_id = str(uuid.uuid4())
    a1_id = str(uuid.uuid4())
    
    # Agent 1 finds open port
    f1 = create_finding(f1_id, "10.0.0.1", "open_port", agent1.id)
    a1 = AgentAction(
        id=a1_id, 
        agent_id=agent1.id, 
        action_type="scan", 
        target="10.0.0.1", 
        result_finding_id=f1_id, 
        decision_context=["isolated_mode"],
        timestamp="2024-01-01T00:00:00Z"
    )
    
    # Configure agents
    agent1.findings = [f1]
    agent1.actions = [a1]
    agent2.findings = []
    agent2.actions = []
    
    isolated_result = await framework.run_isolated(agents, ["10.0.0.1"], {})
    
    assert isolated_result.mode == "isolated"
    assert len(isolated_result.attack_paths) == 1
    assert isolated_result.attack_paths[0].steps[0].technique == "scan"
    
    # --- STIGMERGIC RUN DATA ---
    # Agent 1 finds open port (same as isolated)
    # Agent 2 sees finding via pubsub (simulated) and exploits it
    
    f1_stig_id = str(uuid.uuid4())
    a1_stig_id = str(uuid.uuid4())
    f2_stig_id = str(uuid.uuid4())
    a2_stig_id = str(uuid.uuid4())

    f1_stig = create_finding(f1_stig_id, "10.0.0.1", "open_port", agent1.id)
    a1_stig = AgentAction(
        id=a1_stig_id, 
        agent_id=agent1.id, 
        action_type="scan", 
        target="10.0.0.1", 
        result_finding_id=f1_stig_id, 
        decision_context=[], # Root action
        timestamp="2024-01-01T00:00:00Z"
    )
    
    f2_stig = create_finding(f2_stig_id, "10.0.0.1", "shell", agent2.id)
    a2_stig = AgentAction(
        id=a2_stig_id, 
        agent_id=agent2.id, 
        action_type="exploit", 
        target="10.0.0.1", 
        result_finding_id=f2_stig_id, 
        decision_context=[f1_stig_id], # Triggered by Agent 1's finding (STIGMERGY!)
        timestamp="2024-01-01T00:01:00Z"
    )
    
    agent1.findings = [f1_stig]
    agent1.actions = [a1_stig]
    agent2.findings = [f2_stig]
    agent2.actions = [a2_stig]
    
    stigmergic_result = await framework.run_stigmergic(agents, ["10.0.0.1"], {})
    
    assert stigmergic_result.mode == "stigmergic"
    assert len(stigmergic_result.attack_paths) == 1
    path = stigmergic_result.attack_paths[0]
    assert path.depth == 2 # Scan -> Exploit
    assert path.steps[0].action_id == a1_stig_id
    assert path.steps[1].action_id == a2_stig_id
    
    # --- COMPARISON ---
    comp_result = framework.compare(isolated_result, stigmergic_result)
    
    # The stigmergic path (scan->exploit) is NOT in isolated (only scan)
    # So it should be novel
    assert len(comp_result.novel_paths) == 1
    assert comp_result.emergence_score == 1.0
    assert comp_result.novel_paths[0].depth == 2
    assert comp_result.novel_paths[0].is_novel is True
