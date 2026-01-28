"""Unit Tests for HiveMatrix Widget.

Story 9.6: Hive Matrix Agent Grid

Tests cover:
- HiveMatrix initialization with default and custom grid sizes
- HiveCell color mapping for all AgentStatus values
- _calculate_grid_dimensions() for various agent counts
- add_connection() and remove_connection() for stigmergic tracking
- zoom_in() / zoom_out() boundary conditions
- _apply_zoom() cell size calculations
- Filter application with various criteria
- Agent/anomaly count calculations
"""
from __future__ import annotations

import math
import pytest

from cyberred.tui.widgets.agent_list import (
    AgentRow,
    AgentStatus,
    AttentionPriority,
    get_attention_priority,
)


class TestHiveMatrixImports:
    """Test that HiveMatrix can be imported."""

    def test_import_hive_matrix(self) -> None:
        """Test HiveMatrix can be imported from widgets module."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        assert HiveMatrix is not None

    def test_import_hive_cell(self) -> None:
        """Test HiveCell can be imported from widgets module."""
        from cyberred.tui.widgets.hive_matrix import HiveCell
        assert HiveCell is not None

    def test_import_hive_tooltip(self) -> None:
        """Test HiveTooltip can be imported from widgets module."""
        from cyberred.tui.widgets.hive_matrix import HiveTooltip
        assert HiveTooltip is not None

    def test_import_hive_filter_bar(self) -> None:
        """Test HiveFilterBar can be imported from widgets module."""
        from cyberred.tui.widgets.hive_matrix import HiveFilterBar
        assert HiveFilterBar is not None


class TestHiveMatrixInitialization:
    """Test HiveMatrix initialization."""

    def test_default_initialization(self) -> None:
        """Test HiveMatrix initializes with default values."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        assert matrix._grid_size == 100
        assert matrix._zoom_level == 3  # Default middle zoom
        assert matrix._agents == {}
        assert matrix._cells == {}
        assert matrix._connections == {}

    def test_custom_grid_size(self) -> None:
        """Test HiveMatrix initializes with custom grid size."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix(grid_size=50)
        
        assert matrix._grid_size == 50

    def test_custom_name_id_classes(self) -> None:
        """Test HiveMatrix initializes with custom name, id, classes."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix(name="test-matrix", id="hive-1", classes="custom-class")
        
        assert matrix.name == "test-matrix"
        assert matrix.id == "hive-1"


