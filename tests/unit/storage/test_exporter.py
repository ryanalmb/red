"""Unit tests for DataExporter class.

Story 11.3: Data Export from TUI

Tests for:
- Single item export with decryption
- Archive export with manifest
- Progress tracking
- Cancellation support
- Error handling (permission denied, disk full)
- Cleanup on failure
"""

from __future__ import annotations

import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, patch

import pytest

from cyberred.core.exceptions import ExportError

if TYPE_CHECKING:
    from cyberred.storage.evidence import ExfiltratedDataItem


# === Fixtures ===


@pytest.fixture
def mock_store():
    """Create mock ExfiltratedDataStore."""
    store = MagicMock()
    return store


@pytest.fixture
def mock_audit_logger():
    """Create mock AuditLogger."""
    logger = MagicMock()
    return logger


@pytest.fixture
def sample_item():
    """Create sample ExfiltratedDataItem."""
    item = MagicMock()
    item.id = "item-001"
    item.filename = "shadow"
    item.file_type = "shadow"
    item.mime_type = "text/plain"
    item.size_bytes = 1024
    item.target = "192.168.1.100"
    item.source_agent = "postex-agent-1"
    item.timestamp = datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc)
    item.category = "credentials"
    item.to_dict.return_value = {
        "id": "item-001",
        "filename": "shadow",
        "file_type": "shadow",
        "mime_type": "text/plain",
        "size_bytes": 1024,
        "target": "192.168.1.100",
        "source_agent": "postex-agent-1",
        "timestamp": "2026-01-29T12:00:00+00:00",
        "category": "credentials",
    }
    return item


@pytest.fixture
def sample_content():
    """Sample decrypted content."""
    return b"root:x:0:0:root:/root:/bin/bash\ndaemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin"


# === Task 1: Unit tests for DataExporter class (AC: #1, #2, #6) ===


class TestDataExporterInit:
    """Test DataExporter.__init__()."""

    def test_init_with_store_and_audit_logger(self, mock_store, mock_audit_logger):
        """Test DataExporter initializes with store and audit logger."""
        from cyberred.storage.exporter import DataExporter

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        assert exporter._store is mock_store
        assert exporter._audit is mock_audit_logger
        assert exporter._engagement_name == "test-engagement"


class TestGetDefaultExportPath:
    """Test DataExporter.get_default_export_path()."""

    def test_returns_expected_format(self, mock_store, mock_audit_logger, sample_item):
        """Test default path is ~/cyber-red-exports/{engagement}/{filename}."""
        from cyberred.storage.exporter import DataExporter

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="ministry-2025",
        )

        path = exporter.get_default_export_path(sample_item)

        expected = Path.home() / "cyber-red-exports" / "ministry-2025" / "shadow"
        assert path == expected


