import pytest
import asyncio
import unittest.mock
import time
from unittest.mock import AsyncMock, MagicMock
from cyberred.llm.gateway import LLMGateway
from cyberred.llm.rate_limiter import RateLimiter
from cyberred.llm.router import ModelRouter, TaskComplexity
from cyberred.llm.priority_queue import LLMPriorityQueue
from cyberred.llm.retry import RetryPolicy

@pytest.fixture
def mock_rate_limiter():
    return MagicMock(spec=RateLimiter)

@pytest.fixture
def mock_router():
    return MagicMock(spec=ModelRouter)

@pytest.fixture
def mock_queue():
    return MagicMock(spec=LLMPriorityQueue)

class TestGatewayCreation:

    def test_gateway_creation(self, mock_rate_limiter, mock_router, mock_queue):
        """Test that the gateway can be instantiated with required components."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        
        assert gateway is not None
        # Verify internal state initialization mentioned in task
        assert gateway._rate_limiter == mock_rate_limiter
        assert gateway._router == mock_router
        assert gateway._queue == mock_queue
        assert gateway._running is False
        assert gateway._running is False
        assert gateway._worker_task is None

    def test_gateway_router_exclusion_integration(self, mock_rate_limiter, mock_router, mock_queue):
        """Test gateway configures router with exclusion checker."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        
        # Check if private attribute was set on router
        assert mock_router._exclusion_checker == gateway.is_excluded

    def test_gateway_init_router_missing_attribute(self, mock_rate_limiter, mock_queue):
        """Test gateway init robust to router missing _exclusion_checker."""
        router = object() # Can't set attributes on object()
        gateway = LLMGateway(mock_rate_limiter, router, mock_queue)
        # Should not raise exception
        assert gateway is not None

    def test_gateway_uses_retry_policy(self, mock_rate_limiter, mock_router, mock_queue):
        """Test gateway accepts and uses RetryPolicy."""
        from cyberred.llm.retry import RetryPolicy
        
        policy = RetryPolicy(
            max_retries=5,
            request_timeout=15.0,
            backoff_delays=(0.1, 0.2),
            cb_failure_threshold=10,
            cb_exclusion_duration=120.0
        )
        
        # Test constructor accepts policy
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue, retry_policy=policy)
        
        assert gateway._retry_policy == policy
        assert gateway._max_retries == 5
        assert gateway._request_timeout == 15.0
        
        # Verify legacy args are gone (Red will fail here because signature is old)
        # OR legacy args map to policy defaults?
        # Task says "Remove individual timeout/retry parameters"
        # So we should assume signature changes.

from cyberred.llm.gateway import initialize_gateway, get_gateway, shutdown_gateway

class TestGatewaySingleton:
    def test_singleton_pattern(self, mock_rate_limiter, mock_router, mock_queue):
        """Test the singleton initialization and access."""
        # Ensure clean state
        shutdown_gateway()
        
        # Test initialization
        g1 = initialize_gateway(mock_rate_limiter, mock_router, mock_queue)
        assert isinstance(g1, LLMGateway)
        
        # Test access
        g2 = get_gateway()
        assert g1 is g2
        
        # Test double initialization raises error
        with pytest.raises(RuntimeError):
            initialize_gateway(mock_rate_limiter, mock_router, mock_queue)
            
        # Test shutdown
        shutdown_gateway()
        
        # Test access after shutdown raises error
        with pytest.raises(RuntimeError):
            get_gateway()

from cyberred.llm.provider import LLMRequest, LLMResponse

