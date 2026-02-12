# Story 13.11: Evidence Chain of Custody

Status: ready-for-dev

## Story

As an **operator**,
I want **chain of custody tracking for evidence**,
So that **evidence handling is auditable (FR52)**.

## Acceptance Criteria

1. **Given** evidence file exists
   **When** evidence is accessed, exported, or modified
   **Then** access event is logged to audit trail
   **And** log includes: who, when, what action, file hash before/after
   **And** chain of custody can be reconstructed from audit log
   **And** evidence export includes chain of custody report
   **And** integration tests verify custody tracking

## Tasks / Subtasks

### Phase 1: RED — Write Failing Tests First

- [ ] Task 1: Write Failing Unit Tests for Chain of Custody Logging (AC: 1) <!-- id: 1 -->
  - [ ] Test access event logging includes all required fields
  - [ ] Test export event logging includes all required fields
  - [ ] Test modification event logging includes before/after hashes
  - [ ] Test CustodyEvent dataclass structure
  - [ ] Test custody logger uses audit trail (Redis Streams)
  - [ ] Test custody events include evidence_id, operator, action, timestamp

- [ ] Task 2: Write Failing Unit Tests for EvidenceStore Integration (AC: 1) <!-- id: 2 -->
  - [ ] Test get_evidence() logs custody access event
  - [ ] Test store_evidence() does NOT log custody event (creation, not access)
  - [ ] Test custody logger called with correct parameters
  - [ ] Test operator identity passed to custody logger
  - [ ] Test file hash included in custody event

- [ ] Task 3: Write Failing Unit Tests for Chain of Custody Reconstruction (AC: 1) <!-- id: 3 -->
  - [ ] Test get_custody_chain() returns all events for evidence_id
  - [ ] Test custody chain ordered chronologically (oldest to newest)
  - [ ] Test custody chain includes creation event
  - [ ] Test custody chain includes all access events
  - [ ] Test custody chain includes all export events
  - [ ] Test empty custody chain for non-existent evidence

- [ ] Task 4: Write Failing Unit Tests for Custody Report Generation (AC: 1) <!-- id: 4 -->
  - [ ] Test generate_custody_report() creates JSON report
  - [ ] Test report includes all custody events
  - [ ] Test report includes evidence metadata
  - [ ] Test report includes chain integrity verification
  - [ ] Test report includes cryptographic signatures

- [ ] Task 5: Write Failing Integration Tests for Export with Custody (AC: 1) <!-- id: 5 -->
  - [ ] Test evidence export includes chain_of_custody.json
  - [ ] Test ZIP export contains custody report
  - [ ] Test custody report verifiable with original evidence
  - [ ] Test export event logged to custody chain
  - [ ] Test multi-evidence export includes all custody chains

- [ ] Task 6: Write Failing Integration Tests for End-to-End Custody Flow (AC: all) <!-- id: 6 -->
  - [ ] Test full lifecycle: store → access → export with custody tracking
  - [ ] Test custody chain reconstruction across multiple operators
  - [ ] Test custody events survive system restart
  - [ ] Test custody verification with signed timestamps
  - [ ] Test audit trail integration (Redis Streams)

### Phase 2: GREEN — Implement to Pass Tests

- [ ] Task 7: Implement CustodyEvent and CustodyAuditLogger (AC: 1) <!-- id: 7 -->
  - [ ] Create CustodyEvent dataclass in core/audit.py
  - [ ] Add fields: evidence_id, operator, action, timestamp, file_hash, details
  - [ ] Create CustodyAuditLogger class
  - [ ] Implement log_custody_event() method
  - [ ] Integrate with Redis Streams (custody:{engagement_id} stream)
  - [ ] Add signed_timestamp to custody events

- [ ] Task 8: Integrate Custody Logging in EvidenceStore (AC: 1) <!-- id: 8 -->
  - [ ] Add operator parameter to get_evidence() method
  - [ ] Log custody access event in get_evidence()
  - [ ] Add custody_logger to EvidenceStore constructor
  - [ ] Pass evidence_id, operator, hash to custody logger
  - [ ] Update store_evidence() to log creation event
  - [ ] Ensure thread-safe custody logging

