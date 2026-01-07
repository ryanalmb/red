"""Integration tests for NVIDIA NIM Provider."""

import os
import pytest
from cyberred.llm.nim import NIMProvider
from cyberred.llm.provider import LLMRequest, LLMResponse, HealthStatus

# Skip integration tests if API key not present
pytestmark = pytest.mark.skipif(
    not os.getenv("NVIDIA_API_KEY"),
    reason="NVIDIA_API_KEY not set"
)

@pytest.fixture
def nim_provider():
    """Create a real NIMProvider instance."""
    return NIMProvider(api_key=os.getenv("NVIDIA_API_KEY"))

@pytest.mark.integration
def test_nim_integration_complete(nim_provider):
    """Test real completion against NVIDIA NIM API."""
    request = LLMRequest(
        prompt="Reply with exactly one word: 'pong'.",
        model=nim_provider.get_model_name(),  # Use provider's model
        max_tokens=10
    )
    
    response = nim_provider.complete(request)
    
    assert isinstance(response, LLMResponse)
    assert response.content
    assert response.usage.total_tokens > 0
    assert response.latency_ms > 0

@pytest.mark.integration
async def test_nim_integration_health_check(nim_provider):
    """Test real health check against NVIDIA NIM API."""
    status = await nim_provider.health_check()
    
    assert isinstance(status, HealthStatus)
    assert status.healthy is True
    assert status.latency_ms > 0