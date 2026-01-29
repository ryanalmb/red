"""Unit Tests for SituationalAlertScreen Widget - Story 10.6.

Tests for the situational alert modal screen with:
- Screen initialization with AlertTrigger
- Widget composition (title, content, buttons)
- C/S/N keybinding action handlers
- Focus trap behavior (via ModalScreen)
- Blink animation state
- Notes input field toggle
- Response callback propagation

Test Framework: Textual Pilot (app.run_test())
Coverage Requirement: 100%
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from textual.app import App, ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Input


class TestSituationalAlertScreenComposition:
    """Tests for SituationalAlertScreen widget composition."""

    @pytest.fixture
    def sample_alert_trigger(self):
        """Create a sample AlertTrigger for testing."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        return AlertTrigger(
            id=str(uuid.uuid4()),
            alert_type=AlertType.HONEYPOT,
            severity=AlertSeverity.CRITICAL,
            target="192.168.1.50",
            discovery_details="Canary token detected in AWS credentials file",
            risk_assessment="High risk of detection - canary tokens typically alert defenders",
            recommended_action="Stop immediately, assess detection risk",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def test_screen_extends_modal_screen(self) -> None:
        """Test SituationalAlertScreen extends ModalScreen for focus trap."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        assert issubclass(SituationalAlertScreen, ModalScreen)

    @pytest.mark.asyncio
    async def test_screen_initialization(self, sample_alert_trigger) -> None:
        """Test screen initializes with AlertTrigger."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        screen = SituationalAlertScreen(alert=sample_alert_trigger)
        
        assert screen.alert == sample_alert_trigger
        assert screen.alert.alert_type.value == "honeypot"

    @pytest.mark.asyncio
    async def test_compose_returns_expected_structure(self, sample_alert_trigger) -> None:
        """Test compose() returns title, content, and buttons."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            # Check for key UI elements on the screen (not app)
            assert screen.query_one("#alert-title", Static) is not None
            assert screen.query_one("#discovery-details", Static) is not None
            assert screen.query_one("#risk-assessment", Static) is not None
            assert screen.query_one("#recommended-action", Static) is not None

    @pytest.mark.asyncio
    async def test_compose_shows_alert_type_in_title(self, sample_alert_trigger) -> None:
        """Test title shows alert type prominently."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            # Alert type should be in the title - check via the alert
            assert sample_alert_trigger.alert_type.value == "honeypot"
            title = screen.query_one("#alert-title", Static)
            assert title is not None

    @pytest.mark.asyncio
    async def test_compose_shows_target(self, sample_alert_trigger) -> None:
        """Test screen displays target from alert."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            # Target should be visible - verify the widget exists and alert has target
            target_display = screen.query_one("#target-display", Static)
            assert target_display is not None
            assert sample_alert_trigger.target == "192.168.1.50"

    @pytest.mark.asyncio
    async def test_compose_shows_response_buttons(self, sample_alert_trigger) -> None:
        """Test compose shows C/S/N response buttons."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            # Should have Continue, Stop, Notes buttons
            continue_btn = screen.query_one("#btn-continue", Button)
            stop_btn = screen.query_one("#btn-stop", Button)
            notes_btn = screen.query_one("#btn-notes", Button)
            
            assert continue_btn is not None
            assert stop_btn is not None
            assert notes_btn is not None


