"""
Cyber-Red v2.0 Emergence Tests: Causal Chain Validation

Tests for 3+ hop causal chain validation (NFR36).
All tests are marked with @pytest.mark.emergence and are hard gate tests.

Causal Chain Requirements:
- Verify stigmergic coordination produces multi-hop attack chains
- Validate chains have 3+ hops (discovery -> exploitation -> post-exploitation)
- Ensure decision_context properly tracks chain dependencies

Story 7.11: Causal Chain Depth Validation - Implementation complete.
"""

import pytest

from cyberred.orchestration.emergence.models import AttackPath, PathStep
from cyberred.orchestration.emergence.causal import (
    CausalChainValidator,
    ChainDepthResult,
    ChainStructureResult,
    NFR36_MIN_CHAIN_DEPTH,
)


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


@pytest.fixture
def validator():
    """Create CausalChainValidator instance."""
    return CausalChainValidator()


@pytest.fixture
def three_hop_chain():
    """Create a valid 3-hop causal chain: recon -> exploit -> postex."""
    return create_path([
        ("192.168.1.1", "port_scan", "finding_open_port_22", "action_recon_1", []),
        ("192.168.1.1", "ssh_brute_force", "finding_valid_creds", "action_exploit_1", ["finding_open_port_22"]),
        ("192.168.1.1", "privilege_escalation", "finding_root_access", "action_postex_1", ["finding_valid_creds"]),
    ])


@pytest.fixture
def four_hop_chain():
    """Create a 4-hop causal chain with lateral movement."""
    return create_path([
        ("192.168.1.1", "port_scan", "finding_open_port_22", "action_recon_1", []),
        ("192.168.1.1", "ssh_brute_force", "finding_valid_creds", "action_exploit_1", ["finding_open_port_22"]),
        ("192.168.1.1", "privilege_escalation", "finding_root_access", "action_postex_1", ["finding_valid_creds"]),
        ("192.168.1.2", "lateral_movement", "finding_new_host_access", "action_lateral_1", ["finding_root_access"]),
    ])


@pytest.mark.emergence
class TestCausalChainDepth:
    """Test causal chain depth reaches 3+ hops."""

    def test_causal_chain_minimum_3_hops(self, validator, three_hop_chain):
        """Verify causal chains reach minimum 3 hops depth (HARD GATE: NFR36).
        
        A valid 3-hop chain example:
        Hop 1: ReconAgent discovers open port 22 (Finding₁: open_port)
               ↓ Finding₁ published to stigmergic layer
        Hop 2: ExploitAgent sees Finding₁, attempts SSH brute force (Action₁)
               → Produces Finding₂: valid_credentials
               ↓ Finding₂ published to stigmergic layer  
        Hop 3: PostExAgent sees Finding₂, escalates privileges (Action₂)
               → Produces Finding₃: root_access
        """
        result = validator.validate_chain_depth([three_hop_chain])
        
        assert result.passed is True, f"NFR36 hard gate failed: {result.message}"
        assert result.max_observed_depth >= NFR36_MIN_CHAIN_DEPTH
        assert result.chains_meeting_requirement >= 1
        assert "PASSED" in result.message

    def test_causal_chain_discovery_to_exploitation(self, validator):
        """Verify causal chain includes discovery -> exploitation hop."""
        # Create chain with recon -> exploit transition
        chain = create_path([
            ("target1", "recon", "f_discovery", "a_recon", []),
            ("target1", "exploit", "f_exploited", "a_exploit", ["f_discovery"]),
        ])
        
        # Validate the structure shows discovery led to exploitation
        structure = validator.validate_chain_structure(chain)
        
        assert structure.has_root_finding is True
        assert structure.all_links_valid is True
        # The exploit step references the discovery finding
        assert chain.steps[1].decision_context == ["f_discovery"]

    def test_causal_chain_exploitation_to_postex(self, validator):
        """Verify causal chain includes exploitation -> post-exploitation hop."""
        # Create chain with exploit -> postex transition
        chain = create_path([
            ("target1", "exploit", "f_exploited", "a_exploit", []),
            ("target1", "postex", "f_privesc", "a_postex", ["f_exploited"]),
        ])
        
        # Validate the structure shows exploitation led to postex
        structure = validator.validate_chain_structure(chain)
        
        assert structure.has_root_finding is True
        assert structure.all_links_valid is True
        # The postex step references the exploit finding
        assert chain.steps[1].decision_context == ["f_exploited"]

    def test_causal_chain_depth_exceeds_3_hops(self, validator, four_hop_chain):
        """Verify causal chains can exceed 3 hops when emergent behavior occurs."""
        result = validator.validate_chain_depth([four_hop_chain])
        
        assert result.passed is True
        assert result.max_observed_depth == 4
        assert result.max_observed_depth > NFR36_MIN_CHAIN_DEPTH
        
        # Verify the deepest chain is correctly identified
        deepest = validator.find_deepest_chain([four_hop_chain])
        assert deepest is four_hop_chain
        assert deepest.depth == 4


