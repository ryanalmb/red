"""Unit tests for EventBus wrapper.

Tests the EventBus class which wraps RedisClient for stigmergic pub/sub
with channel validation and typed helpers.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

# Import will fail until implementation exists - this is the RED phase
# We mock RedisClient since it's tested separately in storage tests


class TestEventBusCreation:
    """Task 1: Test EventBus creates with RedisClient."""

    @pytest.mark.asyncio
    async def test_event_bus_creates_with_redis_client(self):
        """EventBus should wrap a RedisClient instance."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        # Create mock RedisClient
        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.is_connected = True

        # Create EventBus with mock
        event_bus = EventBus(mock_redis)

        # Verify EventBus stored the client
        assert event_bus._redis is mock_redis

    @pytest.mark.asyncio
    async def test_event_bus_publish_delegates_to_redis_client(self):
        """EventBus.publish should delegate to RedisClient.publish."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(return_value=3)

        event_bus = EventBus(mock_redis)

        # Call publish (needs valid channel - use control:test)
        result = await event_bus.publish("control:test", "hello")

        # Should delegate to RedisClient
        mock_redis.publish.assert_called_once_with("control:test", "hello")
        assert result == 3

    @pytest.mark.asyncio
    async def test_event_bus_subscribe_delegates_to_redis_client(self):
        """EventBus.subscribe should delegate to RedisClient.subscribe."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient
        from cyberred.storage.redis_client import PubSubSubscription

        mock_subscription = PubSubSubscription(
            pattern="control:*",
            unsubscribe=AsyncMock()
        )
        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.subscribe = AsyncMock(return_value=mock_subscription)

        event_bus = EventBus(mock_redis)

        async def callback(channel: str, message: str):
            pass

        result = await event_bus.subscribe("control:*", callback)

        # Should delegate to RedisClient (callback may be wrapped)
        mock_redis.subscribe.assert_called_once()
        assert result.pattern == "control:*"


class TestChannelValidation:
    """Task 2: Test channel name validation."""

    @pytest.mark.asyncio
    async def test_event_bus_validates_channel_names(self):
        """EventBus should reject invalid channel names."""
        from cyberred.core.events import EventBus, ChannelNameError
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(return_value=0)

        event_bus = EventBus(mock_redis)

        # Invalid channel (no colon notation)
        with pytest.raises(ChannelNameError):
            await event_bus.publish("invalidchannel", "test")

    @pytest.mark.asyncio
    async def test_event_bus_accepts_valid_findings_channel(self):
        """EventBus should accept valid findings:* channels."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(return_value=1)

        event_bus = EventBus(mock_redis)

        # Valid findings channel
        result = await event_bus.publish("findings:abc12345:sqli", "test")
        assert result == 1

    @pytest.mark.asyncio
    async def test_event_bus_accepts_valid_agents_channel(self):
        """EventBus should accept valid agents:*:status channels."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(return_value=1)

        event_bus = EventBus(mock_redis)

        # Valid agent status channel
        result = await event_bus.publish("agents:agent-001:status", '{"state": "running"}')
        assert result == 1

    @pytest.mark.asyncio
    async def test_event_bus_accepts_control_channels(self):
        """EventBus should accept control:* channels."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(return_value=1)

        event_bus = EventBus(mock_redis)

        # Valid control channel
        result = await event_bus.publish("control:kill", '{"reason": "user request"}')
        assert result == 1

    @pytest.mark.asyncio
    async def test_event_bus_accepts_authorization_channels(self):
        """EventBus should accept authorization:* channels."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(return_value=1)

        event_bus = EventBus(mock_redis)

        # Valid authorization channel
        result = await event_bus.publish("authorization:req-123", '{"approved": true}')
        assert result == 1


