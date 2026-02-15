import redis.asyncio as redis
import json
import asyncio
import logging


class _Subscription:
    """Tracks a single subscribe/psubscribe so it can be cleaned up."""

    __slots__ = ("pubsub", "task", "channel_or_pattern", "is_pattern")

    def __init__(
        self,
        pubsub: redis.client.PubSub,
        task: asyncio.Task,
        channel_or_pattern: str,
        is_pattern: bool,
    ):
        self.pubsub = pubsub
        self.task = task
        self.channel_or_pattern = channel_or_pattern
        self.is_pattern = is_pattern

    async def cancel(self) -> None:
        """Cancel the reader task and close the pubsub connection."""
        self.task.cancel()
        try:
            await self.task
        except (asyncio.CancelledError, Exception):
            pass
        try:
            if self.is_pattern:
                await self.pubsub.punsubscribe(self.channel_or_pattern)
            else:
                await self.pubsub.unsubscribe(self.channel_or_pattern)
            await self.pubsub.close()
        except Exception:
            pass


class EventBus:
    """Redis-backed event bus with tracked subscriptions.

    Every ``subscribe()`` / ``psubscribe()`` call creates a dedicated
    pubsub connection + reader task and registers a ``_Subscription``
    so that callers (or ``close()``) can cleanly tear them down,
    preventing Redis connection leaks on agent shutdown.
    """

    def __init__(self, redis_url="redis://localhost:6379/0"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.logger = logging.getLogger("EventBus")
        # Track all subscriptions for cleanup
        self._subscriptions: list[_Subscription] = []
        self._lock = asyncio.Lock()

    async def publish(self, channel: str, message: dict):
        """Publish a structured message to a channel."""
        payload = json.dumps(message)
        await self.redis.publish(channel, payload)

    async def subscribe(self, channel: str, callback) -> "_Subscription":
        """Subscribe to a channel and run callback(message) for each event.

        Returns a ``_Subscription`` handle that can be used to cancel and
        clean up the underlying pubsub connection.
        """
        ps = self.redis.pubsub()
        await ps.subscribe(channel)

        async def reader():
            try:
                async for message in ps.listen():
                    if message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            await callback(data)
                        except json.JSONDecodeError:
                            self.logger.error(f"Invalid JSON in {channel}")
                        except Exception as e:
                            self.logger.error(f"Error in subscriber {channel}: {e}")
            except asyncio.CancelledError:
                pass

        task = asyncio.create_task(reader())
        sub = _Subscription(ps, task, channel, is_pattern=False)
        async with self._lock:
            self._subscriptions.append(sub)
        return sub

    async def psubscribe(self, pattern: str, callback) -> "_Subscription":
        """Subscribe to channels matching a glob pattern (Redis PSUBSCRIBE).

        Callback receives ``(channel, data)`` where *channel* is the
        actual channel name that matched the pattern.

        Returns a ``_Subscription`` handle for cleanup.
        """
        ps = self.redis.pubsub()
        await ps.psubscribe(pattern)

        async def reader():
            try:
                async for message in ps.listen():
                    if message["type"] == "pmessage":
                        try:
                            data = json.loads(message["data"])
                            await callback(message["channel"], data)
                        except json.JSONDecodeError:
                            self.logger.error(f"Invalid JSON in {message['channel']}")
                        except Exception as e:
                            self.logger.error(f"Error in psubscriber {pattern}: {e}")
            except asyncio.CancelledError:
                pass

        task = asyncio.create_task(reader())
        sub = _Subscription(ps, task, pattern, is_pattern=True)
        async with self._lock:
            self._subscriptions.append(sub)
        return sub

    async def cancel_subscription(self, sub: "_Subscription") -> None:
        """Cancel a single subscription and release its connection."""
        await sub.cancel()
        async with self._lock:
            try:
                self._subscriptions.remove(sub)
            except ValueError:
                pass

    async def audit(self, event: dict):
        """Log an audit event to the audit channel.
        
        Audit events are important compliance/security events that need
        to be recorded for later review. They are published to a dedicated
        audit channel.
        
        Args:
            event: The audit event data as a dictionary.
        """
        audit_channel = "audit:events"
        await self.publish(audit_channel, event)
        self.logger.debug(f"Audit event: {event.get('type', 'unknown')}")

    async def close(self):
        """Close all tracked subscriptions and the publish connection."""
        async with self._lock:
            subs = list(self._subscriptions)
            self._subscriptions.clear()
        # Cancel all subscriptions concurrently
        if subs:
            await asyncio.gather(
                *(s.cancel() for s in subs),
                return_exceptions=True,
            )
        await self.redis.close()
