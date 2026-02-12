# Story 13.10: Timestamp Integrity

Status: ready-for-dev

## Story

As a **developer**,
I want **NTP-synced timestamps with crypto signatures**,
So that **evidence timestamps are legally defensible (FR51)**.

## Acceptance Criteria

1. **Given** engagement is running
   **When** any event is logged (finding, action, checkpoint)
   **Then** timestamp is sourced from NTP-synced clock
   **And** timestamp includes timezone (UTC)
   **And** timestamp is cryptographically signed with engagement key
   **And** clock drift is monitored and alerted if >1s
   **And** unit tests verify timestamp signing

## Tasks / Subtasks

### Phase 1: RED — Write Failing Tests First

- [ ] Task 1: Write Failing Unit Tests for Enhanced Timestamp Signing (AC: 1) <!-- id: 1 -->
  - [ ] Test signed timestamp structure includes timestamp, event_hash, signature fields
  - [ ] Test sign_event_timestamp() creates valid signature with engagement key
  - [ ] Test verify_event_timestamp() validates signature correctly
  - [ ] Test signature includes event_hash in signing data
  - [ ] Test invalid signature detection
  - [ ] Test wrong key rejection

- [ ] Task 2: Write Failing Unit Tests for Evidence Store Timestamp Integration (AC: 1) <!-- id: 2 -->
  - [ ] Test EvidenceStore.store() calls TrustedTime and signs timestamp with engagement key
  - [ ] Test evidence manifest includes signed_timestamp field
  - [ ] Test signed_timestamp contains timestamp, event_hash, signature
  - [ ] Test event_hash is SHA-256 of file contents
  - [ ] Test signature verification on evidence retrieval

- [ ] Task 3: Write Failing Unit Tests for Audit Log Timestamp Integration (AC: 1) <!-- id: 3 -->
  - [ ] Test AuthorizationAuditLogger logs include signed timestamps
  - [ ] Test AlertAuditLogger logs include signed timestamps
  - [ ] Test ExportAuditLogger logs include signed timestamps
  - [ ] Test DeletionAuditLogger logs include signed timestamps
  - [ ] Test audit entry structure includes signed_timestamp field
  - [ ] Test signature verification for audit entries

- [ ] Task 4: Write Failing Unit Tests for Checkpoint Timestamp Integration (AC: 1) <!-- id: 4 -->
  - [ ] Test CheckpointManager creates signed timestamps for checkpoints
  - [ ] Test checkpoint metadata includes signed_timestamp
  - [ ] Test checkpoint restore validates timestamp signature
  - [ ] Test signature verification on checkpoint load

- [ ] Task 5: Write Failing Unit Tests for Drift Monitoring and Alerts (AC: 1) <!-- id: 5 -->
  - [ ] Test drift >1s triggers warning alert
  - [ ] Test drift >5s triggers error alert  
  - [ ] Test drift alerts include actual drift value
  - [ ] Test drift monitoring uses TrustedTime.get_drift()
  - [ ] Test alerts are sent through event bus

- [ ] Task 6: Write Failing Integration Tests for End-to-End Timestamp Flow (AC: all) <!-- id: 6 -->
  - [ ] Test evidence storage with real NTP sync and signature
  - [ ] Test audit logging with signed timestamps
  - [ ] Test checkpoint creation with signed timestamps
  - [ ] Test timestamp verification across system restart
  - [ ] Test drift monitoring triggers alerts when clock drifts

### Phase 2: GREEN — Implement to Pass Tests

- [ ] Task 7: Enhance TrustedTime with Event Signing (AC: 1) <!-- id: 7 -->
  - [ ] Add sign_event_timestamp(event_hash: str, key: bytes) -> dict method
  - [ ] Return dict with: timestamp, event_hash, signature
  - [ ] Signature = HMAC-SHA256(timestamp + event_hash, key)
  - [ ] Add verify_event_timestamp(signed_data: dict, key: bytes) -> bool method
  - [ ] Add module-level convenience functions
  - [ ] Update type hints and docstrings

- [ ] Task 8: Integrate Timestamp Signing in EvidenceStore (AC: 1) <!-- id: 8 -->
  - [ ] Modify EvidenceStore.store() to use sign_event_timestamp()
  - [ ] Compute event_hash as SHA-256 of file contents
  - [ ] Add signed_timestamp field to evidence manifest
  - [ ] Store as: {timestamp, event_hash, signature}
  - [ ] Update EvidenceItem model with signed_timestamp field
  - [ ] Add verification method for evidence timestamps

