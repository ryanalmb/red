"""Unit tests for Finding Aggregation (Story 8.9).

Tests for FindingAggregator, enums, and dataclasses that aggregate
findings from agents for Director input.
"""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.orchestration.aggregator import (
    AggregatedFinding,
    AggregationSummary,
    AggregatorConfig,
    FindingAggregator,
    FindingCategory,
    FindingSeverity,
    FINDING_TYPE_CATEGORIES,
)


# =============================================================================
# Task 9.1: FindingCategory Enum Tests
# =============================================================================


class TestFindingCategory:
    """Tests for FindingCategory enum completeness."""

    def test_has_recon_category(self) -> None:
        """Test RECON category exists."""
        assert FindingCategory.RECON.value == "recon"

    def test_has_exploit_category(self) -> None:
        """Test EXPLOIT category exists."""
        assert FindingCategory.EXPLOIT.value == "exploit"

    def test_has_postex_category(self) -> None:
        """Test POSTEX category exists."""
        assert FindingCategory.POSTEX.value == "postex"

    def test_has_other_category(self) -> None:
        """Test OTHER category exists for uncategorized findings."""
        assert FindingCategory.OTHER.value == "other"

    def test_category_count(self) -> None:
        """Test we have exactly 4 categories per AC 3."""
        assert len(FindingCategory) == 4


# =============================================================================
# Task 9.2: FindingSeverity Enum Tests
# =============================================================================


class TestFindingSeverity:
    """Tests for FindingSeverity enum ordering."""

    def test_severity_values(self) -> None:
        """Test severity values for priority ordering."""
        assert FindingSeverity.CRITICAL.value == 0
        assert FindingSeverity.HIGH.value == 1
        assert FindingSeverity.MEDIUM.value == 2
        assert FindingSeverity.LOW.value == 3
        assert FindingSeverity.INFO.value == 4

    def test_severity_count(self) -> None:
        """Test we have exactly 5 severity levels per AC 4."""
        assert len(FindingSeverity) == 5

    def test_severity_ordering_critical_highest(self) -> None:
        """Test CRITICAL has highest priority (lowest value)."""
        assert FindingSeverity.CRITICAL < FindingSeverity.HIGH
        assert FindingSeverity.CRITICAL < FindingSeverity.MEDIUM
        assert FindingSeverity.CRITICAL < FindingSeverity.LOW
        assert FindingSeverity.CRITICAL < FindingSeverity.INFO

    def test_severity_ordering_info_lowest(self) -> None:
        """Test INFO has lowest priority (highest value)."""
        assert FindingSeverity.INFO > FindingSeverity.LOW
        assert FindingSeverity.INFO > FindingSeverity.MEDIUM
        assert FindingSeverity.INFO > FindingSeverity.HIGH
        assert FindingSeverity.INFO > FindingSeverity.CRITICAL

    def test_severity_comparison_operators(self) -> None:
        """Test all comparison operators work."""
        assert FindingSeverity.HIGH > FindingSeverity.CRITICAL
        assert FindingSeverity.CRITICAL < FindingSeverity.HIGH
        assert FindingSeverity.MEDIUM >= FindingSeverity.MEDIUM
        assert FindingSeverity.MEDIUM <= FindingSeverity.MEDIUM


# =============================================================================
# Task 9.3: AggregatedFinding Dataclass Tests
# =============================================================================


class TestAggregatedFinding:
    """Tests for AggregatedFinding dataclass."""

    def test_create_finding(self) -> None:
        """Test creating an aggregated finding."""
        finding = AggregatedFinding(
            target="10.0.0.5",
            finding_type="sqli",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.EXPLOIT,
            timestamp=1234567890.0,
            agent_id="exploit-agent-1",
        )
        assert finding.target == "10.0.0.5"
        assert finding.finding_type == "sqli"
        assert finding.severity == FindingSeverity.CRITICAL
        assert finding.category == FindingCategory.EXPLOIT
        assert finding.timestamp == 1234567890.0
        assert finding.agent_id == "exploit-agent-1"

    def test_finding_with_metadata(self) -> None:
        """Test finding with optional metadata."""
        metadata = {"cve_id": "CVE-2024-1234", "technique": "T1190"}
        finding = AggregatedFinding(
            target="10.0.0.5",
            finding_type="cve",
            severity=FindingSeverity.HIGH,
            category=FindingCategory.EXPLOIT,
            timestamp=1234567890.0,
            agent_id="exploit-agent-1",
            metadata=metadata,
        )
        assert finding.metadata == metadata
        assert finding.metadata["cve_id"] == "CVE-2024-1234"

    def test_finding_default_metadata(self) -> None:
        """Test finding has empty dict as default metadata."""
        finding = AggregatedFinding(
            target="10.0.0.5",
            finding_type="port_scan",
            severity=FindingSeverity.INFO,
            category=FindingCategory.RECON,
            timestamp=1234567890.0,
            agent_id="recon-agent-1",
        )
        assert finding.metadata == {}

    def test_dedup_key_property(self) -> None:
        """Test dedup_key combines target and type."""
        finding = AggregatedFinding(
            target="10.0.0.5:8080",
            finding_type="sqli",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.EXPLOIT,
            timestamp=1234567890.0,
            agent_id="agent-1",
        )
        assert finding.dedup_key == "10.0.0.5:8080:sqli"

    def test_dedup_key_same_for_duplicates(self) -> None:
        """Test same target+type produces same dedup_key."""
        finding1 = AggregatedFinding(
            target="10.0.0.5",
            finding_type="xss",
            severity=FindingSeverity.HIGH,
            category=FindingCategory.EXPLOIT,
            timestamp=1000.0,
            agent_id="agent-1",
        )
        finding2 = AggregatedFinding(
            target="10.0.0.5",
            finding_type="xss",
            severity=FindingSeverity.MEDIUM,
            category=FindingCategory.EXPLOIT,
            timestamp=2000.0,
            agent_id="agent-2",
        )
        assert finding1.dedup_key == finding2.dedup_key


