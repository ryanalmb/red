# Story 2.8: Stop & Checkpoint (Cold State)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **to stop an engagement with checkpoint for later resume**,
So that **I can recover from system restarts (FR54, NFR33)**.

## Acceptance Criteria

1. **Given** an engagement is RUNNING or PAUSED
2. **When** I run `cyber-red stop {id}`
3. **Then** engagement transitions to STOPPED
4. **And** full state is written to SQLite checkpoint file
5. **And** checkpoint includes agent states, findings, scope hash
6. **And** checkpoint is signed with SHA-256 for integrity
7. **When** daemon restarts
8. **Then** stopped engagements are listed and resumable
9. **And** integration tests verify checkpoint/restore cycle

## Tasks / Subtasks

> [!IMPORTANT]
> **COLD STATE = DISK (SQLite)** — Full state persisted to checkpoint file for daemon restart recovery. This is the key difference from Story 2.7 (Hot State / RAM-only).

### Phase 1: Core Infrastructure & Utilities

- [x] Task 1: Create `core/hashing.py` Utility (Enhancement)
  - [x] Create `src/cyberred/core/hashing.py`
  - [x] Implement `calculate_file_hash(path: Path, algorithm: str = "sha256") -> str`
  - [x] Implement `calculate_bytes_hash(data: bytes, algorithm: str = "sha256") -> str`
  - [x] Add type stubs and docstrings
  - [x] Verification: Unit tests verify correct hash calculation

