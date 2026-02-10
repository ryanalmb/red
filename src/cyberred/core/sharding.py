"""Stigmergic Topic Sharding for scale (Story 7.13).

Provides ShardedTopic, ShardedEventBus, and ShardAggregator to prevent
"stigmergic storm" when 10K agents subscribe to findings channels.

Per architecture pre-mortem (P1): Topic sharding prevents Redis 100% CPU
when 10K agents subscribe to `findings:*`. Sharding uses `findings:shard:{hash mod N}:{type}`.

Key Components:
- ShardedTopic: Consistent hashing for target->shard mapping
- ShardedEventBus: Wrapper that transparently shards findings pub/sub
- ShardAggregator: Batches and deduplicates findings across shards

NFR1: Agent coordination latency <1s stigmergic propagation
NFR8: Scale to 10K concurrent agents without Redis overload
"""

from __future__ import annotations

import asyncio
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import structlog

from cyberred.core.config import get_settings

if TYPE_CHECKING:
    from cyberred.core.events import EventBus

log = structlog.get_logger()

# Default shard count (power of 2 recommended for hash distribution)
DEFAULT_SHARD_COUNT = 16

# Default batch window for aggregator
AGGREGATOR_BATCH_MS = 100


# =============================================================================
# ShardedTopic - Consistent hashing for topic sharding
# =============================================================================


@dataclass
class ShardedTopic:
    """Manages sharded topic naming for stigmergic channels.

    Per architecture pre-mortem (line 92): Topic sharding prevents
    "stigmergic storm" when 10K agents subscribe to findings.

    Attributes:
        base_topic: Base topic name (e.g., "findings")
        shard_count: Number of shards (default 16, must be > 0)
    """

    base_topic: str
    shard_count: int = DEFAULT_SHARD_COUNT

    def __post_init__(self) -> None:
        """Validate shard_count after initialization."""
        if self.shard_count <= 0:
            raise ValueError(f"shard_count must be > 0, got {self.shard_count}")

    def get_shard(self, target_hash: str) -> int:
        """Get shard number for target using consistent hashing.

        Uses MD5 for fast, consistent distribution (not cryptographic security).

        Args:
            target_hash: Hash of the target (IP, URL, etc.)

        Returns:
            Shard number (0 to shard_count-1)
        """
        # Use MD5 for fast, consistent distribution
        hash_bytes = hashlib.md5(target_hash.encode()).digest()
        hash_int = int.from_bytes(hash_bytes[:4], byteorder="big")
        return hash_int % self.shard_count

    def get_channel(self, target_hash: str, finding_type: str) -> str:
        """Get sharded channel name for publishing.

        Args:
            target_hash: Hash of the target
            finding_type: Type of finding (sqli, xss, etc.)

        Returns:
            Sharded channel name: findings:shard:{N}:{type}
        """
        shard = self.get_shard(target_hash)
        return f"{self.base_topic}:shard:{shard}:{finding_type}"

    def get_all_shard_patterns(self, finding_type: str = "*") -> list[str]:
        """Get all shard channel patterns for subscription.

        Args:
            finding_type: Optional filter by type, default "*" for all

        Returns:
            List of channel patterns to subscribe to
        """
        return [
            f"{self.base_topic}:shard:{i}:{finding_type}"
            for i in range(self.shard_count)
        ]


# =============================================================================
# ShardedEventBus - Transparent sharding wrapper
# =============================================================================


