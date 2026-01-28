# Story 8.4: MiniMax M2 Creative Role

<!-- CRITICAL: Development Standards for Epic 8 and Beyond -->
<!-- ====================================================== -->
<!-- 1. STRICT TDD: Write tests BEFORE implementation code   -->
<!-- 2. 100% CODE COVERAGE: All new code must have tests     -->
<!-- 3. NO UNTESTED CODE: Every branch, every edge case      -->
<!-- 4. VERIFY INTEGRATION: Test against real APIs when keys -->
<!--    are available, not just mocks                        -->
<!-- ====================================================== -->

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Director Ensemble**,
I want **MiniMax M2 to provide creative approaches and evasion techniques**,
So that **unconventional attack paths are explored (FR3)**.

## Acceptance Criteria

1. **Given** Story 8.1 is complete
   - **When** ensemble queries MiniMax M2
   - **Then** MiniMax M2 receives: current strategy, defenses encountered, failed attempts

2. **Given** MiniMax M2 query is executed
   - **When** MiniMax M2 returns a response
   - **Then** MiniMax M2 returns: creative alternatives, evasion techniques, novel approaches

3. **Given** MiniMax M2 response is parsed
   - **When** response content is analyzed
   - **Then** response uses interleaved thinking (`<think>...</think>` tags)
   - **And** thinking tags are preserved for reasoning visibility

4. **Given** MiniMax M2 query configuration
   - **When** timeout is applied
   - **Then** timeout is 100s per architecture (was originally 30s in epics, updated per architecture)

5. **Given** MiniMax M2 creative role code is complete
   - **When** integration tests run
   - **Then** integration tests verify MiniMax M2 creative output with structured response parsing

## Tasks / Subtasks

