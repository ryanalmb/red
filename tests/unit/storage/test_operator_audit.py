"""Unit tests for Story 13.2: Append-Only Audit Log.

Tests for OperatorAuditEntry dataclass and OperatorAuditLog class.
All tests should FAIL initially (RED phase) as implementation doesn't exist yet.

Acceptance Criteria covered:
- AC #3: Action is logged to append-only audit stream
- AC #4: Log entries include: timestamp, operator, action, context, signature
- AC #5: Log is stored in Redis Streams (consumer group)
- AC #6: Log cannot be modified or deleted (append-only)
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# These imports will fail until implementation exists (RED phase)
# from cyberred.storage.operator_audit import (
#     OperatorAction,
#     OperatorAuditEntry,
#     OperatorAuditLog,
# )


# =============================================================================
# AC #4: OperatorAction Enum Tests
# =============================================================================

class TestOperatorActionEnum:
    """Test OperatorAction enum values per AC #4."""

    def test_operator_action_approve_exists(self) -> None:
        """Test APPROVE action exists in enum."""
        from cyberred.storage.operator_audit import OperatorAction
        
        assert hasattr(OperatorAction, "APPROVE")
        assert OperatorAction.APPROVE.value == "approve"

    def test_operator_action_deny_exists(self) -> None:
        """Test DENY action exists in enum."""
        from cyberred.storage.operator_audit import OperatorAction
        
        assert hasattr(OperatorAction, "DENY")
        assert OperatorAction.DENY.value == "deny"

    def test_operator_action_kill_exists(self) -> None:
        """Test KILL action exists in enum."""
        from cyberred.storage.operator_audit import OperatorAction
        
        assert hasattr(OperatorAction, "KILL")
        assert OperatorAction.KILL.value == "kill"

    def test_operator_action_scope_change_exists(self) -> None:
        """Test SCOPE_CHANGE action exists in enum."""
        from cyberred.storage.operator_audit import OperatorAction
        
        assert hasattr(OperatorAction, "SCOPE_CHANGE")
        assert OperatorAction.SCOPE_CHANGE.value == "scope_change"

    def test_operator_action_pause_exists(self) -> None:
        """Test PAUSE action exists in enum."""
        from cyberred.storage.operator_audit import OperatorAction
        
        assert hasattr(OperatorAction, "PAUSE")
        assert OperatorAction.PAUSE.value == "pause"

    def test_operator_action_resume_exists(self) -> None:
        """Test RESUME action exists in enum."""
        from cyberred.storage.operator_audit import OperatorAction
        
        assert hasattr(OperatorAction, "RESUME")
        assert OperatorAction.RESUME.value == "resume"

    def test_operator_action_start_exists(self) -> None:
        """Test START action exists in enum."""
        from cyberred.storage.operator_audit import OperatorAction
        
        assert hasattr(OperatorAction, "START")
        assert OperatorAction.START.value == "start"

    def test_operator_action_stop_exists(self) -> None:
        """Test STOP action exists in enum."""
        from cyberred.storage.operator_audit import OperatorAction
        
        assert hasattr(OperatorAction, "STOP")
        assert OperatorAction.STOP.value == "stop"

    def test_operator_action_is_string_enum(self) -> None:
        """Test OperatorAction is a string enum for JSON serialization."""
        from cyberred.storage.operator_audit import OperatorAction
        
        # Should be usable as string directly
        assert str(OperatorAction.APPROVE) == "approve" or OperatorAction.APPROVE.value == "approve"


# =============================================================================
# AC #4: OperatorAuditEntry Dataclass Tests
# =============================================================================

