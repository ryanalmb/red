"""Hive Matrix Agent Grid Widget.

Story 9.6: Hive Matrix Agent Grid

Implements a visual grid showing agent status and stigmergic connections:
- 10K+ agents displayed as grid cells with status-based colors
- Stigmergic connection visualization via grouping
- Zoom in/out capability (levels 1-5)
- Hover details for agent information
- Filter bar for state/target/kill-chain filtering
- Critical finding override: objective-relevant findings ignore filters

Performance: <100ms render at 10K scale per NFR4, O(1) cell lookup.
"""
from __future__ import annotations

import fnmatch
import math
from typing import TYPE_CHECKING, ClassVar

from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from cyberred.tui.widgets.agent_list import (
    AgentRow,
    AgentStatus,
    AttentionPriority,
    get_attention_priority,
)

if TYPE_CHECKING:
    from textual.app import ComposeResult


# Status color mapping per UX spec (active=green, idle=blue, error=red)
STATUS_COLORS: dict[AgentStatus, str] = {
    AgentStatus.ACTIVE: "green",
    AgentStatus.IDLE: "blue",
    AgentStatus.ERROR: "red",
    AgentStatus.AUTH_PENDING: "yellow",
    AgentStatus.STALLED: "orange",
    AgentStatus.CRITICAL_FINDING: "magenta",
}


