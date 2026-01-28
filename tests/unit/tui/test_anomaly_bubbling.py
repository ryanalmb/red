"""Unit tests for Anomaly Bubbling feature.

Story 9.4: Anomaly Bubbling
Tests the bubbling mechanism that surfaces agents requiring attention to the top of the list.

Acceptance Criteria:
1. Agent requiring attention (auth pending, error, critical finding) moves to top
2. Attention indicator is visually distinct (color, icon)
3. Attention types prioritized: error > auth_pending > critical_finding > stalled
4. Bubbling animation is smooth (no jarring jumps)
5. Dismissed attention returns agent to normal position
6. Integration tests verify bubbling behavior
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio


class TestAttentionPriority:
    """Tests for AttentionPriority enum."""

    def test_attention_priority_enum_values(self):
        """Test AttentionPriority enum has correct values per spec."""
        from cyberred.tui.widgets.agent_list import AttentionPriority
        
        assert AttentionPriority.ERROR == 0
        assert AttentionPriority.AUTH_PENDING == 1
        assert AttentionPriority.CRITICAL_FINDING == 2
        assert AttentionPriority.STALLED == 3
        assert AttentionPriority.NONE == 99

    def test_attention_priority_ordering(self):
        """Test AttentionPriority values are ordered correctly (lower = higher priority)."""
        from cyberred.tui.widgets.agent_list import AttentionPriority
        
        # ERROR should be highest priority (lowest value)
        assert AttentionPriority.ERROR < AttentionPriority.AUTH_PENDING
        assert AttentionPriority.AUTH_PENDING < AttentionPriority.CRITICAL_FINDING
        assert AttentionPriority.CRITICAL_FINDING < AttentionPriority.STALLED
        assert AttentionPriority.STALLED < AttentionPriority.NONE

    def test_attention_priority_is_int_enum(self):
        """Test AttentionPriority is an IntEnum for efficient comparison."""
        from cyberred.tui.widgets.agent_list import AttentionPriority
        from enum import IntEnum
        
        assert issubclass(AttentionPriority, IntEnum)


class TestGetAttentionPriority:
    """Tests for get_attention_priority function."""

    def test_get_attention_priority_error(self):
        """Test ERROR status returns ERROR priority."""
        from cyberred.tui.widgets.agent_list import (
            get_attention_priority, AgentStatus, AttentionPriority
        )
        
        assert get_attention_priority(AgentStatus.ERROR) == AttentionPriority.ERROR

    def test_get_attention_priority_auth_pending(self):
        """Test AUTH_PENDING status returns AUTH_PENDING priority."""
        from cyberred.tui.widgets.agent_list import (
            get_attention_priority, AgentStatus, AttentionPriority
        )
        
        assert get_attention_priority(AgentStatus.AUTH_PENDING) == AttentionPriority.AUTH_PENDING

    def test_get_attention_priority_critical_finding(self):
        """Test CRITICAL_FINDING status returns CRITICAL_FINDING priority."""
        from cyberred.tui.widgets.agent_list import (
            get_attention_priority, AgentStatus, AttentionPriority
        )
        
        assert get_attention_priority(AgentStatus.CRITICAL_FINDING) == AttentionPriority.CRITICAL_FINDING

    def test_get_attention_priority_stalled(self):
        """Test STALLED status returns STALLED priority."""
        from cyberred.tui.widgets.agent_list import (
            get_attention_priority, AgentStatus, AttentionPriority
        )
        
        assert get_attention_priority(AgentStatus.STALLED) == AttentionPriority.STALLED

    def test_get_attention_priority_active_returns_none(self):
        """Test ACTIVE status returns NONE priority (no attention needed)."""
        from cyberred.tui.widgets.agent_list import (
            get_attention_priority, AgentStatus, AttentionPriority
        )
        
        assert get_attention_priority(AgentStatus.ACTIVE) == AttentionPriority.NONE

    def test_get_attention_priority_idle_returns_none(self):
        """Test IDLE status returns NONE priority (no attention needed)."""
        from cyberred.tui.widgets.agent_list import (
            get_attention_priority, AgentStatus, AttentionPriority
        )
        
        assert get_attention_priority(AgentStatus.IDLE) == AttentionPriority.NONE


class TestIsAttentionRequired:
    """Tests for is_attention_required helper function."""

    def test_is_attention_required_error(self):
        """Test ERROR status requires attention."""
        from cyberred.tui.widgets.agent_list import is_attention_required, AgentStatus
        
        assert is_attention_required(AgentStatus.ERROR) is True

    def test_is_attention_required_auth_pending(self):
        """Test AUTH_PENDING status requires attention."""
        from cyberred.tui.widgets.agent_list import is_attention_required, AgentStatus
        
        assert is_attention_required(AgentStatus.AUTH_PENDING) is True

    def test_is_attention_required_critical_finding(self):
        """Test CRITICAL_FINDING status requires attention."""
        from cyberred.tui.widgets.agent_list import is_attention_required, AgentStatus
        
        assert is_attention_required(AgentStatus.CRITICAL_FINDING) is True

    def test_is_attention_required_stalled(self):
        """Test STALLED status requires attention."""
        from cyberred.tui.widgets.agent_list import is_attention_required, AgentStatus
        
        assert is_attention_required(AgentStatus.STALLED) is True

    def test_is_attention_required_active_false(self):
        """Test ACTIVE status does not require attention."""
        from cyberred.tui.widgets.agent_list import is_attention_required, AgentStatus
        
        assert is_attention_required(AgentStatus.ACTIVE) is False

    def test_is_attention_required_idle_false(self):
        """Test IDLE status does not require attention."""
        from cyberred.tui.widgets.agent_list import is_attention_required, AgentStatus
        
        assert is_attention_required(AgentStatus.IDLE) is False


class TestAgentRowAttentionState:
    """Tests for AgentRow attention state extensions."""

    def test_agent_row_has_attention_dismissed_slot(self):
        """Test AgentRow has attention_dismissed in __slots__."""
        from cyberred.tui.widgets.agent_list import AgentRow
        
        assert "attention_dismissed" in AgentRow.__slots__

    def test_agent_row_attention_dismissed_default_false(self):
        """Test AgentRow.attention_dismissed defaults to False."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row = AgentRow(agent_id="agent-0001")
        assert row.attention_dismissed is False

    def test_agent_row_dismiss_attention_method(self):
        """Test AgentRow.dismiss_attention() sets attention_dismissed to True."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row = AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR)
        row.dismiss_attention()
        assert row.attention_dismissed is True

    def test_agent_row_requires_attention_property_true(self):
        """Test requires_attention returns True when attention needed and not dismissed."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row = AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR)
        assert row.requires_attention is True

    def test_agent_row_requires_attention_property_false_when_dismissed(self):
        """Test requires_attention returns False when attention was dismissed."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row = AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR)
        row.dismiss_attention()
        assert row.requires_attention is False

    def test_agent_row_requires_attention_property_false_for_normal_status(self):
        """Test requires_attention returns False for statuses that don't need attention."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row = AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE)
        assert row.requires_attention is False
        
        row2 = AgentRow(agent_id="agent-0002", status=AgentStatus.IDLE)
        assert row2.requires_attention is False

    def test_agent_row_equality_includes_attention_dismissed(self):
        """Test AgentRow equality includes attention_dismissed field."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row1 = AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR)
        row2 = AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR)
        row2.dismiss_attention()
        
        # Same agent_id and status, but different attention_dismissed
        assert row1 != row2

    def test_agent_row_reset_attention_on_new_attention_state(self):
        """Test attention_dismissed resets when agent enters new attention state."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row = AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR)
        row.dismiss_attention()
        assert row.attention_dismissed is True
        
        # Simulate status change to a new attention state
        row.reset_attention_dismissed()
        assert row.attention_dismissed is False