# =============================================================================
# Task 9.4: AggregationSummary Dataclass Tests
# =============================================================================


class TestAggregationSummary:
    """Tests for AggregationSummary dataclass."""

    def test_create_summary(self) -> None:
        """Test creating an aggregation summary."""
        summary = AggregationSummary(
            total_count=10,
            raw_count=15,
            dropped_count=0,
            by_severity={FindingSeverity.CRITICAL: 2, FindingSeverity.HIGH: 8},
            by_category={FindingCategory.EXPLOIT: 7, FindingCategory.RECON: 3},
            window_start=1000.0,
            window_end=2000.0,
            findings=[],
        )
        assert summary.total_count == 10
        assert summary.raw_count == 15
        assert summary.dropped_count == 0
        assert summary.window_start == 1000.0
        assert summary.window_end == 2000.0

    def test_summary_by_severity_counts(self) -> None:
        """Test severity counts in summary."""
        summary = AggregationSummary(
            total_count=5,
            raw_count=5,
            dropped_count=0,
            by_severity={
                FindingSeverity.CRITICAL: 1,
                FindingSeverity.HIGH: 2,
                FindingSeverity.MEDIUM: 1,
                FindingSeverity.LOW: 1,
                FindingSeverity.INFO: 0,
            },
            by_category={},
            window_start=0.0,
            window_end=0.0,
            findings=[],
        )
        assert summary.by_severity[FindingSeverity.CRITICAL] == 1
        assert summary.by_severity[FindingSeverity.HIGH] == 2

    def test_summary_with_dropped_count(self) -> None:
        """Test summary tracks dropped findings."""
        summary = AggregationSummary(
            total_count=100,
            raw_count=150,
            dropped_count=20,
            by_severity={},
            by_category={},
            window_start=0.0,
            window_end=0.0,
            findings=[],
        )
        assert summary.dropped_count == 20


# =============================================================================
# Task 9.5: AggregatorConfig Dataclass Tests
# =============================================================================


