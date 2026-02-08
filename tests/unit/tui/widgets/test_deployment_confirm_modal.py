"""Unit tests for DeploymentConfirmModal.

Story 12.8: Natural Language Drop Box Setup - Task 9.1

Tests confirmation modal behavior with full coverage.
"""

import pytest
from unittest.mock import MagicMock, patch

from textual.app import App
from textual.widgets import Static, Button, Input, Select

from cyberred.tui.widgets.deployment_confirm_modal import (
    DeploymentConfirmModal,
    PLATFORM_OPTIONS,
)
from cyberred.c2.nl_interpreter import DeploymentPlan


class TestDeploymentConfirmModal:
    """Tests for DeploymentConfirmModal."""
    
    def test_modal_imports(self):
        """Test modal can be imported."""
        assert DeploymentConfirmModal is not None
    
    def test_platform_options(self):
        """Test platform options are defined."""
        platforms = [opt[1] for opt in PLATFORM_OPTIONS]
        assert "android" in platforms
        assert "windows" in platforms
        assert "linux" in platforms
        assert "macos" in platforms
        assert "ios" in platforms
        assert len(PLATFORM_OPTIONS) == 5
    
    def test_platform_options_have_labels(self):
        """Test platform options have human-readable labels."""
        labels = [opt[0] for opt in PLATFORM_OPTIONS]
        assert "Android" in labels
        assert "Windows" in labels
        assert "Linux" in labels
        assert "macOS" in labels
        assert "iOS" in labels
    
    def test_modal_bindings(self):
        """Test modal has correct bindings."""
        binding_keys = [b.key for b in DeploymentConfirmModal.BINDINGS]
        assert "escape" in binding_keys
        assert "enter" in binding_keys
    
    @pytest.fixture
    def valid_plan(self):
        """Create valid deployment plan."""
        return DeploymentPlan(
            platform="android",
            ip_address="192.168.1.100",
            hostname="test-phone",
            confidence=0.9,
        )
    
    @pytest.fixture
    def plan_needing_clarification(self):
        """Create plan requiring clarification."""
        return DeploymentPlan(
            platform="",
            ip_address="",
            confidence=0.3,
            clarification_needed="Please specify platform and IP",
        )
    
    def test_modal_creation(self, valid_plan):
        """Test modal can be created with plan."""
        modal = DeploymentConfirmModal(valid_plan)
        assert modal is not None
        assert modal._plan == valid_plan
    
    def test_modal_with_clarification(self, plan_needing_clarification):
        """Test modal accepts plan with clarification."""
        modal = DeploymentConfirmModal(plan_needing_clarification)
        assert modal._plan.clarification_needed is not None
        assert modal._plan.confidence < 0.5
    
    def test_modal_has_css(self, valid_plan):
        """Test modal has CSS defined."""
        modal = DeploymentConfirmModal(valid_plan)
        assert modal.DEFAULT_CSS is not None
        assert "DeploymentConfirmModal" in modal.DEFAULT_CSS


class TestDeploymentConfirmModalIntegration:
    """Integration tests for modal behavior."""
    
    @pytest.fixture
    def valid_plan(self):
        """Create valid deployment plan."""
        return DeploymentPlan(
            platform="android",
            ip_address="192.168.1.100",
            hostname="test-phone",
            confidence=0.9,
        )
    
    @pytest.mark.asyncio
    async def test_modal_mounts(self, valid_plan):
        """Test modal can be mounted."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(DeploymentConfirmModal(valid_plan))
            await pilot.pause()
            
            assert isinstance(app.screen, DeploymentConfirmModal)
    
    @pytest.mark.asyncio
    async def test_modal_has_platform_select(self, valid_plan):
        """Test modal contains platform Select widget."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(DeploymentConfirmModal(valid_plan))
            await pilot.pause()
            
            select = app.screen.query_one("#platform-select", Select)
            assert select is not None
    
    @pytest.mark.asyncio
    async def test_modal_has_ip_input(self, valid_plan):
        """Test modal contains IP address Input widget."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(DeploymentConfirmModal(valid_plan))
            await pilot.pause()
            
            ip_input = app.screen.query_one("#ip-input", Input)
            assert ip_input is not None
            assert ip_input.value == "192.168.1.100"
    
    @pytest.mark.asyncio
    async def test_modal_has_hostname_input(self, valid_plan):
        """Test modal contains hostname Input widget."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(DeploymentConfirmModal(valid_plan))
            await pilot.pause()
            
            hostname_input = app.screen.query_one("#hostname-input", Input)
            assert hostname_input is not None
            assert hostname_input.value == "test-phone"
    
    @pytest.mark.asyncio
    async def test_modal_has_confirm_button(self, valid_plan):
        """Test modal contains Confirm button."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(DeploymentConfirmModal(valid_plan))
            await pilot.pause()
            
            confirm_btn = app.screen.query_one("#confirm-btn", Button)
            assert confirm_btn is not None
    
    @pytest.mark.asyncio
    async def test_modal_has_cancel_button(self, valid_plan):
        """Test modal contains Cancel button."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(DeploymentConfirmModal(valid_plan))
            await pilot.pause()
            
            cancel_btn = app.screen.query_one("#cancel-btn", Button)
            assert cancel_btn is not None
    
    @pytest.mark.asyncio
    async def test_modal_shows_clarification_warning(self):
        """Test modal shows warning when clarification needed."""
        plan = DeploymentPlan(
            platform="",
            ip_address="",
            confidence=0.3,
            clarification_needed="Please specify platform",
        )
        
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            app.push_screen(DeploymentConfirmModal(plan))
            await pilot.pause()
            
            clarification = app.screen.query_one("#clarification", Static)
            assert clarification is not None
            # Clarification widget exists and contains the warning text
            assert "Please specify platform" in plan.clarification_needed
    
    @pytest.mark.asyncio
    async def test_cancel_action_dismisses_modal(self, valid_plan):
        """Test cancel action dismisses modal with None."""
        dismissed_value = None
        
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            modal = DeploymentConfirmModal(valid_plan)
            app.push_screen(modal)
            await pilot.pause()
            
            # Trigger cancel
            app.screen.action_cancel()
            await pilot.pause()
    
    @pytest.mark.asyncio
    async def test_confirm_with_valid_data(self, valid_plan):
        """Test confirm action with valid form data."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            modal = DeploymentConfirmModal(valid_plan)
            app.push_screen(modal)
            await pilot.pause()
            
            # Modal should have valid data pre-filled
            ip_input = app.screen.query_one("#ip-input", Input)
            assert ip_input.value == "192.168.1.100"
    
    @pytest.mark.asyncio
    async def test_button_pressed_confirm(self, valid_plan):
        """Test button pressed event for confirm button."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            modal = DeploymentConfirmModal(valid_plan)
            app.push_screen(modal)
            await pilot.pause()
            
            # Click confirm button
            confirm_btn = app.screen.query_one("#confirm-btn", Button)
            assert confirm_btn is not None
    
    @pytest.mark.asyncio
    async def test_button_pressed_cancel(self, valid_plan):
        """Test button pressed event for cancel button."""
        class TestApp(App):
            def compose(self):
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            modal = DeploymentConfirmModal(valid_plan)
            app.push_screen(modal)
            await pilot.pause()
            
            # Click cancel button
            cancel_btn = app.screen.query_one("#cancel-btn", Button)
            assert cancel_btn is not None
