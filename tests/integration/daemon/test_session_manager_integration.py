"""Integration tests for Session Manager multi-engagement isolation.

Tests for:
- Multi-engagement lifecycle management via IPC
- Engagement state isolation
- Resource limits enforcement
- Full request/response cycle with SessionManager
"""

import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import time

import pytest

from cyberred.daemon.ipc import (
    IPCCommand,
    IPCRequest,
    IPCResponse,
    encode_message,
    decode_message,
)
from cyberred.daemon.session_manager import SessionManager
from cyberred.daemon.state_machine import EngagementState


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


class TestMultiEngagementIsolation:
    """Integration tests for multi-engagement isolation."""

    @pytest.mark.asyncio
    async def test_multiple_engagements_have_independent_state(
        self, tmp_path: Path
    ) -> None:
        """Multiple engagements should have completely independent states."""
        manager = SessionManager()

        # Create 3 engagements
        configs = []
        engagement_ids = []
        for i in range(3):
            config = tmp_path / f"eng{i}.yaml"
            config.write_text(f"name: eng{i}\n")
            configs.append(config)
            eid = manager.create_engagement(config)
            engagement_ids.append(eid)
            time.sleep(0.01)  # Ensure unique timestamps

        # Start only the first one
        await manager.start_engagement(engagement_ids[0])

        # Verify states are independent
        ctx0 = manager.get_engagement(engagement_ids[0])
        ctx1 = manager.get_engagement(engagement_ids[1])
        ctx2 = manager.get_engagement(engagement_ids[2])

        assert ctx0 is not None
        assert ctx1 is not None
        assert ctx2 is not None

        assert ctx0.state == EngagementState.RUNNING
        assert ctx1.state == EngagementState.INITIALIZING
        assert ctx2.state == EngagementState.INITIALIZING

    @pytest.mark.asyncio
    async def test_engagement_lifecycle_isolation(self, tmp_path: Path) -> None:
        """State changes in one engagement should not affect others."""
        manager = SessionManager()

        # Create 2 engagements
        config1 = tmp_path / "eng1.yaml"
        config1.write_text("name: eng1\n")
        config2 = tmp_path / "eng2.yaml"
        config2.write_text("name: eng2\n")

        eid1 = manager.create_engagement(config1)
        eid2 = manager.create_engagement(config2)

        # Start both, pause first, stop second
        await manager.start_engagement(eid1)
        await manager.start_engagement(eid2)
        manager.pause_engagement(eid1)
        await manager.stop_engagement(eid2)

        ctx1 = manager.get_engagement(eid1)
        ctx2 = manager.get_engagement(eid2)

        assert ctx1 is not None
        assert ctx2 is not None
        assert ctx1.state == EngagementState.PAUSED
        assert ctx2.state == EngagementState.STOPPED

    @pytest.mark.asyncio
    async def test_engagement_removal_only_affects_removed(
        self, tmp_path: Path
    ) -> None:
        """Removing one engagement should not affect others."""
        manager = SessionManager()

        # Create 2 engagements, start and stop both
        config1 = tmp_path / "eng1.yaml"
        config1.write_text("name: eng1\n")
        config2 = tmp_path / "eng2.yaml"
        config2.write_text("name: eng2\n")

        eid1 = manager.create_engagement(config1)
        eid2 = manager.create_engagement(config2)

        await manager.start_engagement(eid1)
        await manager.start_engagement(eid2)
        await manager.stop_engagement(eid1)
        await manager.stop_engagement(eid2)

        # Remove first
        await manager.remove_engagement(eid1)

        # First should be gone, second should remain
        assert manager.get_engagement(eid1) is None
        assert manager.get_engagement(eid2) is not None
        assert manager.get_engagement(eid2).state == EngagementState.STOPPED


