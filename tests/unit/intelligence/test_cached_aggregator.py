import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cyberred.intelligence.aggregator import IntelligenceAggregator, CachedIntelligenceAggregator
from cyberred.intelligence.cache import IntelligenceCache
from cyberred.intelligence.base import IntelResult
from cyberred.storage.redis_client import RedisClient

@pytest.fixture
def mock_redis():
    return AsyncMock(spec=RedisClient)

@pytest.fixture
def mock_cache(mock_redis):
    cache = MagicMock(spec=IntelligenceCache)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    return cache

@pytest.fixture
def aggregator(mock_redis):
    # We need to mock the cache creation inside CachedIntelligenceAggregator or pass it in.
    # The requirement usually implies composition or inheritance.
    # Let's assume constructor changes or we patch it.
    with patch("cyberred.intelligence.aggregator.IntelligenceCache") as MockCacheClass:
        mock_cache_instance = MockCacheClass.return_value
        mock_cache_instance.get = AsyncMock(return_value=None)
        mock_cache_instance.set = AsyncMock(return_value=True)
        agg = CachedIntelligenceAggregator(redis_client=mock_redis)
        agg.cache = mock_cache_instance # Ensure our mock is used if not already
        return agg

@pytest.mark.asyncio
async def test_inheritance():
    """Test that CachedIntelligenceAggregator inherits from IntelligenceAggregator."""
    assert issubclass(CachedIntelligenceAggregator, IntelligenceAggregator)

@pytest.mark.asyncio
async def test_init(mock_redis):
    """Test initialization creates cache."""
    with patch("cyberred.intelligence.aggregator.IntelligenceCache") as MockCacheClass:
        agg = CachedIntelligenceAggregator(mock_redis)
        MockCacheClass.assert_called_once_with(mock_redis)
        assert agg.cache == MockCacheClass.return_value

@pytest.mark.asyncio
@pytest.mark.unit
async def test_query_cache_hit(mock_redis):
    """Test query returns cached result if available."""
    cached_results = [IntelResult(source="cache", cve_id="CVE-HIT", severity="high", priority=1, confidence=1.0, exploit_available=True, exploit_path=None)]
    
    with patch("cyberred.intelligence.aggregator.IntelligenceCache") as MockCacheClass:
        agg = CachedIntelligenceAggregator(mock_redis)
        # Mock get_with_metadata to return (results, cached_at) tuple
        agg.cache.get_with_metadata = AsyncMock(return_value=(cached_results, "2024-01-01T00:00:00Z"))
        
        results = await agg.query("Apache", "2.4.49")
        
        agg.cache.get_with_metadata.assert_called_with("Apache", "2.4.49")
        assert results == cached_results

@pytest.mark.asyncio
@pytest.mark.unit
async def test_query_cache_miss(mock_redis):
    """Test query fetches from sources and caches result on miss."""
    from cyberred.intelligence.base import IntelligenceSource
    
    class MockSource(IntelligenceSource):
        def __init__(self):
            super().__init__("mock_source")
        
        async def query(self, service: str, version: str):
            return [IntelResult(source="mock_source", cve_id="CVE-MISS", severity="high", 
                               priority=1, confidence=1.0, exploit_available=True, exploit_path=None)]
        
        async def health_check(self):
            return True
    
    with patch("cyberred.intelligence.aggregator.IntelligenceCache") as MockCacheClass:
        agg = CachedIntelligenceAggregator(mock_redis)
        # Mock get_with_metadata to return cache miss (None, None)
        agg.cache.get_with_metadata = AsyncMock(return_value=(None, None))
        agg.cache.set = AsyncMock(return_value=True)
        
        # Add a real mock source
        agg.add_source(MockSource())
        
        results = await agg.query("Apache", "2.4.49")
        
        agg.cache.get_with_metadata.assert_called_with("Apache", "2.4.49")
        assert len(results) == 1
        assert results[0].cve_id == "CVE-MISS"
        # Verify cache.set was called with the results
        agg.cache.set.assert_called()

@pytest.mark.asyncio
@pytest.mark.unit
async def test_request_coalescing(mock_redis):
    """Test that multiple concurrent requests for same key result in single downstream query."""
    import asyncio
    from cyberred.intelligence.base import IntelligenceSource
    
    query_count = 0
    
    class SlowMockSource(IntelligenceSource):
        def __init__(self):
            super().__init__("slow_source")
        
        async def query(self, service: str, version: str):
            nonlocal query_count
            query_count += 1
            await asyncio.sleep(0.1)
            return [IntelResult(source="slow", cve_id="CVE-SLOW", severity="high", 
                               priority=1, confidence=1.0, exploit_available=True, exploit_path=None)]
        
        async def health_check(self):
            return True
    
    with patch("cyberred.intelligence.aggregator.IntelligenceCache") as MockCacheClass:
        agg = CachedIntelligenceAggregator(mock_redis)
        
        # Stateful mock for cache to simulate real behavior
        cache_storage = {}
        async def mock_get_with_metadata(s, v, use_archive=False):
            key = f"{s}:{v}"
            if key in cache_storage:
                return (cache_storage[key], "2024-01-01T00:00:00Z")
            return (None, None)
        
        async def mock_set(s, v, val, ttl=None):
            cache_storage[f"{s}:{v}"] = val
            return True
        
        agg.cache.get_with_metadata = AsyncMock(side_effect=mock_get_with_metadata)
        agg.cache.set = AsyncMock(side_effect=mock_set)
        
        agg.add_source(SlowMockSource())
        
        # Run two queries concurrently
        t1 = asyncio.create_task(agg.query("Apache", "2.4.49"))
        t2 = asyncio.create_task(agg.query("Apache", "2.4.49"))
        
        r1, r2 = await asyncio.gather(t1, t2)
        
        # Both should return result
        assert r1 == r2
        assert len(r1) == 1
        
        # Source query should be called ONLY ONCE due to coalescing lock
        assert query_count == 1
