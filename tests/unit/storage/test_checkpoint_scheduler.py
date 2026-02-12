"""Unit tests for CheckpointScheduler - Story 13.3 AC#2.

Tests for automatic checkpoint triggering based on:
- Time interval (60s default)
- Major state changes (PAUSED, STOPPED, critical finding)

TDD RED PHASE: All tests should FAIL until implementation exists.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# These imports will FAIL until implementation exists
# from cyberred.storage.checkpoint_scheduler import (
#     CheckpointScheduler,
#     CheckpointTrigger,
#     should_trigger_checkpoint,
# )


class TestCheckpointSchedulerInit:
    """Tests for CheckpointScheduler initialization."""

    @pytest.mark.asyncio
    async def test_scheduler_init_with_default_interval(self) -> None:
        """
        GIVEN a CheckpointScheduler is created with default parameters
        WHEN initialized with an AsyncCheckpointQueue
        THEN interval_seconds defaults to 60
        """
        # Import will fail until implementation exists
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        from pathlib import Path
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        
        scheduler = CheckpointScheduler(queue=queue)
        
        assert scheduler._interval == 60

    @pytest.mark.asyncio
    async def test_scheduler_init_with_custom_interval(self) -> None:
        """
        GIVEN a CheckpointScheduler is created with custom interval
        WHEN interval_seconds=30 is specified
        THEN scheduler uses 30 second interval
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        from pathlib import Path
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        
        scheduler = CheckpointScheduler(queue=queue, interval_seconds=30)
        
        assert scheduler._interval == 30

    @pytest.mark.asyncio
    async def test_scheduler_init_timer_not_started(self) -> None:
        """
        GIVEN a CheckpointScheduler is created
        WHEN not yet started
        THEN timer task is None
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        from pathlib import Path
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        
        scheduler = CheckpointScheduler(queue=queue)
        
        assert scheduler._timer_task is None


class TestCheckpointSchedulerStartStop:
    """Tests for scheduler start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_begins_background_timer(self) -> None:
        """
        GIVEN a CheckpointScheduler instance
        WHEN start() is called
        THEN background timer task is created
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        from pathlib import Path
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        scheduler = CheckpointScheduler(queue=queue, interval_seconds=1)
        
        await scheduler.start()
        
        try:
            assert scheduler._timer_task is not None
            assert not scheduler._timer_task.done()
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_timer_gracefully(self) -> None:
        """
        GIVEN a running CheckpointScheduler
        WHEN stop() is called
        THEN timer task is cancelled without error
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        from pathlib import Path
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        scheduler = CheckpointScheduler(queue=queue, interval_seconds=1)
        
        await scheduler.start()
        await scheduler.stop()
        
        assert scheduler._timer_task is None or scheduler._timer_task.cancelled()

    @pytest.mark.asyncio
    async def test_stop_idempotent_when_not_started(self) -> None:
        """
        GIVEN a CheckpointScheduler that was never started
        WHEN stop() is called
        THEN no error is raised
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        from pathlib import Path
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        scheduler = CheckpointScheduler(queue=queue)
        
        # Should not raise
        await scheduler.stop()


class TestCheckpointSchedulerInterval:
    """Tests for automatic interval-based checkpointing."""

    @pytest.mark.asyncio
    async def test_checkpoint_triggered_after_interval(self) -> None:
        """
        GIVEN a running CheckpointScheduler with 0.1s interval
        WHEN interval elapses
        THEN checkpoint is enqueued
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        from pathlib import Path
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        queue.enqueue = AsyncMock()  # Mock enqueue to track calls
        
        scheduler = CheckpointScheduler(queue=queue, interval_seconds=0.1)
        scheduler.set_engagement_context(
            engagement_id="test-eng-1",
            agents=[],
            findings=[],
            config={},
        )
        
        await scheduler.start()
        
        try:
            # Wait for interval + buffer
            await asyncio.sleep(0.15)
            
            # Verify checkpoint was enqueued
            assert queue.enqueue.called
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_interval_reset_after_manual_trigger(self) -> None:
        """
        GIVEN a running CheckpointScheduler
        WHEN trigger_now() is called
        THEN interval timer resets
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        from pathlib import Path
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        queue.enqueue = AsyncMock()
        
        scheduler = CheckpointScheduler(queue=queue, interval_seconds=0.2)
        scheduler.set_engagement_context(
            engagement_id="test-eng-1",
            agents=[],
            findings=[],
            config={},
        )
        
        await scheduler.start()
        
        try:
            # Wait half interval
            await asyncio.sleep(0.1)
            
            # Manual trigger resets interval
            await scheduler.trigger_now()
            
            # Wait another half interval (total 0.2s from start but only 0.1s from trigger)
            await asyncio.sleep(0.1)
            
            # Should have exactly 1 call (from trigger_now), not 2
            assert queue.enqueue.call_count == 1
        finally:
            await scheduler.stop()


class TestCheckpointTriggerNow:
    """Tests for manual checkpoint triggering."""

    @pytest.mark.asyncio
    async def test_trigger_now_enqueues_checkpoint(self) -> None:
        """
        GIVEN a CheckpointScheduler with engagement context
        WHEN trigger_now() is called
        THEN checkpoint is immediately enqueued
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        from pathlib import Path
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        queue.enqueue = AsyncMock()
        
        scheduler = CheckpointScheduler(queue=queue)
        scheduler.set_engagement_context(
            engagement_id="test-eng-1",
            agents=[],
            findings=[],
            config={"key": "value"},
        )
        
        await scheduler.trigger_now()
        
        queue.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_now_updates_last_checkpoint_time(self) -> None:
        """
        GIVEN a CheckpointScheduler
        WHEN trigger_now() is called
        THEN _last_checkpoint timestamp is updated
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        from pathlib import Path
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        queue.enqueue = AsyncMock()
        
        scheduler = CheckpointScheduler(queue=queue)
        scheduler.set_engagement_context(
            engagement_id="test-eng-1",
            agents=[],
            findings=[],
            config={},
        )
        
        before = scheduler._last_checkpoint
        await scheduler.trigger_now()
        after = scheduler._last_checkpoint
        
        assert after > before


class TestCheckpointTriggerEnum:
    """Tests for CheckpointTrigger enum."""

    def test_trigger_enum_has_interval(self) -> None:
        """
        GIVEN CheckpointTrigger enum
        THEN INTERVAL value exists
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointTrigger
        
        assert CheckpointTrigger.INTERVAL is not None

    def test_trigger_enum_has_state_change(self) -> None:
        """
        GIVEN CheckpointTrigger enum
        THEN STATE_CHANGE value exists
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointTrigger
        
        assert CheckpointTrigger.STATE_CHANGE is not None

    def test_trigger_enum_has_critical_finding(self) -> None:
        """
        GIVEN CheckpointTrigger enum
        THEN CRITICAL_FINDING value exists
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointTrigger
        
        assert CheckpointTrigger.CRITICAL_FINDING is not None

    def test_trigger_enum_has_manual(self) -> None:
        """
        GIVEN CheckpointTrigger enum
        THEN MANUAL value exists
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointTrigger
        
        assert CheckpointTrigger.MANUAL is not None


class TestShouldTriggerCheckpoint:
    """Tests for state change trigger logic."""

    def test_should_trigger_on_paused_state(self) -> None:
        """
        GIVEN engagement state changes to PAUSED
        WHEN should_trigger_checkpoint() is called
        THEN returns True
        """
        from cyberred.storage.checkpoint_scheduler import should_trigger_checkpoint
        
        result = should_trigger_checkpoint(
            event_type="state_change",
            event_data={"new_state": "PAUSED"},
        )
        
        assert result is True

    def test_should_trigger_on_stopped_state(self) -> None:
        """
        GIVEN engagement state changes to STOPPED
        WHEN should_trigger_checkpoint() is called
        THEN returns True
        """
        from cyberred.storage.checkpoint_scheduler import should_trigger_checkpoint
        
        result = should_trigger_checkpoint(
            event_type="state_change",
            event_data={"new_state": "STOPPED"},
        )
        
        assert result is True

    def test_should_trigger_on_critical_finding(self) -> None:
        """
        GIVEN a critical severity finding is discovered
        WHEN should_trigger_checkpoint() is called
        THEN returns True
        """
        from cyberred.storage.checkpoint_scheduler import should_trigger_checkpoint
        
        result = should_trigger_checkpoint(
            event_type="finding",
            event_data={"severity": "critical"},
        )
        
        assert result is True

    def test_should_not_trigger_on_info_finding(self) -> None:
        """
        GIVEN an info severity finding is discovered
        WHEN should_trigger_checkpoint() is called
        THEN returns False (minor event)
        """
        from cyberred.storage.checkpoint_scheduler import should_trigger_checkpoint
        
        result = should_trigger_checkpoint(
            event_type="finding",
            event_data={"severity": "info"},
        )
        
        assert result is False

    def test_should_not_trigger_on_agent_heartbeat(self) -> None:
        """
        GIVEN an agent heartbeat event
        WHEN should_trigger_checkpoint() is called
        THEN returns False (minor event)
        """
        from cyberred.storage.checkpoint_scheduler import should_trigger_checkpoint
        
        result = should_trigger_checkpoint(
            event_type="heartbeat",
            event_data={"agent_id": "agent-1"},
        )
        
        assert result is False

    def test_should_not_trigger_on_running_state(self) -> None:
        """
        GIVEN engagement state changes to RUNNING
        WHEN should_trigger_checkpoint() is called
        THEN returns False (not a major state change)
        """
        from cyberred.storage.checkpoint_scheduler import should_trigger_checkpoint
        
        result = should_trigger_checkpoint(
            event_type="state_change",
            event_data={"new_state": "RUNNING"},
        )
        
        assert result is False


class TestSchedulerScopePath:
    """Tests for scope_path in scheduler context."""

    @pytest.mark.asyncio
    async def test_set_engagement_context_with_scope_path(self) -> None:
        """
        GIVEN a CheckpointScheduler
        WHEN set_engagement_context is called with scope_path
        THEN scope_path is stored in context
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        from pathlib import Path
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        
        scheduler = CheckpointScheduler(queue=queue)
        scheduler.set_engagement_context(
            engagement_id="test-eng-1",
            agents=[],
            findings=[],
            config={},
            scope_path=Path("/tmp/scope.yaml"),
        )
        
        assert scheduler._scope_path == Path("/tmp/scope.yaml")

    @pytest.mark.asyncio
    async def test_trigger_now_passes_scope_path_to_queue(self) -> None:
        """
        GIVEN a scheduler with scope_path set
        WHEN trigger_now() is called
        THEN scope_path is passed to queue.enqueue()
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        from pathlib import Path
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        queue.enqueue = AsyncMock()
        
        scheduler = CheckpointScheduler(queue=queue)
        scope_path = Path("/tmp/my-scope.yaml")
        scheduler.set_engagement_context(
            engagement_id="test-eng-1",
            scope_path=scope_path,
        )
        
        await scheduler.trigger_now()
        
        # Verify scope_path was passed
        queue.enqueue.assert_called_once()
        call_kwargs = queue.enqueue.call_args.kwargs
        assert call_kwargs.get("scope_path") == scope_path

    @pytest.mark.asyncio
    async def test_default_debounce_is_5_seconds(self) -> None:
        """
        GIVEN a CheckpointScheduler with default parameters
        THEN debounce_seconds defaults to 5.0 as per story spec
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        from pathlib import Path
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        
        scheduler = CheckpointScheduler(queue=queue)
        
        assert scheduler._debounce == 5.0


