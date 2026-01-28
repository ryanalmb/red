"""Unit tests for VirtualizedAgentList widget.

Story 9.3: Virtualized Agent List (10K+ Scale)
Tests the virtualized list that can display 10,000+ agents with:
- O(1) visibility queries
- <100ms render time at 10K scale
- Smooth scrolling (60fps target)
"""
import pytest
from dataclasses import asdict
from unittest.mock import MagicMock, patch
import time


class TestAgentStatus:
    """Tests for AgentStatus enum."""

    def test_agent_status_enum_values(self):
        """Test AgentStatus enum has all required values."""
        from cyberred.tui.widgets.agent_list import AgentStatus
        
        assert AgentStatus.ACTIVE.value == "active"
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.ERROR.value == "error"
        assert AgentStatus.AUTH_PENDING.value == "auth_pending"
        assert AgentStatus.STALLED.value == "stalled"
        assert AgentStatus.CRITICAL_FINDING.value == "critical_finding"

    def test_agent_status_has_six_values(self):
        """Test AgentStatus enum has exactly 6 values per spec."""
        from cyberred.tui.widgets.agent_list import AgentStatus
        
        assert len(AgentStatus) == 6


class TestAgentRow:
    """Tests for AgentRow dataclass."""

    def test_agent_row_creation(self):
        """Test AgentRow dataclass can be created with required fields."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row = AgentRow(
            agent_id="agent-0001",
            status=AgentStatus.ACTIVE,
            target="192.168.1.100:443",
            last_action="nmap -sV completed (12 findings)",
        )
        
        assert row.agent_id == "agent-0001"
        assert row.status == AgentStatus.ACTIVE
        assert row.target == "192.168.1.100:443"
        assert row.last_action == "nmap -sV completed (12 findings)"

    def test_agent_row_has_slots(self):
        """Test AgentRow uses __slots__ for memory efficiency."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row = AgentRow(
            agent_id="agent-0001",
            status=AgentStatus.ACTIVE,
            target="192.168.1.100",
            last_action="scanning",
        )
        
        # __slots__ classes don't have __dict__
        assert hasattr(AgentRow, "__slots__")

    def test_agent_row_default_values(self):
        """Test AgentRow has sensible defaults."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row = AgentRow(agent_id="agent-0001")
        
        assert row.agent_id == "agent-0001"
        assert row.status == AgentStatus.IDLE
        assert row.target == ""
        assert row.last_action == ""

    def test_agent_row_equality(self):
        """Test AgentRow equality comparison."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row1 = AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE)
        row2 = AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE)
        row3 = AgentRow(agent_id="agent-0002", status=AgentStatus.ACTIVE)
        
        assert row1 == row2
        assert row1 != row3

    def test_agent_row_equality_with_non_agent_row(self):
        """Test AgentRow equality returns NotImplemented for non-AgentRow."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row = AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE)
        
        # Comparing with non-AgentRow should return NotImplemented
        # which Python interprets as not equal
        assert row != "not an agent row"
        assert row != 123
        assert row != {"agent_id": "agent-0001"}

    def test_agent_row_repr(self):
        """Test AgentRow __repr__ method."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row = AgentRow(
            agent_id="agent-0001",
            status=AgentStatus.ACTIVE,
            target="192.168.1.1",
            last_action="scanning",
        )
        
        repr_str = repr(row)
        assert "AgentRow" in repr_str
        assert "agent-0001" in repr_str
        assert "AgentStatus.ACTIVE" in repr_str
        assert "192.168.1.1" in repr_str
        assert "scanning" in repr_str

    def test_agent_row_hashable(self):
        """Test AgentRow can be hashed and used in sets."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus
        
        row1 = AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE)
        row2 = AgentRow(agent_id="agent-0002", status=AgentStatus.IDLE)
        row3 = AgentRow(agent_id="agent-0001", status=AgentStatus.ERROR)  # Same ID, different status
        
        # Should be hashable
        assert hash(row1) == hash(row1)
        assert hash(row1) != hash(row2)
        # Same agent_id should have same hash (for row recycling)
        assert hash(row1) == hash(row3)
        
        # Should work in sets
        agent_set = {row1, row2}
        assert len(agent_set) == 2


class TestStatusColorMapping:
    """Tests for status color mapping."""

    def test_get_status_color_active(self):
        """Test ACTIVE status returns green color."""
        from cyberred.tui.widgets.agent_list import AgentStatus, get_status_color
        
        assert get_status_color(AgentStatus.ACTIVE) == "green"

    def test_get_status_color_idle(self):
        """Test IDLE status returns blue color."""
        from cyberred.tui.widgets.agent_list import AgentStatus, get_status_color
        
        assert get_status_color(AgentStatus.IDLE) == "blue"

    def test_get_status_color_error(self):
        """Test ERROR status returns red color."""
        from cyberred.tui.widgets.agent_list import AgentStatus, get_status_color
        
        assert get_status_color(AgentStatus.ERROR) == "red"

    def test_get_status_color_auth_pending(self):
        """Test AUTH_PENDING status returns yellow color."""
        from cyberred.tui.widgets.agent_list import AgentStatus, get_status_color
        
        assert get_status_color(AgentStatus.AUTH_PENDING) == "yellow"

    def test_get_status_color_stalled(self):
        """Test STALLED status returns orange color."""
        from cyberred.tui.widgets.agent_list import AgentStatus, get_status_color
        
        assert get_status_color(AgentStatus.STALLED) == "orange"

    def test_get_status_color_critical_finding(self):
        """Test CRITICAL_FINDING status returns magenta color."""
        from cyberred.tui.widgets.agent_list import AgentStatus, get_status_color
        
        assert get_status_color(AgentStatus.CRITICAL_FINDING) == "magenta"


class TestStatusIconMapping:
    """Tests for status icon mapping."""

    def test_get_status_icon_active(self):
        """Test ACTIVE status returns filled circle icon."""
        from cyberred.tui.widgets.agent_list import AgentStatus, get_status_icon
        
        assert get_status_icon(AgentStatus.ACTIVE) == "●"

    def test_get_status_icon_idle(self):
        """Test IDLE status returns empty circle icon."""
        from cyberred.tui.widgets.agent_list import AgentStatus, get_status_icon
        
        assert get_status_icon(AgentStatus.IDLE) == "○"

    def test_get_status_icon_error(self):
        """Test ERROR status returns X icon."""
        from cyberred.tui.widgets.agent_list import AgentStatus, get_status_icon
        
        assert get_status_icon(AgentStatus.ERROR) == "✗"

    def test_get_status_icon_auth_pending(self):
        """Test AUTH_PENDING status returns warning icon."""
        from cyberred.tui.widgets.agent_list import AgentStatus, get_status_icon
        
        assert get_status_icon(AgentStatus.AUTH_PENDING) == "⚠"

    def test_get_status_icon_stalled(self):
        """Test STALLED status returns half-filled circle icon."""
        from cyberred.tui.widgets.agent_list import AgentStatus, get_status_icon
        
        assert get_status_icon(AgentStatus.STALLED) == "◐"

    def test_get_status_icon_critical_finding(self):
        """Test CRITICAL_FINDING status returns star icon."""
        from cyberred.tui.widgets.agent_list import AgentStatus, get_status_icon
        
        assert get_status_icon(AgentStatus.CRITICAL_FINDING) == "★"


class TestVirtualizedAgentListInit:
    """Tests for VirtualizedAgentList initialization."""

    def test_init_empty_list(self):
        """Test VirtualizedAgentList initialization with empty list."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList
        
        widget = VirtualizedAgentList()
        
        assert widget.agent_count == 0
        assert list(widget.agents) == []

    def test_init_with_agents(self):
        """Test VirtualizedAgentList initialization with agents."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.ACTIVE)
            for i in range(100)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        assert widget.agent_count == 100

    def test_init_with_10k_agents_data_structure_only(self):
        """Test VirtualizedAgentList can hold 10K agents in data structure."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(10_000)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        assert widget.agent_count == 10_000

    def test_row_height_constant(self):
        """Test ROW_HEIGHT constant is defined."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList
        
        assert VirtualizedAgentList.ROW_HEIGHT == 1


class TestVirtualizedAgentListVisibility:
    """Tests for visibility queries."""

    def test_get_visible_range_empty_list(self):
        """Test get_visible_range with empty list returns (0, 0)."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList
        
        widget = VirtualizedAgentList()
        # Simulate viewport
        widget._scroll_y = 0
        widget._viewport_height = 20
        
        start, end = widget.get_visible_range()
        
        assert start == 0
        assert end == 0

    def test_get_visible_range_partial_list(self):
        """Test get_visible_range with agents returns correct range."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(100)
        ]
        widget = VirtualizedAgentList(agents=agents)
        widget._scroll_y = 0
        widget._viewport_height = 20
        
        start, end = widget.get_visible_range()
        
        assert start == 0
        assert end == 20  # Only visible rows

    def test_get_visible_range_scrolled(self):
        """Test get_visible_range when scrolled returns correct range."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(100)
        ]
        widget = VirtualizedAgentList(agents=agents)
        widget._scroll_y = 50  # Scrolled to row 50
        widget._viewport_height = 20
        
        start, end = widget.get_visible_range()
        
        assert start == 50
        assert end == 70  # 50 + 20 visible rows

    def test_get_visible_range_near_end(self):
        """Test get_visible_range near end of list clamps correctly."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(100)
        ]
        widget = VirtualizedAgentList(agents=agents)
        widget._scroll_y = 90  # Near end
        widget._viewport_height = 20
        
        start, end = widget.get_visible_range()
        
        assert start == 90
        assert end == 100  # Clamped to max

    def test_get_visible_range_negative_scroll(self):
        """Test get_visible_range with negative scroll clamps to zero."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(100)
        ]
        widget = VirtualizedAgentList(agents=agents)
        widget._scroll_y = -10  # Negative scroll
        widget._viewport_height = 20
        
        start, end = widget.get_visible_range()
        
        assert start == 0  # Clamped to 0, not negative
        assert end == 20
        
        # Should return valid agents, not empty
        visible = widget.get_visible_agents()
        assert len(visible) == 20
        assert visible[0].agent_id == "agent-0000"

    def test_get_visible_agents_returns_subset(self):
        """Test get_visible_agents returns only visible AgentRow objects."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(100)
        ]
        widget = VirtualizedAgentList(agents=agents)
        widget._scroll_y = 10
        widget._viewport_height = 5
        
        visible = widget.get_visible_agents()
        
        assert len(visible) == 5
        assert visible[0].agent_id == "agent-0010"
        assert visible[-1].agent_id == "agent-0014"


class TestVirtualizedAgentListUpdate:
    """Tests for agent update methods."""

    def test_update_agent_status(self):
        """Test updating a single agent's status."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(10)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        widget.update_agent("agent-0005", status=AgentStatus.ACTIVE)
        
        assert widget.get_agent("agent-0005").status == AgentStatus.ACTIVE

    def test_update_agent_target(self):
        """Test updating a single agent's target."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(10)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        widget.update_agent("agent-0005", target="192.168.1.100:443")
        
        assert widget.get_agent("agent-0005").target == "192.168.1.100:443"

    def test_update_agent_last_action(self):
        """Test updating a single agent's last action."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(10)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        widget.update_agent("agent-0005", last_action="nmap completed")
        
        assert widget.get_agent("agent-0005").last_action == "nmap completed"

    def test_update_nonexistent_agent_no_error(self):
        """Test updating nonexistent agent doesn't raise error."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(10)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        # Should not raise
        widget.update_agent("agent-9999", status=AgentStatus.ACTIVE)

    def test_get_agent_returns_none_for_nonexistent(self):
        """Test get_agent returns None for nonexistent agent."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(10)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        assert widget.get_agent("agent-9999") is None


