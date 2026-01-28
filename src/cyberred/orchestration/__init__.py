"""Orchestration module for Cyber-Red swarm coordination.

This module provides the SwarmRouter integration for routing tasks to
appropriate agent types and spawning agent swarms.
"""

from .router import (
    AGENT_CLASSES,
    ROLE_DISTRIBUTION_DEFAULTS,
    ROLE_KEYWORDS,
    SwarmRouterWrapper,
    SwarmType,
)
from .spawner import (
    PHASE_DISTRIBUTIONS,
    SCOPE_HEURISTICS,
    DynamicSpawner,
)
from .crash_monitor import (
    AgentCrashMonitor,
    AgentHealthState,
    CRASH_DETECTION_TIMEOUT_S,
    HEARTBEAT_INTERVAL_S,
)
from .directive import (
    DirectiveInterpreter,
    DirectiveResult,
    DirectiveType,
    MissionDirective,
    ParsedDirective,
)
from .replan_triggers import (
    TriggerType,
    ReplanTrigger,
    ReplanTriggerConfig,
    ReplanTriggerManager,
    VALID_PHASE_TRANSITIONS,
    VALID_OBJECTIVE_TYPES,
)
from .aggregator import (
    FindingCategory,
    FindingSeverity,
    AggregatedFinding,
    AggregationSummary,
    AggregatorConfig,
    FindingAggregator,
    FINDING_TYPE_CATEGORIES,
)
from .strategy_publisher import (
    PublishedStrategy,
    StrategyPublisher,
)
from .emergence import (
    DecisionContextTracker,
    SignalRecord,
    SIGNAL_TYPE_WEIGHTS,
    validate_decision_context,
    ValidationResult,
    check_hard_gate,
)

__all__ = [
    "SwarmRouterWrapper",
    "SwarmType",
    "ROLE_KEYWORDS",
    "ROLE_DISTRIBUTION_DEFAULTS",
    "AGENT_CLASSES",
    "DynamicSpawner",
    "SCOPE_HEURISTICS",
    "PHASE_DISTRIBUTIONS",
    "DecisionContextTracker",
    "SignalRecord",
    "SIGNAL_TYPE_WEIGHTS",
    "validate_decision_context",
    "ValidationResult",
    "check_hard_gate",
    # Story 7.12: Crash Recovery
    "AgentCrashMonitor",
    "AgentHealthState",
    "CRASH_DETECTION_TIMEOUT_S",
    "HEARTBEAT_INTERVAL_S",
    # Story 8.7: Natural Language Mission Directive
    "DirectiveInterpreter",
    "DirectiveResult",
    "DirectiveType",
    "MissionDirective",
    "ParsedDirective",
    # Story 8.8: Re-Plan Triggers
    "TriggerType",
    "ReplanTrigger",
    "ReplanTriggerConfig",
    "ReplanTriggerManager",
    "VALID_PHASE_TRANSITIONS",
    "VALID_OBJECTIVE_TYPES",
    # Story 8.9: Finding Aggregation
    "FindingCategory",
    "FindingSeverity",
    "AggregatedFinding",
    "AggregationSummary",
    "AggregatorConfig",
    "FindingAggregator",
    "FINDING_TYPE_CATEGORIES",
    # Story 8.10: Strategy Publication
    "PublishedStrategy",
    "StrategyPublisher",
]