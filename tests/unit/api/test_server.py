"""Unit tests for APIServer and create_app (Story 14.1, Tasks 3/5/6 — RED phase)."""

import ssl
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cyberred.api.server import APIServer, create_app
from cyberred.core.config import APIConfig
from cyberred.core.exceptions import ConfigurationError


class TestCreateApp:
    """Tests for create_app() factory function."""

    def test_returns_fastapi_instance(self):
        """create_app() returns a FastAPI instance."""
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_title(self):
        """App has title 'Cyber-Red API'."""
        app = create_app()
        assert app.title == "Cyber-Red API"

    def test_app_version(self):
        """App version matches package version."""
        import cyberred
        app = create_app()
        assert app.version == cyberred.__version__

    def test_openapi_docs_at_docs(self):
        """OpenAPI docs are available at /docs."""
        app = create_app()
        client = TestClient(app)
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json_at_openapi(self):
        """OpenAPI JSON schema is available at /openapi.json."""
        app = create_app()
        client = TestClient(app)
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert data["info"]["title"] == "Cyber-Red API"

    def test_health_router_registered(self):
        """Health router is registered on the app."""
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_cors_middleware_disabled_by_default(self):
        """CORS middleware is not added when cors_origins is empty."""
        config = APIConfig(cors_origins=[])
        app = create_app(config=config)
        # No CORS headers on response when no origins configured
        client = TestClient(app)
        response = client.get("/health", headers={"Origin": "https://evil.com"})
        assert "access-control-allow-origin" not in response.headers

    def test_cors_middleware_enabled_with_origins(self):
        """CORS middleware is added when cors_origins is set."""
        config = APIConfig(cors_origins=["https://example.com"])
        app = create_app(config=config)
        client = TestClient(app)
        response = client.options(
            "/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "https://example.com"


class TestAPIServerInit:
    """Tests for APIServer initialization."""

    def test_init_with_default_config(self):
        """APIServer can be created with default config."""
        config = APIConfig()
        server = APIServer(config=config)
        assert server._config == config
        assert server._app is not None
        assert server._server is None
        assert server._started_at is None

    def test_init_creates_fastapi_app(self):
        """APIServer creates a FastAPI app on init."""
        config = APIConfig()
        server = APIServer(config=config)
        assert isinstance(server._app, FastAPI)


class TestAPIServerTLS:
    """Tests for TLS configuration."""

    def test_create_ssl_context_missing_cert(self, tmp_path):
        """Raises ConfigurationError when cert file is missing."""
        config = APIConfig(
            tls_cert_path=str(tmp_path / "nonexistent.crt"),
            tls_key_path=str(tmp_path / "test.key"),
        )
        server = APIServer(config=config)
        with pytest.raises(ConfigurationError, match="TLS certificate"):
            server._create_ssl_context()

    def test_create_ssl_context_missing_key(self, tmp_path):
        """Raises ConfigurationError when key file is missing."""
        cert_path = tmp_path / "test.crt"
        cert_path.write_text("fake cert")
        config = APIConfig(
            tls_cert_path=str(cert_path),
            tls_key_path=str(tmp_path / "nonexistent.key"),
        )
        server = APIServer(config=config)
        with pytest.raises(ConfigurationError, match="TLS private key"):
            server._create_ssl_context()

    def test_create_ssl_context_both_empty(self):
        """Raises ConfigurationError when both cert and key paths are empty."""
        config = APIConfig(tls_cert_path="", tls_key_path="")
        server = APIServer(config=config)
        with pytest.raises(ConfigurationError, match="TLS certificate"):
            server._create_ssl_context()

    def test_create_ssl_context_valid_certs(self, api_config_with_tls):
        """Creates valid SSL context with proper cert/key."""
        config, cert_path, key_path = api_config_with_tls
        server = APIServer(config=config)
        ctx = server._create_ssl_context()
        assert isinstance(ctx, ssl.SSLContext)

    def test_create_ssl_context_enforces_tls_1_2_minimum(self, api_config_with_tls):
        """SSL context enforces TLS 1.2 as minimum version."""
        config, cert_path, key_path = api_config_with_tls
        server = APIServer(config=config)
        ctx = server._create_ssl_context()
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2

    def test_create_ssl_context_invalid_cert_content(self, tmp_path):
        """Raises ConfigurationError when cert content is invalid."""
        cert_path = tmp_path / "bad.crt"
        key_path = tmp_path / "bad.key"
        cert_path.write_text("not a cert")
        key_path.write_text("not a key")
        config = APIConfig(
            tls_cert_path=str(cert_path),
            tls_key_path=str(key_path),
        )
        server = APIServer(config=config)
        with pytest.raises(ConfigurationError, match="TLS"):
            server._create_ssl_context()


class TestAPIServerLifecycle:
    """Tests for APIServer start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_sets_started_at(self, api_config_with_tls):
        """start() sets _started_at timestamp."""
        config, _, _ = api_config_with_tls
        server = APIServer(config=config)

        # We mock uvicorn.Server to avoid actually binding
        with patch("cyberred.api.server.uvicorn") as mock_uvicorn:
            mock_uv_server = AsyncMock()
            mock_uv_server.serve = AsyncMock()
            mock_uv_server.started = True
            mock_uvicorn.Config.return_value = MagicMock()
            mock_uvicorn.Server.return_value = mock_uv_server

            await server.start()
            assert server._started_at is not None
            assert server._started_at <= time.time()
            await server.stop()

    @pytest.mark.asyncio
    async def test_stop_resets_server(self, api_config_with_tls):
        """stop() shuts down the server gracefully and resets started_at."""
        config, _, _ = api_config_with_tls
        server = APIServer(config=config)

        with patch("cyberred.api.server.uvicorn") as mock_uvicorn:
            mock_uv_server = AsyncMock()
            mock_uv_server.serve = AsyncMock()
            mock_uv_server.started = True
            mock_uv_server.should_exit = False
            mock_uvicorn.Config.return_value = MagicMock()
            mock_uvicorn.Server.return_value = mock_uv_server

            await server.start()
            assert server._started_at is not None
            await server.stop()
            assert mock_uv_server.should_exit is True
            assert server._started_at is None

    @pytest.mark.asyncio
    async def test_start_without_tls_raises(self):
        """start() raises ConfigurationError when TLS is not configured."""
        config = APIConfig(tls_cert_path="", tls_key_path="")
        server = APIServer(config=config)
        with pytest.raises(ConfigurationError):
            await server.start()

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self):
        """stop() is safe to call when server was never started."""
        config = APIConfig()
        server = APIServer(config=config)
        # Should not raise
        await server.stop()
        assert server._started_at is None

    @pytest.mark.asyncio
    async def test_server_uptime(self, api_config_with_tls):
        """uptime property returns seconds since start."""
        config, _, _ = api_config_with_tls
        server = APIServer(config=config)

        with patch("cyberred.api.server.uvicorn") as mock_uvicorn:
            mock_uv_server = AsyncMock()
            mock_uv_server.serve = AsyncMock()
            mock_uv_server.started = True
            mock_uvicorn.Config.return_value = MagicMock()
            mock_uvicorn.Server.return_value = mock_uv_server

            await server.start()
            uptime = server.uptime
            assert uptime >= 0
            await server.stop()

    def test_uptime_before_start(self):
        """uptime is 0.0 before server is started."""
        config = APIConfig()
        server = APIServer(config=config)
        assert server.uptime == 0.0
