"""Export Dialog Widget.

Story 11.3: Data Export from TUI

Modal dialog for configuring data exports:
- Path input with default suggestion
- Archive vs individual files toggle (multi-select)
- Progress bar for large exports
- Keyboard navigation support
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ProgressBar, RadioButton, RadioSet, Static


class ExportDialog(ModalScreen):
    """Modal dialog for export configuration.

    Story 11.3: Data Export from TUI.

    Attributes:
        BINDINGS: Keyboard bindings for dialog.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Export"),
    ]

    DEFAULT_CSS = """
    ExportDialog {
        align: center middle;
    }

    ExportDialog #export-dialog {
        width: 60;
        height: auto;
        max-height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    ExportDialog #export-title {
        text-style: bold;
        margin-bottom: 1;
    }

    ExportDialog .label {
        margin-top: 1;
        margin-bottom: 0;
    }

    ExportDialog #export-path {
        margin-bottom: 1;
    }

    ExportDialog #export-error {
        color: $error;
        margin-top: 1;
    }

    ExportDialog #export-error.hidden {
        display: none;
    }

    ExportDialog #export-buttons {
        margin-top: 2;
        align: right middle;
    }

    ExportDialog #export-buttons Button {
        margin-left: 1;
    }

    ExportDialog #export-format {
        margin-top: 1;
        margin-bottom: 1;
    }

    ExportDialog #export-progress {
        margin-top: 1;
    }

    ExportDialog #export-progress.hidden {
        display: none;
    }
    """

    class ExportRequested(Message):
        """Emitted when user confirms export.

        Attributes:
            item_ids: List of item IDs to export.
            destination: Target path.
            as_archive: Whether to export as ZIP archive.
        """

        def __init__(
            self,
            item_ids: list[str],
            destination: Path,
            as_archive: bool,
        ) -> None:
            """Initialize ExportRequested message.

            Args:
                item_ids: List of item IDs to export.
                destination: Target file/directory path.
                as_archive: True for ZIP archive, False for individual files.
            """
            self.item_ids = item_ids
            self.destination = destination
            self.as_archive = as_archive
            super().__init__()

    def __init__(
        self,
        item_ids: list[str],
        default_path: Path,
        single_item: bool = True,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize ExportDialog.

        Args:
            item_ids: List of item IDs to export.
            default_path: Default export path suggestion.
            single_item: True if exporting single item.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._item_ids = item_ids
        self._default_path = default_path
        self._single_item = single_item

    def compose(self) -> ComposeResult:
        """Compose the dialog layout."""
        with Vertical(id="export-dialog"):
            # Title
            if self._single_item:
                yield Static("📤 Export item", id="export-title")
            else:
                yield Static(
                    f"📤 Export {len(self._item_ids)} items",
                    id="export-title",
                )

            # Path input
            yield Static("Destination:", classes="label")
            yield Input(
                value=str(self._default_path),
                id="export-path",
                placeholder="Enter export path...",
            )

            # Format selection for multi-select
            if not self._single_item:
                yield Static("Format:", classes="label")
                with RadioSet(id="export-format"):
                    yield RadioButton(
                        "ZIP Archive (with manifest)",
                        value=True,
                        id="format-archive",
                    )
                    yield RadioButton("Individual Files", id="format-individual")

            # Error display
            yield Static("", id="export-error", classes="error hidden")

            # Progress bar (hidden by default)
            yield ProgressBar(id="export-progress", classes="hidden", total=100)

            # Buttons
            with Horizontal(id="export-buttons"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                yield Button("Export", variant="primary", id="btn-export")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.

        Args:
            event: Button pressed event.
        """
        if event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-export":
            self.action_confirm()

    def action_cancel(self) -> None:
        """Cancel export and close dialog."""
        self.dismiss(None)

    def action_confirm(self) -> None:
        """Confirm export with current settings."""
        path_input = self.query_one("#export-path", Input)
        error_widget = self.query_one("#export-error", Static)

        # Validate path
        path_value = path_input.value.strip()
        if not path_value:
            error_widget.update("Path cannot be empty")
            error_widget.remove_class("hidden")
            return

        destination = Path(path_value).expanduser()

        # Check if parent directory is writable (if it exists)
        parent = destination.parent
        if parent.exists() and not os.access(parent, os.W_OK):
            error_widget.update(f"Cannot write to {parent}")
            error_widget.remove_class("hidden")
            return

        error_widget.add_class("hidden")

        # Determine archive mode
        as_archive = False
        if not self._single_item:
            try:
                radio_set = self.query_one("#export-format", RadioSet)
                pressed = radio_set.pressed_button
                if pressed is not None:
                    as_archive = pressed.id == "format-archive"
                else:
                    as_archive = True  # Default to archive
            except Exception:
                as_archive = True  # Default to archive for multi-select

        # Emit result and dismiss
        self.dismiss(
            self.ExportRequested(
                item_ids=self._item_ids,
                destination=destination,
                as_archive=as_archive,
            )
        )

    def show_progress(self, percentage: float) -> None:
        """Show and update progress bar.

        Args:
            percentage: Progress percentage (0-100).
        """
        try:
            progress = self.query_one("#export-progress", ProgressBar)
            progress.remove_class("hidden")
            progress.update(progress=percentage)
        except Exception:
            pass

    def hide_progress(self) -> None:
        """Hide progress bar."""
        try:
            progress = self.query_one("#export-progress", ProgressBar)
            progress.add_class("hidden")
        except Exception:
            pass

    def show_error(self, message: str) -> None:
        """Show error message.

        Args:
            message: Error message to display.
        """
        try:
            error_widget = self.query_one("#export-error", Static)
            error_widget.update(message)
            error_widget.remove_class("hidden")
        except Exception:
            pass
