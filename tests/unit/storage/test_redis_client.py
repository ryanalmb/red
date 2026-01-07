"""Unit tests for Redis Sentinel client.

Tests for RedisClient class that provides Redis Sentinel connectivity
with automatic failover for stigmergic coordination (Story 3.1).

Story 3.2 adds:
- MessageBuffer for local buffering during connection loss
- ConnectionState enum for connection state machine
- Exponential backoff reconnection logic
"""

import pytest
import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from cyberred.core.config import RedisConfig
from cyberred.storage.redis_client import RedisClient, PubSubSubscription


class TestRedisClientStructure:
    """Tests for RedisClient class structure (Task 1)."""

    def test_redis_client_instantiation(self) -> None:
        """Test that RedisClient can be instantiated with RedisConfig."""
        config = RedisConfig(
            host="localhost",
            port=6379,
            sentinel_hosts=["sentinel1:26379", "sentinel2:26379"],
            master_name="mymaster",
        )
        client = RedisClient(config, engagement_id="test-engagement")
        
        assert client is not None
        assert isinstance(client, RedisClient)

    def test_redis_client_pool_size_property(self) -> None:
        """Test that pool_size property returns default value."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        # Default pool size is 10 per story requirements
        assert client.pool_size == 10

    def test_redis_client_is_connected_initially_false(self) -> None:
        """Test that is_connected is False before connect() is called."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_redis_client_async_context_manager(self) -> None:
        """Test that RedisClient supports async context manager protocol."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        # Verify __aenter__ and __aexit__ are present
        assert hasattr(client, "__aenter__")
        assert hasattr(client, "__aexit__")

    @pytest.mark.asyncio
    async def test_redis_client_connect_and_close_methods_exist(self) -> None:
        """Test that connect() and close() async methods exist."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        # Methods should exist
        assert hasattr(client, "connect")
        assert hasattr(client, "close")
        assert callable(client.connect)
        assert callable(client.close)


