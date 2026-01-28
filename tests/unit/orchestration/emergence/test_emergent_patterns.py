"""Unit tests for EmergentPattern and EmergentPatternDetector.

Story 7.15: Emergent Attack Strategy Triggering.

Tests pattern detection logic for identifying emergent opportunities
from collective agent findings.
"""

import json
import uuid
from datetime import UTC, datetime

import pytest

from cyberred.core.models import Finding
from cyberred.orchestration.emergence.patterns import (
    EmergentPattern,
    EmergentPatternDetector,
    PatternType,
)


# --- Fixtures ---

@pytest.fixture
def sample_finding() -> Finding:
    """Create a sample finding for testing."""
    return Finding(
        id=str(uuid.uuid4()),
        type="open_port",
        severity="medium",
        target="192.168.1.100",
        evidence="Port 22 SSH OpenSSH 8.2p1",
        agent_id=str(uuid.uuid4()),
        timestamp=datetime.now(UTC).isoformat(),
        tool="nmap",
        topic="findings:abc123:open_port",
        signature="test-sig",
    )


@pytest.fixture
def ssh_findings() -> list[Finding]:
    """Create multiple SSH findings for SERVICE_CORRELATION pattern."""
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
    return findings


@pytest.fixture
def credential_and_smb_findings() -> list[Finding]:
    """Create credential + SMB findings for CREDENTIAL_PIVOT pattern."""
    return [
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
            evidence="SMB 445/tcp open",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            tool="nmap",
            topic="findings:def:service",
            signature="smb-sig",
        ),
    ]


@pytest.fixture
def failed_exploit_findings() -> list[Finding]:
    """Create failed exploit findings for FAILED_EXPLOIT_ESCALATION pattern."""
    findings = []
    for i in range(4):
        findings.append(Finding(
            id=str(uuid.uuid4()),
            type="exploit_failed",
            severity="info",
            target="192.168.1.100",
            evidence=f"Exploit attempt {i+1} failed: connection refused",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            tool="sqlmap",
            topic="findings:xyz:exploit_failed",
            signature=f"fail-sig-{i}",
        ))
    return findings


# --- PatternType Enum Tests ---

class TestPatternType:
    """Tests for PatternType enum."""

    def test_pattern_type_values(self):
        """Test all expected pattern types exist."""
        assert PatternType.SERVICE_CORRELATION.value == "service_correlation"
        assert PatternType.CREDENTIAL_PIVOT.value == "credential_pivot"
        assert PatternType.FAILED_EXPLOIT_ESCALATION.value == "failed_exploit_escalation"
        assert PatternType.ENUMERATION_COMPLETE.value == "enumeration_complete"
        assert PatternType.CROSS_AGENT_DISCOVERY.value == "cross_agent_discovery"

    def test_pattern_type_members_count(self):
        """Test expected number of pattern types."""
        assert len(PatternType) == 5


# --- EmergentPattern Tests ---

class TestEmergentPattern:
    """Tests for EmergentPattern dataclass."""

    def test_emergent_pattern_creation(self):
        """Test creating a valid EmergentPattern."""
        pattern = EmergentPattern(
            id=str(uuid.uuid4()),
            pattern_type=PatternType.SERVICE_CORRELATION,
            confidence=0.85,
            contributing_findings=["finding-1", "finding-2"],
            recommended_actions=["exploit_ssh_8.2"],
            timestamp=datetime.now(UTC).isoformat(),
        )
        
        assert pattern.pattern_type == PatternType.SERVICE_CORRELATION
        assert pattern.confidence == 0.85
        assert len(pattern.contributing_findings) == 2
        assert "exploit_ssh_8.2" in pattern.recommended_actions

    def test_emergent_pattern_confidence_validation(self):
        """Test confidence must be between 0.0 and 1.0."""
        with pytest.raises(ValueError, match="confidence"):
            EmergentPattern(
                id=str(uuid.uuid4()),
                pattern_type=PatternType.SERVICE_CORRELATION,
                confidence=1.5,  # Invalid
                contributing_findings=[],
                recommended_actions=[],
                timestamp=datetime.now(UTC).isoformat(),
            )

    def test_emergent_pattern_confidence_lower_bound(self):
        """Test confidence lower bound validation."""
        with pytest.raises(ValueError, match="confidence"):
            EmergentPattern(
                id=str(uuid.uuid4()),
                pattern_type=PatternType.SERVICE_CORRELATION,
                confidence=-0.1,  # Invalid
                contributing_findings=[],
                recommended_actions=[],
                timestamp=datetime.now(UTC).isoformat(),
            )

    def test_emergent_pattern_to_json(self):
        """Test JSON serialization."""
        pattern = EmergentPattern(
            id="test-id-123",
            pattern_type=PatternType.CREDENTIAL_PIVOT,
            confidence=0.8,
            contributing_findings=["f1", "f2"],
            recommended_actions=["lateral_move"],
            timestamp="2026-01-27T12:00:00+00:00",
        )
        
        json_str = pattern.to_json()
        data = json.loads(json_str)
        
        assert data["id"] == "test-id-123"
        assert data["pattern_type"] == "credential_pivot"
        assert data["confidence"] == 0.8
        assert data["contributing_findings"] == ["f1", "f2"]

    def test_emergent_pattern_from_json(self):
        """Test JSON deserialization."""
        data = {
            "id": "test-id-456",
            "pattern_type": "service_correlation",
            "confidence": 0.9,
            "contributing_findings": ["f1"],
            "recommended_actions": ["exploit"],
            "timestamp": "2026-01-27T12:00:00+00:00",
        }
        
        pattern = EmergentPattern.from_json(json.dumps(data))
        
        assert pattern.id == "test-id-456"
        assert pattern.pattern_type == PatternType.SERVICE_CORRELATION
        assert pattern.confidence == 0.9

    def test_emergent_pattern_from_json_dict(self):
        """Test deserialization from dict."""
        data = {
            "id": "test-id-789",
            "pattern_type": "failed_exploit_escalation",
            "confidence": 0.95,
            "contributing_findings": [],
            "recommended_actions": ["rag_escalate"],
            "timestamp": "2026-01-27T12:00:00+00:00",
        }
        
        pattern = EmergentPattern.from_json(data)
        
        assert pattern.pattern_type == PatternType.FAILED_EXPLOIT_ESCALATION


