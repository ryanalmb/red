# Story 5.9: Offline Intelligence Mode

Status: done

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD methodology at all times. All tasks marked [RED], [GREEN], [REFACTOR] must be followed explicitly. Each task must have a failing test before implementation.

> [!NOTE]
> **DEPENDENCY:** Story 5.8 (Redis Intelligence Cache) must be complete. This story extends:
> - [aggregator.py](file:///root/red/src/cyberred/intelligence/aggregator.py) — `CachedIntelligenceAggregator`
> - [cache.py](file:///root/red/src/cyberred/intelligence/cache.py) — `IntelligenceCache`

> [!CAUTION]
> **GRACEFUL DEGRADATION:** This story implements offline fallback. When ALL intelligence sources timeout or fail, the system MUST NOT raise exceptions. Return stale cached data or empty results with appropriate flags.

## Story

As an **operator**,
I want **intelligence queries to work with cached data when sources are unavailable**,
So that **engagements can continue during network issues (FR73)**.

## Acceptance Criteria

1. **Given** Story 5.8 is complete
   **When** all intelligence sources timeout or fail
   **Then** aggregator returns cached results if available
   **And** results are marked `stale: true` with cache timestamp

2. **Given** sources fail and cache has data
   **When** stale results are returned
   **Then** log warns "Intelligence sources unavailable, using cached data"

3. **Given** sources fail and cache has no data for query
   **When** aggregator attempts fallback
   **Then** aggregator returns empty result with `offline: true`
   **And** agent proceeds without intelligence enrichment

4. **Given** at least one source succeeds
   **When** other sources fail
   **Then** normal behavior applies (partial results from successful source)
   **And** cache is updated with fresh data

5. **Given** offline mode is active
   **Then** cache data never expires (stale > nothing)
   **And** stale results include `cached_at` timestamp

6. **Given** integration tests
   **When** tests simulate offline scenarios
   **Then** offline fallback behavior is verified
   **And** stale flag propagation is tested

7. **Given** offline mode is active
   **When** health_check is called
   **Then** status reports "degraded" (healthy: true) instead of failure
   **And** details include offline source count

8. **Given** offline fallback occurs
   **Then** structured log event `intelligence_offline_mode_active` is emitted
   **And** metric `intelligence_offline_fallback_count` is incremented

## Tasks / Subtasks

### Phase 0: Setup [BLUE]

- [x] Task 0.1: Verify prerequisites
  - [x] Confirm Story 5.8 is complete and tests pass
  - [x] Run: `pytest tests/unit/intelligence/test_cache.py tests/unit/intelligence/test_cached_aggregator.py -v --tb=short`
  - [x] Verify `CachedIntelligenceAggregator` exists in [aggregator.py](file:///root/red/src/cyberred/intelligence/aggregator.py)
  - [x] Review existing `IntelResult` structure in [base.py](file:///root/red/src/cyberred/intelligence/base.py)

- [x] Task 0.2: Design offline response structure
  - [x] Determine how to represent `stale` and `offline` flags
  - [x] Option A: Add `stale: bool` and `offline: bool` fields to `IntelResult`
  - [x] Option B: Create wrapper `OfflineIntelligenceResult` dataclass
  - [x] Option C: Return empty list with metadata (logging only)
  - [x] **Decision:** Extend `IntelResult.metadata` with `stale`, `offline`, `cached_at` keys

---

### Phase 1: IntelResult Metadata Enhancement [RED → GREEN → REFACTOR]

#### 1A: Add Stale/Offline Metadata Support (AC: 1, 3, 5)

- [x] Task 1.1: Test metadata field handling
  - [x] **[RED]** Create `tests/unit/intelligence/test_offline_mode.py`
  - [x] **[RED]** Write failing test: `IntelResult` can have `metadata["stale"] = True`
  - [x] **[RED]** Write failing test: `IntelResult` can have `metadata["offline"] = True`
  - [x] **[RED]** Write failing test: `IntelResult` can have `metadata["cached_at"]` (ISO timestamp)
  - [x] **[GREEN]** Verify existing `IntelResult.metadata: dict` supports these keys (no code change needed)
  - [x] **[REFACTOR]** Add docstring documenting reserved metadata keys

---

### Phase 2: IntelligenceCache Stale Data Retrieval [RED → GREEN → REFACTOR]

#### 2A: Implement Get with Metadata (AC: 1, 5)

- [x] Task 2.1: Cache retrieval with stale marking
  - [x] **[RED]** Write failing test: `get_with_metadata()` returns `(results, cached_at)`
  - [x] **[RED]** Write failing test: `cached_at` is stored when cache is populated
  - [x] **[RED]** Write failing test: `cached_at` is `None` on cache miss
  - [x] **[GREEN]** Modify `IntelligenceCache.set()` to include `_cached_at` timestamp in JSON:
    ```python
    async def set(self, service: str, version: str, results: List[IntelResult], ttl: Optional[int] = None) -> bool:
        """Cache intelligence results with timestamp."""
        key = self._make_key(service, version)
        expiry = ttl if ttl is not None else self._ttl
        
        try:
            cache_entry = {
                "results": [asdict(r) for r in results],
                "cached_at": datetime.utcnow().isoformat() + "Z",
            }
            json_data = json.dumps(cache_entry)
            await self._redis.setex(key, expiry, json_data)
            return True
        except Exception as e:
            log.warning("cache_set_error", key=key, error=str(e))
            return False
    ```
  - [x] **[GREEN]** Implement `get_with_metadata()`:
    ```python
    async def get_with_metadata(self, service: str, version: str) -> Tuple[Optional[List[IntelResult]], Optional[str]]:
        """Get cached results with cache timestamp.
        
        Returns:
            Tuple of (results, cached_at) where cached_at is ISO timestamp or None.
        """
        key = self._make_key(service, version)
        
        try:
            data = await self._redis.get(key)
            if data is None:
                return None, None
            
            cache_entry = json.loads(data)
            # Handle legacy format (list of results without wrapper)
            if isinstance(cache_entry, list):
                results = [IntelResult.from_json(r) for r in cache_entry]
                return results, None
            
            results = [IntelResult.from_json(r) for r in cache_entry.get("results", [])]
            cached_at = cache_entry.get("cached_at")
            return results, cached_at
        except Exception as e:
            log.warning("cache_get_error", key=key, error=str(e))
            return None, None
    ```
  - [x] **[REFACTOR]** Update existing `get()` to use `get_with_metadata()` internally

---

### Phase 3: Offline Mode in CachedIntelligenceAggregator [RED → GREEN → REFACTOR]

#### 3A: Implement Offline Fallback (AC: 1, 2, 3, 4)

- [x] Task 3.1: Detect all-source failure
  - [x] **[RED]** Write failing test: when all sources timeout, `query()` still returns
  - [x] **[RED]** Write failing test: when all sources timeout AND cache has data, return cached with `stale: true`
  - [x] **[RED]** Write failing test: when all sources timeout AND no cache, return empty list (not exception)
  - [x] **[RED]** Write failing test: log warning "Intelligence sources unavailable, using cached data"
  - [x] **[RED]** Write failing test: stale results include `cached_at` in metadata
  - [x] **[GREEN]** Modify `CachedIntelligenceAggregator.query()`:
    ```python
    async def query(self, service: str, version: str) -> List[IntelResult]:
        """Query sources with caching, coalescing, and offline fallback."""
        key = f"{service}:{version}"
        
        async with self._lock_creation_lock:
            if key not in self._request_locks:
                self._request_locks[key] = asyncio.Lock()
            lock = self._request_locks[key]
        
        async with lock:
            # Check cache first (fast path)
            cached, cached_at = await self.cache.get_with_metadata(service, version)
            if cached is not None:
                return cached  # Fresh cache hit
            
            # Cache miss - query sources
            results = await super().query(service, version)
            
            # Check if ALL sources failed (empty results + errors logged)
            # We need to track source failures to detect this
            if not results and self._all_sources_failed():
                # Attempt stale cache fallback
                stale_results, stale_cached_at = await self._get_stale_cache(service, version)
                if stale_results is not None:
                    log.warning("intelligence_offline_mode_stale", 
                               service=service, version=version,
                               message="Intelligence sources unavailable, using cached data")
                    # Mark results as stale
                    return self._mark_as_stale(stale_results, stale_cached_at)
                else:
                    log.warning("intelligence_offline_mode_empty",
                               service=service, version=version)
                    return []  # No cache available
            
            # Cache fresh results
            await self.cache.set(service, version, results)
            return results
    ```
  - [x] **[REFACTOR]** Extract helper methods for cleaner code

- [x] Task 3.2: Implement stale marking helper
  - [x] **[RED]** Write failing test: `_mark_as_stale()` adds `metadata["stale"] = True`
  - [x] **[RED]** Write failing test: `_mark_as_stale()` adds `metadata["cached_at"]`
  - [x] **[GREEN]** Implement `_mark_as_stale()`:
    ```python
    def _mark_as_stale(self, results: List[IntelResult], cached_at: Optional[str]) -> List[IntelResult]:
        """Mark all results as stale with cache timestamp."""
        stale_results = []
        for r in results:
            metadata = {**r.metadata, "stale": True}
            if cached_at:
                metadata["cached_at"] = cached_at
            stale_results.append(IntelResult(
                source=r.source,
                cve_id=r.cve_id,
                severity=r.severity,
                exploit_available=r.exploit_available,
                exploit_path=r.exploit_path,
                confidence=r.confidence,
                priority=r.priority,
                metadata=metadata,
            ))
        return stale_results
    ```

- [x] Task 3.3: Track source failures
  - [x] **[RED]** Write failing test: `_all_sources_failed()` returns `True` when all queries failed
  - [x] **[RED]** Write failing test: `_all_sources_failed()` returns `False` when at least one succeeded
  - [x] **[GREEN]** Add instance variable to track query outcomes per request
  - [x] **[GREEN]** Update `_query_source_with_timeout()` to record success/failure:
    ```python
    # In IntelligenceAggregator base class
    def __init__(self, ...):
        ...
        self._last_query_failures: int = 0
        self._last_query_source_count: int = 0
    
    async def _query_source_with_timeout(self, ...):
        ...
        # Track failure
        if not results:
            self._last_query_failures += 1
        return results
    
    def _all_sources_failed(self) -> bool:
        """Check if all sources failed in the last query."""
        return self._last_query_failures >= self._last_query_source_count > 0
    ```
  - [x] **[REFACTOR]** Reset failure counters at query start

- [x] Task 3.4: Implement stale cache retrieval
  - [x] **[RED]** Write failing test: `_get_stale_cache()` bypasses TTL expiration
  - [x] **[RED]** Write failing test: `_get_stale_cache()` returns data even if "expired"
  - [x] **[GREEN]** Implement `_get_stale_cache()`:
    ```python
    async def _get_stale_cache(self, service: str, version: str) -> Tuple[Optional[List[IntelResult]], Optional[str]]:
        """Get cached data ignoring TTL (stale is better than nothing).
        
        In offline mode, we return cached data regardless of age.
        """
        return await self.cache.get_with_metadata(service, version)
    ```
  - [x] Note: Since Redis TTL auto-deletes keys, truly expired data is gone. Consider separate "archive" key with longer TTL or no expiration for offline fallback.

#### 3B: Health & Observability (AC: 7, 8)

- [x] Task 3.5: Implement Offline Health Check
  - [x] **[RED]** Write failing test: `health_check` returns true but 'degraded' when offline
  - [x] **[GREEN]** Update `health_check` in `CachedIntelligenceAggregator` to tolerate source failures if cache is available
  - [x] **[REFACTOR]** Ensure health dictionary structure is consistent

- [x] Task 3.6: Implement Offline Metrics
  - [x] **[RED]** Write failing test: log event `intelligence_offline_mode_active` emitted
  - [x] **[GREEN]** Ensure `log.warning` includes `event="intelligence_offline_mode_active"`

---

### Phase 4: Offline Archive (Optional Enhancement) [RED → GREEN → REFACTOR]

#### 4A: Implement Long-Term Archive for Offline Mode (AC: 5)

- [x] Task 4.1: Archive cache for offline fallback
  - [x] **[RED]** Write failing test: `set()` also writes to archive key with no TTL
  - [x] **[RED]** Write failing test: archive key format is `intel:archive:{service}:{version}`
  - [x] **[RED]** Write failing test: `_get_stale_cache()` checks archive when main cache misses
  - [x] **[GREEN]** Modify `IntelligenceCache.set()` to write archive copy:
    ```python
    async def set(self, ...):
        # Write main cache with TTL
        await self._redis.setex(key, expiry, json_data)
        # Write archive without TTL for offline fallback
        archive_key = f"intel:archive:{service_norm}:{version_norm}"
        await self._redis.set(archive_key, json_data)  # No TTL
    ```
  - [x] **[REFACTOR]** Add config option to disable archive for memory-constrained environments

---

### Phase 5: Module Exports [RED → GREEN]

#### 5A: Verify Exports (AC: 1)

- [x] Task 5.1: Verify imports work
  - [x] **[RED]** Write test: `from cyberred.intelligence import CachedIntelligenceAggregator` works (already exists)
  - [x] **[GREEN]** No changes needed if all modifications are internal to existing classes
  - [x] **[REFACTOR]** Update module docstring if new public methods added

---

### Phase 6: Integration Tests [RED → GREEN → REFACTOR]

- [x] Task 6.1: Create integration tests (AC: 6)
  - [x] Create `tests/integration/intelligence/test_offline_mode.py`
  - [x] **[RED]** Write test: offline fallback with real Redis (mark `@pytest.mark.integration`)
  - [x] **[RED]** Write test: simulate all sources failing (use mock sources that raise/timeout)
  - [x] **[RED]** Write test: verify stale flag in returned results
  - [x] **[RED]** Write test: verify `cached_at` timestamp propagation
  - [x] **[RED]** Write test: verify empty result when no cache exists
  - [x] **[GREEN]** Implement tests with real Redis container or testcontainers
  - [x] **[REFACTOR]** Add skip markers for tests requiring Redis

---

### Phase 7: Coverage & Documentation [BLUE]

- [x] Task 7.1: Verify 100% coverage
  - [x] Run: `pytest tests/unit/intelligence/test_offline_mode.py --cov=src/cyberred/intelligence/cache --cov=src/cyberred/intelligence/aggregator --cov-report=term-missing`
  - [x] Ensure no untested branches in offline logic

- [x] Task 7.2: Update Dev Agent Record
  - [x] Complete Agent Model Used
  - [x] Add Debug Log References
  - [x] Complete Completion Notes List
  - [x] Fill in File List

- [x] Task 7.3: Final verification
  - [x] Verify all ACs met
  - [x] Run full test suite: `pytest tests/unit/intelligence/ -v --tb=short`
  - [x] Update story status to `review`

## Dev Notes

### Architecture Reference

From [architecture.md#L841](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L841):
```
│   │   ├── cache.py                  # Redis-backed caching (offline-capable)
```

From [epics-stories.md#L2304-L2326](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2304-L2326):
```
Story 5.9: Offline Intelligence Mode
- Graceful degradation pattern
- Cache never expires in offline mode (stale > nothing)
- Offline detection: all sources fail within timeout
```

**FR73 Reference:**
> Intelligence layer caches results in Redis for **offline capability** (configurable TTL)

### Graceful Degradation Pattern (ERR3)

| Scenario | Action | Result |
|----------|--------|--------|
| All sources timeout | Check cache | Return stale data with `stale: true` |
| All sources timeout, no cache | Return empty | `[]` with log warning |
| Some sources succeed | Normal behavior | Fresh results cached |
| Cache expired, sources down | Check archive | Return archived data if available |

### Key Design Decisions

1. **Stale Marking:** Use `metadata["stale"]: bool` instead of new dataclass field for backward compatibility
2. **Cache Timestamp:** Store `cached_at` in cache entry JSON wrapper, propagate to metadata on stale return
3. **Archive Key:** Separate `intel:archive:{key}` without TTL for true offline capability
4. **Failure Detection:** Track source failures per query using instance counters, reset at query start
5. **No Exceptions:** Offline mode MUST return `List[IntelResult]`, never raise exception

### Key Learnings from Story 5.8

1. **Use structlog for logging** — NOT `print()` statements
2. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases explicitly
3. **Verify coverage claims** — Run `pytest --cov` before marking done
4. **Use pytest markers** — Always include `@pytest.mark.unit` and `@pytest.mark.integration`
5. **Async methods** — All cache and aggregator operations must be async
6. **Graceful degradation** — Return empty/partial results on error, never raise exception
7. **IntelResult serialization** — Use `asdict()` for serialization, `from_json()` for deserialization
8. **Request coalescing** — Existing lock pattern prevents stampede; extend for offline

### Existing Code References

| File | Purpose | Story |
|------|---------|-------|
| [base.py](file:///root/red/src/cyberred/intelligence/base.py) | `IntelResult` with `metadata` dict | 5.1 |
| [cache.py](file:///root/red/src/cyberred/intelligence/cache.py) | `IntelligenceCache` | 5.8 |
| [aggregator.py](file:///root/red/src/cyberred/intelligence/aggregator.py) | `CachedIntelligenceAggregator` | 5.7, 5.8 |
| [test_cache.py](file:///root/red/tests/unit/intelligence/test_cache.py) | Cache unit tests | 5.8 |
| [test_cached_aggregator.py](file:///root/red/tests/unit/intelligence/test_cached_aggregator.py) | Aggregator caching tests | 5.8 |

### Test Strategy

**Unit Tests (`tests/unit/intelligence/test_offline_mode.py`):**
- Mock `IntelligenceCache` and sources
- Test failure detection
- Test stale marking
- Test empty fallback
- Test log warnings

**Integration Tests (`tests/integration/intelligence/test_offline_mode.py`):**
- Real Redis (testcontainers or Sentinel cluster)
- Simulate source failures
- Verify cache archive persistence
- Test TTL-bypassed retrieval

### Example Usage

```python
from cyberred.intelligence import CachedIntelligenceAggregator
from cyberred.storage import RedisClient

# Create aggregator with offline capability
redis = RedisClient(config)
await redis.connect()

aggregator = CachedIntelligenceAggregator(redis)
aggregator.add_source(CisaKevSource())  # Will timeout
aggregator.add_source(NvdSource())      # Will timeout

# First query: sources work, results cached
results1 = await aggregator.query("Apache", "2.4.49")
assert results1[0].metadata.get("stale") is None  # Fresh

# Simulate network failure (all sources timeout)
# Second query: offline fallback
results2 = await aggregator.query("Apache", "2.4.49")
assert results2[0].metadata.get("stale") is True
assert "cached_at" in results2[0].metadata

# Query for uncached service (no fallback available)
results3 = await aggregator.query("Unknown", "1.0")
assert results3 == []  # Empty, offline mode with no cache
```

### References

- **Epic 5 Overview:** [epics-stories.md#L2056-L2098](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2056-L2098)
- **Story 5.9 Requirements:** [epics-stories.md#L2304-L2326](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2304-L2326)
- **Story 5.8 Implementation:** [5-8-redis-intelligence-cache.md](file:///root/red/_bmad-output/implementation-artifacts/5-8-redis-intelligence-cache.md)
- **Architecture - Offline Mode:** [architecture.md#L841](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L841)
- **FR73:** Intelligence caching for offline capability

## Dev Agent Record

### Agent Model Used

Gemini 2.5 Pro (Code Review Fix Pass - 2026-01-08)

### Debug Log References

- Tests fixed: `test_cached_aggregator.py` - mock API updated from `cache.get()` to `cache.get_with_metadata()`
- Markers added: `@pytest.mark.unit` to 3 async tests in `test_offline_mode.py`

### Completion Notes List

1. Story status was inconsistent: story file said `ready-for-dev` while sprint-status.yaml said `review`
2. Tasks 3.1-3.4 were implemented but not marked complete in story
3. Unit tests in `test_cached_aggregator.py` broke when cache API changed to use `get_with_metadata()`
4. Integration test with real Redis container passes (`test_offline_mode_integration`)
5. All offline fallback logic working: stale marking, archive retrieval, degraded health status

### File List

| Action | File Path |
|--------|-----------|
| [MODIFY] | `src/cyberred/intelligence/cache.py` |
| [MODIFY] | `src/cyberred/intelligence/aggregator.py` |
| [MODIFY] | `src/cyberred/intelligence/base.py` |
| [NEW] | `tests/unit/intelligence/test_offline_mode.py` |
| [NEW] | `tests/integration/intelligence/test_offline_mode.py` |
| [MODIFY] | `tests/unit/intelligence/test_cached_aggregator.py` |

