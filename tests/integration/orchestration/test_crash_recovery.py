"""Integration tests for agent crash recovery.

Tests the full crash → detect → replace → resume flow with real components.
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
)
from cyberred.storage.checkpoint import CheckpointManager, AgentState


class TestCrashRecoveryIntegration:
    """Integration tests for crash recovery flow."""

    @pytest.fixture
    def checkpoint_manager(self, tmp_path: Path):
        """Create a real CheckpointManager."""
        return CheckpointManager(base_path=tmp_path)

    @pytest.mark.asyncio
    async def test_full_crash_detect_replace_flow(self, checkpoint_manager):
        """Test end-to-end crash → detect → replace → resume flow."""
        # Track replacement calls
        replaced_agents = []

        async def on_crash(agent_id: str, engagement_id: str):
            replaced_agents.append((agent_id, engagement_id))

        # Setup event bus mock
        event_bus = MagicMock()
        event_bus.subscribe = AsyncMock()
        event_bus.publish = AsyncMock()

        # Create crash monitor
        monitor = AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=on_crash,
        )

        # Register an agent
        await monitor.register_agent("agent-1", "eng-1")

        # Simulate crash by setting old heartbeat
        monitor._agents["agent-1"].last_heartbeat = datetime.now(UTC) - timedelta(
            seconds=CRASH_DETECTION_TIMEOUT_S + 5
        )

        # Check agents - should detect crash
        await monitor._check_all_agents()

        # Verify crash was detected and callback called
        assert len(replaced_agents) == 1
        assert replaced_agents[0] == ("agent-1", "eng-1")

        # Agent should be removed from monitoring
        assert "agent-1" not in monitor._agents

    @pytest.mark.asyncio
    async def test_checkpoint_persistence_across_simulated_crash(self, checkpoint_manager):
        """Test checkpoint persistence across simulated crashes."""
        engagement_id = "eng-persist-test"

        # Save agent state
        original_state = AgentState(
            agent_id="agent-persist",
            agent_type="recon",
            state={
                "status": "active",
                "specialty": "network",
                "tool_help_cache": {"nmap": "usage..."},
            },
            last_action_id="action-999",
            decision_context="ctx-a,ctx-b,ctx-c",
        )
        await checkpoint_manager.save_agent_state(engagement_id, original_state)

        # Simulate "crash" - create new checkpoint manager (like restart)
        new_checkpoint_manager = CheckpointManager(base_path=checkpoint_manager.base_path)

        # Load agent state
        loaded_state = await new_checkpoint_manager.load_agent_state(
            engagement_id, "agent-persist"
        )

        # Verify state was persisted
        assert loaded_state is not None
        assert loaded_state.agent_id == "agent-persist"
        assert loaded_state.agent_type == "recon"
        assert loaded_state.state["status"] == "active"
        assert loaded_state.state["specialty"] == "network"
        assert loaded_state.last_action_id == "action-999"

    @pytest.mark.asyncio
    async def test_multiple_concurrent_agent_crashes(self, checkpoint_manager):
        """Test handling multiple concurrent agent crashes."""
        crashed_agents = []

        async def on_crash(agent_id: str, engagement_id: str):
            crashed_agents.append(agent_id)

        event_bus = MagicMock()
        event_bus.subscribe = AsyncMock()

        monitor = AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=on_crash,
        )

        # Register multiple agents
        for i in range(5):
            await monitor.register_agent(f"agent-{i}", "eng-multi")

        # Make all agents "crash" by setting old heartbeat
        old_time = datetime.now(UTC) - timedelta(seconds=CRASH_DETECTION_TIMEOUT_S + 10)
        for agent_id in list(monitor._agents.keys()):
            monitor._agents[agent_id].last_heartbeat = old_time

        # Check agents
        await monitor._check_all_agents()

        # All 5 should have been detected as crashed
        assert len(crashed_agents) == 5
        assert len(monitor._agents) == 0

    @pytest.mark.asyncio
    async def test_heartbeat_resets_crash_timer(self, checkpoint_manager):
        """Test that heartbeat resets crash detection timer."""
        crashed_agents = []

        async def on_crash(agent_id: str, engagement_id: str):
            crashed_agents.append(agent_id)

        event_bus = MagicMock()
        event_bus.subscribe = AsyncMock()

        monitor = AgentCrashMonitor(
            event_bus=event_bus,
            checkpoint_manager=checkpoint_manager,
            on_crash_callback=on_crash,
        )

        # Register agent
        await monitor.register_agent("agent-hb", "eng-hb")

        # Set heartbeat to almost expired
        almost_expired = datetime.now(UTC) - timedelta(
            seconds=CRASH_DETECTION_TIMEOUT_S - 1
        )
        monitor._agents["agent-hb"].last_heartbeat = almost_expired

        # Receive heartbeat - should reset timer
        await monitor._handle_heartbeat(
            "agent:agent-hb:heartbeat",
            {"agent_id": "agent-hb", "engagement_id": "eng-hb"},
        )

        # Check agents - should NOT detect crash now
        await monitor._check_all_agents()

        assert len(crashed_agents) == 0
        assert "agent-hb" in monitor._agents
        assert monitor._agents["agent-hb"].status == "healthy"
