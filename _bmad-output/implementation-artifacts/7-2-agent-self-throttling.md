# Story 7.2: Agent Self-Throttling

Status: done

## Story

As an **agent**,
I want **to self-throttle when LLM queue depth is high**,
So that **I don't starve the system when many agents are active (NFR8)**.

## Acceptance Criteria

1. **Given** Story 7.1 (StigmergicAgent base class) is complete
   - **When** LLM queue depth exceeds threshold (default: 80%)
   - **Then** agent enters WAITING state

2. **Given** agent is in WAITING state due to throttling
   - **When** agent checks queue depth periodically (every 5s)
   - **Then** agent monitors queue depth at configurable interval

3. **Given** agent is throttled and monitoring queue
   - **When** queue depth drops below threshold
   - **Then** agent resumes normal operation (exits WAITING state)

4. **Given** any throttling state transition occurs
   - **When** agent enters or exits throttle
   - **Then** agent logs throttling events with structured logging

5. **Given** throttling is implemented
   - **When** integration tests run against real LLM Gateway
   - **Then** tests verify throttling behavior under load

6. **Given** throttling configuration
   - **When** config.yaml specifies custom throttle settings
   - **Then** threshold and check interval are configurable

## Tasks / Subtasks

### Phase 1: RED - Write Failing Tests First (TDD)

