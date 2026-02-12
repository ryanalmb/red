"""Unit tests for Evidence File Storage (Story 13.1).

Tests for EvidenceStore, EvidenceItem, and EvidenceType following TDD red-green-refactor.
All tests should FAIL initially (RED phase) until implementation is complete.

Acceptance Criteria tested:
- AC #2: Evidence file captured (screenshot, log, loot)
- AC #3: File stored in ~/.cyber-red/evidence/{engagement_id}/
- AC #4: File encrypted at rest (AES-256)
- AC #5: SHA-256 hash recorded in manifest.json
- AC #6: Manifest includes: filename, hash, timestamp, source_agent
- AC #7: Unit tests verify hash integrity
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    pass


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def encryption_key() -> bytes:
    """Valid 32-byte AES-256 encryption key."""
    return os.urandom(32)


@pytest.fixture
def invalid_encryption_key() -> bytes:
    """Invalid 16-byte key (not 32 bytes)."""
    return os.urandom(16)


@pytest.fixture
def engagement_id() -> str:
    """Test engagement ID."""
    return f"eng-{uuid.uuid4()}"


@pytest.fixture
def temp_evidence_dir(tmp_path: Path) -> Path:
    """Temporary base path for evidence storage."""
    return tmp_path / "evidence"


@pytest.fixture
def sample_evidence_content() -> bytes:
    """Sample evidence content (screenshot simulation)."""
    return b"PNG\x89\x50\x4e\x47\x0d\x0a\x1a\x0a" + os.urandom(1024)


@pytest.fixture
def large_evidence_content() -> bytes:
    """Large evidence content (1MB+ for large file test)."""
    return os.urandom(1024 * 1024 + 100)  # 1MB + 100 bytes


# ============================================================================
# Task 2: Evidence Store Initialization Tests (AC #3)
# ============================================================================


class TestEvidenceStoreInitialization:
    """Tests for EvidenceStore.__init__ (AC #3)."""

    def test_creates_directory_structure(
        self, engagement_id: str, encryption_key: bytes, temp_evidence_dir: Path
    ) -> None:
        """Test EvidenceStore creates directory structure on init."""
        # GIVEN: A valid engagement_id and encryption_key
        # WHEN: EvidenceStore is initialized
        from cyberred.storage.evidence_store import EvidenceStore

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # THEN: Directory structure is created
        expected_dir = temp_evidence_dir / engagement_id
        assert expected_dir.exists()
        assert (expected_dir / "data").exists()

    def test_creates_manifest_if_not_exists(
        self, engagement_id: str, encryption_key: bytes, temp_evidence_dir: Path
    ) -> None:
        """Test manifest.json is created if not exists."""
        # GIVEN: A fresh directory with no manifest
        from cyberred.storage.evidence_store import EvidenceStore

        # WHEN: EvidenceStore is initialized
        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # THEN: manifest.json is created
        manifest_path = temp_evidence_dir / engagement_id / "manifest.json"
        assert manifest_path.exists()

        # AND: manifest has correct structure
        with open(manifest_path) as f:
            manifest = json.load(f)
        assert manifest["version"] == "1.0"
        assert manifest["engagement_id"] == engagement_id
        assert "created_at" in manifest
        assert manifest["evidence"] == []

    def test_loads_existing_manifest(
        self, engagement_id: str, encryption_key: bytes, temp_evidence_dir: Path
    ) -> None:
        """Test manifest.json is loaded if exists."""
        # GIVEN: An existing manifest with evidence items
        from cyberred.storage.evidence_store import EvidenceStore

        evidence_dir = temp_evidence_dir / engagement_id
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "data").mkdir()

        existing_manifest = {
            "version": "1.0",
            "engagement_id": engagement_id,
            "created_at": "2026-02-12T00:00:00Z",
            "evidence": [
                {
                    "id": "test-uuid-1",
                    "filename": "test.png",
                    "sha256_hash": "abc123",
                    "encrypted_path": "data/test-uuid-1.enc",
                    "nonce": "0" * 24,
                    "size_bytes": 100,
                    "timestamp": "2026-02-12T01:00:00Z",
                    "source_agent": "recon-01",
                    "evidence_type": "screenshot",
                }
            ],
        }
        manifest_path = evidence_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(existing_manifest, f)

        # WHEN: EvidenceStore is initialized
        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # THEN: Existing evidence is loaded
        items = store.list_evidence()
        assert len(items) == 1
        assert items[0].filename == "test.png"

    def test_invalid_encryption_key_raises_valueerror(
        self, engagement_id: str, invalid_encryption_key: bytes, temp_evidence_dir: Path
    ) -> None:
        """Test invalid encryption key raises ValueError."""
        # GIVEN: An invalid 16-byte key (not 32 bytes)
        from cyberred.storage.evidence_store import EvidenceStore

        # WHEN/THEN: ValueError is raised
        with pytest.raises(ValueError, match="32 bytes"):
            EvidenceStore(
                engagement_id=engagement_id,
                encryption_key=invalid_encryption_key,
                base_path=temp_evidence_dir,
            )

    def test_default_base_path_is_home_cyber_red(
        self, engagement_id: str, encryption_key: bytes
    ) -> None:
        """Test default base_path is ~/.cyber-red/evidence."""
        from cyberred.storage.evidence_store import EvidenceStore

        # Mock Path.home() to return a temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                store = EvidenceStore(
                    engagement_id=engagement_id,
                    encryption_key=encryption_key,
                )

                expected_dir = Path(tmpdir) / ".cyber-red" / "evidence" / engagement_id
                assert expected_dir.exists()


