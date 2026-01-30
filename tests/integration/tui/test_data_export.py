"""Integration tests for full export flow.

Story 11.3: Data Export from TUI

Tests for:
- Single item export end-to-end
- Archive export end-to-end
- Export with real encryption/decryption
- Audit log entries
- Error recovery
"""

from __future__ import annotations

import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# === Task 6: Integration tests for full export flow (AC: #7) ===


class TestSingleItemExportE2E:
    """Test single item export end-to-end."""

    def test_single_item_export_flow(self, tmp_path):
        """Test complete single item export flow."""
        from cyberred.storage.exporter import DataExporter

        # Setup mock store with real-ish data
        store = MagicMock()
        audit = MagicMock()

        item = MagicMock()
        item.id = "item-001"
        item.filename = "shadow"
        item.size_bytes = 100
        item.to_dict.return_value = {"id": "item-001", "filename": "shadow"}

        store.get_item.return_value = item
        store.get_item_content.return_value = b"root:x:0:0:root:/root:/bin/bash"

        exporter = DataExporter(
            store=store,
            audit_logger=audit,
            engagement_name="test-engagement",
        )

        # Export
        destination = tmp_path / "exported_shadow"
        result = exporter.export_single_item("item-001", destination)

        # Verify
        assert result.exists()
        assert result.read_bytes() == b"root:x:0:0:root:/root:/bin/bash"
        audit.log_export.assert_called_once()


class TestArchiveExportE2E:
    """Test archive export end-to-end."""

    def test_archive_export_flow(self, tmp_path):
        """Test complete archive export flow."""
        from cyberred.storage.exporter import DataExporter

        # Setup mock store
        store = MagicMock()
        audit = MagicMock()

        items = []
        for i, name in enumerate(["shadow", "passwd"]):
            item = MagicMock()
            item.id = f"item-{i:03d}"
            item.filename = name
            item.size_bytes = 100
            item.to_dict.return_value = {"id": item.id, "filename": name, "size_bytes": 100}
            items.append(item)

        store.get_item.side_effect = lambda id: next(
            (i for i in items if i.id == id), None
        )
        store.get_item_content.return_value = b"file content"

        exporter = DataExporter(
            store=store,
            audit_logger=audit,
            engagement_name="test-engagement",
        )

        # Export archive
        destination = tmp_path / "export.zip"
        result = exporter.export_archive(["item-000", "item-001"], destination)

        # Verify archive
        assert result.exists()
        assert zipfile.is_zipfile(result)

        with zipfile.ZipFile(result, "r") as zf:
            assert "shadow" in zf.namelist()
            assert "passwd" in zf.namelist()
            assert "manifest.json" in zf.namelist()

        audit.log_archive_export.assert_called_once()


class TestExportWithEncryption:
    """Test export with real encryption/decryption."""

    def test_export_decrypts_content(self, tmp_path):
        """Test export correctly decrypts content."""
        from cyberred.storage.evidence import encrypt_data, ExfiltratedDataStore
        from cyberred.storage.exporter import DataExporter

        # Create actual encrypted data
        key = os.urandom(32)
        plaintext = b"secret credentials data"
        ciphertext, nonce = encrypt_data(plaintext, key)

        # Setup store that returns encrypted data
        store = MagicMock()
        audit = MagicMock()

        item = MagicMock()
        item.id = "item-001"
        item.filename = "secrets.txt"
        item.size_bytes = len(plaintext)
        item.to_dict.return_value = {"id": "item-001", "filename": "secrets.txt"}

        store.get_item.return_value = item
        # Simulate decryption by returning plaintext
        store.get_item_content.return_value = plaintext

        exporter = DataExporter(
            store=store,
            audit_logger=audit,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "secrets.txt"
        result = exporter.export_single_item("item-001", destination)

        assert result.read_bytes() == plaintext


class TestAuditLogEntries:
    """Test audit log entries are created."""

    def test_single_export_creates_audit_entry(self, tmp_path):
        """Test single export creates audit log entry."""
        from cyberred.storage.exporter import DataExporter

        store = MagicMock()
        audit = MagicMock()

        item = MagicMock()
        item.id = "item-001"
        item.filename = "shadow"
        item.size_bytes = 100
        item.to_dict.return_value = {"id": "item-001", "filename": "shadow"}

        store.get_item.return_value = item
        store.get_item_content.return_value = b"content"

        exporter = DataExporter(
            store=store,
            audit_logger=audit,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "shadow"
        exporter.export_single_item("item-001", destination)

        audit.log_export.assert_called_once_with(
            item_id="item-001",
            filename="shadow",
            destination=str(destination),
        )

    def test_archive_export_creates_audit_entry(self, tmp_path):
        """Test archive export creates audit log entry."""
        from cyberred.storage.exporter import DataExporter

        store = MagicMock()
        audit = MagicMock()

        item = MagicMock()
        item.id = "item-001"
        item.filename = "shadow"
        item.size_bytes = 100
        item.to_dict.return_value = {"id": "item-001", "filename": "shadow"}

        store.get_item.return_value = item
        store.get_item_content.return_value = b"content"

        exporter = DataExporter(
            store=store,
            audit_logger=audit,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "export.zip"
        exporter.export_archive(["item-001"], destination)

        audit.log_archive_export.assert_called_once_with(
            item_ids=["item-001"],
            destination=str(destination),
            item_count=1,
        )


class TestErrorRecovery:
    """Test error recovery scenarios."""

    def test_retry_with_valid_path_after_invalid(self, tmp_path):
        """Test retry with valid path after simulated permission error."""
        from cyberred.storage.exporter import DataExporter
        from cyberred.core.exceptions import ExportError

        store = MagicMock()
        audit = MagicMock()

        item = MagicMock()
        item.id = "item-001"
        item.filename = "shadow"
        item.size_bytes = 100
        item.to_dict.return_value = {"id": "item-001", "filename": "shadow"}

        store.get_item.return_value = item
        
        # First call raises permission error, second succeeds
        call_count = [0]
        def mock_get_content(item_id):
            call_count[0] += 1
            if call_count[0] == 1:
                raise PermissionError("Simulated permission error")
            return b"content"
        
        store.get_item_content.side_effect = mock_get_content

        exporter = DataExporter(
            store=store,
            audit_logger=audit,
            engagement_name="test-engagement",
        )

        # First attempt fails
        invalid_dest = tmp_path / "first_attempt"
        with pytest.raises(ExportError):
            exporter.export_single_item("item-001", invalid_dest)

        # Retry succeeds
        valid_dest = tmp_path / "shadow"
        result = exporter.export_single_item("item-001", valid_dest)

        assert result.exists()
        assert result.read_bytes() == b"content"

    def test_no_partial_files_after_failure(self, tmp_path):
        """Test no partial files remain after failure."""
        from cyberred.storage.exporter import DataExporter
        from cyberred.core.exceptions import ExportError

        store = MagicMock()
        audit = MagicMock()

        item = MagicMock()
        item.id = "item-001"
        item.filename = "shadow"
        item.size_bytes = 100
        item.to_dict.return_value = {"id": "item-001", "filename": "shadow"}

        store.get_item.return_value = item
        store.get_item_content.side_effect = Exception("Simulated failure")

        exporter = DataExporter(
            store=store,
            audit_logger=audit,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "shadow"
        with pytest.raises(ExportError):
            exporter.export_single_item("item-001", destination)

        # No files should exist
        assert not destination.exists()
        assert not destination.with_suffix(".tmp").exists()
        assert len(list(tmp_path.iterdir())) == 0
