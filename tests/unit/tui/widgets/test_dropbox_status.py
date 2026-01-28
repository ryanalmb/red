"""Unit tests for DropBoxStatusPanel widget.

Story 9.10: Drop Box Status Panel - Task 10

Tests for DropBoxStatusPanel widget which displays drop box status:
- Connection status (Connected/Disconnected/Reconnecting)
- Last heartbeat timestamp formatting
- Uptime duration formatting
- Network info display
- Status update handler
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone


class TestDropBoxStatusModel:
    """Tests for DropBoxStatus data model - Task 5."""

    def test_import_connection_state(self) -> None:
        """Test ConnectionState enum can be imported."""
        from cyberred.tui.widgets.dropbox_status import ConnectionState
        assert ConnectionState is not None

    def test_connection_state_values(self) -> None:
        """Test ConnectionState has required values."""
        from cyberred.tui.widgets.dropbox_status import ConnectionState
        
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.RECONNECTING.value == "reconnecting"
        assert ConnectionState.UNKNOWN.value == "unknown"

    def test_import_dropbox_status(self) -> None:
        """Test DropBoxStatus dataclass can be imported."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatus
        assert DropBoxStatus is not None

    def test_dropbox_status_creation(self) -> None:
        """Test DropBoxStatus can be created with all fields."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatus, ConnectionState
        
        now = datetime.now(timezone.utc)
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now,
            uptime_start=now - timedelta(hours=1),
            network_info="192.168.1.100:8443/tcp",
            latency_ms=100,
            missed_heartbeats=0,
        )
        
        assert status.connection_state == ConnectionState.CONNECTED
        assert status.last_heartbeat == now
        assert status.latency_ms == 100
        assert status.missed_heartbeats == 0

    def test_dropbox_status_default_missed_heartbeats(self) -> None:
        """Test DropBoxStatus has default missed_heartbeats=0."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatus, ConnectionState
        
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=None,
            uptime_start=None,
            network_info=None,
            latency_ms=None,
        )
        
        assert status.missed_heartbeats == 0


