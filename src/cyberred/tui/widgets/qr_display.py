"""QR Code Display Widget for TUI.

Story 12.8: Natural Language Drop Box Setup - Task 6.5

Widget for rendering QR codes in the terminal.

Usage:
    from cyberred.tui.widgets.qr_display import QRDisplayWidget
    
    qr_widget = QRDisplayWidget(qr_ascii_string)
"""

from __future__ import annotations

from textual.widget import Widget
from textual.widgets import Static

import structlog

log = structlog.get_logger()


class QRDisplayWidget(Static):
    """Widget for displaying QR codes in the terminal.
    
    Renders ASCII/Unicode QR codes with proper styling for terminal display.
    
    Attributes:
        DEFAULT_CSS: Styles for QR code display.
    """
    
    DEFAULT_CSS = """
    QRDisplayWidget {
        padding: 1;
        background: white;
        color: black;
        text-align: center;
        height: auto;
        width: auto;
        min-width: 30;
    }
    """
    
    def __init__(
        self,
        qr_content: str,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize QR display widget.
        
        Args:
            qr_content: ASCII/Unicode QR code string.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(qr_content, name=name, id=id, classes=classes)
        self._qr_content = qr_content
    
    def update_qr(self, qr_content: str) -> None:
        """Update the displayed QR code.
        
        Args:
            qr_content: New QR code string.
        """
        self._qr_content = qr_content
        self.update(qr_content)
