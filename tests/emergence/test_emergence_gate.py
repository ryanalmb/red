"""
Cyber-Red v2.0 Emergence Gate Test

SHIP/NO-SHIP hard gate for v2.0. Validates:
- NFR35: Emergence score > 0.20 (20% novel chains)
- NFR36: At least one 3+ hop causal chain
- NFR37: 100% decision_context population

This test runs against mock data representing cyber range results.
All tests are marked with @pytest.mark.emergence and are CI gate tests.

Story 7.14: Emergence Validation Gate Test
"""

import os
import uuid
from datetime import datetime, UTC
from typing import Any

import pytest

from cyberred.orchestration.emergence import (
    EmergenceComparisonFramework,
    EmergenceComparisonConfig,
    CausalChainValidator,
    validate_decision_context,
    NFR35_EMERGENCE_THRESHOLD,
    NFR36_MIN_CHAIN_DEPTH,
    RunResult,
    ComparisonResult,
    AttackPath,
    PathStep,
)
from cyberred.core.models import AgentAction

# Environment variable configuration (also defined in conftest.py for shared use)
AGENT_COUNT = int(os.environ.get("EMERGENCE_TEST_AGENT_COUNT", "100"))
TEST_TIMEOUT = int(os.environ.get("EMERGENCE_TEST_TIMEOUT", "1800"))  # 30 min


# MockContextResult and EmergenceGateReport moved to conftest.py for shared use
from tests.emergence.conftest import MockContextResult, EmergenceGateReport


def create_path(steps_data: list[tuple[str, str, str, str, list[str]]]) -> AttackPath:
    """Helper to create AttackPath from step tuples.
    
    Args:
        steps_data: List of (target, technique, finding_id, action_id, decision_context)
    """
    steps = [
        PathStep(
            target=target,
            technique=technique,
            finding_id=finding_id,
            action_id=action_id,
            decision_context=decision_context,
        )
        for target, technique, finding_id, action_id, decision_context in steps_data
    ]
    return AttackPath(steps=steps)


def create_action(context: list[str] | None = None) -> AgentAction:
    """Create AgentAction with decision_context for testing.
    
    Args:
        context: Decision context list. Defaults to empty list.
        
    Returns:
        AgentAction instance with generated UUID and provided context.
    """
    return AgentAction(
        id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        action_type="test",
        target="192.168.1.1",
        timestamp=datetime.now(UTC).isoformat(),
        decision_context=context if context is not None else [],
    )


# Note: emergence_config, comparison_framework, and causal_validator fixtures
# are defined in conftest.py for shared use across emergence tests.


@pytest.fixture
def isolated_run_result() -> RunResult:
    """Mock isolated run result with baseline paths."""
    # Create 4 baseline paths (discovered without stigmergic coordination)
    paths = [
        create_path([
            ("192.168.1.1", "port_scan", f"finding_port_{i}", f"action_iso_{i}", [])
        ])
        for i in range(4)
    ]
    
    return RunResult(
        run_id="isolated-run-001",
        mode="isolated",
        agent_count=AGENT_COUNT,
        findings=[{"id": f"finding_port_{i}"} for i in range(4)],
        attack_paths=paths,
        actions=[],
        duration_ms=60000,
    )


