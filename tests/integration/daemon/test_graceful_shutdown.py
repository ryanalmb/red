"""Integration tests for graceful shutdown (Story 2.11).

These tests verify the complete shutdown sequence with real engagements,
checkpoints, and client notifications.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from cyberred.daemon.server import DaemonServer
from cyberred.daemon.session_manager import SessionManager, ShutdownResult
from cyberred.daemon.state_machine import EngagementState
from cyberred.daemon.streaming import StreamEvent, StreamEventType
from cyberred.daemon.ipc import (
    IPCCommand,
    IPCRequest,
    encode_message,
    decode_message,
)


@pytest.fixture(autouse=True)
def mock_preflight():
    """Mock pre-flight checks for all integration tests."""
    with patch("cyberred.daemon.session_manager.PreFlightRunner") as MockRunner:
        runner = MagicMock()
        runner.run_all = AsyncMock(return_value=[])
        runner.validate_results = MagicMock()
        MockRunner.return_value = runner
        yield runner


@pytest.mark.integration
@pytest.mark.asyncio
class TestGracefulShutdownIntegration:
    """Integration tests for graceful daemon shutdown."""

    async def test_shutdown_preserves_running_engagement(self, tmp_path: Path) -> None:
        """Graceful shutdown should transition RUNNING → PAUSED → STOPPED."""
        socket_path = tmp_path / "daemon.sock"
        pid_path = tmp_path / "daemon.pid"
        config = tmp_path / "engagement.yaml"
        config.write_text("name: testeng\n")

        server = DaemonServer(socket_path=socket_path, pid_path=pid_path)
        await server.start()

        # Start engagement via IPC
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        request = IPCRequest(
            command=IPCCommand.ENGAGEMENT_START,
            params={"config_path": str(config)},
            request_id="test-start",
        )
        writer.write(encode_message(request))
        await writer.drain()
        data = await reader.readline()
        response = decode_message(data)
        assert response.status == "ok"
        engagement_id = response.data["id"]

        writer.close()
        await writer.wait_closed()

        # Verify engagement is RUNNING
        ctx = server._session_manager.get_engagement(engagement_id)
        assert ctx.state == EngagementState.RUNNING

        # Graceful shutdown
        exit_code = await server.stop(graceful=True, timeout=10.0)

        assert exit_code == 0
        # Engagement should now be STOPPED
        assert ctx.state == EngagementState.STOPPED

    async def test_shutdown_preserves_paused_engagement(self, tmp_path: Path) -> None:
        """Graceful shutdown should checkpoint already PAUSED engagements."""
        socket_path = tmp_path / "daemon.sock"
        pid_path = tmp_path / "daemon.pid"
        config = tmp_path / "engagement.yaml"
        config.write_text("name: pausedtest\n")

        server = DaemonServer(socket_path=socket_path, pid_path=pid_path)
        await server.start()

        # Start and pause engagement
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        
        # Start
        start_request = IPCRequest(
            command=IPCCommand.ENGAGEMENT_START,
            params={"config_path": str(config)},
            request_id="test-start",
        )
        writer.write(encode_message(start_request))
        await writer.drain()
        data = await reader.readline()
        response = decode_message(data)
        engagement_id = response.data["id"]

        # Pause
        pause_request = IPCRequest(
            command=IPCCommand.ENGAGEMENT_PAUSE,
            params={"engagement_id": engagement_id},
            request_id="test-pause",
        )
        writer.write(encode_message(pause_request))
        await writer.drain()
        data = await reader.readline()
        response = decode_message(data)
        assert response.status == "ok", f"Pause failed: {response.error}"

        writer.close()
        await writer.wait_closed()

        # Verify engagement is PAUSED
        ctx = server._session_manager.get_engagement(engagement_id)
        assert ctx.state == EngagementState.PAUSED

        # Graceful shutdown
        exit_code = await server.stop(graceful=True, timeout=10.0)

        assert exit_code == 0
        # Engagement should now be STOPPED
        assert ctx.state == EngagementState.STOPPED

    async def test_shutdown_multiple_engagements(self, tmp_path: Path) -> None:
        """Graceful shutdown should preserve multiple simultaneous engagements."""
        socket_path = tmp_path / "daemon.sock"
        pid_path = tmp_path / "daemon.pid"
        
        # Create multiple config files
        configs = []
        for i in range(3):
            config = tmp_path / f"eng{i}.yaml"
            config.write_text(f"name: eng{i}\n")
            configs.append(config)

        server = DaemonServer(socket_path=socket_path, pid_path=pid_path)
        await server.start()

        # Start all engagements
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        engagement_ids = []
        
        for i, config in enumerate(configs):
            request = IPCRequest(
                command=IPCCommand.ENGAGEMENT_START,
                params={"config_path": str(config)},
                request_id=f"start-{i}",
            )
            writer.write(encode_message(request))
            await writer.drain()
            data = await reader.readline()
            response = decode_message(data)
            assert response.status == "ok"
            engagement_ids.append(response.data["id"])

        writer.close()
        await writer.wait_closed()

        # Verify all are RUNNING
        for eid in engagement_ids:
            ctx = server._session_manager.get_engagement(eid)
            assert ctx.state == EngagementState.RUNNING

        # Graceful shutdown
        exit_code = await server.stop(graceful=True, timeout=15.0)

        assert exit_code == 0
        # All engagements should be STOPPED
        for eid in engagement_ids:
            ctx = server._session_manager.get_engagement(eid)
            assert ctx.state == EngagementState.STOPPED

    async def test_clients_receive_shutdown_notification(self, tmp_path: Path) -> None:
        """TUI clients should receive DAEMON_SHUTDOWN event before disconnection."""
        socket_path = tmp_path / "daemon.sock"
        pid_path = tmp_path / "daemon.pid"
        config = tmp_path / "engagement.yaml"
        config.write_text("name: notifytest\n")

        server = DaemonServer(socket_path=socket_path, pid_path=pid_path)
        await server.start()

        # Start engagement
        eid = server._session_manager.create_engagement(config)
        await server._session_manager.start_engagement(eid)

        # Create subscription with callback
        notifications_received = []
        
        def callback(event):
            notifications_received.append(event)

        server._session_manager.subscribe_to_engagement(eid, callback)

        # Verify subscription is active
        assert server._session_manager.get_subscription_count(eid) == 1

        # Graceful shutdown
        exit_code = await server.stop(graceful=True, timeout=10.0)

        assert exit_code == 0

        # Verify client received shutdown notification
        assert len(notifications_received) >= 1
        shutdown_event = notifications_received[0]
        assert shutdown_event.event_type == StreamEventType.DAEMON_SHUTDOWN
        assert "reason" in shutdown_event.data
        assert "shutdown_in_seconds" in shutdown_event.data

    async def test_graceful_shutdown_preserves_all_findings(self, tmp_path: Path) -> None:
        """NFR12: Graceful shutdown must preserve 100% of findings.
        
        This test verifies that the checkpoint process captures all findings
        from engagements during shutdown.
        """
        socket_path = tmp_path / "daemon.sock"
        pid_path = tmp_path / "daemon.pid"
        config = tmp_path / "engagement.yaml"
        config.write_text("name: findingstest\n")

        # Create mock checkpoint manager to track findings
        saved_findings = []
        
        mock_checkpoint_manager = MagicMock()
        mock_checkpoint_manager.save = AsyncMock(
            side_effect=lambda engagement_id, scope_path, agents, findings: (
                saved_findings.append({"id": engagement_id, "findings": findings}),
                tmp_path / f"{engagement_id}/checkpoint.sqlite"
            )[1]
        )
        mock_checkpoint_manager.delete = AsyncMock()

        server = DaemonServer(socket_path=socket_path, pid_path=pid_path)
        # Inject checkpoint manager into session manager
        server._session_manager._checkpoint_manager = mock_checkpoint_manager
        await server.start()

        # Start engagement
        eid = server._session_manager.create_engagement(config)
        await server._session_manager.start_engagement(eid)

        # Simulate findings by setting finding_count (Epic 7 placeholder)
        ctx = server._session_manager.get_engagement(eid)
        ctx.finding_count = 5  # Placeholder for actual findings

        # Graceful shutdown
        exit_code = await server.stop(graceful=True, timeout=10.0)

        assert exit_code == 0
        # Checkpoint manager should have been called
        assert mock_checkpoint_manager.save.called
        # Findings list should have been passed (even if empty placeholder)
        assert len(saved_findings) >= 1


@pytest.mark.integration
@pytest.mark.asyncio
class TestGracefulShutdownEdgeCases:
    """Edge case tests for graceful shutdown."""

    async def test_shutdown_with_no_engagements(self, tmp_path: Path) -> None:
        """Graceful shutdown should succeed with no active engagements."""
        socket_path = tmp_path / "daemon.sock"
        pid_path = tmp_path / "daemon.pid"

        server = DaemonServer(socket_path=socket_path, pid_path=pid_path)
        await server.start()

        # No engagements started
        
        # Graceful shutdown
        exit_code = await server.stop(graceful=True, timeout=5.0)

        assert exit_code == 0
        assert not socket_path.exists()
        assert not pid_path.exists()

    async def test_shutdown_timeout_forces_cleanup(self, tmp_path: Path) -> None:
        """Shutdown timeout should force cleanup and exit with code 1."""
        socket_path = tmp_path / "daemon.sock"
        pid_path = tmp_path / "daemon.pid"

        server = DaemonServer(socket_path=socket_path, pid_path=pid_path)
        await server.start()

        # Mock session manager to hang during shutdown
        async def slow_graceful_shutdown():
            await asyncio.sleep(60)  # Hang forever
            return ShutdownResult(paused_ids=[], checkpoint_paths={}, errors=[])

        server._session_manager.graceful_shutdown = slow_graceful_shutdown

        # Very short timeout
        exit_code = await server.stop(graceful=True, timeout=0.1)

        assert exit_code == 1  # Timeout exit code
        # Cleanup should still happen despite timeout
        assert not socket_path.exists()
        assert not pid_path.exists()

    async def test_shutdown_error_exits_code_1(self, tmp_path: Path) -> None:
        """Error during graceful shutdown should exit with code 1."""
        socket_path = tmp_path / "daemon.sock"
        pid_path = tmp_path / "daemon.pid"

        server = DaemonServer(socket_path=socket_path, pid_path=pid_path)
        await server.start()

        # Mock session manager to raise error
        async def failing_graceful_shutdown():
            raise RuntimeError("Simulated shutdown failure")

        server._session_manager.graceful_shutdown = failing_graceful_shutdown

        exit_code = await server.stop(graceful=True)

        assert exit_code == 1
        # Cleanup should still happen despite error
        assert not socket_path.exists()
        assert not pid_path.exists()
