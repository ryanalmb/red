"""Unit tests for offline intelligence mode."""
import pytest
from datetime import datetime
from typing import List
from cyberred.intelligence.base import IntelResult, IntelPriority, IntelligenceSource

@pytest.mark.unit
def test_intel_result_stale_metadata():
    """Test that IntelResult supports 'stale' metadata."""
    result = IntelResult(
        source="test",
        cve_id="CVE-2021-1234",
        severity="high",
        exploit_available=False,
        exploit_path=None,
        confidence=0.8,
        priority=IntelPriority.NVD_HIGH,
        metadata={"stale": True}
    )
    assert result.metadata["stale"] is True

@pytest.mark.unit
def test_intel_result_offline_metadata():
    """Test that IntelResult supports 'offline' metadata."""
    result = IntelResult(
        source="test",
        cve_id="CVE-2021-1234",
        severity="high",
        exploit_available=False,
        exploit_path=None,
        confidence=0.8,
        priority=IntelPriority.NVD_HIGH,
        metadata={"offline": True}
    )
    assert result.metadata["offline"] is True

@pytest.mark.unit
def test_intel_result_cached_at_metadata():
    """Test that IntelResult supports 'cached_at' metadata."""
    timestamp = datetime.utcnow().isoformat()
    result = IntelResult(
        source="test",
        cve_id="CVE-2021-1234",
        severity="high",
        exploit_available=False,
        exploit_path=None,
        confidence=0.8,
        priority=IntelPriority.NVD_HIGH,
        metadata={"cached_at": timestamp}
    )
    assert result.metadata["cached_at"] == timestamp

from unittest.mock import AsyncMock, MagicMock
from cyberred.intelligence.aggregator import CachedIntelligenceAggregator, IntelligenceAggregator

class MockSource(IntelligenceSource):
    def __init__(self, name="mock"):
        super().__init__(name)
        self.should_fail = False

    async def query(self, service: str, version: str) -> List[IntelResult]:
        if self.should_fail:
            raise Exception("Timeout")
        return []

    async def health_check(self) -> bool:
        return True

@pytest.mark.asyncio
@pytest.mark.unit
async def test_offline_fallback_success():
    """Test fallback to stale cache when all sources fail."""
    mock_redis = AsyncMock()
    # We need to mock RedisClient methods used by IntelligenceCache in __init__?
    # No, IntelligenceCache stores redis instance.
    
    aggregator = CachedIntelligenceAggregator(mock_redis)
    # Replace internal cache with mock
    aggregator.cache = AsyncMock()
    
    # Mock source to fail
    source = MockSource("mock_source")
    source.should_fail = True
    aggregator.add_source(source)
    
    # Cache behavior: Fresh miss, Stale hit
    stale_result = IntelResult(
        source="stale_source",
        cve_id="CVE-TEST",
        severity="high",
        exploit_available=False,
        exploit_path=None,
        confidence=0.8,
        priority=IntelPriority.NVD_HIGH,
        metadata={}
    )
    # Mocking get for current implementation, and get_with_metadata for future implementation
    aggregator.cache.get.return_value = None 
    aggregator.cache.get_with_metadata.side_effect = [
        (None, None), # Fresh miss
        ([stale_result], "2023-01-01T00:00:00Z") # Stale hit
    ]
    
    results = await aggregator.query("Apache", "2.4.49")
    
    assert len(results) == 1
    assert results[0].metadata.get("stale") is True
    assert results[0].metadata.get("cached_at") == "2023-01-01T00:00:00Z"

@pytest.mark.asyncio
@pytest.mark.unit
async def test_offline_fallback_empty():
    """Test empty return when sources fail and no cache."""
    mock_redis = AsyncMock()
    aggregator = CachedIntelligenceAggregator(mock_redis)
    aggregator.cache = AsyncMock()
    
    source = MockSource("mock_source")
    source.should_fail = True
    aggregator.add_source(source)
    
    # Cache behavior: Fresh miss
    aggregator.cache.get.return_value = None
    aggregator.cache.get_with_metadata.return_value = (None, None)
    
    results = await aggregator.query("Apache", "2.4.49")
    
    assert results == []

