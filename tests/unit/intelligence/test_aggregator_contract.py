import pytest
import asyncio
from unittest.mock import Mock
from cyberred.intelligence.aggregator import IntelligenceAggregator
from cyberred.intelligence.base import IntelligenceSource

@pytest.mark.unit
class TestAggregatorContract:
    @pytest.mark.asyncio
    async def test_all_sources_timeout(self):
        """Test query with all sources timing out."""
        aggregator = IntelligenceAggregator(timeout=0.01)
        source = Mock(spec=IntelligenceSource)
        source.name = "slow_source"
        async def slow_query(*args):
            await asyncio.sleep(0.05)
            return []
        source.query = slow_query
        aggregator.add_source(source)
        
        results = await aggregator.query("svc", "1.0")
        assert results == []
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_all_sources_raise_exception(self):
        """Test query with all sources raising exceptions."""
        aggregator = IntelligenceAggregator()
        source = Mock(spec=IntelligenceSource)
        source.name = "error_source"
        source.query.side_effect = Exception("Boom")
        aggregator.add_source(source)
        
        results = await aggregator.query("svc", "1.0")
        assert results == []
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_source_returns_none(self):
        """Test source explicitly returning None."""
        aggregator = IntelligenceAggregator()
        source = Mock(spec=IntelligenceSource)
        source.name = "none_source"
        source.query.return_value = None 
        aggregator.add_source(source)
        
        results = await aggregator.query("svc", "1.0")
        assert results == []
        assert isinstance(results, list)
