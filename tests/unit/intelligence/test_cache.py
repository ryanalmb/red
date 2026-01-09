import pytest
from unittest.mock import AsyncMock, ANY
from cyberred.storage.redis_client import RedisClient
from cyberred.intelligence.cache import IntelligenceCache
from cyberred.intelligence.base import IntelResult
import json

@pytest.fixture
def mock_redis():
    return AsyncMock(spec=RedisClient)

def test_intelligence_cache_class_exists():
    """Test that IntelligenceCache class exists."""
    assert IntelligenceCache is not None

def test_intelligence_cache_init_defaults(mock_redis):
    """Test initialization with default values."""
    cache = IntelligenceCache(mock_redis)
    assert cache._redis == mock_redis
    assert cache._ttl == 3600
    assert cache._key_prefix == "intel:"

def test_intelligence_cache_init_custom(mock_redis):
    """Test initialization with custom values."""
    cache = IntelligenceCache(mock_redis, ttl=60, key_prefix="test:")
    assert cache._redis == mock_redis
    assert cache._ttl == 60
    assert cache._key_prefix == "test:"

def test_make_key_basic(mock_redis):
    """Test basic key generation."""
    cache = IntelligenceCache(mock_redis)
    key = cache._make_key("Apache", "2.4.49")
    assert key == "intel:apache:2.4.49"

def test_make_key_consistency(mock_redis):
    """Test key generation consistency."""
    cache = IntelligenceCache(mock_redis)
    key1 = cache._make_key("Apache", "2.4.49")
    key2 = cache._make_key("APACHE", "2.4.49")
    assert key1 == key2

def test_make_key_differentiation(mock_redis):
    """Test that different inputs produce different keys."""
    cache = IntelligenceCache(mock_redis)
    key1 = cache._make_key("Apache", "2.4.49")
    key2 = cache._make_key("Apache", "2.4.50")
    assert key1 != key2

def test_make_key_special_chars(mock_redis):
    """Test validation of characters in keys."""
    cache = IntelligenceCache(mock_redis)
    # Spaces and colons should be replaced
    key = cache._make_key("Apache HTTP Server", "2.4:test")
    assert " " not in key
    assert key == "intel:apache_http_server:2.4_test"

def test_make_key_empty_version(mock_redis):
    """Test handling of empty version."""
    cache = IntelligenceCache(mock_redis)
    key = cache._make_key("Apache", "")
    assert key == "intel:apache:unknown"

@pytest.mark.asyncio
async def test_get_miss(mock_redis):
    """Test cache miss returns None."""
    mock_redis.get.return_value = None
    cache = IntelligenceCache(mock_redis)
    result = await cache.get("Apache", "2.4.49")
    assert result is None
    # Verify Redis key used
    mock_redis.get.assert_called_with("intel:apache:2.4.49")

@pytest.mark.asyncio
async def test_get_hit(mock_redis):
    """Test cache hit returns list of IntelResult."""
    # Mock data
    intel_data = [
        {
            "source": "cisa",
            "cve_id": "CVE-2021-41773",
            "severity": "critical",
            "exploit_available": True,
            "exploit_path": None,
            "confidence": 1.0,
            "priority": 1,
            "metadata": {}
        }
    ]
    mock_redis.get.return_value = json.dumps(intel_data)
    
    cache = IntelligenceCache(mock_redis)
    results = await cache.get("Apache", "2.4.49")
    
    assert results is not None
    assert len(results) == 1
    assert results[0].cve_id == "CVE-2021-41773"
    assert isinstance(results[0], IntelResult)

@pytest.mark.asyncio
async def test_get_corrupt_data(mock_redis):
    """Test corrupt JSON data is handled gracefully."""
    mock_redis.get.return_value = "{invalid_json"
    
    cache = IntelligenceCache(mock_redis)
    result = await cache.get("Apache", "2.4.49")
    
    assert result is None
    # Start: Verify cleanup - corrupt key should be deleted
    # Wait, the task says delete corrupt entry?
    # Task 3.1: "Delete corrupt entry" logic
    # Need to verify if delete is called
    mock_redis.delete.assert_called_with("intel:apache:2.4.49")

@pytest.mark.asyncio
async def test_get_redis_error(mock_redis):
    """Test Redis connection error returns None (graceful degradation)."""
    mock_redis.get.side_effect = ConnectionError("Redis down")
    
    cache = IntelligenceCache(mock_redis)
    result = await cache.get("Apache", "2.4.49")
    
    assert result is None

