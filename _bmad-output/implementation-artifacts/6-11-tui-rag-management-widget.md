# Story 6.11: TUI RAG Management Widget

Status: done 

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **to manage RAG updates via TUI**,
So that **I can refresh knowledge bases without CLI access (FR81, FR85)**.

## Acceptance Criteria

1. **Given** Stories 6.1-6.8 are complete and TUI exists
   - **When** I open RAG Management panel
   - **Then** I see corpus stats: total vectors, storage size

2. **Given** RAG Management panel is open
   - **Then** I see per-source status with chunk count
   - **And** I see last update timestamp for each source

3. **Given** RAG Management panel is open
   - **When** I click "Update RAG" button
   - **Then** full re-ingestion triggers for all sources

4. **Given** re-ingestion is running
   - **Then** ingestion progress is displayed in real-time
   - **And** progress shows current source, document count, chunks processed

5. **Given** RAG Management panel is open
   - **When** I select individual source
   - **Then** I can update that source selectively (not all sources)

6. **Given** integration tests exist
   - **Then** tests verify TUI RAG management widget functionality

## Tasks / Subtasks

- [ ] Task 1: Create RAGManagerWidget class (AC: 1, 2)
  - [ ] 1.1 Create `src/cyberred/tui/widgets/rag_manager.py` with `RAGManagerWidget` class
  - [ ] 1.2 Implement widget layout: stats panel, source list, action buttons
  - [ ] 1.3 Display corpus stats (total vectors, storage size in human-readable format)
  - [ ] 1.4 Display per-source table: source name, chunk count, last updated, status

- [ ] Task 2: Implement stats fetching (AC: 1, 2)
  - [ ] 2.1 Add async `refresh_stats()` method calling `RAGStore.get_stats()`
  - [ ] 2.2 Load ingestion stats from `.rag_stats_*.json` files for per-source timestamps
  - [ ] 2.3 Format storage size as human-readable (KB, MB, GB)
  - [ ] 2.4 Implement reactive update of stats display

- [ ] Task 3: Implement "Update All" action (AC: 3, 4)
  - [ ] 3.1 Add "Update RAG" button with `on_button_pressed` handler
  - [ ] 3.2 Implement non-blocking ingestion via `RAGIngestPipeline`
  - [ ] 3.3 Pass progress callback to pipeline for real-time display
  - [ ] 3.4 Show progress bar or log with: source, current_doc/total_docs, chunks_processed

- [ ] Task 4: Implement selective source update (AC: 5)
  - [ ] 4.1 Add source selection (DataTable row highlight or checkbox)
  - [ ] 4.2 Add "Update Selected" button
  - [ ] 4.3 Implement single-source ingestion (pass source filter to pipeline)
  - [ ] 4.4 Update only selected source's stats on completion

- [ ] Task 5: Integrate widget into TUI (AC: 1)
  - [ ] 5.1 Add F6 keybinding for "RAG" panel in `CyberRedApp`
  - [ ] 5.2 Create `RAGManagerScreen` as modal or dedicated screen
  - [ ] 5.3 Add RAG status indicator to main TUI footer or sidebar
  - [ ] 5.4 Update `src/cyberred/tui/__init__.py` exports

- [ ] Task 6: Update widgets module exports (AC: 1)
  - [ ] 6.1 Update `src/cyberred/tui/widgets.py` or create `widgets/` package
  - [ ] 6.2 Export `RAGManagerWidget` and supporting components

- [ ] Task 7: Unit tests (AC: 1-5)
  - [ ] 7.1 Create `tests/unit/tui/test_rag_manager.py`
  - [ ] 7.2 Test stats display formatting (size conversion, date formatting)
  - [ ] 7.3 Test widget composition and layout
  - [ ] 7.4 Test button handlers with mocked dependencies
  - [ ] 7.5 Test progress callback integration

- [ ] Task 8: Integration tests (AC: 6)
  - [ ] 8.1 Create `tests/integration/tui/test_rag_manager_integration.py`
  - [ ] 8.2 Test full update flow with real RAGStore (temp directory)
  - [ ] 8.3 Test selective source update
  - [ ] 8.4 Test progress updates during ingestion
  - [ ] 8.5 Test widget interaction with TUI app