- [ ] Task 9: Implement Chain of Custody Reconstruction (AC: 1) <!-- id: 9 -->
  - [ ] Add get_custody_chain() method to CustodyAuditLogger
  - [ ] Query Redis Streams for custody:{engagement_id}
  - [ ] Filter events by evidence_id
  - [ ] Sort events chronologically
  - [ ] Return list of CustodyEvent objects
  - [ ] Add pagination support for large chains

- [ ] Task 10: Implement Custody Report Generation (AC: 1) <!-- id: 10 -->
  - [ ] Add generate_custody_report() to EvidenceStore
  - [ ] Include evidence metadata (filename, hash, timestamp)
  - [ ] Include complete custody chain
  - [ ] Add chain integrity verification
  - [ ] Include cryptographic signatures for each event
  - [ ] Output as JSON format

- [ ] Task 11: Implement Evidence Export with Custody (AC: 1) <!-- id: 11 -->
  - [ ] Add export_evidence_with_custody() method
  - [ ] Create ZIP archive with evidence files
  - [ ] Include chain_of_custody.json for each evidence item
  - [ ] Log export event to custody chain
  - [ ] Include manifest.json in export
  - [ ] Add verification script to export

- [ ] Task 12: Add CLI/TUI Integration for Custody Reports (AC: 1) <!-- id: 12 -->
  - [ ] Add custody chain view to data browser (TUI)
  - [ ] Add CLI command: cyber-red custody show <evidence_id>
  - [ ] Add CLI command: cyber-red custody export <engagement_id>
  - [ ] Display custody events in chronological order
  - [ ] Show operator, action, timestamp for each event

### Phase 3: REFACTOR & Finalize

- [ ] Task 13: Refactor Custody Logging for Consistency (AC: all) <!-- id: 13 -->
  - [ ] Ensure consistent event structure across all actions
  - [ ] Extract common custody logging patterns
  - [ ] Add comprehensive error handling
  - [ ] Update all docstrings with custody requirements

- [ ] Task 14: Add Comprehensive Documentation (AC: all) <!-- id: 14 -->
  - [ ] Document custody event schema
  - [ ] Add examples of custody chain reconstruction
  - [ ] Document legal defensibility considerations
  - [ ] Add troubleshooting guide for custody verification
  - [ ] Document export format specification

- [ ] Task 15: Final Integration Testing and Validation (AC: all) <!-- id: 15 -->
  - [ ] Run full integration test suite
  - [ ] Verify custody logging for all evidence operations
  - [ ] Test custody chain reconstruction with real data
  - [ ] Validate export includes complete custody information
  - [ ] Check performance impact of custody logging (should be minimal)
  - [ ] Verify backward compatibility with evidence without custody

## Dev Notes

### Architecture Context

This story implements **chain of custody tracking** for all evidence operations, building on the existing evidence storage (Story 13.1), audit logging (Story 13.2), and timestamp integrity (Story 13.10) infrastructure. Chain of custody is critical for legal defensibility (FR52).

**Key Integration Points:**

1. **Evidence Store** (`src/cyberred/storage/evidence_store.py`) - Story 13.1
   - Current implementation stores evidence with SHA-256 hashes
   - Provides `store_evidence()`, `get_evidence()`, `verify_integrity()`
   - Already includes `signed_timestamp` from Story 13.10

2. **Audit System** (`src/cyberred/core/audit.py`) - Story 13.2
   - Append-only audit log using Redis Streams
   - Multiple audit logger types (Authorization, Alert, Export, Deletion)
   - Pattern: AuditEntry dataclass + AuditLogger class

3. **Timestamp Integrity** (`src/cyberred/core/time.py`) - Story 13.10
   - Provides `sign_event_timestamp()` for cryptographic proof
   - NTP-synced timestamps with drift monitoring
   - Event-bound signatures (timestamp + event_hash)

