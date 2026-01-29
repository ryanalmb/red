"""Safety tests for Scope Editor Screen (Story 10.5).

Tests safety-critical behavior:
- Cannot remove scope with active agents (without force)
- Fail-closed on validation errors
- Audit logging cannot be bypassed
- Countdown cannot be skipped for production ranges

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
        ScopeChangeManager,
        ChangeResult,
    )
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False
    ScopeEditorScreen = None
    ChangeResult = None

from cyberred.tools.scope import ScopeValidator, ScopeConfig


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
    """Create scope configuration for safety tests."""
    return ScopeConfig(
        allowed_networks=[ip_network("192.168.1.0/24")],
        allowed_hostnames=["*.example.com"],
        allowed_ports=[22, 80, 443],
        allowed_protocols=["tcp"],
        allow_private=True,
        allow_loopback=False,
    )


@pytest.fixture
def scope_validator(scope_config: ScopeConfig) -> ScopeValidator:
    """Create scope validator for safety tests."""
    return ScopeValidator(scope_config)


@pytest.fixture
def mock_event_bus() -> MagicMock:
    """Create mock event bus."""
    bus = MagicMock()
    bus.publish = AsyncMock(return_value=1)
    bus.audit = AsyncMock(return_value="audit-id-123")
    return bus


# ─────────────────────────────────────────────────────────────────────────────
# Active Agent Protection Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestActiveAgentProtection:
    """Tests that scope removal is blocked when agents are active."""

    @pytest.mark.asyncio
    async def test_cannot_remove_network_with_active_agents(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test removing network with active agents is blocked."""
        mock_session = MagicMock()
        mock_session.get_agents_on_target = MagicMock(return_value=[
            {"agent_id": "agent-1", "status": "scanning"},
        ])
        
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=mock_event_bus,
            session_manager=mock_session,
        )
        
        result = await screen.remove_network("192.168.1.0/24")
        
        assert result.success is False
        assert result.blocked_by_agents is True
        # Network MUST still be in scope
        assert ip_network("192.168.1.0/24") in scope_validator.config.allowed_networks

    @pytest.mark.asyncio
    async def test_cannot_remove_hostname_with_active_agents(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test removing hostname with active agents is blocked."""
        mock_session = MagicMock()
        mock_session.get_agents_on_hostname = MagicMock(return_value=[
            {"agent_id": "agent-2", "status": "exploiting"},
        ])
        
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=mock_event_bus,
            session_manager=mock_session,
        )
        
        result = await screen.remove_hostname("*.example.com")
        
        assert result.success is False
        assert result.blocked_by_agents is True
        # Hostname MUST still be in scope
        assert "*.example.com" in scope_validator.config.allowed_hostnames

    @pytest.mark.asyncio
    async def test_force_remove_requires_explicit_flag(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test force removal requires explicit force=True flag."""
        mock_session = MagicMock()
        mock_session.get_agents_on_target = MagicMock(return_value=[
            {"agent_id": "agent-1", "status": "scanning"},
        ])
        
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=mock_event_bus,
            session_manager=mock_session,
        )
        
        # Without force flag - should fail
        result = await screen.remove_network("192.168.1.0/24")
        assert result.success is False
        
        # With force flag - should succeed (but log warning)
        result = await screen.remove_network("192.168.1.0/24", force=True)
        assert result.success is True