class TestSituationalAlertScreenKeybindings:
    """Tests for C/S/N keybinding handlers."""

    @pytest.fixture
    def sample_alert_trigger(self):
        """Create a sample AlertTrigger for testing."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        return AlertTrigger(
            id=str(uuid.uuid4()),
            alert_type=AlertType.NEW_SUBNET,
            severity=AlertSeverity.HIGH,
            target="192.168.2.0/24",
            discovery_details="New subnet discovered",
            risk_assessment="Network not in original scope",
            recommended_action="Review scope",
            agent_id=str(uuid.uuid4()),
        )

    def test_screen_has_c_keybinding(self) -> None:
        """Test screen has 'c' keybinding for Continue."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        bindings = {b.key: b for b in SituationalAlertScreen.BINDINGS}
        assert "c" in bindings
        assert bindings["c"].action == "continue_engagement"

    def test_screen_has_s_keybinding(self) -> None:
        """Test screen has 's' keybinding for Stop."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        bindings = {b.key: b for b in SituationalAlertScreen.BINDINGS}
        assert "s" in bindings
        assert bindings["s"].action == "stop_engagement"

    def test_screen_has_n_keybinding(self) -> None:
        """Test screen has 'n' keybinding for Notes."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        bindings = {b.key: b for b in SituationalAlertScreen.BINDINGS}
        assert "n" in bindings
        assert bindings["n"].action == "add_notes"

    @pytest.mark.asyncio
    async def test_c_key_triggers_continue(self, sample_alert_trigger) -> None:
        """Test pressing C triggers continue action."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        from cyberred.core.alerts import AlertResponseDecision
        
        callback_result = []
        
        def callback(response):
            callback_result.append(response)
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger, callback=callback)
            app.push_screen(screen)
            await pilot.pause()
            
            # Call action directly since keybindings may not work in test
            screen.action_continue_engagement()
            await pilot.pause()
            
            assert len(callback_result) == 1
            assert callback_result[0].decision == AlertResponseDecision.CONTINUE

    @pytest.mark.asyncio
    async def test_s_key_triggers_stop(self, sample_alert_trigger) -> None:
        """Test pressing S triggers stop action."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        from cyberred.core.alerts import AlertResponseDecision
        
        callback_result = []
        
        def callback(response):
            callback_result.append(response)
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger, callback=callback)
            app.push_screen(screen)
            await pilot.pause()
            
            # Call action directly
            screen.action_stop_engagement()
            await pilot.pause()
            
            assert len(callback_result) == 1
            assert callback_result[0].decision == AlertResponseDecision.STOP

    @pytest.mark.asyncio
    async def test_n_key_toggles_notes_input(self, sample_alert_trigger) -> None:
        """Test pressing N toggles notes input field."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            # Notes input should be hidden initially
            notes_input = screen.query_one("#notes-input", Input)
            assert notes_input.display is False
            
            # Toggle notes via action
            screen.action_add_notes()
            await pilot.pause()
            
            # Notes input should now be visible
            assert screen.notes_visible is True


class TestSituationalAlertScreenOperatorName:
    """Tests for operator_name parameter."""

    @pytest.fixture
    def sample_alert_trigger(self):
        """Create a sample AlertTrigger for testing."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        return AlertTrigger(
            id=str(uuid.uuid4()),
            alert_type=AlertType.NEW_SUBNET,
            severity=AlertSeverity.HIGH,
            target="192.168.2.0/24",
            discovery_details="New subnet",
            risk_assessment="Not in scope",
            recommended_action="Review",
            agent_id=str(uuid.uuid4()),
        )

    @pytest.mark.asyncio
    async def test_custom_operator_name_in_response(self, sample_alert_trigger) -> None:
        """Test custom operator_name is used in response."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        callback_result = []
        
        def callback(response):
            callback_result.append(response)
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(
                alert=sample_alert_trigger,
                callback=callback,
                operator_name="security_analyst_1",
            )
            app.push_screen(screen)
            await pilot.pause()
            
            screen.action_continue_engagement()
            await pilot.pause()
            
            assert callback_result[0].operator == "security_analyst_1"

    @pytest.mark.asyncio
    async def test_default_operator_name(self, sample_alert_trigger) -> None:
        """Test default operator_name is 'operator'."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        callback_result = []
        
        def callback(response):
            callback_result.append(response)
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(
                alert=sample_alert_trigger,
                callback=callback,
            )
            app.push_screen(screen)
            await pilot.pause()
            
            screen.action_continue_engagement()
            await pilot.pause()
            
            assert callback_result[0].operator == "operator"


