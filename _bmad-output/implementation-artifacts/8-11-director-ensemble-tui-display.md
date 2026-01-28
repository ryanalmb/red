# Story 8.11: Director Ensemble TUI Display

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **to view all three Director perspectives in the TUI**,
So that **I understand the strategic reasoning behind decisions (FR10)**.

## Acceptance Criteria

1. **Given** Stories 8.1-8.5 are complete and TUI exists
   - **When** Director produces synthesis
   - **Then** TUI displays: DeepSeek strategy view, Kimi K2 analysis view, MiniMax M2 creative view

2. **Given** Director synthesis is displayed
   - **When** synthesis includes all three perspectives
   - **Then** TUI displays: synthesized unified strategy

3. **Given** MiniMax M2 provides creative response
   - **When** response includes `<think>...</think>` tags
   - **Then** thinking tags are optionally visible (debug mode toggle)

4. **Given** Director perspectives are displayed
   - **When** operator wants to see details
   - **Then** I can expand/collapse individual perspectives

5. **Given** TUI is connected to daemon
   - **When** Director publishes new strategy
   - **Then** updates are real-time via daemon connection (streaming)

6. **Given** Director Ensemble TUI Display
   - **When** integration tests run
   - **Then** tests verify TUI Director display rendering and updates

## Tasks / Subtasks

- [x] Task 1: Create DirectorDisplayWidget (AC: 1, 2)
  - [x] 1.1: Define `DirectorDisplayWidget` class in `tui/widgets/director_display.py`
  - [x] 1.2: Create three collapsible sections: Strategist, Analyst, Creative
  - [x] 1.3: Create unified strategy section at top
  - [x] 1.4: Add TCSS styling matching "Command & Control" aesthetic
  - [x] 1.5: Export widget in `tui/widgets/__init__.py`

- [x] Task 2: Implement perspective views (AC: 1, 3)
  - [x] 2.1: Create `StrategistView` component showing recommendations, priorities, ATT&CK techniques
  - [x] 2.2: Create `AnalystView` component showing analysis, gaps, overlooked opportunities
  - [x] 2.3: Create `CreativeView` component showing alternatives, evasion techniques, novel approaches
  - [x] 2.4: Implement `<think>` tag rendering with debug mode toggle
  - [x] 2.5: Add color coding per role (strategist=blue, analyst=cyan, creative=magenta)

- [x] Task 3: Implement expand/collapse functionality (AC: 4)
  - [x] 3.1: Add Collapsible container for each perspective
  - [x] 3.2: Implement keyboard shortcuts for expand/collapse (1, 2, 3 keys)
  - [x] 3.3: Add expand/collapse all toggle
  - [x] 3.4: Persist expand/collapse state during session

- [x] Task 4: Integrate with daemon streaming (AC: 5)
  - [x] 4.1: Subscribe to `strategies:{engagement_id}` channel via daemon client
  - [x] 4.2: Handle `StreamEventType.STRATEGY_UPDATE` events
  - [x] 4.3: Parse DirectorQueryResult and SynthesizedStrategy from stream
  - [x] 4.4: Update widget reactively on new strategy arrival
  - [x] 4.5: Add visual indicator for "Strategy Updated" notification

- [x] Task 5: Integrate with CyberRedApp (AC: 1, 5)
  - [x] 5.1: Add DirectorDisplayWidget to TUI layout (pane-mid, below brain stream)
  - [x] 5.2: Add F7 keybinding to toggle Director panel visibility
  - [x] 5.3: Wire up strategy update handler in `_handle_stream_event()`
  - [x] 5.4: Add debug mode toggle binding (Ctrl+T for debug thinking tags)

- [x] Task 6: Write unit tests (AC: 1-4)
  - [x] 6.1: Test DirectorDisplayWidget initialization
  - [x] 6.2: Test perspective view rendering with mock data
  - [x] 6.3: Test expand/collapse state management
  - [x] 6.4: Test `<think>` tag visibility toggle
  - [x] 6.5: Test strategy message parsing

- [x] Task 7: Write integration tests (AC: 5, 6)
  - [x] 7.1: Test real-time update from daemon stream
  - [x] 7.2: Test multiple strategy updates in sequence
  - [x] 7.3: Test TUI rendering with actual DirectorEnsemble output
  - [x] 7.4: Test graceful handling of partial model responses (degradation display)

