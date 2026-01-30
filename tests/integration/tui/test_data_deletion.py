"""Integration tests for Data Deletion Flow.

Story 11.4: Manual Data Deletion

Tests for the full deletion flow from TUI through secure deletion.
Per FR45: Manual deletion with audit logging.

These tests verify:
- End-to-end deletion flow
- Manifest updates are atomic
- Audit logging occurs
- TUI integration works correctly
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cyberred.core.audit import DeletionAuditLogger
from cyberred.core.exceptions import DeletionError
from cyberred.storage.deleter import SecureDeleter, DeletionResult, SECURE_DELETE_PASSES
from cyberred.storage.evidence import ExfiltratedDataStore, encrypt_data


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def temp_engagement_dir():
    """Create a temporary engagement directory with evidence structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engagement_path = Path(tmpdir)
        evidence_path = engagement_path / "evidence"
        data_path = evidence_path / "data"
        data_path.mkdir(parents=True)
        
        yield engagement_path


@pytest.fixture
def encryption_key() -> bytes:
    """Generate a test encryption key."""
    return b"0" * 32  # 32 bytes for AES-256


@pytest.fixture
def sample_manifest(temp_engagement_dir: Path, encryption_key: bytes) -> dict:
    """Create a sample manifest with test items."""
    evidence_path = temp_engagement_dir / "evidence"
    data_path = evidence_path / "data"
    
    items = []
    for i in range(3):
        # Create encrypted file
        content = f"sensitive data {i}".encode()
        ciphertext, nonce = encrypt_data(content, encryption_key)
        
        file_path = data_path / f"item-{i}.enc"
        file_path.write_bytes(ciphertext)
        
        items.append({
            "id": f"item-{i}",
            "filename": f"file-{i}.txt",
            "file_type": "txt",
            "mime_type": "text/plain",
            "size_bytes": len(content),
            "target": f"192.168.1.{i}",
            "source_agent": "test-agent",
            "timestamp": "2026-01-29T12:00:00Z",
            "encrypted_path": f"data/item-{i}.enc",
            "sha256_hash": "abc123",
            "nonce": nonce.hex(),
            "category": "other",
        })
    
    manifest = {"exfiltrated_data": items}
    manifest_path = evidence_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    
    return manifest


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSecureDeletionIntegration:
    """Integration tests for secure deletion."""

    def test_full_deletion_flow(
        self,
        temp_engagement_dir: Path,
        encryption_key: bytes,
        sample_manifest: dict,
    ) -> None:
        """Test full deletion flow: store -> deleter -> audit."""
        # Setup
        store = ExfiltratedDataStore(temp_engagement_dir, encryption_key)
        audit_logger = DeletionAuditLogger()  # No Redis, logs locally
        deleter = SecureDeleter(store, audit_logger)
        
        # Verify initial state
        assert len(store.list_items()) == 3
        
        # Delete first item
        deleter.delete_item("item-0")
        
        # Verify item removed from store
        assert len(store.list_items()) == 2
        assert store.get_item("item-0") is None
        
        # Verify file is deleted
        deleted_file = temp_engagement_dir / "evidence" / "data" / "item-0.enc"
        assert not deleted_file.exists()
        
        # Verify manifest updated
        manifest_path = temp_engagement_dir / "evidence" / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        assert len(manifest["exfiltrated_data"]) == 2
        assert all(item["id"] != "item-0" for item in manifest["exfiltrated_data"])

    def test_bulk_deletion_flow(
        self,
        temp_engagement_dir: Path,
        encryption_key: bytes,
        sample_manifest: dict,
    ) -> None:
        """Test bulk deletion of multiple items."""
        store = ExfiltratedDataStore(temp_engagement_dir, encryption_key)
        audit_logger = DeletionAuditLogger()
        deleter = SecureDeleter(store, audit_logger)
        
        # Delete all items
        result = deleter.delete_items(["item-0", "item-1", "item-2"])
        
        assert result.success
        assert result.total_items == 3
        assert result.deleted_items == 3
        assert len(store.list_items()) == 0

    def test_secure_overwrite_actually_overwrites(
        self,
        temp_engagement_dir: Path,
        encryption_key: bytes,
    ) -> None:
        """Verify file is actually overwritten before deletion."""
        evidence_path = temp_engagement_dir / "evidence"
        data_path = evidence_path / "data"
        data_path.mkdir(parents=True, exist_ok=True)
        
        # Create a test file with known content
        test_file = data_path / "test.enc"
        original_content = b"SENSITIVE DATA THAT MUST BE SECURELY DELETED"
        test_file.write_bytes(original_content)
        
        # Track writes
        writes = []
        original_open = open
        
        def tracking_open(path, mode="r", *args, **kwargs):
            f = original_open(path, mode, *args, **kwargs)
            if "r+b" in mode or mode == "r+b":
                original_write = f.write
                def tracked_write(data):
                    writes.append(data)
                    return original_write(data)
                f.write = tracked_write
            return f
        
        # Create store and deleter
        manifest = {"exfiltrated_data": [{
            "id": "test-item",
            "filename": "test.txt",
            "file_type": "txt",
            "mime_type": "text/plain",
            "size_bytes": len(original_content),
            "target": "192.168.1.1",
            "source_agent": "test",
            "timestamp": "2026-01-29T12:00:00Z",
            "encrypted_path": "data/test.enc",
            "sha256_hash": "abc",
            "nonce": "00" * 12,
            "category": "other",
        }]}
        (evidence_path / "manifest.json").write_text(json.dumps(manifest))
        
        store = ExfiltratedDataStore(temp_engagement_dir, encryption_key)
        audit_logger = DeletionAuditLogger()
        deleter = SecureDeleter(store, audit_logger)
        
        with patch("builtins.open", side_effect=tracking_open):
            deleter.delete_item("test-item")
        
        # Verify 3 overwrites occurred
        assert len(writes) == SECURE_DELETE_PASSES
        
        # Verify each overwrite was the same size as original
        for write_data in writes:
            assert len(write_data) == len(original_content)
            # Verify data is not the original content
            assert write_data != original_content


