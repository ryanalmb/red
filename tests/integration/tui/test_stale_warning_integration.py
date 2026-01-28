"""Integration tests for stale state warning display (Story 9.7).

Tests cover:
- Stale indicator appears after 60s inactivity
- Stale indicator disappears when event received
- Refresh action clears stale state
- Stale warning display format in TUI

AC #9: Integration tests verify stale state warning display.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cyberred.tui.widgets.stale_indicator import StaleStateIndicator


class TestStaleIndicatorIntegration:
    """Integration tests for StaleStateIndicator widget."""

    def test_stale_indicator_initial_state(self):
        """Test indicator starts hidden."""
        indicator = StaleStateIndicator()
        
        assert indicator.is_visible is False
        assert indicator.last_activity is None

    def test_stale_indicator_becomes_visible_when_stale(self):
        """Test indicator becomes visible when stale state is set."""
        indicator = StaleStateIndicator()
        now = datetime.now(timezone.utc)
        
        indicator.update_stale_state(is_stale=True, last_activity=now)
        
        assert indicator.is_visible is True
        assert indicator.last_activity == now

    def test_stale_indicator_hides_when_not_stale(self):
        """Test indicator hides when stale state is cleared."""
        indicator = StaleStateIndicator()
        now = datetime.now(timezone.utc)
        
        # First make visible
        indicator.update_stale_state(is_stale=True, last_activity=now)
        assert indicator.is_visible is True
        
        # Then hide
        indicator.update_stale_state(is_stale=False, last_activity=now)
        assert indicator.is_visible is False

    def test_stale_indicator_display_format(self):
        """Test indicator displays correct format per UX spec."""
        indicator = StaleStateIndicator()
        test_time = datetime(2026, 1, 28, 14, 30, 45, tzinfo=timezone.utc)
        
        indicator.update_stale_state(is_stale=True, last_activity=test_time)
        
        rendered = indicator.render()
        
        # Per UX spec: "⚠ No activity for 60s | Last: HH:MM:SS | Press R to refresh"
        assert "⚠" in rendered
        assert "No activity for 60s" in rendered
        assert "14:30:45" in rendered
        assert "Press R to refresh" in rendered

    def test_stale_indicator_empty_when_hidden(self):
        """Test indicator renders empty when hidden."""
        indicator = StaleStateIndicator()
        test_time = datetime.now(timezone.utc)
        
        # Set activity but keep hidden
        indicator.last_activity = test_time
        indicator.is_visible = False
        
        assert indicator.render() == ""

    def test_stale_indicator_empty_when_no_activity(self):
        """Test indicator renders empty when no activity recorded."""
        indicator = StaleStateIndicator()
        
        indicator.is_visible = True
        indicator.last_activity = None
        
        assert indicator.render() == ""


class TestStaleStateWithTUIClient:
    """Integration tests for stale detection with TUIClient."""

    def test_client_stale_triggers_indicator_update(self):
        """Test TUIClient stale state can trigger indicator update."""
        import time
        from cyberred.tui.daemon_client import TUIClient
        
        client = TUIClient()
        indicator = StaleStateIndicator()
        
        # Simulate activity 61s ago (stale)
        client._last_activity_time = time.monotonic() - 61.0
        
        # Update indicator based on client state
        indicator.update_stale_state(
            is_stale=client.is_stale,
            last_activity=client.last_activity_time,
        )
        
        assert indicator.is_visible is True
        assert indicator.last_activity is not None

    def test_client_fresh_clears_indicator(self):
        """Test fresh TUIClient state clears indicator."""
        import time
        from cyberred.tui.daemon_client import TUIClient
        
        client = TUIClient()
        indicator = StaleStateIndicator()
        
        # First set stale
        client._last_activity_time = time.monotonic() - 61.0
        indicator.update_stale_state(
            is_stale=client.is_stale,
            last_activity=client.last_activity_time,
        )
        assert indicator.is_visible is True
        
        # Now set fresh
        client._last_activity_time = time.monotonic() - 10.0
        indicator.update_stale_state(
            is_stale=client.is_stale,
            last_activity=client.last_activity_time,
        )
        assert indicator.is_visible is False

    def test_refresh_action_clears_stale(self):
        """Test refresh action updates activity time and clears stale."""
        import time
        from cyberred.tui.daemon_client import TUIClient
        
        client = TUIClient()
        indicator = StaleStateIndicator()
        
        # Set stale
        client._last_activity_time = time.monotonic() - 61.0
        assert client.is_stale is True
        
        # Simulate refresh action
        client._last_activity_time = time.monotonic()
        
        # Update indicator
        indicator.update_stale_state(
            is_stale=client.is_stale,
            last_activity=client.last_activity_time,
        )
        
        assert client.is_stale is False
        assert indicator.is_visible is False


class TestStaleCheckTaskLifecycle:
    """Integration tests for stale check task lifecycle."""

    def test_stale_threshold_constant(self):
        """Test STALE_THRESHOLD_SECONDS is 60.0."""
        from cyberred.tui.daemon_client import TUIClient
        
        assert TUIClient.STALE_THRESHOLD_SECONDS == 60.0

    def test_stale_check_is_non_blocking(self):
        """Test stale check doesn't block (uses time.monotonic)."""
        import time
        from cyberred.tui.daemon_client import TUIClient
        
        client = TUIClient()
        client._last_activity_time = time.monotonic() - 30.0
        
        # Property access should be instant (non-blocking)
        start = time.monotonic()
        _ = client.is_stale
        _ = client.seconds_since_activity
        _ = client.last_activity_time
        elapsed = time.monotonic() - start
        
        # Should complete in < 1ms
        assert elapsed < 0.001
