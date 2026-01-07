"""CA Key Storage module for mTLS certificate generation.

Provides secure CA key storage with encrypted private keys and x509 certificate
generation for mTLS (mutual TLS) authentication per NFR17.

Security Notes:
- CA private key is ALWAYS encrypted at rest using Keystore (PBKDF2 + AES-256-GCM)
- CA certificate is stored in plaintext PEM format (public data)
- End-entity certificates include proper mTLS extensions
- Supports certificate pinning via get_ca_public_key_bytes()

Usage:
    from cyberred.core import CAStore, Keystore, generate_salt

    # Initialize
    salt = generate_salt()
    keystore = Keystore.from_password("password", salt)
    ca_store = CAStore(keystore)
    ca_store.generate_ca("Cyber-Red Root CA")

    # Generate mTLS certificate
    cert, key = ca_store.generate_cert("server-01", san_names=["server.local"])

    # Validate
    is_valid = ca_store.verify_cert(cert)
    status = ca_store.get_cert_expiry_status(cert)  # 'OK', 'WARNING', 'BLOCKED'
"""

import ipaddress
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from cryptography.exceptions import InvalidSignature

from cyberred.core.keystore import Keystore
from cyberred.core.exceptions import DecryptionError
from cyberred.core.config import get_settings


# =============================================================================
# Helper Functions
# =============================================================================


def _get_current_time() -> datetime:
    """Get current UTC time. Extracted for testing purposes."""
    return datetime.now(timezone.utc)


def _parse_san_name(name: str) -> x509.GeneralName:
    """Parse a SAN name into appropriate GeneralName type.

    Args:
        name: Either an IP address or DNS name string.

    Returns:
        x509.GeneralName (IPAddress or DNSName).
    """
    try:
        # Try to parse as IP address
        ip = ipaddress.ip_address(name)
        return x509.IPAddress(ip)
    except ValueError:
        # Not an IP, treat as DNS name
        return x509.DNSName(name)


# =============================================================================
# CAStore Class
# =============================================================================


