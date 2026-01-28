"""Unit tests for Partial Model Availability Fallback (Story 8.6).

Tests cover:
- CircuitBreaker class with failure tracking
- CircuitBreakerState dataclass
- ModelAvailabilityStatus dataclass
- AvailabilityState enum
- DegradationLevel enum
- DegradationWarning dataclass
- Extended SynthesizedStrategy with degradation fields
- Degraded synthesis modes (pair, single, zero)
- Confidence score reduction
- Circuit breaker integration with query_all()
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.llm.ensemble import (
    DirectorRole,
    DirectorContext,
    DirectorEnsemble,
    ModelResponse,
    DirectorQueryResult,
    SynthesisInput,
    SynthesizedStrategy,
)
from cyberred.llm.provider import LLMResponse, TokenUsage
from cyberred.core.exceptions import LLMTimeoutError, LLMProviderUnavailable


class TestCircuitBreakerState:
    """Tests for CircuitBreakerState dataclass."""

    def test_default_state(self) -> None:
        """Test default state values."""
        from cyberred.llm.ensemble import CircuitBreakerState
        
        state = CircuitBreakerState()
        assert state.failure_count == 0
        assert state.last_failure_time == 0.0
        assert state.excluded_until == 0.0
    
    def test_is_excluded_when_not_excluded(self) -> None:
        """Test is_excluded returns False when not excluded."""
        from cyberred.llm.ensemble import CircuitBreakerState
        
        state = CircuitBreakerState()
        assert state.is_excluded() is False
    
    def test_is_excluded_when_excluded(self) -> None:
        """Test is_excluded returns True when excluded."""
        from cyberred.llm.ensemble import CircuitBreakerState
        
        state = CircuitBreakerState(excluded_until=time.monotonic() + 60.0)
        assert state.is_excluded() is True
    
    def test_is_excluded_after_period_expires(self) -> None:
        """Test is_excluded returns False after exclusion period."""
        from cyberred.llm.ensemble import CircuitBreakerState
        
        state = CircuitBreakerState(excluded_until=time.monotonic() - 1.0)
        assert state.is_excluded() is False


class TestAvailabilityState:
    """Tests for AvailabilityState enum."""

    def test_availability_states_exist(self) -> None:
        """Test all expected availability states exist."""
        from cyberred.llm.ensemble import AvailabilityState
        
        assert AvailabilityState.AVAILABLE.value == "available"
        assert AvailabilityState.EXCLUDED.value == "excluded"
        assert AvailabilityState.FAILED.value == "failed"
        assert AvailabilityState.UNKNOWN.value == "unknown"

    def test_availability_state_count(self) -> None:
        """Test that exactly four states exist."""
        from cyberred.llm.ensemble import AvailabilityState
        
        assert len(AvailabilityState) == 4


class TestModelAvailabilityStatus:
    """Tests for ModelAvailabilityStatus dataclass."""

    def test_create_status(self) -> None:
        """Test creating ModelAvailabilityStatus."""
        from cyberred.llm.ensemble import ModelAvailabilityStatus, AvailabilityState
        
        status = ModelAvailabilityStatus(
            role=DirectorRole.STRATEGIST,
            state=AvailabilityState.AVAILABLE,
        )
        assert status.role == DirectorRole.STRATEGIST
        assert status.state == AvailabilityState.AVAILABLE
        assert status.failure_count == 0
        assert status.excluded_until is None
        assert status.last_error is None

    def test_create_excluded_status(self) -> None:
        """Test creating excluded status with details."""
        from cyberred.llm.ensemble import ModelAvailabilityStatus, AvailabilityState
        
        excluded_time = time.monotonic() + 60.0
        status = ModelAvailabilityStatus(
            role=DirectorRole.ANALYST,
            state=AvailabilityState.EXCLUDED,
            failure_count=3,
            excluded_until=excluded_time,
            last_error="Timeout after 100s",
        )
        assert status.state == AvailabilityState.EXCLUDED
        assert status.failure_count == 3
        assert status.excluded_until == excluded_time
        assert status.last_error == "Timeout after 100s"


class TestDegradationLevel:
    """Tests for DegradationLevel enum."""

    def test_degradation_levels_exist(self) -> None:
        """Test all expected degradation levels exist."""
        from cyberred.llm.ensemble import DegradationLevel
        
        assert DegradationLevel.FULL.value == "full"
        assert DegradationLevel.DEGRADED_PAIR.value == "degraded_pair"
        assert DegradationLevel.DEGRADED_SINGLE.value == "degraded_single"
        assert DegradationLevel.UNAVAILABLE.value == "unavailable"

    def test_degradation_level_count(self) -> None:
        """Test that exactly four levels exist."""
        from cyberred.llm.ensemble import DegradationLevel
        
        assert len(DegradationLevel) == 4


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_init_defaults(self) -> None:
        """Test CircuitBreaker initialization with defaults."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        cb = CircuitBreaker()
        assert cb._failure_threshold == 3
        assert cb._exclusion_seconds == 60.0

    def test_init_custom_values(self) -> None:
        """Test CircuitBreaker initialization with custom values."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=5, exclusion_seconds=120.0)
        assert cb._failure_threshold == 5
        assert cb._exclusion_seconds == 120.0

    def test_all_roles_initially_available(self) -> None:
        """Test all roles are available initially."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        cb = CircuitBreaker()
        for role in DirectorRole:
            assert cb.is_available(role) is True

    def test_record_single_failure(self) -> None:
        """Test recording a single failure doesn't exclude model."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        cb = CircuitBreaker()
        excluded = cb.record_failure(DirectorRole.STRATEGIST)
        
        assert excluded is False
        assert cb.is_available(DirectorRole.STRATEGIST) is True

    def test_record_two_failures(self) -> None:
        """Test recording two failures doesn't exclude model."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        cb = CircuitBreaker()
        cb.record_failure(DirectorRole.STRATEGIST)
        excluded = cb.record_failure(DirectorRole.STRATEGIST)
        
        assert excluded is False
        assert cb.is_available(DirectorRole.STRATEGIST) is True

    def test_record_three_failures_excludes(self) -> None:
        """Test recording three failures excludes model."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        cb = CircuitBreaker()
        cb.record_failure(DirectorRole.STRATEGIST)
        cb.record_failure(DirectorRole.STRATEGIST)
        excluded = cb.record_failure(DirectorRole.STRATEGIST)
        
        assert excluded is True
        assert cb.is_available(DirectorRole.STRATEGIST) is False

    def test_exclusion_period_expires(self) -> None:
        """Test model becomes available after exclusion period."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        cb = CircuitBreaker(exclusion_seconds=0.01)  # 10ms
        cb.record_failure(DirectorRole.ANALYST)
        cb.record_failure(DirectorRole.ANALYST)
        cb.record_failure(DirectorRole.ANALYST)
        
        assert cb.is_available(DirectorRole.ANALYST) is False
        
        time.sleep(0.02)  # Wait for exclusion to expire
        
        assert cb.is_available(DirectorRole.ANALYST) is True

    def test_record_success_resets_failures(self) -> None:
        """Test recording success resets failure count."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        cb = CircuitBreaker()
        cb.record_failure(DirectorRole.CREATIVE)
        cb.record_failure(DirectorRole.CREATIVE)
        
        cb.record_success(DirectorRole.CREATIVE)
        
        # After success, should need 3 new failures to exclude
        cb.record_failure(DirectorRole.CREATIVE)
        cb.record_failure(DirectorRole.CREATIVE)
        assert cb.is_available(DirectorRole.CREATIVE) is True

    def test_record_success_on_fresh_model(self) -> None:
        """Test recording success on model with zero failures (no-op)."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        cb = CircuitBreaker()
        
        # Should not raise and state should remain unchanged
        cb.record_success(DirectorRole.STRATEGIST)
        
        assert cb._states[DirectorRole.STRATEGIST].failure_count == 0
        assert cb._states[DirectorRole.STRATEGIST].excluded_until == 0.0
        assert cb.is_available(DirectorRole.STRATEGIST) is True

    def test_get_available_roles_all_available(self) -> None:
        """Test get_available_roles returns all roles initially."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        cb = CircuitBreaker()
        available = cb.get_available_roles()
        
        assert len(available) == 3
        assert set(available) == set(DirectorRole)

    def test_get_available_roles_one_excluded(self) -> None:
        """Test get_available_roles excludes failed models."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        cb = CircuitBreaker()
        for _ in range(3):
            cb.record_failure(DirectorRole.ANALYST)
        
        available = cb.get_available_roles()
        
        assert len(available) == 2
        assert DirectorRole.ANALYST not in available

    def test_reset_clears_state(self) -> None:
        """Test reset clears circuit breaker state."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        cb = CircuitBreaker()
        for _ in range(3):
            cb.record_failure(DirectorRole.STRATEGIST)
        
        assert cb.is_available(DirectorRole.STRATEGIST) is False
        
        cb.reset(DirectorRole.STRATEGIST)
        
        assert cb.is_available(DirectorRole.STRATEGIST) is True

    def test_failures_isolated_per_role(self) -> None:
        """Test failures are tracked separately per role."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        cb = CircuitBreaker()
        cb.record_failure(DirectorRole.STRATEGIST)
        cb.record_failure(DirectorRole.STRATEGIST)
        cb.record_failure(DirectorRole.ANALYST)
        
        # Both should still be available
        assert cb.is_available(DirectorRole.STRATEGIST) is True
        assert cb.is_available(DirectorRole.ANALYST) is True

    def test_init_validates_failure_threshold(self) -> None:
        """Test that failure_threshold must be >= 1."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        with pytest.raises(ValueError, match="failure_threshold must be >= 1"):
            CircuitBreaker(failure_threshold=0)
        
        with pytest.raises(ValueError, match="failure_threshold must be >= 1"):
            CircuitBreaker(failure_threshold=-1)
    
    def test_init_validates_exclusion_seconds(self) -> None:
        """Test that exclusion_seconds must be > 0."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        with pytest.raises(ValueError, match="exclusion_seconds must be > 0"):
            CircuitBreaker(exclusion_seconds=0)
        
        with pytest.raises(ValueError, match="exclusion_seconds must be > 0"):
            CircuitBreaker(exclusion_seconds=-1.0)

    def test_record_failure_while_excluded_does_not_increment(self) -> None:
        """Test that failures while already excluded don't increment count."""
        from cyberred.llm.ensemble import CircuitBreaker
        
        cb = CircuitBreaker(failure_threshold=3, exclusion_seconds=60.0)
        
        # Trigger exclusion
        for _ in range(3):
            cb.record_failure(DirectorRole.STRATEGIST)
        
        initial_count = cb._states[DirectorRole.STRATEGIST].failure_count
        assert initial_count == 3
        
        # Additional failures while excluded should not increment
        result = cb.record_failure(DirectorRole.STRATEGIST)
        assert result is False  # Not newly excluded
        assert cb._states[DirectorRole.STRATEGIST].failure_count == 3  # Unchanged

    def test_get_status_available(self) -> None:
        """Test get_status returns AVAILABLE for fresh model."""
        from cyberred.llm.ensemble import CircuitBreaker, AvailabilityState
        
        cb = CircuitBreaker()
        status = cb.get_status(DirectorRole.STRATEGIST)
        
        assert status.role == DirectorRole.STRATEGIST
        assert status.state == AvailabilityState.AVAILABLE
        assert status.failure_count == 0
        assert status.excluded_until is None

    def test_get_status_failed(self) -> None:
        """Test get_status returns FAILED after failure but not excluded."""
        from cyberred.llm.ensemble import CircuitBreaker, AvailabilityState
        
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure(DirectorRole.ANALYST)
        
        status = cb.get_status(DirectorRole.ANALYST)
        
        assert status.state == AvailabilityState.FAILED
        assert status.failure_count == 1
        assert status.excluded_until is None

    def test_get_status_excluded(self) -> None:
        """Test get_status returns EXCLUDED after reaching threshold."""
        from cyberred.llm.ensemble import CircuitBreaker, AvailabilityState
        
        cb = CircuitBreaker(failure_threshold=3, exclusion_seconds=60.0)
        for _ in range(3):
            cb.record_failure(DirectorRole.CREATIVE)
        
        status = cb.get_status(DirectorRole.CREATIVE)
        
        assert status.state == AvailabilityState.EXCLUDED
        assert status.failure_count == 3
        assert status.excluded_until is not None
        assert status.excluded_until > 0


