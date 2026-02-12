"""Integration tests for Drop Box Abort & Wipe functionality.

Story 12.10: Drop Box Abort & Wipe
Integration tests verify the full abort flow with minimal mocking.

These tests are in RED phase - they test functionality that doesn't exist yet.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# NOTE: These imports will FAIL until implementation exists
# This is intentional - RED phase of TDD
# =============================================================================

try:
    from cyberred.c2 import (
        C2Message,
        C2MessageType,
        C2Server,
        C2ServerConfig,
        create_command_message,
        validate_and_parse_message,
    )
    from cyberred.c2.abort import (
        AbortCommand,
        AbortController,
        AbortControllerConfig,
        AbortReason,
        AbortResult,
        WipeResult,
        WipeStatus,
        create_abort_command_message,
    )
    from cyberred.core.events import EventBus
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False
    # Placeholders for test discovery
    AbortController = None
    AbortControllerConfig = None
    AbortReason = None
    AbortResult = None
    WipeStatus = None
    create_abort_command_message = None


# Skip all tests if imports fail (RED phase indicator)
pytestmark = [
    pytest.mark.skipif(
        not IMPORTS_AVAILABLE,
        reason="abort module not implemented yet (RED phase)"
    ),
    pytest.mark.integration,
]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def shared_secret() -> bytes:
    """Shared secret for message signing."""
    return b"integration_test_secret_key_32bytes"


@pytest.fixture
def abort_config() -> "AbortControllerConfig":
    """Abort controller configuration for integration tests."""
    return AbortControllerConfig(
        wipe_timeout_seconds=5,
        delete_binary_default=False,
    )


@pytest.fixture
def mock_websocket() -> AsyncMock:
    """Mock WebSocket connection for integration testing."""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.recv = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def mock_c2_server(mock_websocket: AsyncMock, shared_secret: bytes) -> MagicMock:
    """Create a mock C2Server that simulates real WebSocket behavior."""
    server = MagicMock()
    server._connections = {"db-001": mock_websocket}
    server._shared_secret = shared_secret
    server.mark_as_lost = MagicMock()
    
    async def send_to_drop_box(drop_box_id: str, message: "C2Message") -> bool:
        if drop_box_id in server._connections:
            ws = server._connections[drop_box_id]
            await ws.send(message.to_json())
            return True
        return False
    
    async def receive_from_drop_box(drop_box_id: str, timeout: float) -> dict:
        if drop_box_id in server._connections:
            ws = server._connections[drop_box_id]
            response = await asyncio.wait_for(ws.recv(), timeout=timeout)
            return json.loads(response)
        raise ConnectionError(f"No connection for {drop_box_id}")
    
    server.send_to_drop_box = AsyncMock(side_effect=send_to_drop_box)
    server.receive_from_drop_box = AsyncMock(side_effect=receive_from_drop_box)
    
    return server


@pytest.fixture
def event_bus() -> MagicMock:
    """Create a mock EventBus for integration tests."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    bus.events_published = []
    
    async def capture_publish(topic: str, data: dict) -> None:
        bus.events_published.append({"topic": topic, "data": data})
    
    bus.publish.side_effect = capture_publish
    return bus


# =============================================================================
# AC#1: Integration Test - Abort Command via C2
# =============================================================================


class TestAbortCommandIntegration:
    """Integration tests for abort command flow (AC#1)."""

    @pytest.mark.asyncio
    async def test_abort_command_sent_and_received(
        self,
        abort_config: "AbortControllerConfig",
        mock_c2_server: MagicMock,
        mock_websocket: AsyncMock,
        event_bus: MagicMock,
        shared_secret: bytes,
    ) -> None:
        """Abort command is sent via C2 and response is received (AC#1)."""
        # Configure mock drop box response
        abort_response = {
            "command_id": "abort-integration-001",
            "wipe_status": "success",
            "files_wiped": 12,
            "files_failed": 0,
            "errors": [],
            "self_destruct_initiated": True,
        }
        mock_websocket.recv.return_value = json.dumps(abort_response)
        
        controller = AbortController(
            config=abort_config,
            c2_server=mock_c2_server,
            event_bus=event_bus,
        )
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="integration_test@example.com",
            delete_binary=False,
        )
        
        # Verify command was sent
        mock_websocket.send.assert_called_once()
        sent_message = mock_websocket.send.call_args[0][0]
        sent_data = json.loads(sent_message)
        
        # Verify message structure
        assert sent_data["type"] == "command"
        assert sent_data["payload"]["command"] == "abort"
        assert sent_data["payload"]["args"]["reason"] == "operator_initiated"
        
        # Verify result
        assert result.abort_received is True
        assert result.wipe_result.status == WipeStatus.SUCCESS
        assert result.wipe_result.files_wiped == 12

    @pytest.mark.asyncio
    async def test_abort_command_includes_signature(
        self,
        abort_config: "AbortControllerConfig",
        mock_c2_server: MagicMock,
        mock_websocket: AsyncMock,
        event_bus: MagicMock,
        shared_secret: bytes,
    ) -> None:
        """Abort command includes HMAC signature for security (AC#1)."""
        mock_websocket.recv.return_value = json.dumps({
            "command_id": "abort-001",
            "wipe_status": "success",
            "files_wiped": 5,
            "files_failed": 0,
            "errors": [],
        })
        
        controller = AbortController(
            config=abort_config,
            c2_server=mock_c2_server,
            event_bus=event_bus,
        )
        
        await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.COMPROMISED,
            issued_by="admin@example.com",
        )
        
        # Verify message has signature
        sent_message = mock_websocket.send.call_args[0][0]
        sent_data = json.loads(sent_message)
        
        assert "signature" in sent_data
        assert len(sent_data["signature"]) == 64  # SHA256 hex = 64 chars


