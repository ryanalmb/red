"""Authorization Audit Logger for Story 10.2.

Provides audit logging for authorization response events with:
- AuthorizationAuditEntry dataclass for audit entries
- AuthorizationAuditLogger for writing to Redis Streams
- Integration with audit:stream channel per architecture.md

Audit Entry Schema (per architecture.md lines 686-691):
- event_type: "authorization_response"
- timestamp: ISO 8601 timestamp
- request_id: Original authorization request ID
- decision: APPROVED | DENIED | SKIPPED
- operator: Who made the decision
- constraints: Optional constraints dict
- context: Request context (target, agent_id, etc.)
- batch_apply: Whether applied to similar requests
- auto_denied: Whether auto-denied due to timeout
- delivery_latency_ms: Delivery latency measurement
- swarm_snapshot: Agent distribution at request time

PRD Requirements (FR50-54):
- FR50: Append-only audit log
- FR51: Decision context logging
- FR52: Timestamp integrity
- FR53: Cryptographic proof (SHA-256) - handled by RedisClient.xadd
- FR54: Evidence chain of custody
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from cyberred.storage.redis_client import RedisClient

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

AUDIT_STREAM_NAME = "audit:stream"


# ─────────────────────────────────────────────────────────────────────────────
# AuthorizationAuditEntry
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AuthorizationAuditEntry:
    """Audit entry for authorization response events.
    
    Captures all context required for audit trail compliance per FR50-54.
    
    Attributes:
        event_type: Always "authorization_response" for this entry type.
        timestamp: ISO 8601 timestamp of the decision.
        request_id: Original authorization request ID.
        decision: Authorization decision (APPROVED/DENIED/SKIPPED).
        operator: Who made the decision (username or "system" for auto-deny).
        constraints: Optional constraints dict if approval with constraints.
        context: Request context (target, agent_id, risk_level, request_type).
        batch_apply: Whether decision applies to similar requests.
        auto_denied: Whether this was an automatic denial due to timeout.
        delivery_latency_ms: Delivery latency in milliseconds (NFR5 tracking).
        swarm_snapshot: Agent distribution at request time.
    """
    request_id: str
    decision: str
    operator: str
    event_type: str = "authorization_response"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    constraints: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    batch_apply: bool = False
    auto_denied: bool = False
    delivery_latency_ms: float | None = None
    swarm_snapshot: dict[str, Any] | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert audit entry to dictionary for storage.
        
        Returns:
            Dictionary representation of the audit entry.
        """
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "decision": self.decision,
            "operator": self.operator,
            "constraints": self.constraints,
            "context": self.context,
            "batch_apply": self.batch_apply,
            "auto_denied": self.auto_denied,
            "delivery_latency_ms": self.delivery_latency_ms,
            "swarm_snapshot": self.swarm_snapshot,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuthorizationAuditEntry":
        """Create AuthorizationAuditEntry from dictionary.
        
        Args:
            data: Dictionary with audit entry data.
            
        Returns:
            AuthorizationAuditEntry instance.
        """
        return cls(
            event_type=data.get("event_type", "authorization_response"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            request_id=data.get("request_id", "unknown"),
            decision=data.get("decision", "UNKNOWN"),
            operator=data.get("operator", "unknown"),
            constraints=data.get("constraints"),
            context=data.get("context"),
            batch_apply=data.get("batch_apply", False),
            auto_denied=data.get("auto_denied", False),
            delivery_latency_ms=data.get("delivery_latency_ms"),
            swarm_snapshot=data.get("swarm_snapshot"),
        )


# ─────────────────────────────────────────────────────────────────────────────
# AuthorizationAuditLogger
# ─────────────────────────────────────────────────────────────────────────────

class AuthorizationAuditLogger:
    """Audit logger for authorization response events.
    
    Writes audit entries to Redis Streams for append-only audit trail.
    Uses RedisClient.xadd which includes HMAC-SHA256 signing per FR53.
    
    Attributes:
        _redis_client: Redis client for stream operations.
        _stream_name: Name of the audit stream (default: "audit:stream").
    """
    
    def __init__(
        self,
        redis_client: "RedisClient",
        stream_name: str = AUDIT_STREAM_NAME,
    ) -> None:
        """Initialize AuthorizationAuditLogger.
        
        Args:
            redis_client: Redis client for stream operations.
            stream_name: Name of the audit stream.
        """
        self._redis_client = redis_client
        self._stream_name = stream_name
    
    async def log(self, entry: AuthorizationAuditEntry) -> str | None:
        """Log an authorization audit entry to the stream.
        
        Args:
            entry: AuthorizationAuditEntry to log.
            
        Returns:
            Stream entry ID if successful, None on failure.
        """
        try:
            entry_dict = entry.to_dict()
            
            entry_id = await self._redis_client.xadd(
                self._stream_name,
                entry_dict,
            )
            
            logger.info(
                "Authorization audit logged: %s (decision=%s, request=%s)",
                entry_id,
                entry.decision,
                entry.request_id,
            )
            
            return entry_id
            
        except Exception as e:
            # Log error but don't raise - audit logging should not block operation
            logger.error(
                "Failed to log authorization audit: %s (request=%s)",
                str(e),
                entry.request_id,
            )
            return None
    
    async def log_response(
        self,
        response: dict[str, Any],
    ) -> str | None:
        """Log an authorization response from response dict.
        
        Convenience method that creates an AuthorizationAuditEntry from
        a response dictionary (e.g., from AuthorizationScreen).
        
        Args:
            response: Response dictionary with authorization decision details.
            
        Returns:
            Stream entry ID if successful, None on failure.
        """
        # Build context from response
        context = {}
        for key in ["target", "agent_id", "risk_level", "request_type"]:
            if key in response:
                context[key] = response[key]
        
        entry = AuthorizationAuditEntry(
            request_id=response.get("request_id", "unknown"),
            decision=response.get("decision", "UNKNOWN"),
            operator=response.get("operator", "operator"),
            constraints=response.get("constraints"),
            context=context if context else None,
            batch_apply=response.get("batch_apply", False),
            auto_denied=response.get("auto_denied", False),
            delivery_latency_ms=response.get("delivery_latency_ms"),
            swarm_snapshot=response.get("swarm_snapshot"),
        )
        
        return await self.log(entry)


# ─────────────────────────────────────────────────────────────────────────────
# Module-level audit logger instance (singleton pattern)
# ─────────────────────────────────────────────────────────────────────────────

_audit_logger_instance: AuthorizationAuditLogger | None = None


def get_audit_logger() -> AuthorizationAuditLogger | None:
    """Get the global audit logger instance.
    
    Returns:
        AuthorizationAuditLogger instance, or None if not initialized.
    """
    return _audit_logger_instance


def set_audit_logger(logger: AuthorizationAuditLogger) -> None:
    """Set the global audit logger instance.
    
    Args:
        logger: AuthorizationAuditLogger instance to set.
    """
    global _audit_logger_instance
    _audit_logger_instance = logger


def init_audit_logger(redis_client: "RedisClient") -> AuthorizationAuditLogger:
    """Initialize and set the global audit logger.
    
    Args:
        redis_client: Redis client for stream operations.
        
    Returns:
        Initialized AuthorizationAuditLogger instance.
    """
    audit_logger = AuthorizationAuditLogger(redis_client)
    set_audit_logger(audit_logger)
    return audit_logger


# ─────────────────────────────────────────────────────────────────────────────
# AlertAuditLogger - Story 10.7
# ─────────────────────────────────────────────────────────────────────────────

ALERT_AUDIT_STREAM_NAME = "cyberred:audit:alerts"


class AlertAuditLogger:
    """Audit logger for situational alert responses.
    
    Writes audit entries to Redis Streams for append-only audit trail.
    Stream name pattern: cyberred:audit:alerts:{engagement_id}
    
    Implements FR23: Alert response logging to audit trail.
    
    Attributes:
        _redis_client: Redis client for stream operations.
        _stream_name: Base name of the audit stream.
    """
    
    def __init__(
        self,
        redis_client: "RedisClient",
        stream_name: str = ALERT_AUDIT_STREAM_NAME,
    ) -> None:
        """Initialize AlertAuditLogger.
        
        Args:
            redis_client: Redis client for stream operations.
            stream_name: Base name of the audit stream (engagement_id appended).
        """
        self._redis_client = redis_client
        self._stream_name = stream_name
    
    async def log_response(
        self,
        alert: Any,
        response: Any,
        engagement_id: str,
    ) -> str | None:
        """Log alert response to audit stream.
        
        Creates audit entry per FR23 specification and writes to Redis Stream.
        
        Args:
            alert: AlertTrigger instance with alert details.
            response: AlertResponse instance with operator decision.
            engagement_id: Engagement ID for stream key.
            
        Returns:
            Stream entry ID if successful, None on failure.
        """
        try:
            # Import here to avoid circular imports
            from cyberred.core.alerts import create_audit_entry
            
            entry = create_audit_entry(alert, response)
            stream_key = f"{self._stream_name}:{engagement_id}"
            
            entry_id = await self._redis_client.xadd(stream_key, entry)
            
            logger.info(
                "Alert audit logged: %s (decision=%s, alert=%s)",
                entry_id,
                response.decision.value if hasattr(response.decision, 'value') else response.decision,
                alert.id,
            )
            
            return entry_id
            
        except Exception as e:
            # Log error but don't raise - audit logging should not block operation
            logger.error(
                "Failed to log alert audit: %s (alert=%s)",
                str(e),
                alert.id if hasattr(alert, 'id') else 'unknown',
            )
            return None
    
    async def get_responses_for_engagement(
        self,
        engagement_id: str,
        limit: int = 100,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Retrieve alert responses for an engagement ordered by timestamp.
        
        Args:
            engagement_id: Engagement ID to query.
            limit: Maximum number of entries to return.
            
        Returns:
            List of (entry_id, entry_data) tuples ordered by timestamp.
        """
        try:
            stream_key = f"{self._stream_name}:{engagement_id}"
            
            entries = await self._redis_client.xrange(
                stream_key,
                "-",
                "+",
                count=limit,
            )
            
            return entries
            
        except Exception as e:
            logger.error(
                "Failed to get alert responses: %s (engagement=%s)",
                str(e),
                engagement_id,
            )
            return []
    
    async def get_responses_by_alert_type(
        self,
        engagement_id: str,
        alert_type: Any,
        limit: int = 100,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Retrieve alert responses filtered by alert type.
        
        Args:
            engagement_id: Engagement ID to query.
            alert_type: AlertType enum value to filter by.
            limit: Maximum number of entries to retrieve before filtering.
            
        Returns:
            List of (entry_id, entry_data) tuples matching alert_type.
        """
        # Get all entries then filter
        all_entries = await self.get_responses_for_engagement(
            engagement_id,
            limit=limit,
        )
        
        # Filter by alert_type
        alert_type_value = alert_type.value if hasattr(alert_type, 'value') else str(alert_type)
        
        return [
            (entry_id, entry_data)
            for entry_id, entry_data in all_entries
            if entry_data.get("alert_type") == alert_type_value
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Module-level alert audit logger instance (singleton pattern)
# ─────────────────────────────────────────────────────────────────────────────

_alert_audit_logger_instance: AlertAuditLogger | None = None


def get_alert_audit_logger() -> AlertAuditLogger | None:
    """Get the global alert audit logger instance.
    
    Returns:
        AlertAuditLogger instance, or None if not initialized.
    """
    return _alert_audit_logger_instance


def set_alert_audit_logger(logger_instance: AlertAuditLogger | None) -> None:
    """Set the global alert audit logger instance.
    
    Args:
        logger_instance: AlertAuditLogger instance to set, or None to reset.
    """
    global _alert_audit_logger_instance
    _alert_audit_logger_instance = logger_instance


def init_alert_audit_logger(redis_client: "RedisClient") -> AlertAuditLogger:
    """Initialize and set the global alert audit logger.
    
    Args:
        redis_client: Redis client for stream operations.
        
    Returns:
        Initialized AlertAuditLogger instance.
    """
    alert_logger = AlertAuditLogger(redis_client)
    set_alert_audit_logger(alert_logger)
    return alert_logger