class TestGridDimensionCalculation:
    """Test _calculate_grid_dimensions() for various agent counts."""

    def test_100_agents(self) -> None:
        """Test grid dimensions for 100 agents (10x10)."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        width, height = matrix._calculate_grid_dimensions(100)
        assert width == 10
        assert height == 10

    def test_1000_agents(self) -> None:
        """Test grid dimensions for 1000 agents (~32x32)."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        width, height = matrix._calculate_grid_dimensions(1000)
        assert width == 32
        assert height == 32
        assert width * height >= 1000

    def test_10000_agents(self) -> None:
        """Test grid dimensions for 10000 agents (100x100)."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        width, height = matrix._calculate_grid_dimensions(10000)
        assert width == 100
        assert height == 100

    def test_zero_agents(self) -> None:
        """Test grid dimensions for 0 agents."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        width, height = matrix._calculate_grid_dimensions(0)
        assert width >= 1
        assert height >= 1

    def test_single_agent(self) -> None:
        """Test grid dimensions for 1 agent."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        width, height = matrix._calculate_grid_dimensions(1)
        assert width == 1
        assert height == 1


class TestAgentManagement:
    """Test agent add/update/remove operations."""

    def test_update_agent_adds_new(self) -> None:
        """Test update_agent adds new agent to grid."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        agent = AgentRow(agent_id="agent-001", status=AgentStatus.ACTIVE)
        matrix.update_agent(agent)
        
        assert "agent-001" in matrix._agents
        assert matrix._agents["agent-001"] == agent

    def test_update_agent_updates_existing(self) -> None:
        """Test update_agent updates existing agent."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        agent1 = AgentRow(agent_id="agent-001", status=AgentStatus.IDLE)
        matrix.update_agent(agent1)
        
        agent2 = AgentRow(agent_id="agent-001", status=AgentStatus.ACTIVE, target="192.168.1.1")
        matrix.update_agent(agent2)
        
        assert matrix._agents["agent-001"].status == AgentStatus.ACTIVE
        assert matrix._agents["agent-001"].target == "192.168.1.1"

    def test_agent_count_property(self) -> None:
        """Test agent_count property returns total agents."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        assert matrix.agent_count == 0
        
        for i in range(5):
            matrix.update_agent(AgentRow(agent_id=f"agent-{i:03d}"))
        
        assert matrix.agent_count == 5

    def test_anomaly_count_property(self) -> None:
        """Test anomaly_count property returns agents with attention states."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        # Add normal agents
        matrix.update_agent(AgentRow(agent_id="agent-001", status=AgentStatus.ACTIVE))
        matrix.update_agent(AgentRow(agent_id="agent-002", status=AgentStatus.IDLE))
        
        # Add anomaly agents
        matrix.update_agent(AgentRow(agent_id="agent-003", status=AgentStatus.ERROR))
        matrix.update_agent(AgentRow(agent_id="agent-004", status=AgentStatus.AUTH_PENDING))
        matrix.update_agent(AgentRow(agent_id="agent-005", status=AgentStatus.CRITICAL_FINDING))
        
        assert matrix.anomaly_count == 3


class TestStigmergicConnections:
    """Test stigmergic connection tracking."""

    def test_add_connection(self) -> None:
        """Test adding stigmergic connection between agents."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        matrix.add_connection("agent-001", "agent-002")
        
        assert "agent-002" in matrix._connections.get("agent-001", set())
        assert "agent-001" in matrix._connections.get("agent-002", set())

    def test_add_connection_bidirectional(self) -> None:
        """Test connections are bidirectional."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        matrix.add_connection("agent-001", "agent-002")
        
        # Should be accessible from both directions
        assert matrix._connections["agent-001"] == {"agent-002"}
        assert matrix._connections["agent-002"] == {"agent-001"}

    def test_add_multiple_connections(self) -> None:
        """Test agent can have multiple connections."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        matrix.add_connection("agent-001", "agent-002")
        matrix.add_connection("agent-001", "agent-003")
        
        assert matrix._connections["agent-001"] == {"agent-002", "agent-003"}

    def test_remove_connection(self) -> None:
        """Test removing stigmergic connection."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        matrix.add_connection("agent-001", "agent-002")
        matrix.remove_connection("agent-001", "agent-002")
        
        assert "agent-002" not in matrix._connections.get("agent-001", set())
        assert "agent-001" not in matrix._connections.get("agent-002", set())

    def test_remove_nonexistent_connection(self) -> None:
        """Test removing nonexistent connection doesn't raise."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        # Should not raise
        matrix.remove_connection("agent-001", "agent-002")

    def test_remove_connection_removes_css_class(self) -> None:
        """Test remove_connection removes hive-cell-connected CSS class."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix, HiveCell
        
        matrix = HiveMatrix()
        
        # Create cells
        cell1 = HiveCell()
        cell2 = HiveCell()
        matrix._cells["agent-001"] = cell1
        matrix._cells["agent-002"] = cell2
        
        # Add connection (adds CSS class)
        matrix.add_connection("agent-001", "agent-002")
        assert cell1.has_class("hive-cell-connected")
        assert cell2.has_class("hive-cell-connected")
        
        # Remove connection (should remove CSS class)
        matrix.remove_connection("agent-001", "agent-002")
        assert not cell1.has_class("hive-cell-connected")
        assert not cell2.has_class("hive-cell-connected")

    def test_remove_connection_keeps_css_if_other_connections_exist(self) -> None:
        """Test remove_connection keeps CSS class if agent has other connections."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix, HiveCell
        
        matrix = HiveMatrix()
        
        # Create cells
        cell1 = HiveCell()
        cell2 = HiveCell()
        cell3 = HiveCell()
        matrix._cells["agent-001"] = cell1
        matrix._cells["agent-002"] = cell2
        matrix._cells["agent-003"] = cell3
        
        # Add multiple connections to agent-001
        matrix.add_connection("agent-001", "agent-002")
        matrix.add_connection("agent-001", "agent-003")
        
        # Remove one connection
        matrix.remove_connection("agent-001", "agent-002")
        
        # agent-001 still has connection to agent-003, should keep CSS class
        assert cell1.has_class("hive-cell-connected")
        # agent-002 has no more connections, should lose CSS class
        assert not cell2.has_class("hive-cell-connected")
        # agent-003 still connected
        assert cell3.has_class("hive-cell-connected")


