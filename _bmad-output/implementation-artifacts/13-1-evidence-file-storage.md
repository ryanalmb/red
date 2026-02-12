# Story 13.1: Evidence File Storage

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **secure evidence storage with SHA-256 manifests**,
So that **collected evidence has cryptographic integrity (FR36)**.

## Acceptance Criteria

1. **Given** engagement is running
2. **When** evidence file is captured (screenshot, log, loot)
3. **Then** file is stored in `~/.cyber-red/evidence/{engagement_id}/`
4. **And** file is encrypted at rest (AES-256)
5. **And** SHA-256 hash is recorded in manifest.json
6. **And** manifest includes: filename, hash, timestamp, source_agent
7. **And** unit tests verify hash integrity

## Tasks / Subtasks

> [!IMPORTANT]
> **RED-GREEN TDD METHODOLOGY REQUIRED**
> Each task MUST follow strict TDD: Write failing tests FIRST (RED), then implement code to pass (GREEN), then refactor.

### Phase 1: RED — Write Failing Tests First

- [ ] Task 0: Verify Dependencies (PREREQUISITE) <!-- id: prereq -->
  - [ ] Confirm `cryptography>=42.0.0` in `pyproject.toml` (already present from Story 1.6)
  - [ ] Verify: `python -c "from cryptography.hazmat.primitives.ciphers.aead import AESGCM; print('OK')"`

