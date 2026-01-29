"""Integration Tests for Alert Response Flow - Story 10.7.

Tests full alert response flow from TUI modal to audit trail:
- Continue response → agent status back to ACTIVE
- Stop response → engagement.pause() called → agents receive PAUSED
- Notes inclusion in audit entries
- Audit trail logging to Redis
- End-to-end: alert → response → audit → state update

Coverage: Integration tests for full component interaction.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static


# ─────────────────────────────────────────────────────────────────────────────
# Test Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_alert_trigger():
    """Create a sample AlertTrigger for testing."""
    from cyberred.core.alerts import AlertTrigger, AlertType, AlertSeverity
    
    return AlertTrigger(
        id=str(uuid.uuid4()),
        alert_type=AlertType.HONEYPOT,
        severity=AlertSeverity.CRITICAL,
        target="192.168.1.50",
        discovery_details="Canary token detected in credentials file",
        risk_assessment="High detection risk - honeypot indicators present",
        recommended_action="Stop immediately, assess detection risk",
        agent_id="recon-47",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client for testing."""
    client = AsyncMock()
    client.xadd = AsyncMock(return_value="1234567890-0")
    client.xrange = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_engagement_manager():
    """Create a mock EngagementManager for testing."""
    manager = MagicMock()
    manager.id = "test-engagement-001"
    manager.pause = AsyncMock()
    manager.current_state = "RUNNING"
    return manager


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests: Full Response Flow
# ─────────────────────────────────────────────────────────────────────────────

