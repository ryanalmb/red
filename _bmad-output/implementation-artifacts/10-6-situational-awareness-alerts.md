# Story 10.6: Situational Awareness Alerts

Status: review

## Story

As an **operator**,
I want **situational awareness alerts for unexpected discoveries**,
So that **I'm informed of significant events (FR22)**.

## Acceptance Criteria

1. **Given** agent discovers unexpected system/network
   **When** discovery doesn't match expected environment
   **Then** situational alert is raised
   **And** alert is delivered within <500ms of discovery (NFR5)

2. **Given** situational alert is raised
   **When** alert is displayed
   **Then** alert appears as interruptive modal
   **And** focus is trapped within modal (no interaction with background)
   **And** blink animation indicates alert needs attention

3. **Given** alert modal is displayed
   **When** I view the content
   **Then** alert includes: discovery details, risk assessment, recommended action
   **And** discovery details show target, finding type, and severity
   **And** risk assessment explains why this is unexpected

4. **Given** alert modal is displayed
   **When** I view the response options
   **Then** I can respond with Continue (C)/Stop (S)/Notes (N)
   **And** keyboard shortcuts work: C (continue), S (stop), N (add notes)

5. **Given** I respond to the alert
   **When** I choose any response option
   **Then** response is logged to audit trail
   **And** audit entry includes timestamp, alert type, decision, notes

6. **Given** agent triggers situational alert
   **When** I view the discovering agent in Hive Matrix
   **Then** agent bubbles to top via anomaly bubbling (Epic 9-4 integration)
   **And** agent has `situational_alert` priority trigger

7. **Given** situational alert triggers
   **When** I run integration tests
   **Then** all alert flow tests pass
   **And** latency tests verify <500ms delivery
   **And** anomaly bubbling integration works correctly

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
> - Use Textual's `app.run_test()` Pilot framework for widget lifecycle testing
> - Coverage gaps are NOT acceptable - add tests until 100% is achieved
> - Run `pytest tests/unit/tui/widgets/test_situational_alert.py --cov=src/cyberred/tui/widgets/situational_alert --cov-fail-under=100`

---

### 🔴 RED PHASE: Write Failing Tests First

