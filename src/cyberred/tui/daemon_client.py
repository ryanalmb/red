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
    decode_stream_event,
)

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

    Attributes:
        socket_path: Path to the daemon Unix socket.
        connected: Whether the client is connected.
        attached: Whether the client is attached to an engagement.
        engagement_id: Currently attached engagement ID (if any).
        subscription_id: Current subscription ID (if attached).
    """

    
    # Timeout for reading events (slightly longer than server heartbeat of 30s)
    HEARTBEAT_TIMEOUT: float = 35.0

    def __init__(self) -> None:
        """Initialize TUI client (not connected yet)."""
        self._socket_path: Optional[Path] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._engagement_id: Optional[str] = None
        self._subscription_id: Optional[str] = None
        self._attach_latency_ms: Optional[float] = None
        self._streaming: bool = False

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

    async def attach(self, engagement_id: str) -> AsyncIterator[StreamEvent]:
        """Attach to an engagement and stream events.

        Sends ENGAGEMENT_ATTACH command, receives initial state snapshot,
        then yields streaming events continuously until detach.

        Args:
            engagement_id: Engagement ID to attach to.

        Yields:
            StreamEvent objects from the daemon.

        Raises:
            DaemonConnectionError: If not connected.
            EngagementError: If engagement not found or invalid state.
        """
        start_time = time.monotonic()

        response = await self._send_request(
            IPCCommand.ENGAGEMENT_ATTACH,
            engagement_id=engagement_id,
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
                event_type="state_change",
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

    async def detach(self) -> None:
        """Detach from current engagement.

        Sends ENGAGEMENT_DETACH command to stop streaming.
        Safe to call even if not attached (no-op).
        """
        if not self._subscription_id:
            log.debug("detach_no_subscription")
            return

        if not self.connected:
            log.warning("detach_not_connected")
            self._cleanup_attachment()
            return

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
            else:
                log.warning(
                    "detach_error",
                    engagement_id=self._engagement_id,
                    error=response.error,
                )

        except DaemonConnectionError as e:
            log.warning("detach_connection_error", error=str(e))

        finally:
            self._cleanup_attachment()

    def _cleanup_attachment(self) -> None:
        """Clean up attachment state."""
        self._engagement_id = None
        self._subscription_id = None
        self._streaming = False
        self._attach_latency_ms = None

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