## Dev Notes

### Architecture Patterns

**Per Architecture Document (`_bmad-output/planning-artifacts/architecture.md`):**

1. **TUI Framework** (Section: War Room TUI):
   - Textual framework with TCSS theming
   - Dark mode "Command & Control" aesthetic
   - Three-pane War Room layout
   - F-key navigation (F1-F6, extend with F7 for Director)
   - WCAG 2.1 Level AA accessibility

2. **Daemon Streaming** (Section: Daemon Architecture):
   - TUIClient streams events from daemon
   - Strategy updates via `StreamEventType` enum
   - Real-time updates without polling

3. **Director Ensemble Output** (Section: Director Architecture):
   - Three roles: Strategist (DeepSeek), Analyst (Kimi K2), Creative (MiniMax)
   - Per-model timeout: 100s, aggregate: 180s
   - MiniMax uses `<think>` tags for interleaved reasoning

### Existing Implementation Reference

**From `src/cyberred/llm/ensemble.py`:**
```python
class DirectorRole(Enum):
    STRATEGIST = "strategist"  # DeepSeek - strategic planning
    ANALYST = "analyst"        # Kimi K2 - deep reasoning
    CREATIVE = "creative"      # MiniMax M2 - lateral thinking

@dataclass
class SynthesizedStrategy:
    objectives: List[str]
    actions: List[str]
    rationale: str
    confidence: float
    contributing_roles: List[DirectorRole]
    avoid_list: List[str]
    attck_techniques: List[ATTCKRecommendation]
    creative_alternatives: List[CreativeAlternative]
    risk_warnings: List[str]
    conflicts_resolved: List[ConflictResolution]
    degradation_level: DegradationLevel
    missing_perspectives: List[DirectorRole]
    fallback_warnings: List[str]
```

**From `src/cyberred/tui/app.py`:**
```python
class CyberRedApp(App):
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
        ("f5", "approvals", "Approvals"),
        ("p", "panic", "PANIC"),
        ("ctrl+d", "detach", "Detach"),
        ("f6", "rag_manager", "RAG Manager"),
    ]
    
    async def _handle_stream_event(self, event) -> None:
        """Route daemon stream events to appropriate handlers."""
        # Add: StreamEventType.STRATEGY_UPDATE handler
```

**From `src/cyberred/daemon/streaming.py`:**
```python
class StreamEventType(Enum):
    AGENT_STATUS = "agent_status"
    FINDING = "finding"
    AUTH_REQUEST = "auth_request"
    STATE_CHANGE = "state_change"
    HEARTBEAT = "heartbeat"
    # Add: STRATEGY_UPDATE = "strategy_update"
```

**From `src/cyberred/tui/widgets/rag_manager.py`:**
- Pattern for TUI widget with reactive properties
- Button handling and modal screen integration
- Async task management for updates

### Widget Design

```python
@dataclass
class DirectorPerspective:
    """Single Director model perspective for display."""
    role: DirectorRole
    content: str
    latency_ms: int
    success: bool
    error: Optional[str] = None
    thinking_content: Optional[str] = None  # Extracted <think> tags for creative


class DirectorDisplayWidget(Static):
    """Director Ensemble Display Widget for TUI (FR10).
    
    Displays three Director perspectives and unified synthesis:
    - Strategist (DeepSeek): Strategic recommendations, ATT&CK techniques
    - Analyst (Kimi K2): Attack surface analysis, security gaps
    - Creative (MiniMax): Creative alternatives, evasion techniques
    - Unified: Synthesized strategy with objectives and actions
    """
    
    # Reactive properties
    show_thinking = reactive(False)  # Toggle for <think> tags
    strategist_expanded = reactive(True)
    analyst_expanded = reactive(True)
    creative_expanded = reactive(True)
    
    def __init__(self, daemon_client: Optional[TUIClient] = None) -> None:
        super().__init__()
        self._daemon_client = daemon_client
        self._current_strategy: Optional[SynthesizedStrategy] = None
        self._perspectives: Dict[DirectorRole, DirectorPerspective] = {}
```

### TCSS Styling

