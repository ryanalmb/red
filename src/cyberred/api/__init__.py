"""Cyber-Red REST API module.

FastAPI-based REST API server for external integrations (FR48).
"""

from cyberred.api.auth import (
    TokenPayload,
    configure_auth,
    create_token,
    decode_token,
    get_current_user,
    require_role,
    revoke_token,
)
from cyberred.api.server import APIServer, create_app
from cyberred.api.token_store import TokenStore

__all__ = [
    "APIServer",
    "TokenPayload",
    "TokenStore",
    "configure_auth",
    "create_app",
    "create_token",
    "decode_token",
    "get_current_user",
    "require_role",
    "revoke_token",
]
