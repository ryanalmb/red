# Story 1.9: Kill Switch Core (Tri-Path)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **a kill switch that halts all operations in <1s under 10K agent load**,
So that **I maintain absolute control over the engagement (FR17, FR18, NFR2)**.

## Acceptance Criteria

1. **Given** an engagement is running with agents active
2. **When** `killswitch.trigger()` is called
3. **Then** Path 1: Redis pub/sub `control:kill` is published
4. **And** Path 2: SIGTERM cascade via process group is sent
5. **And** Path 3: Docker API `container.stop()` is called (500ms timeout then kill)
6. **And** atomic "engagement frozen" flag is set before any path executes
7. **And** all three paths execute in parallel
8. **And** kill switch completes in <1s (hard requirement)
9. **And** safety tests verify <1s under simulated load

## Tasks / Subtasks

> [!IMPORTANT]
> **SAFETY-CRITICAL IMPLEMENTATION — RED-GREEN TDD METHODOLOGY REQUIRED**
> This is a **safety-critical** component. Each task MUST follow strict TDD: Write failing tests FIRST (RED), then implement code to pass (GREEN), then refactor. The kill switch MUST work even if Redis is offline.

### Phase 1: RED — Write Failing Tests First

- [x] Task 0: Verify Prerequisites (PREREQUISITE) <!-- id: prereq -->
  - [x] Verify `asyncio` module available (stdlib)
  - [x] Verify `signal` module available (stdlib)
  - [x] Verify `docker` package available — **NOTE: Must add `"docker>=7.0.0"` to pyproject.toml dependencies**
  - [x] Verify `redis` package available (already in pyproject.toml: `redis>=5.0.0`)
  - [x] Verify `redis.asyncio` module available for async operations
  - [x] Verify `KillSwitchTriggered` exists in `cyberred.core.exceptions` with signature `(engagement_id, triggered_by, reason)`
  - [x] Verify Redis pub/sub wrapper available from core/events.py (Story 1.1 exceptions + future Epic 3)
  - [x] Test: `python -c "import asyncio, signal, os; print('OK')"`
  - [x] Note: Docker and Redis clients will be mocked for unit tests; safety tests may use real containers

