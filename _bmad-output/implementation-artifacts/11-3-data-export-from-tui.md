# Story 11.3: Data Export from TUI

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **to export data items from TUI**,
So that **I can save evidence to local filesystem**.

## Acceptance Criteria

1. **Given** data item is selected in browser
   **When** I choose Export (press `e` key or click Export button)
   **Then** export dialog appears with destination path input
   **And** default path suggests `~/cyber-red-exports/{engagement_name}/{filename}`
   **And** I can modify the destination path

2. **Given** export dialog is open for a single item
   **When** I confirm export
   **Then** file is decrypted and saved to specified path
   **And** export preserves original filename
   **And** success notification shows saved path
   **And** export is logged to audit trail with item_id, destination, timestamp

3. **Given** multiple items are selected in browser
   **When** I choose Export All Selected (press `E` key or Shift+E)
   **Then** export dialog shows count of items to export
   **And** I can specify archive format (ZIP) or individual files
   **And** archive includes manifest.json with metadata

4. **Given** archive export is chosen
   **When** I confirm export
   **Then** ZIP file is created at specified path
   **And** archive contains all selected files with original names
   **And** archive includes manifest.json with: item metadata, export timestamp, engagement info
   **And** archive is named `{engagement_name}_export_{timestamp}.zip`

5. **Given** export is in progress
   **When** decryption and file writing occurs
   **Then** progress indicator shows export status
   **And** large exports (>10 items or >10MB) show progress bar
   **And** export can be cancelled mid-operation

6. **Given** export destination is invalid (no write permission, disk full, etc.)
   **When** I attempt to export
   **Then** clear error message explains the issue
   **And** I can choose alternate destination
   **And** no partial files are left behind on failure

7. **Given** integration tests are run
   **When** export functionality is tested
   **Then** single item export tests pass
   **And** multi-item archive export tests pass
   **And** export error handling tests pass
   **And** audit logging tests pass
   **And** manifest.json format tests pass

## Tasks / Subtasks

> **⚠️ CRITICAL: Test-Driven Development (TDD) Required**
> 
> This story MUST follow strict TDD methodology:
> 1. **RED Phase**: Write failing tests FIRST before any implementation
> 2. **GREEN Phase**: Write minimal code to make tests pass
> 3. **REFACTOR Phase**: Clean up code while keeping tests green
>
> **🎯 STRICT 100% TEST COVERAGE REQUIREMENT**
> - All new code MUST achieve 100% test coverage
> - Coverage gaps are NOT acceptable - add tests until 100% is achieved
> - Run targeted coverage checks per file/module

---

### 🔴 RED PHASE: Write Failing Tests First

