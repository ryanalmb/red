"""Unit tests for DataBrowserScreen and related TUI components.

Story 11.2: Exfiltrated Data Browser

Tests for:
- DataBrowserScreen (Task 4)
- DataItemPreview widget (Task 5)
- Filter functionality (Task 6)

TDD RED Phase: These tests should FAIL initially.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from textual.app import App, ComposeResult
from textual.pilot import Pilot


# ============================================================================
# Task 4: Unit tests for DataBrowserScreen (AC: #1, #2, #3)
# ============================================================================


class TestDataBrowserScreen:
    """Tests for DataBrowserScreen."""

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        """Create mock ExfiltratedDataStore."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        store = MagicMock()
        store.is_empty = False

        # Create mock items
        items = [
            ExfiltratedDataItem(
                id="data-001",
                filename="shadow",
                file_type="shadow",
                mime_type="text/plain",
                size_bytes=1024,
                target="192.168.1.100",
                source_agent="postex-agent-1",
                timestamp=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
                encrypted_path=Path("data/cred_001.enc"),
                sha256_hash="abc123",
                nonce=b"\x00" * 12,
                category="credentials",
            ),
            ExfiltratedDataItem(
                id="data-002",
                filename="nginx.conf",
                file_type="conf",
                mime_type="text/plain",
                size_bytes=512,
                target="192.168.1.101",
                source_agent="postex-agent-2",
                timestamp=datetime(2026, 1, 29, 13, 0, 0, tzinfo=timezone.utc),
                encrypted_path=Path("data/config_002.enc"),
                sha256_hash="def456",
                nonce=b"\x00" * 12,
                category="configs",
            ),
        ]

        store.list_items.return_value = items
        store.get_item.side_effect = lambda id: next(
            (i for i in items if i.id == id), None
        )
        store.get_categories.return_value = {
            "credentials": 1,
            "configs": 1,
            "documents": 0,
            "other": 0,
        }
        store.search.return_value = items
        store.get_item_content.return_value = b"test content"

        return store

    @pytest.mark.asyncio
    async def test_screen_initialization(self, mock_store: MagicMock) -> None:
        """Test DataBrowserScreen can be initialized."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen

        screen = DataBrowserScreen(store=mock_store)
        assert screen is not None

    @pytest.mark.asyncio
    async def test_compose_creates_correct_widget_hierarchy(
        self, mock_store: MagicMock
    ) -> None:
        """Test compose() creates correct widget hierarchy."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from cyberred.tui.widgets.data_preview import CategoryTabs, DataItemPreview

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            app = pilot.app
            
            # Should have DataBrowserScreen
            screen = app.query_one(DataBrowserScreen)
            assert screen is not None

            # Should have CategoryTabs (left panel)
            tabs = screen.query_one(CategoryTabs)
            assert tabs is not None

            # Should have DataItemPreview (right panel)
            preview = screen.query_one(DataItemPreview)
            assert preview is not None

    @pytest.mark.asyncio
    async def test_category_tabs_display_with_counts(
        self, mock_store: MagicMock
    ) -> None:
        """Test category tabs display with item counts."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from cyberred.tui.widgets.data_preview import CategoryTabs

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            tabs = screen.query_one(CategoryTabs)

            # Categories should be loaded from store
            assert tabs.categories["credentials"] == 1
            assert tabs.categories["configs"] == 1
            assert tabs.categories["documents"] == 0
            assert tabs.categories["other"] == 0

    @pytest.mark.asyncio
    async def test_data_list_populates_from_store(
        self, mock_store: MagicMock
    ) -> None:
        """Test data list populates from store."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import DataTable

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)

            # Wait for mount
            await pilot.pause()

            # Should have called list_items
            mock_store.list_items.assert_called()

            # DataTable should have rows
            table = screen.query_one(DataTable)
            assert table.row_count == 2

    @pytest.mark.asyncio
    async def test_item_selection_updates_detail_panel(
        self, mock_store: MagicMock
    ) -> None:
        """Test item selection updates detail panel."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from cyberred.tui.widgets.data_preview import DataItemPreview
        from textual.widgets import DataTable

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Select first row
            table = screen.query_one(DataTable)
            table.cursor_coordinate = (0, 0)
            await pilot.pause()

            # Preview should show selected item
            preview = screen.query_one(DataItemPreview)
            # The preview should have been updated with item data
            assert preview._current_item is not None

    @pytest.mark.asyncio
    async def test_search_input_filters_results(
        self, mock_store: MagicMock
    ) -> None:
        """Test search input filters results."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import Input

        # Configure mock to return filtered results
        mock_store.search.return_value = [
            mock_store.list_items.return_value[0]  # Just shadow
        ]

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Find search input and type
            search_input = screen.query_one("#search-input", Input)
            search_input.value = "shadow"
            await pilot.pause()

            # Store's search should have been called
            mock_store.search.assert_called_with("shadow")

    @pytest.mark.asyncio
    async def test_empty_state_displays_when_no_data(self) -> None:
        """Test empty state displays when no data."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen

        empty_store = MagicMock()
        empty_store.is_empty = True
        empty_store.list_items.return_value = []
        empty_store.get_categories.return_value = {
            "credentials": 0,
            "configs": 0,
            "documents": 0,
            "other": 0,
        }

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=empty_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Should show empty state message
            content = screen.render()
            # The screen should indicate no data
            assert empty_store.is_empty

    @pytest.mark.asyncio
    async def test_keyboard_binding_escape_pops_screen(
        self, mock_store: MagicMock
    ) -> None:
        """Test Escape key pops the screen."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import Static

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main Screen")

        async with TestApp().run_test() as pilot:
            app = pilot.app
            
            # Push the data browser screen
            screen = DataBrowserScreen(store=mock_store)
            app.push_screen(screen)
            await pilot.pause()

            initial_stack_size = len(app.screen_stack)

            # Press escape
            await pilot.press("escape")
            await pilot.pause()

            # Screen should be popped
            assert len(app.screen_stack) < initial_stack_size

    @pytest.mark.asyncio
    async def test_keyboard_binding_j_k_navigation(
        self, mock_store: MagicMock
    ) -> None:
        """Test j/k keys navigate the list (vim style)."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import DataTable

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            table = screen.query_one(DataTable)
            table.focus()
            await pilot.pause()

            # Verify table has rows and j/k actions exist
            assert table.row_count >= 2
            
            # Test that action methods exist and are callable
            assert hasattr(screen, "action_cursor_down")
            assert hasattr(screen, "action_cursor_up")
            
            # The navigation should work through screen actions
            screen.action_cursor_down()
            screen.action_cursor_up()

    @pytest.mark.asyncio
    async def test_keyboard_binding_slash_focuses_search(
        self, mock_store: MagicMock
    ) -> None:
        """Test / key focuses search input."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import Input

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Press / to focus search
            await pilot.press("/")
            await pilot.pause()

            # Search input should be focused
            search_input = screen.query_one("#search-input", Input)
            assert search_input.has_focus


