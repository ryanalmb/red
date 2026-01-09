"""Redis-backed intelligence cache."""

import structlog
from typing import Optional, List, Tuple
import json
from dataclasses import asdict
from datetime import datetime

from cyberred.storage.redis_client import RedisClient
from cyberred.intelligence.base import IntelResult

log = structlog.get_logger()

class IntelligenceCache:
    """Redis-backed intelligence query cache.
    
    Caches intelligence query results to reduce API load and
    improve response times for repeated queries.
    
    Attributes:
        redis: RedisClient instance for cache storage.
        ttl: Cache entry time-to-live in seconds (default 3600).
        key_prefix: Prefix for all cache keys (default "intel:").
    
    Architecture Reference:
        From architecture.md (lines 506-522):
        intelligence:
          cache_ttl: 3600          # Redis cache TTL (1 hour)
          source_timeout: 5        # Per-source query timeout (seconds)
    
    Key Format:
        intel:{hash(service:version)} or intel:{service}:{version}
    """
    
    def __init__(
        self,
        redis: RedisClient,
        ttl: int = 3600,
        key_prefix: str = "intel:",
    ) -> None:
        """Initialize the cache.
        
        Args:
            redis: RedisClient instance for storage.
            ttl: Cache TTL in seconds (default 3600 = 1 hour).
            key_prefix: Prefix for cache keys (default "intel:").
        """
        self._redis = redis
        self._ttl = ttl
        self._key_prefix = key_prefix
    
    def _make_key(self, service: str, version: str) -> str:
        """Generate cache key for service/version.
        
        Key format: {prefix}{service_norm}:{version_norm}
        
        Args:
            service: Service name.
            version: Version string.
            
        Returns:
            Redis cache key string.
        """
        # Normalize: lowercase, replace spaces/colons with underscores
        service_norm = service.lower().replace(" ", "_").replace(":", "_")
        version_norm = version.replace(" ", "_").replace(":", "_") if version else "unknown"
        return f"{self._key_prefix}{service_norm}:{version_norm}"

    def _make_archive_key(self, service: str, version: str) -> str:
        """Generate archive cache key (no TTL).
        
        Key format: {prefix}archive:{service_norm}:{version_norm}
        """
        service_norm = service.lower().replace(" ", "_").replace(":", "_")
        version_norm = version.replace(" ", "_").replace(":", "_") if version else "unknown"
        return f"{self._key_prefix}archive:{service_norm}:{version_norm}"

    async def get(self, service: str, version: str) -> Optional[List[IntelResult]]:
        """Get cached intelligence results.
        
        Args:
            service: Service name.
            version: Version string.
            
        Returns:
            List of IntelResult if cache hit, None on miss or error.
        """
        results, _ = await self.get_with_metadata(service, version)
        return results

    async def get_with_metadata(
        self, 
        service: str, 
        version: str,
        use_archive: bool = False
    ) -> Tuple[Optional[List[IntelResult]], Optional[str]]:
        """Get cached results with cache timestamp.
        
        Args:
            service: Service name.
            version: Version string.
            use_archive: If True, check the persistent archive (stale data).
            
        Returns:
            Tuple of (results, cached_at) where cached_at is ISO timestamp or None.
        """
        if use_archive:
            key = self._make_archive_key(service, version)
        else:
            key = self._make_key(service, version)
        
        try:
            data = await self._redis.get(key)
            if data is None:
                # Only log miss for main cache to reduce noise
                if not use_archive:
                    log.debug("cache_miss", service=service, version=version, key=key)
                return None, None
            
            # Deserialize JSON
            try:
                cache_entry = json.loads(data)
            except json.JSONDecodeError as e:
                log.warning("cache_corrupt", key=key, error=str(e))
                await self._delete_key(key)
                return None, None
            
            # Handle legacy format (list of results without wrapper)
            if isinstance(cache_entry, list):
                results = [IntelResult.from_json(r) for r in cache_entry]
                if not use_archive:
                    log.debug("cache_hit_legacy", service=service, version=version, 
                             result_count=len(results))
                return results, None
            
            # Handle new format (dict with results and cached_at)
            results_data = cache_entry.get("results", [])
            results = [IntelResult.from_json(r) for r in results_data]
            cached_at = cache_entry.get("cached_at")
            
            if not use_archive:
                log.debug("cache_hit", service=service, version=version, 
                         result_count=len(results))
            return results, cached_at
            
        except Exception as e:
            log.warning("cache_get_error", key=key, error=str(e))
            return None, None

    async def _delete_key(self, key: str) -> int:
        """Delete a specific cache key.
        
        Args:
            key: Redis key to delete.
            
        Returns:
            Number of keys deleted.
        """
        try:
            return await self._redis.delete(key)
        except Exception:
            # Errors during delete are swallowed to prevent feedback loops
            return 0

    async def set(
        self, 
        service: str, 
        version: str, 
        results: List[IntelResult],
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache intelligence results.
        
        Args:
            service: Service name.
            version: Version string.
            results: List of IntelResult objects to cache.
            ttl: Optional TTL override in seconds.
            
        Returns:
            True if set successfully, False on error.
        """
        key = self._make_key(service, version)
        expiry = ttl if ttl is not None else self._ttl
        
        try:
            # Serialize List[IntelResult] to JSON with wrapper and timestamp
            cache_entry = {
                "results": [asdict(r) for r in results],
                "cached_at": datetime.utcnow().isoformat() + "Z",
            }
            json_data = json.dumps(cache_entry)
            
            # Store in Redis with TTL
            await self._redis.setex(key, expiry, json_data)
            
            # Store in Archive (no TTL) for offline fallback
            archive_key = self._make_archive_key(service, version)
            await self._redis.set(archive_key, json_data)
            
            count = len(results)
            log_event = "cache_set" if count > 0 else "cache_set_empty"
            log.debug(log_event, service=service, version=version, 
                     count=count, ttl=expiry)
            return True
            
        except Exception as e:
            log.warning("cache_set_error", key=key, error=str(e))
            return False

    async def invalidate(self, service: str, version: str) -> int:
        """Invalidate a specific cache entry.
        
        Args:
            service: Service name.
            version: Version string.
            
        Returns:
            Number of keys deleted (0 or 1).
        """
        key = self._make_key(service, version)
        log.info("cache_invalidate", service=service, version=version, key=key)
        return await self._delete_key(key)

    async def invalidate_all(self, pattern: str = None) -> int:
        """Invalidate all cached intelligence.
        
        Args:
            pattern: Optional glob pattern suffix (default: "*").
                     The key prefix is always prepended.
            
        Returns:
            Number of keys deleted.
        """
        suffix = pattern if pattern else "*"
        search_pattern = f"{self._key_prefix}{suffix}"
        
        try:
            keys = await self._redis.keys(search_pattern)
            if not keys:
                return 0
                
            count = await self._redis.delete(*keys)
            log.info("cache_invalidate_all", pattern=search_pattern, count=count)
            return count
        except Exception as e:
            log.warning("cache_invalidate_all_error", error=str(e))
            return 0
