"""Unit tests for AsyncCheckpointQueue - Story 13.3 AC#5.

Tests for async write queue that prevents blocking main thread:
- Non-blocking enqueue
- Background worker processing
- Write coalescing for same engagement_id
- Queue overflow handling

TDD RED PHASE: All tests should FAIL until implementation exists.
"""

import asyncio
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAsyncCheckpointQueueInit:
    """Tests for AsyncCheckpointQueue initialization."""

    @pytest.mark.asyncio
    async def test_queue_init_with_default_max_size(self) -> None:
        """
        GIVEN AsyncCheckpointQueue is created with default parameters
        WHEN initialized with a CheckpointManager
        THEN max_queue_size defaults to 10
        """
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        
        assert queue._max_queue_size == 10

    @pytest.mark.asyncio
    async def test_queue_init_with_custom_max_size(self) -> None:
        """
        GIVEN AsyncCheckpointQueue is created with custom max size
        WHEN max_queue_size=5 is specified
        THEN queue uses 5 as max size
        """
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager, max_queue_size=5)
        
        assert queue._max_queue_size == 5

    @pytest.mark.asyncio
    async def test_queue_init_worker_not_started(self) -> None:
        """
        GIVEN AsyncCheckpointQueue is created
        WHEN not yet started
        THEN worker task is None
        """
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        
        assert queue._worker_task is None


class TestAsyncCheckpointQueueEnqueue:
    """Tests for non-blocking enqueue operation."""

    @pytest.mark.asyncio
    async def test_enqueue_returns_immediately(self) -> None:
        """
        GIVEN a running AsyncCheckpointQueue
        WHEN enqueue() is called
        THEN it returns in < 10ms (non-blocking)
        """
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        await queue.start()
        
        try:
            start = time.perf_counter()
            await queue.enqueue(
                engagement_id="test-eng-1",
                agents=[],
                findings=[],
                config={"key": "value"},
            )
            elapsed = time.perf_counter() - start
            
            # Must return in < 10ms
            assert elapsed < 0.010
        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_enqueue_does_not_block_caller(self) -> None:
        """
        GIVEN a running AsyncCheckpointQueue with slow manager
        WHEN enqueue() is called
        THEN caller is not blocked by checkpoint write
        """
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        # Mock save to be slow
        async def slow_save(*args, **kwargs):
            await asyncio.sleep(1.0)
            return Path("/tmp/fake.sqlite")
        manager.save = slow_save
        
        queue = AsyncCheckpointQueue(manager)
        await queue.start()
        
        try:
            start = time.perf_counter()
            await queue.enqueue(
                engagement_id="test-eng-1",
                agents=[],
                findings=[],
                config={},
            )
            elapsed = time.perf_counter() - start
            
            # Should return immediately, not wait for slow save
            assert elapsed < 0.050
        finally:
            await queue.stop()


class TestAsyncCheckpointQueueWorker:
    """Tests for background worker processing."""

    @pytest.mark.asyncio
    async def test_worker_processes_enqueued_items(self) -> None:
        """
        GIVEN a running AsyncCheckpointQueue
        WHEN items are enqueued
        THEN background worker calls manager.save()
        """
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        manager.save = AsyncMock(return_value=Path("/tmp/test.sqlite"))
        
        queue = AsyncCheckpointQueue(manager)
        await queue.start()
        
        try:
            await queue.enqueue(
                engagement_id="test-eng-1",
                agents=[],
                findings=[],
                config={},
            )
            
            # Wait for worker to process
            await asyncio.sleep(0.05)
            
            manager.save.assert_called()
        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_flush_waits_for_pending_writes(self) -> None:
        """
        GIVEN a queue with pending writes
        WHEN flush() is called
        THEN it waits until all writes complete
        """
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        save_called = asyncio.Event()
        
        async def tracked_save(*args, **kwargs):
            await asyncio.sleep(0.05)
            save_called.set()
            return Path("/tmp/test.sqlite")
        
        manager.save = tracked_save
        
        queue = AsyncCheckpointQueue(manager)
        await queue.start()
        
        try:
            await queue.enqueue(
                engagement_id="test-eng-1",
                agents=[],
                findings=[],
                config={},
            )
            
            # Flush should wait for save to complete
            await queue.flush()
            
            assert save_called.is_set()
        finally:
            await queue.stop()


