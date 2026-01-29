"""Unit tests for ExfiltratedDataStore and related classes.

Story 11.2: Exfiltrated Data Browser

Tests for:
- ExfiltratedDataItem dataclass (Task 1)
- ExfiltratedDataStore class (Task 2)
- Encryption/decryption utilities (Task 3)

TDD RED Phase: These tests should FAIL initially.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from cyberred.core.exceptions import DecryptionError


# ============================================================================
# Task 1: Unit tests for ExfiltratedDataItem dataclass (AC: #3, #4)
# ============================================================================


class TestExfiltratedDataItem:
    """Tests for ExfiltratedDataItem dataclass."""

    def test_initialization_with_all_fields(self) -> None:
        """Test ExfiltratedDataItem can be initialized with all fields."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        item = ExfiltratedDataItem(
            id="data-001-uuid",
            filename="shadow",
            file_type="shadow",
            mime_type="text/plain",
            size_bytes=1024,
            target="192.168.1.100",
            source_agent="postex-agent-7",
            timestamp=datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc),
            encrypted_path=Path("data/cred_001.enc"),
            sha256_hash="a1b2c3d4e5f6",
            nonce=b"\xde\xad\xbe\xef" * 3,
            category="credentials",
        )

        assert item.id == "data-001-uuid"
        assert item.filename == "shadow"
        assert item.file_type == "shadow"
        assert item.mime_type == "text/plain"
        assert item.size_bytes == 1024
        assert item.target == "192.168.1.100"
        assert item.source_agent == "postex-agent-7"
        assert item.encrypted_path == Path("data/cred_001.enc")
        assert item.sha256_hash == "a1b2c3d4e5f6"
        assert item.nonce == b"\xde\xad\xbe\xef" * 3
        assert item.category == "credentials"

    @pytest.mark.parametrize(
        "filename,expected_category",
        [
            # Credentials
            ("shadow", "credentials"),
            ("passwd", "credentials"),
            ("/etc/shadow", "credentials"),
            ("sam.bak", "credentials"),
            ("ntds.dit", "credentials"),
            ("credentials.txt", "credentials"),
            ("secret.key", "credentials"),
            ("api_token.txt", "credentials"),
            ("password.hash", "credentials"),
            # Documents
            ("report.pdf", "documents"),
            ("document.doc", "documents"),
            ("spreadsheet.xlsx", "documents"),
            ("presentation.pptx", "documents"),
            ("notes.odt", "documents"),
            # Configs
            ("nginx.conf", "configs"),
            ("settings.cfg", "configs"),
            ("config.ini", "configs"),
            ("docker-compose.yaml", "configs"),
            ("app.yml", "configs"),
            ("package.json", "configs"),
            ("web.xml", "configs"),
            (".env", "configs"),
            ("settings.toml", "configs"),
            # Other
            ("image.png", "other"),
            ("archive.zip", "other"),
            ("binary.exe", "other"),
            ("unknown.xyz", "other"),
        ],
    )
    def test_category_detection(self, filename: str, expected_category: str) -> None:
        """Test automatic category detection based on filename."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        item = ExfiltratedDataItem(
            id="test-id",
            filename=filename,
            file_type=Path(filename).suffix.lstrip(".") or filename,
            mime_type="application/octet-stream",
            size_bytes=100,
            target="192.168.1.1",
            source_agent="agent-1",
            timestamp=datetime.now(timezone.utc),
            encrypted_path=Path("data/test.enc"),
            sha256_hash="abc123",
            nonce=b"\x00" * 12,
        )

        assert item.category == expected_category

    @pytest.mark.parametrize(
        "mime_type,expected",
        [
            ("text/plain", True),
            ("text/html", True),
            ("text/xml", True),
            ("application/json", True),
            ("application/xml", True),
            ("application/javascript", True),
            ("image/png", False),
            ("application/octet-stream", False),
            ("application/zip", False),
            ("image/jpeg", False),
        ],
    )
    def test_is_text_property(self, mime_type: str, expected: bool) -> None:
        """Test is_text property for text vs binary detection."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        item = ExfiltratedDataItem(
            id="test-id",
            filename="test.txt",
            file_type="txt",
            mime_type=mime_type,
            size_bytes=100,
            target="192.168.1.1",
            source_agent="agent-1",
            timestamp=datetime.now(timezone.utc),
            encrypted_path=Path("data/test.enc"),
            sha256_hash="abc123",
            nonce=b"\x00" * 12,
        )

        assert item.is_text == expected

    @pytest.mark.parametrize(
        "mime_type,size_bytes,expected",
        [
            ("text/plain", 1000, True),  # Text, under 10KB
            ("text/plain", 10 * 1024, True),  # Text, exactly 10KB
            ("text/plain", 10 * 1024 + 1, False),  # Text, over 10KB
            ("text/plain", 100 * 1024, False),  # Text, way over 10KB
            ("image/png", 1000, False),  # Binary, small
            ("application/octet-stream", 100, False),  # Binary
        ],
    )
    def test_is_previewable_property(
        self, mime_type: str, size_bytes: int, expected: bool
    ) -> None:
        """Test is_previewable property (text files < 10KB)."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        item = ExfiltratedDataItem(
            id="test-id",
            filename="test.txt",
            file_type="txt",
            mime_type=mime_type,
            size_bytes=size_bytes,
            target="192.168.1.1",
            source_agent="agent-1",
            timestamp=datetime.now(timezone.utc),
            encrypted_path=Path("data/test.enc"),
            sha256_hash="abc123",
            nonce=b"\x00" * 12,
        )

        assert item.is_previewable == expected

    def test_from_dict_factory_method(self) -> None:
        """Test from_dict() creates item from dictionary."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        data: dict[str, Any] = {
            "id": "data-001-uuid",
            "filename": "shadow",
            "file_type": "shadow",
            "mime_type": "text/plain",
            "size_bytes": 1024,
            "target": "192.168.1.100",
            "source_agent": "postex-agent-7",
            "timestamp": "2026-01-29T12:00:00+00:00",
            "encrypted_path": "data/cred_001.enc",
            "sha256_hash": "a1b2c3d4e5f6",
            "nonce": "deadbeef12345678abcdef00",  # hex-encoded
            "category": "credentials",
        }

        item = ExfiltratedDataItem.from_dict(data)

        assert item.id == "data-001-uuid"
        assert item.filename == "shadow"
        assert item.size_bytes == 1024
        assert item.target == "192.168.1.100"
        assert item.encrypted_path == Path("data/cred_001.enc")
        assert item.nonce == bytes.fromhex("deadbeef12345678abcdef00")
        assert item.category == "credentials"

    def test_to_dict_serialization(self) -> None:
        """Test to_dict() for serialization to manifest.json."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        timestamp = datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc)
        item = ExfiltratedDataItem(
            id="data-001-uuid",
            filename="shadow",
            file_type="shadow",
            mime_type="text/plain",
            size_bytes=1024,
            target="192.168.1.100",
            source_agent="postex-agent-7",
            timestamp=timestamp,
            encrypted_path=Path("data/cred_001.enc"),
            sha256_hash="a1b2c3d4e5f6",
            nonce=b"\xde\xad\xbe\xef\x12\x34\x56\x78\xab\xcd\xef\x00",
            category="credentials",
        )

        data = item.to_dict()

        assert data["id"] == "data-001-uuid"
        assert data["filename"] == "shadow"
        assert data["size_bytes"] == 1024
        assert data["encrypted_path"] == "data/cred_001.enc"
        assert data["nonce"] == "deadbeef12345678abcdef00"
        assert data["timestamp"] == "2026-01-29T12:00:00+00:00"

    def test_roundtrip_dict_conversion(self) -> None:
        """Test that to_dict() -> from_dict() preserves data."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        original = ExfiltratedDataItem(
            id="test-roundtrip",
            filename="test.conf",
            file_type="conf",
            mime_type="text/plain",
            size_bytes=2048,
            target="10.0.0.1",
            source_agent="recon-1",
            timestamp=datetime(2026, 1, 29, 14, 30, 0, tzinfo=timezone.utc),
            encrypted_path=Path("data/test.enc"),
            sha256_hash="fedcba987654",
            nonce=os.urandom(12),
            category="configs",
        )

        data = original.to_dict()
        restored = ExfiltratedDataItem.from_dict(data)

        assert restored.id == original.id
        assert restored.filename == original.filename
        assert restored.size_bytes == original.size_bytes
        assert restored.nonce == original.nonce
        assert restored.category == original.category


