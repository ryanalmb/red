"""Engagement State Machine.

This module defines the strict engagement lifecycle state machine.
Engagements follow predictable transitions per architecture specification.

States:
    INITIALIZING: Loading config, spawning agents
    RUNNING: Active engagement, agents executing
    PAUSED: Operator paused, agents suspended, hot state (RAM)
    STOPPED: Halted, checkpointed to disk
    COMPLETED: Objective achieved, archived

Valid Transitions:
    INITIALIZING → RUNNING
    RUNNING ↔ PAUSED
    RUNNING/PAUSED → STOPPED
    STOPPED → COMPLETED

Usage:
    from cyberred.daemon.state_machine import (
        EngagementState,
        EngagementStateMachine,
        is_valid_transition,
        get_valid_targets,
    )

    # Create state machine for an engagement
    sm = EngagementStateMachine("ministry-2025")

    # Transition through lifecycle
    sm.start()    # INITIALIZING → RUNNING
    sm.pause()    # RUNNING → PAUSED
    sm.resume()   # PAUSED → RUNNING
    sm.stop()     # RUNNING → STOPPED
    sm.complete() # STOPPED → COMPLETED
"""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Awaitable, Callable, Optional, Union
import asyncio
import structlog
from functools import partial

from cyberred.core.exceptions import InvalidStateTransition


log = structlog.get_logger()


class EngagementState(StrEnum):
    """Engagement lifecycle states.

    Per architecture (lines 407-416), each state has specific implications
    for agent status, memory allocation, and resume capability.

    Attributes:
        INITIALIZING: Loading config, spawning agents. Memory allocating.
        RUNNING: Active engagement, agents executing. Memory hot in RAM.
        PAUSED: Operator paused, agents suspended. Memory hot in RAM, instant resume.
        STOPPED: Halted, checkpointed to disk. Memory cold, resume from checkpoint.
        COMPLETED: Objective achieved, archived. Terminated, new engagement needed.
    """

    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"


# Valid state transitions per architecture specification
VALID_TRANSITIONS: frozenset[tuple[EngagementState, EngagementState]] = frozenset([
    (EngagementState.INITIALIZING, EngagementState.RUNNING),
    (EngagementState.RUNNING, EngagementState.PAUSED),
    (EngagementState.RUNNING, EngagementState.STOPPED),
    (EngagementState.PAUSED, EngagementState.RUNNING),
    (EngagementState.PAUSED, EngagementState.STOPPED),
    (EngagementState.STOPPED, EngagementState.COMPLETED),
])


def is_valid_transition(
    from_state: EngagementState,
    to_state: EngagementState,
) -> bool:
    """Check if a state transition is valid.

    Args:
        from_state: Current state.
        to_state: Target state.

    Returns:
        True if transition is allowed, False otherwise.
    """
    return (from_state, to_state) in VALID_TRANSITIONS


def get_valid_targets(from_state: EngagementState) -> set[EngagementState]:
    """Get all valid target states from a given state.

    Args:
        from_state: Current state.

    Returns:
        Set of states that can be transitioned to. Empty if terminal state.
    """
    return {to for (frm, to) in VALID_TRANSITIONS if frm == from_state}


# Type alias for state change listeners (sync or async)
StateChangeListener = Callable[[EngagementState, EngagementState], Union[None, Awaitable[None]]]