class TestAsyncCheckpointQueueCoalescing:
    """Tests for write coalescing behavior."""

    @pytest.mark.asyncio
    async def test_coalesces_writes_for_same_engagement(self) -> None:
        """
        GIVEN multiple enqueue calls for same engagement_id
        WHEN processed before worker runs
        THEN only latest state is written (coalesced)
        """
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        
        save_calls = []
        async def tracking_save(engagement_id, **kwargs):
            save_calls.append((engagement_id, kwargs.get("config", {})))
            return Path("/tmp/test.sqlite")
        
        manager.save = tracking_save
        
        queue = AsyncCheckpointQueue(manager)
        await queue.start()
        
        try:
            # Enqueue multiple for same engagement
            await queue.enqueue("eng-1", [], [], {"version": 1})
            await queue.enqueue("eng-1", [], [], {"version": 2})
            await queue.enqueue("eng-1", [], [], {"version": 3})
            
            # Flush to process all
            await queue.flush()
            
            # Should only have 1 save with latest config
            assert len(save_calls) == 1
            assert save_calls[0][1]["version"] == 3
        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_does_not_coalesce_different_engagements(self) -> None:
        """
        GIVEN enqueue calls for different engagement_ids
        WHEN processed
        THEN each engagement gets its own write
        """
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        
        save_calls = []
        async def tracking_save(engagement_id, **kwargs):
            save_calls.append(engagement_id)
            return Path("/tmp/test.sqlite")
        
        manager.save = tracking_save
        
        queue = AsyncCheckpointQueue(manager)
        await queue.start()
        
        try:
            await queue.enqueue("eng-1", [], [], {})
            await queue.enqueue("eng-2", [], [], {})
            await queue.enqueue("eng-3", [], [], {})
            
            await queue.flush()
            
            assert len(save_calls) == 3
            assert set(save_calls) == {"eng-1", "eng-2", "eng-3"}
        finally:
            await queue.stop()


class TestAsyncCheckpointQueueOverflow:
    """Tests for queue overflow handling."""

    @pytest.mark.asyncio
    async def test_overflow_drops_oldest_with_warning(self) -> None:
        """
        GIVEN a queue at max capacity
        WHEN new item is enqueued
        THEN oldest unprocessed item is dropped with warning log
        """
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        import structlog
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        
        # Make save slow to fill queue
        async def slow_save(*args, **kwargs):
            await asyncio.sleep(1.0)
            return Path("/tmp/test.sqlite")
        
        manager.save = slow_save
        
        # Small queue size for testing
        queue = AsyncCheckpointQueue(manager, max_queue_size=2)
        await queue.start()
        
        try:
            with patch.object(structlog, "get_logger") as mock_logger:
                mock_log = MagicMock()
                mock_logger.return_value = mock_log
                
                # Fill queue beyond capacity
                for i in range(5):
                    await queue.enqueue(f"eng-{i}", [], [], {})
                
                # Should have logged warning about overflow
                # (exact assertion depends on implementation)
                assert queue._overflow_count >= 1 or mock_log.warning.called
        finally:
            await queue.stop()


class TestAsyncCheckpointQueueEnqueueWhenStopped:
    """Tests for enqueue behavior when queue is stopped."""

    @pytest.mark.asyncio
    async def test_enqueue_when_stopped_is_ignored(self) -> None:
        """
        GIVEN an AsyncCheckpointQueue that is NOT running
        WHEN enqueue() is called
        THEN request is silently dropped (no error)
        """
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        manager.save = AsyncMock(return_value=Path("/tmp/test.sqlite"))
        
        queue = AsyncCheckpointQueue(manager)
        # Don't start the queue
        
        # Should not raise
        await queue.enqueue(
            engagement_id="test-eng-1",
            agents=[],
            findings=[],
            config={},
        )
        
        # Save should never be called since queue wasn't running
        manager.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_enqueue_after_stop_is_ignored(self) -> None:
        """
        GIVEN an AsyncCheckpointQueue that was started then stopped
        WHEN enqueue() is called after stop
        THEN request is silently dropped
        """
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        manager.save = AsyncMock(return_value=Path("/tmp/test.sqlite"))
        
        queue = AsyncCheckpointQueue(manager)
        await queue.start()
        await queue.stop()
        
        # Reset mock to track only post-stop calls
        manager.save.reset_mock()
        
        await queue.enqueue(
            engagement_id="test-eng-1",
            agents=[],
            findings=[],
            config={},
        )
        
        # Save should not be called after stop
        manager.save.assert_not_called()


class TestAsyncCheckpointQueueLifecycle:
    """Tests for queue start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_worker_task(self) -> None:
        """
        GIVEN an AsyncCheckpointQueue
        WHEN start() is called
        THEN worker task is created and running
        """
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        
        await queue.start()
        
        try:
            assert queue._worker_task is not None
            assert not queue._worker_task.done()
        finally:
            await queue.stop()

    @pytest.mark.asyncio
    async def test_stop_gracefully_shuts_down_worker(self) -> None:
        """
        GIVEN a running AsyncCheckpointQueue
        WHEN stop() is called
        THEN worker task completes gracefully
        """
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        queue = AsyncCheckpointQueue(manager)
        
        await queue.start()
        await queue.stop()
        
        assert queue._worker_task is None or queue._worker_task.done()

    @pytest.mark.asyncio
    async def test_stop_flushes_pending_before_shutdown(self) -> None:
        """
        GIVEN a queue with pending writes
        WHEN stop() is called
        THEN pending writes are flushed before shutdown
        """
        from cyberred.storage.checkpoint_queue import AsyncCheckpointQueue
        from cyberred.storage.checkpoint import CheckpointManager
        
        manager = CheckpointManager(base_path=Path("/tmp/test-checkpoint"))
        save_count = 0
        
        async def counting_save(*args, **kwargs):
            nonlocal save_count
            save_count += 1
            return Path("/tmp/test.sqlite")
        
        manager.save = counting_save
        
        queue = AsyncCheckpointQueue(manager)
        await queue.start()
        
        await queue.enqueue("eng-1", [], [], {})
        await queue.stop()
        
        # Should have processed the pending write
        assert save_count == 1
