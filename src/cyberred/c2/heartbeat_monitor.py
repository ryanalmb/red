"""Heartbeat monitoring for drop box C2 connections.

Story 12.4: Heartbeat Monitoring
Per FR24: Commands, results, and heartbeats have consistent format.
Per NFR11: C2 link health monitoring with immediate alerts.

Thresholds:
- Heartbeat interval: 5 seconds
- Warning threshold: 3 missed heartbeats (15s) - AC #2
- Critical threshold: 6 missed heartbeats (30s) - AC #3
- Max reconnect delay: 30 seconds (per architecture)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Optional

import structlog

if TYPE_CHECKING:
    from cyberred.core.events import EventBus

log = structlog.get_logger()


class ConnectionStatus(Enum):
    """Drop box connection status based on heartbeat monitoring."""

    HEALTHY = "healthy"
    WARNING = "warning"  # 3+ missed heartbeats (AC #2)
    CRITICAL = "critical"  # 6+ missed heartbeats (AC #3) - triggers reconnection
    LOST = "lost"  # Connection considered dead after reconnection fails


@dataclass
class DropBoxConnection:
    """Track per-drop-box connection state.

    Attributes:
        drop_box_id: Unique identifier for the drop box.
        last_heartbeat: Timestamp of last received heartbeat.
        missed_count: Number of missed heartbeat intervals.
        status: Current connection status.
        reconnect_attempts: Number of reconnection attempts made.
        latency_ms: Last measured heartbeat latency in milliseconds.
    """

    drop_box_id: str
    last_heartbeat: datetime
    missed_count: int = 0
    status: ConnectionStatus = ConnectionStatus.HEALTHY
    reconnect_attempts: int = 0
    latency_ms: Optional[int] = None


@dataclass
class HeartbeatMonitorConfig:
    """Configuration for heartbeat monitoring.

    Attributes:
        heartbeat_interval_seconds: Expected interval between heartbeats (default: 5s).
        warning_threshold: Missed count to trigger warning (default: 3, AC #2).
        critical_threshold: Missed count to trigger critical (default: 6, AC #3).
        lost_threshold: Missed count to consider connection lost (default: 10).
        max_reconnect_delay_seconds: Maximum delay for reconnection backoff (default: 30s).
        max_reconnect_attempts: Max reconnection attempts before marking LOST (default: 5).
    """

    heartbeat_interval_seconds: int = 5
    warning_threshold: int = 3  # AC #2: 3 missed = warning
    critical_threshold: int = 6  # AC #3: 6 missed = critical, triggers reconnection
    lost_threshold: int = 10  # 10 missed = connection considered lost
    max_reconnect_delay_seconds: int = 30  # Per architecture
    max_reconnect_attempts: int = 5  # Give up after 5 reconnection attempts


class HeartbeatMonitor:
    """Monitor drop box heartbeats and trigger alerts/reconnection.

    Per FR24 and NFR11: Immediate C2 link health monitoring.

    Usage:
        monitor = HeartbeatMonitor(
            config=HeartbeatMonitorConfig(),
            event_bus=event_bus,  # For c2.heartbeat.* events
            on_reconnect=handle_reconnect,
        )
        await monitor.start()

        # Called when heartbeat received from C2Server
        monitor.record_heartbeat("drop-box-001", latency_ms=50)

        await monitor.stop()

    Attributes:
        config: HeartbeatMonitorConfig with thresholds.
    """

    def __init__(
        self,
        config: Optional[HeartbeatMonitorConfig] = None,
        event_bus: Optional["EventBus"] = None,
        on_status_change: Optional[Callable[[str, ConnectionStatus], None]] = None,
        on_alert: Optional[Callable[[str, str, dict[str, Any]], None]] = None,
        on_reconnect: Optional[Callable[[str, int, int], None]] = None,
    ) -> None:
        """Initialize HeartbeatMonitor.

        Args:
            config: Optional configuration (uses defaults if not provided).
            event_bus: Optional EventBus for publishing c2.heartbeat.* events (Task 3.5).
            on_status_change: Callback(drop_box_id, new_status) for status transitions.
            on_alert: Callback(drop_box_id, event_type, payload) for alerts.
            on_reconnect: Callback(drop_box_id, attempt, delay_seconds) for reconnection (AC #4).
        """
        self.config = config or HeartbeatMonitorConfig()
        self._connections: dict[str, DropBoxConnection] = {}
        self._event_bus = event_bus
        self._on_status_change = on_status_change
        self._on_alert = on_alert
        self._on_reconnect = on_reconnect
        self._running = False
        self._check_task: Optional[asyncio.Task[None]] = None

    def record_heartbeat(
        self,
        drop_box_id: str,
        timestamp: Optional[datetime] = None,
        latency_ms: Optional[int] = None,
    ) -> None:
        """Record heartbeat from drop box.

        Resets missed count, updates latency, transitions to HEALTHY if recovered.

        Args:
            drop_box_id: Identifier of the drop box.
            timestamp: Heartbeat timestamp (uses current time if not provided).
            latency_ms: Measured latency in milliseconds.
        """
        now = timestamp or datetime.now(timezone.utc)

        if drop_box_id not in self._connections:
            # Register new drop box connection
            self._connections[drop_box_id] = DropBoxConnection(
                drop_box_id=drop_box_id,
                last_heartbeat=now,
                latency_ms=latency_ms,
            )
            log.info("c2_dropbox_registered", drop_box_id=drop_box_id)
        else:
            # Update existing connection
            conn = self._connections[drop_box_id]
            old_status = conn.status

            conn.last_heartbeat = now
            conn.missed_count = 0
            conn.latency_ms = latency_ms
            conn.status = ConnectionStatus.HEALTHY
            conn.reconnect_attempts = 0

            # Notify on recovery
            if old_status != ConnectionStatus.HEALTHY:
                log.info(
                    "c2_dropbox_recovered",
                    drop_box_id=drop_box_id,
                    from_status=old_status.value,
                )
                if self._on_status_change:
                    self._on_status_change(drop_box_id, ConnectionStatus.HEALTHY)

    async def check_heartbeats(self) -> None:
        """Check all connections for missed heartbeats.

        Called on interval (5s). Updates missed counts and triggers alerts.
        """
        now = datetime.now(timezone.utc)
        interval = self.config.heartbeat_interval_seconds

        for drop_box_id, conn in self._connections.items():
            elapsed = (now - conn.last_heartbeat).total_seconds()
            expected_heartbeats = int(elapsed / interval)

            if expected_heartbeats > conn.missed_count:
                conn.missed_count = expected_heartbeats
                self._evaluate_status(conn)

    def _evaluate_status(self, conn: DropBoxConnection) -> None:
        """Evaluate and update connection status based on missed heartbeats.

        Status transitions:
        - HEALTHY -> WARNING at warning_threshold (3 missed)
        - WARNING -> CRITICAL at critical_threshold (6 missed), triggers reconnection
        - CRITICAL -> LOST at lost_threshold (10 missed) or max reconnect attempts

        Args:
            conn: Connection to evaluate.
        """
        old_status = conn.status

        # Check for LOST condition first (highest priority)
        if (conn.missed_count >= self.config.lost_threshold or 
            conn.reconnect_attempts >= self.config.max_reconnect_attempts):
            if conn.status != ConnectionStatus.LOST:
                conn.status = ConnectionStatus.LOST
                self._trigger_lost_alert(conn)
        # Check for CRITICAL condition (AC #3: 6 missed = critical)
        elif conn.missed_count >= self.config.critical_threshold:
            if conn.status != ConnectionStatus.CRITICAL:
                conn.status = ConnectionStatus.CRITICAL
                self._trigger_critical_alert(conn)
                self._trigger_reconnection(conn)
            elif conn.status == ConnectionStatus.CRITICAL:
                # Already critical, trigger another reconnection attempt
                self._trigger_reconnection(conn)
        # Check for WARNING condition (AC #2: 3 missed = warning)
        elif conn.missed_count >= self.config.warning_threshold:
            if old_status == ConnectionStatus.HEALTHY:
                conn.status = ConnectionStatus.WARNING
                self._trigger_warning_alert(conn)

        if old_status != conn.status and self._on_status_change:
            self._on_status_change(conn.drop_box_id, conn.status)

    async def _publish_event(self, channel: str, payload: dict[str, Any]) -> None:
        """Publish event to EventBus if available (Task 3.5).

        Args:
            channel: Event channel (e.g., "c2.heartbeat.warning").
            payload: Event payload dict.
        """
        if self._event_bus:
            try:
                # EventBus expects c2:heartbeat:* pattern channels (Story 12.4)
                # Convert "c2.heartbeat.warning" -> "c2:heartbeat:warning"
                event_channel = channel.replace(".", ":")
                await self._event_bus.publish(event_channel, payload)
                log.debug(
                    "event_published",
                    channel=event_channel,
                    drop_box_id=payload.get("drop_box_id"),
                )
            except Exception as e:
                log.warning(
                    "event_publish_failed",
                    channel=channel,
                    error=str(e),
                )

    def _trigger_warning_alert(self, conn: DropBoxConnection) -> None:
        """Trigger warning alert for 3+ missed heartbeats (AC #2).

        Args:
            conn: Connection with warning condition.
        """
        payload: dict[str, Any] = {
            "drop_box_id": conn.drop_box_id,
            "missed_count": conn.missed_count,
            "threshold": self.config.warning_threshold,
            "status": "warning",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        log.warning(
            "c2_heartbeat_warning",
            drop_box_id=conn.drop_box_id,
            missed_count=conn.missed_count,
        )
        
        # Publish to EventBus (Task 3.5)
        if self._event_bus:
            asyncio.create_task(self._publish_event("c2.heartbeat.warning", payload))
        
        # Legacy callback support
        if self._on_alert:
            self._on_alert(conn.drop_box_id, "c2.heartbeat.warning", payload)

    def _trigger_critical_alert(self, conn: DropBoxConnection) -> None:
        """Trigger critical alert for 6+ missed heartbeats (AC #3).

        Args:
            conn: Connection with critical condition.
        """
        payload: dict[str, Any] = {
            "drop_box_id": conn.drop_box_id,
            "missed_count": conn.missed_count,
            "threshold": self.config.critical_threshold,
            "status": "C2 critical",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        log.error(
            "c2_heartbeat_critical",
            drop_box_id=conn.drop_box_id,
            missed_count=conn.missed_count,
            status="C2 critical",
        )
        
        # Publish to EventBus (Task 3.5)
        if self._event_bus:
            asyncio.create_task(self._publish_event("c2.heartbeat.critical", payload))
        
        # Legacy callback support
        if self._on_alert:
            self._on_alert(conn.drop_box_id, "c2.heartbeat.critical", payload)

    def _trigger_lost_alert(self, conn: DropBoxConnection) -> None:
        """Trigger lost alert when connection is considered dead.

        Args:
            conn: Connection with lost condition.
        """
        payload: dict[str, Any] = {
            "drop_box_id": conn.drop_box_id,
            "missed_count": conn.missed_count,
            "reconnect_attempts": conn.reconnect_attempts,
            "status": "C2 lost",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        log.error(
            "c2_heartbeat_lost",
            drop_box_id=conn.drop_box_id,
            missed_count=conn.missed_count,
            reconnect_attempts=conn.reconnect_attempts,
            status="C2 lost",
        )
        
        # Publish to EventBus
        if self._event_bus:
            asyncio.create_task(self._publish_event("c2.heartbeat.lost", payload))
        
        # Legacy callback support
        if self._on_alert:
            self._on_alert(conn.drop_box_id, "c2.heartbeat.lost", payload)

    def _trigger_reconnection(self, conn: DropBoxConnection) -> None:
        """Trigger automatic reconnection (AC #4).

        Uses exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s.
        Publishes c2.reconnecting event (Task 4.5).

        Args:
            conn: Connection requiring reconnection.
        """
        # Don't attempt reconnection if max attempts reached
        if conn.reconnect_attempts >= self.config.max_reconnect_attempts:
            log.warning(
                "c2_reconnection_max_attempts",
                drop_box_id=conn.drop_box_id,
                attempts=conn.reconnect_attempts,
            )
            return
        
        conn.reconnect_attempts += 1
        delay = min(
            2 ** (conn.reconnect_attempts - 1),
            self.config.max_reconnect_delay_seconds,
        )
        
        payload: dict[str, Any] = {
            "drop_box_id": conn.drop_box_id,
            "attempt": conn.reconnect_attempts,
            "delay_seconds": delay,
            "max_attempts": self.config.max_reconnect_attempts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        log.info(
            "c2_reconnection_triggered",
            drop_box_id=conn.drop_box_id,
            attempt=conn.reconnect_attempts,
            delay_seconds=delay,
        )
        
        # Publish c2.reconnecting event (Task 4.5)
        if self._event_bus:
            asyncio.create_task(self._publish_event("c2.reconnecting", payload))
        
        # Notify reconnection callback for C2Server to handle actual reconnection
        if self._on_reconnect:
            self._on_reconnect(conn.drop_box_id, conn.reconnect_attempts, delay)

    async def start(self) -> None:
        """Start heartbeat monitoring loop."""
        if self._running:
            return  # Already running

        self._running = True
        self._check_task = asyncio.create_task(self._monitor_loop())
        log.info("heartbeat_monitor_started")

    async def stop(self) -> None:
        """Stop heartbeat monitoring loop gracefully."""
        if not self._running:
            return

        self._running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        log.info("heartbeat_monitor_stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop - checks heartbeats every interval."""
        while self._running:
            await asyncio.sleep(self.config.heartbeat_interval_seconds)
            await self.check_heartbeats()

    def get_connection_status(self, drop_box_id: str) -> Optional[DropBoxConnection]:
        """Get connection status for specific drop box.

        Args:
            drop_box_id: Drop box identifier.

        Returns:
            DropBoxConnection if found, None otherwise.
        """
        return self._connections.get(drop_box_id)

    def get_all_connections(self) -> dict[str, DropBoxConnection]:
        """Get all tracked connections.

        Returns:
            Copy of connections dictionary.
        """
        return self._connections.copy()

    @property
    def is_running(self) -> bool:
        """Check if the heartbeat monitor is currently running.

        Returns:
            True if monitor loop is active, False otherwise.
        """
        return self._running
