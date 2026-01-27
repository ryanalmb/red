"""Unit tests for AgentCrashMonitor.

Tests crash detection, heartbeat handling, and agent health tracking.
Story 7.12: Agent Crash Recovery
"""

import asyncio
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.orchestration.crash_monitor import (
    AgentCrashMonitor,
    AgentHealthState,
    CRASH_DETECTION_TIMEOUT_S,
    HEARTBEAT_INTERVAL_S,
)


class TestAgentHealthState:
    """Tests for AgentHealthState dataclass."""

    def test_creation_with_defaults(self):
        """Test creating AgentHealthState with default values."""
        state = AgentHealthState(
            agent_id="agent-1",
            engagement_id="eng-1",
            last_heartbeat=datetime.now(UTC),
        )
        assert state.agent_id == "agent-1"
        assert state.engagement_id == "eng-1"
        assert state.status == "healthy"
        assert state.task_id is None
        assert state.consecutive_misses == 0

    def test_creation_with_all_values(self):
        """Test creating AgentHealthState with all values specified."""
        now = datetime.now(UTC)
        state = AgentHealthState(
            agent_id="agent-2",
            engagement_id="eng-2",
            last_heartbeat=now,
            status="suspected",
            task_id="task-1",
            consecutive_misses=2,
        )
        assert state.status == "suspected"
        assert state.task_id == "task-1"
        assert state.consecutive_misses == 2


class TestAgentCrashMonitorInit:
    """Tests for AgentCrashMonitor initialization."""

    def test_init_with_dependencies(self):
        """Test AgentCrashMonitor initializes with required dependencies."""
        event_bus = MagicMock()
        checkpoint_manager = MagicMock()
        on_crash = AsyncMock()

        monitor = AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=on_crash,
        )

        assert monitor._event_bus is event_bus
        assert monitor._checkpoint_manager is checkpoint_manager
        assert monitor._on_crash is on_crash
        assert monitor._agents == {}
        assert monitor._monitor_task is None


class TestAgentCrashMonitorRegistration:
    """Tests for agent registration/deregistration."""

    @pytest.fixture
    def monitor(self):
        """Create a monitor instance for testing."""
        event_bus = MagicMock()
        checkpoint_manager = MagicMock()
        on_crash = AsyncMock()
        return AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=on_crash,
        )

    @pytest.mark.asyncio
    async def test_register_agent(self, monitor):
        """Test registering an agent for monitoring."""
        await monitor.register_agent("agent-1", "eng-1")

        assert "agent-1" in monitor._agents
        state = monitor._agents["agent-1"]
        assert state.agent_id == "agent-1"
        assert state.engagement_id == "eng-1"
        assert state.status == "healthy"

    @pytest.mark.asyncio
    async def test_register_multiple_agents(self, monitor):
        """Test registering multiple agents."""
        await monitor.register_agent("agent-1", "eng-1")
        await monitor.register_agent("agent-2", "eng-1")
        await monitor.register_agent("agent-3", "eng-2")

        assert len(monitor._agents) == 3
        assert "agent-1" in monitor._agents
        assert "agent-2" in monitor._agents
        assert "agent-3" in monitor._agents

    @pytest.mark.asyncio
    async def test_unregister_agent(self, monitor):
        """Test unregistering an agent."""
        await monitor.register_agent("agent-1", "eng-1")
        assert "agent-1" in monitor._agents

        await monitor.unregister_agent("agent-1")
        assert "agent-1" not in monitor._agents

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_agent(self, monitor):
        """Test unregistering a non-existent agent is safe."""
        # Should not raise
        await monitor.unregister_agent("nonexistent")


