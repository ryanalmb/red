"""Unit tests for StaleStateIndicator widget (Story 9.7).

Tests cover:
- Widget initialization with default hidden state
- Visibility toggle based on stale state
- Display format with timestamp and refresh prompt
- update_stale_state method behavior

AC #6, #7: Stale state warning display.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest


class TestStaleStateIndicatorInit:
    """Tests for StaleStateIndicator initialization."""

    def test_widget_initialization_default_hidden(self):
        """Widget initializes with is_visible=False (hidden by default)."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        widget = StaleStateIndicator()
        assert widget.is_visible is False

    def test_widget_initialization_no_last_activity(self):
        """Widget initializes with last_activity=None."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        widget = StaleStateIndicator()
        assert widget.last_activity is None


class TestStaleStateIndicatorUpdateMethod:
    """Tests for update_stale_state method."""

    def test_update_stale_state_makes_visible(self):
        """update_stale_state(True, ...) makes widget visible."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        widget = StaleStateIndicator()
        now = datetime.now(timezone.utc)
        
        widget.update_stale_state(is_stale=True, last_activity=now)
        
        assert widget.is_visible is True
        assert widget.last_activity == now

    def test_update_stale_state_hides_widget(self):
        """update_stale_state(False, ...) hides widget."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        widget = StaleStateIndicator()
        now = datetime.now(timezone.utc)
        
        # First make visible
        widget.update_stale_state(is_stale=True, last_activity=now)
        assert widget.is_visible is True
        
        # Then hide
        widget.update_stale_state(is_stale=False, last_activity=now)
        assert widget.is_visible is False

    def test_update_stale_state_updates_timestamp(self):
        """update_stale_state updates last_activity timestamp."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        widget = StaleStateIndicator()
        time1 = datetime(2026, 1, 28, 10, 0, 0, tzinfo=timezone.utc)
        time2 = datetime(2026, 1, 28, 11, 0, 0, tzinfo=timezone.utc)
        
        widget.update_stale_state(is_stale=True, last_activity=time1)
        assert widget.last_activity == time1
        
        widget.update_stale_state(is_stale=True, last_activity=time2)
        assert widget.last_activity == time2


class TestStaleStateIndicatorRender:
    """Tests for widget rendering."""

    def test_render_returns_empty_when_not_visible(self):
        """render() returns empty string when not visible."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        widget = StaleStateIndicator()
        widget.is_visible = False
        widget.last_activity = datetime.now(timezone.utc)
        
        assert widget.render() == ""

    def test_render_returns_empty_when_no_activity(self):
        """render() returns empty string when last_activity is None."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        widget = StaleStateIndicator()
        widget.is_visible = True
        widget.last_activity = None
        
        assert widget.render() == ""

    def test_render_includes_warning_symbol(self):
        """render() includes ⚠ warning symbol."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        widget = StaleStateIndicator()
        widget.is_visible = True
        widget.last_activity = datetime(2026, 1, 28, 14, 30, 45, tzinfo=timezone.utc)
        
        result = widget.render()
        assert "⚠" in result

    def test_render_includes_60s_message(self):
        """render() includes 'No activity for 60s' message."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        widget = StaleStateIndicator()
        widget.is_visible = True
        widget.last_activity = datetime(2026, 1, 28, 14, 30, 45, tzinfo=timezone.utc)
        
        result = widget.render()
        assert "No activity for 60s" in result

    def test_render_includes_timestamp(self):
        """render() includes formatted timestamp (HH:MM:SS)."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        widget = StaleStateIndicator()
        widget.is_visible = True
        widget.last_activity = datetime(2026, 1, 28, 14, 30, 45, tzinfo=timezone.utc)
        
        result = widget.render()
        assert "14:30:45" in result

    def test_render_includes_refresh_prompt(self):
        """render() includes refresh prompt 'Press R to refresh'."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        widget = StaleStateIndicator()
        widget.is_visible = True
        widget.last_activity = datetime(2026, 1, 28, 14, 30, 45, tzinfo=timezone.utc)
        
        result = widget.render()
        assert "Press R to refresh" in result

    def test_render_format_complete(self):
        """render() returns complete format per UX spec."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        widget = StaleStateIndicator()
        widget.is_visible = True
        widget.last_activity = datetime(2026, 1, 28, 14, 30, 45, tzinfo=timezone.utc)
        
        result = widget.render()
        # Format: "⚠ No activity for 60s | Last: HH:MM:SS | Press R to refresh"
        assert "⚠ No activity for 60s | Last: 14:30:45 | Press R to refresh" == result


class TestStaleStateIndicatorCSS:
    """Tests for widget CSS styling."""

    def test_default_css_exists(self):
        """Widget has DEFAULT_CSS defined."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        assert hasattr(StaleStateIndicator, 'DEFAULT_CSS')
        assert StaleStateIndicator.DEFAULT_CSS is not None

    def test_default_css_contains_warning_background(self):
        """DEFAULT_CSS contains $warning background."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        assert "$warning" in StaleStateIndicator.DEFAULT_CSS

    def test_default_css_contains_display_none(self):
        """DEFAULT_CSS sets display: none by default (hidden)."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        assert "display: none" in StaleStateIndicator.DEFAULT_CSS


class TestStaleStateIndicatorWatcher:
    """Tests for reactive property watchers."""

    def test_watch_is_visible_adds_class(self):
        """watch_is_visible adds 'visible' class when True."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        widget = StaleStateIndicator()
        # Simulate watcher call
        widget.watch_is_visible(True)
        
        assert "visible" in widget.classes

    def test_watch_is_visible_removes_class(self):
        """watch_is_visible removes 'visible' class when False."""
        from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
        
        widget = StaleStateIndicator()
        widget.add_class("visible")
        
        widget.watch_is_visible(False)
        
        assert "visible" not in widget.classes
