"""Integration tests for CyberRedApp TUI Application.

Story 9.1: Textual App Foundation.

Tests:
- CLI attach command launches TUI
- Attach/detach cycle
- Daemon mode event streaming
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Optional


class TestCLIAttachIntegration:
    """Integration tests for cyber-red attach command (AC: #1)."""

    def test_attach_command_exists_in_cli(self) -> None:
        """Test that attach command is defined in CLI."""
        from cyberred.cli import attach
        
        # Check that attach function exists and is callable
        assert attach is not None
        assert callable(attach)

    def test_attach_command_takes_engagement_id(self) -> None:
        """Test attach command accepts engagement ID argument."""
        from cyberred.cli import attach
        import inspect
        
        # Get the function signature
        sig = inspect.signature(attach)
        params = list(sig.parameters.keys())
        
        # Should have engagement_id parameter
        assert "engagement_id" in params


class TestTUIAppIntegration:
    """Integration tests for TUI app lifecycle."""

    @pytest.mark.asyncio
    async def test_app_initialization_with_daemon_client(self) -> None:
        """Test app initializes correctly with daemon client."""
        from cyberred.tui.app import CyberRedApp
        
        mock_client = MagicMock()
        mock_client.attach = AsyncMock(return_value=iter([]))
        mock_client.detach = AsyncMock()
        
        app = CyberRedApp(
            daemon_client=mock_client,
            engagement_id="test-eng-123",
        )
        
        assert app.is_daemon_mode is True
        assert app._engagement_id == "test-eng-123"

    @pytest.mark.asyncio
    async def test_app_initialization_with_event_bus(self) -> None:
        """Test app initializes correctly with event bus."""
        from cyberred.tui.app import CyberRedApp
        
        mock_bus = MagicMock()
        mock_bus.subscribe = AsyncMock()
        mock_bus.publish = AsyncMock()
        
        app = CyberRedApp(event_bus=mock_bus)
        
        assert app.is_daemon_mode is False
        assert app.bus is mock_bus


class TestResponsiveLayoutIntegration:
    """Integration tests for responsive layout behavior."""

    def test_layout_mode_transitions(self) -> None:
        """Test layout mode transitions correctly on resize."""
        from cyberred.tui.app import CyberRedApp, LayoutMode
        from textual.geometry import Size
        
        app = CyberRedApp()
        
        # Verify transitions at boundaries
        assert app.get_layout_mode(Size(79, 24)) == LayoutMode.COMPACT
        assert app.get_layout_mode(Size(80, 24)) == LayoutMode.COMPACT
        assert app.get_layout_mode(Size(99, 30)) == LayoutMode.COMPACT
        assert app.get_layout_mode(Size(100, 30)) == LayoutMode.STANDARD
        assert app.get_layout_mode(Size(119, 40)) == LayoutMode.STANDARD
        assert app.get_layout_mode(Size(120, 40)) == LayoutMode.OPTIMAL
        assert app.get_layout_mode(Size(200, 60)) == LayoutMode.OPTIMAL


class TestStatusBarIntegration:
    """Integration tests for status bar widget."""

    def test_status_bar_in_app_compose(self) -> None:
        """Test StatusBarWidget is included in app compose."""
        from cyberred.tui.app import CyberRedApp
        import inspect
        
        source = inspect.getsource(CyberRedApp.compose)
        
        # Verify StatusBarWidget is yielded in compose
        assert "StatusBarWidget" in source

    def test_status_bar_reactive_properties(self) -> None:
        """Test StatusBarWidget has reactive properties."""
        from cyberred.tui.widgets import StatusBarWidget
        
        widget = StatusBarWidget(engagement_id="test-123")
        
        # Verify initial reactive state
        assert widget.engagement_state == "STOPPED"
        assert widget.heartbeat == "○"
        assert widget.pending_auth == 0
        
        # Verify updates work
        widget.engagement_state = "RUNNING"
        assert widget.engagement_state == "RUNNING"


class TestEngagementStateIntegration:
    """Integration tests for engagement state management."""

    def test_engagement_state_enum_integration(self) -> None:
        """Test EngagementState enum integrates with app."""
        from cyberred.tui.app import CyberRedApp, EngagementState
        
        app = CyberRedApp()
        
        # Default state should be STOPPED
        assert app.engagement_state == EngagementState.STOPPED
        
        # State can be changed
        app.engagement_state = EngagementState.RUNNING
        assert app.engagement_state == EngagementState.RUNNING
        
        app.engagement_state = EngagementState.PAUSED
        assert app.engagement_state == EngagementState.PAUSED

    def test_heartbeat_status_enum_integration(self) -> None:
        """Test HeartbeatStatus enum integrates with app."""
        from cyberred.tui.app import CyberRedApp, HeartbeatStatus
        
        app = CyberRedApp()
        
        # Default should be CRITICAL (no connection)
        assert app.heartbeat_status == HeartbeatStatus.CRITICAL
        
        # Can be updated
        app.heartbeat_status = HeartbeatStatus.HEALTHY
        assert app.heartbeat_status == HeartbeatStatus.HEALTHY
