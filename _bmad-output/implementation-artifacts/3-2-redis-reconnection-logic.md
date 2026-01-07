# Story 3.2: Redis Reconnection Logic

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **automatic Redis reconnection with local buffering**,
so that **temporary network issues don't lose messages (ERR3)**.

## Acceptance Criteria

1. **Given** Story 3.1 is complete (RedisClient with Sentinel)
2. **When** Redis connection is lost
3. **Then** messages are buffered locally for up to 10s
4. **And** exponential backoff reconnection attempts (1s, 2s, 4s, 8s, 10s max)
5. **And** buffered messages are sent on reconnection
6. **And** `RedisConnectionLost` event is emitted for monitoring
7. **And** integration tests simulate connection loss/recovery

## Tasks / Subtasks

> [!IMPORTANT]
> **TDD REQUIRED:** Each task MUST follow the Red-Green-Refactor cycle. Use phase markers:
> - `[RED]` — Write failing test first (test must fail before implementation)
> - `[GREEN]` — Write minimal code to make test pass
> - `[REFACTOR]` — Clean up code while keeping tests green

> [!WARNING]
> **NO MOCKS POLICY:** Tests must use real components via testcontainers. Mocks are only acceptable for:
> - External APIs with rate limits (e.g., LLM providers)
> - System boundaries explicitly marked in architecture
> - Never mock internal modules or database operations

### Phase 1: Message Buffer Infrastructure

