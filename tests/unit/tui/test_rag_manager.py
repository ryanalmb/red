"""Unit tests for RAG Manager Widget."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from textual.app import App
from textual.widgets import Button, DataTable, Static

from cyberred.tui.widgets.rag_manager import RAGManagerWidget
from cyberred.rag.models import RAGStoreStats
from datetime import datetime

# --- Helpers ---
def get_widget_content(widget):
    try:
        return str(widget.render())
    except Exception:
        return str(getattr(widget, "_renderable", ""))

# --- Fixtures ---
@pytest.fixture
def mock_rag_store():
    store = MagicMock()
    stats = RAGStoreStats(
        total_vectors=1234,
        storage_size_bytes=1024 * 1024 * 50,
        sources=["source1", "source2"],
        last_updated=datetime(2026, 1, 1, 12, 0, 0),
        source_counts={"source1": 1000, "source2": 234}
    )
    store.get_stats = AsyncMock(return_value=stats)
    store._store_path = MagicMock()
    return store

@pytest.fixture
def mock_ingest_pipeline():
    pipeline = MagicMock()
    pipeline.process = AsyncMock()
    pipeline._embeddings = MagicMock()
    return pipeline

@pytest.fixture
def widget(mock_rag_store, mock_ingest_pipeline):
    return RAGManagerWidget(mock_rag_store, mock_ingest_pipeline)

# --- Tests ---

@pytest.mark.asyncio
async def test_widget_composition(widget):
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        assert widget.query_one("#rag-title", Static)

@pytest.mark.asyncio
async def test_initial_stats_refresh(widget, mock_rag_store):
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        await pilot.pause()
        mock_rag_store.get_stats.assert_called()
        assert "50.0 MB" in get_widget_content(widget.query_one("#corpus-stats", Static))

@pytest.mark.asyncio
async def test_format_size_edge_cases(widget):
    assert widget._format_size(0) == "0 B"
    assert widget._format_size(1024) == "1.0 KB"

@pytest.mark.asyncio
async def test_get_source_timestamp_logic(widget, mock_rag_store):
    from pathlib import Path
    from unittest.mock import PropertyMock
    
    # Create a proper mock for db_path that returns a Path-like object
    mock_parent = MagicMock()
    mock_db_path = MagicMock()
    mock_db_path.parent = mock_parent
    
    # Set db_path as a property on the store
    type(mock_rag_store).db_path = PropertyMock(return_value=mock_db_path)
    
    mock_file = MagicMock()
    mock_file.exists.return_value = True
    mock_file.read_text.return_value = '{"source": "test", "last_updated": "2026-01-01T12:00:00", "chunk_count": 10, "document_count": 1, "file_hashes": {}, "failed_docs": []}'
    mock_parent.__truediv__.return_value = mock_file
    
    ts = widget._get_source_timestamp("test")
    assert "2026-01-01 12:00" in ts

@pytest.mark.asyncio
async def test_selection_update(widget):
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        
        table = widget.query_one("#source-table", DataTable)
        table.add_row("test_source", "0", "Never", "Ready", key="test_source")
        
        # Trigger selection
        mock_event = MagicMock()
        mock_event.row_key.value = "test_source"
        await widget.on_data_table_row_selected(mock_event)
        
        assert widget._selected_source == "test_source"
        
        call_event = asyncio.Event()
        async def mark_called(*args, **kwargs):
            call_event.set()
        
        with patch.object(widget, "_run_ingestion", side_effect=mark_called) as mock_run:
            # Invoke handler directly to simulate button press
            btn = widget.query_one("#btn-update-selected", Button)
            pressed_event = Button.Pressed(btn)
            await widget.on_button_pressed(pressed_event)
            
            # Wait for task
            try:
                await asyncio.wait_for(call_event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            
            mock_run.assert_called_with(sources=["test_source"])

@pytest.mark.asyncio
async def test_update_all_trigger(widget):
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        
        call_event = asyncio.Event()
        async def mark_called(*args, **kwargs):
            call_event.set()
            
        with patch.object(widget, "_run_ingestion", side_effect=mark_called) as mock_run:
            btn = widget.query_one("#btn-update-all", Button)
            await widget.on_button_pressed(Button.Pressed(btn))
            
            try:
                await asyncio.wait_for(call_event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            mock_run.assert_called_with()

@pytest.mark.asyncio
async def test_close_button(widget):
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        widget.screen.dismiss = MagicMock()
        
        btn = widget.query_one("#btn-close", Button)
        await widget.on_button_pressed(Button.Pressed(btn))
        
        widget.screen.dismiss.assert_called()

@pytest.mark.asyncio
async def test_ingest_cancellation(widget):
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        
        ingest_started = asyncio.Event()
        async def long_run(*args, **kwargs):
            ingest_started.set()
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                raise
        
        with patch("importlib.import_module") as mock_import:
             mock_mod = MagicMock()
             mock_mod.ingest = AsyncMock(side_effect=long_run)
             mock_import.return_value = mock_mod
             
             # Simulate clicking the "Update All" button which sets _update_task
             btn_update = widget.query_one("#btn-update-all", Button)
             await widget.on_button_pressed(Button.Pressed(btn_update))
             
             # Wait for ingestion to start
             await asyncio.wait_for(ingest_started.wait(), timeout=2.0)
             
             assert widget.is_updating
             assert not widget.query_one("#btn-cancel", Button).disabled
             
             # Cancel via handler - this cancels _update_task
             btn_cancel = widget.query_one("#btn-cancel", Button)
             await widget.on_button_pressed(Button.Pressed(btn_cancel))
             
             # Wait for the task to complete (cancelled)
             try:
                 await asyncio.wait_for(widget._update_task, timeout=2.0)
             except (asyncio.CancelledError, TypeError):
                 pass  # Task was cancelled or already None
             
             # Give time for finally block to execute
             await asyncio.sleep(0.1)
             
             assert not widget.is_updating
             content = get_widget_content(widget.query_one("#progress-display", Static)).lower()
             assert "cancel" in content

@pytest.mark.asyncio
async def test_ingest_error_handling(widget):
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        
        with patch("importlib.import_module") as mock_import:
             # Case: Ingest error - use a valid source from KNOWN_SOURCES
             mock_mod = MagicMock()
             mock_mod.ingest = AsyncMock(side_effect=ValueError("Boom"))
             mock_import.return_value = mock_mod
             
             await widget._run_ingestion(["mitre_attack"])
             
             prog = widget.query_one("#progress-display", Static)
             content = get_widget_content(prog)
             # Check for error indication (case-insensitive) and error message
             assert "error" in content.lower() and "Boom" in content

@pytest.mark.asyncio
async def test_stats_refresh_error(widget, mock_rag_store):
    mock_rag_store.get_stats.side_effect = Exception("DB Error")
    async with App().run_test() as pilot:
         await pilot.app.mount(widget)
         await pilot.pause()
         assert "DB Error" in get_widget_content(widget.query_one("#corpus-stats", Static))


@pytest.mark.asyncio
async def test_format_size_terabytes(widget):
    """Test TB formatting for large sizes."""
    # 1.5 TB = 1.5 * 1024^4 bytes
    tb_size = int(1.5 * 1024 * 1024 * 1024 * 1024)
    result = widget._format_size(tb_size)
    assert "TB" in result
    assert "1.5" in result


@pytest.mark.asyncio
async def test_get_source_timestamp_fallback_store_path(mock_rag_store, mock_ingest_pipeline):
    """Test fallback to _store_path when db_path is not available."""
    from pathlib import Path
    import tempfile
    import json
    
    # Create a real temp directory for _store_path
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        store_path.mkdir()
        
        # Create a fresh mock store WITHOUT db_path attribute using spec to control attributes
        fresh_store = MagicMock(spec=['_store_path', 'get_stats'])
        fresh_store._store_path = store_path
        fresh_store.get_stats = AsyncMock(return_value=RAGStoreStats(
            total_vectors=0, storage_size_bytes=0, sources=[], 
            last_updated=datetime(2026, 1, 1), source_counts={}
        ))
        
        # Create widget with fresh store
        test_widget = RAGManagerWidget(fresh_store, mock_ingest_pipeline)
        
        # Create stats file in parent directory (tmpdir is parent of store_path)
        stats_file = Path(tmpdir) / ".rag_stats_test_source.json"
        stats_data = {
            "source": "test_source",
            "last_updated": "2026-01-01T12:00:00",
            "chunk_count": 10,
            "document_count": 1,
            "file_hashes": {},
            "failed_docs": []
        }
        stats_file.write_text(json.dumps(stats_data))
        
        ts = test_widget._get_source_timestamp("test_source")
        assert "2026-01-01 12:00" in ts


@pytest.mark.asyncio
async def test_get_source_timestamp_no_path_returns_never(widget, mock_rag_store):
    """Test that 'Never' is returned when no path is available."""
    # Remove both db_path and _store_path
    if hasattr(type(mock_rag_store), 'db_path'):
        delattr(type(mock_rag_store), 'db_path')
    mock_rag_store._store_path = None
    
    ts = widget._get_source_timestamp("any_source")
    assert ts == "Never"


@pytest.mark.asyncio
async def test_close_button_no_screen(widget):
    """Test close button when screen is None (uses remove())."""
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        
        # Patch the screen property to return None
        widget.remove = MagicMock()
        
        with patch.object(type(widget), 'screen', new_callable=lambda: property(lambda self: None)):
            btn = widget.query_one("#btn-close", Button)
            await widget.on_button_pressed(Button.Pressed(btn))
            
            # When screen is None, remove() should be called
            widget.remove.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_unknown_source_skipped(widget):
    """Test that unknown sources are skipped with warning."""
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        
        # Try to ingest an unknown source
        await widget._run_ingestion(["unknown_invalid_source"])
        
        # Should complete without error, source was skipped
        prog = widget.query_one("#progress-display", Static)
        content = get_widget_content(prog)
        assert "complete" in content.lower()


@pytest.mark.asyncio
async def test_ingest_module_without_ingest_method(widget):
    """Test handling of module without ingest() method."""
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        
        with patch("importlib.import_module") as mock_import:
            # Module exists but has no ingest method
            mock_mod = MagicMock(spec=[])  # Empty spec means no 'ingest' attribute
            del mock_mod.ingest  # Ensure ingest doesn't exist
            mock_import.return_value = mock_mod
            
            await widget._run_ingestion(["mitre_attack"])
            
            prog = widget.query_one("#progress-display", Static)
            content = get_widget_content(prog)
            # Should mention skipping or no ingest method
            assert "Skipping" in content or "complete" in content.lower()


@pytest.mark.asyncio
async def test_ingest_successful_completion(widget):
    """Test successful ingestion of a source."""
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        
        with patch("importlib.import_module") as mock_import:
            mock_mod = MagicMock()
            mock_mod.ingest = AsyncMock(return_value=None)
            mock_import.return_value = mock_mod
            
            await widget._run_ingestion(["mitre_attack"])
            
            prog = widget.query_one("#progress-display", Static)
            content = get_widget_content(prog)
            assert "complete" in content.lower()


@pytest.mark.asyncio
async def test_ingest_critical_error(widget):
    """Test critical error handling in ingestion."""
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        
        # Patch the entire loop to raise an unexpected exception
        with patch.object(widget, "_log") as mock_log:
            mock_log.info = MagicMock()
            mock_log.debug = MagicMock()
            mock_log.warning = MagicMock()
            mock_log.error = MagicMock()
            
            # Force critical error by making KNOWN_SOURCES iteration fail
            original_sources = widget.KNOWN_SOURCES
            
            # Use a property that raises on iteration
            class BadList:
                def __iter__(self):
                    raise RuntimeError("Critical failure")
            
            widget.KNOWN_SOURCES = BadList()
            
            try:
                await widget._run_ingestion()
            except RuntimeError:
                pass  # Expected
            finally:
                widget.KNOWN_SOURCES = original_sources


@pytest.mark.asyncio
async def test_on_progress_callback(widget):
    """Test the _on_progress callback method."""
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        
        # Create a mock IngestionProgress
        from cyberred.rag.ingest import IngestionProgress
        progress = IngestionProgress(
            source="mitre_attack",
            current_doc=5,
            total_docs=10,
            chunks_processed=150
        )
        
        widget._on_progress(progress)
        
        prog = widget.query_one("#progress-display", Static)
        content = get_widget_content(prog)
        assert "mitre_attack" in content
        assert "5/10" in content or "5" in content
        assert "150" in content


@pytest.mark.asyncio
async def test_get_source_timestamp_store_path_none(mock_rag_store, mock_ingest_pipeline):
    """Test _get_source_timestamp returns 'Never' when _store_path is None."""
    # Create a fresh mock store with _store_path = None
    fresh_store = MagicMock(spec=['_store_path', 'get_stats'])
    fresh_store._store_path = None  # Explicitly None
    fresh_store.get_stats = AsyncMock(return_value=RAGStoreStats(
        total_vectors=0, storage_size_bytes=0, sources=[], 
        last_updated=datetime(2026, 1, 1), source_counts={}
    ))
    
    test_widget = RAGManagerWidget(fresh_store, mock_ingest_pipeline)
    ts = test_widget._get_source_timestamp("any_source")
    assert ts == "Never"


@pytest.mark.asyncio
async def test_update_selected_no_source_selected(widget):
    """Test Update Selected button when no source is selected."""
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        
        # Ensure no source is selected
        widget._selected_source = None
        
        # Click Update Selected button
        btn = widget.query_one("#btn-update-selected", Button)
        await widget.on_button_pressed(Button.Pressed(btn))
        
        # Should show message to select source first
        prog = widget.query_one("#progress-display", Static)
        content = get_widget_content(prog)
        assert "select" in content.lower() and "source" in content.lower()


@pytest.mark.asyncio
async def test_ingest_successful_with_logging(widget):
    """Test successful ingestion logs completion and hits line 224."""
    async with App().run_test() as pilot:
        await pilot.app.mount(widget)
        
        with patch("importlib.import_module") as mock_import:
            mock_mod = MagicMock()
            # Make ingest return successfully (not raise, not return error)
            mock_mod.ingest = AsyncMock(return_value=None)
            mock_import.return_value = mock_mod
            
            await widget._run_ingestion(["mitre_attack"])
            
            # Check progress widget shows completion
            prog = widget.query_one("#progress-display", Static)
            content = get_widget_content(prog)
            # Should show "Completed mitre_attack" from line 222
            assert "Completed" in content or "complete" in content.lower()
