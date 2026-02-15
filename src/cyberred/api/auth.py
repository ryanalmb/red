"""JWT Token Authentication (Story 14.2).

Provides token creation, validation, and FastAPI authentication dependencies
for the Cyber-Red REST API (FR48).

Architecture:
- Tokens are JWTs signed with HS256 (configurable algorithm).
- Token metadata stored in SQLite via TokenStore for revocation tracking.
- FastAPI Depends() pattern for per-endpoint auth requirements.
- Two roles: 'operator' (full control) and 'deputy' (scoped actions).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import jwt
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from cyberred.core.config import APIConfig
from cyberred.core.exceptions import AuthenticationError, ConfigurationError
from cyberred.api.token_store import TokenStore

log = structlog.get_logger()

# FastAPI security scheme
security = HTTPBearer(auto_error=False)

# Module-level token store and config references (set during app wiring)
_token_store: TokenStore | None = None
_api_config: APIConfig | None = None

# Auth router for /auth/verify endpoint
router = APIRouter()


class TokenPayload(BaseModel):
    """JWT token payload model.

    Attributes:
        sub: Token ID (UUID string).
        role: Token role ('operator' or 'deputy').
        exp: Expiration timestamp (Unix epoch).
        iat: Issued-at timestamp (Unix epoch).
    """

    sub: str
    role: str
    exp: int
    iat: int


def configure_auth(config: APIConfig, token_store: TokenStore) -> None:
    """Configure the auth module with API config and token store.

    Called during app startup to wire dependencies.

    Args:
        config: API configuration with JWT settings.
        token_store: Initialized TokenStore instance.
    """
    global _token_store, _api_config
    _token_store = token_store
    _api_config = config


def _get_config() -> APIConfig:
    """Get the current API config, raising if not configured."""
    if _api_config is None:
        raise ConfigurationError(
            config_path="api",
            key="jwt_secret_key",
            message="Auth module not configured. Call configure_auth() first.",
        )
    return _api_config


def _get_token_store() -> TokenStore:
    """Get the current token store, raising if not configured."""
    if _token_store is None:
        raise ConfigurationError(
            config_path="api",
            key="token_store",
            message="Auth module not configured. Call configure_auth() first.",
        )
    return _token_store


async def create_token(
    role: str,
    ttl_hours: int | None = None,
    secret_key: str | None = None,
    algorithm: str | None = None,
) -> str:
    """Create a new JWT token.

    Args:
        role: Token role ('operator' or 'deputy').
        ttl_hours: Token TTL in hours. Uses config default if None.
        secret_key: JWT secret key. Uses config value if None.
        algorithm: JWT algorithm. Uses config value if None.

    Returns:
        Encoded JWT token string.

    Raises:
        ConfigurationError: If jwt_secret_key is empty.
        ValueError: If role is not 'operator' or 'deputy'.
    """
    config = _get_config()
    store = _get_token_store()

    key = secret_key or config.jwt_secret_key
    if not key:
        raise ConfigurationError(
            config_path="api",
            key="jwt_secret_key",
            message="jwt_secret_key must be set for token creation",
        )

    alg = algorithm or config.jwt_algorithm
    ttl = ttl_hours if ttl_hours is not None else config.token_ttl_hours

    if role not in ("operator", "deputy"):
        raise ValueError(f"Invalid role: {role!r}. Must be 'operator' or 'deputy'.")

    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=ttl)
    token_id = str(uuid.uuid4())

    claims: dict[str, Any] = {
        "sub": token_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    # Sign token first — if encoding fails, don't leave orphan metadata in store
    token = jwt.encode(claims, key, algorithm=alg)

    # Store metadata after successful signing
    await store.store_token(
        token_id=token_id,
        role=role,
        created_at=now.isoformat(),
        expires_at=exp.isoformat(),
    )

    log.info("token_created", token_id=token_id, role=role, ttl_hours=ttl)
    return token


async def decode_token(
    token: str,
    secret_key: str | None = None,
    algorithm: str | None = None,
) -> TokenPayload:
    """Decode and validate a JWT token.

    Verifies signature, expiration, and revocation status.

    Args:
        token: Encoded JWT token string.
        secret_key: JWT secret key. Uses config value if None.
        algorithm: JWT algorithm. Uses config value if None.

    Returns:
        TokenPayload with decoded claims.

    Raises:
        AuthenticationError: If token is invalid, expired, or revoked.
    """
    config = _get_config()
    store = _get_token_store()

    key = secret_key or config.jwt_secret_key
    alg = algorithm or config.jwt_algorithm

    try:
        payload = jwt.decode(token, key, algorithms=[alg])
    except jwt.ExpiredSignatureError:
        log.warning("token_auth_failed", reason="expired")
        raise AuthenticationError(reason="Token has expired")
    except jwt.InvalidTokenError as e:
        log.warning("token_auth_failed", reason="invalid", error=str(e))
        raise AuthenticationError(reason="Invalid token")

    token_id = payload.get("sub")
    if not token_id:
        raise AuthenticationError(reason="Token missing 'sub' claim")

    # Validate role claim exists and has a valid value
    role = payload.get("role")
    if not role:
        raise AuthenticationError(reason="Token missing 'role' claim")
    if role not in ("operator", "deputy"):
        raise AuthenticationError(reason=f"Invalid role in token: {role!r}")

    # Check revocation
    revoked = await store.is_revoked(token_id)
    if revoked:
        log.warning("token_auth_failed", reason="revoked", token_id=token_id)
        raise AuthenticationError(reason="Token has been revoked", token_id=token_id)

    return TokenPayload(
        sub=payload["sub"],
        role=role,
        exp=payload["exp"],
        iat=payload["iat"],
    )


async def revoke_token(token_id: str) -> bool:
    """Revoke a token by ID.

    Args:
        token_id: Token ID to revoke.

    Returns:
        True if token was found and revoked, False otherwise.
    """
    store = _get_token_store()
    # Note: TokenStore.revoke_token already logs token_revoked
    return await store.revoke_token(token_id)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> TokenPayload:
    """FastAPI dependency for JWT authentication.

    Extracts Bearer token from Authorization header,
    validates it, and returns the token payload.

    Args:
        credentials: HTTP Bearer credentials from request.

    Returns:
        TokenPayload with authenticated user info.

    Raises:
        HTTPException: 401 if token is missing, invalid, expired, or revoked.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = await decode_token(credentials.credentials)
        return payload
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    except ConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )


def require_role(role: str):
    """Dependency factory for role-based access control.

    Returns a FastAPI dependency that checks the user's role.

    Args:
        role: Required role ('operator' or 'deputy').

    Returns:
        FastAPI dependency function.
    """

    async def _check_role(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        if current_user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' required",
            )
        return current_user

    return _check_role


@router.get("/auth/verify")
async def verify_token(
    current_user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Verify token and return claims (for integration testing).

    This endpoint requires authentication and returns the decoded
    token payload, useful for verifying auth is working.

    Returns:
        Dict with token claims: sub, role, exp, iat.
    """
    return {
        "sub": current_user.sub,
        "role": current_user.role,
        "exp": current_user.exp,
        "iat": current_user.iat,
    }
