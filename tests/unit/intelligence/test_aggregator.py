import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from cyberred.intelligence import IntelligenceAggregator, IntelligenceSource, IntelResult
from cyberred.intelligence.base import IntelPriority

@pytest.fixture
def aggregator():
    return IntelligenceAggregator()

@pytest.mark.unit
def test_aggregator_exists(aggregator):
    """Test that IntelligenceAggregator class can be instantiated."""
    assert isinstance(aggregator, IntelligenceAggregator)

@pytest.mark.unit
def test_aggregator_defaults(aggregator):
    """Test default initialization values."""
    assert aggregator._timeout == 5.0
    assert aggregator._max_total_time == 6.0
    assert aggregator.sources == []

@pytest.mark.unit
def test_add_source(aggregator):
    """Test adding a valid source."""
    mock_source = MagicMock(spec=IntelligenceSource)
    aggregator.add_source(mock_source)
    assert mock_source in aggregator.sources

@pytest.mark.unit
def test_add_source_type_error(aggregator):
    """Test that adding a non-source raises TypeError."""
    with pytest.raises(TypeError):
        aggregator.add_source("not a source")

@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_structure(aggregator):
    """Test that query is async and returns a list."""
    results = await aggregator.query("service", "version")
    assert isinstance(results, list)

@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_calls_parallel(aggregator):
    """Test that query calls all sources concurrently."""
    source1 = AsyncMock(spec=IntelligenceSource)
    source2 = AsyncMock(spec=IntelligenceSource)
    source1.query.return_value = []
    source2.query.return_value = []
    
    aggregator.add_source(source1)
    aggregator.add_source(source2)
    
    await aggregator.query("foo", "1.0")
    
    assert source1.query.called
    assert source2.query.called

@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_handles_source_timeout(aggregator):
    """Test that a single source timeout doesn't block others."""
    # Fast source
    source1 = AsyncMock(spec=IntelligenceSource)
    source1.name = "fast_source"
    source1.query.return_value = [IntelResult(
        source="fast_source",
        cve_id="CVE-2023-1234",
        severity="high",
        exploit_available=False,
        exploit_path=None,
        confidence=1.0,
        priority=3
    )]
    
    # Slow source
    aggregator._timeout = 0.1
    
    source2 = AsyncMock(spec=IntelligenceSource)
    source2.name = "slow_source"
    
    async def slow_query(*args, **kwargs):
        await asyncio.sleep(0.5)
        return []
        
    source2.query.side_effect = slow_query
    
    aggregator.add_source(source1)
    aggregator.add_source(source2)
    
    results = await aggregator.query("foo", "1.0")
    
    assert len(results) == 1
    assert results[0].source == "fast_source"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_handles_source_exception(aggregator):
    """Test that source exception doesn't fail aggregation."""
    source1 = AsyncMock(spec=IntelligenceSource)
    source1.name = "good_source"
    source1.query.return_value = [IntelResult(
        source="good_source",
        cve_id="CVE-2023-1234",
        severity="high",
        exploit_available=False,
        exploit_path=None,
        confidence=1.0,
        priority=3
    )]
    
    source2 = AsyncMock(spec=IntelligenceSource)
    source2.name = "bad_source"
    source2.query.side_effect = Exception("Boom!")
    
    aggregator.add_source(source1)
    aggregator.add_source(source2)
    
    results = await aggregator.query("foo", "1.0")
    
    assert len(results) == 1
    assert results[0].source == "good_source"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_all_fail(aggregator):
    """Test that aggregation handling when all sources fail."""
    source1 = AsyncMock(spec=IntelligenceSource)
    source1.query.side_effect = Exception("Fail 1")
    
    source2 = AsyncMock(spec=IntelligenceSource)
    source2.query.side_effect = Exception("Fail 2")
    
    aggregator.add_source(source1)
    aggregator.add_source(source2)
    
    results = await aggregator.query("foo", "1.0")
    assert results == []

