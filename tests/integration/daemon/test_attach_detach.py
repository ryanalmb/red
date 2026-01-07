"""Integration tests for Attach/Detach TUI Client cycle.

Tests the full attach/detach flow through the DaemonServer, verifying:
- AC#11: Integration test of full attach/detach cycle
- AC#3: Attach returns initial state snapshot
- NFR32: Attach latency <2s
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from unittest.mock import patch, MagicMock, AsyncMock
from cyberred.daemon.ipc import (
    IPCCommand,
    IPCRequest,
    IPCResponse,
    build_request,
    encode_message,
    decode_message,
)
from cyberred.daemon.server import DaemonServer
from cyberred.daemon.state_machine import EngagementState



@pytest.fixture
def mock_preflight():
    """Mock pre-flight checks globally for all integration tests."""
    with patch("cyberred.daemon.preflight.PreFlightRunner.run_all") as mock:
        mock.return_value = MagicMock(
            success=True,
            checks=[],
            failed_checks=[],
            duration_ms=10.0,
        )
        yield mock



@pytest.fixture
def temp_socket_path(tmp_path: Path) -> Path:
    """Create a temporary socket path for testing."""
    return tmp_path / "daemon.sock"


@pytest.fixture
def temp_pid_path(tmp_path: Path) -> Path:
    """Create a temporary PID file path for testing."""
    return tmp_path / "daemon.pid"


@pytest.fixture
async def running_server(
    temp_socket_path: Path, temp_pid_path: Path, mock_preflight
) -> DaemonServer:
    """Create and start a server, yielding it for tests."""
    server = DaemonServer(socket_path=temp_socket_path, pid_path=temp_pid_path)
    start_task = asyncio.create_task(server.start())
    await asyncio.sleep(0.1)  # Wait for server to start
    yield server
    await server.stop()
    start_task.cancel()
    try:
        await start_task
    except asyncio.CancelledError:
        pass


@pytest.fixture
def engagement_config(tmp_path: Path) -> Path:
    """Create a valid engagement config file."""
    config = tmp_path / "engagement.yaml"
    config.write_text("name: test-engagement\n")
    return config


def create_running_engagement(
    server: DaemonServer, config_path: Path
) -> str:
    """Helper to create and start an engagement using SessionManager.
    
    Uses the server's SessionManager directly for testing, then
    transitions to RUNNING state.
    """
    engagement_id = server.session_manager.create_engagement(config_path)
    context = server.session_manager.get_engagement(engagement_id)
    context.state_machine.start()
    return engagement_id


@pytest.mark.integration
class TestAttachInitialState:
    """Tests for attach command returning initial state snapshot (AC#3)."""

    @pytest.mark.asyncio
    async def test_attach_returns_subscription_id(
        self,
        running_server: DaemonServer,
        temp_socket_path: Path,
        engagement_config: Path,
    ) -> None:
        """Attach returns subscription_id for managing the connection."""
        engagement_id = create_running_engagement(running_server, engagement_config)

        reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))
        try:
            request = build_request(
                IPCCommand.ENGAGEMENT_ATTACH,
                engagement_id=engagement_id,
            )
            writer.write(encode_message(request))
            await writer.drain()

            response_data = await reader.readline()
            response = decode_message(response_data)

            assert response.status == "ok"
            assert "subscription_id" in response.data
            assert response.data["subscription_id"].startswith("sub-")
            assert response.data["state"] == "RUNNING"
        finally:
            writer.close()
            await writer.wait_closed()

    @pytest.mark.asyncio
    async def test_attach_returns_agent_and_finding_counts(
        self,
        running_server: DaemonServer,
        temp_socket_path: Path,
        engagement_config: Path,
    ) -> None:
        """Attach returns initial state snapshot with counts."""
        engagement_id = create_running_engagement(running_server, engagement_config)

        reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))
        try:
            request = build_request(
                IPCCommand.ENGAGEMENT_ATTACH,
                engagement_id=engagement_id,
            )
            writer.write(encode_message(request))
            await writer.drain()

            response_data = await reader.readline()
            response = decode_message(response_data)

            assert response.status == "ok"
            assert "agent_count" in response.data
            assert "finding_count" in response.data
            assert isinstance(response.data["agent_count"], int)
            assert isinstance(response.data["finding_count"], int)
        finally:
            writer.close()
            await writer.wait_closed()