@pytest.mark.asyncio
async def test_set_basic(mock_redis):
    """Test basic set operation."""
    cache = IntelligenceCache(mock_redis)
    intel_result = IntelResult(
        source="cisa",
        cve_id="CVE-2021-41773",
        severity="critical",
        exploit_available=True,
        exploit_path=None,
        priority=1,
        confidence=1.0,
        metadata={}
    )
    
    await cache.set("Apache", "2.4.49", [intel_result])
    
    # Verify setex called
    mock_redis.setex.assert_called_once()
    args = mock_redis.setex.call_args[0]
    key, ttl, value = args
    
    val_json = json.loads(value)
    assert key == "intel:apache:2.4.49"
    assert ttl == 3600
    assert "results" in val_json
    assert len(val_json["results"]) == 1
    assert val_json["results"][0]["cve_id"] == "CVE-2021-41773"

@pytest.mark.asyncio
async def test_set_custom_ttl(mock_redis):
    """Test set with custom TTL override."""
    cache = IntelligenceCache(mock_redis)
    intel_result = IntelResult(
        source="test", 
        cve_id="CVE-TEST", 
        severity="low", 
        priority=7, 
        confidence=1.0,
        exploit_available=False,
        exploit_path=None
    )
    
    await cache.set("Apache", "2.4.49", [intel_result], ttl=60)
    
    mock_redis.setex.assert_called_once()
    assert mock_redis.setex.call_args[0][1] == 60

@pytest.mark.asyncio
async def test_set_empty_results(mock_redis):
    """Test caching empty results (negative caching)."""
    cache = IntelligenceCache(mock_redis)
    await cache.set("Apache", "2.4.49", [])
    
    mock_redis.setex.assert_called_once()
    args = mock_redis.setex.call_args[0]
    val_json = json.loads(args[2])
    assert val_json["results"] == []
    assert "cached_at" in val_json

@pytest.mark.asyncio
async def test_set_redis_error(mock_redis):
    """Test Redis error during set is handled gracefully."""
    mock_redis.setex.side_effect = ConnectionError("Redis down")
    cache = IntelligenceCache(mock_redis)
    
    
    # Should not raise exception
    await cache.set("Apache", "2.4.49", [])

@pytest.mark.asyncio
async def test_invalidate_specific(mock_redis):
    """Test invalidation of specific entry."""
    cache = IntelligenceCache(mock_redis)
    
    deleted = await cache.invalidate("Apache", "2.4.49")
    
    mock_redis.delete.assert_called_with("intel:apache:2.4.49")

@pytest.mark.asyncio
async def test_invalidate_all(mock_redis):
    """Test bulk invalidation."""
    mock_redis.keys.return_value = ["key1", "key2"]
    
    cache = IntelligenceCache(mock_redis)
    count = await cache.invalidate_all()
    
    mock_redis.keys.assert_called_with("intel:*")
    mock_redis.delete.assert_called_with("key1", "key2")

@pytest.mark.asyncio
async def test_invalidate_all_pattern(mock_redis):
    """Test bulk invalidation with custom pattern."""
    mock_redis.keys.return_value = ["key1"]
    
    cache = IntelligenceCache(mock_redis)
    await cache.invalidate_all("*apache*")
    
    mock_redis.keys.assert_called_with("intel:*apache*")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalidate_all_no_keys(mock_redis):
    """Test invalidate_all when no keys match pattern."""
    mock_redis.keys.return_value = []
    
    cache = IntelligenceCache(mock_redis)
    count = await cache.invalidate_all()
    
    assert count == 0
    mock_redis.keys.assert_called_with("intel:*")
    mock_redis.delete.assert_not_called()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalidate_error(mock_redis):
    """Test error handling during invalidation."""
    mock_redis.delete.side_effect = ConnectionError("Redis down")
    cache = IntelligenceCache(mock_redis)
    
    deleted = await cache.invalidate("Apache", "2.4.49")
    # Returns 0 on error per graceful degradation pattern
    assert deleted == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalidate_all_keys_error(mock_redis):
    """Test invalidate_all handles keys() error gracefully."""
    mock_redis.keys.side_effect = ConnectionError("Redis down")
    cache = IntelligenceCache(mock_redis)
    
    count = await cache.invalidate_all()
    assert count == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalidate_all_delete_error(mock_redis):
    """Test invalidate_all handles delete() error gracefully."""
    mock_redis.keys.return_value = ["key1", "key2"]
    mock_redis.delete.side_effect = ConnectionError("Redis down")
    cache = IntelligenceCache(mock_redis)
    
    count = await cache.invalidate_all()
    assert count == 0

