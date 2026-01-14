"""Integration tests for Scheduled RAG Refresh (Story 6.12)."""
import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cyberred.rag.scheduler import RAGScheduler, RAGSchedulerState
from cyberred.core.config import RAGConfig

@pytest.fixture
def mock_settings(tmp_path):
    """Mock global settings."""
    with patch("cyberred.rag.scheduler.get_settings") as mock_get:
        settings = MagicMock()
        settings.rag = RAGConfig(
            store_path=str(tmp_path / "rag" / "lancedb"),
            update_schedule="weekly" # Allow start() to run
        )
        mock_get.return_value = settings
        yield settings

@pytest.fixture
def test_scheduler(mock_settings):
    """Create a scheduler instance."""
    return RAGScheduler(mock_settings.rag)

@pytest.mark.asyncio
@pytest.mark.rag
async def test_scheduler_lifecycle(test_scheduler):
    """Test scheduler start/stop lifecycle."""
    await test_scheduler.start()
    assert test_scheduler.is_running
    
    await test_scheduler.stop()
    assert not test_scheduler.is_running

@pytest.mark.asyncio
@pytest.mark.rag
async def test_manual_trigger_execution(test_scheduler, tmp_path):
    """Test that manual trigger actually runs the refresh logic."""
    # Mock dynamic import to track execution
    with patch("importlib.import_module") as mock_import:
        mock_source_module = MagicMock()
        mock_source_module.ingest = MagicMock()
        
        # Mock successful ingest
        from cyberred.rag.ingest import IngestionStats
        from datetime import datetime
        stats = IngestionStats(
            source="test_source",
            last_updated=datetime.now(),
            chunk_count=10,
            document_count=5,
            file_hashes={},
            failed_docs=[]
        )
        
        # Async mock for ingest
        async def async_ingest(**kwargs):
            return stats
        mock_source_module.ingest.side_effect = async_ingest
        
        mock_import.return_value = mock_source_module
        
        # Trigger
        await test_scheduler.trigger_now()
        
        # Allow background task to run
        await asyncio.sleep(0.1)
        
        # Verify import was called for sources
        assert mock_import.call_count >= 1 # mitre_attack, etc.
        
        # Verify state updated
        assert test_scheduler.state.last_refresh is not None
        assert test_scheduler.state.last_status == "success"
        
        # Verify persistence
        state_file = Path(test_scheduler.config.store_path).parent / ".scheduler_state.json"
        assert state_file.exists()
        saved_data = json.loads(state_file.read_text())
        assert saved_data["last_status"] == "success"

@pytest.mark.asyncio
@pytest.mark.rag
async def test_state_persistence_across_instances(mock_settings, tmp_path):
    """Test that state persists across scheduler restarts."""
    # 1. Run first scheduler
    scheduler1 = RAGScheduler(mock_settings.rag)
    # Fake a state update
    scheduler1._state.last_status = "success"
    scheduler1._save_state(scheduler1._state)
    
    # 2. Create second scheduler (simulating restart)
    scheduler2 = RAGScheduler(mock_settings.rag)
    
    # Verify loaded state
    assert scheduler2.state.last_status == "success"

@pytest.mark.asyncio
@pytest.mark.rag
async def test_error_handling(test_scheduler):
    """Test that failure in one source doesn't crash scheduler."""
    with patch("importlib.import_module") as mock_import:
        mock_module = MagicMock()
        # Mock ingest raising exception
        async def failing_ingest(**kwargs):
            raise ValueError("Ingest failed")
        mock_module.ingest.side_effect = failing_ingest
        mock_import.return_value = mock_module
        
        await test_scheduler.trigger_now()
        await asyncio.sleep(0.1)
        
        # Should still be running (if loop was running) or handled gracefully
        assert test_scheduler.state.last_status == "failed" # All sources failed
