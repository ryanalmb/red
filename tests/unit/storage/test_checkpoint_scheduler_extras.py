"""Extra unit tests for CheckpointScheduler edge cases - Story 13.3.

Tests for coverage of edge cases:
- Start when already running
- Stop when already stopped
- Trigger without engagement context
- Timer error handling
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cyberred.storage.checkpoint import CheckpointManager
from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
from cyberred.storage.checkpoint_scheduler import CheckpointScheduler, CheckpointTrigger


class TestCheckpointSchedulerEdgeCases:
    """Edge case tests for CheckpointScheduler."""

    @pytest.mark.asyncio
    async def test_start_when_already_running(self) -> None:
        """
        GIVEN a running CheckpointScheduler
        WHEN start() is called again
        THEN it returns early without creating duplicate timer
        """
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        scheduler = CheckpointScheduler(queue=queue, interval_seconds=60)
        
        await scheduler.start()
        original_task = scheduler._timer_task
        
        # Start again - should be idempotent
        await scheduler.start()
        
        try:
            assert scheduler._timer_task is original_task
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_when_already_stopped(self) -> None:
        """
        GIVEN a stopped CheckpointScheduler
        WHEN stop() is called again
        THEN it returns early without error
        """
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        scheduler = CheckpointScheduler(queue=queue)
        
        await scheduler.start()
        await scheduler.stop()
        
        # Stop again - should be idempotent
        await scheduler.stop()
        
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_trigger_now_without_engagement_context(self) -> None:
        """
        GIVEN a CheckpointScheduler without engagement context set
        WHEN trigger_now() is called
        THEN warning is logged and no checkpoint is enqueued
        """
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        queue.enqueue = AsyncMock()
        
        scheduler = CheckpointScheduler(queue=queue, debounce_seconds=0)
        # Don't call set_engagement_context
        
        await scheduler.trigger_now()
        
        # Enqueue should NOT be called
        queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_timer_loop_exits_when_stopped(self) -> None:
        """
        GIVEN a running CheckpointScheduler
        WHEN stop() is called during sleep
        THEN timer loop exits cleanly
        """
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        queue.enqueue = AsyncMock()
        
        scheduler = CheckpointScheduler(queue=queue, interval_seconds=10)
        scheduler.set_engagement_context("eng-1", [], [], {})
        
        await scheduler.start()
        
        # Give timer time to start sleeping
        await asyncio.sleep(0.01)
        
        # Stop should cancel timer cleanly
        await scheduler.stop()
        
        assert scheduler._timer_task is None or scheduler._timer_task.cancelled()

    @pytest.mark.asyncio
    async def test_timer_loop_handles_exception(self) -> None:
        """
        GIVEN a timer loop where trigger_now raises exception
        WHEN exception occurs
        THEN error is logged and loop continues
        """
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        
        scheduler = CheckpointScheduler(queue=queue, interval_seconds=0.05)
        scheduler.set_engagement_context("eng-1", [], [], {})
        
        # Make trigger_now raise an exception the first time
        original_trigger = scheduler.trigger_now
        call_count = 0
        
        async def error_trigger(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated trigger error")
            return await original_trigger(*args, **kwargs)
        
        scheduler.trigger_now = error_trigger
        
        await scheduler.start()
        
        try:
            # Wait for at least 2 intervals
            await asyncio.sleep(0.15)
            
            # Timer should have recovered after first error
            assert call_count >= 2
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_trigger_with_explicit_trigger_type(self) -> None:
        """
        GIVEN a CheckpointScheduler
        WHEN trigger_now() is called with explicit trigger type
        THEN checkpoint is enqueued with that trigger type logged
        """
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        queue.enqueue = AsyncMock()
        
        scheduler = CheckpointScheduler(queue=queue, debounce_seconds=0)
        scheduler.set_engagement_context("eng-1", [], [], {})
        
        await scheduler.trigger_now(CheckpointTrigger.STATE_CHANGE)
        
        queue.enqueue.assert_called_once()