class TestAlertResponseFlowIntegration:
    """Integration tests for full alert response flow."""

    @pytest.mark.asyncio
    async def test_continue_response_logs_to_audit(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test Continue response logs correctly to audit trail."""
        from cyberred.core.alerts import AlertResponseHandler
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        response = await handler.handle_continue(
            alert=sample_alert_trigger,
            operator="test_operator",
            notes="Acknowledged, continuing engagement",
        )
        
        # Verify audit was logged with correct decision
        mock_redis_client.xadd.assert_called_once()
        call_args = mock_redis_client.xadd.call_args
        entry = call_args[0][1]
        assert entry["operator_response"] == "continue"
        assert entry["notes"] == "Acknowledged, continuing engagement"

    @pytest.mark.asyncio
    async def test_stop_response_triggers_engagement_pause(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test Stop response triggers engagement.pause() (not kill)."""
        from cyberred.core.alerts import AlertResponseHandler
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        await handler.handle_stop(
            alert=sample_alert_trigger,
            operator="test_operator",
            notes="Stopping due to honeypot detection",
        )
        
        # Verify pause was called
        mock_engagement_manager.pause.assert_called_once()
        
        # Verify audit was logged with STOP decision
        call_args = mock_redis_client.xadd.call_args
        entry = call_args[0][1]
        assert entry["operator_response"] == "stop"

    @pytest.mark.asyncio
    async def test_audit_entry_retrievable_after_response(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test audit entry can be retrieved from Redis after response."""
        from cyberred.core.alerts import AlertResponseHandler
        from cyberred.core.audit import AlertAuditLogger
        
        # Set up mock to return the logged entry
        mock_redis_client.xrange.return_value = [
            ("1234567890-0", {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "situational_alert_response",
                "alert_id": sample_alert_trigger.id,
                "alert_type": "honeypot",
                "operator_response": "stop",
                "notes": "Test notes",
                "agent_id": "recon-47",
                "target": "192.168.1.50",
            }),
        ]
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        # Log a response
        await handler.handle_stop(
            alert=sample_alert_trigger,
            operator="test_operator",
            notes="Test notes",
        )
        
        # Retrieve audit entries
        entries = await audit_logger.get_responses_for_engagement(
            mock_engagement_manager.id
        )
        
        assert len(entries) == 1
        assert entries[0][1]["alert_id"] == sample_alert_trigger.id


class TestAlertResponseTUIIntegration:
    """Integration tests for TUI alert response handling."""

    @pytest.mark.asyncio
    async def test_tui_continue_response_flow(self, sample_alert_trigger) -> None:
        """Test TUI Continue action response flow."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        from cyberred.core.alerts import AlertResponseDecision
        
        received_response = None
        
        def callback(response):
            nonlocal received_response
            received_response = response
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(
                alert=sample_alert_trigger,
                callback=callback,
                operator_name="test_operator",
            )
            app.push_screen(screen)
            await pilot.pause()
            
            # Trigger continue action directly (per existing test pattern)
            screen.action_continue_engagement()
            await pilot.pause()
        
        # Verify response received via callback
        assert received_response is not None
        assert received_response.decision == AlertResponseDecision.CONTINUE

    @pytest.mark.asyncio
    async def test_tui_stop_response_flow(self, sample_alert_trigger) -> None:
        """Test TUI Stop action response flow."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        from cyberred.core.alerts import AlertResponseDecision
        
        received_response = None
        
        def callback(response):
            nonlocal received_response
            received_response = response
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(
                alert=sample_alert_trigger,
                callback=callback,
                operator_name="test_operator",
            )
            app.push_screen(screen)
            await pilot.pause()
            
            # Trigger stop action directly
            screen.action_stop_engagement()
            await pilot.pause()
        
        # Verify response received via callback
        assert received_response is not None
        assert received_response.decision == AlertResponseDecision.STOP

    @pytest.mark.asyncio
    async def test_tui_notes_toggle_and_include(self, sample_alert_trigger) -> None:
        """Test TUI Notes toggle and notes inclusion in response."""
        from cyberred.tui.widgets.situational_alert import SituationalAlertScreen
        from textual.widgets import Input
        
        received_response = None
        
        def callback(response):
            nonlocal received_response
            received_response = response
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield Static("Test")
        
        app = TestApp()
        async with app.run_test() as pilot:
            screen = SituationalAlertScreen(
                alert=sample_alert_trigger,
                callback=callback,
                operator_name="test_operator",
            )
            app.push_screen(screen)
            await pilot.pause()
            
            # Toggle notes via action
            screen.action_add_notes()
            await pilot.pause()
            
            # Notes input should be visible via reactive property
            assert screen.notes_visible is True
            
            # Set notes directly on the input
            notes_input = screen.query_one("#notes-input", Input)
            notes_input.value = "Test operator notes"
            await pilot.pause()
            
            # Trigger continue action with notes
            screen.action_continue_engagement()
            await pilot.pause()
        
        # Verify response includes notes
        assert received_response is not None
        assert received_response.notes == "Test operator notes"


class TestAlertResponseEndToEnd:
    """End-to-end tests for alert → response → audit → state flow."""

    @pytest.mark.asyncio
    async def test_end_to_end_continue_flow(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test end-to-end: alert → Continue response → audit."""
        from cyberred.core.alerts import AlertResponseHandler, AlertResponseDecision
        from cyberred.core.audit import AlertAuditLogger
        
        # Set up audit logger and handler
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        # Process Continue response
        response = await handler.handle_response(
            alert=sample_alert_trigger,
            decision=AlertResponseDecision.CONTINUE,
            operator="test_operator",
            notes="Proceeding after review",
        )
        
        # Verify response
        assert response.decision == AlertResponseDecision.CONTINUE
        
        # Verify NO pause was called
        mock_engagement_manager.pause.assert_not_called()
        
        # Verify audit logged
        mock_redis_client.xadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_end_to_end_stop_flow(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test end-to-end: alert → Stop response → pause → audit."""
        from cyberred.core.alerts import AlertResponseHandler, AlertResponseDecision
        from cyberred.core.audit import AlertAuditLogger
        
        # Set up audit logger and handler
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        # Process Stop response
        response = await handler.handle_response(
            alert=sample_alert_trigger,
            decision=AlertResponseDecision.STOP,
            operator="test_operator",
            notes="Honeypot detected - stopping",
        )
        
        # Verify response
        assert response.decision == AlertResponseDecision.STOP
        
        # Verify pause WAS called
        mock_engagement_manager.pause.assert_called_once()
        
        # Verify audit logged with correct data
        call_args = mock_redis_client.xadd.call_args
        entry = call_args[0][1]
        assert entry["operator_response"] == "stop"
        assert entry["notes"] == "Honeypot detected - stopping"
        assert entry["agent_id"] == sample_alert_trigger.agent_id
        assert entry["target"] == sample_alert_trigger.target

    @pytest.mark.asyncio
    async def test_audit_query_by_alert_type(
        self,
        mock_redis_client,
        mock_engagement_manager,
    ) -> None:
        """Test audit entries can be queried by alert type."""
        from cyberred.core.alerts import AlertType
        from cyberred.core.audit import AlertAuditLogger
        
        # Set up mock to return mixed entries
        mock_redis_client.xrange.return_value = [
            ("1-0", {"alert_type": "honeypot", "operator_response": "stop"}),
            ("2-0", {"alert_type": "new_subnet", "operator_response": "continue"}),
            ("3-0", {"alert_type": "honeypot", "operator_response": "continue"}),
        ]
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        
        # Query by alert type
        entries = await audit_logger.get_responses_by_alert_type(
            engagement_id=mock_engagement_manager.id,
            alert_type=AlertType.HONEYPOT,
        )
        
        # Should only return honeypot entries
        assert len(entries) == 2
        assert all(e[1]["alert_type"] == "honeypot" for e in entries)
