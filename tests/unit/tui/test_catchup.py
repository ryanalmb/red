"""Unit tests for CatchupManager.

Story 11.5: RAG Management Panel - AC #4
Tests for catch-up mode event replay functionality.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from cyberred.tui.catchup import (
    CatchupManager,
    CatchupEvent,
    CatchupEventType,
    CatchupProgressIndicator,
)


# --- Fixtures ---

@pytest.fixture
def manager():
    """Create a fresh CatchupManager."""
    return CatchupManager()


@pytest.fixture
def sample_events():
    """Create sample events for testing."""
    base_time = datetime(2026, 1, 29, 12, 0, 0)
    return [
        CatchupEvent(
            event_type=CatchupEventType.FINDING,
            timestamp=base_time + timedelta(minutes=1),
            payload={"finding_id": "f1", "severity": "high"},
            source="agent-1",
        ),
        CatchupEvent(
            event_type=CatchupEventType.STRATEGY_UPDATE,
            timestamp=base_time + timedelta(minutes=2),
            payload={"strategy": "pivot"},
            source="director",
        ),
        CatchupEvent(
            event_type=CatchupEventType.AUTH_REQUEST,
            timestamp=base_time + timedelta(minutes=3),
            payload={"target": "10.0.0.5"},
            source="agent-2",
        ),
    ]


# --- CatchupEventType Tests ---

def test_catchup_event_type_values():
    """Test CatchupEventType enum values."""
    assert CatchupEventType.FINDING.value == "finding"
    assert CatchupEventType.AUTH_REQUEST.value == "auth_request"
    assert CatchupEventType.STRATEGY_UPDATE.value == "strategy_update"
    assert CatchupEventType.AGENT_STATE.value == "agent_state"
    assert CatchupEventType.RAG_UPDATE.value == "rag_update"


# --- CatchupEvent Tests ---

def test_catchup_event_to_dict():
    """Test CatchupEvent serialization."""
    event = CatchupEvent(
        event_type=CatchupEventType.FINDING,
        timestamp=datetime(2026, 1, 29, 12, 0, 0),
        payload={"test": "data"},
        source="agent-1",
    )
    
    result = event.to_dict()
    
    assert result["event_type"] == "finding"
    assert result["timestamp"] == "2026-01-29T12:00:00"
    assert result["payload"] == {"test": "data"}
    assert result["source"] == "agent-1"


def test_catchup_event_from_dict():
    """Test CatchupEvent deserialization."""
    data = {
        "event_type": "strategy_update",
        "timestamp": "2026-01-29T12:30:00",
        "payload": {"strategy": "test"},
        "source": "director",
    }
    
    event = CatchupEvent.from_dict(data)
    
    assert event.event_type == CatchupEventType.STRATEGY_UPDATE
    assert event.timestamp == datetime(2026, 1, 29, 12, 30, 0)
    assert event.payload == {"strategy": "test"}
    assert event.source == "director"


# --- CatchupManager Tests ---

def test_manager_initial_state(manager):
    """Test CatchupManager starts with correct initial state."""
    assert manager.events == []
    assert manager.is_catching_up is False
    assert manager.replay_index == 0
    assert manager.total_events == 0
    assert manager.pending_count == 0
    assert manager.progress_percent == 0.0
    assert manager.progress_text == ""


def test_queue_event(manager):
    """Test queuing a single event."""
    event = CatchupEvent(
        event_type=CatchupEventType.FINDING,
        timestamp=datetime.now(),
        payload={"test": "data"},
        source="test",
    )
    
    manager.queue_event(event)
    
    assert len(manager.events) == 1
    assert manager.events[0] == event
    assert manager.pending_count == 1


def test_queue_events_maintains_chronological_order(manager, sample_events):
    """Test that events are sorted chronologically when queued."""
    # Queue events out of order
    manager.queue_event(sample_events[2])  # minute 3
    manager.queue_event(sample_events[0])  # minute 1
    manager.queue_event(sample_events[1])  # minute 2
    
    # Should be sorted by timestamp
    assert manager.events[0].timestamp < manager.events[1].timestamp
    assert manager.events[1].timestamp < manager.events[2].timestamp


def test_queue_events_batch(manager, sample_events):
    """Test queuing multiple events at once."""
    manager.queue_events(sample_events)
    
    assert len(manager.events) == 3
    assert manager.pending_count == 3


def test_clear_events(manager, sample_events):
    """Test clearing all queued events."""
    manager.queue_events(sample_events)
    assert len(manager.events) == 3
    
    manager.clear()
    
    assert len(manager.events) == 0
    assert manager.pending_count == 0


@pytest.mark.asyncio
async def test_start_catchup_empty_queue(manager):
    """Test starting catchup with empty queue returns 0."""
    handler = AsyncMock()
    
    result = await manager.start_catchup(handler)
    
    assert result == 0
    handler.assert_not_called()


@pytest.mark.asyncio
async def test_start_catchup_replays_events(manager, sample_events):
    """Test that catchup replays all events in order."""
    manager.queue_events(sample_events)
    handler = AsyncMock()
    
    # Reduce delay for faster test
    manager._replay_delay = 0.001
    
    result = await manager.start_catchup(handler)
    
    assert result == 3
    assert handler.call_count == 3
    # Verify events were passed in chronological order
    calls = handler.call_args_list
    assert calls[0][0][0].event_type == CatchupEventType.FINDING
    assert calls[1][0][0].event_type == CatchupEventType.STRATEGY_UPDATE
    assert calls[2][0][0].event_type == CatchupEventType.AUTH_REQUEST


@pytest.mark.asyncio
async def test_start_catchup_clears_queue_after_completion(manager, sample_events):
    """Test that queue is cleared after successful catchup."""
    manager.queue_events(sample_events)
    manager._replay_delay = 0.001
    
    await manager.start_catchup(AsyncMock())
    
    assert len(manager.events) == 0
    assert manager.is_catching_up is False


@pytest.mark.asyncio
async def test_start_catchup_progress_callback(manager, sample_events):
    """Test that progress callback is called during catchup."""
    manager.queue_events(sample_events)
    manager._replay_delay = 0.001
    
    progress_calls = []
    def on_progress(current, total):
        progress_calls.append((current, total))
    
    await manager.start_catchup(AsyncMock(), on_progress=on_progress)
    
    assert len(progress_calls) == 3
    assert progress_calls[0] == (1, 3)
    assert progress_calls[1] == (2, 3)
    assert progress_calls[2] == (3, 3)


@pytest.mark.asyncio
async def test_start_catchup_continues_on_handler_error(manager, sample_events):
    """Test that catchup continues even if handler raises exception."""
    manager.queue_events(sample_events)
    manager._replay_delay = 0.001
    
    # Handler fails on second event
    call_count = 0
    async def failing_handler(event):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise ValueError("Test error")
    
    result = await manager.start_catchup(failing_handler)
    
    # Should have attempted all 3, but only 2 succeeded
    assert result == 2
    assert call_count == 3


@pytest.mark.asyncio
async def test_progress_text_during_catchup(manager, sample_events):
    """Test progress_text property during active catchup."""
    manager.queue_events(sample_events)
    manager._replay_delay = 0.01
    
    progress_texts = []
    
    async def capture_progress(event):
        progress_texts.append(manager.progress_text)
    
    await manager.start_catchup(capture_progress)
    
    assert "Catching up: 1/3 events" in progress_texts
    assert "Catching up: 2/3 events" in progress_texts
    assert "Catching up: 3/3 events" in progress_texts


@pytest.mark.asyncio
async def test_progress_percent_during_catchup(manager, sample_events):
    """Test progress_percent property during active catchup."""
    manager.queue_events(sample_events)
    manager._replay_delay = 0.01
    
    progress_percents = []
    
    async def capture_progress(event):
        progress_percents.append(manager.progress_percent)
    
    await manager.start_catchup(capture_progress)
    
    # Should have ~33%, ~66%, 100%
    assert len(progress_percents) == 3
    assert progress_percents[0] == pytest.approx(33.33, rel=0.1)
    assert progress_percents[1] == pytest.approx(66.67, rel=0.1)
    assert progress_percents[2] == pytest.approx(100.0, rel=0.1)


# --- CatchupProgressIndicator Tests ---

def test_progress_indicator_inactive(manager):
    """Test progress indicator when catchup is not active."""
    indicator = CatchupProgressIndicator(manager)
    
    assert indicator.is_active is False
    assert indicator.status_text == ""
    assert indicator.progress_bar == ""


def test_progress_indicator_active(manager, sample_events):
    """Test progress indicator when catchup is simulated as active."""
    manager.queue_events(sample_events)
    manager.is_catching_up = True
    manager.total_events = 3
    manager.replay_index = 2
    
    indicator = CatchupProgressIndicator(manager)
    
    assert indicator.is_active is True
    assert indicator.status_text == "Catching up: 2/3 events"
    assert "██" in indicator.progress_bar  # Has filled portion
    assert "░" in indicator.progress_bar  # Has empty portion


def test_progress_indicator_progress_bar_format(manager):
    """Test progress bar ASCII format."""
    manager.is_catching_up = True
    manager.total_events = 4
    manager.replay_index = 2  # 50%
    
    indicator = CatchupProgressIndicator(manager)
    bar = indicator.progress_bar
    
    assert bar.startswith("[")
    assert "]" in bar  # Ends with ] followed by percentage
    assert "50%" in bar


def test_pending_count_when_catching_up(manager, sample_events):
    """Test pending_count returns remaining events during catchup (line 226-227)."""
    manager.queue_events(sample_events)
    
    # Simulate being mid-catchup
    manager.is_catching_up = True
    manager.total_events = 3
    manager.replay_index = 1  # Processed 1, 2 remaining
    
    # Should return total - replay_index
    assert manager.pending_count == 2  # Line 226
    
    # Now test when NOT catching up - should return len(events) (line 227)
    manager.is_catching_up = False
    assert manager.pending_count == 3  # Line 227 - returns len(self.events)