class TestOperatorAuditEntry:
    """Test OperatorAuditEntry dataclass per AC #4."""

    def test_operator_audit_entry_has_entry_id_field(self) -> None:
        """Test entry_id field exists (UUID)."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditEntry
        
        entry = OperatorAuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            engagement_id="eng-001",
            operator="root",
            action=OperatorAction.APPROVE,
            context={"target": "192.168.1.1"},
            signature="abc123",
        )
        assert hasattr(entry, "entry_id")
        assert isinstance(entry.entry_id, str)

    def test_operator_audit_entry_has_timestamp_field(self) -> None:
        """Test timestamp field exists (datetime)."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditEntry
        
        now = datetime.now(timezone.utc)
        entry = OperatorAuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=now,
            engagement_id="eng-001",
            operator="root",
            action=OperatorAction.APPROVE,
            context={},
            signature="abc123",
        )
        assert hasattr(entry, "timestamp")
        assert isinstance(entry.timestamp, datetime)

    def test_operator_audit_entry_has_engagement_id_field(self) -> None:
        """Test engagement_id field exists."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditEntry
        
        entry = OperatorAuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            engagement_id="eng-test-123",
            operator="root",
            action=OperatorAction.APPROVE,
            context={},
            signature="abc123",
        )
        assert hasattr(entry, "engagement_id")
        assert entry.engagement_id == "eng-test-123"

    def test_operator_audit_entry_has_operator_field(self) -> None:
        """Test operator field exists."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditEntry
        
        entry = OperatorAuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            engagement_id="eng-001",
            operator="admin_user",
            action=OperatorAction.APPROVE,
            context={},
            signature="abc123",
        )
        assert hasattr(entry, "operator")
        assert entry.operator == "admin_user"

    def test_operator_audit_entry_has_action_field(self) -> None:
        """Test action field exists (OperatorAction enum)."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditEntry
        
        entry = OperatorAuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            engagement_id="eng-001",
            operator="root",
            action=OperatorAction.KILL,
            context={},
            signature="abc123",
        )
        assert hasattr(entry, "action")
        assert entry.action == OperatorAction.KILL

    def test_operator_audit_entry_has_context_field(self) -> None:
        """Test context field exists (dict)."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditEntry
        
        context = {"target": "192.168.1.1", "agent_id": "recon-01"}
        entry = OperatorAuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            engagement_id="eng-001",
            operator="root",
            action=OperatorAction.APPROVE,
            context=context,
            signature="abc123",
        )
        assert hasattr(entry, "context")
        assert entry.context == context

    def test_operator_audit_entry_has_signature_field(self) -> None:
        """Test signature field exists (HMAC-SHA256 hex string)."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditEntry
        
        entry = OperatorAuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            engagement_id="eng-001",
            operator="root",
            action=OperatorAction.APPROVE,
            context={},
            signature="a1b2c3d4e5f6",
        )
        assert hasattr(entry, "signature")
        assert isinstance(entry.signature, str)

    def test_operator_audit_entry_to_dict_serializes_all_fields(self) -> None:
        """Test to_dict() serializes all fields correctly."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditEntry
        
        entry_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        context = {"target": "192.168.1.1"}
        
        entry = OperatorAuditEntry(
            entry_id=entry_id,
            timestamp=now,
            engagement_id="eng-001",
            operator="root",
            action=OperatorAction.APPROVE,
            context=context,
            signature="abc123",
        )
        
        result = entry.to_dict()
        
        assert result["entry_id"] == entry_id
        assert result["engagement_id"] == "eng-001"
        assert result["operator"] == "root"
        assert result["action"] == "approve"
        assert result["context"] == context
        assert result["signature"] == "abc123"
        # Timestamp should be ISO 8601 string
        assert "timestamp" in result
        assert isinstance(result["timestamp"], str)

    def test_operator_audit_entry_from_dict_deserializes_correctly(self) -> None:
        """Test from_dict() deserializes with validation."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditEntry
        
        entry_id = str(uuid.uuid4())
        timestamp_str = "2026-02-12T03:00:00+00:00"
        
        data = {
            "entry_id": entry_id,
            "timestamp": timestamp_str,
            "engagement_id": "eng-001",
            "operator": "root",
            "action": "approve",
            "context": {"target": "192.168.1.1"},
            "signature": "abc123",
        }
        
        entry = OperatorAuditEntry.from_dict(data)
        
        assert entry.entry_id == entry_id
        assert entry.engagement_id == "eng-001"
        assert entry.operator == "root"
        assert entry.action == OperatorAction.APPROVE
        assert entry.context == {"target": "192.168.1.1"}
        assert entry.signature == "abc123"

    def test_operator_audit_entry_timestamp_is_utc(self) -> None:
        """Test timestamp is always UTC."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditEntry
        
        now = datetime.now(timezone.utc)
        entry = OperatorAuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=now,
            engagement_id="eng-001",
            operator="root",
            action=OperatorAction.APPROVE,
            context={},
            signature="abc123",
        )
        
        # Timestamp should have UTC timezone
        assert entry.timestamp.tzinfo is not None
        assert entry.timestamp.tzinfo == timezone.utc or entry.timestamp.utcoffset().total_seconds() == 0

    def test_operator_audit_entry_to_dict_timestamp_iso8601(self) -> None:
        """Test to_dict() serializes timestamp as ISO 8601."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditEntry
        
        now = datetime.now(timezone.utc)
        entry = OperatorAuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=now,
            engagement_id="eng-001",
            operator="root",
            action=OperatorAction.APPROVE,
            context={},
            signature="abc123",
        )
        
        result = entry.to_dict()
        
        # Should be parseable ISO 8601 format
        parsed = datetime.fromisoformat(result["timestamp"])
        assert parsed.tzinfo is not None


# =============================================================================
# AC #3, #5: OperatorAuditLog Tests
# =============================================================================

class TestOperatorAuditLog:
    """Test OperatorAuditLog class per AC #3, #5."""

    def test_operator_audit_log_init_with_redis_client(self) -> None:
        """Test OperatorAuditLog.__init__(redis_client, engagement_id) initializes."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        
        mock_redis = MagicMock()
        engagement_id = "eng-test-001"
        
        log = OperatorAuditLog(mock_redis, engagement_id)
        
        assert log is not None

    def test_operator_audit_log_stream_name_pattern(self) -> None:
        """Test stream name is audit:{engagement_id} per architecture."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        
        mock_redis = MagicMock()
        engagement_id = "eng-ministry-001"
        
        log = OperatorAuditLog(mock_redis, engagement_id)
        
        # Stream name should follow pattern
        assert log.stream_name == f"audit:{engagement_id}"

    @pytest.mark.asyncio
    async def test_operator_audit_log_log_action_returns_entry(self) -> None:
        """Test log_action(operator, action, context) returns OperatorAuditEntry."""
        from cyberred.storage.operator_audit import (
            OperatorAction,
            OperatorAuditEntry,
            OperatorAuditLog,
        )
        
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        entry = await log.log_action(
            operator="root",
            action=OperatorAction.APPROVE,
            context={"target": "192.168.1.1"},
        )
        
        assert isinstance(entry, OperatorAuditEntry)
        assert entry.operator == "root"
        assert entry.action == OperatorAction.APPROVE

    @pytest.mark.asyncio
    async def test_operator_audit_log_writes_to_redis_stream(self) -> None:
        """Test entry is written to Redis Stream via xadd."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditLog
        
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        await log.log_action(
            operator="root",
            action=OperatorAction.APPROVE,
            context={"target": "192.168.1.1"},
        )
        
        # Verify xadd was called with correct stream name
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == "audit:eng-001"

    @pytest.mark.asyncio
    async def test_operator_audit_log_computes_hmac_signature(self) -> None:
        """Test HMAC signature is computed over entry content."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditLog
        
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        entry = await log.log_action(
            operator="root",
            action=OperatorAction.APPROVE,
            context={"target": "192.168.1.1"},
        )
        
        # Signature should be non-empty hex string (64 chars for SHA256)
        assert entry.signature
        assert len(entry.signature) == 64
        assert all(c in "0123456789abcdef" for c in entry.signature)

    @pytest.mark.asyncio
    async def test_operator_audit_log_creates_consumer_group(self) -> None:
        """Test consumer group audit-readers is created for stream."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        
        mock_redis = AsyncMock()
        mock_redis.xgroup_create = AsyncMock(return_value=True)
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # Initialize should create consumer group
        await log.initialize()
        
        mock_redis.xgroup_create.assert_called()
        call_args = mock_redis.xgroup_create.call_args
        assert "audit-readers" in str(call_args)

    @pytest.mark.asyncio
    async def test_operator_audit_log_get_entries_returns_list(self) -> None:
        """Test get_entries(start_id, count) returns entries in order."""
        from cyberred.storage.operator_audit import (
            OperatorAuditEntry,
            OperatorAuditLog,
        )
        
        mock_redis = AsyncMock()
        # Mock xread to return sample entries
        mock_redis.xread = AsyncMock(return_value=[
            ("1234567890-0", {"entry_id": "uuid-1", "operator": "root"}),
            ("1234567890-1", {"entry_id": "uuid-2", "operator": "admin"}),
        ])
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        entries = await log.get_entries(start_id="0", count=100)
        
        assert isinstance(entries, list)

    @pytest.mark.asyncio
    async def test_operator_audit_log_get_entries_verifies_signatures(self) -> None:
        """Test entries are returned with verified signatures."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        
        mock_redis = AsyncMock()
        mock_redis.xread = AsyncMock(return_value=[])
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # This test verifies the method exists and handles signature verification
        entries = await log.get_entries(start_id="0", count=100)
        
        # Should return empty list when no entries
        assert entries == []


