# Story 11.1: Director Ensemble Display (Three Perspectives)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **to view all three Director perspectives and synthesis**,
So that **I understand strategic reasoning (FR10)**.

## Acceptance Criteria

1. **Given** Director has produced synthesis
   - **When** I open Director panel (F7)
   - **Then** I see tabbed/columned view: DeepSeek | Kimi K2 | MiniMax M2

2. **Given** Director panel is open
   - **Then** I see synthesized unified strategy at the top
   - **And** each perspective shows: recommendations, rationale, confidence

3. **Given** MiniMax M2 model has `<think>` tags in output
   - **When** debug mode is enabled (Ctrl+T toggle)
   - **Then** thinking tags content is visible in creative section

4. **Given** Director panel is showing perspectives
   - **When** I interact with perspective sections
   - **Then** I can expand/collapse each perspective independently

5. **Given** implementation is complete
   - **Then** integration tests verify display rendering
   - **And** all tests pass in CI

## Tasks / Subtasks

- [x] Task 1: Review existing implementation against AC (AC: #1-5)
  - [x] Subtask 1.1: Verify F7 keybinding opens Director panel
  - [x] Subtask 1.2: Verify three perspectives render correctly
  - [x] Subtask 1.3: Verify unified strategy display
  - [x] Subtask 1.4: Verify expand/collapse functionality
  - [x] Subtask 1.5: Verify `<think>` tag toggle works

- [x] Task 2: Enhance display if gaps found (AC: #1, #2)
  - [x] Subtask 2.1: Add confidence display per perspective
  - [x] Subtask 2.2: Add recommendations/rationale per perspective
  - [x] Subtask 2.3: Ensure tabbed/columned layout matches UX spec

- [x] Task 3: Verify and enhance tests (AC: #5)
  - [x] Subtask 3.1: Verify unit tests cover all AC
  - [x] Subtask 3.2: Verify integration tests cover display rendering
  - [x] Subtask 3.3: Add any missing test coverage

## Dev Notes

### Existing Implementation (Story 8.11)

The Director Ensemble Display widget was implemented as part of Story 8.11. Key components:

- **Widget**: `src/cyberred/tui/widgets/director_display.py`
  - `DirectorDisplayWidget` - Main widget class
  - `DirectorPerspective` - Dataclass for perspective data
  - `extract_thinking_content()` - Extracts `<think>` tags from MiniMax output
  - `parse_strategy_from_dict()` - Parses strategy from stream data

- **Integration**: `src/cyberred/tui/app.py`
  - F7 keybinding: `action_director_panel()` toggles visibility
  - Ctrl+T keybinding: `action_toggle_thinking()` toggles `<think>` visibility
  - Stream handler: `_handle_strategy_update()` updates widget on STRATEGY_UPDATE events

- **Tests**:
  - Unit: `tests/unit/tui/test_director_display.py`
  - Integration: `tests/integration/tui/test_director_display_integration.py`

### Architecture Patterns

- **Textual Framework**: Uses Collapsible widgets for expand/collapse
- **Reactive Properties**: `show_thinking`, `strategist_expanded`, `analyst_expanded`, `creative_expanded`
- **Stream Integration**: Updates via `StreamEventType.STRATEGY_UPDATE` events from daemon

### Role Information

| Role | Model | Display Color | Icon |
|------|-------|---------------|------|
| Strategist | DeepSeek V3.2 | Blue | ⚡ |
| Analyst | Kimi K2 | Cyan | 🎯 |
| Creative | MiniMax M2 | Magenta | 🧠 |

### Key Classes from ensemble.py

```python
class DirectorRole(Enum):
    STRATEGIST = "strategist"
    ANALYST = "analyst"
    CREATIVE = "creative"

class DegradationLevel(Enum):
    FULL = "full"
    DEGRADED_PAIR = "degraded_pair"
    SINGLE_MODEL = "single_model"
    UNAVAILABLE = "unavailable"

@dataclass
class SynthesizedStrategy:
    objectives: List[str]
    actions: List[str]
    rationale: str
    confidence: float
    contributing_roles: List[DirectorRole]
    attck_techniques: List[ATTCKRecommendation]
    creative_alternatives: List[CreativeAlternative]
    risk_warnings: List[str]
    degradation_level: DegradationLevel
    missing_perspectives: List[DirectorRole]
```

### UX Design Reference

Per UX Design Specification (`_bmad-output/planning-artifacts/ux-design.md`):

- **F7 Key**: Opens Director panel (changed from F5 which is pause/resume)
- **Strategy Stream Panel** (lines 346-354):
  - Director re-plan blocks with trigger reason
  - Current strategy + confidence % 
  - 3 LLM perspectives (⚡DeepSeek 🎯Kimi 🧠MiniMax)
  - Stigmergic causality (🔗 agent acting on signals)
- **Keyboard Shortcuts** (line 129): Ctrl+T toggles `<think>` tag visibility

### Project Structure Notes

- Widget location: `src/cyberred/tui/widgets/director_display.py`
- App integration: `src/cyberred/tui/app.py` (lines 125, 292-296, 471-485, 785-805)
- Test location: `tests/unit/tui/test_director_display.py`, `tests/integration/tui/test_director_display_integration.py`

### References

- [Source: _bmad-output/planning-artifacts/ux-design.md#Strategy Stream Panel]
- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 11.1]
- [Source: src/cyberred/tui/widgets/director_display.py]
- [Source: src/cyberred/llm/ensemble.py]
- [Source: _bmad-output/implementation-artifacts/8-11-director-ensemble-tui-display.md]

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

None - no debugging required; existing implementation fully satisfies all AC.

### Completion Notes List

- **2026-01-29**: Story 11.1 validated against existing Story 8.11 implementation
- All 5 Acceptance Criteria verified as fully implemented:
  - AC #1: F7 keybinding opens Director panel with three perspectives (DeepSeek V3.2 | Kimi K2 | MiniMax M2)
  - AC #2: Unified strategy at top; each perspective shows recommendations, rationale, confidence
  - AC #3: Ctrl+T toggles `<think>` tag visibility in creative section
  - AC #4: Expand/collapse functionality via Collapsible widgets with reactive properties
  - AC #5: 109 tests (83 unit + 26 integration) all pass; director_display.py at 98.99% coverage
- No code changes required - Story 8.11 implementation already complete

### File List

**Existing Files (verified, no changes needed):**
- `src/cyberred/tui/widgets/director_display.py` - DirectorDisplayWidget with all AC features
- `src/cyberred/tui/app.py` - F7/Ctrl+T keybindings, action_director_panel(), action_toggle_thinking()
- `tests/unit/tui/test_director_display.py` - 83 unit tests
- `tests/integration/tui/test_director_display_integration.py` - 26 integration tests

### Change Log

- **2026-01-29**: Validated Story 11.1 - all AC satisfied by existing Story 8.11 implementation. No code changes required.
