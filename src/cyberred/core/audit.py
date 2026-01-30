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


# ─────────────────────────────────────────────────────────────────────────────
# ExportAuditLogger - Story 11.3
# ─────────────────────────────────────────────────────────────────────────────

EXPORT_AUDIT_STREAM_NAME = "cyberred:audit:exports"


@dataclass
class ExportAuditEntry:
    """Audit entry for data export events.
    
    Story 11.3: Data Export from TUI
    
    Captures export operations for audit trail compliance per FR50-54.
    Per AC #2: Export is logged to audit trail with item_id, destination, timestamp.
    
    Attributes:
        event_type: Type of export event (single_export, archive_export).
        timestamp: ISO 8601 timestamp of the export.
        item_id: ID of exported item (for single exports).
        item_ids: List of item IDs (for archive exports).
        filename: Original filename of exported item.
        destination: Destination path where file was exported.
        item_count: Number of items exported (for archives).
        engagement_name: Name of the engagement.
        operator: Who initiated the export.
    """
    event_type: str
    destination: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    item_id: str | None = None
    item_ids: list[str] | None = None
    filename: str | None = None
    item_count: int | None = None
    engagement_name: str | None = None
    operator: str = "operator"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert audit entry to dictionary for storage.
        
        Returns:
            Dictionary representation of the audit entry.
        """
        result = {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "destination": self.destination,
            "operator": self.operator,
        }
        if self.item_id is not None:
            result["item_id"] = self.item_id
        if self.item_ids is not None:
            result["item_ids"] = self.item_ids
        if self.filename is not None:
            result["filename"] = self.filename
        if self.item_count is not None:
            result["item_count"] = self.item_count
        if self.engagement_name is not None:
            result["engagement_name"] = self.engagement_name
        return result


class ExportAuditLogger:
    """Audit logger for data export operations.
    
    Story 11.3: Data Export from TUI
    
    Writes export audit entries to Redis Streams for append-only audit trail.
    Implements AC #2: Export is logged to audit trail.
    
    Attributes:
        _redis_client: Redis client for stream operations (optional).
        _stream_name: Name of the audit stream.
    """
    
    def __init__(
        self,
        redis_client: Optional["RedisClient"] = None,
        stream_name: str = EXPORT_AUDIT_STREAM_NAME,
    ) -> None:
        """Initialize ExportAuditLogger.
        
        Args:
            redis_client: Redis client for stream operations (optional for offline mode).
            stream_name: Name of the audit stream.
        """
        self._redis_client = redis_client
        self._stream_name = stream_name
    
    def log_export(
        self,
        item_id: str,
        filename: str,
        destination: str,
        engagement_name: str | None = None,
        operator: str = "operator",
    ) -> None:
        """Log a single item export to audit trail.
        
        Per AC #2: Export is logged to audit trail with item_id, destination, timestamp.
        
        Args:
            item_id: ID of the exported item.
            filename: Original filename of the item.
            destination: Path where file was exported.
            engagement_name: Name of the engagement.
            operator: Who initiated the export.
        """
        entry = ExportAuditEntry(
            event_type="single_export",
            item_id=item_id,
            filename=filename,
            destination=destination,
            engagement_name=engagement_name,
            operator=operator,
        )
        
        self._write_entry(entry)
    
    def log_archive_export(
        self,
        item_ids: list[str],
        destination: str,
        item_count: int,
        engagement_name: str | None = None,
        operator: str = "operator",
    ) -> None:
        """Log an archive export to audit trail.
        
        Per AC #4: Archive includes manifest.json with metadata.
        
        Args:
            item_ids: List of exported item IDs.
            destination: Path where archive was exported.
            item_count: Number of items in the archive.
            engagement_name: Name of the engagement.
            operator: Who initiated the export.
        """
        entry = ExportAuditEntry(
            event_type="archive_export",
            item_ids=item_ids,
            destination=destination,
            item_count=item_count,
            engagement_name=engagement_name,
            operator=operator,
        )
        
        self._write_entry(entry)
    
    def _write_entry(self, entry: ExportAuditEntry) -> None:
        """Write audit entry to storage.
        
        Handles both sync and async contexts gracefully:
        - In async context (loop running): Creates a task to write asynchronously
        - In sync context (no loop): Runs the coroutine to completion
        - Fallback: Logs locally if Redis write fails
        
        This pattern ensures audit logging never blocks the main export operation
        while still attempting to persist to Redis when available.
        
        Args:
            entry: ExportAuditEntry to write.
        """
        entry_dict = entry.to_dict()
        
        # Log locally regardless of Redis availability
        logger.info(
            "Export audit: %s -> %s (type=%s)",
            entry.item_id or f"{entry.item_count} items",
            entry.destination,
            entry.event_type,
        )
        
        # Write to Redis if available
        if self._redis_client is not None:
            try:
                import asyncio
                try:
                    # Python 3.10+: Use get_running_loop() to check if we're in async context
                    loop = asyncio.get_running_loop()
                    # We're in an async context, schedule the write as a task
                    asyncio.create_task(
                        self._redis_client.xadd(self._stream_name, entry_dict)
                    )
                except RuntimeError:
                    # No running loop - we're in sync context, run to completion
                    asyncio.run(
                        self._redis_client.xadd(self._stream_name, entry_dict)
                    )
            except Exception as e:
                # Log error but don't raise - audit logging should not block operation
                logger.warning("Failed to write export audit to Redis: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Module-level export audit logger instance (singleton pattern)
# ─────────────────────────────────────────────────────────────────────────────

_export_audit_logger_instance: ExportAuditLogger | None = None


def get_export_audit_logger() -> ExportAuditLogger | None:
    """Get the global export audit logger instance.
    
    Returns:
        ExportAuditLogger instance, or None if not initialized.
    """
    return _export_audit_logger_instance


def set_export_audit_logger(logger_instance: ExportAuditLogger | None) -> None:
    """Set the global export audit logger instance.
    
    Args:
        logger_instance: ExportAuditLogger instance to set, or None to reset.
    """
    global _export_audit_logger_instance
    _export_audit_logger_instance = logger_instance


def init_export_audit_logger(
    redis_client: Optional["RedisClient"] = None,
) -> ExportAuditLogger:
    """Initialize and set the global export audit logger.
    
    Args:
        redis_client: Redis client for stream operations (optional).
        
    Returns:
        Initialized ExportAuditLogger instance.
    """
    export_logger = ExportAuditLogger(redis_client)
    set_export_audit_logger(export_logger)
    return export_logger


# ─────────────────────────────────────────────────────────────────────────────
# DeletionAuditLogger - Story 11.4
# ─────────────────────────────────────────────────────────────────────────────

DELETION_AUDIT_STREAM_NAME = "cyberred:audit:deletions"


@dataclass
class DeletionAuditEntry:
    """Audit entry for data deletion events.
    
    Story 11.4: Manual Data Deletion
    
    Captures deletion operations for audit trail compliance per FR50-54.
    Per FR45: All deletions logged to audit trail with item_id, timestamp.
    
    Attributes:
        event_type: Type of deletion event (single_deletion, bulk_deletion).
        timestamp: ISO 8601 timestamp of the deletion.
        item_id: ID of deleted item (for single deletions).
        item_ids: List of item IDs (for bulk deletions).
        filename: Original filename of deleted item.
        target: Target host where data originated.
        size_bytes: Size of deleted data.
        total_deleted: Number of items deleted (for bulk).
        total_failed: Number of items that failed (for bulk).
        operator: Who initiated the deletion.
    """
    event_type: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    item_id: str | None = None
    item_ids: list[str] | None = None
    filename: str | None = None
    target: str | None = None
    size_bytes: int | None = None
    total_deleted: int | None = None
    total_failed: int | None = None
    operator: str = "operator"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert audit entry to dictionary for storage.
        
        Returns:
            Dictionary representation of the audit entry.
        """
        result = {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "operator": self.operator,
        }
        if self.item_id is not None:
            result["item_id"] = self.item_id
        if self.item_ids is not None:
            result["item_ids"] = self.item_ids
        if self.filename is not None:
            result["filename"] = self.filename
        if self.target is not None:
            result["target"] = self.target
        if self.size_bytes is not None:
            result["size_bytes"] = self.size_bytes
        if self.total_deleted is not None:
            result["total_deleted"] = self.total_deleted
        if self.total_failed is not None:
            result["total_failed"] = self.total_failed
        return result


