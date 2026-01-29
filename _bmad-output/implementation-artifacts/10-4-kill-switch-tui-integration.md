# Story 10.4: Kill Switch TUI Integration

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **to trigger kill switch from TUI with <1s response**,
So that **I can halt all operations instantly (FR17, FR18, NFR2)**.

## Acceptance Criteria

1. **Given** engagement is running
2. **When** I press F10 or type `kill`
3. **Then** confirmation modal appears
4. **When** I confirm
5. **Then** kill switch triggers in <1s
6. **And** all agents halt immediately
7. **And** TUI shows "ENGAGEMENT FROZEN" status
8. **And** kill is logged to audit trail
9. **And** safety tests verify <1s response under 10K agent load

## Tasks / Subtasks

> [!IMPORTANT]
> **SAFETY-CRITICAL IMPLEMENTATION — RED-GREEN TDD METHODOLOGY REQUIRED**
> This story integrates the TUI with the safety-critical Kill Switch core (Story 1.9). Each task MUST follow strict TDD: Write failing tests FIRST (RED), then implement code to pass (GREEN), then refactor.
> ensure 100% code coverage. very critical.

### Phase 1: RED — Write Failing Tests First

- [x] Task 1: Create Test File Structure (AC: #9) <!-- id: 0 -->
  - [x] Create `tests/unit/tui/test_kill_switch_integration.py`
  - [x] Create `tests/integration/tui/test_kill_switch_tui.py`
  - [x] Create `tests/safety/tui/test_kill_switch_response_time.py`
  - [x] Import pytest, textual testing utilities, and KillSwitch from core
  - [x] Mark safety tests with `@pytest.mark.safety`

- [x] Task 2: Write Failing TUI KillSwitch Integration Tests (AC: #1-#5) <!-- id: 1 -->
  - [x] Test `CyberRedApp` has `_killswitch` attribute (KillSwitch instance)
  - [x] Test `action_panic()` calls `killswitch.trigger()` instead of just event bus publish
  - [x] Test `action_kill_switch_confirm()` shows confirmation modal (already exists, verify)
  - [x] Test confirmation modal "Yes" triggers actual `killswitch.trigger()`
  - [x] Test F10 binding shows confirmation modal
  - [x] Test ESC binding bypasses confirmation (direct panic)
  - [x] Test `kill` command in input triggers `action_kill_switch_confirm()`
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 3: Write Failing "ENGAGEMENT FROZEN" Status Tests (AC: #6, #7) <!-- id: 2 -->
  - [x] Test `StatusBarWidget` displays "FROZEN" state after kill switch triggers
  - [x] Test engagement state changes to `EngagementState.FROZEN` (new enum value)
  - [x] Test HiveGrid shows all agents in "frozen" status after kill
  - [x] Test "ENGAGEMENT FROZEN" message appears in kill chain log
  - [x] Test status bar turns red/danger color when frozen
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 4: Write Failing Audit Trail Tests (AC: #8) <!-- id: 3 -->
  - [x] Test kill switch trigger logs to audit trail via structlog
  - [x] Test audit log includes: `timestamp`, `issued_by`, `reason`, `duration_ms`
  - [x] Test audit log includes: `trigger_source` (F10, ESC, command)
  - [x] Test audit is written even if kill paths partially fail
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 5: Write Failing <1s Response Time Safety Tests (AC: #9) <!-- id: 4 -->
  - [x] Test `action_panic()` completes in <1s with mocked KillSwitch
  - [x] Test full TUI flow (F10 → confirm → kill) completes in <1.5s total
  - [x] Test ESC → immediate panic completes in <1s
  - [x] Test with simulated 10K agent status updates (async load)
  - [x] Test response time under concurrent auth request handling
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 6: Write Failing Daemon Mode Integration Tests (AC: #5, #6) <!-- id: 5 -->
  - [x] Test kill switch sends `KILL` command to daemon via IPC
  - [x] Test daemon acknowledges kill and broadcasts to all agents
  - [x] Test TUI receives `STATE_CHANGE` event with `FROZEN` state
  - [x] Test status bar updates from daemon state change event
  - [x] **Run tests — ALL FAILED (RED confirmed)**

### Phase 2: GREEN — Implement to Pass Tests

- [x] Task 7: Add FROZEN Engagement State (AC: #7) <!-- id: 6 -->
  - [x] Add `FROZEN = "FROZEN"` to `EngagementState` enum in `app.py`
  - [x] Add `$status-frozen` color token to `style.tcss` (use `$danger` / red)
  - [x] Update `StatusBarWidget.update_state()` to handle FROZEN state
  - [x] Add FROZEN state styling (bold red background)
  - [x] **Run Task 3 tests for state — PASSED (GREEN)**

- [x] Task 8: Integrate KillSwitch into CyberRedApp (AC: #1-#5) <!-- id: 7 -->
  - [x] Import `KillSwitch` from `cyberred.core.killswitch`
  - [x] Add `_killswitch: Optional[KillSwitch]` attribute to `CyberRedApp.__init__()`
  - [x] Initialize KillSwitch with redis_client and docker_client if available
  - [x] Pass engagement_id to KillSwitch constructor
  - [x] Update `action_panic()` to call `await self._killswitch.trigger()` if available
  - [x] Keep event bus publish as fallback for standalone mode
  - [x] **Run Task 2 tests — PASSED (GREEN)**

- [x] Task 9: Implement "ENGAGEMENT FROZEN" Status Display (AC: #6, #7) <!-- id: 8 -->
  - [x] Update `action_panic()` to set `self.engagement_state = EngagementState.FROZEN`
  - [x] Call `self._update_status_bar_state()` after kill trigger
  - [x] Add "ENGAGEMENT FROZEN" log entry to kill chain log
  - [x] Update all HiveGrid agents to "frozen" status
  - [x] Show notification: "ENGAGEMENT FROZEN - Kill switch activated"
  - [x] **Run Task 3 tests — PASSED (GREEN)**

- [x] Task 10: Implement Audit Trail Logging (AC: #8) <!-- id: 9 -->
  - [x] Add structlog logger to CyberRedApp for kill switch events
  - [x] Log kill switch trigger with: timestamp, issued_by, reason, source
  - [x] Log includes duration_ms from KillSwitch.trigger() result
  - [x] Log includes path results (redis, sigterm, docker)
  - [x] Ensure audit logged even on partial failure
  - [x] **Run Task 4 tests — PASSED (GREEN)**

- [x] Task 11: Add `kill` Command Handler (AC: #2) <!-- id: 10 -->
  - [x] Update `on_input_submitted()` to handle `kill` command
  - [x] `kill` command triggers `action_kill_switch_confirm()` (with modal)
  - [x] Add `kill!` command for immediate kill (bypass confirmation, like ESC)
  - [x] **Run Task 2 tests for command — PASSED (GREEN)**

- [x] Task 12: Implement Daemon Mode Kill Switch (AC: #5, #6) <!-- id: 11 -->
  - [x] Add `send_kill_command()` method to TUIClient
  - [x] Update `action_panic()` to use daemon client in daemon mode
  - [x] Handle `STATE_CHANGE` event with `FROZEN` state from daemon
  - [x] Update `_handle_state_change()` to set FROZEN state
  - [x] **Run Task 6 tests — PASSED (GREEN)**

### Phase 3: Safety Tests & Performance Validation

- [x] Task 13: Implement Safety Tests for <1s Response (AC: #9) <!-- id: 12 -->
  - [x] Create load generator for 10K simulated agent status updates
  - [x] Verify `action_panic()` returns in <1s under load
  - [x] Verify end-to-end TUI flow under <1.5s
  - [x] Test with concurrent auth request modal open
  - [x] Test with concurrent Director panel updates
  - [x] **Run Task 5 safety tests — PASSED (GREEN)**

- [x] Task 14: Integration Test Full Kill Switch Flow (AC: all) <!-- id: 13 -->
  - [x] Test F10 → confirmation → kill → FROZEN status → audit log
  - [x] Test ESC → immediate kill → FROZEN status → audit log
  - [x] Test `kill` command → confirmation → kill → FROZEN status
  - [x] Test daemon mode kill propagation
  - [x] Verify all agents show frozen status in HiveGrid
  - [x] **Run full integration tests — PASSED (GREEN)**

- [x] Task 15: Export and Documentation (AC: all) <!-- id: 14 -->
  - [x] Verify KillSwitchConfirmScreen export in `tui/screens/__init__.py`
  - [x] Add docstrings to all new methods
  - [x] Update BINDINGS docstring with kill switch details
  - [x] **Run all tests — ALL PASSED**
        critical; ensure100% code coverage
## Dev Notes

### Critical Requirements

**NFR2 Hard Requirement:** Kill switch MUST complete in <1s under 10K agent load. This is non-negotiable for operator safety.

**FR17:** Kill switch halts all operations immediately
**FR18:** Kill switch logs to audit trail
**NFR2:** <1s response time guarantee

### Existing Infrastructure (Story 1.9 + Story 9.1)

The kill switch core module is already implemented in Story 1.9:
- `src/cyberred/core/killswitch.py` - Tri-path kill switch (Redis, SIGTERM, Docker)
- `KillSwitch.trigger()` returns result dict with `duration_ms`
- `KillSwitch.is_frozen` property for checking frozen state
- Already tested for <1s response in `tests/safety/test_killswitch.py`

The TUI already has partial kill switch support from Story 9.1/9.11:
- `src/cyberred/tui/screens/kill_confirm.py` - Confirmation modal
- `action_panic()` - Currently only publishes to event bus
- `action_kill_switch_confirm()` - Shows confirmation modal
- F10 and ESC bindings configured

### Gap Analysis

**What's Missing:**
1. `action_panic()` doesn't call actual `KillSwitch.trigger()` - just publishes event
2. No "ENGAGEMENT FROZEN" status display (only RUNNING/PAUSED/STOPPED)
3. No audit trail logging from TUI
4. No `kill` command handling
5. Safety tests for TUI response time under load
6. Daemon mode integration (send kill to daemon, receive FROZEN state)

### Architecture Compliance

Per `architecture.md`:
- Kill switch is safety-critical (lines 88-95)
- Tri-path design: Redis pub/sub, SIGTERM, Docker API (lines 60-62)
- <1s timing budget (lines 296-304 of Story 1.9)
- Audit trail format: JSON-structured for structlog

### UX Design Compliance

Per `ux-design.md`:
- **Line 59:** Kill Switch <1s, always visible
- **Line 101:** ESC key (+ multi-path alternatives), always visible via sticky button
- **Line 208:** Kill Switch: `ESC` keyboard, Click [KILL] button mouse
- **Line 517:** `StickyKillButton` - Always-visible kill control
- **Line 543:** Destructive action style: `$danger` bg
- **Line 590:** Multi-path: `ESC` / `Ctrl+C` / `k` / `Ctrl+\` for tmux/screen compatibility

### File Locations

**Files to Modify:**
- `src/cyberred/tui/app.py` - Integrate KillSwitch, add FROZEN state
- `src/cyberred/tui/widgets/__init__.py` - Update StatusBarWidget for FROZEN
- `src/cyberred/tui/style.tcss` - Add FROZEN styling
- `src/cyberred/daemon/streaming.py` - Add FROZEN to StreamEventType if needed

**Files to Create:**
- `tests/unit/tui/test_kill_switch_integration.py`
- `tests/integration/tui/test_kill_switch_tui.py`
- `tests/safety/tui/test_kill_switch_response_time.py`

### Testing Standards

Per Story 1.9 patterns:
- Unit tests in `tests/unit/tui/`
- Integration tests in `tests/integration/tui/`
- Safety tests in `tests/safety/tui/` with `@pytest.mark.safety`
- 100% coverage requirement
- TDD: RED → GREEN → REFACTOR

### Previous Story Learnings (Story 10.3)

From Story 10.3 (Pending Authorization Queue):
- StatusBarWidget already handles `update_state()`, `update_pending_auth()`
- Use `NoMatches` exception handling for widget queries
- Daemon mode uses `_daemon_client` for IPC
- Event streaming via `_handle_stream_event()` router

### Anti-Patterns to Avoid

1. **NEVER** make kill switch async wait on user input after trigger
2. **NEVER** allow kill switch to take >1s (hard failure)
3. **NEVER** skip audit logging even on path failures
4. **NEVER** leave agents in non-frozen state after kill
5. **NEVER** require multiple confirmations for ESC (emergency path)
6. **NEVER** block TUI main thread during kill switch
7. **NEVER** ignore daemon mode - must propagate kill to daemon

### Complete Usage Flow

```
1. Operator sees issue → presses F10
2. Confirmation modal appears: "⚠️ KILL SWITCH ⚠️"
3. Operator presses Y to confirm
4. KillSwitch.trigger() called:
   - Frozen flag set immediately
   - Redis pub/sub broadcasts kill
   - SIGTERM sent to process group
   - Docker containers stopped
5. TUI updates:
   - EngagementState → FROZEN
   - StatusBar → "FROZEN" (red background)
   - HiveGrid → all agents show "frozen"
   - KillChainLog → "ENGAGEMENT FROZEN"
   - Notification → "ENGAGEMENT FROZEN - Kill switch activated"
6. Audit trail logged:
   {
     "event": "kill_switch_triggered",
     "timestamp": "2026-01-29T00:45:00Z",
     "issued_by": "operator",
     "source": "F10",
     "reason": "Operator initiated",
     "duration_ms": 245,
     "paths": {"redis": true, "sigterm": true, "docker": true}
   }
```

### Emergency ESC Path

ESC bypasses confirmation for true emergencies:
```
1. Operator sees critical issue → presses ESC
2. action_panic() called IMMEDIATELY (no modal)
3. KillSwitch.trigger() executes
4. All same updates as F10 confirmed path
5. Audit trail source = "ESC"
```

### Project Structure Notes

- Alignment with unified project structure: TUI components in `src/cyberred/tui/`
- Tests follow `tests/{unit,integration,safety}/tui/` pattern
- No conflicts detected with existing structure

### References

- [Source: _bmad-output/implementation-artifacts/1-9-kill-switch-core-tri-path.md] - Kill Switch Core implementation
- [Source: _bmad-output/planning-artifacts/architecture.md#kill-switch] - Architecture requirements
- [Source: _bmad-output/planning-artifacts/ux-design.md#lines-59-101-208-517-543-590] - UX specifications
- [Source: src/cyberred/tui/app.py] - Current TUI implementation
- [Source: src/cyberred/tui/screens/kill_confirm.py] - Existing confirmation modal
- [Source: tests/safety/test_killswitch.py] - Safety test patterns

### Epic 10 Integration Points

- **Story 10.1:** Authorization Request Modal - Kill switch should work even with auth modal open
- **Story 10.2:** Authorization Response Handling - Auth responses should fail gracefully if frozen
- **Story 10.3:** Pending Authorization Queue - Queue should be cleared/frozen on kill
- **Story 10.5:** Runtime Scope Adjustment - Scope editor should be disabled when frozen
- **Story 10.6:** Situational Awareness Alerts - Alerts should be dismissed on kill

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

N/A

### Completion Notes List

- Implemented FROZEN state in EngagementState enum (AC #7)
- Integrated KillSwitch into CyberRedApp with redis_client and docker_client parameters (AC #1-5)
- Updated action_panic() to call KillSwitch.trigger() with audit trail logging (AC #2, #5, #8)
- Added kill and kill! command handlers in on_input_submitted() (AC #2)
- Implemented FROZEN status display in StatusBarWidget with bold red styling (AC #7)
- Added send_kill_command() method to TUIClient for daemon mode (AC #5, #6)
- Updated _handle_state_change() to handle FROZEN state from daemon (AC #6)
- Added status-frozen CSS class to style.tcss
- Created comprehensive unit tests (20 tests, all passing)
- Created integration tests and safety tests for <1s response time

### File List

**New Files:**
- tests/unit/tui/test_kill_switch_integration.py
- tests/integration/tui/test_kill_switch_tui.py
- tests/safety/tui/test_kill_switch_response_time.py

**Modified Files:**
- src/cyberred/tui/app.py (added FROZEN state, KillSwitch integration, action_panic async, kill commands)
- src/cyberred/tui/daemon_client.py (added send_kill_command(), send_auth_response())
- src/cyberred/tui/widgets/__init__.py (added FROZEN to StatusBarWidget state colors)
- src/cyberred/tui/style.tcss (added status-frozen, status-active, status-auth_pending CSS classes)

