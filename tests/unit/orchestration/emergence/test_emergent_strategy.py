"""Unit tests for EmergentStrategy, EmergentStrategyPublisher, and EmergentStrategyAggregator.

Story 7.15: Emergent Attack Strategy Triggering.

Tests strategy creation, publication, and aggregation of emergent patterns.
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.orchestration.emergence.patterns import (
    EmergentPattern,
    PatternType,
)
from cyberred.orchestration.emergence.strategy import (
    EmergentStrategy,
    EmergentStrategyPublisher,
    EmergentStrategyAggregator,
)


# --- Fixtures ---

@pytest.fixture
def sample_pattern() -> EmergentPattern:
    """Create a sample EmergentPattern."""
    return EmergentPattern(
        id=str(uuid.uuid4()),
        pattern_type=PatternType.SERVICE_CORRELATION,
        confidence=0.85,
        contributing_findings=["finding-1", "finding-2", "finding-3"],
        recommended_actions=["exploit_ssh_cve_2023_1234"],
        timestamp=datetime.now(UTC).isoformat(),
    )


@pytest.fixture
def low_confidence_pattern() -> EmergentPattern:
    """Create a low confidence pattern (below threshold)."""
    return EmergentPattern(
        id=str(uuid.uuid4()),
        pattern_type=PatternType.ENUMERATION_COMPLETE,
        confidence=0.5,  # Below default 0.6 threshold
        contributing_findings=["finding-1"],
        recommended_actions=["transition_phase"],
        timestamp=datetime.now(UTC).isoformat(),
    )


@pytest.fixture
def mock_event_bus():
    """Create a mock EventBus."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock()
    return bus


@pytest.fixture
def mock_pattern_detector():
    """Create a mock EmergentPatternDetector."""
    detector = MagicMock()
    detector.detect = MagicMock(return_value=[])
    return detector


# --- EmergentStrategy Tests ---

