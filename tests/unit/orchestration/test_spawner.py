import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import sys

# Mock swarms to avoid ImportError due to broken dependency
sys.modules["swarms"] = MagicMock()
sys.modules["swarms.structs"] = MagicMock()
sys.modules["swarms.structs.agent"] = MagicMock()

from cyberred.core.models import Scope, Target
from cyberred.agents.roles import AgentRole
# dynamic import to avoid failure before implementation exists
# from cyberred.orchestration.spawner import DynamicSpawner, SCOPE_HEURISTICS, PHASE_DISTRIBUTIONS

@pytest.fixture
def mock_router():
    router = Mock()
    router.create_agent = Mock(return_value=Mock())
    router.spawn_swarm = AsyncMock(return_value=[Mock() for _ in range(10)])
    return router

@pytest.fixture
def mock_event_bus():
    bus = Mock()
    bus.subscribe = AsyncMock()
    bus.publish = AsyncMock()
    return bus

@pytest.fixture
def default_scope():
    return Scope(
        networks=["192.168.1.0/24"], # 1 network -> 10 agents
        webapps=["http://example.com"], # 1 webapp -> 5 agents
        wireless=["CorpWifi"], # 1 wireless -> 3 agents
        domains=["corp.local"], # 1 domain -> 8 agents
        exclusions=[]
    )
    # Total: 10 + 5 + 3 + 8 = 26 agents

# We expect ImportError until module is created
def test_import_spawner():
    try:
        from cyberred.orchestration.spawner import DynamicSpawner
    except ImportError:
        pytest.fail("Could not import DynamicSpawner")

@pytest.mark.asyncio
async def test_calculate_initial_count(mock_router, mock_event_bus, default_scope):
    from cyberred.orchestration.spawner import DynamicSpawner, SCOPE_HEURISTICS
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    
    # Test calculation
    count = spawner.calculate_initial_count(default_scope)
    
    # Expected: 10*1 + 5*1 + 3*1 + 8*1 = 26
    expected = (
        1 * SCOPE_HEURISTICS["agents_per_class_c"] +
        1 * SCOPE_HEURISTICS["agents_per_webapp"] +
        1 * SCOPE_HEURISTICS["agents_per_wireless"] +
        1 * SCOPE_HEURISTICS["agents_per_ad_domain"]
    )
    assert count == expected

@pytest.mark.asyncio
async def test_calculate_initial_count_minimum(mock_router, mock_event_bus):
    from cyberred.orchestration.spawner import DynamicSpawner, SCOPE_HEURISTICS
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    empty_scope = Scope()
    
    count = spawner.calculate_initial_count(empty_scope)
    assert count == SCOPE_HEURISTICS["minimum_agents"]

@pytest.mark.asyncio
@patch("psutil.virtual_memory")
@patch("psutil.cpu_count")
async def test_calculate_initial_count_ceiling(mock_cpu, mock_mem, mock_router, mock_event_bus):
    from cyberred.orchestration.spawner import DynamicSpawner, SCOPE_HEURISTICS
    
    # Mock massive hardware to ensure ceiling is hit, not hardware limit
    mock_mem.return_value.available = 1000 * 1024 * 1024 * 1024 # 1TB
    mock_cpu.return_value = 200
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    # Massive scope to exceed ceiling
    huge_scope = Scope(networks=["192.168.1.0/24"] * 2000) # 2000 * 10 = 20000
    
    count = spawner.calculate_initial_count(huge_scope)
    assert count == SCOPE_HEURISTICS["default_ceiling"]

@pytest.mark.asyncio
async def test_spawn_initial(mock_router, mock_event_bus, default_scope):
    from cyberred.orchestration.spawner import DynamicSpawner
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    agents = await spawner.spawn_initial(default_scope)
    
    assert len(agents) > 0
    mock_router.spawn_swarm.assert_called_once()
    mock_event_bus.publish.assert_called() # Check audit log

@pytest.mark.asyncio
async def test_scale_up(mock_router, mock_event_bus):
    from cyberred.orchestration.spawner import DynamicSpawner
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    
    # New targets
    new_targets = [
        Target(value="10.0.0.0/24", type="network"), # +10
        Target(value="http://new.com", type="webapp") # +5
    ]
    
    agents = await spawner.scale_up(new_targets)
    
    # Should spawn 15 agents
    assert mock_router.spawn_swarm.call_count == 1
    call_args = mock_router.spawn_swarm.call_args
    assert call_args[1]['count'] == 15 # count
    
    # Check audit log
    from unittest.mock import ANY
    mock_event_bus.publish.assert_called_with(
        "audit:spawner",
        {
            "action": "scale_up",
            "count": 15,
            "rationale": "new_targets_discovered",
            "decision_context": [],
            "timestamp": ANY
        }
    )