class TestAgentCrashMonitorHeartbeat:
    """Tests for heartbeat handling."""

    @pytest.fixture
    def monitor(self):
        """Create a monitor instance for testing."""
        event_bus = MagicMock()
        checkpoint_manager = MagicMock()
        on_crash = AsyncMock()
        return AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=on_crash,
        )

    @pytest.mark.asyncio
    async def test_handle_heartbeat_updates_timestamp(self, monitor):
        """Test heartbeat updates last_heartbeat timestamp."""
        await monitor.register_agent("agent-1", "eng-1")
        old_heartbeat = monitor._agents["agent-1"].last_heartbeat

        # Small delay to ensure timestamp difference
        await asyncio.sleep(0.01)

        await monitor._handle_heartbeat(
            "agent:agent-1:heartbeat",
            {"agent_id": "agent-1", "engagement_id": "eng-1", "task_id": "task-1"},
        )

        new_heartbeat = monitor._agents["agent-1"].last_heartbeat
        assert new_heartbeat > old_heartbeat

    @pytest.mark.asyncio
    async def test_handle_heartbeat_updates_status_to_healthy(self, monitor):
        """Test heartbeat resets status to healthy."""
        await monitor.register_agent("agent-1", "eng-1")
        monitor._agents["agent-1"].status = "suspected"
        monitor._agents["agent-1"].consecutive_misses = 2

        await monitor._handle_heartbeat(
            "agent:agent-1:heartbeat",
            {"agent_id": "agent-1", "engagement_id": "eng-1"},
        )

        state = monitor._agents["agent-1"]
        assert state.status == "healthy"
        assert state.consecutive_misses == 0

    @pytest.mark.asyncio
    async def test_handle_heartbeat_updates_task_id(self, monitor):
        """Test heartbeat updates current task_id."""
        await monitor.register_agent("agent-1", "eng-1")

        await monitor._handle_heartbeat(
            "agent:agent-1:heartbeat",
            {"agent_id": "agent-1", "engagement_id": "eng-1", "task_id": "new-task"},
        )

        assert monitor._agents["agent-1"].task_id == "new-task"

    @pytest.mark.asyncio
    async def test_handle_heartbeat_ignores_unknown_agent(self, monitor):
        """Test heartbeat for unknown agent is safely ignored."""
        # No agents registered
        await monitor._handle_heartbeat(
            "agent:unknown:heartbeat",
            {"agent_id": "unknown", "engagement_id": "eng-1"},
        )
        # Should not raise and should not add agent
        assert "unknown" not in monitor._agents

    @pytest.mark.asyncio
    async def test_handle_heartbeat_with_missing_agent_id(self, monitor):
        """Test heartbeat with missing agent_id is ignored."""
        await monitor.register_agent("agent-1", "eng-1")

        # Missing agent_id in data
        await monitor._handle_heartbeat(
            "agent:agent-1:heartbeat",
            {"engagement_id": "eng-1"},
        )
        # Should not crash, state unchanged


class TestAgentCrashMonitorCrashDetection:
    """Tests for crash detection logic."""

    @pytest.fixture
    def monitor(self):
        """Create a monitor instance for testing."""
        event_bus = MagicMock()
        checkpoint_manager = MagicMock()
        on_crash = AsyncMock()
        return AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=on_crash,
        )

    @pytest.mark.asyncio
    async def test_check_agents_detects_crash_after_timeout(self, monitor):
        """Test that agents with stale heartbeats are detected as crashed."""
        await monitor.register_agent("agent-1", "eng-1")

        # Set heartbeat to be older than timeout
        monitor._agents["agent-1"].last_heartbeat = datetime.now(UTC) - timedelta(
            seconds=CRASH_DETECTION_TIMEOUT_S + 5
        )

        await monitor._check_all_agents()

        # Crash callback should be called
        monitor._on_crash.assert_called_once_with("agent-1", "eng-1")
        # Agent should be removed from tracking
        assert "agent-1" not in monitor._agents

    @pytest.mark.asyncio
    async def test_check_agents_healthy_agent_not_crashed(self, monitor):
        """Test that healthy agents are not marked as crashed."""
        await monitor.register_agent("agent-1", "eng-1")

        # Recent heartbeat
        monitor._agents["agent-1"].last_heartbeat = datetime.now(UTC)

        await monitor._check_all_agents()

        # Crash callback should NOT be called
        monitor._on_crash.assert_not_called()
        # Agent should still be tracked
        assert "agent-1" in monitor._agents

    @pytest.mark.asyncio
    async def test_check_agents_multiple_crashes(self, monitor):
        """Test detecting multiple crashed agents."""
        await monitor.register_agent("agent-1", "eng-1")
        await monitor.register_agent("agent-2", "eng-1")
        await monitor.register_agent("agent-3", "eng-1")

        # Set agents 1 and 3 as crashed
        old_time = datetime.now(UTC) - timedelta(seconds=CRASH_DETECTION_TIMEOUT_S + 5)
        monitor._agents["agent-1"].last_heartbeat = old_time
        monitor._agents["agent-3"].last_heartbeat = old_time
        # Agent 2 is healthy
        monitor._agents["agent-2"].last_heartbeat = datetime.now(UTC)

        await monitor._check_all_agents()

        # Two crash callbacks should be called
        assert monitor._on_crash.call_count == 2
        # Only agent-2 should remain
        assert "agent-2" in monitor._agents
        assert "agent-1" not in monitor._agents
        assert "agent-3" not in monitor._agents

    def test_crash_detection_timeout_constant(self):
        """Test that crash detection timeout is 30 seconds per spec."""
        assert CRASH_DETECTION_TIMEOUT_S == 30

    def test_heartbeat_interval_constant(self):
        """Test that heartbeat interval is 10 seconds per spec."""
        assert HEARTBEAT_INTERVAL_S == 10


