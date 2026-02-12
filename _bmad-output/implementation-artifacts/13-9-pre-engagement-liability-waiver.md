# Story 13.9: Pre-Engagement Liability Waiver

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **pre-engagement liability waiver workflow**,
So that **legal requirements are documented before engagement starts (FR54)**.

## Acceptance Criteria

1. **Given** new engagement is being created
2. **When** engagement init runs
3. **Then** waiver prompt appears with legal text
4. **And** operator must acknowledge (checkbox + signature)
5. **And** acknowledgment is timestamped and logged to audit trail
6. **And** engagement cannot start without waiver completion
7. **And** waiver text is configurable per organization
8. **And** integration tests verify waiver enforcement

## Tasks / Subtasks

> [!IMPORTANT]
> **RED-GREEN TDD METHODOLOGY REQUIRED**
> Each task MUST follow strict TDD: Write failing tests FIRST (RED), then implement code to pass (GREEN), then refactor.

### Phase 0: Prerequisites

- [ ] Task 0: Verify Dependencies (PREREQUISITE) <!-- id: prereq -->
  - [ ] Verify Story 13.2 (Append-Only Audit Log) is complete
  - [ ] Verify `OperatorAuditLog` is available in `storage/operator_audit.py`
  - [ ] Verify `OperatorAction` enum includes required actions
  - [ ] Verify Textual TUI framework is available
  - [ ] Verify `SessionManager` in `daemon/session_manager.py` exists
  - [ ] Run: `python -c "from cyberred.storage.operator_audit import OperatorAuditLog, OperatorAction"`
  - [ ] Run: `python -c "from cyberred.daemon.session_manager import SessionManager"`
  - [ ] Run: `python -c "from textual.screen import ModalScreen"`

### Phase 1: RED — Write Failing Tests First