```css
/* Director Display Widget Styles */
DirectorDisplayWidget {
    height: auto;
    border: solid $primary;
    padding: 1;
}

#director-title {
    text-align: center;
    text-style: bold;
    color: $warning;
    margin-bottom: 1;
}

.perspective-header {
    text-style: bold;
    padding: 0 1;
}

.perspective-strategist { border-left: thick $primary; }
.perspective-analyst { border-left: thick $secondary; }
.perspective-creative { border-left: thick $accent; }

.thinking-content {
    color: $text-muted;
    text-style: italic;
    display: none;  /* Hidden by default */
}

.thinking-content.visible {
    display: block;
}

.unified-strategy {
    background: $surface;
    border: double $success;
    padding: 1;
    margin-top: 1;
}

.degradation-warning {
    color: $warning;
    text-style: bold;
}

.confidence-high { color: $success; }
.confidence-medium { color: $warning; }
.confidence-low { color: $error; }
```

### Streaming Integration

```python
# In CyberRedApp._handle_stream_event()
async def _handle_stream_event(self, event) -> None:
    """Route daemon stream events to appropriate handlers."""
    if event.event_type == StreamEventType.STRATEGY_UPDATE:
        await self._handle_strategy_update(event.data)
    # ... existing handlers

async def _handle_strategy_update(self, data: dict) -> None:
    """Handle Director strategy update event."""
    try:
        director_widget = self.query_one(DirectorDisplayWidget)
        await director_widget.update_strategy(data)
    except NoMatches:
        # Director panel not visible, log but don't error
        log.debug("strategy_update_no_widget")
```

### Testing Standards

**Unit Tests (`tests/unit/tui/test_director_display.py`):**
- Test widget initialization with mock data
- Test perspective rendering for each role
- Test expand/collapse state transitions
- Test `<think>` tag visibility toggle
- Test strategy parsing from JSON
- Test degradation level display
- Test confidence color coding

**Integration Tests (`tests/integration/tui/test_director_display_integration.py`):**
- Test real-time updates via mock daemon stream
- Test multiple sequential strategy updates
- Test with actual DirectorEnsemble.synthesize() output
- Test partial model availability display
- Test keyboard shortcuts for expand/collapse

### Project Structure Notes

**New Files:**
- `src/cyberred/tui/widgets/director_display.py` - Main widget implementation
- `tests/unit/tui/test_director_display.py` - Unit tests
- `tests/integration/tui/test_director_display_integration.py` - Integration tests

**Modified Files:**
- `src/cyberred/tui/widgets/__init__.py` - Export DirectorDisplayWidget
- `src/cyberred/tui/app.py` - Add widget to layout, add F7 binding, add strategy handler
- `src/cyberred/daemon/streaming.py` - Add STRATEGY_UPDATE event type
- `src/cyberred/tui/style.tcss` - Add Director widget styles

### Dependencies

- **Story 8.1** (Director Ensemble Base): COMPLETE - provides DirectorEnsemble class
- **Story 8.2** (DeepSeek Strategist): COMPLETE - provides strategist response parsing
- **Story 8.3** (Kimi K2 Analyst): COMPLETE - provides analyst response parsing
- **Story 8.4** (MiniMax Creative): COMPLETE - provides creative response with `<think>` tags
- **Story 8.5** (Strategy Synthesis): COMPLETE - provides SynthesizedStrategy
- **Story 8.10** (Strategy Publication): COMPLETE - provides strategy streaming to agents
- **Story 9.1** (TUI Core): COMPLETE - provides CyberRedApp and base widgets
- **Story 2.9** (Attach/Detach): COMPLETE - provides TUIClient streaming

### Edge Cases to Handle

1. **Partial Model Responses**: Display available perspectives, show placeholder for failed models
2. **Long Content**: Truncate with "..." and allow expand on click
3. **Rapid Updates**: Debounce UI updates if strategies arrive faster than 1/sec
4. **No Strategy Yet**: Show "Awaiting Director synthesis..." placeholder
5. **Degradation Mode**: Clearly indicate which models are unavailable and confidence reduction

### Accessibility (WCAG 2.1 AA)