class TestBatchUpdates:
    """Tests for batch update processing."""

    def test_batch_update_single(self):
        """Test batch_update with single update."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(10)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        updates = [("agent-0005", {"status": AgentStatus.ACTIVE})]
        widget.batch_update(updates)
        
        assert widget.get_agent("agent-0005").status == AgentStatus.ACTIVE

    def test_batch_update_multiple(self):
        """Test batch_update with multiple updates."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(10)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        updates = [
            ("agent-0001", {"status": AgentStatus.ACTIVE}),
            ("agent-0002", {"status": AgentStatus.ERROR}),
            ("agent-0003", {"target": "10.0.0.1"}),
        ]
        widget.batch_update(updates)
        
        assert widget.get_agent("agent-0001").status == AgentStatus.ACTIVE
        assert widget.get_agent("agent-0002").status == AgentStatus.ERROR
        assert widget.get_agent("agent-0003").target == "10.0.0.1"

    def test_batch_update_empty_list(self):
        """Test batch_update with empty list does nothing."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(10)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        widget.batch_update([])
        
        # All agents should still be IDLE
        for i in range(10):
            assert widget.get_agent(f"agent-{i:04d}").status == AgentStatus.IDLE


class TestAgentListAgentManagement:
    """Tests for adding/removing agents."""

    def test_add_agent(self):
        """Test adding a new agent to the list."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        widget = VirtualizedAgentList()
        
        row = AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE)
        widget.add_agent(row)
        
        assert widget.agent_count == 1
        assert widget.get_agent("agent-0001") is not None

    def test_add_agent_duplicate_id_updates_existing(self):
        """Test adding agent with duplicate ID updates existing instead of adding."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        widget = VirtualizedAgentList()
        
        # Add initial agent
        row1 = AgentRow(agent_id="agent-0001", status=AgentStatus.ACTIVE, target="target1")
        widget.add_agent(row1)
        assert widget.agent_count == 1
        assert widget.get_agent("agent-0001").status == AgentStatus.ACTIVE
        
        # Add duplicate - should update, not add
        row2 = AgentRow(agent_id="agent-0001", status=AgentStatus.IDLE, target="target2")
        widget.add_agent(row2)
        
        # Count should still be 1, not 2
        assert widget.agent_count == 1
        # Should have updated values
        agent = widget.get_agent("agent-0001")
        assert agent.status == AgentStatus.IDLE
        assert agent.target == "target2"

    def test_remove_agent(self):
        """Test removing an agent from the list."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(10)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        widget.remove_agent("agent-0005")
        
        assert widget.agent_count == 9
        assert widget.get_agent("agent-0005") is None

    def test_remove_nonexistent_agent_no_error(self):
        """Test removing nonexistent agent doesn't raise error."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(10)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        # Should not raise
        widget.remove_agent("agent-9999")
        
        assert widget.agent_count == 10

    def test_clear_agents(self):
        """Test clearing all agents."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(100)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        widget.clear_agents()
        
        assert widget.agent_count == 0


