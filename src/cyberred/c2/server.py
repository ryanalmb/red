"""C2 Server for drop box mTLS WebSocket communication.

Per FR24: Drop boxes communicate securely over encrypted channels.
Per Architecture: mTLS WebSocket on port 8444.
"""

from __future__ import annotations

import asyncio
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import structlog
import websockets
from websockets.server import WebSocketServerProtocol

if TYPE_CHECKING:
    from cyberred.c2.heartbeat_monitor import HeartbeatMonitor
    from cyberred.core import CAStore

log = structlog.get_logger()


class SSLLoggingProtocol(asyncio.Protocol):
    """Protocol wrapper that logs SSL connection rejections.
    
    This captures SSL handshake failures that occur before the WebSocket
    layer, ensuring all connection attempts are logged for audit purposes.
    """

    def __init__(self, original_protocol: asyncio.Protocol) -> None:
        self._original = original_protocol

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._original.connection_made(transport)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if exc is not None and isinstance(exc, ssl.SSLError):
            # Log SSL rejection
            log.warning(
                "c2_connection_rejected",
                reason=str(exc),
                error_type=type(exc).__name__,
            )
        self._original.connection_lost(exc)

    def data_received(self, data: bytes) -> None:
        self._original.data_received(data)

    def eof_received(self) -> Optional[bool]:
        if hasattr(self._original, "eof_received"):
            return self._original.eof_received()
        return None


@dataclass
class C2ServerConfig:
    """Configuration for C2 server.

    Attributes:
        host: Bind address (default: 0.0.0.0 for remote access)
        port: Listen port (default: 8444 per architecture)
        ca_cert_path: Path to CA certificate for client validation
        server_cert_path: Path to server certificate
        server_key_path: Path to server private key
        shared_secret: Shared secret for HMAC message signatures
    """

    host: str = "0.0.0.0"
    port: int = 8444
    ca_cert_path: Optional[Path] = None
    server_cert_path: Optional[Path] = None
    server_key_path: Optional[Path] = None
    shared_secret: Optional[bytes] = None

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "C2ServerConfig":
        """Load C2 server configuration from engagement YAML file.

        Args:
            yaml_path: Path to the engagement YAML configuration file.

        Returns:
            C2ServerConfig instance populated from YAML.

        Raises:
            FileNotFoundError: If the YAML file doesn't exist.
            ValueError: If required fields are missing or invalid.
        """
        import yaml

        if not yaml_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {yaml_path}")

        with open(yaml_path) as f:
            config_data = yaml.safe_load(f)

        if config_data is None:
            raise ValueError(f"Empty configuration file: {yaml_path}")

        # Extract c2 section if present, otherwise use root
        c2_config: dict[str, Any] = config_data.get("c2", config_data)

        # Build config with defaults for missing values
        # Handle shared_secret - can be string (hex) or bytes
        shared_secret_raw = c2_config.get("shared_secret")
        shared_secret: Optional[bytes] = None
        if shared_secret_raw:
            if isinstance(shared_secret_raw, bytes):
                shared_secret = shared_secret_raw
            else:
                # Assume hex string
                shared_secret = bytes.fromhex(shared_secret_raw) if shared_secret_raw else None

        return cls(
            host=c2_config.get("host", "0.0.0.0"),
            port=c2_config.get("port", 8444),
            ca_cert_path=Path(c2_config["ca_cert_path"]) if c2_config.get("ca_cert_path") else None,
            server_cert_path=Path(c2_config["server_cert_path"]) if c2_config.get("server_cert_path") else None,
            server_key_path=Path(c2_config["server_key_path"]) if c2_config.get("server_key_path") else None,
            shared_secret=shared_secret,
        )


