"""Causal chain depth validation for NFR36 hard gate.

This module provides the CausalChainValidator class for analyzing attack paths
and validating the NFR36 requirement: at least one causal chain with 3+ hops
(Finding→Action→Finding→Action→Finding).

NFR36 Requirements:
    - At least one emergence chain with 3+ hops
    - Each hop represents: Finding published → Agent action → New finding

NFR37 Requirements:
    - 100% of steps must have decision_context populated
    - Chain must be traceable back to root finding

Prometheus Metrics (OBS12):
    - cyberred_causal_chain_max_depth: Maximum chain depth observed
    - cyberred_causal_chain_count_3plus: Count of chains with 3+ hops
    - cyberred_causal_chain_hard_gate_passed: 1 if passed, 0 if failed

Story 7.11: Causal Chain Depth Validation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from cyberred.orchestration.emergence.models import AttackPath

log = structlog.get_logger()

# NFR36 threshold constant
NFR36_MIN_CHAIN_DEPTH = 3


@dataclass
class ChainDepthResult:
    """NFR36 validation result.

    Attributes:
        passed: Whether NFR36 hard gate passed (at least one chain >= min_depth).
        min_required_depth: The minimum depth required (3 for NFR36).
        max_observed_depth: Maximum depth found in any chain.
        chains_meeting_requirement: Count of chains with depth >= min_depth.
        total_chains: Total number of chains analyzed.
        deepest_chain: The chain with maximum depth.
        depth_distribution: Count of chains at each depth level.
        message: Human-readable result message.
    """

    passed: bool
    min_required_depth: int
    max_observed_depth: int
    chains_meeting_requirement: int
    total_chains: int
    deepest_chain: AttackPath | None
    depth_distribution: dict[int, int]
    message: str

    @classmethod
    def from_paths(cls, paths: list[AttackPath], min_depth: int = NFR36_MIN_CHAIN_DEPTH) -> ChainDepthResult:
        """Create ChainDepthResult from paths list.

        Args:
            paths: List of AttackPath instances to analyze.
            min_depth: Minimum depth required (default 3 for NFR36).

        Returns:
            ChainDepthResult with validation results.
            Returns failed result if paths list is empty.
        """
        if not paths:
            return cls(
                passed=False,
                min_required_depth=min_depth,
                max_observed_depth=0,
                chains_meeting_requirement=0,
                total_chains=0,
                deepest_chain=None,
                depth_distribution={},
                message="NFR36 HARD GATE FAILED: No chains to analyze",
            )

        # Calculate depth distribution
        depth_dist: dict[int, int] = {}
        for path in paths:
            depth = path.depth
            depth_dist[depth] = depth_dist.get(depth, 0) + 1

        # Find deepest chain
        deepest = max(paths, key=lambda p: p.depth)
        max_depth = deepest.depth

        # Count chains meeting requirement
        meeting_req = sum(1 for p in paths if p.depth >= min_depth)
        passed = meeting_req > 0

        # Build message
        if passed:
            message = (
                f"NFR36 HARD GATE PASSED: {meeting_req} chain(s) >= {min_depth} hops, "
                f"max depth = {max_depth}"
            )
        else:
            message = (
                f"NFR36 HARD GATE FAILED: No chains >= {min_depth} hops, "
                f"max depth = {max_depth}"
            )

        return cls(
            passed=passed,
            min_required_depth=min_depth,
            max_observed_depth=max_depth,
            chains_meeting_requirement=meeting_req,
            total_chains=len(paths),
            deepest_chain=deepest,
            depth_distribution=depth_dist,
            message=message,
        )


@dataclass
class ChainStructureResult:
    """Chain structure validation result.

    Attributes:
        valid: Overall validity (all checks pass).
        has_root_finding: Whether chain has a root finding (first step has finding_id).
        all_links_valid: Whether each link references valid parent.
        has_cycles: Whether chain contains cycles (repeated action_ids).
        missing_decision_context: List of action_ids missing decision_context.
        errors: List of error messages.
    """

    valid: bool
    has_root_finding: bool
    all_links_valid: bool
    has_cycles: bool
    missing_decision_context: list[str]
    errors: list[str]


class CausalChainValidator:
    """Validates causal chain depth (NFR36) and structure (NFR37).

    Provides methods to:
    - Validate chain depth meets NFR36 requirement (3+ hops)
    - Find the deepest chain in a set
    - Group chains by depth
    - Validate chain structure (root finding, no cycles, valid links)
    - Trace chain back to root finding
    - Export metrics to Prometheus (OBS12)

    Usage:
        validator = CausalChainValidator()
        result = validator.validate_chain_depth(attack_paths)

        if not result.passed:
            raise ValueError(result.message)

        # Export to Prometheus
        validator.export_prometheus_metrics(result, engagement_id, run_id)
    """

    def __init__(self, prometheus_registry: Any = None) -> None:
        """Initialize CausalChainValidator.

        Args:
            prometheus_registry: Optional Prometheus registry for metrics.
                If None, uses default registry when prometheus_client is available.
        """
        self._log = log.bind(component="causal_chain_validator")
        self._registry = prometheus_registry
        self._prometheus_available = False
        self._max_depth_gauge: Any = None
        self._count_3plus_gauge: Any = None
        self._hard_gate_gauge: Any = None
        self._setup_prometheus_metrics()

    def validate_chain_depth(
        self,
        paths: list[AttackPath],
        min_depth: int = NFR36_MIN_CHAIN_DEPTH,
    ) -> ChainDepthResult:
        """Validate at least one chain meets minimum depth requirement.

        Args:
            paths: List of AttackPath instances to validate.
            min_depth: Minimum depth required (default 3 for NFR36).

        Returns:
            ChainDepthResult with validation details.
        """
        result = ChainDepthResult.from_paths(paths, min_depth)

        self._log.info(
            "chain_depth_validated",
            passed=result.passed,
            max_depth=result.max_observed_depth,
            chains_meeting_req=result.chains_meeting_requirement,
            total_chains=result.total_chains,
        )

        return result

    def find_deepest_chain(self, paths: list[AttackPath]) -> AttackPath | None:
        """Return chain with maximum depth, or None if empty.

        Args:
            paths: List of AttackPath instances.

        Returns:
            AttackPath with maximum depth, or None if paths is empty.
        """
        if not paths:
            return None
        return max(paths, key=lambda p: p.depth)

    def get_chains_by_depth(self, paths: list[AttackPath]) -> dict[int, list[AttackPath]]:
        """Group chains by their depth.

        Args:
            paths: List of AttackPath instances.

        Returns:
            Dictionary mapping depth to list of paths at that depth.
        """
        result: dict[int, list[AttackPath]] = {}
        for path in paths:
            result.setdefault(path.depth, []).append(path)
        return result

    def validate_chain_structure(self, path: AttackPath) -> ChainStructureResult:
        """Validate chain structure: root finding, no cycles, valid links, decision_context.

        Checks:
        1. Chain has root finding (first step has finding_id)
        2. No cycles (no repeated action_ids)
        3. All links valid (decision_context references prior findings)
        4. All steps have decision_context populated (NFR37)

        Args:
            path: AttackPath to validate.

        Returns:
            ChainStructureResult with validation details.
        """
        errors: list[str] = []
        missing_context: list[str] = []

        # Check root finding
        has_root = bool(path.steps and path.steps[0].finding_id)
        if not has_root:
            errors.append("Missing root finding")

        # Check cycles (repeated action_ids)
        seen_actions: set[str] = set()
        has_cycles = False
        for step in path.steps:
            if step.action_id in seen_actions:
                has_cycles = True
                errors.append(f"Cycle detected: repeated action_id {step.action_id}")
            seen_actions.add(step.action_id)

        # Check decision_context population (NFR37)
        # Root step (index 0) doesn't need decision_context
        for i, step in enumerate(path.steps):
            if i > 0 and not step.decision_context:
                missing_context.append(step.action_id)

        if missing_context:
            errors.append(f"NFR37: {len(missing_context)} step(s) missing decision_context")

        # Validate links: each non-root step's decision_context should reference prior findings
        all_links_valid = True
        prior_findings: set[str] = set()

        for i, step in enumerate(path.steps):
            if i > 0 and step.decision_context:
                # Check if at least one context item references a prior finding
                # or is "isolated_mode" (special case for isolated runs)
                valid_ref = any(
                    ctx in prior_findings or ctx == "isolated_mode"
                    for ctx in step.decision_context
                )
                if not valid_ref:
                    all_links_valid = False
                    errors.append(f"Step {i} ({step.action_id}) doesn't reference prior findings")

            # Add this step's finding to prior findings for next iteration
            if step.finding_id:
                prior_findings.add(step.finding_id)

        # Overall validity
        valid = has_root and not has_cycles and all_links_valid and not missing_context

        return ChainStructureResult(
            valid=valid,
            has_root_finding=has_root,
            all_links_valid=all_links_valid,
            has_cycles=has_cycles,
            missing_decision_context=missing_context,
            errors=errors,
        )

    def trace_chain_to_root(self, path: AttackPath) -> list[str]:
        """Return finding_ids from leaf to root (reversed order).

        Args:
            path: AttackPath to trace.

        Returns:
            List of finding_ids from leaf (last) to root (first).
            Empty finding_ids are skipped.
        """
        finding_ids = [step.finding_id for step in path.steps if step.finding_id]
        return list(reversed(finding_ids))

    def export_prometheus_metrics(
        self,
        result: ChainDepthResult,
        engagement_id: str,
        run_id: str,
    ) -> None:
        """Export metrics to Prometheus (OBS12).

        Exports:
        - cyberred_causal_chain_max_depth: Maximum chain depth observed
        - cyberred_causal_chain_count_3plus: Count of chains with 3+ hops
        - cyberred_causal_chain_hard_gate_passed: 1 if passed, 0 if failed

        Args:
            result: ChainDepthResult to export.
            engagement_id: Current engagement ID.
            run_id: Current run ID.
        """
        if not self._prometheus_available:
            self._log.debug("prometheus_export_skipped_not_available")
            return

        labels = {"engagement_id": engagement_id, "run_id": run_id}

        self._max_depth_gauge.labels(**labels).set(result.max_observed_depth)
        self._count_3plus_gauge.labels(**labels).set(result.chains_meeting_requirement)
        self._hard_gate_gauge.labels(**labels).set(1 if result.passed else 0)

        self._log.info(
            "prometheus_metrics_exported",
            engagement_id=engagement_id,
            run_id=run_id,
            max_depth=result.max_observed_depth,
            hard_gate_passed=result.passed,
        )

    def _setup_prometheus_metrics(self) -> None:
        """Setup Prometheus gauges for causal chain metrics.

        Handles re-registration gracefully by reusing existing metrics
        if they are already registered in the registry.
        Pattern from metrics.py (Story 7.10).
        """
        try:
            from prometheus_client import REGISTRY, Gauge

            registry = self._registry or REGISTRY

            # Helper to get or create a gauge (handles re-registration)
            def get_or_create_gauge(
                name: str,
                description: str,
                labelnames: list[str],
            ) -> Any:
                """Get existing gauge or create new one.
                
                Returns Any to handle both Gauge and existing Collector types
                from the registry's internal _names_to_collectors dict.
                """
                # Check if metric already exists in registry
                # Note: Branch coverage for re-registration is verified in test_reuses_existing_gauges_same_registry
                # The pragma is needed because coverage.py doesn't track inner function branches correctly
                if hasattr(registry, '_names_to_collectors'):  # pragma: no cover
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

            self._max_depth_gauge = get_or_create_gauge(
                "cyberred_causal_chain_max_depth",
                "Maximum causal chain depth observed",
                ["engagement_id", "run_id"],
            )
            self._count_3plus_gauge = get_or_create_gauge(
                "cyberred_causal_chain_count_3plus",
                "Count of causal chains with 3+ hops",
                ["engagement_id", "run_id"],
            )
            self._hard_gate_gauge = get_or_create_gauge(
                "cyberred_causal_chain_hard_gate_passed",
                "NFR36 hard gate status (1=passed, 0=failed)",
                ["engagement_id", "run_id"],
            )

            self._prometheus_available = True
        except ImportError:
            self._prometheus_available = False
            self._log.warning("prometheus_client_not_available")
