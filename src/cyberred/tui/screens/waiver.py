"""Pre-Engagement Liability Waiver Screen.

Story 13.9: Pre-Engagement Liability Waiver

This module implements the waiver screen that operators must complete
before starting any security engagement. Provides legal liability
documentation with cryptographic proof of acceptance.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static

from cyberred.core.exceptions import ConfigurationError


# ─────────────────────────────────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WaiverAcceptance:
    """Result of waiver acceptance/decline decision.
    
    Attributes:
        accepted: True if waiver accepted, False if declined
        signature: Operator's full name signature (empty if declined)
        timestamp: UTC ISO 8601 timestamp of decision
        waiver_hash: SHA-256 hash of waiver text (empty if declined)
    """
    accepted: bool
    signature: str
    timestamp: str
    waiver_hash: str


@dataclass
class WaiverConfig:
    """Waiver configuration loaded from YAML.
    
    Attributes:
        waiver_text: Legal waiver text to display
        organization_name: Organization name for waiver
        require_signature: Whether signature is required (default True)
    """
    waiver_text: str
    organization_name: str
    require_signature: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# Configuration Loading
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_WAIVER_TEXT = """CYBER SECURITY ENGAGEMENT LIABILITY WAIVER

Organization: {org_name}
Date: {date}

By accepting this waiver, I acknowledge that:

1. I have proper authorization to conduct security testing
2. I understand the risks associated with offensive security operations
3. I will operate only within the defined scope
4. I accept full responsibility for all actions during this engagement
5. I will comply with all applicable laws and regulations

This waiver is legally binding and will be included in the audit trail.