@pytest.mark.emergence
class TestCausalChainStructure:
    """Test causal chain structure and integrity."""

    def test_causal_chain_has_root_finding(self, validator, three_hop_chain):
        """Verify each causal chain has a root discovery finding."""
        result = validator.validate_chain_structure(three_hop_chain)
        
        assert result.has_root_finding is True
        # Root finding should be the first step's finding
        assert three_hop_chain.steps[0].finding_id == "finding_open_port_22"

    def test_causal_chain_links_are_valid(self, validator, three_hop_chain):
        """Verify each link in causal chain references valid parent finding."""
        result = validator.validate_chain_structure(three_hop_chain)
        
        assert result.all_links_valid is True
        assert result.errors == []
        
        # Verify chain linkage manually
        # Step 2 references step 1's finding
        assert three_hop_chain.steps[1].decision_context == ["finding_open_port_22"]
        # Step 3 references step 2's finding
        assert three_hop_chain.steps[2].decision_context == ["finding_valid_creds"]

    def test_causal_chain_no_cycles(self, validator):
        """Verify causal chains do not contain cycles."""
        # Create chain WITHOUT cycles (valid)
        valid_chain = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "f2", "a2", ["f1"]),
            ("t1", "postex", "f3", "a3", ["f2"]),
        ])
        
        result = validator.validate_chain_structure(valid_chain)
        assert result.has_cycles is False
        assert result.valid is True
        
        # Create chain WITH cycles (invalid - repeated action_id)
        steps_with_cycle = [
            PathStep("t1", "recon", "f1", "action_repeated", []),
            PathStep("t1", "exploit", "f2", "action_repeated", ["f1"]),  # Same action_id = cycle
        ]
        invalid_chain = AttackPath(steps=steps_with_cycle)
        
        result_invalid = validator.validate_chain_structure(invalid_chain)
        assert result_invalid.has_cycles is True
        assert result_invalid.valid is False
        assert any("Cycle" in e for e in result_invalid.errors)


@pytest.mark.emergence
class TestCausalChainDecisionContext:
    """Test causal chain decision_context tracking."""

    def test_chain_action_has_decision_context(self, validator, three_hop_chain):
        """Verify each chain action has decision_context populated."""
        result = validator.validate_chain_structure(three_hop_chain)
        
        assert result.missing_decision_context == []
        
        # All non-root steps should have decision_context
        for i, step in enumerate(three_hop_chain.steps):
            if i > 0:  # Skip root
                assert len(step.decision_context) > 0, f"Step {i} missing decision_context"

    def test_decision_context_references_parent_findings(self, validator, three_hop_chain):
        """Verify decision_context references parent findings that influenced action."""
        # Step 2 (exploit) should reference step 1's finding (discovery)
        exploit_step = three_hop_chain.steps[1]
        discovery_finding = three_hop_chain.steps[0].finding_id
        
        assert discovery_finding in exploit_step.decision_context
        
        # Step 3 (postex) should reference step 2's finding (exploit result)
        postex_step = three_hop_chain.steps[2]
        exploit_finding = three_hop_chain.steps[1].finding_id
        
        assert exploit_finding in postex_step.decision_context

    def test_decision_context_traceable_to_root(self, validator, three_hop_chain):
        """Verify decision_context chain is traceable back to root finding."""
        trace = validator.trace_chain_to_root(three_hop_chain)
        
        # Trace should go from leaf to root
        assert len(trace) == 3
        assert trace[0] == "finding_root_access"  # Leaf (last finding)
        assert trace[1] == "finding_valid_creds"  # Middle
        assert trace[2] == "finding_open_port_22"  # Root (first finding)


@pytest.mark.emergence
class TestCausalChainGate:
    """Test 3+ hop causal chain hard gate enforcement."""

    def test_causal_chain_gate_passes_with_3_hops(self, validator, three_hop_chain):
        """Verify gate passes when chains reach 3+ hops."""
        result = validator.validate_chain_depth([three_hop_chain])
        
        assert result.passed is True
        assert result.chains_meeting_requirement >= 1
        assert result.min_required_depth == NFR36_MIN_CHAIN_DEPTH
        assert "PASSED" in result.message

    def test_causal_chain_gate_fails_under_3_hops(self, validator):
        """Verify gate fails when no chains reach 3 hops."""
        # Create chains that are too shallow
        shallow_chain_1 = create_path([
            ("t1", "recon", "f1", "a1", []),
        ])  # depth 1
        
        shallow_chain_2 = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "f2", "a2", ["f1"]),
        ])  # depth 2
        
        result = validator.validate_chain_depth([shallow_chain_1, shallow_chain_2])
        
        assert result.passed is False
        assert result.chains_meeting_requirement == 0
        assert result.max_observed_depth == 2
        assert result.min_required_depth == NFR36_MIN_CHAIN_DEPTH
        assert "FAILED" in result.message

    def test_gate_passes_with_mixed_depth_chains(self, validator, three_hop_chain):
        """Verify gate passes if at least one chain meets requirement."""
        shallow_chain = create_path([
            ("t1", "recon", "f1", "a1", []),
        ])  # depth 1
        
        # Mix of shallow and deep chains
        result = validator.validate_chain_depth([shallow_chain, three_hop_chain])
        
        assert result.passed is True  # At least one chain (three_hop_chain) meets requirement
        assert result.chains_meeting_requirement == 1
        assert result.total_chains == 2

    def test_gate_with_multiple_deep_chains(self, validator, three_hop_chain, four_hop_chain):
        """Verify gate correctly counts multiple chains meeting requirement."""
        result = validator.validate_chain_depth([three_hop_chain, four_hop_chain])
        
        assert result.passed is True
        assert result.chains_meeting_requirement == 2
        assert result.max_observed_depth == 4
        assert result.depth_distribution[3] == 1
        assert result.depth_distribution[4] == 1
