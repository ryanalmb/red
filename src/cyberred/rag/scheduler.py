"""RAG Scheduler Module.

Handles automatic scheduled refreshing of RAG knowledge bases (Story 6.12).
"""
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

import structlog
from cyberred.core.config import RAGConfig, get_settings

log = structlog.get_logger()

@dataclass
class RAGSchedulerState:
    """Persistent state for the RAG scheduler."""
    last_refresh: Optional[datetime]
    last_status: str  # "success", "partial", "failed", "none"
    next_scheduled: Optional[datetime]

class RAGScheduler:
    """Schedules and executes background RAG refresh tasks."""

    def __init__(self, config: RAGConfig):
        self.config = config
        self._shutdown_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._refresh_lock = asyncio.Lock()
        
        # Determine strict state file path
        # In actual app, this should be config.storage.base_path / "rag" / ".scheduler_state.json"
        # Since we only get RAGConfig here, we'll infer from store_path's parent directory
        # effectively ~/.cyber-red/rag/.scheduler_state.json
        self._state_file = Path(config.store_path).parent / ".scheduler_state.json"
        
        self._state = self._load_state()

    @property
    def is_running(self) -> bool:
        """Return True if the scheduler loop is running."""
        return self._task is not None and not self._task.done()

    @property
    def state(self) -> RAGSchedulerState:
        """Return the current scheduler state."""
        return self._state

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self.is_running:
            return

        schedule = self.config.update_schedule
        if schedule == "manual":
            log.info("rag_scheduler_manual_mode", message="Scheduler not started (manual mode)")
            return

        self._shutdown_event.clear()
        self._task = asyncio.create_task(self._scheduler_loop())
        log.info("rag_scheduler_started", schedule=schedule)

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        if not self.is_running:
            return

        self._shutdown_event.set()
        if self._task:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        log.info("rag_scheduler_stopped")

    async def trigger_now(self) -> None:
        """Manually trigger a refresh immediately."""
        log.info("rag_refresh_manual_trigger")
        # Run in background to not block caller
        asyncio.create_task(self._run_refresh())

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while not self._shutdown_event.is_set():
            # Get latest config for hot reload support
            rag_config = get_settings().rag
            next_run = self._calculate_next_run(rag_config.update_schedule)
            
            if not next_run:
                log.warning("rag_scheduler_no_next_run", schedule=rag_config.update_schedule)
                break

            # Update next_scheduled in state just for visibility
            self._state.next_scheduled = next_run
            self._save_state(self._state)

            now = datetime.now()
            sleep_seconds = (next_run - now).total_seconds()
            
            log.info("rag_scheduler_sleeping", sleep_seconds=sleep_seconds, next_run=next_run)

            try:
                # Wait until next run or shutdown
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=max(0, sleep_seconds)
                )
                # If we get here, shutdown event was set
                break
            except asyncio.TimeoutError:
                # Timeout means it's time to run!
                pass

            if not self._shutdown_event.is_set():
                await self._run_refresh()

    async def _run_refresh(self) -> None:
        """Execute the RAG refresh process."""
        if self._refresh_lock.locked():
            log.warning("rag_refresh_skipped_locked")
            return

        async with self._refresh_lock:
            log.info("rag_refresh_started")
            
            # Lazy load components to avoid circular imports and startup costs
            # Using global settings via class instantiation which is standard in this project
            if not hasattr(self, "_store") or self._store is None:
                from cyberred.rag.store import RAGStore
                from cyberred.rag.embeddings import RAGEmbeddings
                self._store = RAGStore()
                self._embeddings = RAGEmbeddings()

            import importlib
            base_package = "cyberred.rag.sources"
            # Core sources defined in story
            sources_to_refresh = ["mitre_attack", "atomic_red", "hacktricks"]
            
            overall_success = True
            refresh_stats = {}

            for source_name in sources_to_refresh:
                try:
                    log.info("rag_source_refresh_started", source=source_name)
                    module = importlib.import_module(f"{base_package}.{source_name}")
                    
                    if hasattr(module, "ingest"):
                        stats = await module.ingest(
                            store=self._store,
                            embeddings=self._embeddings,
                            incremental=True
                        )
                        refresh_stats[source_name] = "success"
                        log.info("rag_source_refresh_complete", source=source_name, chunks=stats.chunk_count)
                    else:
                        log.warning("rag_source_no_ingest_method", source=source_name)
                        refresh_stats[source_name] = "skipped"
                        
                except Exception as e:
                    log.error("rag_source_refresh_failed", source=source_name, error=str(e))
                    refresh_stats[source_name] = "failed"
                    overall_success = False
                    # Continue to next source (AC 4)

            # Update state
            self._state.last_refresh = datetime.now()
            self._state.last_status = "success" if overall_success else "partial_failure"
            if all(s == "failed" for s in refresh_stats.values()) and refresh_stats:
                 self._state.last_status = "failed"
                 
            self._save_state(self._state)
            
            log.info(
                "rag_refresh_completed", 
                status=self._state.last_status,
                details=refresh_stats
            )

    def _calculate_next_run(self, schedule: str) -> Optional[datetime]:
        """Calculate the next run time based on schedule type."""
        now = datetime.now()
        
        if schedule == "weekly":
            # Sunday 3 AM
            # Weekday: Monday is 0, Sunday is 6
            days_ahead = 6 - now.weekday()
            if days_ahead <= 0: # Target day already happened this week
                days_ahead += 7
                
            # If today is Sunday, check if 3AM passed
            if now.weekday() == 6:
                target_today = now.replace(hour=3, minute=0, second=0, microsecond=0)
                if now < target_today:
                    return target_today
                # If passed, run next Sunday
                days_ahead = 7
            
            next_run = (now + timedelta(days=days_ahead)).replace(hour=3, minute=0, second=0, microsecond=0)
            return next_run

        elif schedule == "daily":
            # Daily 3 AM
            target_today = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if now < target_today:
                return target_today
            return target_today + timedelta(days=1)
            
        elif schedule == "manual":
            return None
        
        log.warning("unknown_schedule_type", schedule=schedule)
        return None

    def _load_state(self) -> RAGSchedulerState:
        """Load state from file."""
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                last_refresh = datetime.fromisoformat(data["last_refresh"]) if data.get("last_refresh") else None
                next_scheduled = datetime.fromisoformat(data["next_scheduled"]) if data.get("next_scheduled") else None
                return RAGSchedulerState(
                    last_refresh=last_refresh,
                    last_status=data.get("last_status", "none"),
                    next_scheduled=next_scheduled
                )
            except Exception as e:
                log.warning("rag_scheduler_state_load_failed", error=str(e))
        
        return RAGSchedulerState(last_refresh=None, last_status="none", next_scheduled=None)

    def _save_state(self, state: RAGSchedulerState) -> None:
        """Save state to file."""
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            data = asdict(state)
            # Convert datetimes to ISO strings
            if data["last_refresh"]:
                data["last_refresh"] = data["last_refresh"].isoformat()
            if data["next_scheduled"]:
                data["next_scheduled"] = data["next_scheduled"].isoformat()
                
            self._state_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            log.error("rag_scheduler_state_save_failed", error=str(e))