@pytest.mark.asyncio
async def test_scale_up_with_domain_and_wireless(mock_router, mock_event_bus):
    """Test scale_up handles domain and wireless target types."""
    from cyberred.orchestration.spawner import DynamicSpawner, SCOPE_HEURISTICS
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    
    # All target types
    new_targets = [
        Target(value="corp.local", type="domain"),     # +8
        Target(value="GuestWifi", type="wireless"),    # +3
    ]
    
    agents = await spawner.scale_up(new_targets)
    
    # Should spawn 11 agents (8 + 3)
    assert mock_router.spawn_swarm.call_count == 1
    call_args = mock_router.spawn_swarm.call_args
    expected_count = (
        SCOPE_HEURISTICS["agents_per_ad_domain"] +
        SCOPE_HEURISTICS["agents_per_wireless"]
    )
    assert call_args[1]['count'] == expected_count


@pytest.mark.asyncio
@patch("psutil.virtual_memory")
@patch("psutil.cpu_count")
async def test_scale_up_at_limit(mock_cpu, mock_mem, mock_router, mock_event_bus):
    """Test scale_up returns empty list when at hardware limit."""
    from cyberred.orchestration.spawner import DynamicSpawner
    
    # Very constrained hardware
    mock_mem.return_value.available = 5 * 1024 * 1024 * 1024  # 5GB
    mock_cpu.return_value = 1  # 1 core = 100 agent limit
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    
    # Manually set active agents to near limit
    spawner._active_agents = [Mock() for _ in range(100)]
    
    # Try to scale up
    new_targets = [Target(value="10.0.0.0/24", type="network")]
    agents = await spawner.scale_up(new_targets)
    
    # Should return empty - at limit
    assert agents == []
    # spawn_swarm should NOT be called
    assert mock_router.spawn_swarm.call_count == 0

def test_adjust_distribution_for_phase(mock_router, mock_event_bus):
    from cyberred.orchestration.spawner import DynamicSpawner, PHASE_DISTRIBUTIONS
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    
    dist = spawner.adjust_distribution_for_phase("recon")
    assert dist == PHASE_DISTRIBUTIONS["recon"]
    
    dist = spawner.adjust_distribution_for_phase("exploit")
    assert dist == PHASE_DISTRIBUTIONS["exploit"]

@patch("psutil.virtual_memory")
@patch("psutil.cpu_count")
def test_detect_hardware_limit(mock_cpu, mock_mem, mock_router, mock_event_bus):
    from cyberred.orchestration.spawner import DynamicSpawner
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    
    # Mock 32GB RAM, 16 Cores
    mock_mem.return_value.available = 32 * 1024 * 1024 * 1024
    mock_cpu.return_value = 16
    
    limit = spawner.detect_hardware_limit()
    
    # Logic check:
    # RAM: (32GB - 4GB) * 1000 = 28000 agents
    # CPU: 16 * 100 = 1600 agents
    # Min(28000, 1600) = 1600
    # Ceiling = 10000
    # Result should be 1600
    assert limit == 1600 

@patch("psutil.virtual_memory")
@patch("psutil.cpu_count")
def test_detect_hardware_limit_capped(mock_cpu, mock_mem, mock_router, mock_event_bus):
    from cyberred.orchestration.spawner import DynamicSpawner, SCOPE_HEURISTICS
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    
    # Mock huge hardware: 1TB RAM, 200 Cores
    mock_mem.return_value.available = 1000 * 1024 * 1024 * 1024
    mock_cpu.return_value = 200
    
    limit = spawner.detect_hardware_limit()
    
    # CPU: 200 * 100 = 20000
    # Ceiling: 10000
    # Result should be 10000
    assert limit == SCOPE_HEURISTICS["default_ceiling"]

@pytest.mark.asyncio
async def test_get_scaling_log(mock_router, mock_event_bus):
    from cyberred.orchestration.spawner import DynamicSpawner
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    new_targets = [Target(value="10.0.0.0/24", type="network")]
    await spawner.scale_up(new_targets)
    
    log = spawner.get_scaling_log()
    assert len(log) == 1
    assert log[0]["action"] == "scale_up"
    assert log[0]["count"] == 10

@patch("psutil.virtual_memory", side_effect=Exception("Hardware error"))
def test_detect_hardware_limit_exception(mock_mem, mock_router, mock_event_bus):
    from cyberred.orchestration.spawner import DynamicSpawner, SCOPE_HEURISTICS
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    limit = spawner.detect_hardware_limit()
    
    # Should fall back to default ceiling
    assert limit == SCOPE_HEURISTICS["default_ceiling"]

def test_get_active_count(mock_router, mock_event_bus):
    from cyberred.orchestration.spawner import DynamicSpawner
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    # Manually add some agents
    spawner._active_agents = ["agent1", "agent2"]
    
    assert spawner.get_active_count() == 2

