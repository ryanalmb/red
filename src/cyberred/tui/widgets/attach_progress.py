"""Attach Progress Indicator Widget (Story 9.8).

This widget displays progress during TUI attach operation and shows the
completion result with latency information.

Per NFR32: TUI attach must complete in <2 seconds.

Usage:
    indicator = AttachProgressIndicator()
    indicator.start("engagement-123")
    # ... wait for attach to complete ...
    indicator.complete(success=True, latency_ms=1500.0)
"""

from __future__ import annotations

from typing import ClassVar

from textual.reactive import reactive
from textual.widgets import Static


class AttachProgressIndicator(Static):
    """Progress indicator for TUI attach operation.

    Shows spinner and status during attachment, then completion result.
    Per NFR32: Attach must complete in <2s.

    Attributes:
        is_visible: Whether the indicator is visible.
        engagement_id: The engagement being attached to.
        status: Current status (idle, attaching, success, error).
        latency_ms: Attach latency in milliseconds.
    """

    DEFAULT_CSS: ClassVar[str] = """
    AttachProgressIndicator {
        display: none;
        background: $surface;
        color: $text;
        padding: 0 1;
        height: 1;
    }

    AttachProgressIndicator.visible {
        display: block;
    }

    AttachProgressIndicator.success {
        background: $success;
        color: $text;
    }

    AttachProgressIndicator.error {
        background: $error;
        color: $text;
    }
    """

    is_visible: reactive[bool] = reactive(False)
    engagement_id: reactive[str] = reactive("")
    status: reactive[str] = reactive("idle")  # idle, attaching, success, error
    latency_ms: reactive[float] = reactive(0.0)

    def render(self) -> str:
        """Render progress indicator content.

        Returns:
            Formatted string based on current status:
            - idle: empty string
            - attaching: "⏳ Attaching to {engagement_id}..."
            - success: "✓ Attached in {latency}ms"
            - error: "✗ Attach failed"
        """
        if self.status == "attaching":
            return f"⏳ Attaching to {self.engagement_id}..."
        elif self.status == "success":
            return f"✓ Attached in {self.latency_ms:.0f}ms"
        elif self.status == "error":
            return "✗ Attach failed"
        return ""

    def watch_is_visible(self, visible: bool) -> None:
        """Update CSS class when visibility changes.

        Args:
            visible: New visibility state.
        """
        self.set_class(visible, "visible")

    def watch_status(self, status: str) -> None:
        """Update CSS classes based on status.

        Args:
            status: New status value.
        """
        self.set_class(status == "success", "success")
        self.set_class(status == "error", "error")

    def start(self, engagement_id: str) -> None:
        """Start showing progress for attachment.

        Args:
            engagement_id: The engagement being attached to.
        """
        self.engagement_id = engagement_id
        self.status = "attaching"
        self.is_visible = True

    def complete(self, success: bool, latency_ms: float = 0.0) -> None:
        """Mark attachment complete with result.

        Args:
            success: Whether attach succeeded.
            latency_ms: Attach latency in milliseconds (must be >= 0).
        
        Raises:
            ValueError: If latency_ms is negative.
        """
        if latency_ms < 0:
            raise ValueError(f"latency_ms must be non-negative, got {latency_ms}")
        self.status = "success" if success else "error"
        self.latency_ms = latency_ms
        # Auto-hide after 3 seconds (only if running in app context)
        try:
            self.set_timer(3.0, self._hide)
        except RuntimeError:
            # No event loop running (e.g., in unit tests without app context)
            pass

    def _hide(self) -> None:
        """Hide the indicator and reset status.
        
        Internal method called by auto-hide timer after completion.
        Resets the widget to idle state for reuse.
        """
        self.is_visible = False
        self.status = "idle"
