"""LLM Provider module for Cyber-Red.

This module provides the abstract base class and data models for LLM providers.
All LLM interactions in Cyber-Red go through implementations of LLMProvider.

Per architecture (lines 828-836, 990):
- Located in `src/cyberred/llm/provider.py`
- All LLM calls go through `LLMProvider` protocol
- 30 RPM global rate limit shared across swarm

Classes:
    LLMRequest: Request dataclass for LLM completions
    LLMResponse: Response dataclass from LLM completions
    TokenUsage: Token usage breakdown (frozen)
    HealthStatus: Health check result
    LLMProvider: Abstract base class for LLM providers
    MockLLMProvider: Mock provider for testing
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TokenUsage:
    """Token usage breakdown for LLM responses.

    Attributes:
        prompt_tokens: Number of tokens in the prompt.
        completion_tokens: Number of tokens in the completion.
        total_tokens: Total tokens (prompt + completion).
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class LLMRequest:
    """Request dataclass for LLM completions.

    Attributes:
        prompt: Input prompt for the LLM (required).
        model: Model identifier (required).
        temperature: Sampling temperature (0.0-2.0, default 0.7).
        max_tokens: Maximum response tokens (1-32768, default 1024).
        top_p: Nucleus sampling probability (0.0-1.0, default 1.0).
        frequency_penalty: Frequency penalty (-2.0-2.0, default 0.0).
        system_prompt: Optional system prompt.
        stop_sequences: Optional list of stop sequences.
    """

    prompt: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 1024
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    system_prompt: Optional[str] = None
    stop_sequences: Optional[List[str]] = field(default=None)

    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not self.prompt:
            raise ValueError("prompt cannot be empty")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
        if self.max_tokens <= 0 or self.max_tokens > 32768:
            raise ValueError("max_tokens must be between 1 and 32768")
        if not 0.0 <= self.top_p <= 1.0:
            raise ValueError("top_p must be between 0.0 and 1.0")
        if not -2.0 <= self.frequency_penalty <= 2.0:
            raise ValueError("frequency_penalty must be between -2.0 and 2.0")


@dataclass
class LLMResponse:
    """Response dataclass from LLM completions.

    Attributes:
        content: Generated text response.
        model: Model that produced the response.
        usage: Token usage breakdown.
        latency_ms: Request latency in milliseconds.
        finish_reason: Optional reason for completion.
        request_id: Optional request identifier.
    """

    content: str
    model: str
    usage: TokenUsage
    latency_ms: int
    finish_reason: Optional[str] = None
    request_id: Optional[str] = None

    @property
    def total_tokens(self) -> int:
        """Return total tokens from usage."""
        return self.usage.total_tokens


