"""Timeline Scrubber Widget for Engagement History.

Story 11.5: RAG Management Panel - AC #5

This module provides the TimelineScrubber widget for scrubbing through
engagement history and viewing key events.

Per UX Design:
- "Engagement history review — scroll through past events" (line 516)

Usage:
    from cyberred.tui.widgets.timeline import TimelineScrubber, TimelineMarker
    
    timeline = TimelineScrubber()
    timeline.add_marker(TimelineMarker(
        timestamp=datetime.now(),
        event_type="finding",
        label="Critical CVE found",
        severity="critical",
    ))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Callable, List, Optional

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static
from textual.containers import Horizontal

if TYPE_CHECKING:
    from textual.events import Key, Click


@dataclass
class TimelineMarker:
    """Marker on the timeline representing a key event.
    
    Attributes:
        timestamp: When the event occurred
        event_type: Type of event (finding, auth, strategy, rag)
        label: Short description for tooltip/display
        severity: Importance level (info, warning, critical)
        data: Optional additional data for the event
    """
    timestamp: datetime
    event_type: str  # "finding", "auth", "strategy", "rag"
    label: str
    severity: str = "info"  # "info", "warning", "critical"
    data: Optional[dict] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "label": self.label,
            "severity": self.severity,
            "data": self.data,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TimelineMarker":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=data["event_type"],
            label=data["label"],
            severity=data.get("severity", "info"),
            data=data.get("data"),
        )


class TimelineScrubber(Static):
    """Timeline widget for scrubbing through engagement history.
    
    Story 11.5 AC #5: Allow operator to scrub through engagement history
    via timeline, showing key events (findings, auth requests, strategy changes).
    
    The timeline displays:
    - A horizontal bar representing the engagement duration
    - Markers at positions where key events occurred
    - Current playback position indicator
    - Time labels at start/end
    
    Keyboard Controls:
    - Left/Right: Move position by 5%
    - Home/End: Jump to start/end
    - Enter: Select marker at current position
    
    Attributes:
        current_position: Position on timeline (0.0 to 1.0)
        markers: List of event markers on the timeline
        start_time: Engagement start time
        end_time: Engagement end time (or current time)
    """
    
    DEFAULT_CSS = """
    TimelineScrubber {
        height: 3;
        padding: 0 1;
    }
    
    TimelineScrubber .timeline-bar {
        height: 1;
    }
    
    TimelineScrubber .timeline-time {
        height: 1;
        text-style: dim;
    }
    
    TimelineScrubber .timeline-markers {
        height: 1;
    }
    """
    
    # Reactive property for current position (0.0 to 1.0)
    current_position: reactive[float] = reactive(0.0)
    
    # Marker icons by event type
    MARKER_ICONS = {
        "finding": "💡",
        "auth": "🔐",
        "strategy": "🎯",
        "rag": "📚",
    }
    
    # Severity colors (Rich markup)
    SEVERITY_STYLES = {
        "info": "cyan",
        "warning": "yellow",
        "critical": "red bold",
    }
    
    class PositionChanged(Message):
        """Message sent when timeline position changes."""
        
        def __init__(self, position: float, marker: Optional[TimelineMarker] = None) -> None:
            self.position = position
            self.marker = marker
            super().__init__()
    
    class MarkerSelected(Message):
        """Message sent when a marker is selected."""
        
        def __init__(self, marker: TimelineMarker) -> None:
            self.marker = marker
            super().__init__()
    
    def __init__(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        """Initialize TimelineScrubber.
        
        Args:
            start_time: Engagement start time (defaults to now)
            end_time: Engagement end time (defaults to now)
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._markers: List[TimelineMarker] = []
        self._start_time = start_time or datetime.now()
        self._end_time = end_time or datetime.now()
        self._bar_width = 60  # Characters for the timeline bar
    
    @property
    def markers(self) -> List[TimelineMarker]:
        """Return list of timeline markers."""
        return self._markers.copy()
    
    @property
    def start_time(self) -> datetime:
        """Return timeline start time."""
        return self._start_time
    
    @start_time.setter
    def start_time(self, value: datetime) -> None:
        """Set timeline start time."""
        self._start_time = value
        self._refresh_display()
    
    @property
    def end_time(self) -> datetime:
        """Return timeline end time."""
        return self._end_time
    
    @end_time.setter
    def end_time(self, value: datetime) -> None:
        """Set timeline end time."""
        self._end_time = value
        self._refresh_display()
    
    def compose(self) -> ComposeResult:
        """Compose the timeline widget."""
        yield Static("", id="timeline-markers", classes="timeline-markers")
        yield Static("", id="timeline-bar", classes="timeline-bar")
        yield Static("", id="timeline-time", classes="timeline-time")
    
    def on_mount(self) -> None:
        """Initialize display on mount."""
        self._refresh_display()
    
    def add_marker(self, marker: TimelineMarker) -> None:
        """Add an event marker to the timeline.
        
        Args:
            marker: TimelineMarker to add
        """
        self._markers.append(marker)
        # Keep markers sorted by timestamp
        self._markers.sort(key=lambda m: m.timestamp)
        
        # Extend timeline if marker is outside current range
        if marker.timestamp < self._start_time:
            self._start_time = marker.timestamp
        if marker.timestamp > self._end_time:
            self._end_time = marker.timestamp
        
        self._refresh_display()
    
    def add_markers(self, markers: List[TimelineMarker]) -> None:
        """Add multiple markers at once.
        
        Args:
            markers: List of markers to add
        """
        for marker in markers:
            self._markers.append(marker)
        self._markers.sort(key=lambda m: m.timestamp)
        
        # Update time bounds
        if self._markers:
            earliest = min(m.timestamp for m in self._markers)
            latest = max(m.timestamp for m in self._markers)
            if earliest < self._start_time:
                self._start_time = earliest
            if latest > self._end_time:
                self._end_time = latest
        
        self._refresh_display()
    
    def clear_markers(self) -> None:
        """Remove all markers from timeline."""
        self._markers.clear()
        self._refresh_display()
    
    def scrub_to(self, position: float) -> None:
        """Move timeline to position.
        
        Args:
            position: Position from 0.0 (start) to 1.0 (end)
        """
        new_pos = max(0.0, min(1.0, position))
        if new_pos != self.current_position:
            self.current_position = new_pos
            self._refresh_display()
            
            # Find nearest marker to current position
            marker = self._get_marker_at_position(new_pos)
            self.post_message(self.PositionChanged(new_pos, marker))
    
    def scrub_to_marker(self, marker: TimelineMarker) -> None:
        """Move timeline to a specific marker.
        
        Args:
            marker: Marker to scrub to
        """
        position = self._get_marker_position(marker)
        self.scrub_to(position)
    
    def on_key(self, event: "Key") -> None:
        """Handle keyboard navigation.
        
        Args:
            event: Key event
        """
        if event.key == "left":
            self.scrub_to(self.current_position - 0.05)
            event.stop()
        elif event.key == "right":
            self.scrub_to(self.current_position + 0.05)
            event.stop()
        elif event.key == "home":
            self.scrub_to(0.0)
            event.stop()
        elif event.key == "end":
            self.scrub_to(1.0)
            event.stop()
        elif event.key == "enter":
            marker = self._get_marker_at_position(self.current_position)
            if marker:
                self.post_message(self.MarkerSelected(marker))
            event.stop()
    
    def on_click(self, event: "Click") -> None:
        """Handle mouse click for scrubbing.
        
        Args:
            event: Click event
        """
        # Calculate position based on click x coordinate
        # Need width > 2 for meaningful bar (accounting for 1 char padding each side)
        if self.size.width > 2:
            # Account for padding
            relative_x = event.x - 1
            bar_width = self.size.width - 2  # Always > 0 since width > 2
            position = relative_x / bar_width
            self.scrub_to(position)
    
    def watch_current_position(self, new_value: float) -> None:
        """React to position changes."""
        self._refresh_display()
    
    def _get_marker_position(self, marker: TimelineMarker) -> float:
        """Get position (0.0-1.0) for a marker timestamp.
        
        Args:
            marker: Marker to get position for
            
        Returns:
            Position from 0.0 to 1.0
        """
        total_duration = (self._end_time - self._start_time).total_seconds()
        if total_duration <= 0:
            return 0.5  # All at center if no duration
        
        marker_offset = (marker.timestamp - self._start_time).total_seconds()
        return max(0.0, min(1.0, marker_offset / total_duration))
    
    def _get_marker_at_position(
        self,
        position: float,
        tolerance: float = 0.05,
    ) -> Optional[TimelineMarker]:
        """Find marker nearest to a position within tolerance.
        
        Args:
            position: Position to search at (0.0-1.0)
            tolerance: How close marker must be (default 5%)
            
        Returns:
            Nearest marker if within tolerance, None otherwise
        """
        if not self._markers:
            return None
        
        nearest_marker = None
        nearest_distance = float("inf")
        
        for marker in self._markers:
            marker_pos = self._get_marker_position(marker)
            distance = abs(marker_pos - position)
            if distance < nearest_distance and distance <= tolerance:
                nearest_distance = distance
                nearest_marker = marker
        
        return nearest_marker
    
    def _refresh_display(self) -> None:
        """Update the visual display."""
        try:
            markers_widget = self.query_one("#timeline-markers", Static)
            bar_widget = self.query_one("#timeline-bar", Static)
            time_widget = self.query_one("#timeline-time", Static)
        except Exception:
            return  # Not mounted yet
        
        # Build marker line
        marker_line = self._build_marker_line()
        markers_widget.update(marker_line)
        
        # Build timeline bar with position indicator
        bar_line = self._build_bar_line()
        bar_widget.update(bar_line)
        
        # Build time labels
        time_line = self._build_time_line()
        time_widget.update(time_line)
    
    def _build_marker_line(self) -> str:
        """Build the marker display line."""
        if not self._markers:
            return " " * self._bar_width
        
        # Create character array for markers
        chars = [" "] * self._bar_width
        
        for marker in self._markers:
            pos = self._get_marker_position(marker)
            index = int(pos * (self._bar_width - 1))
            index = max(0, min(self._bar_width - 1, index))
            
            icon = self.MARKER_ICONS.get(marker.event_type, "•")
            chars[index] = icon
        
        return "".join(chars)
    
    def _build_bar_line(self) -> str:
        """Build the timeline bar with position indicator."""
        # Create the bar
        bar_chars = ["─"] * self._bar_width
        
        # Add position indicator
        pos_index = int(self.current_position * (self._bar_width - 1))
        pos_index = max(0, min(self._bar_width - 1, pos_index))
        bar_chars[pos_index] = "▼"
        
        # Add start/end caps
        bar_chars[0] = "├"
        bar_chars[-1] = "┤"
        
        return "".join(bar_chars)
    
    def _build_time_line(self) -> str:
        """Build the time labels line."""
        start_str = self._start_time.strftime("%H:%M:%S")
        end_str = self._end_time.strftime("%H:%M:%S")
        
        # Calculate current time at position
        total_seconds = (self._end_time - self._start_time).total_seconds()
        current_offset = total_seconds * self.current_position
        from datetime import timedelta
        current_time = self._start_time + timedelta(seconds=current_offset)
        current_str = current_time.strftime("%H:%M:%S")
        
        # Build line with start, current (centered), and end
        padding = self._bar_width - len(start_str) - len(end_str)
        if padding < len(current_str) + 2:
            return f"{start_str}{' ' * max(1, padding)}{end_str}"
        
        # Center the current time
        left_pad = (padding - len(current_str)) // 2
        right_pad = padding - left_pad - len(current_str)
        
        return f"{start_str}{' ' * left_pad}{current_str}{' ' * right_pad}{end_str}"
    
    def get_time_at_position(self, position: float) -> datetime:
        """Get datetime at a timeline position.
        
        Args:
            position: Position from 0.0 to 1.0
            
        Returns:
            Datetime at that position
        """
        from datetime import timedelta
        total_seconds = (self._end_time - self._start_time).total_seconds()
        offset_seconds = total_seconds * position
        return self._start_time + timedelta(seconds=offset_seconds)