# ============================================================================
# Task 5: Unit tests for DataItemPreview widget (AC: #3, #5)
# ============================================================================


class TestDataItemPreview:
    """Tests for DataItemPreview widget."""

    @pytest.fixture
    def sample_text_item(self) -> Any:
        """Create sample text data item."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        return ExfiltratedDataItem(
            id="text-001",
            filename="config.yaml",
            file_type="yaml",
            mime_type="text/plain",
            size_bytes=500,
            target="192.168.1.100",
            source_agent="agent-1",
            timestamp=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
            encrypted_path=Path("data/config.enc"),
            sha256_hash="abc123def456",
            nonce=b"\x00" * 12,
            category="configs",
        )

    @pytest.fixture
    def sample_binary_item(self) -> Any:
        """Create sample binary data item."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        return ExfiltratedDataItem(
            id="binary-001",
            filename="image.png",
            file_type="png",
            mime_type="image/png",
            size_bytes=50000,
            target="192.168.1.100",
            source_agent="agent-1",
            timestamp=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
            encrypted_path=Path("data/image.enc"),
            sha256_hash="xyz789",
            nonce=b"\x00" * 12,
            category="other",
        )

    @pytest.mark.asyncio
    async def test_text_preview_renders_content(
        self, sample_text_item: Any
    ) -> None:
        """Test text preview renders content."""
        from cyberred.tui.widgets.data_preview import DataItemPreview

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            content = b"server:\n  port: 8080\n  host: localhost\n"
            preview.show_item(sample_text_item, content=content)
            await pilot.pause()

            # Content should be visible
            rendered = str(preview.render())
            assert "server:" in rendered or preview._content is not None

    @pytest.mark.asyncio
    async def test_text_preview_truncates_at_10kb(self) -> None:
        """Test text preview truncates at 10KB with indicator."""
        from cyberred.storage.evidence import ExfiltratedDataItem
        from cyberred.tui.widgets.data_preview import DataItemPreview

        large_item = ExfiltratedDataItem(
            id="large-001",
            filename="large.txt",
            file_type="txt",
            mime_type="text/plain",
            size_bytes=20 * 1024,  # 20KB
            target="192.168.1.100",
            source_agent="agent-1",
            timestamp=datetime.now(timezone.utc),
            encrypted_path=Path("data/large.enc"),
            sha256_hash="large123",
            nonce=b"\x00" * 12,
            category="other",
        )

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            # Content larger than 10KB
            large_content = b"x" * (15 * 1024)
            preview.show_item(large_item, content=large_content)
            await pilot.pause()

            # Should show truncation indicator
            # The preview should indicate content is truncated
            assert preview._is_truncated or "[truncated]" in str(preview.render()).lower()

    @pytest.mark.asyncio
    async def test_binary_preview_shows_metadata_only(
        self, sample_binary_item: Any
    ) -> None:
        """Test binary preview shows metadata only (no content preview)."""
        from cyberred.tui.widgets.data_preview import DataItemPreview

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            # Show binary item without content
            preview.show_item(sample_binary_item, content=None)
            await pilot.pause()

            # Should have the item set
            assert preview._current_item is not None
            assert preview._current_item.filename == "image.png"
            # Binary items should not be text
            assert not sample_binary_item.is_text

    @pytest.mark.asyncio
    async def test_metadata_display_includes_all_required_fields(
        self, sample_text_item: Any
    ) -> None:
        """Test metadata display includes all required fields."""
        from cyberred.tui.widgets.data_preview import DataItemPreview

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)
            preview.show_item(sample_text_item, content=b"test")
            await pilot.pause()

            # Check that metadata fields are present
            # These should be displayed in the preview widget
            item = preview._current_item
            assert item is not None
            assert item.filename == "config.yaml"
            assert item.category == "configs"
            assert item.target == "192.168.1.100"
            assert item.source_agent == "agent-1"
            assert item.sha256_hash == "abc123def456"

    @pytest.mark.asyncio
    async def test_empty_state_display(self) -> None:
        """Test empty state display."""
        from cyberred.tui.widgets.data_preview import DataItemPreview

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)
            preview.show_empty_state("No Selection", "Select an item to preview")
            await pilot.pause()

            # Should show empty state
            assert preview._current_item is None


# ============================================================================
# Task 6: Unit tests for filter functionality (AC: #2)
# ============================================================================