@pytest.mark.asyncio
async def test_get_with_metadata_miss(mock_redis):
    """Test get_with_metadata returns duplicate None on miss."""
    mock_redis.get.return_value = None
    cache = IntelligenceCache(mock_redis)
    results, cached_at = await cache.get_with_metadata("Apache", "2.4.49")
    assert results is None
    assert cached_at is None

@pytest.mark.asyncio
async def test_get_with_metadata_hit(mock_redis):
    """Test get_with_metadata returns results and timestamp."""
    timestamp = "2023-10-26T12:00:00.000000Z"
    cache_entry = {
        "results": [],
        "cached_at": timestamp
    }
    mock_redis.get.return_value = json.dumps(cache_entry)
    
    cache = IntelligenceCache(mock_redis)
    results, cached_at = await cache.get_with_metadata("Apache", "2.4.49")
    
    assert results is not None
    assert results == []
    assert cached_at == timestamp

@pytest.mark.asyncio
async def test_set_stores_cached_at(mock_redis):
    """Test set stores cached_at timestamp."""
    cache = IntelligenceCache(mock_redis)
    await cache.set("Apache", "2.4.49", [])
    
    mock_redis.setex.assert_called_once()
    args = mock_redis.setex.call_args[0]
    val_json = json.loads(args[2])
    
    assert isinstance(val_json, dict)
    assert "cached_at" in val_json
    assert "results" in val_json
    assert val_json["results"] == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_with_metadata_archive(mock_redis):
    """Test get_with_metadata uses archive key when use_archive=True."""
    timestamp = "2023-10-26T12:00:00.000000Z"
    cache_entry = {
        "results": [{"source": "archive", "cve_id": "CVE-ARCHIVE", "severity": "high", 
                    "exploit_available": False, "exploit_path": None, 
                    "confidence": 1.0, "priority": 3, "metadata": {}}],
        "cached_at": timestamp
    }
    mock_redis.get.return_value = json.dumps(cache_entry)
    
    cache = IntelligenceCache(mock_redis)
    results, cached_at = await cache.get_with_metadata("Apache", "2.4.49", use_archive=True)
    
    # Should use archive key
    mock_redis.get.assert_called_with("intel:archive:apache:2.4.49")
    assert results is not None
    assert len(results) == 1
    assert results[0].cve_id == "CVE-ARCHIVE"
    assert cached_at == timestamp


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_with_metadata_legacy_archive(mock_redis):
    """Test get_with_metadata handles legacy list format when use_archive=True."""
    # Legacy format: array of results without wrapper
    legacy_data = [{"source": "legacy", "cve_id": "CVE-LEGACY", "severity": "high", 
                   "exploit_available": False, "exploit_path": None, 
                   "confidence": 1.0, "priority": 3, "metadata": {}}]
    mock_redis.get.return_value = json.dumps(legacy_data)
    
    cache = IntelligenceCache(mock_redis)
    results, cached_at = await cache.get_with_metadata("Apache", "2.4.49", use_archive=True)
    
    # Should use archive key for archive queries
    mock_redis.get.assert_called_with("intel:archive:apache:2.4.49")
    assert results is not None
    assert len(results) == 1
    assert results[0].cve_id == "CVE-LEGACY"
    # Legacy format has no cached_at
    assert cached_at is None


@pytest.mark.unit
@pytest.mark.asyncio  
async def test_set_archive_failure(mock_redis):
    """Test that archive set failure doesn't fail the entire set operation."""
    # Main setex succeeds, archive set fails
    mock_redis.setex = AsyncMock(return_value=True)
    mock_redis.set = AsyncMock(side_effect=ConnectionError("Archive write failed"))
    
    cache = IntelligenceCache(mock_redis)
    intel_result = IntelResult(
        source="test", cve_id="CVE-TEST", severity="low", 
        priority=7, confidence=1.0, exploit_available=False, exploit_path=None
    )
    
    # Should not raise even though archive fails
    result = await cache.set("Apache", "2.4.49", [intel_result])
    
    # The implementation catches all exceptions and returns False
    # Let's verify both calls were attempted
    mock_redis.setex.assert_called_once()
    mock_redis.set.assert_called_once()


@pytest.mark.unit
def test_make_archive_key(mock_redis):
    """Test archive key generation format."""
    cache = IntelligenceCache(mock_redis)
    key = cache._make_archive_key("Apache", "2.4.49")
    assert key == "intel:archive:apache:2.4.49"


@pytest.mark.unit
def test_make_archive_key_special_chars(mock_redis):
    """Test archive key handles special chars like main key."""
    cache = IntelligenceCache(mock_redis)
    key = cache._make_archive_key("Apache HTTP Server", "2.4:test")
    assert key == "intel:archive:apache_http_server:2.4_test"

