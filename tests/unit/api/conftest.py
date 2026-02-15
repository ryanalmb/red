"""Shared fixtures for API unit tests."""

import pytest

from cyberred.core.config import APIConfig


@pytest.fixture
def api_config() -> APIConfig:
    """Create a default APIConfig for testing."""
    return APIConfig()


@pytest.fixture
def api_config_with_tls(tmp_path):
    """Create an APIConfig with TLS cert/key paths pointing to real temp files."""
    cert_path = tmp_path / "test.crt"
    key_path = tmp_path / "test.key"

    # Generate self-signed cert/key for testing
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    import datetime

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )

    return APIConfig(
        enabled=True,
        host="127.0.0.1",
        port=8443,
        tls_cert_path=str(cert_path),
        tls_key_path=str(key_path),
    ), cert_path, key_path
