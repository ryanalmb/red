"""Re-Plan Triggers for Director Ensemble.

Story 8.8: Re-Plan Triggers.

This module provides the ReplanTriggerManager class that monitors engagement
events and fires triggers to initiate Director re-planning based on configured
conditions.

Key Features:
- Timer-based periodic re-planning (default 5 minutes)
- Critical finding detection (severity: critical)
- Phase transition detection (recon → exploit → postex)
- Objective completion detection (data_accessed, shell_obtained, etc.)
- Operator override (manual request via TUI/directive)
- Debounce logic to prevent trigger storms

Classes:
    TriggerType: Enum of re-plan trigger types
    ReplanTrigger: A re-plan trigger event
    ReplanTriggerConfig: Configuration for re-plan triggers
    ReplanTriggerManager: Manages re-plan triggers for Director Ensemble

Example:
    manager = ReplanTriggerManager(
        event_bus=event_bus,
        on_trigger=handle_replan,
        config=config,
    )
    await manager.start(engagement_id)
    # ... engagement runs ...
    await manager.stop()
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union

import structlog

from cyberred.core.events import EventBus

log = structlog.get_logger()

__all__ = [
    "TriggerType",
    "ReplanTrigger",
    "ReplanTriggerConfig",
    "ReplanTriggerManager",
    "VALID_PHASE_TRANSITIONS",
    "VALID_OBJECTIVE_TYPES",
]

# Valid phase transitions per AC 4.2
VALID_PHASE_TRANSITIONS = frozenset([
    ("recon", "exploit"),
    ("exploit", "postex"),
])

# Valid objective types per AC 5.2
VALID_OBJECTIVE_TYPES = frozenset([
    "data_accessed",
    "shell_obtained",
    "credential_harvested",
])


# =============================================================================
# Enums (Task 1.1)
# =============================================================================


class TriggerType(Enum):
    """Types of re-plan triggers.
    
    Attributes:
        TIMER: Periodic timer (default 5min).
        CRITICAL_FINDING: Severity: critical finding discovered.
        PHASE_TRANSITION: recon → exploit → postex transition.
        OBJECTIVE_MET: Target data accessed or objective achieved.
        OPERATOR_OVERRIDE: Manual request via TUI/directive.
    """
    TIMER = "timer"
    CRITICAL_FINDING = "critical_finding"
    PHASE_TRANSITION = "phase_transition"
    OBJECTIVE_MET = "objective_met"
    OPERATOR_OVERRIDE = "operator_override"


# =============================================================================
# Data Classes (Tasks 1.2, 1.3)
# =============================================================================


@dataclass
class ReplanTrigger:
    """A re-plan trigger event.
    
    Attributes:
        trigger_type: Type of trigger that fired.
        engagement_id: Engagement this trigger belongs to.
        timestamp: When trigger fired.
        metadata: Additional context (finding_id, phase, etc).
    """
    trigger_type: TriggerType
    engagement_id: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplanTriggerConfig:
    """Configuration for re-plan triggers.
    
    Attributes:
        timer_interval_s: Periodic timer interval (default 300s = 5min).
        debounce_window_s: Debounce window to prevent trigger storms (default 10s).
        critical_finding_delay_max_s: Max delay for critical finding trigger (default 30s).
        timer_enabled: Whether timer trigger is enabled.
        critical_finding_enabled: Whether critical finding trigger is enabled.
        phase_transition_enabled: Whether phase transition trigger is enabled.
        objective_met_enabled: Whether objective met trigger is enabled.
    """
    timer_interval_s: float = 300.0  # 5 minutes
    debounce_window_s: float = 10.0
    critical_finding_delay_max_s: float = 30.0
    timer_enabled: bool = True
    critical_finding_enabled: bool = True
    phase_transition_enabled: bool = True
    objective_met_enabled: bool = True


# =============================================================================
# ReplanTriggerManager (Task 1.4)
# =============================================================================


class ReplanTriggerManager:
    """Manages re-plan triggers for Director Ensemble.
    
    Monitors engagement events and fires triggers to initiate
    Director re-planning based on configured conditions.
    
    Example:
        manager = ReplanTriggerManager(
            event_bus=event_bus,
            on_trigger=handle_replan,
            config=config,
        )
        await manager.start(engagement_id)
        # ... engagement runs ...
        await manager.stop()
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        on_trigger: Callable[[ReplanTrigger], Awaitable[None]],
        config: Optional[ReplanTriggerConfig] = None,
    ) -> None:
        """Initialize ReplanTriggerManager.
        
        Args:
            event_bus: EventBus for subscribing to findings/phases.
            on_trigger: Async callback invoked when trigger fires.
            config: Optional trigger configuration.
        """
        self._event_bus = event_bus
        self._on_trigger = on_trigger
        self._config = config or ReplanTriggerConfig()
        self._engagement_id: Optional[str] = None
        self._timer_task: Optional[asyncio.Task] = None
        self._last_trigger_time: float = 0.0
        self._last_director_cycle: float = 0.0
        self._last_timer_fire: float = 0.0
        self._subscriptions: List[Any] = []
        self._running = False
        self._paused = False
        self._log = log.bind(component="replan_triggers")
        self._suppressed_count = 0

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    async def start(self, engagement_id: str) -> None:
        """Start monitoring for re-plan triggers.
        
        Args:
            engagement_id: The engagement to monitor.
        """
        self._engagement_id = engagement_id
        self._running = True
        self._last_director_cycle = time.time()
        self._last_trigger_time = 0.0
        self._last_timer_fire = time.time()
        self._suppressed_count = 0
        
        self._log.info(
            "replan_trigger_manager_started",
            engagement_id=engagement_id,
            timer_interval_s=self._config.timer_interval_s,
            debounce_window_s=self._config.debounce_window_s,
        )
        
        # Start timer loop if enabled
        if self._config.timer_enabled:
            self._timer_task = asyncio.create_task(self._timer_loop())
        
        # Subscribe to event channels
        await self._setup_subscriptions()

    async def stop(self) -> None:
        """Stop monitoring and cleanup."""
        self._running = False
        
        # Cancel timer task
        if self._timer_task:
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                pass
            self._timer_task = None
        
        # Unsubscribe from all channels
        for subscription in self._subscriptions:
            try:
                await subscription.unsubscribe()
            except Exception as e:
                self._log.warning(
                    "subscription_unsubscribe_error",
                    error=str(e),
                )
        self._subscriptions.clear()
        
        self._log.info(
            "replan_trigger_manager_stopped",
            engagement_id=self._engagement_id,
            suppressed_count=self._suppressed_count,
        )

    def pause(self) -> None:
        """Pause trigger monitoring (timer respects this)."""
        self._paused = True
        self._log.info("replan_trigger_manager_paused")

    def resume(self) -> None:
        """Resume trigger monitoring."""
        self._paused = False
        self._log.info("replan_trigger_manager_resumed")

    # =========================================================================
    # Public Trigger Methods (Task 6)
    # =========================================================================

    async def trigger_replan(
        self,
        reason: str = "operator_override",
        operator_id: Optional[str] = None,
    ) -> None:
        """Manually trigger a re-plan (operator override).
        
        Args:
            reason: Reason for the manual trigger.
            operator_id: Optional operator identifier.
        """
        if not self._running:
            self._log.warning(
                "trigger_replan_ignored_not_running",
                reason=reason,
            )
            return
        
        trigger = ReplanTrigger(
            trigger_type=TriggerType.OPERATOR_OVERRIDE,
            engagement_id=self._engagement_id or "",
            metadata={
                "reason": reason,
                "operator_id": operator_id,
            },
        )
        
        await self._fire_trigger(trigger)
        
        # Reset timer to avoid immediate re-trigger (Task 2.4)
        self._last_timer_fire = time.time()

    def get_findings_window(self) -> Tuple[float, float]:
        """Get the time window for findings aggregation.
        
        Returns:
            Tuple of (start_timestamp, end_timestamp) for findings since last cycle.
        """
        return (self._last_director_cycle, time.time())

    # =========================================================================
    # Event Handlers (Tasks 3-5)
    # =========================================================================

    async def _handle_finding(
        self,
        channel: str,
        finding: Union[str, Dict[str, Any]],
    ) -> None:
        """Handle finding event, check for critical severity.
        
        Args:
            channel: The channel the finding was received on.
            finding: Finding data (JSON string or dict).
        """
        if not self._running or self._paused:
            return
        
        if not self._config.critical_finding_enabled:
            return
        
        # Parse finding if it's a string (JSON)
        if isinstance(finding, str):
            try:
                finding = json.loads(finding)
            except json.JSONDecodeError:
                self._log.warning(
                    "finding_parse_error",
                    channel=channel,
                )
                return
        
        severity = finding.get("severity", "").lower()
        
        if severity != "critical":
            return
        
        self._log.info(
            "critical_finding_detected",
            finding_id=finding.get("finding_id"),
            severity=severity,
        )
        
        trigger = ReplanTrigger(
            trigger_type=TriggerType.CRITICAL_FINDING,
            engagement_id=self._engagement_id or "",
            metadata={
                "finding_id": finding.get("finding_id"),
                "severity": severity,
                "target": finding.get("target"),
                "cve_id": finding.get("cve_id"),
                "technique": finding.get("technique"),
            },
        )
        
        await self._fire_trigger(trigger)

    async def _handle_phase_change(
        self,
        channel: str,
        event: Union[str, Dict[str, Any]],
    ) -> None:
        """Handle phase transition event.
        
        Args:
            channel: The channel the event was received on.
            event: Phase change event data (JSON string or dict).
        
        Note:
            Only valid transitions (recon→exploit, exploit→postex) trigger
            re-planning per AC 4.2.
        """
        if not self._running or self._paused:
            return
        
        if not self._config.phase_transition_enabled:
            return
        
        # Parse event if it's a string (JSON)
        if isinstance(event, str):
            try:
                event = json.loads(event)
            except json.JSONDecodeError:
                self._log.warning(
                    "phase_change_parse_error",
                    channel=channel,
                )
                return
        
        from_phase = event.get("from_phase", "").lower()
        to_phase = event.get("to_phase", "").lower()
        
        # Validate phase transition per AC 4.2
        transition = (from_phase, to_phase)
        if transition not in VALID_PHASE_TRANSITIONS:
            self._log.debug(
                "phase_transition_ignored_invalid",
                from_phase=from_phase,
                to_phase=to_phase,
                valid_transitions=list(VALID_PHASE_TRANSITIONS),
            )
            return
        
        self._log.info(
            "phase_transition_detected",
            from_phase=from_phase,
            to_phase=to_phase,
        )
        
        trigger = ReplanTrigger(
            trigger_type=TriggerType.PHASE_TRANSITION,
            engagement_id=self._engagement_id or "",
            metadata={
                "from_phase": from_phase,
                "to_phase": to_phase,
                "reason": event.get("reason"),
            },
        )
        
        # Phase transitions fire immediately (Task 4.3)
        await self._fire_trigger(trigger)

    async def _handle_objective(
        self,
        channel: str,
        event: Union[str, Dict[str, Any]],
    ) -> None:
        """Handle objective met event.
        
        Args:
            channel: The channel the event was received on.
            event: Objective completion event data (JSON string or dict).
        
        Note:
            Only valid objective types (data_accessed, shell_obtained,
            credential_harvested) trigger re-planning per AC 5.2.
        """
        if not self._running or self._paused:
            return
        
        if not self._config.objective_met_enabled:
            return
        
        # Parse event if it's a string (JSON)
        if isinstance(event, str):
            try:
                event = json.loads(event)
            except json.JSONDecodeError:
                self._log.warning(
                    "objective_parse_error",
                    channel=channel,
                )
                return
        
        objective_type = event.get("objective_type", "").lower()
        
        # Validate objective type per AC 5.2
        if objective_type not in VALID_OBJECTIVE_TYPES:
            self._log.debug(
                "objective_ignored_invalid_type",
                objective_type=objective_type,
                valid_types=list(VALID_OBJECTIVE_TYPES),
            )
            return
        
        self._log.info(
            "objective_met_detected",
            objective_type=objective_type,
            target=event.get("target"),
        )
        
        trigger = ReplanTrigger(
            trigger_type=TriggerType.OBJECTIVE_MET,
            engagement_id=self._engagement_id or "",
            metadata={
                "objective_type": objective_type,
                "target": event.get("target"),
                "details": event.get("details"),
            },
        )
        
        await self._fire_trigger(trigger)

    # =========================================================================
    # Internal Methods (Tasks 2, 7)
    # =========================================================================

    async def _fire_trigger(self, trigger: ReplanTrigger) -> None:
        """Fire trigger with debounce check.
        
        Args:
            trigger: The trigger to fire.
        """
        current_time = time.time()
        
        # Check debounce window (Task 7)
        time_since_last = current_time - self._last_trigger_time
        if time_since_last < self._config.debounce_window_s:
            self._suppressed_count += 1
            self._log.debug(
                "trigger_debounced",
                trigger_type=trigger.trigger_type.value,
                time_since_last=time_since_last,
                debounce_window=self._config.debounce_window_s,
                suppressed_count=self._suppressed_count,
            )
            return
        
        # Update timestamps
        self._last_trigger_time = current_time
        self._last_director_cycle = current_time
        
        self._log.info(
            "trigger_fired",
            trigger_type=trigger.trigger_type.value,
            engagement_id=trigger.engagement_id,
        )
        
        # Invoke callback
        try:
            await self._on_trigger(trigger)
        except Exception as e:
            self._log.error(
                "trigger_callback_error",
                trigger_type=trigger.trigger_type.value,
                error=str(e),
                exc_info=True,
            )
        
        # Log to audit trail
        try:
            await self._event_bus.audit({
                "type": "replan_trigger",
                "trigger_type": trigger.trigger_type.value,
                "engagement_id": trigger.engagement_id,
                "metadata": trigger.metadata,
                "timestamp": trigger.timestamp,
            })
        except Exception as e:
            self._log.warning(
                "audit_log_error",
                error=str(e),
            )

    async def _timer_loop(self) -> None:
        """Periodic timer loop (Task 2).
        
        Fires timer triggers at configured intervals while respecting
        pause/resume state.
        """
        self._log.info(
            "timer_loop_started",
            interval_s=self._config.timer_interval_s,
        )
        
        try:
            while self._running:
                # Wait for interval
                await asyncio.sleep(self._config.timer_interval_s)
                
                if not self._running:
                    break
                
                # Respect pause state (Task 2.3)
                if self._paused:
                    self._log.debug("timer_skipped_paused")
                    continue
                
                # Check if we should fire (avoid re-trigger after manual)
                time_since_last_fire = time.time() - self._last_timer_fire
                if time_since_last_fire < self._config.timer_interval_s * 0.9:
                    # Timer was reset recently, skip this iteration
                    self._log.debug(
                        "timer_skipped_recently_reset",
                        time_since_last=time_since_last_fire,
                    )
                    continue
                
                trigger = ReplanTrigger(
                    trigger_type=TriggerType.TIMER,
                    engagement_id=self._engagement_id or "",
                    metadata={
                        "interval_s": self._config.timer_interval_s,
                    },
                )
                
                self._last_timer_fire = time.time()
                await self._fire_trigger(trigger)
                
        except asyncio.CancelledError:
            self._log.info("timer_loop_cancelled")
            raise
        except Exception as e:
            self._log.error(
                "timer_loop_error",
                error=str(e),
                exc_info=True,
            )

    async def _setup_subscriptions(self) -> None:
        """Set up EventBus subscriptions for findings, phases, and objectives.
        
        Note: In production, these would connect to actual Redis channels.
        For unit tests, the handlers are called directly.
        """
        # The actual subscription patterns would be:
        # - findings:{engagement_id}:* for critical findings
        # - phases:{engagement_id} for phase transitions
        # - objectives:{engagement_id} for objective completions
        #
        # For now, we set up the subscription patterns but the handlers
        # are also exposed for direct testing.
        pass