class ShardedEventBus:
    """Event bus with transparent topic sharding for scale.

    Wraps EventBus to provide sharded pub/sub while maintaining
    backward compatibility with non-sharded channels.

    Example:
        sharded_bus = ShardedEventBus(event_bus, shard_count=16)
        await sharded_bus.publish_finding(target_hash, "sqli", {"id": "f1"})
        await sharded_bus.subscribe_findings(callback)
    """

    def __init__(
        self,
        event_bus: EventBus,
        shard_count: int | None = None,
    ) -> None:
        """Initialize ShardedEventBus.

        Args:
            event_bus: Underlying EventBus instance.
            shard_count: Number of shards (uses config if not provided).
        """
        self._bus = event_bus
        
        # Get shard count from config or use provided/default
        if shard_count is not None:
            self._shard_count = shard_count
        else:
            try:
                settings = get_settings()
                self._shard_count = getattr(
                    settings.redis, "shard_count", DEFAULT_SHARD_COUNT
                )
            except Exception:
                self._shard_count = DEFAULT_SHARD_COUNT

        self._findings_topic = ShardedTopic("findings", self._shard_count)
        self._log = log.bind(component="sharded_event_bus", shards=self._shard_count)

    @property
    def shard_count(self) -> int:
        """Get the configured shard count."""
        return self._shard_count

    async def publish_finding(
        self,
        target_hash: str,
        finding_type: str,
        message: dict[str, Any],
    ) -> None:
        """Publish finding to sharded channel.

        Args:
            target_hash: Hash of the target
            finding_type: Type of finding
            message: Finding message payload
        """
        channel = self._findings_topic.get_channel(target_hash, finding_type)
        await self._bus.publish(channel, message)
        self._log.debug(
            "finding_published_sharded",
            channel=channel,
            shard=self._findings_topic.get_shard(target_hash),
        )

    async def subscribe_findings(
        self,
        callback: Callable[[str, dict], Awaitable[None]],
        finding_type: str = "*",
        shard_subset: list[int] | None = None,
    ) -> list:
        """Subscribe to findings across shards.

        Args:
            callback: Async callback(channel, message)
            finding_type: Filter by type, default all
            shard_subset: Optional list of specific shards to subscribe

        Returns:
            List of subscription tasks/handles
        """
        if shard_subset:
            patterns = [
                f"findings:shard:{i}:{finding_type}"
                for i in shard_subset
            ]
        else:
            patterns = self._findings_topic.get_all_shard_patterns(finding_type)

        tasks = []
        for pattern in patterns:
            task = await self._bus.psubscribe(pattern, callback)
            tasks.append(task)

        self._log.info(
            "subscribed_to_shards",
            shard_count=len(patterns),
            finding_type=finding_type,
        )
        return tasks

    # Passthrough for non-sharded channels
    async def publish(self, channel: str, message: dict) -> None:
        """Publish to non-sharded channel (passthrough)."""
        await self._bus.publish(channel, message)

    async def subscribe(self, channel: str, callback: Callable) -> Any:
        """Subscribe to non-sharded channel (passthrough)."""
        return await self._bus.subscribe(channel, callback)


# =============================================================================
# AggregatedBatch - Batch container with deduplication
# =============================================================================


@dataclass
class AggregatedBatch:
    """Batch of deduplicated findings.

    Stores findings with deduplication based on finding ID or
    fallback key (target + type + agent_id).
    """

    findings: list[dict[str, Any]] = field(default_factory=list)
    seen_ids: set[str] = field(default_factory=set)
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))

    def add(self, finding: dict[str, Any]) -> bool:
        """Add finding if not duplicate.

        Args:
            finding: Finding dict to add.

        Returns:
            True if added, False if duplicate.
        """
        # Dedupe key: finding_id OR content hash for unique identification
        finding_id = finding.get("id") or finding.get("data", {}).get("id")
        if not finding_id:
            # Fallback: Generate hash of full finding content to avoid false deduplication
            # This ensures findings with different payloads are not incorrectly deduplicated
            import json
            content_str = json.dumps(finding, sort_keys=True, default=str)
            finding_id = hashlib.md5(content_str.encode()).hexdigest()

        if finding_id in self.seen_ids:
            return False

        self.seen_ids.add(finding_id)
        self.findings.append(finding)
        return True


# =============================================================================
# ShardAggregator - Batch and deduplicate across shards
# =============================================================================