class TestDropBoxStatusHealthChecks:
    """Tests for DropBoxStatus health check properties - Task 5."""

    def test_is_healthy_true(self) -> None:
        """Test is_healthy returns True when connected with good latency."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatus, ConnectionState
        
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=100,
            missed_heartbeats=0,
        )
        
        assert status.is_healthy is True

    def test_is_healthy_false_disconnected(self) -> None:
        """Test is_healthy returns False when disconnected."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatus, ConnectionState
        
        status = DropBoxStatus(
            connection_state=ConnectionState.DISCONNECTED,
            last_heartbeat=None,
            uptime_start=None,
            network_info=None,
            latency_ms=None,
        )
        
        assert status.is_healthy is False

    def test_is_healthy_false_high_latency(self) -> None:
        """Test is_healthy returns False when latency >= 500ms."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatus, ConnectionState
        
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=500,
            missed_heartbeats=0,
        )
        
        assert status.is_healthy is False

    def test_is_healthy_false_missed_heartbeats(self) -> None:
        """Test is_healthy returns False when 3+ missed heartbeats."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatus, ConnectionState
        
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=100,
            missed_heartbeats=3,
        )
        
        assert status.is_healthy is False

    def test_is_degraded_latency(self) -> None:
        """Test is_degraded returns True for 500-2000ms latency."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatus, ConnectionState
        
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=1000,
            missed_heartbeats=0,
        )
        
        assert status.is_degraded is True

    def test_is_degraded_missed_heartbeats(self) -> None:
        """Test is_degraded returns True for 3-5 missed heartbeats."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatus, ConnectionState
        
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=100,
            missed_heartbeats=4,
        )
        
        assert status.is_degraded is True

    def test_is_critical_disconnected(self) -> None:
        """Test is_critical returns True when disconnected."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatus, ConnectionState
        
        status = DropBoxStatus(
            connection_state=ConnectionState.DISCONNECTED,
            last_heartbeat=None,
            uptime_start=None,
            network_info=None,
            latency_ms=None,
        )
        
        assert status.is_critical is True

    def test_is_critical_high_latency(self) -> None:
        """Test is_critical returns True for latency >= 2000ms."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatus, ConnectionState
        
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=2500,
            missed_heartbeats=0,
        )
        
        assert status.is_critical is True

    def test_is_critical_missed_heartbeats(self) -> None:
        """Test is_critical returns True for 6+ missed heartbeats."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatus, ConnectionState
        
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=100,
            missed_heartbeats=6,
        )
        
        assert status.is_critical is True


class TestDropBoxStatusPanelInit:
    """Tests for DropBoxStatusPanel initialization."""

    def test_import(self) -> None:
        """Test DropBoxStatusPanel can be imported."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatusPanel
        assert DropBoxStatusPanel is not None

    def test_default_state(self) -> None:
        """Test DropBoxStatusPanel initializes with default state."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatusPanel
        
        panel = DropBoxStatusPanel()
        assert panel is not None


class TestDropBoxStatusPanelConnectionStatus:
    """Tests for connection status display - AC #1."""

    def test_display_connected_status(self) -> None:
        """Test panel displays 'Connected' status."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=100,
        )
        
        panel.update_status(status)
        assert panel.connection_status == "Connected"

    def test_display_disconnected_status(self) -> None:
        """Test panel displays 'Disconnected' status."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        status = DropBoxStatus(
            connection_state=ConnectionState.DISCONNECTED,
            last_heartbeat=None,
            uptime_start=None,
            network_info=None,
            latency_ms=None,
        )
        
        panel.update_status(status)
        assert panel.connection_status == "Disconnected"

    def test_display_reconnecting_status(self) -> None:
        """Test panel displays 'Reconnecting' status."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        status = DropBoxStatus(
            connection_state=ConnectionState.RECONNECTING,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=None,
        )
        
        panel.update_status(status)
        assert panel.connection_status == "Reconnecting"


class TestDropBoxStatusPanelLastHeartbeat:
    """Tests for last heartbeat timestamp formatting - AC #1."""

    def test_format_relative_time_seconds(self) -> None:
        """Test last heartbeat shows relative time in seconds."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        now = datetime.now(timezone.utc)
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now - timedelta(seconds=3),
            uptime_start=now,
            network_info="192.168.1.100:8443",
            latency_ms=100,
        )
        
        panel.update_status(status)
        # Should show "3s ago" or similar
        assert "s ago" in panel.last_heartbeat_display or "3s" in panel.last_heartbeat_display

    def test_format_relative_time_minutes(self) -> None:
        """Test last heartbeat shows relative time in minutes."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        now = datetime.now(timezone.utc)
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now - timedelta(minutes=5),
            uptime_start=now,
            network_info="192.168.1.100:8443",
            latency_ms=100,
        )
        
        panel.update_status(status)
        # Should show "5m ago" or similar
        assert "m ago" in panel.last_heartbeat_display or "5m" in panel.last_heartbeat_display

    def test_format_no_heartbeat(self) -> None:
        """Test last heartbeat shows 'Never' when None."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        status = DropBoxStatus(
            connection_state=ConnectionState.DISCONNECTED,
            last_heartbeat=None,
            uptime_start=None,
            network_info=None,
            latency_ms=None,
        )
        
        panel.update_status(status)
        assert panel.last_heartbeat_display == "Never"


class TestDropBoxStatusPanelUptime:
    """Tests for uptime duration formatting - AC #1."""

    def test_format_uptime_hours_minutes_seconds(self) -> None:
        """Test uptime shows HH:MM:SS format."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        now = datetime.now(timezone.utc)
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now,
            uptime_start=now - timedelta(hours=2, minutes=30, seconds=45),
            network_info="192.168.1.100:8443",
            latency_ms=100,
        )
        
        panel.update_status(status)
        # Should show "2:30:45" or "02:30:45"
        assert "2" in panel.uptime_display and "30" in panel.uptime_display

    def test_format_uptime_days(self) -> None:
        """Test uptime shows days format for longer durations."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        now = datetime.now(timezone.utc)
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now,
            uptime_start=now - timedelta(days=2, hours=5),
            network_info="192.168.1.100:8443",
            latency_ms=100,
        )
        
        panel.update_status(status)
        # Should show "2d 5h" or similar
        assert "d" in panel.uptime_display or "day" in panel.uptime_display.lower()

    def test_format_uptime_none(self) -> None:
        """Test uptime shows '---' when uptime_start is None."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        status = DropBoxStatus(
            connection_state=ConnectionState.DISCONNECTED,
            last_heartbeat=None,
            uptime_start=None,
            network_info=None,
            latency_ms=None,
        )
        
        panel.update_status(status)
        assert panel.uptime_display == "---"


class TestDropBoxStatusPanelNetworkInfo:
    """Tests for network info display - AC #1."""

    def test_display_network_info(self) -> None:
        """Test panel displays network info."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443/tcp",
            latency_ms=100,
        )
        
        panel.update_status(status)
        assert panel.network_info_display == "192.168.1.100:8443/tcp"

    def test_display_network_info_none(self) -> None:
        """Test panel shows '---' when network_info is None."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        status = DropBoxStatus(
            connection_state=ConnectionState.DISCONNECTED,
            last_heartbeat=None,
            uptime_start=None,
            network_info=None,
            latency_ms=None,
        )
        
        panel.update_status(status)
        assert panel.network_info_display == "---"


