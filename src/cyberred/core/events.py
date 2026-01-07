"""EventBus wrapper for stigmergic pub/sub messaging.

Provides a high-level wrapper around RedisClient for real-time stigmergic
coordination between agents. Handles channel validation, JSON serialization,
and typed helpers for common message patterns.

Key Features:
- Channel name validation (colon notation per architecture)
- JSON auto-serialization for dict/list payloads
- Typed helpers: publish_finding, publish_agent_status, subscribe_kill_switch
- Performance logging with latency metrics
- Delegates HMAC signing/validation to RedisClient (Story 3.1)

Story: 3.3 Event Bus (Pub/Sub)
NFR1: Agent coordination latency <1s stigmergic propagation (Hard)
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Union

import structlog

if TYPE_CHECKING:
    from cyberred.storage.redis_client import (
        HealthStatus,
        PubSubSubscription,
        RedisClient,
    )

log = structlog.get_logger()


# =============================================================================
# Channel Name Patterns (per architecture line 686-700)
# =============================================================================

# Channel patterns allowed by architecture:
# - findings:{target_hash}:{type}
# - agents:{agent_id}:status
# - control:* (kill, pause, etc.)
# - authorization:{request_id}

CHANNEL_PATTERNS = [
    re.compile(r"^findings:[a-f0-9]+:[a-z0-9_-]+$", re.IGNORECASE),  # findings:hash:type
    re.compile(r"^agents:[a-zA-Z0-9_-]+:status$"),  # agents:id:status
    re.compile(r"^control:[a-zA-Z0-9_-]+$"),  # control:*
    re.compile(r"^authorization:[a-zA-Z0-9_-]+$"),  # authorization:request_id
    re.compile(r"^audit:stream$"),  # audit:stream (Story 3.4)
]


# =============================================================================
# Exceptions
# =============================================================================


class ChannelNameError(ValueError):
    """Raised when a channel name doesn't match allowed patterns."""

    def __init__(self, channel: str):
        self.channel = channel
        super().__init__(
            f"Invalid channel name: '{channel}'. "
            "Must match one of: findings:{{hash}}:{{type}}, agents:{{id}}:status, "
            "control:*, authorization:{{id}}, audit:stream"
        )


# =============================================================================
# EventBus Class
# =============================================================================