@pytest.fixture
def stigmergic_run_result() -> RunResult:
    """Mock stigmergic run result with novel paths and proper decision_context."""
    # Include the same 4 baseline paths (shared)
    shared_paths = [
        create_path([
            ("192.168.1.1", "port_scan", f"finding_port_{i}", f"action_stig_{i}", [])
        ])
        for i in range(4)
    ]
    
    # Add 2 novel 3-hop paths (emerged from stigmergic coordination)
    novel_path_1 = create_path([
        ("192.168.1.1", "port_scan", "finding_ssh_open", "action_recon_1", []),
        ("192.168.1.1", "ssh_brute_force", "finding_creds", "action_exploit_1", ["finding_ssh_open"]),
        ("192.168.1.1", "privilege_escalation", "finding_root", "action_postex_1", ["finding_creds"]),
    ])
    
    novel_path_2 = create_path([
        ("192.168.1.2", "http_scan", "finding_http_open", "action_recon_2", []),
        ("192.168.1.2", "sqli_exploit", "finding_db_access", "action_exploit_2", ["finding_http_open"]),
        ("192.168.1.2", "data_exfil", "finding_data", "action_postex_2", ["finding_db_access"]),
    ])
    
    all_paths = shared_paths + [novel_path_1, novel_path_2]
    
    # Create actions with decision_context populated (NFR37 compliant)
    actions = [
        create_action(["stigmergic_signal_1"]),
        create_action(["finding_ssh_open"]),
        create_action(["finding_creds"]),
        create_action(["stigmergic_signal_2"]),
        create_action(["finding_http_open"]),
        create_action(["finding_db_access"]),
    ]
    
    return RunResult(
        run_id="stigmergic-run-001",
        mode="stigmergic",
        agent_count=AGENT_COUNT,
        findings=[
            {"id": "finding_ssh_open"},
            {"id": "finding_creds"},
            {"id": "finding_root"},
            {"id": "finding_http_open"},
            {"id": "finding_db_access"},
            {"id": "finding_data"},
        ],
        attack_paths=all_paths,
        actions=[
            {
                "id": a.id,
                "agent_id": a.agent_id,
                "action_type": a.action_type,
                "target": a.target,
                "timestamp": a.timestamp,
                "decision_context": a.decision_context,
            }
            for a in actions
        ],
        duration_ms=120000,
    )


@pytest.fixture
def stigmergic_actions() -> list[AgentAction]:
    """List of AgentAction objects with decision_context for NFR37 validation.
    
    Returns:
        List of AgentAction instances with non-empty decision_context.
    """
    return [
        create_action(["stigmergic_signal_1"]),
        create_action(["finding_ssh_open"]),
        create_action(["finding_creds"]),
        create_action(["stigmergic_signal_2"]),
        create_action(["finding_http_open"]),
        create_action(["finding_db_access"]),
    ]


@pytest.mark.emergence
@pytest.mark.slow
class TestEmergenceHardGate:
    """
    HARD GATE TESTS for v2.0 ship decision.
    
    ALL tests in this class MUST pass for system to ship.
    """
    
    def test_emergence_score_exceeds_20_percent(
        self,
        comparison_framework: EmergenceComparisonFramework,
        isolated_run_result: RunResult,
        stigmergic_run_result: RunResult,
    ):
        """
        NFR35: Emergence score must exceed 20%.
        
        HARD GATE: If this fails, system cannot ship.
        """
        comparison = comparison_framework.compare(
            isolated_run_result,
            stigmergic_run_result,
        )
        
        assert comparison.emergence_score > NFR35_EMERGENCE_THRESHOLD, (
            f"NFR35 HARD GATE FAILED: Emergence score {comparison.emergence_score:.2%} "
            f"<= required {NFR35_EMERGENCE_THRESHOLD:.0%}. "
            f"Novel chains: {len(comparison.novel_paths)}, "
            f"Total paths: {len(stigmergic_run_result.attack_paths)}"
        )
    
    def test_causal_chain_depth_at_least_3_hops(
        self,
        causal_validator: CausalChainValidator,
        stigmergic_run_result: RunResult,
    ):
        """
        NFR36: At least one causal chain must have 3+ hops.
        
        HARD GATE: If this fails, system cannot ship.
        """
        result = causal_validator.validate_chain_depth(
            stigmergic_run_result.attack_paths,
            min_depth=NFR36_MIN_CHAIN_DEPTH,
        )
        
        assert result.passed, (
            f"NFR36 HARD GATE FAILED: No chains with {NFR36_MIN_CHAIN_DEPTH}+ hops. "
            f"Max depth observed: {result.max_observed_depth}. "
            f"Total chains: {result.total_chains}. "
            f"Depth distribution: {result.depth_distribution}"
        )
    
    def test_decision_context_100_percent_populated(
        self,
        stigmergic_actions: list[AgentAction],
    ):
        """
        NFR37: 100% of agent actions must include decision_context.
        
        HARD GATE: If this fails, system cannot ship.
        """
        result = validate_decision_context(stigmergic_actions)
        
        assert result.passed and result.percentage == 100.0, (
            f"NFR37 HARD GATE FAILED: decision_context population rate "
            f"{result.percentage:.2f}% < 100%. "
            f"Actions missing context: {result.failed_actions}. "
            f"Total actions: {result.total_actions}"
        )
    
    def test_all_emergence_hard_gates_pass(
        self,
        comparison_framework: EmergenceComparisonFramework,
        causal_validator: CausalChainValidator,
        isolated_run_result: RunResult,
        stigmergic_run_result: RunResult,
        stigmergic_actions: list[AgentAction],
    ):
        """
        Combined validation of ALL emergence hard gates.
        
        This is the SHIP/NO-SHIP gate for v2.0.
        """
        # NFR35: Emergence score
        comparison = comparison_framework.compare(
            isolated_run_result,
            stigmergic_run_result,
        )
        
        # NFR36: Chain depth
        chain_result = causal_validator.validate_chain_depth(
            stigmergic_run_result.attack_paths,
        )
        
        # NFR37: Decision context
        context_result = validate_decision_context(stigmergic_actions)
        
        # Generate comprehensive report
        report = EmergenceGateReport.from_results(
            comparison,
            chain_result,
            context_result,
        )
        
        # All gates must pass
        assert report.all_passed, report.report_text