class TestDegradationWarning:
    """Tests for DegradationWarning dataclass."""

    def test_create_warning(self) -> None:
        """Test creating DegradationWarning."""
        from cyberred.llm.ensemble import DegradationWarning, DegradationLevel
        
        warning = DegradationWarning(
            level=DegradationLevel.DEGRADED_PAIR,
            available_models=[DirectorRole.STRATEGIST, DirectorRole.CREATIVE],
            excluded_models=[DirectorRole.ANALYST],
            message="Operating with 2 of 3 models",
        )
        assert warning.level == DegradationLevel.DEGRADED_PAIR
        assert len(warning.available_models) == 2
        assert len(warning.excluded_models) == 1
        assert warning.timestamp > 0

    def test_warning_timestamp_uses_monotonic(self) -> None:
        """Test that timestamp uses monotonic clock (not affected by system clock)."""
        from cyberred.llm.ensemble import DegradationWarning, DegradationLevel
        import time
        
        before = time.monotonic()
        warning = DegradationWarning(
            level=DegradationLevel.DEGRADED_SINGLE,
            available_models=[DirectorRole.STRATEGIST],
            excluded_models=[DirectorRole.ANALYST, DirectorRole.CREATIVE],
            message="Single model operation",
        )
        after = time.monotonic()
        
        # Timestamp should be between before and after monotonic readings
        assert before <= warning.timestamp <= after

    def test_warning_to_event(self) -> None:
        """Test converting warning to event format."""
        from cyberred.llm.ensemble import DegradationWarning, DegradationLevel
        
        warning = DegradationWarning(
            level=DegradationLevel.DEGRADED_SINGLE,
            available_models=[DirectorRole.STRATEGIST],
            excluded_models=[DirectorRole.ANALYST, DirectorRole.CREATIVE],
            message="Single model operation",
        )
        event = warning.to_event()
        
        assert event["type"] == "director_degradation_warning"
        assert event["level"] == "degraded_single"
        assert len(event["available_models"]) == 1
        assert len(event["excluded_models"]) == 2
        assert "timestamp" in event


