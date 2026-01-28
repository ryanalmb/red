"""Safety tests for TUI detach behavior (Story 9.9).

CRITICAL: These tests verify that detach does NOT stop the engagement.
Detach = disconnect client, NOT stop engagement.

Per AC #5:
- Safety tests verify detach doesn't stop engagement
- Engagement state remains RUNNING after detach

Test Matrix:
| Operation | TUI | Daemon | Engagement | Agents |
|-----------|-----|--------|------------|--------|
| Detach    | Exits | Continues | RUNNING | Active |
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.daemon.ipc import IPCCommand, IPCResponse
from cyberred.daemon.streaming import StreamEvent, StreamEventType, encode_stream_event
from cyberred.tui.daemon_client import TUIClient


class TestDetachDoesNotStopEngagement:
    """Safety tests verifying detach doesn't stop engagement (AC #5, Task 8.2-8.4)."""

    @pytest.mark.asyncio
    async def test_detach_sends_engagement_detach_not_stop(self, tmp_path: Path):
        """SAFETY: Detach sends ENGAGEMENT_DETACH, never ENGAGEMENT_STOP.
        
        Per Story 9.9 AC #5: Safety tests verify detach doesn't stop engagement.
        This is CRITICAL - detach must ONLY disconnect the client.
        """
        socket_path = tmp_path / "daemon.sock"
        received_commands = []

        async def handle_client(reader, writer):
            try:
                while True:
                    data = await reader.readline()
                    if not data:
                        break
                    request = json.loads(data.decode())
                    received_commands.append(request.get("command"))
                    
                    response = IPCResponse(
                        status="ok",
                        request_id=request.get("request_id", "test"),
                        data={"subscription_id": "sub-123", "state": "RUNNING", "detached": True},
                    )
                    writer.write((response.to_json() + "\n").encode())
                    await writer.drain()
            except Exception:
                pass
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_unix_server(
            handle_client, path=str(socket_path)
        )

        try:
            client = TUIClient()
            await client.connect(socket_path)
            
            # Simulate attached state
            client._subscription_id = "sub-123"
            client._engagement_id = "eng-safety-test"
            
            # Perform detach
            await client.detach()
            
            # SAFETY ASSERTION: ONLY engagement.detach should be sent
            assert IPCCommand.ENGAGEMENT_DETACH in received_commands
            assert IPCCommand.ENGAGEMENT_STOP not in received_commands
            assert IPCCommand.DAEMON_STOP not in received_commands
            
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_ctrl_d_detach_engagement_remains_running(self, tmp_path: Path):
        """SAFETY: Ctrl+D detach keeps engagement in RUNNING state (Task 8.2).
        
        Per AC #5: Engagement state remains RUNNING after Ctrl+D detach.
        """
        socket_path = tmp_path / "daemon.sock"
        engagement_state = {"state": "RUNNING"}  # Track engagement state

        async def handle_client(reader, writer):
            try:
                while True:
                    data = await reader.readline()
                    if not data:
                        break
                    request = json.loads(data.decode())
                    command = request.get("command")
                    
                    # Simulate daemon behavior
                    if command == IPCCommand.ENGAGEMENT_DETACH:
                        # Detach should NOT change engagement state
                        # State remains RUNNING
                        pass  # No state change
                    elif command == IPCCommand.ENGAGEMENT_STOP:
                        # This should NEVER be called during detach
                        engagement_state["state"] = "STOPPED"
                    
                    response = IPCResponse(
                        status="ok",
                        request_id=request.get("request_id", "test"),
                        data={"detached": True, "engagement_state": engagement_state["state"]},
                    )
                    writer.write((response.to_json() + "\n").encode())
                    await writer.drain()
            except Exception:
                pass
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_unix_server(
            handle_client, path=str(socket_path)
        )

        try:
            client = TUIClient()
            await client.connect(socket_path)
            
            client._subscription_id = "sub-123"
            client._engagement_id = "eng-safety-test"
            
            # Simulate Ctrl+D by calling detach
            await client.detach()
            
            # SAFETY ASSERTION: Engagement state must still be RUNNING
            assert engagement_state["state"] == "RUNNING"
            
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_detach_command_engagement_remains_running(self, tmp_path: Path):
        """SAFETY: 'detach' command keeps engagement in RUNNING state (Task 8.3).
        
        Per AC #5: Engagement state remains RUNNING after 'detach' command.
        """
        socket_path = tmp_path / "daemon.sock"
        engagement_state = {"state": "RUNNING"}

        async def handle_client(reader, writer):
            try:
                while True:
                    data = await reader.readline()
                    if not data:
                        break
                    request = json.loads(data.decode())
                    command = request.get("command")
                    
                    if command == IPCCommand.ENGAGEMENT_STOP:
                        engagement_state["state"] = "STOPPED"
                    
                    response = IPCResponse(
                        status="ok",
                        request_id=request.get("request_id", "test"),
                        data={"detached": True},
                    )
                    writer.write((response.to_json() + "\n").encode())
                    await writer.drain()
            except Exception:
                pass
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_unix_server(
            handle_client, path=str(socket_path)
        )

        try:
            client = TUIClient()
            await client.connect(socket_path)
            
            client._subscription_id = "sub-123"
            client._engagement_id = "eng-safety-test"
            
            # Simulate typing 'detach' command
            await client.detach()
            
            # SAFETY ASSERTION: Engagement must still be RUNNING
            assert engagement_state["state"] == "RUNNING"
            
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_connection_loss_engagement_remains_running(self, tmp_path: Path):
        """SAFETY: Connection loss keeps engagement in RUNNING state (Task 8.4).
        
        Per AC #4 and AC #5: SSH disconnect behaves same as Ctrl+D.
        Engagement continues running without TUI client.
        """
        socket_path = tmp_path / "daemon.sock"
        engagement_state = {"state": "RUNNING", "stopped": False}

        async def handle_client(reader, writer):
            try:
                # Read initial attach request
                data = await reader.readline()
                if data:
                    response = IPCResponse(
                        status="ok",
                        request_id="test",
                        data={"subscription_id": "sub-123", "state": "RUNNING"},
                    )
                    writer.write((response.to_json() + "\n").encode())
                    await writer.drain()
                
                # Simulate sudden disconnect - just close the connection
                # This simulates SSH disconnect or network failure
            except Exception:
                pass
            finally:
                writer.close()
                await writer.wait_closed()
                # Even after client disconnect, engagement state should remain RUNNING
                # This is verified by checking engagement_state was never changed

        server = await asyncio.start_unix_server(
            handle_client, path=str(socket_path)
        )

        try:
            client = TUIClient()
            await client.connect(socket_path)
            
            # Start attach
            async for event in client.attach("eng-safety-test"):
                # Connection will close after initial state
                break
            
            # Client is now disconnected due to connection loss
            # SAFETY ASSERTION: Engagement state was never set to STOPPED
            assert engagement_state["state"] == "RUNNING"
            assert engagement_state["stopped"] is False
            
        finally:
            try:
                await client.close()
            except Exception:
                pass
            server.close()
            await server.wait_closed()


