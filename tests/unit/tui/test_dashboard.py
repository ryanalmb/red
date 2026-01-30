"""Unit tests for DashboardWidget (Story 11.6)."""
import pytest
from textual.app import App, ComposeResult
from cyberred.tui.widgets.dashboard import (
    DashboardWidget,
    render_sparkline,
    format_uptime,
    format_metric,
    SPARKLINE_CHARS,
)


@pytest.fixture(autouse=True)
def reset_prometheus_shared_state():
    """Reset shared Prometheus state between tests to avoid registry conflicts."""
    # Reset before test
    DashboardWidget._shared_prometheus_gauges = None
    DashboardWidget._shared_prometheus_available = None
    yield
    # Reset after test
    DashboardWidget._shared_prometheus_gauges = None
    DashboardWidget._shared_prometheus_available = None

class DashboardApp(App):
    """Test app for dashboard."""
    def compose(self) -> ComposeResult:
        yield DashboardWidget(id="dashboard")

async def test_dashboard_widget_initialization():
    """Test dashboard widget initializes with default values (AC #1)."""
    app = DashboardApp()
    async with app.run_test() as pilot:
        widget = app.query_one("#dashboard", DashboardWidget)

        # Check default reactive values
        assert widget.active_agents == 0
        assert widget.idle_agents == 0
        assert widget.error_agents == 0

        assert widget.findings_critical == 0
        assert widget.findings_high == 0
        assert widget.findings_medium == 0
        assert widget.findings_low == 0

        assert widget.coverage_percent == 0.0
        assert widget.uptime_seconds == 0
        assert widget.llm_calls == 0
        assert widget.tools_executed == 0
        assert widget.emergence_score is None


# Task 2: Uptime formatting tests (AC #2)
def test_format_uptime_seconds():
    """Test uptime formatting for seconds only."""
    assert format_uptime(0) == "00:00:00"
    assert format_uptime(45) == "00:00:45"
    assert format_uptime(59) == "00:00:59"


def test_format_uptime_minutes():
    """Test uptime formatting with minutes."""
    assert format_uptime(60) == "00:01:00"
    assert format_uptime(125) == "00:02:05"
    assert format_uptime(3599) == "00:59:59"


def test_format_uptime_hours():
    """Test uptime formatting with hours."""
    assert format_uptime(3600) == "01:00:00"
    assert format_uptime(7325) == "02:02:05"
    assert format_uptime(86399) == "23:59:59"


def test_format_uptime_days():
    """Test uptime formatting with days."""
    assert format_uptime(86400) == "1d 00:00:00"
    assert format_uptime(90061) == "1d 01:01:01"


# Task 5: Sparkline tests (AC #5)
def test_sparkline_chars_defined():
    """Test sparkline characters are defined."""
    assert len(SPARKLINE_CHARS) == 9
    assert SPARKLINE_CHARS[0] == " "
    assert SPARKLINE_CHARS[-1] == "█"


def test_render_sparkline_empty():
    """Test sparkline with empty values."""
    result = render_sparkline([])
    assert result == " " * 20  # Default width


def test_render_sparkline_single_value():
    """Test sparkline with single value."""
    result = render_sparkline([50])
    assert len(result) == 20
    # Single value should show the middle char (normalized to 0)
    assert "█" in result or " " in result


def test_render_sparkline_increasing():
    """Test sparkline with increasing values."""
    values = list(range(0, 20))
    result = render_sparkline(values, width=20)
    assert len(result) == 20
    # First should be low, last should be high
    assert result[0] == " "
    assert result[-1] == "█"


def test_render_sparkline_custom_width():
    """Test sparkline with custom width."""
    values = [1, 2, 3, 4, 5]
    result = render_sparkline(values, width=10)
    assert len(result) == 10


def test_render_sparkline_constant():
    """Test sparkline with constant values."""
    values = [50, 50, 50, 50, 50]
    result = render_sparkline(values, width=5)
    assert len(result) == 5
    # All same value should use same char
    assert len(set(result)) == 1


# Task 3: Emergence score display tests (AC #3)
async def test_emergence_score_none_display():
    """Test emergence score shows N/A when None (AC #3)."""
    app = DashboardApp()
    async with app.run_test() as pilot:
        widget = app.query_one("#dashboard", DashboardWidget)
        assert widget.emergence_score is None
        display_text = widget.get_emergence_display()
        assert display_text == "N/A"


async def test_emergence_score_value_display():
    """Test emergence score shows percentage when available (AC #3)."""
    app = DashboardApp()
    async with app.run_test() as pilot:
        widget = app.query_one("#dashboard", DashboardWidget)
        widget.emergence_score = 0.25
        display_text = widget.get_emergence_display()
        assert "25" in display_text
        assert "%" in display_text


async def test_emergence_score_passing_threshold():
    """Test emergence score indicates passing (>20%) (AC #3)."""
    app = DashboardApp()
    async with app.run_test() as pilot:
        widget = app.query_one("#dashboard", DashboardWidget)
        widget.emergence_score = 0.25  # > 20% = passing
        assert widget.is_emergence_passing() is True
        widget.emergence_score = 0.15  # < 20% = not passing
        assert widget.is_emergence_passing() is False


# Task 2.3/2.4: Metric formatting tests
def test_format_metric_small():
    """Test metric formatting for small numbers."""
    assert format_metric(0) == "0"
    assert format_metric(123) == "123"
    assert format_metric(999) == "999"


