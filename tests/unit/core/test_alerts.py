"""Unit Tests for Situational Awareness Alerts - Story 10.6.

Tests for AlertType enum, AlertTrigger dataclass, AlertResponse dataclass,
and AlertDetector class following TDD methodology.

Test Coverage Requirements:
- AlertType enum values (NEW_SUBNET, DOMAIN_CONTROLLER, HONEYPOT, UNEXPECTED_SERVICE, SCOPE_DRIFT)
- AlertTrigger dataclass initialization and validation
- AlertTrigger.from_finding() factory method
- AlertTrigger.to_json() and from_json() serialization
- AlertResponse dataclass with Continue/Stop/Notes options
- Recommended action generation based on alert type
- AlertDetector detection methods
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest


class TestAlertType:
    """Tests for AlertType enum."""

    def test_alert_type_has_new_subnet(self) -> None:
        """Test AlertType has NEW_SUBNET value."""
        from cyberred.core.alerts import AlertType
        
        assert hasattr(AlertType, "NEW_SUBNET")
        assert AlertType.NEW_SUBNET.value == "new_subnet"

    def test_alert_type_has_domain_controller(self) -> None:
        """Test AlertType has DOMAIN_CONTROLLER value."""
        from cyberred.core.alerts import AlertType
        
        assert hasattr(AlertType, "DOMAIN_CONTROLLER")
        assert AlertType.DOMAIN_CONTROLLER.value == "domain_controller"

    def test_alert_type_has_honeypot(self) -> None:
        """Test AlertType has HONEYPOT value."""
        from cyberred.core.alerts import AlertType
        
        assert hasattr(AlertType, "HONEYPOT")
        assert AlertType.HONEYPOT.value == "honeypot"

    def test_alert_type_has_unexpected_service(self) -> None:
        """Test AlertType has UNEXPECTED_SERVICE value."""
        from cyberred.core.alerts import AlertType
        
        assert hasattr(AlertType, "UNEXPECTED_SERVICE")
        assert AlertType.UNEXPECTED_SERVICE.value == "unexpected_service"

    def test_alert_type_has_scope_drift(self) -> None:
        """Test AlertType has SCOPE_DRIFT value."""
        from cyberred.core.alerts import AlertType
        
        assert hasattr(AlertType, "SCOPE_DRIFT")
        assert AlertType.SCOPE_DRIFT.value == "scope_drift"

    def test_alert_type_is_str_enum(self) -> None:
        """Test AlertType is a StrEnum for JSON serialization."""
        from enum import StrEnum
        from cyberred.core.alerts import AlertType
        
        assert issubclass(AlertType, StrEnum)


class TestAlertSeverity:
    """Tests for AlertSeverity enum."""

    def test_alert_severity_has_critical(self) -> None:
        """Test AlertSeverity has CRITICAL value."""
        from cyberred.core.alerts import AlertSeverity
        
        assert hasattr(AlertSeverity, "CRITICAL")
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_alert_severity_has_high(self) -> None:
        """Test AlertSeverity has HIGH value."""
        from cyberred.core.alerts import AlertSeverity
        
        assert hasattr(AlertSeverity, "HIGH")
        assert AlertSeverity.HIGH.value == "high"

    def test_alert_severity_has_medium(self) -> None:
        """Test AlertSeverity has MEDIUM value."""
        from cyberred.core.alerts import AlertSeverity
        
        assert hasattr(AlertSeverity, "MEDIUM")
        assert AlertSeverity.MEDIUM.value == "medium"


class TestAlertResponseDecision:
    """Tests for AlertResponseDecision enum."""

    def test_decision_has_continue(self) -> None:
        """Test AlertResponseDecision has CONTINUE value."""
        from cyberred.core.alerts import AlertResponseDecision
        
        assert hasattr(AlertResponseDecision, "CONTINUE")
        assert AlertResponseDecision.CONTINUE.value == "continue"

    def test_decision_has_stop(self) -> None:
        """Test AlertResponseDecision has STOP value."""
        from cyberred.core.alerts import AlertResponseDecision
        
        assert hasattr(AlertResponseDecision, "STOP")
        assert AlertResponseDecision.STOP.value == "stop"

    def test_decision_has_notes(self) -> None:
        """Test AlertResponseDecision has NOTES value (continue with notes)."""
        from cyberred.core.alerts import AlertResponseDecision
        
        assert hasattr(AlertResponseDecision, "NOTES")
        assert AlertResponseDecision.NOTES.value == "notes"


class TestAlertTrigger:
    """Tests for AlertTrigger dataclass."""

    def test_alert_trigger_initialization(self) -> None:
        """Test AlertTrigger can be initialized with required fields."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        alert_id = str(uuid.uuid4())
        trigger = AlertTrigger(
            id=alert_id,
            alert_type=AlertType.NEW_SUBNET,
            severity=AlertSeverity.HIGH,
            target="192.168.2.0/24",
            discovery_details="New subnet discovered during scan",
            risk_assessment="Network segment not in original scope",
            recommended_action="Review scope, consider expansion or stop",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        
        assert trigger.id == alert_id
        assert trigger.alert_type == AlertType.NEW_SUBNET
        assert trigger.severity == AlertSeverity.HIGH
        assert trigger.target == "192.168.2.0/24"
        assert "New subnet" in trigger.discovery_details

    def test_alert_trigger_with_finding_type(self) -> None:
        """Test AlertTrigger includes finding_type field."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        trigger = AlertTrigger(
            id=str(uuid.uuid4()),
            alert_type=AlertType.DOMAIN_CONTROLLER,
            severity=AlertSeverity.CRITICAL,
            target="192.168.1.10",
            discovery_details="Domain controller detected",
            risk_assessment="AD environment detected",
            recommended_action="Pause, assess AD scope",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            finding_type="domain_controller",
        )
        
        assert trigger.finding_type == "domain_controller"

    def test_alert_trigger_default_timestamp(self) -> None:
        """Test AlertTrigger generates default timestamp if not provided."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        trigger = AlertTrigger(
            id=str(uuid.uuid4()),
            alert_type=AlertType.HONEYPOT,
            severity=AlertSeverity.CRITICAL,
            target="192.168.1.50",
            discovery_details="Honeypot indicators detected",
            risk_assessment="Possible canary token",
            recommended_action="Stop immediately",
            agent_id=str(uuid.uuid4()),
        )
        
        assert trigger.timestamp is not None
        # Validate it's a valid ISO timestamp
        datetime.fromisoformat(trigger.timestamp.replace("Z", "+00:00"))

    def test_alert_trigger_origin_time_ns(self) -> None:
        """Test AlertTrigger has origin_time_ns for latency tracking (NFR5)."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        import time
        
        origin_ns = time.monotonic_ns()
        trigger = AlertTrigger(
            id=str(uuid.uuid4()),
            alert_type=AlertType.UNEXPECTED_SERVICE,
            severity=AlertSeverity.MEDIUM,
            target="192.168.1.100:8080",
            discovery_details="Unexpected web service on DB server",
            risk_assessment="Service not expected",
            recommended_action="Note and continue or investigate",
            agent_id=str(uuid.uuid4()),
            origin_time_ns=origin_ns,
        )
        
        assert trigger.origin_time_ns == origin_ns

    def test_alert_trigger_to_dict(self) -> None:
        """Test AlertTrigger.to_dict() serialization."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        alert_id = str(uuid.uuid4())
        agent_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        trigger = AlertTrigger(
            id=alert_id,
            alert_type=AlertType.SCOPE_DRIFT,
            severity=AlertSeverity.HIGH,
            target="10.0.0.0/8",
            discovery_details="Cumulative scope expansion detected",
            risk_assessment="Scope has drifted beyond boundaries",
            recommended_action="Review engagement boundaries",
            agent_id=agent_id,
            timestamp=timestamp,
        )
        
        data = trigger.to_dict()
        
        assert data["id"] == alert_id
        assert data["alert_type"] == "scope_drift"
        assert data["severity"] == "high"
        assert data["target"] == "10.0.0.0/8"
        assert data["agent_id"] == agent_id
        assert isinstance(data, dict)

    def test_alert_trigger_to_json(self) -> None:
        """Test AlertTrigger.to_json() serialization."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        alert_id = str(uuid.uuid4())
        agent_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        trigger = AlertTrigger(
            id=alert_id,
            alert_type=AlertType.SCOPE_DRIFT,
            severity=AlertSeverity.HIGH,
            target="10.0.0.0/8",
            discovery_details="Cumulative scope expansion detected",
            risk_assessment="Scope has drifted beyond boundaries",
            recommended_action="Review engagement boundaries",
            agent_id=agent_id,
            timestamp=timestamp,
        )
        
        json_str = trigger.to_json()
        data = json.loads(json_str)
        
        assert data["id"] == alert_id
        assert data["alert_type"] == "scope_drift"
        assert data["severity"] == "high"
        assert data["target"] == "10.0.0.0/8"
        assert data["agent_id"] == agent_id

    def test_alert_trigger_from_json(self) -> None:
        """Test AlertTrigger.from_json() deserialization."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        alert_id = str(uuid.uuid4())
        agent_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        data = {
            "id": alert_id,
            "alert_type": "new_subnet",
            "severity": "high",
            "target": "192.168.2.0/24",
            "discovery_details": "New subnet found",
            "risk_assessment": "Not in scope",
            "recommended_action": "Review scope",
            "agent_id": agent_id,
            "timestamp": timestamp,
        }
        
        trigger = AlertTrigger.from_json(data)
        
        assert trigger.id == alert_id
        assert trigger.alert_type == AlertType.NEW_SUBNET
        assert trigger.severity == AlertSeverity.HIGH
        assert trigger.target == "192.168.2.0/24"

    def test_alert_trigger_from_json_string(self) -> None:
        """Test AlertTrigger.from_json() with JSON string input."""
        from cyberred.core.alerts import AlertTrigger, AlertType
        
        alert_id = str(uuid.uuid4())
        agent_id = str(uuid.uuid4())
        
        json_str = json.dumps({
            "id": alert_id,
            "alert_type": "honeypot",
            "severity": "critical",
            "target": "192.168.1.50",
            "discovery_details": "Canary detected",
            "risk_assessment": "Detection risk",
            "recommended_action": "Stop now",
            "agent_id": agent_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        trigger = AlertTrigger.from_json(json_str)
        
        assert trigger.id == alert_id
        assert trigger.alert_type == AlertType.HONEYPOT

    def test_alert_trigger_from_finding(self) -> None:
        """Test AlertTrigger.from_finding() factory method."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        from cyberred.core.models import Finding
        
        finding = Finding(
            id=str(uuid.uuid4()),
            type="new_subnet",
            severity="high",
            target="192.168.2.0/24",
            evidence="Discovered subnet 192.168.2.0/24 during nmap scan",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="nmap",
            topic="findings:test:new_subnet",
            signature="test-sig",
        )
        
        trigger = AlertTrigger.from_finding(finding, AlertType.NEW_SUBNET)
        
        assert trigger.target == finding.target
        assert trigger.agent_id == finding.agent_id
        assert trigger.alert_type == AlertType.NEW_SUBNET
        assert finding.evidence in trigger.discovery_details


class TestAlertResponse:
    """Tests for AlertResponse dataclass."""

    def test_alert_response_continue(self) -> None:
        """Test AlertResponse with CONTINUE decision."""
        from cyberred.core.alerts import AlertResponse, AlertResponseDecision
        
        response = AlertResponse(
            alert_id=str(uuid.uuid4()),
            decision=AlertResponseDecision.CONTINUE,
            operator="test_operator",
        )
        
        assert response.decision == AlertResponseDecision.CONTINUE
        assert response.operator == "test_operator"
        assert response.notes is None

    def test_alert_response_stop(self) -> None:
        """Test AlertResponse with STOP decision."""
        from cyberred.core.alerts import AlertResponse, AlertResponseDecision
        
        response = AlertResponse(
            alert_id=str(uuid.uuid4()),
            decision=AlertResponseDecision.STOP,
            operator="test_operator",
            notes="Stopping due to honeypot detection",
        )
        
        assert response.decision == AlertResponseDecision.STOP
        assert "honeypot" in response.notes

    def test_alert_response_with_notes(self) -> None:
        """Test AlertResponse with NOTES decision (continue with notes)."""
        from cyberred.core.alerts import AlertResponse, AlertResponseDecision
        
        response = AlertResponse(
            alert_id=str(uuid.uuid4()),
            decision=AlertResponseDecision.NOTES,
            operator="test_operator",
            notes="Acknowledged, continuing with monitoring",
        )
        
        assert response.decision == AlertResponseDecision.NOTES
        assert response.notes == "Acknowledged, continuing with monitoring"

    def test_alert_response_default_timestamp(self) -> None:
        """Test AlertResponse generates default timestamp."""
        from cyberred.core.alerts import AlertResponse, AlertResponseDecision
        
        response = AlertResponse(
            alert_id=str(uuid.uuid4()),
            decision=AlertResponseDecision.CONTINUE,
            operator="test_operator",
        )
        
        assert response.timestamp is not None
        datetime.fromisoformat(response.timestamp.replace("Z", "+00:00"))

    def test_alert_response_to_dict(self) -> None:
        """Test AlertResponse.to_dict() for audit logging."""
        from cyberred.core.alerts import AlertResponse, AlertResponseDecision
        
        alert_id = str(uuid.uuid4())
        response = AlertResponse(
            alert_id=alert_id,
            decision=AlertResponseDecision.STOP,
            operator="test_operator",
            notes="Test notes",
        )
        
        data = response.to_dict()
        
        assert data["alert_id"] == alert_id
        assert data["decision"] == "stop"
        assert data["operator"] == "test_operator"
        assert data["notes"] == "Test notes"
        assert "timestamp" in data


class TestRecommendedAction:
    """Tests for recommended action generation based on alert type."""

    def test_recommended_action_new_subnet(self) -> None:
        """Test recommended action for NEW_SUBNET alert."""
        from cyberred.core.alerts import get_recommended_action, AlertType
        
        action = get_recommended_action(AlertType.NEW_SUBNET)
        
        assert "scope" in action.lower()
        assert "review" in action.lower() or "expansion" in action.lower()

    def test_recommended_action_domain_controller(self) -> None:
        """Test recommended action for DOMAIN_CONTROLLER alert."""
        from cyberred.core.alerts import get_recommended_action, AlertType
        
        action = get_recommended_action(AlertType.DOMAIN_CONTROLLER)
        
        assert "pause" in action.lower() or "ad" in action.lower()

    def test_recommended_action_honeypot(self) -> None:
        """Test recommended action for HONEYPOT alert."""
        from cyberred.core.alerts import get_recommended_action, AlertType
        
        action = get_recommended_action(AlertType.HONEYPOT)
        
        assert "stop" in action.lower()

    def test_recommended_action_unexpected_service(self) -> None:
        """Test recommended action for UNEXPECTED_SERVICE alert."""
        from cyberred.core.alerts import get_recommended_action, AlertType
        
        action = get_recommended_action(AlertType.UNEXPECTED_SERVICE)
        
        assert "note" in action.lower() or "investigate" in action.lower()

    def test_recommended_action_scope_drift(self) -> None:
        """Test recommended action for SCOPE_DRIFT alert."""
        from cyberred.core.alerts import get_recommended_action, AlertType
        
        action = get_recommended_action(AlertType.SCOPE_DRIFT)
        
        assert "review" in action.lower() or "boundaries" in action.lower()


class TestAlertSeverityMapping:
    """Tests for alert type to severity mapping."""

    def test_honeypot_is_critical(self) -> None:
        """Test HONEYPOT alerts are CRITICAL severity."""
        from cyberred.core.alerts import get_default_severity, AlertType, AlertSeverity
        
        severity = get_default_severity(AlertType.HONEYPOT)
        assert severity == AlertSeverity.CRITICAL

    def test_domain_controller_is_critical(self) -> None:
        """Test DOMAIN_CONTROLLER alerts are CRITICAL severity."""
        from cyberred.core.alerts import get_default_severity, AlertType, AlertSeverity
        
        severity = get_default_severity(AlertType.DOMAIN_CONTROLLER)
        assert severity == AlertSeverity.CRITICAL

    def test_new_subnet_is_high(self) -> None:
        """Test NEW_SUBNET alerts are HIGH severity."""
        from cyberred.core.alerts import get_default_severity, AlertType, AlertSeverity
        
        severity = get_default_severity(AlertType.NEW_SUBNET)
        assert severity == AlertSeverity.HIGH

    def test_scope_drift_is_high(self) -> None:
        """Test SCOPE_DRIFT alerts are HIGH severity."""
        from cyberred.core.alerts import get_default_severity, AlertType, AlertSeverity
        
        severity = get_default_severity(AlertType.SCOPE_DRIFT)
        assert severity == AlertSeverity.HIGH

    def test_unexpected_service_is_medium(self) -> None:
        """Test UNEXPECTED_SERVICE alerts are MEDIUM severity."""
        from cyberred.core.alerts import get_default_severity, AlertType, AlertSeverity
        
        severity = get_default_severity(AlertType.UNEXPECTED_SERVICE)
        assert severity == AlertSeverity.MEDIUM


class TestAlertDetector:
    """Tests for AlertDetector class."""

    def test_detector_initialization(self) -> None:
        """Test AlertDetector can be initialized."""
        from cyberred.core.alerts import AlertDetector
        
        detector = AlertDetector()
        assert detector is not None

    def test_detector_with_scope(self) -> None:
        """Test AlertDetector can be initialized with scope."""
        from cyberred.core.alerts import AlertDetector
        from cyberred.core.models import Scope
        
        scope = Scope(networks=["192.168.1.0/24"])
        detector = AlertDetector(scope=scope)
        
        assert detector.scope == scope

    def test_detect_new_subnet(self) -> None:
        """Test AlertDetector.detect_new_subnet() method."""
        from cyberred.core.alerts import AlertDetector, AlertType
        from cyberred.core.models import Scope, Finding
        
        scope = Scope(networks=["192.168.1.0/24"])
        detector = AlertDetector(scope=scope)
        
        # Finding in a different subnet
        finding = Finding(
            id=str(uuid.uuid4()),
            type="host_discovered",
            severity="info",
            target="192.168.2.50",
            evidence="Host discovered",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="nmap",
            topic="findings:test:host",
            signature="test-sig",
        )
        
        result = detector.detect_new_subnet(finding)
        
        assert result is not None
        assert result.alert_type == AlertType.NEW_SUBNET

    def test_detect_new_subnet_in_scope(self) -> None:
        """Test detect_new_subnet returns None for in-scope target."""
        from cyberred.core.alerts import AlertDetector
        from cyberred.core.models import Scope, Finding
        
        scope = Scope(networks=["192.168.1.0/24"])
        detector = AlertDetector(scope=scope)
        
        # Finding in scope
        finding = Finding(
            id=str(uuid.uuid4()),
            type="host_discovered",
            severity="info",
            target="192.168.1.50",
            evidence="Host discovered",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="nmap",
            topic="findings:test:host",
            signature="test-sig",
        )
        
        result = detector.detect_new_subnet(finding)
        
        assert result is None

    def test_detect_domain_controller(self) -> None:
        """Test AlertDetector.detect_domain_controller() method."""
        from cyberred.core.alerts import AlertDetector, AlertType
        from cyberred.core.models import Finding
        
        detector = AlertDetector()
        
        # Finding indicating domain controller
        finding = Finding(
            id=str(uuid.uuid4()),
            type="domain_controller",
            severity="critical",
            target="192.168.1.10",
            evidence="LDAP on 389, Kerberos on 88, DNS on 53",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="nmap",
            topic="findings:test:dc",
            signature="test-sig",
        )
        
        result = detector.detect_domain_controller(finding)
        
        assert result is not None
        assert result.alert_type == AlertType.DOMAIN_CONTROLLER

    def test_detect_honeypot(self) -> None:
        """Test AlertDetector.detect_honeypot() method."""
        from cyberred.core.alerts import AlertDetector, AlertType
        from cyberred.core.models import Finding
        
        detector = AlertDetector()
        
        # Finding with honeypot indicators
        finding = Finding(
            id=str(uuid.uuid4()),
            type="honeypot_indicator",
            severity="critical",
            target="192.168.1.50",
            evidence="Canary token detected: AWS credentials in file",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="manual",
            topic="findings:test:honeypot",
            signature="test-sig",
        )
        
        result = detector.detect_honeypot(finding)
        
        assert result is not None
        assert result.alert_type == AlertType.HONEYPOT

    def test_detect_honeypot_by_evidence(self) -> None:
        """Test detect_honeypot detects canary tokens in evidence."""
        from cyberred.core.alerts import AlertDetector, AlertType
        from cyberred.core.models import Finding
        
        detector = AlertDetector()
        
        # Finding with canary in evidence
        finding = Finding(
            id=str(uuid.uuid4()),
            type="file_found",
            severity="info",
            target="192.168.1.50",
            evidence="Found file containing CANARY_TOKEN_XYZ",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="find",
            topic="findings:test:file",
            signature="test-sig",
        )
        
        result = detector.detect_honeypot(finding)
        
        assert result is not None
        assert result.alert_type == AlertType.HONEYPOT

    def test_detect_unexpected_service(self) -> None:
        """Test AlertDetector.detect_unexpected_service() method."""
        from cyberred.core.alerts import AlertDetector, AlertType
        from cyberred.core.models import Finding
        
        # Expected services for a database server
        expected_services = {"3306", "22"}  # MySQL and SSH only
        detector = AlertDetector(expected_services=expected_services)
        
        # Finding of unexpected web service - use URL format for port
        finding = Finding(
            id=str(uuid.uuid4()),
            type="open_port",
            severity="info",
            target="http://192.168.1.100:8080",
            evidence="HTTP service detected on port 8080",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="nmap",
            topic="findings:test:port",
            signature="test-sig",
        )
        
        result = detector.detect_unexpected_service(finding)
        
        assert result is not None
        assert result.alert_type == AlertType.UNEXPECTED_SERVICE

    def test_detect_scope_drift(self) -> None:
        """Test AlertDetector.detect_scope_drift() method."""
        from cyberred.core.alerts import AlertDetector, AlertType
        from cyberred.core.models import Scope
        
        scope = Scope(networks=["192.168.1.0/24"])
        detector = AlertDetector(scope=scope, drift_threshold=3)
        
        # Simulate cumulative out-of-scope discoveries
        detector.record_out_of_scope_discovery("192.168.2.1")
        detector.record_out_of_scope_discovery("192.168.2.2")
        detector.record_out_of_scope_discovery("192.168.2.3")
        
        result = detector.detect_scope_drift()
        
        assert result is not None
        assert result.alert_type == AlertType.SCOPE_DRIFT

    def test_detect_scope_drift_below_threshold(self) -> None:
        """Test detect_scope_drift returns None below threshold."""
        from cyberred.core.alerts import AlertDetector
        from cyberred.core.models import Scope
        
        scope = Scope(networks=["192.168.1.0/24"])
        detector = AlertDetector(scope=scope, drift_threshold=5)
        
        # Only 2 out-of-scope discoveries (below threshold of 5)
        detector.record_out_of_scope_discovery("192.168.2.1")
        detector.record_out_of_scope_discovery("192.168.2.2")
        
        result = detector.detect_scope_drift()
        
        assert result is None

    def test_detect_scope_drift_fires_only_once(self) -> None:
        """Test detect_scope_drift only fires once (prevents duplicate alerts)."""
        from cyberred.core.alerts import AlertDetector, AlertType
        from cyberred.core.models import Scope
        
        scope = Scope(networks=["192.168.1.0/24"])
        detector = AlertDetector(scope=scope, drift_threshold=3)
        
        # Exceed threshold
        detector.record_out_of_scope_discovery("192.168.2.1")
        detector.record_out_of_scope_discovery("192.168.2.2")
        detector.record_out_of_scope_discovery("192.168.2.3")
        
        # First call should return alert
        result1 = detector.detect_scope_drift()
        assert result1 is not None
        assert result1.alert_type == AlertType.SCOPE_DRIFT
        
        # Second call should return None (already fired)
        result2 = detector.detect_scope_drift()
        assert result2 is None
        
        # Add more discoveries - should still not fire again
        detector.record_out_of_scope_discovery("192.168.2.4")
        result3 = detector.detect_scope_drift()
        assert result3 is None

    def test_reset_drift_alert_allows_re_detection(self) -> None:
        """Test reset_drift_alert() allows re-detection."""
        from cyberred.core.alerts import AlertDetector, AlertType
        from cyberred.core.models import Scope
        
        scope = Scope(networks=["192.168.1.0/24"])
        detector = AlertDetector(scope=scope, drift_threshold=3)
        
        # Exceed threshold
        detector.record_out_of_scope_discovery("192.168.2.1")
        detector.record_out_of_scope_discovery("192.168.2.2")
        detector.record_out_of_scope_discovery("192.168.2.3")
        
        # First call fires
        result1 = detector.detect_scope_drift()
        assert result1 is not None
        
        # Reset and add more discoveries
        detector.reset_drift_alert()
        detector.record_out_of_scope_discovery("192.168.2.4")
        detector.record_out_of_scope_discovery("192.168.2.5")
        
        # Now should fire again (still >= threshold)
        result2 = detector.detect_scope_drift()
        assert result2 is not None
        assert result2.alert_type == AlertType.SCOPE_DRIFT

    def test_is_in_scope_no_scope_configured(self) -> None:
        """Test _is_in_scope returns True when no scope configured."""
        from cyberred.core.alerts import AlertDetector
        from cyberred.core.models import Finding
        
        # No scope configured
        detector = AlertDetector(scope=None)
        
        finding = Finding(
            id=str(uuid.uuid4()),
            type="host_discovered",
            severity="info",
            target="192.168.2.50",
            evidence="Host discovered",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="nmap",
            topic="findings:test:host",
            signature="test-sig",
        )
        
        # Should not trigger new_subnet since no scope configured (all in scope)
        result = detector.detect_new_subnet(finding)
        assert result is None

    def test_is_in_scope_with_network_cidr_target(self) -> None:
        """Test _is_in_scope handles network CIDR as target."""
        from cyberred.core.alerts import AlertDetector
        from cyberred.core.models import Scope, Finding
        
        scope = Scope(networks=["10.0.0.0/8"])
        detector = AlertDetector(scope=scope)
        
        # Subnet within scope
        finding = Finding(
            id=str(uuid.uuid4()),
            type="subnet_discovered",
            severity="info",
            target="10.1.0.0/16",  # CIDR, not single IP
            evidence="Subnet discovered",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="nmap",
            topic="findings:test:subnet",
            signature="test-sig",
        )
        
        # Should be in scope (subnet of 10.0.0.0/8)
        result = detector.detect_new_subnet(finding)
        assert result is None

    def test_is_in_scope_with_network_cidr_out_of_scope(self) -> None:
        """Test _is_in_scope detects network CIDR out of scope."""
        from cyberred.core.alerts import AlertDetector, AlertType
        from cyberred.core.models import Scope, Finding
        
        scope = Scope(networks=["10.0.0.0/8"])
        detector = AlertDetector(scope=scope)
        
        # Subnet outside scope
        finding = Finding(
            id=str(uuid.uuid4()),
            type="subnet_discovered",
            severity="info",
            target="192.168.0.0/16",  # Not in 10.0.0.0/8
            evidence="Subnet discovered",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="nmap",
            topic="findings:test:subnet",
            signature="test-sig",
        )
        
        result = detector.detect_new_subnet(finding)
        assert result is not None
        assert result.alert_type == AlertType.NEW_SUBNET

    def test_is_in_scope_with_hostname_target(self) -> None:
        """Test _is_in_scope handles hostname as target (assumes in scope)."""
        from cyberred.core.alerts import AlertDetector
        from cyberred.core.models import Scope, Finding
        
        scope = Scope(networks=["192.168.1.0/24"])
        detector = AlertDetector(scope=scope)
        
        # Hostname target (not valid IP)
        finding = Finding(
            id=str(uuid.uuid4()),
            type="host_discovered",
            severity="info",
            target="webserver.internal.local",  # Hostname, not IP
            evidence="Host discovered",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="nmap",
            topic="findings:test:host",
            signature="test-sig",
        )
        
        # Hostname should be assumed in scope (can't validate)
        result = detector.detect_new_subnet(finding)
        assert result is None

    def test_is_in_scope_with_invalid_scope_network(self) -> None:
        """Test _is_in_scope handles invalid scope network entries gracefully."""
        from cyberred.core.alerts import AlertDetector
        from cyberred.core.models import Scope, Finding
        
        # Scope with invalid network entry
        scope = Scope(networks=["invalid-network", "192.168.1.0/24"])
        detector = AlertDetector(scope=scope)
        
        # Valid IP in valid network
        finding = Finding(
            id=str(uuid.uuid4()),
            type="host_discovered",
            severity="info",
            target="192.168.1.50",
            evidence="Host discovered",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="nmap",
            topic="findings:test:host",
            signature="test-sig",
        )
        
        # Should still work with valid network entry
        result = detector.detect_new_subnet(finding)
        assert result is None

    def test_is_in_scope_with_port_in_target(self) -> None:
        """Test _is_in_scope handles target with port correctly."""
        from cyberred.core.alerts import AlertDetector
        from cyberred.core.models import Scope, Finding
        
        scope = Scope(networks=["192.168.1.0/24"])
        detector = AlertDetector(scope=scope)
        
        # Target with port (URL format is valid)
        finding = Finding(
            id=str(uuid.uuid4()),
            type="open_port",
            severity="info",
            target="https://192.168.1.50:443",  # URL with port
            evidence="Port 443 open",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="nmap",
            topic="findings:test:port",
            signature="test-sig",
        )
        
        # Should extract IP and check scope
        result = detector.detect_new_subnet(finding)
        assert result is None

    def test_analyze_finding(self) -> None:
        """Test AlertDetector.analyze_finding() runs all detectors."""
        from cyberred.core.alerts import AlertDetector, AlertType
        from cyberred.core.models import Scope, Finding
        
        scope = Scope(networks=["192.168.1.0/24"])
        detector = AlertDetector(scope=scope)
        
        # Finding that should trigger NEW_SUBNET
        finding = Finding(
            id=str(uuid.uuid4()),
            type="host_discovered",
            severity="info",
            target="10.0.0.1",
            evidence="Host discovered",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="nmap",
            topic="findings:test:host",
            signature="test-sig",
        )
        
        alerts = detector.analyze_finding(finding)
        
        assert len(alerts) >= 1
        assert any(a.alert_type == AlertType.NEW_SUBNET for a in alerts)
