"""Unit tests for keystore module (PBKDF2 key derivation and AES-256-GCM encryption).

This test file follows RED-GREEN-REFACTOR TDD methodology.
These tests are written FIRST (RED phase) to define expected behavior.

Tests cover:
- Key derivation via PBKDF2-HMAC-SHA256
- AES-256-GCM authenticated encryption/decryption
- Keystore class security properties
"""

import os

import pytest
from unittest.mock import patch, MagicMock


class TestDeriveKey:
    """Tests for derive_key() function - PBKDF2-HMAC-SHA256 key derivation."""

    def test_derive_key_returns_32_bytes_for_aes256(self) -> None:
        """derive_key should return 32-byte key suitable for AES-256."""
        from cyberred.core.keystore import derive_key

        password = "test-password-123"
        salt = os.urandom(16)

        key = derive_key(password, salt)

        assert isinstance(key, bytes)
        assert len(key) == 32  # 256 bits for AES-256

    def test_derive_key_uses_pbkdf2_hmac_sha256(self) -> None:
        """derive_key should use PBKDF2-HMAC-SHA256 algorithm."""
        from cyberred.core.keystore import derive_key

        password = "test-password"
        salt = b"fixed-salt-16-b"  # 16 bytes

        # Run twice with same inputs - should be deterministic
        key1 = derive_key(password, salt)
        key2 = derive_key(password, salt)

        assert key1 == key2  # PBKDF2 is deterministic

    def test_derive_key_with_custom_iterations(self) -> None:
        """derive_key should accept custom iteration count."""
        from cyberred.core.keystore import derive_key

        password = "test-password"
        salt = os.urandom(16)

        # Different iteration counts should produce different keys
        key_10k = derive_key(password, salt, iterations=10_000)
        key_20k = derive_key(password, salt, iterations=20_000)

        assert key_10k != key_20k  # Different iterations = different keys
        assert len(key_10k) == 32
        assert len(key_20k) == 32

    @patch('cyberred.core.keystore.PBKDF2HMAC')
    def test_derive_key_default_iterations_is_600000(self, mock_pbkdf2):
        """Test that default iterations is 600,000 (NIST recommendation)."""
        from cyberred.core.keystore import derive_key

        derive_key("password", b"salt")
        
        mock_pbkdf2.assert_called_once()
        _, kwargs = mock_pbkdf2.call_args
        assert kwargs["iterations"] == 600000

    def test_derive_key_different_passwords_yield_different_keys(self) -> None:
        """Different passwords should yield different derived keys."""
        from cyberred.core.keystore import derive_key

        salt = os.urandom(16)

        key1 = derive_key("password-one", salt)
        key2 = derive_key("password-two", salt)

        assert key1 != key2

    def test_derive_key_same_password_different_salt_yields_different_keys(self) -> None:
        """Same password with different salts should yield different keys."""
        from cyberred.core.keystore import derive_key

        password = "same-password"

        key1 = derive_key(password, os.urandom(16))
        key2 = derive_key(password, os.urandom(16))

        assert key1 != key2

    def test_derive_key_empty_password_raises_error(self) -> None:
        """Empty password should raise ValueError."""
        from cyberred.core.keystore import derive_key

        with pytest.raises(ValueError, match="[Pp]assword"):
            derive_key("", os.urandom(16))

    def test_derive_key_empty_salt_raises_error(self) -> None:
        """Empty salt should raise ValueError."""
        from cyberred.core.keystore import derive_key

        with pytest.raises(ValueError, match="[Ss]alt"):
            derive_key("valid-password", b"")


class TestGenerateSalt:
    """Tests for generate_salt() function."""

    def test_generate_salt_returns_16_bytes_by_default(self) -> None:
        """generate_salt should return 16 bytes by default."""
        from cyberred.core.keystore import generate_salt

        salt = generate_salt()

        assert isinstance(salt, bytes)
        assert len(salt) == 16

    def test_generate_salt_custom_length(self) -> None:
        """generate_salt should accept custom length."""
        from cyberred.core.keystore import generate_salt

        salt_32 = generate_salt(32)
        salt_64 = generate_salt(64)

        assert len(salt_32) == 32
        assert len(salt_64) == 64

    def test_generate_salt_is_cryptographically_random(self) -> None:
        """generate_salt should produce unique values (cryptographically random)."""
        from cyberred.core.keystore import generate_salt

        salts = [generate_salt() for _ in range(100)]
        unique_salts = set(salts)

        # All 100 should be unique (probability of collision is negligible)
        assert len(unique_salts) == 100