class TestNoModelsAvailableError:
    """Tests for NoModelsAvailableError exception."""

    def test_create_error(self) -> None:
        """Test creating NoModelsAvailableError."""
        from cyberred.core.exceptions import NoModelsAvailableError
        
        error = NoModelsAvailableError()
        assert "No Director models available" in str(error)

    def test_create_error_with_details(self) -> None:
        """Test creating error with excluded models and errors."""
        from cyberred.core.exceptions import NoModelsAvailableError
        
        error = NoModelsAvailableError(
            message="All models failed",
            excluded_models=["strategist", "analyst", "creative"],
            last_errors={
                "strategist": "Timeout",
                "analyst": "Provider unavailable",
                "creative": "Rate limited",
            },
        )
        assert "All models failed" in str(error)
        assert len(error.excluded_models) == 3
        assert "strategist" in error.last_errors

    def test_error_context(self) -> None:
        """Test error context property."""
        from cyberred.core.exceptions import NoModelsAvailableError
        
        error = NoModelsAvailableError(
            excluded_models=["strategist"],
            last_errors={"strategist": "Error"},
        )
        ctx = error.context
        assert "excluded_models" in ctx
        assert "last_errors" in ctx


class TestConfidenceMultipliers:
    """Tests for confidence score reduction."""

    def test_confidence_multipliers_defined(self) -> None:
        """Test confidence multipliers are defined."""
        from cyberred.llm.ensemble import CONFIDENCE_MULTIPLIERS
        
        assert CONFIDENCE_MULTIPLIERS[3] == 1.0
        assert CONFIDENCE_MULTIPLIERS[2] == 0.75
        assert CONFIDENCE_MULTIPLIERS[1] == 0.5

    def test_apply_confidence_reduction_full(self) -> None:
        """Test no reduction when all 3 models available."""
        from cyberred.llm.ensemble import CONFIDENCE_MULTIPLIERS
        
        base_confidence = 0.8
        result = base_confidence * CONFIDENCE_MULTIPLIERS[3]
        assert result == 0.8

    def test_apply_confidence_reduction_pair(self) -> None:
        """Test 25% reduction when 2 models available."""
        from cyberred.llm.ensemble import CONFIDENCE_MULTIPLIERS
        
        base_confidence = 0.8
        result = base_confidence * CONFIDENCE_MULTIPLIERS[2]
        assert abs(result - 0.6) < 0.001  # Float comparison tolerance

    def test_apply_confidence_reduction_single(self) -> None:
        """Test 50% reduction when 1 model available."""
        from cyberred.llm.ensemble import CONFIDENCE_MULTIPLIERS
        
        base_confidence = 0.8
        result = base_confidence * CONFIDENCE_MULTIPLIERS[1]
        assert result == 0.4


