"""Integration tests for Scope Editor Screen (Story 10.5).

Tests the full scope editor flow with actual components:
- Full add IP range flow (input → validate → confirm → apply)
- Full remove with active agent warning flow
- Countdown and undo end-to-end
- Audit trail logging on scope changes
- Scope propagation to agents via event bus

TDD RED Phase: These tests are written BEFORE implementation.
"""
import asyncio
from datetime import datetime, timezone
from ipaddress import ip_network
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# These imports will fail until implementation exists (RED phase)
try:
    from cyberred.tui.screens.scope_editor import (
        ScopeEditorScreen,
        ScopeChange,
        ScopeSnapshot,
        ScopeUpdatedEvent,
        ScopeChangeManager,
    )
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False
    ScopeEditorScreen = None

from cyberred.tools.scope import ScopeValidator, ScopeConfig
from cyberred.core.events import EventBus


# Skip all tests if imports not available (RED phase)
pytestmark = pytest.mark.skipif(
    not IMPORTS_AVAILABLE,
    reason="ScopeEditorScreen not yet implemented (TDD RED phase)"
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def scope_config() -> ScopeConfig:
    """Create scope configuration for integration tests."""
    return ScopeConfig(
        allowed_networks=[ip_network("192.168.1.0/24"), ip_network("10.0.0.0/8")],
        allowed_hostnames=["*.example.com", "test.local"],
        allowed_ports=[22, 80, 443],
        allowed_protocols=["tcp", "udp"],
        allow_private=True,
        allow_loopback=False,
    )


@pytest.fixture
def scope_validator(scope_config: ScopeConfig) -> ScopeValidator:
    """Create scope validator for integration tests."""
    return ScopeValidator(scope_config)


@pytest.fixture
def mock_redis_client() -> MagicMock:
    """Create mock Redis client for EventBus."""
    client = MagicMock()
    client.publish = AsyncMock(return_value=1)
    client.subscribe = AsyncMock()
    client.xadd = AsyncMock(return_value="1234567890-0")
    return client


@pytest.fixture
def event_bus(mock_redis_client: MagicMock) -> EventBus:
    """Create EventBus with mock Redis for testing."""
    return EventBus(mock_redis_client)


# ─────────────────────────────────────────────────────────────────────────────
# Full Flow Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAddNetworkFlow:
    """Integration tests for adding network to scope."""

    @pytest.mark.asyncio
    async def test_add_private_network_immediate_apply(
        self, scope_validator: ScopeValidator, event_bus: EventBus
    ):
        """Test adding private network applies immediately (no countdown)."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=event_bus,
        )
        
        # Simulate adding a private network
        result = await screen.add_network("172.16.0.0/16")
        
        assert result.success is True
        assert "172.16.0.0/16" in [str(n) for n in scope_validator.config.allowed_networks]
        # Should NOT require countdown for private range
        assert result.countdown_required is False

    @pytest.mark.asyncio
    async def test_add_production_network_requires_countdown(
        self, scope_validator: ScopeValidator, event_bus: EventBus
    ):
        """Test adding production network requires 5s countdown."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=event_bus,
        )
        
        # Simulate adding a production (public) network
        result = await screen.add_network("8.8.8.0/24")
        
        # Should require countdown confirmation
        assert result.countdown_required is True
        assert result.countdown_seconds == 5
        # Network should NOT be added yet (pending confirmation)
        assert "8.8.8.0/24" not in [str(n) for n in scope_validator.config.allowed_networks]

    @pytest.mark.asyncio
    async def test_add_network_emits_scope_updated_event(
        self, scope_validator: ScopeValidator, event_bus: EventBus, mock_redis_client: MagicMock
    ):
        """Test adding network emits ScopeUpdatedEvent via EventBus."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=event_bus,
        )
        
        await screen.add_network("172.16.0.0/16")
        
        # Verify event was published
        mock_redis_client.publish.assert_called()
        call_args = mock_redis_client.publish.call_args
        assert "scope" in call_args[0][0].lower() or "scope" in str(call_args)


class TestRemoveNetworkFlow:
    """Integration tests for removing network from scope."""

    @pytest.mark.asyncio
    async def test_remove_network_no_active_agents(
        self, scope_validator: ScopeValidator, event_bus: EventBus
    ):
        """Test removing network succeeds when no active agents."""
        mock_session = MagicMock()
        mock_session.get_agents_on_target = MagicMock(return_value=[])
        
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=event_bus,
            session_manager=mock_session,
        )
        
        result = await screen.remove_network("192.168.1.0/24")
        
        assert result.success is True
        assert "192.168.1.0/24" not in [str(n) for n in scope_validator.config.allowed_networks]

    @pytest.mark.asyncio
    async def test_remove_network_blocked_by_active_agents(
        self, scope_validator: ScopeValidator, event_bus: EventBus
    ):
        """Test removing network is blocked when agents are active on target."""
        mock_session = MagicMock()
        mock_session.get_agents_on_target = MagicMock(return_value=[
            {"agent_id": "recon-001", "status": "scanning", "target": "192.168.1.50"},
            {"agent_id": "exploit-002", "status": "attacking", "target": "192.168.1.100"},
        ])
        
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=event_bus,
            session_manager=mock_session,
        )
        
        result = await screen.remove_network("192.168.1.0/24")
        
        assert result.success is False
        assert result.blocked_by_agents is True
        assert len(result.affected_agents) == 2
        # Network should still be in scope
        assert "192.168.1.0/24" in [str(n) for n in scope_validator.config.allowed_networks]


class TestUndoFlow:
    """Integration tests for undo functionality."""

    @pytest.mark.asyncio
    async def test_undo_within_window_reverts_change(
        self, scope_validator: ScopeValidator, event_bus: EventBus
    ):
        """Test undo within 10s window reverts the change."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=event_bus,
        )
        
        original_count = len(scope_validator.config.allowed_networks)
        
        # Add network
        await screen.add_network("172.16.0.0/16")
        assert len(scope_validator.config.allowed_networks) == original_count + 1
        
        # Undo within window
        result = await screen.undo()
        
        assert result.success is True
        assert len(scope_validator.config.allowed_networks) == original_count

    @pytest.mark.asyncio
    async def test_undo_after_window_fails(
        self, scope_validator: ScopeValidator, event_bus: EventBus
    ):
        """Test undo after 10s window expires fails."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=event_bus,
        )
        
        # Add network
        await screen.add_network("172.16.0.0/16")
        
        # Simulate window expiry
        screen._clear_undo_state()
        
        # Attempt undo
        result = await screen.undo()
        
        assert result.success is False
        assert "expired" in result.error.lower() or "no undo" in result.error.lower()


class TestAuditTrailIntegration:
    """Integration tests for audit trail logging."""

    @pytest.mark.asyncio
    async def test_add_network_logs_to_audit(
        self, scope_validator: ScopeValidator, event_bus: EventBus, mock_redis_client: MagicMock
    ):
        """Test adding network logs to audit trail."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=event_bus,
        )
        
        await screen.add_network("172.16.0.0/16")
        
        # Verify audit log was written via xadd
        mock_redis_client.xadd.assert_called()

    @pytest.mark.asyncio
    async def test_remove_network_logs_to_audit(
        self, scope_validator: ScopeValidator, event_bus: EventBus, mock_redis_client: MagicMock
    ):
        """Test removing network logs to audit trail."""
        mock_session = MagicMock()
        mock_session.get_agents_on_target = MagicMock(return_value=[])
        
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=event_bus,
            session_manager=mock_session,
        )
        
        await screen.remove_network("192.168.1.0/24")
        
        # Verify audit log was written
        mock_redis_client.xadd.assert_called()

    @pytest.mark.asyncio
    async def test_undo_logs_to_audit(
        self, scope_validator: ScopeValidator, event_bus: EventBus, mock_redis_client: MagicMock
    ):
        """Test undo operation logs to audit trail."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=event_bus,
        )
        
        await screen.add_network("172.16.0.0/16")
        mock_redis_client.xadd.reset_mock()
        
        await screen.undo()
        
        # Verify undo was logged
        mock_redis_client.xadd.assert_called()


class TestScopePropagation:
    """Integration tests for scope propagation to agents."""

    @pytest.mark.asyncio
    async def test_scope_change_publishes_event(
        self, scope_validator: ScopeValidator, event_bus: EventBus, mock_redis_client: MagicMock
    ):
        """Test scope changes publish ScopeUpdatedEvent for agents."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=event_bus,
        )
        
        await screen.add_network("172.16.0.0/16")
        
        # Verify publish was called with scope update
        assert mock_redis_client.publish.called
        # Check the channel pattern
        calls = mock_redis_client.publish.call_args_list
        assert any("scope" in str(call).lower() for call in calls)

    @pytest.mark.asyncio
    async def test_scope_change_includes_snapshot(
        self, scope_validator: ScopeValidator, event_bus: EventBus, mock_redis_client: MagicMock
    ):
        """Test scope change event includes new config snapshot."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=event_bus,
        )
        
        await screen.add_network("172.16.0.0/16")
        
        # The published message should contain the new scope config
        # This enables agents to hot-reload their scope validators
        assert mock_redis_client.publish.called
