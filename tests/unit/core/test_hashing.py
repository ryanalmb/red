"""Unit Tests for core/hashing.py module.

Tests for SHA-256 hash calculation utilities used for checkpoint
integrity verification and scope file hashing.
"""

import hashlib
import pytest
from pathlib import Path

from cyberred.core.hashing import calculate_file_hash, calculate_bytes_hash


class TestCalculateBytesHash:
    """Tests for calculate_bytes_hash function."""

    def test_empty_bytes_hash(self):
        """Verify hash of empty bytes matches expected SHA-256."""
        expected = hashlib.sha256(b"").hexdigest()
        result = calculate_bytes_hash(b"")
        assert result == expected

    def test_simple_bytes_hash(self):
        """Verify hash of simple bytes."""
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        result = calculate_bytes_hash(data)
        assert result == expected

    def test_unicode_encoded_bytes(self):
        """Verify hash of unicode content as bytes."""
        data = "こんにちは".encode("utf-8")
        expected = hashlib.sha256(data).hexdigest()
        result = calculate_bytes_hash(data)
        assert result == expected

    def test_large_bytes_hash(self):
        """Verify hash of large data."""
        data = b"x" * (1024 * 1024)  # 1MB
        expected = hashlib.sha256(data).hexdigest()
        result = calculate_bytes_hash(data)
        assert result == expected

    def test_md5_algorithm(self):
        """Verify MD5 algorithm support."""
        data = b"test data"
        expected = hashlib.md5(data).hexdigest()
        result = calculate_bytes_hash(data, algorithm="md5")
        assert result == expected

    def test_sha512_algorithm(self):
        """Verify SHA-512 algorithm support."""
        data = b"test data"
        expected = hashlib.sha512(data).hexdigest()
        result = calculate_bytes_hash(data, algorithm="sha512")
        assert result == expected

    def test_invalid_algorithm_raises(self):
        """Verify invalid algorithm raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported hash algorithm"):
            calculate_bytes_hash(b"data", algorithm="invalid_algo")


class TestCalculateFileHash:
    """Tests for calculate_file_hash function."""

    def test_simple_file_hash(self, tmp_path: Path):
        """Verify hash of simple file."""
        test_file = tmp_path / "test.txt"
        content = b"hello world"
        test_file.write_bytes(content)
        
        expected = hashlib.sha256(content).hexdigest()
        result = calculate_file_hash(test_file)
        assert result == expected

    def test_empty_file_hash(self, tmp_path: Path):
        """Verify hash of empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")
        
        expected = hashlib.sha256(b"").hexdigest()
        result = calculate_file_hash(test_file)
        assert result == expected

    def test_binary_file_hash(self, tmp_path: Path):
        """Verify hash of binary file with null bytes."""
        test_file = tmp_path / "binary.bin"
        content = b"\x00\x01\x02\xff\xfe\xfd"
        test_file.write_bytes(content)
        
        expected = hashlib.sha256(content).hexdigest()
        result = calculate_file_hash(test_file)
        assert result == expected

    def test_large_file_hash(self, tmp_path: Path):
        """Verify hash of large file (streaming)."""
        test_file = tmp_path / "large.bin"
        content = b"x" * (1024 * 1024)  # 1MB
        test_file.write_bytes(content)
        
        expected = hashlib.sha256(content).hexdigest()
        result = calculate_file_hash(test_file)
        assert result == expected

    def test_file_not_found_raises(self, tmp_path: Path):
        """Verify FileNotFoundError for missing file."""
        missing_file = tmp_path / "does_not_exist.txt"
        with pytest.raises(FileNotFoundError):
            calculate_file_hash(missing_file)

    def test_md5_algorithm_file(self, tmp_path: Path):
        """Verify MD5 algorithm support for files."""
        test_file = tmp_path / "test.txt"
        content = b"test data"
        test_file.write_bytes(content)
        
        expected = hashlib.md5(content).hexdigest()
        result = calculate_file_hash(test_file, algorithm="md5")
        assert result == expected

    def test_sha512_algorithm_file(self, tmp_path: Path):
        """Verify SHA-512 algorithm support for files."""
        test_file = tmp_path / "test.txt"
        content = b"test data"
        test_file.write_bytes(content)
        
        expected = hashlib.sha512(content).hexdigest()
        result = calculate_file_hash(test_file, algorithm="sha512")
        assert result == expected

    def test_invalid_algorithm_file_raises(self, tmp_path: Path):
        """Verify invalid algorithm raises ValueError."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"data")
        
        with pytest.raises(ValueError, match="Unsupported hash algorithm"):
            calculate_file_hash(test_file, algorithm="invalid_algo")

    def test_accepts_string_path(self, tmp_path: Path):
        """Verify string paths are accepted."""
        test_file = tmp_path / "test.txt"
        content = b"hello"
        test_file.write_bytes(content)
        
        expected = hashlib.sha256(content).hexdigest()
        result = calculate_file_hash(str(test_file))
        assert result == expected
