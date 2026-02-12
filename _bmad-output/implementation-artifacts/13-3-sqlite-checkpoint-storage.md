# Story 13.3: SQLite Checkpoint Storage

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **SQLite-based checkpoint storage for session persistence**,
So that **engagement state survives restarts (FR40)**.

## Acceptance Criteria

1. **Given** engagement is running
2. **When** checkpoint interval (60s) elapses or major state change occurs
3. **Then** checkpoint is written to SQLite
4. **And** SQLite uses WAL mode for concurrent reads
5. **And** async write queue prevents blocking main thread
6. **And** checkpoint includes: agent states, findings, scope, config
7. **And** integration tests verify checkpoint restore

## Tasks / Subtasks

> [!IMPORTANT]
> **RED-GREEN TDD METHODOLOGY REQUIRED**
> Each task MUST follow strict TDD: Write failing tests FIRST (RED), then implement code to pass (GREEN), then refactor.

### Phase 1: RED — Write Failing Tests First

- [ ] Task 0: Verify Existing Implementation (PREREQUISITE) <!-- id: prereq -->
  - [ ] Confirm `checkpoint.py` exists with `CheckpointManager` class
  - [ ] Confirm `schema.py` exists with `CURRENT_SCHEMA_VERSION = "2.0.0"`
  - [ ] Verify existing tests pass: `pytest tests/unit/storage/test_checkpoint.py -v`
  - [ ] Identify gaps: interval trigger, async queue, config storage