class TestEncryptDecrypt:
    """Tests for encrypt() and decrypt() functions - AES-256-GCM."""

    def test_encrypt_returns_ciphertext_and_nonce(self) -> None:
        """encrypt should return tuple of (ciphertext, nonce)."""
        from cyberred.core.keystore import derive_key, encrypt

        key = derive_key("test-password", os.urandom(16))
        plaintext = b"Hello, World!"

        result = encrypt(plaintext, key)

        assert isinstance(result, tuple)
        assert len(result) == 2
        ciphertext, nonce = result
        assert isinstance(ciphertext, bytes)
        assert isinstance(nonce, bytes)
        assert len(nonce) == 12  # GCM standard nonce size

    def test_decrypt_returns_original_plaintext(self) -> None:
        """decrypt should return the original plaintext."""
        from cyberred.core.keystore import decrypt, derive_key, encrypt

        key = derive_key("test-password", os.urandom(16))
        original = b"Secret message for testing!"

        ciphertext, nonce = encrypt(original, key)
        decrypted = decrypt(ciphertext, key, nonce)

        assert decrypted == original

    def test_encrypt_decrypt_roundtrip_various_sizes(self) -> None:
        """encrypt/decrypt should work for various data sizes."""
        from cyberred.core.keystore import decrypt, derive_key, encrypt

        key = derive_key("test-password", os.urandom(16))

        test_sizes = [0, 1, 16, 100, 1000, 10000, 100000]  # Various sizes
        for size in test_sizes:
            plaintext = os.urandom(size)
            ciphertext, nonce = encrypt(plaintext, key)
            decrypted = decrypt(ciphertext, key, nonce)
            assert decrypted == plaintext, f"Failed for size {size}"

    def test_decrypt_with_wrong_key_raises_error(self) -> None:
        """decrypt with wrong key should raise DecryptionError."""
        from cyberred.core.exceptions import DecryptionError
        from cyberred.core.keystore import decrypt, derive_key, encrypt

        key1 = derive_key("password-one", os.urandom(16))
        key2 = derive_key("password-two", os.urandom(16))
        plaintext = b"Secret data"

        ciphertext, nonce = encrypt(plaintext, key1)

        with pytest.raises(DecryptionError):
            decrypt(ciphertext, key2, nonce)

    def test_decrypt_with_tampered_ciphertext_raises_error(self) -> None:
        """decrypt with tampered ciphertext should raise DecryptionError."""
        from cyberred.core.exceptions import DecryptionError
        from cyberred.core.keystore import decrypt, derive_key, encrypt

        key = derive_key("test-password", os.urandom(16))
        plaintext = b"Original message"

        ciphertext, nonce = encrypt(plaintext, key)

        # Tamper with ciphertext
        tampered = bytearray(ciphertext)
        tampered[0] ^= 0xFF  # Flip bits in first byte
        tampered = bytes(tampered)

        with pytest.raises(DecryptionError):
            decrypt(tampered, key, nonce)

    def test_encrypt_uses_aes256_gcm_authenticated_encryption(self) -> None:
        """encrypt should use AES-256-GCM (authenticated encryption)."""
        from cyberred.core.keystore import derive_key, encrypt

        key = derive_key("test-password", os.urandom(16))
        plaintext = b"Test data"

        ciphertext, nonce = encrypt(plaintext, key)

        # GCM adds 16-byte auth tag to ciphertext
        # ciphertext length = plaintext length + 16 (auth tag)
        assert len(ciphertext) == len(plaintext) + 16


