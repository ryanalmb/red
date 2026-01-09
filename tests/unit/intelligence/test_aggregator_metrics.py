import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from cyberred.intelligence.aggregator import IntelligenceAggregator
from cyberred.intelligence.base import IntelligenceSource

@pytest.mark.unit
class TestAggregatorMetrics:
    def test_has_error_metrics(self):
        """Test that aggregator has error_metrics property."""
        aggregator = IntelligenceAggregator()
        assert hasattr(aggregator, 'error_metrics')
        assert aggregator.error_metrics is not None

    @pytest.mark.asyncio
    async def test_records_timeout(self):
        """Test that timeouts are recorded in metrics."""
        aggregator = IntelligenceAggregator(timeout=0.1)
        
        # Mock source that sleeps longer than timeout
        source = Mock(spec=IntelligenceSource)
        source.name = "slow_source"
        # query should be awaitable
        async def slow_query(*args, **kwargs):
            await asyncio.sleep(0.5)
            return []
        source.query = slow_query
        
        aggregator.add_source(source)
        
        await aggregator.query("service", "1.0")
        
        metrics = aggregator.error_metrics.get_metrics()
        assert metrics["timeouts"]["slow_source"] == 1

    @pytest.mark.asyncio
    async def test_records_error(self):
        """Test that exceptions are recorded in metrics."""
        aggregator = IntelligenceAggregator()
        
        # Mock source that raises exception
        source = Mock(spec=IntelligenceSource)
        source.name = "error_source"
        source.query.side_effect = Exception("Boom")
        
        aggregator.add_source(source)
        
        await aggregator.query("service", "1.0")
        
        metrics = aggregator.error_metrics.get_metrics()
        assert metrics["errors"]["error_source"]["Exception"] == 1