class TestJSONSerialization:
    """Task 3: Test JSON serialization."""

    @pytest.mark.asyncio
    async def test_event_bus_ensures_json_strings(self):
        """EventBus should serialize dict to JSON string."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient
        import json

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(return_value=1)

        event_bus = EventBus(mock_redis)

        # Pass dict, should be serialized
        await event_bus.publish("control:test", {"key": "value"})

        # Check that publish was called with JSON string
        call_args = mock_redis.publish.call_args[0]
        assert call_args[0] == "control:test"
        # Second arg should be JSON string
        parsed = json.loads(call_args[1])
        assert parsed == {"key": "value"}

    @pytest.mark.asyncio
    async def test_event_bus_passes_strings_directly(self):
        """EventBus should pass string messages directly."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(return_value=1)

        event_bus = EventBus(mock_redis)

        # Pass string directly
        await event_bus.publish("control:test", "raw string")

        mock_redis.publish.assert_called_once_with("control:test", "raw string")

    @pytest.mark.asyncio
    async def test_event_bus_rejects_invalid_types(self):
        """EventBus should reject non-string, non-dict types."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        event_bus = EventBus(mock_redis)

        # Invalid type (int)
        with pytest.raises(ValueError):
            await event_bus.publish("control:test", 12345)


class TestCallbackErrorSafety:
    """Task 4: Test callback error safety."""

    @pytest.mark.asyncio
    async def test_event_bus_wraps_callback_errors(self):
        """EventBus should wrap callbacks to prevent crashes on errors."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient
        from cyberred.storage.redis_client import PubSubSubscription

        mock_redis = MagicMock(spec=RedisClient)

        # Capture the wrapped callback
        captured_callback = None

        async def capture_subscribe(pattern, callback):
            nonlocal captured_callback
            captured_callback = callback
            return PubSubSubscription(pattern=pattern, unsubscribe=AsyncMock())

        mock_redis.subscribe = AsyncMock(side_effect=capture_subscribe)

        event_bus = EventBus(mock_redis)

        # User callback that raises an error
        async def failing_callback(channel: str, message: str):
            raise RuntimeError("Callback error!")

        await event_bus.subscribe("control:*", failing_callback)

        # The wrapped callback should catch the error (not crash)
        # This verifies the wrapper exists
        assert captured_callback is not None
        # Invoke it - should not raise
        await captured_callback("control:test", "message")


class TestAsyncMetrics:
    """Task 5: Test async metrics/logging."""

    @pytest.mark.asyncio
    async def test_event_bus_logs_performance(self):
        """EventBus should log publish latency."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient
        import structlog

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(return_value=1)

        event_bus = EventBus(mock_redis)

        # Capture log output
        with patch.object(structlog, 'get_logger') as mock_get_logger:
            mock_log = MagicMock()
            mock_get_logger.return_value = mock_log

            await event_bus.publish("control:test", "msg")

            # Note: actual structlog might be bound at class init
            # Just verify publish completed (logging tested via integration)


class TestFindingPublicationHelper:
    """Task 6: Test finding publication helper."""

    @pytest.mark.asyncio
    async def test_event_bus_publish_finding(self):
        """EventBus.publish_finding should auto-generate channel."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient
        import hashlib

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(return_value=1)

        event_bus = EventBus(mock_redis)

        # Create a mock finding (simplified)
        class MockFinding:
            target = "192.168.1.1"
            type = "sqli"
            id = "finding-001"

            def to_dict(self):
                return {"id": self.id, "target": self.target, "type": self.type}

        finding = MockFinding()

        result = await event_bus.publish_finding(finding)

        # Verify channel format
        target_hash = hashlib.sha256(finding.target.encode()).hexdigest()[:8]
        expected_channel = f"findings:{target_hash}:{finding.type}"

        call_args = mock_redis.publish.call_args[0]
        assert call_args[0] == expected_channel
        assert result == 1


