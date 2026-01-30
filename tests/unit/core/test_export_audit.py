"""Unit tests for ExportAuditLogger class.

Story 11.3: Data Export from TUI

Tests for ExportAuditLogger functionality:
- log_export() for single item exports
- log_archive_export() for archive exports
- ExportAuditEntry dataclass
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestExportAuditEntry:
    """Test ExportAuditEntry dataclass."""

    def test_to_dict_single_export(self):
        """Test to_dict for single item export."""
        from cyberred.core.audit import ExportAuditEntry

        entry = ExportAuditEntry(
            event_type="single_export",
            destination="/tmp/shadow",
            item_id="item-001",
            filename="shadow",
            engagement_name="test-engagement",
            operator="admin",
        )

        result = entry.to_dict()

        assert result["event_type"] == "single_export"
        assert result["destination"] == "/tmp/shadow"
        assert result["item_id"] == "item-001"
        assert result["filename"] == "shadow"
        assert result["engagement_name"] == "test-engagement"
        assert result["operator"] == "admin"
        assert "timestamp" in result

    def test_to_dict_archive_export(self):
        """Test to_dict for archive export."""
        from cyberred.core.audit import ExportAuditEntry

        entry = ExportAuditEntry(
            event_type="archive_export",
            destination="/tmp/export.zip",
            item_ids=["item-001", "item-002"],
            item_count=2,
            engagement_name="test-engagement",
        )

        result = entry.to_dict()

        assert result["event_type"] == "archive_export"
        assert result["item_ids"] == ["item-001", "item-002"]
        assert result["item_count"] == 2
        assert "item_id" not in result  # Not set for archive

    def test_to_dict_excludes_none_values(self):
        """Test to_dict excludes None values."""
        from cyberred.core.audit import ExportAuditEntry

        entry = ExportAuditEntry(
            event_type="single_export",
            destination="/tmp/test",
        )

        result = entry.to_dict()

        assert "item_id" not in result
        assert "item_ids" not in result
        assert "filename" not in result
        assert "item_count" not in result
        assert "engagement_name" not in result


class TestExportAuditLogger:
    """Test ExportAuditLogger class."""

    def test_init_without_redis(self):
        """Test initialization without Redis client."""
        from cyberred.core.audit import ExportAuditLogger

        logger = ExportAuditLogger()

        assert logger._redis_client is None
        assert logger._stream_name == "cyberred:audit:exports"

    def test_init_with_redis(self):
        """Test initialization with Redis client."""
        from cyberred.core.audit import ExportAuditLogger

        redis_client = MagicMock()
        logger = ExportAuditLogger(redis_client=redis_client)

        assert logger._redis_client is redis_client

    def test_log_export_creates_entry(self):
        """Test log_export creates proper entry."""
        from cyberred.core.audit import ExportAuditLogger

        logger = ExportAuditLogger()

        # Should not raise even without Redis
        logger.log_export(
            item_id="item-001",
            filename="shadow",
            destination="/tmp/shadow",
            engagement_name="test-engagement",
            operator="admin",
        )

    def test_log_archive_export_creates_entry(self):
        """Test log_archive_export creates proper entry."""
        from cyberred.core.audit import ExportAuditLogger

        logger = ExportAuditLogger()

        # Should not raise even without Redis
        logger.log_archive_export(
            item_ids=["item-001", "item-002"],
            destination="/tmp/export.zip",
            item_count=2,
            engagement_name="test-engagement",
        )

    def test_log_export_with_redis_schedules_write(self):
        """Test log_export attempts Redis write when available."""
        from cyberred.core.audit import ExportAuditLogger
        import asyncio

        redis_client = MagicMock()
        redis_client.xadd = AsyncMock(return_value="entry-id")

        logger = ExportAuditLogger(redis_client=redis_client)

        # Mock the asyncio event loop
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete = MagicMock()

            logger.log_export(
                item_id="item-001",
                filename="shadow",
                destination="/tmp/shadow",
            )

            # Should have attempted to write
            mock_loop.return_value.run_until_complete.assert_called_once()

    def test_log_export_handles_redis_error(self):
        """Test log_export handles Redis errors gracefully."""
        from cyberred.core.audit import ExportAuditLogger

        redis_client = MagicMock()
        redis_client.xadd = AsyncMock(side_effect=Exception("Redis error"))

        logger = ExportAuditLogger(redis_client=redis_client)

        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete.side_effect = Exception("Redis error")

            # Should not raise
            logger.log_export(
                item_id="item-001",
                filename="shadow",
                destination="/tmp/shadow",
            )


class TestExportAuditLoggerSingleton:
    """Test singleton pattern for ExportAuditLogger."""

    def test_get_export_audit_logger_returns_none_initially(self):
        """Test get_export_audit_logger returns None when not initialized."""
        from cyberred.core.audit import get_export_audit_logger, set_export_audit_logger

        # Reset to None
        set_export_audit_logger(None)

        result = get_export_audit_logger()
        assert result is None

    def test_init_export_audit_logger_creates_instance(self):
        """Test init_export_audit_logger creates and sets instance."""
        from cyberred.core.audit import (
            init_export_audit_logger,
            get_export_audit_logger,
            set_export_audit_logger,
            ExportAuditLogger,
        )

        # Reset first
        set_export_audit_logger(None)

        logger = init_export_audit_logger()

        assert isinstance(logger, ExportAuditLogger)
        assert get_export_audit_logger() is logger

    def test_set_export_audit_logger_sets_instance(self):
        """Test set_export_audit_logger sets the global instance."""
        from cyberred.core.audit import (
            get_export_audit_logger,
            set_export_audit_logger,
            ExportAuditLogger,
        )

        custom_logger = ExportAuditLogger()
        set_export_audit_logger(custom_logger)

        assert get_export_audit_logger() is custom_logger

        # Cleanup
        set_export_audit_logger(None)