DISCLAIMER: This is a default template. Organizations should consult legal
counsel to ensure compliance with local laws and regulations.
"""

DEFAULT_ORGANIZATION_NAME = "Cyber-Red Organization"


def load_waiver_config(config_path: Optional[Path] = None) -> WaiverConfig:
    """Load waiver configuration from YAML file.
    
    Args:
        config_path: Path to waiver.yaml config file. If None or file doesn't
                     exist, returns default configuration.
    
    Returns:
        WaiverConfig with loaded or default values
    
    Raises:
        ConfigurationError: If YAML is malformed
    """
    # Default configuration
    if config_path is None or not config_path.exists():
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        waiver_text = DEFAULT_WAIVER_TEXT.format(
            org_name=DEFAULT_ORGANIZATION_NAME,
            date=today
        )
        return WaiverConfig(
            waiver_text=waiver_text,
            organization_name=DEFAULT_ORGANIZATION_NAME,
            require_signature=True
        )
    
    # Load from file
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Malformed YAML in waiver config: {e}")
    
    org_name = config_data.get('organization_name', DEFAULT_ORGANIZATION_NAME)
    waiver_text = config_data.get('waiver_text', DEFAULT_WAIVER_TEXT)
    require_signature = config_data.get('require_signature', True)
    
    # Variable substitution
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    waiver_text = waiver_text.replace('{{org_name}}', org_name)
    waiver_text = waiver_text.replace('{{date}}', today)
    
    return WaiverConfig(
        waiver_text=waiver_text,
        organization_name=org_name,
        require_signature=require_signature
    )


def compute_waiver_hash(waiver_text: str) -> str:
    """Compute SHA-256 hash of waiver text for tamper evidence.
    
    Args:
        waiver_text: Full waiver text to hash
    
    Returns:
        Hex-encoded SHA-256 hash
    """
    return hashlib.sha256(waiver_text.encode()).hexdigest()


async def log_waiver_to_audit(
    acceptance: WaiverAcceptance,
    engagement_id: str,
    operator: str,
    audit_log: "OperatorAuditLog"
) -> None:
    """Log waiver acceptance/decline to audit trail.
    
    Args:
        acceptance: WaiverAcceptance result from waiver screen
        engagement_id: Engagement identifier
        operator: Operator username/identifier
        audit_log: OperatorAuditLog instance for logging
    """
    from cyberred.storage.operator_audit import OperatorAction
    
    # Determine action based on acceptance
    action = (
        OperatorAction.WAIVER_ACCEPTED if acceptance.accepted
        else OperatorAction.WAIVER_DECLINED
    )
    
    # Build context with waiver details
    context = {
        "signature": acceptance.signature,
        "waiver_hash": acceptance.waiver_hash,
        "timestamp": acceptance.timestamp,
    }
    
    # Log to audit trail
    await audit_log.log_action(
        operator=operator,
        action=action,
        context=context,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Waiver Screen TUI Component
# ─────────────────────────────────────────────────────────────────────────────

class WaiverScreen(ModalScreen[Optional[WaiverAcceptance]]):
    """Modal screen for pre-engagement liability waiver.
    
    Displays legal waiver text with checkbox acknowledgment and signature
    input. Operator must complete both to accept. Returns WaiverAcceptance
    with cryptographic hash for audit trail.
    
    This is a blocking modal - operator cannot proceed without making a choice.
    """
    
    CSS = """
    WaiverScreen {
        align: center middle;
    }
    
    WaiverScreen > Container {
        width: 90;
        height: auto;
        max-height: 90%;
        background: $panel;
        border: thick $primary;
        padding: 1 2;
    }
    
    WaiverScreen .waiver-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    
    WaiverScreen .waiver-org {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }
    
    WaiverScreen ScrollableContainer {
        height: 20;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
    }
    
    WaiverScreen .waiver-text {
        color: $text;
    }
    
    WaiverScreen .acknowledgment-section {
        margin-top: 1;
        margin-bottom: 1;
    }
    
    WaiverScreen Checkbox {
        margin-bottom: 1;
    }
    
    WaiverScreen .signature-label {
        color: $text;
        margin-bottom: 0;
    }
    
    WaiverScreen Input {
        margin-bottom: 1;
    }
    
    WaiverScreen Horizontal {
        height: auto;
        align: center middle;
    }
    
    WaiverScreen Button {
        margin: 0 1;
    }
    
    WaiverScreen .accept-button {
        background: $success;
    }
    
    WaiverScreen .decline-button {
        background: $error;
    }
    """
    
    BINDINGS = [
        ("escape", "decline", "Decline"),
    ]
    
    def __init__(
        self,
        waiver_text: str,
        org_name: str,
        require_signature: bool = True
    ):
        """Initialize waiver screen.
        
        Args:
            waiver_text: Legal waiver text to display
            org_name: Organization name to display
            require_signature: Whether signature is required (default True)
        """
        super().__init__()
        self.waiver_text = waiver_text
        self.org_name = org_name
        self.require_signature = require_signature
        self._checkbox_checked = False
        self._signature_valid = False
    
    def compose(self) -> ComposeResult:
        """Compose the waiver screen UI."""
        with Container():
            yield Static("PRE-ENGAGEMENT LIABILITY WAIVER", classes="waiver-title")
            yield Static(f"Organization: {self.org_name}", classes="waiver-org")
            
            # Scrollable waiver text
            with ScrollableContainer():
                yield Static(self.waiver_text, classes="waiver-text")
            
            # Acknowledgment section
            with Vertical(classes="acknowledgment-section"):
                yield Checkbox(
                    "I have read and understood the waiver above",
                    id="waiver-checkbox"
                )
                
                yield Label("Full Name (Signature):", classes="signature-label")
                yield Input(
                    placeholder="Enter your full name",
                    id="signature-input"
                )
            
            # Buttons
            with Horizontal():
                yield Button(
                    "Accept",
                    variant="success",
                    id="accept-button",
                    disabled=True,
                    classes="accept-button"
                )
                yield Button(
                    "Decline",
                    variant="error",
                    id="decline-button",
                    classes="decline-button"
                )
    
    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox state change."""
        self._checkbox_checked = event.value
        self._update_accept_button()
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle signature input change."""
        if event.input.id == "signature-input":
            signature = event.value.strip()
            self._signature_valid = len(signature) > 0
            self._update_accept_button()
    
    def _update_accept_button(self) -> None:
        """Update Accept button enabled state based on validation."""
        accept_button = self.query_one("#accept-button", Button)
        
        # Enable only if both checkbox checked AND signature provided
        if self.require_signature:
            accept_button.disabled = not (self._checkbox_checked and self._signature_valid)
        else:
            accept_button.disabled = not self._checkbox_checked
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "accept-button":
            self._handle_accept()
        elif event.button.id == "decline-button":
            self._handle_decline()
    
    def _handle_accept(self) -> None:
        """Handle waiver acceptance."""
        signature_input = self.query_one("#signature-input", Input)
        signature = signature_input.value.strip()
        
        # Create acceptance record
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        waiver_hash = compute_waiver_hash(self.waiver_text)
        
        acceptance = WaiverAcceptance(
            accepted=True,
            signature=signature,
            timestamp=timestamp,
            waiver_hash=waiver_hash
        )
        
        self.dismiss(acceptance)
    
    def _handle_decline(self) -> None:
        """Handle waiver decline."""
        # Create decline record
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        acceptance = WaiverAcceptance(
            accepted=False,
            signature="",
            timestamp=timestamp,
            waiver_hash=""
        )
        
        self.dismiss(acceptance)
    
    def action_decline(self) -> None:
        """Handle ESC key to decline."""
        self._handle_decline()
