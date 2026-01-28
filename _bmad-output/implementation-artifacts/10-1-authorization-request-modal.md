# Story 10.1: Authorization Request Modal

Status: review

## Story

As an **operator**,
I want **an interruptive modal for authorization requests**,
So that **I notice and respond to lateral movement and scope expansion requests (FR13, FR14)**.

## Acceptance Criteria

1. **Given** agent requests lateral movement or scope expansion
   **When** authorization request is created
   **Then** modal appears in TUI with context (target, action, risk)

2. **Given** authorization request is pending
   **When** modal is displayed
   **Then** modal is interruptive (pauses other actions until dismissed)
   **And** focus is trapped within modal (no interaction with background)

3. **Given** modal is displayed
   **When** I view the options
   **Then** modal shows Y/N/M/S options (Yes/No/More info/Skip for now)
   **And** keyboard shortcuts work: Y (approve), N (deny), M (more info), S (skip)

4. **Given** authorization request is created
   **When** I measure delivery time
   **Then** request delivery is <500ms from agent request to modal display (NFR5)

5. **Given** modal is displayed
   **When** I view the context
   **Then** swarm state snapshot is shown (agent distribution at request time)
   **And** related findings are summarized
   **And** risk assessment is displayed

6. **Given** modal is displayed
   **When** I view the requesting agent in Hive Matrix
   **Then** agent requesting auth bubbles to top via anomaly bubbling (Epic 9-4 integration)

7. **Given** authorization modal
   **When** I run integration tests
   **Then** all modal display and interaction tests pass
   **And** latency tests verify <500ms delivery

## Tasks / Subtasks

