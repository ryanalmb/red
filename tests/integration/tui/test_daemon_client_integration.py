"""Integration tests for TUI daemon client socket communication (Story 9.7).

Tests cover:
- Full connect → attach → receive events → detach cycle
- Connection failure handling with real socket errors
- Initial state sync data structure correctness
- Real-time event streaming over Unix socket
- Stale state detection integration

AC #8: Integration tests verify socket communication.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from cyberred.daemon.ipc import IPCResponse
from cyberred.daemon.streaming import StreamEvent, StreamEventType, encode_stream_event
from cyberred.tui.daemon_client import (
    DaemonConnectionError,
    DaemonNotRunningError,
    EngagementError,
    TUIClient,
)


class TestDaemonClientIntegrationConnect:
    """Integration tests for socket connection."""

    @pytest.mark.asyncio
    async def test_full_connect_attach_detach_cycle(self, tmp_path: Path):
        """Test complete lifecycle: connect → attach → receive events → detach."""
        socket_path = tmp_path / "daemon.sock"
        
        events_to_send = [
            StreamEvent(
                event_type=StreamEventType.HEARTBEAT,
                data={"timestamp": "2026-01-28T19:00:00Z"},
            ),
            StreamEvent(
                event_type=StreamEventType.FINDING,
                data={"finding_id": "f-123", "severity": "HIGH"},
            ),
        ]
        
        async def handle_client(reader, writer):
            try:
                # Read attach request
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={
                        "subscription_id": "sub-abc",
                        "state": "RUNNING",
                        "agent_count": 3,
                        "finding_count": 1,
                    },
                )
                writer.write((response.to_json() + "\n").encode())
                await writer.drain()
                
                # Stream events
                for event in events_to_send:
                    writer.write(encode_stream_event(event))
                    await writer.drain()
                    await asyncio.sleep(0.01)
                
                # Read detach request
                await reader.readline()
                detach_response = IPCResponse(
                    status="ok",
                    request_id="detach",
                    data={"detached": True},
                )
                writer.write((detach_response.to_json() + "\n").encode())
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
        
        server = await asyncio.start_unix_server(handle_client, path=str(socket_path))
        
        try:
            client = TUIClient()
            
            # Connect
            await client.connect(socket_path)
            assert client.connected is True
            
            # Attach and receive events
            received = []
            async for event in client.attach("eng-123"):
                received.append(event)
            
            # Verify events received
            assert len(received) == 3  # Initial state + 2 stream events
            assert received[0].event_type == StreamEventType.STATE_CHANGE
            assert received[1].event_type == StreamEventType.HEARTBEAT
            assert received[2].event_type == StreamEventType.FINDING
            
            # Detach
            await client.detach()
            assert client.attached is False
            
            # Close
            await client.close()
            assert client.connected is False
        finally:
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_connection_failure_socket_not_exists(self, tmp_path: Path):
        """Test connection failure when socket doesn't exist."""
        socket_path = tmp_path / "nonexistent.sock"
        
        client = TUIClient()
        
        with pytest.raises(DaemonNotRunningError) as exc_info:
            await client.connect(socket_path)
        
        assert "not found" in str(exc_info.value)
        assert client.connected is False

    @pytest.mark.asyncio
    async def test_connection_failure_connection_refused(self, tmp_path: Path):
        """Test connection failure when connection is refused."""
        socket_path = tmp_path / "refused.sock"
        socket_path.touch()  # File exists but no server
        
        client = TUIClient()
        
        with pytest.raises(DaemonConnectionError) as exc_info:
            await client.connect(socket_path)
        
        assert "Failed to connect" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_initial_state_sync_data_structure(self, tmp_path: Path):
        """Test initial state sync contains expected data structure."""
        socket_path = tmp_path / "daemon.sock"
        
        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={
                        "subscription_id": "sub-abc",
                        "state": "RUNNING",
                        "agent_count": 5,
                        "finding_count": 10,
                        "agents": [
                            {"id": "agent-1", "status": "active"},
                            {"id": "agent-2", "status": "idle"},
                        ],
                        "findings": [
                            {"id": "f-1", "severity": "HIGH"},
                        ],
                    },
                )
                writer.write((response.to_json() + "\n").encode())
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
        
        server = await asyncio.start_unix_server(handle_client, path=str(socket_path))
        
        try:
            client = TUIClient()
            await client.connect(socket_path)
            
            initial_event = None
            async for event in client.attach("eng-123"):
                initial_event = event
                break
            
            # Verify initial state structure
            assert initial_event is not None
            assert initial_event.event_type == StreamEventType.STATE_CHANGE
            assert initial_event.data["state"] == "RUNNING"
            assert initial_event.data["agent_count"] == 5
            assert initial_event.data["finding_count"] == 10
            assert len(initial_event.data["agents"]) == 2
            assert len(initial_event.data["findings"]) == 1
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_realtime_event_streaming(self, tmp_path: Path):
        """Test real-time event streaming over Unix socket."""
        socket_path = tmp_path / "daemon.sock"
        event_timestamps = []
        
        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={"subscription_id": "sub-abc"},
                )
                writer.write((response.to_json() + "\n").encode())
                await writer.drain()
                
                # Stream events with small delays
                for i in range(3):
                    event = StreamEvent(
                        event_type=StreamEventType.AGENT_STATUS,
                        data={"agent_id": f"agent-{i}", "status": "active"},
                    )
                    writer.write(encode_stream_event(event))
                    await writer.drain()
                    await asyncio.sleep(0.02)
            finally:
                writer.close()
                await writer.wait_closed()
        
        server = await asyncio.start_unix_server(handle_client, path=str(socket_path))
        
        try:
            import time
            client = TUIClient()
            await client.connect(socket_path)
            
            received = []
            async for event in client.attach("eng-123"):
                received.append((time.monotonic(), event))
            
            # Verify events received in order
            assert len(received) == 3
            for i, (ts, event) in enumerate(received):
                assert event.event_type == StreamEventType.AGENT_STATUS
                assert event.data["agent_id"] == f"agent-{i}"
        finally:
            await client.close()
            server.close()
            await server.wait_closed()