@pytest.mark.unit
def test_merge_results(aggregator):
    """Test merging of two IntelResults."""
    existing = IntelResult(
        source="s1", 
        cve_id="CVE-1", 
        severity="low", 
        exploit_available=False, 
        exploit_path=None, 
        confidence=0.5, 
        priority=5,
        metadata={"s1_data": "foo"}
    )
    new = IntelResult(
        source="s2", 
        cve_id="CVE-1", 
        severity="high", 
        exploit_available=True, 
        exploit_path="path/to/exploit", 
        confidence=1.0, 
        priority=2,
        metadata={"s2_data": "bar"}
    )
    
    merged = aggregator._merge_results(existing, new)
    
    # Priority check (min wins)
    assert merged.priority == 2
    # Confidence check (max wins)
    assert merged.confidence == 1.0
    # Exploit available (OR logic)
    assert merged.exploit_available is True
    # Exploit path (if priority is better)
    assert merged.exploit_path == "path/to/exploit"
    # Metadata consolidated
    assert merged.metadata["s1_data"] == "foo"
    assert merged.metadata["s2_data"] == "bar"
    assert "_sources" in merged.metadata
    assert "s1" in merged.metadata["_sources"]
    assert "s2" in merged.metadata["_sources"]

@pytest.mark.unit
def test_deduplicate_merges_cve_ids(aggregator):
    """Test that results with same CVE ID are merged."""
    r1 = IntelResult(source="s1", cve_id="CVE-2023-1", severity="low", exploit_available=False, exploit_path=None, confidence=0.5, priority=5)
    r2 = IntelResult(source="s2", cve_id="CVE-2023-1", severity="high", exploit_available=True, exploit_path="path/to/exploit", confidence=1.0, priority=2)
    
    # This should now work as _merge_results is implemented
    results = aggregator._deduplicate_results([r1, r2])
    
    assert len(results) == 1
    assert results[0].cve_id == "CVE-2023-1"
    assert results[0].priority == 2

@pytest.mark.unit
def test_deduplicate_preserves_non_cve(aggregator):
    """Test that non-CVE results are kept."""
    r1 = IntelResult(source="s1", cve_id=None, severity="low", exploit_available=False, exploit_path=None, confidence=0.5, priority=5)
    r2 = IntelResult(source="s2", cve_id=None, severity="high", exploit_available=True, exploit_path=None, confidence=1.0, priority=2)
    
    results = aggregator._deduplicate_results([r1, r2])
    assert len(results) == 2

@pytest.mark.unit
@pytest.mark.asyncio
async def test_sorting_order(aggregator):
    """Test that results are sorted by priority then confidence."""
    # Priority 1 (Best)
    r1 = IntelResult(source="cisa", cve_id="CVE-1", severity="critical", exploit_available=True, exploit_path=None, confidence=1.0, priority=1)
    # Priority 2
    r2 = IntelResult(source="nvd", cve_id="CVE-2", severity="critical", exploit_available=False, exploit_path=None, confidence=1.0, priority=2)
    # Priority 2, lower confidence
    r3 = IntelResult(source="nvd", cve_id="CVE-3", severity="critical", exploit_available=False, exploit_path=None, confidence=0.5, priority=2)
    
    source = AsyncMock(spec=IntelligenceSource)
    source.query.return_value = [r3, r1, r2] # Unsorted
    aggregator.add_source(source)
    
    results = await aggregator.query("foo", "1.0")
    
    assert results[0].priority == 1
    assert results[0].cve_id == "CVE-1"
    
    assert results[1].priority == 2
    assert results[1].confidence == 1.0
    assert results[1].cve_id == "CVE-2"
    
    assert results[2].priority == 2
    assert results[2].confidence == 0.5
    assert results[2].cve_id == "CVE-3"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_health_check_structure(aggregator):
    """Test health check output structure."""
    source1 = AsyncMock(spec=IntelligenceSource)
    source1.name = "s1"
    source1.health_check.return_value = True
    
    aggregator.add_source(source1)
    
    status = await aggregator.health_check()
    assert isinstance(status, dict)
    assert "healthy" in status
    assert "sources" in status
    assert "s1" in status["sources"]
    assert status["sources"]["s1"]["healthy"] is True
    assert "latency_ms" in status["sources"]["s1"]

