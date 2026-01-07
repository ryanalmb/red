"""Extended unit tests for NVIDIA NIM Provider to cover edge cases."""

import pytest
import respx
from httpx import Response

from cyberred.llm.nim import NIMProvider
from cyberred.llm.provider import LLMRequest, LLMResponse, TokenUsage
from cyberred.core.exceptions import LLMProviderUnavailable, LLMRateLimitExceeded, LLMResponseError

@pytest.fixture
def nim_provider():
    """Create a NIMProvider instance for testing."""
    return NIMProvider(api_key="test-key")

@pytest.fixture
def mock_nim_response():
    """Return a standard mocked NIM API response."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1704067200,
        "model": "mistralai/devstral-2-123b-instruct-2512",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Test response"},
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15
        }
    }

@respx.mock
def test_nim_provider_unavailable_check(nim_provider):
    """Test that complete raises if provider is unavailable."""
    # Force unavailable state
    with nim_provider._lock:
        nim_provider._consecutive_failures = 3
        
    request = LLMRequest(prompt="test", model="test")
    
    with pytest.raises(LLMProviderUnavailable) as exc:
        nim_provider.complete(request)
    assert "consecutive failures" in str(exc.value)

@respx.mock
async def test_nim_provider_async_unavailable_check(nim_provider):
    """Test that complete_async raises if provider is unavailable."""
    # Force unavailable state
    with nim_provider._lock:
        nim_provider._consecutive_failures = 3
        
    request = LLMRequest(prompt="test", model="test")
    
    with pytest.raises(LLMProviderUnavailable) as exc:
        await nim_provider.complete_async(request)
    assert "consecutive failures" in str(exc.value)

@respx.mock
def test_nim_provider_generic_exception(nim_provider):
    """Test handling of unexpected exceptions."""
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        side_effect=Exception("Unexpected boom")
    )
    
    request = LLMRequest(prompt="test", model="test")
    
    with pytest.raises(LLMProviderUnavailable) as exc:
        nim_provider.complete(request)
    assert "Unexpected error" in str(exc.value)
    assert "boom" in str(exc.value)

@respx.mock
async def test_nim_provider_async_generic_exception(nim_provider):
    """Test handling of unexpected exceptions in async."""
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        side_effect=Exception("Unexpected boom")
    )
    
    request = LLMRequest(prompt="test", model="test")
    
    with pytest.raises(LLMProviderUnavailable) as exc:
        await nim_provider.complete_async(request)
    assert "Unexpected error" in str(exc.value)
    assert "boom" in str(exc.value)

@respx.mock
def test_nim_provider_error_response_text(nim_provider):
    """Test handling of error response with plain text body."""
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(400, text="Bad Request")
    )
    
    request = LLMRequest(prompt="test", model="test")
    
    with pytest.raises(LLMProviderUnavailable) as exc:
        nim_provider.complete(request)
    assert "API Error: Bad Request" in str(exc.value)

@respx.mock
def test_nim_provider_missing_choices(nim_provider):
    """Test response missing choices field."""
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(200, json={"id": "123"})
    )
    
    request = LLMRequest(prompt="test", model="test")
    
    with pytest.raises(LLMResponseError) as exc:
        nim_provider.complete(request)
    assert "Missing 'choices'" in str(exc.value)

@respx.mock
def test_nim_provider_empty_choices(nim_provider):
    """Test response with empty choices list."""
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(200, json={"choices": []})
    )
    
    request = LLMRequest(prompt="test", model="test")
    
    with pytest.raises(LLMResponseError) as exc:
        nim_provider.complete(request)
    assert "Missing 'choices'" in str(exc.value)

@respx.mock
def test_nim_provider_malformed_json_parsing(nim_provider):
    """Test response causing parse errors in choice structure."""
    # What if choices contains a string instead of a dict?
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(200, json={"choices": ["not-a-dict"]})
    )
    
    request = LLMRequest(prompt="test", model="test")
    
    with pytest.raises(LLMResponseError) as exc:
        nim_provider.complete(request)
    assert "Invalid choice format" in str(exc.value)

@respx.mock
def test_nim_provider_stop_sequences(nim_provider, mock_nim_response):
    """Test sending stop sequences."""
    route = respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(200, json=mock_nim_response)
    )
    
    request = LLMRequest(
        prompt="test", 
        model="test",
        stop_sequences=["STOP", "END"]
    )
    nim_provider.complete(request)
    
    content = route.calls.last.request.read()
    assert b"STOP" in content
    assert b"END" in content

def test_nim_provider_factory_defaults():
    """Test factory handles unknown tiers."""
    provider = NIMProvider.for_tier("UNKNOWN_TIER", "key")
    assert provider.get_model_name() == "mistralai/devstral-2-123b-instruct-2512"

@respx.mock
async def test_health_check_exception(nim_provider):
    """Test health check exception handling."""
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        side_effect=Exception("Health check failed")
    )
    
    status = await nim_provider.health_check()
    assert status.healthy is False
    assert "Health check failed" in status.error

@respx.mock
def test_nim_provider_request_id_parsing(nim_provider, mock_nim_response):
    """Test parsing of different request ID headers."""
    # Case 1: x-inv-request-id
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(200, json=mock_nim_response, headers={"x-inv-request-id": "req-1"})
    )
    resp = nim_provider.complete(LLMRequest("test", "test"))
    assert resp.request_id == "req-1"
    
    # Case 2: nv-request-id
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(200, json=mock_nim_response, headers={"nv-request-id": "req-2"})
    )
    resp = nim_provider.complete(LLMRequest("test", "test"))
    assert resp.request_id == "req-2"
    
    # Case 3: id in body
    mock_nim_response["id"] = "req-3"
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(200, json=mock_nim_response)
    )
    resp = nim_provider.complete(LLMRequest("test", "test"))
    assert resp.request_id == "req-3"


# === Additional tests for 100% coverage ===

@respx.mock
async def test_nim_provider_async_timeout(nim_provider):
    """Test async timeout handling (covers lines 157-158)."""
    from httpx import TimeoutException
    
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        side_effect=TimeoutException("Async timeout")
    )
    
    request = LLMRequest(prompt="test", model="test")
    
    from cyberred.core.exceptions import LLMTimeoutError
    with pytest.raises(LLMTimeoutError):
        await nim_provider.complete_async(request)


@respx.mock
async def test_nim_provider_async_connect_error(nim_provider):
    """Test async connection error handling (covers lines 163-164)."""
    from httpx import ConnectError
    
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        side_effect=ConnectError("Async connect failed")
    )
    
    request = LLMRequest(prompt="test", model="test")
    
    with pytest.raises(LLMProviderUnavailable) as exc:
        await nim_provider.complete_async(request)
    assert "Connection failed" in str(exc.value)


@respx.mock
async def test_nim_provider_async_reraise_llm_exception(nim_provider):
    """Test async reraise of LLM exceptions (covers line 170)."""
    # Trigger a rate limit which should be re-raised, not wrapped
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(429, headers={"Retry-After": "10"})
    )
    
    request = LLMRequest(prompt="test", model="test")
    
    with pytest.raises(LLMRateLimitExceeded) as exc:
        await nim_provider.complete_async(request)
    assert exc.value.retry_after == 10


@respx.mock
def test_nim_provider_message_not_dict(nim_provider):
    """Test message field that is not a dict (covers line 288)."""
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(200, json={
            "choices": [{"message": "not-a-dict", "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
        })
    )
    
    request = LLMRequest(prompt="test", model="test")
    
    with pytest.raises(LLMResponseError) as exc:
        nim_provider.complete(request)
    assert "Malformed response" in str(exc.value)


@respx.mock
def test_nim_models_export():
    """Test NIMProvider.MODELS is accessible via package import."""
    from cyberred.llm import NIMProvider
    
    assert "FAST" in NIMProvider.MODELS
    assert "STANDARD" in NIMProvider.MODELS
    assert "COMPLEX" in NIMProvider.MODELS
    assert NIMProvider.MODELS["FAST"] == "mistralai/devstral-2-123b-instruct-2512"