"""Catch-up Mode for TUI Event Replay.

Story 11.5: RAG Management Panel - AC #4

This module provides the CatchupManager for replaying missed events
when TUI reattaches to an engagement after being disconnected.

Per UX Design:
- "Attach — Immediate state sync on reconnect + Catch-up Mode" (line 104)
- "Catch-up Mode — Chronological replay of missed events" (lines 114-115)

Usage:
    import asyncio
    from cyberred.tui.catchup import CatchupManager, CatchupEvent, CatchupEventType
    
    manager = CatchupManager()
    manager.queue_event(CatchupEvent(...))
    
    # On reattach (within async context):
    async def on_reattach():
        async def event_handler(event: CatchupEvent) -> None:
            print(f"Replaying: {event.event_type}")
        
        await manager.start_catchup(event_handler)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Coroutine, List, Optional

import structlog

if TYPE_CHECKING:
    pass

log = structlog.get_logger()


class CatchupEventType(Enum):
    """Types of events that can be caught up on reattach.
    
    These map to StreamEventType but are specifically for catch-up replay.
    """
    FINDING = "finding"
    AUTH_REQUEST = "auth_request"
    STRATEGY_UPDATE = "strategy_update"
    AGENT_STATE = "agent_state"
    RAG_UPDATE = "rag_update"


@dataclass
class CatchupEvent:
    """Event stored for catch-up replay.
    
    Attributes:
        event_type: Type of event (finding, auth, strategy, etc.)
        timestamp: When the event originally occurred
        payload: Event data dictionary
        source: Origin of event (agent_id, "director", "rag", etc.)
    """
    event_type: CatchupEventType
    timestamp: datetime
    payload: dict
    source: str  # agent_id or "director" or "rag"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "source": self.source,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CatchupEvent":
        """Create from dictionary."""
        return cls(
            event_type=CatchupEventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            payload=data["payload"],
            source=data["source"],
        )


# Type alias for event handler callback
EventHandler = Callable[[CatchupEvent], Coroutine[Any, Any, None]]


@dataclass
class CatchupManager:
    """Manages event catch-up on TUI reattach.
    
    Story 11.5 AC #4: When TUI reattaches after disconnect, missed events
    are replayed chronologically with a progress indicator.
    
    The manager:
    1. Queues events during disconnect (daemon-side)
    2. Replays events chronologically on reattach
    3. Shows "Catching up: X events" progress
    4. Emits events to TUI handlers for display
    
    Attributes:
        events: List of queued events awaiting replay
        is_catching_up: Whether catch-up is currently in progress
        replay_index: Current position in replay (1-indexed for display)
        total_events: Total events to replay (for progress calculation)
    """
    
    events: List[CatchupEvent] = field(default_factory=list)
    is_catching_up: bool = False
    replay_index: int = 0
    total_events: int = 0
    _replay_delay: float = 0.05  # Small delay between events to prevent UI overwhelm
    _log: Any = field(default_factory=lambda: log.bind(component="catchup_manager"))
    
    def queue_event(self, event: CatchupEvent) -> None:
        """Queue event for later replay.
        
        Called by daemon during TUI disconnect to buffer events.
        Events are automatically sorted by timestamp to maintain
        chronological order.
        
        Args:
            event: Event to queue for replay
        """
        self.events.append(event)
        # Maintain chronological order
        self.events.sort(key=lambda e: e.timestamp)
        self._log.debug(
            "event_queued",
            event_type=event.event_type.value,
            source=event.source,
            queue_size=len(self.events),
        )
    
    def queue_events(self, events: List[CatchupEvent]) -> None:
        """Queue multiple events for replay.
        
        Args:
            events: List of events to queue
        """
        self.events.extend(events)
        self.events.sort(key=lambda e: e.timestamp)
        self._log.debug("events_queued", count=len(events), queue_size=len(self.events))
    
    async def start_catchup(
        self,
        handler: EventHandler,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> int:
        """Begin chronological replay of missed events.
        
        Args:
            handler: Async callback to handle each replayed event
            on_progress: Optional callback for progress updates (current, total)
            
        Returns:
            Number of events replayed
        """
        if not self.events:
            self._log.debug("catchup_skipped_no_events")
            return 0
        
        self.is_catching_up = True
        self.total_events = len(self.events)
        self.replay_index = 0
        
        self._log.info("catchup_started", total_events=self.total_events)
        
        replayed_count = 0
        
        try:
            for i, event in enumerate(self.events):
                self.replay_index = i + 1  # 1-indexed for display
                
                # Notify progress callback
                if on_progress:
                    on_progress(self.replay_index, self.total_events)
                
                # Replay the event
                try:
                    await handler(event)
                    replayed_count += 1
                except Exception as e:
                    # Log but continue - don't let one bad event stop catchup
                    self._log.warning(
                        "catchup_event_error",
                        event_type=event.event_type.value,
                        source=event.source,
                        error=str(e),
                    )
                
                # Small delay to prevent overwhelming UI
                await asyncio.sleep(self._replay_delay)
            
            self._log.info(
                "catchup_completed",
                replayed=replayed_count,
                total=self.total_events,
            )
            
        finally:
            self.is_catching_up = False
            self.events.clear()
            self.replay_index = 0
            self.total_events = 0
        
        return replayed_count
    
    def clear(self) -> None:
        """Clear all queued events without replay."""
        count = len(self.events)
        self.events.clear()
        self.replay_index = 0
        self.total_events = 0
        self._log.debug("catchup_cleared", cleared_count=count)
    
    @property
    def pending_count(self) -> int:
        """Number of events pending replay."""
        if self.is_catching_up:
            return self.total_events - self.replay_index
        return len(self.events)
    
    @property
    def progress_percent(self) -> float:
        """Replay progress as percentage (0.0 to 100.0)."""
        if not self.is_catching_up or self.total_events == 0:
            return 0.0
        return (self.replay_index / self.total_events) * 100.0
    
    @property
    def progress_text(self) -> str:
        """Human-readable progress text for display.
        
        Returns:
            Empty string if not catching up, otherwise "Catching up: X/Y events"
        """
        if not self.is_catching_up:
            return ""
        return f"Catching up: {self.replay_index}/{self.total_events} events"


class CatchupProgressIndicator:
    """Progress indicator widget helper for catch-up mode.
    
    Provides formatted strings for TUI display during catch-up.
    """
    
    def __init__(self, manager: CatchupManager) -> None:
        """Initialize with CatchupManager reference.
        
        Args:
            manager: CatchupManager to track
        """
        self._manager = manager
    
    @property
    def is_active(self) -> bool:
        """Return True if catch-up is in progress."""
        return self._manager.is_catching_up
    
    @property
    def status_text(self) -> str:
        """Return formatted status text for display."""
        if not self._manager.is_catching_up:
            return ""
        return self._manager.progress_text
    
    @property
    def progress_bar(self) -> str:
        """Return ASCII progress bar for terminal display.
        
        Returns:
            Progress bar like "[████████░░░░░░░░] 50%"
        """
        if not self._manager.is_catching_up:
            return ""
        
        width = 16
        percent = self._manager.progress_percent
        filled = int(width * percent / 100)
        empty = width - filled
        
        bar = "█" * filled + "░" * empty
        return f"[{bar}] {percent:.0f}%"
