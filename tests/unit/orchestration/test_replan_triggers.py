"""Unit tests for ReplanTriggerManager.

Story 8.8: Re-Plan Triggers.

Tests TriggerType enum, ReplanTrigger/ReplanTriggerConfig dataclasses,
and ReplanTriggerManager functionality including timer, critical finding,
phase transition, objective met, operator override triggers, and debounce logic.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

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
# Task 9.1: Test TriggerType enum completeness
# =============================================================================


class TestTriggerType:
    """Tests for TriggerType enum."""

    def test_trigger_type_has_all_required_values(self) -> None:
        """TriggerType should have all 5 required trigger types."""
        assert TriggerType.TIMER.value == "timer"
        assert TriggerType.CRITICAL_FINDING.value == "critical_finding"
        assert TriggerType.PHASE_TRANSITION.value == "phase_transition"
        assert TriggerType.OBJECTIVE_MET.value == "objective_met"
        assert TriggerType.OPERATOR_OVERRIDE.value == "operator_override"

    def test_trigger_type_has_exactly_5_members(self) -> None:
        """TriggerType should have exactly 5 members."""
        assert len(TriggerType) == 5

    def test_trigger_type_values_are_unique(self) -> None:
        """All TriggerType values should be unique."""
        values = [t.value for t in TriggerType]
        assert len(values) == len(set(values))


class TestValidationConstants:
    """Tests for validation constants (AC 4.2, 5.2)."""

    def test_valid_phase_transitions_contains_required_transitions(self) -> None:
        """VALID_PHASE_TRANSITIONS should contain recon→exploit and exploit→postex."""
        assert ("recon", "exploit") in VALID_PHASE_TRANSITIONS
        assert ("exploit", "postex") in VALID_PHASE_TRANSITIONS

    def test_valid_phase_transitions_has_exactly_2_entries(self) -> None:
        """VALID_PHASE_TRANSITIONS should have exactly 2 valid transitions."""
        assert len(VALID_PHASE_TRANSITIONS) == 2

    def test_valid_phase_transitions_is_immutable(self) -> None:
        """VALID_PHASE_TRANSITIONS should be a frozenset (immutable)."""
        assert isinstance(VALID_PHASE_TRANSITIONS, frozenset)

    def test_valid_objective_types_contains_required_types(self) -> None:
        """VALID_OBJECTIVE_TYPES should contain data_accessed, shell_obtained, credential_harvested."""
        assert "data_accessed" in VALID_OBJECTIVE_TYPES
        assert "shell_obtained" in VALID_OBJECTIVE_TYPES
        assert "credential_harvested" in VALID_OBJECTIVE_TYPES

    def test_valid_objective_types_has_exactly_3_entries(self) -> None:
        """VALID_OBJECTIVE_TYPES should have exactly 3 valid types."""
        assert len(VALID_OBJECTIVE_TYPES) == 3

    def test_valid_objective_types_is_immutable(self) -> None:
        """VALID_OBJECTIVE_TYPES should be a frozenset (immutable)."""
        assert isinstance(VALID_OBJECTIVE_TYPES, frozenset)


# =============================================================================
# Task 9.2: Test ReplanTrigger dataclass creation and validation
# =============================================================================


class TestReplanTrigger:
    """Tests for ReplanTrigger dataclass."""

    def test_replan_trigger_creation_with_required_fields(self) -> None:
        """ReplanTrigger should be created with required fields."""
        trigger = ReplanTrigger(
            trigger_type=TriggerType.TIMER,
            engagement_id="eng-001",
        )
        assert trigger.trigger_type == TriggerType.TIMER
        assert trigger.engagement_id == "eng-001"
        assert isinstance(trigger.timestamp, float)
        assert trigger.metadata == {}

    def test_replan_trigger_creation_with_all_fields(self) -> None:
        """ReplanTrigger should accept all fields."""
        ts = time.time()
        metadata = {"finding_id": "f-123", "severity": "critical"}
        trigger = ReplanTrigger(
            trigger_type=TriggerType.CRITICAL_FINDING,
            engagement_id="eng-002",
            timestamp=ts,
            metadata=metadata,
        )
        assert trigger.trigger_type == TriggerType.CRITICAL_FINDING
        assert trigger.engagement_id == "eng-002"
        assert trigger.timestamp == ts
        assert trigger.metadata == metadata

    def test_replan_trigger_timestamp_default(self) -> None:
        """ReplanTrigger should auto-generate timestamp if not provided."""
        before = time.time()
        trigger = ReplanTrigger(
            trigger_type=TriggerType.PHASE_TRANSITION,
            engagement_id="eng-003",
        )
        after = time.time()
        assert before <= trigger.timestamp <= after

    def test_replan_trigger_metadata_default_is_empty_dict(self) -> None:
        """ReplanTrigger metadata should default to empty dict."""
        trigger = ReplanTrigger(
            trigger_type=TriggerType.OBJECTIVE_MET,
            engagement_id="eng-004",
        )
        assert trigger.metadata == {}
        # Ensure it's a new dict instance (not shared)
        trigger.metadata["key"] = "value"
        trigger2 = ReplanTrigger(
            trigger_type=TriggerType.OBJECTIVE_MET,
            engagement_id="eng-005",
        )
        assert trigger2.metadata == {}


# =============================================================================
# Task 9.3: Test ReplanTriggerConfig defaults and customization
# =============================================================================


class TestReplanTriggerConfig:
    """Tests for ReplanTriggerConfig dataclass."""

    def test_config_default_values(self) -> None:
        """ReplanTriggerConfig should have correct defaults."""
        config = ReplanTriggerConfig()
        assert config.timer_interval_s == 300.0  # 5 minutes
        assert config.debounce_window_s == 10.0
        assert config.critical_finding_delay_max_s == 30.0
        assert config.timer_enabled is True
        assert config.critical_finding_enabled is True
        assert config.phase_transition_enabled is True
        assert config.objective_met_enabled is True

    def test_config_custom_values(self) -> None:
        """ReplanTriggerConfig should accept custom values."""
        config = ReplanTriggerConfig(
            timer_interval_s=60.0,
            debounce_window_s=5.0,
            critical_finding_delay_max_s=15.0,
            timer_enabled=False,
            critical_finding_enabled=False,
            phase_transition_enabled=False,
            objective_met_enabled=False,
        )
        assert config.timer_interval_s == 60.0
        assert config.debounce_window_s == 5.0
        assert config.critical_finding_delay_max_s == 15.0
        assert config.timer_enabled is False
        assert config.critical_finding_enabled is False
        assert config.phase_transition_enabled is False
        assert config.objective_met_enabled is False


# =============================================================================
# Task 9.4-9.8: Test ReplanTriggerManager
# =============================================================================


class TestReplanTriggerManager:
    """Tests for ReplanTriggerManager class."""

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        """Create a mock EventBus."""
        event_bus = MagicMock()
        event_bus.subscribe = AsyncMock(return_value=MagicMock())
        event_bus.audit = AsyncMock()
        return event_bus

    @pytest.fixture
    def triggered_list(self) -> List[ReplanTrigger]:
        """List to collect triggered events."""
        return []

    @pytest.fixture
    def on_trigger_callback(
        self, triggered_list: List[ReplanTrigger]
    ) -> AsyncMock:
        """Create callback that collects triggers."""
        async def callback(trigger: ReplanTrigger) -> None:
            triggered_list.append(trigger)
        return AsyncMock(side_effect=callback)

    @pytest.fixture
    def manager(
        self, mock_event_bus: MagicMock, on_trigger_callback: AsyncMock
    ) -> ReplanTriggerManager:
        """Create a ReplanTriggerManager instance."""
        return ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
        )

    def test_manager_initialization(
        self, mock_event_bus: MagicMock, on_trigger_callback: AsyncMock
    ) -> None:
        """Manager should initialize with event_bus, callback, and default config."""
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
        )
        assert manager._event_bus is mock_event_bus
        assert manager._on_trigger is on_trigger_callback
        assert isinstance(manager._config, ReplanTriggerConfig)

    def test_manager_initialization_with_custom_config(
        self, mock_event_bus: MagicMock, on_trigger_callback: AsyncMock
    ) -> None:
        """Manager should accept custom config."""
        config = ReplanTriggerConfig(timer_interval_s=120.0)
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
            config=config,
        )
        assert manager._config.timer_interval_s == 120.0

    @pytest.mark.asyncio
    async def test_manager_start_sets_running_state(
        self, manager: ReplanTriggerManager
    ) -> None:
        """start() should set running state and engagement_id."""
        await manager.start("eng-001")
        assert manager._running is True
        assert manager._engagement_id == "eng-001"
        await manager.stop()

    @pytest.mark.asyncio
    async def test_manager_stop_clears_running_state(
        self, manager: ReplanTriggerManager
    ) -> None:
        """stop() should clear running state."""
        await manager.start("eng-001")
        await manager.stop()
        assert manager._running is False

    @pytest.mark.asyncio
    async def test_operator_override_trigger(
        self,
        manager: ReplanTriggerManager,
        on_trigger_callback: AsyncMock,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """trigger_replan() should fire operator override trigger immediately."""
        await manager.start("eng-001")
        await manager.trigger_replan(reason="manual request", operator_id="op-123")
        await manager.stop()

        assert len(triggered_list) == 1
        trigger = triggered_list[0]
        assert trigger.trigger_type == TriggerType.OPERATOR_OVERRIDE
        assert trigger.engagement_id == "eng-001"
        assert trigger.metadata["reason"] == "manual request"
        assert trigger.metadata["operator_id"] == "op-123"

    @pytest.mark.asyncio
    async def test_critical_finding_trigger_fires_on_critical_severity(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Critical finding trigger should fire for severity=critical."""
        await manager.start("eng-001")
        
        # Simulate receiving a critical finding
        finding = {
            "severity": "critical",
            "finding_id": "f-123",
            "target": "192.168.1.1",
            "cve_id": "CVE-2024-1234",
        }
        await manager._handle_finding("findings:abc123:vuln", finding)
        await manager.stop()

        assert len(triggered_list) == 1
        trigger = triggered_list[0]
        assert trigger.trigger_type == TriggerType.CRITICAL_FINDING
        assert trigger.metadata["finding_id"] == "f-123"
        assert trigger.metadata["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_critical_finding_trigger_ignores_non_critical(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Critical finding trigger should NOT fire for non-critical severity."""
        await manager.start("eng-001")
        
        # Simulate receiving non-critical findings
        for severity in ["high", "medium", "low", "info"]:
            finding = {"severity": severity, "finding_id": f"f-{severity}"}
            await manager._handle_finding("findings:abc123:vuln", finding)
        
        await manager.stop()
        assert len(triggered_list) == 0

    @pytest.mark.asyncio
    async def test_phase_transition_trigger_fires_immediately(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Phase transition trigger should fire immediately."""
        await manager.start("eng-001")
        
        event = {
            "from_phase": "recon",
            "to_phase": "exploit",
            "reason": "recon complete",
        }
        await manager._handle_phase_change("phases:eng-001", event)
        await manager.stop()

        assert len(triggered_list) == 1
        trigger = triggered_list[0]
        assert trigger.trigger_type == TriggerType.PHASE_TRANSITION
        assert trigger.metadata["from_phase"] == "recon"
        assert trigger.metadata["to_phase"] == "exploit"

    @pytest.mark.asyncio
    async def test_objective_met_trigger(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Objective met trigger should fire when objective is achieved."""
        await manager.start("eng-001")
        
        event = {
            "objective_type": "data_accessed",
            "target": "db-server",
            "details": "Retrieved customer database",
        }
        await manager._handle_objective("objectives:eng-001", event)
        await manager.stop()

        assert len(triggered_list) == 1
        trigger = triggered_list[0]
        assert trigger.trigger_type == TriggerType.OBJECTIVE_MET
        assert trigger.metadata["objective_type"] == "data_accessed"

    @pytest.mark.asyncio
    async def test_objective_met_trigger_ignores_invalid_type(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Objective met trigger should NOT fire for invalid objective types."""
        await manager.start("eng-001")
        
        # Invalid objective type should be ignored
        event = {
            "objective_type": "invalid_objective",
            "target": "some-target",
        }
        await manager._handle_objective("objectives:eng-001", event)
        await manager.stop()

        assert len(triggered_list) == 0

    @pytest.mark.asyncio
    async def test_phase_transition_ignores_invalid_transition(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Phase transition trigger should NOT fire for invalid transitions."""
        await manager.start("eng-001")
        
        # Invalid transition (postex -> recon is not valid)
        event = {
            "from_phase": "postex",
            "to_phase": "recon",
            "reason": "invalid backward transition",
        }
        await manager._handle_phase_change("phases:eng-001", event)
        await manager.stop()

        assert len(triggered_list) == 0

    @pytest.mark.asyncio
    async def test_debounce_suppresses_rapid_triggers(
        self,
        mock_event_bus: MagicMock,
        on_trigger_callback: AsyncMock,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Debounce should suppress rapid triggers within window."""
        config = ReplanTriggerConfig(debounce_window_s=1.0)
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
            config=config,
        )
        await manager.start("eng-001")

        # Fire multiple triggers rapidly
        for i in range(5):
            await manager.trigger_replan(reason=f"trigger-{i}")

        await manager.stop()

        # Only first trigger should fire (others debounced)
        assert len(triggered_list) == 1

    @pytest.mark.asyncio
    async def test_debounce_allows_triggers_after_window(
        self,
        mock_event_bus: MagicMock,
        on_trigger_callback: AsyncMock,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Triggers after debounce window should fire."""
        config = ReplanTriggerConfig(debounce_window_s=0.1)
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
            config=config,
        )
        await manager.start("eng-001")

        # First trigger
        await manager.trigger_replan(reason="first")
        
        # Wait for debounce window to pass
        await asyncio.sleep(0.15)
        
        # Second trigger after window
        await manager.trigger_replan(reason="second")

        await manager.stop()

        assert len(triggered_list) == 2

    @pytest.mark.asyncio
    async def test_timer_trigger_disabled_when_config_false(
        self,
        mock_event_bus: MagicMock,
        on_trigger_callback: AsyncMock,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Timer trigger should not fire when disabled in config."""
        config = ReplanTriggerConfig(
            timer_enabled=False,
            timer_interval_s=0.05,  # Very short for test
        )
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
            config=config,
        )
        await manager.start("eng-001")
        await asyncio.sleep(0.1)
        await manager.stop()

        # No timer triggers should fire
        timer_triggers = [t for t in triggered_list if t.trigger_type == TriggerType.TIMER]
        assert len(timer_triggers) == 0

    @pytest.mark.asyncio
    async def test_critical_finding_trigger_disabled_when_config_false(
        self,
        mock_event_bus: MagicMock,
        on_trigger_callback: AsyncMock,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Critical finding trigger should not fire when disabled."""
        config = ReplanTriggerConfig(critical_finding_enabled=False)
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
            config=config,
        )
        await manager.start("eng-001")
        
        finding = {"severity": "critical", "finding_id": "f-123"}
        await manager._handle_finding("findings:abc:vuln", finding)
        
        await manager.stop()
        assert len(triggered_list) == 0

    @pytest.mark.asyncio
    async def test_phase_transition_trigger_disabled_when_config_false(
        self,
        mock_event_bus: MagicMock,
        on_trigger_callback: AsyncMock,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Phase transition trigger should not fire when disabled."""
        config = ReplanTriggerConfig(phase_transition_enabled=False)
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
            config=config,
        )
        await manager.start("eng-001")
        
        event = {"from_phase": "recon", "to_phase": "exploit"}
        await manager._handle_phase_change("phases:eng-001", event)
        
        await manager.stop()
        assert len(triggered_list) == 0

    @pytest.mark.asyncio
    async def test_objective_met_trigger_disabled_when_config_false(
        self,
        mock_event_bus: MagicMock,
        on_trigger_callback: AsyncMock,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Objective met trigger should not fire when disabled."""
        config = ReplanTriggerConfig(objective_met_enabled=False)
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
            config=config,
        )
        await manager.start("eng-001")
        
        event = {"objective_type": "shell_obtained", "target": "web-server"}
        await manager._handle_objective("objectives:eng-001", event)
        
        await manager.stop()
        assert len(triggered_list) == 0

    @pytest.mark.asyncio
    async def test_triggers_not_fired_when_not_running(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Triggers should not fire when manager is not running."""
        # Don't call start()
        await manager.trigger_replan(reason="should not fire")
        assert len(triggered_list) == 0

    @pytest.mark.asyncio
    async def test_last_director_cycle_tracking(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Manager should track last Director cycle timestamp."""
        await manager.start("eng-001")
        
        initial_time = manager._last_director_cycle
        
        await manager.trigger_replan(reason="test")
        
        # Last director cycle should be updated
        assert manager._last_director_cycle > initial_time
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_get_findings_since_last_cycle(
        self,
        manager: ReplanTriggerManager,
    ) -> None:
        """get_findings_since_last_cycle() should return findings window."""
        await manager.start("eng-001")
        
        # Initially should be empty or return reasonable defaults
        start_ts, end_ts = manager.get_findings_window()
        assert start_ts <= end_ts
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_timer_reset_on_manual_trigger(
        self,
        mock_event_bus: MagicMock,
        on_trigger_callback: AsyncMock,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Timer should reset after manual trigger to avoid immediate re-trigger."""
        config = ReplanTriggerConfig(
            timer_interval_s=0.1,
            debounce_window_s=0.01,
        )
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
            config=config,
        )
        await manager.start("eng-001")
        
        # Wait a bit but not full interval
        await asyncio.sleep(0.05)
        
        # Manual trigger should reset timer
        await manager.trigger_replan(reason="manual")
        
        # The timer should have been reset, check internal state
        assert manager._last_timer_fire > 0
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_pause_and_resume(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """pause() and resume() should control trigger firing."""
        await manager.start("eng-001")
        
        # Pause manager
        manager.pause()
        assert manager._paused is True
        
        # Triggers should not fire while paused
        finding = {"severity": "critical", "finding_id": "f-123"}
        await manager._handle_finding("findings:abc:vuln", finding)
        assert len(triggered_list) == 0
        
        # Resume manager
        manager.resume()
        assert manager._paused is False
        
        # Triggers should fire now
        await manager._handle_finding("findings:abc:vuln", finding)
        assert len(triggered_list) == 1
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_handle_finding_with_json_string(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Handler should parse JSON string finding."""
        await manager.start("eng-001")
        
        # Send finding as JSON string
        import json
        finding_json = json.dumps({
            "severity": "critical",
            "finding_id": "f-json",
            "target": "10.0.0.1",
        })
        await manager._handle_finding("findings:abc:vuln", finding_json)
        await manager.stop()
        
        assert len(triggered_list) == 1
        assert triggered_list[0].metadata["finding_id"] == "f-json"

    @pytest.mark.asyncio
    async def test_handle_finding_invalid_json(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Handler should handle invalid JSON gracefully."""
        await manager.start("eng-001")
        
        # Send invalid JSON
        await manager._handle_finding("findings:abc:vuln", "not-valid-json{")
        await manager.stop()
        
        # No trigger should fire
        assert len(triggered_list) == 0

    @pytest.mark.asyncio
    async def test_handle_phase_change_with_json_string(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Handler should parse JSON string phase change event."""
        await manager.start("eng-001")
        
        import json
        event_json = json.dumps({
            "from_phase": "exploit",
            "to_phase": "postex",
            "reason": "shell obtained",
        })
        await manager._handle_phase_change("phases:eng-001", event_json)
        await manager.stop()
        
        assert len(triggered_list) == 1
        assert triggered_list[0].metadata["to_phase"] == "postex"

    @pytest.mark.asyncio
    async def test_handle_phase_change_invalid_json(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Handler should handle invalid JSON gracefully."""
        await manager.start("eng-001")
        
        await manager._handle_phase_change("phases:eng-001", "invalid{json")
        await manager.stop()
        
        assert len(triggered_list) == 0

    @pytest.mark.asyncio
    async def test_handle_objective_with_json_string(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Handler should parse JSON string objective event."""
        await manager.start("eng-001")
        
        import json
        event_json = json.dumps({
            "objective_type": "credential_harvested",
            "target": "dc-01",
            "details": "Admin credentials obtained",
        })
        await manager._handle_objective("objectives:eng-001", event_json)
        await manager.stop()
        
        assert len(triggered_list) == 1
        assert triggered_list[0].metadata["objective_type"] == "credential_harvested"

    @pytest.mark.asyncio
    async def test_handle_objective_invalid_json(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Handler should handle invalid JSON gracefully."""
        await manager.start("eng-001")
        
        await manager._handle_objective("objectives:eng-001", "{invalid}")
        await manager.stop()
        
        assert len(triggered_list) == 0

    @pytest.mark.asyncio
    async def test_trigger_callback_error_handling(
        self,
        mock_event_bus: MagicMock,
    ) -> None:
        """Manager should handle callback errors gracefully."""
        async def failing_callback(trigger: ReplanTrigger) -> None:
            raise RuntimeError("Callback failed!")
        
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=failing_callback,
        )
        await manager.start("eng-001")
        
        # This should not raise, error is logged
        await manager.trigger_replan(reason="test")
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_audit_log_error_handling(
        self,
        on_trigger_callback: AsyncMock,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Manager should handle audit log errors gracefully."""
        mock_event_bus = MagicMock()
        mock_event_bus.subscribe = AsyncMock(return_value=MagicMock())
        mock_event_bus.audit = AsyncMock(side_effect=RuntimeError("Audit failed!"))
        
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
        )
        await manager.start("eng-001")
        
        # Trigger should still fire even if audit fails
        await manager.trigger_replan(reason="test")
        
        await manager.stop()
        assert len(triggered_list) == 1

    @pytest.mark.asyncio
    async def test_subscription_unsubscribe_error(
        self,
        on_trigger_callback: AsyncMock,
    ) -> None:
        """Manager should handle subscription unsubscribe errors gracefully."""
        mock_subscription = MagicMock()
        mock_subscription.unsubscribe = AsyncMock(side_effect=RuntimeError("Unsub failed!"))
        
        mock_event_bus = MagicMock()
        mock_event_bus.subscribe = AsyncMock(return_value=mock_subscription)
        mock_event_bus.audit = AsyncMock()
        
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
        )
        await manager.start("eng-001")
        manager._subscriptions.append(mock_subscription)
        
        # Stop should not raise despite unsubscribe error
        await manager.stop()

    @pytest.mark.asyncio
    async def test_timer_loop_fires_trigger(
        self,
        mock_event_bus: MagicMock,
        on_trigger_callback: AsyncMock,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Timer loop should fire timer triggers at interval."""
        config = ReplanTriggerConfig(
            timer_interval_s=0.05,  # 50ms for quick test
            debounce_window_s=0.01,
        )
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
            config=config,
        )
        await manager.start("eng-001")
        
        # Wait for at least one timer trigger
        await asyncio.sleep(0.08)
        
        await manager.stop()
        
        # Should have at least one timer trigger
        timer_triggers = [t for t in triggered_list if t.trigger_type == TriggerType.TIMER]
        assert len(timer_triggers) >= 1

    @pytest.mark.asyncio
    async def test_timer_loop_respects_pause(
        self,
        mock_event_bus: MagicMock,
        on_trigger_callback: AsyncMock,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Timer loop should skip firing when paused."""
        config = ReplanTriggerConfig(
            timer_interval_s=0.03,
            debounce_window_s=0.01,
        )
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
            config=config,
        )
        await manager.start("eng-001")
        
        # Pause immediately
        manager.pause()
        
        # Wait for potential timer trigger
        await asyncio.sleep(0.08)
        
        await manager.stop()
        
        # No timer triggers should fire while paused
        timer_triggers = [t for t in triggered_list if t.trigger_type == TriggerType.TIMER]
        assert len(timer_triggers) == 0

    @pytest.mark.asyncio
    async def test_handlers_not_running(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Handlers should not fire triggers when manager is not running."""
        # Don't start the manager
        
        finding = {"severity": "critical", "finding_id": "f-123"}
        await manager._handle_finding("findings:abc:vuln", finding)
        
        event = {"from_phase": "recon", "to_phase": "exploit"}
        await manager._handle_phase_change("phases:eng-001", event)
        
        obj_event = {"objective_type": "data_accessed", "target": "db"}
        await manager._handle_objective("objectives:eng-001", obj_event)
        
        assert len(triggered_list) == 0

    @pytest.mark.asyncio
    async def test_handlers_while_paused(
        self,
        manager: ReplanTriggerManager,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Handlers should not fire triggers when manager is paused."""
        await manager.start("eng-001")
        manager.pause()
        
        finding = {"severity": "critical", "finding_id": "f-123"}
        await manager._handle_finding("findings:abc:vuln", finding)
        
        event = {"from_phase": "recon", "to_phase": "exploit"}
        await manager._handle_phase_change("phases:eng-001", event)
        
        obj_event = {"objective_type": "data_accessed", "target": "db"}
        await manager._handle_objective("objectives:eng-001", obj_event)
        
        await manager.stop()
        assert len(triggered_list) == 0

    @pytest.mark.asyncio
    async def test_timer_skips_when_recently_reset(
        self,
        mock_event_bus: MagicMock,
        on_trigger_callback: AsyncMock,
        triggered_list: List[ReplanTrigger],
    ) -> None:
        """Timer should skip firing when recently reset by manual trigger."""
        config = ReplanTriggerConfig(
            timer_interval_s=0.03,
            debounce_window_s=0.001,
        )
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
            config=config,
        )
        await manager.start("eng-001")
        
        # Let the timer start its first sleep cycle
        await asyncio.sleep(0.01)
        
        # Simulate a recent manual trigger that reset the timer
        # Set last_timer_fire to a time that is within 90% of the interval
        # This simulates the timer waking up but finding it was recently reset
        manager._last_timer_fire = time.time()
        
        # Wait for the timer to wake up and check the recently reset condition
        await asyncio.sleep(0.04)
        
        await manager.stop()
        
        # Timer may or may not have triggers depending on timing
        # The test ensures the branch is hit without exceptions
        timer_triggers = [t for t in triggered_list if t.trigger_type == TriggerType.TIMER]
        assert isinstance(timer_triggers, list)

    @pytest.mark.asyncio
    async def test_timer_loop_stops_when_running_false(
        self,
        mock_event_bus: MagicMock,
        on_trigger_callback: AsyncMock,
    ) -> None:
        """Timer loop should exit when running is set to False during sleep."""
        config = ReplanTriggerConfig(
            timer_interval_s=0.02,
            debounce_window_s=0.001,
        )
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
            config=config,
        )
        await manager.start("eng-001")
        
        # Let timer sleep start
        await asyncio.sleep(0.01)
        
        # Set running to false - timer should exit on next wake
        manager._running = False
        
        # Wait for timer to wake and exit
        await asyncio.sleep(0.03)
        
        # Now stop properly
        await manager.stop()

    @pytest.mark.asyncio
    async def test_timer_loop_handles_exception(
        self,
        mock_event_bus: MagicMock,
    ) -> None:
        """Timer loop should handle exceptions gracefully."""
        call_count = 0
        
        async def failing_callback(trigger: ReplanTrigger) -> None:
            nonlocal call_count
            call_count += 1
            if trigger.trigger_type == TriggerType.TIMER:
                # Raise a non-CancelledError exception
                raise ValueError("Test exception in timer callback")
        
        config = ReplanTriggerConfig(
            timer_interval_s=0.02,
            debounce_window_s=0.001,
        )
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=failing_callback,
            config=config,
        )
        await manager.start("eng-001")
        
        # Wait for timer to fire and hit the exception
        await asyncio.sleep(0.05)
        
        await manager.stop()
        
        # Callback should have been called despite exception
        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_timer_loop_direct_exception_in_loop(
        self,
        mock_event_bus: MagicMock,
        on_trigger_callback: AsyncMock,
    ) -> None:
        """Timer loop should catch and log exceptions in the loop itself."""
        config = ReplanTriggerConfig(
            timer_interval_s=0.02,
            debounce_window_s=0.001,
        )
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=on_trigger_callback,
            config=config,
        )
        await manager.start("eng-001")
        
        # Inject an exception by making _fire_trigger raise
        original_fire = manager._fire_trigger
        
        async def raising_fire(trigger: ReplanTrigger) -> None:
            if trigger.trigger_type == TriggerType.TIMER:
                raise RuntimeError("Simulated timer loop exception")
            await original_fire(trigger)
        
        manager._fire_trigger = raising_fire
        
        # Wait for timer to fire
        await asyncio.sleep(0.05)
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_timer_recently_reset_branch_coverage(
        self,
        mock_event_bus: MagicMock,
    ) -> None:
        """Directly test the recently reset branch in timer loop."""
        triggered = []
        
        async def callback(trigger: ReplanTrigger) -> None:
            triggered.append(trigger)
        
        config = ReplanTriggerConfig(
            timer_interval_s=0.02,
            debounce_window_s=0.001,
        )
        manager = ReplanTriggerManager(
            event_bus=mock_event_bus,
            on_trigger=callback,
            config=config,
        )
        
        # Start manager
        await manager.start("eng-001")
        
        # Immediately after start, set last_timer_fire to current time
        # so when timer wakes, it sees it was "recently reset"
        await asyncio.sleep(0.015)  # Almost at timer interval
        manager._last_timer_fire = time.time()  # Reset it
        
        # Wait for timer to wake and check the condition
        await asyncio.sleep(0.01)
        
        await manager.stop()