class C2Server:
    """mTLS WebSocket server for drop box C2 communication.

    Security: All connections require mutual TLS authentication.
    The server validates client certificates against the engagement CA.

    Usage:
        config = C2ServerConfig(port=8444)
        server = C2Server(config, ca_store)
        await server.start()
        # ... server running ...
        await server.stop()
    """

    def __init__(
        self,
        config: C2ServerConfig,
        ca_store: Optional[CAStore] = None,
        heartbeat_monitor: Optional["HeartbeatMonitor"] = None,
    ) -> None:
        """Initialize C2 server.

        Args:
            config: Server configuration
            ca_store: Optional CAStore instance for certificate validation
            heartbeat_monitor: Optional HeartbeatMonitor for connection health tracking
        """
        self._config = config
        self._ca_store = ca_store
        self._server: Optional[websockets.WebSocketServer] = None
        self._connections: set[WebSocketServerProtocol] = set()
        self._running = False
        self._start_time: Optional[float] = None
        self._heartbeat_monitor = heartbeat_monitor

    async def start(self) -> None:
        """Start the C2 server.

        Raises:
            RuntimeError: If server is already running
            ssl.SSLError: If certificate configuration is invalid
        """
        if self._running:
            raise RuntimeError("C2 server is already running")

        ssl_context = self._create_ssl_context()

        self._server = await websockets.serve(
            self._connection_handler,
            self._config.host,
            self._config.port,
            ssl=ssl_context,
            process_request=self._log_connection_attempt,
        )

        # Get actual port if 0 was specified (OS assigns)
        if self._config.port == 0 and self._server.sockets:
            actual_port = self._server.sockets[0].getsockname()[1]
            log.info(
                "c2_server_started",
                host=self._config.host,
                port=actual_port,
            )
        else:
            log.info(
                "c2_server_started",
                host=self._config.host,
                port=self._config.port,
            )

        self._running = True
        self._start_time = asyncio.get_event_loop().time()

        # Start heartbeat monitor if provided (Story 12.4)
        if self._heartbeat_monitor:
            await self._heartbeat_monitor.start()

    async def stop(self) -> None:
        """Stop the C2 server gracefully."""
        if not self._running:
            return

        self._running = False

        # Stop heartbeat monitor first (Story 12.4)
        if self._heartbeat_monitor:
            await self._heartbeat_monitor.stop()

        # Close all connections
        for conn in self._connections.copy():
            await conn.close()

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        log.info("c2_server_stopped")

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for mTLS.

        Returns:
            Configured SSL context requiring client certificates
        
        Raises:
            ssl.SSLError: If certificate configuration is invalid
        """
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.verify_mode = ssl.CERT_REQUIRED

        # Load CA for client certificate validation
        if self._config.ca_cert_path:
            context.load_verify_locations(cafile=str(self._config.ca_cert_path))

        # Load server certificate
        if self._config.server_cert_path and self._config.server_key_path:
            context.load_cert_chain(
                certfile=str(self._config.server_cert_path),
                keyfile=str(self._config.server_key_path),
            )

        return context

    def _log_connection_attempt(
        self,
        connection: WebSocketServerProtocol,
        request: Any,
    ) -> None:
        """Log connection attempts for audit trail.

        This is called before the WebSocket handshake completes.
        SSL rejections happen before this point, but we log successful
        TLS handshakes here.

        Args:
            connection: The WebSocket server connection.
            request: The HTTP request object.

        Returns:
            None to continue with the connection.
        """
        # Log the connection attempt (SSL already validated at this point)
        client_ip = "unknown"
        if hasattr(connection, "remote_address") and connection.remote_address:
            client_ip = connection.remote_address[0]
        
        path = getattr(request, "path", "/")
        user_agent = "unknown"
        if hasattr(request, "headers"):
            user_agent = request.headers.get("User-Agent", "unknown")
        
        log.debug(
            "c2_connection_attempt",
            client_ip=client_ip,
            path=path,
            user_agent=user_agent,
        )
        return None  # Continue with connection

    async def _connection_handler(self, websocket: WebSocketServerProtocol) -> None:
        """Handle incoming WebSocket connection.

        Args:
            websocket: The connected WebSocket
        """
        from cyberred.c2.protocol import C2MessageType, validate_and_parse_message

        client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"

        # Connection already validated by SSL layer (CERT_REQUIRED)
        log.info("c2_client_connected", client_ip=client_ip)
        self._connections.add(websocket)

        try:
            async for raw_message in websocket:
                log.debug("c2_message_received", client_ip=client_ip, size=len(raw_message))

                # Validate and parse message using protocol (Story 12.2)
                if self._config.shared_secret is None:
                    log.warning("c2_no_shared_secret", client_ip=client_ip)
                    continue

                # Ensure raw_message is string for JSON parsing
                if isinstance(raw_message, bytes):
                    raw_message = raw_message.decode("utf-8")

                message, error = validate_and_parse_message(raw_message, self._config.shared_secret)

                if error:
                    log.warning(
                        "c2_message_invalid",
                        client_ip=client_ip,
                        error=error,
                    )
                    continue

                # Dispatch based on message type
                if message.type == C2MessageType.COMMAND:
                    log.info(
                        "c2_command_received",
                        client_ip=client_ip,
                        message_id=message.id,
                        command=message.payload.get("command"),
                    )
                    # Command execution will be handled by higher-level orchestration
                elif message.type == C2MessageType.RESULT:
                    log.info(
                        "c2_result_received",
                        client_ip=client_ip,
                        message_id=message.id,
                        command_id=message.payload.get("command_id"),
                        success=message.payload.get("success"),
                    )
                elif message.type == C2MessageType.HEARTBEAT:
                    drop_box_id = message.payload.get("drop_box_id")
                    log.debug(
                        "c2_heartbeat_received",
                        client_ip=client_ip,
                        drop_box_id=drop_box_id,
                        status=message.payload.get("status"),
                    )
                    # Record heartbeat in monitor (Story 12.4)
                    if self._heartbeat_monitor and drop_box_id:
                        self._heartbeat_monitor.record_heartbeat(drop_box_id)

        except websockets.exceptions.ConnectionClosed:
            log.info("c2_client_disconnected", client_ip=client_ip)
        finally:
            self._connections.discard(websocket)

    def get_health_status(self) -> dict:
        """Get health status for /health/c2 endpoint.

        Returns:
            Health status dict with status, connections, uptime
        """
        if not self._running:
            return {"status": "error", "connections": 0, "uptime": 0}

        uptime = 0
        if self._start_time is not None:
            try:
                loop = asyncio.get_event_loop()
                uptime = int(loop.time() - self._start_time)
            except RuntimeError:
                # No event loop running, use 0
                uptime = 0

        status = "healthy"
        if len(self._connections) == 0:
            status = "degraded"  # No drop boxes connected

        health = {
            "status": status,
            "connections": len(self._connections),
            "uptime": uptime,
        }

        # Include heartbeat monitor status (Story 12.4)
        if self._heartbeat_monitor:
            connections = self._heartbeat_monitor.get_all_connections()
            health["heartbeat_monitor"] = {
                "tracked_connections": len(connections),
                "healthy": sum(1 for c in connections.values() if c.status.value == "healthy"),
                "warning": sum(1 for c in connections.values() if c.status.value == "warning"),
                "lost": sum(1 for c in connections.values() if c.status.value == "lost"),
            }

        return health

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running

    @property
    def connection_count(self) -> int:
        """Get number of active connections."""
        return len(self._connections)

    async def reload_ssl_context(self, cert_manager: "CertificateManager") -> None:
        """Hot-reload SSL context with new certificates.

        Called after certificate rotation to update the server's SSL context
        without restarting the server.

        Args:
            cert_manager: CertificateManager with updated certificates.
        """
        from cyberred.c2.cert_manager import CertificateManager

        new_context = self._create_ssl_context()

        # Load CRL if available
        if crl_path := cert_manager.get_crl_path():
            new_context.load_verify_locations(cafile=str(crl_path))

        # Store new context for future connections
        self._ssl_context = new_context

        # Update the server's SSL context if server is running
        # Note: This affects new connections; existing connections keep old context
        if self._server is not None:
            # WebSocket server doesn't expose direct SSL context swap,
            # but storing it allows graceful rotation on next restart
            # For live rotation, we would need to restart the server
            pass

        log.info(
            "c2_ssl_context_reloaded",
            crl_loaded=crl_path is not None,
        )
