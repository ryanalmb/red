import pytest
from unittest.mock import Mock
from cyberred.intelligence.aggregator import IntelligenceAggregator
from cyberred.intelligence.base import IntelligenceSource, IntelResult

@pytest.mark.unit
class TestAggregatorValidation:
    @pytest.mark.asyncio
    async def test_validate_non_list_result(self):
        """Test that source returning non-list is logged and excluded."""
        aggregator = IntelligenceAggregator()
        source = Mock(spec=IntelligenceSource)
        source.name = "bad_source"
        
        async def bad_query(*args):
            return "not a list"
        source.query = bad_query
        
        aggregator.add_source(source)
        results = await aggregator.query("svc", "1.0")
        
        assert results == []
        metrics = aggregator.error_metrics.get_metrics()
        assert metrics["errors"]["bad_source"]["InvalidResultType"] == 1

    @pytest.mark.asyncio
    async def test_validate_invalid_list_items(self):
        """Test that list with invalid items is filtered."""
        aggregator = IntelligenceAggregator()
        source = Mock(spec=IntelligenceSource)
        source.name = "mixed_source"
        
        valid_result = IntelResult(
            source="mixed_source",
            cve_id="CVE-2023-1234",
            severity="high",
            exploit_available=False,
            exploit_path=None,
            confidence=1.0,
            priority=1,
            metadata={}
        )
        
        async def mixed_query(*args):
            return [valid_result, "invalid_item"]
        source.query = mixed_query
        
        aggregator.add_source(source)
        results = await aggregator.query("svc", "1.0")
        
        assert len(results) == 1
        assert results[0].cve_id == "CVE-2023-1234"
