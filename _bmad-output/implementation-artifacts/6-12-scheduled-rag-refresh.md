# Story 6.12: Scheduled RAG Refresh

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **automatic weekly RAG updates**,
So that **knowledge bases stay current without manual intervention (FR82)**.

## Acceptance Criteria

1. **Given** Stories 6.1-6.8 are complete
   - **When** system is running on scheduled day (default: Sunday 3AM)
   - **Then** RAG refresh triggers automatically for core sources

2. **Given** RAG scheduler is running
   - **When** refresh starts
   - **Then** refresh runs in background (no engagement interruption)
   - **And** active agent operations are not blocked

3. **Given** `config.yaml` has `rag.update_schedule` setting
   - **When** schedule is configured
   - **Then** schedule is configurable via `config.yaml`
   - **And** valid values are: `"weekly"`, `"daily"`, `"manual"`

4. **Given** RAG refresh encounters an error
   - **When** a source fails to refresh
   - **Then** refresh failure logs warning but doesn't block operations
   - **And** other sources continue to refresh
   - **And** error is captured in structured logs

5. **Given** RAG refresh completes (success or partial failure)
   - **When** refresh finishes
   - **Then** last auto-refresh timestamp is tracked
   - **And** timestamp is persisted across daemon restarts

6. **Given** RAG scheduler implementation
   - **When** tests are run
   - **Then** integration tests verify scheduled refresh mechanism

## Tasks / Subtasks

- [x] Task 1: Create RAG Scheduler Module (AC: 1, 2, 3)
  - [x] 1.1: Create `src/cyberred/rag/scheduler.py` with `RAGScheduler` class
  - [x] 1.2: Implement asyncio-based scheduling using `asyncio.create_task` and sleep loops
  - [x] 1.3: Parse schedule config ("weekly", "daily", "manual") into cron-like timing
  - [x] 1.4: Calculate next run time (Sunday 3AM for weekly, 3AM daily for daily)
  - [x] 1.5: Add `start()`, `stop()`, `trigger_now()` methods

- [x] Task 2: Background Refresh Integration (AC: 2)
  - [x] 2.1: Ensure refresh runs as non-blocking background task
  - [x] 2.2: Use `RAGIngestPipeline` with `incremental=True` for efficiency
  - [x] 2.3: Process core sources: `mitre_attack`, `atomic_red`, `hacktricks`
  - [x] 2.4: Add mutex/lock to prevent concurrent refreshes

- [x] Task 3: Error Handling & Logging (AC: 4)
  - [x] 3.1: Wrap each source refresh in try/except
  - [x] 3.2: Log warnings on failure using structlog
  - [x] 3.3: Continue to next source on failure (no propagation)
  - [x] 3.4: Aggregate errors for final summary log

- [x] Task 4: Timestamp Persistence (AC: 5)
  - [x] 4.1: Create `RAGSchedulerState` dataclass for persistence
  - [x] 4.2: Store state in `~/.cyber-red/rag/.scheduler_state.json`
  - [x] 4.3: Load state on scheduler start to resume timing
  - [x] 4.4: Update state after each refresh cycle

- [x] Task 5: Daemon Integration (AC: 1, 2)
  - [x] 5.1: Initialize `RAGScheduler` in daemon server startup
  - [x] 5.2: Start scheduler when daemon starts (if not "manual" mode)
  - [x] 5.3: Stop scheduler on graceful shutdown
  - [x] 5.4: Add IPC command for manual trigger (`rag refresh`)

- [x] Task 6: Configuration Hot-Reload Support (AC: 3)
  - [x] 6.1: Add `rag.update_schedule` to `HOT_RELOAD_SAFE_PATHS` in config.py
  - [x] 6.2: Scheduler reschedules on config change callback

- [x] Task 7: Unit Tests (AC: 6)
  - [x] 7.1: Create `tests/unit/rag/test_scheduler.py`
  - [x] 7.2: Test schedule parsing (weekly, daily, manual)
  - [x] 7.3: Test next run time calculation
  - [x] 7.4: Test state persistence load/save
  - [x] 7.5: Test error handling (individual source failure)
  - [x] 7.6: Test concurrent refresh prevention