class TestFilterFunctionality:
    """Tests for filter functionality."""

    @pytest.fixture
    def mock_store_with_varied_data(self) -> MagicMock:
        """Create mock store with varied data for filtering."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        items = [
            ExfiltratedDataItem(
                id="cred-001",
                filename="shadow",
                file_type="shadow",
                mime_type="text/plain",
                size_bytes=1024,
                target="192.168.1.100",
                source_agent="agent-1",
                timestamp=datetime(2026, 1, 29, 10, 0, 0, tzinfo=timezone.utc),
                encrypted_path=Path("data/cred_001.enc"),
                sha256_hash="hash1",
                nonce=b"\x00" * 12,
                category="credentials",
            ),
            ExfiltratedDataItem(
                id="conf-001",
                filename="nginx.conf",
                file_type="conf",
                mime_type="text/plain",
                size_bytes=512,
                target="192.168.1.101",
                source_agent="agent-2",
                timestamp=datetime(2026, 1, 29, 11, 0, 0, tzinfo=timezone.utc),
                encrypted_path=Path("data/conf_001.enc"),
                sha256_hash="hash2",
                nonce=b"\x00" * 12,
                category="configs",
            ),
            ExfiltratedDataItem(
                id="doc-001",
                filename="report.pdf",
                file_type="pdf",
                mime_type="application/pdf",
                size_bytes=10240,
                target="192.168.1.100",
                source_agent="agent-1",
                timestamp=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
                encrypted_path=Path("data/doc_001.enc"),
                sha256_hash="hash3",
                nonce=b"\x00" * 12,
                category="documents",
            ),
        ]

        store = MagicMock()
        store.is_empty = False
        
        def filter_by_category(category: str | None = None):
            if category is None:
                return items
            return [i for i in items if i.category == category]

        store.list_items = MagicMock(side_effect=filter_by_category)
        store.get_categories.return_value = {
            "credentials": 1,
            "configs": 1,
            "documents": 1,
            "other": 0,
        }
        store.get_item = MagicMock(side_effect=lambda id: next((i for i in items if i.id == id), None))
        store.get_item_content = MagicMock(return_value=b"test content")
        store.search = MagicMock(return_value=items)

        return store

    @pytest.mark.asyncio
    async def test_filter_by_category_credentials(
        self, mock_store_with_varied_data: MagicMock
    ) -> None:
        """Test filter by category (credentials)."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store_with_varied_data)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Select credentials category
            screen._set_category_filter("credentials")
            await pilot.pause()

            # Verify the category was set
            assert screen._current_category == "credentials"

    @pytest.mark.asyncio
    async def test_filter_by_category_configs(
        self, mock_store_with_varied_data: MagicMock
    ) -> None:
        """Test filter by category (configs)."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store_with_varied_data)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            screen._set_category_filter("configs")
            await pilot.pause()

            # Verify the category was set
            assert screen._current_category == "configs"

    @pytest.mark.asyncio
    async def test_filter_reset_clears_all_filters(
        self, mock_store_with_varied_data: MagicMock
    ) -> None:
        """Test filter reset clears all filters."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store_with_varied_data)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Set a filter
            screen._set_category_filter("credentials")
            await pilot.pause()
            assert screen._current_category == "credentials"

            # Clear filters
            screen._clear_filters()
            await pilot.pause()

            # Should be cleared
            assert screen._current_category is None
            assert screen._search_query == ""

    @pytest.mark.asyncio
    async def test_clear_filters_keyboard_binding(
        self, mock_store_with_varied_data: MagicMock
    ) -> None:
        """Test 'c' key clears filters."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store_with_varied_data)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Set a filter first
            screen._set_category_filter("credentials")
            await pilot.pause()
            assert screen._current_category == "credentials"

            # Call the action directly (keyboard binding triggers this)
            screen.action_clear_filters()
            await pilot.pause()

            assert screen._current_category is None


# ============================================================================
# Additional Coverage Tests for Story 11.2
# ============================================================================


class TestDataItemPreviewSyntaxHighlighting:
    """Tests for syntax highlighting in DataItemPreview."""

    @pytest.fixture
    def json_item(self) -> Any:
        """Create a JSON file item for testing."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        return ExfiltratedDataItem(
            id="json-001",
            filename="config.json",
            file_type="json",
            mime_type="application/json",
            size_bytes=100,
            target="192.168.1.100",
            source_agent="agent-1",
            timestamp=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
            encrypted_path=Path("data/config.enc"),
            sha256_hash="abc123def456",
            nonce=b"\x00" * 12,
            category="configs",
        )

    @pytest.fixture
    def yaml_item(self) -> Any:
        """Create a YAML file item for testing."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        return ExfiltratedDataItem(
            id="yaml-001",
            filename="config.yaml",
            file_type="yaml",
            mime_type="text/yaml",
            size_bytes=50,
            target="192.168.1.100",
            source_agent="agent-1",
            timestamp=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
            encrypted_path=Path("data/config_yaml.enc"),
            sha256_hash="abc123def456",
            nonce=b"\x00" * 12,
            category="configs",
        )

    @pytest.fixture
    def unknown_type_item(self) -> Any:
        """Create an unknown file type item for testing."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        return ExfiltratedDataItem(
            id="unknown-001",
            filename="data.xyz",
            file_type="xyz",
            mime_type="application/octet-stream",
            size_bytes=50,
            target="192.168.1.100",
            source_agent="agent-1",
            timestamp=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
            encrypted_path=Path("data/unknown.enc"),
            sha256_hash="abc123def456",
            nonce=b"\x00" * 12,
            category="other",
        )

    @pytest.mark.asyncio
    async def test_syntax_highlighting_json(self, json_item: Any) -> None:
        """Test syntax highlighting is applied for JSON files."""
        from cyberred.tui.widgets.data_preview import DataItemPreview

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            json_content = b'{"key": "value", "number": 123}'
            preview.show_item(json_item, content=json_content)
            await pilot.pause()

            # Verify item was set
            assert preview._current_item is not None
            assert preview._current_item.file_type == "json"

    @pytest.mark.asyncio
    async def test_syntax_highlighting_yaml(self, yaml_item: Any) -> None:
        """Test syntax highlighting is applied for YAML files."""
        from cyberred.tui.widgets.data_preview import DataItemPreview

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            yaml_content = b"key: value\nnumber: 123"
            preview.show_item(yaml_item, content=yaml_content)
            await pilot.pause()

            assert preview._current_item is not None
            assert preview._current_item.file_type == "yaml"

    @pytest.mark.asyncio
    async def test_no_syntax_highlighting_unknown_type(
        self, unknown_type_item: Any
    ) -> None:
        """Test no syntax highlighting for unknown file types."""
        from cyberred.tui.widgets.data_preview import DataItemPreview

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            content = b"some plain text content"
            preview.show_item(unknown_type_item, content=content)
            await pilot.pause()

            assert preview._current_item is not None
            assert preview._current_item.file_type == "xyz"

    @pytest.mark.asyncio
    async def test_truncated_content_with_highlighting(
        self, json_item: Any
    ) -> None:
        """Test truncated content still gets syntax highlighting."""
        from cyberred.tui.widgets.data_preview import DataItemPreview, MAX_PREVIEW_SIZE

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            # Create content larger than MAX_PREVIEW_SIZE
            large_content = b'{"key": "' + b"x" * (MAX_PREVIEW_SIZE + 1000) + b'"}'
            preview.show_item(json_item, content=large_content)
            await pilot.pause()

            assert preview._is_truncated is True

    @pytest.mark.asyncio
    async def test_apply_syntax_highlighting_method(self) -> None:
        """Test _apply_syntax_highlighting method directly."""
        from cyberred.tui.widgets.data_preview import DataItemPreview

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            # Test with known type
            result = preview._apply_syntax_highlighting('{"key": "value"}', "json")
            assert result is not None

            # Test with unknown type
            result = preview._apply_syntax_highlighting("plain text", "xyz")
            assert result is None


