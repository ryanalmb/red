"""Integration tests for TUI detach flow (Story 9.9).

Tests cover Task 9:
- 9.2: Test attach → detach → reattach cycle
- 9.3: Test detach via Ctrl+D simulation
- 9.4: Test detach via command input
- 9.5: Test connection loss handling and auto-detach
- 9.6: Test multiple TUI clients can attach/detach independently

Per AC #1-#5: Full integration of detach functionality.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from cyberred.daemon.ipc import IPCCommand, IPCResponse
from cyberred.daemon.streaming import StreamEvent, StreamEventType, encode_stream_event
from cyberred.tui.daemon_client import TUIClient


class TestAttachDetachReattachCycle:
    """Integration tests for attach → detach → reattach cycle (Task 9.2)."""

    @pytest.mark.asyncio
    async def test_full_attach_detach_reattach_cycle(self, tmp_path: Path):
        """Test complete attach → detach → reattach cycle preserves engagement."""
        socket_path = tmp_path / "daemon.sock"
        attach_count = {"count": 0}
        finding_count = {"count": 0}

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
                        # Simulate findings accumulated while potentially detached
                        finding_count["count"] += 5
                        response = IPCResponse(
                            status="ok",
                            request_id=request.get("request_id", "test"),
                            data={
                                "subscription_id": f"sub-{attach_count['count']}",
                                "state": "RUNNING",
                                "agent_count": 10,
                                "finding_count": finding_count["count"],
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
            # Phase 1: Initial attach
            client = TUIClient()
            await client.connect(socket_path)
            
            initial_findings = 0
            async for event in client.attach("eng-cycle-test"):
                assert event.data["state"] == "RUNNING"
                initial_findings = event.data["finding_count"]
                break
            
            assert client.attached is True
            assert client.subscription_id is not None
            
            # Phase 2: Detach
            await client.detach()
            assert client.attached is False
            assert client.subscription_id is None
            
            await client.close()
            
            # Phase 3: Reattach (simulating new session)
            client2 = TUIClient()
            await client2.connect(socket_path)
            
            async for event in client2.attach("eng-cycle-test"):
                # Engagement should still be RUNNING
                assert event.data["state"] == "RUNNING"
                # More findings accumulated (simulating work continued during detach)
                assert event.data["finding_count"] > initial_findings
                break
            
            assert client2.attached is True
            
            # Clean up
            await client2.detach()
            await client2.close()
            
            # Verify attach count
            assert attach_count["count"] == 2
            
        finally:
            server.close()
            await server.wait_closed()


class TestDetachViaCtrlD:
    """Integration tests for Ctrl+D detach simulation (Task 9.3)."""

    @pytest.mark.asyncio
    async def test_ctrl_d_triggers_clean_detach(self, tmp_path: Path):
        """Test Ctrl+D keybinding triggers clean detach via action_detach."""
        from cyberred.tui.app import CyberRedApp
        
        socket_path = tmp_path / "daemon.sock"
        detach_received = asyncio.Event()

        async def handle_client(reader, writer):
            try:
                while True:
                    data = await reader.readline()
                    if not data:
                        break
                    request = json.loads(data.decode())
                    command = request.get("command")
                    
                    if command == IPCCommand.ENGAGEMENT_DETACH:
                        detach_received.set()
                    
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
            # Set up real TUIClient
            client = TUIClient()
            await client.connect(socket_path)
            client._subscription_id = "sub-123"
            client._engagement_id = "eng-ctrl-d-test"
            
            # Create app with real client
            app = CyberRedApp(daemon_client=client, engagement_id="eng-ctrl-d-test")
            app.exit = MagicMock()
            app.notify = MagicMock()
            app._stream_task = None
            
            # Simulate Ctrl+D by calling action_detach directly
            # (In real app, Ctrl+D binding calls this)
            await app.action_detach()
            
            # Verify detach was received by daemon
            await asyncio.wait_for(detach_received.wait(), timeout=2.0)
            
            # Verify app exited
            app.exit.assert_called_once()
            
        finally:
            try:
                await client.close()
            except Exception:
                pass
            server.close()
            await server.wait_closed()


class TestDetachViaCommandInput:
    """Integration tests for 'detach' command input (Task 9.4)."""

    @pytest.mark.asyncio
    async def test_detach_command_triggers_clean_detach(self, tmp_path: Path):
        """Test typing 'detach' command triggers clean detach."""
        from cyberred.tui.app import CyberRedApp
        
        socket_path = tmp_path / "daemon.sock"
        detach_received = asyncio.Event()

        async def handle_client(reader, writer):
            try:
                while True:
                    data = await reader.readline()
                    if not data:
                        break
                    request = json.loads(data.decode())
                    command = request.get("command")
                    
                    if command == IPCCommand.ENGAGEMENT_DETACH:
                        detach_received.set()
                    
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
            # Set up real TUIClient
            client = TUIClient()
            await client.connect(socket_path)
            client._subscription_id = "sub-123"
            client._engagement_id = "eng-cmd-test"
            
            # Create app with real client
            app = CyberRedApp(daemon_client=client, engagement_id="eng-cmd-test")
            app.exit = MagicMock()
            app.notify = MagicMock()
            app._stream_task = None
            
            # Mock query_one for input widget
            mock_input = MagicMock()
            app.query_one = MagicMock(return_value=mock_input)
            
            # Simulate typing 'detach' command
            mock_message = MagicMock()
            mock_message.value = "detach"
            
            await app.on_input_submitted(mock_message)
            
            # Verify detach was received by daemon
            await asyncio.wait_for(detach_received.wait(), timeout=2.0)
            
            # Verify app exited
            app.exit.assert_called_once()
            
        finally:
            try:
                await client.close()
            except Exception:
                pass
            server.close()
            await server.wait_closed()


class TestConnectionLossHandling:
    """Integration tests for connection loss auto-detach (Task 9.5)."""

    @pytest.mark.asyncio
    async def test_connection_loss_triggers_auto_cleanup(self, tmp_path: Path):
        """Test sudden connection loss triggers automatic cleanup."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                # Read attach request
                data = await reader.readline()
                if data:
                    response = IPCResponse(
                        status="ok",
                        request_id="test",
                        data={"subscription_id": "sub-123", "state": "RUNNING"},
                    )
                    writer.write((response.to_json() + "\n").encode())
                    await writer.drain()
                
                # Abruptly close connection (simulates SSH disconnect)
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

        server = await asyncio.start_unix_server(
            handle_client, path=str(socket_path)
        )

        try:
            client = TUIClient()
            await client.connect(socket_path)
            
            # Start attach - will receive initial state then connection closes
            events = []
            async for event in client.attach("eng-loss-test"):
                events.append(event)
                # Connection will close after initial state
            
            # Verify we got initial state
            assert len(events) >= 1
            assert events[0].data["state"] == "RUNNING"
            
            # After connection loss, streaming should be stopped
            assert client._streaming is False
            
        finally:
            try:
                await client.close()
            except Exception:
                pass
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_detach_after_connection_loss_is_safe(self, tmp_path: Path):
        """Test calling detach after connection loss doesn't raise."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                # Immediately close connection
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

        server = await asyncio.start_unix_server(
            handle_client, path=str(socket_path)
        )

        try:
            client = TUIClient()
            await client.connect(socket_path)
            
            # Simulate having been attached
            client._subscription_id = "sub-123"
            client._engagement_id = "eng-test"
            
            # Wait for connection to be closed by server
            await asyncio.sleep(0.1)
            
            # Detach should be safe even after connection loss
            await client.detach()
            
            # State should be cleaned up
            assert client.subscription_id is None
            assert client.engagement_id is None
            
        finally:
            try:
                await client.close()
            except Exception:
                pass
            server.close()
            await server.wait_closed()


class TestMultipleClientsAttachDetach:
    """Integration tests for multiple TUI clients (Task 9.6)."""

    @pytest.mark.asyncio
    async def test_multiple_clients_independent_attach_detach(self, tmp_path: Path):
        """Test multiple TUI clients can attach/detach independently."""
        socket_path = tmp_path / "daemon.sock"
        sub_counter = {"count": 0}

        async def handle_client(reader, writer):
            try:
                while True:
                    data = await reader.readline()
                    if not data:
                        break
                    request = json.loads(data.decode())
                    command = request.get("command")
                    
                    if command == IPCCommand.ENGAGEMENT_ATTACH:
                        sub_counter["count"] += 1
                        response = IPCResponse(
                            status="ok",
                            request_id=request.get("request_id", "test"),
                            data={
                                "subscription_id": f"sub-{sub_counter['count']}",
                                "state": "RUNNING",
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
            # Client 1 attaches
            client1 = TUIClient()
            await client1.connect(socket_path)
            
            async for event in client1.attach("eng-multi-test"):
                assert event.data["state"] == "RUNNING"
                break
            
            sub1 = client1.subscription_id
            assert sub1 is not None
            
            # Client 1 detaches
            await client1.detach()
            assert client1.attached is False
            await client1.close()
            
            # Client 2 attaches (same engagement, simulating new session)
            client2 = TUIClient()
            await client2.connect(socket_path)
            
            async for event in client2.attach("eng-multi-test"):
                assert event.data["state"] == "RUNNING"
                break
            
            sub2 = client2.subscription_id
            assert sub2 is not None
            assert sub1 != sub2  # Different subscriptions
            
            # Client 2 detaches
            await client2.detach()
            assert client2.attached is False
            await client2.close()
            
            # Verify we had 2 separate attach operations
            assert sub_counter["count"] == 2
            
        finally:
            server.close()
            await server.wait_closed()


class TestDetachMessageDisplay:
    """Integration tests for detach message display (AC #3)."""

    @pytest.mark.asyncio
    async def test_detach_shows_engagement_id_message(self, tmp_path: Path):
        """Test 'Detached from {engagement_id}' message is shown."""
        from cyberred.tui.app import CyberRedApp
        
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                while True:
                    data = await reader.readline()
                    if not data:
                        break
                    request = json.loads(data.decode())
                    
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
            client._engagement_id = "eng-msg-test"
            
            # Track notify calls
            notify_calls = []
            
            app = CyberRedApp(daemon_client=client, engagement_id="eng-msg-test")
            app.exit = MagicMock()
            app.notify = lambda msg, **kwargs: notify_calls.append(msg)
            app._stream_task = None
            
            await app.action_detach()
            
            # Verify detach message was shown with engagement ID (AC #3)
            assert len(notify_calls) >= 1
            # AC #3: "Detached from {engagement_id}" message is shown
            assert "Detached from eng-msg-test" in notify_calls[0], \
                f"Expected 'Detached from eng-msg-test', got: {notify_calls}"
            
        finally:
            try:
                await client.close()
            except Exception:
                pass
            server.close()
            await server.wait_closed()
