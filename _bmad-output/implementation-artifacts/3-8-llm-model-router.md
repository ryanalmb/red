# Story 3.8: LLM Model Router

Status: done 

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **automatic model selection based on task complexity**,
So that **simple tasks use fast models and complex tasks use powerful models**.

## Acceptance Criteria

1. **Given** Stories 3.5 and 3.6 are complete (`LLMProvider` ABC and `NIMProvider` exist)
2. **When** I call `router.select_model(task_complexity)`
3. **Then** FAST tier returns model for parsing (output extraction)
4. **And** STANDARD tier returns model for reasoning (agent decisions)
5. **And** COMPLEX tier returns model for exploit chaining (multi-step analysis)
6. **And** router respects model availability (skip unavailable)
7. **And** unit tests verify tier selection logic with 100% coverage

## Tasks / Subtasks

> [!IMPORTANT]
> **TDD REQUIRED:** Each task MUST follow the Red-Green-Refactor cycle. Use phase markers:
> - `[RED]` — Write failing test first (test must fail before implementation)
> - `[GREEN]` — Write minimal code to make test pass
> - `[REFACTOR]` — Clean up code while keeping tests green

### Phase 1: Core Model Router

- [x] Task 1: Create TaskComplexity enum (AC: #2) <!-- id: 0 -->
  - [x] [RED] Write failing test: `test_task_complexity_enum_values`
  - [x] [GREEN] Implement `TaskComplexity` enum in `src/cyberred/llm/router.py`:
    - Values: `FAST`, `STANDARD`, `COMPLEX`
    - Each has `value` as lowercase string for logging
    - Add docstring explaining each tier's use case
  - [x] [REFACTOR] Ensure Enum inherits from `str, Enum` for JSON serialization
  - [x] Verification: Test confirms all enum values exist and serialize correctly

- [x] Task 2: Create ModelConfig dataclass (AC: #3, #4, #5) <!-- id: 1 -->
  - [x] [RED] Write failing test: `test_model_config_dataclass`
  - [x] [GREEN] Implement `ModelConfig` dataclass:
    - Fields: `model_id: str`, `tier: TaskComplexity`, `use_case: str`, `context_window: int = 0`, `priority: int = 0`
    - `__post_init__()` validates `model_id` is non-empty
    - `priority` is for fallback ordering (lower = higher priority)
  - [x] [REFACTOR] Add type hints and docstrings
  - [x] Verification: Test confirms dataclass creation with validation

- [x] Task 3: Create ModelRouter class skeleton (AC: #2, #6) <!-- id: 2 -->
  - [x] [RED] Write failing test: `test_model_router_creation`
  - [x] [GREEN] Implement `ModelRouter` class:
    - Constructor: `__init__(providers: List[NIMProvider], default_tier: TaskComplexity = TaskComplexity.STANDARD)`
    - Store providers, default tier, and build internal model registry
    - Validate at least one provider available
    - Property `available_tiers -> List[TaskComplexity]`
  - [x] [REFACTOR] Use composition pattern for multiple providers
  - [x] Verification: Test confirms ModelRouter instantiation

- [x] Task 4: Implement model registry (AC: #3, #4, #5) <!-- id: 3 -->
  - [x] [RED] Write failing test: `test_model_router_registry_built`
  - [x] [GREEN] Implement internal registry:
    - `_models: Dict[TaskComplexity, List[ModelConfig]]` — models per tier
    - Populate from `NIMProvider.MODELS` dictionary
    - Match models to tiers using predefined mapping
    - Pre-compute available models per tier
  - [x] [REFACTOR] Use class-level DEFAULT_MODELS constant for configurability
  - [x] Verification: Test confirms registry populated correctly

### Phase 2: Model Selection Logic

- [x] Task 5: Implement select_model() (AC: #2, #3, #4, #5) <!-- id: 4 -->
  - [x] [RED] Write failing test: `test_select_model_returns_correct_tier`
  - [x] [GREEN] Implement `select_model(complexity: TaskComplexity) -> NIMProvider`:
    - Look up models configured for given complexity tier
    - Return first available provider for that tier
    - If tier has no available models, fall back to default tier
    - Log selection decision for traceability
  - [x] [REFACTOR] Add structured logging with `structlog`
  - [x] Verification: Test confirms correct model returned for each tier

- [x] Task 6: Implement fallback logic (AC: #6) <!-- id: 5 -->
  - [x] [RED] Write failing test: `test_select_model_fallback_when_unavailable`
  - [x] [GREEN] Implement fallback behavior:
    - If preferred tier unavailable, try next tier in order: FAST → STANDARD → COMPLEX
    - If all tiers unavailable, raise `LLMProviderUnavailable`
    - Log fallback decisions with reason
  - [x] [REFACTOR] Create `_find_available_provider()` helper method
  - [x] Verification: Test confirms fallback to available tier

- [x] Task 7: Implement get_provider_for_tier() (AC: #3, #4, #5) <!-- id: 6 -->
  - [x] [RED] Write failing test: `test_get_provider_for_tier`
  - [x] [GREEN] Implement `get_provider_for_tier(tier: TaskComplexity) -> Optional[NIMProvider]`:
    - Return provider configured for specific tier
    - Return None if tier not available (don't fallback)
    - Check `provider.is_available()` before returning
  - [x] [REFACTOR] Cache tier-to-provider mapping for efficiency
  - [x] Verification: Test confirms provider lookup works correctly

### Phase 3: Availability & Monitoring

- [x] Task 8: Implement availability checks (AC: #6) <!-- id: 7 -->
  - [x] [RED] Write failing test: `test_model_router_respects_availability`
  - [x] [GREEN] Implement availability-aware selection:
    - Call `provider.is_available()` before selection
    - Track provider availability status
    - Method `refresh_availability() -> None` — force recheck all providers
    - Property `available_models -> Dict[TaskComplexity, List[str]]`
  - [x] [REFACTOR] Use lazy evaluation for availability checks
  - [x] Verification: Test confirms unavailable providers skipped

- [x] Task 9: Implement metrics/monitoring (AC: #6) <!-- id: 8 -->
  - [x] [RED] Write failing test: `test_model_router_metrics`
  - [x] [GREEN] Implement monitoring properties:
    - `selection_count -> Dict[TaskComplexity, int]` — selections per tier
    - `fallback_count -> int` — times fallback was used
    - `last_selection -> Optional[Tuple[TaskComplexity, str]]` — last tier/model selected
  - [x] [REFACTOR] Thread-safe counters using `threading.Lock()`
  - [x] Verification: Test confirms all metrics accessible

### Phase 4: Task Complexity Detection (Optional Helper)

- [x] Task 10: Implement complexity heuristics (AC: #2) <!-- id: 9 -->
  - [x] [RED] Write failing test: `test_infer_complexity_from_task`
  - [x] [GREEN] Implement `infer_complexity(task_description: str) -> TaskComplexity`:
    - FAST: keywords like "parse", "extract", "format", "summarize"
    - STANDARD: keywords like "decide", "choose", "reason", "plan"
    - COMPLEX: keywords like "exploit", "chain", "debug", "analyze vulnerability"
    - Default to STANDARD if no keywords match
  - [x] [REFACTOR] Make keyword lists configurable
  - [x] Verification: Test confirms correct inference for sample tasks

### Phase 5: Module Exports & Integration

- [x] Task 11: Export from llm package (AC: all) <!-- id: 10 -->
  - [x] [GREEN] Update `src/cyberred/llm/__init__.py`:
    - Add `ModelRouter` to imports and exports
    - Add `TaskComplexity` to imports and exports
    - Add `ModelConfig` to imports and exports
  - [x] [REFACTOR] Update `__all__` list
  - [x] Verification: Test confirms imports work from package

### Phase 6: Testing & Coverage

- [x] Task 12: Unit tests with comprehensive coverage (AC: #7) <!-- id: 11 -->
  - [x] Create `tests/unit/llm/test_router.py`:
    - Test TaskComplexity enum values
    - Test ModelConfig creation and validation
    - Test ModelRouter creation with providers
    - Test select_model() for all tiers
    - Test fallback behavior when tier unavailable
    - Test availability checking
    - Test metrics tracking
    - Test complexity inference heuristics
  - [x] Run: `pytest tests/unit/llm/test_router.py -v`
  - [x] Verification: All unit tests pass

- [x] Task 13: Verify 100% coverage (AC: #7) <!-- id: 12 -->
  - [x] Run: `pytest --cov=src/cyberred/llm/router --cov-report=term-missing tests/unit/llm/`
  - [x] Verify 100% line coverage on `llm/router.py`
  - [x] Add any missing edge case tests
  - [x] Verification: Coverage report shows 100%

## Dev Notes

### Architecture Context

Per architecture (lines 133-139):

| Tier | Models | Use Case |
|------|--------|----------|
| **FAST** | Nemotron-3-Nano-30B (1M context) | Parsing structured tool output |
| **STANDARD** | Llama Nemotron Super 49B, Nemotron 70B | Agent reasoning, next-action decisions |
| **COMPLEX** | DeepSeek-R1-0528, Qwen3-Coder (256K) | Exploit chaining, debugging failures |

> [!NOTE]
> Director Ensemble uses separate synthesis models (DeepSeek V3.2, Kimi K2, MiniMax M2) — **not from this pool**.

Per architecture (line 131):
> Global rate limit: **30 RPM** shared across swarm.

### Existing LLM Infrastructure (Stories 3.5, 3.6, 3.7)

Located at `src/cyberred/llm/`:
- `provider.py` — `LLMProvider` ABC, `LLMRequest`, `LLMResponse`, `TokenUsage`, `HealthStatus`
- `nim.py` — `NIMProvider` with `MODELS` dict and `for_tier()` factory
- `rate_limiter.py` — `RateLimiter` and `RateLimitedProvider`
- `__init__.py` — Package exports

**NIMProvider.MODELS Already Defined:**
```python
MODELS = {
    "FAST": "mistralai/devstral-2-123b-instruct-2512",
    "STANDARD": "moonshotai/kimi-k2-instruct-0905",
    "COMPLEX": "minimaxai/minimax-m2.1",
}
```

> [!IMPORTANT]
> **Reuse existing `NIMProvider.MODELS` mapping.** The ModelRouter should leverage the existing model definitions in `nim.py`, not duplicate them.

### Exception Handling

Located in `src/cyberred/core/exceptions.py`:
- `LLMProviderUnavailable(LLMError)` — Use when no providers available for any tier

> [!IMPORTANT]
> **Use existing exceptions from `core/exceptions.py`.** Do NOT define new exception classes.

### Previous Story Learnings (Stories 3.6 & 3.7)

From Story 3.6 (NIMProvider):
- Use `structlog` for logging: `log = structlog.get_logger()`
- Thread-safe implementation using `threading.Lock()`
- Export all public types via `__init__.py`
- `NIMProvider.for_tier()` already exists — consider wrapping or reusing

From Story 3.7 (RateLimiter):
- Achieve 100% test coverage on all new modules
- Use `time.monotonic()` for timing measurements
- All dataclasses validated in `__post_init__()`
- Properties for monitoring metrics are essential

### Code Patterns to Follow

**TaskComplexity Enum:**
```python
from enum import Enum

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
```

**ModelRouter Pattern:**
```python
import threading
from typing import Dict, List, Optional, Tuple

import structlog

from cyberred.llm.nim import NIMProvider
from cyberred.core.exceptions import LLMProviderUnavailable

log = structlog.get_logger()

class ModelRouter:
    """Routes requests to appropriate model tier based on task complexity.
    
    Per architecture: 30 RPM shared limit, tiered model selection.
    """
    
    # Fallback order when preferred tier unavailable
    FALLBACK_ORDER = [TaskComplexity.FAST, TaskComplexity.STANDARD, TaskComplexity.COMPLEX]
    
    def __init__(
        self, 
        providers: Dict[TaskComplexity, NIMProvider],
        default_tier: TaskComplexity = TaskComplexity.STANDARD
    ) -> None:
        if not providers:
            raise ValueError("At least one provider required")
            
        self._providers = providers
        self._default_tier = default_tier
        self._lock = threading.Lock()
        
        # Metrics
        self._selection_count: Dict[TaskComplexity, int] = {t: 0 for t in TaskComplexity}
        self._fallback_count = 0
        self._last_selection: Optional[Tuple[TaskComplexity, str]] = None
        
    def select_model(self, complexity: TaskComplexity) -> NIMProvider:
        """Select appropriate provider for task complexity."""
        provider = self.get_provider_for_tier(complexity)
        
        if provider is None:
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
```

### Testing Patterns

**ModelRouter Test Pattern:**
```python
import pytest
from unittest.mock import Mock, MagicMock

from cyberred.llm.router import ModelRouter, TaskComplexity, ModelConfig
from cyberred.llm.nim import NIMProvider

class TestModelRouter:
    def test_select_model_fast_tier(self):
        # Create mock providers
        fast_provider = Mock(spec=NIMProvider)
        fast_provider.is_available.return_value = True
        fast_provider.get_model_name.return_value = "fast-model"
        
        providers = {TaskComplexity.FAST: fast_provider}
        router = ModelRouter(providers=providers)
        
        result = router.select_model(TaskComplexity.FAST)
        assert result == fast_provider
        
    def test_select_model_fallback_on_unavailable(self):
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
        
        result = router.select_model(TaskComplexity.FAST)
        assert result == standard_provider  # Fallback
        assert router.fallback_count == 1
```

### Library Versions

- Python: 3.11+
- structlog: Already in project
- threading: stdlib
- enum: stdlib

### Project Structure Notes

Files to create:
- `src/cyberred/llm/router.py`
- `tests/unit/llm/test_router.py`

Files to modify:
- `src/cyberred/llm/__init__.py` — Add `ModelRouter`, `TaskComplexity`, `ModelConfig` exports

### References

- [Source: docs/3-solutioning/architecture.md#line-133-139] Model tier definitions
- [Source: docs/3-solutioning/architecture.md#line-131] 30 RPM global rate limit
- [Source: _bmad-output/planning-artifacts/epics-stories.md#line-1578-1598] Story 3.8 requirements
- [Source: src/cyberred/llm/nim.py#line-42-46] NIMProvider.MODELS dictionary
- [Source: src/cyberred/llm/nim.py#line-78-90] NIMProvider.for_tier() factory
- [Source: _bmad-output/implementation-artifacts/3-7-llm-rate-limiter.md] Previous story patterns

## Dev Agent Record

### Agent Model Used

gemini-3-pro-preview

### Debug Log References

### Completion Notes List

- Implemented `TaskComplexity` enum for tiered model selection
- Created `ModelConfig` dataclass for model configuration
- Implemented `ModelRouter` class with:
  - Model registry based on `NIMProvider` tiers
  - `select_model()` with automatic fallback logic
  - Availability checking via `is_available()`
  - Metrics tracking (selection counts, fallback counts)
  - Complexity inference helper `infer_complexity()`
  - `available_models` property for tier-to-model mapping (Task 8)
  - `refresh_availability()` method to force recheck (Task 8)
- Exported new components from `cyberred.llm` package
- Achieved 100% test coverage for router module (verified)
- Fixed pre-existing test failure in `test_nim_provider_extended.py` related to package exports
- **Code Review Fixes Applied:**
  - Added missing `available_models` property per AC #6
  - Added missing `refresh_availability()` method per AC #6
  - Added test for secondary fallback path (lines 218-229)
  - Simplified `_build_registry` using `setdefault` pattern
  - Added `# pragma: no cover` to unreachable ValueError handler

### File List

- src/cyberred/llm/router.py
- src/cyberred/llm/__init__.py
- tests/unit/llm/test_router.py
- tests/unit/llm/test_nim_provider_extended.py
