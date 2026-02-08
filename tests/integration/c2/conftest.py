"""Pytest fixtures for C2 integration tests."""

import pytest
from pathlib import Path
from typing import Dict

from cyberred.core import CAStore, Keystore, generate_salt
from cyberred.c2 import C2ServerConfig


@pytest.fixture
def ca_store_with_certs(tmp_path: Path) -> tuple[CAStore, Dict[str, Path]]:
    """Create CAStore with server and client certificates.
    
    Returns:
        Tuple of (ca_store, paths_dict) where paths_dict contains:
        - ca_cert: Path to CA certificate
        - server_cert: Path to server certificate
        - server_key: Path to server private key
        - client_cert: Path to client certificate
        - client_key: Path to client private key
    """
    salt = generate_salt()
    keystore = Keystore.from_password("test_pass", salt)
    ca_store = CAStore(keystore)
    ca_store.generate_ca("Test Root CA")

    # Generate server cert
    server_cert, server_key = ca_store.generate_cert(
        common_name="c2-server",
        san_names=["localhost", "127.0.0.1"],
    )

    # Generate client cert
    client_cert, client_key = ca_store.generate_cert(
        common_name="drop-box-1",
        san_names=["client"],
    )

    # Define paths
    paths = {
        "ca_cert": tmp_path / "ca.crt",
        "server_cert": tmp_path / "server.crt",
        "server_key": tmp_path / "server.key",
        "client_cert": tmp_path / "client.crt",
        "client_key": tmp_path / "client.key",
    }

    # Write certificates
    paths["ca_cert"].write_bytes(ca_store.serialize_cert_pem(ca_store._ca_cert))
    paths["server_cert"].write_bytes(ca_store.serialize_cert_pem(server_cert))
    paths["server_key"].write_bytes(ca_store.serialize_key_pem(server_key))
    paths["client_cert"].write_bytes(ca_store.serialize_cert_pem(client_cert))
    paths["client_key"].write_bytes(ca_store.serialize_key_pem(client_key))

    return ca_store, paths


@pytest.fixture
def c2_server_config(ca_store_with_certs: tuple[CAStore, Dict[str, Path]]) -> C2ServerConfig:
    """Create C2ServerConfig with valid certificate paths."""
    _, paths = ca_store_with_certs
    return C2ServerConfig(
        host="127.0.0.1",
        port=0,  # Let OS choose port
        ca_cert_path=paths["ca_cert"],
        server_cert_path=paths["server_cert"],
        server_key_path=paths["server_key"],
    )