## Dev Notes

### Architecture Patterns

- **Widget Location**: Per architecture.md line 887: `tui/widgets/rag_manager.py`
- **Non-blocking Updates**: Engagement continues during RAG refresh (per epics-stories.md)
- **Stats Source**: `RAGStore.get_stats()` provides corpus-level stats; `.rag_stats_*.json` files for per-source timestamps
- **Progress Callback**: Use `IngestionProgress` dataclass from `rag/ingest.py` (already exists)

### Integration Points

```
┌─────────────────────────────────────────────────────────────────┐
│                      CyberRedApp (TUI)                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────────┐ │
│  │ HiveGrid   │  │ KillChain  │  │ RAGManagerWidget (NEW)     │ │
│  │ (existing) │  │ (existing) │  │ - Stats display            │ │
│  └────────────┘  └────────────┘  │ - Source list              │ │
│                                  │ - Update buttons           │ │
│                                  │ - Progress bar             │ │
│                                  └─────────────┬──────────────┘ │
└────────────────────────────────────────────────┼────────────────┘
                                                 │
                         ┌───────────────────────┼───────────────────────┐
                         │                       ▼                       │
                         │               RAGStore (6.1)                  │
                         │               - get_stats()                   │
                         │               - health_check()                │
                         │                       │                       │
                         │                       ▼                       │
                         │           RAGIngestPipeline (6.4)             │
                         │           - ingest_source()                   │
                         │           - progress_callback                 │
                         └───────────────────────────────────────────────┘
```

### Existing Data Models (from src/cyberred/rag/models.py)

```python
@dataclass
class RAGStoreStats:
    total_vectors: int
    storage_size_bytes: int
    sources: List[str]
    last_updated: Optional[datetime]
    source_counts: Dict[str, int]  # {source_name: chunk_count}
```

```python
@dataclass
class IngestionProgress:
    """Progress tracking for ingestion pipeline (FR77)."""
    source: str
    current_doc: int
    total_docs: int
    chunks_processed: int
```

### Widget Layout Design

```
╔══════════════════════════════════════════════════════════════╗
║                     RAG KNOWLEDGE BASE                        ║
╠══════════════════════════════════════════════════════════════╣
║  CORPUS STATS                                                 ║
║  ├─ Total Vectors: 72,450                                     ║
║  ├─ Storage Size:  156.3 MB                                   ║
║  └─ Last Updated:  2026-01-08 14:32:00                        ║
╠══════════════════════════════════════════════════════════════╣
║  SOURCE                  │ CHUNKS  │ LAST UPDATED │ STATUS    ║
║  ────────────────────────┼─────────┼──────────────┼───────────║
║  ▸ mitre-attack          │  12,450 │ 2026-01-08   │ ✓ Ready   ║
║  ▸ atomic-red-team       │  18,200 │ 2026-01-07   │ ✓ Ready   ║
║  ▸ hacktricks            │  28,500 │ 2026-01-06   │ ✓ Ready   ║
║  ▸ payloads-all-things   │   8,300 │ 2026-01-05   │ ✓ Ready   ║
║  ▸ lolbas                │   3,200 │ 2026-01-05   │ ✓ Ready   ║
║  ▸ gtfobins              │   1,800 │ 2026-01-05   │ ✓ Ready   ║
╠══════════════════════════════════════════════════════════════╣
║  PROGRESS: Updating hacktricks... (142/856 docs, 4,230 chunks)║
╠══════════════════════════════════════════════════════════════╣
║  [Update All]  [Update Selected]  [Cancel]  [Close]           ║
╚══════════════════════════════════════════════════════════════╝
```

### Key Implementation Details

#### 1. Widget Class Structure