4. **Data Browser** (`src/cyberred/tui/screens/data_browser.py`) - Story 11.2
   - TUI interface for viewing evidence
   - Integration point for custody chain display

### Technical Requirements

#### Chain of Custody Event Schema

Following the established audit pattern from Story 13.2:

```python
@dataclass
class CustodyEvent:
    """Chain of custody event for evidence handling.
    
    Tracks all access, export, and modification events for legal audit.
    """
    
    event_id: str  # Unique event ID (UUID)
    evidence_id: str  # Evidence item being tracked
    engagement_id: str  # Engagement context
    operator: str  # Who accessed/exported the evidence
    action: str  # ACCESS | EXPORT | MODIFY | CREATE | DELETE
    timestamp: str  # ISO 8601 UTC timestamp
    file_hash: str  # SHA-256 hash at time of event
    file_hash_before: str | None  # For MODIFY events
    details: dict[str, Any]  # Additional context (export path, access reason, etc.)
    signed_timestamp: dict[str, str]  # Cryptographic timestamp signature
```

#### Custody Audit Logger Implementation

Following the pattern from existing audit loggers:

```python
class CustodyAuditLogger:
    """Audit logger for evidence chain of custody.
    
    Logs all evidence access, export, and modification events to
    Redis Streams for tamper-evident audit trail.
    """
    
    def __init__(self, engagement_id: str, redis_client: RedisClient):
        self.engagement_id = engagement_id
        self.redis = redis_client
        self.stream_key = f"custody:{engagement_id}"
    
    async def log_custody_event(
        self,
        evidence_id: str,
        operator: str,
        action: str,
        file_hash: str,
        details: dict[str, Any] | None = None,
        file_hash_before: str | None = None,
    ) -> str:
        """Log custody event to Redis Streams.
        
        Returns:
            Event ID for tracking.
        """
        # Generate event ID
        event_id = str(uuid.uuid4())
        
        # Sign timestamp bound to file hash
        from cyberred.core.time import sign_event_timestamp, now
        signed_ts = sign_event_timestamp(file_hash, self._get_signing_key())
        
        # Create event
        event = CustodyEvent(
            event_id=event_id,
            evidence_id=evidence_id,
            engagement_id=self.engagement_id,
            operator=operator,
            action=action,
            timestamp=now(),
            file_hash=file_hash,
            file_hash_before=file_hash_before,
            details=details or {},
            signed_timestamp=signed_ts,
        )
        
        # Write to Redis Streams (append-only)
        await self.redis.xadd(self.stream_key, event.to_dict())
        
        return event_id
    
    async def get_custody_chain(
        self,
        evidence_id: str,
    ) -> list[CustodyEvent]:
        """Reconstruct chain of custody for evidence.
        
        Returns all custody events for given evidence_id,
        ordered chronologically (oldest to newest).
        """
        # Read all events from stream
        events = await self.redis.xrange(self.stream_key, "-", "+")
        
        # Filter by evidence_id and parse
        chain = []
        for event_id, event_data in events:
            if event_data.get("evidence_id") == evidence_id:
                chain.append(CustodyEvent.from_dict(event_data))
        
        # Sort chronologically
        chain.sort(key=lambda e: e.timestamp)
        
        return chain
```

#### EvidenceStore Integration

Modify `EvidenceStore` to log custody events:

