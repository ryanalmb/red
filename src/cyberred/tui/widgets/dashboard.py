"""Engagement Statistics Dashboard Widget."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from textual.widgets import Static
from textual.reactive import reactive
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Label

if TYPE_CHECKING:
    from cyberred.tui.daemon_client import TUIClient

# Sparkline characters for trend display (AC #5)
SPARKLINE_CHARS = " ▁▂▃▄▅▆▇█"

# Emergence score threshold (NFR35)
EMERGENCE_THRESHOLD = 0.20


def format_uptime(seconds: int) -> str:
    """Format seconds into human-readable uptime string.

    Args:
        seconds: Number of seconds of uptime.

    Returns:
        Formatted string (HH:MM:SS or Nd HH:MM:SS for days).
    """
    if seconds < 0:
        seconds = 0

    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    if days > 0:
        return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_metric(value: int) -> str:
    """Format metric value with K suffix for large numbers.

    Args:
        value: The metric value to format.

    Returns:
        Formatted string (e.g., "123", "1.5K", "999K+").
    """
    if value < 1000:
        return str(value)
    elif value >= 1000000:
        return "999K+"
    else:
        return f"{value / 1000:.1f}K"


def render_sparkline(values: List[float], width: int = 20) -> str:
    """Render a sparkline from numeric values.

    Args:
        values: List of numeric values (most recent last).
        width: Number of characters to display.

    Returns:
        String of Unicode block characters representing trend.
    """
    if not values:
        return " " * width

    # Take last `width` values
    recent = values[-width:]

    # Handle constant values
    min_val = min(recent)
    max_val = max(recent)
    range_val = max_val - min_val

    if range_val == 0:
        # All same value - use middle char
        mid_char = SPARKLINE_CHARS[len(SPARKLINE_CHARS) // 2]
        return (mid_char * len(recent)).ljust(width)

    # Map to sparkline characters
    chars = []
    for v in recent:
        normalized = (v - min_val) / range_val
        idx = int(normalized * (len(SPARKLINE_CHARS) - 1))
        chars.append(SPARKLINE_CHARS[idx])

    return "".join(chars).ljust(width)


class DashboardWidget(Static):
    """Engagement statistics dashboard widget.

    UX Design Reference: Line 401 - F1 Dashboard
    """

    # Reactive properties for real-time updates (AC #1)
    active_agents = reactive(0)
    idle_agents = reactive(0)
    error_agents = reactive(0)

    # Finding counts by severity (AC #1)
    findings_critical = reactive(0)
    findings_high = reactive(0)
    findings_medium = reactive(0)
    findings_low = reactive(0)

    # Engagement metrics (AC #2)
    coverage_percent = reactive(0.0)
    uptime_seconds = reactive(0)
    llm_calls = reactive(0)
    tools_executed = reactive(0)

    # Emergence score (AC #3)
    emergence_score: reactive[Optional[float]] = reactive(None)

    # Internal state for uptime tracking (AC #4)
    _start_time: Optional[datetime] = None
    _uptime_task: Optional[asyncio.Task] = None
    _daemon_client: Optional["TUIClient"] = None
    
    # Prometheus metrics (optional, AC #4 subtask 4.3)
    _prometheus_available: bool = False
    _prometheus_gauges: Optional[dict] = None

    DEFAULT_CSS = """
    DashboardWidget {
        layer: overlay;
        width: 60%;
        height: 70%;
        align: center middle;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    .dashboard-title {
        text-align: center;
        text-style: bold;
        background: $primary;
        color: $text;
        padding: 0 1;
        margin-bottom: 1;
    }

    .metric-row {
        height: auto;
        margin-bottom: 1;
    }

    .metric-card {
        width: 1fr;
        height: auto;
        border: solid $secondary;
        padding: 0 1;
        margin: 0 1;
    }

    .metric-label {
        color: $text-muted;
    }

    .metric-value {
        text-style: bold;
        color: $accent;
    }

    .status-ok { color: $success; }
    .status-warning { color: $warning; }
    .status-error { color: $error; }

    .sparkline {
        color: $primary-lighten-2;
    }

    .emergence-passing { color: $success; }
    .emergence-failing { color: $warning; }
    """

    def __init__(
        self,
        daemon_client: Optional["TUIClient"] = None,
        *args,
        **kwargs,
    ) -> None:
        """Initialize DashboardWidget.

        Args:
            daemon_client: Optional TUIClient for daemon mode metrics.
        """
        super().__init__(*args, **kwargs)
        self._daemon_client = daemon_client
        self._start_time = datetime.now()
        self._uptime_task = None
        # Sparkline data buffers (AC #5) - initialized per-instance to avoid shared state
        self._agent_activity_history: List[int] = []
        self._findings_history: List[int] = []
        # Initialize Prometheus metrics (optional, graceful degradation)
        self._setup_prometheus_metrics()

    def on_mount(self) -> None:
        """Start uptime timer on mount (AC #4)."""
        self._start_time = datetime.now()
        self._uptime_task = asyncio.create_task(self._uptime_ticker())

    def on_unmount(self) -> None:
        """Stop uptime timer on unmount."""
        if self._uptime_task and not self._uptime_task.done():
            self._uptime_task.cancel()

    async def _uptime_ticker(self) -> None:
        """Update uptime every second (AC #4)."""
        try:
            while True:
                if self._start_time:
                    elapsed = datetime.now() - self._start_time
                    self.uptime_seconds = int(elapsed.total_seconds())
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    def compose(self) -> ComposeResult:
        """Create child widgets for the dashboard."""
        yield Label("ENGAGEMENT STATISTICS", classes="dashboard-title")

        with Vertical(id="metrics-container"):
            # Agent Status Row
            with Horizontal(classes="metric-row"):
                with Vertical(classes="metric-card"):
                    yield Label("Active Agents", classes="metric-label")
                    yield Label(str(self.active_agents), id="val-active-agents", classes="metric-value status-ok")
                with Vertical(classes="metric-card"):
                    yield Label("Idle Agents", classes="metric-label")
                    yield Label(str(self.idle_agents), id="val-idle-agents", classes="metric-value")
                with Vertical(classes="metric-card"):
                    yield Label("Error Agents", classes="metric-label")
                    yield Label(str(self.error_agents), id="val-error-agents", classes="metric-value status-error")

            # Findings Row
            with Horizontal(classes="metric-row"):
                with Vertical(classes="metric-card"):
                    yield Label("Critical Findings", classes="metric-label")
                    yield Label(str(self.findings_critical), id="val-findings-crit", classes="metric-value status-error")
                with Vertical(classes="metric-card"):
                    yield Label("High Findings", classes="metric-label")
                    yield Label(str(self.findings_high), id="val-findings-high", classes="metric-value status-warning")
                with Vertical(classes="metric-card"):
                    yield Label("Medium Findings", classes="metric-label")
                    yield Label(str(self.findings_medium), id="val-findings-med", classes="metric-value")
                with Vertical(classes="metric-card"):
                    yield Label("Low Findings", classes="metric-label")
                    yield Label(str(self.findings_low), id="val-findings-low", classes="metric-value status-ok")

            # Engagement Stats Row
            with Horizontal(classes="metric-row"):
                with Vertical(classes="metric-card"):
                    yield Label("Coverage", classes="metric-label")
                    yield Label(f"{self.coverage_percent:.1f}%", id="val-coverage", classes="metric-value")
                with Vertical(classes="metric-card"):
                    yield Label("Uptime", classes="metric-label")
                    yield Label(format_uptime(self.uptime_seconds), id="val-uptime", classes="metric-value")
                with Vertical(classes="metric-card"):
                    yield Label("LLM Calls", classes="metric-label")
                    yield Label(format_metric(self.llm_calls), id="val-llm-calls", classes="metric-value")

            # Tools & Emergence Row
            with Horizontal(classes="metric-row"):
                with Vertical(classes="metric-card"):
                    yield Label("Tools Executed", classes="metric-label")
                    yield Label(format_metric(self.tools_executed), id="val-tools-exec", classes="metric-value")
                with Vertical(classes="metric-card"):
                    yield Label("Emergence Score", classes="metric-label")
                    yield Label(self.get_emergence_display(), id="val-emergence", classes="metric-value")
                with Vertical(classes="metric-card"):
                    yield Label("Agent Activity", classes="metric-label")
                    yield Label(render_sparkline(self._agent_activity_history), id="val-sparkline-agents", classes="sparkline")

            # Sparkline Row
            with Horizontal(classes="metric-row"):
                with Vertical(classes="metric-card"):
                    yield Label("Findings Trend", classes="metric-label")
                    yield Label(render_sparkline(self._findings_history), id="val-sparkline-findings", classes="sparkline")

    def get_emergence_display(self) -> str:
        """Get formatted emergence score display (AC #3).

        Returns:
            "N/A" if score not calculated, otherwise percentage string.
        """
        if self.emergence_score is None:
            return "N/A"
        percentage = self.emergence_score * 100
        passing = "✓" if self.is_emergence_passing() else "✗"
        return f"{percentage:.1f}% {passing}"

    def is_emergence_passing(self) -> bool:
        """Check if emergence score passes threshold (>20%, NFR35).

        Returns:
            True if score >= 20%, False otherwise.
        """
        if self.emergence_score is None:
            return False
        return self.emergence_score >= EMERGENCE_THRESHOLD

    def add_agent_activity_sample(self, active_count: int) -> None:
        """Add sample to agent activity history for sparkline (AC #5).

        Args:
            active_count: Current number of active agents.
        """
        self._agent_activity_history.append(active_count)
        # Keep last 60 samples
        if len(self._agent_activity_history) > 60:
            self._agent_activity_history = self._agent_activity_history[-60:]
        self._update_sparklines()

    def add_findings_sample(self, total_findings: int) -> None:
        """Add sample to findings history for sparkline (AC #5).

        Args:
            total_findings: Current total findings count.
        """
        self._findings_history.append(total_findings)
        # Keep last 60 samples
        if len(self._findings_history) > 60:
            self._findings_history = self._findings_history[-60:]
        self._update_sparklines()

    def _update_sparklines(self) -> None:
        """Update sparkline displays."""
        try:
            self.query_one("#val-sparkline-agents", Label).update(
                render_sparkline(self._agent_activity_history)
            )
            self.query_one("#val-sparkline-findings", Label).update(
                render_sparkline(self._findings_history)
            )
        except Exception:
            pass

    # Class-level Prometheus gauges (shared across instances to avoid registry conflicts)
    _shared_prometheus_gauges: Optional[dict] = None
    _shared_prometheus_available: Optional[bool] = None

    def _setup_prometheus_metrics(self) -> None:
        """Setup Prometheus gauges for dashboard metrics (AC #4 subtask 4.3).
        
        Gracefully degrades if prometheus_client is not available.
        Uses class-level shared gauges to avoid CollectorRegistry conflicts.
        """
        # Use shared gauges if already initialized
        if DashboardWidget._shared_prometheus_available is not None:
            self._prometheus_available = DashboardWidget._shared_prometheus_available
            self._prometheus_gauges = DashboardWidget._shared_prometheus_gauges
            return

        try:
            from prometheus_client import Gauge
            
            # Helper to get or create a gauge (handles re-registration gracefully)
            def get_or_create_gauge(name: str, description: str) -> Gauge:
                """Get existing gauge or create new one."""
                try:
                    return Gauge(name, description)
                except ValueError:
                    # Gauge already registered - this is fine, just skip
                    # We'll use a simple wrapper that's a no-op for duplicate registrations
                    class NoOpGauge:
                        """No-op gauge for when registration fails."""
                        def set(self, value):
                            pass
                    return NoOpGauge()
            
            DashboardWidget._shared_prometheus_gauges = {
                "active_agents": get_or_create_gauge(
                    "cyberred_active_agents", "Number of active agents"
                ),
                "idle_agents": get_or_create_gauge(
                    "cyberred_idle_agents", "Number of idle agents"
                ),
                "error_agents": get_or_create_gauge(
                    "cyberred_error_agents", "Number of agents in error state"
                ),
                "findings_critical": get_or_create_gauge(
                    "cyberred_findings_critical", "Number of critical findings"
                ),
                "findings_high": get_or_create_gauge(
                    "cyberred_findings_high", "Number of high severity findings"
                ),
                "findings_medium": get_or_create_gauge(
                    "cyberred_findings_medium", "Number of medium severity findings"
                ),
                "findings_low": get_or_create_gauge(
                    "cyberred_findings_low", "Number of low severity findings"
                ),
                "coverage_percent": get_or_create_gauge(
                    "cyberred_coverage_percent", "Engagement coverage percentage"
                ),
                "emergence_score": get_or_create_gauge(
                    "cyberred_emergence_score", "Emergence score (0.0-1.0)"
                ),
            }
            DashboardWidget._shared_prometheus_available = True
            self._prometheus_available = True
            self._prometheus_gauges = DashboardWidget._shared_prometheus_gauges
        except ImportError:
            DashboardWidget._shared_prometheus_available = False
            DashboardWidget._shared_prometheus_gauges = None
            self._prometheus_available = False
            self._prometheus_gauges = None

    def export_prometheus_metrics(self) -> None:
        """Export current metrics to Prometheus gauges.
        
        Call this periodically to update Prometheus metrics.
        No-op if prometheus_client is not available.
        """
        if not self._prometheus_available or self._prometheus_gauges is None:
            return
        
        self._prometheus_gauges["active_agents"].set(self.active_agents)
        self._prometheus_gauges["idle_agents"].set(self.idle_agents)
        self._prometheus_gauges["error_agents"].set(self.error_agents)
        self._prometheus_gauges["findings_critical"].set(self.findings_critical)
        self._prometheus_gauges["findings_high"].set(self.findings_high)
        self._prometheus_gauges["findings_medium"].set(self.findings_medium)
        self._prometheus_gauges["findings_low"].set(self.findings_low)
        self._prometheus_gauges["coverage_percent"].set(self.coverage_percent)
        if self.emergence_score is not None:
            self._prometheus_gauges["emergence_score"].set(self.emergence_score)

    # Watchers to update labels when reactive properties change
    def watch_active_agents(self, value: int) -> None:
        try:
            self.query_one("#val-active-agents", Label).update(str(value))
        except Exception:
            pass

    def watch_idle_agents(self, value: int) -> None:
        try:
            self.query_one("#val-idle-agents", Label).update(str(value))
        except Exception:
            pass

    def watch_error_agents(self, value: int) -> None:
        try:
            self.query_one("#val-error-agents", Label).update(str(value))
        except Exception:
            pass

    def watch_findings_critical(self, value: int) -> None:
        try:
            self.query_one("#val-findings-crit", Label).update(str(value))
        except Exception:
            pass

    def watch_findings_high(self, value: int) -> None:
        try:
            self.query_one("#val-findings-high", Label).update(str(value))
        except Exception:
            pass

    def watch_findings_medium(self, value: int) -> None:
        try:
            self.query_one("#val-findings-med", Label).update(str(value))
        except Exception:
            pass

    def watch_findings_low(self, value: int) -> None:
        try:
            self.query_one("#val-findings-low", Label).update(str(value))
        except Exception:
            pass

    def watch_coverage_percent(self, value: float) -> None:
        try:
            self.query_one("#val-coverage", Label).update(f"{value:.1f}%")
        except Exception:
            pass

    def watch_uptime_seconds(self, value: int) -> None:
        try:
            self.query_one("#val-uptime", Label).update(format_uptime(value))
        except Exception:
            pass

    def watch_llm_calls(self, value: int) -> None:
        try:
            self.query_one("#val-llm-calls", Label).update(format_metric(value))
        except Exception:
            pass

    def watch_tools_executed(self, value: int) -> None:
        try:
            self.query_one("#val-tools-exec", Label).update(format_metric(value))
        except Exception:
            pass

    def watch_emergence_score(self, value: Optional[float]) -> None:
        try:
            label = self.query_one("#val-emergence", Label)
            label.update(self.get_emergence_display())
            # Update style based on passing/failing
            label.remove_class("emergence-passing", "emergence-failing")
            if value is not None:
                if self.is_emergence_passing():
                    label.add_class("emergence-passing")
                else:
                    label.add_class("emergence-failing")
        except Exception:
            pass
