"""Evidence File Storage Module.

Story 13.1: Evidence File Storage

Provides secure evidence storage with SHA-256 manifests for cryptographic
integrity (FR36). All evidence is encrypted at rest using AES-256-GCM (NFR14).

Components:
    - EvidenceType: Enum for evidence categories
    - EvidenceItem: Dataclass for individual evidence items
    - EvidenceStore: Manager for encrypted evidence storage

Security Notes:
    - Data encrypted at rest with AES-256-GCM
    - SHA-256 hash of original content stored in manifest
    - Atomic manifest writes prevent corruption on crash
    - All timestamps are UTC ISO8601

Usage:
    from cyberred.storage.evidence_store import EvidenceStore, EvidenceType

    store = EvidenceStore(engagement_id, encryption_key)
    item = store.store_evidence(content, "screenshot.png", "recon-01", EvidenceType.SCREENSHOT)
    
    # Verify integrity
    assert store.verify_integrity(item.id)
    
    # Retrieve decrypted content
    content = store.get_evidence(item.id)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from cyberred.core.exceptions import DecryptionError, IntegrityError
from cyberred.storage.evidence import decrypt_data, encrypt_data, NONCE_LENGTH

logger = logging.getLogger(__name__)


class EvidenceType(Enum):
    """Types of evidence that can be stored.
    
    Per Story 13.1 AC #2: screenshot, log, loot, other.
    """
    
    SCREENSHOT = "screenshot"
    LOG = "log"
    LOOT = "loot"
    OTHER = "other"


@dataclass
class EvidenceItem:
    """Single evidence item with cryptographic metadata.
    
    Per FR36: Evidence files + SHA-256 manifest.
    
    Attributes:
        id: Unique identifier (UUID).
        filename: Original filename.
        sha256_hash: SHA-256 hash of original plaintext content.
        encrypted_path: Relative path to encrypted file.
        nonce: AES-GCM nonce for decryption.
        size_bytes: Size of original content.
        timestamp: When the evidence was stored (UTC).
        source_agent: Agent ID that collected this evidence.
        evidence_type: Type of evidence (screenshot, log, loot, other).
    """
    
    id: str
    filename: str
    sha256_hash: str
    encrypted_path: Path
    nonce: bytes
    size_bytes: int
    timestamp: datetime
    source_agent: str
    evidence_type: EvidenceType
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for manifest.json.
        
        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "id": self.id,
            "filename": self.filename,
            "sha256_hash": self.sha256_hash,
            "encrypted_path": str(self.encrypted_path),
            "nonce": self.nonce.hex(),
            "size_bytes": self.size_bytes,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
            "source_agent": self.source_agent,
            "evidence_type": self.evidence_type.value,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceItem:
        """Create EvidenceItem from dictionary.
        
        Args:
            data: Dictionary with item data (e.g., from manifest.json).
            
        Returns:
            EvidenceItem instance.
        """
        # Parse timestamp
        timestamp_str = data["timestamp"]
        if isinstance(timestamp_str, str):
            # Handle ISO format with Z or +00:00
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
        
        # Parse evidence type
        evidence_type_value = data["evidence_type"]
        if isinstance(evidence_type_value, str):
            evidence_type = EvidenceType(evidence_type_value)
        else:
            evidence_type = evidence_type_value
        
        return cls(
            id=data["id"],
            filename=data["filename"],
            sha256_hash=data["sha256_hash"],
            encrypted_path=Path(data["encrypted_path"]),
            nonce=nonce,
            size_bytes=data["size_bytes"],
            timestamp=timestamp,
            source_agent=data["source_agent"],
            evidence_type=evidence_type,
        )


class EvidenceStore:
    """Manages encrypted evidence storage with SHA-256 integrity.
    
    Per FR36/NFR14: Evidence files + SHA-256 manifest, AES-256 at rest.
    
    The store manages evidence for a single engagement, storing files
    encrypted with AES-256-GCM and maintaining a manifest.json with
    SHA-256 hashes for integrity verification.
    
    Directory Structure:
        {base_path}/{engagement_id}/
        ├── manifest.json        # SHA-256 hashes, metadata
        └── data/
            ├── {uuid1}.enc      # Encrypted evidence file
            └── {uuid2}.enc      # Another encrypted file
    
    Attributes:
        MANIFEST_FILE: Name of the manifest file.
        DATA_DIR: Name of the data subdirectory.
        MANIFEST_VERSION: Current manifest schema version.
    """
    
    MANIFEST_FILE = "manifest.json"
    DATA_DIR = "data"
    MANIFEST_VERSION = "1.0"
    
    def __init__(
        self,
        engagement_id: str,
        encryption_key: bytes,
        base_path: Path | None = None,
    ) -> None:
        """Initialize EvidenceStore.
        
        Args:
            engagement_id: Unique engagement identifier.
            encryption_key: 32-byte AES-256 encryption key.
            base_path: Base directory for evidence storage.
                       Defaults to ~/.cyber-red/evidence.
        
        Raises:
            ValueError: If encryption_key is not 32 bytes.
            ValueError: If engagement_id is empty or invalid.
        """
        # Validate engagement_id
        if not engagement_id or not engagement_id.strip():
            raise ValueError("Engagement ID cannot be empty")
        
        # Validate encryption key
        if len(encryption_key) != 32:
            raise ValueError(
                f"Encryption key must be 32 bytes (got {len(encryption_key)})"
            )
        
        self._engagement_id = engagement_id
        self._encryption_key = encryption_key
        
        # Set base path
        if base_path is None:
            base_path = Path.home() / ".cyber-red" / "evidence"
        self._base_path = base_path
        
        # Set engagement directory
        self._evidence_dir = self._base_path / engagement_id
        self._data_dir = self._evidence_dir / self.DATA_DIR
        self._manifest_path = self._evidence_dir / self.MANIFEST_FILE
        
        # Create directory structure
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # Items cache
        self._items: dict[str, EvidenceItem] = {}
        
        # Thread lock for all item/manifest operations
        self._lock = threading.RLock()
        
        # Track manifest creation timestamp (preserved across saves)
        self._manifest_created_at: str | None = None
        
        # Load or create manifest
        if self._manifest_path.exists():
            self._load_manifest()
        else:
            self._create_manifest()
    
    @property
    def base_path(self) -> Path:
        """Return the base path for evidence storage."""
        return self._base_path
    
    def _create_manifest(self) -> None:
        """Create a new manifest.json file."""
        self._manifest_created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        manifest = {
            "version": self.MANIFEST_VERSION,
            "engagement_id": self._engagement_id,
            "created_at": self._manifest_created_at,
            "evidence": [],
        }
        self._save_manifest(manifest)
        logger.info("Created new manifest for engagement %s", self._engagement_id)
    
    def _load_manifest(self) -> None:
        """Load manifest.json and populate items cache."""
        try:
            with open(self._manifest_path) as f:
                manifest = json.load(f)
            
            # Preserve original created_at timestamp
            self._manifest_created_at = manifest.get("created_at")
            
            for item_data in manifest.get("evidence", []):
                item = EvidenceItem.from_dict(item_data)
                self._items[item.id] = item
            
            logger.info("Loaded %d items from manifest", len(self._items))
        
        except json.JSONDecodeError as e:
            logger.error("Failed to parse manifest: %s", e)
            raise
        except Exception as e:
            logger.error("Failed to load manifest: %s", e)
            raise
    
    def _save_manifest(self, manifest: dict[str, Any] | None = None) -> None:
        """Save manifest.json atomically.
        
        Uses atomic write pattern: write to temp file, then rename.
        This prevents partial writes on crash.
        
        Args:
            manifest: Optional manifest dict to save. If None, rebuilds from items.
        """
        if manifest is None:
            # Rebuild manifest from items, preserving original created_at
            manifest = {
                "version": self.MANIFEST_VERSION,
                "engagement_id": self._engagement_id,
                "created_at": self._manifest_created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "evidence": [item.to_dict() for item in self._items.values()],
            }
        
        # Write to temp file first (atomic pattern)
        temp_fd, temp_path = tempfile.mkstemp(
            suffix=".json",
            dir=self._evidence_dir,
        )
        try:
            with os.fdopen(temp_fd, "w") as f:
                json.dump(manifest, f, indent=2)
            
            # Atomic rename
            shutil.move(temp_path, str(self._manifest_path))
        
        except Exception:
            # Clean up temp file on error
            if Path(temp_path).exists():
                Path(temp_path).unlink()
            raise
    
    def store_evidence(
        self,
        content: bytes,
        filename: str,
        source_agent: str,
        evidence_type: EvidenceType,
    ) -> EvidenceItem:
        """Store evidence with encryption and hash verification.
        
        Thread-safe: Uses lock for all operations.
        
        Args:
            content: Raw evidence content bytes (can be empty).
            filename: Original filename (must not contain path separators).
            source_agent: ID of the agent that collected this evidence.
            evidence_type: Type of evidence.
        
        Returns:
            EvidenceItem with metadata about stored evidence.
        
        Raises:
            ValueError: If filename is empty or contains path traversal.
        """
        # Validate filename - prevent path traversal and empty names
        if not filename or not filename.strip():
            raise ValueError("Filename cannot be empty")
        if "/" in filename or "\\" in filename or ".." in filename:
            raise ValueError("Filename cannot contain path separators or '..'")
        
        # Generate unique ID
        evidence_id = str(uuid.uuid4())
        
        # Calculate SHA-256 hash of original content
        sha256_hash = hashlib.sha256(content).hexdigest()
        
        # Encrypt content
        ciphertext, nonce = encrypt_data(content, self._encryption_key)
        
        # Write encrypted file
        encrypted_path = Path(self.DATA_DIR) / f"{evidence_id}.enc"
        full_encrypted_path = self._evidence_dir / encrypted_path
        full_encrypted_path.write_bytes(ciphertext)
        
        # Create evidence item
        item = EvidenceItem(
            id=evidence_id,
            filename=filename,
            sha256_hash=sha256_hash,
            encrypted_path=encrypted_path,
            nonce=nonce,
            size_bytes=len(content),
            timestamp=datetime.now(timezone.utc),
            source_agent=source_agent,
            evidence_type=evidence_type,
        )
        
        # Thread-safe: Add to cache and save manifest atomically
        with self._lock:
            self._items[evidence_id] = item
            self._save_manifest()
        
        logger.info("Stored evidence %s: %s (%d bytes)", evidence_id, filename, len(content))
        
        return item
    
    def get_evidence(self, evidence_id: str) -> bytes:
        """Retrieve and decrypt evidence content.
        
        Thread-safe: Uses lock to access items cache.
        
        Args:
            evidence_id: ID of the evidence to retrieve.
        
        Returns:
            Decrypted evidence content.
        
        Raises:
            KeyError: If evidence_id not found.
            DecryptionError: If decryption fails (wrong key or tampered data).
            IntegrityError: If SHA-256 hash verification fails.
        """
        with self._lock:
            item = self._items.get(evidence_id)
        if item is None:
            raise KeyError(f"Evidence not found: {evidence_id}")
        
        # Read encrypted file
        encrypted_path = self._evidence_dir / item.encrypted_path
        if not encrypted_path.exists():
            raise KeyError(f"Encrypted file not found: {encrypted_path}")
        
        ciphertext = encrypted_path.read_bytes()
        
        # Decrypt - AES-GCM will raise DecryptionError if tampered or wrong key
        plaintext = decrypt_data(ciphertext, self._encryption_key, item.nonce)
        
        # Verify hash
        actual_hash = hashlib.sha256(plaintext).hexdigest()
        if actual_hash != item.sha256_hash:
            raise IntegrityError(
                evidence_id=evidence_id,
                expected_hash=item.sha256_hash,
                actual_hash=actual_hash,
            )
        
        return plaintext
    
    def verify_integrity(self, evidence_id: str) -> bool:
        """Verify SHA-256 hash of evidence.
        
        Thread-safe: Uses lock to access items cache.
        
        Args:
            evidence_id: ID of the evidence to verify.
        
        Returns:
            True if hash matches, False otherwise.
        
        Raises:
            KeyError: If evidence_id not found.
            DecryptionError: If decryption fails.
        """
        with self._lock:
            item = self._items.get(evidence_id)
        if item is None:
            raise KeyError(f"Evidence not found: {evidence_id}")
        
        # Read encrypted file
        encrypted_path = self._evidence_dir / item.encrypted_path
        if not encrypted_path.exists():
            raise KeyError(f"Encrypted file not found: {encrypted_path}")
        
        ciphertext = encrypted_path.read_bytes()
        
        try:
            # Decrypt
            plaintext = decrypt_data(ciphertext, self._encryption_key, item.nonce)
            
            # Verify hash
            actual_hash = hashlib.sha256(plaintext).hexdigest()
            return actual_hash == item.sha256_hash
        
        except DecryptionError:
            # Decryption failure means integrity check failed
            return False
    
    def list_evidence(
        self,
        evidence_type: EvidenceType | None = None,
    ) -> list[EvidenceItem]:
        """List all evidence items, optionally filtered.
        
        Thread-safe: Uses lock to access items cache.
        Items are sorted by timestamp (newest first).
        
        Args:
            evidence_type: Optional filter by evidence type.
        
        Returns:
            List of EvidenceItem sorted by timestamp descending.
        """
        with self._lock:
            items = list(self._items.values())
        
        if evidence_type is not None:
            items = [i for i in items if i.evidence_type == evidence_type]
        
        # Sort by timestamp, newest first
        items.sort(key=lambda x: x.timestamp, reverse=True)
        return items
    
    def get_manifest_hash(self) -> str:
        """Get SHA-256 hash of entire manifest.
        
        Returns:
            Hexadecimal SHA-256 hash of manifest.json content.
        """
        if not self._manifest_path.exists():
            return ""
        
        content = self._manifest_path.read_bytes()
        return hashlib.sha256(content).hexdigest()