class TestSynthesizedStrategyDegradationFields:
    """Tests for extended SynthesizedStrategy with degradation fields."""

    def test_default_degradation_level(self) -> None:
        """Test default degradation level is FULL."""
        from cyberred.llm.ensemble import DegradationLevel
        
        strategy = SynthesizedStrategy(
            objectives=["Test"],
            actions=["Action"],
            rationale="Test",
            confidence=0.9,
            contributing_roles=[DirectorRole.STRATEGIST],
        )
        assert strategy.degradation_level == DegradationLevel.FULL

    def test_missing_perspectives_default(self) -> None:
        """Test missing_perspectives defaults to empty list."""
        strategy = SynthesizedStrategy(
            objectives=["Test"],
            actions=["Action"],
            rationale="Test",
            confidence=0.9,
            contributing_roles=[DirectorRole.STRATEGIST],
        )
        assert strategy.missing_perspectives == []

    def test_fallback_warnings_default(self) -> None:
        """Test fallback_warnings defaults to empty list."""
        strategy = SynthesizedStrategy(
            objectives=["Test"],
            actions=["Action"],
            rationale="Test",
            confidence=0.9,
            contributing_roles=[DirectorRole.STRATEGIST],
        )
        assert strategy.fallback_warnings == []

    def test_degraded_strategy_to_json(self) -> None:
        """Test degraded strategy serializes correctly."""
        from cyberred.llm.ensemble import DegradationLevel
        
        strategy = SynthesizedStrategy(
            objectives=["Test objective"],
            actions=["Test action"],
            rationale="Test rationale",
            confidence=0.6,
            contributing_roles=[DirectorRole.STRATEGIST, DirectorRole.CREATIVE],
            degradation_level=DegradationLevel.DEGRADED_PAIR,
            missing_perspectives=[DirectorRole.ANALYST],
            fallback_warnings=["Operating in degraded mode"],
        )
        json_data = strategy.to_json()
        
        assert json_data["degradation_level"] == "degraded_pair"
        assert "analyst" in json_data["missing_perspectives"]
        assert "Operating in degraded mode" in json_data["fallback_warnings"]