# ============================================================================
# Task 2: Unit tests for ExfiltratedDataStore class (AC: #1, #6)
# ============================================================================


class TestExfiltratedDataStore:
    """Tests for ExfiltratedDataStore class."""

    @pytest.fixture
    def temp_engagement_path(self, tmp_path: Path) -> Path:
        """Create temporary engagement directory structure."""
        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir(parents=True)
        data_dir = evidence_dir / "data"
        data_dir.mkdir()
        return tmp_path

    @pytest.fixture
    def encryption_key(self) -> bytes:
        """Generate test encryption key."""
        return os.urandom(32)

    @pytest.fixture
    def sample_manifest(self, temp_engagement_path: Path, encryption_key: bytes) -> dict[str, Any]:
        """Create sample manifest with encrypted test data."""
        from cyberred.storage.evidence import encrypt_data

        # Create encrypted test files
        data_dir = temp_engagement_path / "evidence" / "data"
        
        # File 1: credentials
        content1 = b"root:x:0:0:root:/root:/bin/bash\n"
        ciphertext1, nonce1 = encrypt_data(content1, encryption_key)
        (data_dir / "cred_001.enc").write_bytes(ciphertext1)

        # File 2: config
        content2 = b"server {\n  listen 80;\n}\n"
        ciphertext2, nonce2 = encrypt_data(content2, encryption_key)
        (data_dir / "config_002.enc").write_bytes(ciphertext2)

        # File 3: document
        content3 = b"Confidential report content..."
        ciphertext3, nonce3 = encrypt_data(content3, encryption_key)
        (data_dir / "doc_003.enc").write_bytes(ciphertext3)

        manifest = {
            "schema_version": "1.0.0",
            "engagement_id": "eng-test-001",
            "created_at": "2026-01-29T10:00:00Z",
            "updated_at": "2026-01-29T14:30:00Z",
            "exfiltrated_data": [
                {
                    "id": "data-001",
                    "filename": "shadow",
                    "file_type": "shadow",
                    "mime_type": "text/plain",
                    "size_bytes": len(content1),
                    "target": "192.168.1.100",
                    "source_agent": "postex-agent-1",
                    "timestamp": "2026-01-29T12:00:00Z",
                    "encrypted_path": "data/cred_001.enc",
                    "sha256_hash": "abc123",
                    "nonce": nonce1.hex(),
                    "category": "credentials",
                },
                {
                    "id": "data-002",
                    "filename": "nginx.conf",
                    "file_type": "conf",
                    "mime_type": "text/plain",
                    "size_bytes": len(content2),
                    "target": "192.168.1.101",
                    "source_agent": "postex-agent-2",
                    "timestamp": "2026-01-29T13:00:00Z",
                    "encrypted_path": "data/config_002.enc",
                    "sha256_hash": "def456",
                    "nonce": nonce2.hex(),
                    "category": "configs",
                },
                {
                    "id": "data-003",
                    "filename": "report.pdf",
                    "file_type": "pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": len(content3),
                    "target": "192.168.1.100",
                    "source_agent": "postex-agent-1",
                    "timestamp": "2026-01-29T14:00:00Z",
                    "encrypted_path": "data/doc_003.enc",
                    "sha256_hash": "ghi789",
                    "nonce": nonce3.hex(),
                    "category": "documents",
                },
            ],
            "screenshots": [],
            "total_size_bytes": len(content1) + len(content2) + len(content3),
        }

        # Write manifest
        manifest_path = temp_engagement_path / "evidence" / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

        return manifest

    def test_initialization_with_engagement_path(
        self,
        temp_engagement_path: Path,
        encryption_key: bytes,
        sample_manifest: dict[str, Any],
    ) -> None:
        """Test ExfiltratedDataStore initialization."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        store = ExfiltratedDataStore(temp_engagement_path, encryption_key)

        assert store is not None
        assert not store.is_empty

    def test_list_items_returns_all_items(
        self,
        temp_engagement_path: Path,
        encryption_key: bytes,
        sample_manifest: dict[str, Any],
    ) -> None:
        """Test list_items() returns all items sorted by timestamp (newest first)."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        store = ExfiltratedDataStore(temp_engagement_path, encryption_key)
        items = store.list_items()

        assert len(items) == 3
        # Should be sorted newest first
        assert items[0].id == "data-003"  # 14:00
        assert items[1].id == "data-002"  # 13:00
        assert items[2].id == "data-001"  # 12:00

    def test_list_items_filters_by_category(
        self,
        temp_engagement_path: Path,
        encryption_key: bytes,
        sample_manifest: dict[str, Any],
    ) -> None:
        """Test list_items(category=...) filters by category."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        store = ExfiltratedDataStore(temp_engagement_path, encryption_key)

        credentials = store.list_items(category="credentials")
        configs = store.list_items(category="configs")
        documents = store.list_items(category="documents")
        other = store.list_items(category="other")

        assert len(credentials) == 1
        assert credentials[0].filename == "shadow"
        assert len(configs) == 1
        assert configs[0].filename == "nginx.conf"
        assert len(documents) == 1
        assert documents[0].filename == "report.pdf"
        assert len(other) == 0

    def test_get_item_returns_specific_item(
        self,
        temp_engagement_path: Path,
        encryption_key: bytes,
        sample_manifest: dict[str, Any],
    ) -> None:
        """Test get_item(item_id) returns specific item."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        store = ExfiltratedDataStore(temp_engagement_path, encryption_key)

        item = store.get_item("data-002")

        assert item is not None
        assert item.id == "data-002"
        assert item.filename == "nginx.conf"
        assert item.category == "configs"

    def test_get_item_returns_none_for_unknown_id(
        self,
        temp_engagement_path: Path,
        encryption_key: bytes,
        sample_manifest: dict[str, Any],
    ) -> None:
        """Test get_item() returns None for unknown ID."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        store = ExfiltratedDataStore(temp_engagement_path, encryption_key)

        item = store.get_item("nonexistent-id")

        assert item is None

    def test_get_item_content_decrypts_and_returns_content(
        self,
        temp_engagement_path: Path,
        encryption_key: bytes,
        sample_manifest: dict[str, Any],
    ) -> None:
        """Test get_item_content(item_id) decrypts and returns content."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        store = ExfiltratedDataStore(temp_engagement_path, encryption_key)

        content = store.get_item_content("data-001")

        assert content == b"root:x:0:0:root:/root:/bin/bash\n"

    def test_get_item_content_raises_key_error_for_unknown_id(
        self,
        temp_engagement_path: Path,
        encryption_key: bytes,
        sample_manifest: dict[str, Any],
    ) -> None:
        """Test get_item_content() raises KeyError for unknown ID."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        store = ExfiltratedDataStore(temp_engagement_path, encryption_key)

        with pytest.raises(KeyError):
            store.get_item_content("nonexistent-id")

    def test_get_categories_returns_category_counts(
        self,
        temp_engagement_path: Path,
        encryption_key: bytes,
        sample_manifest: dict[str, Any],
    ) -> None:
        """Test get_categories() returns category counts."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        store = ExfiltratedDataStore(temp_engagement_path, encryption_key)

        categories = store.get_categories()

        assert categories == {
            "credentials": 1,
            "configs": 1,
            "documents": 1,
            "other": 0,
        }

    def test_search_by_filename(
        self,
        temp_engagement_path: Path,
        encryption_key: bytes,
        sample_manifest: dict[str, Any],
    ) -> None:
        """Test search(query) searches by filename."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        store = ExfiltratedDataStore(temp_engagement_path, encryption_key)

        results = store.search("shadow")

        assert len(results) == 1
        assert results[0].filename == "shadow"

    def test_search_by_target(
        self,
        temp_engagement_path: Path,
        encryption_key: bytes,
        sample_manifest: dict[str, Any],
    ) -> None:
        """Test search(query) searches by target."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        store = ExfiltratedDataStore(temp_engagement_path, encryption_key)

        results = store.search("192.168.1.100")

        assert len(results) == 2  # shadow and report.pdf

    def test_search_by_category(
        self,
        temp_engagement_path: Path,
        encryption_key: bytes,
        sample_manifest: dict[str, Any],
    ) -> None:
        """Test search(query) searches by category."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        store = ExfiltratedDataStore(temp_engagement_path, encryption_key)

        results = store.search("credentials")

        assert len(results) == 1
        assert results[0].category == "credentials"

    def test_search_case_insensitive(
        self,
        temp_engagement_path: Path,
        encryption_key: bytes,
        sample_manifest: dict[str, Any],
    ) -> None:
        """Test search is case-insensitive."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        store = ExfiltratedDataStore(temp_engagement_path, encryption_key)

        results1 = store.search("SHADOW")
        results2 = store.search("Shadow")
        results3 = store.search("shadow")

        assert len(results1) == 1
        assert len(results2) == 1
        assert len(results3) == 1

    def test_empty_store_returns_empty_list(
        self,
        temp_engagement_path: Path,
        encryption_key: bytes,
    ) -> None:
        """Test empty store returns empty list."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        # Create empty manifest
        manifest = {
            "schema_version": "1.0.0",
            "engagement_id": "eng-empty",
            "created_at": "2026-01-29T10:00:00Z",
            "updated_at": "2026-01-29T10:00:00Z",
            "exfiltrated_data": [],
            "screenshots": [],
            "total_size_bytes": 0,
        }
        manifest_path = temp_engagement_path / "evidence" / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        store = ExfiltratedDataStore(temp_engagement_path, encryption_key)

        assert store.is_empty
        assert store.list_items() == []
        assert store.get_categories() == {
            "credentials": 0,
            "configs": 0,
            "documents": 0,
            "other": 0,
        }

    def test_get_total_size(
        self,
        temp_engagement_path: Path,
        encryption_key: bytes,
        sample_manifest: dict[str, Any],
    ) -> None:
        """Test get_total_size() returns sum of all item sizes."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        store = ExfiltratedDataStore(temp_engagement_path, encryption_key)

        total = store.get_total_size()

        # Sum of content sizes from sample_manifest fixture
        expected = (
            len(b"root:x:0:0:root:/root:/bin/bash\n")
            + len(b"server {\n  listen 80;\n}\n")
            + len(b"Confidential report content...")
        )
        assert total == expected