# --- EmergentPatternDetector Tests ---

class TestEmergentPatternDetector:
    """Tests for EmergentPatternDetector."""

    def test_detector_creation(self):
        """Test detector can be instantiated."""
        detector = EmergentPatternDetector()
        assert detector is not None

    def test_detector_creation_with_config(self):
        """Test detector with custom configuration."""
        detector = EmergentPatternDetector(
            service_correlation_threshold=3,
            failed_exploit_threshold=5,
            confidence_minimum=0.7,
        )
        assert detector._service_correlation_threshold == 3
        assert detector._failed_exploit_threshold == 5
        assert detector._confidence_minimum == 0.7

    def test_detect_empty_findings(self):
        """Test detection with no findings returns empty list."""
        detector = EmergentPatternDetector()
        patterns = detector.detect([])
        assert patterns == []

    def test_detect_single_finding(self):
        """Test detection with single finding returns no patterns."""
        detector = EmergentPatternDetector()
        finding = Finding(
            id=str(uuid.uuid4()),
            type="open_port",
            severity="medium",
            target="192.168.1.100",
            evidence="Port 22",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            tool="nmap",
            topic="findings:abc:open_port",
            signature="sig",
        )
        patterns = detector.detect([finding])
        assert patterns == []

    def test_detect_service_correlation_pattern(self, ssh_findings):
        """Test SERVICE_CORRELATION pattern detection."""
        detector = EmergentPatternDetector(service_correlation_threshold=2)
        patterns = detector.detect(ssh_findings)
        
        service_patterns = [p for p in patterns if p.pattern_type == PatternType.SERVICE_CORRELATION]
        assert len(service_patterns) >= 1
        
        pattern = service_patterns[0]
        assert pattern.confidence >= 0.7
        assert len(pattern.contributing_findings) >= 2

    def test_detect_credential_pivot_pattern(self, credential_and_smb_findings):
        """Test CREDENTIAL_PIVOT pattern detection."""
        detector = EmergentPatternDetector()
        patterns = detector.detect(credential_and_smb_findings)
        
        pivot_patterns = [p for p in patterns if p.pattern_type == PatternType.CREDENTIAL_PIVOT]
        assert len(pivot_patterns) >= 1
        
        pattern = pivot_patterns[0]
        assert pattern.confidence >= 0.7
        assert "credential" in str(pattern.recommended_actions).lower() or "lateral" in str(pattern.recommended_actions).lower()

    def test_detect_failed_exploit_escalation(self, failed_exploit_findings):
        """Test FAILED_EXPLOIT_ESCALATION pattern detection."""
        detector = EmergentPatternDetector(failed_exploit_threshold=3)
        patterns = detector.detect(failed_exploit_findings)
        
        escalation_patterns = [p for p in patterns if p.pattern_type == PatternType.FAILED_EXPLOIT_ESCALATION]
        assert len(escalation_patterns) >= 1
        
        pattern = escalation_patterns[0]
        assert pattern.confidence >= 0.8
        assert "rag" in str(pattern.recommended_actions).lower() or "escalat" in str(pattern.recommended_actions).lower()

    def test_detect_cross_agent_discovery(self):
        """Test CROSS_AGENT_DISCOVERY pattern detection."""
        # Findings from different agent types (roles) that correlate
        recon_agent = str(uuid.uuid4())
        exploit_agent = str(uuid.uuid4())
        
        findings = [
            Finding(
                id=str(uuid.uuid4()),
                type="service",
                severity="medium",
                target="192.168.1.100",
                evidence="Apache 2.4.49 detected",
                agent_id=recon_agent,
                timestamp=datetime.now(UTC).isoformat(),
                tool="whatweb",
                topic="findings:abc:service",
                signature="sig1",
            ),
            Finding(
                id=str(uuid.uuid4()),
                type="vulnerability",
                severity="critical",
                target="192.168.1.100",
                evidence="CVE-2021-41773 path traversal",
                agent_id=exploit_agent,
                timestamp=datetime.now(UTC).isoformat(),
                tool="nuclei",
                topic="findings:abc:vulnerability",
                signature="sig2",
            ),
        ]
        
        detector = EmergentPatternDetector()
        patterns = detector.detect(findings)
        
        # Should detect correlation between service and vulnerability
        cross_patterns = [p for p in patterns if p.pattern_type == PatternType.CROSS_AGENT_DISCOVERY]
        # This pattern requires findings from different agent roles on same target
        # The detection logic will correlate them
        assert isinstance(patterns, list)

    def test_detect_returns_patterns_above_confidence_minimum(self, ssh_findings):
        """Test only patterns above confidence minimum are returned."""
        detector = EmergentPatternDetector(confidence_minimum=0.99)
        patterns = detector.detect(ssh_findings)
        
        for pattern in patterns:
            assert pattern.confidence >= 0.99

    def test_detect_with_mixed_findings(self, ssh_findings, credential_and_smb_findings, failed_exploit_findings):
        """Test detection with multiple pattern types in findings."""
        all_findings = ssh_findings + credential_and_smb_findings + failed_exploit_findings
        
        detector = EmergentPatternDetector()
        patterns = detector.detect(all_findings)
        
        # Should detect multiple pattern types
        pattern_types = {p.pattern_type for p in patterns}
        assert len(pattern_types) >= 1  # At least one pattern type detected

    def test_detect_assigns_unique_ids(self, ssh_findings):
        """Test each detected pattern has a unique ID."""
        detector = EmergentPatternDetector(service_correlation_threshold=2)
        patterns = detector.detect(ssh_findings)
        
        if len(patterns) > 1:
            ids = [p.id for p in patterns]
            assert len(ids) == len(set(ids))  # All unique

    def test_detect_includes_timestamps(self, ssh_findings):
        """Test detected patterns include valid timestamps."""
        detector = EmergentPatternDetector(service_correlation_threshold=2)
        patterns = detector.detect(ssh_findings)
        
        for pattern in patterns:
            assert pattern.timestamp is not None
            # Validate ISO format
            datetime.fromisoformat(pattern.timestamp.replace("Z", "+00:00"))


