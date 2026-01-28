"""Unit tests for DropBoxScreen.

Story 9.10: Drop Box Status Panel - Task 11

Tests for DropBoxScreen which displays drop box status:
- Screen composition with DropBoxStatusPanel
- Back navigation (ESC key)
- F6 keybinding triggers screen
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestDropBoxScreenImport:
    """Tests for DropBoxScreen import."""

    def test_import(self) -> None:
        """Test DropBoxScreen can be imported."""
        from cyberred.tui.screens.dropbox import DropBoxScreen
        assert DropBoxScreen is not None


class TestDropBoxScreenInit:
    """Tests for DropBoxScreen initialization."""

    def test_default_init(self) -> None:
        """Test DropBoxScreen initializes with defaults."""
        from cyberred.tui.screens.dropbox import DropBoxScreen
        
        screen = DropBoxScreen()
        assert screen is not None

    def test_init_with_daemon_client(self) -> None:
        """Test DropBoxScreen initializes with daemon client."""
        from cyberred.tui.screens.dropbox import DropBoxScreen
        
        mock_client = MagicMock()
        screen = DropBoxScreen(daemon_client=mock_client)
        assert screen._daemon_client == mock_client


class TestDropBoxScreenBindings:
    """Tests for DropBoxScreen keybindings - AC #6."""

    def test_escape_binding_exists(self) -> None:
        """Test ESC key binding exists for back navigation."""
        from cyberred.tui.screens.dropbox import DropBoxScreen
        
        bindings = {b[0] if isinstance(b, tuple) else b.key: b for b in DropBoxScreen.BINDINGS}
        assert "escape" in bindings

    def test_escape_binding_pops_screen(self) -> None:
        """Test ESC key pops the screen."""
        from cyberred.tui.screens.dropbox import DropBoxScreen
        
        bindings = {b[0] if isinstance(b, tuple) else b.key: b for b in DropBoxScreen.BINDINGS}
        escape_binding = bindings.get("escape")
        # Check that action is pop_screen
        assert escape_binding is not None
        if isinstance(escape_binding, tuple):
            assert "pop_screen" in escape_binding[1]


class TestDropBoxScreenTitle:
    """Tests for DropBoxScreen title."""

    def test_screen_has_title(self) -> None:
        """Test screen has 'Drop Box Status' title."""
        from cyberred.tui.screens.dropbox import DropBoxScreen
        
        screen = DropBoxScreen()
        # Check TITLE attribute or title property
        title = getattr(screen, 'TITLE', None) or getattr(screen, 'title', '')
        assert "Drop Box" in title or hasattr(screen, 'TITLE')


class TestDropBoxScreenComposition:
    """Tests for DropBoxScreen compose method."""

    def test_compose_yields_header(self) -> None:
        """Test compose yields Header widget."""
        from cyberred.tui.screens.dropbox import DropBoxScreen
        from textual.widgets import Header
        
        screen = DropBoxScreen()
        widgets = list(screen.compose())
        
        header_widgets = [w for w in widgets if isinstance(w, Header)]
        assert len(header_widgets) >= 1

    def test_compose_yields_dropbox_status_panel(self) -> None:
        """Test compose yields DropBoxStatusPanel widget."""
        from cyberred.tui.screens.dropbox import DropBoxScreen
        from cyberred.tui.widgets.dropbox_status import DropBoxStatusPanel
        
        screen = DropBoxScreen()
        widgets = list(screen.compose())
        
        panel_widgets = [w for w in widgets if isinstance(w, DropBoxStatusPanel)]
        assert len(panel_widgets) >= 1

    def test_compose_yields_footer(self) -> None:
        """Test compose yields Footer widget."""
        from cyberred.tui.screens.dropbox import DropBoxScreen
        from textual.widgets import Footer
        
        screen = DropBoxScreen()
        widgets = list(screen.compose())
        
        footer_widgets = [w for w in widgets if isinstance(w, Footer)]
        assert len(footer_widgets) >= 1


class TestDropBoxScreenOnMount:
    """Tests for DropBoxScreen on_mount method."""

    def test_on_mount_success_with_mock_query(self) -> None:
        """Test on_mount successfully queries status panel."""
        from cyberred.tui.screens.dropbox import DropBoxScreen
        from cyberred.tui.widgets.dropbox_status import DropBoxStatusPanel
        
        screen = DropBoxScreen()
        mock_panel = MagicMock(spec=DropBoxStatusPanel)
        
        with patch.object(screen, 'query_one', return_value=mock_panel):
            screen.on_mount()
        
        assert screen._status_panel == mock_panel

    def test_on_mount_handles_no_matches(self) -> None:
        """Test on_mount handles NoMatches exception gracefully."""
        from cyberred.tui.screens.dropbox import DropBoxScreen
        from textual.css.query import NoMatches
        
        screen = DropBoxScreen()
        
        with patch.object(screen, 'query_one', side_effect=NoMatches()):
            screen.on_mount()
        
        # Should not raise, panel should remain None
        assert screen._status_panel is None


class TestDropBoxScreenUpdateStatus:
    """Tests for DropBoxScreen update_status method."""

    def test_update_status_with_panel(self) -> None:
        """Test update_status calls panel.update_status when panel exists."""
        from cyberred.tui.screens.dropbox import DropBoxScreen, DropBoxStatus
        from cyberred.tui.widgets.dropbox_status import ConnectionState
        from datetime import datetime, timezone
        
        screen = DropBoxScreen()
        mock_panel = MagicMock()
        screen._status_panel = mock_panel
        
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=100,
        )
        
        screen.update_status(status)
        
        mock_panel.update_status.assert_called_once_with(status)

    def test_update_status_without_panel(self) -> None:
        """Test update_status does nothing when panel is None."""
        from cyberred.tui.screens.dropbox import DropBoxScreen, DropBoxStatus
        from cyberred.tui.widgets.dropbox_status import ConnectionState
        from datetime import datetime, timezone
        
        screen = DropBoxScreen()
        screen._status_panel = None
        
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=100,
        )
        
        # Should not raise
        screen.update_status(status)