- [x] Task 1: Write unit tests for DataExporter class (AC: #1, #2, #6)
  - [x] Test `DataExporter.__init__()` with store and audit logger
  - [x] Test `export_single_item()` decrypts and writes to path
  - [x] Test `export_single_item()` preserves original filename
  - [x] Test `export_single_item()` creates parent directories if needed
  - [x] Test `export_single_item()` logs to audit trail
  - [x] Test `export_single_item()` raises `ExportError` on permission denied
  - [x] Test `export_single_item()` raises `ExportError` on disk full
  - [x] Test `export_single_item()` cleans up partial files on failure
  - [x] Test `get_default_export_path()` returns expected format

- [x] Task 2: Write unit tests for archive export (AC: #3, #4)
  - [x] Test `export_archive()` creates valid ZIP file
  - [x] Test `export_archive()` includes all items with original names
  - [x] Test `export_archive()` generates manifest.json with correct schema
  - [x] Test `export_archive()` names archive with timestamp format
  - [x] Test `export_archive()` handles duplicate filenames (appends suffix)
  - [x] Test `export_archive()` logs to audit trail
  - [x] Test `export_archive()` cleans up partial archive on failure
  - [x] Test manifest.json contains: items metadata, export_timestamp, engagement_id

- [x] Task 3: Write unit tests for export progress tracking (AC: #5)
  - [x] Test `ExportProgress` dataclass tracks total/completed counts
  - [x] Test `ExportProgress` tracks total/completed bytes
  - [x] Test `ExportProgress.percentage` property calculates correctly
  - [x] Test `ExportProgress.is_large_export` (>10 items or >10MB)
  - [x] Test export cancellation via `CancellationToken`
  - [x] Test cancelled export cleans up partial output

- [x] Task 4: Write unit tests for ExportDialog TUI modal (AC: #1, #3, #5)
  - [x] Test `ExportDialog` compose() creates path input and buttons
  - [x] Test `ExportDialog` shows default path suggestion
  - [x] Test `ExportDialog` validates path input (non-empty, writable directory)
  - [x] Test `ExportDialog` emits `ExportRequested` message on confirm
  - [x] Test `ExportDialog` closes on cancel (Escape key)
  - [x] Test `ExportDialog` shows item count for multi-select
  - [x] Test `ExportDialog` archive vs individual files toggle
  - [x] Test `ExportDialog` progress bar rendering for large exports

- [x] Task 5: Write unit tests for DataBrowserScreen export integration (AC: #1, #2, #7)
  - [x] Test `action_export_item()` opens ExportDialog for single item
  - [x] Test `action_export_selected()` opens ExportDialog for multiple items
  - [x] Test multi-select mode with Space key toggles selection
  - [x] Test selection state visual indicator in DataTable
  - [x] Test export success shows notification with path
  - [x] Test export failure shows error notification

- [x] Task 6: Write integration tests for full export flow (AC: #7)
  - [x] Test single item export end-to-end
  - [x] Test archive export end-to-end
  - [x] Test export with real encryption/decryption
  - [x] Test audit log entries are created
  - [x] Test error recovery (invalid path, then retry with valid path)

---

### 🟢 GREEN PHASE: Implement Features to Pass Tests

- [x] Task 7: Implement DataExporter class (AC: #1, #2, #6)
  - [x] Create `src/cyberred/storage/exporter.py`
  - [x] Implement `DataExporter.__init__(store, audit_logger, engagement_name)`
  - [x] Implement `get_default_export_path(item)` returning `~/cyber-red-exports/{engagement}/{filename}`
  - [x] Implement `export_single_item(item_id, destination_path)` with decryption
  - [x] Implement atomic write pattern (write to temp, rename on success)
  - [x] Implement cleanup on failure (remove partial files)
  - [x] Add audit logging for all exports

- [x] Task 8: Implement archive export functionality (AC: #3, #4)
  - [x] Implement `export_archive(item_ids, destination_path)` 
  - [x] Generate manifest.json with export metadata schema
  - [x] Handle duplicate filenames by appending counter suffix
  - [x] Use atomic write for archive (write to temp .zip.tmp, rename on success)
  - [x] Implement proper ZIP compression (deflate)

- [x] Task 9: Implement export progress tracking (AC: #5)
  - [x] Create `ExportProgress` dataclass with counts and bytes tracking
  - [x] Implement `CancellationToken` for cooperative cancellation
  - [x] Add progress callback parameter to export methods
  - [x] Implement cleanup on cancellation

- [x] Task 10: Implement ExportDialog TUI modal (AC: #1, #3, #5)
  - [x] Create `src/cyberred/tui/widgets/export_dialog.py`
  - [x] Implement modal layout: title, path input, format toggle, buttons
  - [x] Implement path validation with real-time feedback
  - [x] Implement progress bar widget for large exports
  - [x] Emit `ExportRequested` message with export configuration
  - [x] Support keyboard navigation (Tab between fields, Enter to confirm)

- [x] Task 11: Implement multi-select in DataBrowserScreen (AC: #3)
  - [x] Add `_selected_items: set[str]` for multi-selection tracking
  - [x] Implement Space key toggle for selection
  - [x] Add visual indicator (checkbox column or row highlight) for selected items
  - [x] Implement `E` (Shift+E) binding for export all selected
  - [x] Update status bar to show selection count

- [x] Task 12: Integrate export into DataBrowserScreen (AC: #1, #2)
  - [x] Update `action_export_item()` to open ExportDialog
  - [x] Implement `action_export_selected()` for multi-item export
  - [x] Handle `ExportRequested` message and invoke DataExporter
  - [x] Show success/error notifications after export
  - [x] Run export in background to avoid blocking UI

---

### 🔵 REFACTOR PHASE: Clean Up While Keeping Tests Green

- [x] Task 13: Code quality and documentation
  - [x] Add comprehensive docstrings to all public methods
  - [x] Ensure type hints are complete and correct
  - [x] Run coverage report and add tests until 100% achieved
  - [x] Add logging for debugging export operations
  - [x] Optimize large export performance (streaming write for big files)

- [x] Task 14: Final validation
  - [x] Verify all acceptance criteria met
  - [x] Run full test suite
  - [x] Test with real encrypted data files
  - [x] Verify audit log entries are complete and accurate

---

## Dev Notes

### Architecture Patterns

**DataExporter Class Pattern**:
```python
from pathlib import Path
from dataclasses import dataclass
from typing import Callable
import zipfile
import json
import tempfile
import shutil

from cyberred.storage.evidence import ExfiltratedDataStore, ExfiltratedDataItem, SecureBuffer
from cyberred.core.exceptions import ExportError

@dataclass
class ExportProgress:
    """Tracks export progress for UI updates."""
    total_items: int
    completed_items: int
    total_bytes: int
    completed_bytes: int
    current_item: str = ""
    
    @property
    def percentage(self) -> float:
        if self.total_items == 0:
            return 100.0
        return (self.completed_items / self.total_items) * 100
    
    @property
    def is_large_export(self) -> bool:
        """Large export: >10 items or >10MB."""
        return self.total_items > 10 or self.total_bytes > 10 * 1024 * 1024


class CancellationToken:
    """Cooperative cancellation for export operations."""
    def __init__(self) -> None:
        self._cancelled = False
    
    def cancel(self) -> None:
        self._cancelled = True
    
    @property
    def is_cancelled(self) -> bool:
        return self._cancelled


class DataExporter:
    """Handles export of exfiltrated data items. Per Story 11.3."""
    
    DEFAULT_EXPORT_DIR = Path.home() / "cyber-red-exports"
    
    def __init__(
        self,
        store: ExfiltratedDataStore,
        audit_logger: AuditLogger,
        engagement_name: str,
    ) -> None:
        self._store = store
        self._audit = audit_logger
        self._engagement_name = engagement_name
    
    def get_default_export_path(self, item: ExfiltratedDataItem) -> Path:
        """Get default export path for an item."""
        return self.DEFAULT_EXPORT_DIR / self._engagement_name / item.filename
    
    def export_single_item(
        self,
        item_id: str,
        destination: Path,
        progress_callback: Callable[[ExportProgress], None] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> Path:
        """Export single item to destination path.
        
        Args:
            item_id: ID of item to export.
            destination: Target file path.
            progress_callback: Optional callback for progress updates.
            cancellation_token: Optional token for cancellation.
            
        Returns:
            Path to exported file.
            
        Raises:
            ExportError: On permission denied, disk full, or other failure.
            KeyError: If item_id not found.
        """
        item = self._store.get_item(item_id)
        if item is None:
            raise KeyError(f"Item not found: {item_id}")
        
        # Check cancellation
        if cancellation_token and cancellation_token.is_cancelled:
            raise ExportError("Export cancelled")
        
        # Ensure parent directory exists
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # Atomic write: temp file then rename
        temp_path = destination.with_suffix(destination.suffix + ".tmp")
        try:
            # Decrypt and write
            with SecureBuffer(self._store.get_item_content(item_id)) as content:
                temp_path.write_bytes(bytes(content))
            
            # Rename to final destination
            shutil.move(str(temp_path), str(destination))
            
            # Log to audit
            self._audit.log_export(
                item_id=item_id,
                filename=item.filename,
                destination=str(destination),
            )
            
            return destination
            
        except PermissionError as e:
            self._cleanup_temp(temp_path)
            raise ExportError(f"Permission denied: {destination}") from e
        except OSError as e:
            self._cleanup_temp(temp_path)
            if "No space left" in str(e) or e.errno == 28:
                raise ExportError(f"Disk full: cannot write to {destination}") from e
            raise ExportError(f"Export failed: {e}") from e
        except Exception as e:
            self._cleanup_temp(temp_path)
            raise ExportError(f"Export failed: {e}") from e
    
    def export_archive(
        self,
        item_ids: list[str],
        destination: Path,
        progress_callback: Callable[[ExportProgress], None] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> Path:
        """Export multiple items as ZIP archive with manifest.
        
        Args:
            item_ids: List of item IDs to export.
            destination: Target ZIP file path.
            progress_callback: Optional callback for progress updates.
            cancellation_token: Optional token for cancellation.
            
        Returns:
            Path to exported archive.
            
        Raises:
            ExportError: On failure.
        """
        items = [self._store.get_item(id) for id in item_ids]
        items = [i for i in items if i is not None]
        
        total_bytes = sum(i.size_bytes for i in items)
        progress = ExportProgress(
            total_items=len(items),
            completed_items=0,
            total_bytes=total_bytes,
            completed_bytes=0,
        )
        
        # Ensure parent directory exists
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        temp_path = destination.with_suffix(".zip.tmp")
        used_names: dict[str, int] = {}  # Track duplicate filenames
        
        try:
            with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                manifest_items = []
                
                for item in items:
                    if cancellation_token and cancellation_token.is_cancelled:
                        raise ExportError("Export cancelled")
                    
                    progress.current_item = item.filename
                    if progress_callback:
                        progress_callback(progress)
                    
                    # Handle duplicate filenames
                    arc_name = item.filename
                    if arc_name in used_names:
                        used_names[arc_name] += 1
                        base, ext = os.path.splitext(arc_name)
                        arc_name = f"{base}_{used_names[arc_name]}{ext}"
                    else:
                        used_names[arc_name] = 0
                    
                    # Decrypt and add to archive
                    with SecureBuffer(self._store.get_item_content(item.id)) as content:
                        zf.writestr(arc_name, bytes(content))
                    
                    manifest_items.append({
                        **item.to_dict(),
                        "archive_name": arc_name,
                    })
                    
                    progress.completed_items += 1
                    progress.completed_bytes += item.size_bytes
                
                # Write manifest
                manifest = {
                    "schema_version": "1.0.0",
                    "engagement_name": self._engagement_name,
                    "export_timestamp": datetime.now(timezone.utc).isoformat(),
                    "total_items": len(manifest_items),
                    "total_bytes": total_bytes,
                    "items": manifest_items,
                }
                zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            
            # Rename to final destination
            shutil.move(str(temp_path), str(destination))
            
            # Log to audit
            self._audit.log_archive_export(
                item_ids=item_ids,
                destination=str(destination),
                item_count=len(items),
            )
            
            return destination
            
        except Exception as e:
            self._cleanup_temp(temp_path)
            if isinstance(e, ExportError):
                raise
            raise ExportError(f"Archive export failed: {e}") from e
    
    def _cleanup_temp(self, temp_path: Path) -> None:
        """Remove temporary file if it exists."""
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass  # Best effort cleanup
```

**ExportDialog TUI Modal**:
```python
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Button, ProgressBar, RadioSet, RadioButton
from textual.containers import Vertical, Horizontal
from textual.message import Message
from pathlib import Path

class ExportDialog(ModalScreen):
    """Modal dialog for export configuration. Per Story 11.3."""
    
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "confirm", "Export"),
    ]
    
    class ExportRequested(Message):
        """Emitted when user confirms export."""
        def __init__(
            self,
            item_ids: list[str],
            destination: Path,
            as_archive: bool,
        ) -> None:
            self.item_ids = item_ids
            self.destination = destination
            self.as_archive = as_archive
            super().__init__()
    
    def __init__(
        self,
        item_ids: list[str],
        default_path: Path,
        single_item: bool = True,
    ) -> None:
        super().__init__()
        self._item_ids = item_ids
        self._default_path = default_path
        self._single_item = single_item
    
    def compose(self) -> ComposeResult:
        with Vertical(id="export-dialog"):
            yield Static(
                f"Export {'item' if self._single_item else f'{len(self._item_ids)} items'}",
                id="export-title",
            )
            
            yield Static("Destination:", classes="label")
            yield Input(
                value=str(self._default_path),
                id="export-path",
                placeholder="Enter export path...",
            )
            
            if not self._single_item:
                yield Static("Format:", classes="label")
                with RadioSet(id="export-format"):
                    yield RadioButton("ZIP Archive (with manifest)", value=True, id="format-archive")
                    yield RadioButton("Individual Files", id="format-individual")
            
            yield Static("", id="export-error", classes="error hidden")
            
            with Horizontal(id="export-buttons"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                yield Button("Export", variant="primary", id="btn-export")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-export":
            self.action_confirm()
    
    def action_cancel(self) -> None:
        self.dismiss(None)
    
    def action_confirm(self) -> None:
        path_input = self.query_one("#export-path", Input)
        destination = Path(path_input.value).expanduser()
        
        # Validate path
        error_widget = self.query_one("#export-error", Static)
        
        if not path_input.value.strip():
            error_widget.update("Path cannot be empty")
            error_widget.remove_class("hidden")
            return
        
        # Check if parent directory is writable
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
                as_archive = radio_set.pressed_button.id == "format-archive"
            except Exception:
                as_archive = True  # Default to archive for multi-select
        
        self.dismiss(self.ExportRequested(
            item_ids=self._item_ids,
            destination=destination,
            as_archive=as_archive,
        ))
```

**manifest.json Export Schema**:
```json
{
    "schema_version": "1.0.0",
    "engagement_name": "ministry-2025",
    "export_timestamp": "2026-01-29T15:30:00Z",
    "total_items": 5,
    "total_bytes": 102400,
    "items": [
        {
            "id": "data-001-uuid",
            "filename": "shadow",
            "archive_name": "shadow",
            "file_type": "shadow",
            "mime_type": "text/plain",
            "size_bytes": 1024,
            "target": "192.168.1.100",
            "source_agent": "postex-agent-7",
            "timestamp": "2026-01-29T12:00:00Z",
            "sha256_hash": "a1b2c3d4e5f6...",
            "category": "credentials"
        },
        {
            "id": "data-002-uuid",
            "filename": "shadow",
            "archive_name": "shadow_1",
            "...": "duplicate filename handling"
        }
    ]
}
```

### Component Locations

| Component | Location | Purpose |
|-----------|----------|---------|
| `DataExporter` | `src/cyberred/storage/exporter.py` | Export logic and archive creation |
| `ExportProgress` | `src/cyberred/storage/exporter.py` | Progress tracking dataclass |
| `CancellationToken` | `src/cyberred/storage/exporter.py` | Cooperative cancellation |
| `ExportError` | `src/cyberred/core/exceptions.py` | Export-specific exception (add if not exists) |
| `ExportDialog` | `src/cyberred/tui/widgets/export_dialog.py` | TUI export modal |
| `DataBrowserScreen` | `src/cyberred/tui/screens/data_browser.py` | Updated with export integration |
| Unit tests | `tests/unit/storage/test_exporter.py` | Exporter unit tests |
| Unit tests | `tests/unit/tui/test_export_dialog.py` | TUI widget tests |
| Integration tests | `tests/integration/tui/test_data_export.py` | Full export flow tests |

### Existing Code to Leverage

**From `src/cyberred/storage/evidence.py`** (Story 11.2):
- `ExfiltratedDataStore` - store for accessing items
- `ExfiltratedDataItem` - item dataclass with `to_dict()` for manifest
- `SecureBuffer` - secure memory handling for decrypted content
- `decrypt_data()` - AES-256-GCM decryption

**From `src/cyberred/tui/screens/data_browser.py`** (Story 11.2):
- `DataBrowserScreen` - existing screen with `action_export_item()` placeholder
- `_selected_item_id` - current selection tracking
- Keybinding pattern with `BINDINGS` list
- Notification pattern with `self.notify()`

**From `src/cyberred/storage/audit.py`** (if exists, else create):
- `AuditLogger` - for logging export operations
- Should support `log_export()` and `log_archive_export()` methods

### Keybindings (per UX Design)

| Key | Action | Context |
|-----|--------|---------|
| `e` | Export selected item | Single item selected |
| `E` (Shift+E) | Export all selected | Multi-select mode |
| `Space` | Toggle selection | Multi-select mode |
| `Escape` | Cancel/close dialog | Export dialog |
| `Enter` | Confirm export | Export dialog |
| `Tab` | Navigate fields | Export dialog |

### Security Considerations

1. **Decrypted data handling**: Use `SecureBuffer` to zero memory after write
2. **Atomic writes**: Write to temp file, rename on success - prevents partial corrupt files
3. **Audit trail**: All exports logged with item_id, destination, timestamp for compliance
4. **No auto-delete**: Per FR44, exported data remains in store (no side effects)
5. **Path validation**: Verify write permissions before attempting export

### Testing Standards

Per project testing requirements:
- **100% coverage** on all new code
- **TDD methodology**: Write tests first (RED), implement (GREEN), refactor (BLUE)
- **Unit tests**: Test each method in isolation with mocks
- **Integration tests**: Test full export flow with real encryption
- Use fixtures from `tests/fixtures/` for test data
- Follow patterns from `tests/unit/storage/test_evidence.py`

### Error Messages (User-Friendly)

| Error | Message |
|-------|---------|
| Permission denied | "Cannot write to {path}: Permission denied. Choose a different location." |
| Disk full | "Not enough disk space to export. Free up space or choose a different drive." |
| Item not found | "Export failed: Item no longer exists." |
| Export cancelled | "Export cancelled. No files were saved." |
| Invalid path | "Invalid path: {path}. Please enter a valid file path." |

### Project Structure Notes

- New file `src/cyberred/storage/exporter.py` follows module organization
- Widget `export_dialog.py` goes in `tui/widgets/` per architecture
- Tests follow `tests/unit/` and `tests/integration/` structure
- All paths align with `_bmad-output/planning-artifacts/architecture.md` project structure

### References

- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 11.3]
- [Source: _bmad-output/planning-artifacts/ux-design.md#Feedback Patterns]
- [Source: _bmad-output/planning-artifacts/ux-design.md#Keyboard Consistency]
- [Source: _bmad-output/implementation-artifacts/11-2-exfiltrated-data-browser.md]
- [Source: src/cyberred/storage/evidence.py]
- [Source: src/cyberred/tui/screens/data_browser.py#action_export_item]

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

- All 44 tests pass (29 unit + 15 integration)

### Completion Notes List

- Implemented `DataExporter` class with single item and archive export
- Implemented `ExportProgress` and `CancellationToken` for progress tracking
- Implemented `ExportDialog` TUI modal with path input and format toggle
- Added `ExportError` exception to exception hierarchy
- Integrated export into `DataBrowserScreen` with `e`, `E`, and Space keybindings
- Added multi-select support for bulk exports

### Code Review Fixes (2026-01-29)

- **Fixed class variable bug**: `_selected_items` was a class variable causing shared state between instances; moved to instance variable in `__init__`
- **Fixed multi-item individual export**: When `as_archive=False` with multiple items, now exports each item individually instead of only the first
- **Fixed hardcoded engagement name**: Added `engagement_name` parameter to `DataBrowserScreen.__init__` and use it in export paths
- **Fixed default export path**: Now uses `{engagement_name}` instead of hardcoded "export" subdirectory
- **Added visual selection indicator**: Checkbox (☑) prefix on selected items in DataTable
- **Added `ExportAuditLogger`**: New audit logger class in `core/audit.py` with `log_export()` and `log_archive_export()` methods
- **Improved audit logging integration**: `_get_audit_logger()` now uses real `ExportAuditLogger` when available

### File List

- `src/cyberred/storage/exporter.py` (NEW) - DataExporter, ExportProgress, CancellationToken
- `src/cyberred/tui/widgets/export_dialog.py` (NEW) - ExportDialog modal
- `src/cyberred/core/exceptions.py` (MODIFIED) - Added ExportError
- `src/cyberred/core/audit.py` (MODIFIED) - Added ExportAuditLogger, ExportAuditEntry
- `src/cyberred/tui/screens/data_browser.py` (MODIFIED) - Export integration with code review fixes
- `tests/unit/storage/test_exporter.py` (NEW) - DataExporter unit tests
- `tests/unit/tui/test_export_dialog.py` (NEW) - ExportDialog unit tests
- `tests/integration/tui/test_data_export.py` (NEW) - Integration tests