```python
class EvidenceStore:
    def __init__(
        self,
        engagement_id: str,
        encryption_key: bytes,
        base_path: Path | None = None,
        custody_logger: CustodyAuditLogger | None = None,  # NEW
    ):
        # ... existing init ...
        self.custody_logger = custody_logger
    
    def store_evidence(
        self,
        content: bytes,
        filename: str,
        source_agent: str,
        evidence_type: EvidenceType,
        operator: str = "system",  # NEW: for custody tracking
    ) -> EvidenceItem:
        """Store evidence with encryption and custody logging."""
        # ... existing storage logic ...
        
        # Log custody creation event
        if self.custody_logger:
            asyncio.create_task(
                self.custody_logger.log_custody_event(
                    evidence_id=item.id,
                    operator=operator,
                    action="CREATE",
                    file_hash=sha256_hash,
                    details={
                        "filename": filename,
                        "source_agent": source_agent,
                        "evidence_type": evidence_type.value,
                    },
                )
            )
        
        return item
    
    def get_evidence(
        self,
        evidence_id: str,
        operator: str,  # NEW: required for custody
        access_reason: str | None = None,  # NEW: optional context
    ) -> bytes:
        """Retrieve evidence with custody logging."""
        # ... existing retrieval logic ...
        
        # Log custody access event
        if self.custody_logger:
            asyncio.create_task(
                self.custody_logger.log_custody_event(
                    evidence_id=evidence_id,
                    operator=operator,
                    action="ACCESS",
                    file_hash=item.sha256_hash,
                    details={"access_reason": access_reason or "retrieval"},
                )
            )
        
        return plaintext
```

#### Custody Report Format

Export format for chain of custody:

```json
{
  "report_version": "1.0",
  "generated_at": "2026-02-12T09:30:00Z",
  "engagement_id": "ministry-2025",
  "evidence": {
    "id": "abc-123-def",
    "filename": "screenshot_001.png",
    "sha256_hash": "a1b2c3...",
    "created_at": "2026-02-10T15:00:00Z",
    "source_agent": "recon-42"
  },
  "custody_chain": [
    {
      "event_id": "evt-001",
      "action": "CREATE",
      "operator": "system",
      "timestamp": "2026-02-10T15:00:00Z",
      "file_hash": "a1b2c3...",
      "signed_timestamp": {
        "timestamp": "2026-02-10T15:00:00.000000+00:00",
        "event_hash": "a1b2c3...",
        "signature": "base64..."
      }
    },
    {
      "event_id": "evt-002",
      "action": "ACCESS",
      "operator": "root",
      "timestamp": "2026-02-11T10:00:00Z",
      "file_hash": "a1b2c3...",
      "details": {"access_reason": "manual review"},
      "signed_timestamp": {...}
    },
    {
      "event_id": "evt-003",
      "action": "EXPORT",
      "operator": "root",
      "timestamp": "2026-02-12T09:30:00Z",
      "file_hash": "a1b2c3...",
      "details": {"export_path": "/tmp/evidence_export.zip"},
      "signed_timestamp": {...}
    }
  ],
  "integrity_verification": {
    "all_signatures_valid": true,
    "chain_complete": true,
    "no_hash_changes": true
  }
}
```

### Existing Code Patterns

#### From Story 13.1 (Evidence Storage)

The `EvidenceStore` already implements:
- Thread-safe evidence storage with `_lock`
- SHA-256 hashing of content
- Signed timestamps (Story 13.10 integration)
- Atomic manifest updates

**Integration Point:**
```python
# Current get_evidence signature
def get_evidence(self, evidence_id: str) -> bytes:
    ...

# Enhanced signature with custody tracking
def get_evidence(
    self,
    evidence_id: str,
    operator: str,  # NEW
    access_reason: str | None = None,  # NEW
) -> bytes:
    ...
```

#### From Story 13.2 (Audit Logging)

Established audit patterns:
- Redis Streams for append-only log
- Dataclass for entry structure
- Logger class with `log_*()` methods
- Async operations for non-blocking writes

**Code Pattern:**
```python
# Existing pattern from AuthorizationAuditLogger
@dataclass
class AuthorizationAuditEntry:
    timestamp: str
    operator: str
    # ... fields ...

class AuthorizationAuditLogger:
    def __init__(self, engagement_id: str, redis_client: RedisClient):
        self.stream_key = f"audit:{engagement_id}"
    
    async def log_authorization(self, entry: AuthorizationAuditEntry):
        await self.redis.xadd(self.stream_key, entry.to_dict())
```