class TestEmergentStrategy:
    """Tests for EmergentStrategy dataclass."""

    def test_emergent_strategy_creation(self, sample_pattern):
        """Test creating a valid EmergentStrategy."""
        strategy = EmergentStrategy(
            id=str(uuid.uuid4()),
            engagement_id="engagement-123",
            pattern=sample_pattern,
            objectives=["Exploit SSH vulnerability across correlated targets"],
            recommended_techniques=["T1021.004"],  # SSH exploitation
            avoid_targets=[],
            confidence=sample_pattern.confidence,
            timestamp=datetime.now(UTC).isoformat(),
        )
        
        assert strategy.engagement_id == "engagement-123"
        assert strategy.pattern == sample_pattern
        assert len(strategy.objectives) == 1
        assert "T1021.004" in strategy.recommended_techniques

    def test_emergent_strategy_confidence_validation(self, sample_pattern):
        """Test confidence must be between 0.0 and 1.0."""
        with pytest.raises(ValueError, match="confidence"):
            EmergentStrategy(
                id=str(uuid.uuid4()),
                engagement_id="engagement-123",
                pattern=sample_pattern,
                objectives=[],
                recommended_techniques=[],
                avoid_targets=[],
                confidence=1.5,  # Invalid
                timestamp=datetime.now(UTC).isoformat(),
            )

    def test_emergent_strategy_to_json(self, sample_pattern):
        """Test JSON serialization."""
        strategy = EmergentStrategy(
            id="strategy-123",
            engagement_id="engagement-456",
            pattern=sample_pattern,
            objectives=["Exploit targets"],
            recommended_techniques=["T1021"],
            avoid_targets=["192.168.1.200"],
            confidence=0.85,
            timestamp="2026-01-27T12:00:00+00:00",
        )
        
        json_str = strategy.to_json()
        data = json.loads(json_str)
        
        assert data["id"] == "strategy-123"
        assert data["engagement_id"] == "engagement-456"
        assert data["objectives"] == ["Exploit targets"]
        assert data["avoid_targets"] == ["192.168.1.200"]
        assert "pattern" in data

    def test_emergent_strategy_from_json(self, sample_pattern):
        """Test JSON deserialization."""
        pattern_dict = {
            "id": sample_pattern.id,
            "pattern_type": sample_pattern.pattern_type.value,
            "confidence": sample_pattern.confidence,
            "contributing_findings": sample_pattern.contributing_findings,
            "recommended_actions": sample_pattern.recommended_actions,
            "timestamp": sample_pattern.timestamp,
        }
        
        data = {
            "id": "strategy-789",
            "engagement_id": "engagement-abc",
            "pattern": pattern_dict,
            "objectives": ["Test objective"],
            "recommended_techniques": ["T1059"],
            "avoid_targets": [],
            "confidence": 0.9,
            "timestamp": "2026-01-27T12:00:00+00:00",
        }
        
        strategy = EmergentStrategy.from_json(json.dumps(data))
        
        assert strategy.id == "strategy-789"
        assert strategy.engagement_id == "engagement-abc"
        assert strategy.pattern.pattern_type == PatternType.SERVICE_CORRELATION

    def test_emergent_strategy_from_json_dict(self, sample_pattern):
        """Test deserialization from dict."""
        pattern_dict = {
            "id": sample_pattern.id,
            "pattern_type": sample_pattern.pattern_type.value,
            "confidence": sample_pattern.confidence,
            "contributing_findings": sample_pattern.contributing_findings,
            "recommended_actions": sample_pattern.recommended_actions,
            "timestamp": sample_pattern.timestamp,
        }
        
        data = {
            "id": "strategy-xyz",
            "engagement_id": "engagement-def",
            "pattern": pattern_dict,
            "objectives": [],
            "recommended_techniques": [],
            "avoid_targets": [],
            "confidence": 0.7,
            "timestamp": "2026-01-27T12:00:00+00:00",
        }
        
        strategy = EmergentStrategy.from_json(data)
        assert strategy.id == "strategy-xyz"

    def test_emergent_strategy_pattern_id_accessor(self, sample_pattern):
        """Test pattern_id property for convenience access."""
        strategy = EmergentStrategy(
            id=str(uuid.uuid4()),
            engagement_id="engagement-123",
            pattern=sample_pattern,
            objectives=[],
            recommended_techniques=[],
            avoid_targets=[],
            confidence=0.8,
            timestamp=datetime.now(UTC).isoformat(),
        )
        
        assert strategy.pattern_id == sample_pattern.id

    def test_emergent_strategy_contributing_findings_accessor(self, sample_pattern):
        """Test contributing_finding_ids property."""
        strategy = EmergentStrategy(
            id=str(uuid.uuid4()),
            engagement_id="engagement-123",
            pattern=sample_pattern,
            objectives=[],
            recommended_techniques=[],
            avoid_targets=[],
            confidence=0.8,
            timestamp=datetime.now(UTC).isoformat(),
        )
        
        assert strategy.contributing_finding_ids == sample_pattern.contributing_findings


# --- EmergentStrategyPublisher Tests ---

