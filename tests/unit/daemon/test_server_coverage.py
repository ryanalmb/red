"""Additional coverage tests for DaemonServer."""
import pytest
import asyncio
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from cyberred.daemon.ipc import IPCRequest, IPCCommand, encode_message, decode_message
from cyberred.daemon.server import DaemonServer

@pytest.fixture
def temp_socket_path(tmp_path: Path) -> Path:
    return tmp_path / "test_cov.sock"

@pytest.fixture
def temp_pid_path(tmp_path: Path) -> Path:
    return tmp_path / "test_cov.pid"

class TestDaemonServerCoverage:
    @pytest.mark.asyncio
    async def test_shutdown_callback_not_called_if_none(self, temp_socket_path: Path, temp_pid_path: Path) -> None:
        """Verify nothing breaks if shutdown_callback is None during DAEMON_STOP."""
        server = DaemonServer(socket_path=temp_socket_path, pid_path=temp_pid_path)
        # Ensure it's None (default)
        assert server._shutdown_callback is None
        
        await server.start()
        
        reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))
        request = IPCRequest(command=IPCCommand.DAEMON_STOP, params={}, request_id="stop-no-cb")
        writer.write(encode_message(request))
        await writer.drain()
        
        data = await reader.readline()
        response = decode_message(data)
        assert response.status == "ok"
        
        writer.close()
        await writer.wait_closed()
        await asyncio.sleep(0.1)
        assert not server._running

    @pytest.mark.asyncio
    async def test_engagement_lifecycle_missing_param_errors(self, temp_socket_path: Path, temp_pid_path: Path) -> None:
        """Test missing parameter errors for PAUSE, RESUME, STOP, START."""
        server = DaemonServer(socket_path=temp_socket_path, pid_path=temp_pid_path)
        await server.start()
        
        reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))
        
        commands = [
            (IPCCommand.ENGAGEMENT_START, "config_path"),
            (IPCCommand.ENGAGEMENT_PAUSE, "engagement_id"),
            (IPCCommand.ENGAGEMENT_RESUME, "engagement_id"),
            (IPCCommand.ENGAGEMENT_STOP, "engagement_id"),
        ]
        
        for cmd, param in commands:
            request = IPCRequest(command=cmd, params={}, request_id=f"test-{cmd}")
            writer.write(encode_message(request))
            await writer.drain()
            
            data = await reader.readline()
            response = decode_message(data)
            assert response.status == "error"
            assert f"Missing required parameter: {param}" in response.error
            
        writer.close()
        await writer.wait_closed()
        await server.stop()



    @pytest.mark.asyncio
    async def test_internal_error_handling(self, temp_socket_path: Path, temp_pid_path: Path) -> None:
        """Test generic exception handling in command handler."""
        server = DaemonServer(socket_path=temp_socket_path, pid_path=temp_pid_path)
        await server.start()
        
        # Mock session_manager.list_engagements to raise generic Exception
        server._session_manager.list_engagements = MagicMock(side_effect=RuntimeError("Boom"))
        
        reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))
        request = IPCRequest(command=IPCCommand.SESSIONS_LIST, params={}, request_id="test-error")
        writer.write(encode_message(request))
        await writer.drain()
        
        data = await reader.readline()
        response = decode_message(data)
        assert response.status == "error"
        assert "Internal error: Boom" in response.error
        
        writer.close()
        await writer.wait_closed()
        await server.stop()

    @pytest.mark.asyncio
    async def test_specific_exception_mapping(self, temp_socket_path: Path, temp_pid_path: Path) -> None:
        """Test mapping of specific exceptions to error responses."""
        from cyberred.core.exceptions import (
            EngagementNotFoundError, 
            InvalidStateTransition,
            ResourceLimitError,
        )
        
        server = DaemonServer(socket_path=temp_socket_path, pid_path=temp_pid_path)
        await server.start()
        reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))

        # 1. EngagementNotFoundError
        server.session_manager.pause_engagement = MagicMock(side_effect=EngagementNotFoundError("Not found"))
        req = IPCRequest(command=IPCCommand.ENGAGEMENT_PAUSE, params={"engagement_id": "x"}, request_id="1")
        writer.write(encode_message(req))
        await writer.drain()
        assert decode_message(await reader.readline()).error == "Engagement not found: Not found" # Msg depends on exc
        
        # 2. InvalidStateTransition
        server.session_manager.pause_engagement = MagicMock(side_effect=InvalidStateTransition("x", "A", "B"))
        req = IPCRequest(command=IPCCommand.ENGAGEMENT_PAUSE, params={"engagement_id": "x"}, request_id="2")
        writer.write(encode_message(req))
        await writer.drain()
        assert "Invalid state transition" in decode_message(await reader.readline()).error
        
        # 3. ResourceLimitError
        server.session_manager.create_engagement = MagicMock(side_effect=ResourceLimitError("Limit hit"))
        req = IPCRequest(command=IPCCommand.ENGAGEMENT_START, params={"config_path": "x"}, request_id="3")
        writer.write(encode_message(req))
        await writer.drain()
        assert "Limit hit" in decode_message(await reader.readline()).error # Msg depends on exc
        
        # 4. FileNotFoundError
        server.session_manager.create_engagement = MagicMock(side_effect=FileNotFoundError("No file"))
        req = IPCRequest(command=IPCCommand.ENGAGEMENT_START, params={"config_path": "x"}, request_id="4")
        writer.write(encode_message(req))
        await writer.drain()
        assert "No file" in decode_message(await reader.readline()).error

        writer.close()
        await writer.wait_closed()
        await server.stop()

    @pytest.mark.asyncio
    async def test_unhandled_command_fallback(self, temp_socket_path: Path, temp_pid_path: Path) -> None:
        """Test fallback for unhandled command keys."""
        server = DaemonServer(socket_path=temp_socket_path, pid_path=temp_pid_path)
        await server.start()
        
        # Monkeypatch IPCCommand to include a dummy value
        import cyberred.daemon.server as server_mod
        from enum import Enum
        
        # We need to trick the enum check in _handle_command
        # Instead of modifying Enum, let's mock IPCCommand class in server module
        original_enum = server_mod.IPCCommand
        
        class MockEnum(str, Enum):
            SESSIONS_LIST = "sessions.list"
            ENGAGEMENT_START = "engagement.start"
            ENGAGEMENT_ATTACH = "engagement.attach"
            ENGAGEMENT_DETACH = "engagement.detach"
            ENGAGEMENT_PAUSE = "engagement.pause"
            ENGAGEMENT_RESUME = "engagement.resume"
            ENGAGEMENT_STOP = "engagement.stop"
            DAEMON_STOP = "daemon.stop"
            DUMMY = "dummy.command"
            
        with patch("cyberred.daemon.server.IPCCommand", MockEnum):
            reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))
            # IPCRequest constructor validates against REAL IPCCommand, so we need to bypass validation
            # by manually constructing JSON
            req_json = '{"command": "dummy.command", "params": {}, "request_id": "fallback"}\n'
            writer.write(req_json.encode("utf-8"))
            await writer.drain()
            
            data = await reader.readline()
            response = decode_message(data)
            
            assert response.status == "ok"
            assert response.data == {} # Empty dict fallback
            
            writer.close()
            await writer.wait_closed()
            
        await server.stop()

    @pytest.mark.asyncio
    async def test_hard_limit_logging(self, temp_socket_path: Path, temp_pid_path: Path) -> None:
        """Test logging when hard limit is hit."""
        server = DaemonServer(socket_path=temp_socket_path, pid_path=temp_pid_path)
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        # Raise LimitOverrunError
        mock_reader.readline.side_effect = asyncio.LimitOverrunError("Boom", 100)
        
        server._clients.add(mock_writer)
        server._running = True
        
        # Patched log to verify warning
        with patch("cyberred.daemon.server.log") as mock_log:
            await server._handle_client(mock_reader, mock_writer)
            
            mock_log.warning.assert_any_call(
                "message_hard_limit_exceeded", 
                client_id=id(mock_writer)
            )
            
            
            mock_log.warning.assert_any_call(
                "message_hard_limit_exceeded", 
                client_id=id(mock_writer)
            )
            
        server._running = False
        server._clients.clear()

    @pytest.mark.asyncio
    async def test_write_error_inside_loop(self, temp_socket_path: Path, temp_pid_path: Path) -> None:
        """Test ConnectionResetError during write/drain inside the loop."""
        server = DaemonServer(socket_path=temp_socket_path, pid_path=temp_pid_path)
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        
        # Reader gives valid data first time, then Mock raises error on drain
        # valid request format
        req_json = '{"command": "sessions.list", "params": {}, "request_id": "1"}\n'
        mock_reader.readline.side_effect = [req_json.encode("utf-8"), b""]
        mock_writer.drain.side_effect = ConnectionResetError("Reset")
        
        server._clients.add(mock_writer)
        server._running = True
        
        await server._handle_client(mock_reader, mock_writer)
        
        # Should have logged client_disconnected_abruptly
        # (We can verify valid transition from try -> except(outer) -> finally)
        assert mock_writer not in server._clients

    @pytest.mark.asyncio
    async def test_generic_error_inside_loop(self, temp_socket_path: Path, temp_pid_path: Path) -> None:
        """Test generic RuntimeError during write/drain inside the loop."""
        server = DaemonServer(socket_path=temp_socket_path, pid_path=temp_pid_path)
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        
        # Valid request, then crash
        req_json = '{"command": "sessions.list", "params": {}, "request_id": "1"}\n'
        mock_reader.readline.side_effect = [req_json.encode("utf-8"), b""]
        mock_writer.drain.side_effect = RuntimeError("Panic")
        
        server._clients.add(mock_writer)
        server._running = True
        
        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Panic"):
            await server._handle_client(mock_reader, mock_writer)
            
        server._clients.clear()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_client_task_cancellation(self, temp_socket_path: Path, temp_pid_path: Path) -> None:
        """Test cancellation of client handler task triggers finally block."""
        server = DaemonServer(socket_path=temp_socket_path, pid_path=temp_pid_path)
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        
        # Valid request
        req_json = '{"command": "sessions.list", "params": {}, "request_id": "cancel"}\n'
        mock_reader.readline.return_value = req_json.encode("utf-8")
        
        # _handle_command raises CancelledError directly (simulating cancellation point)
        # We need to patch _handle_command
        # Since _handle_command is a method on the instance, we can patch it on the instance or class
        # But patching server._handle_command is easier?
        # server._handle_command is an async method.
        
        server._handle_command = MagicMock(side_effect=asyncio.CancelledError())

        server._clients.add(mock_writer)
        server._running = True
        
        # Should raise CancelledError
        try:
             await server._handle_client(mock_reader, mock_writer)
        except asyncio.CancelledError:
             pass
            
        # Finally block should have run (writer removed)
        assert mock_writer not in server._clients

    @pytest.mark.asyncio
    async def test_send_response_to_server(self, temp_socket_path: Path, temp_pid_path: Path) -> None:
        """Test sending an IPCResponse to server triggers protocol error."""
        server = DaemonServer(socket_path=temp_socket_path, pid_path=temp_pid_path)
        await server.start()
        
        reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))
        
        # Send a response object (valid JSON, but not a Request)
        # IPCResponse(status="ok", request_id="123")
        msg = '{"status": "ok", "request_id": "123"}\n'
        writer.write(msg.encode("utf-8"))
        await writer.drain()
        
        # Server should log warning and continue (no response sent back)
        # We can send a valid request immediately after to prove connection is alive
        req = IPCRequest(command=IPCCommand.SESSIONS_LIST, params={}, request_id="check")
        writer.write(encode_message(req))
        await writer.drain()
        
        data = await reader.readline()
        response = decode_message(data)
        assert response.status == "ok"
        assert response.request_id == "check"
        
        writer.close()
        await writer.wait_closed()
        await server.stop()

    @pytest.mark.asyncio
    async def test_preflight_error_handled(self, temp_socket_path: Path, temp_pid_path: Path, tmp_path: Path) -> None:
        """Test that preflight errors return IPC error response."""
        from cyberred.core.exceptions import PreFlightCheckError
        from cyberred.daemon.preflight import CheckResult, CheckStatus, CheckPriority
        
        server = DaemonServer(socket_path=temp_socket_path, pid_path=temp_pid_path)
        await server.start()
        
        # Mock preflight error in start_engagement
        error = PreFlightCheckError([CheckResult("P0_FAIL", CheckStatus.FAIL, CheckPriority.P0, "Blocking fail")])
        server._session_manager.start_engagement = AsyncMock(side_effect=error)
        
        reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))
        config_path = tmp_path / "eng.yaml"
        config_path.write_text("name: eng\n")
        
        request = IPCRequest(command=IPCCommand.ENGAGEMENT_START, params={"config_path": str(config_path)}, request_id="pf-err")
        writer.write(encode_message(request))
        await writer.drain()
        
        data = await reader.readline()
        response = decode_message(data)
        assert response.status == "error"
        assert "P0_FAIL" in response.error
        
        writer.close()
        await writer.wait_closed()
        await server.stop()

    @pytest.mark.asyncio
    async def test_handle_client_stopped_server(self) -> None:
        """Test _handle_client when server is not running (skips loop)."""
        server = DaemonServer()
        server._running = False # Stopped
        
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        
        await server._handle_client(mock_reader, mock_writer)
        
        # Should have exited immediately after finally block
        assert mock_writer.close.called
