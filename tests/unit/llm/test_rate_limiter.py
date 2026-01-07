import pytest
import asyncio
import time
import threading
from cyberred.llm.rate_limiter import RateLimiter

class TestRateLimiter:
    def test_rate_limiter_creation(self):
        """Test that RateLimiter can be instantiated with valid parameters."""
        limiter = RateLimiter(rpm=30, burst=5)
        assert limiter is not None
        
        # Test default values
        limiter_default = RateLimiter()
        assert limiter_default is not None

    def test_rate_limiter_validation(self):
        """Test that RateLimiter validates input parameters."""
        with pytest.raises(ValueError, match="rpm must be positive"):
            RateLimiter(rpm=0, burst=5)
            
        with pytest.raises(ValueError, match="burst must be at least 1"):
            RateLimiter(rpm=30, burst=0)

    def test_context_manager(self):
        """Test that RateLimiter works as a context manager."""
        limiter = RateLimiter(rpm=30, burst=5)
        with limiter as l:
            assert l is limiter
        
        # Verify context manager exit handling
        try:
            with limiter:
                raise ValueError("test error")
        except ValueError:
            pass

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test that RateLimiter works as an async context manager."""
        limiter = RateLimiter(rpm=30, burst=5)
        async with limiter as l:
            assert l is limiter
            
        # Verify async context manager exit handling
        try:
            async with limiter:
                raise ValueError("test error")
        except ValueError:
            pass

    def test_refill_logic_edge_cases(self):
        """Test refill logic edge cases."""
        limiter = RateLimiter(rpm=60, burst=5)
        
        # Manually set tokens to max
        limiter._tokens = 5.0
        limiter._last_refill = time.monotonic() - 10.0
        
        # Refill shouldn't exceed burst
        limiter._refill()
        assert limiter._tokens == 5.0
        
        # Test 0 tokens to add
        limiter._last_refill = time.monotonic()
        limiter._refill()
        assert limiter._tokens == 5.0

    def test_token_refill(self):
        """Test that tokens are refilled over time."""
        limiter = RateLimiter(rpm=60, burst=5)
        # Manually drain tokens to 0
        limiter._tokens = 0
        limiter._last_refill = time.monotonic() - 1.0  # Simulate 1 second passed
        
        limiter._refill()
        
        # Should have regenerated 1 token (60 RPM = 1 RPS)
        assert limiter._tokens >= 1.0
        assert limiter._tokens <= 1.1  # Allow small margin

    def test_acquire_blocks_when_empty(self):
        """Test that acquire blocks when tokens are exhausted."""
        limiter = RateLimiter(rpm=60, burst=1)
        
        # First acquire should succeed immediately
        assert limiter.acquire() is True
        
        # Second acquire should block and wait for refill
        start_time = time.monotonic()
        assert limiter.acquire(timeout=2.0) is True
        elapsed = time.monotonic() - start_time
        
        # Should wait approx 1 second for refill (60 RPM = 1 RPS)
        assert elapsed >= 0.9

    def test_acquire_timeout(self):
        """Test that acquire returns False on timeout."""
        limiter = RateLimiter(rpm=60, burst=1)
        
        # Consume available token
        limiter.acquire()
        
        # Try to acquire again with short timeout
        start_time = time.monotonic()
        assert limiter.acquire(timeout=0.1) is False
        elapsed = time.monotonic() - start_time
        
        # Should have waited for timeout
        assert elapsed >= 0.1

    @pytest.mark.asyncio
    async def test_acquire_async(self):
        """Test that acquire_async works correctly."""
        limiter = RateLimiter(rpm=60, burst=1)
        
        # First acquire should succeed immediately
        assert await limiter.acquire_async() is True
        
        # Second acquire should wait
        start_time = time.monotonic()
        assert await limiter.acquire_async(timeout=2.0) is True
        elapsed = time.monotonic() - start_time
        
        # Should wait approx 1 second
        assert elapsed >= 0.9

    def test_queue_depth(self):
        """Test that queue depth is tracked correctly."""
        limiter = RateLimiter(rpm=60, burst=1)
        
        # Initial depth should be 0
        assert limiter.queue_depth == 0
        
        # Consume token
        limiter.acquire()
        
        # Start a thread to wait for token
        def wait_for_token():
            limiter.acquire()
            
        t = threading.Thread(target=wait_for_token)
        t.start()
        
        # Wait a bit for thread to start waiting
        time.sleep(0.1)
        
        # Depth should increase
        assert limiter.queue_depth == 1
        
        # Wait for thread to finish (should take ~1s)
        t.join()
        
        # Depth should return to 0
        assert limiter.queue_depth == 0

    def test_try_acquire_non_blocking(self):
        """Test try_acquire returns immediately."""
        limiter = RateLimiter(rpm=60, burst=1)
        
        # Should succeed
        assert limiter.try_acquire() is True
        
        # Should fail immediately (not block)
        start_time = time.monotonic()
        assert limiter.try_acquire() is False
        elapsed = time.monotonic() - start_time
        
        # Should be very fast
        assert elapsed < 0.1

    def test_metrics_properties(self):
        """Test metrics properties."""
        limiter = RateLimiter(rpm=30, burst=5)
        
        assert limiter.requests_per_minute == 30
        assert limiter.burst_limit == 5
        
        # Initial tokens should be equal to burst
        assert limiter.available_tokens == 5.0
        
        # Consume one
        limiter.acquire()
        assert limiter.available_tokens < 5.0

    def test_rate_limited_provider_wraps_calls(self):
        """Test RateLimitedProvider wraps calls."""
        from cyberred.llm.rate_limiter import RateLimitedProvider
        from cyberred.llm.provider import LLMProvider, LLMRequest, LLMResponse
        from unittest.mock import Mock, MagicMock
        
        mock_provider = Mock(spec=LLMProvider)
        from cyberred.llm.provider import TokenUsage
        
        mock_usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        mock_response = LLMResponse(
            content="test",
            model="mock-model",
            usage=mock_usage,
            latency_ms=100
        )
        mock_provider.complete.return_value = mock_response
        
        limiter = RateLimiter(rpm=60, burst=1)
        wrapper = RateLimitedProvider(provider=mock_provider, rate_limiter=limiter)
        
        request = LLMRequest(prompt="hello", model="mock-model")
        response = wrapper.complete(request)
        
        assert response == mock_response
        mock_provider.complete.assert_called_once_with(request)

    def test_rate_limited_provider_complete_raises_on_timeout(self):
        """Test RateLimitedProvider raises exception on acquire timeout."""
        from cyberred.llm.rate_limiter import RateLimitedProvider
        from cyberred.llm.provider import LLMProvider, LLMRequest
        from cyberred.core.exceptions import LLMRateLimitExceeded
        from unittest.mock import Mock
        
        mock_provider = Mock(spec=LLMProvider)
        
        # Create rate limiter with 0 burst (already empty)
        limiter = RateLimiter(rpm=60, burst=1)
        limiter.acquire() # Consume token
        
        # Use short timeout for test
        wrapper = RateLimitedProvider(
            provider=mock_provider,
            rate_limiter=limiter,
            acquire_timeout=0.1
        )
        
        request = LLMRequest(prompt="hello", model="mock-model")
        
        with pytest.raises(LLMRateLimitExceeded, match="Rate limit acquire timeout"):
            wrapper.complete(request)

    @pytest.mark.asyncio
    async def test_rate_limited_provider_complete_async(self):
        """Test RateLimitedProvider wraps async calls."""
        from cyberred.llm.rate_limiter import RateLimitedProvider
        from cyberred.llm.provider import LLMProvider, LLMRequest, LLMResponse, TokenUsage
        from unittest.mock import Mock, AsyncMock
        
        mock_provider = Mock(spec=LLMProvider)
        mock_usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        mock_response = LLMResponse(
            content="test",
            model="mock-model",
            usage=mock_usage,
            latency_ms=100
        )
        mock_provider.complete_async = AsyncMock(return_value=mock_response)
        
        limiter = RateLimiter(rpm=60, burst=1)
        wrapper = RateLimitedProvider(provider=mock_provider, rate_limiter=limiter)
        
        request = LLMRequest(prompt="hello", model="mock-model")
        response = await wrapper.complete_async(request)
        
        assert response == mock_response
        mock_provider.complete_async.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_rate_limited_provider_complete_async_raises_on_timeout(self):
        """Test RateLimitedProvider raises exception on async acquire timeout."""
        from cyberred.llm.rate_limiter import RateLimitedProvider
        from cyberred.llm.provider import LLMProvider, LLMRequest
        from cyberred.core.exceptions import LLMRateLimitExceeded
        from unittest.mock import Mock
        
        mock_provider = Mock(spec=LLMProvider)
        
        # Create rate limiter with 0 burst (already empty)
        limiter = RateLimiter(rpm=60, burst=1)
        limiter.acquire() # Consume token
        
        # Use short timeout for test
        wrapper = RateLimitedProvider(
            provider=mock_provider,
            rate_limiter=limiter,
            acquire_timeout=0.1
        )
        
        request = LLMRequest(prompt="hello", model="mock-model")
        
        with pytest.raises(LLMRateLimitExceeded, match="Rate limit acquire timeout"):
            await wrapper.complete_async(request)

    def test_validation_negative_rpm(self):
        """Test that negative rpm values are rejected."""
        with pytest.raises(ValueError, match="rpm must be positive"):
            RateLimiter(rpm=-5, burst=5)

    @pytest.mark.asyncio
    async def test_acquire_async_without_timeout(self):
        """Test acquire_async without timeout parameter (covers lines 120-129)."""
        limiter = RateLimiter(rpm=120, burst=1)  # 2 tokens/sec for fast test
        
        # Consume token to force wait path
        await limiter.acquire_async()
        
        # Now acquire without timeout - should wait for refill
        start = time.monotonic()
        result = await limiter.acquire_async()  # No timeout - exercises else branch
        elapsed = time.monotonic() - start
        
        assert result is True
        assert elapsed >= 0.4  # Should wait ~0.5 seconds for refill

    def test_refill_zero_elapsed_time(self):
        """Test refill when no time has passed (covers line 42 false branch)."""
        limiter = RateLimiter(rpm=60, burst=5)
        
        # Force tokens to add = 0 by calling refill immediately twice
        limiter._refill()
        initial_tokens = limiter._tokens
        
        # Call refill again immediately - elapsed should be ~0
        limiter._refill()
        
        # Tokens should not increase significantly (within floating point error)
        assert abs(limiter._tokens - initial_tokens) < 0.001

    def test_refill_no_tokens_to_add_mocked(self):
        """Test refill when tokens_to_add is exactly 0 (covers line 42 false branch via mock)."""
        from unittest.mock import patch
        
        limiter = RateLimiter(rpm=60, burst=5)
        limiter._tokens = 3.0
        
        # Mock time.monotonic to return same value each time (zero elapsed)
        fixed_time = 1000.0
        with patch('cyberred.llm.rate_limiter.time') as mock_time:
            mock_time.monotonic.return_value = fixed_time
            limiter._last_refill = fixed_time  # Same as current time
            
            # Call refill - elapsed will be 0, so tokens_to_add will be 0
            limiter._refill()
            
            # Tokens should remain unchanged
            assert limiter._tokens == 3.0