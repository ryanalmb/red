"""Integration tests for Director Ensemble (Story 8.1).

Tests verify:
- Full ensemble workflow with mocked gateway
- Concurrent query execution behavior
- Integration with LLMGateway patterns
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.llm.ensemble import (
    DirectorRole,
    DirectorContext,
    DirectorEnsemble,
    SynthesisInput,
)
from cyberred.llm.provider import LLMResponse, TokenUsage


class TestDirectorEnsembleIntegration:
    """Integration tests for DirectorEnsemble."""

    @pytest.fixture
    def sample_context(self) -> DirectorContext:
        """Create a realistic context for integration tests."""
        return DirectorContext(
            engagement_id="eng-integration-001",
            phase="exploitation",
            prompt="Analyze discovered SSH service on port 22 and recommend attack strategy",
            findings=[
                {"type": "service", "port": 22, "service": "ssh", "version": "OpenSSH 7.6"},
                {"type": "service", "port": 80, "service": "http", "version": "nginx 1.14"},
                {"type": "vuln", "cve": "CVE-2018-15473", "severity": "medium"},
            ],
            constraints={
                "no_dos": True,
                "stealth_required": True,
                "scope": ["192.168.1.0/24"],
            },
            previous_strategies=["Initial network scan completed"],
        )

    @pytest.fixture
    def mock_gateway_responses(self) -> dict[str, LLMResponse]:
        """Create mock responses for each model."""
        return {
            "deepseek-ai/deepseek-v3.2": LLMResponse(
                content="""Strategic Analysis:
1. Primary Target: SSH service (port 22) - OpenSSH 7.6 has known username enumeration vulnerability
2. Secondary Target: HTTP service for potential web application attacks
3. Recommended Sequence: 
   - Enumerate valid usernames via CVE-2018-15473
   - Attempt credential stuffing with common credentials
   - If access gained, pivot to web server
4. Risk Assessment: Medium - stealth required limits brute-force options""",
                model="deepseek-ai/deepseek-v3.2",
                usage=TokenUsage(prompt_tokens=200, completion_tokens=150, total_tokens=350),
                latency_ms=1500,
            ),
            "moonshotai/kimi-k2-instruct": LLMResponse(
                content="""Deep Analysis:
1. CVE-2018-15473 Impact: Username enumeration allows targeted password attacks
2. OpenSSH 7.6 Attack Surface:
   - No direct RCE vulnerabilities known
   - Authentication bypass requires weak credentials
   - Key-based auth may be in use
3. Prerequisites:
   - Valid username list from enumeration
   - Password list based on target context
4. Dependencies: HTTP service may reveal usernames via web app""",
                model="moonshotai/kimi-k2-instruct",
                usage=TokenUsage(prompt_tokens=200, completion_tokens=180, total_tokens=380),
                latency_ms=2200,
            ),
            "minimaxai/minimax-m2": LLMResponse(
                content="""Creative Approaches:
