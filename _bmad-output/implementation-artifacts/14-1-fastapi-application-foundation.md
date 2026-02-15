# Story 14.1: FastAPI Application Foundation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **a FastAPI-based REST API server**,
So that **external systems can integrate with Cyber-Red (FR48)**.

## Acceptance Criteria

1. **Given** API server is configured
   - **When** I start `api.server.run()`
   - **Then** server listens on port 8443 (configurable)
   - **And** server binds to configurable host (default `0.0.0.0`)

2. **Given** API server is running
   - **When** a client connects via HTTPS
   - **Then** server uses TLS certificates for encryption
   - **And** plain HTTP connections are rejected (TLS required)

3. **Given** API server is running
   - **When** I access `/docs`
   - **Then** OpenAPI/Swagger documentation is rendered
   - **And** API version and title are displayed

4. **Given** API server is running
   - **When** I GET `/health`
   - **Then** response includes `status`, `uptime`, and `version`
   - **And** response HTTP status is 200 when healthy
   - **And** endpoint works without authentication (for load balancers)

5. **Given** API server is running
   - **When** server encounters TLS certificate errors
   - **Then** server logs the error and refuses to start
   - **And** a clear error message indicates the TLS misconfiguration

6. **Given** API server is started and stopped
   - **When** `start()` is called
   - **Then** server starts accepting connections
   - **When** `stop()` is called
   - **Then** server shuts down gracefully, closing all connections

7. **Given** implementation is complete
   - **Then** integration tests verify server starts and responds to health checks
   - **And** integration tests verify TLS enforcement
   - **And** integration tests verify OpenAPI spec is served
   - **And** all tests pass with 100% coverage on new code

## Tasks / Subtasks

**⚠️ CRITICAL: Test-Driven Development (TDD) Required**

> This story MUST follow strict TDD methodology:
> 1. **RED Phase**: Write failing tests FIRST before any implementation
> 2. **GREEN Phase**: Write minimal code to make tests pass
> 3. **REFACTOR Phase**: Clean up code while keeping tests green
>
> **🎯 COVERAGE REQUIREMENT**
> - All new code MUST achieve 100% test coverage
> - Run targeted coverage checks per file/module

