"""Hashing utilities for Cyber-Red.

Provides standardized hash calculation for files and byte data.
Used for checkpoint integrity verification and scope file hashing.

Usage:
    from cyberred.core.hashing import calculate_file_hash, calculate_bytes_hash
    
    # Hash a file (default SHA-256)
    file_hash = calculate_file_hash(Path("checkpoint.sqlite"))
    
    # Hash bytes
    data_hash = calculate_bytes_hash(b"some data")
    
    # Use different algorithm
    md5_hash = calculate_bytes_hash(b"data", algorithm="md5")
"""

import hashlib
from pathlib import Path
from typing import Union


# Supported hash algorithms
SUPPORTED_ALGORITHMS = frozenset({"sha256", "sha512", "sha384", "md5", "sha1"})

# Default buffer size for file reading (64KB)
FILE_BUFFER_SIZE = 65536


def calculate_bytes_hash(
    data: bytes,
    algorithm: str = "sha256",
) -> str:
    """Calculate hash of bytes data.
    
    Args:
        data: Bytes to hash.
        algorithm: Hash algorithm name. Default is "sha256".
                   Supported: sha256, sha512, sha384, md5, sha1.
    
    Returns:
        Hexadecimal hash string.
    
    Raises:
        ValueError: If algorithm is not supported.
    
    Examples:
        >>> calculate_bytes_hash(b"hello")
        '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
    """
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(
            f"Unsupported hash algorithm: '{algorithm}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_ALGORITHMS))}"
        )
    
    hasher = hashlib.new(algorithm)
    hasher.update(data)
    return hasher.hexdigest()


def calculate_file_hash(
    path: Union[str, Path],
    algorithm: str = "sha256",
) -> str:
    """Calculate hash of file contents.
    
    Streams file data in chunks for memory efficiency with large files.
    
    Args:
        path: Path to file (string or Path object).
        algorithm: Hash algorithm name. Default is "sha256".
                   Supported: sha256, sha512, sha384, md5, sha1.
    
    Returns:
        Hexadecimal hash string.
    
    Raises:
        ValueError: If algorithm is not supported.
        FileNotFoundError: If file does not exist.
    
    Examples:
        >>> calculate_file_hash(Path("/path/to/file.txt"))
        '...'
    """
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(
            f"Unsupported hash algorithm: '{algorithm}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_ALGORITHMS))}"
        )
    
    file_path = Path(path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    hasher = hashlib.new(algorithm)
    
    with file_path.open("rb") as f:
        while chunk := f.read(FILE_BUFFER_SIZE):
            hasher.update(chunk)
    
    return hasher.hexdigest()
