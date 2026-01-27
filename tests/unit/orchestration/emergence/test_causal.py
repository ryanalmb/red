"""Unit tests for CausalChainValidator (Story 7.11).

Tests causal chain depth validation for NFR36 hard gate:
- At least one causal chain with 3+ hops required
- Chain structure validation (root finding, no cycles, valid links)
- Decision context traceability (NFR37 compliance)
- Prometheus metrics export (OBS12)
"""

import pytest
from unittest.mock import Mock, patch

from cyberred.orchestration.emergence.models import AttackPath, PathStep
from cyberred.orchestration.emergence.causal import (
    CausalChainValidator,
    ChainDepthResult,
    ChainStructureResult,
    NFR36_MIN_CHAIN_DEPTH,
)


@pytest.fixture
def validator():
    """Create CausalChainValidator instance."""
    return CausalChainValidator()


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


class TestCausalChainValidatorInstantiation:
    """Test CausalChainValidator instantiation."""

    def test_instantiation_default(self):
        """Test default instantiation without prometheus registry."""
        validator = CausalChainValidator()
        assert validator is not None

    def test_instantiation_with_registry(self):
        """Test instantiation with custom prometheus registry."""
        mock_registry = Mock()
        validator = CausalChainValidator(prometheus_registry=mock_registry)
        assert validator is not None

    def test_multiple_instances_no_error(self):
        """Test creating multiple instances doesn't raise re-registration error."""
        v1 = CausalChainValidator()
        v2 = CausalChainValidator()
        v3 = CausalChainValidator()
        assert v1 is not v2
        assert v2 is not v3


class TestValidateChainDepth:
    """Test validate_chain_depth() method."""

    def test_empty_paths_returns_failed(self, validator):
        """Edge case: empty paths list returns failed result."""
        result = validator.validate_chain_depth([])
        
        assert result.passed is False
        assert result.total_chains == 0
        assert result.max_observed_depth == 0
        assert result.chains_meeting_requirement == 0
        assert result.deepest_chain is None
        assert "FAILED" in result.message

    def test_all_paths_under_min_depth_fails(self, validator):
        """Edge case: all paths depth < 3 returns failed result."""
        path1 = create_path([
            ("target1", "recon", "f1", "a1", []),
        ])
        path2 = create_path([
            ("target1", "recon", "f1", "a1", []),
            ("target1", "exploit", "f2", "a2", ["f1"]),
        ])
        
        result = validator.validate_chain_depth([path1, path2])
        
        assert result.passed is False
        assert result.max_observed_depth == 2
        assert result.chains_meeting_requirement == 0
        assert "FAILED" in result.message

    def test_single_path_meeting_depth_passes(self, validator):
        """Edge case: single path with depth >= 3 returns passed result."""
        path = create_path([
            ("target1", "recon", "f1", "a1", []),
            ("target1", "exploit", "f2", "a2", ["f1"]),
            ("target1", "postex", "f3", "a3", ["f2"]),
        ])
        
        result = validator.validate_chain_depth([path])
        
        assert result.passed is True
        assert result.max_observed_depth == 3
        assert result.chains_meeting_requirement == 1
        assert result.total_chains == 1
        assert "PASSED" in result.message

    def test_multiple_paths_mixed_depths(self, validator):
        """Test with mix of passing and failing depth paths."""
        path1 = create_path([("t1", "recon", "f1", "a1", [])])  # depth 1
        path2 = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "f2", "a2", ["f1"]),
            ("t1", "postex", "f3", "a3", ["f2"]),
        ])  # depth 3
        path3 = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "f2", "a2", ["f1"]),
            ("t1", "postex", "f3", "a3", ["f2"]),
            ("t1", "lateral", "f4", "a4", ["f3"]),
        ])  # depth 4
        
        result = validator.validate_chain_depth([path1, path2, path3])
        
        assert result.passed is True
        assert result.max_observed_depth == 4
        assert result.chains_meeting_requirement == 2
        assert result.total_chains == 3
        assert result.depth_distribution == {1: 1, 3: 1, 4: 1}

    def test_custom_min_depth(self, validator):
        """Test with custom minimum depth requirement."""
        path = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "f2", "a2", ["f1"]),
            ("t1", "postex", "f3", "a3", ["f2"]),
        ])  # depth 3
        
        # Should pass with min_depth=3
        result3 = validator.validate_chain_depth([path], min_depth=3)
        assert result3.passed is True
        
        # Should fail with min_depth=4
        result4 = validator.validate_chain_depth([path], min_depth=4)
        assert result4.passed is False


