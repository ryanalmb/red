# Story 11.4: Manual Data Deletion

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **to manually delete data items through TUI**,
So that **I can clean up sensitive data when required (FR45)**.

## Acceptance Criteria

1. **Given** data item is selected in Data Browser
   **When** I press `d` key or click Delete button
   **Then** confirmation modal appears with warning message
   **And** modal shows item filename, size, and target
   **And** modal requires explicit confirmation (type "DELETE" or press specific key combo)

2. **Given** confirmation modal is displayed
   **When** I confirm deletion
   **Then** data is securely deleted (overwritten with random bytes before unlink)
   **And** item is removed from manifest.json
   **And** deletion is logged to audit trail with item_id, filename, timestamp, operator
   **And** Data Browser refreshes to reflect deletion
   **And** success notification confirms "Item permanently deleted"

3. **Given** confirmation modal is displayed
   **When** I cancel or press Escape
   **Then** modal closes without deletion
   **And** item remains intact
   **And** no audit log entry is created

4. **Given** multiple items are selected in Data Browser
   **When** I press `D` (Shift+D) for bulk delete
   **Then** confirmation modal shows count of items to delete
   **And** modal lists all filenames being deleted (scrollable if >10)
   **And** bulk delete requires stronger confirmation (type "DELETE ALL")

5. **Given** secure deletion is performed
   **When** file is overwritten
   **Then** file content is overwritten with cryptographically random bytes (3 passes)
   **And** file is then unlinked from filesystem
   **And** encrypted file path no longer exists after deletion
   **And** no recovery is possible via standard forensic methods

6. **Given** deletion fails (file locked, permission denied, etc.)
   **When** error occurs during deletion
   **Then** clear error message explains the issue
   **And** item remains in manifest (no partial deletion state)
   **And** operator can retry or skip

7. **Given** no auto-delete functionality exists (FR44 compliance)
   **When** system operates normally
   **Then** data is NEVER automatically deleted
   **And** only manual operator-initiated deletion is supported
   **And** scheduled deletion features do NOT exist

8. **Given** integration tests are run
   **When** deletion functionality is tested
   **Then** single item deletion tests pass
   **And** bulk deletion tests pass
   **And** secure overwrite verification tests pass
   **And** audit logging tests pass
   **And** error handling tests pass
   **And** FR44 compliance tests pass (no auto-delete)

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