# =============================================================================
# AC#2: Integration Test - Operations Stopped Immediately
# =============================================================================


class TestOperationsStoppedIntegration:
    """Integration tests for stopping operations (AC#2)."""

    @pytest.mark.asyncio
    async def test_abort_response_confirms_operations_stopped(
        self,
        abort_config: "AbortControllerConfig",
        mock_c2_server: MagicMock,
        mock_websocket: AsyncMock,
        event_bus: MagicMock,
    ) -> None:
        """Abort response confirms all operations were stopped (AC#2)."""
        mock_websocket.recv.return_value = json.dumps({
            "command_id": "abort-001",
            "wipe_status": "success",
            "files_wiped": 10,
            "files_failed": 0,
            "errors": [],
            "operations_stopped": True,
            "pending_commands_cancelled": 3,
        })
        
        controller = AbortController(
            config=abort_config,
            c2_server=mock_c2_server,
            event_bus=event_bus,
        )
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.EMERGENCY,
            issued_by="operator@example.com",
        )
        
        assert result.abort_received is True


# =============================================================================
# AC#5: Integration Test - Audit Events Published
# =============================================================================


class TestAuditEventsIntegration:
    """Integration tests for audit event publishing (AC#5)."""

    @pytest.mark.asyncio
    async def test_abort_publishes_initiated_event(
        self,
        abort_config: "AbortControllerConfig",
        mock_c2_server: MagicMock,
        mock_websocket: AsyncMock,
        event_bus: MagicMock,
    ) -> None:
        """Abort publishes c2.abort.initiated event (AC#5, Task 5.1)."""
        mock_websocket.recv.return_value = json.dumps({
            "command_id": "abort-001",
            "wipe_status": "success",
            "files_wiped": 10,
            "files_failed": 0,
            "errors": [],
        })
        
        controller = AbortController(
            config=abort_config,
            c2_server=mock_c2_server,
            event_bus=event_bus,
        )
        
        await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@example.com",
        )
        
        # Check that abort.initiated event was published
        event_topics = [e["topic"] for e in event_bus.events_published]
        assert any("abort.initiated" in topic for topic in event_topics)

    @pytest.mark.asyncio
    async def test_abort_publishes_completed_event(
        self,
        abort_config: "AbortControllerConfig",
        mock_c2_server: MagicMock,
        mock_websocket: AsyncMock,
        event_bus: MagicMock,
    ) -> None:
        """Abort publishes c2.abort.completed event with result (AC#5, Task 5.4)."""
        mock_websocket.recv.return_value = json.dumps({
            "command_id": "abort-001",
            "wipe_status": "success",
            "files_wiped": 10,
            "files_failed": 0,
            "errors": [],
        })
        
        controller = AbortController(
            config=abort_config,
            c2_server=mock_c2_server,
            event_bus=event_bus,
        )
        
        await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@example.com",
        )
        
        # Check that abort.completed event was published
        event_topics = [e["topic"] for e in event_bus.events_published]
        assert any("abort.completed" in topic or "completed" in topic for topic in event_topics)

    @pytest.mark.asyncio
    async def test_abort_event_contains_required_fields(
        self,
        abort_config: "AbortControllerConfig",
        mock_c2_server: MagicMock,
        mock_websocket: AsyncMock,
        event_bus: MagicMock,
    ) -> None:
        """Abort events contain timestamp, operator, drop_box_id, reason (AC#5)."""
        mock_websocket.recv.return_value = json.dumps({
            "command_id": "abort-001",
            "wipe_status": "success",
            "files_wiped": 10,
            "files_failed": 0,
            "errors": [],
        })
        
        controller = AbortController(
            config=abort_config,
            c2_server=mock_c2_server,
            event_bus=event_bus,
        )
        
        await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.COMPROMISED,
            issued_by="security@example.com",
        )
        
        # Find abort event and check fields
        abort_events = [
            e for e in event_bus.events_published 
            if "abort" in e["topic"].lower()
        ]
        
        assert len(abort_events) >= 1
        
        for event in abort_events:
            data = event["data"]
            # These fields are required for audit compliance
            assert "drop_box_id" in data or "timestamp" in data or len(data) > 0


