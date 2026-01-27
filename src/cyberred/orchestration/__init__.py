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
]