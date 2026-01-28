"""Integration tests for War Room Three-Pane Layout.

Story 9.2: War Room Three-Pane Layout

Tests:
- Three-pane rendering with Textual pilot
- Pane resize behavior
- Layout persistence file I/O
- F-key focus navigation
- Responsive mode transitions
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from textual.pilot import Pilot


class TestWarRoomLayoutRendering:
    """Integration tests for three-pane rendering (AC: #1, #5)."""

    @pytest.mark.asyncio
    async def test_war_room_layout_mounts_three_panes(self) -> None:
        """Test WarRoomLayout mounts three pane containers."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield WarRoomLayout()

        async with TestApp().run_test() as pilot:
            app = pilot.app
            # Query for the three panes
            targets = app.query_one("#pane-targets")
            hive = app.query_one("#pane-hive")
            strategy = app.query_one("#pane-strategy")
            
            assert targets is not None
            assert hive is not None
            assert strategy is not None

    @pytest.mark.asyncio
    async def test_war_room_layout_panes_have_titles(self) -> None:
        """Test each pane has a title Static widget."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield WarRoomLayout()

        async with TestApp().run_test() as pilot:
            app = pilot.app
            # Query for pane titles
            titles = app.query(".pane-title")
            assert len(titles) == 3

    @pytest.mark.asyncio
    async def test_war_room_layout_default_widths_applied(self) -> None:
        """Test default width percentages are applied to panes."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield WarRoomLayout()

        async with TestApp().run_test() as pilot:
            app = pilot.app
            layout = app.query_one(WarRoomLayout)
            
            # Check reactive properties
            assert layout.left_width == 20
            assert layout.center_width == 50
            assert layout.right_width == 30


class TestWarRoomLayoutResize:
    """Integration tests for pane resize functionality (AC: #2)."""

    @pytest.mark.asyncio
    async def test_resize_pane_updates_layout(self) -> None:
        """Test resizing a pane updates layout widths."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield WarRoomLayout()

        async with TestApp().run_test() as pilot:
            app = pilot.app
            layout = app.query_one(WarRoomLayout)
            
            # Resize left pane
            layout.resize_pane("left", 25)
            
            assert layout.left_width == 25
            assert layout.center_width == 45  # Adjusted
            assert layout.right_width == 30   # Unchanged

    @pytest.mark.asyncio
    async def test_expand_shrink_focused_pane(self) -> None:
        """Test keyboard expand/shrink of focused pane."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout, RESIZE_STEP

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield WarRoomLayout()

        async with TestApp().run_test() as pilot:
            app = pilot.app
            layout = app.query_one(WarRoomLayout)
            
            # Focus left pane and expand
            layout.active_pane = "left"
            original_width = layout.left_width
            
            layout.expand_focused_pane()
            
            assert layout.left_width == original_width + RESIZE_STEP

    @pytest.mark.asyncio
    async def test_pane_resized_message_emitted(self) -> None:
        """Test PaneResized message is emitted on resize."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout, PaneResized

        messages_received = []

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield WarRoomLayout()

            def on_pane_resized(self, event: PaneResized) -> None:
                messages_received.append(event)

        async with TestApp().run_test() as pilot:
            app = pilot.app
            layout = app.query_one(WarRoomLayout)
            
            # Resize left pane
            layout.resize_pane("left", 25)
            
            # Allow message to propagate
            await pilot.pause()
            
            # Check message was received
            assert len(messages_received) >= 1
            assert any(m.pane == "left" for m in messages_received)


class TestWarRoomLayoutPersistence:
    """Integration tests for layout persistence (AC: #3)."""

    @pytest.mark.asyncio
    async def test_save_and_load_config(self, tmp_path: Path) -> None:
        """Test saving and loading layout configuration."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout

        config_path = tmp_path / "layout.json"

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield WarRoomLayout()

        async with TestApp().run_test() as pilot:
            app = pilot.app
            layout = app.query_one(WarRoomLayout)
            
            # Customize widths
            layout.left_width = 30
            layout.center_width = 40
            layout.right_width = 30
            
            # Save config
            layout.save_config(config_path)
            
            assert config_path.exists()
            
            # Verify saved data
            data = json.loads(config_path.read_text())
            assert data["left_width"] == 30
            assert data["center_width"] == 40
            assert data["right_width"] == 30

    @pytest.mark.asyncio
    async def test_load_config_on_startup(self, tmp_path: Path) -> None:
        """Test loading layout config restores widths."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout

        config_path = tmp_path / "layout.json"
        config_path.write_text('{"left_width": 15, "center_width": 60, "right_width": 25}')

        class TestApp(App):
            def compose(self) -> ComposeResult:
                layout = WarRoomLayout()
                layout.load_config(config_path)
                yield layout

        async with TestApp().run_test() as pilot:
            app = pilot.app
            layout = app.query_one(WarRoomLayout)
            
            assert layout.left_width == 15
            assert layout.center_width == 60
            assert layout.right_width == 25

    @pytest.mark.asyncio
    async def test_load_missing_config_uses_defaults(self, tmp_path: Path) -> None:
        """Test loading missing config file uses defaults."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout

        config_path = tmp_path / "nonexistent.json"

        class TestApp(App):
            def compose(self) -> ComposeResult:
                layout = WarRoomLayout()
                layout.load_config(config_path)
                yield layout

        async with TestApp().run_test() as pilot:
            app = pilot.app
            layout = app.query_one(WarRoomLayout)
            
            # Should use defaults
            assert layout.left_width == 20
            assert layout.center_width == 50
            assert layout.right_width == 30


class TestWarRoomLayoutFocusNavigation:
    """Integration tests for F-key focus navigation (AC: #4)."""

    @pytest.mark.asyncio
    async def test_focus_targets_sets_active_pane(self) -> None:
        """Test focus_targets() sets active pane to left."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield WarRoomLayout()

        async with TestApp().run_test() as pilot:
            app = pilot.app
            layout = app.query_one(WarRoomLayout)
            
            layout.focus_targets()
            
            assert layout.active_pane == "left"

    @pytest.mark.asyncio
    async def test_focus_hive_sets_active_pane(self) -> None:
        """Test focus_hive() sets active pane to center."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield WarRoomLayout()

        async with TestApp().run_test() as pilot:
            app = pilot.app
            layout = app.query_one(WarRoomLayout)
            
            layout.focus_hive()
            
            assert layout.active_pane == "center"

    @pytest.mark.asyncio
    async def test_focus_strategy_sets_active_pane(self) -> None:
        """Test focus_strategy() sets active pane to right."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield WarRoomLayout()

        async with TestApp().run_test() as pilot:
            app = pilot.app
            layout = app.query_one(WarRoomLayout)
            
            layout.focus_strategy()
            
            assert layout.active_pane == "right"

    @pytest.mark.asyncio
    async def test_active_pane_visual_indicator(self) -> None:
        """Test focused pane has visual indicator class."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield WarRoomLayout()

        async with TestApp().run_test() as pilot:
            app = pilot.app
            layout = app.query_one(WarRoomLayout)
            
            # Focus left pane
            layout.focus_targets()
            await pilot.pause()
            
            targets_pane = app.query_one("#pane-targets")
            assert "focused" in targets_pane.classes


class TestWarRoomLayoutWidthConstraints:
    """Integration tests for width constraints."""

    @pytest.mark.asyncio
    async def test_minimum_width_enforced(self) -> None:
        """Test panes cannot go below minimum width."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout, MIN_PANE_WIDTH

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield WarRoomLayout()

        async with TestApp().run_test() as pilot:
            app = pilot.app
            layout = app.query_one(WarRoomLayout)
            
            # Try to resize below minimum
            layout.resize_pane("left", 5)
            
            assert layout.left_width >= MIN_PANE_WIDTH

    @pytest.mark.asyncio
    async def test_maximum_width_enforced(self) -> None:
        """Test panes cannot exceed maximum width."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout, MAX_PANE_WIDTH

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield WarRoomLayout()

        async with TestApp().run_test() as pilot:
            app = pilot.app
            layout = app.query_one(WarRoomLayout)
            
            # Try to resize above maximum
            layout.resize_pane("center", 90)
            
            assert layout.center_width <= MAX_PANE_WIDTH

    @pytest.mark.asyncio
    async def test_total_width_remains_100(self) -> None:
        """Test total width always sums to approximately 100%."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield WarRoomLayout()

        async with TestApp().run_test() as pilot:
            app = pilot.app
            layout = app.query_one(WarRoomLayout)
            
            # Perform multiple resizes
            layout.resize_pane("left", 25)
            layout.resize_pane("right", 35)
            layout.resize_pane("center", 45)
            
            total = layout.left_width + layout.center_width + layout.right_width
            # Should be close to 100 (may have small variance due to clamping)
            assert 95 <= total <= 105


class TestWarRoomLayoutExportsFromInit:
    """Test exports from widgets __init__.py."""

    def test_war_room_layout_importable_from_widgets(self) -> None:
        """Test WarRoomLayout can be imported from widgets module."""
        from cyberred.tui.widgets import (
            WarRoomLayout,
            LayoutConfig,
            PaneResized,
            TargetsPane,
            HiveMatrixPane,
            StrategyStreamPane,
            MIN_PANE_WIDTH,
            MAX_PANE_WIDTH,
            RESIZE_STEP,
            DEFAULT_CONFIG_PATH,
        )
        
        assert WarRoomLayout is not None
        assert LayoutConfig is not None
        assert PaneResized is not None
        assert TargetsPane is not None
        assert HiveMatrixPane is not None
        assert StrategyStreamPane is not None
        assert MIN_PANE_WIDTH == 10
        assert MAX_PANE_WIDTH == 80
        assert RESIZE_STEP == 5