class TestAggregatorConfig:
    """Tests for AggregatorConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = AggregatorConfig()
        assert config.max_findings_per_cycle == 100
        assert config.dedup_enabled is True
        assert config.include_info_severity is True  # Default is True for backward compat

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = AggregatorConfig(
            max_findings_per_cycle=50,
            dedup_enabled=False,
            include_info_severity=False,
        )
        assert config.max_findings_per_cycle == 50
        assert config.dedup_enabled is False
        assert config.include_info_severity is False


# =============================================================================
# Task 9.5: Deduplication Tests (AC 2)
# =============================================================================


class TestFindingDeduplication:
    """Tests for deduplication by target + type."""

    def test_add_finding_returns_true_for_new(self) -> None:
        """Test add_finding returns True for new finding."""
        aggregator = FindingAggregator()
        finding = AggregatedFinding(
            target="10.0.0.5",
            finding_type="sqli",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.EXPLOIT,
            timestamp=1000.0,
            agent_id="agent-1",
        )
        result = aggregator.add_finding(finding)
        assert result is True

    def test_add_finding_returns_false_for_duplicate(self) -> None:
        """Test add_finding returns False for duplicate (same target+type)."""
        aggregator = FindingAggregator()
        finding1 = AggregatedFinding(
            target="10.0.0.5",
            finding_type="sqli",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.EXPLOIT,
            timestamp=1000.0,
            agent_id="agent-1",
        )
        finding2 = AggregatedFinding(
            target="10.0.0.5",
            finding_type="sqli",
            severity=FindingSeverity.HIGH,
            category=FindingCategory.EXPLOIT,
            timestamp=2000.0,
            agent_id="agent-2",
        )
        aggregator.add_finding(finding1)
        result = aggregator.add_finding(finding2)
        assert result is False

    def test_duplicate_preserves_earliest_timestamp(self) -> None:
        """Test duplicate findings preserve earliest timestamp per AC 2."""
        aggregator = FindingAggregator()
        finding1 = AggregatedFinding(
            target="10.0.0.5",
            finding_type="sqli",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.EXPLOIT,
            timestamp=1000.0,
            agent_id="agent-1",
        )
        finding2 = AggregatedFinding(
            target="10.0.0.5",
            finding_type="sqli",
            severity=FindingSeverity.HIGH,
            category=FindingCategory.EXPLOIT,
            timestamp=500.0,  # Earlier timestamp
            agent_id="agent-2",
        )
        aggregator.add_finding(finding1)
        aggregator.add_finding(finding2)
        
        summary = aggregator.get_summary()
        assert len(summary.findings) == 1
        assert summary.findings[0].timestamp == 500.0  # Earlier preserved

    def test_dedup_disabled_allows_duplicates(self) -> None:
        """Test dedup can be disabled via config."""
        config = AggregatorConfig(dedup_enabled=False)
        aggregator = FindingAggregator(config=config)
        
        finding1 = AggregatedFinding(
            target="10.0.0.5",
            finding_type="sqli",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.EXPLOIT,
            timestamp=1000.0,
            agent_id="agent-1",
        )
        finding2 = AggregatedFinding(
            target="10.0.0.5",
            finding_type="sqli",
            severity=FindingSeverity.HIGH,
            category=FindingCategory.EXPLOIT,
            timestamp=2000.0,
            agent_id="agent-2",
        )
        
        result1 = aggregator.add_finding(finding1)
        result2 = aggregator.add_finding(finding2)
        
        assert result1 is True
        assert result2 is True

    def test_different_targets_not_deduplicated(self) -> None:
        """Test different targets are not deduplicated."""
        aggregator = FindingAggregator()
        finding1 = AggregatedFinding(
            target="10.0.0.5",
            finding_type="sqli",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.EXPLOIT,
            timestamp=1000.0,
            agent_id="agent-1",
        )
        finding2 = AggregatedFinding(
            target="10.0.0.6",
            finding_type="sqli",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.EXPLOIT,
            timestamp=1000.0,
            agent_id="agent-1",
        )
        aggregator.add_finding(finding1)
        result = aggregator.add_finding(finding2)
        assert result is True

    def test_different_types_not_deduplicated(self) -> None:
        """Test different types are not deduplicated."""
        aggregator = FindingAggregator()
        finding1 = AggregatedFinding(
            target="10.0.0.5",
            finding_type="sqli",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.EXPLOIT,
            timestamp=1000.0,
            agent_id="agent-1",
        )
        finding2 = AggregatedFinding(
            target="10.0.0.5",
            finding_type="xss",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.EXPLOIT,
            timestamp=1000.0,
            agent_id="agent-1",
        )
        aggregator.add_finding(finding1)
        result = aggregator.add_finding(finding2)
        assert result is True


# =============================================================================
# Task 9.6: Category Assignment Tests (AC 3)
# =============================================================================


class TestCategoryAssignment:
    """Tests for category assignment based on finding type."""

    def test_recon_types_mapped_correctly(self) -> None:
        """Test RECON finding types are mapped correctly."""
        recon_types = [
            "port_scan", "service_detection", "subdomain",
            "web_tech", "dns_record", "banner_grab", "ssl_cert", "waf_detect",
        ]
        for finding_type in recon_types:
            assert FINDING_TYPE_CATEGORIES.get(finding_type) == FindingCategory.RECON, \
                f"{finding_type} should be RECON"

    def test_exploit_types_mapped_correctly(self) -> None:
        """Test EXPLOIT finding types are mapped correctly."""
        exploit_types = [
            "vulnerability", "cve", "sqli", "xss", "rce",
            "lfi", "ssrf", "auth_bypass", "idor",
        ]
        for finding_type in exploit_types:
            assert FINDING_TYPE_CATEGORIES.get(finding_type) == FindingCategory.EXPLOIT, \
                f"{finding_type} should be EXPLOIT"

    def test_postex_types_mapped_correctly(self) -> None:
        """Test POSTEX finding types are mapped correctly."""
        postex_types = [
            "credential", "shell", "pivot", "persistence",
            "exfil", "privesc", "lateral_move",
        ]
        for finding_type in postex_types:
            assert FINDING_TYPE_CATEGORIES.get(finding_type) == FindingCategory.POSTEX, \
                f"{finding_type} should be POSTEX"

    def test_unknown_type_returns_other(self) -> None:
        """Test unknown types are categorized as OTHER."""
        aggregator = FindingAggregator()
        category = aggregator._categorize("unknown_finding_type")
        assert category == FindingCategory.OTHER

    def test_get_by_category(self) -> None:
        """Test retrieving findings by category."""
        aggregator = FindingAggregator()
        
        # Add one of each category
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5",
            finding_type="port_scan",
            severity=FindingSeverity.INFO,
            category=FindingCategory.RECON,
            timestamp=1000.0,
            agent_id="agent-1",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5",
            finding_type="sqli",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.EXPLOIT,
            timestamp=1000.0,
            agent_id="agent-1",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5",
            finding_type="credential",
            severity=FindingSeverity.HIGH,
            category=FindingCategory.POSTEX,
            timestamp=1000.0,
            agent_id="agent-1",
        ))
        
        recon_findings = aggregator.get_by_category(FindingCategory.RECON)
        exploit_findings = aggregator.get_by_category(FindingCategory.EXPLOIT)
        postex_findings = aggregator.get_by_category(FindingCategory.POSTEX)
        
        assert len(recon_findings) == 1
        assert len(exploit_findings) == 1
        assert len(postex_findings) == 1


# =============================================================================
# Task 9.7: Summary Statistics Tests (AC 4)
# =============================================================================


class TestSummaryStatistics:
    """Tests for summary statistics calculation."""

    def test_total_count(self) -> None:
        """Test total finding count in summary."""
        aggregator = FindingAggregator()
        for i in range(5):
            aggregator.add_finding(AggregatedFinding(
                target=f"10.0.0.{i}",
                finding_type="port_scan",
                severity=FindingSeverity.INFO,
                category=FindingCategory.RECON,
                timestamp=1000.0 + i,
                agent_id="agent-1",
            ))
        
        summary = aggregator.get_summary()
        assert summary.total_count == 5

    def test_raw_count_vs_total_count(self) -> None:
        """Test raw_count includes duplicates, total_count does not."""
        aggregator = FindingAggregator()
        
        # Add 3 findings, 1 is duplicate
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5",
            finding_type="sqli",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.EXPLOIT,
            timestamp=1000.0,
            agent_id="agent-1",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5",
            finding_type="sqli",  # Duplicate
            severity=FindingSeverity.HIGH,
            category=FindingCategory.EXPLOIT,
            timestamp=2000.0,
            agent_id="agent-2",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.6",
            finding_type="xss",
            severity=FindingSeverity.MEDIUM,
            category=FindingCategory.EXPLOIT,
            timestamp=1000.0,
            agent_id="agent-1",
        ))
        
        summary = aggregator.get_summary()
        assert summary.raw_count == 3
        assert summary.total_count == 2

    def test_severity_counts(self) -> None:
        """Test counts per severity level."""
        aggregator = FindingAggregator()
        
        # Add findings of different severities
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.1", finding_type="sqli",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.EXPLOIT, timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.2", finding_type="xss",
            severity=FindingSeverity.HIGH,
            category=FindingCategory.EXPLOIT, timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.3", finding_type="xss",
            severity=FindingSeverity.HIGH,
            category=FindingCategory.EXPLOIT, timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.4", finding_type="port_scan",
            severity=FindingSeverity.INFO,
            category=FindingCategory.RECON, timestamp=1000.0, agent_id="a",
        ))
        
        summary = aggregator.get_summary()
        assert summary.by_severity[FindingSeverity.CRITICAL] == 1
        assert summary.by_severity[FindingSeverity.HIGH] == 2
        assert summary.by_severity.get(FindingSeverity.MEDIUM, 0) == 0
        assert summary.by_severity.get(FindingSeverity.LOW, 0) == 0
        assert summary.by_severity[FindingSeverity.INFO] == 1

    def test_category_counts(self) -> None:
        """Test counts per category."""
        aggregator = FindingAggregator()
        
        # Add findings of different categories
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.1", finding_type="port_scan",
            severity=FindingSeverity.INFO, category=FindingCategory.RECON,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.2", finding_type="sqli",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.3", finding_type="xss",
            severity=FindingSeverity.HIGH, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.4", finding_type="credential",
            severity=FindingSeverity.HIGH, category=FindingCategory.POSTEX,
            timestamp=1000.0, agent_id="a",
        ))
        
        summary = aggregator.get_summary()
        assert summary.by_category[FindingCategory.RECON] == 1
        assert summary.by_category[FindingCategory.EXPLOIT] == 2
        assert summary.by_category[FindingCategory.POSTEX] == 1

    def test_window_timestamps(self) -> None:
        """Test window start/end timestamps in summary."""
        aggregator = FindingAggregator()
        
        # Window start is set at aggregator creation time
        before_time = time.time()
        
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.1", finding_type="port_scan",
            severity=FindingSeverity.INFO, category=FindingCategory.RECON,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.2", finding_type="sqli",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=2000.0, agent_id="a",
        ))
        
        summary = aggregator.get_summary()
        # Window start is creation time, window end is max finding timestamp
        assert summary.window_start <= before_time + 1  # Allow 1s tolerance
        assert summary.window_end >= 2000.0  # Should include latest finding timestamp


# =============================================================================
# Task 9.8: Priority Ordering Tests (AC 5)
# =============================================================================


class TestPriorityOrdering:
    """Tests for priority ordering (severity then recency)."""

    def test_prioritize_by_severity(self) -> None:
        """Test findings are sorted by severity (critical first)."""
        aggregator = FindingAggregator()
        
        # Add in wrong order
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.1", finding_type="info1",
            severity=FindingSeverity.INFO, category=FindingCategory.RECON,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.2", finding_type="crit1",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.3", finding_type="high1",
            severity=FindingSeverity.HIGH, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        
        summary = aggregator.get_summary()
        findings = summary.findings
        
        assert findings[0].severity == FindingSeverity.CRITICAL
        assert findings[1].severity == FindingSeverity.HIGH
        assert findings[2].severity == FindingSeverity.INFO

    def test_prioritize_by_recency_within_severity(self) -> None:
        """Test within same severity, newer findings come first."""
        aggregator = FindingAggregator()
        
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.1", finding_type="high1",
            severity=FindingSeverity.HIGH, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.2", finding_type="high2",
            severity=FindingSeverity.HIGH, category=FindingCategory.EXPLOIT,
            timestamp=2000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.3", finding_type="high3",
            severity=FindingSeverity.HIGH, category=FindingCategory.EXPLOIT,
            timestamp=1500.0, agent_id="a",
        ))
        
        summary = aggregator.get_summary()
        findings = summary.findings
        
        # All HIGH, sorted by timestamp descending (newest first)
        assert findings[0].timestamp == 2000.0
        assert findings[1].timestamp == 1500.0
        assert findings[2].timestamp == 1000.0


# =============================================================================
# Task 9.9: Max Findings Limit Tests (AC 5)
# =============================================================================


class TestMaxFindingsLimit:
    """Tests for max_findings_per_cycle limit enforcement."""

    def test_limit_enforced(self) -> None:
        """Test findings are limited to max_findings_per_cycle."""
        config = AggregatorConfig(max_findings_per_cycle=5)
        aggregator = FindingAggregator(config=config)
        
        # Add 10 findings
        for i in range(10):
            aggregator.add_finding(AggregatedFinding(
                target=f"10.0.0.{i}", finding_type=f"type{i}",
                severity=FindingSeverity.MEDIUM, category=FindingCategory.EXPLOIT,
                timestamp=1000.0 + i, agent_id="a",
            ))
        
        summary = aggregator.get_summary()
        assert len(summary.findings) == 5
        assert summary.dropped_count == 5

    def test_high_severity_prioritized_when_limited(self) -> None:
        """Test high severity findings are kept when limit enforced."""
        config = AggregatorConfig(max_findings_per_cycle=2)
        aggregator = FindingAggregator(config=config)
        
        # Add low severity first, then critical
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.1", finding_type="low1",
            severity=FindingSeverity.LOW, category=FindingCategory.RECON,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.2", finding_type="low2",
            severity=FindingSeverity.LOW, category=FindingCategory.RECON,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.3", finding_type="crit1",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        
        summary = aggregator.get_summary()
        
        # Critical should be kept, one low dropped
        assert len(summary.findings) == 2
        assert summary.findings[0].severity == FindingSeverity.CRITICAL

    def test_dropped_count_logged(self) -> None:
        """Test dropped count is tracked in summary."""
        config = AggregatorConfig(max_findings_per_cycle=3)
        aggregator = FindingAggregator(config=config)
        
        for i in range(7):
            aggregator.add_finding(AggregatedFinding(
                target=f"10.0.0.{i}", finding_type=f"type{i}",
                severity=FindingSeverity.MEDIUM, category=FindingCategory.EXPLOIT,
                timestamp=1000.0 + i, agent_id="a",
            ))
        
        summary = aggregator.get_summary()
        assert summary.dropped_count == 4


# =============================================================================
# Task 9.10: Director Prompt Formatting Tests (AC 6)
# =============================================================================


class TestDirectorPromptFormatting:
    """Tests for Director prompt formatting."""

    def test_format_includes_summary_header(self) -> None:
        """Test formatted output includes summary header."""
        aggregator = FindingAggregator()
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="sqli",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        
        output = aggregator.format_for_director()
        assert "Findings Summary" in output

    def test_format_includes_statistics(self) -> None:
        """Test formatted output includes statistics."""
        aggregator = FindingAggregator()
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="sqli",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.6", finding_type="xss",
            severity=FindingSeverity.HIGH, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        
        output = aggregator.format_for_director()
        assert "Total:" in output or "total" in output.lower()
        assert "Critical:" in output or "critical" in output.lower()

    def test_format_includes_critical_findings_section(self) -> None:
        """Test critical findings have dedicated section."""
        aggregator = FindingAggregator()
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="sqli",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
            metadata={"cve_id": "CVE-2024-1234"},
        ))
        
        output = aggregator.format_for_director()
        assert "Critical" in output
        assert "10.0.0.5" in output

    def test_format_includes_category_context(self) -> None:
        """Test output includes category context."""
        aggregator = FindingAggregator()
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="port_scan",
            severity=FindingSeverity.INFO, category=FindingCategory.RECON,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="sqli",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        
        output = aggregator.format_for_director()
        # Should mention categories
        assert "Recon" in output or "recon" in output.lower() or "RECON" in output
        assert "Exploit" in output or "exploit" in output.lower() or "EXPLOIT" in output

    def test_format_empty_aggregator(self) -> None:
        """Test formatting when no findings."""
        aggregator = FindingAggregator()
        output = aggregator.format_for_director()
        assert "0" in output or "No findings" in output or "no findings" in output.lower()


# =============================================================================
# Window Reset and Lifecycle Tests
# =============================================================================


class TestWindowReset:
    """Tests for window reset functionality."""

    def test_reset_window_clears_findings(self) -> None:
        """Test reset_window clears all findings."""
        aggregator = FindingAggregator()
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="sqli",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        
        assert aggregator.get_summary().total_count == 1
        
        aggregator.reset_window()
        
        assert aggregator.get_summary().total_count == 0

    def test_reset_window_updates_timestamps(self) -> None:
        """Test reset_window updates window start timestamp."""
        aggregator = FindingAggregator()
        
        old_summary = aggregator.get_summary()
        old_start = old_summary.window_start
        
        time.sleep(0.01)  # Small delay
        aggregator.reset_window()
        
        new_summary = aggregator.get_summary()
        assert new_summary.window_start >= old_start


# =============================================================================
# Get Findings Since Tests (Task 8)
# =============================================================================


class TestGetFindingsSince:
    """Tests for get_findings_since method."""

    def test_get_findings_since_all(self) -> None:
        """Test get_findings_since returns all findings when no timestamp."""
        aggregator = FindingAggregator()
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="sqli",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.6", finding_type="xss",
            severity=FindingSeverity.HIGH, category=FindingCategory.EXPLOIT,
            timestamp=2000.0, agent_id="a",
        ))
        
        summary = aggregator.get_findings_since()
        assert summary.total_count == 2

    def test_get_findings_since_filtered(self) -> None:
        """Test get_findings_since filters by timestamp."""
        aggregator = FindingAggregator()
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="sqli",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.6", finding_type="xss",
            severity=FindingSeverity.HIGH, category=FindingCategory.EXPLOIT,
            timestamp=2000.0, agent_id="a",
        ))
        
        summary = aggregator.get_findings_since(timestamp=1500.0)
        assert summary.total_count == 1
        assert summary.findings[0].target == "10.0.0.6"

    def test_get_findings_since_clears_window(self) -> None:
        """Test get_findings_since clears window after retrieval."""
        aggregator = FindingAggregator()
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="sqli",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        
        # First call gets findings
        summary1 = aggregator.get_findings_since()
        assert summary1.total_count == 1
        
        # Second call should be empty (window cleared)
        summary2 = aggregator.get_findings_since()
        assert summary2.total_count == 0


# =============================================================================
# Async Lifecycle Tests
# =============================================================================


class TestAsyncLifecycle:
    """Tests for async lifecycle methods."""

    @pytest.mark.asyncio
    async def test_start_sets_engagement_id(self) -> None:
        """Test start sets engagement_id."""
        aggregator = FindingAggregator()
        await aggregator.start("test-engagement-123")
        assert aggregator._engagement_id == "test-engagement-123"
        assert aggregator._running is True

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self) -> None:
        """Test stop sets running to False."""
        aggregator = FindingAggregator()
        await aggregator.start("test-engagement")
        await aggregator.stop()
        assert aggregator._running is False

    @pytest.mark.asyncio
    async def test_start_resets_window_timestamps(self) -> None:
        """Test start resets window timestamps."""
        aggregator = FindingAggregator()
        before = time.time()
        await aggregator.start("test-engagement")
        after = time.time()
        assert aggregator._window_start >= before
        assert aggregator._window_start <= after

    @pytest.mark.asyncio
    async def test_stop_clears_subscriptions(self) -> None:
        """Test stop clears subscriptions list."""
        aggregator = FindingAggregator()
        await aggregator.start("test-engagement")
        # Manually add a mock subscription
        mock_sub = AsyncMock()
        aggregator._subscriptions.append(mock_sub)
        
        await aggregator.stop()
        assert len(aggregator._subscriptions) == 0
        mock_sub.unsubscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_handles_subscription_error(self) -> None:
        """Test stop handles subscription unsubscribe errors gracefully."""
        aggregator = FindingAggregator()
        await aggregator.start("test-engagement")
        
        # Add mock subscription that raises error
        mock_sub = AsyncMock()
        mock_sub.unsubscribe.side_effect = Exception("Connection lost")
        aggregator._subscriptions.append(mock_sub)
        
        # Should not raise, just log warning
        await aggregator.stop()
        assert len(aggregator._subscriptions) == 0


# =============================================================================
# EventBus Integration Tests (Unit Level)
# =============================================================================


class TestEventBusHandling:
    """Tests for EventBus event handling."""

    @pytest.mark.asyncio
    async def test_handle_finding_event_parses_json(self) -> None:
        """Test _handle_finding_event parses JSON correctly."""
        aggregator = FindingAggregator()
        aggregator._running = True
        
        message = json.dumps({
            "target": "10.0.0.5",
            "type": "sqli",
            "severity": "CRITICAL",
            "agent_id": "agent-1",
            "timestamp": 1000.0,
            "cve_id": "CVE-2024-1234",
        })
        
        await aggregator._handle_finding_event("findings:abc123:sqli", message)
        
        summary = aggregator.get_summary()
        assert summary.total_count == 1
        assert summary.findings[0].target == "10.0.0.5"
        assert summary.findings[0].metadata.get("cve_id") == "CVE-2024-1234"

    @pytest.mark.asyncio
    async def test_handle_finding_event_uses_finding_type_fallback(self) -> None:
        """Test _handle_finding_event uses finding_type key as fallback."""
        aggregator = FindingAggregator()
        aggregator._running = True
        
        message = json.dumps({
            "target": "10.0.0.5",
            "finding_type": "xss",  # Uses finding_type instead of type
            "severity": "HIGH",
            "agent_id": "agent-1",
        })
        
        await aggregator._handle_finding_event("findings:abc123:xss", message)
        
        summary = aggregator.get_summary()
        assert summary.total_count == 1
        assert summary.findings[0].finding_type == "xss"

    @pytest.mark.asyncio
    async def test_handle_finding_event_skips_when_not_running(self) -> None:
        """Test _handle_finding_event skips when not running."""
        aggregator = FindingAggregator()
        aggregator._running = False
        
        message = json.dumps({
            "target": "10.0.0.5",
            "type": "sqli",
            "severity": "CRITICAL",
            "agent_id": "agent-1",
        })
        
        await aggregator._handle_finding_event("findings:abc123:sqli", message)
        
        summary = aggregator.get_summary()
        assert summary.total_count == 0

    @pytest.mark.asyncio
    async def test_handle_finding_event_handles_invalid_json(self) -> None:
        """Test _handle_finding_event handles invalid JSON gracefully."""
        aggregator = FindingAggregator()
        aggregator._running = True
        
        # Invalid JSON
        await aggregator._handle_finding_event("findings:abc123:sqli", "not valid json")
        
        summary = aggregator.get_summary()
        assert summary.total_count == 0

    @pytest.mark.asyncio
    async def test_handle_finding_event_handles_missing_fields(self) -> None:
        """Test _handle_finding_event handles missing required fields."""
        aggregator = FindingAggregator()
        aggregator._running = True
        
        # Missing target
        message = json.dumps({
            "type": "sqli",
            "severity": "CRITICAL",
        })
        
        await aggregator._handle_finding_event("findings:abc123:sqli", message)
        
        summary = aggregator.get_summary()
        assert summary.total_count == 0

    @pytest.mark.asyncio
    async def test_handle_finding_event_defaults_severity_to_info(self) -> None:
        """Test _handle_finding_event defaults unknown severity to INFO."""
        aggregator = FindingAggregator()
        aggregator._running = True
        
        message = json.dumps({
            "target": "10.0.0.5",
            "type": "sqli",
            "severity": "UNKNOWN_SEVERITY",
            "agent_id": "agent-1",
        })
        
        await aggregator._handle_finding_event("findings:abc123:sqli", message)
        
        summary = aggregator.get_summary()
        assert summary.total_count == 1
        assert summary.findings[0].severity == FindingSeverity.INFO

    @pytest.mark.asyncio
    async def test_handle_finding_event_auto_categorizes(self) -> None:
        """Test _handle_finding_event auto-categorizes based on type."""
        aggregator = FindingAggregator()
        aggregator._running = True
        
        # Port scan should be categorized as RECON
        message = json.dumps({
            "target": "10.0.0.5",
            "type": "port_scan",
            "severity": "INFO",
            "agent_id": "agent-1",
        })
        
        await aggregator._handle_finding_event("findings:abc123:port_scan", message)
        
        summary = aggregator.get_summary()
        assert summary.total_count == 1
        assert summary.findings[0].category == FindingCategory.RECON

    @pytest.mark.asyncio
    async def test_setup_subscriptions_without_event_bus(self) -> None:
        """Test _setup_subscriptions does nothing without EventBus."""
        aggregator = FindingAggregator(event_bus=None)
        aggregator._engagement_id = "test-engagement"
        
        # Should not raise
        await aggregator._setup_subscriptions()
        assert len(aggregator._subscriptions) == 0

    @pytest.mark.asyncio
    async def test_setup_subscriptions_without_engagement_id(self) -> None:
        """Test _setup_subscriptions does nothing without engagement_id."""
        mock_event_bus = MagicMock()
        aggregator = FindingAggregator(event_bus=mock_event_bus)
        aggregator._engagement_id = None
        
        # Should not raise
        await aggregator._setup_subscriptions()
        assert len(aggregator._subscriptions) == 0


# =============================================================================
# Severity Comparison Edge Cases
# =============================================================================


class TestSeverityEdgeCases:
    """Tests for severity comparison edge cases."""

    def test_severity_lt_with_non_severity(self) -> None:
        """Test __lt__ returns NotImplemented for non-FindingSeverity."""
        assert FindingSeverity.CRITICAL.__lt__("not_a_severity") == NotImplemented

    def test_severity_le_with_non_severity(self) -> None:
        """Test __le__ returns NotImplemented for non-FindingSeverity."""
        assert FindingSeverity.CRITICAL.__le__("not_a_severity") == NotImplemented

    def test_severity_gt_with_non_severity(self) -> None:
        """Test __gt__ returns NotImplemented for non-FindingSeverity."""
        assert FindingSeverity.CRITICAL.__gt__("not_a_severity") == NotImplemented

    def test_severity_ge_with_non_severity(self) -> None:
        """Test __ge__ returns NotImplemented for non-FindingSeverity."""
        assert FindingSeverity.CRITICAL.__ge__("not_a_severity") == NotImplemented


# =============================================================================
# Additional Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for additional edge cases."""

    def test_get_by_category_empty(self) -> None:
        """Test get_by_category returns empty list when no matches."""
        aggregator = FindingAggregator()
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="sqli",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        
        postex_findings = aggregator.get_by_category(FindingCategory.POSTEX)
        assert postex_findings == []

    def test_format_for_director_with_high_findings_only(self) -> None:
        """Test format_for_director with only HIGH findings."""
        aggregator = FindingAggregator()
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="xss",
            severity=FindingSeverity.HIGH, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        
        output = aggregator.format_for_director()
        assert "High" in output or "HIGH" in output
        assert "10.0.0.5" in output

    def test_get_findings_since_with_limit(self) -> None:
        """Test get_findings_since enforces limit."""
        config = AggregatorConfig(max_findings_per_cycle=2)
        aggregator = FindingAggregator(config=config)
        
        for i in range(5):
            aggregator.add_finding(AggregatedFinding(
                target=f"10.0.0.{i}", finding_type=f"type{i}",
                severity=FindingSeverity.MEDIUM, category=FindingCategory.EXPLOIT,
                timestamp=1000.0 + i, agent_id="a",
            ))
        
        summary = aggregator.get_findings_since()
        assert len(summary.findings) == 2
        assert summary.dropped_count == 3

    def test_format_for_director_postex_context(self) -> None:
        """Test format_for_director includes postex context."""
        aggregator = FindingAggregator()
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="credential",
            severity=FindingSeverity.HIGH, category=FindingCategory.POSTEX,
            timestamp=1000.0, agent_id="a",
        ))
        
        output = aggregator.format_for_director()
        assert "post-exploitation" in output.lower() or "Postex" in output

    def test_get_by_category_with_dedup_disabled(self) -> None:
        """Test get_by_category works with dedup disabled."""
        config = AggregatorConfig(dedup_enabled=False)
        aggregator = FindingAggregator(config=config)
        
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="sqli",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.6", finding_type="port_scan",
            severity=FindingSeverity.INFO, category=FindingCategory.RECON,
            timestamp=1000.0, agent_id="b",
        ))
        
        exploit_findings = aggregator.get_by_category(FindingCategory.EXPLOIT)
        assert len(exploit_findings) == 1
        assert exploit_findings[0].target == "10.0.0.5"


