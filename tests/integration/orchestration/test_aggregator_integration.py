"""Integration tests for Finding Aggregation (Story 8.9).

Tests for FindingAggregator integration with EventBus and
ReplanTriggerManager for end-to-end finding collection.
"""

from __future__ import annotations

import asyncio
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
)


# =============================================================================
# Task 10.1: End-to-end finding collection via EventBus
# =============================================================================


class TestEventBusIntegration:
    """Tests for EventBus integration."""

    @pytest.mark.asyncio
    async def test_setup_subscriptions_with_event_bus(self) -> None:
        """Test _setup_subscriptions creates subscription with EventBus."""
        mock_event_bus = MagicMock()
        mock_subscription = AsyncMock()
        mock_event_bus.subscribe = AsyncMock(return_value=mock_subscription)
        
        aggregator = FindingAggregator(event_bus=mock_event_bus)
        aggregator._engagement_id = "test-engagement-123"
        
        await aggregator._setup_subscriptions()
        
        # Verify subscribe was called with correct pattern
        mock_event_bus.subscribe.assert_called_once()
        call_args = mock_event_bus.subscribe.call_args
        assert "findings:test-engagement-123:" in call_args[0][0]
        assert len(aggregator._subscriptions) == 1

    @pytest.mark.asyncio
    async def test_setup_subscriptions_handles_error(self) -> None:
        """Test _setup_subscriptions handles subscription errors gracefully."""
        mock_event_bus = MagicMock()
        mock_event_bus.subscribe = AsyncMock(side_effect=Exception("Connection failed"))
        
        aggregator = FindingAggregator(event_bus=mock_event_bus)
        aggregator._engagement_id = "test-engagement-123"
        
        # Should not raise
        await aggregator._setup_subscriptions()
        
        # No subscription should be added
        assert len(aggregator._subscriptions) == 0

    @pytest.mark.asyncio
    async def test_start_with_event_bus_sets_up_subscriptions(self) -> None:
        """Test start() sets up EventBus subscriptions."""
        mock_event_bus = MagicMock()
        mock_subscription = AsyncMock()
        mock_event_bus.subscribe = AsyncMock(return_value=mock_subscription)
        
        aggregator = FindingAggregator(event_bus=mock_event_bus)
        await aggregator.start("test-engagement-456")
        
        assert aggregator._running is True
        assert aggregator._engagement_id == "test-engagement-456"
        mock_event_bus.subscribe.assert_called_once()


# =============================================================================
# Task 10.2: Aggregation with real finding events
# =============================================================================


class TestRealFindingEvents:
    """Tests for aggregation with real finding event formats."""

    @pytest.mark.asyncio
    async def test_process_multiple_finding_events(self) -> None:
        """Test processing multiple finding events."""
        aggregator = FindingAggregator()
        aggregator._running = True
        
        # Simulate multiple findings from different agents
        findings = [
            {"target": "10.0.0.1", "type": "port_scan", "severity": "INFO", "agent_id": "recon-1"},
            {"target": "10.0.0.1", "type": "sqli", "severity": "CRITICAL", "agent_id": "exploit-1"},
            {"target": "10.0.0.2", "type": "xss", "severity": "HIGH", "agent_id": "exploit-2"},
            {"target": "10.0.0.1", "type": "credential", "severity": "HIGH", "agent_id": "postex-1"},
        ]
        
        for finding in findings:
            await aggregator._handle_finding_event(
                f"findings:abc123:{finding['type']}",
                json.dumps(finding),
            )
        
        summary = aggregator.get_summary()
        assert summary.total_count == 4
        assert summary.by_category[FindingCategory.RECON] == 1
        assert summary.by_category[FindingCategory.EXPLOIT] == 2
        assert summary.by_category[FindingCategory.POSTEX] == 1

    @pytest.mark.asyncio
    async def test_deduplication_across_events(self) -> None:
        """Test deduplication works across multiple events."""
        aggregator = FindingAggregator()
        aggregator._running = True
        
        # Same target+type from different agents
        for i in range(3):
            await aggregator._handle_finding_event(
                "findings:abc123:sqli",
                json.dumps({
                    "target": "10.0.0.5",
                    "type": "sqli",
                    "severity": "CRITICAL",
                    "agent_id": f"agent-{i}",
                    "timestamp": 1000.0 + i,
                }),
            )
        
        summary = aggregator.get_summary()
        # Should be deduplicated to 1
        assert summary.total_count == 1
        assert summary.raw_count == 3


# =============================================================================
# Task 10.3: Integration with ReplanTriggerManager callback
# =============================================================================


class TestReplanTriggerIntegration:
    """Tests for ReplanTriggerManager integration."""

    @pytest.mark.asyncio
    async def test_get_findings_for_replan_trigger(self) -> None:
        """Test get_findings_since provides data for re-plan triggers."""
        aggregator = FindingAggregator()
        aggregator._running = True
        
        # Add findings
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="sqli",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=time.time(), agent_id="agent-1",
        ))
        
        # Simulate ReplanTriggerManager requesting findings
        summary = aggregator.get_findings_since()
        
        assert summary.total_count == 1
        assert len(summary.findings) == 1
        
        # Window should be cleared for next cycle
        summary2 = aggregator.get_findings_since()
        assert summary2.total_count == 0

    @pytest.mark.asyncio
    async def test_format_for_director_after_trigger(self) -> None:
        """Test format_for_director produces valid prompt after trigger."""
        aggregator = FindingAggregator()
        
        # Add mixed findings
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.5", finding_type="sqli",
            severity=FindingSeverity.CRITICAL, category=FindingCategory.EXPLOIT,
            timestamp=time.time(), agent_id="exploit-1",
            metadata={"cve_id": "CVE-2024-9999"},
        ))
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.6", finding_type="port_scan",
            severity=FindingSeverity.INFO, category=FindingCategory.RECON,
            timestamp=time.time(), agent_id="recon-1",
        ))
        
        prompt = aggregator.format_for_director()
        
        # Verify prompt structure
        assert "Findings Summary" in prompt
        assert "Critical" in prompt
        assert "10.0.0.5" in prompt
        assert "sqli" in prompt


