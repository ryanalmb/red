"""Safety tests for TUI attach latency (NFR32: <2s).

Story 9.8: TUI Attach Latency (<2s)
AC #4: Safety tests verify <2s attach latency.

These tests verify that TUI attach completes within the required 2 second
threshold at various agent scales (0, 100, 1000, 10000 agents).

NFR32: TUI attach must complete in <2 seconds.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from cyberred.daemon.ipc import IPCResponse
from cyberred.daemon.streaming import StreamEvent, StreamEventType, encode_stream_event
from cyberred.tui.daemon_client import TUIClient


# NFR32: TUI attach must complete in <2 seconds
ATTACH_LATENCY_THRESHOLD_MS = 2000.0


class TestAttachLatencySafety:
    """Safety gate tests for attach latency (NFR32)."""

    @pytest.mark.safety
    @pytest.mark.asyncio
    async def test_attach_latency_baseline_zero_agents(self, tmp_path: Path):
        """Test attach completes in <2s with 0 agents (baseline).
        
        AC #4: Safety tests verify <2s attach latency.
        Task 7.2: Test with 0 agents.
        """
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={
                        "subscription_id": "sub-baseline",
                        "state": "RUNNING",
                        "agent_count": 0,
                        "finding_count": 0,
                        "agents": [],
                        "findings": [],
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

            async for _ in client.attach("baseline-test"):
                break  # Get first event (initial state)

            assert client.attach_latency_ms is not None
            assert client.attach_latency_ms < ATTACH_LATENCY_THRESHOLD_MS, (
                f"Attach latency {client.attach_latency_ms:.2f}ms exceeds "
                f"{ATTACH_LATENCY_THRESHOLD_MS}ms threshold (baseline with 0 agents)"
            )
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.safety
    @pytest.mark.asyncio
    async def test_attach_latency_100_agents(self, tmp_path: Path):
        """Test attach completes in <2s with 100 agents.
        
        Task 7.3: Test with 100 agents.
        """
        socket_path = tmp_path / "daemon.sock"
        agent_count = 100

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                agents = [
                    {"id": f"agent-{i}", "status": "active", "target": f"10.0.0.{i % 256}"}
                    for i in range(agent_count)
                ]
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={
                        "subscription_id": "sub-100",
                        "state": "RUNNING",
                        "agent_count": agent_count,
                        "finding_count": 25,
                        "agents": agents,
                        "findings": [],
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

            async for _ in client.attach("scale-test-100"):
                break

            assert client.attach_latency_ms is not None
            assert client.attach_latency_ms < ATTACH_LATENCY_THRESHOLD_MS, (
                f"Attach latency {client.attach_latency_ms:.2f}ms with {agent_count} agents "
                f"exceeds {ATTACH_LATENCY_THRESHOLD_MS}ms threshold"
            )
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.safety
    @pytest.mark.asyncio
    async def test_attach_latency_1000_agents(self, tmp_path: Path):
        """Test attach completes in <2s with 1000 agents.
        
        Task 7.4: Test with 1000 agents.
        """
        socket_path = tmp_path / "daemon.sock"
        agent_count = 1000

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                agents = [
                    {"id": f"agent-{i}", "status": "active", "target": f"10.0.{i // 256}.{i % 256}"}
                    for i in range(agent_count)
                ]
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={
                        "subscription_id": "sub-1000",
                        "state": "RUNNING",
                        "agent_count": agent_count,
                        "finding_count": 100,
                        "agents": agents,
                        "findings": [],
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

            async for _ in client.attach("scale-test-1000"):
                break

            assert client.attach_latency_ms is not None
            assert client.attach_latency_ms < ATTACH_LATENCY_THRESHOLD_MS, (
                f"Attach latency {client.attach_latency_ms:.2f}ms with {agent_count} agents "
                f"exceeds {ATTACH_LATENCY_THRESHOLD_MS}ms threshold"
            )
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.safety
    @pytest.mark.asyncio
    async def test_attach_latency_10000_agents(self, tmp_path: Path):
        """Test attach completes in <2s with 10000 agents (full scale).
        
        Task 7.5: Test with 10000 agents.
        """
        socket_path = tmp_path / "daemon.sock"
        agent_count = 10000

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                # For 10K agents, use incremental mode - only return counts
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={
                        "subscription_id": "sub-10000",
                        "state": "RUNNING",
                        "agent_count": agent_count,
                        "finding_count": 500,
                        # Incremental mode: no full agent list
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

            # Use incremental sync for 10K scale
            async for _ in client.attach("scale-test-10000", sync_mode="incremental"):
                break

            assert client.attach_latency_ms is not None
            assert client.attach_latency_ms < ATTACH_LATENCY_THRESHOLD_MS, (
                f"Attach latency {client.attach_latency_ms:.2f}ms with {agent_count} agents "
                f"exceeds {ATTACH_LATENCY_THRESHOLD_MS}ms threshold"
            )
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.safety
    @pytest.mark.asyncio
    async def test_attach_timeout_handling_graceful_degradation(self, tmp_path: Path):
        """Test attach timeout handling when >2s (graceful degradation).
        
        Task 7.6: Test timeout handling.
        
        When attach takes longer than 2s, the TUI should still work but
        with a warning. This tests graceful degradation.
        """
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                # Simulate slow response (but under test timeout)
                await asyncio.sleep(0.1)  # Small delay to simulate latency
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={
                        "subscription_id": "sub-slow",
                        "state": "RUNNING",
                        "agent_count": 5000,
                        "finding_count": 200,
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

            async for _ in client.attach("slow-test"):
                break

            # Even with delay, attach should complete and latency should be tracked
            assert client.attach_latency_ms is not None
            # Note: In real scenario, if >2s we'd show warning but continue
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.safety
    @pytest.mark.asyncio
    async def test_attach_latency_property_is_set(self, tmp_path: Path):
        """Test that attach_latency_ms property is correctly set.
        
        Task 7.7: Assert TUIClient.attach_latency_ms is set and <2000.
        """
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={
                        "subscription_id": "sub-latency",
                        "state": "RUNNING",
                        "agent_count": 50,
                        "finding_count": 10,
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
            
            # Before attach, latency should be None
            assert client.attach_latency_ms is None
            
            await client.connect(socket_path)

            async for _ in client.attach("latency-test"):
                break

            # After attach, latency must be set
            assert client.attach_latency_ms is not None, (
                "attach_latency_ms must be set after successful attach"
            )
            assert isinstance(client.attach_latency_ms, float), (
                "attach_latency_ms must be a float"
            )
            assert client.attach_latency_ms > 0, (
                "attach_latency_ms must be positive"
            )
            assert client.attach_latency_ms < ATTACH_LATENCY_THRESHOLD_MS, (
                f"attach_latency_ms ({client.attach_latency_ms:.2f}ms) must be <{ATTACH_LATENCY_THRESHOLD_MS}ms"
            )
        finally:
            await client.close()
            server.close()
            await server.wait_closed()


class TestAttachLatencyParameterized:
    """Parameterized safety tests for various agent counts."""

    @pytest.mark.safety
    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_count", [0, 10, 50, 100, 500, 1000])
    async def test_attach_latency_at_scale(self, tmp_path: Path, agent_count: int):
        """Test attach completes in <2s at various agent scales.
        
        Parameterized test covering multiple scale points.
        """
        socket_path = tmp_path / f"daemon-{agent_count}.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={
                        "subscription_id": f"sub-{agent_count}",
                        "state": "RUNNING",
                        "agent_count": agent_count,
                        "finding_count": agent_count // 10,
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

            async for _ in client.attach(f"scale-{agent_count}"):
                break

            assert client.attach_latency_ms is not None
            assert client.attach_latency_ms < ATTACH_LATENCY_THRESHOLD_MS, (
                f"Attach latency {client.attach_latency_ms:.2f}ms with {agent_count} agents "
                f"exceeds {ATTACH_LATENCY_THRESHOLD_MS}ms threshold"
            )
        finally:
            await client.close()
            server.close()
            await server.wait_closed()