- [ ] Task 1: Write Failing Checkpoint Scheduler Tests (AC: #2) <!-- id: 1 -->
  - [ ] Create `tests/unit/storage/test_checkpoint_scheduler.py`
  - [ ] Test `CheckpointScheduler.__init__(manager, interval_seconds=60)` creates scheduler
  - [ ] Test `start()` begins background checkpoint timer
  - [ ] Test `stop()` cancels timer gracefully
  - [ ] Test checkpoint triggered automatically after 60s interval
  - [ ] Test checkpoint triggered on `trigger_now()` for major state changes
  - [ ] Test interval reset after manual trigger
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 2: Write Failing Async Write Queue Tests (AC: #5) <!-- id: 2 -->
  - [ ] Create `tests/unit/storage/test_checkpoint_queue.py`
  - [ ] Test `AsyncCheckpointQueue.__init__(manager, max_queue_size=10)` creates queue
  - [ ] Test `enqueue(engagement_id, agents, findings, config)` returns immediately
  - [ ] Test enqueue does NOT block caller (measure time < 10ms)
  - [ ] Test queue processes writes in background worker
  - [ ] Test queue coalesces multiple writes for same engagement_id
  - [ ] Test `flush()` waits for pending writes to complete
  - [ ] Test queue overflow drops oldest unprocessed item (with warning log)
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 3: Write Failing Config Storage Tests (AC: #6) <!-- id: 3 -->
  - [ ] Add tests to `tests/unit/storage/test_checkpoint.py` (existing file)
  - [ ] Test `CheckpointManager.save()` accepts `config: dict[str, Any]` parameter
  - [ ] Test config is stored in checkpoint SQLite database
  - [ ] Test `CheckpointManager.load()` returns `CheckpointData` with config field
  - [ ] Test config includes: engagement settings, roe hash, models config
  - [ ] Test config is JSON serialized correctly (handles datetime, sets, bytes)
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 4: Write Failing State Change Trigger Tests (AC: #2) <!-- id: 4 -->
  - [ ] Test `trigger_checkpoint_on_state_change()` fires on PAUSED state
  - [ ] Test `trigger_checkpoint_on_state_change()` fires on STOPPED state  
  - [ ] Test `trigger_checkpoint_on_state_change()` fires on critical finding (severity=critical)
  - [ ] Test NO checkpoint on minor state changes (agent heartbeat, info finding)
  - [ ] Test debounce: multiple rapid triggers coalesce to single write
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 5: Write Failing Integration Tests (AC: #7) <!-- id: 5 -->
  - [ ] Create `tests/integration/storage/test_checkpoint_restore.py`
  - [ ] Test full cycle: create engagement → save checkpoint → load checkpoint → verify state matches
  - [ ] Test checkpoint restore after simulated crash (kill process, restart)
  - [ ] Test concurrent checkpoint reads during write (WAL mode validation)
  - [ ] Test checkpoint with 100+ agents and 1000+ findings (scale test)
  - [ ] Test restore with scope hash mismatch raises `CheckpointScopeChangedError`
  - [ ] Test restore with schema version mismatch raises `IncompatibleSchemaError`
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

### Phase 2: GREEN — Implement to Pass Tests

- [ ] Task 6: Extend CheckpointData for Config (AC: #6) <!-- id: 6 -->
  - [ ] Modify `CheckpointData` dataclass in `checkpoint.py`:
    ```python
    @dataclass
    class CheckpointData:
        engagement_id: str
        scope_hash: str
        created_at: datetime
        schema_version: str
        agents: list[AgentState] = field(default_factory=list)
        findings: list[Finding] = field(default_factory=list)
        config: dict[str, Any] = field(default_factory=dict)  # NEW
    ```
  - [ ] Add `config` table to `schema.py` or store in metadata
  - [ ] Update `save()` to serialize and store config
  - [ ] Update `load()` to deserialize and return config
  - [ ] Update signature calculation to include config
  - [ ] **Run Task 3 tests — ALL PASSED (GREEN)**

- [ ] Task 7: Implement AsyncCheckpointQueue (AC: #5) <!-- id: 7 -->
  - [ ] Create `src/cyberred/storage/checkpoint_queue.py`
  - [ ] Implement `AsyncCheckpointQueue` class:
    ```python
    class AsyncCheckpointQueue:
        def __init__(self, manager: CheckpointManager, max_queue_size: int = 10):
            self._manager = manager
            self._queue: asyncio.Queue[CheckpointRequest] = asyncio.Queue(max_queue_size)
            self._pending: dict[str, CheckpointRequest] = {}  # Coalesce by engagement_id
            self._worker_task: Optional[asyncio.Task] = None
        
        async def enqueue(self, engagement_id: str, ...) -> None: ...
        async def flush(self) -> None: ...
        async def _worker(self) -> None: ...
    ```
  - [ ] Use `asyncio.Queue` for non-blocking enqueue
  - [ ] Implement coalescing: newer request replaces older for same engagement_id
  - [ ] Implement background worker with `asyncio.create_task()`
  - [ ] Log warning on queue overflow, drop oldest
  - [ ] **Run Task 2 tests — ALL PASSED (GREEN)**

- [ ] Task 8: Implement CheckpointScheduler (AC: #2) <!-- id: 8 -->
  - [ ] Create `src/cyberred/storage/checkpoint_scheduler.py`
  - [ ] Implement `CheckpointScheduler` class:
    ```python
    class CheckpointScheduler:
        def __init__(
            self,
            queue: AsyncCheckpointQueue,
            interval_seconds: int = 60,
        ):
            self._queue = queue
            self._interval = interval_seconds
            self._timer_task: Optional[asyncio.Task] = None
            self._last_checkpoint: datetime = datetime.min
        
        async def start(self) -> None: ...
        async def stop(self) -> None: ...
        async def trigger_now(self) -> None: ...
    ```
  - [ ] Use `asyncio.sleep()` for interval timing
  - [ ] Reset interval on manual `trigger_now()` call
  - [ ] **Run Task 1 tests — ALL PASSED (GREEN)**

- [ ] Task 9: Implement State Change Triggers (AC: #2) <!-- id: 9 -->
  - [ ] Add `CheckpointTrigger` enum: `INTERVAL`, `STATE_CHANGE`, `CRITICAL_FINDING`, `MANUAL`
  - [ ] Implement `should_trigger_checkpoint(event_type, event_data) -> bool`
  - [ ] Implement debounce logic with configurable window (default 5s)
  - [ ] Connect to daemon state machine events (import from daemon/state_machine.py)
  - [ ] **Run Task 4 tests — ALL PASSED (GREEN)**

- [ ] Task 10: Run Integration Tests (AC: #7) <!-- id: 10 -->
  - [ ] **Run Task 5 integration tests — ALL PASSED (GREEN)**
  - [ ] Verify WAL mode allows concurrent reads during write
  - [ ] Verify 100+ agent scale test completes in < 5s
  - [ ] Verify all error conditions raise correct exceptions

### Phase 3: REFACTOR & Export

- [ ] Task 11: Export from Storage Package <!-- id: 11 -->
  - [ ] Export `AsyncCheckpointQueue`, `CheckpointScheduler`, `CheckpointTrigger` from `storage/__init__.py`
  - [ ] Add to `__all__` lists
  - [ ] Verify no circular imports

- [ ] Task 12: Validate 100% Test Coverage <!-- id: 12 -->
  - [ ] Run `pytest tests/unit/storage/test_checkpoint*.py --cov=src/cyberred/storage/checkpoint --cov=src/cyberred/storage/checkpoint_queue --cov=src/cyberred/storage/checkpoint_scheduler --cov-report=term-missing --cov-fail-under=100`
  - [ ] Ensure 100% line coverage on all checkpoint modules
  - [ ] Add any missing edge case tests

- [ ] Task 13: Run Full Integration Test Suite <!-- id: 13 -->
  - [ ] Run `pytest tests/integration/storage/test_checkpoint*.py -v`
  - [ ] Verify all integration tests pass
  - [ ] Verify NO mocks in integration tests (real SQLite I/O)

## Dev Notes

### Architecture Context

This story extends existing checkpoint infrastructure per Epic 13 architecture:
```
storage/checkpoint.py — SQLite checkpoints (WAL mode, async write queue)
```

**CRITICAL: Existing Implementation**
The `checkpoint.py` file **already exists** with a substantial implementation:
- `CheckpointManager` class with `save()` and `load()` async methods
- SQLite WAL mode enabled via `PRAGMA journal_mode=WAL`
- SHA-256 content signature verification
- Scope hash validation with `CheckpointScopeChangedError`
- Schema version validation with `IncompatibleSchemaError`
- Atomic writes via temp file + rename pattern

**What This Story Adds:**
1. **Automatic interval trigger (60s)** — New `CheckpointScheduler` class
2. **Async write queue** — New `AsyncCheckpointQueue` class for non-blocking writes
3. **Config storage** — Extend `CheckpointData` to include engagement config
4. **State change triggers** — Fire checkpoint on PAUSED/STOPPED/critical finding
5. **Integration tests** — Verify full restore cycle

### File Locations

Per architecture and existing structure:
```
src/cyberred/storage/
├── checkpoint.py           # EXISTING - extend with config support
├── checkpoint_queue.py     # NEW - async write queue
├── checkpoint_scheduler.py # NEW - interval + trigger logic
├── schema.py               # EXISTING - may need config table
├── __init__.py             # MODIFY - export new classes
```

Checkpoint file structure (unchanged):
```
~/.cyber-red/engagements/{engagement_id}/
└── checkpoint.sqlite       # WAL mode database
```

### Technical Specifications

**Checkpoint Interval:**
- Default: 60 seconds
- Configurable via engagement config
- Reset on manual trigger or major state change

**Async Write Queue:**
- Max queue size: 10 (configurable)
- Coalesce writes for same engagement_id
- Background worker using `asyncio.create_task()`
- Graceful shutdown with `flush()` method

**State Change Triggers:**
- `PAUSED` → immediate checkpoint
- `STOPPED` → immediate checkpoint
- `CRITICAL` finding → immediate checkpoint
- Debounce window: 5 seconds (prevent rapid-fire checkpoints)

**Config Storage:**
```python
# Config fields to checkpoint
config = {
    "engagement_name": str,
    "roe_hash": str,  # Rules of engagement file hash
    "models_config": dict,  # LLM model configuration
    "scope_config": dict,  # Scope validation settings
    "created_at": datetime,
    "updated_at": datetime,
}
```

### Existing Code to Reuse

From `src/cyberred/storage/checkpoint.py`:
- `CheckpointManager` — base manager class (extend, don't replace)
- `CheckpointData` — dataclass (extend with config field)
- `CheckpointJSONEncoder` — handles datetime, sets, bytes
- `CheckpointScopeChangedError` — scope validation error
- `IncompatibleSchemaError` — schema version error
- `_calculate_content_signature()` — integrity hash (update for config)

From `src/cyberred/storage/schema.py`:
- `Base`, `Engagement`, `Agent`, `Finding` — SQLAlchemy models
- `enable_foreign_keys()` — SQLite FK enforcement
- `CURRENT_SCHEMA_VERSION = "2.0.0"` — schema version

From `src/cyberred/daemon/state_machine.py`:
- `EngagementState` enum — INITIALIZING, RUNNING, PAUSED, STOPPED, COMPLETED
- State transition events for checkpoint triggering

### Library Requirements

**Already in pyproject.toml:**
```toml
"sqlalchemy>=2.0.0",
"structlog>=24.0.0",
"aiosqlite>=0.19.0",  # For async SQLite (if not present, add)
```

**Import Pattern:**
```python
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

import structlog

from cyberred.storage.checkpoint import CheckpointManager, CheckpointData
from cyberred.daemon.state_machine import EngagementState
```

### Previous Story Patterns (from Story 13.1, 13.2)

- RED-GREEN-REFACTOR TDD cycle strictly enforced
- Unit tests in `tests/unit/storage/test_<module>.py`
- Integration tests in `tests/integration/storage/test_<module>_integration.py`
- 100% coverage requirement via pytest-cov
- Async patterns using `asyncio.Queue` and `asyncio.Task`
- structlog for logging with context binding

### Anti-Patterns to Avoid

1. **NEVER** block main thread during checkpoint write — use async queue
2. **NEVER** skip signature verification on load
3. **NEVER** checkpoint on every minor event — use debounce
4. **NEVER** ignore queue overflow — log warning and handle gracefully
5. **NEVER** leave orphan asyncio tasks — proper cleanup in `stop()`
6. **DO NOT** replace existing `CheckpointManager` — extend it
7. **DO NOT** change schema version unless adding new tables

### Dependency Chain

```
Story 2.8 (Stop & Checkpoint) → Story 13.3 (Checkpoint Storage)
                                      ↓
                               Story 13.10 (Timestamp Integrity)
                                      ↓
                               Story 13.12 (Engagement Statistics)
```

### Testing Strategy

**Unit Tests (mocked I/O):**
- `test_checkpoint_scheduler.py` — timer logic, trigger conditions
- `test_checkpoint_queue.py` — queue operations, coalescing, overflow
- `test_checkpoint.py` — config storage extension (existing + new tests)

**Integration Tests (real SQLite):**
- `test_checkpoint_restore.py` — full save/load cycle with real database
- Test concurrent access during WAL writes
- Test scale with 100+ agents, 1000+ findings
- Test crash recovery simulation

### Performance Requirements

Per architecture NFRs:
- Checkpoint save: < 500ms for typical engagement (10 agents, 100 findings)
- Checkpoint save: < 5s for large engagement (100 agents, 1000 findings)
- Queue enqueue: < 10ms (non-blocking)
- Concurrent reads during write: no blocking (WAL mode)

### References

- [Epic 13: Evidence, Reporting & Audit](_bmad-output/planning-artifacts/epics-stories.md#epic-13-evidence-reporting--audit)
- [Story 13.3 Definition](_bmad-output/planning-artifacts/epics-stories.md#story-133-sqlite-checkpoint-storage)
- [Architecture: storage/checkpoint.py](_bmad-output/planning-artifacts/architecture.md)
- [Existing checkpoint.py](src/cyberred/storage/checkpoint.py)
- [Existing schema.py](src/cyberred/storage/schema.py)
- [Story 13.1: Evidence File Storage](_bmad-output/implementation-artifacts/13-1-evidence-file-storage.md) — TDD pattern reference
- [Story 13.2: Append-Only Audit Log](_bmad-output/implementation-artifacts/13-2-append-only-audit-log.md) — async patterns reference
- [SQLite WAL Mode](https://www.sqlite.org/wal.html) — concurrent read/write documentation

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

- All unit tests pass: 35 tests in test_checkpoint_queue.py and test_checkpoint_scheduler.py
- All integration tests pass: 13 tests in test_checkpoint_restore.py
- Extra edge case tests added for coverage

### Completion Notes List

1. Implemented `AsyncCheckpointQueue` class for non-blocking checkpoint writes
2. Implemented `CheckpointScheduler` class for automatic interval-based checkpointing
3. Added `CheckpointTrigger` enum and `should_trigger_checkpoint()` function
4. Extended `CheckpointData` dataclass with `config` field
5. Updated `CheckpointManager.save()` to accept `config` parameter
6. Updated `CheckpointManager.load()` to return config in CheckpointData
7. Updated `_calculate_content_signature()` to include config in hash
8. Updated `verify()` method to validate config in signature
9. Exported new classes from `storage/__init__.py`
10. All acceptance criteria met (AC#2, AC#5, AC#6, AC#7)

### File List

- `src/cyberred/storage/checkpoint.py` (MODIFIED — extend CheckpointData with config)
- `src/cyberred/storage/checkpoint_queue.py` (NEW — async write queue)
- `src/cyberred/storage/checkpoint_scheduler.py` (NEW — interval + trigger logic)
- `src/cyberred/storage/__init__.py` (MODIFIED — export new classes)
- `tests/unit/storage/test_checkpoint_queue.py` (EXISTS — tests were pre-written)
- `tests/unit/storage/test_checkpoint_queue_extras.py` (NEW — edge case tests)
- `tests/unit/storage/test_checkpoint_scheduler.py` (EXISTS — tests were pre-written)
- `tests/unit/storage/test_checkpoint_scheduler_extras.py` (NEW — edge case tests)
- `tests/integration/storage/test_checkpoint_restore.py` (EXISTS — tests were pre-written)

## Senior Developer Review (AI)

**Reviewer:** Rovo Dev (Claude)
**Date:** 2026-02-12
**Outcome:** APPROVED WITH FIXES APPLIED

### Issues Found and Fixed

| # | Severity | Issue | Location | Fix Applied |
|---|----------|-------|----------|-------------|
| 1 | HIGH | Resource Leak - WAL/SHM files not cleaned up on delete | `checkpoint.py:661-676` | Extended `delete()` to clean up `.sqlite-wal` and `.sqlite-shm` journal files |
| 2 | HIGH | Missing scope_path in scheduler context | `checkpoint_scheduler.py:115-134` | Added `scope_path` parameter to `set_engagement_context()` and passed to queue |
| 3 | MEDIUM | Enqueue allowed when queue stopped | `checkpoint_queue.py:115-160` | Added `_running` check in `enqueue()` with warning log |
| 4 | LOW | Missing tests for scope_path flow | Tests | Added `TestSchedulerScopePath` test class |
| 5 | LOW | Missing tests for enqueue-when-stopped | Tests | Added `TestAsyncCheckpointQueueEnqueueWhenStopped` test class |
| 6 | LOW | Missing tests for WAL/SHM cleanup | Tests | Added `TestCheckpointDeleteCleanup` test class with 5 tests |

### Test Results

- All 53 tests pass (unit + integration)
- New tests added for all fixes
- No regressions introduced

### Files Modified

- `src/cyberred/storage/checkpoint.py` - WAL/SHM cleanup in delete()
- `src/cyberred/storage/checkpoint_scheduler.py` - Added scope_path support
- `src/cyberred/storage/checkpoint_queue.py` - Guard against enqueue when stopped
- `tests/unit/storage/test_checkpoint.py` - Added TestCheckpointDeleteCleanup
- `tests/unit/storage/test_checkpoint_queue.py` - Added TestAsyncCheckpointQueueEnqueueWhenStopped
- `tests/unit/storage/test_checkpoint_scheduler.py` - Added TestSchedulerScopePath

## Change Log

| Date | Change |
|------|--------|
| 2026-02-12 | **Code Review:** Fixed 6 issues (2 HIGH, 1 MEDIUM, 3 LOW). Added WAL/SHM cleanup, scope_path support, enqueue guard, and comprehensive tests. |
| 2026-02-12 | Story created with comprehensive context from existing checkpoint.py, schema.py, architecture.md, and Epic 13 patterns. Identified gaps in existing implementation and designed extensions for async queue, scheduler, and config storage. |