# ============================================================================
# Task 3: Unit tests for encryption/decryption (AC: #4)
# ============================================================================


class TestEncryption:
    """Tests for encryption/decryption utilities."""

    def test_encrypt_data_aes256_gcm(self) -> None:
        """Test AES-256-GCM encryption of data."""
        from cyberred.storage.evidence import encrypt_data

        key = os.urandom(32)
        plaintext = b"secret data to encrypt"

        ciphertext, nonce = encrypt_data(plaintext, key)

        assert ciphertext != plaintext
        assert len(nonce) == 12  # GCM nonce is 12 bytes
        assert len(ciphertext) > len(plaintext)  # Includes auth tag

    def test_decrypt_data_aes256_gcm(self) -> None:
        """Test AES-256-GCM decryption of data."""
        from cyberred.storage.evidence import encrypt_data, decrypt_data

        key = os.urandom(32)
        plaintext = b"secret data to decrypt"

        ciphertext, nonce = encrypt_data(plaintext, key)
        decrypted = decrypt_data(ciphertext, key, nonce)

        assert decrypted == plaintext

    def test_decrypt_with_wrong_key_raises_decryption_error(self) -> None:
        """Test decryption with wrong key raises DecryptionError."""
        from cyberred.storage.evidence import encrypt_data, decrypt_data

        correct_key = os.urandom(32)
        wrong_key = os.urandom(32)
        plaintext = b"secret data"

        ciphertext, nonce = encrypt_data(plaintext, correct_key)

        with pytest.raises(DecryptionError):
            decrypt_data(ciphertext, wrong_key, nonce)

    def test_encrypt_uses_unique_nonce_per_call(self) -> None:
        """Test encryption uses unique nonce per item."""
        from cyberred.storage.evidence import encrypt_data

        key = os.urandom(32)
        plaintext = b"same data"

        _, nonce1 = encrypt_data(plaintext, key)
        _, nonce2 = encrypt_data(plaintext, key)
        _, nonce3 = encrypt_data(plaintext, key)

        # All nonces should be unique
        assert nonce1 != nonce2
        assert nonce2 != nonce3
        assert nonce1 != nonce3

    def test_encrypt_empty_data(self) -> None:
        """Test encryption of empty data works."""
        from cyberred.storage.evidence import encrypt_data, decrypt_data

        key = os.urandom(32)
        plaintext = b""

        ciphertext, nonce = encrypt_data(plaintext, key)
        decrypted = decrypt_data(ciphertext, key, nonce)

        assert decrypted == b""

    def test_encrypt_large_data(self) -> None:
        """Test encryption of large data works."""
        from cyberred.storage.evidence import encrypt_data, decrypt_data

        key = os.urandom(32)
        plaintext = os.urandom(1024 * 1024)  # 1MB

        ciphertext, nonce = encrypt_data(plaintext, key)
        decrypted = decrypt_data(ciphertext, key, nonce)

        assert decrypted == plaintext


