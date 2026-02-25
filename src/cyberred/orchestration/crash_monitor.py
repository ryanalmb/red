"""Agent Crash Monitor for crash detection and recovery.

This module implements crash detection via heartbeat monitoring and triggers
agent replacement when crashes are detected.

Story 7.12: Agent Crash Recovery
ERR5: "Log crash, spawn replacement, resume from checkpoint"
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

import structlog

if TYPE_CHECKING:
    from cyberred.core.events import EventBus
    from cyberred.storage.checkpoint import CheckpointManager

log = structlog.get_logger()

# Per story spec: detect crash within 30s
CRASH_DETECTION_TIMEOUT_S = 30
# Per story spec: heartbeat every 10s (3 missed = crash)
HEARTBEAT_INTERVAL_S = 10


@dataclass
class AgentHealthState:
    """Track agent health for crash detection.
    
    Attributes:
        agent_id: Unique identifier for the agent.
        engagement_id: ID of the current engagement.
        last_heartbeat: Timestamp of last received heartbeat.
        status: Health status (healthy, suspected, crashed).
        task_id: Current task being executed (if any).
        consecutive_misses: Number of consecutive missed heartbeats.
    """
    agent_id: str
    engagement_id: str
    last_heartbeat: datetime
    status: str = "healthy"  # healthy, suspected, crashed
    task_id: Optional[str] = None
    consecutive_misses: int = 0


class AgentCrashMonitor:
    """Monitor agent health and trigger replacement on crash.
    
    Implements ERR5: "Log crash, spawn replacement, resume from checkpoint"
    
    The monitor:
    1. Subscribes to agent heartbeat events
    2. Tracks last heartbeat timestamp per agent
    3. Periodically checks for stale heartbeats (>30s)
    4. Triggers crash callback when agent is detected as crashed
    
    Attributes:
        _event_bus: EventBus for subscribing to heartbeats.
        _checkpoint_manager: CheckpointManager for state persistence.
        _on_crash: Callback invoked when crash is detected.
        _agents: Dict mapping agent_id to AgentHealthState.
        _monitor_task: Background task for periodic health checks.
    """
    
    def __init__(
        self,
        event_bus: "EventBus",
        checkpoint_manager: "CheckpointManager",
        on_crash_callback: Callable[[str, str], Awaitable[None]],
    ) -> None:
        """Initialize the crash monitor.
        
        Args:
            event_bus: EventBus instance for heartbeat subscription.
            checkpoint_manager: CheckpointManager for state access.
            on_crash_callback: Async callback(agent_id, engagement_id) on crash.
        """
        self._event_bus = event_bus
        self._checkpoint_manager = checkpoint_manager
        self._on_crash = on_crash_callback
        self._agents: dict[str, AgentHealthState] = {}
        self._monitor_task: Optional[asyncio.Task[None]] = None
        self._heartbeat_subscription: Any = None
        self._log = log.bind(component="crash_monitor")
    
    async def start(self) -> None:
        """Start monitoring agent health.
        
        Subscribes to heartbeat events and starts the periodic check loop.
        """
        # Subscribe to heartbeat pattern.
        # Prefer pattern subscription when available (core.event_bus) so
        # channels like agent:{id}:heartbeat are matched correctly.
        if hasattr(self._event_bus, "psubscribe"):
            self._heartbeat_subscription = await self._event_bus.psubscribe(
                "agent:*:heartbeat",
                self._handle_heartbeat,
            )
        else:
            # Fallback for buses without psubscribe support.
            self._heartbeat_subscription = await self._event_bus.subscribe(
                "agent:heartbeat",
                lambda data: self._handle_heartbeat("agent:heartbeat", data),
            )
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self._log.info("crash_monitor_started")
    
    async def stop(self) -> None:
        """Stop monitoring and cleanup resources."""
        if self._monitor_task:
            self._monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor_task
            self._monitor_task = None
        if self._heartbeat_subscription is not None:
            with contextlib.suppress(Exception):
                cancel_fn = getattr(self._heartbeat_subscription, "cancel", None)
                unsubscribe_fn = getattr(self._heartbeat_subscription, "unsubscribe", None)
                if callable(cancel_fn):
                    await cancel_fn()
                elif callable(unsubscribe_fn):
                    await unsubscribe_fn()
            self._heartbeat_subscription = None
        self._log.info("crash_monitor_stopped")
    
    async def register_agent(self, agent_id: str, engagement_id: str) -> None:
        """Register a new agent for health monitoring.
        
        Args:
            agent_id: Unique identifier for the agent.
            engagement_id: ID of the engagement the agent belongs to.
        """
        self._agents[agent_id] = AgentHealthState(
            agent_id=agent_id,
            engagement_id=engagement_id,
            last_heartbeat=datetime.now(UTC),
        )
        self._log.info(
            "agent_registered_for_monitoring",
            agent_id=agent_id,
            engagement_id=engagement_id,
        )
    
    async def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent from health monitoring.
        
        Args:
            agent_id: Agent to unregister.
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
            self._log.info("agent_unregistered_from_monitoring", agent_id=agent_id)
    
    def get_agent_state(self, agent_id: str) -> Optional[AgentHealthState]:
        """Get health state for a specific agent.
        
        Args:
            agent_id: Agent to look up.
            
        Returns:
            AgentHealthState or None if agent not found.
        """
        return self._agents.get(agent_id)
    
    def get_all_agent_states(self) -> list[AgentHealthState]:
        """Get health states for all monitored agents.
        
        Returns:
            List of AgentHealthState for all registered agents.
        """
        return list(self._agents.values())
    
    async def _handle_heartbeat(self, channel: str, data: dict[str, Any]) -> None:
        """Process agent heartbeat message.
        
        Updates last_heartbeat timestamp and resets health status.
        
        Args:
            channel: The channel the heartbeat was received on.
            data: Heartbeat payload with agent_id, engagement_id, task_id.
        """
        agent_id = data.get("agent_id")
        if not agent_id or agent_id not in self._agents:
            return
        
        state = self._agents[agent_id]
        state.last_heartbeat = datetime.now(UTC)
        state.status = "healthy"
        state.consecutive_misses = 0
        state.task_id = data.get("task_id")
        
        self._log.debug(
            "heartbeat_received",
            agent_id=agent_id,
            task_id=state.task_id,
        )
    
    async def _monitor_loop(self) -> None:
        """Periodic health check loop.
        
        Runs every HEARTBEAT_INTERVAL_S seconds and checks all agents.
        """
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL_S)
                await self._check_all_agents()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.error("monitor_loop_error", error=str(e), exc_info=True)
    
    async def _check_all_agents(self) -> None:
        """Check health of all registered agents.
        
        Detects crashed agents (heartbeat older than CRASH_DETECTION_TIMEOUT_S)
        and triggers the crash callback for each.
        """
        now = datetime.now(UTC)
        crashed_agents: list[tuple[str, str]] = []
        
        for agent_id, state in list(self._agents.items()):
            elapsed = (now - state.last_heartbeat).total_seconds()
            
            if elapsed > CRASH_DETECTION_TIMEOUT_S:
                state.status = "crashed"
                self._log.error(
                    "agent_crash_detected",
                    agent_id=agent_id,
                    engagement_id=state.engagement_id,
                    last_heartbeat=state.last_heartbeat.isoformat(),
                    elapsed_seconds=elapsed,
                    task_id=state.task_id,
                )
                crashed_agents.append((agent_id, state.engagement_id))
                del self._agents[agent_id]
        
        # Trigger crash callbacks (outside the iteration loop)
        for agent_id, engagement_id in crashed_agents:
            try:
                await self._on_crash(agent_id, engagement_id)
            except Exception as e:
                self._log.error(
                    "crash_callback_error",
                    agent_id=agent_id,
                    error=str(e),
                    exc_info=True,
                )
