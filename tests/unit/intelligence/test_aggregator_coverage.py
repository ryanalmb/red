import pytest
from unittest.mock import Mock, AsyncMock
from cyberred.intelligence.base import IntelligenceSource, IntelResult
from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
from cyberred.intelligence.stigmergic import StigmergicIntelligenceSubscriber, StigmergicIntelligencePublisher
from cyberred.storage.redis_client import RedisClient

@pytest.mark.unit
class TestAggregatorCoverage:
    
    @pytest.mark.asyncio
    async def test_stigmergic_hit(self):
        """Test returning results directly from stigmergic layer."""
        mock_redis = AsyncMock()
        mock_sub = Mock(spec=StigmergicIntelligenceSubscriber)
        mock_sub.get.return_value = [IntelResult(
            source="stigmergic", cve_id="CVE-2023-1", severity="critical",
            confidence=1.0, priority=1, exploit_available=True, exploit_path=None, metadata={}
        )]
        
        aggregator = CachedIntelligenceAggregator(
            redis_client=mock_redis,
            stigmergic_subscriber=mock_sub
        )
        
        results = await aggregator.query("svc", "1.0")
        assert len(results) == 1
        assert results[0].source == "stigmergic"
        mock_sub.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_stigmergic_publish_exception(self):
        """Test stigmergic publish exception is caught and logged."""
        mock_redis = AsyncMock()
        mock_pub = Mock(spec=StigmergicIntelligencePublisher)
        mock_pub.publish = AsyncMock(side_effect=Exception("Publish Error"))
        
        aggregator = CachedIntelligenceAggregator(
            redis_client=mock_redis,
            stigmergic_publisher=mock_pub
        )
        aggregator.cache = AsyncMock()
        aggregator.cache.get_with_metadata = AsyncMock(return_value=(None, None))
        aggregator.cache.set = AsyncMock()
        
        # Add source
        source = Mock(spec=IntelligenceSource)
        source.name = "src"
        source.query = AsyncMock(return_value=[IntelResult(
            source="src", cve_id="CVE-1", severity="low",
            confidence=1.0, priority=1, exploit_available=False, exploit_path=None, metadata={}
        )])
        aggregator.add_source(source)
        
        # Should not raise exception
        results = await aggregator.query("svc", "1.0")
        assert len(results) == 1
        mock_pub.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_valid_empty_result_caching(self):
        """Test failures==0 branch for caching empty results."""
        mock_redis = AsyncMock()
        aggregator = CachedIntelligenceAggregator(redis_client=mock_redis)
        aggregator.cache = AsyncMock()
        aggregator.cache.get_with_metadata = AsyncMock(return_value=(None, None))
        aggregator.cache.set = AsyncMock()
        
        source = Mock(spec=IntelligenceSource)
        source.name = "src"
        # Return empty list (valid result)
        source.query = AsyncMock(return_value=[])
        aggregator.add_source(source)
        
        results = await aggregator.query("svc", "1.0")
        assert results == []
        # Should call cache.set (negative caching)
        aggregator.cache.set.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_stale_mark_no_timestamp(self):
        """Test _mark_as_stale with None timestamp."""
        aggregator = CachedIntelligenceAggregator(AsyncMock())
        result = IntelResult(
            source="src", cve_id="CVE-1", severity="low",
            confidence=1.0, priority=1, exploit_available=False, exploit_path=None, metadata={}
        )
        stale = aggregator._mark_as_stale([result], None)
        assert stale[0].metadata["stale"] is True
        assert "cached_at" not in stale[0].metadata

    @pytest.mark.asyncio
    async def test_health_check_redis_ping_error(self):
        """Test health check when redis ping raises exception."""
        mock_redis = AsyncMock()
        aggregator = CachedIntelligenceAggregator(mock_redis)
        aggregator.cache = AsyncMock()
        # Ping raises exception (accessing _redis.ping)
        mock_redis_param = AsyncMock()
        mock_redis_param.ping.side_effect = Exception("Connection Error")
        aggregator.cache._redis = mock_redis_param
        
        res = await aggregator.health_check()
        assert res["cache"]["healthy"] is False
        assert "error" in res["cache"]

    @pytest.mark.asyncio
    async def test_query_result_not_list(self):
        """Test internal method returning non-list (defensive)."""
        mock_redis = AsyncMock()
        aggregator = CachedIntelligenceAggregator(mock_redis)
        aggregator.cache = AsyncMock()
        aggregator.cache.get_with_metadata.return_value = (None, None)
        
        # Mock _query_source_with_timeout on the instance
        aggregator._query_source_with_timeout = AsyncMock()
        # One valid, one invalid type (though type hint forbids)
        aggregator._query_source_with_timeout.side_effect = [
            [], # Valid empty list
            "Not a list" # Invalid
        ]
        
        aggregator._sources = [Mock(spec=IntelligenceSource), Mock(spec=IntelligenceSource)] # Two dummies
        
        # This exercises loop "if isinstance(result, list)"
        results = await aggregator.query("svc", "1.0")
        assert results == []

    @pytest.mark.asyncio
    async def test_stigmergic_miss(self):
        """Test stigmergic subscriber returning None."""
        mock_redis = AsyncMock()
        mock_sub = Mock(spec=StigmergicIntelligenceSubscriber)
        mock_sub.get.return_value = None
        
        aggregator = CachedIntelligenceAggregator(
            redis_client=mock_redis,
            stigmergic_subscriber=mock_sub
        )
        aggregator.cache = AsyncMock()
        aggregator.cache.get_with_metadata.return_value = (None, None)
        aggregator._sources = [] # No sources
        
        results = await aggregator.query("svc", "1.0")
        assert results == []
        mock_sub.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_degraded(self):
        """Test health check degraded state (Cache OK, Sources Fail)."""
        mock_redis = AsyncMock()
        aggregator = CachedIntelligenceAggregator(mock_redis)
        aggregator.cache = AsyncMock()
        mock_redis_param = AsyncMock()
        mock_redis_param.ping.return_value = True
        aggregator.cache._redis = mock_redis_param
        
        # Mock super().health_check to return unhealthy
        with pytest.MonkeyPatch.context() as m:
            # We can't easily mock super() call, so we mock _sources to fail health check
            source = Mock(spec=IntelligenceSource)
            source.name = "fail_src"
            source.health_check = AsyncMock(return_value=False)
            aggregator._sources = [source]
            
            res = await aggregator.health_check()
            assert res["status"] == "degraded"
            assert res["healthy"] is True # overall_healthy becomes True if cache is up

    @pytest.mark.asyncio
    async def test_failures_non_zero(self):
        """Test failures > 0 (lines 488->496 else)."""
        mock_redis = AsyncMock()
        aggregator = CachedIntelligenceAggregator(mock_redis)
        aggregator.cache = AsyncMock()
        aggregator.cache.get_with_metadata = AsyncMock(return_value=(None, None))
        
        # One failing source
        source = Mock(spec=IntelligenceSource)
        source.name = "fail"
        source.query = AsyncMock(side_effect=Exception("Fail"))
        aggregator.add_source(source)
        
        results = await aggregator.query("svc", "1.0")
        assert results == []
        # cache.set should NOT be called if failures > 0?
        # Logic says: "elif failures == 0: cache.set(...)".
        # So check cache.set NOT called.
        aggregator.cache.set.assert_not_called()