@pytest.mark.asyncio
async def test_handle_phase_transition_invalid(mock_router, mock_event_bus):
    from cyberred.orchestration.spawner import DynamicSpawner
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    # Initial phase is recon
    assert spawner._current_phase == "recon"
    
    # Invalid phase
    await spawner._handle_phase_transition("channel", {"phase": "invalid_phase"})
    
    # Should stay recon
    assert spawner._current_phase == "recon"


@pytest.mark.asyncio
async def test_start_method_initializes_subscription(mock_router, mock_event_bus):
    """Test that start() initializes phase transition subscription."""
    from cyberred.orchestration.spawner import DynamicSpawner
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    
    # Reset subscription state for testing
    spawner._subscription_initialized = False
    mock_event_bus.subscribe.reset_mock()
    
    # Call start
    await spawner.start()
    
    # Should have subscribed
    assert spawner._subscription_initialized is True
    mock_event_bus.subscribe.assert_called_once()
    
    # Calling start again should not re-subscribe
    await spawner.start()
    assert mock_event_bus.subscribe.call_count == 1  # Still just 1


@pytest.mark.asyncio
async def test_timestamp_is_iso_format(mock_router, mock_event_bus):
    """Test that scaling decisions have valid ISO timestamps."""
    from cyberred.orchestration.spawner import DynamicSpawner
    from datetime import datetime
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    
    new_targets = [Target(value="10.0.0.0/24", type="network")]
    await spawner.scale_up(new_targets)
    
    log = spawner.get_scaling_log()
    assert len(log) == 1
    
    # Validate timestamp is proper ISO format
    timestamp = log[0]["timestamp"]
    assert timestamp != "TODO: timestamp"  # Not placeholder
    # Should parse without error
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert parsed is not None


@pytest.mark.asyncio
async def test_audit_publish_failure_handled_gracefully(mock_router, mock_event_bus):
    """Test that audit publish failures are logged but don't crash scaling."""
    from cyberred.orchestration.spawner import DynamicSpawner
    
    # Make publish raise an exception
    mock_event_bus.publish = AsyncMock(side_effect=Exception("Redis connection lost"))
    
    spawner = DynamicSpawner(mock_router, mock_event_bus, "test-engagement")
    
    # Should not raise despite publish failure
    new_targets = [Target(value="10.0.0.0/24", type="network")]
    agents = await spawner.scale_up(new_targets)
    
    # Scaling should still work
    assert mock_router.spawn_swarm.call_count == 1
    # Decision should still be logged locally
    log = spawner.get_scaling_log()
    assert len(log) == 1