class TestBubblingSort:
    """Tests for _sort_with_bubbling method in VirtualizedAgentList."""

    def test_sort_with_bubbling_error_to_top(self):
        """Test agent with ERROR status bubbles to top."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE))
        agent_list.add_agent(AgentRow(agent_id="agent-0002", status=AgentStatus.IDLE))
        agent_list.add_agent(AgentRow(agent_id="agent-0003", status=AgentStatus.ERROR))
        
        agent_list._sort_with_bubbling()
        
        agents = list(agent_list.agents)
        assert agents[0].agent_id == "agent-0003"  # ERROR at top
        assert agents[0].status == AgentStatus.ERROR

    def test_sort_with_bubbling_priority_order(self):
        """Test bubbling sort respects priority: error > auth_pending > critical > stalled."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-stalled", status=AgentStatus.STALLED))
        agent_list.add_agent(AgentRow(agent_id="agent-error", status=AgentStatus.ERROR))
        agent_list.add_agent(AgentRow(agent_id="agent-critical", status=AgentStatus.CRITICAL_FINDING))
        agent_list.add_agent(AgentRow(agent_id="agent-auth", status=AgentStatus.AUTH_PENDING))
        agent_list.add_agent(AgentRow(agent_id="agent-active", status=AgentStatus.ACTIVE))
        
        agent_list._sort_with_bubbling()
        
        agents = list(agent_list.agents)
        assert agents[0].agent_id == "agent-error"
        assert agents[1].agent_id == "agent-auth"
        assert agents[2].agent_id == "agent-critical"
        assert agents[3].agent_id == "agent-stalled"
        assert agents[4].agent_id == "agent-active"

    def test_sort_with_bubbling_stable_sort(self):
        """Test bubbling sort preserves order within same priority (stable sort)."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        # Add agents in specific order
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE))
        agent_list.add_agent(AgentRow(agent_id="agent-0002", status=AgentStatus.ACTIVE))
        agent_list.add_agent(AgentRow(agent_id="agent-0003", status=AgentStatus.ACTIVE))
        
        agent_list._sort_with_bubbling()
        
        agents = list(agent_list.agents)
        # Order should be preserved for same-priority agents
        assert agents[0].agent_id == "agent-0001"
        assert agents[1].agent_id == "agent-0002"
        assert agents[2].agent_id == "agent-0003"

    def test_sort_with_bubbling_dismissed_goes_back(self):
        """Test dismissed attention agent returns to normal position."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE))
        error_agent = AgentRow(agent_id="agent-0002", status=AgentStatus.ERROR)
        agent_list.add_agent(error_agent)
        agent_list.add_agent(AgentRow(agent_id="agent-0003", status=AgentStatus.ACTIVE))
        
        # First sort - error should be at top
        agent_list._sort_with_bubbling()
        agents = list(agent_list.agents)
        assert agents[0].agent_id == "agent-0002"
        
        # Dismiss attention
        agent_list.get_agent("agent-0002").dismiss_attention()
        agent_list._sort_with_bubbling()
        
        # Error agent should now be back in original position (index 1)
        agents = list(agent_list.agents)
        assert agents[0].agent_id == "agent-0001"
        assert agents[1].agent_id == "agent-0002"
        assert agents[2].agent_id == "agent-0003"

    def test_sort_with_bubbling_has_original_order_tracking(self):
        """Test VirtualizedAgentList tracks original insertion order."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE))
        agent_list.add_agent(AgentRow(agent_id="agent-0002", status=AgentStatus.IDLE))
        
        assert hasattr(agent_list, "_original_order")
        assert agent_list._original_order["agent-0001"] == 0
        assert agent_list._original_order["agent-0002"] == 1


class TestUpdateAgentStatusTriggersSort:
    """Tests for update_agent_status triggering bubbling sort."""

    def test_update_agent_status_method_exists(self):
        """Test update_agent_status method exists on VirtualizedAgentList."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList
        
        agent_list = VirtualizedAgentList()
        assert hasattr(agent_list, "update_agent_status")
        assert callable(agent_list.update_agent_status)

    def test_update_agent_status_nonexistent_agent(self):
        """Test update_agent_status does nothing for nonexistent agent."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentStatus
        
        agent_list = VirtualizedAgentList()
        # Should not raise any error
        agent_list.update_agent_status("nonexistent-agent", AgentStatus.ERROR)

    def test_update_agent_status_triggers_bubbling(self):
        """Test update_agent_status triggers bubbling when attention state detected."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE))
        agent_list.add_agent(AgentRow(agent_id="agent-0002", status=AgentStatus.ACTIVE))
        agent_list.add_agent(AgentRow(agent_id="agent-0003", status=AgentStatus.ACTIVE))
        
        # Update agent-0003 to ERROR
        agent_list.update_agent_status("agent-0003", AgentStatus.ERROR)
        
        agents = list(agent_list.agents)
        assert agents[0].agent_id == "agent-0003"  # Should bubble to top

    def test_update_agent_status_resets_attention_dismissed(self):
        """Test update_agent_status resets attention_dismissed for new attention state."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        error_agent = AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR)
        agent_list.add_agent(error_agent)
        
        # Dismiss attention
        agent_list.get_agent("agent-0001").dismiss_attention()
        assert agent_list.get_agent("agent-0001").attention_dismissed is True
        
        # Update to new attention state
        agent_list.update_agent_status("agent-0001", AgentStatus.CRITICAL_FINDING)
        
        # attention_dismissed should be reset
        assert agent_list.get_agent("agent-0001").attention_dismissed is False


class TestAttentionVisualIndicators:
    """Tests for attention visual indicators."""

    def test_attention_icons_defined(self):
        """Test attention icons are defined for each attention state."""
        from cyberred.tui.widgets.agent_list import _ATTENTION_ICONS, AgentStatus
        
        assert _ATTENTION_ICONS[AgentStatus.ERROR] == "⚠"
        assert _ATTENTION_ICONS[AgentStatus.AUTH_PENDING] == "🔐"
        assert _ATTENTION_ICONS[AgentStatus.CRITICAL_FINDING] == "🔴"
        assert _ATTENTION_ICONS[AgentStatus.STALLED] == "⏸"

    def test_attention_colors_defined(self):
        """Test attention colors are defined with distinct styling."""
        from cyberred.tui.widgets.agent_list import _ATTENTION_COLORS, AgentStatus
        
        assert _ATTENTION_COLORS[AgentStatus.ERROR] == "bright_red"
        assert _ATTENTION_COLORS[AgentStatus.AUTH_PENDING] == "yellow"
        assert _ATTENTION_COLORS[AgentStatus.CRITICAL_FINDING] == "magenta"
        assert _ATTENTION_COLORS[AgentStatus.STALLED] == "orange3"

    def test_format_agent_row_uses_attention_styling(self):
        """Test format_agent_row uses attention styling when requires_attention is True."""
        from cyberred.tui.widgets.agent_list import (
            format_agent_row, AgentRow, AgentStatus
        )
        
        row = AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR)
        formatted = format_agent_row(row)
        
        # Should use bright_red and bold for attention
        assert "[bold bright_red]" in formatted or "bright_red" in formatted

    def test_format_agent_row_attention_icon(self):
        """Test format_agent_row includes attention icon for attention states."""
        from cyberred.tui.widgets.agent_list import (
            format_agent_row, AgentRow, AgentStatus
        )
        
        row = AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR)
        formatted = format_agent_row(row)
        
        # Should include the attention icon
        assert "⚠" in formatted


class TestDismissalMethods:
    """Tests for attention dismissal methods."""

    def test_dismiss_agent_attention_method(self):
        """Test dismiss_agent_attention method exists and works."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR))
        
        agent_list.dismiss_agent_attention("agent-0001")
        
        agent = agent_list.get_agent("agent-0001")
        assert agent.attention_dismissed is True

    def test_dismiss_agent_attention_triggers_resort(self):
        """Test dismiss_agent_attention triggers re-sort to move agent back."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE))
        agent_list.add_agent(AgentRow(agent_id="agent-0002", status=AgentStatus.ERROR))
        
        # ERROR should be at top after adding
        agent_list._sort_with_bubbling()
        agents = list(agent_list.agents)
        assert agents[0].agent_id == "agent-0002"
        
        # Dismiss attention
        agent_list.dismiss_agent_attention("agent-0002")
        
        # Should be back in original position
        agents = list(agent_list.agents)
        assert agents[0].agent_id == "agent-0001"
        assert agents[1].agent_id == "agent-0002"

    def test_dismiss_all_attention_method(self):
        """Test dismiss_all_attention clears all attention states."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR))
        agent_list.add_agent(AgentRow(agent_id="agent-0002", status=AgentStatus.AUTH_PENDING))
        agent_list.add_agent(AgentRow(agent_id="agent-0003", status=AgentStatus.CRITICAL_FINDING))
        
        agent_list.dismiss_all_attention()
        
        for agent in agent_list.agents:
            assert agent.attention_dismissed is True

    def test_dismiss_nonexistent_agent_no_error(self):
        """Test dismissing attention for non-existent agent doesn't raise error."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList
        
        agent_list = VirtualizedAgentList()
        
        # Should not raise any error
        agent_list.dismiss_agent_attention("nonexistent-agent")


class TestBubblingAnimation:
    """Tests for smooth bubbling animation."""

    def test_bubbling_enabled_property_default_true(self):
        """Test bubbling_enabled property defaults to True."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList
        
        agent_list = VirtualizedAgentList()
        assert agent_list.bubbling_enabled is True

    def test_bubbling_enabled_can_be_toggled(self):
        """Test bubbling_enabled can be toggled off."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList
        
        agent_list = VirtualizedAgentList()
        agent_list.bubbling_enabled = False
        assert agent_list.bubbling_enabled is False

    def test_animate_bubble_method_exists(self):
        """Test _animate_bubble method exists."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList
        
        agent_list = VirtualizedAgentList()
        assert hasattr(agent_list, "_animate_bubble")

    @pytest.mark.asyncio
    async def test_animate_bubble_skips_when_disabled(self):
        """Test _animate_bubble does nothing when bubbling_enabled is False."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        agent_list.bubbling_enabled = False
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR))
        
        # Should complete immediately without animation
        await agent_list._animate_bubble("agent-0001", 5, 0)
        # No exception means success

    @pytest.mark.asyncio
    async def test_animate_bubble_executes_animation_loop(self):
        """Test _animate_bubble executes the full animation loop when enabled."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        agent_list.bubbling_enabled = True
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR))
        
        # Run animation - this will execute the full loop
        await agent_list._animate_bubble("agent-0001", 5, 0)
        
        # After animation, task should be cleaned up
        assert "agent-0001" not in agent_list._animation_tasks

    @pytest.mark.asyncio
    async def test_animate_bubble_handles_rapid_changes(self):
        """Test _animate_bubble handles rapid state changes gracefully."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR))
        
        # Start multiple animations rapidly
        tasks = [
            agent_list._animate_bubble("agent-0001", 5, 0),
            agent_list._animate_bubble("agent-0001", 0, 3),
            agent_list._animate_bubble("agent-0001", 3, 1),
        ]
        
        # All should complete without error
        await asyncio.gather(*tasks)

    @pytest.mark.asyncio
    async def test_animate_bubble_cancellation(self):
        """Test _animate_bubble handles cancellation properly."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        agent_list.bubbling_enabled = True
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR))
        
        # Create a task for animation
        task = asyncio.create_task(agent_list._animate_bubble("agent-0001", 10, 0))
        
        # Wait a tiny bit then cancel
        await asyncio.sleep(0.01)
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected
        
        # Task should be cleaned up from animation_tasks
        # Note: cleanup happens in finally block

    @pytest.mark.asyncio
    async def test_animate_bubble_cancels_existing_task(self):
        """Test _animate_bubble cancels existing task for same agent."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        agent_list.bubbling_enabled = True
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR))
        
        # Create a mock task that simulates a running animation
        async def long_animation():
            await asyncio.sleep(10)  # Long sleep
        
        running_task = asyncio.create_task(long_animation())
        agent_list._animation_tasks["agent-0001"] = running_task
        
        # Give it a moment to start
        await asyncio.sleep(0.001)
        
        # Start second animation - should cancel the first one
        # Run with short timeout since the new animation will also run
        try:
            await asyncio.wait_for(
                agent_list._animate_bubble("agent-0001", 0, 5),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            pass
        
        # First task should be cancelled
        assert running_task.cancelled() or running_task.done()

    @pytest.mark.asyncio
    async def test_animate_bubble_skips_cancel_for_done_task(self):
        """Test _animate_bubble skips cancel for already done task."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        agent_list.bubbling_enabled = True
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR))
        
        # Create a task that completes immediately
        async def quick_animation():
            pass
        
        done_task = asyncio.create_task(quick_animation())
        await done_task  # Wait for it to complete
        
        # Store the done task in animation_tasks
        agent_list._animation_tasks["agent-0001"] = done_task
        
        # Verify the task is done
        assert done_task.done()
        
        # Start new animation - should skip cancel since task is done
        await agent_list._animate_bubble("agent-0001", 0, 5)
        
        # Should complete without errors
        assert "agent-0001" not in agent_list._animation_tasks


