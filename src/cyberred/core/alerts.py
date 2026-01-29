"""Situational Awareness Alerts for Story 10.6.

Provides alert types, triggers, responses, and detection for unexpected discoveries:
- AlertType enum: NEW_SUBNET, DOMAIN_CONTROLLER, HONEYPOT, UNEXPECTED_SERVICE, SCOPE_DRIFT
- AlertSeverity enum: CRITICAL, HIGH, MEDIUM
- AlertTrigger dataclass: Alert data with discovery details, risk assessment, recommended action
- AlertResponse dataclass: Response data with decision and notes
- AlertDetector class: Detection logic for unexpected discoveries
- Audit entry creation for FR23 compliance

FR22: Situational awareness alerts for unexpected discoveries
FR23: Alert response logging to audit trail
NFR5: Alert delivery <500ms (origin_time_ns for latency tracking)

UX Spec References:
- Lines 56: WebSocket push, interrupt without losing context
- Lines 502: Modal base for overlay
- Lines 549-555: Feedback patterns (Warning/Error persist)
- Lines 584: Target Unreachable auto-pause + alert
"""
from __future__ import annotations

import ipaddress
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from cyberred.core.models import Finding, Scope


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class AlertType(StrEnum):
    """Type of situational awareness alert.
    
    Values per story specification:
    - NEW_SUBNET: Agent finds network CIDR not in original scope
    - DOMAIN_CONTROLLER: Finding indicates domain controller presence
    - HONEYPOT: Canary tokens, fake services, unusual ports
    - UNEXPECTED_SERVICE: Service not expected on target
    - SCOPE_DRIFT: Cumulative target expansion exceeds threshold
    """
    NEW_SUBNET = "new_subnet"
    DOMAIN_CONTROLLER = "domain_controller"
    HONEYPOT = "honeypot"
    UNEXPECTED_SERVICE = "unexpected_service"
    SCOPE_DRIFT = "scope_drift"


class AlertSeverity(StrEnum):
    """Severity level for situational alerts.
    
    Severity mapping per story specification:
    - CRITICAL: HONEYPOT, DOMAIN_CONTROLLER (immediate action required)
    - HIGH: NEW_SUBNET, SCOPE_DRIFT (significant concern)
    - MEDIUM: UNEXPECTED_SERVICE (note and monitor)
    """
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"


class AlertResponseDecision(StrEnum):
    """Response decision options for situational alerts.
    
    Per story AC#4:
    - CONTINUE (C): Continue engagement
    - STOP (S): Pause engagement (not kill)
    - NOTES (N): Continue with notes added
    """
    CONTINUE = "continue"
    STOP = "stop"
    NOTES = "notes"


# ─────────────────────────────────────────────────────────────────────────────
# Recommended Actions and Severity Mapping
# ─────────────────────────────────────────────────────────────────────────────

_RECOMMENDED_ACTIONS: dict[AlertType, str] = {
    AlertType.NEW_SUBNET: "Review scope, consider expansion or stop",
    AlertType.DOMAIN_CONTROLLER: "Pause, assess AD environment scope",
    AlertType.HONEYPOT: "Stop immediately, assess detection risk",
    AlertType.UNEXPECTED_SERVICE: "Note and continue, or investigate",
    AlertType.SCOPE_DRIFT: "Review engagement boundaries",
}

_DEFAULT_SEVERITIES: dict[AlertType, AlertSeverity] = {
    AlertType.NEW_SUBNET: AlertSeverity.HIGH,
    AlertType.DOMAIN_CONTROLLER: AlertSeverity.CRITICAL,
    AlertType.HONEYPOT: AlertSeverity.CRITICAL,
    AlertType.UNEXPECTED_SERVICE: AlertSeverity.MEDIUM,
    AlertType.SCOPE_DRIFT: AlertSeverity.HIGH,
}


def get_recommended_action(alert_type: AlertType) -> str:
    """Get recommended action for an alert type.
    
    Args:
        alert_type: Type of situational alert.
        
    Returns:
        Recommended action string per story specification.
    """
    return _RECOMMENDED_ACTIONS.get(alert_type, "Review and assess")


def get_default_severity(alert_type: AlertType) -> AlertSeverity:
    """Get default severity for an alert type.
    
    Args:
        alert_type: Type of situational alert.
        
    Returns:
        Default severity level per story specification.
    """
    return _DEFAULT_SEVERITIES.get(alert_type, AlertSeverity.MEDIUM)


