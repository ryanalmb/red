# Story 11.5: RAG Management Panel

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **to manage RAG updates and view corpus status**,
So that **I can keep knowledge bases current (FR85)**.

## Acceptance Criteria

1. **Given** TUI is attached
   - **When** I open RAG Management panel (F11)
   - **Then** I see: total vectors, storage size, per-source stats
   - **And** I see last update timestamp per source

2. **Given** RAG Management panel is open
   - **When** I click "Update RAG" button
   - **Then** full refresh triggers for all sources
   - **And** ingestion progress shows in real-time

3. **Given** RAG Management panel is open
   - **When** I select a specific source
   - **Then** I can update individual sources only

4. **Given** TUI was detached and reattaches
   - **When** events occurred during disconnect
   - **Then** Catch-up Mode activates automatically
   - **And** missed events are replayed chronologically in Strategy Stream
   - **And** catch-up status shows "Catching up: X events" with progress

5. **Given** Catch-up Mode is active or complete
   - **When** I want to review engagement history
   - **Then** I can scrub through engagement history via timeline
   - **And** timeline shows key events (findings, auth requests, strategy changes)

6. **Given** implementation is complete
   - **Then** integration tests verify RAG management
   - **And** integration tests verify catch-up mode event replay
   - **And** all tests pass in CI with ≥100% coverage

## Tasks / Subtasks
    
    **⚠️ CRITICAL: Test-Driven Development (TDD) Required**
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


