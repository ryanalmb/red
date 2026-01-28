"""Unit tests for Director Ensemble (Story 8.1).

Tests cover:
- DirectorRole enum
- DirectorModel dataclass
- DirectorContext dataclass
- ModelResponse dataclass
- DirectorQueryResult dataclass
- SynthesisInput and SynthesizedStrategy dataclasses
- DirectorEnsemble initialization
- Parallel query mechanism
- Synthesis interface
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.llm.ensemble import (
    DirectorRole,
    DirectorModel,
    DirectorContext,
    ModelResponse,
    DirectorQueryResult,
    SynthesisInput,
    SynthesizedStrategy,
    DirectorEnsemble,
    DIRECTOR_MODELS,
)
from cyberred.llm.provider import LLMResponse, TokenUsage
from cyberred.core.exceptions import LLMTimeoutError, LLMProviderUnavailable


class TestDirectorRole:
    """Tests for DirectorRole enum."""

    def test_role_values(self) -> None:
        """Test that all expected roles exist with correct values."""
        assert DirectorRole.STRATEGIST.value == "strategist"
        assert DirectorRole.ANALYST.value == "analyst"
        assert DirectorRole.CREATIVE.value == "creative"

    def test_role_count(self) -> None:
        """Test that exactly three roles exist."""
        assert len(DirectorRole) == 3

    def test_roles_are_unique(self) -> None:
        """Test that all role values are unique."""
        values = [role.value for role in DirectorRole]
        assert len(values) == len(set(values))


class TestDirectorModel:
    """Tests for DirectorModel dataclass."""

    def test_create_model(self) -> None:
        """Test creating a DirectorModel."""
        model = DirectorModel(
            model_id="test-model",
            role=DirectorRole.STRATEGIST,
            timeout=30.0,
            system_prompt="Test prompt",
        )
        assert model.model_id == "test-model"
        assert model.role == DirectorRole.STRATEGIST
        assert model.timeout == 30.0
        assert model.system_prompt == "Test prompt"

    def test_model_is_frozen(self) -> None:
        """Test that DirectorModel is immutable."""
        model = DirectorModel(
            model_id="test",
            role=DirectorRole.ANALYST,
            timeout=10.0,
            system_prompt="prompt",
        )
        with pytest.raises(AttributeError):
            model.model_id = "changed"  # type: ignore

    def test_default_models_exist(self) -> None:
        """Test that default models are configured for all roles."""
        for role in DirectorRole:
            assert role in DIRECTOR_MODELS
            model = DIRECTOR_MODELS[role]
            assert model.role == role
            assert model.model_id
            assert model.timeout > 0
            assert model.system_prompt


class TestDirectorContext:
    """Tests for DirectorContext dataclass."""

    def test_create_minimal_context(self) -> None:
        """Test creating context with required fields only."""
        ctx = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="What should we do?",
        )
        assert ctx.engagement_id == "eng-001"
        assert ctx.phase == "recon"
        assert ctx.prompt == "What should we do?"
        assert ctx.findings == []
        assert ctx.constraints == {}
        assert ctx.previous_strategies == []
        assert ctx.metadata == {}

    def test_create_full_context(self) -> None:
        """Test creating context with all fields."""
        ctx = DirectorContext(
            engagement_id="eng-002",
            phase="exploitation",
            prompt="Analyze target",
            findings=[{"type": "port", "value": 22}],
            constraints={"no_dos": True},
            previous_strategies=["scan first"],
            metadata={"priority": "high"},
        )
        assert len(ctx.findings) == 1
        assert ctx.constraints["no_dos"] is True
        assert "scan first" in ctx.previous_strategies
        assert ctx.metadata["priority"] == "high"

    def test_empty_engagement_id_raises(self) -> None:
        """Test that empty engagement_id raises ValueError."""
        with pytest.raises(ValueError, match="engagement_id cannot be empty"):
            DirectorContext(
                engagement_id="",
                phase="recon",
                prompt="Test prompt",
            )

    def test_whitespace_engagement_id_raises(self) -> None:
        """Test that whitespace-only engagement_id raises ValueError."""
        with pytest.raises(ValueError, match="engagement_id cannot be empty"):
            DirectorContext(
                engagement_id="   ",
                phase="recon",
                prompt="Test prompt",
            )

    def test_empty_phase_raises(self) -> None:
        """Test that empty phase raises ValueError."""
        with pytest.raises(ValueError, match="phase cannot be empty"):
            DirectorContext(
                engagement_id="eng-001",
                phase="",
                prompt="Test prompt",
            )

    def test_whitespace_phase_raises(self) -> None:
        """Test that whitespace-only phase raises ValueError."""
        with pytest.raises(ValueError, match="phase cannot be empty"):
            DirectorContext(
                engagement_id="eng-001",
                phase="  \t  ",
                prompt="Test prompt",
            )

    def test_empty_prompt_raises(self) -> None:
        """Test that empty prompt raises ValueError."""
        with pytest.raises(ValueError, match="prompt cannot be empty"):
            DirectorContext(
                engagement_id="eng-001",
                phase="recon",
                prompt="",
            )

    def test_whitespace_prompt_raises(self) -> None:
        """Test that whitespace-only prompt raises ValueError."""
        with pytest.raises(ValueError, match="prompt cannot be empty"):
            DirectorContext(
                engagement_id="eng-001",
                phase="recon",
                prompt="   \n   ",
            )


class TestModelResponse:
    """Tests for ModelResponse dataclass."""

    def test_successful_response(self) -> None:
        """Test creating a successful model response."""
        resp = ModelResponse(
            role=DirectorRole.STRATEGIST,
            model_id="test-model",
            content="Attack plan here",
            latency_ms=150,
            success=True,
            token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )
        assert resp.success is True
        assert resp.content == "Attack plan here"
        assert resp.error is None
        assert resp.token_usage.total_tokens == 150

    def test_failed_response(self) -> None:
        """Test creating a failed model response."""
        resp = ModelResponse(
            role=DirectorRole.ANALYST,
            model_id="test-model",
            content="",
            latency_ms=5000,
            success=False,
            error="Timeout after 30s",
        )
        assert resp.success is False
        assert resp.content == ""
        assert resp.error == "Timeout after 30s"


class TestDirectorQueryResult:
    """Tests for DirectorQueryResult dataclass."""

    @pytest.fixture
    def sample_context(self) -> DirectorContext:
        """Create sample context for tests."""
        return DirectorContext(
            engagement_id="eng-test",
            phase="recon",
            prompt="Test query",
        )

    @pytest.fixture
    def all_success_responses(self) -> dict[DirectorRole, ModelResponse]:
        """Create responses where all models succeed."""
        return {
            DirectorRole.STRATEGIST: ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="m1",
                content="Strategy",
                latency_ms=100,
                success=True,
            ),
            DirectorRole.ANALYST: ModelResponse(
                role=DirectorRole.ANALYST,
                model_id="m2",
                content="Analysis",
                latency_ms=200,
                success=True,
            ),
            DirectorRole.CREATIVE: ModelResponse(
                role=DirectorRole.CREATIVE,
                model_id="m3",
                content="Creative",
                latency_ms=150,
                success=True,
            ),
        }

    def test_all_succeeded(
        self, sample_context: DirectorContext, all_success_responses: dict
    ) -> None:
        """Test all_succeeded property when all models succeed."""
        result = DirectorQueryResult(
            context=sample_context,
            responses=all_success_responses,
            total_latency_ms=250,
            successful_count=3,
            failed_count=0,
        )
        assert result.all_succeeded is True
        assert result.has_responses is True

    def test_partial_success(self, sample_context: DirectorContext) -> None:
        """Test properties when some models fail."""
        responses = {
            DirectorRole.STRATEGIST: ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="m1",
                content="Strategy",
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
                content="Creative",
                latency_ms=150,
                success=True,
            ),
        }
        result = DirectorQueryResult(
            context=sample_context,
            responses=responses,
            total_latency_ms=5000,
            successful_count=2,
            failed_count=1,
        )
        assert result.all_succeeded is False
        assert result.has_responses is True

    def test_all_failed(self, sample_context: DirectorContext) -> None:
        """Test properties when all models fail."""
        responses = {
            role: ModelResponse(
                role=role,
                model_id=f"m{i}",
                content="",
                latency_ms=5000,
                success=False,
                error="Timeout",
            )
            for i, role in enumerate(DirectorRole)
        }
        result = DirectorQueryResult(
            context=sample_context,
            responses=responses,
            total_latency_ms=5000,
            successful_count=0,
            failed_count=3,
        )
        assert result.all_succeeded is False
        assert result.has_responses is False

    def test_get_response(
        self, sample_context: DirectorContext, all_success_responses: dict
    ) -> None:
        """Test get_response method."""
        result = DirectorQueryResult(
            context=sample_context,
            responses=all_success_responses,
            total_latency_ms=250,
            successful_count=3,
            failed_count=0,
        )
        resp = result.get_response(DirectorRole.STRATEGIST)
        assert resp is not None
        assert resp.role == DirectorRole.STRATEGIST

    def test_get_content(
        self, sample_context: DirectorContext, all_success_responses: dict
    ) -> None:
        """Test get_content method."""
        result = DirectorQueryResult(
            context=sample_context,
            responses=all_success_responses,
            total_latency_ms=250,
            successful_count=3,
            failed_count=0,
        )
        assert result.get_content(DirectorRole.ANALYST) == "Analysis"

    def test_get_content_failed_response(
        self, sample_context: DirectorContext
    ) -> None:
        """Test get_content returns empty string for failed responses."""
        responses = {
            DirectorRole.STRATEGIST: ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="m1",
                content="",
                latency_ms=5000,
                success=False,
                error="Timeout",
            ),
        }
        result = DirectorQueryResult(
            context=sample_context,
            responses=responses,
            total_latency_ms=5000,
            successful_count=0,
            failed_count=1,
        )
        assert result.get_content(DirectorRole.STRATEGIST) == ""


class TestSynthesisDataclasses:
    """Tests for SynthesisInput and SynthesizedStrategy dataclasses."""

    def test_synthesis_input(self) -> None:
        """Test creating SynthesisInput."""
        ctx = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test",
        )
        responses = {
            role: ModelResponse(
                role=role,
                model_id=f"m{i}",
                content=f"Content {i}",
                latency_ms=100,
                success=True,
            )
            for i, role in enumerate(DirectorRole)
        }
        query_result = DirectorQueryResult(
            context=ctx,
            responses=responses,
            total_latency_ms=300,
            successful_count=3,
            failed_count=0,
        )
        synthesis_input = SynthesisInput(
            query_result=query_result,
            synthesis_prompt="Combine these",
        )
        assert synthesis_input.query_result == query_result
        assert synthesis_input.synthesis_prompt == "Combine these"

    def test_synthesized_strategy(self) -> None:
        """Test creating SynthesizedStrategy."""
        strategy = SynthesizedStrategy(
            objectives=["Gain foothold", "Escalate privileges"],
            actions=["Scan ports", "Exploit SSH"],
            rationale="Based on discovered services",
            confidence=0.85,
            contributing_roles=[DirectorRole.STRATEGIST, DirectorRole.ANALYST],
            metadata={"version": "1.0"},
        )
        assert len(strategy.objectives) == 2
        assert len(strategy.actions) == 2
        assert strategy.confidence == 0.85
        assert DirectorRole.STRATEGIST in strategy.contributing_roles


class TestDirectorEnsemble:
    """Tests for DirectorEnsemble class."""

    def test_init_default_models(self) -> None:
        """Test initialization with default models."""
        ensemble = DirectorEnsemble()
        assert len(ensemble.models) == 3
        for role in DirectorRole:
            assert role in ensemble.models

    def test_init_custom_models(self) -> None:
        """Test initialization with custom models."""
        custom_models = {
            DirectorRole.STRATEGIST: DirectorModel(
                model_id="custom-strategist",
                role=DirectorRole.STRATEGIST,
                timeout=20.0,
                system_prompt="Custom strategist prompt",
            ),
            DirectorRole.ANALYST: DirectorModel(
                model_id="custom-analyst",
                role=DirectorRole.ANALYST,
                timeout=25.0,
                system_prompt="Custom analyst prompt",
            ),
            DirectorRole.CREATIVE: DirectorModel(
                model_id="custom-creative",
                role=DirectorRole.CREATIVE,
                timeout=15.0,
                system_prompt="Custom creative prompt",
            ),
        }
        ensemble = DirectorEnsemble(models=custom_models)
        assert ensemble.get_model(DirectorRole.STRATEGIST).model_id == "custom-strategist"

    def test_init_missing_role_raises(self) -> None:
        """Test that missing role configuration raises ValueError."""
        incomplete_models = {
            DirectorRole.STRATEGIST: DirectorModel(
                model_id="m1",
                role=DirectorRole.STRATEGIST,
                timeout=10.0,
                system_prompt="prompt",
            ),
        }
        with pytest.raises(ValueError, match="Missing model configuration"):
            DirectorEnsemble(models=incomplete_models)

    def test_init_custom_timeout(self) -> None:
        """Test initialization with custom aggregate timeout."""
        ensemble = DirectorEnsemble(aggregate_timeout=120.0)
        assert ensemble.aggregate_timeout == 120.0

    def test_default_aggregate_timeout(self) -> None:
        """Test default aggregate timeout is 180 seconds per architecture."""
        ensemble = DirectorEnsemble()
        assert ensemble.aggregate_timeout == 180.0

    def test_get_model(self) -> None:
        """Test get_model method."""
        ensemble = DirectorEnsemble()
        model = ensemble.get_model(DirectorRole.ANALYST)
        assert model.role == DirectorRole.ANALYST

    def test_models_property_returns_copy(self) -> None:
        """Test that models property returns a copy."""
        ensemble = DirectorEnsemble()
        models1 = ensemble.models
        models2 = ensemble.models
        assert models1 is not models2

    @pytest.mark.asyncio
    async def test_query_model_success(self) -> None:
        """Test successful single model query."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Analyze target",
        )

        mock_response = LLMResponse(
            content="Strategic analysis result",
            model="test-model",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            latency_ms=100,
        )

        mock_gateway = MagicMock()
        mock_gateway.director_complete = AsyncMock(return_value=mock_response)

        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            response = await ensemble.query_model(DirectorRole.STRATEGIST, context)

        assert response.success is True
        assert response.content == "Strategic analysis result"
        assert response.role == DirectorRole.STRATEGIST
        assert response.latency_ms >= 0  # Can be 0 for fast mock calls

    @pytest.mark.asyncio
    async def test_query_model_timeout(self) -> None:
        """Test model query timeout handling."""
        # Use very short timeout for test
        custom_models = {
            role: DirectorModel(
                model_id=f"model-{role.value}",
                role=role,
                timeout=0.001,  # 1ms timeout
                system_prompt="prompt",
            )
            for role in DirectorRole
        }
        ensemble = DirectorEnsemble(models=custom_models)
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test",
        )

        async def slow_complete(*args, **kwargs):
            await asyncio.sleep(1)  # Much longer than timeout
            return LLMResponse(content="Too slow", model="test", usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20), latency_ms=1000)

        mock_gateway = MagicMock()
        mock_gateway.director_complete = slow_complete

        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            response = await ensemble.query_model(DirectorRole.STRATEGIST, context)

        assert response.success is False
        assert "Timeout" in response.error

    @pytest.mark.asyncio
    async def test_query_model_llm_timeout_error(self) -> None:
        """Test handling of LLMTimeoutError."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test",
        )

        mock_gateway = MagicMock()
        mock_gateway.director_complete = AsyncMock(
            side_effect=LLMTimeoutError("LLM timeout", timeout_seconds=30.0)
        )

        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            response = await ensemble.query_model(DirectorRole.ANALYST, context)

        assert response.success is False
        assert "LLM timeout" in response.error

    @pytest.mark.asyncio
    async def test_query_model_provider_unavailable(self) -> None:
        """Test handling of LLMProviderUnavailable."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test",
        )

        mock_gateway = MagicMock()
        mock_gateway.director_complete = AsyncMock(
            side_effect=LLMProviderUnavailable("Provider down")
        )

        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            response = await ensemble.query_model(DirectorRole.CREATIVE, context)

        assert response.success is False
        assert "Provider down" in response.error

    @pytest.mark.asyncio
    async def test_query_model_unexpected_exception(self) -> None:
        """Test handling of unexpected exceptions."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test",
        )

        mock_gateway = MagicMock()
        mock_gateway.director_complete = AsyncMock(
            side_effect=RuntimeError("Unexpected internal error")
        )

        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            response = await ensemble.query_model(DirectorRole.STRATEGIST, context)

        assert response.success is False
        assert "RuntimeError" in response.error
        assert "Unexpected internal error" in response.error

    @pytest.mark.asyncio
    async def test_query_all_parallel_execution(self) -> None:
        """Test that query_all executes queries in parallel."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="exploitation",
            prompt="Plan attack",
        )

        call_times: list[float] = []

        async def mock_complete(*args, **kwargs):
            import time
            call_times.append(time.monotonic())
            await asyncio.sleep(0.05)  # 50ms delay
            return LLMResponse(
                content="Response",
                model="test",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
                latency_ms=50,
            )

        mock_gateway = MagicMock()
        mock_gateway.director_complete = mock_complete

        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            result = await ensemble.query_all(context)

        # All 3 calls should happen nearly simultaneously (within 20ms of each other)
        assert len(call_times) == 3
        time_spread = max(call_times) - min(call_times)
        assert time_spread < 0.02  # 20ms tolerance for parallel execution

        assert result.successful_count == 3
        assert result.failed_count == 0
        assert result.all_succeeded is True

    @pytest.mark.asyncio
    async def test_query_all_partial_failure(self) -> None:
        """Test query_all with some models failing."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test",
        )

        call_count = 0

        async def mock_complete(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise LLMTimeoutError("Timeout on second call", timeout_seconds=30.0)
            return LLMResponse(
                content="Success",
                model="test",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
                latency_ms=50,
            )

        mock_gateway = MagicMock()
        mock_gateway.director_complete = mock_complete

        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            result = await ensemble.query_all(context)

        assert result.successful_count == 2
        assert result.failed_count == 1
        assert result.has_responses is True
        assert result.all_succeeded is False

    @pytest.mark.asyncio
    async def test_query_all_aggregate_timeout(self) -> None:
        """Test query_all respects aggregate timeout."""
        ensemble = DirectorEnsemble(aggregate_timeout=0.05)  # 50ms
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test",
        )

        async def very_slow_complete(*args, **kwargs):
            await asyncio.sleep(10)  # Way over aggregate timeout
            return LLMResponse(content="Too slow", model="test", usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20), latency_ms=10000)

        mock_gateway = MagicMock()
        mock_gateway.director_complete = very_slow_complete

        with patch("cyberred.llm.ensemble.get_gateway", return_value=mock_gateway):
            result = await ensemble.query_all(context)

        # All should fail due to aggregate timeout
        assert result.successful_count == 0
        assert result.failed_count == 3
        assert "Aggregate timeout" in result.responses[DirectorRole.STRATEGIST].error

    def test_synthesize_full_implementation(self) -> None:
        """Test full synthesis implementation (Story 8.5)."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test",
        )
        responses = {
            DirectorRole.STRATEGIST: ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="m1",
                content="Strategic recommendation: Attack port 22",
                latency_ms=100,
                success=True,
            ),
            DirectorRole.ANALYST: ModelResponse(
                role=DirectorRole.ANALYST,
                model_id="m2",
                content="Analysis: SSH service vulnerable",
                latency_ms=200,
                success=True,
            ),
            DirectorRole.CREATIVE: ModelResponse(
                role=DirectorRole.CREATIVE,
                model_id="m3",
                content="Creative: Try SSH tunneling",
                latency_ms=150,
                success=True,
            ),
        }
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
        # Story 8.5 synthesis version
        assert strategy.metadata.get("synthesis_version") == "8.5"
        # Confidence should be positive when all models succeed
        assert strategy.confidence > 0

    def test_synthesize_partial_responses(self) -> None:
        """Test synthesis with partial responses."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="Test",
        )
        responses = {
            DirectorRole.STRATEGIST: ModelResponse(
                role=DirectorRole.STRATEGIST,
                model_id="m1",
                content="Strategy content",
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
                content="Creative content",
                latency_ms=150,
                success=True,
            ),
        }
        query_result = DirectorQueryResult(
            context=context,
            responses=responses,
            total_latency_ms=5000,
            successful_count=2,
            failed_count=1,
        )
        synthesis_input = SynthesisInput(query_result=query_result)

        strategy = ensemble.synthesize(synthesis_input)

        # 2 out of 3 succeeded - confidence is calculated by StrategySynthesizer
        # which uses a weighted formula, not simple ratio
        assert strategy.confidence > 0  # Should be positive
        assert strategy.confidence < 1.0  # But not perfect
        assert len(strategy.contributing_roles) == 2
        assert DirectorRole.ANALYST not in strategy.contributing_roles

    def test_build_prompt_minimal(self) -> None:
        """Test prompt building with minimal context."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-001",
            phase="recon",
            prompt="What next?",
        )
        prompt = ensemble._build_prompt(context)

        assert "eng-001" in prompt
        assert "recon" in prompt
        assert "What next?" in prompt

    def test_build_prompt_full(self) -> None:
        """Test prompt building with full context."""
        ensemble = DirectorEnsemble()
        context = DirectorContext(
            engagement_id="eng-002",
            phase="exploitation",
            prompt="Analyze",
            findings=[{"service": "ssh", "port": 22}],
            constraints={"no_dos": True},
            previous_strategies=["Scanned first"],
        )
        prompt = ensemble._build_prompt(context)

        assert "eng-002" in prompt
        assert "exploitation" in prompt
        assert "Findings" in prompt
        assert "Constraints" in prompt
        assert "Previous Strategies" in prompt
