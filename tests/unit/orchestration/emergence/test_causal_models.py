"""Unit tests for causal chain data models (Story 7.11).

Tests ChainDepthResult and ChainStructureResult dataclasses.
"""

import pytest
import json

from cyberred.orchestration.emergence.models import AttackPath, PathStep
from cyberred.orchestration.emergence.causal import (
    ChainDepthResult,
    ChainStructureResult,
)


def create_simple_path(depth: int = 1) -> AttackPath:
    """Helper to create AttackPath with given depth."""
    steps = [
        PathStep(
            target=f"target{i}",
            technique=f"technique{i}",
            finding_id=f"f{i}",
            action_id=f"a{i}",
            decision_context=[f"f{i-1}"] if i > 0 else [],
        )
        for i in range(depth)
    ]
    return AttackPath(steps=steps)


class TestChainDepthResult:
    """Test ChainDepthResult dataclass."""

    def test_dataclass_fields(self):
        """Test all required fields exist."""
        result = ChainDepthResult(
            passed=True,
            min_required_depth=3,
            max_observed_depth=4,
            chains_meeting_requirement=2,
            total_chains=5,
            deepest_chain=None,
            depth_distribution={1: 1, 3: 2, 4: 2},
            message="NFR36 PASSED: 2 chain(s) >= 3 hops",
        )
        
        assert result.passed is True
        assert result.min_required_depth == 3
        assert result.max_observed_depth == 4
        assert result.chains_meeting_requirement == 2
        assert result.total_chains == 5
        assert result.deepest_chain is None
        assert result.depth_distribution == {1: 1, 3: 2, 4: 2}
        assert "PASSED" in result.message

    def test_dataclass_with_deepest_chain(self):
        """Test with actual deepest_chain populated."""
        deepest = create_simple_path(4)
        
        result = ChainDepthResult(
            passed=True,
            min_required_depth=3,
            max_observed_depth=4,
            chains_meeting_requirement=1,
            total_chains=3,
            deepest_chain=deepest,
            depth_distribution={2: 2, 4: 1},
            message="NFR36 PASSED",
        )
        
        assert result.deepest_chain is deepest
        assert result.deepest_chain.depth == 4

    def test_failed_result_fields(self):
        """Test failed result has correct field values."""
        result = ChainDepthResult(
            passed=False,
            min_required_depth=3,
            max_observed_depth=2,
            chains_meeting_requirement=0,
            total_chains=5,
            deepest_chain=None,
            depth_distribution={1: 3, 2: 2},
            message="NFR36 HARD GATE FAILED: No chains >= 3 hops",
        )
        
        assert result.passed is False
        assert result.chains_meeting_requirement == 0
        assert "FAILED" in result.message

    def test_json_serialization(self):
        """Test ChainDepthResult can be serialized to JSON."""
        result = ChainDepthResult(
            passed=True,
            min_required_depth=3,
            max_observed_depth=4,
            chains_meeting_requirement=2,
            total_chains=5,
            deepest_chain=None,  # Skip AttackPath for JSON
            depth_distribution={1: 1, 3: 2, 4: 2},
            message="NFR36 PASSED",
        )
        
        # Convert to dict for JSON serialization
        result_dict = {
            "passed": result.passed,
            "min_required_depth": result.min_required_depth,
            "max_observed_depth": result.max_observed_depth,
            "chains_meeting_requirement": result.chains_meeting_requirement,
            "total_chains": result.total_chains,
            "depth_distribution": result.depth_distribution,
            "message": result.message,
        }
        
        json_str = json.dumps(result_dict)
        parsed = json.loads(json_str)
        
        assert parsed["passed"] is True
        assert parsed["max_observed_depth"] == 4
        assert parsed["depth_distribution"] == {"1": 1, "3": 2, "4": 2}  # JSON keys are strings

    def test_from_paths_class_method(self):
        """Test ChainDepthResult.from_paths() class method."""
        path1 = create_simple_path(2)
        path2 = create_simple_path(3)
        path3 = create_simple_path(4)
        
        result = ChainDepthResult.from_paths([path1, path2, path3], min_depth=3)
        
        assert result.passed is True
        assert result.total_chains == 3
        assert result.chains_meeting_requirement == 2  # path2 and path3
        assert result.max_observed_depth == 4
        assert result.deepest_chain is path3

    def test_from_paths_empty_list(self):
        """Test from_paths with empty list returns failed result."""
        result = ChainDepthResult.from_paths([])
        
        assert result.passed is False
        assert result.total_chains == 0
        assert result.max_observed_depth == 0
        assert result.deepest_chain is None
        assert "FAILED" in result.message

    def test_from_paths_no_chains_meeting_requirement(self):
        """Test from_paths when no chains meet minimum depth."""
        path1 = create_simple_path(1)
        path2 = create_simple_path(2)
        
        result = ChainDepthResult.from_paths([path1, path2], min_depth=3)
        
        assert result.passed is False
        assert result.chains_meeting_requirement == 0
        assert result.max_observed_depth == 2


class TestChainStructureResult:
    """Test ChainStructureResult dataclass."""

    def test_dataclass_fields(self):
        """Test all required fields exist."""
        result = ChainStructureResult(
            valid=True,
            has_root_finding=True,
            all_links_valid=True,
            has_cycles=False,
            missing_decision_context=[],
            errors=[],
        )
        
        assert result.valid is True
        assert result.has_root_finding is True
        assert result.all_links_valid is True
        assert result.has_cycles is False
        assert result.missing_decision_context == []
        assert result.errors == []

    def test_invalid_result_fields(self):
        """Test invalid result with errors."""
        result = ChainStructureResult(
            valid=False,
            has_root_finding=False,
            all_links_valid=False,
            has_cycles=True,
            missing_decision_context=["a2", "a3"],
            errors=[
                "Missing root finding",
                "Cycle: a2",
                "NFR37: 2 steps missing decision_context",
            ],
        )
        
        assert result.valid is False
        assert result.has_root_finding is False
        assert result.has_cycles is True
        assert len(result.missing_decision_context) == 2
        assert len(result.errors) == 3

    def test_json_serialization(self):
        """Test ChainStructureResult can be serialized to JSON."""
        result = ChainStructureResult(
            valid=False,
            has_root_finding=True,
            all_links_valid=False,
            has_cycles=False,
            missing_decision_context=["a2"],
            errors=["Step 1 doesn't reference prior findings"],
        )
        
        result_dict = {
            "valid": result.valid,
            "has_root_finding": result.has_root_finding,
            "all_links_valid": result.all_links_valid,
            "has_cycles": result.has_cycles,
            "missing_decision_context": result.missing_decision_context,
            "errors": result.errors,
        }
        
        json_str = json.dumps(result_dict)
        parsed = json.loads(json_str)
        
        assert parsed["valid"] is False
        assert parsed["missing_decision_context"] == ["a2"]
        assert len(parsed["errors"]) == 1

    def test_partial_validity(self):
        """Test result can be partially valid."""
        # Has root, no cycles, but missing decision_context
        result = ChainStructureResult(
            valid=False,
            has_root_finding=True,
            all_links_valid=True,
            has_cycles=False,
            missing_decision_context=["a3"],
            errors=["NFR37: 1 step missing decision_context"],
        )
        
        assert result.valid is False  # Overall invalid
        assert result.has_root_finding is True  # But has root
        assert result.all_links_valid is True  # And links are valid
        assert result.has_cycles is False  # No cycles
        # Failed only due to missing decision_context
        assert len(result.missing_decision_context) == 1