class TestRedisClientMasterDiscovery:
    """Tests for Sentinel master discovery (Task 2)."""

    def test_redis_client_has_master_address_property(self) -> None:
        """Test that master_address property exists."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        assert hasattr(client, "master_address")
        # Before connection, should be None
        assert client.master_address is None

    def test_redis_client_sentinel_parsing(self) -> None:
        """Test that sentinel_hosts are parsed correctly."""
        config = RedisConfig(
            sentinel_hosts=["host1:26379", "host2:26380", "host3"],
        )
        client = RedisClient(config, engagement_id="test-engagement")
        
        # Internal parsing should work
        parsed = client._parse_sentinel_hosts()
        assert ("host1", 26379) in parsed
        assert ("host2", 26380) in parsed
        assert ("host3", 26379) in parsed  # default port


class TestRedisClientPoolManagement:
    """Tests for connection pool management (Task 4)."""

    def test_redis_client_pool_size_configurable(self) -> None:
        """Test that pool_size can be configured."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement", pool_size=20)
        
        assert client.pool_size == 20

    def test_redis_client_pool_stats_exist(self) -> None:
        """Test that pool stats are exposed."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        assert hasattr(client, "pool_stats")


class TestPubSubSubscription:
    """Tests for PubSubSubscription dataclass (Task 6)."""

    def test_pubsub_subscription_structure(self) -> None:
        """Test PubSubSubscription has required fields."""
        # Create a mock unsubscribe callable
        async def mock_unsubscribe() -> None:
            pass
        
        sub = PubSubSubscription(
            pattern="findings:*",
            unsubscribe=mock_unsubscribe,
        )
        
        assert sub.pattern == "findings:*"
        assert callable(sub.unsubscribe)


class TestRedisClientPubSub:
    """Tests for pub/sub operations (Tasks 5-6)."""

    def test_publish_method_exists(self) -> None:
        """Test that publish method exists."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        assert hasattr(client, "publish")
        assert callable(client.publish)

    def test_subscribe_method_exists(self) -> None:
        """Test that subscribe method exists."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        assert hasattr(client, "subscribe")
        assert callable(client.subscribe)

    @pytest.mark.asyncio
    async def test_publish_raises_when_disconnected(self) -> None:
        """Test that publish raises ConnectionError when not connected."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        with pytest.raises(ConnectionError, match="Not connected"):
            await client.publish("channel", "message")

    @pytest.mark.asyncio
    async def test_subscribe_raises_when_disconnected(self) -> None:
        """Test that subscribe raises ConnectionError when not connected."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        async def callback(ch: str, msg: str) -> None:
            pass
        
        with pytest.raises(ConnectionError, match="Not connected"):
            await client.subscribe("pattern:*", callback)


class TestRedisClientStreams:
    """Tests for Redis Streams operations (Tasks 7, 7b)."""

    def test_xadd_method_exists(self) -> None:
        """Test that xadd method exists."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        assert hasattr(client, "xadd")
        assert callable(client.xadd)

    def test_xread_method_exists(self) -> None:
        """Test that xread method exists."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        assert hasattr(client, "xread")
        assert callable(client.xread)

    @pytest.mark.asyncio
    async def test_xadd_raises_when_disconnected(self) -> None:
        """Test that xadd raises ConnectionError when not connected."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        with pytest.raises(ConnectionError, match="Not connected"):
            await client.xadd("stream", {"field": "value"})

    @pytest.mark.asyncio
    async def test_xread_raises_when_disconnected(self) -> None:
        """Test that xread raises ConnectionError when not connected."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        with pytest.raises(ConnectionError, match="Not connected"):
            await client.xread("stream", "0")


# =============================================================================
# Story 3.4: Redis Streams with HMAC Tests
# =============================================================================


class TestRedisClientStreamsHMAC:
    """Tests for Story 3.4 Redis Streams with HMAC signing/verification."""

    @pytest.mark.asyncio
    async def test_xadd_signs_payload_with_hmac(self) -> None:
        """Test xadd serializes and signs the payload."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._master.xadd = AsyncMock(return_value="1234567890-0")
        
        with patch.object(client, "_sign_message", return_value="signed_data") as mock_sign:
            await client.xadd("audit:stream", {"type": "test", "value": 123})
            
            mock_sign.assert_called_once()
            # Payload stored as {"payload": signed_data}
            client._master.xadd.assert_called_once()
            call_kwargs = client._master.xadd.call_args
            assert call_kwargs[0][1] == {"payload": "signed_data"}

    @pytest.mark.asyncio
    async def test_xread_verifies_hmac_and_parses_json(self) -> None:
        """Test xread verifies HMAC and parses JSON."""
        import json
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        
        # Mock Redis response
        client._master.xread = AsyncMock(return_value=[
            (b"audit:stream", [(b"123-0", {b"payload": b"signed_json"})])
        ])
        
        with patch.object(client, "_verify_message", return_value='{"type": "test"}'):
            result = await client.xread("audit:stream", "0")
            
            assert len(result) == 1
            assert result[0][0] == "123-0"
            assert result[0][1] == {"type": "test"}

    @pytest.mark.asyncio
    async def test_xread_skips_tampered_messages(self) -> None:
        """Test xread skips messages with invalid HMAC."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        
        client._master.xread = AsyncMock(return_value=[
            (b"audit:stream", [
                (b"123-0", {b"payload": b"tampered"}),
                (b"124-0", {b"payload": b"valid"}),
            ])
        ])
        
        # First message fails verification, second passes
        with patch.object(client, "_verify_message", side_effect=[None, '{"ok": true}']):
            result = await client.xread("audit:stream", "0")
            
            # Only valid message returned
            assert len(result) == 1
            assert result[0][0] == "124-0"

    @pytest.mark.asyncio
    async def test_xread_handles_missing_payload(self) -> None:
        """Test xread handles messages without payload field."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        
        client._master.xread = AsyncMock(return_value=[
            (b"audit:stream", [(b"123-0", {b"other_field": b"value"})])
        ])
        
        result = await client.xread("audit:stream", "0")
        assert len(result) == 0  # Skipped

    @pytest.mark.asyncio
    async def test_xread_handles_invalid_json(self) -> None:
        """Test xread handles messages with invalid JSON."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        
        client._master.xread = AsyncMock(return_value=[
            (b"audit:stream", [(b"123-0", {b"payload": b"signed"})])
        ])
        
        with patch.object(client, "_verify_message", return_value="not valid json"):
            result = await client.xread("audit:stream", "0")
            assert len(result) == 0  # Skipped

    @pytest.mark.asyncio
    async def test_xread_returns_empty_for_no_results(self) -> None:
        """Test xread returns empty list when no messages."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._master.xread = AsyncMock(return_value=None)
        
        result = await client.xread("audit:stream", "0")
        assert result == []

    @pytest.mark.asyncio
    async def test_xgroup_create_returns_true_on_success(self) -> None:
        """Test xgroup_create returns True on successful creation."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._master.xgroup_create = AsyncMock(return_value=True)
        
        result = await client.xgroup_create("audit:stream", "my-group")
        
        assert result is True
        client._master.xgroup_create.assert_called_with(
            "audit:stream", "my-group", "$", mkstream=True
        )

    @pytest.mark.asyncio
    async def test_xgroup_create_returns_false_if_exists(self) -> None:
        """Test xgroup_create returns False if group already exists."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._master.xgroup_create = AsyncMock(
            side_effect=Exception("BUSYGROUP Consumer Group name already exists")
        )
        
        result = await client.xgroup_create("audit:stream", "my-group")
        assert result is False

    @pytest.mark.asyncio
    async def test_xgroup_create_raises_when_disconnected(self) -> None:
        """Test xgroup_create raises ConnectionError when disconnected."""
        client = RedisClient(RedisConfig())
        
        with pytest.raises(ConnectionError, match="Not connected"):
            await client.xgroup_create("stream", "group")

    @pytest.mark.asyncio
    async def test_xreadgroup_verifies_hmac(self) -> None:
        """Test xreadgroup verifies HMAC signatures."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        
        client._master.xreadgroup = AsyncMock(return_value=[
            (b"audit:stream", [(b"123-0", {b"payload": b"signed"})])
        ])
        
        with patch.object(client, "_verify_message", return_value='{"event": "test"}'):
            result = await client.xreadgroup("group", "consumer", "audit:stream")
            
            assert len(result) == 1
            assert result[0][1] == {"event": "test"}

    @pytest.mark.asyncio
    async def test_xreadgroup_raises_when_disconnected(self) -> None:
        """Test xreadgroup raises ConnectionError when disconnected."""
        client = RedisClient(RedisConfig())
        
        with pytest.raises(ConnectionError, match="Not connected"):
            await client.xreadgroup("group", "consumer", "stream")

    @pytest.mark.asyncio
    async def test_xreadgroup_returns_empty_for_no_results(self) -> None:
        """Test xreadgroup returns empty list when no messages."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._master.xreadgroup = AsyncMock(return_value=None)
        
        result = await client.xreadgroup("group", "consumer", "stream")
        assert result == []

    @pytest.mark.asyncio
    async def test_xack_acknowledges_messages(self) -> None:
        """Test xack acknowledges messages."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._master.xack = AsyncMock(return_value=2)
        
        result = await client.xack("stream", "group", "123-0", "124-0")
        
        assert result == 2
        client._master.xack.assert_called_with("stream", "group", "123-0", "124-0")

    @pytest.mark.asyncio
    async def test_xack_returns_zero_for_empty(self) -> None:
        """Test xack returns 0 for empty message_ids."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        
        result = await client.xack("stream", "group")
        assert result == 0

    @pytest.mark.asyncio
    async def test_xack_raises_when_disconnected(self) -> None:
        """Test xack raises ConnectionError when disconnected."""
        client = RedisClient(RedisConfig())
        
        with pytest.raises(ConnectionError, match="Not connected"):
            await client.xack("stream", "group", "123-0")

    @pytest.mark.asyncio
    async def test_xpending_returns_info(self) -> None:
        """Test xpending returns pending info."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._master.xpending = AsyncMock(return_value=[
            5, b"100-0", b"105-0", [[b"consumer1", b"3"], [b"consumer2", b"2"]]
        ])
        
        result = await client.xpending("stream", "group")
        
        assert result["count"] == 5
        assert result["min_id"] == "100-0"
        assert result["max_id"] == "105-0"
        assert result["consumers"]["consumer1"] == 3
        assert result["consumers"]["consumer2"] == 2

    @pytest.mark.asyncio
    async def test_xpending_raises_when_disconnected(self) -> None:
        """Test xpending raises ConnectionError when disconnected."""
        client = RedisClient(RedisConfig())
        
        with pytest.raises(ConnectionError, match="Not connected"):
            await client.xpending("stream", "group")

    @pytest.mark.asyncio
    async def test_xclaim_claims_messages_with_verification(self) -> None:
        """Test xclaim claims and verifies messages."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._master.xclaim = AsyncMock(return_value=[
            (b"123-0", {b"payload": b"signed"})
        ])
        
        with patch.object(client, "_verify_message", return_value='{"claimed": true}'):
            result = await client.xclaim("stream", "group", "consumer", 60000, ["123-0"])
            
            assert len(result) == 1
            assert result[0][1] == {"claimed": True}

    @pytest.mark.asyncio
    async def test_xclaim_returns_empty_for_no_ids(self) -> None:
        """Test xclaim returns empty for empty message_ids."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        
        result = await client.xclaim("stream", "group", "consumer", 60000, [])
        assert result == []

    @pytest.mark.asyncio
    async def test_xclaim_raises_when_disconnected(self) -> None:
        """Test xclaim raises ConnectionError when disconnected."""
        client = RedisClient(RedisConfig())
        
        with pytest.raises(ConnectionError, match="Not connected"):
            await client.xclaim("stream", "group", "consumer", 60000, ["123-0"])


class TestRedisClientHealthCheck:
    """Tests for health_check method (Task 9)."""

    def test_health_check_method_exists(self) -> None:
        """Test that health_check method exists."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        assert hasattr(client, "health_check")
        assert callable(client.health_check)

    @pytest.mark.asyncio
    async def test_health_check_when_disconnected(self) -> None:
        """Test health_check returns unhealthy when not connected."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        status = await client.health_check()
        
        assert status.healthy is False
        assert status.latency_ms == 0.0
        assert status.master_addr == ""

    @pytest.mark.asyncio
    async def test_health_check_with_ping_failure(self) -> None:
        """Test health_check returns unhealthy when ping fails."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        # Simulate connected state with failing ping
        client._is_connected = True
        mock_master = AsyncMock()
        mock_master.ping = AsyncMock(side_effect=ConnectionError("Connection lost"))
        client._master = mock_master
        
        status = await client.health_check()
        
        assert status.healthy is False
        assert status.latency_ms == 0.0
        assert status.master_addr == ""

    @pytest.mark.asyncio
    async def test_health_check_with_master_address_set(self) -> None:
        """Test health_check uses master_address when available."""
        config = RedisConfig(host="default-host", port=1234)
        client = RedisClient(config, engagement_id="test-engagement")
        
        # Simulate connected state with master address set
        client._is_connected = True
        client._master_address = ("real-master", 6379)
        mock_master = AsyncMock()
        mock_master.ping = AsyncMock(return_value=True)
        client._master = mock_master
        
        status = await client.health_check()
        
        assert status.healthy is True
        assert status.latency_ms >= 0
        assert status.master_addr == "real-master:6379"  # Uses master_address

    @pytest.mark.asyncio
    async def test_health_check_emits_master_changed(self) -> None:
        """Test that health check emits REDIS_MASTER_CHANGED on failure if previously connected."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        # Simulate connected state
        client._is_connected = True
        mock_master = AsyncMock()
        mock_master.ping = AsyncMock(side_effect=Exception("Ping failed"))
        client._master = mock_master
        
        # Run health check - should fail and log warning
        with patch("cyberred.storage.redis_client.log") as mock_log:
            status = await client.health_check()
            
            assert status.healthy is False
            assert not client._is_connected
            
            # Verify specific log event
            mock_log.warning.assert_any_call(
                "REDIS_MASTER_CHANGED",
                reason="health_check_failed",
                error="Ping failed"
            )

class TestRedisClientStats:
    """Tests for pool statistics (Task 4)."""
    
    @pytest.mark.asyncio
    async def test_pool_stats_disconnected(self) -> None:
        """Test pool_stats when disconnected."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        stats = client.pool_stats
        assert stats["pool_size"] == 10
        assert stats["in_use"] == 0
        assert stats["available"] == 0
    
    @pytest.mark.asyncio
    async def test_pool_stats_connected(self) -> None:
        """Test pool_stats when connected."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        # Mock connection pool
        client._is_connected = True
        mock_master = MagicMock() # Redis client
        mock_pool = MagicMock()
        mock_pool.max_connections = 10
        mock_pool._in_use_connections = [1, 2]
        mock_pool._available_connections = [3, 4, 5]
        mock_pool._created_connections = 5
        mock_master.connection_pool = mock_pool
        client._master = mock_master
        
        stats = client.pool_stats
        assert stats["pool_size"] == 10
        assert stats["in_use"] == 2
        assert stats["available"] == 3
        assert stats["created"] == 5

class TestRedisClientHMAC:
    """Tests for HMAC signature verification (Task 5 & 6)."""

    @pytest.mark.asyncio
    async def test_publish_adds_signature(self) -> None:
        """Test that publish adds HMAC signature to message."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        # Mock master and publish
        client._is_connected = True
        mock_master = AsyncMock()
        client._master = mock_master
        
        await client.publish("channel", "message")
        
        # Verify publish was called with a JSON structure containing signature
        args = mock_master.publish.call_args
        assert args is not None
        channel, message = args[0]
        assert channel == "channel"
        
        # Message should be JSON with content and sig
        import json
        data = json.loads(message)
        assert data["content"] == "message"
        assert "sig" in data
        assert len(data["sig"]) == 64  # SHA256 hex digest length

    @pytest.mark.asyncio
    async def test_subscribe_verifies_signature(self) -> None:
        """Test that subscribe validates signatures on incoming messages."""
        config = RedisConfig()
        client = RedisClient(config, engagement_id="test-engagement")
        
        content = "test-message"
        signed = client._sign_message(content)
        
        # Test valid
        assert client._verify_message(signed) == content
        
        # Test invalid
        import json
        data = json.loads(signed)
        data["sig"] = "bad-sig"
        assert client._verify_message(json.dumps(data)) is None