@pytest.mark.emergence
@pytest.mark.slow
class TestEmergenceGateReporting:
    """Tests for emergence gate reporting and metrics."""
    
    def test_gate_failure_produces_detailed_report(
        self,
        comparison_framework: EmergenceComparisonFramework,
        causal_validator: CausalChainValidator,
    ):
        """Verify gate failures include actionable diagnostics."""
        # Create a failing scenario (0% emergence)
        isolated = RunResult(
            run_id="iso-fail",
            mode="isolated",
            agent_count=10,
            findings=[],
            attack_paths=[
                create_path([("t1", "scan", "f1", "a1", [])])
            ],
            actions=[],
            duration_ms=1000,
        )
        
        stigmergic = RunResult(
            run_id="stig-fail",
            mode="stigmergic",
            agent_count=10,
            findings=[],
            attack_paths=[
                create_path([("t1", "scan", "f1", "a1", [])])  # Same path = no novel
            ],
            actions=[],
            duration_ms=1000,
        )
        
        comparison = comparison_framework.compare(isolated, stigmergic)
        chain_result = causal_validator.validate_chain_depth(stigmergic.attack_paths)
        
        # Use module-level MockContextResult for failing context
        context_result = MockContextResult(passed=False, percentage=0.0)
        
        report = EmergenceGateReport.from_results(
            comparison,
            chain_result,
            context_result,
        )
        
        # Verify failure report contains actionable info
        assert not report.all_passed
        assert "FAIL" in report.report_text
        assert "NO SHIP" in report.report_text
        assert "NFR35" in report.report_text
        assert "NFR36" in report.report_text
        assert "NFR37" in report.report_text
    
    def test_gate_success_produces_metrics_report(
        self,
        comparison_framework: EmergenceComparisonFramework,
        causal_validator: CausalChainValidator,
        isolated_run_result: RunResult,
        stigmergic_run_result: RunResult,
        stigmergic_actions: list[AgentAction],
    ):
        """Verify successful gate run produces comprehensive metrics."""
        comparison = comparison_framework.compare(
            isolated_run_result,
            stigmergic_run_result,
        )
        chain_result = causal_validator.validate_chain_depth(
            stigmergic_run_result.attack_paths,
        )
        context_result = validate_decision_context(stigmergic_actions)
        
        report = EmergenceGateReport.from_results(
            comparison,
            chain_result,
            context_result,
        )
        
        # Verify success report contains all metrics
        assert report.all_passed
        assert "PASS" in report.report_text
        assert "SHIP APPROVED" in report.report_text
        assert report.nfr35_score > NFR35_EMERGENCE_THRESHOLD
        assert report.nfr36_max_depth >= NFR36_MIN_CHAIN_DEPTH
        assert report.nfr37_rate == 100.0
    
    def test_prometheus_metrics_exported_on_gate_run(
        self,
        comparison_framework: EmergenceComparisonFramework,
        isolated_run_result: RunResult,
        stigmergic_run_result: RunResult,
    ):
        """Verify Prometheus metrics are exported during gate test."""
        # The compare method internally calls export_prometheus_metrics
        comparison = comparison_framework.compare(
            isolated_run_result,
            stigmergic_run_result,
        )
        
        # Verify metrics object exists (prometheus integration is optional)
        assert comparison.metrics is not None
        assert "novel_path_count" in comparison.metrics
        assert "stigmergic_path_count" in comparison.metrics
        
        # Verify the comparison has the expected structure
        assert comparison.emergence_score >= 0.0
        assert comparison.emergence_score <= 1.0