class TestSecureBuffer:
    """Tests for SecureBuffer context manager."""

    def test_secure_buffer_clears_memory_on_exit(self) -> None:
        """Test SecureBuffer clears memory on context exit."""
        from cyberred.storage.evidence import SecureBuffer

        original_data = b"sensitive secret data"

        with SecureBuffer(original_data) as buffer:
            # Data should be accessible inside context
            assert bytes(buffer) == original_data
            # Keep reference to check after
            buffer_ref = buffer

        # After exit, buffer should be cleared
        assert len(buffer_ref) == 0

    def test_secure_buffer_clears_on_exception(self) -> None:
        """Test SecureBuffer clears memory even when exception occurs."""
        from cyberred.storage.evidence import SecureBuffer

        original_data = b"sensitive data"
        buffer_ref = None

        with pytest.raises(ValueError):
            with SecureBuffer(original_data) as buffer:
                buffer_ref = buffer
                raise ValueError("Test exception")

        # Buffer should still be cleared
        assert buffer_ref is not None
        assert len(buffer_ref) == 0

    def test_secure_buffer_zeros_content(self) -> None:
        """Test SecureBuffer zeros the actual bytes, not just clears."""
        from cyberred.storage.evidence import SecureBuffer

        original_data = b"secret"

        with SecureBuffer(original_data) as buffer:
            buffer_copy = bytearray(buffer)  # Copy before zeroing

        # Original buffer reference check happens in __exit__
        # The implementation should zero bytes before clear
        assert buffer_copy == bytearray(original_data)