class TestEmergentStrategyPublisher:
    """Tests for EmergentStrategyPublisher."""

    def test_publisher_creation(self, mock_event_bus):
        """Test publisher can be instantiated."""
        publisher = EmergentStrategyPublisher(event_bus=mock_event_bus)
        assert publisher is not None
        assert publisher._event_bus == mock_event_bus

    def test_publisher_creation_with_threshold(self, mock_event_bus):
        """Test publisher with custom confidence threshold."""
        publisher = EmergentStrategyPublisher(
            event_bus=mock_event_bus,
            confidence_threshold=0.8,
        )
        assert publisher._confidence_threshold == 0.8

    @pytest.mark.asyncio
    async def test_publish_strategy_from_pattern(self, mock_event_bus, sample_pattern):
        """Test publishing a strategy from a detected pattern."""
        publisher = EmergentStrategyPublisher(event_bus=mock_event_bus)
        
        strategy = await publisher.publish_strategy(
            pattern=sample_pattern,
            engagement_id="engagement-123",
        )
        
        assert strategy is not None
        assert strategy.engagement_id == "engagement-123"
        assert strategy.pattern == sample_pattern
        mock_event_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_strategy_channel(self, mock_event_bus, sample_pattern):
        """Test strategy is published to correct channel."""
        publisher = EmergentStrategyPublisher(event_bus=mock_event_bus)
        
        await publisher.publish_strategy(
            pattern=sample_pattern,
            engagement_id="engagement-456",
        )
        
        call_args = mock_event_bus.publish.call_args
        channel = call_args[0][0]
        assert channel == "strategies:engagement-456"

    @pytest.mark.asyncio
    async def test_publish_strategy_message_format(self, mock_event_bus, sample_pattern):
        """Test published message contains required fields."""
        publisher = EmergentStrategyPublisher(event_bus=mock_event_bus)
        
        await publisher.publish_strategy(
            pattern=sample_pattern,
            engagement_id="engagement-789",
        )
        
        call_args = mock_event_bus.publish.call_args
        message = call_args[0][1]
        
        assert "id" in message
        assert "engagement_id" in message
        assert "pattern" in message
        assert "objectives" in message
        assert "recommended_techniques" in message
        assert "confidence" in message

    @pytest.mark.asyncio
    async def test_publish_strategy_below_threshold_skipped(self, mock_event_bus, low_confidence_pattern):
        """Test patterns below confidence threshold are not published."""
        publisher = EmergentStrategyPublisher(
            event_bus=mock_event_bus,
            confidence_threshold=0.6,
        )
        
        result = await publisher.publish_strategy(
            pattern=low_confidence_pattern,
            engagement_id="engagement-123",
        )
        
        assert result is None
        mock_event_bus.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_strategy_generates_objectives(self, mock_event_bus, sample_pattern):
        """Test publisher generates appropriate objectives from pattern."""
        publisher = EmergentStrategyPublisher(event_bus=mock_event_bus)
        
        strategy = await publisher.publish_strategy(
            pattern=sample_pattern,
            engagement_id="engagement-123",
        )
        
        assert len(strategy.objectives) > 0

    @pytest.mark.asyncio
    async def test_publish_strategy_maps_techniques(self, mock_event_bus):
        """Test publisher maps pattern actions to ATT&CK techniques."""
        pattern = EmergentPattern(
            id=str(uuid.uuid4()),
            pattern_type=PatternType.CREDENTIAL_PIVOT,
            confidence=0.85,
            contributing_findings=["cred-1", "smb-1"],
            recommended_actions=["authenticate_smb", "lateral_movement"],
            timestamp=datetime.now(UTC).isoformat(),
        )
        
        publisher = EmergentStrategyPublisher(event_bus=mock_event_bus)
        strategy = await publisher.publish_strategy(
            pattern=pattern,
            engagement_id="engagement-123",
        )
        
        # Should include lateral movement technique
        assert len(strategy.recommended_techniques) > 0

    @pytest.mark.asyncio
    async def test_publish_multiple_strategies(self, mock_event_bus, sample_pattern):
        """Test publishing multiple strategies."""
        publisher = EmergentStrategyPublisher(event_bus=mock_event_bus)
        
        pattern2 = EmergentPattern(
            id=str(uuid.uuid4()),
            pattern_type=PatternType.CREDENTIAL_PIVOT,
            confidence=0.9,
            contributing_findings=["f1"],
            recommended_actions=["pivot"],
            timestamp=datetime.now(UTC).isoformat(),
        )
        
        s1 = await publisher.publish_strategy(sample_pattern, "eng-1")
        s2 = await publisher.publish_strategy(pattern2, "eng-1")
        
        assert s1.id != s2.id
        assert mock_event_bus.publish.call_count == 2


# --- EmergentStrategyAggregator Tests ---