class ShardAggregator:
    """Aggregates findings from all shards with batching and deduplication.

    Per architecture pre-mortem: Aggregation service batches and deduplicates
    across shards to prevent downstream overload.

    Example:
        aggregator = ShardAggregator(event_bus, "eng123", shard_count=16)
        await aggregator.start()
        # ... findings are batched and published to findings:aggregated:eng123
        await aggregator.stop()
    """

    def __init__(
        self,
        event_bus: EventBus,
        engagement_id: str,
        shard_count: int = DEFAULT_SHARD_COUNT,
        batch_window_ms: int = AGGREGATOR_BATCH_MS,
    ) -> None:
        """Initialize ShardAggregator.

        Args:
            event_bus: EventBus instance for pub/sub.
            engagement_id: Engagement ID for aggregated channel.
            shard_count: Number of shards to aggregate.
            batch_window_ms: Batch window in milliseconds.
        """
        self._sharded_bus = ShardedEventBus(event_bus, shard_count)
        self._raw_bus = event_bus
        self._engagement_id = engagement_id
        self._batch_window_ms = batch_window_ms
        self._current_batch = AggregatedBatch()
        self._batch_lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._running = False
        self._log = log.bind(
            component="shard_aggregator",
            engagement_id=engagement_id,
            shards=shard_count,
        )

        # Metrics
        self._shard_counts: dict[int, int] = defaultdict(int)
        self._total_received = 0
        self._total_deduplicated = 0

    async def start(self) -> None:
        """Start aggregator - subscribe to all shards."""
        self._running = True
        await self._sharded_bus.subscribe_findings(
            self._handle_finding,
            finding_type="*",
        )
        self._flush_task = asyncio.create_task(self._flush_loop())
        self._log.info("aggregator_started")

    async def stop(self) -> None:
        """Stop aggregator and flush remaining batch."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        # Final flush
        await self._flush_batch()
        self._log.info(
            "aggregator_stopped",
            total_received=self._total_received,
            total_deduplicated=self._total_deduplicated,
        )

    async def _handle_finding(self, channel: str, message: dict) -> None:
        """Handle finding from any shard."""
        # Extract shard number from channel for metrics
        # Channel format: findings:shard:{N}:{type}
        parts = channel.split(":")
        if len(parts) >= 3 and parts[1] == "shard":
            try:
                shard = int(parts[2])
                self._shard_counts[shard] += 1
            except ValueError:
                pass

        async with self._batch_lock:
            self._total_received += 1
            added = self._current_batch.add(message)
            if not added:
                self._total_deduplicated += 1

    async def _flush_loop(self) -> None:
        """Periodic flush of batched findings."""
        while self._running:
            await asyncio.sleep(self._batch_window_ms / 1000.0)
            await self._flush_batch()

    async def _flush_batch(self) -> None:
        """Flush current batch to aggregated channel."""
        async with self._batch_lock:
            if not self._current_batch.findings:
                return

            batch = self._current_batch
            self._current_batch = AggregatedBatch()

        # Publish aggregated findings
        aggregated_channel = f"findings:aggregated:{self._engagement_id}"
        await self._raw_bus.publish(
            aggregated_channel,
            {
                "findings": batch.findings,
                "count": len(batch.findings),
                "batch_start": batch.start_time.isoformat(),
                "batch_end": datetime.now(UTC).isoformat(),
            },
        )

        self._log.debug(
            "batch_flushed",
            count=len(batch.findings),
            deduplicated=len(batch.seen_ids) - len(batch.findings),
        )

    def get_shard_distribution(self) -> dict[int, int]:
        """Get message count per shard for monitoring."""
        return dict(self._shard_counts)

    def get_metrics(self) -> dict[str, Any]:
        """Get aggregator metrics."""
        return {
            "total_received": self._total_received,
            "total_deduplicated": self._total_deduplicated,
            "dedup_rate": self._total_deduplicated / max(1, self._total_received),
            "shard_distribution": self.get_shard_distribution(),
        }
