"""Data Export Module.

Story 11.3: Data Export from TUI

Provides export functionality for exfiltrated data:
- Single item export with decryption
- Archive export with manifest.json
- Progress tracking for large exports
- Cancellation support
- Atomic writes with cleanup on failure

Security Notes:
- Uses SecureBuffer for decrypted content handling
- Atomic write pattern prevents partial corrupt files
- All exports logged to audit trail
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from cyberred.core.exceptions import ExportError
from cyberred.storage.evidence import SecureBuffer

if TYPE_CHECKING:
    from cyberred.storage.evidence import ExfiltratedDataItem, ExfiltratedDataStore

logger = logging.getLogger(__name__)


@dataclass
class ExportProgress:
    """Tracks export progress for UI updates.

    Attributes:
        total_items: Total number of items to export.
        completed_items: Number of items completed.
        total_bytes: Total bytes to export.
        completed_bytes: Bytes exported so far.
        current_item: Name of current item being exported.
    """

    total_items: int
    completed_items: int
    total_bytes: int
    completed_bytes: int
    current_item: str = ""

    @property
    def percentage(self) -> float:
        """Calculate completion percentage.

        Returns:
            Percentage complete (0-100). Returns 100 if no items.
        """
        if self.total_items == 0:
            return 100.0
        return (self.completed_items / self.total_items) * 100

    @property
    def is_large_export(self) -> bool:
        """Check if this is a large export (>10 items or >10MB).

        Returns:
            True if export should show progress bar.
        """
        return self.total_items > 10 or self.total_bytes > 10 * 1024 * 1024


class CancellationToken:
    """Cooperative cancellation for export operations.

    Usage:
        token = CancellationToken()
        # In another thread/task:
        token.cancel()
        # In export code:
        if token.is_cancelled:
            raise ExportError("Export cancelled")
    """

    def __init__(self) -> None:
        """Initialize CancellationToken in non-cancelled state."""
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation."""
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation was requested.

        Returns:
            True if cancel() has been called.
        """
        return self._cancelled


class DataExporter:
    """Handles export of exfiltrated data items.

    Story 11.3: Data Export from TUI.

    Provides methods to export single items or archives of multiple items.
    All exports use atomic writes and log to audit trail.

    Attributes:
        DEFAULT_EXPORT_DIR: Default base directory for exports.
    """

    DEFAULT_EXPORT_DIR = Path.home() / "cyber-red-exports"

    def __init__(
        self,
        store: ExfiltratedDataStore,
        audit_logger: Any,
        engagement_name: str,
    ) -> None:
        """Initialize DataExporter.

        Args:
            store: ExfiltratedDataStore instance for accessing items.
            audit_logger: AuditLogger instance for logging exports.
            engagement_name: Name of current engagement.
        """
        self._store = store
        self._audit = audit_logger
        self._engagement_name = engagement_name

    def get_default_export_path(self, item: ExfiltratedDataItem) -> Path:
        """Get default export path for an item.

        Args:
            item: The item to get path for.

        Returns:
            Path: ~/cyber-red-exports/{engagement_name}/{filename}
        """
        return self.DEFAULT_EXPORT_DIR / self._engagement_name / item.filename

    def export_single_item(
        self,
        item_id: str,
        destination: Path,
        progress_callback: Callable[[ExportProgress], None] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> Path:
        """Export single item to destination path.

        Decrypts item content and writes to specified path using atomic
        write pattern (write to temp, rename on success).

        Args:
            item_id: ID of item to export.
            destination: Target file path.
            progress_callback: Optional callback for progress updates.
            cancellation_token: Optional token for cancellation.

        Returns:
            Path to exported file.

        Raises:
            ExportError: On permission denied, disk full, or other failure.
            KeyError: If item_id not found.
        """
        # Check cancellation first
        if cancellation_token and cancellation_token.is_cancelled:
            raise ExportError("Export cancelled")

        item = self._store.get_item(item_id)
        if item is None:
            raise KeyError(f"Item not found: {item_id}")

        # Ensure parent directory exists
        destination.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: temp file then rename
        temp_path = destination.with_suffix(destination.suffix + ".tmp")

        try:
            # Get decrypted content
            content = self._store.get_item_content(item_id)

            # Check cancellation again
            if cancellation_token and cancellation_token.is_cancelled:
                raise ExportError("Export cancelled")

            # Write to temp file using SecureBuffer
            with SecureBuffer(content) as buffer:
                temp_path.write_bytes(bytes(buffer))

            # Rename to final destination (atomic on same filesystem)
            shutil.move(str(temp_path), str(destination))

            # Log to audit trail
            self._audit.log_export(
                item_id=item_id,
                filename=item.filename,
                destination=str(destination),
            )

            logger.info(f"Exported item {item_id} to {destination}")
            return destination

        except PermissionError as e:
            self._cleanup_temp(temp_path)
            raise ExportError(
                f"Permission denied: {destination}",
                destination=str(destination),
            ) from e
        except OSError as e:
            self._cleanup_temp(temp_path)
            if e.errno == 28 or "No space left" in str(e):
                raise ExportError(
                    f"Disk full: cannot write to {destination}",
                    destination=str(destination),
                ) from e
            raise ExportError(
                f"Export failed: {e}",
                destination=str(destination),
            ) from e
        except ExportError:
            self._cleanup_temp(temp_path)
            raise
        except Exception as e:
            self._cleanup_temp(temp_path)
            raise ExportError(
                f"Export failed: {e}",
                destination=str(destination),
            ) from e

    def export_archive(
        self,
        item_ids: list[str],
        destination: Path,
        progress_callback: Callable[[ExportProgress], None] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> Path:
        """Export multiple items as ZIP archive with manifest.

        Creates a ZIP archive containing all items with their original
        filenames (handling duplicates by appending suffix) and a
        manifest.json with metadata.

        Args:
            item_ids: List of item IDs to export.
            destination: Target ZIP file path.
            progress_callback: Optional callback for progress updates.
            cancellation_token: Optional token for cancellation.

        Returns:
            Path to exported archive.

        Raises:
            ExportError: On failure.
        """
        # Collect items
        items = []
        for item_id in item_ids:
            item = self._store.get_item(item_id)
            if item is not None:
                items.append(item)

        total_bytes = sum(i.size_bytes for i in items)
        progress = ExportProgress(
            total_items=len(items),
            completed_items=0,
            total_bytes=total_bytes,
            completed_bytes=0,
        )

        # Ensure parent directory exists
        destination.parent.mkdir(parents=True, exist_ok=True)

        temp_path = destination.with_suffix(".zip.tmp")
        used_names: dict[str, int] = {}  # Track duplicate filenames

        try:
            with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                manifest_items = []

                for item in items:
                    if cancellation_token and cancellation_token.is_cancelled:
                        raise ExportError("Export cancelled")

                    progress.current_item = item.filename
                    if progress_callback:
                        progress_callback(progress)

                    # Handle duplicate filenames
                    arc_name = item.filename
                    if arc_name in used_names:
                        used_names[arc_name] += 1
                        base = arc_name
                        ext = ""
                        if "." in arc_name:
                            dot_idx = arc_name.rfind(".")
                            base = arc_name[:dot_idx]
                            ext = arc_name[dot_idx:]
                        arc_name = f"{base}_{used_names[item.filename]}{ext}"
                    else:
                        used_names[arc_name] = 0

                    # Get decrypted content and add to archive
                    content = self._store.get_item_content(item.id)
                    with SecureBuffer(content) as buffer:
                        zf.writestr(arc_name, bytes(buffer))

                    # Build manifest entry
                    item_dict = item.to_dict()
                    item_dict["archive_name"] = arc_name
                    manifest_items.append(item_dict)

                    progress.completed_items += 1
                    progress.completed_bytes += item.size_bytes

                # Write manifest.json
                manifest = {
                    "schema_version": "1.0.0",
                    "engagement_name": self._engagement_name,
                    "export_timestamp": datetime.now(timezone.utc).isoformat(),
                    "total_items": len(manifest_items),
                    "total_bytes": total_bytes,
                    "items": manifest_items,
                }
                zf.writestr("manifest.json", json.dumps(manifest, indent=2))

            # Rename to final destination
            shutil.move(str(temp_path), str(destination))

            # Log to audit trail
            self._audit.log_archive_export(
                item_ids=item_ids,
                destination=str(destination),
                item_count=len(items),
            )

            logger.info(f"Exported archive with {len(items)} items to {destination}")
            return destination

        except ExportError:
            self._cleanup_temp(temp_path)
            raise
        except Exception as e:
            self._cleanup_temp(temp_path)
            raise ExportError(
                f"Archive export failed: {e}",
                destination=str(destination),
            ) from e

    def _cleanup_temp(self, temp_path: Path) -> None:
        """Remove temporary file if it exists.

        Args:
            temp_path: Path to temporary file.
        """
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass  # Best effort cleanup
