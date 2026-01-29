"""Data Preview Widgets for Exfiltrated Data Browser.

Story 11.2: Exfiltrated Data Browser

Provides widgets for displaying exfiltrated data items:
    - DataItemPreview: Shows text preview or metadata for selected item
    - CategoryTabs: Category navigation with item counts

Per FR42: Access all exfiltrated data via TUI menu
Per FR43: Data encrypted at rest (decryption on-the-fly)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static, Label
from rich.syntax import Syntax
from rich.text import Text

if TYPE_CHECKING:
    from cyberred.storage.evidence import ExfiltratedDataItem

logger = logging.getLogger(__name__)

# File extension to syntax lexer mapping
SYNTAX_LEXERS: dict[str, str] = {
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "xml": "xml",
    "py": "python",
    "python": "python",
    "sh": "bash",
    "bash": "bash",
    "js": "javascript",
    "ts": "typescript",
    "html": "html",
    "css": "css",
    "sql": "sql",
    "ini": "ini",
    "conf": "ini",
    "cfg": "ini",
    "toml": "toml",
    "env": "bash",
    "md": "markdown",
}

# Maximum preview size (10KB per spec)
MAX_PREVIEW_SIZE = 10 * 1024


class CategoryTabs(Static):
    """Category navigation tabs with item counts.

    Displays buttons for: All, Credentials, Configs, Documents, Other
    Each button shows the count of items in that category.
    """

    DEFAULT_CSS = """
    CategoryTabs {
        width: 100%;
        height: auto;
        padding: 1;
    }

    CategoryTabs .category-btn {
        margin: 0 0 1 0;
        width: 100%;
    }

    CategoryTabs .category-btn.selected {
        background: $accent;
    }
    """

    class CategorySelected(Message):
        """Message sent when a category is selected."""

        def __init__(self, category: str | None) -> None:
            self.category = category
            super().__init__()

    def __init__(
        self,
        categories: dict[str, int] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize CategoryTabs.

        Args:
            categories: Initial category counts.
        """
        super().__init__(**kwargs)
        self.categories = categories or {
            "credentials": 0,
            "configs": 0,
            "documents": 0,
            "other": 0,
        }
        self.selected_category: str | None = None

    def compose(self) -> ComposeResult:
        """Compose the category buttons."""
        total = sum(self.categories.values())
        yield Label(f"[bold]All[/bold] ({total})", id="cat-all", classes="category-btn selected")
        yield Label(
            f"🔑 Credentials ({self.categories.get('credentials', 0)})",
            id="cat-credentials",
            classes="category-btn",
        )
        yield Label(
            f"⚙️ Configs ({self.categories.get('configs', 0)})",
            id="cat-configs",
            classes="category-btn",
        )
        yield Label(
            f"📄 Documents ({self.categories.get('documents', 0)})",
            id="cat-documents",
            classes="category-btn",
        )
        yield Label(
            f"📦 Other ({self.categories.get('other', 0)})",
            id="cat-other",
            classes="category-btn",
        )

    def on_click(self, event: Any) -> None:
        """Handle click on category labels."""
        # Find which label was clicked
        target = event.widget
        if not hasattr(target, "id") or not target.id:
            return

        target_id = target.id

        # Update selection
        for label in self.query(".category-btn"):
            label.remove_class("selected")

        target.add_class("selected")

        # Determine category
        if target_id == "cat-all":
            self.selected_category = None
        elif target_id.startswith("cat-"):
            self.selected_category = target_id.replace("cat-", "")

        self.post_message(self.CategorySelected(self.selected_category))

    def update_counts(self, categories: dict[str, int]) -> None:
        """Update category counts.

        Args:
            categories: New category counts.
        """
        self.categories = categories
        # Update labels
        total = sum(categories.values())
        try:
            self.query_one("#cat-all", Label).update(f"[bold]All[/bold] ({total})")
            self.query_one("#cat-credentials", Label).update(
                f"🔑 Credentials ({categories.get('credentials', 0)})"
            )
            self.query_one("#cat-configs", Label).update(
                f"⚙️ Configs ({categories.get('configs', 0)})"
            )
            self.query_one("#cat-documents", Label).update(
                f"📄 Documents ({categories.get('documents', 0)})"
            )
            self.query_one("#cat-other", Label).update(
                f"📦 Other ({categories.get('other', 0)})"
            )
        except Exception:
            pass  # Widget not mounted yet


