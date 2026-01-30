"""TUI Utility Functions.

Shared utilities for TUI widgets and screens.

Components:
    - format_size: Human-readable file size formatting
"""

from __future__ import annotations


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable form.

    Converts bytes to appropriate unit (B, KB, MB, GB, TB).

    Args:
        size_bytes: Size in bytes.

    Returns:
        Human-readable size string (e.g., "1.5 MB").

    Examples:
        >>> format_size(0)
        '0 B'
        >>> format_size(1024)
        '1.0 KB'
        >>> format_size(1536)
        '1.5 KB'
        >>> format_size(1048576)
        '1.0 MB'
    """
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} B"
    return f"{size:.1f} {units[unit_index]}"