1. Unconventional Vector: Check for SSH agent forwarding misconfiguration
2. Evasion Technique: Use slow/randomized timing to avoid detection
3. Alternative: Web application user enumeration may yield SSH usernames
4. Lateral Thinking: Check for exposed .ssh directories via HTTP
5. Consider: SSH tunneling through compromised web app if initial access fails""",
                model="minimaxai/minimax-m2",
                usage=TokenUsage(prompt_tokens=200, completion_tokens=120, total_tokens=320),
                latency_ms=1200,
            ),
        }

    @pytest.mark.asyncio
    async def test_full_ensemble_workflow(
        self, sample_context: DirectorContext, mock_gateway_responses: dict
    ) -> None:
        """Test complete ensemble query and synthesis workflow."""
        ensemble = DirectorEnsemble()

        async def mock_director_complete(request):
            model_id = request.model
            await asyncio.sleep(0.01)  # Simulate small latency
            return mock_gateway_responses[model_id]

        mock_gateway = MagicMock()
        mock_gateway.director_complete = mock_director_complete

        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            # Query all models
            result = await ensemble.query_all(sample_context)

            assert result.all_succeeded
            assert result.successful_count == 3

            # Verify each role has meaningful content
            for role in DirectorRole:
                content = result.get_content(role)
                assert len(content) > 100, f"Role {role} should have substantial content"

            # Test synthesis
            synthesis_input = SynthesisInput(query_result=result)
            strategy = ensemble.synthesize(synthesis_input)

            # Confidence is calculated as: availability_factor*0.4 + avg_confidence*0.4 + consensus*0.2
            # With all 3 models available and default confidence (0.5), this yields ~0.8
            assert strategy.confidence >= 0.6  # At least reasonable confidence with all models
            assert len(strategy.contributing_roles) == 3

    @pytest.mark.asyncio
    async def test_ensemble_graceful_degradation(
        self, sample_context: DirectorContext, mock_gateway_responses: dict
    ) -> None:
        """Test ensemble continues with partial failures."""
        ensemble = DirectorEnsemble()

        call_count = 0

        async def mock_director_complete_with_failure(request):
            nonlocal call_count
            call_count += 1
            model_id = request.model
            
            # Simulate one model failing
            if model_id == "moonshotai/kimi-k2-instruct":
                raise asyncio.TimeoutError("Simulated timeout")
            
            await asyncio.sleep(0.01)
            return mock_gateway_responses[model_id]

        mock_gateway = MagicMock()
        mock_gateway.director_complete = mock_director_complete_with_failure

        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            result = await ensemble.query_all(sample_context)

            # Should still have 2 successful responses
            assert result.successful_count == 2
            assert result.failed_count == 1
            assert result.has_responses

            # Strategist and Creative should have content
            assert len(result.get_content(DirectorRole.STRATEGIST)) > 0
            assert len(result.get_content(DirectorRole.CREATIVE)) > 0
            
            # Analyst should be empty
            assert result.get_content(DirectorRole.ANALYST) == ""

            # Synthesis should still work with partial responses
            synthesis_input = SynthesisInput(query_result=result)
            strategy = ensemble.synthesize(synthesis_input)

            # With 2/3 models available and default confidence, expect degraded confidence
            # availability_factor=2/3, avg_confidence=0.5, consensus varies
            assert strategy.confidence >= 0.4  # Reasonable degraded confidence
            assert strategy.confidence <= 0.8  # But not full confidence
            assert DirectorRole.ANALYST not in strategy.contributing_roles

    @pytest.mark.asyncio
    async def test_ensemble_parallel_performance(
        self, sample_context: DirectorContext, mock_gateway_responses: dict
    ) -> None:
        """Test that queries execute in parallel, not sequentially."""
        ensemble = DirectorEnsemble()

        model_start_times: dict[str, float] = {}
        
        async def mock_director_complete_with_timing(request):
            import time
            model_id = request.model
            model_start_times[model_id] = time.monotonic()
            
            # Each model takes 100ms
            await asyncio.sleep(0.1)
            return mock_gateway_responses[model_id]

        mock_gateway = MagicMock()
        mock_gateway.director_complete = mock_director_complete_with_timing

        import time
        start = time.monotonic()
        
        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            result = await ensemble.query_all(sample_context)

        elapsed = time.monotonic() - start

        assert result.all_succeeded
        
        # If parallel: ~100ms total
        # If sequential: ~300ms total
        # Allow some tolerance
        assert elapsed < 0.25, f"Expected parallel execution (<250ms), got {elapsed*1000:.0f}ms"

        # All models should have started within 50ms of each other
        start_times = list(model_start_times.values())
        time_spread = max(start_times) - min(start_times)
        assert time_spread < 0.05, f"Models should start near-simultaneously, spread was {time_spread*1000:.0f}ms"

    @pytest.mark.asyncio
    async def test_ensemble_respects_aggregate_timeout(
        self, sample_context: DirectorContext
    ) -> None:
        """Test that aggregate timeout cancels all pending queries."""
        # Very short aggregate timeout
        ensemble = DirectorEnsemble(aggregate_timeout=0.1)

        async def very_slow_complete(request):
            await asyncio.sleep(10)  # Much longer than aggregate timeout
            return LLMResponse(
                content="Never reached",
                model=request.model,
                usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
                latency_ms=10000,
            )

        mock_gateway = MagicMock()
        mock_gateway.director_complete = very_slow_complete

        import time
        start = time.monotonic()
        
        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            result = await ensemble.query_all(sample_context)

        elapsed = time.monotonic() - start

        # Should complete near the aggregate timeout, not wait for all models
        assert elapsed < 0.3, f"Should timeout quickly, took {elapsed*1000:.0f}ms"
        assert result.failed_count == 3
        assert not result.has_responses

    @pytest.mark.asyncio
    async def test_ensemble_with_different_model_configs(
        self, sample_context: DirectorContext, mock_gateway_responses: dict
    ) -> None:
        """Test ensemble with custom model configurations."""
        from cyberred.llm.ensemble import DirectorModel
        
        # Custom models with different timeouts
        custom_models = {
            DirectorRole.STRATEGIST: DirectorModel(
                model_id="deepseek-ai/deepseek-v3.2",
                role=DirectorRole.STRATEGIST,
                timeout=10.0,
                system_prompt="Custom strategist prompt",
            ),
            DirectorRole.ANALYST: DirectorModel(
                model_id="moonshotai/kimi-k2-instruct",
                role=DirectorRole.ANALYST,
                timeout=15.0,
                system_prompt="Custom analyst prompt",
            ),
            DirectorRole.CREATIVE: DirectorModel(
                model_id="minimaxai/minimax-m2",
                role=DirectorRole.CREATIVE,
                timeout=8.0,
                system_prompt="Custom creative prompt",
            ),
        }
        
        ensemble = DirectorEnsemble(models=custom_models, aggregate_timeout=30.0)

        async def mock_director_complete(request):
            model_id = request.model
            return mock_gateway_responses[model_id]

        mock_gateway = MagicMock()
        mock_gateway.director_complete = mock_director_complete

        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            result = await ensemble.query_all(sample_context)

        assert result.all_succeeded
        assert ensemble.aggregate_timeout == 30.0
        assert ensemble.get_model(DirectorRole.STRATEGIST).timeout == 10.0