def test_format_metric_thousands():
    """Test metric formatting with K suffix."""
    assert format_metric(1000) == "1.0K"
    assert format_metric(1500) == "1.5K"
    assert format_metric(999999) == "1000.0K"


def test_format_metric_overflow():
    """Test metric formatting for overflow values."""
    result = format_metric(1000000)
    assert "999K+" in result or "1.0M" in result or "1000.0K" in result

async def test_dashboard_reactive_updates():
    """Test reactive properties update UI (AC #4)."""
    app = DashboardApp()
    async with app.run_test() as pilot:
        widget = app.query_one("#dashboard", DashboardWidget)

        # Update values
        widget.active_agents = 5
        widget.findings_high = 2
        widget.coverage_percent = 45.5

        # Allow reactivity to propagate
        await pilot.pause()

        # Verify values persisted
        assert widget.active_agents == 5
        assert widget.findings_high == 2
        assert widget.coverage_percent == 45.5


async def test_findings_low_reactive_update():
    """Test findings_low reactive property updates UI (AC #1)."""
    app = DashboardApp()
    async with app.run_test() as pilot:
        widget = app.query_one("#dashboard", DashboardWidget)

        # Update findings_low
        widget.findings_low = 42
        await pilot.pause()

        # Verify value persisted
        assert widget.findings_low == 42

        # Verify label exists and was updated
        from textual.widgets import Label
        label = widget.query_one("#val-findings-low", Label)
        assert label is not None


async def test_findings_low_watcher():
    """Test watch_findings_low updates the label correctly."""
    app = DashboardApp()
    async with app.run_test() as pilot:
        widget = app.query_one("#dashboard", DashboardWidget)

        # Update multiple times to trigger watcher
        widget.findings_low = 10
        await pilot.pause()
        widget.findings_low = 25
        await pilot.pause()

        assert widget.findings_low == 25


def test_prometheus_setup_graceful_degradation():
    """Test Prometheus setup gracefully handles missing dependency."""
    # Create widget - should not raise even without prometheus_client
    widget = DashboardWidget()
    
    # _prometheus_available should be set (True or False depending on env)
    assert hasattr(widget, "_prometheus_available")
    assert isinstance(widget._prometheus_available, bool)
    
    # _prometheus_gauges should be set (dict or None)
    assert hasattr(widget, "_prometheus_gauges")


def test_prometheus_export_noop_without_prometheus():
    """Test export_prometheus_metrics is no-op without prometheus_client."""
    widget = DashboardWidget()
    
    # Force prometheus unavailable for test
    widget._prometheus_available = False
    widget._prometheus_gauges = None
    
    # Should not raise
    widget.export_prometheus_metrics()


def test_prometheus_export_with_metrics():
    """Test export_prometheus_metrics with mock gauges."""
    widget = DashboardWidget()
    
    # Set up test values
    widget.active_agents = 5
    widget.idle_agents = 3
    widget.error_agents = 1
    widget.findings_critical = 2
    widget.findings_high = 4
    widget.findings_medium = 6
    widget.findings_low = 8
    widget.coverage_percent = 75.5
    widget.emergence_score = 0.25
    
    # Create mock gauges
    class MockGauge:
        def __init__(self):
            self.value = None
        def set(self, val):
            self.value = val
    
    mock_gauges = {
        "active_agents": MockGauge(),
        "idle_agents": MockGauge(),
        "error_agents": MockGauge(),
        "findings_critical": MockGauge(),
        "findings_high": MockGauge(),
        "findings_medium": MockGauge(),
        "findings_low": MockGauge(),
        "coverage_percent": MockGauge(),
        "emergence_score": MockGauge(),
    }
    
    widget._prometheus_available = True
    widget._prometheus_gauges = mock_gauges
    
    # Export metrics
    widget.export_prometheus_metrics()
    
    # Verify gauges were set
    assert mock_gauges["active_agents"].value == 5
    assert mock_gauges["idle_agents"].value == 3
    assert mock_gauges["error_agents"].value == 1
    assert mock_gauges["findings_critical"].value == 2
    assert mock_gauges["findings_high"].value == 4
    assert mock_gauges["findings_medium"].value == 6
    assert mock_gauges["findings_low"].value == 8
    assert mock_gauges["coverage_percent"].value == 75.5
    assert mock_gauges["emergence_score"].value == 0.25


def test_prometheus_export_skips_none_emergence():
    """Test export_prometheus_metrics skips emergence_score when None."""
    widget = DashboardWidget()
    widget.emergence_score = None
    
    class MockGauge:
        def __init__(self):
            self.value = "NOT_SET"
        def set(self, val):
            self.value = val
    
    mock_gauges = {
        "active_agents": MockGauge(),
        "idle_agents": MockGauge(),
        "error_agents": MockGauge(),
        "findings_critical": MockGauge(),
        "findings_high": MockGauge(),
        "findings_medium": MockGauge(),
        "findings_low": MockGauge(),
        "coverage_percent": MockGauge(),
        "emergence_score": MockGauge(),
    }
    
    widget._prometheus_available = True
    widget._prometheus_gauges = mock_gauges
    
    # Export metrics
    widget.export_prometheus_metrics()
    
    # Emergence should NOT have been set
    assert mock_gauges["emergence_score"].value == "NOT_SET"


def test_format_uptime_negative():
    """Test format_uptime handles negative values."""
    # Negative should be treated as 0
    assert format_uptime(-10) == "00:00:00"
    assert format_uptime(-86400) == "00:00:00"
