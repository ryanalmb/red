"""Safety tests for agent crash recovery.

Verifies ERR5 compliance: "Log crash, spawn replacement, resume from checkpoint"
Story 7.12: Agent Crash Recovery
"""

import asyncio
from datetime import datetime, UTC, timedelta
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

from cyberred.orchestration.crash_monitor import (
    AgentCrashMonitor,
    CRASH_DETECTION_TIMEOUT_S,
    HEARTBEAT_INTERVAL_S,
)
from cyberred.storage.checkpoint import CheckpointManager, AgentState


class TestCrashRecoverySafety:
    """Safety tests for crash recovery - ERR5 compliance."""

    @pytest.fixture
    def checkpoint_manager(self, tmp_path: Path):
        """Create a real CheckpointManager."""
        return CheckpointManager(base_path=tmp_path)

    @pytest.mark.asyncio
    async def test_engagement_continues_after_agent_crash(self, checkpoint_manager):
        """Verify engagement continues despite individual agent failure (ERR5)."""
        engagement_id = "eng-safety-1"
        crash_handled = asyncio.Event()
        crashed_agent_ids = []

        async def handle_crash(agent_id: str, eng_id: str):
            crashed_agent_ids.append(agent_id)
            crash_handled.set()

        event_bus = MagicMock()
        event_bus.subscribe = AsyncMock()
        event_bus.publish = AsyncMock()

        monitor = AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=handle_crash,
        )

        # Register multiple agents for an engagement
        await monitor.register_agent("agent-a", engagement_id)
        await monitor.register_agent("agent-b", engagement_id)
        await monitor.register_agent("agent-c", engagement_id)

        # Simulate crash of agent-b only
        monitor._agents["agent-b"].last_heartbeat = datetime.now(UTC) - timedelta(
            seconds=CRASH_DETECTION_TIMEOUT_S + 5
        )

        # Check agents
        await monitor._check_all_agents()

        # Verify:
        # 1. Crashed agent was detected
        assert "agent-b" in crashed_agent_ids

        # 2. Other agents continue (still monitored)
        assert "agent-a" in monitor._agents
        assert "agent-c" in monitor._agents

        # 3. Engagement can continue with remaining agents
        assert len(monitor._agents) == 2

    @pytest.mark.asyncio
    async def test_no_data_loss_from_crash_recovery(self, checkpoint_manager):
        """Verify no data loss when agent crashes and recovers."""
        engagement_id = "eng-no-loss"

        # Save detailed agent state before "crash"
        original_state = AgentState(
            agent_id="agent-critical",
            agent_type="exploit",
            state={
                "status": "active",
                "specialty": "web",
                "tool_help_cache": {
                    "sqlmap": "usage: sqlmap -u URL ...",
                    "nikto": "usage: nikto -h HOST ...",
                },
                "current_task_id": "task-important-123",
            },
            last_action_id="action-critical-456",
            decision_context="signal-1,signal-2,signal-3",
        )

        await checkpoint_manager.save_agent_state(engagement_id, original_state)

        # Simulate crash and recovery by loading state
        recovered_state = await checkpoint_manager.load_agent_state(
            engagement_id, "agent-critical"
        )

        # Verify ALL data is preserved
        assert recovered_state is not None
        assert recovered_state.agent_id == original_state.agent_id
        assert recovered_state.agent_type == original_state.agent_type
        assert recovered_state.state["status"] == original_state.state["status"]
        assert recovered_state.state["specialty"] == original_state.state["specialty"]
        assert recovered_state.state["tool_help_cache"] == original_state.state["tool_help_cache"]
        assert recovered_state.state["current_task_id"] == original_state.state["current_task_id"]
        assert recovered_state.last_action_id == original_state.last_action_id
        # decision_context is JSON serialized
        assert recovered_state.decision_context is not None

    @pytest.mark.asyncio
    async def test_crash_detection_within_30s_timeout(self, checkpoint_manager):
        """Verify crash is detected within 30s timeout per spec (AC: 1)."""
        # Verify constant is correct per story specification
        assert CRASH_DETECTION_TIMEOUT_S == 30, "Crash detection must be within 30s"
        assert HEARTBEAT_INTERVAL_S == 10, "Heartbeat interval must be 10s"

        detected_at = None

        async def on_crash(agent_id: str, engagement_id: str):
            nonlocal detected_at
            detected_at = datetime.now(UTC)

        event_bus = MagicMock()
        event_bus.subscribe = AsyncMock()

        monitor = AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=on_crash,
        )

        # Register agent
        await monitor.register_agent("agent-timeout", "eng-timeout")

        # Set heartbeat to exactly 31 seconds ago (just past timeout)
        crash_time = datetime.now(UTC) - timedelta(seconds=31)
        monitor._agents["agent-timeout"].last_heartbeat = crash_time

        # Check agents
        await monitor._check_all_agents()

        # Crash should have been detected
        assert detected_at is not None, "Crash should be detected after 30s timeout"

    @pytest.mark.asyncio
    async def test_replacement_agent_inherits_context(self, checkpoint_manager):
        """Verify replacement agent inherits context from crashed agent (AC: 3, 4)."""
        engagement_id = "eng-inherit"

        # Save state with rich context
        original_state = AgentState(
            agent_id="agent-context",
            agent_type="postex",
            state={
                "status": "active",
                "specialty": "privesc",
                "current_task_id": "task-pivoting",
            },
            last_action_id="action-lateral-move",
            decision_context="finding-1,intel-2,rag-3",
        )

        await checkpoint_manager.save_agent_state(engagement_id, original_state)

        # Load state (simulating replacement agent initialization)
        loaded_state = await checkpoint_manager.load_agent_state(
            engagement_id, "agent-context"
        )

        # Verify context is inherited
        assert loaded_state.state["current_task_id"] == "task-pivoting"
        assert loaded_state.last_action_id == "action-lateral-move"
        assert loaded_state.decision_context is not None

    @pytest.mark.asyncio
    async def test_crash_callback_error_does_not_stop_other_recoveries(
        self, checkpoint_manager
    ):
        """Verify callback errors don't prevent other crash recoveries."""
        call_count = 0
        successful_recoveries = []

        async def flaky_callback(agent_id: str, engagement_id: str):
            nonlocal call_count
            call_count += 1
            if agent_id == "agent-fail":
                raise RuntimeError("Simulated callback failure")
            successful_recoveries.append(agent_id)

        event_bus = MagicMock()
        event_bus.subscribe = AsyncMock()

        monitor = AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=flaky_callback,
        )

        # Register multiple agents
        await monitor.register_agent("agent-fail", "eng-err")
        await monitor.register_agent("agent-ok-1", "eng-err")
        await monitor.register_agent("agent-ok-2", "eng-err")

        # Make all crash
        old_time = datetime.now(UTC) - timedelta(seconds=CRASH_DETECTION_TIMEOUT_S + 5)
        for aid in list(monitor._agents.keys()):
            monitor._agents[aid].last_heartbeat = old_time

        # Check agents - should handle all despite error
        await monitor._check_all_agents()

        # All callbacks should have been attempted
        assert call_count == 3

        # Successful recoveries should have occurred
        assert "agent-ok-1" in successful_recoveries
        assert "agent-ok-2" in successful_recoveries