# ─────────────────────────────────────────────────────────────────────────────
# AlertTrigger Dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AlertTrigger:
    """Situational alert trigger with discovery context.
    
    Contains all information needed to display alert modal and log audit trail.
    
    Attributes:
        id: Unique alert identifier (UUID format).
        alert_type: Type of situational alert.
        severity: Alert severity level.
        target: Target IP/hostname/CIDR that triggered alert.
        discovery_details: Description of what was discovered.
        risk_assessment: Why this is unexpected/concerning.
        recommended_action: Suggested operator action.
        agent_id: ID of agent that made the discovery.
        timestamp: ISO 8601 timestamp of alert creation.
        finding_type: Original finding type if applicable.
        origin_time_ns: Monotonic nanoseconds for latency tracking (NFR5).
    """
    id: str
    alert_type: AlertType
    severity: AlertSeverity
    target: str
    discovery_details: str
    risk_assessment: str
    recommended_action: str
    agent_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finding_type: str | None = None
    origin_time_ns: int | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary with all fields, enums as string values.
        """
        data = asdict(self)
        # Convert enums to their string values
        data["alert_type"] = self.alert_type.value
        data["severity"] = self.severity.value
        return data
    
    def to_json(self) -> str:
        """Serialize to JSON string.
        
        Returns:
            JSON string representation.
        """
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, data: str | dict[str, Any]) -> "AlertTrigger":
        """Deserialize from JSON string or dict.
        
        Args:
            data: JSON string or dictionary.
            
        Returns:
            AlertTrigger instance.
        """
        if isinstance(data, str):
            data = json.loads(data)
        
        return cls(
            id=data["id"],
            alert_type=AlertType(data["alert_type"]),
            severity=AlertSeverity(data["severity"]),
            target=data["target"],
            discovery_details=data["discovery_details"],
            risk_assessment=data["risk_assessment"],
            recommended_action=data["recommended_action"],
            agent_id=data["agent_id"],
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            finding_type=data.get("finding_type"),
            origin_time_ns=data.get("origin_time_ns"),
        )
    
    @classmethod
    def from_finding(
        cls,
        finding: "Finding",
        alert_type: AlertType,
        risk_assessment: str | None = None,
    ) -> "AlertTrigger":
        """Create AlertTrigger from a Finding.
        
        Factory method to convert a Finding into an AlertTrigger.
        
        Args:
            finding: Source Finding instance.
            alert_type: Type of alert to create.
            risk_assessment: Optional custom risk assessment.
            
        Returns:
            AlertTrigger instance.
        """
        severity = get_default_severity(alert_type)
        recommended_action = get_recommended_action(alert_type)
        
        if risk_assessment is None:
            risk_assessment = f"Unexpected {alert_type.value} discovery requires attention"
        
        return cls(
            id=str(uuid.uuid4()),
            alert_type=alert_type,
            severity=severity,
            target=finding.target,
            discovery_details=finding.evidence,
            risk_assessment=risk_assessment,
            recommended_action=recommended_action,
            agent_id=finding.agent_id,
            finding_type=finding.type,
        )


# ─────────────────────────────────────────────────────────────────────────────
# AlertResponse Dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AlertResponse:
    """Response to a situational alert.
    
    Captures operator decision for audit trail per FR23.
    
    Attributes:
        alert_id: ID of the original alert.
        decision: Response decision (CONTINUE/STOP/NOTES).
        operator: Who made the decision.
        timestamp: ISO 8601 decision time.
        notes: Optional operator notes.
    """
    alert_id: str
    decision: AlertResponseDecision
    operator: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for audit logging.
        
        Returns:
            Dictionary representation.
        """
        return {
            "alert_id": self.alert_id,
            "decision": self.decision.value,
            "operator": self.operator,
            "timestamp": self.timestamp,
            "notes": self.notes,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Audit Entry Creation
# ─────────────────────────────────────────────────────────────────────────────

def create_audit_entry(
    alert: AlertTrigger,
    response: AlertResponse,
) -> dict[str, Any]:
    """Create audit entry for situational alert response.
    
    Format per FR23 specification:
    {
        "timestamp": "2026-01-15T14:30:00Z",
        "event_type": "situational_alert_response",
        "alert_id": "uuid-here",
        "alert_type": "HONEYPOT",
        "operator_response": "STOP",
        "notes": "Detected canary token...",
        "agent_id": "recon-47",
        "target": "192.168.1.50"
    }
    
    Args:
        alert: Original AlertTrigger.
        response: AlertResponse from operator.
        
    Returns:
        Audit entry dictionary.
    """
    return {
        "timestamp": response.timestamp,
        "event_type": "situational_alert_response",
        "alert_id": alert.id,
        "alert_type": alert.alert_type.value,
        "operator_response": response.decision.value,
        "decision": response.decision.value,
        "notes": response.notes,
        "agent_id": alert.agent_id,
        "target": alert.target,
        "severity": alert.severity.value,
    }


# ─────────────────────────────────────────────────────────────────────────────
# AlertDetector Class
# ─────────────────────────────────────────────────────────────────────────────

# Honeypot indicator patterns
_HONEYPOT_PATTERNS = [
    "canary",
    "honeypot",
    "honeyd",
    "cowrie",
    "kippo",
    "dionaea",
    "aws_credentials",
    "fake_service",
]

# Domain controller indicator finding types
_DC_FINDING_TYPES = [
    "domain_controller",
    "active_directory",
    "ldap_dc",
    "kerberos_kdc",
]


class AlertDetector:
    """Detector for situational awareness alerts.
    
    Analyzes findings to detect unexpected discoveries that require
    operator attention.
    
    Attributes:
        scope: Optional engagement scope for comparison.
        expected_services: Optional set of expected service ports.
        drift_threshold: Number of out-of-scope discoveries before drift alert.
        _out_of_scope_discoveries: Tracked out-of-scope targets.
        _drift_alert_fired: Whether scope drift alert has been fired.
    """
    
    def __init__(
        self,
        scope: Optional["Scope"] = None,
        expected_services: Optional[set[str]] = None,
        drift_threshold: int = 5,
    ) -> None:
        """Initialize AlertDetector.
        
        Args:
            scope: Engagement scope for comparison.
            expected_services: Set of expected service ports (e.g., {"22", "80"}).
            drift_threshold: Number of out-of-scope discoveries before drift alert.
        """
        self.scope = scope
        self.expected_services = expected_services or set()
        self.drift_threshold = drift_threshold
        self._out_of_scope_discoveries: set[str] = set()
        self._drift_alert_fired: bool = False
    
    def _is_in_scope(self, target: str) -> bool:
        """Check if target is within engagement scope.
        
        Args:
            target: Target IP address or CIDR.
            
        Returns:
            True if in scope, False otherwise.
        """
        if self.scope is None:
            return True
        
        # Extract IP from target (may have port)
        ip_str = target.split(":")[0]
        
        try:
            target_ip = ipaddress.ip_address(ip_str)
        except ValueError:
            # Not a valid IP, check if it's a network
            try:
                target_net = ipaddress.ip_network(ip_str, strict=False)
                # Check if any scope network contains this network
                for network in self.scope.networks:
                    try:
                        scope_net = ipaddress.ip_network(network, strict=False)
                        if target_net.subnet_of(scope_net):
                            return True
                    except ValueError:
                        continue
                return False
            except ValueError:
                # Not an IP or network, assume in scope
                return True
        
        # Check if IP is in any scope network
        for network in self.scope.networks:
            try:
                scope_net = ipaddress.ip_network(network, strict=False)
                if target_ip in scope_net:
                    return True
            except ValueError:
                continue
        
        return False
    
    def detect_new_subnet(self, finding: "Finding") -> Optional[AlertTrigger]:
        """Detect if finding is from a new subnet not in scope.
        
        Args:
            finding: Finding to analyze.
            
        Returns:
            AlertTrigger if new subnet detected, None otherwise.
        """
        if self._is_in_scope(finding.target):
            return None
        
        return AlertTrigger.from_finding(
            finding,
            AlertType.NEW_SUBNET,
            risk_assessment="Network segment not in original scope",
        )
    
    def detect_domain_controller(self, finding: "Finding") -> Optional[AlertTrigger]:
        """Detect if finding indicates a domain controller.
        
        Args:
            finding: Finding to analyze.
            
        Returns:
            AlertTrigger if DC detected, None otherwise.
        """
        # Check finding type
        if finding.type.lower() in _DC_FINDING_TYPES:
            return AlertTrigger.from_finding(
                finding,
                AlertType.DOMAIN_CONTROLLER,
                risk_assessment="Active Directory environment detected",
            )
        
        # Check evidence for DC indicators
        evidence_lower = finding.evidence.lower()
        dc_indicators = ["ldap", "kerberos", "port 389", "port 88", "port 53"]
        indicator_count = sum(1 for ind in dc_indicators if ind in evidence_lower)
        
        if indicator_count >= 2:
            return AlertTrigger.from_finding(
                finding,
                AlertType.DOMAIN_CONTROLLER,
                risk_assessment="Multiple AD service indicators detected",
            )
        
        return None
    
    def detect_honeypot(self, finding: "Finding") -> Optional[AlertTrigger]:
        """Detect if finding indicates a honeypot.
        
        Args:
            finding: Finding to analyze.
            
        Returns:
            AlertTrigger if honeypot detected, None otherwise.
        """
        # Check finding type
        if "honeypot" in finding.type.lower() or "canary" in finding.type.lower():
            return AlertTrigger.from_finding(
                finding,
                AlertType.HONEYPOT,
                risk_assessment="Honeypot/canary indicators detected - high detection risk",
            )
        
        # Check evidence for honeypot patterns
        evidence_lower = finding.evidence.lower()
        for pattern in _HONEYPOT_PATTERNS:
            if pattern in evidence_lower:
                return AlertTrigger.from_finding(
                    finding,
                    AlertType.HONEYPOT,
                    risk_assessment=f"Honeypot indicator detected: {pattern}",
                )
        
        return None
    
    def detect_unexpected_service(self, finding: "Finding") -> Optional[AlertTrigger]:
        """Detect if finding shows an unexpected service.
        
        Args:
            finding: Finding to analyze.
            
        Returns:
            AlertTrigger if unexpected service detected, None otherwise.
        """
        if not self.expected_services:
            return None
        
        # Extract port from target
        if ":" in finding.target:
            port = finding.target.split(":")[-1]
            if port not in self.expected_services:
                return AlertTrigger.from_finding(
                    finding,
                    AlertType.UNEXPECTED_SERVICE,
                    risk_assessment=f"Service on port {port} not in expected services list",
                )
        
        return None
    
    def record_out_of_scope_discovery(self, target: str) -> None:
        """Record an out-of-scope discovery for drift tracking.
        
        Args:
            target: Out-of-scope target discovered.
        """
        self._out_of_scope_discoveries.add(target)
    
    def detect_scope_drift(self) -> Optional[AlertTrigger]:
        """Detect if cumulative scope drift exceeds threshold.
        
        Only fires once per detector instance to avoid duplicate alerts.
        Call reset_drift_alert() to re-enable detection.
        
        Returns:
            AlertTrigger if scope drift detected (first time), None otherwise.
        """
        if self._drift_alert_fired:
            return None
        
        if len(self._out_of_scope_discoveries) >= self.drift_threshold:
            self._drift_alert_fired = True
            return AlertTrigger(
                id=str(uuid.uuid4()),
                alert_type=AlertType.SCOPE_DRIFT,
                severity=get_default_severity(AlertType.SCOPE_DRIFT),
                target=", ".join(list(self._out_of_scope_discoveries)[:5]),
                discovery_details=f"{len(self._out_of_scope_discoveries)} out-of-scope targets discovered",
                risk_assessment="Cumulative scope expansion exceeds threshold",
                recommended_action=get_recommended_action(AlertType.SCOPE_DRIFT),
                agent_id="system",
            )
        return None
    
    def reset_drift_alert(self) -> None:
        """Reset drift alert flag to allow re-detection.
        
        Call this after operator acknowledges drift alert to allow
        detection of further scope expansion.
        """
        self._drift_alert_fired = False
    
    def analyze_finding(self, finding: "Finding") -> list[AlertTrigger]:
        """Analyze a finding for all alert types.
        
        Runs all detection methods and returns any triggered alerts.
        
        Args:
            finding: Finding to analyze.
            
        Returns:
            List of AlertTrigger instances (may be empty).
        """
        alerts: list[AlertTrigger] = []
        
        # Run all detectors
        if alert := self.detect_new_subnet(finding):
            alerts.append(alert)
            self.record_out_of_scope_discovery(finding.target)
        
        if alert := self.detect_domain_controller(finding):
            alerts.append(alert)
        
        if alert := self.detect_honeypot(finding):
            alerts.append(alert)
        
        if alert := self.detect_unexpected_service(finding):
            alerts.append(alert)
        
        # Check for scope drift after recording
        if drift_alert := self.detect_scope_drift():
            # Only add if not already added
            if not any(a.alert_type == AlertType.SCOPE_DRIFT for a in alerts):
                alerts.append(drift_alert)
        
        return alerts


# ─────────────────────────────────────────────────────────────────────────────
# AlertResponseHandler - Story 10.7
# ─────────────────────────────────────────────────────────────────────────────

class AlertResponseHandler:
    """Handles operator responses to situational alerts.
    
    Processes Continue/Stop/Notes responses and coordinates with:
    - AlertAuditLogger for audit trail logging (FR23)
    - EngagementManager for pause operations (Stop = pause, not kill)
    
    Per story 10.7 technical notes:
    - Stop triggers engagement.pause(), NOT engagement.kill()
    - All responses are logged to audit trail
    
    Attributes:
        _audit: AlertAuditLogger for audit logging.
        _engagement: EngagementManager for state control.
    """
    
    def __init__(
        self,
        audit_logger: "AlertAuditLogger",
        engagement_manager: Any,
    ) -> None:
        """Initialize AlertResponseHandler.
        
        Args:
            audit_logger: AlertAuditLogger for audit trail operations.
            engagement_manager: EngagementManager for engagement state control.
        """
        self._audit = audit_logger
        self._engagement = engagement_manager
    
    async def handle_continue(
        self,
        alert: AlertTrigger,
        operator: str,
        notes: str | None = None,
    ) -> AlertResponse:
        """Handle Continue response - engagement continues normally.
        
        Args:
            alert: AlertTrigger that prompted the response.
            operator: Operator who made the decision.
            notes: Optional operator notes.
            
        Returns:
            AlertResponse with CONTINUE decision.
        """
        response = AlertResponse(
            alert_id=alert.id,
            decision=AlertResponseDecision.CONTINUE,
            operator=operator,
            notes=notes,
        )
        
        # Log to audit trail
        await self._audit.log_response(
            alert=alert,
            response=response,
            engagement_id=self._engagement.id,
        )
        
        return response
    
    async def handle_stop(
        self,
        alert: AlertTrigger,
        operator: str,
        notes: str | None = None,
    ) -> AlertResponse:
        """Handle Stop response - engagement pauses (NOT kill).
        
        Per story 10.7: Stop = engagement.pause(), not kill.
        
        Args:
            alert: AlertTrigger that prompted the response.
            operator: Operator who made the decision.
            notes: Optional operator notes.
            
        Returns:
            AlertResponse with STOP decision.
        """
        response = AlertResponse(
            alert_id=alert.id,
            decision=AlertResponseDecision.STOP,
            operator=operator,
            notes=notes,
        )
        
        # Pause the engagement (NOT kill!)
        await self._engagement.pause()
        
        # Log to audit trail
        await self._audit.log_response(
            alert=alert,
            response=response,
            engagement_id=self._engagement.id,
        )
        
        return response
    
    async def handle_response(
        self,
        alert: AlertTrigger,
        decision: AlertResponseDecision,
        operator: str,
        notes: str | None = None,
    ) -> AlertResponse:
        """Unified handler for all alert response types.
        
        Routes to appropriate handler based on decision type.
        
        Args:
            alert: AlertTrigger that prompted the response.
            decision: AlertResponseDecision (CONTINUE/STOP/NOTES).
            operator: Operator who made the decision.
            notes: Optional operator notes.
            
        Returns:
            AlertResponse instance.
        """
        if decision == AlertResponseDecision.STOP:
            return await self.handle_stop(alert, operator, notes)
        elif decision == AlertResponseDecision.NOTES:
            # NOTES = continue with notes (per story spec)
            return await self._handle_notes(alert, operator, notes)
        else:
            # CONTINUE
            return await self.handle_continue(alert, operator, notes)
    
    async def _handle_notes(
        self,
        alert: AlertTrigger,
        operator: str,
        notes: str | None = None,
    ) -> AlertResponse:
        """Handle Notes response - continue with notes added.
        
        NOTES decision means continue engagement but with notes recorded.
        
        Args:
            alert: AlertTrigger that prompted the response.
            operator: Operator who made the decision.
            notes: Operator notes (expected for NOTES decision).
            
        Returns:
            AlertResponse with NOTES decision.
        """
        response = AlertResponse(
            alert_id=alert.id,
            decision=AlertResponseDecision.NOTES,
            operator=operator,
            notes=notes,
        )
        
        # Log to audit trail (no pause for NOTES)
        await self._audit.log_response(
            alert=alert,
            response=response,
            engagement_id=self._engagement.id,
        )
        
        return response


# Type alias for AlertAuditLogger to avoid import issues
if TYPE_CHECKING:
    from cyberred.core.audit import AlertAuditLogger
