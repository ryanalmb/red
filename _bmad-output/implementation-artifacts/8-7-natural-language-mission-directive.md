# Story 8.7: Natural Language Mission Directive

Status: review

## Story

As an **operator**,
I want **to issue mission directives in natural language**,
So that **I can guide the engagement without technical commands (FR1)**.

## Acceptance Criteria

1. **Given** Story 8.1 (Director Ensemble Base Architecture) is complete
   - **When** I type "Focus on web application vulnerabilities, skip network infrastructure"
   - **Then** Director Ensemble interprets the directive

2. **Given** a natural language directive is interpreted
   - **When** the Director processes the directive
   - **Then** Director translates into agent task priorities
   - **And** the translation includes specific focus areas, exclusions, and priority ordering

3. **Given** a directive is processed
   - **When** the directive is logged
   - **Then** directive is logged to audit trail via `audit:stream`
   - **And** the log includes timestamp, engagement_id, raw directive text, and parsed interpretation

4. **Given** a valid directive is interpreted
   - **When** the strategy is updated
   - **Then** agents receive updated strategy via `strategies:{engagement_id}` channel
   - **And** the strategy includes the directive's influence on objectives and actions

5. **Given** a directive that would violate scope rules
   - **When** the directive is validated
   - **Then** validation fails and directive is rejected
   - **And** operator receives clear error message about scope violation
   - **And** hard-gate scope rules are NEVER overridden

6. **Given** the DirectorEnsemble is available
   - **When** a directive is submitted
   - **Then** integration tests verify natural language interpretation
   - **And** tests cover various directive types (focus, exclude, prioritize, pivot)

## Tasks / Subtasks

- [x] Task 1: Create `orchestration/directive.py` module (AC: 1, 2)
  - [x] 1.1: Define `MissionDirective` dataclass with raw_text, engagement_id, timestamp
  - [x] 1.2: Define `ParsedDirective` dataclass with focus_areas, exclusions, priorities, pivot_reason
  - [x] 1.3: Define `DirectiveResult` dataclass with success, strategy_update, error_message
  - [x] 1.4: Implement `DirectiveInterpreter` class with `interpret()` method using DirectorEnsemble
  - [x] 1.5: Implement directive type detection (focus, exclude, prioritize, pivot, abort)

- [x] Task 2: Implement scope validation for directives (AC: 5)
  - [x] 2.1: Add `_validate_against_scope()` method to check directive doesn't override scope
  - [x] 2.2: Implement exclusion validation (cannot exclude in-scope required targets)
  - [x] 2.3: Implement focus validation (focus areas must be within scope)
  - [x] 2.4: Add clear error messages for scope violations

- [x] Task 3: Implement audit trail logging (AC: 3)
  - [x] 3.1: Add `_log_directive_to_audit()` method using EventBus.audit()
  - [x] 3.2: Include all required fields: timestamp, engagement_id, raw_text, parsed_interpretation
  - [x] 3.3: Log both successful and failed directive attempts

- [x] Task 4: Implement strategy publication (AC: 4)
  - [x] 4.1: Add `_publish_strategy_update()` method using EventBus.publish()
  - [x] 4.2: Integrate with `SynthesizedStrategy.to_json()` for Redis publication
  - [x] 4.3: Include directive influence in strategy metadata

- [x] Task 5: Write unit tests (AC: 1-5)
  - [x] 5.1: Test `MissionDirective` and `ParsedDirective` dataclass validation
  - [x] 5.2: Test `DirectiveInterpreter.interpret()` with mocked DirectorEnsemble
  - [x] 5.3: Test scope validation blocks scope-violating directives
  - [x] 5.4: Test audit logging format and completeness
  - [x] 5.5: Test strategy publication format

- [x] Task 6: Write integration tests (AC: 6)
  - [x] 6.1: Test end-to-end directive interpretation with real LLM (if available) or mock
  - [x] 6.2: Test "focus on X" directive type
  - [x] 6.3: Test "skip/exclude Y" directive type
  - [x] 6.4: Test "prioritize Z" directive type
  - [x] 6.5: Test "pivot to W" directive type
  - [x] 6.6: Test scope violation rejection

