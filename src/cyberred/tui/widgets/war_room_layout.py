"""War Room Three-Pane Layout Widget.

Story 9.2: War Room Three-Pane Layout

Implements the three-pane War Room layout per UX spec:
- Left (20%): TARGETS - scope tree, discovered hosts
- Center (50%): HIVE MATRIX - agent status grid  
- Right (30%): STRATEGY STREAM - Director output + findings

Features:
- Resizable panes via keyboard (Ctrl+Left/Right)
- Layout persistence to ~/.cyber-red/layout.json
- F-key focus navigation between panes
- Minimum 10% width per pane
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from textual.containers import Horizontal, Vertical
from textual.widgets import Static
from textual.reactive import reactive
from textual.message import Message
from textual.css.query import NoMatches

if TYPE_CHECKING:
    from textual.app import ComposeResult

# Constants per UX spec
MIN_PANE_WIDTH = 10  # Minimum 10% width per pane
MAX_PANE_WIDTH = 80  # Maximum 80% width per pane
RESIZE_STEP = 5  # 5% step for keyboard resize
DEFAULT_CONFIG_PATH = Path.home() / ".cyber-red" / "layout.json"

# Pane type literal
PaneName = Literal["left", "center", "right"]


@dataclass
class LayoutConfig:
    """Persistent layout configuration.
    
    Stores pane width percentages for persistence across sessions.
    Default values match UX spec: Left 20%, Center 50%, Right 30%.
    """
    left_width: int = 20
    center_width: int = 50
    right_width: int = 30
    
    @classmethod
    def load(cls, path: Path) -> "LayoutConfig":
        """Load configuration from JSON file.
        
        Args:
            path: Path to the JSON configuration file.
            
        Returns:
            LayoutConfig instance with loaded values, or defaults if load fails.
        """
        try:
            with open(path) as f:
                data = json.load(f)
            # Validate that values are integers
            left = data.get("left_width", 20)
            center = data.get("center_width", 50)
            right = data.get("right_width", 30)
            if not all(isinstance(v, int) for v in [left, center, right]):
                return cls()
            # Validate that widths sum to 100% (with tolerance for rounding)
            total = left + center + right
            if not (95 <= total <= 105):
                return cls()
            return cls(left_width=left, center_width=center, right_width=right)
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            return cls()
    
    def save(self, path: Path) -> bool:
        """Save configuration to JSON file atomically.
        
        Creates parent directories if they don't exist.
        Uses atomic write (write to temp file, then rename) to prevent corruption.
        
        Args:
            path: Path where to save the JSON configuration.
            
        Returns:
            True if save succeeded, False otherwise.
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Atomic write: write to temp file then rename
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(asdict(self), f)
            temp_path.replace(path)
            return True
        except (OSError, PermissionError):
            return False


class PaneResized(Message):
    """Message emitted when a pane is resized.
    
    Used to trigger layout persistence on resize.
    """
    
    def __init__(self, pane: str, old_width: int, new_width: int) -> None:
        """Initialize PaneResized message.
        
        Args:
            pane: Name of the resized pane ('left', 'center', 'right').
            old_width: Previous width percentage.
            new_width: New width percentage.
        """
        super().__init__()
        self.pane = pane
        self.old_width = old_width
        self.new_width = new_width


class TargetsPane(Static):
    """Placeholder widget for TARGETS pane content.
    
    Will be populated by Story 9.x with scope tree and discovered hosts.
    """
    
    DEFAULT_CSS = """
    TargetsPane {
        height: 100%;
        border: solid $primary;
    }
    """
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__("TARGETS PANE\n(Scope tree, discovered hosts)", *args, **kwargs)


class HiveMatrixPane(Static):
    """Placeholder widget for HIVE MATRIX pane content.
    
    Will be populated by Stories 9.3/9.6 with agent status grid.
    """
    
    DEFAULT_CSS = """
    HiveMatrixPane {
        height: 100%;
        border: solid $primary;
    }
    """
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__("HIVE MATRIX PANE\n(Agent status grid)", *args, **kwargs)


class StrategyStreamPane(Static):
    """Placeholder widget for STRATEGY STREAM pane content.
    
    Will be populated by Story 9.5 with Director output and findings.
    """
    
    DEFAULT_CSS = """
    StrategyStreamPane {
        height: 100%;
        border: solid $primary;
    }
    """
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__("STRATEGY STREAM PANE\n(Director output, findings)", *args, **kwargs)


