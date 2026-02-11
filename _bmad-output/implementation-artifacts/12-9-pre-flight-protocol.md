# Story 12.9: Pre-Flight Protocol

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **drop box pre-flight validation before operations**,
So that **I confirm the drop box is functional before commencing the objective (FR26)**.

## Acceptance Criteria

1. **Given** drop box connects to C2
   - **When** pre-flight is initiated
   - **Then** sequence runs deterministically: PING → EXEC_TEST → STREAM_TEST → NET_ENUM → READY
   - **And** each step completes or times out within 10 seconds

2. **Given** PING step executes
   - **When** drop box responds
   - **Then** RTT latency is measured and recorded
   - **And** latency value is available for display

3. **Given** EXEC_TEST step executes
   - **When** a benign command is sent to the drop box
   - **Then** drop box executes the command and returns the result
   - **And** result is validated (non-empty, successful)

4. **Given** STREAM_TEST step executes
   - **When** bidirectional streaming is tested
   - **Then** data flows from server→drop box and drop box→server
   - **And** streaming integrity is confirmed

5. **Given** NET_ENUM step executes
   - **When** network enumeration runs on the drop box
   - **Then** local network interfaces are discovered and returned
   - **And** network info is stored for engagement context

6. **Given** all steps pass
   - **When** READY state is reached
   - **Then** drop box is marked READY for operations
   - **And** TUI displays: "Drop box connected. Pre-flight passed. Ready for objective."

7. **Given** any step fails or times out
   - **When** pre-flight cannot complete
   - **Then** drop box is marked NOT READY
   - **And** failure reason and failed step are reported
   - **And** TUI displays the specific failure

8. **Given** pre-flight results are available
   - **When** displayed in TUI
   - **Then** each step shows: status (pass/fail/timeout), duration, and details
   - **And** overall pre-flight status is shown prominently

9. **Given** pre-flight implementation
   - **When** integration tests run
   - **Then** full pre-flight sequence is verified with mock drop box
   - **And** timeout behavior is tested
   - **And** partial failure scenarios are tested

**⚠️ CRITICAL: Test-Driven Development (TDD) Required**

> This story MUST follow strict TDD methodology:
> 1. **RED Phase**: Write failing tests FIRST before any implementation
> 2. **GREEN Phase**: Write minimal code to make tests pass
> 3. **REFACTOR Phase**: Clean up code while keeping tests green
>
> **🎯 COVERAGE REQUIREMENT**
> - All new code MUST achieve 100% test coverage
> - Run targeted coverage checks per file/module

## Tasks / Subtasks

