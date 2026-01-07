import threading
import time
import asyncio
from typing import Optional

import structlog

from cyberred.llm.provider import LLMProvider, LLMRequest, LLMResponse
from cyberred.core.exceptions import LLMRateLimitExceeded

log = structlog.get_logger()

class RateLimiter:
    """Token bucket rate limiter for LLM requests.
    
    Per architecture: 30 RPM global cap shared across swarm.
    """
    
    def __init__(self, rpm: int = 30, burst: int = 5) -> None:
        if rpm <= 0:
            raise ValueError("rpm must be positive")
        if burst < 1:
            raise ValueError("burst must be at least 1")
            
        self._rpm = rpm
        self._burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        
        self._lock = threading.Lock()
        self._async_condition = asyncio.Condition()
        self._waiting_count = 0

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        
        # Calculate tokens to add: (RPM / 60) * elapsed_seconds
        tokens_to_add = elapsed * (self._rpm / 60.0)
        
        if tokens_to_add > 0:
            self._tokens = min(float(self._burst), self._tokens + tokens_to_add)
            self._last_refill = now

    def acquire(self, timeout: float = None) -> bool:
        """Acquire a token, blocking until available or timeout."""
        start_time = time.monotonic()
        
        with self._lock:
            while True:
                self._refill()
                
                if self._tokens >= 1:
                    self._tokens -= 1
                    return True
                    
                if timeout is not None:
                    elapsed = time.monotonic() - start_time
                    remaining = timeout - elapsed
                    if remaining <= 0:
                        return False
                    
                    # Wait for next token availability
                    # RPM / 60 = tokens per second
                    # 1 token / (RPM/60) = seconds per token
                    time_per_token = 60.0 / self._rpm
                    sleep_time = min(remaining, time_per_token)
                    
                    # Release lock while sleeping
                    self._waiting_count += 1
                    self._lock.release()
                    try:
                        time.sleep(sleep_time)
                    finally:
                        self._lock.acquire()
                        self._waiting_count -= 1
                else:
                    # Blocking wait without timeout
                    time_per_token = 60.0 / self._rpm
                    self._waiting_count += 1
                    self._lock.release()
                    try:
                        time.sleep(time_per_token)
                    finally:
                        self._lock.acquire()
                        self._waiting_count -= 1

    async def acquire_async(self, timeout: float = None) -> bool:
        """Acquire a token asynchronously."""
        start_time = time.monotonic()
        
        async with self._async_condition:
            while True:
                self._refill()
                
                if self._tokens >= 1:
                    self._tokens -= 1
                    return True
                
                if timeout is not None:
                    elapsed = time.monotonic() - start_time
                    remaining = timeout - elapsed
                    if remaining <= 0:
                        return False
                    
                    # Wait for token availability
                    time_per_token = 60.0 / self._rpm
                    wait_time = min(remaining, time_per_token)
                    
                    self._waiting_count += 1
                    try:
                        # Use wait_for to handle timeout
                        await asyncio.wait_for(self._async_condition.wait(), timeout=wait_time)
                    except asyncio.TimeoutError:
                        # Timeout here just means we wake up to check again
                        pass
                    finally:
                        self._waiting_count -= 1
                else:
                    # Blocking wait without timeout
                    time_per_token = 60.0 / self._rpm
                    self._waiting_count += 1
                    try:
                        await asyncio.wait_for(self._async_condition.wait(), timeout=time_per_token)
                    except asyncio.TimeoutError:
                        pass
                    finally:
                        self._waiting_count -= 1

    @property
    def queue_depth(self) -> int:
        """Return the number of requests waiting for a token."""
        return self._waiting_count

    @property
    def available_tokens(self) -> float:
        """Return current token count (thread-safe)."""
        with self._lock:
            self._refill()
            return self._tokens

    @property
    def requests_per_minute(self) -> int:
        """Return configured RPM."""
        return self._rpm

    @property
    def burst_limit(self) -> int:
        """Return configured burst limit."""
        return self._burst

    def try_acquire(self) -> bool:
        """Attempt to acquire a token without blocking."""
        return self.acquire(timeout=0)

    def __enter__(self):
        """Context manager support."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        pass

    async def __aenter__(self):
        """Async context manager support."""
        await self.acquire_async()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        pass

class RateLimitedProvider:
    """Wrapper that applies rate limiting to any LLM provider."""
    
    def __init__(
        self, 
        provider: LLMProvider, 
        rate_limiter: "RateLimiter",
        acquire_timeout: float = 60.0
    ) -> None:
        self._provider = provider
        self._rate_limiter = rate_limiter
        self._acquire_timeout = acquire_timeout
    
    def complete(self, request: LLMRequest) -> LLMResponse:
        if not self._rate_limiter.acquire(timeout=self._acquire_timeout):
            raise LLMRateLimitExceeded("Rate limit acquire timeout")
        return self._provider.complete(request)

    async def complete_async(self, request: LLMRequest) -> LLMResponse:
        if not await self._rate_limiter.acquire_async(timeout=self._acquire_timeout):
            raise LLMRateLimitExceeded("Rate limit acquire timeout")
        return await self._provider.complete_async(request)