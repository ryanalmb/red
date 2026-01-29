"""Integration Tests for Situational Alert Flow - Story 10.6.

Tests full alert flow from agent discovery to TUI modal to response:
- Agent discovery → alert detection → TUI modal display
- Latency measurement (<500ms NFR5 compliance)
- Anomaly bubbling integration (AttentionPriority.SITUATIONAL_ALERT)
- Audit trail logging with required fields
- Modal dismiss and result propagation

Coverage: Integration tests for full component interaction.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static


class TestAlertFlowIntegration:
    """Integration tests for full alert flow."""

    @pytest.fixture
    def sample_finding(self):
        """Create a sample Finding that should trigger an alert."""
        from cyberred.core.models import Finding
        
        return Finding(
            id=str(uuid.uuid4()),
            type="host_discovered",
            severity="info",
            target="192.168.2.50",  # Out of scope
            evidence="Host discovered during network scan",
            agent_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool="nmap",
            topic="findings:test:host",
            signature="test-sig",
        )

    @pytest.fixture
    def in_scope_config(self):
        """Create scope configuration."""
        from cyberred.core.models import Scope
        
        return Scope(networks=["192.168.1.0/24"])

    @pytest.mark.asyncio
    async def test_finding_triggers_alert_detection(self, sample_finding, in_scope_config) -> None:
        """Test finding outside scope triggers alert detection."""
        from cyberred.core.alerts import AlertDetector, AlertType
        
        detector = AlertDetector(scope=in_scope_config)
        alerts = detector.analyze_finding(sample_finding)
        
        assert len(alerts) >= 1
        assert any(a.alert_type == AlertType.NEW_SUBNET for a in alerts)

    @pytest.mark.asyncio
    async def test_alert_includes_finding_context(self, sample_finding, in_scope_config) -> None:
        """Test generated alert includes context from finding."""
        from cyberred.core.alerts import AlertDetector
        
        detector = AlertDetector(scope=in_scope_config)
        alerts = detector.analyze_finding(sample_finding)
        
        alert = alerts[0]
        assert alert.target == sample_finding.target
        assert alert.agent_id == sample_finding.agent_id

    @pytest.mark.asyncio
    async def test_alert_modal_displays_from_trigger(self, sample_finding, in_scope_config) -> None:
        """Test alert modal displays correctly from AlertTrigger."""
        from cyberred.core.alerts import AlertDetector
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        detector = AlertDetector(scope=in_scope_config)
        alerts = detector.analyze_finding(sample_finding)
        alert = alerts[0]
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=alert)
            app.push_screen(screen)
            await pilot.pause()
            
            # Modal should be displayed
            assert app.screen == screen


class TestAlertLatencyCompliance:
    """Tests for NFR5 latency compliance (<500ms)."""

    @pytest.fixture
    def sample_alert_trigger(self):
        """Create an alert trigger with origin timestamp."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        return AlertTrigger(
            id=str(uuid.uuid4()),
            alert_type=AlertType.NEW_SUBNET,
            severity=AlertSeverity.HIGH,
            target="192.168.2.0/24",
            discovery_details="New subnet found",
            risk_assessment="Not in scope",
            recommended_action="Review scope",
            agent_id=str(uuid.uuid4()),
            origin_time_ns=time.monotonic_ns(),
        )

    @pytest.mark.asyncio
    async def test_alert_delivery_under_500ms(self, sample_alert_trigger) -> None:
        """Test alert delivery completes in <500ms (NFR5)."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            start_ns = time.monotonic_ns()
            
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            delivery_ns = time.monotonic_ns()
            latency_ms = (delivery_ns - start_ns) / 1_000_000
            
            # Should be well under 500ms
            assert latency_ms < 500, f"Alert delivery took {latency_ms}ms, exceeds 500ms NFR5 limit"

    @pytest.mark.asyncio
    async def test_latency_tracking_from_origin(self, sample_alert_trigger) -> None:
        """Test latency can be measured from origin_time_ns."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            # Calculate latency from origin
            if sample_alert_trigger.origin_time_ns:
                delivery_ns = time.monotonic_ns()
                latency_ms = (delivery_ns - sample_alert_trigger.origin_time_ns) / 1_000_000
                
                # Should be under 500ms
                assert latency_ms < 500


class TestAnomalyBubblingIntegration:
    """Tests for anomaly bubbling integration with Story 9-4."""

    def test_situational_alert_priority_exists(self) -> None:
        """Test SITUATIONAL_ALERT priority exists in AttentionPriority."""
        from cyberred.tui.widgets.agent_list import AttentionPriority
        
        # SITUATIONAL_ALERT should be added (priority 2 per story spec)
        assert hasattr(AttentionPriority, "SITUATIONAL_ALERT")
        assert AttentionPriority.SITUATIONAL_ALERT == 2

    def test_situational_alert_priority_order(self) -> None:
        """Test SITUATIONAL_ALERT has correct priority order."""
        from cyberred.tui.widgets.agent_list import AttentionPriority
        
        # Order: ERROR(0) < AUTH_PENDING(1) < SITUATIONAL_ALERT(2) < CRITICAL_FINDING(3)
        assert AttentionPriority.AUTH_PENDING < AttentionPriority.SITUATIONAL_ALERT
        assert AttentionPriority.SITUATIONAL_ALERT < AttentionPriority.CRITICAL_FINDING

    def test_agent_status_has_situational_alert(self) -> None:
        """Test AgentStatus has SITUATIONAL_ALERT value."""
        from cyberred.tui.widgets.agent_list import AgentStatus
        
        assert hasattr(AgentStatus, "SITUATIONAL_ALERT")

    def test_situational_alert_maps_to_priority(self) -> None:
        """Test SITUATIONAL_ALERT status maps to correct priority."""
        from cyberred.tui.widgets.agent_list import (
            AgentStatus,
            AttentionPriority,
            get_attention_priority,
        )
        
        priority = get_attention_priority(AgentStatus.SITUATIONAL_ALERT)
        assert priority == AttentionPriority.SITUATIONAL_ALERT


