"""Unit tests for JWT Authentication (Story 14.2).

Tests create_token, decode_token, get_current_user, require_role,
TokenPayload model, and /auth/verify endpoint.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cyberred.api.auth import (
    TokenPayload,
    configure_auth,
    create_token,
    decode_token,
    get_current_user,
    require_role,
    revoke_token,
    router as auth_router,
    _get_config,
    _get_token_store,
)
from cyberred.api.token_store import TokenStore
from cyberred.core.config import APIConfig
from cyberred.core.exceptions import AuthenticationError, ConfigurationError


# ---- Fixtures ----

SECRET_KEY = "test-secret-key-for-unit-tests-only"


@pytest.fixture
async def token_store(tmp_path):
    """Create and initialize a TokenStore for testing."""
    db_path = str(tmp_path / "test_auth_tokens.db")
    store = TokenStore(db_path)
    await store.initialize()
    yield store
    await store.close()


@pytest.fixture
def api_config():
    """Create an APIConfig with JWT settings for testing."""
    return APIConfig(
        jwt_secret_key=SECRET_KEY,
        jwt_algorithm="HS256",
        token_ttl_hours=24,
    )


@pytest.fixture
async def configured_auth(api_config, token_store):
    """Configure the auth module for testing and clean up after."""
    import cyberred.api.auth as auth_module

    old_store = auth_module._token_store
    old_config = auth_module._api_config
    configure_auth(api_config, token_store)
    yield api_config, token_store
    # Restore previous state
    auth_module._token_store = old_store
    auth_module._api_config = old_config


@pytest.fixture
def test_app(api_config, token_store):
    """Create a FastAPI test app with auth wired in."""
    import cyberred.api.auth as auth_module

    old_store = auth_module._token_store
    old_config = auth_module._api_config
    configure_auth(api_config, token_store)

    app = FastAPI()
    app.include_router(auth_router)
    yield app

    auth_module._token_store = old_store
    auth_module._api_config = old_config


@pytest.fixture
def test_client(test_app):
    """Create a TestClient for the test app."""
    return TestClient(test_app)


# ---- TokenPayload Tests ----


class TestTokenPayload:
    """Tests for TokenPayload Pydantic model."""

    def test_token_payload_creation(self):
        """TokenPayload can be created with valid data."""
        now = int(time.time())
        payload = TokenPayload(sub="tok-123", role="operator", exp=now + 3600, iat=now)
        assert payload.sub == "tok-123"
        assert payload.role == "operator"
        assert payload.exp == now + 3600
        assert payload.iat == now

    def test_token_payload_deputy_role(self):
        """TokenPayload accepts 'deputy' role."""
        now = int(time.time())
        payload = TokenPayload(sub="tok-456", role="deputy", exp=now + 3600, iat=now)
        assert payload.role == "deputy"


# ---- configure_auth / _get_config / _get_token_store Tests ----


class TestConfigureAuth:
    """Tests for auth module configuration."""

    def test_get_config_not_configured(self):
        """_get_config raises ConfigurationError when not configured."""
        import cyberred.api.auth as auth_module

        old = auth_module._api_config
        auth_module._api_config = None
        try:
            with pytest.raises(ConfigurationError):
                _get_config()
        finally:
            auth_module._api_config = old

    def test_get_token_store_not_configured(self):
        """_get_token_store raises ConfigurationError when not configured."""
        import cyberred.api.auth as auth_module

        old = auth_module._token_store
        auth_module._token_store = None
        try:
            with pytest.raises(ConfigurationError):
                _get_token_store()
        finally:
            auth_module._token_store = old

    async def test_configure_auth_sets_globals(self, api_config, token_store):
        """configure_auth sets module-level config and store."""
        import cyberred.api.auth as auth_module

        old_store = auth_module._token_store
        old_config = auth_module._api_config
        try:
            configure_auth(api_config, token_store)
            assert auth_module._api_config is api_config
            assert auth_module._token_store is token_store
        finally:
            auth_module._token_store = old_store
            auth_module._api_config = old_config


# ---- create_token Tests ----


class TestCreateToken:
    """Tests for create_token()."""

    async def test_create_operator_token(self, configured_auth):
        """create_token creates a valid JWT for operator role."""
        token = await create_token(role="operator")
        assert isinstance(token, str)
        # Decode to verify claims
        claims = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        assert claims["role"] == "operator"
        assert "sub" in claims
        assert "exp" in claims
        assert "iat" in claims

    async def test_create_deputy_token(self, configured_auth):
        """create_token creates a valid JWT for deputy role."""
        token = await create_token(role="deputy")
        claims = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        assert claims["role"] == "deputy"

    async def test_create_token_custom_ttl(self, configured_auth):
        """create_token respects custom ttl_hours."""
        token = await create_token(role="operator", ttl_hours=1)
        claims = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        # Expiration should be ~1 hour from now
        assert claims["exp"] - claims["iat"] == 3600

    async def test_create_token_stores_metadata(self, configured_auth):
        """create_token stores token metadata in TokenStore."""
        _, store = configured_auth
        token = await create_token(role="operator")
        claims = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        token_id = claims["sub"]
        stored = await store.get_token(token_id)
        assert stored is not None
        assert stored["role"] == "operator"
        assert stored["revoked"] is False

    async def test_create_token_invalid_role(self, configured_auth):
        """create_token raises ValueError for invalid role."""
        with pytest.raises(ValueError, match="Invalid role"):
            await create_token(role="admin")

    async def test_create_token_empty_secret_key(self, token_store):
        """create_token raises ConfigurationError when jwt_secret_key is empty."""
        import cyberred.api.auth as auth_module

        old_store = auth_module._token_store
        old_config = auth_module._api_config
        try:
            empty_config = APIConfig(jwt_secret_key="")
            configure_auth(empty_config, token_store)
            with pytest.raises(ConfigurationError, match="jwt_secret_key"):
                await create_token(role="operator")
        finally:
            auth_module._token_store = old_store
            auth_module._api_config = old_config

    async def test_create_token_custom_secret_and_algorithm(self, configured_auth):
        """create_token accepts custom secret_key and algorithm overrides."""
        custom_key = "custom-secret"
        token = await create_token(
            role="operator", secret_key=custom_key, algorithm="HS256"
        )
        claims = jwt.decode(token, custom_key, algorithms=["HS256"])
        assert claims["role"] == "operator"


# ---- decode_token Tests ----


class TestDecodeToken:
    """Tests for decode_token()."""

    async def test_decode_valid_token(self, configured_auth):
        """decode_token returns TokenPayload for valid token."""
        token = await create_token(role="operator")
        payload = await decode_token(token)
        assert isinstance(payload, TokenPayload)
        assert payload.role == "operator"

    async def test_decode_expired_token(self, configured_auth):
        """decode_token raises AuthenticationError for expired token."""
        # Create a token that's already expired
        now = int(time.time())
        claims = {"sub": "expired-tok", "role": "operator", "iat": now - 7200, "exp": now - 3600}
        token = jwt.encode(claims, SECRET_KEY, algorithm="HS256")
        with pytest.raises(AuthenticationError, match="expired"):
            await decode_token(token)

    async def test_decode_invalid_signature(self, configured_auth):
        """decode_token raises AuthenticationError for wrong signature."""
        token = jwt.encode(
            {"sub": "bad", "role": "operator", "iat": int(time.time()), "exp": int(time.time()) + 3600},
            "wrong-secret",
            algorithm="HS256",
        )
        with pytest.raises(AuthenticationError, match="Invalid token"):
            await decode_token(token)

    async def test_decode_malformed_token(self, configured_auth):
        """decode_token raises AuthenticationError for malformed token."""
        with pytest.raises(AuthenticationError, match="Invalid token"):
            await decode_token("not-a-jwt-token")

    async def test_decode_missing_sub_claim(self, configured_auth):
        """decode_token raises AuthenticationError when sub claim is missing."""
        now = int(time.time())
        token = jwt.encode(
            {"role": "operator", "iat": now, "exp": now + 3600},
            SECRET_KEY,
            algorithm="HS256",
        )
        with pytest.raises(AuthenticationError, match="sub"):
            await decode_token(token)

    async def test_decode_missing_role_claim(self, configured_auth):
        """decode_token raises AuthenticationError when role claim is missing."""
        now = int(time.time())
        token = jwt.encode(
            {"sub": "tok-no-role", "iat": now, "exp": now + 3600},
            SECRET_KEY,
            algorithm="HS256",
        )
        with pytest.raises(AuthenticationError, match="role"):
            await decode_token(token)

    async def test_decode_invalid_role_claim(self, configured_auth):
        """decode_token raises AuthenticationError for invalid role value."""
        now = int(time.time())
        token = jwt.encode(
            {"sub": "tok-bad-role", "role": "admin", "iat": now, "exp": now + 3600},
            SECRET_KEY,
            algorithm="HS256",
        )
        with pytest.raises(AuthenticationError, match="Invalid role"):
            await decode_token(token)

    async def test_decode_revoked_token(self, configured_auth):
        """decode_token raises AuthenticationError for revoked token."""
        token = await create_token(role="operator")
        claims = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        token_id = claims["sub"]
        await revoke_token(token_id)
        with pytest.raises(AuthenticationError, match="revoked"):
            await decode_token(token)

    async def test_decode_token_custom_secret(self, configured_auth):
        """decode_token accepts custom secret_key override."""
        custom_key = "my-custom-key"
        token = await create_token(role="deputy", secret_key=custom_key)
        payload = await decode_token(token, secret_key=custom_key)
        assert payload.role == "deputy"


# ---- revoke_token Tests ----


class TestRevokeToken:
    """Tests for revoke_token()."""

    async def test_revoke_existing_token(self, configured_auth):
        """revoke_token returns True for existing token."""
        token = await create_token(role="operator")
        claims = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        result = await revoke_token(claims["sub"])
        assert result is True

    async def test_revoke_nonexistent_token(self, configured_auth):
        """revoke_token returns False for nonexistent token."""
        result = await revoke_token("nonexistent-id")
        assert result is False


# ---- get_current_user / FastAPI Endpoint Tests ----


class TestGetCurrentUser:
    """Tests for get_current_user FastAPI dependency and /auth/verify endpoint."""

    async def test_verify_without_token_returns_401(self, test_client):
        """GET /auth/verify without Authorization header returns 401."""
        response = test_client.get("/auth/verify")
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    async def test_verify_with_valid_token(self, test_client, configured_auth):
        """GET /auth/verify with valid token returns 200 with claims."""
        token = await create_token(role="operator")
        response = test_client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "operator"
        assert "sub" in data
        assert "exp" in data
        assert "iat" in data

    async def test_verify_with_invalid_token(self, test_client):
        """GET /auth/verify with invalid token returns 401."""
        response = test_client.get(
            "/auth/verify",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired token"

    async def test_verify_with_expired_token(self, test_client, configured_auth):
        """GET /auth/verify with expired token returns 401."""
        now = int(time.time())
        claims = {"sub": "exp-tok", "role": "operator", "iat": now - 7200, "exp": now - 3600}
        token = jwt.encode(claims, SECRET_KEY, algorithm="HS256")
        response = test_client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired token"

    async def test_verify_with_revoked_token(self, test_client, configured_auth):
        """GET /auth/verify with revoked token returns 401."""
        token = await create_token(role="operator")
        claims = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        await revoke_token(claims["sub"])
        response = test_client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    async def test_verify_deputy_role(self, test_client, configured_auth):
        """GET /auth/verify correctly shows deputy role."""
        token = await create_token(role="deputy")
        response = test_client.get(
            "/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "deputy"


# ---- require_role Tests ----


class TestRequireRole:
    """Tests for require_role dependency factory."""

    async def test_require_role_matching(self, configured_auth):
        """require_role allows access when role matches."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        import cyberred.api.auth as auth_module

        app = FastAPI()

        @app.get("/operator-only")
        async def operator_endpoint(user=pytest.importorskip("fastapi").Depends(require_role("operator"))):
            return {"role": user.role}

        client = TestClient(app)
        token = await create_token(role="operator")
        response = client.get(
            "/operator-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "operator"

    async def test_require_role_mismatch(self, configured_auth):
        """require_role returns 403 when role doesn't match."""
        from fastapi import Depends, FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()

        @app.get("/operator-only")
        async def operator_endpoint(user=Depends(require_role("operator"))):
            return {"role": user.role}

        client = TestClient(app)
        token = await create_token(role="deputy")
        response = client.get(
            "/operator-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert "operator" in response.json()["detail"]


class TestGetCurrentUserConfigError:
    """Tests for get_current_user when auth module is not configured."""

    async def test_get_current_user_config_error_returns_401(self):
        """get_current_user returns 401 when auth module not configured (ConfigurationError)."""
        import cyberred.api.auth as auth_module

        old_store = auth_module._token_store
        old_config = auth_module._api_config
        auth_module._token_store = None
        auth_module._api_config = None
        try:
            app = FastAPI()
            app.include_router(auth_router)
            client = TestClient(app)
            response = client.get(
                "/auth/verify",
                headers={"Authorization": "Bearer some-token"},
            )
            assert response.status_code == 401
            assert response.json()["detail"] == "Not authenticated"
        finally:
            auth_module._token_store = old_store
            auth_module._api_config = old_config
