"""Unit tests for Scope Editor Screen (Story 10.5).

Tests the ScopeEditorScreen with:
- Screen initialization with current ScopeConfig
- Input validation for IP ranges, hostnames, and ports
- Add/remove operations
- Countdown confirmation for production ranges
- Undo window functionality
- F8 keybinding access

TDD RED Phase: These tests are written BEFORE implementation.
"""
import asyncio
import time
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
        ChangeResult,
        is_production_range,
        validate_cidr,
        validate_hostname,
        validate_port_range,
    )
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False
    ChangeResult = None
    # Create placeholder classes for test collection
    ScopeEditorScreen = None
    ScopeChange = None
    ScopeSnapshot = None
    ScopeUpdatedEvent = None
    ScopeChangeManager = None

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
def sample_scope_config() -> ScopeConfig:
    """Create a sample scope configuration for testing."""
    return ScopeConfig(
        allowed_networks=[ip_network("192.168.1.0/24"), ip_network("10.0.0.0/8")],
        allowed_hostnames=["*.example.com", "test.local"],
        allowed_ports=[22, 80, 443, (8000, 8100)],
        allowed_protocols=["tcp", "udp"],
        allow_private=True,
        allow_loopback=False,
    )


@pytest.fixture
def sample_scope_validator(sample_scope_config: ScopeConfig) -> ScopeValidator:
    """Create a sample scope validator for testing."""
    return ScopeValidator(sample_scope_config)


@pytest.fixture
def mock_session_manager() -> MagicMock:
    """Create a mock session manager for active agent queries."""
    manager = MagicMock()
    manager.get_agents_on_target = MagicMock(return_value=[])
    return manager


@pytest.fixture
def mock_event_bus() -> MagicMock:
    """Create a mock event bus for scope propagation."""
    bus = MagicMock()
    bus.publish = AsyncMock(return_value=1)
    return bus


# ─────────────────────────────────────────────────────────────────────────────
# Validation Function Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateCidr:
    """Tests for CIDR notation validation."""

    def test_valid_ipv4_cidr(self):
        """Test valid IPv4 CIDR notation."""
        assert validate_cidr("192.168.1.0/24") is True
        assert validate_cidr("10.0.0.0/8") is True
        assert validate_cidr("172.16.0.0/12") is True

    def test_valid_ipv4_single_host(self):
        """Test valid IPv4 single host (no prefix)."""
        assert validate_cidr("192.168.1.100") is True
        assert validate_cidr("10.0.0.1") is True

    def test_valid_ipv6_cidr(self):
        """Test valid IPv6 CIDR notation."""
        assert validate_cidr("2001:db8::/32") is True
        assert validate_cidr("fe80::/10") is True

    def test_invalid_cidr(self):
        """Test invalid CIDR notation."""
        assert validate_cidr("192.168.1.0/33") is False  # Invalid prefix
        assert validate_cidr("256.256.256.256") is False  # Invalid octet
        assert validate_cidr("not-an-ip") is False
        assert validate_cidr("") is False
        assert validate_cidr("192.168.1") is False  # Incomplete


class TestValidateHostname:
    """Tests for hostname validation."""

    def test_valid_exact_hostname(self):
        """Test valid exact hostnames."""
        assert validate_hostname("example.com") is True
        assert validate_hostname("test.local") is True
        assert validate_hostname("server-01.example.com") is True

    def test_valid_wildcard_hostname(self):
        """Test valid wildcard hostname patterns."""
        assert validate_hostname("*.example.com") is True
        assert validate_hostname("*.test.local") is True

    def test_invalid_hostname(self):
        """Test invalid hostname patterns."""
        assert validate_hostname("") is False
        assert validate_hostname("-invalid.com") is False  # Starts with hyphen
        assert validate_hostname("invalid-.com") is False  # Ends with hyphen
        assert validate_hostname("*.") is False  # Wildcard only
        assert validate_hostname("*") is False  # Just asterisk


class TestValidatePortRange:
    """Tests for port range validation."""

    def test_valid_single_port(self):
        """Test valid single port numbers."""
        assert validate_port_range("80") is True
        assert validate_port_range("443") is True
        assert validate_port_range("1") is True
        assert validate_port_range("65535") is True

    def test_valid_port_range(self):
        """Test valid port range format."""
        assert validate_port_range("80-443") is True
        assert validate_port_range("8000-8100") is True
        assert validate_port_range("1-65535") is True

    def test_invalid_port(self):
        """Test invalid port specifications."""
        assert validate_port_range("0") is False  # Below minimum
        assert validate_port_range("65536") is False  # Above maximum
        assert validate_port_range("-1") is False  # Negative
        assert validate_port_range("abc") is False  # Non-numeric
        assert validate_port_range("") is False
        assert validate_port_range("443-80") is False  # End < start


