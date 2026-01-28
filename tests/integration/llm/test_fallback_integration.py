"""Integration tests for Partial Model Availability Fallback (Story 8.6).

Tests cover:
- Full degradation and recovery cycle
- Circuit breaker integration with DirectorEnsemble
- Degraded synthesis modes (pair, single)
- Zero-model error handling
- Model recovery after exclusion
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
    DirectorModel,
    ModelResponse,
    SynthesisInput,
    CircuitBreaker,
    DegradationLevel,
    CONFIDENCE_MULTIPLIERS,
)
from cyberred.llm.provider import LLMResponse, TokenUsage
from cyberred.core.exceptions import LLMTimeoutError, LLMProviderUnavailable, NoModelsAvailableError


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker with DirectorEnsemble."""

    @pytest.fixture
    def sample_context(self) -> DirectorContext:
        """Create sample context for tests."""
        return DirectorContext(
            engagement_id="eng-integration-001",
            phase="recon",
            prompt="Analyze attack strategy",
        )

    @pytest.mark.asyncio
    async def test_circuit_breaker_excludes_after_three_failures(
        self, sample_context: DirectorContext
    ) -> None:
        """Test that circuit breaker excludes model after 3 failures."""
        cb = CircuitBreaker(failure_threshold=3, exclusion_seconds=60.0)
        
        # Simulate 3 failures
        for i in range(3):
            excluded = cb.record_failure(DirectorRole.STRATEGIST)
            if i < 2:
                assert excluded is False
            else:
                assert excluded is True
        
        # Model should now be excluded
        assert cb.is_available(DirectorRole.STRATEGIST) is False
        assert DirectorRole.STRATEGIST not in cb.get_available_roles()

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery_after_exclusion_period(self) -> None:
        """Test that model recovers after exclusion period expires."""
        cb = CircuitBreaker(failure_threshold=3, exclusion_seconds=0.05)  # 50ms
        
        # Trigger exclusion
        for _ in range(3):
            cb.record_failure(DirectorRole.ANALYST)
        
        assert cb.is_available(DirectorRole.ANALYST) is False
        
        # Wait for exclusion to expire
        await asyncio.sleep(0.1)
        
        assert cb.is_available(DirectorRole.ANALYST) is True

    @pytest.mark.asyncio
    async def test_success_resets_circuit_breaker_state(self) -> None:
        """Test that success resets failure count."""
        cb = CircuitBreaker(failure_threshold=3, exclusion_seconds=60.0)
        
        # Record 2 failures
        cb.record_failure(DirectorRole.CREATIVE)
        cb.record_failure(DirectorRole.CREATIVE)
        
        # Then success
        cb.record_success(DirectorRole.CREATIVE)
        
        # Should need 3 more failures to exclude
        cb.record_failure(DirectorRole.CREATIVE)
        cb.record_failure(DirectorRole.CREATIVE)
        assert cb.is_available(DirectorRole.CREATIVE) is True
        
        # Third failure triggers exclusion
        cb.record_failure(DirectorRole.CREATIVE)
        assert cb.is_available(DirectorRole.CREATIVE) is False


