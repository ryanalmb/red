"""Integration tests for ReplanTriggerManager.

Story 8.8: Re-Plan Triggers.

Tests end-to-end trigger flows with real asyncio timing,
EventBus integration, and aggregator interaction.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from cyberred.orchestration.replan_triggers import (
    TriggerType,
    ReplanTrigger,
    ReplanTriggerConfig,
    ReplanTriggerManager,
    VALID_PHASE_TRANSITIONS,
    VALID_OBJECTIVE_TYPES,
)


# =============================================================================
# Task 10.1: Test end-to-end timer trigger with real asyncio timing
# =============================================================================


class TestTimerTriggerIntegration:
    """Integration tests for timer-based triggers."""

    @pytest.mark.asyncio
    async def test_timer_fires_at_configured_interval(self) -> None:
        """Timer trigger should fire at configured interval with real timing."""
        triggered: List[ReplanTrigger] = []
        
        async def on_trigger(trigger: ReplanTrigger) -> None:
            triggered.append(trigger)
        
        mock_event_bus = MagicMock()
        mock_event_bus.audit = AsyncMock()
        
        config = ReplanTriggerConfig(
            timer_interval_s=0.1,  # 100ms interval for test
            debounce_window_s=0.01,
        )
        
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger,
            config=config,
        )
        
        start_time = time.time()
        await manager.start("eng-integration-001")
        
        # Wait for 2+ timer intervals
        await asyncio.sleep(0.25)
        
        await manager.stop()
        elapsed = time.time() - start_time
        
        # Should have at least 2 timer triggers
        timer_triggers = [t for t in triggered if t.trigger_type == TriggerType.TIMER]
        assert len(timer_triggers) >= 2, f"Expected >= 2 timer triggers in {elapsed:.2f}s, got {len(timer_triggers)}"
        
        # Verify trigger metadata
        for trigger in timer_triggers:
            assert trigger.engagement_id == "eng-integration-001"
            assert trigger.metadata["interval_s"] == 0.1


# =============================================================================
# Task 10.2: Test critical finding trigger via EventBus publish
# =============================================================================


class TestCriticalFindingTriggerIntegration:
    """Integration tests for critical finding triggers."""

    @pytest.mark.asyncio
    async def test_critical_finding_triggers_replan(self) -> None:
        """Critical finding should trigger re-plan within 30s."""
        triggered: List[ReplanTrigger] = []
        
        async def on_trigger(trigger: ReplanTrigger) -> None:
            triggered.append(trigger)
        
        mock_event_bus = MagicMock()
        mock_event_bus.audit = AsyncMock()
        
        config = ReplanTriggerConfig(
            timer_enabled=False,  # Disable timer for this test
            debounce_window_s=0.01,
        )
        
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger,
            config=config,
        )
        
        await manager.start("eng-integration-002")
        
        # Simulate critical finding discovery
        finding = {
            "severity": "critical",
            "finding_id": "CVE-2024-CRITICAL",
            "target": "192.168.1.100",
            "cve_id": "CVE-2024-1234",
            "technique": "T1190",
        }
        
        start_time = time.time()
        await manager._handle_finding("findings:abc123:vuln", finding)
        trigger_latency = time.time() - start_time
        
        await manager.stop()
        
        # Verify trigger fired within 30s (AC: 1)
        assert trigger_latency < 30.0, f"Critical finding trigger took {trigger_latency:.2f}s, exceeds 30s limit"
        
        # Verify trigger details
        assert len(triggered) == 1
        trigger = triggered[0]
        assert trigger.trigger_type == TriggerType.CRITICAL_FINDING
        assert trigger.metadata["cve_id"] == "CVE-2024-1234"
        assert trigger.metadata["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_multiple_critical_findings_debounced(self) -> None:
        """Multiple critical findings within debounce window should be batched."""
        triggered: List[ReplanTrigger] = []
        
        async def on_trigger(trigger: ReplanTrigger) -> None:
            triggered.append(trigger)
        
        mock_event_bus = MagicMock()
        mock_event_bus.audit = AsyncMock()
        
        config = ReplanTriggerConfig(
            timer_enabled=False,
            debounce_window_s=0.5,  # 500ms debounce
        )
        
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger,
            config=config,
        )
        
        await manager.start("eng-integration-003")
        
        # Rapid-fire 5 critical findings
        for i in range(5):
            finding = {
                "severity": "critical",
                "finding_id": f"CVE-{i}",
                "target": f"192.168.1.{i}",
            }
            await manager._handle_finding(f"findings:hash{i}:vuln", finding)
        
        await manager.stop()
        
        # Only first should fire (AC: 6 - debounce)
        assert len(triggered) == 1


# =============================================================================
# Task 10.3: Test phase transition trigger via EventBus publish
# =============================================================================


class TestPhaseTransitionTriggerIntegration:
    """Integration tests for phase transition triggers."""

    @pytest.mark.asyncio
    async def test_phase_transition_fires_immediately(self) -> None:
        """Phase transition should fire trigger immediately (AC: 2)."""
        triggered: List[ReplanTrigger] = []
        
        async def on_trigger(trigger: ReplanTrigger) -> None:
            triggered.append(trigger)
        
        mock_event_bus = MagicMock()
        mock_event_bus.audit = AsyncMock()
        
        config = ReplanTriggerConfig(
            timer_enabled=False,
            debounce_window_s=0.01,
        )
        
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger,
            config=config,
        )
        
        await manager.start("eng-integration-004")
        
        # Test phase transition
        event = {
            "from_phase": "recon",
            "to_phase": "exploit",
            "reason": "Transitioning from recon",
        }
        
        start_time = time.time()
        await manager._handle_phase_change("phases:eng-004", event)
        latency_ms = (time.time() - start_time) * 1000
        
        await manager.stop()
        
        # Should fire immediately (< 100ms)
        assert latency_ms < 100, f"Phase transition took {latency_ms:.1f}ms"
        
        assert len(triggered) == 1
        assert triggered[0].trigger_type == TriggerType.PHASE_TRANSITION
        assert triggered[0].metadata["from_phase"] == "recon"
        assert triggered[0].metadata["to_phase"] == "exploit"

    @pytest.mark.asyncio
    async def test_phase_transition_exploit_to_postex(self) -> None:
        """Phase transition from exploit to postex should fire trigger."""
        triggered: List[ReplanTrigger] = []
        
        async def on_trigger(trigger: ReplanTrigger) -> None:
            triggered.append(trigger)
        
        mock_event_bus = MagicMock()
        mock_event_bus.audit = AsyncMock()
        
        config = ReplanTriggerConfig(
            timer_enabled=False,
            debounce_window_s=0.01,
        )
        
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger,
            config=config,
        )
        
        await manager.start("eng-integration-004b")
        
        event = {
            "from_phase": "exploit",
            "to_phase": "postex",
            "reason": "Shell obtained",
        }
        
        await manager._handle_phase_change("phases:eng-004b", event)
        
        await manager.stop()
        
        assert len(triggered) == 1
        assert triggered[0].metadata["to_phase"] == "postex"


# =============================================================================
# Task 10.4: Test objective met trigger via EventBus publish
# =============================================================================


class TestObjectiveMetTriggerIntegration:
    """Integration tests for objective met triggers."""

    @pytest.mark.asyncio
    async def test_objective_met_triggers(self) -> None:
        """Objective met events should trigger re-plan (AC: 5)."""
        triggered: List[ReplanTrigger] = []
        
        async def on_trigger(trigger: ReplanTrigger) -> None:
            triggered.append(trigger)
        
        mock_event_bus = MagicMock()
        mock_event_bus.audit = AsyncMock()
        
        config = ReplanTriggerConfig(
            timer_enabled=False,
            debounce_window_s=0.01,
        )
        
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger,
            config=config,
        )
        
        await manager.start("eng-integration-005")
        
        # Test all objective types
        objective_types = [
            "data_accessed",
            "shell_obtained",
            "credential_harvested",
        ]
        
        for i, obj_type in enumerate(objective_types):
            # Wait for debounce window between objectives
            if i > 0:
                await asyncio.sleep(0.02)
            
            event = {
                "objective_type": obj_type,
                "target": f"target-{i}",
                "details": f"Achieved {obj_type}",
            }
            
            await manager._handle_objective("objectives:eng-005", event)
        
        await manager.stop()
        
        # All objectives should trigger
        assert len(triggered) == 3
        objective_triggers = [t for t in triggered if t.trigger_type == TriggerType.OBJECTIVE_MET]
        assert len(objective_triggers) == 3


# =============================================================================
# Task 10.5: Test operator override trigger via public method
# =============================================================================


class TestOperatorOverrideTriggerIntegration:
    """Integration tests for operator override triggers."""

    @pytest.mark.asyncio
    async def test_operator_override_fires_immediately(self) -> None:
        """Operator override should fire immediately (AC: 5)."""
        triggered: List[ReplanTrigger] = []
        
        async def on_trigger(trigger: ReplanTrigger) -> None:
            triggered.append(trigger)
        
        mock_event_bus = MagicMock()
        mock_event_bus.audit = AsyncMock()
        
        config = ReplanTriggerConfig(
            timer_enabled=False,
            debounce_window_s=0.01,
        )
        
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger,
            config=config,
        )
        
        await manager.start("eng-integration-006")
        
        start_time = time.time()
        await manager.trigger_replan(
            reason="Operator requested re-plan",
            operator_id="op-admin-001",
        )
        latency_ms = (time.time() - start_time) * 1000
        
        await manager.stop()
        
        # Should fire immediately
        assert latency_ms < 50, f"Operator override took {latency_ms:.1f}ms"
        
        assert len(triggered) == 1
        trigger = triggered[0]
        assert trigger.trigger_type == TriggerType.OPERATOR_OVERRIDE
        assert trigger.metadata["reason"] == "Operator requested re-plan"
        assert trigger.metadata["operator_id"] == "op-admin-001"


# =============================================================================
# Task 10.6: Test debounce under rapid trigger conditions
# =============================================================================


class TestDebounceIntegration:
    """Integration tests for debounce logic."""

    @pytest.mark.asyncio
    async def test_debounce_under_rapid_triggers(self) -> None:
        """Debounce should prevent trigger storms (AC: 6)."""
        triggered: List[ReplanTrigger] = []
        trigger_times: List[float] = []
        
        async def on_trigger(trigger: ReplanTrigger) -> None:
            triggered.append(trigger)
            trigger_times.append(time.time())
        
        mock_event_bus = MagicMock()
        mock_event_bus.audit = AsyncMock()
        
        config = ReplanTriggerConfig(
            timer_enabled=False,
            debounce_window_s=0.2,  # 200ms debounce
        )
        
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger,
            config=config,
        )
        
        await manager.start("eng-integration-007")
        
        # Fire 10 triggers rapidly
        for i in range(10):
            await manager.trigger_replan(reason=f"rapid-{i}")
            await asyncio.sleep(0.01)  # 10ms between triggers
        
        await manager.stop()
        
        # Only first should fire (rest debounced)
        assert len(triggered) == 1
        
        # Verify suppression logged
        assert manager._suppressed_count == 9

    @pytest.mark.asyncio
    async def test_debounce_allows_after_window(self) -> None:
        """Triggers after debounce window should fire."""
        triggered: List[ReplanTrigger] = []
        
        async def on_trigger(trigger: ReplanTrigger) -> None:
            triggered.append(trigger)
        
        mock_event_bus = MagicMock()
        mock_event_bus.audit = AsyncMock()
        
        config = ReplanTriggerConfig(
            timer_enabled=False,
            debounce_window_s=0.1,  # 100ms debounce
        )
        
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger,
            config=config,
        )
        
        await manager.start("eng-integration-008")
        
        # First trigger
        await manager.trigger_replan(reason="first")
        
        # Wait for debounce window
        await asyncio.sleep(0.15)
        
        # Second trigger (after window)
        await manager.trigger_replan(reason="second")
        
        await manager.stop()
        
        # Both should fire
        assert len(triggered) == 2


# =============================================================================
# Task 10.7: Test aggregator integration (findings batch on trigger)
# =============================================================================


class TestAggregatorIntegration:
    """Integration tests for findings aggregation."""

    @pytest.mark.asyncio
    async def test_findings_window_tracking(self) -> None:
        """Manager should track findings window for aggregation (AC: 4)."""
        triggered: List[ReplanTrigger] = []
        
        async def on_trigger(trigger: ReplanTrigger) -> None:
            triggered.append(trigger)
        
        mock_event_bus = MagicMock()
        mock_event_bus.audit = AsyncMock()
        
        config = ReplanTriggerConfig(
            timer_enabled=False,
            debounce_window_s=0.01,
        )
        
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger,
            config=config,
        )
        
        await manager.start("eng-integration-009")
        
        # Get initial window
        start_ts1, end_ts1 = manager.get_findings_window()
        
        # Fire a trigger
        await manager.trigger_replan(reason="test")
        
        # Window should be updated
        start_ts2, end_ts2 = manager.get_findings_window()
        
        # New window start should be after first trigger
        assert start_ts2 > start_ts1
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_last_director_cycle_updated_on_trigger(self) -> None:
        """last_director_cycle should update when trigger fires."""
        triggered: List[ReplanTrigger] = []
        
        async def on_trigger(trigger: ReplanTrigger) -> None:
            triggered.append(trigger)
        
        mock_event_bus = MagicMock()
        mock_event_bus.audit = AsyncMock()
        
        config = ReplanTriggerConfig(
            timer_enabled=False,
            debounce_window_s=0.01,
        )
        
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger,
            config=config,
        )
        
        await manager.start("eng-integration-010")
        
        initial_cycle = manager._last_director_cycle
        
        # Wait a bit
        await asyncio.sleep(0.05)
        
        # Fire trigger
        await manager.trigger_replan(reason="test")
        
        # Cycle should be updated
        assert manager._last_director_cycle > initial_cycle
        
        await manager.stop()


# =============================================================================
# End-to-end lifecycle test
# =============================================================================


class TestLifecycleIntegration:
    """Integration tests for manager lifecycle."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_with_all_trigger_types(self) -> None:
        """Test complete lifecycle with all trigger types."""
        triggered: List[ReplanTrigger] = []
        
        async def on_trigger(trigger: ReplanTrigger) -> None:
            triggered.append(trigger)
        
        mock_event_bus = MagicMock()
        mock_event_bus.audit = AsyncMock()
        
        # Disable debounce entirely for lifecycle test to verify all types work
        config = ReplanTriggerConfig(
            timer_interval_s=0.02,
            debounce_window_s=0.0,  # No debounce for this test
        )
        
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger,
            config=config,
        )
        
        # Start
        await manager.start("eng-lifecycle-001")
        assert manager._running is True
        
        # Wait for timer to fire
        await asyncio.sleep(0.04)
        
        # Critical finding
        await manager._handle_finding("ch", {"severity": "critical", "finding_id": "f1"})
        
        # Phase transition
        await manager._handle_phase_change("ch", {"from_phase": "recon", "to_phase": "exploit"})
        
        # Objective
        await manager._handle_objective("ch", {"objective_type": "shell_obtained", "target": "t1"})
        
        # Operator override
        await manager.trigger_replan(reason="manual")
        
        # Stop
        await manager.stop()
        assert manager._running is False
        
        # Verify all trigger types were seen
        trigger_types = {t.trigger_type for t in triggered}
        assert TriggerType.TIMER in trigger_types, f"TIMER not in {trigger_types}"
        assert TriggerType.CRITICAL_FINDING in trigger_types, f"CRITICAL_FINDING not in {trigger_types}"
        assert TriggerType.PHASE_TRANSITION in trigger_types, f"PHASE_TRANSITION not in {trigger_types}"
        assert TriggerType.OBJECTIVE_MET in trigger_types, f"OBJECTIVE_MET not in {trigger_types}"
        assert TriggerType.OPERATOR_OVERRIDE in trigger_types, f"OPERATOR_OVERRIDE not in {trigger_types}"