class TestIsProductionRange:
    """Tests for production range detection."""

    def test_private_ranges_not_production(self):
        """Test RFC 1918 private ranges are NOT production."""
        assert is_production_range("192.168.1.0/24") is False
        assert is_production_range("10.0.0.0/8") is False
        assert is_production_range("172.16.0.0/12") is False

    def test_documentation_ranges_not_production(self):
        """Test documentation ranges are NOT production."""
        assert is_production_range("192.0.2.0/24") is False  # TEST-NET-1
        assert is_production_range("198.51.100.0/24") is False  # TEST-NET-2
        assert is_production_range("203.0.113.0/24") is False  # TEST-NET-3
        assert is_production_range("2001:db8::/32") is False  # IPv6 doc

    def test_public_ranges_are_production(self):
        """Test public ranges ARE production."""
        assert is_production_range("8.8.8.0/24") is True  # Google DNS
        assert is_production_range("1.1.1.0/24") is True  # Cloudflare


# ─────────────────────────────────────────────────────────────────────────────
# ScopeChange Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestScopeChange:
    """Tests for ScopeChange dataclass."""

    def test_create_add_network_change(self):
        """Test creating an add network scope change."""
        change = ScopeChange(
            change_type="add",
            category="network",
            value="192.168.2.0/24",
            timestamp=datetime.now(timezone.utc).isoformat(),
            operator="test_operator",
            is_production=False,
        )
        assert change.change_type == "add"
        assert change.category == "network"
        assert change.value == "192.168.2.0/24"
        assert change.is_production is False

    def test_create_remove_hostname_change(self):
        """Test creating a remove hostname scope change."""
        change = ScopeChange(
            change_type="remove",
            category="hostname",
            value="*.example.com",
            timestamp=datetime.now(timezone.utc).isoformat(),
            operator="test_operator",
            is_production=False,
        )
        assert change.change_type == "remove"
        assert change.category == "hostname"


# ─────────────────────────────────────────────────────────────────────────────
# ScopeSnapshot Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestScopeSnapshot:
    """Tests for ScopeSnapshot dataclass."""

    def test_create_snapshot(self, sample_scope_config: ScopeConfig):
        """Test creating a scope snapshot."""
        snapshot = ScopeSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            networks=["192.168.1.0/24", "10.0.0.0/8"],
            hostnames=["*.example.com", "test.local"],
            ports=[22, 80, 443, (8000, 8100)],
            allow_private=True,
            allow_loopback=False,
        )
        assert len(snapshot.networks) == 2
        assert len(snapshot.hostnames) == 2
        assert len(snapshot.ports) == 4

    def test_snapshot_from_config(self, sample_scope_config: ScopeConfig):
        """Test creating snapshot from ScopeConfig."""
        snapshot = ScopeSnapshot.from_config(sample_scope_config)
        assert snapshot.allow_private == sample_scope_config.allow_private
        assert snapshot.allow_loopback == sample_scope_config.allow_loopback


