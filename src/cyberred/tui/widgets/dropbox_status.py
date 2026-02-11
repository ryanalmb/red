"""DropBoxStatusPanel Widget for drop box status display.

Story 9.10: Drop Box Status Panel - Task 2, 5
Story 12.9: Pre-Flight Protocol - Task 5 (pre-flight status display)

Displays drop box status including:
- Connection status (Connected/Disconnected/Reconnecting)
- Last heartbeat timestamp with relative time
- Uptime duration
- Network info (IP, port, protocol)
- HeartbeatIndicator widget for visual status
- Pre-flight status (Not Started/In Progress/Ready/Not Ready)

Per FR12 and UX spec line 360.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from cyberred.c2.preflight import PreFlightResult, PreFlightStatus

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static
from textual.reactive import reactive

from .heartbeat_indicator import HeartbeatIndicator


class ConnectionState(Enum):
    """Drop box connection state.
    
    Per FR12: C2 link health monitoring.
    """
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    UNKNOWN = "unknown"


@dataclass
class DropBoxStatus:
    """Drop box status data model.
    
    Per FR12: C2 link health monitoring.
    
    Attributes:
        connection_state: Current connection state.
        last_heartbeat: Timestamp of last heartbeat, or None.
        uptime_start: Timestamp when connection started, or None.
        network_info: Network info string (IP:port/protocol), or None.
        latency_ms: Current latency in milliseconds, or None.
        missed_heartbeats: Count of consecutive missed heartbeats.
    """
    connection_state: ConnectionState
    last_heartbeat: Optional[datetime]
    uptime_start: Optional[datetime]
    network_info: Optional[str]
    latency_ms: Optional[int]
    missed_heartbeats: int = 0
    
    @property
    def is_healthy(self) -> bool:
        """Check if drop box is healthy (<500ms, no missed heartbeats).
        
        Returns:
            True if connected with good latency and few missed heartbeats.
        """
        return (
            self.connection_state == ConnectionState.CONNECTED
            and self.latency_ms is not None
            and self.latency_ms < 500
            and self.missed_heartbeats < 3
        )
    
    @property
    def is_degraded(self) -> bool:
        """Check if drop box is degraded (500-2000ms or 3+ missed).
        
        Returns:
            True if connection is degraded but not critical.
        """
        if self.connection_state != ConnectionState.CONNECTED:
            return False
        
        latency_degraded = (
            self.latency_ms is not None 
            and 500 <= self.latency_ms < 2000
        )
        missed_degraded = 3 <= self.missed_heartbeats < 6
        
        return latency_degraded or missed_degraded
    
    @property
    def is_critical(self) -> bool:
        """Check if drop box is critical (>2000ms or 6+ missed).
        
        Returns:
            True if connection is in critical state.
        """
        if self.connection_state != ConnectionState.CONNECTED:
            return True
        
        latency_critical = (
            self.latency_ms is not None 
            and self.latency_ms >= 2000
        )
        missed_critical = self.missed_heartbeats >= 6
        
        return latency_critical or missed_critical


class DropBoxStatusPanel(Container):
    """Drop box status panel showing C2 link health.
    
    Per FR12 and UX spec line 360:
    - Connection status
    - Last heartbeat timestamp
    - Uptime duration
    - Network info
    - HeartbeatIndicator widget
    
    Attributes:
        connection_status: Current connection status string.
        last_heartbeat_display: Formatted last heartbeat time.
        uptime_display: Formatted uptime duration.
        network_info_display: Network info string.
        latency_ms: Current latency in milliseconds.
    """
    
    DEFAULT_CSS = """
    DropBoxStatusPanel {
        padding: 1 2;
        border: solid $primary;
        height: auto;
    }
    
    DropBoxStatusPanel .panel-title {
        text-style: bold;
        margin-bottom: 1;
    }
    
    DropBoxStatusPanel .status-row {
        height: 1;
        margin-bottom: 0;
    }
    
    DropBoxStatusPanel .status-label {
        width: 18;
        color: $text-muted;
    }
    
    DropBoxStatusPanel .status-value {
        width: auto;
    }
    """
    
    # Reactive properties for display
    connection_status: reactive[str] = reactive("Unknown")
    last_heartbeat_display: reactive[str] = reactive("Never")
    uptime_display: reactive[str] = reactive("---")
    network_info_display: reactive[str] = reactive("---")
    latency_ms: reactive[Optional[int]] = reactive(None)
    preflight_status_display: reactive[str] = reactive("Not Started")
    
    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize DropBoxStatusPanel.
        
        Args:
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._heartbeat_indicator: Optional[HeartbeatIndicator] = None
        self._current_status: Optional[DropBoxStatus] = None
    
    def compose(self) -> ComposeResult:
        """Compose the panel layout."""
        yield Static("Drop Box Status", classes="panel-title")
        yield Static("", id="connection-status", classes="status-row")
        yield HeartbeatIndicator(id="heartbeat")
        yield Static("", id="last-heartbeat", classes="status-row")
        yield Static("", id="uptime", classes="status-row")
        yield Static("", id="network-info", classes="status-row")
        yield Static("", id="preflight-status", classes="status-row")
    
    def on_mount(self) -> None:
        """Handle mount event - update initial display."""
        self._update_display()
    
    def update_status(self, status: DropBoxStatus) -> None:
        """Update panel with new drop box status.
        
        Args:
            status: New DropBoxStatus data.
        """
        self._current_status = status
        
        # Update connection status
        self.connection_status = self._format_connection_state(status.connection_state)
        
        # Update last heartbeat
        self.last_heartbeat_display = self._format_relative_time(status.last_heartbeat)
        
        # Update uptime
        self.uptime_display = self._format_duration(status.uptime_start)
        
        # Update network info
        self.network_info_display = status.network_info or "---"
        
        # Update latency
        self.latency_ms = status.latency_ms
        
        # Update heartbeat indicator if mounted
        self._update_heartbeat_indicator(status)
        
        # Update display
        self._update_display()
    
    def _update_heartbeat_indicator(self, status: DropBoxStatus) -> None:
        """Update the HeartbeatIndicator widget with status data.
        
        Args:
            status: Current DropBoxStatus.
        """
        from textual.css.query import NoMatches
        try:
            heartbeat = self.query_one("#heartbeat", HeartbeatIndicator)
            if status.latency_ms is not None:
                heartbeat.on_heartbeat(status.latency_ms)
            heartbeat.missed_heartbeats = status.missed_heartbeats
        except NoMatches:
            # Widget not mounted yet
            pass
    
    def _update_display(self) -> None:
        """Update the display widgets with current values."""
        from textual.css.query import NoMatches
        try:
            self.query_one("#connection-status", Static).update(
                f"Status: {self.connection_status}"
            )
            self.query_one("#last-heartbeat", Static).update(
                f"Last Heartbeat: {self.last_heartbeat_display}"
            )
            self.query_one("#uptime", Static).update(
                f"Uptime: {self.uptime_display}"
            )
            self.query_one("#network-info", Static).update(
                f"Network: {self.network_info_display}"
            )
            self.query_one("#preflight-status", Static).update(
                f"Pre-Flight: {self.preflight_status_display}"
            )
        except NoMatches:
            # Widgets not mounted yet
            pass

    def update_preflight_status(self, result: "PreFlightResult") -> None:
        """Update panel with pre-flight validation result.

        Story 12.9: Pre-Flight Protocol - Task 5.

        Args:
            result: PreFlightResult from pre-flight validation.
        """
        self.preflight_status_display = self._format_preflight_status(result)
        self._update_display()

    def _format_preflight_status(self, result: "PreFlightResult") -> str:
        """Format pre-flight result for display.

        Args:
            result: PreFlightResult to format.

        Returns:
            Formatted string like "✓ Ready (645ms)" or "✗ Not Ready (PING failed)".
        """
        from cyberred.c2.preflight import PreFlightStatus, StepStatus

        if result.overall_status == PreFlightStatus.READY:
            return f"✓ Ready ({result.total_duration_ms}ms)"
        elif result.overall_status == PreFlightStatus.IN_PROGRESS:
            return "⟳ In Progress..."
        elif result.overall_status == PreFlightStatus.NOT_READY:
            # Find the first failed step for context
            failed_step = next(
                (r for r in result.step_results if r.status in (StepStatus.FAIL, StepStatus.TIMEOUT)),
                None,
            )
            if failed_step:
                return f"✗ Not Ready ({failed_step.step.value} {failed_step.status.value})"
            return "✗ Not Ready"
        else:
            return "Not Started"
    
    def _format_connection_state(self, state: ConnectionState) -> str:
        """Format connection state for display.
        
        Args:
            state: ConnectionState enum value.
            
        Returns:
            Formatted state string (e.g., "Connected", "Disconnected").
        """
        state_map = {
            ConnectionState.CONNECTED: "Connected",
            ConnectionState.DISCONNECTED: "Disconnected",
            ConnectionState.RECONNECTING: "Reconnecting",
            ConnectionState.UNKNOWN: "Unknown",
        }
        return state_map.get(state, "Unknown")
    
    def _format_relative_time(self, timestamp: Optional[datetime]) -> str:
        """Format timestamp as relative time (e.g., "3s ago").
        
        Args:
            timestamp: Datetime to format, or None.
            
        Returns:
            Relative time string or "Never" if None.
        """
        if timestamp is None:
            return "Never"
        
        now = datetime.now(timezone.utc)
        # Ensure timestamp is timezone-aware
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        delta = now - timestamp
        seconds = int(delta.total_seconds())
        
        if seconds < 60:
            return f"{seconds}s ago"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours}h ago"
        else:
            days = seconds // 86400
            return f"{days}d ago"
    
    def _format_duration(self, start_time: Optional[datetime]) -> str:
        """Format duration since start time (e.g., "2:30:45" or "2d 5h").
        
        Args:
            start_time: Start timestamp, or None.
            
        Returns:
            Formatted duration string or "---" if None.
        """
        if start_time is None:
            return "---"
        
        now = datetime.now(timezone.utc)
        # Ensure timestamp is timezone-aware
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        
        delta = now - start_time
        total_seconds = int(delta.total_seconds())
        
        days = total_seconds // 86400
        remaining = total_seconds % 86400
        hours = remaining // 3600
        remaining = remaining % 3600
        minutes = remaining // 60
        seconds = remaining % 60
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        else:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
