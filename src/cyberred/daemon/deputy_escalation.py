"""Deputy Escalation Manager for Story 10.8.

Manages escalation timers for authorization requests. When the primary
operator doesn't respond within escalation_timeout, the request is
escalated to the deputy operator.

Per FR63: "Deputy Operator role for authorization backup"

Usage:
    from cyberred.core.config import DeputyOperatorConfig
    from cyberred.daemon.deputy_escalation import DeputyEscalationManager
    
    config = DeputyOperatorConfig(
        deputy_operator="deputy@example.com",
        escalation_timeout=timedelta(minutes=30),
    )
    
    manager = DeputyEscalationManager(config, event_bus, audit_logger)
    await manager.start_escalation_timer("request-123")
    
    # When primary responds:
    await manager.cancel_escalation_timer("request-123")
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from cyberred.core.audit import AuthorizationAuditLogger
    from cyberred.core.config import DeputyOperatorConfig
    from cyberred.core.event_bus import EventBus
    from cyberred.daemon.authorization_queue import AuthorizationQueue

logger = logging.getLogger(__name__)


# =============================================================================
# Deputy Response Dataclass
# =============================================================================


@dataclass
class DeputyResponse:
    """Response from deputy operator to an escalated authorization request.
    
    Attributes:
        request_id: ID of the original authorization request.
        decision: Authorization decision (APPROVED/DENIED/MORE_INFO/SKIPPED).
        responder: Deputy operator identifier (email or username).
        escalated: Always True for deputy responses.
        timestamp: ISO 8601 timestamp of the response.
        constraints: Optional constraints (time_limit, target_limit, etc.).
        notes: Optional notes from deputy.
    """
    request_id: str
    decision: str
    responder: str
    escalated: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    constraints: Dict[str, Any] | None = None
    notes: str | None = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for transmission/storage.
        
        Returns:
            Dictionary representation of the response.
        """
        return {
            "request_id": self.request_id,
            "decision": self.decision,
            "responder": self.responder,
            "escalated": self.escalated,
            "timestamp": self.timestamp,
            "constraints": self.constraints,
            "notes": self.notes,
        }


# =============================================================================
# Escalation Audit Entry Helper
# =============================================================================


def create_escalation_audit_entry(
    request_id: str,
    decision: str,
    responder: str,
    escalated: bool = True,
    escalated_at: str | None = None,
    original_operator: str | None = None,
    constraints: Dict[str, Any] | None = None,
    notes: str | None = None,
) -> Dict[str, Any]:
    """Create an audit entry for an escalated authorization response.
    
    Per AC #3: Audit entry includes `escalated: true` and `responder: deputy`.
    
    Args:
        request_id: ID of the authorization request.
        decision: Authorization decision (APPROVED/DENIED/etc.).
        responder: Deputy operator identifier.
        escalated: Whether this was an escalated request (always True for deputy).
        escalated_at: ISO timestamp when escalation occurred.
        original_operator: Primary operator who didn't respond.
        constraints: Optional constraints applied to approval.
        notes: Optional notes from responder.
        
    Returns:
        Dictionary suitable for audit logging.
    """
    return {
        "event_type": "authorization_response",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "decision": decision,
        "responder": responder,
        "escalated": escalated,
        "escalated_at": escalated_at,
        "original_operator": original_operator,
        "constraints": constraints,
        "notes": notes,
    }


# =============================================================================
# Deputy Escalation Manager
# =============================================================================