class TestMultiEngagementViaIPC:
    """Integration tests for multi-engagement operations via IPC."""

    @pytest.mark.asyncio
    async def test_sessions_list_returns_multiple_engagements(
        self, temp_socket_path: Path, temp_pid_path: Path, tmp_path: Path
    ) -> None:
        """sessions.list should return all engagements via IPC."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            # Create 3 engagements
            for i in range(3):
                config = tmp_path / f"eng{i}.yaml"
                config.write_text(f"name: eng{i}\n")

                request = IPCRequest(
                    command=IPCCommand.ENGAGEMENT_START,
                    params={"config_path": str(config)},
                    request_id=f"start-{i}",
                )
                writer.write(encode_message(request))
                await writer.drain()
                await reader.readline()  # consume response

            # List all engagements
            list_request = IPCRequest(
                command=IPCCommand.SESSIONS_LIST,
                params={},
                request_id="list-all",
            )
            writer.write(encode_message(list_request))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "ok"
            engagements = response.data.get("engagements", [])
            assert len(engagements) == 3

            # All should be RUNNING (created and started)
            for eng in engagements:
                assert eng["state"] == "RUNNING"
                assert "id" in eng
                assert "created_at" in eng

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_resource_limit_enforced_via_ipc(
        self, temp_socket_path: Path, temp_pid_path: Path, tmp_path: Path
    ) -> None:
        """Resource limits should be enforced for IPC-created engagements."""
        from cyberred.daemon.server import DaemonServer

        # Create server with max 2 engagements
        server = DaemonServer(
            socket_path=temp_socket_path,
            pid_path=temp_pid_path,
            max_engagements=2,
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            # Create 2 engagements (should succeed)
            for i in range(2):
                config = tmp_path / f"eng{i}.yaml"
                config.write_text(f"name: eng{i}\n")

                request = IPCRequest(
                    command=IPCCommand.ENGAGEMENT_START,
                    params={"config_path": str(config)},
                    request_id=f"start-{i}",
                )
                writer.write(encode_message(request))
                await writer.drain()
                data = await reader.readline()
                response = decode_message(data)
                assert response.status == "ok", f"Create {i} failed: {response.error}"

            # Third should fail with resource limit error
            config3 = tmp_path / "eng3.yaml"
            config3.write_text("name: eng3\n")

            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_START,
                params={"config_path": str(config3)},
                request_id="start-3",
            )
            writer.write(encode_message(request))
            await writer.drain()
            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "error"
            assert "Maximum active engagements" in response.error

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_full_engagement_lifecycle_via_ipc(
        self, temp_socket_path: Path, temp_pid_path: Path, tmp_path: Path
    ) -> None:
        """Full engagement lifecycle: create, start, pause, resume, stop, complete."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            config = tmp_path / "lifecycle.yaml"
            config.write_text("name: lifecycle\n")

            # Start (creates and starts)
            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_START,
                params={"config_path": str(config)},
                request_id="start",
            )
            writer.write(encode_message(request))
            await writer.drain()
            data = await reader.readline()
            response = decode_message(data)
            assert response.status == "ok"
            assert response.data["state"] == "RUNNING"
            engagement_id = response.data["id"]

            # Pause
            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_PAUSE,
                params={"engagement_id": engagement_id},
                request_id="pause",
            )
            writer.write(encode_message(request))
            await writer.drain()
            data = await reader.readline()
            response = decode_message(data)
            assert response.status == "ok"
            assert response.data["state"] == "PAUSED"

            # Resume
            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_RESUME,
                params={"engagement_id": engagement_id},
                request_id="resume",
            )
            writer.write(encode_message(request))
            await writer.drain()
            data = await reader.readline()
            response = decode_message(data)
            assert response.status == "ok"
            assert response.data["state"] == "RUNNING"

            # Stop
            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_STOP,
                params={"engagement_id": engagement_id},
                request_id="stop",
            )
            writer.write(encode_message(request))
            await writer.drain()
            data = await reader.readline()
            response = decode_message(data)
            assert response.status == "ok"
            assert response.data["state"] == "STOPPED"

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()


class TestEngagementErrorHandling:
    """Integration tests for error handling via IPC."""

    @pytest.mark.asyncio
    async def test_engagement_not_found_error(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Operations on nonexistent engagements should return error."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_PAUSE,
                params={"engagement_id": "nonexistent-123"},
                request_id="pause-none",
            )
            writer.write(encode_message(request))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "error"
            assert "not found" in response.error.lower()

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_invalid_state_transition_error(
        self, temp_socket_path: Path, temp_pid_path: Path, tmp_path: Path
    ) -> None:
        """Invalid state transitions should return error."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            config = tmp_path / "test.yaml"
            config.write_text("name: test\n")

            # Start engagement
            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_START,
                params={"config_path": str(config)},
                request_id="start",
            )
            writer.write(encode_message(request))
            await writer.drain()
            data = await reader.readline()
            response = decode_message(data)
            engagement_id = response.data["id"]

            # Try to resume when already RUNNING (should fail)
            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_RESUME,
                params={"engagement_id": engagement_id},
                request_id="resume-invalid",
            )
            writer.write(encode_message(request))
            await writer.drain()
            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "error"
            assert "Invalid state transition" in response.error

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_missing_parameter_error(
        self, temp_socket_path: Path, temp_pid_path: Path
    ) -> None:
        """Missing required parameters should return error."""
        from cyberred.daemon.server import DaemonServer

        server = DaemonServer(
            socket_path=temp_socket_path, pid_path=temp_pid_path
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(temp_socket_path)
            )

            # Try to pause without engagement_id
            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_PAUSE,
                params={},  # Missing engagement_id
                request_id="pause-no-id",
            )
            writer.write(encode_message(request))
            await writer.drain()

            data = await reader.readline()
            response = decode_message(data)

            assert response.status == "error"
            assert "Missing required parameter" in response.error

            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()
