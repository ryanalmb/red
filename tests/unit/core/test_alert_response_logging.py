"""Unit Tests for Alert Response & Logging - Story 10.7.

Tests for AlertAuditLogger and AlertResponseHandler classes following TDD methodology.

Test Coverage Requirements:
- AlertAuditLogger initialization with Redis client
- AlertAuditLogger.log_response() writes to Redis Streams
- Audit entry format matches FR23 specification
- AlertAuditLogger.get_responses_for_engagement() retrieves entries
- AlertAuditLogger.get_responses_by_alert_type() filters correctly
- Stream name follows pattern: cyberred:audit:alerts:{engagement_id}
- AlertResponseHandler initialization
- AlertResponseHandler.handle_continue() returns success and logs
- AlertResponseHandler.handle_stop() triggers engagement.pause() and logs
- AlertResponseHandler.handle_response() unified method
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
def sample_alert_response():
    """Create a sample AlertResponse for testing."""
    from cyberred.core.alerts import AlertResponse, AlertResponseDecision
    
    return AlertResponse(
        alert_id=str(uuid.uuid4()),
        decision=AlertResponseDecision.STOP,
        operator="test_operator",
        notes="Detected canary token, aborting to avoid detection",
    )


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client for testing."""
    client = AsyncMock()
    client.xadd = AsyncMock(return_value="1234567890-0")
    client.xrange = AsyncMock(return_value=[])
    client.xread = AsyncMock(return_value=[])
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
# AlertAuditLogger Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAlertAuditLoggerInitialization:
    """Tests for AlertAuditLogger initialization."""

    def test_alert_audit_logger_exists(self) -> None:
        """Test AlertAuditLogger class can be imported."""
        from cyberred.core.audit import AlertAuditLogger
        
        assert AlertAuditLogger is not None

    def test_alert_audit_logger_initialization(self, mock_redis_client) -> None:
        """Test AlertAuditLogger can be initialized with Redis client."""
        from cyberred.core.audit import AlertAuditLogger
        
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        
        assert logger is not None
        assert logger._redis_client is mock_redis_client

    def test_alert_audit_logger_custom_stream_name(self, mock_redis_client) -> None:
        """Test AlertAuditLogger accepts custom stream name prefix."""
        from cyberred.core.audit import AlertAuditLogger
        
        custom_stream = "custom:audit:alerts"
        logger = AlertAuditLogger(
            redis_client=mock_redis_client,
            stream_name=custom_stream,
        )
        
        assert logger._stream_name == custom_stream