class TestFormatAgentRow:
    """Tests for row formatting."""

    def test_format_agent_row_basic(self):
        """Test basic agent row formatting."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus, format_agent_row
        
        row = AgentRow(
            agent_id="agent-0001",
            status=AgentStatus.ACTIVE,
            target="192.168.1.100:443",
            last_action="nmap completed",
        )
        
        formatted = format_agent_row(row)
        
        assert "agent-0001" in formatted
        assert "ACTIVE" in formatted
        assert "192.168.1.100:443" in formatted
        assert "nmap completed" in formatted

    def test_format_agent_row_includes_icon(self):
        """Test formatted row includes status icon."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus, format_agent_row
        
        row = AgentRow(
            agent_id="agent-0001",
            status=AgentStatus.ACTIVE,
        )
        
        formatted = format_agent_row(row)
        
        assert "●" in formatted  # ACTIVE icon

    def test_format_agent_row_truncates_long_action(self):
        """Test formatted row truncates overly long last_action."""
        from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus, format_agent_row
        
        row = AgentRow(
            agent_id="agent-0001",
            status=AgentStatus.ACTIVE,
            target="192.168.1.100",
            last_action="x" * 100,  # Very long action
        )
        
        formatted = format_agent_row(row)
        
        # Should be truncated to ~40 chars for last_action column
        assert len(formatted) < 150  # Reasonable total length