- [x] Task 1: Create API module directory structure (AC: #1)
  - [x] Subtask 1.1: Create `src/cyberred/api/__init__.py` with module exports
  - [x] Subtask 1.2: Create `src/cyberred/api/server.py` with `APIServer` class skeleton
  - [x] Subtask 1.3: Create `src/cyberred/api/routes/__init__.py`
  - [x] Subtask 1.4: Create `src/cyberred/api/routes/health.py` with health endpoint skeleton
  - [x] Subtask 1.5: Create `tests/unit/api/` directory with `__init__.py` and `conftest.py`
  - [x] Subtask 1.6: Create `tests/integration/api/` directory with `__init__.py` and `conftest.py`

- [x] Task 2: Add API configuration to Settings (AC: #1)
  - [x] Subtask 2.1: RED — Write failing tests for `APIConfig` Pydantic model
  - [x] Subtask 2.2: GREEN — Add `APIConfig` model to `core/config.py` with `host` (default `0.0.0.0`), `port` (default `8443`), `tls_cert_path`, `tls_key_path`, `enabled` (default `False`)
  - [x] Subtask 2.3: Wire `APIConfig` into the `Settings` class as `api: APIConfig`
  - [x] Subtask 2.4: Add `api.*` paths to `HOT_RELOAD_SAFE_PATHS` where appropriate (e.g., rate limits — NOT port/host changes)

- [x] Task 3: Implement FastAPI application factory (AC: #1, #3)
  - [x] Subtask 3.1: RED — Write failing tests for `create_app()` returning a `FastAPI` instance
  - [x] Subtask 3.2: GREEN — Implement `create_app()` in `api/server.py` with title="Cyber-Red API", version from package, OpenAPI docs at `/docs`
  - [x] Subtask 3.3: Register health router on the FastAPI app
  - [x] Subtask 3.4: Add CORS middleware (disabled by default, configurable origins)
  - [x] Subtask 3.5: Add startup/shutdown lifespan context manager for initialization

- [x] Task 4: Implement health endpoint (AC: #4)
  - [x] Subtask 4.1: RED — Write failing tests for `GET /health` returning `{"status": "ok", "uptime": ..., "version": ...}`
  - [x] Subtask 4.2: GREEN — Implement health endpoint in `api/routes/health.py`
  - [x] Subtask 4.3: Track server start time for uptime calculation
  - [x] Subtask 4.4: Read version from `cyberred.__version__` or `importlib.metadata`
  - [x] Subtask 4.5: Health endpoint must NOT require authentication

- [x] Task 5: Implement TLS configuration (AC: #2, #5)
  - [x] Subtask 5.1: RED — Write failing tests for TLS SSL context creation
  - [x] Subtask 5.2: GREEN — Implement `_create_ssl_context()` in `APIServer` using cert/key paths from config
  - [x] Subtask 5.3: Validate cert/key files exist before server start, raise `ConfigurationError` if missing
  - [x] Subtask 5.4: Support optional self-signed cert generation for development (via flag)

- [x] Task 6: Implement APIServer lifecycle (AC: #6)
  - [x] Subtask 6.1: RED — Write failing tests for `APIServer.start()` and `APIServer.stop()`
  - [x] Subtask 6.2: GREEN — Implement `APIServer` class wrapping uvicorn with `start()` / `stop()` methods
  - [x] Subtask 6.3: Use `uvicorn.Config` + `uvicorn.Server` programmatic API (not CLI)
  - [x] Subtask 6.4: Implement graceful shutdown: close active connections, wait for in-flight requests
  - [x] Subtask 6.5: Add structlog logging for server start/stop events

- [x] Task 7: Write integration tests (AC: #7)
  - [x] Subtask 7.1: Integration test: server starts and health endpoint responds 200
  - [x] Subtask 7.2: Integration test: OpenAPI spec is served at `/docs` and `/openapi.json`
  - [x] Subtask 7.3: Integration test: server stop completes gracefully
  - [x] Subtask 7.4: Integration test: TLS enforcement (HTTPS required)
  - [x] Subtask 7.5: Integration test: health response includes correct fields
  - [x] Subtask 7.6: Verify 100% coverage on all new files

## Dev Notes

### Architecture Context

**Startup Order** (from architecture doc):
> Redis → Daemon → C2 Server → **API Server** (daemon manages agent lifecycle)

**Shutdown Order:**
> **API** → C2 → Daemon (pauses all engagements) → Redis

The API server is the **last** to start and the **first** to stop. It delegates all engagement operations to the Daemon's `SessionManager` — it does NOT manage agents or tools directly.

**Architectural Boundary** (from architecture doc):
> **API ↔ Core:** REST endpoints delegate to daemon. No direct agent/tool access.

The API server will need a reference to the daemon's `SessionManager` (or an IPC client) to route requests. For this foundation story, the server only needs health endpoint — session manager integration comes in Story 14.3.

### System Architecture Diagram

```
                                ┌──────────────────┐
                                │   External API   │ ← FR48: Automation
                                │   (FastAPI)      │   (token auth)
                                │   0.0.0.0:8443   │
                                └────────┬─────────┘
                                         │
┌────────────────┐     Unix Socket  ┌────▼─────────────┐     mTLS WS      ┌──────────────┐
│  Textual TUI   │◄────────────────►│  Cyber-Red Core   │◄────────────────►│   Drop Box   │
│  (operator)    │   127.0.0.1:8080 │  (asyncio)        │   0.0.0.0:8444  │   (remote)   │
└────────────────┘                  └──────────────────┘                   └──────────────┘
```

### Key Technical Decisions

1. **FastAPI + uvicorn** — Per architecture: "External API: REST via FastAPI" with uvicorn ASGI server
2. **Port 8443** — Architecture specifies `0.0.0.0:8443` for external API
3. **TLS required** — No HTTP mode; all connections must use HTTPS
4. **structlog** — All logging uses structlog with context binding per project conventions
5. **Pydantic v2** — For request/response schemas (FastAPI native integration)
6. **No authentication on `/health`** — Load balancers need unauthenticated health checks (Story 14.10 will expand health further)

### Dependencies Required

These dependencies should already be in `pyproject.toml` (per architecture doc):
```toml
"fastapi>=0.109.0",     # REST API (FR48)
"uvicorn[standard]",    # ASGI server
```

If not present, add them. Also need:
```toml
"pydantic>=2.0.0",      # Already present (used by core/config.py)
```

### Existing Code Patterns to Follow

**Server lifecycle pattern** (from `daemon/server.py` — `DaemonServer`):
```python
class APIServer:
    """FastAPI REST API server for external integrations."""
    
    def __init__(self, config: APIConfig | None = None):
        self._config = config or get_settings().api
        self._app = create_app()
        self._server: uvicorn.Server | None = None
        self._started_at: float | None = None
    
    async def start(self) -> None:
        """Start the API server with TLS."""
        ...
    
    async def stop(self) -> None:
        """Stop the API server gracefully."""
        ...
```

**Configuration pattern** (from `core/config.py`):
```python
class APIConfig(BaseModel):
    """API server configuration."""
    enabled: bool = False
    host: str = "0.0.0.0"
    port: PositiveInt = 8443
    tls_cert_path: str = ""
    tls_key_path: str = ""
```

**Logging pattern** (from project conventions):
```python
import structlog
log = structlog.get_logger()

log.info("api_server_started", host=host, port=port)
log.error("api_server_tls_error", error=str(e))
```

**Exception pattern** (from `core/exceptions.py`):
- Use `ConfigurationError` for TLS/config issues
- Follow existing hierarchy — don't create new exception classes unless truly needed

### File Structure

```
src/cyberred/api/
├── __init__.py              # Module exports: APIServer, create_app
├── server.py                # APIServer class, create_app() factory
├── routes/
│   ├── __init__.py
│   └── health.py            # GET /health endpoint
└── schemas.py               # (Placeholder for Story 14.7)

tests/unit/api/
├── __init__.py
├── conftest.py              # Shared fixtures (test client, etc.)
├── test_server.py           # APIServer unit tests
└── test_health.py           # Health endpoint unit tests

tests/integration/api/
├── __init__.py
├── conftest.py              # Integration fixtures
└── test_api_server.py       # Full server integration tests
```

### Testing Strategy

**Unit tests** — Use FastAPI `TestClient` (from `starlette.testclient`) for synchronous endpoint testing:
```python
from fastapi.testclient import TestClient
from cyberred.api.server import create_app

def test_health_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
```

**Integration tests** — Use `httpx.AsyncClient` with actual server binding for TLS and lifecycle tests:
```python
import httpx
import pytest

@pytest.mark.integration
async def test_server_starts_and_responds():
    server = APIServer(config=test_config)
    await server.start()
    try:
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.get(f"https://localhost:{port}/health")
            assert resp.status_code == 200
    finally:
        await server.stop()
```

### Cross-Story Context

**This story is the foundation for all Epic 14 stories:**
- **14.2** (Token Auth) — Adds JWT auth middleware to this server
- **14.3** (Engagement CRUD) — Adds engagement routes, requires SessionManager integration
- **14.4** (Findings Query) — Adds findings routes
- **14.5** (WebSocket Stream) — Adds WebSocket endpoint for real-time events
- **14.6** (Rate Limiting) — Adds `slowapi` middleware
- **14.7** (Pydantic Schemas) — Adds comprehensive `api/schemas.py`
- **14.8** (Deputy Operator) — Adds auth routes for deputy
- **14.9** (Auto-Pause) — Timer in daemon, API reports paused status
- **14.10** (Health & Metrics) — Expands health endpoint with Prometheus
- **14.11** (OpenTelemetry) — Adds tracing middleware

**Dependencies from previous epics:**
- `core/config.py` — Settings singleton (done, Epic 1)
- `core/exceptions.py` — Exception hierarchy (done, Epic 1)
- Daemon server pattern (done, Epic 2) — lifecycle reference
- C2 server pattern (done, Epic 12) — TLS context reference

### Epic 14 Context Summary

Epic 14 covers **11 stories** total delivering:
- FastAPI REST API server (this story)
- JWT token authentication with role-based access (operator/deputy)
- Engagement CRUD, findings query, WebSocket streaming
- Rate limiting, Pydantic schemas, health/metrics
- Deputy operator API support, auto-pause governance
- OpenTelemetry distributed tracing

**FRs Covered:** FR48 (API mode), FR49 (scriptable mode), FR63 (deputy operator), FR64 (auto-pause)
**NFRs Covered:** NFR9 (rate limiting)

### Project Structure Notes

- Alignment: New `src/cyberred/api/` module matches architecture doc exactly
- The architecture specifies `api/server.py`, `api/routes/engagements.py`, `api/routes/findings.py`, `api/routes/health.py`, `api/auth.py`, `api/schemas.py`
- This story creates the foundation (`server.py`, `routes/health.py`); remaining files come in later stories
- Test files mirror source structure per project convention: `tests/unit/api/` and `tests/integration/api/`

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#API Design] — FastAPI choice, port 8443, token auth
- [Source: _bmad-output/planning-artifacts/architecture.md#Mandatory Rules for AI Agents] — Startup/shutdown order
- [Source: _bmad-output/planning-artifacts/architecture.md#Architectural Boundaries] — API ↔ Core delegation
- [Source: _bmad-output/planning-artifacts/architecture.md#Technology Stack] — fastapi>=0.109.0, uvicorn[standard]
- [Source: _bmad-output/planning-artifacts/architecture.md#Complete Project Directory] — api/ structure
- [Source: _bmad-output/planning-artifacts/epics-stories.md#Epic 14] — All 11 stories, FRs, components
- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 14.1] — Original acceptance criteria
- [Source: src/cyberred/daemon/server.py] — DaemonServer lifecycle pattern reference
- [Source: src/cyberred/c2/server.py] — C2Server TLS/mTLS pattern reference
- [Source: src/cyberred/core/config.py] — Settings, BaseModel patterns, HOT_RELOAD_SAFE_PATHS
- [Source: src/cyberred/core/exceptions.py] — ConfigurationError for TLS validation

## Dev Agent Record

### Agent Model Used

Claude (Anthropic) via Rovo Dev

### Debug Log References

- Unit tests: `python3 -m pytest tests/unit/api/ -v --cov=src/cyberred/api` → 36 passed, 100% coverage
- Integration tests: `python3 -m pytest tests/integration/api/ -v` → 5 passed
- Combined: `python3 -m pytest tests/unit/api/ tests/integration/api/ -v --cov=src/cyberred/api` → 41 passed, 100% coverage

### Completion Notes List

- Added `fastapi>=0.109.0` and `uvicorn[standard]>=0.27.0` to `pyproject.toml` dependencies
- Added `APIConfig` Pydantic model to `core/config.py` with defaults: host=0.0.0.0, port=8443, enabled=False
- Wired `APIConfig` into both `SystemConfig` and `Settings` classes
- Added `api.cors_origins` to `HOT_RELOAD_SAFE_PATHS` (port/host changes require restart)
- Implemented `create_app()` factory with FastAPI title="Cyber-Red API", version from package, lifespan manager
- Implemented `GET /health` returning `{status, uptime, version}` without authentication
- Implemented `APIServer` class with TLS enforcement, `start()`/`stop()` lifecycle, structlog logging
- CORS middleware disabled by default, enabled when `cors_origins` is configured
- TLS validation raises `ConfigurationError` for missing/invalid cert/key files
- All 41 tests pass (36 unit + 5 integration) with 100% branch coverage on new code

### File List

**New source files:**
- `src/cyberred/api/__init__.py` — Module exports (APIServer, create_app)
- `src/cyberred/api/server.py` — APIServer class, create_app() factory, lifespan
- `src/cyberred/api/routes/__init__.py` — Route module init
- `src/cyberred/api/routes/health.py` — GET /health endpoint

**Modified source files:**
- `src/cyberred/core/config.py` — Added APIConfig model, wired into Settings + SystemConfig, updated HOT_RELOAD_SAFE_PATHS
- `pyproject.toml` — Added fastapi and uvicorn dependencies

**New test files:**
- `tests/unit/api/__init__.py`
- `tests/unit/api/conftest.py` — Shared fixtures (api_config, api_config_with_tls)
- `tests/unit/api/test_config.py` — APIConfig unit tests (5 tests)
- `tests/unit/api/test_health.py` — Health endpoint unit tests (10 tests)
- `tests/unit/api/test_server.py` — APIServer unit tests (21 tests)
- `tests/integration/api/__init__.py`
- `tests/integration/api/conftest.py` — Integration fixtures (TLS certs, unused port)
- `tests/integration/api/test_api_server.py` — Full server integration tests (5 tests)