class TestAddAgentTriggersSort:
    """Tests for add_agent triggering bubbling on attention state."""

    def test_add_agent_with_attention_triggers_sort(self):
        """Test adding agent with attention status triggers bubbling sort."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE))
        agent_list.add_agent(AgentRow(agent_id="agent-0002", status=AgentStatus.ACTIVE))
        
        # Add agent with ERROR - should bubble to top
        agent_list.add_agent(AgentRow(agent_id="agent-0003", status=AgentStatus.ERROR))
        
        agents = list(agent_list.agents)
        assert agents[0].agent_id == "agent-0003"

    def test_add_agent_duplicate_id_updates_existing(self):
        """Test adding agent with duplicate ID updates the existing agent."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(
            agent_id="agent-0001",
            status=AgentStatus.IDLE,
            target="original_target"
        ))
        
        assert agent_list.agent_count == 1
        
        # Add another agent with same ID but different data
        agent_list.add_agent(AgentRow(
            agent_id="agent-0001",
            status=AgentStatus.ACTIVE,
            target="new_target"
        ))
        
        # Should still be 1 agent (updated, not duplicated)
        assert agent_list.agent_count == 1
        
        agent = agent_list.get_agent("agent-0001")
        assert agent.status == AgentStatus.ACTIVE
        assert agent.target == "new_target"


