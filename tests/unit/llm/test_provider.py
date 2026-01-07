"""Unit tests for LLM provider module.

Tests for LLMRequest, LLMResponse, TokenUsage, HealthStatus dataclasses,
LLMProvider ABC, and MockLLMProvider implementation.
"""

from __future__ import annotations

import inspect
from typing import Dict

import pytest

from cyberred.core.exceptions import (
    CyberRedError,
    LLMError,
    LLMProviderUnavailable,
    LLMRateLimitExceeded,
    LLMResponseError,
    LLMTimeoutError,
)
from cyberred.llm import (
    HealthStatus,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    MockLLMProvider,
    TokenUsage,
)
from cyberred.protocols.provider import LLMProviderProtocol


# === Phase 1: Data Models Tests ===


class TestLLMRequest:
    """Tests for LLMRequest dataclass."""

    def test_llm_request_has_required_fields(self) -> None:
        """Test that LLMRequest has all required fields."""
        request = LLMRequest(prompt="Hello", model="test-model")

        assert request.prompt == "Hello"
        assert request.model == "test-model"
        assert request.temperature == 0.7  # default
        assert request.max_tokens == 1024  # default
        assert request.top_p == 1.0  # default
        assert request.frequency_penalty == 0.0  # default

    def test_llm_request_optional_fields(self) -> None:
        """Test optional fields in LLMRequest."""
        request = LLMRequest(
            prompt="Hello",
            model="test-model",
            temperature=0.5,
            max_tokens=2048,
            top_p=0.9,
            frequency_penalty=0.5,
            system_prompt="You are helpful",
            stop_sequences=["STOP", "END"],
        )

        assert request.system_prompt == "You are helpful"
        assert request.stop_sequences == ["STOP", "END"]
        assert request.temperature == 0.5
        assert request.max_tokens == 2048
        assert request.top_p == 0.9
        assert request.frequency_penalty == 0.5

    def test_llm_request_validation_empty_prompt(self) -> None:
        """Test that empty prompt raises ValueError."""
        with pytest.raises(ValueError, match="prompt cannot be empty"):
            LLMRequest(prompt="", model="test-model")

    def test_llm_request_validation_temperature_low(self) -> None:
        """Test that temperature < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="temperature must be"):
            LLMRequest(prompt="Hello", model="test-model", temperature=-0.1)

    def test_llm_request_validation_temperature_high(self) -> None:
        """Test that temperature > 2.0 raises ValueError."""
        with pytest.raises(ValueError, match="temperature must be"):
            LLMRequest(prompt="Hello", model="test-model", temperature=2.1)

    def test_llm_request_validation_max_tokens_zero(self) -> None:
        """Test that max_tokens <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="max_tokens must be"):
            LLMRequest(prompt="Hello", model="test-model", max_tokens=0)

    def test_llm_request_validation_max_tokens_too_high(self) -> None:
        """Test that max_tokens > 32768 raises ValueError."""
        with pytest.raises(ValueError, match="max_tokens must be"):
            LLMRequest(prompt="Hello", model="test-model", max_tokens=32769)

    def test_llm_request_validation_top_p_low(self) -> None:
        """Test that top_p < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="top_p must be"):
            LLMRequest(prompt="Hello", model="test-model", top_p=-0.1)

    def test_llm_request_validation_top_p_high(self) -> None:
        """Test that top_p > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="top_p must be"):
            LLMRequest(prompt="Hello", model="test-model", top_p=1.1)

    def test_llm_request_validation_frequency_penalty_low(self) -> None:
        """Test that frequency_penalty < -2.0 raises ValueError."""
        with pytest.raises(ValueError, match="frequency_penalty must be"):
            LLMRequest(prompt="Hello", model="test-model", frequency_penalty=-2.1)

    def test_llm_request_validation_frequency_penalty_high(self) -> None:
        """Test that frequency_penalty > 2.0 raises ValueError."""
        with pytest.raises(ValueError, match="frequency_penalty must be"):
            LLMRequest(prompt="Hello", model="test-model", frequency_penalty=2.1)


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""

    def test_token_usage_has_required_fields(self) -> None:
        """Test that TokenUsage has all required fields."""
        usage = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)

        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 20
        assert usage.total_tokens == 30

    def test_token_usage_is_frozen(self) -> None:
        """Test that TokenUsage is immutable (frozen)."""
        usage = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)

        with pytest.raises(AttributeError):
            usage.prompt_tokens = 100  # type: ignore


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_llm_response_has_required_fields(self) -> None:
        """Test that LLMResponse has all required fields."""
        usage = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        response = LLMResponse(
            content="Hello world",
            model="test-model",
            usage=usage,
            latency_ms=150,
        )

        assert response.content == "Hello world"
        assert response.model == "test-model"
        assert response.usage == usage
        assert response.latency_ms == 150

    def test_llm_response_optional_fields(self) -> None:
        """Test optional fields in LLMResponse."""
        usage = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        response = LLMResponse(
            content="Hello",
            model="test-model",
            usage=usage,
            latency_ms=100,
            finish_reason="stop",
            request_id="req-123",
        )

        assert response.finish_reason == "stop"
        assert response.request_id == "req-123"

    def test_llm_response_total_tokens_property(self) -> None:
        """Test total_tokens helper property."""
        usage = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        response = LLMResponse(
            content="Hello",
            model="test-model",
            usage=usage,
            latency_ms=100,
        )

        assert response.total_tokens == 30