class TestFindDeepestChain:
    """Test find_deepest_chain() method."""

    def test_empty_paths_returns_none(self, validator):
        """Empty paths returns None."""
        result = validator.find_deepest_chain([])
        assert result is None

    def test_single_path_returns_it(self, validator):
        """Single path is returned as deepest."""
        path = create_path([("t1", "recon", "f1", "a1", [])])
        result = validator.find_deepest_chain([path])
        assert result is path

    def test_returns_deepest_path(self, validator):
        """Returns the path with maximum depth."""
        path1 = create_path([("t1", "recon", "f1", "a1", [])])  # depth 1
        path2 = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "f2", "a2", ["f1"]),
            ("t1", "postex", "f3", "a3", ["f2"]),
        ])  # depth 3
        path3 = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "f2", "a2", ["f1"]),
        ])  # depth 2
        
        result = validator.find_deepest_chain([path1, path2, path3])
        assert result is path2
        assert result.depth == 3


class TestGetChainsByDepth:
    """Test get_chains_by_depth() method."""

    def test_empty_paths_returns_empty_dict(self, validator):
        """Empty paths returns empty dict."""
        result = validator.get_chains_by_depth([])
        assert result == {}

    def test_groups_by_depth(self, validator):
        """Groups paths by their depth."""
        path1a = create_path([("t1", "recon", "f1", "a1", [])])  # depth 1
        path1b = create_path([("t2", "scan", "f2", "a2", [])])   # depth 1
        path2 = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "f2", "a2", ["f1"]),
        ])  # depth 2
        path3 = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "f2", "a2", ["f1"]),
            ("t1", "postex", "f3", "a3", ["f2"]),
        ])  # depth 3
        
        result = validator.get_chains_by_depth([path1a, path1b, path2, path3])
        
        assert len(result) == 3
        assert len(result[1]) == 2
        assert len(result[2]) == 1
        assert len(result[3]) == 1
        assert path1a in result[1]
        assert path1b in result[1]
        assert path2 in result[2]
        assert path3 in result[3]


class TestValidateChainStructure:
    """Test validate_chain_structure() method."""

    def test_valid_chain_structure(self, validator):
        """Valid chain passes all structure checks."""
        path = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "f2", "a2", ["f1"]),
            ("t1", "postex", "f3", "a3", ["f2"]),
        ])
        
        result = validator.validate_chain_structure(path)
        
        assert result.valid is True
        assert result.has_root_finding is True
        assert result.all_links_valid is True
        assert result.has_cycles is False
        assert result.missing_decision_context == []
        assert result.errors == []

    def test_missing_root_finding(self, validator):
        """Detects missing root finding."""
        path = create_path([
            ("t1", "recon", "", "a1", []),  # No finding_id
        ])
        
        result = validator.validate_chain_structure(path)
        
        assert result.valid is False
        assert result.has_root_finding is False
        assert "Missing root finding" in result.errors

    def test_detects_cycles(self, validator):
        """Detects cycles in chain (repeated action_ids)."""
        steps = [
            PathStep("t1", "recon", "f1", "a1", []),
            PathStep("t1", "exploit", "f2", "a1", ["f1"]),  # Same action_id!
        ]
        path = AttackPath(steps=steps)
        
        result = validator.validate_chain_structure(path)
        
        assert result.valid is False
        assert result.has_cycles is True
        assert any("Cycle" in e for e in result.errors)

    def test_detects_missing_decision_context(self, validator):
        """Detects steps missing decision_context (NFR37)."""
        path = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "f2", "a2", []),  # Missing decision_context!
        ])
        
        result = validator.validate_chain_structure(path)
        
        assert result.valid is False
        assert "a2" in result.missing_decision_context
        assert any("NFR37" in e for e in result.errors)

    def test_invalid_links(self, validator):
        """Detects invalid parent references."""
        path = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "f2", "a2", ["f999"]),  # References non-existent finding
        ])
        
        result = validator.validate_chain_structure(path)
        
        assert result.valid is False
        assert result.all_links_valid is False

    def test_empty_path(self, validator):
        """Empty path fails validation."""
        path = AttackPath(steps=[])
        
        result = validator.validate_chain_structure(path)
        
        assert result.valid is False
        assert result.has_root_finding is False


