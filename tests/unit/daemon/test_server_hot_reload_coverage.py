"""Targeted coverage tests for server.py hot reload integration.

Covers new lines in DaemonServer.start regarding ConfigWatcher.
"""
import asyncio
import os
import signal
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from cyberred.daemon.server import DaemonServer, run_daemon

@pytest.fixture
def temp_paths(tmp_path: [Path]):
    socket = tmp_path / "daemon.sock"
    pid = tmp_path / "daemon.pid"
    config = tmp_path / "config.yaml"
    return socket, pid, config

@pytest.mark.asyncio
async def test_server_starts_watcher_if_config_exists(temp_paths):
    socket, pid, config = temp_paths
    config.write_text("name: test\n")
    
    # Mock settings to point to tmp_path
    with patch("cyberred.daemon.server.get_settings") as mock_get_settings:
        settings_mock = mock_get_settings.return_value
        settings_mock.storage.base_path = str(config.parent)
        settings_mock.redis.port = 6379
        settings_mock.redis.host = "localhost"
        settings_mock.server.host = "localhost"
        settings_mock.server.port = 8080
        settings_mock.metrics.enabled = False
        
        # Mock _SettingsHolder to verify calls
        # Since server.py does local import, we patch the source
        with patch("cyberred.core.config._SettingsHolder") as MockSettingsHolder:
            server = DaemonServer(socket_path=socket, pid_path=pid)
            await server.start()
            
            # Check if start_watching was called
            MockSettingsHolder.start_watching.assert_called_once()
            args, _ = MockSettingsHolder.start_watching.call_args
            assert str(args[0]) == str(config)
            
            await server.stop()
            MockSettingsHolder.stop_watching.assert_called()

@pytest.mark.asyncio
async def test_server_start_watcher_exception_logged(temp_paths):
    socket, pid, config = temp_paths
    config.write_text("name: test\n")
    
    with patch("cyberred.daemon.server.get_settings") as mock_get_settings:
        settings_mock = mock_get_settings.return_value
        settings_mock.storage.base_path = str(config.parent)
        settings_mock.redis.port = 6379
        settings_mock.redis.host = "localhost"
        settings_mock.metrics.enabled = False
        
        with patch("cyberred.core.config._SettingsHolder") as MockSettingsHolder:
            MockSettingsHolder.start_watching.side_effect = Exception("Watcher failed")
            
            with patch("cyberred.daemon.server.log") as mock_log:
                server = DaemonServer(socket_path=socket, pid_path=pid)
                await server.start()
                
                # Should not raise, but log warning
                warning_calls = [
                    call for call in mock_log.warning.call_args_list
                    if call.args and "config_watcher_start_failed" in call.args[0]
                ]
                assert len(warning_calls) > 0
                
                await server.stop()

@pytest.mark.asyncio
async def test_sighup_handler_triggers_config_changes(temp_paths):
    """Test the local sighup_handler in run_daemon."""
    # This is tricky because sighup_handler is a closure.
    # We rely on test_sighup_handling_in_run_daemon in test_server.py 
    # but we want to verify it calls _handle_config_change.
    
    socket, pid, config = temp_paths
    config.write_text("name: test\n")

    with patch("cyberred.daemon.server.DaemonServer") as MockServer:
        mock_instance = AsyncMock()
        mock_instance.close = MagicMock()
        mock_instance._running = True
        MockServer.return_value = mock_instance
        
        with patch("cyberred.daemon.server.get_settings") as mock_get_settings:
            settings_mock = mock_get_settings.return_value
            settings_mock.storage.base_path = str(config.parent)
            settings_mock.redis.port = 6379
            settings_mock.redis.host = "localhost"
            settings_mock.metrics.enabled = False
            
            with patch("cyberred.core.config._SettingsHolder") as MockSettingsHolder:
                
                # We need to trigger SIGHUP.
                async def send_signal():
                    await asyncio.sleep(0.1)
                    os.kill(os.getpid(), signal.SIGHUP)
                    await asyncio.sleep(0.1)
                    os.kill(os.getpid(), signal.SIGINT)

                signal_task = asyncio.create_task(send_signal())

                try:
                    await run_daemon(foreground=True)
                except asyncio.CancelledError:
                    pass
                
                # Verify _handle_config_change was called
                # Wait, sighup_handler does local import of _SettingsHolder too?
                # Line 656: from cyberred.core.config import _SettingsHolder
                # So verify call on our patched mock
                
                MockSettingsHolder._handle_config_change.assert_called()
                
                if not signal_task.done():
                    signal_task.cancel()
                    try:
                        await signal_task
                    except:
                        pass
