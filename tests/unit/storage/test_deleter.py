"""Unit tests for SecureDeleter.

Story 11.4: Manual Data Deletion

Tests for secure deletion with 3-pass random overwrite (DoD 5220.22-M style).
Per FR45: Manual deletion with audit logging.

TDD RED Phase: These tests should FAIL until implementation is complete.
"""

from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch, call

import pytest

from cyberred.storage.deleter import (
    SECURE_DELETE_PASSES,
    DeletionResult,
    SecureDeleter,
)
from cyberred.core.exceptions import DeletionError


# ─────────────────────────────────────────────────────────────────────────────
# DeletionResult Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestDeletionResult:
    """Tests for DeletionResult dataclass."""

    def test_success_when_all_deleted(self) -> None:
        """DeletionResult.success is True when all items deleted."""
        result = DeletionResult(
            total_items=3,
            deleted_items=3,
            failed_items=[],
        )
        assert result.success is True

    def test_failure_when_partial_delete(self) -> None:
        """DeletionResult.success is False when some items failed."""
        result = DeletionResult(
            total_items=3,
            deleted_items=2,
            failed_items=[("item-3", "Permission denied")],
        )
        assert result.success is False

    def test_failure_when_all_failed(self) -> None:
        """DeletionResult.success is False when all items failed."""
        result = DeletionResult(
            total_items=2,
            deleted_items=0,
            failed_items=[
                ("item-1", "File not found"),
                ("item-2", "Permission denied"),
            ],
        )
        assert result.success is False

    def test_empty_result_is_success(self) -> None:
        """Empty deletion (0 items) is still considered success."""
        result = DeletionResult(
            total_items=0,
            deleted_items=0,
            failed_items=[],
        )
        assert result.success is True


