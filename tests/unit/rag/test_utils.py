"""Unit tests for RAG utilities module (Story 6-13)."""
import pytest
from cyberred.rag.utils import (
    validate_technique_id,
    get_tactics_for_technique,
    get_tactics_for_techniques,
    set_technique_tactics_cache,
    get_technique_tactics_cache,
    clear_technique_tactics_cache,
)


class TestValidateTechniqueId:
    """Tests for validate_technique_id function."""

    def test_valid_technique_id(self) -> None:
        """Valid T#### format."""
        assert validate_technique_id("T1059") is True

    def test_valid_sub_technique_id(self) -> None:
        """Valid T####.### format."""
        assert validate_technique_id("T1059.001") is True

    def test_invalid_short_id(self) -> None:
        """Too few digits."""
        assert validate_technique_id("T12") is False
        assert validate_technique_id("T123") is False

    def test_invalid_long_id(self) -> None:
        """Too many digits."""
        assert validate_technique_id("T12345") is False

    def test_invalid_prefix(self) -> None:
        """Wrong prefix."""
        assert validate_technique_id("A1059") is False
        assert validate_technique_id("t1059") is False  # lowercase

    def test_invalid_letters_in_id(self) -> None:
        """Letters in numeric portion."""
        assert validate_technique_id("TXXX") is False
        assert validate_technique_id("T1X59") is False

    def test_invalid_sub_technique_format(self) -> None:
        """Invalid sub-technique format."""
        assert validate_technique_id("T1059.1") is False
        assert validate_technique_id("T1059.12") is False
        assert validate_technique_id("T1059.1234") is False

    def test_empty_string(self) -> None:
        """Empty string."""
        assert validate_technique_id("") is False

    def test_none_value(self) -> None:
        """None value (should handle gracefully)."""
        assert validate_technique_id(None) is False  # type: ignore


