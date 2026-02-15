"""Integration test fixtures for API server."""

import datetime

import pytest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from cyberred.core.config import APIConfig


@pytest.fixture
def tls_cert_and_key(tmp_path):
    """Generate a self-signed TLS cert and key for integration testing."""
    cert_path = tmp_path / "server.crt"
    key_path = tmp_path / "server.key"

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
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(
                    __import__("ipaddress").ip_address("127.0.0.1")
                ),
            ]),
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

    return cert_path, key_path


@pytest.fixture
def integration_api_config(tls_cert_and_key, unused_tcp_port):
    """Create an APIConfig for integration testing with real TLS certs."""
    cert_path, key_path = tls_cert_and_key
    return APIConfig(
        enabled=True,
        host="127.0.0.1",
        port=unused_tcp_port,
        tls_cert_path=str(cert_path),
        tls_key_path=str(key_path),
    )


@pytest.fixture
def unused_tcp_port():
    """Find an unused TCP port."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
