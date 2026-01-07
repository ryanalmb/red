"""Integration tests for LLM timeout and retry scenarios.

Tests per Story 3.11 AC#8: Integration tests simulate timeout scenarios.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cyberred.llm.gateway import LLMGateway
from cyberred.llm.provider import LLMRequest, LLMResponse, TokenUsage
from cyberred.llm.rate_limiter import RateLimiter
from cyberred.llm.router import ModelRouter, TaskComplexity
from cyberred.llm.priority_queue import LLMPriorityQueue, PriorityRequest
from cyberred.llm.retry import RetryPolicy
from cyberred.core.exceptions import LLMTimeoutError, LLMProviderUnavailable


class TestTimeoutRetryIntegration:
    """Integration tests for timeout and retry scenarios."""

    @pytest.fixture
    def failing_provider(self):
        """Provider that always fails with LLMProviderUnavailable."""
        provider = AsyncMock()
        provider.model_name = "failing-model"
        provider.is_available.return_value = True
        provider.get_model_name.return_value = "failing-model"
        provider.complete_async.side_effect = LLMProviderUnavailable("provider unavailable")
        return provider

    @pytest.fixture
    def fallback_provider(self):
        """Provider that always succeeds."""
        provider = AsyncMock()
        provider.model_name = "fallback-model"
        provider.is_available.return_value = True
        provider.get_model_name.return_value = "fallback-model"
        provider.complete_async.return_value = LLMResponse(
            content="success from fallback",
            model="fallback-model",
            usage=TokenUsage(10, 20, 30),
            latency_ms=50.0,
        )
        return provider

    @pytest.fixture
    def rate_limiter(self):
        """Rate limiter for tests."""
        limiter = MagicMock(spec=RateLimiter)
        limiter.acquire_async.return_value = True
        return limiter

    @pytest.fixture
    def queue(self):
        """Priority queue for tests."""
        return MagicMock(spec=LLMPriorityQueue)

    @pytest.mark.asyncio
    async def test_circuit_breaker_excludes_model_after_failures(
        self, failing_provider, rate_limiter, queue
    ):
        """Test that model is excluded after 3 failures (AC#6)."""
        # Use low threshold for testing
        policy = RetryPolicy(
            max_retries=0,  # No retries per attempt
            request_timeout=1.0,
            cb_failure_threshold=3,
            cb_exclusion_duration=60.0,
        )
        
        router = ModelRouter(
            providers={TaskComplexity.STANDARD: failing_provider}
        )
        
        gateway = LLMGateway(rate_limiter, router, queue, retry_policy=policy)
        
        request = LLMRequest(prompt="test", model="auto")
        
        # Trigger 3 failures
        for i in range(3):
            with pytest.raises(LLMProviderUnavailable):
                await gateway._execute_with_retry(request)
        
        # Model should now be excluded
        assert gateway.is_excluded("failing-model") is True

    @pytest.mark.asyncio
    async def test_excluded_model_recovery_after_duration(
        self, failing_provider, rate_limiter, queue
    ):
        """Test that excluded model recovers after exclusion duration (AC#6)."""
        policy = RetryPolicy(
            max_retries=0,
            request_timeout=1.0,
            cb_failure_threshold=1,  # Exclude after 1 failure
            cb_exclusion_duration=0.1,  # Very short for testing
        )
        
        router = ModelRouter(
            providers={TaskComplexity.STANDARD: failing_provider}
        )
        
        gateway = LLMGateway(rate_limiter, router, queue, retry_policy=policy)
        
        request = LLMRequest(prompt="test", model="auto")
        
        # Trigger failure
        with pytest.raises(LLMProviderUnavailable):
            await gateway._execute_with_retry(request)
        
        # Model should be excluded
        assert gateway.is_excluded("failing-model") is True
        
        # Wait for exclusion to expire
        await asyncio.sleep(0.15)
        
        # Model should no longer be excluded
        assert gateway.is_excluded("failing-model") is False

    @pytest.mark.asyncio
    async def test_fallback_to_different_tier_when_primary_excluded(
        self, rate_limiter, queue
    ):
        """Test fallback to different tier when primary is excluded (AC#7)."""
        import time
        
        # Create a fast provider that will be manually excluded
        # Use MagicMock for sync methods, attach AsyncMock for async methods
        fast_provider = MagicMock()
        fast_provider.model_name = "fast-model"
        fast_provider.is_available.return_value = True
        fast_provider.get_model_name.return_value = "fast-model"
        fast_provider.complete_async = AsyncMock()
        
        # Create fallback provider inline (not from fixture) to ensure same instance
        fallback_provider = MagicMock()
        fallback_provider.model_name = "fallback-model"
        fallback_provider.is_available.return_value = True
        fallback_provider.get_model_name.return_value = "fallback-model"
        fallback_provider.complete_async = AsyncMock()
        
        policy = RetryPolicy(
            max_retries=0,
            request_timeout=1.0,
            cb_failure_threshold=1,
            cb_exclusion_duration=60.0,
        )
        
        router = ModelRouter(
            providers={
                TaskComplexity.FAST: fast_provider,
                TaskComplexity.STANDARD: fallback_provider,
            }
        )
        
        gateway = LLMGateway(rate_limiter, router, queue, retry_policy=policy)
        
        # Manually exclude the FAST model via gateway (simulating circuit breaker trigger)
        gateway._model_excluded_until["fast-model"] = time.monotonic() + 3600
        
        # Verify exclusion is active
        assert gateway.is_excluded("fast-model") is True
        
        # Select should skip excluded FAST and use STANDARD
        selected = router.select_model(TaskComplexity.FAST)
        # Verify by model_name since AsyncMock instances may differ
        assert selected.model_name == "fallback-model"

    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(
        self, rate_limiter, queue
    ):
        """Test exponential backoff timing (AC#4)."""
        policy = RetryPolicy(
            max_retries=2,
            backoff_delays=(0.01, 0.02, 0.04),  # Fast for testing
            request_timeout=0.1,
        )
        
        provider = AsyncMock()
        provider.model_name = "test-model"
        provider.is_available.return_value = True
        provider.get_model_name.return_value = "test-model"
        # Fail twice, then succeed
        provider.complete_async.side_effect = [
            LLMProviderUnavailable("fail 1"),
            LLMProviderUnavailable("fail 2"),
            LLMResponse(content="success", model="test-model", usage=None, latency_ms=10.0),
        ]
        
        router = ModelRouter(providers={TaskComplexity.STANDARD: provider})
        gateway = LLMGateway(rate_limiter, router, queue, retry_policy=policy)
        
        request = LLMRequest(prompt="test", model="auto")
        
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            response = await gateway._execute_with_retry(request)
            
            assert response.content == "success"
            assert mock_sleep.call_count == 2
            # Verify backoff delays
            calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert calls == [0.01, 0.02]

    @pytest.mark.asyncio
    async def test_router_respects_circuit_breaker_during_selection(
        self, rate_limiter, queue
    ):
        """Test router checks circuit breaker during model selection (AC#7)."""
        import time
        
        # Use MagicMock for sync methods, attach AsyncMock for async methods
        fast_provider = MagicMock()
        fast_provider.model_name = "fast-model"
        fast_provider.is_available.return_value = True
        fast_provider.get_model_name.return_value = "fast-model"
        fast_provider.complete_async = AsyncMock()
        
        # Create fallback provider inline to ensure same instance
        fallback_provider = MagicMock()
        fallback_provider.model_name = "fallback-model"
        fallback_provider.is_available.return_value = True
        fallback_provider.get_model_name.return_value = "fallback-model"
        fallback_provider.complete_async = AsyncMock()
        
        router = ModelRouter(
            providers={
                TaskComplexity.FAST: fast_provider,
                TaskComplexity.STANDARD: fallback_provider,
            }
        )
        
        gateway = LLMGateway(rate_limiter, router, queue)
        
        # Manually exclude the FAST model using proper monotonic time
        gateway._model_excluded_until["fast-model"] = time.monotonic() + 3600
        
        # Verify exclusion is active
        assert gateway.is_excluded("fast-model") is True
        
        # Router should skip excluded model
        selected = router.select_model(TaskComplexity.FAST)
        
        # Should get fallback since FAST is excluded - verify by model_name
        assert selected.model_name == "fallback-model"

    @pytest.mark.asyncio
    async def test_graceful_error_response_after_retries_exhausted(
        self, rate_limiter, queue
    ):
        """Test graceful error response when all retries fail (AC#5)."""
        policy = RetryPolicy(max_retries=1, request_timeout=0.1)
        
        provider = AsyncMock()
        provider.model_name = "fail-model"
        provider.is_available.return_value = True
        provider.get_model_name.return_value = "fail-model"
        provider.complete_async.side_effect = LLMProviderUnavailable("always fails")
        
        router = ModelRouter(providers={TaskComplexity.STANDARD: provider})
        gateway = LLMGateway(rate_limiter, router, queue, retry_policy=policy)
        
        # Create priority request
        request = LLMRequest(prompt="fail", model="auto")
        future = asyncio.Future()
        preq = PriorityRequest(request=request, priority=0, sequence=0, future=future)
        
        queue.dequeue.side_effect = [preq, asyncio.CancelledError()]
        
        def complete_request_side_effect(req, response):
            req.future.set_result(response)
        
        queue.complete_request.side_effect = complete_request_side_effect
        
        # Run worker
        gateway._running = True
        with patch("asyncio.sleep", new_callable=AsyncMock):
            try:
                await gateway._process_requests()
            except asyncio.CancelledError:
                pass
        
        # Should have error response
        response = await future
        assert "error" in response.finish_reason
        assert "transient" in response.finish_reason or "LLMProviderUnavailable" in response.finish_reason


class TestRateLimitRetryIntegration:
    """Integration tests for rate limit retry behavior."""

    @pytest.mark.asyncio
    async def test_rate_limit_retry_respects_retry_after(self):
        """Test that retry_after header is respected (Task 10)."""
        from cyberred.core.exceptions import LLMRateLimitExceeded
        
        rate_limiter = MagicMock(spec=RateLimiter)
        rate_limiter.acquire_async.return_value = True
        
        queue = MagicMock(spec=LLMPriorityQueue)
        
        policy = RetryPolicy(max_retries=1)
        
        provider = AsyncMock()
        provider.model_name = "rate-limited-model"
        provider.is_available.return_value = True
        provider.get_model_name.return_value = "rate-limited-model"
        
        # First call raises rate limit with retry_after, second succeeds
        rate_limit_error = LLMRateLimitExceeded("test", 30)
        rate_limit_error.retry_after = 5.0
        provider.complete_async.side_effect = [
            rate_limit_error,
            LLMResponse(content="success", model="test", usage=None, latency_ms=10.0),
        ]
        
        router = ModelRouter(providers={TaskComplexity.STANDARD: provider})
        gateway = LLMGateway(rate_limiter, router, queue, retry_policy=policy)
        
        request = LLMRequest(prompt="test", model="auto")
        
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            response = await gateway._execute_with_retry(request)
            
            assert response.content == "success"
            # Should have used retry_after delay (5.0)
            mock_sleep.assert_called_with(5.0)

    @pytest.mark.asyncio
    async def test_rate_limit_retry_after_capped_at_60s(self):
        """Test that retry_after is capped at 60s maximum."""
        from cyberred.core.exceptions import LLMRateLimitExceeded
        
        rate_limiter = MagicMock(spec=RateLimiter)
        rate_limiter.acquire_async.return_value = True
        
        queue = MagicMock(spec=LLMPriorityQueue)
        
        policy = RetryPolicy(max_retries=1)
        
        provider = AsyncMock()
        provider.model_name = "rate-limited-model"
        provider.is_available.return_value = True
        provider.get_model_name.return_value = "rate-limited-model"
        
        # Rate limit with very long retry_after
        rate_limit_error = LLMRateLimitExceeded("test", 30)
        rate_limit_error.retry_after = 300.0  # 5 minutes - should be capped
        provider.complete_async.side_effect = [
            rate_limit_error,
            LLMResponse(content="success", model="test", usage=None, latency_ms=10.0),
        ]
        
        router = ModelRouter(providers={TaskComplexity.STANDARD: provider})
        gateway = LLMGateway(rate_limiter, router, queue, retry_policy=policy)
        
        request = LLMRequest(prompt="test", model="auto")
        
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            response = await gateway._execute_with_retry(request)
            
            assert response.content == "success"
            # Should have used capped delay (60.0)
            mock_sleep.assert_called_with(60.0)