class TestAlertAuditLoggerLogResponse:
    """Tests for AlertAuditLogger.log_response() method."""

    @pytest.mark.asyncio
    async def test_log_response_writes_to_redis_stream(
        self,
        mock_redis_client,
        sample_alert_trigger,
        sample_alert_response,
    ) -> None:
        """Test log_response writes audit entry to Redis Stream."""
        from cyberred.core.audit import AlertAuditLogger
        
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        engagement_id = "test-engagement-001"
        
        result = await logger.log_response(
            alert=sample_alert_trigger,
            response=sample_alert_response,
            engagement_id=engagement_id,
        )
        
        # Verify Redis xadd was called
        mock_redis_client.xadd.assert_called_once()
        
        # Verify stream name includes engagement_id
        call_args = mock_redis_client.xadd.call_args
        stream_name = call_args[0][0]
        assert engagement_id in stream_name
        
        # Verify result is stream entry ID
        assert result == "1234567890-0"

    @pytest.mark.asyncio
    async def test_log_response_audit_entry_format_fr23(
        self,
        mock_redis_client,
        sample_alert_trigger,
        sample_alert_response,
    ) -> None:
        """Test audit entry format matches FR23 specification."""
        from cyberred.core.audit import AlertAuditLogger
        
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        
        await logger.log_response(
            alert=sample_alert_trigger,
            response=sample_alert_response,
            engagement_id="test-engagement",
        )
        
        # Get the entry that was written
        call_args = mock_redis_client.xadd.call_args
        entry = call_args[0][1]
        
        # Verify FR23 required fields
        assert "timestamp" in entry
        assert "event_type" in entry
        assert entry["event_type"] == "situational_alert_response"
        assert "alert_id" in entry
        assert "alert_type" in entry
        assert "operator_response" in entry
        assert "notes" in entry
        assert "agent_id" in entry
        assert "target" in entry

    @pytest.mark.asyncio
    async def test_log_response_stream_name_pattern(
        self,
        mock_redis_client,
        sample_alert_trigger,
        sample_alert_response,
    ) -> None:
        """Test stream name follows pattern: cyberred:audit:alerts:{engagement_id}."""
        from cyberred.core.audit import AlertAuditLogger
        
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        engagement_id = "ministry-2025"
        
        await logger.log_response(
            alert=sample_alert_trigger,
            response=sample_alert_response,
            engagement_id=engagement_id,
        )
        
        call_args = mock_redis_client.xadd.call_args
        stream_name = call_args[0][0]
        
        assert stream_name == f"cyberred:audit:alerts:{engagement_id}"

    @pytest.mark.asyncio
    async def test_log_response_handles_redis_error(
        self,
        mock_redis_client,
        sample_alert_trigger,
        sample_alert_response,
    ) -> None:
        """Test log_response handles Redis errors gracefully."""
        from cyberred.core.audit import AlertAuditLogger
        
        mock_redis_client.xadd.side_effect = Exception("Redis connection error")
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        
        # Should not raise, returns None on error
        result = await logger.log_response(
            alert=sample_alert_trigger,
            response=sample_alert_response,
            engagement_id="test-engagement",
        )
        
        assert result is None