- [x] Task 8: Integration Tests (AC: 6)
  - [x] 8.1: Create `tests/integration/rag/test_scheduled_refresh.py`
  - [x] 8.2: Test end-to-end scheduled refresh with mock time
  - [x] 8.3: Test daemon integration (start/stop scheduler)
  - [x] 8.4: Test manual trigger via IPC

## Dev Notes

### Architecture Patterns and Constraints

- **Location**: `src/cyberred/rag/scheduler.py` (new file)
- **Schedule Config**: Already exists in `RAGConfig.update_schedule` (default: "weekly")
- **Asyncio Pattern**: Use background task with sleep loop, NOT external cron
- **Concurrency**: Single refresh at a time, use `asyncio.Lock`

### Source Tree Components to Touch

| File | Action | Description |
|------|--------|-------------|
| `src/cyberred/rag/scheduler.py` | CREATE | New RAGScheduler class |
| `src/cyberred/rag/__init__.py` | MODIFY | Export RAGScheduler |
| `src/cyberred/core/config.py` | MODIFY | Add schedule to HOT_RELOAD_SAFE_PATHS |
| `src/cyberred/daemon/server.py` | MODIFY | Initialize and manage scheduler lifecycle |
| `src/cyberred/daemon/ipc.py` | MODIFY | Add `rag refresh` IPC command |
| `tests/unit/rag/test_scheduler.py` | CREATE | Unit tests |
| `tests/integration/rag/test_scheduled_refresh.py` | CREATE | Integration tests |

### Implementation Patterns from Previous Stories

**From Story 6.11 (TUI RAG Manager Widget):**
- Reuse `KNOWN_SOURCES` list: `["mitre_attack", "atomic_red", "hacktricks", "payloads", "lolbas"]`
- Core sources for auto-refresh: `mitre_attack`, `atomic_red`, `hacktricks` (per story requirements)
- Dynamic import pattern: `importlib.import_module(f"cyberred.rag.sources.{source_name}")`
- Each source has `ingest(store, embeddings, incremental)` function

**From Story 2.13 (Configuration Hot-Reload):**
- `HOT_RELOAD_SAFE_PATHS` in `config.py` defines safe runtime changes
- Config watcher pattern via `_SettingsHolder._handle_config_change`

**From Daemon Patterns (Epic 2):**
- Graceful shutdown via `asyncio.Event` signaling
- Background tasks tracked in `_background_tasks` set
- IPC commands follow `{"command": "name", "args": {...}}` protocol

### Testing Standards Summary

- **100% coverage required** (project hard gate)
- Use `pytest-asyncio` for async tests
- Use `freezegun` or `time-machine` for time manipulation in tests
- Integration tests use real `RAGStore` with temp directory
- Mark with `@pytest.mark.rag` for selective test runs

### Project Structure Notes

- Alignment with unified project structure: `src/cyberred/rag/scheduler.py`
- State file location: `~/.cyber-red/rag/.scheduler_state.json` (alongside LanceDB)
- Config path: `rag.update_schedule` in `~/.cyber-red/config.yaml`

### Key Code Patterns

**Scheduler Loop Pattern:**
```python
async def _scheduler_loop(self) -> None:
    """Main scheduler loop."""
    while not self._shutdown_event.is_set():
        next_run = self._calculate_next_run()
        sleep_seconds = (next_run - datetime.now()).total_seconds()
        
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=max(0, sleep_seconds)
            )
            break  # Shutdown requested
        except asyncio.TimeoutError:
            pass  # Time to run
        
        await self._run_refresh()
```

**State Persistence Pattern:**
```python
@dataclass
class RAGSchedulerState:
    last_refresh: Optional[datetime]
    last_status: str  # "success", "partial", "failed"
    next_scheduled: Optional[datetime]
```

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#RAG Escalation Layer Integration] - Architecture patterns
- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 6.12] - Original story requirements
- [Source: src/cyberred/rag/ingest.py] - RAGIngestPipeline implementation
- [Source: src/cyberred/tui/widgets/rag_manager.py] - Manual refresh pattern (KNOWN_SOURCES, dynamic import)
- [Source: src/cyberred/core/config.py#RAGConfig] - RAG configuration model
- [Source: src/cyberred/core/config.py#HOT_RELOAD_SAFE_PATHS] - Hot-reload safe paths

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