class TestEmergentStrategyAggregator:
    """Tests for EmergentStrategyAggregator."""

    def test_aggregator_creation(self, mock_event_bus, mock_pattern_detector):
        """Test aggregator can be instantiated."""
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="engagement-123",
            detector=mock_pattern_detector,
        )
        assert aggregator is not None

    def test_aggregator_with_custom_window(self, mock_event_bus, mock_pattern_detector):
        """Test aggregator with custom sliding window."""
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="engagement-123",
            detector=mock_pattern_detector,
            window_seconds=600,  # 10 minutes
        )
        assert aggregator._window_seconds == 600

    def test_aggregator_with_custom_cycle(self, mock_event_bus, mock_pattern_detector):
        """Test aggregator with custom detection cycle."""
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="engagement-123",
            detector=mock_pattern_detector,
            detection_cycle_seconds=60,
        )
        assert aggregator._detection_cycle_seconds == 60

    @pytest.mark.asyncio
    async def test_aggregator_start_subscribes_to_findings(self, mock_event_bus, mock_pattern_detector):
        """Test aggregator subscribes to findings channel on start."""
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="engagement-123",
            detector=mock_pattern_detector,
        )
        
        await aggregator.start()
        
        # Should subscribe to findings:* channel
        mock_event_bus.subscribe.assert_called()
        
        await aggregator.stop()

    @pytest.mark.asyncio
    async def test_aggregator_stop_cancels_tasks(self, mock_event_bus, mock_pattern_detector):
        """Test aggregator cancels background tasks on stop."""
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="engagement-123",
            detector=mock_pattern_detector,
        )
        
        await aggregator.start()
        await aggregator.stop()
        
        assert aggregator._running is False

    @pytest.mark.asyncio
    async def test_aggregator_add_finding(self, mock_event_bus, mock_pattern_detector):
        """Test adding a finding to the aggregator."""
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="engagement-123",
            detector=mock_pattern_detector,
        )
        
        finding_data = {
            "id": str(uuid.uuid4()),
            "type": "service",
            "severity": "medium",
            "target": "192.168.1.100",
            "evidence": "SSH 8.2",
            "agent_id": str(uuid.uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "tool": "nmap",
            "topic": "findings:abc:service",
            "signature": "sig",
        }
        
        aggregator.add_finding(finding_data)
        
        assert len(aggregator._findings_buffer) == 1

    @pytest.mark.asyncio
    async def test_aggregator_sliding_window_expires_old_findings(self, mock_event_bus, mock_pattern_detector):
        """Test old findings are removed from sliding window."""
        import time
        
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="engagement-123",
            detector=mock_pattern_detector,
            window_seconds=1,  # 1 second window for testing
        )
        
        old_finding = {
            "id": str(uuid.uuid4()),
            "type": "service",
            "severity": "medium",
            "target": "192.168.1.100",
            "evidence": "SSH 8.2",
            "agent_id": str(uuid.uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "tool": "nmap",
            "topic": "findings:abc:service",
            "signature": "sig",
        }
        
        aggregator.add_finding(old_finding)
        # Wait for the window to expire
        time.sleep(1.1)
        aggregator._prune_expired_findings()
        
        assert len(aggregator._findings_buffer) == 0

    @pytest.mark.asyncio
    async def test_aggregator_detection_cycle_calls_detector(self, mock_event_bus, mock_pattern_detector, sample_pattern):
        """Test detection cycle invokes pattern detector."""
        mock_pattern_detector.detect.return_value = [sample_pattern]
        
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="engagement-123",
            detector=mock_pattern_detector,
        )
        
        finding_data = {
            "id": str(uuid.uuid4()),
            "type": "service",
            "severity": "medium",
            "target": "192.168.1.100",
            "evidence": "SSH 8.2",
            "agent_id": str(uuid.uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "tool": "nmap",
            "topic": "findings:abc:service",
            "signature": "sig",
        }
        aggregator.add_finding(finding_data)
        
        await aggregator._run_detection_cycle()
        
        mock_pattern_detector.detect.assert_called_once()

    @pytest.mark.asyncio
    async def test_aggregator_publishes_detected_patterns(self, mock_event_bus, mock_pattern_detector, sample_pattern):
        """Test aggregator publishes strategies for detected patterns."""
        mock_pattern_detector.detect.return_value = [sample_pattern]
        
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="engagement-123",
            detector=mock_pattern_detector,
        )
        
        finding_data = {
            "id": str(uuid.uuid4()),
            "type": "service",
            "severity": "medium",
            "target": "192.168.1.100",
            "evidence": "SSH 8.2",
            "agent_id": str(uuid.uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "tool": "nmap",
            "topic": "findings:abc:service",
            "signature": "sig",
        }
        aggregator.add_finding(finding_data)
        
        await aggregator._run_detection_cycle()
        
        # Should publish to strategies channel
        mock_event_bus.publish.assert_called()

    def test_aggregator_get_recent_findings_count(self, mock_event_bus, mock_pattern_detector):
        """Test getting count of recent findings."""
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="engagement-123",
            detector=mock_pattern_detector,
        )
        
        for i in range(5):
            finding_data = {
                "id": str(uuid.uuid4()),
                "type": "service",
                "severity": "medium",
                "target": f"192.168.1.{100+i}",
                "evidence": "SSH 8.2",
                "agent_id": str(uuid.uuid4()),
                "timestamp": datetime.now(UTC).isoformat(),
                "tool": "nmap",
                "topic": "findings:abc:service",
                "signature": f"sig-{i}",
            }
            aggregator.add_finding(finding_data)
        
        assert aggregator.get_recent_findings_count() == 5


