"""Mission Directive Interpreter for natural language operator commands.

Story 8.7: Natural Language Mission Directive.

This module provides the DirectiveInterpreter class that uses the DirectorEnsemble
to interpret natural language mission directives from operators and translate them
into structured task priorities for agents.

Key Features:
- Natural language directive parsing via LLM
- Scope validation (hard-gate - directives cannot override scope rules)
- Audit trail logging for all directives
- Strategy publication via Redis pub/sub

Classes:
    DirectiveType: Enum of directive types (focus, exclude, prioritize, pivot, abort)
    MissionDirective: Raw mission directive from operator
    ParsedDirective: Interpreted directive with structured components
    DirectiveResult: Result of directive processing
    DirectiveInterpreter: Main interpreter class

Example:
    interpreter = DirectiveInterpreter(
        ensemble=ensemble,
        event_bus=event_bus,
        scope_validator=scope_validator,
    )
    directive = MissionDirective(
        raw_text="Focus on web application vulnerabilities",
        engagement_id="eng-001",
    )
    result = await interpreter.interpret(directive)
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

from cyberred.llm.ensemble import (
    DirectorContext,
    DirectorEnsemble,
    DirectorRole,
    ModelResponse,
    SynthesizedStrategy,
    DegradationLevel,
)
from cyberred.core.events import EventBus
from cyberred.core.exceptions import ScopeViolationError
from cyberred.tools.scope import ScopeValidator

log = structlog.get_logger()


# =============================================================================
# Enums
# =============================================================================


class DirectiveType(Enum):
    """Types of mission directives.
    
    Attributes:
        FOCUS: Focus on specific areas/targets/techniques.
        EXCLUDE: Skip/exclude targets or techniques.
        PRIORITIZE: Change priority ordering.
        PIVOT: Change attack direction.
        ABORT: Abort specific actions.
    """
    FOCUS = "focus"
    EXCLUDE = "exclude"
    PRIORITIZE = "prioritize"
    PIVOT = "pivot"
    ABORT = "abort"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class MissionDirective:
    """Raw mission directive from operator.
    
    Attributes:
        raw_text: Original natural language directive.
        engagement_id: Current engagement identifier.
        timestamp: When directive was issued (defaults to current time).
        operator_id: Optional operator identifier.
    
    Raises:
        ValueError: If raw_text or engagement_id is empty/whitespace.
    """
    raw_text: str
    engagement_id: str
    timestamp: float = field(default_factory=time.time)
    operator_id: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate required fields after initialization."""
        if not self.raw_text or not self.raw_text.strip():
            raise ValueError("raw_text cannot be empty")
        if not self.engagement_id or not self.engagement_id.strip():
            raise ValueError("engagement_id cannot be empty")


@dataclass
class ParsedDirective:
    """Interpreted directive with structured components.
    
    Attributes:
        directive_type: Type of directive (focus, exclude, prioritize, pivot, abort).
        focus_areas: Areas to focus on (e.g., ["web applications", "SQL injection"]).
        exclusions: Areas to exclude (e.g., ["network infrastructure", "DNS"]).
        priorities: Priority ordering (e.g., ["critical vulns", "high vulns"]).
        pivot_reason: Reason for pivot if directive_type is PIVOT.
        confidence: Confidence in interpretation (0.0-1.0), clamped to valid range.
        raw_interpretation: Raw LLM interpretation text.
    
    Raises:
        ValueError: If confidence is not a valid number.
    """
    directive_type: DirectiveType
    focus_areas: List[str] = field(default_factory=list)
    exclusions: List[str] = field(default_factory=list)
    priorities: List[str] = field(default_factory=list)
    pivot_reason: Optional[str] = None
    confidence: float = 0.0
    raw_interpretation: str = ""
    
    def __post_init__(self) -> None:
        """Validate and clamp confidence to valid range after initialization."""
        # Clamp confidence to [0.0, 1.0] range
        self.confidence = max(0.0, min(1.0, float(self.confidence)))


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


# =============================================================================
# DirectiveInterpreter
# =============================================================================