class TestExportSingleItem:
    """Test DataExporter.export_single_item()."""

    def test_decrypts_and_writes_to_path(
        self, mock_store, mock_audit_logger, sample_item, sample_content, tmp_path
    ):
        """Test export_single_item decrypts and writes to destination."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = sample_item
        mock_store.get_item_content.return_value = sample_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "exported_shadow"
        result = exporter.export_single_item("item-001", destination)

        assert result == destination
        assert destination.exists()
        assert destination.read_bytes() == sample_content

    def test_preserves_original_filename(
        self, mock_store, mock_audit_logger, sample_item, sample_content, tmp_path
    ):
        """Test export preserves original filename when using default path."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = sample_item
        mock_store.get_item_content.return_value = sample_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        # Use a path that matches the original filename
        destination = tmp_path / "shadow"
        result = exporter.export_single_item("item-001", destination)

        assert result.name == "shadow"

    def test_creates_parent_directories(
        self, mock_store, mock_audit_logger, sample_item, sample_content, tmp_path
    ):
        """Test export creates parent directories if needed."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = sample_item
        mock_store.get_item_content.return_value = sample_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "deep" / "nested" / "path" / "shadow"
        result = exporter.export_single_item("item-001", destination)

        assert destination.exists()
        assert destination.parent.exists()

    def test_logs_to_audit_trail(
        self, mock_store, mock_audit_logger, sample_item, sample_content, tmp_path
    ):
        """Test export logs to audit trail."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = sample_item
        mock_store.get_item_content.return_value = sample_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "shadow"
        exporter.export_single_item("item-001", destination)

        mock_audit_logger.log_export.assert_called_once_with(
            item_id="item-001",
            filename="shadow",
            destination=str(destination),
        )

    def test_raises_export_error_on_permission_denied(
        self, mock_store, mock_audit_logger, sample_item, sample_content, tmp_path
    ):
        """Test raises ExportError on permission denied."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = sample_item
        # Simulate permission error during content retrieval
        mock_store.get_item_content.side_effect = PermissionError("Permission denied")

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "shadow"
        with pytest.raises(ExportError) as exc_info:
            exporter.export_single_item("item-001", destination)

        assert "Permission denied" in str(exc_info.value)

    def test_raises_export_error_on_disk_full(
        self, mock_store, mock_audit_logger, sample_item, tmp_path
    ):
        """Test raises ExportError on disk full."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = sample_item
        # Simulate disk full by raising OSError with errno 28
        mock_store.get_item_content.side_effect = OSError(28, "No space left on device")

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "shadow"
        with pytest.raises(ExportError) as exc_info:
            exporter.export_single_item("item-001", destination)

        assert "Disk full" in str(exc_info.value) or "No space left" in str(exc_info.value)

    def test_cleans_up_partial_files_on_failure(
        self, mock_store, mock_audit_logger, sample_item, tmp_path
    ):
        """Test cleanup of partial files on failure."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = sample_item
        mock_store.get_item_content.side_effect = Exception("Unexpected error")

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "shadow"
        with pytest.raises(ExportError):
            exporter.export_single_item("item-001", destination)

        # Temp file should not exist
        temp_path = destination.with_suffix(destination.suffix + ".tmp")
        assert not temp_path.exists()
        assert not destination.exists()

    def test_raises_key_error_for_nonexistent_item(
        self, mock_store, mock_audit_logger, tmp_path
    ):
        """Test raises KeyError for non-existent item."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = None

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "shadow"
        with pytest.raises(KeyError) as exc_info:
            exporter.export_single_item("nonexistent", destination)

        assert "nonexistent" in str(exc_info.value)


# === Task 2: Unit tests for archive export (AC: #3, #4) ===