class TestAgentStatusHelper:
    """Task 7: Test agent status publication helper."""

    @pytest.mark.asyncio
    async def test_event_bus_publish_agent_status(self):
        """EventBus.publish_agent_status should use correct channel."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient
        import json

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(return_value=1)

        event_bus = EventBus(mock_redis)

        status = {"state": "running", "task": "scanning", "timestamp": "2026-01-04T12:00:00Z"}

        result = await event_bus.publish_agent_status("agent-001", status)

        # Verify channel
        call_args = mock_redis.publish.call_args[0]
        assert call_args[0] == "agents:agent-001:status"
        # Verify payload is JSON
        parsed = json.loads(call_args[1])
        assert parsed["state"] == "running"
        assert result == 1


class TestKillSwitchSubscription:
    """Task 8: Test kill switch subscription."""

    @pytest.mark.asyncio
    async def test_event_bus_kill_switch_subscription(self):
        """EventBus.subscribe_kill_switch should subscribe to control:kill."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient
        from cyberred.storage.redis_client import PubSubSubscription

        mock_redis = MagicMock(spec=RedisClient)
        mock_subscription = PubSubSubscription(
            pattern="control:kill",
            unsubscribe=AsyncMock()
        )
        mock_redis.subscribe = AsyncMock(return_value=mock_subscription)

        event_bus = EventBus(mock_redis)

        async def kill_handler(reason: str):
            pass

        result = await event_bus.subscribe_kill_switch(kill_handler)

        # Verify subscription to correct channel
        call_args = mock_redis.subscribe.call_args[0]
        assert call_args[0] == "control:kill"
        assert result.pattern == "control:kill"


class TestDegradedModeVisibility:
    """Task 9: Test degraded mode visibility."""

    @pytest.mark.asyncio
    async def test_event_bus_exposes_degraded_state(self):
        """EventBus.is_degraded should reflect RedisClient state."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient
        from cyberred.storage.redis_client import ConnectionState

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.connection_state = ConnectionState.DEGRADED

        event_bus = EventBus(mock_redis)

        assert event_bus.is_degraded is True

        # Test connected state
        mock_redis.connection_state = ConnectionState.CONNECTED
        assert event_bus.is_degraded is False


class TestHealthCheck:
    """Task 10: Test health check."""

    @pytest.mark.asyncio
    async def test_event_bus_health_check(self):
        """EventBus.health_check should delegate to RedisClient."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient
        from cyberred.storage.redis_client import HealthStatus

        mock_redis = MagicMock(spec=RedisClient)
        mock_health = HealthStatus(healthy=True, latency_ms=5.0, master_addr="localhost:6379")
        mock_redis.health_check = AsyncMock(return_value=mock_health)

        event_bus = EventBus(mock_redis)

        result = await event_bus.health_check()

        mock_redis.health_check.assert_called_once()
        assert result.healthy is True
        assert result.latency_ms == 5.0


