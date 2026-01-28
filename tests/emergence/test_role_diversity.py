"""
Cyber-Red v2.0 Emergence Tests: Role Diversity Validation

Story 7.25: Emergence Validation Update - Tests for 8 agent role diversity.

Tests that emergence validation properly covers all 8 agent types:
- RECON, EXPLOIT, POSTEX, WEBAPP, WIRELESS, AD, CREDENTIAL, FORENSICS

NFR35-37 validation with diverse agent swarms.

NOTE: Helper functions (create_path_for_role, create_multi_step_path) and
shared fixtures are defined in conftest.py to avoid duplication.
"""

import pytest

from cyberred.agents.roles import AgentRole
from cyberred.orchestration.emergence import (
    AttackPath,
    CausalChainValidator,
    EmergenceComparisonConfig,
    EmergenceComparisonFramework,
    NFR35_EMERGENCE_THRESHOLD,
    NFR36_MIN_CHAIN_DEPTH,
    PathStep,
    RunResult,
    validate_decision_context,
)
# Import helpers and shared test classes from conftest
from tests.emergence.conftest import (
    create_path_for_role,
    create_multi_step_path,
    EmergenceGateReport,
)


@pytest.mark.emergence
class TestRoleDiversityFixtures:
    """Test that role diversity fixtures are correctly created (AC: 1)."""

    def test_all_8_roles_present_in_fixture(self, all_agent_roles: list[AgentRole]):
        """Verify all 8 agent roles are available."""
        assert len(all_agent_roles) == 8
        
        expected_roles = {
            AgentRole.RECON,
            AgentRole.EXPLOIT,
            AgentRole.POSTEX,
            AgentRole.WEBAPP,
            AgentRole.WIRELESS,
            AgentRole.AD,
            AgentRole.CREDENTIAL,
            AgentRole.FORENSICS,
        }
        assert set(all_agent_roles) == expected_roles

    def test_eight_role_fixture_has_all_roles(
        self,
        eight_role_stigmergic_result: RunResult,
        all_agent_roles: list[AgentRole],
    ):
        """Verify 8-role fixture contains paths from all agent types (AC: 1)."""
        # Extract unique techniques from paths
        techniques = set()
        for path in eight_role_stigmergic_result.attack_paths:
            for step in path.steps:
                techniques.add(step.technique.replace("_technique", ""))
        
        # All 8 roles should be represented
        role_values = {role.value for role in all_agent_roles}
        assert role_values.issubset(techniques), (
            f"Missing roles in fixture: {role_values - techniques}"
        )

    def test_three_role_fixture_has_limited_roles(
        self,
        three_role_stigmergic_result: RunResult,
        three_role_list: list[AgentRole],
    ):
        """Verify 3-role fixture contains only baseline roles (AC: 5)."""
        techniques = set()
        for path in three_role_stigmergic_result.attack_paths:
            for step in path.steps:
                techniques.add(step.technique.replace("_technique", ""))
        
        expected = {role.value for role in three_role_list}
        assert techniques == expected

    @pytest.mark.parametrize("role", list(AgentRole))
    def test_create_path_for_each_role(self, role: AgentRole):
        """Verify path creation works for each role (AC: 1)."""
        path = create_path_for_role(role)
        
        assert len(path.steps) == 1
        assert role.value in path.steps[0].technique
        assert role.value in path.steps[0].finding_id
        assert role.value in path.steps[0].action_id