class TestZoomFunctionality:
    """Test zoom in/out functionality."""

    def test_default_zoom_level(self) -> None:
        """Test default zoom level is 3 (middle)."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        assert matrix._zoom_level == 3

    def test_zoom_in(self) -> None:
        """Test zoom_in increases zoom level."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        initial = matrix._zoom_level
        matrix.zoom_in()
        
        assert matrix._zoom_level == initial + 1

    def test_zoom_in_max_boundary(self) -> None:
        """Test zoom_in doesn't exceed max (5)."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        matrix._zoom_level = 5
        
        matrix.zoom_in()
        
        assert matrix._zoom_level == 5

    def test_zoom_out(self) -> None:
        """Test zoom_out decreases zoom level."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        initial = matrix._zoom_level
        matrix.zoom_out()
        
        assert matrix._zoom_level == initial - 1

    def test_zoom_out_min_boundary(self) -> None:
        """Test zoom_out doesn't go below min (1)."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        matrix._zoom_level = 1
        
        matrix.zoom_out()
        
        assert matrix._zoom_level == 1

    def test_zoom_level_property(self) -> None:
        """Test zoom_level property."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        assert matrix.zoom_level == 3
        matrix._zoom_level = 5
        assert matrix.zoom_level == 5


class TestCellSizeCalculation:
    """Test cell size calculations based on zoom level."""

    def test_zoom_level_1_cell_size(self) -> None:
        """Test zoom level 1 gives 1x1 cells."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        size = matrix._get_cell_size_for_zoom(1)
        assert size == 1

    def test_zoom_level_3_cell_size(self) -> None:
        """Test zoom level 3 gives 2x2 cells."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        size = matrix._get_cell_size_for_zoom(3)
        assert size == 2

    def test_zoom_level_5_cell_size(self) -> None:
        """Test zoom level 5 gives 3x3 cells."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        size = matrix._get_cell_size_for_zoom(5)
        assert size == 3


class TestHiveCellRendering:
    """Test HiveCell rendering and status colors."""

    def test_cell_status_color_active(self) -> None:
        """Test ACTIVE status renders green."""
        from cyberred.tui.widgets.hive_matrix import HiveCell, STATUS_COLORS
        assert STATUS_COLORS[AgentStatus.ACTIVE] == "green"

    def test_cell_status_color_idle(self) -> None:
        """Test IDLE status renders blue."""
        from cyberred.tui.widgets.hive_matrix import STATUS_COLORS
        assert STATUS_COLORS[AgentStatus.IDLE] == "blue"

    def test_cell_status_color_error(self) -> None:
        """Test ERROR status renders red."""
        from cyberred.tui.widgets.hive_matrix import STATUS_COLORS
        assert STATUS_COLORS[AgentStatus.ERROR] == "red"

    def test_cell_status_color_auth_pending(self) -> None:
        """Test AUTH_PENDING status renders yellow."""
        from cyberred.tui.widgets.hive_matrix import STATUS_COLORS
        assert STATUS_COLORS[AgentStatus.AUTH_PENDING] == "yellow"

    def test_cell_status_color_stalled(self) -> None:
        """Test STALLED status renders orange."""
        from cyberred.tui.widgets.hive_matrix import STATUS_COLORS
        assert STATUS_COLORS[AgentStatus.STALLED] == "orange"

    def test_cell_status_color_critical_finding(self) -> None:
        """Test CRITICAL_FINDING status renders magenta."""
        from cyberred.tui.widgets.hive_matrix import STATUS_COLORS
        assert STATUS_COLORS[AgentStatus.CRITICAL_FINDING] == "magenta"

    def test_all_statuses_have_colors(self) -> None:
        """Test all AgentStatus values have color mappings."""
        from cyberred.tui.widgets.hive_matrix import STATUS_COLORS
        for status in AgentStatus:
            assert status in STATUS_COLORS, f"Missing color for {status}"


class TestFilterFunctionality:
    """Test filter application."""

    def test_set_filter_by_status(self) -> None:
        """Test setting filter by status."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        matrix.set_filter(status=AgentStatus.ACTIVE)
        
        assert matrix._filters.get("status") == AgentStatus.ACTIVE

    def test_set_filter_by_target(self) -> None:
        """Test setting filter by target pattern."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        matrix.set_filter(target_pattern="192.168.*")
        
        assert matrix._filters.get("target_pattern") == "192.168.*"

    def test_clear_filters(self) -> None:
        """Test clearing all filters."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        matrix.set_filter(status=AgentStatus.ACTIVE)
        matrix.clear_filters()
        
        assert matrix._filters == {}

    def test_get_filtered_agents_by_status(self) -> None:
        """Test filtering agents by status."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        matrix.update_agent(AgentRow(agent_id="agent-001", status=AgentStatus.ACTIVE))
        matrix.update_agent(AgentRow(agent_id="agent-002", status=AgentStatus.IDLE))
        matrix.update_agent(AgentRow(agent_id="agent-003", status=AgentStatus.ACTIVE))
        
        matrix.set_filter(status=AgentStatus.ACTIVE)
        filtered = matrix.get_filtered_agents()
        
        assert len(filtered) == 2
        assert all(a.status == AgentStatus.ACTIVE for a in filtered)

    def test_get_filtered_agents_by_target(self) -> None:
        """Test filtering agents by target pattern."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        matrix.update_agent(AgentRow(agent_id="agent-001", target="192.168.1.1"))
        matrix.update_agent(AgentRow(agent_id="agent-002", target="10.0.0.1"))
        matrix.update_agent(AgentRow(agent_id="agent-003", target="192.168.1.2"))
        
        matrix.set_filter(target_pattern="192.168.*")
        filtered = matrix.get_filtered_agents()
        
        assert len(filtered) == 2

    def test_hidden_agent_count(self) -> None:
        """Test hidden_agent_count returns filtered out count."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        matrix.update_agent(AgentRow(agent_id="agent-001", status=AgentStatus.ACTIVE))
        matrix.update_agent(AgentRow(agent_id="agent-002", status=AgentStatus.IDLE))
        matrix.update_agent(AgentRow(agent_id="agent-003", status=AgentStatus.ACTIVE))
        
        matrix.set_filter(status=AgentStatus.ACTIVE)
        
        assert matrix.hidden_agent_count == 1

    def test_critical_finding_overrides_filter(self) -> None:
        """Test critical findings are always visible despite filters."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        matrix = HiveMatrix()
        
        matrix.update_agent(AgentRow(agent_id="agent-001", status=AgentStatus.ACTIVE))
        matrix.update_agent(AgentRow(agent_id="agent-002", status=AgentStatus.CRITICAL_FINDING))
        
        matrix.set_filter(status=AgentStatus.ACTIVE)
        filtered = matrix.get_filtered_agents()
        
        # Critical finding should still be visible
        agent_ids = [a.agent_id for a in filtered]
        assert "agent-002" in agent_ids


