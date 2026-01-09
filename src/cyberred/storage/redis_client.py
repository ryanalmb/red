"""Redis Sentinel client for stigmergic coordination.

Provides high-availability Redis connectivity with automatic failover
for pub/sub and streams operations (Story 3.1, NFR28).

Key Features:
- Redis Sentinel for master discovery and automatic failover
- Configurable connection pooling (default: 10 connections)
- Pub/Sub with HMAC signature validation
- Redis Streams support (xadd, xread)
- Exponential backoff for reconnection
- Local message buffering during connection loss (Story 3.2)

Usage:
    from cyberred.storage import RedisClient
    from cyberred.core.config import RedisConfig
    
    config = RedisConfig(
        sentinel_hosts=["sentinel1:26379", "sentinel2:26379"],
        master_name="mymaster",
    )
    
    async with RedisClient(config, engagement_id="eng-123") as client:
        await client.publish("channel", "message")
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Awaitable, Callable, Optional

import structlog

from cyberred.core.config import RedisConfig

log = structlog.get_logger()


# Default connection pool size
DEFAULT_POOL_SIZE = 10


# =============================================================================
# Story 3.2: Connection State Machine
# =============================================================================

class ConnectionState(Enum):
    """Connection state for Redis client state machine.
    
    States:
        DISCONNECTED: Not connected, no reconnection attempts.
        CONNECTING: Initial connection or reconnection in progress.
        CONNECTED: Healthy connection to master.
        DEGRADED: Connection lost, buffering enabled, reconnecting.
    """
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    DEGRADED = auto()


# =============================================================================
# Story 3.2: Exponential Backoff
# =============================================================================

def calculate_backoff(
    attempt: int, 
    max_delay: float = 10.0, 
    jitter: float = 0.1
) -> float:
    """Calculate exponential backoff delay with optional jitter.
    
    Args:
        attempt: Attempt number (0-indexed).
        max_delay: Maximum delay in seconds.
        jitter: Jitter factor (0.1 = ±10%).
        
    Returns:
        Delay in seconds.
    """
    base_delay = min(max_delay, 2 ** attempt)
    if jitter > 0:
        jitter_range = base_delay * jitter
        base_delay += random.uniform(-jitter_range, jitter_range)
    return base_delay


# =============================================================================
# Story 3.2: Message Buffer
# =============================================================================

@dataclass
class BufferedMessage:
    """A message buffered during connection loss.
    
    Attributes:
        channel: Redis channel name.
        message: Message content.
        timestamp: Time when message was buffered.
    """
    channel: str
    message: str
    timestamp: float = field(default_factory=time.time)


class MessageBuffer:
    """In-memory buffer for messages during Redis connection loss.
    
    Stores messages with timestamps and filters expired ones on drain.
    
    Attributes:
        max_size: Maximum number of messages to buffer.
        max_age_seconds: Maximum age of messages before expiry.
    """
    
    def __init__(
        self, 
        max_size: int = 1000, 
        max_age_seconds: float = 10.0
    ) -> None:
        """Initialize MessageBuffer.
        
        Args:
            max_size: Maximum messages to buffer (default: 1000).
            max_age_seconds: Maximum message age in seconds (default: 10.0).
        """
        self._max_size = max_size
        self._max_age_seconds = max_age_seconds
        self._messages: list[BufferedMessage] = []
    
    @property
    def size(self) -> int:
        """Current number of buffered messages."""
        return len(self._messages)
    
    @property
    def is_full(self) -> bool:
        """Whether buffer has reached max capacity."""
        return len(self._messages) >= self._max_size
    
    def add(self, channel: str, message: str) -> bool:
        """Add a message to the buffer.
        
        Args:
            channel: Redis channel name.
            message: Message content.
            
        Returns:
            True if added, False if buffer full.
        """
        if self.is_full:
            log.warning(
                "buffer_overflow",
                size=self.size,
                max_size=self._max_size,
            )
            return False
        
        self._messages.append(BufferedMessage(
            channel=channel,
            message=message,
            timestamp=time.time(),
        ))
        return True
    
    def drain(self) -> list[tuple[str, str]]:
        """Drain all non-expired messages from buffer.
        
        Returns:
            List of (channel, message) tuples.
        """
        now = time.time()
        cutoff = now - self._max_age_seconds
        
        valid_messages = []
        expired_count = 0
        
        for msg in self._messages:
            if msg.timestamp >= cutoff:
                valid_messages.append((msg.channel, msg.message))
            else:
                expired_count += 1
        
        if expired_count > 0:
            log.info(
                "buffer_message_expired",
                expired_count=expired_count,
                remaining=len(valid_messages),
            )
        
        self._messages.clear()
        return valid_messages


@dataclass
class PubSubSubscription:
    """Handle for an active pub/sub subscription.
    
    Attributes:
        pattern: The subscribed channel pattern (e.g., "findings:*").
        unsubscribe: Async callable to cancel the subscription.
    """
    pattern: str
    unsubscribe: Callable[[], Awaitable[None]]


@dataclass
class HealthStatus:
    """Health check result for Redis connection.
    
    Attributes:
        healthy: Whether the connection is healthy.
        latency_ms: Round-trip ping latency in milliseconds.
        master_addr: Current master address as "host:port" string.
    """
    healthy: bool
    latency_ms: float
    master_addr: str


class RedisClient:
    """Redis Sentinel client with automatic failover.
    
    Connects to Redis via Sentinel for high availability. Supports
    pub/sub messaging with HMAC signatures and Redis Streams for 
    stigmergic coordination.
    
    Attributes:
        config: Redis configuration including sentinel hosts.
        engagement_id: ID used for cryptographic key derivation.
        pool_size: Maximum number of connections in the pool.
        is_connected: Whether the client is currently connected.
    """
    
    def __init__(
        self, 
        config: RedisConfig, 
        engagement_id: str = "default-engagement",
        pool_size: int = DEFAULT_POOL_SIZE
    ) -> None:
        """Initialize RedisClient.
        
        Args:
            config: Redis configuration with sentinel hosts and master name.
            engagement_id: ID for key derivation (required for HMAC).
            pool_size: Maximum connections in pool (default: 10).
        """
        self._config = config
        self._engagement_id = engagement_id
        self._pool_size = pool_size
        self._is_connected = False
        self._sentinel: Optional[Any] = None
        self._master: Optional[Any] = None
        self._pubsub: Optional[Any] = None
        self._pubsub_task: Optional[Any] = None
        self._master_address: Optional[tuple[str, int]] = None
        self._callbacks: dict[str, list[Callable[[str, str], Awaitable[None]]]] = {}
        
        # Story 3.2: Connection state machine
        self._connection_state = ConnectionState.DISCONNECTED
        self._buffer = MessageBuffer()
        self._reconnection_task: Optional[asyncio.Task[None]] = None
        self._state_lock = asyncio.Lock()
        
        # Derive signing key
        from cyberred.core.keystore import derive_key
        # Use engagement_id as password, purpose as salt
        self._signing_key = derive_key(
            self._engagement_id, 
            salt=b"hmac-sha256"
        )
    
    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attributes to the underlying Redis master client."""
        if self._master:
            return getattr(self._master, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}' (not connected)")
    
    @property
    def pool_size(self) -> int:
        """Maximum connections in the pool."""
        return self._pool_size
    
    @property
    def is_connected(self) -> bool:
        """Whether client is connected to Redis master."""
        return self._is_connected
    
    @property
    def connection_state(self) -> ConnectionState:
        """Current connection state (Story 3.2 state machine)."""
        return self._connection_state
    
    @property
    def master_address(self) -> Optional[tuple[str, int]]:
        """Current master address (host, port) or None if not connected."""
        return self._master_address
    
    @property
    def pool_stats(self) -> dict[str, Any]:
        """Connection pool statistics for monitoring.
        
        Returns:
            Dict with pool_size, in_use, available, and created counts.
        """
        if not self._is_connected or not self._master:
            return {
                "pool_size": self._pool_size,
                "in_use": 0,
                "available": 0,
                "created": 0,
            }
        
        pool = self._master.connection_pool
        return {
            "pool_size": pool.max_connections,
            "in_use": len(pool._in_use_connections),
            "available": len(pool._available_connections),
            "created": pool._created_connections,
        }
    
    def _parse_sentinel_hosts(self) -> list[tuple[str, int]]:
        """Parse sentinel_hosts config into (host, port) tuples.
        
        Returns:
            List of (host, port) tuples for Sentinel nodes.
        """
        sentinels = []
        for host_port in self._config.sentinel_hosts:
            if ":" in host_port:
                host, port_str = host_port.rsplit(":", 1)
                sentinels.append((host, int(port_str)))
            else:
                # Default sentinel port 26379
                sentinels.append((host_port, 26379))
        return sentinels
    
    async def connect(self) -> None:
        """Establish connection to Redis via Sentinel.
        
        Discovers the master from Sentinel nodes and creates
        a connection pool.
        
        Raises:
            ConnectionError: If unable to connect to Sentinel or master.
        """
        if self._is_connected:
            return
        
        from redis.asyncio.sentinel import Sentinel
        
        # Parse sentinel_hosts using helper
        sentinels = self._parse_sentinel_hosts()
        
        # If no sentinels configured, use direct connection
        if not sentinels:
            log.warning(
                "redis_no_sentinels",
                host=self._config.host,
                port=self._config.port,
            )
            # Fall back to direct connection for non-HA setups
            import redis.asyncio as redis
            self._master = redis.Redis(
                host=self._config.host,
                port=self._config.port,
                max_connections=self._pool_size,
            )
            # Approximate master address for direct connection
            self._master_address = (self._config.host, self._config.port)
        else:
            self._sentinel = Sentinel(
                sentinels,
                socket_timeout=5.0,
            )
            # Create master connection with connection handling
            self._master = self._sentinel.master_for(
                self._config.master_name,
                socket_timeout=5.0,
                max_connections=self._pool_size,
            )
            
            # Try to discover master address for monitoring
            try:
                self._master_address = await self._sentinel.discover_master(
                    self._config.master_name
                )
            except Exception as e:
                log.warning("redis_master_discovery_failed_log_only", error=str(e))
        
        try:
            # Test connection
            await self._master.ping()
            self._is_connected = True
            self._connection_state = ConnectionState.CONNECTED
            
            log.info(
                "redis_connected",
                master_name=self._config.master_name,
                sentinel_count=len(sentinels),
                pool_size=self._pool_size,
                master_addr=self._master_address,
            )
        except Exception as e:
            # Check for failover
            log.error("redis_connection_failed", error=str(e))
            self._is_connected = False
            self._master = None
            raise ConnectionError(f"Failed to connect to Redis: {e}") from e
    
    async def close(self) -> None:
        """Close Redis connection gracefully."""
        # Story 3.2: Stop reconnection task first
        if self._reconnection_task:
            self._reconnection_task.cancel()
            try:
                await self._reconnection_task
            except (Exception, asyncio.CancelledError):
                pass
            self._reconnection_task = None
        
        # Stop listener task first
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except (Exception, asyncio.CancelledError):
                # Ignore cancellation errors during shutdown
                pass
            self._pubsub_task = None
            
        if self._pubsub:
            await self._pubsub.close()
            self._pubsub = None
        
        if self._master:
            await self._master.close()
            self._master = None
        
        self._sentinel = None
        self._is_connected = False
        self._connection_state = ConnectionState.DISCONNECTED
        
        log.info("redis_disconnected")
    
    # ==========================================================================
    # Story 3.2: Reconnection Loop
    # ==========================================================================
    
    async def _connect_to_master(self) -> bool:
        """Attempt to connect to Redis master.
        
        Returns:
            True if connected successfully, False otherwise.
        """
        try:
            await self.connect()
            self._connection_state = ConnectionState.CONNECTED
            return True
        except Exception as e:
            log.debug("reconnect_attempt_failed", error=str(e))
            return False
    
    async def _reconnection_loop(self) -> None:
        """Background reconnection loop with exponential backoff.
        
        Runs until connection is re-established or cancelled.
        """
        attempt = 0
        
        while self._connection_state == ConnectionState.DEGRADED:
            delay = calculate_backoff(attempt, max_delay=10.0, jitter=0.1)
            
            log.info(
                "redis_reconnect_attempt",
                attempt=attempt + 1,
                delay_seconds=delay,
            )
            
            await asyncio.sleep(delay)
            
            if await self._connect_to_master():
                log.info(
                    "redis_reconnected",
                    master_addr=self._master_address,
                    attempt_count=attempt + 1,
                )
                await self._flush_buffer()
                break
            
            attempt += 1
    
    async def _flush_buffer(self) -> None:
        """Flush buffered messages after reconnection.
        
        Drains the buffer and republishes all valid messages.
        """
        messages = self._buffer.drain()
        
        if not messages:
            return
        
        success_count = 0
        fail_count = 0
        
        for channel, message in messages:
            try:
                signed_package = self._sign_message(message)
                await self._master.publish(channel, signed_package)
                success_count += 1
            except Exception as e:
                log.warning(
                    "buffer_flush_failed",
                    channel=channel,
                    error=str(e),
                )
                fail_count += 1
        
        log.info(
            "buffer_flushed",
            success_count=success_count,
            fail_count=fail_count,
        )
    
    def _handle_connection_lost(self) -> None:
        """Handle connection loss event (Story 3.2).
        
        Transitions to DEGRADED state and logs the event.
        """
        if self._connection_state == ConnectionState.DEGRADED:
            return  # Already in degraded mode
        
        master_addr = ""
        if self._master_address:
            master_addr = f"{self._master_address[0]}:{self._master_address[1]}"
        
        log.warning(
            "redis_connection_lost",
            master_addr=master_addr,
            timestamp=time.time(),
        )
        
        self._connection_state = ConnectionState.DEGRADED
        self._is_connected = False
        
        # Start reconnection loop
        if not self._reconnection_task or self._reconnection_task.done():
            self._reconnection_task = asyncio.create_task(self._reconnection_loop())
    
    async def __aenter__(self) -> "RedisClient":
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Async context manager exit."""
        await self.close()
    
    def _sign_message(self, content: str) -> str:
        """Create signed message package.
        
        Args:
            content: Raw message content.
            
        Returns:
            JSON string containing content and HMAC signature.
        """
        import hmac
        import hashlib
        import json
        import time
        
        # Calculate HMAC
        h = hmac.new(
            self._signing_key, 
            content.encode("utf-8"), 
            hashlib.sha256
        )
        sig = h.hexdigest()
        
        # Structure as JSON
        package = {
            "content": content,
            "sig": sig,
            "ts": time.time()
        }
        return json.dumps(package)
    
    def _verify_message(self, package_json: str) -> Optional[str]:
        """Verify signature and return content.
        
        Args:
            package_json: JSON string with content and signature.
            
        Returns:
            Original content if valid, None otherwise.
        """
        import hmac
        import hashlib
        import json
        
        try:
            data = json.loads(package_json)
            content = data.get("content")
            sig = data.get("sig")
            
            if not content or not sig:
                return None
            
            # Verify signature
            h = hmac.new(
                self._signing_key, 
                content.encode("utf-8"), 
                hashlib.sha256
            )
            expected_sig = h.hexdigest()
            
            if hmac.compare_digest(sig, expected_sig):
                return content
            
            log.warning("redis_invalid_signature", sig=sig)
            return None
            
        except json.JSONDecodeError:
            log.warning("redis_invalid_json_message")
            return None
        except Exception as e:
            log.warning("redis_verification_error", error=str(e))
            return None

    async def _pubsub_listener(self) -> None:
        """Background task to process incoming messages."""
        if not self._pubsub:
            return
            
        import asyncio
        try:
            async for message in self._pubsub.listen():
                if message["type"] != "pmessage":
                    continue
                
                # Check callbacks for this channel/pattern
                # Note: Redis returns the specific channel, but we subscribe by pattern.
                # However, python redis client's pmessage includes 'pattern' key.
                pattern = message.get("pattern")
                if isinstance(pattern, bytes):
                    pattern = pattern.decode("utf-8")
                
                # We need data and channel
                channel = message["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode("utf-8")
                
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                
                if pattern and pattern in self._callbacks:
                    # Verify signature
                    verified_content = self._verify_message(data)
                    
                    if verified_content:
                        # invoke all callbacks for this pattern
                        for callback in self._callbacks[pattern]:
                            try:
                                await callback(channel, verified_content)
                            except Exception as e:
                                log.error("redis_callback_error", error=str(e))
        except asyncio.CancelledError:
            # Task was cancelled, exit gracefully
            return
        except BaseException as e:
            # Catch all other errors (including generator exit etc) to prevent crash
            if "CancelledError" not in str(type(e).__name__):
                log.error("redis_listener_crashed", error=str(e))

    # ====================
    # Task 5: Pub/Sub Publish
    # ====================
    
    async def publish(self, channel: str, message: str) -> int:
        """Publish a message to a Redis channel.
        
        Args:
            channel: Channel name (e.g., "findings:a1b2c3:sqli").
            message: Message content to publish.
            
        Returns:
            Number of subscribers that received the message.
            Returns 0 if message was buffered (DEGRADED state).
            
        Raises:
            ConnectionError: If not connected to Redis and not in DEGRADED state.
        """
        # Story 3.2: Buffer messages when in DEGRADED state
        if self._connection_state == ConnectionState.DEGRADED:
            self._buffer.add(channel, message)
            log.debug(
                "message_buffered",
                channel=channel,
                buffer_size=self._buffer.size,
            )
            return 0
        
        if not self._is_connected or not self._master:
            raise ConnectionError("Not connected to Redis")
        
        try:
            # Sign message before publishing
            signed_package = self._sign_message(message)
            
            result = await self._master.publish(channel, signed_package)
            
            log.debug(
                "redis_publish",
                channel=channel,
                content_len=len(message),
                package_len=len(signed_package),
                subscribers=result,
            )
            
            return result
        except Exception as e:
            if "ConnectionError" in str(type(e).__name__):
                log.warning("redis_publish_failed_connection", error=str(e))
                # Story 3.2: Transition to DEGRADED and buffer the message
                self._handle_connection_lost()
                self._buffer.add(channel, message)
                return 0
            raise
    
    # ====================
    # Task 6: Pub/Sub Subscribe
    # ====================
    
    async def subscribe(
        self,
        pattern: str,
        callback: Callable[[str, str], Awaitable[None]],
    ) -> PubSubSubscription:
        """Subscribe to Redis channels matching a pattern.
        
        Args:
            pattern: Channel pattern (e.g., "findings:*").
            callback: Async function(channel, message) called for each message.
            
        Returns:
            PubSubSubscription handle for unsubscribing.
            
        Raises:
            ConnectionError: If not connected to Redis.
        """
        import asyncio
        if not self._is_connected or not self._master:
            raise ConnectionError("Not connected to Redis")
        
        # Create pubsub connection if needed
        if not self._pubsub:
            self._pubsub = self._master.pubsub()
            # Start listener loop
            self._pubsub_task = asyncio.create_task(self._pubsub_listener())
        
        # Validated pattern subscription
        if pattern not in self._callbacks:
            self._callbacks[pattern] = []
            # Only subscribe if new pattern
            await self._pubsub.psubscribe(pattern)
        
        self._callbacks[pattern].append(callback)
        
        log.info("redis_subscribed", pattern=pattern)
        
        # Return subscription handle
        async def unsubscribe() -> None:
            if pattern in self._callbacks:
                if callback in self._callbacks[pattern]:
                    self._callbacks[pattern].remove(callback)
                
                # If no more callbacks for this pattern, unsubscribe from Redis
                if not self._callbacks[pattern] and self._pubsub:
                    await self._pubsub.punsubscribe(pattern)
                    del self._callbacks[pattern]
                    log.info("redis_unsubscribed", pattern=pattern)
        
        return PubSubSubscription(pattern=pattern, unsubscribe=unsubscribe)
    
    # ====================
    # Task 7: Redis Streams xadd (Story 3.4: with HMAC signing)
    # ====================
    
    async def xadd(
        self,
        stream: str,
        fields: dict[str, Any],
        maxlen: Optional[int] = None,
    ) -> str:
        """Append an entry to a Redis Stream with HMAC signature.
        
        Args:
            stream: Stream name (e.g., "audit:stream").
            fields: Field-value pairs for the entry.
            maxlen: Optional max stream length (for exact trimming).
            
        Returns:
            Entry ID assigned by Redis (timestamp-sequence string).
            
        Raises:
            ConnectionError: If not connected to Redis.
            
        Note:
            Payload is serialized to JSON and signed with HMAC-SHA256.
            Use xread/xreadgroup with verification to consume messages.
        """
        import json
        
        if not self._is_connected or not self._master:
            raise ConnectionError("Not connected to Redis")
        
        # Serialize fields to JSON and sign with HMAC-SHA256
        payload_json = json.dumps(fields)
        signed_payload = self._sign_message(payload_json)
        
        try:
            # Store signed payload as single field for integrity
            entry_id = await self._master.xadd(
                stream, 
                {"payload": signed_payload}, 
                maxlen=maxlen, 
                approximate=False
            )
            
            log.info(
                "stream_message_added",
                stream=stream,
                entry_id=entry_id,
                field_count=len(fields),
            )
            
            # Redis returns bytes, decode to str
            if isinstance(entry_id, bytes):
                entry_id = entry_id.decode("utf-8")
            
            return entry_id
        except Exception as e:
            if "ConnectionError" in str(type(e).__name__):
                log.warning("redis_xadd_failed_connection", error=str(e))
                self._is_connected = False
                raise ConnectionError(f"Connection lost during xadd: {e}") from e
            raise


    # ====================
    # Task 8: Key-Value Operations (Story 5.8)
    # ====================

    async def get(self, key: str) -> Any:
        """Get value by key.
        
        Args:
            key: Redis key.
            
        Returns:
            Value if key exists, None otherwise.
            
        Raises:
            ConnectionError: If not connected.
        """
        if not self._is_connected or not self._master:
            raise ConnectionError("Not connected to Redis")
        return await self._master.get(key)

    async def setex(self, key: str, time: int | Any, value: Any) -> Any:
        """Set the value and expiration of a key.
        
        Args:
            key: Redis key.
            time: Seconds to expire.
            value: Value to set.
            
        Returns:
            True if successful.
            
        Raises:
            ConnectionError: If not connected.
        """
        if not self._is_connected or not self._master:
            raise ConnectionError("Not connected to Redis")
        return await self._master.setex(key, time, value)

    async def delete(self, *names: str) -> int:
        """Delete one or more keys.
        
        Args:
            names: Keys to delete.
            
        Returns:
            Number of keys deleted.
            
        Raises:
            ConnectionError: If not connected.
        """
        if not self._is_connected or not self._master:
            raise ConnectionError("Not connected to Redis")
        return await self._master.delete(*names)

    async def keys(self, pattern: str) -> list:
        """Returns a list of keys matching pattern.
        
        Args:
            pattern: Glob pattern to match.
            
        Returns:
            List of keys.
            
        Raises:
            ConnectionError: If not connected.
        """
        if not self._is_connected or not self._master:
            raise ConnectionError("Not connected to Redis")
        return await self._master.keys(pattern)

    async def exists(self, *names: str) -> int:
        """Returns the number of keys that exist.
        
        Args:
            names: Keys to check.
            
        Returns:
            Number of existing keys.
            
        Raises:
            ConnectionError: If not connected.
        """
        if not self._is_connected or not self._master:
            raise ConnectionError("Not connected to Redis")
        return await self._master.exists(*names)

    
    # ====================
    # Task 7b: Redis Streams xread (Story 3.4: with HMAC verification)
    # ====================
    
    async def xread(
        self,
        stream: str,
        last_id: str,
        count: int = 1,
        block_ms: int | None = None,
    ) -> list[tuple[str, dict]]:
        """Read entries from a Redis Stream with HMAC verification.
        
        Args:
            stream: Stream name (e.g., "audit:stream").
            last_id: Last message ID to read after (use "0" for all).
            count: Maximum entries to read.
            block_ms: Optional milliseconds to block waiting for data.
            
        Returns:
            List of (entry_id, data_dict) tuples with verified data.
            Tampered messages are skipped and logged.
            
        Raises:
            ConnectionError: If not connected to Redis.
        """
        import json
        
        if not self._is_connected or not self._master:
            raise ConnectionError("Not connected to Redis")
        
        try:
            result = await self._master.xread(
                {stream: last_id}, 
                count=count, 
                block=block_ms
            )
            
            if not result:
                return []
            
            verified_messages: list[tuple[str, dict]] = []
            tampered_count = 0
            
            # Process each stream's messages
            for stream_name, messages in result:
                for entry_id, fields in messages:
                    # Decode bytes if needed
                    if isinstance(entry_id, bytes):
                        entry_id = entry_id.decode("utf-8")
                    
                    # Get payload field
                    payload = fields.get(b"payload") or fields.get("payload")
                    if isinstance(payload, bytes):
                        payload = payload.decode("utf-8")
                    
                    if not payload:
                        log.warning(
                            "security_audit_tampered_message",
                            message_id=entry_id,
                            reason="missing_payload",
                        )
                        tampered_count += 1
                        continue
                    
                    # Verify HMAC signature
                    verified_content = self._verify_message(payload)
                    if verified_content is None:
                        log.warning(
                            "security_audit_tampered_message",
                            message_id=entry_id,
                            reason="invalid_signature",
                        )
                        tampered_count += 1
                        continue
                    
                    # Parse JSON data
                    try:
                        data = json.loads(verified_content)
                    except json.JSONDecodeError:
                        log.warning(
                            "security_audit_tampered_message",
                            message_id=entry_id,
                            reason="invalid_json",
                        )
                        tampered_count += 1
                        continue
                    
                    verified_messages.append((entry_id, data))
            
            log.info(
                "stream_messages_read",
                stream=stream,
                count=len(verified_messages),
                tampered_count=tampered_count,
            )
            
            return verified_messages
        except Exception as e:
            if "ConnectionError" in str(type(e).__name__):
                log.warning("redis_xread_failed_connection", error=str(e))
                self._is_connected = False
                raise ConnectionError(f"Connection lost during xread: {e}") from e
            raise
    
    # ====================
    # Story 3.4 Task 3: Consumer Group Create
    # ====================
    
    async def xgroup_create(
        self,
        stream: str,
        group: str,
        start_id: str = "$",
        mkstream: bool = True,
    ) -> bool:
        """Create a consumer group for a Redis Stream.
        
        Args:
            stream: Stream name (e.g., "audit:stream").
            group: Consumer group name.
            start_id: ID from which to start reading ("$" = new messages only).
            mkstream: Create stream if it doesn't exist.
            
        Returns:
            True if group created, False if already exists.
            
        Raises:
            ConnectionError: If not connected to Redis.
        """
        if not self._is_connected or not self._master:
            raise ConnectionError("Not connected to Redis")
        
        try:
            await self._master.xgroup_create(
                stream, group, start_id, mkstream=mkstream
            )
            log.info(
                "consumer_group_created",
                stream=stream,
                group=group,
                start_id=start_id,
            )
            return True
        except Exception as e:
            # Handle BUSYGROUP error (group already exists)
            if "BUSYGROUP" in str(e):
                log.debug(
                    "consumer_group_exists",
                    stream=stream,
                    group=group,
                )
                return False
            if "ConnectionError" in str(type(e).__name__):
                log.warning("redis_xgroup_create_failed_connection", error=str(e))
                self._is_connected = False
                raise ConnectionError(f"Connection lost during xgroup_create: {e}") from e
            raise
    
    # ====================
    # Story 3.4 Task 4: Consumer Group Read
    # ====================
    
    async def xreadgroup(
        self,
        group: str,
        consumer_name: str,
        stream: str,
        count: int = 10,
        block_ms: int | None = None,
    ) -> list[tuple[str, dict]]:
        """Read entries from a stream as a consumer group member.
        
        Args:
            group: Consumer group name.
            consumer_name: Consumer identifier within the group.
            stream: Stream name.
            count: Maximum entries to read.
            block_ms: Optional milliseconds to block waiting for data.
            
        Returns:
            List of (entry_id, data_dict) tuples with verified data.
            Tampered messages are skipped (not yielded, not acknowledged).
            
        Raises:
            ConnectionError: If not connected to Redis.
        """
        import json
        
        if not self._is_connected or not self._master:
            raise ConnectionError("Not connected to Redis")
        
        try:
            result = await self._master.xreadgroup(
                group, consumer_name, 
                {stream: ">"},  # ">" = only new undelivered messages
                count=count, 
                block=block_ms
            )
            
            if not result:
                return []
            
            verified_messages: list[tuple[str, dict]] = []
            tampered_count = 0
            
            # Process messages with HMAC verification
            for stream_name, messages in result:
                for entry_id, fields in messages:
                    if isinstance(entry_id, bytes):
                        entry_id = entry_id.decode("utf-8")
                    
                    # Get payload
                    payload = fields.get(b"payload") or fields.get("payload")
                    if isinstance(payload, bytes):
                        payload = payload.decode("utf-8")
                    
                    if not payload:
                        log.warning(
                            "security_audit_tampered_message",
                            message_id=entry_id,
                            consumer=consumer_name,
                            reason="missing_payload",
                        )
                        tampered_count += 1
                        continue
                    
                    # Verify HMAC
                    verified_content = self._verify_message(payload)
                    if verified_content is None:
                        log.warning(
                            "security_audit_tampered_message",
                            message_id=entry_id,
                            consumer=consumer_name,
                            reason="invalid_signature",
                        )
                        tampered_count += 1
                        continue
                    
                    # Parse JSON
                    try:
                        data = json.loads(verified_content)
                    except json.JSONDecodeError:
                        log.warning(
                            "security_audit_tampered_message",
                            message_id=entry_id,
                            consumer=consumer_name,
                            reason="invalid_json",
                        )
                        tampered_count += 1
                        continue
                    
                    verified_messages.append((entry_id, data))
            
            log.info(
                "consumer_messages_read",
                stream=stream,
                group=group,
                consumer=consumer_name,
                count=len(verified_messages),
                tampered_count=tampered_count,
            )
            
            return verified_messages
        except Exception as e:
            if "ConnectionError" in str(type(e).__name__):
                log.warning("redis_xreadgroup_failed_connection", error=str(e))
                self._is_connected = False
                raise ConnectionError(f"Connection lost during xreadgroup: {e}") from e
            raise
    
    # ====================
    # Story 3.4 Task 5: Acknowledge Messages
    # ====================
    
    async def xack(
        self,
        stream: str,
        group: str,
        *message_ids: str,
    ) -> int:
        """Acknowledge messages as processed by consumer group.
        
        Args:
            stream: Stream name.
            group: Consumer group name.
            *message_ids: One or more message IDs to acknowledge.
            
        Returns:
            Number of messages successfully acknowledged.
            
        Raises:
            ConnectionError: If not connected to Redis.
        """
        if not self._is_connected or not self._master:
            raise ConnectionError("Not connected to Redis")
        
        if not message_ids:
            return 0
        
        try:
            count = await self._master.xack(stream, group, *message_ids)
            
            log.info(
                "messages_acknowledged",
                stream=stream,
                group=group,
                acknowledged_count=count,
                message_ids=list(message_ids),
            )
            
            return count
        except Exception as e:
            if "ConnectionError" in str(type(e).__name__):
                log.warning("redis_xack_failed_connection", error=str(e))
                self._is_connected = False
                raise ConnectionError(f"Connection lost during xack: {e}") from e
            raise
    
    # ====================
    # Story 3.4 Task 6: Pending Info and Claim
    # ====================
    
    async def xpending(
        self,
        stream: str,
        group: str,
    ) -> dict:
        """Get pending message info for a consumer group.
        
        Args:
            stream: Stream name.
            group: Consumer group name.
            
        Returns:
            Dict with pending info:
            - count: Total pending messages
            - min_id: Oldest pending message ID (or None)
            - max_id: Newest pending message ID (or None)
            - consumers: Dict of consumer_name -> pending_count
            
        Raises:
            ConnectionError: If not connected to Redis.
        """
        if not self._is_connected or not self._master:
            raise ConnectionError("Not connected to Redis")
        
        try:
            result = await self._master.xpending(stream, group)
            
            # Handle empty result (no pending messages)
            if not result or (isinstance(result, (list, tuple)) and len(result) == 0):
                return {
                    "count": 0,
                    "min_id": None,
                    "max_id": None,
                    "consumers": {},
                }
            
            # Parse result: [count, min_id, max_id, [[consumer, count], ...]]
            # Note: May be a dict or list depending on redis-py version
            if isinstance(result, dict):
                # Redis-py returns dict format
                pending_info = {
                    "count": result.get("pending", 0),
                    "min_id": result.get("min", None),
                    "max_id": result.get("max", None),
                    "consumers": {},
                }
                if isinstance(pending_info["min_id"], bytes):
                    pending_info["min_id"] = pending_info["min_id"].decode("utf-8")
                if isinstance(pending_info["max_id"], bytes):
                    pending_info["max_id"] = pending_info["max_id"].decode("utf-8")
                consumers = result.get("consumers", [])
                for consumer_data in consumers:
                    if isinstance(consumer_data, dict):
                        name = consumer_data.get("name", b"").decode("utf-8") if isinstance(consumer_data.get("name"), bytes) else str(consumer_data.get("name", ""))
                        count = consumer_data.get("pending", 0)
                    else:
                        name = consumer_data[0].decode("utf-8") if isinstance(consumer_data[0], bytes) else str(consumer_data[0])
                        count = int(consumer_data[1])
                    pending_info["consumers"][name] = count
            else:
                # List format: [count, min_id, max_id, [[consumer, count], ...]]
                pending_info = {
                    "count": result[0] if result else 0,
                    "min_id": result[1].decode("utf-8") if result and result[1] else None,
                    "max_id": result[2].decode("utf-8") if result and result[2] else None,
                    "consumers": {},
                }
                
                if result and len(result) > 3 and result[3]:
                    for consumer_data in result[3]:
                        consumer_name = consumer_data[0]
                        if isinstance(consumer_name, bytes):
                            consumer_name = consumer_name.decode("utf-8")
                        pending_count = int(consumer_data[1])
                        pending_info["consumers"][consumer_name] = pending_count
            
            log.debug(
                "pending_info_retrieved",
                stream=stream,
                group=group,
                pending_count=pending_info["count"],
            )
            
            return pending_info
        except Exception as e:
            if "ConnectionError" in str(type(e).__name__):
                log.warning("redis_xpending_failed_connection", error=str(e))
                self._is_connected = False
                raise ConnectionError(f"Connection lost during xpending: {e}") from e
            raise
    
    async def xclaim(
        self,
        stream: str,
        group: str,
        consumer_name: str,
        min_idle_time: int,
        message_ids: list[str],
    ) -> list[tuple[str, dict]]:
        """Claim pending messages for a consumer.
        
        Used for redelivery of messages stuck with crashed consumers.
        
        Args:
            stream: Stream name.
            group: Consumer group name.
            consumer_name: Consumer to claim messages for.
            min_idle_time: Minimum idle time in milliseconds.
            message_ids: List of message IDs to claim.
            
        Returns:
            List of (entry_id, data_dict) tuples for claimed messages.
            Messages with invalid signatures are skipped.
            
        Raises:
            ConnectionError: If not connected to Redis.
        """
        import json
        
        if not self._is_connected or not self._master:
            raise ConnectionError("Not connected to Redis")
        
        if not message_ids:
            return []
        
        try:
            result = await self._master.xclaim(
                stream, group, consumer_name, min_idle_time, message_ids
            )
            
            if not result:
                return []
            
            claimed_messages: list[tuple[str, dict]] = []
            
            for entry_id, fields in result:
                if isinstance(entry_id, bytes):
                    entry_id = entry_id.decode("utf-8")
                
                # Get and verify payload
                payload = fields.get(b"payload") or fields.get("payload")
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8")
                
                if not payload:
                    log.warning(
                        "security_audit_tampered_message",
                        message_id=entry_id,
                        reason="missing_payload_claim",
                    )
                    continue
                
                verified_content = self._verify_message(payload)
                if verified_content is None:
                    log.warning(
                        "security_audit_tampered_message",
                        message_id=entry_id,
                        reason="invalid_signature_claim",
                    )
                    continue
                
                try:
                    data = json.loads(verified_content)
                    claimed_messages.append((entry_id, data))
                except json.JSONDecodeError:
                    log.warning(
                        "security_audit_tampered_message",
                        message_id=entry_id,
                        reason="invalid_json_claim",
                    )
                    continue
            
            log.info(
                "audit_pending_claimed",
                stream=stream,
                group=group,
                consumer=consumer_name,
                claimed_count=len(claimed_messages),
            )
            
            return claimed_messages
        except Exception as e:
            if "ConnectionError" in str(type(e).__name__):
                log.warning("redis_xclaim_failed_connection", error=str(e))
                self._is_connected = False
                raise ConnectionError(f"Connection lost during xclaim: {e}") from e
            raise
    
    # ====================
    # Task 9: Health Check
    # ====================
    
    async def health_check(self) -> HealthStatus:
        """Check Redis connection health and measure latency.
        
        Pings the Redis master and measures round-trip time.
        
        Returns:
            HealthStatus with healthy flag, latency, and master address.
            
        Raises:
            ConnectionError: If not connected to Redis.
        """
        import time
        
        if not self._is_connected or not self._master:
            return HealthStatus(
                healthy=False,
                latency_ms=0.0,
                master_addr="",
            )
        
        try:
            start = time.perf_counter()
            await self._master.ping()
            latency_ms = (time.perf_counter() - start) * 1000
            
            # Get master address from discovery if available or connection settings
            master_addr = f"{self._config.host}:{self._config.port}"
            if self._master_address:
                master_addr = f"{self._master_address[0]}:{self._master_address[1]}"
            else:
                # Try to check connection pool connection kwargs often has address
                try:
                    conn_kwargs = self._master.connection_pool.connection_kwargs
                    if 'host' in conn_kwargs and 'port' in conn_kwargs:
                        master_addr = f"{conn_kwargs['host']}:{conn_kwargs['port']}"
                except Exception:
                    pass
            
            log.debug(
                "redis_health_check",
                healthy=True,
                latency_ms=latency_ms,
                master_addr=master_addr,
            )
            
            return HealthStatus(
                healthy=True,
                latency_ms=latency_ms,
                master_addr=master_addr,
            )
        except Exception as e:
            # Emit master changed event on health check failure
            if self._is_connected:
                log.warning("REDIS_MASTER_CHANGED", reason="health_check_failed", error=str(e))
                self._is_connected = False
                
            log.warning("redis_health_check_failed", error=str(e))
            return HealthStatus(
                healthy=False,
                latency_ms=0.0,
                master_addr="",
            )