# ─────────────────────────────────────────────────────────────────────────────
# SecureDeleter Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSecureDeleter:
    """Tests for SecureDeleter class."""

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        """Create mock ExfiltratedDataStore."""
        store = MagicMock()
        store._evidence_path = Path("/fake/evidence")
        store._items = {}
        return store

    @pytest.fixture
    def mock_audit_logger(self) -> MagicMock:
        """Create mock DeletionAuditLogger."""
        return MagicMock()

    @pytest.fixture
    def deleter(
        self, mock_store: MagicMock, mock_audit_logger: MagicMock
    ) -> SecureDeleter:
        """Create SecureDeleter with mocks."""
        return SecureDeleter(store=mock_store, audit_logger=mock_audit_logger)

    # ─────────────────────────────────────────────────────────────────────────
    # secure_delete_file tests
    # ─────────────────────────────────────────────────────────────────────────

    def test_secure_delete_file_overwrites_3_times(self, deleter: SecureDeleter) -> None:
        """secure_delete_file performs 3-pass overwrite per DoD 5220.22-M."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_path = Path(f.name)
            original_data = b"sensitive data that must be securely deleted"
            f.write(original_data)

        try:
            # Track overwrite calls
            write_count = 0
            original_open = open

            def counting_open(path, mode="r", *args, **kwargs):
                nonlocal write_count
                if "r+b" in mode or mode == "r+b":
                    write_count += 1
                return original_open(path, mode, *args, **kwargs)

            with patch("builtins.open", side_effect=counting_open):
                deleter.secure_delete_file(test_path)

            # Should have written 3 times (3 passes)
            assert write_count == SECURE_DELETE_PASSES
            # File should no longer exist
            assert not test_path.exists()

        finally:
            if test_path.exists():
                test_path.unlink()

    def test_secure_delete_file_uses_cryptographic_random(
        self, deleter: SecureDeleter
    ) -> None:
        """secure_delete_file uses secrets.token_bytes for secure randomness."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_path = Path(f.name)
            f.write(b"sensitive data")

        try:
            with patch("cyberred.storage.deleter.secrets.token_bytes") as mock_token:
                mock_token.return_value = b"\x00" * 14  # Same size as "sensitive data"
                deleter.secure_delete_file(test_path)

            # Should be called 3 times (one per pass)
            assert mock_token.call_count == SECURE_DELETE_PASSES

        finally:
            if test_path.exists():
                test_path.unlink()

    def test_secure_delete_file_calls_fsync(self, deleter: SecureDeleter) -> None:
        """secure_delete_file calls fsync after each pass to ensure disk write."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_path = Path(f.name)
            f.write(b"data")

        try:
            with patch("os.fsync") as mock_fsync:
                deleter.secure_delete_file(test_path)

            # fsync should be called 3 times (once per pass)
            assert mock_fsync.call_count == SECURE_DELETE_PASSES

        finally:
            if test_path.exists():
                test_path.unlink()

    def test_secure_delete_file_skips_nonexistent(
        self, deleter: SecureDeleter
    ) -> None:
        """secure_delete_file silently skips non-existent files."""
        nonexistent = Path("/nonexistent/file.txt")
        # Should not raise
        deleter.secure_delete_file(nonexistent)

    def test_secure_delete_file_verifies_deletion(
        self, deleter: SecureDeleter
    ) -> None:
        """secure_delete_file raises DeletionError if file still exists after unlink."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_path = Path(f.name)
            f.write(b"data")

        try:
            # Mock unlink to not actually delete
            with patch.object(Path, "unlink"):
                with pytest.raises(DeletionError) as exc_info:
                    deleter.secure_delete_file(test_path)

            assert "verification_failed" in str(exc_info.value.reason)

        finally:
            if test_path.exists():
                test_path.unlink()

    # ─────────────────────────────────────────────────────────────────────────
    # delete_item tests
    # ─────────────────────────────────────────────────────────────────────────

    def test_delete_item_removes_from_manifest(
        self,
        mock_store: MagicMock,
        mock_audit_logger: MagicMock,
    ) -> None:
        """delete_item removes item from manifest after secure file deletion."""
        # Setup mock item
        mock_item = MagicMock()
        mock_item.id = "item-123"
        mock_item.filename = "passwords.txt"
        mock_item.target = "192.168.1.100"
        mock_item.size_bytes = 1024
        mock_item.encrypted_path = Path("data/item-123.enc")

        mock_store.get_item.return_value = mock_item
        mock_store._items = {"item-123": mock_item}

        deleter = SecureDeleter(store=mock_store, audit_logger=mock_audit_logger)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_path = Path(f.name)
            f.write(b"encrypted content")

        try:
            mock_store._evidence_path = test_path.parent
            mock_item.encrypted_path = Path(test_path.name)

            deleter.delete_item("item-123")

            # Verify manifest update was called
            mock_store._remove_from_manifest.assert_called_once_with("item-123")

            # Verify item removed from cache
            assert "item-123" not in mock_store._items

        finally:
            if test_path.exists():
                test_path.unlink()

    def test_delete_item_logs_to_audit(
        self,
        mock_store: MagicMock,
        mock_audit_logger: MagicMock,
    ) -> None:
        """delete_item logs deletion to audit trail per FR45."""
        mock_item = MagicMock()
        mock_item.id = "item-456"
        mock_item.filename = "credentials.json"
        mock_item.target = "10.0.0.50"
        mock_item.size_bytes = 2048
        mock_item.encrypted_path = Path("data/item-456.enc")

        mock_store.get_item.return_value = mock_item
        mock_store._items = {"item-456": mock_item}

        deleter = SecureDeleter(store=mock_store, audit_logger=mock_audit_logger)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_path = Path(f.name)
            f.write(b"content")

        try:
            mock_store._evidence_path = test_path.parent
            mock_item.encrypted_path = Path(test_path.name)

            deleter.delete_item("item-456")

            # Verify audit log was called
            mock_audit_logger.log_deletion.assert_called_once_with(
                "item-456",
                "credentials.json",
                "10.0.0.50",
                2048,
            )

        finally:
            if test_path.exists():
                test_path.unlink()

    def test_delete_item_raises_keyerror_for_unknown(
        self,
        mock_store: MagicMock,
        mock_audit_logger: MagicMock,
    ) -> None:
        """delete_item raises KeyError for non-existent item."""
        mock_store.get_item.return_value = None

        deleter = SecureDeleter(store=mock_store, audit_logger=mock_audit_logger)

        with pytest.raises(KeyError, match="Item not found"):
            deleter.delete_item("nonexistent-item")

    def test_delete_item_handles_item_not_in_cache(
        self,
        mock_store: MagicMock,
        mock_audit_logger: MagicMock,
    ) -> None:
        """delete_item handles case where item exists in store but not in _items cache."""
        mock_item = MagicMock()
        mock_item.id = "item-789"
        mock_item.filename = "uncached.txt"
        mock_item.target = "10.0.0.99"
        mock_item.size_bytes = 512
        mock_item.encrypted_path = Path("data/item-789.enc")

        mock_store.get_item.return_value = mock_item
        # Simulate item NOT in the _items cache (empty dict)
        mock_store._items = {}

        deleter = SecureDeleter(store=mock_store, audit_logger=mock_audit_logger)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_path = Path(f.name)
            f.write(b"content")

        try:
            mock_store._evidence_path = test_path.parent
            mock_item.encrypted_path = Path(test_path.name)

            # Should succeed even though item not in cache
            deleter.delete_item("item-789")

            # Verify manifest update was still called
            mock_store._remove_from_manifest.assert_called_once_with("item-789")
            # Verify audit log was called
            mock_audit_logger.log_deletion.assert_called_once()

        finally:
            if test_path.exists():
                test_path.unlink()

    # ─────────────────────────────────────────────────────────────────────────
    # delete_items (bulk) tests
    # ─────────────────────────────────────────────────────────────────────────

    def test_delete_items_bulk_success(
        self,
        mock_store: MagicMock,
        mock_audit_logger: MagicMock,
    ) -> None:
        """delete_items successfully deletes multiple items."""
        # Create temp files for items
        temp_files = []
        items = {}

        for i in range(3):
            f = tempfile.NamedTemporaryFile(delete=False)
            f.write(b"content")
            f.close()
            temp_files.append(Path(f.name))

            mock_item = MagicMock()
            mock_item.id = f"item-{i}"
            mock_item.filename = f"file-{i}.txt"
            mock_item.target = f"192.168.1.{i}"
            mock_item.size_bytes = 100
            mock_item.encrypted_path = Path(temp_files[-1].name)
            items[f"item-{i}"] = mock_item

        mock_store.get_item.side_effect = lambda x: items.get(x)
        mock_store._items = items.copy()
        mock_store._evidence_path = temp_files[0].parent

        deleter = SecureDeleter(store=mock_store, audit_logger=mock_audit_logger)

        try:
            result = deleter.delete_items(["item-0", "item-1", "item-2"])

            assert result.success is True
            assert result.total_items == 3
            assert result.deleted_items == 3
            assert result.failed_items == []

            # Verify bulk audit log
            mock_audit_logger.log_bulk_deletion.assert_called_once()

        finally:
            for f in temp_files:
                if f.exists():
                    f.unlink()

    def test_delete_items_partial_failure_continue_on_error(
        self,
        mock_store: MagicMock,
        mock_audit_logger: MagicMock,
    ) -> None:
        """delete_items continues on error when continue_on_error=True."""
        # Create one real file, second item doesn't exist in store
        f = tempfile.NamedTemporaryFile(delete=False)
        f.write(b"content")
        f.close()
        temp_file = Path(f.name)

        item1 = MagicMock()
        item1.id = "item-1"
        item1.filename = "file1.txt"
        item1.target = "host1"
        item1.size_bytes = 100
        item1.encrypted_path = Path(temp_file.name)

        # item-2 does not exist in the store (get_item returns None)
        items = {"item-1": item1}
        mock_store.get_item.side_effect = lambda x: items.get(x)
        mock_store._items = items.copy()
        mock_store._evidence_path = temp_file.parent

        deleter = SecureDeleter(store=mock_store, audit_logger=mock_audit_logger)

        try:
            result = deleter.delete_items(
                ["item-1", "item-2"],  # item-2 doesn't exist
                continue_on_error=True,
            )

            assert result.success is False
            assert result.total_items == 2
            assert result.deleted_items == 1
            assert len(result.failed_items) == 1
            assert result.failed_items[0][0] == "item-2"
            assert "not found" in result.failed_items[0][1].lower()

        finally:
            if temp_file.exists():
                temp_file.unlink()

    def test_delete_items_stops_on_first_error_by_default(
        self,
        mock_store: MagicMock,
        mock_audit_logger: MagicMock,
    ) -> None:
        """delete_items stops on first error when continue_on_error=False."""
        # First item will fail
        mock_store.get_item.return_value = None

        deleter = SecureDeleter(store=mock_store, audit_logger=mock_audit_logger)

        result = deleter.delete_items(["bad-item", "good-item"])

        assert result.success is False
        assert result.deleted_items == 0
        assert len(result.failed_items) == 1
        # Second item should not be attempted
        assert mock_store.get_item.call_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# Constants Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestConstants:
    """Tests for module constants."""

    def test_secure_delete_passes_is_3(self) -> None:
        """SECURE_DELETE_PASSES should be 3 per DoD 5220.22-M."""
        assert SECURE_DELETE_PASSES == 3