class TestDropBoxStatusPanelUpdateHandler:
    """Tests for status update handler - AC #1."""

    def test_update_status_updates_all_fields(self) -> None:
        """Test update_status updates all display fields."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        now = datetime.now(timezone.utc)
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now - timedelta(seconds=5),
            uptime_start=now - timedelta(hours=1),
            network_info="192.168.1.100:8443",
            latency_ms=150,
        )
        
        panel.update_status(status)
        
        assert panel.connection_status == "Connected"
        assert panel.network_info_display == "192.168.1.100:8443"
        assert panel.latency_ms == 150

    def test_update_status_updates_heartbeat_indicator(self) -> None:
        """Test update_status updates HeartbeatIndicator widget."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        now = datetime.now(timezone.utc)
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now,
            uptime_start=now,
            network_info="192.168.1.100:8443",
            latency_ms=100,
            missed_heartbeats=0,
        )
        
        panel.update_status(status)
        
        # Verify heartbeat indicator was updated
        assert panel.latency_ms == 100


class TestDropBoxStatusPanelConnectionLoss:
    """Tests for connection loss handling - AC #1."""

    def test_handle_connection_loss_gracefully(self) -> None:
        """Test panel shows 'Unknown' status on connection loss."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        status = DropBoxStatus(
            connection_state=ConnectionState.UNKNOWN,
            last_heartbeat=None,
            uptime_start=None,
            network_info=None,
            latency_ms=None,
        )
        
        panel.update_status(status)
        assert panel.connection_status == "Unknown"


class TestDropBoxStatusDegradedEdgeCases:
    """Tests for edge cases in is_degraded property."""

    def test_is_degraded_false_when_disconnected(self) -> None:
        """Test is_degraded returns False when not connected."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatus, ConnectionState
        
        status = DropBoxStatus(
            connection_state=ConnectionState.DISCONNECTED,
            last_heartbeat=None,
            uptime_start=None,
            network_info=None,
            latency_ms=1000,  # Would be degraded if connected
            missed_heartbeats=0,
        )
        
        assert status.is_degraded is False

    def test_is_degraded_false_when_healthy(self) -> None:
        """Test is_degraded returns False when healthy."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatus, ConnectionState
        
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=100,  # Healthy
            missed_heartbeats=0,
        )
        
        assert status.is_degraded is False


class TestDropBoxStatusPanelRelativeTimeEdgeCases:
    """Tests for edge cases in relative time formatting."""

    def test_format_relative_time_hours(self) -> None:
        """Test relative time formatting for hours."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        now = datetime.now(timezone.utc)
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now - timedelta(hours=2),
            uptime_start=now,
            network_info="192.168.1.100:8443",
            latency_ms=100,
        )
        
        panel.update_status(status)
        assert "h ago" in panel.last_heartbeat_display or "2h" in panel.last_heartbeat_display

    def test_format_relative_time_days(self) -> None:
        """Test relative time formatting for days."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        now = datetime.now(timezone.utc)
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now - timedelta(days=3),
            uptime_start=now,
            network_info="192.168.1.100:8443",
            latency_ms=100,
        )
        
        panel.update_status(status)
        assert "d ago" in panel.last_heartbeat_display or "3d" in panel.last_heartbeat_display

    def test_format_relative_time_naive_datetime(self) -> None:
        """Test relative time formatting with naive datetime (no timezone)."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        now = datetime.now()  # Naive datetime (no timezone)
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now - timedelta(seconds=10),
            uptime_start=now,
            network_info="192.168.1.100:8443",
            latency_ms=100,
        )
        
        panel.update_status(status)
        # Should still work with naive datetime
        assert "s ago" in panel.last_heartbeat_display or "ago" in panel.last_heartbeat_display


class TestDropBoxStatusPanelDurationEdgeCases:
    """Tests for edge cases in duration formatting."""

    def test_format_duration_naive_datetime(self) -> None:
        """Test duration formatting with naive datetime (no timezone)."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        now = datetime.now()  # Naive datetime (no timezone)
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now,
            uptime_start=now - timedelta(hours=1, minutes=30),
            network_info="192.168.1.100:8443",
            latency_ms=100,
        )
        
        panel.update_status(status)
        # Should still work with naive datetime
        assert "1:" in panel.uptime_display or "30" in panel.uptime_display


class TestDropBoxStatusPanelHeartbeatUpdate:
    """Tests for heartbeat indicator update edge cases."""

    def test_update_status_with_none_latency(self) -> None:
        """Test update_status handles None latency correctly."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        status = DropBoxStatus(
            connection_state=ConnectionState.RECONNECTING,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=None,  # No latency data
            missed_heartbeats=2,
        )
        
        panel.update_status(status)
        assert panel.latency_ms is None
        assert panel.connection_status == "Reconnecting"


