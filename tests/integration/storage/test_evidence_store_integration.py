"""Integration tests for Evidence File Storage (Story 13.1).

STRICT integration tests that test ACTUAL PRODUCTION CODE with NO MOCKS.
Tests real file I/O, encryption, and manifest operations.

Acceptance Criteria tested:
- AC #1: Given engagement is running
- AC #2: When evidence file is captured (screenshot, log, loot)
- AC #3: Then file is stored in ~/.cyber-red/evidence/{engagement_id}/
- AC #4: And file is encrypted at rest (AES-256)
- AC #5: And SHA-256 hash is recorded in manifest.json
- AC #6: And manifest includes: filename, hash, timestamp, source_agent
- AC #7: And unit tests verify hash integrity
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest


# ============================================================================
# Integration Test Fixtures (No Mocks)
# ============================================================================


@pytest.fixture
def real_encryption_key() -> bytes:
    """Real 32-byte AES-256 encryption key."""
    return os.urandom(32)


@pytest.fixture
def real_engagement_id() -> str:
    """Real engagement ID for integration tests."""
    return f"integration-eng-{uuid.uuid4()}"


@pytest.fixture
def real_evidence_dir(tmp_path: Path) -> Path:
    """Real temporary directory for evidence storage."""
    evidence_dir = tmp_path / "cyber-red-integration" / "evidence"
    evidence_dir.mkdir(parents=True)
    return evidence_dir


@pytest.fixture
def screenshot_content() -> bytes:
    """Real PNG-like screenshot content."""
    # PNG magic bytes + random data to simulate real screenshot
    png_header = b"\x89PNG\r\n\x1a\n"
    return png_header + os.urandom(4096)


@pytest.fixture
def log_content() -> bytes:
    """Real log file content."""
    lines = [
        f"[2026-02-12 {i:02d}:00:00] INFO: Test log entry {i}\n"
        for i in range(100)
    ]
    return "".join(lines).encode("utf-8")


@pytest.fixture
def loot_content() -> bytes:
    """Real loot file content (credentials simulation)."""
    return b"""# /etc/shadow dump
