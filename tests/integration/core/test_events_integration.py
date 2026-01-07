"""Integration tests for EventBus with Redis Sentinel.

Tests the EventBus wrapper with real Redis via testcontainers.
Verifies NFR1: Agent coordination latency <1s stigmergic propagation.
"""

import asyncio
import json
import time

import pytest


@pytest.fixture(scope="function")
def redis_container():
    """Provide a real Redis container for integration tests."""
    from testcontainers.redis import RedisContainer

    container = RedisContainer("redis:7-alpine")
    container.start()

    yield container

    container.stop()


@pytest.fixture
def redis_config(redis_container):
    """Create RedisConfig from testcontainer."""
    from cyberred.core.config import RedisConfig

    host = redis_container.get_container_host_ip()
    port = int(redis_container.get_exposed_port(6379))

    # Create config for standalone Redis (not Sentinel for unit integration)
    return RedisConfig(
        host=host,
        port=port,
        sentinel_hosts=[],  # Empty for standalone
        master_name="mymaster",
    )


@pytest.fixture
async def event_bus(redis_config):
    """Create EventBus with RedisClient connected to test Redis."""
    from cyberred.core.events import EventBus
    from cyberred.storage.redis_client import RedisClient

    client = RedisClient(redis_config, engagement_id="test-engagement")
    await client.connect()

    event_bus = EventBus(client)

    yield event_bus

    await client.close()