class TestAgentRowDunderMethods:
    """Tests for AgentRow __eq__, __repr__, __hash__ methods."""

    def test_agent_row_repr(self):
        """Test AgentRow __repr__ returns proper string representation."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row = AgentRow(
            agent_id="agent-0001",
            status=AgentStatus.ERROR,
            target="192.168.1.1",
            last_action="nmap scan"
        )
        repr_str = repr(row)
        
        assert "AgentRow" in repr_str
        assert "agent-0001" in repr_str
        assert "AgentStatus.ERROR" in repr_str
        assert "192.168.1.1" in repr_str
        assert "nmap scan" in repr_str

    def test_agent_row_hash(self):
        """Test AgentRow __hash__ returns consistent hash based on agent_id."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row1 = AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR)
        row2 = AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE)  # Same ID, different status
        row3 = AgentRow(agent_id="agent-0002", status=AgentStatus.ERROR)  # Different ID
        
        # Same agent_id should have same hash (for row recycling)
        assert hash(row1) == hash(row2)
        # Different agent_id should have different hash
        assert hash(row1) != hash(row3)
        
        # Hash should be stable
        assert hash(row1) == hash(row1)
        
        # Can be used as dict key
        agent_dict = {row1: "first"}
        assert row1 in agent_dict

    def test_agent_row_eq_with_non_agent_row(self):
        """Test AgentRow __eq__ returns NotImplemented for non-AgentRow types."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row = AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR)
        
        # Comparing with non-AgentRow should return NotImplemented
        result = row.__eq__("not an agent row")
        assert result is NotImplemented
        
        result = row.__eq__(123)
        assert result is NotImplemented
        
        result = row.__eq__(None)
        assert result is NotImplemented


class TestFormatAgentRowEdgeCases:
    """Tests for format_agent_row edge cases."""

    def test_format_agent_row_truncates_long_last_action(self):
        """Test format_agent_row truncates long last_action with ellipsis."""
        from cyberred.tui.widgets.agent_list import format_agent_row, AgentRow, AgentStatus
        
        # Create agent with very long last_action (> 42 chars)
        long_action = "A" * 100  # 100 characters
        row = AgentRow(
            agent_id="agent-0001",
            status=AgentStatus.ACTIVE,
            last_action=long_action
        )
        
        formatted = format_agent_row(row)
        
        # Should be truncated with ellipsis
        assert "..." in formatted
        # Should not contain the full 100 chars
        assert "A" * 100 not in formatted

    def test_format_agent_row_short_last_action_no_truncation(self):
        """Test format_agent_row does not truncate short last_action."""
        from cyberred.tui.widgets.agent_list import format_agent_row, AgentRow, AgentStatus
        
        short_action = "nmap scan"
        row = AgentRow(
            agent_id="agent-0001",
            status=AgentStatus.ACTIVE,
            last_action=short_action
        )
        
        formatted = format_agent_row(row)
        
        # Should contain the full action without ellipsis
        assert "nmap scan" in formatted
        # No truncation ellipsis for short strings
        assert "..." not in formatted or "nmap scan" in formatted


class TestVirtualizedAgentListProperties:
    """Tests for VirtualizedAgentList properties."""

    def test_agent_count_property(self):
        """Test agent_count property returns correct count."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        assert agent_list.agent_count == 0
        
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE))
        assert agent_list.agent_count == 1
        
        agent_list.add_agent(AgentRow(agent_id="agent-0002", status=AgentStatus.IDLE))
        assert agent_list.agent_count == 2

    def test_virtual_height_property(self):
        """Test virtual_height property returns correct height."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        assert agent_list.virtual_height == 0
        
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE))
        assert agent_list.virtual_height == 1  # ROW_HEIGHT = 1
        
        agent_list.add_agent(AgentRow(agent_id="agent-0002", status=AgentStatus.IDLE))
        assert agent_list.virtual_height == 2


class TestVirtualizedAgentListViewport:
    """Tests for VirtualizedAgentList viewport methods."""

    def test_get_visible_range_empty_list(self):
        """Test get_visible_range returns (0, 0) for empty list."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList
        
        agent_list = VirtualizedAgentList()
        assert agent_list.get_visible_range() == (0, 0)

    def test_get_visible_range_with_agents(self):
        """Test get_visible_range returns correct range based on viewport."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        for i in range(100):
            agent_list.add_agent(AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE))
        
        # Default viewport is 20
        start, end = agent_list.get_visible_range()
        assert start == 0
        assert end == 20

    def test_get_visible_range_with_scroll(self):
        """Test get_visible_range accounts for scroll position."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        for i in range(100):
            agent_list.add_agent(AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE))
        
        # Scroll down
        agent_list._scroll_y = 30
        start, end = agent_list.get_visible_range()
        assert start == 30
        assert end == 50  # 30 + 20 viewport

    def test_get_visible_agents(self):
        """Test get_visible_agents returns correct list of agents."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        for i in range(100):
            agent_list.add_agent(AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE))
        
        visible = agent_list.get_visible_agents()
        assert len(visible) == 20
        assert visible[0].agent_id == "agent-0000"
        assert visible[19].agent_id == "agent-0019"


class TestVirtualizedAgentListUpdateMethods:
    """Tests for VirtualizedAgentList update methods."""

    def test_update_agent_changes_fields(self):
        """Test update_agent correctly updates agent fields."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.IDLE))
        
        agent_list.update_agent(
            "agent-0001",
            status=AgentStatus.ACTIVE,
            target="192.168.1.1",
            last_action="scanning"
        )
        
        agent = agent_list.get_agent("agent-0001")
        assert agent.status == AgentStatus.ACTIVE
        assert agent.target == "192.168.1.1"
        assert agent.last_action == "scanning"

    def test_update_agent_nonexistent_does_nothing(self):
        """Test update_agent on non-existent agent does nothing."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentStatus
        
        agent_list = VirtualizedAgentList()
        # Should not raise an error
        agent_list.update_agent("nonexistent", status=AgentStatus.ERROR)

    def test_update_agent_partial_update(self):
        """Test update_agent with partial fields only updates specified."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(
            agent_id="agent-0001",
            status=AgentStatus.IDLE,
            target="original_target",
            last_action="original_action"
        ))
        
        # Only update status
        agent_list.update_agent("agent-0001", status=AgentStatus.ACTIVE)
        
        agent = agent_list.get_agent("agent-0001")
        assert agent.status == AgentStatus.ACTIVE
        assert agent.target == "original_target"  # Unchanged
        assert agent.last_action == "original_action"  # Unchanged

    def test_update_agent_only_target(self):
        """Test update_agent with only target updates just target."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(
            agent_id="agent-0001",
            status=AgentStatus.IDLE,
            target="original_target",
            last_action="original_action"
        ))
        
        # Only update target
        agent_list.update_agent("agent-0001", target="new_target")
        
        agent = agent_list.get_agent("agent-0001")
        assert agent.status == AgentStatus.IDLE  # Unchanged
        assert agent.target == "new_target"
        assert agent.last_action == "original_action"  # Unchanged

    def test_update_agent_only_last_action(self):
        """Test update_agent with only last_action updates just last_action."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(
            agent_id="agent-0001",
            status=AgentStatus.IDLE,
            target="original_target",
            last_action="original_action"
        ))
        
        # Only update last_action
        agent_list.update_agent("agent-0001", last_action="new_action")
        
        agent = agent_list.get_agent("agent-0001")
        assert agent.status == AgentStatus.IDLE  # Unchanged
        assert agent.target == "original_target"  # Unchanged
        assert agent.last_action == "new_action"

    def test_batch_update_multiple_agents(self):
        """Test batch_update updates multiple agents correctly."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.IDLE))
        agent_list.add_agent(AgentRow(agent_id="agent-0002", status=AgentStatus.IDLE))
        
        updates = [
            ("agent-0001", {"status": AgentStatus.ACTIVE, "target": "10.0.0.1"}),
            ("agent-0002", {"status": AgentStatus.ERROR, "last_action": "failed"}),
        ]
        
        agent_list.batch_update(updates)
        
        agent1 = agent_list.get_agent("agent-0001")
        assert agent1.status == AgentStatus.ACTIVE
        assert agent1.target == "10.0.0.1"
        
        agent2 = agent_list.get_agent("agent-0002")
        assert agent2.status == AgentStatus.ERROR
        assert agent2.last_action == "failed"


class TestVirtualizedAgentListRemoveClear:
    """Tests for VirtualizedAgentList remove and clear methods."""

    def test_remove_agent(self):
        """Test remove_agent removes agent from list."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.IDLE))
        agent_list.add_agent(AgentRow(agent_id="agent-0002", status=AgentStatus.IDLE))
        
        agent_list.remove_agent("agent-0001")
        
        assert agent_list.agent_count == 1
        assert agent_list.get_agent("agent-0001") is None
        assert agent_list.get_agent("agent-0002") is not None

    def test_remove_agent_nonexistent_does_nothing(self):
        """Test remove_agent on non-existent agent does nothing."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList
        
        agent_list = VirtualizedAgentList()
        # Should not raise an error
        agent_list.remove_agent("nonexistent")

    def test_clear_agents(self):
        """Test clear_agents removes all agents."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.IDLE))
        agent_list.add_agent(AgentRow(agent_id="agent-0002", status=AgentStatus.IDLE))
        
        agent_list.clear_agents()
        
        assert agent_list.agent_count == 0
        assert agent_list.get_agent("agent-0001") is None


