"""Stigmergic Intelligence Publication for Swarm-Wide Sharing.

Story 5.10: Intelligence Stigmergic Publication

Implements stigmergic intelligence sharing where agents publish intelligence
results to Redis pub/sub, allowing other agents to skip redundant queries.

Classes:
    StigmergicIntelligencePublisher: Publishes IntelResult to stigmergic layer
    StigmergicIntelligenceSubscriber: Subscribes to stigmergic intelligence updates

Architecture Reference:
    From architecture.md:
    - Stigmergic Publication: findings:{target_hash}:intel_enriched
    - TTL: 5 min for stigmergic (shorter than 1 hour cache)
    - Query order: stigmergic → cache → sources

Channel Pattern:
    findings:{target_hash}:intel_enriched
    where target_hash = SHA256(service:version)[:8]
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Awaitable, Callable, List, Optional

import structlog

from cyberred.intelligence.base import IntelResult

if TYPE_CHECKING:
    from cyberred.core.events import EventBus

log = structlog.get_logger()


class StigmergicIntelligencePublisher:
    """Publishes intelligence results to the stigmergic layer.

    When an agent receives intelligence results, it publishes them to
    `findings:{target_hash}:intel_enriched` so other agents can skip
    redundant queries.

    Attributes:
        TTL_SECONDS: Time-to-live for stigmergic messages (300 = 5 min)

    Example:
        >>> publisher = StigmergicIntelligencePublisher(event_bus)
        >>> await publisher.publish("Apache", "2.4.49", results)
    """

    TTL_SECONDS: int = 300  # 5 minutes (shorter than cache TTL of 1 hour)

    def __init__(self, event_bus: EventBus) -> None:
        """Initialize the stigmergic publisher.

        Args:
            event_bus: EventBus instance for pub/sub messaging.
        """
        self._event_bus = event_bus
        self._log = log.bind(component="stigmergic_publisher")

    def _make_topic(self, service: str, version: str) -> str:
        """Generate stigmergic topic for intelligence results.

        Format: findings:{target_hash}:intel_enriched
        where target_hash = SHA256(service:version)[:8]

        Args:
            service: Service name (e.g., "Apache").
            version: Version string (e.g., "2.4.49").

        Returns:
            Topic string in format findings:{hash}:intel_enriched
        """
        target_key = f"{service}:{version}".lower()
        target_hash = hashlib.sha256(target_key.encode()).hexdigest()[:8]
        return f"findings:{target_hash}:intel_enriched"

    async def publish(
        self,
        service: str,
        version: str,
        results: List[IntelResult],
        agent_id: str = "system",
    ) -> int:
        """Publish intelligence results to stigmergic layer.

        Args:
            service: Service name (e.g., "Apache").
            version: Version string (e.g., "2.4.49").
            results: Intelligence results to share.
            agent_id: ID of agent publishing the results.

        Returns:
            Number of subscribers that received the message.
        """
        topic = self._make_topic(service, version)

        message = {
            "service": service,
            "version": version,
            "results": [
                {
                    "source": r.source,
                    "cve_id": r.cve_id,
                    "severity": r.severity,
                    "exploit_available": r.exploit_available,
                    "exploit_path": r.exploit_path,
                    "confidence": r.confidence,
                    "priority": r.priority,
                    "metadata": r.metadata,
                }
                for r in results
            ],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "ttl_seconds": self.TTL_SECONDS,
            "source_agent_id": agent_id,
        }

        subscriber_count = await self._event_bus.publish(topic, message)

        self._log.info(
            "intelligence_stigmergic_published",
            service=service,
            version=version,
            result_count=len(results),
            subscribers=subscriber_count,
            agent_id=agent_id,
        )

        return subscriber_count


class StigmergicIntelligenceSubscriber:
    """Subscribes to stigmergic intelligence updates.

    Agents subscribe to receive intelligence results published by other
    agents, storing them in a local cache for quick lookup.

    Example:
        >>> subscriber = StigmergicIntelligenceSubscriber(event_bus)
        >>> await subscriber.subscribe()
        >>> results = subscriber.get("Apache", "2.4.49")
    """

    def __init__(self, event_bus: EventBus) -> None:
        """Initialize the stigmergic subscriber.

        Args:
            event_bus: EventBus instance for pub/sub messaging.
        """
        self._event_bus = event_bus
        self._cache: dict = {}
        self._callback: Optional[
            Callable[[str, str, List[IntelResult]], Awaitable[None]]
        ] = None
        self._log = log.bind(component="stigmergic_subscriber")

    async def subscribe(
        self,
        callback: Optional[
            Callable[[str, str, List[IntelResult]], Awaitable[None]]
        ] = None,
    ) -> None:
        """Subscribe to stigmergic intelligence updates.

        Args:
            callback: Optional callback(service, version, results) for custom handling.
        """
        self._callback = callback

        async def handler(channel: str, message: str) -> None:
            data = json.loads(message)
            service = data["service"]
            version = data["version"]
            results = [IntelResult.from_json(r) for r in data["results"]]

            # Store in local cache with TTL
            key = f"{service}:{version}".lower()
            self._cache[key] = {
                "results": results,
                "timestamp": data["timestamp"],
                "expires_at": datetime.utcnow() + timedelta(seconds=data["ttl_seconds"]),
            }

            self._log.debug(
                "intelligence_stigmergic_received",
                service=service,
                version=version,
                result_count=len(results),
                source_agent=data.get("source_agent_id"),
            )

            if self._callback:
                await self._callback(service, version, results)

        await self._event_bus.subscribe("findings:*:intel_enriched", handler)

        self._log.info("intelligence_stigmergic_subscribed")

    def get(self, service: str, version: str) -> Optional[List[IntelResult]]:
        """Get intelligence from stigmergic cache.

        Args:
            service: Service name.
            version: Version string.

        Returns:
            List of IntelResult if found and not expired, None otherwise.
        """
        key = f"{service}:{version}".lower()
        cached = self._cache.get(key)

        if cached is None:
            return None

        if datetime.utcnow() > cached["expires_at"]:
            # Expired, remove from cache
            del self._cache[key]
            self._log.debug(
                "intelligence_stigmergic_expired",
                service=service,
                version=version,
            )
            return None

        self._log.debug(
            "intelligence_stigmergic_hit",
            service=service,
            version=version,
            result_count=len(cached["results"]),
        )
        return cached["results"]