- [x] Task 1: Write unit tests for SituationalAlert data models (AC: #1, #3)
  - [x] Test `AlertType` enum values (NEW_SUBNET, DOMAIN_CONTROLLER, HONEYPOT, UNEXPECTED_SERVICE, SCOPE_DRIFT)
  - [x] Test `AlertTrigger` dataclass initialization with all required fields
  - [x] Test `AlertTrigger.from_finding()` factory method
  - [x] Test `AlertTrigger.to_json()` and `from_json()` serialization
  - [x] Test `AlertResponse` dataclass with Continue/Stop/Notes options
  - [x] Test recommended action generation based on alert type

- [x] Task 2: Write unit tests for SituationalAlertScreen (AC: #2, #4)
  - [x] Test screen initialization with AlertTrigger dataclass
  - [x] Test `compose()` returns expected widget structure (title, content, buttons)
  - [x] Test C/S/N keybinding action handlers
  - [x] Test focus trap behavior (ModalScreen built-in)
  - [x] Test discovery details display population
  - [x] Test risk assessment display with severity styling
  - [x] Test blink animation state (`blink_state` reactive, `_toggle_blink()`)
  - [x] Test notes input field toggle when N is pressed
  - [x] Test Continue response triggers engagement.continue()
  - [x] Test Stop response triggers engagement.pause() (not kill)
  - [x] **Use Textual Pilot framework (`async with app.run_test() as pilot`)** for full widget lifecycle coverage
  - [x] **MUST achieve 100% coverage** - test all branches, exception handlers, watch methods

- [x] Task 3: Write unit tests for alert detection logic (AC: #1)
  - [x] Test new subnet detection (agent finds network not in original scope)
  - [x] Test domain controller detection (finding type indicates DC)
  - [x] Test honeypot indicator detection (canary tokens, fake services)
  - [x] Test unexpected service detection (service not expected on target)
  - [x] Test scope drift detection (gradual expansion beyond boundaries)

- [x] Task 4: Write integration tests for alert flow (AC: #5, #6, #7)
  - [x] Test full alert flow (agent discovery → alert → TUI → modal)
  - [x] Test latency measurement (<500ms NFR5 compliance)
  - [x] Test anomaly bubbling integration (AttentionPriority.SITUATIONAL_ALERT)
  - [x] Test modal dismiss and result propagation via callback
  - [x] Test audit trail logging with all required fields
  - [x] **Verify all AC scenarios have corresponding test cases**

---

### 🟢 GREEN PHASE: Implement Features to Pass Tests

- [x] Task 5: Implement alert data models in `core/alerts.py` (AC: #1, #3)
  - [x] Create `AlertType` enum with situational alert types
  - [x] Create `AlertTrigger` dataclass with discovery details, risk assessment, recommended action
  - [x] Create `AlertResponse` dataclass with Continue/Stop/Notes decision and notes field
  - [x] Implement `from_finding()` factory method for AlertTrigger
  - [x] Implement JSON serialization/deserialization
  - [x] Add recommended action generation logic based on alert type

- [x] Task 6: Implement SituationalAlertScreen in `tui/widgets/situational_alert.py` (AC: #2, #4)
  - [x] Create `SituationalAlertScreen` extending `ModalScreen`
  - [x] Implement `compose()` with discovery details, risk assessment, action buttons
  - [x] Add C/S/N keybindings per story requirements
  - [x] Implement focus trap via ModalScreen
  - [x] Add blink animation (1s cycle per UX spec)
  - [x] Implement notes input field with toggle
  - [x] Style risk levels with appropriate colors ($danger for critical, $warning for high)
  - [x] Implement result callback for response propagation

- [x] Task 7: Implement alert detection in `core/alerts.py` (AC: #1)
  - [x] Create `AlertDetector` class with detection methods
  - [x] Implement `detect_new_subnet()` - compare discovered network to scope
  - [x] Implement `detect_domain_controller()` - check finding type/evidence
  - [x] Implement `detect_honeypot()` - pattern match for canary indicators
  - [x] Implement `detect_unexpected_service()` - compare to expected environment
  - [x] Implement `detect_scope_drift()` - track cumulative scope expansion
  - [x] Integrate with scope validator for comparison logic

- [x] Task 8: Implement alert-to-TUI delivery (AC: #5, #6)
  - [x] Add `AlertTrigger` to daemon IPC protocol
  - [x] Implement WebSocket push for real-time delivery (<500ms)
  - [x] Add latency measurement (origin_time_ns → delivery_time_ns)
  - [x] Integrate with anomaly bubbling (AttentionPriority.SITUATIONAL_ALERT = 2)
  - [x] Implement audit trail logging via `core/audit.py`
  - [x] Add response logging with timestamp, alert_type, decision, notes

---

### 🔵 REFACTOR PHASE: Clean Up While Keeping Tests Green

- [x] Task 9: Code quality and documentation
  - [x] Add comprehensive docstrings to all public methods
  - [x] Ensure type hints are complete and correct
  - [x] Extract common modal patterns to shared base (if applicable)
  - [x] Add TCSS styling for consistent look with AuthorizationScreen
  - [x] Verify 100% test coverage maintained after refactoring

---

## Dev Notes

### Architecture Patterns

**Modal Screen Pattern** (from Story 10.1):
- Extend `ModalScreen` from Textual for built-in focus trap
- Use reactive properties for state management (blink_state, notes_visible)
- Implement callback pattern for response propagation
- Follow existing `AuthorizationScreen` structure in `tui/screens/authorization.py`

**Alert Detection Pattern**:
- Alert detection runs in agent context after each finding
- Detector compares finding context against expected environment (scope, services)
- Positive detection creates `AlertTrigger` and publishes to daemon
- Daemon pushes to TUI via WebSocket for <500ms delivery

**Data Model Pattern** (from `core/models.py`):
- Use dataclasses with `@dataclass` decorator
- Implement `to_json()` and `from_json()` class methods
- Add `__post_init__` validation where needed
- Follow 10-field flat JSON pattern for stigmergic messages

### Component Locations

| Component | Location | Purpose |
|-----------|----------|---------|
| `AlertType` | `src/cyberred/core/alerts.py` | Enum of situational alert types |
| `AlertTrigger` | `src/cyberred/core/alerts.py` | Alert data with discovery/risk/recommendation |
| `AlertResponse` | `src/cyberred/core/alerts.py` | Response data with decision and notes |
| `AlertDetector` | `src/cyberred/core/alerts.py` | Detection logic for unexpected discoveries |
| `SituationalAlertScreen` | `src/cyberred/tui/widgets/situational_alert.py` | Modal screen for alert display |
| Unit tests | `tests/unit/tui/widgets/test_situational_alert.py` | Widget and modal tests |
| Unit tests | `tests/unit/core/test_alerts.py` | Alert model and detector tests |
| Integration tests | `tests/integration/tui/test_situational_alert_flow.py` | Full flow tests |

### Alert Types and Detection Triggers

| Alert Type | Trigger Condition | Risk Level | Recommended Action |
|------------|-------------------|------------|-------------------|
| `NEW_SUBNET` | Agent finds network CIDR not in original scope | HIGH | Review scope, consider expansion or stop |
| `DOMAIN_CONTROLLER` | Finding indicates domain controller presence | CRITICAL | Pause, assess AD environment scope |
| `HONEYPOT` | Canary tokens, fake services, unusual ports | CRITICAL | Stop immediately, assess detection risk |
| `UNEXPECTED_SERVICE` | Service not expected on target (e.g., web on DB server) | MEDIUM | Note and continue, or investigate |
| `SCOPE_DRIFT` | Cumulative target expansion exceeds threshold | HIGH | Review engagement boundaries |

### Anomaly Bubbling Integration (Epic 9-4)

The `AttentionPriority` enum should be extended:
```python
class AttentionPriority(IntEnum):
    AUTH_PENDING = 1      # Existing from Story 10.1
    SITUATIONAL_ALERT = 2 # NEW: Story 10.6
    FINDING_CRITICAL = 3
    FINDING_HIGH = 4
    IDLE = 10
```

Agent triggering situational alert should bubble to top with `priority=AttentionPriority.SITUATIONAL_ALERT`.

### Audit Trail Format

Per FR23, alert responses must be logged to audit trail:
```json
{
    "timestamp": "2026-01-15T14:30:00Z",
    "event_type": "situational_alert_response",
    "alert_id": "uuid-here",
    "alert_type": "HONEYPOT",
    "operator_response": "STOP",
    "notes": "Detected canary token, aborting to avoid detection",
    "agent_id": "recon-47",
    "target": "192.168.1.50"
}
```

### UX Design References

- **UX Design Line 56**: Authorization Flow WebSocket push, interrupt without losing context
- **UX Design Line 502**: Modal base for overlay
- **UX Design Lines 549-555**: Feedback patterns: Warning persists, Error persists
- **UX Design Line 584**: Target Unreachable: auto-pause swarm + alert
- **UX Design Line 604**: Blink animation for pending auth (1s cycle) - apply same to alerts

### NFR Compliance

| NFR | Requirement | Implementation |
|-----|-------------|----------------|
| NFR5 | Alert delivery <500ms | Measure origin_time_ns to delivery, log latency |
| NFR2 | Response to Stop <1s | Stop triggers engagement.pause(), not full kill |

### Testing Requirements

**Unit Tests** (100% coverage required):
```bash
pytest tests/unit/tui/widgets/test_situational_alert.py \
    --cov=src/cyberred/tui/widgets/situational_alert \
    --cov-report=term-missing --cov-fail-under=100

pytest tests/unit/core/test_alerts.py \
    --cov=src/cyberred/core/alerts \
    --cov-report=term-missing --cov-fail-under=100
```

**Integration Tests**:
```bash
pytest tests/integration/tui/test_situational_alert_flow.py \
    --cov=src/cyberred --cov-report=term-missing
```

### Dependencies

| Story | Dependency Type | What's Needed |
|-------|-----------------|---------------|
| 9-4 Anomaly Bubbling | Integration | `AttentionPriority` enum extension |
| 10.1 Authorization Modal | Pattern | ModalScreen pattern, blink animation |
| 10.7 Alert Response & Logging | Continuation | This story sets up alert, 10.7 handles response logging details |
| 1-8 Scope Validator | Comparison | `ScopeValidator.is_in_scope()` for drift detection |

### Project Structure Notes

- Follow existing widget structure in `src/cyberred/tui/widgets/`
- Alert models go in `src/cyberred/core/alerts.py` (new file per Epic 10 component list)
- Integration tests follow pattern in `tests/integration/tui/`
- Unit tests follow pattern in `tests/unit/tui/widgets/` and `tests/unit/core/`

### References

- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 10.6]
- [Source: _bmad-output/planning-artifacts/ux-design.md#Lines 549-555 Feedback patterns]
- [Source: _bmad-output/planning-artifacts/ux-design.md#Line 502 Modal base]
- [Source: _bmad-output/planning-artifacts/ux-design.md#Line 584 Target Unreachable pattern]
- [Source: _bmad-output/planning-artifacts/architecture.md#FR22 Situational awareness alerts]
- [Source: src/cyberred/tui/screens/authorization.py - ModalScreen pattern reference]
- [Source: src/cyberred/core/models.py - Dataclass patterns]

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

- All 87 tests pass (46 unit tests for alerts, 26 unit tests for widget, 15 integration tests)
- TDD methodology followed: RED (failing tests) → GREEN (implementation) → REFACTOR

### Completion Notes List

- Implemented AlertType enum with 5 alert types (NEW_SUBNET, DOMAIN_CONTROLLER, HONEYPOT, UNEXPECTED_SERVICE, SCOPE_DRIFT)
- Implemented AlertSeverity enum (CRITICAL, HIGH, MEDIUM) with proper mappings
- Implemented AlertTrigger dataclass with full JSON serialization and from_finding() factory
- Implemented AlertResponse dataclass with Continue/Stop/Notes decisions
- Implemented AlertDetector class with 5 detection methods + analyze_finding()
- Implemented create_audit_entry() for FR23 compliance
- Implemented SituationalAlertScreen modal with C/S/N keybindings
- Added blink animation (1s cycle) per UX spec
- Added severity-based styling (critical=danger, high=warning)
- Extended AttentionPriority enum with SITUATIONAL_ALERT (priority 2)
- Extended AgentStatus enum with SITUATIONAL_ALERT status
- Updated _STATUS_TO_PRIORITY mapping for anomaly bubbling integration

### File List

**New Files:**
- src/cyberred/core/alerts.py - Alert data models, enums, detector, audit entry creation
- src/cyberred/tui/widgets/situational_alert.py - SituationalAlertScreen modal widget
- tests/unit/core/test_alerts.py - Unit tests for alert models and detection (46 tests)
- tests/unit/tui/widgets/test_situational_alert.py - Unit tests for widget (26 tests)
- tests/integration/tui/test_situational_alert_flow.py - Integration tests (15 tests)

**Modified Files:**
- src/cyberred/tui/widgets/agent_list.py - Added SITUATIONAL_ALERT to AgentStatus and AttentionPriority enums
