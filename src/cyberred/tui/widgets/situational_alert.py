"""Situational Alert Screen for Story 10.6.

Implements an interruptive modal for situational awareness alerts with:
- AlertTrigger display (discovery details, risk assessment, recommended action)
- C/S/N keybindings (Continue/Stop/Notes)
- Focus trap via ModalScreen
- Blink animation (1s cycle per UX spec)
- Notes input field with toggle
- Severity-based styling ($danger for critical, $warning for high)
- Callback for response propagation

FR22: Situational awareness alerts for unexpected discoveries
FR23: Alert response logging to audit trail
NFR5: Alert delivery <500ms

UX Spec References:
- Lines 56: WebSocket push, interrupt without losing context
- Lines 502: Modal base for overlay
- Lines 549-555: Feedback patterns (Warning/Error persist)
- Lines 604: Blink animation for pending auth (1s cycle)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Input
from textual.timer import Timer

if TYPE_CHECKING:
    from cyberred.core.alerts import AlertTrigger, AlertResponse

logger = logging.getLogger(__name__)


# CSS for situational alert screen
SITUATIONAL_ALERT_CSS = """
SituationalAlertScreen {
    align: center middle;
}

#alert-container {
    width: 80;
    height: auto;
    max-height: 30;
    border: thick $error;
    background: $surface;
    padding: 1 2;
}

#alert-container.blink-on {
    border: thick $warning;
}

#alert-title {
    text-style: bold;
    text-align: center;
    padding: 1;
    width: 100%;
}

.severity-critical {
    background: $error;
    color: $text;
}

.severity-high {
    background: $warning;
    color: $text;
}

.severity-medium {
    background: $primary;
    color: $text;
}

#target-display {
    padding: 0 1;
    margin-bottom: 1;
}

#discovery-details {
    padding: 0 1;
    margin-bottom: 1;
}

#risk-assessment {
    padding: 0 1;
    margin-bottom: 1;
}

#recommended-action {
    padding: 0 1;
    margin-bottom: 1;
    text-style: italic;
}

#notes-input {
    margin: 1 0;
}

#button-bar {
    align: center middle;
    height: auto;
    margin-top: 1;
}

#button-bar Button {
    margin: 0 1;
}

#btn-continue {
    background: $success;
}

#btn-stop {
    background: $error;
}

#btn-notes {
    background: $primary;
}
"""


class SituationalAlertScreen(ModalScreen):
    """Modal screen for situational awareness alerts.
    
    Displays alert details and captures operator response (Continue/Stop/Notes).
    
    Attributes:
        alert: AlertTrigger instance with alert details.
        callback: Optional callback for response propagation.
        blink_state: Reactive property for blink animation.
        notes_visible: Reactive property for notes input visibility.
    """
    
    CSS = SITUATIONAL_ALERT_CSS
    
    BINDINGS = [
        Binding("c", "continue_engagement", "Continue (C)", show=True),
        Binding("s", "stop_engagement", "Stop (S)", show=True),
        Binding("n", "add_notes", "Notes (N)", show=True),
    ]
    
    blink_state = reactive(False)
    notes_visible = reactive(False)
    
    def __init__(
        self,
        alert: "AlertTrigger",
        callback: Optional[Callable[["AlertResponse"], None]] = None,
        operator_name: str = "operator",
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        """Initialize SituationalAlertScreen.
        
        Args:
            alert: AlertTrigger instance with alert details.
            callback: Optional callback for response propagation.
            operator_name: Name of the operator for audit trail (default: "operator").
            name: Optional widget name.
            id: Optional widget ID.
            classes: Optional CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.alert = alert
        self._callback = callback
        self._operator_name = operator_name
        self._blink_timer: Optional[Timer] = None
    
    def compose(self) -> ComposeResult:
        """Compose the alert modal layout."""
        # Determine severity class
        severity_class = f"severity-{self.alert.severity.value}"
        
        with Container(id="alert-container"):
            yield Static(
                f"⚠️ SITUATIONAL ALERT: {self.alert.alert_type.value.upper()}",
                id="alert-title",
            )
            yield Static(
                f"[{self.alert.severity.value.upper()}]",
                id="severity-indicator",
                classes=severity_class,
            )
            yield Static(
                f"Target: {self.alert.target}",
                id="target-display",
            )
            yield Static(
                f"Discovery: {self.alert.discovery_details}",
                id="discovery-details",
            )
            yield Static(
                f"Risk: {self.alert.risk_assessment}",
                id="risk-assessment",
            )
            yield Static(
                f"Recommended: {self.alert.recommended_action}",
                id="recommended-action",
            )
            yield Input(
                placeholder="Add operator notes...",
                id="notes-input",
            )
            with Horizontal(id="button-bar"):
                yield Button("Continue (C)", id="btn-continue", variant="success")
                yield Button("Stop (S)", id="btn-stop", variant="error")
                yield Button("Notes (N)", id="btn-notes", variant="primary")
    
    def on_mount(self) -> None:
        """Start blink animation timer on mount."""
        # Hide notes input initially
        notes_input = self.query_one("#notes-input", Input)
        notes_input.display = False
        
        # Start blink timer (1s cycle per UX spec)
        self._blink_timer = self.set_interval(1.0, self._toggle_blink)
    
    def on_unmount(self) -> None:
        """Stop blink timer on unmount."""
        if self._blink_timer:
            self._blink_timer.stop()
            self._blink_timer = None
    
    def _toggle_blink(self) -> None:
        """Toggle blink state for animation."""
        self.blink_state = not self.blink_state
    
    def watch_blink_state(self, blink_on: bool) -> None:
        """Watch blink_state and update container styling."""
        container = self.query_one("#alert-container", Container)
        if blink_on:
            container.add_class("blink-on")
        else:
            container.remove_class("blink-on")
    
    def watch_notes_visible(self, visible: bool) -> None:
        """Watch notes_visible and show/hide notes input."""
        notes_input = self.query_one("#notes-input", Input)
        notes_input.display = visible
        if visible:
            notes_input.focus()
    
    def _get_notes(self) -> Optional[str]:
        """Get notes from input field if any."""
        notes_input = self.query_one("#notes-input", Input)
        return notes_input.value if notes_input.value else None
    
    def _create_response(self, decision: str) -> "AlertResponse":
        """Create AlertResponse from decision.
        
        Args:
            decision: Decision string (continue/stop/notes).
            
        Returns:
            AlertResponse instance.
        """
        from cyberred.core.alerts import AlertResponse, AlertResponseDecision
        
        return AlertResponse(
            alert_id=self.alert.id,
            decision=AlertResponseDecision(decision),
            operator=self._operator_name,
            notes=self._get_notes(),
        )
    
    def _submit_response(self, decision: str) -> None:
        """Submit response and dismiss modal.
        
        Args:
            decision: Decision string.
        """
        response = self._create_response(decision)
        
        if self._callback:
            self._callback(response)
        
        self.dismiss(response)
    
    def action_continue_engagement(self) -> None:
        """Handle Continue (C) action."""
        self._submit_response("continue")
    
    def action_stop_engagement(self) -> None:
        """Handle Stop (S) action."""
        self._submit_response("stop")
    
    def action_add_notes(self) -> None:
        """Handle Notes (N) action - toggle notes input."""
        self.notes_visible = not self.notes_visible
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        
        if button_id == "btn-continue":
            self.action_continue_engagement()
        elif button_id == "btn-stop":
            self.action_stop_engagement()
        elif button_id == "btn-notes":
            self.action_add_notes()
