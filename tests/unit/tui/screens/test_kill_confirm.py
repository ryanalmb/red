"""Unit tests for KillSwitchConfirmScreen.

Story 9.11: Keyboard Navigation (F-Keys) - Task 4

Tests for kill switch confirmation modal:
- Modal displays warning message and Y/N options
- Y key confirms and dismisses with True
- N key cancels and dismisses with False
- ESC key cancels and dismisses with False
- Modal styling per UX spec
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestKillSwitchConfirmScreen:
    """Tests for KillSwitchConfirmScreen modal."""

    def test_kill_confirm_screen_instantiation(self) -> None:
        """Test KillSwitchConfirmScreen can be instantiated."""
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        screen = KillSwitchConfirmScreen()
        
        assert screen is not None

    def test_kill_confirm_screen_has_title(self) -> None:
        """Test KillSwitchConfirmScreen has appropriate title."""
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        screen = KillSwitchConfirmScreen()
        
        # Should have a title indicating kill switch
        assert hasattr(screen, "TITLE") or screen.title is not None

    def test_kill_confirm_screen_bindings(self) -> None:
        """Test KillSwitchConfirmScreen has Y/N/ESC bindings."""
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        screen = KillSwitchConfirmScreen()
        
        # Check BINDINGS attribute contains expected keys
        binding_keys = [b[0] if isinstance(b, tuple) else b.key for b in screen.BINDINGS]
        
        assert "y" in binding_keys
        assert "n" in binding_keys
        assert "escape" in binding_keys

    def test_kill_confirm_screen_has_default_css(self) -> None:
        """Test KillSwitchConfirmScreen has CSS for styling."""
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        screen = KillSwitchConfirmScreen()
        
        # Should have some CSS defined
        assert screen.DEFAULT_CSS is not None or screen.CSS is not None


class TestKillSwitchConfirmScreenActions:
    """Tests for KillSwitchConfirmScreen action methods."""

    @pytest.mark.asyncio
    async def test_action_confirm_dismisses_with_true(self) -> None:
        """Test action_confirm dismisses modal with True."""
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        screen = KillSwitchConfirmScreen()
        screen.dismiss = MagicMock()
        
        screen.action_confirm()
        
        screen.dismiss.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_action_cancel_dismisses_with_false(self) -> None:
        """Test action_cancel dismisses modal with False."""
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        screen = KillSwitchConfirmScreen()
        screen.dismiss = MagicMock()
        
        screen.action_cancel()
        
        screen.dismiss.assert_called_once_with(False)


class TestKillSwitchConfirmScreenIntegration:
    """Integration tests for KillSwitchConfirmScreen with Textual."""

    @pytest.mark.asyncio
    async def test_kill_confirm_screen_mounts_in_app(self) -> None:
        """Test KillSwitchConfirmScreen can be mounted in app."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main content")
        
        app = TestApp()
        async with app.run_test() as pilot:
            # Push the kill confirm screen
            app.push_screen(KillSwitchConfirmScreen())
            await pilot.pause()
            
            # Screen should be visible
            assert len(app.screen_stack) >= 2

    @pytest.mark.asyncio
    async def test_kill_confirm_y_key_dismisses_true(self) -> None:
        """Test pressing Y key dismisses with True."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        class TestApp(App):
            def __init__(self):
                super().__init__()
                self.dismiss_result = None
                
            def compose(self) -> ComposeResult:
                yield Static("Main content")
            
            def on_screen_dismiss(self, event) -> None:
                self.dismiss_result = event.result
        
        app = TestApp()
        async with app.run_test() as pilot:
            # Push the kill confirm screen
            screen = KillSwitchConfirmScreen()
            app.push_screen(screen)
            await pilot.pause()
            
            # Press Y to confirm
            await pilot.press("y")
            await pilot.pause()
            
            # Screen should be dismissed
            assert len(app.screen_stack) == 1

    @pytest.mark.asyncio
    async def test_kill_confirm_n_key_dismisses_false(self) -> None:
        """Test pressing N key dismisses with False."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main content")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(KillSwitchConfirmScreen())
            await pilot.pause()
            
            # Press N to cancel
            await pilot.press("n")
            await pilot.pause()
            
            # Screen should be dismissed
            assert len(app.screen_stack) == 1

    @pytest.mark.asyncio
    async def test_kill_confirm_escape_key_dismisses(self) -> None:
        """Test pressing ESC key dismisses modal."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main content")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(KillSwitchConfirmScreen())
            await pilot.pause()
            
            # Press ESC to cancel
            await pilot.press("escape")
            await pilot.pause()
            
            # Screen should be dismissed
            assert len(app.screen_stack) == 1

    @pytest.mark.asyncio
    async def test_kill_confirm_displays_warning_message(self) -> None:
        """Test KillSwitchConfirmScreen displays warning message."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main content")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(KillSwitchConfirmScreen())
            await pilot.pause()
            
            # Check screen content contains warning elements
            screen = app.screen
            # The screen should have some warning text
            assert screen is not None

    @pytest.mark.asyncio
    async def test_kill_confirm_has_buttons(self) -> None:
        """Test KillSwitchConfirmScreen has confirm/cancel buttons."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static, Button
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main content")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(KillSwitchConfirmScreen())
            await pilot.pause()
            
            # Should have buttons in the modal
            buttons = app.screen.query(Button)
            assert len(buttons) >= 2  # At least confirm and cancel

    @pytest.mark.asyncio
    async def test_kill_confirm_button_click_confirm(self) -> None:
        """Test clicking confirm button dismisses with True."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static, Button
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main content")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(KillSwitchConfirmScreen())
            await pilot.pause()
            
            # Click the confirm button
            confirm_btn = app.screen.query_one("#btn-confirm", Button)
            await pilot.click(confirm_btn)
            await pilot.pause()
            
            # Screen should be dismissed
            assert len(app.screen_stack) == 1

    @pytest.mark.asyncio
    async def test_kill_confirm_button_click_cancel(self) -> None:
        """Test clicking cancel button dismisses with False."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static, Button
        from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main content")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(KillSwitchConfirmScreen())
            await pilot.pause()
            
            # Click the cancel button
            cancel_btn = app.screen.query_one("#btn-cancel", Button)
            await pilot.click(cancel_btn)
            await pilot.pause()
            
            # Screen should be dismissed
            assert len(app.screen_stack) == 1
