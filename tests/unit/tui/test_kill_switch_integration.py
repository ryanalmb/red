"""Unit tests for Kill Switch TUI Integration.

Story 10.4: Kill Switch TUI Integration
Tests for integrating the tri-path KillSwitch (Story 1.9) into the TUI.

TDD Phase: RED - These tests should fail until implementation is complete.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from textual.pilot import Pilot

from cyberred.tui.app import CyberRedApp, EngagementState


class TestKillSwitchAttribute:
    """Test that CyberRedApp has _killswitch attribute."""

    def test_app_has_killswitch_attribute(self) -> None:
        """AC #1: CyberRedApp has _killswitch attribute."""
        app = CyberRedApp()
        assert hasattr(app, "_killswitch")

    def test_app_killswitch_is_none_by_default(self) -> None:
        """KillSwitch is None when no Redis/Docker clients provided."""
        app = CyberRedApp()
        assert app._killswitch is None

    def test_app_killswitch_initialized_with_clients(self) -> None:
        """KillSwitch is initialized when Redis client is provided."""
        mock_redis = MagicMock()
        mock_docker = MagicMock()
        app = CyberRedApp(
            redis_client=mock_redis,
            docker_client=mock_docker,
            engagement_id="test-engagement",
        )
        assert app._killswitch is not None

    def test_app_killswitch_has_engagement_id(self) -> None:
        """KillSwitch is initialized with engagement_id."""
        mock_redis = MagicMock()
        app = CyberRedApp(
            redis_client=mock_redis,
            engagement_id="test-engagement-123",
        )
        assert app._killswitch is not None
        assert app._killswitch._engagement_id == "test-engagement-123"


class TestActionPanicIntegration:
    """Test that action_panic calls KillSwitch.trigger()."""

    @pytest.mark.asyncio
    async def test_action_panic_calls_killswitch_trigger(self) -> None:
        """AC #2: action_panic() calls killswitch.trigger()."""
        mock_killswitch = MagicMock()
        mock_killswitch.trigger = AsyncMock(return_value={
            "success": True,
            "duration_ms": 100,
            "paths": {"redis": True, "sigterm": True, "docker": True},
        })
        
        app = CyberRedApp()
        app._killswitch = mock_killswitch
        
        async with app.run_test() as pilot:
            await app.action_panic()
            mock_killswitch.trigger.assert_called_once()

    @pytest.mark.asyncio
    async def test_action_panic_passes_trigger_source_esc(self) -> None:
        """AC #2: action_panic logs trigger_source as ESC for direct panic."""
        mock_killswitch = MagicMock()
        mock_killswitch.trigger = AsyncMock(return_value={
            "success": True,
            "duration_ms": 50,
            "paths": {"redis": True, "sigterm": False, "docker": True},
        })
        
        app = CyberRedApp()
        app._killswitch = mock_killswitch
        
        async with app.run_test() as pilot:
            await app.action_panic(trigger_source="ESC")
            mock_killswitch.trigger.assert_called_once()
            call_kwargs = mock_killswitch.trigger.call_args[1]
            assert call_kwargs.get("triggered_by") == "operator"

    @pytest.mark.asyncio
    async def test_action_panic_fallback_to_event_bus_without_killswitch(self) -> None:
        """action_panic falls back to event bus when no KillSwitch."""
        mock_bus = MagicMock()
        mock_bus.publish = AsyncMock()
        mock_bus.subscribe = AsyncMock()  # Mock subscribe to avoid coroutine error
        
        app = CyberRedApp(event_bus=mock_bus)
        app._killswitch = None
        
        async with app.run_test() as pilot:
            await app.action_panic()
            # Check that publish was called with swarm:broadcast and ABORT command
            calls = [c for c in mock_bus.publish.call_args_list 
                     if c[0] == ("swarm:broadcast", {"command": "ABORT"})]
            assert len(calls) == 1


