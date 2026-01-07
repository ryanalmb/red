"""Unit tests for SessionManager event propagation.

Tests that SessionManager correctly uses EventBus to publish state changes.
"""

import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import pytest
import json

from cyberred.daemon.session_manager import SessionManager
from cyberred.daemon.state_machine import EngagementState

@pytest.fixture
def mock_event_bus():
    """Create a mock EventBus."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus

@pytest.fixture
def mock_preflight():
    """Mock pre-flight checks globally for all tests."""
    with patch("cyberred.daemon.session_manager.PreFlightRunner") as MockRunner:
        runner = MagicMock()
        runner.run_all = AsyncMock(return_value=[])
        runner.validate_results = MagicMock()
        MockRunner.return_value = runner
        yield runner

@pytest.mark.asyncio
async def test_session_manager_publishes_state_events(
    tmp_path: Path, 
    mock_event_bus, 
    mock_preflight
):
    """Verify SessionManager publishes state changes to EventBus."""
    config = tmp_path / "test.yaml"
    config.write_text("name: test-events\n")
    
    manager = SessionManager(event_bus=mock_event_bus)
    engagement_id = manager.create_engagement(config)
    
    # helper to wait for call
    async def wait_for_publish(count_needed=1, timeout=1.0):
        start = time.time()
        while time.time() - start < timeout:
            if mock_event_bus.publish.call_count >= count_needed:
                return
            await asyncio.sleep(0.01)
        raise TimeoutError("EventBus publish not called")
    
    # 1. Start Engagement (INITIALIZING -> RUNNING)
    await manager.start_engagement(engagement_id)
    await wait_for_publish(1)
    
    # Check last call args
    call_args = mock_event_bus.publish.call_args
    channel = call_args[0][0]
    message = call_args[0][1]
    
    assert channel == f"engagement:{engagement_id}:state"
    assert message["type"] == "state_change"
    assert message["new_state"] == "RUNNING"
    
    # 2. Pause Engagement (RUNNING -> PAUSED)
    mock_event_bus.publish.reset_mock()
    manager.pause_engagement(engagement_id)
    await wait_for_publish(1)
    
    call_args = mock_event_bus.publish.call_args
    message = call_args[0][1]
    assert message["new_state"] == "PAUSED"
    
    # 3. Resume Engagement (PAUSED -> RUNNING)
    mock_event_bus.publish.reset_mock()
    manager.resume_engagement(engagement_id)
    await wait_for_publish(1)
    
    call_args = mock_event_bus.publish.call_args
    message = call_args[0][1]
    assert message["new_state"] == "RUNNING"
