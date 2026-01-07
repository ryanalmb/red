"""Integration test fixtures for daemon tests.

This module provides fixtures for integration testing including:
- Real self-signed certificates with configurable expiry
- Redis testcontainer management
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator

import pytest
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


@pytest.fixture
def generate_cert():
    """Factory fixture to generate real self-signed certificates.
    
    Usage:
        cert_path = generate_cert(tmp_path, hours_valid=48)
    """
    def _generate(
        tmp_path: Path,
        hours_valid: float = 48,
        filename: str = "cert.pem"
    ) -> Path:
        """Generate a self-signed certificate.
        
        Args:
            tmp_path: Directory to write certificate to.
            hours_valid: Hours until certificate expires.
                         Use negative values for already-expired certs.
            filename: Filename for the certificate.
            
        Returns:
            Path to the generated certificate file.
        """
        # Generate private key
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Set validity period
        now = datetime.now(timezone.utc)
        not_before = now - timedelta(hours=1)  # Valid from 1 hour ago
        not_after = now + timedelta(hours=hours_valid)
        
        # Build certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Test"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Test City"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Org"),
            x509.NameAttribute(NameOID.COMMON_NAME, "test.local"),
        ])
        
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(not_before)
            .not_valid_after(not_after)
            .sign(key, hashes.SHA256(), default_backend())
        )
        
        # Write certificate to file
        cert_path = tmp_path / filename
        cert_path.write_bytes(
            cert.public_bytes(serialization.Encoding.PEM)
        )
        
        return cert_path
    
    return _generate


@pytest.fixture
def valid_cert_path(tmp_path: Path, generate_cert) -> Path:
    """Generate a certificate with 48h validity (well above 24h threshold)."""
    return generate_cert(tmp_path, hours_valid=48, filename="valid.pem")


@pytest.fixture
def expiring_cert_path(tmp_path: Path, generate_cert) -> Path:
    """Generate a certificate with only 12h remaining (below 24h threshold)."""
    return generate_cert(tmp_path, hours_valid=12, filename="expiring.pem")


@pytest.fixture
def expired_cert_path(tmp_path: Path, generate_cert) -> Path:
    """Generate an already-expired certificate."""
    return generate_cert(tmp_path, hours_valid=-1, filename="expired.pem")


@pytest.fixture
def scope_file(tmp_path: Path) -> Path:
    """Generate a valid scope YAML file."""
    scope_path = tmp_path / "scope.yaml"
    scope_path.write_text(
        "targets:\n"
        "  - 10.0.0.0/24\n"
        "  - 192.168.1.0/24\n"
        "exclusions:\n"
        "  - 10.0.0.1\n"
    )
    return scope_path
