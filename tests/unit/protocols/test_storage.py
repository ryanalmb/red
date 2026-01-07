"""Unit tests for StorageProtocol.

Tests verify:
1. Compliant classes pass isinstance() checks
2. Non-compliant classes fail isinstance() checks
3. All async methods have correct signatures
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pytest

from cyberred.protocols import StorageProtocol


class CompliantStorage:
    """A minimal compliant storage implementation for testing."""
    
    def __init__(self) -> None:
        self._data: Dict[str, Dict] = {}
    
    async def save(self, key: str, data: Dict) -> bool:
        """Persist data with the given key."""
        self._data[key] = data
        return True
    
    async def load(self, key: str) -> Optional[Dict]:
        """Retrieve data by key."""
        return self._data.get(key)
    
    async def delete(self, key: str) -> bool:
        """Remove data by key."""
        if key in self._data:
            del self._data[key]
        return True
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._data
    
    async def list_keys(self, prefix: str) -> List[str]:
        """List keys matching prefix."""
        return [k for k in self._data.keys() if k.startswith(prefix)]


class PartialStorage:
    """A storage missing some required methods."""
    
    async def save(self, key: str, data: Dict) -> bool:
        return True
    
    # Missing: load, delete, exists, list_keys


class NonCompliantClass:
    """A class with no storage methods."""
    
    def do_something(self) -> str:
        return "something"


# -----------------------------------------------------------------------------
# Protocol Compliance Tests
# -----------------------------------------------------------------------------

def test_compliant_storage_passes_isinstance() -> None:
    """Verify that a fully compliant storage passes isinstance check."""
    storage = CompliantStorage()
    assert isinstance(storage, StorageProtocol)


def test_non_compliant_class_fails_isinstance() -> None:
    """Verify that a non-compliant class fails isinstance check."""
    obj = NonCompliantClass()
    assert not isinstance(obj, StorageProtocol)


def test_partial_storage_fails_isinstance() -> None:
    """Verify that a partially compliant class fails isinstance check."""
    storage = PartialStorage()
    assert not isinstance(storage, StorageProtocol)


# -----------------------------------------------------------------------------
# Method Signature Tests
# -----------------------------------------------------------------------------

def test_save_method_exists() -> None:
    """Verify save method exists."""
    storage = CompliantStorage()
    assert hasattr(storage, "save")
    assert callable(storage.save)


def test_load_method_exists() -> None:
    """Verify load method exists."""
    storage = CompliantStorage()
    assert hasattr(storage, "load")
    assert callable(storage.load)


def test_delete_method_exists() -> None:
    """Verify delete method exists."""
    storage = CompliantStorage()
    assert hasattr(storage, "delete")
    assert callable(storage.delete)


def test_exists_method_exists() -> None:
    """Verify exists method exists."""
    storage = CompliantStorage()
    assert hasattr(storage, "exists")
    assert callable(storage.exists)


def test_list_keys_method_exists() -> None:
    """Verify list_keys method exists."""
    storage = CompliantStorage()
    assert hasattr(storage, "list_keys")
    assert callable(storage.list_keys)


# -----------------------------------------------------------------------------
# Async Method Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_returns_bool() -> None:
    """Verify save returns a bool."""
    storage = CompliantStorage()
    result = await storage.save("key1", {"data": "value"})
    assert isinstance(result, bool)
    assert result is True


@pytest.mark.asyncio
async def test_load_returns_dict_or_none() -> None:
    """Verify load returns dict or None."""
    storage = CompliantStorage()
    
    # Key doesn't exist
    result = await storage.load("nonexistent")
    assert result is None
    
    # Key exists
    await storage.save("key2", {"data": "value"})
    result = await storage.load("key2")
    assert isinstance(result, dict)
    assert result == {"data": "value"}


@pytest.mark.asyncio
async def test_delete_returns_bool() -> None:
    """Verify delete returns a bool."""
    storage = CompliantStorage()
    await storage.save("key3", {"data": "value"})
    result = await storage.delete("key3")
    assert isinstance(result, bool)
    assert result is True


@pytest.mark.asyncio
async def test_exists_returns_bool() -> None:
    """Verify exists returns a bool."""
    storage = CompliantStorage()
    
    # Key doesn't exist
    result = await storage.exists("nonexistent")
    assert result is False
    
    # Key exists
    await storage.save("key4", {"data": "value"})
    result = await storage.exists("key4")
    assert result is True


@pytest.mark.asyncio
async def test_list_keys_returns_list() -> None:
    """Verify list_keys returns a list."""
    storage = CompliantStorage()
    await storage.save("prefix:key1", {"data": "1"})
    await storage.save("prefix:key2", {"data": "2"})
    await storage.save("other:key3", {"data": "3"})
    
    result = await storage.list_keys("prefix:")
    assert isinstance(result, list)
    assert len(result) == 2
    assert "prefix:key1" in result
    assert "prefix:key2" in result