@pytest.mark.emergence
class TestEightRoleEmergenceScore:
    """Test emergence score calculation with 8-role diversity (AC: 2)."""

    def test_emergence_score_with_all_8_roles(
        self,
        comparison_framework: EmergenceComparisonFramework,
        isolated_baseline_result: RunResult,
        eight_role_stigmergic_result: RunResult,
    ):
        """Verify emergence score calculation with all 8 roles (AC: 2)."""
        comparison = comparison_framework.compare(
            isolated_baseline_result,
            eight_role_stigmergic_result,
        )
        
        # With 8-role diversity, we should have significant novel paths
        # Isolated has 2 paths, stigmergic has 9 paths (8 single + 1 chain)
        # Novel paths = 9 - 2 = 7 (or more depending on matching)
        assert comparison.emergence_score > NFR35_EMERGENCE_THRESHOLD, (
            f"8-role swarm emergence score {comparison.emergence_score:.2%} "
            f"should exceed {NFR35_EMERGENCE_THRESHOLD:.0%}"
        )

    def test_novel_chains_identified_across_agent_types(
        self,
        comparison_framework: EmergenceComparisonFramework,
        isolated_baseline_result: RunResult,
        eight_role_stigmergic_result: RunResult,
    ):
        """Verify novel chain detection spans all roles (AC: 2)."""
        comparison = comparison_framework.compare(
            isolated_baseline_result,
            eight_role_stigmergic_result,
        )
        
        # Novel paths should include paths from roles not in isolated
        novel_techniques = set()
        for path in comparison.novel_paths:
            for step in path.steps:
                novel_techniques.add(step.technique.replace("_technique", ""))
        
        # Should include new roles like webapp, wireless, ad, credential, forensics
        new_roles = {"webapp", "wireless", "ad", "credential", "forensics"}
        assert novel_techniques.intersection(new_roles), (
            f"Novel paths should include new roles, found: {novel_techniques}"
        )

    def test_emergence_score_multi_role_vs_single_role(
        self,
        comparison_framework: EmergenceComparisonFramework,
    ):
        """Verify emergence improves with multi-role diversity (AC: 2)."""
        # Single role isolated baseline
        isolated = RunResult(
            run_id="iso-single",
            mode="isolated",
            agent_count=10,
            findings=[],
            attack_paths=[create_path_for_role(AgentRole.RECON)],
            actions=[],
            duration_ms=1000,
        )
        
        # Single role stigmergic (same as isolated - 0% emergence)
        stigmergic_single = RunResult(
            run_id="stig-single",
            mode="stigmergic",
            agent_count=10,
            findings=[],
            attack_paths=[create_path_for_role(AgentRole.RECON)],
            actions=[],
            duration_ms=1000,
        )
        
        # Multi-role stigmergic (adds novel paths)
        stigmergic_multi = RunResult(
            run_id="stig-multi",
            mode="stigmergic",
            agent_count=10,
            findings=[],
            attack_paths=[
                create_path_for_role(AgentRole.RECON),
                create_path_for_role(AgentRole.EXPLOIT),
                create_path_for_role(AgentRole.WEBAPP),
            ],
            actions=[],
            duration_ms=1000,
        )
        
        score_single = comparison_framework.compare(isolated, stigmergic_single).emergence_score
        score_multi = comparison_framework.compare(isolated, stigmergic_multi).emergence_score
        
        assert score_multi > score_single, (
            f"Multi-role emergence {score_multi:.2%} should exceed "
            f"single-role {score_single:.2%}"
        )


@pytest.mark.emergence
class TestCrossRoleCausalChains:
    """Test causal chain validation across multiple roles (AC: 3)."""

    def test_causal_chain_spans_multiple_agent_types(
        self,
        causal_validator: CausalChainValidator,
    ):
        """Verify chain spanning RECON→EXPLOIT→POSTEX→AD validates (AC: 3)."""
        chain = create_multi_step_path([
            AgentRole.RECON,
            AgentRole.EXPLOIT,
            AgentRole.POSTEX,
            AgentRole.AD,
        ])
        
        result = causal_validator.validate_chain_depth([chain])
        
        assert result.passed, f"Cross-role 4-hop chain should pass: {result.message}"
        assert result.max_observed_depth == 4
        assert result.chains_meeting_requirement >= 1

    def test_decision_context_links_cross_role_findings(
        self,
        causal_validator: CausalChainValidator,
    ):
        """Verify decision_context links findings across roles (AC: 3)."""
        chain = create_multi_step_path([
            AgentRole.RECON,
            AgentRole.EXPLOIT,
            AgentRole.POSTEX,
        ])
        
        # Verify each step after root references previous finding
        assert chain.steps[1].decision_context == ["finding_recon_001"]
        assert chain.steps[2].decision_context == ["finding_exploit_002"]
        
        structure = causal_validator.validate_chain_structure(chain)
        assert structure.all_links_valid

    def test_chain_depth_with_8_role_diversity(
        self,
        causal_validator: CausalChainValidator,
        all_agent_roles: list[AgentRole],
    ):
        """Verify depth calculation with all 8 roles in chain (AC: 3)."""
        # Create a chain using all 8 roles
        chain = create_multi_step_path(all_agent_roles)
        
        assert chain.depth == 8, "8-role chain should have depth 8"
        
        result = causal_validator.validate_chain_depth([chain])
        assert result.passed
        assert result.max_observed_depth == 8

    @pytest.fixture
    def cross_role_causal_chain(self) -> AttackPath:
        """Create chain spanning RECON→EXPLOIT→POSTEX→AD (AC: 3)."""
        return create_multi_step_path([
            AgentRole.RECON,
            AgentRole.EXPLOIT,
            AgentRole.POSTEX,
            AgentRole.AD,
        ])

    def test_cross_role_chain_structure(
        self,
        causal_validator: CausalChainValidator,
        cross_role_causal_chain: AttackPath,
    ):
        """Verify cross-role chain has valid structure."""
        structure = causal_validator.validate_chain_structure(cross_role_causal_chain)
        
        assert structure.valid
        assert structure.has_root_finding
        assert structure.all_links_valid
        assert not structure.has_cycles


