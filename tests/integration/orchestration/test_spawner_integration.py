import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
import sys

# Mock swarms to avoid ImportError due to broken dependency
sys.modules["swarms"] = MagicMock()
sys.modules["swarms.structs"] = MagicMock()
sys.modules["swarms.structs.agent"] = MagicMock()

from cyberred.core.models import Scope, Target
from cyberred.agents.roles import AgentRole
from cyberred.core.events import EventBus

# We expect ImportError until implementation
# from cyberred.orchestration.spawner import DynamicSpawner
# from cyberred.orchestration.router import SwarmRouterWrapper

@pytest.fixture
def mock_event_bus():
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock()
    return bus

@pytest.fixture
def mock_router():
    # Mocking SwarmRouterWrapper to avoid dependency issues during test
    router = Mock()
    router.spawn_swarm = AsyncMock(return_value=[Mock(agent_id="agent-1"), Mock(agent_id="agent-2")])
    router.create_agent = Mock(return_value=Mock(agent_id="agent-3"))
    return router

@pytest.fixture
def basic_scope():
    return Scope(
        networks=["192.168.1.0/24"],
        webapps=["http://example.com"],
        wireless=[],
        domains=[],
        exclusions=[]
    )

@pytest.mark.asyncio
async def test_full_scaling_lifecycle(mock_router, mock_event_bus, basic_scope):
    """Test initial spawn -> scale up -> phase transition flow."""
    from cyberred.orchestration.spawner import DynamicSpawner
    
    engagement_id = "integration-test-eng"
    spawner = DynamicSpawner(mock_router, mock_event_bus, engagement_id)
    
    # 1. Initial Spawn
    # 10 (network) + 5 (webapp) = 15 agents
    initial_agents = await spawner.spawn_initial(basic_scope)
    
    assert mock_router.spawn_swarm.call_count == 1
    call_args = mock_router.spawn_swarm.call_args
    # spawn_swarm called with kwargs
    assert call_args[1]['count'] == 15 # count
    assert call_args[1]['engagement_id'] == engagement_id
    
    # 2. Scale Up
    new_targets = [Target(value="10.0.0.0/16", type="network")]
    # Heuristic for /16 is not explicitly defined in story, 
    # but story says "agents_per_class_c": 10.
    # Implementation should probably handle CIDR math or just count networks.
    # Assuming the heuristics map is simple for now (per network item).
    # If implementation parses CIDR, we need to be careful.
    # Story says: "~10 agents per /24 network".
    # Implementation detail: Does it calculate IPs? Or just items in list?
    # Test assumes items in list for simplicity unless refined.
    
    scaled_agents = await spawner.scale_up(new_targets)
    
    assert mock_router.spawn_swarm.call_count == 2
    # Check that it spawned more agents
    
    # 3. Phase Transition
    # Spawner should have subscribed to phase events
    # Allow background task to run
    import asyncio
    await asyncio.sleep(0.1)
    
    mock_event_bus.subscribe.assert_called_with(
        f"engagement:{engagement_id}:phase",
        spawner._handle_phase_transition
    )
    
    # Simulate phase transition event
    await spawner._handle_phase_transition("engagement:123:phase", {"phase": "exploit"})
    
    # Check if distribution update was logged/handled
    # (Since spawn_swarm uses current distribution, we might not see immediate call 
    # unless we trigger a rebalance or if handling phase transition triggers scaling/respawning.
    # Story doesn't explicitly say phase transition triggers respawn, just "adjusts role distribution".
    # This implies *future* spawns use new distribution.
    # Or maybe it reshuffles? Story says "Spawner adjusts role distribution... on phase transitions".
    # We will verify internal state or subsequent spawns use new distribution.)
    
    # Trigger another scale up to verify new distribution is used
    more_targets = [Target(value="wifi", type="wireless")]
    await spawner.scale_up(more_targets)
    
    assert mock_router.spawn_swarm.call_count == 3
    call_args = mock_router.spawn_swarm.call_args
    # Verify distribution argument in last call matches exploit phase
    distribution_arg = call_args[1].get('distribution')
    assert distribution_arg[AgentRole.EXPLOIT] == 0.30 # Exploit heavy in exploit phase

@pytest.mark.asyncio
async def test_audit_logging_integration(mock_router, mock_event_bus, basic_scope):
    """Verify that scaling decisions produce audit events."""
    from cyberred.orchestration.spawner import DynamicSpawner
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "audit-test")
    await spawner.spawn_initial(basic_scope)
    
    # Check for specific audit event structure
    publish_calls = mock_event_bus.publish.call_args_list
    
    # Find the spawner audit event
    spawner_events = [
        call for call in publish_calls 
        if call[0][0] == "audit:spawner"
    ]
    
    assert len(spawner_events) > 0
    payload = spawner_events[0][0][1]
    assert "action" in payload
    assert "count" in payload
    assert "rationale" in payload
    assert "decision_context" in payload
