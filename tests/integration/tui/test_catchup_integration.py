"""Integration tests for Catch-up Mode.

Story 11.5: RAG Management Panel - AC #4, #6
Tests for catch-up mode integration with TUI.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from textual.app import App

from cyberred.tui.catchup import (
    CatchupManager,
    CatchupEvent,
    CatchupEventType,
)
from cyberred.tui.widgets.timeline import TimelineScrubber, TimelineMarker


class MockStrategyStream:
    """Mock strategy stream for testing catch-up replay."""
    
    def __init__(self):
        self.replayed_events = []
    
    async def replay_event(self, event: CatchupEvent) -> None:
        """Store replayed event for verification."""
        self.replayed_events.append(event)


@pytest.mark.asyncio
async def test_catchup_mode_full_flow():
    """Test complete catch-up mode flow: queue -> replay -> clear."""
    manager = CatchupManager()
    stream = MockStrategyStream()
    
    # Simulate events that occurred during TUI disconnect
    base_time = datetime(2026, 1, 29, 12, 0, 0)
    events = [
        CatchupEvent(
            event_type=CatchupEventType.FINDING,
            timestamp=base_time + timedelta(minutes=1),
            payload={"finding_id": "CVE-2026-001", "severity": "critical"},
            source="recon-agent",
        ),
        CatchupEvent(
            event_type=CatchupEventType.AUTH_REQUEST,
            timestamp=base_time + timedelta(minutes=2),
            payload={"target": "10.0.0.5", "action": "exploit"},
            source="exploit-agent",
        ),
        CatchupEvent(
            event_type=CatchupEventType.STRATEGY_UPDATE,
            timestamp=base_time + timedelta(minutes=3),
            payload={"strategy": "pivot", "confidence": 0.85},
            source="director",
        ),
    ]
    
    # Queue events
    manager.queue_events(events)
    assert manager.pending_count == 3
    
    # Track progress
    progress_updates = []
    def on_progress(current, total):
        progress_updates.append((current, total))
    
    # Reduce delay for test speed
    manager._replay_delay = 0.001
    
    # Start catchup
    async def handler(event):
        await stream.replay_event(event)
    
    replayed = await manager.start_catchup(handler, on_progress=on_progress)
    
    # Verify all events replayed
    assert replayed == 3
    assert len(stream.replayed_events) == 3
    
    # Verify chronological order
    assert stream.replayed_events[0].event_type == CatchupEventType.FINDING
    assert stream.replayed_events[1].event_type == CatchupEventType.AUTH_REQUEST
    assert stream.replayed_events[2].event_type == CatchupEventType.STRATEGY_UPDATE
    
    # Verify progress was tracked
    assert progress_updates == [(1, 3), (2, 3), (3, 3)]
    
    # Verify cleanup
    assert manager.pending_count == 0
    assert manager.is_catching_up is False


@pytest.mark.asyncio
async def test_catchup_with_timeline_integration():
    """Test catch-up events are added to timeline as markers."""
    manager = CatchupManager()
    timeline = TimelineScrubber()
    
    base_time = datetime(2026, 1, 29, 12, 0, 0)
    events = [
        CatchupEvent(
            event_type=CatchupEventType.FINDING,
            timestamp=base_time + timedelta(minutes=5),
            payload={"label": "Critical CVE found"},
            source="agent-1",
        ),
        CatchupEvent(
            event_type=CatchupEventType.STRATEGY_UPDATE,
            timestamp=base_time + timedelta(minutes=10),
            payload={"label": "Strategy pivot"},
            source="director",
        ),
    ]
    
    manager.queue_events(events)
    manager._replay_delay = 0.001
    
    # Handler that adds markers to timeline
    async def handler(event):
        marker = TimelineMarker(
            timestamp=event.timestamp,
            event_type=event.event_type.value,
            label=event.payload.get("label", "Event"),
            severity="info",
        )
        timeline.add_marker(marker)
    
    await manager.start_catchup(handler)
    
    # Verify markers added to timeline
    markers = timeline.markers
    assert len(markers) == 2
    assert markers[0].event_type == "finding"
    assert markers[1].event_type == "strategy_update"


@pytest.mark.asyncio
async def test_catchup_resilience_to_handler_errors():
    """Test catch-up continues even if some events fail to replay."""
    manager = CatchupManager()
    
    base_time = datetime(2026, 1, 29, 12, 0, 0)
    events = [
        CatchupEvent(
            event_type=CatchupEventType.FINDING,
            timestamp=base_time + timedelta(minutes=1),
            payload={"id": 1},
            source="agent",
        ),
        CatchupEvent(
            event_type=CatchupEventType.FINDING,
            timestamp=base_time + timedelta(minutes=2),
            payload={"id": 2, "corrupt": True},  # Will cause error
            source="agent",
        ),
        CatchupEvent(
            event_type=CatchupEventType.FINDING,
            timestamp=base_time + timedelta(minutes=3),
            payload={"id": 3},
            source="agent",
        ),
    ]
    
    manager.queue_events(events)
    manager._replay_delay = 0.001
    
    successful_replays = []
    
    async def handler(event):
        if event.payload.get("corrupt"):
            raise ValueError("Corrupt event data")
        successful_replays.append(event.payload["id"])
    
    replayed = await manager.start_catchup(handler)
    
    # Should have attempted all 3, succeeded with 2
    assert replayed == 2
    assert successful_replays == [1, 3]


@pytest.mark.asyncio
async def test_timeline_scrubber_with_rag_events():
    """Test timeline displays RAG update events correctly."""
    async with App().run_test() as pilot:
        start = datetime(2026, 1, 29, 10, 0, 0)
        end = datetime(2026, 1, 29, 12, 0, 0)
        timeline = TimelineScrubber(start_time=start, end_time=end)
        await pilot.app.mount(timeline)
        
        # Add RAG update marker
        rag_marker = TimelineMarker(
            timestamp=datetime(2026, 1, 29, 11, 0, 0),
            event_type="rag",
            label="MITRE ATT&CK corpus updated",
            severity="info",
        )
        timeline.add_marker(rag_marker)
        
        # Verify marker position (50% = middle)
        markers = timeline.markers
        assert len(markers) == 1
        assert markers[0].event_type == "rag"
        
        # Scrub to marker position
        timeline.scrub_to(0.5)
        assert timeline.current_position == 0.5


@pytest.mark.asyncio
async def test_catchup_event_serialization_roundtrip():
    """Test events can be serialized and deserialized for daemon communication."""
    original = CatchupEvent(
        event_type=CatchupEventType.AUTH_REQUEST,
        timestamp=datetime(2026, 1, 29, 14, 30, 45),
        payload={"target": "192.168.1.100", "action": "scan", "agent": "recon-1"},
        source="exploit-agent-5",
    )
    
    # Serialize
    data = original.to_dict()
    
    # Deserialize
    restored = CatchupEvent.from_dict(data)
    
    # Verify
    assert restored.event_type == original.event_type
    assert restored.timestamp == original.timestamp
    assert restored.payload == original.payload
    assert restored.source == original.source