class TestHealthStatus:
    """Tests for HealthStatus dataclass."""

    def test_health_status_healthy(self) -> None:
        """Test healthy status."""
        status = HealthStatus(healthy=True, latency_ms=50, error=None)

        assert status.healthy is True
        assert status.latency_ms == 50
        assert status.error is None

    def test_health_status_unhealthy(self) -> None:
        """Test unhealthy status with error."""
        status = HealthStatus(healthy=False, latency_ms=None, error="Connection refused")

        assert status.healthy is False
        assert status.latency_ms is None
        assert status.error == "Connection refused"


# === Phase 2: LLMProvider ABC Tests ===


class TestLLMProviderABC:
    """Tests for LLMProvider abstract base class."""

    def test_llm_provider_cannot_be_instantiated(self) -> None:
        """Test that LLMProvider ABC cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            LLMProvider()  # type: ignore

    def test_llm_provider_complete_is_abstract(self) -> None:
        """Test that complete() is an abstract method."""
        # Check that complete is an abstract method
        assert hasattr(LLMProvider, "complete")
        method = getattr(LLMProvider, "complete")
        assert getattr(method, "__isabstractmethod__", False)

    def test_llm_provider_complete_async_is_abstract(self) -> None:
        """Test that complete_async() is an abstract method."""
        assert hasattr(LLMProvider, "complete_async")
        method = getattr(LLMProvider, "complete_async")
        assert getattr(method, "__isabstractmethod__", False)

    def test_llm_provider_health_check_is_abstract(self) -> None:
        """Test that health_check() is an abstract method."""
        assert hasattr(LLMProvider, "health_check")
        method = getattr(LLMProvider, "health_check")
        assert getattr(method, "__isabstractmethod__", False)


# === Phase 3: Protocol Compliance Tests ===


class TestProtocolCompliance:
    """Tests for LLMProvider protocol compliance."""

    def test_llm_provider_satisfies_protocol(self) -> None:
        """Test that concrete LLMProvider subclass satisfies LLMProviderProtocol."""
        # MockLLMProvider is a concrete implementation
        provider = MockLLMProvider(model_name="test-model")

        # Check it satisfies the protocol via isinstance (runtime_checkable)
        assert isinstance(provider, LLMProviderProtocol)

    def test_mock_provider_implements_protocol(self) -> None:
        """Test that MockLLMProvider implements all protocol methods."""
        provider = MockLLMProvider(model_name="test-model")

        # All protocol methods exist
        assert hasattr(provider, "generate")
        assert hasattr(provider, "generate_structured")
        assert hasattr(provider, "get_model_name")
        assert hasattr(provider, "get_rate_limit")
        assert hasattr(provider, "get_token_usage")
        assert hasattr(provider, "is_available")


class TestMockLLMProvider:
    """Tests for MockLLMProvider implementation."""

    def test_mock_provider_complete(self) -> None:
        """Test MockLLMProvider.complete() returns configurable response."""
        provider = MockLLMProvider(
            model_name="test-model",
            default_response="Test response",
        )
        request = LLMRequest(prompt="Hello", model="test-model")

        response = provider.complete(request)

        assert response.content == "Test response"
        assert response.model == "test-model"

    @pytest.mark.asyncio
    async def test_mock_provider_complete_async(self) -> None:
        """Test MockLLMProvider.complete_async() returns configurable response."""
        provider = MockLLMProvider(
            model_name="test-model",
            default_response="Async response",
        )
        request = LLMRequest(prompt="Hello", model="test-model")

        response = await provider.complete_async(request)

        assert response.content == "Async response"

    @pytest.mark.asyncio
    async def test_mock_provider_health_check(self) -> None:
        """Test MockLLMProvider.health_check()."""
        provider = MockLLMProvider(model_name="test-model")

        status = await provider.health_check()

        assert status.healthy is True
        assert status.latency_ms is not None

    @pytest.mark.asyncio
    async def test_mock_provider_health_check_unhealthy(self) -> None:
        """Test MockLLMProvider.health_check() when unavailable."""
        provider = MockLLMProvider(model_name="test-model", available=False)

        status = await provider.health_check()

        assert status.healthy is False
        assert status.error == "Provider unavailable"

    def test_mock_provider_tracks_call_count(self) -> None:
        """Test that MockLLMProvider tracks call count."""
        provider = MockLLMProvider(model_name="test-model")
        request = LLMRequest(prompt="Hello", model="test-model")

        assert provider.call_count == 0

        provider.complete(request)
        assert provider.call_count == 1

        provider.complete(request)
        assert provider.call_count == 2

    @pytest.mark.asyncio
    async def test_mock_provider_generate_wrapper(self) -> None:
        """Test generate() wrapper for protocol compliance."""
        provider = MockLLMProvider(
            model_name="test-model",
            default_response="Generated text",
        )

        result = await provider.generate("Hello world")

        assert result == "Generated text"

    @pytest.mark.asyncio
    async def test_mock_provider_generate_structured_not_implemented(self) -> None:
        """Test generate_structured() raises NotImplementedError."""
        provider = MockLLMProvider(model_name="test-model")

        with pytest.raises(NotImplementedError, match="generate_structured"):
            await provider.generate_structured("Hello", {"type": "object"})

    def test_mock_provider_get_model_name(self) -> None:
        """Test get_model_name() returns configured model."""
        provider = MockLLMProvider(model_name="nvidia/nemotron-70b")

        assert provider.get_model_name() == "nvidia/nemotron-70b"

    def test_mock_provider_get_rate_limit(self) -> None:
        """Test get_rate_limit() returns 30 RPM default."""
        provider = MockLLMProvider(model_name="test-model")

        assert provider.get_rate_limit() == 30

    def test_mock_provider_get_token_usage(self) -> None:
        """Test get_token_usage() returns accumulated usage."""
        provider = MockLLMProvider(model_name="test-model")

        # Initial usage should be empty
        usage = provider.get_token_usage()
        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0

        # After a call, usage should be tracked
        request = LLMRequest(prompt="Hello", model="test-model")
        provider.complete(request)

        usage = provider.get_token_usage()
        assert usage["total_tokens"] > 0

    def test_mock_provider_is_available(self) -> None:
        """Test is_available() returns True by default."""
        provider = MockLLMProvider(model_name="test-model")

        assert provider.is_available() is True

    def test_mock_provider_is_available_false(self) -> None:
        """Test is_available() can be configured to return False."""
        provider = MockLLMProvider(model_name="test-model", available=False)

        assert provider.is_available() is False


# === Phase 4: Exception Tests ===


class TestLLMExceptions:
    """Tests for LLM exception hierarchy."""

    def test_llm_exceptions_in_hierarchy(self) -> None:
        """Test that all LLM exceptions inherit from LLMError and CyberRedError."""
        # All inherit from LLMError
        assert issubclass(LLMProviderUnavailable, LLMError)
        assert issubclass(LLMRateLimitExceeded, LLMError)
        assert issubclass(LLMTimeoutError, LLMError)
        assert issubclass(LLMResponseError, LLMError)

        # LLMError inherits from CyberRedError
        assert issubclass(LLMError, CyberRedError)

    def test_llm_error_base(self) -> None:
        """Test LLMError base exception."""
        error = LLMError("Test error", provider="test-provider", model="test-model")

        assert str(error) == "Test error"
        assert error.provider == "test-provider"
        assert error.model == "test-model"
        assert "provider" in error.context

    def test_llm_provider_unavailable(self) -> None:
        """Test LLMProviderUnavailable exception."""
        error = LLMProviderUnavailable("nvidia-nim", retry_after=60)

        assert "unavailable" in str(error).lower()
        assert error.provider == "nvidia-nim"
        assert error.retry_after == 60

    def test_llm_rate_limit_exceeded(self) -> None:
        """Test LLMRateLimitExceeded exception."""
        error = LLMRateLimitExceeded("nvidia-nim", limit=30, retry_after=10)

        assert "rate limit" in str(error).lower()
        assert error.limit == 30
        assert error.retry_after == 10

    def test_llm_timeout_error(self) -> None:
        """Test LLMTimeoutError exception."""
        error = LLMTimeoutError("nvidia-nim", timeout_seconds=30.0, request_id="req-123")

        assert "timed out" in str(error).lower()
        assert error.timeout_seconds == 30.0
        assert error.request_id == "req-123"

    def test_llm_response_error(self) -> None:
        """Test LLMResponseError exception."""
        error = LLMResponseError("nvidia-nim", reason="Invalid JSON")

        assert "Invalid JSON" in str(error)
        assert error.reason == "Invalid JSON"


# === Phase 5: Package Import Tests ===


class TestPackageImports:
    """Tests for package exports and imports."""

    def test_llm_package_exports(self) -> None:
        """Test llm package exports all required types."""
        # All types are importable
        assert LLMProvider is not None
        assert LLMRequest is not None
        assert LLMResponse is not None
        assert TokenUsage is not None
        assert HealthStatus is not None
        assert MockLLMProvider is not None

    def test_core_llm_exception_exports(self) -> None:
        """Test core module exports LLM exceptions."""
        # All exceptions are importable from core
        assert LLMError is not None
        assert LLMProviderUnavailable is not None
        assert LLMRateLimitExceeded is not None
        assert LLMTimeoutError is not None
        assert LLMResponseError is not None

