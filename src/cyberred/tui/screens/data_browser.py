"""Exfiltrated Data Browser Screen.

Story 11.2: Exfiltrated Data Browser

Provides TUI screen for browsing and viewing exfiltrated data:
- Three-column layout: Categories | Data List | Preview
- Keyboard navigation (j/k, Enter, Esc, /, c)
- Search and filter functionality
- Decryption on-the-fly for previews

Per FR42: Access all exfiltrated data via TUI menu
Per FR43: Data encrypted at rest
Per FR44: No auto-delete

UX References:
- Lines 496-500: DataTable for virtualized lists
- Lines 575-585: State patterns (Loading, Empty, Error)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Label, Static

from cyberred.tui.utils import format_size
from cyberred.tui.widgets.data_preview import CategoryTabs, DataItemPreview
from cyberred.tui.widgets.delete_confirmation import DeleteConfirmationModal
from cyberred.tui.widgets.export_dialog import ExportDialog

if TYPE_CHECKING:
    from cyberred.storage.evidence import ExfiltratedDataItem, ExfiltratedDataStore
    from cyberred.storage.exporter import DataExporter

logger = logging.getLogger(__name__)


class DataBrowserScreen(Screen):
    """Exfiltrated Data Browser TUI Screen.

    Per FR42: Access all exfiltrated data via TUI menu.

    Layout:
        - Left: CategoryTabs (category filter)
        - Center: Search input + DataTable (item list)
        - Right: DataItemPreview (selected item preview)

    Keybindings:
        - Escape: Go back
        - j/k: Navigate list (vim style)
        - Enter: View selected item
        - /: Focus search
        - c: Clear filters
        - e: Export selected item
    """

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "view_item", "View"),
        Binding("/", "focus_search", "Search"),
        Binding("e", "export_item", "Export"),
        Binding("E", "export_selected", "Export All", show=False),
        Binding("d", "delete_item", "Delete"),
        Binding("D", "delete_selected", "Delete All", show=False),
        Binding("space", "toggle_selection", "Select", show=False),
        Binding("c", "clear_filters", "Clear Filters"),
    ]

    DEFAULT_CSS = """
    DataBrowserScreen {
        layout: grid;
        grid-size: 3 1;
        grid-columns: 1fr 2fr 2fr;
    }

    DataBrowserScreen #left-panel {
        width: 100%;
        height: 100%;
        border: solid $primary;
        padding: 1;
    }

    DataBrowserScreen #center-panel {
        width: 100%;
        height: 100%;
        border: solid $primary;
        padding: 1;
    }

    DataBrowserScreen #right-panel {
        width: 100%;
        height: 100%;
    }

    DataBrowserScreen #search-input {
        margin-bottom: 1;
    }

    DataBrowserScreen #data-table {
        height: 100%;
    }

    DataBrowserScreen #empty-state {
        text-align: center;
        margin-top: 5;
        color: $text-muted;
    }

    DataBrowserScreen .title {
        text-style: bold;
        margin-bottom: 1;
    }
    """

    _current_category: reactive[str | None] = reactive(None)
    _search_query: reactive[str] = reactive("")
    _selected_item_id: reactive[str | None] = reactive(None)

    def __init__(
        self,
        store: ExfiltratedDataStore,
        engagement_name: str = "engagement",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize DataBrowserScreen.

        Args:
            store: ExfiltratedDataStore instance.
            engagement_name: Name of current engagement for export paths.
            name: Screen name.
            id: Screen ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._store = store
        self._engagement_name = engagement_name
        self._items: list[ExfiltratedDataItem] = []
        self._selected_items: set[str] = set()  # Instance variable for multi-selection
        self._current_category = None
        self._search_query = ""
        self._selected_item_id = None

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()

        with Horizontal():
            # Left panel: Categories
            with Vertical(id="left-panel"):
                yield Label("📁 Categories", classes="title")
                yield CategoryTabs(
                    categories=self._store.get_categories(),
                    id="category-tabs",
                )

            # Center panel: Search + Data list
            with Vertical(id="center-panel"):
                yield Label("📋 Exfiltrated Data", classes="title")
                yield Input(
                    placeholder="Search by filename, target, or category...",
                    id="search-input",
                )

                if self._store.is_empty:
                    yield Static(
                        "📭 [bold]No exfiltrated data yet[/bold]\n\n"
                        "Data will appear here as agents collect it during the engagement.\n\n"
                        "[dim]Tip: PostEx agents collect credentials, configs, and documents "
                        "from compromised systems.[/dim]",
                        id="empty-state",
                    )
                else:
                    table = DataTable(id="data-table")
                    table.cursor_type = "row"
                    yield table

            # Right panel: Preview
            with Vertical(id="right-panel"):
                yield DataItemPreview(id="item-preview")

        yield Footer()

    def on_mount(self) -> None:
        """Handle screen mount."""
        self._refresh_data()

        # Show empty state in preview if needed
        preview = self.query_one("#item-preview", DataItemPreview)
        if self._store.is_empty:
            preview.show_empty_state(
                "No Data",
                "No exfiltrated data has been collected yet.",
            )
        else:
            preview.show_empty_state(
                "Select an Item",
                "Select an item from the list to preview.",
            )

    def _refresh_data(self) -> None:
        """Refresh the data table."""
        if self._store.is_empty:
            return

        # Get items based on current filters
        if self._search_query:
            self._items = self._store.search(self._search_query)
        else:
            self._items = self._store.list_items(category=self._current_category)

        # Update table
        try:
            table = self.query_one("#data-table", DataTable)
        except Exception:
            # Table not mounted yet or doesn't exist
            return

        # Clear and repopulate
        table.clear(columns=True)
        table.add_columns("Filename", "Category", "Target", "Size", "Time")

        for item in self._items:
            table.add_row(
                item.filename,
                item.category,
                item.target,
                format_size(item.size_bytes),
                item.timestamp.strftime("%Y-%m-%d %H:%M"),
                key=item.id,
            )

        # Update category tabs
        try:
            tabs = self.query_one("#category-tabs", CategoryTabs)
            tabs.update_counts(self._store.get_categories())
        except Exception:
            pass

    def _set_category_filter(self, category: str | None) -> None:
        """Set category filter.

        Args:
            category: Category to filter by, or None for all.
        """
        self._current_category = category
        self._refresh_data()

    def _clear_filters(self) -> None:
        """Clear all filters."""
        self._current_category = None
        self._search_query = ""

        try:
            search_input = self.query_one("#search-input", Input)
            search_input.value = ""
        except Exception:
            pass

        self._refresh_data()

    def on_category_tabs_category_selected(
        self, event: CategoryTabs.CategorySelected
    ) -> None:
        """Handle category selection."""
        self._set_category_filter(event.category)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search-input":
            self._search_query = event.value
            self._refresh_data()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in data table."""
        if event.row_key is None:
            return

        item_id = str(event.row_key.value)
        self._selected_item_id = item_id
        self._show_item_preview(item_id)

    def on_data_table_row_highlighted(
        self, event: DataTable.RowHighlighted
    ) -> None:
        """Handle row highlight (cursor movement)."""
        if event.row_key is None:
            return

        item_id = str(event.row_key.value)
        self._selected_item_id = item_id
        self._show_item_preview(item_id)

    def _show_item_preview(self, item_id: str) -> None:
        """Show preview for selected item.

        Args:
            item_id: ID of item to preview.
        """
        item = self._store.get_item(item_id)
        if item is None:
            return

        preview = self.query_one("#item-preview", DataItemPreview)

        # Get content for text files
        content = None
        if item.is_text:
            try:
                content = self._store.get_item_content(item_id)
            except Exception as e:
                logger.error(f"Failed to decrypt content for {item_id}: {e}")

        preview.show_item(item, content=content)

    def action_cursor_down(self) -> None:
        """Move cursor down in data table."""
        if self._store.is_empty:
            return

        try:
            table = self.query_one("#data-table", DataTable)
            table.action_cursor_down()
        except Exception:
            pass

    def action_cursor_up(self) -> None:
        """Move cursor up in data table."""
        if self._store.is_empty:
            return

        try:
            table = self.query_one("#data-table", DataTable)
            table.action_cursor_up()
        except Exception:
            pass

    def action_view_item(self) -> None:
        """View selected item (Enter key)."""
        if self._selected_item_id:
            self._show_item_preview(self._selected_item_id)

    def action_focus_search(self) -> None:
        """Focus search input (/ key)."""
        try:
            search_input = self.query_one("#search-input", Input)
            search_input.focus()
        except Exception:
            pass

    def action_clear_filters(self) -> None:
        """Clear all filters (c key)."""
        self._clear_filters()

    def action_export_item(self) -> None:
        """Export selected item (e key)."""
        if not self._selected_item_id:
            self.notify("No item selected", severity="warning")
            return

        item = self._store.get_item(self._selected_item_id)
        if item is None:
            self.notify("Item not found", severity="error")
            return

        # Get default export path using engagement name per AC #1
        from cyberred.storage.exporter import DataExporter
        default_path = DataExporter.DEFAULT_EXPORT_DIR / self._engagement_name / item.filename

        dialog = ExportDialog(
            item_ids=[self._selected_item_id],
            default_path=default_path,
            single_item=True,
        )
        self.app.push_screen(dialog, self._handle_export_result)

    def action_export_selected(self) -> None:
        """Export all selected items (E/Shift+E key)."""
        if not self._selected_items:
            # Fall back to single item if no multi-selection
            self.action_export_item()
            return

        from cyberred.storage.exporter import DataExporter
        from datetime import datetime, timezone

        # Use engagement name in archive path per AC #4
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        default_path = DataExporter.DEFAULT_EXPORT_DIR / f"{self._engagement_name}_export_{timestamp}.zip"

        dialog = ExportDialog(
            item_ids=list(self._selected_items),
            default_path=default_path,
            single_item=False,
        )
        self.app.push_screen(dialog, self._handle_export_result)

    def action_toggle_selection(self) -> None:
        """Toggle selection of current item (Space key)."""
        if not self._selected_item_id:
            return

        if self._selected_item_id in self._selected_items:
            self._selected_items.discard(self._selected_item_id)
        else:
            self._selected_items.add(self._selected_item_id)

        # Update visual indicator in table
        self._update_selection_visuals()

        # Update status bar with selection count
        count = len(self._selected_items)
        if count > 0:
            self.notify(f"{count} item{'s' if count > 1 else ''} selected (E to export)", severity="information")
        else:
            self.notify("Selection cleared", severity="information")

    def _update_selection_visuals(self) -> None:
        """Update visual indicators for selected items in the data table."""
        if self._store.is_empty:
            return

        try:
            table = self.query_one("#data-table", DataTable)
            
            # Update each row to show selection state
            for row_key in table.rows:
                item_id = str(row_key.value)
                is_selected = item_id in self._selected_items
                
                # Get current filename from first column
                row_data = table.get_row(row_key)
                if row_data:
                    filename = str(row_data[0])
                    # Add/remove checkbox indicator
                    if is_selected and not filename.startswith("☑ "):
                        new_filename = f"☑ {filename}"
                        table.update_cell(row_key, "Filename", new_filename)
                    elif not is_selected and filename.startswith("☑ "):
                        new_filename = filename[2:]  # Remove "☑ "
                        table.update_cell(row_key, "Filename", new_filename)
        except Exception as e:
            logger.debug(f"Could not update selection visuals: {e}")

    def _handle_export_result(self, result: ExportDialog.ExportRequested | None) -> None:
        """Handle export dialog result.

        Args:
            result: Export request or None if cancelled.
        """
        if result is None:
            return  # Cancelled

        # Perform export in background
        self._do_export(result)

    def _do_export(self, request: ExportDialog.ExportRequested) -> None:
        """Perform the actual export.

        Args:
            request: Export request with items and destination.
        """
        try:
            from cyberred.storage.exporter import DataExporter, ExportProgress

            # Get audit logger - use stub if real one not available
            audit_logger = self._get_audit_logger()

            exporter = DataExporter(
                store=self._store,
                audit_logger=audit_logger,
                engagement_name=self._engagement_name,
            )

            if request.as_archive:
                # Archive export for multiple items
                result = exporter.export_archive(request.item_ids, request.destination)
                self.notify(
                    f"Exported {len(request.item_ids)} items to {result}",
                    title="Export Complete",
                    severity="information",
                )
            elif len(request.item_ids) == 1:
                # Single item export
                result = exporter.export_single_item(request.item_ids[0], request.destination)
                self.notify(
                    f"Exported to {result}",
                    title="Export Complete",
                    severity="information",
                )
            else:
                # Multi-item individual files export (not archive)
                # Export each item to destination directory
                dest_dir = request.destination.parent if request.destination.suffix else request.destination
                dest_dir.mkdir(parents=True, exist_ok=True)
                
                exported_count = 0
                for item_id in request.item_ids:
                    item = self._store.get_item(item_id)
                    if item is not None:
                        item_dest = dest_dir / item.filename
                        exporter.export_single_item(item_id, item_dest)
                        exported_count += 1
                
                self.notify(
                    f"Exported {exported_count} files to {dest_dir}",
                    title="Export Complete",
                    severity="information",
                )

            # Clear multi-selection after successful export
            self._selected_items.clear()
            self._update_selection_visuals()

        except Exception as e:
            logger.error(f"Export failed: {e}")
            self.notify(f"Export failed: {e}", title="Error", severity="error")

    def _get_audit_logger(self):
        """Get export audit logger instance.
        
        Returns:
            ExportAuditLogger instance or new instance if not initialized.
        """
        try:
            from cyberred.core.audit import get_export_audit_logger, ExportAuditLogger
            audit_logger = get_export_audit_logger()
            if audit_logger is not None:
                return audit_logger
            # Return a new instance without Redis (logs locally only)
            return ExportAuditLogger()
        except Exception as e:
            logger.debug(f"Could not get export audit logger: {e}")
        
        # Fallback stub logger for backwards compatibility
        class StubAuditLogger:
            """Stub audit logger when real one not available."""
            def log_export(self, **kwargs):
                logger.info(f"Export logged: {kwargs}")
            def log_archive_export(self, **kwargs):
                logger.info(f"Archive export logged: {kwargs}")
        
        return StubAuditLogger()

    def action_delete_item(self) -> None:
        """Delete selected item (d key)."""
        if not self._selected_item_id:
            self.notify("No item selected", severity="warning")
            return

        item = self._store.get_item(self._selected_item_id)
        if item is None:
            self.notify("Item not found", severity="error")
            return

        # Show confirmation modal
        modal = DeleteConfirmationModal(items=[item])
        self.app.push_screen(modal, self._handle_delete_result)

    def action_delete_selected(self) -> None:
        """Delete all selected items (D/Shift+D key)."""
        if not self._selected_items:
            # Fall back to single item if no multi-selection
            self.action_delete_item()
            return

        # Get all selected items
        items = []
        for item_id in self._selected_items:
            item = self._store.get_item(item_id)
            if item is not None:
                items.append(item)

        if not items:
            self.notify("No valid items selected", severity="error")
            return

        # Show confirmation modal
        modal = DeleteConfirmationModal(items=items)
        self.app.push_screen(modal, self._handle_delete_result)

    def _handle_delete_result(
        self, result: DeleteConfirmationModal.DeletionConfirmed | None
    ) -> None:
        """Handle delete confirmation modal result.

        Args:
            result: Deletion confirmation or None if cancelled.
        """
        if result is None:
            return  # Cancelled

        # Perform deletion
        self._do_delete(result.item_ids)

    def _do_delete(self, item_ids: list[str]) -> None:
        """Perform the actual deletion.

        Args:
            item_ids: List of item IDs to delete.
        """
        try:
            from cyberred.storage.deleter import SecureDeleter

            # Get audit logger
            audit_logger = self._get_deletion_audit_logger()

            deleter = SecureDeleter(
                store=self._store,
                audit_logger=audit_logger,
            )

            if len(item_ids) == 1:
                # Single item deletion
                deleter.delete_item(item_ids[0])
                self.notify(
                    "Item deleted securely",
                    title="Deletion Complete",
                    severity="information",
                )
            else:
                # Bulk deletion
                result = deleter.delete_items(item_ids, continue_on_error=True)
                if result.success:
                    self.notify(
                        f"Deleted {result.deleted_items} items securely",
                        title="Deletion Complete",
                        severity="information",
                    )
                else:
                    self.notify(
                        f"Deleted {result.deleted_items} of {result.total_items} items. "
                        f"{len(result.failed_items)} failed.",
                        title="Partial Deletion",
                        severity="warning",
                    )

            # Clear selection and refresh
            self._selected_items.clear()
            self._selected_item_id = None
            self._refresh_data()

            # Update preview to show empty state
            preview = self.query_one("#item-preview", DataItemPreview)
            preview.show_empty_state(
                "Select an Item",
                "Select an item from the list to preview.",
            )

        except Exception as e:
            logger.error(f"Deletion failed: {e}")
            self.notify(f"Deletion failed: {e}", title="Error", severity="error")

    def _get_deletion_audit_logger(self):
        """Get deletion audit logger instance.

        Returns:
            DeletionAuditLogger instance or new instance if not initialized.
        """
        try:
            from cyberred.core.audit import get_deletion_audit_logger, DeletionAuditLogger
            audit_logger = get_deletion_audit_logger()
            if audit_logger is not None:
                return audit_logger
            # Return a new instance without Redis (logs locally only)
            return DeletionAuditLogger()
        except Exception as e:
            logger.debug(f"Could not get deletion audit logger: {e}")

        # Fallback stub logger for backwards compatibility
        class StubDeletionAuditLogger:
            """Stub audit logger when real one not available."""
            def log_deletion(self, item_id, filename, target, size_bytes):
                logger.info(f"Deletion logged: {item_id} ({filename})")
            def log_bulk_deletion(self, item_ids, total_deleted, total_failed):
                logger.info(f"Bulk deletion logged: {total_deleted} deleted, {total_failed} failed")

        return StubDeletionAuditLogger()

    def action_pop_screen(self) -> None:
        """Go back (Escape key)."""
        self.app.pop_screen()
