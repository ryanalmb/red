"""Unit tests for AttachProgressIndicator widget (Story 9.8).

Tests cover:
- Widget initialization with default hidden state
- start() method makes widget visible with engagement ID
- complete(success=True) shows success message with latency
- complete(success=False) shows error message
- Auto-hide timer functionality
- CSS class updates based on status

AC #3: Attach shows progress indicator.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App, ComposeResult


class TestAttachProgressIndicatorInit:
    """Tests for AttachProgressIndicator initialization."""

    def test_initial_state_hidden(self):
        """Widget starts hidden with default status."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        assert indicator.is_visible is False
        assert indicator.engagement_id == ""
        assert indicator.status == "idle"
        assert indicator.latency_ms == 0.0

    def test_default_css_present(self):
        """Widget has default CSS for styling."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        assert "AttachProgressIndicator" in indicator.DEFAULT_CSS
        assert "display: none" in indicator.DEFAULT_CSS


class TestAttachProgressIndicatorStart:
    """Tests for AttachProgressIndicator.start() method."""

    def test_start_makes_visible(self):
        """start() sets visibility to True."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.start("eng-123")
        
        assert indicator.is_visible is True
        assert indicator.engagement_id == "eng-123"
        assert indicator.status == "attaching"

    def test_start_updates_engagement_id(self):
        """start() updates engagement_id."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.start("test-engagement-id")
        
        assert indicator.engagement_id == "test-engagement-id"

    def test_start_sets_attaching_status(self):
        """start() sets status to 'attaching'."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.start("eng-abc")
        
        assert indicator.status == "attaching"


class TestAttachProgressIndicatorComplete:
    """Tests for AttachProgressIndicator.complete() method."""

    def test_complete_success_updates_status(self):
        """complete(success=True) sets status to 'success'."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.start("eng-123")
        indicator.complete(success=True, latency_ms=150.5)
        
        assert indicator.status == "success"
        assert indicator.latency_ms == 150.5

    def test_complete_negative_latency_raises_error(self):
        """complete() raises ValueError for negative latency."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        import pytest
        
        indicator = AttachProgressIndicator()
        indicator.start("eng-123")
        
        with pytest.raises(ValueError) as exc_info:
            indicator.complete(success=True, latency_ms=-100.0)
        
        assert "non-negative" in str(exc_info.value)
        assert "-100" in str(exc_info.value)

    def test_complete_failure_updates_status(self):
        """complete(success=False) sets status to 'error'."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.start("eng-123")
        indicator.complete(success=False)
        
        assert indicator.status == "error"

    def test_complete_stores_latency(self):
        """complete() stores latency value."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.start("eng-123")
        indicator.complete(success=True, latency_ms=1234.56)
        
        assert indicator.latency_ms == 1234.56

    def test_complete_default_latency_is_zero(self):
        """complete() uses 0.0 as default latency."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.start("eng-123")
        indicator.complete(success=False)
        
        assert indicator.latency_ms == 0.0


class TestAttachProgressIndicatorRender:
    """Tests for AttachProgressIndicator.render() method."""

    def test_render_idle_returns_empty(self):
        """render() returns empty string when idle."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        assert indicator.render() == ""

    def test_render_unknown_status_returns_empty(self):
        """render() returns empty string for unknown status values."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.status = "unknown_status"
        assert indicator.render() == ""

    def test_render_attaching_shows_engagement_id(self):
        """render() shows engagement ID when attaching."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.start("my-engagement")
        
        result = indicator.render()
        assert "my-engagement" in result
        assert "Attaching" in result
        assert "⏳" in result

    def test_render_success_shows_latency(self):
        """render() shows latency on success."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.start("eng-123")
        indicator.complete(success=True, latency_ms=1500.0)
        
        result = indicator.render()
        assert "1500" in result
        assert "✓" in result
        assert "Attached" in result

    def test_render_error_shows_failure(self):
        """render() shows error message on failure."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.start("eng-123")
        indicator.complete(success=False)
        
        result = indicator.render()
        assert "✗" in result
        assert "failed" in result.lower()


class TestAttachProgressIndicatorHide:
    """Tests for AttachProgressIndicator._hide() method."""

    def test_hide_sets_invisible(self):
        """_hide() sets is_visible to False."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.start("eng-123")
        assert indicator.is_visible is True
        
        indicator._hide()
        assert indicator.is_visible is False

    def test_hide_resets_status_to_idle(self):
        """_hide() resets status to 'idle'."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.start("eng-123")
        indicator.complete(success=True, latency_ms=100.0)
        assert indicator.status == "success"
        
        indicator._hide()
        assert indicator.status == "idle"


class TestAttachProgressIndicatorWatchers:
    """Tests for reactive property watchers."""

    def test_watch_is_visible_adds_class(self):
        """watch_is_visible adds 'visible' class when True."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        # Simulate watcher being called
        indicator.watch_is_visible(True)
        
        assert "visible" in indicator.classes

    def test_watch_is_visible_removes_class(self):
        """watch_is_visible removes 'visible' class when False."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.add_class("visible")
        indicator.watch_is_visible(False)
        
        assert "visible" not in indicator.classes

    def test_watch_status_success_adds_class(self):
        """watch_status adds 'success' class when status is success."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.watch_status("success")
        
        assert "success" in indicator.classes
        assert "error" not in indicator.classes

    def test_watch_status_error_adds_class(self):
        """watch_status adds 'error' class when status is error."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.watch_status("error")
        
        assert "error" in indicator.classes
        assert "success" not in indicator.classes

    def test_watch_status_clears_classes_on_idle(self):
        """watch_status clears success/error classes when idle."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        indicator = AttachProgressIndicator()
        indicator.add_class("success")
        indicator.watch_status("idle")
        
        assert "success" not in indicator.classes
        assert "error" not in indicator.classes


class TestAttachProgressIndicatorExport:
    """Tests for AttachProgressIndicator module exports."""

    def test_widget_exported_from_widgets_package(self):
        """AttachProgressIndicator is exported from widgets package."""
        from cyberred.tui.widgets import AttachProgressIndicator
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator as DirectImport
        
        assert AttachProgressIndicator is DirectImport


class TestAttachProgressIndicatorIntegration:
    """Integration tests for AttachProgressIndicator with Textual app."""

    @pytest.mark.asyncio
    async def test_widget_in_app_context(self):
        """Widget works correctly in a Textual app context."""
        from cyberred.tui.widgets.attach_progress import AttachProgressIndicator
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield AttachProgressIndicator(id="progress")
        
        app = TestApp()
        async with app.run_test() as pilot:
            indicator = app.query_one("#progress", AttachProgressIndicator)
            
            # Test start
            indicator.start("test-eng")
            assert indicator.is_visible is True
            assert indicator.engagement_id == "test-eng"
            
            # Test complete
            indicator.complete(success=True, latency_ms=500.0)
            assert indicator.status == "success"
            assert indicator.latency_ms == 500.0