class TestManifestAtomicity:
    """Tests for atomic manifest updates."""

    def test_manifest_update_is_atomic(
        self,
        temp_engagement_dir: Path,
        encryption_key: bytes,
        sample_manifest: dict,
    ) -> None:
        """Verify manifest update uses atomic write pattern."""
        store = ExfiltratedDataStore(temp_engagement_dir, encryption_key)
        
        # Track temp file creation
        temp_files_created = []
        original_mkstemp = tempfile.mkstemp
        
        def tracking_mkstemp(*args, **kwargs):
            fd, path = original_mkstemp(*args, **kwargs)
            temp_files_created.append(path)
            return fd, path
        
        with patch("tempfile.mkstemp", side_effect=tracking_mkstemp):
            store._remove_from_manifest("item-0")
        
        # Verify temp file was used
        assert len(temp_files_created) == 1
        
        # Verify temp file no longer exists (was renamed)
        assert not Path(temp_files_created[0]).exists()

    def test_manifest_not_found_raises_keyerror(
        self,
        encryption_key: bytes,
    ) -> None:
        """Removing from non-existent manifest raises KeyError."""
        # Create a fresh temp dir without manifest
        with tempfile.TemporaryDirectory() as tmpdir:
            engagement_path = Path(tmpdir)
            evidence_path = engagement_path / "evidence"
            evidence_path.mkdir(parents=True)
            
            # Create store (will have empty items since no manifest)
            store = ExfiltratedDataStore(engagement_path, encryption_key)
            
            with pytest.raises(KeyError, match="Manifest not found"):
                store._remove_from_manifest("nonexistent")

    def test_item_not_in_manifest_raises_keyerror(
        self,
        temp_engagement_dir: Path,
        encryption_key: bytes,
        sample_manifest: dict,
    ) -> None:
        """Removing non-existent item from manifest raises KeyError."""
        store = ExfiltratedDataStore(temp_engagement_dir, encryption_key)
        
        with pytest.raises(KeyError, match="Item not found in manifest"):
            store._remove_from_manifest("nonexistent-item")


class TestAuditLogging:
    """Tests for deletion audit logging."""

    def test_single_deletion_logged(
        self,
        temp_engagement_dir: Path,
        encryption_key: bytes,
        sample_manifest: dict,
    ) -> None:
        """Verify single deletion is logged to audit trail."""
        store = ExfiltratedDataStore(temp_engagement_dir, encryption_key)
        audit_logger = MagicMock(spec=DeletionAuditLogger)
        deleter = SecureDeleter(store, audit_logger)
        
        deleter.delete_item("item-0")
        
        audit_logger.log_deletion.assert_called_once()
        call_args = audit_logger.log_deletion.call_args
        assert call_args[0][0] == "item-0"  # item_id
        assert call_args[0][1] == "file-0.txt"  # filename
        assert call_args[0][2] == "192.168.1.0"  # target

    def test_bulk_deletion_logged(
        self,
        temp_engagement_dir: Path,
        encryption_key: bytes,
        sample_manifest: dict,
    ) -> None:
        """Verify bulk deletion is logged to audit trail."""
        store = ExfiltratedDataStore(temp_engagement_dir, encryption_key)
        audit_logger = MagicMock(spec=DeletionAuditLogger)
        deleter = SecureDeleter(store, audit_logger)
        
        deleter.delete_items(["item-0", "item-1"])
        
        # Should log individual deletions plus bulk summary
        assert audit_logger.log_deletion.call_count == 2
        audit_logger.log_bulk_deletion.assert_called_once()
