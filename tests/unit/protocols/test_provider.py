"""Unit tests for LLMProviderProtocol.

Tests verify:
1. Compliant classes pass isinstance() checks
2. Non-compliant classes fail isinstance() checks
3. All async methods have correct signatures
4. Observability methods (get_token_usage, is_available) work correctly
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from cyberred.protocols import LLMProviderProtocol


class CompliantProvider:
    """A minimal compliant LLM provider implementation for testing."""
    
    def __init__(self) -> None:
        self._model_name = "test-model"
        self._rate_limit = 30
        self._available = True
        self._token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
    
    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text completion."""
        self._token_usage["prompt_tokens"] += len(prompt.split())
        self._token_usage["completion_tokens"] += 10
        self._token_usage["total_tokens"] = (
            self._token_usage["prompt_tokens"] + 
            self._token_usage["completion_tokens"]
        )
        return f"Response to: {prompt}"
    
    async def generate_structured(
        self, prompt: str, schema: Dict, **kwargs: Any
    ) -> Dict:
        """Generate structured output."""
        return {"result": "structured response", "schema_keys": list(schema.keys())}
    
    def get_model_name(self) -> str:
        """Return model identifier."""
        return self._model_name
    
    def get_rate_limit(self) -> int:
        """Return rate limit in RPM."""
        return self._rate_limit
    
    def get_token_usage(self) -> Dict:
        """Return usage metrics."""
        return self._token_usage.copy()
    
    def is_available(self) -> bool:
        """Check provider availability."""
        return self._available


class PartialProvider:
    """A provider missing some required methods."""
    
    async def generate(self, prompt: str, **kwargs: Any) -> str:
        return "response"
    
    def get_model_name(self) -> str:
        return "partial"
    
    # Missing: generate_structured, get_rate_limit, get_token_usage, is_available


class NonCompliantClass:
    """A class with no provider methods."""
    
    def do_something(self) -> str:
        return "something"


# -----------------------------------------------------------------------------
# Protocol Compliance Tests
# -----------------------------------------------------------------------------

def test_compliant_provider_passes_isinstance() -> None:
    """Verify that a fully compliant provider passes isinstance check."""
    provider = CompliantProvider()
    assert isinstance(provider, LLMProviderProtocol)


def test_non_compliant_class_fails_isinstance() -> None:
    """Verify that a non-compliant class fails isinstance check."""
    obj = NonCompliantClass()
    assert not isinstance(obj, LLMProviderProtocol)


def test_partial_provider_fails_isinstance() -> None:
    """Verify that a partially compliant class fails isinstance check."""
    provider = PartialProvider()
    assert not isinstance(provider, LLMProviderProtocol)


# -----------------------------------------------------------------------------
# Method Signature Tests
# -----------------------------------------------------------------------------

def test_generate_method_exists() -> None:
    """Verify generate method exists."""
    provider = CompliantProvider()
    assert hasattr(provider, "generate")
    assert callable(provider.generate)


def test_generate_structured_method_exists() -> None:
    """Verify generate_structured method exists."""
    provider = CompliantProvider()
    assert hasattr(provider, "generate_structured")
    assert callable(provider.generate_structured)


def test_get_model_name_method_exists() -> None:
    """Verify get_model_name method exists and returns string."""
    provider = CompliantProvider()
    assert hasattr(provider, "get_model_name")
    result = provider.get_model_name()
    assert isinstance(result, str)


def test_get_rate_limit_method_exists() -> None:
    """Verify get_rate_limit method exists and returns int."""
    provider = CompliantProvider()
    assert hasattr(provider, "get_rate_limit")
    result = provider.get_rate_limit()
    assert isinstance(result, int)


def test_get_token_usage_method_exists() -> None:
    """Verify get_token_usage method exists and returns dict."""
    provider = CompliantProvider()
    assert hasattr(provider, "get_token_usage")
    result = provider.get_token_usage()
    assert isinstance(result, dict)


def test_is_available_method_exists() -> None:
    """Verify is_available method exists and returns bool."""
    provider = CompliantProvider()
    assert hasattr(provider, "is_available")
    result = provider.is_available()
    assert isinstance(result, bool)


# -----------------------------------------------------------------------------
# Async Method Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_returns_string() -> None:
    """Verify generate returns a string."""
    provider = CompliantProvider()
    result = await provider.generate("test prompt")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_generate_with_kwargs() -> None:
    """Verify generate accepts kwargs."""
    provider = CompliantProvider()
    result = await provider.generate(
        "test prompt",
        temperature=0.7,
        max_tokens=100
    )
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_generate_structured_returns_dict() -> None:
    """Verify generate_structured returns a dict."""
    provider = CompliantProvider()
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    result = await provider.generate_structured("test prompt", schema)
    assert isinstance(result, dict)


# -----------------------------------------------------------------------------
# Observability Tests
# -----------------------------------------------------------------------------

def test_token_usage_has_required_keys() -> None:
    """Verify token usage dict has expected keys."""
    provider = CompliantProvider()
    usage = provider.get_token_usage()
    assert "prompt_tokens" in usage
    assert "completion_tokens" in usage
    assert "total_tokens" in usage


@pytest.mark.asyncio
async def test_token_usage_updates_after_generate() -> None:
    """Verify token usage updates after generate calls."""
    provider = CompliantProvider()
    initial_usage = provider.get_token_usage()
    assert initial_usage["total_tokens"] == 0
    
    await provider.generate("test prompt with several words")
    updated_usage = provider.get_token_usage()
    assert updated_usage["total_tokens"] > 0


def test_rate_limit_is_positive() -> None:
    """Verify rate limit is a positive integer."""
    provider = CompliantProvider()
    limit = provider.get_rate_limit()
    assert limit > 0


def test_is_available_returns_true_by_default() -> None:
    """Verify is_available returns True for a healthy provider."""
    provider = CompliantProvider()
    assert provider.is_available() is True
