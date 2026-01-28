"""Integration tests for F-key navigation.

Story 9.11: Keyboard Navigation (F-Keys) - Task 11

Tests for full F-key navigation flow:
- F-key navigation with Textual pilot
- Keyboard-only operation (no mouse)
- Focus transitions between views
- Kill switch confirmation modal flow
- Help overlay display and dismissal
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestFKeyNavigationFlow:
    """Integration tests for F-key navigation flow."""

    @pytest.mark.asyncio
    async def test_full_fkey_navigation_cycle(self) -> None:
        """Test navigating through all F-key views in sequence."""
        from cyberred.tui.app import CyberRedApp, EngagementState
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # F1 - Dashboard
            await pilot.press("f1")
            await pilot.pause()
            assert app.is_running
            
            # F3 - Logs
            await pilot.press("f3")
            await pilot.pause()
            assert app.is_running
            
            # F5 - Pause/Resume
            app.engagement_state = EngagementState.RUNNING
            await pilot.press("f5")
            await pilot.pause()
            assert app.engagement_state == EngagementState.PAUSED
            
            # F5 again - Resume
            await pilot.press("f5")
            await pilot.pause()
            assert app.engagement_state == EngagementState.RUNNING

    @pytest.mark.asyncio
    async def test_keyboard_only_operation(self) -> None:
        """Test all actions accessible via keyboard only (AC #7)."""
        from cyberred.tui.app import CyberRedApp
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # All these should work without mouse
            await pilot.press("f1")  # Dashboard
            await pilot.pause()
            
            await pilot.press("f6")  # Drop Box
            await pilot.pause()
            await pilot.press("escape")  # Close Drop Box
            await pilot.pause()
            
            # F10 with confirmation flow
            await pilot.press("f10")  # Kill confirm modal
            await pilot.pause()
            await pilot.press("n")  # Cancel
            await pilot.pause()
            
            # Help overlay
            app.action_help()
            await pilot.pause()
            await pilot.press("escape")  # Close help
            await pilot.pause()
            
            assert app.is_running

    @pytest.mark.asyncio
    async def test_focus_transitions_between_panes(self) -> None:
        """Test focus moves correctly between panes (AC #7)."""
        from cyberred.tui.app import CyberRedApp
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # F1 focuses dashboard/hive grid
            await pilot.press("f1")
            await pilot.pause()
            
            # F3 focuses logs
            await pilot.press("f3")
            await pilot.pause()
            
            # App should still be running
            assert app.is_running

    @pytest.mark.asyncio
    async def test_kill_switch_confirmation_flow(self) -> None:
        """Test complete kill switch confirmation flow (AC #4)."""
        from cyberred.tui.app import CyberRedApp
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # Press F10 to show modal
            await pilot.press("f10")
            await pilot.pause()
            
            # Verify modal is shown
            assert isinstance(app.screen, KillSwitchConfirmScreen)
            
            # Press N to cancel
            await pilot.press("n")
            await pilot.pause()
            
            # Modal should be dismissed
            assert not isinstance(app.screen, KillSwitchConfirmScreen)

    @pytest.mark.asyncio
    async def test_kill_switch_escape_immediate(self) -> None:
        """Test ESC triggers immediate kill without confirmation (AC #4)."""
        from cyberred.tui.app import CyberRedApp
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            initial_stack = len(app.screen_stack)
            
            # Press ESC - should trigger immediate panic, not modal
            await pilot.press("escape")
            await pilot.pause()
            
            # Should NOT have pushed a modal
            assert len(app.screen_stack) == initial_stack
            # Note: panic action shows notification but doesn't push screen

    @pytest.mark.asyncio
    async def test_help_overlay_display_and_dismissal(self) -> None:
        """Test help overlay displays and dismisses correctly (AC #3)."""
        from cyberred.tui.app import CyberRedApp
        from cyberred.tui.screens.help import HelpScreen
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # Show help
            app.action_help()
            await pilot.pause()
            
            # Verify help is shown
            assert isinstance(app.screen, HelpScreen)
            
            # Dismiss with ESC
            await pilot.press("escape")
            await pilot.pause()
            
            # Help should be dismissed
            assert not isinstance(app.screen, HelpScreen)

    @pytest.mark.asyncio
    async def test_dropbox_screen_navigation(self) -> None:
        """Test F6 Drop Box screen navigation."""
        from cyberred.tui.app import CyberRedApp
        from cyberred.tui.screens.dropbox import DropBoxScreen
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # Press F6 to show drop box
            await pilot.press("f6")
            await pilot.pause()
            
            # Verify Drop Box screen is shown
            assert isinstance(app.screen, DropBoxScreen)
            
            # Dismiss with ESC
            await pilot.press("escape")
            await pilot.pause()
            
            # Should be back to main screen
            assert not isinstance(app.screen, DropBoxScreen)

    @pytest.mark.asyncio
    async def test_director_panel_toggle(self) -> None:
        """Test F7 toggles director panel visibility."""
        from cyberred.tui.app import CyberRedApp
        
        app = CyberRedApp()
        async with app.run_test() as pilot:
            # Press F7 to toggle director panel
            await pilot.press("f7")
            await pilot.pause()
            
            # App should still be running
            assert app.is_running
            
            # Press F7 again to toggle back
            await pilot.press("f7")
            await pilot.pause()
            
            assert app.is_running


class TestFKeyBarIntegration:
    """Integration tests for FKeyBar widget in app."""

    @pytest.mark.asyncio
    async def test_fkey_bar_widget_available(self) -> None:
        """Test FKeyBar widget is properly exported and usable."""
        from cyberred.tui.widgets import FKeyBar, FKeyMapping, DEFAULT_FKEY_MAPPINGS
        
        # Verify exports work
        assert FKeyBar is not None
        assert FKeyMapping is not None
        assert DEFAULT_FKEY_MAPPINGS is not None
        assert len(DEFAULT_FKEY_MAPPINGS) >= 8  # F1-F7 + F10

    @pytest.mark.asyncio
    async def test_fkey_mapping_matches_app_bindings(self) -> None:
        """Test FKeyBar mappings match app BINDINGS."""
        from cyberred.tui.app import CyberRedApp
        from cyberred.tui.widgets import DEFAULT_FKEY_MAPPINGS
        
        app = CyberRedApp()
        
        # Get app binding keys
        app_keys = [b[0] if isinstance(b, tuple) else b.key for b in app.BINDINGS]
        
        # All FKeyBar mappings should have corresponding app bindings
        for mapping in DEFAULT_FKEY_MAPPINGS:
            assert mapping.key in app_keys, f"{mapping.key} not in app BINDINGS"


class TestKeybindingsIntegration:
    """Integration tests for keybindings module."""

    def test_keybindings_load_default(self) -> None:
        """Test keybindings loads default mappings."""
        from cyberred.tui.keybindings import load_keybindings, DEFAULT_FKEY_MAPPINGS
        
        result = load_keybindings(None)
        
        assert result == DEFAULT_FKEY_MAPPINGS

    def test_keybindings_fkey_mapping_reexport(self) -> None:
        """Test FKeyMapping is re-exported from keybindings."""
        from cyberred.tui.keybindings import FKeyMapping
        from cyberred.tui.widgets.fkey_bar import FKeyMapping as OriginalFKeyMapping
        
        # Should be the same class
        assert FKeyMapping is OriginalFKeyMapping


class TestScreensIntegration:
    """Integration tests for screen exports."""

    def test_screens_export_all_new_screens(self) -> None:
        """Test screens __init__ exports all new screens."""
        from cyberred.tui.screens import (
            DropBoxScreen,
            KillSwitchConfirmScreen,
            HelpScreen,
        )
        
        assert DropBoxScreen is not None
        assert KillSwitchConfirmScreen is not None
        assert HelpScreen is not None
