"""Unit tests for DeputyEscalationManager.

Story 10.8: Deputy Operator Configuration
Tests AC: #2, #3, #6

RED Phase: These tests should FAIL until DeputyEscalationManager is implemented.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDeputyEscalationManagerInit:
    """Tests for DeputyEscalationManager initialization."""

    def test_init_with_config(self) -> None:
        """Test initialization with DeputyOperatorConfig."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        config = DeputyOperatorConfig(
            deputy_operator="deputy@example.com",
            escalation_timeout=timedelta(minutes=30),
        )
        event_bus = MagicMock()
        audit_logger = MagicMock()
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=event_bus,
            audit_logger=audit_logger,
        )
        
        assert manager._config == config
        assert manager._event_bus == event_bus
        assert manager._audit == audit_logger

    def test_init_timers_empty(self) -> None:
        """Test that timers dict is empty on init."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        config = DeputyOperatorConfig(deputy_operator="deputy@example.com")
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=MagicMock(),
            audit_logger=MagicMock(),
        )
        
        assert len(manager._timers) == 0
        assert len(manager._start_times) == 0


class TestDeputyEscalationManagerStartTimer:
    """Tests for DeputyEscalationManager.start_escalation_timer()."""

    @pytest.mark.asyncio
    async def test_start_escalation_timer(self) -> None:
        """Test starting an escalation timer for a request."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        config = DeputyOperatorConfig(
            deputy_operator="deputy@example.com",
            escalation_timeout=timedelta(minutes=30),
        )
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=MagicMock(),
            audit_logger=MagicMock(),
        )
        
        await manager.start_escalation_timer("request-123")
        
        assert "request-123" in manager._timers
        assert "request-123" in manager._start_times

    @pytest.mark.asyncio
    async def test_start_timer_records_start_time(self) -> None:
        """Test that start_escalation_timer records the start time."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        config = DeputyOperatorConfig(deputy_operator="deputy@example.com")
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=MagicMock(),
            audit_logger=MagicMock(),
        )
        
        before = datetime.now(timezone.utc)
        await manager.start_escalation_timer("request-123")
        after = datetime.now(timezone.utc)
        
        start_time = manager._start_times["request-123"]
        assert before <= start_time <= after

    @pytest.mark.asyncio
    async def test_start_timer_idempotent(self) -> None:
        """Test that starting timer twice doesn't create duplicate timers."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        config = DeputyOperatorConfig(deputy_operator="deputy@example.com")
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=MagicMock(),
            audit_logger=MagicMock(),
        )
        
        await manager.start_escalation_timer("request-123")
        original_timer = manager._timers["request-123"]
        original_start = manager._start_times["request-123"]
        
        await manager.start_escalation_timer("request-123")
        
        # Should not create new timer
        assert manager._timers["request-123"] == original_timer
        assert manager._start_times["request-123"] == original_start

    @pytest.mark.asyncio
    async def test_multiple_concurrent_timers(self) -> None:
        """Test managing multiple concurrent escalation timers."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        config = DeputyOperatorConfig(deputy_operator="deputy@example.com")
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=MagicMock(),
            audit_logger=MagicMock(),
        )
        
        await manager.start_escalation_timer("request-1")
        await manager.start_escalation_timer("request-2")
        await manager.start_escalation_timer("request-3")
        
        assert len(manager._timers) == 3
        assert "request-1" in manager._timers
        assert "request-2" in manager._timers
        assert "request-3" in manager._timers


class TestDeputyEscalationManagerCancelTimer:
    """Tests for DeputyEscalationManager.cancel_escalation_timer()."""

    @pytest.mark.asyncio
    async def test_cancel_escalation_timer(self) -> None:
        """Test cancelling an escalation timer."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        config = DeputyOperatorConfig(deputy_operator="deputy@example.com")
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=MagicMock(),
            audit_logger=MagicMock(),
        )
        
        await manager.start_escalation_timer("request-123")
        assert "request-123" in manager._timers
        
        await manager.cancel_escalation_timer("request-123")
        
        assert "request-123" not in manager._timers
        assert "request-123" not in manager._start_times

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_timer_no_error(self) -> None:
        """Test that cancelling nonexistent timer doesn't raise error."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        config = DeputyOperatorConfig(deputy_operator="deputy@example.com")
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=MagicMock(),
            audit_logger=MagicMock(),
        )
        
        # Should not raise
        await manager.cancel_escalation_timer("nonexistent-request")

    @pytest.mark.asyncio
    async def test_primary_response_cancels_escalation(self) -> None:
        """Test that primary operator response cancels escalation (AC: #6)."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        config = DeputyOperatorConfig(deputy_operator="deputy@example.com")
        event_bus = MagicMock()
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=event_bus,
            audit_logger=MagicMock(),
        )
        
        await manager.start_escalation_timer("request-123")
        
        # Primary responds - cancel escalation
        await manager.cancel_escalation_timer("request-123")
        
        # Timer should be cancelled, deputy should NOT be notified
        assert "request-123" not in manager._timers
        # Event bus should NOT have published escalation event
        event_bus.publish.assert_not_called()