class TestExportArchive:
    """Test DataExporter.export_archive()."""

    def test_creates_valid_zip_file(
        self, mock_store, mock_audit_logger, sample_item, sample_content, tmp_path
    ):
        """Test export_archive creates valid ZIP file."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = sample_item
        mock_store.get_item_content.return_value = sample_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "export.zip"
        result = exporter.export_archive(["item-001"], destination)

        assert result == destination
        assert destination.exists()
        assert zipfile.is_zipfile(destination)

    def test_includes_all_items_with_original_names(
        self, mock_store, mock_audit_logger, sample_content, tmp_path
    ):
        """Test archive includes all items with original names."""
        from cyberred.storage.exporter import DataExporter

        # Create multiple items
        items = []
        for i, name in enumerate(["shadow", "passwd", "config.json"]):
            item = MagicMock()
            item.id = f"item-{i:03d}"
            item.filename = name
            item.size_bytes = 1024
            item.to_dict.return_value = {"id": item.id, "filename": name, "size_bytes": 1024}
            items.append(item)

        mock_store.get_item.side_effect = lambda id: next(
            (i for i in items if i.id == id), None
        )
        mock_store.get_item_content.return_value = sample_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "export.zip"
        exporter.export_archive(["item-000", "item-001", "item-002"], destination)

        with zipfile.ZipFile(destination, "r") as zf:
            names = zf.namelist()
            assert "shadow" in names
            assert "passwd" in names
            assert "config.json" in names

    def test_generates_manifest_json_with_correct_schema(
        self, mock_store, mock_audit_logger, sample_item, sample_content, tmp_path
    ):
        """Test archive includes manifest.json with correct schema."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = sample_item
        mock_store.get_item_content.return_value = sample_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="ministry-2025",
        )

        destination = tmp_path / "export.zip"
        exporter.export_archive(["item-001"], destination)

        with zipfile.ZipFile(destination, "r") as zf:
            assert "manifest.json" in zf.namelist()
            manifest = json.loads(zf.read("manifest.json"))

            # Verify schema
            assert manifest["schema_version"] == "1.0.0"
            assert manifest["engagement_name"] == "ministry-2025"
            assert "export_timestamp" in manifest
            assert manifest["total_items"] == 1
            assert "items" in manifest
            assert len(manifest["items"]) == 1

    def test_names_archive_with_timestamp_format(
        self, mock_store, mock_audit_logger, sample_item, sample_content, tmp_path
    ):
        """Test archive naming follows timestamp format."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = sample_item
        mock_store.get_item_content.return_value = sample_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        # Use timestamp in name as per AC#4
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        destination = tmp_path / f"test-engagement_export_{timestamp}.zip"
        result = exporter.export_archive(["item-001"], destination)

        assert "export" in result.name
        assert result.suffix == ".zip"

    def test_handles_duplicate_filenames(
        self, mock_store, mock_audit_logger, sample_content, tmp_path
    ):
        """Test duplicate filenames are handled with suffix."""
        from cyberred.storage.exporter import DataExporter

        # Create items with duplicate filenames
        items = []
        for i in range(3):
            item = MagicMock()
            item.id = f"item-{i:03d}"
            item.filename = "shadow"  # All same name
            item.size_bytes = 1024
            item.to_dict.return_value = {"id": item.id, "filename": "shadow", "size_bytes": 1024}
            items.append(item)

        mock_store.get_item.side_effect = lambda id: next(
            (i for i in items if i.id == id), None
        )
        mock_store.get_item_content.return_value = sample_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "export.zip"
        exporter.export_archive(["item-000", "item-001", "item-002"], destination)

        with zipfile.ZipFile(destination, "r") as zf:
            names = zf.namelist()
            # Should have shadow, shadow_1, shadow_2 (plus manifest)
            shadow_files = [n for n in names if n.startswith("shadow")]
            assert len(shadow_files) == 3

    def test_logs_archive_export_to_audit_trail(
        self, mock_store, mock_audit_logger, sample_item, sample_content, tmp_path
    ):
        """Test archive export logs to audit trail."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = sample_item
        mock_store.get_item_content.return_value = sample_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "export.zip"
        exporter.export_archive(["item-001"], destination)

        mock_audit_logger.log_archive_export.assert_called_once_with(
            item_ids=["item-001"],
            destination=str(destination),
            item_count=1,
        )

    def test_cleans_up_partial_archive_on_failure(
        self, mock_store, mock_audit_logger, sample_item, tmp_path
    ):
        """Test cleanup of partial archive on failure."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = sample_item
        mock_store.get_item_content.side_effect = Exception("Unexpected error")

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "export.zip"
        with pytest.raises(ExportError):
            exporter.export_archive(["item-001"], destination)

        # Temp file should not exist
        temp_path = destination.with_suffix(".zip.tmp")
        assert not temp_path.exists()
        assert not destination.exists()

    def test_manifest_contains_required_fields(
        self, mock_store, mock_audit_logger, sample_item, sample_content, tmp_path
    ):
        """Test manifest contains items metadata, export_timestamp, engagement_id."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = sample_item
        mock_store.get_item_content.return_value = sample_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="ministry-2025",
        )

        destination = tmp_path / "export.zip"
        exporter.export_archive(["item-001"], destination)

        with zipfile.ZipFile(destination, "r") as zf:
            manifest = json.loads(zf.read("manifest.json"))

            # Required fields per AC#4
            assert "export_timestamp" in manifest
            assert "engagement_name" in manifest
            assert "items" in manifest
            assert len(manifest["items"]) > 0

            # Item metadata
            item_meta = manifest["items"][0]
            assert "archive_name" in item_meta


# === Task 3: Unit tests for export progress tracking (AC: #5) ===


