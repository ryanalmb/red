"""Unit tests for LLM Model Router."""

import pytest
from enum import Enum
import threading
from unittest.mock import Mock, MagicMock

from cyberred.llm.nim import NIMProvider
from cyberred.core.exceptions import LLMProviderUnavailable

from cyberred.llm.router import (
    TaskComplexity,
    ModelConfig,
    ModelRouter
)

class TestTaskComplexity:
    """Tests for TaskComplexity enum."""

    def test_task_complexity_enum_values(self):
        """Verify TaskComplexity enum values match architecture."""
        # This will fail if TaskComplexity is not imported/defined
        assert TaskComplexity.FAST.value == "fast"
        assert TaskComplexity.STANDARD.value == "standard"
        assert TaskComplexity.COMPLEX.value == "complex"
        
        # Verify inheritance
        assert isinstance(TaskComplexity.FAST, str)
        assert isinstance(TaskComplexity.FAST, Enum)

class TestModelConfig:
    """Tests for ModelConfig dataclass."""

    def test_model_config_dataclass(self):
        """Verify ModelConfig dataclass fields and validation."""
        config = ModelConfig(
            model_id="test-model",
            tier=TaskComplexity.FAST,
            use_case="testing",
            context_window=1000,
            priority=1
        )
        
        assert config.model_id == "test-model"
        assert config.tier == TaskComplexity.FAST
        assert config.use_case == "testing"
        assert config.context_window == 1000
        assert config.priority == 1
        
        # Test default values
        config_defaults = ModelConfig(
            model_id="test-model-2",
            tier=TaskComplexity.STANDARD,
            use_case="testing"
        )
        assert config_defaults.context_window == 0
        assert config_defaults.priority == 0
        
        # Test validation
        with pytest.raises(ValueError, match="model_id cannot be empty"):
            ModelConfig(model_id="", tier=TaskComplexity.FAST, use_case="test")