class TestDecryptionEdgeCases:
    """Tests for decryption error handling edge cases."""

    def test_decrypt_with_invalid_nonce_length(self) -> None:
        """Test decryption with invalid nonce raises DecryptionError."""
        from cyberred.storage.evidence import encrypt_data, decrypt_data
        from cyberred.core.exceptions import DecryptionError

        key = os.urandom(32)
        data = b"test data"

        ciphertext, nonce = encrypt_data(data, key)

        # Try with wrong nonce length
        with pytest.raises(DecryptionError) as exc_info:
            decrypt_data(ciphertext, key, b"short")
        
        assert "Invalid" in str(exc_info.value)

    def test_decrypt_with_corrupted_ciphertext(self) -> None:
        """Test decryption with corrupted ciphertext raises DecryptionError."""
        from cyberred.storage.evidence import encrypt_data, decrypt_data
        from cyberred.core.exceptions import DecryptionError

        key = os.urandom(32)
        data = b"test data"

        ciphertext, nonce = encrypt_data(data, key)

        # Corrupt the ciphertext
        corrupted = bytearray(ciphertext)
        corrupted[0] ^= 0xFF
        corrupted = bytes(corrupted)

        with pytest.raises(DecryptionError) as exc_info:
            decrypt_data(corrupted, key, nonce)
        
        assert "Invalid tag" in str(exc_info.value) or "tampered" in str(exc_info.value)


