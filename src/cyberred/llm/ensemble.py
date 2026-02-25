"""Director Ensemble for multi-model strategy synthesis.

Story 8.1: Director Ensemble Base Architecture.
Story 8.2: DeepSeek Strategist Role.
Story 8.3: Kimi K2 Analyst Role.

This module provides the DirectorEnsemble class that coordinates three LLM models
for multi-perspective strategic analysis during penetration testing operations.

Per architecture:
- Director uses separate synthesis models, NOT from agent model pool
- Models: DeepSeek V3.2 (strategist), Kimi K2 (analyst), MiniMax M2 (creative)
- Long-running, deadline-aware timeouts for thinking-model responses
- Pattern inspired by kyegomez/swarms MixtureOfAgents (parallel query, synthesis)
- Custom implementation (not using swarms library) for LLMGateway integration

Classes:
    DirectorRole: Enum defining director model roles (STRATEGIST, ANALYST, CREATIVE)
    DirectorModel: Configuration dataclass for each director model
    DirectorContext: Input context for ensemble queries
    ModelResponse: Response from a single model
    DirectorQueryResult: Aggregated results from all models
    SynthesisInput: Input for strategy synthesis
    SynthesizedStrategy: Unified strategy output
    DirectorEnsemble: Main ensemble coordinator class
    
    SwarmState: Current swarm state for strategist context (Story 8.2)
    FindingsSummary: Aggregated findings for strategist context (Story 8.2)
    ATTCKRecommendation: ATT&CK technique recommendation (Story 8.2)
    StrategistResponse: Structured response from strategist (Story 8.2)
    
    SecurityGap: Security gap identified by analyst (Story 8.3)
    OverlookedOpportunity: Overlooked attack opportunity (Story 8.3)
    RiskAssessment: Overall risk assessment from analyst (Story 8.3)
    FindingDetail: Detailed finding information (Story 8.3)
    TargetEnvironment: Target environment information (Story 8.3)
    AttackPath: Discovered attack path (Story 8.3)
    AnalystResponse: Structured response from analyst (Story 8.3)

Functions:
    extract_attck_techniques: Extract ATT&CK techniques from response text (Story 8.2)
    extract_gaps: Extract security gaps from response text (Story 8.3)
    extract_opportunities: Extract overlooked opportunities from response text (Story 8.3)
    extract_risk_assessment: Extract risk assessment from response text (Story 8.3)
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import structlog

from cyberred.llm.provider import LLMRequest, LLMResponse, TokenUsage
from cyberred.llm.gateway import get_gateway
from cyberred.core.exceptions import LLMTimeoutError, LLMProviderUnavailable

log = structlog.get_logger()


class DirectorRole(Enum):
    """Director model roles for multi-perspective analysis.
    
    Each role brings a different analytical perspective to strategic planning:
    - STRATEGIST: High-level strategic planning and attack sequencing
    - ANALYST: Deep reasoning and attack surface analysis
    - CREATIVE: Lateral thinking and evasion technique generation
    """
    STRATEGIST = "strategist"  # DeepSeek - strategic planning
    ANALYST = "analyst"        # Kimi K2 - deep reasoning
    CREATIVE = "creative"      # MiniMax M2 - lateral thinking


# ============================================================================
# Story 8.6: Partial Model Availability Fallback
# ============================================================================


class AvailabilityState(Enum):
    """Model availability states for circuit breaker tracking.
    
    Story 8.6: Partial Model Availability Fallback.
    """
    AVAILABLE = "available"    # Model is ready for queries
    EXCLUDED = "excluded"      # Model excluded by circuit breaker
    FAILED = "failed"          # Model failed last query
    UNKNOWN = "unknown"        # Model status not yet determined


class DegradationLevel(Enum):
    """Level of ensemble degradation based on available models.
    
    Story 8.6: Partial Model Availability Fallback.
    """
    FULL = "full"                      # All 3 models available
    DEGRADED_PAIR = "degraded_pair"    # 2 of 3 models available
    DEGRADED_SINGLE = "degraded_single"  # 1 of 3 models available
    UNAVAILABLE = "unavailable"        # 0 models available


# Confidence multipliers based on available models (Story 8.6)
CONFIDENCE_MULTIPLIERS: Dict[int, float] = {
    3: 1.0,    # Full ensemble - no reduction
    2: 0.75,   # Pair mode - 25% reduction
    1: 0.5,    # Single mode - 50% reduction
}


@dataclass
class CircuitBreakerState:
    """State for a single model's circuit breaker.
    
    Story 8.6: Partial Model Availability Fallback.
    
    Attributes:
        failure_count: Number of consecutive failures.
        last_failure_time: Timestamp of last failure (monotonic).
        excluded_until: Timestamp when exclusion ends (monotonic).
    """
    failure_count: int = 0
    last_failure_time: float = 0.0
    excluded_until: float = 0.0
    
    def is_excluded(self) -> bool:
        """Check if model is currently excluded.
        
        Returns:
            True if model is still in exclusion period.
        """
        return time.monotonic() < self.excluded_until


@dataclass
class ModelAvailabilityStatus:
    """Status of a single Director model.
    
    Story 8.6: Partial Model Availability Fallback.
    
    Attributes:
        role: The Director role.
        state: Current availability state.
        failure_count: Number of consecutive failures.
        excluded_until: Timestamp when exclusion ends (if excluded).
        last_error: Last error message (if failed).
    """
    role: DirectorRole
    state: AvailabilityState
    failure_count: int = 0
    excluded_until: Optional[float] = None
    last_error: Optional[str] = None


@dataclass
class DegradationWarning:
    """Warning about ensemble degradation for operator notification.
    
    Story 8.6: Partial Model Availability Fallback.
    
    Attributes:
        level: Current degradation level.
        available_models: List of available model roles.
        excluded_models: List of excluded model roles.
        message: Human-readable warning message.
        timestamp: Warning timestamp (monotonic clock for stability).
    """
    level: DegradationLevel
    available_models: List[DirectorRole]
    excluded_models: List[DirectorRole]
    message: str
    timestamp: float = field(default_factory=time.monotonic)
    
    def to_event(self) -> Dict[str, Any]:
        """Convert to event bus format for TUI notification.
        
        Returns:
            Dictionary suitable for event bus publication.
        """
        return {
            "type": "director_degradation_warning",
            "level": self.level.value,
            "available_models": [m.value for m in self.available_models],
            "excluded_models": [m.value for m in self.excluded_models],
            "message": self.message,
            "timestamp": self.timestamp,
        }


class CircuitBreaker:
    """Circuit breaker for Director model availability.
    
    Story 8.6: Partial Model Availability Fallback.
    Per architecture: 3 failures → exclude model for 60s.
    
    Tracks consecutive failures per model and excludes models that
    fail repeatedly to prevent hammering unavailable providers.
    
    Attributes:
        _failure_threshold: Number of failures before exclusion.
        _exclusion_seconds: Duration to exclude failed model.
        _states: Per-role circuit breaker states.
    """
    
    def __init__(
        self,
        failure_threshold: int = 3,
        exclusion_seconds: float = 60.0,
    ) -> None:
        """Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before exclusion (default: 3).
                Must be >= 1.
            exclusion_seconds: Duration to exclude model in seconds (default: 60).
                Must be > 0.
        
        Raises:
            ValueError: If failure_threshold < 1 or exclusion_seconds <= 0.
        """
        if failure_threshold < 1:
            raise ValueError(f"failure_threshold must be >= 1, got {failure_threshold}")
        if exclusion_seconds <= 0:
            raise ValueError(f"exclusion_seconds must be > 0, got {exclusion_seconds}")
        
        self._failure_threshold = failure_threshold
        self._exclusion_seconds = exclusion_seconds
        self._states: Dict[DirectorRole, CircuitBreakerState] = {
            role: CircuitBreakerState() for role in DirectorRole
        }
    
    def record_failure(self, role: DirectorRole) -> bool:
        """Record a failure for a model.
        
        Args:
            role: The role that failed.
            
        Returns:
            True if model was excluded due to this failure (first time reaching threshold).
        """
        state = self._states[role]
        
        # If already excluded, don't increment or re-log
        if state.is_excluded():
            return False
        
        state.failure_count += 1
        state.last_failure_time = time.monotonic()
        
        if state.failure_count >= self._failure_threshold:
            state.excluded_until = time.monotonic() + self._exclusion_seconds
            log.warning(
                "circuit_breaker_model_excluded",
                role=role.value,
                failure_count=state.failure_count,
                excluded_seconds=self._exclusion_seconds,
            )
            return True
        return False
    
    def record_success(self, role: DirectorRole) -> None:
        """Record a success for a model, resetting failure count.
        
        Args:
            role: The role that succeeded.
        """
        state = self._states[role]
        if state.failure_count > 0:
            log.info(
                "circuit_breaker_model_recovered",
                role=role.value,
                previous_failures=state.failure_count,
            )
        state.failure_count = 0
        state.excluded_until = 0.0
    
    def is_available(self, role: DirectorRole) -> bool:
        """Check if a model is available (not excluded).
        
        Args:
            role: The role to check.
            
        Returns:
            True if model is available for queries.
        """
        state = self._states[role]
        if state.is_excluded():
            return False
        return True
    
    def get_available_roles(self) -> List[DirectorRole]:
        """Get list of available (non-excluded) roles.
        
        Returns:
            List of roles that are available for queries.
        """
        return [role for role in DirectorRole if self.is_available(role)]
    
    def reset(self, role: DirectorRole) -> None:
        """Manually reset circuit breaker for a role.
        
        Args:
            role: The role to reset.
        """
        self._states[role] = CircuitBreakerState()
        log.info("circuit_breaker_reset", role=role.value)

    def get_status(self, role: DirectorRole) -> ModelAvailabilityStatus:
        """Get detailed availability status for a role.
        
        Args:
            role: The role to check.
            
        Returns:
            ModelAvailabilityStatus with full state information.
        """
        state = self._states[role]
        
        if state.is_excluded():
            availability_state = AvailabilityState.EXCLUDED
        elif state.failure_count > 0:
            availability_state = AvailabilityState.FAILED
        else:
            availability_state = AvailabilityState.AVAILABLE
        
        return ModelAvailabilityStatus(
            role=role,
            state=availability_state,
            failure_count=state.failure_count,
            excluded_until=state.excluded_until if state.excluded_until > 0 else None,
        )


@dataclass(frozen=True)
class DirectorModel:
    """Configuration for a Director model.
    
    Attributes:
        model_id: Model identifier for LLM routing (e.g., 'deepseek-ai/deepseek-v3_2').
        role: The role this model plays in the ensemble.
        timeout: Per-model timeout in seconds.
        system_prompt: Role-specific system prompt for the model.
    """
    model_id: str
    role: DirectorRole
    timeout: float
    system_prompt: str


# Default model configurations tuned for long-context reasoning models.
DIRECTOR_MODELS: Dict[DirectorRole, DirectorModel] = {
    DirectorRole.STRATEGIST: DirectorModel(
        model_id="deepseek-ai/deepseek-v3.2",
        role=DirectorRole.STRATEGIST,
        timeout=300.0,
        system_prompt="""You are a strategic planning expert for penetration testing operations.

Your role is to analyze engagement state and provide strategic guidance.

## Required Output Format

Provide your response in the following structured format:

### Strategic Recommendations
1. [Recommendation with rationale]
2. [Recommendation with rationale]

### Next Phases
- [Phase name]: [Description and timing]

### Target Priorities
| Priority | Target | Rationale |
|----------|--------|-----------|
| 1 | [target] | [why highest priority] |

### ATT&CK Techniques
- T[XXXX].[XXX] - [Technique Name]: [Why applicable to this engagement]

### Confidence Assessment
[0.0-1.0]: [Rationale for confidence level]

Focus on strategic value, operational efficiency, and proven attack frameworks."""
    ),
    DirectorRole.ANALYST: DirectorModel(
        model_id="moonshotai/kimi-k2-instruct",
        role=DirectorRole.ANALYST,
        timeout=300.0,
        system_prompt="""You are a deep reasoning analyst for penetration testing attack surface analysis.

Your role is to thoroughly analyze findings and identify overlooked opportunities.

## Required Output Format

Provide your response in the following structured format:

### Attack Surface Analysis
[Comprehensive analysis of the discovered attack surface, including exposed services, potential entry points, and attack vectors]

### Risk Assessment
**Overall Risk Level:** [CRITICAL/HIGH/MEDIUM/LOW/INFO]
**Risk Factors:**
- [Factor 1]
- [Factor 2]
**Mitigations Needed:**
- [Mitigation 1]
- [Mitigation 2]
**Confidence:** [0.0-1.0]

### Security Gaps
| Gap ID | Description | Severity | Affected Assets |
|--------|-------------|----------|-----------------|
| GAP-001 | [description] | [CRITICAL/HIGH/MEDIUM/LOW] | [asset1, asset2] |