class TestCheckpointDebounce:
    """Tests for debounce logic to prevent rapid-fire checkpoints."""

    @pytest.mark.asyncio
    async def test_debounce_coalesces_rapid_triggers(self) -> None:
        """
        GIVEN multiple rapid trigger_now() calls within debounce window
        WHEN triggers occur within 5s (default debounce)
        THEN only one checkpoint is actually written
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        from pathlib import Path
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        queue.enqueue = AsyncMock()
        
        scheduler = CheckpointScheduler(queue=queue, debounce_seconds=0.1)
        scheduler.set_engagement_context(
            engagement_id="test-eng-1",
            agents=[],
            findings=[],
            config={},
        )
        
        # Rapid fire triggers
        await scheduler.trigger_now()
        await scheduler.trigger_now()
        await scheduler.trigger_now()
        
        # Should debounce to single enqueue
        assert queue.enqueue.call_count == 1

    @pytest.mark.asyncio
    async def test_debounce_allows_trigger_after_window(self) -> None:
        """
        GIVEN a trigger was fired
        WHEN debounce window (0.1s for test) elapses
        THEN next trigger is allowed
        """
        from cyberred.storage.checkpoint_scheduler import CheckpointScheduler
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        from pathlib import Path
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        queue.enqueue = AsyncMock()
        
        scheduler = CheckpointScheduler(queue=queue, debounce_seconds=0.05)
        scheduler.set_engagement_context(
            engagement_id="test-eng-1",
            agents=[],
            findings=[],
            config={},
        )
        
        await scheduler.trigger_now()
        
        # Wait for debounce window
        await asyncio.sleep(0.06)
        
        await scheduler.trigger_now()
        
        # Should have 2 calls
        assert queue.enqueue.call_count == 2