# ─────────────────────────────────────────────────────────────────────────────
# Fail-Closed Validation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFailClosedValidation:
    """Tests that validation errors result in fail-closed behavior."""

    @pytest.mark.asyncio
    async def test_invalid_cidr_rejected(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test invalid CIDR notation is rejected (fail-closed)."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=mock_event_bus,
        )
        
        result = await screen.add_network("invalid-network")
        
        assert result.success is False
        assert "invalid" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invalid_hostname_rejected(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test invalid hostname is rejected (fail-closed)."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=mock_event_bus,
        )
        
        result = await screen.add_hostname("-invalid-hostname")
        
        assert result.success is False

    @pytest.mark.asyncio
    async def test_invalid_port_rejected(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test invalid port is rejected (fail-closed)."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=mock_event_bus,
        )
        
        result = await screen.add_port(70000)  # Above max
        
        assert result.success is False

    @pytest.mark.asyncio
    async def test_exception_during_add_fails_closed(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test unexpected exception during add results in denial via change manager.
        
        The ScopeChangeManager.add_network method catches exceptions internally
        and returns ChangeResult(success=False), demonstrating fail-closed behavior.
        """
        manager = ScopeChangeManager(scope_validator)
        original_count = len(scope_validator.config.allowed_networks)
        
        # Force an exception by manipulating validator's config to cause an error
        # Test through the manager's exception handling in add_network
        result = manager.add_network("invalid-will-fail")
        
        assert result.success is False
        assert "invalid" in result.error.lower()
        # Original scope unchanged
        assert len(scope_validator.config.allowed_networks) == original_count


# ─────────────────────────────────────────────────────────────────────────────
# Audit Trail Enforcement Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditTrailEnforcement:
    """Tests that audit logging is mandatory and cannot be bypassed."""

    @pytest.mark.asyncio
    async def test_add_network_always_audited(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test adding network is always logged to audit trail."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=mock_event_bus,
        )
        
        await screen.add_network("172.16.0.0/16")
        
        # Audit must be called
        mock_event_bus.audit.assert_called()

    @pytest.mark.asyncio
    async def test_remove_network_always_audited(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test removing network is always logged to audit trail."""
        mock_session = MagicMock()
        mock_session.get_agents_on_target = MagicMock(return_value=[])
        
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=mock_event_bus,
            session_manager=mock_session,
        )
        
        await screen.remove_network("192.168.1.0/24")
        
        mock_event_bus.audit.assert_called()

    @pytest.mark.asyncio
    async def test_undo_always_audited(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test undo operations are always logged to audit trail."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=mock_event_bus,
        )
        
        await screen.add_network("172.16.0.0/16")
        mock_event_bus.audit.reset_mock()
        
        await screen.undo()
        
        mock_event_bus.audit.assert_called()

    @pytest.mark.asyncio
    async def test_audit_includes_operator(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test audit log includes operator identifier."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=mock_event_bus,
            operator="test_operator",
        )
        
        await screen.add_network("172.16.0.0/16")
        
        # Check audit call includes operator
        call_args = mock_event_bus.audit.call_args
        assert "test_operator" in str(call_args)

    @pytest.mark.asyncio
    async def test_audit_includes_timestamp(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test audit log includes timestamp."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=mock_event_bus,
        )
        
        await screen.add_network("172.16.0.0/16")
        
        # Check audit call includes timestamp
        call_args = mock_event_bus.audit.call_args
        assert "timestamp" in str(call_args).lower() or "time" in str(call_args).lower()


# ─────────────────────────────────────────────────────────────────────────────
# Countdown Enforcement Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCountdownEnforcement:
    """Tests that countdown cannot be skipped for production ranges."""

    @pytest.mark.asyncio
    async def test_production_range_requires_countdown(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test production range addition requires countdown."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=mock_event_bus,
        )
        
        # Try to add public/production range
        result = await screen.add_network("8.8.8.0/24")
        
        # Should require countdown confirmation
        assert result.countdown_required is True
        # Should NOT be added yet
        assert ip_network("8.8.8.0/24") not in scope_validator.config.allowed_networks

    @pytest.mark.asyncio
    async def test_countdown_cannot_be_bypassed(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test countdown cannot be bypassed for production ranges."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=mock_event_bus,
        )
        
        # Try to bypass countdown with skip_countdown flag
        # This should NOT work for production ranges
        result = await screen.add_network("8.8.8.0/24", skip_countdown=True)
        
        # Even with skip flag, production ranges MUST countdown
        assert result.countdown_required is True

    @pytest.mark.asyncio
    async def test_private_range_can_skip_countdown(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test private ranges do NOT require countdown."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=mock_event_bus,
        )
        
        result = await screen.add_network("172.16.0.0/16")
        
        # Private range should apply immediately
        assert result.countdown_required is False
        assert result.success is True

    @pytest.mark.asyncio
    async def test_countdown_can_be_cancelled(
        self, scope_validator: ScopeValidator, mock_event_bus: MagicMock
    ):
        """Test countdown can be cancelled before completion."""
        screen = ScopeEditorScreen(
            validator=scope_validator,
            event_bus=mock_event_bus,
        )
        
        # Start countdown for production range
        result = await screen.add_network("8.8.8.0/24")
        assert result.countdown_required is True
        
        # Cancel during countdown
        cancel_result = await screen.cancel_pending_change()
        
        assert cancel_result.success is True
        # Network should NOT be added
        assert ip_network("8.8.8.0/24") not in scope_validator.config.allowed_networks
