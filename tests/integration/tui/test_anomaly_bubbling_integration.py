"""Integration tests for Anomaly Bubbling feature.

Story 9.4: Anomaly Bubbling
Tests the bubbling mechanism that surfaces agents requiring attention to the top of the list.

These tests verify the full bubbling flow with real components.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch


class TestBubblingIntegration:
    """Integration tests for agent bubbling behavior."""

    def test_agent_error_bubbles_to_top_of_large_list(self):
        """Test agent with ERROR status bubbles to top of 1000-agent list."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        
        # Add 1000 agents with IDLE status
        for i in range(1000):
            agent_list.add_agent(
                AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            )
        
        # Update agent at position 500 to ERROR
        agent_list.update_agent_status("agent-0500", AgentStatus.ERROR)
        
        # Verify it bubbled to top
        agents = list(agent_list.agents)
        assert agents[0].agent_id == "agent-0500"
        assert agents[0].status == AgentStatus.ERROR

    def test_priority_ordering_multiple_attention_agents(self):
        """Test priority ordering with multiple attention agents."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        
        # Add agents in specific order
        agent_list.add_agent(AgentRow(agent_id="agent-active", status=AgentStatus.ACTIVE))
        agent_list.add_agent(AgentRow(agent_id="agent-stalled", status=AgentStatus.STALLED))
        agent_list.add_agent(AgentRow(agent_id="agent-error", status=AgentStatus.ERROR))
        agent_list.add_agent(AgentRow(agent_id="agent-critical", status=AgentStatus.CRITICAL_FINDING))
        agent_list.add_agent(AgentRow(agent_id="agent-auth", status=AgentStatus.AUTH_PENDING))
        agent_list.add_agent(AgentRow(agent_id="agent-idle", status=AgentStatus.IDLE))
        
        agents = list(agent_list.agents)
        
        # Verify priority order: ERROR > AUTH_PENDING > CRITICAL_FINDING > STALLED > others
        assert agents[0].agent_id == "agent-error"
        assert agents[1].agent_id == "agent-auth"
        assert agents[2].agent_id == "agent-critical"
        assert agents[3].agent_id == "agent-stalled"
        # Non-attention agents preserve insertion order
        assert agents[4].agent_id == "agent-active"
        assert agents[5].agent_id == "agent-idle"

    def test_dismiss_returns_agent_to_correct_position(self):
        """Test dismiss returns agent to correct original position."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        
        # Add agents
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE))
        agent_list.add_agent(AgentRow(agent_id="agent-0002", status=AgentStatus.ACTIVE))
        agent_list.add_agent(AgentRow(agent_id="agent-0003", status=AgentStatus.ACTIVE))
        
        # Update middle agent to ERROR - it should bubble to top
        agent_list.update_agent_status("agent-0002", AgentStatus.ERROR)
        agents = list(agent_list.agents)
        assert agents[0].agent_id == "agent-0002"
        
        # Dismiss attention - agent should return to original position (index 1)
        agent_list.dismiss_agent_attention("agent-0002")
        agents = list(agent_list.agents)
        assert agents[0].agent_id == "agent-0001"
        assert agents[1].agent_id == "agent-0002"
        assert agents[2].agent_id == "agent-0003"

    def test_rapid_status_changes_no_race_conditions(self):
        """Test rapid status changes don't cause race conditions."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        
        # Add agents
        for i in range(100):
            agent_list.add_agent(
                AgentRow(agent_id=f"agent-{i:03d}", status=AgentStatus.IDLE)
            )
        
        # Rapidly change statuses
        for i in range(100):
            status = AgentStatus.ERROR if i % 2 == 0 else AgentStatus.IDLE
            agent_list.update_agent_status(f"agent-{i:03d}", status)
        
        # Verify no exceptions and list is consistent
        agents = list(agent_list.agents)
        assert len(agents) == 100
        
        # All ERROR agents should be at the top
        error_agents = [a for a in agents if a.status == AgentStatus.ERROR]
        assert all(
            agents.index(ea) < len(error_agents) for ea in error_agents
        )

    def test_dismiss_all_attention_clears_all_bubbled(self):
        """Test dismiss_all_attention clears all bubbled agents."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        
        # Add agents with various attention states
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE))
        agent_list.add_agent(AgentRow(agent_id="agent-0002", status=AgentStatus.ERROR))
        agent_list.add_agent(AgentRow(agent_id="agent-0003", status=AgentStatus.AUTH_PENDING))
        agent_list.add_agent(AgentRow(agent_id="agent-0004", status=AgentStatus.CRITICAL_FINDING))
        agent_list.add_agent(AgentRow(agent_id="agent-0005", status=AgentStatus.IDLE))
        
        # Dismiss all attention
        agent_list.dismiss_all_attention()
        
        # All agents should now be in original insertion order
        agents = list(agent_list.agents)
        assert agents[0].agent_id == "agent-0001"
        assert agents[1].agent_id == "agent-0002"
        assert agents[2].agent_id == "agent-0003"
        assert agents[3].agent_id == "agent-0004"
        assert agents[4].agent_id == "agent-0005"

    def test_attention_visual_styling_in_format(self):
        """Test attention styling is applied in formatted output."""
        from cyberred.tui.widgets.agent_list import (
            format_agent_row, AgentRow, AgentStatus
        )
        
        # Agent with attention state
        error_agent = AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR)
        formatted = format_agent_row(error_agent)
        
        # Should have attention styling (bold and bright_red)
        assert "bright_red" in formatted
        assert "⚠" in formatted  # Attention icon
        
        # Agent without attention state
        active_agent = AgentRow(agent_id="agent-0002", status=AgentStatus.ACTIVE)
        formatted_active = format_agent_row(active_agent)
        
        # Should not have attention styling
        assert "bright_red" not in formatted_active

    def test_new_attention_state_resets_dismissed(self):
        """Test new attention state resets dismissed flag."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR))
        
        # Dismiss attention
        agent_list.dismiss_agent_attention("agent-0001")
        agent = agent_list.get_agent("agent-0001")
        assert agent.attention_dismissed is True
        
        # Change to new attention state
        agent_list.update_agent_status("agent-0001", AgentStatus.CRITICAL_FINDING)
        
        # Dismissed flag should be reset
        assert agent.attention_dismissed is False
        
        # Agent should be back at top
        agents = list(agent_list.agents)
        assert agents[0].agent_id == "agent-0001"


class TestBubblingAnimationIntegration:
    """Integration tests for bubbling animation."""

    @pytest.mark.asyncio
    async def test_animation_completes_without_errors(self):
        """Test animation completes without errors."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        agent_list.bubbling_enabled = True
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR))
        
        # Run animation
        await agent_list._animate_bubble("agent-0001", 10, 0)
        
        # Should complete without errors
        assert "agent-0001" not in agent_list._animation_tasks

    @pytest.mark.asyncio
    async def test_animation_disabled_completes_immediately(self):
        """Test animation disabled completes immediately."""
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        import time
        
        agent_list = VirtualizedAgentList()
        agent_list.bubbling_enabled = False
        agent_list.add_agent(AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR))
        
        # Run animation - should return immediately
        start = time.perf_counter()
        await agent_list._animate_bubble("agent-0001", 10, 0)
        elapsed = time.perf_counter() - start
        
        # Should be nearly instantaneous (< 10ms)
        assert elapsed < 0.01