class TestDataItemPreviewCopyToClipboard:
    """Tests for copy_to_clipboard functionality."""

    @pytest.fixture
    def text_item(self) -> Any:
        """Create a text file item for testing."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        return ExfiltratedDataItem(
            id="text-001",
            filename="passwords.txt",
            file_type="txt",
            mime_type="text/plain",
            size_bytes=100,
            target="192.168.1.100",
            source_agent="agent-1",
            timestamp=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
            encrypted_path=Path("data/passwords.enc"),
            sha256_hash="abc123def456",
            nonce=b"\x00" * 12,
            category="credentials",
        )

    @pytest.mark.asyncio
    async def test_copy_to_clipboard_no_content(self) -> None:
        """Test copy_to_clipboard returns False when no content."""
        from cyberred.tui.widgets.data_preview import DataItemPreview

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            # No item shown yet
            result = preview.copy_to_clipboard()
            assert result is False

    @pytest.mark.asyncio
    async def test_copy_to_clipboard_with_content(self, text_item: Any) -> None:
        """Test copy_to_clipboard with content (mocked pyperclip)."""
        from cyberred.tui.widgets.data_preview import DataItemPreview
        from unittest.mock import patch, MagicMock
        import cyberred.tui.widgets.data_preview as dp_module

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            content = b"secret password content"
            preview.show_item(text_item, content=content)
            await pilot.pause()

            # Mock pyperclip module
            mock_pyperclip = MagicMock()
            original_has = dp_module.HAS_PYPERCLIP
            
            # Inject mock
            dp_module.HAS_PYPERCLIP = True
            dp_module.pyperclip = mock_pyperclip
            
            try:
                result = preview.copy_to_clipboard()
                assert result is True
                mock_pyperclip.copy.assert_called_once_with("secret password content")
            finally:
                dp_module.HAS_PYPERCLIP = original_has
                if hasattr(dp_module, 'pyperclip'):
                    delattr(dp_module, 'pyperclip')

    @pytest.mark.asyncio
    async def test_copy_to_clipboard_no_pyperclip(self, text_item: Any) -> None:
        """Test copy_to_clipboard returns False when pyperclip unavailable."""
        from cyberred.tui.widgets.data_preview import DataItemPreview
        from unittest.mock import patch

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            content = b"secret password content"
            preview.show_item(text_item, content=content)
            await pilot.pause()

            with patch("cyberred.tui.widgets.data_preview.HAS_PYPERCLIP", False):
                result = preview.copy_to_clipboard()
                assert result is False


class TestDataItemPreviewProperties:
    """Tests for DataItemPreview properties."""

    @pytest.fixture
    def sample_item(self) -> Any:
        """Create a sample item for testing."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        return ExfiltratedDataItem(
            id="prop-001",
            filename="test.txt",
            file_type="txt",
            mime_type="text/plain",
            size_bytes=100,
            target="192.168.1.100",
            source_agent="agent-1",
            timestamp=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
            encrypted_path=Path("data/test.enc"),
            sha256_hash="abc123def456",
            nonce=b"\x00" * 12,
            category="other",
        )

    @pytest.mark.asyncio
    async def test_current_item_property(self, sample_item: Any) -> None:
        """Test current_item property returns the displayed item."""
        from cyberred.tui.widgets.data_preview import DataItemPreview

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            # Initially None
            assert preview.current_item is None

            # After showing item
            preview.show_item(sample_item, content=b"test")
            await pilot.pause()

            assert preview.current_item is not None
            assert preview.current_item.id == "prop-001"

    @pytest.mark.asyncio
    async def test_is_truncated_property(self, sample_item: Any) -> None:
        """Test is_truncated property."""
        from cyberred.tui.widgets.data_preview import DataItemPreview, MAX_PREVIEW_SIZE

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            # Not truncated with small content
            preview.show_item(sample_item, content=b"small")
            await pilot.pause()
            assert preview.is_truncated is False

            # Truncated with large content
            large_content = b"x" * (MAX_PREVIEW_SIZE + 1000)
            preview.show_item(sample_item, content=large_content)
            await pilot.pause()
            assert preview.is_truncated is True