class TestTraceChainToRoot:
    """Test trace_chain_to_root() method."""

    def test_empty_path_returns_empty(self, validator):
        """Empty path returns empty list."""
        path = AttackPath(steps=[])
        result = validator.trace_chain_to_root(path)
        assert result == []

    def test_returns_finding_ids_leaf_to_root(self, validator):
        """Returns finding_ids from leaf to root (reversed order)."""
        path = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "f2", "a2", ["f1"]),
            ("t1", "postex", "f3", "a3", ["f2"]),
        ])
        
        result = validator.trace_chain_to_root(path)
        
        # Should be reversed: f3 (leaf) -> f2 -> f1 (root)
        assert result == ["f3", "f2", "f1"]

    def test_skips_empty_finding_ids(self, validator):
        """Skips steps with empty finding_ids."""
        path = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "", "a2", ["f1"]),  # No finding produced
            ("t1", "postex", "f3", "a3", ["f1"]),
        ])
        
        result = validator.trace_chain_to_root(path)
        assert result == ["f3", "f1"]


class TestPrometheusMetrics:
    """Test Prometheus metrics export (OBS12)."""

    def test_metrics_exported_when_available(self, validator):
        """Metrics are exported when Prometheus is available."""
        validator._prometheus_available = True
        validator._max_depth_gauge = Mock()
        validator._count_3plus_gauge = Mock()
        validator._hard_gate_gauge = Mock()
        
        result = ChainDepthResult(
            passed=True,
            min_required_depth=3,
            max_observed_depth=4,
            chains_meeting_requirement=2,
            total_chains=5,
            deepest_chain=None,
            depth_distribution={1: 1, 2: 2, 4: 2},
            message="NFR36 PASSED",
        )
        
        validator.export_prometheus_metrics(result, "eng123", "run456")
        
        validator._max_depth_gauge.labels.assert_called_with(engagement_id="eng123", run_id="run456")
        validator._max_depth_gauge.labels.return_value.set.assert_called_with(4)
        validator._count_3plus_gauge.labels.return_value.set.assert_called_with(2)
        validator._hard_gate_gauge.labels.return_value.set.assert_called_with(1)

    def test_metrics_skipped_when_unavailable(self, validator):
        """Metrics export is a no-op when Prometheus unavailable."""
        validator._prometheus_available = False
        
        result = ChainDepthResult(
            passed=True,
            min_required_depth=3,
            max_observed_depth=4,
            chains_meeting_requirement=2,
            total_chains=5,
            deepest_chain=None,
            depth_distribution={},
            message="NFR36 PASSED",
        )
        
        # Should not raise
        validator.export_prometheus_metrics(result, "eng123", "run456")

    def test_hard_gate_gauge_zero_on_fail(self, validator):
        """Hard gate gauge is 0 when validation fails."""
        validator._prometheus_available = True
        validator._max_depth_gauge = Mock()
        validator._count_3plus_gauge = Mock()
        validator._hard_gate_gauge = Mock()
        
        result = ChainDepthResult(
            passed=False,
            min_required_depth=3,
            max_observed_depth=2,
            chains_meeting_requirement=0,
            total_chains=5,
            deepest_chain=None,
            depth_distribution={},
            message="NFR36 FAILED",
        )
        
        validator.export_prometheus_metrics(result, "eng123", "run456")
        
        validator._hard_gate_gauge.labels.return_value.set.assert_called_with(0)


class TestNFR36Constant:
    """Test NFR36_MIN_CHAIN_DEPTH constant."""

    def test_constant_value(self):
        """NFR36 requires minimum 3 hops."""
        assert NFR36_MIN_CHAIN_DEPTH == 3

    def test_validator_uses_constant_by_default(self, validator):
        """Validator uses NFR36 constant as default min_depth."""
        path = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "f2", "a2", ["f1"]),
            ("t1", "postex", "f3", "a3", ["f2"]),
        ])
        
        result = validator.validate_chain_depth([path])
        assert result.min_required_depth == NFR36_MIN_CHAIN_DEPTH


