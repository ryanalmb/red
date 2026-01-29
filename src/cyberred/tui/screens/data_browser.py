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

from cyberred.tui.widgets.data_preview import CategoryTabs, DataItemPreview

if TYPE_CHECKING:
    from cyberred.storage.evidence import ExfiltratedDataItem, ExfiltratedDataStore

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
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize DataBrowserScreen.

        Args:
            store: ExfiltratedDataStore instance.
            name: Screen name.
            id: Screen ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._store = store
        self._items: list[ExfiltratedDataItem] = []
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
                self._format_size(item.size_bytes),
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
        # TODO: Implement export in Story 11-3
        if self._selected_item_id:
            self.notify(
                f"Export functionality coming in Story 11.3",
                title="Export",
                severity="information",
            )

    def action_pop_screen(self) -> None:
        """Go back (Escape key)."""
        self.app.pop_screen()

    def _format_size(self, size_bytes: int) -> str:
        """Format size in human-readable form.

        Args:
            size_bytes: Size in bytes.

        Returns:
            Formatted string (e.g., "1.5 KB").
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
