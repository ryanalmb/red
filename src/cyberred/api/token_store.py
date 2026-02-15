"""SQLite Token Metadata Store (Story 14.2).

Stores JWT token metadata for revocation tracking.
Uses aiosqlite for async SQLite access (non-blocking in FastAPI's event loop).

Token metadata only — the JWT itself is NOT stored (stateless verification
with revocation check).
"""

from __future__ import annotations

from typing import Any

import aiosqlite
import structlog

log = structlog.get_logger()

# SQL schema for token storage
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tokens (
    token_id TEXT PRIMARY KEY,
    role TEXT NOT NULL CHECK(role IN ('operator', 'deputy')),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked INTEGER DEFAULT 0,
    revoked_at TEXT
)
"""


class TokenStore:
    """Async SQLite store for JWT token metadata.

    Tracks token creation and revocation status. Uses WAL mode
    for concurrent reads (consistent with checkpoint storage pattern).

    Attributes:
        _db_path: Path to the SQLite database file.
        _db: aiosqlite connection (set after initialize).
    """

    def __init__(self, db_path: str) -> None:
        """Initialize TokenStore.

        Args:
            db_path: Path to the SQLite database file.
        """
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open database connection and create table if needed.

        Enables WAL mode for concurrent read access.
        Safe to call multiple times — closes existing connection first.
        """
        if self._db is not None:
            await self._db.close()
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute(_CREATE_TABLE_SQL)
        await self._db.commit()
        log.info("token_store_initialized", db_path=self._db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def store_token(
        self,
        token_id: str,
        role: str,
        created_at: str,
        expires_at: str,
    ) -> None:
        """Store token metadata.

        Args:
            token_id: Unique token identifier (UUID).
            role: Token role ('operator' or 'deputy').
            created_at: ISO 8601 UTC creation timestamp.
            expires_at: ISO 8601 UTC expiration timestamp.
        """
        if self._db is None:
            raise RuntimeError("TokenStore not initialized. Call initialize() first.")
        await self._db.execute(
            "INSERT INTO tokens (token_id, role, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token_id, role, created_at, expires_at),
        )
        await self._db.commit()
        log.info("token_created", token_id=token_id, role=role)

    async def get_token(self, token_id: str) -> dict[str, Any] | None:
        """Get token metadata by ID.

        Args:
            token_id: Token identifier to look up.

        Returns:
            Dict with token metadata, or None if not found.
        """
        if self._db is None:
            raise RuntimeError("TokenStore not initialized. Call initialize() first.")
        cursor = await self._db.execute(
            "SELECT token_id, role, created_at, expires_at, revoked, revoked_at "
            "FROM tokens WHERE token_id = ?",
            (token_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return {
            "token_id": row[0],
            "role": row[1],
            "created_at": row[2],
            "expires_at": row[3],
            "revoked": bool(row[4]),
            "revoked_at": row[5],
        }

    async def revoke_token(self, token_id: str) -> bool:
        """Revoke a token by marking it in the store.

        Args:
            token_id: Token identifier to revoke.

        Returns:
            True if token was found and revoked, False if not found.
        """
        if self._db is None:
            raise RuntimeError("TokenStore not initialized. Call initialize() first.")
        from datetime import datetime, timezone

        revoked_at = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            "UPDATE tokens SET revoked = 1, revoked_at = ? WHERE token_id = ? AND revoked = 0",
            (revoked_at, token_id),
        )
        await self._db.commit()
        if cursor.rowcount > 0:
            log.info("token_revoked", token_id=token_id)
            return True
        return False

    async def is_revoked(self, token_id: str) -> bool:
        """Check if a token has been revoked.

        Args:
            token_id: Token identifier to check.

        Returns:
            True if token is revoked, False otherwise.
            Returns True if token is not found (fail-closed).
        """
        if self._db is None:
            raise RuntimeError("TokenStore not initialized. Call initialize() first.")
        cursor = await self._db.execute(
            "SELECT revoked FROM tokens WHERE token_id = ?",
            (token_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return True  # Fail-closed: unknown tokens are treated as revoked
        return bool(row[0])