- [ ] Task 1: Create `PreFlightStep` enum and `PreFlightResult` dataclasses (AC: #1, #6, #7)
  - [ ] 1.1 Define `PreFlightStep` enum: `PING`, `EXEC_TEST`, `STREAM_TEST`, `NET_ENUM`, `READY`
  - [ ] 1.2 Define `PreFlightStepResult` dataclass: step, status (pass/fail/timeout), duration_ms, details, error
  - [ ] 1.3 Define `PreFlightResult` dataclass: overall status (READY/NOT_READY), step_results list, total_duration_ms, drop_box_id, timestamp
  - [ ] 1.4 Define `PreFlightStatus` enum: `READY`, `NOT_READY`, `IN_PROGRESS`, `NOT_STARTED`
  - [ ] 1.5 Write unit tests for all data models

- [ ] Task 2: Implement `PreFlightProtocol` class with step execution (AC: #1, #2, #3, #4, #5)
  - [ ] 2.1 Create `PreFlightConfig` dataclass with `step_timeout_seconds: int = 10`
  - [ ] 2.2 Implement `PreFlightProtocol.__init__(config, c2_server, event_bus)` with dependency injection
  - [ ] 2.3 Implement `async run_preflight(drop_box_id) -> PreFlightResult` orchestrator that executes steps sequentially
  - [ ] 2.4 Implement `async _execute_ping(drop_box_id) -> PreFlightStepResult` — sends ping, measures RTT
  - [ ] 2.5 Implement `async _execute_exec_test(drop_box_id) -> PreFlightStepResult` — sends benign command (`echo preflight_test`), validates response
  - [ ] 2.6 Implement `async _execute_stream_test(drop_box_id) -> PreFlightStepResult` — tests bidirectional data flow
  - [ ] 2.7 Implement `async _execute_net_enum(drop_box_id) -> PreFlightStepResult` — requests network interface enumeration
  - [ ] 2.8 Implement per-step `asyncio.wait_for` with 10s timeout, catching `asyncio.TimeoutError`
  - [ ] 2.9 Implement fail-fast: if any step fails/times out, mark remaining steps as SKIPPED, return NOT_READY
  - [ ] 2.10 Write unit tests for each step executor (passing and failing scenarios)
  - [ ] 2.11 Write unit tests for the orchestrator (full pass, each step failing, timeout)

- [ ] Task 3: Integrate with C2 protocol message layer (AC: #2, #3, #4, #5)
  - [ ] 3.1 Add `PREFLIGHT` type to `C2MessageType` enum or use existing `COMMAND` type with preflight-specific command names
  - [ ] 3.2 Define preflight command payloads: `preflight_ping`, `preflight_exec`, `preflight_stream`, `preflight_net_enum`
  - [ ] 3.3 Implement message send/receive via `C2Server` WebSocket connection for each step
  - [ ] 3.4 Write unit tests for message construction and parsing

- [ ] Task 4: Integrate with EventBus for pre-flight events (AC: #1, #6, #7)
  - [ ] 4.1 Publish `c2.preflight.started` event when pre-flight begins
  - [ ] 4.2 Publish `c2.preflight.step_completed` event after each step (with step name, status, duration)
  - [ ] 4.3 Publish `c2.preflight.completed` event with overall result (READY/NOT_READY)
  - [ ] 4.4 Write unit tests for event publishing

- [ ] Task 5: TUI pre-flight display (AC: #8)
  - [ ] 5.1 Add pre-flight status fields to `DropBoxStatus` dataclass in `dropbox_status.py`
  - [ ] 5.2 Update `DropBoxStatusPanel` to display pre-flight step results (checklist-style: ✅/❌/⏳ per step)
  - [ ] 5.3 Display overall pre-flight status message: "Pre-flight passed. Ready for objective." or failure details
  - [ ] 5.4 Write unit tests for TUI widget updates

- [ ] Task 6: Update module exports (AC: all)
  - [ ] 6.1 Update `src/cyberred/c2/__init__.py` with new exports: `PreFlightProtocol`, `PreFlightConfig`, `PreFlightStep`, `PreFlightStepResult`, `PreFlightResult`, `PreFlightStatus`
  - [ ] 6.2 Write import tests

- [ ] Task 7: Integration tests (AC: #9)
  - [ ] 7.1 Write integration test: full pre-flight pass with mock drop box responding to all steps
  - [ ] 7.2 Write integration test: PING timeout → NOT_READY, remaining steps SKIPPED
  - [ ] 7.3 Write integration test: EXEC_TEST fails → NOT_READY
  - [ ] 7.4 Write integration test: STREAM_TEST bidirectional verification
  - [ ] 7.5 Write integration test: NET_ENUM returns network interface data
  - [ ] 7.6 Write integration test: partial failure (e.g., NET_ENUM fails after others pass)

## Dev Notes

### Architecture Context

- **FR26** (PRD line 1244): "System can execute deterministic pre-flight protocol (PING→EXEC_TEST→STREAM_TEST→NET_ENUM→READY)"
- **FR29** (PRD line 1247): "Drop box can relay commands to target network and stream results back" — validates STREAM_TEST capability
- **Architecture lines 437-453**: Pre-flight validation pattern (note: that section covers *system-level* pre-flight for engagements; Story 12.9 is the *drop box* pre-flight which uses the specific PING→EXEC_TEST→STREAM_TEST→NET_ENUM→READY sequence from the PRD)
- **PRD lines 188-204**: Detailed pre-flight step descriptions and TUI display requirements
- **Timeout**: 10s per step (per epics-stories.md Technical Notes)
- **Failure policy**: Fail on any step → drop box marked NOT READY (fail-fast, skip remaining steps)

### Existing Code Patterns (MUST follow)

All new code MUST follow these patterns from the existing C2 module:

1. **Dataclass-based configs**: Use `@dataclass` for `PreFlightConfig` (see `HeartbeatMonitorConfig`, `C2ServerConfig`, `CertManagerConfig`)
2. **Enum-based states**: Use `Enum` for `PreFlightStep` and `PreFlightStatus` (see `C2MessageType`, `ConnectionStatus`)
3. **Async patterns**: All step execution must be `async def` with `asyncio.wait_for` for timeouts (see `HeartbeatMonitor.start()`, `C2Server.start()`)
4. **Structured logging**: Use `structlog.get_logger()` with contextual key-value pairs (see all C2 modules)
5. **EventBus integration**: Publish events via `EventBus` with TYPE_CHECKING guard (see `HeartbeatMonitor._publish_event()`)
6. **Dependency injection**: Accept `C2Server`, `EventBus` as constructor parameters (see `HeartbeatMonitor.__init__`)
7. **Module exports**: Update `__init__.py` `__all__` list (see current `c2/__init__.py`)

### Source Tree — Files to Create

| File | Purpose |
|------|---------|
| `src/cyberred/c2/preflight.py` | **[NEW]** Pre-flight protocol implementation: `PreFlightStep`, `PreFlightStepResult`, `PreFlightResult`, `PreFlightStatus`, `PreFlightConfig`, `PreFlightProtocol` |
| `tests/unit/c2/test_preflight.py` | **[NEW]** Unit tests for all data models and step executors |
| `tests/integration/c2/test_preflight.py` | **[NEW]** Integration tests for full pre-flight sequence |

### Source Tree — Files to Modify

| File | Change |
|------|--------|
| `src/cyberred/c2/__init__.py` | Add new exports for preflight classes |
| `src/cyberred/c2/protocol.py` | Potentially add preflight command constants (or keep as string commands) |
| `src/cyberred/tui/widgets/dropbox_status.py` | Add pre-flight status fields to `DropBoxStatus`, update panel display |
| `src/cyberred/tui/screens/dropbox.py` | Display pre-flight results on screen |

### Previous Story Learnings (from 12-8)

- Story 12-8 implemented NL drop box setup with `DeploymentPlan` dataclass, `DropBoxDeploymentInterpreter`, `InterpretationError`, platform validation
- Pattern: standalone module file + update `__init__.py` exports + comprehensive unit tests
- All C2 modules use `from __future__ import annotations` at top
- Type hints use `Optional` from typing and string-quoted forward references for circular imports
- Test files use pytest fixtures via `conftest.py` at `tests/unit/c2/conftest.py`
- Mock external dependencies (C2Server connections) — never require real WebSocket connections in unit tests

### Testing Strategy

- **Unit tests**: Mock `C2Server` WebSocket sends/receives. Test each step independently. Test orchestrator with mocked step methods. Test timeouts with manual `asyncio.sleep` mocks.
- **Integration tests**: Use mock drop box (simulated WebSocket endpoint) that responds to preflight commands. Test full sequence, partial failures, timeouts.
- **Coverage target**: 100% for `preflight.py`
- **PRD line 250**: "Mock drop box environment in CI for automated testing without physical hardware"

### Key Implementation Notes

1. **Sequential execution**: Steps MUST execute in order PING→EXEC_TEST→STREAM_TEST→NET_ENUM. Do NOT parallelize.
2. **READY is not a step to execute**: READY is the final state when all 4 steps pass. It is the result, not an action.
3. **RTT measurement**: PING step should capture `time.monotonic()` before sending and after receiving response. Store as `latency_ms: int` in step result.
4. **Benign command example**: EXEC_TEST should use something like `echo preflight_test` or equivalent that proves command execution works without side effects.
5. **Stream test**: Send known data payload in both directions, verify integrity (e.g., hash match).
6. **Network enumeration**: Request `ip addr` / `ifconfig` equivalent output, parse into structured format.
7. **TUI display**: Show checklist-style progress during pre-flight: `⏳ PING...` → `✅ PING (45ms)` → `⏳ EXEC_TEST...`

## Story Progress Notes

### Agent Model Used: TBD
### Completion Notes: TBD
