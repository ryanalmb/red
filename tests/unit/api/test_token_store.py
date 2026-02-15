"""Unit tests for TokenStore (Story 14.2).

Tests SQLite token metadata storage: create_table, store_token,
get_token, revoke_token, is_revoked.
"""

from __future__ import annotations

import os

import pytest

from cyberred.api.token_store import TokenStore


@pytest.fixture
async def token_store(tmp_path):
    """Create and initialize a TokenStore with a temp database."""
    db_path = str(tmp_path / "test_tokens.db")
    store = TokenStore(db_path)
    await store.initialize()
    yield store
    await store.close()


class TestTokenStoreInitialize:
    """Tests for TokenStore initialization."""

    async def test_initialize_creates_db_file(self, tmp_path):
        """TokenStore.initialize() creates the SQLite database file."""
        db_path = str(tmp_path / "new_tokens.db")
        store = TokenStore(db_path)
        await store.initialize()
        assert os.path.exists(db_path)
        await store.close()

    async def test_initialize_idempotent(self, tmp_path):
        """Calling initialize() twice does not raise."""
        db_path = str(tmp_path / "tokens.db")
        store = TokenStore(db_path)
        await store.initialize()
        await store.initialize()  # Should not raise
        await store.close()

    async def test_close_idempotent(self, tmp_path):
        """Calling close() multiple times does not raise."""
        db_path = str(tmp_path / "tokens.db")
        store = TokenStore(db_path)
        await store.initialize()
        await store.close()
        await store.close()  # Should not raise


class TestTokenStoreOperations:
    """Tests for TokenStore CRUD operations."""

    async def test_store_and_get_token(self, token_store):
        """store_token() stores metadata, get_token() retrieves it."""
        await token_store.store_token(
            token_id="tok-1",
            role="operator",
            created_at="2026-01-01T00:00:00+00:00",
            expires_at="2026-01-02T00:00:00+00:00",
        )
        result = await token_store.get_token("tok-1")
        assert result is not None
        assert result["token_id"] == "tok-1"
        assert result["role"] == "operator"
        assert result["created_at"] == "2026-01-01T00:00:00+00:00"
        assert result["expires_at"] == "2026-01-02T00:00:00+00:00"
        assert result["revoked"] is False
        assert result["revoked_at"] is None

    async def test_get_token_not_found(self, token_store):
        """get_token() returns None for unknown token_id."""
        result = await token_store.get_token("nonexistent")
        assert result is None

    async def test_store_deputy_token(self, token_store):
        """store_token() accepts 'deputy' role."""
        await token_store.store_token(
            token_id="tok-deputy",
            role="deputy",
            created_at="2026-01-01T00:00:00+00:00",
            expires_at="2026-01-02T00:00:00+00:00",
        )
        result = await token_store.get_token("tok-deputy")
        assert result is not None
        assert result["role"] == "deputy"

    async def test_revoke_token_success(self, token_store):
        """revoke_token() marks token as revoked and returns True."""
        await token_store.store_token(
            token_id="tok-rev",
            role="operator",
            created_at="2026-01-01T00:00:00+00:00",
            expires_at="2026-01-02T00:00:00+00:00",
        )
        result = await token_store.revoke_token("tok-rev")
        assert result is True

        token = await token_store.get_token("tok-rev")
        assert token is not None
        assert token["revoked"] is True
        assert token["revoked_at"] is not None

    async def test_revoke_token_not_found(self, token_store):
        """revoke_token() returns False for unknown token_id."""
        result = await token_store.revoke_token("nonexistent")
        assert result is False

    async def test_revoke_already_revoked(self, token_store):
        """revoke_token() returns False when already revoked."""
        await token_store.store_token(
            token_id="tok-double",
            role="operator",
            created_at="2026-01-01T00:00:00+00:00",
            expires_at="2026-01-02T00:00:00+00:00",
        )
        assert await token_store.revoke_token("tok-double") is True
        assert await token_store.revoke_token("tok-double") is False

    async def test_is_revoked_false(self, token_store):
        """is_revoked() returns False for non-revoked token."""
        await token_store.store_token(
            token_id="tok-active",
            role="operator",
            created_at="2026-01-01T00:00:00+00:00",
            expires_at="2026-01-02T00:00:00+00:00",
        )
        assert await token_store.is_revoked("tok-active") is False

    async def test_is_revoked_true(self, token_store):
        """is_revoked() returns True after revocation."""
        await token_store.store_token(
            token_id="tok-revoked",
            role="operator",
            created_at="2026-01-01T00:00:00+00:00",
            expires_at="2026-01-02T00:00:00+00:00",
        )
        await token_store.revoke_token("tok-revoked")
        assert await token_store.is_revoked("tok-revoked") is True

    async def test_is_revoked_unknown_token_fail_closed(self, token_store):
        """is_revoked() returns True for unknown tokens (fail-closed)."""
        assert await token_store.is_revoked("nonexistent") is True


class TestTokenStoreNotInitialized:
    """Tests for operations before initialize()."""

    async def test_store_token_not_initialized(self, tmp_path):
        """store_token() raises RuntimeError when not initialized."""
        store = TokenStore(str(tmp_path / "test.db"))
        with pytest.raises(RuntimeError, match="not initialized"):
            await store.store_token("t", "operator", "c", "e")

    async def test_get_token_not_initialized(self, tmp_path):
        """get_token() raises RuntimeError when not initialized."""
        store = TokenStore(str(tmp_path / "test.db"))
        with pytest.raises(RuntimeError, match="not initialized"):
            await store.get_token("t")

    async def test_revoke_token_not_initialized(self, tmp_path):
        """revoke_token() raises RuntimeError when not initialized."""
        store = TokenStore(str(tmp_path / "test.db"))
        with pytest.raises(RuntimeError, match="not initialized"):
            await store.revoke_token("t")

    async def test_is_revoked_not_initialized(self, tmp_path):
        """is_revoked() raises RuntimeError when not initialized."""
        store = TokenStore(str(tmp_path / "test.db"))
        with pytest.raises(RuntimeError, match="not initialized"):
            await store.is_revoked("t")
