"""Unit tests for Cyber-Red CLI.

Tests the CLI entry point and all commands per Story 2.1.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from typer.testing import CliRunner

from cyberred.cli import app
from cyberred.core.config import ConfigurationError

if TYPE_CHECKING:
    from click.testing import Result

runner = CliRunner()


class TestCLIUtils:
    """Tests for CLI helper functions."""

    def test_get_socket_path(self) -> None:
        """Test get_socket_path returns correct path from settings."""
        from cyberred.cli import get_socket_path
        
        # Should rely on default settings which point to ~/.cyber-red
        path = get_socket_path()
        assert path.name == "daemon.sock"
        assert ".cyber-red" in str(path)

    def test_configure_logging(self) -> None:
        """Test logging configuration."""
        from cyberred.cli import configure_logging
        
        # Should run without error
        configure_logging()


class TestCLIHelp:
    """Tests for CLI help and command discovery."""

    def test_help_shows_all_commands(self) -> None:
        """Test that --help shows all expected commands."""
        result: Result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # Top-level commands
        assert "daemon" in result.output
        assert "sessions" in result.output
        assert "attach" in result.output
        assert "detach" in result.output
        assert "new" in result.output
        assert "pause" in result.output
        assert "resume" in result.output
        assert "stop" in result.output

    def test_daemon_help_shows_subcommands(self) -> None:
        """Test that daemon --help shows start/stop/status."""
        result: Result = runner.invoke(app, ["daemon", "--help"])
        assert result.exit_code == 0
        assert "start" in result.output
        assert "stop" in result.output
        assert "status" in result.output

    def test_no_args_shows_help(self) -> None:
        """Test that invoking with no args shows help."""
        result: Result = runner.invoke(app, [])
        # no_args_is_help=True shows help with exit code 0
        assert "Cyber-Red" in result.output or "Usage" in result.output


class TestDaemonCommands:
    """Tests for daemon subcommands."""

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.run")
    def test_daemon_start_default(
        self, mock_asyncio_run: MagicMock, mock_socket_path: MagicMock, tmp_path: Path
    ) -> None:
        """Test daemon start with defaults."""
        # Socket doesn't exist (daemon not running)
        mock_socket_path.return_value = tmp_path / "daemon.sock"
        
        result: Result = runner.invoke(app, ["daemon", "start"])
        assert result.exit_code == 0
        assert "Starting daemon..." in result.output
        mock_asyncio_run.assert_called_once()

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.run")
    def test_daemon_start_foreground(
        self, mock_asyncio_run: MagicMock, mock_socket_path: MagicMock, tmp_path: Path
    ) -> None:
        """Test daemon start with --foreground flag."""
        mock_socket_path.return_value = tmp_path / "daemon.sock"
        
        result: Result = runner.invoke(app, ["daemon", "start", "--foreground"])
        assert result.exit_code == 0
        assert "foreground" in result.output
        mock_asyncio_run.assert_called_once()

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.run")
    @patch("cyberred.cli.get_settings")
    def test_daemon_start_with_config(
        self, mock_get_settings: MagicMock, mock_asyncio_run: MagicMock, 
        mock_socket_path: MagicMock, tmp_path: Path
    ) -> None:
        """Test daemon start with valid config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("test: value\n")
        mock_socket_path.return_value = tmp_path / "daemon.sock"
        
        result: Result = runner.invoke(app, ["--config", str(config_file), "daemon", "start"])
        
        assert result.exit_code == 0
        assert "Starting daemon..." in result.output
        # Verify get_settings was called with force_reload=True and path
        mock_get_settings.assert_any_call(force_reload=True, system_config_path=config_file)

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.get_settings")
    def test_daemon_start_config_error(self, mock_get_settings: MagicMock, mock_socket_path: MagicMock, tmp_path: Path) -> None:
        """Test daemon start with invalid config file."""
        config_file = tmp_path / "config.yaml"
        config_file.touch()
        
        # Ensure daemon check passes
        mock_socket_path.return_value = tmp_path / "nonexistent.sock"
        
        # Make get_settings fail only when called with force_reload=True
        # But since side_effect applies to all calls, and we mocked socket_path,
        # get_settings should only be called during the reload block now.
        mock_get_settings.side_effect = ConfigurationError(str(config_file), "Invalid YAML")
        
        result: Result = runner.invoke(app, ["--config", str(config_file), "daemon", "start"])
        
        assert result.exit_code == 1
        assert "Error loading config" in result.output

    @patch("cyberred.cli.get_socket_path")
    def test_daemon_start_config_not_found(self, mock_socket_path: MagicMock, tmp_path: Path) -> None:
        """Test daemon start with non-existent config file."""
        # Ensure daemon check passes
        mock_socket_path.return_value = tmp_path / "nonexistent.sock"
        
        config_file = tmp_path / "nonexistent.yaml"
        result: Result = runner.invoke(app, ["--config", str(config_file), "daemon", "start"])
        assert result.exit_code == 1
        assert "not found" in result.output

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.open_unix_connection")
    def test_daemon_start_already_running(
        self, mock_connect: AsyncMock, mock_socket_path: MagicMock, tmp_path: Path
    ) -> None:
        """Test daemon start when already running."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()
        mock_socket_path.return_value = socket_file
        
        # Mock successful connection (liveness check)
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_writer.close = MagicMock()
        
        # Make side_effect return a tuple as expected by await open_unix_connection
        async def mock_open(*args):
            return mock_reader, mock_writer
        
        mock_connect.side_effect = mock_open
        
        result: Result = runner.invoke(app, ["daemon", "start"])
        assert result.exit_code == 1
        assert "already running" in result.output

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.open_unix_connection")
    def test_daemon_stop(self, mock_connect: AsyncMock, mock_socket_path: MagicMock, tmp_path: Path) -> None:
        """Test daemon stop command."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()
        mock_socket_path.return_value = socket_file
        
        # Mock successful IPC response for send_stop
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        
        async def mock_readline():
            from cyberred.daemon.ipc import IPCResponse, encode_message
            response = IPCResponse.create_ok(data={"stopping": True}, request_id="req")
            return encode_message(response)
            
        mock_reader.readline.side_effect = mock_readline
        mock_writer.drain.side_effect = AsyncMock()
        # wait_closed is called in send_stop
        mock_writer.wait_closed.side_effect = AsyncMock()
        mock_writer.close = MagicMock()
        
        # open_unix_connection returns (reader, writer)
        async def mock_open(*args):
            return mock_reader, mock_writer
            
        mock_connect.side_effect = mock_open
        
        # Cleanup file to simulate shutdown so polling exits immediately
        # Patching Path.exists logic locally for the poller?
        # The poller checks pid_path.exists() and socket_path.exists()
        # We can just unlink the file after the connect call maybe?
        # Or patch Path.exists but that affects the first check too.
        # Let's just unlink it in a separate thread? No.
        # Let's mock time.sleep to unlink the file?
        with patch("time.sleep") as mock_sleep:
             def side_effect_sleep(*args):
                 if socket_file.exists():
                     socket_file.unlink()
             mock_sleep.side_effect = side_effect_sleep
             
             result = runner.invoke(app, ["daemon", "stop"])

        assert result.exit_code == 0
        assert "Daemon stopping..." in result.output
        assert "Done." in result.output

    @patch("cyberred.cli.get_socket_path")
    def test_daemon_stop_not_running(self, mock_socket_path: MagicMock, tmp_path: Path) -> None:
        """Test daemon stop when not running."""
        mock_socket_path.return_value = tmp_path / "nonexistent.sock"
        
        result: Result = runner.invoke(app, ["daemon", "stop"])
        assert result.exit_code == 1
        assert "not running" in result.output

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.open_unix_connection")
    @patch("pathlib.Path.exists")
    def test_daemon_stop_timeout(
        self,
        mock_exists,
        mock_connect,
        mock_socket_path,
        tmp_path,
    ) -> None:
        """Test daemon stop times out if files persist."""
        mock_socket_path.return_value = tmp_path / "daemon.sock"

        # Mock successful IPC response for send_stop
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        
        async def mock_readline():
            from cyberred.daemon.ipc import IPCResponse, encode_message
            response = IPCResponse.create_ok(data={"stopping": True}, request_id="req")
            return encode_message(response)
        
        mock_reader.readline.side_effect = mock_readline
        mock_writer.drain.side_effect = AsyncMock()
        mock_writer.wait_closed.side_effect = AsyncMock()
        mock_writer.close = MagicMock()
        
        mock_connect.return_value = (mock_reader, mock_writer)

        # Files persist forever (simulating stuck daemon)
        mock_exists.return_value = True
        
        # Mock sleep to run instantly
        with patch("time.sleep"):
            result = runner.invoke(app, ["daemon", "stop"])

        assert result.exit_code == 0
        # Should have printed timeout warning
        assert "Timeout awaiting shutdown" in result.output
        assert "Done." not in result.output

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.open_unix_connection")
    def test_daemon_stop_connection_error(
        self,
        mock_connect,
        mock_socket_path,
        tmp_path,
    ) -> None:
        """Test daemon stop handling connection errors (daemon died/unreachable)."""
        mock_socket_path.return_value = tmp_path / "daemon.sock"
        # Socket file exists, so we try to connect
        mock_socket_path.return_value.touch()

        # Connect fails
        mock_connect.side_effect = ConnectionRefusedError("Connection refused")

        result = runner.invoke(app, ["daemon", "stop"])

        assert result.exit_code == 1
        assert "Failed to stop daemon" in result.output

    @patch("cyberred.cli.get_socket_path")
    def test_daemon_status_not_running(self, mock_socket_path: MagicMock, tmp_path: Path) -> None:
        """Test daemon status when not running (socket doesn't exist)."""
        mock_socket_path.return_value = tmp_path / "nonexistent.sock"
        
        result: Result = runner.invoke(app, ["daemon", "status"])
        assert result.exit_code == 1
        assert "not running" in result.output

    def test_daemon_status_running(self, tmp_path: Path) -> None:
        """Test daemon status when running (socket exists)."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()
        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text("12345")
        
        with patch("cyberred.cli.get_settings") as mock_get_settings, \
             patch("cyberred.cli.get_socket_path") as mock_socket_path, \
             patch("cyberred.cli.asyncio.open_unix_connection", new_callable=AsyncMock) as mock_connect:
            
            mock_socket_path.return_value = socket_file
            mock_get_settings.return_value.storage.base_path = str(tmp_path)
            
            # Mock IPC response
            mock_reader = MagicMock()
            mock_writer = MagicMock()
            
            async def mock_readline():
                from cyberred.daemon.ipc import IPCResponse, encode_message
                response = IPCResponse.create_ok(
                    data={"engagements": [{"id": "test-1", "state": "RUNNING"}]}, 
                    request_id="test-req-id"
                )
                return encode_message(response)
                
            mock_reader.readline.side_effect = mock_readline
            mock_writer.drain.side_effect = AsyncMock()
            mock_writer.wait_closed.side_effect = AsyncMock()
            
            mock_connect.return_value = (mock_reader, mock_writer)
            
            result: Result = runner.invoke(app, ["daemon", "status"])
            assert result.exit_code == 0
            assert "Daemon running" in result.output
            assert "12345" in result.output
            assert "1 active engagements" in result.output


class TestSessionCommands:
    """Tests for session management commands."""

    def test_sessions_list(self, tmp_path: Path) -> None:
        """Test sessions command lists engagements."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()
        
        with patch("cyberred.cli.get_socket_path") as mock_socket_path, \
             patch("cyberred.cli.asyncio.open_unix_connection", new_callable=AsyncMock) as mock_connect:
            
            mock_socket_path.return_value = socket_file
            
            mock_reader = MagicMock()
            mock_writer = MagicMock()
            
            async def mock_readline():
                from cyberred.daemon.ipc import IPCResponse, encode_message
                response = IPCResponse.create_ok(data={"engagements": []}, request_id="req")
                return encode_message(response)
                
            mock_reader.readline.side_effect = mock_readline
            mock_writer.drain.side_effect = AsyncMock()
            mock_writer.wait_closed.side_effect = AsyncMock()
            mock_connect.return_value = (mock_reader, mock_writer)

            result: Result = runner.invoke(app, ["sessions"])
            assert result.exit_code == 0
            assert "0 engagements" in result.output

    @patch("cyberred.cli._send_ipc_request")
    def test_sessions_list_connection_error(self, mock_send: MagicMock) -> None:
        """Test sessions list error handling."""
        mock_send.side_effect = typer.Exit(code=1)
        
        result: Result = runner.invoke(app, ["sessions"])
        assert result.exit_code == 1

    def test_attach(self, tmp_path: Path) -> None:
        """Test attach command launches TUI with TUIClient."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()

        with patch("cyberred.cli.get_socket_path") as mock_socket_path, \
             patch("cyberred.cli.asyncio.open_unix_connection", new_callable=AsyncMock) as mock_connect, \
             patch("cyberred.tui.daemon_client.TUIClient") as mock_client_cls, \
             patch("cyberred.tui.app.CyberRedApp") as mock_app_cls:

            mock_socket_path.return_value = socket_file

            # Mock IPC responses for attach checks
            mock_reader = MagicMock()
            mock_writer = MagicMock()

            async def mock_readline():
                from cyberred.daemon.ipc import IPCResponse, encode_message
                return encode_message(IPCResponse.create_ok(
                    data={"subscription_id": "sub-123", "state": "RUNNING"},
                    request_id="req"
                ))

            mock_reader.readline.side_effect = mock_readline
            mock_writer.drain.side_effect = AsyncMock()
            mock_writer.wait_closed.side_effect = AsyncMock()
            mock_connect.return_value = (mock_reader, mock_writer)

            # Mock TUIClient
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock()
            mock_client.close = AsyncMock()
            mock_client_cls.return_value = mock_client

            # Mock CyberRedApp
            mock_app = MagicMock()
            mock_app.run_async = AsyncMock()
            mock_app_cls.return_value = mock_app

            result: Result = runner.invoke(app, ["attach", "test-engagement"])
            
            # The command should complete (TUI mocked)
            assert result.exit_code == 0
            # TUIClient should be created and used
            mock_client_cls.assert_called_once()
            mock_app_cls.assert_called_once()

    def test_attach_requires_id(self) -> None:
        """Test attach fails without engagement ID."""
        result: Result = runner.invoke(app, ["attach"])
        assert result.exit_code != 0

    def test_attach_daemon_not_running(self, tmp_path: Path) -> None:
        """Test attach when daemon is not running (socket doesn't exist)."""
        from cyberred.tui.daemon_client import DaemonNotRunningError

        with patch("cyberred.cli.get_socket_path") as mock_socket_path, \
             patch("cyberred.tui.daemon_client.TUIClient") as mock_client_cls:

            mock_socket_path.return_value = tmp_path / "nonexistent.sock"

            # Mock TUIClient to raise DaemonNotRunningError
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(side_effect=DaemonNotRunningError("not running"))
            mock_client.close = AsyncMock()
            mock_client_cls.return_value = mock_client

            result: Result = runner.invoke(app, ["attach", "test-engagement"])
            assert result.exit_code == 1
            assert "Daemon not running" in result.output

    def test_detach(self, tmp_path: Path) -> None:
        """Test detach command."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()

        with patch("cyberred.cli.get_socket_path") as mock_socket_path, \
             patch("cyberred.cli.asyncio.open_unix_connection", new_callable=AsyncMock) as mock_connect:

            mock_socket_path.return_value = socket_file

            mock_reader = MagicMock()
            mock_writer = MagicMock()
            async def mock_readline():
                from cyberred.daemon.ipc import IPCResponse, encode_message
                return encode_message(IPCResponse.create_ok(data={}, request_id="req"))
            mock_reader.readline.side_effect = mock_readline
            mock_writer.drain.side_effect = AsyncMock()
            mock_writer.wait_closed.side_effect = AsyncMock()
            mock_connect.return_value = (mock_reader, mock_writer)

            result: Result = runner.invoke(app, ["detach", "test-engagement"])
            assert result.exit_code == 0
            assert "Detached from test-engagement" in result.output


    def test_new_engagement_with_valid_config(self, tmp_path: Path) -> None:
        """Test new engagement with valid config."""
        config_file = tmp_path / "engagement.yaml"
        # Minimum valid EngagementConfig
        config_file.write_text("name: Test Engagement\n")
        
        result: Result = runner.invoke(app, ["new", "--config", str(config_file)])
        assert result.exit_code == 0
        assert "Starting engagement" in result.output

    def test_new_engagement_invalid_yaml(self, tmp_path: Path) -> None:
        """Test new engagement with invalid YAML."""
        config_file = tmp_path / "engagement.yaml"
        config_file.write_text("invalid: [yaml\n")
        
        result: Result = runner.invoke(app, ["new", "--config", str(config_file)])
        assert result.exit_code == 1
        assert "Invalid engagement config" in result.output

    def test_new_engagement_schema_validation_error(self, tmp_path: Path) -> None:
        """Test new engagement with invalid schema."""
        config_file = tmp_path / "engagement.yaml"
        # max_agents must be positive int
        config_file.write_text("max_agents: -5\n")
        
        result: Result = runner.invoke(app, ["new", "--config", str(config_file)])
        assert result.exit_code == 1
        assert "Invalid engagement config" in result.output

    def test_new_engagement_config_not_found(self, tmp_path: Path) -> None:
        """Test new engagement with non-existent config."""
        config_file = tmp_path / "nonexistent.yaml"
        result: Result = runner.invoke(app, ["new", "--config", str(config_file)])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_new_engagement_requires_config(self) -> None:
        """Test new engagement fails without config."""
        result: Result = runner.invoke(app, ["new"])
        assert result.exit_code != 0

    # ==================== PAUSE COMMAND TESTS ====================

    @patch("cyberred.cli.get_socket_path")
    def test_pause_daemon_not_running(self, mock_socket_path: MagicMock, tmp_path: Path) -> None:
        """Test pause when daemon is not running (socket doesn't exist)."""
        mock_socket_path.return_value = tmp_path / "nonexistent.sock"
        
        result: Result = runner.invoke(app, ["pause", "test-engagement"])
        assert result.exit_code == 1
        assert "Daemon not running" in result.output

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.open_unix_connection", new_callable=MagicMock)
    def test_pause_success(
        self, mock_connect: MagicMock, mock_socket_path: MagicMock, tmp_path: Path
    ) -> None:
        """Test pause command success path."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()
        mock_socket_path.return_value = socket_file
        
        # Mock successful IPC response
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        
        # AsyncMock for async methods
        async def mock_readline():
            from cyberred.daemon.ipc import IPCResponse, encode_message
            response = IPCResponse.create_ok(data={"state": "PAUSED"}, request_id="test-req-id")
            return encode_message(response)
            
        async def mock_drain(): 
            pass
            
        async def mock_wait_closed():
            pass

        mock_reader.readline.side_effect = mock_readline
        mock_writer.drain.side_effect = mock_drain
        mock_writer.wait_closed.side_effect = mock_wait_closed
        
        # open_unix_connection returns (reader, writer)
        async def mock_open(*args):
            return mock_reader, mock_writer
            
        mock_connect.side_effect = mock_open
        
        result: Result = runner.invoke(app, ["pause", "test-engagement"])
        assert result.exit_code == 0
        assert "paused" in result.output.lower()
        assert "state preserved in memory" in result.output.lower()

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.open_unix_connection", new_callable=MagicMock)
    def test_pause_engagement_not_found(
        self, mock_connect: MagicMock, mock_socket_path: MagicMock, tmp_path: Path
    ) -> None:
        """Test pause when engagement not found."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()
        mock_socket_path.return_value = socket_file
        
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        
        async def mock_readline():
            from cyberred.daemon.ipc import IPCResponse, encode_message
            response = IPCResponse.create_error("Engagement not found: invalid-id", request_id="test-req-id")
            return encode_message(response)
        
        async def mock_drain(): pass
        async def mock_wait_closed(): pass

        mock_reader.readline.side_effect = mock_readline
        mock_writer.drain.side_effect = mock_drain
        mock_writer.wait_closed.side_effect = mock_wait_closed
        
        async def mock_open(*args): return mock_reader, mock_writer
        mock_connect.side_effect = mock_open
        
        result: Result = runner.invoke(app, ["pause", "invalid-id"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.open_unix_connection", new_callable=MagicMock)
    def test_pause_invalid_state(
        self, mock_connect: MagicMock, mock_socket_path: MagicMock, tmp_path: Path
    ) -> None:
        """Test pause when engagement not in RUNNING state."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()
        mock_socket_path.return_value = socket_file
        
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        
        async def mock_readline():
            from cyberred.daemon.ipc import IPCResponse, encode_message
            response = IPCResponse.create_error("Invalid state transition: not running", request_id="test-req-id")
            return encode_message(response)
            
        async def mock_drain(): pass
        async def mock_wait_closed(): pass

        mock_reader.readline.side_effect = mock_readline
        mock_writer.drain.side_effect = mock_drain
        mock_writer.wait_closed.side_effect = mock_wait_closed
        
        async def mock_open(*args): return mock_reader, mock_writer
        mock_connect.side_effect = mock_open
        
        result: Result = runner.invoke(app, ["pause", "test-engagement"])
        assert result.exit_code == 1
        assert "Cannot pause" in result.output or "not running" in result.output.lower()

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.open_unix_connection", new_callable=MagicMock)
    def test_pause_connection_error(
        self, mock_connect: MagicMock, mock_socket_path: MagicMock, tmp_path: Path
    ) -> None:
        """Test pause when daemon connection fails (but socket file exists)."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()
        mock_socket_path.return_value = socket_file
        
        async def mock_open(*args):
            raise ConnectionRefusedError("Connection refused")
        mock_connect.side_effect = mock_open
        
        result: Result = runner.invoke(app, ["pause", "test-engagement"])
        assert result.exit_code == 1
        assert "Daemon not running" in result.output

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.open_unix_connection", new_callable=MagicMock)
    def test_pause_generic_error(
        self, mock_connect: MagicMock, mock_socket_path: MagicMock, tmp_path: Path
    ) -> None:
        """Test pause when a generic unknown error occurs."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()
        mock_socket_path.return_value = socket_file
        
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        
        async def mock_readline():
            from cyberred.daemon.ipc import IPCResponse, encode_message
            response = IPCResponse.create_error("Something bad happened", request_id="test-req-id")
            return encode_message(response)
            
        async def mock_drain(): pass
        async def mock_wait_closed(): pass

        mock_reader.readline.side_effect = mock_readline
        mock_writer.drain.side_effect = mock_drain
        mock_writer.wait_closed.side_effect = mock_wait_closed
        
        async def mock_open(*args): return mock_reader, mock_writer
        mock_connect.side_effect = mock_open
        
        result: Result = runner.invoke(app, ["pause", "test-engagement"])
        assert result.exit_code == 1
        assert "Error: Something bad happened" in result.output

    # ==================== RESUME COMMAND TESTS ====================

    @patch("cyberred.cli.get_socket_path")
    def test_resume_daemon_not_running(self, mock_socket_path: MagicMock, tmp_path: Path) -> None:
        """Test resume when daemon is not running (socket doesn't exist)."""
        mock_socket_path.return_value = tmp_path / "nonexistent.sock"
        
        result: Result = runner.invoke(app, ["resume", "test-engagement"])
        assert result.exit_code == 1
        assert "Daemon not running" in result.output

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.open_unix_connection", new_callable=MagicMock)
    def test_resume_success(
        self, mock_connect: MagicMock, mock_socket_path: MagicMock, tmp_path: Path
    ) -> None:
        """Test resume command success path."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()
        mock_socket_path.return_value = socket_file
        
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        
        async def mock_readline():
            from cyberred.daemon.ipc import IPCResponse, encode_message
            response = IPCResponse.create_ok(data={"state": "RUNNING"}, request_id="test-req-id")
            return encode_message(response)
        
        async def mock_drain(): pass
        async def mock_wait_closed(): pass

        mock_reader.readline.side_effect = mock_readline
        mock_writer.drain.side_effect = mock_drain
        mock_writer.wait_closed.side_effect = mock_wait_closed
        
        async def mock_open(*args): return mock_reader, mock_writer
        mock_connect.side_effect = mock_open
        
        result: Result = runner.invoke(app, ["resume", "test-engagement"])
        assert result.exit_code == 0
        assert "resumed" in result.output.lower()

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.open_unix_connection", new_callable=MagicMock)
    def test_resume_engagement_not_found(
        self, mock_connect: MagicMock, mock_socket_path: MagicMock, tmp_path: Path
    ) -> None:
        """Test resume when engagement not found."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()
        mock_socket_path.return_value = socket_file
        
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        
        async def mock_readline():
            from cyberred.daemon.ipc import IPCResponse, encode_message
            response = IPCResponse.create_error("Engagement not found: invalid-id", request_id="test-req-id")
            return encode_message(response)
            
        async def mock_drain(): pass
        async def mock_wait_closed(): pass

        mock_reader.readline.side_effect = mock_readline
        mock_writer.drain.side_effect = mock_drain
        mock_writer.wait_closed.side_effect = mock_wait_closed
        
        async def mock_open(*args): return mock_reader, mock_writer
        mock_connect.side_effect = mock_open
        
        result: Result = runner.invoke(app, ["resume", "invalid-id"])
        
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.open_unix_connection", new_callable=MagicMock)
    def test_resume_invalid_state(
        self, mock_connect: MagicMock, mock_socket_path: MagicMock, tmp_path: Path
    ) -> None:
        """Test resume when engagement not in PAUSED state."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()
        mock_socket_path.return_value = socket_file
        
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        
        async def mock_readline():
            from cyberred.daemon.ipc import IPCResponse, encode_message
            response = IPCResponse.create_error("Invalid state transition: not paused", request_id="test-req-id")
            return encode_message(response)
            
        async def mock_drain(): pass
        async def mock_wait_closed(): pass

        mock_reader.readline.side_effect = mock_readline
        mock_writer.drain.side_effect = mock_drain
        mock_writer.wait_closed.side_effect = mock_wait_closed
        
        async def mock_open(*args): return mock_reader, mock_writer
        mock_connect.side_effect = mock_open
        
        result: Result = runner.invoke(app, ["resume", "test-engagement"])
        assert result.exit_code == 1
        assert "Cannot resume" in result.output or "not paused" in result.output.lower()

    @patch("cyberred.cli.get_socket_path")
    @patch("cyberred.cli.asyncio.open_unix_connection", new_callable=MagicMock)
    def test_resume_connection_error(
        self, mock_connect: MagicMock, mock_socket_path: MagicMock, tmp_path: Path
    ) -> None:
        """Test resume when daemon connection fails."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()
        mock_socket_path.return_value = socket_file
        
        async def mock_open(*args): raise ConnectionRefusedError
        mock_connect.side_effect = mock_open
        
        result: Result = runner.invoke(app, ["resume", "test-engagement"])
        assert result.exit_code == 1
        assert "Daemon not running" in result.output

    # ==================== STOP COMMAND TESTS (placeholder) ====================

    def test_stop_engagement(self, tmp_path: Path) -> None:
        """Test stop command."""
        socket_file = tmp_path / "daemon.sock"
        socket_file.touch()
        
        with patch("cyberred.cli.get_socket_path") as mock_socket_path, \
             patch("cyberred.cli.asyncio.open_unix_connection", new_callable=AsyncMock) as mock_connect:
        
            mock_socket_path.return_value = socket_file
            
            mock_reader = MagicMock()
            mock_writer = MagicMock()
            async def mock_readline():
                from cyberred.daemon.ipc import IPCResponse, encode_message
                return encode_message(IPCResponse.create_ok(
                    data={"state": "STOPPED", "checkpoint_path": "/tmp/checkpoint.sqlite"}, 
                    request_id="req"
                ))
            mock_reader.readline.side_effect = mock_readline
            mock_writer.drain.side_effect = AsyncMock()
            mock_writer.wait_closed.side_effect = AsyncMock()
            mock_connect.return_value = (mock_reader, mock_writer)

            result: Result = runner.invoke(app, ["stop", "test-engagement"])
            assert result.exit_code == 0
            assert "stopped" in result.output.lower()
            assert "checkpoint" in result.output.lower()

    def test_global_config_option(self, tmp_path: Path) -> None:
        """Test global --config option triggers load_config."""
        config_file = tmp_path / "global_config.yaml"
        config_file.write_text("test: global\n")
        
        # We patch load_config_callback directly or spy on it?
        # Since it's a callback, we can verify it's called using settings side effect
        with patch("cyberred.cli.get_settings") as mock_get_settings:
            # We skip socket check for sessions list command mock
            with patch("cyberred.cli.get_socket_path") as mock_socket_path, \
                 patch("cyberred.cli.asyncio.open_unix_connection", new_callable=AsyncMock) as mock_connect:

                socket_file = tmp_path / "daemon.sock"
                socket_file.touch()
                mock_socket_path.return_value = socket_file
                
                mock_reader = MagicMock()
                mock_writer = MagicMock()
                async def mock_readline():
                    from cyberred.daemon.ipc import IPCResponse, encode_message
                    return encode_message(IPCResponse.create_ok(data={"engagements": []}, request_id="req"))
                mock_reader.readline.side_effect = mock_readline
                mock_writer.drain.side_effect = AsyncMock()
                mock_writer.wait_closed.side_effect = AsyncMock()
                mock_connect.return_value = (mock_reader, mock_writer)
                
                result: Result = runner.invoke(app, ["--config", str(config_file), "sessions"])
                
                assert result.exit_code == 0
                
                # Check get_settings called with force_reload=True and path
                calls = mock_get_settings.call_args_list
                
                reload_call = None
                for call in calls:
                    if call.kwargs.get("force_reload") and str(call.kwargs.get("system_config_path")) == str(config_file):
                        reload_call = call
                        break
                
                assert reload_call is not None, "get_settings(force_reload=True) not called with config file"


class TestDaemonSystemdCommands:
    """Tests for systemd-related daemon commands (install, uninstall, logs)."""

    @patch("os.geteuid")
    def test_daemon_install_not_root(self, mock_geteuid: MagicMock) -> None:
        """Test daemon install fails when not root."""
        mock_geteuid.return_value = 1000  # Non-root UID
        
        result = runner.invoke(app, ["daemon", "install"])
        assert result.exit_code == 1
        assert "requires root privileges" in result.output

    @patch("cyberred.cli.get_settings")
    @patch("cyberred.daemon.systemd.ensure_storage_directory")
    @patch("cyberred.daemon.systemd.write_service_file")
    @patch("cyberred.daemon.systemd.generate_service_file")
    @patch("cyberred.daemon.systemd.reload_systemd")
    @patch("cyberred.daemon.systemd.enable_service")
    @patch("os.geteuid")
    def test_daemon_install_success(
        self,
        mock_geteuid: MagicMock,
        mock_enable: MagicMock,
        mock_reload: MagicMock,
        mock_generate: MagicMock,
        mock_write: MagicMock,
        mock_ensure_storage: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test daemon install success with all steps."""
        mock_geteuid.return_value = 0  # Root
        mock_generate.return_value = "[Unit]\nDescription=Test\n"
        mock_settings.return_value.storage.base_path = str(tmp_path)
        
        result = runner.invoke(app, ["daemon", "install"])
        
        assert result.exit_code == 0
        assert "installed successfully" in result.output
        mock_generate.assert_called_once()
        mock_write.assert_called_once()
        mock_reload.assert_called_once()
        mock_enable.assert_called_once()

    @patch("cyberred.cli.get_settings")
    @patch("cyberred.daemon.systemd.ensure_storage_directory")
    @patch("cyberred.daemon.systemd.write_service_file")
    @patch("cyberred.daemon.systemd.generate_service_file")
    @patch("cyberred.daemon.systemd.reload_systemd")
    @patch("os.geteuid")
    def test_daemon_install_no_enable(
        self,
        mock_geteuid: MagicMock,
        mock_reload: MagicMock,
        mock_generate: MagicMock,
        mock_write: MagicMock,
        mock_ensure_storage: MagicMock,
        mock_settings: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test daemon install with --no-enable flag."""
        mock_geteuid.return_value = 0
        mock_generate.return_value = "[Unit]\nDescription=Test\n"
        mock_settings.return_value.storage.base_path = str(tmp_path)
        
        result = runner.invoke(app, ["daemon", "install", "--no-enable"])
        
        assert result.exit_code == 0
        assert "installed successfully" in result.output

    @patch("os.geteuid")
    def test_daemon_uninstall_not_root(self, mock_geteuid: MagicMock) -> None:
        """Test daemon uninstall fails when not root."""
        mock_geteuid.return_value = 1000
        
        result = runner.invoke(app, ["daemon", "uninstall"])
        assert result.exit_code == 1
        assert "requires root privileges" in result.output

    @patch("cyberred.daemon.systemd.stop_service")
    @patch("cyberred.daemon.systemd.disable_service")
    @patch("cyberred.daemon.systemd.remove_service_file")
    @patch("cyberred.daemon.systemd.reload_systemd")
    @patch("os.geteuid")
    def test_daemon_uninstall_success(
        self,
        mock_geteuid: MagicMock,
        mock_reload: MagicMock,
        mock_remove: MagicMock,
        mock_disable: MagicMock,
        mock_stop: MagicMock,
    ) -> None:
        """Test daemon uninstall success."""
        mock_geteuid.return_value = 0
        
        result = runner.invoke(app, ["daemon", "uninstall"])
        
        assert result.exit_code == 0
        assert "uninstalled successfully" in result.output
        mock_stop.assert_called_once()
        mock_disable.assert_called_once()
        mock_remove.assert_called_once()
        mock_reload.assert_called_once()

    @patch("subprocess.run")
    def test_daemon_logs_default(self, mock_run: MagicMock) -> None:
        """Test daemon logs with default options."""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = runner.invoke(app, ["daemon", "logs"])
        
        assert result.exit_code == 0
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "journalctl" in call_args
        assert "-n" in call_args
        assert "50" in call_args

    @patch("subprocess.run")
    def test_daemon_logs_follow(self, mock_run: MagicMock) -> None:
        """Test daemon logs with --follow flag."""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = runner.invoke(app, ["daemon", "logs", "--follow"])
        
        assert result.exit_code == 0
        call_args = mock_run.call_args[0][0]
        assert "-f" in call_args

    @patch("subprocess.run")
    def test_daemon_logs_journalctl_not_found(self, mock_run: MagicMock) -> None:
        """Test daemon logs when journalctl is not found."""
        mock_run.side_effect = FileNotFoundError("journalctl not found")
        
        result = runner.invoke(app, ["daemon", "logs"])
        
        assert result.exit_code == 1
        assert "journalctl not found" in result.output