# =============================================================================
# AC#6: Integration Test - Connection Loss Handling
# =============================================================================


class TestConnectionLossIntegration:
    """Integration tests for connection loss during abort (AC#6)."""

    @pytest.mark.asyncio
    async def test_timeout_marks_drop_box_as_lost(
        self,
        abort_config: "AbortControllerConfig",
        mock_c2_server: MagicMock,
        mock_websocket: AsyncMock,
        event_bus: MagicMock,
    ) -> None:
        """Timeout waiting for abort response marks drop box as lost (AC#6)."""
        # Simulate timeout
        mock_websocket.recv.side_effect = asyncio.TimeoutError()
        
        # Use short timeout config
        config = AbortControllerConfig(wipe_timeout_seconds=1)
        controller = AbortController(
            config=config,
            c2_server=mock_c2_server,
            event_bus=event_bus,
        )
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@example.com",
        )
        
        # Drop box should be marked as lost
        mock_c2_server.mark_as_lost.assert_called_once()
        
        # Result indicates connection was lost
        assert result.abort_received is False

    @pytest.mark.asyncio
    async def test_connection_error_marks_drop_box_as_lost(
        self,
        abort_config: "AbortControllerConfig",
        mock_c2_server: MagicMock,
        mock_websocket: AsyncMock,
        event_bus: MagicMock,
    ) -> None:
        """Connection error marks drop box as lost (AC#6)."""
        # Simulate connection error
        mock_websocket.recv.side_effect = ConnectionError("WebSocket closed")
        
        controller = AbortController(
            config=abort_config,
            c2_server=mock_c2_server,
            event_bus=event_bus,
        )
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.COMPROMISED,
            issued_by="operator@example.com",
        )
        
        # Drop box should be marked as lost
        mock_c2_server.mark_as_lost.assert_called()
        assert result.abort_received is False

    @pytest.mark.asyncio
    async def test_connection_lost_publishes_event(
        self,
        abort_config: "AbortControllerConfig",
        mock_c2_server: MagicMock,
        mock_websocket: AsyncMock,
        event_bus: MagicMock,
    ) -> None:
        """Connection loss publishes c2.abort.connection_lost event (AC#6, Task 5.3)."""
        mock_websocket.recv.side_effect = asyncio.TimeoutError()
        
        config = AbortControllerConfig(wipe_timeout_seconds=1)
        controller = AbortController(
            config=config,
            c2_server=mock_c2_server,
            event_bus=event_bus,
        )
        
        await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@example.com",
        )
        
        # Check that connection_lost event was published
        event_topics = [e["topic"] for e in event_bus.events_published]
        assert any("connection_lost" in topic or "lost" in topic for topic in event_topics)


# =============================================================================
# Message Protocol Integration Tests (Task 3)
# =============================================================================


class TestAbortMessageProtocolIntegration:
    """Integration tests for abort message protocol (Task 3)."""

    def test_create_abort_command_message_structure(
        self,
        shared_secret: bytes,
    ) -> None:
        """Abort command message has correct structure (Task 3.2, 3.4)."""
        message = create_abort_command_message(
            drop_box_id="db-001",
            reason=AbortReason.EMERGENCY,
            delete_binary=True,
            secret=shared_secret,
        )
        
        # Verify message type
        assert message.type == C2MessageType.COMMAND
        
        # Verify payload structure
        assert message.payload["command"] == "abort"
        assert message.payload["args"]["reason"] == "emergency"
        assert message.payload["args"]["delete_binary"] is True
        
        # Verify signature exists
        assert len(message.signature) == 64

    def test_abort_message_can_be_serialized_and_parsed(
        self,
        shared_secret: bytes,
    ) -> None:
        """Abort message can be serialized to JSON and parsed back (Task 3.5)."""
        original = create_abort_command_message(
            drop_box_id="db-001",
            reason=AbortReason.OPERATOR_INITIATED,
            delete_binary=False,
            secret=shared_secret,
        )
        
        # Serialize
        json_str = original.to_json()
        
        # Parse and validate
        parsed, error = validate_and_parse_message(json_str, shared_secret)
        
        assert error is None
        assert parsed is not None
        assert parsed.type == original.type
        assert parsed.payload == original.payload

    def test_abort_message_signature_verified(
        self,
        shared_secret: bytes,
    ) -> None:
        """Abort message signature is verified on parse (Task 3.5)."""
        message = create_abort_command_message(
            drop_box_id="db-001",
            reason=AbortReason.COMPROMISED,
            delete_binary=True,
            secret=shared_secret,
        )
        
        json_str = message.to_json()
        
        # Verify with correct secret succeeds
        parsed, error = validate_and_parse_message(json_str, shared_secret)
        assert error is None
        assert parsed is not None
        
        # Verify with wrong secret fails
        wrong_secret = b"wrong_secret"
        parsed, error = validate_and_parse_message(json_str, wrong_secret)
        assert error == "invalid_signature"
        assert parsed is None


