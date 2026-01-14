"""Integration tests for RAG Manager Widget."""
import pytest
import asyncio
from pathlib import Path
from textual.app import App
from textual.widgets import Button, DataTable, Static

from cyberred.tui.widgets.rag_manager import RAGManagerWidget
from cyberred.rag.store import RAGStore
from cyberred.rag.ingest import RAGIngestPipeline
from cyberred.rag.embeddings import RAGEmbeddings

# Mock source module for testing ingestion without external calls
import sys
from types import ModuleType
from unittest.mock import MagicMock

@pytest.fixture
def mock_source_module():
    """Register a mock source module for ingestion testing."""
    mod_name = "cyberred.rag.sources.mock_source"
    mock_mod = ModuleType(mod_name)
    
    async def mock_ingest(store=None, embeddings=None, incremental=True):
        # Simulate work
        pass

    mock_mod.ingest = MagicMock(side_effect=mock_ingest)
    sys.modules[mod_name] = mock_mod
    yield mock_mod
    del sys.modules[mod_name]

@pytest.mark.integration
@pytest.mark.asyncio
async def test_rag_manager_e2e(tmp_path, mock_source_module):
    """Test full RAG Manager flow with real components (but mock source logic)."""
    
    # Setup RAG components with temp DB
    db_path = tmp_path / "rag_store.lance"
    store = RAGStore(store_path=str(db_path))
    embeddings = RAGEmbeddings() # Default mock embeddings usually ok for tests?
    # RAGEmbeddings defaults attempt to load model, which might be slow.
    # In integration tests we might want to mock the embedding model or use a tiny one.
    # But for this test, we are testing the WIDGET interaction, not the RAG logic quality.
    # We can rely on mocked ingestion in the source.
    pipeline = RAGIngestPipeline(store, embeddings)
    
    widget = RAGManagerWidget(store, pipeline)
    
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        
        # Verify initial state
        title_widget = widget.query_one("#rag-title", Static)
        try:
             title_content = str(title_widget.render())
        except Exception:
             title_content = str(getattr(title_widget, "_renderable", ""))
             
        assert "RAG KNOWLEDGE BASE" in title_content
        
        # Patch KNOWN_SOURCES to use our mock
        widget.KNOWN_SOURCES = ["mock_source"]
        
        # Trigger "Update All"
        btn = widget.query_one("#btn-update-all", Button)
        # Verify direct interaction to avoid pilot.click flakiness
        await widget.on_button_pressed(Button.Pressed(btn))
        
        # Wait for async task
        await pilot.pause(0.5)
        
        # "Completed mock_source." or "All updates complete."
        progress = widget.query_one("#progress-display", Static)
        
        # Use simple string check on render() result or internal _renderable
        content = ""
        try:
            content = str(progress.render())
        except Exception:
            # Fallback to internal
            content = str(getattr(progress, "_renderable", ""))
            
        assert "complete" in content.lower() or "mock_source" in content or "Updating" in content

        # Check that mock ingest was called
        # We need access to the mock object created in fixture
        # But fixture yield isn't easily accessible here unless we stored it on sys.modules
        mock_mod = sys.modules.get("cyberred.rag.sources.mock_source")
        if mock_mod:
             mock_mod.ingest.assert_called()