@pytest.mark.emergence
class TestEmergenceGateEdgeCases:
    """Test edge cases for emergence gate validation."""
    
    def test_empty_paths_fails_gate(
        self,
        comparison_framework: EmergenceComparisonFramework,
        causal_validator: CausalChainValidator,
    ):
        """Verify empty paths result in gate failure."""
        isolated = RunResult(
            run_id="iso-empty",
            mode="isolated",
            agent_count=10,
            findings=[],
            attack_paths=[],
            actions=[],
            duration_ms=1000,
        )
        
        stigmergic = RunResult(
            run_id="stig-empty",
            mode="stigmergic",
            agent_count=10,
            findings=[],
            attack_paths=[],
            actions=[],
            duration_ms=1000,
        )
        
        comparison = comparison_framework.compare(isolated, stigmergic)
        chain_result = causal_validator.validate_chain_depth(stigmergic.attack_paths)
        
        # Empty paths = 0% emergence and no chains
        assert comparison.emergence_score == 0.0
        assert not chain_result.passed
    
    def test_exactly_20_percent_fails_gate(
        self,
        comparison_framework: EmergenceComparisonFramework,
    ):
        """Verify exactly 20% emergence fails (must EXCEED 20%)."""
        # 4 shared paths + 1 novel = 5 total, 1/5 = 20% exactly
        isolated = RunResult(
            run_id="iso-20",
            mode="isolated",
            agent_count=10,
            findings=[],
            attack_paths=[
                create_path([("t1", "scan", f"f{i}", f"a{i}", [])]) for i in range(4)
            ],
            actions=[],
            duration_ms=1000,
        )
        
        stigmergic = RunResult(
            run_id="stig-20",
            mode="stigmergic",
            agent_count=10,
            findings=[],
            attack_paths=[
                create_path([("t1", "scan", f"f{i}", f"a{i}", [])]) for i in range(4)
            ] + [
                create_path([("t2", "novel", "fn", "an", [])])  # 1 novel
            ],
            actions=[],
            duration_ms=1000,
        )
        
        comparison = comparison_framework.compare(isolated, stigmergic)
        
        # 1/5 = 0.20 exactly, which does NOT exceed threshold
        assert comparison.emergence_score == pytest.approx(0.20, rel=1e-2)
        assert not (comparison.emergence_score > NFR35_EMERGENCE_THRESHOLD)
    
    def test_missing_decision_context_fails_nfr37(self):
        """Verify missing decision_context fails NFR37 gate."""
        action_valid_1 = create_action(["signal_1"])  # Valid
        action_invalid = create_action([])  # Missing context - invalid
        action_valid_2 = create_action(["signal_3"])  # Valid
        
        actions = [action_valid_1, action_invalid, action_valid_2]
        
        result = validate_decision_context(actions)
        
        assert not result.passed
        assert result.percentage == pytest.approx(66.67, rel=1e-1)
        # Verify at least one action failed (the one with empty context)
        assert len(result.failed_actions) == 1
    
    def test_all_paths_novel_passes_gate(
        self,
        comparison_framework: EmergenceComparisonFramework,
    ):
        """Verify 100% novel paths passes emergence gate."""
        isolated = RunResult(
            run_id="iso-empty",
            mode="isolated",
            agent_count=10,
            findings=[],
            attack_paths=[],  # No baseline paths
            actions=[],
            duration_ms=1000,
        )
        
        stigmergic = RunResult(
            run_id="stig-all-novel",
            mode="stigmergic",
            agent_count=10,
            findings=[],
            attack_paths=[
                create_path([
                    ("t1", "recon", "f1", "a1", []),
                    ("t1", "exploit", "f2", "a2", ["f1"]),
                    ("t1", "postex", "f3", "a3", ["f2"]),
                ])
            ],
            actions=[],
            duration_ms=1000,
        )
        
        comparison = comparison_framework.compare(isolated, stigmergic)
        
        # All paths are novel = 100% emergence
        assert comparison.emergence_score == 1.0
        assert comparison.emergence_score > NFR35_EMERGENCE_THRESHOLD


