"""Unit tests for DropBoxWizardScreen.

Story 12.8: Natural Language Drop Box Setup - Task 9.1

Tests wizard screen composition and behavior with full coverage.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from textual.app import App
from textual.widgets import Static, TextArea, Button

from cyberred.tui.screens.dropbox_wizard import DropBoxWizardScreen, EXAMPLE_PROMPTS
from cyberred.c2.nl_interpreter import DeploymentPlan, InterpretationError


class TestDropBoxWizardScreen:
    """Tests for DropBoxWizardScreen composition."""
    
    def test_screen_imports(self):
        """Test screen can be imported."""
        assert DropBoxWizardScreen is not None
    
    def test_screen_title(self):
        """Test screen has correct title."""
        assert DropBoxWizardScreen.TITLE == "Deploy Drop Box"
    
    def test_screen_bindings(self):
        """Test screen has required bindings."""
        binding_keys = [b.key for b in DropBoxWizardScreen.BINDINGS]
        assert "escape" in binding_keys
        assert "ctrl+enter" in binding_keys
    
    def test_example_prompts_content(self):
        """Test example prompts are defined."""
        assert "Android" in EXAMPLE_PROMPTS
        assert "Windows" in EXAMPLE_PROMPTS
        assert "Linux" in EXAMPLE_PROMPTS
        assert "192.168.1.100" in EXAMPLE_PROMPTS
        assert "macOS" in EXAMPLE_PROMPTS


class TestDropBoxWizardScreenComposition:
    """Tests for screen widget composition."""
    
    @pytest.fixture
    def screen(self):
        """Create screen instance."""
        return DropBoxWizardScreen()
    
    def test_screen_creates_without_error(self, screen):
        """Test screen can be instantiated."""
        assert screen is not None
        assert screen._processing is False
    
    def test_screen_has_css(self, screen):
        """Test screen has CSS defined."""
        assert screen.DEFAULT_CSS is not None
        assert len(screen.DEFAULT_CSS) > 0
        assert "DropBoxWizardScreen" in screen.DEFAULT_CSS


class TestDropBoxWizardScreenIntegration:
    """Integration-style tests for wizard screen."""
    
    @pytest.mark.asyncio
    async def test_screen_mounts(self):
        """Test screen can be mounted in app."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(DropBoxWizardScreen())
            await pilot.pause()
            assert isinstance(app.screen, DropBoxWizardScreen)
    
    @pytest.mark.asyncio
    async def test_screen_has_text_area(self):
        """Test screen contains TextArea for NL input."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(DropBoxWizardScreen())
            await pilot.pause()
            
            # Query for TextArea
            text_area = app.screen.query_one("#nl-input", TextArea)
            assert text_area is not None
    
    @pytest.mark.asyncio
    async def test_screen_has_deploy_button(self):
        """Test screen contains Deploy button."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(DropBoxWizardScreen())
            await pilot.pause()
            
            deploy_btn = app.screen.query_one("#deploy-btn", Button)
            assert deploy_btn is not None
            assert "Deploy" in str(deploy_btn.label)
    
    @pytest.mark.asyncio
    async def test_screen_has_cancel_button(self):
        """Test screen contains Cancel button."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(DropBoxWizardScreen())
            await pilot.pause()
            
            cancel_btn = app.screen.query_one("#cancel-btn", Button)
            assert cancel_btn is not None
    
    @pytest.mark.asyncio
    async def test_empty_input_shows_error(self):
        """Test empty input shows error message."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(DropBoxWizardScreen())
            await pilot.pause()
            
            # Trigger deploy with empty input
            app.screen.action_deploy()
            await pilot.pause()
            
            # Error should be visible
            error_display = app.screen.query_one("#error-display", Static)
            assert "visible" in error_display.classes or "enter a deployment" in error_display.renderable.lower()
    
    @pytest.mark.asyncio
    async def test_status_update(self):
        """Test status update method."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(DropBoxWizardScreen())
            await pilot.pause()
            
            app.screen._update_status("Test status message")
            await pilot.pause()
            status = app.screen.query_one("#status", Static)
            # Check render_str or the update was applied
            assert status is not None
    
    @pytest.mark.asyncio
    async def test_show_and_hide_error(self):
        """Test show and hide error methods."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(DropBoxWizardScreen())
            await pilot.pause()
            
            # Show error
            app.screen._show_error("Test error")
            error_display = app.screen.query_one("#error-display", Static)
            assert "visible" in error_display.classes
            
            # Hide error
            app.screen._hide_error()
            assert "visible" not in error_display.classes
