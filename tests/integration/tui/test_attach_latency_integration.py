"""Integration tests for TUI attach latency (Story 9.8).

Tests cover:
- Full attach → state sync → TUI operational cycle (AC #1)
- Progress indicator appears during attach (AC #3)
- Progress indicator shows completion with latency (AC #3)
- State sync contains expected data (agents, findings, state) (AC #2)

Task 8: Integration Tests - Full Attach Flow
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from cyberred.daemon.ipc import IPCResponse
from cyberred.daemon.streaming import StreamEvent, StreamEventType, encode_stream_event
from cyberred.tui.daemon_client import TUIClient
from cyberred.tui.widgets.attach_progress import AttachProgressIndicator


class TestAttachFlowIntegration:
    """Integration tests for complete attach flow (Story 9.8)."""

    @pytest.mark.asyncio
    async def test_full_attach_state_sync_tui_operational_cycle(self, tmp_path: Path):
        """Test full attach → state sync → TUI operational cycle (AC #1, Task 8.2).
        
        Verifies that:
        1. Client connects successfully
        2. Client attaches to engagement
        3. Initial state is synced
        4. TUI becomes operational (receives events)
        5. Attach completes within 2s
        """
        socket_path = tmp_path / "daemon.sock"
        
        # Simulate daemon with full state sync and streaming events
        async def handle_client(reader, writer):
            try:
                # Read attach request
                await reader.readline()
                
                # Send initial state response
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={
                        "subscription_id": "sub-integration",
                        "state": "RUNNING",
                        "agent_count": 50,
                        "finding_count": 10,
                        "agents": [
                            {"id": f"agent-{i}", "status": "active"}
                            for i in range(50)
                        ],
                        "findings": [
                            {"id": f"finding-{i}", "severity": "MEDIUM"}
                            for i in range(10)
                        ],
                    },
                )
                writer.write((response.to_json() + "\n").encode())
                await writer.drain()
                
                # Stream some events to simulate TUI operational state
                events = [
                    StreamEvent(
                        event_type=StreamEventType.HEARTBEAT,
                        data={"timestamp": "2026-01-28T20:00:00Z"},
                    ),
                    StreamEvent(
                        event_type=StreamEventType.AGENT_STATUS,
                        data={"agent_id": "agent-0", "status": "busy"},
                    ),
                    StreamEvent(
                        event_type=StreamEventType.FINDING,
                        data={"finding_id": "finding-new", "severity": "HIGH"},
                    ),
                ]
                
                for event in events:
                    writer.write(encode_stream_event(event))
                    await writer.drain()
                    await asyncio.sleep(0.01)
                    
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_unix_server(handle_client, path=str(socket_path))

        try:
            client = TUIClient()
            
            # 1. Connect
            await client.connect(socket_path)
            assert client.connected is True
            
            # 2. Attach and receive events
            received_events = []
            async for event in client.attach("integration-test"):
                received_events.append(event)
            
            # 3. Verify initial state was synced (first event)
            assert len(received_events) >= 1
            initial_state = received_events[0]
            assert initial_state.event_type == StreamEventType.STATE_CHANGE
            assert initial_state.data["state"] == "RUNNING"
            assert initial_state.data["agent_count"] == 50
            assert initial_state.data["finding_count"] == 10
            
            # 4. Verify TUI received streaming events (operational)
            assert len(received_events) >= 3  # state + heartbeat + status + finding
            
            # 5. Verify attach latency is within threshold
            assert client.attach_latency_ms is not None
            assert client.attach_latency_ms < 2000.0
            
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_state_sync_contains_expected_data(self, tmp_path: Path):
        """Test state sync contains expected data (AC #2, Task 8.5).
        
        Verifies initial state sync includes:
        - Engagement state
        - Agent count and details
        - Finding count and details
        """
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={
                        "subscription_id": "sub-data",
                        "state": "PAUSED",
                        "agent_count": 3,
                        "finding_count": 2,
                        "agents": [
                            {"id": "recon-1", "status": "idle", "target": "10.0.0.1"},
                            {"id": "exploit-1", "status": "active", "target": "10.0.0.2"},
                            {"id": "postex-1", "status": "busy", "target": "10.0.0.3"},
                        ],
                        "findings": [
                            {"id": "vuln-1", "severity": "CRITICAL", "type": "RCE"},
                            {"id": "vuln-2", "severity": "HIGH", "type": "SQLi"},
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

            events = []
            async for event in client.attach("data-test"):
                events.append(event)
                break  # Only get first event

            assert len(events) == 1
            state_data = events[0].data
            
            # Verify engagement state
            assert state_data["state"] == "PAUSED"
            
            # Verify agent data
            assert state_data["agent_count"] == 3
            assert len(state_data["agents"]) == 3
            assert state_data["agents"][0]["id"] == "recon-1"
            
            # Verify finding data
            assert state_data["finding_count"] == 2
            assert len(state_data["findings"]) == 2
            assert state_data["findings"][0]["severity"] == "CRITICAL"
            
        finally:
            await client.close()
            server.close()
            await server.wait_closed()


class TestAttachProgressIndicatorIntegration:
    """Integration tests for AttachProgressIndicator widget (AC #3)."""

    def test_progress_indicator_initialization(self):
        """Test progress indicator initializes correctly (Task 8.3)."""
        indicator = AttachProgressIndicator()
        
        # Should start hidden
        assert indicator.is_visible is False
        assert indicator.status == "idle"
        assert indicator.engagement_id == ""

    def test_progress_indicator_start_shows_engagement(self):
        """Test progress indicator appears during attach (Task 8.3)."""
        indicator = AttachProgressIndicator()
        
        # Start should make it visible
        indicator.start("my-engagement-123")
        
        assert indicator.is_visible is True
        assert indicator.status == "attaching"
        assert indicator.engagement_id == "my-engagement-123"
        
        # Render should show engagement ID
        rendered = indicator.render()
        assert "my-engagement-123" in rendered
        assert "Attaching" in rendered

    def test_progress_indicator_complete_shows_latency(self):
        """Test progress indicator shows completion with latency (Task 8.4)."""
        indicator = AttachProgressIndicator()
        
        # Start then complete
        indicator.start("test-eng")
        indicator.complete(success=True, latency_ms=1234.5)
        
        assert indicator.status == "success"
        assert indicator.latency_ms == 1234.5
        
        # Render should show latency
        rendered = indicator.render()
        assert "1234" in rendered or "1235" in rendered  # Allow rounding
        assert "✓" in rendered

    def test_progress_indicator_complete_failure(self):
        """Test progress indicator shows failure correctly."""
        indicator = AttachProgressIndicator()
        
        indicator.start("failing-eng")
        indicator.complete(success=False)
        
        assert indicator.status == "error"
        
        rendered = indicator.render()
        assert "✗" in rendered
        assert "failed" in rendered.lower()


class TestIncrementalSyncIntegration:
    """Integration tests for incremental state sync (AC #2)."""

    @pytest.mark.asyncio
    async def test_incremental_sync_returns_counts_only(self, tmp_path: Path):
        """Test incremental sync returns counts without full details (Task 8.5).
        
        In incremental mode, the initial response should contain:
        - state
        - agent_count
        - finding_count
        
        But NOT the full agent/finding lists (for faster attach).
        """
        socket_path = tmp_path / "daemon.sock"
        received_params = {}

        async def handle_client(reader, writer):
            try:
                data = await reader.readline()
                import json
                received_params.update(json.loads(data.decode()))
                
                # Simulate incremental mode response
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={
                        "subscription_id": "sub-incremental",
                        "state": "RUNNING",
                        "agent_count": 10000,
                        "finding_count": 500,
                        # No agents/findings lists - incremental mode
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

            events = []
            async for event in client.attach("incremental-test", sync_mode="incremental"):
                events.append(event)
                break

            # Verify incremental mode was requested
            assert received_params["params"]["sync_mode"] == "incremental"
            
            # Verify counts are returned
            state_data = events[0].data
            assert state_data["agent_count"] == 10000
            assert state_data["finding_count"] == 500
            
            # In incremental mode, lists should be empty or not present
            agents = state_data.get("agents", [])
            findings = state_data.get("findings", [])
            assert len(agents) == 0
            assert len(findings) == 0
            
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_full_sync_returns_details(self, tmp_path: Path):
        """Test full sync returns complete agent/finding details."""
        socket_path = tmp_path / "daemon.sock"

        async def handle_client(reader, writer):
            try:
                await reader.readline()
                response = IPCResponse(
                    status="ok",
                    request_id="test",
                    data={
                        "subscription_id": "sub-full",
                        "state": "RUNNING",
                        "agent_count": 5,
                        "finding_count": 3,
                        "agents": [
                            {"id": f"agent-{i}", "status": "active"}
                            for i in range(5)
                        ],
                        "findings": [
                            {"id": f"finding-{i}", "severity": "HIGH"}
                            for i in range(3)
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

            events = []
            async for event in client.attach("full-test", sync_mode="full"):
                events.append(event)
                break

            state_data = events[0].data
            assert len(state_data["agents"]) == 5
            assert len(state_data["findings"]) == 3
            
        finally:
            await client.close()
            server.close()
            await server.wait_closed()