class TestModelRouter:
    """Tests for ModelRouter class."""

    def test_model_router_creation(self):
        """Verify ModelRouter instantiation and initialization."""
        # Create mock providers
        fast_provider = Mock(spec=NIMProvider)
        standard_provider = Mock(spec=NIMProvider)
        
        providers = {
            TaskComplexity.FAST: fast_provider,
            TaskComplexity.STANDARD: standard_provider
        }
        
        router = ModelRouter(providers=providers, default_tier=TaskComplexity.STANDARD)
        
        assert router.available_tiers == [TaskComplexity.FAST, TaskComplexity.STANDARD]
        
        # Test validation
        with pytest.raises(ValueError, match="At least one provider required"):
            ModelRouter(providers={})

    def test_model_router_registry_built(self):
        """Verify model registry is populated from providers."""
        fast_provider = Mock(spec=NIMProvider)
        fast_provider.get_model_name.return_value = "fast-model-1"
        
        standard_provider = Mock(spec=NIMProvider)
        standard_provider.get_model_name.return_value = "standard-model-1"
        
        providers = {
            TaskComplexity.FAST: fast_provider,
            TaskComplexity.STANDARD: standard_provider
        }
        
        router = ModelRouter(providers=providers)
        
        # Access private registry for verification
        registry = router._models
        
        assert TaskComplexity.FAST in registry
        assert TaskComplexity.STANDARD in registry
        assert len(registry[TaskComplexity.FAST]) > 0
        assert registry[TaskComplexity.FAST][0].model_id == "fast-model-1"
        assert registry[TaskComplexity.STANDARD][0].model_id == "standard-model-1"

    def test_select_model_returns_correct_tier(self):
        """Verify select_model returns provider for requested tier."""
        fast_provider = Mock(spec=NIMProvider)
        fast_provider.is_available.return_value = True
        fast_provider.get_model_name.return_value = "fast-model"
        
        standard_provider = Mock(spec=NIMProvider)
        standard_provider.is_available.return_value = True
        standard_provider.get_model_name.return_value = "standard-model"
        
        providers = {
            TaskComplexity.FAST: fast_provider,
            TaskComplexity.STANDARD: standard_provider
        }
        
        router = ModelRouter(providers=providers)
        
        # Test FAST selection
        result = router.select_model(TaskComplexity.FAST)
        assert result == fast_provider
        
        # Test STANDARD selection
        result = router.select_model(TaskComplexity.STANDARD)
        assert result == standard_provider

    def test_select_model_fallback_when_unavailable(self):
        """Verify select_model falls back to other tiers when preferred is unavailable."""
        fast_provider = Mock(spec=NIMProvider)
        fast_provider.is_available.return_value = False
        
        standard_provider = Mock(spec=NIMProvider)
        standard_provider.is_available.return_value = True
        standard_provider.get_model_name.return_value = "standard-model"
        
        providers = {
            TaskComplexity.FAST: fast_provider,
            TaskComplexity.STANDARD: standard_provider,
        }
        router = ModelRouter(providers=providers)
        
        # Test fallback from FAST to STANDARD
        result = router.select_model(TaskComplexity.FAST)
        assert result == standard_provider
        assert router._fallback_count == 1
        
        # Test unavailable exception when all fail
        standard_provider.is_available.return_value = False
        with pytest.raises(LLMProviderUnavailable):
            router.select_model(TaskComplexity.FAST)

    def test_get_provider_for_tier(self):
        """Verify get_provider_for_tier returns correct provider or None."""
        fast_provider = Mock(spec=NIMProvider)
        
        providers = {
            TaskComplexity.FAST: fast_provider
        }
        
        router = ModelRouter(providers=providers)
        
        # Test existing tier
        assert router.get_provider_for_tier(TaskComplexity.FAST) == fast_provider
        
        # Test missing tier
        assert router.get_provider_for_tier(TaskComplexity.STANDARD) is None

    def test_model_router_respects_availability(self):
        """Verify unavailable providers are skipped during selection."""
        fast_provider = Mock(spec=NIMProvider)
        fast_provider.is_available.return_value = False
        
        standard_provider = Mock(spec=NIMProvider)
        standard_provider.is_available.return_value = True
        standard_provider.get_model_name.return_value = "standard-model"
        
        providers = {
            TaskComplexity.FAST: fast_provider,
            TaskComplexity.STANDARD: standard_provider
        }
        
        router = ModelRouter(providers=providers)
        
        # Should skip FAST and go to STANDARD
        result = router.select_model(TaskComplexity.FAST)
        assert result == standard_provider
        
        # Availability should be checked
        fast_provider.is_available.assert_called()

    def test_model_router_metrics(self):
        """Verify metrics are tracked correctly."""
        fast_provider = Mock(spec=NIMProvider)
        fast_provider.is_available.return_value = True
        fast_provider.get_model_name.return_value = "fast-model"
        
        providers = {
            TaskComplexity.FAST: fast_provider
        }
        
        router = ModelRouter(providers=providers)
        
        # Initial state
        assert router.selection_count[TaskComplexity.FAST] == 0
        assert router.fallback_count == 0
        assert router.last_selection is None
        
        # After selection
        router.select_model(TaskComplexity.FAST)
        assert router.selection_count[TaskComplexity.FAST] == 1
        assert router.fallback_count == 0
        assert router.last_selection == (TaskComplexity.FAST, "fast-model")

    def test_infer_complexity_from_task(self):
        """Verify task complexity inference heuristics."""
        router = ModelRouter(providers={TaskComplexity.STANDARD: Mock(spec=NIMProvider)})
        
        # FAST tasks
        assert router.infer_complexity("Parse the Nmap output") == TaskComplexity.FAST
        assert router.infer_complexity("Extract IP addresses") == TaskComplexity.FAST
        assert router.infer_complexity("Summarize this finding") == TaskComplexity.FAST
        
        # STANDARD tasks
        assert router.infer_complexity("Decide next step") == TaskComplexity.STANDARD
        assert router.infer_complexity("Reason about the target") == TaskComplexity.STANDARD
        assert router.infer_complexity("Plan the attack") == TaskComplexity.STANDARD
        
        # COMPLEX tasks
        assert router.infer_complexity("Exploit the vulnerability") == TaskComplexity.COMPLEX
        assert router.infer_complexity("Chain these exploits together") == TaskComplexity.COMPLEX
        assert router.infer_complexity("Debug why the exploit failed") == TaskComplexity.COMPLEX
        
        # Default fallback
        assert router.infer_complexity("Do something generic") == TaskComplexity.STANDARD

    def test_available_models_property(self):
        """Verify available_models returns only available providers."""
        fast_provider = Mock(spec=NIMProvider)
        fast_provider.is_available.return_value = True
        fast_provider.get_model_name.return_value = "fast-model"
        
        standard_provider = Mock(spec=NIMProvider)
        standard_provider.is_available.return_value = False
        standard_provider.get_model_name.return_value = "standard-model"
        
        complex_provider = Mock(spec=NIMProvider)
        complex_provider.is_available.return_value = True
        complex_provider.get_model_name.return_value = "complex-model"
        
        providers = {
            TaskComplexity.FAST: fast_provider,
            TaskComplexity.STANDARD: standard_provider,
            TaskComplexity.COMPLEX: complex_provider
        }
        
        router = ModelRouter(providers=providers)
        available = router.available_models
        
        # Only FAST and COMPLEX should be in available_models
        assert TaskComplexity.FAST in available
        assert TaskComplexity.STANDARD not in available
        assert TaskComplexity.COMPLEX in available
        assert available[TaskComplexity.FAST] == ["fast-model"]
        assert available[TaskComplexity.COMPLEX] == ["complex-model"]

    def test_refresh_availability(self):
        """Verify refresh_availability checks all providers."""
        fast_provider = Mock(spec=NIMProvider)
        standard_provider = Mock(spec=NIMProvider)
        
        providers = {
            TaskComplexity.FAST: fast_provider,
            TaskComplexity.STANDARD: standard_provider
        }
        
        router = ModelRouter(providers=providers)
        
        # Reset mock call counts
        fast_provider.is_available.reset_mock()
        standard_provider.is_available.reset_mock()
        
        # Call refresh
        router.refresh_availability()
        
        # Both providers should have is_available called
        fast_provider.is_available.assert_called_once()
        standard_provider.is_available.assert_called_once()

    def test_secondary_fallback_to_earlier_tier(self):
        """Test fallback to tier BEFORE requested tier when later tiers unavailable.
        
        This exercises the secondary fallback loop (lines 218-229) that checks
        tiers before the requested tier when all tiers after it are unavailable.
        """
        # FAST available, STANDARD unavailable, request STANDARD
        # Primary fallback: STANDARD -> COMPLEX (COMPLEX not configured)
        # Secondary fallback: should find FAST
        fast_provider = Mock(spec=NIMProvider)
        fast_provider.is_available.return_value = True
        fast_provider.get_model_name.return_value = "fast-model"
        
        standard_provider = Mock(spec=NIMProvider)
        standard_provider.is_available.return_value = False
        
        providers = {
            TaskComplexity.FAST: fast_provider,
            TaskComplexity.STANDARD: standard_provider,
            # Note: COMPLEX is NOT configured, so primary fallback fails
        }
        
        router = ModelRouter(providers=providers)
        
        # Request STANDARD -> unavailable
        # Primary fallback checks STANDARD (unavail), COMPLEX (not configured)
        # Secondary fallback finds FAST
        result = router.select_model(TaskComplexity.STANDARD)
        assert result == fast_provider
        assert router.fallback_count == 1

    def test_router_respects_exclusion_callback(self):
        """Verify router accepts exclusion callback in init."""
        mock_provider = Mock(spec=NIMProvider)
        providers = {TaskComplexity.STANDARD: mock_provider}
        
        # Test default
        router = ModelRouter(providers=providers)
        # Should default to returning False
        assert hasattr(router, "_exclusion_checker")
        assert router._exclusion_checker("test") is False
        
        # Test custom
        checker = Mock(return_value=True)
        # Type check will fail until we update __init__ signature
        router = ModelRouter(providers=providers, exclusion_checker=checker)
        assert router._exclusion_checker("test") is True
        checker.assert_called_with("test")

    def test_select_model_skips_excluded_provider(self):
        """Verify select_model skips providers that are excluded."""
        # Setup provider that is technically "available" but excluded by callback
        provider = Mock(spec=NIMProvider)
        provider.is_available.return_value = True
        provider.get_model_name.return_value = "excluded-model"
        
        providers = {TaskComplexity.STANDARD: provider}
        
        # Exclusion checker returns True for this model
        checker = Mock(return_value=True)
        
        router = ModelRouter(providers=providers, exclusion_checker=checker)
        
        # Should NOT return the excluded provider
        # Since it's the only one, it should raise LLMProviderUnavailable
        # AND check fallback count (though fallback will also fail if no others)
        
        with pytest.raises(LLMProviderUnavailable):
            router.select_model(TaskComplexity.STANDARD)
            
        checker.assert_called_with("excluded-model")
        
        # Verify it tries to log warning (optional but good practice)
        # We can't easily verify logging without structlog capture, skipping for now

    def test_fallback_respects_exclusion(self):
        """Verify fallback logic skips excluded providers."""
        # Setup: FAST excluded, STANDARD available
        fast_provider = Mock(spec=NIMProvider)
        fast_provider.is_available.return_value = True
        fast_provider.get_model_name.return_value = "fast-model"
        
        standard_provider = Mock(spec=NIMProvider)
        standard_provider.is_available.return_value = True
        standard_provider.get_model_name.return_value = "standard-model"
        
        providers = {
            TaskComplexity.FAST: fast_provider,
            TaskComplexity.STANDARD: standard_provider
        }
        
        checker = Mock(side_effect=lambda name: name == "fast-model")
        router = ModelRouter(providers=providers, exclusion_checker=checker)
        
        # Request FAST -> Excluded -> Fallback -> STANDARD
        result = router.select_model(TaskComplexity.FAST)
        
        assert result == standard_provider
        # Verify checker was called for fast-model (initial check)
        # And potentially in fallback loop