class CAStore:
    """Certificate Authority storage with encrypted key management.

    Provides secure CA key storage and mTLS certificate generation
    per NFR17 security requirements.

    Attributes:
        _keystore: Keystore instance for encryption/decryption.
        _ca_key: CA private key (RSA).
        _ca_cert: CA certificate (x509).
        _encrypted_key: Encrypted key data for persistence.

    Usage:
        keystore = Keystore.from_password("secret", salt)
        ca_store = CAStore(keystore)
        ca_store.generate_ca("My CA")
        cert, key = ca_store.generate_cert("server")
    """

    def __init__(self, keystore: Keystore) -> None:
        """Initialize CAStore with a Keystore for encryption.

        Args:
            keystore: Keystore instance for encrypting CA private key.
        """
        self._keystore = keystore
        self._ca_key: Optional[rsa.RSAPrivateKey] = None
        self._ca_cert: Optional[x509.Certificate] = None
        self._encrypted_key: Optional[dict] = None

    def generate_ca(
        self, common_name: str = "Cyber-Red CA", valid_days: Optional[int] = None
    ) -> None:
        """Generate a new CA private key and self-signed certificate.

        Args:
            common_name: CA certificate common name.
            valid_days: Certificate validity in days (default: None, uses config).

        Raises:
            ValueError: If common_name is empty.
        """
        if not common_name:
            raise ValueError("Common name cannot be empty")

        if valid_days is None:
            valid_days = get_settings().security.ca_validity_days

        # Generate RSA 4096-bit key for CA (stronger than end-entity)
        self._ca_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
        )

        # Build CA certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Cyber-Red"),
        ])

        now = _get_current_time()
        self._ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(self._ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=valid_days))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=0),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=False,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(self._ca_key, hashes.SHA256())
        )

        # Encrypt the private key for storage
        key_bytes = self._ca_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self._encrypted_key = self._keystore.encrypt(key_bytes)

    def save(self, key_path: Path, cert_path: Path) -> None:
        """Save CA to files (encrypted key and PEM certificate).

        Args:
            key_path: Path to save encrypted private key.
            cert_path: Path to save PEM certificate.

        Raises:
            RuntimeError: If CA has not been generated.
        """
        if self._ca_cert is None or self._encrypted_key is None:
            raise RuntimeError("CA not initialized. Call generate_ca() first.")

        # Ensure parent directories exist
        key_path.parent.mkdir(parents=True, exist_ok=True)
        cert_path.parent.mkdir(parents=True, exist_ok=True)

        # Save encrypted key as JSON with binary data
        key_data = {
            "ciphertext": self._encrypted_key["ciphertext"].hex(),
            "nonce": self._encrypted_key["nonce"].hex(),
        }
        key_path.write_bytes(json.dumps(key_data).encode())

        # Save certificate as PEM
        cert_pem = self._ca_cert.public_bytes(serialization.Encoding.PEM)
        cert_path.write_bytes(cert_pem)

    @classmethod
    def load(
        cls, keystore: Keystore, key_path: Path, cert_path: Path
    ) -> "CAStore":
        """Load CA from files.

        Args:
            keystore: Keystore for decrypting private key.
            key_path: Path to encrypted private key file.
            cert_path: Path to PEM certificate file.

        Returns:
            CAStore instance with loaded CA.

        Raises:
            FileNotFoundError: If files don't exist.
            DecryptionError: If decryption fails (wrong password or corrupted).
        """
        if not key_path.exists():
            raise FileNotFoundError(f"Key file not found: {key_path}")
        if not cert_path.exists():
            raise FileNotFoundError(f"Certificate file not found: {cert_path}")

        # Load and decrypt key
        try:
            key_data = json.loads(key_path.read_bytes().decode())
            ciphertext = bytes.fromhex(key_data["ciphertext"])
            nonce = bytes.fromhex(key_data["nonce"])
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise DecryptionError(f"Corrupted key file: {e}") from e

        try:
            key_bytes = keystore.decrypt(ciphertext, nonce)
        except Exception as e:
            raise DecryptionError(f"Failed to decrypt key: {e}") from e

        # Load private key from DER
        private_key = serialization.load_der_private_key(key_bytes, password=None)
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise DecryptionError("Invalid key type")

        # Load certificate
        cert_pem = cert_path.read_bytes()
        certificate = x509.load_pem_x509_certificate(cert_pem)

        # Create CAStore instance
        ca_store = cls(keystore)
        ca_store._ca_key = private_key
        ca_store._ca_cert = certificate
        ca_store._encrypted_key = {"ciphertext": ciphertext, "nonce": nonce}

        return ca_store

    def generate_cert(
        self,
        common_name: str,
        valid_hours: int = 24,
        key_size: int = 2048,
        san_names: Optional[list[str]] = None,
    ) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
        """Generate a signed end-entity certificate for mTLS.

        Args:
            common_name: Certificate common name (e.g., "server-01").
            valid_hours: Certificate validity in hours (default: 24).
            key_size: RSA key size in bits (default: 2048).
            san_names: Subject Alternative Names (DNS names or IP addresses).

        Returns:
            Tuple of (certificate, private_key).

        Raises:
            RuntimeError: If CA has not been initialized.
        """
        if self._ca_key is None or self._ca_cert is None:
            raise RuntimeError("CA not initialized. Call generate_ca() first.")

        # Generate key for this certificate
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
        )

        # Build subject
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        now = _get_current_time()

        # Build certificate
        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(self._ca_cert.subject)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(hours=valid_hours))
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=True,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([
                    ExtendedKeyUsageOID.SERVER_AUTH,
                    ExtendedKeyUsageOID.CLIENT_AUTH,
                ]),
                critical=False,
            )
        )

        # Add SAN extension if provided
        if san_names:
            san_entries = [_parse_san_name(name) for name in san_names]
            builder = builder.add_extension(
                x509.SubjectAlternativeName(san_entries),
                critical=False,
            )

        # Sign with CA key
        certificate = builder.sign(self._ca_key, hashes.SHA256())

        return certificate, private_key

    def verify_cert(self, cert: x509.Certificate) -> bool:
        """Verify a certificate is valid and signed by this CA.

        Args:
            cert: Certificate to verify.

        Returns:
            True if certificate is valid and not expired, False otherwise.
        """
        if self._ca_key is None or self._ca_cert is None:
            return False

        # Check expiration
        now = _get_current_time()
        if cert.not_valid_after_utc < now or cert.not_valid_before_utc > now:
            return False

        # Verify signature
        try:
            self._ca_cert.public_key().verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                padding.PKCS1v15(),
                cert.signature_hash_algorithm,
            )
            return True
        except InvalidSignature:
            return False
        except Exception:
            return False

    def get_cert_expiry_status(
        self, cert: x509.Certificate
    ) -> Literal["OK", "WARNING", "BLOCKED"]:
        """Get certificate expiry status per architecture requirements.

        Per architecture line 106:
        - >7 days remaining → OK
        - <7 days remaining → WARNING
        - <24 hours remaining → BLOCKED

        Args:
            cert: Certificate to check.

        Returns:
            Status string: 'OK', 'WARNING', or 'BLOCKED'.
        """
        remaining = self.get_remaining_validity(cert)

        if remaining < timedelta(hours=24):
            return "BLOCKED"
        elif remaining < timedelta(days=7):
            return "WARNING"
        else:
            return "OK"

    def get_remaining_validity(self, cert: x509.Certificate) -> timedelta:
        """Get remaining validity period for a certificate.

        Args:
            cert: Certificate to check.

        Returns:
            Remaining time until expiration.
        """
        now = _get_current_time()
        return cert.not_valid_after_utc - now

    def get_cert_fingerprint(self, cert: x509.Certificate) -> str:
        """Get SHA-256 fingerprint of a certificate.

        Args:
            cert: Certificate to fingerprint.

        Returns:
            Lowercase hex string of SHA-256 digest.
        """
        return cert.fingerprint(hashes.SHA256()).hex()

    def get_ca_public_key_bytes(self) -> bytes:
        """Get CA public key bytes for certificate pinning.

        Returns:
            DER-encoded public key bytes.

        Raises:
            RuntimeError: If CA has not been initialized.
        """
        if self._ca_cert is None:
            raise RuntimeError("CA not initialized. Call generate_ca() first.")

        return self._ca_cert.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    @staticmethod
    def serialize_cert_pem(cert: x509.Certificate) -> bytes:
        """Serialize certificate to PEM format.

        Args:
            cert: Certificate to serialize.

        Returns:
            PEM-encoded certificate bytes.
        """
        return cert.public_bytes(serialization.Encoding.PEM)

    @staticmethod
    def serialize_key_pem(
        key: rsa.RSAPrivateKey, password: Optional[bytes] = None
    ) -> bytes:
        """Serialize private key to PEM format.

        Args:
            key: Private key to serialize.
            password: Optional password for encryption.

        Returns:
            PEM-encoded private key bytes.
        """
        if password:
            encryption = serialization.BestAvailableEncryption(password)
        else:
            encryption = serialization.NoEncryption()

        return key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption,
        )