class TestVirtualSize:
    """Tests for virtual size calculation."""

    def test_virtual_size_empty(self):
        """Test virtual_size with empty list."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList
        
        widget = VirtualizedAgentList()
        
        assert widget.virtual_height == 0

    def test_virtual_size_with_agents(self):
        """Test virtual_size with agents."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(100)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        # Each row is ROW_HEIGHT (1) line
        assert widget.virtual_height == 100

    def test_virtual_size_10k_agents(self):
        """Test virtual_size with 10K agents."""
        from cyberred.tui.widgets.agent_list import VirtualizedAgentList, AgentRow, AgentStatus
        
        agents = [
            AgentRow(agent_id=f"agent-{i:04d}", status=AgentStatus.IDLE)
            for i in range(10_000)
        ]
        widget = VirtualizedAgentList(agents=agents)
        
        assert widget.virtual_height == 10_000


class TestColumnHeaders:
    """Tests for column headers."""

    def test_column_headers_defined(self):
        """Test COLUMN_HEADERS constant is defined."""
        from cyberred.tui.widgets.agent_list import COLUMN_HEADERS
        
        assert "AGENT_ID" in COLUMN_HEADERS
        assert "STATUS" in COLUMN_HEADERS
        assert "TARGET" in COLUMN_HEADERS
        assert "LAST_ACTION" in COLUMN_HEADERS

    def test_column_widths_defined(self):
        """Test COLUMN_WIDTHS constant is defined with correct values per spec."""
        from cyberred.tui.widgets.agent_list import COLUMN_WIDTHS
        
        # Per spec: agent_id (8ch), status (12ch), target (20ch), last_action (40ch)
        assert COLUMN_WIDTHS["agent_id"] == 10  # 8 + padding
        assert COLUMN_WIDTHS["status"] == 14  # 12 + padding
        assert COLUMN_WIDTHS["target"] == 22  # 20 + padding
        assert COLUMN_WIDTHS["last_action"] == 42  # 40 + padding