# =============================================================================
# Tests for include_info_severity Config (Code Review Fix)
# =============================================================================


class TestIncludeInfoSeverityConfig:
    """Tests for include_info_severity configuration option."""

    def test_info_severity_filtered_when_disabled(self) -> None:
        """Test INFO severity findings are filtered when include_info_severity=False."""
        config = AggregatorConfig(include_info_severity=False)
        aggregator = FindingAggregator(config=config)
        
        # Add INFO severity finding
        result = aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="port_scan",
            severity=FindingSeverity.INFO, category=FindingCategory.RECON,
            timestamp=1000.0, agent_id="a",
        ))
        
        assert result is False  # Should be filtered
        summary = aggregator.get_summary()
        assert summary.total_count == 0
        assert summary.raw_count == 1  # Raw count still incremented

    def test_info_severity_included_when_enabled(self) -> None:
        """Test INFO severity findings are included when include_info_severity=True."""
        config = AggregatorConfig(include_info_severity=True)
        aggregator = FindingAggregator(config=config)
        
        result = aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="port_scan",
            severity=FindingSeverity.INFO, category=FindingCategory.RECON,
            timestamp=1000.0, agent_id="a",
        ))
        
        assert result is True
        summary = aggregator.get_summary()
        assert summary.total_count == 1

    def test_non_info_severity_always_included(self) -> None:
        """Test non-INFO severity findings are included regardless of config."""
        config = AggregatorConfig(include_info_severity=False)
        aggregator = FindingAggregator(config=config)
        
        # Add non-INFO severity findings
        for sev in [FindingSeverity.CRITICAL, FindingSeverity.HIGH, 
                    FindingSeverity.MEDIUM, FindingSeverity.LOW]:
            aggregator.add_finding(AggregatedFinding(
                target=f"10.0.0.{sev.value}", finding_type=f"type_{sev.name}",
                severity=sev, category=FindingCategory.EXPLOIT,
                timestamp=1000.0, agent_id="a",
            ))
        
        summary = aggregator.get_summary()
        assert summary.total_count == 4


