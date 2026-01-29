"""Scope Editor Screen for Runtime Scope Adjustment.

Story 10.5: Runtime Scope Adjustment

Implements a full screen for modifying scope validator rules at runtime:
- View current scope rules (IP ranges, hostnames, ports)
- Add/remove IP ranges (CIDR notation)
- Add/remove hostnames (exact or wildcard)
- Add/remove port ranges
- 5-second countdown confirmation for production ranges
- 10-second undo window after changes
- Active agent detection to prevent unsafe scope removal
- Audit trail logging for all changes
- Event propagation to agents via EventBus

UX Spec References:
- Lines 436-438: Live scope modification with confirmation
- Lines 573: Confirmation input pattern
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from ipaddress import ip_network, IPv4Network, IPv6Network
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Optional, Union

import structlog
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static, Button, Input, ListView, ListItem, Label
from textual.timer import Timer

if TYPE_CHECKING:
    from cyberred.core.events import EventBus
    from cyberred.daemon.session_manager import SessionManager

from cyberred.tools.scope import ScopeValidator, ScopeConfig

log = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Validation Functions
# ─────────────────────────────────────────────────────────────────────────────

def validate_cidr(value: str) -> bool:
    """Validate CIDR notation or single IP address.
    
    Args:
        value: IP address or CIDR notation string.
        
    Returns:
        True if valid, False otherwise.
    """
    if not value or not value.strip():
        return False
    try:
        ip_network(value.strip(), strict=False)
        return True
    except ValueError:
        return False


def validate_hostname(value: str) -> bool:
    """Validate hostname (exact or wildcard pattern).
    
    Args:
        value: Hostname string.
        
    Returns:
        True if valid, False otherwise.
    """
    if not value or not value.strip():
        return False
    
    hostname = value.strip().lower()
    
    # Check for wildcard pattern
    if hostname.startswith("*."):
        # Must have something after *.
        if len(hostname) <= 2:
            return False
        hostname = hostname[2:]  # Remove *. prefix for validation
    elif hostname == "*":
        return False
    
    # Check each label in the hostname
    labels = hostname.split(".")
    if not labels or any(not label for label in labels):
        return False
    
    for label in labels:
        # Each label must not start or end with hyphen
        if label.startswith("-") or label.endswith("-"):
            return False
        # Each label must be alphanumeric with optional hyphens
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$", label):
            return False
    
    return True


def validate_port_range(value: str) -> bool:
    """Validate port number or port range.
    
    Args:
        value: Port string (e.g., "80" or "8000-8100").
        
    Returns:
        True if valid, False otherwise.
    """
    if not value or not value.strip():
        return False
    
    value = value.strip()
    
    # Check for range format
    if "-" in value:
        parts = value.split("-")
        if len(parts) != 2:
            return False
        try:
            start = int(parts[0])
            end = int(parts[1])
            if start < 1 or end > 65535 or start > end:
                return False
            return True
        except ValueError:
            return False
    else:
        try:
            port = int(value)
            return 1 <= port <= 65535
        except ValueError:
            return False


def is_production_range(network: str) -> bool:
    """Detect if network is a production (non-test) range.
    
    Production ranges trigger 5-second countdown confirmation.
    
    Args:
        network: CIDR notation string.
        
    Returns:
        True if production range, False otherwise.
    """
    try:
        net = ip_network(network, strict=False)
    except ValueError:
        return True  # Fail-closed: treat invalid as production
    
    # RFC 1918 private ranges are NOT production
    if net.is_private:
        return False
    
    # Documentation ranges are NOT production
    doc_ranges = [
        ip_network("192.0.2.0/24"),      # TEST-NET-1
        ip_network("198.51.100.0/24"),   # TEST-NET-2
        ip_network("203.0.113.0/24"),    # TEST-NET-3
        ip_network("2001:db8::/32"),     # IPv6 documentation
    ]
    for doc in doc_ranges:
        try:
            if net.subnet_of(doc) or net == doc:
                return False
        except TypeError:
            # IPv4/IPv6 mismatch
            continue
    
    # Everything else is production
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ScopeChange:
    """Represents a scope modification.
    
    Attributes:
        change_type: "add" or "remove"
        category: "network", "hostname", or "port"
        value: The value being added/removed
        timestamp: ISO 8601 timestamp
        operator: Who made the change
        is_production: Whether countdown was required
    """
    change_type: str
    category: str
    value: str
    timestamp: str
    operator: str
    is_production: bool = False


@dataclass
class ScopeSnapshot:
    """Snapshot of scope configuration for undo support.
    
    Attributes:
        timestamp: ISO 8601 timestamp
        networks: List of CIDR strings
        hostnames: List of hostname patterns
        ports: List of ports/ranges
        allow_private: Whether private IPs allowed
        allow_loopback: Whether loopback allowed
    """
    timestamp: str
    networks: list[str] = field(default_factory=list)
    hostnames: list[str] = field(default_factory=list)
    ports: list[Union[int, tuple[int, int]]] = field(default_factory=list)
    allow_private: bool = False
    allow_loopback: bool = False
    
    @classmethod
    def from_config(cls, config: ScopeConfig) -> "ScopeSnapshot":
        """Create snapshot from ScopeConfig.
        
        Args:
            config: ScopeConfig to snapshot.
            
        Returns:
            ScopeSnapshot instance.
        """
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            networks=[str(n) for n in config.allowed_networks],
            hostnames=list(config.allowed_hostnames),
            ports=list(config.allowed_ports) if config.allowed_ports else [],
            allow_private=config.allow_private,
            allow_loopback=config.allow_loopback,
        )


@dataclass
class ScopeUpdatedEvent:
    """Event emitted when scope is updated.
    
    Attributes:
        change: The ScopeChange that was applied
        new_config: New scope configuration snapshot
        previous_config: Previous scope configuration snapshot
    """
    change: ScopeChange
    new_config: ScopeSnapshot
    previous_config: ScopeSnapshot


@dataclass
class ChangeResult:
    """Result of a scope change operation.
    
    Attributes:
        success: Whether the change succeeded
        error: Error message if failed
        countdown_required: Whether countdown confirmation needed
        countdown_seconds: Countdown duration if required
        blocked_by_agents: Whether blocked due to active agents
        affected_agents: List of affected agent info if blocked
    """
    success: bool = False
    error: str = ""
    countdown_required: bool = False
    countdown_seconds: int = 0
    blocked_by_agents: bool = False
    affected_agents: list[dict] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# ScopeChangeManager
# ─────────────────────────────────────────────────────────────────────────────

class ScopeChangeManager:
    """Manages scope changes with validation and agent protection.
    
    Provides methods to add/remove scope entries while:
    - Validating input formats
    - Checking for active agents before removal
    - Creating snapshots for undo support
    """
    
    def __init__(
        self,
        validator: ScopeValidator,
        session_manager: Optional["SessionManager"] = None,
    ) -> None:
        """Initialize ScopeChangeManager.
        
        Args:
            validator: ScopeValidator to manage.
            session_manager: Optional SessionManager for agent queries.
        """
        self._validator = validator
        self._session_manager = session_manager
    
    @property
    def validator(self) -> ScopeValidator:
        """Get the managed ScopeValidator."""
        return self._validator
    
    def add_network(self, network: str) -> ChangeResult:
        """Add a network to the scope.
        
        Args:
            network: CIDR notation string.
            
        Returns:
            ChangeResult indicating success or failure.
        """
        if not validate_cidr(network):
            return ChangeResult(success=False, error="Invalid CIDR notation")
        
        try:
            net = ip_network(network.strip(), strict=False)
            if net not in self._validator.config.allowed_networks:
                self._validator.config.allowed_networks.append(net)
            return ChangeResult(success=True)
        except Exception as e:
            return ChangeResult(success=False, error=str(e))
    
    def remove_network(
        self, 
        network: str, 
        force: bool = False
    ) -> ChangeResult:
        """Remove a network from the scope.
        
        Args:
            network: CIDR notation string.
            force: If True, remove even with active agents.
            
        Returns:
            ChangeResult indicating success or failure.
        """
        if not validate_cidr(network):
            return ChangeResult(success=False, error="Invalid CIDR notation")
        
        try:
            net = ip_network(network.strip(), strict=False)
            
            # Check for active agents
            if self._session_manager and not force:
                agents = self._session_manager.get_agents_on_target(network)
                if agents:
                    return ChangeResult(
                        success=False,
                        error="Active agents on target",
                        blocked_by_agents=True,
                        affected_agents=agents,
                    )
            
            # Remove network
            networks = self._validator.config.allowed_networks
            self._validator.config.allowed_networks = [
                n for n in networks if n != net
            ]
            return ChangeResult(success=True)
        except Exception as e:
            return ChangeResult(success=False, error=str(e))
    
    def add_hostname(self, hostname: str) -> ChangeResult:
        """Add a hostname to the scope.
        
        Args:
            hostname: Hostname pattern (exact or wildcard).
            
        Returns:
            ChangeResult indicating success or failure.
        """
        if not validate_hostname(hostname):
            return ChangeResult(success=False, error="Invalid hostname format")
        
        try:
            hostname = hostname.strip().lower()
            if hostname not in self._validator.config.allowed_hostnames:
                self._validator.config.allowed_hostnames.append(hostname)
            return ChangeResult(success=True)
        except Exception as e:
            return ChangeResult(success=False, error=str(e))
    
    def remove_hostname(
        self, 
        hostname: str, 
        force: bool = False
    ) -> ChangeResult:
        """Remove a hostname from the scope.
        
        Args:
            hostname: Hostname pattern to remove.
            force: If True, remove even with active agents.
            
        Returns:
            ChangeResult indicating success or failure.
        """
        try:
            hostname = hostname.strip().lower()
            
            # Check for active agents
            if self._session_manager and not force:
                if hasattr(self._session_manager, 'get_agents_on_hostname'):
                    agents = self._session_manager.get_agents_on_hostname(hostname)
                    if agents:
                        return ChangeResult(
                            success=False,
                            error="Active agents on hostname",
                            blocked_by_agents=True,
                            affected_agents=agents,
                        )
            
            hostnames = self._validator.config.allowed_hostnames
            self._validator.config.allowed_hostnames = [
                h for h in hostnames if h != hostname
            ]
            return ChangeResult(success=True)
        except Exception as e:
            return ChangeResult(success=False, error=str(e))
    
    def add_port(self, port: Union[int, tuple[int, int]]) -> ChangeResult:
        """Add a port or port range to the scope.
        
        Args:
            port: Single port number or (start, end) tuple.
            
        Returns:
            ChangeResult indicating success or failure.
        """
        try:
            if isinstance(port, int):
                if port < 1 or port > 65535:
                    return ChangeResult(success=False, error="Port out of range (1-65535)")
            elif isinstance(port, tuple):
                if len(port) != 2 or port[0] < 1 or port[1] > 65535 or port[0] > port[1]:
                    return ChangeResult(success=False, error="Invalid port range")
            else:
                return ChangeResult(success=False, error="Invalid port type")
            
            if self._validator.config.allowed_ports is None:
                self._validator.config.allowed_ports = []
            
            if port not in self._validator.config.allowed_ports:
                self._validator.config.allowed_ports.append(port)
            return ChangeResult(success=True)
        except Exception as e:
            return ChangeResult(success=False, error=str(e))
    
    def remove_port(self, port: Union[int, tuple[int, int]]) -> ChangeResult:
        """Remove a port or port range from the scope.
        
        Args:
            port: Single port number or (start, end) tuple.
            
        Returns:
            ChangeResult indicating success or failure.
        """
        try:
            if self._validator.config.allowed_ports is None:
                return ChangeResult(success=False, error="No ports configured")
            
            self._validator.config.allowed_ports = [
                p for p in self._validator.config.allowed_ports if p != port
            ]
            return ChangeResult(success=True)
        except Exception as e:
            return ChangeResult(success=False, error=str(e))
    
    def get_snapshot(self) -> ScopeSnapshot:
        """Get current scope configuration snapshot.
        
        Returns:
            ScopeSnapshot of current configuration.
        """
        return ScopeSnapshot.from_config(self._validator.config)
    
    def restore_snapshot(self, snapshot: ScopeSnapshot) -> ChangeResult:
        """Restore scope from snapshot (undo).
        
        Args:
            snapshot: ScopeSnapshot to restore.
            
        Returns:
            ChangeResult indicating success or failure.
        """
        try:
            # Restore networks
            self._validator.config.allowed_networks = [
                ip_network(n, strict=False) for n in snapshot.networks
            ]
            # Restore hostnames
            self._validator.config.allowed_hostnames = list(snapshot.hostnames)
            # Restore ports
            self._validator.config.allowed_ports = list(snapshot.ports) if snapshot.ports else None
            # Restore flags
            self._validator.config.allow_private = snapshot.allow_private
            self._validator.config.allow_loopback = snapshot.allow_loopback
            return ChangeResult(success=True)
        except Exception as e:
            return ChangeResult(success=False, error=str(e))
    
    def requires_countdown(self, network: str) -> bool:
        """Check if network requires countdown confirmation.
        
        Args:
            network: CIDR notation string.
            
        Returns:
            True if production range requiring countdown.
        """
        return is_production_range(network)


# ─────────────────────────────────────────────────────────────────────────────
# ScopeEditorScreen
# ─────────────────────────────────────────────────────────────────────────────

class ScopeEditorScreen(Screen):
    """Full screen for runtime scope adjustment.
    
    Story 10.5: Runtime Scope Adjustment
    
    Features:
    - View current scope (networks, hostnames, ports)
    - Add/remove entries with validation
    - 5-second countdown for production ranges
    - 10-second undo window after changes
    - Active agent protection on removal
    - Audit trail logging
    """
    
    TITLE = "Scope Editor"
    
    BINDINGS = [
        Binding("escape", "close", "Close", show=True, priority=True),
        Binding("u", "undo", "Undo", show=True),
        Binding("c", "cancel_countdown", "Cancel", show=False),
    ]
    
    DEFAULT_CSS: ClassVar[str] = """
    ScopeEditorScreen {
        align: center middle;
    }
    
    ScopeEditorScreen > #scope-container {
        width: 100%;
        height: 100%;
        padding: 1;
        background: $surface;
    }
    
    ScopeEditorScreen .section-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    
    ScopeEditorScreen .scope-section {
        height: auto;
        min-height: 8;
        max-height: 15;
        border: solid $primary;
        margin-bottom: 1;
        padding: 1;
    }
    
    ScopeEditorScreen .input-row {
        height: 3;
        margin-top: 1;
    }
    
    ScopeEditorScreen .input-row Input {
        width: 60%;
    }
    
    ScopeEditorScreen .input-row Button {
        margin-left: 1;
    }
    
    ScopeEditorScreen #countdown-overlay {
        width: 50;
        height: 10;
        background: $warning-darken-2;
        border: thick $warning;
        padding: 2;
        display: none;
    }
    
    ScopeEditorScreen #countdown-overlay.visible {
        display: block;
    }
    
    ScopeEditorScreen #undo-bar {
        height: 3;
        background: $success-darken-2;
        padding: 0 2;
        display: none;
    }
    
    ScopeEditorScreen #undo-bar.visible {
        display: block;
    }
    
    ScopeEditorScreen #status-message {
        height: 2;
        padding: 0 1;
    }
    """
    
    # Constants
    COUNTDOWN_SECONDS: ClassVar[int] = 5
    UNDO_WINDOW_SECONDS: ClassVar[int] = 10
    
    # Reactive properties
    countdown_remaining: reactive[float] = reactive(0.0)
    undo_remaining: reactive[float] = reactive(0.0)
    
    def __init__(
        self,
        validator: ScopeValidator,
        event_bus: Optional["EventBus"] = None,
        session_manager: Optional["SessionManager"] = None,
        operator: str = "operator",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize ScopeEditorScreen.
        
        Args:
            validator: ScopeValidator to edit.
            event_bus: EventBus for scope update events and audit.
            session_manager: SessionManager for agent queries.
            operator: Operator identifier for audit trail.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._validator = validator
        self._event_bus = event_bus
        self._session_manager = session_manager
        self._operator = operator
        self._change_manager = ScopeChangeManager(validator, session_manager)
        
        # Undo state
        self._undo_snapshot: Optional[ScopeSnapshot] = None
        self._can_undo: bool = False
        self._undo_timer: Optional[Timer] = None
        
        # Countdown state
        self._pending_change: Optional[ScopeChange] = None
        self._countdown_timer: Optional[Timer] = None
    
    @property
    def validator(self) -> ScopeValidator:
        """Get the ScopeValidator being edited."""
        return self._validator
    
    def compose(self) -> ComposeResult:
        """Compose the scope editor layout."""
        with Container(id="scope-container"):
            yield Static("🎯 SCOPE EDITOR", id="title", classes="section-title")
            yield Static("", id="status-message")
            
            # Networks section
            with Vertical(classes="scope-section", id="networks-section"):
                yield Static("📡 IP Networks (CIDR)", classes="section-title")
                yield ListView(id="networks-list")
                with Horizontal(classes="input-row"):
                    yield Input(placeholder="e.g., 192.168.1.0/24", id="network-input")
                    yield Button("Add", id="add-network", variant="success")
                    yield Button("Remove", id="remove-network", variant="error")
            
            # Hostnames section
            with Vertical(classes="scope-section", id="hostnames-section"):
                yield Static("🌐 Hostnames", classes="section-title")
                yield ListView(id="hostnames-list")
                with Horizontal(classes="input-row"):
                    yield Input(placeholder="e.g., *.example.com", id="hostname-input")
                    yield Button("Add", id="add-hostname", variant="success")
                    yield Button("Remove", id="remove-hostname", variant="error")
            
            # Ports section
            with Vertical(classes="scope-section", id="ports-section"):
                yield Static("🔌 Ports", classes="section-title")
                yield ListView(id="ports-list")
                with Horizontal(classes="input-row"):
                    yield Input(placeholder="e.g., 80 or 8000-8100", id="port-input")
                    yield Button("Add", id="add-port", variant="success")
                    yield Button("Remove", id="remove-port", variant="error")
            
            # Undo bar
            with Horizontal(id="undo-bar"):
                yield Static("", id="undo-countdown")
                yield Button("Undo Last Change", id="undo-btn", variant="warning")
            
            # Countdown overlay
            with Container(id="countdown-overlay"):
                yield Static("⚠️ Production Range Detected", id="countdown-title")
                yield Static("", id="countdown-text")
                yield Button("Cancel", id="cancel-countdown", variant="error")
    
    def on_mount(self) -> None:
        """Populate lists with current scope on mount."""
        self._refresh_lists()
    
    def _refresh_lists(self) -> None:
        """Refresh all scope lists from current config.
        
        Safe to call when screen is not mounted (e.g., in tests).
        """
        try:
            # Networks
            networks_list = self.query_one("#networks-list", ListView)
            networks_list.clear()
            for net in self._validator.config.allowed_networks:
                networks_list.append(ListItem(Label(str(net))))
            
            # Hostnames
            hostnames_list = self.query_one("#hostnames-list", ListView)
            hostnames_list.clear()
            for host in self._validator.config.allowed_hostnames:
                hostnames_list.append(ListItem(Label(host)))
            
            # Ports
            ports_list = self.query_one("#ports-list", ListView)
            ports_list.clear()
            if self._validator.config.allowed_ports:
                for port in self._validator.config.allowed_ports:
                    if isinstance(port, tuple):
                        ports_list.append(ListItem(Label(f"{port[0]}-{port[1]}")))
                    else:
                        ports_list.append(ListItem(Label(str(port))))
        except Exception:
            # Screen not mounted - safe to skip UI updates
            pass
    
    def _set_status(self, message: str, error: bool = False) -> None:
        """Set status message.
        
        Safe to call when screen is not mounted (e.g., in tests).
        
        Args:
            message: Status message to display.
            error: If True, display as error (red), else success (green).
        """
        try:
            status = self.query_one("#status-message", Static)
            if error:
                status.update(f"[red]❌ {message}[/red]")
            else:
                status.update(f"[green]✓ {message}[/green]")
        except Exception:
            # Screen not mounted - safe to skip UI updates
            pass
    
    # ─────────────────────────────────────────────────────────────────────
    # Validation Methods
    # ─────────────────────────────────────────────────────────────────────
    
    def _validate_network_input(self, value: str) -> bool:
        """Validate network input."""
        return validate_cidr(value)
    
    def _validate_hostname_input(self, value: str) -> bool:
        """Validate hostname input."""
        return validate_hostname(value)
    
    def _validate_port_input(self, value: str) -> bool:
        """Validate port input."""
        return validate_port_range(value)
    
    # ─────────────────────────────────────────────────────────────────────
    # Change Application
    # ─────────────────────────────────────────────────────────────────────
    
    def _should_show_countdown(self) -> bool:
        """Check if countdown should be shown for pending change."""
        if not self._pending_change:
            return False
        return self._pending_change.is_production
    
    def _apply_change_internal(self, change: ScopeChange) -> None:
        """Apply a scope change internally (after confirmation)."""
        # Store undo snapshot
        self._undo_snapshot = self._change_manager.get_snapshot()
        self._can_undo = True
        
        # Apply change
        if change.category == "network":
            if change.change_type == "add":
                self._change_manager.add_network(change.value)
            else:
                self._change_manager.remove_network(change.value, force=True)
        elif change.category == "hostname":
            if change.change_type == "add":
                self._change_manager.add_hostname(change.value)
            else:
                self._change_manager.remove_hostname(change.value, force=True)
        elif change.category == "port":
            port_val = self._parse_port_value(change.value)
            if change.change_type == "add":
                self._change_manager.add_port(port_val)
            else:
                self._change_manager.remove_port(port_val)
        
        # Start undo timer
        self._start_undo_timer()
        
        # Refresh UI
        self._refresh_lists()
    
    def _parse_port_value(self, value: str) -> Union[int, tuple[int, int]]:
        """Parse port string to int or tuple."""
        if "-" in value:
            parts = value.split("-")
            return (int(parts[0]), int(parts[1]))
        return int(value)
    
    def _perform_undo(self) -> None:
        """Perform undo operation."""
        if self._undo_snapshot and self._can_undo:
            self._change_manager.restore_snapshot(self._undo_snapshot)
            self._clear_undo_state()
            self._refresh_lists()
            self._set_status("Change undone")
    
    def _clear_undo_state(self) -> None:
        """Clear undo state."""
        self._undo_snapshot = None
        self._can_undo = False
        if self._undo_timer:
            self._undo_timer.stop()
            self._undo_timer = None
        try:
            undo_bar = self.query_one("#undo-bar")
            undo_bar.remove_class("visible")
        except Exception:
            pass
    
    def _start_undo_timer(self) -> None:
        """Start the undo window timer.
        
        Safe to call when screen is not mounted (e.g., in tests).
        """
        self.undo_remaining = self.UNDO_WINDOW_SECONDS
        try:
            self._undo_timer = self.set_interval(0.1, self._update_undo_timer)
            undo_bar = self.query_one("#undo-bar")
            undo_bar.add_class("visible")
        except Exception:
            # Screen not mounted - timer won't start but state is set
            pass
    
    def _update_undo_timer(self) -> None:
        """Update undo countdown."""
        self.undo_remaining = max(0.0, self.undo_remaining - 0.1)
        try:
            countdown = self.query_one("#undo-countdown", Static)
            countdown.update(f"Undo available: {self.undo_remaining:.1f}s")
        except Exception:
            pass
        
        if self.undo_remaining <= 0:
            self._clear_undo_state()
    
    # ─────────────────────────────────────────────────────────────────────
    # Public Async Methods
    # ─────────────────────────────────────────────────────────────────────
    
    async def add_network(
        self, 
        network: str, 
        skip_countdown: bool = False
    ) -> ChangeResult:
        """Add a network to scope.
        
        Args:
            network: CIDR notation string.
            skip_countdown: Ignored for production ranges.
            
        Returns:
            ChangeResult indicating success or pending confirmation.
        """
        if not validate_cidr(network):
            return ChangeResult(success=False, error="Invalid CIDR notation")
        
        is_prod = is_production_range(network)
        
        # Production ranges ALWAYS require countdown
        if is_prod:
            self._pending_change = ScopeChange(
                change_type="add",
                category="network",
                value=network,
                timestamp=datetime.now(timezone.utc).isoformat(),
                operator=self._operator,
                is_production=True,
            )
            self._start_countdown()
            return ChangeResult(
                success=False,
                countdown_required=True,
                countdown_seconds=self.COUNTDOWN_SECONDS,
            )
        
        # Non-production: apply immediately
        change = ScopeChange(
            change_type="add",
            category="network",
            value=network,
            timestamp=datetime.now(timezone.utc).isoformat(),
            operator=self._operator,
            is_production=False,
        )
        self._apply_change_internal(change)
        await self._emit_scope_updated(change)
        await self._log_audit(change)
        self._set_status(f"Added network: {network}")
        return ChangeResult(success=True)
    
    async def remove_network(
        self, 
        network: str, 
        force: bool = False
    ) -> ChangeResult:
        """Remove a network from scope.
        
        Args:
            network: CIDR notation string.
            force: If True, remove even with active agents.
            
        Returns:
            ChangeResult indicating success or failure.
        """
        if not validate_cidr(network):
            return ChangeResult(success=False, error="Invalid CIDR notation")
        
        # Check for active agents
        if self._session_manager and not force:
            agents = self._session_manager.get_agents_on_target(network)
            if agents:
                return ChangeResult(
                    success=False,
                    error="Active agents on target",
                    blocked_by_agents=True,
                    affected_agents=agents,
                )
        
        change = ScopeChange(
            change_type="remove",
            category="network",
            value=network,
            timestamp=datetime.now(timezone.utc).isoformat(),
            operator=self._operator,
            is_production=is_production_range(network),
        )
        self._apply_change_internal(change)
        await self._emit_scope_updated(change)
        await self._log_audit(change)
        self._set_status(f"Removed network: {network}")
        return ChangeResult(success=True)
    
    async def add_hostname(self, hostname: str) -> ChangeResult:
        """Add a hostname to scope."""
        if not validate_hostname(hostname):
            return ChangeResult(success=False, error="Invalid hostname format")
        
        change = ScopeChange(
            change_type="add",
            category="hostname",
            value=hostname,
            timestamp=datetime.now(timezone.utc).isoformat(),
            operator=self._operator,
            is_production=False,
        )
        self._apply_change_internal(change)
        await self._emit_scope_updated(change)
        await self._log_audit(change)
        self._set_status(f"Added hostname: {hostname}")
        return ChangeResult(success=True)
    
    async def remove_hostname(
        self, 
        hostname: str, 
        force: bool = False
    ) -> ChangeResult:
        """Remove a hostname from scope."""
        if self._session_manager and not force:
            if hasattr(self._session_manager, 'get_agents_on_hostname'):
                agents = self._session_manager.get_agents_on_hostname(hostname)
                if agents:
                    return ChangeResult(
                        success=False,
                        error="Active agents on hostname",
                        blocked_by_agents=True,
                        affected_agents=agents,
                    )
        
        change = ScopeChange(
            change_type="remove",
            category="hostname",
            value=hostname,
            timestamp=datetime.now(timezone.utc).isoformat(),
            operator=self._operator,
            is_production=False,
        )
        self._apply_change_internal(change)
        await self._emit_scope_updated(change)
        await self._log_audit(change)
        self._set_status(f"Removed hostname: {hostname}")
        return ChangeResult(success=True)
    
    async def add_port(self, port: Union[int, str]) -> ChangeResult:
        """Add a port to scope.
        
        Args:
            port: Port number or range string (e.g., "80" or "8000-8100").
            
        Returns:
            ChangeResult indicating success or failure.
        """
        if isinstance(port, str):
            if not validate_port_range(port):
                return ChangeResult(success=False, error="Invalid port")
            port_val = self._parse_port_value(port)
        else:
            if port < 1 or port > 65535:
                return ChangeResult(success=False, error="Port out of range")
            port_val = port
        
        # Store undo snapshot BEFORE making changes
        self._undo_snapshot = self._change_manager.get_snapshot()
        
        change = ScopeChange(
            change_type="add",
            category="port",
            value=str(port),
            timestamp=datetime.now(timezone.utc).isoformat(),
            operator=self._operator,
            is_production=False,
        )
        
        result = self._change_manager.add_port(port_val)
        if not result.success:
            self._undo_snapshot = None  # Clear snapshot on failure
            return result
        
        # Enable undo and refresh
        self._can_undo = True
        self._start_undo_timer()
        self._refresh_lists()
        
        await self._emit_scope_updated(change)
        await self._log_audit(change)
        self._set_status(f"Added port: {port}")
        return ChangeResult(success=True)
    
    async def remove_port(self, port: Union[int, str]) -> ChangeResult:
        """Remove a port from scope.
        
        Args:
            port: Port number or range string (e.g., "80" or "8000-8100").
            
        Returns:
            ChangeResult indicating success or failure.
        """
        if isinstance(port, str):
            if not validate_port_range(port):
                return ChangeResult(success=False, error="Invalid port")
            port_val = self._parse_port_value(port)
        else:
            if port < 1 or port > 65535:
                return ChangeResult(success=False, error="Port out of range")
            port_val = port
        
        # Store undo snapshot BEFORE making changes
        self._undo_snapshot = self._change_manager.get_snapshot()
        
        change = ScopeChange(
            change_type="remove",
            category="port",
            value=str(port),
            timestamp=datetime.now(timezone.utc).isoformat(),
            operator=self._operator,
            is_production=False,
        )
        
        result = self._change_manager.remove_port(port_val)
        if not result.success:
            self._undo_snapshot = None  # Clear snapshot on failure
            return result
        
        # Enable undo and refresh
        self._can_undo = True
        self._start_undo_timer()
        self._refresh_lists()
        
        await self._emit_scope_updated(change)
        await self._log_audit(change)
        self._set_status(f"Removed port: {port}")
        return ChangeResult(success=True)
    
    async def undo(self) -> ChangeResult:
        """Undo the last scope change."""
        if not self._can_undo or not self._undo_snapshot:
            return ChangeResult(success=False, error="No undo available or expired")
        
        # Log undo to audit
        undo_change = ScopeChange(
            change_type="undo",
            category="all",
            value="previous_state",
            timestamp=datetime.now(timezone.utc).isoformat(),
            operator=self._operator,
            is_production=False,
        )
        await self._log_audit(undo_change)
        
        self._perform_undo()
        return ChangeResult(success=True)
    
    async def cancel_pending_change(self) -> ChangeResult:
        """Cancel a pending countdown change."""
        if self._pending_change:
            self._pending_change = None
            self._stop_countdown()
            self._set_status("Change cancelled")
            return ChangeResult(success=True)
        return ChangeResult(success=False, error="No pending change")
    
    # ─────────────────────────────────────────────────────────────────────
    # Countdown Methods
    # ─────────────────────────────────────────────────────────────────────
    
    def _start_countdown(self) -> None:
        """Start countdown for production range confirmation."""
        self.countdown_remaining = self.COUNTDOWN_SECONDS
        self._countdown_timer = self.set_interval(0.1, self._update_countdown)
        try:
            overlay = self.query_one("#countdown-overlay")
            overlay.add_class("visible")
            text = self.query_one("#countdown-text", Static)
            text.update(f"Applying in {self.countdown_remaining:.1f}s...")
        except Exception:
            pass
    
    def _stop_countdown(self) -> None:
        """Stop countdown."""
        if self._countdown_timer:
            self._countdown_timer.stop()
            self._countdown_timer = None
        try:
            overlay = self.query_one("#countdown-overlay")
            overlay.remove_class("visible")
        except Exception:
            pass
    
    def _update_countdown(self) -> None:
        """Update countdown display."""
        self.countdown_remaining = max(0.0, self.countdown_remaining - 0.1)
        try:
            text = self.query_one("#countdown-text", Static)
            text.update(f"Applying in {self.countdown_remaining:.1f}s...")
        except Exception:
            pass
        
        if self.countdown_remaining <= 0:
            self._countdown_complete()
    
    def _countdown_complete(self) -> None:
        """Handle countdown completion."""
        self._stop_countdown()
        if self._pending_change:
            asyncio.create_task(self._apply_pending_change())
    
    async def _apply_pending_change(self) -> None:
        """Apply the pending change after countdown."""
        if not self._pending_change:
            return
        
        change = self._pending_change
        self._pending_change = None
        
        self._apply_change_internal(change)
        await self._emit_scope_updated(change)
        await self._log_audit(change)
        self._set_status(f"Applied: {change.change_type} {change.category} {change.value}")
    
    # ─────────────────────────────────────────────────────────────────────
    # Event Bus Integration
    # ─────────────────────────────────────────────────────────────────────
    
    async def _emit_scope_updated(self, change: ScopeChange) -> None:
        """Emit scope updated event via EventBus."""
        if not self._event_bus:
            return
        
        try:
            event_data = {
                "type": "scope_updated",
                "change": {
                    "change_type": change.change_type,
                    "category": change.category,
                    "value": change.value,
                    "operator": change.operator,
                    "timestamp": change.timestamp,
                },
                "new_config": self._change_manager.get_snapshot().__dict__,
            }
            await self._event_bus.publish("control:scope", event_data)
        except Exception as e:
            log.error("scope_event_publish_failed", error=str(e))
    
    async def _log_audit(self, change: ScopeChange) -> None:
        """Log scope change to audit trail."""
        if not self._event_bus:
            return
        
        try:
            audit_data = {
                "type": "scope_change",
                "change_type": change.change_type,
                "category": change.category,
                "value": change.value,
                "operator": change.operator,
                "timestamp": change.timestamp,
                "is_production": change.is_production,
            }
            await self._event_bus.audit(audit_data)
        except Exception as e:
            log.error("scope_audit_failed", error=str(e))
    
    # ─────────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────────
    
    def action_close(self) -> None:
        """Close the scope editor screen."""
        self.app.pop_screen()
    
    def action_undo(self) -> None:
        """Trigger undo action."""
        asyncio.create_task(self.undo())
    
    def action_cancel_countdown(self) -> None:
        """Cancel countdown action."""
        asyncio.create_task(self.cancel_pending_change())
    
    # ─────────────────────────────────────────────────────────────────────
    # Button Handlers
    # ─────────────────────────────────────────────────────────────────────
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        
        if button_id == "add-network":
            value = self.query_one("#network-input", Input).value
            if value:
                asyncio.create_task(self.add_network(value))
                self.query_one("#network-input", Input).value = ""
        
        elif button_id == "remove-network":
            value = self.query_one("#network-input", Input).value
            if value:
                asyncio.create_task(self.remove_network(value))
                self.query_one("#network-input", Input).value = ""
        
        elif button_id == "add-hostname":
            value = self.query_one("#hostname-input", Input).value
            if value:
                asyncio.create_task(self.add_hostname(value))
                self.query_one("#hostname-input", Input).value = ""
        
        elif button_id == "remove-hostname":
            value = self.query_one("#hostname-input", Input).value
            if value:
                asyncio.create_task(self.remove_hostname(value))
                self.query_one("#hostname-input", Input).value = ""
        
        elif button_id == "add-port":
            value = self.query_one("#port-input", Input).value
            if value:
                asyncio.create_task(self.add_port(value))
                self.query_one("#port-input", Input).value = ""
        
        elif button_id == "remove-port":
            value = self.query_one("#port-input", Input).value
            if value:
                asyncio.create_task(self.remove_port(value))
                self.query_one("#port-input", Input).value = ""
        
        elif button_id == "undo-btn":
            asyncio.create_task(self.undo())
        
        elif button_id == "cancel-countdown":
            asyncio.create_task(self.cancel_pending_change())