class TestHiveTooltip:
    """Test HiveTooltip widget."""

    def test_tooltip_displays_agent_info(self) -> None:
        """Test tooltip displays agent_id, status, target, last_action."""
        from cyberred.tui.widgets.hive_matrix import HiveTooltip
        
        agent = AgentRow(
            agent_id="agent-001",
            status=AgentStatus.ACTIVE,
            target="192.168.1.1:443",
            last_action="nmap -sV completed",
        )
        
        tooltip = HiveTooltip(agent=agent)
        
        assert tooltip._agent == agent

    def test_tooltip_format_content(self) -> None:
        """Test tooltip formats content correctly."""
        from cyberred.tui.widgets.hive_matrix import HiveTooltip
        
        agent = AgentRow(
            agent_id="agent-001",
            status=AgentStatus.ACTIVE,
            target="192.168.1.1:443",
            last_action="nmap -sV completed",
        )
        
        tooltip = HiveTooltip(agent=agent)
        content = tooltip._format_content()
        
        assert "agent-001" in content
        assert "ACTIVE" in content
        assert "192.168.1.1:443" in content
        assert "nmap" in content


class TestHiveFilterBar:
    """Test HiveFilterBar widget."""

    def test_filter_bar_initialization(self) -> None:
        """Test HiveFilterBar initializes correctly."""
        from cyberred.tui.widgets.hive_matrix import HiveFilterBar
        
        filter_bar = HiveFilterBar()
        assert filter_bar is not None

    def test_filter_bar_has_status_options(self) -> None:
        """Test filter bar includes all status options."""
        from cyberred.tui.widgets.hive_matrix import HiveFilterBar
        
        filter_bar = HiveFilterBar()
        statuses = filter_bar.get_status_options()
        
        for status in AgentStatus:
            assert status in statuses