class DirectiveInterpreter:
    """Interprets natural language mission directives.
    
    Uses DirectorEnsemble to parse operator directives into structured
    task priorities while enforcing scope validation.
    
    Attributes:
        _ensemble: DirectorEnsemble for LLM-based interpretation.
        _event_bus: EventBus for audit logging and strategy publication.
        _scope_validator: Optional ScopeValidator for directive validation.
        _engagement_id: Default engagement ID if not in directive.
    
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

IMPORTANT: Output ONLY valid JSON in the following format (no markdown, no explanation):
{
    "directive_type": "focus|exclude|prioritize|pivot|abort",
    "focus_areas": ["area1", "area2"],
    "exclusions": ["exclusion1", "exclusion2"],
    "priorities": ["priority1", "priority2"],
    "pivot_reason": "reason if pivot, otherwise null",
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
            current_context: Optional current engagement context for additional context.
            
        Returns:
            DirectiveResult with parsed directive and strategy update.
        """
        self._log.info(
            "directive_interpretation_started",
            engagement_id=directive.engagement_id,
            raw_text=directive.raw_text[:100],  # Truncate for logging
        )
        
        try:
            # Step 1: Query LLM to interpret the directive
            parsed = await self._interpret_with_llm(directive, current_context)
            
            if parsed is None:
                result = DirectiveResult(
                    success=False,
                    error_message="Failed to interpret directive: LLM returned no response",
                )
                await self._log_directive_to_audit(directive, result)
                return result
            
            # Step 2: Validate against scope rules (hard-gate)
            scope_error = await self._validate_against_scope(parsed)
            if scope_error:
                result = DirectiveResult(
                    success=False,
                    error_message=f"Directive violates scope: {scope_error}",
                    scope_violation=True,
                )
                await self._log_directive_to_audit(directive, result)
                return result
            
            # Step 3: Create strategy update
            strategy = self._create_strategy_from_directive(parsed, directive)
            
            # Step 4: Publish strategy update
            await self._publish_strategy_update(
                directive.engagement_id,
                strategy,
                directive,
            )
            
            # Step 5: Create success result
            result = DirectiveResult(
                success=True,
                parsed=parsed,
                strategy_update=strategy,
            )
            
            # Step 6: Log to audit trail
            await self._log_directive_to_audit(directive, result)
            
            self._log.info(
                "directive_interpretation_completed",
                engagement_id=directive.engagement_id,
                directive_type=parsed.directive_type.value,
                confidence=parsed.confidence,
            )
            
            return result
            
        except Exception as e:
            self._log.error(
                "directive_interpretation_error",
                engagement_id=directive.engagement_id,
                error=str(e),
                exc_info=True,
            )
            result = DirectiveResult(
                success=False,
                error_message=f"Interpretation failed: {str(e)}",
            )
            await self._log_directive_to_audit(directive, result)
            return result
    
    async def _interpret_with_llm(
        self,
        directive: MissionDirective,
        current_context: Optional[DirectorContext] = None,
    ) -> Optional[ParsedDirective]:
        """Use LLM to interpret the directive.
        
        Args:
            directive: The mission directive to interpret.
            current_context: Optional current engagement context.
            
        Returns:
            ParsedDirective if successful, None if LLM fails.
        """
        # Build the interpretation prompt
        prompt = self._build_interpretation_prompt(directive, current_context)
        
        # Create context for Director query
        context = DirectorContext(
            engagement_id=directive.engagement_id,
            phase="directive_interpretation",
            prompt=prompt,
        )
        
        # Query the strategist model for interpretation
        response = await self._ensemble.query_model(DirectorRole.STRATEGIST, context)
        
        if not response.success:
            self._log.warning(
                "directive_llm_query_failed",
                error=response.error,
            )
            return None
        
        # Parse the LLM response
        return self._parse_llm_response(response)
    
    def _build_interpretation_prompt(
        self,
        directive: MissionDirective,
        current_context: Optional[DirectorContext] = None,
    ) -> str:
        """Build the prompt for LLM interpretation.
        
        Args:
            directive: The mission directive.
            current_context: Optional current context.
            
        Returns:
            Prompt string for LLM.
        """
        parts = [
            self.DIRECTIVE_SYSTEM_PROMPT,
            "",
            "## Operator Directive",
            f'"{directive.raw_text}"',
        ]
        
        if current_context:
            parts.extend([
                "",
                "## Current Context",
                f"Phase: {current_context.phase}",
            ])
            if current_context.constraints:
                parts.append(f"Constraints: {json.dumps(current_context.constraints)}")
        
        parts.extend([
            "",
            "Parse this directive and output the JSON:",
        ])
        
        return "\n".join(parts)
    
    def _parse_llm_response(self, response: ModelResponse) -> Optional[ParsedDirective]:
        """Parse LLM response into ParsedDirective.
        
        Args:
            response: The LLM response.
            
        Returns:
            ParsedDirective if parsing succeeds, None otherwise.
        """
        content = response.content.strip()
        
        # Try to extract JSON from response (may have markdown wrapping)
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            content = json_match.group(0)
        
        try:
            data = json.loads(content)
            
            # Parse directive type
            directive_type_str = data.get("directive_type", "focus")
            try:
                directive_type = DirectiveType(directive_type_str)
            except ValueError:
                directive_type = DirectiveType.FOCUS
            
            return ParsedDirective(
                directive_type=directive_type,
                focus_areas=data.get("focus_areas", []) or [],
                exclusions=data.get("exclusions", []) or [],
                priorities=data.get("priorities", []) or [],
                pivot_reason=data.get("pivot_reason"),
                confidence=float(data.get("confidence", 0.5)),
                raw_interpretation=content,
            )
            
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            self._log.warning(
                "directive_json_parse_failed",
                error=str(e),
                content=content[:200],
            )
            # Attempt fallback parsing for non-JSON response
            return self._fallback_parse(response.content)
    
    def _fallback_parse(self, content: str) -> Optional[ParsedDirective]:
        """Fallback parsing for non-JSON responses.
        
        Attempts to extract directive information from natural language response.
        
        Args:
            content: The raw response content.
            
        Returns:
            ParsedDirective with best-effort parsing, or None if impossible.
        """
        content_lower = content.lower()
        
        # Detect directive type from keywords
        if "abort" in content_lower or "stop" in content_lower:
            directive_type = DirectiveType.ABORT
        elif "pivot" in content_lower or "change direction" in content_lower:
            directive_type = DirectiveType.PIVOT
        elif "exclude" in content_lower or "skip" in content_lower:
            directive_type = DirectiveType.EXCLUDE
        elif "prioritize" in content_lower or "priority" in content_lower:
            directive_type = DirectiveType.PRIORITIZE
        else:
            directive_type = DirectiveType.FOCUS
        
        return ParsedDirective(
            directive_type=directive_type,
            confidence=0.3,  # Low confidence for fallback parsing
            raw_interpretation=content,
        )
    
    async def _validate_against_scope(
        self,
        parsed: ParsedDirective,
    ) -> Optional[str]:
        """Validate parsed directive against scope rules.
        
        This is a HARD-GATE: Directives cannot override scope rules.
        
        Args:
            parsed: The parsed directive.
            
        Returns:
            Error message if validation fails, None if OK.
        """
        if not self._scope_validator:
            return None
        
        # Validate focus areas are within scope
        for focus_area in parsed.focus_areas:
            # Check if focus area looks like an IP/network/hostname
            if self._looks_like_target(focus_area):
                try:
                    self._scope_validator.validate(target=focus_area)
                except ScopeViolationError as e:
                    return f"Focus area '{focus_area}' is out of scope: {e.message}"
        
        return None
    
    def _looks_like_target(self, value: str) -> bool:
        """Check if a string looks like a target (IP, network, hostname).
        
        Used to determine if a focus area should be validated against scope rules.
        Non-target strings like "SQL injection" or "web applications" are allowed
        without scope validation since they represent techniques, not actual targets.
        
        Recognized patterns:
            - IPv4 addresses: 192.168.1.1
            - CIDR notation: 192.168.1.0/24
            - Hostnames: example.com, sub.domain.example.com
        
        Args:
            value: The string to check.
            
        Returns:
            True if the value matches an IP address, CIDR notation, or hostname pattern.
            False for technique names, vulnerability types, or other non-target strings.
        """
        # IP address pattern (with optional CIDR notation)
        ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?$'
        # Hostname pattern (must have at least one dot, e.g., example.com)
        hostname_pattern = r'^[a-zA-Z0-9][-a-zA-Z0-9]*(?:\.[a-zA-Z0-9][-a-zA-Z0-9]*)+$'
        
        return bool(re.match(ip_pattern, value) or re.match(hostname_pattern, value))
    
    def _create_strategy_from_directive(
        self,
        parsed: ParsedDirective,
        directive: MissionDirective,
    ) -> SynthesizedStrategy:
        """Create a SynthesizedStrategy from the parsed directive.
        
        Args:
            parsed: The parsed directive.
            directive: The original directive.
            
        Returns:
            SynthesizedStrategy incorporating the directive.
        """
        # Build objectives based on directive type
        objectives: List[str] = []
        actions: List[str] = []
        
        if parsed.directive_type == DirectiveType.FOCUS:
            for area in parsed.focus_areas:
                objectives.append(f"Focus engagement on {area}")
                actions.append(f"Prioritize scanning and exploitation of {area}")
        
        elif parsed.directive_type == DirectiveType.EXCLUDE:
            for exclusion in parsed.exclusions:
                objectives.append(f"Exclude {exclusion} from engagement")
                actions.append(f"Skip all activities targeting {exclusion}")
        
        elif parsed.directive_type == DirectiveType.PRIORITIZE:
            for i, priority in enumerate(parsed.priorities):
                objectives.append(f"Priority {i+1}: {priority}")
                actions.append(f"Reorder tasks to address {priority} first")
        
        elif parsed.directive_type == DirectiveType.PIVOT:
            if parsed.pivot_reason:
                objectives.append(f"Pivot engagement: {parsed.pivot_reason}")
            for area in parsed.focus_areas:
                objectives.append(f"New focus: {area}")
                actions.append(f"Redirect efforts to {area}")
        
        elif parsed.directive_type == DirectiveType.ABORT:
            if parsed.exclusions:
                for exclusion in parsed.exclusions:
                    objectives.append(f"Abort: {exclusion}")
                    actions.append(f"Immediately stop all {exclusion} activities")
            else:
                # Handle ABORT with no specific exclusions - abort all non-essential activities
                objectives.append("Abort: All non-essential activities")
                actions.append("Immediately halt non-critical operations pending operator review")
        
        # Build rationale
        rationale = f"Strategy updated per operator directive: '{directive.raw_text[:100]}'"
        if parsed.pivot_reason:
            rationale += f" Reason: {parsed.pivot_reason}"
        
        return SynthesizedStrategy(
            objectives=objectives,
            actions=actions,
            rationale=rationale,
            confidence=parsed.confidence,
            contributing_roles=[DirectorRole.STRATEGIST],
            avoid_list=parsed.exclusions,
            metadata={
                "directive_type": parsed.directive_type.value,
                "source": "operator_directive",
            },
        )
    
    async def _log_directive_to_audit(
        self,
        directive: MissionDirective,
        result: DirectiveResult,
    ) -> None:
        """Log directive to audit trail.
        
        Args:
            directive: The original directive.
            result: The processing result.
        """
        audit_event = {
            "type": "mission_directive",
            "engagement_id": directive.engagement_id,
            "raw_text": directive.raw_text,
            "operator_id": directive.operator_id,
            "success": result.success,
            "parsed": None,
            "error": result.error_message,
            "scope_violation": result.scope_violation,
            "timestamp": directive.timestamp,
        }
        
        if result.parsed:
            audit_event["parsed"] = {
                "directive_type": result.parsed.directive_type.value,
                "focus_areas": result.parsed.focus_areas,
                "exclusions": result.parsed.exclusions,
                "priorities": result.parsed.priorities,
                "confidence": result.parsed.confidence,
            }
        
        await self._event_bus.audit(audit_event)
        
        self._log.info(
            "directive_audit_logged",
            engagement_id=directive.engagement_id,
            success=result.success,
        )
    
    async def _publish_strategy_update(
        self,
        engagement_id: str,
        strategy: SynthesizedStrategy,
        directive: MissionDirective,
    ) -> int:
        """Publish strategy update to agents.
        
        Args:
            engagement_id: The engagement ID.
            strategy: The strategy to publish.
            directive: The original directive.
            
        Returns:
            Number of subscribers that received the message.
        """
        # Add directive metadata to strategy
        strategy.metadata["directive"] = {
            "raw_text": directive.raw_text,
            "timestamp": directive.timestamp,
            "operator_id": directive.operator_id,
        }
        
        channel = f"strategies:{engagement_id}"
        subscribers = await self._event_bus.publish(channel, strategy.to_json())
        
        self._log.info(
            "directive_strategy_published",
            engagement_id=engagement_id,
            channel=channel,
            subscribers=subscribers,
        )
        
        return subscribers