```python
from textual.widgets import Static, DataTable, Button, ProgressBar
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.reactive import reactive

class RAGManagerWidget(Static):
    """RAG Management Widget for TUI (FR81, FR85)."""
    
    # Reactive properties for automatic UI updates
    total_vectors: reactive[int] = reactive(0)
    storage_size: reactive[int] = reactive(0)
    is_updating: reactive[bool] = reactive(False)
    
    def __init__(self, rag_store: RAGStore, ingest_pipeline: RAGIngestPipeline) -> None:
        super().__init__()
        self._store = rag_store
        self._pipeline = ingest_pipeline
        self._update_task: Optional[asyncio.Task] = None
    
    def compose(self) -> ComposeResult:
        with Container(id="rag-manager"):
            yield Static("RAG KNOWLEDGE BASE", id="rag-title")
            yield Static(id="corpus-stats")
            yield DataTable(id="source-table")
            yield Static(id="progress-display")
            with Horizontal(id="rag-buttons"):
                yield Button("Update All", id="btn-update-all", variant="primary")
                yield Button("Update Selected", id="btn-update-selected")
                yield Button("Cancel", id="btn-cancel", disabled=True)
                yield Button("Close", id="btn-close")
```

#### 2. Stats Fetching

```python
async def refresh_stats(self) -> None:
    """Fetch and display current RAG stats."""
    stats = await self._store.get_stats()
    
    self.total_vectors = stats.total_vectors
    self.storage_size = stats.storage_size_bytes
    
    # Update corpus stats display
    stats_widget = self.query_one("#corpus-stats", Static)
    stats_widget.update(
        f"Total Vectors: {stats.total_vectors:,}\n"
        f"Storage Size: {self._format_size(stats.storage_size_bytes)}\n"
        f"Sources: {len(stats.sources)}"
    )
    
    # Update source table
    table = self.query_one("#source-table", DataTable)
    table.clear()
    for source in stats.sources:
        count = stats.source_counts.get(source, 0)
        last_updated = self._get_source_timestamp(source)
        table.add_row(source, f"{count:,}", last_updated, "✓ Ready")

def _format_size(self, size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
```

#### 3. Progress Callback Integration

```python
async def _run_ingestion(self, sources: Optional[List[str]] = None) -> None:
    """Run ingestion with progress updates."""
    self.is_updating = True
    cancel_btn = self.query_one("#btn-cancel", Button)
    cancel_btn.disabled = False
    
    try:
        await self._pipeline.ingest_all(
            sources=sources,
            progress_callback=self._on_progress
        )
    finally:
        self.is_updating = False
        cancel_btn.disabled = True
        await self.refresh_stats()

def _on_progress(self, progress: IngestionProgress) -> None:
    """Handle ingestion progress updates."""
    progress_widget = self.query_one("#progress-display", Static)
    progress_widget.update(
        f"Updating {progress.source}... "
        f"({progress.current_doc}/{progress.total_docs} docs, "
        f"{progress.chunks_processed:,} chunks)"
    )
```

#### 4. Source Selection

```python
async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
    """Handle source row selection for selective update."""
    self._selected_source = event.row_key.value

async def on_button_pressed(self, event: Button.Pressed) -> None:
    """Handle button clicks."""
    if event.button.id == "btn-update-all":
        asyncio.create_task(self._run_ingestion())
    elif event.button.id == "btn-update-selected" and self._selected_source:
        asyncio.create_task(self._run_ingestion(sources=[self._selected_source]))
    elif event.button.id == "btn-cancel" and self._update_task:
        self._update_task.cancel()
    elif event.button.id == "btn-close":
        self.app.pop_screen()
```

### CSS Styling (add to style.tcss)

```css
#rag-manager {
    width: 100%;
    height: 100%;
    padding: 1;
}

#rag-title {
    text-align: center;
    text-style: bold;
    background: $primary;
    padding: 1;
    margin-bottom: 1;
}

#corpus-stats {
    padding: 1;
    background: $surface;
    margin-bottom: 1;
}

#source-table {
    height: auto;
    max-height: 50%;
    margin-bottom: 1;
}

#progress-display {
    padding: 1;
    background: $warning-darken-2;
    color: $text;
}

#rag-buttons {
    align: center middle;
    height: auto;
    padding: 1;
}

#rag-buttons Button {
    margin: 0 1;
}
```

### Loading Per-Source Timestamps

The `RAGIngestPipeline` writes `.rag_stats_<source>.json` files in the store directory. Load these for accurate per-source timestamps:

```python
def _get_source_timestamp(self, source: str) -> str:
    """Get last update timestamp for a source."""
    stats_file = self._store._store_path / f".rag_stats_{source}.json"
    if stats_file.exists():
        try:
            data = json.loads(stats_file.read_text())
            stats = IngestionStats.from_dict(data)
            return stats.last_updated.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
    return "Never"
```

