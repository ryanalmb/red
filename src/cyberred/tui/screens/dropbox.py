"""DropBoxScreen for drop box status display.

Story 9.10: Drop Box Status Panel - Task 3

Full-screen view accessible via F6 showing:
- DropBoxStatusPanel widget
- Header with "Drop Box Status" title
- Footer with keybindings
- ESC to return to War Room

Per UX spec line 386-387 and 400.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, Header, Footer, Static

from cyberred.tui.widgets.dropbox_status import DropBoxStatusPanel, DropBoxStatus

if TYPE_CHECKING:
    from cyberred.tui.daemon_client import TUIClient


class DropBoxScreen(Screen):
    """Drop Box status screen accessible via F6.
    
    Per UX spec line 386: F6 Drop Box screen
    Per architecture line 880: tui/screens/dropbox.py
    
    Attributes:
        TITLE: Screen title displayed in header.
        BINDINGS: Keybindings including ESC for back navigation.
    """
    
    TITLE = "Drop Box Status"
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=True),
        Binding("n", "new_dropbox", "New Drop Box", show=True),
    ]
    
    DEFAULT_CSS = """
    DropBoxScreen {
        layout: vertical;
    }
    
    DropBoxScreen #screen-title {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: $surface;
    }
    
    DropBoxScreen DropBoxStatusPanel {
        margin: 1 2;
    }
    
    DropBoxScreen #button-row {
        align: center middle;
        height: auto;
        padding: 1;
        dock: bottom;
    }
    
    DropBoxScreen #deploy-btn {
        background: $success;
    }
    """
    
    def __init__(
        self,
        daemon_client: Optional["TUIClient"] = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize DropBoxScreen.
        
        Args:
            daemon_client: TUIClient for daemon communication (optional).
            name: Screen name.
            id: Screen ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._daemon_client = daemon_client
        self._status_panel: Optional[DropBoxStatusPanel] = None
    
    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Static("Drop Box Status", id="screen-title")
        yield DropBoxStatusPanel(id="dropbox-status-panel")
        with Horizontal(id="button-row"):
            yield Button("🚀 Deploy New Drop Box", id="deploy-btn", variant="success")
        yield Footer()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "deploy-btn":
            self.action_new_dropbox()
    
    def action_new_dropbox(self) -> None:
        """Open the drop box deployment wizard."""
        from cyberred.tui.screens.dropbox_wizard import DropBoxWizardScreen
        self.app.push_screen(DropBoxWizardScreen())
    
    def on_mount(self) -> None:
        """Handle mount event."""
        from textual.css.query import NoMatches
        try:
            self._status_panel = self.query_one("#dropbox-status-panel", DropBoxStatusPanel)
        except NoMatches:
            # Panel not found in composition - should not happen in normal use
            pass
    
    def update_status(self, status: DropBoxStatus) -> None:
        """Update the drop box status display.
        
        Args:
            status: New DropBoxStatus data.
        """
        if self._status_panel:
            self._status_panel.update_status(status)