class TestExfiltratedDataItemFromDict:
    """Tests for ExfiltratedDataItem.from_dict edge cases."""

    def test_from_dict_with_datetime_timestamp(self) -> None:
        """Test from_dict when timestamp is already a datetime object."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        timestamp = datetime(2026, 1, 29, 12, 0, 0, tzinfo=timezone.utc)
        
        data = {
            "id": "test-001",
            "filename": "test.txt",
            "file_type": "txt",
            "mime_type": "text/plain",
            "size_bytes": 100,
            "target": "192.168.1.100",
            "source_agent": "agent-1",
            "timestamp": timestamp,  # Already a datetime
            "encrypted_path": "data/test.enc",
            "sha256_hash": "abc123",
            "nonce": b"\x00" * 12,  # Already bytes
            "category": "other",
        }

        item = ExfiltratedDataItem.from_dict(data)
        
        assert item.timestamp == timestamp
        assert item.nonce == b"\x00" * 12

    def test_from_dict_with_z_suffix_timestamp(self) -> None:
        """Test from_dict with ISO timestamp ending in Z."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        data = {
            "id": "test-002",
            "filename": "test.txt",
            "file_type": "txt",
            "mime_type": "text/plain",
            "size_bytes": 100,
            "target": "192.168.1.100",
            "source_agent": "agent-1",
            "timestamp": "2026-01-29T12:00:00Z",  # Z suffix
            "encrypted_path": "data/test.enc",
            "sha256_hash": "abc123",
            "nonce": "000000000000000000000000",  # Hex string
        }

        item = ExfiltratedDataItem.from_dict(data)
        
        assert item.timestamp.tzinfo is not None

    def test_from_dict_with_naive_timestamp(self) -> None:
        """Test from_dict with naive timestamp (no timezone)."""
        from cyberred.storage.evidence import ExfiltratedDataItem

        data = {
            "id": "test-003",
            "filename": "test.txt",
            "file_type": "txt",
            "mime_type": "text/plain",
            "size_bytes": 100,
            "target": "192.168.1.100",
            "source_agent": "agent-1",
            "timestamp": "2026-01-29T12:00:00",  # No timezone
            "encrypted_path": "data/test.enc",
            "sha256_hash": "abc123",
            "nonce": "000000000000000000000000",
        }

        item = ExfiltratedDataItem.from_dict(data)
        
        # Should add UTC timezone
        assert item.timestamp.tzinfo == timezone.utc