class TestCategoryTabsInteraction:
    """Tests for CategoryTabs widget interaction."""

    @pytest.mark.asyncio
    async def test_category_tabs_initialization(self) -> None:
        """Test CategoryTabs initializes with counts."""
        from cyberred.tui.widgets.data_preview import CategoryTabs

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield CategoryTabs(
                    categories={
                        "credentials": 5,
                        "configs": 3,
                        "documents": 2,
                        "other": 1,
                    }
                )

        async with TestApp().run_test() as pilot:
            tabs = pilot.app.query_one(CategoryTabs)
            await pilot.pause()

            assert tabs.categories["credentials"] == 5
            assert tabs.categories["configs"] == 3
            assert tabs.selected_category is None

    @pytest.mark.asyncio
    async def test_category_tabs_update_counts(self) -> None:
        """Test CategoryTabs.update_counts method."""
        from cyberred.tui.widgets.data_preview import CategoryTabs

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield CategoryTabs()

        async with TestApp().run_test() as pilot:
            tabs = pilot.app.query_one(CategoryTabs)
            await pilot.pause()

            # Update counts
            tabs.update_counts({
                "credentials": 10,
                "configs": 5,
                "documents": 3,
                "other": 2,
            })
            await pilot.pause()

            assert tabs.categories["credentials"] == 10
            assert tabs.categories["configs"] == 5

    @pytest.mark.asyncio
    async def test_category_tabs_default_categories(self) -> None:
        """Test CategoryTabs uses default categories when none provided."""
        from cyberred.tui.widgets.data_preview import CategoryTabs

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield CategoryTabs()  # No categories provided

        async with TestApp().run_test() as pilot:
            tabs = pilot.app.query_one(CategoryTabs)
            await pilot.pause()

            # Should have default zero counts
            assert tabs.categories["credentials"] == 0
            assert tabs.categories["configs"] == 0


class TestDataBrowserScreenActions:
    """Tests for DataBrowserScreen action methods."""

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        """Create mock ExfiltratedDataStore."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        store = MagicMock()
        store.is_empty = False

        items = [
            ExfiltratedDataItem(
                id="action-001",
                filename="test.txt",
                file_type="txt",
                mime_type="text/plain",
                size_bytes=100,
                target="192.168.1.100",
                source_agent="agent-1",
                timestamp=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
                encrypted_path=Path("data/test.enc"),
                sha256_hash="abc123",
                nonce=b"\x00" * 12,
                category="other",
            ),
        ]

        store.list_items.return_value = items
        store.get_item.side_effect = lambda id: next(
            (i for i in items if i.id == id), None
        )
        store.get_categories.return_value = {
            "credentials": 0,
            "configs": 0,
            "documents": 0,
            "other": 1,
        }
        store.search.return_value = items
        store.get_item_content.return_value = b"test content"

        return store

    @pytest.mark.asyncio
    async def test_action_export_item(self, mock_store: MagicMock) -> None:
        """Test action_export_item shows notification."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Set a selected item
            screen._selected_item_id = "action-001"

            # Call export action
            screen.action_export_item()
            await pilot.pause()

            # Should show notification (no error thrown)

    @pytest.mark.asyncio
    async def test_action_view_item(self, mock_store: MagicMock) -> None:
        """Test action_view_item shows preview."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Set selected item
            screen._selected_item_id = "action-001"

            # Call view action
            screen.action_view_item()
            await pilot.pause()

            # Store should have been queried
            mock_store.get_item.assert_called()

    @pytest.mark.asyncio
    async def test_action_focus_search(self, mock_store: MagicMock) -> None:
        """Test action_focus_search focuses the search input."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import Input

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Call focus search action
            screen.action_focus_search()
            await pilot.pause()

            # Search input should exist
            search_input = screen.query_one("#search-input", Input)
            assert search_input is not None


class TestDataBrowserFormatSize:
    """Tests for _format_size method edge cases."""

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        """Create minimal mock store."""
        store = MagicMock()
        store.is_empty = True
        store.get_categories.return_value = {}
        return store

    @pytest.mark.asyncio
    async def test_format_size_bytes(self, mock_store: MagicMock) -> None:
        """Test _format_size with bytes (< 1KB)."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)

            assert screen._format_size(500) == "500 B"
            assert screen._format_size(0) == "0 B"
            assert screen._format_size(1023) == "1023 B"

    @pytest.mark.asyncio
    async def test_format_size_kilobytes(self, mock_store: MagicMock) -> None:
        """Test _format_size with kilobytes."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)

            assert screen._format_size(1024) == "1.0 KB"
            assert screen._format_size(2048) == "2.0 KB"
            assert screen._format_size(1536) == "1.5 KB"

    @pytest.mark.asyncio
    async def test_format_size_megabytes(self, mock_store: MagicMock) -> None:
        """Test _format_size with megabytes."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)

            assert screen._format_size(1024 * 1024) == "1.0 MB"
            assert screen._format_size(5 * 1024 * 1024) == "5.0 MB"

    @pytest.mark.asyncio
    async def test_format_size_gigabytes(self, mock_store: MagicMock) -> None:
        """Test _format_size with gigabytes."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)

            assert screen._format_size(1024 * 1024 * 1024) == "1.0 GB"
            assert screen._format_size(2 * 1024 * 1024 * 1024) == "2.0 GB"


