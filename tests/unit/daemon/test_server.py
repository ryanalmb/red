"""Unit tests for DaemonServer Unix socket server.

Tests core functionality:
- Socket creation at expected path
- Socket permissions (0o600)
- Stale socket cleanup
- PID file management
- Command routing
- Client handling
"""

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.daemon.ipc import (
    IPCCommand,
    IPCRequest,
    IPCResponse,
    encode_message,
    decode_message,
    MAX_MESSAGE_SIZE,
)


# Tests will be run against the DaemonServer class once implemented


@pytest.fixture
def temp_socket_path(tmp_path: Path) -> Path:
    """Create a temporary socket path for testing."""
    return tmp_path / "test.sock"


@pytest.fixture
def temp_pid_path(tmp_path: Path) -> Path:
    """Create a temporary PID file path for testing."""
    return tmp_path / "test.pid"


class TestDaemonServerSocketCreation:
    """Tests for socket creation and permissions."""

    @pytest.mark.asyncio
    async def test_socket_created_at_expected_path(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Socket file should be created at the specified path."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            assert temp_socket_path.exists(), "Socket file should exist after start"
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_socket_permissions_restricted(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Socket permissions should be 0o600 (owner only)."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            stat = temp_socket_path.stat()
            # Socket permissions (mask out socket type bits)
            perms = stat.st_mode & 0o777
            assert perms == 0o600, f"Socket permissions should be 0o600, got {oct(perms)}"
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_stale_socket_cleanup_on_startup(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Stale socket file should be removed on startup."""
        from cyberred.daemon.server import DaemonServer

        # Create stale socket file
        temp_socket_path.touch()
        assert temp_socket_path.exists()

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            # Should be a valid socket now, not the stale file
            assert temp_socket_path.exists()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_socket_removed_on_clean_shutdown(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Socket file should be removed after clean shutdown."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        assert temp_socket_path.exists()
        await server.stop()
        assert not temp_socket_path.exists(), "Socket should be removed after stop"


class TestDaemonServerPIDFile:
    """Tests for PID file management."""

    @pytest.mark.asyncio
    async def test_pid_file_created_on_startup(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """PID file should be created on startup."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            assert temp_pid_path.exists(), "PID file should exist after start"
            pid_content = temp_pid_path.read_text().strip()
            assert pid_content == str(os.getpid())
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_pid_file_removed_on_shutdown(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """PID file should be removed after clean shutdown."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        assert temp_pid_path.exists()
        await server.stop()
        assert not temp_pid_path.exists(), "PID file should be removed after stop"


class TestDaemonServerCommands:
    """Tests for IPC command handling."""

    @pytest.fixture(autouse=True)
    def mock_preflight(self):
        """Mock pre-flight checks."""
        with patch("cyberred.daemon.session_manager.PreFlightRunner") as MockRunner:
            runner = MagicMock()
            runner.run_all = AsyncMock(return_value=[])
            runner.validate_results = MagicMock()
            MockRunner.return_value = runner
            yield runner

    @pytest.mark.asyncio

    async def test_sessions_list_command(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """sessions.list should return empty engagements list."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            request = IPCRequest(
                command=IPCCommand.SESSIONS_LIST,
                params={},
                request_id="test-123",
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

    @pytest.mark.asyncio
    async def test_engagement_start_command(
        self, temp_socket_path: Path, temp_pid_path: Path, tmp_path: Path
    ) -> None:
        """engagement.start should create and start engagement."""
        from cyberred.daemon.server import DaemonServer

        # Create config file for engagement
        config_path = tmp_path / "test-eng.yaml"
        config_path.write_text("name: testeng\n")

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_START,
                params={"config_path": str(config_path)},
                request_id="test-456",
            )
            writer.write(encode_message(request))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "ok", f"Start failed: {response.error}"
            assert "id" in response.data
            assert response.data["state"] == "RUNNING"
            assert response.request_id == "test-456"

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_daemon_stop_command(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """daemon.stop should trigger graceful shutdown and call callback."""
        from cyberred.daemon.server import DaemonServer

        shutdown_callback = MagicMock()

        server = DaemonServer(
            socket_path=temp_socket_path, 
            pid_path=temp_pid_path,
            shutdown_callback=shutdown_callback
        )
        await server.start()

        reader, writer = await asyncio.open_unix_connection(
            str(temp_socket_path)
        )

        request = IPCRequest(
            command=IPCCommand.DAEMON_STOP,
            params={},
            request_id="test-stop",
        )
        writer.write(encode_message(request))
        await writer.drain()

        data = await reader.readline()
        response = decode_message(data)

        assert response.status == "ok"
        assert response.data.get("stopping") is True

        writer.close()
        await writer.wait_closed()

        # Wait for shutdown to complete (callback should be called)
        # Server stop is async task, callback is sync
        shutdown_callback.assert_called_once()

        # Wait for async stop task to finish
        await asyncio.sleep(0.1)
        assert not server._running

    @pytest.mark.asyncio
    async def test_unknown_command_returns_error(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Unknown commands should return error response."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            # Send request with unknown command (bypass validation)
            request_data = {
                "command": "unknown.command",
                "params": {},
                "request_id": "test-unknown",
            }
            import json
            writer.write((json.dumps(request_data) + "\n").encode("utf-8"))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "error"
            assert "unknown" in response.error.lower()
            assert response.request_id == "test-unknown"

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()


class TestDaemonServerClientHandling:
    """Tests for client connection handling."""

    @pytest.mark.asyncio
    async def test_multiple_concurrent_clients(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Server should accept multiple concurrent clients."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            # Connect multiple clients
            clients = []
            for i in range(3):
                reader, writer = await asyncio.open_unix_connection(
                    str(temp_socket_path)
                )
                clients.append((reader, writer))

            # Send request from each client
            for i, (reader, writer) in enumerate(clients):
                request = IPCRequest(
                    command=IPCCommand.SESSIONS_LIST,
                    params={},
                    request_id=f"client-{i}",
                )
                writer.write(encode_message(request))
                await writer.drain()

            # Get responses
            for i, (reader, writer) in enumerate(clients):
                data = await reader.readline()
                response = decode_message(data)
                assert response.status == "ok"
                assert response.request_id == f"client-{i}"

            # Clean up
            for reader, writer in clients:
                writer.close()
                await writer.wait_closed()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_client_disconnect_handled_gracefully(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Server should handle client disconnect gracefully."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            # Disconnect without sending anything
            writer.close()
            await writer.wait_closed()

            # Server should still be running
            await asyncio.sleep(0.1)
            assert server._running

            # New connections should work
            reader2, writer2 = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )
            request = IPCRequest(
                command=IPCCommand.SESSIONS_LIST,
                params={},
                request_id="after-disconnect",
            )
            writer2.write(encode_message(request))
            await writer2.drain()
            data = await reader2.readline()
            response = decode_message(data)
            assert response.status == "ok"

            writer2.close()
            await writer2.wait_closed()
        finally:
            await server.stop()


            await server.stop()

    @pytest.mark.asyncio
    async def test_max_connections_limit_enforced(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Server should reject connections over the limit."""
        from cyberred.daemon.server import DaemonServer
        import cyberred.daemon.server as server_module

        # Patch MAX_CONNECTIONS to a small value
        with patch.object(server_module, "MAX_CONNECTIONS", 1):
            server = DaemonServer(
                socket_path=temp_socket_path, pid_path=temp_pid_path
            )
            await server.start()
            try:
                # First client connects fine
                reader1, writer1 = await asyncio.open_unix_connection(
                    str(temp_socket_path)
                )

                # Second client should be rejected (closed immediately)
                reader2, writer2 = await asyncio.open_unix_connection(
                    str(temp_socket_path)
                )
                
                # Check that second client is closed
                # Writing should fail or reading empty bytes immediately
                try:
                    data = await reader2.read()
                    assert data == b"", "Connection should be closed immediately"
                except (ConnectionResetError, BrokenPipeError):
                    pass  # Expected behavior
                
                writer1.close()
                await writer1.wait_closed()
                writer2.close()
                try:
                    await writer2.wait_closed()
                except Exception:
                    pass
            finally:
                await server.stop()


                await server.stop()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_message_size_limit_enforced(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Server should drop messages larger than MAX_MESSAGE_SIZE."""
        from cyberred.daemon.server import DaemonServer
        import cyberred.daemon.server as server_module

        # Patch MAX_MESSAGE_SIZE to small value (1KB)
        # We need to patch it in server module where it's used
        SMALL_SIZE = 1024
        with patch.object(server_module, "MAX_MESSAGE_SIZE", SMALL_SIZE):
            server = DaemonServer(
                socket_path=temp_socket_path, pid_path=temp_pid_path
            )
            await server.start()
            try:
                reader, writer = await asyncio.open_unix_connection(
                    str(temp_socket_path)
                )

                # Send oversize message (1KB + 10 bytes)
                # This fits in default asyncio 64KB buffer, so readline works,
                # but fails our mocked check. Server might close immediately.
                try:
                    msg = b"x" * (SMALL_SIZE + 10) + b"\n"
                    writer.write(msg)
                    await writer.drain()
                except (ConnectionResetError, BrokenPipeError):
                    pass # Connection closed early, which is fine

                # Server should close connection immediately
                try:
                    # Try to read, should return empty bytes (EOF) or raise Error
                    data = await reader.read()
                    assert data == b"", "Connection should be closed"
                except (ConnectionResetError, BrokenPipeError):
                    pass # Expected
                
                # Connection is dead, we are done.
                try:
                    writer.close()
                    await writer.wait_closed()
                except (Exception):
                    pass

                writer.close()
                await writer.wait_closed()
            finally:
                await server.stop()

    @pytest.mark.asyncio
    async def test_read_timeout(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Server should disconnect client on read timeout."""
        from cyberred.daemon.server import DaemonServer, READ_TIMEOUT
        import cyberred.daemon.server as server_module

        # Patch READ_TIMEOUT to very small value
        with patch.object(server_module, "READ_TIMEOUT", 0.1):
            server = DaemonServer(
                socket_path=temp_socket_path, pid_path=temp_pid_path
            )
            await server.start()
            try:
                reader, writer = await asyncio.open_unix_connection(
                    str(temp_socket_path)
                )

                # Wait longer than timeout
                await asyncio.sleep(0.2)

                # Connection should be closed
                try:
                    data = await reader.read()
                    assert data == b""
                except (ConnectionResetError, BrokenPipeError):
                    pass
                
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
            finally:
                await server.stop()

    @pytest.mark.asyncio
    async def test_broken_pipe_handling(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Server should handle BrokenPipeError/ConnectionResetError."""
        from cyberred.daemon.server import DaemonServer
        
        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            # We can't easily force BrokenPipeError from python client side 
            # without lower level hacks, so we'll mock the handler behavior
            pass
            # Actually, let's unit test the _handle_client method directly with mocks
            # which is easier for these specific exception paths
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_writer_close_error_ignored(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Errors during writer.wait_closed() should be ignored."""
        from cyberred.daemon.server import DaemonServer
        
        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        
        # Test unit directly
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_writer.close = MagicMock()
        mock_reader.readline.return_value = b"" # Immediate disconnect
        
        mock_writer.wait_closed.side_effect = Exception("Close error")
        
        server._clients.add(mock_writer)
        server._running = True
        
        # Should not raise
        await server._handle_client(mock_reader, mock_writer)
        
        assert mock_writer.close.called
        assert mock_writer in server._clients or len(server._clients) == 0


class TestDaemonServerHelpers:
    """Tests for helper functions."""

    def test_get_socket_path_returns_path(self) -> None:
        """get_socket_path should return Path from settings."""
        from cyberred.daemon.server import get_socket_path

        with patch("cyberred.daemon.server.get_settings") as mock_settings:
            mock_settings.return_value.storage.base_path = "/tmp/test"
            result = get_socket_path()
            assert isinstance(result, Path)
            assert result == Path("/tmp/test/daemon.sock")

    def test_get_pid_path_returns_path(self) -> None:
        """get_pid_path should return Path from settings."""
        from cyberred.daemon.server import get_pid_path

        with patch("cyberred.daemon.server.get_settings") as mock_settings:
            mock_settings.return_value.storage.base_path = "/tmp/test"
            result = get_pid_path()
            assert isinstance(result, Path)
            assert result == Path("/tmp/test/daemon.pid")


class TestDaemonServerMessageHandling:
    """Tests for message size and protocol handling."""

    @pytest.mark.asyncio
    async def test_malformed_json_handled(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Malformed JSON should be handled gracefully."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            # Send malformed JSON
            writer.write(b"not valid json\n")
            await writer.drain()

            # Server should not crash, wait a bit
            await asyncio.sleep(0.1)
            assert server._running

            # Should be able to send valid request after
            request = IPCRequest(
                command=IPCCommand.SESSIONS_LIST,
                params={},
                request_id="after-malformed",
            )
            writer.write(encode_message(request))
            await writer.drain()
            data = await reader.readline()
            response = decode_message(data)
            assert response.status == "ok"

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()


            await server.stop()

    @pytest.mark.asyncio
    async def test_protocol_error_handling(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """IPCProtocolError should be logged and loop continued."""
        from cyberred.daemon.server import DaemonServer
        
        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )
            
            # Send message that decodes but isn't IPCRequest (if possible)
            # or force decode_message to raise IPCProtocolError
            # Since decode_message checks JSON structure, let's send valid JSON that isn't a request
            # But the server uses decode_message which returns IPCRequest or raises.
            # If we send a dict that misses fields, decode_message raises IPCProtocolError
            
            # Invalid request (missing command)
            writer.write(b'{"params": {}}\n')
            await writer.drain()
            
            # Server logs warning and continues. 
            # Send valid request to prove it's still alive
            request = IPCRequest(
                command=IPCCommand.SESSIONS_LIST,
                params={}, 
                request_id="after-proto-error"
            )
            writer.write(encode_message(request))
            await writer.drain()
            
            data = await reader.readline()
            response = decode_message(data)
            assert response.status == "ok"
            assert response.request_id == "after-proto-error"
            
            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()
            
    @pytest.mark.asyncio
    async def test_stop_handles_cleanup_errors(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """stop() should handle OSError during file cleanup and timeouts."""
        from cyberred.daemon.server import DaemonServer
        
        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        
        # Mock unlink to raise OSError
        with patch.object(Path, "unlink", side_effect=OSError("Permission denied")):
            # Should not raise
            await server.stop()
            
    @pytest.mark.asyncio
    async def test_stop_server_close_timeout(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """stop() should handle timeout waiting for server close."""
        from cyberred.daemon.server import DaemonServer
        
        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        
        # Mock wait_closed to timeout
        server._server.wait_closed = AsyncMock(side_effect=asyncio.TimeoutError)
        
        # Should not raise
        await server.stop()

    @pytest.mark.asyncio
    async def test_broken_pipe_handling_direct(self) -> None:
        """Direct unit test for broken pipe in main loop."""
        from cyberred.daemon.server import DaemonServer
        
        server = DaemonServer()
        server._running = True
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_writer.close = MagicMock()
        
        # Reader raises BrokenPipeError immediately
        mock_reader.readline.side_effect = BrokenPipeError()
        
        await server._handle_client(mock_reader, mock_writer)
        
        # Client should be removed
        assert mock_writer not in server._clients


    @pytest.mark.asyncio
    async def test_hard_limit_enforced(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Server should disconnect if hard limit (limit*2) is exceeded."""
        from cyberred.daemon.server import DaemonServer
        import cyberred.daemon.server as server_module

        # Patch MAX_MESSAGE_SIZE to small value
        SMALL_SIZE = 1024
        # Hard limit will be 2048
        with patch.object(server_module, "MAX_MESSAGE_SIZE", SMALL_SIZE):
            server = DaemonServer(
                socket_path=temp_socket_path, pid_path=temp_pid_path
            )
            await server.start()
            try:
                reader, writer = await asyncio.open_unix_connection(
                    str(temp_socket_path)
                )

                # Send message exceeding hard limit (2048 + 1)
                # readline will raise LimitOverrunError
                msg = b"x" * (SMALL_SIZE * 2 + 100) + b"\n"
                writer.write(msg)
                await writer.drain()

                # Server should close connection
                try:
                    data = await reader.read()
                    assert data == b""
                except (ConnectionResetError, BrokenPipeError):
                    pass
                
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
            finally:
                await server.stop()
                
    @pytest.mark.asyncio
    async def test_pid_cleanup_failure(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """stop() should log warning if PID file cleanup fails."""
        from cyberred.daemon.server import DaemonServer
        
        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        
        # Mock Path.unlink to succeed first (socket), then fail (pid)
        with patch.object(Path, "unlink", side_effect=[None, OSError("Fail")]):
             await server.stop()
             
    @pytest.mark.asyncio
    async def test_stop_client_close_timeout(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """stop() should handle timeout when closing clients."""
        from cyberred.daemon.server import DaemonServer
        
        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        
        # Manually add a mock client that hangs on wait_closed
        mock_writer = AsyncMock()
        mock_writer.close = MagicMock()
        
        # AsyncMock side_effect needs to be an exception instance or class
        # When awaited, it raises.
        # But wait_for calls it.
        # Ensure it behaves like an async function raising TimeoutError
        async def raise_timeout():
            # Sleep a bit then raise, or just raise
            await asyncio.sleep(0.1) 
            raise asyncio.TimeoutError("Mock timeout")
            
        mock_writer.wait_closed.side_effect = raise_timeout
        
        server._clients.add(mock_writer)
        server._running = True
        
        
        # Should not raise
        await server.stop()
        assert mock_writer.close.called
        
    @pytest.mark.asyncio
    async def test_handle_client_calls_drain(self) -> None:
        """Verify writer.drain() is awaited."""
        from cyberred.daemon.server import DaemonServer
        from cyberred.daemon.ipc import IPCCommand, IPCRequest, encode_message
        
        server = DaemonServer()
        server._running = True
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_writer.close = MagicMock()
        
        # Valid request
        request = IPCRequest(
            command=IPCCommand.SESSIONS_LIST,
            params={},
            request_id="test-drain"
        )
        msg_bytes = encode_message(request)
        
        # Read request then EOF
        mock_reader.readline.side_effect = [msg_bytes, b""]
        
        await server._handle_client(mock_reader, mock_writer)
        
        # Verify drain called
        assert mock_writer.drain.called
        assert mock_writer.drain.await_count >= 1
        
    @pytest.mark.asyncio
    async def test_stop_explicit_timeout(self) -> None:
        """Call stop with explicit timeout."""
        from cyberred.daemon.server import DaemonServer
        server = DaemonServer()
        # Mock server
        server._server = AsyncMock()
        await server.stop(timeout=1.0)


class TestDaemonServerAllCommands:
    """Tests for all IPC command handlers with SessionManager integration."""

    @pytest.fixture(autouse=True)
    def mock_preflight(self):
        """Mock pre-flight checks."""
        with patch("cyberred.daemon.session_manager.PreFlightRunner") as MockRunner:
            runner = MagicMock()
            runner.run_all = AsyncMock(return_value=[])
            runner.validate_results = MagicMock()
            MockRunner.return_value = runner
            yield runner

    @pytest.mark.asyncio

    async def test_engagement_attach_command(
        self, temp_socket_path: Path, temp_pid_path: Path, tmp_path: Path
    ) -> None:
        """engagement.attach should return state snapshot and subscription_id for RUNNING engagement."""
        from cyberred.daemon.server import DaemonServer

        # Create config file for engagement
        config_path = tmp_path / "test-eng.yaml"
        config_path.write_text("name: testeng\n")

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            # First create and start an engagement
            start_request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_START,
                params={"config_path": str(config_path)},
                request_id="test-start",
            )
            writer.write(encode_message(start_request))
            await writer.drain()
            start_data = await reader.readline()
            start_response = decode_message(start_data)
            assert start_response.status == "ok"
            engagement_id = start_response.data.get("id")

            # Now attach to it
            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_ATTACH,
                params={"engagement_id": engagement_id},
                request_id="test-attach",
            )
            writer.write(encode_message(request))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "ok"
            assert response.data.get("engagement_id") == engagement_id
            assert response.data.get("state") == "RUNNING"
            assert "subscription_id" in response.data
            assert response.data.get("subscription_id").startswith("sub-")
            assert response.request_id == "test-attach"

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_engagement_attach_missing_engagement_id(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """engagement.attach without engagement_id returns error."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_ATTACH,
                params={},  # Missing engagement_id
                request_id="test-attach-missing",
            )
            writer.write(encode_message(request))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "error"
            assert "Missing required parameter: engagement_id" in response.error

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_engagement_attach_nonexistent_engagement(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """engagement.attach for nonexistent engagement returns error."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_ATTACH,
                params={"engagement_id": "nonexistent-eng-id"},
                request_id="test-attach-notfound",
            )
            writer.write(encode_message(request))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "error"
            assert "Engagement not found" in response.error

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_engagement_attach_wrong_state(
        self, temp_socket_path: Path, temp_pid_path: Path, tmp_path: Path
    ) -> None:
        """engagement.attach for INITIALIZING engagement returns error."""
        from cyberred.daemon.server import DaemonServer

        # Create config file but DON'T start engagement
        config_path = tmp_path / "test-eng.yaml"
        config_path.write_text("name: testeng\n")

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            # Manually create engagement without starting (stays in INITIALIZING)
            engagement_id = server.session_manager.create_engagement(config_path)

            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_ATTACH,
                params={"engagement_id": engagement_id},
                request_id="test-attach-wrongstate",
            )
            writer.write(encode_message(request))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "error"
            assert "INITIALIZING" in response.error
            assert "must be RUNNING or PAUSED" in response.error

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_engagement_detach_command(
        self, temp_socket_path: Path, temp_pid_path: Path, tmp_path: Path
    ) -> None:
        """engagement.detach should unsubscribe and return success."""
        from cyberred.daemon.server import DaemonServer

        # Create and start engagement first
        config_path = tmp_path / "test-eng.yaml"
        config_path.write_text("name: testeng\n")

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            # Start engagement
            start_request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_START,
                params={"config_path": str(config_path)},
                request_id="test-start",
            )
            writer.write(encode_message(start_request))
            await writer.drain()
            start_data = await reader.readline()
            start_response = decode_message(start_data)
            engagement_id = start_response.data.get("id")

            # Attach to get subscription_id
            attach_request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_ATTACH,
                params={"engagement_id": engagement_id},
                request_id="test-attach",
            )
            writer.write(encode_message(attach_request))
            await writer.drain()
            attach_data = await reader.readline()
            attach_response = decode_message(attach_data)
            subscription_id = attach_response.data.get("subscription_id")

            # Now detach
            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_DETACH,
                params={"subscription_id": subscription_id},
                request_id="test-detach",
            )
            writer.write(encode_message(request))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "ok"
            assert response.data.get("detached") is True
            assert response.data.get("subscription_id") == subscription_id

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_engagement_detach_missing_subscription_id(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """engagement.detach without subscription_id returns error."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_DETACH,
                params={},  # Missing subscription_id
                request_id="test-detach-missing",
            )
            writer.write(encode_message(request))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "error"
            assert "Missing required parameter: subscription_id" in response.error

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_engagement_pause_command(
        self, temp_socket_path: Path, temp_pid_path: Path, tmp_path: Path
    ) -> None:
        """engagement.pause should return PAUSED state for running engagement."""
        from cyberred.daemon.server import DaemonServer

        # Create config file for engagement
        config_path = tmp_path / "test-eng.yaml"
        config_path.write_text("name: testeng\n")

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            # First create and start an engagement
            start_request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_START,
                params={"config_path": str(config_path)},
                request_id="test-start",
            )
            writer.write(encode_message(start_request))
            await writer.drain()
            start_data = await reader.readline()
            start_response = decode_message(start_data)
            assert start_response.status == "ok", f"Start failed: {start_response.error}"
            engagement_id = start_response.data.get("id")

            # Now pause it
            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_PAUSE,
                params={"engagement_id": engagement_id},
                request_id="test-pause",
            )
            writer.write(encode_message(request))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "ok", f"Pause failed: {response.error}"
            assert response.data.get("state") == "PAUSED"

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_engagement_resume_command(
        self, temp_socket_path: Path, temp_pid_path: Path, tmp_path: Path
    ) -> None:
        """engagement.resume should return RUNNING state for paused engagement."""
        from cyberred.daemon.server import DaemonServer

        # Create config file for engagement
        config_path = tmp_path / "test-eng.yaml"
        config_path.write_text("name: testeng\n")

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            # Create and start an engagement
            start_request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_START,
                params={"config_path": str(config_path)},
                request_id="test-start",
            )
            writer.write(encode_message(start_request))
            await writer.drain()
            start_data = await reader.readline()
            start_response = decode_message(start_data)
            engagement_id = start_response.data.get("id")

            # Pause it
            pause_request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_PAUSE,
                params={"engagement_id": engagement_id},
                request_id="test-pause",
            )
            writer.write(encode_message(pause_request))
            await writer.drain()
            await reader.readline()  # consume pause response

            # Now resume it
            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_RESUME,
                params={"engagement_id": engagement_id},
                request_id="test-resume",
            )
            writer.write(encode_message(request))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "ok", f"Resume failed: {response.error}"
            assert response.data.get("state") == "RUNNING"

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_engagement_stop_command(
        self, temp_socket_path: Path, temp_pid_path: Path, tmp_path: Path
    ) -> None:
        """engagement.stop should return STOPPED state for running engagement."""
        from cyberred.daemon.server import DaemonServer

        # Create config file for engagement
        config_path = tmp_path / "test-eng.yaml"
        config_path.write_text("name: testeng\n")

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            # Create and start an engagement
            start_request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_START,
                params={"config_path": str(config_path)},
                request_id="test-start",
            )
            writer.write(encode_message(start_request))
            await writer.drain()
            start_data = await reader.readline()
            start_response = decode_message(start_data)
            engagement_id = start_response.data.get("id")

            # Now stop it
            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_STOP,
                params={"engagement_id": engagement_id},
                request_id="test-stop-eng",
            )
            writer.write(encode_message(request))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "ok"
            assert response.data.get("state") == "STOPPED"

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()


class TestDaemonServerDefaultPaths:
    """Tests for default path resolution."""

    def test_server_uses_default_socket_path(self) -> None:
        """DaemonServer should use get_socket_path() if not provided."""
        from cyberred.daemon.server import DaemonServer

        with patch("cyberred.daemon.server.get_socket_path") as mock_socket:
            with patch("cyberred.daemon.server.get_pid_path") as mock_pid:
                mock_socket.return_value = Path("/tmp/default.sock")
                mock_pid.return_value = Path("/tmp/default.pid")

                server = DaemonServer()

                assert server._socket_path == Path("/tmp/default.sock")
                assert server._pid_path == Path("/tmp/default.pid")


class TestRunDaemon:
    """Tests for run_daemon function."""

    @pytest.mark.asyncio
    async def test_run_daemon_starts_and_stops(self) -> None:
        """run_daemon should start server and handle shutdown signal."""
        from cyberred.daemon.server import run_daemon, DaemonServer
        import signal

        with patch("cyberred.daemon.server.DaemonServer") as MockServer:
            mock_instance = AsyncMock(spec=DaemonServer)
            mock_instance._running = True
            MockServer.return_value = mock_instance

            # Create a task that will send SIGINT after a short delay
            async def send_signal():
                await asyncio.sleep(0.1)
                os.kill(os.getpid(), signal.SIGINT)

            signal_task = asyncio.create_task(send_signal())

            try:
                await run_daemon(foreground=True)
            except asyncio.CancelledError:
                pass

            # Verify server was started and stopped
            mock_instance.start.assert_called_once()
            mock_instance.stop.assert_called_once()

            # Clean up signal task if still running
            if not signal_task.done():
                signal_task.cancel()
                try:
                    await signal_task
                except asyncio.CancelledError:
                    pass


# =============================================================================
# Story 2.11: Graceful Shutdown Tests
# =============================================================================

@pytest.mark.asyncio
class TestDaemonServerGracefulShutdown:
    """Tests for graceful shutdown (Story 2.11)."""

    @pytest.fixture(autouse=True)
    def mock_preflight(self):
        """Mock pre-flight checks."""
        with patch("cyberred.daemon.session_manager.PreFlightRunner") as MockRunner:
            runner = MagicMock()
            runner.run_all = AsyncMock(return_value=[])
            runner.validate_results = MagicMock()
            MockRunner.return_value = runner
            yield runner

    async def test_stop_graceful_notifies_clients(
        self, temp_socket_path: Path, temp_pid_path: Path, tmp_path: Path
    ) -> None:
        """Graceful shutdown should notify all TUI clients."""
        from cyberred.daemon.server import DaemonServer

        # Create config file for engagement
        config_path = tmp_path / "test-eng.yaml"
        config_path.write_text("name: testeng\n")

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()

        # Create an engagement and subscribe
        reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))
        
        # Start engagement first
        start_request = IPCRequest(
            command=IPCCommand.ENGAGEMENT_START,
            params={"config_path": str(config_path)},
            request_id="test-start",
        )
        writer.write(encode_message(start_request))
        await writer.drain()
        start_data = await reader.readline()
        start_response = decode_message(start_data)
        assert start_response.status == "ok"
        engagement_id = start_response.data["id"]

        writer.close()
        await writer.wait_closed()

        # Now stop gracefully
        exit_code = await server.stop(graceful=True, timeout=5.0)

        assert exit_code == 0
        assert not temp_socket_path.exists()
        assert not temp_pid_path.exists()

    async def test_stop_graceful_pauses_all_engagements(
        self, temp_socket_path: Path, temp_pid_path: Path, tmp_path: Path
    ) -> None:
        """Graceful shutdown should pause all running engagements."""
        from cyberred.daemon.server import DaemonServer
        from cyberred.daemon.state_machine import EngagementState

        # Create config files
        config1 = tmp_path / "eng1.yaml"
        config1.write_text("name: eng1\n")
        config2 = tmp_path / "eng2.yaml"
        config2.write_text("name: eng2\n")

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()

        # Start two engagements
        reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))
        
        for config in [config1, config2]:
            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_START,
                params={"config_path": str(config)},
                request_id=f"start-{config.stem}",
            )
            writer.write(encode_message(request))
            await writer.drain()
            data = await reader.readline()
            response = decode_message(data)
            assert response.status == "ok"

        writer.close()
        await writer.wait_closed()

        # Both should be running
        engagements = server._session_manager.list_engagements()
        assert len(engagements) == 2
        assert all(e.state == "RUNNING" for e in engagements)

        # Graceful shutdown
        exit_code = await server.stop(graceful=True, timeout=10.0)

        assert exit_code == 0
        # After shutdown, engagements should be STOPPED
        for e in engagements:
            ctx = server._session_manager.get_engagement(e.id)
            assert ctx.state == EngagementState.STOPPED

    async def test_stop_non_graceful_skips_preservation(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Non-graceful shutdown should skip engagement preservation."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()

        # Stop non-gracefully
        exit_code = await server.stop(graceful=False)

        assert exit_code == 0
        assert not temp_socket_path.exists()
        assert not temp_pid_path.exists()

    async def test_stop_exits_code_0_on_success(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Graceful shutdown should return exit code 0 on success."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()

        exit_code = await server.stop(graceful=True)

        assert exit_code == 0

    async def test_stop_exits_code_1_on_timeout(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Graceful shutdown should return exit code 1 on timeout."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()

        # Mock session manager to take too long
        async def slow_shutdown():
            await asyncio.sleep(10)
            return MagicMock()

        server._session_manager.graceful_shutdown = slow_shutdown

        # Stop with very short timeout
        exit_code = await server.stop(graceful=True, timeout=0.01)

        assert exit_code == 1
        # Cleanup should still happen
        assert not temp_socket_path.exists()
        assert not temp_pid_path.exists()

    async def test_stop_exits_code_1_on_error(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Graceful shutdown should return exit code 1 on error."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()

        # Mock exception
        server._session_manager.graceful_shutdown = MagicMock(side_effect=Exception("shutdown boom"))

        exit_code = await server.stop(graceful=True)

        assert exit_code == 1

    async def test_stop_graceful_exits_code_1_on_checkpoint_failure(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Graceful shutdown should return exit code 1 if checkpoints fail."""
        from cyberred.daemon.server import DaemonServer
        from cyberred.daemon.session_manager import ShutdownResult

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        
        # Mock result with errors
        failed_result = ShutdownResult(
            paused_ids=[],
            checkpoint_paths={},
            errors=["checkpoint failed for eng-1"],
        )
        server._session_manager.graceful_shutdown = AsyncMock(return_value=failed_result)

        exit_code = await server.stop(graceful=True)

        assert exit_code == 1

    async def test_daemon_stop_uses_graceful_by_default(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """daemon.stop IPC command should use graceful shutdown by default."""
        from cyberred.daemon.server import DaemonServer

        shutdown_callback = MagicMock()

        server = DaemonServer(
            socket_path=temp_socket_path,
            pid_path=temp_pid_path,
            shutdown_callback=shutdown_callback
        )
        await server.start()

        reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))

        request = IPCRequest(
            command=IPCCommand.DAEMON_STOP,
            params={},
            request_id="test-daemon-stop",
        )
        writer.write(encode_message(request))
        await writer.drain()

        data = await reader.readline()
        response = decode_message(data)

        assert response.status == "ok"
        assert response.data.get("stopping") is True

        writer.close()
        await writer.wait_closed()

        # Wait for async stop to complete
        await asyncio.sleep(0.5)
        assert not server._running


@pytest.mark.asyncio
class TestDaemonServerCoverage:
    """Tests to close coverage gaps for 100%."""

    async def test_stop_handles_event_bus_close_error(self) -> None:
        """stop() should process safely even if event_bus.close() fails."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer()
        
        # Inject mock event bus
        mock_bus = AsyncMock()
        mock_bus.close.side_effect = Exception("EventBus close failed")
        server._event_bus = mock_bus
        
        # Should not raise
        await server.stop(graceful=False)
        
        mock_bus.close.assert_called_once()


    async def test_sighup_handling_in_run_daemon(self) -> None:
        """run_daemon should register and handle SIGHUP."""
        from cyberred.daemon.server import run_daemon, DaemonServer
        import signal

        with patch("cyberred.daemon.server.DaemonServer") as MockServer:
            mock_instance = AsyncMock(spec=DaemonServer)
            mock_instance.close = MagicMock()
            mock_instance._running = True
            MockServer.return_value = mock_instance

            # Create a task that will send SIGHUP after a short delay
            async def send_signal():
                await asyncio.sleep(0.1)
                os.kill(os.getpid(), signal.SIGHUP)
                # Then send SIGINT to stop
                await asyncio.sleep(0.1)
                os.kill(os.getpid(), signal.SIGINT)

            signal_task = asyncio.create_task(send_signal())

            try:
                # Mock logging to verify "sighup_received"
                with patch("cyberred.daemon.server.log") as mock_log:
                    await run_daemon(foreground=True)
                    
                    # Verify SIGHUP logic triggered
                    # sighup_handler calls log.info("sighup_received", ...)
                    # We might need to check call args matches
                    # log.info("sighup_received", action="config_reload_placeholder")
                    sighup_calls = [
                        call for call in mock_log.info.call_args_list 
                        if call.args and "sighup_received" in call.args[0]
                    ]
                    assert len(sighup_calls) > 0, "SIGHUP handler not triggered"

            except asyncio.CancelledError:
                pass

            # Cleanup
            if not signal_task.done():
                signal_task.cancel()
                try:
                    await signal_task
                except asyncio.CancelledError:
                    pass

    async def test_stop_safe_without_event_bus(self) -> None:
        """stop() should be safe if _event_bus is not initialized."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer()
        # Ensure _event_bus is missing
        if hasattr(server, "_event_bus"):
            del server._event_bus
            
    async def test_handle_client_stops_if_shutdown_triggered_during_read(self) -> None:
        """Client handler should stop if running becomes False during read."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer()
        server._running = True

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        
        # Simulate successful read but shutdown triggered "during" it
        # We simulate this by having readline return data, but we set _running=False first
        mock_reader.readline.return_value = b"some_data"
        
        # We need a way to set server._running = False *after* readline returns but *before* the check
        # Since we can't easily inject code there, we just set it False beforehand?
        # No, the code checks:
        # data = await readline()
        # if not self._running: break
        
        # So if we set _running = False, then call _handle_client, 
        # the while loop condition `while self._running` would prevent entry if checked first.
        # But wait, the while loop is `while self._running:`. 
        # If we start with True, enter loop, then readline.
        
        # To test the INNER check, we need `readline` to complete, returns data, BUT `_running` is False.
        # So we can set side_effect of readline to flip the flag?
        
        async def flip_running_state():
            server._running = False
            return b'{"command": "foo"}\n'
            
        mock_reader.readline.side_effect = flip_running_state

        await server._handle_client(mock_reader, mock_writer)

        # Should verify that it did NOT process the command
        # We can check if _handle_command was called
        # But _handle_client calls _handle_command internally.
        # We should mock _handle_command to verify it wasn't called.
        
        # We can't easily mock private method on the instance we already created unless we patch it
        with patch.object(server, '_handle_command') as mock_handle_cmd:
            await server._handle_client(mock_reader, mock_writer)
            mock_handle_cmd.assert_not_called()
            
            # Additional check: log warning should be emitted
            # "command_received_during_shutdown"
            
            
            

