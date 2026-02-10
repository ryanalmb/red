"""Drop Box Wizard Screen for NL-based deployment.

Story 12.8: Natural Language Drop Box Setup - Task 1

Provides natural language interface for deploying drop boxes.
Accessible from DropBoxScreen via "Deploy New Drop Box" button.

Usage:
    from cyberred.tui.screens.dropbox_wizard import DropBoxWizardScreen
    
    self.app.push_screen(DropBoxWizardScreen())
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static, TextArea

import structlog

if TYPE_CHECKING:
    from cyberred.c2.nl_interpreter import DeploymentPlan

log = structlog.get_logger()

# Example prompts for operators
EXAMPLE_PROMPTS = """**Example commands:**
• "Deploy a drop box on my Android phone at 192.168.1.100"
• "Set up Windows drop box on 10.0.0.50"
• "Linux dropbox at server.local called office-server"
• "macOS drop box at macbook.local"
"""


class DropBoxWizardScreen(Screen):
    """Natural language drop box deployment wizard.
    
    Allows operators to describe deployment in natural language,
    which is then interpreted and confirmed before execution.
    
    Per FR25: Natural language drop box configuration.
    
    Attributes:
        TITLE: Screen title.
        BINDINGS: Keyboard bindings.
    """
    
    TITLE = "Deploy Drop Box"
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=True),
        Binding("ctrl+enter", "deploy", "Deploy", show=True),
    ]
    
    DEFAULT_CSS = """
    DropBoxWizardScreen {
        layout: vertical;
    }
    
    DropBoxWizardScreen #screen-title {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $primary;
        color: $text;
    }
    
    DropBoxWizardScreen #main-container {
        padding: 2;
    }
    
    DropBoxWizardScreen #instructions {
        margin-bottom: 1;
        padding: 1;
        background: $surface;
        border: solid $primary-lighten-2;
    }
    
    DropBoxWizardScreen #examples {
        color: $text-muted;
        padding: 1;
        margin-bottom: 1;
    }
    
    DropBoxWizardScreen #nl-input {
        height: 5;
        margin-bottom: 1;
        border: solid $accent;
    }
    
    DropBoxWizardScreen #nl-input:focus {
        border: solid $primary;
    }
    
    DropBoxWizardScreen #button-row {
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    
    DropBoxWizardScreen Button {
        margin: 0 2;
    }
    
    DropBoxWizardScreen #deploy-btn {
        background: $success;
    }
    
    DropBoxWizardScreen #status {
        margin-top: 2;
        padding: 1;
        text-align: center;
    }
    
    DropBoxWizardScreen #error-display {
        color: $error;
        padding: 1;
        margin-top: 1;
        background: $error 10%;
        border: solid $error;
        display: none;
    }
    
    DropBoxWizardScreen #error-display.visible {
        display: block;
    }
    """
    
    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize wizard screen."""
        super().__init__(name=name, id=id, classes=classes)
        self._processing = False
    
    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Static("🚀 Deploy New Drop Box", id="screen-title")
        
        with Container(id="main-container"):
            yield Static(
                "Describe your deployment in natural language. "
                "The AI will parse your request and confirm before deploying.",
                id="instructions",
            )
            
            yield Static(EXAMPLE_PROMPTS, id="examples")
            
            yield TextArea(
                placeholder="Describe your deployment (e.g., 'Deploy on Android at 192.168.1.100')...",
                id="nl-input",
            )
            
            with Horizontal(id="button-row"):
                yield Button("Cancel", id="cancel-btn", variant="error")
                yield Button("Deploy", id="deploy-btn", variant="success")
            
            yield Static("", id="status")
            yield Static("", id="error-display")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Focus the input on mount."""
        self.query_one("#nl-input", TextArea).focus()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "deploy-btn":
            self.action_deploy()
        elif event.button.id == "cancel-btn":
            self.app.pop_screen()
    
    def action_deploy(self) -> None:
        """Process the NL input and start deployment flow."""
        if self._processing:
            return
        
        nl_input = self.query_one("#nl-input", TextArea)
        text = nl_input.text.strip()
        
        if not text:
            self._show_error("Please enter a deployment description.")
            return
        
        self._processing = True
        self._update_status("🔄 Processing your request...")
        self._hide_error()
        
        # Run async interpretation
        self.run_worker(self._interpret_and_confirm(text))
    
    async def _interpret_and_confirm(self, nl_input: str) -> None:
        """Interpret NL input and show confirmation modal.
        
        Args:
            nl_input: Natural language deployment description.
        """
        try:
            from cyberred.c2.nl_interpreter import DropBoxDeploymentInterpreter, InterpretationError
            
            interpreter = DropBoxDeploymentInterpreter()
            plan = await interpreter.interpret(nl_input)
            
            # Show confirmation modal
            self._update_status("✅ Parsed successfully. Confirm deployment details.")
            
            from cyberred.tui.widgets.deployment_confirm_modal import DeploymentConfirmModal
            
            confirmed_plan = await self.app.push_screen_wait(DeploymentConfirmModal(plan))
            
            if confirmed_plan is None:
                # User cancelled
                self._update_status("❌ Deployment cancelled.")
                self._processing = False
                return
            
            # Proceed with deployment
            await self._execute_deployment(confirmed_plan)
            
        except InterpretationError as e:
            self._show_error(f"{e}\n\n{e.suggestion or ''}")
            self._update_status("")
            self._processing = False
        except ValueError as e:
            self._show_error(str(e))
            self._update_status("")
            self._processing = False
        except Exception as e:
            log.error("wizard_interpretation_error", error=str(e))
            self._show_error(f"An error occurred: {str(e)}")
            self._update_status("")
            self._processing = False
    
    async def _execute_deployment(self, plan: "DeploymentPlan") -> None:
        """Execute the deployment with confirmed plan.
        
        Args:
            plan: Confirmed DeploymentPlan.
        """
        try:
            self._update_status("🔐 Generating certificates...")
            
            # Get certificate manager and generate certs
            from cyberred.c2.cert_manager import CertificateManager, CertManagerConfig
            from cyberred.core.keystore import Keystore
            from pathlib import Path
            import os
            
            # Generate drop box ID
            drop_box_id = plan.generate_drop_box_id()
            
            # Try to get existing cert manager from app state
            cert_manager = getattr(self.app, '_cert_manager', None)
            
            if cert_manager is None:
                raise RuntimeError(
                    "No certificate manager available. "
                    "Start an engagement first to initialize certificate infrastructure."
                )
            
            # Issue client certificate
            cert_path, key_path = cert_manager.issue_client_cert(drop_box_id)
            
            # Ensure private key has restricted permissions (0600) per security requirements
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                log.warning("could_not_set_key_permissions", key_path=str(key_path))
            
            ca_path = cert_manager.get_ca_cert_path()
            
            self._update_status("📋 Generating deployment instructions...")
            
            # Get C2 URL from config or use default
            c2_url = getattr(self.app, '_c2_url', "wss://c2.cyber-red.local:8444")
            
            # Generate instructions
            from cyberred.c2.deployment_instructions import get_instructions, is_mobile_platform
            
            instructions = get_instructions(
                platform=plan.platform,
                cert_path=cert_path,
                key_path=key_path,
                ca_path=ca_path,
                c2_url=c2_url,
                drop_box_id=drop_box_id,
            )
            
            # Generate QR code for mobile
            qr_code = None
            if is_mobile_platform(plan.platform):
                from cyberred.c2.qr_generator import generate_qr_for_cert
                qr_code = generate_qr_for_cert(c2_url, cert_path, drop_box_id)
            
            # Show results screen
            from cyberred.tui.screens.deployment_result import DeploymentResultScreen
            
            await self.app.push_screen_wait(
                DeploymentResultScreen(
                    plan=plan,
                    drop_box_id=drop_box_id,
                    cert_path=cert_path,
                    key_path=key_path,
                    ca_path=ca_path,
                    instructions=instructions,
                    qr_code=qr_code,
                )
            )
            
            # Return to drop box screen and reset processing flag
            self._processing = False
            self.app.pop_screen()
            
        except Exception as e:
            log.error("deployment_execution_error", error=str(e))
            self._show_error(f"Deployment failed: {str(e)}")
            self._update_status("")
            self._processing = False
    
    def _update_status(self, message: str) -> None:
        """Update status display.
        
        Args:
            message: Status message to display.
        """
        status = self.query_one("#status", Static)
        status.update(message)
    
    def _show_error(self, message: str) -> None:
        """Show error message.
        
        Args:
            message: Error message to display.
        """
        error_display = self.query_one("#error-display", Static)
        error_display.update(f"⚠️ {message}")
        error_display.add_class("visible")
    
    def _hide_error(self) -> None:
        """Hide error display."""
        error_display = self.query_one("#error-display", Static)
        error_display.remove_class("visible")
