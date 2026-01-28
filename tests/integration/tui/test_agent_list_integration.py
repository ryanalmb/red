"""Integration tests for VirtualizedAgentList widget.

Story 9.3: Virtualized Agent List (10K+ Scale)

Tests actual production code with:
- 10K simulated agents
- Performance measurements (<100ms render, 60fps scroll)
- Memory usage bounds
- Real viewport visibility queries
"""
import pytest
import time
import sys
from typing import List

from cyberred.tui.widgets.agent_list import (
    VirtualizedAgentList,
    AgentRow,
    AgentStatus,
    format_agent_row,
    get_status_color,
    get_status_icon,
)


class TestVirtualizedAgentList10KScale:
    """Integration tests with 10K agents."""

    @pytest.fixture
    def agents_10k(self) -> List[AgentRow]:
        """Create 10,000 agents for testing."""
        return [
            AgentRow(
                agent_id=f"agent-{i:04d}",
                status=AgentStatus.IDLE,
                target=f"192.168.{i // 256}.{i % 256}:443",
                last_action=f"Scanning target {i}",
            )
            for i in range(10_000)
        ]

    def test_10k_agent_creation_time(self, agents_10k: List[AgentRow]):
        """Test 10K agents can be created in reasonable time."""
        start = time.perf_counter()
        widget = VirtualizedAgentList(agents=agents_10k)
        elapsed = time.perf_counter() - start
        
        assert widget.agent_count == 10_000
        # Should create in <1 second
        assert elapsed < 1.0, f"Creating 10K agents took {elapsed:.2f}s, expected <1s"

    def test_10k_visible_range_performance(self, agents_10k: List[AgentRow]):
        """Test visible range query is O(1) - <1ms for 10K agents."""
        widget = VirtualizedAgentList(agents=agents_10k)
        widget._scroll_y = 5000
        widget._viewport_height = 50
        
        start = time.perf_counter()
        for _ in range(1000):  # 1000 iterations to measure accurately
            start_idx, end_idx = widget.get_visible_range()
        elapsed = time.perf_counter() - start
        
        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 1.0, f"Visible range query took {avg_ms:.3f}ms, expected <1ms"
        assert start_idx == 5000
        assert end_idx == 5050

    def test_10k_get_visible_agents_performance(self, agents_10k: List[AgentRow]):
        """Test getting visible agents is fast at 10K scale."""
        widget = VirtualizedAgentList(agents=agents_10k)
        widget._scroll_y = 5000
        widget._viewport_height = 50
        
        start = time.perf_counter()
        for _ in range(100):
            visible = widget.get_visible_agents()
        elapsed = time.perf_counter() - start
        
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 10.0, f"Get visible agents took {avg_ms:.3f}ms, expected <10ms"
        assert len(visible) == 50

    def test_10k_update_agent_performance(self, agents_10k: List[AgentRow]):
        """Test updating single agent is O(1) at 10K scale."""
        widget = VirtualizedAgentList(agents=agents_10k)
        
        start = time.perf_counter()
        for i in range(1000):
            widget.update_agent(
                f"agent-{i:04d}",
                status=AgentStatus.ACTIVE,
                target=f"new-target-{i}",
            )
        elapsed = time.perf_counter() - start
        
        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 1.0, f"Update agent took {avg_ms:.3f}ms, expected <1ms"

    def test_10k_batch_update_performance(self, agents_10k: List[AgentRow]):
        """Test batch update of 100 agents is efficient."""
        widget = VirtualizedAgentList(agents=agents_10k)
        
        updates = [
            (f"agent-{i:04d}", {"status": AgentStatus.ACTIVE})
            for i in range(100)
        ]
        
        start = time.perf_counter()
        widget.batch_update(updates)
        elapsed = time.perf_counter() - start
        
        elapsed_ms = elapsed * 1000
        assert elapsed_ms < 50.0, f"Batch update 100 agents took {elapsed_ms:.2f}ms, expected <50ms"
        
        # Verify updates applied
        for i in range(100):
            assert widget.get_agent(f"agent-{i:04d}").status == AgentStatus.ACTIVE

    def test_10k_memory_usage_bounded(self, agents_10k: List[AgentRow]):
        """Test memory usage is bounded with 10K agents using __slots__."""
        widget = VirtualizedAgentList(agents=agents_10k)
        
        # Get approximate memory usage of the widget
        # Each AgentRow with __slots__ should be ~200 bytes (rough estimate)
        # 10K agents = ~2MB (acceptable)
        agent_size = sys.getsizeof(agents_10k[0])
        
        # __slots__ objects are smaller than dict-based objects
        # A dict-based object would be ~400+ bytes
        assert agent_size < 200, f"AgentRow size {agent_size} bytes, expected <200 with __slots__"

    def test_10k_scroll_simulation(self, agents_10k: List[AgentRow]):
        """Test simulated scroll through 10K agents."""
        widget = VirtualizedAgentList(agents=agents_10k)
        widget._viewport_height = 50
        
        # Simulate scrolling from top to bottom
        scroll_times = []
        for scroll_pos in range(0, 10_000, 100):
            start = time.perf_counter()
            widget._scroll_y = scroll_pos
            visible = widget.get_visible_agents()
            scroll_times.append(time.perf_counter() - start)
        
        avg_scroll_ms = (sum(scroll_times) / len(scroll_times)) * 1000
        max_scroll_ms = max(scroll_times) * 1000
        
        # Each scroll should be <16ms (60fps)
        assert avg_scroll_ms < 16.0, f"Avg scroll time {avg_scroll_ms:.2f}ms, expected <16ms"
        assert max_scroll_ms < 50.0, f"Max scroll time {max_scroll_ms:.2f}ms, expected <50ms"


