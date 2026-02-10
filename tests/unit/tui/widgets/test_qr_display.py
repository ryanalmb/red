"""Unit tests for QRDisplayWidget.

Story 12.8: Natural Language Drop Box Setup - Task 9.4

Tests QR display widget rendering and updates with full coverage.
"""

import pytest
from textual.app import App
from textual.widgets import Static

from cyberred.tui.widgets.qr_display import QRDisplayWidget


class TestQRDisplayWidget:
    """Tests for QRDisplayWidget."""

    def test_widget_imports(self):
        """Test widget can be imported."""
        assert QRDisplayWidget is not None

    def test_widget_creation(self):
        """Test widget can be created with QR content."""
        qr_content = "██████\n██  ██\n██████"
        widget = QRDisplayWidget(qr_content)
        assert widget is not None
        assert widget._qr_content == qr_content

    def test_widget_has_css(self):
        """Test widget has CSS defined."""
        qr_content = "██████"
        widget = QRDisplayWidget(qr_content)
        assert widget.DEFAULT_CSS is not None
        assert "QRDisplayWidget" in widget.DEFAULT_CSS

    def test_widget_with_id(self):
        """Test widget can be created with ID."""
        widget = QRDisplayWidget("test", id="qr-test")
        assert widget.id == "qr-test"

    def test_widget_with_classes(self):
        """Test widget can be created with classes."""
        widget = QRDisplayWidget("test", classes="my-class")
        assert "my-class" in widget.classes

    def test_update_qr(self):
        """Test QR content can be updated."""
        widget = QRDisplayWidget("initial")
        assert widget._qr_content == "initial"

        widget.update_qr("updated")
        assert widget._qr_content == "updated"

    def test_widget_extends_static(self):
        """Test QRDisplayWidget is a subclass of Static."""
        assert issubclass(QRDisplayWidget, Static)

    def test_widget_empty_content(self):
        """Test widget can be created with empty content."""
        widget = QRDisplayWidget("")
        assert widget._qr_content == ""

    def test_widget_with_name(self):
        """Test widget can be created with name parameter."""
        widget = QRDisplayWidget("test", name="qr-widget")
        assert widget.name == "qr-widget"


class TestQRDisplayWidgetIntegration:
    """Integration tests for QR display widget."""

    @pytest.mark.asyncio
    async def test_widget_mounts(self):
        """Test widget can be mounted in app."""
        qr_content = "██████\n██  ██\n██████"

        class TestApp(App):
            def compose(self):
                yield QRDisplayWidget(qr_content, id="test-qr")

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            qr_widget = app.query_one("#test-qr", QRDisplayWidget)
            assert qr_widget is not None

    @pytest.mark.asyncio
    async def test_widget_update_qr_mounted(self):
        """Test QR content can be updated after mounting."""
        original = "██  ██"
        updated = "  ████"

        class TestApp(App):
            def compose(self):
                yield QRDisplayWidget(original, id="test-qr")

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-qr", QRDisplayWidget)
            widget.update_qr(updated)
            await pilot.pause()
            assert widget._qr_content == updated

    @pytest.mark.asyncio
    async def test_widget_renders_block_chars(self):
        """Test widget renders Unicode block character content."""
        qr_content = "██  ██\n  ████\n██  ██"

        class TestApp(App):
            def compose(self):
                yield QRDisplayWidget(qr_content, id="test-qr")

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-qr", QRDisplayWidget)
            assert widget._qr_content is not None

    @pytest.mark.asyncio
    async def test_widget_renders_fallback_text(self):
        """Test widget can render fallback text instead of QR."""
        fallback = (
            "┌──────────────────────────┐\n"
            "│ QR Library Not Installed │\n"
            "│ C2: wss://test:8444      │\n"
            "└──────────────────────────┘"
        )

        class TestApp(App):
            def compose(self):
                yield QRDisplayWidget(fallback, id="test-qr")

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            widget = app.query_one("#test-qr", QRDisplayWidget)
            assert widget._qr_content == fallback