### Overlooked Opportunities
| Opportunity ID | Description | Potential Impact | Recommended Action | Confidence |
|----------------|-------------|------------------|-------------------|------------|
| OPP-001 | [description] | [impact] | [action] | [0.0-1.0] |

Focus on thorough analysis, identifying gaps in current coverage, and uncovering overlooked attack vectors."""
    ),
    DirectorRole.CREATIVE: DirectorModel(
        model_id="minimaxai/minimax-m2",
        role=DirectorRole.CREATIVE,
        timeout=300.0,
        system_prompt="""You are a creative approaches expert for penetration testing evasion and novel attack techniques.

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
    ),
}


@dataclass
class DirectorContext:
    """Input context for Director ensemble queries.
    
    Attributes:
        engagement_id: Current engagement identifier.
        phase: Current kill chain phase.
        prompt: The strategic question or analysis request.
        findings: List of current findings/intelligence.
        constraints: Operational constraints (scope, rules of engagement).
        previous_strategies: Previously attempted strategies for context.
        metadata: Additional context metadata.
        
    Raises:
        ValueError: If engagement_id, phase, or prompt is empty/whitespace.
    """
    engagement_id: str
    phase: str
    prompt: str
    findings: List[Dict[str, Any]] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    previous_strategies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Validate required fields after initialization."""
        if not self.engagement_id or not self.engagement_id.strip():
            raise ValueError("engagement_id cannot be empty or whitespace")
        if not self.phase or not self.phase.strip():
            raise ValueError("phase cannot be empty or whitespace")
        if not self.prompt or not self.prompt.strip():
            raise ValueError("prompt cannot be empty or whitespace")


@dataclass
class ModelResponse:
    """Response from a single Director model.
    
    Attributes:
        role: The role of the model that produced this response.
        model_id: The model identifier.
        content: The response content.
        latency_ms: Response latency in milliseconds.
        success: Whether the query succeeded.
        error: Error message if query failed.
        token_usage: Token usage for the response.
    """
    role: DirectorRole
    model_id: str
    content: str
    latency_ms: int
    success: bool
    error: Optional[str] = None
    token_usage: Optional[TokenUsage] = None


@dataclass
class DirectorQueryResult:
    """Aggregated results from querying all Director models.
    
    Attributes:
        context: The original query context.
        responses: Mapping of role to model response.
        total_latency_ms: Total query time in milliseconds.
        successful_count: Number of successful model responses.
        failed_count: Number of failed model responses.
    """
    context: DirectorContext
    responses: Dict[DirectorRole, ModelResponse]
    total_latency_ms: int
    successful_count: int
    failed_count: int

    @property
    def all_succeeded(self) -> bool:
        """Check if all models responded successfully."""
        return self.failed_count == 0

    @property
    def has_responses(self) -> bool:
        """Check if at least one model responded successfully."""
        return self.successful_count > 0

    def get_response(self, role: DirectorRole) -> Optional[ModelResponse]:
        """Get response for a specific role."""
        return self.responses.get(role)

    def get_content(self, role: DirectorRole) -> str:
        """Get response content for a specific role, empty string if failed."""
        response = self.responses.get(role)
        if response and response.success:
            return response.content
        return ""


@dataclass
class SynthesisInput:
    """Input for strategy synthesis from multi-model responses.
    
    Attributes:
        query_result: The aggregated query results.
        synthesis_prompt: Optional additional synthesis instructions.
    """
    query_result: DirectorQueryResult
    synthesis_prompt: Optional[str] = None


@dataclass
class ConflictResolution:
    """Record of a resolved conflict between model recommendations.
    
    Story 8.5: Strategy Synthesis Engine.
    
    Attributes:
        conflict_type: Type of conflict (priority, approach, target, technique, safety).
        source_roles: Roles that had conflicting recommendations.
        conflicting_values: The conflicting values from each role.
        resolved_value: The resolved value after applying priority rules.
        resolution_rationale: Explanation of why this resolution was chosen.
    """
    conflict_type: str  # "priority", "approach", "target", "technique", "safety"
    source_roles: List[DirectorRole]
    conflicting_values: List[str]
    resolved_value: str
    resolution_rationale: str


# Priority order for conflict resolution (Story 8.5)
# Lower number = higher priority
CONFLICT_PRIORITY: Dict[str, int] = {
    "security_warning": 1,     # Analyst security concerns always highest
    "scope_constraint": 2,     # Must respect scope rules
    "strategic_priority": 3,   # Strategist priorities
    "risk_avoidance": 4,       # Analyst risk warnings
    "creative_alternative": 5, # Creative suggestions lowest priority
}


@dataclass
class SynthesizedStrategy:
    """Unified strategy synthesized from multiple model perspectives.
    
    Story 8.5: Extended with additional fields for comprehensive synthesis.
    Story 8.6: Added degradation fields for fallback tracking.
    
    Attributes:
        objectives: Strategic objectives to pursue.
        actions: Ordered list of recommended actions.
        rationale: Explanation of the strategy synthesis.
        confidence: Confidence score (0.0-1.0) based on model agreement.
        contributing_roles: Roles that contributed to this synthesis.
        metadata: Additional synthesis metadata.
        avoid_list: Targets/approaches to skip.
        attck_techniques: ATT&CK technique recommendations from strategist.
        creative_alternatives: Preserved creative alternatives.
        risk_warnings: Risk warnings from analyst.
        conflicts_resolved: Record of resolved conflicts.
        degradation_level: Current degradation level (Story 8.6).
        missing_perspectives: Roles that were unavailable (Story 8.6).
        fallback_warnings: Warnings about degraded operation (Story 8.6).
    """
    objectives: List[str]
    actions: List[str]
    rationale: str
    confidence: float
    contributing_roles: List[DirectorRole]
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Story 8.5: Synthesis fields
    avoid_list: List[str] = field(default_factory=list)
    attck_techniques: List["ATTCKRecommendation"] = field(default_factory=list)
    creative_alternatives: List["CreativeAlternative"] = field(default_factory=list)
    risk_warnings: List[str] = field(default_factory=list)
    conflicts_resolved: List[ConflictResolution] = field(default_factory=list)
    # Story 8.6: Degradation fields
    degradation_level: DegradationLevel = DegradationLevel.FULL
    missing_perspectives: List[DirectorRole] = field(default_factory=list)
    fallback_warnings: List[str] = field(default_factory=list)

    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON for Redis publication.
        
        Story 8.5: Structured output for strategies:{engagement_id} topic.
        Story 8.6: Added degradation fields for fallback tracking.
        
        Returns:
            Dictionary suitable for JSON serialization and Redis publication.
        """
        return {
            "objectives": self.objectives,
            "actions": self.actions,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "contributing_roles": [r.value for r in self.contributing_roles],
            "avoid_list": self.avoid_list,
            "attck_techniques": [
                {
                    "technique_id": t.technique_id,
                    "technique_name": t.technique_name,
                    "rationale": t.rationale,
                    "phase": t.phase,  # Include phase field from ATTCKRecommendation
                }
                for t in self.attck_techniques
            ],
            "creative_alternatives": [
                {
                    "alternative_id": a.alternative_id,
                    "description": a.description,
                    "rationale": a.rationale,
                    "novelty_score": a.novelty_score,
                }
                for a in self.creative_alternatives
            ],
            "risk_warnings": self.risk_warnings,
            "conflicts_resolved": [
                {
                    "conflict_type": c.conflict_type,
                    "source_roles": [r.value for r in c.source_roles],
                    "conflicting_values": c.conflicting_values,
                    "resolved_value": c.resolved_value,
                    "resolution_rationale": c.resolution_rationale,
                }
                for c in self.conflicts_resolved
            ],
            "metadata": self.metadata,
            # Story 8.6: Degradation fields
            "degradation_level": self.degradation_level.value,
            "missing_perspectives": [r.value for r in self.missing_perspectives],
            "fallback_warnings": self.fallback_warnings,
        }