class DeletionAuditLogger:
    """Audit logger for data deletion operations.
    
    Story 11.4: Manual Data Deletion
    
    Writes deletion audit entries to Redis Streams for append-only audit trail.
    Implements FR45: All deletions logged to audit trail.
    
    Attributes:
        _redis_client: Redis client for stream operations (optional).
        _stream_name: Name of the audit stream.
    """
    
    def __init__(
        self,
        redis_client: Optional["RedisClient"] = None,
        stream_name: str = DELETION_AUDIT_STREAM_NAME,
    ) -> None:
        """Initialize DeletionAuditLogger.
        
        Args:
            redis_client: Redis client for stream operations (optional for offline mode).
            stream_name: Name of the audit stream.
        """
        self._redis_client = redis_client
        self._stream_name = stream_name
    
    def log_deletion(
        self,
        item_id: str,
        filename: str,
        target: str,
        size_bytes: int,
        operator: str = "operator",
    ) -> None:
        """Log a single item deletion to audit trail.
        
        Per FR45: All deletions logged to audit trail with item_id, timestamp.
        
        Args:
            item_id: ID of the deleted item.
            filename: Original filename of the item.
            target: Target host where data originated.
            size_bytes: Size of deleted data.
            operator: Who initiated the deletion.
        """
        entry = DeletionAuditEntry(
            event_type="single_deletion",
            item_id=item_id,
            filename=filename,
            target=target,
            size_bytes=size_bytes,
            operator=operator,
        )
        
        self._write_entry(entry)
    
    def log_bulk_deletion(
        self,
        item_ids: list[str],
        total_deleted: int,
        total_failed: int,
        operator: str = "operator",
    ) -> None:
        """Log a bulk deletion to audit trail.
        
        Args:
            item_ids: List of deleted item IDs.
            total_deleted: Number of items successfully deleted.
            total_failed: Number of items that failed to delete.
            operator: Who initiated the deletion.
        """
        entry = DeletionAuditEntry(
            event_type="bulk_deletion",
            item_ids=item_ids,
            total_deleted=total_deleted,
            total_failed=total_failed,
            operator=operator,
        )
        
        self._write_entry(entry)
    
    def _write_entry(self, entry: DeletionAuditEntry) -> None:
        """Write audit entry to storage.
        
        Handles both sync and async contexts gracefully:
        - In async context (loop running): Creates a task to write asynchronously
        - In sync context (no loop): Runs the coroutine to completion
        - Fallback: Logs locally if Redis write fails
        
        This pattern ensures audit logging never blocks the main deletion operation
        while still attempting to persist to Redis when available.
        
        Args:
            entry: DeletionAuditEntry to write.
        """
        entry_dict = entry.to_dict()
        
        # Log locally regardless of Redis availability
        logger.info(
            "Deletion audit: %s (type=%s, operator=%s)",
            entry.item_id or f"{entry.total_deleted} items",
            entry.event_type,
            entry.operator,
        )
        
        # Write to Redis if available
        if self._redis_client is not None:
            try:
                import asyncio
                try:
                    # Python 3.10+: Use get_running_loop() to check if we're in async context
                    loop = asyncio.get_running_loop()
                    # We're in an async context, schedule the write as a task
                    asyncio.create_task(
                        self._redis_client.xadd(self._stream_name, entry_dict)
                    )
                except RuntimeError:
                    # No running loop - we're in sync context, run to completion
                    asyncio.run(
                        self._redis_client.xadd(self._stream_name, entry_dict)
                    )
            except Exception as e:
                # Log error but don't raise - audit logging should not block operation
                logger.warning("Failed to write deletion audit to Redis: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Module-level deletion audit logger instance (singleton pattern)
# ─────────────────────────────────────────────────────────────────────────────

_deletion_audit_logger_instance: DeletionAuditLogger | None = None


def get_deletion_audit_logger() -> DeletionAuditLogger | None:
    """Get the global deletion audit logger instance.
    
    Returns:
        DeletionAuditLogger instance, or None if not initialized.
    """
    return _deletion_audit_logger_instance


def set_deletion_audit_logger(logger_instance: DeletionAuditLogger | None) -> None:
    """Set the global deletion audit logger instance.
    
    Args:
        logger_instance: DeletionAuditLogger instance to set, or None to reset.
    """
    global _deletion_audit_logger_instance
    _deletion_audit_logger_instance = logger_instance


def init_deletion_audit_logger(
    redis_client: Optional["RedisClient"] = None,
) -> DeletionAuditLogger:
    """Initialize and set the global deletion audit logger.
    
    Args:
        redis_client: Redis client for stream operations (optional).
        
    Returns:
        Initialized DeletionAuditLogger instance.
    """
    deletion_logger = DeletionAuditLogger(redis_client)
    set_deletion_audit_logger(deletion_logger)
    return deletion_logger
