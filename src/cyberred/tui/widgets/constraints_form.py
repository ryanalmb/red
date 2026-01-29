"""Constraints Form Widget for Authorization Response Handling.

Story 10.2: Authorization Response Handling

Provides a form for operators to specify constraints when approving
authorization requests:
- time_limit: Duration in seconds for approval validity
- target_limit: Maximum number of hosts agent can target
- specific_hosts_only: List of allowed hosts (comma-separated)

UX Spec References:
- Lines 569-573: Authorization input pattern: "instant response"
- Constraints form should be quick and optional
- Default to "no constraints" for speed
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Static, Button, Input, Select, Label
from textual.widget import Widget

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Time limit options: (value_in_seconds, display_label)
# None means no limit
TIME_LIMIT_OPTIONS: list[tuple[int | None, str]] = [
    (None, "No limit"),
    (300, "5 minutes"),
    (900, "15 minutes"),
    (1800, "30 minutes"),
    (3600, "1 hour"),
    (7200, "2 hours"),
]

# Target limit validation bounds
TARGET_LIMIT_MIN = 1
TARGET_LIMIT_MAX = 100


# ─────────────────────────────────────────────────────────────────────────────
# Validation Functions
# ─────────────────────────────────────────────────────────────────────────────

def validate_target_limit(value: int | None) -> bool:
    """Validate target_limit is within valid range.
    
    Args:
        value: Target limit value to validate.
        
    Returns:
        True if valid (1-100), False otherwise.
    """
    if value is None:
        return True
    return TARGET_LIMIT_MIN <= value <= TARGET_LIMIT_MAX


def validate_host_format(host: str) -> bool:
    """Validate that a host string is a valid IP or hostname.
    
    Args:
        host: Host string to validate.
        
    Returns:
        True if valid IP address or hostname format, False otherwise.
    """
    import re
    
    # Basic IPv4 pattern
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    # Basic hostname pattern (allows alphanumeric, hyphens, dots)
    hostname_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$'
    
    if re.match(ipv4_pattern, host):
        # Validate each octet is 0-255
        octets = host.split('.')
        return all(0 <= int(octet) <= 255 for octet in octets)
    
    return bool(re.match(hostname_pattern, host))


def parse_hosts_input(text: str) -> list[str] | None:
    """Parse comma-separated hosts input.
    
    Args:
        text: Raw input string with comma-separated hosts.
        
    Returns:
        List of host strings, or None if input is empty.
    """
    if not text or not text.strip():
        return None
    
    hosts = [h.strip() for h in text.split(",") if h.strip()]
    return hosts if hosts else None


# ─────────────────────────────────────────────────────────────────────────────
# ConstraintsForm Widget
# ─────────────────────────────────────────────────────────────────────────────

class ConstraintsForm(Widget):
    """Form widget for specifying authorization constraints.
    
    Story 10.2: Provides input fields for:
    - time_limit: Dropdown with preset durations
    - target_limit: Numeric input (1-100)
    - specific_hosts_only: Text input (comma-separated)
    
    Attributes:
        time_limit: Selected time limit in seconds, or None for unlimited.
        target_limit: Maximum hosts, or None for unlimited.
        specific_hosts_only: List of allowed hosts, or None for any.
    """
    
    DEFAULT_CSS: ClassVar[str] = """
    ConstraintsForm {
        height: auto;
        padding: 1;
        background: $surface;
        border: solid $primary;
    }
    
    ConstraintsForm .form-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    
    ConstraintsForm .form-row {
        height: auto;
        margin-bottom: 1;
    }
    
    ConstraintsForm .form-label {
        width: 20;
        padding-right: 1;
    }
    
    ConstraintsForm .form-input {
        width: 1fr;
    }
    
    ConstraintsForm .button-row {
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    
    ConstraintsForm Button {
        margin: 0 1;
    }
    
    ConstraintsForm #error-display {
        color: $error;
        text-align: center;
        height: auto;
    }
    """
    
    BINDINGS = [
        Binding("enter", "submit", "Apply", show=False),
        Binding("escape", "cancel", "Skip", show=False),
    ]
    
    # Reactive properties for constraint values
    time_limit: reactive[int | None] = reactive(None)
    target_limit: reactive[int | None] = reactive(None)
    specific_hosts_only: reactive[list[str] | None] = reactive(None)
    
    def __init__(
        self,
        callback: Callable[[dict[str, Any] | None], Any] | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize ConstraintsForm.
        
        Args:
            callback: Function called with constraints dict on submit,
                     or None on cancel/skip.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._callback = callback
        self._target_limit_value: int | None = None  # Internal storage for validation
    
    def compose(self) -> ComposeResult:
        """Compose the constraints form layout."""
        yield Static(
            "⚙️  Authorization Constraints (Optional)",
            classes="form-title",
        )
        
        # Time limit row
        with Horizontal(classes="form-row"):
            yield Label("Time Limit:", classes="form-label")
            yield Select(
                [(label, value) for value, label in TIME_LIMIT_OPTIONS],
                value=None,
                id="time-limit-select",
                classes="form-input",
            )
        
        # Target limit row
        with Horizontal(classes="form-row"):
            yield Label("Target Limit (1-100):", classes="form-label")
            yield Input(
                placeholder="No limit",
                id="target-limit-input",
                classes="form-input",
                type="integer",
            )
        
        # Specific hosts row
        with Horizontal(classes="form-row"):
            yield Label("Specific Hosts Only:", classes="form-label")
            yield Input(
                placeholder="e.g., 192.168.1.10, 192.168.1.20",
                id="hosts-input",
                classes="form-input",
            )
        
        # Error display
        yield Static("", id="error-display")
        
        # Buttons
        with Horizontal(classes="button-row"):
            yield Button("Apply Constraints", id="btn-apply", variant="success")
            yield Button("Skip (No Constraints)", id="btn-skip", variant="default")
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle time limit selection change.
        
        Args:
            event: Select changed event.
        """
        if event.select.id == "time-limit-select":
            self.time_limit = event.value
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input field changes.
        
        Args:
            event: Input changed event.
        """
        if event.input.id == "target-limit-input":
            try:
                if event.value.strip():
                    value = int(event.value)
                    self._target_limit_value = value
                    if validate_target_limit(value):
                        self.target_limit = value
                        self._clear_error()
                    else:
                        self._show_error(f"Target limit must be between {TARGET_LIMIT_MIN} and {TARGET_LIMIT_MAX}")
                else:
                    self._target_limit_value = None
                    self.target_limit = None
                    self._clear_error()
            except ValueError:
                self._show_error("Target limit must be a number")
        
        elif event.input.id == "hosts-input":
            self.specific_hosts_only = parse_hosts_input(event.value)
    
    def _show_error(self, message: str) -> None:
        """Display error message.
        
        Args:
            message: Error message to display.
        """
        try:
            error_display = self.query_one("#error-display", Static)
            error_display.update(f"[red]⚠️ {message}[/red]")
        except Exception:
            pass
    
    def _clear_error(self) -> None:
        """Clear error message display."""
        try:
            error_display = self.query_one("#error-display", Static)
            error_display.update("")
        except Exception:
            pass
    
    def is_valid(self) -> bool:
        """Check if form inputs are valid.
        
        Returns:
            True if all inputs are valid, False otherwise.
        """
        # Check target limit if set
        if self._target_limit_value is not None:
            if not validate_target_limit(self._target_limit_value):
                return False
        return True
    
    def get_constraints(self) -> dict[str, Any] | None:
        """Get constraints as dictionary.
        
        Returns:
            Dictionary with non-None constraint values,
            or None if all constraints are None.
        """
        constraints: dict[str, Any] = {}
        
        if self.time_limit is not None:
            constraints["time_limit"] = self.time_limit
        
        if self.target_limit is not None:
            constraints["target_limit"] = self.target_limit
        
        if self.specific_hosts_only is not None:
            constraints["specific_hosts_only"] = self.specific_hosts_only
        
        return constraints if constraints else None
    
    def _submit(self) -> None:
        """Submit the form with current constraints."""
        if not self.is_valid():
            self._show_error("Please fix validation errors before submitting")
            return
        
        constraints = self.get_constraints()
        
        logger.info(
            "Constraints form submitted: %s",
            constraints,
        )
        
        if self._callback:
            self._callback(constraints)
    
    def _cancel(self) -> None:
        """Cancel/skip constraints input."""
        logger.info("Constraints form cancelled/skipped")
        
        if self._callback:
            self._callback(None)
    
    def action_submit(self) -> None:
        """Handle Enter key to submit form."""
        self._submit()
    
    def action_cancel(self) -> None:
        """Handle Escape key to cancel form."""
        self._cancel()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.
        
        Args:
            event: Button pressed event.
        """
        if event.button.id == "btn-apply":
            self._submit()
        elif event.button.id == "btn-skip":
            self._cancel()