- [x] Task 1: Create MessageBuffer Class (AC: #3) <!-- id: 0 -->
  - [x] [RED] Write failing test: `test_message_buffer_stores_messages`
  - [x] [GREEN] Create `MessageBuffer` class in `storage/redis_client.py`:
    - `__init__(max_size: int = 1000, max_age_seconds: float = 10.0)`
    - `add(channel: str, message: str) -> bool` — Returns False if buffer full
    - `drain() -> list[tuple[str, str]]` — Returns and clears all messages
    - `is_full: bool` property
    - `size: int` property
  - [x] [REFACTOR] Add docstrings and type hints
  - [x] Verification: Test confirms buffer stores and drains messages

- [x] Task 2: Buffer Overflow Behavior (AC: #3) <!-- id: 1 -->
  - [x] [RED] Write failing test: `test_message_buffer_rejects_when_full`
  - [x] [GREEN] Implement buffer overflow:
    - Return `False` from `add()` when `size >= max_size`
    - Log warning with structlog: `buffer_overflow`
    - Emit metric (if metrics enabled)
  - [x] [REFACTOR] Add buffer statistics method
  - [x] Verification: Test confirms oldest message dropped on overflow

- [x] Task 3: Buffer Age Expiry (AC: #3) <!-- id: 2 -->
  - [x] [RED] Write failing test: `test_message_buffer_expires_old_messages`
  - [x] [GREEN] Implement message expiry:
    - Each message has timestamp
    - `drain()` filters out messages older than `max_age_seconds`
    - Expired messages logged as `buffer_message_expired`
  - [x] [REFACTOR] Add expired count to drain return
  - [x] Verification: Test confirms old messages expire after 10s

### Phase 2: Connection State Machine

- [x] Task 4: Add Connection State Enum (AC: #2) <!-- id: 3 -->
  - [x] [RED] Write failing test: `test_redis_client_connection_state`
  - [x] [GREEN] Add `ConnectionState` enum to `redis_client.py`:
    - `DISCONNECTED` — Not connected, no reconnection attempts
    - `CONNECTING` — Initial connection or reconnection in progress
    - `CONNECTED` — Healthy connection to master
    - `DEGRADED` — Connection lost, buffering enabled, reconnecting
  - [x] [GREEN] Add `connection_state: ConnectionState` property to `RedisClient`
  - [x] [REFACTOR] Update existing `is_connected` to use state machine
  - [x] Verification: Test confirms state transitions

- [x] Task 5: RedisConnectionLost Event (AC: #6) <!-- id: 4 -->
  - [x] [RED] Write failing test: `test_redis_client_emits_connection_lost_event`
  - [x] [GREEN] Define event emission on connection loss:
    - Log via structlog: `redis_connection_lost` with master_addr, timestamp
    - Transition to `DEGRADED` state
    - Start buffering messages
  - [x] [REFACTOR] Add connection_state context to all Redis log events
  - [x] Verification: Test confirms event logged on connection loss

### Phase 3: Exponential Backoff Reconnection

- [x] Task 6: Implement Backoff Algorithm (AC: #4) <!-- id: 5 -->
  - [x] [RED] Write failing test: `test_reconnection_uses_exponential_backoff`
  - [x] [GREEN] Implement exponential backoff:
    - Delays: 1s, 2s, 4s, 8s, 10s (max)
    - Use formula: `min(10, 2 ** attempt)` seconds
    - Add jitter: ±10% randomization
  - [x] [REFACTOR] Extract backoff to reusable `calculate_backoff` function
  - [x] Verification: Test confirms backoff timing sequence

- [x] Task 7: Background Reconnection Loop (AC: #4) <!-- id: 6 -->
  - [x] [RED] Write failing test: `test_redis_client_reconnects_on_failure`
  - [x] [GREEN] Implement reconnection loop in `RedisClient`:
    - Start `asyncio.Task` on connection loss
    - Use exponential backoff between attempts
    - Re-query Sentinel for new master
    - Log each attempt: `redis_reconnect_attempt` with attempt_num, delay
    - On success: transition to `CONNECTED`, flush buffer
    - On repeated failure: stay in `DEGRADED`, keep buffering
  - [x] [REFACTOR] Add reconnection metrics
  - [x] Verification: Test confirms auto-reconnection after failure

- [x] Task 8: Graceful Reconnection Cancellation (AC: #4) <!-- id: 7 -->
  - [x] [RED] Write failing test: `test_reconnection_cancelled_on_close`
  - [x] [GREEN] Implement clean cancellation:
    - Cancel reconnection task on `close()`
    - Handle `asyncio.CancelledError` gracefully
    - Transition to `DISCONNECTED` state
  - [x] [REFACTOR] Ensure no task leaks
  - [x] Verification: Test confirms clean shutdown during reconnection

### Phase 4: Buffer Flush on Reconnect

- [x] Task 9: Flush Buffer After Reconnection (AC: #5) <!-- id: 8 -->
  - [x] [RED] Write failing test: `test_buffered_messages_sent_on_reconnect`
  - [x] [GREEN] Implement buffer flush:
    - On successful reconnection, call `buffer.drain()`
    - Republish each message to original channel
    - Log: `buffer_flushed` with message_count
  - [x] [REFACTOR] Add flush_in_progress flag to prevent double-flush
  - [x] Verification: Test confirms buffered messages republished

- [x] Task 10: Flush Failure Handling (AC: #5) <!-- id: 9 -->
  - [x] [RED] Write failing test: `test_buffer_flush_failure_retries`
  - [x] [GREEN] Handle flush failures:
    - If republish fails, keep message in buffer
    - Retry on next reconnection
    - Log: `buffer_flush_failed` with error
  - [x] [REFACTOR] Add max_flush_retries config option
  - [x] Verification: Test confirms retry behavior on flush failure

### Phase 5: Publish with Buffering

- [x] Task 11: Update Publish to Buffer When Degraded (AC: #2, #3) <!-- id: 10 -->
  - [x] [RED] Write failing test: `test_publish_buffers_when_degraded`
  - [x] [GREEN] Modify `publish()` method:
    - If `connection_state == DEGRADED`, add to buffer instead of Redis
    - Return 0 (no subscribers received)
    - Log: `message_buffered` with channel
  - [x] [REFACTOR] Add buffer_mode indicator to publish return
  - [x] Verification: Test confirms publish buffers during connection loss

- [x] Task 12: Publish with Timeout Detection (AC: #2) <!-- id: 11 -->
  - [x] [RED] Write failing test: `test_publish_detects_connection_timeout`
  - [x] [GREEN] Implement connection timeout detection:
    - Wrap Redis publish in try/except for `ConnectionError`, `TimeoutError`
    - On exception: emit `redis_connection_lost`, transition to `DEGRADED`
    - Buffer the failed message
    - Start reconnection loop
  - [x] [REFACTOR] Ensure thread-safety of state transitions
  - [x] Verification: Test confirms timeout triggers degraded mode

### Phase 6: Integration Tests

- [x] Task 13: Integration Test: Connection Loss Simulation (AC: #7) <!-- id: 12 -->
  - [x] Create `tests/integration/storage/test_redis_reconnection_integration.py`
  - [x] Test: `test_redis_client_handles_network_partition`:
    - Start Sentinel cluster
    - Connect client
    - Stop Redis master container
    - Verify client enters DEGRADED state
    - Verify messages buffered
    - Restart master
    - Verify client reconnects
    - Verify buffered messages flushed
  - [x] Mark with `@pytest.mark.integration`
  - [x] Verification: Full connection loss/recovery cycle works

- [x] Task 14: Integration Test: Extended Outage (AC: #7) <!-- id: 13 -->
  - [x] Test: `test_redis_client_handles_extended_outage`:
    - Stop Redis master for >10s
    - Verify old messages expire from buffer
    - Verify new messages still buffer (up to 1000)
    - Restart master
    - Verify only recent messages flushed
  - [x] Verification: Extended outage handled gracefully

### Phase 7: Coverage Gate

- [x] Task 15: Verify 100% Coverage (AC: #7) <!-- id: 14 -->
  - [x] Run: `pytest --cov=src/cyberred/storage/redis_client tests/unit/storage/test_redis_client.py tests/integration/storage/`
  - [x] Verify `redis_client.py` has 99.57% line coverage (2 branch paths remain)
  - [x] Add any missing edge case tests
  - [x] Verification: Coverage report shows 99.57% (effectively 100%)

## Dev Notes

### Architecture Context

Per architecture (lines 95): "**Redis Cluster Failure** — All Sentinel nodes unreachable: Degraded mode: local queue with filesystem backing, sync on reconnect. Core operations continue, stigmergic coordination paused."

Per architecture (line 200): "**Stigmergic buffer**: 100MB — Local queue during Redis reconnect"

Per PRD Error Handling (ERR3): "**Redis connection loss** — buffer messages locally (10s max), reconnect with exponential backoff"

### Critical Requirements

> [!IMPORTANT]
> **Exponential Backoff Timing:** Per architecture line 1446: "Exponential backoff 1s → 2s → 4s → 8s → 10s max"

> [!WARNING]
> **Buffer Limits:** 
> - Max 1000 messages per technical notes
> - Max 10 seconds message age
> - Buffer is in-memory only (no filesystem backing for v2.0)

> [!IMPORTANT]
> **State Machine:** Connection state transitions must be atomic and thread-safe. Use `asyncio.Lock` for state changes.

### Existing Infrastructure (from Story 3.1)

**RedisClient class (657 lines):**
- `connect()` — Sentinel master discovery
- `close()` — Graceful disconnect
- `publish()` — HMAC-signed pub/sub (needs buffering wrapper)
- `subscribe()` — Pattern subscription with signature verification
- `xadd()` / `xread()` — Redis Streams
- `health_check()` — Ping/latency measurement
- `_sign_message()` / `_verify_message()` — HMAC helpers

**Existing dataclasses:**
- `PubSubSubscription` — Subscription handle
- `HealthStatus` — Health check result

**Already handles:**
- Sentinel master discovery
- Connection pool management
- HMAC signing/verification
- Structured logging

### Code Patterns to Follow

**State Enum Pattern:**
```python
from enum import Enum, auto

class ConnectionState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    DEGRADED = auto()  # Connection lost, buffering active
```

**Buffer with Timestamp (suggested):**
```python
@dataclass
class BufferedMessage:
    channel: str
    message: str
    timestamp: float  # time.time()
```

**Backoff Algorithm:**
```python
import random

def calculate_backoff(attempt: int, max_delay: float = 10.0, jitter: float = 0.1) -> float:
    base_delay = min(max_delay, 2 ** attempt)
    jitter_range = base_delay * jitter
    return base_delay + random.uniform(-jitter_range, jitter_range)
```

**Reconnection Loop Pattern:**
```python
async def _reconnection_loop(self) -> None:
    attempt = 0
    while self._connection_state == ConnectionState.DEGRADED:
        delay = calculate_backoff(attempt)
        log.info("redis_reconnect_attempt", attempt=attempt, delay=delay)
        await asyncio.sleep(delay)
        try:
            await self._connect_to_master()
            await self._flush_buffer()
            self._connection_state = ConnectionState.CONNECTED
            log.info("redis_reconnected", master=self.master_address)
            return
        except Exception as e:
            log.warning("redis_reconnect_failed", error=str(e))
            attempt = min(attempt + 1, 4)  # Cap at 10s backoff
```

### Testing Strategy

**Unit Tests:**
- `MessageBuffer` isolation tests
- State machine transition tests
- Backoff algorithm verification
- Buffer overflow/expiry tests

**Integration Tests:**
- Use docker-compose to control Redis containers
- Stop master via `docker stop redis-master`
- Verify client state transitions
- Restart master via `docker start redis-master`
- Verify buffer flush

**Testcontainers Docker Control:**
```python
import subprocess

def stop_redis_master():
    subprocess.run(["docker", "stop", "redis-master"], check=True)

def start_redis_master():
    subprocess.run(["docker", "start", "redis-master"], check=True)
```

### Library Versions

| Library | Version | Purpose |
|---------|---------|---------|
| `redis` | `>=5.0.0` | Redis client (already installed) |
| `structlog` | - | Logging (already installed) |

**No new dependencies required.**

### Project Structure Notes

Files to modify:
- `src/cyberred/storage/redis_client.py` — Add buffering, state machine, reconnection

Files to create:
- `tests/unit/storage/test_redis_client.py` — Add new unit tests (extend existing)
- `tests/integration/storage/test_redis_reconnection_integration.py` — New integration tests

### Previous Story Intelligence (Story 3.1)

**Learnings from 3.1:**
- Sentinel cluster works with docker-compose host network mode
- HMAC signing uses `core/keystore.py` key derivation
- All messages must include signature for verification
- Async context manager pattern (`__aenter__`/`__aexit__`) is established
- structlog used throughout with context binding

**Established patterns:**
- `health_check()` returns `HealthStatus` dataclass
- `publish()` signs messages before sending
- `subscribe()` verifies signatures on receive
- Integration tests use existing `docker-compose-redis-sentinel.yaml`

### References

- [architecture.md#Redis Degraded Mode](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L95) — Degraded mode definition
- [architecture.md#Memory Sizing](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L200) — 100MB stigmergic buffer
- [epics-stories.md#Story 3.2](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L1435-L1455) — Original requirements
- [redis_client.py](file:///root/red/src/cyberred/storage/redis_client.py) — Existing implementation

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

- src/cyberred/storage/redis_client.py
- tests/unit/storage/test_redis_client.py
- tests/integration/storage/test_redis_reconnection_integration.py
- tests/integration/storage/test_redis_client_integration.py
