"""Keystore module for secure key derivation and encryption.

Provides PBKDF2-HMAC-SHA256 key derivation and AES-256-GCM authenticated
encryption per NFR14, NFR15-16 security requirements.

Security Notes:
- Keys are NEVER stored in plaintext
- Passwords are discarded immediately after key derivation
- Uses cryptographically secure random number generation
- AES-256-GCM provides authenticated encryption (confidentiality + integrity)

Usage:
    from cyberred.core.keystore import Keystore, derive_key, encrypt, decrypt

    # Low-level functions
    salt = generate_salt()
    key = derive_key("password", salt)
    ciphertext, nonce = encrypt(b"secret", key)
    plaintext = decrypt(ciphertext, key, nonce)

    # High-level class
    ks = Keystore.from_password("password", salt)
    encrypted = ks.encrypt(b"secret")
    decrypted = ks.decrypt(encrypted["ciphertext"], encrypted["nonce"])
"""

import os
from typing import TypedDict, Tuple

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from cyberred.core.exceptions import DecryptionError

# Constants
DEFAULT_ITERATIONS = 600_000  # NIST recommended minimum for PBKDF2
KEY_LENGTH = 32  # 256 bits for AES-256
SALT_LENGTH = 16  # 128 bits minimum
NONCE_LENGTH = 12  # 96 bits for GCM


class EncryptionResult(TypedDict):
    """Result of encryption operation."""

    ciphertext: bytes
    nonce: bytes


def generate_salt(length: int = SALT_LENGTH) -> bytes:
    """Generate cryptographically secure random salt.

    Args:
        length: Salt length in bytes. Default is 16 (128 bits).

    Returns:
        Cryptographically secure random bytes.
    """
    return os.urandom(length)


def derive_key(
    password: str,
    salt: bytes,
    iterations: int = DEFAULT_ITERATIONS,
) -> bytes:
    """Derive AES-256 key from password using PBKDF2-HMAC-SHA256.

    Args:
        password: The master password for key derivation.
        salt: Random salt bytes (minimum 16 bytes recommended).
        iterations: PBKDF2 iteration count. Default is 100,000.

    Returns:
        32-byte key suitable for AES-256 encryption.

    Raises:
        ValueError: If password is empty or salt is empty.
    """
    if not password:
        raise ValueError("Password cannot be empty")
    if not salt:
        raise ValueError("Salt cannot be empty")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt(plaintext: bytes, key: bytes) -> Tuple[bytes, bytes]:
    """Encrypt data using AES-256-GCM authenticated encryption.

    Args:
        plaintext: Data to encrypt (can be any size, including empty).
        key: 32-byte encryption key.

    Returns:
        Tuple of (ciphertext, nonce) where ciphertext includes auth tag.
    """
    nonce = os.urandom(NONCE_LENGTH)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return ciphertext, nonce


def decrypt(ciphertext: bytes, key: bytes, nonce: bytes) -> bytes:
    """Decrypt data using AES-256-GCM authenticated encryption.

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
        # AESGCM.decrypt raises InvalidTag if authentication fails
        return aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag as e:
        raise DecryptionError("Decryption failed: Invalid tag (wrong key or tampered data)") from e
    except ValueError as e:
        # Raises ValueError if nonce is wrong length
        raise DecryptionError(f"Decryption failed: {e}") from e
    except Exception as e:
        # Catch-all for other unexpected crypto errors
        raise DecryptionError(f"Decryption failed: Unexpected error - {e}") from e


class Keystore:
    """High-level keystore for secure encryption operations.

    Security properties:
    - Password is NEVER stored
    - Derived key is stored in memory (protected attribute) while instance is alive
    - Provides convenient encrypt/decrypt methods
    - Supports manual clearing of key from memory

    Usage:
        ks = Keystore.from_password("secret", salt)
        encrypted = ks.encrypt(b"data")
        plaintext = ks.decrypt(encrypted["ciphertext"], encrypted["nonce"])
        ks.clear()  # Clear key from memory
    """

    def __init__(self, key: bytes) -> None:
        """Initialize Keystore with a derived key.

        Args:
            key: 32-byte AES-256 encryption key.

        Note:
            Use Keystore.from_password() classmethod for typical usage.
            Direct initialization is for advanced use cases.
        """
        self._key: bytes | None = key

    @classmethod
    def from_password(cls, password: str, salt: bytes) -> "Keystore":
        """Create Keystore by deriving key from password.

        Args:
            password: Master password for key derivation.
            salt: Random salt bytes.

        Returns:
            Keystore instance ready for encryption/decryption.
        """
        key = derive_key(password, salt)
        return cls(key)

    def encrypt(self, plaintext: bytes) -> EncryptionResult:
        """Encrypt data and return result as dict.

        Args:
            plaintext: Data to encrypt.

        Returns:
            EncryptionResult dict with 'ciphertext' and 'nonce' keys.

        Raises:
            RuntimeError: If keystore has been cleared/closed.
        """
        if self._key is None:
            raise RuntimeError("Keystore is closed/cleared")
            
        ciphertext, nonce = encrypt(plaintext, self._key)
        return {
            "ciphertext": ciphertext,
            "nonce": nonce,
        }

    def decrypt(self, ciphertext: bytes, nonce: bytes) -> bytes:
        """Decrypt data.

        Args:
            ciphertext: Encrypted data (includes auth tag).
            nonce: Nonce used during encryption.

        Returns:
            Original plaintext bytes.

        Raises:
            DecryptionError: If decryption fails.
            RuntimeError: If keystore has been cleared/closed.
        """
        if self._key is None:
            raise RuntimeError("Keystore is closed/cleared")
            
        return decrypt(ciphertext, self._key, nonce)

    def clear(self) -> None:
        """Clear the key from memory.
        
        Overwrites the key reference. Python's garbage collector 
        handles the actual memory cleanup, but this prevents 
        accidental access via the instance.
        """
        self._key = None