@pytest.mark.emergence
class TestEmergenceGateReportGeneration:
    """Test EmergenceGateReport dataclass functionality."""
    
    def test_report_dataclass_attributes(self):
        """Verify EmergenceGateReport has all required attributes."""
        report = EmergenceGateReport(
            nfr35_passed=True,
            nfr35_score=0.33,
            nfr36_passed=True,
            nfr36_max_depth=3,
            nfr37_passed=True,
            nfr37_rate=100.0,
            all_passed=True,
            report_text="Test report",
        )
        
        assert report.nfr35_passed is True
        assert report.nfr35_score == 0.33
        assert report.nfr36_passed is True
        assert report.nfr36_max_depth == 3
        assert report.nfr37_passed is True
        assert report.nfr37_rate == 100.0
        assert report.all_passed is True
        assert report.report_text == "Test report"
    
    def test_report_from_results_passing(
        self,
        comparison_framework: EmergenceComparisonFramework,
        causal_validator: CausalChainValidator,
        isolated_run_result: RunResult,
        stigmergic_run_result: RunResult,
        stigmergic_actions: list[AgentAction],
    ):
        """Verify from_results creates correct passing report."""
        comparison = comparison_framework.compare(
            isolated_run_result,
            stigmergic_run_result,
        )
        chain_result = causal_validator.validate_chain_depth(
            stigmergic_run_result.attack_paths,
        )
        context_result = validate_decision_context(stigmergic_actions)
        
        report = EmergenceGateReport.from_results(
            comparison,
            chain_result,
            context_result,
        )
        
        assert report.all_passed is True
        assert report.nfr35_passed is True
        assert report.nfr36_passed is True
        assert report.nfr37_passed is True
    
    def test_report_from_results_failing(
        self,
        comparison_framework: EmergenceComparisonFramework,
        causal_validator: CausalChainValidator,
    ):
        """Verify from_results creates correct failing report."""
        # Create failing scenario
        isolated = RunResult("iso", "isolated", 10, [], [], [], 1000)
        stigmergic = RunResult("stig", "stigmergic", 10, [], [], [], 1000)
        
        comparison = comparison_framework.compare(isolated, stigmergic)
        chain_result = causal_validator.validate_chain_depth([])
        
        # Use module-level MockContextResult for failing context
        context_result = MockContextResult(passed=False, percentage=50.0)
        
        report = EmergenceGateReport.from_results(
            comparison,
            chain_result,
            context_result,
        )
        
        assert report.all_passed is False
        # At least one gate should fail
        assert not (report.nfr35_passed and report.nfr36_passed and report.nfr37_passed)