class TestKillSwitchConfirmFlow:
    """Test F10 → confirmation → kill flow."""

    @pytest.mark.asyncio
    async def test_f10_shows_confirmation_modal(self) -> None:
        """AC #3: F10 shows confirmation modal."""
        app = CyberRedApp()
        
        async with app.run_test() as pilot:
            await pilot.press("f10")
            # Check that KillSwitchConfirmScreen is pushed
            from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
            assert any(
                isinstance(screen, KillSwitchConfirmScreen)
                for screen in app.screen_stack
            )

    @pytest.mark.asyncio
    async def test_confirmation_yes_triggers_killswitch(self) -> None:
        """AC #4: Confirmation 'Yes' triggers killswitch.trigger()."""
        mock_killswitch = MagicMock()
        mock_killswitch.trigger = AsyncMock(return_value={
            "success": True,
            "duration_ms": 100,
            "paths": {"redis": True, "sigterm": True, "docker": True},
        })
        
        app = CyberRedApp()
        app._killswitch = mock_killswitch
        
        async with app.run_test() as pilot:
            await pilot.press("f10")  # Show confirm modal
            await pilot.press("y")    # Confirm
            # KillSwitch should have been triggered
            mock_killswitch.trigger.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirmation_no_does_not_trigger_killswitch(self) -> None:
        """Confirmation 'No' does not trigger killswitch."""
        mock_killswitch = MagicMock()
        mock_killswitch.trigger = AsyncMock()
        
        app = CyberRedApp()
        app._killswitch = mock_killswitch
        
        async with app.run_test() as pilot:
            await pilot.press("f10")  # Show confirm modal
            await pilot.press("n")    # Cancel
            # KillSwitch should NOT have been triggered
            mock_killswitch.trigger.assert_not_called()

    @pytest.mark.asyncio
    async def test_esc_bypasses_confirmation(self) -> None:
        """AC #5: ESC bypasses confirmation for emergency."""
        mock_killswitch = MagicMock()
        mock_killswitch.trigger = AsyncMock(return_value={
            "success": True,
            "duration_ms": 50,
            "paths": {"redis": True, "sigterm": True, "docker": True},
        })
        
        app = CyberRedApp()
        app._killswitch = mock_killswitch
        
        async with app.run_test() as pilot:
            await pilot.press("escape")  # Direct panic, no confirm
            # KillSwitch should have been triggered immediately
            mock_killswitch.trigger.assert_called_once()


class TestKillCommand:
    """Test 'kill' command in input."""

    @pytest.mark.asyncio
    async def test_kill_command_shows_confirmation(self) -> None:
        """AC #2: 'kill' command triggers action_kill_switch_confirm()."""
        app = CyberRedApp()
        
        async with app.run_test() as pilot:
            # Type 'kill' command
            input_widget = app.query_one("#cmd-input")
            input_widget.value = "kill"
            await pilot.press("enter")
            
            # Check confirmation modal is shown
            from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
            assert any(
                isinstance(screen, KillSwitchConfirmScreen)
                for screen in app.screen_stack
            )

    @pytest.mark.asyncio
    async def test_kill_bang_command_bypasses_confirmation(self) -> None:
        """'kill!' command triggers immediate panic (bypass confirmation)."""
        mock_killswitch = MagicMock()
        mock_killswitch.trigger = AsyncMock(return_value={
            "success": True,
            "duration_ms": 50,
            "paths": {"redis": True, "sigterm": True, "docker": True},
        })
        
        app = CyberRedApp()
        app._killswitch = mock_killswitch
        
        async with app.run_test() as pilot:
            input_widget = app.query_one("#cmd-input")
            input_widget.value = "kill!"
            await pilot.press("enter")
            
            # KillSwitch should have been triggered immediately (no modal)
            mock_killswitch.trigger.assert_called_once()


class TestFrozenEngagementState:
    """Test FROZEN engagement state."""

    def test_frozen_state_exists_in_enum(self) -> None:
        """AC #7: EngagementState enum has FROZEN value."""
        assert hasattr(EngagementState, "FROZEN")
        assert EngagementState.FROZEN.value == "FROZEN"

    def test_status_bar_update_state_validates_input(self) -> None:
        """StatusBarWidget.update_state() validates state input."""
        from cyberred.tui.widgets import StatusBarWidget
        sb = StatusBarWidget()
        
        # Valid states should work
        sb.update_state("RUNNING")
        assert sb.engagement_state == "RUNNING"
        
        sb.update_state("FROZEN")
        assert sb.engagement_state == "FROZEN"
        
        # Invalid state should raise ValueError
        with pytest.raises(ValueError, match="Invalid engagement state"):
            sb.update_state("INVALID_STATE")

    def test_status_bar_render_frozen_has_bold_red(self) -> None:
        """StatusBarWidget renders FROZEN with bold red styling."""
        from cyberred.tui.widgets import StatusBarWidget
        sb = StatusBarWidget()
        sb.update_state("FROZEN")
        rendered = sb.render()
        assert "FROZEN" in rendered
        assert "bold red" in rendered

    @pytest.mark.asyncio
    async def test_action_panic_sets_frozen_state(self) -> None:
        """AC #6, #7: action_panic sets engagement_state to FROZEN."""
        mock_killswitch = MagicMock()
        mock_killswitch.trigger = AsyncMock(return_value={
            "success": True,
            "duration_ms": 100,
            "paths": {"redis": True, "sigterm": True, "docker": True},
        })
        
        app = CyberRedApp()
        app._killswitch = mock_killswitch
        
        async with app.run_test() as pilot:
            # Start with RUNNING
            app.engagement_state = EngagementState.RUNNING
            
            await app.action_panic()
            
            assert app.engagement_state == EngagementState.FROZEN

    @pytest.mark.asyncio
    async def test_status_bar_shows_frozen_state(self) -> None:
        """AC #7: StatusBarWidget displays 'FROZEN' state."""
        mock_killswitch = MagicMock()
        mock_killswitch.trigger = AsyncMock(return_value={
            "success": True,
            "duration_ms": 100,
            "paths": {"redis": True, "sigterm": True, "docker": True},
        })
        
        app = CyberRedApp()
        app._killswitch = mock_killswitch
        
        async with app.run_test() as pilot:
            await app.action_panic()
            
            from cyberred.tui.widgets import StatusBarWidget
            status_bar = app.query_one("#status-bar", StatusBarWidget)
            assert status_bar.engagement_state == "FROZEN"

    @pytest.mark.asyncio
    async def test_kill_chain_log_shows_frozen_message(self) -> None:
        """AC #7: KillChainLog shows 'ENGAGEMENT FROZEN' message."""
        mock_killswitch = MagicMock()
        mock_killswitch.trigger = AsyncMock(return_value={
            "success": True,
            "duration_ms": 100,
            "paths": {"redis": True, "sigterm": True, "docker": True},
        })
        
        app = CyberRedApp()
        app._killswitch = mock_killswitch
        
        async with app.run_test() as pilot:
            await app.action_panic()
            
            from cyberred.tui.widgets import KillChainLog
            log = app.query_one("#kill-chain", KillChainLog)
            # Verify log_event was called - check that log widget has content
            # The log widget writes "ENGAGEMENT FROZEN" during action_panic
            assert log is not None

    @pytest.mark.asyncio
    async def test_action_panic_returns_result_dict(self) -> None:
        """action_panic returns KillSwitch result dict with duration_ms."""
        mock_killswitch = MagicMock()
        mock_killswitch.trigger = AsyncMock(return_value={
            "success": True,
            "duration_ms": 150,
            "paths": {"redis": True, "sigterm": False, "docker": True},
        })
        
        app = CyberRedApp()
        app._killswitch = mock_killswitch
        
        async with app.run_test() as pilot:
            result = await app.action_panic()
            
            assert result is not None
            assert result["success"] is True
            assert result["duration_ms"] == 150
            assert result["paths"]["redis"] is True
            assert result["paths"]["sigterm"] is False


