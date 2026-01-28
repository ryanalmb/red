"""Integration tests for Drop Box Status Panel.

Story 9.10: Drop Box Status Panel - Task 12

Integration tests verifying:
- Full flow: connect → heartbeat → display update
- Status transitions (healthy → degraded → critical)
- Missed heartbeat warning progression (3 → 6)
- F6 navigation to Drop Box screen
- Real-time updates
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.integration
class TestDropBoxStatusIntegration:
    """Integration tests for Drop Box status flow."""

    def test_full_status_update_flow(self) -> None:
        """Test full flow: status update → display update."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        now = datetime.now(timezone.utc)
        
        # Simulate connected state
        status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now - timedelta(seconds=2),
            uptime_start=now - timedelta(hours=1),
            network_info="192.168.1.100:8443/tcp",
            latency_ms=150,
            missed_heartbeats=0,
        )
        
        panel.update_status(status)
        
        assert panel.connection_status == "Connected"
        assert panel.latency_ms == 150
        assert panel.network_info_display == "192.168.1.100:8443/tcp"

    def test_status_transition_healthy_to_degraded(self) -> None:
        """Test status transition from healthy to degraded."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        now = datetime.now(timezone.utc)
        
        # Start healthy
        healthy_status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now,
            uptime_start=now - timedelta(hours=1),
            network_info="192.168.1.100:8443",
            latency_ms=100,
            missed_heartbeats=0,
        )
        panel.update_status(healthy_status)
        assert healthy_status.is_healthy is True
        
        # Transition to degraded
        degraded_status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now,
            uptime_start=now - timedelta(hours=1),
            network_info="192.168.1.100:8443",
            latency_ms=1000,  # Degraded latency
            missed_heartbeats=0,
        )
        panel.update_status(degraded_status)
        assert degraded_status.is_degraded is True

    def test_status_transition_degraded_to_critical(self) -> None:
        """Test status transition from degraded to critical."""
        from cyberred.tui.widgets.dropbox_status import (
            DropBoxStatusPanel, DropBoxStatus, ConnectionState
        )
        
        panel = DropBoxStatusPanel()
        now = datetime.now(timezone.utc)
        
        # Start degraded
        degraded_status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now,
            uptime_start=now - timedelta(hours=1),
            network_info="192.168.1.100:8443",
            latency_ms=1000,
            missed_heartbeats=0,
        )
        panel.update_status(degraded_status)
        assert degraded_status.is_degraded is True
        
        # Transition to critical
        critical_status = DropBoxStatus(
            connection_state=ConnectionState.CONNECTED,
            last_heartbeat=now,
            uptime_start=now - timedelta(hours=1),
            network_info="192.168.1.100:8443",
            latency_ms=2500,  # Critical latency
            missed_heartbeats=0,
        )
        panel.update_status(critical_status)
        assert critical_status.is_critical is True


@pytest.mark.integration
class TestMissedHeartbeatProgression:
    """Integration tests for missed heartbeat warning progression."""

    def test_missed_heartbeat_warning_at_3(self) -> None:
        """Test warning at 3 missed heartbeats - AC #4."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 100  # Healthy latency
        
        # Miss 3 heartbeats
        for _ in range(3):
            indicator.on_heartbeat_missed()
        
        assert indicator.missed_heartbeats == 3
        assert indicator.compute_css_class() == "heartbeat-warning"
        assert "3 missed heartbeats" in indicator.get_warning_message()

    def test_missed_heartbeat_critical_at_6(self) -> None:
        """Test critical at 6 missed heartbeats - AC #5."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 100  # Healthy latency
        
        # Miss 6 heartbeats
        for _ in range(6):
            indicator.on_heartbeat_missed()
        
        assert indicator.missed_heartbeats == 6
        assert indicator.compute_css_class() == "heartbeat-critical"
        assert "6 missed heartbeats" in indicator.get_warning_message()
        assert "critical" in indicator.get_warning_message().lower()

    def test_heartbeat_resets_missed_counter(self) -> None:
        """Test successful heartbeat resets missed counter."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        
        # Miss some heartbeats
        for _ in range(5):
            indicator.on_heartbeat_missed()
        assert indicator.missed_heartbeats == 5
        
        # Receive successful heartbeat
        indicator.on_heartbeat(100)
        
        assert indicator.missed_heartbeats == 0
        assert indicator.latency_ms == 100
        assert indicator.compute_css_class() == "heartbeat-healthy"


@pytest.mark.integration
class TestDropBoxScreenNavigation:
    """Integration tests for Drop Box screen navigation."""

    def test_dropbox_screen_creation(self) -> None:
        """Test DropBoxScreen can be created and composed."""
        from cyberred.tui.screens.dropbox import DropBoxScreen
        from cyberred.tui.widgets.dropbox_status import DropBoxStatusPanel
        
        screen = DropBoxScreen()
        widgets = list(screen.compose())
        
        # Verify DropBoxStatusPanel is in composition
        panel_widgets = [w for w in widgets if isinstance(w, DropBoxStatusPanel)]
        assert len(panel_widgets) == 1

    def test_f6_keybinding_defined_in_app(self) -> None:
        """Test F6 keybinding is defined for drop box screen - AC #6."""
        from cyberred.tui.app import CyberRedApp
        
        bindings = {b[0] if isinstance(b, tuple) else b.key: b for b in CyberRedApp.BINDINGS}
        assert "f6" in bindings
        
        f6_binding = bindings["f6"]
        if isinstance(f6_binding, tuple):
            assert "dropbox" in f6_binding[1].lower() or "show_dropbox" in f6_binding[1]

    def test_action_show_dropbox_method_exists(self) -> None:
        """Test action_show_dropbox method exists in CyberRedApp."""
        from cyberred.tui.app import CyberRedApp
        
        assert hasattr(CyberRedApp, "action_show_dropbox")


@pytest.mark.integration
class TestHeartbeatIndicatorStates:
    """Integration tests for HeartbeatIndicator state rendering."""

    def test_all_indicator_states(self) -> None:
        """Test all indicator states render correctly."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        
        # Test healthy state
        indicator.latency_ms = 100
        indicator.missed_heartbeats = 0
        assert indicator.compute_indicator() == "●"
        assert indicator.compute_css_class() == "heartbeat-healthy"
        
        # Test degraded state
        indicator.latency_ms = 1000
        indicator.missed_heartbeats = 0
        assert indicator.compute_indicator() == "◐"
        assert indicator.compute_css_class() == "heartbeat-degraded"
        
        # Test critical state
        indicator.latency_ms = 2500
        indicator.missed_heartbeats = 0
        assert indicator.compute_indicator() == "○"
        assert indicator.compute_css_class() == "heartbeat-critical"
        
        # Test unknown state
        indicator.latency_ms = None
        indicator.missed_heartbeats = 0
        assert indicator.compute_indicator() == "○"
        assert indicator.compute_css_class() == "heartbeat-unknown"

    def test_indicator_render_output(self) -> None:
        """Test indicator render produces expected output."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        
        # Test with latency
        indicator.latency_ms = 250
        indicator.missed_heartbeats = 0
        rendered = indicator.render()
        assert "●" in str(rendered)
        assert "250ms" in str(rendered)
        
        # Test with warning
        indicator.missed_heartbeats = 3
        rendered = indicator.render()
        assert "3 missed heartbeats" in str(rendered)
