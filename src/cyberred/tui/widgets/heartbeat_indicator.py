"""HeartbeatIndicator Widget for C2 heartbeat status display.

Story 9.10: Drop Box Status Panel - Task 1

Displays C2 heartbeat status with latency-based indicators:
- ● healthy (<500ms)
- ◐ degraded (500-2000ms)
- ○ critical (>2000ms)

Also tracks missed heartbeats with warning thresholds:
- 3 missed: Yellow warning
- 6 missed: Red critical

Per UX spec line 360 and 511.
"""
from __future__ import annotations

from textual.widgets import Static
from textual.reactive import reactive


class HeartbeatIndicator(Static):
    """C2 heartbeat status indicator with latency granularity.
    
    Per UX spec line 360 and 511:
    - ● healthy (<500ms)
    - ◐ degraded (500-2000ms)
    - ○ critical (>2000ms)
    - Pulse animation on successful heartbeat (5s cycle)
    
    Attributes:
        latency_ms: Current latency in milliseconds, None if unknown.
        missed_heartbeats: Count of consecutive missed heartbeats.
    
    Constants:
        HEALTHY_THRESHOLD_MS: Threshold for healthy status (500ms).
        DEGRADED_THRESHOLD_MS: Threshold for degraded status (2000ms).
        WARNING_MISSED_COUNT: Missed count for warning (3).
        CRITICAL_MISSED_COUNT: Missed count for critical (6).
    """
    
    # Latency thresholds per UX spec
    HEALTHY_THRESHOLD_MS: int = 500
    DEGRADED_THRESHOLD_MS: int = 2000
    
    # Missed heartbeat thresholds per story AC #4, #5
    WARNING_MISSED_COUNT: int = 3
    CRITICAL_MISSED_COUNT: int = 6
    
    # Indicator symbols
    SYMBOL_HEALTHY: str = "●"
    SYMBOL_DEGRADED: str = "◐"
    SYMBOL_CRITICAL: str = "○"
    
    # Reactive properties for state tracking
    latency_ms: reactive[int | None] = reactive(None)
    missed_heartbeats: reactive[int] = reactive(0)
    
    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize HeartbeatIndicator.
        
        Args:
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
    
    def compute_indicator(self) -> str:
        """Compute visual indicator symbol based on latency.
        
        Returns:
            Indicator symbol:
            - ● for healthy (<500ms)
            - ◐ for degraded (500-2000ms)
            - ○ for critical (>=2000ms or unknown)
        """
        if self.latency_ms is None:
            return self.SYMBOL_CRITICAL  # Unknown/disconnected
        elif self.latency_ms < self.HEALTHY_THRESHOLD_MS:
            return self.SYMBOL_HEALTHY
        elif self.latency_ms < self.DEGRADED_THRESHOLD_MS:
            return self.SYMBOL_DEGRADED
        else:
            return self.SYMBOL_CRITICAL
    
    def compute_css_class(self) -> str:
        """Compute CSS class for styling based on state.
        
        Missed heartbeats take precedence over latency-based status.
        
        Returns:
            CSS class name:
            - "heartbeat-critical": 6+ missed or >2000ms latency
            - "heartbeat-warning": 3-5 missed
            - "heartbeat-unknown": No latency data
            - "heartbeat-healthy": <500ms latency, <3 missed
            - "heartbeat-degraded": 500-2000ms latency
        """
        # Missed heartbeats take precedence (AC #4, #5)
        if self.missed_heartbeats >= self.CRITICAL_MISSED_COUNT:
            return "heartbeat-critical"
        elif self.missed_heartbeats >= self.WARNING_MISSED_COUNT:
            return "heartbeat-warning"
        
        # Latency-based status
        if self.latency_ms is None:
            return "heartbeat-unknown"
        elif self.latency_ms < self.HEALTHY_THRESHOLD_MS:
            return "heartbeat-healthy"
        elif self.latency_ms < self.DEGRADED_THRESHOLD_MS:
            return "heartbeat-degraded"
        else:
            return "heartbeat-critical"
    
    def on_heartbeat(self, latency_ms: int) -> None:
        """Handle successful heartbeat.
        
        Updates latency and resets missed heartbeat counter.
        Triggers pulse animation class.
        
        Args:
            latency_ms: Measured latency in milliseconds.
        """
        self.latency_ms = latency_ms
        self.missed_heartbeats = 0
        # Trigger pulse animation
        self.add_class("pulse")
        # Remove pulse class after animation (handled by CSS or timer)
        self.refresh()
    
    def on_heartbeat_missed(self) -> None:
        """Handle missed heartbeat.
        
        Increments the missed heartbeat counter.
        """
        self.missed_heartbeats += 1
        self.refresh()
    
    def get_warning_message(self) -> str | None:
        """Get warning message based on missed heartbeat count.
        
        Returns:
            Warning message string or None/empty if no warning.
            - "3 missed heartbeats" for warning state (AC #4)
            - "6 missed heartbeats - connection critical" for critical (AC #5)
        """
        if self.missed_heartbeats >= self.CRITICAL_MISSED_COUNT:
            return f"{self.missed_heartbeats} missed heartbeats - connection critical"
        elif self.missed_heartbeats >= self.WARNING_MISSED_COUNT:
            return f"{self.missed_heartbeats} missed heartbeats"
        return ""
    
    def render(self) -> str:
        """Render the heartbeat indicator display.
        
        Returns:
            Formatted string with indicator symbol and latency.
        """
        indicator = self.compute_indicator()
        css_class = self.compute_css_class()
        
        # Update CSS classes
        self.remove_class(
            "heartbeat-healthy",
            "heartbeat-degraded",
            "heartbeat-critical",
            "heartbeat-warning",
            "heartbeat-unknown",
        )
        self.add_class(css_class)
        
        # Build display string
        if self.latency_ms is not None:
            latency_str = f"{self.latency_ms}ms"
        else:
            latency_str = "---"
        
        # Include warning message if applicable
        warning = self.get_warning_message()
        if warning:
            return f"{indicator} {latency_str} ({warning})"
        
        return f"{indicator} {latency_str}"