class TestHiveMatrixMessages:
    """Test HiveMatrix message types."""

    def test_agent_updated_message(self) -> None:
        """Test AgentUpdated message carries agent data."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        
        agent = AgentRow(agent_id="agent-001", status=AgentStatus.ACTIVE)
        msg = HiveMatrix.AgentUpdated(agent)
        
        assert msg.agent == agent

    def test_filter_changed_message(self) -> None:
        """Test FilterChanged message carries filter data."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        
        filters = {"status": AgentStatus.ACTIVE}
        msg = HiveMatrix.FilterChanged(filters)
        
        assert msg.filters == filters

    def test_zoom_changed_message(self) -> None:
        """Test ZoomChanged message carries zoom level."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        
        msg = HiveMatrix.ZoomChanged(old_level=2, new_level=3)
        
        assert msg.old_level == 2
        assert msg.new_level == 3


class TestHiveCellWidget:
    """Test HiveCell widget rendering."""

    def test_cell_render_empty(self) -> None:
        """Test HiveCell renders empty cell when no agent."""
        from cyberred.tui.widgets.hive_matrix import HiveCell
        
        cell = HiveCell()
        assert cell.render() == "░"

    def test_cell_render_with_agent(self) -> None:
        """Test HiveCell renders filled cell when agent present."""
        from cyberred.tui.widgets.hive_matrix import HiveCell
        
        agent = AgentRow(agent_id="agent-001", status=AgentStatus.ACTIVE)
        cell = HiveCell(agent=agent)
        assert cell.render() == "█"

    def test_cell_watch_agent_adds_class(self) -> None:
        """Test HiveCell adds CSS class on agent change."""
        from cyberred.tui.widgets.hive_matrix import HiveCell
        
        cell = HiveCell()
        agent = AgentRow(agent_id="agent-001", status=AgentStatus.ACTIVE)
        cell.watch_agent(agent)
        
        assert cell.has_class("hive-cell-active")

    def test_cell_watch_agent_removes_old_class(self) -> None:
        """Test HiveCell removes old CSS class on status change."""
        from cyberred.tui.widgets.hive_matrix import HiveCell
        
        cell = HiveCell()
        agent1 = AgentRow(agent_id="agent-001", status=AgentStatus.ACTIVE)
        cell.watch_agent(agent1)
        
        agent2 = AgentRow(agent_id="agent-001", status=AgentStatus.IDLE)
        cell.watch_agent(agent2)
        
        assert not cell.has_class("hive-cell-active")
        assert cell.has_class("hive-cell-idle")

    def test_cell_watch_agent_none(self) -> None:
        """Test HiveCell handles None agent."""
        from cyberred.tui.widgets.hive_matrix import HiveCell
        
        cell = HiveCell()
        agent = AgentRow(agent_id="agent-001", status=AgentStatus.ACTIVE)
        cell.watch_agent(agent)
        cell.watch_agent(None)
        
        # Should have removed all status classes
        assert not cell.has_class("hive-cell-active")

    def test_cell_initialization_with_agent(self) -> None:
        """Test HiveCell initialization with agent parameter."""
        from cyberred.tui.widgets.hive_matrix import HiveCell
        
        agent = AgentRow(agent_id="agent-001", status=AgentStatus.ERROR)
        cell = HiveCell(agent=agent, id="cell-1", classes="test-class")
        
        assert cell.agent == agent
        assert cell.id == "cell-1"


class TestHiveTooltipWidget:
    """Test HiveTooltip widget rendering."""

    def test_tooltip_render(self) -> None:
        """Test HiveTooltip renders content."""
        from cyberred.tui.widgets.hive_matrix import HiveTooltip
        
        agent = AgentRow(
            agent_id="agent-001",
            status=AgentStatus.ACTIVE,
            target="192.168.1.1",
            last_action="scanning"
        )
        tooltip = HiveTooltip(agent=agent)
        content = tooltip.render()
        
        assert "agent-001" in content
        assert "ACTIVE" in content

    def test_tooltip_truncates_long_action(self) -> None:
        """Test HiveTooltip truncates long last_action."""
        from cyberred.tui.widgets.hive_matrix import HiveTooltip
        
        agent = AgentRow(
            agent_id="agent-001",
            status=AgentStatus.ACTIVE,
            target="192.168.1.1",
            last_action="a" * 50  # Very long action
        )
        tooltip = HiveTooltip(agent=agent)
        content = tooltip._format_content()
        
        assert "..." in content

    def test_tooltip_handles_empty_target(self) -> None:
        """Test HiveTooltip handles empty target."""
        from cyberred.tui.widgets.hive_matrix import HiveTooltip
        
        agent = AgentRow(agent_id="agent-001", status=AgentStatus.IDLE)
        tooltip = HiveTooltip(agent=agent)
        content = tooltip._format_content()
        
        assert "N/A" in content

    def test_tooltip_handles_empty_last_action(self) -> None:
        """Test HiveTooltip handles empty last_action."""
        from cyberred.tui.widgets.hive_matrix import HiveTooltip
        
        agent = AgentRow(agent_id="agent-001", status=AgentStatus.IDLE, target="10.0.0.1")
        tooltip = HiveTooltip(agent=agent)
        content = tooltip._format_content()
        
        # The Action line should show N/A for empty action
        assert "Action: N/A" in content


class TestHiveFilterBarWidget:
    """Test HiveFilterBar widget."""

    def test_filter_bar_render(self) -> None:
        """Test HiveFilterBar renders content."""
        from cyberred.tui.widgets.hive_matrix import HiveFilterBar
        
        filter_bar = HiveFilterBar()
        content = filter_bar.render()
        
        assert "Filter:" in content
        assert "Status:" in content


class TestHiveMatrixCompose:
    """Test HiveMatrix compose method."""

    def test_compose_yields_nothing_initially(self) -> None:
        """Test compose yields empty initially (cells created dynamically)."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        
        matrix = HiveMatrix()
        children = list(matrix.compose())
        
        assert children == []