class TestRequestEntryPoints:
    @pytest.mark.asyncio
    async def test_director_complete(self, mock_rate_limiter, mock_router, mock_queue):
        """Test director_complete enqueues with director priority."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        
        request = LLMRequest(prompt="strategy", model="auto")
        expected_response = LLMResponse(content="plan", model="test-model", usage=None, latency_ms=100.0)
        
        # Mock the queue returning a future that resolves only when awaited
        future = asyncio.Future()
        future.set_result(expected_response)
        
        # enqueue_director should return a future (not the response directly)
        mock_queue.enqueue_director.return_value = future
        
        response = await gateway.director_complete(request)
        
        assert response == expected_response
        mock_queue.enqueue_director.assert_called_once_with(request)
    
    @pytest.mark.asyncio
    async def test_agent_complete(self, mock_rate_limiter, mock_router, mock_queue):
        """Test agent_complete enqueues with agent priority."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        request = LLMRequest(prompt="task", model="auto")
        expected_response = LLMResponse(content="result", model="test", usage=None, latency_ms=50.0)
        
        future = asyncio.Future()
        future.set_result(expected_response)
        mock_queue.enqueue_agent.return_value = future
        
        response = await gateway.agent_complete(request)
        
        assert response == expected_response
        mock_queue.enqueue_agent.assert_called_once_with(request)
    
    @pytest.mark.asyncio
    async def test_generic_complete(self, mock_rate_limiter, mock_router, mock_queue):
        """Test generic complete delegates correctly."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        request = LLMRequest(prompt="generic", model="auto")
        expected_response = LLMResponse(content="generic", model="test", usage=None, latency_ms=10.0)
        
        future = asyncio.Future()
        future.set_result(expected_response)
        
        # Test director delegation
        mock_queue.enqueue_director.return_value = future
        await gateway.complete(request, is_director=True)
        mock_queue.enqueue_director.assert_called_once_with(request)
        
        # Test agent delegation (default)
        mock_queue.enqueue_agent.return_value = future
        await gateway.complete(request, is_director=False)
        mock_queue.enqueue_agent.assert_called_once_with(request)

from cyberred.llm.priority_queue import PriorityRequest

class TestBackgroundWorker:
    @pytest.mark.asyncio
    async def test_worker_processes_requests(self, mock_rate_limiter, mock_router, mock_queue):
        """Test that the worker processes requests in priority order."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        
        # Setup mocks
        mock_rate_limiter.acquire_async.return_value = True
        
        provider = AsyncMock()
        expected_response = LLMResponse(content="done", model="test", usage=None, latency_ms=10.0)
        provider.complete_async.return_value = expected_response
        
        mock_router.infer_complexity.return_value = TaskComplexity.STANDARD
        mock_router.select_model.return_value = provider
        
        # Determine strict priority order via queue mock
        req1 = LLMRequest(prompt="p0", model="auto")
        req2 = LLMRequest(prompt="p1", model="auto")
        
        preq1 = PriorityRequest(request=req1, priority=0, sequence=0, future=asyncio.Future())
        preq2 = PriorityRequest(request=req2, priority=1, sequence=1, future=asyncio.Future())
        
        # Dequeue returns req1, then req2, then cancels loop by raising CancelledError
        mock_queue.dequeue.side_effect = [preq1, preq2, asyncio.CancelledError()]
        
        # Manually start worker loop (bypassing start() which creates task)
        # We set _running = True for the loop to enter
        gateway._running = True
        try:
            await gateway._process_requests()
        except asyncio.CancelledError:
            pass
        
        # Verification
        # 1. Rate limiter acquired twice
        assert mock_rate_limiter.acquire_async.call_count == 2
        
        # 2. Router used twice
        assert mock_router.select_model.call_count == 2
        
        # 3. Provider called twice
        assert provider.complete_async.call_count == 2
        
        # 4. Queue completion called twice
        assert mock_queue.complete_request.call_count == 2
        mock_queue.complete_request.assert_any_call(preq1, expected_response)
        mock_queue.complete_request.assert_any_call(preq2, expected_response)