class DataItemPreview(Static):
    """Preview widget for exfiltrated data items.

    Shows:
    - Text preview for text files under 10KB
    - Metadata only for binary files or large text files
    - Empty state when no item selected
    """

    DEFAULT_CSS = """
    DataItemPreview {
        width: 100%;
        height: 100%;
        padding: 1;
        border: solid $primary;
    }

    DataItemPreview .preview-header {
        text-style: bold;
        margin-bottom: 1;
    }

    DataItemPreview .preview-metadata {
        margin-bottom: 1;
    }

    DataItemPreview .preview-content {
        height: auto;
        max-height: 100%;
        overflow-y: auto;
    }

    DataItemPreview .empty-state {
        text-align: center;
        margin-top: 5;
        color: $text-muted;
    }

    DataItemPreview .truncated-indicator {
        color: $warning;
        text-style: italic;
    }
    """

    _current_item: ExfiltratedDataItem | None = None
    _content: bytes | None = None
    _is_truncated: bool = False

    def __init__(self, **kwargs: Any) -> None:
        """Initialize DataItemPreview."""
        super().__init__(**kwargs)
        self._current_item = None
        self._content = None
        self._is_truncated = False

    def compose(self) -> ComposeResult:
        """Compose the preview widget."""
        with Vertical(id="preview-container"):
            yield Label("", id="preview-header", classes="preview-header")
            yield Static("", id="preview-metadata", classes="preview-metadata")
            yield Static("", id="preview-content", classes="preview-content")

    def show_item(
        self,
        item: ExfiltratedDataItem,
        content: bytes | None = None,
    ) -> None:
        """Show preview for an item.

        Args:
            item: The data item to preview.
            content: Optional decrypted content for text preview.
        """
        self._current_item = item
        self._content = content
        self._is_truncated = False

        # Update header
        header = self.query_one("#preview-header", Label)
        header.update(f"📄 {item.filename}")

        # Build metadata
        metadata_lines = [
            f"[bold]Category:[/bold] {item.category}",
            f"[bold]Target:[/bold] {item.target}",
            f"[bold]Agent:[/bold] {item.source_agent}",
            f"[bold]Size:[/bold] {self._format_size(item.size_bytes)}",
            f"[bold]Type:[/bold] {item.mime_type}",
            f"[bold]SHA-256:[/bold] {item.sha256_hash[:16]}...",
            f"[bold]Timestamp:[/bold] {item.timestamp.isoformat()}",
        ]

        metadata = self.query_one("#preview-metadata", Static)
        metadata.update("\n".join(metadata_lines))

        # Update content preview
        content_widget = self.query_one("#preview-content", Static)

        if not item.is_text:
            # Binary file - metadata only
            content_widget.update(
                "[dim]Binary file - export to view[/dim]\n\n"
                "Press [bold]e[/bold] to export this file."
            )
        elif content is not None:
            # Text file with content
            if len(content) > MAX_PREVIEW_SIZE:
                # Truncate
                self._is_truncated = True
                preview_text = content[:MAX_PREVIEW_SIZE].decode(
                    "utf-8", errors="replace"
                )
                # Apply syntax highlighting if applicable
                highlighted = self._apply_syntax_highlighting(
                    preview_text, item.file_type
                )
                if highlighted is not None:
                    # Show highlighted content with truncation notice
                    content_widget.update(highlighted)
                else:
                    content_widget.update(
                        f"{preview_text}\n\n"
                        "[yellow][truncated - file exceeds 10KB preview limit][/yellow]"
                    )
            else:
                preview_text = content.decode("utf-8", errors="replace")
                # Apply syntax highlighting if applicable
                highlighted = self._apply_syntax_highlighting(
                    preview_text, item.file_type
                )
                if highlighted is not None:
                    content_widget.update(highlighted)
                else:
                    content_widget.update(preview_text)
        else:
            # No content provided
            content_widget.update(
                "[dim]Select to view content preview[/dim]"
            )

    def show_empty_state(self, title: str, message: str) -> None:
        """Show empty state message.

        Args:
            title: Title for empty state.
            message: Description message.
        """
        self._current_item = None
        self._content = None
        self._is_truncated = False

        header = self.query_one("#preview-header", Label)
        header.update(title)

        metadata = self.query_one("#preview-metadata", Static)
        metadata.update("")

        content = self.query_one("#preview-content", Static)
        content.update(f"[dim]{message}[/dim]")

    def _format_size(self, size_bytes: int) -> str:
        """Format size in human-readable form.

        Args:
            size_bytes: Size in bytes.

        Returns:
            Formatted string (e.g., "1.5 KB", "2.3 MB").
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    def _apply_syntax_highlighting(
        self, text: str, file_type: str
    ) -> Syntax | None:
        """Apply syntax highlighting based on file type.

        Args:
            text: Text content to highlight.
            file_type: File extension/type.

        Returns:
            Rich Syntax object if highlighting is available, None otherwise.
        """
        lexer = SYNTAX_LEXERS.get(file_type.lower())
        if lexer is None:
            return None
        try:
            return Syntax(
                text,
                lexer,
                theme="monokai",
                line_numbers=False,
                word_wrap=True,
            )
        except Exception as e:
            logger.debug(f"Failed to apply syntax highlighting: {e}")
            return None

    def copy_to_clipboard(self) -> bool:
        """Copy current content to clipboard.

        Returns:
            True if copy succeeded, False otherwise.
        """
        if self._content is None:
            return False
        if not HAS_PYPERCLIP:
            logger.warning("pyperclip not available for clipboard operations")
            return False
        try:
            text = self._content.decode("utf-8", errors="replace")
            pyperclip.copy(text)
            return True
        except Exception as e:
            logger.warning(f"Failed to copy to clipboard: {e}")
            return False

    @property
    def current_item(self) -> ExfiltratedDataItem | None:
        """Get the currently displayed item."""
        return self._current_item

    @property
    def is_truncated(self) -> bool:
        """Check if current preview is truncated."""
        return self._is_truncated