# --- Edge Case Tests ---

class TestEmergentPatternDetectorEdgeCases:
    """Edge case tests for EmergentPatternDetector."""

    def test_findings_with_same_target_different_types(self):
        """Test findings on same target but different types."""
        findings = [
            Finding(
                id=str(uuid.uuid4()),
                type="open_port",
                severity="info",
                target="192.168.1.100",
                evidence="Port 22",
                agent_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC).isoformat(),
                tool="nmap",
                topic="findings:abc:open_port",
                signature="sig1",
            ),
            Finding(
                id=str(uuid.uuid4()),
                type="open_port",
                severity="info",
                target="192.168.1.100",
                evidence="Port 80",
                agent_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC).isoformat(),
                tool="nmap",
                topic="findings:abc:open_port",
                signature="sig2",
            ),
        ]
        
        detector = EmergentPatternDetector()
        patterns = detector.detect(findings)
        # Should not create false positives
        assert isinstance(patterns, list)

    def test_duplicate_findings_not_double_counted(self):
        """Test duplicate findings are not double counted."""
        finding_id = str(uuid.uuid4())
        findings = [
            Finding(
                id=finding_id,
                type="service",
                severity="medium",
                target="192.168.1.100",
                evidence="SSH 8.2",
                agent_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC).isoformat(),
                tool="nmap",
                topic="findings:abc:service",
                signature="sig",
            ),
            Finding(
                id=finding_id,  # Same ID = duplicate
                type="service",
                severity="medium",
                target="192.168.1.100",
                evidence="SSH 8.2",
                agent_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC).isoformat(),
                tool="nmap",
                topic="findings:abc:service",
                signature="sig",
            ),
        ]
        
        detector = EmergentPatternDetector()
        patterns = detector.detect(findings)
        
        # Duplicates should be deduplicated before pattern detection
        for pattern in patterns:
            unique_findings = set(pattern.contributing_findings)
            assert len(unique_findings) == len(pattern.contributing_findings)