@pytest.mark.integration
class TestEventBusIntegration:
    """Integration tests for EventBus with real Redis."""

    @pytest.mark.asyncio
    async def test_event_bus_pubsub_round_trip_latency(self, event_bus):
        """Verify pub/sub round-trip latency <1s (NFR1).
        
        Task 11: Integration Test: Round-Trip Latency (AC: #9)
        """
        received_future = asyncio.get_event_loop().create_future()
        publish_time = None

        async def callback(channel: str, message: str):
            if not received_future.done():
                received_future.set_result((time.perf_counter(), channel, message))

        # Subscribe
        subscription = await event_bus.subscribe("control:*", callback)

        # Give subscription time to register
        await asyncio.sleep(0.1)

        # Publish
        publish_time = time.perf_counter()
        await event_bus.publish("control:test", {"msg": "latency_test"})

        # Wait for callback
        try:
            recv_time, recv_channel, recv_message = await asyncio.wait_for(
                received_future, timeout=2.0
            )
            latency_ms = (recv_time - publish_time) * 1000

            # NFR1: latency must be <1000ms
            assert latency_ms < 1000, f"Latency {latency_ms}ms exceeds NFR1 threshold"
            assert recv_channel == "control:test"
            assert json.loads(recv_message)["msg"] == "latency_test"
        finally:
            await subscription.unsubscribe()

    @pytest.mark.asyncio
    async def test_event_bus_concurrent_subscriptions(self, event_bus):
        """Verify concurrent subscriptions work correctly.
        
        Task 12: Integration Test: Concurrent Subscribers (AC: #7, #9)
        """
        # Track received messages per pattern
        received = {f"control:test{i}": asyncio.Event() for i in range(5)}
        messages = {}

        async def make_callback(pattern_key):
            async def callback(channel: str, message: str):
                messages[pattern_key] = message
                received[pattern_key].set()
            return callback

        # Subscribe to 5 patterns concurrently
        subscriptions = []
        for i in range(5):
            pattern_key = f"control:test{i}"
            callback = await make_callback(pattern_key)
            sub = await event_bus.subscribe(f"control:test{i}", callback)
            subscriptions.append(sub)

        # Give subscriptions time to register
        await asyncio.sleep(0.2)

        # Publish to each channel
        for i in range(5):
            await event_bus.publish(f"control:test{i}", f"msg{i}")

        # Wait for all to be received
        try:
            await asyncio.wait_for(
                asyncio.gather(*[e.wait() for e in received.values()]),
                timeout=3.0
            )

            # Verify all messages received
            for i in range(5):
                assert f"control:test{i}" in messages
                assert messages[f"control:test{i}"] == f"msg{i}"
        finally:
            for sub in subscriptions:
                await sub.unsubscribe()

    @pytest.mark.asyncio
    async def test_event_bus_hmac_enforcement(self, event_bus, redis_config):
        """Verify HMAC enforcement - tampered messages are dropped.
        
        Task 13: Integration Test: HMAC End-to-End (AC: #8)
        """
        import redis.asyncio as aioredis

        valid_received = asyncio.Event()
        tampered_received = asyncio.Event()

        async def callback(channel: str, message: str):
            if "valid" in message:
                valid_received.set()
            elif "tampered" in message:
                tampered_received.set()

        # Subscribe via EventBus (signature validation enabled)
        subscription = await event_bus.subscribe("control:*", callback)

        await asyncio.sleep(0.1)

        # Test 1: Publish valid message through EventBus (should work)
        await event_bus.publish("control:hmactest", '{"msg": "valid"}')

        # Wait for valid message
        try:
            await asyncio.wait_for(valid_received.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pytest.fail("Valid message was not received")

        # Test 2: Publish tampered message directly via raw Redis (should be dropped)
        # Connect directly to Redis bypassing EventBus/RedisClient
        raw_redis = aioredis.from_url(
            f"redis://{redis_config.host}:{redis_config.port}",
            decode_responses=True
        )

        try:
            # Publish raw message without proper HMAC signature
            await raw_redis.publish("control:hmactest", '{"msg": "tampered", "signature": "invalid"}')

            # The tampered message should NOT be received
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(tampered_received.wait(), timeout=0.5)
        finally:
            await raw_redis.close()
            await subscription.unsubscribe()

    @pytest.mark.asyncio
    async def test_event_bus_finding_publication(self, event_bus):
        """Verify finding publication helper works end-to-end."""
        import hashlib

        received_future = asyncio.get_event_loop().create_future()

        async def callback(channel: str, message: str):
            if not received_future.done():
                received_future.set_result((channel, message))

        # Subscribe to findings channel
        subscription = await event_bus.subscribe("findings:*", callback)

        await asyncio.sleep(0.1)

        # Create mock finding
        class TestFinding:
            target = "scanme.nmap.org"
            type = "openport"  # Changed to alphanumeric
            id = "finding-123"

            def to_dict(self):
                return {"id": self.id, "target": self.target, "type": self.type}

        finding = TestFinding()
        await event_bus.publish_finding(finding)

        try:
            channel, message = await asyncio.wait_for(received_future, timeout=2.0)

            # Verify channel format
            target_hash = hashlib.sha256(finding.target.encode()).hexdigest()[:8]
            expected_channel = f"findings:{target_hash}:{finding.type}"
            assert channel == expected_channel

            # Verify payload
            data = json.loads(message)
            assert data["id"] == "finding-123"
            assert data["target"] == "scanme.nmap.org"
        finally:
            await subscription.unsubscribe()

    @pytest.mark.asyncio
    async def test_event_bus_agent_status_publication(self, event_bus):
        """Verify agent status publication helper works end-to-end."""
        received_future = asyncio.get_event_loop().create_future()

        async def callback(channel: str, message: str):
            if not received_future.done():
                received_future.set_result((channel, message))

        # Subscribe to agent status
        subscription = await event_bus.subscribe("agents:*", callback)

        await asyncio.sleep(0.1)

        status = {"state": "running", "task": "scanning", "timestamp": "2026-01-04T12:00:00Z"}
        await event_bus.publish_agent_status("agent001", status)  # Changed to alphanumeric only

        try:
            channel, message = await asyncio.wait_for(received_future, timeout=2.0)

            assert channel == "agents:agent001:status"
            data = json.loads(message)
            assert data["state"] == "running"
            assert data["task"] == "scanning"
        finally:
            await subscription.unsubscribe()

    @pytest.mark.asyncio
    async def test_event_bus_kill_switch_integration(self, event_bus):
        """Verify kill switch subscription works end-to-end."""
        received_reason = asyncio.get_event_loop().create_future()

        async def kill_handler(reason: str):
            if not received_reason.done():
                received_reason.set_result(reason)

        # Subscribe to kill switch
        subscription = await event_bus.subscribe_kill_switch(kill_handler)

        await asyncio.sleep(0.1)

        # Publish kill signal
        await event_bus.publish("control:kill", {"reason": "emergency_stop"})

        try:
            reason = await asyncio.wait_for(received_reason, timeout=2.0)
            assert reason == "emergency_stop"
        finally:
            await subscription.unsubscribe()

    @pytest.mark.asyncio
    async def test_event_bus_health_check_integration(self, event_bus):
        """Verify health check works with real Redis."""
        result = await event_bus.health_check()

        assert result.healthy is True
        assert result.latency_ms < 100  # Should be fast for local Redis
        assert result.master_addr is not None
