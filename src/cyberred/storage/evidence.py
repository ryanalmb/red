"""Exfiltrated Data Storage Module.

Story 11.2: Exfiltrated Data Browser

Provides secure storage and retrieval for exfiltrated data during engagements.
All data is encrypted at rest using AES-256-GCM (per FR43).

Components:
    - ExfiltratedDataItem: Dataclass for individual data items
    - ExfiltratedDataStore: Manager for encrypted evidence storage
    - encrypt_data/decrypt_data: AES-256-GCM encryption utilities
    - SecureBuffer: Context manager for secure memory handling

Security Notes:
    - Data encrypted at rest with AES-256-GCM
    - Decrypted content only held in memory, never written to disk
    - SecureBuffer zeros memory after use
    - No auto-delete of evidence (FR44)

Usage:
    from cyberred.storage.evidence import ExfiltratedDataStore, SecureBuffer

    store = ExfiltratedDataStore(engagement_path, encryption_key)
    items = store.list_items(category="credentials")
    
    with SecureBuffer(store.get_item_content(item.id)) as content:
        # Process decrypted content
        pass
    # Content automatically zeroed after context exit
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from cyberred.core.exceptions import DecryptionError

logger = logging.getLogger(__name__)

# Constants
NONCE_LENGTH = 12  # 96 bits for GCM
MAX_PREVIEW_SIZE = 10 * 1024  # 10KB

# Category detection patterns
CREDENTIAL_PATTERNS = frozenset([
    "password", "passwd", "shadow", "sam", "ntds", "credential",
    "secret", "token", "key", ".hash", "htpasswd", "credentials",
])

DOCUMENT_EXTENSIONS = frozenset([
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp",
])

CONFIG_PATTERNS = frozenset([
    "conf", "cfg", "ini", "yaml", "yml", "json", "xml", "env", "toml",
    "config", "settings", ".env",
])

TEXT_MIME_PREFIXES = ("text/", "application/json", "application/xml", "application/javascript")


def encrypt_data(data: bytes, key: bytes) -> tuple[bytes, bytes]:
    """Encrypt data using AES-256-GCM.

    Args:
        data: Plaintext data to encrypt.
        key: 32-byte encryption key.

    Returns:
        Tuple of (ciphertext, nonce) where ciphertext includes auth tag.
    """
    nonce = os.urandom(NONCE_LENGTH)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return ciphertext, nonce


def decrypt_data(ciphertext: bytes, key: bytes, nonce: bytes) -> bytes:
    """Decrypt data using AES-256-GCM.

    Args:
        ciphertext: Encrypted data (includes auth tag).
        key: 32-byte encryption key.
        nonce: 12-byte nonce used during encryption.

    Returns:
        Original plaintext bytes.

    Raises:
        DecryptionError: If decryption fails (wrong key, tampered data, etc).
    """
    try:
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag as e:
        raise DecryptionError("Invalid tag - wrong key or tampered data") from e
    except ValueError as e:
        raise DecryptionError(f"Invalid parameters: {e}") from e
    except Exception as e:
        raise DecryptionError(f"Unexpected error: {e}") from e


class SecureBuffer:
    """Context manager that zeros memory on exit.

    Provides secure handling for sensitive data by ensuring the buffer
    contents are zeroed when the context exits, even on exception.

    Usage:
        with SecureBuffer(sensitive_data) as buffer:
            # Work with buffer
            process(bytes(buffer))
        # Buffer is now zeroed
    """

    def __init__(self, data: bytes) -> None:
        """Initialize SecureBuffer with data.

        Args:
            data: Bytes to protect.
        """
        self._data = bytearray(data)

    def __enter__(self) -> bytearray:
        """Enter context and return buffer.

        Returns:
            Bytearray containing the data.
        """
        return self._data

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context and zero the buffer.

        Always zeros the buffer, even if an exception occurred.
        """
        # Zero the bytes
        self._data[:] = b"\x00" * len(self._data)
        # Clear the bytearray
        self._data.clear()


def _detect_category(filename: str, file_type: str) -> str:
    """Detect category based on filename and file type.

    Args:
        filename: Original filename.
        file_type: File extension/type.

    Returns:
        Category string: "credentials", "documents", "configs", or "other".
    """
    filename_lower = filename.lower()
    file_type_lower = file_type.lower()

    # Check for credentials
    for pattern in CREDENTIAL_PATTERNS:
        if pattern in filename_lower:
            return "credentials"

    # Check for documents by extension
    if file_type_lower in DOCUMENT_EXTENSIONS:
        return "documents"

    # Check for configs
    for pattern in CONFIG_PATTERNS:
        if pattern in filename_lower or file_type_lower == pattern:
            return "configs"

    return "other"