class TestDismissAllAttentionEdgeCases:
    """Tests for dismiss_all_attention edge cases."""

    def test_dismiss_all_attention_empty_list(self):
        """Test dismiss_all_attention on empty list does nothing."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList
        
        agent_list = VirtualizedAgentList()
        # Should not raise an error
        agent_list.dismiss_all_attention()

    def test_dismiss_all_attention_no_attention_agents(self):
        """Test dismiss_all_attention when no agents require attention."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE))
        agent_list.add_agent(AgentRow(agent_id="agent-0002", status=AgentStatus.IDLE))
        
        # Should not raise an error and should not change anything
        agent_list.dismiss_all_attention()
        
        # Agents should still be in original order
        agents = list(agent_list.agents)
        assert agents[0].agent_id == "agent-0001"
        assert agents[1].agent_id == "agent-0002"


class TestPerformance:
    """Performance tests for bubbling sort at scale."""

    def test_sort_performance_10k_agents(self):
        """Test bubbling sort completes in <100ms for 10K agents (NFR4 requirement)."""
        import time
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        
        # Add 10K agents - use IDLE status to avoid triggering sort on each add
        for i in range(10000):
            agent_list.add_agent(
                AgentRow(agent_id=f"agent-{i:05d}", status=AgentStatus.IDLE)
            )
        
        # Now update one agent to ERROR to trigger bubbling
        agent_list.get_agent("agent-05000").status = AgentStatus.ERROR
        
        # Time the sort
        start = time.perf_counter()
        agent_list._sort_with_bubbling()
        elapsed = (time.perf_counter() - start) * 1000  # ms
        
        # Should complete in <100ms per NFR4 requirement
        assert elapsed < 100, f"Sort took {elapsed:.2f}ms, expected <100ms"
        
        # Verify error agent is at top
        agents = list(agent_list.agents)
        assert agents[0].agent_id == "agent-05000"