class TestVirtualizedAgentListRealBehavior:
    """Integration tests for real behavior without mocks."""

    def test_agent_lifecycle(self):
        """Test full agent lifecycle: add, update, remove."""
        widget = VirtualizedAgentList()
        
        # Add agents
        for i in range(100):
            agent = AgentRow(
                agent_id=f"agent-{i:04d}",
                status=AgentStatus.IDLE,
            )
            widget.add_agent(agent)
        
        assert widget.agent_count == 100
        
        # Update some agents
        for i in range(50):
            widget.update_agent(
                f"agent-{i:04d}",
                status=AgentStatus.ACTIVE,
                target=f"target-{i}",
                last_action=f"action-{i}",
            )
        
        # Verify updates
        for i in range(50):
            agent = widget.get_agent(f"agent-{i:04d}")
            assert agent.status == AgentStatus.ACTIVE
            assert agent.target == f"target-{i}"
            assert agent.last_action == f"action-{i}"
        
        # Remove some agents
        for i in range(0, 100, 2):  # Remove even-numbered agents
            widget.remove_agent(f"agent-{i:04d}")
        
        assert widget.agent_count == 50
        
        # Verify odd-numbered agents still exist
        for i in range(1, 100, 2):
            assert widget.get_agent(f"agent-{i:04d}") is not None

    def test_visible_agents_after_removal(self):
        """Test visibility queries work correctly after agent removal."""
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(100)
        ]
        widget = VirtualizedAgentList(agents=agents)
        widget._scroll_y = 0
        widget._viewport_height = 20
        
        # Get initial visible agents
        visible = widget.get_visible_agents()
        assert len(visible) == 20
        assert visible[0].agent_id == "agent-0000"
        
        # Remove first 10 agents
        for i in range(10):
            widget.remove_agent(f"agent-{i:04d}")
        
        # Visible agents should now start from agent-0010
        visible = widget.get_visible_agents()
        assert len(visible) == 20
        assert visible[0].agent_id == "agent-0010"

    def test_format_all_status_types(self):
        """Test formatting works for all status types."""
        for status in AgentStatus:
            row = AgentRow(
                agent_id="agent-0001",
                status=status,
                target="192.168.1.1",
                last_action="test action",
            )
            
            formatted = format_agent_row(row)
            
            # Should contain the icon for this status
            icon = get_status_icon(status)
            assert icon in formatted
            
            # Should contain at least the start of the status text (may be truncated for long statuses)
            status_text = status.value.upper()
            # Check first 8 chars which won't be truncated
            assert status_text[:8] in formatted

    def test_concurrent_updates_consistency(self):
        """Test data consistency with rapid sequential updates."""
        widget = VirtualizedAgentList()
        
        # Add 1000 agents
        for i in range(1000):
            widget.add_agent(AgentRow(agent_id=f"agent-{i:04d}"))
        
        # Rapidly update all agents
        for i in range(1000):
            widget.update_agent(
                f"agent-{i:04d}",
                status=AgentStatus.ACTIVE,
                target=f"target-{i % 256}",
            )
        
        # Verify all updates applied correctly
        for i in range(1000):
            agent = widget.get_agent(f"agent-{i:04d}")
            assert agent is not None
            assert agent.status == AgentStatus.ACTIVE
            assert agent.target == f"target-{i % 256}"