class TestAuditTrailIntegration:
    """Tests for audit trail logging integration."""

    @pytest.fixture
    def sample_alert_trigger(self):
        """Create a sample AlertTrigger."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        return AlertTrigger(
            id=str(uuid.uuid4()),
            alert_type=AlertType.HONEYPOT,
            severity=AlertSeverity.CRITICAL,
            target="192.168.1.50",
            discovery_details="Canary detected",
            risk_assessment="Detection risk",
            recommended_action="Stop now",
            agent_id=str(uuid.uuid4()),
        )

    @pytest.mark.asyncio
    async def test_alert_response_creates_audit_entry(self, sample_alert_trigger) -> None:
        """Test alert response creates proper audit entry."""
        from cyberred.core.alerts import AlertResponse, AlertResponseDecision
        
        response = AlertResponse(
            alert_id=sample_alert_trigger.id,
            decision=AlertResponseDecision.STOP,
            operator="test_operator",
            notes="Stopping due to honeypot",
        )
        
        audit_dict = response.to_dict()
        
        # Per FR23 audit format requirements
        assert "alert_id" in audit_dict
        assert "decision" in audit_dict
        assert "operator" in audit_dict
        assert "timestamp" in audit_dict
        assert "notes" in audit_dict

    @pytest.mark.asyncio
    async def test_audit_entry_includes_alert_type(self, sample_alert_trigger) -> None:
        """Test audit entry includes alert type for context."""
        from cyberred.core.alerts import (
            AlertResponse,
            AlertResponseDecision,
            create_audit_entry,
        )
        
        response = AlertResponse(
            alert_id=sample_alert_trigger.id,
            decision=AlertResponseDecision.STOP,
            operator="test_operator",
        )
        
        audit_entry = create_audit_entry(sample_alert_trigger, response)
        
        assert audit_entry["alert_type"] == "honeypot"
        assert audit_entry["target"] == sample_alert_trigger.target
        assert audit_entry["agent_id"] == sample_alert_trigger.agent_id

    @pytest.mark.asyncio
    async def test_audit_entry_format_matches_spec(self, sample_alert_trigger) -> None:
        """Test audit entry format matches FR23 specification."""
        from cyberred.core.alerts import (
            AlertResponse,
            AlertResponseDecision,
            create_audit_entry,
        )
        
        response = AlertResponse(
            alert_id=sample_alert_trigger.id,
            decision=AlertResponseDecision.CONTINUE,
            operator="test_operator",
            notes="Acknowledged, proceeding",
        )
        
        audit_entry = create_audit_entry(sample_alert_trigger, response)
        
        # Required fields per spec:
        # timestamp, event_type, alert_id, alert_type, operator_response, notes, agent_id, target
        assert "timestamp" in audit_entry
        assert audit_entry["event_type"] == "situational_alert_response"
        assert "alert_id" in audit_entry
        assert "alert_type" in audit_entry
        assert "operator_response" in audit_entry or "decision" in audit_entry
        assert "agent_id" in audit_entry
        assert "target" in audit_entry


class TestModalDismissAndResultPropagation:
    """Tests for modal dismiss and result propagation."""

    @pytest.fixture
    def sample_alert_trigger(self):
        """Create a sample AlertTrigger."""
        from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
        
        return AlertTrigger(
            id=str(uuid.uuid4()),
            alert_type=AlertType.UNEXPECTED_SERVICE,
            severity=AlertSeverity.MEDIUM,
            target="192.168.1.100:8080",
            discovery_details="Unexpected service",
            risk_assessment="Service not expected",
            recommended_action="Investigate",
            agent_id=str(uuid.uuid4()),
        )

    @pytest.mark.asyncio
    async def test_continue_response_propagates(self, sample_alert_trigger) -> None:
        """Test continue response propagates correctly via callback."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        from cyberred.core.alerts import AlertResponseDecision
        
        result = []
        
        def callback(response):
            result.append(response)
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger, callback=callback)
            app.push_screen(screen)
            await pilot.pause()
            
            screen.action_continue_engagement()
            await pilot.pause()
            
            assert len(result) == 1
            assert result[0].decision == AlertResponseDecision.CONTINUE
            assert result[0].alert_id == sample_alert_trigger.id

    @pytest.mark.asyncio
    async def test_stop_response_propagates(self, sample_alert_trigger) -> None:
        """Test stop response propagates correctly via callback."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        from cyberred.core.alerts import AlertResponseDecision
        
        result = []
        
        def callback(response):
            result.append(response)
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger, callback=callback)
            app.push_screen(screen)
            await pilot.pause()
            
            screen.action_stop_engagement()
            await pilot.pause()
            
            assert len(result) == 1
            assert result[0].decision == AlertResponseDecision.STOP

    @pytest.mark.asyncio
    async def test_modal_pops_after_response(self, sample_alert_trigger) -> None:
        """Test modal screen pops after operator response."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Main Screen")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(alert=sample_alert_trigger)
            app.push_screen(screen)
            await pilot.pause()
            
            # Verify modal is on top
            assert isinstance(app.screen, SituationalAlertScreen)
            
            screen.action_continue_engagement()
            await pilot.pause()
            
            # Modal should be dismissed
            assert not isinstance(app.screen, SituationalAlertScreen)