@pytest.mark.unit
@pytest.mark.asyncio
async def test_health_check_overall(aggregator):
    """Test overall health logic (healthy if >= 1 source healthy)."""
    s1 = AsyncMock(spec=IntelligenceSource)
    s1.name = "s1"
    s1.health_check.return_value = False
    
    s2 = AsyncMock(spec=IntelligenceSource)
    s2.name = "s2"
    s2.health_check.return_value = True
    
    aggregator.add_source(s1)
    aggregator.add_source(s2)
    
    status = await aggregator.health_check()
    assert status["healthy"] is True
    assert status["sources"]["s1"]["healthy"] is False
    assert status["sources"]["s2"]["healthy"] is True

@pytest.mark.unit
@pytest.mark.asyncio
async def test_health_check_failure_handling(aggregator):
    """Test health check handles source exceptions."""
    s1 = AsyncMock(spec=IntelligenceSource)
    s1.name = "s1"
    s1.health_check.side_effect = Exception("error")
    
    aggregator.add_source(s1)
    
    status = await aggregator.health_check()
    assert status["healthy"] is False
    assert status["sources"]["s1"]["healthy"] is False
    assert "error" in status["sources"]["s1"]


# === Additional tests for 100% coverage ===

@pytest.mark.unit
def test_remove_source_success(aggregator):
    """Test removing a source that exists."""
    source = MagicMock(spec=IntelligenceSource)
    source.name = "test_source"
    aggregator.add_source(source)
    
    result = aggregator.remove_source("test_source")
    
    assert result is True
    assert source not in aggregator.sources


@pytest.mark.unit
def test_remove_source_not_found(aggregator):
    """Test removing a source that doesn't exist returns False."""
    source = MagicMock(spec=IntelligenceSource)
    source.name = "existing_source"
    aggregator.add_source(source)
    
    result = aggregator.remove_source("nonexistent_source")
    
    assert result is False
    assert source in aggregator.sources


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_empty_service(aggregator):
    """Test that empty service string returns empty list."""
    source = AsyncMock(spec=IntelligenceSource)
    source.name = "s1"
    aggregator.add_source(source)
    
    results = await aggregator.query("", "1.0")
    
    assert results == []
    source.query.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_total_timeout():
    """Test that total timeout returns empty results."""
    aggregator = IntelligenceAggregator(timeout=5.0, max_total_time=0.05)
    
    source = AsyncMock(spec=IntelligenceSource)
    source.name = "slow_source"
    
    async def very_slow_query(*args):
        await asyncio.sleep(1.0)
        return [IntelResult(
            source="slow_source",
            cve_id="CVE-2023-1234",
            severity="high",
            exploit_available=False,
            exploit_path=None,
            confidence=1.0,
            priority=3
        )]
    
    source.query.side_effect = very_slow_query
    aggregator.add_source(source)
    
    results = await aggregator.query("foo", "1.0")
    
    # Should return empty due to total timeout
    assert results == []