class DirectorEnsemble:
    """Ensemble coordinator for multi-model strategic analysis.
    
    Coordinates three LLM models (DeepSeek, Kimi K2, MiniMax M2) to provide
    multi-perspective strategic analysis for penetration testing operations.
    
    Uses a MixtureOfAgents-inspired pattern adapted for cyber-red:
    - Routes through LLMGateway for rate limiting and circuit breaker
    - Parallel query execution with per-model timeouts
    - Graceful degradation when individual models fail
    
    Example:
        >>> ensemble = DirectorEnsemble()
        >>> context = DirectorContext(
        ...     engagement_id="eng-001",
        ...     phase="exploitation",
        ...     prompt="Analyze attack strategy for discovered SSH service",
        ...     findings=[{"service": "ssh", "port": 22}]
        ... )
        >>> result = await ensemble.query_all(context)
        >>> print(result.get_content(DirectorRole.STRATEGIST))
    
    Attributes:
        models: Mapping of role to model configuration.
        aggregate_timeout: Maximum time for entire ensemble query.
    """

    # End-to-end timeout for a single Director ensemble cycle.
    DEFAULT_AGGREGATE_TIMEOUT = 420.0

    def __init__(
        self,
        models: Optional[Dict[DirectorRole, DirectorModel]] = None,
        aggregate_timeout: float = DEFAULT_AGGREGATE_TIMEOUT,
    ) -> None:
        """Initialize the Director Ensemble.
        
        Args:
            models: Optional custom model configurations. Defaults to DIRECTOR_MODELS.
            aggregate_timeout: Maximum time for entire ensemble query in seconds.
        """
        self._models = models or DIRECTOR_MODELS.copy()
        self._aggregate_timeout = aggregate_timeout
        failure_threshold = max(
            1,
            int(os.getenv("CYBERRED_DIRECTOR_CB_FAILURE_THRESHOLD", "3")),
        )
        exclusion_seconds = max(
            1.0,
            float(os.getenv("CYBERRED_DIRECTOR_CB_EXCLUSION_SECONDS", "180")),
        )
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            exclusion_seconds=exclusion_seconds,
        )
        
        # Validate all roles are configured
        for role in DirectorRole:
            if role not in self._models:
                raise ValueError(f"Missing model configuration for role: {role}")
        
        log.info(
            "director_ensemble_initialized",
            models=[m.model_id for m in self._models.values()],
            aggregate_timeout=aggregate_timeout,
            cb_failure_threshold=failure_threshold,
            cb_exclusion_seconds=exclusion_seconds,
        )

    @property
    def models(self) -> Dict[DirectorRole, DirectorModel]:
        """Return the model configurations."""
        return self._models.copy()

    @property
    def aggregate_timeout(self) -> float:
        """Return the aggregate timeout in seconds."""
        return self._aggregate_timeout

    def get_model(self, role: DirectorRole) -> DirectorModel:
        """Get model configuration for a specific role.
        
        Args:
            role: The director role.
            
        Returns:
            The model configuration for that role.
        """
        return self._models[role]

    def reset_role_circuit_breaker(self, role: DirectorRole) -> None:
        """Reset circuit-breaker state for a Director role."""
        self._circuit_breaker.reset(role)

    def get_availability_snapshot(self) -> Dict[str, Any]:
        """Return circuit-breaker availability state for all Director roles."""
        status: Dict[str, Any] = {}
        for role in DirectorRole:
            role_status = self._circuit_breaker.get_status(role)
            status[role.value] = {
                "state": role_status.state.value,
                "failure_count": role_status.failure_count,
                "excluded_until": role_status.excluded_until,
            }
        available_roles = self._circuit_breaker.get_available_roles()
        return {
            "available_roles": [role.value for role in available_roles],
            "available_count": len(available_roles),
            "roles": status,
        }

    async def query_model(
        self,
        role: DirectorRole,
        context: DirectorContext,
    ) -> ModelResponse:
        """Query a single Director model.
        
        Args:
            role: The role of the model to query.
            context: The query context.
            
        Returns:
            ModelResponse with the model's response or error.
        """
        model = self._models[role]
        start_time = time.monotonic()
        
        try:
            # Build the request
            request = LLMRequest(
                prompt=self._build_prompt(context),
                model=model.model_id,
                system_prompt=model.system_prompt,
                temperature=0.7,
                max_tokens=5000,
                timeout_budget_s=model.timeout,
            )
            
            # Route through gateway with Director priority
            gateway = get_gateway()
            
            # Gateway owns timeout budget enforcement.
            response: LLMResponse = await gateway.director_complete(request)
            
            latency_ms = int((time.monotonic() - start_time) * 1000)

            finish_reason = (response.finish_reason or "").strip().lower()
            if response.model == "error" or finish_reason.startswith("error:"):
                error_msg = response.finish_reason or "Gateway returned structured error response"
                log.warning(
                    "director_model_query_failed",
                    role=role.value,
                    model=model.model_id,
                    error=error_msg,
                    latency_ms=latency_ms,
                )
                return ModelResponse(
                    role=role,
                    model_id=model.model_id,
                    content="",
                    latency_ms=latency_ms,
                    success=False,
                    error=error_msg,
                )

            if not response.content.strip():
                error_msg = "Gateway returned empty content"
                log.warning(
                    "director_model_query_empty",
                    role=role.value,
                    model=model.model_id,
                    latency_ms=latency_ms,
                )
                return ModelResponse(
                    role=role,
                    model_id=model.model_id,
                    content="",
                    latency_ms=latency_ms,
                    success=False,
                    error=error_msg,
                    token_usage=response.usage,
                )
            
            log.debug(
                "director_model_query_success",
                role=role.value,
                model=model.model_id,
                latency_ms=latency_ms,
            )
            
            return ModelResponse(
                role=role,
                model_id=model.model_id,
                content=response.content,
                latency_ms=latency_ms,
                success=True,
                token_usage=response.usage,
            )
            
        except asyncio.CancelledError:
            # Re-raise CancelledError to allow proper task cancellation
            # This ensures clean shutdown when parent task is cancelled
            latency_ms = int((time.monotonic() - start_time) * 1000)
            log.info(
                "director_model_query_cancelled",
                role=role.value,
                model=model.model_id,
                latency_ms=latency_ms,
            )
            raise
            
        except (LLMTimeoutError, LLMProviderUnavailable) as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            error_msg = str(e)
            event_name = (
                "director_model_query_timeout"
                if isinstance(e, LLMTimeoutError)
                else "director_model_query_failed"
            )
            
            log.warning(
                event_name,
                role=role.value,
                model=model.model_id,
                error=error_msg,
                timeout=model.timeout if isinstance(e, LLMTimeoutError) else None,
            )
            
            return ModelResponse(
                role=role,
                model_id=model.model_id,
                content="",
                latency_ms=latency_ms,
                success=False,
                error=error_msg,
            )
            
        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            error_msg = f"{type(e).__name__}: {str(e)}"
            
            log.error(
                "director_model_query_error",
                role=role.value,
                model=model.model_id,
                error=error_msg,
            )
            
            return ModelResponse(
                role=role,
                model_id=model.model_id,
                content="",
                latency_ms=latency_ms,
                success=False,
                error=error_msg,
            )

    async def query_all(
        self,
        context: DirectorContext,
    ) -> DirectorQueryResult:
        """Query all three models in parallel.
        
        Executes queries to all Director models concurrently using asyncio.gather().
        Individual model timeouts are respected, and failures don't block other models.
        
        Args:
            context: The query context.
            
        Returns:
            DirectorQueryResult with per-model responses and aggregate metrics.
        """
        start_time = time.monotonic()
        
        log.info(
            "director_ensemble_query_start",
            engagement_id=context.engagement_id,
            phase=context.phase,
        )

        available_roles = self._circuit_breaker.get_available_roles()
        excluded_roles = [role for role in DirectorRole if role not in available_roles]
        if excluded_roles:
            log.warning(
                "director_ensemble_degraded",
                engagement_id=context.engagement_id,
                available=[role.value for role in available_roles],
                excluded=[role.value for role in excluded_roles],
            )

        if not available_roles:
            now_latency_ms = int((time.monotonic() - start_time) * 1000)
            responses = {
                role: ModelResponse(
                    role=role,
                    model_id=self._models[role].model_id,
                    content="",
                    latency_ms=now_latency_ms,
                    success=False,
                    error="Model excluded by circuit breaker",
                )
                for role in DirectorRole
            }
            log.warning(
                "director_ensemble_no_available_models",
                engagement_id=context.engagement_id,
            )
            return DirectorQueryResult(
                context=context,
                responses=responses,
                total_latency_ms=now_latency_ms,
                successful_count=0,
                failed_count=len(DirectorRole),
            )

        # Create tasks only for currently-available roles.
        tasks = [self.query_model(role, context) for role in available_roles]
        
        # Execute in parallel with aggregate timeout
        try:
            results: List[ModelResponse] = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=False),
                timeout=self._aggregate_timeout,
            )
        except asyncio.TimeoutError:
            # Aggregate timeout hit - cancel remaining and collect what we have
            log.warning(
                "director_ensemble_aggregate_timeout",
                timeout=self._aggregate_timeout,
            )
            # Return empty results for queried models.
            results = [
                ModelResponse(
                    role=role,
                    model_id=self._models[role].model_id,
                    content="",
                    latency_ms=int((time.monotonic() - start_time) * 1000),
                    success=False,
                    error=f"Aggregate timeout after {self._aggregate_timeout}s",
                )
                for role in available_roles
            ]

        for response in results:
            if response.success:
                self._circuit_breaker.record_success(response.role)
            else:
                self._circuit_breaker.record_failure(response.role)

        for role in excluded_roles:
            results.append(
                ModelResponse(
                    role=role,
                    model_id=self._models[role].model_id,
                    content="",
                    latency_ms=int((time.monotonic() - start_time) * 1000),
                    success=False,
                    error="Model excluded by circuit breaker",
                )
            )
        
        # Build response mapping
        responses: Dict[DirectorRole, ModelResponse] = {
            r.role: r for r in results
        }
        
        total_latency_ms = int((time.monotonic() - start_time) * 1000)
        successful_count = sum(1 for r in results if r.success)
        failed_count = len(results) - successful_count
        
        log.info(
            "director_ensemble_query_complete",
            engagement_id=context.engagement_id,
            total_latency_ms=total_latency_ms,
            successful=successful_count,
            failed=failed_count,
        )
        
        return DirectorQueryResult(
            context=context,
            responses=responses,
            total_latency_ms=total_latency_ms,
            successful_count=successful_count,
            failed_count=failed_count,
        )

    def synthesize(
        self,
        synthesis_input: SynthesisInput,
    ) -> SynthesizedStrategy:
        """Synthesize responses into a unified strategy.
        
        Story 8.5: Full synthesis implementation using StrategySynthesizer.
        
        Parses the raw model responses from query_result and synthesizes them
        into a unified strategy with conflict resolution and confidence scoring.
        
        Args:
            synthesis_input: The synthesis input with query results.
            
        Returns:
            SynthesizedStrategy with unified objectives, actions, and rationale.
        """
        query_result = synthesis_input.query_result
        
        # Parse raw responses into structured format
        strategist_response: Optional[StrategistResponse] = None
        analyst_response: Optional[AnalystResponse] = None
        creative_response: Optional[CreativeResponse] = None
        
        # Parse strategist response
        strategist_raw = query_result.get_response(DirectorRole.STRATEGIST)
        if strategist_raw and strategist_raw.success and strategist_raw.content:
            strategist_response = self._parse_strategist_response(strategist_raw)
        
        # Parse analyst response
        analyst_raw = query_result.get_response(DirectorRole.ANALYST)
        if analyst_raw and analyst_raw.success and analyst_raw.content:
            analyst_response = self._parse_analyst_response(analyst_raw)
        
        # Parse creative response
        creative_raw = query_result.get_response(DirectorRole.CREATIVE)
        if creative_raw and creative_raw.success and creative_raw.content:
            creative_response = self._parse_creative_response(creative_raw)
        
        # Use StrategySynthesizer for full synthesis
        synthesizer = StrategySynthesizer()
        strategy = synthesizer.synthesize(
            strategist=strategist_response,
            analyst=analyst_response,
            creative=creative_response,
        )
        
        log.info(
            "director_synthesis_complete",
            contributing_roles=[r.value for r in strategy.contributing_roles],
            confidence=strategy.confidence,
            objectives_count=len(strategy.objectives),
            actions_count=len(strategy.actions),
        )
        
        return strategy

    async def query_strategist(
        self,
        context: DirectorContext,
        swarm_state: Optional[SwarmState] = None,
        findings_summary: Optional[FindingsSummary] = None,
        objective: Optional[str] = None,
    ) -> StrategistResponse:
        """Query DeepSeek strategist role with structured response parsing.
        
        Args:
            context: Base director context with engagement info.
            swarm_state: Current state of the agent swarm.
            findings_summary: Aggregated findings from engagement.
            objective: Current engagement objective.
            
        Returns:
            StrategistResponse with parsed strategic recommendations.
            
        Raises:
            LLMTimeoutError: If DeepSeek does not respond within 100s.
            LLMProviderUnavailable: If DeepSeek model is unavailable.
        """
        # Build enhanced prompt with swarm state, findings, objective
        enhanced_prompt = self._build_strategist_prompt(
            context, swarm_state, findings_summary, objective
        )
        
        # Create enhanced context with modified prompt
        strategist_context = DirectorContext(
            engagement_id=context.engagement_id,
            phase=context.phase,
            prompt=enhanced_prompt,
            findings=context.findings,
            constraints=context.constraints,
            previous_strategies=context.previous_strategies,
            metadata=context.metadata,
        )
        
        # Query strategist model
        model_response = await self.query_model(
            DirectorRole.STRATEGIST,
            strategist_context,
        )
        
        # If query failed, raise appropriate exception
        if not model_response.success:
            if "Timeout" in (model_response.error or ""):
                raise LLMTimeoutError(
                    f"Strategist query timeout: {model_response.error}",
                    timeout_seconds=self._models[DirectorRole.STRATEGIST].timeout,
                )
            else:
                raise LLMProviderUnavailable(
                    f"Strategist query failed: {model_response.error}"
                )
        
        # Parse structured response
        return self._parse_strategist_response(model_response)

    def _build_strategist_prompt(
        self,
        context: DirectorContext,
        swarm_state: Optional[SwarmState] = None,
        findings_summary: Optional[FindingsSummary] = None,
        objective: Optional[str] = None,
    ) -> str:
        """Build enhanced prompt for strategist with swarm state and findings.
        
        Args:
            context: Base director context.
            swarm_state: Current swarm state.
            findings_summary: Aggregated findings summary.
            objective: Engagement objective.
            
        Returns:
            Enhanced prompt string with strategist-specific context.
        """
        parts = [
            f"Engagement: {context.engagement_id}",
            f"Phase: {context.phase}",
        ]
        
        # Add swarm state if provided
        if swarm_state:
            parts.append("")
            parts.append("## Swarm State")
            parts.append(f"- Active Agents: {swarm_state.active_agents}")
            parts.append(f"- Current Phase: {swarm_state.phase}")
            parts.append(f"- Targets Scanned: {swarm_state.targets_scanned}")
            parts.append(f"- Findings Count: {swarm_state.findings_count}")
        
        # Add findings summary if provided
        if findings_summary:
            parts.append("")
            parts.append("## Findings Summary")
            parts.append(f"- Critical: {findings_summary.critical_count}")
            parts.append(f"- High: {findings_summary.high_count}")
            parts.append(f"- Medium: {findings_summary.medium_count}")
            if findings_summary.top_findings:
                parts.append("")
                parts.append("Top Findings:")
                for i, finding in enumerate(findings_summary.top_findings[:5], 1):
                    parts.append(f"{i}. {finding}")
        
        # Add objective if provided
        if objective:
            parts.append("")
            parts.append(f"## Objective")
            parts.append(objective)
        
        parts.append("")
        parts.append("## Strategic Query")
        parts.append(context.prompt)
        
        if context.constraints:
            parts.append("")
            parts.append("## Constraints")
            for key, value in context.constraints.items():
                parts.append(f"- {key}: {value}")
        
        if context.previous_strategies:
            parts.append("")
            parts.append("## Previous Strategies (for context)")
            for strategy in context.previous_strategies[:5]:
                parts.append(f"- {strategy}")
        
        return "\n".join(parts)

    def _parse_strategist_response(self, model_response: ModelResponse) -> StrategistResponse:
        """Parse strategist model response into structured format.
        
        Args:
            model_response: The raw model response.
            
        Returns:
            StrategistResponse with extracted structured data.
        """
        content = model_response.content
        
        # Extract recommendations
        recommendations = self._extract_section_list(content, "Strategic Recommendations")
        
        # Extract next phases
        next_phases = self._extract_section_list(content, "Next Phases")
        
        # Extract priorities from table
        priorities = self._extract_priorities(content)
        
        # Extract ATT&CK techniques
        attck_techniques = extract_attck_techniques(content)
        
        # Extract confidence score
        confidence = self._extract_confidence(content)
        
        return StrategistResponse(
            raw_content=content,
            recommendations=recommendations,
            next_phases=next_phases,
            priorities=priorities,
            attck_techniques=attck_techniques,
            confidence=confidence,
            model_response=model_response,
        )

    def _extract_section_list(self, content: str, section_name: str) -> List[str]:
        """Extract list items from a named section.
        
        Args:
            content: The response content.
            section_name: The section header to find.
            
        Returns:
            List of extracted items.
        """
        items: List[str] = []
        
        # Find section header
        pattern = re.compile(rf'###\s*{re.escape(section_name)}(.+?)(?=###|$)', re.DOTALL | re.IGNORECASE)
        match = pattern.search(content)
        
        if match:
            section_content = match.group(1)
            
            # Extract numbered items (1. Item)
            numbered = re.findall(r'^\s*\d+\.\s*(.+?)(?=^\s*\d+\.|$)', section_content, re.MULTILINE | re.DOTALL)
            items.extend([item.strip() for item in numbered])
            
            # Extract bulleted items (- Item)
            bulleted = re.findall(r'^\s*[-*]\s*(.+?)(?=^\s*[-*]|$)', section_content, re.MULTILINE | re.DOTALL)
            items.extend([item.strip() for item in bulleted])
        
        return items

    def _extract_priorities(self, content: str) -> List[Tuple[str, int]]:
        """Extract priorities from table format.
        
        Args:
            content: The response content.
            
        Returns:
            List of (target, priority_score) tuples.
        """
        priorities: List[Tuple[str, int]] = []
        
        # Find Target Priorities section
        pattern = re.compile(r'###\s*Target Priorities(.+?)(?=###|$)', re.DOTALL | re.IGNORECASE)
        match = pattern.search(content)
        
        if match:
            section_content = match.group(1)
            
            # Extract table rows (skip header and separator)
            rows = re.findall(r'^\s*\|\s*(\d+)\s*\|\s*([^|]+)\s*\|', section_content, re.MULTILINE)
            
            for priority_str, target in rows:
                try:
                    priority = int(priority_str)
                    priorities.append((target.strip(), priority))
                except ValueError:
                    continue
        
        return priorities

    def _extract_confidence(self, content: str) -> float:
        """Extract confidence score from response.
        
        Args:
            content: The response content.
            
        Returns:
            Confidence score 0.0-1.0, defaults to 0.5 if not found.
        """
        # Find Confidence Assessment section
        pattern = re.compile(r'###\s*Confidence Assessment\s*\n\s*([0-9.]+)', re.IGNORECASE)
        match = pattern.search(content)
        
        if match:
            try:
                confidence = float(match.group(1))
                # Clamp to valid range
                return max(0.0, min(1.0, confidence))
            except ValueError:
                pass
        
        # Default confidence if not found
        return 0.5

    async def query_analyst(
        self,
        context: DirectorContext,
        findings_details: Optional[List[FindingDetail]] = None,
        target_environment: Optional[TargetEnvironment] = None,
        discovered_paths: Optional[List[AttackPath]] = None,
    ) -> AnalystResponse:
        """Query Kimi K2 analyst role with structured response parsing.
        
        Args:
            context: Base director context with engagement info.
            findings_details: Detailed findings from engagement.
            target_environment: Information about target environment.
            discovered_paths: Known attack vectors/paths.
            
        Returns:
            AnalystResponse with parsed analysis results.
            
        Raises:
            LLMTimeoutError: If Kimi K2 does not respond within 100s.
            LLMProviderUnavailable: If Kimi K2 model is unavailable.
        """
        # Build enhanced prompt with findings, environment, paths
        enhanced_prompt = self._build_analyst_prompt(
            context, findings_details, target_environment, discovered_paths
        )
        
        # Create enhanced context with modified prompt
        analyst_context = DirectorContext(
            engagement_id=context.engagement_id,
            phase=context.phase,
            prompt=enhanced_prompt,
            findings=context.findings,
            constraints=context.constraints,
            previous_strategies=context.previous_strategies,
            metadata=context.metadata,
        )
        
        # Query analyst model
        model_response = await self.query_model(
            DirectorRole.ANALYST,
            analyst_context,
        )
        
        # If query failed, raise appropriate exception
        if not model_response.success:
            if "Timeout" in (model_response.error or ""):
                raise LLMTimeoutError(
                    f"Analyst query timeout: {model_response.error}",
                    timeout_seconds=self._models[DirectorRole.ANALYST].timeout,
                )
            else:
                raise LLMProviderUnavailable(
                    f"Analyst query failed: {model_response.error}"
                )
        
        # Parse structured response
        return self._parse_analyst_response(model_response)

    def _build_analyst_prompt(
        self,
        context: DirectorContext,
        findings_details: Optional[List[FindingDetail]] = None,
        target_environment: Optional[TargetEnvironment] = None,
        discovered_paths: Optional[List[AttackPath]] = None,
    ) -> str:
        """Build enhanced prompt for analyst with findings, environment, and paths.
        
        Args:
            context: Base director context.
            findings_details: Detailed findings list.
            target_environment: Target environment info.
            discovered_paths: Known attack paths.
            
        Returns:
            Enhanced prompt string with analyst-specific context.
        """
        parts = [
            f"Engagement: {context.engagement_id}",
            f"Phase: {context.phase}",
        ]
        
        # Add findings details if provided
        if findings_details:
            parts.append("")
            parts.append("## Findings Details")
            for finding in findings_details[:10]:
                parts.append(f"- **{finding.finding_id}** [{finding.severity}]: {finding.description}")
                parts.append(f"  - Target: {finding.target}, Service: {finding.service}")
                parts.append(f"  - Type: {finding.finding_type}")
                if finding.evidence:
                    parts.append(f"  - Evidence: {finding.evidence[:100]}...")
        
        # Add target environment if provided
        if target_environment:
            parts.append("")
            parts.append("## Target Environment")
            parts.append(f"- Environment Type: {target_environment.environment_type}")
            parts.append(f"- Discovered Hosts: {target_environment.discovered_hosts}")
            parts.append(f"- Discovered Services: {target_environment.discovered_services}")
            if target_environment.os_distribution:
                os_str = ", ".join(f"{k}: {v}" for k, v in target_environment.os_distribution.items())
                parts.append(f"- OS Distribution: {os_str}")
            if target_environment.network_segments:
                parts.append(f"- Network Segments: {', '.join(target_environment.network_segments)}")
        
        # Add discovered paths if provided
        if discovered_paths:
            parts.append("")
            parts.append("## Discovered Attack Paths")
            for path in discovered_paths[:5]:
                parts.append(f"- **{path.path_id}**: {path.entry_point} → {path.target_asset}")
                parts.append(f"  - Steps: {' → '.join(path.steps)}")
                parts.append(f"  - Success Probability: {path.success_probability:.0%}")
        
        parts.append("")
        parts.append("## Analysis Query")
        parts.append(context.prompt)
        
        if context.constraints:
            parts.append("")
            parts.append("## Constraints")
            for key, value in context.constraints.items():
                parts.append(f"- {key}: {value}")
        
        return "\n".join(parts)

    def _parse_analyst_response(self, model_response: ModelResponse) -> AnalystResponse:
        """Parse analyst model response into structured format.
        
        Args:
            model_response: The raw model response.
            
        Returns:
            AnalystResponse with extracted structured data.
        """
        content = model_response.content
        
        # Extract attack surface analysis section
        attack_surface_analysis = self._extract_attack_surface_analysis(content)
        
        # Extract risk assessment
        risk_assessment = extract_risk_assessment(content)
        
        # Extract security gaps
        gaps = extract_gaps(content)
        
        # Extract overlooked opportunities
        overlooked_opportunities = extract_opportunities(content)
        
        return AnalystResponse(
            raw_content=content,
            attack_surface_analysis=attack_surface_analysis,
            risk_assessment=risk_assessment,
            gaps=gaps,
            overlooked_opportunities=overlooked_opportunities,
            model_response=model_response,
        )

    def _extract_attack_surface_analysis(self, content: str) -> str:
        """Extract attack surface analysis section from response.
        
        Args:
            content: The response content.
            
        Returns:
            Attack surface analysis text, or empty string if not found.
        """
        pattern = re.compile(r'###\s*Attack Surface Analysis(.+?)(?=###|$)', re.DOTALL | re.IGNORECASE)
        match = pattern.search(content)
        
        if match:
            return match.group(1).strip()
        
        return ""

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
        
        # Create enhanced context with modified prompt
        creative_context = DirectorContext(
            engagement_id=context.engagement_id,
            phase=context.phase,
            prompt=enhanced_prompt,
            findings=context.findings,
            constraints=context.constraints,
            previous_strategies=context.previous_strategies,
            metadata=context.metadata,
        )
        
        # Query creative model
        model_response = await self.query_model(
            DirectorRole.CREATIVE,
            creative_context,
        )
        
        # If query failed, raise appropriate exception
        if not model_response.success:
            if "Timeout" in (model_response.error or ""):
                raise LLMTimeoutError(
                    f"Creative query timeout: {model_response.error}",
                    timeout_seconds=self._models[DirectorRole.CREATIVE].timeout,
                )
            else:
                raise LLMProviderUnavailable(
                    f"Creative query failed: {model_response.error}"
                )
        
        # Parse structured response
        return self._parse_creative_response(model_response)

    def _build_creative_prompt(
        self,
        context: DirectorContext,
        current_strategy: Optional[CurrentStrategy] = None,
        defenses_encountered: Optional[List[DefenseEncountered]] = None,
        failed_attempts: Optional[List[FailedAttempt]] = None,
    ) -> str:
        """Build enhanced prompt for creative with strategy, defenses, and failed attempts.
        
        Args:
            context: Base director context.
            current_strategy: Current engagement strategy.
            defenses_encountered: Defenses observed.
            failed_attempts: Failed approaches.
            
        Returns:
            Enhanced prompt string with creative-specific context.
        """
        parts = [
            f"Engagement: {context.engagement_id}",
            f"Phase: {context.phase}",
        ]
        
        # Add current strategy if provided
        if current_strategy:
            parts.append("")
            parts.append("## Current Strategy")
            parts.append(f"- Strategy ID: {current_strategy.strategy_id}")
            parts.append(f"- Description: {current_strategy.description}")
            parts.append(f"- Phase: {current_strategy.phase}")
            if current_strategy.objectives:
                parts.append(f"- Objectives: {', '.join(current_strategy.objectives)}")
            if current_strategy.techniques_in_use:
                parts.append(f"- Techniques in use: {', '.join(current_strategy.techniques_in_use)}")
        
        # Add defenses encountered if provided
        if defenses_encountered:
            parts.append("")
            parts.append("## Defenses Encountered")
            for defense in defenses_encountered[:10]:
                parts.append(f"- **{defense.defense_id}** [{defense.defense_type}]: {defense.description}")
                parts.append(f"  - Target: {defense.target}")
                if defense.blocking_technique:
                    parts.append(f"  - Blocking Technique: {defense.blocking_technique}")
        
        # Add failed attempts if provided
        if failed_attempts:
            parts.append("")
            parts.append("## Failed Attempts")
            for attempt in failed_attempts[:10]:
                parts.append(f"- **{attempt.attempt_id}**: {attempt.technique} → {attempt.target}")
                parts.append(f"  - Failure Reason: {attempt.failure_reason}")
                parts.append(f"  - Timestamp: {attempt.timestamp}")
        
        parts.append("")
        parts.append("## Creative Query")
        parts.append(context.prompt)
        
        if context.constraints:
            parts.append("")
            parts.append("## Constraints")
            for key, value in context.constraints.items():
                parts.append(f"- {key}: {value}")
        
        return "\n".join(parts)

    def _parse_creative_response(self, model_response: ModelResponse) -> CreativeResponse:
        """Parse creative model response into structured format.
        
        Args:
            model_response: The raw model response.
            
        Returns:
            CreativeResponse with extracted structured data.
        """
        content = model_response.content
        
        # Extract thinking content
        thinking_content = extract_thinking_tags(content)
        
        # Strip thinking tags for clean content
        clean_content = strip_thinking_tags(content)
        
        # Extract creative elements
        creative_alternatives = extract_creative_alternatives(content)
        evasion_techniques = extract_evasion_techniques(content)
        novel_approaches = extract_novel_approaches(content)
        
        return CreativeResponse(
            raw_content=content,
            clean_content=clean_content,
            thinking_content=thinking_content,
            creative_alternatives=creative_alternatives,
            evasion_techniques=evasion_techniques,
            novel_approaches=novel_approaches,
            model_response=model_response,
        )

    def _build_prompt(self, context: DirectorContext) -> str:
        """Build the prompt for a Director model query.
        
        Args:
            context: The query context.
            
        Returns:
            Formatted prompt string.
        """
        parts = [
            f"Engagement: {context.engagement_id}",
            f"Phase: {context.phase}",
            "",
            "## Query",
            context.prompt,
        ]
        
        if context.findings:
            parts.append("")
            parts.append("## Current Findings")
            for i, finding in enumerate(context.findings[:10], 1):
                # Handle both dict and dataclass findings
                if hasattr(finding, 'target') and hasattr(finding, 'finding_type'):
                    # Dataclass (AggregatedFinding or similar) - format nicely
                    target = getattr(finding, 'target', 'unknown')
                    finding_type = getattr(finding, 'finding_type', 'unknown')
                    severity = getattr(finding, 'severity', 'unknown')
                    # Handle enum - use name for readability
                    if hasattr(severity, 'name'):
                        severity = severity.name
                    finding_str = f"[{severity}] {finding_type} on {target}"
                    # Add metadata if present
                    metadata = getattr(finding, 'metadata', {})
                    if metadata:
                        meta_str = ", ".join(f"{k}={v}" for k, v in list(metadata.items())[:3])
                        finding_str += f" ({meta_str})"
                elif isinstance(finding, dict):
                    # Dict - format key fields
                    target = finding.get('target', 'unknown')
                    finding_type = finding.get('finding_type', finding.get('type', 'unknown'))
                    severity = finding.get('severity', 'unknown')
                    finding_str = f"[{severity}] {finding_type} on {target}"
                else:
                    finding_str = str(finding)
                parts.append(f"{i}. {finding_str}")
        
        if context.constraints:
            parts.append("")
            parts.append("## Constraints")
            for key, value in context.constraints.items():
                parts.append(f"- {key}: {value}")
        
        if context.previous_strategies:
            parts.append("")
            parts.append("## Previous Strategies (for context)")
            for strategy in context.previous_strategies[:5]:
                parts.append(f"- {strategy}")
        
        return "\n".join(parts)


