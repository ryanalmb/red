"""Safety Tests for SSH Disconnect Resilience (Story 2.9).

These tests verify that engagements survive TUI client disconnects,
ensuring operators can safely reconnect without losing engagement state.

AC#9: Engagement continues running if TUI client crashes/disconnects
AC#10: Operators can safely reconnect after SSH disconnect
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

from cyberred.daemon.session_manager import SessionManager
from cyberred.daemon.state_machine import EngagementState
from cyberred.daemon.streaming import StreamEvent, StreamEventType


@pytest.fixture
def session_manager() -> SessionManager:
    """Create a fresh SessionManager for testing."""
    return SessionManager(max_engagements=10)


@pytest.fixture
def engagement_config(tmp_path: Path) -> Path:
    """Create a valid engagement config file."""
    config = tmp_path / "engagement.yaml"
    config.write_text("name: test-engagement\n")
    return config


@pytest.fixture
def running_engagement(
    session_manager: SessionManager,
    engagement_config: Path,
) -> Generator[str, None, None]:
    """Create an engagement in RUNNING state.
    
    Uses direct state transition for safety testing isolation.
    """
    engagement_id = session_manager.create_engagement(engagement_config)
    context = session_manager.get_engagement(engagement_id)
    context.state_machine.start()
    yield engagement_id


@pytest.mark.safety
class TestEngagementSurvivesTUIDisconnect:
    """Verify engagement resilience to TUI client failures (AC#9, AC#10)."""

    def test_engagement_survives_subscription_removal(
        self,
        session_manager: SessionManager,
        running_engagement: str,
    ) -> None:
        """Engagement continues RUNNING when subscription is removed.
        
        Simulates TUI crash by abruptly removing subscription without
        proper detach handshake.
        """
        # Subscribe a client
        callback = MagicMock()
        sub_id = session_manager.subscribe_to_engagement(running_engagement, callback)
        
        assert session_manager.get_subscription_count(running_engagement) == 1
        
        # Simulate crash: just unsubscribe (like socket closing)
        session_manager.unsubscribe_from_engagement(sub_id)
        
        # Verify engagement state unchanged
        context = session_manager.get_engagement(running_engagement)
        assert context.state == EngagementState.RUNNING
        assert session_manager.get_subscription_count(running_engagement) == 0

    def test_engagement_survives_all_clients_disconnect(
        self,
        session_manager: SessionManager,
        running_engagement: str,
    ) -> None:
        """Engagement continues when all clients disconnect.
        
        AC#9: Even with zero attached clients, engagement keeps running.
        """
        # Subscribe multiple clients
        callbacks = [MagicMock() for _ in range(3)]
        sub_ids = [
            session_manager.subscribe_to_engagement(running_engagement, cb)
            for cb in callbacks
        ]
        
        assert session_manager.get_subscription_count(running_engagement) == 3
        
        # Disconnect all clients
        for sub_id in sub_ids:
            session_manager.unsubscribe_from_engagement(sub_id)
        
        # Engagement still running
        context = session_manager.get_engagement(running_engagement)
        assert context.state == EngagementState.RUNNING
        assert session_manager.get_subscription_count(running_engagement) == 0

    def test_reattach_after_disconnect(
        self,
        session_manager: SessionManager,
        running_engagement: str,
    ) -> None:
        """Operator can reconnect after disconnect (AC#10).
        
        Simulates SSH disconnect and reconnection.
        """
        # Initial attach
        callback1 = MagicMock()
        sub_id1 = session_manager.subscribe_to_engagement(running_engagement, callback1)
        
        # Verify receives broadcast
        event = StreamEvent(event_type=StreamEventType.AGENT_STATUS, data={"agent_id": "1"})
        session_manager.broadcast_event(running_engagement, event)
        callback1.assert_called_once_with(event)
        
        # Simulate disconnect (SSH drops)
        session_manager.unsubscribe_from_engagement(sub_id1)
        callback1.reset_mock()
        
        # Reconnect with new subscription
        callback2 = MagicMock()
        sub_id2 = session_manager.subscribe_to_engagement(running_engagement, callback2)
        
        # New client receives events
        event2 = StreamEvent(event_type=StreamEventType.FINDING, data={"id": "f-1"})
        session_manager.broadcast_event(running_engagement, event2)
        
        callback1.assert_not_called()  # Old client disconnected
        callback2.assert_called_once_with(event2)  # New client receives
        
        # Engagement still running
        context = session_manager.get_engagement(running_engagement)
        assert context.state == EngagementState.RUNNING

    def test_paused_engagement_survives_disconnect(
        self,
        session_manager: SessionManager,
        running_engagement: str,
    ) -> None:
        """Paused engagement also survives client disconnect."""
        # Pause engagement
        session_manager.pause_engagement(running_engagement)
        context = session_manager.get_engagement(running_engagement)
        assert context.state == EngagementState.PAUSED
        
        # Attach
        callback = MagicMock()
        sub_id = session_manager.subscribe_to_engagement(running_engagement, callback)
        
        # Simulate disconnect
        session_manager.unsubscribe_from_engagement(sub_id)
        
        # Engagement still paused (not crashed/stopped)
        assert context.state == EngagementState.PAUSED


@pytest.mark.safety
class TestSubscriptionCleanup:
    """Verify subscription cleanup doesn't affect engagement state."""

    def test_broken_callback_removed_automatically(
        self,
        session_manager: SessionManager,
        running_engagement: str,
    ) -> None:
        """Broken callbacks are removed during broadcast.
        
        If a TUI client's callback raises an exception (e.g., broken pipe),
        it should be automatically cleaned up without affecting engagement.
        """
        # Good callback
        good_callback = MagicMock()
        session_manager.subscribe_to_engagement(running_engagement, good_callback)
        
        # Bad callback that raises exception
        bad_callback = MagicMock(side_effect=BrokenPipeError("Connection reset"))
        session_manager.subscribe_to_engagement(running_engagement, bad_callback)
        
        assert session_manager.get_subscription_count(running_engagement) == 2
        
        # Broadcast - bad callback should be cleaned up
        event = StreamEvent(event_type=StreamEventType.HEARTBEAT, data={})
        count = session_manager.broadcast_event(running_engagement, event)
        
        # Only good callback received event
        assert count == 1
        good_callback.assert_called_once_with(event)
        
        # Bad callback was removed
        assert session_manager.get_subscription_count(running_engagement) == 1
        
        # Engagement still running
        context = session_manager.get_engagement(running_engagement)
        assert context.state == EngagementState.RUNNING

    def test_multiple_broken_callbacks_handled(
        self,
        session_manager: SessionManager,
        running_engagement: str,
    ) -> None:
        """Multiple broken callbacks handled gracefully."""
        # Create callbacks that all fail
        bad_callbacks = [
            MagicMock(side_effect=ConnectionResetError()),
            MagicMock(side_effect=OSError("Socket closed")),
            MagicMock(side_effect=RuntimeError("Client gone")),
        ]
        
        for cb in bad_callbacks:
            session_manager.subscribe_to_engagement(running_engagement, cb)
        
        assert session_manager.get_subscription_count(running_engagement) == 3
        
        # Broadcast - all broken callbacks cleaned up
        event = StreamEvent(event_type=StreamEventType.STATE_CHANGE, data={"state": "RUNNING"})
        count = session_manager.broadcast_event(running_engagement, event)
        
        assert count == 0  # All callbacks failed
        assert session_manager.get_subscription_count(running_engagement) == 0
        
        # Engagement still running
        context = session_manager.get_engagement(running_engagement)
        assert context.state == EngagementState.RUNNING


@pytest.mark.safety
class TestAttachLatency:
    """NFR32: Attach latency must be <2s from command to TUI operational."""

    def test_subscribe_latency_under_100ms(
        self,
        session_manager: SessionManager,
        running_engagement: str,
    ) -> None:
        """Subscription creation must be fast.
        
        The server-side subscription is a small part of the <2s attach budget.
        It should complete in <100ms.
        """
        callback = MagicMock()
        
        start = time.perf_counter()
        sub_id = session_manager.subscribe_to_engagement(running_engagement, callback)
        elapsed = time.perf_counter() - start
        
        assert sub_id is not None
        assert elapsed < 0.1, f"Subscribe took {elapsed:.3f}s, expected <100ms"

    def test_unsubscribe_latency_under_100ms(
        self,
        session_manager: SessionManager,
        running_engagement: str,
    ) -> None:
        """Unsubscription must be fast for clean detach."""
        callback = MagicMock()
        sub_id = session_manager.subscribe_to_engagement(running_engagement, callback)
        
        start = time.perf_counter()
        session_manager.unsubscribe_from_engagement(sub_id)
        elapsed = time.perf_counter() - start
        
        assert elapsed < 0.1, f"Unsubscribe took {elapsed:.3f}s, expected <100ms"