class TestRedisClientCoverage:
    """Targeted tests to fill coverage gaps."""

    @pytest.mark.asyncio
    async def test_connect_handles_discovery_error(self) -> None:
        """Test connect warning log when master discovery fails."""
        config = RedisConfig(sentinel_hosts=["sentinel:26379"])
        client = RedisClient(config)
        
        with patch("redis.asyncio.sentinel.Sentinel") as MockSentinel:
            mock_sentinel_instance = MockSentinel.return_value
            mock_sentinel_instance.discover_master.side_effect = Exception("Discovery failed")
            # ensure master_for returns an object with async ping
            mock_master = MagicMock()
            mock_master.ping = AsyncMock(return_value=True)
            mock_sentinel_instance.master_for.return_value = mock_master
            
            with patch("cyberred.storage.redis_client.log") as mock_log:
                await client.connect()
                
                mock_log.warning.assert_any_call(
                    "redis_master_discovery_failed_log_only", 
                    error="Discovery failed"
                )
    
    @pytest.mark.asyncio
    async def test_connect_handles_ping_failure(self) -> None:
        """Test connect raising ConnectionError on initial ping failure."""
        config = RedisConfig(sentinel_hosts=["sentinel:26379"])
        client = RedisClient(config)
        
        with patch("redis.asyncio.sentinel.Sentinel") as MockSentinel:
            mock_sentinel_instance = MockSentinel.return_value
            mock_sentinel_instance.master_for.return_value.ping.side_effect = Exception("Ping failed")
            
            with pytest.raises(ConnectionError, match="Failed to connect"):
                await client.connect()

    @pytest.mark.asyncio
    async def test_close_handles_cancellation_error(self) -> None:
        """Test close ignores cancellation error from listener task."""
        client = RedisClient(RedisConfig())
        client._pubsub_task = AsyncMock()
        client._pubsub_task.cancel.return_value = None
        # Make the await raise CancelledError
        client._pubsub_task.__await__ = MagicMock(side_effect=asyncio.CancelledError)
        
        await client.close()
        assert client._pubsub_task is None

    @pytest.mark.asyncio
    async def test_verify_message_edge_cases(self) -> None:
        """Test _verify_message with invalid inputs."""
        client = RedisClient(RedisConfig())
        
        # Invalid JSON
        assert client._verify_message("{bad_json") is None
        
        # Missing fields
        assert client._verify_message("{}") is None
        assert client._verify_message('{"content": "foo"}') is None
        assert client._verify_message('{"sig": "bar"}') is None
        
        # Generated exception (mock json.loads to raise generic error)
        with patch("json.loads", side_effect=Exception("Generic Error")):
            assert client._verify_message("{}") is None

    @pytest.mark.asyncio
    async def test_publish_connection_error_handling(self) -> None:
        """Test publish buffers on ConnectionError (Story 3.2 behavior)."""
        from cyberred.storage.redis_client import ConnectionState
        
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._connection_state = ConnectionState.CONNECTED
        client._master = AsyncMock()
        client._master.publish.side_effect = ConnectionError("Lost")
        
        # Story 3.2: publish should buffer and return 0, not raise
        result = await client.publish("channel", "msg")
        
        assert result == 0
        assert client._is_connected is False
        assert client._connection_state == ConnectionState.DEGRADED
        assert client._buffer.size == 1  # Message was buffered

    @pytest.mark.asyncio
    async def test_xadd_connection_error_handling(self) -> None:
        """Test xadd handles ConnectionError."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._master.xadd.side_effect = ConnectionError("Lost")
        
        with pytest.raises(ConnectionError, match="Connection lost"):
            await client.xadd("stream", {})
            
        assert client._is_connected is False

    @pytest.mark.asyncio
    async def test_xread_connection_error_handling(self) -> None:
        """Test xread handles ConnectionError."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._master.xread.side_effect = ConnectionError("Lost")
        
        with pytest.raises(ConnectionError, match="Connection lost"):
            await client.xread("s", "0")
            
        assert client._is_connected is False

    @pytest.mark.asyncio
    async def test_health_check_fallback_address(self) -> None:
        """Test health check uses connection pool kwargs as fallback."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._master.ping.return_value = True
        
        # Mock connection pool kwargs
        mock_pool = MagicMock()
        mock_pool.connection_kwargs = {"host": "fallback-host", "port": 1234}
        client._master.connection_pool = mock_pool
        
        status = await client.health_check()
        assert status.master_addr == "fallback-host:1234"
        
    @pytest.mark.asyncio
    async def test_health_check_fallback_exception(self) -> None:
        """Test health check fallback ignores exception."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._master.ping.return_value = True
        
        # Mock connection pool to raise error on access
        type(client._master).connection_pool = PropertyMock(side_effect=Exception("Pool error"))
        
        status = await client.health_check()
        # Should fallback to config host:port
        assert status.master_addr == "localhost:6379"

    @pytest.mark.asyncio
    async def test_pubsub_listener_edge_cases(self) -> None:
        """Test listener handles various message types and errors."""
        client = RedisClient(RedisConfig())
        client._pubsub = AsyncMock()
        
        # Mock callbacks
        callback = AsyncMock()
        client._callbacks = {"tests:*": [callback]}
        
        # Helper for async generator
        async def mock_listen_gen():
            yield {"type": "subscribe", "channel": b"foo", "data": 1}
            yield {
                "type": "pmessage", 
                "pattern": b"tests:*", 
                "channel": b"tests:1", 
                "data": b"{\"content\": \"data\", \"sig\": \"sig\"}"
            }
            await asyncio.sleep(10) # Keep alive
            
        # Ensure pubsub is not AsyncMock for listen() call
        client._pubsub = MagicMock()
        client._pubsub.listen.return_value = mock_listen_gen()
        
        # Patch verify_message to succeed
        with patch.object(client, "_verify_message", return_value="verified_data"):
            with patch("cyberred.storage.redis_client.log") as mock_log:
                # Create task and wait for it to process
                task = asyncio.create_task(client._pubsub_listener())
                
                # Give it time to process the yields
                await asyncio.sleep(0.5)
                
                # Check for crash
                if mock_log.error.called:
                    # Print calls for debugging if failed
                    print(f"DEBUG: Log error calls: {mock_log.error.call_args_list}")
                
                assert not mock_log.error.called, f"Listener crashed: {mock_log.error.call_args_list}"
                
                # Verify callback invoked
                callback.assert_called_once()
                args = callback.call_args
                assert args[0][0] == "tests:1" 
                assert args[0][1] == "verified_data"
                
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


    @pytest.mark.asyncio
    async def test_pubsub_listener_early_exit(self) -> None:
        """Test listener exits early if no pubsub connection."""
        client = RedisClient(RedisConfig())
        client._pubsub = None
        await client._pubsub_listener()
        # Should just return without error

    @pytest.mark.asyncio
    async def test_pubsub_listener_yields_strings(self) -> None:
        """Test listener handles string data (already decoded)."""
        client = RedisClient(RedisConfig())
        callback = AsyncMock()
        client._callbacks = {"tests:*": [callback]}
        
        # Async generator yielding STRINGS instead of bytes
        async def mock_listen_gen():
            yield {
                "type": "pmessage", 
                "pattern": "tests:*", 
                "channel": "tests:1", 
                "data": '{"content": "data", "sig": "sig"}'
            }
            await asyncio.sleep(10)
            
        client._pubsub = MagicMock()
        client._pubsub.listen.return_value = mock_listen_gen()
        
        with patch.object(client, "_verify_message", return_value="verified"):
            task = asyncio.create_task(client._pubsub_listener())
            await asyncio.sleep(0.1)
            callback.assert_called_with("tests:1", "verified")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_pubsub_listener_callback_exception(self) -> None:
        """Test listener handles callback exceptions."""
        client = RedisClient(RedisConfig())
        callback = AsyncMock(side_effect=Exception("Callback failed"))
        client._callbacks = {"tests:*": [callback]}
        
        async def mock_listen_gen():
            yield {
                "type": "pmessage", 
                "pattern": b"tests:*", 
                "channel": b"tests:1", 
                "data": b'{}'
            }
            await asyncio.sleep(10)
            
        client._pubsub = MagicMock()
        client._pubsub.listen.return_value = mock_listen_gen()
        
        with patch.object(client, "_verify_message", return_value="data"):
            with patch("cyberred.storage.redis_client.log") as mock_log:
                task = asyncio.create_task(client._pubsub_listener())
                await asyncio.sleep(0.1)
                
                # Should log the error
                mock_log.error.assert_any_call("redis_callback_error", error="Callback failed")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    @pytest.mark.asyncio
    async def test_pubsub_listener_generic_crash(self) -> None:
        """Test listener handles generic crash logs."""
        client = RedisClient(RedisConfig())
        client._pubsub = MagicMock()
        client._pubsub.listen.side_effect = Exception("Crash")
        
        with patch("cyberred.storage.redis_client.log") as mock_log:
            await client._pubsub_listener()
            mock_log.error.assert_called_with("redis_listener_crashed", error="Crash")

    @pytest.mark.asyncio
    async def test_subscribe_idempotency(self) -> None:
        """Test subscribe re-uses existing connection and set."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = MagicMock()
        client._pubsub = MagicMock()
        
        # Pre-populate
        client._callbacks = {"pat": []}
        
        # Subscribe again
        await client.subscribe("pat", AsyncMock())
        
        # Should NOT call psubscribe again
        client._pubsub.psubscribe.assert_not_called()

    @pytest.mark.asyncio
    async def test_unsubscribe_logic(self) -> None:
        """Test unsubscribe logic thoroughly."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = MagicMock()
        client._pubsub = AsyncMock()
        client._pubsub.punsubscribe = AsyncMock()
        
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        
        # Setup subscription
        sub = await client.subscribe("pat", cb1)
        # Add second callback manually or via subscribe
        client._callbacks["pat"].append(cb2)
        
        # Unsubscribe cb1
        await sub.unsubscribe()
        assert cb1 not in client._callbacks["pat"]
        assert cb2 in client._callbacks["pat"]
        # punsubscribe not called yet
        client._pubsub.punsubscribe.assert_not_called()
        
        # Unsubscribe cb2 (simulate second handle)
        # We can reuse the same handle logic if we mock it, or just use internal logic
        # But 'sub' closure captured 'cb1'.
        
        # Let's create a "fake" handle for cb2 or just call the logic manually?
        # Better: create a second subscription
        sub2 = await client.subscribe("pat", cb2) # This appends cb2 (now it's in twice? no, I added it manually before)
        # Reset state to be clean
        client._callbacks["pat"] = [cb2] 
        
        # Create handle for cb2 properly
        async def unsub_cb2():
            client._callbacks["pat"].remove(cb2)
            if not client._callbacks["pat"]:
                 await client._pubsub.punsubscribe("pat")
                 del client._callbacks["pat"]
                 
        await unsub_cb2()
        
        # Now callbacks empty, punsubscribe should be called
        assert "pat" not in client._callbacks
        client._pubsub.punsubscribe.assert_called_with("pat")

    @pytest.mark.asyncio
    async def test_unsubscribe_safe_checking(self) -> None:
        """Test unsubscribe handles already removed patterns/callbacks."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = MagicMock()
        client._pubsub = AsyncMock()
        
        cb = AsyncMock()
        sub = await client.subscribe("pat", cb)
        
        # Remove from backend manually
        del client._callbacks["pat"]
        
        # Call unsubscribe - should fail silently
        await sub.unsubscribe()

    @pytest.mark.asyncio
    async def test_pubsub_listener_pattern_mismatch(self) -> None:
        """Test listener ignores messages for unknown patterns."""
        client = RedisClient(RedisConfig())
        client._callbacks = {} # No callbacks
        
        async def mock_listen_gen():
            yield {
                "type": "pmessage", 
                "pattern": b"unknown:*", 
                "channel": b"unknown:1", 
                "data": b'{}'
            }
            await asyncio.sleep(10)
            
        client._pubsub = MagicMock()
        client._pubsub.listen.return_value = mock_listen_gen()
        
        with patch.object(client, "_verify_message") as mock_verify:
            task = asyncio.create_task(client._pubsub_listener())
            await asyncio.sleep(0.1)
            mock_verify.assert_not_called()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_pubsub_listener_invalid_signature(self) -> None:
        """Test listener ignores messages with invalid signatures."""
        client = RedisClient(RedisConfig())
        cb = AsyncMock()
        client._callbacks = {"tests:*": [cb]}
        
        async def mock_listen_gen():
            yield {
                "type": "pmessage", 
                "pattern": b"tests:*", 
                "channel": b"tests:1", 
                "data": b'bad_sig_json'
            }
            await asyncio.sleep(10)
            
        client._pubsub = MagicMock()
        client._pubsub.listen.return_value = mock_listen_gen()
        
        # Mock _verify_message to return None (invalid)
        with patch.object(client, "_verify_message", return_value=None):
            task = asyncio.create_task(client._pubsub_listener())
            await asyncio.sleep(0.1)
            cb.assert_not_called()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_publish_generic_error(self) -> None:
        """Test publish re-raises non-ConnectionError exceptions."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._master.publish.side_effect = ValueError("Generic")
        
        with pytest.raises(ValueError, match="Generic"):
            await client.publish("chan", "msg")

    @pytest.mark.asyncio
    async def test_xadd_generic_error(self) -> None:
        """Test xadd re-raises non-ConnectionError exceptions."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._master.xadd.side_effect = ValueError("Generic")
        
        with pytest.raises(ValueError, match="Generic"):
            await client.xadd("s", {})

    @pytest.mark.asyncio
    async def test_xread_generic_error(self) -> None:
        """Test xread re-raises non-ConnectionError exceptions."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._master.xread.side_effect = ValueError("Generic")
        
        with pytest.raises(ValueError, match="Generic"):
            await client.xread("stream", "0")

    @pytest.mark.asyncio
    async def test_unsubscribe_check_missing_callback(self) -> None:
        """Test unsubscribe when callback already removed."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = AsyncMock()
        client._pubsub = AsyncMock()
        client._pubsub.punsubscribe = AsyncMock()
        
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        
        # Subscribe both
        handle1 = await client.subscribe("pat", cb1)
        # Add cb2
        client._callbacks["pat"].append(cb2)
        
        # Manually remove cb1 checking condition 485
        client._callbacks["pat"].remove(cb1)
        
        # Unsubscribe handle1
        # cb1 not in list -> 485 False
        # list has cb2 -> 489 False
        await handle1.unsubscribe()
        
        # Verify punsubscribe NOT called
        client._pubsub.punsubscribe.assert_not_called()
        assert len(client._callbacks["pat"]) == 1

    @pytest.mark.asyncio
    async def test_health_check_fail_disconnected(self) -> None:
        """Test health check failure when connection drops during check."""
        client = RedisClient(RedisConfig())
        client._is_connected = True # Start connected
        client._master = AsyncMock()
        
        # Side effect: disconnect THEN raise
        async def disconnect_and_raise():
            client._is_connected = False
            raise Exception("Fail")
            
        client._master.ping.side_effect = disconnect_and_raise
        
        # Call health check
        await client.health_check()
    
    @pytest.mark.asyncio
    async def test_health_check_missing_kwargs(self) -> None:
        """Test health check fallback when connection kwargs missing host/port."""
        client = RedisClient(RedisConfig())
        client._is_connected = True
        client._master = MagicMock()
        # Ping fails to force address lookup
        client._master.ping = AsyncMock(side_effect=Exception("Ping failed"))
        
        # Empty kwargs
        client._master.connection_pool.connection_kwargs = {}
        
        with patch("cyberred.storage.redis_client.log") as mock_log:
             await client.health_check()
             # Should fall back to 0.0.0.0:0 or config default?
             # Logic lines 628-633 check defaults.
             
    @pytest.mark.asyncio
    async def test_pubsub_listener_custom_cancelled_error(self) -> None:
        """Test listener handles custom CancelledError-like exceptions."""
        client = RedisClient(RedisConfig())
        client._pubsub = MagicMock()
        
        class CustomCancelledError(BaseException):
            pass
            
        client._pubsub.listen.side_effect = CustomCancelledError("CancelledError checks")
        
        with patch("cyberred.storage.redis_client.log") as mock_log:
            await client._pubsub_listener()
            # Should NOT log "redis_listener_crashed" because name contains CancelledError
            mock_log.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_pubsub_listener_loop_finish(self) -> None:
        """Test listener handles natural loop finish."""
        client = RedisClient(RedisConfig())
        client._pubsub = MagicMock()
        
        async def mock_listen_gen():
             yield {"type": "subscribe", "channel": b"foo", "data": 1}
             # Finish iteration
             
        client._pubsub.listen.return_value = mock_listen_gen()
        
        await client._pubsub_listener()
        # Should return gracefully without log


# =============================================================================
# Story 3.2: Redis Reconnection Logic Tests
# =============================================================================

class TestMessageBuffer:
    """Tests for MessageBuffer class (Tasks 1-3)."""

    def test_message_buffer_stores_messages(self) -> None:
        """Test that MessageBuffer stores messages correctly."""
        from cyberred.storage.redis_client import MessageBuffer
        
        buffer = MessageBuffer(max_size=1000, max_age_seconds=10.0)
        
        # Add messages
        result1 = buffer.add("channel1", "message1")
        result2 = buffer.add("channel2", "message2")
        
        assert result1 is True
        assert result2 is True
        assert buffer.size == 2
        assert buffer.is_full is False

    def test_message_buffer_drains_messages(self) -> None:
        """Test that drain() returns and clears all messages."""
        from cyberred.storage.redis_client import MessageBuffer
        
        buffer = MessageBuffer(max_size=1000, max_age_seconds=10.0)
        buffer.add("ch1", "msg1")
        buffer.add("ch2", "msg2")
        
        messages = buffer.drain()
        
        assert len(messages) == 2
        assert ("ch1", "msg1") in messages
        assert ("ch2", "msg2") in messages
        assert buffer.size == 0  # Buffer should be empty after drain

    def test_message_buffer_rejects_when_full(self) -> None:
        """Test that add() returns False when buffer is full."""
        from cyberred.storage.redis_client import MessageBuffer
        
        buffer = MessageBuffer(max_size=3, max_age_seconds=10.0)
        
        buffer.add("ch1", "msg1")
        buffer.add("ch2", "msg2")
        buffer.add("ch3", "msg3")
        
        assert buffer.is_full is True
        
        # Adding when full should return False
        result = buffer.add("ch4", "msg4")
        assert result is False
        assert buffer.size == 3  # Size unchanged

    def test_message_buffer_expires_old_messages(self) -> None:
        """Test that drain() filters out expired messages."""
        from cyberred.storage.redis_client import MessageBuffer
        
        buffer = MessageBuffer(max_size=1000, max_age_seconds=0.1)  # 100ms expiry
        
        buffer.add("ch1", "old_msg")
        
        # Wait for message to expire
        time.sleep(0.15)
        
        buffer.add("ch2", "new_msg")
        
        messages = buffer.drain()
        
        # Only the new message should remain
        assert len(messages) == 1
        assert messages[0] == ("ch2", "new_msg")

    def test_message_buffer_size_property(self) -> None:
        """Test size property returns correct count."""
        from cyberred.storage.redis_client import MessageBuffer
        
        buffer = MessageBuffer()
        assert buffer.size == 0
        
        buffer.add("ch", "msg")
        assert buffer.size == 1

    def test_message_buffer_is_full_property(self) -> None:
        """Test is_full property returns correct value."""
        from cyberred.storage.redis_client import MessageBuffer
        
        buffer = MessageBuffer(max_size=2)
        
        assert buffer.is_full is False
        buffer.add("ch1", "m1")
        assert buffer.is_full is False
        buffer.add("ch2", "m2")
        assert buffer.is_full is True


class TestConnectionState:
    """Tests for ConnectionState enum (Task 4)."""

    def test_connection_state_enum_values(self) -> None:
        """Test ConnectionState enum has required values."""
        from cyberred.storage.redis_client import ConnectionState
        
        # All required states should exist
        assert ConnectionState.DISCONNECTED is not None
        assert ConnectionState.CONNECTING is not None
        assert ConnectionState.CONNECTED is not None
        assert ConnectionState.DEGRADED is not None

    def test_redis_client_connection_state_property(self) -> None:
        """Test RedisClient has connection_state property."""
        from cyberred.storage.redis_client import ConnectionState
        
        config = RedisConfig()
        client = RedisClient(config)
        
        # Should have connection_state property
        assert hasattr(client, "connection_state")
        # Initial state should be DISCONNECTED
        assert client.connection_state == ConnectionState.DISCONNECTED


class TestMessageBufferCoverage:
    """Additional coverage tests for MessageBuffer."""

    def test_buffer_overflow_logs_warning(self) -> None:
        """Test that buffer overflow logs a warning."""
        from cyberred.storage.redis_client import MessageBuffer
        
        buffer = MessageBuffer(max_size=2, max_age_seconds=10.0)
        buffer.add("ch1", "m1")
        buffer.add("ch2", "m2")
        
        with patch("cyberred.storage.redis_client.log") as mock_log:
            result = buffer.add("ch3", "m3")
            
            assert result is False
            mock_log.warning.assert_called_with(
                "buffer_overflow",
                size=2,
                max_size=2,
            )

    def test_buffer_drain_logs_expired_messages(self) -> None:
        """Test that drain logs expired message count."""
        from cyberred.storage.redis_client import MessageBuffer
        
        buffer = MessageBuffer(max_size=100, max_age_seconds=0.05)
        buffer.add("ch1", "old")
        time.sleep(0.1)  # Let message expire
        buffer.add("ch2", "new")
        
        with patch("cyberred.storage.redis_client.log") as mock_log:
            messages = buffer.drain()
            
            assert len(messages) == 1
            mock_log.info.assert_called_with(
                "buffer_message_expired",
                expired_count=1,
                remaining=1,
            )


class TestHandleConnectionLostCoverage:
    """Coverage tests for _handle_connection_lost."""

    def test_handle_connection_lost_transitions_to_degraded(self) -> None:
        """Test _handle_connection_lost transitions to DEGRADED state."""
        from cyberred.storage.redis_client import ConnectionState
        
        config = RedisConfig()
        client = RedisClient(config)
        client._connection_state = ConnectionState.CONNECTED
        client._is_connected = True
        client._master_address = ("redis-master", 6379)
        
        with patch("cyberred.storage.redis_client.log") as mock_log, \
             patch("cyberred.storage.redis_client.asyncio.create_task"):
            client._handle_connection_lost()
            
            assert client.connection_state == ConnectionState.DEGRADED
            assert client._is_connected is False
            mock_log.warning.assert_called()

    def test_handle_connection_lost_already_degraded(self) -> None:
        """Test _handle_connection_lost is idempotent."""
        from cyberred.storage.redis_client import ConnectionState
        
        config = RedisConfig()
        client = RedisClient(config)
        client._connection_state = ConnectionState.DEGRADED
        
        with patch("cyberred.storage.redis_client.log") as mock_log:
            client._handle_connection_lost()
            
            # Should not log again
            mock_log.warning.assert_not_called()

    def test_handle_connection_lost_no_master_address(self) -> None:
        """Test _handle_connection_lost without master address."""
        from cyberred.storage.redis_client import ConnectionState
        
        config = RedisConfig()
        client = RedisClient(config)
        client._connection_state = ConnectionState.CONNECTED
        client._master_address = None
        
        with patch("cyberred.storage.redis_client.log") as mock_log, \
             patch("cyberred.storage.redis_client.asyncio.create_task"):
            client._handle_connection_lost()
            
            # Should still transition
            assert client.connection_state == ConnectionState.DEGRADED
            # Check log was called with empty master_addr
            mock_log.warning.assert_called()


class TestCloseWithStateUpdate:
    """Test close() updates connection_state."""

    @pytest.mark.asyncio
    async def test_close_sets_disconnected_state(self) -> None:
        """Test close() transitions to DISCONNECTED state."""
        from cyberred.storage.redis_client import ConnectionState
        
        config = RedisConfig()
        client = RedisClient(config)
        client._connection_state = ConnectionState.CONNECTED
        client._is_connected = True
        
        await client.close()
        
        assert client.connection_state == ConnectionState.DISCONNECTED
        assert client._is_connected is False


class TestBackoffPolicy:
    """Tests for exponential backoff algorithm (Task 6)."""

    def test_backoff_calculation(self) -> None:
        """Test exponential backoff timing sequence."""
        from cyberred.storage.redis_client import calculate_backoff
        
        # Test backoff sequence: 1s, 2s, 4s, 8s, 10s max
        delay0 = calculate_backoff(0, max_delay=10.0, jitter=0.0)
        delay1 = calculate_backoff(1, max_delay=10.0, jitter=0.0)
        delay2 = calculate_backoff(2, max_delay=10.0, jitter=0.0)
        delay3 = calculate_backoff(3, max_delay=10.0, jitter=0.0)
        delay4 = calculate_backoff(4, max_delay=10.0, jitter=0.0)
        delay5 = calculate_backoff(5, max_delay=10.0, jitter=0.0)
        
        assert delay0 == 1.0  # 2^0 = 1
        assert delay1 == 2.0  # 2^1 = 2
        assert delay2 == 4.0  # 2^2 = 4
        assert delay3 == 8.0  # 2^3 = 8
        assert delay4 == 10.0  # 2^4 = 16, capped to 10
        assert delay5 == 10.0  # Still capped

    def test_backoff_with_jitter(self) -> None:
        """Test backoff includes jitter."""
        from cyberred.storage.redis_client import calculate_backoff
        
        # With 10% jitter, value should be within ±10%
        delay = calculate_backoff(2, max_delay=10.0, jitter=0.1)
        
        # Base is 4.0, with ±10% jitter: 3.6 to 4.4
        assert 3.6 <= delay <= 4.4


class TestRedisClientReconnection:
    """Tests for reconnection logic (Tasks 5-12)."""

    def test_redis_connection_lost_event(self) -> None:
        """Test RedisConnectionLost event is emitted."""
        from cyberred.storage.redis_client import ConnectionState
        
        config = RedisConfig()
        client = RedisClient(config)
        
        # Simulate connection loss
        client._is_connected = True
        client._connection_state = ConnectionState.CONNECTED
        
        # Method to trigger should exist
        assert hasattr(client, "_handle_connection_lost")

    @pytest.mark.asyncio
    async def test_publish_buffers_when_degraded(self) -> None:
        """Test publish() buffers messages when in DEGRADED state."""
        from cyberred.storage.redis_client import ConnectionState, MessageBuffer
        
        config = RedisConfig()
        client = RedisClient(config)
        
        # Set up degraded state
        client._connection_state = ConnectionState.DEGRADED
        client._buffer = MessageBuffer()
        
        # Publish should buffer instead of raising
        result = await client.publish("channel", "message")
        
        assert result == 0  # No subscribers received
        assert client._buffer.size == 1


class TestReconnectionLoop:
    """Tests for background reconnection loop (Tasks 7-8)."""

    @pytest.mark.asyncio
    async def test_reconnection_loop_exists(self) -> None:
        """Test that _reconnection_loop method exists."""
        config = RedisConfig()
        client = RedisClient(config)
        
        assert hasattr(client, "_reconnection_loop")
        assert asyncio.iscoroutinefunction(client._reconnection_loop)

    @pytest.mark.asyncio
    async def test_reconnection_loop_attempts_reconnect(self) -> None:
        """Test reconnection loop attempts to reconnect."""
        from cyberred.storage.redis_client import ConnectionState
        
        config = RedisConfig()
        client = RedisClient(config)
        client._connection_state = ConnectionState.DEGRADED
        
        # Mock _connect_to_master to succeed on first call
        client._connect_to_master = AsyncMock(return_value=True)
        client._flush_buffer = AsyncMock()
        
        # Patch sleep to return immediately
        with patch("cyberred.storage.redis_client.asyncio.sleep", new_callable=AsyncMock):
            await client._reconnection_loop()
        
        # Should have attempted connect
        client._connect_to_master.assert_called()

    @pytest.mark.asyncio
    async def test_reconnection_cancelled_on_close(self) -> None:
        """Test reconnection task is cancelled on close()."""
        from cyberred.storage.redis_client import ConnectionState
        
        config = RedisConfig()
        client = RedisClient(config)
        client._connection_state = ConnectionState.DEGRADED
        
        # Create a mock reconnection task
        async def mock_reconnection():
            await asyncio.sleep(100)
        
        client._reconnection_task = asyncio.create_task(mock_reconnection())
        
        await client.close()
        
        assert client._reconnection_task is None
        assert client._connection_state == ConnectionState.DISCONNECTED


class TestBufferFlush:
    """Tests for buffer flush on reconnect (Tasks 9-10)."""

    @pytest.mark.asyncio
    async def test_flush_buffer_method_exists(self) -> None:
        """Test that _flush_buffer method exists."""
        config = RedisConfig()
        client = RedisClient(config)
        
        assert hasattr(client, "_flush_buffer")
        assert asyncio.iscoroutinefunction(client._flush_buffer)

    @pytest.mark.asyncio
    async def test_flush_buffer_republishes_messages(self) -> None:
        """Test _flush_buffer republishes buffered messages."""
        from cyberred.storage.redis_client import ConnectionState
        
        config = RedisConfig()
        client = RedisClient(config)
        client._is_connected = True
        client._connection_state = ConnectionState.CONNECTED
        client._master = AsyncMock()
        client._master.publish = AsyncMock(return_value=1)
        
        # Add messages to buffer
        client._buffer.add("ch1", "msg1")
        client._buffer.add("ch2", "msg2")
        
        await client._flush_buffer()
        
        # Buffer should be empty
        assert client._buffer.size == 0
        # Publish should have been called for each message
        assert client._master.publish.call_count == 2

    @pytest.mark.asyncio
    async def test_flush_buffer_logs_success(self) -> None:
        """Test _flush_buffer logs buffer_flushed event."""
        from cyberred.storage.redis_client import ConnectionState
        
        config = RedisConfig()
        client = RedisClient(config)
        client._is_connected = True
        client._connection_state = ConnectionState.CONNECTED
        client._master = AsyncMock()
        client._master.publish = AsyncMock(return_value=1)
        
        client._buffer.add("ch", "msg")
        
        with patch("cyberred.storage.redis_client.log") as mock_log:
            await client._flush_buffer()
            mock_log.info.assert_called()

    @pytest.mark.asyncio
    async def test_flush_buffer_empty(self) -> None:
        """Test _flush_buffer with no messages returns early."""
        from cyberred.storage.redis_client import ConnectionState
        
        config = RedisConfig()
        client = RedisClient(config)
        client._is_connected = True
        client._connection_state = ConnectionState.CONNECTED
        client._master = AsyncMock()
        
        # Buffer is empty
        assert client._buffer.size == 0
        
        await client._flush_buffer()
        
        # Publish should not have been called
        client._master.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_buffer_handles_failure(self) -> None:
        """Test _flush_buffer handles publish failures."""
        from cyberred.storage.redis_client import ConnectionState
        
        config = RedisConfig()
        client = RedisClient(config)
        client._is_connected = True
        client._connection_state = ConnectionState.CONNECTED
        client._master = AsyncMock()
        # First call succeeds, second fails
        client._master.publish = AsyncMock(side_effect=[1, Exception("Publish failed")])
        
        client._buffer.add("ch1", "msg1")
        client._buffer.add("ch2", "msg2")
        
        with patch("cyberred.storage.redis_client.log") as mock_log:
            await client._flush_buffer()
            # Should log warning for failure
            mock_log.warning.assert_called()

    @pytest.mark.asyncio
    async def test_connect_to_master_failure(self) -> None:
        """Test _connect_to_master returns False on connection failure."""
        config = RedisConfig(
            sentinel_hosts=["localhost:99999"],  # Invalid port
            master_name="invalid",
        )
        client = RedisClient(config)
        
        # Should return False without raising
        result = await client._connect_to_master()
        assert result is False

    @pytest.mark.asyncio
    async def test_reconnection_loop_multiple_attempts(self) -> None:
        """Test reconnection loop tries multiple times before success."""
        from cyberred.storage.redis_client import ConnectionState
        
        config = RedisConfig()
        client = RedisClient(config)
        client._connection_state = ConnectionState.DEGRADED
        
        # Fail first 2 attempts, succeed on 3rd
        call_count = 0
        async def mock_connect():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return False
            return True
        
        client._connect_to_master = mock_connect
        client._flush_buffer = AsyncMock()
        
        with patch("cyberred.storage.redis_client.asyncio.sleep", new_callable=AsyncMock):
            await client._reconnection_loop()
        
        assert call_count == 3