root:$6$randomsalt$hashedpassword:19000:0:99999:7:::
admin:$6$anothersalt$anotherhash:19000:0:99999:7:::
user1:$6$salt3$hash3:19000:0:99999:7:::
"""


# ============================================================================
# Task 6: Full Integration Tests (All ACs)
# ============================================================================


class TestEvidenceStoreIntegration:
    """Full integration tests for EvidenceStore - NO MOCKS."""

    def test_full_cycle_store_verify_retrieve(
        self,
        real_engagement_id: str,
        real_encryption_key: bytes,
        real_evidence_dir: Path,
        screenshot_content: bytes,
    ) -> None:
        """Test full cycle: store → verify → retrieve → verify integrity."""
        # GIVEN: An initialized EvidenceStore with real file system
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=real_engagement_id,
            encryption_key=real_encryption_key,
            base_path=real_evidence_dir,
        )

        # WHEN: Evidence is stored
        item = store.store_evidence(
            content=screenshot_content,
            filename="target_192.168.1.1_screenshot.png",
            source_agent="recon-agent-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # THEN: Item is created with correct metadata
        assert item.id is not None
        assert item.filename == "target_192.168.1.1_screenshot.png"
        assert item.source_agent == "recon-agent-01"
        assert item.evidence_type == EvidenceType.SCREENSHOT
        assert item.size_bytes == len(screenshot_content)

        # AND: SHA-256 hash is correct
        expected_hash = hashlib.sha256(screenshot_content).hexdigest()
        assert item.sha256_hash == expected_hash

        # AND: Integrity verification passes
        assert store.verify_integrity(item.id) is True

        # AND: Retrieved content matches original
        retrieved = store.get_evidence(item.id)
        assert retrieved == screenshot_content

        # AND: Hash of retrieved content matches
        assert hashlib.sha256(retrieved).hexdigest() == expected_hash

    def test_multiple_evidence_types(
        self,
        real_engagement_id: str,
        real_encryption_key: bytes,
        real_evidence_dir: Path,
        screenshot_content: bytes,
        log_content: bytes,
        loot_content: bytes,
    ) -> None:
        """Test storing multiple evidence types (screenshot, log, loot)."""
        # GIVEN: An initialized EvidenceStore
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=real_engagement_id,
            encryption_key=real_encryption_key,
            base_path=real_evidence_dir,
        )

        # WHEN: Different types of evidence are stored
        screenshot = store.store_evidence(
            content=screenshot_content,
            filename="screen_capture.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )
        log = store.store_evidence(
            content=log_content,
            filename="nmap_output.log",
            source_agent="recon-01",
            evidence_type=EvidenceType.LOG,
        )
        loot = store.store_evidence(
            content=loot_content,
            filename="shadow_dump.txt",
            source_agent="postex-01",
            evidence_type=EvidenceType.LOOT,
        )
        other = store.store_evidence(
            content=b"misc data",
            filename="misc.bin",
            source_agent="exploit-01",
            evidence_type=EvidenceType.OTHER,
        )

        # THEN: All items are stored correctly
        all_items = store.list_evidence()
        assert len(all_items) == 4

        # AND: Can filter by type
        screenshots = store.list_evidence(evidence_type=EvidenceType.SCREENSHOT)
        assert len(screenshots) == 1
        assert screenshots[0].id == screenshot.id

        logs = store.list_evidence(evidence_type=EvidenceType.LOG)
        assert len(logs) == 1
        assert logs[0].id == log.id

        loots = store.list_evidence(evidence_type=EvidenceType.LOOT)
        assert len(loots) == 1
        assert loots[0].id == loot.id

        # AND: All can be retrieved and verified
        for item, original in [
            (screenshot, screenshot_content),
            (log, log_content),
            (loot, loot_content),
            (other, b"misc data"),
        ]:
            assert store.verify_integrity(item.id) is True
            assert store.get_evidence(item.id) == original

    def test_concurrent_storage_operations(
        self,
        real_engagement_id: str,
        real_encryption_key: bytes,
        real_evidence_dir: Path,
    ) -> None:
        """Test concurrent storage operations are thread-safe."""
        # GIVEN: An initialized EvidenceStore
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=real_engagement_id,
            encryption_key=real_encryption_key,
            base_path=real_evidence_dir,
        )

        results: list[str] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def store_evidence(index: int) -> None:
            """Store evidence in a thread."""
            try:
                content = f"Evidence content {index}".encode() + os.urandom(512)
                item = store.store_evidence(
                    content=content,
                    filename=f"evidence_{index}.bin",
                    source_agent=f"agent-{index % 5}",
                    evidence_type=EvidenceType.LOG,
                )
                with lock:
                    results.append(item.id)
            except Exception as e:
                with lock:
                    errors.append(e)

        # WHEN: Multiple threads store evidence concurrently
        num_threads = 10
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(store_evidence, i) for i in range(num_threads)]
            for future in futures:
                future.result()  # Wait for completion

        # THEN: No errors occurred
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # AND: All items were stored
        assert len(results) == num_threads

        # AND: All items are in the store
        all_items = store.list_evidence()
        assert len(all_items) == num_threads

        # AND: Manifest is valid
        manifest_path = real_evidence_dir / real_engagement_id / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        assert len(manifest["evidence"]) == num_threads

    def test_persistence_across_restarts(
        self,
        real_engagement_id: str,
        real_encryption_key: bytes,
        real_evidence_dir: Path,
        screenshot_content: bytes,
        log_content: bytes,
    ) -> None:
        """Test evidence persists across EvidenceStore restarts."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        # GIVEN: Evidence stored in first session
        store1 = EvidenceStore(
            engagement_id=real_engagement_id,
            encryption_key=real_encryption_key,
            base_path=real_evidence_dir,
        )
        item1 = store1.store_evidence(
            content=screenshot_content,
            filename="session1_screenshot.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )
        item2 = store1.store_evidence(
            content=log_content,
            filename="session1_log.txt",
            source_agent="recon-01",
            evidence_type=EvidenceType.LOG,
        )
        del store1  # Simulate process exit

        # WHEN: New store is created (simulating restart)
        store2 = EvidenceStore(
            engagement_id=real_engagement_id,
            encryption_key=real_encryption_key,
            base_path=real_evidence_dir,
        )

        # THEN: All evidence is accessible
        items = store2.list_evidence()
        assert len(items) == 2

        # AND: Content can be retrieved
        assert store2.get_evidence(item1.id) == screenshot_content
        assert store2.get_evidence(item2.id) == log_content

        # AND: Integrity checks pass
        assert store2.verify_integrity(item1.id) is True
        assert store2.verify_integrity(item2.id) is True

        # WHEN: More evidence is added in second session
        item3 = store2.store_evidence(
            content=b"session 2 data",
            filename="session2_data.bin",
            source_agent="recon-02",
            evidence_type=EvidenceType.OTHER,
        )
        del store2

        # AND: Third session reads all
        store3 = EvidenceStore(
            engagement_id=real_engagement_id,
            encryption_key=real_encryption_key,
            base_path=real_evidence_dir,
        )
        items = store3.list_evidence()
        assert len(items) == 3

    def test_real_file_encryption_verification(
        self,
        real_engagement_id: str,
        real_encryption_key: bytes,
        real_evidence_dir: Path,
    ) -> None:
        """Test files on disk are actually encrypted (not plaintext)."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        # GIVEN: Known plaintext content
        secret_data = b"SUPER_SECRET_PASSWORD=admin123\nAPI_KEY=sk-live-abcdef123456"

        store = EvidenceStore(
            engagement_id=real_engagement_id,
            encryption_key=real_encryption_key,
            base_path=real_evidence_dir,
        )

        # WHEN: Secret data is stored
        item = store.store_evidence(
            content=secret_data,
            filename="secrets.env",
            source_agent="postex-01",
            evidence_type=EvidenceType.LOOT,
        )

        # THEN: Encrypted file on disk does NOT contain plaintext
        encrypted_path = real_evidence_dir / real_engagement_id / item.encrypted_path
        encrypted_bytes = encrypted_path.read_bytes()

        # Plaintext should NOT appear in encrypted file
        assert b"SUPER_SECRET" not in encrypted_bytes
        assert b"admin123" not in encrypted_bytes
        assert b"sk-live" not in encrypted_bytes
        assert b"API_KEY" not in encrypted_bytes

        # AND: Encrypted file should be larger than plaintext (due to auth tag)
        assert len(encrypted_bytes) > len(secret_data)

        # AND: Decrypted content matches original
        decrypted = store.get_evidence(item.id)
        assert decrypted == secret_data

    def test_manifest_integrity_after_multiple_operations(
        self,
        real_engagement_id: str,
        real_encryption_key: bytes,
        real_evidence_dir: Path,
    ) -> None:
        """Test manifest integrity after multiple store operations."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=real_engagement_id,
            encryption_key=real_encryption_key,
            base_path=real_evidence_dir,
        )

        # Store 20 items
        stored_items = []
        for i in range(20):
            content = f"Evidence item {i}: ".encode() + os.urandom(256)
            item = store.store_evidence(
                content=content,
                filename=f"evidence_{i:03d}.bin",
                source_agent=f"agent-{i % 3}",
                evidence_type=EvidenceType.LOG,
            )
            stored_items.append((item, content))

        # THEN: Manifest is valid JSON
        manifest_path = real_evidence_dir / real_engagement_id / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest["version"] == "1.0"
        assert manifest["engagement_id"] == real_engagement_id
        assert len(manifest["evidence"]) == 20

        # AND: All items have required fields
        for entry in manifest["evidence"]:
            assert "id" in entry
            assert "filename" in entry
            assert "sha256_hash" in entry
            assert len(entry["sha256_hash"]) == 64  # SHA-256 hex
            assert "timestamp" in entry
            assert "source_agent" in entry
            assert "evidence_type" in entry
            assert "encrypted_path" in entry
            assert "nonce" in entry
            assert "size_bytes" in entry

        # AND: All items can be retrieved and verified
        for item, original_content in stored_items:
            assert store.verify_integrity(item.id) is True
            assert store.get_evidence(item.id) == original_content

    def test_evidence_directory_structure(
        self,
        real_engagement_id: str,
        real_encryption_key: bytes,
        real_evidence_dir: Path,
        screenshot_content: bytes,
    ) -> None:
        """Test correct directory structure is created."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=real_engagement_id,
            encryption_key=real_encryption_key,
            base_path=real_evidence_dir,
        )

        # WHEN: Evidence is stored
        item = store.store_evidence(
            content=screenshot_content,
            filename="test.png",
            source_agent="recon-01",
            evidence_type=EvidenceType.SCREENSHOT,
        )

        # THEN: Directory structure is correct
        engagement_dir = real_evidence_dir / real_engagement_id
        assert engagement_dir.exists()
        assert engagement_dir.is_dir()

        data_dir = engagement_dir / "data"
        assert data_dir.exists()
        assert data_dir.is_dir()

        manifest_path = engagement_dir / "manifest.json"
        assert manifest_path.exists()
        assert manifest_path.is_file()

        # AND: Encrypted file is in data directory
        encrypted_path = engagement_dir / item.encrypted_path
        assert encrypted_path.exists()
        assert encrypted_path.parent == data_dir

    def test_large_file_handling(
        self,
        real_engagement_id: str,
        real_encryption_key: bytes,
        real_evidence_dir: Path,
    ) -> None:
        """Test handling of large files (5MB)."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        # GIVEN: A large file (5MB)
        large_content = os.urandom(5 * 1024 * 1024)

        store = EvidenceStore(
            engagement_id=real_engagement_id,
            encryption_key=real_encryption_key,
            base_path=real_evidence_dir,
        )

        # WHEN: Large file is stored
        start_time = time.time()
        item = store.store_evidence(
            content=large_content,
            filename="large_memory_dump.bin",
            source_agent="postex-01",
            evidence_type=EvidenceType.LOOT,
        )
        store_time = time.time() - start_time

        # THEN: File is stored correctly
        assert item.size_bytes == len(large_content)

        # AND: Can be retrieved
        start_time = time.time()
        retrieved = store.get_evidence(item.id)
        retrieve_time = time.time() - start_time

        assert retrieved == large_content

        # AND: Operations complete in reasonable time (< 10s each)
        assert store_time < 10, f"Store took too long: {store_time}s"
        assert retrieve_time < 10, f"Retrieve took too long: {retrieve_time}s"

    def test_timestamp_ordering(
        self,
        real_engagement_id: str,
        real_encryption_key: bytes,
        real_evidence_dir: Path,
    ) -> None:
        """Test evidence items are ordered by timestamp correctly."""
        from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

        store = EvidenceStore(
            engagement_id=real_engagement_id,
            encryption_key=real_encryption_key,
            base_path=real_evidence_dir,
        )

        # Store items with small delays
        items = []
        for i in range(5):
            item = store.store_evidence(
                content=f"item {i}".encode(),
                filename=f"item_{i}.txt",
                source_agent="agent-01",
                evidence_type=EvidenceType.LOG,
            )
            items.append(item)
            time.sleep(0.02)  # 20ms delay

        # WHEN: Items are listed
        listed = store.list_evidence()

        # THEN: Items are sorted by timestamp (newest first)
        assert len(listed) == 5
        for i in range(len(listed) - 1):
            assert listed[i].timestamp >= listed[i + 1].timestamp
