"""Deployment Result Screen for Drop Box Wizard.

Story 12.8: Natural Language Drop Box Setup - Task 7

Displays deployment results including instructions, cert info, and QR code.

Usage:
    from cyberred.tui.screens.deployment_result import DeploymentResultScreen
    
    self.app.push_screen(DeploymentResultScreen(plan, drop_box_id, ...))
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static, TabbedContent, TabPane

import structlog

if TYPE_CHECKING:
    from cyberred.c2.nl_interpreter import DeploymentPlan

log = structlog.get_logger()


class DeploymentResultScreen(Screen):
    """Screen displaying deployment results and instructions.
    
    Shows:
    - Platform-specific deployment instructions
    - Certificate information (paths, fingerprint)
    - QR code for mobile platforms
    
    Attributes:
        TITLE: Screen title.
        BINDINGS: Keyboard bindings.
    """
    
    TITLE = "Deployment Complete"
    
    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
        Binding("c", "copy_cert", "Copy Cert Path", show=True),
    ]
    
    DEFAULT_CSS = """
    DeploymentResultScreen {
        layout: vertical;
    }
    
    DeploymentResultScreen #screen-title {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $success;
        color: $text;
    }
    
    DeploymentResultScreen #main-container {
        padding: 1 2;
    }
    
    DeploymentResultScreen #summary {
        padding: 1;
        margin-bottom: 1;
        background: $surface;
        border: solid $primary;
    }
    
    DeploymentResultScreen #cert-info {
        padding: 1;
        margin-bottom: 1;
        background: $surface;
        border: solid $accent;
    }
    
    DeploymentResultScreen .label {
        color: $text-muted;
    }
    
    DeploymentResultScreen .value {
        color: $text;
        text-style: bold;
    }
    
    DeploymentResultScreen #instructions-scroll {
        height: 1fr;
        border: solid $primary-lighten-2;
        padding: 1;
    }
    
    DeploymentResultScreen #instructions {
        padding: 1;
    }
    
    DeploymentResultScreen #qr-container {
        align: center middle;
        padding: 1;
        background: white;
        color: black;
        margin: 1;
    }
    
    DeploymentResultScreen #button-row {
        align: center middle;
        height: auto;
        margin-top: 1;
        padding: 1;
    }
    
    DeploymentResultScreen Button {
        margin: 0 2;
    }
    """
    
    def __init__(
        self,
        plan: "DeploymentPlan",
        drop_box_id: str,
        cert_path: Path,
        key_path: Path,
        ca_path: Optional[Path],
        instructions: str,
        qr_code: Optional[str] = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize result screen.
        
        Args:
            plan: Confirmed DeploymentPlan.
            drop_box_id: Generated drop box ID.
            cert_path: Path to client certificate.
            key_path: Path to client private key.
            ca_path: Path to CA certificate.
            instructions: Platform-specific instructions.
            qr_code: Optional ASCII QR code for mobile.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._plan = plan
        self._drop_box_id = drop_box_id
        self._cert_path = cert_path
        self._key_path = key_path
        self._ca_path = ca_path
        self._instructions = instructions
        self._qr_code = qr_code
    
    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Static("✅ Drop Box Deployment Ready", id="screen-title")
        
        with Container(id="main-container"):
            # Summary section
            with Container(id="summary"):
                yield Static("📋 Deployment Summary", classes="section-title")
                yield Static(f"[dim]Platform:[/] [bold]{self._plan.platform.upper()}[/]")
                yield Static(f"[dim]Target:[/] [bold]{self._plan.ip_address}[/]")
                yield Static(f"[dim]Drop Box ID:[/] [bold]{self._drop_box_id}[/]")
            
            # Certificate info section
            with Container(id="cert-info"):
                yield Static("🔐 Certificate Information", classes="section-title")
                yield Static(f"[dim]Certificate:[/] {self._cert_path}")
                yield Static(f"[dim]Private Key:[/] {self._key_path}")
                if self._ca_path:
                    yield Static(f"[dim]CA Cert:[/] {self._ca_path}")
                yield Static(
                    "[yellow]⚠️ Never share the private key![/]",
                    classes="warning",
                )
            
            # Tabbed content for instructions and QR
            with TabbedContent():
                with TabPane("Instructions", id="instructions-tab"):
                    with VerticalScroll(id="instructions-scroll"):
                        yield Static(self._instructions, id="instructions")
                
                if self._qr_code:
                    with TabPane("QR Code", id="qr-tab"):
                        yield Static(
                            "Scan this QR code with the Cyber-Red mobile app:",
                            id="qr-label",
                        )
                        from cyberred.tui.widgets.qr_display import QRDisplayWidget
                        yield QRDisplayWidget(self._qr_code, id="qr-display")
            
            # Buttons
            with Horizontal(id="button-row"):
                yield Button("Copy Cert Path", id="copy-cert-btn", variant="primary")
                yield Button("Done", id="done-btn", variant="success")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "done-btn":
            self.action_close()
        elif event.button.id == "copy-cert-btn":
            self.action_copy_cert()
    
    def action_close(self) -> None:
        """Close the result screen."""
        log.info("deployment_result_closed", drop_box_id=self._drop_box_id)
        self.dismiss(True)
    
    def action_copy_cert(self) -> None:
        """Copy certificate path to clipboard."""
        try:
            import pyperclip
            pyperclip.copy(str(self._cert_path))
            self.notify("Certificate path copied to clipboard!", title="Copied")
        except ImportError:
            # pyperclip not available - show path in notification
            self.notify(
                f"Certificate path: {self._cert_path}",
                title="Certificate Path",
                timeout=10,
            )
        except Exception as e:
            self.notify(f"Could not copy: {e}", severity="error")