@pytest.mark.asyncio
@pytest.mark.unit
async def test_health_check_offline_degraded():
    """Test health check confirms degraded status when sources down."""
    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True
    aggregator = CachedIntelligenceAggregator(mock_redis)
    # Mock internal redis ping check if implemented
    # Currently IntelligenceCache doesn't expose health check, but we access aggregator.cache._redis
    
    source = MockSource("fail_source")
    # Mock health_check to fail
    # Since MockSource.health_check is async, we assign a new AsyncMock
    source.health_check = AsyncMock(side_effect=Exception("Down"))
    aggregator.add_source(source)
    
    status = await aggregator.health_check()
    
    assert status["healthy"] is True
    assert status.get("status") == "degraded"
    assert status["sources"]["fail_source"]["healthy"] is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cached_aggregator_no_sources():
    """Test CachedIntelligenceAggregator returns empty when no sources configured."""
    mock_redis = AsyncMock()
    aggregator = CachedIntelligenceAggregator(mock_redis)
    aggregator.cache = AsyncMock()
    aggregator.cache.get_with_metadata = AsyncMock(return_value=(None, None))
    
    # No sources added
    results = await aggregator.query("Apache", "2.4.49")
    
    assert results == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cached_aggregator_partial_success():
    """Test CachedIntelligenceAggregator caches results when some sources fail."""
    mock_redis = AsyncMock()
    aggregator = CachedIntelligenceAggregator(mock_redis)
    aggregator.cache = AsyncMock()
    aggregator.cache.get_with_metadata = AsyncMock(return_value=(None, None))
    aggregator.cache.set = AsyncMock(return_value=True)
    
    # Create a source that returns actual results
    class SuccessSource(IntelligenceSource):
        def __init__(self):
            super().__init__("success_source")
        
        async def query(self, service: str, version: str):
            return [IntelResult(
                source="success_source", cve_id="CVE-PARTIAL", severity="high",
                exploit_available=True, exploit_path=None, confidence=0.9, 
                priority=IntelPriority.NVD_HIGH, metadata={}
            )]
        
        async def health_check(self):
            return True
    
    good_source = SuccessSource()
    
    bad_source = MockSource("bad_source")
    bad_source.should_fail = True
    
    aggregator.add_source(good_source)
    aggregator.add_source(bad_source)
    
    results = await aggregator.query("Apache", "2.4.49")
    
    # Should get results from successful source
    assert len(results) == 1
    assert results[0].cve_id == "CVE-PARTIAL"
    # Cache.set should be called with partial results
    aggregator.cache.set.assert_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cached_aggregator_valid_empty_result():
    """Test that valid empty results (no hits) are cached."""
    mock_redis = AsyncMock()
    aggregator = CachedIntelligenceAggregator(mock_redis)
    aggregator.cache = AsyncMock()
    aggregator.cache.get_with_metadata = AsyncMock(return_value=(None, None))
    aggregator.cache.set = AsyncMock(return_value=True)
    
    # Source returns empty (no CVEs found - valid result)
    source = MockSource("empty_source")
    source.should_fail = False  # Successful query, just no results
    aggregator.add_source(source)
    
    results = await aggregator.query("UnknownService", "1.0")
    
    assert results == []
    # Valid empty results should be cached (negative caching)
    aggregator.cache.set.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_health_check_all_down():
    """Test health check when both sources AND cache are down."""
    mock_redis = AsyncMock()
    mock_redis.ping.side_effect = Exception("Redis down")
    
    aggregator = CachedIntelligenceAggregator(mock_redis)
    
    source = MockSource("down_source")
    source.health_check = AsyncMock(side_effect=Exception("Source down"))
    aggregator.add_source(source)
    
    status = await aggregator.health_check()
    
    assert status["healthy"] is False
    assert status.get("status") == "unhealthy"
    assert status["cache"]["healthy"] is False
    assert status["sources"]["down_source"]["healthy"] is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_mark_as_stale_preserves_original_metadata():
    """Test _mark_as_stale preserves existing metadata while adding stale flag."""
    mock_redis = AsyncMock()
    aggregator = CachedIntelligenceAggregator(mock_redis)
    
    original = IntelResult(
        source="test",
        cve_id="CVE-2021-1234",
        severity="high",
        exploit_available=False,
        exploit_path=None,
        confidence=0.8,
        priority=IntelPriority.NVD_HIGH,
        metadata={"original_key": "original_value", "cvss": 9.8}
    )
    
    stale_results = aggregator._mark_as_stale([original], "2023-01-01T00:00:00Z")
    
    assert len(stale_results) == 1
    assert stale_results[0].metadata["stale"] is True
    assert stale_results[0].metadata["cached_at"] == "2023-01-01T00:00:00Z"
    # Original metadata preserved
    assert stale_results[0].metadata["original_key"] == "original_value"
    assert stale_results[0].metadata["cvss"] == 9.8


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cached_aggregator_total_timeout():
    """Test CachedIntelligenceAggregator handles total timeout gracefully."""
    import asyncio
    
    mock_redis = AsyncMock()
    aggregator = CachedIntelligenceAggregator(mock_redis)
    aggregator._max_total_time = 0.01  # Very short timeout (10ms)
    aggregator.cache = AsyncMock()
    aggregator.cache.get_with_metadata = AsyncMock(return_value=(None, None))
    aggregator.cache.set = AsyncMock(return_value=True)
    
    # Create a very slow source that will exceed the total timeout
    class VerySlowSource(IntelligenceSource):
        def __init__(self):
            super().__init__("very_slow_source")
        
        async def query(self, service: str, version: str):
            await asyncio.sleep(1.0)  # Much longer than total timeout
            return [IntelResult(
                source="slow", cve_id="CVE-SLOW", severity="high",
                exploit_available=False, exploit_path=None, confidence=1.0,
                priority=IntelPriority.NVD_HIGH, metadata={}
            )]
        
        async def health_check(self):
            return True
    
    aggregator.add_source(VerySlowSource())
    
    results = await aggregator.query("Apache", "2.4.49")
    
    # When total timeout occurs, results_lists becomes [] and no failures counted
    # So the code returns [] (empty) rather than hitting fallback path
    assert results == []


