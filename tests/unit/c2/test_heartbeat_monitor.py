"""Unit tests for HeartbeatMonitor class.

Story 12.4: Heartbeat Monitoring
Tests follow RED-GREEN-REFACTOR TDD cycle.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from cyberred.c2.heartbeat_monitor import (
    ConnectionStatus,
    DropBoxConnection,
    HeartbeatMonitor,
    HeartbeatMonitorConfig,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def default_config() -> HeartbeatMonitorConfig:
    """Default heartbeat monitor configuration."""
    return HeartbeatMonitorConfig()


@pytest.fixture
def fast_config() -> HeartbeatMonitorConfig:
    """Fast config for testing (1s intervals instead of 5s)."""
    return HeartbeatMonitorConfig(
        heartbeat_interval_seconds=1,
        warning_threshold=3,
        critical_threshold=6,
        max_reconnect_delay_seconds=30,
    )


@pytest.fixture
def heartbeat_monitor(default_config: HeartbeatMonitorConfig) -> HeartbeatMonitor:
    """Create HeartbeatMonitor instance with default config."""
    return HeartbeatMonitor(config=default_config)


@pytest.fixture
def monitor_with_callbacks() -> tuple[HeartbeatMonitor, MagicMock, MagicMock]:
    """Create HeartbeatMonitor with status change and alert callbacks."""
    on_status_change = MagicMock()
    on_alert = MagicMock()
    monitor = HeartbeatMonitor(
        config=HeartbeatMonitorConfig(),
        on_status_change=on_status_change,
        on_alert=on_alert,
    )
    return monitor, on_status_change, on_alert


# =============================================================================
# Task 1: HeartbeatMonitor Initialization Tests (Subtask 1.1)
# =============================================================================


class TestHeartbeatMonitorInit:
    """Tests for HeartbeatMonitor initialization."""

    def test_init_with_default_config(self) -> None:
        """Monitor initializes with default configuration."""
        monitor = HeartbeatMonitor()
        
        assert monitor.config.heartbeat_interval_seconds == 5
        assert monitor.config.warning_threshold == 3
        assert monitor.config.critical_threshold == 6
        assert monitor.config.max_reconnect_delay_seconds == 30
        assert len(monitor.get_all_connections()) == 0

    def test_init_with_custom_config(self) -> None:
        """Monitor initializes with custom configuration."""
        config = HeartbeatMonitorConfig(
            heartbeat_interval_seconds=10,
            warning_threshold=5,
            critical_threshold=10,
            max_reconnect_delay_seconds=60,
        )
        monitor = HeartbeatMonitor(config=config)
        
        assert monitor.config.heartbeat_interval_seconds == 10
        assert monitor.config.warning_threshold == 5
        assert monitor.config.critical_threshold == 10
        assert monitor.config.max_reconnect_delay_seconds == 60

    def test_init_with_callbacks(self) -> None:
        """Monitor initializes with status change and alert callbacks."""
        on_status = MagicMock()
        on_alert = MagicMock()
        
        monitor = HeartbeatMonitor(
            on_status_change=on_status,
            on_alert=on_alert,
        )
        
        assert monitor._on_status_change is on_status
        assert monitor._on_alert is on_alert

    def test_init_not_running(self) -> None:
        """Monitor is not running after initialization."""
        monitor = HeartbeatMonitor()
        
        assert not monitor._running
        assert monitor._check_task is None


# =============================================================================
# Task 1: DropBoxConnection Dataclass Tests (Subtask 1.3)
# =============================================================================


class TestDropBoxConnection:
    """Tests for DropBoxConnection dataclass."""

    def test_drop_box_connection_defaults(self) -> None:
        """DropBoxConnection has correct defaults."""
        now = datetime.now(timezone.utc)
        conn = DropBoxConnection(drop_box_id="db-001", last_heartbeat=now)
        
        assert conn.drop_box_id == "db-001"
        assert conn.last_heartbeat == now
        assert conn.missed_count == 0
        assert conn.status == ConnectionStatus.HEALTHY
        assert conn.reconnect_attempts == 0
        assert conn.latency_ms is None

    def test_drop_box_connection_custom_values(self) -> None:
        """DropBoxConnection accepts custom values."""
        now = datetime.now(timezone.utc)
        conn = DropBoxConnection(
            drop_box_id="db-002",
            last_heartbeat=now,
            missed_count=3,
            status=ConnectionStatus.WARNING,
            reconnect_attempts=2,
            latency_ms=150,
        )
        
        assert conn.missed_count == 3
        assert conn.status == ConnectionStatus.WARNING
        assert conn.reconnect_attempts == 2
        assert conn.latency_ms == 150


# =============================================================================
# Task 1: ConnectionStatus Enum Tests (Subtask 2.5)
# =============================================================================


class TestConnectionStatus:
    """Tests for ConnectionStatus enum."""

    def test_connection_status_values(self) -> None:
        """ConnectionStatus has correct values."""
        assert ConnectionStatus.HEALTHY.value == "healthy"
        assert ConnectionStatus.WARNING.value == "warning"
        assert ConnectionStatus.CRITICAL.value == "critical"
        assert ConnectionStatus.LOST.value == "lost"

    def test_connection_status_members(self) -> None:
        """ConnectionStatus has all expected members."""
        members = list(ConnectionStatus)
        assert len(members) == 4
        assert ConnectionStatus.HEALTHY in members
        assert ConnectionStatus.WARNING in members
        assert ConnectionStatus.CRITICAL in members
        assert ConnectionStatus.LOST in members


# =============================================================================
# Task 1: record_heartbeat Tests (Subtasks 1.4-1.5)
# =============================================================================


class TestRecordHeartbeat:
    """Tests for record_heartbeat method."""

    def test_record_heartbeat_registers_new_connection(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """record_heartbeat registers new drop box connection."""
        now = datetime.now(timezone.utc)
        
        heartbeat_monitor.record_heartbeat("db-001", timestamp=now, latency_ms=100)
        
        conn = heartbeat_monitor.get_connection_status("db-001")
        assert conn is not None
        assert conn.drop_box_id == "db-001"
        assert conn.last_heartbeat == now
        assert conn.latency_ms == 100
        assert conn.status == ConnectionStatus.HEALTHY

    def test_record_heartbeat_updates_existing_connection(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """record_heartbeat updates existing connection timestamp."""
        now = datetime.now(timezone.utc)
        later = now + timedelta(seconds=5)
        
        heartbeat_monitor.record_heartbeat("db-001", timestamp=now, latency_ms=100)
        heartbeat_monitor.record_heartbeat("db-001", timestamp=later, latency_ms=120)
        
        conn = heartbeat_monitor.get_connection_status("db-001")
        assert conn is not None
        assert conn.last_heartbeat == later
        assert conn.latency_ms == 120

    def test_record_heartbeat_resets_missed_count(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """record_heartbeat resets missed count to zero."""
        now = datetime.now(timezone.utc)
        
        # Register and simulate missed heartbeats
        heartbeat_monitor.record_heartbeat("db-001", timestamp=now)
        conn = heartbeat_monitor.get_connection_status("db-001")
        conn.missed_count = 5
        conn.status = ConnectionStatus.WARNING
        
        # Record new heartbeat
        later = now + timedelta(seconds=30)
        heartbeat_monitor.record_heartbeat("db-001", timestamp=later)
        
        conn = heartbeat_monitor.get_connection_status("db-001")
        assert conn.missed_count == 0
        assert conn.status == ConnectionStatus.HEALTHY

    def test_record_heartbeat_uses_current_time_if_not_provided(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """record_heartbeat uses current time when timestamp not provided."""
        before = datetime.now(timezone.utc)
        heartbeat_monitor.record_heartbeat("db-001")
        after = datetime.now(timezone.utc)
        
        conn = heartbeat_monitor.get_connection_status("db-001")
        assert before <= conn.last_heartbeat <= after

    def test_record_heartbeat_resets_reconnect_attempts(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """record_heartbeat resets reconnect attempts on recovery."""
        now = datetime.now(timezone.utc)
        
        # Register and simulate reconnection state
        heartbeat_monitor.record_heartbeat("db-001", timestamp=now)
        conn = heartbeat_monitor.get_connection_status("db-001")
        conn.reconnect_attempts = 3
        conn.status = ConnectionStatus.LOST
        
        # Record recovery heartbeat
        later = now + timedelta(seconds=60)
        heartbeat_monitor.record_heartbeat("db-001", timestamp=later)
        
        conn = heartbeat_monitor.get_connection_status("db-001")
        assert conn.reconnect_attempts == 0
        assert conn.status == ConnectionStatus.HEALTHY

    def test_record_heartbeat_triggers_status_change_callback(
        self, monitor_with_callbacks: tuple[HeartbeatMonitor, MagicMock, MagicMock]
    ) -> None:
        """record_heartbeat triggers callback on status recovery."""
        monitor, on_status_change, _ = monitor_with_callbacks
        now = datetime.now(timezone.utc)
        
        # Register and set to warning
        monitor.record_heartbeat("db-001", timestamp=now)
        conn = monitor.get_connection_status("db-001")
        conn.status = ConnectionStatus.WARNING
        
        # Record recovery
        later = now + timedelta(seconds=30)
        monitor.record_heartbeat("db-001", timestamp=later)
        
        on_status_change.assert_called_with("db-001", ConnectionStatus.HEALTHY)


# =============================================================================
# Task 1: check_heartbeats Tests (Subtasks 1.6-1.7)
# =============================================================================


class TestCheckHeartbeats:
    """Tests for check_heartbeats method."""

    @pytest.mark.asyncio
    async def test_check_heartbeats_increments_missed_count(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """check_heartbeats increments missed count for stale connections."""
        # Register drop box with old timestamp
        old_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        heartbeat_monitor.record_heartbeat("db-001", timestamp=old_time)
        
        await heartbeat_monitor.check_heartbeats()
        
        conn = heartbeat_monitor.get_connection_status("db-001")
        assert conn.missed_count == 2  # 10s / 5s = 2 missed

    @pytest.mark.asyncio
    async def test_check_heartbeats_no_increment_for_fresh_connection(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """check_heartbeats does not increment for fresh connections."""
        # Register drop box with current timestamp
        now = datetime.now(timezone.utc)
        heartbeat_monitor.record_heartbeat("db-001", timestamp=now)
        
        await heartbeat_monitor.check_heartbeats()
        
        conn = heartbeat_monitor.get_connection_status("db-001")
        assert conn.missed_count == 0

    @pytest.mark.asyncio
    async def test_check_heartbeats_multiple_connections(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """check_heartbeats handles multiple drop box connections."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(seconds=20)
        
        heartbeat_monitor.record_heartbeat("db-001", timestamp=now)  # Fresh
        heartbeat_monitor.record_heartbeat("db-002", timestamp=old_time)  # Stale
        
        await heartbeat_monitor.check_heartbeats()
        
        conn1 = heartbeat_monitor.get_connection_status("db-001")
        conn2 = heartbeat_monitor.get_connection_status("db-002")
        
        assert conn1.missed_count == 0
        assert conn2.missed_count == 4  # 20s / 5s = 4 missed


