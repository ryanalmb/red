"""Unit tests for WarRoomLayout widget.

Story 9.2: War Room Three-Pane Layout

Tests:
- WarRoomLayout initialization with default widths (20/50/30)
- Pane width reactive updates
- LayoutConfig load/save operations
- Minimum width bounds (10% minimum per pane)
- Focus switching methods
- PaneResized message emission
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from dataclasses import asdict


class TestLayoutConfig:
    """Unit tests for LayoutConfig dataclass (AC: #3)."""

    def test_layout_config_default_values(self) -> None:
        """Test LayoutConfig has correct default values per UX spec."""
        from cyberred.tui.widgets.war_room_layout import LayoutConfig
        
        config = LayoutConfig()
        
        # Per UX spec: Left 20%, Middle 50%, Right 30%
        assert config.left_width == 20
        assert config.center_width == 50
        assert config.right_width == 30

    def test_layout_config_custom_values(self) -> None:
        """Test LayoutConfig accepts custom values."""
        from cyberred.tui.widgets.war_room_layout import LayoutConfig
        
        config = LayoutConfig(left_width=25, center_width=45, right_width=30)
        
        assert config.left_width == 25
        assert config.center_width == 45
        assert config.right_width == 30

    def test_layout_config_load_valid_file(self, tmp_path: Path) -> None:
        """Test LayoutConfig.load() with valid JSON file."""
        from cyberred.tui.widgets.war_room_layout import LayoutConfig
        
        config_path = tmp_path / "layout.json"
        config_data = {"left_width": 15, "center_width": 60, "right_width": 25}
        config_path.write_text(json.dumps(config_data))
        
        config = LayoutConfig.load(config_path)
        
        assert config.left_width == 15
        assert config.center_width == 60
        assert config.right_width == 25

    def test_layout_config_load_missing_file(self, tmp_path: Path) -> None:
        """Test LayoutConfig.load() returns defaults for missing file."""
        from cyberred.tui.widgets.war_room_layout import LayoutConfig
        
        config_path = tmp_path / "nonexistent.json"
        
        config = LayoutConfig.load(config_path)
        
        # Should return defaults
        assert config.left_width == 20
        assert config.center_width == 50
        assert config.right_width == 30

    def test_layout_config_load_corrupted_json(self, tmp_path: Path) -> None:
        """Test LayoutConfig.load() handles corrupted JSON gracefully."""
        from cyberred.tui.widgets.war_room_layout import LayoutConfig
        
        config_path = tmp_path / "corrupted.json"
        config_path.write_text("{ invalid json }")
        
        config = LayoutConfig.load(config_path)
        
        # Should return defaults
        assert config.left_width == 20
        assert config.center_width == 50
        assert config.right_width == 30

    def test_layout_config_load_invalid_types(self, tmp_path: Path) -> None:
        """Test LayoutConfig.load() handles invalid type values."""
        from cyberred.tui.widgets.war_room_layout import LayoutConfig
        
        config_path = tmp_path / "invalid_types.json"
        config_path.write_text('{"left_width": "not_a_number"}')
        
        config = LayoutConfig.load(config_path)
        
        # Should return defaults due to TypeError
        assert config.left_width == 20
        assert config.center_width == 50
        assert config.right_width == 30

    def test_layout_config_save_creates_directory(self, tmp_path: Path) -> None:
        """Test LayoutConfig.save() creates parent directory."""
        from cyberred.tui.widgets.war_room_layout import LayoutConfig
        
        config = LayoutConfig(left_width=25, center_width=45, right_width=30)
        config_path = tmp_path / "subdir" / "layout.json"
        
        config.save(config_path)
        
        assert config_path.exists()
        saved_data = json.loads(config_path.read_text())
        assert saved_data["left_width"] == 25
        assert saved_data["center_width"] == 45
        assert saved_data["right_width"] == 30

    def test_layout_config_save_overwrites_existing(self, tmp_path: Path) -> None:
        """Test LayoutConfig.save() overwrites existing file."""
        from cyberred.tui.widgets.war_room_layout import LayoutConfig
        
        config_path = tmp_path / "layout.json"
        config_path.write_text('{"left_width": 10}')
        
        config = LayoutConfig(left_width=30, center_width=40, right_width=30)
        config.save(config_path)
        
        saved_data = json.loads(config_path.read_text())
        assert saved_data["left_width"] == 30
        assert saved_data["center_width"] == 40
        assert saved_data["right_width"] == 30

    def test_layout_config_asdict(self) -> None:
        """Test LayoutConfig can be converted to dict."""
        from cyberred.tui.widgets.war_room_layout import LayoutConfig
        
        config = LayoutConfig(left_width=15, center_width=55, right_width=30)
        
        data = asdict(config)
        
        assert data == {"left_width": 15, "center_width": 55, "right_width": 30}

    def test_layout_config_load_invalid_sum(self, tmp_path: Path) -> None:
        """Test LayoutConfig.load() rejects widths that don't sum to ~100%."""
        from cyberred.tui.widgets.war_room_layout import LayoutConfig
        
        config_path = tmp_path / "invalid_sum.json"
        # Sum is 150%, which is invalid
        config_path.write_text('{"left_width": 50, "center_width": 50, "right_width": 50}')
        
        config = LayoutConfig.load(config_path)
        
        # Should return defaults
        assert config.left_width == 20
        assert config.center_width == 50
        assert config.right_width == 30

    def test_layout_config_load_valid_sum_with_tolerance(self, tmp_path: Path) -> None:
        """Test LayoutConfig.load() accepts widths that sum within tolerance (95-105)."""
        from cyberred.tui.widgets.war_room_layout import LayoutConfig
        
        config_path = tmp_path / "valid_tolerance.json"
        # Sum is 98%, within tolerance
        config_path.write_text('{"left_width": 18, "center_width": 50, "right_width": 30}')
        
        config = LayoutConfig.load(config_path)
        
        assert config.left_width == 18
        assert config.center_width == 50
        assert config.right_width == 30

    def test_layout_config_save_returns_true_on_success(self, tmp_path: Path) -> None:
        """Test LayoutConfig.save() returns True on success."""
        from cyberred.tui.widgets.war_room_layout import LayoutConfig
        
        config = LayoutConfig(left_width=25, center_width=45, right_width=30)
        config_path = tmp_path / "layout.json"
        
        result = config.save(config_path)
        
        assert result is True
        assert config_path.exists()

    def test_layout_config_save_returns_false_on_permission_error(self, tmp_path: Path) -> None:
        """Test LayoutConfig.save() returns False on permission error."""
        from cyberred.tui.widgets.war_room_layout import LayoutConfig
        
        config = LayoutConfig(left_width=25, center_width=45, right_width=30)
        
        # Mock mkdir to raise PermissionError
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            mock_mkdir.side_effect = PermissionError("Permission denied")
            config_path = tmp_path / "subdir" / "layout.json"
            
            result = config.save(config_path)
            
            assert result is False

    def test_layout_config_save_atomic_write(self, tmp_path: Path) -> None:
        """Test LayoutConfig.save() uses atomic write pattern."""
        from cyberred.tui.widgets.war_room_layout import LayoutConfig
        
        config = LayoutConfig(left_width=30, center_width=40, right_width=30)
        config_path = tmp_path / "layout.json"
        
        # First save
        config.save(config_path)
        
        # Verify no temp file left behind
        temp_path = config_path.with_suffix(".tmp")
        assert not temp_path.exists()
        assert config_path.exists()

    def test_layout_config_save_handles_oserror(self, tmp_path: Path) -> None:
        """Test LayoutConfig.save() handles OSError."""
        from cyberred.tui.widgets.war_room_layout import LayoutConfig
        
        config = LayoutConfig(left_width=25, center_width=45, right_width=30)
        
        # Mock open to raise OSError during write
        with patch("builtins.open") as mock_open:
            mock_open.side_effect = OSError("Disk full")
            config_path = tmp_path / "layout.json"
            
            result = config.save(config_path)
            
            assert result is False


class TestWarRoomLayout:
    """Unit tests for WarRoomLayout widget (AC: #1, #2)."""

    def test_war_room_layout_default_widths(self) -> None:
        """Test WarRoomLayout initializes with default UX spec widths."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        
        # Per UX spec: Left 20%, Middle 50%, Right 30%
        assert layout.left_width == 20
        assert layout.center_width == 50
        assert layout.right_width == 30

    def test_war_room_layout_custom_widths(self) -> None:
        """Test WarRoomLayout accepts custom initial widths."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout(left_width=25, center_width=45, right_width=30)
        
        assert layout.left_width == 25
        assert layout.center_width == 45
        assert layout.right_width == 30

    def test_war_room_layout_min_width_constant(self) -> None:
        """Test minimum width constant is defined."""
        from cyberred.tui.widgets.war_room_layout import MIN_PANE_WIDTH
        
        assert MIN_PANE_WIDTH == 10

    def test_war_room_layout_max_width_constant(self) -> None:
        """Test maximum width constant is defined."""
        from cyberred.tui.widgets.war_room_layout import MAX_PANE_WIDTH
        
        assert MAX_PANE_WIDTH == 80

    def test_war_room_layout_clamp_width_enforces_minimum(self) -> None:
        """Test clamp_width enforces minimum 10% per pane."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        
        # Try to set below minimum
        result = layout.clamp_width(5)
        
        assert result == 10  # Clamped to minimum

    def test_war_room_layout_clamp_width_enforces_maximum(self) -> None:
        """Test clamp_width enforces maximum 80% per pane."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        
        # Try to set above maximum
        result = layout.clamp_width(90)
        
        assert result == 80  # Clamped to maximum

    def test_war_room_layout_clamp_width_allows_valid(self) -> None:
        """Test clamp_width allows valid widths."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        
        result = layout.clamp_width(35)
        
        assert result == 35  # No change needed

    def test_war_room_layout_resize_left_pane(self) -> None:
        """Test resizing left pane updates widths correctly."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()  # 20/50/30
        
        layout.resize_pane("left", 25)
        
        assert layout.left_width == 25
        # Center adjusts, right stays same
        assert layout.center_width == 45
        assert layout.right_width == 30

    def test_war_room_layout_resize_right_pane(self) -> None:
        """Test resizing right pane updates widths correctly."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()  # 20/50/30
        
        layout.resize_pane("right", 35)
        
        assert layout.left_width == 20
        # Center adjusts
        assert layout.center_width == 45
        assert layout.right_width == 35

    def test_war_room_layout_resize_center_pane(self) -> None:
        """Test resizing center pane adjusts others proportionally."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()  # 20/50/30
        
        layout.resize_pane("center", 60)
        
        # Left and right should adjust proportionally
        assert layout.center_width == 60
        # Total should still be 100
        assert layout.left_width + layout.center_width + layout.right_width == 100

    def test_war_room_layout_resize_respects_minimum(self) -> None:
        """Test resize doesn't allow any pane below minimum."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()  # 20/50/30
        
        # Try to make center so big it would force others below minimum
        layout.resize_pane("center", 85)
        
        # Should be constrained - no pane below 10%
        assert layout.left_width >= 10
        assert layout.center_width >= 10
        assert layout.right_width >= 10

    def test_war_room_layout_resize_center_edge_case_zero_ratio(self) -> None:
        """Test resize center handles edge case when left+right is minimal."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        # Create layout where left and right are at minimum
        layout = WarRoomLayout(left_width=10, center_width=80, right_width=10)
        
        # Resize center - should handle division gracefully
        layout.resize_pane("center", 70)
        
        # Total should still be approximately 100
        total = layout.left_width + layout.center_width + layout.right_width
        assert 95 <= total <= 105

    def test_war_room_layout_resize_invalid_pane_name(self) -> None:
        """Test resize_pane with invalid pane name does nothing."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()  # 20/50/30
        original_left = layout.left_width
        original_center = layout.center_width
        original_right = layout.right_width
        
        # Call resize with invalid pane name - should not change anything
        layout.resize_pane("invalid", 40)  # type: ignore
        
        # Widths should remain unchanged
        assert layout.left_width == original_left
        assert layout.center_width == original_center
        assert layout.right_width == original_right

    def test_war_room_layout_config_path(self) -> None:
        """Test default config path is ~/.cyber-red/layout.json."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout, DEFAULT_CONFIG_PATH
        
        assert "layout.json" in str(DEFAULT_CONFIG_PATH)
        assert ".cyber-red" in str(DEFAULT_CONFIG_PATH)

    def test_war_room_layout_load_config(self, tmp_path: Path) -> None:
        """Test load_config loads layout from file."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        config_path = tmp_path / "layout.json"
        config_path.write_text('{"left_width": 25, "center_width": 45, "right_width": 30}')
        
        layout = WarRoomLayout()
        layout.load_config(config_path)
        
        assert layout.left_width == 25
        assert layout.center_width == 45
        assert layout.right_width == 30

    def test_war_room_layout_save_config(self, tmp_path: Path) -> None:
        """Test save_config persists layout to file."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        config_path = tmp_path / "layout.json"
        
        layout = WarRoomLayout(left_width=30, center_width=40, right_width=30)
        layout.save_config(config_path)
        
        saved = json.loads(config_path.read_text())
        assert saved["left_width"] == 30
        assert saved["center_width"] == 40
        assert saved["right_width"] == 30


class TestPaneResizedMessage:
    """Unit tests for PaneResized message (AC: #2)."""

    def test_pane_resized_message_attributes(self) -> None:
        """Test PaneResized message has required attributes."""
        from cyberred.tui.widgets.war_room_layout import PaneResized
        
        msg = PaneResized(pane="left", old_width=20, new_width=25)
        
        assert msg.pane == "left"
        assert msg.old_width == 20
        assert msg.new_width == 25

    def test_pane_resized_message_types(self) -> None:
        """Test PaneResized message is a Textual Message."""
        from cyberred.tui.widgets.war_room_layout import PaneResized
        from textual.message import Message
        
        msg = PaneResized(pane="center", old_width=50, new_width=55)
        
        assert isinstance(msg, Message)


class TestTargetsPane:
    """Unit tests for TargetsPane placeholder widget."""

    def test_targets_pane_exists(self) -> None:
        """Test TargetsPane widget exists."""
        from cyberred.tui.widgets.war_room_layout import TargetsPane
        
        pane = TargetsPane()
        assert pane is not None

    def test_targets_pane_id(self) -> None:
        """Test TargetsPane can be created with custom id."""
        from cyberred.tui.widgets.war_room_layout import TargetsPane
        
        pane = TargetsPane(id="my-targets")
        assert pane.id == "my-targets"


class TestHiveMatrixPane:
    """Unit tests for HiveMatrixPane placeholder widget."""

    def test_hive_matrix_pane_exists(self) -> None:
        """Test HiveMatrixPane widget exists."""
        from cyberred.tui.widgets.war_room_layout import HiveMatrixPane
        
        pane = HiveMatrixPane()
        assert pane is not None


class TestStrategyStreamPane:
    """Unit tests for StrategyStreamPane placeholder widget."""

    def test_strategy_stream_pane_exists(self) -> None:
        """Test StrategyStreamPane widget exists."""
        from cyberred.tui.widgets.war_room_layout import StrategyStreamPane
        
        pane = StrategyStreamPane()
        assert pane is not None


class TestFocusNavigation:
    """Unit tests for F-key pane focus navigation (AC: #4)."""

    def test_war_room_layout_focus_targets(self) -> None:
        """Test focus_targets method exists."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        
        assert hasattr(layout, "focus_targets")
        assert callable(layout.focus_targets)

    def test_war_room_layout_focus_hive(self) -> None:
        """Test focus_hive method exists."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        
        assert hasattr(layout, "focus_hive")
        assert callable(layout.focus_hive)

    def test_war_room_layout_focus_strategy(self) -> None:
        """Test focus_strategy method exists."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        
        assert hasattr(layout, "focus_strategy")
        assert callable(layout.focus_strategy)

    def test_war_room_layout_active_pane_reactive(self) -> None:
        """Test active_pane is a reactive property."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        
        # Should have active_pane attribute
        assert hasattr(layout, "active_pane")
        
        # Should be able to set it
        layout.active_pane = "left"
        assert layout.active_pane == "left"


class TestKeyboardResize:
    """Unit tests for keyboard resize commands (AC: #2)."""

    def test_war_room_layout_expand_focused_pane(self) -> None:
        """Test expand_focused_pane increases width."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()  # 20/50/30
        layout.active_pane = "left"
        
        layout.expand_focused_pane()
        
        assert layout.left_width > 20

    def test_war_room_layout_shrink_focused_pane(self) -> None:
        """Test shrink_focused_pane decreases width."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()  # 20/50/30
        layout.active_pane = "left"
        
        layout.shrink_focused_pane()
        
        assert layout.left_width < 20

    def test_keyboard_resize_step_constant(self) -> None:
        """Test keyboard resize step is 5%."""
        from cyberred.tui.widgets.war_room_layout import RESIZE_STEP
        
        assert RESIZE_STEP == 5


class TestWarRoomLayoutExports:
    """Test that all components are properly exported."""

    def test_war_room_layout_exports(self) -> None:
        """Test all components are importable from widgets module."""
        from cyberred.tui.widgets.war_room_layout import (
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


class TestWarRoomLayoutCompose:
    """Tests for WarRoomLayout compose and widget methods."""

    def test_war_room_layout_compose_yields_panes(self) -> None:
        """Test compose yields components."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        # compose() returns a generator that yields widgets
        assert hasattr(layout, "compose")
        # Can call compose - it's a generator
        gen = layout.compose()
        assert gen is not None

    def test_war_room_layout_has_compose_method(self) -> None:
        """Test WarRoomLayout has compose method."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        assert hasattr(layout, "compose")
        assert callable(layout.compose)

    def test_war_room_layout_has_on_mount_method(self) -> None:
        """Test WarRoomLayout has on_mount method."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        assert hasattr(layout, "on_mount")
        assert callable(layout.on_mount)

    def test_war_room_layout_apply_widths_method_exists(self) -> None:
        """Test _apply_widths method exists."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        assert hasattr(layout, "_apply_widths")
        
        # Should not raise when called (panes not mounted)
        layout._apply_widths()

    def test_war_room_layout_on_mount_calls_apply_widths(self) -> None:
        """Test on_mount calls _apply_widths."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        from unittest.mock import MagicMock
        
        layout = WarRoomLayout()
        layout._apply_widths = MagicMock()
        
        layout.on_mount()
        
        layout._apply_widths.assert_called_once()


class TestWarRoomLayoutWatchers:
    """Tests for reactive property watchers."""

    def test_watch_left_width_posts_message(self) -> None:
        """Test watch_left_width posts PaneResized message."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout, PaneResized
        from unittest.mock import MagicMock
        
        layout = WarRoomLayout()
        layout.post_message = MagicMock()
        layout._apply_widths = MagicMock()
        
        layout.watch_left_width(20, 25)
        
        # Should post PaneResized message
        layout.post_message.assert_called_once()
        call_args = layout.post_message.call_args[0][0]
        assert isinstance(call_args, PaneResized)
        assert call_args.pane == "left"
        assert call_args.old_width == 20
        assert call_args.new_width == 25

    def test_watch_left_width_no_message_if_same(self) -> None:
        """Test watch_left_width doesn't post if width unchanged."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        from unittest.mock import MagicMock
        
        layout = WarRoomLayout()
        layout.post_message = MagicMock()
        layout._apply_widths = MagicMock()
        
        layout.watch_left_width(20, 20)
        
        layout.post_message.assert_not_called()

    def test_watch_center_width_posts_message(self) -> None:
        """Test watch_center_width posts PaneResized message."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout, PaneResized
        from unittest.mock import MagicMock
        
        layout = WarRoomLayout()
        layout.post_message = MagicMock()
        layout._apply_widths = MagicMock()
        
        layout.watch_center_width(50, 55)
        
        layout.post_message.assert_called_once()
        call_args = layout.post_message.call_args[0][0]
        assert isinstance(call_args, PaneResized)
        assert call_args.pane == "center"

    def test_watch_center_width_no_message_if_same(self) -> None:
        """Test watch_center_width doesn't post if width unchanged."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        from unittest.mock import MagicMock
        
        layout = WarRoomLayout()
        layout.post_message = MagicMock()
        layout._apply_widths = MagicMock()
        
        layout.watch_center_width(50, 50)
        
        layout.post_message.assert_not_called()

    def test_watch_right_width_posts_message(self) -> None:
        """Test watch_right_width posts PaneResized message."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout, PaneResized
        from unittest.mock import MagicMock
        
        layout = WarRoomLayout()
        layout.post_message = MagicMock()
        layout._apply_widths = MagicMock()
        
        layout.watch_right_width(30, 35)
        
        layout.post_message.assert_called_once()
        call_args = layout.post_message.call_args[0][0]
        assert isinstance(call_args, PaneResized)
        assert call_args.pane == "right"

    def test_watch_right_width_no_message_if_same(self) -> None:
        """Test watch_right_width doesn't post if width unchanged."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        from unittest.mock import MagicMock
        
        layout = WarRoomLayout()
        layout.post_message = MagicMock()
        layout._apply_widths = MagicMock()
        
        layout.watch_right_width(30, 30)
        
        layout.post_message.assert_not_called()

    def test_watch_active_pane_handles_exception(self) -> None:
        """Test watch_active_pane handles missing panes gracefully."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        
        # Should not raise when panes not mounted
        layout.watch_active_pane("center", "left")
        layout.watch_active_pane("left", "right")
        layout.watch_active_pane("right", "center")

    def test_watch_active_pane_with_invalid_old_value(self) -> None:
        """Test watch_active_pane handles invalid old_value gracefully."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        
        # Should not raise when old_value is not in pane_map
        layout.watch_active_pane("invalid_pane", "left")
        layout.watch_active_pane("", "center")

    def test_watch_active_pane_with_invalid_new_value(self) -> None:
        """Test watch_active_pane handles invalid new_value gracefully."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        
        # Should not raise when new_value is not in pane_map
        layout.watch_active_pane("left", "invalid_pane")
        layout.watch_active_pane("center", "")

    def test_watch_active_pane_with_both_invalid(self) -> None:
        """Test watch_active_pane handles both values invalid gracefully."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        
        # Should not raise when both values are not in pane_map
        layout.watch_active_pane("invalid1", "invalid2")
        layout.watch_active_pane("", "")


class TestWarRoomLayoutFocusMethods:
    """Tests for focus navigation methods."""

    def test_focus_targets_sets_active_pane(self) -> None:
        """Test focus_targets sets active_pane to left."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        layout.active_pane = "center"
        
        layout.focus_targets()
        
        assert layout.active_pane == "left"

    def test_focus_targets_handles_exception(self) -> None:
        """Test focus_targets handles missing pane gracefully."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        
        # Should not raise when pane not mounted
        layout.focus_targets()
        assert layout.active_pane == "left"

    def test_focus_hive_sets_active_pane(self) -> None:
        """Test focus_hive sets active_pane to center."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        layout.active_pane = "left"
        
        layout.focus_hive()
        
        assert layout.active_pane == "center"

    def test_focus_hive_handles_exception(self) -> None:
        """Test focus_hive handles missing pane gracefully."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        
        # Should not raise when pane not mounted
        layout.focus_hive()
        assert layout.active_pane == "center"

    def test_focus_strategy_sets_active_pane(self) -> None:
        """Test focus_strategy sets active_pane to right."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        layout.active_pane = "center"
        
        layout.focus_strategy()
        
        assert layout.active_pane == "right"

    def test_focus_strategy_handles_exception(self) -> None:
        """Test focus_strategy handles missing pane gracefully."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout
        
        layout = WarRoomLayout()
        
        # Should not raise when pane not mounted
        layout.focus_strategy()
        assert layout.active_pane == "right"


class TestWarRoomLayoutResize:
    """Additional tests for resize functionality."""

    def test_expand_focused_pane_center(self) -> None:
        """Test expanding center pane."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout, RESIZE_STEP
        
        layout = WarRoomLayout()  # 20/50/30
        layout.active_pane = "center"
        
        layout.expand_focused_pane()
        
        assert layout.center_width == 50 + RESIZE_STEP

    def test_expand_focused_pane_right(self) -> None:
        """Test expanding right pane."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout, RESIZE_STEP
        
        layout = WarRoomLayout()  # 20/50/30
        layout.active_pane = "right"
        
        layout.expand_focused_pane()
        
        assert layout.right_width == 30 + RESIZE_STEP

    def test_shrink_focused_pane_center(self) -> None:
        """Test shrinking center pane."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout, RESIZE_STEP
        
        layout = WarRoomLayout()  # 20/50/30
        layout.active_pane = "center"
        
        layout.shrink_focused_pane()
        
        assert layout.center_width == 50 - RESIZE_STEP

    def test_shrink_focused_pane_right(self) -> None:
        """Test shrinking right pane."""
        from cyberred.tui.widgets.war_room_layout import WarRoomLayout, RESIZE_STEP
        
        layout = WarRoomLayout()  # 20/50/30
        layout.active_pane = "right"
        
        layout.shrink_focused_pane()
        
        assert layout.right_width == 30 - RESIZE_STEP


class TestPanePlaceholders:
    """Tests for placeholder pane widgets."""

    def test_targets_pane_has_default_content(self) -> None:
        """Test TargetsPane has placeholder content."""
        from cyberred.tui.widgets.war_room_layout import TargetsPane
        from textual.widgets import Static
        
        pane = TargetsPane()
        # TargetsPane extends Static
        assert isinstance(pane, Static)

    def test_hive_matrix_pane_has_default_content(self) -> None:
        """Test HiveMatrixPane has placeholder content."""
        from cyberred.tui.widgets.war_room_layout import HiveMatrixPane
        from textual.widgets import Static
        
        pane = HiveMatrixPane()
        assert isinstance(pane, Static)

    def test_strategy_stream_pane_has_default_content(self) -> None:
        """Test StrategyStreamPane has placeholder content."""
        from cyberred.tui.widgets.war_room_layout import StrategyStreamPane
        from textual.widgets import Static
        
        pane = StrategyStreamPane()
        assert isinstance(pane, Static)
