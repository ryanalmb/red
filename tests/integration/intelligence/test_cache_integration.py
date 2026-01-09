import pytest
import json
import asyncio
from cyberred.core.config import RedisConfig
from cyberred.storage.redis_client import RedisClient
from cyberred.intelligence.cache import IntelligenceCache
from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
from cyberred.intelligence.base import IntelResult, IntelPriority, IntelligenceSource
from typing import List, Dict, Any

# Import fixture
pytest_plugins = ["tests.fixtures.redis_container"]

@pytest.mark.integration
class TestCacheIntegration:
    """Integration tests for IntelligenceCache with real Redis."""
    
    @pytest.fixture
    async def redis_client(self, redis_container):
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        config = RedisConfig(host=host, port=port)
        client = RedisClient(config, engagement_id="integration-test")
        await client.connect()
        
        # Clean up keys used in tests
        keys = await client.keys("intel:test:*")
        if keys:
            await client.delete(*keys)
            
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_cache_set_get_roundtrip(self, redis_client):
        """Test full set/get roundtrip with real Redis."""
        cache = IntelligenceCache(redis_client, key_prefix="intel:test:")
        
        result = IntelResult(
            source="test_src",
            cve_id="CVE-2023-1234",
            severity="critical",
            exploit_available=True,
            exploit_path=None,
            priority=1,
            confidence=0.9,
            metadata={"foo": "bar"}
        )
        
        # Set
        success = await cache.set("TestService", "1.0", [result])
        assert success is True
        
        # Verify in Redis directly (raw check)
        # Note: key is lowercase
        raw_key = "intel:test:testservice:1.0"
        raw_val = await redis_client.get(raw_key)
        assert raw_val is not None
        
        # Get via Cache
        cached_results = await cache.get("TestService", "1.0")
        assert cached_results is not None
        assert len(cached_results) == 1
        assert cached_results[0].cve_id == "CVE-2023-1234"
        assert cached_results[0].metadata["foo"] == "bar"

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, redis_client):
        """Test invalidation with real Redis."""
        cache = IntelligenceCache(redis_client, key_prefix="intel:test:")
        
        # Populate
        await cache.set("ServiceA", "1.0", [])
        await cache.set("ServiceB", "1.0", [])
        
        # Invalidate specific
        count = await cache.invalidate("ServiceA", "1.0")
        assert count == 1
        assert await cache.get("ServiceA", "1.0") is None
        assert await cache.get("ServiceB", "1.0") is not None
        
        # Invalidate all
        # Note: invalidate_all uses prefix. Default suffix "*" -> "intel:test:*"
        count = await cache.invalidate_all()
        assert count >= 1 # ServiceB is there
        assert await cache.get("ServiceB", "1.0") is None

    @pytest.mark.asyncio
    async def test_concurrent_access(self, redis_client):
        """Test concurrent access to same key."""
        cache = IntelligenceCache(redis_client, key_prefix="intel:test:")
        
        # 50 concurrent writes
        writes = [
            cache.set("Concurrent", "1.0", [])
            for _ in range(50)
        ]
        results = await asyncio.gather(*writes)
        assert all(results)
        
        # Read
        val = await cache.get("Concurrent", "1.0")
        assert val == []

@pytest.mark.integration
class TestCacheSentinelIntegration:
    """Integration tests for IntelligenceCache with real Redis Sentinel cluster.
    
    Requires docker-compose-redis-sentinel.yaml cluster running.
    """
    
    @pytest.fixture
    def sentinel_config(self) -> RedisConfig:
        """Provide config for Sentinel cluster."""
        return RedisConfig(
            host="localhost",
            port=6379,
            sentinel_hosts=["localhost:26379", "localhost:26380", "localhost:26381"],
            master_name="mymaster",
        )

    @pytest.fixture
    async def redis_client(self, sentinel_config):
        client = RedisClient(sentinel_config, engagement_id="integration-test-sentinel")
        await client.connect()
        
        # Clean up keys used in tests
        keys = await client.keys("intel:sentinel:*")
        if keys:
            await client.delete(*keys)
            
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_sentinel_cache_operations(self, redis_client):
        """Test cache operations against Sentinel backing."""
        cache = IntelligenceCache(redis_client, key_prefix="intel:sentinel:")
        
        result = IntelResult(
            source="sentinel_src",
            cve_id="CVE-SENTINEL",
            severity="high",
            exploit_available=False,
            exploit_path=None,
            priority=3,
            confidence=1.0, 
            metadata={}
        )
        
        # Set
        assert await cache.set("SentinelApp", "1.0", [result]) is True
        
        # Get
        cached = await cache.get("SentinelApp", "1.0")
        assert cached is not None
        assert len(cached) == 1
        assert cached[0].cve_id == "CVE-SENTINEL"
        
        # Invalidate
        deleted = await cache.invalidate("SentinelApp", "1.0")
        assert deleted == 1
        assert await cache.get("SentinelApp", "1.0") is None

class MockSource(IntelligenceSource):
    def __init__(self, name: str, results: List[IntelResult]):
        self._name = name
        self._results = results
        self.call_count = 0
        
    @property
    def name(self) -> str:
        return self._name
        
    async def query(self, service: str, version: str) -> List[IntelResult]:
        self.call_count += 1
        return self._results
        
    async def health_check(self) -> bool:
        return True

@pytest.mark.integration
class TestCachedAggregatorIntegration:
    """Integration tests for CachedIntelligenceAggregator with real Redis."""
    
    @pytest.fixture
    async def redis_client(self, redis_container):
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        config = RedisConfig(host=host, port=port)
        client = RedisClient(config, engagement_id="integration-test-agg")
        await client.connect()
        keys = await client.keys("intel:cache_agg:*")
        if keys:
            await client.delete(*keys)
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_aggregator_cache_flow(self, redis_client):
        """Test full aggregator flow: Miss -> Source -> Set Cache -> Hit."""
        # Setup
        aggregator = CachedIntelligenceAggregator(redis_client)
        aggregator.cache._key_prefix = "intel:cache_agg:" # Use distinct prefix
        
        result = IntelResult(
             source="mock_src", cve_id="CVE-2024-0001", severity="high",
             exploit_available=True, exploit_path=None, priority=1, confidence=1.0, metadata={}
        )
        source = MockSource("mock_src", [result])
        aggregator.add_source(source)
        
        # 1. First Query (Cache Miss)
        res1 = await aggregator.query("ServiceX", "1.0")
        assert len(res1) == 1
        assert res1[0].cve_id == "CVE-2024-0001"
        assert source.call_count == 1
        
        # 2. Check Redis directly (Verify it was cached)
        cache_key = "intel:cache_agg:servicex:1.0"
        assert await redis_client.exists(cache_key)
        
        # 3. Second Query (Cache Hit)
        # Verify source NOT called again
        res2 = await aggregator.query("ServiceX", "1.0")
        assert len(res2) == 1
        assert res2[0].cve_id == "CVE-2024-0001"
        assert source.call_count == 1  # Still 1
