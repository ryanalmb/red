"""Async Checkpoint Queue for non-blocking checkpoint writes.

Provides an async queue that decouples checkpoint triggering from
checkpoint writing, ensuring the main thread is never blocked by I/O.

Key Features:
- Non-blocking enqueue (< 10ms)
- Background worker processing
- Write coalescing for same engagement_id
- Graceful overflow handling

Usage:
    from cyberred.storage import AsyncCheckpointQueue, CheckpointManager
    
    manager = CheckpointManager(base_path=Path("~/.cyber-red"))
    queue = AsyncCheckpointQueue(manager)
    
    await queue.start()
    await queue.enqueue("eng-1", agents, findings, config)
    await queue.flush()
    await queue.stop()
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import structlog

from cyberred.storage.checkpoint import (
    CheckpointManager,
    AgentState,
    Finding,
)

log = structlog.get_logger()


@dataclass
class CheckpointRequest:
    """Request to checkpoint an engagement."""
    engagement_id: str
    agents: list[AgentState]
    findings: list[Finding]
    config: dict[str, Any]
    scope_path: Optional[Path] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed: asyncio.Event = field(default_factory=asyncio.Event)


class AsyncCheckpointQueue:
    """Async queue for non-blocking checkpoint writes.
    
    Enqueue operations return immediately, with actual checkpoint
    writes processed by a background worker. Multiple writes for
    the same engagement_id are coalesced to the latest state.
    
    Attributes:
        _manager: CheckpointManager for actual write operations.
        _max_queue_size: Maximum pending requests before overflow.
    """
    
    def __init__(
        self,
        manager: CheckpointManager,
        max_queue_size: int = 10,
    ) -> None:
        """Initialize AsyncCheckpointQueue.
        
        Args:
            manager: CheckpointManager for writes.
            max_queue_size: Maximum queue size before overflow.
        """
        self._manager = manager
        self._max_queue_size = max_queue_size
        self._pending: dict[str, CheckpointRequest] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._running = False
        self._overflow_count = 0
        self._lock = asyncio.Lock()
        self._in_flight: dict[str, CheckpointRequest] = {}  # Currently being processed
    
    async def start(self) -> None:
        """Start the background worker."""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        log.debug("checkpoint_queue_started")
    
    async def stop(self) -> None:
        """Stop the queue and flush pending writes."""
        if not self._running:
            return
        
        self._running = False
        
        # Flush pending writes
        await self.flush()
        
        # Cancel worker task
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        self._worker_task = None
        log.debug("checkpoint_queue_stopped")
    
    async def enqueue(
        self,
        engagement_id: str,
        agents: Optional[list[AgentState]] = None,
        findings: Optional[list[Finding]] = None,
        config: Optional[dict[str, Any]] = None,
        scope_path: Optional[Path] = None,
    ) -> None:
        """Enqueue a checkpoint request (non-blocking).
        
        If the queue is not running, the request is silently dropped
        with a warning log.
        
        Args:
            engagement_id: Engagement to checkpoint.
            agents: Agent states to save.
            findings: Findings to save.
            config: Config dict to save.
            scope_path: Optional scope file path.
        """
        if not self._running:
            log.warning(
                "checkpoint_queue_enqueue_while_stopped",
                engagement_id=engagement_id,
            )
            return
        
        request = CheckpointRequest(
            engagement_id=engagement_id,
            agents=agents or [],
            findings=findings or [],
            config=config or {},
            scope_path=scope_path,
        )
        
        async with self._lock:
            # Check for overflow - coalescing means we count unique engagement_ids
            is_new = engagement_id not in self._pending
            
            if is_new and len(self._pending) >= self._max_queue_size:
                # Overflow - drop oldest
                self._overflow_count += 1
                oldest_key = next(iter(self._pending))
                del self._pending[oldest_key]
                log.warning(
                    "checkpoint_queue_overflow",
                    dropped_engagement=oldest_key,
                    overflow_count=self._overflow_count,
                )
            
            # Coalesce: newer request replaces older for same engagement
            self._pending[engagement_id] = request
            
            # Only queue if new engagement_id
            if is_new:
                await self._queue.put(engagement_id)
    
    async def flush(self) -> None:
        """Wait for all pending writes to complete."""
        # Collect all requests that need to complete
        async with self._lock:
            requests_to_wait = list(self._pending.values()) + list(self._in_flight.values())
        
        # Wait for all of them to complete
        for request in requests_to_wait:
            await request.completed.wait()
    
    async def _worker(self) -> None:
        """Background worker that processes checkpoint requests."""
        while self._running or not self._queue.empty():
            try:
                # Wait for next engagement_id
                try:
                    engagement_id = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=0.1,
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Get the latest request for this engagement (coalesced)
                async with self._lock:
                    request = self._pending.pop(engagement_id, None)
                    if request is not None:
                        self._in_flight[engagement_id] = request
                
                if request is None:
                    continue
                
                # Perform the actual save
                try:
                    await self._manager.save(
                        engagement_id=request.engagement_id,
                        scope_path=request.scope_path,
                        agents=request.agents,
                        findings=request.findings,
                        config=request.config,
                    )
                    log.debug(
                        "checkpoint_queue_write_complete",
                        engagement_id=engagement_id,
                    )
                except Exception as e:
                    log.error(
                        "checkpoint_queue_write_error",
                        engagement_id=engagement_id,
                        error=str(e),
                    )
                finally:
                    # Mark as completed and remove from in_flight
                    async with self._lock:
                        self._in_flight.pop(engagement_id, None)
                    request.completed.set()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("checkpoint_worker_error", error=str(e))
