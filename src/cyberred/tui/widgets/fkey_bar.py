"""FKeyBar widget for displaying F-key mappings.

Story 9.11: Keyboard Navigation (F-Keys) - Task 1

Displays F-key mappings in the footer area per UX spec lines 386-387:
[F1]Dash [F2]Cfg [F3]Log [F4]Rpt [F5]Pause [F6]Drop [F7]Dir [F8]Scope [F9]Data [F10]KILL [F11]RAG

Features:
- Configurable mappings via FKeyMapping dataclass
- Reactive updates when mappings change
- Compact mode for narrow terminals
- TCSS styling via fkey-bar class
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from textual.widgets import Static
from textual.reactive import reactive


@dataclass
class FKeyMapping:
    """F-key mapping configuration.
    
    Attributes:
        key: The key binding (e.g., "f1", "f10").
        action: The action method name to call.
        label: Display label shown in the bar (e.g., "Dash", "Cfg").
    """
    key: str
    action: str
    label: str
    
    def to_display(self) -> str:
        """Convert mapping to display format [F1]Label.
        
        Returns:
            Formatted string like "[F1]Dash" or "[F10]KILL".
        """
        # Convert key to display format (f1 -> F1, f10 -> F10)
        key_display = self.key.upper()
        return f"[{key_display}]{self.label}"


# Default F-key mappings per UX spec and story AC #3
# F1=Dashboard, F2=Config, F3=Logs, F4=Report, F5=Pause/Resume,
# F6=Drop Box, F7=Director, F8=Scope, F9=Data, F10=Kill Switch, F11=RAG
DEFAULT_FKEY_MAPPINGS: List[FKeyMapping] = [
    FKeyMapping(key="f1", action="dashboard", label="Dash"),
    FKeyMapping(key="f2", action="config", label="Cfg"),
    FKeyMapping(key="f3", action="logs", label="Log"),
    FKeyMapping(key="f4", action="report", label="Rpt"),
    FKeyMapping(key="f5", action="pause_resume", label="Pause"),
    FKeyMapping(key="f6", action="show_dropbox", label="Drop"),
    FKeyMapping(key="f7", action="director_panel", label="Dir"),
    FKeyMapping(key="f8", action="scope_editor", label="Scope"),  # Story 10.5
    FKeyMapping(key="f9", action="data_browser", label="Data"),  # Story 11.2
    FKeyMapping(key="f10", action="kill_switch_confirm", label="KILL"),
    FKeyMapping(key="f11", action="rag_panel", label="RAG"),  # Story 11.5
]


class FKeyBar(Static):
    """F-key mapping display bar per UX spec lines 386-387.
    
    Displays: [F1]Dash [F2]Cfg [F3]Log [F4]Rpt [F5]Pause [F6]Drop [F7]Dir [F8]Scope [F9]Data [F10]KILL [F11]RAG
    
    Supports:
    - Custom mappings via constructor or reactive property
    - Compact mode for narrow terminals
    - Rich markup for styling
    
    Attributes:
        mappings: List of FKeyMapping objects to display.
        compact_mode: Whether to use compact display mode.
    """
    
    DEFAULT_CSS = """
    FKeyBar {
        height: 1;
        dock: bottom;
        background: $surface;
        padding: 0 1;
    }
    
    FKeyBar.fkey-bar {
        background: $surface;
    }
    """
    
    # Reactive properties for dynamic updates
    mappings: reactive[List[FKeyMapping]] = reactive(list, init=False)
    compact_mode: reactive[bool] = reactive(False)
    
    def __init__(
        self,
        mappings: Optional[List[FKeyMapping]] = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize FKeyBar.
        
        Args:
            mappings: List of FKeyMapping objects. Uses DEFAULT_FKEY_MAPPINGS if None.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        # Add fkey-bar class for styling
        if classes:
            classes = f"{classes} fkey-bar"
        else:
            classes = "fkey-bar"
        
        super().__init__(name=name, id=id, classes=classes)
        
        # Set mappings (use default if not provided)
        self.mappings = mappings if mappings is not None else list(DEFAULT_FKEY_MAPPINGS)
    
    def render(self) -> str:
        """Render F-key bar with Rich markup.
        
        Returns:
            Formatted string with all F-key mappings.
        """
        if self.compact_mode:
            # Compact mode: show fewer mappings or shorter labels
            # Show only essential keys: F1, F5, F10
            essential_keys = {"f1", "f5", "f10"}
            parts = [
                f"[bold cyan][{m.key.upper()}][/bold cyan]{m.label}"
                for m in self.mappings
                if m.key in essential_keys
            ]
        else:
            # Full mode: show all mappings
            parts = [
                f"[bold cyan][{m.key.upper()}][/bold cyan]{m.label}"
                for m in self.mappings
            ]
        
        return " ".join(parts)
    
    def watch_mappings(self, new_mappings: List[FKeyMapping]) -> None:
        """React to mappings changes by refreshing display.
        
        Args:
            new_mappings: The new list of mappings.
        """
        self.refresh()
    
    def watch_compact_mode(self, compact: bool) -> None:
        """React to compact mode changes by refreshing display.
        
        Args:
            compact: Whether compact mode is enabled.
        """
        self.refresh()
