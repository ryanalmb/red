"""RAG Management Widget for TUI."""
from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, List, Optional
from datetime import datetime

import structlog
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, DataTable, Static, ProgressBar

if TYPE_CHECKING:
    from cyberred.rag.store import RAGStore
    from cyberred.rag.ingest import RAGIngestPipeline
    from cyberred.rag.models import RAGStoreStats
from cyberred.rag.ingest import IngestionProgress, IngestionStats

log = structlog.get_logger()


class RAGManagerWidget(Static):
    """RAG Management Widget for TUI (FR81, FR85)."""
    
    # Reactive properties for automatic UI updates
    total_vectors = reactive(0)
    storage_size = reactive(0)
    is_updating = reactive(False)
    
    # Known RAG sources - must match actual module names in cyberred.rag.sources
    KNOWN_SOURCES = [
        "mitre_attack",
        "atomic_red",
        "hacktricks",
        "payloads",
        "lolbas",
    ]
    
    def __init__(self, rag_store: RAGStore, ingest_pipeline: RAGIngestPipeline) -> None:
        super().__init__()
        self._store = rag_store
        self._pipeline = ingest_pipeline
        self._update_task: Optional[asyncio.Task] = None
        self._selected_source: Optional[str] = None
        self._log = log.bind(widget="rag_manager")
    
    def compose(self) -> ComposeResult:
        with Container(id="rag-manager"):
            yield Static("RAG KNOWLEDGE BASE", id="rag-title")
            yield Static("Loading stats...", id="corpus-stats")
            
            # Setup DataTable
            table = DataTable(id="source-table")
            table.cursor_type = "row"
            table.add_columns("Source", "Chunks", "Last Updated", "Status")
            yield table
            
            # Story 11.5: Enhanced progress display with progress bar
            with Vertical(id="progress-container"):
                yield Static("Ready", id="progress-display")
                progress_bar = ProgressBar(id="progress-bar", total=100, show_eta=False)
                progress_bar.display = False  # Hidden until update starts
                yield progress_bar
                yield Static("", id="source-progress")  # Per-source progress
            
            with Horizontal(id="rag-buttons"):
                yield Button("Update All", id="btn-update-all", variant="primary")
                yield Button("Update Selected", id="btn-update-selected")
                yield Button("Cancel", id="btn-cancel", disabled=True)
                yield Button("Close", id="btn-close")

    def on_mount(self) -> None:
        """Load stats when widget is mounted."""
        # We start a background task to refresh stats
        # Using self.call_after_refresh might be better but async is needed
        asyncio.create_task(self.refresh_stats())

    async def refresh_stats(self) -> None:
        """Fetch and display current RAG stats."""
        try:
            stats = await self._store.get_stats()
            
            self.total_vectors = stats.total_vectors
            self.storage_size = stats.storage_size_bytes
            
            # Update corpus stats display
            stats_widget = self.query_one("#corpus-stats", Static)
            stats_widget.update(
                f"Total Vectors: {stats.total_vectors:,}\n"
                f"Storage Size: {self._format_size(stats.storage_size_bytes)}\n"
                f"Sources: {len(stats.sources)}"
            )
            
            # Update source table
            table = self.query_one("#source-table", DataTable)
            table.clear()
            
            for source in stats.sources:
                count = stats.source_counts.get(source, 0)
                last_updated = self._get_source_timestamp(source)
                # We can deduce status roughly
                table.add_row(source, f"{count:,}", last_updated, "✓ Ready", key=source)
                
        except Exception as e:
            stats_widget = self.query_one("#corpus-stats", Static)
            stats_widget.update(f"Error loading stats: {str(e)}")

    def _format_size(self, size_bytes: int) -> str:
        """Format bytes as human-readable string."""
        if size_bytes == 0:
            return "0 B"
        
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def _get_source_timestamp(self, source: str) -> str:
        """Get last update timestamp for a source.
        
        Stats files are stored in the parent directory of the RAGStore db_path,
        matching the logic in RAGIngestPipeline._get_stats_path.
        """
        try:
            # Use db_path property (now available on RAGStore)
            if hasattr(self._store, "db_path"):
                base_path = self._store.db_path.parent
            else:
                # Fallback to _store_path for backwards compatibility
                store_path = getattr(self._store, "_store_path", None)
                if store_path:
                    base_path = store_path.parent
                else:
                    return "Never"
            
            stats_file = base_path / f".rag_stats_{source}.json"
            if stats_file.exists():
                data = json.loads(stats_file.read_text())
                stats = IngestionStats.from_dict(data)
                return stats.last_updated.strftime("%Y-%m-%d %H:%M")
        except Exception as e:
            self._log.debug("failed_to_read_source_timestamp", source=source, error=str(e))
        return "Never"

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle source row selection for selective update."""
        self._selected_source = event.row_key.value

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        btn_id = event.button.id
        if btn_id == "btn-update-all":
            self._update_task = asyncio.create_task(self._run_ingestion())
        elif btn_id == "btn-update-selected":
            if self._selected_source:
                self._update_task = asyncio.create_task(self._run_ingestion(sources=[self._selected_source]))
            else:
                progress = self.query_one("#progress-display", Static)
                progress.update("Please select a source first.")
        elif btn_id == "btn-cancel":
            if self._update_task:
                self._update_task.cancel()
        elif btn_id == "btn-close":
            # If in a modal, calling app methods or dismissing
            # Getting the screen that contains this widget
            if self.screen:
                self.screen.dismiss()
            else:
                self.remove()

    async def _run_ingestion(self, sources: Optional[List[str]] = None) -> None:
        """Run ingestion with progress updates.
        
        Story 11.5: Enhanced with real-time progress bar and per-source tracking.
        """
        import importlib
        
        self.is_updating = True
        cancel_btn = self.query_one("#btn-cancel", Button)
        update_all_btn = self.query_one("#btn-update-all", Button)
        update_sel_btn = self.query_one("#btn-update-selected", Button)
        progress_widget = self.query_one("#progress-display", Static)
        progress_bar = self.query_one("#progress-bar", ProgressBar)
        source_progress = self.query_one("#source-progress", Static)
        
        cancel_btn.disabled = False
        update_all_btn.disabled = True
        update_sel_btn.disabled = True
        
        # Use class constant for sources, validate against allowlist
        targets = sources if sources else self.KNOWN_SOURCES
        
        try:
            total_sources = len(targets)
            
            # Story 11.5: Show progress bar during update
            progress_bar.display = True
            progress_bar.update(total=total_sources * 100, progress=0)
            
            self._log.info("ingestion_started", sources=targets)
            errors = []
            completed = []
            
            for idx, source_name in enumerate(targets):
                # Sanitize and validate against allowlist (security)
                source_name = source_name.replace("-", "_")
                
                if source_name not in self.KNOWN_SOURCES:
                    self._log.warning("unknown_source_skipped", source=source_name)
                    continue
                
                # Story 11.5: Update per-source progress
                source_progress.update(f"[{idx + 1}/{total_sources}] {source_name}")
                progress_bar.update(progress=idx * 100)
                
                try:
                    progress_widget.update(f"Loading source: {source_name}...")
                    self._log.debug("loading_source", source=source_name)
                    
                    # Dynamically import source module
                    module = importlib.import_module(f"cyberred.rag.sources.{source_name}")
                    if not hasattr(module, "ingest"):
                        msg = f"Skipping {source_name}: No ingest() method found."
                        progress_widget.update(msg)
                        self._log.warning("source_missing_ingest", source=source_name)
                        continue
                    
                    # Update progress bar to 50% for this source (loading done)
                    progress_bar.update(progress=idx * 100 + 50)
                    progress_widget.update(f"Ingesting {source_name}...")
                    
                    await module.ingest(
                        store=self._store,
                        embeddings=self._pipeline._embeddings,
                        incremental=True
                    )
                    
                    # Update progress bar to 100% for this source
                    progress_bar.update(progress=(idx + 1) * 100)
                    progress_widget.update(f"Completed {source_name}.")
                    completed.append(source_name)
                    self._log.info("source_ingestion_complete", source=source_name)
                    
                except ImportError as e:
                    # Log but allow skipping if source module doesn't exist yet
                    self._log.warning("source_import_error", source=source_name, error=str(e))
                    progress_bar.update(progress=(idx + 1) * 100)  # Move progress forward
                except Exception as e:
                    msg = f"Error ingesting {source_name}: {e}"
                    progress_widget.update(msg)
                    errors.append(msg)
                    self._log.error("source_ingestion_error", source=source_name, error=str(e))
                    progress_bar.update(progress=(idx + 1) * 100)  # Move progress forward
            
            if errors:
                progress_widget.update(f"Completed with {len(errors)} errors. Last: {errors[-1]}")
                self._log.warning("ingestion_completed_with_errors", 
                                  completed=completed, error_count=len(errors))
            else:
                progress_widget.update("All updates complete.")
                self._log.info("ingestion_completed", completed=completed)

        except asyncio.CancelledError:
            progress_widget.update("Update cancelled.")
            self._log.info("ingestion_cancelled")
            raise  # Re-raise to properly handle cancellation
        except Exception as e:
            progress_widget.update(f"Critical Error: {e}")
            self._log.error("ingestion_critical_error", error=str(e))
        finally:
            self.is_updating = False
            cancel_btn.disabled = True
            update_all_btn.disabled = False
            update_sel_btn.disabled = False
            # Story 11.5: Hide progress bar and clear source progress
            progress_bar.display = False
            source_progress.update("")
            await self.refresh_stats()

    def _on_progress(self, progress: IngestionProgress) -> None:
        """Handle ingestion progress updates (callback for pipeline)."""
        progress_widget = self.query_one("#progress-display", Static)
        progress_widget.update(
            f"Updating {progress.source}... "
            f"({progress.current_doc}/{progress.total_docs} docs, "
            f"{progress.chunks_processed:,} chunks)"
        )
