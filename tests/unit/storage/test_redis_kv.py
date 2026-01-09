import pytest
from unittest.mock import AsyncMock, patch
from cyberred.storage.redis_client import RedisClient
from cyberred.core.config import RedisConfig

@pytest.fixture
def redis_config():
    return RedisConfig(
        host="localhost",
        port=6379,
        master_name="mymaster",
        sentinel_hosts=["sentinel:26379"]
    )

@pytest.fixture
def redis_client(redis_config):
    return RedisClient(config=redis_config)

@pytest.mark.asyncio
async def test_get_delegation(redis_client):
    """Test get delegates to master."""
    redis_client._master = AsyncMock()
    redis_client._is_connected = True
    
    await redis_client.get("test_key")
    
    redis_client._master.get.assert_called_once_with("test_key")

@pytest.mark.asyncio
async def test_setex_delegation(redis_client):
    """Test setex delegates to master."""
    redis_client._master = AsyncMock()
    redis_client._is_connected = True
    
    await redis_client.setex("test_key", 3600, "test_value")
    
    redis_client._master.setex.assert_called_once_with("test_key", 3600, "test_value")

@pytest.mark.asyncio
async def test_delete_delegation(redis_client):
    """Test delete delegates to master."""
    redis_client._master = AsyncMock()
    redis_client._is_connected = True
    
    await redis_client.delete("test_key1", "test_key2")
    
    redis_client._master.delete.assert_called_once_with("test_key1", "test_key2")

@pytest.mark.asyncio
async def test_keys_delegation(redis_client):
    """Test keys delegates to master."""
    redis_client._master = AsyncMock()
    redis_client._is_connected = True
    
    await redis_client.keys("test_pattern*")
    
    redis_client._master.keys.assert_called_once_with("test_pattern*")

@pytest.mark.asyncio
async def test_exists_delegation(redis_client):
    """Test exists delegates to master."""
    redis_client._master = AsyncMock()
    redis_client._is_connected = True
    
    await redis_client.exists("test_key")
    
    redis_client._master.exists.assert_called_once_with("test_key")

@pytest.mark.asyncio
async def test_kv_methods_error_when_disconnected(redis_client):
    """Test KV methods raise ConnectionError when not connected."""
    redis_client._is_connected = False
    
    with pytest.raises(ConnectionError):
        await redis_client.get("key")
        
    with pytest.raises(ConnectionError):
        await redis_client.setex("key", 10, "val")
        
    with pytest.raises(ConnectionError):
        await redis_client.delete("key")

@pytest.mark.asyncio
async def test_keys_safe_default(redis_client):
    """Test keys handles empty pattern securely."""
    redis_client._master = AsyncMock()
    redis_client._is_connected = True
    
    # Should probably allow it to pass through, but good to check basic deleg
    await redis_client.keys("*")
    redis_client._master.keys.assert_called_once_with("*")
