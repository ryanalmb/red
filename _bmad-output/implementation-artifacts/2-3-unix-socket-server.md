# Story 2.3: Unix Socket Server

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **the daemon to listen on a Unix socket**,
So that **TUI clients can connect locally without network exposure**.

## Acceptance Criteria

1. **Given** Story 2.2 is complete
2. **When** daemon starts
3. **Then** Unix socket is created at `~/.cyber-red/daemon.sock`
4. **And** socket permissions are restricted (owner only - `0o600`)
5. **And** server accepts multiple concurrent client connections
6. **And** server handles client disconnection gracefully
7. **And** server responds to IPC protocol commands (from Story 2.2)
8. **And** integration tests verify socket communication

## Tasks / Subtasks

> [!IMPORTANT]
> **FIRST SOCKET SERVER IMPLEMENTATION — Foundation for all daemon-client communication (TUI, CLI)**

### Phase 1: Server Foundation

- [x] Task 1: Create Unix socket server class (AC: #2, #3, #4) <!-- id: 0 -->
  - [x] Create `src/cyberred/daemon/server.py`
  - [x] Implement `DaemonServer` class with asyncio
  - [x] Add `start()` method that creates Unix socket at `~/.cyber-red/daemon.sock`
  - [x] Set socket permissions to `0o600` (owner read/write only) using `os.chmod()`
  - [x] Add socket path configuration via `get_settings().storage.base_path`
  - [x] Remove stale socket file if exists on startup (handle unclean shutdown)
  - [x] Create PID file at `~/.cyber-red/daemon.pid` on startup, remove on shutdown
  - [x] Add `get_socket_path()` helper function for CLI integration
  - [x] Log server startup with `structlog`

- [x] Task 2: Implement connection handler (AC: #5, #6) <!-- id: 1 -->
  - [x] Create `_handle_client(reader, writer)` coroutine
  - [x] Accept multiple concurrent connections using `asyncio.start_unix_server()`
  - [x] Track active connections in a set for cleanup
  - [x] **Add read timeout** (30s default) to prevent hung clients: `asyncio.wait_for(reader.readline(), timeout=30)`
  - [x] **Enforce MAX_MESSAGE_SIZE** (10MB from `ipc.py`) before processing
  - [x] Handle `ConnectionResetError`, `BrokenPipeError`, and `asyncio.TimeoutError` gracefully
  - [x] Log client connect/disconnect events
  - [x] Implement clean connection close with writer.close() + wait_closed()

### Phase 2: IPC Protocol Integration

- [x] Task 3: Implement message processing (AC: #7) <!-- id: 2 -->
  - [x] Read newline-delimited JSON messages from client
  - [x] Decode messages using `decode_message()` from `daemon.ipc`
  - [x] Route commands to appropriate handlers
  - [x] Encode responses using `encode_message()` from `daemon.ipc`
  - [x] Send responses back to client
  - [x] Handle `IPCProtocolError` with error response

- [x] Task 4: Implement command handlers (AC: #7) <!-- id: 3 -->
  - [x] Create `_handle_command(request: IPCRequest) -> IPCResponse` method
  - [x] `sessions.list` → Return empty list (full impl in Story 2.5)
  - [x] `engagement.start` → Placeholder response (full impl in Story 2.5)
  - [x] `engagement.attach` → Placeholder response (full impl in Story 2.9)
  - [x] `engagement.detach` → Placeholder response (full impl in Story 2.9)
  - [x] `engagement.pause` → Placeholder response (full impl in Story 2.7)
  - [x] `engagement.resume` → Placeholder response (full impl in Story 2.7)
  - [x] `engagement.stop` → Placeholder response (full impl in Story 2.8)
  - [x] **`daemon.stop`** → Trigger graceful server shutdown (sets `_running = False`)
  - [x] Unknown commands → Error response
  - [x] **Note:** Add `DAEMON_STOP = "daemon.stop"` to `IPCCommand` enum in `ipc.py`

### Phase 3: Server Lifecycle

- [x] Task 5: Implement graceful shutdown <!-- id: 4 -->
  - [x] Add `stop()` method to `DaemonServer`
  - [x] Close all active client connections
  - [x] Close server socket
  - [x] Remove socket file on clean shutdown
  - [x] Remove PID file on clean shutdown
  - [x] Handle SIGTERM and SIGINT signals
  - [x] Add shutdown timeout (default: 5s)

- [x] Task 6: Integrate with CLI daemon commands <!-- id: 5 -->
  - [x] Update `cli.py` `daemon_start()` to instantiate and run `DaemonServer`
  - [x] Update `cli.py` `daemon_stop()` to send shutdown via IPC
  - [x] Update `cli.py` `daemon_status()` to query server via IPC
  - [x] Use `asyncio.run()` to bridge sync CLI with async server

### Phase 4: Testing

- [x] Task 7: Create unit tests for server (AC: #8) <!-- id: 6 -->
  - [x] Create `tests/unit/daemon/test_server.py`
  - [x] Test socket creation at expected path
  - [x] Test socket permissions are `0o600`
  - [x] Test stale socket cleanup on startup
  - [x] Test command routing for all IPC commands
  - [x] Test malformed message handling
  - [x] Test client disconnect handling
  - [x] Test server shutdown and socket cleanup
  - [x] Achieve 100% coverage on `daemon/server.py`

- [x] Task 8: Create integration tests for socket communication (AC: #8) <!-- id: 7 -->
  - [x] Create `tests/integration/daemon/test_server_integration.py`
  - [x] Test full request/response cycle via Unix socket
  - [x] Test multiple concurrent client connections
  - [x] Test client reconnection after disconnect
  - [x] Test server restart with existing clients

- [x] Task 9: Run full test suite <!-- id: 8 -->
  - [x] Run `pytest tests/unit/daemon/test_server.py -v`
  - [x] Run `pytest tests/integration/daemon/ -v`
  - [x] Run `pytest --cov=src/cyberred/daemon --cov-report=term-missing`
  - [x] Verify 100% coverage on `daemon/server.py`
  - [x] Verify no test regressions (full suite green)

- [x] Review Fixes (AI)
  - [x] Add implementation files to git
  - [x] Fix CLI stale socket check (liveness probing)
  - [x] Fix CLI stop verification (polling shutdown)
  - [x] Add connection rate limiting (MAX_CONNECTIONS=100)

## Dev Notes

### Architecture Context

This story implements the Unix socket server per architecture (lines 369-405, 417-427, 769-774):

```
src/cyberred/daemon/
├── __init__.py
├── ipc.py           # Story 2.2: IPCRequest, IPCResponse, protocol (DONE)
├── server.py        # ← THIS STORY: Unix socket server
├── session_manager.py  # Story 2.5: Multi-engagement management
└── state_machine.py    # Story 2.4: Engagement lifecycle
```

**From Architecture — Daemon Execution Model:**
```
┌──────────────────────────────────────────────────────────────────────┐
│                     CYBER-RED DAEMON (background)                     │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    SESSION MANAGER                               │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │ │
│  │  │ Engagement 1    │  │ Engagement 2    │  │ Engagement 3    │  │ │
│  │  │ State: RUNNING  │  │ State: PAUSED   │  │ State: STOPPED  │  │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

The server survives SSH disconnect and multiple TUI clients can attach.

### IPC Protocol (from Story 2.2)

Wire format: JSON + newline delimiter (`\n`), UTF-8 encoded

**Request Format:**
```json
{
  "command": "sessions.list",
  "params": {},
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response Format:**
```json
{
  "status": "ok",
  "data": {"engagements": []},
  "error": null,
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Implementation Pattern

```python
# src/cyberred/daemon/server.py
import asyncio
import os
import signal
import structlog
from pathlib import Path
from typing import Optional, Set

from cyberred.core.config import get_settings
from cyberred.core.exceptions import IPCProtocolError
from cyberred.daemon.ipc import (
    IPCCommand, IPCRequest, IPCResponse,
    decode_message, encode_message, MAX_MESSAGE_SIZE
)

READ_TIMEOUT = 30.0  # seconds - prevents hung clients

log = structlog.get_logger()


def get_socket_path() -> Path:
    """Get daemon socket path from settings."""
    settings = get_settings()
    return Path(settings.storage.base_path).expanduser() / "daemon.sock"


def get_pid_path() -> Path:
    """Get daemon PID file path from settings."""
    settings = get_settings()
    return Path(settings.storage.base_path).expanduser() / "daemon.pid"


class DaemonServer:
    """Unix socket server for daemon IPC."""

    def __init__(self, socket_path: Optional[Path] = None):
        if socket_path is None:
            socket_path = get_socket_path()
        self._socket_path = socket_path
        self._pid_path = get_pid_path()
        self._server: Optional[asyncio.Server] = None
        self._clients: Set[asyncio.StreamWriter] = set()
        self._running = False

    async def start(self) -> None:
        """Start the Unix socket server."""
        # Clean up stale socket
        if self._socket_path.exists():
            log.warning("removing_stale_socket", path=str(self._socket_path))
            self._socket_path.unlink()

        # Ensure parent directory exists
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)

        # Start server
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=str(self._socket_path)
        )
        
        # Set restrictive permissions (owner only)
        os.chmod(self._socket_path, 0o600)
        
        # Write PID file
        self._pid_path.write_text(str(os.getpid()))
        
        self._running = True
        log.info("daemon_server_started", socket=str(self._socket_path), pid=os.getpid())

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """Handle a single client connection."""
        self._clients.add(writer)
        client_id = id(writer)
        log.info("client_connected", client_id=client_id)
        
        try:
            while self._running:
                try:
                    data = await asyncio.wait_for(
                        reader.readline(), timeout=READ_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    log.warning("client_read_timeout", client_id=client_id)
                    break
                    
                if not data:
                    break  # Client disconnected
                
                # Enforce message size limit (prevent DoS)
                if len(data) > MAX_MESSAGE_SIZE:
                    log.warning("message_too_large", size=len(data), limit=MAX_MESSAGE_SIZE)
                    continue
                    
                try:
                    request = decode_message(data)
                    if not isinstance(request, IPCRequest):
                        raise IPCProtocolError("Expected IPCRequest")
                    
                    response = await self._handle_command(request)
                    writer.write(encode_message(response))
                    await writer.drain()
                    
                except IPCProtocolError as e:
                    log.warning("protocol_error", error=str(e))
                    # Can't send error response without request_id
                    
        except (ConnectionResetError, BrokenPipeError):
            log.warning("client_disconnected_abruptly", client_id=client_id)
        finally:
            self._clients.discard(writer)
            writer.close()
            await writer.wait_closed()
            log.info("client_disconnected", client_id=client_id)

    async def _handle_command(self, request: IPCRequest) -> IPCResponse:
        """Route and handle IPC command."""
        log.debug("handling_command", command=request.command, request_id=request.request_id)
        
        try:
            command = IPCCommand(request.command)
        except ValueError:
            return IPCResponse.error(
                f"Unknown command: {request.command}",
                request.request_id
            )
        
        # Placeholder implementations - full logic in subsequent stories
        if command == IPCCommand.SESSIONS_LIST:
            return IPCResponse.ok({"engagements": []}, request.request_id)
        
        elif command == IPCCommand.ENGAGEMENT_START:
            return IPCResponse.ok(
                {"id": "placeholder", "state": "INITIALIZING"},
                request.request_id
            )
        
        elif command == IPCCommand.ENGAGEMENT_ATTACH:
            return IPCResponse.ok({"attached": True}, request.request_id)
        
        elif command == IPCCommand.ENGAGEMENT_DETACH:
            return IPCResponse.ok({"detached": True}, request.request_id)
        
        elif command == IPCCommand.ENGAGEMENT_PAUSE:
            return IPCResponse.ok({"state": "PAUSED"}, request.request_id)
        
        elif command == IPCCommand.ENGAGEMENT_RESUME:
            return IPCResponse.ok({"state": "RUNNING"}, request.request_id)
        
        elif command == IPCCommand.ENGAGEMENT_STOP:
            return IPCResponse.ok({"state": "STOPPED"}, request.request_id)
        
        elif command == IPCCommand.DAEMON_STOP:
            log.info("daemon_stop_requested", request_id=request.request_id)
            asyncio.create_task(self.stop())  # Trigger shutdown
            return IPCResponse.ok({"stopping": True}, request.request_id)
        
        return IPCResponse.ok({}, request.request_id)

    async def stop(self, timeout: float = 5.0) -> None:
        """Stop the server gracefully."""
        self._running = False
        
        # Close all client connections
        for writer in list(self._clients):
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
        
        # Close server
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        # Remove socket file
        if self._socket_path.exists():
            self._socket_path.unlink()
        
        # Remove PID file
        if self._pid_path.exists():
            self._pid_path.unlink()
        
        log.info("daemon_server_stopped")


async def run_daemon(foreground: bool = False) -> None:
    """Run the daemon server.
    
    Args:
        foreground: If True, run in foreground (for systemd Type=simple).
                    If False, would daemonize (not implemented - use systemd).
    """
    server = DaemonServer()
    
    loop = asyncio.get_event_loop()
    
    # Signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(server.stop()))
    
    await server.start()
    
    try:
        await server._server.serve_forever()
    except asyncio.CancelledError:
        pass
    finally:
        await server.stop()
```

### Socket Path

Per architecture (line 146) and config (Story 1.3):
- Default: `~/.cyber-red/daemon.sock`
- Derived from: `get_settings().storage.base_path`
- Permissions: `0o600` (owner read/write only)

### CLI Integration Pattern

```python
# Update to cli.py

@daemon_app.command("start")
def daemon_start(
    foreground: bool = typer.Option(False, "--foreground", "-f"),
    config: Optional[Path] = typer.Option(None, "--config", "-c")
) -> None:
    """Start the Cyber-Red daemon."""
    if config:
        if not config.exists():
            typer.echo(f"Error: Config file {config} not found", err=True)
            raise typer.Exit(code=1)
        get_settings(force_reload=True, system_config_path=config)
    
    from cyberred.daemon.server import run_daemon
    asyncio.run(run_daemon(foreground=foreground))


@daemon_app.command("status")
def daemon_status() -> None:
    """Show daemon status."""
    from cyberred.daemon.ipc import build_request, encode_message, decode_message
    
    socket_path = get_socket_path()
    if not socket_path.exists():
        typer.echo("Daemon not running")
        raise typer.Exit(code=1)
    
    # Query daemon via IPC
    async def query_status():
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        request = build_request(IPCCommand.SESSIONS_LIST)
        writer.write(encode_message(request))
        await writer.drain()
        data = await reader.readline()
        response = decode_message(data)
        writer.close()
        await writer.wait_closed()
        return response
    
    try:
        response = asyncio.run(query_status())
        if response.status == "ok":
            typer.echo(f"Daemon running, {len(response.data.get('engagements', []))} active engagements")
        else:
            typer.echo(f"Daemon error: {response.error}")
            raise typer.Exit(code=1)
    except (ConnectionRefusedError, FileNotFoundError):
        typer.echo("Daemon not running")
        raise typer.Exit(code=1)
```

### Test Pattern

```python
# tests/unit/daemon/test_server.py
import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock
from cyberred.daemon.server import DaemonServer
from cyberred.daemon.ipc import (
    IPCRequest, IPCCommand, encode_message, decode_message
)


@pytest.fixture
def temp_socket_path(tmp_path: Path) -> Path:
    return tmp_path / "test.sock"


@pytest.fixture
def server(temp_socket_path: Path) -> DaemonServer:
    return DaemonServer(socket_path=temp_socket_path)


class TestDaemonServer:
    @pytest.mark.asyncio
    async def test_socket_created_at_expected_path(
        self, server: DaemonServer, temp_socket_path: Path
    ) -> None:
        await server.start()
        try:
            assert temp_socket_path.exists()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_socket_permissions_restricted(
        self, server: DaemonServer, temp_socket_path: Path
    ) -> None:
        await server.start()
        try:
            stat = temp_socket_path.stat()
            assert stat.st_mode & 0o777 == 0o600
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_stale_socket_cleanup(
        self, temp_socket_path: Path
    ) -> None:
        # Create stale socket
        temp_socket_path.touch()
        
        server = DaemonServer(socket_path=temp_socket_path)
        await server.start()
        await server.stop()
        
        # Verify socket was recreated
        assert not temp_socket_path.exists()  # Cleaned up on stop

    @pytest.mark.asyncio
    async def test_sessions_list_command(
        self, server: DaemonServer, temp_socket_path: Path
    ) -> None:
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))
            
            request = IPCRequest(
                command=IPCCommand.SESSIONS_LIST,
                params={},
                request_id="test-123"
            )
            writer.write(encode_message(request))
            await writer.drain()
            
            data = await reader.readline()
            response = decode_message(data)
            
            assert response.status == "ok"
            assert response.data == {"engagements": []}
            assert response.request_id == "test-123"
            
            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()
```

### Dependencies

**Required (no new dependencies):**
- `asyncio` (stdlib) - Unix socket server
- `signal` (stdlib) - Signal handling
- `os` (stdlib) - Chmod for socket permissions
- `structlog` (existing) - Logging
- `cyberred.daemon.ipc` (Story 2.2) - IPC protocol, `MAX_MESSAGE_SIZE` constant

### Previous Story Intelligence

**From Story 2.2 (IPC Protocol Definition):**
- `IPCRequest` and `IPCResponse` dataclasses available
- `IPCCommand` StrEnum with 7 commands (add `DAEMON_STOP` in this story)
- `encode_message()` and `decode_message()` for wire protocol
- `MAX_MESSAGE_SIZE = 10MB` for DoS prevention
- `IPCProtocolError` for malformed messages
- Wire format: JSON + newline delimiter

**From Story 2.1 (CLI Entry Point):**
- CLI uses Typer framework
- Config validation working via `get_settings()`
- Socket path derived from `get_settings().storage.base_path`
- Use `asyncio.run()` to bridge sync CLI with async server

### Anti-Patterns to Avoid

1. **NEVER** implement actual engagement logic in this story (that's Story 2.5+)
2. **NEVER** use TCP sockets for local daemon communication (security risk)
3. **NEVER** allow socket permissions > 0o600 (owner only)
4. **NEVER** leave stale socket files on crash (check and clean on startup)
5. **NEVER** skip client disconnect handling (graceful cleanup required)
6. **NEVER** block the event loop (all I/O must be async)

### Project Structure Notes

- Creates `daemon/server.py` in existing `src/cyberred/daemon/` package
- Aligns with architecture project structure (line 769-774)
- Integration tests go in `tests/integration/daemon/`
- Socket path: `~/.cyber-red/daemon.sock` (from architecture line 146)

### References

- [Architecture: Daemon Execution Model](file:///root/red/docs/3-solutioning/architecture.md#L365-L405)
- [Architecture: IPC Protocol](file:///root/red/docs/3-solutioning/architecture.md#L417-L427)
- [Architecture: Daemon Structure](file:///root/red/docs/3-solutioning/architecture.md#L769-L774)
- [Epics: Story 2.3](file:///root/red/docs/3-solutioning/epics-stories.md#L1136-L1156)
- [Epics: Story 2.4 (State Machine)](file:///root/red/docs/3-solutioning/epics-stories.md#L1160-L1180)
- [Epics: Story 2.5 (Session Manager)](file:///root/red/docs/3-solutioning/epics-stories.md#L1183-L1202)

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

- src/cyberred/daemon/server.py
- tests/unit/daemon/test_server.py
- tests/integration/daemon/test_server_integration.py
- src/cyberred/cli.py
- tests/unit/test_cli.py