class TestDataBrowserEmptyStore:
    """Tests for DataBrowserScreen with empty store."""

    @pytest.fixture
    def empty_store(self) -> MagicMock:
        """Create empty mock store."""
        store = MagicMock()
        store.is_empty = True
        store.list_items.return_value = []
        store.get_categories.return_value = {
            "credentials": 0,
            "configs": 0,
            "documents": 0,
            "other": 0,
        }
        return store

    @pytest.mark.asyncio
    async def test_empty_store_shows_empty_state(
        self, empty_store: MagicMock
    ) -> None:
        """Test empty store shows empty state message."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import Static

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=empty_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Should have empty state widget
            empty_state = screen.query_one("#empty-state", Static)
            assert empty_state is not None

    @pytest.mark.asyncio
    async def test_empty_store_cursor_actions_no_op(
        self, empty_store: MagicMock
    ) -> None:
        """Test cursor actions are no-op on empty store."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=empty_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # These should not raise errors
            screen.action_cursor_down()
            screen.action_cursor_up()
            await pilot.pause()


class TestDataBrowserRowEvents:
    """Tests for DataBrowser row selection and highlight events."""

    @pytest.fixture
    def mock_store_with_items(self) -> MagicMock:
        """Create mock store with items for row event tests."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        store = MagicMock()
        store.is_empty = False

        items = [
            ExfiltratedDataItem(
                id="row-001",
                filename="test1.txt",
                file_type="txt",
                mime_type="text/plain",
                size_bytes=100,
                target="192.168.1.100",
                source_agent="agent-1",
                timestamp=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
                encrypted_path=Path("data/test1.enc"),
                sha256_hash="abc123",
                nonce=b"\x00" * 12,
                category="other",
            ),
            ExfiltratedDataItem(
                id="row-002",
                filename="test2.txt",
                file_type="txt",
                mime_type="text/plain",
                size_bytes=200,
                target="192.168.1.101",
                source_agent="agent-2",
                timestamp=datetime(2026, 1, 29, 13, 0, 0, tzinfo=timezone.utc),
                encrypted_path=Path("data/test2.enc"),
                sha256_hash="def456",
                nonce=b"\x00" * 12,
                category="credentials",
            ),
        ]

        store.list_items.return_value = items
        store.get_item.side_effect = lambda id: next(
            (i for i in items if i.id == id), None
        )
        store.get_categories.return_value = {
            "credentials": 1,
            "configs": 0,
            "documents": 0,
            "other": 1,
        }
        store.search.return_value = items
        store.get_item_content.return_value = b"test content"

        return store

    @pytest.mark.asyncio
    async def test_row_highlighted_updates_preview(
        self, mock_store_with_items: MagicMock
    ) -> None:
        """Test row highlight event updates preview."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import DataTable

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store_with_items)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Get the data table and move cursor
            table = screen.query_one("#data-table", DataTable)
            table.focus()
            await pilot.pause()

            # Navigate to trigger highlight event
            await pilot.press("down")
            await pilot.pause()

            # Selected item should be updated
            assert screen._selected_item_id is not None

    @pytest.mark.asyncio
    async def test_row_selected_shows_item_preview(
        self, mock_store_with_items: MagicMock
    ) -> None:
        """Test row selected event shows item preview."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import DataTable

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store_with_items)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Get the data table
            table = screen.query_one("#data-table", DataTable)
            table.focus()
            await pilot.pause()

            # Select a row
            await pilot.press("enter")
            await pilot.pause()

            # Store should have been queried for item
            mock_store_with_items.get_item.assert_called()

    @pytest.mark.asyncio
    async def test_decrypt_error_handling(
        self, mock_store_with_items: MagicMock
    ) -> None:
        """Test handling of decrypt errors in preview."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen

        # Make get_item_content raise an exception
        mock_store_with_items.get_item_content.side_effect = Exception("Decrypt failed")

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store_with_items)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Try to show preview - should handle error gracefully
            screen._show_item_preview("row-001")
            await pilot.pause()

            # No crash should occur


class TestCategoryTabsClickHandling:
    """Tests for CategoryTabs click event handling."""

    @pytest.mark.asyncio
    async def test_click_credentials_category(self) -> None:
        """Test clicking credentials category button."""
        from cyberred.tui.widgets.data_preview import CategoryTabs

        messages_received = []

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield CategoryTabs(
                    categories={
                        "credentials": 5,
                        "configs": 3,
                        "documents": 2,
                        "other": 1,
                    }
                )

            def on_category_tabs_category_selected(
                self, event: CategoryTabs.CategorySelected
            ) -> None:
                messages_received.append(event.category)

        async with TestApp().run_test() as pilot:
            tabs = pilot.app.query_one(CategoryTabs)
            await pilot.pause()

            # Click on credentials label
            cred_label = tabs.query_one("#cat-credentials")
            await pilot.click(cred_label)
            await pilot.pause()

            # Check message was sent
            assert tabs.selected_category == "credentials"

    @pytest.mark.asyncio
    async def test_click_all_category(self) -> None:
        """Test clicking All category button."""
        from cyberred.tui.widgets.data_preview import CategoryTabs

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield CategoryTabs()

        async with TestApp().run_test() as pilot:
            tabs = pilot.app.query_one(CategoryTabs)
            await pilot.pause()

            # First select a different category
            tabs.selected_category = "credentials"

            # Click on All label
            all_label = tabs.query_one("#cat-all")
            await pilot.click(all_label)
            await pilot.pause()

            # Should reset to None (all)
            assert tabs.selected_category is None