# =============================================================================
# Tests for Improved Actionable Context (Code Review Fix)
# =============================================================================


class TestActionableContext:
    """Tests for actionable context in format_for_director."""

    def test_actionable_context_with_high_severity_only(self) -> None:
        """Test actionable context shows high severity when no critical."""
        aggregator = FindingAggregator()
        
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="xss",
            severity=FindingSeverity.HIGH, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        
        output = aggregator.format_for_director()
        assert "high severity" in output.lower() or "warrant attention" in output.lower()

    def test_actionable_context_with_medium_severity_only(self) -> None:
        """Test actionable context shows exploit count when only medium severity."""
        aggregator = FindingAggregator()
        
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="xss",
            severity=FindingSeverity.MEDIUM, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        
        output = aggregator.format_for_director()
        assert "exploit" in output.lower() or "investigation" in output.lower()

    def test_actionable_context_with_recon_only(self) -> None:
        """Test actionable context shows recon info when only recon findings."""
        config = AggregatorConfig(include_info_severity=False)
        aggregator = FindingAggregator(config=config)
        
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="subdomain",
            severity=FindingSeverity.LOW, category=FindingCategory.RECON,
            timestamp=1000.0, agent_id="a",
        ))
        
        output = aggregator.format_for_director()
        assert "recon" in output.lower() or "enumeration" in output.lower()

    def test_actionable_context_with_other_category(self) -> None:
        """Test actionable context shows general count for OTHER category."""
        config = AggregatorConfig(include_info_severity=False)
        aggregator = FindingAggregator(config=config)
        
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="unknown_type",
            severity=FindingSeverity.LOW, category=FindingCategory.OTHER,
            timestamp=1000.0, agent_id="a",
        ))
        
        output = aggregator.format_for_director()
        assert "collected" in output.lower() or "analysis" in output.lower()


