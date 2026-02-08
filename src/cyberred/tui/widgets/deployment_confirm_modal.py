"""Deployment Confirmation Modal for Drop Box Wizard.

Story 12.8: Natural Language Drop Box Setup - Task 3

Modal dialog to confirm deployment plan with editable fields.

Usage:
    from cyberred.tui.widgets.deployment_confirm_modal import DeploymentConfirmModal
    
    modal = DeploymentConfirmModal(deployment_plan)
    self.app.push_screen(modal)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

import structlog

if TYPE_CHECKING:
    from cyberred.c2.nl_interpreter import DeploymentPlan

log = structlog.get_logger()

# Supported platforms for dropdown
PLATFORM_OPTIONS = [
    ("Android", "android"),
    ("Windows", "windows"),
    ("Linux", "linux"),
    ("macOS", "macos"),
    ("iOS", "ios"),
]


class DeploymentConfirmModal(ModalScreen[Optional["DeploymentPlan"]]):
    """Modal screen for confirming deployment plan.
    
    Displays parsed deployment parameters and allows editing before confirmation.
    Returns the confirmed/modified DeploymentPlan or None if cancelled.
    
    Attributes:
        BINDINGS: Keyboard bindings (Enter to confirm, Escape to cancel).
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("enter", "confirm", "Confirm", show=True),
    ]
    
    DEFAULT_CSS = """
    DeploymentConfirmModal {
        align: center middle;
    }
    
    DeploymentConfirmModal > Container {
        width: 60;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    
    DeploymentConfirmModal #modal-title {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $primary;
        color: $text;
        margin-bottom: 1;
    }
    
    DeploymentConfirmModal .field-label {
        margin-top: 1;
        color: $text-muted;
    }
    
    DeploymentConfirmModal Input {
        margin-bottom: 1;
    }
    
    DeploymentConfirmModal Select {
        margin-bottom: 1;
    }
    
    DeploymentConfirmModal #clarification {
        color: $warning;
        padding: 1;
        margin: 1 0;
        background: $warning 10%;
        border: solid $warning;
    }
    
    DeploymentConfirmModal #button-row {
        margin-top: 2;
        align: center middle;
        height: auto;
    }
    
    DeploymentConfirmModal Button {
        margin: 0 2;
    }
    
    DeploymentConfirmModal #confirm-btn {
        background: $success;
    }
    
    DeploymentConfirmModal #cancel-btn {
        background: $error;
    }
    """
    
    def __init__(
        self,
        plan: "DeploymentPlan",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize confirmation modal.
        
        Args:
            plan: DeploymentPlan to confirm/edit.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._plan = plan
    
    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container():
            yield Static("Confirm Deployment", id="modal-title")
            
            # Show clarification warning if needed
            if self._plan.clarification_needed:
                yield Static(
                    f"⚠️ {self._plan.clarification_needed}",
                    id="clarification",
                )
            
            with Vertical():
                # Platform selection
                yield Label("Platform:", classes="field-label")
                # Use Select.BLANK for empty platform to avoid InvalidSelectValueError
                platform_value = self._plan.platform if self._plan.platform in [p[1] for p in PLATFORM_OPTIONS] else PLATFORM_OPTIONS[0][1]
                yield Select(
                    options=PLATFORM_OPTIONS,
                    value=platform_value,
                    id="platform-select",
                    allow_blank=False,
                )
                
                # IP Address input
                yield Label("IP Address / Hostname:", classes="field-label")
                yield Input(
                    value=self._plan.ip_address or "",
                    placeholder="e.g., 192.168.1.100 or server.local",
                    id="ip-input",
                )
                
                # Hostname input (friendly name)
                yield Label("Drop Box Name (optional):", classes="field-label")
                yield Input(
                    value=self._plan.hostname or "",
                    placeholder="e.g., office-android",
                    id="hostname-input",
                )
                
                # Confidence indicator
                confidence_pct = int(self._plan.confidence * 100)
                confidence_color = "green" if confidence_pct >= 70 else "yellow" if confidence_pct >= 50 else "red"
                yield Static(
                    f"Confidence: [{confidence_color}]{confidence_pct}%[/]",
                    id="confidence-display",
                )
            
            # Buttons
            with Horizontal(id="button-row"):
                yield Button("Cancel", id="cancel-btn", variant="error")
                yield Button("Confirm", id="confirm-btn", variant="success")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "confirm-btn":
            self.action_confirm()
        elif event.button.id == "cancel-btn":
            self.action_cancel()
    
    def action_confirm(self) -> None:
        """Confirm the deployment plan with current values."""
        # Get edited values
        platform_select = self.query_one("#platform-select", Select)
        ip_input = self.query_one("#ip-input", Input)
        hostname_input = self.query_one("#hostname-input", Input)
        
        # Update plan with edited values
        from cyberred.c2.nl_interpreter import DeploymentPlan
        
        updated_plan = DeploymentPlan(
            platform=str(platform_select.value) if platform_select.value else "",
            ip_address=ip_input.value.strip(),
            hostname=hostname_input.value.strip() or None,
            options=self._plan.options,
            confidence=1.0,  # User confirmed, so confidence is high
        )
        
        # Validate
        errors = updated_plan.validate()
        if errors:
            self.notify("\n".join(errors), severity="error", title="Validation Error")
            return
        
        log.info(
            "deployment_confirmed",
            platform=updated_plan.platform,
            ip_address=updated_plan.ip_address,
        )
        
        self.dismiss(updated_plan)
    
    def action_cancel(self) -> None:
        """Cancel the deployment."""
        log.info("deployment_cancelled")
        self.dismiss(None)