@dataclass
class ExfiltratedDataItem:
    """Single exfiltrated data item.

    Per FR42/FR43/FR44 - represents a piece of evidence collected
    during an engagement, stored encrypted at rest.

    Attributes:
        id: Unique identifier (UUID).
        filename: Original filename.
        file_type: File extension (e.g., "txt", "json").
        mime_type: MIME type (e.g., "text/plain").
        size_bytes: Size of original content.
        target: Source IP/hostname where data was collected.
        source_agent: Agent ID that collected this data.
        timestamp: When the data was collected.
        encrypted_path: Path to encrypted file (relative to evidence dir).
        sha256_hash: Hash of original content for integrity.
        nonce: AES-GCM nonce for decryption.
        category: Auto-detected category (credentials/documents/configs/other).
    """

    id: str
    filename: str
    file_type: str
    mime_type: str
    size_bytes: int
    target: str
    source_agent: str
    timestamp: datetime
    encrypted_path: Path
    sha256_hash: str
    nonce: bytes
    category: str = field(default="")

    def __post_init__(self) -> None:
        """Auto-detect category if not provided."""
        if not self.category:
            self.category = _detect_category(self.filename, self.file_type)

    @property
    def is_text(self) -> bool:
        """Check if item is a text file based on MIME type.

        Returns:
            True if MIME type indicates text content.
        """
        return self.mime_type.startswith(TEXT_MIME_PREFIXES)

    @property
    def is_previewable(self) -> bool:
        """Check if item can be previewed (text and under 10KB).

        Returns:
            True if item is text and size <= 10KB.
        """
        return self.is_text and self.size_bytes <= MAX_PREVIEW_SIZE

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExfiltratedDataItem:
        """Create ExfiltratedDataItem from dictionary.

        Args:
            data: Dictionary with item data (e.g., from manifest.json).

        Returns:
            ExfiltratedDataItem instance.
        """
        # Parse timestamp
        timestamp_str = data["timestamp"]
        if isinstance(timestamp_str, str):
            # Handle ISO format with or without timezone
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str[:-1] + "+00:00"
            timestamp = datetime.fromisoformat(timestamp_str)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp_str

        # Parse nonce from hex string
        nonce_data = data["nonce"]
        if isinstance(nonce_data, str):
            nonce = bytes.fromhex(nonce_data)
        else:
            nonce = nonce_data

        return cls(
            id=data["id"],
            filename=data["filename"],
            file_type=data["file_type"],
            mime_type=data["mime_type"],
            size_bytes=data["size_bytes"],
            target=data["target"],
            source_agent=data["source_agent"],
            timestamp=timestamp,
            encrypted_path=Path(data["encrypted_path"]),
            sha256_hash=data["sha256_hash"],
            nonce=nonce,
            category=data.get("category", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for manifest.json.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "id": self.id,
            "filename": self.filename,
            "file_type": self.file_type,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "target": self.target,
            "source_agent": self.source_agent,
            "timestamp": self.timestamp.isoformat(),
            "encrypted_path": str(self.encrypted_path),
            "sha256_hash": self.sha256_hash,
            "nonce": self.nonce.hex(),
            "category": self.category,
        }


class ExfiltratedDataStore:
    """Manages encrypted exfiltrated data storage.

    Per FR42/FR43/FR44 - provides access to evidence collected during
    an engagement. All data is encrypted at rest using AES-256-GCM.

    The store loads metadata from manifest.json and provides methods
    to list, filter, search, and decrypt evidence items.

    Attributes:
        MANIFEST_FILE: Name of the manifest file.
        DATA_DIR: Name of the data subdirectory.
    """

    MANIFEST_FILE = "manifest.json"
    DATA_DIR = "data"

    def __init__(self, engagement_path: Path, encryption_key: bytes) -> None:
        """Initialize ExfiltratedDataStore.

        Args:
            engagement_path: Path to engagement directory.
            encryption_key: 32-byte AES-256 encryption key.
        """
        self._engagement_path = engagement_path
        self._evidence_path = engagement_path / "evidence"
        self._encryption_key = encryption_key
        self._items: dict[str, ExfiltratedDataItem] = {}

        self._load_manifest()

    def _load_manifest(self) -> None:
        """Load manifest.json and populate items cache."""
        manifest_path = self._evidence_path / self.MANIFEST_FILE

        if not manifest_path.exists():
            logger.warning(f"Manifest not found at {manifest_path}")
            return

        try:
            with open(manifest_path) as f:
                manifest = json.load(f)

            for item_data in manifest.get("exfiltrated_data", []):
                item = ExfiltratedDataItem.from_dict(item_data)
                self._items[item.id] = item

            logger.info(f"Loaded {len(self._items)} items from manifest")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse manifest: {e}")
        except Exception as e:
            logger.error(f"Failed to load manifest: {e}")

    @property
    def is_empty(self) -> bool:
        """Check if store has no items.

        Returns:
            True if no exfiltrated data items exist.
        """
        return len(self._items) == 0

    def list_items(
        self,
        category: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        file_type: str | None = None,
    ) -> list[ExfiltratedDataItem]:
        """List all items, optionally filtered by category, timestamp, or file type.

        Items are sorted by timestamp (newest first).

        Args:
            category: Optional category filter (credentials/documents/configs/other).
            start_time: Optional start of timestamp range filter (inclusive).
            end_time: Optional end of timestamp range filter (inclusive).
            file_type: Optional file extension filter (e.g., "json", "txt").

        Returns:
            List of ExfiltratedDataItem sorted by timestamp descending.
        """
        items = list(self._items.values())

        if category is not None:
            items = [i for i in items if i.category == category]

        if start_time is not None:
            items = [i for i in items if i.timestamp >= start_time]

        if end_time is not None:
            items = [i for i in items if i.timestamp <= end_time]

        if file_type is not None:
            file_type_lower = file_type.lower()
            items = [i for i in items if i.file_type.lower() == file_type_lower]

        # Sort by timestamp, newest first
        items.sort(key=lambda x: x.timestamp, reverse=True)
        return items

    def get_item(self, item_id: str) -> ExfiltratedDataItem | None:
        """Get a specific item by ID.

        Args:
            item_id: Unique item identifier.

        Returns:
            ExfiltratedDataItem or None if not found.
        """
        return self._items.get(item_id)

    def get_item_content(self, item_id: str) -> bytes:
        """Get decrypted content of an item.

        Args:
            item_id: Unique item identifier.

        Returns:
            Decrypted content bytes.

        Raises:
            KeyError: If item_id not found.
            DecryptionError: If decryption fails.
        """
        item = self._items.get(item_id)
        if item is None:
            raise KeyError(f"Item not found: {item_id}")

        # Read encrypted file
        encrypted_path = self._evidence_path / item.encrypted_path
        if not encrypted_path.exists():
            raise KeyError(f"Encrypted file not found: {encrypted_path}")

        ciphertext = encrypted_path.read_bytes()
        return decrypt_data(ciphertext, self._encryption_key, item.nonce)

    def get_categories(self) -> dict[str, int]:
        """Get category counts.

        Returns:
            Dictionary mapping category names to item counts.
        """
        counts = {
            "credentials": 0,
            "configs": 0,
            "documents": 0,
            "other": 0,
        }

        for item in self._items.values():
            if item.category in counts:
                counts[item.category] += 1
            else:
                counts["other"] += 1

        return counts

    def search(
        self,
        query: str,
        category: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        file_type: str | None = None,
    ) -> list[ExfiltratedDataItem]:
        """Search items by filename, target, or category.

        Search is case-insensitive. Additional filters can be combined.

        Args:
            query: Search query string.
            category: Optional category filter.
            start_time: Optional start of timestamp range filter (inclusive).
            end_time: Optional end of timestamp range filter (inclusive).
            file_type: Optional file extension filter (e.g., "json", "txt").

        Returns:
            List of matching ExfiltratedDataItem sorted by timestamp.
        """
        query_lower = query.lower()
        # Escape regex special chars for safe matching
        query_escaped = re.escape(query_lower)

        results = []
        for item in self._items.values():
            # Apply text search
            searchable = f"{item.filename} {item.target} {item.category}".lower()
            if query_lower not in searchable:
                continue

            # Apply category filter
            if category is not None and item.category != category:
                continue

            # Apply timestamp range filter
            if start_time is not None and item.timestamp < start_time:
                continue
            if end_time is not None and item.timestamp > end_time:
                continue

            # Apply file type filter
            if file_type is not None and item.file_type.lower() != file_type.lower():
                continue

            results.append(item)

        # Sort by timestamp, newest first
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results

    def get_total_size(self) -> int:
        """Get total size of all items in bytes.

        Returns:
            Sum of size_bytes for all items.
        """
        return sum(item.size_bytes for item in self._items.values())
