import asyncio
import threading
import time
import os
from typing import Optional, Dict

import structlog

from cyberred.llm.provider import LLMRequest, LLMResponse, TokenUsage
from cyberred.llm.rate_limiter import RateLimiter
from cyberred.llm.router import ModelRouter
from cyberred.llm.priority_queue import LLMPriorityQueue, RequestPriority
from cyberred.llm.retry import RetryPolicy
from cyberred.llm.env import resolve_llm_api_key

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
    fallback_models: Optional[Dict[str, str]] = None,
    num_workers: int = 25,
) -> "LLMGateway":
    """Initialize the singleton gateway instance."""
    global _gateway_instance
    with _gateway_lock:
        if _gateway_instance is not None:
            raise RuntimeError("Gateway already initialized")
        _gateway_instance = LLMGateway(
            rate_limiter, router, queue, retry_policy, fallback_models,
            num_workers=num_workers,
        )
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
        fallback_models: Optional[Dict[str, str]] = None,
        num_workers: int = 4,
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
        self._total_request_timeout = self._retry_policy.total_request_timeout
        self._max_retries = self._retry_policy.max_retries
        self._min_attempt_timeout = 5.0

        # Model fallback mapping: primary_model -> fallback_model
        self._fallback_models = fallback_models or {}

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

        reserve_hint = os.getenv("CYBERRED_LLM_DIRECTOR_RESERVED_WORKERS", "2")
        try:
            reserve_workers = int(reserve_hint)
        except ValueError:
            reserve_workers = 2
        reserve_workers = max(0, min(max(0, num_workers - 1), reserve_workers))
        self._director_reserved_workers = reserve_workers
        self._base_agent_inflight_cap = max(1, num_workers - reserve_workers)
        self._max_agent_inflight = self._base_agent_inflight_cap
        dynamic_reserve_hint = str(
            os.getenv("CYBERRED_LLM_DYNAMIC_DIRECTOR_RESERVE", "true")
        ).strip().lower()
        self._dynamic_director_reserve = dynamic_reserve_hint not in {
            "0", "false", "off", "no"
        }
        min_reserve_hint = os.getenv("CYBERRED_LLM_MIN_DIRECTOR_RESERVE", "0")
        try:
            min_reserve = int(min_reserve_hint)
        except ValueError:
            min_reserve = 0
        self._min_director_reserve = max(0, min(reserve_workers, min_reserve))
        cap_override_hint = os.getenv("CYBERRED_LLM_AGENT_INFLIGHT_CAP")
        cap_override: int | None = None
        if cap_override_hint:
            try:
                parsed = int(cap_override_hint)
                if parsed > 0:
                    cap_override = parsed
            except ValueError:
                cap_override = None
        self._agent_inflight_cap_override = cap_override
        self._agent_inflight = 0

        self._running = False
        self._num_workers = num_workers
        self._worker_tasks: list[asyncio.Task] = []

        log.info(
            "gateway_initialized",
            num_workers=num_workers,
            director_reserved_workers=self._director_reserved_workers,
            agent_max_inflight=self._base_agent_inflight_cap,
            dynamic_director_reserve=self._dynamic_director_reserve,
            min_director_reserve=self._min_director_reserve,
            agent_inflight_cap_override=self._agent_inflight_cap_override,
        )
    
    async def director_complete(self, request: LLMRequest) -> LLMResponse:
        """Submit a Director request with highest priority.
        
        Director requests are processed before agent requests.
        """
        normalized_request = self._with_deadline(request)
        future = await self._queue.enqueue_director(normalized_request)
        return await future
    
    async def agent_complete(self, request: LLMRequest) -> LLMResponse:
        """Submit an Agent request with normal priority."""
        normalized_request = self._with_deadline(request)
        future = await self._queue.enqueue_agent(normalized_request)
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
        """Start the background request processing workers."""
        if self._running:
            log.warning("gateway_already_running")
            return

        self._running = True
        self._worker_tasks = [
            asyncio.create_task(self._process_requests())
            for _ in range(self._num_workers)
        ]
        log.info("gateway_started", num_workers=self._num_workers)

    async def stop(self) -> None:
        """Stop the gateway and cleanup."""
        self._running = False

        for task in self._worker_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._worker_tasks = []

        log.info("gateway_stopped")
    
    async def _process_requests(self) -> None:
        """Background worker that processes queued requests."""
        while self._running:
            try:
                # Dequeue with timeout to allow shutdown check
                priority_request = await self._queue.dequeue(timeout=1.0)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Timeout or other error - continue loop
                continue

            reserved_agent_slot = False
            if priority_request.priority == RequestPriority.AGENT:
                if not self._try_reserve_agent_slot():
                    await self._queue.requeue(priority_request)
                    await asyncio.sleep(0.05)
                    continue
                reserved_agent_slot = True

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
            except asyncio.CancelledError:
                if not priority_request.future.done():
                    priority_request.future.cancel()
                raise
                
            except Exception as e:
                # Graceful handling: Return error response instead of causing caller exception
                # Task 9: Structured error fields for monitoring
                error_type = "transient" if isinstance(
                    e, (LLMTimeoutError, LLMRateLimitExceeded, LLMProviderUnavailable)
                ) else "permanent"
                
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
            finally:
                if reserved_agent_slot:
                    self._release_agent_slot()

    def _try_reserve_agent_slot(self) -> bool:
        """Try to reserve one in-flight slot for an agent request."""
        with self._metrics_lock:
            limit = self._current_agent_inflight_limit_locked()
            if self._agent_inflight >= limit:
                return False
            self._agent_inflight += 1
            return True

    def _release_agent_slot(self) -> None:
        """Release an in-flight slot for an agent request."""
        with self._metrics_lock:
            if self._agent_inflight > 0:
                self._agent_inflight -= 1

    def _current_agent_inflight_limit_locked(self) -> int:
        """Resolve effective in-flight cap while metrics lock is held."""
        if self._agent_inflight_cap_override is not None:
            return max(1, min(self._num_workers, self._agent_inflight_cap_override))

        configured_cap = max(1, int(self._max_agent_inflight))
        if not self._dynamic_director_reserve:
            return configured_cap
        if self._director_reserved_workers <= self._min_director_reserve:
            return configured_cap
        if configured_cap != self._base_agent_inflight_cap:
            return configured_cap

        director_depth = self._safe_queue_depth(
            getattr(self._queue, "director_queue_depth", 0)
        )
        if director_depth > 0:
            return configured_cap

        reclaim = max(0, self._director_reserved_workers - self._min_director_reserve)
        return max(1, min(self._num_workers, configured_cap + reclaim))

    @staticmethod
    def _safe_queue_depth(raw_value: object) -> int:
        """Parse queue depth value safely."""
        if isinstance(raw_value, bool):
            return int(raw_value)
        if isinstance(raw_value, (int, float)):
            return max(0, int(raw_value))
        if isinstance(raw_value, str):
            try:
                return max(0, int(raw_value))
            except ValueError:
                return 0
        return 0
    
    async def _execute_with_retry(self, request: LLMRequest) -> LLMResponse:
        """Execute request with retry, exponential backoff, and model fallback.

        Per ERR2: 3x retry with exponential backoff (1s, 2s, 4s).
        If all retries fail with 429, try the fallback model (if configured).

        If request.model is explicitly set, creates a provider for that specific
        model (used by Director Ensemble). Otherwise, routes via complexity tier.
        """
        deadline_monotonic_s = self._resolve_deadline_monotonic(request)

        response, last_exception = await self._try_model_with_retries(
            request,
            deadline_monotonic_s=deadline_monotonic_s,
        )
        if response is not None:
            return response

        # Primary model exhausted — try fallback if available and error was rate limit
        if request.model and request.model in self._fallback_models:
            fallback = self._fallback_models[request.model]
            log.warning(
                "gateway_model_fallback",
                primary=request.model,
                fallback=fallback,
            )
            fallback_request = LLMRequest(
                prompt=request.prompt,
                system_prompt=request.system_prompt,
                model=fallback,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
                frequency_penalty=request.frequency_penalty,
                stop_sequences=request.stop_sequences,
                timeout_budget_s=request.timeout_budget_s,
                deadline_monotonic_s=deadline_monotonic_s,
            )
            response, fallback_exception = await self._try_model_with_retries(
                fallback_request,
                deadline_monotonic_s=deadline_monotonic_s,
            )
            if fallback_exception is not None:
                last_exception = fallback_exception
            if response is not None:
                return response

        raise last_exception if last_exception else RuntimeError("Unknown error")

    async def _try_model_with_retries(
        self,
        request: LLMRequest,
        *,
        deadline_monotonic_s: float,
    ) -> tuple[Optional[LLMResponse], Optional[Exception]]:
        """Try a model with retries under a fixed end-to-end deadline."""
        backoff_delays = self._retry_policy.backoff_delays
        last_exception: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            remaining_budget_s = deadline_monotonic_s - time.monotonic()
            if remaining_budget_s <= 0:
                timeout_window = request.timeout_budget_s or self._total_request_timeout
                last_exception = LLMTimeoutError(
                    provider="gateway",
                    timeout_seconds=timeout_window,
                    message=(
                        "LLM request deadline exceeded before execution "
                        f"(attempt={attempt + 1})."
                    ),
                )
                break

            provider = None
            attempt_timeout_s = self._estimate_attempt_timeout(request, remaining_budget_s)
            try:
                # Rate limit — acquire token for each attempt
                rate_limit_timeout = max(0.05, min(60.0, remaining_budget_s))
                if not await self._rate_limiter.acquire_async(timeout=rate_limit_timeout):
                    raise LLMRateLimitExceeded("gateway", 30)

                # Check if explicit model requested (e.g., Director Ensemble)
                if request.model and request.model not in ("auto", "default"):
                    from cyberred.llm.nim import NIMProvider
                    api_key = resolve_llm_api_key()
                    if not api_key:
                        raise LLMProviderUnavailable(
                            provider="NIM",
                            message="LLM API key missing for explicit model request",
                        )
                    provider = NIMProvider(api_key=api_key, model=request.model)
                else:
                    complexity = self._router.infer_complexity(request.prompt)
                    provider = self._router.select_model(complexity)

                # Recompute timeout after potential queue/rate-limit wait.
                remaining_budget_s = deadline_monotonic_s - time.monotonic()
                if remaining_budget_s <= 0:
                    raise LLMTimeoutError(
                        provider="gateway",
                        timeout_seconds=request.timeout_budget_s or self._total_request_timeout,
                        message=(
                            "LLM request deadline exceeded after rate-limit wait "
                            f"(attempt={attempt + 1})."
                        ),
                    )
                attempt_timeout_s = self._estimate_attempt_timeout(request, remaining_budget_s)
                request.provider_timeout_s = attempt_timeout_s

                # Execute with deadline-aligned timeout.
                response = await asyncio.wait_for(
                    provider.complete_async(request),
                    timeout=attempt_timeout_s,
                )

                # Reset circuit breaker on success
                model_name = getattr(provider, "model_name", None)
                if model_name:
                    self._record_success(model_name)

                return response, None

            except LLMRateLimitExceeded as e:
                last_exception = e
                retry_after = getattr(e, "retry_after", None)
                if retry_after is not None and attempt < self._max_retries:
                    min_next_attempt_s = self._minimum_retry_window(request)
                    capped_delay = min(
                        float(retry_after),
                        60.0,
                        max(0.0, remaining_budget_s - min_next_attempt_s),
                    )
                    log.warning(
                        "gateway_retry_rate_limit",
                        attempt=attempt + 1,
                        retry_after=retry_after,
                        capped_delay=capped_delay,
                        remaining_budget_s=remaining_budget_s,
                        model=request.model,
                    )
                    if capped_delay <= 0:
                        break
                    await asyncio.sleep(capped_delay)
                    with self._metrics_lock:
                        self._total_retries += 1
                    continue
            except asyncio.TimeoutError:
                model_name = getattr(provider, "model_name", None)
                if model_name:
                    self._record_failure(model_name)
                timeout_provider = model_name or (
                    request.model
                    if request.model and request.model not in ("auto", "default")
                    else "gateway"
                )
                timeout_window = max(0.05, min(attempt_timeout_s, remaining_budget_s))
                last_exception = LLMTimeoutError(
                    provider=timeout_provider,
                    timeout_seconds=timeout_window,
                )
            except (LLMProviderUnavailable, LLMTimeoutError) as e:
                model_name = getattr(provider, "model_name", None) or (
                    request.model
                    if request.model and request.model not in ("auto", "default")
                    else None
                )
                if model_name:
                    self._record_failure(model_name)
                last_exception = e
            except Exception:
                raise

            # Apply backoff if retry remaining
            if attempt < self._max_retries:
                if attempt < len(backoff_delays):
                    delay = backoff_delays[attempt]
                else:
                    delay = backoff_delays[-1] if backoff_delays else 1.0
                remaining_for_backoff = deadline_monotonic_s - time.monotonic()
                min_next_attempt_s = self._minimum_retry_window(request)
                if remaining_for_backoff <= min_next_attempt_s:
                    break
                delay = min(delay, max(0.0, remaining_for_backoff - min_next_attempt_s))

                log.warning(
                    "gateway_retry",
                    attempt=attempt + 1,
                    max_retries=self._max_retries,
                    delay=delay,
                    remaining_budget_s=remaining_for_backoff,
                    error=str(last_exception),
                    model=request.model,
                )
                if delay <= 0:
                    break

                await asyncio.sleep(delay)

                with self._metrics_lock:
                    self._total_retries += 1

        # All retries exhausted for this model
        return None, last_exception

    def _estimate_attempt_timeout(self, request: LLMRequest, remaining_budget_s: float) -> float:
        """Resolve a per-attempt timeout aligned to the request deadline.

        The gateway enforces a hard end-to-end deadline. This helper only decides
        the per-attempt provider timeout (HTTP/network) and must not exceed the
        remaining deadline budget.
        """
        base_timeout = request.provider_timeout_s or self._request_timeout
        if request.timeout_budget_s is not None:
            try:
                base_timeout = min(float(base_timeout), float(request.timeout_budget_s))
            except (TypeError, ValueError):
                base_timeout = base_timeout
        try:
            base_timeout_s = float(base_timeout)
        except (TypeError, ValueError):
            base_timeout_s = float(self._request_timeout)
        if base_timeout_s <= 0:
            base_timeout_s = float(self._request_timeout)
        return max(0.05, min(base_timeout_s, remaining_budget_s))

    def _minimum_retry_window(self, request: LLMRequest) -> float:
        """Minimum budget needed to justify another retry attempt."""
        token_floor = 5.0 + (max(1, request.max_tokens) / 250.0)
        return max(self._min_attempt_timeout, min(45.0, token_floor))

    def _with_deadline(self, request: LLMRequest) -> LLMRequest:
        """Return a request carrying a concrete monotonic deadline."""
        if request.deadline_monotonic_s is not None:
            return request

        budget_s = request.timeout_budget_s or self._total_request_timeout
        request.timeout_budget_s = budget_s
        request.deadline_monotonic_s = time.monotonic() + budget_s
        return request

    def _resolve_deadline_monotonic(self, request: LLMRequest) -> float:
        """Resolve request deadline, defaulting to gateway timeout budget."""
        if request.deadline_monotonic_s is not None:
            return request.deadline_monotonic_s
        budget_s = request.timeout_budget_s or self._total_request_timeout
        return time.monotonic() + budget_s

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

    @property
    def director_queue_depth(self) -> int:
        """Current Director queue depth."""
        return self._queue.director_queue_depth

    @property
    def agent_queue_depth(self) -> int:
        """Current Agent queue depth."""
        return self._queue.agent_queue_depth

    @property
    def agent_inflight(self) -> int:
        """Current number of in-flight agent requests."""
        with self._metrics_lock:
            return self._agent_inflight

    @property
    def max_agent_inflight(self) -> int:
        """Configured in-flight agent request ceiling."""
        with self._metrics_lock:
            return self._current_agent_inflight_limit_locked()

    
    async def __aenter__(self) -> "LLMGateway":
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
