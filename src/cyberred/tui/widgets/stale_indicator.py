"""Stale State Indicator Widget (Story 9.7).

Visual warning indicator for stale daemon connection state.
Displays when no activity received from daemon for 60+ seconds.

Per UX spec lines 583-584: "$warning + timestamp" pattern.

Usage:
    from cyberred.tui.widgets.stale_indicator import StaleStateIndicator
    
    indicator = StaleStateIndicator()
    indicator.update_stale_state(is_stale=True, last_activity=datetime.now())
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Optional

from textual.reactive import reactive
from textual.widgets import Static

# Stale threshold in seconds - must match TUIClient.STALE_THRESHOLD_SECONDS
STALE_THRESHOLD_SECONDS: int = 60


class StaleStateIndicator(Static):
    """Warning indicator for stale daemon connection state.
    
    Displays when no activity received from daemon for 60+ seconds.
    Per UX spec lines 583-584: "$warning + timestamp" pattern.
    
    Format: "⚠ No activity for {threshold}s | Last: HH:MM:SS | Press R to refresh"
    
    Attributes:
        is_visible: Whether the indicator is visible.
        last_activity: Datetime of last activity from daemon.
    """
    
    DEFAULT_CSS: ClassVar[str] = """
    StaleStateIndicator {
        display: none;
        background: $warning;
        color: $text;
        padding: 0 1;
    }
    
    StaleStateIndicator.visible {
        display: block;
    }
    """
    
    is_visible: reactive[bool] = reactive(False)
    last_activity: reactive[Optional[datetime]] = reactive(None)
    
    def render(self) -> str:
        """Render stale warning message.
        
        Returns:
            Formatted warning string, or empty string if not visible/no activity.
        """
        if not self.is_visible or self.last_activity is None:
            return ""
        
        time_str = self.last_activity.strftime("%H:%M:%S")
        return f"⚠ No activity for {STALE_THRESHOLD_SECONDS}s | Last: {time_str} | Press R to refresh"
    
    def watch_is_visible(self, visible: bool) -> None:
        """Update CSS class when visibility changes.
        
        Args:
            visible: New visibility state.
        """
        self.set_class(visible, "visible")
    
    def update_stale_state(self, is_stale: bool, last_activity: Optional[datetime]) -> None:
        """Update indicator state.
        
        Args:
            is_stale: Whether daemon connection is stale.
            last_activity: Datetime of last activity from daemon.
        """
        self.is_visible = is_stale
        self.last_activity = last_activity