@pytest.mark.integration
class TestDetachEngagementContinues:
    """Tests that engagement continues after detach (AC#11)."""

    @pytest.mark.asyncio
    async def test_detach_engagement_continues_running(
        self,
        running_server: DaemonServer,
        temp_socket_path: Path,
        engagement_config: Path,
    ) -> None:
        """Detach removes subscription but engagement keeps running."""
        engagement_id = create_running_engagement(running_server, engagement_config)
        context = running_server.session_manager.get_engagement(engagement_id)

        reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))
        try:
            attach_req = build_request(
                IPCCommand.ENGAGEMENT_ATTACH,
                engagement_id=engagement_id,
            )
            writer.write(encode_message(attach_req))
            await writer.drain()

            attach_resp = decode_message(await reader.readline())
            sub_id = attach_resp.data["subscription_id"]

            assert running_server.session_manager.get_subscription_count(engagement_id) == 1

            detach_req = build_request(
                IPCCommand.ENGAGEMENT_DETACH,
                subscription_id=sub_id,
                engagement_id=engagement_id,
            )
            writer.write(encode_message(detach_req))
            await writer.drain()

            detach_resp = decode_message(await reader.readline())
            assert detach_resp.status == "ok"
            assert detach_resp.data.get("detached") is True

            assert context.state == EngagementState.RUNNING
            assert running_server.session_manager.get_subscription_count(engagement_id) == 0
        finally:
            writer.close()
            await writer.wait_closed()

    @pytest.mark.asyncio
    async def test_reattach_after_detach(
        self,
        running_server: DaemonServer,
        temp_socket_path: Path,
        engagement_config: Path,
    ) -> None:
        """Can reattach to engagement after detaching."""
        engagement_id = create_running_engagement(running_server, engagement_config)

        reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))
        try:
            req1 = build_request(
                IPCCommand.ENGAGEMENT_ATTACH,
                engagement_id=engagement_id,
            )
            writer.write(encode_message(req1))
            await writer.drain()
            resp1 = decode_message(await reader.readline())
            sub_id1 = resp1.data["subscription_id"]

            detach = build_request(
                IPCCommand.ENGAGEMENT_DETACH,
                subscription_id=sub_id1,
                engagement_id=engagement_id,
            )
            writer.write(encode_message(detach))
            await writer.drain()
            await reader.readline()

            req2 = build_request(
                IPCCommand.ENGAGEMENT_ATTACH,
                engagement_id=engagement_id,
            )
            writer.write(encode_message(req2))
            await writer.drain()
            resp2 = decode_message(await reader.readline())

            assert resp2.status == "ok"
            assert resp2.data["subscription_id"] != sub_id1
            assert running_server.session_manager.get_subscription_count(engagement_id) == 1
        finally:
            writer.close()
            await writer.wait_closed()


@pytest.mark.integration
class TestMultipleClientsAttach:
    """Tests for multiple TUI clients attaching simultaneously."""

    @pytest.mark.asyncio
    async def test_multiple_clients_can_attach(
        self,
        running_server: DaemonServer,
        temp_socket_path: Path,
        engagement_config: Path,
    ) -> None:
        """Multiple clients can attach to same engagement."""
        engagement_id = create_running_engagement(running_server, engagement_config)

        subscription_ids = []

        for i in range(3):
            reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))
            try:
                req = build_request(
                    IPCCommand.ENGAGEMENT_ATTACH,
                    engagement_id=engagement_id,
                )
                writer.write(encode_message(req))
                await writer.drain()

                resp = decode_message(await reader.readline())
                assert resp.status == "ok"
                subscription_ids.append(resp.data["subscription_id"])
            finally:
                writer.close()
                await writer.wait_closed()

        assert running_server.session_manager.get_subscription_count(engagement_id) == 3
        assert len(set(subscription_ids)) == 3


@pytest.mark.integration
class TestAttachLatency:
    """NFR32: Attach latency <2s from command to TUI operational."""

    @pytest.mark.asyncio
    async def test_attach_latency_under_2s(
        self,
        running_server: DaemonServer,
        temp_socket_path: Path,
        engagement_config: Path,
    ) -> None:
        """Full attach cycle completes in <2s."""
        engagement_id = create_running_engagement(running_server, engagement_config)

        start = time.perf_counter()

        reader, writer = await asyncio.open_unix_connection(str(temp_socket_path))
        try:
            req = build_request(
                IPCCommand.ENGAGEMENT_ATTACH,
                engagement_id=engagement_id,
            )
            writer.write(encode_message(req))
            await writer.drain()

            resp_data = await reader.readline()
            response = decode_message(resp_data)

            elapsed = time.perf_counter() - start

            assert response.status == "ok"
            assert elapsed < 2.0, f"Attach took {elapsed:.3f}s, expected <2s (NFR32)"
            assert elapsed < 0.5, f"Attach took {elapsed:.3f}s, expected <500ms typically"
        finally:
            writer.close()
            await writer.wait_closed()