class TestDropBoxStatusPanelCompose:
    """Tests for DropBoxStatusPanel compose method."""

    def test_compose_yields_widgets(self) -> None:
        """Test compose yields expected widgets."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatusPanel
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        from textual.widgets import Static
        
        panel = DropBoxStatusPanel()
        widgets = list(panel.compose())
        
        # Should yield 6 widgets: title, connection-status, heartbeat, last-heartbeat, uptime, network-info
        assert len(widgets) == 6
        
        # First should be panel title
        assert isinstance(widgets[0], Static)
        
        # Should include HeartbeatIndicator
        heartbeat_widgets = [w for w in widgets if isinstance(w, HeartbeatIndicator)]
        assert len(heartbeat_widgets) == 1


class TestDropBoxStatusPanelOnMount:
    """Tests for DropBoxStatusPanel on_mount method."""

    def test_on_mount_calls_update_display(self) -> None:
        """Test on_mount calls _update_display."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatusPanel
        
        panel = DropBoxStatusPanel()
        
        with patch.object(panel, '_update_display') as mock_update:
            panel.on_mount()
            mock_update.assert_called_once()


class TestDropBoxStatusPanelUpdateHeartbeatIndicatorException:
    """Tests for _update_heartbeat_indicator exception handling."""

    def test_update_heartbeat_indicator_handles_no_matches(self) -> None:
        """Test _update_heartbeat_indicator handles NoMatches gracefully."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        from textual.css.query import NoMatches
        
        panel = DropBoxStatusPanel()
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=100,
            missed_heartbeats=0,
        )
        
        with patch.object(panel, 'query_one', side_effect=NoMatches()):
            # Should not raise
            panel._update_heartbeat_indicator(status)

    def test_update_heartbeat_indicator_success_with_latency(self) -> None:
        """Test _update_heartbeat_indicator successfully updates widget with latency."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        panel = DropBoxStatusPanel()
        mock_heartbeat = MagicMock(spec=HeartbeatIndicator)
        
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=150,
            missed_heartbeats=2,
        )
        
        with patch.object(panel, 'query_one', return_value=mock_heartbeat):
            panel._update_heartbeat_indicator(status)
        
        mock_heartbeat.on_heartbeat.assert_called_once_with(150)
        assert mock_heartbeat.missed_heartbeats == 2

    def test_update_heartbeat_indicator_success_without_latency(self) -> None:
        """Test _update_heartbeat_indicator with None latency skips on_heartbeat."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        panel = DropBoxStatusPanel()
        mock_heartbeat = MagicMock(spec=HeartbeatIndicator)
        
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=datetime.now(timezone.utc),
            uptime_start=datetime.now(timezone.utc),
            network_info="192.168.1.100:8443",
            latency_ms=None,  # No latency
            missed_heartbeats=3,
        )
        
        with patch.object(panel, 'query_one', return_value=mock_heartbeat):
            panel._update_heartbeat_indicator(status)
        
        # on_heartbeat should NOT be called when latency is None
        mock_heartbeat.on_heartbeat.assert_not_called()
        assert mock_heartbeat.missed_heartbeats == 3


class TestDropBoxStatusPanelUpdateDisplayException:
    """Tests for _update_display exception handling."""

    def test_update_display_handles_no_matches(self) -> None:
        """Test _update_display handles NoMatches gracefully."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatusPanel
        from textual.css.query import NoMatches
        
        panel = DropBoxStatusPanel()
        
        with patch.object(panel, 'query_one', side_effect=NoMatches()):
            # Should not raise
            panel._update_display()

    def test_update_display_success(self) -> None:
        """Test _update_display successfully updates all widgets."""
        from cyberred.tui.widgets.dropbox_status import DropBoxStatusPanel
        from textual.widgets import Static
        
        panel = DropBoxStatusPanel()
        panel.connection_status = "Connected"
        panel.last_heartbeat_display = "5s ago"
        panel.uptime_display = "1:30:00"
        panel.network_info_display = "192.168.1.100:8443"
        
        mock_widgets = {
            "#connection-status": MagicMock(spec=Static),
            "#last-heartbeat": MagicMock(spec=Static),
            "#uptime": MagicMock(spec=Static),
            "#network-info": MagicMock(spec=Static),
        }
        
        def mock_query_one(selector, widget_type):
            return mock_widgets[selector]
        
        with patch.object(panel, 'query_one', side_effect=mock_query_one):
            panel._update_display()
        
        mock_widgets["#connection-status"].update.assert_called_once_with("Status: Connected")
        mock_widgets["#last-heartbeat"].update.assert_called_once_with("Last Heartbeat: 5s ago")
        mock_widgets["#uptime"].update.assert_called_once_with("Uptime: 1:30:00")
        mock_widgets["#network-info"].update.assert_called_once_with("Network: 192.168.1.100:8443")
