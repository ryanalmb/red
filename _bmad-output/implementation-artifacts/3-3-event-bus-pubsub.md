Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **a Redis pub/sub wrapper for real-time stigmergic signals**,
so that **agents can coordinate via fire-and-forget messages (NFR1)**.

## Acceptance Criteria

1. **Given** Stories 3.1 and 3.2 are complete (RedisClient with Sentinel and reconnection)
2. **When** I call `events.publish(channel, message)`
3. **Then** message is published to Redis pub/sub
4. **And** message includes HMAC-SHA256 signature for integrity (handled by RedisClient)
5. **And** subscribers receive messages in <1s (NFR1)
6. **When** I call `events.subscribe(pattern)`
7. **Then** callback is invoked for matching messages
8. **And** signature is validated on receipt (handled by RedisClient)
9. **And** integration tests verify pub/sub latency <1s

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

### Phase 1: EventBus Core Structure

- [x] Task 1: Create EventBus Class (AC: #2, #3) <!-- id: 0 -->
  - [x] [RED] Write failing test: `test_event_bus_creates_with_redis_client`
  - [x] [GREEN] Create `src/cyberred/core/events.py` with `EventBus` class:
    - `__init__(redis_client: RedisClient)` — wraps existing RedisClient
    - `async publish(channel: str, message: str) -> int` — delegates to `redis_client.publish`
    - `async subscribe(pattern: str, callback: Callable) -> PubSubSubscription` — delegates to `redis_client.subscribe`
  - [x] [REFACTOR] Add docstrings and type hints
  - [x] Verification: Test confirms EventBus wraps RedisClient correcty

- [x] Task 2: Channel Naming Validation (AC: #2, #3) <!-- id: 1 -->
  - [x] [RED] Write failing test: `test_event_bus_validates_channel_names`
  - [x] [GREEN] Implement channel name validation:
    - Enforce colon notation pattern (per architecture line 686-700)
    - Allowed patterns: `findings:{hash}:{type}`, `agents:{id}:status`, `control:*`, `authorization:*`
    - Raise `ChannelNameError` for invalid patterns
  - [x] [REFACTOR] Add constant patterns for common channel prefixes
  - [x] Verification: Test confirms invalid channels rejected

### Phase 2: Serialization & Protocol

- [x] Task 3: JSON Serialization (AC: #2) <!-- id: 2 -->
  - [x] [RED] Write failing test: `test_event_bus_ensures_json_strings`
  - [x] [GREEN] Ensure payloads are strings:
    - If `publish` input is dict/list, auto-serialize to JSON string
    - If `publish` input is non-string (and not dict/list), raise ValueError
    - Note: Crypto signing is handled by `RedisClient.publish`, so only pass the raw payload string
  - [x] [REFACTOR] Add `_ensure_string` helper
  - [x] Verification: Test confirms structured data is serialized before passing to RedisClient

- [x] Task 4: Callback Error Safety (AC: #7) <!-- id: 3 -->
  - [x] [RED] Write failing test: `test_event_bus_wraps_callback_errors`
  - [x] [GREEN] Wrap user callbacks:
    - Ensure logical errors in user callback don't crash the listener
    - Log `event_callback_error` with stack trace
    - Note: Signature validation is handled by `RedisClient.subscribe`, so callbacks receive only verified content
  - [x] [REFACTOR] Add callback execution timing logs
  - [x] Verification: Test confirms listener survives callback exceptions

### Phase 3: Latency Optimization

- [x] Task 5: Async Metrics (AC: #5) <!-- id: 4 -->
  - [x] [RED] Write failing test: `test_event_bus_logs_performance`
  - [x] [GREEN] Add performance logging:
    - Measure time taken for `publish` call
    - Log: structlog `event_published` with `latency_ms`
    - Emit warning if latency >500ms
  - [x] [REFACTOR] Add latency histogram metrics (if metrics enabled)
  - [x] Verification: Test confirms performance logs emitted

### Phase 4: Stigmergic Channel Helpers

- [x] Task 6: Finding Publication Helper (AC: #2, #3) <!-- id: 5 -->
  - [x] [RED] Write failing test: `test_event_bus_publish_finding`
  - [x] [GREEN] Implement `publish_finding(finding: Finding) -> int`:
    - Auto-generate channel: `findings:{target_hash}:{finding.type}`
    - Serialize Finding to JSON (using Task 3 logic)
    - Publish
    - Log: `finding_published` with finding_id, target, type
  - [x] [REFACTOR] Hash target using SHA-256 prefix (first 8 chars)
  - [x] Verification: Test confirms finding published to correct channel

- [x] Task 7: Agent Status Publication Helper (AC: #2, #3) <!-- id: 6 -->
  - [x] [RED] Write failing test: `test_event_bus_publish_agent_status`
  - [x] [GREEN] Implement `publish_agent_status(agent_id: str, status: dict) -> int`:
    - Channel: `agents:{agent_id}:status`
    - Publish status JSON
    - Log: `agent_status_published` with agent_id, status
  - [x] [REFACTOR] Add status field validation (expected fields: state, task, timestamp)
  - [x] Verification: Test confirms status published to agent channel

- [x] Task 8: Kill Switch Subscription (AC: #7, #8) <!-- id: 7 -->
  - [x] [RED] Write failing test: `test_event_bus_kill_switch_subscription`
  - [x] [GREEN] Implement `subscribe_kill_switch(callback: Callable) -> PubSubSubscription`:
    - Subscribe to `control:kill` channel
    - Invoke callback with kill switch reason
    - Log: `kill_switch_received` immediately
  - [x] [REFACTOR] Ensure callback is awaited immediately
  - [x] Verification: Test confirms kill switch subscription works

### Phase 5: Connection State Integration

- [x] Task 9: Degraded Mode Visibility (AC: #2, #3) <!-- id: 8 -->
  - [x] [RED] Write failing test: `test_event_bus_exposes_degraded_state`
  - [x] [GREEN] Passthrough state properties:
    - `is_degraded` property (from RedisClient)
    - Log: `event_bus_degraded_mode` when publishing in degraded state
  - [x] [REFACTOR] Add flush notification hook
  - [x] Verification: Test confirms degraded state visibility

- [x] Task 10: Health Check (AC: #5) <!-- id: 9 -->
  - [x] [RED] Write failing test: `test_event_bus_health_check`
  - [x] [GREEN] Implement `health_check() -> HealthStatus`:
    - Delegate to RedisClient.health_check()
    - Add `pubsub_active` field
    - Log: `event_bus_health_check` with result
  - [x] [REFACTOR] Add last_publish_latency_ms to health status
  - [x] Verification: Test confirms health check returns valid status

### Phase 6: Integration Tests

- [x] Task 11: Integration Test: Round-Trip Latency (AC: #9) <!-- id: 10 -->
  - [x] Create `tests/integration/core/test_events_integration.py`
  - [x] Test: `test_event_bus_pubsub_round_trip_latency`:
    - Start Sentinel cluster
    - Create EventBus with RedisClient
    - Publish message, measure time to callback
    - Assert latency <1000ms (NFR1)
  - [x] Mark with `@pytest.mark.integration`
  - [x] Verification: Round-trip latency verified <1s

- [x] Task 12: Integration Test: Concurrent Subscribers (AC: #7, #9) <!-- id: 11 -->
  - [x] Test: `test_event_bus_concurrent_subscriptions`:
    - Subscribe 5 patterns simultaneously
    - Publish to each, verify all callbacks invoked
    - Verify no message loss
  - [x] Verification: Concurrent subscriptions work correctly

- [x] Task 13: Integration Test: HMAC End-to-End (AC: #8) <!-- id: 12 -->
  - [x] Test: `test_event_bus_hmac_enforcement`:
    - Publish via EventBus (Should sign)
    - Subscribe via EventBus (Should verify)
    - Confirm communication works
    - Publish RAW invalid string via redis-cli (or bypass)
    - Confirm EventBus subscriber drops it
  - [x] Verification: Security guarantee verified end-to-end

### Phase 7: Coverage Gate

- [x] Task 14: Verify 100% Coverage (AC: #9) <!-- id: 13 -->
  - [x] Run: `pytest --cov=src/cyberred/core/events tests/unit/core/test_events.py tests/integration/core/`
  - [x] Verify `events.py` has 100% line coverage
  - [x] Add any missing edge case tests
  - [x] Verification: Coverage report shows 100%

## Dev Notes

### Architecture Context

Per architecture (lines 226-233): "Event Bus (Real-time): Redis Pub/Sub — Fire-and-forget stigmergic signals, low latency."

Per NFR1: "Agent coordination latency <1s stigmergic propagation (Hard)"

### Critical Requirements

> [!IMPORTANT]
> **LATENCY REQUIREMENT (NFR1):** End-to-end pub/sub latency MUST be <1s.
> Test with: `test_event_bus_pubsub_round_trip_latency`

> [!NOTE]
> **NO REDUNDANT CRYPTO:** `RedisClient` handles all HMAC signing and validation. `EventBus` MUST NOT re-implement this. Focus on payload structure and channel routing.

### Existing Infrastructure

**RedisClient class (`storage/redis_client.py`):**
- `publish(channel, message)`: Signs message, returns subscribers or 0 (degraded).
- `subscribe(pattern, callback)`: Validates signatures, invokes callback with verified content.

### Code Patterns to Follow

**Structure:**
```python
class EventBus:
    def __init__(self, redis: RedisClient):
        self._redis = redis
        
    async def publish(self, channel: str, message: Union[str, dict]) -> int:
        payload = self._ensure_string(message)
        return await self._redis.publish(channel, payload)
```

**Channel Constants:**
```python
CHANNEL_FINDINGS_TEMPLATE = "findings:{}:{}"
```

### Library Versions

- `redis`: >=5.0.0
- `structlog`: Standard

### Project Structure Notes

Files to create:
- `src/cyberred/core/events.py`
- `tests/unit/core/test_events.py`
- `tests/integration/core/test_events_integration.py`

## Dev Agent Record

### Agent Model Used

Antigravity (Google DeepMind)

### Completion Notes List

- Created `events.py` with full EventBus implementation (359 lines)
- Channel validation with 5 regex patterns per architecture
- Typed helpers: `publish_finding`, `publish_agent_status`, `subscribe_kill_switch`
- 25 unit tests passing with 100% coverage
- 7 integration tests passing with real Redis via testcontainers
- NFR1 latency requirement verified <1s in integration test
- HMAC enforcement verified - tampered messages are dropped
- Exported `EventBus` and `ChannelNameError` from `core/__init__.py`
- [Code Review] Added strict schema validation for agent status (AC #2)
- [Code Review] Updated ChannelNameError message
- [Code Review] Optimized test suite (removed sleeps)

### File List

- `src/cyberred/core/events.py` - EventBus implementation
- `src/cyberred/core/__init__.py` - Updated with exports
- `tests/unit/core/test_events.py` - Unit tests (25 tests)
- `tests/integration/core/test_events_integration.py` - Integration tests (7 tests)