class TestTacticsCacheFunctions:
    """Tests for tactics cache functions."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        clear_technique_tactics_cache()

    def teardown_method(self) -> None:
        """Clear cache after each test."""
        clear_technique_tactics_cache()

    def test_set_and_get_cache(self) -> None:
        """Set and retrieve cache."""
        mapping = {
            "T1059": ["execution"],
            "T1078": ["defense-evasion", "initial-access", "persistence", "privilege-escalation"],
        }
        set_technique_tactics_cache(mapping)
        
        cached = get_technique_tactics_cache()
        assert cached == mapping

    def test_cache_is_copy(self) -> None:
        """Cache operations return copies, not references."""
        mapping = {"T1059": ["execution"]}
        set_technique_tactics_cache(mapping)
        
        # Get cached and modify returned copy
        cached = get_technique_tactics_cache()
        cached["T1059"].append("persistence")
        
        # Original cache should be unaffected
        cached2 = get_technique_tactics_cache()
        assert cached2["T1059"] == ["execution"]

    def test_clear_cache(self) -> None:
        """Clear cache works."""
        set_technique_tactics_cache({"T1059": ["execution"]})
        clear_technique_tactics_cache()
        
        assert get_technique_tactics_cache() == {}


class TestGetTacticsForTechnique:
    """Tests for get_tactics_for_technique function."""

    def setup_method(self) -> None:
        """Set up cache with test data."""
        clear_technique_tactics_cache()
        set_technique_tactics_cache({
            "T1059": ["execution"],
            "T1078": ["defense-evasion", "initial-access", "persistence", "privilege-escalation"],
            "T1550": ["defense-evasion", "lateral-movement"],
        })

    def teardown_method(self) -> None:
        """Clear cache after each test."""
        clear_technique_tactics_cache()

    def test_exact_match(self) -> None:
        """Exact technique ID match."""
        tactics = get_tactics_for_technique("T1059")
        assert tactics == ["execution"]

    def test_sub_technique_uses_parent(self) -> None:
        """Sub-technique falls back to parent tactics."""
        tactics = get_tactics_for_technique("T1059.001")
        assert tactics == ["execution"]

    def test_unknown_technique(self) -> None:
        """Unknown technique returns empty list."""
        tactics = get_tactics_for_technique("T9999")
        assert tactics == []

    def test_empty_string(self) -> None:
        """Empty string returns empty list."""
        tactics = get_tactics_for_technique("")
        assert tactics == []

    def test_returns_copy(self) -> None:
        """Returns a copy, not a reference."""
        tactics = get_tactics_for_technique("T1059")
        tactics.append("persistence")  # modify returned list
        
        # Original cache unaffected
        assert get_tactics_for_technique("T1059") == ["execution"]


class TestGetTacticsForTechniques:
    """Tests for get_tactics_for_techniques function."""

    def setup_method(self) -> None:
        """Set up cache with test data."""
        clear_technique_tactics_cache()
        set_technique_tactics_cache({
            "T1059": ["execution"],
            "T1078": ["defense-evasion", "initial-access"],
            "T1550": ["defense-evasion", "lateral-movement"],
        })

    def teardown_method(self) -> None:
        """Clear cache after each test."""
        clear_technique_tactics_cache()

    def test_multiple_techniques(self) -> None:
        """Multiple techniques combine tactics."""
        tactics = get_tactics_for_techniques(["T1059", "T1078"])
        # Should be sorted and deduplicated
        assert tactics == ["defense-evasion", "execution", "initial-access"]

    def test_deduplicated(self) -> None:
        """Duplicate tactics are removed."""
        tactics = get_tactics_for_techniques(["T1078", "T1550"])
        # Both have defense-evasion
        assert tactics.count("defense-evasion") == 1

    def test_sorted_output(self) -> None:
        """Output is sorted alphabetically."""
        tactics = get_tactics_for_techniques(["T1059", "T1078", "T1550"])
        assert tactics == sorted(tactics)

    def test_empty_list(self) -> None:
        """Empty list returns empty list."""
        assert get_tactics_for_techniques([]) == []

    def test_unknown_techniques(self) -> None:
        """Unknown techniques don't contribute tactics."""
        tactics = get_tactics_for_techniques(["T9999", "T1059"])
        assert tactics == ["execution"]


class TestSubTechniqueFallback:
    """Tests for sub-technique fallback to parent technique."""

    def setup_method(self) -> None:
        """Set up cache with parent techniques only."""
        clear_technique_tactics_cache()
        set_technique_tactics_cache({
            "T1059": ["execution"],
            "T1078": ["defense-evasion", "initial-access", "persistence", "privilege-escalation"],
        })

    def teardown_method(self) -> None:
        """Clear cache after each test."""
        clear_technique_tactics_cache()

    def test_subtechnique_falls_back_to_parent(self) -> None:
        """Sub-technique not in cache falls back to parent technique."""
        # T1059.999 is not in cache, but T1059 (parent) is
        tactics = get_tactics_for_technique("T1059.999")
        assert tactics == ["execution"]

    def test_subtechnique_parent_fallback_returns_copy(self) -> None:
        """Sub-technique fallback returns a copy, not reference."""
        tactics = get_tactics_for_technique("T1059.001")
        tactics.append("lateral-movement")
        
        # Original should be unaffected
        assert get_tactics_for_technique("T1059") == ["execution"]

    def test_subtechnique_unknown_parent(self) -> None:
        """Sub-technique with unknown parent returns empty list."""
        # T9999.001 - neither sub nor parent in cache
        tactics = get_tactics_for_technique("T9999.001")
        assert tactics == []

    def test_subtechnique_multiple_parent_tactics(self) -> None:
        """Sub-technique inherits all parent tactics."""
        # T1078.001 falls back to T1078 which has 4 tactics
        tactics = get_tactics_for_technique("T1078.001")
        assert len(tactics) == 4
        assert "defense-evasion" in tactics
        assert "initial-access" in tactics