# ============================================================================
# Task 3: Evidence Storage Tests (AC #2, #4, #5, #6)
# ============================================================================


class TestEvidenceStorage:
    """Tests for store_evidence method (AC #2, #4, #5, #6)."""

    def test_store_evidence_returns_evidence_item(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test store_evidence returns EvidenceItem."""
        # GIVEN: An initialized EvidenceStore
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceItem, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # WHEN: Evidence is stored
        item = store.store_evidence(
            content=sample_evidence_content,
            filename="screenshot.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # THEN: EvidenceItem is returned with correct attributes
        assert isinstance(item, EvidenceItem)
        assert item.filename == "screenshot.png"
        assert item.source_agent == "recon-01"
        assert item.evidence_type == EvidenceType.SCREENSHOT

    def test_file_is_encrypted_with_aes256_gcm(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test file is encrypted with AES-256-GCM (AC #4)."""
        # GIVEN: An initialized EvidenceStore
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # WHEN: Evidence is stored
        item = store.store_evidence(
            content=sample_evidence_content,
            filename="screenshot.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # THEN: Encrypted file exists and content is NOT plaintext
        encrypted_path = temp_evidence_dir / engagement_id / item.encrypted_path
        assert encrypted_path.exists()

        encrypted_content = encrypted_path.read_bytes()
        assert encrypted_content != sample_evidence_content
        assert sample_evidence_content not in encrypted_content

    def test_sha256_hash_stored_in_manifest(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test SHA-256 hash is calculated and stored in manifest (AC #5)."""
        # GIVEN: An initialized EvidenceStore
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # WHEN: Evidence is stored
        item = store.store_evidence(
            content=sample_evidence_content,
            filename="screenshot.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # THEN: SHA-256 hash matches expected
        expected_hash = hashlib.sha256(sample_evidence_content).hexdigest()
        assert item.sha256_hash == expected_hash

        # AND: Hash is stored in manifest
        manifest_path = temp_evidence_dir / engagement_id / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)

        assert len(manifest["evidence"]) == 1
        assert manifest["evidence"][0]["sha256_hash"] == expected_hash

    def test_manifest_entry_includes_required_fields(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test manifest entry includes all required fields (AC #6)."""
        # GIVEN: An initialized EvidenceStore
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # WHEN: Evidence is stored
        item = store.store_evidence(
            content=sample_evidence_content,
            filename="screenshot.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # THEN: Manifest entry has all required fields
        manifest_path = temp_evidence_dir / engagement_id / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)

        entry = manifest["evidence"][0]
        assert "id" in entry
        assert entry["filename"] == "screenshot.png"
        assert "sha256_hash" in entry
        assert "timestamp" in entry
        assert entry["source_agent"] == "recon-01"
        assert entry["evidence_type"] == "screenshot"
        assert "encrypted_path" in entry
        assert "nonce" in entry
        assert "size_bytes" in entry

    def test_encrypted_file_written_to_data_subdir(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test encrypted file is written to {engagement_id}/data/{uuid}.enc."""
        # GIVEN: An initialized EvidenceStore
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # WHEN: Evidence is stored
        item = store.store_evidence(
            content=sample_evidence_content,
            filename="screenshot.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # THEN: Encrypted path follows convention
        assert str(item.encrypted_path).startswith("data/")
        assert str(item.encrypted_path).endswith(".enc")

        # AND: File exists at that path
        full_path = temp_evidence_dir / engagement_id / item.encrypted_path
        assert full_path.exists()

    def test_evidence_type_enum_values(self) -> None:
        """Test EvidenceType enum has correct values."""
        from cyberred.storage.evidence_store import EvidenceType

        assert EvidenceType.SCREENSHOT.value == "screenshot"
        assert EvidenceType.LOG.value == "log"
        assert EvidenceType.LOOT.value == "loot"
        assert EvidenceType.OTHER.value == "other"

    def test_large_file_storage(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        large_evidence_content: bytes,
    ) -> None:
        """Test large file storage (1MB+)."""
        # GIVEN: An initialized EvidenceStore and large content
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # WHEN: Large evidence is stored
        item = store.store_evidence(
            content=large_evidence_content,
            filename="large_dump.bin",
            source_agent="postex-01",
            evidence_type=EvidenceType.LOOT,
        )

        # THEN: Item is stored correctly
        assert item.size_bytes == len(large_evidence_content)

        # AND: Can be retrieved and verified
        retrieved = store.get_evidence(item.id)
        assert retrieved == large_evidence_content


# ============================================================================
# Task 4: Evidence Retrieval Tests (AC #4, #5)
# ============================================================================


class TestEvidenceRetrieval:
    """Tests for evidence retrieval methods (AC #4, #5)."""

    def test_get_evidence_returns_decrypted_content(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test get_evidence returns decrypted content."""
        # GIVEN: An initialized EvidenceStore with stored evidence
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )
        item = store.store_evidence(
            content=sample_evidence_content,
            filename="screenshot.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # WHEN: Evidence is retrieved
        retrieved = store.get_evidence(item.id)

        # THEN: Decrypted content matches original
        assert retrieved == sample_evidence_content

    def test_get_evidence_with_wrong_key_raises_decryption_error(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test get_evidence with wrong key raises DecryptionError."""
        # GIVEN: Evidence stored with one key
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType
        from cyberred.core.exceptions import DecryptionError

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )
        item = store.store_evidence(
            content=sample_evidence_content,
            filename="screenshot.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # WHEN: A new store is created with different key
        wrong_key = os.urandom(32)
        store2 = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=wrong_key,
            base_path=temp_evidence_dir,
        )

        # THEN: DecryptionError is raised
        with pytest.raises(DecryptionError):
            store2.get_evidence(item.id)

    def test_get_evidence_with_tampered_file_raises_error(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test get_evidence with tampered file raises IntegrityError or DecryptionError.
        
        Note: AES-GCM detects tampering via auth tag, raising DecryptionError.
        This is semantically an integrity failure - the auth tag IS integrity check.
        """
        # GIVEN: Evidence is stored
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType
        from cyberred.core.exceptions import IntegrityError, DecryptionError

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )
        item = store.store_evidence(
            content=sample_evidence_content,
            filename="screenshot.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # WHEN: File is tampered with (flip some bits)
        encrypted_path = temp_evidence_dir / engagement_id / item.encrypted_path
        tampered_content = encrypted_path.read_bytes()
        # Tamper by flipping bits in the middle
        tampered = bytearray(tampered_content)
        if len(tampered) > 50:
            tampered[50] ^= 0xFF
        encrypted_path.write_bytes(bytes(tampered))

        # THEN: Either IntegrityError or DecryptionError is raised
        # AES-GCM auth tag failure = DecryptionError (built-in integrity check)
        with pytest.raises((IntegrityError, DecryptionError)):
            store.get_evidence(item.id)

    def test_verify_integrity_validates_sha256_hash(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test verify_integrity validates SHA-256 hash (AC #7)."""
        # GIVEN: Evidence is stored
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )
        item = store.store_evidence(
            content=sample_evidence_content,
            filename="screenshot.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # WHEN: Integrity is verified
        result = store.verify_integrity(item.id)

        # THEN: Returns True for valid evidence
        assert result is True

    def test_verify_integrity_returns_false_for_corrupted_file(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test verify_integrity returns False for corrupted file."""
        # GIVEN: Evidence is stored
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )
        item = store.store_evidence(
            content=sample_evidence_content,
            filename="screenshot.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # WHEN: Manifest hash is corrupted
        manifest_path = temp_evidence_dir / engagement_id / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        manifest["evidence"][0]["sha256_hash"] = "corrupted_hash"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)

        # Reload the store to pick up corrupted manifest
        store2 = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # THEN: verify_integrity returns False
        result = store2.verify_integrity(item.id)
        assert result is False

    def test_list_evidence_returns_all_items_sorted_by_timestamp(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
    ) -> None:
        """Test list_evidence returns all items sorted by timestamp."""
        # GIVEN: Multiple evidence items stored
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType
        import time

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # Store items with slight delay
        item1 = store.store_evidence(
            content=b"first",
            filename="first.txt",
            source_agent="agent-01",
            evidence_type=EvidenceType.LOG,
        )
        time.sleep(0.01)
        item2 = store.store_evidence(
            content=b"second",
            filename="second.txt",
            source_agent="agent-02",
            evidence_type=EvidenceType.LOG,
        )

        # WHEN: list_evidence is called
        items = store.list_evidence()

        # THEN: Items are sorted by timestamp (newest first)
        assert len(items) == 2
        assert items[0].timestamp >= items[1].timestamp

    def test_list_evidence_filters_by_evidence_type(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
    ) -> None:
        """Test list_evidence filters by evidence_type."""
        # GIVEN: Different types of evidence stored
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        store.store_evidence(
            content=b"screenshot data",
            filename="screen.png",
            source_agent="agent-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )
        store.store_evidence(
            content=b"log data",
            filename="output.log",
            source_agent="agent-02",
            evidence_type=EvidenceType.LOG,
        )

        # WHEN: list_evidence is called with type filter
        screenshots = store.list_evidence(evidence_type=EvidenceType.SCREENSHOT)
        logs = store.list_evidence(evidence_type=EvidenceType.LOG)

        # THEN: Only matching types are returned
        assert len(screenshots) == 1
        assert screenshots[0].evidence_type == EvidenceType.SCREENSHOT
        assert len(logs) == 1
        assert logs[0].evidence_type == EvidenceType.LOG


# ============================================================================
# Task 5: Manifest Tests (AC #5, #6)
# ============================================================================


class TestManifestOperations:
    """Tests for manifest operations (AC #5, #6)."""

    def test_manifest_structure(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
    ) -> None:
        """Test manifest.json has correct structure."""
        # GIVEN: An initialized EvidenceStore
        from cyberred.storage.evidence_store import EvidenceStore

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # WHEN: Manifest is read
        manifest_path = temp_evidence_dir / engagement_id / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)

        # THEN: Structure matches expected format
        assert manifest["version"] == "1.0"
        assert manifest["engagement_id"] == engagement_id
        assert "created_at" in manifest
        assert isinstance(manifest["evidence"], list)

    def test_manifest_atomic_write(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test manifest atomic write (crash safety)."""
        # GIVEN: An initialized EvidenceStore
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # WHEN: Evidence is stored (triggers manifest write)
        item = store.store_evidence(
            content=sample_evidence_content,
            filename="test.png",
            source_agent="agent-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # THEN: No temp files left behind (atomic write completed)
        evidence_dir = temp_evidence_dir / engagement_id
        temp_files = list(evidence_dir.glob("*.tmp"))
        json_temps = list(evidence_dir.glob("tmp*.json"))
        assert len(temp_files) == 0, f"Found temp files: {temp_files}"
        assert len(json_temps) == 0, f"Found temp JSON files: {json_temps}"

        # AND: Manifest is valid JSON
        manifest_path = evidence_dir / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        assert len(manifest["evidence"]) == 1

    def test_manifest_includes_utc_iso8601_timestamps(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test manifest includes UTC ISO8601 timestamps."""
        # GIVEN: An initialized EvidenceStore with evidence
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )
        store.store_evidence(
            content=sample_evidence_content,
            filename="test.png",
            source_agent="agent-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # WHEN: Manifest is read
        manifest_path = temp_evidence_dir / engagement_id / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)

        # THEN: Timestamps are in ISO8601 format with UTC
        created_at = manifest["created_at"]
        assert "T" in created_at  # ISO8601 format
        assert created_at.endswith("Z") or "+00:00" in created_at  # UTC

        evidence_ts = manifest["evidence"][0]["timestamp"]
        assert "T" in evidence_ts
        assert evidence_ts.endswith("Z") or "+00:00" in evidence_ts

    def test_manifest_reloading_preserves_entries(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test manifest re-loading after restart preserves all entries."""
        # GIVEN: An initialized EvidenceStore with multiple evidence items
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )
        item1 = store.store_evidence(
            content=sample_evidence_content,
            filename="test1.png",
            source_agent="agent-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )
        item2 = store.store_evidence(
            content=b"second evidence",
            filename="test2.log",
            source_agent="agent-02",
            evidence_type=EvidenceType.LOG,
        )

        # WHEN: A new store is created (simulating restart)
        store2 = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # THEN: All entries are preserved
        items = store2.list_evidence()
        assert len(items) == 2
        item_ids = {i.id for i in items}
        assert item1.id in item_ids
        assert item2.id in item_ids

    def test_get_manifest_hash(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test get_manifest_hash returns SHA-256 of entire manifest."""
        # GIVEN: An initialized EvidenceStore with evidence
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )
        store.store_evidence(
            content=sample_evidence_content,
            filename="test.png",
            source_agent="agent-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # WHEN: Manifest hash is retrieved
        manifest_hash = store.get_manifest_hash()

        # THEN: Hash is a valid SHA-256 hex string
        assert len(manifest_hash) == 64  # SHA-256 hex = 64 chars
        assert all(c in "0123456789abcdef" for c in manifest_hash)

        # AND: Hash matches computed hash of manifest file
        manifest_path = temp_evidence_dir / engagement_id / "manifest.json"
        with open(manifest_path, "rb") as f:
            expected_hash = hashlib.sha256(f.read()).hexdigest()
        assert manifest_hash == expected_hash


# ============================================================================
# EvidenceItem Dataclass Tests
# ============================================================================


class TestEvidenceItem:
    """Tests for EvidenceItem dataclass."""

    def test_evidence_item_to_dict(self) -> None:
        """Test EvidenceItem.to_dict() serialization."""
        from cyberred.storage.evidence_store import EvidenceItem, EvidenceType
        from pathlib import Path

        item = EvidenceItem(
            id="test-uuid-123",
            filename="screenshot.png",
            sha256_hash="abc123def456",
            encrypted_path=Path("data/test-uuid-123.enc"),
            nonce=b"\x00" * 12,
            size_bytes=1024,
            timestamp=datetime(2026, 2, 12, 12, 0, 0, tzinfo=timezone.utc),
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # WHEN: to_dict is called
        result = item.to_dict()

        # THEN: Dictionary has correct values
        assert result["id"] == "test-uuid-123"
        assert result["filename"] == "screenshot.png"
        assert result["sha256_hash"] == "abc123def456"
        assert result["encrypted_path"] == "data/test-uuid-123.enc"
        assert result["nonce"] == "0" * 24  # hex encoded
        assert result["size_bytes"] == 1024
        assert result["source_agent"] == "recon-01"
        assert result["evidence_type"] == "screenshot"
        assert "2026-02-12" in result["timestamp"]

    def test_evidence_item_from_dict(self) -> None:
        """Test EvidenceItem.from_dict() deserialization."""
        from cyberred.storage.evidence_store import EvidenceItem, EvidenceType

        data = {
            "id": "test-uuid-123",
            "filename": "screenshot.png",
            "sha256_hash": "abc123def456",
            "encrypted_path": "data/test-uuid-123.enc",
            "nonce": "0" * 24,
            "size_bytes": 1024,
            "timestamp": "2026-02-12T12:00:00Z",
            "source_agent": "recon-01",
            "evidence_type": "screenshot",
        }

        # WHEN: from_dict is called
        item = EvidenceItem.from_dict(data)

        # THEN: Item has correct values
        assert item.id == "test-uuid-123"
        assert item.filename == "screenshot.png"
        assert item.sha256_hash == "abc123def456"
        assert str(item.encrypted_path) == "data/test-uuid-123.enc"
        assert item.nonce == b"\x00" * 12
        assert item.size_bytes == 1024
        assert item.source_agent == "recon-01"
        assert item.evidence_type == EvidenceType.SCREENSHOT
        assert item.timestamp.year == 2026

    def test_evidence_item_roundtrip(self) -> None:
        """Test to_dict/from_dict roundtrip preserves data."""
        from cyberred.storage.evidence_store import EvidenceItem, EvidenceType
        from pathlib import Path

        original = EvidenceItem(
            id="test-uuid-roundtrip",
            filename="loot.bin",
            sha256_hash="deadbeef" * 8,
            encrypted_path=Path("data/test-uuid-roundtrip.enc"),
            nonce=os.urandom(12),
            size_bytes=2048,
            timestamp=datetime.now(timezone.utc),
            source_agent="postex-02",
            evidence_type=EvidenceType.LOOT,
        )

        # WHEN: Roundtrip through dict
        data = original.to_dict()
        restored = EvidenceItem.from_dict(data)

        # THEN: Data is preserved
        assert restored.id == original.id
        assert restored.filename == original.filename
        assert restored.sha256_hash == original.sha256_hash
        assert str(restored.encrypted_path) == str(original.encrypted_path)
        assert restored.nonce == original.nonce
        assert restored.size_bytes == original.size_bytes
        assert restored.source_agent == original.source_agent
        assert restored.evidence_type == original.evidence_type


# ============================================================================
# Additional Coverage Tests
# ============================================================================


class TestEvidenceStoreCoverage:
    """Additional tests for full coverage."""

    def test_from_dict_with_datetime_object(self) -> None:
        """Test from_dict handles datetime object directly."""
        from cyberred.storage.evidence_store import EvidenceItem, EvidenceType

        ts = datetime(2026, 2, 12, 12, 0, 0, tzinfo=timezone.utc)
        data = {
            "id": "test-uuid",
            "filename": "test.png",
            "sha256_hash": "abc123",
            "encrypted_path": "data/test.enc",
            "nonce": b"\x00" * 12,  # bytes directly
            "size_bytes": 100,
            "timestamp": ts,  # datetime object directly
            "source_agent": "agent-01",
            "evidence_type": EvidenceType.SCREENSHOT,  # enum directly
        }

        item = EvidenceItem.from_dict(data)
        assert item.timestamp == ts
        assert item.nonce == b"\x00" * 12
        assert item.evidence_type == EvidenceType.SCREENSHOT

    def test_from_dict_with_timezone_offset(self) -> None:
        """Test from_dict handles timestamp with +00:00 offset."""
        from cyberred.storage.evidence_store import EvidenceItem, EvidenceType

        data = {
            "id": "test-uuid",
            "filename": "test.png",
            "sha256_hash": "abc123",
            "encrypted_path": "data/test.enc",
            "nonce": "0" * 24,
            "size_bytes": 100,
            "timestamp": "2026-02-12T12:00:00+00:00",  # with offset
            "source_agent": "agent-01",
            "evidence_type": "screenshot",
        }

        item = EvidenceItem.from_dict(data)
        assert item.timestamp.tzinfo is not None

    def test_from_dict_with_naive_timestamp(self) -> None:
        """Test from_dict handles naive timestamp (no tz)."""
        from cyberred.storage.evidence_store import EvidenceItem, EvidenceType

        data = {
            "id": "test-uuid",
            "filename": "test.png",
            "sha256_hash": "abc123",
            "encrypted_path": "data/test.enc",
            "nonce": "0" * 24,
            "size_bytes": 100,
            "timestamp": "2026-02-12T12:00:00",  # naive, no tz
            "source_agent": "agent-01",
            "evidence_type": "screenshot",
        }

        item = EvidenceItem.from_dict(data)
        assert item.timestamp.tzinfo == timezone.utc

    def test_get_evidence_not_found(
        self, engagement_id: str, encryption_key: bytes, temp_evidence_dir: Path
    ) -> None:
        """Test get_evidence raises KeyError for nonexistent ID."""
        from cyberred.storage.evidence_store import EvidenceStore

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        with pytest.raises(KeyError, match="Evidence not found"):
            store.get_evidence("nonexistent-id")

    def test_get_evidence_file_missing(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test get_evidence raises KeyError when encrypted file is deleted."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )
        item = store.store_evidence(
            content=sample_evidence_content,
            filename="test.png",
            source_agent="agent-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # Delete the encrypted file
        encrypted_path = temp_evidence_dir / engagement_id / item.encrypted_path
        encrypted_path.unlink()

        with pytest.raises(KeyError, match="Encrypted file not found"):
            store.get_evidence(item.id)

    def test_verify_integrity_not_found(
        self, engagement_id: str, encryption_key: bytes, temp_evidence_dir: Path
    ) -> None:
        """Test verify_integrity raises KeyError for nonexistent ID."""
        from cyberred.storage.evidence_store import EvidenceStore

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        with pytest.raises(KeyError, match="Evidence not found"):
            store.verify_integrity("nonexistent-id")

    def test_verify_integrity_file_missing(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test verify_integrity raises KeyError when encrypted file is deleted."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )
        item = store.store_evidence(
            content=sample_evidence_content,
            filename="test.png",
            source_agent="agent-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # Delete the encrypted file
        encrypted_path = temp_evidence_dir / engagement_id / item.encrypted_path
        encrypted_path.unlink()

        with pytest.raises(KeyError, match="Encrypted file not found"):
            store.verify_integrity(item.id)

    def test_verify_integrity_decryption_error(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test verify_integrity returns False on DecryptionError."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )
        item = store.store_evidence(
            content=sample_evidence_content,
            filename="test.png",
            source_agent="agent-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # Tamper with encrypted file to cause DecryptionError
        encrypted_path = temp_evidence_dir / engagement_id / item.encrypted_path
        tampered = bytearray(encrypted_path.read_bytes())
        tampered[50] ^= 0xFF
        encrypted_path.write_bytes(bytes(tampered))

        # Should return False, not raise
        assert store.verify_integrity(item.id) is False

    def test_get_manifest_hash_no_manifest(
        self, engagement_id: str, encryption_key: bytes, temp_evidence_dir: Path
    ) -> None:
        """Test get_manifest_hash returns empty string when no manifest."""
        from cyberred.storage.evidence_store import EvidenceStore

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # Delete the manifest
        manifest_path = temp_evidence_dir / engagement_id / "manifest.json"
        manifest_path.unlink()

        # Should return empty string
        assert store.get_manifest_hash() == ""

    def test_load_manifest_json_decode_error(
        self, engagement_id: str, encryption_key: bytes, temp_evidence_dir: Path
    ) -> None:
        """Test loading invalid JSON manifest raises error."""
        from cyberred.storage.evidence_store import EvidenceStore

        # Create directory with invalid JSON manifest
        evidence_dir = temp_evidence_dir / engagement_id
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "data").mkdir()
        manifest_path = evidence_dir / "manifest.json"
        manifest_path.write_text("invalid json {{{")

        with pytest.raises(json.JSONDecodeError):
            EvidenceStore(
                engagement_id=engagement_id,
                encryption_key=encryption_key,
                base_path=temp_evidence_dir,
            )

    def test_load_manifest_other_error(
        self, engagement_id: str, encryption_key: bytes, temp_evidence_dir: Path
    ) -> None:
        """Test loading manifest with missing required fields raises error."""
        from cyberred.storage.evidence_store import EvidenceStore

        # Create directory with manifest missing required fields
        evidence_dir = temp_evidence_dir / engagement_id
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "data").mkdir()
        manifest_path = evidence_dir / "manifest.json"
        # Valid JSON but evidence items missing required fields
        manifest_path.write_text('{"version": "1.0", "evidence": [{"id": "test"}]}')

        with pytest.raises(KeyError):
            EvidenceStore(
                engagement_id=engagement_id,
                encryption_key=encryption_key,
                base_path=temp_evidence_dir,
            )

    def test_base_path_property(
        self, engagement_id: str, encryption_key: bytes, temp_evidence_dir: Path
    ) -> None:
        """Test base_path property returns correct path."""
        from cyberred.storage.evidence_store import EvidenceStore

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        assert store.base_path == temp_evidence_dir

    def test_get_evidence_hash_mismatch_raises_integrity_error(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test get_evidence raises IntegrityError when hash doesn't match."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType
        from cyberred.core.exceptions import IntegrityError

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )
        item = store.store_evidence(
            content=sample_evidence_content,
            filename="test.png",
            source_agent="agent-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # Modify the hash in the manifest to cause mismatch
        manifest_path = temp_evidence_dir / engagement_id / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        manifest["evidence"][0]["sha256_hash"] = "wrong_hash_value"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)

        # Reload the store
        store2 = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        with pytest.raises(IntegrityError):
            store2.get_evidence(item.id)

    def test_save_manifest_exception_cleanup(
        self, engagement_id: str, encryption_key: bytes, temp_evidence_dir: Path
    ) -> None:
        """Test _save_manifest cleans up temp file on error."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType
        from unittest.mock import patch, MagicMock

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # Mock shutil.move to raise an exception
        with patch("shutil.move", side_effect=OSError("Simulated error")):
            with pytest.raises(OSError, match="Simulated error"):
                store.store_evidence(
                    content=b"test content",
                    filename="test.bin",
                    source_agent="agent-01",
                    evidence_type=EvidenceType.LOG,
                )

        # Verify no temp files left behind
        evidence_dir = temp_evidence_dir / engagement_id
        temp_files = list(evidence_dir.glob("tmp*"))
        assert len(temp_files) == 0


# ============================================================================
# Additional Tests for Code Review Fixes
# ============================================================================


class TestCodeReviewFixes:
    """Tests for code review fixes."""

    def test_empty_engagement_id_raises_valueerror(
        self, encryption_key: bytes, temp_evidence_dir: Path
    ) -> None:
        """Test empty engagement_id raises ValueError."""
        from cyberred.storage.evidence_store import EvidenceStore

        with pytest.raises(ValueError, match="Engagement ID cannot be empty"):
            EvidenceStore(
                engagement_id="",
                encryption_key=encryption_key,
                base_path=temp_evidence_dir,
            )

    def test_whitespace_engagement_id_raises_valueerror(
        self, encryption_key: bytes, temp_evidence_dir: Path
    ) -> None:
        """Test whitespace-only engagement_id raises ValueError."""
        from cyberred.storage.evidence_store import EvidenceStore

        with pytest.raises(ValueError, match="Engagement ID cannot be empty"):
            EvidenceStore(
                engagement_id="   ",
                encryption_key=encryption_key,
                base_path=temp_evidence_dir,
            )

    def test_empty_filename_raises_valueerror(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test empty filename raises ValueError."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        with pytest.raises(ValueError, match="Filename cannot be empty"):
            store.store_evidence(
                content=sample_evidence_content,
                filename="",
                source_agent="agent-01",
                evidence_type=EvidenceType.SCREENSHOT,
            )

    def test_whitespace_filename_raises_valueerror(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test whitespace-only filename raises ValueError."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        with pytest.raises(ValueError, match="Filename cannot be empty"):
            store.store_evidence(
                content=sample_evidence_content,
                filename="   ",
                source_agent="agent-01",
                evidence_type=EvidenceType.SCREENSHOT,
            )

    def test_path_traversal_filename_raises_valueerror(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test path traversal in filename raises ValueError."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # Test various path traversal attempts
        bad_filenames = [
            "../etc/passwd",
            "..\\windows\\system32",
            "foo/bar.txt",
            "foo\\bar.txt",
            "..secret.txt",
        ]

        for bad_filename in bad_filenames:
            with pytest.raises(ValueError, match="cannot contain path separators"):
                store.store_evidence(
                    content=sample_evidence_content,
                    filename=bad_filename,
                    source_agent="agent-01",
                    evidence_type=EvidenceType.SCREENSHOT,
                )

    def test_manifest_created_at_preserved_across_saves(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
        sample_evidence_content: bytes,
    ) -> None:
        """Test manifest created_at is preserved when adding new evidence."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType
        import time

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # Read initial created_at
        manifest_path = temp_evidence_dir / engagement_id / "manifest.json"
        with open(manifest_path) as f:
            initial_manifest = json.load(f)
        initial_created_at = initial_manifest["created_at"]

        # Wait and add evidence
        time.sleep(0.1)
        store.store_evidence(
            content=sample_evidence_content,
            filename="test.png",
            source_agent="agent-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # Check created_at is preserved
        with open(manifest_path) as f:
            updated_manifest = json.load(f)
        assert updated_manifest["created_at"] == initial_created_at

    def test_empty_content_allowed(
        self,
        engagement_id: str,
        encryption_key: bytes,
        temp_evidence_dir: Path,
    ) -> None:
        """Test empty content is allowed (documented behavior)."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=engagement_id,
            encryption_key=encryption_key,
            base_path=temp_evidence_dir,
        )

        # Empty content should be allowed
        item = store.store_evidence(
            content=b"",
            filename="empty.txt",
            source_agent="agent-01",
            evidence_type=EvidenceType.OTHER,
        )

        assert item.size_bytes == 0
        assert store.get_evidence(item.id) == b""