- [ ] Task 9: Integrate Timestamp Signing in Audit Loggers (AC: 1) <!-- id: 9 -->
  - [ ] Update AuthorizationAuditEntry with signed_timestamp field
  - [ ] Update AlertAuditLogger to use signed timestamps
  - [ ] Update ExportAuditLogger to use signed timestamps
  - [ ] Update DeletionAuditLogger to use signed timestamps
  - [ ] Compute event_hash as SHA-256 of entry content
  - [ ] Store signed_timestamp in Redis streams

- [ ] Task 10: Integrate Timestamp Signing in CheckpointManager (AC: 1) <!-- id: 10 -->
  - [ ] Add signed_timestamp to CheckpointData model
  - [ ] Compute event_hash as SHA-256 of serialized checkpoint data
  - [ ] Sign timestamp during checkpoint save
  - [ ] Verify signature during checkpoint restore
  - [ ] Log warning if signature verification fails

- [ ] Task 11: Implement Drift Monitoring Service (AC: 1) <!-- id: 11 -->
  - [ ] Create DriftMonitor class in core/time.py
  - [ ] Run periodic check (every 60s) using TrustedTime.get_drift()
  - [ ] Trigger warning alert if drift > 1.0s
  - [ ] Trigger error alert if drift > 5.0s
  - [ ] Publish alerts to event bus (situational_alert topic)
  - [ ] Start monitor as background thread in daemon
  - [ ] Add graceful shutdown on daemon stop

- [ ] Task 12: Add Drift Alerts to TUI (AC: 1) <!-- id: 12 -->
  - [ ] Handle situational_alert events for drift warnings
  - [ ] Display drift value in alert message
  - [ ] Show visual indicator when drift exceeds threshold
  - [ ] Add drift status to system status panel (if exists)

### Phase 3: REFACTOR & Finalize

- [ ] Task 13: Refactor Timestamp Signing for Consistency (AC: all) <!-- id: 13 -->
  - [ ] Ensure all storage modules use consistent signing format
  - [ ] Extract common signing logic if needed
  - [ ] Update all docstrings with signing specification
  - [ ] Add type hints for signed_timestamp structures

- [ ] Task 14: Add Comprehensive Documentation (AC: all) <!-- id: 14 -->
  - [ ] Document signed timestamp format specification
  - [ ] Add examples of signature verification
  - [ ] Document legal defensibility considerations
  - [ ] Update architecture docs with timestamp integrity flow
  - [ ] Add troubleshooting guide for drift issues

- [ ] Task 15: Final Integration Testing and Validation (AC: all) <!-- id: 15 -->
  - [ ] Run full integration test suite
  - [ ] Verify all evidence, audit, checkpoint timestamps are signed
  - [ ] Test signature verification across system restart
  - [ ] Validate drift monitoring alerts work correctly
  - [ ] Check performance impact of signing (should be minimal)
  - [ ] Verify backward compatibility with unsigned timestamps

## Dev Notes

### Architecture Context

This story enhances the existing **TrustedTime** NTP synchronization system (Story 1.5) to provide **cryptographic proof** of timestamp integrity for legal defensibility. The implementation builds on:

1. **Existing NTP Infrastructure** (`src/cyberred/core/time.py`):
   - `TrustedTime` class already provides NTP-synced timestamps via background thread
   - `sign_timestamp()` and `verify_timestamp_signature()` methods exist for basic signing
   - Module exports `now()`, `sign_timestamp()`, `verify_timestamp_signature()` functions
   - Drift detection already logs warnings at >1s and errors at >5s

2. **Storage Systems Requiring Signed Timestamps**:
   - **Evidence Store** (`src/cyberred/storage/evidence_store.py`) - Story 13.1
   - **Audit Loggers** (`src/cyberred/core/audit.py`) - Story 13.2
   - **Checkpoint Manager** (`src/cyberred/storage/checkpoint.py`) - Story 13.3

3. **Crypto Requirements** (from architecture):
   - Use HMAC-SHA256 for timestamp signatures
   - Engagement-specific signing key from keystore
   - Signature format: `{timestamp, event_hash, signature}`
   - Event hash = SHA-256 of logged event/file content