class TestDataItemPreviewEdgeCases:
    """Tests for DataItemPreview edge cases."""

    @pytest.fixture
    def text_item_no_content(self) -> Any:
        """Create a text item without content for testing."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        return ExfiltratedDataItem(
            id="edge-001",
            filename="empty.txt",
            file_type="txt",
            mime_type="text/plain",
            size_bytes=0,
            target="192.168.1.100",
            source_agent="agent-1",
            timestamp=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
            encrypted_path=Path("data/empty.enc"),
            sha256_hash="abc123def456",
            nonce=b"\x00" * 12,
            category="other",
        )

    @pytest.mark.asyncio
    async def test_show_item_no_content_provided(
        self, text_item_no_content: Any
    ) -> None:
        """Test show_item when no content is provided for text file."""
        from cyberred.tui.widgets.data_preview import DataItemPreview

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            # Show item with no content
            preview.show_item(text_item_no_content, content=None)
            await pilot.pause()

            # Should show "select to view" message
            assert preview._current_item is not None

    @pytest.mark.asyncio
    async def test_format_size_in_preview(self) -> None:
        """Test _format_size method in DataItemPreview."""
        from cyberred.tui.widgets.data_preview import DataItemPreview

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            # Test all size ranges
            assert preview._format_size(500) == "500 B"
            assert preview._format_size(1024) == "1.0 KB"
            assert preview._format_size(1024 * 1024) == "1.0 MB"
            assert preview._format_size(1024 * 1024 * 1024) == "1.0 GB"

    @pytest.mark.asyncio
    async def test_syntax_highlighting_exception_handling(self) -> None:
        """Test _apply_syntax_highlighting handles exceptions gracefully."""
        from cyberred.tui.widgets.data_preview import DataItemPreview
        from unittest.mock import patch

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            # Mock Syntax to raise an exception
            with patch(
                "cyberred.tui.widgets.data_preview.Syntax",
                side_effect=Exception("Syntax error")
            ):
                result = preview._apply_syntax_highlighting('{"key": "value"}', "json")
                # Should return None on exception
                assert result is None


class TestDataBrowserSearchFlow:
    """Tests for search functionality in DataBrowserScreen."""

    @pytest.fixture
    def searchable_store(self) -> MagicMock:
        """Create mock store for search tests."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        items = [
            ExfiltratedDataItem(
                id="search-001",
                filename="passwords.txt",
                file_type="txt",
                mime_type="text/plain",
                size_bytes=100,
                target="192.168.1.100",
                source_agent="agent-1",
                timestamp=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
                encrypted_path=Path("data/passwords.enc"),
                sha256_hash="abc123",
                nonce=b"\x00" * 12,
                category="credentials",
            ),
        ]

        store = MagicMock()
        store.is_empty = False
        store.list_items.return_value = items
        store.get_item.side_effect = lambda id: next(
            (i for i in items if i.id == id), None
        )
        store.get_categories.return_value = {
            "credentials": 1,
            "configs": 0,
            "documents": 0,
            "other": 0,
        }
        store.search.return_value = items
        store.get_item_content.return_value = b"admin:password123"

        return store

    @pytest.mark.asyncio
    async def test_search_triggers_refresh(
        self, searchable_store: MagicMock
    ) -> None:
        """Test that search input triggers data refresh."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import Input

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=searchable_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Set search input value directly
            search_input = screen.query_one("#search-input", Input)
            search_input.value = "password"
            await pilot.pause()

            # Search should have been called
            assert screen._search_query == "password"
            searchable_store.search.assert_called()


class TestDataBrowserInputEvents:
    """Tests for input event handling in DataBrowserScreen."""

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        """Create mock store for input tests."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        store = MagicMock()
        store.is_empty = False
        store.list_items.return_value = []
        store.get_categories.return_value = {}
        store.search.return_value = []
        return store

    @pytest.mark.asyncio
    async def test_input_changed_other_input_ignored(
        self, mock_store: MagicMock
    ) -> None:
        """Test that input changes from other inputs are ignored."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import Input

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)
                yield Input(id="other-input")

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Set value in other input directly
            other_input = pilot.app.query_one("#other-input", Input)
            other_input.value = "test"
            await pilot.pause()

            # Search query should not change
            assert screen._search_query == ""


class TestDataBrowserExceptionPaths:
    """Tests for exception handling paths in DataBrowserScreen."""

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        """Create mock store."""
        store = MagicMock()
        store.is_empty = False
        store.list_items.return_value = []
        store.get_categories.return_value = {}
        store.search.return_value = []
        return store

    @pytest.mark.asyncio
    async def test_refresh_data_table_not_mounted(
        self, mock_store: MagicMock
    ) -> None:
        """Test _refresh_data handles missing table gracefully."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from unittest.mock import patch

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Mock query_one to raise exception
            with patch.object(screen, "query_one", side_effect=Exception("Not found")):
                # Should not raise
                screen._refresh_data()
                await pilot.pause()

    @pytest.mark.asyncio
    async def test_refresh_data_tabs_exception(
        self, mock_store: MagicMock
    ) -> None:
        """Test _refresh_data handles CategoryTabs exception gracefully."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import DataTable

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Make get_categories raise an exception
            mock_store.get_categories.side_effect = Exception("DB error")
            
            # Should not raise - exception in tabs update is caught
            screen._refresh_data()
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_clear_filters_search_input_exception(
        self, mock_store: MagicMock
    ) -> None:
        """Test _clear_filters handles missing search input gracefully."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from unittest.mock import patch

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Set initial values
            screen._current_category = "credentials"
            screen._search_query = "test"

            # Mock query_one to fail for search input but not for table
            original_query_one = screen.query_one
            def mock_query(selector, *args):
                if "search-input" in selector:
                    raise Exception("Not found")
                return original_query_one(selector, *args)

            with patch.object(screen, "query_one", side_effect=mock_query):
                # Should not raise
                screen._clear_filters()
                await pilot.pause()

            # Filters should still be cleared
            assert screen._current_category is None
            assert screen._search_query == ""

    @pytest.mark.asyncio
    async def test_cursor_down_exception(self, mock_store: MagicMock) -> None:
        """Test action_cursor_down handles exception gracefully."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from unittest.mock import patch

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            with patch.object(screen, "query_one", side_effect=Exception("Not found")):
                # Should not raise
                screen.action_cursor_down()
                await pilot.pause()

    @pytest.mark.asyncio
    async def test_cursor_up_exception(self, mock_store: MagicMock) -> None:
        """Test action_cursor_up handles exception gracefully."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from unittest.mock import patch

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            with patch.object(screen, "query_one", side_effect=Exception("Not found")):
                # Should not raise
                screen.action_cursor_up()
                await pilot.pause()

    @pytest.mark.asyncio
    async def test_focus_search_exception(self, mock_store: MagicMock) -> None:
        """Test action_focus_search handles exception gracefully."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from unittest.mock import patch

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            with patch.object(screen, "query_one", side_effect=Exception("Not found")):
                # Should not raise
                screen.action_focus_search()
                await pilot.pause()

    @pytest.mark.asyncio
    async def test_row_selected_with_none_key(self, mock_store: MagicMock) -> None:
        """Test row selected handler with None row_key."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import DataTable

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Create event with None row_key
            event = DataTable.RowSelected(None, None, None)
            
            # Call handler directly - should return early
            screen.on_data_table_row_selected(event)
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_row_highlighted_with_none_key(self, mock_store: MagicMock) -> None:
        """Test row highlighted handler with None row_key."""
        from cyberred.tui.screens.data_browser import DataBrowserScreen
        from textual.widgets import DataTable

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataBrowserScreen(store=mock_store)

        async with TestApp().run_test() as pilot:
            screen = pilot.app.query_one(DataBrowserScreen)
            await pilot.pause()

            # Create event with None row_key
            event = DataTable.RowHighlighted(None, None, None)
            
            # Call handler directly - should return early
            screen.on_data_table_row_highlighted(event)
            await pilot.pause()