@pytest.mark.emergence
class TestDecisionContextAllRoles:
    """Test decision_context validation for all 8 roles (AC: 4)."""

    @pytest.mark.parametrize("role", list(AgentRole))
    def test_decision_context_populated_for_each_role(self, role: AgentRole):
        """Verify decision_context can be created for each role (AC: 4)."""
        path = create_path_for_role(
            role,
            decision_context=[f"signal_from_{role.value}"],
        )
        
        assert path.steps[0].decision_context == [f"signal_from_{role.value}"]

    def test_decision_context_references_cross_role_signals(
        self,
        causal_validator: CausalChainValidator,
    ):
        """Verify decision_context tracks inter-role signals (AC: 4)."""
        # Create a path where EXPLOIT references RECON finding
        # and POSTEX references EXPLOIT finding
        chain = create_multi_step_path([
            AgentRole.RECON,
            AgentRole.EXPLOIT,
            AgentRole.POSTEX,
        ])
        
        # Trace from leaf to root
        trace = causal_validator.trace_chain_to_root(chain)
        
        # Should trace: postex → exploit → recon
        assert len(trace) == 3
        assert "postex" in trace[0]
        assert "exploit" in trace[1]
        assert "recon" in trace[2]

    def test_decision_context_8_role_actions(
        self,
        all_agent_roles: list[AgentRole],
    ):
        """Verify decision_context validation with 8-role actions (AC: 4)."""
        from cyberred.orchestration.emergence import validate_decision_context
        from cyberred.core.models import AgentAction
        from datetime import datetime, UTC
        import uuid
        
        # Create actions for all 8 roles with decision_context
        actions = [
            AgentAction(
                id=str(uuid.uuid4()),
                agent_id=str(uuid.uuid4()),  # Must be valid UUID
                action_type=f"{role.value}_action",
                target="192.168.1.1",
                timestamp=datetime.now(UTC).isoformat(),
                decision_context=[f"signal_{role.value}"],
            )
            for role in all_agent_roles
        ]
        
        result = validate_decision_context(actions)
        
        assert result.passed, f"8-role actions should pass: {result.failed_actions}"
        assert result.percentage == 100.0
        assert result.total_actions == 8