## Dev Notes

### Relevant Architecture Patterns and Constraints

1. **Director Ensemble Integration (Story 8.1)**
   - Use `DirectorEnsemble` from `cyberred/llm/ensemble.py` for NL interpretation
   - Leverage existing `DirectorContext` for providing engagement context
   - Use `SynthesizedStrategy` output format for consistency

2. **Event Bus Integration (Story 3.3, 3.4)**
   - Audit logging via `EventBus.audit()` to `audit:stream`
   - Strategy publication via `EventBus.publish()` to `strategies:{engagement_id}`
   - Channel patterns already registered in `CHANNEL_PATTERNS`

3. **Scope Validation (Story 1.8)**
   - Hard-gate scope validation is MANDATORY - directives cannot override
   - Use `ScopeValidator` from `cyberred/tools/scope.py` for validation
   - Fail-closed on any scope violation

4. **Existing Strategy Pattern (Story 8.5)**
   - Follow `SynthesizedStrategy` structure from `llm/ensemble.py`
   - Use `to_json()` method for Redis publication
   - Include `objectives`, `actions`, `rationale`, `confidence`

### Source Tree Components to Touch

```
src/cyberred/orchestration/
├── __init__.py              # Add DirectiveInterpreter export
├── directive.py             # NEW: Main directive module
└── emergence/
    └── strategy.py          # Reference for strategy publication pattern

src/cyberred/llm/
└── ensemble.py              # DirectorEnsemble integration point

src/cyberred/tools/
└── scope.py                 # ScopeValidator for directive validation

tests/unit/orchestration/
└── test_directive.py        # NEW: Unit tests

tests/integration/orchestration/
└── test_directive_integration.py  # NEW: Integration tests
```

### Key Implementation Details

#### DirectiveInterpreter Class Structure