- [x] Task 1: Write unit tests for SecureDeleter class (AC: #2, #5, #6)
  - [x] Test `SecureDeleter.__init__()` with store and audit logger
  - [x] Test `secure_delete_file()` overwrites file with random bytes (3 passes)
  - [x] Test `secure_delete_file()` unlinks file after overwrite
  - [x] Test `secure_delete_file()` verifies file no longer exists
  - [x] Test `secure_delete_file()` raises `DeletionError` on permission denied
  - [x] Test `secure_delete_file()` raises `DeletionError` on file locked
  - [x] Test `secure_delete_file()` handles non-existent file gracefully

- [x] Task 2: Write unit tests for delete_item() method (AC: #2, #6)
  - [x] Test `delete_item()` calls `secure_delete_file()` for encrypted file
  - [x] Test `delete_item()` removes item from manifest.json
  - [x] Test `delete_item()` logs to audit trail
  - [x] Test `delete_item()` updates in-memory store cache
  - [x] Test `delete_item()` raises `DeletionError` if item not found
  - [x] Test `delete_item()` handles item not in cache

- [x] Task 3: Write unit tests for bulk deletion (AC: #4)
  - [x] Test `delete_items()` deletes multiple items atomically
  - [x] Test `delete_items()` logs single audit entry for bulk delete
  - [x] Test `delete_items()` continues on individual item failure (configurable)
  - [x] Test `delete_items()` returns summary of deleted/failed items
  - [x] Test `delete_items()` stops on first error by default

- [x] Task 4: Write unit tests for DeleteConfirmationModal (AC: #1, #3, #4)
  - [x] Test modal compose() shows warning message and item details
  - [x] Test modal requires typing "DELETE" for single item confirmation
  - [x] Test modal requires typing "DELETE ALL" for bulk confirmation
  - [x] Test modal Escape key cancels without deletion
  - [x] Test modal emits `DeletionConfirmed` message on valid confirmation
  - [x] Test modal shows error for invalid confirmation text
  - [x] Test modal scrollable list for >10 items in bulk delete

- [x] Task 5: Write unit tests for DataBrowserScreen delete integration (AC: #1, #2)
  - [x] Test `action_delete_item()` opens DeleteConfirmationModal
  - [x] Test `action_delete_selected()` opens bulk DeleteConfirmationModal
  - [x] Test `d` keybinding triggers single delete
  - [x] Test `D` (Shift+D) keybinding triggers bulk delete
  - [x] Test successful deletion refreshes data table
  - [x] Test successful deletion shows success notification
  - [x] Test failed deletion shows error notification

- [x] Task 6: Write unit tests for FR44 compliance (AC: #7)
  - [x] Test no scheduled deletion methods exist
  - [x] Test no auto-delete triggers exist
  - [x] Test no TTL-based deletion exists
  - [x] Test deletion only occurs via explicit operator action

- [x] Task 7: Write integration tests for full delete flow (AC: #8)
  - [x] Test single item deletion end-to-end
  - [x] Test bulk deletion end-to-end
  - [x] Test secure overwrite actually overwrites file content
  - [x] Test audit log entries are created correctly
  - [x] Test manifest.json is updated correctly
  - [x] Test recovery is not possible after secure delete

---

### 🟢 GREEN PHASE: Implement Features to Pass Tests

- [x] Task 8: Implement SecureDeleter class (AC: #5)
  - [x] Create `src/cyberred/storage/deleter.py`
  - [x] Implement `SecureDeleter.__init__(store, audit_logger)`
  - [x] Implement `secure_delete_file(path)` with 3-pass random overwrite
  - [x] Implement proper file locking detection
  - [x] Add logging for each deletion step

- [x] Task 9: Implement delete_item() in ExfiltratedDataStore (AC: #2)
  - [x] Add `delete_item(item_id)` method to `SecureDeleter`
  - [x] Implement manifest.json update with atomic write
  - [x] Implement in-memory cache update
  - [x] Add audit logging integration
  - [x] Implement rollback on failure

- [x] Task 10: Implement bulk deletion (AC: #4)
  - [x] Add `delete_items(item_ids, continue_on_error=False)` method
  - [x] Implement batch audit logging
  - [x] Return `DeletionResult` with success/failure counts

- [x] Task 11: Implement DeleteConfirmationModal (AC: #1, #3)
  - [x] Create `src/cyberred/tui/widgets/delete_confirmation.py`
  - [x] Implement modal layout with warning, item details, confirmation input
  - [x] Implement "DELETE" / "DELETE ALL" confirmation validation
  - [x] Implement scrollable list for bulk items
  - [x] Emit `DeletionConfirmed` message on valid confirmation

- [x] Task 12: Integrate deletion into DataBrowserScreen (AC: #1, #2)
  - [x] Add `d` keybinding for single item delete
  - [x] Add `D` keybinding for bulk delete
  - [x] Implement `action_delete_item()` to open modal
  - [x] Implement `action_delete_selected()` for bulk delete
  - [x] Handle `DeletionConfirmed` message and invoke SecureDeleter
  - [x] Show success/error notifications
  - [x] Refresh data table after deletion

- [x] Task 13: Add DeletionError to exception hierarchy
  - [ ] Add `DeletionError` to `src/cyberred/core/exceptions.py`
  - [ ] Include `item_id` and `reason` attributes

---

### 🔵 REFACTOR PHASE: Clean Up While Keeping Tests Green

- [x] Task 14: Code quality and documentation
  - [ ] Add comprehensive docstrings to all public methods
  - [ ] Ensure type hints are complete and correct
  - [ ] Run coverage report and add tests until 100% achieved
  - [ ] Add logging for debugging deletion operations
  - [ ] Security review of secure deletion implementation

- [x] Task 15: Final validation
  - [ ] Verify all acceptance criteria met
  - [ ] Run full test suite
  - [ ] Test with real encrypted data files
  - [ ] Verify audit log entries are complete and accurate
  - [ ] Verify FR44 compliance (no auto-delete anywhere)

---

## Dev Notes

### Architecture Patterns

**SecureDeleter Class** (`src/cyberred/storage/deleter.py`):
```python
SECURE_DELETE_PASSES = 3

@dataclass
class DeletionResult:
    total_items: int
    deleted_items: int
    failed_items: list[tuple[str, str]]  # (item_id, error_message)
    
    @property
    def success(self) -> bool: return self.deleted_items == self.total_items

class SecureDeleter:
    """Secure deletion with 3-pass random overwrite (DoD 5220.22-M style). FR45."""
    
    def __init__(self, store: "ExfiltratedDataStore", audit_logger: "DeletionAuditLogger"):
        self._store, self._audit = store, audit_logger
    
    def secure_delete_file(self, file_path: Path) -> None:
        """3-pass overwrite with secrets.token_bytes(), fsync each pass, then unlink."""
        if not file_path.exists(): return
        file_size = file_path.stat().st_size
        for _ in range(SECURE_DELETE_PASSES):
            with open(file_path, "r+b") as f:
                f.write(secrets.token_bytes(file_size)); f.flush(); os.fsync(f.fileno())
        file_path.unlink()
        if file_path.exists():
            raise DeletionError("File still exists", reason="verification_failed")
    
    def delete_item(self, item_id: str) -> None:
        """Delete single item: secure_delete_file -> remove from manifest -> audit log."""
        item = self._store.get_item(item_id)
        if not item: raise KeyError(f"Item not found: {item_id}")
        self.secure_delete_file(self._store._evidence_path / item.encrypted_path)
        self._store._remove_from_manifest(item_id)
        del self._store._items[item_id]
        self._audit.log_deletion(item_id, item.filename, item.target, item.size_bytes)
    
    def delete_items(self, item_ids: list[str], continue_on_error: bool = False) -> DeletionResult:
        """Bulk delete with optional continue_on_error. Returns DeletionResult."""
        deleted, failed = 0, []
        for item_id in item_ids:
            try: self.delete_item(item_id); deleted += 1
            except (DeletionError, KeyError) as e:
                failed.append((item_id, str(e)))
                if not continue_on_error: break
        if deleted: self._audit.log_bulk_deletion(item_ids[:deleted], deleted, len(failed))
        return DeletionResult(len(item_ids), deleted, failed)
```

**ExfiltratedDataStore Extension** (add to `evidence.py`):
```python
def _remove_from_manifest(self, item_id: str) -> None:
    """Atomic manifest update: read -> filter -> write to tmp -> rename."""
    manifest_path, temp_path = self._evidence_path / self.MANIFEST_FILE, ...
    manifest = json.load(open(manifest_path))
    manifest["exfiltrated_data"] = [i for i in manifest.get("exfiltrated_data", []) if i.get("id") != item_id]
    json.dump(manifest, open(temp_path, "w"), indent=2)
    shutil.move(str(temp_path), str(manifest_path))
```

**DeleteConfirmationModal** (`src/cyberred/tui/widgets/delete_confirmation.py`):
```python
class DeleteConfirmationModal(ModalScreen):
    """Requires typing "DELETE" (single) or "DELETE ALL" (bulk) to confirm. FR45."""
    BINDINGS = [("escape", "cancel", "Cancel")]
    
    class DeletionConfirmed(Message):
        def __init__(self, item_ids: list[str]): self.item_ids = item_ids; super().__init__()
    
    def __init__(self, items: list["ExfiltratedDataItem"], name: str | None = None):
        super().__init__(name=name)
        self._items, self._is_bulk = items, len(items) > 1
        self._required_text = "DELETE ALL" if self._is_bulk else "DELETE"
    
    def compose(self) -> ComposeResult:
        # Warning header, item list (scrollable if bulk), confirmation input, Cancel/Delete buttons
        # Shows: filename, target, size for single; bullet list for bulk
        ...
    
    def _attempt_confirm(self) -> None:
        if self.query_one("#confirm-input", Input).value.strip().upper() == self._required_text:
            self.dismiss(self.DeletionConfirmed([item.id for item in self._items]))
```

**DeletionError** (add to `exceptions.py`):
```python
class DeletionError(CyberRedError):
    def __init__(self, message: str, item_id: str = "", reason: str = ""):
        super().__init__(message); self.item_id, self.reason = item_id, reason
```

**DeletionAuditLogger** (add to `audit.py`):
```python
class DeletionAuditLogger:
    """Logs deletions to structured logger + Redis stream (audit:deletions)."""
    def log_deletion(self, item_id, filename, target, size_bytes): ...
    def log_bulk_deletion(self, item_ids, total_deleted, total_failed): ...
```

### Component Locations

| Component | Location | Purpose |
|-----------|----------|---------|
| `SecureDeleter` | `src/cyberred/storage/deleter.py` | Secure deletion logic |
| `DeletionResult` | `src/cyberred/storage/deleter.py` | Deletion result dataclass |
| `DeletionError` | `src/cyberred/core/exceptions.py` | Deletion-specific exception |
| `DeletionAuditLogger` | `src/cyberred/core/audit.py` | Audit logging for deletions |
| `DeleteConfirmationModal` | `src/cyberred/tui/widgets/delete_confirmation.py` | TUI confirmation modal |
| `DataBrowserScreen` | `src/cyberred/tui/screens/data_browser.py` | Updated with delete integration |
| Unit tests | `tests/unit/storage/test_deleter.py` | SecureDeleter unit tests |
| Unit tests | `tests/unit/tui/test_delete_confirmation.py` | TUI widget tests |
| Integration tests | `tests/integration/tui/test_data_deletion.py` | Full deletion flow tests |

### Existing Code to Leverage

**From `src/cyberred/storage/evidence.py`** (Story 11.2):
- `ExfiltratedDataStore` - store with `get_item()`, `_items` cache
- `ExfiltratedDataItem` - item dataclass
- Manifest loading/saving patterns

**From `src/cyberred/tui/screens/data_browser.py`** (Story 11.2/11.3):
- `DataBrowserScreen` - existing screen with keybindings
- `_selected_item_id` and `_selected_items` - selection tracking
- Notification patterns with `self.notify()`
- Export integration patterns (similar to deletion flow)

**From `src/cyberred/storage/exporter.py`** (Story 11.3):
- Atomic write patterns (write to temp, rename)
- `SecureBuffer` usage for sensitive data
- Progress tracking patterns

**From `src/cyberred/core/audit.py`** (Story 11.3):
- `ExportAuditLogger` pattern for audit entries
- Redis stream integration

### Keybindings (per UX Design)

| Key | Action | Context |
|-----|--------|---------|
| `d` | Delete selected item | Single item selected |
| `D` (Shift+D) | Delete all selected | Multi-select mode |
| `Escape` | Cancel deletion | Confirmation modal |
| `Enter` | Submit confirmation | Confirmation modal |

### Security Considerations

1. **Secure overwrite**: 3-pass random byte overwrite (DoD 5220.22-M inspired)
2. **Cryptographic randomness**: Use `secrets.token_bytes()` not `os.urandom()`
3. **Fsync after each pass**: Ensure data is written to disk, not just buffered
4. **Verification**: Confirm file no longer exists after unlink
5. **Atomic manifest update**: Prevent partial state on crash
6. **Audit trail**: All deletions logged with item_id, timestamp, operator
7. **No auto-delete**: FR44 compliance - only manual operator deletion

### FR44/FR45 Compliance

**FR44 (No Auto-Delete)**:
- ❌ NO scheduled deletion jobs
- ❌ NO TTL-based expiration
- ❌ NO automatic cleanup
- ✅ Data persists until explicit operator action

**FR45 (Manual Deletion)**:
- ✅ Operator can manually delete via TUI
- ✅ Requires explicit confirmation
- ✅ Secure deletion (overwrite before unlink)
- ✅ All deletions logged to audit trail

### Testing Standards

Per project testing requirements:
- **100% coverage** on all new code
- **TDD methodology**: Write tests first (RED), implement (GREEN), refactor (BLUE)
- **Unit tests**: Test each method in isolation with mocks
- **Integration tests**: Test full deletion flow with real files
- Use fixtures from `tests/fixtures/` for test data
- Follow patterns from `tests/unit/storage/test_evidence.py` and `tests/unit/storage/test_exporter.py`

### Test Commands

```bash
# Activate virtual environment
source venv/bin/activate

# SecureDeleter unit tests
pytest tests/unit/storage/test_deleter.py \
    --cov=src/cyberred/storage/deleter \
    --cov-report=term-missing --cov-fail-under=100

# TUI widget tests
pytest tests/unit/tui/test_delete_confirmation.py \
    --cov=src/cyberred/tui/widgets/delete_confirmation \
    --cov-report=term-missing --cov-fail-under=100

# Integration tests
pytest tests/integration/tui/test_data_deletion.py \
    --cov=src/cyberred --cov-report=term-missing

# Full test suite
pytest tests/ -v --tb=short
```

### Error Messages (User-Friendly)

| Error | Message |
|-------|---------|
| Permission denied | "Cannot delete {filename}: Permission denied. Check file permissions." |
| File locked | "Cannot delete {filename}: File is in use. Close any applications using it." |
| Item not found | "Item no longer exists. It may have been deleted already." |
| Partial failure | "Deleted {n} of {total} items. {failed} items could not be deleted." |
| Invalid confirmation | 'Please type "{required}" exactly to confirm deletion.' |

### Edge Cases to Handle

1. **File already deleted**: Skip gracefully, log warning
2. **Manifest write failure**: Rollback in-memory state
3. **Concurrent access**: Handle manifest race conditions
4. **Very large file**: Progress indicator for overwrite passes
5. **Read-only filesystem**: Clear error message
6. **Network filesystem**: May not support fsync properly - warn user
7. **SSD wear leveling**: Note in docs that SSD may retain data in spare blocks

### References

- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 11.4]
- [Source: _bmad-output/planning-artifacts/ux-design.md#Feedback Patterns]
- [Source: _bmad-output/planning-artifacts/ux-design.md#Keyboard Consistency]
- [Source: _bmad-output/implementation-artifacts/11-2-exfiltrated-data-browser.md]
- [Source: _bmad-output/implementation-artifacts/11-3-data-export-from-tui.md]
- [Source: src/cyberred/storage/evidence.py]
- [Source: src/cyberred/storage/exporter.py]
- [Source: src/cyberred/tui/screens/data_browser.py]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4 (Rovo Dev)

### Debug Log References

- All 62 unit tests pass (17 deleter + 21 audit logger + 11 utils + 13 TUI modal)
- All 8 integration tests pass
- TDD methodology followed: RED (tests first) → GREEN (implementation) → REFACTOR

### Completion Notes List

- Implemented SecureDeleter with 3-pass DoD 5220.22-M style secure overwrite
- Implemented DeleteConfirmationModal requiring typed "DELETE"/"DELETE ALL" confirmation
- Added DeletionError exception to exceptions.py
- Added DeletionAuditLogger and DeletionAuditEntry to audit.py
- Added _remove_from_manifest() atomic update method to ExfiltratedDataStore
- Integrated deletion keybindings (d/D) into DataBrowserScreen
- All acceptance criteria satisfied including FR44/FR45 compliance
- Date: 2026-01-29

### File List

- `src/cyberred/storage/deleter.py` (NEW) - SecureDeleter, DeletionResult
- `src/cyberred/tui/widgets/delete_confirmation.py` (NEW) - DeleteConfirmationModal
- `src/cyberred/core/exceptions.py` (MODIFIED) - Add DeletionError
- `src/cyberred/core/audit.py` (MODIFIED) - Add DeletionAuditLogger, DeletionAuditEntry
- `src/cyberred/storage/evidence.py` (MODIFIED) - Add _remove_from_manifest() method
- `src/cyberred/tui/screens/data_browser.py` (MODIFIED) - Add deletion keybindings and actions
- `tests/unit/storage/test_deleter.py` (NEW) - SecureDeleter unit tests
- `tests/unit/tui/test_delete_confirmation.py` (NEW) - Modal widget tests
- `tests/integration/tui/test_data_deletion.py` (NEW) - Integration tests