class TestExportProgress:
    """Test ExportProgress dataclass."""

    def test_tracks_total_and_completed_counts(self):
        """Test ExportProgress tracks total/completed counts."""
        from cyberred.storage.exporter import ExportProgress

        progress = ExportProgress(
            total_items=10,
            completed_items=5,
            total_bytes=10240,
            completed_bytes=5120,
        )

        assert progress.total_items == 10
        assert progress.completed_items == 5

    def test_tracks_total_and_completed_bytes(self):
        """Test ExportProgress tracks total/completed bytes."""
        from cyberred.storage.exporter import ExportProgress

        progress = ExportProgress(
            total_items=10,
            completed_items=5,
            total_bytes=10240,
            completed_bytes=5120,
        )

        assert progress.total_bytes == 10240
        assert progress.completed_bytes == 5120

    def test_percentage_property_calculates_correctly(self):
        """Test percentage property calculates correctly."""
        from cyberred.storage.exporter import ExportProgress

        progress = ExportProgress(
            total_items=10,
            completed_items=5,
            total_bytes=10240,
            completed_bytes=5120,
        )

        assert progress.percentage == 50.0

    def test_percentage_handles_zero_items(self):
        """Test percentage returns 100 for zero items."""
        from cyberred.storage.exporter import ExportProgress

        progress = ExportProgress(
            total_items=0,
            completed_items=0,
            total_bytes=0,
            completed_bytes=0,
        )

        assert progress.percentage == 100.0

    def test_is_large_export_over_10_items(self):
        """Test is_large_export for >10 items."""
        from cyberred.storage.exporter import ExportProgress

        progress = ExportProgress(
            total_items=11,
            completed_items=0,
            total_bytes=1024,
            completed_bytes=0,
        )

        assert progress.is_large_export is True

    def test_is_large_export_over_10mb(self):
        """Test is_large_export for >10MB."""
        from cyberred.storage.exporter import ExportProgress

        progress = ExportProgress(
            total_items=5,
            completed_items=0,
            total_bytes=11 * 1024 * 1024,  # 11MB
            completed_bytes=0,
        )

        assert progress.is_large_export is True

    def test_is_large_export_false_for_small(self):
        """Test is_large_export is False for small exports."""
        from cyberred.storage.exporter import ExportProgress

        progress = ExportProgress(
            total_items=5,
            completed_items=0,
            total_bytes=1024,
            completed_bytes=0,
        )

        assert progress.is_large_export is False


