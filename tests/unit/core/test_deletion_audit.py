"""Unit tests for DeletionAuditLogger and DeletionAuditEntry.

Story 11.4: Manual Data Deletion

Tests for audit logging of deletion operations per FR45:
All deletions logged to audit trail with item_id, timestamp.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.core.audit import (
    DELETION_AUDIT_STREAM_NAME,
    DeletionAuditEntry,
    DeletionAuditLogger,
    get_deletion_audit_logger,
    init_deletion_audit_logger,
    set_deletion_audit_logger,
)


# ─────────────────────────────────────────────────────────────────────────────
# DeletionAuditEntry Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestDeletionAuditEntry:
    """Tests for DeletionAuditEntry dataclass."""

    def test_single_deletion_entry_creation(self) -> None:
        """Test creating a single deletion audit entry."""
        entry = DeletionAuditEntry(
            event_type="single_deletion",
            item_id="item-123",
            filename="passwords.txt",
            target="192.168.1.100",
            size_bytes=1024,
            operator="admin",
        )

        assert entry.event_type == "single_deletion"
        assert entry.item_id == "item-123"
        assert entry.filename == "passwords.txt"
        assert entry.target == "192.168.1.100"
        assert entry.size_bytes == 1024
        assert entry.operator == "admin"
        assert entry.timestamp is not None

    def test_bulk_deletion_entry_creation(self) -> None:
        """Test creating a bulk deletion audit entry."""
        entry = DeletionAuditEntry(
            event_type="bulk_deletion",
            item_ids=["item-1", "item-2", "item-3"],
            total_deleted=3,
            total_failed=0,
            operator="operator",
        )

        assert entry.event_type == "bulk_deletion"
        assert entry.item_ids == ["item-1", "item-2", "item-3"]
        assert entry.total_deleted == 3
        assert entry.total_failed == 0

    def test_to_dict_single_deletion(self) -> None:
        """Test serialization of single deletion entry."""
        entry = DeletionAuditEntry(
            event_type="single_deletion",
            item_id="item-123",
            filename="test.txt",
            target="10.0.0.1",
            size_bytes=512,
            operator="tester",
        )

        result = entry.to_dict()

        assert result["event_type"] == "single_deletion"
        assert result["item_id"] == "item-123"
        assert result["filename"] == "test.txt"
        assert result["target"] == "10.0.0.1"
        assert result["size_bytes"] == 512
        assert result["operator"] == "tester"
        assert "timestamp" in result

    def test_to_dict_bulk_deletion(self) -> None:
        """Test serialization of bulk deletion entry."""
        entry = DeletionAuditEntry(
            event_type="bulk_deletion",
            item_ids=["a", "b"],
            total_deleted=2,
            total_failed=1,
        )

        result = entry.to_dict()

        assert result["event_type"] == "bulk_deletion"
        assert result["item_ids"] == ["a", "b"]
        assert result["total_deleted"] == 2
        assert result["total_failed"] == 1

    def test_to_dict_excludes_none_values(self) -> None:
        """Test that None values are excluded from dict."""
        entry = DeletionAuditEntry(
            event_type="single_deletion",
            item_id="item-1",
        )

        result = entry.to_dict()

        # These should NOT be in the dict since they are None
        assert "filename" not in result
        assert "target" not in result
        assert "size_bytes" not in result
        assert "item_ids" not in result
        assert "total_deleted" not in result
        assert "total_failed" not in result

    def test_default_operator(self) -> None:
        """Test default operator value."""
        entry = DeletionAuditEntry(event_type="single_deletion")
        assert entry.operator == "operator"

    def test_timestamp_is_iso_format(self) -> None:
        """Test that timestamp is in ISO format."""
        entry = DeletionAuditEntry(event_type="single_deletion")
        
        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(entry.timestamp)
        assert parsed is not None


# ─────────────────────────────────────────────────────────────────────────────
# DeletionAuditLogger Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestDeletionAuditLogger:
    """Tests for DeletionAuditLogger class."""

    def test_init_without_redis(self) -> None:
        """Test initialization without Redis client."""
        logger = DeletionAuditLogger()

        assert logger._redis_client is None
        assert logger._stream_name == DELETION_AUDIT_STREAM_NAME

    def test_init_with_redis(self) -> None:
        """Test initialization with Redis client."""
        mock_redis = MagicMock()
        logger = DeletionAuditLogger(redis_client=mock_redis)

        assert logger._redis_client is mock_redis
        assert logger._stream_name == DELETION_AUDIT_STREAM_NAME

    def test_init_with_custom_stream_name(self) -> None:
        """Test initialization with custom stream name."""
        logger = DeletionAuditLogger(stream_name="custom:stream")

        assert logger._stream_name == "custom:stream"

    def test_log_deletion_without_redis(self) -> None:
        """Test log_deletion when Redis is not available."""
        logger = DeletionAuditLogger()

        # Should not raise - logs locally only
        logger.log_deletion(
            item_id="item-123",
            filename="test.txt",
            target="10.0.0.1",
            size_bytes=100,
        )

    def test_log_deletion_with_custom_operator(self) -> None:
        """Test log_deletion with custom operator."""
        logger = DeletionAuditLogger()

        # Should not raise
        logger.log_deletion(
            item_id="item-123",
            filename="test.txt",
            target="10.0.0.1",
            size_bytes=100,
            operator="custom_user",
        )

    def test_log_bulk_deletion_without_redis(self) -> None:
        """Test log_bulk_deletion when Redis is not available."""
        logger = DeletionAuditLogger()

        # Should not raise - logs locally only
        logger.log_bulk_deletion(
            item_ids=["item-1", "item-2"],
            total_deleted=2,
            total_failed=0,
        )

    def test_log_bulk_deletion_with_failures(self) -> None:
        """Test log_bulk_deletion with some failures."""
        logger = DeletionAuditLogger()

        logger.log_bulk_deletion(
            item_ids=["item-1", "item-2"],
            total_deleted=1,
            total_failed=1,
            operator="admin",
        )

    @pytest.mark.asyncio
    async def test_write_entry_in_async_context(self) -> None:
        """Test _write_entry when running in async context."""
        mock_redis = MagicMock()
        mock_redis.xadd = AsyncMock(return_value="stream-id-123")

        logger = DeletionAuditLogger(redis_client=mock_redis)

        # In async context, should create task
        logger.log_deletion(
            item_id="item-123",
            filename="test.txt",
            target="10.0.0.1",
            size_bytes=100,
        )

        # Give the task time to execute
        await asyncio.sleep(0.1)

        # Verify xadd was called
        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == DELETION_AUDIT_STREAM_NAME

    def test_write_entry_redis_error_does_not_raise(self) -> None:
        """Test that Redis errors are caught and logged, not raised."""
        mock_redis = MagicMock()
        mock_redis.xadd = AsyncMock(side_effect=Exception("Redis connection error"))

        logger = DeletionAuditLogger(redis_client=mock_redis)

        # Should not raise even if Redis fails
        logger.log_deletion(
            item_id="item-123",
            filename="test.txt",
            target="10.0.0.1",
            size_bytes=100,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Module-level Function Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestDeletionAuditLoggerSingleton:
    """Tests for module-level singleton functions."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        set_deletion_audit_logger(None)

    def teardown_method(self) -> None:
        """Reset singleton after each test."""
        set_deletion_audit_logger(None)

    def test_get_deletion_audit_logger_returns_none_initially(self) -> None:
        """Test that get returns None when not initialized."""
        result = get_deletion_audit_logger()
        assert result is None

    def test_set_deletion_audit_logger(self) -> None:
        """Test setting the global logger instance."""
        logger = DeletionAuditLogger()
        set_deletion_audit_logger(logger)

        result = get_deletion_audit_logger()
        assert result is logger

    def test_set_deletion_audit_logger_to_none(self) -> None:
        """Test resetting the global logger to None."""
        logger = DeletionAuditLogger()
        set_deletion_audit_logger(logger)
        set_deletion_audit_logger(None)

        result = get_deletion_audit_logger()
        assert result is None

    def test_init_deletion_audit_logger_without_redis(self) -> None:
        """Test init_deletion_audit_logger without Redis client."""
        result = init_deletion_audit_logger()

        assert result is not None
        assert isinstance(result, DeletionAuditLogger)
        assert get_deletion_audit_logger() is result

    def test_init_deletion_audit_logger_with_redis(self) -> None:
        """Test init_deletion_audit_logger with Redis client."""
        mock_redis = MagicMock()
        result = init_deletion_audit_logger(redis_client=mock_redis)

        assert result is not None
        assert result._redis_client is mock_redis
        assert get_deletion_audit_logger() is result
