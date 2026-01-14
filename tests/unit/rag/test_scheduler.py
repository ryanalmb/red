import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
import json

from cyberred.rag.scheduler import RAGScheduler, RAGSchedulerState
from cyberred.core.config import RAGConfig

@pytest.fixture
def mock_rag_config():
    return RAGConfig(
        store_path="/tmp/test_rag_store",
        update_schedule="weekly"
    )

@pytest.fixture
def scheduler(mock_rag_config):
    return RAGScheduler(config=mock_rag_config)

@pytest.mark.asyncio
async def test_scheduler_initialization(scheduler, mock_rag_config):
    """Test that scheduler initializes correctly."""
    assert scheduler.config == mock_rag_config
    assert not scheduler.is_running
    assert isinstance(scheduler.state, RAGSchedulerState)
    assert scheduler.state.last_status == "none"

# ... (skipped)

@pytest.mark.asyncio
async def test_trigger_now(scheduler):
    """Test manual trigger."""
    with patch.object(scheduler, '_run_refresh', new_callable=AsyncMock) as mock_refresh:
        await scheduler.trigger_now()
        # Allow the task to start
        await asyncio.sleep(0)
        mock_refresh.assert_called_once()

def test_state_persistence(scheduler, tmp_path):
    """Test state saving and loading."""
    state_file = tmp_path / ".scheduler_state.json"
    scheduler._state_file = state_file
    
    test_state = RAGSchedulerState(
        last_refresh=datetime(2023, 1, 1, 3, 0, 0),
        last_status="success",
        next_scheduled=datetime(2023, 1, 8, 3, 0, 0)
    )
    
    # Test Save
    scheduler._save_state(test_state)
    assert state_file.exists()
    
    data = json.loads(state_file.read_text())
    assert data["last_status"] == "success"
    assert data["last_refresh"] == "2023-01-01T03:00:00"
    
    # Test Load
    loaded_state = scheduler._load_state()
    assert loaded_state.last_status == "success"
    assert loaded_state.last_refresh == datetime(2023, 1, 1, 3, 0, 0)