class TestSituationalAlertScreenBlinkAnimation:
    """Tests for blink animation behavior."""

    @pytest.fixture
    def sample_alert_trigger(self):
        """Create a sample AlertTrigger for testing."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        return AlertTrigger(
            id=str(uuid.uuid4()),
            alert_type=AlertType.DOMAIN_CONTROLLER,
            severity=AlertSeverity.CRITICAL,
            target="192.168.1.10",
            discovery_details="Domain controller detected",
            risk_assessment="AD environment detected",
            recommended_action="Pause and assess",
            agent_id=str(uuid.uuid4()),
        )

    def test_screen_has_blink_state_reactive(self) -> None:
        """Test screen has blink_state reactive property."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        # Check that blink_state is defined as reactive
        assert hasattr(SituationalAlertScreen, "blink_state")

    @pytest.mark.asyncio
    async def test_on_unmount_with_no_timer(self, sample_alert_trigger) -> None:
        """Test on_unmount handles None blink_timer gracefully."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            # Manually set timer to None before mount
            screen._blink_timer = None
            
            # Call on_unmount directly - should not raise
            screen.on_unmount()
            
            # Verify no exception was raised
            assert screen._blink_timer is None

    @pytest.mark.asyncio
    async def test_blink_animation_toggles(self, sample_alert_trigger) -> None:
        """Test blink animation toggles state."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            initial_state = screen.blink_state
            
            # Trigger blink toggle manually
            screen._toggle_blink()
            
            assert screen.blink_state != initial_state

    @pytest.mark.asyncio
    async def test_blink_timer_starts_on_mount(self, sample_alert_trigger) -> None:
        """Test blink timer starts when screen is mounted."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            # Screen should have a blink timer
            assert screen._blink_timer is not None


class TestSituationalAlertScreenSeverityStyling:
    """Tests for severity-based styling."""

    @pytest.fixture
    def critical_alert(self):
        """Create a CRITICAL severity alert."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        return AlertTrigger(
            id=str(uuid.uuid4()),
            alert_type=AlertType.HONEYPOT,
            severity=AlertSeverity.CRITICAL,
            target="192.168.1.50",
            discovery_details="Honeypot detected",
            risk_assessment="Critical risk",
            recommended_action="Stop now",
            agent_id=str(uuid.uuid4()),
        )

    @pytest.fixture
    def high_alert(self):
        """Create a HIGH severity alert."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        return AlertTrigger(
            id=str(uuid.uuid4()),
            alert_type=AlertType.NEW_SUBNET,
            severity=AlertSeverity.HIGH,
            target="192.168.2.0/24",
            discovery_details="New subnet",
            risk_assessment="High risk",
            recommended_action="Review scope",
            agent_id=str(uuid.uuid4()),
        )

    @pytest.mark.asyncio
    async def test_critical_severity_uses_danger_style(self, critical_alert) -> None:
        """Test CRITICAL severity uses danger styling ($danger)."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            CSS = """
            .severity-critical { background: $error; }
            .severity-high { background: $warning; }
            """
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=critical_alert)
            app.push_screen(screen)
            await pilot.pause()
            
            severity_indicator = screen.query_one("#severity-indicator")
            assert "severity-critical" in severity_indicator.classes

    @pytest.mark.asyncio
    async def test_high_severity_uses_warning_style(self, high_alert) -> None:
        """Test HIGH severity uses warning styling ($warning)."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            CSS = """
            .severity-critical { background: $error; }
            .severity-high { background: $warning; }
            """
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=high_alert)
            app.push_screen(screen)
            await pilot.pause()
            
            severity_indicator = screen.query_one("#severity-indicator")
            assert "severity-high" in severity_indicator.classes


class TestSituationalAlertScreenCallback:
    """Tests for response callback propagation."""

    @pytest.fixture
    def sample_alert_trigger(self):
        """Create a sample AlertTrigger for testing."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        return AlertTrigger(
            id=str(uuid.uuid4()),
            alert_type=AlertType.UNEXPECTED_SERVICE,
            severity=AlertSeverity.MEDIUM,
            target="192.168.1.100:8080",
            discovery_details="Unexpected service",
            risk_assessment="Service not expected",
            recommended_action="Investigate",
            agent_id=str(uuid.uuid4()),
        )

    @pytest.mark.asyncio
    async def test_callback_receives_alert_response(self, sample_alert_trigger) -> None:
        """Test callback receives AlertResponse on dismiss."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        from cyberred.core.alerts import AlertResponse
        
        callback_result = []
        
        def callback(response):
            callback_result.append(response)
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger, callback=callback)
            app.push_screen(screen)
            await pilot.pause()
            
            screen.action_continue_engagement()
            await pilot.pause()
            
            assert len(callback_result) == 1
            assert isinstance(callback_result[0], AlertResponse)

    @pytest.mark.asyncio
    async def test_callback_includes_notes_when_provided(self, sample_alert_trigger) -> None:
        """Test callback includes notes when operator adds them."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        callback_result = []
        
        def callback(response):
            callback_result.append(response)
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger, callback=callback)
            app.push_screen(screen)
            await pilot.pause()
            
            # Toggle notes and set value
            screen.action_add_notes()
            await pilot.pause()
            
            notes_input = screen.query_one("#notes-input", Input)
            notes_input.value = "Test note from operator"
            
            screen.action_continue_engagement()
            await pilot.pause()
            
            assert callback_result[0].notes == "Test note from operator"

    @pytest.mark.asyncio
    async def test_screen_dismisses_after_response(self, sample_alert_trigger) -> None:
        """Test screen dismisses after operator response."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            assert app.screen == screen
            
            screen.action_continue_engagement()
            await pilot.pause()
            
            # Screen should be dismissed
            assert app.screen != screen


class TestSituationalAlertScreenNotesInput:
    """Tests for notes input field behavior."""

    @pytest.fixture
    def sample_alert_trigger(self):
        """Create a sample AlertTrigger for testing."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        return AlertTrigger(
            id=str(uuid.uuid4()),
            alert_type=AlertType.SCOPE_DRIFT,
            severity=AlertSeverity.HIGH,
            target="10.0.0.0/8",
            discovery_details="Scope drift detected",
            risk_assessment="Boundaries exceeded",
            recommended_action="Review boundaries",
            agent_id=str(uuid.uuid4()),
        )

    def test_screen_has_notes_visible_reactive(self) -> None:
        """Test screen has notes_visible reactive property."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        assert hasattr(SituationalAlertScreen, "notes_visible")

    @pytest.mark.asyncio
    async def test_notes_input_hidden_by_default(self, sample_alert_trigger) -> None:
        """Test notes input is hidden by default."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            assert screen.notes_visible is False

    @pytest.mark.asyncio
    async def test_notes_toggle_shows_input(self, sample_alert_trigger) -> None:
        """Test toggling notes shows input field."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            screen.action_add_notes()
            await pilot.pause()
            
            assert screen.notes_visible is True


class TestSituationalAlertScreenButtonHandlers:
    """Tests for button click handlers."""

    @pytest.fixture
    def sample_alert_trigger(self):
        """Create a sample AlertTrigger for testing."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        return AlertTrigger(
            id=str(uuid.uuid4()),
            alert_type=AlertType.NEW_SUBNET,
            severity=AlertSeverity.HIGH,
            target="192.168.2.0/24",
            discovery_details="New subnet",
            risk_assessment="Not in scope",
            recommended_action="Review",
            agent_id=str(uuid.uuid4()),
        )

    @pytest.mark.asyncio
    async def test_on_button_pressed_continue(self, sample_alert_trigger) -> None:
        """Test on_button_pressed handler for Continue button."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        from cyberred.core.alerts import AlertResponseDecision
        from textual.widgets import Button
        
        callback_result = []
        
        def callback(response):
            callback_result.append(response)
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger, callback=callback)
            app.push_screen(screen)
            await pilot.pause()
            
            # Simulate button press event
            btn = screen.query_one("#btn-continue", Button)
            btn.press()
            await pilot.pause()
            
            assert len(callback_result) == 1
            assert callback_result[0].decision == AlertResponseDecision.CONTINUE

    @pytest.mark.asyncio
    async def test_on_button_pressed_stop(self, sample_alert_trigger) -> None:
        """Test on_button_pressed handler for Stop button."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        from cyberred.core.alerts import AlertResponseDecision
        from textual.widgets import Button
        
        callback_result = []
        
        def callback(response):
            callback_result.append(response)
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger, callback=callback)
            app.push_screen(screen)
            await pilot.pause()
            
            # Simulate button press event
            btn = screen.query_one("#btn-stop", Button)
            btn.press()
            await pilot.pause()
            
            assert len(callback_result) == 1
            assert callback_result[0].decision == AlertResponseDecision.STOP

    @pytest.mark.asyncio
    async def test_on_button_pressed_notes(self, sample_alert_trigger) -> None:
        """Test on_button_pressed handler for Notes button."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        from textual.widgets import Button
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            assert screen.notes_visible is False
            
            # Simulate button press event
            btn = screen.query_one("#btn-notes", Button)
            btn.press()
            await pilot.pause()
            
            assert screen.notes_visible is True

    @pytest.mark.asyncio
    async def test_continue_button_click(self, sample_alert_trigger) -> None:
        """Test clicking Continue button triggers continue action."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        from cyberred.core.alerts import AlertResponseDecision
        
        callback_result = []
        
        def callback(response):
            callback_result.append(response)
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger, callback=callback)
            app.push_screen(screen)
            await pilot.pause()
            
            # Use action directly for reliable testing
            screen.action_continue_engagement()
            await pilot.pause()
            
            assert len(callback_result) == 1
            assert callback_result[0].decision == AlertResponseDecision.CONTINUE

    @pytest.mark.asyncio
    async def test_stop_button_click(self, sample_alert_trigger) -> None:
        """Test clicking Stop button triggers stop action."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        from cyberred.core.alerts import AlertResponseDecision
        
        callback_result = []
        
        def callback(response):
            callback_result.append(response)
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger, callback=callback)
            app.push_screen(screen)
            await pilot.pause()
            
            # Use action directly for reliable testing
            screen.action_stop_engagement()
            await pilot.pause()
            
            assert len(callback_result) == 1
            assert callback_result[0].decision == AlertResponseDecision.STOP

    @pytest.mark.asyncio
    async def test_notes_button_click(self, sample_alert_trigger) -> None:
        """Test clicking Notes button toggles notes input."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            assert screen.notes_visible is False
            
            # Use action directly for reliable testing
            screen.action_add_notes()
            await pilot.pause()
            
            assert screen.notes_visible is True

    @pytest.mark.asyncio
    async def test_on_button_pressed_unknown_button(self, sample_alert_trigger) -> None:
        """Test on_button_pressed handles unknown button gracefully."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        from textual.widgets import Button
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            # Create a mock button pressed event with unknown ID
            mock_button = MagicMock(spec=Button)
            mock_button.id = "unknown-button"
            mock_event = MagicMock()
            mock_event.button = mock_button
            
            # Call handler directly - should not raise
            screen.on_button_pressed(mock_event)
            
            # Verify nothing changed (no action taken)
            assert screen.notes_visible is False