```python
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
import time

import structlog

from cyberred.llm.ensemble import DirectorEnsemble, DirectorContext, SynthesizedStrategy
from cyberred.core.events import EventBus
from cyberred.tools.scope import ScopeValidator
from cyberred.core.exceptions import ScopeViolationError

log = structlog.get_logger()


class DirectiveType(Enum):
    """Types of mission directives."""
    FOCUS = "focus"           # Focus on specific areas
    EXCLUDE = "exclude"       # Skip/exclude targets or techniques
    PRIORITIZE = "prioritize" # Change priority ordering
    PIVOT = "pivot"           # Change attack direction
    ABORT = "abort"           # Abort specific actions


@dataclass
class MissionDirective:
    """Raw mission directive from operator.
    
    Attributes:
        raw_text: Original natural language directive.
        engagement_id: Current engagement identifier.
        timestamp: When directive was issued.
        operator_id: Optional operator identifier.
    """
    raw_text: str
    engagement_id: str
    timestamp: float = field(default_factory=time.time)
    operator_id: Optional[str] = None
    
    def __post_init__(self) -> None:
        if not self.raw_text or not self.raw_text.strip():
            raise ValueError("raw_text cannot be empty")
        if not self.engagement_id or not self.engagement_id.strip():
            raise ValueError("engagement_id cannot be empty")


@dataclass
class ParsedDirective:
    """Interpreted directive with structured components.
    
    Attributes:
        directive_type: Type of directive (focus, exclude, prioritize, pivot).
        focus_areas: Areas to focus on (e.g., ["web applications", "SQL injection"]).
        exclusions: Areas to exclude (e.g., ["network infrastructure", "DNS"]).
        priorities: Priority ordering (e.g., ["critical vulns", "high vulns"]).
        pivot_reason: Reason for pivot if directive_type is PIVOT.
        confidence: Confidence in interpretation (0.0-1.0).
        raw_interpretation: Raw LLM interpretation text.
    """
    directive_type: DirectiveType
    focus_areas: List[str] = field(default_factory=list)
    exclusions: List[str] = field(default_factory=list)
    priorities: List[str] = field(default_factory=list)
    pivot_reason: Optional[str] = None
    confidence: float = 0.0
    raw_interpretation: str = ""


@dataclass
class DirectiveResult:
    """Result of directive processing.
    
    Attributes:
        success: Whether directive was successfully processed.
        parsed: Parsed directive (if successful).
        strategy_update: Updated strategy (if successful).
        error_message: Error message (if failed).
        scope_violation: Whether failure was due to scope violation.
    """
    success: bool
    parsed: Optional[ParsedDirective] = None
    strategy_update: Optional[SynthesizedStrategy] = None
    error_message: Optional[str] = None
    scope_violation: bool = False


class DirectiveInterpreter:
    """Interprets natural language mission directives.
    
    Uses DirectorEnsemble to parse operator directives into structured
    task priorities while enforcing scope validation.
    
    Example:
        interpreter = DirectiveInterpreter(
            ensemble=ensemble,
            event_bus=event_bus,
            scope_validator=scope_validator,
        )
        result = await interpreter.interpret(directive)
    """
    
    # System prompt for directive interpretation
    DIRECTIVE_SYSTEM_PROMPT = '''You are interpreting operator mission directives for a penetration testing engagement.

Parse the directive into structured components:
1. Directive Type: focus, exclude, prioritize, pivot, or abort
2. Focus Areas: Specific targets, vulnerabilities, or techniques to focus on
3. Exclusions: Targets, vulnerabilities, or techniques to skip
4. Priorities: How to order/prioritize work
5. Pivot Reason: If pivoting, why

Output JSON format:
{
    "directive_type": "focus|exclude|prioritize|pivot|abort",
    "focus_areas": ["area1", "area2"],
    "exclusions": ["exclusion1", "exclusion2"],
    "priorities": ["priority1", "priority2"],
    "pivot_reason": "reason if pivot",
    "confidence": 0.0-1.0
}'''

    def __init__(
        self,
        ensemble: DirectorEnsemble,
        event_bus: EventBus,
        scope_validator: Optional[ScopeValidator] = None,
        engagement_id: Optional[str] = None,
    ) -> None:
        """Initialize DirectiveInterpreter.
        
        Args:
            ensemble: DirectorEnsemble for NL interpretation.
            event_bus: EventBus for audit logging and strategy publication.
            scope_validator: Optional ScopeValidator for directive validation.
            engagement_id: Default engagement ID if not in directive.
        """
        self._ensemble = ensemble
        self._event_bus = event_bus
        self._scope_validator = scope_validator
        self._engagement_id = engagement_id
        self._log = log.bind(component="directive_interpreter")
    
    async def interpret(
        self,
        directive: MissionDirective,
        current_context: Optional[DirectorContext] = None,
    ) -> DirectiveResult:
        """Interpret a natural language mission directive.
        
        Args:
            directive: The mission directive to interpret.
            current_context: Optional current engagement context.
            
        Returns:
            DirectiveResult with parsed directive and strategy update.
        """
        # Implementation follows in actual code
        pass
    
    async def _validate_against_scope(
        self,
        parsed: ParsedDirective,
    ) -> Optional[str]:
        """Validate parsed directive against scope rules.
        
        Returns error message if validation fails, None if OK.
        """
        # Implementation validates focus_areas are in scope
        # and exclusions don't override required scope targets
        pass
    
    async def _log_directive_to_audit(
        self,
        directive: MissionDirective,
        result: DirectiveResult,
    ) -> None:
        """Log directive to audit trail."""
        await self._event_bus.audit({
            "type": "mission_directive",
            "engagement_id": directive.engagement_id,
            "raw_text": directive.raw_text,
            "operator_id": directive.operator_id,
            "success": result.success,
            "parsed": {
                "directive_type": result.parsed.directive_type.value if result.parsed else None,
                "focus_areas": result.parsed.focus_areas if result.parsed else [],
                "exclusions": result.parsed.exclusions if result.parsed else [],
            } if result.parsed else None,
            "error": result.error_message,
            "scope_violation": result.scope_violation,
            "timestamp": directive.timestamp,
        })
    
    async def _publish_strategy_update(
        self,
        engagement_id: str,
        strategy: SynthesizedStrategy,
        directive: MissionDirective,
    ) -> int:
        """Publish strategy update to agents."""
        # Add directive metadata to strategy
        strategy.metadata["directive"] = {
            "raw_text": directive.raw_text,
            "timestamp": directive.timestamp,
        }
        
        channel = f"strategies:{engagement_id}"
        return await self._event_bus.publish(channel, strategy.to_json())
```