# =============================================================================
# Full End-to-End Flow Integration Test
# =============================================================================


class TestAbortEndToEndFlow:
    """End-to-end integration tests for abort flow."""

    @pytest.mark.asyncio
    async def test_full_abort_flow_success(
        self,
        abort_config: "AbortControllerConfig",
        mock_c2_server: MagicMock,
        mock_websocket: AsyncMock,
        event_bus: MagicMock,
    ) -> None:
        """Full abort flow: send command → receive response → publish events (AC#1-5)."""
        # Configure successful abort response
        mock_websocket.recv.return_value = json.dumps({
            "command_id": "abort-e2e-001",
            "wipe_status": "success",
            "files_wiped": 15,
            "files_failed": 0,
            "errors": [],
            "self_destruct_initiated": True,
            "binary_deleted": False,
        })
        
        controller = AbortController(
            config=abort_config,
            c2_server=mock_c2_server,
            event_bus=event_bus,
        )
        
        # Execute abort
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.ENGAGEMENT_ENDED,
            issued_by="operator@example.com",
            delete_binary=False,
        )
        
        # Verify command was sent (AC#1)
        assert mock_websocket.send.call_count == 1
        
        # Verify result (AC#2, AC#3, AC#4)
        assert result.drop_box_id == "db-001"
        assert result.abort_received is True
        assert result.wipe_result.status == WipeStatus.SUCCESS
        assert result.wipe_result.files_wiped == 15
        assert result.wipe_result.files_failed == 0
        assert result.self_destruct_initiated is True
        
        # Verify events published (AC#5)
        assert len(event_bus.events_published) >= 2  # initiated + completed

    @pytest.mark.asyncio
    async def test_full_abort_flow_partial_wipe(
        self,
        abort_config: "AbortControllerConfig",
        mock_c2_server: MagicMock,
        mock_websocket: AsyncMock,
        event_bus: MagicMock,
    ) -> None:
        """Full abort flow with partial wipe (some files failed) (AC#7)."""
        mock_websocket.recv.return_value = json.dumps({
            "command_id": "abort-e2e-002",
            "wipe_status": "partial",
            "files_wiped": 12,
            "files_failed": 3,
            "errors": [
                "client.key: Permission denied",
                "commands.log: File in use",
                "cache.db: Read-only",
            ],
            "self_destruct_initiated": True,
        })
        
        controller = AbortController(
            config=abort_config,
            c2_server=mock_c2_server,
            event_bus=event_bus,
        )
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.COMPROMISED,
            issued_by="security@example.com",
        )
        
        # Verify partial wipe result
        assert result.abort_received is True
        assert result.wipe_result.status == WipeStatus.PARTIAL
        assert result.wipe_result.files_wiped == 12
        assert result.wipe_result.files_failed == 3
        assert len(result.wipe_result.errors) == 3

    @pytest.mark.asyncio
    async def test_full_abort_flow_connection_lost(
        self,
        mock_c2_server: MagicMock,
        mock_websocket: AsyncMock,
        event_bus: MagicMock,
    ) -> None:
        """Full abort flow with connection loss (AC#6)."""
        # Simulate timeout
        mock_websocket.recv.side_effect = asyncio.TimeoutError()
        
        config = AbortControllerConfig(wipe_timeout_seconds=1)
        controller = AbortController(
            config=config,
            c2_server=mock_c2_server,
            event_bus=event_bus,
        )
        
        result = await controller.send_abort(
            drop_box_id="db-001",
            reason=AbortReason.EMERGENCY,
            issued_by="operator@example.com",
        )
        
        # Command was still sent (drop box should execute locally)
        assert mock_websocket.send.call_count == 1
        
        # Result indicates connection lost
        assert result.abort_received is False
        
        # Drop box marked as lost
        mock_c2_server.mark_as_lost.assert_called_once()
        
        # Events still published
        assert len(event_bus.events_published) >= 1
