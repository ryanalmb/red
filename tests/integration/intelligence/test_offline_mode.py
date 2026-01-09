import pytest
import asyncio
from cyberred.intelligence import CachedIntelligenceAggregator, IntelResult, IntelligenceSource
from cyberred.storage.redis_client import RedisClient
from cyberred.core.config import RedisConfig

# Enable the plugin if not automatically discovered, though usually pytest finds `pytest_plugins` in root conftest or by name. 
# But let's importing explicitly might be needed if it's not in conftest path.
# test_cache_integration.py uses: pytest_plugins = ["tests.fixtures.redis_container"]
pytest_plugins = ["tests.fixtures.redis_container"]

class MockDelaySource(IntelligenceSource):
    def __init__(self, name="delay", delay=0.1, fail=False):
        # Pass logger=None or check base init signature. Base just takes name usually
        super().__init__(name)
        self.delay = delay
        self.fail = fail

    async def query(self, service: str, version: str):
        await asyncio.sleep(self.delay)
        if self.fail:
            raise Exception("Source failure")
        # Metadata logic: ensure we return some
        return [IntelResult(
            source=self.name, 
            cve_id="CVE-MOCK",
            severity="low",
            exploit_available=False,
            exploit_path=None,
            confidence=1.0, 
            priority=1, 
            metadata={}
        )]
        
    async def health_check(self):
        if self.fail:
            raise Exception("Unhealthy")
        return True

@pytest.mark.integration
@pytest.mark.asyncio
async def test_offline_mode_integration(redis_container):
    """Integration test with real Redis container."""
    
    host = redis_container.get_container_host_ip()
    port = int(redis_container.get_exposed_port(6379))
    
    # We need to construct RedisClient with config matching these
    config = RedisConfig(host=host, port=port)
    client = RedisClient(config, engagement_id="integration-offline")
    await client.connect()
    
    aggregator = CachedIntelligenceAggregator(client)
    
    # 1. Fresh Query
    source = MockDelaySource("test_source", delay=0.1)
    aggregator.add_source(source)
    
    results = await aggregator.query("apache", "2.4.49")
    assert len(results) == 1
    assert results[0].metadata.get("stale") is None
    
    # Verify it is in cache (main)
    cached, _ = await aggregator.cache.get_with_metadata("apache", "2.4.49")
    assert cached is not None
    assert len(cached) == 1
    
    # Verify it is in archive
    cached_archive, _ = await aggregator.cache.get_with_metadata("apache", "2.4.49", use_archive=True)
    assert len(cached_archive) == 1
    
    # 2. Offline Fallback
    # Force source failure
    source.fail = True
    
    # Simulate TTL expiration of main cache by deleting key
    # Key format: intel:apache:2.4.49
    # aggregator.cache._make_key("apache", "2.4.49") -> "intel:apache:2.4.49"
    main_key = "intel:apache:2.4.49"
    await client.delete(main_key)
    
    # Verify main cache is gone
    assert await client.exists(main_key) == 0
    
    # Verify archive is still there
    archive_key = "intel:archive:apache:2.4.49"
    assert await client.exists(archive_key) == 1
    
    # Now query. Should fail source, miss main cache, hit archive.
    results_offline = await aggregator.query("apache", "2.4.49")
    
    assert len(results_offline) == 1
    assert results_offline[0].metadata.get("stale") is True
    assert results_offline[0].metadata.get("cached_at") is not None
    
    # Cleanup
    await client.close()