# Story 8.2: DeepSeek Strategist Role Support


# Story 8.3: Kimi K2 Analyst Role Support


@dataclass
class SecurityGap:
    """Security gap identified by analyst.
    
    Attributes:
        gap_id: Unique identifier (e.g., "GAP-001").
        description: Description of the gap.
        severity: CRITICAL, HIGH, MEDIUM, LOW, or INFO.
        affected_assets: Assets affected by this gap.
        
    Raises:
        ValueError: If gap_id or description is empty, or severity is invalid.
    """
    gap_id: str
    description: str
    severity: str
    affected_assets: List[str]
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not self.gap_id or not self.gap_id.strip():
            raise ValueError("gap_id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")
        if self.severity not in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            raise ValueError(f"Invalid severity: {self.severity}")


@dataclass
class OverlookedOpportunity:
    """Overlooked attack opportunity identified by analyst.
    
    Attributes:
        opportunity_id: Unique identifier (e.g., "OPP-001").
        description: Description of the opportunity.
        potential_impact: Expected impact if exploited.
        recommended_action: Recommended next step.
        confidence: Confidence score 0.0-1.0.
        
    Raises:
        ValueError: If opportunity_id or description is empty, or confidence out of range.
    """
    opportunity_id: str
    description: str
    potential_impact: str
    recommended_action: str
    confidence: float
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not self.opportunity_id or not self.opportunity_id.strip():
            raise ValueError("opportunity_id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")


