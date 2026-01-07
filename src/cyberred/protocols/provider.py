"""LLM Provider protocol for Cyber-Red.

This module defines the LLMProviderProtocol interface that all LLM
providers must implement. Uses `typing.Protocol` for structural subtyping.

Per architecture (lines 788-792, 990):
- Protocols belong in `src/cyberred/protocols/`
- All LLM calls should go through implementations of this protocol

NFR29 requires graceful degradation when LLM providers are unavailable.
The `is_available()` method enables circuit-breaker patterns.

Usage:
    from cyberred.protocols import LLMProviderProtocol
    
    class NIMProvider:
        # Implement all protocol methods...
        pass
    
    provider = NIMProvider()
    assert isinstance(provider, LLMProviderProtocol)
"""

from __future__ import annotations

from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class LLMProviderProtocol(Protocol):
    """Protocol for LLM providers in Cyber-Red.
    
    All LLM provider implementations must satisfy this interface. The
    protocol supports both free-form text generation and structured
    output generation with JSON schema validation.
    
    The architecture requires a 30 RPM global rate limit shared across
    the swarm. Implementations should respect `get_rate_limit()` values.
    
    NFR29 requires graceful degradation. When a provider is unavailable,
    `is_available()` should return False and callers should fall back
    to other providers or queue requests.
    
    Methods:
        generate: Generate text completion.
        generate_structured: Generate structured output matching a schema.
        get_model_name: Return model identifier.
        get_rate_limit: Return rate limit in requests per minute.
        get_token_usage: Return usage metrics.
        is_available: Check provider availability.
    
    Note:
        Implementations do NOT need to inherit from this class.
    """
    
    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text completion for the given prompt.
        
        Args:
            prompt: Input prompt for the LLM.
            **kwargs: Additional provider-specific parameters
                (e.g., temperature, max_tokens).
                
        Returns:
            Generated text response.
            
        Raises:
            ConfigurationError: If provider is not configured.
        """
        ...
    
    async def generate_structured(
        self, prompt: str, schema: Dict, **kwargs: Any
    ) -> Dict:
        """Generate structured output matching the given schema.
        
        Args:
            prompt: Input prompt for the LLM.
            schema: JSON schema for the expected output structure.
            **kwargs: Additional provider-specific parameters.
            
        Returns:
            Dictionary matching the provided schema.
            
        Raises:
            ValueError: If output doesn't match schema.
        """
        ...
    
    def get_model_name(self) -> str:
        """Return the model identifier.
        
        Returns:
            Model name string (e.g., 'nvidia/nemotron-70b').
        """
        ...
    
    def get_rate_limit(self) -> int:
        """Return the rate limit in requests per minute.
        
        Per architecture, global rate limit is 30 RPM shared across swarm.
        
        Returns:
            Maximum requests per minute for this provider.
        """
        ...
    
    def get_token_usage(self) -> Dict:
        """Return usage metrics for observability.
        
        Tracks prompt tokens, completion tokens, and total tokens
        for monitoring and cost management.
        
        Returns:
            Dictionary with keys:
                - 'prompt_tokens': int
                - 'completion_tokens': int  
                - 'total_tokens': int
        """
        ...
    
    def is_available(self) -> bool:
        """Check if the provider is currently available.
        
        Used for circuit-breaker patterns per NFR29. When False,
        callers should fall back to other providers or queue requests.
        
        Returns:
            True if provider is available for requests, False otherwise.
        """
        ...