### Technical Requirements

#### Enhanced Timestamp Signing

The current `TrustedTime.sign_timestamp()` only signs the timestamp itself. For legal defensibility, we need to bind the timestamp to the specific event:

```python
# Current (timestamp-only signing)
signature = HMAC-SHA256(timestamp, key)

# Enhanced (timestamp + event binding)
signature = HMAC-SHA256(timestamp + event_hash, key)
```

**New Method Signature:**
```python
def sign_event_timestamp(event_hash: str, key: bytes) -> dict:
    """Create signed timestamp bound to specific event.
    
    Args:
        event_hash: SHA-256 hash of event/file content (hex string)
        key: Engagement-specific signing key
    
    Returns:
        {
            "timestamp": "2026-01-01T12:00:00.000000+00:00",
            "event_hash": "abc123...",
            "signature": "base64-encoded-hmac-sha256"
        }
    """
```

#### Integration Points

1. **EvidenceStore.store()** - When storing evidence files:
   ```python
   # Compute event hash from file contents
   event_hash = hashlib.sha256(file_contents).hexdigest()
   
   # Sign timestamp bound to this file
   signed_ts = TrustedTime().sign_event_timestamp(event_hash, engagement_key)
   
   # Add to manifest
   manifest["signed_timestamp"] = signed_ts
   ```

2. **Audit Loggers** - When creating audit entries:
   ```python
   # Compute event hash from entry content
   entry_content = f"{operator}|{action}|{context}"
   event_hash = hashlib.sha256(entry_content.encode()).hexdigest()
   
   # Sign timestamp
   signed_ts = sign_event_timestamp(event_hash, engagement_key)
   
   # Include in audit entry
   entry["signed_timestamp"] = signed_ts
   ```

3. **CheckpointManager** - When saving checkpoints:
   ```python
   # Serialize checkpoint data
   checkpoint_json = json.dumps(checkpoint_data, sort_keys=True)
   event_hash = hashlib.sha256(checkpoint_json.encode()).hexdigest()
   
   # Sign timestamp
   signed_ts = sign_event_timestamp(event_hash, engagement_key)
   
   # Add to checkpoint metadata
   checkpoint_data.signed_timestamp = signed_ts
   ```

#### Drift Monitoring Service

While drift detection already exists in `TrustedTime._sync()`, we need **active monitoring** to trigger alerts:

```python
class DriftMonitor:
    """Background service to monitor clock drift and trigger alerts."""
    
    def __init__(self, event_bus: EventBus):
        self.time_provider = TrustedTime()
        self.event_bus = event_bus
        self._stop_event = threading.Event()
        
    def run(self):
        """Check drift every 60s and publish alerts."""
        while not self._stop_event.wait(60):
            drift = self.time_provider.get_drift()
            if abs(drift) > 5.0:
                self._publish_alert("error", drift)
            elif abs(drift) > 1.0:
                self._publish_alert("warning", drift)
```

Start in daemon initialization:
```python
# src/cyberred/daemon/server.py
self.drift_monitor = DriftMonitor(self.event_bus)
monitor_thread = threading.Thread(target=self.drift_monitor.run, daemon=True)
monitor_thread.start()
```

### Existing Code Patterns

#### From Story 1.5 (NTP Time Synchronization)

The `TrustedTime` class is already implemented with:
- Background thread for non-blocking NTP sync
- `now()` method returning ISO 8601 timestamps with UTC timezone
- `sign_timestamp()` for HMAC-SHA256 signing
- `get_drift()` for drift monitoring
- Drift logging at >1s (warning) and >5s (error) thresholds

**Key code patterns:**
```python
# Getting NTP-synced timestamp
from cyberred.core.time import now
timestamp = now()  # "2026-01-01T12:00:00.123456+00:00"

# Signing timestamp (current implementation)
from cyberred.core.time import sign_timestamp
signature = sign_timestamp(timestamp, key)

# Checking drift
time_provider = TrustedTime()
drift = time_provider.get_drift()  # float, seconds
```

#### From Story 13.1 (Evidence Storage)

Evidence files are stored with SHA-256 manifests:
```python
class EvidenceItem:
    filename: str
    hash: str  # SHA-256
    timestamp: str  # Currently unsigned
    source_agent: str
    # Need to add: signed_timestamp
```