class TestDeputyEscalationManagerGetTimeRemaining:
    """Tests for DeputyEscalationManager.get_time_until_escalation()."""

    @pytest.mark.asyncio
    async def test_get_time_until_escalation(self) -> None:
        """Test getting remaining time until escalation."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        config = DeputyOperatorConfig(
            deputy_operator="deputy@example.com",
            escalation_timeout=timedelta(minutes=30),
        )
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=MagicMock(),
            audit_logger=MagicMock(),
        )
        
        await manager.start_escalation_timer("request-123")
        
        remaining = manager.get_time_until_escalation("request-123")
        
        # Should be close to 30 minutes
        assert remaining is not None
        assert timedelta(minutes=29) < remaining <= timedelta(minutes=30)

    def test_get_time_until_escalation_nonexistent(self) -> None:
        """Test getting time for nonexistent request returns None."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        config = DeputyOperatorConfig(deputy_operator="deputy@example.com")
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=MagicMock(),
            audit_logger=MagicMock(),
        )
        
        remaining = manager.get_time_until_escalation("nonexistent")
        
        assert remaining is None

    @pytest.mark.asyncio
    async def test_get_time_decreases_over_time(self) -> None:
        """Test that remaining time decreases as time passes."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        # Use minimum valid timeout (5 minutes)
        config = DeputyOperatorConfig(
            deputy_operator="deputy@example.com",
            escalation_timeout=timedelta(minutes=5),
        )
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=MagicMock(),
            audit_logger=MagicMock(),
        )
        
        await manager.start_escalation_timer("request-123")
        
        time1 = manager.get_time_until_escalation("request-123")
        await asyncio.sleep(0.1)
        time2 = manager.get_time_until_escalation("request-123")
        
        assert time1 is not None
        assert time2 is not None
        assert time2 < time1


class TestDeputyEscalationManagerTimeout:
    """Tests for escalation timeout behavior."""

    @pytest.mark.asyncio
    async def test_escalation_triggers_after_timeout(self) -> None:
        """Test that escalation triggers after timeout expires (AC: #2).
        
        Uses object.__new__ to bypass __post_init__ validation for testing
        with very short timeouts.
        """
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        # Bypass validation for testing with short timeout
        config = object.__new__(DeputyOperatorConfig)
        config.deputy_operator = "deputy@example.com"
        config.escalation_timeout = timedelta(milliseconds=100)
        
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()
        audit_logger = MagicMock()
        audit_logger.log_escalation = AsyncMock()
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=event_bus,
            audit_logger=audit_logger,
        )
        
        await manager.start_escalation_timer("request-123")
        
        # Wait for timeout to expire
        await asyncio.sleep(0.2)
        
        # Escalation event should have been published
        event_bus.publish.assert_called()
        
        # Check that the event has correct structure
        call_args = event_bus.publish.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_escalation_logs_to_audit_trail(self) -> None:
        """Test that escalation is logged to audit trail (AC: #2).
        
        Uses object.__new__ to bypass __post_init__ validation for testing
        with very short timeouts.
        """
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        # Bypass validation for testing with short timeout
        config = object.__new__(DeputyOperatorConfig)
        config.deputy_operator = "deputy@example.com"
        config.escalation_timeout = timedelta(milliseconds=100)
        
        audit_logger = MagicMock()
        audit_logger.log_escalation = AsyncMock()
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=MagicMock(publish=AsyncMock()),
            audit_logger=audit_logger,
        )
        
        await manager.start_escalation_timer("request-123")
        await asyncio.sleep(0.2)
        
        # Audit logger should have been called
        audit_logger.log_escalation.assert_called_once()
        call_kwargs = audit_logger.log_escalation.call_args.kwargs
        assert call_kwargs["request_id"] == "request-123"
        assert call_kwargs["deputy"] == "deputy@example.com"

    @pytest.mark.asyncio
    async def test_timer_cleanup_after_timeout(self) -> None:
        """Test that timer is cleaned up after timeout fires.
        
        Uses object.__new__ to bypass __post_init__ validation for testing
        with very short timeouts.
        """
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        # Bypass validation for testing with short timeout
        config = object.__new__(DeputyOperatorConfig)
        config.deputy_operator = "deputy@example.com"
        config.escalation_timeout = timedelta(milliseconds=100)
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=MagicMock(publish=AsyncMock()),
            audit_logger=MagicMock(log_escalation=AsyncMock()),
        )
        
        await manager.start_escalation_timer("request-123")
        await asyncio.sleep(0.2)
        
        # Timer should be cleaned up
        assert "request-123" not in manager._timers
        assert "request-123" not in manager._start_times


class TestDeputyResponseHandling:
    """Tests for deputy response handling (AC: #3)."""

    @pytest.mark.asyncio
    async def test_deputy_response_approve(self) -> None:
        """Test deputy can respond with Y (approve)."""
        from cyberred.daemon.deputy_escalation import DeputyResponse, process_deputy_response
        
        response = DeputyResponse(
            request_id="request-123",
            decision="APPROVED",
            responder="deputy@example.com",
            escalated=True,
        )
        
        assert response.decision == "APPROVED"
        assert response.responder == "deputy@example.com"
        assert response.escalated is True

    @pytest.mark.asyncio
    async def test_deputy_response_deny(self) -> None:
        """Test deputy can respond with N (deny)."""
        from cyberred.daemon.deputy_escalation import DeputyResponse
        
        response = DeputyResponse(
            request_id="request-123",
            decision="DENIED",
            responder="deputy@example.com",
            escalated=True,
        )
        
        assert response.decision == "DENIED"

    @pytest.mark.asyncio
    async def test_deputy_response_more_info(self) -> None:
        """Test deputy can respond with M (more info)."""
        from cyberred.daemon.deputy_escalation import DeputyResponse
        
        response = DeputyResponse(
            request_id="request-123",
            decision="MORE_INFO",
            responder="deputy@example.com",
            escalated=True,
        )
        
        assert response.decision == "MORE_INFO"

    @pytest.mark.asyncio
    async def test_deputy_response_skip(self) -> None:
        """Test deputy can respond with S (skip)."""
        from cyberred.daemon.deputy_escalation import DeputyResponse
        
        response = DeputyResponse(
            request_id="request-123",
            decision="SKIPPED",
            responder="deputy@example.com",
            escalated=True,
        )
        
        assert response.decision == "SKIPPED"

    def test_deputy_response_to_dict(self) -> None:
        """Test deputy response serialization."""
        from cyberred.daemon.deputy_escalation import DeputyResponse
        
        response = DeputyResponse(
            request_id="request-123",
            decision="APPROVED",
            responder="deputy@example.com",
            escalated=True,
            constraints={"time_limit": 3600},
        )
        
        data = response.to_dict()
        
        assert data["request_id"] == "request-123"
        assert data["decision"] == "APPROVED"
        assert data["responder"] == "deputy@example.com"
        assert data["escalated"] is True
        assert data["constraints"] == {"time_limit": 3600}

    def test_deputy_response_with_notes(self) -> None:
        """Test deputy response with notes field."""
        from cyberred.daemon.deputy_escalation import DeputyResponse
        
        response = DeputyResponse(
            request_id="request-123",
            decision="APPROVED",
            responder="deputy@example.com",
            notes="Approved due to time sensitivity",
        )
        
        assert response.notes == "Approved due to time sensitivity"
        
        data = response.to_dict()
        assert data["notes"] == "Approved due to time sensitivity"

    def test_deputy_response_timestamp_auto_generated(self) -> None:
        """Test that deputy response timestamp is auto-generated in ISO format."""
        from datetime import datetime
        from cyberred.daemon.deputy_escalation import DeputyResponse
        
        response = DeputyResponse(
            request_id="request-123",
            decision="APPROVED",
            responder="deputy@example.com",
        )
        
        # Verify timestamp is set and is valid ISO format
        assert response.timestamp is not None
        # Should parse without error
        parsed = datetime.fromisoformat(response.timestamp.replace('Z', '+00:00'))
        assert parsed is not None
        
        data = response.to_dict()
        assert data["timestamp"] == response.timestamp


class TestEscalationAuditEntry:
    """Tests for escalation audit entries."""

    def test_escalation_audit_entry_format(self) -> None:
        """Test audit entry format for escalated requests (AC: #3)."""
        from cyberred.daemon.deputy_escalation import create_escalation_audit_entry
        
        entry = create_escalation_audit_entry(
            request_id="request-123",
            decision="APPROVED",
            responder="deputy@example.com",
            escalated=True,
            escalated_at="2026-01-15T14:00:00Z",
            original_operator="primary@example.com",
        )
        
        assert entry["event_type"] == "authorization_response"
        assert entry["request_id"] == "request-123"
        assert entry["decision"] == "APPROVED"
        assert entry["responder"] == "deputy@example.com"
        assert entry["escalated"] is True
        assert entry["escalated_at"] == "2026-01-15T14:00:00Z"
        assert entry["original_operator"] == "primary@example.com"


class TestDeputyEscalationManagerErrorHandling:
    """Tests for error handling in escalation manager."""

    @pytest.mark.asyncio
    async def test_escalation_handles_audit_error(self) -> None:
        """Test that escalation continues even if audit logging fails."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        # Bypass validation for testing with short timeout
        config = object.__new__(DeputyOperatorConfig)
        config.deputy_operator = "deputy@example.com"
        config.escalation_timeout = timedelta(milliseconds=100)
        
        # Audit logger that raises an exception
        audit_logger = MagicMock()
        audit_logger.log_escalation = AsyncMock(side_effect=Exception("Audit failed"))
        
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=event_bus,
            audit_logger=audit_logger,
        )
        
        await manager.start_escalation_timer("request-123")
        await asyncio.sleep(0.2)
        
        # Event bus should still have been called despite audit error
        event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_escalation_handles_event_bus_error(self) -> None:
        """Test that escalation completes even if event bus fails."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        # Bypass validation for testing with short timeout
        config = object.__new__(DeputyOperatorConfig)
        config.deputy_operator = "deputy@example.com"
        config.escalation_timeout = timedelta(milliseconds=100)
        
        audit_logger = MagicMock()
        audit_logger.log_escalation = AsyncMock()
        
        # Event bus that raises an exception
        event_bus = MagicMock()
        event_bus.publish = AsyncMock(side_effect=Exception("Event bus failed"))
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=event_bus,
            audit_logger=audit_logger,
        )
        
        await manager.start_escalation_timer("request-123")
        await asyncio.sleep(0.2)
        
        # Audit should still have been called
        audit_logger.log_escalation.assert_called()
        # Timer should be cleaned up despite errors
        assert "request-123" not in manager._timers


class TestDeputyResponseProcessing:
    """Tests for deputy response processing."""

    @pytest.mark.asyncio
    async def test_process_deputy_response_success(self) -> None:
        """Test processing response for existing request returns True."""
        from cyberred.daemon.authorization_queue import AuthorizationQueue
        from cyberred.daemon.deputy_escalation import (
            DeputyResponse,
            process_deputy_response,
        )
        from cyberred.tui.screens.authorization import AuthorizationRequest
        
        queue = AuthorizationQueue()
        
        # Add a request to the queue
        request = AuthorizationRequest(
            id="request-123",
            request_type="lateral_move",
            agent_id="agent-001",
            target="192.168.1.100",
            proposed_action="SSH to target",
        )
        queue.add_request(request)
        
        # Verify request is in queue
        assert queue.get_request_by_id("request-123") is not None
        
        # Process deputy response
        response = DeputyResponse(
            request_id="request-123",
            decision="APPROVED",
            responder="deputy@example.com",
            escalated=True,
        )
        
        result = await process_deputy_response(response=response, queue=queue)
        
        # Should return True and remove request from queue
        assert result is True
        assert queue.get_request_by_id("request-123") is None

    @pytest.mark.asyncio
    async def test_process_deputy_response_unknown_request(self) -> None:
        """Test processing response for unknown request returns False."""
        from cyberred.daemon.authorization_queue import AuthorizationQueue
        from cyberred.daemon.deputy_escalation import (
            DeputyResponse,
            process_deputy_response,
        )
        
        queue = AuthorizationQueue()
        
        # No request in queue
        response = DeputyResponse(
            request_id="nonexistent-request",
            decision="APPROVED",
            responder="deputy@example.com",
            escalated=True,
        )
        
        result = await process_deputy_response(response=response, queue=queue)
        
        assert result is False


class TestDeputyEscalationManagerCancelAll:
    """Tests for cancelling all timers (e.g., on engagement pause)."""

    @pytest.mark.asyncio
    async def test_cancel_all_timers(self) -> None:
        """Test cancelling all active escalation timers."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        config = DeputyOperatorConfig(deputy_operator="deputy@example.com")
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=MagicMock(),
            audit_logger=MagicMock(),
        )
        
        await manager.start_escalation_timer("request-1")
        await manager.start_escalation_timer("request-2")
        await manager.start_escalation_timer("request-3")
        
        assert len(manager._timers) == 3
        
        await manager.cancel_all_timers()
        
        assert len(manager._timers) == 0
        assert len(manager._start_times) == 0

    @pytest.mark.asyncio
    async def test_get_active_escalations(self) -> None:
        """Test getting list of active escalation request IDs."""
        from cyberred.core.config import DeputyOperatorConfig
        from cyberred.daemon.deputy_escalation import DeputyEscalationManager
        
        config = DeputyOperatorConfig(deputy_operator="deputy@example.com")
        
        manager = DeputyEscalationManager(
            config=config,
            event_bus=MagicMock(),
            audit_logger=MagicMock(),
        )
        
        await manager.start_escalation_timer("request-1")
        await manager.start_escalation_timer("request-2")
        
        active = manager.get_active_escalations()
        
        assert set(active) == {"request-1", "request-2"}
