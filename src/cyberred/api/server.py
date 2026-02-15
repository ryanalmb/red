"""FastAPI Application Server (Story 14.1).

Provides the APIServer class and create_app() factory for the
Cyber-Red REST API server (FR48).

Architecture Context:
- Startup Order: Redis → Daemon → C2 Server → API Server
- Shutdown Order: API → C2 → Daemon → Redis
- API ↔ Core: REST endpoints delegate to daemon. No direct agent/tool access.
"""

from __future__ import annotations

import os
import ssl
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import cyberred
from cyberred.api.auth import configure_auth, router as auth_router
from cyberred.api.routes.health import reset_start_time, router as health_router
from cyberred.api.routes.health import set_start_time
from cyberred.api.token_store import TokenStore
from cyberred.core.config import APIConfig
from cyberred.core.exceptions import ConfigurationError

log = structlog.get_logger()


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan context manager for startup/shutdown.

    Sets server start time on startup for uptime tracking.
    Initializes token store for auth. Cleans up on shutdown.
    """
    set_start_time(time.time())

    # Initialize token store if config is attached to app state
    token_store: TokenStore | None = getattr(app.state, "_token_store", None)
    if token_store is not None:
        await token_store.initialize()

    log.info("api_server_lifespan_startup")
    yield

    # Clean up token store
    if token_store is not None:
        await token_store.close()

    reset_start_time()
    log.info("api_server_lifespan_shutdown")


def create_app(
    config: APIConfig | None = None,
    token_store: TokenStore | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: Optional APIConfig. If None, uses defaults.
        token_store: Optional TokenStore for auth. If None and jwt_secret_key
            is set, a default store is created.

    Returns:
        Configured FastAPI application instance.
    """
    if config is None:
        config = APIConfig()

    app = FastAPI(
        title="Cyber-Red API",
        version=cyberred.__version__,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=_lifespan,
    )

    # Register health router (unauthenticated)
    app.include_router(health_router)

    # Set up auth if jwt_secret_key is configured
    if config.jwt_secret_key:
        if token_store is None:
            import os
            db_dir = os.path.expanduser("~/.cyber-red")
            os.makedirs(db_dir, exist_ok=True)
            token_store = TokenStore(os.path.join(db_dir, "api_tokens.db"))

        # Attach token store to app state for lifespan management
        app.state._token_store = token_store
        configure_auth(config, token_store)

        # Register auth router (protected endpoints)
        app.include_router(auth_router)

    # Add CORS middleware if origins are configured
    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    return app


class APIServer:
    """FastAPI REST API server for external integrations.

    Wraps uvicorn with programmatic start/stop and TLS enforcement.

    Attributes:
        _config: API configuration.
        _app: FastAPI application instance.
        _server: Uvicorn server instance (set after start).
        _started_at: Timestamp when server was started.
    """

    def __init__(self, config: APIConfig | None = None) -> None:
        """Initialize APIServer.

        Args:
            config: API configuration. Uses defaults if None.
        """
        self._config = config or APIConfig()
        self._app = create_app(config=self._config)
        self._server: uvicorn.Server | None = None
        self._started_at: float | None = None

    @property
    def uptime(self) -> float:
        """Get server uptime in seconds.

        Returns:
            Uptime in seconds, or 0.0 if not started.
        """
        if self._started_at is None:
            return 0.0
        return time.time() - self._started_at

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context from configured cert/key paths.

        Enforces TLS 1.2 minimum for security.

        Returns:
            Configured ssl.SSLContext.

        Raises:
            ConfigurationError: If cert/key files are missing or invalid.
        """
        cert_path = self._config.tls_cert_path
        key_path = self._config.tls_key_path

        if not cert_path or not os.path.isfile(cert_path):
            raise ConfigurationError(
                config_path="api",
                key="tls_cert_path",
                message=f"TLS certificate file not found: {cert_path!r}",
            )

        if not key_path or not os.path.isfile(key_path):
            raise ConfigurationError(
                config_path="api",
                key="tls_key_path",
                message=f"TLS private key file not found: {key_path!r}",
            )

        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
            return ctx
        except (ssl.SSLError, OSError) as e:
            raise ConfigurationError(
                config_path="api",
                key="tls_cert_path",
                message=f"TLS configuration error: {e}",
            ) from e

    async def start(self) -> None:
        """Start the API server with TLS.

        Creates SSL context, configures uvicorn, and starts serving.
        Log message is emitted after uvicorn server object is created
        but before the blocking serve() call.

        Raises:
            ConfigurationError: If TLS configuration is invalid.
        """
        ssl_context = self._create_ssl_context()

        self._started_at = time.time()

        uv_config = uvicorn.Config(
            app=self._app,
            host=self._config.host,
            port=self._config.port,
            ssl_keyfile=self._config.tls_key_path,
            ssl_certfile=self._config.tls_cert_path,
            log_level="warning",
        )
        self._server = uvicorn.Server(config=uv_config)

        log.info(
            "api_server_starting",
            host=self._config.host,
            port=self._config.port,
        )

        await self._server.serve()

    async def stop(self) -> None:
        """Stop the API server gracefully.

        Signals the uvicorn server to exit and waits for shutdown.
        Safe to call even if server was never started.
        """
        if self._server is not None:
            self._server.should_exit = True
            log.info("api_server_stopping")
        self._started_at = None
