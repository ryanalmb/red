"""Unit tests for HeartbeatIndicator widget.

Story 9.10: Drop Box Status Panel - Task 9

Tests for HeartbeatIndicator widget which displays C2 heartbeat status:
- Healthy state (● indicator, <500ms latency)
- Degraded state (◐ indicator, 500-2000ms latency)
- Critical state (○ indicator, >2000ms latency)
- Missed heartbeat tracking (3 = yellow warning, 6 = red warning)
- Heartbeat counter reset on successful heartbeat
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


class TestHeartbeatIndicatorInit:
    """Tests for HeartbeatIndicator initialization."""

    def test_import(self) -> None:
        """Test HeartbeatIndicator can be imported."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        assert HeartbeatIndicator is not None

    def test_default_state(self) -> None:
        """Test HeartbeatIndicator initializes with default state."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        assert indicator.latency_ms is None
        assert indicator.missed_heartbeats == 0

    def test_thresholds_defined(self) -> None:
        """Test threshold constants are defined."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        assert HeartbeatIndicator.HEALTHY_THRESHOLD_MS == 500
        assert HeartbeatIndicator.DEGRADED_THRESHOLD_MS == 2000


class TestHeartbeatIndicatorHealthyState:
    """Tests for healthy state (● indicator, <500ms latency) - AC #2."""

    def test_healthy_indicator_symbol(self) -> None:
        """Test healthy state shows ● indicator when latency <500ms."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 100
        
        assert indicator.compute_indicator() == "●"

    def test_healthy_indicator_at_zero_latency(self) -> None:
        """Test healthy state at 0ms latency."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 0
        
        assert indicator.compute_indicator() == "●"

    def test_healthy_indicator_at_499ms(self) -> None:
        """Test healthy state at boundary (499ms)."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 499
        
        assert indicator.compute_indicator() == "●"

    def test_healthy_css_class(self) -> None:
        """Test healthy state returns correct CSS class."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 100
        
        assert indicator.compute_css_class() == "heartbeat-healthy"


class TestHeartbeatIndicatorDegradedState:
    """Tests for degraded state (◐ indicator, 500-2000ms latency) - AC #3."""

    def test_degraded_indicator_symbol(self) -> None:
        """Test degraded state shows ◐ indicator when latency 500-2000ms."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 1000
        
        assert indicator.compute_indicator() == "◐"

    def test_degraded_indicator_at_500ms(self) -> None:
        """Test degraded state at boundary (500ms)."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 500
        
        assert indicator.compute_indicator() == "◐"

    def test_degraded_indicator_at_1999ms(self) -> None:
        """Test degraded state at upper boundary (1999ms)."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 1999
        
        assert indicator.compute_indicator() == "◐"

    def test_degraded_css_class(self) -> None:
        """Test degraded state returns correct CSS class."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 1000
        
        assert indicator.compute_css_class() == "heartbeat-degraded"


class TestHeartbeatIndicatorCriticalState:
    """Tests for critical state (○ indicator, >2000ms latency) - AC #3, #5."""

    def test_critical_indicator_symbol(self) -> None:
        """Test critical state shows ○ indicator when latency >=2000ms."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 2500
        
        assert indicator.compute_indicator() == "○"

    def test_critical_indicator_at_2000ms(self) -> None:
        """Test critical state at boundary (2000ms)."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 2000
        
        assert indicator.compute_indicator() == "○"

    def test_critical_css_class(self) -> None:
        """Test critical state returns correct CSS class."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 2500
        
        assert indicator.compute_css_class() == "heartbeat-critical"

    def test_unknown_indicator_when_no_latency(self) -> None:
        """Test unknown state (○) when latency is None."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = None
        
        assert indicator.compute_indicator() == "○"

    def test_unknown_css_class_when_no_latency(self) -> None:
        """Test unknown CSS class when latency is None."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = None
        
        assert indicator.compute_css_class() == "heartbeat-unknown"


class TestHeartbeatIndicatorMissedHeartbeats:
    """Tests for missed heartbeat tracking - AC #4, #5."""

    def test_missed_heartbeat_increment(self) -> None:
        """Test on_heartbeat_missed increments counter."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        assert indicator.missed_heartbeats == 0
        
        indicator.on_heartbeat_missed()
        assert indicator.missed_heartbeats == 1
        
        indicator.on_heartbeat_missed()
        assert indicator.missed_heartbeats == 2

    def test_three_missed_heartbeats_yellow_warning(self) -> None:
        """Test 3 missed heartbeats shows yellow warning - AC #4."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 100  # Otherwise healthy
        
        for _ in range(3):
            indicator.on_heartbeat_missed()
        
        assert indicator.missed_heartbeats == 3
        assert indicator.compute_css_class() == "heartbeat-warning"

    def test_five_missed_heartbeats_still_yellow(self) -> None:
        """Test 5 missed heartbeats still shows yellow warning."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 100
        
        for _ in range(5):
            indicator.on_heartbeat_missed()
        
        assert indicator.missed_heartbeats == 5
        assert indicator.compute_css_class() == "heartbeat-warning"

    def test_six_missed_heartbeats_red_critical(self) -> None:
        """Test 6 missed heartbeats shows red critical - AC #5."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 100  # Otherwise healthy
        
        for _ in range(6):
            indicator.on_heartbeat_missed()
        
        assert indicator.missed_heartbeats == 6
        assert indicator.compute_css_class() == "heartbeat-critical"

    def test_seven_missed_heartbeats_still_critical(self) -> None:
        """Test 7+ missed heartbeats still shows critical."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 100
        
        for _ in range(7):
            indicator.on_heartbeat_missed()
        
        assert indicator.missed_heartbeats == 7
        assert indicator.compute_css_class() == "heartbeat-critical"

    def test_missed_heartbeats_take_precedence_over_latency(self) -> None:
        """Test missed heartbeats override healthy latency status."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 50  # Very healthy latency
        indicator.missed_heartbeats = 6  # But critical missed count
        
        assert indicator.compute_css_class() == "heartbeat-critical"