- [x] Task 1: Create Test File Structure (AC: #9) <!-- id: 0 -->
  - [x] Create `tests/unit/core/test_killswitch.py`
  - [x] Create `tests/safety/test_killswitch.py` (marked with `@pytest.mark.safety`)
  - [x] Import pytest and required testing utilities
  - [x] Import `KillSwitch` from `cyberred.core.killswitch`
  - [x] Import `KillSwitchTriggered` from `cyberred.core.exceptions`

- [x] Task 2: Write Failing Core Kill Switch Tests (AC: #1-#7) <!-- id: 1 -->
  - [x] Test `KillSwitch.__init__(redis_client, docker_client, process_group)` initializes paths
  - [x] Test `KillSwitch.trigger()` sets atomic frozen flag FIRST before any path
  - [x] Test `KillSwitch.trigger()` returns within 1s (asyncio timeout test)
  - [x] Test `KillSwitch.is_frozen` property returns current frozen state
  - [x] Test `KillSwitch.reset()` clears frozen flag (for testing only, production use restricted)
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 3: Write Failing Redis Path Tests (AC: #3) <!-- id: 2 -->
  - [x] Test `_path_redis()` publishes to `control:kill` channel
  - [x] Test `_path_redis()` message includes: `{command: "kill", issued_by, timestamp, reason}`
  - [x] Test `_path_redis()` continues even if Redis unavailable (fail-silent, logs warning)
  - [x] Test `_path_redis()` has 500ms timeout (does not block other paths)
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 4: Write Failing SIGTERM Path Tests (AC: #4) <!-- id: 3 -->
  - [x] Test `_path_sigterm()` sends SIGTERM to process group
  - [x] Test `_path_sigterm()` uses `os.killpg(os.getpgid(pid), signal.SIGTERM)`
  - [x] Test `_path_sigterm()` handles `ProcessLookupError` gracefully (process already dead)
  - [x] Test `_path_sigterm()` handles `PermissionError` gracefully (logs warning)
  - [x] Test `_path_sigterm()` has 300ms timeout before fallback
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 5: Write Failing Docker Path Tests (AC: #5) <!-- id: 4 -->
  - [x] Test `_path_docker()` calls `container.stop(timeout=0.5)` on all engagement containers
  - [x] Test `_path_docker()` calls `container.kill()` if stop() times out
  - [x] Test `_path_docker()` filters containers by engagement label
  - [x] Test `_path_docker()` continues even if Docker unavailable (fail-silent, logs warning)
  - [x] Test `_path_docker()` handles `docker.errors.NotFound` (container already stopped)
  - [x] Test `_path_docker()` has 600ms timeout (500ms stop + 100ms buffer)
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 6: Write Failing Parallel Execution Tests (AC: #6, #7) <!-- id: 5 -->
  - [x] Test all three paths execute via `asyncio.gather()` with `return_exceptions=True`
  - [x] Test total execution completes even if one path hangs (individual timeouts)
  - [x] Test path failures do not block other paths
  - [x] Test execution order: frozen flag → parallel paths → completion
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 7: Write Failing <1s Timing Tests (AC: #8) <!-- id: 6 -->
  - [x] Test `trigger()` completes in <1s with mocked paths (0ms execution)
  - [x] Test `trigger()` completes in <1s with simulated slow Redis (400ms)
  - [x] Test `trigger()` completes in <1s with simulated slow Docker (500ms)
  - [x] Test `trigger()` completes in <1s with all paths at max timeout
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 8: Write Failing Audit Trail Tests <!-- id: 7 -->
  - [x] Test `trigger()` logs kill switch activation to audit trail
  - [x] Test audit log includes: timestamp, issued_by, reason, paths_executed, duration_ms
  - [x] Test audit log format is JSON-structured (for `structlog` compatibility)
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 9: Write Failing Exception Tests <!-- id: 8 -->
  - [x] Test `KillSwitchTriggered` exception raised contains engagement_id
  - [x] Test `KillSwitchTriggered` exception contains trigger reason
  - [x] Test `KillSwitchTriggered` auto-logs to audit trail on raise
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 10: Write Failing Agent Integration Tests <!-- id: 9 -->
  - [x] Test agents check frozen flag before spawning new actions
  - [x] Test agents exit gracefully when frozen flag is set
  - [x] Test agent action loop respects frozen state (no work while frozen)
  - [x] **Run tests — ALL FAILED (RED confirmed)**

### Phase 2: GREEN — Implement to Pass Tests

- [x] Task 11: Create KillSwitch Module Core (AC: #1, #6) <!-- id: 10 -->
  - [x] Create `src/cyberred/core/killswitch.py`
  - [x] Import `asyncio`, `signal`, `os`, `time`, `logging`
  - [x] Import `KillSwitchTriggered` from `cyberred.core.exceptions`
  - [x] Import `structlog` for JSON-structured logging
  - [x] Implement `KillSwitch.__init__(redis_client=None, docker_client=None, engagement_id=None)`
    - [x] Store redis_client (optional — kill switch works without Redis)
    - [x] Store docker_client (optional — kill switch works without Docker)
    - [x] Initialize `_frozen` as `threading.Event()` for atomic flag (thread-safe)
    - [x] Initialize `_trigger_time` for timing measurement
  - [x] Implement `is_frozen` property returning `_frozen.is_set()`
  - [x] **Run Task 2 tests — ALL PASSED (GREEN)**

- [x] Task 12: Implement Redis Path (AC: #3) <!-- id: 11 -->
  - [x] Implement `async _path_redis(self, reason: str) -> bool`:
    - [x] If no redis_client, log warning and return False
    - [x] Build message: `{"command": "kill", "issued_by": operator, "timestamp": ISO8601, "reason": reason}`
    - [x] Publish to `control:kill` channel with 500ms timeout
    - [x] Return True on success, False on failure (never raise)
    - [x] Wrap in try-except, log any errors
  - [x] **Run Task 3 tests — ALL PASSED (GREEN)**

- [x] Task 13: Implement SIGTERM Path (AC: #4) <!-- id: 12 -->
  - [x] Implement `async _path_sigterm(self) -> bool`:
    - [x] Get process group ID via `os.getpgid(os.getpid())`
    - [x] Send SIGTERM via `os.killpg(pgid, signal.SIGTERM)` with 300ms timeout
    - [x] Handle `ProcessLookupError` (process already dead) — return True
    - [x] Handle `PermissionError` — log warning, return False
    - [x] Return True on success, False on failure (never raise)
  - [x] **Run Task 4 tests — ALL PASSED (GREEN)**

- [x] Task 14: Implement Docker Path (AC: #5) <!-- id: 13 -->
  - [x] Implement `async _path_docker(self) -> bool`:
    - [x] If no docker_client, log warning and return False
    - [x] List containers filtered by label `cyberred.engagement_id={engagement_id}`
    - [x] For each container:
      - [x] Call `container.stop(timeout=0.5)`
      - [x] If timeout, call `container.kill()`
    - [x] Handle `docker.errors.NotFound` (container already stopped)
    - [x] Wrap in 600ms total timeout
    - [x] Return True on success, False on partial failure (never raise)
  - [x] **Run Task 5 tests — ALL PASSED (GREEN)**

- [x] Task 15: Implement Trigger with Parallel Execution (AC: #6, #7, #8) <!-- id: 14 -->
  - [x] Implement `async trigger(self, reason: str = "Operator initiated", triggered_by: str = "operator") -> dict`:
    - [x] FIRST: Set atomic frozen flag: `self._frozen.set()`
    - [x] Record start time: `start = time.perf_counter()`
    - [x] SECOND: Execute all paths in parallel:
      ```python
      results = await asyncio.gather(
          asyncio.wait_for(self._path_redis(reason), timeout=0.5),
          asyncio.wait_for(self._path_sigterm(), timeout=0.3),
          asyncio.wait_for(self._path_docker(), timeout=0.6),
          return_exceptions=True
      )
      ```
    - [x] Calculate duration: `duration_ms = (time.perf_counter() - start) * 1000`
    - [x] Log to audit trail: `{"event": "kill_switch_triggered", "duration_ms": duration_ms, ...}`
    - [x] Return result dict: `{"success": True, "duration_ms": duration_ms, "paths": {...}}`
  - [x] **Run Tasks 6, 7 tests — ALL PASSED (GREEN)**

- [x] Task 16: Implement Audit Trail Integration <!-- id: 15 -->
  - [x] Import `structlog` for JSON-structured logging
  - [x] Implement `_log_trigger(self, reason: str, duration_ms: float, path_results: dict) -> None`
    - [x] Log to `structlog` with fields: `event="kill_switch_triggered"`, `engagement_id`, `reason`, `duration_ms`, `paths`
  - [x] Call `_log_trigger()` at end of `trigger()`
  - [x] **Run Task 8 tests — ALL PASSED (GREEN)**

- [x] Task 17: Implement KillSwitchTriggered Exception Enhancement <!-- id: 16 -->
  - [x] Verify `KillSwitchTriggered` in `core/exceptions.py` includes `engagement_id` and `reason`
  - [x] If not present, add fields to exception class
  - [x] Hook into `__init__` to auto-log on raise if audit logging available
  - [x] **Run Task 9 tests — ALL PASSED (GREEN)**

- [x] Task 18: Implement Agent Frozen Check Helper <!-- id: 17 -->
  - [x] Implement `check_frozen(self, triggered_by: str = "system") -> None`:
    - [x] If `self._frozen.is_set()`, raise `KillSwitchTriggered(self.engagement_id, triggered_by, "Engagement frozen")`
  - [x] Document: Agents should call `killswitch.check_frozen()` before each action
  - [x] **Run Task 10 tests — ALL PASSED (GREEN)**

### Phase 3: REFACTOR & Export

- [x] Task 19: Export from Core Package (AC: all) <!-- id: 18 -->
  - [x] Export `KillSwitch` from `core/__init__.py`
  - [x] Add to `__all__` list
  - [x] Verify no circular imports
  - [x] Verify `KillSwitchTriggered` already exported from exceptions

- [x] Task 20: Validate 100% Test Coverage <!-- id: 19 -->
  - [x] Run `pytest tests/unit/core/test_killswitch.py --cov=src/cyberred/core/killswitch --cov-report=term-missing`
  - [x] Ensure 100% line coverage on `killswitch.py`
  - [x] Ensure 100% branch coverage on `killswitch.py`
  - [x] Run `pytest tests/safety/test_killswitch.py -m safety`
  - [x] Ensure all safety tests pass

- [x] Task 21: Documentation & Examples <!-- id: 20 -->
  - [x] Add comprehensive docstrings to `KillSwitch` class
  - [x] Document tri-path design rationale
  - [x] Document fail-silent behavior for individual paths
  - [x] Document <1s timing requirement
  - [x] Create usage example in docstrings

## Dev Notes

### Architecture Context

This story implements `core/killswitch.py` per architecture (line 782):
```
core/killswitch.py — Tri-path kill switch (safety-critical)
```

**Why Kill Switch is Safety-Critical:**

> [!CAUTION]
> This is a **SAFETY-CRITICAL** component in Cyber-Red v2.0. A kill switch failure could result in:
> - Continued unauthorized operations after operator requests stop
> - Agents running out of control during emergencies
> - Legal liability for operator
> - Loss of control over engagement

**Architecture Requirements (Hard Gates):**

- **FR17**: Operator can trigger kill switch to halt all operations (<1s under load)
- **FR18**: Kill switch can execute hybrid control (instant halt + graceful shutdown)
- **NFR2**: Kill switch response <1s halt all operations under 10K agent load (Hard)
- **Architecture line 91**: Tri-path: (1) Redis pub/sub `control:kill`, (2) SIGTERM cascade via process group, (3) Docker API `container.stop()` with 500ms timeout then `kill()`. Atomic "engagement frozen" flag checked before any agent spawn
- **Architecture line 71**: Kill Switch — Must work even if Redis is offline (dual-path)
- **Architecture line 689**: Redis channel `control:kill` for kill switch

### Tri-Path Kill Switch Design

**Threat Model:** A single kill path can fail:
- **Redis offline** → Path 1 fails (network partition, crash)
- **Process dead** → Path 2 fails (agent already exited)
- **Docker daemon** → Path 3 fails (Docker API unreachable)

**Defense:** Per architecture (line 91):
> "Tri-path: (1) Redis pub/sub `control:kill`, (2) SIGTERM cascade via process group, (3) Docker API `container.stop()` with 500ms timeout then `kill()`. Atomic 'engagement frozen' flag checked before any agent spawn"

**Design Principle:** Kill switch MUST work even if Redis is completely offline. That's why Path 2 (SIGTERM) and Path 3 (Docker) are redundant local paths.

### Path Details

**Path 1: Redis Pub/Sub**
- Publishes to `control:kill` channel
- All agents subscribe to this channel → immediate termination signal
- Timeout: 500ms (non-blocking on Redis failures)
- Fail-silent: logs warning if Redis unavailable

**Path 2: SIGTERM Cascade**
- Sends SIGTERM to entire process group
- Uses `os.killpg(pgid, signal.SIGTERM)`
- Handles graceful shutdown for Python processes
- Timeout: 300ms
- Fail-silent: handles ProcessLookupError, PermissionError

**Path 3: Docker API**
- Calls `container.stop(timeout=0.5)` on all engagement containers
- Filters by label `cyberred.engagement_id={engagement_id}`
- Falls back to `container.kill()` if stop times out
- Timeout: 600ms (500ms stop + 100ms buffer)
- Fail-silent: handles NotFound, APIError

### Atomic Frozen Flag

**Critical Requirement:** The frozen flag MUST be set BEFORE any path executes:

```python
async def trigger(self, reason: str = "Operator initiated") -> dict:
    # FIRST: Set atomic frozen flag
    self._frozen.set()  # <- This happens BEFORE paths
    
    # SECOND: Execute paths in parallel
    results = await asyncio.gather(...)
```

**Why:** Agents check the frozen flag before spawning new work. Setting it first guarantees no new work starts, even if paths are slow.

### Timing Budget

| Component | Budget | Rationale |
|-----------|--------|-----------|
| Frozen flag set | ~1ms | Atomic operation |
| Redis path | 500ms max | Network timeout |
| SIGTERM path | 300ms max | Process signal |
| Docker path | 600ms max | API + container stop |
| **Total parallel** | 600ms max | All paths run simultaneously |
| **Reserve** | 400ms | Buffer for logging, overhead |
| **Total** | <1000ms | NFR2 hard requirement |

### Control Message Format

Per architecture (lines 694-701):
```json
{
    "command": "kill",
    "issued_by": "root",
    "timestamp": "2025-12-27T23:30:00Z",
    "reason": "Operator initiated emergency stop"
}
```

### Exception Definition

Per architecture (lines 668-669) and actual implementation in `core/exceptions.py`:
```python
class KillSwitchTriggered(CyberRedError):
    """Engagement halted by operator."""
    def __init__(self, engagement_id: str, triggered_by: str, reason: str):
        self.engagement_id = engagement_id
        self.triggered_by = triggered_by  # Who triggered (operator, system, etc.)
        self.reason = reason
        super().__init__(f"Kill switch triggered for {engagement_id} by {triggered_by}: {reason}")
```

### Agent Integration Pattern

Agents should check the frozen flag before each action cycle:

```python
class StigmergicAgent:
    def __init__(self, killswitch: KillSwitch):
        self.killswitch = killswitch
    
    async def run(self):
        while True:
            # Check frozen flag BEFORE any work
            self.killswitch.check_frozen()  # Raises KillSwitchTriggered if frozen
            
            # ... agent work ...
```

### Library Requirements

**Standard Library (No External Dependencies for Core):**
```python
import asyncio       # Async execution, gather, timeouts
import signal        # SIGTERM handling
import os           # Process group management
import time         # Timing measurement
import threading    # Event for atomic flag
import logging      # Audit trail logging
```

**Already in pyproject.toml:**
```toml
"structlog>=24.0.0",  # JSON-structured logging
"redis>=5.0.0",       # Redis client (optional) — use redis.asyncio for async
```

**Must add to pyproject.toml:**
```toml
"docker>=7.0.0",      # Docker client (optional) — NOT YET ADDED
```

**Async Redis Pattern:**
```python
from redis.asyncio import Redis
async_redis = Redis.from_url("redis://localhost")
await async_redis.publish("control:kill", message)
```

**Import Pattern:**
```python
import asyncio
import signal
import os
import time
import threading
from typing import Optional, Dict, Any
import structlog

from cyberred.core.exceptions import KillSwitchTriggered
```

### Previous Story Patterns

**From Story 1.8 (Scope Validator):**
- Module exports via `core/__init__.py` with `__all__` list
- Exception hierarchy extends `CyberRedError`
- Unit tests in `tests/unit/core/test_killswitch.py`
- Safety tests in `tests/safety/test_killswitch.py` with `@pytest.mark.safety`
- 100% coverage requirement enforced via pytest-cov
- Docstrings with Args, Returns, Raises sections
- TDD methodology: RED → GREEN → REFACTOR

**From Story 1.1 (Exception Hierarchy):**
- `KillSwitchTriggered` extends `CyberRedError`
- Auto-logging to audit trail on exception raise

### Anti-Patterns to Avoid

1. **NEVER** rely on Redis alone (must work offline)
2. **NEVER** execute paths sequentially (must be parallel)
3. **NEVER** let one path block others (individual timeouts)
4. **NEVER** skip the frozen flag (must be set FIRST)
5. **NEVER** raise exceptions from paths (fail-silent, log warnings)
6. **NEVER** exceed 1s total execution time
7. **NEVER** allow new agent work while frozen
8. **NEVER** silently swallow all errors (log warnings for debugging)
9. **NEVER** make trigger() synchronous (must be async for parallel execution)
10. **NEVER** use blocking calls in paths (use asyncio timeouts)

### Complete Usage Example

```python
from cyberred.core.killswitch import KillSwitch
from cyberred.core.exceptions import KillSwitchTriggered

# Initialize with dependencies (all optional for resilience)
killswitch = KillSwitch(
    redis_client=redis_client,  # Optional
    docker_client=docker_client,  # Optional
    engagement_id="ministry-2025"
)

# Trigger kill switch (emergency stop)
result = await killswitch.trigger(reason="Operator initiated emergency stop")
print(f"Kill switch completed in {result['duration_ms']:.1f}ms")
# Output: Kill switch completed in 234.5ms

# Check if frozen
if killswitch.is_frozen:
    print("Engagement is frozen")

# Agent checks frozen state (raises if frozen)
try:
    killswitch.check_frozen()
    # ... agent work ...
except KillSwitchTriggered as e:
    print(f"Cannot proceed: {e}")
```

### Integration with TUI (Epic 10)

The TUI will bind the kill switch to:
- ESC key (keyboard shortcut)
- Sticky kill button (always visible)
- F-key navigation (dedicated kill switch screen)

```python
# In TUI app.py
async def on_key(self, event):
    if event.key == "escape":
        await self.killswitch.trigger(reason="Operator pressed ESC")
```

### Testing Strategy

**Unit Tests** (`tests/unit/core/test_killswitch.py`):
- Core initialization and properties
- Frozen flag atomic behavior
- Individual path execution (mocked clients)
- Parallel execution timing
- Error handling for each path
- Audit trail logging

**Safety Tests** (`tests/safety/test_killswitch.py`):
- <1s timing validation under various conditions
- Resilience when Redis unavailable
- Resilience when Docker unavailable
- All paths execute even if some fail
- Agent frozen check integration

### Downstream Consumers

- `agents/base.py` (Epic 7) will check frozen flag before each action
- `tui/screens/war_room.py` (Epic 10) will expose kill switch button
- `daemon/session_manager.py` (Epic 2) will trigger on graceful shutdown
- `c2/server.py` (Epic 12) will use for emergency drop box abort

**Ensure public API is stable for downstream consumption:**
- `KillSwitch.trigger(reason: str, triggered_by: str = "operator") -> dict`
- `KillSwitch.is_frozen -> bool`
- `KillSwitch.check_frozen(triggered_by: str = "system") -> None`
- `KillSwitchTriggered(engagement_id, triggered_by, reason)` exception

### References

- [Architecture: core/killswitch.py](file:///root/red/docs/3-solutioning/architecture.md#L782)
- [Architecture: Tri-path Kill Switch](file:///root/red/docs/3-solutioning/architecture.md#L91)
- [Architecture: Kill Switch Offline](file:///root/red/docs/3-solutioning/architecture.md#L71)
- [Architecture: control:kill Channel](file:///root/red/docs/3-solutioning/architecture.md#L689)
- [Architecture: KillSwitchTriggered Exception](file:///root/red/docs/3-solutioning/architecture.md#L668)
- [Epics: Story 1.9](file:///root/red/docs/3-solutioning/epics-stories.md#L1031)
- [Epics: Story 1.10 - Kill Switch Resilience Testing](file:///root/red/docs/3-solutioning/epics-stories.md#L1056)
- [PRD: FR17, FR18, NFR2](file:///root/red/docs/2-plan/prd.md)
- [Python asyncio docs](https://docs.python.org/3/library/asyncio.html)
- [Python signal docs](https://docs.python.org/3/library/signal.html)

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

N/A

### Completion Notes List

- ✅ Added `docker>=7.0.0` dependency to pyproject.toml
- ✅ Created `src/cyberred/core/killswitch.py` with tri-path implementation (331 lines)
- ✅ Exported `KillSwitch` from `core/__init__.py`
- ✅ Created `tests/unit/core/test_killswitch.py` with 30 comprehensive unit tests
- ✅ Replaced placeholder `tests/safety/test_killswitch.py` with 10 real safety tests
- ✅ All 40 tests pass with 100% line coverage on `killswitch.py`
- ✅ Tri-path implementation: Redis pub/sub, SIGTERM cascade, Docker API
- ✅ Atomic frozen flag set BEFORE any path executes
- ✅ Individual path timeouts: Redis 500ms, SIGTERM 300ms, Docker 600ms
- ✅ Fail-silent paths (log warnings, don't raise)
- ✅ `check_frozen()` helper for agent integration
- ✅ Safety tests verify <1s timing under simulated load

### File List

- `pyproject.toml` - Added docker>=7.0.0 dependency
- `src/cyberred/core/killswitch.py` - NEW: Tri-path kill switch implementation
- `src/cyberred/core/__init__.py` - Added KillSwitch export
- `tests/unit/core/test_killswitch.py` - NEW: 30 unit tests
- `tests/safety/test_killswitch.py` - MODIFIED: Replaced placeholders with 10 real tests

### Change Log

- 2026-01-01: Story implemented with 100% test coverage, all acceptance criteria met
- 2026-01-01: Code review fixes: blocking I/O (executor), NTP compliance (trusted time), error handling