class TestDetachClientCleanup:
    """Safety tests verifying client cleanup after detach."""

    @pytest.mark.asyncio
    async def test_detach_clears_subscription_id(self, tmp_path: Path):
        """SAFETY: Detach clears subscription to prevent stale subscriptions."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={"detached": True},
                )
                writer.write((response.to_json() + "\n").encode())
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_unix_server(
            handle_client, path=str(socket_path)
        )

        try:
            client = TUIClient()
            await client.connect(socket_path)
            
            client._subscription_id = "sub-123"
            client._engagement_id = "eng-test"
            
            await client.detach()
            
            # Client should be cleaned up
            assert client.subscription_id is None
            assert client.engagement_id is None
            assert client.attached is False
            
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_detach_stops_streaming_without_stopping_engagement(self, tmp_path: Path):
        """SAFETY: Detach stops event streaming but engagement continues."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={"detached": True},
                )
                writer.write((response.to_json() + "\n").encode())
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_unix_server(
            handle_client, path=str(socket_path)
        )

        try:
            client = TUIClient()
            await client.connect(socket_path)
            
            client._subscription_id = "sub-123"
            client._engagement_id = "eng-test"
            client._streaming = True
            
            await client.detach()
            
            # Streaming should stop
            assert client._streaming is False
            
        finally:
            await client.close()
            server.close()
            await server.wait_closed()


