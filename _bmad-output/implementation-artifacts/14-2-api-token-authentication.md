# Story 14.2: API Token Authentication

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **token-based API authentication**,
So that **only authorized systems can access the API (FR48)**.

## Acceptance Criteria

1. **Given** API server is running (Story 14.1 complete)
   - **When** request includes valid Bearer token in `Authorization` header
   - **Then** request is authenticated and proceeds to the endpoint
   - **And** the authenticated user's role (`operator` or `deputy`) is available to downstream handlers

2. **Given** API server is running
   - **When** request lacks `Authorization` header or token is missing
   - **Then** 401 Unauthorized response is returned
   - **And** response body includes `{"detail": "Not authenticated"}`

3. **Given** API server is running
   - **When** request includes an invalid or malformed JWT token
   - **Then** 401 Unauthorized response is returned
   - **And** response body includes `{"detail": "Invalid or expired token"}`

4. **Given** API server is running
   - **When** request includes an expired JWT token
   - **Then** 401 Unauthorized response is returned
   - **And** response body includes `{"detail": "Invalid or expired token"}`

5. **Given** a valid operator or CLI session
   - **When** a token is generated via `create_token(role, ttl)`
   - **Then** JWT token is returned with claims: `sub` (token ID), `role` ("operator" or "deputy"), `exp` (expiration), `iat` (issued at)
   - **And** token has configurable expiration (default: 24 hours)
   - **And** token metadata (token_id, role, created_at, expires_at, revoked) is stored in SQLite

6. **Given** a valid token exists
   - **When** `revoke_token(token_id)` is called
   - **Then** token is marked as revoked in the token store
   - **And** subsequent requests with that token return 401 Unauthorized
   - **And** revocation is logged to structlog

7. **Given** implementation is complete
   - **Then** integration tests verify full auth flow: create → authenticate → revoke → reject
   - **And** integration tests verify valid token grants access to protected endpoint
   - **And** integration tests verify expired tokens are rejected
   - **And** integration tests verify revoked tokens are rejected
   - **And** integration tests verify missing/malformed tokens are rejected
   - **And** integration tests verify role claim is correctly propagated
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

