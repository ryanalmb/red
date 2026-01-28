"""HelpScreen for displaying keybinding help.

Story 9.11: Keyboard Navigation (F-Keys) - Task 5

Help overlay screen per UX spec line 595:
- Displays all keybindings in organized sections
- F-keys, navigation keys, and special actions
- Dismissal via ?, ESC, or any key
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static


class HelpScreen(ModalScreen[None]):
    """Help overlay showing all keybindings.
    
    Per UX spec line 595: Help is accessible via `?` key.
    
    Organized sections:
    - F-Keys: Quick navigation
    - Navigation: Movement and focus
    - Special Actions: Kill switch, detach, etc.
    
    Attributes:
        TITLE: Modal title.
        BINDINGS: Keybindings for dismissal.
    """
    
    TITLE = "Keyboard Shortcuts"
    
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("question_mark", "dismiss", "Close", show=False),
        # Note: "?" is normalized to "question_mark" by Textual, no need for duplicate
    ]
    
    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    
    HelpScreen > Vertical {
        width: 70;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        background: $surface;
        border: thick $primary;
    }
    
    HelpScreen .help-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    
    HelpScreen .section-title {
        text-style: bold;
        color: $warning;
        margin-top: 1;
        margin-bottom: 0;
    }
    
    HelpScreen .keybinding-row {
        margin-left: 2;
    }
    
    HelpScreen .key {
        color: $accent;
        text-style: bold;
        width: 12;
    }
    
    HelpScreen .description {
        color: $text;
    }
    
    HelpScreen .footer-hint {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """
    
    def compose(self) -> ComposeResult:
        """Compose the help overlay layout."""
        with Vertical():
            yield Static("⌨️  Keyboard Shortcuts", classes="help-title")
            
            with VerticalScroll():
                # F-Keys Section
                yield Static("F-Keys (Quick Navigation)", classes="section-title")
                yield Static("[bold cyan]F1[/]          Dashboard - Focus main view", classes="keybinding-row")
                yield Static("[bold cyan]F2[/]          Config - Configuration panel", classes="keybinding-row")
                yield Static("[bold cyan]F3[/]          Logs - Focus logs panel", classes="keybinding-row")
                yield Static("[bold cyan]F4[/]          Report - Engagement report", classes="keybinding-row")
                yield Static("[bold cyan]F5[/]          Pause/Resume - Toggle engagement", classes="keybinding-row")
                yield Static("[bold cyan]F6[/]          Drop Box - C2 status screen", classes="keybinding-row")
                yield Static("[bold cyan]F7[/]          Director - Toggle director panel", classes="keybinding-row")
                yield Static("[bold cyan]F10[/]         Kill Switch - Stop engagement (confirm)", classes="keybinding-row")
                
                # Navigation Section
                yield Static("Navigation", classes="section-title")
                yield Static("[bold cyan]Tab[/]         Next widget", classes="keybinding-row")
                yield Static("[bold cyan]Shift+Tab[/]   Previous widget", classes="keybinding-row")
                yield Static("[bold cyan]↑/↓[/]         Scroll up/down", classes="keybinding-row")
                yield Static("[bold cyan]PgUp/PgDn[/]   Page up/down", classes="keybinding-row")
                yield Static("[bold cyan]Home/End[/]    Jump to start/end", classes="keybinding-row")
                
                # Special Actions Section
                yield Static("Special Actions", classes="section-title")
                yield Static("[bold cyan]ESC[/]         Kill Switch - Emergency stop (immediate)", classes="keybinding-row")
                yield Static("[bold cyan]Ctrl+D[/]      Detach - Disconnect TUI (daemon continues)", classes="keybinding-row")
                yield Static("[bold cyan]Ctrl+T[/]      Toggle thinking tags visibility", classes="keybinding-row")
                yield Static("[bold cyan]R[/]           Refresh - Reload state from daemon", classes="keybinding-row")
                yield Static("[bold cyan]Q[/]           Quit - Exit application", classes="keybinding-row")
                yield Static("[bold cyan]D[/]           Toggle dark mode", classes="keybinding-row")
                yield Static("[bold cyan]?[/]           Help - Show this overlay", classes="keybinding-row")
            
            yield Static("Press ESC or ? to close", classes="footer-hint")
    
    def action_dismiss(self) -> None:
        """Dismiss the help overlay."""
        self.dismiss()