- All interactive elements keyboard accessible
- Color coding supplemented with text labels
- Screen reader compatible labels for perspectives
- Focus indicators for expand/collapse buttons
- Sufficient color contrast for all text

### References

- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story-8.11] - Story definition
- [Source: _bmad-output/planning-artifacts/architecture.md#War-Room-TUI] - TUI architecture
- [Source: _bmad-output/planning-artifacts/ux-design.md] - UX patterns
- [Source: src/cyberred/llm/ensemble.py] - DirectorEnsemble, SynthesizedStrategy
- [Source: src/cyberred/tui/app.py] - CyberRedApp integration points
- [Source: src/cyberred/tui/widgets/rag_manager.py] - Widget pattern reference
- [Source: _bmad-output/implementation-artifacts/8-10-strategy-publication-to-agents.md] - Strategy streaming

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

- All 69 tests pass (50 unit + 19 integration)
- Coverage for director_display.py: 65.40%

### Completion Notes List

- Created DirectorDisplayWidget with three collapsible perspective sections (Strategist, Analyst, Creative)
- Implemented unified strategy display showing objectives, actions, rationale, and confidence
- Added `<think>` tag extraction and visibility toggle for creative model reasoning
- Added STRATEGY_UPDATE event type to StreamEventType enum
- Integrated widget into CyberRedApp with F7 toggle and Ctrl+T for thinking visibility
- Created comprehensive TCSS styling matching "Command & Control" aesthetic
- Implemented degradation level display with warnings for unavailable models
- Created 50 unit tests covering all widget logic and parsing
- Created 19 integration tests covering real-time updates and edge cases

### File List

**New Files:**
- `src/cyberred/tui/widgets/director_display.py` - DirectorDisplayWidget implementation
- `tests/unit/tui/test_director_display.py` - Unit tests (69 tests)
- `tests/integration/tui/test_director_display_integration.py` - Integration tests (29 tests)

**Modified Files:**
- `src/cyberred/tui/widgets/__init__.py` - Export DirectorDisplayWidget, DirectorPerspective
- `src/cyberred/tui/app.py` - Add F7/Ctrl+T bindings, DirectorDisplayWidget to layout, strategy handler
- `src/cyberred/daemon/streaming.py` - Add STRATEGY_UPDATE event type
- `src/cyberred/tui/style.tcss` - Add Director widget TCSS styles

## Senior Developer Review (AI)

**Reviewer:** Rovo Dev (Code Review Agent)
**Date:** 2026-01-28
**Status:** APPROVED

### Issues Found and Fixed

1. **MEDIUM - Incomplete Type Annotation** (Fixed)
   - `extract_thinking_content` function signature didn't explicitly annotate `Optional[str]` for the `content` parameter
   - Fixed: Updated to `content: Optional[str]` with improved docstring

2. **MEDIUM - Low Test Coverage** (Fixed)
   - Original coverage: 65.40%
   - Added comprehensive unit tests for: `_render_unified_strategy()`, watch methods, `_update_display()`, perspective parsing edge cases
   - Added integration tests with Textual App context for DOM operations: `compose()`, `on_mount()`, collapsible section toggling
   - Final coverage: 99.65%

3. **LOW - Unreachable Branch** (Documented)
   - Line 325: `if alt.rationale:` branch is defensive code - the falsy branch is unreachable because `CreativeAlternative` dataclass validates rationale cannot be empty
   - Decision: Keep as defensive code for future-proofing; 99.65% coverage is acceptable

4. **VERIFIED - All Acceptance Criteria Implemented**
   - AC1: ✅ TUI displays all three perspectives (Strategist, Analyst, Creative)
   - AC2: ✅ Unified strategy section with synthesis
   - AC3: ✅ `<think>` tag toggle via Ctrl+T (debug mode)
   - AC4: ✅ Expand/collapse via actions and reactive properties
   - AC5: ✅ Real-time streaming via STRATEGY_UPDATE event
   - AC6: ✅ Integration tests verify rendering and updates

### Test Summary

- **98 tests total** (69 unit + 29 integration)
- All tests pass
- Coverage: 99.65% for director_display.py

### Code Quality

- Clean separation of concerns
- Proper use of Textual reactive properties
- Good error handling with graceful degradation
- TCSS styling matches "Command & Control" aesthetic