# ─────────────────────────────────────────────────────────────────────────────
# ScopeChangeManager Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestScopeChangeManager:
    """Tests for ScopeChangeManager."""

    def test_init_with_validator(self, sample_scope_validator: ScopeValidator):
        """Test initializing manager with validator."""
        manager = ScopeChangeManager(sample_scope_validator)
        assert manager.validator is sample_scope_validator

    def test_add_network_success(self, sample_scope_validator: ScopeValidator):
        """Test successfully adding a network."""
        manager = ScopeChangeManager(sample_scope_validator)
        result = manager.add_network("172.16.0.0/16")
        assert result.success is True
        assert "172.16.0.0/16" in [str(n) for n in manager.validator.config.allowed_networks]

    def test_add_network_invalid_format(self, sample_scope_validator: ScopeValidator):
        """Test adding invalid network format fails."""
        manager = ScopeChangeManager(sample_scope_validator)
        result = manager.add_network("invalid-network")
        assert result.success is False
        assert "invalid" in result.error.lower()

    def test_remove_network_success(self, sample_scope_validator: ScopeValidator):
        """Test successfully removing a network."""
        manager = ScopeChangeManager(sample_scope_validator)
        result = manager.remove_network("192.168.1.0/24")
        assert result.success is True
        assert "192.168.1.0/24" not in [str(n) for n in manager.validator.config.allowed_networks]

    def test_remove_network_with_active_agents_blocked(
        self, sample_scope_validator: ScopeValidator, mock_session_manager: MagicMock
    ):
        """Test removing network with active agents is blocked."""
        mock_session_manager.get_agents_on_target.return_value = [
            {"agent_id": "agent-1", "target": "192.168.1.50"},
            {"agent_id": "agent-2", "target": "192.168.1.100"},
        ]
        manager = ScopeChangeManager(
            sample_scope_validator, 
            session_manager=mock_session_manager
        )
        result = manager.remove_network("192.168.1.0/24")
        assert result.success is False
        assert result.blocked_by_agents is True
        assert len(result.affected_agents) == 2

    def test_add_hostname_success(self, sample_scope_validator: ScopeValidator):
        """Test successfully adding a hostname."""
        manager = ScopeChangeManager(sample_scope_validator)
        result = manager.add_hostname("*.newdomain.com")
        assert result.success is True
        assert "*.newdomain.com" in manager.validator.config.allowed_hostnames

    def test_add_port_single(self, sample_scope_validator: ScopeValidator):
        """Test adding a single port."""
        manager = ScopeChangeManager(sample_scope_validator)
        result = manager.add_port(8443)
        assert result.success is True
        assert 8443 in manager.validator.config.allowed_ports

    def test_add_port_range(self, sample_scope_validator: ScopeValidator):
        """Test adding a port range."""
        manager = ScopeChangeManager(sample_scope_validator)
        result = manager.add_port((9000, 9100))
        assert result.success is True
        assert (9000, 9100) in manager.validator.config.allowed_ports

    def test_get_snapshot(self, sample_scope_validator: ScopeValidator):
        """Test getting config snapshot for undo."""
        manager = ScopeChangeManager(sample_scope_validator)
        snapshot = manager.get_snapshot()
        assert isinstance(snapshot, ScopeSnapshot)
        assert len(snapshot.networks) == 2

    def test_restore_snapshot(self, sample_scope_validator: ScopeValidator):
        """Test restoring from snapshot (undo)."""
        manager = ScopeChangeManager(sample_scope_validator)
        
        # Get initial snapshot
        original_snapshot = manager.get_snapshot()
        
        # Make changes
        manager.add_network("172.16.0.0/16")
        assert len(manager.validator.config.allowed_networks) == 3
        
        # Restore
        manager.restore_snapshot(original_snapshot)
        assert len(manager.validator.config.allowed_networks) == 2

    def test_countdown_required_for_production(self, sample_scope_validator: ScopeValidator):
        """Test countdown is required for production ranges."""
        manager = ScopeChangeManager(sample_scope_validator)
        assert manager.requires_countdown("8.8.8.0/24") is True  # Public
        assert manager.requires_countdown("192.168.1.0/24") is False  # Private


# ─────────────────────────────────────────────────────────────────────────────
# ScopeEditorScreen Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestScopeEditorScreen:
    """Tests for ScopeEditorScreen."""

    @pytest.fixture
    def screen(self, sample_scope_validator: ScopeValidator) -> ScopeEditorScreen:
        """Create a scope editor screen for testing."""
        return ScopeEditorScreen(validator=sample_scope_validator)

    def test_screen_initialization(self, screen: ScopeEditorScreen):
        """Test screen initializes with current scope config."""
        assert screen.validator is not None
        assert screen._change_manager is not None

    def test_screen_has_change_manager(self, screen: ScopeEditorScreen):
        """Test screen has properly initialized change manager."""
        assert screen._change_manager is not None
        assert screen._change_manager.validator is screen.validator

    def test_screen_bindings_include_escape(self):
        """Test ESC keybinding is configured for closing."""
        bindings = ScopeEditorScreen.BINDINGS
        binding_keys = [b.key if hasattr(b, 'key') else b[0] for b in bindings]
        # Screen should have ESC to close
        assert any("escape" in str(k).lower() for k in binding_keys)


