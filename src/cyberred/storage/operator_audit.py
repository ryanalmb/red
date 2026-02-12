"""Append-Only Operator Audit Log for Story 13.2.

Provides tamper-evident audit logging for operator actions with:
- OperatorAction enum for action types
- OperatorAuditEntry dataclass for audit entries
- OperatorAuditLog for writing to Redis Streams with HMAC signing

Audit Entry Schema (per architecture.md and epics-stories.md):
- entry_id: UUID for the entry
- timestamp: ISO 8601 UTC timestamp
- engagement_id: Engagement identifier
- operator: Who performed the action
- action: OperatorAction enum value
- context: Additional context dict
- signature: HMAC-SHA256 signature

PRD Requirements:
- FR50: Append-only audit log
- NFR15: Tamper-evident audit trail
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

import structlog

if TYPE_CHECKING:
    from cyberred.storage.redis_client import RedisClient

log = structlog.get_logger()


# =============================================================================
# OperatorAction Enum
# =============================================================================

class OperatorAction(str, Enum):
    """Operator action types for audit logging.
    
    Inherits from str for JSON serialization compatibility.
    
    Values:
        APPROVE: Operator approved an authorization request
        DENY: Operator denied an authorization request
        KILL: Operator triggered kill switch
        SCOPE_CHANGE: Operator modified engagement scope
        PAUSE: Operator paused engagement
        RESUME: Operator resumed engagement
        START: Operator started engagement
        STOP: Operator stopped engagement
        WAIVER_ACCEPTED: Operator accepted pre-engagement waiver
        WAIVER_DECLINED: Operator declined pre-engagement waiver
    """
    APPROVE = "approve"
    DENY = "deny"
    KILL = "kill"
    SCOPE_CHANGE = "scope_change"
    PAUSE = "pause"
    RESUME = "resume"
    START = "start"
    STOP = "stop"
    WAIVER_ACCEPTED = "waiver_accepted"
    WAIVER_DECLINED = "waiver_declined"


# =============================================================================
# OperatorAuditEntry Dataclass
# =============================================================================

@dataclass
class OperatorAuditEntry:
    """Audit entry for operator actions.
    
    Captures all context required for tamper-evident audit trail per FR50/NFR15.
    
    Attributes:
        entry_id: Unique identifier (UUID) for this entry.
        timestamp: ISO 8601 UTC timestamp when action occurred.
        engagement_id: Engagement this action belongs to.
        operator: Username/identifier of the operator.
        action: Type of action performed (OperatorAction enum).
        context: Additional context dict (target, reason, etc.).
        signature: HMAC-SHA256 signature for tamper detection.
    """
    entry_id: str
    timestamp: datetime
    engagement_id: str
    operator: str
    action: OperatorAction
    context: dict[str, Any]
    signature: str
    
    def to_dict(self) -> dict[str, Any]:
        """Convert audit entry to dictionary for storage.
        
        Returns:
            Dictionary representation with ISO 8601 timestamp.
        """
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "engagement_id": self.engagement_id,
            "operator": self.operator,
            "action": self.action.value if isinstance(self.action, OperatorAction) else self.action,
            "context": self.context,
            "signature": self.signature,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OperatorAuditEntry":
        """Create OperatorAuditEntry from dictionary.
        
        Args:
            data: Dictionary with audit entry data.
            
        Returns:
            OperatorAuditEntry instance.
            
        Raises:
            ValueError: If required fields are missing or invalid.
        """
        # Validate required fields
        # Note: "context" is optional and defaults to {} if missing or None
        required_fields = ["entry_id", "timestamp", "engagement_id", "operator", "action", "context", "signature"]
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"Missing required field: {field_name}")
        
        # Parse timestamp
        timestamp = data["timestamp"]
        if isinstance(timestamp, str):
            # Parse ISO 8601 format
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        
        # Ensure timestamp is UTC
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        # Parse action
        action = data["action"]
        if isinstance(action, str):
            action = OperatorAction(action)
        
        # Parse context
        context = data.get("context", {})
        if context is None:
            context = {}
        
        return cls(
            entry_id=data["entry_id"],
            timestamp=timestamp,
            engagement_id=data["engagement_id"],
            operator=data["operator"],
            action=action,
            context=context,
            signature=data["signature"],
        )


# =============================================================================
# OperatorAuditLog Class
# =============================================================================

# Consumer group name for audit readers
AUDIT_CONSUMER_GROUP = "audit-readers"


class OperatorAuditLog:
    """Append-only audit log for operator actions.
    
    Writes audit entries to Redis Streams with HMAC-SHA256 signing for
    tamper detection. Provides NO delete, update, or clear methods to
    enforce append-only semantics.
    
    Attributes:
        _redis_client: Redis client for stream operations.
        _engagement_id: Engagement identifier.
        _stream_name: Redis Stream name (audit:{engagement_id}).
        _signing_key: HMAC signing key derived from engagement.
    """
    
    def __init__(
        self,
        redis_client: "RedisClient",
        engagement_id: str,
    ) -> None:
        """Initialize OperatorAuditLog.
        
        Args:
            redis_client: Redis client for stream operations.
            engagement_id: Engagement identifier for stream naming.
        """
        self._redis_client = redis_client
        self._engagement_id = engagement_id
        self._stream_name = f"audit:{engagement_id}"
        self._initialized = False
        
        # Derive signing key from engagement_id
        from cyberred.core.keystore import derive_key
        self._signing_key = derive_key(
            engagement_id,
            salt=b"operator-audit-hmac"
        )
    
    @property
    def stream_name(self) -> str:
        """Redis Stream name for this audit log."""
        return self._stream_name
    
    @property
    def engagement_id(self) -> str:
        """Engagement ID for this audit log."""
        return self._engagement_id
    
    async def initialize(self) -> None:
        """Initialize the audit log.
        
        Creates the consumer group if it doesn't exist.
        """
        if self._initialized:
            return
        
        # Create consumer group (creates stream if needed)
        await self._redis_client.xgroup_create(
            self._stream_name,
            AUDIT_CONSUMER_GROUP,
            start_id="0",  # Read all messages from beginning
            mkstream=True,
        )
        
        self._initialized = True
        log.info(
            "operator_audit_log_initialized",
            engagement_id=self._engagement_id,
            stream_name=self._stream_name,
        )
    
    def _compute_signature(
        self,
        entry_id: str,
        timestamp: str,
        operator: str,
        action: str,
        context: dict[str, Any],
    ) -> str:
        """Compute HMAC-SHA256 signature for audit entry.
        
        Args:
            entry_id: Entry UUID.
            timestamp: ISO 8601 timestamp string.
            operator: Operator identifier.
            action: Action type string.
            context: Context dict.
            
        Returns:
            Hex-encoded HMAC-SHA256 signature.
        """
        # Canonical format for signing
        sign_data = f"{entry_id}|{timestamp}|{operator}|{action}|{json.dumps(context, sort_keys=True)}"
        signature = hmac.new(
            self._signing_key,
            sign_data.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _verify_signature(self, entry: OperatorAuditEntry) -> bool:
        """Verify HMAC signature of an audit entry.
        
        Args:
            entry: Audit entry to verify.
            
        Returns:
            True if signature is valid, False otherwise.
        """
        try:
            timestamp_str = entry.timestamp.isoformat() if isinstance(entry.timestamp, datetime) else entry.timestamp
            action_str = entry.action.value if isinstance(entry.action, OperatorAction) else entry.action
            
            expected_sig = self._compute_signature(
                entry.entry_id,
                timestamp_str,
                entry.operator,
                action_str,
                entry.context,
            )
            
            return hmac.compare_digest(entry.signature, expected_sig)
        except Exception:
            # Ensure constant-time failure - don't leak timing info on exceptions
            return False
    
    async def log_action(
        self,
        operator: str,
        action: OperatorAction,
        context: dict[str, Any],
    ) -> OperatorAuditEntry:
        """Log an operator action to the audit stream.
        
        Args:
            operator: Username/identifier of the operator.
            action: Type of action performed.
            context: Additional context (target, reason, etc.).
            
        Returns:
            The created OperatorAuditEntry.
            
        Raises:
            ConnectionError: If not connected to Redis.
        """
        # Generate entry fields
        entry_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        timestamp_str = timestamp.isoformat()
        action_str = action.value
        
        # Compute signature
        signature = self._compute_signature(
            entry_id,
            timestamp_str,
            operator,
            action_str,
            context,
        )
        
        # Create entry
        entry = OperatorAuditEntry(
            entry_id=entry_id,
            timestamp=timestamp,
            engagement_id=self._engagement_id,
            operator=operator,
            action=action,
            context=context,
            signature=signature,
        )
        
        # Write to Redis Stream using xadd
        # Note: RedisClient.xadd adds its own HMAC layer, but we also
        # include our application-level signature in the entry data
        await self._redis_client.xadd(
            self._stream_name,
            entry.to_dict(),
        )
        
        log.info(
            "operator_action_logged",
            entry_id=entry_id,
            operator=operator,
            action=action_str,
            engagement_id=self._engagement_id,
        )
        
        return entry
    
    async def get_entries(
        self,
        start_id: str = "0",
        count: int = 100,
    ) -> list[OperatorAuditEntry]:
        """Get audit entries from the stream.
        
        Args:
            start_id: Start reading after this ID ("0" for all).
            count: Maximum entries to return.
            
        Returns:
            List of verified OperatorAuditEntry objects.
            Entries with invalid signatures are filtered out.
            
        Raises:
            ConnectionError: If not connected to Redis.
        """
        # Read entries using xread
        raw_entries = await self._redis_client.xread(
            self._stream_name,
            start_id,
            count=count,
        )
        
        entries: list[OperatorAuditEntry] = []
        
        for stream_entry_id, data in raw_entries:
            try:
                # Parse entry from dict
                entry = OperatorAuditEntry.from_dict(data)
                
                # Verify application-level signature
                if self._verify_signature(entry):
                    entries.append(entry)
                else:
                    log.warning(
                        "audit_entry_signature_invalid",
                        entry_id=entry.entry_id,
                        stream_entry_id=stream_entry_id,
                    )
            except (ValueError, KeyError, TypeError) as e:
                log.warning(
                    "audit_entry_parse_failed",
                    stream_entry_id=stream_entry_id,
                    error=str(e),
                )
                continue
        
        return entries
    
    async def verify_integrity(self, entry_id: str) -> bool:
        """Verify integrity of a specific audit entry.
        
        Args:
            entry_id: UUID of the entry to verify.
            
        Returns:
            True if entry exists and signature is valid, False otherwise.
        """
        # Get all entries and search for the specific one
        # Entries are already verified during get_entries
        entries = await self.get_entries(start_id="0", count=10000)
        
        for entry in entries:
            if entry.entry_id == entry_id:
                # Entry was already verified during get_entries
                return True
        
        return False
    
    async def verify_chain(
        self,
        start_id: str = "0",
        end_id: str = "+",
    ) -> tuple[bool, list[str]]:
        """Verify integrity of the entire audit chain.
        
        Args:
            start_id: Start of range to verify.
            end_id: End of range to verify.
            
        Returns:
            Tuple of (all_valid, list_of_invalid_entry_ids).
            
        Note:
            The end_id parameter is used in the xrange call to limit the range.
        """
        # Read raw entries directly from Redis to check all entries
        # including ones that might fail signature verification
        if not self._redis_client._master:
            return (False, [])
        
        try:
            # Use start_id and end_id to limit the range
            # Convert "0" to "-" for Redis xrange syntax
            range_start = "-" if start_id == "0" else start_id
            range_end = end_id
            raw_entries = await self._redis_client._master.xrange(
                self._stream_name,
                range_start,
                range_end,
            )
        except Exception as e:
            log.error("verify_chain_read_failed", error=str(e))
            return (False, [])
        
        invalid_ids: list[str] = []
        
        for stream_entry_id, fields in raw_entries:
            if isinstance(stream_entry_id, bytes):
                stream_entry_id = stream_entry_id.decode()
            
            # Get payload field
            payload = fields.get(b"payload") or fields.get("payload")
            if isinstance(payload, bytes):
                payload = payload.decode()
            
            if not payload:
                invalid_ids.append(stream_entry_id)
                continue
            
            try:
                # Parse the signed package from RedisClient
                import json
                package = json.loads(payload)
                content = package.get("content")
                sig = package.get("sig")
                
                if not content or not sig:
                    invalid_ids.append(stream_entry_id)
                    continue
                
                # Verify RedisClient-level signature
                redis_verified = self._redis_client._verify_message(payload)
                if redis_verified is None:
                    invalid_ids.append(stream_entry_id)
                    continue
                
                # Parse entry data
                data = json.loads(redis_verified)
                entry = OperatorAuditEntry.from_dict(data)
                
                # Verify application-level signature
                if not self._verify_signature(entry):
                    invalid_ids.append(entry.entry_id)
                    
            except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
                invalid_ids.append(stream_entry_id)
                continue
        
        all_valid = len(invalid_ids) == 0
        return (all_valid, invalid_ids)


# =============================================================================
# Factory Functions (Singleton Pattern)
# =============================================================================

_operator_audit_log: Optional[OperatorAuditLog] = None


def get_operator_audit_log() -> Optional[OperatorAuditLog]:
    """Get the current OperatorAuditLog instance.
    
    Returns:
        The current OperatorAuditLog or None if not initialized.
    """
    return _operator_audit_log


def set_operator_audit_log(audit_log: Optional[OperatorAuditLog]) -> None:
    """Set the OperatorAuditLog instance.
    
    Args:
        audit_log: The OperatorAuditLog instance to set, or None to clear.
    """
    global _operator_audit_log
    _operator_audit_log = audit_log


async def init_operator_audit_log(
    redis_client: "RedisClient",
    engagement_id: str,
) -> OperatorAuditLog:
    """Initialize and return an OperatorAuditLog instance.
    
    Creates the audit log and sets it as the global instance.
    
    Args:
        redis_client: Redis client for stream operations.
        engagement_id: Engagement identifier.
        
    Returns:
        Initialized OperatorAuditLog instance.
    """
    global _operator_audit_log
    
    audit_log = OperatorAuditLog(redis_client, engagement_id)
    await audit_log.initialize()
    
    _operator_audit_log = audit_log
    return audit_log
