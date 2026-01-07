"""Unit tests for TUIClient daemon connection.

Tests cover:
- Connection to daemon via Unix socket
- ENGAGEMENT_ATTACH command and response handling
- Streaming events from daemon
- ENGAGEMENT_DETACH command
- Error handling for connection failures
- Attach latency measurement
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.daemon.ipc import IPCResponse
from cyberred.daemon.streaming import StreamEvent, StreamEventType, encode_stream_event
from cyberred.tui.daemon_client import (
    DaemonConnectionError,
    DaemonNotRunningError,
    EngagementError,
    TUIClient,
)


class TestTUIClientInit:
    """Tests for TUIClient initialization."""

    def test_initial_state(self):
        """Client starts disconnected and unattached."""
        client = TUIClient()
        assert client.connected is False
        assert client.attached is False
        assert client.engagement_id is None
        assert client.subscription_id is None
        assert client.attach_latency_ms is None


class TestTUIClientConnect:
    """Tests for TUIClient.connect()."""

    @pytest.mark.asyncio
    async def test_connect_socket_not_found(self, tmp_path: Path):
        """Connect raises DaemonNotRunningError if socket doesn't exist."""
        client = TUIClient()
        socket_path = tmp_path / "nonexistent.sock"

        with pytest.raises(DaemonNotRunningError) as exc_info:
            await client.connect(socket_path)

        assert "not found" in str(exc_info.value)
        assert client.connected is False

    @pytest.mark.asyncio
    async def test_connect_connection_refused(self, tmp_path: Path):
        """Connect raises DaemonConnectionError when connection refused."""
        socket_path = tmp_path / "test.sock"
        socket_path.touch()  # Create file but no server

        client = TUIClient()

        with pytest.raises(DaemonConnectionError) as exc_info:
            await client.connect(socket_path)

        assert "Failed to connect" in str(exc_info.value)
        assert client.connected is False

    @pytest.mark.asyncio
    async def test_connect_success(self, tmp_path: Path):
        """Connect succeeds when daemon is running."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            # Keep connection open briefly then close
            try:
                await asyncio.sleep(0.1)
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_unix_server(
            handle_client, path=str(socket_path)
        )

        try:
            client = TUIClient()
            await client.connect(socket_path)

            assert client.connected is True
            assert client.attached is False

            await client.close()
            assert client.connected is False
        finally:
            server.close()
            await server.wait_closed()


class TestTUIClientAttach:
    """Tests for TUIClient.attach()."""

    @pytest.mark.asyncio
    async def test_attach_not_connected(self):
        """Attach raises error when not connected."""
        client = TUIClient()

        with pytest.raises(DaemonConnectionError) as exc_info:
            async for _ in client.attach("test-id"):
                pass

        assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_attach_engagement_not_found(self, tmp_path: Path):
        """Attach raises EngagementError when engagement not found."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="error",
                    request_id="test",
                    error="Engagement not found",
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

            with pytest.raises(EngagementError) as exc_info:
                async for _ in client.attach("nonexistent"):
                    pass

            assert "not found" in str(exc_info.value)
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_attach_success_with_initial_state(self, tmp_path: Path):
        """Attach yields initial state snapshot."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={
                        "subscription_id": "sub-abc123",
                        "state": "RUNNING",
                        "agent_count": 5,
                        "finding_count": 3,
                        "agents": [{"id": "agent-1", "status": "active"}],
                        "findings": [{"id": "finding-1", "severity": "HIGH"}],
                    },
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

            events = []
            async for event in client.attach("eng-123"):
                events.append(event)
                break  # Only get the first event (initial state)

            assert len(events) == 1
            assert events[0].event_type == StreamEventType.STATE_CHANGE
            assert events[0].data["state"] == "RUNNING"
            assert events[0].data["agent_count"] == 5
            assert client.attached is True
            assert client.engagement_id == "eng-123"
            assert client.subscription_id == "sub-abc123"
            assert client.attach_latency_ms is not None
            assert client.attach_latency_ms > 0
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_attach_receives_stream_events(self, tmp_path: Path):
        """Attach yields streaming events after initial state."""
        socket_path = tmp_path / "daemon.sock"
        events_to_send = [
            StreamEvent(
                event_type=StreamEventType.AGENT_STATUS,
                data={"agent_id": "agent-1", "status": "busy"},
            ),
            StreamEvent(
                event_type=StreamEventType.FINDING,
                data={"finding_id": "f-1", "severity": "HIGH"},
            ),
        ]

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={"subscription_id": "sub-abc123", "state": "RUNNING"},
                )
                writer.write((response.to_json() + "\n").encode())
                await writer.drain()

                for event in events_to_send:
                    writer.write(encode_stream_event(event))
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

            received = []
            async for event in client.attach("eng-123"):
                received.append(event)

            # Should receive: initial state + 2 stream events
            assert len(received) == 3
            assert received[0].event_type == StreamEventType.STATE_CHANGE
            assert received[1].event_type == StreamEventType.AGENT_STATUS
            assert received[2].event_type == StreamEventType.FINDING
        finally:
            await client.close()
            server.close()
            await server.wait_closed()


class TestTUIClientDetach:
    """Tests for TUIClient.detach()."""

    @pytest.mark.asyncio
    async def test_detach_not_attached(self):
        """Detach is a no-op when not attached."""
        client = TUIClient()
        await client.detach()
        assert client.attached is False

    @pytest.mark.asyncio
    async def test_detach_not_connected(self):
        """Detach cleans up when not connected."""
        client = TUIClient()
        client._subscription_id = "sub-123"
        client._engagement_id = "eng-123"

        await client.detach()

        assert client.subscription_id is None
        assert client.engagement_id is None

    @pytest.mark.asyncio
    async def test_detach_success(self, tmp_path: Path):
        """Detach sends command and cleans up."""
        socket_path = tmp_path / "daemon.sock"
        detach_received = asyncio.Event()

        async def handle_client(reader, writer):
            try:
                data = await reader.readline()
                detach_received.set()
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

            client._subscription_id = "sub-abc"
            client._engagement_id = "eng-123"

            await client.detach()

            await asyncio.wait_for(detach_received.wait(), timeout=2.0)
            assert client.attached is False
            assert client.subscription_id is None
        finally:
            await client.close()
            server.close()
            await server.wait_closed()


class TestTUIClientClose:
    """Tests for TUIClient.close()."""

    @pytest.mark.asyncio
    async def test_close_when_not_connected(self):
        """Close is safe when not connected."""
        client = TUIClient()
        await client.close()
        assert client.connected is False

    @pytest.mark.asyncio
    async def test_close_detaches_first(self, tmp_path: Path):
        """Close detaches from engagement before closing."""
        socket_path = tmp_path / "daemon.sock"
        detach_received = asyncio.Event()

        async def handle_client(reader, writer):
            try:
                data = await reader.readline()
                if b"detach" in data:
                    detach_received.set()
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
            client._subscription_id = "sub-abc"
            client._engagement_id = "eng-123"

            await client.close()

            await asyncio.wait_for(detach_received.wait(), timeout=2.0)
            assert client.connected is False
            assert client.attached is False
        finally:
            server.close()
            await server.wait_closed()


class TestTUIClientContextManager:
    """Tests for async context manager support."""

    @pytest.mark.asyncio
    async def test_context_manager(self, tmp_path: Path):
        """Client can be used as async context manager."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await asyncio.sleep(0.1)
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_unix_server(
            handle_client, path=str(socket_path)
        )

        try:
            async with TUIClient() as client:
                await client.connect(socket_path)
                assert client.connected is True

            assert client.connected is False
        finally:
            server.close()
            await server.wait_closed()