class TestCancellationToken:
    """Test CancellationToken."""

    def test_initial_state_not_cancelled(self):
        """Test token is not cancelled initially."""
        from cyberred.storage.exporter import CancellationToken

        token = CancellationToken()
        assert token.is_cancelled is False

    def test_cancel_sets_cancelled_flag(self):
        """Test cancel() sets cancelled flag."""
        from cyberred.storage.exporter import CancellationToken

        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled is True

    def test_export_cancelled_via_token(
        self, mock_store, mock_audit_logger, sample_item, sample_content, tmp_path
    ):
        """Test cancelled export raises ExportError."""
        from cyberred.storage.exporter import CancellationToken, DataExporter

        mock_store.get_item.return_value = sample_item
        mock_store.get_item_content.return_value = sample_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        token = CancellationToken()
        token.cancel()

        destination = tmp_path / "shadow"
        with pytest.raises(ExportError) as exc_info:
            exporter.export_single_item("item-001", destination, cancellation_token=token)

        assert "cancelled" in str(exc_info.value).lower()

    def test_cancelled_export_cleans_up(
        self, mock_store, mock_audit_logger, sample_item, sample_content, tmp_path
    ):
        """Test cancelled export cleans up partial output."""
        from cyberred.storage.exporter import CancellationToken, DataExporter

        mock_store.get_item.return_value = sample_item
        mock_store.get_item_content.return_value = sample_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        token = CancellationToken()
        token.cancel()

        destination = tmp_path / "shadow"
        with pytest.raises(ExportError):
            exporter.export_single_item("item-001", destination, cancellation_token=token)

        assert not destination.exists()
        assert not destination.with_suffix(".tmp").exists()

    def test_mid_export_cancellation_single_item(
        self, mock_store, mock_audit_logger, sample_item, tmp_path
    ):
        """Test cancellation after content retrieval (line 195)."""
        from cyberred.storage.exporter import CancellationToken, DataExporter

        mock_store.get_item.return_value = sample_item
        
        # Create a token that gets cancelled during content retrieval
        token = CancellationToken()
        
        def cancel_during_get_content(item_id):
            token.cancel()  # Cancel after get_item but during get_content
            return b"content"
        
        mock_store.get_item_content.side_effect = cancel_during_get_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "shadow"
        with pytest.raises(ExportError) as exc_info:
            exporter.export_single_item("item-001", destination, cancellation_token=token)

        assert "cancelled" in str(exc_info.value).lower()

    def test_mid_export_cancellation_archive(
        self, mock_store, mock_audit_logger, sample_content, tmp_path
    ):
        """Test cancellation during archive export (line 293)."""
        from cyberred.storage.exporter import CancellationToken, DataExporter

        # Create multiple items
        items = []
        for i in range(3):
            item = MagicMock()
            item.id = f"item-{i:03d}"
            item.filename = f"file{i}.txt"
            item.size_bytes = 100
            item.to_dict.return_value = {"id": item.id, "filename": item.filename}
            items.append(item)

        mock_store.get_item.side_effect = lambda id: next(
            (i for i in items if i.id == id), None
        )
        
        token = CancellationToken()
        call_count = [0]
        
        def cancel_on_second_item(item_id):
            call_count[0] += 1
            if call_count[0] >= 2:
                token.cancel()
            return sample_content
        
        mock_store.get_item_content.side_effect = cancel_on_second_item

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "export.zip"
        with pytest.raises(ExportError) as exc_info:
            exporter.export_archive(
                ["item-000", "item-001", "item-002"],
                destination,
                cancellation_token=token,
            )

        assert "cancelled" in str(exc_info.value).lower()


class TestProgressCallback:
    """Test progress callback functionality."""

    def test_progress_callback_called_during_archive(
        self, mock_store, mock_audit_logger, sample_content, tmp_path
    ):
        """Test progress callback is invoked (line 297)."""
        from cyberred.storage.exporter import DataExporter, ExportProgress

        items = []
        for i in range(3):
            item = MagicMock()
            item.id = f"item-{i:03d}"
            item.filename = f"file{i}.txt"
            item.size_bytes = 100
            item.to_dict.return_value = {"id": item.id, "filename": item.filename}
            items.append(item)

        mock_store.get_item.side_effect = lambda id: next(
            (i for i in items if i.id == id), None
        )
        mock_store.get_item_content.return_value = sample_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        progress_updates = []
        
        def track_progress(progress: ExportProgress):
            progress_updates.append({
                "current_item": progress.current_item,
                "completed": progress.completed_items,
                "total": progress.total_items,
            })

        destination = tmp_path / "export.zip"
        exporter.export_archive(
            ["item-000", "item-001", "item-002"],
            destination,
            progress_callback=track_progress,
        )

        assert len(progress_updates) == 3
        assert progress_updates[0]["current_item"] == "file0.txt"
        assert progress_updates[1]["current_item"] == "file1.txt"
        assert progress_updates[2]["current_item"] == "file2.txt"


class TestDuplicateFilenamesWithExtensions:
    """Test duplicate filename handling with extensions (lines 306-308)."""

    def test_handles_duplicate_filenames_with_extension(
        self, mock_store, mock_audit_logger, sample_content, tmp_path
    ):
        """Test duplicate filenames with extensions get proper suffixes."""
        from cyberred.storage.exporter import DataExporter

        # Create items with duplicate filenames that have extensions
        items = []
        for i in range(3):
            item = MagicMock()
            item.id = f"item-{i:03d}"
            item.filename = "config.json"  # All same name with extension
            item.size_bytes = 100
            item.to_dict.return_value = {"id": item.id, "filename": "config.json"}
            items.append(item)

        mock_store.get_item.side_effect = lambda id: next(
            (i for i in items if i.id == id), None
        )
        mock_store.get_item_content.return_value = sample_content

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "export.zip"
        exporter.export_archive(["item-000", "item-001", "item-002"], destination)

        with zipfile.ZipFile(destination, "r") as zf:
            names = zf.namelist()
            # Should have config.json, config_1.json, config_2.json
            config_files = sorted([n for n in names if n.startswith("config")])
            assert "config.json" in config_files
            assert "config_1.json" in config_files
            assert "config_2.json" in config_files


