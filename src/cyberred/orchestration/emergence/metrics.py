"""Emergence score calculation and NFR35 hard gate validation.

This module provides the EmergenceMetrics class for calculating emergence scores
from isolated vs stigmergic comparison runs, validating the NFR35 hard gate (>20%),
and exporting metrics to Prometheus (OBS11).

Emergence Score Formula:
    novel_chains = paths in stigmergic NOT in isolated (by signature)
    emergence_score = len(novel_chains) / len(total_stigmergic_paths)

HARD GATE (NFR35): emergence_score > 0.20 (20%)
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from cyberred.orchestration.emergence.models import (
    AttackPath,
    RunResult,
)

log = structlog.get_logger().bind(component="emergence_metrics")

# NFR35 threshold constant
NFR35_EMERGENCE_THRESHOLD = 0.20


@dataclass
class EmergenceScore:
    """Calculated emergence score with full audit trail.

    Attributes:
        novel_path_count: Number of paths only in stigmergic run.
        shared_path_count: Number of paths in both runs.
        total_stigmergic_paths: Total paths in stigmergic run.
        total_isolated_paths: Total paths in isolated run.
        score: Emergence score (0.0 to 1.0).
        novel_paths: The actual novel AttackPath instances.
        calculation_timestamp: When score was calculated.
        avg_novel_depth: Average depth of novel paths.
        max_novel_depth: Maximum depth of novel paths.
        min_novel_depth: Minimum depth of novel paths.
        depth_distribution: Count of paths at each depth level.
        technique_distribution: Count of paths using each technique.
    """

    novel_path_count: int
    shared_path_count: int
    total_stigmergic_paths: int
    total_isolated_paths: int
    score: float
    novel_paths: list[AttackPath]
    calculation_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    avg_novel_depth: float = 0.0
    max_novel_depth: int = 0
    min_novel_depth: int = 0
    depth_distribution: dict[int, int] = field(default_factory=dict)
    technique_distribution: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        return {
            "novel_path_count": self.novel_path_count,
            "shared_path_count": self.shared_path_count,
            "total_stigmergic_paths": self.total_stigmergic_paths,
            "total_isolated_paths": self.total_isolated_paths,
            "score": self.score,
            "score_percentage": f"{self.score * 100:.1f}%",
            "calculation_timestamp": self.calculation_timestamp.isoformat(),
            "avg_novel_depth": self.avg_novel_depth,
            "max_novel_depth": self.max_novel_depth,
            "min_novel_depth": self.min_novel_depth,
            "depth_distribution": self.depth_distribution,
            "technique_distribution": self.technique_distribution,
        }


@dataclass
class HardGateResult:
    """Result of NFR35 hard gate validation.

    Attributes:
        passed: Whether the hard gate passed (score > threshold).
        threshold: The threshold used (0.20 for NFR35).
        score: The actual emergence score.
        margin: score - threshold (positive if passed).
        message: Human-readable result message.
    """

    passed: bool
    threshold: float
    score: float
    margin: float
    message: str

    @classmethod
    def from_score(cls, score: float, threshold: float = NFR35_EMERGENCE_THRESHOLD) -> "HardGateResult":
        """Create HardGateResult from emergence score.

        Args:
            score: The emergence score (0.0 to 1.0).
            threshold: The threshold to compare against (default 0.20).

        Returns:
            HardGateResult with pass/fail status and details.
        """
        passed = score > threshold
        margin = score - threshold

        if passed:
            message = (
                f"NFR35 HARD GATE PASSED: Emergence score {score:.1%} "
                f"exceeds {threshold:.0%} threshold by {margin:.1%}"
            )
        else:
            message = (
                f"NFR35 HARD GATE FAILED: Emergence score {score:.1%} "
                f"does not exceed {threshold:.0%} threshold (margin: {margin:.1%})"
            )

        return cls(
            passed=passed,
            threshold=threshold,
            score=score,
            margin=margin,
            message=message,
        )


class EmergenceMetrics:
    """Calculates and validates emergence metrics for NFR35.

    Provides:
    - Emergence score calculation (novel paths / total paths)
    - Hard gate validation (>20% required)
    - Prometheus metrics export (OBS11)
    - Detailed statistics for analysis

    Usage:
        metrics = EmergenceMetrics()
        score = metrics.calculate_emergence_score(isolated_result, stigmergic_result)
        gate_result = metrics.validate_hard_gate(score)

        if not gate_result.passed:
            raise ValueError(gate_result.message)
    """

    def __init__(self, prometheus_registry: Any = None) -> None:
        """Initialize EmergenceMetrics.

        Args:
            prometheus_registry: Optional Prometheus registry for metrics.
                If None, uses default registry when prometheus_client is available.
        """
        self._log = log
        self._registry = prometheus_registry
        self._prometheus_available = False
        self._emergence_score_gauge: Any = None
        self._novel_paths_gauge: Any = None
        self._total_paths_gauge: Any = None
        self._hard_gate_gauge: Any = None
        self._setup_prometheus_metrics()

    def _setup_prometheus_metrics(self) -> None:
        """Setup Prometheus gauges for emergence metrics.

        Handles re-registration gracefully by reusing existing metrics
        if they are already registered in the registry.
        """
        try:
            from prometheus_client import REGISTRY, Gauge

            registry = self._registry or REGISTRY

            # Helper to get or create a gauge (handles re-registration)
            def get_or_create_gauge(
                name: str, description: str, labelnames: list[str]
            ) -> Gauge:
                """Get existing gauge or create new one."""
                # Check if metric already exists in registry
                if hasattr(registry, '_names_to_collectors'):
                    existing = registry._names_to_collectors.get(name)
                    if existing is not None:
                        return existing

                # Create new gauge
                return Gauge(
                    name,
                    description,
                    labelnames,
                    registry=registry,
                )

            self._emergence_score_gauge = get_or_create_gauge(
                "cyberred_emergence_score",
                "Current emergence score (0.0-1.0)",
                ["engagement_id", "run_id"],
            )
            self._novel_paths_gauge = get_or_create_gauge(
                "cyberred_emergence_novel_paths",
                "Count of novel attack paths from stigmergic coordination",
                ["engagement_id", "run_id"],
            )
            self._total_paths_gauge = get_or_create_gauge(
                "cyberred_emergence_total_paths",
                "Total attack paths in stigmergic run",
                ["engagement_id", "run_id"],
            )
            self._hard_gate_gauge = get_or_create_gauge(
                "cyberred_emergence_hard_gate_passed",
                "1 if NFR35 hard gate passed, 0 if failed",
                ["engagement_id", "run_id"],
            )
            self._prometheus_available = True
        except ImportError:
            self._prometheus_available = False
            self._log.warning("prometheus_client_not_available")

    def calculate_emergence_score(
        self,
        isolated: RunResult,
        stigmergic: RunResult,
    ) -> EmergenceScore:
        """Calculate emergence score from isolated vs stigmergic comparison.

        Formula: emergence_score = novel_paths / total_stigmergic_paths

        Args:
            isolated: RunResult from isolated (no pub/sub) run.
            stigmergic: RunResult from stigmergic (full coordination) run.

        Returns:
            EmergenceScore with full calculation details.
        """
        self._log.info(
            "calculating_emergence_score",
            isolated_paths=len(isolated.attack_paths),
            stigmergic_paths=len(stigmergic.attack_paths),
        )

        # Build signatures for isolated paths
        isolated_signatures = {self._path_signature(p) for p in isolated.attack_paths}

        # Identify novel and shared paths
        # Note: We set is_novel on the path objects for downstream consumers,
        # but we also explicitly reset shared paths to avoid stale state
        novel_paths: list[AttackPath] = []
        shared_paths: list[AttackPath] = []

        for path in stigmergic.attack_paths:
            sig = self._path_signature(path)
            if sig in isolated_signatures:
                path.is_novel = False  # Explicitly reset to avoid stale state
                shared_paths.append(path)
            else:
                path.is_novel = True
                novel_paths.append(path)

        # Calculate score
        total_stigmergic = len(stigmergic.attack_paths)
        score = 0.0 if total_stigmergic == 0 else len(novel_paths) / total_stigmergic

        # Calculate depth and technique statistics (AC7 compliant naming)
        avg_depth, max_depth, min_depth, depth_dist = self._calculate_depth_stats(novel_paths)
        technique_dist = self._calculate_technique_distribution(novel_paths)

        emergence_score = EmergenceScore(
            novel_path_count=len(novel_paths),
            shared_path_count=len(shared_paths),
            total_stigmergic_paths=total_stigmergic,
            total_isolated_paths=len(isolated.attack_paths),
            score=score,
            novel_paths=novel_paths,
            avg_novel_depth=avg_depth,
            max_novel_depth=max_depth,
            min_novel_depth=min_depth,
            depth_distribution=depth_dist,
            technique_distribution=technique_dist,
        )

        self._log.info(
            "emergence_score_calculated",
            score=score,
            score_percentage=f"{score:.1%}",
            novel_paths=len(novel_paths),
            shared_paths=len(shared_paths),
        )

        return emergence_score

    def validate_hard_gate(
        self,
        score: EmergenceScore,
        threshold: float = NFR35_EMERGENCE_THRESHOLD,
    ) -> HardGateResult:
        """Validate emergence score against NFR35 hard gate.

        Args:
            score: EmergenceScore to validate.
            threshold: Minimum required score (default 0.20 per NFR35).

        Returns:
            HardGateResult with pass/fail status and details.
        """
        result = HardGateResult.from_score(score.score, threshold)

        self._log.info(
            "hard_gate_validated",
            passed=result.passed,
            score=result.score,
            threshold=result.threshold,
            margin=result.margin,
        )

        return result

    def export_prometheus_metrics(
        self,
        score: EmergenceScore,
        engagement_id: str,
        run_id: str,
    ) -> None:
        """Export emergence metrics to Prometheus.

        Args:
            score: EmergenceScore to export.
            engagement_id: Current engagement ID.
            run_id: Current run ID.
        """
        if not self._prometheus_available:
            self._log.debug("prometheus_export_skipped_not_available")
            return

        labels = {"engagement_id": engagement_id, "run_id": run_id}

        self._emergence_score_gauge.labels(**labels).set(score.score)
        self._novel_paths_gauge.labels(**labels).set(score.novel_path_count)
        self._total_paths_gauge.labels(**labels).set(score.total_stigmergic_paths)

        gate_result = self.validate_hard_gate(score)
        self._hard_gate_gauge.labels(**labels).set(1 if gate_result.passed else 0)

        self._log.info(
            "prometheus_metrics_exported",
            engagement_id=engagement_id,
            run_id=run_id,
            score=score.score,
        )

    def _path_signature(self, path: AttackPath) -> str:
        """Generate signature for path comparison (ignores timing/IDs)."""
        steps_sig = "|".join(f"{s.target}:{s.technique}" for s in path.steps)
        return steps_sig

    def _calculate_depth_stats(
        self, paths: list[AttackPath]
    ) -> tuple[float, int, int, dict[int, int]]:
        """Calculate depth statistics for paths.

        Args:
            paths: List of AttackPath instances.

        Returns:
            Tuple of (avg_depth, max_depth, min_depth, depth_distribution).
        """
        if not paths:
            return 0.0, 0, 0, {}

        depths = [p.depth for p in paths]

        # Build depth distribution: count of paths at each depth level
        depth_distribution: dict[int, int] = {}
        for d in depths:
            depth_distribution[d] = depth_distribution.get(d, 0) + 1

        return (
            sum(depths) / len(depths),
            max(depths),
            min(depths),
            depth_distribution,
        )

    def _calculate_technique_distribution(
        self,
        paths: list[AttackPath],
    ) -> dict[str, int]:
        """Calculate distribution of techniques in paths.

        Args:
            paths: List of AttackPath instances.

        Returns:
            Dictionary mapping technique names to counts.
        """
        distribution: dict[str, int] = {}

        for path in paths:
            for step in path.steps:
                technique = step.technique
                distribution[technique] = distribution.get(technique, 0) + 1

        return distribution