@pytest.mark.unit
def test_merge_results_exploit_path_fallback(aggregator):
    """Test exploit_path fallback when existing has none but new has path."""
    existing = IntelResult(
        source="s1",
        cve_id="CVE-1",
        severity="high",
        exploit_available=False,
        exploit_path=None,  # No exploit path
        confidence=0.5,
        priority=2,  # Higher priority (lower number = better)
        metadata={}
    )
    new = IntelResult(
        source="s2",
        cve_id="CVE-1",
        severity="low",
        exploit_available=True,
        exploit_path="path/to/exploit",  # Has exploit path
        confidence=0.8,
        priority=5,  # Lower priority (higher number = worse)
        metadata={}
    )
    
    merged = aggregator._merge_results(existing, new)
    
    # Since existing has better priority but no exploit path,
    # and new has worse priority but has exploit path,
    # the fallback logic (lines 146-147) should take new's exploit_path
    assert merged.exploit_path == "path/to/exploit"
    assert merged.priority == 2  # Best priority kept
    assert merged.source == "s1"  # Source from better priority


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_handles_exception_in_results(aggregator):
    """Test that exceptions in result list are handled gracefully.
    
    This tests the defense-in-depth exception handling in query() method
    (lines 252-255) which handles cases where gather returns exceptions.
    """
    from unittest.mock import patch
    
    source1 = AsyncMock(spec=IntelligenceSource)
    source1.name = "good_source"
    source1.query.return_value = [IntelResult(
        source="good_source",
        cve_id="CVE-2023-1234",
        severity="high",
        exploit_available=False,
        exploit_path=None,
        confidence=1.0,
        priority=3
    )]
    
    source2 = AsyncMock(spec=IntelligenceSource)
    source2.name = "bad_source"
    
    aggregator.add_source(source1)
    aggregator.add_source(source2)
    
    # Patch gather to return an exception in the results list
    # This simulates the scenario where return_exceptions=True captures an exception
    original_gather = asyncio.gather
    
    async def mock_gather(*coros, return_exceptions=False):
        results = await original_gather(*coros, return_exceptions=True)
        # Inject an exception into the results list
        return [results[0], Exception("Injected exception")]
    
    with patch('asyncio.gather', side_effect=mock_gather):
        results = await aggregator.query("foo", "1.0")
    
    # Should still return results from the good source, ignoring the exception
    assert len(results) == 1
    assert results[0].source == "good_source"


@pytest.mark.unit
def test_merge_results_new_priority_with_exploit_path(aggregator):
    """Test merge when new has better priority AND exploit path (line 146-147).
    
    This hits the 'if new.priority < existing.priority and new.exploit_path' branch.
    """
    existing = IntelResult(
        source="s1",
        cve_id="CVE-1",
        severity="low",
        exploit_available=False,
        exploit_path="old/path",  # Has existing path
        confidence=0.5,
        priority=5,  # Worse priority
        metadata={}
    )
    new = IntelResult(
        source="s2",
        cve_id="CVE-1",
        severity="high",
        exploit_available=True,
        exploit_path="new/better/path",  # Has new path
        confidence=0.8,
        priority=2,  # Better priority 
        metadata={}
    )
    
    merged = aggregator._merge_results(existing, new)
    
    # New has better priority AND exploit path, so new's path wins
    assert merged.exploit_path == "new/better/path"
    assert merged.priority == 2
    assert merged.source == "s2"
    assert merged.severity == "high"


@pytest.mark.unit
def test_merge_results_neither_exploit_condition(aggregator):
    """Test merge when neither exploit path condition is met (no new exploit path).
    
    This tests when new.exploit_path is None, so neither branch is taken
    and exploit_path stays as existing.exploit_path.
    """
    existing = IntelResult(
        source="s1",
        cve_id="CVE-1",
        severity="low",
        exploit_available=False,
        exploit_path="existing/path",  # Has existing path
        confidence=0.5,
        priority=5,
        metadata={}
    )
    new = IntelResult(
        source="s2",
        cve_id="CVE-1",
        severity="high",
        exploit_available=True,
        exploit_path=None,  # No new path
        confidence=0.8,
        priority=2,  # Better priority, but no exploit path to replace with
        metadata={}
    )
    
    merged = aggregator._merge_results(existing, new)
    
    # Neither condition met (new.exploit_path is None), so existing path kept
    assert merged.exploit_path == "existing/path"
    assert merged.priority == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_handles_non_list_result(aggregator):
    """Test that non-list results from gather are skipped (line 258).
    
    This tests the defensive check 'if isinstance(result, list)' at line 258
    which handles unexpected result types.
    """
    from unittest.mock import patch
    
    source = AsyncMock(spec=IntelligenceSource)
    source.name = "weird_source"
    aggregator.add_source(source)
    
    # Patch gather to return a non-list, non-exception result
    async def mock_gather(*coros, return_exceptions=False):
        # Return something that's neither a list nor an Exception
        return ["not_a_valid_result_type"]  # String instead of list
    
    with patch('asyncio.gather', side_effect=mock_gather):
        results = await aggregator.query("foo", "1.0")
    
    # Should return empty list since the result wasn't a proper list
    assert results == []