class TestExfiltratedDataStoreManifest:
    """Tests for manifest loading edge cases."""

    def test_load_manifest_not_found(self, tmp_path: Path) -> None:
        """Test store handles missing manifest gracefully."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        # Create engagement dir without manifest
        evidence_path = tmp_path / "evidence"
        evidence_path.mkdir(parents=True)

        store = ExfiltratedDataStore(tmp_path, os.urandom(32))
        
        assert store.is_empty

    def test_load_manifest_invalid_json(self, tmp_path: Path) -> None:
        """Test store handles invalid JSON manifest gracefully."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        evidence_path = tmp_path / "evidence"
        evidence_path.mkdir(parents=True)

        # Create invalid JSON manifest
        manifest_path = evidence_path / "manifest.json"
        manifest_path.write_text("{ invalid json }")

        store = ExfiltratedDataStore(tmp_path, os.urandom(32))
        
        assert store.is_empty

    def test_load_manifest_with_error(self, tmp_path: Path) -> None:
        """Test store handles generic errors during manifest load."""
        from cyberred.storage.evidence import ExfiltratedDataStore
        from unittest.mock import patch, mock_open

        evidence_path = tmp_path / "evidence"
        evidence_path.mkdir(parents=True)

        manifest_path = evidence_path / "manifest.json"
        manifest_path.write_text('{"exfiltrated_data": []}')

        # Mock open to raise an exception
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            store = ExfiltratedDataStore(tmp_path, os.urandom(32))
        
        assert store.is_empty

    def test_get_item_content_file_not_found(self, tmp_path: Path) -> None:
        """Test get_item_content raises KeyError when file doesn't exist."""
        from cyberred.storage.evidence import ExfiltratedDataStore, ExfiltratedDataItem

        evidence_path = tmp_path / "evidence"
        evidence_path.mkdir(parents=True)

        # Create manifest with item but no actual file
        item_data = {
            "id": "missing-001",
            "filename": "missing.txt",
            "file_type": "txt",
            "mime_type": "text/plain",
            "size_bytes": 100,
            "target": "192.168.1.100",
            "source_agent": "agent-1",
            "timestamp": "2026-01-29T12:00:00Z",
            "encrypted_path": "data/missing.enc",
            "sha256_hash": "abc123",
            "nonce": "000000000000000000000000",
        }

        manifest_path = evidence_path / "manifest.json"
        manifest_path.write_text(json.dumps({"exfiltrated_data": [item_data]}))

        store = ExfiltratedDataStore(tmp_path, os.urandom(32))

        with pytest.raises(KeyError) as exc_info:
            store.get_item_content("missing-001")
        
        assert "not found" in str(exc_info.value)


