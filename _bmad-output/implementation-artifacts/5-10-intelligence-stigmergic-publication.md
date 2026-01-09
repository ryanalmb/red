# Story 5.10: Intelligence Stigmergic Publication

Status: review

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD methodology at all times. All tasks marked [RED], [GREEN], [REFACTOR] must be followed explicitly. Each task must have a failing test before implementation.

> [!NOTE]
> **DEPENDENCIES:**
> - Story 5.7 (Intelligence Aggregator) - Provides `CachedIntelligenceAggregator`
> - Epic 3 (Event Bus) - Provides Redis pub/sub via [events.py](file:///root/red/src/cyberred/core/events.py)
> - [aggregator.py](file:///root/red/src/cyberred/intelligence/aggregator.py) — `CachedIntelligenceAggregator`
> - [base.py](file:///root/red/src/cyberred/intelligence/base.py) — `IntelResult` data model

> [!CAUTION]
> **SWARM-WIDE SHARING:** This story implements stigmergic intelligence sharing. When an agent receives intelligence results, it MUST publish them to allow other agents to skip redundant queries. Check order MUST be: **stigmergic → cache → sources**.

## Story

As an **agent**,
I want **to publish intelligence results to the stigmergic layer**,
So that **other agents skip redundant queries (FR75)**.

## Acceptance Criteria

1. **Given** Stories 5.7 and Epic 3 (event bus) are complete
   **When** I receive intelligence results for a target
   **Then** results are published to `findings:{target_hash}:intel_enriched`

2. **Given** intelligence results are published to stigmergic layer
   **When** other agents subscribed to this topic receive the intelligence
   **Then** they can use it without querying the aggregator

3. **Given** an agent needs intelligence for a target
   **When** checking for intelligence
   **Then** agents check stigmergic layer before querying aggregator
   **And** query order is: stigmergic → cache → sources

4. **Given** stigmergic intelligence is published
   **Then** it has shorter TTL (5 min) than cache (1 hour)
   **And** TTL prevents stale data from persisting in pub/sub

5. **Given** multiple agents request intelligence for the same target simultaneously
   **When** the first result arrives via stigmergic layer
   **Then** subsequent agents use the stigmergic result
   **And** redundant source queries are avoided

6. **Given** integration tests
   **When** tests verify swarm-wide intelligence sharing
   **Then** message publication and subscription are tested
   **And** TTL expiration is tested
   **And** query order (stigmergic → cache → sources) is tested

## Tasks / Subtasks

### Phase 0: Setup [BLUE]

- [x] Task 0.1: Verify prerequisites
  - [x] Confirm Story 5.7 is complete and tests pass
  - [x] Run: `pytest tests/unit/intelligence/test_aggregator.py tests/unit/intelligence/test_cached_aggregator.py -v --tb=short`
  - [x] Confirm Epic 3 (Event Bus) exists: `pytest tests/unit/core/test_events.py -v --tb=short`
  - [x] Review `EventBus` class in [events.py](file:///root/red/src/cyberred/core/events.py)
  - [x] Review channel patterns: `findings:{target_hash}:{type}` pattern in events.py

- [x] Task 0.2: Design stigmergic publication model
  - [x] Determine message format for `intel_enriched` type
  - [x] Ensure compatibility with existing `IntelResult` serialization
  - [x] Define TTL mechanism (5 min for stigmergic vs 1 hour for cache)
  - [x] **Decision:** Use existing `IntelResult.to_dict()` for serialization, wrap in stigmergic envelope

---

### Phase 1: StigmergicIntelligencePublisher Class [RED → GREEN → REFACTOR]

#### 1A: Create Publisher Class (AC: 1, 4)

- [x] Task 1.1: Create test file and publisher skeleton
  - [x] **[RED]** Create `tests/unit/intelligence/test_stigmergic_publisher.py`
  - [x] **[RED]** Write failing test: `StigmergicIntelligencePublisher` can be instantiated with `EventBus`
  - [x] **[RED]** Write failing test: `publish()` accepts service, version, and List[IntelResult]
  - [x] **[GREEN]** Create `src/cyberred/intelligence/stigmergic.py` with skeleton class
  - [x] **[REFACTOR]** Add comprehensive docstring

- [x] Task 1.2: Implement topic generation (AC: 1)
  - [x] **[RED]** Write failing test: `_make_topic()` generates `findings:{target_hash}:intel_enriched`
  - [x] **[RED]** Write failing test: target_hash is SHA256 of `service:version` (first 8 hex chars)
  - [x] **[GREEN]** Implement `_make_topic()`:
    ```python
    def _make_topic(self, service: str, version: str) -> str:
        """Generate stigmergic topic for intelligence results.
        
        Format: findings:{target_hash}:intel_enriched
        """
        target_key = f"{service}:{version}".lower()
        target_hash = hashlib.sha256(target_key.encode()).hexdigest()[:8]
        return f"findings:{target_hash}:intel_enriched"
    ```
  - [x] **[REFACTOR]** Ensure consistent normalization with cache key generation

- [x] Task 1.3: Implement publish method (AC: 1, 4)
  - [x] **[RED]** Write failing test: `publish()` serializes IntelResult list and calls `EventBus.publish()`
  - [x] **[RED]** Write failing test: published message includes `timestamp` and `ttl_seconds` (300)
  - [x] **[RED]** Write failing test: published message includes `source_agent_id` from context
  - [x] **[GREEN]** Implement `publish()`:
    ```python
    async def publish(
        self,
        service: str,
        version: str,
        results: List[IntelResult],
        agent_id: str = "system",
    ) -> int:
        """Publish intelligence results to stigmergic layer.
        
        Args:
            service: Service name (e.g., "Apache")
            version: Version string (e.g., "2.4.49")
            results: Intelligence results to share
            agent_id: ID of agent publishing the results
            
        Returns:
            Number of subscribers that received the message.
        """
        topic = self._make_topic(service, version)
        message = {
            "service": service,
            "version": version,
            "results": [r.to_dict() for r in results],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "ttl_seconds": self.TTL_SECONDS,  # 300 (5 min)
            "source_agent_id": agent_id,
        }
        return await self._event_bus.publish(topic, message)
    ```
  - [x] **[REFACTOR]** Add structured logging for publication events

---

### Phase 2: StigmergicIntelligenceSubscriber Class [RED → GREEN → REFACTOR]

#### 2A: Create Subscriber Class (AC: 2, 5)

- [x] Task 2.1: Create subscriber skeleton
  - [x] **[RED]** Write failing test: `StigmergicIntelligenceSubscriber` can be instantiated
  - [x] **[RED]** Write failing test: `subscribe()` registers callback with EventBus
  - [x] **[GREEN]** Implement subscriber class skeleton
  - [x] **[REFACTOR]** Add docstrings

- [x] Task 2.2: Implement subscription handler (AC: 2)
  - [x] **[RED]** Write failing test: subscriber receives messages from `findings:*:intel_enriched`
  - [x] **[RED]** Write failing test: subscriber deserializes IntelResult list from message
  - [x] **[RED]** Write failing test: subscriber stores results in local cache (dict)
  - [x] **[GREEN]** Implement `subscribe()`:
    ```python
    async def subscribe(self, callback: Callable[[str, str, List[IntelResult]], Awaitable[None]] = None):
        """Subscribe to stigmergic intelligence updates.
        
        Args:
            callback: Optional callback(service, version, results) for custom handling.
        """
        async def handler(channel: str, message: str):
            data = json.loads(message)
            service = data["service"]
            version = data["version"]
            results = [IntelResult.from_dict(r) for r in data["results"]]
            
            # Store in local cache
            key = f"{service}:{version}"
            self._cache[key] = {
                "results": results,
                "timestamp": data["timestamp"],
                "expires_at": datetime.utcnow() + timedelta(seconds=data["ttl_seconds"]),
            }
            
            if callback:
                await callback(service, version, results)
        
        return await self._event_bus.subscribe("findings:*:intel_enriched", handler)
    ```
  - [x] **[REFACTOR]** Add TTL-based expiration check

- [x] Task 2.3: Implement get from stigmergic cache (AC: 2, 3)
  - [x] **[RED]** Write failing test: `get()` returns cached results if not expired
  - [x] **[RED]** Write failing test: `get()` returns None if not found or expired
  - [x] **[GREEN]** Implement `get()`:
    ```python
    def get(self, service: str, version: str) -> Optional[List[IntelResult]]:
        """Get intelligence from stigmergic cache.
        
        Returns:
            List of IntelResult if found and not expired, None otherwise.
        """
        key = f"{service}:{version}"
        cached = self._cache.get(key)
        if cached is None:
            return None
        if datetime.utcnow() > cached["expires_at"]:
            del self._cache[key]
            return None
        return cached["results"]
    ```
  - [x] **[REFACTOR]** Add metrics for hit/miss tracking

---

### Phase 3: Integrate with CachedIntelligenceAggregator [RED → GREEN → REFACTOR]

#### 3A: Add Stigmergic Check to Query Path (AC: 3, 5)

- [x] Task 3.1: Extend CachedIntelligenceAggregator to use stigmergic layer
  - [x] **[RED]** Write failing test: aggregator accepts optional `StigmergicIntelligenceSubscriber`
  - [x] **[RED]** Write failing test: query checks stigmergic cache first (before Redis cache)
  - [x] **[RED]** Write failing test: when stigmergic hit, skip Redis cache and source queries
  - [x] **[GREEN]** Modify `CachedIntelligenceAggregator.__init__()` to accept subscriber:
    ```python
    def __init__(
        self,
        redis_client: RedisClient,
        stigmergic_subscriber: Optional[StigmergicIntelligenceSubscriber] = None,
    ):
        ...
        self._stigmergic = stigmergic_subscriber
    ```
  - [x] **[GREEN]** Modify `CachedIntelligenceAggregator.query()` to check stigmergic first:
    ```python
    async def query(self, service: str, version: str) -> List[IntelResult]:
        # Check stigmergic layer first (fastest path)
        if self._stigmergic:
            stigmergic_results = self._stigmergic.get(service, version)
            if stigmergic_results is not None:
                log.info("intelligence_stigmergic_hit", service=service, version=version)
                return stigmergic_results
        
        # Existing cache/source query logic...
        # ... (rest of existing implementation)
    ```
  - [x] **[REFACTOR]** Extract query order logic into private method for clarity

- [x] Task 3.2: Auto-publish results after source query (AC: 1, 5)
  - [x] **[RED]** Write failing test: after successful source query, results are published to stigmergic layer
  - [x] **[RED]** Write failing test: aggregator accepts optional `StigmergicIntelligencePublisher`
  - [x] **[GREEN]** Modify aggregator to publish after source query:
    ```python
    # After querying sources and caching results
    if results and self._stigmergic_publisher:
        await self._stigmergic_publisher.publish(service, version, results)
        log.info("intelligence_stigmergic_published", 
                 service=service, version=version, count=len(results))
    ```
  - [x] **[REFACTOR]** Ensure publish is non-blocking (fire-and-forget)

---

### Phase 4: Module Exports [RED → GREEN]

#### 4A: Update __init__.py (AC: 1)

- [x] Task 4.1: Export new classes
  - [x] **[RED]** Write test: `from cyberred.intelligence import StigmergicIntelligencePublisher` works
  - [x] **[RED]** Write test: `from cyberred.intelligence import StigmergicIntelligenceSubscriber` works
  - [x] **[GREEN]** Update `src/cyberred/intelligence/__init__.py`:
    ```python
    from cyberred.intelligence.stigmergic import (
        StigmergicIntelligencePublisher,
        StigmergicIntelligenceSubscriber,
    )
    
    __all__ = [
        # ... existing exports
        "StigmergicIntelligencePublisher",
        "StigmergicIntelligenceSubscriber",
    ]
    ```
  - [x] **[REFACTOR]** Update module docstring

---

### Phase 5: Integration Tests [RED → GREEN → REFACTOR]

- [x] Task 5.1: Create integration tests (AC: 6)
  - [x] Create `tests/integration/intelligence/test_stigmergic_publication.py`
  - [x] **[RED]** Write test: end-to-end pub/sub with real Redis
  - [x] **[RED]** Write test: multiple subscribers receive same message
  - [x] **[RED]** Write test: TTL expiration (5 min) is honored
  - [x] **[RED]** Write test: query order: stigmergic → cache → sources
  - [x] **[RED]** Write test: swarm scenario - Agent A publishes, Agent B receives via stigmergic
  - [x] **[GREEN]** Implement tests with testcontainers Redis (all 8 tests pass in 17s)
  - [x] **[REFACTOR]** Tests use `@pytest.mark.integration` marker

---

### Phase 6: Coverage & Documentation [BLUE]

- [x] Task 6.1: Verify 100% coverage
  - [x] Run: `pytest tests/unit/intelligence/test_stigmergic_publisher.py --cov=src/cyberred/intelligence/stigmergic --cov-report=term-missing`
  - [x] Ensure no untested branches (100% coverage achieved)

- [x] Task 6.2: Update Dev Agent Record
  - [x] Complete Agent Model Used
  - [x] Add Debug Log References
  - [x] Complete Completion Notes List
  - [x] Fill in File List

- [x] Task 6.3: Final verification
  - [x] Verify all ACs met
  - [x] Run full test suite: `pytest tests/unit/intelligence/ -v --tb=short` (275 tests pass)
  - [x] Update story status to `review`

## Dev Notes

### Architecture Reference

From [architecture.md#L270-L272](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L270-L272):
```
6. Finding published to stigmergic layer (other agents skip re-query)
Stigmergic Publication: `findings:{target_hash}:intel_enriched` — shares intelligence results swarm-wide.
```

From [architecture.md#L226-L233](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L226-L233):
```
Event Bus (Real-time): Redis Pub/Sub — Fire-and-forget stigmergic signals, low latency
Stigmergic Signals: Agent → Redis Pub/Sub → Subscribed Agents (real-time)
```

**FR75 Reference:**
> Intelligence queries are non-blocking — agents continue if sources timeout

### Query Order (CRITICAL)

| Step | Source | TTL | Purpose |
|------|--------|-----|---------|
| 1 | Stigmergic | 5 min | Real-time swarm sharing |
| 2 | Redis Cache | 1 hour | Persistent per-node cache |
| 3 | Intelligence Sources | N/A | Live query to external sources |

### Channel Pattern

The topic `findings:{target_hash}:intel_enriched` must match the existing channel pattern in [events.py](file:///root/red/src/cyberred/core/events.py):
```python
CHANNEL_PATTERNS = [
    re.compile(r"^findings:[a-f0-9]+:[a-z0-9_-]+$", re.IGNORECASE),  # findings:hash:type
    ...
]
```

The `intel_enriched` type is valid because it matches `[a-z0-9_-]+`.

### Message Format

```json
{
    "service": "Apache",
    "version": "2.4.49",
    "results": [
        {
            "source": "cisa_kev",
            "cve_id": "CVE-2021-41773",
            "severity": "critical",
            "exploit_available": true,
            "exploit_path": "/path/to/exploit",
            "confidence": 1.0,
            "priority": 1,
            "metadata": {}
        }
    ],
    "timestamp": "2026-01-08T05:00:00Z",
    "ttl_seconds": 300,
    "source_agent_id": "recon-47"
}
```

### Key Learnings from Story 5.9

1. **Use structlog for logging** — NOT `print()` statements
2. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases explicitly
3. **Verify coverage claims** — Run `pytest --cov` before marking done
4. **Use pytest markers** — Always include `@pytest.mark.unit` and `@pytest.mark.integration`
5. **Async methods** — All pub/sub operations must be async
6. **Graceful degradation** — Stigmergic failures should not block agent operation
7. **IntelResult serialization** — Use `to_dict()` for serialization, `from_dict()` for deserialization

### Existing Code References

| File | Purpose | Story |
|------|---------|-------|
| [events.py](file:///root/red/src/cyberred/core/events.py) | `EventBus` with `publish()`, `subscribe()` | Epic 3 |
| [base.py](file:///root/red/src/cyberred/intelligence/base.py) | `IntelResult` with `to_dict()`, `from_dict()` | 5.1 |
| [cache.py](file:///root/red/src/cyberred/intelligence/cache.py) | `IntelligenceCache` | 5.8 |
| [aggregator.py](file:///root/red/src/cyberred/intelligence/aggregator.py) | `CachedIntelligenceAggregator` | 5.7, 5.8, 5.9 |

### EventBus Pattern Reference

From [events.py](file:///root/red/src/cyberred/core/events.py):
```python
# Publish example
await event_bus.publish("findings:a1b2c3d4:intel_enriched", message_dict)

# Subscribe example
async def handler(channel: str, message: str):
    data = json.loads(message)
    # Process...

subscription = await event_bus.subscribe("findings:*:intel_enriched", handler)
```

### Test Strategy

**Unit Tests (`tests/unit/intelligence/test_stigmergic_publisher.py`):**
- Mock `EventBus`
- Test topic generation
- Test message serialization
- Test TTL inclusion
- Test callback handling

**Integration Tests (`tests/integration/intelligence/test_stigmergic_publication.py`):**
- Real Redis (testcontainers)
- End-to-end pub/sub
- Multi-subscriber scenario
- Query order verification
- TTL expiration

### Example Usage

```python
from cyberred.core.events import EventBus
from cyberred.intelligence import (
    CachedIntelligenceAggregator,
    StigmergicIntelligencePublisher,
    StigmergicIntelligenceSubscriber,
)
from cyberred.storage import RedisClient

# Setup
redis = RedisClient(config)
await redis.connect()
event_bus = EventBus(redis)

# Create stigmergic layer
publisher = StigmergicIntelligencePublisher(event_bus)
subscriber = StigmergicIntelligenceSubscriber(event_bus)

# Start listening for stigmergic intelligence
await subscriber.subscribe()

# Create aggregator with stigmergic integration
aggregator = CachedIntelligenceAggregator(
    redis_client=redis,
    stigmergic_subscriber=subscriber,
    stigmergic_publisher=publisher,
)
aggregator.add_source(CisaKevSource())
aggregator.add_source(NvdSource())

# Agent A queries (no stigmergic, goes to sources, publishes)
results_a = await aggregator.query("Apache", "2.4.49")
# Results published to findings:{hash}:intel_enriched

# Agent B queries (stigmergic hit, skips sources)
results_b = await aggregator.query("Apache", "2.4.49")
# Log: intelligence_stigmergic_hit service=Apache version=2.4.49
```

### References

- **Epic 5 Overview:** [epics-stories.md](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2056-L2098)
- **Story 5.10 Requirements:** [epics-stories.md#L2329-L2349](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2329-L2349)
- **Story 5.9 Implementation:** [5-9-offline-intelligence-mode.md](file:///root/red/_bmad-output/implementation-artifacts/5-9-offline-intelligence-mode.md)
- **Architecture - Stigmergic:** [architecture.md#L270-L272](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L270-L272)
- **Architecture - Event Bus:** [architecture.md#L226-L233](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L226-L233)
- **FR75:** Intelligence queries are non-blocking

## Dev Agent Record

### Agent Model Used

Claude 4 Opus (Antigravity)

### Debug Log References

- All 275 intelligence tests pass with no regressions
- 100% code coverage on `stigmergic.py` (54 statements, 6 branches)

### Completion Notes List

- Created `StigmergicIntelligencePublisher` class with topic generation and publish method
- Created `StigmergicIntelligenceSubscriber` class with subscribe handler and local cache
- Extended `CachedIntelligenceAggregator` to accept stigmergic_subscriber and stigmergic_publisher
- Implemented query order: stigmergic → cache → sources per architecture spec
- Auto-publish to stigmergic layer after source queries with graceful degradation
- TTL mechanism: 5 min for stigmergic (vs 1 hour for Redis cache)
- 28 unit tests covering publisher, subscriber, and aggregator integration
- 8 integration tests with real Redis using testcontainers (17s runtime)

### File List

| Action | File Path |
|--------|-----------|
| [NEW] | `src/cyberred/intelligence/stigmergic.py` |
| [MODIFY] | `src/cyberred/intelligence/aggregator.py` |
| [MODIFY] | `src/cyberred/intelligence/__init__.py` |
| [NEW] | `tests/unit/intelligence/test_stigmergic_publisher.py` |
| [NEW] | `tests/integration/intelligence/test_stigmergic_publication.py` |