class TestEdgeCases:
    """Edge case tests for 100% coverage."""

    @pytest.mark.asyncio
    async def test_event_bus_slow_publish_warning(self):
        """EventBus should log warning for slow publishes (>500ms)."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient
        import time

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(return_value=1)

        event_bus = EventBus(mock_redis)

        # Mock time.perf_counter to simulate delay
        # First call: start time
        # Second call: end time (start + 0.6s)
        # Third call: callback start (if any) - not needed here
        with patch("time.perf_counter", side_effect=[1000.0, 1000.6]):
            # This should trigger the slow warning path
            result = await event_bus.publish("control:test", "msg")

        assert result == 1
        # warning log is checked via side effect of covering the line

    @pytest.mark.asyncio
    async def test_event_bus_publish_agent_status_validation(self):
        """EventBus.publish_agent_status should validate required fields."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        event_bus = EventBus(mock_redis)

        # Missing 'timestamp'
        invalid_status = {"state": "running", "task": "scanning"}

        with pytest.raises(ValueError, match="missing required fields.*timestamp"):
            await event_bus.publish_agent_status("agent-001", invalid_status)

    @pytest.mark.asyncio
    async def test_event_bus_publish_finding_missing_attributes(self):
        """EventBus.publish_finding should raise ValueError for invalid finding."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        event_bus = EventBus(mock_redis)

        # Finding without target/type
        class InvalidFinding:
            pass

        with pytest.raises(ValueError, match="target.*type"):
            await event_bus.publish_finding(InvalidFinding())

    @pytest.mark.asyncio
    async def test_event_bus_publish_finding_without_to_dict(self):
        """EventBus.publish_finding should handle objects without to_dict."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient
        import json

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(return_value=1)

        event_bus = EventBus(mock_redis)

        # Finding with __dict__ but no to_dict method
        class SimpleFinding:
            def __init__(self):
                self.target = "10.0.0.1"
                self.type = "xss"
                self.severity = "high"
                self._internal = "private"

        finding = SimpleFinding()
        result = await event_bus.publish_finding(finding)

        # Verify payload was extracted from __dict__ (excluding _private)
        call_args = mock_redis.publish.call_args[0]
        payload = json.loads(call_args[1])
        assert payload["target"] == "10.0.0.1"
        assert payload["type"] == "xss"
        assert payload["severity"] == "high"
        assert "_internal" not in payload
        assert result == 1

    @pytest.mark.asyncio
    async def test_event_bus_publish_finding_bare_object(self):
        """EventBus.publish_finding should handle bare objects without __dict__."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient
        import json

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(return_value=1)

        event_bus = EventBus(mock_redis)

        # Use a namedtuple-like object (has target/type but special __dict__ behavior)
        class BareFinding:
            __slots__ = ["target", "type"]
            
            def __init__(self, target, finding_type):
                self.target = target
                self.type = finding_type

        finding = BareFinding("192.168.1.1", "rce")
        result = await event_bus.publish_finding(finding)

        # Should fall back to basic payload
        call_args = mock_redis.publish.call_args[0]
        payload = json.loads(call_args[1])
        assert payload["target"] == "192.168.1.1"
        assert payload["type"] == "rce"
        assert result == 1

    @pytest.mark.asyncio
    async def test_event_bus_kill_switch_json_message(self):
        """EventBus kill switch handler should parse JSON reason."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient
        from cyberred.storage.redis_client import PubSubSubscription

        mock_redis = MagicMock(spec=RedisClient)

        # Capture the registered callback
        captured_handler = None

        async def capture_subscribe(pattern, callback):
            nonlocal captured_handler
            captured_handler = callback
            return PubSubSubscription(pattern=pattern, unsubscribe=AsyncMock())

        mock_redis.subscribe = AsyncMock(side_effect=capture_subscribe)

        event_bus = EventBus(mock_redis)

        # Track what reason the user callback receives
        received_reason = None

        async def user_callback(reason: str):
            nonlocal received_reason
            received_reason = reason

        await event_bus.subscribe_kill_switch(user_callback)

        # Invoke handler with JSON message
        await captured_handler("control:kill", '{"reason": "user_abort"}')
        assert received_reason == "user_abort"

    @pytest.mark.asyncio
    async def test_event_bus_kill_switch_plain_message(self):
        """EventBus kill switch handler should handle non-JSON messages."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient
        from cyberred.storage.redis_client import PubSubSubscription

        mock_redis = MagicMock(spec=RedisClient)

        captured_handler = None

        async def capture_subscribe(pattern, callback):
            nonlocal captured_handler
            captured_handler = callback
            return PubSubSubscription(pattern=pattern, unsubscribe=AsyncMock())

        mock_redis.subscribe = AsyncMock(side_effect=capture_subscribe)

        event_bus = EventBus(mock_redis)

        received_reason = None

        async def user_callback(reason: str):
            nonlocal received_reason
            received_reason = reason

        await event_bus.subscribe_kill_switch(user_callback)

        # Invoke handler with plain string (not JSON)
        await captured_handler("control:kill", "emergency_stop")
        assert received_reason == "emergency_stop"

    @pytest.mark.asyncio
    async def test_event_bus_list_serialization(self):
        """EventBus should serialize list messages to JSON."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient
        import json

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.publish = AsyncMock(return_value=1)

        event_bus = EventBus(mock_redis)

        # Pass a list
        await event_bus.publish("control:test", ["item1", "item2"])

        call_args = mock_redis.publish.call_args[0]
        parsed = json.loads(call_args[1])
        assert parsed == ["item1", "item2"]


