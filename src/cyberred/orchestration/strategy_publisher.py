"""Strategy Publisher for Director Ensemble to Agent communication.

Story 8.10: Strategy Publication to Agents.

This module provides the StrategyPublisher class that publishes synthesized
strategies from the DirectorEnsemble to agents via Redis pub/sub.

Per architecture:
- Strategy channel: `strategies:{engagement_id}`
- JSON message format with structured fields
- Agents subscribe via pattern subscription
- Fire-and-forget publication (non-blocking)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import structlog

if TYPE_CHECKING:
    from cyberred.core.events import EventBus
    from cyberred.llm.ensemble import SynthesizedStrategy

log = structlog.get_logger().bind(component="strategy_publisher")

__all__ = [
    "PublishedStrategy",
    "StrategyPublisher",
]


@dataclass
class PublishedStrategy:
    """Strategy message published to agents.

    This dataclass represents the message format for strategies published
    to the `strategies:{engagement_id}` channel for agent consumption.

    Attributes:
        engagement_id: The engagement this strategy applies to.
        objectives: Strategic objectives to pursue.
        priorities: Ordered target/action priorities.
        recommended_techniques: ATT&CK techniques to apply.
        avoid_list: Targets/approaches to skip.
        confidence: Strategy confidence score (0.0-1.0).
        timestamp: When strategy was synthesized (epoch time).
        contributing_roles: Director roles that contributed.
        rationale: Explanation of strategy reasoning.
    """

    engagement_id: str
    objectives: List[str]
    priorities: List[str]
    recommended_techniques: List[Dict[str, str]]  # technique_id, name, rationale
    avoid_list: List[str]
    confidence: float
    timestamp: float
    contributing_roles: List[str]
    rationale: str

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        # Validate engagement_id is non-empty string
        if not self.engagement_id or not isinstance(self.engagement_id, str):
            raise ValueError("engagement_id must be a non-empty string")
        
        # Validate confidence bounds
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        
        # Validate timestamp is non-negative
        if self.timestamp < 0:
            raise ValueError(
                f"timestamp must be non-negative, got {self.timestamp}"
            )
        
        # Validate list fields are not None
        if self.objectives is None:
            raise ValueError("objectives cannot be None")
        if self.priorities is None:
            raise ValueError("priorities cannot be None")
        if self.recommended_techniques is None:
            raise ValueError("recommended_techniques cannot be None")
        if self.avoid_list is None:
            raise ValueError("avoid_list cannot be None")
        if self.contributing_roles is None:
            raise ValueError("contributing_roles cannot be None")

    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary.

        Returns:
            Dictionary suitable for JSON serialization and Redis publication.
        """
        return {
            "engagement_id": self.engagement_id,
            "objectives": self.objectives,
            "priorities": self.priorities,
            "recommended_techniques": self.recommended_techniques,
            "avoid_list": self.avoid_list,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "contributing_roles": self.contributing_roles,
            "rationale": self.rationale,
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "PublishedStrategy":
        """Create PublishedStrategy from JSON dictionary.

        Args:
            data: Dictionary with strategy fields.

        Returns:
            PublishedStrategy instance.

        Raises:
            KeyError: If required fields are missing.
            ValueError: If field values are invalid.
        """
        return cls(
            engagement_id=data["engagement_id"],
            objectives=data["objectives"],
            priorities=data["priorities"],
            recommended_techniques=data["recommended_techniques"],
            avoid_list=data["avoid_list"],
            confidence=data["confidence"],
            timestamp=data["timestamp"],
            contributing_roles=data["contributing_roles"],
            rationale=data["rationale"],
        )

    @classmethod
    def from_synthesized(
        cls,
        synthesized: "SynthesizedStrategy",
        engagement_id: str,
    ) -> "PublishedStrategy":
        """Create PublishedStrategy from SynthesizedStrategy.

        Converts a SynthesizedStrategy from DirectorEnsemble into the
        PublishedStrategy format for agent consumption.

        Args:
            synthesized: The SynthesizedStrategy from DirectorEnsemble.
            engagement_id: The engagement ID for this strategy.

        Returns:
            PublishedStrategy instance ready for publication.
        """
        # Convert ATTCKRecommendation objects to dicts
        techniques = [
            {
                "technique_id": t.technique_id,
                "name": t.technique_name,
                "rationale": t.rationale,
            }
            for t in synthesized.attck_techniques
        ]

        # Convert DirectorRole enums to strings
        roles = [r.value for r in synthesized.contributing_roles]

        # Use actions as priorities (ordered actions are priorities)
        priorities = synthesized.actions

        return cls(
            engagement_id=engagement_id,
            objectives=synthesized.objectives,
            priorities=priorities,
            recommended_techniques=techniques,
            avoid_list=synthesized.avoid_list,
            confidence=synthesized.confidence,
            timestamp=time.time(),
            contributing_roles=roles,
            rationale=synthesized.rationale,
        )


class StrategyPublisher:
    """Publishes synthesized strategies to the coordination channel.

    Converts SynthesizedStrategy from DirectorEnsemble into PublishedStrategy
    and publishes to `strategies:{engagement_id}` for agent consumption.

    Per Story 8.10:
    - Publishes to `strategies:{engagement_id}` channel
    - Uses EventBus.publish() for publication
    - Fire-and-forget publication (non-blocking)
    - Handles publication failures gracefully (log, don't block)

    Attributes:
        _event_bus: EventBus for publication.
        _confidence_threshold: Minimum confidence to publish.
    """

    def __init__(
        self,
        event_bus: "EventBus",
        confidence_threshold: float = 0.5,
    ) -> None:
        """Initialize the publisher.

        Args:
            event_bus: EventBus instance for pub/sub.
            confidence_threshold: Minimum strategy confidence to publish.
                Strategies below this threshold are not published.
        """
        self._event_bus = event_bus
        self._confidence_threshold = confidence_threshold
        self._log = log

    async def publish_strategy(
        self,
        synthesized: "SynthesizedStrategy",
        engagement_id: str,
    ) -> Optional[PublishedStrategy]:
        """Publish a strategy derived from DirectorEnsemble synthesis.

        Args:
            synthesized: The SynthesizedStrategy from DirectorEnsemble.
            engagement_id: Target engagement ID.

        Returns:
            The published PublishedStrategy, or None if below threshold
            or publication failed.
        """
        # Check confidence threshold
        if synthesized.confidence < self._confidence_threshold:
            self._log.debug(
                "strategy_below_threshold",
                confidence=synthesized.confidence,
                threshold=self._confidence_threshold,
            )
            return None

        try:
            # Convert to published format
            published = PublishedStrategy.from_synthesized(
                synthesized=synthesized,
                engagement_id=engagement_id,
            )

            # Publish to strategies channel
            channel = f"strategies:{engagement_id}"
            message = published.to_json()

            await self._event_bus.publish(channel, message)

            self._log.info(
                "strategy_published",
                engagement_id=engagement_id,
                confidence=published.confidence,
                objectives_count=len(published.objectives),
                techniques_count=len(published.recommended_techniques),
            )

            return published

        except Exception as e:
            # Handle publication failures gracefully (log, don't block)
            self._log.error(
                "strategy_publication_failed",
                engagement_id=engagement_id,
                error=str(e),
            )
            return None