# =============================================================================
# Task 10.4: Window reset across Director cycles
# =============================================================================


class TestWindowResetCycles:
    """Tests for window reset across Director cycles."""

    @pytest.mark.asyncio
    async def test_multiple_cycles(self) -> None:
        """Test aggregator handles multiple Director cycles."""
        aggregator = FindingAggregator()
        
        # Cycle 1
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.1", finding_type="vuln1",
            severity=FindingSeverity.HIGH, category=FindingCategory.EXPLOIT,
            timestamp=1000.0, agent_id="a",
        ))
        summary1 = aggregator.get_findings_since()
        assert summary1.total_count == 1
        
        # Cycle 2 (window cleared)
        aggregator.add_finding(AggregatedFinding(
            target="10.0.0.2", finding_type="vuln2",
            severity=FindingSeverity.MEDIUM, category=FindingCategory.EXPLOIT,
            timestamp=2000.0, agent_id="a",
        ))
        summary2 = aggregator.get_findings_since()
        assert summary2.total_count == 1
        assert summary2.findings[0].target == "10.0.0.2"


# =============================================================================
# Task 10.5: Concurrent finding addition
# =============================================================================


class TestConcurrentAddition:
    """Tests for concurrent finding addition."""

    @pytest.mark.asyncio
    async def test_concurrent_adds(self) -> None:
        """Test concurrent finding additions are handled correctly."""
        aggregator = FindingAggregator()
        aggregator._running = True
        
        async def add_findings(agent_id: str, count: int) -> None:
            for i in range(count):
                await aggregator._handle_finding_event(
                    f"findings:abc123:type{agent_id}_{i}",
                    json.dumps({
                        "target": f"target-{agent_id}-{i}",
                        "type": f"type{agent_id}_{i}",
                        "severity": "MEDIUM",
                        "agent_id": agent_id,
                    }),
                )
        
        # Run concurrent adds
        await asyncio.gather(
            add_findings("agent-1", 10),
            add_findings("agent-2", 10),
            add_findings("agent-3", 10),
        )
        
        summary = aggregator.get_summary()
        assert summary.total_count == 30


# =============================================================================
# Task 10.6: Graceful handling of malformed events
# =============================================================================


class TestMalformedEvents:
    """Tests for graceful handling of malformed events."""

    @pytest.mark.asyncio
    async def test_malformed_json_skipped(self) -> None:
        """Test malformed JSON events are skipped."""
        aggregator = FindingAggregator()
        aggregator._running = True
        
        # Valid finding
        await aggregator._handle_finding_event(
            "findings:abc123:sqli",
            json.dumps({"target": "10.0.0.5", "type": "sqli", "severity": "HIGH", "agent_id": "a"}),
        )
        
        # Malformed JSON
        await aggregator._handle_finding_event(
            "findings:abc123:xss",
            "not json {",
        )
        
        # Another valid finding
        await aggregator._handle_finding_event(
            "findings:abc123:xss",
            json.dumps({"target": "10.0.0.6", "type": "xss", "severity": "HIGH", "agent_id": "b"}),
        )
        
        summary = aggregator.get_summary()
        # Only 2 valid findings should be counted
        assert summary.total_count == 2

    @pytest.mark.asyncio
    async def test_missing_required_fields_skipped(self) -> None:
        """Test events missing required fields are skipped."""
        aggregator = FindingAggregator()
        aggregator._running = True
        
        # Missing target
        await aggregator._handle_finding_event(
            "findings:abc123:sqli",
            json.dumps({"type": "sqli", "severity": "HIGH"}),
        )
        
        # Missing type
        await aggregator._handle_finding_event(
            "findings:abc123:sqli",
            json.dumps({"target": "10.0.0.5", "severity": "HIGH"}),
        )
        
        # Valid
        await aggregator._handle_finding_event(
            "findings:abc123:sqli",
            json.dumps({"target": "10.0.0.5", "type": "sqli", "severity": "HIGH", "agent_id": "a"}),
        )
        
        summary = aggregator.get_summary()
        assert summary.total_count == 1

    @pytest.mark.asyncio
    async def test_empty_string_fields_skipped(self) -> None:
        """Test events with empty string fields are skipped."""
        aggregator = FindingAggregator()
        aggregator._running = True
        
        # Empty target
        await aggregator._handle_finding_event(
            "findings:abc123:sqli",
            json.dumps({"target": "", "type": "sqli", "severity": "HIGH", "agent_id": "a"}),
        )
        
        # Empty type
        await aggregator._handle_finding_event(
            "findings:abc123:sqli",
            json.dumps({"target": "10.0.0.5", "type": "", "severity": "HIGH", "agent_id": "a"}),
        )
        
        summary = aggregator.get_summary()
        assert summary.total_count == 0