class TestExportErrorReraise:
    """Test ExportError re-raise paths (lines 232-233, 351-352)."""

    def test_export_error_reraises_in_single_item(
        self, mock_store, mock_audit_logger, sample_item, tmp_path
    ):
        """Test ExportError is re-raised without wrapping (line 232-233)."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = sample_item
        mock_store.get_item_content.side_effect = ExportError("Custom error", destination="/test")

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "shadow"
        with pytest.raises(ExportError) as exc_info:
            exporter.export_single_item("item-001", destination)

        # Should be the original error, not wrapped
        assert "Custom error" in str(exc_info.value)

    def test_export_error_reraises_in_archive(
        self, mock_store, mock_audit_logger, sample_item, tmp_path
    ):
        """Test ExportError is re-raised without wrapping in archive (line 351-352)."""
        from cyberred.storage.exporter import DataExporter

        mock_store.get_item.return_value = sample_item
        mock_store.get_item_content.side_effect = ExportError("Archive custom error")

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "export.zip"
        with pytest.raises(ExportError) as exc_info:
            exporter.export_archive(["item-001"], destination)

        # Should be the original error, not wrapped
        assert "Archive custom error" in str(exc_info.value)


class TestCleanupExceptionHandling:
    """Test cleanup exception handling (lines 369-370)."""

    def test_cleanup_handles_exception_gracefully(self, tmp_path):
        """Test _cleanup_temp handles exceptions silently."""
        from cyberred.storage.exporter import DataExporter
        from unittest.mock import MagicMock, patch

        exporter = DataExporter(
            store=MagicMock(),
            audit_logger=MagicMock(),
            engagement_name="test",
        )

        # Create a path that will raise an exception during unlink
        temp_path = tmp_path / "test.tmp"
        temp_path.write_text("test")

        # Mock Path.exists to return True but unlink to raise
        with patch.object(type(temp_path), 'unlink', side_effect=PermissionError("Cannot delete")):
            # Should not raise - cleanup is best effort
            exporter._cleanup_temp(temp_path)

    def test_cleanup_nonexistent_file(self, tmp_path):
        """Test _cleanup_temp handles nonexistent files."""
        from cyberred.storage.exporter import DataExporter

        exporter = DataExporter(
            store=MagicMock(),
            audit_logger=MagicMock(),
            engagement_name="test",
        )

        # Nonexistent path should not raise
        nonexistent = tmp_path / "does_not_exist.tmp"
        exporter._cleanup_temp(nonexistent)  # Should not raise


class TestOSErrorHandling:
    """Test OSError handling (non-disk-full errors)."""

    def test_generic_oserror_raises_export_error(
        self, mock_store, mock_audit_logger, sample_item, tmp_path
    ):
        """Test generic OSError raises ExportError (line 227)."""
        from cyberred.storage.exporter import DataExporter
        import errno

        mock_store.get_item.return_value = sample_item
        
        # Create an OSError that is NOT disk full (errno 28)
        os_error = OSError("Network error")
        os_error.errno = errno.ENETUNREACH  # Network unreachable
        mock_store.get_item_content.side_effect = os_error

        exporter = DataExporter(
            store=mock_store,
            audit_logger=mock_audit_logger,
            engagement_name="test-engagement",
        )

        destination = tmp_path / "shadow"
        with pytest.raises(ExportError) as exc_info:
            exporter.export_single_item("item-001", destination)

        assert "Export failed" in str(exc_info.value)
        assert "Network error" in str(exc_info.value)
