"""Storage protocol for Cyber-Red.

This module defines the StorageProtocol interface that all storage
backends must implement. Uses `typing.Protocol` for structural subtyping.

Per architecture (lines 788-792, 989):
- Protocols belong in `src/cyberred/protocols/`
- All Redis access should go through implementations of this protocol

Usage:
    from cyberred.protocols import StorageProtocol
    
    class RedisStorage:
        # Implement all protocol methods...
        pass
    
    storage = RedisStorage()
    assert isinstance(storage, StorageProtocol)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class StorageProtocol(Protocol):
    """Protocol for storage backends in Cyber-Red.
    
    All storage implementations must satisfy this interface. The protocol
    provides async methods for key-value operations with support for
    prefixed key listing.
    
    Implementations may use Redis, SQLite, or other backends while
    conforming to this common interface.
    
    Methods:
        save: Persist data with a key.
        load: Retrieve data by key.
        delete: Remove data by key.
        exists: Check if key exists.
        list_keys: List keys matching a prefix.
    
    Note:
        All methods are async to support non-blocking I/O.
        Implementations do NOT need to inherit from this class.
    """
    
    async def save(self, key: str, data: Dict) -> bool:
        """Persist data with the given key.
        
        Args:
            key: Unique identifier for the data.
            data: Dictionary of data to persist.
            
        Returns:
            True if save succeeded, False otherwise.
            
        Raises:
            ConfigurationError: If storage is not configured.
        """
        ...
    
    async def load(self, key: str) -> Optional[Dict]:
        """Retrieve data by key.
        
        Args:
            key: Key to lookup.
            
        Returns:
            Dictionary of data if found, None if key doesn't exist.
        """
        ...
    
    async def delete(self, key: str) -> bool:
        """Remove data by key.
        
        Args:
            key: Key to delete.
            
        Returns:
            True if deletion succeeded (or key didn't exist), False on error.
        """
        ...
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in storage.
        
        Args:
            key: Key to check.
            
        Returns:
            True if key exists, False otherwise.
        """
        ...
    
    async def list_keys(self, prefix: str) -> List[str]:
        """List all keys matching a prefix.
        
        Warning:
            This method returns all matching keys in memory. For large 
            datasets (e.g., millions of keys), this may be performant 
            intensive. Implementations should consider strict limits or
            pagination if available.
        
        Args:
            prefix: Key prefix to match (e.g., 'findings:' for all findings).
            
        Returns:
            List of matching keys. Empty list if no matches.
        """
        ...