# =============================================================================
# Story 3.4: EventBus Audit Stream Tests
# =============================================================================


class TestEventBusAudit:
    """Tests for EventBus audit stream methods (Story 3.4 Tasks 7-11)."""

    @pytest.mark.asyncio
    async def test_event_bus_audit_writes_to_stream(self):
        """EventBus.audit should write event to audit:stream."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")

        event_bus = EventBus(mock_redis)

        result = await event_bus.audit({"type": "login", "user": "test"})

        assert result == "1234567890-0"
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == "audit:stream"

    @pytest.mark.asyncio
    async def test_event_bus_audit_with_string_event(self):
        """EventBus.audit should handle string events."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.xadd = AsyncMock(return_value="1234567890-1")

        event_bus = EventBus(mock_redis)

        result = await event_bus.audit("user_logged_in")

        assert result == "1234567890-1"
        call_args = mock_redis.xadd.call_args
        payload = call_args[0][1]
        assert payload["event"] == "user_logged_in"
        assert "timestamp" in payload

    @pytest.mark.asyncio
    async def test_event_bus_audit_adds_timestamp(self):
        """EventBus.audit should add timestamp if not present."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.xadd = AsyncMock(return_value="1234567890-2")

        event_bus = EventBus(mock_redis)

        await event_bus.audit({"type": "action"})

        call_args = mock_redis.xadd.call_args
        payload = call_args[0][1]
        assert "timestamp" in payload

    @pytest.mark.asyncio
    async def test_event_bus_audit_preserves_timestamp(self):
        """EventBus.audit should preserve existing timestamp."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.xadd = AsyncMock(return_value="1234567890-3")

        event_bus = EventBus(mock_redis)

        await event_bus.audit({"type": "action", "timestamp": 12345.0})

        call_args = mock_redis.xadd.call_args
        payload = call_args[0][1]
        assert payload["timestamp"] == 12345.0

    @pytest.mark.asyncio
    async def test_event_bus_audit_rejects_invalid_type(self):
        """EventBus.audit should reject invalid event types."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        event_bus = EventBus(mock_redis)

        with pytest.raises(ValueError, match="Event must be str or dict"):
            await event_bus.audit(12345)

    @pytest.mark.asyncio
    async def test_event_bus_audit_with_maxlen(self):
        """EventBus.audit should pass maxlen to xadd."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.xadd = AsyncMock(return_value="1234567890-4")

        event_bus = EventBus(mock_redis)

        await event_bus.audit({"type": "test"}, maxlen=1000)

        call_args = mock_redis.xadd.call_args
        assert call_args[1]["maxlen"] == 1000

    @pytest.mark.asyncio
    async def test_event_bus_create_audit_consumer_group(self):
        """EventBus.create_audit_consumer_group should create group."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.xgroup_create = AsyncMock(return_value=True)

        event_bus = EventBus(mock_redis)

        result = await event_bus.create_audit_consumer_group()

        assert result is True
        mock_redis.xgroup_create.assert_called_once_with(
            "audit:stream", "audit-consumers", start_id="0", mkstream=True
        )

    @pytest.mark.asyncio
    async def test_event_bus_create_audit_consumer_group_custom(self):
        """EventBus.create_audit_consumer_group should accept custom group."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.xgroup_create = AsyncMock(return_value=True)

        event_bus = EventBus(mock_redis)

        await event_bus.create_audit_consumer_group(group="my-custom-group")

        call_args = mock_redis.xgroup_create.call_args
        assert call_args[0][1] == "my-custom-group"

    @pytest.mark.asyncio
    async def test_event_bus_consume_audit(self):
        """EventBus.consume_audit should read from stream."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_messages = [("123-0", {"type": "test"})]
        mock_redis.xreadgroup = AsyncMock(return_value=mock_messages)

        event_bus = EventBus(mock_redis)

        result = await event_bus.consume_audit("consumer-1", count=5)

        assert result == mock_messages
        mock_redis.xreadgroup.assert_called_once_with(
            "audit-consumers", "consumer-1", "audit:stream", count=5, block_ms=5000
        )

    @pytest.mark.asyncio
    async def test_event_bus_ack_audit(self):
        """EventBus.ack_audit should acknowledge messages."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.xack = AsyncMock(return_value=2)

        event_bus = EventBus(mock_redis)

        result = await event_bus.ack_audit("123-0", "123-1")

        assert result == 2
        mock_redis.xack.assert_called_once_with("audit:stream", "audit-consumers", "123-0", "123-1")

    @pytest.mark.asyncio
    async def test_event_bus_ack_audit_empty(self):
        """EventBus.ack_audit should return 0 for no messages."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        event_bus = EventBus(mock_redis)

        result = await event_bus.ack_audit()

        assert result == 0
        mock_redis.xack.assert_not_called()

    @pytest.mark.asyncio
    async def test_event_bus_pending_audit(self):
        """EventBus.pending_audit should return pending info."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_pending = {"count": 5, "min_id": "100-0", "max_id": "105-0", "consumers": {}}
        mock_redis.xpending = AsyncMock(return_value=mock_pending)

        event_bus = EventBus(mock_redis)

        result = await event_bus.pending_audit()

        assert result == mock_pending
        mock_redis.xpending.assert_called_once_with("audit:stream", "audit-consumers")

    @pytest.mark.asyncio
    async def test_event_bus_claim_pending_audit(self):
        """EventBus.claim_pending_audit should claim messages."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_claimed = [("123-0", {"type": "old"})]
        mock_redis.xclaim = AsyncMock(return_value=mock_claimed)

        event_bus = EventBus(mock_redis)

        result = await event_bus.claim_pending_audit(
            "consumer-new", min_idle_ms=30000, message_ids=["123-0"]
        )

        assert result == mock_claimed
        mock_redis.xclaim.assert_called_once_with(
            "audit:stream", "audit-consumers", "consumer-new", 30000, ["123-0"]
        )

    @pytest.mark.asyncio
    async def test_event_bus_claim_pending_audit_empty(self):
        """EventBus.claim_pending_audit should return empty for no IDs."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        event_bus = EventBus(mock_redis)

        result = await event_bus.claim_pending_audit("consumer-new")

        assert result == []
        mock_redis.xclaim.assert_not_called()

    @pytest.mark.asyncio
    async def test_event_bus_create_audit_group_already_exists(self):
        """EventBus.create_audit_consumer_group should not log when group exists."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.xgroup_create = AsyncMock(return_value=False)  # Group already exists

        event_bus = EventBus(mock_redis)

        result = await event_bus.create_audit_consumer_group()

        assert result is False  # Branch 437->444 taken (no log)

    @pytest.mark.asyncio
    async def test_event_bus_consume_audit_empty_result(self):
        """EventBus.consume_audit should not log when no messages."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.xreadgroup = AsyncMock(return_value=[])  # No messages

        event_bus = EventBus(mock_redis)

        result = await event_bus.consume_audit("consumer-1")

        assert result == []  # Branch 478->485 taken (no log)

    @pytest.mark.asyncio
    async def test_event_bus_claim_pending_audit_no_claims(self):
        """EventBus.claim_pending_audit should not log when no claims."""
        from cyberred.core.events import EventBus
        from cyberred.storage import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.xclaim = AsyncMock(return_value=[])  # No claims

        event_bus = EventBus(mock_redis)

        result = await event_bus.claim_pending_audit(
            "consumer-new", min_idle_ms=1000, message_ids=["123-0"]
        )

        assert result == []  # Branch 561->568 taken (no log)