- [x] Task 1: Enhance AuthorizationModal screen (AC: #1, #2, #3)
  - [x] Migrate existing `AuthorizationModal` from `widgets/__init__.py` to `screens/authorization.py`
  - [x] Add Y/N/M/S keybindings per UX spec
  - [x] Implement focus trap (modal captures all input)
  - [x] Add blink animation for pending auth (1s cycle per UX spec)

- [x] Task 2: Add swarm state snapshot display (AC: #5)
  - [x] Create `SwarmStateSnapshot` component showing agent distribution
  - [x] Display count by status: idle, scanning, thinking, attacking, exploited
  - [x] Show timestamp of snapshot
  - [x] Display related findings summary (last 3-5 relevant findings)

- [x] Task 3: Add risk assessment context (AC: #5)
  - [x] Display target information (IP, hostname, discovered services)
  - [x] Show proposed action (lateral move target, scope expansion details)
  - [x] Display risk level indicator (LOW/MEDIUM/HIGH/CRITICAL)
  - [x] Show potential impact description

- [x] Task 4: Implement "More Info" (M) expansion (AC: #3)
  - [x] Add collapsible detail section
  - [x] Show full finding chain leading to request
  - [x] Display agent reasoning/decision context
  - [x] Show ATT&CK technique mapping if available

- [~] Task 5: Implement "Skip for now" (S) functionality (AC: #3)
  - [ ] Add request to pending queue (for Story 10.3) `[AI-Review: Queue declared but not used]`
  - [x] Dismiss modal without decision
  - [ ] Track skip count for auth timeout handling `[AI-Review: Not implemented]`

- [ ] Task 6: Integrate with anomaly bubbling (AC: #6) `[AI-Review: NOT IMPLEMENTED]`
  - [ ] Emit `AgentPriorityChanged` message when auth requested
  - [ ] Add `pending_authorization` as priority trigger
  - [ ] Verify agent bubbles to top in Hive Matrix

- [~] Task 7: Implement WebSocket push delivery (AC: #4)
  - [x] Create `AuthorizationRequestEvent` message type
  - [x] Integrate with daemon streaming (StreamEventType.AUTHORIZATION_REQUEST)
  - [ ] Measure and log delivery latency `[AI-Review: No latency measurement]`
  - [ ] Verify <500ms delivery time `[AI-Review: Not verified in tests]`

- [x] Task 8: Write unit tests (AC: #7)
  - [x] Test modal rendering with all context sections
  - [x] Test Y/N/M/S keybinding handlers
  - [x] Test focus trap behavior
  - [x] Test swarm snapshot population
  - [x] Test risk assessment display
  - [x] Achieve 100% coverage for `screens/authorization.py`

- [x] Task 9: Write integration tests (AC: #7)
  - [x] Test full auth request flow (agent → daemon → TUI → modal)
  - [ ] Test latency measurement (<500ms) `[AI-Review: Latency not measured]`
  - [ ] Test anomaly bubbling integration `[AI-Review: Not implemented]`
  - [x] Test modal dismiss and result propagation

## Dev Notes

### Existing Implementation

**IMPORTANT:** A basic `AuthorizationModal` already exists in `src/cyberred/tui/widgets/__init__.py` (lines 261-335). This story enhances it significantly per UX spec requirements.

**Current AuthorizationModal Features:**
- Basic modal with target and message display
- Three buttons: Approve, Always, Deny
- Callback pattern for result handling
- Basic CSS styling

**Gaps to Address (from UX Spec):**
1. **Y/N/M/S Options**: Current has Approve/Always/Deny → Need Y/N/M/S per UX spec
2. **Swarm State Snapshot**: Not implemented → Add agent distribution display
3. **Auth Batching**: Not implemented → "Approve all similar?" option
4. **Focus Trap**: Basic modal → Need explicit focus trap
5. **Blink Animation**: Not implemented → 1s cycle for pending auth
6. **Cooldown**: Not implemented → 3s cooldown on consecutive approvals
7. **Timeout**: Not implemented → Configurable timeout (default: 30min auto-deny)

### Architecture Patterns

**Screen vs Widget:**
The enhanced authorization modal should be a `ModalScreen` (current approach is correct) because:
- It needs to be interruptive (capture all input)
- It overlays the War Room
- Focus trap is built into ModalScreen

**Authorization Request Flow:**
```
Agent (requests auth)
    │
    ▼
Daemon (via EventBus)
    │
    ▼
StreamEventType.AUTHORIZATION_REQUEST
    │
    ▼
TUIClient._handle_stream_event()
    │
    ▼
CyberRedApp.handle_auth_request()
    │
    ▼
AuthorizationScreen.push() ← NEW (renamed from Modal)
    │
    ▼
Operator responds (Y/N/M/S)
    │
    ▼
Response sent via daemon socket
```

**File Location:**
- Move from: `src/cyberred/tui/widgets/__init__.py`
- Move to: `src/cyberred/tui/screens/authorization.py`
- Keep backward-compatible import in widgets for existing code

### UX Design References

**Critical UX Spec Sections:**
- **Lines 302-306**: Authorization Flow Y/N/M/S quick responses
  - Y (approve) / N (deny) / M (modify/more info) / S (skip)
- **Lines 510**: AuthorizationModal with swarm state snapshot, auth batching, 3s cooldown, timeout
- **Lines 562-563**: Modal overlay focus trap
- **Lines 604**: Blink animation for pending auth (1s cycle, persists until acknowledged)
- **Lines 539-545**: Action Hierarchy (Primary: accent bg, Destructive: danger bg)
- **Lines 569-573**: Input Patterns for authorization (instant response)

**Authorization Modal Requirements (UX Spec line 510):**
```
AuthorizationModal with:
- Y/N/M/S with full context display
- Swarm State Snapshot showing agent distribution at request time
- Auth batching ("Approve all similar?")
- 3s cooldown on consecutive approvals to prevent auth fatigue
- Configurable auth timeout (default: 30min auto-deny)
```

### Epic 9 Integration Points

| Component | Integration Type | Reference |
|-----------|------------------|-----------|
| **9-4 Anomaly Bubbling** | Agent requesting auth bubbles to top | `src/cyberred/tui/widgets/hive_matrix.py` |
| **9-6 Hive Matrix** | Filter bar support for `status:pending-auth` | Story 10-3 will add filter |
| **9-1 StatusBarWidget** | `[AUTH:n]` count display | Already implemented, call `update_pending_auth()` |
| **9-7 Daemon Socket Client** | Event streaming | `TUIClient` handles events |

**Anomaly Bubbling Integration:**
From Epic 9-4, anomaly bubbling uses priority scoring. Add `pending_authorization` as a priority trigger:
```python
# In hive_matrix.py bubble_priority calculation
PRIORITY_PENDING_AUTH = 100  # High priority - bubble to top
```

### File Structure

```
src/cyberred/tui/
├── screens/
│   ├── __init__.py
│   ├── authorization.py    # NEW - Enhanced AuthorizationScreen
│   ├── dropbox.py          # Existing
│   ├── help.py             # Existing
│   └── kill_confirm.py     # Existing
├── widgets/
│   ├── __init__.py         # Keep AuthorizationModal for backward compat
│   └── ...
└── app.py                  # Update to use new AuthorizationScreen
```

### Data Models

**AuthorizationRequest:**
```python
@dataclass
class AuthorizationRequest:
    id: str                    # Request UUID
    request_type: str          # "lateral_move" | "scope_expansion"
    agent_id: str              # Requesting agent
    target: str                # Target IP/hostname
    proposed_action: str       # What agent wants to do
    risk_level: str            # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    related_findings: List[Finding]  # Findings that led to this request
    decision_context: List[str]      # Stigmergic signals influencing
    timestamp: str             # ISO 8601 request time
    swarm_snapshot: SwarmSnapshot    # Agent distribution at request time
```

**SwarmSnapshot:**
```python
@dataclass
class SwarmSnapshot:
    timestamp: str
    total_agents: int
    by_status: Dict[str, int]  # {"idle": 10, "scanning": 50, ...}
    by_target: Dict[str, int]  # {"192.168.1.0/24": 30, ...}
```

**AuthorizationResponse:**
```python
@dataclass
class AuthorizationResponse:
    request_id: str
    decision: str              # "APPROVED" | "DENIED" | "SKIPPED"
    operator: str              # Who made decision
    timestamp: str             # ISO 8601
    constraints: Optional[Dict]  # time_limit, target_limit, etc.
    batch_apply: bool          # Apply to similar requests
```

### Testing Requirements

**Unit Tests (`tests/unit/tui/test_authorization_screen.py`):**
- Test screen initialization with AuthorizationRequest
- Test compose() returns expected widget structure
- Test Y/N/M/S keybinding handlers
- Test focus trap (no background interaction)
- Test swarm snapshot display
- Test risk level styling (colors per severity)
- Test "More Info" expansion toggle
- Test "Skip" adds to pending queue
- Test blink animation state
- Test cooldown timer (3s between approvals)
- Test timeout countdown display

**Integration Tests (`tests/integration/tui/test_authorization_flow.py`):**
- Test full flow: agent request → daemon event → TUI modal
- Test latency <500ms (NFR5 compliance)
- Test anomaly bubbling integration (agent priority change)
- Test response propagation back to daemon
- Test StatusBarWidget `[AUTH:n]` counter update
- Test modal dismiss and cleanup

**Safety Tests (`tests/safety/tui/test_authorization_safety.py`):**
- Test auth timeout auto-deny behavior
- Test rapid approval cooldown (prevent auth fatigue)
- Test audit logging of all decisions

### Dependencies

**Python Dependencies:**
- `textual>=0.40.0` (ModalScreen, focus trap)
- `asyncio` (stdlib - async handlers)

**Internal Dependencies:**
- `cyberred.core.models.Finding` - Finding data model
- `cyberred.daemon.streaming.StreamEventType` - Event types
- `cyberred.tui.daemon_client.TUIClient` - Daemon communication
- `cyberred.tui.widgets.hive_matrix.HiveMatrix` - Anomaly bubbling

### Previous Story Intelligence

**From Story 9-1 (Textual App Foundation):**
- `handle_auth_request()` already exists in `app.py` (line 474)
- `AuthorizationModal` is pushed via `self.push_screen()`
- Callback pattern sends response to daemon
- StatusBarWidget has `update_pending_auth()` method

**From Story 9-4 (Anomaly Bubbling):**
- Priority scoring system for agent bubbling
- `AgentPriorityChanged` message for priority updates
- Bubble algorithm in `HiveMatrix._calculate_priority()`

**From Epic 9 Retrospective:**
- AI-3 Action Item: "Define Anomaly Bubbling Priority for Auth Events — Add `pending_authorization` and `situational_alert` as priority triggers in bubbling algorithm"

### Implementation Checklist

- [ ] Create `src/cyberred/tui/screens/authorization.py`
- [ ] Define `AuthorizationScreen` class extending `ModalScreen`
- [ ] Implement Y/N/M/S keybindings
- [ ] Add swarm state snapshot component
- [ ] Add risk assessment display
- [ ] Implement "More Info" expansion
- [ ] Implement "Skip for now" with queue integration
- [ ] Add blink animation (CSS animation, 1s cycle)
- [ ] Implement 3s cooldown on consecutive approvals
- [ ] Add timeout countdown display
- [ ] Integrate with anomaly bubbling (emit priority change)
- [ ] Update `app.py` to use new screen
- [ ] Keep backward-compatible import in widgets
- [ ] Write comprehensive unit tests
- [ ] Write integration tests with latency validation
- [ ] Verify NFR5 compliance (<500ms delivery)

### Project Structure Notes

- Alignment: New screen follows established pattern at `src/cyberred/tui/screens/`
- Test structure mirrors source: `tests/unit/tui/`, `tests/integration/tui/`
- Safety tests in `tests/safety/tui/` per Epic 9 pattern

### References

- [Source: _bmad-output/planning-artifacts/ux-design.md#lines-302-306] - Y/N/M/S Authorization Flow
- [Source: _bmad-output/planning-artifacts/ux-design.md#lines-510] - AuthorizationModal spec
- [Source: _bmad-output/planning-artifacts/ux-design.md#lines-562-563] - Modal focus trap
- [Source: _bmad-output/planning-artifacts/ux-design.md#lines-604] - Blink animation
- [Source: _bmad-output/planning-artifacts/architecture.md#lines-686-690] - Event naming patterns
- [Source: _bmad-output/planning-artifacts/epics-stories.md#lines-4090-4114] - Original story definition
- [Source: _bmad-output/implementation-artifacts/epic-9-retro-2026-01-28.md#lines-99-107] - Epic 10 action items
- [Source: src/cyberred/tui/widgets/__init__.py#lines-261-335] - Existing AuthorizationModal
- [Source: src/cyberred/tui/app.py#lines-474-488] - Existing handle_auth_request

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4 (Rovo Dev)

### Debug Log References

### Completion Notes List

**[AI-Review 2026-01-28]** Code review completed. Found 10 issues (4 HIGH, 4 MEDIUM, 2 LOW):

**HIGH Issues:**
- H1: Story status was `ready-for-dev` but implementation exists → Fixed to `review`
- H2: File List was empty → Fixed below
- H3: Auth timeout feature NOT implemented (AC #5, UX Spec line 510 requires 30min auto-deny)
- H4: Anomaly bubbling NOT integrated (Task 6 - no `AgentPriorityChanged` emitted)

**MEDIUM Issues:**
- M1: Task checkboxes not updated → Fixed above
- M2: Skip queue declared but never used (`_pending_queue` in line 582)
- M3: Latency measurement not implemented (AC #4, NFR5)
- M4: Auth batching "Approve all similar?" not implemented

**LOW Issues:**
- L1: Widget imports could use `__all__`
- L2: Missing docstring for `_pending_queue` purpose

**Passing Tests:** 39 unit tests, 10 integration tests

**Remaining Work for Story Completion:**
1. Implement auth timeout (30min auto-deny countdown)
2. Implement anomaly bubbling integration (emit `AgentPriorityChanged`)
3. Add latency measurement and logging
4. Implement auth batching UI
5. Wire up `_pending_queue` for skip functionality

### File List

- src/cyberred/tui/screens/authorization.py (NEW - 790 lines)
- src/cyberred/tui/screens/__init__.py (MODIFIED - added AuthorizationScreen export)
- src/cyberred/tui/widgets/__init__.py (MODIFIED - backward compat import)
- src/cyberred/tui/app.py (MODIFIED - uses new AuthorizationScreen)
- tests/unit/tui/test_authorization_screen.py (NEW - 587 lines, 39 tests)
- tests/integration/tui/test_authorization_integration.py (NEW - 10 tests)