class TestKeystoreClass:
    """Tests for Keystore class - high-level encryption operations."""


    def test_keystore_never_stores_raw_password(self) -> None:
        """Keystore class should never store the raw password."""
        from cyberred.core.keystore import Keystore

        password = "secret-password-123"
        salt = os.urandom(16)

        ks = Keystore.from_password(password, salt)

        # Check no attribute contains the password
        for attr_name in dir(ks):
            if not attr_name.startswith("_"):
                continue
            attr_value = getattr(ks, attr_name, None)
            if isinstance(attr_value, (str, bytes)):
                if isinstance(attr_value, str):
                    assert password not in attr_value
                else:
                    assert password.encode() not in attr_value

    def test_keystore_class_never_stores_derived_key_in_plaintext_attributes(self) -> None:
        """Test Keystore never stores derived key in accessible public attributes."""
        from cyberred.core.keystore import Keystore
        
        salt = os.urandom(16)
        ks = Keystore.from_password("secret", salt)
        
        # Verify key is stored in private attribute _key
        assert hasattr(ks, "_key")
        
        # Verify NO public attribute has the key
        for attr in dir(ks):
            if not attr.startswith("_"):
                val = getattr(ks, attr)
                if isinstance(val, bytes):
                    assert val != ks._key

    def test_keystore_memory_is_properly_cleaned(self) -> None:
        """Test Keystore.clear() removes key from memory reference."""
        from cyberred.core.keystore import Keystore
        
        ks = Keystore.from_password("secret", os.urandom(16))
        assert ks._key is not None
        
        # Verify it works before clear
        enc = ks.encrypt(b"test")
        assert ks.decrypt(enc["ciphertext"], enc["nonce"]) == b"test"
        
        # Clear it
        ks.clear()
        
        # Verify key is gone
        assert ks._key is None
        
        # Verify operations fail securely
        with pytest.raises(RuntimeError, match="Keystore is closed/cleared"):
            ks.encrypt(b"test")
            
        with pytest.raises(RuntimeError, match="Keystore is closed/cleared"):
            ks.decrypt(enc["ciphertext"], enc["nonce"])

    def test_keystore_encrypt_returns_dict_with_ciphertext_and_nonce(self) -> None:
        """Keystore.encrypt should return dict with ciphertext and nonce."""
        from cyberred.core.keystore import Keystore

        ks = Keystore.from_password("test-password", os.urandom(16))
        plaintext = b"Test message"

        result = ks.encrypt(plaintext)

        assert isinstance(result, dict)
        assert "ciphertext" in result
        assert "nonce" in result
        assert isinstance(result["ciphertext"], bytes)
        assert isinstance(result["nonce"], bytes)

    def test_keystore_decrypt_returns_original_plaintext(self) -> None:
        """Keystore.decrypt should return the original plaintext."""
        from cyberred.core.keystore import Keystore

        ks = Keystore.from_password("test-password", os.urandom(16))
        original = b"Original secret message"

        encrypted = ks.encrypt(original)
        decrypted = ks.decrypt(encrypted["ciphertext"], encrypted["nonce"])

        assert decrypted == original

    def test_keystore_from_password_classmethod(self) -> None:
        """Keystore.from_password should create Keystore with derived key."""
        from cyberred.core.keystore import Keystore

        password = "test-password"
        salt = os.urandom(16)

        ks = Keystore.from_password(password, salt)

        assert isinstance(ks, Keystore)
        # Should be able to encrypt/decrypt
        encrypted = ks.encrypt(b"test")
        assert ks.decrypt(encrypted["ciphertext"], encrypted["nonce"]) == b"test"


class TestDecryptionError:
    """Tests for DecryptionError exception."""

    def test_decryption_error_exists_and_extends_cyberred_error(self) -> None:
        """DecryptionError should exist and extend CyberRedError."""
        from cyberred.core.exceptions import CyberRedError, DecryptionError

        assert issubclass(DecryptionError, CyberRedError)

    def test_decryption_error_has_meaningful_message(self) -> None:
        """DecryptionError should have a meaningful default message."""
        from cyberred.core.exceptions import DecryptionError

        error = DecryptionError("Test reason")
        assert "Test reason" in str(error)
        
    def test_decryption_error_catches_value_error(self) -> None:
        """decrypt should catch ValueError and wrap in DecryptionError."""
        from cyberred.core.keystore import decrypt
        from cyberred.core.exceptions import DecryptionError
        from unittest.mock import patch

        # Mock AESGCM to raise ValueError (e.g. for invalid parameters)
        with patch("cyberred.core.keystore.AESGCM") as MockAESGCM:
            mock_instance = MockAESGCM.return_value
            mock_instance.decrypt.side_effect = ValueError("Invalid parameter")
            
            with pytest.raises(DecryptionError) as exc_info:
                decrypt(b"cipher", b"key"*32, b"nonce"*12)
            
            assert "Decryption failed" in str(exc_info.value)
            assert isinstance(exc_info.value.__cause__, ValueError)

    def test_decryption_error_generic_exception(self) -> None:
        """decrypt should catch generic exceptions and wrap in DecryptionError."""
        from cyberred.core.keystore import decrypt
        from cyberred.core.exceptions import DecryptionError
        from unittest.mock import patch

        # Mock AESGCM to raise a generic ConnectionError (or any non-crypto error)
        with patch("cyberred.core.keystore.AESGCM") as MockAESGCM:
            mock_instance = MockAESGCM.return_value
            mock_instance.decrypt.side_effect = RuntimeError("Hardware failure")
            
            with pytest.raises(DecryptionError) as exc_info:
                decrypt(b"cipher", b"key"*32, b"nonce"*12)
            
            assert "Unexpected error" in str(exc_info.value)
            assert "Hardware failure" in str(exc_info.value)