@pytest.mark.emergence
class TestDiversityComparison:
    """Test diversity impact on emergence (AC: 5)."""

    def test_emergence_improvement_with_diversity(
        self,
        comparison_framework: EmergenceComparisonFramework,
        isolated_baseline_result: RunResult,
        three_role_stigmergic_result: RunResult,
        eight_role_stigmergic_result: RunResult,
    ):
        """Verify 8-role swarm has higher emergence than 3-role (AC: 5)."""
        score_3_role = comparison_framework.compare(
            isolated_baseline_result,
            three_role_stigmergic_result,
        ).emergence_score
        
        score_8_role = comparison_framework.compare(
            isolated_baseline_result,
            eight_role_stigmergic_result,
        ).emergence_score
        
        assert score_8_role >= score_3_role, (
            f"8-role emergence {score_8_role:.2%} should >= "
            f"3-role emergence {score_3_role:.2%}"
        )

    def test_role_diversity_increases_novel_path_discovery(
        self,
        comparison_framework: EmergenceComparisonFramework,
        isolated_baseline_result: RunResult,
        three_role_stigmergic_result: RunResult,
        eight_role_stigmergic_result: RunResult,
    ):
        """Verify more roles discover more novel paths (AC: 5)."""
        comparison_3 = comparison_framework.compare(
            isolated_baseline_result,
            three_role_stigmergic_result,
        )
        
        comparison_8 = comparison_framework.compare(
            isolated_baseline_result,
            eight_role_stigmergic_result,
        )
        
        assert len(comparison_8.novel_paths) >= len(comparison_3.novel_paths), (
            f"8-role novel paths ({len(comparison_8.novel_paths)}) should >= "
            f"3-role novel paths ({len(comparison_3.novel_paths)})"
        )

    def test_diversity_hypothesis_more_roles_higher_emergence(
        self,
        comparison_framework: EmergenceComparisonFramework,
    ):
        """Statistical test: diversity correlates with emergence (AC: 5)."""
        # Create isolated baseline with 1 path
        isolated = RunResult(
            run_id="iso-hyp",
            mode="isolated",
            agent_count=10,
            findings=[],
            attack_paths=[create_path_for_role(AgentRole.RECON, finding_prefix="iso")],
            actions=[],
            duration_ms=1000,
        )
        
        # Test emergence with increasing diversity
        scores = []
        role_counts = [1, 2, 4, 8]
        
        for count in role_counts:
            roles = list(AgentRole)[:count]
            paths = [create_path_for_role(r) for r in roles]
            
            stigmergic = RunResult(
                run_id=f"stig-{count}",
                mode="stigmergic",
                agent_count=10,
                findings=[],
                attack_paths=paths,
                actions=[],
                duration_ms=1000,
            )
            
            score = comparison_framework.compare(isolated, stigmergic).emergence_score
            scores.append(score)
        
        # Verify scores are non-decreasing (more roles >= same emergence)
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1], (
                f"Emergence should not decrease with more roles: "
                f"{role_counts[i]} roles ({scores[i]:.2%}) < "
                f"{role_counts[i-1]} roles ({scores[i-1]:.2%})"
            )


@pytest.mark.emergence
class TestNFR35WithFullDiversity:
    """Test NFR35 hard gate with 8-role swarm (AC: 6)."""

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
        all_agent_roles: list[AgentRole],
    ):
        """Verify report includes per-role metrics (AC: 6)."""
        # EmergenceGateReport and validate_decision_context imported at module level
        from cyberred.core.models import AgentAction
        from datetime import datetime, UTC
        import uuid
        
        comparison = comparison_framework.compare(
            isolated_baseline_result,
            eight_role_stigmergic_result,
        )
        
        chain_result = causal_validator.validate_chain_depth(
            eight_role_stigmergic_result.attack_paths
        )
        
        # Create actions for validation (agent_id must be valid UUID)
        actions = [
            AgentAction(
                id=str(uuid.uuid4()),
                agent_id=str(uuid.uuid4()),  # Must be valid UUID
                action_type=f"{role.value}_action",
                target="192.168.1.1",
                timestamp=datetime.now(UTC).isoformat(),
                decision_context=[f"signal_{role.value}"],
            )
            for role in all_agent_roles
        ]
        context_result = validate_decision_context(actions)
        
        report = EmergenceGateReport.from_results(
            comparison,
            chain_result,
            context_result,
        )
        
        assert report.all_passed, f"8-role gate should pass: {report.report_text}"
        
        # Calculate role contributions from novel paths
        role_contributions: dict[AgentRole, int] = {role: 0 for role in AgentRole}
        for path in comparison.novel_paths:
            for step in path.steps:
                technique = step.technique.replace("_technique", "")
                for role in AgentRole:
                    if role.value == technique:
                        role_contributions[role] += 1
        
        # Verify we have contributions from multiple roles
        contributing_roles = sum(1 for count in role_contributions.values() if count > 0)
        assert contributing_roles >= 3, (
            f"Should have contributions from 3+ roles, got {contributing_roles}: "
            f"{role_contributions}"
        )

    def test_nfr35_novel_chains_from_all_8_types(
        self,
        comparison_framework: EmergenceComparisonFramework,
        all_agent_roles: list[AgentRole],
    ):
        """Verify NFR35 with 8 types contributing to novel chains (AC: 6)."""
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