**Apply to Custody:**
```python
# New custody logger following same pattern
@dataclass
class CustodyEvent:
    evidence_id: str
    operator: str
    action: str
    # ... fields ...

class CustodyAuditLogger:
    def __init__(self, engagement_id: str, redis_client: RedisClient):
        self.stream_key = f"custody:{engagement_id}"
    
    async def log_custody_event(self, ...):
        await self.redis.xadd(self.stream_key, event.to_dict())
```

#### From Story 13.10 (Timestamp Integrity)

Signed timestamps for all custody events:

```python
from cyberred.core.time import sign_event_timestamp

# Sign custody event timestamp bound to file hash
signed_ts = sign_event_timestamp(file_hash, signing_key)

# Include in custody event
event.signed_timestamp = signed_ts
```

#### From Story 11.2 (Data Browser)

Data browser provides TUI for viewing evidence. Add custody chain view:

```python
# In data_browser.py
async def show_custody_chain(self, evidence_id: str):
    """Display chain of custody for evidence."""
    custody_logger = self.get_custody_logger()
    chain = await custody_logger.get_custody_chain(evidence_id)
    
    # Display in chronological order
    for event in chain:
        self.log_custody_event_to_ui(event)
```

### Library and Framework Requirements

**No new dependencies required** - all functionality uses existing libraries:

1. **Redis (redis-py)** - Already in use for audit streams
2. **hashlib** - Python stdlib for SHA-256
3. **uuid** - Python stdlib for event IDs
4. **json** - Python stdlib for report generation
5. **zipfile** - Python stdlib for evidence export archives

### File Structure Requirements

**Files to Modify:**

1. **`src/cyberred/core/audit.py`**
   - Add `CustodyEvent` dataclass
   - Add `CustodyAuditLogger` class
   - Follow existing audit logger pattern

2. **`src/cyberred/storage/evidence_store.py`**
   - Add `operator` parameter to `get_evidence()`
   - Add `custody_logger` to constructor
   - Log custody events on access/export/creation
   - Add `generate_custody_report()` method
   - Add `export_evidence_with_custody()` method

3. **`src/cyberred/tui/screens/data_browser.py`**
   - Add custody chain view
   - Display custody events for selected evidence
   - Add export with custody option

4. **`src/cyberred/cli.py`** (optional CLI integration)
   - Add `custody show <evidence_id>` command
   - Add `custody export <engagement_id>` command

**Files to Create:**

No new files required - all functionality integrates into existing modules.

**Test Files to Create/Modify:**

1. **`tests/unit/core/test_audit_custody.py`** - New unit tests for custody logging
2. **`tests/unit/storage/test_evidence_custody.py`** - Unit tests for EvidenceStore integration
3. **`tests/integration/storage/test_custody_chain.py`** - New integration tests for end-to-end custody
4. **`tests/integration/tui/test_data_browser_custody.py`** - TUI custody view tests

### Testing Requirements

**Unit Tests** (TDD - write first):
- Test `CustodyEvent` dataclass serialization/deserialization
- Test `CustodyAuditLogger.log_custody_event()` writes to Redis
- Test `get_custody_chain()` filters and sorts correctly
- Test `EvidenceStore.get_evidence()` logs custody access
- Test custody report generation format
- Test signed timestamp integration in custody events

**Integration Tests** (strict, minimal mocks):
- Test end-to-end custody tracking: create → access → export
- Test custody chain reconstruction from Redis Streams
- Test evidence export includes chain_of_custody.json
- Test custody events survive system restart
- Test multi-operator custody chain
- Test custody verification with signed timestamps

**Safety Tests**:
- Test custody logging cannot be bypassed
- Test tampering detection (modified custody events)
- Test custody chain completeness verification
- Test operator identity validation

### Previous Story Intelligence

From **Story 13.10 (Timestamp Integrity)**:

**Successful Patterns:**
- TDD approach with comprehensive failing tests first
- Integration with existing modules (EvidenceStore, Audit)
- Signed timestamps using `sign_event_timestamp()`
- Thread-safe operations with locks
- Async operations for non-blocking I/O