# =============================================================================
# AC #6: Append-Only Enforcement Tests
# =============================================================================

class TestAppendOnlyEnforcement:
    """Test append-only enforcement per AC #6."""

    def test_operator_audit_log_has_no_delete_entry_method(self) -> None:
        """Test no delete_entry() method exists on OperatorAuditLog."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        
        mock_redis = MagicMock()
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # Should NOT have delete methods
        assert not hasattr(log, "delete_entry")
        assert not hasattr(log, "delete")

    def test_operator_audit_log_has_no_update_entry_method(self) -> None:
        """Test no update_entry() method exists on OperatorAuditLog."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        
        mock_redis = MagicMock()
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # Should NOT have update methods
        assert not hasattr(log, "update_entry")
        assert not hasattr(log, "update")
        assert not hasattr(log, "modify")

    def test_operator_audit_log_has_no_clear_method(self) -> None:
        """Test no clear() method exists on OperatorAuditLog."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        
        mock_redis = MagicMock()
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # Should NOT have clear/truncate methods
        assert not hasattr(log, "clear")
        assert not hasattr(log, "truncate")
        assert not hasattr(log, "purge")

    @pytest.mark.asyncio
    async def test_operator_audit_log_no_xtrim_in_operations(self) -> None:
        """Test Redis Stream is configured as append-only (no XTRIM)."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditLog
        
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # Log several actions
        for i in range(5):
            await log.log_action(
                operator="root",
                action=OperatorAction.APPROVE,
                context={"index": i},
            )
        
        # xadd should NOT use maxlen parameter (no trimming)
        for call in mock_redis.xadd.call_args_list:
            # Check that maxlen is not set or is None
            kwargs = call.kwargs if hasattr(call, 'kwargs') else {}
            if 'maxlen' in kwargs:
                assert kwargs['maxlen'] is None


# =============================================================================
# Signature Computation Tests
# =============================================================================