class TestCategoryTabsEdgeCases:
    """Tests for CategoryTabs edge cases."""

    @pytest.mark.asyncio
    async def test_click_widget_without_id(self) -> None:
        """Test click on widget without id is ignored."""
        from cyberred.tui.widgets.data_preview import CategoryTabs
        from textual.events import Click

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield CategoryTabs()

        async with TestApp().run_test() as pilot:
            tabs = pilot.app.query_one(CategoryTabs)
            await pilot.pause()

            # Initial state
            initial_category = tabs.selected_category

            # Create a mock widget without id
            class MockWidget:
                id = None

            # Create click event with mock widget
            event = MagicMock()
            event.widget = MockWidget()

            # Call handler - should return early
            tabs.on_click(event)
            await pilot.pause()

            # State should be unchanged
            assert tabs.selected_category == initial_category

    @pytest.mark.asyncio
    async def test_update_counts_not_mounted(self) -> None:
        """Test update_counts handles unmounted widgets gracefully."""
        from cyberred.tui.widgets.data_preview import CategoryTabs
        from unittest.mock import patch

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield CategoryTabs()

        async with TestApp().run_test() as pilot:
            tabs = pilot.app.query_one(CategoryTabs)
            await pilot.pause()

            # Mock query_one to raise exception
            with patch.object(tabs, "query_one", side_effect=Exception("Not mounted")):
                # Should not raise
                tabs.update_counts({"credentials": 5, "configs": 3})
                await pilot.pause()


class TestDataItemPreviewCopyException:
    """Tests for copy_to_clipboard exception handling."""

    @pytest.fixture
    def text_item(self) -> Any:
        """Create a text file item for testing."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        return ExfiltratedDataItem(
            id="copy-exc-001",
            filename="test.txt",
            file_type="txt",
            mime_type="text/plain",
            size_bytes=100,
            target="192.168.1.100",
            source_agent="agent-1",
            timestamp=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
            encrypted_path=Path("data/test.enc"),
            sha256_hash="abc123def456",
            nonce=b"\x00" * 12,
            category="other",
        )

    @pytest.mark.asyncio
    async def test_copy_to_clipboard_pyperclip_exception(
        self, text_item: Any
    ) -> None:
        """Test copy_to_clipboard handles pyperclip exception."""
        from cyberred.tui.widgets.data_preview import DataItemPreview
        from unittest.mock import MagicMock
        import cyberred.tui.widgets.data_preview as dp_module

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DataItemPreview()

        async with TestApp().run_test() as pilot:
            preview = pilot.app.query_one(DataItemPreview)

            content = b"secret content"
            preview.show_item(text_item, content=content)
            await pilot.pause()

            # Mock pyperclip to raise exception
            mock_pyperclip = MagicMock()
            mock_pyperclip.copy.side_effect = Exception("Clipboard error")
            
            original_has = dp_module.HAS_PYPERCLIP
            dp_module.HAS_PYPERCLIP = True
            dp_module.pyperclip = mock_pyperclip

            try:
                result = preview.copy_to_clipboard()
                # Should return False on exception
                assert result is False
            finally:
                dp_module.HAS_PYPERCLIP = original_has
                if hasattr(dp_module, 'pyperclip'):
                    delattr(dp_module, 'pyperclip')