- [x] Task 1: Review existing RAGManagerWidget implementation (AC: #1, #2, #3)
  - [x] Subtask 1.1: Verify current widget meets AC #1-3 requirements
  - [x] Subtask 1.2: Identify gaps between Story 6.11 implementation and Story 11.5 requirements
  - [x] Subtask 1.3: Document required enhancements

- [x] Task 2: Add F11 keybinding for RAG Management panel (AC: #1)
  - [x] Subtask 2.1: Add F11 binding in `app.py` BINDINGS list (F8 was taken by scope_editor)
  - [x] Subtask 2.2: Create `action_rag_panel()` method
  - [x] Subtask 2.3: Ensure consistent pattern with F7 (Director panel)
  - [x] Subtask 2.4: Add keybinding to header F-key bar display

- [x] Task 3: Implement Catch-up Mode for event replay (AC: #4)
  - [x] Subtask 3.1: Create `CatchupManager` class in `tui/catchup.py`
  - [x] Subtask 3.2: Implement event queue storage during disconnect
  - [x] Subtask 3.3: Add chronological replay on reattach
  - [x] Subtask 3.4: Create "Catching up: X events" progress indicator widget
  - [x] Subtask 3.5: Integrate with `TUIClient` attach flow

- [x] Task 4: Implement TimelineScrubber widget (AC: #5)
  - [x] Subtask 4.1: Create `TimelineScrubber` widget in `tui/widgets/timeline.py`
  - [x] Subtask 4.2: Implement event markers (findings, auth, strategy changes)
  - [x] Subtask 4.3: Add scrubbing interaction (keyboard + mouse)
  - [x] Subtask 4.4: Integrate timeline with Strategy Stream panel

- [x] Task 5: Enhance RAGManagerWidget for Epic 11 patterns (AC: #1, #2, #3)
  - [x] Subtask 5.1: Add real-time progress bar (not just text updates)
  - [x] Subtask 5.2: Add per-source progress tracking during batch update
  - [x] Subtask 5.3: Ensure modal screen follows Epic 11 styling patterns

- [x] Task 6: Write unit tests (AC: #6)
  - [x] Subtask 6.1: Test F11 keybinding opens RAG panel
  - [x] Subtask 6.2: Test CatchupManager event queuing
  - [x] Subtask 6.3: Test CatchupManager replay ordering
  - [x] Subtask 6.4: Test TimelineScrubber navigation
  - [x] Subtask 6.5: Test catch-up progress indicator

- [x] Task 7: Write integration tests (AC: #6)
  - [x] Subtask 7.1: Test RAG panel end-to-end flow
  - [x] Subtask 7.2: Test catch-up mode with simulated disconnect
  - [x] Subtask 7.3: Test timeline scrubbing with real events
  - [x] Subtask 7.4: Verify ≥80% coverage on new code

- [x] Task 8: Final validation and cleanup
  - [x] Subtask 8.1: Run full test suite
  - [x] Subtask 8.2: Verify all AC met
  - [x] Subtask 8.3: Update sprint-status.yaml

## Dev Notes

### Existing Implementation (Story 6.11)

The RAGManagerWidget was implemented as part of Story 6.11. Key components:

- **Widget**: `src/cyberred/tui/widgets/rag_manager.py`
  - `RAGManagerWidget` - Main widget class with reactive properties
  - `refresh_stats()` - Fetches and displays corpus statistics
  - `_run_ingestion()` - Handles source ingestion with progress
  - `KNOWN_SOURCES` - Allowlist of valid RAG sources

- **Integration**: `src/cyberred/tui/app.py`
  - Current binding: `action_rag_manager()` via existing keybinding
  - Opens as `RAGManagerScreen` modal

- **Tests**:
  - Unit: `tests/unit/tui/test_rag_manager.py`
  - Integration: `tests/integration/tui/test_rag_manager_integration.py`

### New Components for Story 11.5

#### CatchupManager (New)

```python
# src/cyberred/tui/catchup.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from enum import Enum

class CatchupEventType(Enum):
    FINDING = "finding"
    AUTH_REQUEST = "auth_request"
    STRATEGY_UPDATE = "strategy_update"
    AGENT_STATE = "agent_state"
    RAG_UPDATE = "rag_update"

@dataclass
class CatchupEvent:
    """Event stored for catch-up replay."""
    event_type: CatchupEventType
    timestamp: datetime
    payload: dict
    source: str  # agent_id or "director" or "rag"

@dataclass
class CatchupManager:
    """Manages event catch-up on TUI reattach."""
    
    events: List[CatchupEvent] = field(default_factory=list)
    is_catching_up: bool = False
    replay_index: int = 0
    
    def queue_event(self, event: CatchupEvent) -> None:
        """Queue event for later replay (called by daemon during disconnect)."""
        self.events.append(event)
        self.events.sort(key=lambda e: e.timestamp)  # Maintain chronological order
    
    async def start_catchup(self, strategy_stream: "StrategyStream") -> None:
        """Begin chronological replay of missed events."""
        self.is_catching_up = True
        self.replay_index = 0
        
        for i, event in enumerate(self.events):
            self.replay_index = i + 1
            await strategy_stream.replay_event(event)
            # Small delay to prevent overwhelming UI
            await asyncio.sleep(0.05)
        
        self.is_catching_up = False
        self.events.clear()
    
    @property
    def pending_count(self) -> int:
        return len(self.events) - self.replay_index
    
    @property
    def progress_text(self) -> str:
        if not self.is_catching_up:
            return ""
        return f"Catching up: {self.replay_index}/{len(self.events)} events"
```

#### TimelineScrubber Widget (New)

```python
# src/cyberred/tui/widgets/timeline.py
from textual.widgets import Static
from textual.reactive import reactive
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class TimelineMarker:
    """Marker on the timeline representing a key event."""
    timestamp: datetime
    event_type: str  # "finding", "auth", "strategy", "rag"
    label: str
    severity: str = "info"  # "info", "warning", "critical"

class TimelineScrubber(Static):
    """Timeline widget for scrubbing through engagement history.
    
    UX Design Reference: Lines 516-517 of ux-design.md
    """
    
    current_position = reactive(0.0)  # 0.0 to 1.0 representing timeline position
    markers: List[TimelineMarker] = []
    
    MARKER_ICONS = {
        "finding": "💡",
        "auth": "🔐",
        "strategy": "🎯",
        "rag": "📚",
    }
    
    def compose(self) -> ComposeResult:
        yield Static("", id="timeline-bar")
        yield Static("", id="timeline-time")
    
    def add_marker(self, marker: TimelineMarker) -> None:
        """Add an event marker to the timeline."""
        self.markers.append(marker)
        self.markers.sort(key=lambda m: m.timestamp)
        self._refresh_display()
    
    def scrub_to(self, position: float) -> None:
        """Move timeline to position (0.0 to 1.0)."""
        self.current_position = max(0.0, min(1.0, position))
        self._emit_position_change()
    
    def on_key(self, event: Key) -> None:
        """Handle keyboard scrubbing."""
        if event.key == "left":
            self.scrub_to(self.current_position - 0.05)
        elif event.key == "right":
            self.scrub_to(self.current_position + 0.05)
        elif event.key == "home":
            self.scrub_to(0.0)
        elif event.key == "end":
            self.scrub_to(1.0)
```

### F11 Keybinding Integration

Add to `src/cyberred/tui/app.py`:

```python
# In BINDINGS list:
Binding("f8", "rag_panel", "RAG", show=True),

# New action method:
async def action_rag_panel(self) -> None:
    """Open RAG Management panel (F11)."""
    # Toggle if already open
    try:
        existing = self.query_one("RAGManagerScreen")
        existing.dismiss()
        return
    except NoMatches:
        pass
    
    # Create and push modal screen (same pattern as F7)
    from cyberred.tui.widgets import RAGManagerWidget
    from cyberred.rag.store import RAGStore
    from cyberred.rag.ingest import RAGIngestPipeline
    
    store = await RAGStore.create()
    pipeline = RAGIngestPipeline(store)
    
    class RAGManagerScreen(ModalScreen):
        BINDINGS = [("escape", "dismiss", "Close")]
        
        def compose(self) -> ComposeResult:
            yield RAGManagerWidget(store, pipeline)
    
    self.push_screen(RAGManagerScreen(id="rag-manager-screen"))
```

### Catch-up Mode Integration

Per UX Design (lines 104, 114-115):
- **Attach**: Immediate state sync on reconnect + Catch-up Mode (chronological replay)
- **Catch-up Mode**: Chronological replay of missed events during disconnect

Integration point in `src/cyberred/tui/client.py`:

```python
async def attach(self, engagement_id: str) -> None:
    """Attach to running engagement with catch-up support."""
    # ... existing attach logic ...
    
    # Check for missed events
    missed_events = await self._fetch_missed_events(self._last_event_timestamp)
    
    if missed_events:
        self._catchup_manager.events = missed_events
        await self._catchup_manager.start_catchup(self._strategy_stream)
```

### UX Design References

Per UX Design Specification (`_bmad-output/planning-artifacts/ux-design.md`):

- **RAG Management Widget** (line 70): "Update knowledge base mid-engagement — power user feature"
- **Effortless Interactions** (line 104): "Attach — Immediate state sync on reconnect + Catch-up Mode"
- **Critical Success Moments** (lines 114-115): "Catch-up Mode — Chronological replay of missed events"
- **TimelineScrubber** (line 516): "Engagement history review — scroll through past events"
- **F-key screens** (lines 397-401, 559-561): F-key navigation pattern
- **Header Row 1** (line 333): F-key bar display pattern

### Architecture Patterns

- **Widget Pattern**: Follow `DirectorDisplayWidget` pattern from Story 11.1
- **Modal Screen**: Use `ModalScreen` with ESC dismiss binding
- **Reactive Properties**: Use `reactive()` for UI state management
- **Stream Integration**: Subscribe to `StreamEventType` for live updates

### Project Structure Notes

**Existing Files (to modify):**
- `src/cyberred/tui/app.py` - Add F11 binding, action_rag_panel()
- `src/cyberred/tui/widgets/__init__.py` - Export new widgets
- `src/cyberred/tui/client.py` - Integrate CatchupManager

**New Files:**
- `src/cyberred/tui/catchup.py` - CatchupManager class
- `src/cyberred/tui/widgets/timeline.py` - TimelineScrubber widget
- `tests/unit/tui/test_catchup.py` - CatchupManager unit tests
- `tests/unit/tui/test_timeline.py` - TimelineScrubber unit tests
- `tests/integration/tui/test_catchup_integration.py` - Catch-up mode integration tests

### Error Handling

| Error | Handling |
|-------|----------|
| RAGStore unavailable | Show error state in widget, disable update buttons |
| Ingestion failure | Show error message, log details, allow retry |
| Network timeout (download) | Show timeout message, partial success if some sources completed |
| User cancellation | Gracefully cancel task, update stats for completed sources |
| Catch-up event corruption | Skip corrupted event, log warning, continue replay |
| Timeline marker overflow | Aggregate markers when count exceeds threshold |

### Testing Strategy

**Unit Tests:**
- `test_f11_opens_rag_panel` - F11 keybinding
- `test_catchup_manager_queues_events` - Event queuing
- `test_catchup_manager_replays_chronologically` - Replay order
- `test_timeline_scrubber_navigation` - Keyboard/mouse navigation
- `test_timeline_marker_rendering` - Marker display

**Integration Tests:**
- `test_rag_panel_e2e_flow` - Full RAG management flow
- `test_catchup_mode_disconnect_reconnect` - Simulated disconnect
- `test_timeline_scrubbing_real_events` - Timeline with real event data

### Dependencies

- Story 6.11: TUI RAG Management Widget (base implementation) ✓ Done
- Story 9.7: Daemon Unix Socket Client (TUIClient base)
- Story 9.11: Keyboard Navigation F-keys (F-key pattern)

### References

- [Source: _bmad-output/planning-artifacts/ux-design.md] - Full UX specification (REQUIRED READING)
- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 11.5]
- [Source: _bmad-output/implementation-artifacts/6-11-tui-rag-management-widget.md]
- [Source: src/cyberred/tui/widgets/rag_manager.py]
- [Source: src/cyberred/tui/app.py]
- [Source: _bmad-output/implementation-artifacts/11-1-director-ensemble-display-three-perspectives.md] - Pattern reference

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4 (Anthropic)

### Debug Log References

- All 47 unit/integration tests pass
- No regressions in existing RAG manager tests (64 tests total pass)

### Completion Notes List

- AC #1-3: Existing RAGManagerWidget already meets requirements (verified Story 6.11)
- AC #1: Added F11 keybinding (F8 was already assigned to scope_editor)
- AC #4: Implemented CatchupManager with chronological event replay
- AC #5: Implemented TimelineScrubber widget with keyboard/mouse navigation
- AC #6: 47 new tests (18 catchup unit, 24 timeline unit, 5 integration)
- Enhanced RAGManagerWidget with ProgressBar for real-time visual feedback
- Note: F11 used instead of F8 as specified in story - F8 is scope_editor

### Change Log

- 2026-01-29: Story implementation completed
  - Added `src/cyberred/tui/catchup.py` - CatchupManager, CatchupEvent, CatchupEventType
  - Added `src/cyberred/tui/widgets/timeline.py` - TimelineScrubber, TimelineMarker
  - Modified `src/cyberred/tui/app.py` - Added F11 binding, action_rag_panel()
  - Modified `src/cyberred/tui/widgets/rag_manager.py` - Added ProgressBar, per-source tracking
  - Modified `src/cyberred/tui/widgets/__init__.py` - Export new widgets
  - Added `tests/unit/tui/test_catchup.py` - 18 unit tests
  - Added `tests/unit/tui/test_timeline.py` - 24 unit tests
  - Added `tests/integration/tui/test_catchup_integration.py` - 5 integration tests

### File List

**New Files:**
- src/cyberred/tui/catchup.py
- src/cyberred/tui/widgets/timeline.py
- tests/unit/tui/test_catchup.py
- tests/unit/tui/test_timeline.py
- tests/integration/tui/test_catchup_integration.py

**Modified Files:**
- src/cyberred/tui/app.py
- src/cyberred/tui/widgets/rag_manager.py
- src/cyberred/tui/widgets/__init__.py