class TestScopeEditorScreenValidation:
    """Tests for input validation in ScopeEditorScreen."""

    @pytest.fixture
    def screen(self, sample_scope_validator: ScopeValidator) -> ScopeEditorScreen:
        """Create a scope editor screen for testing."""
        return ScopeEditorScreen(validator=sample_scope_validator)

    def test_validate_network_input_valid(self, screen: ScopeEditorScreen):
        """Test valid network input passes validation."""
        assert screen._validate_network_input("192.168.2.0/24") is True
        assert screen._validate_network_input("10.0.0.1") is True

    def test_validate_network_input_invalid(self, screen: ScopeEditorScreen):
        """Test invalid network input fails validation."""
        assert screen._validate_network_input("invalid") is False
        assert screen._validate_network_input("") is False

    def test_validate_hostname_input_valid(self, screen: ScopeEditorScreen):
        """Test valid hostname input passes validation."""
        assert screen._validate_hostname_input("test.example.com") is True
        assert screen._validate_hostname_input("*.example.com") is True

    def test_validate_hostname_input_invalid(self, screen: ScopeEditorScreen):
        """Test invalid hostname input fails validation."""
        assert screen._validate_hostname_input("") is False
        assert screen._validate_hostname_input("-invalid.com") is False

    def test_validate_port_input_valid(self, screen: ScopeEditorScreen):
        """Test valid port input passes validation."""
        assert screen._validate_port_input("443") is True
        assert screen._validate_port_input("8000-8100") is True

    def test_validate_port_input_invalid(self, screen: ScopeEditorScreen):
        """Test invalid port input fails validation."""
        assert screen._validate_port_input("0") is False
        assert screen._validate_port_input("70000") is False
        assert screen._validate_port_input("abc") is False


class TestScopeEditorScreenCountdown:
    """Tests for countdown confirmation functionality."""

    @pytest.fixture
    def screen(self, sample_scope_validator: ScopeValidator) -> ScopeEditorScreen:
        """Create a scope editor screen for testing."""
        return ScopeEditorScreen(validator=sample_scope_validator)

    def test_countdown_triggered_for_production(self, screen: ScopeEditorScreen):
        """Test countdown is triggered for production ranges."""
        # Mock the internal state to check countdown triggering
        screen._pending_change = ScopeChange(
            change_type="add",
            category="network",
            value="8.8.8.0/24",  # Public/production
            timestamp=datetime.now(timezone.utc).isoformat(),
            operator="test",
            is_production=True,
        )
        assert screen._should_show_countdown() is True

    def test_countdown_not_triggered_for_private(self, screen: ScopeEditorScreen):
        """Test countdown is NOT triggered for private ranges."""
        screen._pending_change = ScopeChange(
            change_type="add",
            category="network",
            value="192.168.2.0/24",  # Private
            timestamp=datetime.now(timezone.utc).isoformat(),
            operator="test",
            is_production=False,
        )
        assert screen._should_show_countdown() is False

    def test_countdown_duration_is_5_seconds(self, screen: ScopeEditorScreen):
        """Test countdown duration is 5 seconds per spec."""
        assert screen.COUNTDOWN_SECONDS == 5


class TestScopeEditorScreenUndo:
    """Tests for undo window functionality."""

    @pytest.fixture
    def screen(self, sample_scope_validator: ScopeValidator) -> ScopeEditorScreen:
        """Create a scope editor screen for testing."""
        return ScopeEditorScreen(validator=sample_scope_validator)

    def test_undo_window_duration_is_10_seconds(self, screen: ScopeEditorScreen):
        """Test undo window is 10 seconds per spec."""
        assert screen.UNDO_WINDOW_SECONDS == 10

    def test_undo_stores_previous_state_via_manager(self, screen: ScopeEditorScreen):
        """Test undo stores previous state before change via change manager."""
        original_networks = len(screen.validator.config.allowed_networks)
        
        # Get snapshot before change
        snapshot = screen._change_manager.get_snapshot()
        
        # Apply change through manager
        screen._change_manager.add_network("172.16.0.0/16")
        
        # Verify original snapshot has correct count
        assert len(snapshot.networks) == original_networks

    def test_undo_reverts_change_via_manager(self, screen: ScopeEditorScreen):
        """Test undo reverts the last change via manager."""
        original_count = len(screen.validator.config.allowed_networks)
        
        # Get snapshot before change
        snapshot = screen._change_manager.get_snapshot()
        
        # Apply change
        screen._change_manager.add_network("172.16.0.0/16")
        assert len(screen.validator.config.allowed_networks) == original_count + 1
        
        # Undo via restore
        screen._change_manager.restore_snapshot(snapshot)
        assert len(screen.validator.config.allowed_networks) == original_count

    def test_undo_clears_state(self, screen: ScopeEditorScreen):
        """Test undo state clears properly."""
        # Set up undo state manually
        screen._undo_snapshot = screen._change_manager.get_snapshot()
        screen._can_undo = True
        
        # Clear undo state
        screen._clear_undo_state()
        assert screen._undo_snapshot is None
        assert screen._can_undo is False