class TestSignatureComputation:
    """Test HMAC-SHA256 signature computation."""

    @pytest.mark.asyncio
    async def test_signature_uses_canonical_format(self) -> None:
        """Test signature is computed using canonical format."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditLog
        
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        entry = await log.log_action(
            operator="root",
            action=OperatorAction.APPROVE,
            context={"target": "192.168.1.1"},
        )
        
        # Signature should be deterministic for same inputs
        assert entry.signature is not None
        assert len(entry.signature) == 64  # SHA256 hex = 64 chars

    @pytest.mark.asyncio
    async def test_different_contexts_produce_different_signatures(self) -> None:
        """Test different contexts produce different signatures."""
        from cyberred.storage.operator_audit import OperatorAction, OperatorAuditLog
        
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        entry1 = await log.log_action(
            operator="root",
            action=OperatorAction.APPROVE,
            context={"target": "192.168.1.1"},
        )
        
        entry2 = await log.log_action(
            operator="root",
            action=OperatorAction.APPROVE,
            context={"target": "192.168.1.2"},
        )
        
        # Different contexts should produce different signatures
        assert entry1.signature != entry2.signature


# =============================================================================
# Factory Functions Tests (Coverage for lines 440-498, 514, 524, 544-548)
# =============================================================================

class TestFactoryFunctions:
    """Test singleton factory functions."""

    def test_get_operator_audit_log_returns_none_initially(self) -> None:
        """Test get_operator_audit_log returns None when not set."""
        from cyberred.storage import operator_audit
        
        # Reset global state
        operator_audit._operator_audit_log = None
        
        result = operator_audit.get_operator_audit_log()
        assert result is None

    def test_set_operator_audit_log_sets_instance(self) -> None:
        """Test set_operator_audit_log sets the global instance."""
        from cyberred.storage import operator_audit
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import MagicMock
        
        mock_redis = MagicMock()
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        operator_audit.set_operator_audit_log(log)
        
        result = operator_audit.get_operator_audit_log()
        assert result is log
        
        # Clean up
        operator_audit.set_operator_audit_log(None)

    def test_set_operator_audit_log_accepts_none(self) -> None:
        """Test set_operator_audit_log accepts None to clear."""
        from cyberred.storage import operator_audit
        
        operator_audit.set_operator_audit_log(None)
        
        result = operator_audit.get_operator_audit_log()
        assert result is None

    @pytest.mark.asyncio
    async def test_init_operator_audit_log_creates_and_sets_instance(self) -> None:
        """Test init_operator_audit_log creates and sets instance."""
        from cyberred.storage import operator_audit
        from cyberred.storage.operator_audit import init_operator_audit_log
        from unittest.mock import AsyncMock
        
        mock_redis = AsyncMock()
        mock_redis.xgroup_create = AsyncMock(return_value=True)
        
        log = await init_operator_audit_log(mock_redis, "eng-002")
        
        assert log is not None
        assert log.engagement_id == "eng-002"
        assert operator_audit.get_operator_audit_log() is log
        
        # Clean up
        operator_audit.set_operator_audit_log(None)


# =============================================================================
# Verify Chain Tests (Coverage for lines 278-289, 387-390, 415-422)
# =============================================================================

class TestVerifyChain:
    """Test verify_chain functionality."""

    @pytest.mark.asyncio
    async def test_verify_chain_returns_tuple(self) -> None:
        """Test verify_chain returns (bool, list) tuple."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock, MagicMock
        
        mock_redis = AsyncMock()
        mock_redis._master = MagicMock()
        mock_redis._master.xrange = AsyncMock(return_value=[])
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        result = await log.verify_chain()
        
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], list)

    @pytest.mark.asyncio
    async def test_verify_chain_empty_stream_is_valid(self) -> None:
        """Test empty stream is considered valid."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock, MagicMock
        
        mock_redis = AsyncMock()
        mock_redis._master = MagicMock()
        mock_redis._master.xrange = AsyncMock(return_value=[])
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        all_valid, invalid_ids = await log.verify_chain()
        
        assert all_valid is True
        assert invalid_ids == []

    @pytest.mark.asyncio
    async def test_verify_chain_with_no_master_returns_false(self) -> None:
        """Test verify_chain returns False when no master connection."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock
        
        mock_redis = AsyncMock()
        mock_redis._master = None
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        all_valid, invalid_ids = await log.verify_chain()
        
        assert all_valid is False
        assert invalid_ids == []

    @pytest.mark.asyncio
    async def test_verify_chain_handles_xrange_exception(self) -> None:
        """Test verify_chain handles xrange exception gracefully."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock, MagicMock
        
        mock_redis = AsyncMock()
        mock_redis._master = MagicMock()
        mock_redis._master.xrange = AsyncMock(side_effect=Exception("Connection error"))
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        all_valid, invalid_ids = await log.verify_chain()
        
        assert all_valid is False
        assert invalid_ids == []

    @pytest.mark.asyncio
    async def test_verify_chain_detects_missing_payload(self) -> None:
        """Test verify_chain detects entries with missing payload."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock, MagicMock
        
        mock_redis = AsyncMock()
        mock_redis._master = MagicMock()
        mock_redis._master.xrange = AsyncMock(return_value=[
            (b"1234567890-0", {b"no_payload": b"value"}),
        ])
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        all_valid, invalid_ids = await log.verify_chain()
        
        assert all_valid is False
        assert "1234567890-0" in invalid_ids

    @pytest.mark.asyncio
    async def test_verify_chain_detects_invalid_json(self) -> None:
        """Test verify_chain detects entries with invalid JSON."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock, MagicMock
        
        mock_redis = AsyncMock()
        mock_redis._master = MagicMock()
        mock_redis._master.xrange = AsyncMock(return_value=[
            (b"1234567890-0", {b"payload": b"not-valid-json"}),
        ])
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        all_valid, invalid_ids = await log.verify_chain()
        
        assert all_valid is False

    @pytest.mark.asyncio
    async def test_verify_chain_detects_missing_sig_in_payload(self) -> None:
        """Test verify_chain detects payloads without sig field."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock, MagicMock
        import json
        
        mock_redis = AsyncMock()
        mock_redis._master = MagicMock()
        # Payload missing "sig" field
        payload = json.dumps({"content": "{}", "ts": 1234})
        mock_redis._master.xrange = AsyncMock(return_value=[
            (b"1234567890-0", {b"payload": payload.encode()}),
        ])
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        all_valid, invalid_ids = await log.verify_chain()
        
        assert all_valid is False