class TestPrometheusSetup:
    """Test Prometheus metrics setup."""

    def test_setup_creates_gauges_with_prometheus_available(self):
        """Test Prometheus gauges are created when prometheus_client is available."""
        # Import prometheus_client to ensure it's available
        try:
            from prometheus_client import CollectorRegistry
            
            # Use isolated registry to avoid conflicts
            registry = CollectorRegistry()
            validator = CausalChainValidator(prometheus_registry=registry)
            
            assert validator._prometheus_available is True
            assert validator._max_depth_gauge is not None
            assert validator._count_3plus_gauge is not None
            assert validator._hard_gate_gauge is not None
        except ImportError:
            pytest.skip("prometheus_client not available")

    def test_setup_handles_reregistration(self):
        """Test multiple validators with same registry don't cause re-registration errors."""
        try:
            from prometheus_client import CollectorRegistry
            
            registry = CollectorRegistry()
            v1 = CausalChainValidator(prometheus_registry=registry)
            v2 = CausalChainValidator(prometheus_registry=registry)
            
            # Both should have metrics available
            assert v1._prometheus_available is True
            assert v2._prometheus_available is True
        except ImportError:
            pytest.skip("prometheus_client not available")

    def test_export_metrics_with_real_prometheus(self):
        """Test actual Prometheus export with real registry."""
        try:
            from prometheus_client import CollectorRegistry
            
            registry = CollectorRegistry()
            validator = CausalChainValidator(prometheus_registry=registry)
            
            path = create_path([
                ("t1", "recon", "f1", "a1", []),
                ("t1", "exploit", "f2", "a2", ["f1"]),
                ("t1", "postex", "f3", "a3", ["f2"]),
            ])
            
            result = validator.validate_chain_depth([path])
            
            # Export metrics
            validator.export_prometheus_metrics(result, "eng_test", "run_test")
            
            # Verify metrics were set (accessing internal state)
            assert validator._prometheus_available is True
        except ImportError:
            pytest.skip("prometheus_client not available")

    def test_setup_without_prometheus(self):
        """Test graceful handling when prometheus_client is not available."""
        validator = CausalChainValidator()
        
        # The module is available in our test env, but we can test 
        # that the fallback path works by verifying the validator still functions
        path = create_path([
            ("t1", "recon", "f1", "a1", []),
            ("t1", "exploit", "f2", "a2", ["f1"]),
            ("t1", "postex", "f3", "a3", ["f2"]),
        ])
        
        result = validator.validate_chain_depth([path])
        assert result.passed is True
        
        # Export should not raise even if prometheus is unavailable
        validator.export_prometheus_metrics(result, "eng_test", "run_test")

    def test_reuses_existing_gauges_same_registry(self):
        """Test that creating multiple validators with same registry reuses gauges."""
        from prometheus_client import CollectorRegistry
        
        registry = CollectorRegistry()
        
        # First validator creates the gauges
        v1 = CausalChainValidator(prometheus_registry=registry)
        gauge1 = v1._max_depth_gauge
        
        # Verify registry has the metrics registered
        assert hasattr(registry, '_names_to_collectors')
        assert 'cyberred_causal_chain_max_depth' in registry._names_to_collectors
        
        # Second validator should reuse existing gauges (not create new ones)
        # This exercises the branch at line 377->383 where existing is not None
        v2 = CausalChainValidator(prometheus_registry=registry)
        gauge2 = v2._max_depth_gauge
        
        # Should be the exact same gauge object (proves reuse happened)
        assert gauge1 is gauge2
        assert v1._count_3plus_gauge is v2._count_3plus_gauge
        assert v1._hard_gate_gauge is v2._hard_gate_gauge
        
        # Create a third one to be extra sure
        v3 = CausalChainValidator(prometheus_registry=registry)
        assert gauge1 is v3._max_depth_gauge

    def test_import_error_handling(self):
        """Test ImportError branch by simulating missing prometheus_client."""
        import sys
        
        # Save original module
        original_prometheus = sys.modules.get('prometheus_client')
        
        try:
            # Remove prometheus_client from sys.modules to simulate ImportError
            if 'prometheus_client' in sys.modules:
                del sys.modules['prometheus_client']
            
            # Also need to block future imports
            import builtins
            original_import = builtins.__import__
            
            def mock_import(name, *args, **kwargs):
                if name == 'prometheus_client' or name.startswith('prometheus_client.'):
                    raise ImportError("Mocked: No module named 'prometheus_client'")
                return original_import(name, *args, **kwargs)
            
            builtins.__import__ = mock_import
            
            # Need to reimport the module to trigger the ImportError path
            # But since CausalChainValidator is already imported, we test 
            # by directly calling _setup_prometheus_metrics after setting unavailable
            validator = CausalChainValidator.__new__(CausalChainValidator)
            validator._log = Mock()
            validator._registry = None
            validator._prometheus_available = False
            validator._max_depth_gauge = None
            validator._count_3plus_gauge = None
            validator._hard_gate_gauge = None
            
            # This will hit ImportError branch
            builtins.__import__ = mock_import
            validator._setup_prometheus_metrics()
            
            assert validator._prometheus_available is False
            assert validator._log.warning.called
        finally:
            # Restore original import
            builtins.__import__ = original_import
            # Restore prometheus_client if it was there
            if original_prometheus:
                sys.modules['prometheus_client'] = original_prometheus