#### From Story 13.2 (Audit Logging)

Audit entries use Redis Streams with structured data:
```python
class AuthorizationAuditEntry:
    timestamp: str  # Currently from now()
    operator: str
    action: str
    context: dict
    # Need to add: signed_timestamp
```

#### From Story 13.9 (Previous Story - Waiver Workflow)

Recent learnings from Story 13.9:
- Use TDD approach with comprehensive test coverage
- Integration tests should test real behavior with minimal mocks
- Store cryptographic data in structured format for easy verification
- Use engagement_id for key derivation
- Test error cases (missing keys, invalid signatures)

### Library and Framework Requirements

**No new dependencies required** - all functionality uses existing libraries:

1. **ntplib** - Already in use for NTP synchronization (Story 1.5)
2. **hmac, hashlib** - Python stdlib for cryptographic operations
3. **base64** - Python stdlib for signature encoding

### File Structure Requirements

**Files to Modify:**

1. **`src/cyberred/core/time.py`**
   - Add `sign_event_timestamp()` method to `TrustedTime` class
   - Add `verify_event_timestamp()` method
   - Add module-level convenience functions
   - Add `DriftMonitor` class for active monitoring

2. **`src/cyberred/storage/evidence_store.py`**
   - Update `EvidenceItem` model with `signed_timestamp` field
   - Modify `store()` method to compute event hash and sign timestamp
   - Add `verify_evidence_timestamp()` method

3. **`src/cyberred/core/audit.py`**
   - Update all audit entry models with `signed_timestamp` field
   - Modify all logger classes to sign timestamps
   - Add verification helpers

4. **`src/cyberred/storage/checkpoint.py`**
   - Update `CheckpointData` model with `signed_timestamp` field
   - Modify `save()` to sign checkpoints
   - Modify `restore()` to verify signatures

5. **`src/cyberred/daemon/server.py`** (or daemon initialization)
   - Start `DriftMonitor` background service
   - Add graceful shutdown handling

**Files to Create:**

No new files required - all functionality integrates into existing modules.

**Test Files to Modify/Create:**

1. **`tests/unit/core/test_time.py`** - Add tests for event signing
2. **`tests/unit/storage/test_evidence_store.py`** - Add timestamp signing tests
3. **`tests/unit/core/test_audit.py`** - Add audit timestamp tests
4. **`tests/unit/storage/test_checkpoint.py`** - Add checkpoint timestamp tests
5. **`tests/integration/core/test_timestamp_integrity.py`** - New integration tests

### Testing Requirements

**Unit Tests** (TDD - write first):
- Test `sign_event_timestamp()` creates correct signature format
- Test signature includes both timestamp and event_hash
- Test `verify_event_timestamp()` validates signatures correctly
- Test invalid signature detection
- Test each storage system integration (evidence, audit, checkpoint)
- Test drift monitoring alert thresholds

**Integration Tests** (strict, minimal mocks):
- Test end-to-end evidence storage with signed timestamps
- Test audit logging with signature verification
- Test checkpoint save/restore with signature validation
- Test drift monitoring triggers alerts on real drift simulation
- Test signature verification survives system restart

**Safety Tests**:
- Test tamper detection (modified timestamp/event_hash fails verification)
- Test signature verification with wrong key fails
- Test system behavior when NTP sync fails (should still sign with local time)

### Previous Story Intelligence

From **Story 13.9 (Pre-Engagement Liability Waiver)**:

**Successful Patterns:**
- TDD approach with failing tests first
- Integration tests in `tests/integration/tui/` with real Redis/SQLite
- Use of `@pytest.fixture` for shared test setup
- Comprehensive error handling and validation
- Clear separation of concerns (model, storage, UI)

**Code Patterns Established:**
```python
# Engagement key derivation (from Story 1.6)
from cyberred.core.keystore import get_engagement_key
key = get_engagement_key(engagement_id)

# Event bus integration (from multiple stories)
from cyberred.core.events import get_event_bus
event_bus = get_event_bus()
await event_bus.publish("situational_alert", alert_data)

# Redis integration (from Story 3.1)
from cyberred.storage.redis_client import get_redis
redis = get_redis()
await redis.xadd(f"audit:{engagement_id}", entry_dict)
```