class TestAgentCrashMonitorStartStop:
    """Tests for monitor start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_subscribes_to_heartbeats(self):
        """Test that start() subscribes to heartbeat channel."""
        event_bus = MagicMock()
        event_bus.subscribe = AsyncMock()
        checkpoint_manager = MagicMock()
        on_crash = AsyncMock()

        monitor = AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=on_crash,
        )

        await monitor.start()

        # Should subscribe to heartbeat pattern
        event_bus.subscribe.assert_called_once()
        call_args = event_bus.subscribe.call_args
        assert "heartbeat" in call_args[0][0]

        # Cleanup
        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_monitor_task(self):
        """Test that stop() cancels the monitoring task."""
        event_bus = MagicMock()
        event_bus.subscribe = AsyncMock()
        checkpoint_manager = MagicMock()
        on_crash = AsyncMock()

        monitor = AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=on_crash,
        )

        await monitor.start()
        assert monitor._monitor_task is not None

        await monitor.stop()
        assert monitor._monitor_task is None or monitor._monitor_task.cancelled()

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self):
        """Test that stop() without start() doesn't raise."""
        event_bus = MagicMock()
        checkpoint_manager = MagicMock()
        on_crash = AsyncMock()

        monitor = AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=on_crash,
        )

        # Should not raise
        await monitor.stop()


class TestAgentCrashMonitorGetAgentState:
    """Tests for get_agent_state method."""

    @pytest.fixture
    def monitor(self):
        """Create a monitor instance for testing."""
        event_bus = MagicMock()
        checkpoint_manager = MagicMock()
        on_crash = AsyncMock()
        return AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=on_crash,
        )

    @pytest.mark.asyncio
    async def test_get_agent_state_returns_state(self, monitor):
        """Test getting agent state."""
        await monitor.register_agent("agent-1", "eng-1")

        state = monitor.get_agent_state("agent-1")

        assert state is not None
        assert state.agent_id == "agent-1"

    @pytest.mark.asyncio
    async def test_get_agent_state_returns_none_for_unknown(self, monitor):
        """Test getting state for unknown agent returns None."""
        state = monitor.get_agent_state("unknown")
        assert state is None

    @pytest.mark.asyncio
    async def test_get_all_agent_states(self, monitor):
        """Test getting all agent states."""
        await monitor.register_agent("agent-1", "eng-1")
        await monitor.register_agent("agent-2", "eng-1")

        states = monitor.get_all_agent_states()

        assert len(states) == 2
        agent_ids = [s.agent_id for s in states]
        assert "agent-1" in agent_ids
        assert "agent-2" in agent_ids


class TestAgentCrashMonitorErrorHandling:
    """Tests for error handling in monitor."""

    @pytest.mark.asyncio
    async def test_monitor_loop_handles_check_errors(self):
        """Test that monitor loop continues after errors in check."""
        event_bus = MagicMock()
        event_bus.subscribe = AsyncMock()
        checkpoint_manager = MagicMock()
        on_crash = AsyncMock()

        monitor = AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=on_crash,
        )

        # Make _check_all_agents raise an exception
        call_count = 0
        original_check = monitor._check_all_agents

        async def error_check():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Test error")
            # Second call works fine

        monitor._check_all_agents = error_check

        # Start monitor and let it run briefly
        await monitor.start()
        
        # Give it time to run through the loop at least once
        # Use a short sleep interval by patching
        with patch('cyberred.orchestration.crash_monitor.HEARTBEAT_INTERVAL_S', 0.01):
            await asyncio.sleep(0.05)

        await monitor.stop()

        # Monitor should have continued despite error
        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_crash_callback_error_is_logged_not_raised(self):
        """Test that errors in crash callback don't stop processing."""
        event_bus = MagicMock()
        event_bus.subscribe = AsyncMock()
        checkpoint_manager = MagicMock()
        
        # Callback that raises on first call
        call_count = 0
        async def failing_callback(agent_id: str, engagement_id: str):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Callback error")

        monitor = AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=failing_callback,
        )

        # Register two agents that will both crash
        await monitor.register_agent("agent-1", "eng-1")
        await monitor.register_agent("agent-2", "eng-1")

        # Set both as crashed
        old_time = datetime.now(UTC) - timedelta(seconds=CRASH_DETECTION_TIMEOUT_S + 5)
        monitor._agents["agent-1"].last_heartbeat = old_time
        monitor._agents["agent-2"].last_heartbeat = old_time

        # Should not raise despite callback error
        await monitor._check_all_agents()

        # Both callbacks should have been called (second one succeeds)
        assert call_count == 2
        # Both agents should be removed
        assert len(monitor._agents) == 0

    @pytest.mark.asyncio
    async def test_monitor_loop_exits_on_cancellation(self):
        """Test that monitor loop exits cleanly on cancellation."""
        event_bus = MagicMock()
        event_bus.subscribe = AsyncMock()
        checkpoint_manager = MagicMock()
        on_crash = AsyncMock()

        monitor = AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=on_crash,
        )

        await monitor.start()
        assert monitor._monitor_task is not None
        
        # Cancel the task
        monitor._monitor_task.cancel()
        
        # Wait for it to finish
        with pytest.raises(asyncio.CancelledError):
            await monitor._monitor_task
        
        # Cleanup
        await monitor.stop()