class EventBus:
    """High-level wrapper for Redis pub/sub messaging.

    Wraps RedisClient to provide channel validation, JSON serialization,
    and typed helpers for stigmergic communication patterns.

    Note: HMAC signing and validation is handled by RedisClient (Story 3.1).
    EventBus focuses on channel routing and payload structure.

    Example:
        async with RedisClient(config, engagement_id) as redis:
            event_bus = EventBus(redis)
            await event_bus.publish_finding(finding)
    """

    def __init__(self, redis_client: RedisClient) -> None:
        """Initialize EventBus.

        Args:
            redis_client: Connected RedisClient instance.
        """
        self._redis = redis_client
        self._last_publish_latency_ms: float = 0.0
        self._log = log.bind(component="event_bus")

    # =========================================================================
    # Core Publish/Subscribe (Tasks 1-2)
    # =========================================================================

    async def publish(
        self,
        channel: str,
        message: Union[str, dict, list],
    ) -> int:
        """Publish a message to a Redis channel.

        Args:
            channel: Channel name (must match allowed patterns).
            message: Message content (str, dict, or list). Dicts/lists are
                auto-serialized to JSON.

        Returns:
            Number of subscribers that received the message (0 if degraded).

        Raises:
            ChannelNameError: If channel doesn't match allowed patterns.
            ValueError: If message type is not str, dict, or list.
        """
        # Task 2: Validate channel name
        self._validate_channel(channel)

        # Task 3: Ensure string payload
        payload = self._ensure_string(message)

        # Task 5: Measure latency
        start_time = time.perf_counter()

        # Delegate to RedisClient (which handles HMAC signing)
        result = await self._redis.publish(channel, payload)

        # Task 5: Log performance
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        self._last_publish_latency_ms = elapsed_ms

        if elapsed_ms > 500:
            self._log.warning(
                "event_published_slow",
                channel=channel,
                latency_ms=elapsed_ms,
            )
        else:
            self._log.debug(
                "event_published",
                channel=channel,
                latency_ms=elapsed_ms,
                subscribers=result,
            )

        return result

    async def subscribe(
        self,
        pattern: str,
        callback: Callable[[str, str], Awaitable[None]],
    ) -> PubSubSubscription:
        """Subscribe to Redis channels matching a pattern.

        Args:
            pattern: Channel pattern (e.g., "findings:*", "control:*").
            callback: Async function(channel, message) called for each message.
                Note: callback receives verified content (HMAC checked by RedisClient).

        Returns:
            PubSubSubscription handle for unsubscribing.
        """
        from cyberred.storage.redis_client import PubSubSubscription

        # Task 4: Wrap callback for error safety
        async def safe_callback(channel: str, message: str) -> None:
            callback_start = time.perf_counter()
            try:
                await callback(channel, message)
            except Exception as e:
                self._log.error(
                    "event_callback_error",
                    channel=channel,
                    error=str(e),
                    exc_info=True,
                )
            finally:
                elapsed_ms = (time.perf_counter() - callback_start) * 1000
                self._log.debug(
                    "event_callback_completed",
                    channel=channel,
                    duration_ms=elapsed_ms,
                )

        # Delegate to RedisClient (which handles signature validation)
        subscription = await self._redis.subscribe(pattern, safe_callback)

        self._log.info("event_subscribed", pattern=pattern)

        return subscription

    # =========================================================================
    # Validation Helpers (Task 2)
    # =========================================================================


    def _validate_channel(self, channel: str) -> None:
        """Validate channel name against allowed patterns.

        Raises:
            ChannelNameError: If channel doesn't match any allowed pattern.
        """
        for pattern in CHANNEL_PATTERNS:
            if pattern.match(channel):
                return
        raise ChannelNameError(channel)

    def _ensure_string(self, message: Union[str, dict, list, Any]) -> str:
        """Ensure message is a string, serializing if needed.

        Args:
            message: Message to convert (str, dict, or list).

        Returns:
            String representation.

        Raises:
            ValueError: If message type is not supported.
        """
        if isinstance(message, str):
            return message
        if isinstance(message, (dict, list)):
            return json.dumps(message)
        raise ValueError(
            f"Message must be str, dict, or list, got {type(message).__name__}"
        )

    # =========================================================================
    # Stigmergic Channel Helpers (Tasks 6-8)
    # =========================================================================

    async def publish_finding(self, finding: Any) -> int:
        """Publish a finding to the findings channel.

        Auto-generates channel: findings:{target_hash}:{type}

        Args:
            finding: Finding object with 'target', 'type', and 'to_dict()' or dict-like.

        Returns:
            Number of subscribers that received the message.
        """
        # Extract target and type
        target = getattr(finding, "target", None)
        finding_type = getattr(finding, "type", None)

        if not target or not finding_type:
            raise ValueError("Finding must have 'target' and 'type' attributes")

        # Generate channel
        target_hash = hashlib.sha256(str(target).encode()).hexdigest()[:8]
        channel = f"findings:{target_hash}:{finding_type}"

        # Serialize finding
        if hasattr(finding, "to_dict"):
            payload = finding.to_dict()
        elif hasattr(finding, "__dict__"):
            payload = {
                k: v for k, v in finding.__dict__.items() if not k.startswith("_")
            }
        else:
            payload = {"target": target, "type": finding_type}

        result = await self.publish(channel, payload)

        self._log.info(
            "finding_published",
            finding_id=getattr(finding, "id", None),
            target=target,
            type=finding_type,
            channel=channel,
        )

        return result

    async def publish_agent_status(self, agent_id: str, status: dict) -> int:
        """Publish agent status update.

        Args:
            agent_id: Agent identifier.
            status: Status dict (must contain 'state', 'task', 'timestamp').

        Returns:
            Number of subscribers that received the message.

        Raises:
            ValueError: If status dict is missing required fields.
        """
        required_fields = {"state", "task", "timestamp"}
        missing_fields = required_fields - status.keys()
        if missing_fields:
            raise ValueError(
                f"Status dict missing required fields: {', '.join(missing_fields)}"
            )

        channel = f"agents:{agent_id}:status"

        result = await self.publish(channel, status)

        self._log.info(
            "agent_status_published",
            agent_id=agent_id,
            status_state=status.get("state"),
        )

        return result

    async def subscribe_kill_switch(
        self,
        callback: Callable[[str], Awaitable[None]],
    ) -> PubSubSubscription:
        """Subscribe to kill switch channel.

        Args:
            callback: Async function(reason) called when kill signal received.

        Returns:
            PubSubSubscription handle for unsubscribing.
        """
        async def kill_handler(channel: str, message: str) -> None:
            self._log.warning("kill_switch_received", channel=channel)
            # Parse message to extract reason
            try:
                data = json.loads(message)
                reason = data.get("reason", "unknown")
            except json.JSONDecodeError:
                reason = message
            await callback(reason)

        return await self._redis.subscribe("control:kill", kill_handler)

    # =========================================================================
    # Connection State (Tasks 9-10)
    # =========================================================================

    @property
    def is_degraded(self) -> bool:
        """Whether EventBus is in degraded mode (buffering messages)."""
        from cyberred.storage.redis_client import ConnectionState

        return self._redis.connection_state == ConnectionState.DEGRADED

    async def health_check(self) -> HealthStatus:
        """Check health of underlying Redis connection.

        Returns:
            HealthStatus with connection health info.
        """
        result = await self._redis.health_check()

        self._log.debug(
            "event_bus_health_check",
            healthy=result.healthy,
            latency_ms=result.latency_ms,
            last_publish_latency_ms=self._last_publish_latency_ms,
        )

        return result

    # =========================================================================
    # Story 3.4: Audit Stream Methods (Tasks 7-11)
    # =========================================================================

    # Default audit stream name
    AUDIT_STREAM = "audit:stream"
    AUDIT_CONSUMER_GROUP = "audit-consumers"

    async def audit(
        self,
        event: Union[str, dict],
        maxlen: int | None = None,
    ) -> str:
        """Write audit event to Redis Stream with at-least-once guarantee.

        Args:
            event: Event data (str or dict). Dicts are auto-serialized to JSON.
            maxlen: Optional max stream length for trimming.

        Returns:
            Message ID assigned by Redis (timestamp-sequence string).

        Note:
            Events are signed with HMAC-SHA256 by RedisClient.xadd.
        """
        # Ensure event is dict format
        if isinstance(event, str):
            payload = {"event": event, "timestamp": time.time()}
        elif isinstance(event, dict):
            payload = event
            if "timestamp" not in payload:
                payload = {**payload, "timestamp": time.time()}
        else:
            raise ValueError(f"Event must be str or dict, got {type(event).__name__}")

        # Extract event type for logging
        event_type = payload.get("type", payload.get("event", "unknown"))

        message_id = await self._redis.xadd(self.AUDIT_STREAM, payload, maxlen=maxlen)

        self._log.info(
            "audit_event_written",
            message_id=message_id,
            event_type=event_type,
        )

        return message_id

    async def create_audit_consumer_group(self, group: str | None = None) -> bool:
        """Initialize the audit consumer group.

        Args:
            group: Optional custom group name (default: "audit-consumers").

        Returns:
            True if group created, False if already exists.
        """
        group_name = group or self.AUDIT_CONSUMER_GROUP

        result = await self._redis.xgroup_create(
            self.AUDIT_STREAM,
            group_name,
            start_id="0",  # Start from beginning for audit (don't lose events)
            mkstream=True,
        )

        if result:
            self._log.info(
                "audit_consumer_group_initialized",
                stream=self.AUDIT_STREAM,
                group=group_name,
            )

        return result

    async def consume_audit(
        self,
        consumer_id: str,
        count: int = 10,
        block_ms: int = 5000,
        group: str | None = None,
    ) -> list[tuple[str, dict]]:
        """Consume audit events from the stream.

        Args:
            consumer_id: Unique consumer identifier within the group.
            count: Maximum events to consume per call.
            block_ms: Milliseconds to block waiting for data.
            group: Optional custom group name.

        Returns:
            List of (message_id, event_data) tuples.
            Caller must call ack_audit() after processing.

        Note:
            Messages with invalid HMAC signatures are automatically skipped.
        """
        group_name = group or self.AUDIT_CONSUMER_GROUP

        messages = await self._redis.xreadgroup(
            group_name,
            consumer_id,
            self.AUDIT_STREAM,
            count=count,
            block_ms=block_ms,
        )

        if messages:
            self._log.info(
                "audit_events_consumed",
                consumer=consumer_id,
                count=len(messages),
            )

        return messages

    async def ack_audit(self, *message_ids: str, group: str | None = None) -> int:
        """Acknowledge audit events as processed.

        Args:
            *message_ids: One or more message IDs to acknowledge.
            group: Optional custom group name.

        Returns:
            Number of messages successfully acknowledged.
        """
        if not message_ids:
            return 0

        group_name = group or self.AUDIT_CONSUMER_GROUP

        count = await self._redis.xack(self.AUDIT_STREAM, group_name, *message_ids)

        self._log.info(
            "audit_events_acknowledged",
            acknowledged_count=count,
        )

        return count

    async def pending_audit(self, group: str | None = None) -> dict:
        """Get pending audit message info.

        Args:
            group: Optional custom group name.

        Returns:
            Dict with pending info:
            - count: Total pending messages
            - min_id: Oldest pending message ID
            - max_id: Newest pending message ID
            - consumers: Dict of consumer_name -> pending_count
        """
        group_name = group or self.AUDIT_CONSUMER_GROUP

        return await self._redis.xpending(self.AUDIT_STREAM, group_name)

    async def claim_pending_audit(
        self,
        consumer_id: str,
        min_idle_ms: int = 60000,
        message_ids: list[str] | None = None,
        group: str | None = None,
    ) -> list[tuple[str, dict]]:
        """Claim stale pending audit messages for redelivery.

        Used to reprocess messages from crashed consumers.

        Args:
            consumer_id: Consumer to claim messages for.
            min_idle_ms: Minimum idle time threshold (default: 60s).
            message_ids: Specific message IDs to claim (required).
            group: Optional custom group name.

        Returns:
            List of (message_id, event_data) tuples for claimed messages.
        """
        if not message_ids:
            return []

        group_name = group or self.AUDIT_CONSUMER_GROUP

        claimed = await self._redis.xclaim(
            self.AUDIT_STREAM,
            group_name,
            consumer_id,
            min_idle_ms,
            message_ids,
        )

        if claimed:
            self._log.info(
                "audit_pending_claimed",
                consumer=consumer_id,
                claimed_count=len(claimed),
            )

        return claimed