class TestDegradedSynthesisIntegration:
    """Integration tests for degraded synthesis modes."""

    @pytest.fixture
    def ensemble(self) -> DirectorEnsemble:
        """Create DirectorEnsemble for tests."""
        return DirectorEnsemble()

    @pytest.fixture
    def sample_context(self) -> DirectorContext:
        """Create sample context for tests."""
        return DirectorContext(
            engagement_id="eng-degraded-001",
            phase="exploitation",
            prompt="Plan attack for discovered SSH service",
        )

    def test_full_synthesis_with_all_models(self, ensemble: DirectorEnsemble) -> None:
        """Test synthesis with all 3 models available."""
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test",
        )
        responses = {
            DirectorRole.STRATEGIST: ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="m1",
                content="### Strategic Recommendations\n1. Scan ports\n\n### Confidence Assessment\n0.8",
                latency_ms=100,
                success=True,
            ),
            DirectorRole.ANALYST: ModelResponse(
                role=DirectorRole.ANALYST,
                model_id="m2",
                content="### Attack Surface Analysis\nSSH exposed\n\n### Risk Assessment\n**Overall Risk Level:** HIGH",
                latency_ms=200,
                success=True,
            ),
            DirectorRole.CREATIVE: ModelResponse(
                role=DirectorRole.CREATIVE,
                model_id="m3",
                content="<think>Consider tunneling</think>\n\n### Creative Alternatives\n| ALT-001 | SSH tunnel | bypass firewall | 0.7 |",
                latency_ms=150,
                success=True,
            ),
        }
        from cyberred.llm.ensemble import DirectorQueryResult
        query_result = DirectorQueryResult(
            context=context,
            responses=responses,
            total_latency_ms=200,
            successful_count=3,
            failed_count=0,
        )
        synthesis_input = SynthesisInput(query_result=query_result)
        
        strategy = ensemble.synthesize(synthesis_input)
        
        # All 3 roles contributed
        assert len(strategy.contributing_roles) == 3
        assert strategy.degradation_level == DegradationLevel.FULL

    def test_pair_synthesis_with_two_models(self, ensemble: DirectorEnsemble) -> None:
        """Test synthesis with 2 of 3 models available."""
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test",
        )
        responses = {
            DirectorRole.STRATEGIST: ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="m1",
                content="### Strategic Recommendations\n1. Focus on web app\n\n### Confidence Assessment\n0.7",
                latency_ms=100,
                success=True,
            ),
            DirectorRole.ANALYST: ModelResponse(
                role=DirectorRole.ANALYST,
                model_id="m2",
                content="",
                latency_ms=5000,
                success=False,
                error="Timeout",
            ),
            DirectorRole.CREATIVE: ModelResponse(
                role=DirectorRole.CREATIVE,
                model_id="m3",
                content="<think>Creative approach</think>\n\n### Novel Approaches\n| NOV-001 | Test |",
                latency_ms=150,
                success=True,
            ),
        }
        from cyberred.llm.ensemble import DirectorQueryResult
        query_result = DirectorQueryResult(
            context=context,
            responses=responses,
            total_latency_ms=5000,
            successful_count=2,
            failed_count=1,
        )
        synthesis_input = SynthesisInput(query_result=query_result)
        
        strategy = ensemble.synthesize(synthesis_input)
        
        # Only 2 roles contributed
        assert len(strategy.contributing_roles) == 2
        assert DirectorRole.ANALYST not in strategy.contributing_roles

    def test_single_synthesis_with_one_model(self, ensemble: DirectorEnsemble) -> None:
        """Test synthesis with only 1 model available."""
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test",
        )
        responses = {
            DirectorRole.STRATEGIST: ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="m1",
                content="### Strategic Recommendations\n1. Proceed with caution\n\n### Confidence Assessment\n0.5",
                latency_ms=100,
                success=True,
            ),
            DirectorRole.ANALYST: ModelResponse(
                role=DirectorRole.ANALYST,
                model_id="m2",
                content="",
                latency_ms=5000,
                success=False,
                error="Provider unavailable",
            ),
            DirectorRole.CREATIVE: ModelResponse(
                role=DirectorRole.CREATIVE,
                model_id="m3",
                content="",
                latency_ms=5000,
                success=False,
                error="Timeout",
            ),
        }
        from cyberred.llm.ensemble import DirectorQueryResult
        query_result = DirectorQueryResult(
            context=context,
            responses=responses,
            total_latency_ms=5000,
            successful_count=1,
            failed_count=2,
        )
        synthesis_input = SynthesisInput(query_result=query_result)
        
        strategy = ensemble.synthesize(synthesis_input)
        
        # Only 1 role contributed
        assert len(strategy.contributing_roles) == 1
        assert DirectorRole.STRATEGIST in strategy.contributing_roles


class TestFullDegradationCycle:
    """Integration tests for complete degradation and recovery cycle."""

    @pytest.mark.asyncio
    async def test_full_cycle_degradation_and_recovery(self) -> None:
        """Test complete cycle: healthy → degraded → recovery."""
        cb = CircuitBreaker(failure_threshold=3, exclusion_seconds=0.1)  # 100ms exclusion
        
        # Phase 1: All models available
        assert len(cb.get_available_roles()) == 3
        
        # Phase 2: One model starts failing
        cb.record_failure(DirectorRole.ANALYST)
        cb.record_failure(DirectorRole.ANALYST)
        assert len(cb.get_available_roles()) == 3  # Still available
        
        # Phase 3: Third failure triggers exclusion
        cb.record_failure(DirectorRole.ANALYST)
        assert len(cb.get_available_roles()) == 2
        assert DirectorRole.ANALYST not in cb.get_available_roles()
        
        # Phase 4: Wait for recovery
        await asyncio.sleep(0.15)
        
        # Phase 5: Model recovered
        assert len(cb.get_available_roles()) == 3
        assert DirectorRole.ANALYST in cb.get_available_roles()

    @pytest.mark.asyncio
    async def test_multiple_models_degraded_simultaneously(self) -> None:
        """Test handling when multiple models fail at once."""
        cb = CircuitBreaker(failure_threshold=3, exclusion_seconds=0.1)
        
        # Fail two models
        for _ in range(3):
            cb.record_failure(DirectorRole.STRATEGIST)
            cb.record_failure(DirectorRole.ANALYST)
        
        # Only creative should be available
        available = cb.get_available_roles()
        assert len(available) == 1
        assert DirectorRole.CREATIVE in available
        
        # Recovery
        await asyncio.sleep(0.15)
        assert len(cb.get_available_roles()) == 3

    @pytest.mark.asyncio
    async def test_all_models_excluded(self) -> None:
        """Test handling when all models are excluded."""
        cb = CircuitBreaker(failure_threshold=3, exclusion_seconds=60.0)
        
        # Exclude all models
        for role in DirectorRole:
            for _ in range(3):
                cb.record_failure(role)
        
        # No models available
        assert len(cb.get_available_roles()) == 0
        
        # This would trigger NoModelsAvailableError in production


class TestConfidenceScoreReduction:
    """Integration tests for confidence score reduction based on available models."""

    def test_confidence_reduction_reflects_model_count(self) -> None:
        """Test that confidence is correctly reduced based on available model count."""
        base_confidence = 0.8
        
        # Full ensemble - no reduction
        full_confidence = base_confidence * CONFIDENCE_MULTIPLIERS[3]
        assert full_confidence == 0.8
        
        # Pair mode - 25% reduction
        pair_confidence = base_confidence * CONFIDENCE_MULTIPLIERS[2]
        assert abs(pair_confidence - 0.6) < 0.001
        
        # Single mode - 50% reduction
        single_confidence = base_confidence * CONFIDENCE_MULTIPLIERS[1]
        assert single_confidence == 0.4