class TestVirtualizedAgentListEdgeCases:
    """Integration tests for edge cases."""

    def test_empty_to_full_transition(self):
        """Test transitioning from empty to full list."""
        widget = VirtualizedAgentList()
        assert widget.agent_count == 0
        assert widget.virtual_height == 0
        
        # Add agents one by one
        for i in range(100):
            widget.add_agent(AgentRow(agent_id=f"agent-{i:04d}"))
            assert widget.agent_count == i + 1
            assert widget.virtual_height == i + 1

    def test_full_to_empty_transition(self):
        """Test transitioning from full to empty list."""
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}")
            for i in range(100)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        # Clear all agents
        widget.clear_agents()
        
        assert widget.agent_count == 0
        assert widget.virtual_height == 0
        assert widget.get_visible_range() == (0, 0)

    def test_viewport_larger_than_agent_count(self):
        """Test viewport larger than total agent count."""
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}")
            for i in range(10)
        ]
        widget = VirtualizedAgentList(agents=agents)
        widget._scroll_y = 0
        widget._viewport_height = 100  # Larger than agent count
        
        start, end = widget.get_visible_range()
        assert start == 0
        assert end == 10  # Should clamp to agent count

    def test_scroll_past_end(self):
        """Test scrolling past end of list."""
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}")
            for i in range(100)
        ]
        widget = VirtualizedAgentList(agents=agents)
        widget._scroll_y = 150  # Past end
        widget._viewport_height = 20
        
        start, end = widget.get_visible_range()
        # Should return range clamped to valid indices
        assert end <= 100

    def test_single_agent_list(self):
        """Test list with single agent."""
        agent = AgentRow(agent_id="single-agent", status=AgentStatus.ACTIVE)
        widget = VirtualizedAgentList(agents=[agent])
        
        assert widget.agent_count == 1
        assert widget.virtual_height == 1
        
        visible = widget.get_visible_agents()
        assert len(visible) == 1
        assert visible[0].agent_id == "single-agent"


class TestStatusDisplayIntegration:
    """Integration tests for status display."""

    def test_all_status_colors_are_valid(self):
        """Test all status colors are valid rich markup colors."""
        valid_colors = {"green", "blue", "red", "yellow", "orange", "magenta", "white"}
        
        for status in AgentStatus:
            color = get_status_color(status)
            assert color in valid_colors, f"Invalid color {color} for {status}"

    def test_all_status_icons_are_unicode(self):
        """Test all status icons are valid unicode characters."""
        for status in AgentStatus:
            icon = get_status_icon(status)
            assert len(icon) == 1, f"Icon for {status} should be single character"
            assert ord(icon) > 127, f"Icon for {status} should be unicode"

    def test_format_preserves_all_fields(self):
        """Test formatting preserves all agent information."""
        row = AgentRow(
            agent_id="agent-test",
            status=AgentStatus.ACTIVE,  # Use short status to avoid truncation issues
            target="critical-target",
            last_action="found critical vulnerability",
        )
        
        formatted = format_agent_row(row)
        
        assert "agent-test" in formatted
        assert "ACTIVE" in formatted
        assert "critical-target" in formatted
        assert "found critical" in formatted  # May be truncated
