"""Intelligence Aggregator Implementation.

This module implements the IntelligenceAggregator class, which orchestrates
queries to multiple intelligence sources in parallel.
"""

import asyncio
import time
from typing import List, Optional, Dict, Any, Set, Tuple
import structlog

from cyberred.intelligence.base import IntelligenceSource, IntelResult, IntelPriority
from cyberred.intelligence.cache import IntelligenceCache
from cyberred.intelligence.metrics import IntelligenceErrorMetrics
from cyberred.storage.redis_client import RedisClient

log = structlog.get_logger()

class IntelligenceAggregator:
    """Unified intelligence query interface.
    
    Queries all registered intelligence sources in parallel and
    returns deduplicated, prioritized results.
    
    Attributes:
        sources: List of registered IntelligenceSource instances.
        timeout: Per-source query timeout in seconds (default 5.0).
        max_total_time: Maximum total aggregation time (default 6.0).
    """
    
    def __init__(
        self,
        timeout: float = 5.0,
        max_total_time: float = 6.0,
    ) -> None:
        """Initialize the aggregator.
        
        Args:
            timeout: Per-source query timeout in seconds.
            max_total_time: Maximum total aggregation time.
        """
        self._sources: List[IntelligenceSource] = []
        self._timeout = timeout
        self._max_total_time = max_total_time
        self._error_metrics = IntelligenceErrorMetrics()

    @property
    def error_metrics(self) -> IntelligenceErrorMetrics:
        """Get error metrics."""
        return self._error_metrics

    @property
    def sources(self) -> List[IntelligenceSource]:
        """Get list of registered sources."""
        return list(self._sources)

    def add_source(self, source: IntelligenceSource) -> None:
        """Add an intelligence source to the aggregator.
        
        Args:
            source: IntelligenceSource implementation to add.
            
        Raises:
            TypeError: If source is not an IntelligenceSource.
        """
        if not isinstance(source, IntelligenceSource):
            raise TypeError(f"Expected IntelligenceSource, got {type(source).__name__}")
        self._sources.append(source)
        log.info("aggregator_source_added", source=source.name)

    def remove_source(self, name: str) -> bool:
        """Remove a source by name.
        
        Args:
            name: Name of the source to remove.
            
        Returns:
            True if source was found and removed, False otherwise.
        """
        for i, source in enumerate(self._sources):
            if source.name == name:
                del self._sources[i]
                log.info("aggregator_source_removed", source=name)
                return True
        return False

    async def _query_source_with_timeout(
        self, 
        source: IntelligenceSource, 
        service: str, 
        version: str
    ) -> Optional[List[IntelResult]]:
        """Query a single source with timeout.
        
        Args:
            source: Intelligence source to query.
            service: Service name.
            version: Version string.
            
        Returns:
            List of IntelResult from source, or None on timeout/error.
        """
        try:
            results = await asyncio.wait_for(
                source.query(service, version),
                timeout=self._timeout,
            )
            
            # Validate result type
            if not isinstance(results, list):
                self._error_metrics.record_error(source.name, "InvalidResultType")
                log.warning("aggregator_invalid_result_type", 
                           source=source.name, 
                           actual_type=type(results).__name__)
                return None
            
            valid_results = []
            for item in results:
                if isinstance(item, IntelResult):
                    valid_results.append(item)
                else:
                    log.warning("aggregator_invalid_result_item", 
                               source=source.name, 
                               item_type=type(item).__name__)
            
            log.debug("aggregator_source_complete", 
                     source=source.name, 
                     result_count=len(valid_results))
            return valid_results
        except asyncio.TimeoutError:
            self._error_metrics.record_timeout(source.name)
            log.warning("aggregator_source_timeout", 
                       source=source.name, 
                       timeout=self._timeout)
            return None
        except Exception as e:
            self._error_metrics.record_error(source.name, type(e).__name__)
            log.warning("aggregator_source_error", 
                       source=source.name, 
                       error=str(e))
            return None

    def _merge_results(
        self, 
        existing: IntelResult, 
        new: IntelResult
    ) -> IntelResult:
        """Merge two IntelResult objects for the same CVE.
        
        Args:
            existing: Previously stored result.
            new: New result to merge.
            
        Returns:
            Merged IntelResult with consolidated data.
        """
        # Track sources that contributed to this result
        sources_key = "_sources"
        existing_sources = existing.metadata.get(sources_key, [existing.source])
        merged_sources = list(set(existing_sources + [new.source]))
        
        # Merge metadata (new overwrites existing for same keys)
        merged_metadata = {**existing.metadata, **new.metadata}
        merged_metadata[sources_key] = merged_sources
        
        # Pick best values
        best_priority = min(existing.priority, new.priority)
        best_confidence = max(existing.confidence, new.confidence)
        exploit_available = existing.exploit_available or new.exploit_available
        
        # Keep exploit_path from highest priority source
        exploit_path = existing.exploit_path
        if new.priority < existing.priority and new.exploit_path:
            exploit_path = new.exploit_path
        elif not exploit_path and new.exploit_path:
            exploit_path = new.exploit_path
        
        # Use severity from highest priority source
        severity = existing.severity
        source_name = existing.source
        if new.priority < existing.priority:
            severity = new.severity
            source_name = new.source
        
        return IntelResult(
            source=source_name,
            cve_id=existing.cve_id,
            severity=severity,
            exploit_available=exploit_available,
            exploit_path=exploit_path,
            confidence=best_confidence,
            priority=best_priority,
            metadata=merged_metadata,
        )

    def _deduplicate_results(self, results: List[IntelResult]) -> List[IntelResult]:
        """Deduplicate results by CVE ID, merging metadata.
        
        Results with the same CVE ID are merged:
        - Highest priority (lowest number) is kept
        - Highest confidence is kept
        - Metadata is consolidated from all sources
        - exploit_available is True if any source has it
        
        Results without CVE IDs are kept as-is (no deduplication).
        
        Args:
            results: List of IntelResult from all sources.
            
        Returns:
            Deduplicated list of IntelResult.
        """
        cve_results: Dict[str, IntelResult] = {}
        non_cve_results: List[IntelResult] = []
        
        for result in results:
            if not result.cve_id:
                # No CVE ID - keep as separate entry
                non_cve_results.append(result)
                continue
            
            cve_id = result.cve_id
            if cve_id not in cve_results:
                # First occurrence - store directly
                cve_results[cve_id] = result
            else:
                # Merge with existing result
                existing = cve_results[cve_id]
                cve_results[cve_id] = self._merge_results(existing, result)
        
        # Combine CVE and non-CVE results
        return list(cve_results.values()) + non_cve_results

    async def query(self, service: str, version: str) -> List[IntelResult]:
        """Query all intelligence sources for service/version.
        
        Queries all registered sources in parallel with timeout handling.
        Results are deduplicated by CVE ID and sorted by priority.
        
        Args:
            service: Service name (e.g., "Apache", "OpenSSH")
            version: Version string (e.g., "2.4.49", "8.2p1")
            
        Returns:
            List of IntelResult sorted by priority (lowest number first).
            Empty list if all sources fail or timeout.
        """
        log.info("aggregator_query_start", service=service, version=version, 
                 source_count=len(self._sources))
        
        if not service:
            log.warning("aggregator_empty_service")
            return []
        
        if not self._sources:
            log.warning("aggregator_no_sources")
            return []
        
        start_time = time.time()
        
        # Query all sources in parallel with timeout
        tasks = [
            self._query_source_with_timeout(source, service, version)
            for source in self._sources
        ]
        
        try:
            # Wait for all sources with total timeout
            results_lists = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self._max_total_time,
            )
        except asyncio.TimeoutError:
            log.warning("aggregator_total_timeout", max_total_time=self._max_total_time)
            results_lists = []
        
        # Flatten and filter out exceptions
        all_results: List[IntelResult] = []
        for i, result in enumerate(results_lists):
            if result is None:
                continue

            if isinstance(result, list):
                all_results.extend(result)
        
        # Deduplicate and sort
        deduplicated = self._deduplicate_results(all_results)
        # Sort by priority (asc) then confidence (desc)
        sorted_results = sorted(
            deduplicated, 
            key=lambda r: (r.priority, -r.confidence)
        )
        
        duration = time.time() - start_time
        log.info("aggregator_query_complete", 
                 result_count=len(sorted_results),
                 source_count=len(self._sources),
                 duration_ms=round(duration * 1000, 2))
        
        return sorted_results

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all sources.
        
        Returns:
            Dict containing overall health status and per-source status.
        """
        source_status = {}
        overall_healthy = False
        
        for source in self._sources:
            start = time.time()
            try:
                is_healthy = await source.health_check()
                latency = (time.time() - start) * 1000
                source_status[source.name] = {
                    "healthy": is_healthy,
                    "latency_ms": round(latency, 2)
                }
                if is_healthy:
                    overall_healthy = True
            except Exception as e:
                source_status[source.name] = {
                    "healthy": False,
                    "error": str(e)
                }
        
        return {
            "healthy": overall_healthy,
            "sources": source_status
        }


class CachedIntelligenceAggregator(IntelligenceAggregator):
    """Intelligence aggregator with Redis caching and stigmergic integration.
    
    Extends IntelligenceAggregator to:
    - Cache results in Redis
    - Coalesce concurrent requests
    - Check stigmergic layer for swarm-shared intelligence
    - Auto-publish results to stigmergic layer
    
    Query order: stigmergic → cache → sources
    """
    
    def __init__(
        self,
        redis_client: RedisClient,
        stigmergic_subscriber: "StigmergicIntelligenceSubscriber" = None,
        stigmergic_publisher: "StigmergicIntelligencePublisher" = None,
    ):
        """Initialize cached aggregator.
        
        Args:
            redis_client: Redis client for caching.
            stigmergic_subscriber: Optional subscriber for stigmergic intelligence.
            stigmergic_publisher: Optional publisher for stigmergic intelligence.
        """
        super().__init__()
        self.cache = IntelligenceCache(redis_client)
        self._request_locks: Dict[str, asyncio.Lock] = {}
        self._lock_creation_lock = asyncio.Lock()
        self._stigmergic_subscriber = stigmergic_subscriber
        self._stigmergic_publisher = stigmergic_publisher
        
    async def query(self, service: str, version: str) -> List[IntelResult]:
        """Query sources with caching, stigmergic, and request coalescing.
        
        Query order: stigmergic → cache → sources
        
        Args:
            service: Service name.
            version: Version string.
            
        Returns:
            List of unique, prioritized intelligence results.
        """
        # 1. Check stigmergic layer first (fastest path, real-time swarm sharing)
        if self._stigmergic_subscriber:
            stigmergic_results = self._stigmergic_subscriber.get(service, version)
            if stigmergic_results is not None:
                log.info("intelligence_stigmergic_hit", service=service, version=version)
                return stigmergic_results
        
        # Request Coalescing: Ensure only one query per service:version proceeds at a time
        key = f"{service}:{version}"
        
        async with self._lock_creation_lock:
            if key not in self._request_locks:
                self._request_locks[key] = asyncio.Lock()
            lock = self._request_locks[key]
        
        async with lock:
            # 2. Check Redis cache (persisted cache, 1 hour TTL)
            cached, cached_at = await self.cache.get_with_metadata(service, version)
            if cached is not None:
                return cached
            
            # Cache miss - query sources
            # Reimplement query logic to track failures directly
            log.info("aggregator_query_start_cached", service=service, version=version, 
                    source_count=len(self._sources))
            
            if not self._sources:
                log.warning("aggregator_no_sources")
                return []
            
            start_time = time.time()
            
            tasks = [
                self._query_source_with_timeout(source, service, version)
                for source in self._sources
            ]
            
            try:
                results_lists = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=self._max_total_time,
                )
            except asyncio.TimeoutError:
                log.warning("aggregator_total_timeout", max_total_time=self._max_total_time)
                results_lists = []
            
            all_results: List[IntelResult] = []
            failures = 0
            
            for i, result in enumerate(results_lists):
                if result is None:
                    failures += 1
                    continue

                if isinstance(result, list):
                    all_results.extend(result)
            
            # Offline Fallback Logic
            if not all_results and failures > 0 and failures == len(self._sources):
                 # All allowed sources failed
                 stale_results, stale_cached_at = await self._get_stale_cache(service, version)
                 if stale_results is not None:
                     log.warning("intelligence_offline_mode_active", 
                                service=service, version=version,
                                message="Intelligence sources unavailable, using cached data")
                     return self._mark_as_stale(stale_results, stale_cached_at)
                 else:
                     log.warning("intelligence_offline_mode_empty",
                                service=service, version=version)
                     # Return empty list, but maybe we should return it with metadata indicating offline?
                     # The story says "Return empty result with offline: true".
                     # I can't wrap empty list with metadata. 
                     # Wait, AC 3 says: "returns empty result with offline: true"? 
                     # IntelResult is an object. A list is a list.
                     # Option C in Phase 0 said: "Return empty list with metadata (logging only)".
                     # So returning `[]` is correct. The logging handles the event.
                     return []

            # Deduplicate and sort
            deduplicated = self._deduplicate_results(all_results)
            sorted_results = sorted(
                deduplicated, 
                key=lambda r: (r.priority, -r.confidence)
            )
            
            # Cache results (fresh)
            if sorted_results:
                await self.cache.set(service, version, sorted_results)
                # 3. Publish to stigmergic layer for swarm sharing
                if self._stigmergic_publisher:
                    try:
                        await self._stigmergic_publisher.publish(
                            service, version, sorted_results
                        )
                        log.info(
                            "intelligence_stigmergic_published",
                            service=service,
                            version=version,
                            count=len(sorted_results),
                        )
                    except Exception as e:
                        # Non-blocking - stigmergic failures shouldn't break agent operation
                        log.warning(
                            "intelligence_stigmergic_publish_failed",
                            service=service,
                            version=version,
                            error=str(e),
                        )
            elif failures == 0:
                 # Valid empty result (no hits)
                 # Cache it (negative caching)
                 await self.cache.set(service, version, sorted_results)
            
            # If partial failure (some sources failed, some success or valid empty), we cache what we have
            # Wait, if failure > 0 but not all failed? "Normal behavior applies".
            
            duration = time.time() - start_time
            log.info("aggregator_query_complete_cached", 
                     result_count=len(sorted_results),
                     source_count=len(self._sources),
                     duration_ms=round(duration * 1000, 2))
            
            return sorted_results

    async def _get_stale_cache(self, service: str, version: str) -> Tuple[Optional[List[IntelResult]], Optional[str]]:
        """Get cached data ignoring TTL implications (handled by returning whatever get_with_metadata finds).
        
        Args:
            service: Service name.
            version: Version string.
            
        Returns:
            Tuple of (results, timestamp) or (None, None).
        """
        # Retrieve from persistent archive
        return await self.cache.get_with_metadata(service, version, use_archive=True)

    def _mark_as_stale(self, results: List[IntelResult], cached_at: Optional[str]) -> List[IntelResult]:
        """Mark all results as stale with cache timestamp.
        
        Args:
            results: List of results to mark.
            cached_at: Timestamp string.
            
        Returns:
            New list of IntelResults with updated metadata.
        """
        stale_results = []
        for r in results:
            # Create copy of metadata
            metadata = r.metadata.copy()
            metadata["stale"] = True
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

    async def health_check(self) -> Dict[str, Any]:
        """Check health with offline tolerance.
        
        Returns:
            Dict with health status. Offline sources don't fail the check if cache is up.
        """
        # 1. Check Redis first
        cache_health = {"healthy": False}
        try:
             # Access internal redis client
             if await self.cache._redis.ping():
                 cache_health = {"healthy": True} 
        except Exception as e:
             cache_health = {"healthy": False, "error": str(e)}

        # 2. Check sources
        source_result = await super().health_check()
        
        # 3. Determine overall status
        overall_healthy = source_result["healthy"]
        status_msg = "healthy"
        
        if cache_health["healthy"]:
            if not overall_healthy:
                overall_healthy = True
                status_msg = "degraded"
        
        if not overall_healthy and not cache_health["healthy"]:
            status_msg = "unhealthy"

        return {
            "healthy": overall_healthy,
            "status": status_msg,
            "cache": cache_health,
            "sources": source_result["sources"]
        }