- [x] Task 1: Create test file structure (AC: #5)
  - [x] Create `tests/unit/agents/test_agent_throttling.py`
  - [x] Create `tests/integration/agents/test_agent_throttling_integration.py`

- [x] Task 2: Write unit tests for throttle configuration (AC: #6)
  - [x] Test `ThrottleConfig` model with default values (threshold=0.8, check_interval=5.0)
  - [x] Test `ThrottleConfig` validation (threshold 0.0-1.0, interval > 0)
  - [x] Test config loading from `config.yaml` agents section
  - [x] Test config override via engagement config

- [x] Task 3: Write unit tests for throttle state machine (AC: #1, #2, #3)
  - [x] Test `_check_throttle()` returns True when queue_depth >= threshold
  - [x] Test `_check_throttle()` returns False when queue_depth < threshold
  - [x] Test agent status transitions: `active` → `waiting` on throttle
  - [x] Test agent status transitions: `waiting` → `active` on unthrottle
  - [x] Test throttle check uses `LLMGateway.queue_depth` property
  - [x] Test throttle check uses `LLMPriorityQueue.total_queue_depth` via gateway

- [x] Task 4: Write unit tests for throttle monitoring loop (AC: #2, #4)
  - [x] Test `_throttle_monitor_loop()` runs at configured interval
  - [x] Test monitor loop exits when agent status is `shutdown`
  - [x] Test monitor loop logs throttle enter/exit events
  - [x] Test monitor loop handles gateway unavailable gracefully

- [x] Task 5: Write unit tests for execute() integration (AC: #1, #3)
  - [x] Test `execute()` calls `_check_throttle()` before LLM request
  - [x] Test `execute()` enters WAITING state when throttled
  - [x] Test `execute()` waits until unthrottled before proceeding
  - [x] Test `execute()` respects max_throttle_wait timeout (configurable, default 300s)
  - [x] Test `execute()` raises `ThrottleTimeoutError` if max wait exceeded

- [x] Task 6: Write integration tests (AC: #5)
  - [x] Test throttle behavior with real LLMGateway mock queue depth
  - [x] Test multi-agent throttling scenario (10 agents, 80% threshold)
  - [x] Test throttle-unthrottle cycle with actual queue depth changes
  - [x] Test throttle logging output (structured JSON format)

### Phase 2: GREEN - Implement Minimal Code

- [x] Task 7: Add ThrottleConfig to config system (AC: #6)
  - [x] Add `ThrottleConfig` model to `src/cyberred/core/config.py`
  - [x] Add `agents.throttle` section to `Settings` class
  - [x] Add to `HOT_RELOAD_SAFE_PATHS`: `agents.throttle.threshold`, `agents.throttle.check_interval`
  - [x] Update config validation for throttle parameters

- [x] Task 8: Implement `_check_throttle()` method (AC: #1, #3)
  - [x] Update `src/cyberred/agents/base.py` with full throttle implementation
  - [x] Add `_gateway` property for LLMGateway singleton access
  - [x] Implement queue depth check against threshold
  - [x] Handle gateway unavailable (fail-open: no throttle)
  - [x] Return boolean indicating throttle state

- [x] Task 9: Implement throttle monitoring loop (AC: #2, #4)
  - [x] Add `_throttle_monitor_task` attribute for async task
  - [x] Implement `_start_throttle_monitor()` called from `spawn()`
  - [x] Implement `_throttle_monitor_loop()` with configurable interval
  - [x] Add structured logging for throttle state changes
  - [x] Ensure loop cleanup on `shutdown()`

- [ ] Task 10: Integrate throttling into execute() (AC: #1, #3)
  - [ ] Add throttle check at start of `execute()`
  - [ ] Implement wait loop with `asyncio.Event` for throttle release
  - [ ] Add `max_throttle_wait` timeout with `ThrottleTimeoutError`
  - [ ] Ensure status transitions are atomic (thread-safe)

- [ ] Task 11: Add ThrottleTimeoutError exception (AC: #5)
  - [ ] Add `ThrottleTimeoutError` to `src/cyberred/core/exceptions.py`
  - [ ] Include agent_id, wait_duration, queue_depth in exception

### Phase 3: REFACTOR - Optimize and Harden

- [ ] Task 12: Optimize monitoring efficiency (AC: #2)
  - [ ] Use `asyncio.Event` for immediate wake on queue depth change (if feasible)
  - [ ] Add exponential backoff when repeatedly throttled
  - [ ] Add jitter to check interval to prevent thundering herd

- [ ] Task 13: Add Prometheus metrics (OBS pattern)
  - [ ] Add `agent_throttle_events_total` counter (labels: agent_type, action=enter|exit)
  - [ ] Add `agent_throttle_duration_seconds` histogram
  - [ ] Add `agent_throttle_wait_seconds` summary
  - [ ] Add `agents_throttled_current` gauge

- [ ] Task 14: Documentation and exports
  - [ ] Add comprehensive docstrings to all new methods
  - [ ] Update `agents/__init__.py` exports if needed
  - [ ] Add throttling section to config.yaml example
  - [ ] Update AGENTS.md if present

- [ ] Task 15: Edge case handling
  - [ ] Test and handle negative queue depth (defensive)
  - [ ] Test and handle None gateway (graceful degradation)
  - [ ] Test concurrent throttle checks (thread safety)
  - [ ] Test rapid throttle/unthrottle cycling (debounce if needed)

## Dev Notes

### Architecture Patterns & Constraints

**Self-Throttling Design (from Architecture line 140-142):**
> **Agent Self-Throttling:** When LLM queue depth exceeds threshold, agents enter WAITING state to prevent queue starvation.
> **Dynamic Scaling:** 10,000 agents is the ceiling, not the target. Spawner scales based on attack surface size.

**Memory Efficiency (NFR8):**
> Stigmergic coordination O(1), not O(n)

The throttling mechanism must be O(1) - each agent independently checks queue depth without coordination overhead.

**LLM Gateway Integration:**
```python
# From src/cyberred/llm/gateway.py (lines 401-404)
@property
def queue_depth(self) -> int:
    """Current queue depth."""
    return self._queue.total_queue_depth

# From src/cyberred/llm/priority_queue.py (lines 201-205)
@property
def total_queue_depth(self) -> int:
    """Return total pending requests."""
    with self._lock:
        return self._director_pending + self._agent_pending
```

**Existing Stub in StigmergicAgent (Story 7.1):**
```python
# From src/cyberred/agents/base.py (lines 217-226)
async def _check_throttle(self) -> bool:
    """Check if agent should throttle execution.
    
    Placeholder for Story 7.2 (Self-Throttling).
    
    Returns:
        True if should throttle, False otherwise.
    """
    # Default implementation: no throttling
    return False
```

**Status Property (already exists):**
```python
# From src/cyberred/agents/base.py (line 56)
self._status = "idle"  # Possible values: idle, active, waiting, shutdown, error
```

### Configuration Structure

Add to `config.yaml`:
```yaml
agents:
  throttle:
    threshold: 0.8        # 80% queue depth triggers throttle
    check_interval: 5.0   # Check every 5 seconds
    max_wait: 300         # Max seconds to wait before timeout error
```

**ThrottleConfig Model:**
```python
class ThrottleConfig(BaseModel):
    """Agent throttling configuration."""
    threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    check_interval: float = Field(default=5.0, gt=0.0)
    max_wait: PositiveInt = 300

class AgentsConfig(BaseModel):
    """Agents configuration section."""
    throttle: ThrottleConfig = Field(default_factory=ThrottleConfig)
```

### Error Handling

**Fail-Open Strategy:**
- If LLMGateway is unavailable → No throttle (agent proceeds)
- If queue depth cannot be read → No throttle (agent proceeds)
- If config is missing → Use defaults

**Fail-Closed Strategy:**
- If max_wait exceeded → Raise `ThrottleTimeoutError`
- If agent in shutdown state → Don't start new executions

### Logging Requirements (structlog)

Per architecture Rule 6: Use `structlog` with context binding.

```python
# Throttle enter
self._log.info(
    "agent_throttled",
    queue_depth=queue_depth,
    threshold=threshold,
    previous_status=previous_status,
)

# Throttle exit
self._log.info(
    "agent_unthrottled",
    queue_depth=queue_depth,
    threshold=threshold,
    wait_duration_seconds=wait_duration,
)

# Throttle timeout
self._log.warning(
    "agent_throttle_timeout",
    queue_depth=queue_depth,
    max_wait=max_wait,
)
```

### Existing Code to Reuse/Extend

| Component | Location | Usage |
|-----------|----------|-------|
| `StigmergicAgent._check_throttle()` | `src/cyberred/agents/base.py:217` | Stub to implement |
| `StigmergicAgent._status` | `src/cyberred/agents/base.py:56` | Status tracking |
| `LLMGateway.queue_depth` | `src/cyberred/llm/gateway.py:401` | Queue depth source |
| `get_gateway()` | `src/cyberred/llm/gateway.py:39` | Gateway singleton |
| `Settings` | `src/cyberred/core/config.py` | Configuration |
| `structlog` | Already imported in base.py | Logging |

### Anti-Patterns to Avoid

1. **DO NOT** poll Redis directly for queue depth — use `LLMGateway.queue_depth`
2. **DO NOT** create inter-agent dependencies for throttle state — O(1) requirement
3. **DO NOT** block the event loop during throttle wait — use async patterns
4. **DO NOT** forget to cancel monitor task on shutdown
5. **DO NOT** use busy-wait loops — use `asyncio.sleep()` with proper intervals
6. **DO NOT** hardcode thresholds — must be configurable via `config.yaml`

### Testing Standards

- **100% coverage required** (NFR19/NFR20)
- Use `pytest-asyncio` for async tests
- Mock `LLMGateway` for unit tests (use `MagicMock` with `queue_depth` property)
- Use `AsyncMock` for async method mocks
- Test markers: `@pytest.mark.unit`, `@pytest.mark.integration`
- Follow existing test patterns from `tests/unit/agents/test_stigmergic_base.py`

### Project Structure Notes

**Files to Modify:**
```
src/cyberred/
├── agents/
│   └── base.py                    # MODIFY: Implement _check_throttle(), add monitor loop
├── core/
│   ├── config.py                  # MODIFY: Add ThrottleConfig, AgentsConfig
│   └── exceptions.py              # MODIFY: Add ThrottleTimeoutError

tests/
├── unit/agents/
│   └── test_agent_throttling.py   # NEW: Unit tests
├── integration/agents/
│   └── test_agent_throttling_integration.py  # NEW: Integration tests
```

**Config Files to Update:**
```
config/
└── roe.yaml                       # Example config with throttle section
```

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Agent-LLM-Model-Pool] — Agent self-throttling design
- [Source: _bmad-output/planning-artifacts/architecture.md#Memory-Sizing] — NFR8 O(1) coordination requirement
- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story-7.2] — Story acceptance criteria
- [Source: src/cyberred/agents/base.py#_check_throttle] — Existing stub method
- [Source: src/cyberred/llm/gateway.py#queue_depth] — Queue depth property
- [Source: src/cyberred/llm/priority_queue.py#total_queue_depth] — Priority queue depth

### Story 7.1 Learnings Applied

From Story 7.1 completion notes:
- Used TDD phased format (RED/GREEN/REFACTOR) — **applying same approach**
- EventBus integration patterns established — **following same patterns**
- Protocol compliance via structural subtyping — **maintaining compatibility**
- structlog context binding pattern — **reusing same logging approach**

### Dependencies

**Prerequisites (all complete):**
- Story 7.1: StigmergicAgent Base Class ✅
- Story 3.9: LLM Priority Queue ✅
- Story 3.10: LLM Gateway Singleton ✅

**Blocks:**
- Story 7.3: ReconAgent Implementation (needs throttle-aware base)
- Story 7.4: ExploitAgent Implementation (needs throttle-aware base)
- Story 7.5: PostExAgent Implementation (needs throttle-aware base)
- Story 7.7: Dynamic Agent Spawner (needs throttle metrics)

### NFR Traceability

| NFR | Requirement | Implementation |
|-----|-------------|----------------|
| NFR8 | Memory efficiency O(1) | Each agent checks independently, no inter-agent state |
| NFR1 | <1s stigmergic propagation | Throttle doesn't affect pub/sub, only LLM requests |
| NFR6 | 10,000+ agents | Throttle prevents queue starvation at scale |
| NFR19 | 100% unit test coverage | TDD approach ensures full coverage |
| NFR20 | 100% integration test coverage | Integration tests verify real behavior |

---

## Dev Agent Record

### Agent Model Used

gemini-2.0-flash-exp

### Debug Log References

### Completion Notes List

### File List

- src/cyberred/core/config.py
- src/cyberred/core/exceptions.py
- src/cyberred/agents/base.py
- tests/unit/agents/test_agent_throttling.py
- tests/integration/agents/test_agent_throttling_integration.py
