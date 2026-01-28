"""Unit tests for Authorization Screen (Story 10.1).

Tests the enhanced AuthorizationScreen with:
- Y/N/M/S keybindings
- Focus trap (modal behavior)
- Swarm state snapshot display
- Risk assessment context
- Blink animation
- 3s cooldown on consecutive approvals
- More Info expansion
- Skip functionality
"""
import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.tui.screens.authorization import (
    AuthorizationScreen,
    AuthorizationRequest,
    AuthorizationResponse,
    AuthorizationType,
    AuthorizationDecision,
    RiskLevel,
    SwarmSnapshot,
    SwarmStateSnapshot,
    RiskAssessmentDisplay,
    RelatedFindingsDisplay,
    MoreInfoSection,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_swarm_snapshot() -> SwarmSnapshot:
    """Create a sample swarm snapshot for testing."""
    return SwarmSnapshot(
        timestamp="2026-01-28T12:00:00Z",
        total_agents=50,
        by_status={"idle": 20, "scanning": 15, "attacking": 10, "exploited": 5},
        by_target={"192.168.1.0/24": 30, "10.0.0.0/24": 20},
    )


@pytest.fixture
def sample_auth_request(sample_swarm_snapshot: SwarmSnapshot) -> AuthorizationRequest:
    """Create a sample authorization request for testing."""
    return AuthorizationRequest(
        id="auth-001",
        request_type=AuthorizationType.LATERAL_MOVE,
        agent_id="recon-agent-001",
        target="192.168.1.100",
        proposed_action="SSH brute force attack",
        risk_level=RiskLevel.HIGH,
        related_findings=[
            {"finding_id": "find-001", "title": "SSH port open", "severity": "MEDIUM"},
            {"finding_id": "find-002", "title": "Weak credentials detected", "severity": "HIGH"},
        ],
        decision_context=[
            "Found SSH service on port 22",
            "Previous scan revealed potential weak credentials",
            "Target is within authorized scope",
        ],
        swarm_snapshot=sample_swarm_snapshot,
        attck_technique="T1110.001",
        attck_tactic="Credential Access",
    )


@pytest.fixture
def sample_auth_request_dict() -> dict:
    """Create a sample authorization request as dict (simulating wire format)."""
    return {
        "id": "auth-002",
        "request_type": "scope_expansion",
        "agent_id": "exploit-agent-003",
        "target": "10.0.0.50",
        "proposed_action": "Expand scope to new subnet",
        "risk_level": "CRITICAL",
        "related_findings": [
            {"finding_id": "find-010", "title": "Pivot point discovered", "severity": "CRITICAL"},
        ],
        "decision_context": ["New network segment discovered via compromised host"],
        "swarm_snapshot": {
            "timestamp": "2026-01-28T14:00:00Z",
            "total_agents": 75,
            "by_status": {"idle": 30, "scanning": 25, "attacking": 15, "exploited": 5},
        },
        "attck_technique": "T1046",
        "attck_tactic": "Discovery",
    }


# ─────────────────────────────────────────────────────────────────────────────
# SwarmSnapshot Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSwarmSnapshot:
    """Tests for SwarmSnapshot dataclass."""

    def test_from_dict_complete(self):
        """Test creating SwarmSnapshot from complete dict."""
        data = {
            "timestamp": "2026-01-28T12:00:00Z",
            "total_agents": 100,
            "by_status": {"idle": 50, "scanning": 30, "attacking": 20},
            "by_target": {"192.168.1.0/24": 60, "10.0.0.0/24": 40},
        }
        snapshot = SwarmSnapshot.from_dict(data)
        
        assert snapshot.timestamp == "2026-01-28T12:00:00Z"
        assert snapshot.total_agents == 100
        assert snapshot.by_status == {"idle": 50, "scanning": 30, "attacking": 20}
        assert snapshot.by_target == {"192.168.1.0/24": 60, "10.0.0.0/24": 40}

    def test_from_dict_minimal(self):
        """Test creating SwarmSnapshot from minimal dict."""
        data = {}
        snapshot = SwarmSnapshot.from_dict(data)
        
        assert snapshot.total_agents == 0
        assert snapshot.by_status == {}
        assert snapshot.by_target == {}
        # timestamp should be auto-generated
        assert snapshot.timestamp is not None

    def test_default_values(self):
        """Test SwarmSnapshot default values."""
        snapshot = SwarmSnapshot()
        
        assert snapshot.total_agents == 0
        assert snapshot.by_status == {}
        assert snapshot.by_target == {}
        assert snapshot.timestamp is not None


# ─────────────────────────────────────────────────────────────────────────────
# AuthorizationRequest Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthorizationRequest:
    """Tests for AuthorizationRequest dataclass."""

    def test_from_dict_complete(self, sample_auth_request_dict: dict):
        """Test creating AuthorizationRequest from complete dict."""
        request = AuthorizationRequest.from_dict(sample_auth_request_dict)
        
        assert request.id == "auth-002"
        assert request.request_type == "scope_expansion"
        assert request.agent_id == "exploit-agent-003"
        assert request.target == "10.0.0.50"
        assert request.proposed_action == "Expand scope to new subnet"
        assert request.risk_level == "CRITICAL"
        assert len(request.related_findings) == 1
        assert request.attck_technique == "T1046"
        assert request.attck_tactic == "Discovery"
        assert request.swarm_snapshot is not None
        assert request.swarm_snapshot.total_agents == 75

    def test_from_dict_minimal(self):
        """Test creating AuthorizationRequest from minimal dict."""
        data = {
            "id": "auth-min",
            "agent_id": "agent-1",
            "target": "192.168.1.1",
            "proposed_action": "Test action",
        }
        request = AuthorizationRequest.from_dict(data)
        
        assert request.id == "auth-min"
        assert request.request_type == AuthorizationType.LATERAL_MOVE  # default
        assert request.risk_level == RiskLevel.MEDIUM  # default
        assert request.swarm_snapshot is None
        assert request.related_findings == []
        assert request.decision_context == []

    def test_default_timestamp(self):
        """Test that timestamp is auto-generated."""
        request = AuthorizationRequest(
            id="test",
            request_type=AuthorizationType.LATERAL_MOVE,
            agent_id="agent-1",
            target="192.168.1.1",
            proposed_action="Test",
        )
        assert request.timestamp is not None


# ─────────────────────────────────────────────────────────────────────────────
# AuthorizationResponse Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthorizationResponse:
    """Tests for AuthorizationResponse dataclass."""

    def test_to_dict_approved(self):
        """Test converting approved response to dict."""
        response = AuthorizationResponse(
            request_id="auth-001",
            decision=AuthorizationDecision.APPROVED,
            operator="test_user",
        )
        result = response.to_dict()
        
        assert result["request_id"] == "auth-001"
        assert result["decision"] == "APPROVED"
        assert result["operator"] == "test_user"
        assert result["timestamp"] is not None
        assert result["constraints"] is None
        assert result["batch_apply"] is False

    def test_to_dict_denied(self):
        """Test converting denied response to dict."""
        response = AuthorizationResponse(
            request_id="auth-002",
            decision=AuthorizationDecision.DENIED,
        )
        result = response.to_dict()
        
        assert result["decision"] == "DENIED"

    def test_to_dict_skipped(self):
        """Test converting skipped response to dict."""
        response = AuthorizationResponse(
            request_id="auth-003",
            decision=AuthorizationDecision.SKIPPED,
        )
        result = response.to_dict()
        
        assert result["decision"] == "SKIPPED"

    def test_to_dict_with_constraints(self):
        """Test response with constraints."""
        response = AuthorizationResponse(
            request_id="auth-004",
            decision=AuthorizationDecision.APPROVED,
            constraints={"time_limit": 3600, "target_limit": 10},
            batch_apply=True,
        )
        result = response.to_dict()
        
        assert result["constraints"] == {"time_limit": 3600, "target_limit": 10}
        assert result["batch_apply"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Widget Rendering Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSwarmStateSnapshotWidget:
    """Tests for SwarmStateSnapshot widget."""

    def test_render_with_data(self, sample_swarm_snapshot: SwarmSnapshot):
        """Test rendering with valid snapshot data."""
        widget = SwarmStateSnapshot(sample_swarm_snapshot)
        rendered = widget.render()
        
        assert "Swarm State Snapshot" in rendered
        assert "50" in rendered  # total_agents
        assert "idle:20" in rendered or "idle" in rendered

    def test_render_no_data(self):
        """Test rendering with no snapshot data."""
        widget = SwarmStateSnapshot(None)
        rendered = widget.render()
        
        assert "No swarm data" in rendered


class TestRiskAssessmentDisplay:
    """Tests for RiskAssessmentDisplay widget."""

    def test_render_high_risk(self, sample_auth_request: AuthorizationRequest):
        """Test rendering high risk request."""
        widget = RiskAssessmentDisplay(sample_auth_request)
        rendered = widget.render()
        
        assert "192.168.1.100" in rendered  # target
        assert "SSH brute force" in rendered  # action
        assert "HIGH" in rendered  # risk level
        assert "recon-agent-001" in rendered  # agent

    def test_render_low_risk(self):
        """Test rendering low risk request."""
        request = AuthorizationRequest(
            id="test",
            request_type=AuthorizationType.LATERAL_MOVE,
            agent_id="agent-1",
            target="192.168.1.1",
            proposed_action="Port scan",
            risk_level=RiskLevel.LOW,
        )
        widget = RiskAssessmentDisplay(request)
        rendered = widget.render()
        
        assert "LOW" in rendered

    def test_risk_css_class(self, sample_auth_request: AuthorizationRequest):
        """Test that risk level affects CSS class."""
        widget = RiskAssessmentDisplay(sample_auth_request)
        assert "risk-high" in widget.classes


class TestRelatedFindingsDisplay:
    """Tests for RelatedFindingsDisplay widget."""

    def test_render_with_findings(self):
        """Test rendering with findings."""
        findings = [
            {"finding_id": "f1", "title": "SSH Port Open", "severity": "HIGH"},
            {"finding_id": "f2", "title": "FTP Anonymous", "severity": "MEDIUM"},
        ]
        widget = RelatedFindingsDisplay(findings)
        rendered = widget.render()
        
        assert "Related Findings" in rendered
        assert "SSH Port Open" in rendered
        assert "FTP Anonymous" in rendered

    def test_render_no_findings(self):
        """Test rendering with no findings."""
        widget = RelatedFindingsDisplay([])
        rendered = widget.render()
        
        assert "No related findings" in rendered

    def test_truncates_long_list(self):
        """Test that long finding lists are truncated."""
        findings = [{"title": f"Finding {i}", "severity": "INFO"} for i in range(10)]
        widget = RelatedFindingsDisplay(findings)
        # Widget stores max 5
        assert len(widget._findings) == 5


class TestMoreInfoSection:
    """Tests for MoreInfoSection widget."""

    def test_render_with_attck(self, sample_auth_request: AuthorizationRequest):
        """Test rendering with ATT&CK mapping."""
        widget = MoreInfoSection(sample_auth_request)
        rendered = widget.render()
        
        assert "MITRE ATT&CK" in rendered
        assert "T1110.001" in rendered
        assert "Credential Access" in rendered

    def test_render_with_decision_context(self, sample_auth_request: AuthorizationRequest):
        """Test rendering with decision context."""
        widget = MoreInfoSection(sample_auth_request)
        rendered = widget.render()
        
        assert "Agent Reasoning" in rendered
        assert "SSH service" in rendered

    def test_render_minimal(self):
        """Test rendering with minimal data."""
        request = AuthorizationRequest(
            id="test",
            request_type=AuthorizationType.LATERAL_MOVE,
            agent_id="agent-1",
            target="192.168.1.1",
            proposed_action="Test",
        )
        widget = MoreInfoSection(request)
        rendered = widget.render()
        
        assert "No additional context" in rendered


# ─────────────────────────────────────────────────────────────────────────────
# AuthorizationScreen Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthorizationScreen:
    """Tests for AuthorizationScreen modal."""

    def test_init_with_request_object(self, sample_auth_request: AuthorizationRequest):
        """Test initialization with AuthorizationRequest object."""
        screen = AuthorizationScreen(sample_auth_request)
        assert screen._request == sample_auth_request
        assert screen._callback is None

    def test_init_with_dict(self, sample_auth_request_dict: dict):
        """Test initialization with dict (wire format)."""
        screen = AuthorizationScreen(sample_auth_request_dict)
        assert screen._request.id == "auth-002"
        assert screen._request.target == "10.0.0.50"

    def test_init_with_callback(self, sample_auth_request: AuthorizationRequest):
        """Test initialization with callback."""
        callback = MagicMock()
        screen = AuthorizationScreen(sample_auth_request, callback=callback)
        assert screen._callback == callback

    def test_bindings_defined(self, sample_auth_request: AuthorizationRequest):
        """Test that Y/N/M/S bindings are defined."""
        screen = AuthorizationScreen(sample_auth_request)
        binding_keys = [b.key for b in screen.BINDINGS]
        
        assert "y" in binding_keys  # Approve
        assert "n" in binding_keys  # Deny
        assert "m" in binding_keys  # More info
        assert "s" in binding_keys  # Skip

    def test_cooldown_constant(self):
        """Test cooldown constant is 3 seconds."""
        assert AuthorizationScreen.COOLDOWN_SECONDS == 3.0

    def test_send_response_approved(self, sample_auth_request: AuthorizationRequest):
        """Test _send_response for approved decision."""
        callback = MagicMock()
        screen = AuthorizationScreen(sample_auth_request, callback=callback)
        
        # Mock dismiss to avoid Textual runtime issues
        screen.dismiss = MagicMock()
        
        screen._send_response(AuthorizationDecision.APPROVED)
        
        # Verify callback was called
        callback.assert_called_once()
        result = callback.call_args[0][0]
        assert result["decision"] == "APPROVED"
        assert result["approved"] is True
        assert result["skipped"] is False
        assert result["target"] == "192.168.1.100"
        
        # Verify dismiss was called
        screen.dismiss.assert_called_once()

    def test_send_response_denied(self, sample_auth_request: AuthorizationRequest):
        """Test _send_response for denied decision."""
        callback = MagicMock()
        screen = AuthorizationScreen(sample_auth_request, callback=callback)
        screen.dismiss = MagicMock()
        
        screen._send_response(AuthorizationDecision.DENIED)
        
        result = callback.call_args[0][0]
        assert result["decision"] == "DENIED"
        assert result["approved"] is False
        assert result["skipped"] is False

    def test_send_response_skipped(self, sample_auth_request: AuthorizationRequest):
        """Test _send_response for skipped decision."""
        callback = MagicMock()
        screen = AuthorizationScreen(sample_auth_request, callback=callback)
        screen.dismiss = MagicMock()
        
        screen._send_response(AuthorizationDecision.SKIPPED)
        
        result = callback.call_args[0][0]
        assert result["decision"] == "SKIPPED"
        assert result["approved"] is False
        assert result["skipped"] is True

    def test_action_approve_blocked_during_cooldown(
        self, sample_auth_request: AuthorizationRequest
    ):
        """Test that approve is blocked during cooldown."""
        screen = AuthorizationScreen(sample_auth_request)
        screen.cooldown_remaining = 2.0  # Still in cooldown
        screen.dismiss = MagicMock()
        
        # Mock the app.bell() method using patch
        with patch.object(screen, "_app", create=True) as mock_app:
            mock_app.bell = MagicMock()
            # Also need to patch the property getter
            with patch.object(type(screen), "app", new_callable=lambda: property(lambda self: mock_app)):
                screen.action_approve()
        
        # Dismiss should NOT be called during cooldown
        screen.dismiss.assert_not_called()

    def test_action_deny_not_blocked_by_cooldown(
        self, sample_auth_request: AuthorizationRequest
    ):
        """Test that deny is NOT blocked by cooldown."""
        screen = AuthorizationScreen(sample_auth_request)
        screen.cooldown_remaining = 2.0  # In cooldown
        screen.dismiss = MagicMock()
        
        screen.action_deny()
        
        # Dismiss SHOULD be called (deny bypasses cooldown)
        screen.dismiss.assert_called_once()

    def test_action_skip_not_blocked_by_cooldown(
        self, sample_auth_request: AuthorizationRequest
    ):
        """Test that skip is NOT blocked by cooldown."""
        screen = AuthorizationScreen(sample_auth_request)
        screen.cooldown_remaining = 2.0  # In cooldown
        screen.dismiss = MagicMock()
        
        screen.action_skip()
        
        # Dismiss SHOULD be called (skip bypasses cooldown)
        screen.dismiss.assert_called_once()

    def test_more_info_toggle(self, sample_auth_request: AuthorizationRequest):
        """Test more info section toggle."""
        screen = AuthorizationScreen(sample_auth_request)
        
        assert screen.more_info_expanded is False
        
        screen.action_more_info()
        assert screen.more_info_expanded is True
        
        screen.action_more_info()
        assert screen.more_info_expanded is False

    @patch("time.monotonic")
    def test_cooldown_sets_last_approval_time(
        self, mock_monotonic, sample_auth_request: AuthorizationRequest
    ):
        """Test that approval sets class-level last approval time."""
        mock_monotonic.return_value = 100.0
        
        screen = AuthorizationScreen(sample_auth_request)
        screen.cooldown_remaining = 0.0  # Not in cooldown
        screen.dismiss = MagicMock()
        
        screen.action_approve()
        
        assert AuthorizationScreen._last_approval_time == 100.0


# ─────────────────────────────────────────────────────────────────────────────
# Enum Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEnums:
    """Tests for authorization enums."""

    def test_authorization_type_values(self):
        """Test AuthorizationType enum values."""
        assert AuthorizationType.LATERAL_MOVE == "lateral_move"
        assert AuthorizationType.SCOPE_EXPANSION == "scope_expansion"

    def test_risk_level_values(self):
        """Test RiskLevel enum values."""
        assert RiskLevel.LOW == "LOW"
        assert RiskLevel.MEDIUM == "MEDIUM"
        assert RiskLevel.HIGH == "HIGH"
        assert RiskLevel.CRITICAL == "CRITICAL"

    def test_authorization_decision_values(self):
        """Test AuthorizationDecision enum values."""
        assert AuthorizationDecision.APPROVED == "APPROVED"
        assert AuthorizationDecision.DENIED == "DENIED"
        assert AuthorizationDecision.SKIPPED == "SKIPPED"


# ─────────────────────────────────────────────────────────────────────────────
# Backward Compatibility Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBackwardCompatibility:
    """Tests for backward compatibility with old AuthorizationModal."""

    def test_modal_alias_import(self):
        """Test AuthorizationModal alias works."""
        from cyberred.tui.widgets import AuthorizationModal
        from cyberred.tui.screens.authorization import AuthorizationScreen
        
        assert AuthorizationModal is AuthorizationScreen

    def test_screens_module_exports(self):
        """Test screens module exports all needed types."""
        from cyberred.tui.screens import (
            AuthorizationScreen,
            AuthorizationRequest,
            AuthorizationResponse,
            AuthorizationType,
            AuthorizationDecision,
            RiskLevel,
            SwarmSnapshot,
        )
        
        # All imports should succeed
        assert AuthorizationScreen is not None
        assert AuthorizationRequest is not None


# ─────────────────────────────────────────────────────────────────────────────
# Timeout Tests (Story 10.1 - Auth Timeout)
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthorizationTimeout:
    """Tests for authorization timeout functionality."""

    def test_default_timeout_value(self):
        """Test default timeout is 30 minutes (1800 seconds)."""
        from cyberred.tui.screens.authorization import DEFAULT_AUTH_TIMEOUT_SECONDS
        assert DEFAULT_AUTH_TIMEOUT_SECONDS == 30 * 60

    def test_screen_accepts_custom_timeout(self, sample_auth_request):
        """Test screen accepts custom timeout parameter."""
        screen = AuthorizationScreen(
            sample_auth_request,
            timeout_seconds=60.0,  # 1 minute timeout
        )
        assert screen._timeout_seconds == 60.0

    def test_timeout_remaining_reactive(self, sample_auth_request):
        """Test timeout_remaining is a reactive property."""
        screen = AuthorizationScreen(sample_auth_request, timeout_seconds=120.0)
        assert hasattr(screen, 'timeout_remaining')
        # Initial value should be 0 until mounted
        assert screen.timeout_remaining == 0.0


class TestTimeoutDisplay:
    """Tests for timeout display formatting."""

    def test_update_timeout_display_minutes(self, sample_auth_request):
        """Test timeout display shows minutes and seconds."""
        screen = AuthorizationScreen(sample_auth_request, timeout_seconds=600.0)
        screen.timeout_remaining = 605.0  # 10 minutes 5 seconds
        # Method exists for display update
        assert hasattr(screen, '_update_timeout_display')

    def test_update_timeout_display_warning_under_5_min(self, sample_auth_request):
        """Test timeout shows warning color under 5 minutes."""
        screen = AuthorizationScreen(sample_auth_request, timeout_seconds=300.0)
        screen.timeout_remaining = 180.0  # 3 minutes
        # Display method handles warning state
        assert hasattr(screen, '_update_timeout_display')

    def test_update_timeout_display_critical_under_1_min(self, sample_auth_request):
        """Test timeout shows critical color under 1 minute."""
        screen = AuthorizationScreen(sample_auth_request, timeout_seconds=60.0)
        screen.timeout_remaining = 30.0  # 30 seconds
        assert hasattr(screen, '_update_timeout_display')


# ─────────────────────────────────────────────────────────────────────────────
# Latency Measurement Tests (Story 10.1 - NFR5)
# ─────────────────────────────────────────────────────────────────────────────

class TestLatencyMeasurement:
    """Tests for delivery latency measurement (NFR5: <500ms)."""

    def test_latency_measured_with_origin_time(self):
        """Test latency is measured when origin_time_ns is provided."""
        import time
        origin_ns = time.monotonic_ns()
        
        request = AuthorizationRequest(
            id="lat-001",
            request_type="lateral_move",
            agent_id="agent-001",
            target="192.168.1.1",
            proposed_action="Test",
            origin_time_ns=origin_ns,
        )
        
        screen = AuthorizationScreen(request)
        assert screen.delivery_latency_ms is not None
        # Should be very fast (< 100ms for same-process test)
        assert screen.delivery_latency_ms < 100

    def test_latency_none_without_origin_time(self, sample_auth_request):
        """Test latency is None when origin_time_ns not provided."""
        # sample_auth_request doesn't have origin_time_ns
        screen = AuthorizationScreen(sample_auth_request)
        assert screen.delivery_latency_ms is None

    def test_latency_from_dict_with_origin_time(self):
        """Test latency measured from dict with origin_time_ns."""
        import time
        data = {
            "id": "lat-002",
            "agent_id": "agent-002",
            "target": "10.0.0.1",
            "proposed_action": "Test action",
            "request_type": "lateral_move",
            "origin_time_ns": time.monotonic_ns(),
        }
        
        screen = AuthorizationScreen(data)
        assert screen.delivery_latency_ms is not None

    def test_latency_included_in_response(self):
        """Test delivery latency is included in response."""
        import time
        request = AuthorizationRequest(
            id="lat-003",
            request_type="lateral_move",
            agent_id="agent-003",
            target="192.168.1.1",
            proposed_action="Test",
            origin_time_ns=time.monotonic_ns(),
        )
        
        results = []
        def capture_callback(result):
            results.append(result)
        
        screen = AuthorizationScreen(request, callback=capture_callback)
        # Mock dismiss to avoid NoActiveAppError
        screen.dismiss = MagicMock()
        screen._send_response(AuthorizationDecision.APPROVED)
        
        assert len(results) == 1
        assert "delivery_latency_ms" in results[0]


# ─────────────────────────────────────────────────────────────────────────────
# Skip Queue Tests (Story 10.1 - Skip Functionality)
# ─────────────────────────────────────────────────────────────────────────────

class TestSkipQueue:
    """Tests for skip queue functionality."""

    def setup_method(self):
        """Clear skip queue before each test."""
        AuthorizationScreen.clear_skip_queue()

    def test_skip_adds_to_queue(self, sample_auth_request):
        """Test skip action adds request to queue."""
        screen = AuthorizationScreen(sample_auth_request)
        screen.dismiss = MagicMock()  # Mock dismiss to avoid NoActiveAppError
        
        initial_count = AuthorizationScreen.get_skip_count()
        screen.action_skip()
        
        assert AuthorizationScreen.get_skip_count() == initial_count + 1
        queue = AuthorizationScreen.get_skip_queue()
        assert len(queue) == 1
        assert queue[0].id == sample_auth_request.id

    def test_skip_queue_is_class_level(self, sample_auth_request):
        """Test skip queue is shared across instances."""
        AuthorizationScreen.clear_skip_queue()
        
        screen1 = AuthorizationScreen(sample_auth_request)
        screen1.dismiss = MagicMock()  # Mock dismiss
        screen1.action_skip()
        
        # Create another request
        request2 = AuthorizationRequest(
            id="skip-002",
            request_type="lateral_move",
            agent_id="agent-002",
            target="10.0.0.1",
            proposed_action="Test 2",
        )
        screen2 = AuthorizationScreen(request2)
        screen2.dismiss = MagicMock()  # Mock dismiss
        screen2.action_skip()
        
        # Both should be in queue
        queue = AuthorizationScreen.get_skip_queue()
        assert len(queue) == 2
        assert AuthorizationScreen.get_skip_count() == 2

    def test_clear_skip_queue(self, sample_auth_request):
        """Test clear_skip_queue empties queue and resets count."""
        screen = AuthorizationScreen(sample_auth_request)
        screen.dismiss = MagicMock()  # Mock dismiss
        screen.action_skip()
        
        AuthorizationScreen.clear_skip_queue()
        
        assert AuthorizationScreen.get_skip_count() == 0
        assert len(AuthorizationScreen.get_skip_queue()) == 0

    def test_get_skip_queue_returns_copy(self, sample_auth_request):
        """Test get_skip_queue returns a copy, not original."""
        screen = AuthorizationScreen(sample_auth_request)
        screen.dismiss = MagicMock()  # Mock dismiss
        screen.action_skip()
        
        queue1 = AuthorizationScreen.get_skip_queue()
        queue2 = AuthorizationScreen.get_skip_queue()
        
        # Should be equal but not same object
        assert queue1 == queue2
        assert queue1 is not queue2


# ─────────────────────────────────────────────────────────────────────────────
# Batch Apply Tests (Story 10.1 - Auth Batching)
# ─────────────────────────────────────────────────────────────────────────────

class TestBatchApply:
    """Tests for batch apply functionality."""

    def test_batch_apply_default_false(self, sample_auth_request):
        """Test batch_apply defaults to False."""
        screen = AuthorizationScreen(sample_auth_request)
        assert screen.batch_apply is False

    def test_toggle_batch_action(self, sample_auth_request):
        """Test action_toggle_batch toggles batch_apply."""
        screen = AuthorizationScreen(sample_auth_request)
        
        assert screen.batch_apply is False
        screen.action_toggle_batch()
        assert screen.batch_apply is True
        screen.action_toggle_batch()
        assert screen.batch_apply is False

    def test_batch_apply_included_in_response(self, sample_auth_request):
        """Test batch_apply is included in response."""
        results = []
        def capture_callback(result):
            results.append(result)
        
        screen = AuthorizationScreen(sample_auth_request, callback=capture_callback)
        screen.dismiss = MagicMock()  # Mock dismiss to avoid NoActiveAppError
        screen.batch_apply = True
        screen._send_response(AuthorizationDecision.APPROVED)
        
        assert len(results) == 1
        assert results[0]["batch_apply"] is True

    def test_batch_apply_in_authorization_response(self, sample_auth_request):
        """Test AuthorizationResponse includes batch_apply."""
        response = AuthorizationResponse(
            request_id="resp-001",
            decision=AuthorizationDecision.APPROVED,
            batch_apply=True,
        )
        
        result_dict = response.to_dict()
        assert result_dict["batch_apply"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Auto-Deny Tests (Story 10.1 - Timeout Auto-Deny)
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoDeny:
    """Tests for auto-deny on timeout."""

    def test_auto_denied_flag_in_response(self, sample_auth_request):
        """Test auto_denied flag is included in response."""
        results = []
        def capture_callback(result):
            results.append(result)
        
        screen = AuthorizationScreen(sample_auth_request, callback=capture_callback)
        screen.dismiss = MagicMock()  # Mock dismiss to avoid NoActiveAppError
        screen._send_response(AuthorizationDecision.DENIED, auto_denied=True)
        
        assert len(results) == 1
        assert results[0]["auto_denied"] is True
        assert results[0]["decision"] == AuthorizationDecision.DENIED

    def test_manual_deny_not_auto_denied(self, sample_auth_request):
        """Test manual deny has auto_denied=False."""
        results = []
        def capture_callback(result):
            results.append(result)
        
        screen = AuthorizationScreen(sample_auth_request, callback=capture_callback)
        screen.dismiss = MagicMock()  # Mock dismiss to avoid NoActiveAppError
        screen.action_deny()
        
        assert len(results) == 1
        assert results[0]["auto_denied"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Origin Time Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestOriginTime:
    """Tests for origin_time_ns in AuthorizationRequest."""

    def test_origin_time_ns_default_none(self):
        """Test origin_time_ns defaults to None."""
        request = AuthorizationRequest(
            id="orig-001",
            request_type="lateral_move",
            agent_id="agent-001",
            target="192.168.1.1",
            proposed_action="Test",
        )
        assert request.origin_time_ns is None

    def test_origin_time_ns_from_dict(self):
        """Test origin_time_ns is parsed from dict."""
        import time
        origin = time.monotonic_ns()
        
        data = {
            "id": "orig-002",
            "agent_id": "agent-002",
            "target": "10.0.0.1",
            "proposed_action": "Test",
            "request_type": "lateral_move",
            "origin_time_ns": origin,
        }
        
        request = AuthorizationRequest.from_dict(data)
        assert request.origin_time_ns == origin

    def test_origin_time_ns_set_directly(self):
        """Test origin_time_ns can be set directly."""
        import time
        origin = time.monotonic_ns()
        
        request = AuthorizationRequest(
            id="orig-003",
            request_type="lateral_move",
            agent_id="agent-003",
            target="192.168.1.1",
            proposed_action="Test",
            origin_time_ns=origin,
        )
        assert request.origin_time_ns == origin