**Code Patterns Established:**
```python
# Signed timestamp pattern
from cyberred.core.time import sign_event_timestamp
signed_ts = sign_event_timestamp(event_hash, key)

# Redis Streams pattern
await redis.xadd(stream_key, event_dict)

# Thread-safe operations
with self._lock:
    # ... critical section ...
```

**Testing Approach:**
- Phase 1: Write all failing tests
- Phase 2: Implement minimal code to pass
- Phase 3: Refactor and document
- Integration tests use real Redis (no mocks)

### Git Intelligence

Recent commits show:
1. **Comprehensive audit infrastructure** - Story 13.2 implementation
2. **Evidence storage with encryption** - Story 13.1 implementation
3. **Timestamp integrity** - Story 13.10 implementation
4. **TUI data browser** - Story 11.2 implementation

**Relevant Patterns from Recent Work:**
- Consistent use of dataclasses for structured data
- Redis Streams for append-only logs
- Async/await for I/O operations
- Type hints with `from __future__ import annotations`
- Comprehensive docstrings with Args/Returns

### Project Structure Notes

**Alignment with Unified Project Structure:**

1. **Audit System** (`src/cyberred/core/audit.py`):
   - Established pattern: Multiple audit logger types
   - Adding `CustodyAuditLogger` follows existing conventions
   - Uses same Redis Streams infrastructure

2. **Evidence Storage** (`src/cyberred/storage/evidence_store.py`):
   - Extension of existing `EvidenceStore` class
   - Maintains backward compatibility
   - Adds optional custody logging

3. **TUI Integration** (`src/cyberred/tui/screens/data_browser.py`):
   - Extends existing data browser functionality
   - Adds custody chain view
   - Follows established TUI patterns

4. **Testing Structure** (`tests/`):
   - Unit tests mirror `src/` structure
   - Integration tests in `tests/integration/storage/`
   - Safety tests in `tests/safety/` for critical custody features

**No Conflicts Detected** - This story extends existing modules without breaking changes.

### References

**Source Documents:**

1. **Epic 13: Evidence, Reporting & Audit** - [Source: _bmad-output/planning-artifacts/epics-stories.md#Epic-13]
   - Story 13.11 requirements (lines 5015-5036)
   - FR52: "Chain of custody for legal defensibility"
   - NFR15, NFR16: Legal defensibility and audit compliance

2. **Architecture Document** - [Source: _bmad-output/planning-artifacts/architecture.md]
   - Lines 861-866: Storage module architecture
   - Evidence storage structure
   - Audit trail infrastructure

3. **Story 13.1: Evidence File Storage** - [Source: _bmad-output/implementation-artifacts/13-1-evidence-file-storage.md]
   - `EvidenceStore` implementation
   - SHA-256 manifest format
   - Thread-safe operations

4. **Story 13.2: Append-Only Audit Log** - [Source: _bmad-output/implementation-artifacts/13-2-append-only-audit-log.md]
   - Audit logger pattern
   - Redis Streams integration
   - Append-only guarantees

5. **Story 13.10: Timestamp Integrity** - [Source: _bmad-output/implementation-artifacts/13-10-timestamp-integrity.md]
   - Signed timestamp implementation
   - Event-bound signatures
   - Cryptographic proof

6. **Story 11.2: Exfiltrated Data Browser** - [Source: _bmad-output/implementation-artifacts/11-2-exfiltrated-data-browser.md]
   - TUI data browser implementation
   - Evidence viewing interface
   - Integration patterns

**Code References:**

1. `src/cyberred/storage/evidence_store.py` - Evidence storage with signed timestamps
2. `src/cyberred/core/audit.py` - Audit logging infrastructure
3. `src/cyberred/core/time.py` - Timestamp signing and verification
4. `src/cyberred/tui/screens/data_browser.py` - TUI evidence browser
5. `tests/integration/storage/test_evidence_store.py` - Evidence storage tests

## Dev Agent Record

### Agent Model Used

<!-- To be filled by dev agent -->

### Debug Log References

<!-- To be filled by dev agent -->

### Completion Notes List

<!-- To be filled by dev agent -->

### File List

<!-- To be filled by dev agent -->
