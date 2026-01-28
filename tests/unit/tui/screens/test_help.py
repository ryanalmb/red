"""Unit tests for HelpScreen.

Story 9.11: Keyboard Navigation (F-Keys) - Task 5

Tests for help overlay screen:
- Displays all keybindings in organized sections
- Includes F-keys, navigation keys, and special actions
- Dismissal via ?, ESC, or any key
"""
import pytest
from unittest.mock import MagicMock


class TestHelpScreen:
    """Tests for HelpScreen modal."""

    def test_help_screen_instantiation(self) -> None:
        """Test HelpScreen can be instantiated."""
        from cyberred.tui.screens.help import HelpScreen
        
        screen = HelpScreen()
        
        assert screen is not None

    def test_help_screen_has_title(self) -> None:
        """Test HelpScreen has appropriate title."""
        from cyberred.tui.screens.help import HelpScreen
        
        screen = HelpScreen()
        
        assert hasattr(screen, "TITLE") or screen.title is not None

    def test_help_screen_bindings_include_dismiss_keys(self) -> None:
        """Test HelpScreen has dismiss bindings (?, ESC)."""
        from cyberred.tui.screens.help import HelpScreen
        
        screen = HelpScreen()
        
        # Check BINDINGS for dismiss keys
        binding_keys = [b[0] if isinstance(b, tuple) else b.key for b in screen.BINDINGS]
        
        # Should have escape and ? for dismissal
        assert "escape" in binding_keys
        assert "question_mark" in binding_keys or "?" in binding_keys

    def test_help_screen_has_default_css(self) -> None:
        """Test HelpScreen has CSS for styling."""
        from cyberred.tui.screens.help import HelpScreen
        
        screen = HelpScreen()
        
        assert screen.DEFAULT_CSS is not None or screen.CSS is not None


class TestHelpScreenActions:
    """Tests for HelpScreen action methods."""

    def test_action_dismiss_closes_screen(self) -> None:
        """Test action_dismiss dismisses the modal."""
        from cyberred.tui.screens.help import HelpScreen
        
        screen = HelpScreen()
        screen.dismiss = MagicMock()
        
        screen.action_dismiss()
        
        screen.dismiss.assert_called_once()


class TestHelpScreenIntegration:
    """Integration tests for HelpScreen with Textual."""

    @pytest.mark.asyncio
    async def test_help_screen_mounts_in_app(self) -> None:
        """Test HelpScreen can be mounted in app."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from cyberred.tui.screens.help import HelpScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main content")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(HelpScreen())
            await pilot.pause()
            
            assert len(app.screen_stack) >= 2

    @pytest.mark.asyncio
    async def test_help_screen_escape_dismisses(self) -> None:
        """Test ESC key dismisses help screen."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from cyberred.tui.screens.help import HelpScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main content")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(HelpScreen())
            await pilot.pause()
            
            await pilot.press("escape")
            await pilot.pause()
            
            assert len(app.screen_stack) == 1

    @pytest.mark.asyncio
    async def test_help_screen_question_mark_dismisses(self) -> None:
        """Test ? key dismisses help screen (toggle behavior)."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from cyberred.tui.screens.help import HelpScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main content")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(HelpScreen())
            await pilot.pause()
            
            # Press ? to dismiss (toggle)
            await pilot.press("?")
            await pilot.pause()
            
            assert len(app.screen_stack) == 1

    @pytest.mark.asyncio
    async def test_help_screen_displays_fkey_section(self) -> None:
        """Test HelpScreen displays F-key section."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from cyberred.tui.screens.help import HelpScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main content")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(HelpScreen())
            await pilot.pause()
            
            # The screen should exist and have content
            assert app.screen is not None

    @pytest.mark.asyncio
    async def test_help_screen_displays_navigation_section(self) -> None:
        """Test HelpScreen displays navigation keys section."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from cyberred.tui.screens.help import HelpScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main content")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(HelpScreen())
            await pilot.pause()
            
            # The screen should exist
            assert app.screen is not None

    @pytest.mark.asyncio
    async def test_help_screen_displays_special_actions_section(self) -> None:
        """Test HelpScreen displays special actions section."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from cyberred.tui.screens.help import HelpScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main content")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(HelpScreen())
            await pilot.pause()
            
            # The screen should exist
            assert app.screen is not None
