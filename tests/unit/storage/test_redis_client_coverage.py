import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from cyberred.storage.redis_client import RedisClient, ConnectionState
from cyberred.core.config import RedisConfig

@pytest.fixture
def redis_config():
    return RedisConfig(host="localhost", port=6379, password="test")

@pytest.fixture
def mock_redis():
    with patch("redis.asyncio.Redis") as mock_cls:
        # Create a specific AsyncMock for the instance
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        
        # Setup common async methods
        mock_instance.ping = AsyncMock(return_value=True)
        mock_instance.close = AsyncMock()
        mock_instance.connection_pool.disconnect = AsyncMock()
        
        # Setup stream methods as AsyncMocks by default
        mock_instance.xadd = AsyncMock()
        mock_instance.xread = AsyncMock()
        mock_instance.xgroup_create = AsyncMock()
        mock_instance.xreadgroup = AsyncMock()
        mock_instance.xack = AsyncMock()
        mock_instance.xpending = AsyncMock()
        mock_instance.xclaim = AsyncMock()
        
        yield mock_instance

@pytest.mark.asyncio
async def test_xadd_connection_error(redis_config, mock_redis):
    """Test xadd raises ConnectionError on failure."""
    # Ensure ping succeeds for __aenter__
    mock_redis.ping.return_value = True
    mock_redis.xadd.side_effect = ConnectionError("Connection lost")
    
    async with RedisClient(redis_config, "test") as client:
        with pytest.raises(ConnectionError):
            await client.xadd("stream", {"key": "val"})
        assert client._is_connected is False

@pytest.mark.asyncio
async def test_xread_connection_error(redis_config, mock_redis):
    """Test xread raises ConnectionError."""
    mock_redis.xread.side_effect = ConnectionError("Lost")
    
    async with RedisClient(redis_config, "test") as client:
        with pytest.raises(ConnectionError):
            await client.xread("stream", "0")

@pytest.mark.asyncio
async def test_xgroup_create_connection_error(redis_config, mock_redis):
    """Test xgroup_create raises ConnectionError."""
    mock_redis.xgroup_create.side_effect = ConnectionError("Lost")
    
    async with RedisClient(redis_config, "test") as client:
        with pytest.raises(ConnectionError):
            await client.xgroup_create("stream", "group")

@pytest.mark.asyncio
async def test_xreadgroup_connection_error(redis_config, mock_redis):
    """Test xreadgroup raises ConnectionError."""
    mock_redis.xreadgroup.side_effect = ConnectionError("Lost")
    
    async with RedisClient(redis_config, "test") as client:
        with pytest.raises(ConnectionError):
            await client.xreadgroup("group", "con", "stream")

@pytest.mark.asyncio
async def test_xreadgroup_parsing_errors(redis_config, mock_redis):
    """Test xreadgroup parsing edge cases (bytes, invalid json)."""
    # Mock valid signature but invalid JSON
    with patch.object(RedisClient, '_verify_message', return_value='{invalid_json'):
        # Return structure: [[stream_name, [[msg_id, fields]]]]
        mock_redis.xreadgroup.return_value = [
            (b"stream", [
                (b"1-0", {b"payload": b"signed_data"}), 
                (b"2-0", {b"payload": b""}) # Empty payload
            ])
        ]
        
        async with RedisClient(redis_config, "test") as client:
            # Should skip all invalid
            results = await client.xreadgroup("g", "c", "s")
            assert len(results) == 0

@pytest.mark.asyncio
async def test_xack_connection_error(redis_config, mock_redis):
    """Test xack raises ConnectionError."""
    mock_redis.xack.side_effect = ConnectionError("Lost")
    
    async with RedisClient(redis_config, "test") as client:
        # Empty check first (no mock call needed)
        assert await client.xack("s", "g") == 0
        
        with pytest.raises(ConnectionError):
            await client.xack("s", "g", "1-0")

@pytest.mark.asyncio
async def test_xpending_connection_error(redis_config, mock_redis):
    """Test xpending connection error."""
    mock_redis.xpending.side_effect = ConnectionError("Lost")
    
    async with RedisClient(redis_config, "test") as client:
        with pytest.raises(ConnectionError):
            await client.xpending("stream", "group")

