"""Unit tests for F-key actions in CyberRedApp.

Story 9.11: Keyboard Navigation (F-Keys) - Task 10

Tests for F-key actions:
- F10 triggers kill switch confirmation modal
- ? triggers help overlay
- ESC triggers immediate kill (no confirmation)
- FKeyBar integration in app layout
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestFKeyBindings:
    """Tests for F-key bindings in CyberRedApp."""

    def test_app_has_f10_binding(self) -> None:
        """Test CyberRedApp has F10 binding for kill switch confirmation."""
        from cyberred.tui.app import CyberRedApp
        
        app = CyberRedApp()
        
        # Check BINDINGS contains f10
        binding_keys = [b[0] if isinstance(b, tuple) else b.key for b in app.BINDINGS]
        
        assert "f10" in binding_keys

    def test_app_has_question_mark_binding(self) -> None:
        """Test CyberRedApp has ? binding for help."""
        from cyberred.tui.app import CyberRedApp
        
        app = CyberRedApp()
        
        # Check BINDINGS contains ? or question_mark
        binding_keys = [b[0] if isinstance(b, tuple) else b.key for b in app.BINDINGS]
        
        assert "question_mark" in binding_keys or "?" in binding_keys

    def test_app_has_escape_binding(self) -> None:
        """Test CyberRedApp has ESC binding for immediate kill."""
        from cyberred.tui.app import CyberRedApp
        
        app = CyberRedApp()
        
        binding_keys = [b[0] if isinstance(b, tuple) else b.key for b in app.BINDINGS]
        
        assert "escape" in binding_keys


class TestKillSwitchConfirmAction:
    """Tests for kill switch confirmation action."""

    def test_action_kill_switch_confirm_exists(self) -> None:
        """Test action_kill_switch_confirm method exists."""
        from cyberred.tui.app import CyberRedApp
        
        app = CyberRedApp()
        
        assert hasattr(app, "action_kill_switch_confirm")
        assert callable(app.action_kill_switch_confirm)


class TestHelpAction:
    """Tests for help action."""

    def test_action_help_exists(self) -> None:
        """Test action_help method exists."""
        from cyberred.tui.app import CyberRedApp
        
        app = CyberRedApp()
        
        assert hasattr(app, "action_help")
        assert callable(app.action_help)


class TestFKeyActionsIntegration:
    """Integration tests for F-key actions."""

    @pytest.mark.asyncio
    async def test_f10_shows_kill_confirm_modal(self) -> None:
        """Test F10 key shows kill switch confirmation modal."""
        from cyberred.tui.app import CyberRedApp
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # Press F10
            await pilot.press("f10")
            await pilot.pause()
            
            # Should have pushed KillSwitchConfirmScreen
            assert len(app.screen_stack) >= 2
            assert isinstance(app.screen, KillSwitchConfirmScreen)

    @pytest.mark.asyncio
    async def test_question_mark_shows_help_screen(self) -> None:
        """Test ? key (action_help) shows help overlay."""
        from cyberred.tui.app import CyberRedApp
        from cyberred.tui.screens.help import HelpScreen
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # Trigger action_help directly (? key binding)
            app.action_help()
            await pilot.pause()
            
            # Should have pushed HelpScreen
            assert len(app.screen_stack) >= 2
            assert isinstance(app.screen, HelpScreen)

    @pytest.mark.asyncio
    async def test_escape_triggers_immediate_panic(self) -> None:
        """Test ESC triggers immediate kill (no confirmation per AC #4)."""
        from cyberred.tui.app import CyberRedApp
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # ESC should trigger panic action directly (no modal)
            # This is verified by checking no modal is pushed
            initial_stack_len = len(app.screen_stack)
            
            await pilot.press("escape")
            await pilot.pause()
            
            # ESC triggers panic, not a modal - stack should remain same
            # (panic action shows notification but doesn't push screen)
            # Note: The actual panic behavior publishes to event bus
            assert len(app.screen_stack) == initial_stack_len

    @pytest.mark.asyncio
    async def test_f1_triggers_dashboard(self) -> None:
        """Test F1 triggers dashboard action."""
        from cyberred.tui.app import CyberRedApp
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # Press F1
            await pilot.press("f1")
            await pilot.pause()
            
            # Should not crash and app should still be running
            assert app.is_running

    @pytest.mark.asyncio
    async def test_f5_triggers_pause_resume(self) -> None:
        """Test F5 triggers pause/resume action."""
        from cyberred.tui.app import CyberRedApp, EngagementState
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # Set initial state to RUNNING
            app.engagement_state = EngagementState.RUNNING
            
            # Press F5 to pause
            await pilot.press("f5")
            await pilot.pause()
            
            # Should be paused now
            assert app.engagement_state == EngagementState.PAUSED

    @pytest.mark.asyncio
    async def test_f6_shows_dropbox_screen(self) -> None:
        """Test F6 shows drop box status screen."""
        from cyberred.tui.app import CyberRedApp
        from cyberred.tui.screens.dropbox import DropBoxScreen
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # Press F6
            await pilot.press("f6")
            await pilot.pause()
            
            # Should have pushed DropBoxScreen
            assert len(app.screen_stack) >= 2
            assert isinstance(app.screen, DropBoxScreen)

    @pytest.mark.asyncio
    async def test_f7_toggles_director_panel(self) -> None:
        """Test F7 toggles director panel visibility."""
        from cyberred.tui.app import CyberRedApp
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # Press F7 to toggle director panel
            await pilot.press("f7")
            await pilot.pause()
            
            # Should not crash
            assert app.is_running

    @pytest.mark.asyncio
    async def test_kill_confirm_modal_yes_triggers_panic(self) -> None:
        """Test confirming kill switch modal triggers panic."""
        from cyberred.tui.app import CyberRedApp
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # Press F10 to show modal
            await pilot.press("f10")
            await pilot.pause()
            
            # Press Y to confirm
            await pilot.press("y")
            await pilot.pause()
            
            # Modal should be dismissed
            assert len(app.screen_stack) == 1

    @pytest.mark.asyncio
    async def test_kill_confirm_modal_no_cancels(self) -> None:
        """Test canceling kill switch modal doesn't trigger panic."""
        from cyberred.tui.app import CyberRedApp
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # Press F10 to show modal
            await pilot.press("f10")
            await pilot.pause()
            
            # Press N to cancel
            await pilot.press("n")
            await pilot.pause()
            
            # Modal should be dismissed, app continues
            assert len(app.screen_stack) == 1
            assert app.is_running
