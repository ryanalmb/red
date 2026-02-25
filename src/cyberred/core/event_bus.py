import asyncio
import contextlib
import inspect
import json
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

import redis.asyncio as redis


class _Subscription:
    """Tracks a single subscription callback so it can be cleaned up."""

    __slots__ = ("_cancel_cb", "_closed")

    def __init__(
        self,
        cancel_cb: Callable[[], Awaitable[None]],
    ) -> None:
        self._cancel_cb = cancel_cb
        self._closed = False

    async def cancel(self) -> None:
        """Cancel this subscription callback."""
        if self._closed:
            return
        self._closed = True
        await self._cancel_cb()


class EventBus:
    """Redis-backed event bus with shared pubsub multiplexing.

    Uses one shared Redis pubsub connection for exact subscriptions and
    one shared pubsub connection for pattern subscriptions. This avoids
    opening one TCP socket per callback, which causes FD exhaustion when
    many agents subscribe concurrently.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.logger = logging.getLogger("EventBus")
        self._lock = asyncio.Lock()
        # redis-py PubSub is not safe for concurrent reads/writes on the same
        # connection. Serialize all PubSub socket I/O per connection.
        self._channel_io_lock = asyncio.Lock()
        self._pattern_io_lock = asyncio.Lock()
        self._subscriptions: set[_Subscription] = set()
        self._channel_callbacks: dict[str, list[Callable[..., Any]]] = defaultdict(list)
        self._pattern_callbacks: dict[str, list[Callable[..., Any]]] = defaultdict(list)
        self._channel_pubsub: Any | None = None
        self._pattern_pubsub: Any | None = None
        self._channel_task: asyncio.Task | None = None
        self._pattern_task: asyncio.Task | None = None

    async def publish(self, channel: str, message: dict) -> None:
        """Publish a structured message to a channel."""
        payload = json.dumps(message)
        await self.redis.publish(channel, payload)

    @staticmethod
    def _accepts_n_args(callback: Callable[..., Any], n: int) -> bool:
        """Best-effort check if callback accepts N positional args."""
        try:
            inspect.signature(callback).bind_partial(*([None] * n))
            return True
        except (TypeError, ValueError):
            return False

    async def _invoke_channel_callback(
        self,
        callback: Callable[..., Any],
        channel: str,
        data: Any,
    ) -> None:
        """Invoke subscribe() callback while preserving legacy signatures."""
        try:
            if self._accepts_n_args(callback, 1):
                result = callback(data)
            elif self._accepts_n_args(callback, 2):
                result = callback(channel, data)
            else:
                result = callback(data)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            self.logger.error("Error in subscriber %s: %s", channel, exc)

    async def _invoke_pattern_callback(
        self,
        callback: Callable[..., Any],
        pattern: str,
        channel: str,
        data: Any,
    ) -> None:
        """Invoke psubscribe() callback while preserving legacy signatures."""
        try:
            if self._accepts_n_args(callback, 2):
                result = callback(channel, data)
            elif self._accepts_n_args(callback, 1):
                result = callback(data)
            else:
                result = callback(channel, data)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            self.logger.error("Error in psubscriber %s: %s", pattern, exc)

    async def _channel_reader(self) -> None:
        """Read exact-channel pubsub messages and dispatch to callbacks."""
        while True:
            pubsub = self._channel_pubsub
            if pubsub is None:
                return
            try:
                async with self._channel_io_lock:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                if not message:
                    continue
                if message.get("type") != "message":
                    continue
                channel = message.get("channel")
                raw_data = message.get("data")
                if isinstance(channel, bytes):
                    channel = channel.decode()
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode()
                try:
                    data = json.loads(raw_data)
                except json.JSONDecodeError:
                    self.logger.error("Invalid JSON in %s", channel)
                    continue
                async with self._lock:
                    callbacks = list(self._channel_callbacks.get(channel, ()))
                for callback in callbacks:
                    await self._invoke_channel_callback(callback, channel, data)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                self.logger.error("Channel reader crashed: %s", exc)
                await asyncio.sleep(0.1)

    async def _pattern_reader(self) -> None:
        """Read pattern pubsub messages and dispatch to callbacks."""
        while True:
            pubsub = self._pattern_pubsub
            if pubsub is None:
                return
            try:
                async with self._pattern_io_lock:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                if not message:
                    continue
                if message.get("type") != "pmessage":
                    continue
                pattern = message.get("pattern")
                channel = message.get("channel")
                raw_data = message.get("data")
                if isinstance(pattern, bytes):
                    pattern = pattern.decode()
                if isinstance(channel, bytes):
                    channel = channel.decode()
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode()
                try:
                    data = json.loads(raw_data)
                except json.JSONDecodeError:
                    self.logger.error("Invalid JSON in %s", channel)
                    continue
                async with self._lock:
                    callbacks = list(self._pattern_callbacks.get(pattern, ()))
                for callback in callbacks:
                    await self._invoke_pattern_callback(callback, pattern, channel, data)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                self.logger.error("Pattern reader crashed: %s", exc)
                await asyncio.sleep(0.1)

    async def _ensure_channel_pubsub_locked(self) -> None:
        if self._channel_pubsub is None:
            self._channel_pubsub = self.redis.pubsub()
            self._channel_task = asyncio.create_task(self._channel_reader())

    async def _ensure_pattern_pubsub_locked(self) -> None:
        if self._pattern_pubsub is None:
            self._pattern_pubsub = self.redis.pubsub()
            self._pattern_task = asyncio.create_task(self._pattern_reader())

    async def _shutdown_channel_pubsub_locked(self) -> None:
        task = self._channel_task
        pubsub = self._channel_pubsub
        self._channel_task = None
        self._channel_pubsub = None
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if pubsub:
            with contextlib.suppress(Exception):
                await pubsub.close()

    async def _shutdown_pattern_pubsub_locked(self) -> None:
        task = self._pattern_task
        pubsub = self._pattern_pubsub
        self._pattern_task = None
        self._pattern_pubsub = None
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if pubsub:
            with contextlib.suppress(Exception):
                await pubsub.close()

    async def _unsubscribe_channel_callback(
        self,
        channel: str,
        callback: Callable[..., Any],
    ) -> None:
        pubsub: Any | None = None
        should_unsubscribe = False
        async with self._lock:
            callbacks = self._channel_callbacks.get(channel)
            if not callbacks:
                return
            with contextlib.suppress(ValueError):
                callbacks.remove(callback)
            if callbacks:
                return
            self._channel_callbacks.pop(channel, None)
            pubsub = self._channel_pubsub
            should_unsubscribe = pubsub is not None

        if should_unsubscribe and pubsub is not None:
            with contextlib.suppress(Exception):
                async with self._channel_io_lock:
                    await pubsub.unsubscribe(channel)

        async with self._lock:
            if self._channel_pubsub is pubsub and not self._channel_callbacks:
                await self._shutdown_channel_pubsub_locked()

    async def _unsubscribe_pattern_callback(
        self,
        pattern: str,
        callback: Callable[..., Any],
    ) -> None:
        pubsub: Any | None = None
        should_unsubscribe = False
        async with self._lock:
            callbacks = self._pattern_callbacks.get(pattern)
            if not callbacks:
                return
            with contextlib.suppress(ValueError):
                callbacks.remove(callback)
            if callbacks:
                return
            self._pattern_callbacks.pop(pattern, None)
            pubsub = self._pattern_pubsub
            should_unsubscribe = pubsub is not None

        if should_unsubscribe and pubsub is not None:
            with contextlib.suppress(Exception):
                async with self._pattern_io_lock:
                    await pubsub.punsubscribe(pattern)

        async with self._lock:
            if self._pattern_pubsub is pubsub and not self._pattern_callbacks:
                await self._shutdown_pattern_pubsub_locked()

    async def subscribe(self, channel: str, callback) -> "_Subscription":
        """Subscribe to a channel and run callback(message) for each event.

        Returns a ``_Subscription`` handle that can be used to cancel and
        clean up the callback registration.
        """
        pubsub: Any | None = None
        should_subscribe = False
        async with self._lock:
            await self._ensure_channel_pubsub_locked()
            should_subscribe = not self._channel_callbacks[channel]
            self._channel_callbacks[channel].append(callback)
            pubsub = self._channel_pubsub

        if should_subscribe and pubsub is not None:
            async with self._channel_io_lock:
                await pubsub.subscribe(channel)

        sub: _Subscription

        async def _cancel() -> None:
            await self._unsubscribe_channel_callback(channel, callback)
            async with self._lock:
                self._subscriptions.discard(sub)

        sub = _Subscription(_cancel)
        async with self._lock:
            self._subscriptions.add(sub)
        return sub

    async def psubscribe(self, pattern: str, callback) -> "_Subscription":
        """Subscribe to channels matching a glob pattern (Redis PSUBSCRIBE).

        Callback receives ``(channel, data)`` where *channel* is the
        actual channel name that matched the pattern.

        Returns a ``_Subscription`` handle for cleanup.
        """
        pubsub: Any | None = None
        should_subscribe = False
        async with self._lock:
            await self._ensure_pattern_pubsub_locked()
            should_subscribe = not self._pattern_callbacks[pattern]
            self._pattern_callbacks[pattern].append(callback)
            pubsub = self._pattern_pubsub

        if should_subscribe and pubsub is not None:
            async with self._pattern_io_lock:
                await pubsub.psubscribe(pattern)

        sub: _Subscription

        async def _cancel() -> None:
            await self._unsubscribe_pattern_callback(pattern, callback)
            async with self._lock:
                self._subscriptions.discard(sub)

        sub = _Subscription(_cancel)
        async with self._lock:
            self._subscriptions.add(sub)
        return sub

    async def cancel_subscription(self, sub: "_Subscription") -> None:
        """Cancel a single subscription and release its connection."""
        await sub.cancel()

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

    async def close(self) -> None:
        """Close all tracked subscriptions and the publish connection."""
        async with self._lock:
            subs = list(self._subscriptions)
            self._subscriptions.clear()

        if subs:
            await asyncio.gather(
                *(s.cancel() for s in subs),
                return_exceptions=True,
            )

        async with self._lock:
            self._channel_callbacks.clear()
            self._pattern_callbacks.clear()
            await self._shutdown_channel_pubsub_locked()
            await self._shutdown_pattern_pubsub_locked()

        await self.redis.close()
