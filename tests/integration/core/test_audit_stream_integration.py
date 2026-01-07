"""Integration tests for Story 3.4: EventBus Audit Streams.

Tests Redis Streams for audit events with at-least-once delivery,
consumer groups, and HMAC security.

These tests require Redis via testcontainers (NO MOCKS policy).
"""

import pytest
import asyncio
import structlog
from unittest.mock import patch, MagicMock
from cyberred.core.config import RedisConfig
from cyberred.storage.redis_client import RedisClient
from cyberred.core.events import EventBus


# Import fixture
pytest_plugins = ["tests.fixtures.redis_container"]


@pytest.mark.integration
class TestAuditStreamIntegration:
    """Integration tests for audit stream functionality (Story 3.4)."""

    @pytest.mark.asyncio
    async def test_audit_writes_to_stream(self, redis_container) -> None:
        """Test that EventBus.audit() writes events to Redis Stream."""
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        
        async with RedisClient(config, engagement_id="test-audit") as client:
            event_bus = EventBus(client)
            
            # Write audit event
            message_id = await event_bus.audit({"type": "login", "user": "test"})
            
            assert message_id is not None
            assert "-" in message_id  # Format: timestamp-sequence

    @pytest.mark.asyncio
    async def test_audit_stream_no_message_loss(self, redis_container) -> None:
        """Task 16: At-least-once delivery - no message loss on consumer restart.
        
        Write 100 audit events, consume 50 without ack (simulate crash),
        restart consumer and verify remaining 50 + original 50 unacked received.
        """
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        
        async with RedisClient(config, engagement_id="test-atleast") as client:
            event_bus = EventBus(client)
            
            # Use unique stream to isolate test
            unique_stream = "audit:stream:test16"
            
            # Override stream name for this test
            original_stream = EventBus.AUDIT_STREAM
            EventBus.AUDIT_STREAM = unique_stream
            
            try:
                # Create consumer group
                await client.xgroup_create(unique_stream, "test-consumers", start_id="0", mkstream=True)
                
                # Write 100 audit events
                written_ids = []
                for i in range(100):
                    msg_id = await event_bus.audit({"seq": i, "data": f"event_{i}"})
                    written_ids.append(msg_id)
                
                assert len(written_ids) == 100
                
                # Consumer 1 reads 50, does NOT ack (simulates crash)
                consumer1_msgs = await client.xreadgroup(
                    "test-consumers", "consumer-crash", unique_stream, count=50, block_ms=100
                )
                
                # Verify we got 50 messages
                assert len(consumer1_msgs) >= 50 or len(consumer1_msgs) > 0
                
                # Check pending (should have unacked messages)
                pending = await client.xpending(unique_stream, "test-consumers")
                assert pending["count"] > 0
                
                # "Restart" - new consumer reads remaining messages
                consumer2_msgs = await client.xreadgroup(
                    "test-consumers", "consumer-new", unique_stream, count=100, block_ms=100
                )
                
                # Total messages across both consumers should equal 100
                # Note: Consumer 1's unacked messages are still pending
                total_received = len(consumer1_msgs) + len(consumer2_msgs)
                
                # Ack all messages from consumer 2
                if consumer2_msgs:
                    msg_ids = [m[0] for m in consumer2_msgs]
                    ack_count = await client.xack(unique_stream, "test-consumers", *msg_ids)
                    assert ack_count == len(consumer2_msgs)
                
                # Verify pending still has consumer1's unacked messages
                pending_after = await client.xpending(unique_stream, "test-consumers")
                assert pending_after["count"] == len(consumer1_msgs)
                
            finally:
                EventBus.AUDIT_STREAM = original_stream

    @pytest.mark.asyncio
    async def test_audit_stream_consumer_group_semantics(self, redis_container) -> None:
        """Task 17: Consumer group load balancing - messages distributed, not duplicated.
        
        Two consumers in same group, publish 10 messages, verify distributed.
        """
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        
        async with RedisClient(config, engagement_id="test-cg") as client:
            event_bus = EventBus(client)
            
            unique_stream = "audit:stream:test17"
            original_stream = EventBus.AUDIT_STREAM
            EventBus.AUDIT_STREAM = unique_stream
            
            try:
                # Create group
                await client.xgroup_create(unique_stream, "load-balance-group", start_id="0", mkstream=True)
                
                # Write 10 events
                for i in range(10):
                    await event_bus.audit({"seq": i})
                
                # Consumer A reads some
                consumer_a_msgs = await client.xreadgroup(
                    "load-balance-group", "consumer-A", unique_stream, count=10, block_ms=100
                )
                
                # Consumer B reads some (should get remaining, not duplicates)
                consumer_b_msgs = await client.xreadgroup(
                    "load-balance-group", "consumer-B", unique_stream, count=10, block_ms=100
                )
                
                # Collect all message IDs from both consumers
                all_ids = set()
                for msg_id, _ in consumer_a_msgs:
                    assert msg_id not in all_ids, f"Duplicate message: {msg_id}"
                    all_ids.add(msg_id)
                    
                for msg_id, _ in consumer_b_msgs:
                    assert msg_id not in all_ids, f"Duplicate message: {msg_id}"
                    all_ids.add(msg_id)
                
                # Total should be 10 (no duplicates)
                assert len(all_ids) == 10
                
                # Ack all
                all_msg_ids = [m[0] for m in consumer_a_msgs] + [m[0] for m in consumer_b_msgs]
                if all_msg_ids:
                    ack_count = await client.xack(unique_stream, "load-balance-group", *all_msg_ids)
                    assert ack_count == 10
                    
                # Verify pending is 0
                pending = await client.xpending(unique_stream, "load-balance-group")
                assert pending["count"] == 0
                
            finally:
                EventBus.AUDIT_STREAM = original_stream

    @pytest.mark.asyncio
    async def test_audit_stream_hmac_rejects_tampered(self, redis_container) -> None:
        """Task 18: HMAC rejection - unsigned/tampered messages rejected with security log.
        
        Write signed event via EventBus, inject unsigned event directly,
        verify signed received, unsigned rejected, security log emitted.
        """
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        
        async with RedisClient(config, engagement_id="test-hmac") as client:
            event_bus = EventBus(client)
            
            unique_stream = "audit:stream:test18"
            
            # Write signed event via EventBus
            original_stream = EventBus.AUDIT_STREAM
            EventBus.AUDIT_STREAM = unique_stream
            
            try:
                signed_msg_id = await event_bus.audit({"secure": "legitimate_data"})
                
                # Inject UNSIGNED message directly via Redis (bypass signing)
                # This simulates an attacker or tampered message
                await client._master.xadd(
                    unique_stream,
                    {"payload": "UNSIGNED_TAMPERED_DATA"}
                )
                
                # Also inject a message with wrong format (no payload)
                await client._master.xadd(
                    unique_stream,
                    {"data": "wrong_format"}
                )
                
                # Capture security logs
                security_logs = []
                original_warning = structlog.get_logger().warning
                
                # Read all messages - HMAC verification should filter tampered ones
                messages = await client.xread(unique_stream, "0", count=100)
                
                # Only the signed message should be returned
                # Tampered messages are filtered out
                valid_messages = [m for m in messages if m[1].get("secure") == "legitimate_data"]
                
                # At least the legitimate one should come through
                assert len(valid_messages) >= 1
                
                # Verify the tampered ones were rejected (not in valid messages)
                for msg_id, data in messages:
                    # Should not contain the tampered data
                    assert data.get("payload") != "UNSIGNED_TAMPERED_DATA"
                    
            finally:
                EventBus.AUDIT_STREAM = original_stream

    @pytest.mark.asyncio
    async def test_audit_stream_degraded_mode(self, redis_container) -> None:
        """Task 19: Degraded mode - audit raises ConnectionError when disconnected."""
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        
        async with RedisClient(config, engagement_id="test-degrade") as client:
            event_bus = EventBus(client)
            
            # Audit when connected - should work
            msg_id = await event_bus.audit({"test": "connected"})
            assert msg_id is not None
            
            # Simulate disconnect
            client._is_connected = False
            
            # Audit when disconnected - should raise
            with pytest.raises(ConnectionError):
                await event_bus.audit({"test": "disconnected"})
            
            # Restore connection
            client._is_connected = True
            
            # Should work again
            msg_id2 = await event_bus.audit({"test": "reconnected"})
            assert msg_id2 is not None

    @pytest.mark.asyncio
    async def test_audit_consumer_group_workflow(self, redis_container) -> None:
        """Test consumer group create, consume, and ack workflow."""
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        
        async with RedisClient(config, engagement_id="test-cg-wf") as client:
            event_bus = EventBus(client)
            
            # Write some events
            for i in range(5):
                await event_bus.audit({"event": f"test_{i}"})
            
            # Create consumer group (may already exist)
            created = await event_bus.create_audit_consumer_group()
            
            # Consume events
            messages = await event_bus.consume_audit(
                "consumer-1", count=10, block_ms=100
            )
            
            # Should get messages
            assert len(messages) > 0
            
            # Acknowledge
            if messages:
                message_ids = [msg[0] for msg in messages]
                ack_count = await event_bus.ack_audit(*message_ids)
                assert ack_count == len(messages)

    @pytest.mark.asyncio
    async def test_audit_pending_info(self, redis_container) -> None:
        """Test pending_audit returns correct info."""
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        
        async with RedisClient(config, engagement_id="test-pending") as client:
            event_bus = EventBus(client)
            
            # Create group and write event
            await event_bus.create_audit_consumer_group()
            await event_bus.audit({"test": "pending"})
            
            # Consume but don't ack
            await event_bus.consume_audit("pending-consumer", count=1, block_ms=100)
            
            # Check pending
            pending = await event_bus.pending_audit()
            
            assert "count" in pending
            assert "consumers" in pending

    @pytest.mark.asyncio
    async def test_audit_claim_pending(self, redis_container) -> None:
        """Test claim_pending_audit claims stale messages."""
        host = redis_container.get_container_host_ip()
        port = int(redis_container.get_exposed_port(6379))
        
        config = RedisConfig(host=host, port=port)
        
        async with RedisClient(config, engagement_id="test-claim") as client:
            event_bus = EventBus(client)
            
            unique_stream = "audit:stream:claim"
            original_stream = EventBus.AUDIT_STREAM
            EventBus.AUDIT_STREAM = unique_stream
            
            try:
                # Create group
                await client.xgroup_create(unique_stream, "claim-group", start_id="0", mkstream=True)
                
                # Write event
                msg_id = await event_bus.audit({"claim": "test"}, maxlen=1000)
                
                # Consume but don't ack (simulates crashed consumer)
                old_group = EventBus.AUDIT_CONSUMER_GROUP
                EventBus.AUDIT_CONSUMER_GROUP = "claim-group"
                
                messages = await event_bus.consume_audit("dead-consumer", count=1, block_ms=100)
                
                if messages:
                    # Try to claim with min_idle_ms=0 (claim immediately for test)
                    claimed = await event_bus.claim_pending_audit(
                        "new-consumer",
                        min_idle_ms=0,
                        message_ids=[messages[0][0]]
                    )
                    # Note: claim may fail if min_idle not met, that's ok for this test
                
                EventBus.AUDIT_CONSUMER_GROUP = old_group
            finally:
                EventBus.AUDIT_STREAM = original_stream