class TestTUIClientLatency:
    """Tests for attach latency measurement (NFR32)."""

    @pytest.mark.asyncio
    async def test_attach_latency_measured(self, tmp_path: Path):
        """Attach latency is measured and recorded."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                await asyncio.sleep(0.05)
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={"subscription_id": "sub-abc", "state": "RUNNING"},
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

            async for _ in client.attach("eng-123"):
                break

            assert client.attach_latency_ms is not None
            assert client.attach_latency_ms >= 50.0
        finally:
            await client.close()
            server.close()
            await server.wait_closed()


class TestTUIClientEdgeCases:
    """Tests for edge cases to achieve 100% coverage."""

    @pytest.mark.asyncio
    async def test_send_request_daemon_closes_connection(self, tmp_path: Path):
        """Test line 165: Daemon closes connection (empty data)."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            # Read request but don't send response, just close
            try:
                await reader.readline()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_unix_server(
            handle_client, path=str(socket_path)
        )

        try:
            client = TUIClient()
            await client.connect(socket_path)

            with pytest.raises(DaemonConnectionError) as exc_info:
                async for _ in client.attach("test-id"):
                    pass

            assert "closed connection" in str(exc_info.value)
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_send_request_unexpected_response_type(self, tmp_path: Path):
        """Test line 169: Unexpected response type (not IPCResponse)."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                # Send an IPCRequest instead of IPCResponse (wrong type)
                from cyberred.daemon.ipc import IPCRequest
                malformed = IPCRequest(
                    command="sessions.list",
                    params={},
                    request_id="test",
                )
                writer.write((malformed.to_json() + "\n").encode())
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

            with pytest.raises(DaemonConnectionError) as exc_info:
                async for _ in client.attach("test-id"):
                    pass

            assert "Unexpected response type" in str(exc_info.value)
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_attach_stream_timeout(self, tmp_path: Path):
        """Test lines 248-251: Stream timeout breaks the loop."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={"subscription_id": "sub-abc", "state": "RUNNING"},
                )
                writer.write((response.to_json() + "\n").encode())
                await writer.drain()
                # Don't send any more events, just wait (simulates timeout)
                await asyncio.sleep(10)
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_unix_server(
            handle_client, path=str(socket_path)
        )

        try:
            client = TUIClient()
            await client.connect(socket_path)

            # Temporarily reduce timeout for fast test
            events = []
            with patch.object(asyncio, 'wait_for', side_effect=asyncio.TimeoutError()):
                async for event in client.attach("eng-123"):
                    events.append(event)

            # Should receive only initial state before timeout
            assert len(events) == 1
            assert events[0].event_type == StreamEventType.STATE_CHANGE
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_attach_stream_decode_error(self, tmp_path: Path):
        """Test lines 252-254: Generic exception in stream loop."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={"subscription_id": "sub-abc", "state": "RUNNING"},
                )
                writer.write((response.to_json() + "\n").encode())
                await writer.drain()
                # Send invalid data that will fail decode
                writer.write(b"not valid json\n")
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

            events = []
            async for event in client.attach("eng-123"):
                events.append(event)

            # Should get initial state but error on bad data causes break
            assert len(events) == 1
            assert events[0].event_type == StreamEventType.STATE_CHANGE
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_detach_error_response(self, tmp_path: Path):
        """Test line 288: Detach returns error status."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="error",
                    request_id="test",
                    error="Subscription not found",
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
            client._subscription_id = "sub-invalid"
            client._engagement_id = "eng-123"

            # Should not raise, just logs warning and cleans up
            await client.detach()

            assert client.attached is False
            assert client.subscription_id is None
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_attach_no_initial_state_in_response(self, tmp_path: Path):
        """Test branch 218->232: No 'state' in attach response data."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                # Response without 'state' key - skips initial state yield
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={"subscription_id": "sub-abc"},  # No 'state' key
                )
                writer.write((response.to_json() + "\n").encode())
                await writer.drain()
                # Send one stream event
                event = StreamEvent(
                    event_type=StreamEventType.HEARTBEAT,
                    data={},
                )
                writer.write(encode_stream_event(event))
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

            events = []
            async for event in client.attach("eng-123"):
                events.append(event)

            # Should NOT receive initial state, only the heartbeat
            assert len(events) == 1
            assert events[0].event_type == StreamEventType.HEARTBEAT
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_attach_streaming_false_before_loop(self, tmp_path: Path):
        """Test branch 233->257: _streaming set to False skips while loop."""
        socket_path = tmp_path / "daemon.sock"
        event_sent = asyncio.Event()

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={"subscription_id": "sub-abc"},  # No 'state' key
                )
                writer.write((response.to_json() + "\n").encode())
                await writer.drain()
                event_sent.set()
                # Keep connection open
                await asyncio.sleep(1.0)
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_unix_server(
            handle_client, path=str(socket_path)
        )

        try:
            client = TUIClient()
            await client.connect(socket_path)

            # Start iterating, but immediately stop streaming
            events = []
            async for event in client.attach("eng-123"):
                events.append(event)
                # Set streaming to false to exit while loop
                client._streaming = False

            # Wait for server to have sent response
            await asyncio.wait_for(event_sent.wait(), timeout=2.0)

            # No initial state (no 'state' key), and loop exits immediately
            assert len(events) == 0
        finally:
            await client.close()
            server.close()
            await server.wait_closed()
