"""LLM Model Router.

Routes requests to appropriate model tier based on task complexity.
Architecture-defined tiers:
- FAST: Parsing structured tool output (30B models)
- STANDARD: Agent reasoning, next-action decisions (70B models)
- COMPLEX: Exploit chaining, debugging failures (DeepSeek/Qwen models)
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
import threading
import structlog

from cyberred.llm.nim import NIMProvider
from cyberred.core.exceptions import LLMProviderUnavailable

log = structlog.get_logger()

class TaskComplexity(str, Enum):
    """Task complexity tiers for model selection.
    
    Per architecture:
    - FAST: Parsing structured tool output
    - STANDARD: Agent reasoning, next-action decisions  
    - COMPLEX: Exploit chaining, debugging failures
    """
    FAST = "fast"
    STANDARD = "standard"
    COMPLEX = "complex"

@dataclass
class ModelConfig:
    """Configuration for a specific model within a tier.
    
    Attributes:
        model_id: Model identifier string.
        tier: Complexity tier this model belongs to.
        use_case: Description of intended use.
        context_window: Max context tokens (0 = unknown).
        priority: Selection priority (lower = higher priority).
    """
    model_id: str
    tier: TaskComplexity
    use_case: str
    context_window: int = 0
    priority: int = 0
    
    def __post_init__(self) -> None:
        """Validate configuration."""
        if not self.model_id:
            raise ValueError("model_id cannot be empty")

class ModelRouter:
    """Routes requests to appropriate model tier based on task complexity.
    
    Per architecture: 30 RPM shared limit, tiered model selection.
    """
    
    # Fallback order when preferred tier unavailable
    FALLBACK_ORDER = [TaskComplexity.FAST, TaskComplexity.STANDARD, TaskComplexity.COMPLEX]
    
    def __init__(
        self,
        providers: Dict[TaskComplexity, NIMProvider],
        default_tier: TaskComplexity = TaskComplexity.STANDARD,
        exclusion_checker: Optional[Callable[[str], bool]] = None,
    ) -> None:
        """Initialize ModelRouter.
        
        Args:
            providers: Dictionary mapping complexity tiers to providers.
            default_tier: Tier to use if specific tier unavailable.
            exclusion_checker: Optional callback to check if model is excluded.
                Returns True if model should be skipped.
            
        Raises:
            ValueError: If no providers are supplied.
        """
        if not providers:
            raise ValueError("At least one provider required")
            
        self._providers = providers
        self._default_tier = default_tier
        self._exclusion_checker = exclusion_checker or (lambda _: False)
        self._lock = threading.Lock()
        
        # Metrics
        self._selection_count: Dict[TaskComplexity, int] = {t: 0 for t in TaskComplexity}
        self._fallback_count = 0
        self._last_selection: Optional[Tuple[TaskComplexity, str]] = None
        
        self._build_registry()
        
    @property
    def selection_count(self) -> Dict[TaskComplexity, int]:
        """Return selection counts per tier."""
        with self._lock:
            return self._selection_count.copy()
            
    @property
    def fallback_count(self) -> int:
        """Return number of fallback events."""
        with self._lock:
            return self._fallback_count
            
    @property
    def last_selection(self) -> Optional[Tuple[TaskComplexity, str]]:
        """Return last selected tier and model."""
        with self._lock:
            return self._last_selection

    @property
    def available_tiers(self) -> List[TaskComplexity]:
        """Return list of configured tiers."""
        return list(self._providers.keys())

    @property
    def available_models(self) -> Dict[TaskComplexity, List[str]]:
        """Return available models per tier.
        
        Only includes models that are currently available.
        """
        result: Dict[TaskComplexity, List[str]] = {}
        for tier, provider in self._providers.items():
            if provider.is_available():
                result[tier] = [provider.get_model_name()]
        return result

    def refresh_availability(self) -> None:
        """Force recheck of all provider availability.
        
        This clears any cached availability state and forces providers
        to be rechecked on next selection.
        """
        for provider in self._providers.values():
            # Trigger availability check by accessing is_available
            # This resets any failure counters or cached state
            _ = provider.is_available()

    def infer_complexity(self, task_description: str) -> TaskComplexity:
        """Infer task complexity from description keywords.
        
        Args:
            task_description: The user's task description.
            
        Returns:
            Inferred TaskComplexity (default: STANDARD).
        """
        desc = task_description.lower()
        
        fast_keywords = ["parse", "extract", "format", "summarize"]
        complex_keywords = ["exploit", "chain", "debug", "analyze vulnerability"]
        
        if any(kw in desc for kw in fast_keywords):
            return TaskComplexity.FAST
            
        if any(kw in desc for kw in complex_keywords):
            return TaskComplexity.COMPLEX
            
        return TaskComplexity.STANDARD

    def select_model(self, complexity: TaskComplexity) -> NIMProvider:
        """Select appropriate provider for task complexity.
        
        Args:
            complexity: The complexity tier of the task.
            
        Returns:
            The selected NIMProvider.
            
        Raises:
            LLMProviderUnavailable: If no provider is available.
        """
        provider = self.get_provider_for_tier(complexity)
        
        provider = self.get_provider_for_tier(complexity)
        
        if provider and self._is_provider_excluded(provider, complexity):
            provider = None

        if provider is None or not provider.is_available():
            # Fallback logic
            provider = self._find_available_provider(complexity)
            
            if provider is None:
                raise LLMProviderUnavailable(
                    provider="ModelRouter",
                    message=f"No available provider for tier {complexity.value}"
                )
            
            with self._lock:
                self._fallback_count += 1
                
        with self._lock:
            self._selection_count[complexity] += 1
            self._last_selection = (complexity, provider.get_model_name())
            
        log.info("model_selected", tier=complexity.value, model=provider.get_model_name())
        return provider

    def get_provider_for_tier(self, tier: TaskComplexity) -> Optional[NIMProvider]:
        """Get provider configured for specific tier.
        
        Args:
            tier: The requested complexity tier.
            
        Returns:
            The configured provider or None if not configured.
        """
        return self._providers.get(tier)

    def _find_available_provider(self, requested_tier: TaskComplexity) -> Optional[NIMProvider]:
        """Find an available provider using fallback logic.
        
        Args:
            requested_tier: The originally requested tier.
            
        Returns:
            An available provider from fallback tiers, or None.
        """
        # Start looking from the requested tier onwards in fallback order
        try:
            start_idx = self.FALLBACK_ORDER.index(requested_tier)
        except ValueError:  # pragma: no cover
            # Should not happen given type safety, but safe default
            start_idx = 0
            
        # Check tiers in fallback order
        for tier in self.FALLBACK_ORDER[start_idx:]:
            provider = self._providers.get(tier)
            if provider and provider.is_available() and not self._is_provider_excluded(provider, tier, log_warning=False):
                log.warning(
                    "model_fallback",
                    requested=requested_tier.value,
                    fallback=tier.value
                )
                return provider
                
        # If still nothing, try tiers BEFORE the requested one (upgrade/downgrade depending on order)
        # The architecture implies we might want to try higher power models if low power fails?
        # Or just stick to the defined order.
        # Let's stick to the defined FALLBACK_ORDER which is FAST -> STANDARD -> COMPLEX
        # If we asked for STANDARD, we check STANDARD -> COMPLEX.
        # If that fails, maybe we should check FAST?
        # Architecture says: "If preferred tier unavailable, try next tier in order: FAST -> STANDARD -> COMPLEX"
        # This implies a global priority order.
        
        for tier in self.FALLBACK_ORDER:
            if tier == requested_tier:
                continue # Already checked
                
            provider = self._providers.get(tier)
            if provider and provider.is_available() and not self._is_provider_excluded(provider, tier, log_warning=False):
                log.warning(
                    "model_fallback",
                    requested=requested_tier.value,
                    fallback=tier.value
                )
                return provider
                
        return None

    def _build_registry(self) -> None:
        """Build internal model registry from providers.
        
        This populates the internal registry used for validation and fallback.
        """
        self._models: Dict[TaskComplexity, List[ModelConfig]] = {}
        
        for tier, provider in self._providers.items():
            model_name = provider.get_model_name()
            # In a real scenario, we might look up more details
            # For now, we create a basic config based on the provider
            config = ModelConfig(
                model_id=model_name,
                tier=tier,
                use_case=f"Model for {tier.value} tier",
                priority=0
            )
            
            self._models.setdefault(tier, []).append(config)

    def _is_provider_excluded(self, provider: NIMProvider, tier: TaskComplexity, log_warning: bool = True) -> bool:
        """Check if provider is currently excluded.
        
        Args:
            provider: The provider to check.
            tier: The tier context for logging.
            log_warning: Whether to log a warning if excluded.
            
        Returns:
            True if excluded, False otherwise.
        """
        model_name = provider.get_model_name()
        if model_name and self._exclusion_checker(model_name):
            if log_warning:
                log.warning(
                    "model_excluded_by_circuit_breaker",
                    model=model_name,
                    tier=tier.value,
                )
            return True
        return False