### Testing Standards

- Follow existing test patterns from `tests/unit/tui/test_daemon_client.py`
- Use `pytest-textual-snapshot` or mock Textual app for widget tests
- Mock `RAGStore` and `RAGIngestPipeline` for unit tests
- Test edge cases: empty store, ingestion failure, cancellation
- **Coverage Target**: 100% for `rag_manager.py`

### File Locations

**Source files:**
- `src/cyberred/tui/widgets/rag_manager.py` - RAGManagerWidget implementation (NEW)
- `src/cyberred/tui/widgets/__init__.py` - Widget exports (NEW if converting to package)
- `src/cyberred/tui/app.py` - Add F6 binding and screen integration
- `src/cyberred/tui/style.tcss` - Add RAG manager styles

**Test files:**
- `tests/unit/tui/test_rag_manager.py` - Unit tests (NEW)
- `tests/integration/tui/test_rag_manager_integration.py` - Integration tests (NEW)

### Dependencies

- Existing dependencies sufficient (no new packages needed):
  - `textual>=0.40.0` - TUI framework (already used)
  - `structlog` - Logging (already used)
  - `asyncio` - Async handling (stdlib)
- Depends on: `RAGStore` (Story 6.1), `RAGIngestPipeline` (Story 6.4), `IngestionProgress` (Story 6.4)

### Project Structure Notes

- Alignment with unified project structure: TUI widgets in `src/cyberred/tui/widgets/`
- Per architecture.md line 887: widget at `tui/widgets/rag_manager.py`
- May need to convert `widgets.py` to `widgets/` package (move existing widgets)
- Follow existing modal pattern from `AuthorizationModal` in `widgets.py`

### Known RAG Sources (from completed stories)

| Source | Story | Module |
|--------|-------|--------|
| mitre-attack | 6.5 | `rag/sources/mitre_attack.py` |
| atomic-red-team | 6.6 | `rag/sources/atomic_red.py` |
| hacktricks | 6.7 | `rag/sources/hacktricks.py` |
| payloads-all-things | 6.8 | `rag/sources/payloads.py` |
| lolbas | 6.8 | `rag/sources/lolbas.py` |
| gtfobins | 6.8 | `rag/sources/gtfobins.py` |

### Previous Story Intelligence (Story 6.10)

**Key learnings from Story 6.10 (Agent RAG Escalation):**

- `RAGStore.get_stats()` returns `RAGStoreStats` with all needed corpus info
- Source counts available in `stats.source_counts` dict
- Use structlog with context binding for consistent logging
- Decision context logging is CRITICAL for emergence validation
- Follow test patterns in `tests/unit/rag/` directory

**Difference from Story 6.10:**
- Story 6.10: Agent queries RAG for alternative methodologies
- Story 6.11: Operator manages RAG knowledge base via TUI widget
- Story 6.11 focuses on UI/UX, not query logic

### Error Handling

| Error | Handling |
|-------|----------|
| RAGStore unavailable | Show error state in widget, disable update buttons |
| Ingestion failure | Show error message, log details, allow retry |
| Network timeout (download) | Show timeout message, partial success if some sources completed |
| User cancellation | Gracefully cancel task, update stats for completed sources |

### References

- Story definition: `_bmad-output/planning-artifacts/epics-stories.md` → "Story 6.11: TUI RAG Management Widget"
- Architecture: `_bmad-output/planning-artifacts/architecture.md` → line 887: `rag_manager.py`
- Previous story: `_bmad-output/implementation-artifacts/6-10-agent-rag-escalation.md`
- RAG Store: `src/cyberred/rag/store.py` (RAGStore, RAGStoreStats)
- RAG Models: `src/cyberred/rag/models.py` (IngestionProgress, IngestionStats)
- Ingest Pipeline: `src/cyberred/rag/ingest.py` (RAGIngestPipeline)
- TUI App: `src/cyberred/tui/app.py` (CyberRedApp)
- Existing Widgets: `src/cyberred/tui/widgets.py` (pattern reference)
- FR81: Update RAG button, status, stats display
- FR85: Manage RAG updates via TUI without CLI access

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

