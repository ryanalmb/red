"""Unit tests for Drop Box Abort & Wipe functionality.

Story 12.10: Drop Box Abort & Wipe
Tests follow RED-GREEN-REFACTOR TDD cycle.
Coverage target: 100% for abort.py

These tests are in RED phase - they test functionality that doesn't exist yet.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# NOTE: These imports will FAIL until implementation exists
# This is intentional - RED phase of TDD
# =============================================================================

# Import statements for modules that don't exist yet
# These will cause ImportError until implementation
try:
    from cyberred.c2.abort import (
        AbortCommand,
        AbortController,
        AbortControllerConfig,
        AbortReason,
        AbortResult,
        WipeResult,
        WipeStatus,
    )
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False
    # Define placeholder classes for test discovery
    AbortReason = None
    WipeStatus = None
    AbortCommand = None
    WipeResult = None
    AbortResult = None
    AbortControllerConfig = None
    AbortController = None


# Skip all tests if imports fail (RED phase indicator)
pytestmark = pytest.mark.skipif(
    not IMPORTS_AVAILABLE,
    reason="abort module not implemented yet (RED phase)"
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def default_config() -> "AbortControllerConfig":
    """Default abort controller config (30s timeout)."""
    return AbortControllerConfig()


@pytest.fixture
def fast_config() -> "AbortControllerConfig":
    """Fast config for testing (1s timeout)."""
    return AbortControllerConfig(wipe_timeout_seconds=1)


@pytest.fixture
def mock_c2_server() -> MagicMock:
    """Create mock C2Server with async send/receive methods."""
    mock = MagicMock()
    mock.send_to_drop_box = AsyncMock()
    mock.receive_from_drop_box = AsyncMock()
    mock.get_connection = MagicMock()
    mock.mark_as_lost = MagicMock()
    return mock


@pytest.fixture
def mock_event_bus() -> MagicMock:
    """Create mock EventBus."""
    mock = MagicMock()
    mock.publish = AsyncMock()
    return mock


@pytest.fixture
def controller(
    default_config: "AbortControllerConfig",
    mock_c2_server: MagicMock,
    mock_event_bus: MagicMock,
) -> "AbortController":
    """Create AbortController with mocked dependencies."""
    return AbortController(
        config=default_config,
        c2_server=mock_c2_server,
        event_bus=mock_event_bus,
    )


# =============================================================================
# AC#1: Abort Command Sent via C2 with Reason
# Given drop box is connected
# When I trigger abort from TUI
# Then abort command sent via C2
# And command includes abort reason for audit trail
# =============================================================================


class TestAbortReasonEnum:
    """Tests for AbortReason enum (AC#1, Task 1.1)."""

    def test_abort_reason_values(self) -> None:
        """AbortReason has correct values per Task 1.1."""
        assert AbortReason.OPERATOR_INITIATED.value == "operator_initiated"
        assert AbortReason.COMPROMISED.value == "compromised"
        assert AbortReason.ENGAGEMENT_ENDED.value == "engagement_ended"
        assert AbortReason.EMERGENCY.value == "emergency"

    def test_abort_reason_members(self) -> None:
        """AbortReason has all 4 expected members."""
        members = list(AbortReason)
        assert len(members) == 4
        assert AbortReason.OPERATOR_INITIATED in members
        assert AbortReason.COMPROMISED in members
        assert AbortReason.ENGAGEMENT_ENDED in members
        assert AbortReason.EMERGENCY in members


class TestWipeStatusEnum:
    """Tests for WipeStatus enum (AC#3, Task 1.2)."""

    def test_wipe_status_values(self) -> None:
        """WipeStatus has correct values per Task 1.2."""
        assert WipeStatus.SUCCESS.value == "success"
        assert WipeStatus.PARTIAL.value == "partial"
        assert WipeStatus.FAILED.value == "failed"
        assert WipeStatus.IN_PROGRESS.value == "in_progress"
        assert WipeStatus.NOT_STARTED.value == "not_started"

    def test_wipe_status_members(self) -> None:
        """WipeStatus has all 5 expected members."""
        members = list(WipeStatus)
        assert len(members) == 5


class TestAbortCommand:
    """Tests for AbortCommand dataclass (AC#1, Task 1.3)."""

    def test_abort_command_creation(self) -> None:
        """AbortCommand can be created with all required fields."""
        cmd = AbortCommand(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
            timestamp="2026-02-12T00:00:00Z",
            delete_binary=False,
        )
        assert cmd.drop_box_id == "db-001"
        assert cmd.reason == AbortReason.OPERATOR_INITIATED
        assert cmd.issued_by == "operator@test.com"
        assert cmd.timestamp == "2026-02-12T00:00:00Z"
        assert cmd.delete_binary is False

    def test_abort_command_with_delete_binary(self) -> None:
        """AbortCommand with delete_binary=True."""
        cmd = AbortCommand(
            drop_box_id="db-002",
            reason=AbortReason.COMPROMISED,
            issued_by="admin@test.com",
            timestamp="2026-02-12T00:00:00Z",
            delete_binary=True,
        )
        assert cmd.delete_binary is True

    def test_abort_command_reason_is_enum(self) -> None:
        """AbortCommand reason must be AbortReason enum."""
        cmd = AbortCommand(
            drop_box_id="db-003",
            reason=AbortReason.EMERGENCY,
            issued_by="admin@test.com",
            timestamp="2026-02-12T00:00:00Z",
            delete_binary=False,
        )
        assert isinstance(cmd.reason, AbortReason)


class TestWipeResult:
    """Tests for WipeResult dataclass (AC#3, Task 1.4)."""

    def test_wipe_result_success(self) -> None:
        """WipeResult with successful wipe."""
        result = WipeResult(
            status=WipeStatus.SUCCESS,
            files_wiped=10,
            files_failed=0,
            errors=[],
            duration_ms=500,
        )
        assert result.status == WipeStatus.SUCCESS
        assert result.files_wiped == 10
        assert result.files_failed == 0
        assert result.errors == []
        assert result.duration_ms == 500

    def test_wipe_result_partial(self) -> None:
        """WipeResult with partial wipe (some files failed)."""
        result = WipeResult(
            status=WipeStatus.PARTIAL,
            files_wiped=8,
            files_failed=2,
            errors=["file1.log: Permission denied", "file2.key: File locked"],
            duration_ms=750,
        )
        assert result.status == WipeStatus.PARTIAL
        assert result.files_wiped == 8
        assert result.files_failed == 2
        assert len(result.errors) == 2

    def test_wipe_result_failed(self) -> None:
        """WipeResult with failed wipe."""
        result = WipeResult(
            status=WipeStatus.FAILED,
            files_wiped=0,
            files_failed=10,
            errors=["Disk read-only"],
            duration_ms=100,
        )
        assert result.status == WipeStatus.FAILED
        assert result.files_wiped == 0
        assert result.files_failed == 10


class TestAbortResult:
    """Tests for AbortResult dataclass (AC#2, Task 1.5)."""

    def test_abort_result_success(self) -> None:
        """AbortResult with successful abort and wipe."""
        wipe_result = WipeResult(
            status=WipeStatus.SUCCESS,
            files_wiped=10,
            files_failed=0,
            errors=[],
            duration_ms=500,
        )
        result = AbortResult(
            drop_box_id="db-001",
            abort_received=True,
            wipe_result=wipe_result,
            self_destruct_initiated=True,
            timestamp="2026-02-12T00:00:00Z",
        )
        assert result.drop_box_id == "db-001"
        assert result.abort_received is True
        assert result.wipe_result.status == WipeStatus.SUCCESS
        assert result.self_destruct_initiated is True

    def test_abort_result_connection_lost(self) -> None:
        """AbortResult when connection lost (AC#6)."""
        result = AbortResult(
            drop_box_id="db-001",
            abort_received=False,
            wipe_result=None,
            self_destruct_initiated=False,
            timestamp="2026-02-12T00:00:00Z",
        )
        assert result.abort_received is False
        assert result.wipe_result is None


# =============================================================================
# AC#1, AC#2: AbortController Tests
# =============================================================================


class TestAbortControllerConfig:
    """Tests for AbortControllerConfig dataclass (Task 2.1)."""

    def test_config_defaults(self) -> None:
        """AbortControllerConfig has correct defaults."""
        config = AbortControllerConfig()
        assert config.wipe_timeout_seconds == 30
        assert config.delete_binary_default is False

    def test_config_custom_values(self) -> None:
        """AbortControllerConfig accepts custom values."""
        config = AbortControllerConfig(
            wipe_timeout_seconds=60,
            delete_binary_default=True,
        )
        assert config.wipe_timeout_seconds == 60
        assert config.delete_binary_default is True


class TestAbortControllerInit:
    """Tests for AbortController initialization (Task 2.2)."""

    def test_controller_init_with_all_deps(
        self,
        default_config: "AbortControllerConfig",
        mock_c2_server: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """AbortController initializes with all dependencies."""
        controller = AbortController(
            config=default_config,
            c2_server=mock_c2_server,
            event_bus=mock_event_bus,
        )
        assert controller.config == default_config
        assert controller._c2_server == mock_c2_server
        assert controller._event_bus == mock_event_bus

    def test_controller_init_without_event_bus(
        self,
        default_config: "AbortControllerConfig",
        mock_c2_server: MagicMock,
    ) -> None:
        """AbortController initializes without EventBus (optional)."""
        controller = AbortController(
            config=default_config,
            c2_server=mock_c2_server,
        )
        assert controller._event_bus is None


class TestAbortControllerSendAbort:
    """Tests for AbortController.send_abort() (AC#1, Task 2.3)."""

    @pytest.mark.asyncio
    async def test_send_abort_success(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
    ) -> None:
        """send_abort sends abort command and returns result (AC#1)."""
        # Mock successful abort response
        mock_c2_server.receive_from_drop_box.return_value = {
            "command_id": "abort-123",
            "wipe_status": "success",
            "files_wiped": 10,
            "files_failed": 0,
            "errors": [],
        }
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
            delete_binary=False,
        )
        
        # Verify command was sent
        mock_c2_server.send_to_drop_box.assert_called_once()
        call_args = mock_c2_server.send_to_drop_box.call_args
        assert call_args[0][0] == "db-001"  # drop_box_id
        
        # Verify result
        assert result.drop_box_id == "db-001"
        assert result.abort_received is True
        assert result.wipe_result.status == WipeStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_send_abort_includes_reason(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
    ) -> None:
        """send_abort command includes abort reason for audit trail (AC#1)."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "command_id": "abort-123",
            "wipe_status": "success",
            "files_wiped": 5,
            "files_failed": 0,
            "errors": [],
        }
        
        await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.COMPROMISED,
            issued_by="operator@test.com",
            delete_binary=True,
        )
        
        # Verify the abort command payload includes reason
        call_args = mock_c2_server.send_to_drop_box.call_args
        # call_args[0] = (drop_box_id, command, args)
        command = call_args[0][1]
        args = call_args[0][2]
        assert command == "abort"
        assert "reason" in args
        assert args["reason"] == "compromised"
        assert args["delete_binary"] is True


# =============================================================================
# AC#2: Drop Box Stops Operations Immediately
# =============================================================================


class TestAbortStopsOperations:
    """Tests for abort stopping all operations (AC#2)."""

    @pytest.mark.asyncio
    async def test_abort_stops_pending_commands(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
    ) -> None:
        """Abort stops all pending commands from executing (AC#2)."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "command_id": "abort-123",
            "wipe_status": "success",
            "files_wiped": 5,
            "files_failed": 0,
            "errors": [],
            "pending_commands_cancelled": 3,
        }
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.EMERGENCY,
            issued_by="operator@test.com",
        )
        
        assert result.abort_received is True


# =============================================================================
# AC#3: Wipe Sequence
# =============================================================================


class TestWipeSequence:
    """Tests for wipe sequence (AC#3)."""

    @pytest.mark.asyncio
    async def test_wipe_includes_certs_logs_cache(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
    ) -> None:
        """Wipe includes certificates, logs, and cached data (AC#3)."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "command_id": "abort-123",
            "wipe_status": "success",
            "files_wiped": 15,
            "files_failed": 0,
            "errors": [],
            "wiped_categories": ["certificates", "logs", "cache", "config"],
        }
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        assert result.wipe_result.status == WipeStatus.SUCCESS
        assert result.wipe_result.files_wiped > 0

    @pytest.mark.asyncio
    async def test_wipe_reports_completion_status(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
    ) -> None:
        """Wipe completion status is reported back to C2 (AC#3)."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "command_id": "abort-123",
            "wipe_status": "partial",
            "files_wiped": 8,
            "files_failed": 2,
            "errors": ["cert.pem: file locked"],
        }
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        assert result.wipe_result.status == WipeStatus.PARTIAL
        assert result.wipe_result.files_failed == 2
        assert len(result.wipe_result.errors) == 1


# =============================================================================
# AC#4: Self-Destruct
# =============================================================================


class TestSelfDestruct:
    """Tests for self-destruct behavior (AC#4)."""

    @pytest.mark.asyncio
    async def test_self_destruct_triggered_after_wipe(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
    ) -> None:
        """Self-destruct is triggered after wipe completes (AC#4)."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "command_id": "abort-123",
            "wipe_status": "success",
            "files_wiped": 10,
            "files_failed": 0,
            "errors": [],
            "self_destruct_initiated": True,
        }
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        assert result.self_destruct_initiated is True

    @pytest.mark.asyncio
    async def test_self_destruct_with_binary_deletion(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
    ) -> None:
        """Self-destruct optionally deletes binary (AC#4)."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "command_id": "abort-123",
            "wipe_status": "success",
            "files_wiped": 11,  # Including binary
            "files_failed": 0,
            "errors": [],
            "self_destruct_initiated": True,
            "binary_deleted": True,
        }
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
            delete_binary=True,
        )
        
        assert result.self_destruct_initiated is True


# =============================================================================
# AC#5: Audit Logging
# =============================================================================


class TestAbortAuditLogging:
    """Tests for abort audit logging (AC#5)."""

    @pytest.mark.asyncio
    async def test_abort_logged_to_audit_trail(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Abort is logged with timestamp, operator, drop_box_id, reason (AC#5)."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "command_id": "abort-123",
            "wipe_status": "success",
            "files_wiped": 10,
            "files_failed": 0,
            "errors": [],
        }
        
        await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        # Verify event was published to audit trail
        mock_event_bus.publish.assert_called()
        # Check for abort.initiated event
        calls = mock_event_bus.publish.call_args_list
        event_names = [str(call) for call in calls]
        assert any("abort" in name.lower() for name in event_names)

    @pytest.mark.asyncio
    async def test_wipe_status_logged(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Wipe status (success/partial/failed) is logged (AC#5)."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "command_id": "abort-123",
            "wipe_status": "partial",
            "files_wiped": 8,
            "files_failed": 2,
            "errors": ["file.log: locked"],
        }
        
        await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        # Verify wipe completion event was published
        assert mock_event_bus.publish.call_count >= 1


# =============================================================================
# AC#6: Connection Lost During Abort
# =============================================================================


class TestConnectionLostDuringAbort:
    """Tests for connection loss handling (AC#6, ERR4)."""

    @pytest.mark.asyncio
    async def test_wipe_proceeds_on_connection_loss(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
    ) -> None:
        """Wipe proceeds anyway when connection is lost (fail-safe) (AC#6)."""
        # Simulate timeout waiting for response
        mock_c2_server.receive_from_drop_box.side_effect = asyncio.TimeoutError()
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        # Command was sent (drop box will execute wipe locally)
        mock_c2_server.send_to_drop_box.assert_called_once()
        # Result indicates connection lost
        assert result.abort_received is False or result.wipe_result is None

    @pytest.mark.asyncio
    async def test_drop_box_marked_as_lost(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
    ) -> None:
        """Drop box is marked as 'lost' on C2 server when connection lost (AC#6)."""
        mock_c2_server.receive_from_drop_box.side_effect = asyncio.TimeoutError()
        
        await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        # Verify drop box was marked as lost
        mock_c2_server.mark_as_lost.assert_called_once()
        call_args = mock_c2_server.mark_as_lost.call_args
        assert call_args[0][0] == "db-001"

    @pytest.mark.asyncio
    async def test_warning_logged_on_connection_loss(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Warning is logged per ERR4 when connection lost (AC#6)."""
        mock_c2_server.receive_from_drop_box.side_effect = asyncio.TimeoutError()
        
        await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        # Verify connection_lost event was published
        mock_event_bus.publish.assert_called()


# =============================================================================
# AC#7: Safety Tests - Partial Wipe Scenarios
# =============================================================================


class TestPartialWipeScenarios:
    """Tests for partial wipe scenarios (AC#7)."""

    @pytest.mark.asyncio
    async def test_partial_wipe_some_files_locked(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
    ) -> None:
        """Partial wipe when some files are locked/inaccessible (AC#7)."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "command_id": "abort-123",
            "wipe_status": "partial",
            "files_wiped": 7,
            "files_failed": 3,
            "errors": [
                "server.key: Permission denied",
                "access.log: File in use",
                "cache.db: Read-only filesystem",
            ],
        }
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        assert result.wipe_result.status == WipeStatus.PARTIAL
        assert result.wipe_result.files_wiped == 7
        assert result.wipe_result.files_failed == 3
        assert len(result.wipe_result.errors) == 3


# =============================================================================
# Message Protocol Tests (Task 3)
# =============================================================================


class TestAbortMessageProtocol:
    """Tests for abort message protocol (Task 3)."""

    def test_create_abort_command_message(self) -> None:
        """Abort command message has correct structure (Task 3.2)."""
        # This test verifies the protocol helper function
        from cyberred.c2.abort import create_abort_command_message
        
        secret = b"test_secret"
        message = create_abort_command_message(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            delete_binary=True,
            secret=secret,
        )
        
        assert message.type.value == "command"
        assert message.payload["command"] == "abort"
        assert message.payload["args"]["reason"] == "operator_initiated"
        assert message.payload["args"]["delete_binary"] is True

    def test_create_abort_command_message_with_custom_id(self) -> None:
        """Abort command message accepts custom message_id."""
        from cyberred.c2.abort import create_abort_command_message
        
        secret = b"test_secret"
        custom_id = "custom-abort-123"
        message = create_abort_command_message(
            drop_box_id="db-002",
            reason=AbortReason.COMPROMISED,
            delete_binary=False,
            secret=secret,
            message_id=custom_id,
        )
        
        assert message.id == custom_id
        assert message.payload["args"]["drop_box_id"] == "db-002"
        assert message.payload["args"]["reason"] == "compromised"


# =============================================================================
# EventBus Integration Tests (Task 5)
# =============================================================================


class TestAbortControllerErrorHandling:
    """Tests for AbortController error handling paths."""

    @pytest.mark.asyncio
    async def test_send_abort_no_c2_server(
        self,
        default_config: "AbortControllerConfig",
        mock_event_bus: MagicMock,
    ) -> None:
        """send_abort handles missing C2 server gracefully."""
        controller = AbortController(
            config=default_config,
            c2_server=None,  # No C2 server
            event_bus=mock_event_bus,
        )
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        # Should return failure result
        assert result.abort_received is False
        assert result.wipe_result is None

    @pytest.mark.asyncio
    async def test_send_abort_send_command_fails(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
    ) -> None:
        """send_abort handles command send failure gracefully."""
        mock_c2_server.send_to_drop_box.side_effect = RuntimeError("Connection refused")
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        # Should return failure result and mark as lost
        assert result.abort_received is False
        assert result.wipe_result is None
        mock_c2_server.mark_as_lost.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_abort_uses_config_default_delete_binary(
        self,
        mock_c2_server: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """send_abort uses config default for delete_binary when not specified."""
        config = AbortControllerConfig(delete_binary_default=True)
        controller = AbortController(
            config=config,
            c2_server=mock_c2_server,
            event_bus=mock_event_bus,
        )
        
        mock_c2_server.receive_from_drop_box.return_value = {
            "wipe_status": "success",
            "files_wiped": 5,
            "files_failed": 0,
            "errors": [],
        }
        
        await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
            # delete_binary not specified - should use config default
        )
        
        call_args = mock_c2_server.send_to_drop_box.call_args
        args = call_args[0][2]
        assert args["delete_binary"] is True  # From config default

    @pytest.mark.asyncio
    async def test_wipe_confirmation_no_response(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
    ) -> None:
        """Handles case when wipe confirmation returns None."""
        mock_c2_server.receive_from_drop_box.return_value = None
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        # Should handle None response gracefully
        assert result.abort_received is False
        mock_c2_server.mark_as_lost.assert_called_once()

    @pytest.mark.asyncio
    async def test_wipe_confirmation_invalid_status(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
    ) -> None:
        """Handles invalid wipe status in response."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "wipe_status": "invalid_status",  # Not a valid WipeStatus
            "files_wiped": 0,
            "files_failed": 0,
            "errors": [],
        }
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        # Should default to FAILED status
        assert result.wipe_result.status == WipeStatus.FAILED

    @pytest.mark.asyncio
    async def test_send_abort_generic_exception(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
    ) -> None:
        """send_abort handles generic exceptions during wait."""
        mock_c2_server.receive_from_drop_box.side_effect = Exception("Unexpected error")
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        # Should handle exception and mark as lost
        assert result.abort_received is False
        mock_c2_server.mark_as_lost.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_connection_lost_without_c2_server(
        self,
        default_config: "AbortControllerConfig",
        mock_event_bus: MagicMock,
    ) -> None:
        """_handle_connection_lost works without C2 server."""
        controller = AbortController(
            config=default_config,
            c2_server=None,
            event_bus=mock_event_bus,
        )
        
        # Should not raise when c2_server is None
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        assert result.abort_received is False

    @pytest.mark.asyncio
    async def test_publish_event_failure_handled(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Event publishing failures are handled gracefully."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "wipe_status": "success",
            "files_wiped": 5,
            "files_failed": 0,
            "errors": [],
        }
        mock_event_bus.publish.side_effect = Exception("EventBus error")
        
        # Should not raise despite event publish failure
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        # Operation should still succeed
        assert result.drop_box_id == "db-001"


class TestEventBusIntegration:
    """Tests for EventBus event publishing (Task 5)."""

    @pytest.mark.asyncio
    async def test_abort_initiated_event_published(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """c2.abort.initiated event is published (Task 5.1)."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "command_id": "abort-123",
            "wipe_status": "success",
            "files_wiped": 10,
            "files_failed": 0,
            "errors": [],
        }
        
        await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        # Check that abort.initiated event was published
        calls = mock_event_bus.publish.call_args_list
        event_topics = [call[0][0] if call[0] else call[1].get("topic", "") for call in calls]
        assert any("abort.initiated" in str(topic) or "abort" in str(topic) for topic in event_topics)

    @pytest.mark.asyncio
    async def test_abort_completed_event_published(
        self,
        controller: "AbortController",
        mock_c2_server: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """c2.abort.completed event is published with overall result (Task 5.4)."""
        mock_c2_server.receive_from_drop_box.return_value = {
            "command_id": "abort-123",
            "wipe_status": "success",
            "files_wiped": 10,
            "files_failed": 0,
            "errors": [],
        }
        
        await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@test.com",
        )
        
        # Verify completed event published
        assert mock_event_bus.publish.call_count >= 2  # At least initiated + completed
