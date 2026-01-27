from .tracker import DecisionContextTracker, SignalRecord, SIGNAL_TYPE_WEIGHTS
from .validator import ValidationResult, check_hard_gate, validate_decision_context
from .models import (
    AttackPath,
    ComparisonResult,
    EmergenceComparisonConfig,
    PathStep,
    RunResult,
)
from .comparison import EmergenceComparisonFramework
from .metrics import EmergenceMetrics, EmergenceScore, HardGateResult, NFR35_EMERGENCE_THRESHOLD
from .causal import (
    CausalChainValidator,
    ChainDepthResult,
    ChainStructureResult,
    NFR36_MIN_CHAIN_DEPTH,
)

__all__ = [
    "DecisionContextTracker",
    "SignalRecord",
    "SIGNAL_TYPE_WEIGHTS",
    "validate_decision_context",
    "ValidationResult",
    "check_hard_gate",
    "EmergenceComparisonFramework",
    "EmergenceComparisonConfig",
    "RunResult",
    "ComparisonResult",
    "AttackPath",
    "PathStep",
    # Story 7.10: Emergence Score Calculation
    "EmergenceMetrics",
    "EmergenceScore",
    "HardGateResult",
    "NFR35_EMERGENCE_THRESHOLD",
    # Story 7.11: Causal Chain Depth Validation
    "CausalChainValidator",
    "ChainDepthResult",
    "ChainStructureResult",
    "NFR36_MIN_CHAIN_DEPTH",
]