class TestDaemonClientIntegrationStale:
    """Integration tests for stale state detection."""

    @pytest.mark.asyncio
    async def test_activity_time_updated_on_events(self, tmp_path: Path):
        """Test _last_activity_time is updated when events are received."""
        import time
        socket_path = tmp_path / "daemon.sock"
        
        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={"subscription_id": "sub-abc"},
                )
                writer.write((response.to_json() + "\n").encode())
                await writer.drain()
                
                # Send event
                event = StreamEvent(
                    event_type=StreamEventType.HEARTBEAT,
                    data={},
                )
                writer.write(encode_stream_event(event))
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
        
        server = await asyncio.start_unix_server(handle_client, path=str(socket_path))
        
        try:
            client = TUIClient()
            await client.connect(socket_path)
            
            # Initially no activity
            assert client._last_activity_time == 0.0
            
            before = time.monotonic()
            async for event in client.attach("eng-123"):
                pass
            after = time.monotonic()
            
            # Activity time should be updated
            assert client._last_activity_time >= before
            assert client._last_activity_time <= after
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    def test_is_stale_integration(self):
        """Test is_stale property integration with TUIClient."""
        import time
        
        client = TUIClient()
        
        # Initially not stale (no events ever)
        assert client.is_stale is False
        
        # Set activity time to 30s ago - not stale
        client._last_activity_time = time.monotonic() - 30.0
        assert client.is_stale is False
        
        # Set activity time to 61s ago - stale
        client._last_activity_time = time.monotonic() - 61.0
        assert client.is_stale is True

    def test_seconds_since_activity_integration(self):
        """Test seconds_since_activity property integration."""
        import time
        
        client = TUIClient()
        
        # Initially 0
        assert client.seconds_since_activity == 0.0
        
        # Set activity time
        client._last_activity_time = time.monotonic() - 45.0
        seconds = client.seconds_since_activity
        assert 44.5 <= seconds <= 46.0

    def test_last_activity_time_integration(self):
        """Test last_activity_time property returns datetime."""
        import time
        from datetime import datetime, timezone
        
        client = TUIClient()
        
        # Initially None
        assert client.last_activity_time is None
        
        # Set activity time
        client._last_activity_time = time.monotonic() - 10.0
        result = client.last_activity_time
        
        assert result is not None
        assert isinstance(result, datetime)
        
        # Should be approximately 10 seconds ago
        now = datetime.now(timezone.utc)
        diff = (now - result).total_seconds()
        assert 9.0 <= diff <= 11.0