class TestHiveMatrixApplyZoom:
    """Test HiveMatrix _apply_zoom method."""

    def test_apply_zoom_updates_cell_sizes(self) -> None:
        """Test _apply_zoom updates cell sizes."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix, HiveCell
        
        matrix = HiveMatrix()
        # Manually add a cell to test zoom
        cell = HiveCell()
        matrix._cells["agent-001"] = cell
        
        matrix._zoom_level = 5
        matrix._apply_zoom()
        
        # At zoom level 5, cell size should be 3
        # Textual styles.width/height return Scalar objects with .value
        assert cell.styles.width.value == 3
        assert cell.styles.height.value == 3


class TestHiveMatrixFilterPhase:
    """Test filter by phase functionality."""

    def test_filter_by_phase_set(self) -> None:
        """Test setting phase filter."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        
        matrix = HiveMatrix()
        matrix.set_filter(phase="recon")
        
        assert matrix._filters.get("phase") == "recon"

    def test_filter_by_phase_in_get_filtered(self) -> None:
        """Test phase filter is considered in get_filtered_agents."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        
        matrix = HiveMatrix()
        matrix.update_agent(AgentRow(agent_id="agent-001", status=AgentStatus.ACTIVE))
        matrix.set_filter(phase="recon")
        
        # Phase filtering is a placeholder - agents still pass
        filtered = matrix.get_filtered_agents()
        assert len(filtered) == 1


class TestHiveMatrixCellUpdates:
    """Test cell updates when agent is in _cells dict."""

    def test_update_agent_updates_existing_cell(self) -> None:
        """Test update_agent updates cell when it exists."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix, HiveCell
        
        matrix = HiveMatrix()
        
        # Add initial agent and cell
        agent1 = AgentRow(agent_id="agent-001", status=AgentStatus.IDLE)
        matrix.update_agent(agent1)
        
        # Manually register a cell
        cell = HiveCell(agent=agent1)
        matrix._cells["agent-001"] = cell
        
        # Update the agent
        agent2 = AgentRow(agent_id="agent-001", status=AgentStatus.ACTIVE, target="10.0.0.1")
        matrix.update_agent(agent2)
        
        # Cell should now have the updated agent
        assert matrix._cells["agent-001"].agent == agent2