@dataclass
class HealthStatus:
    """Health check result for LLM providers.

    Attributes:
        healthy: Whether the provider is healthy.
        latency_ms: Optional latency in milliseconds.
        error: Optional error message if unhealthy.
    """

    healthy: bool
    latency_ms: Optional[int] = None
    error: Optional[str] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All LLM provider implementations must extend this class. Provides
    both synchronous and asynchronous completion methods.

    Per architecture (line 990):
    - All LLM calls go through LLMProvider protocol
    - 30 RPM global rate limit

    Abstract Methods:
        complete: Synchronous completion.
        complete_async: Asynchronous completion.
        health_check: Health check for circuit breaker.
        is_available: Check provider availability.
        get_model_name: Return model identifier.
        get_rate_limit: Return rate limit in RPM.
        get_token_usage: Return accumulated token usage.
    """

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate completion synchronously.

        Args:
            request: LLM request with prompt and parameters.

        Returns:
            LLM response with content and usage.

        Raises:
            LLMProviderUnavailable: If provider is not available.
            LLMTimeoutError: If request times out.
        """
        ...  # pragma: no cover

    @abstractmethod
    async def complete_async(self, request: LLMRequest) -> LLMResponse:
        """Generate completion asynchronously.

        Args:
            request: LLM request with prompt and parameters.

        Returns:
            LLM response with content and usage.

        Raises:
            LLMProviderUnavailable: If provider is not available.
            LLMTimeoutError: If request times out.
        """
        ...  # pragma: no cover

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Check provider health for circuit breaker.

        Returns:
            Health status with latency and error info.
        """
        ...  # pragma: no cover

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is currently available.

        Used for circuit-breaker patterns per NFR29.

        Returns:
            True if provider is available for requests.
        """
        ...  # pragma: no cover

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier.

        Returns:
            Model name string (e.g., 'nvidia/nemotron-70b').
        """
        ...  # pragma: no cover

    @abstractmethod
    def get_rate_limit(self) -> int:
        """Return rate limit in requests per minute.

        Returns:
            Maximum requests per minute (default 30 RPM).
        """
        ...  # pragma: no cover

    @abstractmethod
    def get_token_usage(self) -> Dict[str, int]:
        """Return accumulated token usage metrics.

        Returns:
            Dictionary with prompt_tokens, completion_tokens, total_tokens.
        """
        ...  # pragma: no cover

    # Protocol compatibility wrappers

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text completion (protocol compatibility wrapper).

        Wraps complete_async() to match LLMProviderProtocol.generate().

        Args:
            prompt: Input prompt for the LLM.
            **kwargs: Additional parameters (temperature, max_tokens).

        Returns:
            Generated text response.
        """
        model = kwargs.pop("model", self.get_model_name())
        temperature = kwargs.pop("temperature", 0.7)
        max_tokens = kwargs.pop("max_tokens", 1024)
        top_p = kwargs.pop("top_p", 1.0)
        frequency_penalty = kwargs.pop("frequency_penalty", 0.0)

        request = LLMRequest(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
        )
        response = await self.complete_async(request)
        return response.content

    async def generate_structured(
        self, prompt: str, schema: Dict[str, Any], **kwargs: Any
    ) -> Dict[str, Any]:
        """Generate structured output (protocol compatibility wrapper).

        Args:
            prompt: Input prompt for the LLM.
            schema: JSON schema for expected output.
            **kwargs: Additional parameters.

        Returns:
            Dictionary matching the provided schema.

        Raises:
            NotImplementedError: Schema validation deferred to future story.
        """
        raise NotImplementedError(
            "generate_structured() requires schema validation - deferred to Story 3.6"
        )


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing.

    Provides configurable responses and tracks calls for verification.
    Thread-safe implementation.

    Attributes:
        model_name: Model identifier.
        default_response: Default response content.
        available: Whether provider is available.
        call_count: Number of calls made.
    """

    def __init__(
        self,
        model_name: str = "mock-model",
        default_response: str = "Mock response",
        available: bool = True,
    ) -> None:
        """Initialize mock provider.

        Args:
            model_name: Model identifier to return.
            default_response: Default response content.
            available: Whether provider is available.
        """
        self._model_name = model_name
        self._default_response = default_response
        self._available = available
        self._call_count = 0
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._lock = threading.Lock()

    @property
    def call_count(self) -> int:
        """Return number of calls made."""
        with self._lock:
            return self._call_count

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate mock completion synchronously."""
        with self._lock:
            self._call_count += 1
            # Simulate token counts
            prompt_tokens = len(request.prompt.split())
            completion_tokens = len(self._default_response.split())
            self._total_prompt_tokens += prompt_tokens
            self._total_completion_tokens += completion_tokens
            
            # Snapshots for return
            p_tokens = prompt_tokens
            c_tokens = completion_tokens

        usage = TokenUsage(
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            total_tokens=p_tokens + c_tokens,
        )

        return LLMResponse(
            content=self._default_response,
            model=self._model_name,
            usage=usage,
            latency_ms=10,
            finish_reason="stop",
        )

    async def complete_async(self, request: LLMRequest) -> LLMResponse:
        """Generate mock completion asynchronously."""
        return self.complete(request)

    async def health_check(self) -> HealthStatus:
        """Return mock health status."""
        if self._available:
            return HealthStatus(healthy=True, latency_ms=5)
        return HealthStatus(healthy=False, error="Provider unavailable")

    def is_available(self) -> bool:
        """Return configured availability."""
        return self._available

    def get_model_name(self) -> str:
        """Return configured model name."""
        return self._model_name

    def get_rate_limit(self) -> int:
        """Return 30 RPM as per architecture."""
        return 30

    def get_token_usage(self) -> Dict[str, int]:
        """Return accumulated token usage."""
        with self._lock:
            return {
                "prompt_tokens": self._total_prompt_tokens,
                "completion_tokens": self._total_completion_tokens,
                "total_tokens": self._total_prompt_tokens
                + self._total_completion_tokens,
            }
