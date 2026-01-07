"""Integration tests for Redis Sentinel client.

Tests RedisClient with real Redis using testcontainers (NO MOCKS policy).
"""

import pytest
from cyberred.core.config import RedisConfig
from cyberred.storage.redis_client import RedisClient


# Import fixture
pytest_plugins = ["tests.fixtures.redis_container"]


@pytest.mark.integration
class TestRedisClientIntegration:
    """Integration tests for RedisClient with real Redis."""

    @pytest.mark.asyncio
    async def test_redis_client_connect_and_close(self, redis_container) -> None:
        """Test connecting to real Redis and closing gracefully."""
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        client = RedisClient(config, engagement_id="test-engagement")
        
        assert not client.is_connected
        
        await client.connect()
        assert client.is_connected
        
        await client.close()
        assert not client.is_connected

    @pytest.mark.asyncio
    async def test_redis_client_connect_idempotent(self, redis_container) -> None:
        """Test that connect() is idempotent (can be called multiple times)."""
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        client = RedisClient(config, engagement_id="test-engagement")
        
        # First connect
        await client.connect()
        assert client.is_connected
        
        # Second connect should be no-op (idempotent)
        await client.connect()  # Should not raise
        assert client.is_connected
        
        await client.close()

    @pytest.mark.asyncio
    async def test_redis_client_async_context_manager(self, redis_container) -> None:
        """Test async context manager connects and closes properly."""
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        
        async with RedisClient(config, engagement_id="test-engagement") as client:
            assert client.is_connected
        
        # After exiting context, should be disconnected
        assert not client.is_connected

    @pytest.mark.asyncio
    async def test_redis_client_publish(self, redis_container) -> None:
        """Test publishing messages to Redis channels."""
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        
        async with RedisClient(config, engagement_id="test-engagement") as client:
            # Publish with no subscribers should return 0
            result = await client.publish("test:channel", "hello world")
            assert result == 0  # No subscribers yet

    @pytest.mark.asyncio
    async def test_redis_client_xadd_and_xread(self, redis_container) -> None:
        """Test Redis Streams xadd and xread operations."""
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        
        async with RedisClient(config, engagement_id="test-engagement") as client:
            # Add entries to stream
            entry_id1 = await client.xadd("test:stream", {"field1": "value1"})
            entry_id2 = await client.xadd("test:stream", {"field2": "value2"})
            
            assert entry_id1 is not None
            assert entry_id2 is not None
            assert entry_id1 != entry_id2
            
            # Read from stream (now returns verified (id, data) tuples)
            results = await client.xread("test:stream", "0", count=10)
            
            assert len(results) > 0
            # Results are (entry_id, data_dict) tuples

    @pytest.mark.asyncio
    async def test_redis_client_xadd_with_maxlen(self, redis_container) -> None:
        """Test Redis Streams xadd with maxlen trimming."""
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        
        async with RedisClient(config, engagement_id="test-engagement") as client:
            # Add multiple entries with maxlen
            # xadd uses exact trimming (approximate=False)
            for i in range(20):
                await client.xadd("test:limited", {"seq": str(i)}, maxlen=10)
            
            # Read all entries - should be exactly maxlen
            results = await client.xread("test:limited", "0", count=100)
            
            # New format returns list of (id, data) tuples
            assert len(results) == 10  # Exact trimming

    @pytest.mark.asyncio
    async def test_redis_client_subscribe(self, redis_container) -> None:
        """Test subscribing to Redis channels."""
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        
        async with RedisClient(config, engagement_id="test-engagement") as client:
            import asyncio
            received = asyncio.Event()
            received_msg = {"channel": "", "content": ""}

            async def callback(channel: str, message: str) -> None:
                received_msg["channel"] = channel
                received_msg["content"] = message
                received.set()
            
            subscription = await client.subscribe("test:*", callback)
            
            assert subscription is not None
            assert subscription.pattern == "test:*"
            
            # Publish to a channel matching pattern
            # Using a second client to publish (to ensure real round-trip)
            async with RedisClient(config, engagement_id="test-engagement") as pub_client:
                await pub_client.publish("test:msg", "hello callback")
            
            # Wait for callback
            try:
                await asyncio.wait_for(received.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pytest.fail("Callback was not invoked within timeout")
            
            assert received_msg["channel"] == "test:msg"
            assert received_msg["content"] == "hello callback"

            # Unsubscribe
            await subscription.unsubscribe()

    @pytest.mark.asyncio
    async def test_redis_client_health_check(self, redis_container) -> None:
        """Test health check returns valid status."""
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        
        async with RedisClient(config, engagement_id="test-engagement") as client:
            status = await client.health_check()
            
            assert status.healthy is True
            assert status.latency_ms > 0
            assert status.master_addr != ""

    @pytest.mark.asyncio
    async def test_redis_client_health_check_disconnected(self, redis_container) -> None:
        """Test health check returns unhealthy when not connected."""
        config = RedisConfig(host="localhost", port=6379)
        client = RedisClient(config, engagement_id="test-engagement")
        
        # Don't connect - check health returns unhealthy
        status = await client.health_check()
        
        assert status.healthy is False
        assert status.latency_ms == 0.0
        assert status.master_addr == ""


@pytest.mark.integration
class TestRedisClientSentinelIntegration:
    """Integration tests for RedisClient with Redis Sentinel cluster.
    
    These tests require the docker-compose-redis-sentinel.yaml cluster running:
        docker compose -f tests/fixtures/docker-compose-redis-sentinel.yaml up -d
    """

    @pytest.fixture
    def sentinel_config(self) -> RedisConfig:
        """Provide config for Sentinel cluster (assumes docker-compose is running)."""
        return RedisConfig(
            host="localhost",
            port=6379,
            sentinel_hosts=["localhost:26379", "localhost:26380", "localhost:26381"],
            master_name="mymaster",
        )

    @pytest.mark.asyncio
    async def test_redis_client_connects_via_sentinel(self, sentinel_config) -> None:
        """Test connecting to Redis via Sentinel cluster."""
        client = RedisClient(sentinel_config, engagement_id="test-engagement")
        
        try:
            await client.connect()
            assert client.is_connected
            
            # Verify we can perform operations
            result = await client.publish("test:sentinel", "hello from sentinel")
            assert result >= 0  # May have 0 subscribers
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_redis_client_sentinel_health_check(self, sentinel_config) -> None:
        """Test health check through Sentinel connection."""
        async with RedisClient(sentinel_config, engagement_id="test-engagement") as client:
            status = await client.health_check()
            
            assert status.healthy is True
            assert status.latency_ms > 0

    @pytest.mark.asyncio
    async def test_redis_client_sentinel_pubsub(self, sentinel_config) -> None:
        """Test pub/sub through Sentinel connection."""
        async with RedisClient(sentinel_config, engagement_id="test-engagement") as client:
            async def callback(channel: str, message: str) -> None:
                pass
            
            subscription = await client.subscribe("test:sentinel:*", callback)
            assert subscription.pattern == "test:sentinel:*"
            
            await subscription.unsubscribe()

    @pytest.mark.asyncio
    async def test_redis_client_sentinel_streams(self, sentinel_config) -> None:
        """Test Redis Streams through Sentinel connection."""
        async with RedisClient(sentinel_config, engagement_id="test-engagement") as client:
            # Add to stream
            entry_id = await client.xadd("sentinel:stream", {"msg": "hello"})
            assert entry_id is not None
            
            # Read from stream
            results = await client.xread("sentinel:stream", "0", count=10)
            assert len(results) > 0


@pytest.mark.integration
class TestRedisClientReconnectionIntegration:
    """Integration tests for Story 3.2 reconnection logic.
    
    These tests require the docker-compose-redis-sentinel.yaml cluster running:
        docker compose -f tests/fixtures/docker-compose-redis-sentinel.yaml up -d
    """

    @pytest.fixture
    def sentinel_config(self) -> RedisConfig:
        """Provide config for Sentinel cluster."""
        return RedisConfig(
            host="localhost",
            port=6379,
            sentinel_hosts=["localhost:26379", "localhost:26380", "localhost:26381"],
            master_name="mymaster",
        )

    @pytest.mark.asyncio
    async def test_connection_state_transitions(self, sentinel_config) -> None:
        """Test connection state machine transitions correctly."""
        from cyberred.storage.redis_client import ConnectionState
        
        client = RedisClient(sentinel_config, engagement_id="test-reconnection")
        
        # Initial state is DISCONNECTED
        assert client.connection_state == ConnectionState.DISCONNECTED
        
        # After connect, should be CONNECTED
        await client.connect()
        assert client.connection_state == ConnectionState.CONNECTED
        assert client.is_connected
        
        # After close, should be DISCONNECTED
        await client.close()
        assert client.connection_state == ConnectionState.DISCONNECTED
        assert not client.is_connected

    @pytest.mark.asyncio
    async def test_message_buffer_integration(self, sentinel_config) -> None:
        """Test MessageBuffer stores and drains messages correctly."""
        from cyberred.storage.redis_client import MessageBuffer
        
        buffer = MessageBuffer(max_size=100, max_age_seconds=10.0)
        
        # Add messages
        buffer.add("ch1", "msg1")
        buffer.add("ch2", "msg2")
        buffer.add("ch3", "msg3")
        
        assert buffer.size == 3
        assert not buffer.is_full
        
        # Drain returns all messages and clears buffer
        messages = buffer.drain()
        assert len(messages) == 3
        assert buffer.size == 0

    @pytest.mark.asyncio
    async def test_publish_buffers_when_degraded(self, sentinel_config) -> None:
        """Test publish() buffers messages in DEGRADED state."""
        from cyberred.storage.redis_client import ConnectionState
        
        client = RedisClient(sentinel_config, engagement_id="test-buffer")
        
        # Connect first
        await client.connect()
        assert client.connection_state == ConnectionState.CONNECTED
        
        # Manually transition to DEGRADED
        client._handle_connection_lost()
        assert client.connection_state == ConnectionState.DEGRADED
        
        # Publish should buffer (not raise)
        result = await client.publish("test:buffered", "message in buffer")
        assert result == 0  # Buffered, not delivered
        assert client._buffer.size == 1
        
        await client.close()

    @pytest.mark.asyncio
    async def test_buffer_flush_on_reconnect(self, sentinel_config) -> None:
        """Test buffered messages are flushed on reconnection."""
        from cyberred.storage.redis_client import ConnectionState
        
        client = RedisClient(sentinel_config, engagement_id="test-flush")
        
        # Connect
        await client.connect()
        
        # Add messages to buffer manually
        client._buffer.add("test:flush1", "msg1")
        client._buffer.add("test:flush2", "msg2")
        assert client._buffer.size == 2
        
        # Call flush
        await client._flush_buffer()
        
        # Buffer should be empty
        assert client._buffer.size == 0
        
        await client.close()

    @pytest.mark.asyncio
    async def test_backoff_calculation(self) -> None:
        """Test exponential backoff calculation."""
        from cyberred.storage.redis_client import calculate_backoff
        
        # Test sequence without jitter
        assert calculate_backoff(0, jitter=0.0) == 1.0  # 2^0
        assert calculate_backoff(1, jitter=0.0) == 2.0  # 2^1
        assert calculate_backoff(2, jitter=0.0) == 4.0  # 2^2
        assert calculate_backoff(3, jitter=0.0) == 8.0  # 2^3
        assert calculate_backoff(4, jitter=0.0) == 10.0  # Capped at max_delay
        
        # With jitter, should be within ±10%
        value = calculate_backoff(2, jitter=0.1)
        assert 3.6 <= value <= 4.4

    @pytest.mark.asyncio
    async def test_reconnection_loop_recovers(self, sentinel_config) -> None:
        """Test reconnection loop successfully reconnects."""
        import asyncio
        from cyberred.storage.redis_client import ConnectionState
        from unittest.mock import AsyncMock, patch
        
        client = RedisClient(sentinel_config, engagement_id="test-reconnect-loop")
        
        # Connect first
        await client.connect()
        assert client.connection_state == ConnectionState.CONNECTED
        
        # Simulate degraded state
        client._handle_connection_lost()
        assert client.connection_state == ConnectionState.DEGRADED
        
        # Mock sleep to run faster
        with patch("cyberred.storage.redis_client.asyncio.sleep", new_callable=AsyncMock):
            await client._reconnection_loop()
        
        # Should have reconnected
        assert client.connection_state == ConnectionState.CONNECTED
        
        await client.close()

    @pytest.mark.asyncio
    async def test_close_cancels_reconnection_task(self, sentinel_config) -> None:
        """Test close() properly cancels any running reconnection task."""
        import asyncio
        from cyberred.storage.redis_client import ConnectionState
        
        client = RedisClient(sentinel_config, engagement_id="test-cancel")
        
        # Create a mock reconnection task
        async def slow_reconnect():
            await asyncio.sleep(1000)
        
        client._reconnection_task = asyncio.create_task(slow_reconnect())
        client._connection_state = ConnectionState.DEGRADED
        
        # Close should cancel the task
        await client.close()
        
        assert client._reconnection_task is None
        assert client.connection_state == ConnectionState.DISCONNECTED