- [ ] Task 1: Create Test File Structure (AC: #8) <!-- id: 0 -->
  - [ ] Create `tests/unit/tui/screens/test_waiver.py`
  - [ ] Import pytest, Textual testing utilities
  - [ ] Create fixture for waiver configuration with legal text
  - [ ] Create fixture for waiver configuration with custom org text
  - [ ] Create fixture for engagement config dict
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 2: Write Failing WaiverScreen Class Tests (AC: #1, #3) <!-- id: 1 -->
  - [ ] Test `WaiverScreen.__init__(waiver_text, org_name)` initializes correctly
  - [ ] Test waiver screen displays legal text in scrollable container
  - [ ] Test waiver screen displays organization name
  - [ ] Test waiver screen displays checkbox for acknowledgment
  - [ ] Test waiver screen displays signature input field
  - [ ] Test waiver screen displays "Accept" and "Decline" buttons
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 3: Write Failing Waiver Validation Tests (AC: #4) <!-- id: 2 -->
  - [ ] Test "Accept" button disabled when checkbox unchecked
  - [ ] Test "Accept" button disabled when signature empty
  - [ ] Test "Accept" button disabled when signature is whitespace only
  - [ ] Test "Accept" button enabled when checkbox checked AND signature provided
  - [ ] Test "Decline" button always enabled
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 4: Write Failing Waiver Acceptance Tests (AC: #4, #5) <!-- id: 3 -->
  - [ ] Test clicking "Accept" returns WaiverAcceptance dataclass
  - [ ] Test WaiverAcceptance contains: accepted=True, signature, timestamp
  - [ ] Test timestamp is UTC ISO format
  - [ ] Test signature matches input text
  - [ ] Test waiver hash is SHA-256 of waiver text
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 5: Write Failing Waiver Decline Tests (AC: #6) <!-- id: 4 -->
  - [ ] Test clicking "Decline" returns WaiverAcceptance with accepted=False
  - [ ] Test decline does not require signature
  - [ ] Test decline includes timestamp
  - [ ] Test decline does not create waiver hash
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 6: Write Failing Waiver Config Loading Tests (AC: #7) <!-- id: 5 -->
  - [ ] Test `load_waiver_config(config_path)` reads YAML config
  - [ ] Test default waiver text if file not found
  - [ ] Test custom organization name from config
  - [ ] Test waiver text with variable substitution: {{org_name}}, {{date}}
  - [ ] Test malformed YAML raises ConfigurationError
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 7: Write Failing Audit Integration Tests (AC: #5) <!-- id: 6 -->
  - [ ] Test `log_waiver_to_audit(acceptance, engagement_id, operator)` logs to audit
  - [ ] Test audit entry has action=WAIVER_ACCEPTED or WAIVER_DECLINED
  - [ ] Test audit entry includes signature in context
  - [ ] Test audit entry includes waiver_hash in context
  - [ ] Test audit entry timestamp matches acceptance timestamp
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 8: Write Failing SessionManager Integration Tests (AC: #6) <!-- id: 7 -->
  - [ ] Test `create_engagement()` calls waiver screen before completing
  - [ ] Test engagement creation fails if waiver declined
  - [ ] Test engagement config stores waiver_hash after acceptance
  - [ ] Test engagement config stores waiver_signature
  - [ ] Test engagement config stores waiver_timestamp
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 9: Write Failing Waiver Enforcement Tests (AC: #6, #8) <!-- id: 8 -->
  - [ ] Test `start_engagement()` fails if no waiver_hash in config
  - [ ] Test `start_engagement()` succeeds if valid waiver_hash exists
  - [ ] Test PreFlightCheck validates waiver presence
  - [ ] Test PreFlightCheck priority is P0 (blocking)
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 10: Write Failing Integration Tests (AC: all) <!-- id: 9 -->
  - [ ] Create `tests/integration/tui/test_waiver_workflow.py`
  - [ ] Test full workflow: create engagement → waiver screen → accept → audit logged
  - [ ] Test full workflow: create engagement → waiver screen → decline → engagement not created
  - [ ] Test waiver with custom organization config
  - [ ] Test waiver screen keyboard navigation (Tab, Enter, Escape)
  - [ ] Test waiver screen cannot be bypassed (no close without choice)
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

### Phase 2: GREEN — Implement to Pass Tests

- [ ] Task 11: Implement WaiverAcceptance Dataclass (AC: #4, #5) <!-- id: 10 -->
  - [ ] Create `src/cyberred/tui/screens/waiver.py`
  - [ ] Implement `@dataclass WaiverAcceptance`:
    - `accepted: bool`
    - `signature: str`
    - `timestamp: str` (UTC ISO)
    - `waiver_hash: str` (SHA-256)
  - [ ] Add helper method `compute_waiver_hash(waiver_text: str) -> str`
  - [ ] **Run Task 4 tests — PASS (GREEN)**

- [ ] Task 12: Implement Waiver Configuration (AC: #7) <!-- id: 11 -->
  - [ ] Create `WaiverConfig` dataclass with fields:
    - `waiver_text: str`
    - `organization_name: str`
    - `require_signature: bool = True`
  - [ ] Implement `load_waiver_config(config_path: Optional[Path]) -> WaiverConfig`
  - [ ] Load from `config/waiver.yaml` by default
  - [ ] Provide default waiver text if file not found
  - [ ] Support variable substitution: `{{org_name}}`, `{{date}}`
  - [ ] **Run Task 6 tests — PASS (GREEN)**

- [ ] Task 13: Implement WaiverScreen TUI Component (AC: #3, #4) <!-- id: 12 -->
  - [ ] Create `class WaiverScreen(ModalScreen[Optional[WaiverAcceptance]])`
  - [ ] Implement TCSS styling matching other modals (dark theme)
  - [ ] Add scrollable container for waiver text display
  - [ ] Add `Checkbox` widget for acknowledgment
  - [ ] Add `Input` widget for signature with label "Full Name:"
  - [ ] Add button row with "Accept" and "Decline" buttons
  - [ ] Implement reactive validation: enable Accept only when checkbox + signature
  - [ ] **Run Task 2, 3 tests — PASS (GREEN)**

- [ ] Task 14: Implement Waiver Acceptance Logic (AC: #4) <!-- id: 13 -->
  - [ ] Implement `on_button_pressed(event)` for Accept button:
    - Get signature from input
    - Get current UTC timestamp
    - Compute waiver hash
    - Create WaiverAcceptance(accepted=True, ...)
    - Dismiss screen with result
  - [ ] **Run Task 4 tests — PASS (GREEN)**

- [ ] Task 15: Implement Waiver Decline Logic (AC: #6) <!-- id: 14 -->
  - [ ] Implement `on_button_pressed(event)` for Decline button:
    - Create WaiverAcceptance(accepted=False, signature="", timestamp=now, waiver_hash="")
    - Dismiss screen with result
  - [ ] Add confirmation dialog before decline: "Are you sure? This will cancel engagement creation."
  - [ ] **Run Task 5 tests — PASS (GREEN)**

- [ ] Task 16: Implement Audit Logging (AC: #5) <!-- id: 15 -->
  - [ ] Extend `OperatorAction` enum with:
    - `WAIVER_ACCEPTED = "waiver_accepted"`
    - `WAIVER_DECLINED = "waiver_declined"`
  - [ ] Implement `log_waiver_to_audit(acceptance, engagement_id, operator, audit_log)`
  - [ ] Log with context: `{"signature": ..., "waiver_hash": ..., "timestamp": ...}`
  - [ ] **Run Task 7 tests — PASS (GREEN)**

- [ ] Task 17: Integrate with SessionManager (AC: #6) <!-- id: 16 -->
  - [ ] Modify `SessionManager.create_engagement()`:
    - Load waiver config
    - Show WaiverScreen modal (if TUI context available)
    - If declined, raise `EngagementCreationError("Waiver declined")`
    - If accepted, store waiver data in engagement config dict
  - [ ] For CLI-only context, provide text-based waiver acceptance
  - [ ] **Run Task 8 tests — PASS (GREEN)**

- [ ] Task 18: Implement Waiver Pre-Flight Check (AC: #6, #8) <!-- id: 17 -->
  - [ ] Create `src/cyberred/daemon/preflight_waiver.py`
  - [ ] Implement `class WaiverPreFlightCheck(PreFlightCheck)`:
    - Priority: P0 (blocking)
    - Check: engagement_config contains `waiver_hash`
    - Check: waiver_hash is valid SHA-256 format
    - Check: waiver_timestamp is present
  - [ ] Add to default pre-flight checks in `PreFlightRunner`
  - [ ] **Run Task 9 tests — PASS (GREEN)**

- [ ] Task 19: Add Waiver to Engagement Config Schema (AC: #6) <!-- id: 18 -->
  - [ ] Update engagement config schema in `core/config.py`:
    - Add optional fields: `waiver_hash`, `waiver_signature`, `waiver_timestamp`
  - [ ] Update sample configs in `config/` directory
  - [ ] **Run all unit tests — PASS (GREEN)**

- [ ] Task 20: Implement Full Integration (AC: all) <!-- id: 19 -->
  - [ ] Wire waiver screen into TUI app initialization flow
  - [ ] Test full workflow with TUI running
  - [ ] Test CLI workflow with text prompt fallback
  - [ ] Test waiver rejection properly cancels engagement creation
  - [ ] **Run Task 10 integration tests — PASS (GREEN)**

### Phase 3: REFACTOR & Finalize

- [ ] Task 21: Code Quality & Documentation (AC: all) <!-- id: 20 -->
  - [ ] Add comprehensive docstrings to all classes and functions
  - [ ] Add inline comments for complex logic
  - [ ] Ensure type hints on all function signatures
  - [ ] Add logging for waiver events (info level)
  - [ ] **Run all tests — PASS (GREEN)**

- [ ] Task 22: Create Default Waiver Template (AC: #7) <!-- id: 21 -->
  - [ ] Create `config/waiver.yaml` with default template
  - [ ] Include standard liability waiver text
  - [ ] Include placeholders for customization
  - [ ] Add comments explaining configuration options
  - [ ] **Manual verification — COMPLETE**

- [ ] Task 23: Update Documentation (AC: all) <!-- id: 22 -->
  - [ ] Add waiver configuration to operator guide
  - [ ] Document how to customize waiver text
  - [ ] Document waiver audit trail location
  - [ ] Add screenshots of waiver screen to docs
  - [ ] **Manual verification — COMPLETE**

- [ ] Task 24: Run Full Test Suite (AC: #8) <!-- id: 23 -->
  - [ ] Run: `pytest tests/unit/tui/screens/test_waiver.py -v --cov=src/cyberred/tui/screens/waiver --cov-report=term-missing --cov-fail-under=100`
  - [ ] Run: `pytest tests/integration/tui/test_waiver_workflow.py -v --cov=src/cyberred --cov-report=term-missing`
  - [ ] Verify 100% coverage for waiver module
  - [ ] Fix any remaining edge cases
  - [ ] **All tests PASS with 100% coverage**

- [ ] Task 25: Final Refactoring (AC: all) <!-- id: 24 -->
  - [ ] Review code for DRY violations
  - [ ] Extract magic strings to constants
  - [ ] Optimize imports and remove unused code
  - [ ] Run linters: `ruff check src/cyberred/tui/screens/waiver.py`
  - [ ] Run formatter: `ruff format src/cyberred/tui/screens/waiver.py`
  - [ ] **All quality checks PASS**

## Dev Notes

### Architecture Context

**Engagement Lifecycle Integration:**
- Waiver screen is shown during `SessionManager.create_engagement()` flow
- This happens BEFORE engagement reaches INITIALIZING state
- Waiver acceptance is a PREREQUISITE for engagement creation
- Pre-flight checks validate waiver presence before `start_engagement()`

**TUI Modal Pattern:**
- Follow existing modal patterns from `AuthorizationScreen`, `KillSwitchConfirmScreen`
- Use `ModalScreen[Optional[WaiverAcceptance]]` for type-safe return values
- Use Textual's reactive validation for button enable/disable
- Match dark theme styling from other screens

**Audit Integration:**
- Waiver acceptance/decline MUST be logged to append-only audit trail
- Use existing `OperatorAuditLog` from Story 13.2
- Extend `OperatorAction` enum with WAIVER_ACCEPTED and WAIVER_DECLINED
- Waiver hash provides tamper-evidence for legal defensibility

### Technical Requirements

**File Structure:**
```
src/cyberred/
├── tui/screens/waiver.py          # WaiverScreen modal (NEW)
├── daemon/preflight_waiver.py     # Waiver pre-flight check (NEW)
├── daemon/session_manager.py      # MODIFY: integrate waiver
├── storage/operator_audit.py      # MODIFY: add waiver actions
└── core/config.py                 # MODIFY: add waiver fields

tests/
├── unit/tui/screens/test_waiver.py              # NEW
├── integration/tui/test_waiver_workflow.py      # NEW
├── unit/daemon/test_preflight_waiver.py         # NEW
└── integration/daemon/test_session_waiver.py    # NEW

config/
└── waiver.yaml                    # Default waiver template (NEW)
```

**Dependencies:**
- Textual (already in project): `from textual.screen import ModalScreen`
- `OperatorAuditLog` from Story 13.2
- `SessionManager` from Epic 2
- Pre-flight framework from Story 2.6

**Configuration Schema (waiver.yaml):**
```yaml
organization_name: "{{org_name}}"
waiver_text: |
  CYBER SECURITY ENGAGEMENT LIABILITY WAIVER
  
  Organization: {{org_name}}
  Date: {{date}}
  
  By accepting this waiver, I acknowledge that:
  
  1. I have proper authorization to conduct security testing
  2. I understand the risks associated with offensive security operations
  3. I will operate only within the defined scope
  4. I accept full responsibility for all actions during this engagement
  5. I will comply with all applicable laws and regulations
  
  This waiver is legally binding and will be included in the audit trail.
  
require_signature: true
```

**Data Flow:**
1. Operator runs: `cyberred-cli engagement create config.yaml`
2. `SessionManager.create_engagement()` loads waiver config
3. TUI shows `WaiverScreen` modal (or CLI text prompt)
4. Operator reads waiver, checks acknowledgment, enters signature
5. Operator clicks "Accept" or "Decline"
6. If accepted:
   - Waiver hash computed (SHA-256 of text)
   - WaiverAcceptance created with timestamp
   - Audit log entry created (WAIVER_ACCEPTED)
   - Engagement config stores: waiver_hash, waiver_signature, waiver_timestamp
   - Engagement creation continues
7. If declined:
   - Audit log entry created (WAIVER_DECLINED)
   - Engagement creation CANCELLED
   - Error message shown to operator

**Security Considerations:**
- Waiver text hashed with SHA-256 for tamper evidence
- Audit log is append-only and HMAC signed (from Story 13.2)
- Timestamp from NTP-synced clock (from Story 1.5)
- Cannot bypass waiver screen (ModalScreen prevents background interaction)
- Pre-flight check enforces waiver presence (P0 blocking priority)

### Testing Standards

**Unit Tests:**
- Test all components in isolation with mocks
- Test edge cases: empty signature, whitespace, unicode
- Test validation logic thoroughly
- Test configuration loading with various YAML structures
- Achieve 100% line and branch coverage

**Integration Tests:**
- Test full engagement creation workflow with waiver
- Test TUI modal display and interaction
- Test audit log integration (actual Redis Streams)
- Test pre-flight check enforcement
- Test CLI fallback for non-TUI context

**Safety Tests:**
- Verify waiver cannot be bypassed
- Verify declined waiver prevents engagement creation
- Verify missing waiver blocks engagement start
- Verify audit entries are tamper-evident

### Project Structure Notes

**Alignment with Unified Structure:**
- Follows TUI screen pattern: `src/cyberred/tui/screens/waiver.py`
- Follows daemon pattern: `src/cyberred/daemon/preflight_waiver.py`
- Follows test structure: `tests/unit/tui/screens/test_waiver.py`
- Config in standard location: `config/waiver.yaml`

**Integration Points:**
- `SessionManager.create_engagement()`: Shows waiver and stores acceptance
- `PreFlightRunner`: Validates waiver before engagement start
- `OperatorAuditLog`: Records waiver acceptance/decline
- TUI App: Provides modal screen context

**Naming Conventions:**
- Class: `WaiverScreen` (follows TUI screen naming)
- Dataclass: `WaiverAcceptance` (clear noun)
- Function: `load_waiver_config`, `log_waiver_to_audit` (verb_noun)
- Enum: `OperatorAction.WAIVER_ACCEPTED` (ALL_CAPS)

### References

**Source Documents:**
- [Epic 13, Story 13.9: Pre-Engagement Liability Waiver](_bmad-output/planning-artifacts/epics-stories.md#story-139-pre-engagement-liability-waiver)
- [FR54: Pre-engagement liability waiver flow](_bmad-output/planning-artifacts/prd.md)
- [Architecture: TUI Modal Patterns](docs/3-solutioning/architecture.md#tui-patterns)
- [Story 13.2: Append-Only Audit Log](_bmad-output/implementation-artifacts/13-2-append-only-audit-log.md)
- [Story 2.6: Engagement Start & Pre-flight Checks](_bmad-output/implementation-artifacts/2-6-engagement-start-and-pre-flight-checks.md)

**Architecture References:**
- Lines 502: Modal base for overlay (architecture.md)
- Lines 570-947: Project Structure (architecture.md)
- Audit trail pattern: Redis Streams append-only (architecture.md)
- Timestamp integrity: NTP sync (Story 1.5)

**Previous Story Learnings:**
From Story 13.8 (CSV/Excel Export):
- Strict TDD with RED-GREEN-REFACTOR phases
- Comprehensive test coverage with edge cases
- Clear task sequencing with prerequisites
- Integration tests verify end-to-end workflow

**Similar Patterns in Codebase:**
- `AuthorizationScreen`: ModalScreen pattern for operator decisions
- `KillSwitchConfirmScreen`: Blocking modal with confirmation
- `DeleteConfirmationModal`: Typed input validation
- `DeploymentConfirmModal`: Form-based modal with validation

### Known Issues & Risks

**Risk: TUI Not Available in All Contexts**
- Mitigation: Provide CLI text-based fallback for waiver acceptance
- For automated/headless use: Allow pre-acceptance via config flag (with audit note)

**Risk: Waiver Text Changes After Acceptance**
- Mitigation: Hash is stored in config, can detect if waiver changed
- New waiver version requires re-acceptance (compare hashes)

**Risk: Legal Compliance Varies by Jurisdiction**
- Mitigation: Waiver text is fully configurable per organization
- Include disclaimer that org should consult legal counsel

**Risk: Signature Not Cryptographic**
- Mitigation: This is a legal acknowledgment, not cryptographic signature
- Audit log provides tamper-evidence via HMAC signing
- For stronger auth, could add future enhancement: GPG signing

## Dev Agent Record

### Agent Model Used

<!-- Fill in after implementation -->

### Debug Log References

<!-- Fill in after implementation -->

### Completion Notes List

<!-- Fill in after implementation -->

### File List

<!-- Fill in after implementation -->
