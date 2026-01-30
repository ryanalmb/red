"""Integration tests for DashboardWidget (Story 11.6)."""
import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from cyberred.tui.widgets.dashboard import DashboardWidget


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


class DashboardIntegrationApp(App):
    """Test app for dashboard integration tests."""

    BINDINGS = [("f1", "dashboard", "Dashboard")]

    def compose(self) -> ComposeResult:
        yield Static("Main Content", id="main-content")
        dashboard = DashboardWidget(id="dashboard-widget")
        dashboard.display = False
        yield dashboard

    def action_dashboard(self) -> None:
        """Toggle dashboard visibility."""
        try:
            dashboard = self.query_one("#dashboard-widget", DashboardWidget)
            dashboard.display = not dashboard.display
        except Exception:
            pass


async def test_dashboard_f1_toggle():
    """Test F1 key toggles dashboard visibility (AC #1)."""
    app = DashboardIntegrationApp()
    async with app.run_test() as pilot:
        # Dashboard should be hidden by default
        dashboard = app.query_one("#dashboard-widget", DashboardWidget)
        assert dashboard.display is False

        # Press F1 to show dashboard
        await pilot.press("f1")
        await pilot.pause()
        assert dashboard.display is True

        # Press F1 again to hide dashboard
        await pilot.press("f1")
        await pilot.pause()
        assert dashboard.display is False


async def test_dashboard_agent_count_sync():
    """Test dashboard shows correct agent counts (AC #1)."""
    app = DashboardIntegrationApp()
    async with app.run_test() as pilot:
        dashboard = app.query_one("#dashboard-widget", DashboardWidget)

        # Update agent counts
        dashboard.active_agents = 5
        dashboard.idle_agents = 3
        dashboard.error_agents = 2

        await pilot.pause()

        # Verify values are set correctly
        assert dashboard.active_agents == 5
        assert dashboard.idle_agents == 3
        assert dashboard.error_agents == 2


async def test_dashboard_finding_stream_sync():
    """Test dashboard updates finding counts (AC #1)."""
    app = DashboardIntegrationApp()
    async with app.run_test() as pilot:
        dashboard = app.query_one("#dashboard-widget", DashboardWidget)

        # Update finding counts
        dashboard.findings_critical = 1
        dashboard.findings_high = 5
        dashboard.findings_medium = 10
        dashboard.findings_low = 20

        await pilot.pause()

        # Verify values
        assert dashboard.findings_critical == 1
        assert dashboard.findings_high == 5
        assert dashboard.findings_medium == 10
        assert dashboard.findings_low == 20


async def test_dashboard_emergence_score_integration():
    """Test emergence score display integration (AC #3)."""
    app = DashboardIntegrationApp()
    async with app.run_test() as pilot:
        dashboard = app.query_one("#dashboard-widget", DashboardWidget)

        # Initially None
        assert dashboard.emergence_score is None
        assert dashboard.get_emergence_display() == "N/A"
        assert dashboard.is_emergence_passing() is False

        # Set passing score
        dashboard.emergence_score = 0.25
        await pilot.pause()

        assert "25" in dashboard.get_emergence_display()
        assert dashboard.is_emergence_passing() is True

        # Set failing score
        dashboard.emergence_score = 0.15
        await pilot.pause()

        assert "15" in dashboard.get_emergence_display()
        assert dashboard.is_emergence_passing() is False


async def test_dashboard_sparkline_sample_collection():
    """Test sparkline data collection (AC #5)."""
    app = DashboardIntegrationApp()
    async with app.run_test() as pilot:
        dashboard = app.query_one("#dashboard-widget", DashboardWidget)

        # Add samples
        for i in range(10):
            dashboard.add_agent_activity_sample(i * 2)
            dashboard.add_findings_sample(i * 5)

        await pilot.pause()

        # Verify history is recorded
        assert len(dashboard._agent_activity_history) == 10
        assert len(dashboard._findings_history) == 10
        assert dashboard._agent_activity_history[-1] == 18
        assert dashboard._findings_history[-1] == 45


async def test_dashboard_sparkline_rolling_window():
    """Test sparkline maintains 60-sample rolling window (AC #5)."""
    app = DashboardIntegrationApp()
    async with app.run_test() as pilot:
        dashboard = app.query_one("#dashboard-widget", DashboardWidget)

        # Add more than 60 samples
        for i in range(70):
            dashboard.add_agent_activity_sample(i)

        await pilot.pause()

        # Should only keep last 60
        assert len(dashboard._agent_activity_history) == 60
        assert dashboard._agent_activity_history[0] == 10  # First kept sample
        assert dashboard._agent_activity_history[-1] == 69  # Last sample


async def test_dashboard_metrics_display():
    """Test engagement metrics display (AC #2)."""
    app = DashboardIntegrationApp()
    async with app.run_test() as pilot:
        dashboard = app.query_one("#dashboard-widget", DashboardWidget)

        # Set metrics
        dashboard.coverage_percent = 75.5
        dashboard.llm_calls = 1500
        dashboard.tools_executed = 250

        await pilot.pause()

        # Verify values are set
        assert dashboard.coverage_percent == 75.5
        assert dashboard.llm_calls == 1500
        assert dashboard.tools_executed == 250


async def test_dashboard_uptime_auto_increment():
    """Test uptime auto-increments (AC #4)."""
    import asyncio

    app = DashboardIntegrationApp()
    async with app.run_test() as pilot:
        dashboard = app.query_one("#dashboard-widget", DashboardWidget)
        dashboard.display = True

        # Wait for uptime to increment
        initial_uptime = dashboard.uptime_seconds
        await asyncio.sleep(1.2)
        await pilot.pause()

        # Uptime should have increased
        assert dashboard.uptime_seconds >= initial_uptime + 1