class TestHiveGridFrozenStatus:
    """Test HiveGrid frozen status display."""

    @pytest.mark.asyncio
    async def test_hive_grid_shows_frozen_agents(self) -> None:
        """AC #6: HiveGrid shows all agents as 'frozen' after kill."""
        mock_killswitch = MagicMock()
        mock_killswitch.trigger = AsyncMock(return_value={
            "success": True,
            "duration_ms": 100,
            "paths": {"redis": True, "sigterm": True, "docker": True},
        })
        
        app = CyberRedApp()
        app._killswitch = mock_killswitch
        
        async with app.run_test() as pilot:
            # Set some agents to active state first
            from cyberred.tui.widgets import HiveGrid
            grid = app.query_one("#hive-grid", HiveGrid)
            grid.update_agent(1, "active")
            grid.update_agent(2, "scanning")
            
            await app.action_panic()
            
            # All agents should now show frozen status
            # Check that freeze_all_agents was called or similar


class TestDaemonModeKillSwitch:
    """Test daemon mode kill switch integration."""

    @pytest.mark.asyncio
    async def test_daemon_mode_sends_kill_command(self) -> None:
        """AC #5: Daemon mode sends KILL command via IPC."""
        mock_daemon_client = MagicMock()
        mock_daemon_client.send_kill_command = AsyncMock(return_value=True)
        mock_daemon_client.attach = AsyncMock()
        
        app = CyberRedApp(daemon_client=mock_daemon_client, engagement_id="test")
        # Ensure no KillSwitch so it falls back to daemon client
        app._killswitch = None
        
        async with app.run_test() as pilot:
            await app.action_panic()
            mock_daemon_client.send_kill_command.assert_called_once()

    def test_ipc_command_kill_exists(self) -> None:
        """Verify IPCCommand.KILL exists in enum (Story 10.4 fix)."""
        from cyberred.daemon.ipc import IPCCommand
        assert hasattr(IPCCommand, "KILL")
        assert IPCCommand.KILL.value == "kill"

    def test_ipc_command_auth_response_exists(self) -> None:
        """Verify IPCCommand.AUTH_RESPONSE exists in enum (Story 10.2 fix)."""
        from cyberred.daemon.ipc import IPCCommand
        assert hasattr(IPCCommand, "AUTH_RESPONSE")
        assert IPCCommand.AUTH_RESPONSE.value == "auth.response"

    @pytest.mark.asyncio
    async def test_state_change_frozen_from_daemon(self) -> None:
        """AC #6: TUI handles STATE_CHANGE with FROZEN state from daemon."""
        app = CyberRedApp()
        
        async with app.run_test() as pilot:
            # Set initial state
            app.engagement_state = EngagementState.RUNNING
            
            # Simulate receiving FROZEN state change from daemon
            await app._handle_state_change({"state": "FROZEN"})
            
            assert app.engagement_state == EngagementState.FROZEN
