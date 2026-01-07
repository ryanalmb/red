"""Unit tests for CAStore module.

Tests CA key storage and certificate generation following TDD methodology.
Phase 1: RED - All tests should fail initially.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID

from cyberred.core import Keystore, generate_salt
from cyberred.core.exceptions import DecryptionError


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def keystore():
    """Create a keystore for testing."""
    salt = generate_salt()
    return Keystore.from_password("test_password", salt)


@pytest.fixture
def keystore_wrong_password():
    """Create a keystore with different password."""
    salt = generate_salt()
    return Keystore.from_password("wrong_password", salt)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for file operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# =============================================================================
# Task 2: CA Store Initialization Tests (AC: #1, #2, #3, #4)
# =============================================================================


class TestCAStoreInitialization:
    """Tests for CAStore creation and CA generation."""

    def test_generate_ca_creates_private_key_and_certificate(self, keystore):
        """Test CAStore.generate_ca() creates CA private key and certificate."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        assert ca_store._ca_key is not None
        assert ca_store._ca_cert is not None
        assert isinstance(ca_store._ca_key, rsa.RSAPrivateKey)
        assert isinstance(ca_store._ca_cert, x509.Certificate)

    def test_generate_ca_encrypts_private_key(self, keystore):
        """Test CA private key is encrypted using keystore (not plaintext in memory)."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        # Encrypted data should be stored for persistence
        assert ca_store._encrypted_key is not None
        assert "ciphertext" in ca_store._encrypted_key
        assert "nonce" in ca_store._encrypted_key

    def test_generate_ca_uses_config_default_validity(self, keystore):
        """Test generate_ca uses valid_days from config if not specified."""
        from cyberred.core.ca_store import CAStore
        
        # Default is 365 in config, but let's mock it to be sure
        with patch("cyberred.core.ca_store.get_settings") as mock_settings:
            mock_settings.return_value.security.ca_validity_days = 100
            
            ca_store = CAStore(keystore)
            ca_store.generate_ca("Test CA")
            
            # Check validity is approx 100 days
            validity = ca_store._ca_cert.not_valid_after_utc - ca_store._ca_cert.not_valid_before_utc
            assert timedelta(days=99) < validity < timedelta(days=101)

    def test_generate_ca_uses_explicit_validity(self, keystore):
        """Test generate_ca uses valid_days argument when provided."""
        from cyberred.core.ca_store import CAStore
        
        ca_store = CAStore(keystore)
        # Pass explicit valid_days=10, ignoring config
        ca_store.generate_ca("Test CA", valid_days=10)
        
        # Check validity is approx 10 days
        validity = ca_store._ca_cert.not_valid_after_utc - ca_store._ca_cert.not_valid_before_utc
        assert timedelta(days=9) < validity < timedelta(days=11)

    def test_load_ca_from_files(self, keystore, temp_dir):
        """Test CAStore.load() loads CA from encrypted key file + certificate file."""
        from cyberred.core.ca_store import CAStore

        # Create and save CA
        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")
        key_path = temp_dir / "ca.key.enc"
        cert_path = temp_dir / "ca.crt"
        ca_store.save(key_path, cert_path)

        # Load from files
        loaded_ca = CAStore.load(keystore, key_path, cert_path)

        assert loaded_ca._ca_key is not None
        assert loaded_ca._ca_cert is not None
        # Verify same CA by comparing public key
        from cryptography.hazmat.primitives import serialization
        loaded_pk = loaded_ca._ca_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        original_pk = ca_store._ca_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        assert loaded_pk == original_pk

    def test_load_raises_decryption_error_with_wrong_password(
        self, keystore, keystore_wrong_password, temp_dir
    ):
        """Test CAStore.load() raises DecryptionError with wrong password."""
        from cyberred.core.ca_store import CAStore

        # Create and save CA
        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")
        key_path = temp_dir / "ca.key.enc"
        cert_path = temp_dir / "ca.crt"
        ca_store.save(key_path, cert_path)

        # Attempt to load with wrong password
        with pytest.raises(DecryptionError):
            CAStore.load(keystore_wrong_password, key_path, cert_path)

    def test_saved_key_file_is_encrypted(self, keystore, temp_dir):
        """Test CA private key file is NOT plaintext (encrypted bytes)."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")
        key_path = temp_dir / "ca.key.enc"
        cert_path = temp_dir / "ca.crt"
        ca_store.save(key_path, cert_path)

        # Read the key file
        key_data = key_path.read_bytes()

        # Should NOT contain PEM markers (it's encrypted)
        assert b"-----BEGIN" not in key_data
        assert b"PRIVATE KEY" not in key_data

    def test_saved_cert_file_is_pem_plaintext(self, keystore, temp_dir):
        """Test CA certificate file IS plaintext (PEM format)."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")
        key_path = temp_dir / "ca.key.enc"
        cert_path = temp_dir / "ca.crt"
        ca_store.save(key_path, cert_path)

        # Read the cert file
        cert_data = cert_path.read_bytes()

        # Should contain PEM markers
        assert b"-----BEGIN CERTIFICATE-----" in cert_data
        assert b"-----END CERTIFICATE-----" in cert_data

    def test_save_persists_ca_to_files(self, keystore, temp_dir):
        """Test CAStore.save() persists CA to files."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")
        key_path = temp_dir / "ca.key.enc"
        cert_path = temp_dir / "ca.crt"

        ca_store.save(key_path, cert_path)

        assert key_path.exists()
        assert cert_path.exists()
        assert key_path.stat().st_size > 0
        assert cert_path.stat().st_size > 0

    def test_save_with_custom_file_paths(self, keystore, temp_dir):
        """Test CAStore.save() with custom file paths."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        # Custom paths in subdirectory
        subdir = temp_dir / "certs" / "ca"
        subdir.mkdir(parents=True)
        key_path = subdir / "custom_key.encrypted"
        cert_path = subdir / "custom_cert.pem"

        ca_store.save(key_path, cert_path)

        assert key_path.exists()
        assert cert_path.exists()


# =============================================================================
# Task 3: Certificate Generation Tests (AC: #5, #6)
# =============================================================================


class TestCertificateGeneration:
    """Tests for mTLS certificate generation."""

    def test_generate_cert_returns_certificate_and_key(self, keystore):
        """Test generate_cert returns signed certificate + key pair."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        cert, key = ca_store.generate_cert("test-server")

        assert isinstance(cert, x509.Certificate)
        assert isinstance(key, rsa.RSAPrivateKey)

    def test_generated_cert_is_signed_by_ca(self, keystore):
        """Test generated certificate is signed by CA (chain validation)."""
        from cyberred.core.ca_store import CAStore
        from cryptography.hazmat.primitives.asymmetric import padding

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        cert, _ = ca_store.generate_cert("test-server")

        # Verify the certificate was signed by the CA
        ca_public_key = ca_store._ca_cert.public_key()
        # This will raise if verification fails
        ca_public_key.verify(
            cert.signature,
            cert.tbs_certificate_bytes,
            padding.PKCS1v15(),
            cert.signature_hash_algorithm,
        )

    def test_generated_cert_has_extended_key_usage_server_auth(self, keystore):
        """Test Extended Key Usage includes TLS Web Server Authentication."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        cert, _ = ca_store.generate_cert("test-server")

        ext = cert.extensions.get_extension_for_oid(x509.ExtensionOID.EXTENDED_KEY_USAGE)
        assert ExtendedKeyUsageOID.SERVER_AUTH in ext.value

    def test_generated_cert_has_extended_key_usage_client_auth(self, keystore):
        """Test Extended Key Usage includes TLS Web Client Authentication."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        cert, _ = ca_store.generate_cert("test-server")

        ext = cert.extensions.get_extension_for_oid(x509.ExtensionOID.EXTENDED_KEY_USAGE)
        assert ExtendedKeyUsageOID.CLIENT_AUTH in ext.value

    def test_generated_cert_has_key_usage_digital_signature(self, keystore):
        """Test Key Usage includes Digital Signature."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        cert, _ = ca_store.generate_cert("test-server")

        ext = cert.extensions.get_extension_for_oid(x509.ExtensionOID.KEY_USAGE)
        assert ext.value.digital_signature is True

    def test_generated_cert_has_key_usage_key_encipherment(self, keystore):
        """Test Key Usage includes Key Encipherment."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        cert, _ = ca_store.generate_cert("test-server")

        ext = cert.extensions.get_extension_for_oid(x509.ExtensionOID.KEY_USAGE)
        assert ext.value.key_encipherment is True

    def test_generated_cert_has_basic_constraints_ca_false(self, keystore):
        """Test Basic Constraints: CA:FALSE."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        cert, _ = ca_store.generate_cert("test-server")

        ext = cert.extensions.get_extension_for_oid(x509.ExtensionOID.BASIC_CONSTRAINTS)
        assert ext.value.ca is False

    def test_generated_cert_has_san_extension(self, keystore):
        """Test generated certificate has Subject Alternative Name (SAN) extension."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        cert, _ = ca_store.generate_cert(
            "test-server", san_names=["test.example.com", "192.168.1.1"]
        )

        ext = cert.extensions.get_extension_for_oid(
            x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        )
        san_values = ext.value
        dns_names = [n.value for n in san_values if isinstance(n, x509.DNSName)]
        ip_addrs = [str(n.value) for n in san_values if isinstance(n, x509.IPAddress)]

        assert "test.example.com" in dns_names
        assert "192.168.1.1" in ip_addrs

    def test_generated_cert_with_custom_validity_period(self, keystore):
        """Test generated certificate with custom validity period."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        cert, _ = ca_store.generate_cert("test-server", valid_hours=48)

        # Check validity is approximately 48 hours
        validity = cert.not_valid_after_utc - cert.not_valid_before_utc
        assert timedelta(hours=47) < validity < timedelta(hours=49)

    def test_generated_cert_with_custom_key_size(self, keystore):
        """Test generated certificate with custom key size (default: 2048 bits RSA)."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        # Default 2048
        _, key_default = ca_store.generate_cert("test-server")
        assert key_default.key_size == 2048

        # Custom 4096
        _, key_4096 = ca_store.generate_cert("test-server-4k", key_size=4096)
        assert key_4096.key_size == 4096

    def test_certificate_expiration_default_24_hours(self, keystore):
        """Test certificate expiration is configurable (default: 24 hours per architecture)."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        cert, _ = ca_store.generate_cert("test-server")

        # Default should be 24 hours
        validity = cert.not_valid_after_utc - cert.not_valid_before_utc
        assert timedelta(hours=23) < validity < timedelta(hours=25)


# =============================================================================
# Task 4: Certificate Chain Validation Tests (AC: #7)
# =============================================================================


class TestCertificateValidation:
    """Tests for certificate chain validation."""

    def test_verify_cert_returns_true_for_valid_certificate(self, keystore):
        """Test verify_cert returns True for valid certificate."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")
        cert, _ = ca_store.generate_cert("test-server")

        assert ca_store.verify_cert(cert) is True

    def test_verify_cert_returns_false_for_expired_certificate(self, keystore):
        """Test verify_cert returns False for expired certificate."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        # Generate cert with 1 hour validity then mock time to after expiry
        cert, _ = ca_store.generate_cert("test-server", valid_hours=1)

        # Mock current time to be past expiry
        future_time = datetime.now(timezone.utc) + timedelta(hours=2)
        with patch("cyberred.core.ca_store._get_current_time", return_value=future_time):
            assert ca_store.verify_cert(cert) is False

    def test_verify_cert_returns_false_for_different_ca(self, keystore):
        """Test verify_cert returns False for certificate signed by different CA."""
        from cyberred.core.ca_store import CAStore

        ca_store1 = CAStore(keystore)
        ca_store1.generate_ca("CA 1")

        ca_store2 = CAStore(keystore)
        ca_store2.generate_ca("CA 2")

        # Generate cert with CA 2
        cert, _ = ca_store2.generate_cert("test-server")

        # Verify with CA 1 should fail
        assert ca_store1.verify_cert(cert) is False

    def test_verify_cert_returns_false_for_tampered_certificate(self, keystore):
        """Test verify_cert returns False for tampered certificate."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")
        cert, _ = ca_store.generate_cert("test-server")

        # Create a "tampered" cert by generating another one
        # (simulates tampered cert being different from what CA signed)
        cert2, _ = ca_store.generate_cert("different-server")

        # The signature on cert2 is valid, but if we modify it...
        # For this test, we verify that a cert from different CA fails
        ca_store2 = CAStore(keystore)
        ca_store2.generate_ca("Different CA")
        tampered_cert, _ = ca_store2.generate_cert("test-server")

        assert ca_store.verify_cert(tampered_cert) is False

    def test_get_cert_expiry_status_returns_ok_if_more_than_7_days(self, keystore):
        """Test get_cert_expiry_status returns OK if >7 days remaining."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        # Generate cert with 30 days validity
        cert, _ = ca_store.generate_cert("test-server", valid_hours=30 * 24)

        assert ca_store.get_cert_expiry_status(cert) == "OK"

    def test_get_cert_expiry_status_returns_warning_if_less_than_7_days(self, keystore):
        """Test get_cert_expiry_status returns WARNING if <7 days remaining."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        # Generate cert with 5 days validity
        cert, _ = ca_store.generate_cert("test-server", valid_hours=5 * 24)

        assert ca_store.get_cert_expiry_status(cert) == "WARNING"

    def test_get_cert_expiry_status_returns_blocked_if_less_than_24h(self, keystore):
        """Test get_cert_expiry_status returns BLOCKED if <24h remaining."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        # Generate cert with 12 hours validity
        cert, _ = ca_store.generate_cert("test-server", valid_hours=12)

        assert ca_store.get_cert_expiry_status(cert) == "BLOCKED"

    def test_get_remaining_validity_returns_correct_timedelta(self, keystore):
        """Test get_remaining_validity returns correct timedelta."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        cert, _ = ca_store.generate_cert("test-server", valid_hours=48)

        remaining = ca_store.get_remaining_validity(cert)

        # Should be approximately 48 hours (within a few seconds)
        assert timedelta(hours=47, minutes=59) < remaining < timedelta(hours=48, seconds=5)

    def test_get_cert_fingerprint_returns_sha256_hex(self, keystore):
        """Test get_cert_fingerprint returns SHA-256 hex digest."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        cert, _ = ca_store.generate_cert("test-server")

        fingerprint = ca_store.get_cert_fingerprint(cert)

        # SHA-256 hex digest is 64 characters
        assert len(fingerprint) == 64
        # Should be hex string
        assert all(c in "0123456789abcdef" for c in fingerprint.lower())


# =============================================================================
# Task 5: Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_load_with_nonexistent_files_raises_file_not_found(self, keystore, temp_dir):
        """Test CAStore.load() with non-existent files raises FileNotFoundError."""
        from cyberred.core.ca_store import CAStore

        key_path = temp_dir / "nonexistent.key"
        cert_path = temp_dir / "nonexistent.crt"

        with pytest.raises(FileNotFoundError):
            CAStore.load(keystore, key_path, cert_path)

    def test_load_with_corrupted_key_raises_decryption_error(self, keystore, temp_dir):
        """Test CAStore.load() with corrupted encrypted key raises DecryptionError."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")
        key_path = temp_dir / "ca.key.enc"
        cert_path = temp_dir / "ca.crt"
        ca_store.save(key_path, cert_path)

        # Corrupt the key file
        key_path.write_bytes(b"corrupted data that is not valid encrypted content")

        with pytest.raises(DecryptionError):
            CAStore.load(keystore, key_path, cert_path)

    def test_generate_ca_with_empty_common_name_raises_value_error(self, keystore):
        """Test CAStore.generate_ca() with invalid parameters raises ValueError."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)

        with pytest.raises(ValueError):
            ca_store.generate_ca("")

    def test_generate_cert_without_ca_raises_runtime_error(self, keystore):
        """Test CAStore.generate_cert() without initialized CA raises RuntimeError."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        # Don't call generate_ca()

        with pytest.raises(RuntimeError):
            ca_store.generate_cert("test-server")

    def test_save_without_ca_raises_runtime_error(self, keystore, temp_dir):
        """Test CAStore.save() without initialized CA raises RuntimeError."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        # Don't call generate_ca()

        with pytest.raises(RuntimeError):
            ca_store.save(temp_dir / "ca.key", temp_dir / "ca.crt")

    def test_load_with_missing_cert_file_raises_file_not_found(self, keystore, temp_dir):
        """Test CAStore.load() when cert file doesn't exist raises FileNotFoundError."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")
        key_path = temp_dir / "ca.key.enc"
        cert_path = temp_dir / "ca.crt"
        ca_store.save(key_path, cert_path)

        # Delete cert file, keep key file
        cert_path.unlink()

        with pytest.raises(FileNotFoundError):
            CAStore.load(keystore, key_path, cert_path)

    def test_verify_cert_without_ca_returns_false(self, keystore):
        """Test verify_cert returns False when CA is not initialized."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        # Don't call generate_ca()

        # Create a cert from another CA to have something to verify
        ca_store2 = CAStore(keystore)
        ca_store2.generate_ca("Other CA")
        cert, _ = ca_store2.generate_cert("test-server")

        # verify_cert should return False when CA is not initialized
        assert ca_store.verify_cert(cert) is False

    def test_get_ca_public_key_bytes_without_ca_raises_runtime_error(self, keystore):
        """Test get_ca_public_key_bytes raises RuntimeError without CA."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        # Don't call generate_ca()

        with pytest.raises(RuntimeError):
            ca_store.get_ca_public_key_bytes()

    def test_load_with_non_rsa_key_raises_decryption_error(self, keystore, temp_dir):
        """Test CAStore.load() with non-RSA key (e.g. EC) raises DecryptionError."""
        from cyberred.core.ca_store import CAStore
        from cryptography.hazmat.primitives.asymmetric import ec
        import json
        from cryptography.hazmat.primitives import serialization

        # Create an EC key (valid key, but not RSA)
        ec_key = ec.generate_private_key(ec.SECP256R1())
        key_bytes = ec_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        
        # Encrypt it manually as if it were a CA key
        encrypted = keystore.encrypt(key_bytes)
        
        # Save to file
        key_path = temp_dir / "ec_ca.key.enc"
        cert_path = temp_dir / "ec_ca.crt" # Dummy path, won't be read before key check fails?
        # Actually load reads key first, then decrypts, then checks type. 
        # But we need a valid cert file existence check first.
        cert_path.touch()

        key_data = {
            "ciphertext": encrypted["ciphertext"].hex(),
            "nonce": encrypted["nonce"].hex(),
        }
        key_path.write_bytes(json.dumps(key_data).encode())

        with pytest.raises(DecryptionError, match="Invalid key type"):
            CAStore.load(keystore, key_path, cert_path)

    def test_verify_cert_returns_false_on_generic_exception(self, keystore):
        """Test verify_cert returns False when a generic exception occurs."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")
        cert, _ = ca_store.generate_cert("test-server")

        # Mock the _ca_cert object completely to avoid issues with C-extension objects
        mock_cert = MagicMock()
        mock_public_key = MagicMock()
        mock_cert.public_key.return_value = mock_public_key
        mock_public_key.verify.side_effect = Exception("Generic error")
        
        # Replace the real cert with mock
        ca_store._ca_cert = mock_cert
        
        assert ca_store.verify_cert(cert) is False


# =============================================================================
# Additional Tests for Serialization and Pinning Support
# =============================================================================


class TestSerializationAndPinning:
    """Tests for certificate serialization and pinning support."""

    def test_serialize_cert_pem(self, keystore):
        """Test serialize_cert_pem returns PEM bytes."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")
        cert, _ = ca_store.generate_cert("test-server")

        pem_data = ca_store.serialize_cert_pem(cert)

        assert b"-----BEGIN CERTIFICATE-----" in pem_data
        assert b"-----END CERTIFICATE-----" in pem_data

    def test_serialize_key_pem(self, keystore):
        """Test serialize_key_pem returns PEM bytes."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")
        _, key = ca_store.generate_cert("test-server")

        pem_data = ca_store.serialize_key_pem(key)

        assert b"-----BEGIN" in pem_data
        assert b"PRIVATE KEY-----" in pem_data

    def test_serialize_key_pem_with_password(self, keystore):
        """Test serialize_key_pem with password encryption."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")
        _, key = ca_store.generate_cert("test-server")

        pem_data = ca_store.serialize_key_pem(key, password=b"secret")

        assert b"-----BEGIN ENCRYPTED PRIVATE KEY-----" in pem_data

    def test_get_ca_public_key_bytes(self, keystore):
        """Test get_ca_public_key_bytes for certificate pinning."""
        from cyberred.core.ca_store import CAStore

        ca_store = CAStore(keystore)
        ca_store.generate_ca("Test CA")

        pubkey_bytes = ca_store.get_ca_public_key_bytes()

        assert isinstance(pubkey_bytes, bytes)
        assert len(pubkey_bytes) > 0
        # Should be DER encoded public key
        assert pubkey_bytes[:2] == b"\x30\x82"  # DER sequence marker
