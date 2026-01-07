"""Protocol abstractions for Cyber-Red.

This module provides abstract base classes (protocols) for dependency injection
and component swapping. All protocols use `typing.Protocol` for structural
subtyping with `@runtime_checkable` for isinstance() support.

Protocols:
    AgentProtocol: Interface for all Cyber-Red agents.
    StorageProtocol: Interface for storage backends.
    LLMProviderProtocol: Interface for LLM providers.

Usage:
    from cyberred.protocols import AgentProtocol, StorageProtocol, LLMProviderProtocol
    
    # Check protocol compliance
    assert isinstance(my_agent, AgentProtocol)
"""

from __future__ import annotations

from cyberred.protocols.agent import AgentProtocol
from cyberred.protocols.storage import StorageProtocol
from cyberred.protocols.provider import LLMProviderProtocol

__all__ = [
    "AgentProtocol",
    "StorageProtocol",
    "LLMProviderProtocol",
]
