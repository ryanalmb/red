"""Integration tests for API Token Authentication (Story 14.2).

Tests the full auth flow using create_app() with real TokenStore and JWT.
No mocks — tests actual production code end-to-end.

Covers AC#7:
- Valid token grants access to protected endpoint
- Expired tokens are rejected
- Revoked tokens are rejected
- Missing/malformed tokens are rejected
- Role claim is correctly propagated
- /health remains unauthenticated
- Full lifecycle: create → authenticate → revoke → reject
"""

from __future__ import annotations

import time

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from cyberred.api.auth import (
    configure_auth,
    create_token,
    decode_token,
    revoke_token,
)
from cyberred.api.server import create_app
from cyberred.api.token_store import TokenStore
from cyberred.core.config import APIConfig

SECRET_KEY = "integration-test-secret-key-very-strong"


@pytest.fixture
async def auth_setup(tmp_path):
    """Set up a full auth-enabled app with real TokenStore."""
    import cyberred.api.auth as auth_module

    db_path = str(tmp_path / "integration_tokens.db")
    token_store = TokenStore(db_path)
    await token_store.initialize()

    config = APIConfig(
        jwt_secret_key=SECRET_KEY,
        jwt_algorithm="HS256",
        token_ttl_hours=24,
    )

    # Save old state
    old_store = auth_module._token_store
    old_config = auth_module._api_config

    app = create_app(config=config, token_store=token_store)
    client = TestClient(app)

    yield client, config, token_store

    # Restore state
    auth_module._token_store = old_store
    auth_module._api_config = old_config
    await token_store.close()


@pytest.mark.integration
class TestAuthIntegrationFullFlow:
    """Integration test: full auth lifecycle."""

    async def test_create_authenticate_revoke_reject(self, auth_setup):
        """Full lifecycle: create token → use it → revoke → verify rejected."""
        client, config, store = auth_setup

        # 1. Create token
        token = await create_token(role="operator")
        assert isinstance(token, str)

        # 2. Use token to access protected endpoint
        response = client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "operator"
        token_id = data["sub"]

        # 3. Revoke token
        revoked = await revoke_token(token_id)
        assert revoked is True

        # 4. Verify revoked token is rejected
        response = client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestAuthIntegrationValidToken:
    """Integration tests: valid token grants access."""

    async def test_valid_operator_token_grants_access(self, auth_setup):
        """Valid operator token grants access to protected endpoint."""
        client, _, _ = auth_setup
        token = await create_token(role="operator")
        response = client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "operator"
        assert "sub" in response.json()
        assert "exp" in response.json()
        assert "iat" in response.json()

    async def test_valid_deputy_token_grants_access(self, auth_setup):
        """Valid deputy token grants access and role is propagated."""
        client, _, _ = auth_setup
        token = await create_token(role="deputy")
        response = client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "deputy"


@pytest.mark.integration
class TestAuthIntegrationRejections:
    """Integration tests: various rejection scenarios."""

    async def test_missing_token_returns_401(self, auth_setup):
        """Request without Authorization header returns 401."""
        client, _, _ = auth_setup
        response = client.get("/auth/verify")
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    async def test_malformed_token_returns_401(self, auth_setup):
        """Malformed/invalid JWT returns 401."""
        client, _, _ = auth_setup
        response = client.get(
            "/auth/verify",
            headers={"Authorization": "Bearer not-a-valid-jwt"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired token"

    async def test_expired_token_returns_401(self, auth_setup):
        """Expired JWT token returns 401."""
        client, _, store = auth_setup
        now = int(time.time())
        token_id = "expired-integration-tok"
        # Store metadata first so revocation check passes
        await store.store_token(
            token_id=token_id,
            role="operator",
            created_at="2026-01-01T00:00:00+00:00",
            expires_at="2026-01-01T01:00:00+00:00",
        )
        claims = {
            "sub": token_id,
            "role": "operator",
            "iat": now - 7200,
            "exp": now - 3600,
        }
        token = pyjwt.encode(claims, SECRET_KEY, algorithm="HS256")
        response = client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired token"

    async def test_revoked_token_returns_401(self, auth_setup):
        """Revoked token returns 401."""
        client, _, _ = auth_setup
        token = await create_token(role="operator")
        claims = pyjwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        await revoke_token(claims["sub"])
        response = client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    async def test_wrong_secret_key_returns_401(self, auth_setup):
        """Token signed with wrong key returns 401."""
        client, _, _ = auth_setup
        now = int(time.time())
        token = pyjwt.encode(
            {"sub": "wrong-key-tok", "role": "operator", "iat": now, "exp": now + 3600},
            "wrong-secret-key",
            algorithm="HS256",
        )
        response = client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    async def test_unknown_sub_not_in_store_returns_401(self, auth_setup):
        """Valid JWT with sub not stored in DB is rejected (fail-closed)."""
        client, _, _ = auth_setup
        now = int(time.time())
        # Create a valid JWT but don't store the token_id in the store
        token = pyjwt.encode(
            {"sub": "never-stored-tok", "role": "operator", "iat": now, "exp": now + 3600},
            SECRET_KEY,
            algorithm="HS256",
        )
        response = client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    async def test_invalid_role_in_token_returns_401(self, auth_setup):
        """Valid JWT with invalid role value is rejected."""
        client, _, store = auth_setup
        now = int(time.time())
        token_id = "invalid-role-tok"
        token = pyjwt.encode(
            {"sub": token_id, "role": "admin", "iat": now, "exp": now + 3600},
            SECRET_KEY,
            algorithm="HS256",
        )
        response = client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestAuthIntegrationRolePropagation:
    """Integration tests: role claim propagation."""

    async def test_operator_role_propagated(self, auth_setup):
        """Operator role is correctly returned in /auth/verify."""
        client, _, _ = auth_setup
        token = await create_token(role="operator")
        response = client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "operator"

    async def test_deputy_role_propagated(self, auth_setup):
        """Deputy role is correctly returned in /auth/verify."""
        client, _, _ = auth_setup
        token = await create_token(role="deputy")
        response = client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "deputy"


@pytest.mark.integration
class TestAuthIntegrationHealthEndpoint:
    """Integration tests: /health remains unauthenticated."""

    async def test_health_works_without_auth(self, auth_setup):
        """GET /health works without any authentication."""
        client, _, _ = auth_setup
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "uptime" in data
        assert "version" in data

    async def test_health_no_auth_header_needed(self, auth_setup):
        """GET /health does not require Authorization header."""
        client, _, _ = auth_setup
        # Explicitly no headers
        response = client.get("/health", headers={})
        assert response.status_code == 200


@pytest.mark.integration
class TestAuthIntegrationNoAuthConfig:
    """Integration test: app without jwt_secret_key has no auth endpoints."""

    def test_no_auth_verify_without_jwt_config(self, tmp_path):
        """Without jwt_secret_key, /auth/verify is not registered."""
        config = APIConfig()  # No jwt_secret_key
        app = create_app(config=config)
        client = TestClient(app)
        response = client.get("/auth/verify")
        # Should be 404 since auth router was not registered
        assert response.status_code == 404

    def test_health_works_without_jwt_config(self, tmp_path):
        """GET /health still works when auth is not configured."""
        config = APIConfig()
        app = create_app(config=config)
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