- [x] Task 1: Add AuthenticationError exception to exception hierarchy (AC: #2, #3, #4)
  - [ ] Subtask 1.1: RED — Write failing tests for `AuthenticationError` exception class
  - [ ] Subtask 1.2: GREEN — Add `AuthenticationError` to `core/exceptions.py` with attributes: `reason`, `token_id` (optional)
  - [ ] Subtask 1.3: Ensure it inherits from `CyberRedError` and implements `context` property

- [x] Task 2: Add `pyjwt[crypto]` dependency (AC: #5)
  - [ ] Subtask 2.1: Add `"PyJWT[crypto]>=2.8.0"` to `pyproject.toml` dependencies
  - [ ] Subtask 2.2: Verify import works: `import jwt`

- [x] Task 3: Add API auth configuration to `APIConfig` (AC: #5)
  - [ ] Subtask 3.1: RED — Write failing tests for new `APIConfig` fields: `jwt_secret_key`, `jwt_algorithm`, `token_ttl_hours`
  - [ ] Subtask 3.2: GREEN — Add fields to `APIConfig` in `core/config.py`:
    - `jwt_secret_key: str = ""` (MUST be set for production — raise `ConfigurationError` if empty when auth is needed)
    - `jwt_algorithm: str = "HS256"`
    - `token_ttl_hours: PositiveInt = 24`
  - [ ] Subtask 3.3: Add `api.token_ttl_hours` to `HOT_RELOAD_SAFE_PATHS`

- [x] Task 4: Implement token store (`api/token_store.py`) (AC: #5, #6)
  - [ ] Subtask 4.1: RED — Write failing tests for `TokenStore` class: `create_table()`, `store_token()`, `get_token()`, `revoke_token()`, `is_revoked()`
  - [ ] Subtask 4.2: GREEN — Implement `TokenStore` using SQLite:
    - Schema: `tokens(token_id TEXT PRIMARY KEY, role TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked INTEGER DEFAULT 0, revoked_at TEXT)`
    - `store_token(token_id, role, created_at, expires_at) -> None`
    - `get_token(token_id) -> dict | None`
    - `revoke_token(token_id) -> bool` (returns True if found and revoked)
    - `is_revoked(token_id) -> bool`
  - [ ] Subtask 4.3: Use `aiosqlite` for async SQLite access (consistent with storage patterns)
  - [ ] Subtask 4.4: Add structlog logging for token creation and revocation events

- [x] Task 5: Implement JWT token creation and validation (`api/auth.py`) (AC: #1, #2, #3, #4, #5, #6)
  - [ ] Subtask 5.1: RED — Write failing tests for `create_token(role, ttl_hours, secret_key)` returning JWT string
  - [ ] Subtask 5.2: RED — Write failing tests for `decode_token(token, secret_key)` returning claims dict or raising
  - [ ] Subtask 5.3: GREEN — Implement `create_token()`:
    - Generate UUID for `sub` (token_id)
    - Include claims: `sub`, `role`, `exp`, `iat`
    - Sign with `jwt_secret_key` using `jwt_algorithm`
    - Store metadata via `TokenStore`
  - [ ] Subtask 5.4: GREEN — Implement `decode_token()`:
    - Decode and verify JWT signature
    - Check expiration
    - Check revocation via `TokenStore`
    - Return claims dict with `sub`, `role`, `exp`, `iat`
    - Raise `AuthenticationError` on any failure
  - [ ] Subtask 5.5: Implement `revoke_token(token_id)` — delegates to `TokenStore`

- [x] Task 6: Implement FastAPI auth dependency (`api/auth.py`) (AC: #1, #2, #3, #4)
  - [ ] Subtask 6.1: RED — Write failing tests for `get_current_user` FastAPI dependency
  - [ ] Subtask 6.2: GREEN — Implement `get_current_user(credentials: HTTPAuthorizationCredentials)` as FastAPI `Depends`:
    - Uses `HTTPBearer` security scheme
    - Extracts Bearer token from `Authorization` header
    - Calls `decode_token()` to validate
    - Returns `TokenPayload` Pydantic model with `sub`, `role`, `exp`, `iat`
    - Raises `HTTPException(401)` on invalid/missing/expired/revoked token
  - [ ] Subtask 6.3: Implement `require_role(role: str)` dependency factory for role-based access control
    - Returns a dependency that checks `TokenPayload.role == required_role`
    - Raises `HTTPException(403)` if role doesn't match

- [x] Task 7: Wire auth into FastAPI app (AC: #1)
  - [ ] Subtask 7.1: Add `TokenPayload` Pydantic model to `api/auth.py`
  - [ ] Subtask 7.2: Register `HTTPBearer` security scheme on FastAPI app
  - [ ] Subtask 7.3: Ensure `/health` endpoint remains unauthenticated (no auth dependency)
  - [ ] Subtask 7.4: Add a test-only protected endpoint `/auth/verify` that returns token claims (for integration testing)

- [x] Task 8: Write integration tests (AC: #7)
  - [ ] Subtask 8.1: Integration test: valid token grants access to protected endpoint
  - [ ] Subtask 8.2: Integration test: missing token returns 401
  - [ ] Subtask 8.3: Integration test: invalid/malformed token returns 401
  - [ ] Subtask 8.4: Integration test: expired token returns 401
  - [ ] Subtask 8.5: Integration test: revoked token returns 401
  - [ ] Subtask 8.6: Integration test: role claim is correctly propagated (operator vs deputy)
  - [ ] Subtask 8.7: Integration test: `/health` still works without authentication
  - [ ] Subtask 8.8: Verify 100% coverage on all new files

## Dev Notes

### Architecture Context

**Startup Order** (from architecture doc):
> Redis → Daemon → C2 Server → **API Server** (daemon manages agent lifecycle)

The API server was established in Story 14.1. This story adds the authentication layer that all subsequent API stories (14.3–14.11) will depend on.

**Architectural Boundary** (from architecture doc):
> **API ↔ Core:** REST endpoints delegate to daemon. No direct agent/tool access.

The auth module is self-contained within `api/` — it does NOT depend on daemon, agents, or tools. Token storage uses a local SQLite database specific to the API module.

### System Architecture — Auth Flow

```
┌─────────────────┐       Authorization: Bearer <jwt>
│  External Client │ ─────────────────────────────────────┐
└─────────────────┘                                       │
                                                          ▼
                                        ┌──────────────────────────┐
                                        │   FastAPI Middleware      │
                                        │   HTTPBearer → Depends   │
                                        │                          │
                                        │  1. Extract Bearer token │
                                        │  2. decode_token(jwt)    │
                                        │  3. Check revocation     │
                                        │  4. Return TokenPayload  │
                                        └────────────┬─────────────┘
                                                     │
                                          ┌──────────▼──────────┐
                                          │  Protected Endpoint  │
                                          │  (has current_user)  │
                                          └──────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  Token Lifecycle                                                  │
│                                                                   │
│  CLI/TUI → create_token(role="operator", ttl=24h)                │
│         → JWT signed with jwt_secret_key                          │
│         → metadata stored in SQLite tokens table                  │
│                                                                   │
│  Revocation → revoke_token(token_id)                             │
│            → marks token as revoked in SQLite                     │
│            → all subsequent requests with this token → 401        │
└──────────────────────────────────────────────────────────────────┘
```

### Key Technical Decisions

1. **PyJWT library** — Industry-standard JWT implementation for Python. `PyJWT[crypto]` includes cryptography backend for HS256 and future RS256 support.
2. **HS256 algorithm default** — Symmetric signing is sufficient for single-server deployment. RS256 can be added later if multi-service verification is needed.
3. **SQLite token store** — Lightweight, zero-dependency persistence for token metadata and revocation tracking. Consistent with project's SQLite usage (checkpoints, audit).
4. **aiosqlite** — Async SQLite wrapper consistent with async patterns used throughout the project (FastAPI, uvicorn, daemon).
5. **Role-based model** — Two roles per design decision: `operator` (full control) and `deputy` (scoped to authorized actions only). Role is embedded in JWT claims.
6. **FastAPI `Depends`** — Standard FastAPI dependency injection pattern for auth. Enables per-endpoint auth requirements.
7. **No auth on `/health`** — Per Story 14.1 AC#4 and 14.10: health endpoint must remain unauthenticated for load balancer health checks.
8. **structlog** — All logging uses structlog with context binding per project conventions.

### Dependencies Required

**New dependency to add to `pyproject.toml`:**
```toml
"PyJWT[crypto]>=2.8.0",   # JWT token authentication (FR48)
```

**Already present:**
```toml
"fastapi>=0.109.0",       # REST API framework (Story 14.1)
"uvicorn[standard]>=0.27.0", # ASGI server (Story 14.1)
"pydantic>=2.0.0",        # Request/response models
"aiosqlite",              # Async SQLite (if not present, add it)
```

### Existing Code Patterns to Follow

**Exception pattern** (from `core/exceptions.py`):
```python
class AuthenticationError(CyberRedError):
    """Authentication failed — invalid, expired, or revoked token.
    
    Attributes:
        reason: Description of why authentication failed.
        token_id: Optional token ID (for revocation tracking).
    """
    
    def __init__(
        self,
        reason: str,
        token_id: str | None = None,
        message: str | None = None,
    ) -> None:
        self.reason = reason
        self.token_id = token_id
        if message is None:
            message = f"Authentication failed: {reason}"
        super().__init__(message)
    
    @property
    def context(self) -> dict[str, Any]:
        return {"reason": self.reason, "token_id": self.token_id}
```

**Configuration pattern** (extend existing `APIConfig` in `core/config.py`):
```python
class APIConfig(BaseModel):
    """API server configuration (Epic 14)."""
    enabled: bool = False
    host: str = "0.0.0.0"
    port: PositiveInt = 8443
    tls_cert_path: str = ""
    tls_key_path: str = ""
    cors_origins: List[str] = Field(default_factory=list)
    # New in Story 14.2:
    jwt_secret_key: str = ""        # MUST be set for production
    jwt_algorithm: str = "HS256"
    token_ttl_hours: PositiveInt = 24
```

**FastAPI dependency pattern**:
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenPayload:
    """FastAPI dependency for JWT authentication."""
    token = credentials.credentials
    try:
        payload = await decode_token(token, secret_key=...)
        return payload
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
```

**Logging pattern** (from project conventions):
```python
import structlog
log = structlog.get_logger()

log.info("token_created", token_id=token_id, role=role, ttl_hours=ttl)
log.info("token_revoked", token_id=token_id)
log.warning("token_auth_failed", reason="expired", token_id=token_id)
```

### File Structure

```
src/cyberred/api/
├── __init__.py              # Update exports: add auth functions
├── server.py                # Existing (Story 14.1) — no changes needed
├── auth.py                  # NEW: JWT auth (create_token, decode_token, get_current_user, require_role)
├── token_store.py           # NEW: SQLite token metadata storage
├── routes/
│   ├── __init__.py
│   └── health.py            # Existing (Story 14.1) — remains unauthenticated

src/cyberred/core/
├── exceptions.py            # MODIFY: Add AuthenticationError

tests/unit/api/
├── test_auth.py             # NEW: JWT creation, validation, decode tests
├── test_token_store.py      # NEW: TokenStore CRUD tests

tests/integration/api/
├── test_api_auth.py         # NEW: Full auth flow integration tests
```

### Testing Strategy

**Unit tests** — Use FastAPI `TestClient` for endpoint testing:
```python
from fastapi.testclient import TestClient
from cyberred.api.server import create_app

def test_protected_endpoint_without_token(test_client):
    response = test_client.get("/auth/verify")
    assert response.status_code == 401

def test_protected_endpoint_with_valid_token(test_client, valid_token):
    response = test_client.get(
        "/auth/verify",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "operator"
```

**Integration tests** — Use `httpx.AsyncClient` with actual server for full TLS + auth flow:
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_flow_end_to_end(integration_api_config):
    # 1. Create token
    token = await create_token(role="operator", ...)
    
    # 2. Use token to access protected endpoint
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.get(
            f"https://127.0.0.1:{port}/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
    
    # 3. Revoke token
    await revoke_token(token_id)
    
    # 4. Verify revoked token is rejected
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.get(
            f"https://127.0.0.1:{port}/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
```

### Cross-Story Context

**This story is the auth foundation for all subsequent Epic 14 stories:**
- **14.3** (Engagement CRUD) — All CRUD endpoints require `get_current_user` dependency
- **14.4** (Findings Query) — Findings endpoints require authenticated access
- **14.5** (WebSocket Stream) — WebSocket auth via Bearer header or `?token=` query param (per design decision)
- **14.6** (Rate Limiting) — Rate limits are per-token (not global), uses `token_id` from auth
- **14.7** (Pydantic Schemas) — `TokenPayload` model defined here, reused in schemas
- **14.8** (Deputy Operator) — Deputy tokens have `role: "deputy"`, scoped to auth response endpoints only
- **14.9** (Auto-Pause) — API reports paused status, auth required
- **14.10** (Health & Metrics) — Health remains unauthenticated, metrics may require auth
- **14.11** (OpenTelemetry) — Traces include `token_id` for request attribution

**Design Decisions (operator-approved, from epics-stories.md):**
- **Role-based model with 2 roles:** `operator` (full control) and `deputy` (scoped to authorized actions only)
- JWT claims MUST include `role` field: `{"role": "operator"}` or `{"role": "deputy"}`
- Deputy tokens can only access actions explicitly listed in deputy-authorized endpoints

**Dependencies from previous stories:**
- `api/server.py` — FastAPI app factory, `create_app()` (done, Story 14.1)
- `api/routes/health.py` — Health endpoint that must remain unauthenticated (done, Story 14.1)
- `core/config.py` — `APIConfig` model to extend (done, Story 14.1)
- `core/exceptions.py` — Exception hierarchy to extend (done, Epic 1)

### Previous Story Intelligence (14.1)

**Key learnings from Story 14.1:**
- FastAPI app created via `create_app()` factory in `api/server.py`
- `APIConfig` Pydantic model in `core/config.py` with TLS, host, port, cors_origins
- Health endpoint at `/health` uses `APIRouter` — add auth router similarly
- Test patterns: unit tests use `TestClient`, integration tests use `httpx.AsyncClient` with real TLS
- Integration test conftest.py at `tests/integration/api/conftest.py` has `tls_cert_and_key` and `integration_api_config` fixtures
- Unit test conftest.py at `tests/unit/api/conftest.py` has `api_config` and `api_config_with_tls` fixtures
- All 41 tests passed (36 unit + 5 integration) with 100% coverage
- CORS middleware disabled by default, enabled when `cors_origins` is configured
- `api.cors_origins` added to `HOT_RELOAD_SAFE_PATHS`

**Patterns to replicate:**
- Router pattern: `router = APIRouter()` with `@router.get(...)` decorators
- App registration: `app.include_router(auth_router)` in `create_app()`
- Structlog: `log = structlog.get_logger()` at module level
- Error handling: `ConfigurationError` for config issues, `HTTPException` for API errors

### Token Storage Design

```sql
CREATE TABLE IF NOT EXISTS tokens (
    token_id TEXT PRIMARY KEY,
    role TEXT NOT NULL CHECK(role IN ('operator', 'deputy')),
    created_at TEXT NOT NULL,  -- ISO 8601 UTC
    expires_at TEXT NOT NULL,  -- ISO 8601 UTC
    revoked INTEGER DEFAULT 0,
    revoked_at TEXT             -- ISO 8601 UTC, NULL if not revoked
);
```

**Storage location:** `~/.cyber-red/api_tokens.db` (or configurable via `APIConfig`)

**Key considerations:**
- Use `aiosqlite` for async access (non-blocking in FastAPI's event loop)
- WAL mode for concurrent reads (consistent with checkpoint storage pattern)
- Token metadata only — the JWT itself is NOT stored (stateless verification with revocation check)

### JWT Token Structure

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",  // token_id (UUID)
  "role": "operator",                                // "operator" or "deputy"
  "iat": 1706745600,                                 // issued at (Unix timestamp)
  "exp": 1706832000                                  // expires at (Unix timestamp)
}
```

### Security Considerations

1. **Secret key management:** `jwt_secret_key` MUST be set to a strong random value in production. Empty string should raise `ConfigurationError` when token creation is attempted.
2. **Token revocation:** Checked on every request via `TokenStore.is_revoked()`. SQLite lookup is fast for single-key queries.
3. **No token in URL:** Tokens are passed via `Authorization: Bearer` header only (Story 14.5 will add query param support for WebSocket).
4. **Short-lived tokens:** Default 24h TTL. Configurable via `token_ttl_hours`.
5. **Audit logging:** Token creation and revocation events logged via structlog for audit trail.

### Project Structure Notes

- Alignment: `api/auth.py` matches architecture doc exactly (`src/cyberred/api/auth.py`)
- New `api/token_store.py` is a supporting module for auth — not in architecture doc but follows project patterns for data persistence
- Test files mirror source structure: `tests/unit/api/test_auth.py`, `tests/unit/api/test_token_store.py`, `tests/integration/api/test_api_auth.py`

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#API Design] — FastAPI REST, token-based auth
- [Source: _bmad-output/planning-artifacts/architecture.md#Complete Project Directory] — `api/auth.py` location
- [Source: _bmad-output/planning-artifacts/architecture.md#Mandatory Rules for AI Agents] — Startup/shutdown order
- [Source: _bmad-output/planning-artifacts/architecture.md#Architectural Boundaries] — API ↔ Core delegation
- [Source: _bmad-output/planning-artifacts/epics-stories.md#Epic 14] — All 11 stories, FRs, design decisions
- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 14.2] — Original acceptance criteria and design decisions
- [Source: _bmad-output/implementation-artifacts/14-1-fastapi-application-foundation.md] — Previous story patterns and learnings
- [Source: src/cyberred/api/server.py] — FastAPI app factory, create_app(), APIServer class
- [Source: src/cyberred/api/routes/health.py] — Health endpoint pattern (unauthenticated)
- [Source: src/cyberred/core/config.py] — APIConfig model to extend, HOT_RELOAD_SAFE_PATHS
- [Source: src/cyberred/core/exceptions.py] — CyberRedError hierarchy to extend

## Dev Agent Record

### Agent Model Used

Claude (Anthropic) via Rovo Dev

### Debug Log References

### Completion Notes List

### File List

**New files:**
- `src/cyberred/api/auth.py` — JWT auth: create_token, decode_token, get_current_user, require_role, TokenPayload, /auth/verify endpoint
- `src/cyberred/api/token_store.py` — SQLite token metadata store (aiosqlite, WAL mode)
- `tests/unit/api/test_auth.py` — 29 unit tests for auth module
- `tests/unit/api/test_token_store.py` — 16 unit tests for token store
- `tests/integration/api/test_api_auth.py` — 14 integration tests for full auth flow

**Modified files:**
- `pyproject.toml` — Added PyJWT[crypto]>=2.8.0, aiosqlite>=0.19.0
- `src/cyberred/core/exceptions.py` — Added AuthenticationError
- `src/cyberred/core/config.py` — Added jwt_secret_key, jwt_algorithm, token_ttl_hours to APIConfig; api.token_ttl_hours to HOT_RELOAD_SAFE_PATHS
- `src/cyberred/api/server.py` — Wired auth router, token store lifespan, create_app accepts token_store
- `src/cyberred/api/__init__.py` — Updated exports