class EngagementStateMachine:
    """Strict engagement state machine.

    Manages engagement lifecycle transitions with validation.
    Invalid transitions raise InvalidStateTransition.

    Attributes:
        engagement_id: Unique engagement identifier.
        current_state: Current engagement state (read-only).
        history: List of (state, timestamp) tuples (read-only copy).
    """

    def __init__(self, engagement_id: str) -> None:
        """Initialize state machine in INITIALIZING state.

        Args:
            engagement_id: Unique identifier for the engagement.
        """
        self._engagement_id = engagement_id
        self._current_state = EngagementState.INITIALIZING
        self._history: list[tuple[EngagementState, datetime]] = [
            (EngagementState.INITIALIZING, datetime.now(timezone.utc))
        ]
        self._listeners: list[StateChangeListener] = []

    @property
    def engagement_id(self) -> str:
        """Engagement identifier."""
        return self._engagement_id

    @property
    def current_state(self) -> EngagementState:
        """Current engagement state."""
        return self._current_state

    @property
    def history(self) -> list[tuple[EngagementState, datetime]]:
        """State transition history (read-only copy)."""
        return list(self._history)

    def add_listener(self, callback: StateChangeListener) -> None:
        """Add a state change listener.

        Args:
            callback: Function called with (old_state, new_state) on transitions.
                Can be sync or async function.
        """
        self._listeners.append(callback)

    def remove_listener(self, callback: StateChangeListener) -> None:
        """Remove a state change listener.

        Args:
            callback: Previously registered callback.

        Raises:
            ValueError: If callback is not registered.
        """
        self._listeners.remove(callback)

    def transition(self, to_state: EngagementState) -> None:
        """Transition to a new state.

        Args:
            to_state: Target state.

        Raises:
            InvalidStateTransition: If transition is not valid.
        """
        from_state = self._current_state

        if not is_valid_transition(from_state, to_state):
            raise InvalidStateTransition(
                engagement_id=self._engagement_id,
                from_state=str(from_state),
                to_state=str(to_state),
            )

        self._current_state = to_state
        self._history.append((to_state, datetime.now(timezone.utc)))

        log.info(
            "engagement_state_changed",
            engagement_id=self._engagement_id,
            from_state=str(from_state),
            to_state=str(to_state),
        )

        self._notify_listeners(from_state, to_state)

    def _notify_listeners(
        self,
        from_state: EngagementState,
        to_state: EngagementState,
    ) -> None:
        """Notify all registered listeners of state change.

        Handles both sync and async listeners. Listener exceptions
        are caught and logged but do not propagate.
        """
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    try:
                        loop = asyncio.get_running_loop()
                        task = loop.create_task(listener(from_state, to_state))
                        # Attach callback to log exceptions from the async task
                        task.add_done_callback(
                            partial(self._handle_async_exception, engagement_id=self._engagement_id)
                        )
                    except RuntimeError:
                        # No event loop running - skip async listener
                        log.warning(
                            "async_listener_no_loop",
                            engagement_id=self._engagement_id,
                        )
                else:
                    listener(from_state, to_state) # type: ignore
            except Exception as e:
                log.warning(
                    "state_listener_error",
                    engagement_id=self._engagement_id,
                    error=str(e),
                )

    @staticmethod
    def _handle_async_exception(task: asyncio.Task, engagement_id: str) -> None:
        """Callback to log exceptions from async listeners."""
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.warning(
                "state_listener_error",
                engagement_id=engagement_id,
                error=str(e),
                async_task=True,
            )

    # Convenience transition methods

    def start(self) -> None:
        """Transition from INITIALIZING to RUNNING.

        Raises:
            InvalidStateTransition: If not in INITIALIZING state.
        """
        self.transition(EngagementState.RUNNING)

    def pause(self) -> None:
        """Transition from RUNNING to PAUSED.

        Raises:
            InvalidStateTransition: If not in RUNNING state.
        """
        self.transition(EngagementState.PAUSED)

    def resume(self) -> None:
        """Transition from PAUSED to RUNNING.

        Raises:
            InvalidStateTransition: If not in PAUSED state.
        """
        self.transition(EngagementState.RUNNING)

    def stop(self) -> None:
        """Transition from RUNNING or PAUSED to STOPPED.

        Raises:
            InvalidStateTransition: If not in RUNNING or PAUSED state.
        """
        self.transition(EngagementState.STOPPED)

    def complete(self) -> None:
        """Transition from STOPPED to COMPLETED.

        Raises:
            InvalidStateTransition: If not in STOPPED state.
        """
        self.transition(EngagementState.COMPLETED)
