"""Emergent strategy creation and publication.

Story 7.15: Emergent Attack Strategy Triggering.

This module provides strategy creation from detected patterns and
publication to the stigmergic coordination channel for agent consumption.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable

import structlog

from cyberred.orchestration.emergence.patterns import (
    EmergentPattern,
    EmergentPatternDetector,
    PatternType,
)

if TYPE_CHECKING:
    from cyberred.core.events import EventBus
    from cyberred.core.models import Finding

log = structlog.get_logger().bind(component="emergent_strategy")


# ATT&CK technique mapping for pattern types
PATTERN_TO_TECHNIQUES: dict[PatternType, list[str]] = {
    PatternType.SERVICE_CORRELATION: ["T1046", "T1018"],  # Network Service Discovery
    PatternType.CREDENTIAL_PIVOT: ["T1021", "T1078"],  # Remote Services, Valid Accounts
    PatternType.FAILED_EXPLOIT_ESCALATION: ["T1190"],  # Exploit Public-Facing App
    PatternType.ENUMERATION_COMPLETE: ["T1595", "T1592"],  # Active Scanning
    PatternType.CROSS_AGENT_DISCOVERY: ["T1082", "T1016"],  # System/Network Discovery
}

# Objective templates for pattern types
PATTERN_OBJECTIVES: dict[PatternType, str] = {
    PatternType.SERVICE_CORRELATION: "Exploit correlated service version across {target_count} targets",
    PatternType.CREDENTIAL_PIVOT: "Attempt authentication with discovered credentials on accessible services",
    PatternType.FAILED_EXPLOIT_ESCALATION: "Escalate to RAG for alternative attack techniques after {failure_count} failures",
    PatternType.ENUMERATION_COMPLETE: "Transition to exploitation phase with enumerated targets",
    PatternType.CROSS_AGENT_DISCOVERY: "Correlate cross-agent findings for deeper target analysis",
}


@dataclass
class EmergentStrategy:
    """Strategy synthesized from an emergent pattern.
    
    Published to agents via `strategies:{engagement_id}` channel
    to influence their tool selection and decision making.
    
    Attributes:
        id: Unique identifier for this strategy.
        engagement_id: Associated engagement ID.
        pattern: The EmergentPattern that triggered this strategy.
        objectives: Strategic objectives derived from pattern.
        recommended_techniques: ATT&CK technique IDs to consider.
        avoid_targets: Targets to avoid (e.g., already exploited).
        confidence: Confidence score (inherited from pattern).
        timestamp: When strategy was created (ISO 8601).
    """
    
    id: str
    engagement_id: str
    pattern: EmergentPattern
    objectives: list[str]
    recommended_techniques: list[str]
    avoid_targets: list[str]
    confidence: float
    timestamp: str
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
    
    @property
    def pattern_id(self) -> str:
        """Get the pattern ID for convenience."""
        return self.pattern.id
    
    @property
    def contributing_finding_ids(self) -> list[str]:
        """Get contributing finding IDs for provenance tracking."""
        return self.pattern.contributing_findings
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        data = self._to_dict()
        return json.dumps(data)
    
    def _to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["pattern"]["pattern_type"] = self.pattern.pattern_type.value
        return data
    
    @classmethod
    def from_json(cls, data: str | dict) -> EmergentStrategy:
        """Deserialize from JSON string or dict."""
        if isinstance(data, str):
            data = json.loads(data)
        data = dict(data)  # Make mutable copy
        
        # Reconstruct pattern
        pattern_data = data.pop("pattern")
        pattern = EmergentPattern.from_json(pattern_data)
        
        return cls(pattern=pattern, **data)


class EmergentStrategyPublisher:
    """Publishes emergent strategies to the coordination channel.
    
    Converts detected patterns into strategies and publishes them
    to `strategies:{engagement_id}` for agent consumption.
    
    Attributes:
        _event_bus: EventBus for publication.
        _confidence_threshold: Minimum confidence to publish.
    """
    
    def __init__(
        self,
        event_bus: "EventBus",
        confidence_threshold: float = 0.6,
    ) -> None:
        """Initialize the publisher.
        
        Args:
            event_bus: EventBus instance for pub/sub.
            confidence_threshold: Minimum pattern confidence to publish.
        """
        self._event_bus = event_bus
        self._confidence_threshold = confidence_threshold
        self._log = log
    
    async def publish_strategy(
        self,
        pattern: EmergentPattern,
        engagement_id: str,
    ) -> EmergentStrategy | None:
        """Publish a strategy derived from a detected pattern.
        
        Args:
            pattern: The detected EmergentPattern.
            engagement_id: Target engagement ID.
            
        Returns:
            The published EmergentStrategy, or None if below threshold.
        """
        if pattern.confidence < self._confidence_threshold:
            self._log.debug(
                "pattern_below_threshold",
                pattern_id=pattern.id,
                confidence=pattern.confidence,
                threshold=self._confidence_threshold,
            )
            return None
        
        # Create strategy from pattern
        strategy = self._create_strategy(pattern, engagement_id)
        
        # Publish to strategies channel
        channel = f"strategies:{engagement_id}"
        message = strategy._to_dict()
        
        await self._event_bus.publish(channel, message)
        
        self._log.info(
            "strategy_published",
            strategy_id=strategy.id,
            pattern_type=pattern.pattern_type.value,
            engagement_id=engagement_id,
            confidence=pattern.confidence,
        )
        
        return strategy
    
    def _create_strategy(
        self,
        pattern: EmergentPattern,
        engagement_id: str,
    ) -> EmergentStrategy:
        """Create a strategy from a pattern.
        
        Args:
            pattern: The source EmergentPattern.
            engagement_id: Target engagement ID.
            
        Returns:
            EmergentStrategy instance.
        """
        # Generate objectives from template
        objective_template = PATTERN_OBJECTIVES.get(
            pattern.pattern_type,
            "Execute recommended actions based on emergent pattern",
        )
        
        # Fill in template variables
        objective = objective_template.format(
            target_count=len(pattern.contributing_findings),
            failure_count=len(pattern.contributing_findings),
        )
        
        # Get recommended techniques
        techniques = PATTERN_TO_TECHNIQUES.get(pattern.pattern_type, [])
        
        return EmergentStrategy(
            id=str(uuid.uuid4()),
            engagement_id=engagement_id,
            pattern=pattern,
            objectives=[objective],
            recommended_techniques=techniques,
            avoid_targets=[],
            confidence=pattern.confidence,
            timestamp=datetime.now(UTC).isoformat(),
        )


@dataclass
class _BufferedFinding:
    """Internal representation of a buffered finding with timestamp."""
    data: dict[str, Any]
    received_at: datetime


class EmergentStrategyAggregator:
    """Aggregates findings and triggers pattern detection cycles.
    
    Maintains a sliding window of recent findings and periodically
    runs pattern detection to identify emergent opportunities.
    
    Attributes:
        _event_bus: EventBus for subscription and publication.
        _engagement_id: Target engagement ID.
        _detector: EmergentPatternDetector instance.
        _publisher: EmergentStrategyPublisher instance.
        _window_seconds: Sliding window duration in seconds.
        _detection_cycle_seconds: Time between detection cycles.
    """
    
    def __init__(
        self,
        event_bus: "EventBus",
        engagement_id: str,
        detector: EmergentPatternDetector | None = None,
        publisher: EmergentStrategyPublisher | None = None,
        window_seconds: int = 300,  # 5 minutes
        detection_cycle_seconds: int = 30,
    ) -> None:
        """Initialize the aggregator.
        
        Args:
            event_bus: EventBus for pub/sub.
            engagement_id: Target engagement ID.
            detector: Pattern detector (creates default if None).
            publisher: Strategy publisher (creates default if None).
            window_seconds: Sliding window duration.
            detection_cycle_seconds: Detection cycle interval.
        """
        self._event_bus = event_bus
        self._engagement_id = engagement_id
        self._detector = detector or EmergentPatternDetector()
        self._publisher = publisher or EmergentStrategyPublisher(event_bus)
        self._window_seconds = window_seconds
        self._detection_cycle_seconds = detection_cycle_seconds
        
        self._findings_buffer: deque[_BufferedFinding] = deque()
        self._running = False
        self._detection_task: asyncio.Task | None = None
        self._subscription: Any | None = None
        self._log = log.bind(engagement_id=engagement_id)
    
    async def start(self) -> None:
        """Start the aggregator (subscribe to findings, start detection loop)."""
        if self._running:
            return
        self._running = True

        # Subscribe to all findings channels via Redis pattern subscription.
        self._subscription = await self._event_bus.psubscribe(
            "findings:*",
            lambda channel, data: asyncio.ensure_future(self._on_finding(channel, data)),
        )
        
        # Start background detection loop
        self._detection_task = asyncio.create_task(self._detection_loop())
        
        self._log.info("aggregator_started")
    
    async def stop(self) -> None:
        """Stop the aggregator."""
        self._running = False
        
        if self._subscription is not None:
            try:
                cancel_fn = getattr(self._subscription, "cancel", None)
                unsubscribe_fn = getattr(self._subscription, "unsubscribe", None)
                if callable(cancel_fn):
                    await cancel_fn()
                elif callable(unsubscribe_fn):
                    await unsubscribe_fn()
            except Exception:
                pass
            finally:
                self._subscription = None

        if self._detection_task:
            self._detection_task.cancel()
            try:
                await self._detection_task
            except asyncio.CancelledError:
                pass
        
        self._log.info("aggregator_stopped")
    
    def add_finding(self, finding_data: dict[str, Any]) -> None:
        """Add a finding to the buffer.
        
        Args:
            finding_data: Finding data dictionary.
        """
        self._findings_buffer.append(_BufferedFinding(
            data=finding_data,
            received_at=datetime.now(UTC),
        ))
    
    def get_recent_findings_count(self) -> int:
        """Get count of findings in buffer."""
        return len(self._findings_buffer)
    
    async def _on_finding(self, channel: str, message: dict | str) -> None:
        """Handle incoming finding from EventBus."""
        if ":aggregated:" in channel or ":intel_enriched" in channel:
            return

        if isinstance(message, str):
            try:
                message = json.loads(message)
            except json.JSONDecodeError:
                return

        if not isinstance(message, dict):
            return

        data = dict(message)
        if "data" in data and isinstance(data["data"], dict):
            data = dict(data["data"])
            if "agent_id" not in data and isinstance(message.get("agent_id"), str):
                data["agent_id"] = message["agent_id"]

        data["_source_channel"] = channel
        self.add_finding(data)
    
    def _prune_expired_findings(self) -> None:
        """Remove findings outside the sliding window."""
        cutoff = datetime.now(UTC) - timedelta(seconds=self._window_seconds)
        
        while self._findings_buffer:
            oldest = self._findings_buffer[0]
            if oldest.received_at < cutoff:
                self._findings_buffer.popleft()
            else:
                break
    
    async def _detection_loop(self) -> None:
        """Background loop for periodic pattern detection."""
        while self._running:
            try:
                await asyncio.sleep(self._detection_cycle_seconds)
                await self._run_detection_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.error("detection_cycle_error", error=str(e))
    
    async def _run_detection_cycle(self) -> None:
        """Run a single pattern detection cycle."""
        # Prune expired findings
        self._prune_expired_findings()
        
        if not self._findings_buffer:
            return
        
        # Convert buffered findings to normalized Finding objects
        from cyberred.core.models import Finding
        
        findings: list[Finding] = []
        for buffered in self._findings_buffer:
            finding = self._coerce_finding(buffered.data)
            if finding is None:
                continue
            findings.append(finding)
        
        if not findings:
            return
        
        # Detect patterns
        patterns = self._detector.detect(findings)
        
        # Publish strategies for detected patterns
        for pattern in patterns:
            await self._publisher.publish_strategy(pattern, self._engagement_id)
        
        self._log.debug(
            "detection_cycle_complete",
            findings_count=len(findings),
            patterns_detected=len(patterns),
        )

    def _stable_uuid(self, raw_value: Any, namespace: str) -> str:
        """Return a valid UUID string, synthesizing deterministic UUIDs when needed."""
        text = str(raw_value or "").strip()
        if not text:
            text = f"{namespace}:unknown"
        try:
            return str(uuid.UUID(text))
        except Exception:
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{namespace}:{text}"))

    def _coerce_finding(self, raw_data: dict[str, Any]):
        """Best-effort normalization into core Finding model."""
        from cyberred.core.models import Finding

        data = dict(raw_data)
        target = str(data.get("target") or data.get("domain") or "").strip()
        if not target:
            return None

        finding_type = str(data.get("type") or data.get("finding_type") or "unknown").strip().lower()
        if not finding_type:
            finding_type = "unknown"

        severity = str(data.get("severity") or "info").strip().lower()
        if severity not in {"critical", "high", "medium", "low", "info"}:
            severity = "info"

        timestamp_raw = data.get("timestamp")
        timestamp = datetime.now(UTC).isoformat()
        if isinstance(timestamp_raw, (int, float)):
            try:
                timestamp = datetime.fromtimestamp(float(timestamp_raw), UTC).isoformat()
            except Exception:
                pass
        elif isinstance(timestamp_raw, str) and timestamp_raw.strip():
            try:
                timestamp = datetime.fromisoformat(timestamp_raw).isoformat()
            except Exception:
                timestamp = datetime.now(UTC).isoformat()

        evidence = str(
            data.get("evidence")
            or data.get("output")
            or data.get("description")
            or data.get("username")
            or ""
        )[:1000]

        finding_payload = {
            "id": self._stable_uuid(data.get("id") or data.get("finding_id"), "finding"),
            "type": finding_type,
            "severity": severity,
            "target": target,
            "evidence": evidence,
            "agent_id": self._stable_uuid(data.get("agent_id"), "agent"),
            "timestamp": timestamp,
            "tool": str(data.get("tool") or data.get("tool_name") or "unknown")[:120],
            "topic": str(data.get("topic") or data.get("_source_channel") or "findings:unknown"),
            "signature": str(data.get("signature") or "generated"),
        }

        try:
            return Finding(**finding_payload)
        except (TypeError, ValueError) as e:
            self._log.debug("invalid_finding_data", error=str(e), payload=finding_payload)
            return None