### Testing Requirements

1. **Unit Tests** (`tests/unit/orchestration/test_directive.py`):
   - Test dataclass validation (empty strings, required fields)
   - Test `DirectiveType` enum values
   - Test `DirectiveInterpreter` with mocked `DirectorEnsemble`
   - Test scope validation logic
   - Test audit log format

2. **Integration Tests** (`tests/integration/orchestration/test_directive_integration.py`):
   - Test full interpret flow with mocked LLM responses
   - Test various directive types (focus, exclude, prioritize, pivot)
   - Test scope violation rejection
   - Test audit stream integration
   - Test strategy publication

### Previous Story Intelligence

From **Story 8.1** (Director Ensemble Base Architecture):
- `DirectorEnsemble` class is fully implemented in `llm/ensemble.py`
- Use `query_model()` for single model queries or `query_all()` for full ensemble
- `DirectorContext` provides engagement context

From **Story 8.5** (Strategy Synthesis Engine):
- `SynthesizedStrategy` provides structured output format
- `to_json()` method for Redis publication
- Conflict resolution patterns established

From **Story 8.6** (Partial Model Availability Fallback):
- Degradation handling is built into ensemble
- Use `DegradationLevel` for tracking availability
- Circuit breaker protects against hammering unavailable models

From **Story 3.3** (Event Bus):
- `EventBus.publish()` for strategy publication
- `EventBus.audit()` for audit trail logging
- Channel validation is automatic

### Project Structure Notes

- New module at `src/cyberred/orchestration/directive.py`
- Export `DirectiveInterpreter`, `MissionDirective`, `ParsedDirective`, `DirectiveResult` from `orchestration/__init__.py`
- Tests follow existing patterns in `tests/unit/orchestration/` and `tests/integration/orchestration/`

### References

- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story-8.7]
- [Source: _bmad-output/implementation-artifacts/8-1-director-ensemble-base-architecture.md]
- [Source: _bmad-output/implementation-artifacts/8-5-strategy-synthesis-engine.md]
- [Source: src/cyberred/llm/ensemble.py#DirectorEnsemble]
- [Source: src/cyberred/core/events.py#EventBus]
- [Source: src/cyberred/tools/scope.py#ScopeValidator]
- [Source: _bmad-output/planning-artifacts/architecture.md]

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

N/A - No debug issues encountered.

### Completion Notes List

- **Implementation Complete**: All 6 tasks completed successfully
- **Unit Tests**: 44 tests passing covering dataclass validation, interpreter logic, scope validation, audit logging, and strategy publication
- **Integration Tests**: 7 tests passing covering end-to-end flows for all directive types
- **Coverage**: 98.71% line coverage for directive.py (51 total tests)
- **All Acceptance Criteria Met**:
  - AC1: Director Ensemble interprets natural language directives ✓
  - AC2: Directives translated to agent task priorities with focus areas, exclusions, priorities ✓
  - AC3: Directives logged to audit:stream with timestamp, engagement_id, raw_text, parsed interpretation ✓
  - AC4: Strategy updates published via strategies:{engagement_id} channel ✓
  - AC5: Scope-violating directives rejected with clear error messages, hard-gate enforced ✓
  - AC6: Integration tests verify various directive types (focus, exclude, prioritize, pivot, abort) ✓

### File List

**Implementation Files:**
- `src/cyberred/orchestration/directive.py` - Main directive interpreter module (636 lines)
- `src/cyberred/orchestration/__init__.py` - Updated exports (already contained directive exports)

**Test Files:**
- `tests/unit/orchestration/test_directive.py` - Unit tests (44 tests, 1345 lines)
- `tests/integration/orchestration/test_directive_integration.py` - Integration tests (7 tests, 409 lines)
