"""NVIDIA NIM LLM provider implementation."""

import threading
import time
from typing import Any, Dict, List, Optional

import httpx
import structlog

from cyberred.llm.provider import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    TokenUsage,
    HealthStatus,
)
from cyberred.core.exceptions import (
    LLMProviderUnavailable,
    LLMRateLimitExceeded,
    LLMTimeoutError,
    LLMResponseError,
)

log = structlog.get_logger()


class NIMProvider(LLMProvider):
    """NVIDIA NIM LLM provider implementation.
    
    Connects to NVIDIA NIM hosted models via standard OpenAI-compatible API.
    Enforces architecture constraints:
    - 30 RPM global rate limit (reported, not enforced locally)
    - Circuit breaker pattern (3 failures = unavailable)
    - Tiered model selection
    """

    DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
    DEFAULT_MODEL = "mistralai/devstral-2-123b-instruct-2512"  # FAST tier - validated available
    DEFAULT_TIMEOUT = 60.0
    
    # Model tiers per architecture
    MODELS = {
        "FAST": "mistralai/devstral-2-123b-instruct-2512",
        "STANDARD": "moonshotai/kimi-k2-instruct-0905",
        "COMPLEX": "minimaxai/minimax-m2.1",
    }

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        """Initialize NIM provider.
        
        Args:
            api_key: NVIDIA API key.
            model: Model identifier.
            base_url: Base API URL.
            
        Raises:
            ValueError: If api_key is empty.
        """
        if not api_key:
            raise ValueError("api_key cannot be empty")
            
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        
        # State tracking
        self._lock = threading.Lock()
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._consecutive_failures = 0
        self._is_healthy = True

    @classmethod
    def for_tier(cls, tier: str, api_key: str) -> "NIMProvider":
        """Factory method to create provider for a specific tier.
        
        Args:
            tier: One of FAST, STANDARD, COMPLEX.
            api_key: NVIDIA API key.
            
        Returns:
            Configured NIMProvider instance.
        """
        model = cls.MODELS.get(tier.upper(), cls.DEFAULT_MODEL)
        return cls(api_key=api_key, model=model)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Generate completion synchronously."""
        if not self.is_available():
            raise LLMProviderUnavailable(
                provider="NIM", 
                message="Provider unavailable due to consecutive failures"
            )
            
        start_time = time.monotonic()
        payload = self._build_request_payload(request)
        headers = self._get_headers()
        
        try:
            with httpx.Client(timeout=self.DEFAULT_TIMEOUT) as client:
                response = client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers
                )
                self._handle_response_error(response)
                result = self._parse_response(response, start_time)
                self._record_success(result.usage)
                return result
                
        except (httpx.TimeoutException, LLMTimeoutError):
            self._record_failure()
            raise LLMTimeoutError(
                provider="NIM",
                timeout_seconds=self.DEFAULT_TIMEOUT
            )
        except (httpx.ConnectError, httpx.NetworkError):
            self._record_failure()
            raise LLMProviderUnavailable(provider="NIM", message="Connection failed")
        except Exception as e:
            if not isinstance(e, (LLMProviderUnavailable, LLMRateLimitExceeded, LLMResponseError)):
                self._record_failure()
                log.error("nim_provider_error", error=str(e))
                raise LLMProviderUnavailable(provider="NIM", message=f"Unexpected error: {str(e)}")
            raise

    async def complete_async(self, request: LLMRequest) -> LLMResponse:
        """Generate completion asynchronously."""
        if not self.is_available():
            raise LLMProviderUnavailable(
                provider="NIM", 
                message="Provider unavailable due to consecutive failures"
            )
            
        start_time = time.monotonic()
        payload = self._build_request_payload(request)
        headers = self._get_headers()
        
        try:
            async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers
                )
                self._handle_response_error(response)
                result = self._parse_response(response, start_time)
                self._record_success(result.usage)
                return result
                
        except (httpx.TimeoutException, LLMTimeoutError):
            self._record_failure()
            raise LLMTimeoutError(
                provider="NIM",
                timeout_seconds=self.DEFAULT_TIMEOUT
            )
        except (httpx.ConnectError, httpx.NetworkError):
            self._record_failure()
            raise LLMProviderUnavailable(provider="NIM", message="Connection failed")
        except Exception as e:
            if not isinstance(e, (LLMProviderUnavailable, LLMRateLimitExceeded, LLMResponseError)):
                self._record_failure()
                log.error("nim_provider_error", error=str(e))
                raise LLMProviderUnavailable(provider="NIM", message=f"Unexpected error: {str(e)}")
            raise

    async def health_check(self) -> HealthStatus:
        """Check provider health via minimal API call."""
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    json={
                        "model": self._model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1
                    },
                    headers=self._get_headers()
                )
                response.raise_for_status()
                latency = int((time.monotonic() - start) * 1000)
                return HealthStatus(healthy=True, latency_ms=latency)
        except Exception as e:
            return HealthStatus(healthy=False, error=str(e))

    def is_available(self) -> bool:
        """Check if provider is available (circuit breaker)."""
        with self._lock:
            return self._consecutive_failures < 3

    def get_model_name(self) -> str:
        """Return configured model."""
        return self._model

    def get_rate_limit(self) -> int:
        """Return 30 RPM per architecture."""
        return 30

    def get_token_usage(self) -> Dict[str, int]:
        """Return accumulated token usage."""
        with self._lock:
            return {
                "prompt_tokens": self._total_prompt_tokens,
                "completion_tokens": self._total_completion_tokens,
                "total_tokens": self._total_prompt_tokens + self._total_completion_tokens
            }

    # Private helpers

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _build_request_payload(self, request: LLMRequest) -> Dict[str, Any]:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
        }
        
        if request.stop_sequences:
            payload["stop"] = request.stop_sequences
            
        return payload

    def _handle_response_error(self, response: httpx.Response) -> None:
        """Handle HTTP error responses."""
        if response.is_success:
            return
            
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            raise LLMRateLimitExceeded(
                provider="NIM",
                limit=30,
                retry_after=retry_after
            )
            
        if response.status_code == 401:
            log.error("nim_auth_error", status=401)
            raise LLMProviderUnavailable(provider="NIM", message="Invalid API Key")
            
        if response.status_code >= 500:
            raise LLMProviderUnavailable(
                provider="NIM", 
                message=f"Server error: {response.status_code}"
            )
            
        # Other errors
        try:
            error_msg = response.json().get("error", {}).get("message", response.text)
        except Exception:
            error_msg = response.text
            
        raise LLMProviderUnavailable(provider="NIM", message=f"API Error: {error_msg}")

    def _parse_response(self, response: httpx.Response, start_time: float) -> LLMResponse:
        """Parse successful API response."""
        try:
            data = response.json()
            
            if "choices" not in data or not data["choices"]:
                raise LLMResponseError(provider="NIM", reason="Missing 'choices' field")
                
            choice = data["choices"][0]
            # Ensure choice is a dict before accessing
            if not isinstance(choice, dict):
                raise LLMResponseError(provider="NIM", reason="Invalid choice format: expected dict")
            message = choice.get("message", {})
            if not isinstance(message, dict):
                raise ValueError("Message field must be a dictionary")
                
            content = message.get("content", "")
            finish_reason = choice.get("finish_reason")
            
            usage_data = data.get("usage", {})
            usage = TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0)
            )
            
            latency = int((time.monotonic() - start_time) * 1000)
            # NVIDIA NIM sometimes uses different header names for request ID
            request_id = response.headers.get("x-inv-request-id") or \
                         response.headers.get("nv-request-id") or \
                         data.get("id")
            
            return LLMResponse(
                content=content,
                model=data.get("model", self._model),
                usage=usage,
                latency_ms=latency,
                finish_reason=finish_reason,
                request_id=request_id
            )
            
        except (ValueError, KeyError) as e:
            raise LLMResponseError(provider="NIM", reason=f"Malformed response: {str(e)}")

    def _record_success(self, usage: TokenUsage) -> None:
        """Update stats on success."""
        with self._lock:
            self._consecutive_failures = 0
            self._total_prompt_tokens += usage.prompt_tokens
            self._total_completion_tokens += usage.completion_tokens

    def _record_failure(self) -> None:
        """Update stats on failure."""
        with self._lock:
            self._consecutive_failures += 1