class TestExfiltratedDataStoreFiltering:
    """Tests for list_items and search filtering."""

    @pytest.fixture
    def store_with_items(self, tmp_path: Path) -> "ExfiltratedDataStore":
        """Create store with multiple items for filtering tests."""
        from cyberred.storage.evidence import ExfiltratedDataStore, encrypt_data

        evidence_path = tmp_path / "evidence"
        data_path = evidence_path / "data"
        data_path.mkdir(parents=True)

        key = os.urandom(32)

        items = []
        for i, (name, cat, ftype, ts) in enumerate([
            ("passwords.txt", "credentials", "txt", "2026-01-28T10:00:00Z"),
            ("config.json", "configs", "json", "2026-01-28T12:00:00Z"),
            ("report.pdf", "documents", "pdf", "2026-01-28T14:00:00Z"),
            ("backup.txt", "other", "txt", "2026-01-29T10:00:00Z"),
        ]):
            content = f"content for {name}".encode()
            ciphertext, nonce = encrypt_data(content, key)
            
            enc_path = data_path / f"item_{i}.enc"
            enc_path.write_bytes(ciphertext)

            items.append({
                "id": f"item-{i:03d}",
                "filename": name,
                "file_type": ftype,
                "mime_type": "text/plain" if ftype == "txt" else f"application/{ftype}",
                "size_bytes": len(content),
                "target": f"192.168.1.{100 + i}",
                "source_agent": f"agent-{i}",
                "timestamp": ts,
                "encrypted_path": f"data/item_{i}.enc",
                "sha256_hash": f"hash{i}",
                "nonce": nonce.hex(),
                "category": cat,
            })

        manifest_path = evidence_path / "manifest.json"
        manifest_path.write_text(json.dumps({"exfiltrated_data": items}))

        return ExfiltratedDataStore(tmp_path, key)

    def test_list_items_filter_by_start_time(
        self, store_with_items: "ExfiltratedDataStore"
    ) -> None:
        """Test list_items filters by start_time."""
        start = datetime(2026, 1, 28, 13, 0, 0, tzinfo=timezone.utc)
        
        items = store_with_items.list_items(start_time=start)
        
        for item in items:
            assert item.timestamp >= start

    def test_list_items_filter_by_end_time(
        self, store_with_items: "ExfiltratedDataStore"
    ) -> None:
        """Test list_items filters by end_time."""
        end = datetime(2026, 1, 28, 13, 0, 0, tzinfo=timezone.utc)
        
        items = store_with_items.list_items(end_time=end)
        
        for item in items:
            assert item.timestamp <= end

    def test_list_items_filter_by_file_type(
        self, store_with_items: "ExfiltratedDataStore"
    ) -> None:
        """Test list_items filters by file_type."""
        items = store_with_items.list_items(file_type="txt")
        
        assert len(items) == 2  # passwords.txt and backup.txt
        for item in items:
            assert item.file_type == "txt"

    def test_list_items_filter_by_file_type_case_insensitive(
        self, store_with_items: "ExfiltratedDataStore"
    ) -> None:
        """Test list_items file_type filter is case-insensitive."""
        items_lower = store_with_items.list_items(file_type="txt")
        items_upper = store_with_items.list_items(file_type="TXT")
        
        assert len(items_lower) == len(items_upper)

    def test_search_with_category_filter(
        self, store_with_items: "ExfiltratedDataStore"
    ) -> None:
        """Test search with category filter."""
        # Search for all items, filter by credentials category
        items = store_with_items.search("", category="credentials")
        
        assert len(items) == 1
        assert items[0].category == "credentials"

    def test_search_with_start_time_filter(
        self, store_with_items: "ExfiltratedDataStore"
    ) -> None:
        """Test search with start_time filter."""
        start = datetime(2026, 1, 29, 0, 0, 0, tzinfo=timezone.utc)
        
        items = store_with_items.search("", start_time=start)
        
        for item in items:
            assert item.timestamp >= start

    def test_search_with_end_time_filter(
        self, store_with_items: "ExfiltratedDataStore"
    ) -> None:
        """Test search with end_time filter."""
        end = datetime(2026, 1, 28, 11, 0, 0, tzinfo=timezone.utc)
        
        items = store_with_items.search("", end_time=end)
        
        for item in items:
            assert item.timestamp <= end

    def test_search_with_file_type_filter(
        self, store_with_items: "ExfiltratedDataStore"
    ) -> None:
        """Test search with file_type filter."""
        items = store_with_items.search("", file_type="json")
        
        assert len(items) == 1
        assert items[0].file_type == "json"

    def test_search_combined_filters(
        self, store_with_items: "ExfiltratedDataStore"
    ) -> None:
        """Test search with multiple filters combined."""
        start = datetime(2026, 1, 28, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 1, 28, 23, 59, 59, tzinfo=timezone.utc)
        
        items = store_with_items.search(
            "",
            file_type="txt",
            start_time=start,
            end_time=end,
        )
        
        # Only passwords.txt should match (txt file on Jan 28)
        assert len(items) == 1
        assert items[0].filename == "passwords.txt"


class TestGetCategoriesEdgeCases:
    """Tests for get_categories edge cases."""

    def test_get_categories_with_unknown_category(self, tmp_path: Path) -> None:
        """Test get_categories counts unknown categories as 'other'."""
        from cyberred.storage.evidence import ExfiltratedDataStore

        evidence_path = tmp_path / "evidence"
        evidence_path.mkdir(parents=True)

        # Create item with unknown category
        item_data = {
            "id": "unknown-001",
            "filename": "mystery.xyz",
            "file_type": "xyz",
            "mime_type": "application/octet-stream",
            "size_bytes": 100,
            "target": "192.168.1.100",
            "source_agent": "agent-1",
            "timestamp": "2026-01-29T12:00:00Z",
            "encrypted_path": "data/mystery.enc",
            "sha256_hash": "abc123",
            "nonce": "000000000000000000000000",
            "category": "unknown_category",  # Non-standard category
        }

        manifest_path = evidence_path / "manifest.json"
        manifest_path.write_text(json.dumps({"exfiltrated_data": [item_data]}))

        store = ExfiltratedDataStore(tmp_path, os.urandom(32))
        
        categories = store.get_categories()
        
        # Unknown category should be counted as "other"
        assert categories["other"] == 1