class TestAlertAuditLoggerGetResponses:
    """Tests for AlertAuditLogger retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_responses_for_engagement(self, mock_redis_client) -> None:
        """Test get_responses_for_engagement retrieves entries ordered by timestamp."""
        from cyberred.core.audit import AlertAuditLogger
        
        # Mock xrange to return sample entries
        mock_redis_client.xrange.return_value = [
            ("1234567890-0", {
                "timestamp": "2026-01-15T14:30:00Z",
                "event_type": "situational_alert_response",
                "alert_id": "alert-1",
                "alert_type": "honeypot",
                "operator_response": "stop",
            }),
            ("1234567891-0", {
                "timestamp": "2026-01-15T14:31:00Z",
                "event_type": "situational_alert_response",
                "alert_id": "alert-2",
                "alert_type": "new_subnet",
                "operator_response": "continue",
            }),
        ]
        
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        engagement_id = "test-engagement"
        
        entries = await logger.get_responses_for_engagement(engagement_id)
        
        # Verify xrange was called with correct stream name
        mock_redis_client.xrange.assert_called_once()
        call_args = mock_redis_client.xrange.call_args
        stream_name = call_args[0][0]
        assert stream_name == f"cyberred:audit:alerts:{engagement_id}"
        
        # Verify entries are returned
        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_get_responses_for_engagement_with_limit(self, mock_redis_client) -> None:
        """Test get_responses_for_engagement respects limit parameter."""
        from cyberred.core.audit import AlertAuditLogger
        
        mock_redis_client.xrange.return_value = []
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        
        await logger.get_responses_for_engagement("test-engagement", limit=50)
        
        call_args = mock_redis_client.xrange.call_args
        # Verify count/limit was passed
        assert "count" in call_args.kwargs or len(call_args[0]) > 2

    @pytest.mark.asyncio
    async def test_get_responses_by_alert_type(self, mock_redis_client) -> None:
        """Test get_responses_by_alert_type filters by alert type."""
        from cyberred.core.alerts import AlertType
        from cyberred.core.audit import AlertAuditLogger
        
        # Mock xrange to return mixed entries
        mock_redis_client.xrange.return_value = [
            ("1234567890-0", {
                "alert_type": "honeypot",
                "operator_response": "stop",
            }),
            ("1234567891-0", {
                "alert_type": "new_subnet",
                "operator_response": "continue",
            }),
            ("1234567892-0", {
                "alert_type": "honeypot",
                "operator_response": "stop",
            }),
        ]
        
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        
        entries = await logger.get_responses_by_alert_type(
            engagement_id="test-engagement",
            alert_type=AlertType.HONEYPOT,
        )
        
        # Should filter to only honeypot entries
        assert len(entries) == 2
        assert all(e[1]["alert_type"] == "honeypot" for e in entries)


# ─────────────────────────────────────────────────────────────────────────────
# AlertResponseHandler Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAlertResponseHandlerInitialization:
    """Tests for AlertResponseHandler initialization."""

    def test_alert_response_handler_exists(self) -> None:
        """Test AlertResponseHandler class can be imported."""
        from cyberred.core.alerts import AlertResponseHandler
        
        assert AlertResponseHandler is not None

    def test_alert_response_handler_initialization(
        self,
        mock_redis_client,
        mock_engagement_manager,
    ) -> None:
        """Test AlertResponseHandler can be initialized."""
        from cyberred.core.alerts import AlertResponseHandler
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        assert handler is not None
        assert handler._audit is audit_logger
        assert handler._engagement is mock_engagement_manager


class TestAlertResponseHandlerContinue:
    """Tests for AlertResponseHandler.handle_continue() method."""

    @pytest.mark.asyncio
    async def test_handle_continue_returns_alert_response(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test handle_continue returns AlertResponse with CONTINUE decision."""
        from cyberred.core.alerts import AlertResponseHandler, AlertResponseDecision
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        response = await handler.handle_continue(
            alert=sample_alert_trigger,
            operator="test_operator",
        )
        
        assert response is not None
        assert response.alert_id == sample_alert_trigger.id
        assert response.decision == AlertResponseDecision.CONTINUE
        assert response.operator == "test_operator"

    @pytest.mark.asyncio
    async def test_handle_continue_logs_to_audit(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test handle_continue logs response to audit trail."""
        from cyberred.core.alerts import AlertResponseHandler
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        await handler.handle_continue(
            alert=sample_alert_trigger,
            operator="test_operator",
        )
        
        # Verify audit was logged
        mock_redis_client.xadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_continue_with_notes(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test handle_continue includes operator notes in response."""
        from cyberred.core.alerts import AlertResponseHandler
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        notes = "Acknowledged but continuing with caution"
        response = await handler.handle_continue(
            alert=sample_alert_trigger,
            operator="test_operator",
            notes=notes,
        )
        
        assert response.notes == notes


class TestAlertResponseHandlerStop:
    """Tests for AlertResponseHandler.handle_stop() method."""

    @pytest.mark.asyncio
    async def test_handle_stop_returns_alert_response(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test handle_stop returns AlertResponse with STOP decision."""
        from cyberred.core.alerts import AlertResponseHandler, AlertResponseDecision
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        response = await handler.handle_stop(
            alert=sample_alert_trigger,
            operator="test_operator",
        )
        
        assert response is not None
        assert response.alert_id == sample_alert_trigger.id
        assert response.decision == AlertResponseDecision.STOP
        assert response.operator == "test_operator"

    @pytest.mark.asyncio
    async def test_handle_stop_triggers_engagement_pause(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test handle_stop calls engagement.pause() (NOT kill)."""
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
        )
        
        # Verify pause was called, NOT kill
        mock_engagement_manager.pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_stop_logs_to_audit(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test handle_stop logs response to audit trail."""
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
        )
        
        # Verify audit was logged
        mock_redis_client.xadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_stop_with_notes(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test handle_stop includes operator notes in response."""
        from cyberred.core.alerts import AlertResponseHandler
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        notes = "Stopping due to honeypot detection risk"
        response = await handler.handle_stop(
            alert=sample_alert_trigger,
            operator="test_operator",
            notes=notes,
        )
        
        assert response.notes == notes


class TestAlertResponseHandlerUnified:
    """Tests for AlertResponseHandler.handle_response() unified method."""

    @pytest.mark.asyncio
    async def test_handle_response_continue(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test handle_response with CONTINUE decision."""
        from cyberred.core.alerts import AlertResponseHandler, AlertResponseDecision
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        response = await handler.handle_response(
            alert=sample_alert_trigger,
            decision=AlertResponseDecision.CONTINUE,
            operator="test_operator",
        )
        
        assert response.decision == AlertResponseDecision.CONTINUE
        # Should NOT call pause
        mock_engagement_manager.pause.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_response_stop(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test handle_response with STOP decision calls pause."""
        from cyberred.core.alerts import AlertResponseHandler, AlertResponseDecision
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        response = await handler.handle_response(
            alert=sample_alert_trigger,
            decision=AlertResponseDecision.STOP,
            operator="test_operator",
        )
        
        assert response.decision == AlertResponseDecision.STOP
        mock_engagement_manager.pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_response_notes(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test handle_response with NOTES decision (continue with notes)."""
        from cyberred.core.alerts import AlertResponseHandler, AlertResponseDecision
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        notes = "Proceeding with additional monitoring"
        response = await handler.handle_response(
            alert=sample_alert_trigger,
            decision=AlertResponseDecision.NOTES,
            operator="test_operator",
            notes=notes,
        )
        
        assert response.decision == AlertResponseDecision.NOTES
        assert response.notes == notes
        # Should NOT call pause for NOTES (it's continue with notes)
        mock_engagement_manager.pause.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# AlertAuditLogger Additional Coverage Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAlertAuditLoggerEdgeCases:
    """Tests for AlertAuditLogger edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_get_responses_for_engagement_handles_redis_error(
        self,
        mock_redis_client,
    ) -> None:
        """Test get_responses_for_engagement handles Redis errors gracefully."""
        from cyberred.core.audit import AlertAuditLogger
        
        mock_redis_client.xrange.side_effect = Exception("Redis connection error")
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        
        # Should not raise, returns empty list
        result = await logger.get_responses_for_engagement("test-engagement")
        
        assert result == []

    @pytest.mark.asyncio
    async def test_get_responses_by_alert_type_with_string_type(
        self,
        mock_redis_client,
    ) -> None:
        """Test get_responses_by_alert_type works with string alert type."""
        from cyberred.core.audit import AlertAuditLogger
        
        mock_redis_client.xrange.return_value = [
            ("1-0", {"alert_type": "honeypot", "operator_response": "stop"}),
        ]
        
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        
        # Pass string instead of enum
        entries = await logger.get_responses_by_alert_type(
            engagement_id="test-engagement",
            alert_type="honeypot",  # String, not enum
        )
        
        assert len(entries) == 1


class TestAlertAuditLoggerSingleton:
    """Tests for AlertAuditLogger singleton pattern."""

    def test_get_alert_audit_logger_returns_none_initially(self) -> None:
        """Test get_alert_audit_logger returns None when not initialized."""
        from cyberred.core.audit import get_alert_audit_logger, set_alert_audit_logger
        
        # Reset global state
        set_alert_audit_logger(None)  # type: ignore
        
        result = get_alert_audit_logger()
        assert result is None

    def test_set_alert_audit_logger_sets_instance(self, mock_redis_client) -> None:
        """Test set_alert_audit_logger sets the global instance."""
        from cyberred.core.audit import (
            AlertAuditLogger,
            get_alert_audit_logger,
            set_alert_audit_logger,
        )
        
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        set_alert_audit_logger(logger)
        
        result = get_alert_audit_logger()
        assert result is logger
        
        # Clean up
        set_alert_audit_logger(None)  # type: ignore

    def test_init_alert_audit_logger_creates_and_sets(self, mock_redis_client) -> None:
        """Test init_alert_audit_logger creates and sets global instance."""
        from cyberred.core.audit import (
            get_alert_audit_logger,
            init_alert_audit_logger,
            set_alert_audit_logger,
        )
        
        result = init_alert_audit_logger(mock_redis_client)
        
        assert result is not None
        assert get_alert_audit_logger() is result
        
        # Clean up
        set_alert_audit_logger(None)  # type: ignore


class TestAlertResponseHandlerEdgeCases:
    """Tests for AlertResponseHandler edge cases."""

    @pytest.mark.asyncio
    async def test_handle_notes_logs_to_audit(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test _handle_notes logs response to audit trail."""
        from cyberred.core.alerts import AlertResponseHandler, AlertResponseDecision
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        response = await handler._handle_notes(
            alert=sample_alert_trigger,
            operator="test_operator",
            notes="Test notes",
        )
        
        assert response.decision == AlertResponseDecision.NOTES
        assert response.notes == "Test notes"
        mock_redis_client.xadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_notes_without_notes_provided(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test _handle_notes with None notes."""
        from cyberred.core.alerts import AlertResponseHandler, AlertResponseDecision
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        response = await handler._handle_notes(
            alert=sample_alert_trigger,
            operator="test_operator",
            notes=None,
        )
        
        assert response.decision == AlertResponseDecision.NOTES
        assert response.notes is None


class TestAlertAuditLoggerLogResponseEdgeCases:
    """Additional edge case tests for AlertAuditLogger.log_response."""

    @pytest.mark.asyncio
    async def test_log_response_with_alert_missing_id_attribute(
        self,
        mock_redis_client,
        sample_alert_response,
    ) -> None:
        """Test log_response handles alert without id attribute gracefully."""
        from cyberred.core.audit import AlertAuditLogger
        
        # Create a mock alert without 'id' attribute
        mock_alert = MagicMock(spec=[])  # Empty spec means no attributes
        del mock_alert.id  # Ensure 'id' doesn't exist
        
        mock_redis_client.xadd.side_effect = Exception("Test error")
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        
        # Should not raise, should handle gracefully
        result = await logger.log_response(
            alert=mock_alert,
            response=sample_alert_response,
            engagement_id="test-engagement",
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_log_response_logs_decision_value_correctly(
        self,
        mock_redis_client,
        sample_alert_trigger,
    ) -> None:
        """Test log_response logs correct decision value from enum."""
        from cyberred.core.alerts import AlertResponse, AlertResponseDecision
        from cyberred.core.audit import AlertAuditLogger
        
        # Create a proper AlertResponse with decision enum
        response = AlertResponse(
            alert_id=sample_alert_trigger.id,
            decision=AlertResponseDecision.STOP,
            operator="test_operator",
            notes="Test notes",
        )
        
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        
        result = await logger.log_response(
            alert=sample_alert_trigger,
            response=response,
            engagement_id="test-engagement",
        )
        
        assert result == "1234567890-0"
        
        # Verify the logged decision value
        call_args = mock_redis_client.xadd.call_args
        entry = call_args[0][1]
        assert entry["operator_response"] == "stop"
        assert entry["decision"] == "stop"


class TestAlertAuditLoggerSingletonEdgeCases:
    """Edge case tests for singleton pattern."""

    def test_set_alert_audit_logger_accepts_none(self) -> None:
        """Test set_alert_audit_logger accepts None to reset state."""
        from cyberred.core.audit import (
            get_alert_audit_logger,
            set_alert_audit_logger,
        )
        
        # Set to None explicitly (now properly typed)
        set_alert_audit_logger(None)
        
        result = get_alert_audit_logger()
        assert result is None


class TestAlertAuditLoggerGetResponsesEdgeCases:
    """Edge case tests for get_responses methods."""

    @pytest.mark.asyncio
    async def test_get_responses_by_alert_type_no_matches(
        self,
        mock_redis_client,
    ) -> None:
        """Test get_responses_by_alert_type returns empty list when no matches."""
        from cyberred.core.alerts import AlertType
        from cyberred.core.audit import AlertAuditLogger
        
        # Mock returns entries but none match the type we're looking for
        mock_redis_client.xrange.return_value = [
            ("1-0", {"alert_type": "new_subnet", "operator_response": "continue"}),
            ("2-0", {"alert_type": "unexpected_service", "operator_response": "continue"}),
        ]
        
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        
        entries = await logger.get_responses_by_alert_type(
            engagement_id="test-engagement",
            alert_type=AlertType.HONEYPOT,
        )
        
        # Should return empty list when no matches
        assert len(entries) == 0

    @pytest.mark.asyncio
    async def test_get_responses_for_engagement_empty_stream(
        self,
        mock_redis_client,
    ) -> None:
        """Test get_responses_for_engagement returns empty list for empty stream."""
        from cyberred.core.audit import AlertAuditLogger
        
        mock_redis_client.xrange.return_value = []
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        
        entries = await logger.get_responses_for_engagement("empty-engagement")
        
        assert entries == []

    @pytest.mark.asyncio
    async def test_get_responses_for_engagement_uses_xrange_params(
        self,
        mock_redis_client,
    ) -> None:
        """Test get_responses_for_engagement calls xrange with correct parameters."""
        from cyberred.core.audit import AlertAuditLogger
        
        mock_redis_client.xrange.return_value = []
        logger = AlertAuditLogger(redis_client=mock_redis_client)
        
        await logger.get_responses_for_engagement("test-eng", limit=25)
        
        # Verify xrange was called with stream key, "-", "+", and count
        call_args = mock_redis_client.xrange.call_args
        assert call_args[0][0] == "cyberred:audit:alerts:test-eng"
        assert call_args[0][1] == "-"
        assert call_args[0][2] == "+"
        assert call_args.kwargs.get("count") == 25


class TestAlertResponseHandlerAllDecisions:
    """Test all decision paths through handle_response unified method."""

    @pytest.mark.asyncio
    async def test_handle_response_routes_to_handle_continue(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test handle_response routes CONTINUE to handle_continue."""
        from cyberred.core.alerts import AlertResponseHandler, AlertResponseDecision
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        response = await handler.handle_response(
            alert=sample_alert_trigger,
            decision=AlertResponseDecision.CONTINUE,
            operator="test_operator",
            notes="Continuing after review",
        )
        
        assert response.decision == AlertResponseDecision.CONTINUE
        assert response.notes == "Continuing after review"
        mock_engagement_manager.pause.assert_not_called()
        mock_redis_client.xadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_response_routes_to_handle_stop(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test handle_response routes STOP to handle_stop."""
        from cyberred.core.alerts import AlertResponseHandler, AlertResponseDecision
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        response = await handler.handle_response(
            alert=sample_alert_trigger,
            decision=AlertResponseDecision.STOP,
            operator="test_operator",
            notes="Emergency stop",
        )
        
        assert response.decision == AlertResponseDecision.STOP
        mock_engagement_manager.pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_response_routes_to_handle_notes(
        self,
        mock_redis_client,
        mock_engagement_manager,
        sample_alert_trigger,
    ) -> None:
        """Test handle_response routes NOTES to _handle_notes."""
        from cyberred.core.alerts import AlertResponseHandler, AlertResponseDecision
        from cyberred.core.audit import AlertAuditLogger
        
        audit_logger = AlertAuditLogger(redis_client=mock_redis_client)
        handler = AlertResponseHandler(
            audit_logger=audit_logger,
            engagement_manager=mock_engagement_manager,
        )
        
        response = await handler.handle_response(
            alert=sample_alert_trigger,
            decision=AlertResponseDecision.NOTES,
            operator="test_operator",
            notes="Adding notes and continuing",
        )
        
        assert response.decision == AlertResponseDecision.NOTES
        assert response.notes == "Adding notes and continuing"
        mock_engagement_manager.pause.assert_not_called()