@dataclass
class RiskAssessment:
    """Overall risk assessment from analyst.
    
    Attributes:
        overall_risk_level: CRITICAL, HIGH, MEDIUM, LOW, or INFO.
        risk_factors: Contributing risk factors.
        mitigations_needed: Recommended mitigations.
        confidence: Confidence score 0.0-1.0.
        
    Raises:
        ValueError: If risk level is invalid or confidence out of range.
    """
    overall_risk_level: str
    risk_factors: List[str]
    mitigations_needed: List[str]
    confidence: float
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if self.overall_risk_level not in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            raise ValueError(f"Invalid risk level: {self.overall_risk_level}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")


@dataclass
class FindingDetail:
    """Detailed finding information for analyst context.
    
    Attributes:
        finding_id: Unique finding identifier.
        finding_type: Type (e.g., "vulnerability", "misconfiguration", "exposure").
        target: Target IP/hostname.
        service: Affected service.
        severity: CRITICAL, HIGH, MEDIUM, LOW, or INFO.
        description: Finding description.
        evidence: Optional evidence string.
        
    Raises:
        ValueError: If finding_id is empty or severity is invalid.
    """
    finding_id: str
    finding_type: str
    target: str
    service: str
    severity: str
    description: str
    evidence: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not self.finding_id or not self.finding_id.strip():
            raise ValueError("finding_id cannot be empty")
        if self.severity not in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            raise ValueError(f"Invalid severity: {self.severity}")


@dataclass
class TargetEnvironment:
    """Target environment information for analyst context.
    
    Attributes:
        environment_type: Environment type (e.g., "corporate", "cloud", "hybrid", "ot").
        discovered_hosts: Number of discovered hosts.
        discovered_services: Number of discovered services.
        os_distribution: OS type to count mapping.
        network_segments: Identified network segments.
        
    Raises:
        ValueError: If counts are negative.
    """
    environment_type: str
    discovered_hosts: int
    discovered_services: int
    os_distribution: Dict[str, int]
    network_segments: List[str]
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if self.discovered_hosts < 0:
            raise ValueError("discovered_hosts cannot be negative")
        if self.discovered_services < 0:
            raise ValueError("discovered_services cannot be negative")


@dataclass
class AttackPath:
    """Discovered attack path for analyst context.
    
    Attributes:
        path_id: Unique path identifier.
        entry_point: Initial entry point.
        steps: Steps in the attack path.
        target_asset: Final target.
        success_probability: Success probability 0.0-1.0.
        
    Raises:
        ValueError: If path_id is empty or probability out of range.
    """
    path_id: str
    entry_point: str
    steps: List[str]
    target_asset: str
    success_probability: float
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not self.path_id or not self.path_id.strip():
            raise ValueError("path_id cannot be empty")
        if not 0.0 <= self.success_probability <= 1.0:
            raise ValueError(f"success_probability must be 0.0-1.0, got {self.success_probability}")


@dataclass
class AnalystResponse:
    """Structured response from Kimi K2 analyst role.
    
    Attributes:
        raw_content: Original response from the model.
        attack_surface_analysis: Full attack surface analysis text.
        risk_assessment: Structured risk assessment.
        gaps: Identified security gaps.
        overlooked_opportunities: Overlooked attack paths.
        model_response: Underlying model response metadata.
    """
    raw_content: str
    attack_surface_analysis: str
    risk_assessment: RiskAssessment
    gaps: List[SecurityGap]
    overlooked_opportunities: List[OverlookedOpportunity]
    model_response: ModelResponse


@dataclass
class SwarmState:
    """Current swarm state for strategist context.
    
    Attributes:
        active_agents: Number of currently active agents.
        phase: Current engagement phase.
        targets_scanned: Number of targets scanned.
        findings_count: Total number of findings.
        
    Raises:
        ValueError: If any count is negative or phase is empty.
    """
    active_agents: int
    phase: str
    targets_scanned: int
    findings_count: int
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if self.active_agents < 0:
            raise ValueError("active_agents cannot be negative")
        if not self.phase or not self.phase.strip():
            raise ValueError("phase cannot be empty")
        if self.targets_scanned < 0:
            raise ValueError("targets_scanned cannot be negative")
        if self.findings_count < 0:
            raise ValueError("findings_count cannot be negative")


@dataclass
class FindingsSummary:
    """Aggregated findings summary for strategist context.
    
    Attributes:
        critical_count: Number of critical findings.
        high_count: Number of high severity findings.
        medium_count: Number of medium severity findings.
        top_findings: List of top findings descriptions.
        
    Raises:
        ValueError: If any count is negative.
    """
    critical_count: int
    high_count: int
    medium_count: int
    top_findings: List[str]
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if self.critical_count < 0:
            raise ValueError("critical_count cannot be negative")
        if self.high_count < 0:
            raise ValueError("high_count cannot be negative")
        if self.medium_count < 0:
            raise ValueError("medium_count cannot be negative")


@dataclass
class ATTCKRecommendation:
    """ATT&CK technique recommendation from strategist.
    
    Attributes:
        technique_id: ATT&CK technique ID (e.g., "T1566.001").
        technique_name: Human-readable technique name.
        rationale: Why this technique is recommended.
        phase: Kill chain phase (recon, exploit, postex).
    """
    technique_id: str
    technique_name: str
    rationale: str
    phase: str
    
    def __post_init__(self) -> None:
        """Validate technique_id format."""
        if not self.technique_id or not self.technique_id.strip():
            raise ValueError("technique_id cannot be empty")
        # Validate ATT&CK ID format: T#### or T####.###
        if not re.match(r'^T\d{4}(?:\.\d{3})?$', self.technique_id):
            raise ValueError(f"Invalid ATT&CK technique ID format: {self.technique_id}")


