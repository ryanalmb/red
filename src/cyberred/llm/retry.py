"""Retry logic and configuration for LLM requests."""

from dataclasses import dataclass
from typing import Tuple

@dataclass
class RetryPolicy:
    """Configuration for retry behavior and circuit breaker.
    
    Per ERR2: 3x retry with exponential backoff.
    """
    max_retries: int = 3
    backoff_delays: Tuple[float, ...] = (1.0, 2.0, 4.0)
    request_timeout: float = 100.0
    cb_failure_threshold: int = 3
    cb_exclusion_duration: float = 60.0
    
    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be > 0")
        if self.cb_failure_threshold < 1:
            raise ValueError("cb_failure_threshold must be >= 1")
        if self.cb_exclusion_duration <= 0:
            raise ValueError("cb_exclusion_duration must be > 0")