# --- Integration-style Unit Tests ---

class TestEmergentStrategyAggregatorEdgeCases:
    """Edge case tests for EmergentStrategyAggregator."""

    @pytest.mark.asyncio
    async def test_aggregator_on_finding_string_message(self, mock_event_bus, mock_pattern_detector):
        """Test handling string message in _on_finding."""
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="engagement-123",
            detector=mock_pattern_detector,
        )
        
        finding_dict = {
            "id": str(uuid.uuid4()),
            "type": "service",
            "severity": "medium",
            "target": "192.168.1.100",
            "evidence": "SSH 8.2",
            "agent_id": str(uuid.uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "tool": "nmap",
            "topic": "findings:abc:service",
            "signature": "sig",
        }
        
        # Pass as JSON string
        await aggregator._on_finding(json.dumps(finding_dict))
        
        assert len(aggregator._findings_buffer) == 1

    @pytest.mark.asyncio
    async def test_aggregator_on_finding_invalid_json(self, mock_event_bus, mock_pattern_detector):
        """Test handling invalid JSON in _on_finding."""
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="engagement-123",
            detector=mock_pattern_detector,
        )
        
        # Pass invalid JSON
        await aggregator._on_finding("not valid json {{{")
        
        # Should not add anything
        assert len(aggregator._findings_buffer) == 0

    @pytest.mark.asyncio
    async def test_aggregator_run_detection_with_invalid_finding_data(self, mock_event_bus, mock_pattern_detector):
        """Test detection cycle handles invalid finding data gracefully."""
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="engagement-123",
            detector=mock_pattern_detector,
        )
        
        # Add invalid finding data (missing required fields)
        aggregator.add_finding({"invalid": "data"})
        
        # Should not raise, just skip invalid
        await aggregator._run_detection_cycle()
        
        # Detector should not be called with empty findings list
        # (after invalid ones are filtered)

    @pytest.mark.asyncio
    async def test_aggregator_run_detection_all_invalid_findings(self, mock_event_bus, mock_pattern_detector):
        """Test detection cycle with all invalid findings returns early."""
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="engagement-123",
            detector=mock_pattern_detector,
        )
        
        # Add only invalid findings
        aggregator.add_finding({"bad": "data1"})
        aggregator.add_finding({"bad": "data2"})
        
        await aggregator._run_detection_cycle()
        
        # Detector should not be called since no valid findings
        mock_pattern_detector.detect.assert_not_called()


class TestEmergentStrategyIntegration:
    """Integration-style unit tests for emergent strategy components."""

    @pytest.mark.asyncio
    async def test_pattern_to_strategy_pipeline(self, mock_event_bus):
        """Test full pipeline from pattern detection to strategy publication."""
        pattern = EmergentPattern(
            id=str(uuid.uuid4()),
            pattern_type=PatternType.CREDENTIAL_PIVOT,
            confidence=0.85,
            contributing_findings=["cred-finding", "smb-finding"],
            recommended_actions=["authenticate_smb"],
            timestamp=datetime.now(UTC).isoformat(),
        )
        
        publisher = EmergentStrategyPublisher(event_bus=mock_event_bus)
        strategy = await publisher.publish_strategy(pattern, "engagement-test")
        
        assert strategy is not None
        assert strategy.pattern.pattern_type == PatternType.CREDENTIAL_PIVOT
        assert mock_event_bus.publish.called

    @pytest.mark.asyncio
    async def test_aggregator_end_to_end(self, mock_event_bus, sample_pattern):
        """Test aggregator end-to-end flow."""
        detector = MagicMock()
        detector.detect.return_value = [sample_pattern]
        
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="engagement-e2e",
            detector=detector,
        )
        
        # Add multiple findings
        for i in range(3):
            aggregator.add_finding({
                "id": str(uuid.uuid4()),
                "type": "service",
                "severity": "medium",
                "target": f"192.168.1.{100+i}",
                "evidence": "SSH 8.2p1",
                "agent_id": str(uuid.uuid4()),
                "timestamp": datetime.now(UTC).isoformat(),
                "tool": "nmap",
                "topic": f"findings:hash{i}:service",
                "signature": f"sig-{i}",
            })
        
        # Run detection
        await aggregator._run_detection_cycle()
        
        # Verify detector was called with findings
        assert detector.detect.called
        # Verify strategy was published
        assert mock_event_bus.publish.called