# ─────────────────────────────────────────────────────────────────────────────
# Additional Coverage Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidationEdgeCases:
    """Additional validation edge case tests."""

    def test_validate_cidr_whitespace(self):
        """Test CIDR validation handles whitespace."""
        assert validate_cidr("  192.168.1.0/24  ") is True

    def test_validate_hostname_uppercase(self):
        """Test hostname validation normalizes to lowercase."""
        assert validate_hostname("EXAMPLE.COM") is True
        assert validate_hostname("*.EXAMPLE.COM") is True

    def test_validate_hostname_single_label(self):
        """Test single label hostname."""
        assert validate_hostname("localhost") is True

    def test_validate_port_whitespace(self):
        """Test port validation handles whitespace."""
        assert validate_port_range("  80  ") is True
        assert validate_port_range("  8000-8100  ") is True

    def test_is_production_invalid_returns_true(self):
        """Test invalid network returns True (fail-closed)."""
        # Invalid networks should be treated as production (fail-closed)
        assert is_production_range("invalid") is True


class TestScopeChangeManagerEdgeCases:
    """Additional ScopeChangeManager edge case tests."""

    @pytest.fixture
    def manager(self, sample_scope_validator: ScopeValidator) -> ScopeChangeManager:
        """Create scope change manager for testing."""
        return ScopeChangeManager(sample_scope_validator)

    def test_add_duplicate_network(self, manager: ScopeChangeManager):
        """Test adding duplicate network is idempotent."""
        initial_count = len(manager.validator.config.allowed_networks)
        manager.add_network("192.168.1.0/24")  # Already exists
        assert len(manager.validator.config.allowed_networks) == initial_count

    def test_add_duplicate_hostname(self, manager: ScopeChangeManager):
        """Test adding duplicate hostname is idempotent."""
        manager.add_hostname("new.example.com")
        count_after_first = len(manager.validator.config.allowed_hostnames)
        manager.add_hostname("new.example.com")
        assert len(manager.validator.config.allowed_hostnames) == count_after_first

    def test_add_duplicate_port(self, manager: ScopeChangeManager):
        """Test adding duplicate port is idempotent."""
        manager.add_port(8080)
        count_after_first = len(manager.validator.config.allowed_ports)
        manager.add_port(8080)
        assert len(manager.validator.config.allowed_ports) == count_after_first

    def test_remove_nonexistent_network(self, manager: ScopeChangeManager):
        """Test removing non-existent network succeeds."""
        result = manager.remove_network("1.2.3.0/24")
        assert result.success is True

    def test_remove_nonexistent_hostname(self, manager: ScopeChangeManager):
        """Test removing non-existent hostname succeeds."""
        result = manager.remove_hostname("nonexistent.com")
        assert result.success is True

    def test_remove_port_no_ports_configured(self, sample_scope_config: ScopeConfig):
        """Test removing port when no ports configured."""
        config = ScopeConfig(
            allowed_networks=sample_scope_config.allowed_networks,
            allowed_hostnames=sample_scope_config.allowed_hostnames,
            allowed_ports=None,  # No ports
        )
        validator = ScopeValidator(config)
        manager = ScopeChangeManager(validator)
        result = manager.remove_port(80)
        assert result.success is False
        assert "No ports" in result.error

    def test_add_port_invalid_range_end_less_than_start(self, manager: ScopeChangeManager):
        """Test adding port range where end < start fails."""
        result = manager.add_port((8100, 8000))  # Invalid: end < start
        assert result.success is False

    def test_add_port_invalid_type(self, manager: ScopeChangeManager):
        """Test adding port with invalid type fails."""
        result = manager.add_port("not-a-port")  # type: ignore
        assert result.success is False