@pytest.mark.asyncio
async def test_xpending_formats(redis_config, mock_redis):
    """Test xpending result formats (dict vs list)."""
    
    # 1. Test List format
    mock_redis.xpending.return_value = [
        10, b"1-0", b"10-0", [[b"consumer1", b"5"]]
    ]
    
    async with RedisClient(redis_config, "test") as client:
        res = await client.xpending("s", "g")
        assert res['count'] == 10
        assert res['min_id'] == "1-0"
        assert res['consumers']['consumer1'] == 5

    # 2. Test Dict format
    mock_redis.xpending.return_value = {
        "pending": 5, "min": b"2-0", "max": b"6-0", 
        "consumers": [{"name": b"c2", "pending": 5}]
    }
    
    async with RedisClient(redis_config, "test") as client:
        res = await client.xpending("s", "g")
        assert res['count'] == 5
        assert res['min_id'] == "2-0"
        assert res['consumers']['c2'] == 5

@pytest.mark.asyncio
async def test_xclaim_connection_error(redis_config, mock_redis):
    """Test xclaim connection error."""
    mock_redis.xclaim.side_effect = ConnectionError("Lost")
    
    async with RedisClient(redis_config, "test") as client:
        # Empty check
        assert await client.xclaim("s", "g", "c", 1, []) == []
        
        with pytest.raises(ConnectionError):
            await client.xclaim("s", "g", "c", 1, ["1-0"])

@pytest.mark.asyncio
async def test_health_check_pool_fallback(redis_config, mock_redis):
    """Test health_check falls back to connection pool info."""
    mock_instance = mock_redis
    # Mock connection pool access
    mock_instance.connection_pool.connection_kwargs = {'host': 'pool_host', 'port': 9999}
    
    async with RedisClient(redis_config, "test") as client:
        # Force _master_address to None to trigger fallback
        client._master_address = None
        status = await client.health_check()
        assert status.healthy is True
        assert status.master_addr == "pool_host:9999"

@pytest.mark.asyncio
async def test_xclaim_tampered_and_errors(redis_config, mock_redis):
    """Test xclaim handles tampered messages and parsing errors."""
    with patch.object(RedisClient, '_verify_message') as mock_verify:
        # 1. Missing payload
        mock_redis.xclaim.return_value = [
            (b"1-0", {b"other": b"data"})
        ]
        async with RedisClient(redis_config, "test") as client:
            res = await client.xclaim("s", "g", "c", 1, ["1-0"])
            assert len(res) == 0

        # 2. Invalid Signature (mock_verify returns None)
        mock_verify.return_value = None
        mock_redis.xclaim.return_value = [
            (b"2-0", {b"payload": b"bad_sig"})
        ]
        async with RedisClient(redis_config, "test") as client:
            res = await client.xclaim("s", "g", "c", 1, ["2-0"])
            assert len(res) == 0

        # 3. Invalid JSON
        mock_verify.return_value = "{invalid_json"
        mock_redis.xclaim.return_value = [
            (b"3-0", {b"payload": b"bad_json"})
        ]
        async with RedisClient(redis_config, "test") as client:
            res = await client.xclaim("s", "g", "c", 1, ["3-0"])
            assert len(res) == 0

@pytest.mark.asyncio
async def test_xpending_empty(redis_config, mock_redis):
    """Test xpending handles empty results."""
    mock_redis.xpending.return_value = []
    
    async with RedisClient(redis_config, "test") as client:
        res = await client.xpending("s", "g")
        assert res['count'] == 0

@pytest.mark.asyncio
async def test_xreadgroup_generic_error(redis_config, mock_redis):
    """Test xreadgroup re-raises generic errors."""
    mock_redis.xreadgroup.side_effect = RuntimeError("Other error")
    
    async with RedisClient(redis_config, "test") as client:
        with pytest.raises(RuntimeError):
            await client.xreadgroup("g", "c", "s")

@pytest.mark.asyncio
async def test_xclaim_generic_error(redis_config, mock_redis):
    """Test xclaim re-raises generic errors."""
    mock_redis.xclaim.side_effect = ValueError("Other error")
    
    async with RedisClient(redis_config, "test") as client:
        with pytest.raises(ValueError):
            await client.xclaim("s", "g", "c", 1, ["1-0"])

@pytest.mark.asyncio
async def test_xack_generic_error(redis_config, mock_redis):
    """Test xack re-raises generic errors."""
    mock_redis.xack.side_effect = RuntimeError("Other error")
    
    async with RedisClient(redis_config, "test") as client:
        with pytest.raises(RuntimeError):
            await client.xack("s", "g", "1-0")

@pytest.mark.asyncio
async def test_xpending_generic_error(redis_config, mock_redis):
    """Test xpending re-raises generic errors."""
    mock_redis.xpending.side_effect = RuntimeError("Other error")
    
    async with RedisClient(redis_config, "test") as client:
        with pytest.raises(RuntimeError):
            await client.xpending("s", "g")
