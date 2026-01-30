"""Delete Confirmation Modal Widget.

Story 11.4: Manual Data Deletion

Provides a TUI confirmation modal that requires typing "DELETE" (single)
or "DELETE ALL" (bulk) to confirm deletion. Per FR45: Requires explicit
confirmation before deletion.

Components:
    - DeleteConfirmationModal: Modal screen requiring typed confirmation

Security Notes:
    - Requires exact text match (case-insensitive)
    - No accidental deletion via simple button press
    - Escape key cancels without deletion

Usage:
    from cyberred.tui.widgets.delete_confirmation import DeleteConfirmationModal

    modal = DeleteConfirmationModal(items=[item1, item2])
    app.push_screen(modal, callback)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from cyberred.tui.utils import format_size

if TYPE_CHECKING:
    from cyberred.storage.evidence import ExfiltratedDataItem

logger = logging.getLogger(__name__)


class DeleteConfirmationModal(ModalScreen):
    """Modal requiring typed confirmation for deletion.

    Per FR45: Requires typing "DELETE" (single) or "DELETE ALL" (bulk)
    to confirm deletion. This prevents accidental data loss.

    Attributes:
        _items: List of items to delete.
        _is_bulk: True if multiple items being deleted.
        _required_text: Text that must be typed to confirm.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    DeleteConfirmationModal {
        align: center middle;
    }

    DeleteConfirmationModal #dialog {
        width: 60;
        height: auto;
        max-height: 30;
        border: solid red;
        background: $surface;
        padding: 1 2;
    }

    DeleteConfirmationModal #warning-header {
        text-align: center;
        color: $error;
        text-style: bold;
        margin-bottom: 1;
    }

    DeleteConfirmationModal #item-info {
        margin-bottom: 1;
        padding: 1;
        background: $boost;
    }

    DeleteConfirmationModal #item-list {
        max-height: 10;
        overflow-y: auto;
        margin-bottom: 1;
        padding: 1;
        background: $boost;
    }

    DeleteConfirmationModal #confirm-input {
        margin-bottom: 1;
    }

    DeleteConfirmationModal #instructions {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    DeleteConfirmationModal #button-row {
        align: center middle;
        height: auto;
    }

    DeleteConfirmationModal Button {
        margin: 0 1;
    }

    DeleteConfirmationModal #delete-button {
        background: $error;
    }
    """

    class DeletionConfirmed(Message):
        """Message sent when deletion is confirmed.

        Attributes:
            item_ids: List of item IDs to delete.
        """

        def __init__(self, item_ids: list[str]) -> None:
            """Initialize DeletionConfirmed message.

            Args:
                item_ids: List of item IDs to delete.
            """
            self.item_ids = item_ids
            super().__init__()

    def __init__(
        self,
        items: list["ExfiltratedDataItem"],
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize DeleteConfirmationModal.

        Args:
            items: List of items to delete.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._items = items
        self._is_bulk = len(items) > 1
        self._required_text = "DELETE ALL" if self._is_bulk else "DELETE"

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="dialog"):
            # Warning header
            yield Label(
                "⚠️ PERMANENT DELETION ⚠️",
                id="warning-header",
            )

            # Item information
            if self._is_bulk:
                yield Label(
                    f"You are about to delete {len(self._items)} items:",
                    id="item-label",
                )
                # Show bullet list of items (scrollable)
                item_list = "\n".join(
                    f"  • {item.filename} ({item.target})"
                    for item in self._items[:10]  # Show first 10
                )
                if len(self._items) > 10:
                    item_list += f"\n  ... and {len(self._items) - 10} more"
                yield Static(item_list, id="item-list")
            else:
                item = self._items[0]
                yield Static(
                    f"File: {item.filename}\n"
                    f"Target: {item.target}\n"
                    f"Size: {format_size(item.size_bytes)}",
                    id="item-info",
                )

            # Instructions
            yield Label(
                f'Type "{self._required_text}" to confirm:',
                id="instructions",
            )

            # Confirmation input
            yield Input(
                placeholder=self._required_text,
                id="confirm-input",
            )

            # Buttons
            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="default", id="cancel-button")
                yield Button("Delete", variant="error", id="delete-button")

    def on_mount(self) -> None:
        """Focus the input on mount."""
        self.query_one("#confirm-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-button":
            self.dismiss(None)
        elif event.button.id == "delete-button":
            self._attempt_confirm()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        if event.input.id == "confirm-input":
            self._attempt_confirm()

    def _attempt_confirm(self) -> None:
        """Attempt to confirm deletion based on input text."""
        input_widget = self.query_one("#confirm-input", Input)
        input_text = input_widget.value.strip().upper()

        if self._is_valid_confirmation(input_text):
            # Confirmed - send message with item IDs
            item_ids = [item.id for item in self._items]
            self.dismiss(self.DeletionConfirmed(item_ids))
        else:
            # Invalid - show error
            input_widget.styles.border = ("solid", "red")
            self.notify(
                f'Please type "{self._required_text}" exactly to confirm deletion.',
                severity="error",
            )

    def _is_valid_confirmation(self, text: str) -> bool:
        """Check if confirmation text is valid.

        Args:
            text: Text entered by user.

        Returns:
            True if text matches required confirmation (case-insensitive).
        """
        return text.strip().upper() == self._required_text

    def action_cancel(self) -> None:
        """Cancel the modal (Escape key)."""
        self.dismiss(None)