class TestScopeSnapshotMethods:
    """Tests for ScopeSnapshot methods."""

    def test_snapshot_from_config_with_none_ports(self):
        """Test snapshot creation when ports is None."""
        config = ScopeConfig(
            allowed_networks=[ip_network("192.168.1.0/24")],
            allowed_hostnames=["test.com"],
            allowed_ports=None,
        )
        snapshot = ScopeSnapshot.from_config(config)
        assert snapshot.ports == []

    def test_snapshot_preserves_all_fields(self, sample_scope_config: ScopeConfig):
        """Test snapshot preserves all config fields."""
        snapshot = ScopeSnapshot.from_config(sample_scope_config)
        assert snapshot.allow_private == sample_scope_config.allow_private
        assert snapshot.allow_loopback == sample_scope_config.allow_loopback
        assert len(snapshot.networks) == len(sample_scope_config.allowed_networks)
        assert len(snapshot.hostnames) == len(sample_scope_config.allowed_hostnames)


class TestChangeResult:
    """Tests for ChangeResult dataclass."""

    def test_change_result_defaults(self):
        """Test ChangeResult has correct defaults."""
        result = ChangeResult()
        assert result.success is False
        assert result.error == ""
        assert result.countdown_required is False
        assert result.countdown_seconds == 0
        assert result.blocked_by_agents is False
        assert result.affected_agents == []

    def test_change_result_with_agents(self):
        """Test ChangeResult with affected agents."""
        result = ChangeResult(
            success=False,
            blocked_by_agents=True,
            affected_agents=[{"agent_id": "a1"}, {"agent_id": "a2"}],
        )
        assert len(result.affected_agents) == 2


class TestScopeEditorConstants:
    """Tests for ScopeEditorScreen constants."""

    def test_countdown_seconds_value(self):
        """Test COUNTDOWN_SECONDS is 5."""
        assert ScopeEditorScreen.COUNTDOWN_SECONDS == 5

    def test_undo_window_seconds_value(self):
        """Test UNDO_WINDOW_SECONDS is 10."""
        assert ScopeEditorScreen.UNDO_WINDOW_SECONDS == 10

    def test_screen_has_title(self):
        """Test screen has TITLE defined."""
        assert ScopeEditorScreen.TITLE == "Scope Editor"

    def test_screen_has_css(self):
        """Test screen has DEFAULT_CSS defined."""
        assert ScopeEditorScreen.DEFAULT_CSS is not None
        assert "scope-container" in ScopeEditorScreen.DEFAULT_CSS


class TestScopeUpdatedEvent:
    """Tests for ScopeUpdatedEvent dataclass."""

    def test_create_scope_updated_event(self, sample_scope_config: ScopeConfig):
        """Test creating ScopeUpdatedEvent."""
        change = ScopeChange(
            change_type="add",
            category="network",
            value="172.16.0.0/16",
            timestamp="2026-01-29T00:00:00Z",
            operator="test",
            is_production=False,
        )
        snapshot = ScopeSnapshot.from_config(sample_scope_config)
        event = ScopeUpdatedEvent(
            change=change,
            new_config=snapshot,
            previous_config=snapshot,
        )
        assert event.change.value == "172.16.0.0/16"
        assert event.new_config is not None