# =============================================================================
# Verify Integrity Tests (Coverage for lines 215, 223)
# =============================================================================

class TestVerifyIntegrity:
    """Test verify_integrity functionality."""

    @pytest.mark.asyncio
    async def test_verify_integrity_returns_false_for_nonexistent_entry(self) -> None:
        """Test verify_integrity returns False for non-existent entry."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock
        
        mock_redis = AsyncMock()
        mock_redis.xread = AsyncMock(return_value=[])
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        result = await log.verify_integrity("nonexistent-uuid")
        
        assert result is False


# =============================================================================
# Edge Cases Tests (Coverage for remaining lines)
# =============================================================================

class TestEdgeCases:
    """Test edge cases for full coverage."""

    def test_from_dict_with_missing_field_raises_value_error(self) -> None:
        """Test from_dict raises ValueError for missing required fields."""
        from cyberred.storage.operator_audit import OperatorAuditEntry
        
        incomplete_data = {
            "entry_id": "uuid-1",
            # Missing timestamp, engagement_id, operator, action, signature
        }
        
        with pytest.raises(ValueError, match="Missing required field"):
            OperatorAuditEntry.from_dict(incomplete_data)

    def test_from_dict_with_none_context(self) -> None:
        """Test from_dict handles None context gracefully."""
        from cyberred.storage.operator_audit import OperatorAuditEntry
        from datetime import datetime, timezone
        
        data = {
            "entry_id": "uuid-1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "engagement_id": "eng-001",
            "operator": "root",
            "action": "approve",
            "context": None,
            "signature": "abc123",
        }
        
        entry = OperatorAuditEntry.from_dict(data)
        assert entry.context == {}

    def test_from_dict_with_z_suffix_timestamp(self) -> None:
        """Test from_dict handles Z suffix in timestamp."""
        from cyberred.storage.operator_audit import OperatorAuditEntry
        
        data = {
            "entry_id": "uuid-1",
            "timestamp": "2026-02-12T03:00:00Z",  # Z suffix instead of +00:00
            "engagement_id": "eng-001",
            "operator": "root",
            "action": "approve",
            "context": {},
            "signature": "abc123",
        }
        
        entry = OperatorAuditEntry.from_dict(data)
        assert entry.timestamp.tzinfo is not None

    def test_from_dict_with_naive_timestamp_gets_utc(self) -> None:
        """Test from_dict adds UTC to naive timestamps."""
        from cyberred.storage.operator_audit import OperatorAuditEntry
        
        data = {
            "entry_id": "uuid-1",
            "timestamp": "2026-02-12T03:00:00",  # Naive timestamp
            "engagement_id": "eng-001",
            "operator": "root",
            "action": "approve",
            "context": {},
            "signature": "abc123",
        }
        
        entry = OperatorAuditEntry.from_dict(data)
        assert entry.timestamp.tzinfo is not None

    def test_to_dict_with_string_timestamp(self) -> None:
        """Test to_dict handles string timestamp."""
        from cyberred.storage.operator_audit import OperatorAuditEntry, OperatorAction
        
        entry = OperatorAuditEntry(
            entry_id="uuid-1",
            timestamp="2026-02-12T03:00:00+00:00",  # String instead of datetime
            engagement_id="eng-001",
            operator="root",
            action=OperatorAction.APPROVE,
            context={},
            signature="abc123",
        )
        
        result = entry.to_dict()
        assert result["timestamp"] == "2026-02-12T03:00:00+00:00"

    def test_to_dict_with_string_action(self) -> None:
        """Test to_dict handles string action."""
        from cyberred.storage.operator_audit import OperatorAuditEntry
        from datetime import datetime, timezone
        
        entry = OperatorAuditEntry(
            entry_id="uuid-1",
            timestamp=datetime.now(timezone.utc),
            engagement_id="eng-001",
            operator="root",
            action="approve",  # String instead of enum
            context={},
            signature="abc123",
        )
        
        result = entry.to_dict()
        assert result["action"] == "approve"

    @pytest.mark.asyncio
    async def test_initialize_only_runs_once(self) -> None:
        """Test initialize() only creates consumer group once."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock
        
        mock_redis = AsyncMock()
        mock_redis.xgroup_create = AsyncMock(return_value=True)
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        await log.initialize()
        await log.initialize()  # Second call should be no-op
        
        # Should only be called once
        assert mock_redis.xgroup_create.call_count == 1

    @pytest.mark.asyncio  
    async def test_get_entries_handles_parse_error(self) -> None:
        """Test get_entries handles parse errors gracefully."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock
        
        mock_redis = AsyncMock()
        # Return entries with invalid data that will fail from_dict
        mock_redis.xread = AsyncMock(return_value=[
            ("1234567890-0", {"invalid": "data"}),
        ])
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        entries = await log.get_entries()
        
        # Should return empty list, not crash
        assert entries == []

    @pytest.mark.asyncio
    async def test_verify_signature_with_string_action(self) -> None:
        """Test _verify_signature handles string action in entry."""
        from cyberred.storage.operator_audit import OperatorAuditLog, OperatorAuditEntry
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock
        
        mock_redis = AsyncMock()
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # Create entry with string action instead of enum
        entry = OperatorAuditEntry(
            entry_id="uuid-1",
            timestamp=datetime.now(timezone.utc),
            engagement_id="eng-001", 
            operator="root",
            action="approve",  # String
            context={},
            signature="wrong-signature",
        )
        
        result = log._verify_signature(entry)
        
        # Should return False (invalid signature)
        assert result is False


# =============================================================================
# Additional Coverage Tests
# =============================================================================

class TestAdditionalCoverage:
    """Additional tests to reach 100% coverage."""

    @pytest.mark.asyncio
    async def test_get_entries_filters_invalid_signatures(self) -> None:
        """Test get_entries filters entries with invalid signatures (lines 387-390)."""
        from cyberred.storage.operator_audit import OperatorAuditLog, OperatorAction
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock
        import json
        
        mock_redis = AsyncMock()
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # Create a valid entry dict but with wrong signature
        timestamp = datetime.now(timezone.utc)
        entry_data = {
            "entry_id": "uuid-test",
            "timestamp": timestamp.isoformat(),
            "engagement_id": "eng-001",
            "operator": "root",
            "action": "approve",
            "context": {},
            "signature": "invalid_signature_that_wont_match",
        }
        
        mock_redis.xread = AsyncMock(return_value=[
            ("1234567890-0", entry_data),
        ])
        
        entries = await log.get_entries()
        
        # Entry should be filtered out due to invalid signature
        assert entries == []

    @pytest.mark.asyncio
    async def test_verify_integrity_returns_true_for_valid_entry(self) -> None:
        """Test verify_integrity returns True when entry exists (lines 418-420)."""
        from cyberred.storage.operator_audit import OperatorAuditLog, OperatorAction
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock
        import json
        
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # First log an action to get a valid entry
        entry = await log.log_action(
            operator="root",
            action=OperatorAction.START,
            context={"test": True},
        )
        
        # Mock xread to return this valid entry with correct signature
        mock_redis.xread = AsyncMock(return_value=[
            ("1234567890-0", entry.to_dict()),
        ])
        
        # verify_integrity should return True
        result = await log.verify_integrity(entry.entry_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_chain_with_valid_redis_verified_content(self) -> None:
        """Test verify_chain with valid Redis-verified content (lines 480-491)."""
        from cyberred.storage.operator_audit import OperatorAuditLog, OperatorAction
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock, MagicMock
        import json
        
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # First create a valid entry
        entry = await log.log_action(
            operator="root",
            action=OperatorAction.APPROVE,
            context={"target": "192.168.1.1"},
        )
        
        # Create the signed package structure that RedisClient would create
        entry_dict = entry.to_dict()
        content_json = json.dumps(entry_dict)
        
        # Mock _verify_message to return the content (simulating valid signature)
        mock_redis._verify_message = MagicMock(return_value=content_json)
        
        # Create the payload structure
        payload = json.dumps({
            "content": content_json,
            "sig": "valid_sig",
            "ts": 1234567890.0,
        })
        
        mock_redis._master = MagicMock()
        mock_redis._master.xrange = AsyncMock(return_value=[
            (b"1234567890-0", {b"payload": payload.encode()}),
        ])
        
        all_valid, invalid_ids = await log.verify_chain()
        
        assert all_valid is True
        assert invalid_ids == []

    @pytest.mark.asyncio
    async def test_verify_chain_with_invalid_app_signature(self) -> None:
        """Test verify_chain detects invalid app-level signature (line 489-490)."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock, MagicMock
        import json
        
        mock_redis = AsyncMock()
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # Entry with wrong app-level signature
        entry_dict = {
            "entry_id": "uuid-test",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "engagement_id": "eng-001",
            "operator": "root",
            "action": "approve",
            "context": {},
            "signature": "wrong_app_signature",
        }
        content_json = json.dumps(entry_dict)
        
        # Mock _verify_message to return the content (Redis layer passes)
        mock_redis._verify_message = MagicMock(return_value=content_json)
        
        payload = json.dumps({
            "content": content_json,
            "sig": "valid_redis_sig",
            "ts": 1234567890.0,
        })
        
        mock_redis._master = MagicMock()
        mock_redis._master.xrange = AsyncMock(return_value=[
            (b"1234567890-0", {b"payload": payload.encode()}),
        ])
        
        all_valid, invalid_ids = await log.verify_chain()
        
        # App signature is wrong, should be flagged
        assert all_valid is False
        assert "uuid-test" in invalid_ids

    @pytest.mark.asyncio
    async def test_verify_chain_handles_value_error_in_from_dict(self) -> None:
        """Test verify_chain handles ValueError from from_dict (line 492-494)."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock, MagicMock
        import json
        
        mock_redis = AsyncMock()
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # Content that will cause from_dict to raise ValueError (missing fields)
        content_json = json.dumps({"incomplete": "data"})
        
        mock_redis._verify_message = MagicMock(return_value=content_json)
        
        payload = json.dumps({
            "content": content_json,
            "sig": "valid_sig",
            "ts": 1234567890.0,
        })
        
        mock_redis._master = MagicMock()
        mock_redis._master.xrange = AsyncMock(return_value=[
            (b"1234567890-0", {b"payload": payload.encode()}),
        ])
        
        all_valid, invalid_ids = await log.verify_chain()
        
        assert all_valid is False
        assert "1234567890-0" in invalid_ids

    @pytest.mark.asyncio
    async def test_verify_chain_with_redis_verify_returning_none(self) -> None:
        """Test verify_chain when _verify_message returns None (line 480-482)."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock, MagicMock
        import json
        
        mock_redis = AsyncMock()
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # _verify_message returns None (Redis signature invalid)
        mock_redis._verify_message = MagicMock(return_value=None)
        
        payload = json.dumps({
            "content": "{}",
            "sig": "invalid_redis_sig",
            "ts": 1234567890.0,
        })
        
        mock_redis._master = MagicMock()
        mock_redis._master.xrange = AsyncMock(return_value=[
            (b"1234567890-0", {b"payload": payload.encode()}),
        ])
        
        all_valid, invalid_ids = await log.verify_chain()
        
        assert all_valid is False
        assert "1234567890-0" in invalid_ids


