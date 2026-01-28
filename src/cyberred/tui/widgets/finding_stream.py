"""Real-Time Finding Stream Widget.

Story 9.5: Real-Time Finding Stream

Implements a real-time finding stream that displays security findings as they
are discovered by agents. Features:
- Severity-based color coding (critical=red, high=orange, medium=yellow)
- Auto-scroll with pause toggle
- Click-to-detail interaction
- <500ms update latency
- FIFO eviction at configurable max findings

Display format per spec:
[timestamp] [severity_icon] [SEVERITY] [target] summary
[14:30:45] 🔴 [CRITICAL] 192.168.1.100:443 SQL Injection detected
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.widgets import RichLog, Static, Button
from textual.containers import Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.binding import Binding

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.events import Click

# Logger for latency warnings
_logger = logging.getLogger(__name__)

# Latency threshold in milliseconds (FR9 requirement)
LATENCY_THRESHOLD_MS = 500


class FindingSeverity(IntEnum):
    """Finding severity levels.
    
    Lower values = higher severity (critical first).
    Used for sorting and color-coding findings.
    """
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    INFO = 4


# Severity color mapping per UX spec
_SEVERITY_COLORS: dict[FindingSeverity, str] = {
    FindingSeverity.CRITICAL: "bright_red",
    FindingSeverity.HIGH: "orange3",
    FindingSeverity.MEDIUM: "yellow",
    FindingSeverity.LOW: "blue",
    FindingSeverity.INFO: "dim",
}

# Severity icon mapping per UX spec
_SEVERITY_ICONS: dict[FindingSeverity, str] = {
    FindingSeverity.CRITICAL: "🔴",
    FindingSeverity.HIGH: "🟠",
    FindingSeverity.MEDIUM: "🟡",
    FindingSeverity.LOW: "🔵",
    FindingSeverity.INFO: "ℹ️",
}


def get_severity_style(severity: FindingSeverity) -> str:
    """Get Rich style string for a severity level.
    
    Args:
        severity: Finding severity enum value.
        
    Returns:
        Rich style string (e.g., "bold bright_red").
    """
    color = _SEVERITY_COLORS.get(severity, "white")
    return f"bold {color}"


@dataclass(slots=True)
class Finding:
    """Represents a security finding discovered by an agent.
    
    Uses __slots__ for memory efficiency when handling many findings.
    Equality and hashing are based on the finding id.
    """
    id: str
    timestamp: datetime
    severity: FindingSeverity
    finding_type: str
    target: str
    summary: str
    details: dict = field(default_factory=dict)
    agent_id: str = ""
    
    @property
    def formatted_timestamp(self) -> str:
        """Return human-readable timestamp in HH:MM:SS format."""
        return self.timestamp.strftime("%H:%M:%S")
    
    def __hash__(self) -> int:
        """Hash based on finding id."""
        return hash(self.id)
    
    def __eq__(self, other: object) -> bool:
        """Equality based on finding id."""
        if not isinstance(other, Finding):
            return NotImplemented
        return self.id == other.id
    
    def __repr__(self) -> str:
        """Return useful representation string."""
        return f"Finding(id={self.id!r}, severity={self.severity.name}, target={self.target!r})"


class FindingDetailModal(ModalScreen):
    """Modal screen showing detailed finding information.
    
    Displays all finding fields including details JSON.
    Closes on Escape key or clicking the Close button.
    """
    
    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "dismiss", "Close"),
    ]
    
    DEFAULT_CSS: ClassVar[str] = """
    FindingDetailModal {
        align: center middle;
    }
    
    FindingDetailModal > Vertical {
        width: 60%;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    
    FindingDetailModal .title {
        text-style: bold;
        margin-bottom: 1;
    }
    
    FindingDetailModal .field {
        margin-bottom: 0;
    }
    
    FindingDetailModal .details {
        margin-top: 1;
        background: $surface-darken-1;
        padding: 1;
    }
    
    FindingDetailModal Button {
        margin-top: 1;
        width: 100%;
    }
    """
    
    def __init__(self, finding: Finding) -> None:
        """Initialize FindingDetailModal.
        
        Args:
            finding: The finding to display details for.
        """
        self.finding = finding
        super().__init__()
    
    def compose(self) -> "ComposeResult":
        """Compose the modal content."""
        with Vertical(id="detail-container"):
            yield Static(f"Finding: {self.finding.id}", classes="title")
            yield Static(f"Severity: {self.finding.severity.name}", classes="field")
            yield Static(f"Type: {self.finding.finding_type}", classes="field")
            yield Static(f"Target: {self.finding.target}", classes="field")
            yield Static(f"Summary: {self.finding.summary}", classes="field")
            yield Static(f"Agent: {self.finding.agent_id}", classes="field")
            yield Static(f"Time: {self.finding.timestamp}", classes="field")
            if self.finding.details:
                yield Static("Details:", classes="field")
                yield Static(json.dumps(self.finding.details, indent=2), classes="details")
            yield Button("Close", id="close-btn", variant="primary")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press to close modal."""
        if event.button.id == "close-btn":
            self.dismiss()


class FindingStream(RichLog):
    """Real-time finding stream widget.
    
    Displays security findings as they are discovered, with severity-based
    color coding and click-to-detail interaction.
    
    Features:
    - Severity-based color coding per UX spec
    - Auto-scroll with pause option (press 'p' to toggle)
    - FIFO eviction at max_findings limit
    - Line-to-finding index for click interaction
    - Click or Enter to view finding details
    - <500ms latency tracking with warning
    """
    
    DEFAULT_CSS: ClassVar[str] = """
    FindingStream {
        height: 100%;
        border: solid $accent;
    }
    
    FindingStream.finding-critical {
        color: $error;
    }
    
    FindingStream.finding-high {
        color: $warning;
    }
    
    FindingStream.finding-medium {
        color: yellow;
    }
    
    FindingStream.finding-low {
        color: $primary;
    }
    
    FindingStream.finding-info {
        color: $text-muted;
    }
    """
    
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("p", "toggle_pause", "Pause/Resume"),
        Binding("enter", "show_detail", "Show Detail"),
    ]
    
    class FindingReceived(Message):
        """Message sent when a new finding is received.
        
        Used for real-time updates from daemon connection.
        """
        def __init__(self, finding: Finding, discovery_time_ns: int | None = None) -> None:
            """Initialize FindingReceived message.
            
            Args:
                finding: The received finding.
                discovery_time_ns: Time of discovery in nanoseconds (time.time_ns()).
            """
            self.finding = finding
            self.discovery_time_ns = discovery_time_ns
            super().__init__()
    
    def __init__(
        self,
        *,
        max_findings: int = 1000,
        auto_scroll: bool = True,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize FindingStream widget.
        
        Args:
            max_findings: Maximum number of findings to retain (FIFO eviction).
            auto_scroll: Whether to auto-scroll to latest findings.
            name: Widget name.
            id: Widget DOM id.
            classes: Widget CSS classes.
        """
        super().__init__(
            highlight=True,
            markup=True,
            auto_scroll=auto_scroll,
            name=name,
            id=id,
            classes=classes,
        )
        self._findings: list[Finding] = []
        self._finding_index: dict[int, Finding] = {}
        self._max_findings = max_findings
        self._paused = False
        self._line_count = 0
        self._selected_line: int = -1
        self._last_latency_ms: int = 0
    
    @property
    def paused(self) -> bool:
        """Whether auto-scroll is paused."""
        return self._paused
    
    @paused.setter
    def paused(self, value: bool) -> None:
        """Set pause state and update auto_scroll accordingly."""
        self._paused = value
        self.auto_scroll = not value
        self.refresh()
    
    @property
    def border_title(self) -> str:
        """Return title with pause indicator if paused."""
        if self._paused:
            return "Finding Stream [PAUSED]"
        return "Finding Stream"
    
    def toggle_auto_scroll(self) -> None:
        """Toggle auto-scroll pause state."""
        self.paused = not self.paused
    
    def action_toggle_pause(self) -> None:
        """Action handler for 'p' key binding."""
        self.toggle_auto_scroll()
    
    def action_show_detail(self) -> None:
        """Action handler for 'Enter' key binding."""
        if self._selected_line >= 0:
            finding = self.get_finding_at_line(self._selected_line)
            if finding:
                self.app.push_screen(FindingDetailModal(finding))
        elif self._findings:
            # Show most recent finding if none selected
            self.app.push_screen(FindingDetailModal(self._findings[-1]))
    
    def on_click(self, event: "Click") -> None:
        """Handle click event to show finding detail.
        
        Args:
            event: The click event.
        """
        # Calculate line number from click position
        # RichLog uses scroll_y + event.y to determine line
        line = self.scroll_y + event.y
        self._selected_line = line
        finding = self.get_finding_at_line(line)
        if finding:
            self.app.push_screen(FindingDetailModal(finding))
    
    def add_finding(
        self,
        finding: Finding,
        discovery_time_ns: int | None = None,
    ) -> None:
        """Add a finding to the stream.
        
        Handles FIFO eviction if at capacity, updates the finding index,
        formats and displays the finding. Tracks latency and logs warning
        if >500ms.
        
        Args:
            finding: The finding to add.
            discovery_time_ns: Time of discovery in nanoseconds for latency tracking.
        """
        # Track latency if discovery time provided
        if discovery_time_ns is not None:
            display_time_ns = time.time_ns()
            self._last_latency_ms = (display_time_ns - discovery_time_ns) // 1_000_000
            if self._last_latency_ms > LATENCY_THRESHOLD_MS:
                _logger.warning(
                    "Finding display latency %dms exceeds %dms threshold for finding %s",
                    self._last_latency_ms,
                    LATENCY_THRESHOLD_MS,
                    finding.id,
                )
        
        # FIFO eviction if at capacity
        if len(self._findings) >= self._max_findings:
            self._findings.pop(0)
        
        self._findings.append(finding)
        self._finding_index[self._line_count] = finding
        self._line_count += 1
        
        # Format and display
        formatted = self.format_finding(finding)
        self.write(formatted)
    
    def format_finding(self, finding: Finding) -> Text:
        """Format a finding for display.
        
        Format: [timestamp] [icon] [SEVERITY] [target] summary
        
        Args:
            finding: The finding to format.
            
        Returns:
            Rich Text object with styled content.
        """
        color = _SEVERITY_COLORS[finding.severity]
        icon = _SEVERITY_ICONS[finding.severity]
        severity_name = finding.severity.name
        
        # Truncate summary if needed (max 60 chars)
        summary = finding.summary
        if len(summary) > 60:
            summary = summary[:57] + "..."
        
        text = Text()
        text.append(f"[{finding.formatted_timestamp}] ", style="dim")
        text.append(f"{icon} ", style=color)
        text.append(f"[{severity_name}] ", style=f"bold {color}")
        text.append(f"{finding.target} ", style="cyan")
        text.append(summary, style=color)
        
        return text
    
    def get_finding_at_line(self, line: int) -> Finding | None:
        """Get the finding at a specific line number.
        
        Args:
            line: The line number (0-indexed).
            
        Returns:
            The Finding at that line, or None if not found.
        """
        return self._finding_index.get(line)
    
    def on_finding_received(self, message: FindingReceived) -> None:
        """Handle FindingReceived message.
        
        Adds the finding from the message to the stream with latency tracking.
        
        Args:
            message: The FindingReceived message.
        """
        self.add_finding(message.finding, message.discovery_time_ns)