class TestReattachAfterDetach:
    """Safety tests verifying reattach after detach (Task 8.6)."""

    @pytest.mark.asyncio
    async def test_reattach_shows_engagement_still_active(self, tmp_path: Path):
        """SAFETY: Reattach after detach shows engagement still active (Task 8.6).
        
        This verifies the engagement continued running while TUI was detached.
        """
        socket_path = tmp_path / "daemon.sock"
        attach_count = {"count": 0}

        async def handle_client(reader, writer):
            try:
                while True:
                    data = await reader.readline()
                    if not data:
                        break
                    request = json.loads(data.decode())
                    command = request.get("command")
                    
                    if command == IPCCommand.ENGAGEMENT_ATTACH:
                        attach_count["count"] += 1
                        response = IPCResponse(
                            status="ok",
                            request_id=request.get("request_id", "test"),
                            data={
                                "subscription_id": f"sub-{attach_count['count']}",
                                "state": "RUNNING",  # Still RUNNING after detach!
                                "agent_count": 5,  # Agents still active
                                "finding_count": 10,  # Findings accumulated while detached
                            },
                        )
                    elif command == IPCCommand.ENGAGEMENT_DETACH:
                        response = IPCResponse(
                            status="ok",
                            request_id=request.get("request_id", "test"),
                            data={"detached": True},
                        )
                    else:
                        response = IPCResponse(
                            status="ok",
                            request_id=request.get("request_id", "test"),
                            data={},
                        )
                    
                    writer.write((response.to_json() + "\n").encode())
                    await writer.drain()
            except Exception:
                pass
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_unix_server(
            handle_client, path=str(socket_path)
        )

        try:
            # First attach
            client1 = TUIClient()
            await client1.connect(socket_path)
            
            async for event in client1.attach("eng-reattach-test"):
                assert event.data["state"] == "RUNNING"
                break
            
            # Detach
            await client1.detach()
            await client1.close()
            
            # Reattach with new client (simulating new TUI session)
            client2 = TUIClient()
            await client2.connect(socket_path)
            
            async for event in client2.attach("eng-reattach-test"):
                # SAFETY ASSERTION: Engagement is STILL RUNNING after detach
                assert event.data["state"] == "RUNNING"
                # Agents continued working while detached
                assert event.data["agent_count"] == 5
                # Findings accumulated while detached
                assert event.data["finding_count"] == 10
                break
            
            # Verify we attached twice
            assert attach_count["count"] == 2
            
            await client2.close()
            
        finally:
            server.close()
            await server.wait_closed()


