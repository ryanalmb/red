"""Integration tests for Emergent Strategy Triggering.

Story 7.15: Emergent Attack Strategy Triggering.

Tests the full pipeline from findings to pattern detection to strategy publication.
Uses real EventBus with mocked Redis for isolation.
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.core.models import Finding
from cyberred.orchestration.emergence.patterns import (
    EmergentPattern,
    EmergentPatternDetector,
    PatternType,
)
from cyberred.orchestration.emergence.strategy import (
    EmergentStrategy,
    EmergentStrategyAggregator,
    EmergentStrategyPublisher,
)


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = MagicMock()
    redis.publish = AsyncMock()
    redis.subscribe = AsyncMock()
    return redis


@pytest.fixture
def mock_event_bus(mock_redis):
    """Create mock EventBus with Redis."""
    bus = MagicMock()
    bus.redis = mock_redis
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock()
    return bus


class TestEmergentStrategyPipeline:
    """Integration tests for the full emergent strategy pipeline."""

    @pytest.mark.asyncio
    async def test_findings_to_pattern_to_strategy_pipeline(self, mock_event_bus):
        """Test complete pipeline: findings → pattern → strategy."""
        # Create findings that should trigger SERVICE_CORRELATION
        findings = []
        for i, target in enumerate(["192.168.1.100", "192.168.1.101", "192.168.1.102"]):
            findings.append(Finding(
                id=str(uuid.uuid4()),
                type="service",
                severity="info",
                target=target,
                evidence="SSH OpenSSH 8.2p1 Ubuntu-4ubuntu0.1",
                agent_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC).isoformat(),
                tool="nmap",
                topic=f"findings:hash{i}:service",
                signature=f"sig-{i}",
            ))

        # Detect patterns
        detector = EmergentPatternDetector(service_correlation_threshold=2)
        patterns = detector.detect(findings)

        assert len(patterns) >= 1
        pattern = patterns[0]
        assert pattern.pattern_type == PatternType.SERVICE_CORRELATION

        # Publish strategy
        publisher = EmergentStrategyPublisher(event_bus=mock_event_bus)
        strategy = await publisher.publish_strategy(pattern, "test-engagement")

        assert strategy is not None
        assert strategy.engagement_id == "test-engagement"
        assert strategy.pattern.pattern_type == PatternType.SERVICE_CORRELATION
        assert len(strategy.recommended_techniques) > 0

        # Verify EventBus was called
        mock_event_bus.publish.assert_called_once()
        call_args = mock_event_bus.publish.call_args
        assert call_args[0][0] == "strategies:test-engagement"

    @pytest.mark.asyncio
    async def test_credential_pivot_detection_and_publication(self, mock_event_bus):
        """Test CREDENTIAL_PIVOT pattern detection and strategy publication."""
        findings = [
            Finding(
                id=str(uuid.uuid4()),
                type="credential",
                severity="high",
                target="192.168.1.100",
                evidence="admin:P@ssw0rd123",
                agent_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC).isoformat(),
                tool="mimikatz",
                topic="findings:abc:credential",
                signature="cred-sig",
            ),
            Finding(
                id=str(uuid.uuid4()),
                type="service",
                severity="medium",
                target="192.168.1.101",
                evidence="SMB 445/tcp open microsoft-ds",
                agent_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC).isoformat(),
                tool="nmap",
                topic="findings:def:service",
                signature="smb-sig",
            ),
        ]

        detector = EmergentPatternDetector()
        patterns = detector.detect(findings)

        pivot_patterns = [p for p in patterns if p.pattern_type == PatternType.CREDENTIAL_PIVOT]
        assert len(pivot_patterns) >= 1

        publisher = EmergentStrategyPublisher(event_bus=mock_event_bus)
        strategy = await publisher.publish_strategy(pivot_patterns[0], "pivot-engagement")

        assert strategy is not None
        assert "lateral" in str(strategy.pattern.recommended_actions).lower() or \
               "authenticate" in str(strategy.pattern.recommended_actions).lower()

    @pytest.mark.asyncio
    async def test_aggregator_full_cycle(self, mock_event_bus):
        """Test aggregator subscribes, collects findings, and publishes strategies."""
        detector = EmergentPatternDetector(service_correlation_threshold=2)
        
        aggregator = EmergentStrategyAggregator(
            event_bus=mock_event_bus,
            engagement_id="aggregator-test",
            detector=detector,
            window_seconds=300,
            detection_cycle_seconds=1,
        )

        # Add findings directly (simulating EventBus callback)
        for i, target in enumerate(["10.0.0.1", "10.0.0.2", "10.0.0.3"]):
            aggregator.add_finding({
                "id": str(uuid.uuid4()),
                "type": "service",
                "severity": "info",
                "target": target,
                "evidence": "Apache 2.4.49 (Ubuntu)",
                "agent_id": str(uuid.uuid4()),
                "timestamp": datetime.now(UTC).isoformat(),
                "tool": "whatweb",
                "topic": f"findings:hash{i}:service",
                "signature": f"apache-sig-{i}",
            })

        assert aggregator.get_recent_findings_count() == 3

        # Run detection cycle manually
        await aggregator._run_detection_cycle()

        # Should have published a strategy
        assert mock_event_bus.publish.called

    @pytest.mark.asyncio
    async def test_failed_exploit_escalation_triggers_rag(self, mock_event_bus):
        """Test FAILED_EXPLOIT_ESCALATION triggers RAG escalation recommendation."""
        findings = []
        for i in range(4):
            findings.append(Finding(
                id=str(uuid.uuid4()),
                type="exploit_failed",
                severity="info",
                target="192.168.1.100",
                evidence=f"SQLi attempt {i+1} failed: WAF blocked",
                agent_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC).isoformat(),
                tool="sqlmap",
                topic="findings:target:exploit_failed",
                signature=f"fail-{i}",
            ))

        detector = EmergentPatternDetector(failed_exploit_threshold=3)
        patterns = detector.detect(findings)

        escalation_patterns = [p for p in patterns if p.pattern_type == PatternType.FAILED_EXPLOIT_ESCALATION]
        assert len(escalation_patterns) >= 1

        pattern = escalation_patterns[0]
        assert pattern.confidence >= 0.8
        assert "rag" in str(pattern.recommended_actions).lower() or \
               "escalat" in str(pattern.recommended_actions).lower()

    @pytest.mark.asyncio
    async def test_strategy_contains_provenance(self, mock_event_bus):
        """Test strategy maintains provenance chain for NFR37."""
        finding_ids = [str(uuid.uuid4()) for _ in range(3)]
        
        findings = [
            Finding(
                id=finding_ids[i],
                type="service",
                severity="info",
                target=f"192.168.1.{100+i}",
                evidence="nginx 1.18",
                agent_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC).isoformat(),
                tool="whatweb",
                topic=f"findings:h{i}:service",
                signature=f"sig{i}",
            )
            for i in range(3)
        ]

        detector = EmergentPatternDetector(service_correlation_threshold=2)
        patterns = detector.detect(findings)

        assert len(patterns) >= 1
        pattern = patterns[0]

        # Verify pattern contains contributing finding IDs
        for fid in pattern.contributing_findings:
            assert fid in finding_ids

        publisher = EmergentStrategyPublisher(event_bus=mock_event_bus)
        strategy = await publisher.publish_strategy(pattern, "provenance-test")

        # Verify strategy maintains provenance
        assert strategy.pattern_id == pattern.id
        assert set(strategy.contributing_finding_ids) == set(pattern.contributing_findings)


class TestEmergentPatternDetectorIntegration:
    """Integration tests for EmergentPatternDetector with realistic findings."""

    def test_mixed_findings_multiple_patterns(self):
        """Test detection with mixed findings producing multiple patterns."""
        findings = [
            # Service correlation group 1 (SSH)
            Finding(
                id=str(uuid.uuid4()), type="service", severity="info",
                target="10.0.0.1", evidence="SSH OpenSSH 8.2",
                agent_id=str(uuid.uuid4()), timestamp=datetime.now(UTC).isoformat(),
                tool="nmap", topic="f:a:s", signature="s1",
            ),
            Finding(
                id=str(uuid.uuid4()), type="service", severity="info",
                target="10.0.0.2", evidence="SSH OpenSSH 8.2",
                agent_id=str(uuid.uuid4()), timestamp=datetime.now(UTC).isoformat(),
                tool="nmap", topic="f:b:s", signature="s2",
            ),
            # Credential for pivot
            Finding(
                id=str(uuid.uuid4()), type="credential", severity="high",
                target="10.0.0.3", evidence="root:toor",
                agent_id=str(uuid.uuid4()), timestamp=datetime.now(UTC).isoformat(),
                tool="hydra", topic="f:c:cred", signature="c1",
            ),
            # SMB service for pivot
            Finding(
                id=str(uuid.uuid4()), type="service", severity="medium",
                target="10.0.0.4", evidence="SMB 445 open",
                agent_id=str(uuid.uuid4()), timestamp=datetime.now(UTC).isoformat(),
                tool="nmap", topic="f:d:s", signature="s3",
            ),
        ]

        detector = EmergentPatternDetector(service_correlation_threshold=2)
        patterns = detector.detect(findings)

        pattern_types = {p.pattern_type for p in patterns}
        
        # Should detect both SERVICE_CORRELATION and CREDENTIAL_PIVOT
        assert PatternType.SERVICE_CORRELATION in pattern_types
        assert PatternType.CREDENTIAL_PIVOT in pattern_types

    def test_no_false_positives_with_unrelated_findings(self):
        """Test detector doesn't produce false positives from unrelated findings."""
        findings = [
            Finding(
                id=str(uuid.uuid4()), type="open_port", severity="info",
                target="10.0.0.1", evidence="Port 22 open",
                agent_id=str(uuid.uuid4()), timestamp=datetime.now(UTC).isoformat(),
                tool="nmap", topic="f:a:p", signature="p1",
            ),
            Finding(
                id=str(uuid.uuid4()), type="open_port", severity="info",
                target="10.0.0.2", evidence="Port 80 open",
                agent_id=str(uuid.uuid4()), timestamp=datetime.now(UTC).isoformat(),
                tool="nmap", topic="f:b:p", signature="p2",
            ),
        ]

        detector = EmergentPatternDetector(confidence_minimum=0.7)
        patterns = detector.detect(findings)

        # Should not produce high-confidence patterns from basic port scans
        high_confidence = [p for p in patterns if p.confidence >= 0.8]
        assert len(high_confidence) == 0