class TestZoomLevelProperty:
    """Test zoom_level property edge cases."""

    def test_zoom_level_all_values(self) -> None:
        """Test _get_cell_size_for_zoom for all zoom levels."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        
        matrix = HiveMatrix()
        
        # Zoom 1 and 2 -> size 1
        assert matrix._get_cell_size_for_zoom(1) == 1
        assert matrix._get_cell_size_for_zoom(2) == 1
        
        # Zoom 3 and 4 -> size 2
        assert matrix._get_cell_size_for_zoom(3) == 2
        assert matrix._get_cell_size_for_zoom(4) == 2
        
        # Zoom 5 -> size 3
        assert matrix._get_cell_size_for_zoom(5) == 3


class TestHiddenAgentCount:
    """Test hidden_agent_count property."""

    def test_hidden_agent_count_no_filters(self) -> None:
        """Test hidden_agent_count returns 0 when no filters."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        
        matrix = HiveMatrix()
        matrix.update_agent(AgentRow(agent_id="agent-001", status=AgentStatus.ACTIVE))
        matrix.update_agent(AgentRow(agent_id="agent-002", status=AgentStatus.IDLE))
        
        # No filters set
        assert matrix.hidden_agent_count == 0


class TestConnectionWithCells:
    """Test add_connection when cells exist."""

    def test_add_connection_updates_cell_class(self) -> None:
        """Test add_connection adds CSS class to existing cells."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix, HiveCell
        
        matrix = HiveMatrix()
        
        # Create cells first
        cell1 = HiveCell()
        cell2 = HiveCell()
        matrix._cells["agent-001"] = cell1
        matrix._cells["agent-002"] = cell2
        
        # Add connection
        matrix.add_connection("agent-001", "agent-002")
        
        # Both cells should have connected class
        assert cell1.has_class("hive-cell-connected")
        assert cell2.has_class("hive-cell-connected")

    def test_add_connection_one_cell_exists(self) -> None:
        """Test add_connection when only one cell exists."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix, HiveCell
        
        matrix = HiveMatrix()
        
        # Only create one cell
        cell1 = HiveCell()
        matrix._cells["agent-001"] = cell1
        
        # Add connection - should not raise even if agent-002 has no cell
        matrix.add_connection("agent-001", "agent-002")
        
        # Only cell1 should have connected class
        assert cell1.has_class("hive-cell-connected")