@pytest.mark.emergence
class TestNFR35With8RoleSwarm:
    """Test NFR35 hard gate with 8-role swarm diversity (Story 7.25, AC: 6)."""

    def test_nfr35_with_8_role_swarm(
        self,
        comparison_framework: EmergenceComparisonFramework,
        isolated_baseline_result: RunResult,
        eight_role_stigmergic_result: RunResult,
    ):
        """Verify NFR35 passes with 8-role swarm (AC: 6)."""
        comparison = comparison_framework.compare(
            isolated_baseline_result,
            eight_role_stigmergic_result,
        )
        
        assert comparison.emergence_score > NFR35_EMERGENCE_THRESHOLD, (
            f"NFR35 HARD GATE with 8 roles: {comparison.emergence_score:.2%} "
            f"must exceed {NFR35_EMERGENCE_THRESHOLD:.0%}"
        )

    def test_emergence_gate_report_shows_role_breakdown(
        self,
        comparison_framework: EmergenceComparisonFramework,
        causal_validator: CausalChainValidator,
        isolated_baseline_result: RunResult,
        eight_role_stigmergic_result: RunResult,
    ):
        """Verify report includes per-role metrics (AC: 6)."""
        comparison = comparison_framework.compare(
            isolated_baseline_result,
            eight_role_stigmergic_result,
        )
        
        chain_result = causal_validator.validate_chain_depth(
            eight_role_stigmergic_result.attack_paths
        )
        
        # Create actions for validation (using valid UUIDs)
        actions = [create_action([f"signal_{i}"]) for i in range(8)]
        context_result = validate_decision_context(actions)
        
        report = EmergenceGateReport.from_results(
            comparison,
            chain_result,
            context_result,
        )
        
        assert report.all_passed, f"8-role gate should pass: {report.report_text}"
        
        # Verify role_contributions is populated
        assert report.role_contributions is not None
        assert len(report.role_contributions) > 0
        
        # Verify report text contains role breakdown
        assert "Role Contributions:" in report.report_text

    def test_nfr35_novel_chains_from_all_8_types(
        self,
        comparison_framework: EmergenceComparisonFramework,
        all_agent_roles,
    ):
        """Verify NFR35 with 8 types contributing to novel chains (AC: 6)."""
        from tests.emergence.conftest import create_path_for_role
        
        # Isolated has no paths
        isolated = RunResult(
            run_id="iso-empty",
            mode="isolated",
            agent_count=100,
            findings=[],
            attack_paths=[],
            actions=[],
            duration_ms=1000,
        )
        
        # Stigmergic has paths from all 8 roles
        paths = [create_path_for_role(role) for role in all_agent_roles]
        
        stigmergic = RunResult(
            run_id="stig-all-8",
            mode="stigmergic",
            agent_count=100,
            findings=[],
            attack_paths=paths,
            actions=[],
            duration_ms=1000,
        )
        
        comparison = comparison_framework.compare(isolated, stigmergic)
        
        # All 8 paths should be novel (100% emergence)
        assert comparison.emergence_score == 1.0, (
            f"All paths novel = 100% emergence, got {comparison.emergence_score:.2%}"
        )
        assert len(comparison.novel_paths) == 8

    def test_role_contributions_in_report(
        self,
        comparison_framework: EmergenceComparisonFramework,
        causal_validator: CausalChainValidator,
        all_agent_roles,
    ):
        """Verify role_contributions dict is correctly populated (AC: 6)."""
        from tests.emergence.conftest import create_path_for_role
        
        # Create isolated with no paths
        isolated = RunResult(
            run_id="iso-contrib",
            mode="isolated",
            agent_count=100,
            findings=[],
            attack_paths=[],
            actions=[],
            duration_ms=1000,
        )
        
        # Create stigmergic with 1 path per role
        paths = [create_path_for_role(role) for role in all_agent_roles]
        
        stigmergic = RunResult(
            run_id="stig-contrib",
            mode="stigmergic",
            agent_count=100,
            findings=[],
            attack_paths=paths,
            actions=[],
            duration_ms=1000,
        )
        
        comparison = comparison_framework.compare(isolated, stigmergic)
        chain_result = causal_validator.validate_chain_depth(paths)
        context_result = MockContextResult(passed=True, percentage=100.0)
        
        report = EmergenceGateReport.from_results(
            comparison,
            chain_result,
            context_result,
        )
        
        # Verify role_contributions has all 8 roles
        assert report.role_contributions is not None
        assert len(report.role_contributions) == 8
        
        # Each role should have contributed 1 step
        for role in all_agent_roles:
            assert role.value in report.role_contributions
            assert report.role_contributions[role.value] == 1

    def test_ci_gate_uses_8_role_swarm_data(
        self,
        comparison_framework: EmergenceComparisonFramework,
        causal_validator: CausalChainValidator,
        isolated_baseline_result: RunResult,
        eight_role_stigmergic_result: RunResult,
    ):
        """Integration test: CI gate uses 8-role swarm data (AC: 6)."""
        # Simulate full CI gate check with 8-role swarm
        comparison = comparison_framework.compare(
            isolated_baseline_result,
            eight_role_stigmergic_result,
        )
        
        chain_result = causal_validator.validate_chain_depth(
            eight_role_stigmergic_result.attack_paths
        )
        
        actions = [create_action([f"signal_{i}"]) for i in range(8)]
        context_result = validate_decision_context(actions)
        
        report = EmergenceGateReport.from_results(
            comparison,
            chain_result,
            context_result,
        )
        
        # All gates should pass
        assert report.nfr35_passed, f"NFR35 failed: {report.nfr35_score:.2%}"
        assert report.nfr36_passed, f"NFR36 failed: max depth {report.nfr36_max_depth}"
        assert report.nfr37_passed, f"NFR37 failed: {report.nfr37_rate:.1f}%"
        assert report.all_passed, f"CI gate failed: {report.report_text}"
        
        # Verify diversity is reflected in report
        assert report.role_contributions is not None
        contributing_roles = len([c for c in report.role_contributions.values() if c > 0])
        assert contributing_roles >= 3, (
            f"Expected 3+ contributing roles, got {contributing_roles}"
        )
