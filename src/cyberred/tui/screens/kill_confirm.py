"""KillSwitchConfirmScreen for kill switch confirmation modal.

Story 9.11: Keyboard Navigation (F-Keys) - Task 4

Confirmation modal for F10 kill switch per UX spec:
- Warning message and Y/N options
- Y key confirms and triggers kill switch
- N key or ESC cancels
- Per UX spec: Kill switch (F10) requires confirmation
  ESC key bypasses confirmation for emergency use (handled in app.py)
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, Button


class KillSwitchConfirmScreen(ModalScreen[bool]):
    """Confirmation modal for F10 kill switch.
    
    Per UX spec: Kill switch (F10) requires confirmation.
    ESC key bypasses confirmation for emergency use.
    
    Attributes:
        TITLE: Modal title.
        BINDINGS: Keybindings for Y/N/ESC actions.
    """
    
    TITLE = "Kill Switch Confirmation"
    
    BINDINGS = [
        Binding("y", "confirm", "Yes - Kill", show=True),
        Binding("n", "cancel", "No - Cancel", show=True),
        Binding("escape", "cancel", "Cancel", show=False),
    ]
    
    DEFAULT_CSS = """
    KillSwitchConfirmScreen {
        align: center middle;
    }
    
    KillSwitchConfirmScreen > Vertical {
        width: 50;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $error;
    }
    
    KillSwitchConfirmScreen .kill-title {
        text-align: center;
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }
    
    KillSwitchConfirmScreen .kill-warning {
        text-align: center;
        margin-bottom: 1;
    }
    
    KillSwitchConfirmScreen .kill-message {
        text-align: center;
        color: $warning;
        margin-bottom: 1;
    }
    
    KillSwitchConfirmScreen .button-row {
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    
    KillSwitchConfirmScreen Button {
        margin: 0 1;
    }
    """
    
    def compose(self) -> ComposeResult:
        """Compose the confirmation modal layout."""
        with Vertical():
            yield Static("⚠️  KILL SWITCH  ⚠️", classes="kill-title")
            yield Static(
                "This will immediately terminate the engagement.",
                classes="kill-warning",
            )
            yield Static(
                "All agents will be stopped and the session will end.",
                classes="kill-message",
            )
            with Horizontal(classes="button-row"):
                yield Button("Yes [Y]", id="btn-confirm", variant="error")
                yield Button("No [N]", id="btn-cancel", variant="primary")
    
    def action_confirm(self) -> None:
        """Confirm kill switch and dismiss modal with True."""
        self.dismiss(True)
    
    def action_cancel(self) -> None:
        """Cancel kill switch and dismiss modal with False."""
        self.dismiss(False)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.
        
        Args:
            event: Button pressed event.
        """
        if event.button.id == "btn-confirm":
            self.action_confirm()
        elif event.button.id == "btn-cancel":
            self.action_cancel()
