"""Unit tests for APIConfig (Story 14.1, Task 2 — RED phase)."""

import pytest

from cyberred.core.config import APIConfig, Settings, get_settings, reset_settings


class TestAPIConfig:
    """Tests for APIConfig Pydantic model."""

    def test_default_values(self):
        """APIConfig has correct defaults."""
        config = APIConfig()
        assert config.enabled is False
        assert config.host == "0.0.0.0"
        assert config.port == 8443
        assert config.tls_cert_path == ""
        assert config.tls_key_path == ""
        assert config.cors_origins == []

    def test_custom_values(self):
        """APIConfig accepts custom values."""
        config = APIConfig(
            enabled=True,
            host="127.0.0.1",
            port=9443,
            tls_cert_path="/etc/ssl/cert.pem",
            tls_key_path="/etc/ssl/key.pem",
            cors_origins=["https://example.com"],
        )
        assert config.enabled is True
        assert config.host == "127.0.0.1"
        assert config.port == 9443
        assert config.tls_cert_path == "/etc/ssl/cert.pem"
        assert config.tls_key_path == "/etc/ssl/key.pem"
        assert config.cors_origins == ["https://example.com"]

    def test_port_must_be_positive(self):
        """APIConfig rejects non-positive port values."""
        with pytest.raises(Exception):
            APIConfig(port=0)
        with pytest.raises(Exception):
            APIConfig(port=-1)

    def test_settings_includes_api_config(self):
        """Settings class includes api field with APIConfig default."""
        reset_settings()
        try:
            settings = Settings()
            assert hasattr(settings, "api")
            assert isinstance(settings.api, APIConfig)
            assert settings.api.port == 8443
        finally:
            reset_settings()

    def test_cors_origins_multiple(self):
        """APIConfig supports multiple CORS origins."""
        config = APIConfig(
            cors_origins=["https://a.com", "https://b.com", "http://localhost:3000"]
        )
        assert len(config.cors_origins) == 3