class DeputyEscalationManager:
    """Manages escalation timers for authorization requests.
    
    When primary operator doesn't respond within escalation_timeout,
    the request is escalated to the deputy operator.
    
    Thread-safe: Uses asyncio.Lock for concurrent timer management.
    
    Attributes:
        _config: DeputyOperatorConfig with deputy email and timeout.
        _event_bus: EventBus for publishing escalation events.
        _audit: AuthorizationAuditLogger for audit trail.
        _timers: Dict mapping request_id to asyncio.Task.
        _start_times: Dict mapping request_id to start datetime.
        _lock: asyncio.Lock for thread-safe access to timers and start_times.
    """
    
    def __init__(
        self,
        config: "DeputyOperatorConfig",
        event_bus: Any,  # EventBus or mock
        audit_logger: Any,  # AuthorizationAuditLogger or mock
    ) -> None:
        """Initialize DeputyEscalationManager.
        
        Args:
            config: DeputyOperatorConfig with deputy operator settings.
            event_bus: EventBus for publishing escalation events.
            audit_logger: AuthorizationAuditLogger for audit trail.
        """
        self._config = config
        self._event_bus = event_bus
        self._audit = audit_logger
        self._timers: Dict[str, asyncio.Task] = {}
        self._start_times: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
    
    async def start_escalation_timer(self, request_id: str) -> None:
        """Start escalation countdown for an authorization request.
        
        If a timer already exists for this request, this is a no-op.
        
        Args:
            request_id: Unique identifier for the authorization request.
        """
        async with self._lock:
            if request_id in self._timers:
                logger.debug(
                    "Escalation timer already running for %s",
                    request_id,
                )
                return
            
            self._start_times[request_id] = datetime.now(timezone.utc)
            
            # Create async task for timeout
            task = asyncio.create_task(
                self._escalation_timer_task(request_id)
            )
            self._timers[request_id] = task
            
            logger.info(
                "Started escalation timer for %s (timeout: %s)",
                request_id,
                self._config.escalation_timeout,
            )
    
    async def _escalation_timer_task(self, request_id: str) -> None:
        """Internal task that waits for timeout then triggers escalation.
        
        Args:
            request_id: The request to escalate after timeout.
        """
        try:
            # Wait for the escalation timeout
            await asyncio.sleep(self._config.escalation_timeout.total_seconds())
            
            # Timeout expired - trigger escalation
            await self._on_escalation_timeout(request_id)
            
        except asyncio.CancelledError:
            # Timer was cancelled (primary responded)
            logger.debug(
                "Escalation timer cancelled for %s",
                request_id,
            )
            raise
    
    async def cancel_escalation_timer(self, request_id: str) -> None:
        """Cancel escalation timer (primary responded in time).
        
        Safe to call even if no timer exists for the request.
        
        Args:
            request_id: The request whose timer to cancel.
        """
        async with self._lock:
            task = self._timers.pop(request_id, None)
            self._start_times.pop(request_id, None)
            
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
                logger.info(
                    "Cancelled escalation timer for %s (primary responded)",
                    request_id,
                )
    
    def get_time_until_escalation(self, request_id: str) -> timedelta | None:
        """Get remaining time until escalation for a request.
        
        Note: This method accesses _start_times without holding the lock for
        performance reasons in read-heavy scenarios. The dict.get() operation
        is atomic in CPython, and we only read a snapshot of the start time.
        
        Args:
            request_id: The request to check.
            
        Returns:
            Remaining time as timedelta, or None if no timer exists.
        """
        # Read start_time snapshot - dict.get() is atomic in CPython
        start_time = self._start_times.get(request_id)
        if start_time is None:
            return None
        
        elapsed = datetime.now(timezone.utc) - start_time
        remaining = self._config.escalation_timeout - elapsed
        
        return max(remaining, timedelta(0))
    
    async def _on_escalation_timeout(self, request_id: str) -> None:
        """Handle escalation timeout - notify deputy operator.
        
        Called when the escalation timer expires without primary response.
        
        Args:
            request_id: The request that timed out.
        """
        async with self._lock:
            # Clean up timer state
            self._timers.pop(request_id, None)
            self._start_times.pop(request_id, None)
        
        escalated_at = datetime.now(timezone.utc).isoformat()
        
        # Log escalation event to audit trail
        try:
            await self._audit.log_escalation(
                request_id=request_id,
                deputy=self._config.deputy_operator,
            )
        except Exception as e:
            logger.error(
                "Failed to log escalation to audit: %s",
                str(e),
            )
        
        # Publish escalation event for TUI and deputy notification
        try:
            await self._event_bus.publish(
                "authorization:escalated",
                {
                    "request_id": request_id,
                    "deputy": self._config.deputy_operator,
                    "escalated_at": escalated_at,
                    "event_type": "AUTHORIZATION_ESCALATED",
                },
            )
        except Exception as e:
            logger.error(
                "Failed to publish escalation event: %s",
                str(e),
            )
        
        logger.warning(
            "Authorization request %s escalated to deputy %s",
            request_id,
            self._config.deputy_operator,
        )
    
    async def cancel_all_timers(self) -> None:
        """Cancel all active escalation timers.
        
        Used when engagement is paused or stopped.
        """
        async with self._lock:
            request_ids = list(self._timers.keys())
        
        for request_id in request_ids:
            await self.cancel_escalation_timer(request_id)
        
        logger.info("Cancelled all escalation timers")
    
    def get_active_escalations(self) -> list[str]:
        """Get list of request IDs with active escalation timers.
        
        Returns:
            List of request IDs currently awaiting escalation.
        """
        return list(self._timers.keys())


# =============================================================================
# Deputy Response Processing
# =============================================================================


async def process_deputy_response(
    response: DeputyResponse,
    queue: "AuthorizationQueue",
) -> bool:
    """Process a deputy operator's response to an escalated request.
    
    Removes the request from the authorization queue and applies
    the deputy's decision.
    
    Args:
        response: DeputyResponse with the deputy's decision.
        queue: AuthorizationQueue containing the pending request.
        
    Returns:
        True if the request was found and processed, False otherwise.
    """
    # Remove from queue
    removed = queue.remove_request(response.request_id)
    
    if removed:
        logger.info(
            "Processed deputy response for %s: %s",
            response.request_id,
            response.decision,
        )
    else:
        logger.warning(
            "Deputy response for unknown request: %s",
            response.request_id,
        )
    
    return removed
