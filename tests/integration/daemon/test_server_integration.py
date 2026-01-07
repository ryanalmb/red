"""Integration tests for DaemonServer Unix socket communication.

Tests full request/response cycle and concurrent clients.
"""

import asyncio
from pathlib import Path

import pytest

from unittest.mock import patch, MagicMock, AsyncMock
from cyberred.daemon.ipc import (
    IPCCommand,
    IPCRequest,
    IPCResponse,
    encode_message,
    decode_message,
)
from cyberred.daemon.server import DaemonServer


@pytest.fixture(autouse=True)
def mock_preflight():
    """Mock pre-flight checks globally for all integration tests."""
    with patch("cyberred.daemon.session_manager.PreFlightRunner") as MockRunner:
        runner = MagicMock()
        runner.run_all = AsyncMock(return_value=[])
        runner.validate_results = MagicMock()
        MockRunner.return_value = runner
        yield runner


@pytest.fixture
def temp_socket_path(tmp_path: Path) -> Path:
    """Create a temporary socket path for testing."""
    return tmp_path / "test.sock"


@pytest.fixture
def temp_pid_path(tmp_path: Path) -> Path:
    """Create a temporary PID file path for testing."""
    return tmp_path / "test.pid"


@pytest.fixture
async def running_server(
    temp_socket_path: Path, temp_pid_path: Path
) -> DaemonServer:
    """Create and start a server, yielding it for tests."""
    server = DaemonServer(
        socket_path=temp_socket_path,
        pid_path=temp_pid_path,
    )
    await server.start()
    yield server
    await server.stop()


class TestFullRequestResponseCycle:
    """Tests for complete IPC request/response cycles."""

    @pytest.mark.asyncio
    async def test_full_cycle_sessions_list(
        self, running_server: DaemonServer, temp_socket_path: Path
    ) -> None:
        """Full cycle: connect, send request, receive response, disconnect."""
        # Connect
        reader, writer = await asyncio.open_unix_connection(
            str(temp_socket_path)
        )

        # Send request
        request = IPCRequest(
            command=IPCCommand.SESSIONS_LIST,
            params={},
            request_id="int-test-1",
        )
        writer.write(encode_message(request))
        await writer.drain()

        # Receive response
        data = await reader.readline()
        response = decode_message(data)

        # Validate
        assert isinstance(response, IPCResponse)
        assert response.status == "ok"
        assert response.request_id == "int-test-1"
        assert response.data == {"engagements": []}

        # Clean disconnect
        writer.close()
        await writer.wait_closed()

    @pytest.mark.asyncio
    async def test_multiple_requests_single_connection(
        self, running_server: DaemonServer, temp_socket_path: Path, tmp_path: Path
    ) -> None:
        """Multiple requests on same connection should work."""
        # Create config file for engagement
        config_path = tmp_path / "test-eng.yaml"
        config_path.write_text("name: testeng\n")

        reader, writer = await asyncio.open_unix_connection(
            str(temp_socket_path)
        )

        # Request 1: List (empty)
        request = IPCRequest(
            command=IPCCommand.SESSIONS_LIST,
            params={},
            request_id="multi-0",
        )
        writer.write(encode_message(request))
        await writer.drain()
        data = await reader.readline()
        response = decode_message(data)
        assert response.status == "ok"
        assert response.request_id == "multi-0"

        # Request 2: Create engagement
        request = IPCRequest(
            command=IPCCommand.ENGAGEMENT_START,
            params={"config_path": str(config_path)},
            request_id="multi-1",
        )
        writer.write(encode_message(request))
        await writer.drain()
        data = await reader.readline()
        response = decode_message(data)
        assert response.status == "ok"
        engagement_id = response.data.get("id")

        # Request 3: List (now has one)
        request = IPCRequest(
            command=IPCCommand.SESSIONS_LIST,
            params={},
            request_id="multi-2",
        )
        writer.write(encode_message(request))
        await writer.drain()
        data = await reader.readline()
        response = decode_message(data)
        assert response.status == "ok"
        assert len(response.data.get("engagements", [])) == 1

        # Request 4: Pause the engagement
        request = IPCRequest(
            command=IPCCommand.ENGAGEMENT_PAUSE,
            params={"engagement_id": engagement_id},
            request_id="multi-3",
        )
        writer.write(encode_message(request))
        await writer.drain()
        data = await reader.readline()
        response = decode_message(data)
        assert response.status == "ok"
        assert response.data.get("state") == "PAUSED"

        writer.close()
        await writer.wait_closed()


class TestConcurrentClients:
    """Tests for multiple concurrent client connections."""

    @pytest.mark.asyncio
    async def test_concurrent_clients_all_receive_responses(
        self, running_server: DaemonServer, temp_socket_path: Path
    ) -> None:
        """Multiple clients connecting simultaneously should all work."""
        num_clients = 5

        async def client_task(client_id: int) -> bool:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            request = IPCRequest(
                command=IPCCommand.SESSIONS_LIST,
                params={},
                request_id=f"concurrent-{client_id}",
            )
            writer.write(encode_message(request))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            writer.close()
            await writer.wait_closed()

            return (
                response.status == "ok" and
                response.request_id == f"concurrent-{client_id}"
            )

        # Run all clients concurrently
        tasks = [client_task(i) for i in range(num_clients)]
        results = await asyncio.gather(*tasks)

        assert all(results), "All concurrent clients should receive valid responses"

    @pytest.mark.asyncio
    async def test_client_reconnection_after_disconnect(
        self, running_server: DaemonServer, temp_socket_path: Path
    ) -> None:
        """Client should be able to reconnect after disconnecting."""
        for attempt in range(3):
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            request = IPCRequest(
                command=IPCCommand.SESSIONS_LIST,
                params={},
                request_id=f"reconnect-{attempt}",
            )
            writer.write(encode_message(request))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "ok"
            assert response.request_id == f"reconnect-{attempt}"

            # Disconnect
            writer.close()
            await writer.wait_closed()

            # Small delay between reconnects
            await asyncio.sleep(0.05)


class TestServerRestart:
    """Tests for server restart scenarios."""

    @pytest.mark.asyncio
    async def test_server_restart_new_clients_work(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """After server restart, new clients should be able to connect."""
        # Start server
        server = DaemonServer(
            socket_path=temp_socket_path,
            pid_path=temp_pid_path,
        )
        await server.start()

        # Connect and verify
        reader, writer = await asyncio.open_unix_connection(
            str(temp_socket_path)
        )
        request = IPCRequest(
            command=IPCCommand.SESSIONS_LIST,
            params={},
            request_id="before-restart",
        )
        writer.write(encode_message(request))
        await writer.drain()
        data = await reader.readline()
        response = decode_message(data)
        assert response.status == "ok"
        writer.close()
        await writer.wait_closed()

        # Stop server
        await server.stop()

        # Start new server
        server2 = DaemonServer(
            socket_path=temp_socket_path,
            pid_path=temp_pid_path,
        )
        await server2.start()

        # Connect to new server
        reader2, writer2 = await asyncio.open_unix_connection(
            str(temp_socket_path)
        )
        request2 = IPCRequest(
            command=IPCCommand.SESSIONS_LIST,
            params={},
            request_id="after-restart",
        )
        writer2.write(encode_message(request2))
        await writer2.drain()
        data2 = await reader2.readline()
        response2 = decode_message(data2)
        assert response2.status == "ok"
        assert response2.request_id == "after-restart"

        writer2.close()
        await writer2.wait_closed()
        await server2.stop()
