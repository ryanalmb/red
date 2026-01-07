
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from typer.testing import CliRunner
from cyberred.cli import app, IPCCommand, _send_ipc_request
from cyberred.daemon.ipc import IPCResponse, encode_message
import typer
# ensure cli imported for coverage
import cyberred.cli

runner = CliRunner()

def test_daemon_start_stale_socket(tmp_path):
    """Test daemon start when there is a stale socket file."""
    socket_path = tmp_path / "daemon.sock"
    socket_path.touch()
    
    def mock_main(**kwargs): 
        return asyncio.sleep(0.01)

    with patch("cyberred.cli.get_socket_path", return_value=socket_path), \
         patch("cyberred.cli.asyncio.open_unix_connection", side_effect=ConnectionRefusedError), \
         patch("cyberred.daemon.server.run_daemon", side_effect=mock_main):

         result = runner.invoke(app, ["daemon", "start"])
         assert result.exit_code == 0

def test_daemon_start_already_running(tmp_path):
    """Test daemon start when it is already running (alive)."""
    socket_path = tmp_path / "daemon.sock"
    socket_path.touch()
    
    mock_writer = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    mock_reader = MagicMock()

    async def mock_open(*args):
        return mock_reader, mock_writer

    with patch("cyberred.cli.get_socket_path", return_value=socket_path), \
         patch("cyberred.cli.asyncio.open_unix_connection", side_effect=mock_open):

         result = runner.invoke(app, ["daemon", "start"])
         assert result.exit_code == 1
         assert "Daemon is already running" in result.output

def test_daemon_stop_timeout(tmp_path):
    """Test daemon stop timeout waiting for pid removal."""
    socket_path = tmp_path / "daemon.sock"
    socket_path.touch()
    pid_path = tmp_path / "daemon.pid"
    
    mock_reader = MagicMock()
    mock_writer = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.wait_closed = AsyncMock()
    
    async def mock_readline():
        response = IPCResponse.create_ok(data={}, request_id="req")
        return encode_message(response)
    
    mock_reader.readline.side_effect = mock_readline
    
    async def mock_open(*args):
        return mock_reader, mock_writer
        
    with patch("cyberred.cli.get_settings") as mock_settings, \
         patch("cyberred.cli.get_socket_path", return_value=socket_path), \
         patch("cyberred.cli.asyncio.open_unix_connection", side_effect=mock_open), \
         patch("time.sleep", side_effect=None), \
         patch("typer.echo") as mock_echo:
         
        mock_settings.return_value.storage.base_path = str(tmp_path)
        pid_path.touch()
        
        result = runner.invoke(app, ["daemon", "stop"])
        assert result.exit_code == 0
        calls = [str(c) for c in mock_echo.mock_calls]
        assert any("Timeout awaiting shutdown" in c for c in calls)

def test_daemon_stop_failed_to_respond(tmp_path):
    """Test daemon stop when connection fails."""
    socket_path = tmp_path / "daemon.sock"
    socket_path.touch()
    
    with patch("cyberred.cli.get_socket_path", return_value=socket_path), \
         patch("cyberred.cli.asyncio.open_unix_connection", side_effect=ConnectionRefusedError):
         
         result = runner.invoke(app, ["daemon", "stop"])
         assert result.exit_code == 1
         assert "Failed to stop daemon" in result.output

@pytest.mark.asyncio
async def test_send_ipc_request_generic_error(tmp_path):
    """Test generic IPC error handling in _send_ipc_request directly."""
    socket_path = tmp_path / "daemon.sock"
    socket_path.touch()
    
    mock_reader = MagicMock()
    mock_writer = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.wait_closed = AsyncMock()
    
    # Mock response with generic error
    response = IPCResponse.create_error(message="Generic Error", request_id="req")
    mock_reader.readline = AsyncMock(return_value=encode_message(response))
    
    with patch("cyberred.cli.get_socket_path", return_value=socket_path), \
         patch("cyberred.cli.asyncio.open_unix_connection", return_value=(mock_reader, mock_writer)), \
         patch("typer.echo") as mock_echo:
         
         # Should raise typer.Exit(1)
         # and match "Error: Generic Error"
         
         with pytest.raises(typer.Exit) as exc:
             await _send_ipc_request(IPCCommand.SESSIONS_LIST)
         
         assert exc.value.exit_code == 1
         
         # Verify typer.echo called with error
         assert mock_echo.called
         calls = [str(c) for c in mock_echo.mock_calls]
         assert any("Generic Error" in c for c in calls)

def test_daemon_status_reraises_exit(tmp_path):
    """Test that daemon_status re-raises typer.Exit(1) from ipc request."""
    socket_path = tmp_path / "daemon.sock"
    socket_path.touch()
    pid_path = tmp_path / "daemon.pid"
    pid_path.touch()
    
    # We mock _send_ipc_request to raise typer.Exit(1)
    # daemon_status calls it via asyncio.run.
    
    with patch("cyberred.cli.get_socket_path", return_value=socket_path), \
         patch("cyberred.cli.get_settings") as mock_settings, \
         patch("cyberred.cli._send_ipc_request", side_effect=typer.Exit(code=1)), \
         patch("cyberred.cli.asyncio.run", side_effect=typer.Exit(code=1)):
         
         mock_settings.return_value.storage.base_path = str(tmp_path)
         
         result = runner.invoke(app, ["daemon", "status"])
         assert result.exit_code == 1


def test_sessions_reraises_exit(tmp_path):
    """Test that sessions command reraises typer.Exit to cover lines 288-289."""
    socket_path = tmp_path / "daemon.sock"
    socket_path.touch()
    
    with patch("cyberred.cli.get_socket_path", return_value=socket_path), \
         patch("cyberred.cli.asyncio.run", side_effect=typer.Exit(code=1)):
         
         result = runner.invoke(app, ["sessions"])
         assert result.exit_code == 1


def test_invalid_state_transition_other_command(tmp_path):
    """Test Invalid state transition error for non-pause/resume command (line 145)."""
    socket_path = tmp_path / "daemon.sock"
    socket_path.touch()
    
    mock_reader = MagicMock()
    mock_writer = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.wait_closed = AsyncMock()
    
    # Mock response with "Invalid state transition" for a non-pause/resume command
    response = IPCResponse.create_error(message="Invalid state transition: wrong state", request_id="req")
    mock_reader.readline = AsyncMock(return_value=encode_message(response))
    
    with patch("cyberred.cli.get_socket_path", return_value=socket_path), \
         patch("cyberred.cli.asyncio.open_unix_connection", return_value=(mock_reader, mock_writer)):
         
         # Use ENGAGEMENT_STOP which is neither pause nor resume
         result = runner.invoke(app, ["stop", "test-engagement"])
         assert result.exit_code == 1
         assert "Invalid state transition" in result.output
