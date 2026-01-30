"""Secure Data Deletion Module.

Story 11.4: Manual Data Deletion

Provides secure deletion with 3-pass random overwrite (DoD 5220.22-M style).
Per FR45: Manual deletion with operator confirmation and audit logging.

Components:
    - SECURE_DELETE_PASSES: Number of overwrite passes (3)
    - DeletionResult: Dataclass for deletion operation results
    - SecureDeleter: Secure deletion logic with audit logging

Security Notes:
    - Uses secrets.token_bytes() for cryptographic randomness
    - Calls fsync after each overwrite pass to ensure disk write
    - Verifies file deletion after unlink
    - All deletions logged to audit trail

Usage:
    from cyberred.storage.deleter import SecureDeleter, DeletionResult

    deleter = SecureDeleter(store, audit_logger)
    
    # Single item deletion
    deleter.delete_item("item-123")
    
    # Bulk deletion with continue on error
    result = deleter.delete_items(["item-1", "item-2"], continue_on_error=True)
    if not result.success:
        print(f"Failed items: {result.failed_items}")
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from cyberred.core.exceptions import DeletionError

if TYPE_CHECKING:
    from cyberred.storage.evidence import ExfiltratedDataStore
    from cyberred.core.audit import DeletionAuditLogger

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

SECURE_DELETE_PASSES = 3  # DoD 5220.22-M style 3-pass overwrite


# ─────────────────────────────────────────────────────────────────────────────
# DeletionResult
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DeletionResult:
    """Result of a deletion operation.

    Tracks success/failure of bulk deletion operations.

    Attributes:
        total_items: Total number of items attempted.
        deleted_items: Number of successfully deleted items.
        failed_items: List of (item_id, error_message) tuples for failures.
    """

    total_items: int
    deleted_items: int
    failed_items: list[tuple[str, str]]

    @property
    def success(self) -> bool:
        """Check if all items were deleted successfully.

        Returns:
            True if deleted_items equals total_items.
        """
        return self.deleted_items == self.total_items


# ─────────────────────────────────────────────────────────────────────────────
# SecureDeleter
# ─────────────────────────────────────────────────────────────────────────────


class SecureDeleter:
    """Secure deletion with 3-pass random overwrite (DoD 5220.22-M style).

    Per FR45: Manual deletion with audit logging.

    The secure deletion process:
    1. Overwrite file content with random bytes (3 passes)
    2. Call fsync after each pass to ensure disk write
    3. Unlink (delete) the file
    4. Verify file no longer exists
    5. Update manifest and audit log

    Attributes:
        _store: ExfiltratedDataStore for item access.
        _audit: DeletionAuditLogger for audit trail.
    """

    def __init__(
        self,
        store: "ExfiltratedDataStore",
        audit_logger: "DeletionAuditLogger",
    ) -> None:
        """Initialize SecureDeleter.

        Args:
            store: ExfiltratedDataStore instance.
            audit_logger: DeletionAuditLogger for audit trail.
        """
        self._store = store
        self._audit = audit_logger

    def secure_delete_file(self, file_path: Path) -> None:
        """Securely delete a file with 3-pass random overwrite.

        Per DoD 5220.22-M style secure deletion:
        1. Overwrite with random bytes
        2. Repeat 3 times
        3. Unlink file
        4. Verify deletion

        Args:
            file_path: Path to file to securely delete.

        Raises:
            DeletionError: If deletion verification fails.
        """
        if not file_path.exists():
            logger.debug(f"File does not exist, skipping: {file_path}")
            return

        file_size = file_path.stat().st_size

        # 3-pass random overwrite
        for pass_num in range(SECURE_DELETE_PASSES):
            logger.debug(f"Secure delete pass {pass_num + 1}/{SECURE_DELETE_PASSES}: {file_path}")
            with open(file_path, "r+b") as f:
                # Use cryptographic random bytes
                random_data = secrets.token_bytes(file_size)
                f.write(random_data)
                f.flush()
                os.fsync(f.fileno())

        # Delete the file
        file_path.unlink()

        # Verify deletion
        if file_path.exists():
            raise DeletionError(
                f"File still exists after deletion: {file_path}",
                reason="verification_failed",
            )

        logger.info(f"Securely deleted file: {file_path}")

    def delete_item(self, item_id: str) -> None:
        """Delete a single item securely.

        Process:
        1. Get item from store
        2. Secure delete the encrypted file
        3. Remove from manifest
        4. Remove from cache
        5. Log to audit trail

        Args:
            item_id: ID of the item to delete.

        Raises:
            KeyError: If item_id not found.
            DeletionError: If secure deletion fails.
        """
        item = self._store.get_item(item_id)
        if item is None:
            raise KeyError(f"Item not found: {item_id}")

        # Secure delete the encrypted file
        encrypted_path = self._store._evidence_path / item.encrypted_path
        self.secure_delete_file(encrypted_path)

        # Remove from manifest (atomic update)
        self._store._remove_from_manifest(item_id)

        # Remove from in-memory cache
        if item_id in self._store._items:
            del self._store._items[item_id]

        # Log to audit trail
        self._audit.log_deletion(
            item_id,
            item.filename,
            item.target,
            item.size_bytes,
        )

        logger.info(f"Deleted item: {item_id} ({item.filename})")

    def delete_items(
        self,
        item_ids: list[str],
        continue_on_error: bool = False,
    ) -> DeletionResult:
        """Delete multiple items securely.

        Args:
            item_ids: List of item IDs to delete.
            continue_on_error: If True, continue deleting after failures.

        Returns:
            DeletionResult with success/failure details.
        """
        deleted_ids: list[str] = []
        failed: list[tuple[str, str]] = []

        for item_id in item_ids:
            try:
                self.delete_item(item_id)
                deleted_ids.append(item_id)
            except (DeletionError, KeyError) as e:
                error_msg = str(e)
                failed.append((item_id, error_msg))
                logger.warning(f"Failed to delete {item_id}: {error_msg}")

                if not continue_on_error:
                    break

        # Log bulk deletion to audit if any succeeded
        if deleted_ids:
            self._audit.log_bulk_deletion(
                deleted_ids,
                len(deleted_ids),
                len(failed),
            )

        return DeletionResult(
            total_items=len(item_ids),
            deleted_items=len(deleted_ids),
            failed_items=failed,
        )
