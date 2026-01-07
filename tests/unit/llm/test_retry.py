"""Unit tests for RetryPolicy."""

import pytest
from cyberred.llm.retry import RetryPolicy

def test_retry_policy_creation():
    """Test RetryPolicy dataclass creation and validation."""
    # Default values
    policy = RetryPolicy()
    assert policy.max_retries == 3
    assert policy.backoff_delays == (1.0, 2.0, 4.0)
    assert policy.request_timeout == 100.0
    assert policy.cb_failure_threshold == 3
    assert policy.cb_exclusion_duration == 60.0
    
    # Validation - max_retries
    with pytest.raises(ValueError, match="max_retries must be >= 0"):
        RetryPolicy(max_retries=-1)
        
    # Validation - request_timeout
    with pytest.raises(ValueError, match="request_timeout must be > 0"):
        RetryPolicy(request_timeout=0)
        
    # Validation - cb_failure_threshold
    with pytest.raises(ValueError, match="cb_failure_threshold must be >= 1"):
        RetryPolicy(cb_failure_threshold=0)
        
    # Validation - cb_exclusion_duration
    with pytest.raises(ValueError, match="cb_exclusion_duration must be > 0"):
        RetryPolicy(cb_exclusion_duration=0)
