"""Unit tests for TUI utilities.

Tests for shared utility functions used across TUI components.
"""

from __future__ import annotations

import pytest

from cyberred.tui.utils import format_size


class TestFormatSize:
    """Tests for format_size utility function."""

    def test_zero_bytes(self) -> None:
        """Test formatting zero bytes."""
        assert format_size(0) == "0 B"

    def test_bytes_under_1kb(self) -> None:
        """Test formatting bytes under 1 KB."""
        assert format_size(1) == "1 B"
        assert format_size(100) == "100 B"
        assert format_size(512) == "512 B"
        assert format_size(1023) == "1023 B"

    def test_exactly_1kb(self) -> None:
        """Test formatting exactly 1 KB."""
        assert format_size(1024) == "1.0 KB"

    def test_kilobytes(self) -> None:
        """Test formatting kilobytes."""
        assert format_size(1536) == "1.5 KB"
        assert format_size(2048) == "2.0 KB"
        assert format_size(10240) == "10.0 KB"
        assert format_size(1024 * 500) == "500.0 KB"

    def test_exactly_1mb(self) -> None:
        """Test formatting exactly 1 MB."""
        assert format_size(1024 * 1024) == "1.0 MB"

    def test_megabytes(self) -> None:
        """Test formatting megabytes."""
        assert format_size(int(1024 * 1024 * 1.5)) == "1.5 MB"
        assert format_size(1024 * 1024 * 10) == "10.0 MB"
        assert format_size(1024 * 1024 * 500) == "500.0 MB"

    def test_exactly_1gb(self) -> None:
        """Test formatting exactly 1 GB."""
        assert format_size(1024 * 1024 * 1024) == "1.0 GB"

    def test_gigabytes(self) -> None:
        """Test formatting gigabytes."""
        assert format_size(int(1024 * 1024 * 1024 * 1.5)) == "1.5 GB"
        assert format_size(1024 * 1024 * 1024 * 10) == "10.0 GB"

    def test_terabytes(self) -> None:
        """Test formatting terabytes."""
        assert format_size(1024 * 1024 * 1024 * 1024) == "1.0 TB"
        assert format_size(int(1024 * 1024 * 1024 * 1024 * 2.5)) == "2.5 TB"

    def test_large_values(self) -> None:
        """Test formatting very large values stays at TB."""
        # 10 TB
        assert format_size(1024 * 1024 * 1024 * 1024 * 10) == "10.0 TB"
        # 1000 TB
        assert format_size(1024 * 1024 * 1024 * 1024 * 1000) == "1000.0 TB"

    def test_precision(self) -> None:
        """Test that decimal precision is correct (1 decimal place)."""
        # 1.23 KB should round to 1.2 KB
        assert format_size(1260) == "1.2 KB"
        # 1.25 KB should round to 1.2 KB (banker's rounding)
        assert format_size(1280) == "1.2 KB"
        # 1.26 KB should round to 1.3 KB
        assert format_size(1290) == "1.3 KB"
