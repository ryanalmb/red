import asyncio
import threading
import time
from typing import Optional, Dict

import structlog

from cyberred.llm.provider import LLMRequest, LLMResponse, TokenUsage
from cyberred.llm.rate_limiter import RateLimiter
from cyberred.llm.router import ModelRouter
from cyberred.llm.priority_queue import LLMPriorityQueue
from cyberred.llm.retry import RetryPolicy

from cyberred.core.exceptions import (
    LLMTimeoutError, LLMProviderUnavailable, LLMRateLimitExceeded
)

log = structlog.get_logger()

# Singleton instance
_gateway_instance: Optional["LLMGateway"] = None
_gateway_lock = threading.Lock()


def initialize_gateway(
    rate_limiter: RateLimiter,
    router: ModelRouter,
    queue: LLMPriorityQueue,
    retry_policy: Optional[RetryPolicy] = None,
) -> "LLMGateway":
    """Initialize the singleton gateway instance."""
    global _gateway_instance
    with _gateway_lock:
        if _gateway_instance is not None:
            raise RuntimeError("Gateway already initialized")
        _gateway_instance = LLMGateway(rate_limiter, router, queue, retry_policy)
        return _gateway_instance


def get_gateway() -> "LLMGateway":
    """Get the singleton gateway instance."""
    if _gateway_instance is None:
        raise RuntimeError("Gateway not initialized - call initialize_gateway() first")
    return _gateway_instance


def shutdown_gateway() -> None:
    """Shutdown and clear the singleton gateway instance."""
    global _gateway_instance
    with _gateway_lock:
        if _gateway_instance is not None:
            # Gateway shutdown handled by caller via async context manager
            # or explicit stop() call before shutdown_gateway()
            _gateway_instance = None