# ─────────────────────────────────────────────────────────────────────────────
# Async Method Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestScopeEditorAsyncMethods:
    """Tests for ScopeEditorScreen async methods."""

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        """Create a mock event bus."""
        bus = MagicMock()
        bus.publish = AsyncMock(return_value=1)
        bus.audit = AsyncMock(return_value="audit-id")
        return bus

    @pytest.fixture
    def screen(self, sample_scope_validator: ScopeValidator, mock_event_bus: MagicMock) -> ScopeEditorScreen:
        """Create scope editor screen for testing."""
        return ScopeEditorScreen(
            validator=sample_scope_validator,
            event_bus=mock_event_bus,
            operator="test_operator",
        )

    @pytest.mark.asyncio
    async def test_add_network_private_success(self, screen: ScopeEditorScreen):
        """Test adding private network succeeds immediately."""
        result = await screen.add_network("172.16.0.0/16")
        assert result.success is True
        assert result.countdown_required is False

    @pytest.mark.asyncio
    async def test_add_network_production_requires_countdown(self, screen: ScopeEditorScreen):
        """Test adding production network requires countdown."""
        result = await screen.add_network("8.8.8.0/24")
        assert result.countdown_required is True
        assert result.countdown_seconds == 5

    @pytest.mark.asyncio
    async def test_add_network_invalid_fails(self, screen: ScopeEditorScreen):
        """Test adding invalid network fails."""
        result = await screen.add_network("invalid-network")
        assert result.success is False
        assert "invalid" in result.error.lower()

    @pytest.mark.asyncio
    async def test_remove_network_success(self, screen: ScopeEditorScreen):
        """Test removing network succeeds."""
        result = await screen.remove_network("192.168.1.0/24")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_remove_network_invalid_fails(self, screen: ScopeEditorScreen):
        """Test removing invalid network fails."""
        result = await screen.remove_network("invalid")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_add_hostname_success(self, screen: ScopeEditorScreen):
        """Test adding hostname succeeds."""
        result = await screen.add_hostname("new.example.com")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_add_hostname_invalid_fails(self, screen: ScopeEditorScreen):
        """Test adding invalid hostname fails."""
        result = await screen.add_hostname("-invalid")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_remove_hostname_success(self, screen: ScopeEditorScreen):
        """Test removing hostname succeeds."""
        result = await screen.remove_hostname("*.example.com")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_add_port_string_success(self, screen: ScopeEditorScreen):
        """Test adding port as string succeeds."""
        result = await screen.add_port("8443")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_add_port_range_string_success(self, screen: ScopeEditorScreen):
        """Test adding port range as string succeeds."""
        result = await screen.add_port("9000-9100")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_add_port_int_success(self, screen: ScopeEditorScreen):
        """Test adding port as int succeeds."""
        result = await screen.add_port(8080)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_add_port_invalid_string_fails(self, screen: ScopeEditorScreen):
        """Test adding invalid port string fails."""
        result = await screen.add_port("invalid")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_add_port_out_of_range_fails(self, screen: ScopeEditorScreen):
        """Test adding port out of range fails."""
        result = await screen.add_port(70000)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_remove_port_string_success(self, screen: ScopeEditorScreen):
        """Test removing port as string succeeds."""
        result = await screen.remove_port("80")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_remove_port_range_string_success(self, screen: ScopeEditorScreen):
        """Test removing port range as string succeeds."""
        # First add the range, then remove it
        await screen.add_port("9000-9100")
        result = await screen.remove_port("9000-9100")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_remove_port_int_success(self, screen: ScopeEditorScreen):
        """Test removing port as int succeeds."""
        result = await screen.remove_port(443)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_remove_port_invalid_fails(self, screen: ScopeEditorScreen):
        """Test removing invalid port fails."""
        result = await screen.remove_port("invalid")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_remove_port_out_of_range_fails(self, screen: ScopeEditorScreen):
        """Test removing port out of range fails."""
        result = await screen.remove_port(70000)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_undo_success(self, screen: ScopeEditorScreen):
        """Test undo succeeds after a change."""
        original_count = len(screen.validator.config.allowed_networks)
        await screen.add_network("172.16.0.0/16")
        assert len(screen.validator.config.allowed_networks) == original_count + 1
        
        result = await screen.undo()
        assert result.success is True
        assert len(screen.validator.config.allowed_networks) == original_count

    @pytest.mark.asyncio
    async def test_undo_fails_when_no_undo_available(self, screen: ScopeEditorScreen):
        """Test undo fails when no undo state available."""
        result = await screen.undo()
        assert result.success is False
        assert "no undo" in result.error.lower()

    @pytest.mark.asyncio
    async def test_cancel_pending_change_success(self, screen: ScopeEditorScreen):
        """Test cancelling pending change succeeds."""
        # Start a countdown for production range
        await screen.add_network("8.8.8.0/24")
        
        # Cancel it
        result = await screen.cancel_pending_change()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_cancel_pending_change_fails_when_none(self, screen: ScopeEditorScreen):
        """Test cancelling when no pending change fails."""
        result = await screen.cancel_pending_change()
        assert result.success is False


class TestParsePortValue:
    """Tests for _parse_port_value helper."""

    @pytest.fixture
    def screen(self, sample_scope_validator: ScopeValidator) -> ScopeEditorScreen:
        """Create scope editor screen for testing."""
        return ScopeEditorScreen(validator=sample_scope_validator)

    def test_parse_single_port(self, screen: ScopeEditorScreen):
        """Test parsing single port."""
        assert screen._parse_port_value("80") == 80

    def test_parse_port_range(self, screen: ScopeEditorScreen):
        """Test parsing port range."""
        assert screen._parse_port_value("8000-8100") == (8000, 8100)
