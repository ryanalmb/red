"""TUI Client for Daemon Communication.

This module provides the TUI-side client for connecting to the Cyber-Red daemon
via Unix socket and receiving streaming events.

Usage:
    from cyberred.tui.daemon_client import TUIClient

    client = TUIClient()
    await client.connect(Path("/var/run/cyber-red/daemon.sock"))
    
    async for event in client.attach("engagement-123"):
        print(f"Event: {event.event_type}")
    
    await client.detach()
    await client.close()
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncIterator, Optional, Any

import structlog

from cyberred.daemon.ipc import (
    IPCCommand,
    IPCRequest,
    IPCResponse,
    build_request,
    encode_message,
    decode_message,
)
from cyberred.daemon.streaming import (
    StreamEvent,
    StreamEventType,
    decode_stream_event,
)
from cyberred.tui.catchup import CatchupManager, CatchupEvent, CatchupEventType

log = structlog.get_logger()


class DaemonConnectionError(Exception):
    """Raised when connection to daemon fails."""

    pass


class DaemonNotRunningError(DaemonConnectionError):
    """Raised when daemon is not running (socket doesn't exist)."""

    pass


class EngagementError(Exception):
    """Raised when engagement operation fails."""

    pass


class TUIClient:
    """Client for TUI-to-daemon communication over Unix socket.

    This client handles:
    - Connecting to the daemon via Unix socket
    - Attaching to engagements and receiving streaming events
    - Detaching from engagements
    - Measuring attach latency (NFR32: <2s)
    - Stale state detection (Story 9.7: AC #6, #7)

    Attributes:
        socket_path: Path to the daemon Unix socket.
        connected: Whether the client is connected.
        attached: Whether the client is attached to an engagement.
        engagement_id: Currently attached engagement ID (if any).
        subscription_id: Current subscription ID (if attached).
        is_stale: Whether daemon connection is stale (no activity for 60s+).
        last_activity_time: Datetime of last event received.
        seconds_since_activity: Seconds since last event received.
    """

    # Timeout for reading events (slightly longer than server heartbeat of 30s)
    HEARTBEAT_TIMEOUT: float = 35.0
    
    # Stale state threshold (Story 9.7: AC #6)
    STALE_THRESHOLD_SECONDS: float = 60.0

    def __init__(self) -> None:
        """Initialize TUI client (not connected yet)."""
        self._socket_path: Optional[Path] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._engagement_id: Optional[str] = None
        self._subscription_id: Optional[str] = None
        self._attach_latency_ms: Optional[float] = None
        self._streaming: bool = False
        self._last_activity_time: float = 0.0  # Story 9.7: Track last event timestamp
        # Story 11.5: CatchupManager for event replay on reattach
        self._catchup_manager: CatchupManager = CatchupManager()

    @property
    def connected(self) -> bool:
        """Return True if connected to daemon."""
        return self._writer is not None and not self._writer.is_closing()

    @property
    def attached(self) -> bool:
        """Return True if attached to an engagement."""
        return self._subscription_id is not None

    @property
    def engagement_id(self) -> Optional[str]:
        """Return currently attached engagement ID."""
        return self._engagement_id

    @property
    def subscription_id(self) -> Optional[str]:
        """Return current subscription ID."""
        return self._subscription_id

    @property
    def attach_latency_ms(self) -> Optional[float]:
        """Return attach latency in milliseconds (after successful attach)."""
        return self._attach_latency_ms

    @property
    def is_stale(self) -> bool:
        """Return True if no activity received for more than 60 seconds (Story 9.7: AC #6).
        
        Returns False if no events have ever been received (never activated).
        Returns False at exactly 60 seconds, True only after 60 seconds.
        """
        if self._last_activity_time == 0.0:
            return False  # Never received any event
        elapsed = time.monotonic() - self._last_activity_time
        # Use > (not >=) so exactly 60s is not stale, only >60s is stale
        return elapsed > self.STALE_THRESHOLD_SECONDS

    @property
    def last_activity_time(self) -> Optional[datetime]:
        """Return datetime of last activity (Story 9.7: AC #7).
        
        Returns:
            Datetime of last event received, or None if no events received.
        """
        if self._last_activity_time == 0.0:
            return None
        # Convert monotonic to wall clock (approximate)
        seconds_ago = time.monotonic() - self._last_activity_time
        return datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)

    @property
    def seconds_since_activity(self) -> float:
        """Return seconds since last activity (Story 9.7: AC #7).
        
        Returns:
            Seconds since last event, or 0.0 if no events ever received.
        """
        if self._last_activity_time == 0.0:
            return 0.0
        return time.monotonic() - self._last_activity_time

    def reset_activity_time(self) -> None:
        """Reset activity time to current time (Story 9.7: AC #7).
        
        Used by refresh action to clear stale state.
        This is the public API for updating activity time externally.
        """
        self._last_activity_time = time.monotonic()

    @property
    def catchup_manager(self) -> CatchupManager:
        """Return the CatchupManager for event replay (Story 11.5: AC #4).
        
        Returns:
            CatchupManager instance for queuing and replaying missed events.
        """
        return self._catchup_manager

    def queue_for_catchup(self, event: StreamEvent) -> None:
        """Queue a stream event for catch-up replay (Story 11.5: AC #4).
        
        Called when TUI is disconnected to buffer events for later replay.
        Converts StreamEvent to CatchupEvent and queues it.
        
        Args:
            event: StreamEvent to queue for replay
        """
        from datetime import datetime
        
        # Map StreamEventType to CatchupEventType
        type_map = {
            StreamEventType.FINDING: CatchupEventType.FINDING,
            StreamEventType.AUTH_REQUEST: CatchupEventType.AUTH_REQUEST,
            StreamEventType.STRATEGY_UPDATE: CatchupEventType.STRATEGY_UPDATE,
            StreamEventType.AGENT_STATUS: CatchupEventType.AGENT_STATE,
        }
        
        catchup_type = type_map.get(event.event_type)
        if catchup_type is None:
            # Skip events that don't need catch-up (heartbeats, etc.)
            return
        
        catchup_event = CatchupEvent(
            event_type=catchup_type,
            timestamp=datetime.now(),
            payload=event.data,
            source=event.data.get("agent_id", "unknown"),
        )
        self._catchup_manager.queue_event(catchup_event)

    async def connect(self, socket_path: Path) -> None:
        """Connect to the daemon via Unix socket.

        Args:
            socket_path: Path to the daemon Unix socket.

        Raises:
            DaemonNotRunningError: If socket doesn't exist.
            DaemonConnectionError: If connection fails.
        """
        if not socket_path.exists():
            raise DaemonNotRunningError(
                f"Daemon not running: socket '{socket_path}' not found"
            )

        try:
            self._reader, self._writer = await asyncio.open_unix_connection(
                str(socket_path)
            )
            self._socket_path = socket_path
            log.info("daemon_connected", socket_path=str(socket_path))

        except (ConnectionRefusedError, OSError) as e:
            raise DaemonConnectionError(f"Failed to connect to daemon: {e}") from e

    async def _send_request(self, command: IPCCommand, **params: Any) -> IPCResponse:
        """Send IPC request and receive response.

        Args:
            command: IPC command to send.
            **params: Command parameters.

        Returns:
            IPCResponse from daemon.

        Raises:
            DaemonConnectionError: If not connected or communication fails.
        """
        if not self.connected:
            raise DaemonConnectionError("Not connected to daemon")

        assert self._reader is not None
        assert self._writer is not None

        try:
            request = build_request(command, **params)
            self._writer.write(encode_message(request))
            await self._writer.drain()

            data = await self._reader.readline()
            if not data:
                raise DaemonConnectionError("Daemon closed connection")

            response = decode_message(data)
            if not isinstance(response, IPCResponse):
                raise DaemonConnectionError("Unexpected response type")

            return response

        except (BrokenPipeError, ConnectionResetError) as e:
            raise DaemonConnectionError(f"Connection lost: {e}") from e

    async def attach(
        self,
        engagement_id: str,
        sync_mode: str = "full",
    ) -> AsyncIterator[StreamEvent]:
        """Attach to an engagement and stream events.

        Sends ENGAGEMENT_ATTACH command, receives initial state snapshot,
        then yields streaming events continuously until detach.

        Args:
            engagement_id: Engagement ID to attach to.
            sync_mode: Sync mode - "full" for complete state with agent/finding
                details, "incremental" for counts only (faster attach).
                Default is "full" for backwards compatibility.

        Yields:
            StreamEvent objects from the daemon.

        Raises:
            DaemonConnectionError: If not connected.
            EngagementError: If engagement not found or invalid state.
        
        Note:
            For incremental mode (Story 9.8):
            - First yield contains: state, agent_count, finding_count
            - TUI becomes operational immediately
            - Full details loaded on-demand when user requests
        
        Raises:
            ValueError: If sync_mode is not 'full' or 'incremental'.
            DaemonConnectionError: If not connected.
            EngagementError: If engagement not found or invalid state.
        """
        # Validate sync_mode parameter
        if sync_mode not in ("full", "incremental"):
            raise ValueError(f"sync_mode must be 'full' or 'incremental', got '{sync_mode}'")
        
        start_time = time.monotonic()

        response = await self._send_request(
            IPCCommand.ENGAGEMENT_ATTACH,
            engagement_id=engagement_id,
            sync_mode=sync_mode,
        )

        if response.status == "error":
            raise EngagementError(response.error or "Attach failed")

        # Extract subscription info from response
        data = response.data or {}
        self._subscription_id = data.get("subscription_id")
        self._engagement_id = engagement_id
        self._streaming = True

        # Calculate attach latency
        self._attach_latency_ms = (time.monotonic() - start_time) * 1000
        log.info(
            "attached_to_engagement",
            engagement_id=engagement_id,
            subscription_id=self._subscription_id,
            attach_latency_ms=round(self._attach_latency_ms, 2),
        )

        # Yield initial state as a STATE_CHANGE event if state is present
        if "state" in data:
            yield StreamEvent(
                event_type=StreamEventType.STATE_CHANGE,
                data={
                    "engagement_id": engagement_id,
                    "state": data.get("state"),
                    "agents": data.get("agents", []),
                    "findings": data.get("findings", []),
                    "agent_count": data.get("agent_count", 0),
                    "finding_count": data.get("finding_count", 0),
                },
            )

        # Stream events until detach or connection closed
        assert self._reader is not None
        while self._streaming:  # pragma: no branch
            try:

                # Read next event with timeout for heartbeat handling
                data_line = await asyncio.wait_for(
                    self._reader.readline(),
                    timeout=self.HEARTBEAT_TIMEOUT,
                )

                if not data_line:
                    log.info("daemon_closed_stream", engagement_id=engagement_id)
                    break

                event = decode_stream_event(data_line)
                self._last_activity_time = time.monotonic()  # Story 9.7: Track activity
                yield event

            except asyncio.TimeoutError:
                # No event received - connection might be stale
                log.warning("stream_timeout", engagement_id=engagement_id)
                break
            except Exception as e:
                log.error("stream_error", engagement_id=engagement_id, error=str(e))
                break

        # Clean up streaming state
        self._streaming = False

    async def detach(self) -> bool:
        """Detach from current engagement.

        Sends ENGAGEMENT_DETACH command to stop streaming.
        Safe to call even if not attached (no-op).
        
        Per Story 9.9 FR59: Detach without stopping engagement.
        SSH disconnect behaves same as Ctrl+D.

        Returns:
            True if detach successful or already detached, False on error.
        """
        if not self._subscription_id:
            log.debug("detach_no_subscription")
            return True  # Already detached is success

        if not self.connected:
            log.warning("detach_not_connected")
            self._cleanup_attachment()
            return True  # Connection lost counts as successful detach

        try:
            response = await self._send_request(
                IPCCommand.ENGAGEMENT_DETACH,
                subscription_id=self._subscription_id,
                engagement_id=self._engagement_id,
            )

            if response.status == "ok":
                log.info(
                    "detached_from_engagement",
                    engagement_id=self._engagement_id,
                    subscription_id=self._subscription_id,
                )
                return True
            else:
                log.warning(
                    "detach_error",
                    engagement_id=self._engagement_id,
                    error=response.error,
                )
                return False

        except DaemonConnectionError as e:
            log.warning("detach_connection_error", error=str(e))
            return True  # Connection error during detach still counts as detached

        finally:
            self._cleanup_attachment()

    def _cleanup_attachment(self) -> None:
        """Clean up attachment state."""
        self._engagement_id = None
        self._subscription_id = None
        self._streaming = False
        self._attach_latency_ms = None

    async def send_kill_command(self) -> bool:
        """Send kill switch command to daemon (Story 10.4: AC #5).
        
        Triggers the kill switch on the daemon, which will:
        1. Set the frozen flag on the engagement
        2. Broadcast kill to all agents
        3. Stop all containers
        
        Returns:
            True if kill command successful, False on error.
        """
        if not self.connected:
            log.warning("send_kill_not_connected")
            return False
        
        try:
            response = await self._send_request(
                IPCCommand.KILL,
                engagement_id=self._engagement_id,
            )
            
            if response.status == "ok":
                log.warning(
                    "kill_command_sent",
                    engagement_id=self._engagement_id,
                )
                return True
            else:
                log.error(
                    "kill_command_failed",
                    engagement_id=self._engagement_id,
                    error=response.error,
                )
                return False
                
        except DaemonConnectionError as e:
            log.error("kill_command_connection_error", error=str(e))
            return False

    async def send_auth_response(self, response: dict) -> bool:
        """Send authorization response to daemon (Story 10.2).
        
        Args:
            response: Authorization response dict with decision.
            
        Returns:
            True if response sent successfully, False on error.
        """
        if not self.connected:
            log.warning("send_auth_response_not_connected")
            return False
        
        try:
            ipc_response = await self._send_request(
                IPCCommand.AUTH_RESPONSE,
                engagement_id=self._engagement_id,
                response=response,
            )
            
            return ipc_response.status == "ok"
                
        except DaemonConnectionError as e:
            log.error("auth_response_connection_error", error=str(e))
            return False

    async def close(self) -> None:
        """Close the daemon connection.

        Detaches from any engagement first if attached.
        """
        if self.attached:
            await self.detach()

        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass  # Ignore close errors

        self._reader = None
        self._writer = None
        self._socket_path = None
        log.info("daemon_disconnected")

    async def __aenter__(self) -> "TUIClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - closes connection."""
        await self.close()