class LLMGateway:
    """Singleton LLM gateway that manages all requests.
    
    Centralizes rate limiting, model routing, and priority queue management.
    Per architecture: All agent and Director LLM requests flow through this gateway.
    
    ERR2 handling: 3x retry with exponential backoff (1s, 2s, 4s).
    """
    
    def __init__(
        self,
        rate_limiter: RateLimiter,
        router: ModelRouter,
        queue: LLMPriorityQueue,
        retry_policy: Optional[RetryPolicy] = None,
    ) -> None:
        self._rate_limiter = rate_limiter
        self._router = router
        # Wire exclusion checker
        try:
            self._router._exclusion_checker = self.is_excluded
        except AttributeError:
            pass
        self._queue = queue
        
        self._retry_policy = retry_policy or RetryPolicy()
        self._request_timeout = self._retry_policy.request_timeout
        self._max_retries = self._retry_policy.max_retries
        
        # Metrics
        self._metrics_lock = threading.Lock()
        self._total_requests = 0
        self._total_successes = 0
        self._total_failures = 0
        self._total_retries = 0
        self._total_latency_ms = 0.0

        # Circuit breaker state
        self._model_failures: Dict[str, int] = {}
        self._model_excluded_until: Dict[str, float] = {}
        self._cb_lock = threading.Lock()
        
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        
        log.info("gateway_initialized")
    
    async def director_complete(self, request: LLMRequest) -> LLMResponse:
        """Submit a Director request with highest priority.
        
        Director requests are processed before agent requests.
        """
        future = await self._queue.enqueue_director(request)
        return await future
    
    async def agent_complete(self, request: LLMRequest) -> LLMResponse:
        """Submit an Agent request with normal priority."""
        future = await self._queue.enqueue_agent(request)
        return await future
    
    async def complete(
        self, 
        request: LLMRequest, 
        is_director: bool = False
    ) -> LLMResponse:
        """Submit a request with specified priority.
        
        Args:
            request: The LLM request.
            is_director: If True, use Director priority.
            
        Returns:
            The LLM response.
        """
        if is_director:
            return await self.director_complete(request)
        return await self.agent_complete(request)
    
    async def start(self) -> None:
        """Start the background request processing worker."""
        if self._running:
            log.warning("gateway_already_running")
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._process_requests())
        log.info("gateway_started")
    
    async def stop(self) -> None:
        """Stop the gateway and cleanup."""
        self._running = False
        
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        
        log.info("gateway_stopped")
    
    async def _process_requests(self) -> None:
        """Background worker that processes queued requests."""
        while self._running:
            try:
                # Dequeue with timeout to allow shutdown check
                priority_request = await self._queue.dequeue(timeout=1.0)
            except Exception as e:
                # Timeout or other error - continue loop
                continue
            
            # Start timing
            start_time = time.monotonic()
            
            try:
                response = await self._execute_with_retry(priority_request.request)
                self._queue.complete_request(priority_request, response)
                
                # Update metrics
                with self._metrics_lock:
                    self._total_requests += 1
                    self._total_successes += 1
                    latency = (time.monotonic() - start_time) * 1000
                    self._total_latency_ms += latency
                
            except Exception as e:
                # Graceful handling: Return error response instead of causing caller exception
                # Task 9: Structured error fields for monitoring
                error_type = "transient" if isinstance(
                    e, (LLMTimeoutError, LLMRateLimitExceeded, LLMProviderUnavailable)
                ) else "permanent"
                
                retry_info = f"retries={self._retry_policy.max_retries}"
                error_msg = f"{error_type}:{type(e).__name__}:{str(e)} [{retry_info}]"
                
                response = LLMResponse(
                    content="",
                    model="error",
                    usage=TokenUsage(0, 0, 0),
                    latency_ms=int((time.monotonic() - start_time) * 1000),
                    finish_reason=f"error:{error_type}:{type(e).__name__}"
                )
                self._queue.complete_request(priority_request, response)
                
                log.error(
                    "gateway_request_failed",
                    error_type=error_type,
                    error_class=type(e).__name__,
                    error_message=str(e),
                    max_retries=self._retry_policy.max_retries,
                )
                
                # Update metrics
                with self._metrics_lock:
                    self._total_requests += 1
                    self._total_failures += 1
    
    async def _execute_with_retry(self, request: LLMRequest) -> LLMResponse:
        """Execute request with retry and exponential backoff.
        
        Per ERR2: 3x retry with exponential backoff (1s, 2s, 4s).
        """
        
        backoff_delays = self._retry_policy.backoff_delays
        last_exception: Optional[Exception] = None
        
        for attempt in range(self._max_retries + 1):
            try:
                # Rate limit
                # We acquire rate limit for each attempt
                # Timeout on rate limit acquisition to prevent indefinite hanging
                if not await self._rate_limiter.acquire_async(timeout=60.0):
                    raise LLMRateLimitExceeded("gateway", 30)
                
                # Router
                complexity = self._router.infer_complexity(request.prompt)
                provider = self._router.select_model(complexity)
                
                # Execute with timeout
                response = await asyncio.wait_for(
                    provider.complete_async(request),
                    timeout=self._request_timeout,
                )
                
                # Reset circuit breaker on success
                model_name = getattr(provider, "model_name", None)
                if model_name:
                    self._record_success(model_name)
                    
                return response
                
            except LLMRateLimitExceeded as e:
                # Retry but don't record model failure (usually local limit or global bucket)
                last_exception = e
                # Task 10: Respect retry_after if provided, capped at 60s
                retry_after = getattr(e, "retry_after", None)
                if retry_after is not None and attempt < self._max_retries:
                    # Cap at 60s to prevent excessive waits
                    capped_delay = min(float(retry_after), 60.0)
                    log.warning(
                        "gateway_retry_rate_limit",
                        attempt=attempt + 1,
                        retry_after=retry_after,
                        capped_delay=capped_delay,
                    )
                    await asyncio.sleep(capped_delay)
                    with self._metrics_lock:
                        self._total_retries += 1
                    continue  # Skip the normal backoff logic below
            except asyncio.TimeoutError:
                last_exception = LLMTimeoutError(
                    provider="gateway",
                    timeout_seconds=self._request_timeout,
                )
            except (LLMProviderUnavailable, LLMTimeoutError) as e:
                # Record failure for CB
                # We need to access provider model name. 
                # Since provider was selected inside loop, we need to ensure we can access it.
                model_name = getattr(provider, "model_name", None)
                if model_name:
                    self._record_failure(model_name)
                    
                last_exception = e
            except Exception as e:
                # Non-retryable error
                raise
            
            # Apply backoff if retry remaining
            if attempt < self._max_retries:
                # Use exponential backoff capped at 4.0s
                # Or use the predefined list if retries <= 3
                if attempt < len(backoff_delays):
                    delay = backoff_delays[attempt]
                else:
                    delay = backoff_delays[-1] if backoff_delays else 1.0
                
                log.warning(
                    "gateway_retry",
                    attempt=attempt + 1,
                    max_retries=self._max_retries,
                    delay=delay,
                    error=str(last_exception),
                )
                
                await asyncio.sleep(delay)
                
                with self._metrics_lock:
                    self._total_retries += 1
        
        # All retries exhausted
        raise last_exception if last_exception else RuntimeError("Unknown error")

    def _record_failure(self, model_name: str) -> None:
        """Record a failure for a model and trigger CB if threshold reached."""
        with self._cb_lock:
            self._model_failures[model_name] = self._model_failures.get(model_name, 0) + 1
            
            # Check threshold from policy
            if self._model_failures[model_name] >= self._retry_policy.cb_failure_threshold:
                # Exclude for duration from policy
                exclusion_duration = self._retry_policy.cb_exclusion_duration
                self._model_excluded_until[model_name] = time.monotonic() + exclusion_duration
                
                log.warning(
                    "circuit_breaker_triggered",
                    model=model_name,
                    failures=self._model_failures[model_name],
                    duration=exclusion_duration,
                )
                
                # Reset failure count so it can recover after exclusion expires
                # Alternatively, keep it and require success to reset?
                # Simple implementation: reset failures only after success or explicit reset.
                # Actually, if we exclude, we should probably tell the router.
                # Since this is a simple implementation, we assume router checks gateway for exclusions 
                # OR we notify router. 
                # The Task 10 says "Update Router".
                # For now, let's assume we call refresh on router if available.
                try:
                    self._router.refresh_availability()
                except Exception:
                    pass # Router might not support this or mock might fail if not set up

    def _record_success(self, model_name: str) -> None:
        """Reset failure count for a model on success."""
        with self._cb_lock:
            if model_name in self._model_failures and self._model_failures[model_name] > 0:
                self._model_failures[model_name] = 0

    def is_excluded(self, model_name: str) -> bool:
        """Check if a model is currently excluded by circuit breaker.
        
        Args:
            model_name: The model identifier to check.
            
        Returns:
            True if model is excluded, False otherwise.
        """
        with self._cb_lock:
            excluded_until = self._model_excluded_until.get(model_name)
            if excluded_until is None:
                return False
            
            now = time.monotonic()
            if now >= excluded_until:
                # Exclusion expired - clean up
                del self._model_excluded_until[model_name]
                log.info("circuit_breaker_reset", model=model_name)
                return False
            
            return True

    @property
    def total_requests(self) -> int:
        """Total requests processed."""
        with self._metrics_lock:
            return self._total_requests
    
    @property
    def total_successes(self) -> int:
        """Successful completions."""
        with self._metrics_lock:
            return self._total_successes
    
    @property
    def total_failures(self) -> int:
        """Failed requests."""
        with self._metrics_lock:
            return self._total_failures
    
    @property
    def total_retries(self) -> int:
        """Total retry events."""
        with self._metrics_lock:
            return self._total_retries
    
    @property
    def avg_latency_ms(self) -> float:
        """Average request latency in milliseconds."""
        with self._metrics_lock:
            if self._total_successes == 0:
                return 0.0
            return self._total_latency_ms / self._total_successes
    
    @property
    def queue_depth(self) -> int:
        """Current queue depth."""
        return self._queue.total_queue_depth

    
    async def __aenter__(self) -> "LLMGateway":
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