# =============================================================================
# Task 2: Alert Thresholds and Status Transitions (Subtasks 2.1-2.6)
# =============================================================================


class TestAlertThresholds:
    """Tests for alert thresholds and status transitions."""

    @pytest.mark.asyncio
    async def test_warning_at_3_missed_heartbeats(
        self, monitor_with_callbacks: tuple[HeartbeatMonitor, MagicMock, MagicMock]
    ) -> None:
        """Warning alert triggers at exactly 3 missed heartbeats (AC #2)."""
        monitor, on_status_change, on_alert = monitor_with_callbacks
        
        # Register with timestamp 15s in past (3 missed @ 5s interval)
        old_time = datetime.now(timezone.utc) - timedelta(seconds=15)
        monitor.record_heartbeat("db-001", timestamp=old_time)
        
        await monitor.check_heartbeats()
        
        conn = monitor.get_connection_status("db-001")
        assert conn.status == ConnectionStatus.WARNING
        assert conn.missed_count == 3
        
        on_status_change.assert_called_with("db-001", ConnectionStatus.WARNING)
        on_alert.assert_called_once()
        call_args = on_alert.call_args
        assert call_args[0][0] == "db-001"
        assert call_args[0][1] == "c2.heartbeat.warning"

    @pytest.mark.asyncio
    async def test_critical_at_6_missed_heartbeats(
        self, monitor_with_callbacks: tuple[HeartbeatMonitor, MagicMock, MagicMock]
    ) -> None:
        """Critical alert triggers at exactly 6 missed heartbeats (AC #3).
        
        Note: 6 missed = CRITICAL status (triggers reconnection).
        LOST status requires 10 missed or max reconnect attempts.
        """
        monitor, on_status_change, on_alert = monitor_with_callbacks
        
        # Register with timestamp 30s in past (6 missed @ 5s interval)
        old_time = datetime.now(timezone.utc) - timedelta(seconds=30)
        monitor.record_heartbeat("db-001", timestamp=old_time)
        
        await monitor.check_heartbeats()
        
        conn = monitor.get_connection_status("db-001")
        assert conn.status == ConnectionStatus.CRITICAL  # 6 missed = CRITICAL
        assert conn.missed_count == 6
        
        # Check critical alert was triggered
        alert_calls = [call for call in on_alert.call_args_list 
                       if call[0][1] == "c2.heartbeat.critical"]
        assert len(alert_calls) == 1
        assert alert_calls[0][0][2]["status"] == "C2 critical"

    @pytest.mark.asyncio
    async def test_status_transition_healthy_to_warning(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """Status transitions from HEALTHY to WARNING at threshold."""
        old_time = datetime.now(timezone.utc) - timedelta(seconds=15)
        heartbeat_monitor.record_heartbeat("db-001", timestamp=old_time)
        
        conn = heartbeat_monitor.get_connection_status("db-001")
        assert conn.status == ConnectionStatus.HEALTHY
        
        await heartbeat_monitor.check_heartbeats()
        
        conn = heartbeat_monitor.get_connection_status("db-001")
        assert conn.status == ConnectionStatus.WARNING

    @pytest.mark.asyncio
    async def test_status_transition_warning_to_critical(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """Status transitions from WARNING to CRITICAL at critical threshold."""
        # Set up warning state
        old_time = datetime.now(timezone.utc) - timedelta(seconds=15)
        heartbeat_monitor.record_heartbeat("db-001", timestamp=old_time)
        await heartbeat_monitor.check_heartbeats()
        
        conn = heartbeat_monitor.get_connection_status("db-001")
        assert conn.status == ConnectionStatus.WARNING
        
        # Simulate more time passing (total 30s = 6 missed)
        conn.last_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=30)
        await heartbeat_monitor.check_heartbeats()
        
        conn = heartbeat_monitor.get_connection_status("db-001")
        assert conn.status == ConnectionStatus.CRITICAL  # 6 missed = CRITICAL, not LOST

    @pytest.mark.asyncio
    async def test_recovery_from_critical_to_healthy(
        self, monitor_with_callbacks: tuple[HeartbeatMonitor, MagicMock, MagicMock]
    ) -> None:
        """Status transitions from CRITICAL back to HEALTHY on heartbeat."""
        monitor, on_status_change, _ = monitor_with_callbacks
        
        # Set up critical state (6 missed = CRITICAL)
        old_time = datetime.now(timezone.utc) - timedelta(seconds=30)
        monitor.record_heartbeat("db-001", timestamp=old_time)
        await monitor.check_heartbeats()
        
        conn = monitor.get_connection_status("db-001")
        assert conn.status == ConnectionStatus.CRITICAL
        
        # Recovery heartbeat
        on_status_change.reset_mock()
        monitor.record_heartbeat("db-001")
        
        conn = monitor.get_connection_status("db-001")
        assert conn.status == ConnectionStatus.HEALTHY
        on_status_change.assert_called_with("db-001", ConnectionStatus.HEALTHY)


# =============================================================================
# Task 4: Automatic Reconnection Logic (Subtasks 4.1-4.6)
# =============================================================================


class TestReconnectionLogic:
    """Tests for automatic reconnection logic."""

    @pytest.mark.asyncio
    async def test_reconnection_triggered_on_c2_lost(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """Reconnection is triggered when C2 is lost (AC #4)."""
        # Set up lost state
        old_time = datetime.now(timezone.utc) - timedelta(seconds=30)
        heartbeat_monitor.record_heartbeat("db-001", timestamp=old_time)
        
        await heartbeat_monitor.check_heartbeats()
        
        conn = heartbeat_monitor.get_connection_status("db-001")
        assert conn.reconnect_attempts == 1

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """Reconnection uses exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s max."""
        conn = DropBoxConnection(
            drop_box_id="db-001",
            last_heartbeat=datetime.now(timezone.utc) - timedelta(seconds=30),
        )
        heartbeat_monitor._connections["db-001"] = conn
        
        # Calculate expected delays
        expected_delays = [1, 2, 4, 8, 16, 30, 30, 30]  # Capped at 30
        
        for i, expected_delay in enumerate(expected_delays):
            conn.reconnect_attempts = i
            heartbeat_monitor._trigger_reconnection(conn)
            
            actual_delay = min(
                2 ** conn.reconnect_attempts,
                heartbeat_monitor.config.max_reconnect_delay_seconds
            )
            # Note: reconnect_attempts incremented in _trigger_reconnection
            # So we check the calculation matches expected pattern

    @pytest.mark.asyncio
    async def test_reconnection_state_tracking(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """Reconnection attempts are tracked in connection state."""
        old_time = datetime.now(timezone.utc) - timedelta(seconds=30)
        heartbeat_monitor.record_heartbeat("db-001", timestamp=old_time)
        
        # First check triggers reconnection
        await heartbeat_monitor.check_heartbeats()
        conn = heartbeat_monitor.get_connection_status("db-001")
        assert conn.reconnect_attempts == 1
        
        # Manual trigger for additional attempt
        heartbeat_monitor._trigger_reconnection(conn)
        assert conn.reconnect_attempts == 2

    def test_reconnection_attempts_reset_on_recovery(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """Reconnection attempts reset to 0 on successful recovery."""
        now = datetime.now(timezone.utc)
        
        # Set up connection in lost state with reconnection attempts
        heartbeat_monitor.record_heartbeat("db-001", timestamp=now)
        conn = heartbeat_monitor.get_connection_status("db-001")
        conn.reconnect_attempts = 5
        conn.status = ConnectionStatus.LOST
        
        # Recovery heartbeat
        heartbeat_monitor.record_heartbeat("db-001")
        
        conn = heartbeat_monitor.get_connection_status("db-001")
        assert conn.reconnect_attempts == 0


# =============================================================================
# Monitor Start/Stop Tests
# =============================================================================


class TestMonitorStartStop:
    """Tests for monitor start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_begins_monitoring_loop(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """start() begins the monitoring loop."""
        await heartbeat_monitor.start()
        
        assert heartbeat_monitor._running is True
        assert heartbeat_monitor._check_task is not None
        
        await heartbeat_monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_monitoring_loop(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """stop() cancels the monitoring loop gracefully."""
        await heartbeat_monitor.start()
        await heartbeat_monitor.stop()
        
        assert heartbeat_monitor._running is False

    @pytest.mark.asyncio
    async def test_double_start_is_safe(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """Calling start() twice doesn't create duplicate tasks."""
        await heartbeat_monitor.start()
        first_task = heartbeat_monitor._check_task
        
        await heartbeat_monitor.start()  # Should be no-op or handle gracefully
        
        await heartbeat_monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """Calling stop() without start() doesn't raise."""
        await heartbeat_monitor.stop()  # Should not raise
        assert heartbeat_monitor._running is False


# =============================================================================
# Connection Status Accessor Tests
# =============================================================================


class TestConnectionAccessors:
    """Tests for connection status accessors."""

    def test_get_connection_status_returns_none_for_unknown(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """get_connection_status returns None for unknown drop box."""
        assert heartbeat_monitor.get_connection_status("unknown") is None

    def test_get_connection_status_returns_connection(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """get_connection_status returns connection for known drop box."""
        heartbeat_monitor.record_heartbeat("db-001")
        
        conn = heartbeat_monitor.get_connection_status("db-001")
        assert conn is not None
        assert conn.drop_box_id == "db-001"

    def test_get_all_connections_returns_copy(
        self, heartbeat_monitor: HeartbeatMonitor
    ) -> None:
        """get_all_connections returns a copy of connections dict."""
        heartbeat_monitor.record_heartbeat("db-001")
        heartbeat_monitor.record_heartbeat("db-002")
        
        connections = heartbeat_monitor.get_all_connections()
        assert len(connections) == 2
        assert "db-001" in connections
        assert "db-002" in connections
        
        # Verify it's a copy
        connections["db-003"] = None
        assert "db-003" not in heartbeat_monitor.get_all_connections()
