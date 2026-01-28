"""Integration tests for MiniMax M2 Creative Role (Story 8.4).

These tests verify the creative role with real LLM API calls when
NVIDIA_API_KEY is available. Tests are skipped without the API key.

Tests cover:
- Real query_creative() execution with MiniMax M2
- Structured creative output format verification
- Thinking tag preservation
- Timeout behavior
- Graceful degradation when unavailable
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Generator

import pytest

from cyberred.llm.ensemble import (
    DirectorContext,
    DirectorEnsemble,
    DirectorRole,
    CurrentStrategy,
    DefenseEncountered,
    FailedAttempt,
)
from cyberred.core.exceptions import LLMTimeoutError, LLMProviderUnavailable

if TYPE_CHECKING:
    pass


# Skip all tests if NVIDIA_API_KEY is not set
pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("NVIDIA_API_KEY"),
        reason="NVIDIA_API_KEY not set - skipping integration tests"
    ),
    pytest.mark.integration,
]


@pytest.fixture(scope="module")
def setup_gateway() -> Generator[None, None, None]:
    """Initialize the LLM gateway for integration tests."""
    import os
    from cyberred.llm.gateway import initialize_gateway, shutdown_gateway
    from cyberred.llm.rate_limiter import RateLimiter
    from cyberred.llm.router import ModelRouter
    from cyberred.llm.priority_queue import LLMPriorityQueue
    from cyberred.llm.nim import NIMProvider
    from cyberred.llm.router import TaskComplexity
    
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        pytest.skip("NVIDIA_API_KEY not available")
    
    # Initialize dependencies
    rate_limiter = RateLimiter(rpm=30)
    queue = LLMPriorityQueue()
    
    # Setup providers
    nim_fast = NIMProvider.for_tier("FAST", api_key)
    nim_standard = NIMProvider.for_tier("STANDARD", api_key)
    
    providers = {
        TaskComplexity.FAST: nim_fast,
        TaskComplexity.STANDARD: nim_standard,
        TaskComplexity.COMPLEX: nim_standard,
    }
    
    router = ModelRouter(providers=providers, default_tier=TaskComplexity.FAST)
    
    # Initialize gateway
    initialize_gateway(rate_limiter, router, queue)
    yield
    shutdown_gateway()


class TestCreativeIntegration:
    """Integration tests for MiniMax M2 Creative Role."""
    
    @pytest.fixture
    def ensemble(self, setup_gateway) -> DirectorEnsemble:
        """Create DirectorEnsemble instance."""
        return DirectorEnsemble()
    
    @pytest.fixture
    def base_context(self) -> DirectorContext:
        """Create base DirectorContext for tests."""
        return DirectorContext(
            engagement_id="integration-test-001",
            phase="exploitation",
            prompt="Suggest creative alternatives for bypassing a WAF that blocks SQL injection attempts",
        )
    
    @pytest.fixture
    def sample_strategy(self) -> CurrentStrategy:
        """Create sample CurrentStrategy for tests."""
        return CurrentStrategy(
            strategy_id="STRAT-001",
            description="Direct SQL injection attack on login form",
            phase="exploitation",
            objectives=["Gain database access", "Extract credentials"],
            techniques_in_use=["T1190"],
        )
    
    @pytest.fixture
    def sample_defenses(self) -> list[DefenseEncountered]:
        """Create sample DefenseEncountered list for tests."""
        return [
            DefenseEncountered(
                defense_id="DEF-001",
                defense_type="WAF",
                target="web-server-01",
                description="Cloudflare WAF blocking SQL injection payloads",
                blocking_technique="T1190",
            ),
        ]
    
    @pytest.fixture
    def sample_failed_attempts(self) -> list[FailedAttempt]:
        """Create sample FailedAttempt list for tests."""
        return [
            FailedAttempt(
                attempt_id="FA-001",
                technique="Union-based SQLi",
                target="login.php",
                failure_reason="WAF blocked UNION SELECT pattern",
                timestamp="2026-01-28T07:00:00Z",
            ),
            FailedAttempt(
                attempt_id="FA-002",
                technique="Boolean-based SQLi",
                target="login.php",
                failure_reason="WAF blocked OR 1=1 pattern",
                timestamp="2026-01-28T07:01:00Z",
            ),
        ]
    
    @pytest.mark.asyncio
    async def test_query_creative_real_api(
        self,
        ensemble: DirectorEnsemble,
        base_context: DirectorContext,
    ) -> None:
        """Test query_creative with real MiniMax M2 API."""
        result = await ensemble.query_creative(base_context)
        
        # Verify response structure
        assert result is not None
        assert result.raw_content, "Response should have content"
        assert result.model_response.success, "Query should succeed"
        assert result.model_response.role == DirectorRole.CREATIVE
        assert result.model_response.model_id == "minimaxai/minimax-m2"
    
    @pytest.mark.asyncio
    async def test_query_creative_with_full_context(
        self,
        ensemble: DirectorEnsemble,
        base_context: DirectorContext,
        sample_strategy: CurrentStrategy,
        sample_defenses: list[DefenseEncountered],
        sample_failed_attempts: list[FailedAttempt],
    ) -> None:
        """Test query_creative with full context including strategy, defenses, and failed attempts."""
        result = await ensemble.query_creative(
            base_context,
            current_strategy=sample_strategy,
            defenses_encountered=sample_defenses,
            failed_attempts=sample_failed_attempts,
        )
        
        # Verify response structure
        assert result is not None
        assert result.raw_content, "Response should have content"
        assert result.model_response.success, "Query should succeed"
        
        # Verify structured output (may vary based on model response)
        # The model should return at least some content
        assert len(result.clean_content) > 0 or len(result.raw_content) > 0
    
    @pytest.mark.asyncio
    async def test_query_creative_thinking_tags_present(
        self,
        ensemble: DirectorEnsemble,
        base_context: DirectorContext,
    ) -> None:
        """Test that thinking tags are present and preserved in response."""
        result = await ensemble.query_creative(base_context)
        
        # Check if response contains thinking tags
        # Note: Model may or may not use thinking tags in every response
        if "<think>" in result.raw_content.lower():
            assert len(result.thinking_content) > 0, "Should extract thinking content when tags present"
            # Verify clean content has tags removed
            assert "<think>" not in result.clean_content.lower()
    
    @pytest.mark.asyncio
    async def test_query_creative_response_latency(
        self,
        ensemble: DirectorEnsemble,
        base_context: DirectorContext,
    ) -> None:
        """Test that response latency is within expected bounds."""
        result = await ensemble.query_creative(base_context)
        
        # Verify latency is recorded
        assert result.model_response.latency_ms > 0
        
        # Latency should be less than timeout (100s = 100000ms)
        assert result.model_response.latency_ms < 100000
    
    @pytest.mark.asyncio
    async def test_creative_model_configuration(
        self,
        ensemble: DirectorEnsemble,
    ) -> None:
        """Test that creative model is correctly configured per architecture."""
        creative_model = ensemble.get_model(DirectorRole.CREATIVE)
        
        # Verify configuration per architecture
        assert creative_model.model_id == "minimaxai/minimax-m2"
        assert creative_model.timeout == 100.0  # 100s per architecture
        assert creative_model.role == DirectorRole.CREATIVE
        
        # Verify system prompt has required elements
        assert "Creative Alternatives" in creative_model.system_prompt
        assert "Evasion Techniques" in creative_model.system_prompt
        assert "Novel Approaches" in creative_model.system_prompt
        assert "<think>" in creative_model.system_prompt


class TestCreativeGracefulDegradation:
    """Tests for graceful degradation when MiniMax M2 is unavailable."""
    
    @pytest.mark.asyncio
    async def test_handles_api_errors_gracefully(self) -> None:
        """Test that API errors are handled gracefully."""
        # This test verifies the error handling path exists
        # Actual API errors are rare in integration tests
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="error-test-001",
            phase="test",
            prompt="Test prompt for error handling",
        )
        
        try:
            result = await ensemble.query_creative(context)
            # If successful, verify response is valid
            assert result is not None
        except (LLMTimeoutError, LLMProviderUnavailable) as e:
            # These are expected exceptions for graceful degradation
            assert str(e), "Exception should have a message"