class TestGatewayLifecycle:
    @pytest.mark.asyncio
    async def test_gateway_lifecycle(self, mock_rate_limiter, mock_router, mock_queue):
        """Test start/stop and context manager."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        
        # Test explicit start/stop
        await gateway.start()
        assert gateway._running is True
        assert gateway._worker_task is not None
        
        await gateway.stop()
        assert gateway._running is False
        assert gateway._worker_task is None
        
        # Test context manager
        async with gateway as g:
            assert g is gateway
            assert gateway._running is True
            assert gateway._worker_task is not None
        
        assert gateway._running is False
        assert gateway._worker_task is None

from cyberred.core.exceptions import LLMTimeoutError, LLMProviderUnavailable, LLMRateLimitExceeded

class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_request_timeout(self, mock_rate_limiter, mock_router, mock_queue):
        """Test that requests timeout if provider takes too long."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue, retry_policy=RetryPolicy(request_timeout=0.1))
        
        # Setup mock to hang
        provider = AsyncMock()
        async def delay(*args, **kwargs):
            await asyncio.sleep(0.5)
            # Should not be reached if timeout works
            return LLMResponse(content="slow", model="test", usage=None)
            
        provider.complete_async.side_effect = delay
        
        mock_router.infer_complexity.return_value = TaskComplexity.STANDARD
        mock_router.select_model.return_value = provider
        
        # Mock rate limiter
        mock_rate_limiter.acquire_async.return_value = True
        
        request = LLMRequest(prompt="timeout", model="auto")
        
        with pytest.raises(LLMTimeoutError):
            await gateway._execute_with_retry(request)

    @pytest.mark.asyncio
    async def test_retry_with_backoff(self, mock_rate_limiter, mock_router, mock_queue):
        """Test retry logic with exponential backoff."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue, retry_policy=RetryPolicy(max_retries=2))
        
        provider = AsyncMock()
        # Fail twice with timeout, then succeed
        provider.complete_async.side_effect = [
            asyncio.TimeoutError(),
            asyncio.TimeoutError(),
            LLMResponse(content="success", model="test", usage=None, latency_ms=10.0),
        ]
        
        mock_router.infer_complexity.return_value = TaskComplexity.STANDARD
        mock_router.select_model.return_value = provider
        mock_rate_limiter.acquire_async.return_value = True
        
        request = LLMRequest(prompt="retry", model="auto")
        
        # We need to mock sleep to speed up test
        with unittest.mock.patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            response = await gateway._execute_with_retry(request)
            
            assert response.content == "success"
            # Should have slept twice (backoff)
            assert mock_sleep.call_count == 2
            # Delays: 1.0, 2.0
            mock_sleep.assert_any_call(1.0)
            mock_sleep.assert_any_call(2.0)

    @pytest.mark.asyncio
    async def test_graceful_failure_response(self, mock_rate_limiter, mock_router, mock_queue):
        """Test that exhausted retries return error response instead of raising."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue, retry_policy=RetryPolicy(max_retries=1))
        
        provider = AsyncMock()
        # Always fail
        provider.complete_async.side_effect = LLMProviderUnavailable("fail")
        
        mock_router.infer_complexity.return_value = TaskComplexity.STANDARD
        mock_router.select_model.return_value = provider
        mock_rate_limiter.acquire_async.return_value = True
        
        request = LLMRequest(prompt="graceful", model="auto")
        
        # We need to simulate the worker processing flow because graceful handling happens in _process_requests
        # AND we need to verify what `gateway.complete` returns.
        # But `gateway.complete` delegates to queue. 
        # The worker calls `queue.complete_request(req, result)` or `queue.fail_request(req, e)`.
        
        # We need to mock queue.dequeue to return our request, then inspect call to complete_request
        from cyberred.llm.priority_queue import PriorityRequest
        
        future = asyncio.Future()
        preq = PriorityRequest(request=request, priority=0, sequence=0, future=future)
        
        mock_queue.dequeue.side_effect = [preq, asyncio.CancelledError()]
        
        # Helper to set future when complete_request is called
        def complete_request_side_effect(request, result):
            request.future.set_result(result)
            
        mock_queue.complete_request.side_effect = complete_request_side_effect
        
        # Use mocked sleep
        with unittest.mock.patch("asyncio.sleep", new_callable=AsyncMock):
            gateway._running = True
            try:
                await gateway._process_requests()
            except asyncio.CancelledError:
                pass
                
        # With current implementation (fail_request), future has exception.
        # We expect FUTURE to have RESULT (response) with error info.
        
        # This will raise exception if fail_request was called
        # We catch it to verify Red state, or assert result if Green
        
        # If Future has exception, this await raises.
        # We want to assert NO exception raised, and result is valid
        
        response = await future # Should not raise
        assert response.content == ""
        assert "error" in response.finish_reason
        # Task 9: Verify structured error fields
        assert "transient" in response.finish_reason
        assert "LLMProviderUnavailable" in response.finish_reason

