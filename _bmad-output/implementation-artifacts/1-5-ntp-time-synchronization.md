# Story 1.5: NTP Time Synchronization

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **NTP-synchronized timestamps with drift detection**,
So that **audit trails have cryptographically verifiable timestamps (NFR16)**.

## Acceptance Criteria

1. **Given** NTP servers are reachable
2. **When** I call `time.now()`
3. **Then** timestamp is NTP-synchronized (not local system time)
4. **And** timestamps are ISO 8601 formatted
5. **And** drift detection warns if local clock diverges >1s
6. **And** `time.sign_timestamp()` produces cryptographic signature
7. **And** integration test verifies NTP sync

## Tasks / Subtasks

- [x] Create Time Module (AC: #1, #2, #3, #4) <!-- id: 0 -->
  - [x] Create `src/cyberred/core/time.py`
  - [x] Implement `TrustedTime` class for NTP synchronization
  - [x] Implement `now()` function returning NTP-synced datetime
  - [x] Format all timestamps as ISO 8601 (e.g., `2025-12-31T23:59:59.123456Z`)
  - [x] Add configurable NTP server pool (default: `pool.ntp.org`)
  - [x] Integration with `core.config.Settings` (retrieve `ntp_server` from config)

- [x] Implement NTP Synchronization (AC: #1, #3) <!-- id: 1 -->
  - [x] Use `ntplib` library for NTP queries
  - [x] Query NTP server and calculate offset from local time
  - [x] Cache NTP offset with configurable TTL (default: 60s)
  - [x] Apply offset to local time for all `now()` calls
  - [x] Handle NTP server unreachability gracefully

- [x] Implement Drift Detection (AC: #5) <!-- id: 2 -->
  - [x] Track offset between NTP time and local system time
  - [x] Log WARNING if drift exceeds 1 second threshold
  - [x] Log ERROR if drift exceeds 5 seconds (severe)
  - [x] Implement `get_drift()` method returning current offset
  - [x] Implement `is_synced` property (bool) for external status checks
  - [x] Add drift threshold configuration option

- [x] Implement Local Time Fallback (AC: #1) <!-- id: 3 -->
  - [x] If NTP unreachable, fallback to local system time
  - [x] Log WARNING when using fallback (degraded mode)
  - [x] Set `is_ntp_synced` flag to False during fallback
  - [x] Retry NTP sync periodically (every 30s) during fallback
  - [x] Track fallback duration for observability

- [x] Implement Timestamp Signing (AC: #6) <!-- id: 4 -->
  - [x] Create `sign_timestamp(timestamp: str, key: bytes) -> str` function
  - [x] Use HMAC-SHA256 for signature generation
  - [x] Include timestamp + key in signature computation
  - [x] Return base64-encoded signature string
  - [x] Create `verify_timestamp_signature()` for validation

- [x] Export from Core Package (AC: all) <!-- id: 5 -->
  - [x] Export `TrustedTime`, `now`, `sign_timestamp`, `verify_timestamp_signature` from `core/__init__.py`
  - [x] Add to `__all__` list
  - [x] Verify no circular imports

- [x] Create Unit Tests <!-- id: 6 -->
  - [x] Create `tests/unit/core/test_time.py`
  - [x] Test `now()` returns ISO 8601 formatted string
  - [x] Test `now()` applies NTP offset to local time
  - [x] Test drift detection warns at >1s threshold
  - [x] Test fallback to local time when NTP unreachable
  - [x] Test `sign_timestamp()` produces valid HMAC-SHA256
  - [x] Test `verify_timestamp_signature()` validates signatures
  - [x] Test signature verification fails on tampered timestamps
  - [x] Mock `ntplib` to avoid real NTP calls in unit tests

- [x] Create Integration Tests (AC: #7) <!-- id: 7 -->
  - [x] Create `tests/integration/test_time_ntp.py`
  - [x] Test actual NTP synchronization with real NTP servers
  - [x] Test drift detection with simulated clock skew
  - [x] Mark integration tests with `@pytest.mark.integration`
  - [x] Skip gracefully if NTP servers unreachable in CI

## Dev Notes

### Architecture Context

This story implements the NTP time synchronization module per architecture (line 785):
```
core/time.py — NTP sync wrapper with drift detection
```

**Why NTP synchronization is critical:**
- **FR50**: System must maintain timestamped audit trail (NTP-synchronized, cryptographically signed)
- **NFR16**: Timestamp integrity — NTP-synchronized, cryptographically signed (Hard requirement)
- Audit logs must be forensically valid — local system time can be spoofed

### File Location

Per architecture section 5.1:
```
src/cyberred/core/
├── time.py              # NTP sync wrapper with drift detection (THIS STORY)
├── config.py            # Already exists (Story 1.3)
├── exceptions.py        # Already exists (Story 1.1)
├── models.py            # Already exists (Story 1.2)
```

### References

- [Architecture: core/time.py](file:///root/red/docs/3-solutioning/architecture.md#L785)
- [Architecture: Audit NTP-synced](file:///root/red/docs/3-solutioning/architecture.md#L1162)
- [PRD: NFR16 Timestamp Integrity](file:///root/red/docs/2-plan/prd.md#L1368)

## Dev Agent Record

### Agent Model Used

Gemini 2.5 Pro

### Debug Log References

### Completion Notes List

- ✅ Created `src/cyberred/core/time.py` with `TrustedTime` class
- ✅ Implemented NTP synchronization via `ntplib` library
- ✅ Added drift detection with WARNING (>1s) and ERROR (>5s) thresholds
- ✅ Implemented fallback to local time when NTP unreachable
- ✅ Added HMAC-SHA256 timestamp signing and verification
- ✅ Exported `TrustedTime`, `now`, `sign_timestamp`, `verify_timestamp_signature` from `core/__init__.py`
- ✅ Created 23 unit tests in `tests/unit/core/test_time.py` with 100% coverage on time.py
- ✅ Created 6 integration tests in `tests/integration/test_time_ntp.py` with real NTP servers
- ✅ All 29 tests pass
- ✅ Added `ntplib>=0.4.0` dependency to `pyproject.toml`
- ✅ [Code Review Fix] Implemented `NTPConfig` in `src/cyberred/core/config.py`
- ✅ [Code Review Fix] Integrated `time.py` with `get_settings()`

### File List

- `src/cyberred/core/time.py` (NEW)
- `src/cyberred/core/config.py` (MODIFIED)
- `src/cyberred/core/__init__.py` (MODIFIED)
- `tests/unit/core/__init__.py` (NEW)
- `tests/unit/core/test_time.py` (NEW)
- `tests/integration/__init__.py` (NEW)
- `tests/integration/test_time_ntp.py` (NEW)
- `pyproject.toml` (MODIFIED)

## Change Log

| Date | Change |
|------|--------|
| 2026-01-01 | Story created with comprehensive context from architecture.md, epics-stories.md, and Story 1.4 patterns. |
| 2026-01-01 | Implementation complete: TrustedTime class with NTP sync, drift detection, fallback, HMAC-SHA256 signing. 29 tests passing, 100% coverage on time.py. |