class TestDynamicSpawnerReplaceAgent:
    """Tests for replace_agent crash recovery method (Story 7.12)."""

    @pytest.fixture
    def spawner(self):
        """Create a spawner with mocked router."""
        from cyberred.orchestration.spawner import DynamicSpawner
        
        router = MagicMock()
        router.create_agent = AsyncMock()
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()
        
        spawner = DynamicSpawner(
            router=router,
            event_bus=event_bus,
            engagement_id="eng-test",
        )
        return spawner

    @pytest.mark.asyncio
    async def test_replace_agent_loads_checkpoint(self, spawner):
        """Test replace_agent loads checkpoint for crashed agent."""
        from cyberred.storage.checkpoint import AgentState
        
        checkpoint_manager = MagicMock()
        agent_state = AgentState(
            agent_id="crashed-agent",
            agent_type="recon",
            state={"status": "active"},
        )
        checkpoint_manager.load_agent_state = AsyncMock(return_value=agent_state)
        
        # Mock the created agent
        mock_agent = MagicMock()
        mock_agent.agent_id = "crashed-agent"
        mock_agent.restore_from_checkpoint = AsyncMock()
        mock_agent.spawn = AsyncMock()
        spawner.router.create_agent = AsyncMock(return_value=mock_agent)
        
        result = await spawner.replace_agent(
            "crashed-agent",
            "eng-test",
            checkpoint_manager,
        )
        
        checkpoint_manager.load_agent_state.assert_called_once_with("eng-test", "crashed-agent")
        assert result is mock_agent

    @pytest.mark.asyncio
    async def test_replace_agent_returns_none_without_checkpoint(self, spawner):
        """Test replace_agent returns None if no checkpoint exists."""
        checkpoint_manager = MagicMock()
        checkpoint_manager.load_agent_state = AsyncMock(return_value=None)
        
        result = await spawner.replace_agent(
            "crashed-agent",
            "eng-test",
            checkpoint_manager,
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_replace_agent_restores_state(self, spawner):
        """Test replacement agent has state restored from checkpoint."""
        from cyberred.storage.checkpoint import AgentState
        
        checkpoint_manager = MagicMock()
        agent_state = AgentState(
            agent_id="crashed-agent",
            agent_type="exploit",
            state={"status": "waiting", "specialty": "web"},
            last_action_id="action-123",
        )
        checkpoint_manager.load_agent_state = AsyncMock(return_value=agent_state)
        
        mock_agent = MagicMock()
        mock_agent.agent_id = "crashed-agent"
        mock_agent.restore_from_checkpoint = AsyncMock()
        mock_agent.spawn = AsyncMock()
        spawner.router.create_agent = AsyncMock(return_value=mock_agent)
        
        await spawner.replace_agent(
            "crashed-agent",
            "eng-test",
            checkpoint_manager,
        )
        
        mock_agent.restore_from_checkpoint.assert_called_once_with(agent_state)

    @pytest.mark.asyncio
    async def test_replace_agent_updates_active_agents(self, spawner):
        """Test replacement agent is added to active agents list."""
        from cyberred.storage.checkpoint import AgentState
        
        # Add a mock crashed agent to active list
        old_agent = MagicMock()
        old_agent.agent_id = "crashed-agent"
        spawner._active_agents = [old_agent]
        
        checkpoint_manager = MagicMock()
        agent_state = AgentState(
            agent_id="crashed-agent",
            agent_type="recon",
            state={},
        )
        checkpoint_manager.load_agent_state = AsyncMock(return_value=agent_state)
        
        new_agent = MagicMock()
        new_agent.agent_id = "crashed-agent"
        new_agent.restore_from_checkpoint = AsyncMock()
        new_agent.spawn = AsyncMock()
        spawner.router.create_agent = AsyncMock(return_value=new_agent)
        
        await spawner.replace_agent(
            "crashed-agent",
            "eng-test",
            checkpoint_manager,
        )
        
        assert len(spawner._active_agents) == 1
        assert spawner._active_agents[0] is new_agent

    @pytest.mark.asyncio
    async def test_replace_agent_logs_scaling_decision(self, spawner):
        """Test replace_agent logs the scaling decision."""
        from cyberred.storage.checkpoint import AgentState
        
        checkpoint_manager = MagicMock()
        agent_state = AgentState(
            agent_id="crashed-agent",
            agent_type="recon",
            state={},
        )
        checkpoint_manager.load_agent_state = AsyncMock(return_value=agent_state)
        
        mock_agent = MagicMock()
        mock_agent.agent_id = "crashed-agent"
        mock_agent.restore_from_checkpoint = AsyncMock()
        mock_agent.spawn = AsyncMock()
        spawner.router.create_agent = AsyncMock(return_value=mock_agent)
        
        await spawner.replace_agent(
            "crashed-agent",
            "eng-test",
            checkpoint_manager,
        )
        
        # Check scaling log
        log = spawner.get_scaling_log()
        assert len(log) == 1
        assert log[0]["action"] == "replace_crashed"
        assert log[0]["count"] == 1
        assert "crashed-agent" in log[0]["rationale"]

    @pytest.mark.asyncio
    async def test_replace_agent_returns_none_for_invalid_agent_type(self, spawner):
        """Test replace_agent returns None if agent_type is invalid."""
        from cyberred.storage.checkpoint import AgentState
        
        checkpoint_manager = MagicMock()
        # Invalid agent_type that doesn't match any AgentRole enum value
        agent_state = AgentState(
            agent_id="crashed-agent",
            agent_type="invalid_role_xyz",
            state={},
        )
        checkpoint_manager.load_agent_state = AsyncMock(return_value=agent_state)
        
        result = await spawner.replace_agent(
            "crashed-agent",
            "eng-test",
            checkpoint_manager,
        )
        
        assert result is None
        # create_agent should NOT have been called
        spawner.router.create_agent.assert_not_called()

    @pytest.mark.asyncio
    async def test_replace_agent_calls_spawn_on_replacement(self, spawner):
        """Test replace_agent calls spawn() to start heartbeat and subscriptions."""
        from cyberred.storage.checkpoint import AgentState
        
        checkpoint_manager = MagicMock()
        agent_state = AgentState(
            agent_id="crashed-agent",
            agent_type="exploit",
            state={"status": "active"},
        )
        checkpoint_manager.load_agent_state = AsyncMock(return_value=agent_state)
        
        mock_agent = MagicMock()
        mock_agent.agent_id = "crashed-agent"
        mock_agent.restore_from_checkpoint = AsyncMock()
        mock_agent.spawn = AsyncMock()
        spawner.router.create_agent = AsyncMock(return_value=mock_agent)
        
        result = await spawner.replace_agent(
            "crashed-agent",
            "eng-test",
            checkpoint_manager,
        )
        
        # spawn() MUST be called to start heartbeat task
        mock_agent.spawn.assert_called_once()
        assert result is mock_agent