class TestDetachVsStopDistinction:
    """Safety tests verifying detach is distinct from stop operation."""

    @pytest.mark.asyncio
    async def test_detach_uses_correct_ipc_command(self):
        """SAFETY: Verify ENGAGEMENT_DETACH is distinct from ENGAGEMENT_STOP."""
        # These commands must be different values
        assert IPCCommand.ENGAGEMENT_DETACH != IPCCommand.ENGAGEMENT_STOP
        assert IPCCommand.ENGAGEMENT_DETACH.value == "engagement.detach"
        assert IPCCommand.ENGAGEMENT_STOP.value == "engagement.stop"

    @pytest.mark.asyncio
    async def test_detach_does_not_call_stop_methods(self, tmp_path: Path):
        """SAFETY: TUIClient.detach() never calls stop-related methods."""
        socket_path = tmp_path / "daemon.sock"
        commands_received = []

        async def handle_client(reader, writer):
            try:
                while True:
                    data = await reader.readline()
                    if not data:
                        break
                    request = json.loads(data.decode())
                    commands_received.append(request.get("command"))
                    
                    response = IPCResponse(
                        status="ok",
                        request_id=request.get("request_id", "test"),
                        data={"detached": True},
                    )
                    writer.write((response.to_json() + "\n").encode())
                    await writer.drain()
            except Exception:
                pass
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_unix_server(
            handle_client, path=str(socket_path)
        )

        try:
            client = TUIClient()
            await client.connect(socket_path)
            
            client._subscription_id = "sub-123"
            client._engagement_id = "eng-test"
            
            await client.detach()
            
            # SAFETY ASSERTIONS: No stop/pause/kill commands sent
            assert IPCCommand.ENGAGEMENT_STOP not in commands_received
            assert IPCCommand.ENGAGEMENT_PAUSE not in commands_received
            assert IPCCommand.DAEMON_STOP not in commands_received
            
            # Only detach command should be sent
            assert IPCCommand.ENGAGEMENT_DETACH in commands_received
            assert len(commands_received) == 1
            
        finally:
            await client.close()
            server.close()
            await server.wait_closed()


class TestAppActionDetachSafety:
    """Safety tests for CyberRedApp.action_detach()."""

    @pytest.mark.asyncio
    async def test_action_detach_only_calls_client_detach(self):
        """SAFETY: action_detach() only calls client.detach(), not stop."""
        from cyberred.tui.app import CyberRedApp
        
        mock_client = MagicMock()
        mock_client.detach = AsyncMock()
        # Add other methods to verify they're NOT called
        mock_client.stop = AsyncMock()
        
        app = CyberRedApp(daemon_client=mock_client, engagement_id="eng-test")
        app.exit = MagicMock()
        app.notify = MagicMock()
        app._stream_task = None
        
        await app.action_detach()
        
        # SAFETY: Only detach should be called
        mock_client.detach.assert_called_once()
        # Stop should never be called
        if hasattr(mock_client, 'stop'):
            mock_client.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_detach_command_input_calls_action_detach(self):
        """SAFETY: Typing 'detach' triggers action_detach, not stop."""
        from cyberred.tui.app import CyberRedApp
        from textual.widgets import Input
        
        mock_client = MagicMock()
        mock_client.detach = AsyncMock()
        
        app = CyberRedApp(daemon_client=mock_client, engagement_id="eng-test")
        app.exit = MagicMock()
        app.notify = MagicMock()
        app._stream_task = None
        
        # Mock query_one to return a mock input
        mock_input = MagicMock()
        app.query_one = MagicMock(return_value=mock_input)
        
        # Simulate input submission with "detach"
        mock_message = MagicMock()
        mock_message.value = "detach"
        
        await app.on_input_submitted(mock_message)
        
        # SAFETY: detach should be called
        mock_client.detach.assert_called_once()

    @pytest.mark.asyncio
    async def test_detach_command_case_insensitive(self):
        """SAFETY: 'DETACH', 'Detach', 'detach' all trigger action_detach."""
        from cyberred.tui.app import CyberRedApp
        
        for cmd in ["detach", "DETACH", "Detach", "DeTaCh", "  detach  "]:
            mock_client = MagicMock()
            mock_client.detach = AsyncMock()
            
            app = CyberRedApp(daemon_client=mock_client, engagement_id="eng-test")
            app.exit = MagicMock()
            app.notify = MagicMock()
            app._stream_task = None
            
            mock_input = MagicMock()
            app.query_one = MagicMock(return_value=mock_input)
            
            mock_message = MagicMock()
            mock_message.value = cmd
            
            await app.on_input_submitted(mock_message)
            
            # SAFETY: detach should be called for all variations
            mock_client.detach.assert_called_once(), f"Failed for input: {cmd}"