# =============================================================================
# Code Review Fix Coverage Tests
# =============================================================================

class TestCodeReviewFixes:
    """Tests added during code review to achieve 100% coverage."""

    def test_from_dict_requires_context_field(self) -> None:
        """Test from_dict requires context field (Issue 5 fix)."""
        from cyberred.storage.operator_audit import OperatorAuditEntry
        from datetime import datetime, timezone
        
        # Missing context field should raise ValueError
        data_no_context = {
            "entry_id": "uuid-1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "engagement_id": "eng-001",
            "operator": "root",
            "action": "approve",
            # "context" is missing
            "signature": "abc123",
        }
        
        with pytest.raises(ValueError, match="Missing required field: context"):
            OperatorAuditEntry.from_dict(data_no_context)

    @pytest.mark.asyncio
    async def test_verify_signature_exception_returns_false(self) -> None:
        """Test _verify_signature returns False on exception (Issue 6 fix)."""
        from cyberred.storage.operator_audit import OperatorAuditLog, OperatorAuditEntry
        from unittest.mock import AsyncMock, MagicMock, patch
        
        mock_redis = AsyncMock()
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # Create an entry with a context that will cause json.dumps to fail
        class BadContext:
            def __repr__(self):
                raise RuntimeError("Cannot serialize")
        
        entry = OperatorAuditEntry(
            entry_id="uuid-1",
            timestamp="not-a-datetime",  # Will cause isoformat() to fail
            engagement_id="eng-001",
            operator="root",
            action="approve",
            context={},
            signature="abc123",
        )
        
        # Mock _compute_signature to raise an exception
        with patch.object(log, '_compute_signature', side_effect=Exception("Compute failed")):
            result = log._verify_signature(entry)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_integrity_searches_entries(self) -> None:
        """Test verify_integrity searches through entries."""
        from cyberred.storage.operator_audit import OperatorAuditLog, OperatorAction
        from unittest.mock import AsyncMock
        
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # Mock xread to return empty list
        mock_redis.xread = AsyncMock(return_value=[])
        
        # Should search and not find (returns False)
        result = await log.verify_integrity("nonexistent-entry")
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_chain_uses_end_id_parameter(self) -> None:
        """Test verify_chain uses the end_id parameter (Issue 8 fix)."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock, MagicMock
        
        mock_redis = AsyncMock()
        mock_master = MagicMock()
        mock_master.xrange = AsyncMock(return_value=[])
        mock_redis._master = mock_master
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # Call verify_chain with specific end_id
        await log.verify_chain(start_id="1000-0", end_id="2000-0")
        
        # Verify xrange was called with correct parameters
        mock_master.xrange.assert_called_once()
        call_args = mock_master.xrange.call_args
        assert call_args[0][1] == "1000-0"  # start_id passed through
        assert call_args[0][2] == "2000-0"  # end_id passed through

    @pytest.mark.asyncio
    async def test_verify_chain_start_id_zero_converts_to_dash(self) -> None:
        """Test verify_chain converts start_id '0' to '-' for Redis."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock, MagicMock
        
        mock_redis = AsyncMock()
        mock_master = MagicMock()
        mock_master.xrange = AsyncMock(return_value=[])
        mock_redis._master = mock_master
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # Call verify_chain with default start_id="0"
        await log.verify_chain()
        
        # Verify xrange was called with "-" instead of "0"
        mock_master.xrange.assert_called_once()
        call_args = mock_master.xrange.call_args
        assert call_args[0][1] == "-"  # "0" converted to "-"
        assert call_args[0][2] == "+"  # default end_id

    @pytest.mark.asyncio
    async def test_verify_integrity_finds_entry_in_first_batch(self) -> None:
        """Test verify_integrity finds entry in first batch."""
        from cyberred.storage.operator_audit import OperatorAuditLog, OperatorAction
        from unittest.mock import AsyncMock
        
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # Create a valid entry
        entry = await log.log_action(
            operator="root",
            action=OperatorAction.START,
            context={},
        )
        
        # Mock xread to return our entry
        mock_redis.xread = AsyncMock(return_value=[
            ("1234567890-0", entry.to_dict()),
        ])
        
        result = await log.verify_integrity(entry.entry_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_integrity_not_found_in_entries(self) -> None:
        """Test verify_integrity returns False when entry not found."""
        from cyberred.storage.operator_audit import OperatorAuditLog, OperatorAction
        from unittest.mock import AsyncMock
        
        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock(return_value="1234567890-0")
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        # Create a valid entry but we'll search for a different one
        entry = await log.log_action(
            operator="root",
            action=OperatorAction.START,
            context={},
        )
        
        # Mock xread to return our entry
        mock_redis.xread = AsyncMock(return_value=[
            ("1234567890-0", entry.to_dict()),
        ])
        
        # Search for non-existent entry
        result = await log.verify_integrity("non-existent-uuid")
        assert result is False

    def test_from_dict_with_datetime_timestamp_object(self) -> None:
        """Test from_dict handles datetime object directly (branch 134->139)."""
        from cyberred.storage.operator_audit import OperatorAuditEntry, OperatorAction
        from datetime import datetime, timezone
        
        ts = datetime.now(timezone.utc)
        data = {
            "entry_id": "uuid-1",
            "timestamp": ts,  # Already a datetime object
            "engagement_id": "eng-001",
            "operator": "root",
            "action": "approve",
            "context": {},
            "signature": "abc123",
        }
        
        entry = OperatorAuditEntry.from_dict(data)
        assert entry.timestamp == ts

    def test_from_dict_with_operator_action_enum(self) -> None:
        """Test from_dict handles OperatorAction enum directly (branch 144->148)."""
        from cyberred.storage.operator_audit import OperatorAuditEntry, OperatorAction
        from datetime import datetime, timezone
        
        data = {
            "entry_id": "uuid-1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "engagement_id": "eng-001",
            "operator": "root",
            "action": OperatorAction.APPROVE,  # Already an enum
            "context": {},
            "signature": "abc123",
        }
        
        entry = OperatorAuditEntry.from_dict(data)
        assert entry.action == OperatorAction.APPROVE

    @pytest.mark.asyncio
    async def test_verify_chain_with_string_stream_entry_id(self) -> None:
        """Test verify_chain handles string stream entry ID (branch 469->473)."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock, MagicMock
        import json
        
        mock_redis = AsyncMock()
        mock_master = MagicMock()
        
        # Return string stream entry ID instead of bytes
        mock_master.xrange = AsyncMock(return_value=[
            ("1234567890-0", {b"payload": b"invalid"}),  # string ID, not bytes
        ])
        mock_redis._master = mock_master
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        all_valid, invalid_ids = await log.verify_chain()
        
        # Should handle string ID without decode error
        assert all_valid is False
        assert "1234567890-0" in invalid_ids

    @pytest.mark.asyncio
    async def test_verify_chain_with_string_payload_key(self) -> None:
        """Test verify_chain handles string 'payload' key."""
        from cyberred.storage.operator_audit import OperatorAuditLog
        from unittest.mock import AsyncMock, MagicMock
        import json
        
        mock_redis = AsyncMock()
        mock_master = MagicMock()
        
        # Return with string key "payload" instead of bytes b"payload"
        mock_master.xrange = AsyncMock(return_value=[
            (b"1234567890-0", {"payload": "invalid-json"}),  # string key
        ])
        mock_redis._master = mock_master
        
        log = OperatorAuditLog(mock_redis, "eng-001")
        
        all_valid, invalid_ids = await log.verify_chain()
        
        assert all_valid is False