# =============================================================================
# Tests for Corrected Dedup/Drop Statistics (Code Review Fix)
# =============================================================================


class TestDedupDropStatistics:
    """Tests for correct dedup and dropped count in format_for_director."""

    def test_format_shows_dropped_count(self) -> None:
        """Test format_for_director shows dropped count when findings exceed limit."""
        config = AggregatorConfig(max_findings_per_cycle=2)
        aggregator = FindingAggregator(config=config)
        
        for i in range(5):
            aggregator.add_finding(AggregatedFinding(
                target=f"10.0.0.{i}", finding_type=f"type{i}",
                severity=FindingSeverity.MEDIUM, category=FindingCategory.EXPLOIT,
                timestamp=1000.0, agent_id="a",
            ))
        
        output = aggregator.format_for_director()
        assert "dropped" in output.lower()
        assert "3" in output  # 5 - 2 = 3 dropped

    def test_format_correct_dedup_count_with_drops(self) -> None:
        """Test dedup count is calculated correctly when there are also drops."""
        config = AggregatorConfig(max_findings_per_cycle=2)
        aggregator = FindingAggregator(config=config)
        
        # 4 raw findings: 1 duplicate, so 3 unique, but limit is 2, so 1 dropped
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.1", finding_type="sqli",
            severity=FindingSeverity.HIGH, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.1", finding_type="sqli",  # Duplicate
            severity=FindingSeverity.MEDIUM, category=FindingCategory.EXPLOIT,
            timestamp=2000.0, agent_id="b",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.2", finding_type="xss",
            severity=FindingSeverity.HIGH, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.3", finding_type="rce",
            severity=FindingSeverity.LOW, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        
        output = aggregator.format_for_director()
        # 4 raw, 1 deduplicated, 1 dropped
        assert "4 raw" in output
        assert "1 deduplicated" in output
        assert "1 dropped" in output.lower()

    def test_format_no_dropped_when_under_limit(self) -> None:
        """Test format doesn't show dropped when findings under limit."""
        aggregator = FindingAggregator()
        
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="sqli",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        
        output = aggregator.format_for_director()
        assert "dropped" not in output.lower()