**Files Modified in Story 13.9:**
- `src/cyberred/tui/screens/waiver.py` - TUI screen implementation
- `tests/integration/tui/test_waiver_workflow.py` - Integration tests
- Story followed strict TDD with comprehensive test coverage

**Testing Approach:**
- Write all unit tests first (RED phase)
- Implement minimal code to pass tests (GREEN phase)
- Refactor for clarity and consistency (REFACTOR phase)
- Integration tests use real dependencies (Redis, SQLite, event bus)

### Git Intelligence

Recent commits show:
1. **Agent-driven development workflows** - Extensive BMAD automation
2. **Security adapters and libraries** - Focus on crypto and security
3. **Comprehensive testing frameworks** - Test infrastructure maturity

**Relevant Patterns from Recent Work:**
- Use of async/await for I/O operations
- Type hints with `from __future__ import annotations`
- Comprehensive docstrings with Args/Returns sections
- Consistent error handling with custom exceptions

### Project Structure Notes

**Alignment with Unified Project Structure:**

1. **Core Time Module** (`src/cyberred/core/time.py`):
   - Already established in Story 1.5
   - Enhancement adds event-binding to existing signature methods
   - Maintains backward compatibility with `sign_timestamp()`

2. **Storage Modules** (`src/cyberred/storage/`):
   - Evidence, checkpoint modules follow established patterns
   - All use async I/O for file operations
   - All integrate with event bus for monitoring

3. **Audit System** (`src/cyberred/core/audit.py`):
   - Centralized audit logging for all operator actions
   - Uses Redis Streams for append-only log
   - Already structured for extensibility

4. **Testing Structure** (`tests/`):
   - Unit tests in `tests/unit/` mirror `src/` structure
   - Integration tests in `tests/integration/` with real dependencies
   - Safety tests in `tests/safety/` for security-critical features

**No Conflicts Detected** - This story extends existing modules without breaking changes.

### References

**Source Documents:**

1. **Epic 13: Evidence, Reporting & Audit** - [Source: _bmad-output/planning-artifacts/epics-stories.md#Epic-13]
   - Story 13.10 requirements (lines 4992-5013)
   - FR51: "Timestamp integrity (NTP sync, crypto signatures)"
   - NFR15, NFR16: Legal defensibility and audit compliance

2. **Architecture Document** - [Source: _bmad-output/planning-artifacts/architecture.md]
   - Line 542: "Timestamp integrity (NTP sync, crypto signatures)"
   - Crypto specifications for HMAC-SHA256
   - Event bus architecture for alert distribution

3. **Story 1.5: NTP Time Synchronization** - [Source: _bmad-output/implementation-artifacts/1-5-ntp-time-synchronization.md]
   - Existing `TrustedTime` implementation
   - Drift detection thresholds (>1s warn, >5s error)
   - Background thread architecture

4. **Story 13.1: Evidence File Storage** - [Source: _bmad-output/implementation-artifacts/13-1-evidence-file-storage.md]
   - `EvidenceStore` class and `EvidenceItem` model
   - SHA-256 manifest format
   - Integration with engagement keystore

5. **Story 13.2: Append-Only Audit Log** - [Source: _bmad-output/implementation-artifacts/13-2-append-only-audit-log.md]
   - Audit entry models and loggers
   - Redis Streams integration
   - Tamper-evidence requirements

6. **Story 13.3: SQLite Checkpoint Storage** - [Source: _bmad-output/implementation-artifacts/13-3-sqlite-checkpoint-storage.md]
   - `CheckpointManager` and `CheckpointData` models
   - Checkpoint save/restore flow
   - Integrity validation requirements

**Code References:**

1. `src/cyberred/core/time.py` - TrustedTime implementation
2. `src/cyberred/storage/evidence_store.py` - Evidence storage
3. `src/cyberred/core/audit.py` - Audit logging system
4. `src/cyberred/storage/checkpoint.py` - Checkpoint management
5. `tests/unit/core/test_time.py` - Existing timestamp tests

## Dev Agent Record

### Agent Model Used

<!-- To be filled by dev agent -->

### Debug Log References

<!-- To be filled by dev agent -->

### Completion Notes List

<!-- To be filled by dev agent -->

### File List

<!-- To be filled by dev agent -->