class HiveCell(Static):
    """Individual cell in the Hive Matrix representing one agent.
    
    Displays a colored block based on agent status.
    """
    
    agent: reactive[AgentRow | None] = reactive(None)
    
    DEFAULT_CSS: ClassVar[str] = """
    HiveCell {
        width: 1;
        height: 1;
        content-align: center middle;
    }
    """
    
    def __init__(
        self,
        agent: AgentRow | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize HiveCell.
        
        Args:
            agent: Agent data to display in this cell.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.agent = agent
    
    def render(self) -> str:
        """Render cell as colored block."""
        if self.agent is None:
            return "░"  # Empty cell
        return "█"  # Filled cell, color via CSS class
    
    def watch_agent(self, agent: AgentRow | None) -> None:
        """Update CSS class when agent changes."""
        # Remove old status classes
        for status in AgentStatus:
            self.remove_class(f"hive-cell-{status.value}")
        
        if agent:
            self.add_class(f"hive-cell-{agent.status.value}")


class HiveTooltip(Static):
    """Tooltip widget displaying agent details on hover.
    
    Displays: agent_id, status (with icon), target, last_action (truncated).
    """
    
    DEFAULT_CSS: ClassVar[str] = """
    HiveTooltip {
        layer: tooltip;
        background: $surface;
        border: solid $primary;
        padding: 1;
        width: auto;
        height: auto;
    }
    """
    
    def __init__(
        self,
        agent: AgentRow,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize HiveTooltip.
        
        Args:
            agent: Agent data to display in tooltip.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._agent = agent
    
    def _format_content(self) -> str:
        """Format tooltip content.
        
        Returns:
            Formatted string with agent details.
        """
        agent = self._agent
        color = STATUS_COLORS.get(agent.status, "white")
        
        # Truncate last_action if too long
        last_action = agent.last_action
        if len(last_action) > 30:
            last_action = last_action[:27] + "..."
        
        return (
            f"ID: {agent.agent_id}\n"
            f"Status: [{color}]{agent.status.value.upper()}[/{color}]\n"
            f"Target: {agent.target or 'N/A'}\n"
            f"Action: {last_action or 'N/A'}"
        )
    
    def render(self) -> str:
        """Render the tooltip content."""
        return self._format_content()


class HiveFilterBar(Static):
    """Filter bar for HiveMatrix with state/target/kill-chain filtering.
    
    Provides filter inputs for:
    - Status: ACTIVE, IDLE, ERROR, AUTH_PENDING, STALLED, CRITICAL_FINDING
    - Target: IP/hostname pattern matching
    - Kill chain phase: Recon, Exploit, Post-Ex, etc.
    """
    
    DEFAULT_CSS: ClassVar[str] = """
    HiveFilterBar {
        height: 3;
        background: $surface;
        border: solid $primary;
        padding: 0 1;
    }
    """
    
    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize HiveFilterBar.
        
        Args:
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._status_filter: AgentStatus | None = None
        self._target_pattern: str | None = None
        self._phase_filter: str | None = None
    
    def get_status_options(self) -> list[AgentStatus]:
        """Get available status filter options.
        
        Returns:
            List of all AgentStatus values.
        """
        return list(AgentStatus)
    
    def render(self) -> str:
        """Render filter bar content."""
        status_text = self._status_filter.value if self._status_filter else "All"
        target_text = self._target_pattern or "*"
        return f"Filter: [Status: {status_text}] [Target: {target_text}] | Press / to focus"


class HiveMatrix(Widget):
    """Visual grid showing agent status and stigmergic connections.
    
    Displays 10K+ agents as a grid with:
    - Status-based cell colors (active=green, idle=blue, error=red)
    - Stigmergic connection visualization via grouping
    - Zoom in/out capability (levels 1-5)
    - Hover details for agent information
    - Filter bar for state/target/kill-chain filtering
    
    Performance: <100ms render at 10K scale, O(1) cell lookup.
    """
    
    DEFAULT_CSS: ClassVar[str] = """
    HiveMatrix {
        layout: grid;
        grid-gutter: 0;
        padding: 0;
        height: 100%;
        width: 100%;
    }
    
    HiveMatrix > HiveCell {
        width: 1;
        height: 1;
    }
    
    /* Status color classes */
    .hive-cell-active { background: green; }
    .hive-cell-idle { background: blue; }
    .hive-cell-error { background: red; }
    .hive-cell-auth_pending { background: yellow; }
    .hive-cell-stalled { background: orange; }
    .hive-cell-critical_finding { background: magenta; }
    
    /* Stigmergic connection highlight */
    .hive-cell-connected { border: solid cyan; }
    """
    
    # Messages
    class AgentUpdated(Message):
        """Message sent when an agent is updated in the grid."""
        
        def __init__(self, agent: AgentRow) -> None:
            """Initialize AgentUpdated message.
            
            Args:
                agent: The updated agent data.
            """
            self.agent = agent
            super().__init__()
    
    class FilterChanged(Message):
        """Message sent when filters are changed."""
        
        def __init__(self, filters: dict) -> None:
            """Initialize FilterChanged message.
            
            Args:
                filters: Current filter settings.
            """
            self.filters = filters
            super().__init__()
    
    class ZoomChanged(Message):
        """Message sent when zoom level changes."""
        
        def __init__(self, old_level: int, new_level: int) -> None:
            """Initialize ZoomChanged message.
            
            Args:
                old_level: Previous zoom level.
                new_level: New zoom level.
            """
            self.old_level = old_level
            self.new_level = new_level
            super().__init__()
    
    def __init__(
        self,
        *,
        grid_size: int = 100,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize HiveMatrix.
        
        Args:
            grid_size: Maximum grid dimension (default 100 for 10K agents).
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._agents: dict[str, AgentRow] = {}
        self._cells: dict[str, HiveCell] = {}
        self._connections: dict[str, set[str]] = {}
        self._grid_size = grid_size
        self._zoom_level = 3  # Default middle zoom (1-5)
        self._hovered_agent: AgentRow | None = None
        self._filters: dict[str, object] = {}
    
    def _calculate_grid_dimensions(self, agent_count: int) -> tuple[int, int]:
        """Calculate grid width and height for given agent count.
        
        Uses square grid layout (sqrt-based) for efficient display.
        
        Args:
            agent_count: Number of agents to display.
            
        Returns:
            Tuple of (width, height) grid dimensions.
        """
        side = max(1, int(math.ceil(math.sqrt(agent_count))))
        return side, side
    
    @property
    def agent_count(self) -> int:
        """Total agents in grid."""
        return len(self._agents)
    
    @property
    def anomaly_count(self) -> int:
        """Agents with attention states (error, auth_pending, etc.)."""
        return sum(
            1 for agent in self._agents.values()
            if get_attention_priority(agent.status) != AttentionPriority.NONE
        )
    
    @property
    def zoom_level(self) -> int:
        """Current zoom level (1-5)."""
        return self._zoom_level
    
    @property
    def hidden_agent_count(self) -> int:
        """Number of agents hidden by current filters."""
        if not self._filters:
            return 0
        total = len(self._agents)
        visible = len(self.get_filtered_agents())
        return total - visible
    
    def update_agent(self, agent: AgentRow) -> None:
        """Update or add an agent in the grid.
        
        Args:
            agent: Agent data to add or update.
        """
        self._agents[agent.agent_id] = agent
        if agent.agent_id in self._cells:
            self._cells[agent.agent_id].agent = agent
        self.post_message(self.AgentUpdated(agent))
    
    def add_connection(self, agent_id_1: str, agent_id_2: str) -> None:
        """Add stigmergic connection between two agents.
        
        Connections are bidirectional - adding A→B also adds B→A.
        
        Args:
            agent_id_1: First agent ID.
            agent_id_2: Second agent ID.
        """
        if agent_id_1 not in self._connections:
            self._connections[agent_id_1] = set()
        if agent_id_2 not in self._connections:
            self._connections[agent_id_2] = set()
        self._connections[agent_id_1].add(agent_id_2)
        self._connections[agent_id_2].add(agent_id_1)
        
        # Update cell styling
        if agent_id_1 in self._cells:
            self._cells[agent_id_1].add_class("hive-cell-connected")
        if agent_id_2 in self._cells:
            self._cells[agent_id_2].add_class("hive-cell-connected")
    
    def remove_connection(self, agent_id_1: str, agent_id_2: str) -> None:
        """Remove stigmergic connection between two agents.
        
        Args:
            agent_id_1: First agent ID.
            agent_id_2: Second agent ID.
        """
        if agent_id_1 in self._connections:
            self._connections[agent_id_1].discard(agent_id_2)
            # Remove connected class if no more connections
            if not self._connections[agent_id_1] and agent_id_1 in self._cells:
                self._cells[agent_id_1].remove_class("hive-cell-connected")
        if agent_id_2 in self._connections:
            self._connections[agent_id_2].discard(agent_id_1)
            # Remove connected class if no more connections
            if not self._connections[agent_id_2] and agent_id_2 in self._cells:
                self._cells[agent_id_2].remove_class("hive-cell-connected")
    
    def zoom_in(self) -> None:
        """Increase zoom level (max 5)."""
        if self._zoom_level < 5:
            old_level = self._zoom_level
            self._zoom_level += 1
            self._apply_zoom()
            self.post_message(self.ZoomChanged(old_level, self._zoom_level))
    
    def zoom_out(self) -> None:
        """Decrease zoom level (min 1)."""
        if self._zoom_level > 1:
            old_level = self._zoom_level
            self._zoom_level -= 1
            self._apply_zoom()
            self.post_message(self.ZoomChanged(old_level, self._zoom_level))
    
    def _get_cell_size_for_zoom(self, zoom_level: int) -> int:
        """Get cell size for given zoom level.
        
        Zoom level 1: 1x1 cells (dense overview)
        Zoom level 3: 2x2 cells (medium detail)
        Zoom level 5: 3x3 cells (full detail)
        
        Args:
            zoom_level: Zoom level (1-5).
            
        Returns:
            Cell size in characters.
        """
        # Maps: 1→1, 2→1, 3→2, 4→2, 5→3
        return 1 + (zoom_level - 1) // 2
    
    def _apply_zoom(self) -> None:
        """Apply current zoom level to cell sizes."""
        cell_size = self._get_cell_size_for_zoom(self._zoom_level)
        for cell in self._cells.values():
            cell.styles.width = cell_size
            cell.styles.height = cell_size
    
    def set_filter(
        self,
        status: AgentStatus | None = None,
        target_pattern: str | None = None,
        phase: str | None = None,
    ) -> None:
        """Set filter criteria.
        
        Args:
            status: Filter by agent status.
            target_pattern: Filter by target pattern (glob-style).
            phase: Filter by kill chain phase.
        """
        if status is not None:
            self._filters["status"] = status
        if target_pattern is not None:
            self._filters["target_pattern"] = target_pattern
        if phase is not None:
            self._filters["phase"] = phase
        
        self.post_message(self.FilterChanged(self._filters.copy()))
    
    def clear_filters(self) -> None:
        """Clear all filters."""
        self._filters.clear()
        self.post_message(self.FilterChanged({}))
    
    def get_filtered_agents(self) -> list[AgentRow]:
        """Get agents matching current filters.
        
        Critical findings (CRITICAL_FINDING status) always pass filters
        per UX spec "critical finding override".
        
        Returns:
            List of agents matching filter criteria.
        """
        if not self._filters:
            return list(self._agents.values())
        
        result = []
        for agent in self._agents.values():
            # Critical finding override - always visible
            if agent.status == AgentStatus.CRITICAL_FINDING:
                result.append(agent)
                continue
            
            # Check status filter
            status_filter = self._filters.get("status")
            if status_filter is not None and agent.status != status_filter:
                continue
            
            # Check target pattern filter
            target_pattern = self._filters.get("target_pattern")
            if target_pattern is not None:
                # Agents with no target are excluded when filtering by target
                if agent.target is None or not fnmatch.fnmatch(agent.target, target_pattern):
                    continue
            
            # Check phase filter (placeholder - requires agent phase tracking)
            phase_filter = self._filters.get("phase")
            if phase_filter is not None:
                # Phase filtering would check agent.phase if available
                pass
            
            result.append(agent)
        
        return result
    
    def compose(self) -> "ComposeResult":
        """Compose the grid layout."""
        # Placeholder - cells are created dynamically as agents are added
        yield from []