class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_circuit_breaker_excludes_model(self, mock_rate_limiter, mock_router, mock_queue):
        """Test that models are excluded after repeated failures."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue, retry_policy=RetryPolicy(max_retries=1))
        
        # Setup mocks
        mock_rate_limiter.acquire_async.return_value = True
        
        provider = AsyncMock()
        provider.model_name = "test-model"
        # Always fail
        provider.complete_async.side_effect = LLMProviderUnavailable("fail")
        
        mock_router.infer_complexity.return_value = TaskComplexity.STANDARD
        mock_router.select_model.return_value = provider
        
        request = LLMRequest(prompt="break", model="auto")
        
        # Trigger failures (threshold is 3)
        # We need 3 FAILURES, not just attempts. 
        # With max_retries=1, each call does 2 attempts.
        # So calling _execute_with_retry twice should be enough to trigger if threshold is based on total failures
        
        # Call 1: 2 failures
        with pytest.raises(LLMProviderUnavailable):
            await gateway._execute_with_retry(request)
            
        assert gateway._model_failures.get("test-model", 0) == 2
        
        # Call 2: 2 more failures -> hits threshold (3)
        with pytest.raises(LLMProviderUnavailable):
            await gateway._execute_with_retry(request)
            
        assert gateway._model_failures.get("test-model", 0) == 4
        
        # Verify circuit breaker triggered
        assert "test-model" in gateway._model_excluded_until
        exclusion_time = gateway._model_excluded_until["test-model"]
        assert exclusion_time > 0
        
        exclusion_time = gateway._model_excluded_until["test-model"]
        assert exclusion_time > 0
        
        # Verify router refresh called
        # We expect it to be called when exclusion happens
        # Note: We need to implement this integration
        mock_router.refresh_availability.assert_called()

    @pytest.mark.asyncio
    async def test_gateway_is_excluded(self, mock_rate_limiter, mock_router, mock_queue):
        """Test is_excluded method returns correct state."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        
        # Test default
        assert gateway.is_excluded("mock-model") is False
        
        # Manually force exclusion
        with gateway._cb_lock:
            # Set to 1 hour in future
            gateway._model_excluded_until["mock-model"] = time.monotonic() + 3600
            
        assert gateway.is_excluded("mock-model") is True
        
        # Manually force expiration
        with gateway._cb_lock:
            # Set to 1 hour in past
            gateway._model_excluded_until["mock-model"] = time.monotonic() - 3600
            
        assert gateway.is_excluded("mock-model") is False
        # Entry should be removed
        assert "mock-model" not in gateway._model_excluded_until

    @pytest.mark.asyncio
    async def test_exclusion_expiry_logging(self, mock_rate_limiter, mock_router, mock_queue):
        """Test that expiry logs a message."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        
        # Manually force exclusion in past
        with gateway._cb_lock:
            gateway._model_excluded_until["mock-model"] = time.monotonic() - 10
            
        with unittest.mock.patch("cyberred.llm.gateway.log") as mock_log:
            gateway.is_excluded("mock-model")
            
            # Should have logged "circuit_breaker_reset"
            mock_log.info.assert_called_with("circuit_breaker_reset", model="mock-model")

    @pytest.mark.asyncio
    async def test_worker_error_handling(self, mock_rate_limiter, mock_router, mock_queue):
        """Test worker handles unexpected exceptions gracefully."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        
        # Setup queue to raise generic exception then empty
        mock_queue.dequeue.side_effect = [
            RuntimeError("Unexpected error"),
            asyncio.CancelledError()
        ]
        
        gateway._running = True
        try:
            await gateway._process_requests()
        except asyncio.CancelledError:
            pass
        
        # Worker should have continued after RuntimeError
        assert mock_queue.dequeue.call_count == 2
        
    @pytest.mark.asyncio
    async def test_record_failure_router_error(self, mock_rate_limiter, mock_router, mock_queue):
        """Test that router refresh failure is ignored."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue, retry_policy=RetryPolicy(max_retries=1))
        
        # Setup calling record failure directly to hit thresholds
        # Mock router refresh to fail
        mock_router.refresh_availability.side_effect = RuntimeError("Refresh failed")
        
        # Force failures
        with gateway._cb_lock:
            gateway._model_failures["test"] = 2
        
        gateway._record_failure("test")
        
        # Should not raise exception
        assert gateway._model_failures["test"] == 3
        # Refresh was called
        mock_router.refresh_availability.assert_called_once()

    @pytest.mark.asyncio
    async def test_provider_no_name_error(self, mock_rate_limiter, mock_router, mock_queue):
        """Test failure recording when provider has no model name."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue, retry_policy=RetryPolicy(max_retries=1))
        
        mock_rate_limiter.acquire_async.return_value = True
        # Spec with only complete_async, so model_name raises AttributeError
        provider = AsyncMock(spec=["complete_async"]) 
        provider.complete_async.side_effect = LLMProviderUnavailable("fail")
        
        mock_router.infer_complexity.return_value = TaskComplexity.STANDARD
        mock_router.select_model.return_value = provider
        
        request = LLMRequest(prompt="fail", model="auto")
        
        with pytest.raises(LLMProviderUnavailable):
            await gateway._execute_with_retry(request)
            
        # No failures recorded (key error or empty)
        assert len(gateway._model_failures) == 0

    @pytest.mark.asyncio
    async def test_stop_error_handling(self, mock_rate_limiter, mock_router, mock_queue):
        """Test error handling during stop."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        await gateway.start()
        
        # Mock task to raise CancelledError when awaited
        async def corrupted_task():
            raise asyncio.CancelledError()
            
        gateway._worker_task = asyncio.create_task(corrupted_task())
        
        # Should not raise exception
        await gateway.stop()
        assert gateway._running is False

    @pytest.mark.asyncio
    async def test_start_already_running(self, mock_rate_limiter, mock_router, mock_queue):
        """Test start when already running."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        await gateway.start()
        original_task = gateway._worker_task
        
        # Call start again
        await gateway.start()
        
        # Should be same task (no new task created)
        assert gateway._worker_task is original_task
        
        await gateway.stop()

    @pytest.mark.asyncio
    async def test_stop_not_running(self, mock_rate_limiter, mock_router, mock_queue):
        """Test stop when not running."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        assert gateway._worker_task is None
        
        # Should not raise error
        await gateway.stop()

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, mock_rate_limiter, mock_router, mock_queue):
        """Test rate limit acquisition failure."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        
        # Rate limiter returns False (timeout)
        mock_rate_limiter.acquire_async.return_value = False
        
        request = LLMRequest(prompt="fail", model="auto")
        
        with pytest.raises(LLMRateLimitExceeded):
            await gateway._execute_with_retry(request)

    @pytest.mark.asyncio
    async def test_max_retries_fallback(self, mock_rate_limiter, mock_router, mock_queue):
        """Test backoff fallback for high retry counts."""
        # max_retries = 4, delays list has 3 items
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue, retry_policy=RetryPolicy(max_retries=4))
        
        provider = AsyncMock()
        provider.complete_async.side_effect = LLMProviderUnavailable("fail")
        
        mock_router.infer_complexity.return_value = TaskComplexity.STANDARD
        mock_router.select_model.return_value = provider
        mock_rate_limiter.acquire_async.return_value = True
        
        request = LLMRequest(prompt="retry", model="auto")
        
        with unittest.mock.patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(LLMProviderUnavailable):
                await gateway._execute_with_retry(request)
            
            # Should have slept 4 times
            assert mock_sleep.call_count == 4
            # Delays: 1.0, 2.0, 4.0, 4.0 (fallback)
            mock_sleep.assert_any_call(4.0)

    @pytest.mark.asyncio
    async def test_non_retryable_error(self, mock_rate_limiter, mock_router, mock_queue):
        """Test non-retryable error logic."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        
        mock_rate_limiter.acquire_async.return_value = True
        provider = AsyncMock()
        provider.complete_async.side_effect = ValueError("Fatal error")
        
        mock_router.infer_complexity.return_value = TaskComplexity.STANDARD
        mock_router.select_model.return_value = provider
        
        request = LLMRequest(prompt="fail", model="auto")
        
        # Should raise ValueError immediately (no retries)
        with pytest.raises(ValueError):
            await gateway._execute_with_retry(request)
            
    @pytest.mark.asyncio
    async def test_worker_fail_request(self, mock_rate_limiter, mock_router, mock_queue):
        """Test worker calling fail_request on exception."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        
        # Mock execute to raise exception
        gateway._execute_with_retry = AsyncMock(side_effect=ValueError("Worker fail"))
        
        priority_request = MagicMock()
        mock_queue.dequeue.side_effect = [priority_request, asyncio.CancelledError()]
        
        gateway._running = True
        try:
            await gateway._process_requests()
        except asyncio.CancelledError:
            pass
            
        # Should now call complete_request with error response
        mock_queue.complete_request.assert_called_once()
        # verify args
        args = mock_queue.complete_request.call_args
        assert args[0][0] == priority_request
        assert args[0][1].finish_reason.startswith("error:")

    @pytest.mark.asyncio
    async def test_rate_limit_retry(self, mock_rate_limiter, mock_router, mock_queue):
        """Test that rate limit exceeded triggers retry."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue, retry_policy=RetryPolicy(max_retries=1))
        
        # First attempt fails with rate limit, second succeeds
        mock_rate_limiter.acquire_async.side_effect = [False, True]
        
        provider = AsyncMock()
        provider.complete_async.return_value = LLMResponse(content="ok", model="test", usage=None, latency_ms=10.0)
        
        mock_router.select_model.return_value = provider
        
        request = LLMRequest(prompt="retry", model="auto")
        
        # Should succeed after retry
        with unittest.mock.patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            response = await gateway._execute_with_retry(request)
            assert response.content == "ok"
            assert mock_sleep.call_count == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_reset_on_success(self, mock_rate_limiter, mock_router, mock_queue):
        """Test that failure count resets on success."""
        # Use max_retries=0 to make failures count effectively immediately per call
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue, retry_policy=RetryPolicy(max_retries=0))
        
        provider = AsyncMock()
        provider.model_name = "test-model"
        
        mock_router.infer_complexity.return_value = TaskComplexity.STANDARD
        mock_router.select_model.return_value = provider
        mock_rate_limiter.acquire_async.return_value = True
        
        request = LLMRequest(prompt="test", model="auto")
        
        # 1. Fail twice
        provider.complete_async.side_effect = LLMProviderUnavailable("fail")
        
        with pytest.raises(LLMProviderUnavailable):
            await gateway._execute_with_retry(request)
        with pytest.raises(LLMProviderUnavailable):
            await gateway._execute_with_retry(request)
            
        # Manually check failures count
        assert gateway._model_failures["test-model"] == 2
        
        # 2. Succeed
        provider.complete_async.side_effect = None
        provider.complete_async.return_value = LLMResponse(content="ok", model="test-model", usage=None, latency_ms=10.0)
        
        await gateway._execute_with_retry(request)
        
        # 3. Verify count reset
        assert gateway._model_failures["test-model"] == 0

    @pytest.mark.asyncio
    async def test_rate_limit_retry_after_respected(self, mock_rate_limiter, mock_router, mock_queue):
        """Test that retry_after from LLMRateLimitExceeded is respected (Task 10)."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue, retry_policy=RetryPolicy(max_retries=1))
        
        mock_rate_limiter.acquire_async.return_value = True
        
        provider = AsyncMock()
        provider.model_name = "test-model"
        
        # Create rate limit error with retry_after
        rate_limit_error = LLMRateLimitExceeded("test", 30)
        rate_limit_error.retry_after = 5.0
        
        provider.complete_async.side_effect = [
            rate_limit_error,
            LLMResponse(content="success", model="test", usage=None, latency_ms=10.0)
        ]
        
        mock_router.infer_complexity.return_value = TaskComplexity.STANDARD
        mock_router.select_model.return_value = provider
        
        request = LLMRequest(prompt="test", model="auto")
        
        with unittest.mock.patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            response = await gateway._execute_with_retry(request)
            
            assert response.content == "success"
            # Should use retry_after delay instead of normal backoff
            mock_sleep.assert_called_with(5.0)

    @pytest.mark.asyncio
    async def test_rate_limit_retry_after_capped(self, mock_rate_limiter, mock_router, mock_queue):
        """Test that retry_after is capped at 60s (Task 10)."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue, retry_policy=RetryPolicy(max_retries=1))
        
        mock_rate_limiter.acquire_async.return_value = True
        
        provider = AsyncMock()
        provider.model_name = "test-model"
        
        # Create rate limit error with very long retry_after
        rate_limit_error = LLMRateLimitExceeded("test", 30)
        rate_limit_error.retry_after = 300.0  # 5 minutes
        
        provider.complete_async.side_effect = [
            rate_limit_error,
            LLMResponse(content="success", model="test", usage=None, latency_ms=10.0)
        ]
        
        mock_router.infer_complexity.return_value = TaskComplexity.STANDARD
        mock_router.select_model.return_value = provider
        
        request = LLMRequest(prompt="test", model="auto")
        
        with unittest.mock.patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            response = await gateway._execute_with_retry(request)
            
            assert response.content == "success"
            # Should be capped at 60s
            mock_sleep.assert_called_with(60.0)

class TestMetrics:
    @pytest.mark.asyncio
    async def test_metrics_tracking(self, mock_rate_limiter, mock_router, mock_queue):
        """Test that metrics are correctly updated."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        
        # Setup for 1 success and 1 failure
        req1 = LLMRequest(prompt="success", model="auto")
        req2 = LLMRequest(prompt="fail", model="auto")
        
        preq1 = PriorityRequest(request=req1, priority=0, sequence=0, future=asyncio.Future())
        preq2 = PriorityRequest(request=req2, priority=0, sequence=1, future=asyncio.Future())
        
        mock_queue.dequeue.side_effect = [preq1, preq2, asyncio.CancelledError()]
        mock_rate_limiter.acquire_async.return_value = True
        
        provider = AsyncMock()
        provider.model_name = "test-model"
        
        # Side effect for _execute_with_retry logic
        mock_router.select_model.return_value = provider
        
        async def side_effect(request):
            if request.prompt == "success":
                return LLMResponse(content="ok", model="test-model", usage=None, latency_ms=10.0)
            raise ValueError("Fail")
            
        provider.complete_async.side_effect = side_effect
        
        # Run worker
        gateway._running = True
        try:
            await gateway._process_requests()
        except asyncio.CancelledError:
            pass
            
        # Check metrics
        assert gateway.total_requests == 2
        assert gateway.total_successes == 1
        assert gateway.total_failures == 1
        assert gateway.avg_latency_ms >= 0.0

    @pytest.mark.asyncio
    async def test_retry_metrics(self, mock_rate_limiter, mock_router, mock_queue):
        """Test that retries are counted in metrics."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue, retry_policy=RetryPolicy(max_retries=1))
        
        provider = AsyncMock()
        provider.complete_async.side_effect = [
            asyncio.TimeoutError(),
            LLMResponse(content="ok", model="test", usage=None, latency_ms=10.0)
        ]
        
        mock_router.select_model.return_value = provider
        mock_rate_limiter.acquire_async.return_value = True
        
        request = LLMRequest(prompt="test", model="auto")
        
        # Use mocked sleep to be fast
        with unittest.mock.patch("asyncio.sleep", new_callable=AsyncMock):
            await gateway._execute_with_retry(request)
            
        assert gateway.total_retries == 1

    @pytest.mark.asyncio
    async def test_metrics_edge_cases(self, mock_rate_limiter, mock_router, mock_queue):
        """Test edge cases for metrics properties."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        
        # 1. Zero successes latency
        assert gateway.avg_latency_ms == 0.0
        
        # 2. Queue depth delegation
        mock_queue.total_queue_depth = 42
        assert gateway.queue_depth == 42
        
    @pytest.mark.asyncio
    async def test_success_no_model_name(self, mock_rate_limiter, mock_router, mock_queue):
        """Test success path with provider missing model_name."""
        gateway = LLMGateway(mock_rate_limiter, mock_router, mock_queue)
        
        mock_rate_limiter.acquire_async.return_value = True
        
        # Use standard AsyncMock but set model_name to None explicitly
        # This ensures getattr(provider, "model_name", None) returns None if accessed directly
        # or if we accessed it as attribute.
        # But wait, gateway uses getattr(provider, "model_name", None).
        # If provider.model_name = None, getattr returns None.
        provider = AsyncMock() 
        provider.model_name = None
        provider.complete_async.return_value = LLMResponse(content="ok", model="unknown", usage=None, latency_ms=10.0)
        
        mock_router.infer_complexity.return_value = TaskComplexity.STANDARD
        mock_router.select_model.return_value = provider
        
        request = LLMRequest(prompt="test", model="auto")
        
        response = await gateway._execute_with_retry(request)
        assert response.content == "ok"