@dataclass
class StrategistResponse:
    """Structured response from DeepSeek strategist role.
    
    Attributes:
        raw_content: Original response from the model.
        recommendations: List of strategic recommendations.
        next_phases: Recommended next phases to pursue.
        priorities: Target/action priorities with scores (higher = more important).
        attck_techniques: ATT&CK technique mappings.
        confidence: Confidence score 0.0-1.0.
        model_response: Underlying model response metadata.
    """
    raw_content: str
    recommendations: List[str]
    next_phases: List[str]
    priorities: List[Tuple[str, int]]
    attck_techniques: List[ATTCKRecommendation]
    confidence: float
    model_response: ModelResponse
    
    def __post_init__(self) -> None:
        """Validate confidence score."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")


def extract_gaps(response: str) -> List[SecurityGap]:
    """Extract security gaps from response text.
    
    Parses markdown tables with format:
    | Gap ID | Description | Severity | Affected Assets |
    
    Args:
        response: The response text to parse.
        
    Returns:
        List of SecurityGap objects extracted from the response.
    """
    gaps: List[SecurityGap] = []
    
    # Find Security Gaps section
    pattern = re.compile(r'###\s*Security Gaps(.+?)(?=###|$)', re.DOTALL | re.IGNORECASE)
    match = pattern.search(response)
    
    if not match:
        return gaps
    
    section_content = match.group(1)
    
    # Extract table rows: | GAP-XXX | Description | Severity | Assets |
    # Use IGNORECASE to handle LLM responses with lowercase gap-xxx
    row_pattern = re.compile(
        r'^\s*\|\s*(GAP-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|',
        re.MULTILINE | re.IGNORECASE
    )
    
    for row_match in row_pattern.finditer(section_content):
        gap_id, description, severity, assets_str = row_match.groups()
        
        # Clean up values and normalize case
        gap_id = gap_id.strip().upper()  # Normalize to uppercase
        description = description.strip()
        severity = severity.strip().upper()
        
        # Parse assets (comma-separated)
        affected_assets = [a.strip() for a in assets_str.split(',') if a.strip()]
        
        # Validate severity
        if severity not in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            log.warning(
                "invalid_gap_severity",
                gap_id=gap_id,
                severity=severity,
            )
            continue
        
        try:
            gaps.append(SecurityGap(
                gap_id=gap_id,
                description=description,
                severity=severity,
                affected_assets=affected_assets,
            ))
        except ValueError as e:
            log.warning(
                "invalid_security_gap",
                gap_id=gap_id,
                error=str(e),
            )
            continue
    
    return gaps


def extract_opportunities(response: str) -> List[OverlookedOpportunity]:
    """Extract overlooked opportunities from response text.
    
    Parses markdown tables with format:
    | Opportunity ID | Description | Potential Impact | Recommended Action | Confidence |
    
    Args:
        response: The response text to parse.
        
    Returns:
        List of OverlookedOpportunity objects extracted from the response.
    """
    opportunities: List[OverlookedOpportunity] = []
    
    # Find Overlooked Opportunities section
    pattern = re.compile(r'###\s*Overlooked Opportunities(.+?)(?=###|$)', re.DOTALL | re.IGNORECASE)
    match = pattern.search(response)
    
    if not match:
        return opportunities
    
    section_content = match.group(1)
    
    # Extract table rows
    # Use IGNORECASE to handle LLM responses with lowercase opp-xxx
    row_pattern = re.compile(
        r'^\s*\|\s*(OPP-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|',
        re.MULTILINE | re.IGNORECASE
    )
    
    for row_match in row_pattern.finditer(section_content):
        opp_id, description, impact, action, confidence_str = row_match.groups()
        
        # Clean up values and normalize case
        opp_id = opp_id.strip().upper()  # Normalize to uppercase
        description = description.strip()
        impact = impact.strip()
        action = action.strip()
        
        # Parse confidence
        try:
            confidence = float(confidence_str.strip())
        except ValueError:
            log.warning(
                "invalid_opportunity_confidence",
                opportunity_id=opp_id,
                confidence_str=confidence_str,
            )
            continue
        
        try:
            opportunities.append(OverlookedOpportunity(
                opportunity_id=opp_id,
                description=description,
                potential_impact=impact,
                recommended_action=action,
                confidence=confidence,
            ))
        except ValueError as e:
            log.warning(
                "invalid_overlooked_opportunity",
                opportunity_id=opp_id,
                error=str(e),
            )
            continue
    
    return opportunities


def extract_risk_assessment(response: str) -> RiskAssessment:
    """Extract risk assessment from response text.
    
    Parses structured format:
    ### Risk Assessment
    **Overall Risk Level:** HIGH
    **Risk Factors:**
    - Factor 1
    **Mitigations Needed:**
    - Mitigation 1
    **Confidence:** 0.85
    
    Args:
        response: The response text to parse.
        
    Returns:
        RiskAssessment with extracted or default values.
    """
    # Default values
    overall_risk_level = "MEDIUM"
    risk_factors: List[str] = []
    mitigations_needed: List[str] = []
    confidence = 0.5
    
    # Find Risk Assessment section
    pattern = re.compile(r'###\s*Risk Assessment(.+?)(?=###|$)', re.DOTALL | re.IGNORECASE)
    match = pattern.search(response)
    
    if not match:
        return RiskAssessment(
            overall_risk_level=overall_risk_level,
            risk_factors=risk_factors,
            mitigations_needed=mitigations_needed,
            confidence=confidence,
        )
    
    section_content = match.group(1)
    
    # Extract overall risk level
    risk_level_pattern = re.compile(r'\*\*Overall Risk Level:\*\*\s*(\w+)', re.IGNORECASE)
    risk_match = risk_level_pattern.search(section_content)
    if risk_match:
        level = risk_match.group(1).strip().upper()
        if level in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            overall_risk_level = level
    
    # Extract risk factors
    risk_factors_pattern = re.compile(
        r'\*\*Risk Factors:\*\*(.+?)(?=\*\*|$)', re.DOTALL | re.IGNORECASE
    )
    rf_match = risk_factors_pattern.search(section_content)
    if rf_match:
        rf_content = rf_match.group(1)
        # Extract bullet points
        factors = re.findall(r'^\s*[-*]\s*(.+?)$', rf_content, re.MULTILINE)
        risk_factors = [f.strip() for f in factors if f.strip()]
    
    # Extract mitigations needed
    mitigations_pattern = re.compile(
        r'\*\*Mitigations Needed:\*\*(.+?)(?=\*\*|$)', re.DOTALL | re.IGNORECASE
    )
    mit_match = mitigations_pattern.search(section_content)
    if mit_match:
        mit_content = mit_match.group(1)
        # Extract bullet points
        mitigations = re.findall(r'^\s*[-*]\s*(.+?)$', mit_content, re.MULTILINE)
        mitigations_needed = [m.strip() for m in mitigations if m.strip()]
    
    # Extract confidence
    confidence_pattern = re.compile(r'\*\*Confidence:\*\*\s*([0-9.]+)', re.IGNORECASE)
    conf_match = confidence_pattern.search(section_content)
    if conf_match:
        try:
            conf_value = float(conf_match.group(1))
            confidence = max(0.0, min(1.0, conf_value))
        except ValueError:
            pass
    
    return RiskAssessment(
        overall_risk_level=overall_risk_level,
        risk_factors=risk_factors,
        mitigations_needed=mitigations_needed,
        confidence=confidence,
    )


def extract_attck_techniques(response: str) -> List[ATTCKRecommendation]:
    """Extract ATT&CK technique references from response text.
    
    Supports formats:
    - T1566 (main technique)
    - T1566.001 (sub-technique)
    - Full sentences like "T1566.001 - Spearphishing Attachment: rationale"
    
    Args:
        response: The response text to parse.
        
    Returns:
        List of ATTCKRecommendation objects extracted from the response.
    """
    recommendations: List[ATTCKRecommendation] = []
    
    # Pattern for structured ATT&CK mentions with name and rationale
    # Format: T####[.###] - Technique Name: Rationale text
    structured_pattern = re.compile(
        r'([Tt]\d{4}(?:\.\d{3})?)\s*[-–]\s*([^:]+):\s*(.+?)(?=[Tt]\d{4}|$)',
        re.DOTALL
    )
    
    for match in structured_pattern.finditer(response):
        technique_id, technique_name, rationale = match.groups()
        
        # Normalize technique_id to uppercase
        technique_id = technique_id.upper()
        
        # Clean up whitespace
        technique_name = technique_name.strip()
        rationale = rationale.strip()
        
        # Remove trailing punctuation from rationale
        rationale = rationale.rstrip('.,;')
        
        try:
            recommendations.append(ATTCKRecommendation(
                technique_id=technique_id,
                technique_name=technique_name,
                rationale=rationale,
                phase="unknown",  # Can be inferred from context in future
            ))
        except ValueError as e:
            # Skip invalid technique IDs
            log.warning(
                "invalid_attck_technique_id",
                technique_id=technique_id,
                error=str(e),
            )
            continue
    
    return recommendations


# Story 8.4: MiniMax M2 Creative Role Support


@dataclass
class ThinkingContent:
    """Extracted thinking content from MiniMax M2 response.
    
    MiniMax M2 uses interleaved thinking with <think>...</think> tags
    to show its reasoning process. These are preserved for visibility.
    
    Attributes:
        content: The thinking content inside tags.
        position: Character position in original response.
        
    Raises:
        ValueError: If content is empty or position is negative.
    """
    content: str
    position: int
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not self.content or not self.content.strip():
            raise ValueError("content cannot be empty")
        if self.position < 0:
            raise ValueError("position cannot be negative")


@dataclass
class CreativeAlternative:
    """Creative alternative approach identified by MiniMax M2.
    
    Attributes:
        alternative_id: Unique identifier (e.g., "ALT-001").
        description: Description of the alternative.
        rationale: Why this alternative might work.
        novelty_score: 0.0-1.0 novelty/creativity score.
        
    Raises:
        ValueError: If alternative_id or description is empty, or novelty_score out of range.
    """
    alternative_id: str
    description: str
    rationale: str
    novelty_score: float
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not self.alternative_id or not self.alternative_id.strip():
            raise ValueError("alternative_id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")
        if not self.rationale or not self.rationale.strip():
            raise ValueError("rationale cannot be empty")
        if not 0.0 <= self.novelty_score <= 1.0:
            raise ValueError(f"novelty_score must be 0.0-1.0, got {self.novelty_score}")


@dataclass
class EvasionTechnique:
    """Evasion technique for bypassing encountered defenses.
    
    Attributes:
        technique_id: Unique identifier (e.g., "EVA-001").
        description: Description of the evasion technique.
        target_defense: The defense this technique targets.
        success_likelihood: 0.0-1.0 estimated success probability.
        
    Raises:
        ValueError: If technique_id, description, or target_defense is empty,
                   or success_likelihood out of range.
    """
    technique_id: str
    description: str
    target_defense: str
    success_likelihood: float
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not self.technique_id or not self.technique_id.strip():
            raise ValueError("technique_id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")
        if not self.target_defense or not self.target_defense.strip():
            raise ValueError("target_defense cannot be empty")
        if not 0.0 <= self.success_likelihood <= 1.0:
            raise ValueError(f"success_likelihood must be 0.0-1.0, got {self.success_likelihood}")


@dataclass
class NovelApproach:
    """Novel approach when standard methods have failed.
    
    Attributes:
        approach_id: Unique identifier (e.g., "NOV-001").
        description: Description of the novel approach.
        innovation_type: Type: "technique", "vector", "social", "physical", "hybrid".
        risk_level: CRITICAL, HIGH, MEDIUM, LOW.
        potential_impact: Expected impact if successful.
        
    Raises:
        ValueError: If approach_id or description is empty, or invalid innovation_type/risk_level.
    """
    approach_id: str
    description: str
    innovation_type: str
    risk_level: str
    potential_impact: str
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not self.approach_id or not self.approach_id.strip():
            raise ValueError("approach_id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")
        if self.innovation_type not in ("technique", "vector", "social", "physical", "hybrid"):
            raise ValueError(f"Invalid innovation_type: {self.innovation_type}")
        if self.risk_level not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            raise ValueError(f"Invalid risk_level: {self.risk_level}")


@dataclass
class CurrentStrategy:
    """Current engagement strategy for creative context.
    
    Attributes:
        strategy_id: Unique strategy identifier.
        description: Description of current strategy.
        phase: Current kill chain phase.
        objectives: Current objectives.
        techniques_in_use: ATT&CK techniques currently being used.
        
    Raises:
        ValueError: If strategy_id or description is empty.
    """
    strategy_id: str
    description: str
    phase: str
    objectives: List[str]
    techniques_in_use: List[str]
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not self.strategy_id or not self.strategy_id.strip():
            raise ValueError("strategy_id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")


@dataclass
class DefenseEncountered:
    """Defense mechanism encountered during engagement.
    
    Attributes:
        defense_id: Unique defense identifier.
        defense_type: e.g., "WAF", "IDS", "EDR", "firewall", "MFA".
        target: Where the defense was encountered.
        description: Description of the defense behavior.
        blocking_technique: Which technique it blocked (optional).
        
    Raises:
        ValueError: If defense_id or defense_type is empty.
    """
    defense_id: str
    defense_type: str
    target: str
    description: str
    blocking_technique: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not self.defense_id or not self.defense_id.strip():
            raise ValueError("defense_id cannot be empty")
        if not self.defense_type or not self.defense_type.strip():
            raise ValueError("defense_type cannot be empty")
        if not self.target or not self.target.strip():
            raise ValueError("target cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")


@dataclass
class FailedAttempt:
    """Failed attack attempt for creative context.
    
    Attributes:
        attempt_id: Unique attempt identifier.
        technique: Technique that was attempted.
        target: Target of the attempt.
        failure_reason: Why it failed.
        timestamp: When it was attempted.
        
    Raises:
        ValueError: If attempt_id, technique, or failure_reason is empty.
    """
    attempt_id: str
    technique: str
    target: str
    failure_reason: str
    timestamp: str
    
    def __post_init__(self) -> None:
        """Validate fields after initialization."""
        if not self.attempt_id or not self.attempt_id.strip():
            raise ValueError("attempt_id cannot be empty")
        if not self.technique or not self.technique.strip():
            raise ValueError("technique cannot be empty")
        if not self.target or not self.target.strip():
            raise ValueError("target cannot be empty")
        if not self.failure_reason or not self.failure_reason.strip():
            raise ValueError("failure_reason cannot be empty")
        if not self.timestamp or not self.timestamp.strip():
            raise ValueError("timestamp cannot be empty")


@dataclass
class CreativeResponse:
    """Structured response from MiniMax M2 creative role.
    
    Attributes:
        raw_content: Original response (with thinking tags).
        clean_content: Response with thinking tags stripped.
        thinking_content: Extracted thinking sections.
        creative_alternatives: Creative alternative approaches.
        evasion_techniques: Evasion techniques for defenses.
        novel_approaches: Novel approaches.
        model_response: Underlying model response.
    """
    raw_content: str
    clean_content: str
    thinking_content: List[ThinkingContent]
    creative_alternatives: List[CreativeAlternative]
    evasion_techniques: List[EvasionTechnique]
    novel_approaches: List[NovelApproach]
    model_response: ModelResponse


# Thinking tag pattern for MiniMax M2
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


def extract_creative_alternatives(response: str) -> List[CreativeAlternative]:
    """Extract creative alternatives from response text.
    
    Parses table format:
    | Alternative ID | Description | Rationale | Novelty Score |
    
    Args:
        response: The response text to parse.
        
    Returns:
        List of CreativeAlternative objects extracted from the response.
    """
    alternatives: List[CreativeAlternative] = []
    
    # Find Creative Alternatives section
    pattern = re.compile(r'###\s*Creative Alternatives(.+?)(?=###|$)', re.DOTALL | re.IGNORECASE)
    match = pattern.search(response)
    
    if not match:
        return alternatives
    
    section_content = match.group(1)
    
    # Extract table rows: | ALT-XXX | description | rationale | score |
    row_pattern = re.compile(
        r'^\s*\|\s*(ALT-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([0-9.]+)\s*\|',
        re.MULTILINE | re.IGNORECASE
    )
    
    for row_match in row_pattern.finditer(section_content):
        alt_id, description, rationale, score_str = row_match.groups()
        
        try:
            score = float(score_str.strip())
            # Clamp to valid range
            score = max(0.0, min(1.0, score))
            
            alternatives.append(CreativeAlternative(
                alternative_id=alt_id.strip().upper(),
                description=description.strip(),
                rationale=rationale.strip(),
                novelty_score=score,
            ))
        except (ValueError, TypeError) as e:
            log.warning(
                "invalid_creative_alternative",
                alternative_id=alt_id,
                error=str(e),
            )
            continue
    
    return alternatives


def extract_evasion_techniques(response: str) -> List[EvasionTechnique]:
    """Extract evasion techniques from response text.
    
    Parses table format:
    | Technique ID | Description | Target Defense | Success Likelihood |
    
    Args:
        response: The response text to parse.
        
    Returns:
        List of EvasionTechnique objects extracted from the response.
    """
    techniques: List[EvasionTechnique] = []
    
    # Find Evasion Techniques section
    pattern = re.compile(r'###\s*Evasion Techniques(.+?)(?=###|$)', re.DOTALL | re.IGNORECASE)
    match = pattern.search(response)
    
    if not match:
        return techniques
    
    section_content = match.group(1)
    
    # Extract table rows: | EVA-XXX | description | target_defense | likelihood |
    row_pattern = re.compile(
        r'^\s*\|\s*(EVA-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([0-9.]+)\s*\|',
        re.MULTILINE | re.IGNORECASE
    )
    
    for row_match in row_pattern.finditer(section_content):
        tech_id, description, target_defense, likelihood_str = row_match.groups()
        
        try:
            likelihood = float(likelihood_str.strip())
            # Clamp to valid range
            likelihood = max(0.0, min(1.0, likelihood))
            
            techniques.append(EvasionTechnique(
                technique_id=tech_id.strip().upper(),
                description=description.strip(),
                target_defense=target_defense.strip(),
                success_likelihood=likelihood,
            ))
        except (ValueError, TypeError) as e:
            log.warning(
                "invalid_evasion_technique",
                technique_id=tech_id,
                error=str(e),
            )
            continue
    
    return techniques


def extract_novel_approaches(response: str) -> List[NovelApproach]:
    """Extract novel approaches from response text.
    
    Parses table format:
    | Approach ID | Description | Innovation Type | Risk Level | Potential Impact |
    
    Args:
        response: The response text to parse.
        
    Returns:
        List of NovelApproach objects extracted from the response.
    """
    approaches: List[NovelApproach] = []

    innovation_aliases = {
        "technique": "technique",
        "techniques": "technique",
        "tactic": "technique",
        "tactics": "technique",
        "method": "technique",
        "methods": "technique",
        "vector": "vector",
        "vectors": "vector",
        "path": "vector",
        "pathway": "vector",
        "avenue": "vector",
        "social": "social",
        "socialengineering": "social",
        "human": "social",
        "physical": "physical",
        "hardware": "physical",
        "hybrid": "hybrid",
        "mixed": "hybrid",
        "multivector": "hybrid",
        "multistage": "hybrid",
    }
    risk_aliases = {
        "CRITICAL": "CRITICAL",
        "HIGH": "HIGH",
        "MEDIUM": "MEDIUM",
        "LOW": "LOW",
        "SEVERE": "CRITICAL",
        "MODERATE": "MEDIUM",
        "INFO": "LOW",
    }
    
    # Find Novel Approaches section
    pattern = re.compile(r'###\s*Novel Approaches(.+?)(?=###|$)', re.DOTALL | re.IGNORECASE)
    match = pattern.search(response)
    
    if not match:
        return approaches
    
    section_content = match.group(1)
    
    # Extract table rows: | NOV-XXX | description | innovation_type | risk_level | impact |
    row_pattern = re.compile(
        r'^\s*\|\s*(NOV-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|',
        re.MULTILINE | re.IGNORECASE
    )
    
    for row_match in row_pattern.finditer(section_content):
        approach_id, description, raw_innovation_type, raw_risk_level, impact = row_match.groups()

        innovation_key = re.sub(r"[^a-z0-9]+", "", raw_innovation_type.strip().lower())
        innovation_type = innovation_aliases.get(innovation_key)
        risk_key = re.sub(r"[^A-Z0-9]+", "", raw_risk_level.strip().upper())
        risk_level = risk_aliases.get(risk_key)
        
        # Validate innovation_type
        if innovation_type not in ("technique", "vector", "social", "physical", "hybrid"):
            log.warning(
                "invalid_novel_approach_innovation_type",
                approach_id=approach_id,
                innovation_type=raw_innovation_type.strip().lower(),
            )
            continue
        
        # Validate risk_level
        if risk_level not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            log.warning(
                "invalid_novel_approach_risk_level",
                approach_id=approach_id,
                risk_level=raw_risk_level.strip().upper(),
            )
            continue
        
        try:
            approaches.append(NovelApproach(
                approach_id=approach_id.strip().upper(),
                description=description.strip(),
                innovation_type=innovation_type,
                risk_level=risk_level,
                potential_impact=impact.strip(),
            ))
        except ValueError as e:
            log.warning(
                "invalid_novel_approach",
                approach_id=approach_id,
                error=str(e),
            )
            continue
    
    return approaches


class StrategySynthesizer:
    """Synthesizes multi-model responses into unified strategy.
    
    Story 8.5: Strategy Synthesis Engine.
    
    Combines insights from:
    - Strategist: objectives, priorities, ATT&CK techniques
    - Analyst: risk assessment, security gaps, overlooked opportunities
    - Creative: alternatives, evasion techniques, novel approaches
    
    Uses priority rules to resolve conflicts:
    1. Security warnings (highest)
    2. Scope constraints
    3. Strategic priorities
    4. Risk avoidance
    5. Creative alternatives (lowest)
    """

    def __init__(self) -> None:
        """Initialize the StrategySynthesizer."""
        log.info("strategy_synthesizer_initialized")

    def synthesize(
        self,
        strategist: Optional[StrategistResponse],
        analyst: Optional[AnalystResponse],
        creative: Optional[CreativeResponse],
    ) -> SynthesizedStrategy:
        """Synthesize all role responses into unified strategy.
        
        Args:
            strategist: Response from DeepSeek strategist role.
            analyst: Response from Kimi K2 analyst role.
            creative: Response from MiniMax M2 creative role.
            
        Returns:
            SynthesizedStrategy with unified objectives, actions, and rationale.
        """
        # Determine contributing roles
        contributing_roles: List[DirectorRole] = []
        if strategist:
            contributing_roles.append(DirectorRole.STRATEGIST)
        if analyst:
            contributing_roles.append(DirectorRole.ANALYST)
        if creative:
            contributing_roles.append(DirectorRole.CREATIVE)
        
        # Handle no responses case
        if not contributing_roles:
            log.warning("synthesis_no_model_responses")
            return SynthesizedStrategy(
                objectives=[],
                actions=[],
                rationale="No model responses available for synthesis.",
                confidence=0.0,
                contributing_roles=[],
                metadata={"synthesis_version": "8.5", "error": "no_responses"},
            )
        
        # Extract objectives from all roles
        objectives = self._extract_objectives(strategist, analyst, creative)
        
        # Extract actions from strategist and creative
        actions = self._extract_actions(strategist, creative)
        
        # Merge insights from analyst gaps with strategist priorities
        merged_insights = self._merge_insights(strategist, analyst)
        actions.extend(merged_insights)
        
        # Detect and resolve conflicts
        conflicts = self._detect_conflicts(strategist, analyst, creative)
        resolved_conflicts = self._resolve_conflicts(conflicts)
        
        # Calculate consensus score
        consensus = self._calculate_consensus(strategist, analyst, creative)
        
        # Extract ATT&CK techniques from strategist
        attck_techniques: List[ATTCKRecommendation] = []
        if strategist and strategist.attck_techniques:
            attck_techniques = strategist.attck_techniques
        
        # Extract risk warnings from analyst
        risk_warnings: List[str] = []
        if analyst:
            if analyst.risk_assessment:
                risk_warnings.extend(analyst.risk_assessment.risk_factors)
            for gap in analyst.gaps:
                if gap.severity in ("CRITICAL", "HIGH"):
                    risk_warnings.append(f"[{gap.severity}] {gap.description}")
        
        # Preserve creative alternatives
        creative_alternatives: List[CreativeAlternative] = []
        if creative and creative.creative_alternatives:
            creative_alternatives = creative.creative_alternatives
        
        # Build avoid list from analyst risk assessment
        avoid_list: List[str] = []
        if analyst and analyst.risk_assessment:
            avoidance_keywords = ["avoid", "skip", "don't", "do not", "refrain", "never", "must not", "should not"]
            for mitigation in analyst.risk_assessment.mitigations_needed:
                mitigation_lower = mitigation.lower()
                if any(keyword in mitigation_lower for keyword in avoidance_keywords):
                    avoid_list.append(mitigation)
        
        # Build rationale combining all perspectives
        rationale = self._build_rationale(
            strategist, analyst, creative, resolved_conflicts
        )
        
        # Calculate confidence based on consensus and model availability
        confidence = self._compute_final_confidence(
            strategist, analyst, creative, consensus
        )
        
        log.info(
            "synthesis_complete",
            contributing_roles=[r.value for r in contributing_roles],
            objectives_count=len(objectives),
            actions_count=len(actions),
            conflicts_resolved=len(resolved_conflicts),
            confidence=confidence,
        )
        
        return SynthesizedStrategy(
            objectives=objectives,
            actions=actions,
            rationale=rationale,
            confidence=confidence,
            contributing_roles=contributing_roles,
            avoid_list=avoid_list,
            attck_techniques=attck_techniques,
            creative_alternatives=creative_alternatives,
            risk_warnings=risk_warnings,
            conflicts_resolved=resolved_conflicts,
            metadata={"synthesis_version": "8.5"},
        )

    def _extract_objectives(
        self,
        strategist: Optional[StrategistResponse],
        analyst: Optional[AnalystResponse],
        creative: Optional[CreativeResponse],
    ) -> List[str]:
        """Extract and merge objectives from all roles.
        
        Args:
            strategist: Strategist response with recommendations.
            analyst: Analyst response with gaps and opportunities.
            creative: Creative response with alternatives.
            
        Returns:
            List of unified objectives.
        """
        objectives: List[str] = []
        
        # Strategist recommendations become primary objectives
        if strategist and strategist.recommendations:
            for rec in strategist.recommendations[:5]:  # Top 5 recommendations
                # Clean up recommendation text
                obj = rec.strip()
                if obj and obj not in objectives:
                    objectives.append(obj)
        
        # Analyst overlooked opportunities can become objectives
        if analyst and analyst.overlooked_opportunities:
            for opp in analyst.overlooked_opportunities[:3]:  # Top 3 opportunities
                obj = f"Address: {opp.description}"
                if obj not in objectives:
                    objectives.append(obj)
        
        # Creative alternatives with high novelty can inform objectives
        if creative and creative.creative_alternatives:
            for alt in creative.creative_alternatives:
                if alt.novelty_score >= 0.7:  # High novelty threshold
                    obj = f"Consider: {alt.description}"
                    if obj not in objectives:
                        objectives.append(obj)
        
        return objectives

    def _extract_actions(
        self,
        strategist: Optional[StrategistResponse],
        creative: Optional[CreativeResponse],
    ) -> List[str]:
        """Extract actions from strategist and creative responses.
        
        Args:
            strategist: Strategist response with next phases.
            creative: Creative response with alternatives.
            
        Returns:
            List of recommended actions.
        """
        actions: List[str] = []
        
        # Strategist next phases become actions
        if strategist and strategist.next_phases:
            for phase in strategist.next_phases:
                action = phase.strip()
                if action and action not in actions:
                    actions.append(action)
        
        # Strategist priorities inform actions
        if strategist and strategist.priorities:
            for target, priority in strategist.priorities[:3]:  # Top 3 priority targets
                action = f"Priority {priority}: Target {target}"
                if action not in actions:
                    actions.append(action)
        
        # Creative evasion techniques become actions when defenses are encountered
        if creative and creative.evasion_techniques:
            for tech in creative.evasion_techniques:
                if tech.success_likelihood >= 0.6:  # Reasonable success threshold
                    action = f"Evasion: {tech.description} (target: {tech.target_defense})"
                    if action not in actions:
                        actions.append(action)
        
        return actions

    def _merge_insights(
        self,
        strategist: Optional[StrategistResponse],
        analyst: Optional[AnalystResponse],
    ) -> List[str]:
        """Merge analyst gaps with strategist priorities.
        
        Args:
            strategist: Strategist response.
            analyst: Analyst response with gaps.
            
        Returns:
            List of merged insight actions.
        """
        merged: List[str] = []
        
        if not analyst:
            return merged
        
        # Security gaps with high severity become priority actions
        for gap in analyst.gaps:
            if gap.severity in ("CRITICAL", "HIGH"):
                action = f"Address gap: {gap.description} (affects: {', '.join(gap.affected_assets[:3])})"
                merged.append(action)
        
        # Overlooked opportunities with high confidence
        for opp in analyst.overlooked_opportunities:
            if opp.confidence >= 0.7:
                action = f"Opportunity: {opp.recommended_action}"
                merged.append(action)
        
        return merged

    def _detect_conflicts(
        self,
        strategist: Optional[StrategistResponse],
        analyst: Optional[AnalystResponse],
        creative: Optional[CreativeResponse],
    ) -> List[ConflictResolution]:
        """Detect conflicting recommendations across roles.
        
        Args:
            strategist: Strategist response.
            analyst: Analyst response.
            creative: Creative response.
            
        Returns:
            List of detected conflicts (unresolved).
        """
        conflicts: List[ConflictResolution] = []
        
        # Detect aggressive vs cautious approach conflicts
        strategist_aggressive = False
        analyst_cautious = False
        
        if strategist and strategist.recommendations:
            for rec in strategist.recommendations:
                rec_lower = rec.lower()
                if any(word in rec_lower for word in ["aggressive", "rapid", "fast", "quick"]):
                    strategist_aggressive = True
                    break
        
        if analyst and analyst.risk_assessment:
            for factor in analyst.risk_assessment.risk_factors:
                factor_lower = factor.lower()
                if any(word in factor_lower for word in ["detected", "ids", "alert", "monitor"]):
                    analyst_cautious = True
                    break
        
        if strategist_aggressive and analyst_cautious:
            conflicts.append(ConflictResolution(
                conflict_type="approach",
                source_roles=[DirectorRole.STRATEGIST, DirectorRole.ANALYST],
                conflicting_values=["aggressive_approach", "cautious_approach"],
                resolved_value="",  # To be resolved
                resolution_rationale="",
            ))
        
        # Detect priority conflicts between strategist and creative
        if strategist and creative:
            strategist_targets = set()
            creative_targets = set()
            
            for target, _ in strategist.priorities:
                strategist_targets.add(target.lower().strip())
            
            for alt in creative.creative_alternatives:
                # Check if creative suggests different targets
                desc_lower = alt.description.lower()
                if "instead" in desc_lower or "alternative" in desc_lower:
                    creative_targets.add(alt.description[:50])
            
            if strategist_targets and creative_targets:
                if not strategist_targets.intersection(creative_targets):
                    conflicts.append(ConflictResolution(
                        conflict_type="target",
                        source_roles=[DirectorRole.STRATEGIST, DirectorRole.CREATIVE],
                        conflicting_values=list(strategist_targets)[:2] + list(creative_targets)[:2],
                        resolved_value="",
                        resolution_rationale="",
                    ))
        
        return conflicts

    def _resolve_conflicts(
        self,
        conflicts: List[ConflictResolution],
    ) -> List[ConflictResolution]:
        """Apply priority rules to resolve conflicts.
        
        Priority order:
        1. Security warnings (highest)
        2. Scope constraints
        3. Strategic priorities
        4. Risk avoidance
        5. Creative alternatives (lowest)
        
        Args:
            conflicts: List of unresolved conflicts.
            
        Returns:
            List of resolved conflicts with resolution details.
        """
        resolved: List[ConflictResolution] = []
        
        for conflict in conflicts:
            resolution: ConflictResolution
            if conflict.conflict_type == "approach":
                # Security/analyst concerns win over aggressive approaches
                resolution = ConflictResolution(
                    conflict_type=conflict.conflict_type,
                    source_roles=conflict.source_roles,
                    conflicting_values=conflict.conflicting_values,
                    resolved_value="cautious_approach",
                    resolution_rationale="Security concerns take precedence over aggressive tactics per conflict priority rules.",
                )
            elif conflict.conflict_type == "target":
                # Strategist priorities win over creative alternatives
                resolution = ConflictResolution(
                    conflict_type=conflict.conflict_type,
                    source_roles=conflict.source_roles,
                    conflicting_values=conflict.conflicting_values,
                    resolved_value=conflict.conflicting_values[0] if conflict.conflicting_values else "",
                    resolution_rationale="Strategic priorities take precedence over creative alternatives per conflict priority rules.",
                )
            elif conflict.conflict_type == "safety":
                # Safety always wins
                resolution = ConflictResolution(
                    conflict_type=conflict.conflict_type,
                    source_roles=conflict.source_roles,
                    conflicting_values=conflict.conflicting_values,
                    resolved_value="safe_approach",
                    resolution_rationale="Safety concerns always take highest priority.",
                )
            else:
                # Default: keep first value with generic rationale
                resolution = ConflictResolution(
                    conflict_type=conflict.conflict_type,
                    source_roles=conflict.source_roles,
                    conflicting_values=conflict.conflicting_values,
                    resolved_value=conflict.conflicting_values[0] if conflict.conflicting_values else "",
                    resolution_rationale="Resolved using default priority ordering.",
                )
            
            # Log resolved conflict for audit trail (Task 2 requirement)
            log.info(
                "conflict_resolved",
                conflict_type=resolution.conflict_type,
                source_roles=[r.value for r in resolution.source_roles],
                resolved_value=resolution.resolved_value,
                rationale=resolution.resolution_rationale,
            )
            resolved.append(resolution)
        
        return resolved

    def _calculate_consensus(
        self,
        strategist: Optional[StrategistResponse],
        analyst: Optional[AnalystResponse],
        creative: Optional[CreativeResponse],
    ) -> float:
        """Calculate consensus score based on model agreement.
        
        Returns:
            0.0-1.0 consensus score:
            - 1.0: All models agree on approach
            - 0.67: 2 of 3 models agree
            - 0.33: Models have different recommendations
            - 0.0: Only 1 model available or complete disagreement
        """
        available_count = sum([
            1 if strategist else 0,
            1 if analyst else 0,
            1 if creative else 0,
        ])
        
        if available_count == 0:
            return 0.0
        
        if available_count == 1:
            return 0.0  # No consensus possible with single model
        
        # Calculate agreement based on confidence scores
        confidences: List[float] = []
        if strategist:
            confidences.append(strategist.confidence)
        if analyst and analyst.risk_assessment:
            confidences.append(analyst.risk_assessment.confidence)
        if creative:
            # Use average novelty score as proxy for creative confidence
            if creative.creative_alternatives:
                avg_novelty = sum(a.novelty_score for a in creative.creative_alternatives) / len(creative.creative_alternatives)
                confidences.append(avg_novelty)
        
        if len(confidences) < 2:
            return 0.33  # Limited consensus data
        
        # High consensus if confidences are similar (within 0.3 of each other)
        confidence_spread = max(confidences) - min(confidences)
        if confidence_spread <= 0.2:
            return 1.0 if available_count == 3 else 0.67
        elif confidence_spread <= 0.4:
            return 0.67 if available_count == 3 else 0.5
        else:
            return 0.33
    
    def _weight_by_confidence(
        self,
        actions: List[Tuple[str, float]],
    ) -> List[Tuple[str, float]]:
        """Weight actions by confidence scores.
        
        Args:
            actions: List of (action, confidence) tuples.
            
        Returns:
            Sorted list with highest confidence first.
        """
        return sorted(actions, key=lambda x: x[1], reverse=True)

    def _compute_final_confidence(
        self,
        strategist: Optional[StrategistResponse],
        analyst: Optional[AnalystResponse],
        creative: Optional[CreativeResponse],
        consensus: float,
    ) -> float:
        """Compute final confidence score for the synthesis.
        
        Weighting rationale:
        - 40% availability: More models = more comprehensive strategy
        - 40% model confidence: Higher model confidence = better recommendations  
        - 20% consensus: Agreement between models indicates reliability
        
        Args:
            strategist: Strategist response.
            analyst: Analyst response.
            creative: Creative response.
            consensus: Calculated consensus score.
            
        Returns:
            Final confidence score (0.0-1.0).
        """
        available_count = sum([
            1 if strategist else 0,
            1 if analyst else 0,
            1 if creative else 0,
        ])
        
        if available_count == 0:
            return 0.0
        
        # Base confidence from model availability
        availability_factor = available_count / 3.0
        
        # Average confidence from available models (with validation)
        confidences: List[float] = []
        if strategist:
            # Validate and clamp confidence to 0.0-1.0 range
            conf = max(0.0, min(1.0, strategist.confidence))
            confidences.append(conf)
        if analyst and analyst.risk_assessment:
            conf = max(0.0, min(1.0, analyst.risk_assessment.confidence))
            confidences.append(conf)
        if creative and creative.creative_alternatives:
            avg_novelty = sum(a.novelty_score for a in creative.creative_alternatives) / len(creative.creative_alternatives)
            conf = max(0.0, min(1.0, avg_novelty))
            confidences.append(conf)
        
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        # Final confidence weighted by availability and consensus
        final_confidence = (availability_factor * 0.4) + (avg_confidence * 0.4) + (consensus * 0.2)
        
        return min(1.0, max(0.0, final_confidence))
    
    async def synthesize_async(
        self,
        strategist: Optional[StrategistResponse],
        analyst: Optional[AnalystResponse],
        creative: Optional[CreativeResponse],
        timeout: float = 60.0,
    ) -> SynthesizedStrategy:
        """Async synthesis with optional LLM aggregator call for complex cases.
        
        Story 8.5 Task 5: Implement async synthesis with LLM aggregator call.
        
        Uses aggregator LLM call when simple merging is insufficient (e.g., when
        multiple conflicts are detected or confidence is low). Falls back to 
        simple merge if aggregator call fails or times out.
        
        Args:
            strategist: Strategist response.
            analyst: Analyst response.
            creative: Creative response.
            timeout: Timeout in seconds for aggregator call (default 60s per architecture).
            
        Returns:
            SynthesizedStrategy with unified objectives, actions, and rationale.
        """
        # First, try simple synchronous synthesis
        simple_strategy = self.synthesize(strategist, analyst, creative)
        
        # Determine if we need complex synthesis via LLM aggregator
        needs_aggregator = (
            len(simple_strategy.conflicts_resolved) > 2 or
            simple_strategy.confidence < 0.4 or
            (len(simple_strategy.objectives) == 0 and len(simple_strategy.actions) == 0)
        )
        
        if not needs_aggregator:
            log.debug(
                "synthesis_async_simple_sufficient",
                confidence=simple_strategy.confidence,
                conflicts_count=len(simple_strategy.conflicts_resolved),
            )
            return simple_strategy
        
        # Try aggregator LLM call for complex synthesis
        try:
            log.info(
                "synthesis_async_aggregator_start",
                timeout=timeout,
                reason="complex_synthesis_needed",
            )
            
            # Import here to avoid circular imports
            aggregated_strategy = await asyncio.wait_for(
                self._call_aggregator_llm(strategist, analyst, creative, simple_strategy),
                timeout=timeout,
            )
            
            log.info(
                "synthesis_async_aggregator_success",
                confidence=aggregated_strategy.confidence,
            )
            return aggregated_strategy
            
        except asyncio.TimeoutError:
            log.warning(
                "synthesis_async_aggregator_timeout",
                timeout=timeout,
                fallback="simple_merge",
            )
            # Fallback to simple merge on timeout
            return simple_strategy
            
        except Exception as e:
            log.warning(
                "synthesis_async_aggregator_failed",
                error=str(e),
                fallback="simple_merge",
            )
            # Fallback to simple merge on any error
            return simple_strategy
    
    async def _call_aggregator_llm(
        self,
        strategist: Optional[StrategistResponse],
        analyst: Optional[AnalystResponse],
        creative: Optional[CreativeResponse],
        base_strategy: SynthesizedStrategy,
    ) -> SynthesizedStrategy:
        """Call LLM to aggregate complex multi-model synthesis.
        
        This is a placeholder for future LLM aggregation. Currently returns
        the base strategy with metadata indicating aggregation was attempted.
        
        Args:
            strategist: Strategist response.
            analyst: Analyst response.
            creative: Creative response.
            base_strategy: Initial synthesis result to improve upon.
            
        Returns:
            Improved SynthesizedStrategy (or base strategy if aggregation unavailable).
        """
        # For now, return base strategy with aggregation metadata
        # Full LLM aggregation would require gateway integration
        base_strategy.metadata["aggregation_attempted"] = True
        base_strategy.metadata["aggregation_status"] = "fallback_simple"
        return base_strategy

    def _build_rationale(
        self,
        strategist: Optional[StrategistResponse],
        analyst: Optional[AnalystResponse],
        creative: Optional[CreativeResponse],
        conflicts_resolved: List[ConflictResolution],
    ) -> str:
        """Build rationale combining all perspectives.
        
        Args:
            strategist: Strategist response.
            analyst: Analyst response.
            creative: Creative response.
            conflicts_resolved: List of resolved conflicts.
            
        Returns:
            Combined rationale string.
        """
        parts: List[str] = []
        
        if strategist:
            parts.append(f"**Strategic Perspective:** {len(strategist.recommendations)} recommendations provided with {strategist.confidence:.0%} confidence.")
            if strategist.attck_techniques:
                techniques = ", ".join(t.technique_id for t in strategist.attck_techniques[:3])
                parts.append(f"Recommended ATT&CK techniques: {techniques}")
        
        if analyst:
            parts.append(f"**Analyst Perspective:** {len(analyst.gaps)} security gaps identified.")
            if analyst.risk_assessment:
                parts.append(f"Overall risk level: {analyst.risk_assessment.overall_risk_level}")
        
        if creative:
            parts.append(f"**Creative Perspective:** {len(creative.creative_alternatives)} alternatives proposed.")
            if creative.thinking_content:
                parts.append(f"Creative reasoning preserved ({len(creative.thinking_content)} thinking blocks).")
        
        if conflicts_resolved:
            parts.append(f"**Conflicts Resolved:** {len(conflicts_resolved)} conflicts resolved using priority rules.")
            for conflict in conflicts_resolved[:2]:  # Show first 2 conflicts
                parts.append(f"- {conflict.conflict_type}: {conflict.resolution_rationale}")
        
        return "\n".join(parts) if parts else "Synthesis completed with available model responses."