class TestFilterTargetPatternMismatch:
    """Test filter when target doesn't match pattern."""

    def test_target_pattern_filters_non_matching(self) -> None:
        """Test that agents not matching target pattern are filtered."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        
        matrix = HiveMatrix()
        
        matrix.update_agent(AgentRow(agent_id="agent-001", target="192.168.1.1", status=AgentStatus.ACTIVE))
        matrix.update_agent(AgentRow(agent_id="agent-002", target="10.0.0.1", status=AgentStatus.ACTIVE))
        matrix.update_agent(AgentRow(agent_id="agent-003", target="", status=AgentStatus.ACTIVE))  # Empty target
        
        matrix.set_filter(target_pattern="192.168.*")
        filtered = matrix.get_filtered_agents()
        
        # Only agent-001 matches the pattern
        assert len(filtered) == 1
        assert filtered[0].agent_id == "agent-001"

    def test_target_pattern_filters_none_target(self) -> None:
        """Test that agents with None target are filtered when target pattern is set."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        
        matrix = HiveMatrix()
        
        matrix.update_agent(AgentRow(agent_id="agent-001", target="192.168.1.1", status=AgentStatus.ACTIVE))
        # AgentRow with no target specified - target will be empty string by default
        agent_no_target = AgentRow(agent_id="agent-002", status=AgentStatus.ACTIVE)
        agent_no_target.target = None  # Explicitly set to None
        matrix._agents["agent-002"] = agent_no_target
        
        matrix.set_filter(target_pattern="192.168.*")
        filtered = matrix.get_filtered_agents()
        
        # Only agent-001 matches (agent-002 with None target should be excluded)
        assert len(filtered) == 1
        assert filtered[0].agent_id == "agent-001"


class TestGetFilteredAgentsNoFilters:
    """Test get_filtered_agents with no filters."""

    def test_get_filtered_agents_returns_all_when_no_filters(self) -> None:
        """Test get_filtered_agents returns all agents when no filters set."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        
        matrix = HiveMatrix()
        matrix.update_agent(AgentRow(agent_id="agent-001", status=AgentStatus.ACTIVE))
        matrix.update_agent(AgentRow(agent_id="agent-002", status=AgentStatus.IDLE))
        matrix.update_agent(AgentRow(agent_id="agent-003", status=AgentStatus.ERROR))
        
        # No filters - should return all agents
        filtered = matrix.get_filtered_agents()
        assert len(filtered) == 3


class TestAddConnectionExistingConnection:
    """Test add_connection when connection dict already exists."""

    def test_add_connection_existing_connection_dict(self) -> None:
        """Test add_connection when agent already has connections."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        
        matrix = HiveMatrix()
        
        # First connection creates the dict entries
        matrix.add_connection("agent-001", "agent-002")
        
        # Second connection to agent-001 should reuse existing dict entry
        matrix.add_connection("agent-001", "agent-003")
        
        # agent-001 should have both connections
        assert matrix._connections["agent-001"] == {"agent-002", "agent-003"}
        # agent-002 and agent-003 each have connection to agent-001
        assert matrix._connections["agent-002"] == {"agent-001"}
        assert matrix._connections["agent-003"] == {"agent-001"}

    def test_add_connection_agent2_already_has_connections(self) -> None:
        """Test add_connection when agent_id_2 already has connection entries."""
        from cyberred.tui.widgets.hive_matrix import HiveMatrix
        
        matrix = HiveMatrix()
        
        # Create connection so agent-002 has an entry in _connections
        matrix.add_connection("agent-002", "agent-003")
        
        # Now add connection where agent-002 (as agent_id_2) already exists
        # This tests the branch at line 379 where agent_id_2 IS in _connections
        matrix.add_connection("agent-001", "agent-002")
        
        # Verify all connections are correct
        assert "agent-002" in matrix._connections["agent-001"]
        assert "agent-001" in matrix._connections["agent-002"]
        assert "agent-003" in matrix._connections["agent-002"]