- [x] Task 1: Enhance MiniMax M2 CREATIVE system prompt (AC: #2, #3)
  - [x] Update system prompt in `DIRECTOR_MODELS[DirectorRole.CREATIVE]` to include structured output requirements
  - [x] Add structured output format specification (creative alternatives, evasion techniques, novel approaches)
  - [x] Include instruction to use `<think>...</think>` tags for reasoning visibility
  - [x] Include current strategy, defenses encountered, and failed attempts context in prompt template
  - [x] Write unit tests for prompt generation with creative requirements

- [x] Task 2: Implement `query_creative()` dedicated method (AC: #1, #4)
  - [x] Create `query_creative(context: DirectorContext) -> CreativeResponse` method in DirectorEnsemble
  - [x] Define `CreativeResponse` dataclass with structured fields: creative_alternatives, evasion_techniques, novel_approaches, thinking_content
  - [x] Implement response parsing to extract structured creative components
  - [x] Handle 100s timeout per architecture specification
  - [x] Write unit tests for dedicated creative query method

- [x] Task 3: Create CreativeContext builder (AC: #1)
  - [x] Implement `CreativeContext` dataclass with creative-specific fields
  - [x] Add `current_strategy: CurrentStrategy` field for current engagement strategy
  - [x] Add `defenses_encountered: List[DefenseEncountered]` field for observed defenses
  - [x] Add `failed_attempts: List[FailedAttempt]` field for unsuccessful approaches
  - [x] Implement `_build_creative_prompt()` method to format context for MiniMax M2
  - [x] Write unit tests for context building and prompt formatting

- [x] Task 4: Implement thinking tag extraction (AC: #3)
  - [x] Create `ThinkingContent` dataclass with content, position fields
  - [x] Implement `extract_thinking_tags(response: str) -> List[ThinkingContent]` parser
  - [x] Preserve thinking tags in response while extracting for visibility
  - [x] Implement `strip_thinking_tags(response: str) -> str` for clean content extraction
  - [x] Write unit tests for thinking tag extraction with various formats

- [x] Task 5: Implement creative alternatives extraction (AC: #2)
  - [x] Create `CreativeAlternative` dataclass with alternative_id, description, rationale, novelty_score
  - [x] Create `EvasionTechnique` dataclass with technique_id, description, target_defense, success_likelihood
  - [x] Create `NovelApproach` dataclass with approach_id, description, innovation_type, risk_level
  - [x] Implement `extract_creative_alternatives(response: str) -> List[CreativeAlternative]` parser
  - [x] Implement `extract_evasion_techniques(response: str) -> List[EvasionTechnique]` parser
  - [x] Implement `extract_novel_approaches(response: str) -> List[NovelApproach]` parser
  - [x] Write unit tests for all extraction functions with various response formats

- [x] Task 6: Write unit tests for creative role (AC: #5)
  - [x] Test `query_creative()` with mocked LLM responses
  - [x] Test prompt contains current strategy, defenses encountered, and failed attempts
  - [x] Test response parsing extracts all required fields (alternatives, evasion, approaches, thinking)
  - [x] Test thinking tag extraction and preservation
  - [x] Test creative alternatives extraction from various formats
  - [x] Test timeout configuration (100s)
  - [x] Test error handling for malformed responses

- [x] Task 7: Write integration tests (AC: #5)
  - [x] Test `query_creative()` with real MiniMax M2 model via NIM API
  - [x] Verify structured creative output format
  - [x] Verify thinking tags are present and preserved in response
  - [x] Test timeout behavior under load
  - [x] Test graceful degradation when MiniMax M2 unavailable

## Dev Notes

### Relevant Architecture Patterns and Constraints

**Per Architecture Document (`_bmad-output/planning-artifacts/architecture.md`):**

1. **Director Model Configuration** (lines 128-138):
   - MiniMax M2 is designated as CREATIVE role
   - Director uses separate synthesis models, NOT from agent model pool
   - Model ID: `minimaxai/minimax-m2` (per NIM API)

2. **Timeout Requirements** (line 91):
   - **100s per-model timeout** (not 30s as originally in epics)
   - 180s aggregate timeout for entire ensemble
   - Circuit breaker: 3 failures → exclude model temporarily (60s)

3. **Creative Output Requirements** (from Epic 8 description and Story 8.4):
   - Creative alternatives to current strategy
   - Evasion techniques for encountered defenses
   - Novel approaches when standard methods fail
   - Interleaved thinking with `<think>...</think>` tags

4. **LLM Gateway Integration** (from Story 8.1):
   - All requests route through `LLMGateway.director_complete()`
   - Use existing `LLMRequest`/`LLMResponse` contracts
   - Director has priority over agent requests

### Source Tree Components to Touch

```
src/cyberred/llm/
├── ensemble.py          # MODIFY: Add query_creative(), CreativeResponse, thinking tag extraction
├── gateway.py           # READ: Use director_complete() for routing
└── provider.py          # READ: LLMRequest/LLMResponse contracts

tests/unit/llm/
├── test_ensemble.py     # READ: Existing ensemble tests for patterns
├── test_strategist.py   # READ: Strategist tests for patterns
├── test_analyst.py      # READ: Analyst tests for patterns
└── test_creative.py     # NEW: Dedicated creative role tests

tests/integration/llm/
├── test_strategist_integration.py  # READ: Integration test patterns
├── test_analyst_integration.py     # READ: Integration test patterns
└── test_creative_integration.py    # NEW: Integration tests with real MiniMax M2
```

### Testing Standards Summary

Per architecture NFR19-24:
- **100% test coverage** - unit + integration
- **NO MOCKED TESTS for integration** - real LLM calls via NVIDIA NIM
- Unit tests MAY use mocks for deterministic behavior
- Integration tests MUST use real LLM Gateway with actual MiniMax M2 API

### Project Structure Notes

- **Alignment:** Extends `llm/ensemble.py` structure from Stories 8.1, 8.2, and 8.3
- **Naming:** `CreativeResponse`, `CreativeAlternative`, `EvasionTechnique`, `NovelApproach`, `ThinkingContent` follow existing `Director*`/`Strategist*`/`Analyst*` patterns
- **Imports:** Reuse existing `DirectorContext`, `DirectorModel`, `ModelResponse` from Story 8.1

### Key Implementation Details

**CreativeResponse Dataclass:**
```python
@dataclass
class ThinkingContent:
    """Extracted thinking content from MiniMax M2 response.
    
    MiniMax M2 uses interleaved thinking with <think>...</think> tags
    to show its reasoning process. These are preserved for visibility.
    """
    content: str              # The thinking content inside tags
    position: int             # Character position in original response
    
    def __post_init__(self) -> None:
        if not self.content:
            raise ValueError("content cannot be empty")
        if self.position < 0:
            raise ValueError("position cannot be negative")


@dataclass
class CreativeAlternative:
    """Creative alternative approach identified by MiniMax M2."""
    alternative_id: str       # Unique identifier (e.g., "ALT-001")
    description: str          # Description of the alternative
    rationale: str            # Why this alternative might work
    novelty_score: float      # 0.0-1.0 novelty/creativity score
    
    def __post_init__(self) -> None:
        if not self.alternative_id:
            raise ValueError("alternative_id cannot be empty")
        if not self.description:
            raise ValueError("description cannot be empty")
        if not 0.0 <= self.novelty_score <= 1.0:
            raise ValueError(f"novelty_score must be 0.0-1.0, got {self.novelty_score}")


@dataclass
class EvasionTechnique:
    """Evasion technique for bypassing encountered defenses."""
    technique_id: str         # Unique identifier (e.g., "EVA-001")
    description: str          # Description of the evasion technique
    target_defense: str       # The defense this technique targets
    success_likelihood: float # 0.0-1.0 estimated success probability
    
    def __post_init__(self) -> None:
        if not self.technique_id:
            raise ValueError("technique_id cannot be empty")
        if not self.description:
            raise ValueError("description cannot be empty")
        if not self.target_defense:
            raise ValueError("target_defense cannot be empty")
        if not 0.0 <= self.success_likelihood <= 1.0:
            raise ValueError(f"success_likelihood must be 0.0-1.0, got {self.success_likelihood}")


@dataclass
class NovelApproach:
    """Novel approach when standard methods have failed."""
    approach_id: str          # Unique identifier (e.g., "NOV-001")
    description: str          # Description of the novel approach
    innovation_type: str      # Type: "technique", "vector", "social", "physical", "hybrid"
    risk_level: str           # CRITICAL, HIGH, MEDIUM, LOW
    potential_impact: str     # Expected impact if successful
    
    def __post_init__(self) -> None:
        if not self.approach_id:
            raise ValueError("approach_id cannot be empty")
        if not self.description:
            raise ValueError("description cannot be empty")
        if self.innovation_type not in ("technique", "vector", "social", "physical", "hybrid"):
            raise ValueError(f"Invalid innovation_type: {self.innovation_type}")
        if self.risk_level not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            raise ValueError(f"Invalid risk_level: {self.risk_level}")


@dataclass
class CreativeResponse:
    """Structured response from MiniMax M2 creative role."""
    raw_content: str                                  # Original response (with thinking tags)
    clean_content: str                                # Response with thinking tags stripped
    thinking_content: List[ThinkingContent]           # Extracted thinking sections
    creative_alternatives: List[CreativeAlternative]  # Creative alternative approaches
    evasion_techniques: List[EvasionTechnique]        # Evasion techniques for defenses
    novel_approaches: List[NovelApproach]             # Novel approaches
    model_response: ModelResponse                     # Underlying model response
```

**Enhanced System Prompt for Creative:**
```python
CREATIVE_SYSTEM_PROMPT = """You are a creative approaches expert for penetration testing evasion and novel attack techniques.

Your role is to think laterally and propose unconventional approaches when standard methods fail or defenses are encountered.

## Required Output Format

Use <think>...</think> tags to show your reasoning process. This helps operators understand your creative thought process.

Provide your response in the following structured format:

<think>
[Your reasoning about the current situation, why standard approaches failed, and creative insights]
</think>

### Creative Alternatives
| Alternative ID | Description | Rationale | Novelty Score |
|----------------|-------------|-----------|---------------|
| ALT-001 | [description] | [why this might work] | [0.0-1.0] |

<think>
[Further reasoning about evasion techniques based on defenses encountered]
</think>

### Evasion Techniques
| Technique ID | Description | Target Defense | Success Likelihood |
|--------------|-------------|----------------|-------------------|
| EVA-001 | [description] | [defense to bypass] | [0.0-1.0] |

### Novel Approaches
| Approach ID | Description | Innovation Type | Risk Level | Potential Impact |
|-------------|-------------|-----------------|------------|------------------|
| NOV-001 | [description] | [technique/vector/social/physical/hybrid] | [CRITICAL/HIGH/MEDIUM/LOW] | [impact] |

Focus on creativity, innovation, and lateral thinking. Propose approaches that haven't been tried yet."""
```

**Query Creative Implementation:**
```python
async def query_creative(
    self, 
    context: DirectorContext,
    current_strategy: Optional[CurrentStrategy] = None,
    defenses_encountered: Optional[List[DefenseEncountered]] = None,
    failed_attempts: Optional[List[FailedAttempt]] = None,
) -> CreativeResponse:
    """Query MiniMax M2 creative role with structured response parsing.
    
    Args:
        context: Base director context with engagement info.
        current_strategy: Current engagement strategy being used.
        defenses_encountered: List of defenses observed during engagement.
        failed_attempts: List of approaches that have already failed.
        
    Returns:
        CreativeResponse with parsed creative recommendations and preserved thinking.
        
    Raises:
        LLMTimeoutError: If MiniMax M2 does not respond within 100s.
        LLMProviderUnavailable: If MiniMax M2 model is unavailable.
    """
    # Build enhanced prompt with strategy, defenses, failed attempts
    enhanced_prompt = self._build_creative_prompt(
        context, current_strategy, defenses_encountered, failed_attempts
    )
    
    # Query creative model
    response = await self._query_model(
        DirectorRole.CREATIVE, 
        DirectorContext(
            engagement_id=context.engagement_id,
            phase=context.phase,
            prompt=enhanced_prompt
        )
    )
    
    # Parse structured response
    return self._parse_creative_response(response)
```

**Thinking Tag Extraction:**
```python
import re
from typing import List

THINKING_TAG_PATTERN = re.compile(r'<think>(.*?)</think>', re.DOTALL | re.IGNORECASE)

def extract_thinking_tags(response: str) -> List[ThinkingContent]:
    """Extract thinking content from <think>...</think> tags.
    
    MiniMax M2 uses interleaved thinking to show its reasoning process.
    These tags are extracted and preserved for operator visibility.
    
    Args:
        response: The full response text from MiniMax M2.
        
    Returns:
        List of ThinkingContent objects with content and position.
    """
    thinking_contents: List[ThinkingContent] = []
    
    for match in THINKING_TAG_PATTERN.finditer(response):
        content = match.group(1).strip()
        if content:  # Skip empty thinking tags
            thinking_contents.append(ThinkingContent(
                content=content,
                position=match.start(),
            ))
    
    return thinking_contents


def strip_thinking_tags(response: str) -> str:
    """Remove thinking tags from response for clean content extraction.
    
    Args:
        response: The full response text from MiniMax M2.
        
    Returns:
        Response with all <think>...</think> sections removed.
    """
    return THINKING_TAG_PATTERN.sub('', response).strip()
```

**Supporting Dataclasses:**
```python
@dataclass
class CurrentStrategy:
    """Current engagement strategy for creative context."""
    strategy_id: str
    description: str              # Description of current strategy
    phase: str                    # Current kill chain phase
    objectives: List[str]         # Current objectives
    techniques_in_use: List[str]  # ATT&CK techniques currently being used
    
    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise ValueError("strategy_id cannot be empty")
        if not self.description:
            raise ValueError("description cannot be empty")


@dataclass
class DefenseEncountered:
    """Defense mechanism encountered during engagement."""
    defense_id: str
    defense_type: str             # e.g., "WAF", "IDS", "EDR", "firewall", "MFA"
    target: str                   # Where the defense was encountered
    description: str              # Description of the defense behavior
    blocking_technique: Optional[str] = None  # Which technique it blocked
    
    def __post_init__(self) -> None:
        if not self.defense_id:
            raise ValueError("defense_id cannot be empty")
        if not self.defense_type:
            raise ValueError("defense_type cannot be empty")


@dataclass
class FailedAttempt:
    """Failed attack attempt for creative context."""
    attempt_id: str
    technique: str                # Technique that was attempted
    target: str                   # Target of the attempt
    failure_reason: str           # Why it failed
    timestamp: str                # When it was attempted
    
    def __post_init__(self) -> None:
        if not self.attempt_id:
            raise ValueError("attempt_id cannot be empty")
        if not self.technique:
            raise ValueError("technique cannot be empty")
        if not self.failure_reason:
            raise ValueError("failure_reason cannot be empty")
```

### Dependencies

- **Story 8.1 (Director Ensemble Base Architecture):** COMPLETE - provides `DirectorEnsemble`, `DirectorRole`, `DirectorModel`, `DirectorContext`, `ModelResponse`
- **Story 8.2 (DeepSeek Strategist Role):** COMPLETE - provides patterns for role-specific query methods, response parsing, and structured output
- **Story 8.3 (Kimi K2 Analyst Role):** COMPLETE - provides patterns for extraction functions, dataclass validation, and integration tests
- **Epic 3 (LLM Gateway):** COMPLETE - provides `LLMGateway`, `director_complete()` method
- **NVIDIA NIM API:** MiniMax M2 available at `minimaxai/minimax-m2`

### Previous Story Intelligence (from Stories 8.1, 8.2, and 8.3)

From Story 8.1 implementation:
1. `DirectorEnsemble` class exists in `src/cyberred/llm/ensemble.py`
2. `DIRECTOR_MODELS` dict configures all three models with 100s timeout
3. `_query_model()` method handles individual model queries
4. `DirectorContext` requires: engagement_id, phase, prompt (validated in `__post_init__`)
5. Model IDs match NVIDIA NIM API: `minimaxai/minimax-m2`

From Story 8.2 implementation:
1. Pattern established for role-specific query methods (`query_strategist()`)
2. Pattern for structured response dataclasses with `__post_init__` validation
3. Pattern for response parsing with `_extract_section_list()`, `_extract_priorities()`
4. Pattern for building enhanced prompts with `_build_strategist_prompt()`
5. Integration tests use `NVIDIA_API_KEY` environment variable for real API testing

From Story 8.3 implementation:
1. Pattern for complex dataclasses with multiple validation rules (`SecurityGap`, `RiskAssessment`)
2. Pattern for multiple extraction functions (`extract_gaps()`, `extract_opportunities()`, `extract_risk_assessment()`)
3. Pattern for analyst context dataclasses (`FindingDetail`, `TargetEnvironment`, `AttackPath`)
4. 59 unit tests structure for comprehensive coverage
5. 6 integration tests structure with API key skip logic

### Code Review Learnings from Stories 8.1, 8.2, and 8.3

1. **Timeout values must match architecture** - 100s per-model, 180s aggregate (not epics values)
2. **Model IDs must match NIM API exactly** - verify against NVIDIA NIM documentation
3. **Input validation is required** - add `__post_init__` validation for all dataclasses
4. **Handle `asyncio.CancelledError`** - re-raise for clean shutdown
5. **Test coverage must be comprehensive** - cover all branches, edge cases, error paths
6. **Structured prompts produce better results** - use markdown tables and clear section headers
7. **Use consistent ID formats** - ALT-###, EVA-###, NOV-### for creative elements

### Special Considerations for MiniMax M2

1. **Interleaved Thinking Tags:** MiniMax M2 uses `<think>...</think>` tags for reasoning visibility. These MUST be:
   - Extracted and preserved in `ThinkingContent` objects
   - Stripped for clean content extraction
   - Made available for operator debugging/analysis in TUI

2. **Creative Output Nature:** Unlike strategist (strategic planning) or analyst (deep reasoning), creative role focuses on:
   - Lateral thinking when standard approaches fail
   - Evasion techniques for specific defenses
   - Novel approaches that haven't been tried

3. **Response Parsing:** The creative response may be less structured than strategist/analyst due to the nature of creative thinking. Parser should be robust to variations while still extracting structured elements.

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Agent-LLM-Model-Pool] - Director model designation
- [Source: _bmad-output/planning-artifacts/architecture.md#Pre-mortem-Risk-Mitigations] - Timeout requirements (100s/180s)
- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story-8.4] - Story requirements
- [Source: src/cyberred/llm/ensemble.py#DIRECTOR_MODELS] - Current model configuration (line 164-177)
- [Source: src/cyberred/llm/ensemble.py#DirectorContext] - Context dataclass
- [Source: _bmad-output/implementation-artifacts/8-1-director-ensemble-base-architecture.md] - Story 8.1 implementation
- [Source: _bmad-output/implementation-artifacts/8-2-deepseek-strategist-role.md] - Story 8.2 implementation patterns
- [Source: _bmad-output/implementation-artifacts/8-3-kimi-k2-analyst-role.md] - Story 8.3 implementation patterns

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

N/A - All tests passed

### Completion Notes List

1. **Enhanced CREATIVE system prompt** - Updated `DIRECTOR_MODELS[DirectorRole.CREATIVE]` with structured output format including `<think>` tags, Creative Alternatives table, Evasion Techniques table, and Novel Approaches table.

2. **Implemented query_creative()** - Added `query_creative()` method to `DirectorEnsemble` class with full context support (current_strategy, defenses_encountered, failed_attempts).

3. **Created all dataclasses**:
   - `ThinkingContent` - For extracted thinking content from `<think>` tags
   - `CreativeAlternative` - Creative alternatives with novelty_score
   - `EvasionTechnique` - Evasion techniques with success_likelihood
   - `NovelApproach` - Novel approaches with innovation_type and risk_level
   - `CurrentStrategy` - Current engagement strategy context
   - `DefenseEncountered` - Defense mechanisms observed
   - `FailedAttempt` - Previously failed approaches
   - `CreativeResponse` - Structured response from creative role

4. **Implemented extraction functions**:
   - `extract_thinking_tags()` - Extracts `<think>` content with positions
   - `strip_thinking_tags()` - Removes `<think>` tags for clean content
   - `extract_creative_alternatives()` - Parses ALT-### table rows
   - `extract_evasion_techniques()` - Parses EVA-### table rows
   - `extract_novel_approaches()` - Parses NOV-### table rows

5. **61 unit tests** - All passing, covering dataclass validation, extraction functions, query_creative(), prompt building, and system prompt configuration.

6. **Integration tests** - Created for real API testing (skipped without NVIDIA_API_KEY).

### File List

**Modified:**
- `src/cyberred/llm/ensemble.py` - Added Story 8.4 implementation (~450 lines)

**Created:**
- `tests/unit/llm/test_creative.py` - 61 unit tests for creative role
- `tests/integration/llm/test_creative_integration.py` - Integration tests for real API