class WarRoomLayout(Horizontal):
    """Three-pane War Room layout per UX spec.
    
    Panes:
    - Left (20%): TARGETS - scope tree, discovered hosts
    - Center (50%): HIVE MATRIX - agent status grid
    - Right (30%): STRATEGY STREAM - Director output + findings
    
    Features:
    - Resizable panes with minimum 10% width
    - Layout persistence across sessions
    - F-key focus navigation
    """
    
    DEFAULT_CSS = """
    WarRoomLayout {
        height: 100%;
        width: 100%;
    }
    
    WarRoomLayout > Vertical {
        height: 100%;
    }
    
    .war-room-pane {
        border: solid $primary;
    }
    
    .war-room-pane.focused {
        border: double $accent;
    }
    
    .pane-title {
        height: 1;
        background: $surface;
        text-style: bold;
        text-align: center;
    }
    """
    
    # Reactive width properties (percentages)
    left_width: reactive[int] = reactive(20)
    center_width: reactive[int] = reactive(50)
    right_width: reactive[int] = reactive(30)
    
    # Active pane for focus tracking
    active_pane: reactive[str] = reactive("center")
    
    def __init__(
        self,
        left_width: int = 20,
        center_width: int = 50,
        right_width: int = 30,
        *args,
        **kwargs,
    ) -> None:
        """Initialize WarRoomLayout.
        
        Args:
            left_width: Initial left pane width percentage (default 20).
            center_width: Initial center pane width percentage (default 50).
            right_width: Initial right pane width percentage (default 30).
        """
        super().__init__(*args, **kwargs)
        self.left_width = left_width
        self.center_width = center_width
        self.right_width = right_width
    
    def compose(self) -> "ComposeResult":
        """Compose the three-pane layout."""
        # Left pane: TARGETS
        with Vertical(id="pane-targets", classes="war-room-pane"):
            yield Static("TARGETS", classes="pane-title")
            yield TargetsPane()
        
        # Center pane: HIVE MATRIX
        with Vertical(id="pane-hive", classes="war-room-pane"):
            yield Static("HIVE MATRIX", classes="pane-title")
            yield HiveMatrixPane()
        
        # Right pane: STRATEGY STREAM
        with Vertical(id="pane-strategy", classes="war-room-pane"):
            yield Static("STRATEGY STREAM", classes="pane-title")
            yield StrategyStreamPane()
    
    def on_mount(self) -> None:
        """Apply initial widths on mount."""
        self._apply_widths()
    
    def _apply_widths(self) -> None:
        """Apply current width percentages to panes."""
        try:
            targets = self.query_one("#pane-targets", Vertical)
            hive = self.query_one("#pane-hive", Vertical)
            strategy = self.query_one("#pane-strategy", Vertical)
            
            targets.styles.width = f"{self.left_width}%"
            hive.styles.width = f"{self.center_width}%"
            strategy.styles.width = f"{self.right_width}%"
        except NoMatches:
            # Panes not yet mounted
            pass
    
    def watch_left_width(self, old_value: int, new_value: int) -> None:
        """React to left_width changes."""
        self._apply_widths()
        if old_value != new_value:
            self.post_message(PaneResized("left", old_value, new_value))
    
    def watch_center_width(self, old_value: int, new_value: int) -> None:
        """React to center_width changes."""
        self._apply_widths()
        if old_value != new_value:
            self.post_message(PaneResized("center", old_value, new_value))
    
    def watch_right_width(self, old_value: int, new_value: int) -> None:
        """React to right_width changes."""
        self._apply_widths()
        if old_value != new_value:
            self.post_message(PaneResized("right", old_value, new_value))
    
    def watch_active_pane(self, old_value: str, new_value: str) -> None:
        """Update visual focus indicator on active pane change."""
        pane_map = {
            "left": "#pane-targets",
            "center": "#pane-hive", 
            "right": "#pane-strategy",
        }
        
        # Remove focused class from old pane
        if old_value in pane_map:
            try:
                old_pane = self.query_one(pane_map[old_value], Vertical)
                old_pane.remove_class("focused")
            except NoMatches:
                pass
        
        # Add focused class to new pane
        if new_value in pane_map:
            try:
                new_pane = self.query_one(pane_map[new_value], Vertical)
                new_pane.add_class("focused")
            except NoMatches:
                pass
    
    @staticmethod
    def clamp_width(width: int) -> int:
        """Clamp width to valid range.
        
        Args:
            width: Proposed width percentage.
            
        Returns:
            Width clamped to [MIN_PANE_WIDTH, MAX_PANE_WIDTH].
        """
        return max(MIN_PANE_WIDTH, min(MAX_PANE_WIDTH, width))
    
    def resize_pane(self, pane: PaneName, new_width: int) -> None:
        """Resize a pane while maintaining total 100%.
        
        Args:
            pane: Name of pane to resize ('left', 'center', 'right').
            new_width: Desired new width percentage.
        """
        new_width = self.clamp_width(new_width)
        
        if pane == "left":
            delta = new_width - self.left_width
            # Adjust center to compensate
            new_center = self.clamp_width(self.center_width - delta)
            actual_delta = self.center_width - new_center
            self.left_width = self.clamp_width(self.left_width + actual_delta)
            self.center_width = new_center
            
        elif pane == "right":
            delta = new_width - self.right_width
            # Adjust center to compensate
            new_center = self.clamp_width(self.center_width - delta)
            actual_delta = self.center_width - new_center
            self.right_width = self.clamp_width(self.right_width + actual_delta)
            self.center_width = new_center
            
        elif pane == "center":
            delta = new_width - self.center_width
            # Adjust left and right proportionally
            left_ratio = self.left_width / (self.left_width + self.right_width) if (self.left_width + self.right_width) > 0 else 0.5
            
            left_adjustment = int(delta * left_ratio)
            right_adjustment = delta - left_adjustment
            
            new_left = self.clamp_width(self.left_width - left_adjustment)
            new_right = self.clamp_width(self.right_width - right_adjustment)
            
            # Recalculate center based on actual adjustments
            self.left_width = new_left
            self.right_width = new_right
            self.center_width = 100 - new_left - new_right
    
    def expand_focused_pane(self) -> None:
        """Expand the currently focused pane by RESIZE_STEP."""
        current_width = getattr(self, f"{self.active_pane}_width", self.center_width)
        if self.active_pane == "center":
            current_width = self.center_width
        elif self.active_pane == "left":
            current_width = self.left_width
        else:
            current_width = self.right_width
            
        self.resize_pane(self.active_pane, current_width + RESIZE_STEP)  # type: ignore
    
    def shrink_focused_pane(self) -> None:
        """Shrink the currently focused pane by RESIZE_STEP."""
        current_width = getattr(self, f"{self.active_pane}_width", self.center_width)
        if self.active_pane == "center":
            current_width = self.center_width
        elif self.active_pane == "left":
            current_width = self.left_width
        else:
            current_width = self.right_width
            
        self.resize_pane(self.active_pane, current_width - RESIZE_STEP)  # type: ignore
    
    def focus_targets(self) -> None:
        """Focus the TARGETS (left) pane."""
        self.active_pane = "left"
        try:
            pane = self.query_one("#pane-targets", Vertical)
            pane.focus()
        except NoMatches:
            pass
    
    def focus_hive(self) -> None:
        """Focus the HIVE MATRIX (center) pane."""
        self.active_pane = "center"
        try:
            pane = self.query_one("#pane-hive", Vertical)
            pane.focus()
        except NoMatches:
            pass
    
    def focus_strategy(self) -> None:
        """Focus the STRATEGY STREAM (right) pane."""
        self.active_pane = "right"
        try:
            pane = self.query_one("#pane-strategy", Vertical)
            pane.focus()
        except NoMatches:
            pass
    
    def load_config(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        """Load layout configuration from file.
        
        Args:
            path: Path to configuration file (default: ~/.cyber-red/layout.json).
        """
        config = LayoutConfig.load(path)
        self.left_width = config.left_width
        self.center_width = config.center_width
        self.right_width = config.right_width
    
    def save_config(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        """Save current layout configuration to file.
        
        Args:
            path: Path to configuration file (default: ~/.cyber-red/layout.json).
        """
        config = LayoutConfig(
            left_width=self.left_width,
            center_width=self.center_width,
            right_width=self.right_width,
        )
        config.save(path)
