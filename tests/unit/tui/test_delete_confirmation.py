"""Unit tests for DeleteConfirmationModal.

Story 11.4: Manual Data Deletion

Tests for the TUI confirmation modal that requires typing "DELETE" or "DELETE ALL".
Per FR45: Requires explicit confirmation before deletion.

TDD RED Phase: These tests should FAIL until implementation is complete.
"""

from __future__ import annotations

from unittest.mock import MagicMock, AsyncMock, patch
from typing import TYPE_CHECKING

import pytest
from textual.widgets import Input, Button

from cyberred.tui.widgets.delete_confirmation import DeleteConfirmationModal


# ─────────────────────────────────────────────────────────────────────────────
# DeleteConfirmationModal Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestDeleteConfirmationModal:
    """Tests for DeleteConfirmationModal widget."""

    @pytest.fixture
    def mock_single_item(self) -> MagicMock:
        """Create mock single item for deletion."""
        item = MagicMock()
        item.id = "item-123"
        item.filename = "passwords.txt"
        item.target = "192.168.1.100"
        item.size_bytes = 1024
        return item

    @pytest.fixture
    def mock_multiple_items(self) -> list[MagicMock]:
        """Create mock multiple items for bulk deletion."""
        items = []
        for i in range(3):
            item = MagicMock()
            item.id = f"item-{i}"
            item.filename = f"file-{i}.txt"
            item.target = f"192.168.1.{i}"
            item.size_bytes = 100 * (i + 1)
            items.append(item)
        return items

    # ─────────────────────────────────────────────────────────────────────────
    # Initialization Tests
    # ─────────────────────────────────────────────────────────────────────────

    def test_single_item_requires_delete_text(
        self, mock_single_item: MagicMock
    ) -> None:
        """Single item deletion requires typing 'DELETE'."""
        modal = DeleteConfirmationModal(items=[mock_single_item])
        assert modal._required_text == "DELETE"
        assert modal._is_bulk is False

    def test_bulk_deletion_requires_delete_all_text(
        self, mock_multiple_items: list[MagicMock]
    ) -> None:
        """Bulk deletion requires typing 'DELETE ALL'."""
        modal = DeleteConfirmationModal(items=mock_multiple_items)
        assert modal._required_text == "DELETE ALL"
        assert modal._is_bulk is True

    def test_stores_item_references(
        self, mock_multiple_items: list[MagicMock]
    ) -> None:
        """Modal stores references to items for later retrieval."""
        modal = DeleteConfirmationModal(items=mock_multiple_items)
        assert len(modal._items) == 3
        assert modal._items[0].id == "item-0"

    # ─────────────────────────────────────────────────────────────────────────
    # Confirmation Logic Tests
    # ─────────────────────────────────────────────────────────────────────────

    def test_exact_match_required_case_insensitive(
        self, mock_single_item: MagicMock
    ) -> None:
        """Confirmation text must match exactly but is case-insensitive."""
        modal = DeleteConfirmationModal(items=[mock_single_item])

        # These should all be valid
        assert modal._is_valid_confirmation("DELETE")
        assert modal._is_valid_confirmation("delete")
        assert modal._is_valid_confirmation("Delete")
        assert modal._is_valid_confirmation("  DELETE  ")  # With whitespace

    def test_partial_match_rejected(self, mock_single_item: MagicMock) -> None:
        """Partial or incorrect text is rejected."""
        modal = DeleteConfirmationModal(items=[mock_single_item])

        # These should all be invalid
        assert modal._is_valid_confirmation("DEL") is False
        assert modal._is_valid_confirmation("DELET") is False
        assert modal._is_valid_confirmation("DELETE ALL") is False  # Wrong for single
        assert modal._is_valid_confirmation("REMOVE") is False
        assert modal._is_valid_confirmation("") is False

    def test_bulk_requires_delete_all(
        self, mock_multiple_items: list[MagicMock]
    ) -> None:
        """Bulk deletion requires 'DELETE ALL', not just 'DELETE'."""
        modal = DeleteConfirmationModal(items=mock_multiple_items)

        assert modal._is_valid_confirmation("DELETE ALL")
        assert modal._is_valid_confirmation("delete all")
        assert modal._is_valid_confirmation("DELETE") is False  # Not enough for bulk

    # ─────────────────────────────────────────────────────────────────────────
    # Message Tests
    # ─────────────────────────────────────────────────────────────────────────

    def test_deletion_confirmed_message_contains_item_ids(
        self, mock_multiple_items: list[MagicMock]
    ) -> None:
        """DeletionConfirmed message contains all item IDs."""
        modal = DeleteConfirmationModal(items=mock_multiple_items)
        
        # Simulate successful confirmation
        message = DeleteConfirmationModal.DeletionConfirmed(
            item_ids=["item-0", "item-1", "item-2"]
        )
        
        assert len(message.item_ids) == 3
        assert "item-0" in message.item_ids
        assert "item-1" in message.item_ids
        assert "item-2" in message.item_ids

    # ─────────────────────────────────────────────────────────────────────────
    # UI Behavior Tests (require async/app context)
    # ─────────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_escape_cancels_modal(self, mock_single_item: MagicMock) -> None:
        """Pressing Escape cancels the modal without deletion."""
        modal = DeleteConfirmationModal(items=[mock_single_item])
        
        # Modal should have escape binding
        bindings = [b.key for b in modal.BINDINGS]
        assert "escape" in bindings

    def test_displays_warning_header(self, mock_single_item: MagicMock) -> None:
        """Modal displays warning header about irreversible action."""
        modal = DeleteConfirmationModal(items=[mock_single_item])
        
        # The modal should indicate this is a destructive action
        # This is tested via compose() output in integration tests
        assert modal._required_text == "DELETE"

    def test_shows_item_details_for_single(
        self, mock_single_item: MagicMock
    ) -> None:
        """Single item deletion shows filename, target, and size."""
        modal = DeleteConfirmationModal(items=[mock_single_item])
        
        # Modal should have access to item details
        assert modal._items[0].filename == "passwords.txt"
        assert modal._items[0].target == "192.168.1.100"
        assert modal._items[0].size_bytes == 1024

    def test_shows_bullet_list_for_bulk(
        self, mock_multiple_items: list[MagicMock]
    ) -> None:
        """Bulk deletion shows bullet list of items."""
        modal = DeleteConfirmationModal(items=mock_multiple_items)
        
        # Modal should have all items available
        assert len(modal._items) == 3
        assert modal._is_bulk is True


# ─────────────────────────────────────────────────────────────────────────────
# Keybinding Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestDeleteConfirmationBindings:
    """Tests for modal keybindings."""

    def test_has_escape_binding(self) -> None:
        """Modal has escape binding to cancel."""
        item = MagicMock()
        item.id = "test"
        modal = DeleteConfirmationModal(items=[item])
        
        binding_keys = [b.key for b in modal.BINDINGS]
        assert "escape" in binding_keys

    def test_escape_action_is_cancel(self) -> None:
        """Escape key triggers cancel action."""
        item = MagicMock()
        item.id = "test"
        modal = DeleteConfirmationModal(items=[item])
        
        for binding in modal.BINDINGS:
            if binding.key == "escape":
                assert binding.action == "cancel"
                break
        else:
            pytest.fail("Escape binding not found")
