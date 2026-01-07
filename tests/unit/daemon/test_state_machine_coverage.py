"""Additional coverage tests for EngagementStateMachine."""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock

from cyberred.daemon.state_machine import (
    EngagementStateMachine, 
    EngagementState
)
from datetime import datetime
from unittest.mock import MagicMock

from cyberred.daemon.state_machine import (
    EngagementStateMachine, 
    EngagementState,
    get_valid_targets
)
from cyberred.core.exceptions import InvalidStateTransition

class TestStateMachineCoverage:
    def test_get_valid_targets(self) -> None:
        """Test get_valid_targets utility."""
        targets = get_valid_targets(EngagementState.RUNNING)
        assert EngagementState.PAUSED in targets
        assert EngagementState.STOPPED in targets
        assert EngagementState.INITIALIZING not in targets
        
    def test_task_cancellation_ignored(self) -> None:
        """Task cancellation in async listener handler should be ignored."""
        sm = EngagementStateMachine("id")
        task = MagicMock()
        task.result.side_effect = asyncio.CancelledError()
        # Should not raise
        sm._handle_async_exception(task, "id")

    def test_properties(self) -> None:
        """Test simple properties."""
        sm = EngagementStateMachine("id-123")
        assert sm.engagement_id == "id-123"
        assert len(sm.history) == 1
        assert sm.history[0][0] == EngagementState.INITIALIZING

    def test_remove_listener(self) -> None:
        """Test removing listeners."""
        sm = EngagementStateMachine("id-123")
        cb = MagicMock()
        sm.add_listener(cb)
        sm.remove_listener(cb)
        
        sm.start()
        cb.assert_not_called()
        
        with pytest.raises(ValueError):
            sm.remove_listener(cb)

    def test_invalid_transition_raises(self) -> None:
        """Test explicit raise of InvalidStateTransition."""
        sm = EngagementStateMachine("id-123")
        # Valid: INIT -> RUNNING
        sm.start()
        
        # Invalid: RUNNING -> INIT
        with pytest.raises(InvalidStateTransition) as exc:
             sm.transition(EngagementState.INITIALIZING)
        
        assert "RUNNING → INITIALIZING" in str(exc.value)

    def test_sync_listener_exception_caught(self) -> None:
        """Sync listener exception should be logged and ignored."""
        sm = EngagementStateMachine("id-123")
        
        def failing_listener(f, t):
            raise RuntimeError("Sync Boom")
            
        sm.add_listener(failing_listener)
        
        # Should not raise
        sm.start()
        assert sm.current_state == EngagementState.RUNNING

    @pytest.mark.asyncio
    async def test_async_listener_execution_and_error(self) -> None:
        """Async listener should run and exceptions caught."""
        sm = EngagementStateMachine("id-123")
        
        # Successful async listener
        future = asyncio.Future()
        async def success_listener(f, t):
            future.set_result((f, t))
            
        # Failing async listener
        async def fail_listener(f, t):
            raise RuntimeError("Async Boom")
            
        sm.add_listener(success_listener)
        sm.add_listener(fail_listener)
        
        sm.start()
        
        # Verify success listener ran
        res = await asyncio.wait_for(future, timeout=1.0)
        assert res == (EngagementState.INITIALIZING, EngagementState.RUNNING)
        
        # Verify failing listener didn't crash everything (can't easily assert log without structlog capture, 
        # but coverage will show lines hit)
        await asyncio.sleep(0.1) # Yield to allow error callback to run

    def test_async_listener_no_loop_warning(self) -> None:
        """Async listener scheduled without running loop should log warning."""
        # This is tricky because pytest-asyncio provides a loop.
        # We need to run this WITHOUT a loop context if possible, or mock get_running_loop to raise RuntimeError
        
        sm = EngagementStateMachine("id-123")
        async def async_cb(f, t): pass
        sm.add_listener(async_cb)
        
        with pytest.MonkeyPatch.context() as m:
            m.setattr(asyncio, "get_running_loop", MagicMock(side_effect=RuntimeError("No loop")))
            sm.start()
            # Should hit the except RuntimeError block