class TestBubblingPerformanceIntegration:
    """Performance integration tests."""

    def test_bubbling_performance_with_many_attention_agents(self):
        """Test bubbling sort performance with many attention agents."""
        import time
        from cyberred.tui.widgets.agent_list import (
            VirtualizedAgentList, AgentRow, AgentStatus
        )
        
        agent_list = VirtualizedAgentList()
        
        # Add 5000 agents with mixed statuses
        statuses = [
            AgentStatus.IDLE,
            AgentStatus.ACTIVE,
            AgentStatus.ERROR,
            AgentStatus.AUTH_PENDING,
            AgentStatus.CRITICAL_FINDING,
            AgentStatus.STALLED,
        ]
        
        for i in range(5000):
            status = statuses[i % len(statuses)]
            agent_list.add_agent(
                AgentRow(agent_id=f"agent-{i:05d}", status=status)
            )
        
        # Time a manual re-sort
        start = time.perf_counter()
        agent_list._sort_with_bubbling()
        elapsed = (time.perf_counter() - start) * 1000
        
        # Should complete in <100ms
        assert elapsed < 100, f"Sort took {elapsed:.2f}ms"
        
        # Verify correct ordering - ERROR agents should be first
        agents = list(agent_list.agents)
        first_non_error = next(
            (i for i, a in enumerate(agents) if a.status != AgentStatus.ERROR),
            len(agents)
        )
        error_count = sum(1 for a in agents if a.status == AgentStatus.ERROR)
        assert first_non_error == error_count
