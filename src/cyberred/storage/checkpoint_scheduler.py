"""Checkpoint Scheduler for automatic checkpoint triggering.

Provides automatic checkpoint scheduling based on:
- Time intervals (default 60 seconds)
- State change events (PAUSED, STOPPED)
- Critical findings

Key Features:
- Configurable interval
- Debounce to prevent rapid-fire checkpoints
- State change trigger detection
- Manual trigger support

Usage:
    from cyberred.storage import CheckpointScheduler, AsyncCheckpointQueue
    
    scheduler = CheckpointScheduler(queue=queue, interval_seconds=60)
    scheduler.set_engagement_context(engagement_id, agents, findings, config)
    
    await scheduler.start()
    await scheduler.trigger_now()  # Manual trigger
    await scheduler.stop()
"""

import asyncio
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

import structlog

from cyberred.storage.checkpoint import AgentState, Finding
from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue

log = structlog.get_logger()


class CheckpointTrigger(Enum):
    """Types of checkpoint triggers."""
    INTERVAL = auto()
    STATE_CHANGE = auto()
    CRITICAL_FINDING = auto()
    MANUAL = auto()


# States that trigger checkpoint
_CHECKPOINT_TRIGGER_STATES = frozenset({"PAUSED", "STOPPED", "COMPLETED"})

# Severities that trigger checkpoint
_CHECKPOINT_TRIGGER_SEVERITIES = frozenset({"critical"})


def should_trigger_checkpoint(
    event_type: str,
    event_data: dict[str, Any],
) -> bool:
    """Determine if an event should trigger a checkpoint.
    
    Args:
        event_type: Type of event (state_change, finding, heartbeat, etc.)
        event_data: Event data dict.
        
    Returns:
        True if checkpoint should be triggered.
    """
    if event_type == "state_change":
        new_state = event_data.get("new_state", "")
        return new_state in _CHECKPOINT_TRIGGER_STATES
    
    if event_type == "finding":
        severity = event_data.get("severity", "").lower()
        return severity in _CHECKPOINT_TRIGGER_SEVERITIES
    
    # All other events (heartbeat, etc.) don't trigger checkpoint
    return False


class CheckpointScheduler:
    """Scheduler for automatic checkpoint triggering.
    
    Manages checkpoint timing based on intervals and state changes.
    Uses debounce to prevent excessive checkpoint writes.
    
    Attributes:
        _queue: AsyncCheckpointQueue for enqueuing checkpoints.
        _interval: Checkpoint interval in seconds.
        _debounce: Debounce window in seconds.
    """
    
    def __init__(
        self,
        queue: AsyncCheckpointQueue,
        interval_seconds: int = 60,
        debounce_seconds: float = 5.0,
    ) -> None:
        """Initialize CheckpointScheduler.
        
        Args:
            queue: AsyncCheckpointQueue for checkpoint writes.
            interval_seconds: Automatic checkpoint interval.
            debounce_seconds: Minimum time between checkpoints.
        """
        self._queue = queue
        self._interval = interval_seconds
        self._debounce = debounce_seconds
        self._timer_task: Optional[asyncio.Task[None]] = None
        self._last_checkpoint: datetime = datetime.min.replace(tzinfo=timezone.utc)
        self._running = False
        
        # Engagement context
        self._engagement_id: Optional[str] = None
        self._agents: list[AgentState] = []
        self._findings: list[Finding] = []
        self._config: dict[str, Any] = {}
        self._scope_path: Optional[Path] = None
    
    def set_engagement_context(
        self,
        engagement_id: str,
        agents: Optional[list[AgentState]] = None,
        findings: Optional[list[Finding]] = None,
        config: Optional[dict[str, Any]] = None,
        scope_path: Optional[Path] = None,
    ) -> None:
        """Set the current engagement context for checkpointing.
        
        Args:
            engagement_id: Current engagement ID.
            agents: Current agent states.
            findings: Current findings.
            config: Current config.
            scope_path: Path to scope file for hash validation.
        """
        self._engagement_id = engagement_id
        self._agents = agents or []
        self._findings = findings or []
        self._config = config or {}
        self._scope_path = scope_path
    
    async def start(self) -> None:
        """Start the checkpoint scheduler."""
        if self._running:
            return
        
        self._running = True
        self._timer_task = asyncio.create_task(self._timer_loop())
        log.debug("checkpoint_scheduler_started", interval=self._interval)
    
    async def stop(self) -> None:
        """Stop the checkpoint scheduler."""
        if not self._running:
            return
        
        self._running = False
        
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                pass
        
        self._timer_task = None
        log.debug("checkpoint_scheduler_stopped")
    
    async def trigger_now(self, trigger_type: CheckpointTrigger = CheckpointTrigger.MANUAL) -> None:
        """Trigger an immediate checkpoint if not debounced.
        
        Args:
            trigger_type: Type of trigger for logging.
        """
        now = datetime.now(timezone.utc)
        
        # Check debounce
        elapsed = (now - self._last_checkpoint).total_seconds()
        if elapsed < self._debounce:
            log.debug(
                "checkpoint_debounced",
                elapsed=elapsed,
                debounce=self._debounce,
            )
            return
        
        if not self._engagement_id:
            log.warning("checkpoint_trigger_no_engagement")
            return
        
        # Update last checkpoint time
        self._last_checkpoint = now
        
        # Enqueue checkpoint
        await self._queue.enqueue(
            engagement_id=self._engagement_id,
            agents=self._agents,
            findings=self._findings,
            config=self._config,
            scope_path=self._scope_path,
        )
        
        log.debug(
            "checkpoint_triggered",
            trigger_type=trigger_type.name,
            engagement_id=self._engagement_id,
        )
    
    async def _timer_loop(self) -> None:
        """Background timer loop for interval-based checkpoints."""
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                
                if not self._running:
                    break
                
                await self.trigger_now(CheckpointTrigger.INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("checkpoint_timer_error", error=str(e))
