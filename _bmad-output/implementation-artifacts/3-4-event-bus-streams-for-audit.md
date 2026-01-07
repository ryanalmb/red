# Story 3.4: Event Bus (Streams for Audit)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **Redis Streams for persistent audit events**,
so that **audit trail has at-least-once delivery guarantee**.

## Acceptance Criteria

1. **Given** Story 3.3 is complete (EventBus pub/sub wrapper)
2. **When** I call `events.audit(event)`
3. **Then** event is added to `audit:stream` Redis Stream
4. **And** consumer group `audit-consumers` processes events
5. **And** events are acknowledged after processing
6. **And** unacknowledged events are redelivered
7. **And** all messages include HMAC-SHA256 signature for integrity validation
8. **And** invalid signatures are rejected and logged as security events
9. **And** integration tests verify no message loss on consumer restart
10. **And** integration tests verify HMAC validation rejects tampered messages

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

### Phase 1: Redis Streams Core Methods

- [ ] Task 1: Add xadd to RedisClient (AC: #3) <!-- id: 0 -->
  - [ ] [RED] Write failing test: `test_redis_client_xadd_adds_to_stream`
  - [ ] [GREEN] Implement `RedisClient.xadd(stream: str, fields: dict, maxlen: Optional[int] = None) -> str`:
    - Serialize fields to JSON if needed
    - Sign payload with HMAC-SHA256 (like publish)
    - Call `redis.xadd(stream, {"payload": signed_data})`
    - Return message ID (timestamp-sequence string)
  - [ ] [REFACTOR] Add structlog logging `stream_message_added`
  - [ ] Verification: Test confirms message added with ID returned

- [ ] Task 2: Add xread to RedisClient (AC: #3) <!-- id: 1 -->
  - [ ] [RED] Write failing test: `test_redis_client_xread_reads_messages`
  - [ ] [GREEN] Implement `RedisClient.xread(stream: str, last_id: str, count: int, block_ms: int) -> list`:
    - Call `redis.xread({stream: last_id}, count=count, block=block_ms)`
    - Verify HMAC-SHA256 signature on each message
    - Reject tampered messages (log security event, skip)
    - Return list of (id, data) tuples
  - [ ] [REFACTOR] Add `stream_messages_read` logging with count
  - [ ] Verification: Test confirms messages read correctly

- [ ] Task 3: Add xgroup_create to RedisClient (AC: #4) <!-- id: 2 -->
  - [ ] [RED] Write failing test: `test_redis_client_xgroup_create`
  - [ ] [GREEN] Implement `RedisClient.xgroup_create(stream: str, group: str, start_id: str = "$", mkstream: bool = True) -> bool`:
    - Call `redis.xgroup_create(stream, group, start_id, mkstream=mkstream)`
    - Handle BUSYGROUP error (group exists) gracefully → return False
    - Return True if created successfully
  - [ ] [REFACTOR] Add `consumer_group_created` logging
  - [ ] Verification: Test confirms group creation and idempotency

- [ ] Task 4: Add xreadgroup to RedisClient (AC: #4, #6) <!-- id: 3 -->
  - [ ] [RED] Write failing test: `test_redis_client_xreadgroup_reads_for_consumer`
  - [ ] [GREEN] Implement `RedisClient.xreadgroup(group: str, consumer_name: str, stream: str, count: int, block_ms: int) -> list`:
    - Call `redis.xreadgroup(group, consumer, {stream: ">"}, count=count, block=block_ms)`
    - Verify HMAC-SHA256 signature on each message (reject tampered)
    - Return list of (id, data) tuples
  - [ ] [REFACTOR] Add `consumer_messages_read` logging
  - [ ] Verification: Test confirms consumer receives unacked messages

- [ ] Task 5: Add xack to RedisClient (AC: #5) <!-- id: 4 -->
  - [ ] [RED] Write failing test: `test_redis_client_xack_acknowledges_message`
  - [ ] [GREEN] Implement `RedisClient.xack(stream: str, group: str, *message_ids: str) -> int`:
    - Call `redis.xack(stream, group, *message_ids)`
    - Return count of acknowledged messages
  - [ ] [REFACTOR] Add `messages_acknowledged` logging with count
  - [ ] Verification: Test confirms acknowledgment removes from pending

- [ ] Task 6: Add xpending and xclaim to RedisClient (AC: #6) <!-- id: 5 -->
  - [ ] [RED] Write failing tests: `test_redis_client_xpending`, `test_redis_client_xclaim`
  - [ ] [GREEN] Implement `RedisClient.xpending(stream: str, group: str) -> dict`:
    - Call `redis.xpending(stream, group)`
    - Return pending info (count, min_id, max_id, consumers)
  - [ ] [GREEN] Implement `RedisClient.xclaim(stream: str, group: str, consumer_name: str, min_idle_time: int, message_ids: list) -> list`:
    - Call `redis.xclaim(stream, group, consumer_name, min_idle_time, message_ids)`
  - [ ] [REFACTOR] Add typed return dataclass `PendingInfo`
  - [ ] Verification: Test confirms pending info returned and messages claimed

### Phase 2: EventBus Audit Methods

- [ ] Task 7: Add audit() method to EventBus (AC: #2, #3, #7) <!-- id: 6 -->
  - [ ] [RED] Write failing test: `test_event_bus_audit_adds_to_stream`
  - [ ] [GREEN] Implement `EventBus.audit(event: Union[str, dict]) -> str`:
    - Serialize event to JSON if dict
    - Add timestamp if not present
    - Call `self._redis.xadd("audit:stream", event)`
    - Log `audit_event_written` with event type
    - Return message ID
  - [ ] [REFACTOR] Add event type extraction for logging
  - [ ] Verification: Test confirms audit event written to stream

- [ ] Task 8: Add create_audit_consumer_group() (AC: #4) <!-- id: 7 -->
  - [ ] [RED] Write failing test: `test_event_bus_create_audit_consumer_group`
  - [ ] [GREEN] Implement `EventBus.create_audit_consumer_group() -> bool`:
    - Call `self._redis.xgroup_create("audit:stream", "audit-consumers", mkstream=True)`
    - Handle exists gracefully
    - Log `audit_consumer_group_initialized`
  - [ ] [REFACTOR] Add option for custom group name
  - [ ] Verification: Test confirms consumer group creation

- [ ] Task 9: Add consume_audit() iterator (AC: #4, #5, #6) <!-- id: 8 -->
  - [ ] [RED] Write failing test: `test_event_bus_consume_audit_yields_messages`
  - [ ] [GREEN] Implement `EventBus.consume_audit(consumer_id: str, count: int = 10, block_ms: int = 5000) -> AsyncGenerator`:
    - Yield (message_id, event_data) tuples
    - Use `xreadgroup` for consumer-group semantics
    - Caller must call `ack_audit()` after processing
    - Log `audit_events_consumed`
  - [ ] [REFACTOR] Add consumer heartbeat logging
  - [ ] Verification: Test confirms messages yielded correctly

- [ ] Task 10: Add ack_audit() method (AC: #5) <!-- id: 9 -->
  - [ ] [RED] Write failing test: `test_event_bus_ack_audit_acknowledges`
  - [ ] [GREEN] Implement `EventBus.ack_audit(*message_ids: str) -> int`:
    - Call `self._redis.xack("audit:stream", "audit-consumers", *message_ids)`
    - Log `audit_events_acknowledged`
    - Return count
  - [ ] [REFACTOR] Support batch acknowledgment efficiently
  - [ ] Verification: Test confirms messages acknowledged

- [ ] Task 11: Add pending_audit() method (AC: #6) <!-- id: 10 -->
  - [ ] [RED] Write failing test: `test_event_bus_pending_audit_returns_info`
  - [ ] [GREEN] Implement `EventBus.pending_audit() -> PendingInfo`:
    - Call `self._redis.xpending("audit:stream", "audit-consumers")`
    - Return structured pending info
  - [ ] [REFACTOR] Add pending count to health_check
  - [ ] Verification: Test confirms pending info returned

### Phase 3: HMAC Security Enforcement

- [ ] Task 12: Signature Validation on Read (AC: #7, #8) <!-- id: 11 -->
  - [ ] [RED] Write failing test: `test_event_bus_audit_rejects_tampered_messages`
  - [ ] [GREEN] Ensure xread/xreadgroup verify HMAC:
    - Invalid signature → log `security_audit_tampered_message`
    - Include message_id in log for forensics
    - Skip message (do not yield to consumer)
    - Do NOT ack tampered messages (leave in pending)
  - [ ] [REFACTOR] Add tampered message counter metric
  - [ ] Verification: Test confirms tampered messages rejected

- [ ] Task 13: Signature Inclusion on Write (AC: #7) <!-- id: 12 -->
  - [ ] [RED] Write failing test: `test_event_bus_audit_signs_messages`
  - [ ] [GREEN] Verify xadd includes HMAC:
    - Reuse existing RedisClient signing logic
    - Signature stored in payload alongside data
  - [ ] [REFACTOR] Ensure consistent signing format with pub/sub
  - [ ] Verification: Test confirms signed messages written

### Phase 4: Redelivery & Reliability

- [ ] Task 14: Unacknowledged Redelivery (AC: #6) <!-- id: 13 -->
  - [ ] [RED] Write failing test: `test_event_bus_audit_redelivers_unacked`
  - [ ] [GREEN] Implement `EventBus.claim_pending_audit(consumer_id: str, min_idle_ms: int = 60000) -> list`:
    - Use `XAUTOCLAIM` or `XCLAIM` to claim stale pending messages
    - Return claimed (message_id, data) list
    - Log `audit_pending_claimed`
  - [ ] [REFACTOR] Add idle time threshold configuration
  - [ ] Verification: Test confirms stale messages claimed

- [ ] Task 15: Stream Trimming Configuration (AC: #3) <!-- id: 14 -->
  - [ ] [RED] Write failing test: `test_event_bus_audit_respects_max_len`
  - [ ] [GREEN] Add `maxlen` parameter to audit():
    - Default: no trimming (audit is permanent)
    - Optional: `maxlen=~1000000` for approximate trimming
    - Use XTRIM semantics from xadd
  - [ ] [REFACTOR] Add config setting for max_audit_stream_len
  - [ ] Verification: Test confirms trimming works when configured

### Phase 5: Integration Tests

- [ ] Task 16: Integration Test: At-Least-Once Delivery (AC: #9) <!-- id: 15 -->
  - [ ] Create `tests/integration/core/test_audit_stream_integration.py`
  - [ ] Test: `test_audit_stream_no_message_loss`:
    - Write 100 audit events
    - Consume 50, simulate consumer crash (no ack)
    - Restart consumer, verify remaining 50 + original 50 unacked received
    - Ack all, verify pending count = 0
  - [ ] Mark with `@pytest.mark.integration`
  - [ ] Verification: At-least-once delivery verified

- [ ] Task 17: Integration Test: Consumer Group Semantics (AC: #4, #5) <!-- id: 16 -->
  - [ ] Test: `test_audit_stream_consumer_group_semantics`:
    - Create consumer group
    - Two consumers in same group
    - Publish 10 messages
    - Verify messages distributed across consumers (not duplicated)
    - Ack all, verify all processed exactly once
  - [ ] Verification: Consumer group load balancing works

- [ ] Task 18: Integration Test: HMAC Rejection (AC: #8, #10) <!-- id: 17 -->
  - [ ] Test: `test_audit_stream_hmac_rejects_tampered`:
    - Write audit event via EventBus (signed)
    - Write raw unsigned event via redis-cli (bypass signing)
    - Consume via EventBus
    - Verify signed event received, unsigned event rejected
    - Verify security log emitted for tampered message
  - [ ] Verification: Security guarantee enforced

- [ ] Task 19: Integration Test: Degraded Mode Buffering (AC: #3) <!-- id: 18 -->
  - [ ] Test: `test_audit_stream_degraded_mode`:
    - Audit event when Redis available → written
    - Simulate Redis disconnect
    - Audit event → buffered (if applicable) or raises
    - Reconnect, verify behavior consistent with pub/sub
  - [ ] Verification: Degraded mode consistent with EventBus design

### Phase 6: Coverage & Export

- [ ] Task 20: Verify 100% Coverage (AC: all) <!-- id: 19 -->
  - [ ] Run: `pytest --cov=src/cyberred/storage/redis_client --cov=src/cyberred/core/events tests/unit/storage/test_redis_client.py tests/unit/core/test_events.py tests/integration/core/`
  - [ ] Verify 100% line coverage for new stream methods
  - [ ] Add any missing edge case tests
  - [ ] Verification: Coverage report shows 100%

- [ ] Task 21: Export Types from Core (AC: all) <!-- id: 20 -->
  - [ ] Update `src/cyberred/core/__init__.py`:
    - Export `PendingInfo` dataclass if created
  - [ ] Update `src/cyberred/storage/__init__.py`:
    - Ensure stream methods exported
  - [ ] Verification: Public API complete

## Dev Notes

### Architecture Context

Per architecture (lines 226-233):
- "Event Bus (Audit): Redis Streams — Persistent, replay capability, exactly-once via consumer groups"
- "Audit Trail: Agent → Redis Streams → Audit Consumer (persistent)"

Per architecture (line 1078-1079):
```python
# Ensure audit never loses events (at-least-once delivery)
redis.xgroup_create("audit:stream", "audit-consumers", mkstream=True)
```

### Critical Requirements

> [!IMPORTANT]
> **AT-LEAST-ONCE DELIVERY:** Unacknowledged messages MUST be redelivered.
> Consumer crashes should NOT lose audit events.

> [!WARNING]
> **HMAC SECURITY:** All stream messages must be signed on write and verified on read.
> Tampered messages must be rejected and logged as security events.

### Existing Infrastructure

**EventBus class (`core/events.py`):**
- Already has channel pattern `audit:stream` validated
- HMAC signing/verification delegated to RedisClient

**RedisClient class (`storage/redis_client.py`):**
- Has `publish/subscribe` with HMAC
- Needs new stream methods: `xadd`, `xread`, `xgroup_create`, `xreadgroup`, `xack`, `xpending`

### Code Patterns to Follow

**Stream Methods (RedisClient):**
```python
async def xadd(
    self,
    stream: str,
    fields: dict,
    maxlen: Optional[int] = None,
) -> str:
    """Add message to stream with HMAC signature."""
    signed = self._sign_message(json.dumps(fields))
    return await self._redis.xadd(stream, {"payload": signed}, maxlen=maxlen)
```

**Audit Method (EventBus):**
```python
async def audit(self, event: Union[str, dict]) -> str:
    """Write audit event to stream with at-least-once guarantee."""
    payload = self._ensure_string(event)
    return await self._redis.xadd("audit:stream", {"event": payload})
```

### Consumer Group Pattern
```python
# Initialize on startup
await event_bus.create_audit_consumer_group()

# Consume in loop
async for msg_id, data in event_bus.consume_audit("worker-1"):
    process(data)
    await event_bus.ack_audit(msg_id)
```

### Library Versions

- `redis`: >=5.0.0 (Streams fully supported)
- Redis server: >=6.2 (for XAUTOCLAIM)

### Project Structure Notes

Files to modify:
- `src/cyberred/storage/redis_client.py` — Add stream methods
- `src/cyberred/core/events.py` — Add audit() and consumer methods
- `src/cyberred/core/__init__.py` — Export new types

Files to create:
- `tests/unit/storage/test_redis_client_streams.py` OR extend existing
- `tests/unit/core/test_events_audit.py` OR extend existing
- `tests/integration/core/test_audit_stream_integration.py`

### References

- [Source: docs/3-solutioning/architecture.md#line-227] Event Bus Audit pattern
- [Source: docs/3-solutioning/architecture.md#line-1078-1079] Consumer group initialization
- [Source: _bmad-output/planning-artifacts/epics-stories.md#line-1483-1507] Story 3.4 requirements
- [Source: _bmad-output/implementation-artifacts/3-3-event-bus-pubsub.md] Previous story patterns

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- Implemented Redis Streams wrapper in `RedisClient` with HMAC support.
- Implemented Audit Event Bus in `EventBus` with consumer group support.
- Achieved 100% test coverage including edge cases (connection errors, byte decoding).
- Verified via integration tests (at-least-once delivery, security rejection).

### File List

- src/cyberred/storage/redis_client.py
- src/cyberred/core/events.py
- src/cyberred/core/__init__.py
- tests/integration/core/test_audit_stream_integration.py
- tests/unit/storage/test_redis_client_coverage.py