- [x] Task 2: Create `storage/` Module & Checkpoint Infrastructure (AC: #4, #5)
  - [x] Create `src/cyberred/storage/__init__.py` with exports
  - [x] Create `src/cyberred/storage/checkpoint.py`
  - [x] Define `CheckpointManager` class with initialization
  - [x] Configure SQLite WAL mode for concurrent reads
  - [x] Implement checkpoint directory structure: `~/.cyber-red/engagements/{id}/checkpoint.sqlite`
  - [x] Verification: Module imports work, WAL mode verified

- [x] Task 3: Define Checkpoint Schema (AC: #5)
  - [x] Create `CheckpointSchema` dataclass for serialization structure
  - [x] Tables: `metadata`, `agents`, `findings`, `audit_log`
  - [x] `metadata` table: engagement_id, scope_hash (SHA-256), created_at, version, signature
  - [x] `agents` table: agent_id, state_json, last_action_id, decision_context
  - [x] `findings` table: finding_id, finding_json, timestamp
  - [x] Create schema migration with Alembic (or embedded version check)
  - [x] Add indexes for engagement_id lookups
  - [x] Verification: Schema creates successfully

### Phase 2: Checkpoint Write Implementation

- [x] Task 4: Implement `CheckpointManager.save()` (AC: #4, #5, #6)
  - [x] Method signature: `async def save(engagement_context: EngagementContext) -> Path`
  - [x] Serialize agent states to JSON
  - [x] Serialize findings to JSON
  - [x] Calculate scope file SHA-256 hash using `core.hashing.calculate_file_hash`
  - [x] Write all data to SQLite tables atomically
  - [x] Calculate checkpoint file SHA-256 signature using `core.hashing.calculate_file_hash`
  - [x] Store signature in metadata table
  - [x] Return checkpoint file path
  - [x] Verification: Checkpoint file created with all data

- [x] Task 5: Integrate Checkpoint into `SessionManager.stop_engagement()` (AC: #3, #4)
  - [x] Inject `CheckpointManager` into `SessionManager` (constructor or dependency)
  - [x] Modify `stop_engagement()` to call `checkpoint_manager.save()` before state transition
  - [x] Update method signature to return `tuple[EngagementState, Path]` (state + checkpoint path)
  - [x] Log checkpoint path on success
  - [x] Handle checkpoint errors (raise or return error status)
  - [x] Verification: `stop_engagement()` creates checkpoint file

### Phase 3: Checkpoint Restore Implementation

- [x] Task 6: Implement `CheckpointManager.load()` (AC: #7, #8)
  - [x] Method signature: `async def load(checkpoint_path: Path) -> CheckpointData`
  - [x] Verify checkpoint file exists
  - [x] Verify SHA-256 signature matches file content (use `core.hashing`)
  - [x] Extract scope_hash from metadata
  - [x] Calculate current scope file hash
  - [x] If scope changed: raise `CheckpointScopeChangedError` (new exception)
  - [x] Deserialize agent states from JSON
  - [x] Deserialize findings from JSON
  - [x] Return `CheckpointData` object with all restored state
  - [x] Verification: Load restores exact state from file

- [x] Task 7: Implement `CheckpointManager.verify()` (AC: #6)
  - [x] Method signature: `def verify(checkpoint_path: Path) -> bool`
  - [x] Read file and calculate SHA-256 using `core.hashing`
  - [x] Compare to stored signature
  - [x] Return True if valid, False if tampered
  - [x] Verification: Tampered files detected

### Phase 4: Daemon Restart Recovery

- [x] Task 8: Implement Engagement Discovery on Daemon Start (AC: #7, #8)
  - [x] Update `DaemonServer.__init__()` or startup sequence
  - [x] Scan `~/.cyber-red/engagements/*/checkpoint.sqlite` for existing checkpoints
  - [x] For each checkpoint: verify integrity, load metadata
  - [x] Register STOPPED engagements in `SessionManager` without starting them
  - [x] Log discovered engagements
  - [x] Verification: Daemon restart lists previously stopped engagements

- [x] Task 9: Implement `SessionManager.restore_engagement()` (AC: #7, #8)
  - [x] Method signature: `async def restore_engagement(engagement_id: str, checkpoint_path: Path) -> str`
  - [x] Load checkpoint data
  - [x] Recreate `EngagementContext` from checkpoint
  - [x] Verify scope hash (optionally warn if changed)
  - [x] register engagement in STOPPED state
  - [x] Return engagement ID
  - [x] Verification: Restored engagement matches original

### Phase 5: CLI Enhancement

- [x] Task 10: Update `stop` CLI Command Output (AC: #2, #3)
  - [x] Update `src/cyberred/cli.py` function `stop_engagement()` (lines 368-378)
  - [x] Capture checkpoint_path from IPC response
  - [x] Print `Engagement {id} stopped (checkpoint saved)`
  - [x] Print `Checkpoint: {checkpoint_path}`
  - [x] Handle checkpoint failure: print `Error: Failed to create checkpoint`, exit(1)
  - [x] Verification: CLI shows checkpoint location

### Phase 6: Server Handler Update

- [x] Task 11: Update `ENGAGEMENT_STOP` IPC Handler (AC: #4)
  - [x] Modify handler in `src/cyberred/daemon/server.py`
  - [x] Call `session_manager.stop_engagement()` (which now creates checkpoint)
  - [x] Include `checkpoint_path` in response data
  - [x] Handle checkpoint creation errors
  - [x] Verification: IPC returns checkpoint path

### Phase 7: Unit Tests

- [x] Task 12: Unit Tests for Infrastructure
  - [x] Create `tests/unit/core/test_hashing.py`
  - [x] Create `tests/unit/storage/test_checkpoint.py`
  - [x] Test hashing utility thoroughly
  - [x] Test checkpoint save/load/verify with real file I/O
  - [x] Test scope change detection logic
  - [x] Verification: Infrastructure tests pass

- [x] Task 13: Unit Tests for `SessionManager` Stop Integration
  - [x] Update `tests/unit/daemon/test_session_manager.py`
  - [x] Test: `test_stop_engagement_creates_checkpoint`
  - [x] Test: `test_stop_engagement_returns_checkpoint_path`
  - [x] Test: `test_restore_engagement_loads_from_checkpoint`
  - [x] Verification: All session manager tests pass

### Phase 8: Integration Tests

- [x] Task 14: Integration Test for Checkpoint/Restore Cycle (AC: #9)
  - [x] Create `tests/integration/daemon/test_checkpoint.py`
  - [x] Test: `test_stop_and_restart_cycle`
    - Create engagement → Start → Stop with checkpoint
    - Simulate daemon restart (reinitialize SessionManager)
    - Verify engagement listed as STOPPED
    - Verify checkpoint integrity
  - [x] Test: `test_checkpoint_survives_daemon_restart`
  - [x] Test: `test_tampered_checkpoint_rejected`
  - [x] Test: `test_scope_changed_since_checkpoint_warning`
  - [x] Mark with `@pytest.mark.integration`
  - [x] Verification: `pytest tests/integration/daemon/test_checkpoint.py -v` passes

### Phase 9: Coverage Gate

- [x] Task 15: Achieve 100% Test Coverage
  - [x] Run `pytest --cov=src/cyberred/storage --cov=src/cyberred/core/hashing.py --cov=src/cyberred/daemon/session_manager --cov-report=term-missing`
  - [x] Identify and cover any missing lines
  - [x] Verification: 100% coverage for storage/, hashing.py, and session_manager.py

## Dev Notes

### Architecture Context

- **Cold State**: Disk-based (SQLite with WAL mode), contrast with PAUSED (hot state) which is RAM-only (Story 2.7)
- **NFR33**: System restart recovery — all paused/stopped engagements recoverable after daemon restart
- **FR54**: System can resume engagement from saved state after interruption
- **State Machine**: RUNNING/PAUSED → STOPPED transition already implemented in `state_machine.py`

### Exception Handling (IMPROVED)

- **Reuse `CheckpointIntegrityError`**: Do NOT create this exception. It already exists in `src/cyberred/core/exceptions.py`. Import and iterate on it if needed.
- **Create `CheckpointScopeChangedError`**: Create this NEW exception in `src/cyberred/core/exceptions.py` inheriting from `CheckpointIntegrityError`.

### Hashing Utility (IMPROVED)

- Use the new `src/cyberred/core/hashing.py` for all SHA-256 operations.
- Avoid implementing ad-hoc hashing in `checkpoint.py`.
- This ensures consistency for Epic 13 (Evidence/Audit).

### SQLite Schema Design (Per Architecture)

```sql
-- metadata table
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Keys: engagement_id, scope_hash, created_at, schema_version, signature

-- agents table  
CREATE TABLE agents (
    agent_id TEXT PRIMARY KEY,
    agent_type TEXT NOT NULL,
    state_json TEXT NOT NULL,
    last_action_id TEXT,
    decision_context TEXT,
    updated_at TEXT NOT NULL
);

-- findings table
CREATE TABLE findings (
    finding_id TEXT PRIMARY KEY,
    finding_json TEXT NOT NULL,
    agent_id TEXT,
    timestamp TEXT NOT NULL
);
```

### Checkpoint Integrity (Security-Critical)

Per architecture (lines 429-436):
1. Verify SHA-256 signature of checkpoint file
2. Validate scope file hash matches checkpoint's recorded scope
3. If scope changed since checkpoint, raise `CheckpointScopeChangedError` (fail safe) -> Operator must confirm override (future story)
4. Reject tampered or unsigned checkpoints with `CheckpointIntegrityError`

### Project Structure Notes

**New files to create:**
- `src/cyberred/core/hashing.py` (New utility)
- `src/cyberred/storage/__init__.py`
- `src/cyberred/storage/checkpoint.py`
- `tests/unit/core/test_hashing.py`
- `tests/unit/storage/test_checkpoint.py`
- `tests/integration/daemon/test_checkpoint.py`

**Files to modify:**
- `src/cyberred/core/exceptions.py` (Add CheckpointScopeChangedError)
- `src/cyberred/daemon/session_manager.py` — Add checkpoint integration
- `src/cyberred/daemon/server.py` — Update ENGAGEMENT_STOP handler
- `src/cyberred/cli.py` — Update stop command output

### References

- [Architecture: Checkpoint Verification](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L429-L436)
- [Architecture: Engagement Storage Structure](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L156-L165)
- [Existing Exceptions](file:///root/red/src/cyberred/core/exceptions.py)
