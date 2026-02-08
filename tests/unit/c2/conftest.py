"""Pytest fixtures for C2 unit tests."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from cyberred.c2 import C2ServerConfig


@pytest.fixture
def default_config() -> C2ServerConfig:
    """Create default C2ServerConfig."""
    return C2ServerConfig()


@pytest.fixture
def custom_config(tmp_path: Path) -> C2ServerConfig:
    """Create custom C2ServerConfig with paths."""
    return C2ServerConfig(
        host="127.0.0.1",
        port=9444,
        ca_cert_path=tmp_path / "ca.crt",
        server_cert_path=tmp_path / "server.crt",
        server_key_path=tmp_path / "server.key",
    )


@pytest.fixture
def mock_ca_store() -> MagicMock:
    """Create mock CAStore."""
    mock = MagicMock()
    mock.verify_certificate.return_value = True
    return mock


@pytest.fixture
def shared_secret() -> bytes:
    """Test shared secret for HMAC signing."""
    return b"test_secret_key_for_hmac_signing"


@pytest.fixture
def config_with_secret(tmp_path: Path, shared_secret: bytes) -> C2ServerConfig:
    """Create C2ServerConfig with shared secret."""
    return C2ServerConfig(
        host="127.0.0.1",
        port=0,
        shared_secret=shared_secret,
    )