class TestHeartbeatIndicatorOnHeartbeat:
    """Tests for on_heartbeat handler - AC #2."""

    def test_on_heartbeat_updates_latency(self) -> None:
        """Test on_heartbeat sets latency_ms."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.on_heartbeat(250)
        
        assert indicator.latency_ms == 250

    def test_on_heartbeat_resets_missed_counter(self) -> None:
        """Test on_heartbeat resets missed_heartbeats to 0 - AC #2."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.missed_heartbeats = 5  # Simulate 5 missed
        
        indicator.on_heartbeat(100)
        
        assert indicator.missed_heartbeats == 0
        assert indicator.latency_ms == 100

    def test_on_heartbeat_clears_warning_state(self) -> None:
        """Test successful heartbeat clears warning state."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        
        # Simulate 5 missed heartbeats (warning state)
        for _ in range(5):
            indicator.on_heartbeat_missed()
        assert indicator.compute_css_class() == "heartbeat-warning"
        
        # Successful heartbeat should clear warning
        indicator.on_heartbeat(100)
        assert indicator.compute_css_class() == "heartbeat-healthy"


class TestHeartbeatIndicatorWarningMessage:
    """Tests for warning message generation - AC #4, #5."""

    def test_warning_message_at_3_missed(self) -> None:
        """Test warning message shows '3 missed heartbeats' - AC #4."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.missed_heartbeats = 3
        
        message = indicator.get_warning_message()
        assert "3 missed heartbeats" in message

    def test_warning_message_at_6_missed(self) -> None:
        """Test warning message shows '6 missed heartbeats - connection critical' - AC #5."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.missed_heartbeats = 6
        
        message = indicator.get_warning_message()
        assert "6 missed heartbeats" in message
        assert "critical" in message.lower()

    def test_no_warning_message_when_healthy(self) -> None:
        """Test no warning message when heartbeats are healthy."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.missed_heartbeats = 2  # Below warning threshold
        
        message = indicator.get_warning_message()
        assert message is None or message == ""


class TestHeartbeatIndicatorRender:
    """Tests for render method."""

    def test_render_includes_indicator_symbol(self) -> None:
        """Test render includes the indicator symbol."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 100
        
        rendered = indicator.render()
        assert "●" in str(rendered)

    def test_render_shows_dashes_when_no_latency(self) -> None:
        """Test render shows '---' when latency is None."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = None
        
        rendered = indicator.render()
        assert "---" in str(rendered)

    def test_render_includes_warning_message(self) -> None:
        """Test render includes warning message when missed heartbeats >= 3."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 100
        indicator.missed_heartbeats = 3
        
        rendered = indicator.render()
        assert "3 missed heartbeats" in str(rendered)

    def test_render_includes_latency_display(self) -> None:
        """Test render includes latency value when available."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 250
        
        rendered = indicator.render()
        assert "250" in str(rendered) or "ms" in str(rendered).lower()

    def test_render_degraded_indicator(self) -> None:
        """Test render shows degraded indicator."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 1000
        
        rendered = indicator.render()
        assert "◐" in str(rendered)

    def test_render_critical_indicator(self) -> None:
        """Test render shows critical indicator."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        indicator = HeartbeatIndicator()
        indicator.latency_ms = 3000
        
        rendered = indicator.render()
        assert "○" in str(rendered)


class TestHeartbeatIndicatorConstants:
    """Tests for HeartbeatIndicator constants per UX spec."""

    def test_healthy_threshold_per_spec(self) -> None:
        """Test healthy threshold is 500ms per UX spec line 360."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        assert HeartbeatIndicator.HEALTHY_THRESHOLD_MS == 500

    def test_degraded_threshold_per_spec(self) -> None:
        """Test degraded threshold is 2000ms per UX spec."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        assert HeartbeatIndicator.DEGRADED_THRESHOLD_MS == 2000

    def test_warning_missed_count(self) -> None:
        """Test warning shows at 3 missed heartbeats per AC #4."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        assert HeartbeatIndicator.WARNING_MISSED_COUNT == 3

    def test_critical_missed_count(self) -> None:
        """Test critical shows at 6 missed heartbeats per AC #5."""
        from cyberred.tui.widgets.heartbeat_indicator import HeartbeatIndicator
        
        assert HeartbeatIndicator.CRITICAL_MISSED_COUNT == 6