- [ ] Task 1: Create Test File Structure (AC: #7) <!-- id: 0 -->
  - [ ] Create `tests/unit/storage/test_evidence_store.py`
  - [ ] Ensure `tests/unit/storage/__init__.py` exists
  - [ ] Import pytest and required testing utilities

- [ ] Task 2: Write Failing Evidence Store Initialization Tests (AC: #3) <!-- id: 1 -->
  - [ ] Test `EvidenceStore.__init__(engagement_id, encryption_key)` creates directory structure
  - [ ] Test evidence directory created at `~/.cyber-red/evidence/{engagement_id}/`
  - [ ] Test manifest.json is created if not exists
  - [ ] Test manifest.json is loaded if exists
  - [ ] Test invalid encryption_key raises `ValueError`
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 3: Write Failing Evidence Storage Tests (AC: #2, #4, #5, #6) <!-- id: 2 -->
  - [ ] Test `store_evidence(content, filename, source_agent, evidence_type)` returns `EvidenceItem`
  - [ ] Test file is encrypted with AES-256-GCM
  - [ ] Test SHA-256 hash is calculated and stored in manifest
  - [ ] Test manifest entry includes: id, filename, sha256_hash, timestamp, source_agent, evidence_type
  - [ ] Test encrypted file is written to `{engagement_id}/data/{uuid}.enc`
  - [ ] Test evidence_type enum: "screenshot", "log", "loot", "other"
  - [ ] Test large file storage (1MB+)
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 4: Write Failing Evidence Retrieval Tests (AC: #4, #5) <!-- id: 3 -->
  - [ ] Test `get_evidence(evidence_id)` returns decrypted content
  - [ ] Test `get_evidence()` with wrong key raises `DecryptionError`
  - [ ] Test `get_evidence()` with tampered file raises `IntegrityError`
  - [ ] Test `verify_integrity(evidence_id)` validates SHA-256 hash
  - [ ] Test `list_evidence()` returns all evidence items sorted by timestamp
  - [ ] Test `list_evidence(evidence_type=...)` filters by type
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 5: Write Failing Manifest Tests (AC: #5, #6) <!-- id: 4 -->
  - [ ] Test manifest.json structure: `{"version": "1.0", "engagement_id": ..., "evidence": [...]}`
  - [ ] Test manifest atomic write (crash safety)
  - [ ] Test manifest includes UTC ISO8601 timestamps
  - [ ] Test manifest re-loading after restart preserves all entries
  - [ ] Test `get_manifest_hash()` returns SHA-256 of entire manifest
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 6: Write Failing Integration Test (AC: all) <!-- id: 5 -->
  - [ ] Create `tests/integration/storage/test_evidence_store_integration.py`
  - [ ] Test full cycle: store → verify → retrieve → verify integrity
  - [ ] Test with multiple evidence types
  - [ ] Test concurrent storage operations
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

### Phase 2: GREEN — Implement to Pass Tests

- [ ] Task 7: Create EvidenceItem Dataclass (AC: #6) <!-- id: 6 -->
  - [ ] Create `src/cyberred/storage/evidence_store.py` (new file, separate from existing evidence.py)
  - [ ] Import from `dataclasses`, `datetime`, `pathlib`, `enum`
  - [ ] Create `EvidenceType` enum: SCREENSHOT, LOG, LOOT, OTHER
  - [ ] Create `EvidenceItem` dataclass with fields:
    - id: str (UUID)
    - filename: str
    - sha256_hash: str
    - encrypted_path: Path
    - nonce: bytes
    - size_bytes: int
    - timestamp: datetime
    - source_agent: str
    - evidence_type: EvidenceType
  - [ ] Implement `to_dict()` and `from_dict()` methods
  - [ ] **Run Task 2 tests — PARTIAL PASS**

- [ ] Task 8: Implement EvidenceStore Core (AC: #2, #3, #4) <!-- id: 7 -->
  - [ ] Implement `EvidenceStore.__init__(engagement_id, encryption_key, base_path=None)`
  - [ ] Default base_path: `~/.cyber-red/evidence`
  - [ ] Create directory structure: `{base_path}/{engagement_id}/data/`
  - [ ] Load or create manifest.json
  - [ ] Validate encryption_key is 32 bytes
  - [ ] **Run Task 2 tests — ALL PASSED (GREEN)**

- [ ] Task 9: Implement Evidence Storage (AC: #2, #4, #5) <!-- id: 8 -->
  - [ ] Implement `store_evidence(content: bytes, filename: str, source_agent: str, evidence_type: EvidenceType) -> EvidenceItem`
  - [ ] Generate UUID for evidence_id
  - [ ] Calculate SHA-256 hash of original content
  - [ ] Encrypt content using AES-256-GCM (reuse encrypt_data from existing evidence.py)
  - [ ] Write encrypted file to `data/{uuid}.enc`
  - [ ] Add entry to manifest
  - [ ] Save manifest atomically
  - [ ] Return EvidenceItem
  - [ ] **Run Task 3 tests — ALL PASSED (GREEN)**

- [ ] Task 10: Implement Evidence Retrieval (AC: #4, #5) <!-- id: 9 -->
  - [ ] Implement `get_evidence(evidence_id: str) -> bytes`
  - [ ] Read encrypted file
  - [ ] Decrypt using AES-256-GCM
  - [ ] Verify SHA-256 hash matches manifest
  - [ ] Raise `IntegrityError` if hash mismatch
  - [ ] Implement `verify_integrity(evidence_id: str) -> bool`
  - [ ] Implement `list_evidence(evidence_type: EvidenceType | None = None) -> list[EvidenceItem]`
  - [ ] **Run Task 4 tests — ALL PASSED (GREEN)**

- [ ] Task 11: Implement Manifest Operations (AC: #5, #6) <!-- id: 10 -->
  - [ ] Implement `_save_manifest()` with atomic write (write to tmp, rename)
  - [ ] Implement `_load_manifest()`
  - [ ] Implement `get_manifest_hash() -> str`
  - [ ] Ensure all timestamps are UTC ISO8601
  - [ ] **Run Task 5 tests — ALL PASSED (GREEN)**

- [ ] Task 12: Add IntegrityError Exception <!-- id: 11 -->
  - [ ] Add `IntegrityError` to `src/cyberred/core/exceptions.py`
  - [ ] `IntegrityError` extends `CyberRedError`
  - [ ] Include meaningful default message: "Evidence integrity check failed"

### Phase 3: REFACTOR & Export

- [ ] Task 13: Export from Storage Package (AC: all) <!-- id: 12 -->
  - [ ] Export `EvidenceStore`, `EvidenceItem`, `EvidenceType` from `storage/__init__.py`
  - [ ] Export `IntegrityError` from `core/__init__.py`
  - [ ] Add to `__all__` lists
  - [ ] Verify no circular imports

- [ ] Task 14: Validate 100% Test Coverage <!-- id: 13 -->
  - [ ] Run `pytest tests/unit/storage/test_evidence_store.py --cov=src/cyberred/storage/evidence_store --cov-report=term-missing --cov-fail-under=100`
  - [ ] Ensure 100% line coverage on `evidence_store.py`
  - [ ] Add any missing edge case tests

- [ ] Task 15: Run Integration Tests <!-- id: 14 -->
  - [ ] Run `pytest tests/integration/storage/test_evidence_store_integration.py --cov=src/cyberred/storage/evidence_store --cov-report=term-missing`
  - [ ] Verify all integration tests pass
  - [ ] Verify no mocks used in integration tests (real file I/O)

## Dev Notes

### Architecture Context

This story implements evidence storage per Epic 13 architecture:
```
storage/evidence.py — Evidence files + SHA-256 manifest
```

**Note:** The existing `src/cyberred/storage/evidence.py` is for Story 11.2 (Exfiltrated Data Browser). This story creates a NEW file `evidence_store.py` specifically for evidence file storage with SHA-256 manifests as defined in FR36.

**Why evidence_store is critical:**
- **FR36**: Evidence files + SHA-256 manifest
- **NFR14**: Data at rest protected with AES-256
- Story 13.2 (Append-Only Audit Log) will reference evidence stored here
- Story 13.10 (Timestamp Integrity) will integrate with evidence timestamps
- Story 13.11 (Chain of Custody) **depends on this story** for tracking evidence access

### File Locations

Per architecture section and Epic 13 components:
```
src/cyberred/storage/
├── evidence.py          # Story 11.2 - Exfiltrated data (EXISTING)
├── evidence_store.py    # Story 13.1 - Evidence storage (THIS STORY - NEW)
├── audit.py             # Story 13.2 - Audit log (depends on this)
├── checkpoint.py        # Story 13.3 - SQLite checkpoints (EXISTING)
```

Evidence directory structure:
```
~/.cyber-red/evidence/{engagement_id}/
├── manifest.json        # SHA-256 hashes, metadata
├── data/
│   ├── {uuid1}.enc      # Encrypted screenshot
│   ├── {uuid2}.enc      # Encrypted log
│   └── {uuid3}.enc      # Encrypted loot
```

### Technical Specifications

**Evidence Storage:**
- Directory: `~/.cyber-red/evidence/{engagement_id}/`
- Encryption: AES-256-GCM (reuse from `evidence.py`)
- Nonce: 12 bytes (96 bits, GCM standard)
- Hash: SHA-256 of original plaintext

**Manifest Format:**
```json
{
  "version": "1.0",
  "engagement_id": "eng-uuid-here",
  "created_at": "2026-02-12T02:21:00Z",
  "evidence": [
    {
      "id": "uuid-1",
      "filename": "screenshot_192.168.1.1.png",
      "sha256_hash": "abc123...",
      "encrypted_path": "data/uuid-1.enc",
      "nonce": "hex-encoded-nonce",
      "size_bytes": 12345,
      "timestamp": "2026-02-12T02:22:00Z",
      "source_agent": "recon-agent-01",
      "evidence_type": "screenshot"
    }
  ]
}
```

**Evidence Types:**
- `screenshot`: Screen captures, terminal output images
- `log`: Tool output, command logs
- `loot`: Collected files, credentials (distinct from exfiltrated data in 11.2)
- `other`: Miscellaneous evidence

### Library Requirements

**Already in pyproject.toml (from Story 1.6):**
```toml
"cryptography>=42.0.0",  # Provides AES-GCM
```

**Import Pattern:**
```python
import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from cyberred.core.exceptions import DecryptionError, IntegrityError
```

### Reuse from Existing Code

From `src/cyberred/storage/evidence.py` (Story 11.2):
- `encrypt_data(data, key) -> (ciphertext, nonce)` — reuse directly
- `decrypt_data(ciphertext, key, nonce) -> bytes` — reuse directly
- `NONCE_LENGTH = 12` — constant
- `SecureBuffer` — for secure memory handling

```python
from cyberred.storage.evidence import encrypt_data, decrypt_data, NONCE_LENGTH
```

### Previous Story Patterns (from Story 1.6)

- Module exports via `storage/__init__.py` with `__all__` list
- Exception hierarchy extends `CyberRedError`
- Unit tests in `tests/unit/storage/test_<module>.py`
- Integration tests in `tests/integration/storage/test_<module>_integration.py`
- 100% coverage requirement enforced via pytest-cov
- Atomic file writes using temp file + rename pattern

### Anti-Patterns to Avoid

1. **NEVER** store unencrypted evidence to disk
2. **NEVER** skip hash verification on retrieval
3. **NEVER** use non-atomic manifest writes (risk data loss on crash)
4. **NEVER** use local time (always UTC)
5. **NEVER** generate UUIDs with predictable patterns
6. **NEVER** log evidence content (even in debug mode)
7. **DO NOT** modify existing `evidence.py` — create new `evidence_store.py`

### Dependency Chain

```
Story 1.6 (Keystore) → Story 13.1 (Evidence Storage) → Story 13.2 (Audit Log)
                                                     → Story 13.10 (Timestamp Integrity)
                                                     → Story 13.11 (Chain of Custody)
```

### References

- [Epic 13: Evidence, Reporting & Audit](_bmad-output/planning-artifacts/epics-stories.md#epic-13-evidence-reporting--audit)
- [Story 13.1 Definition](_bmad-output/planning-artifacts/epics-stories.md#story-131-evidence-file-storage)
- [Architecture: storage/evidence.py](_bmad-output/planning-artifacts/architecture.md)
- [Story 1.6 Pattern](_bmad-output/implementation-artifacts/1-6-keystore-pbkdf2-key-derivation.md)
- [Existing evidence.py](src/cyberred/storage/evidence.py) — reuse encryption functions
- [cryptography AESGCM docs](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM)

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

- `src/cyberred/storage/evidence_store.py` (NEW)
- `src/cyberred/storage/__init__.py` (MODIFIED — export new classes)
- `src/cyberred/core/exceptions.py` (MODIFIED — add IntegrityError)
- `src/cyberred/core/__init__.py` (MODIFIED — export IntegrityError)
- `tests/unit/storage/test_evidence_store.py` (NEW)
- `tests/integration/storage/test_evidence_store_integration.py` (NEW)

## Change Log

| Date | Change |
|------|--------|
| 2026-02-12 | Story created with comprehensive context from architecture.md, epics-stories.md, existing evidence.py patterns, and Story 1.6 TDD methodology. |
