# Story 9.6: Hive Matrix Agent Grid

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **a visual grid showing agent status and stigmergic connections**,
so that **I can see swarm coordination at a glance (FR11)**.

## Acceptance Criteria

1. **Given** Story 9.3 is complete
   - **When** agents are active
   - **Then** Hive Matrix shows agents as grid cells

2. **Given** agents are displayed in the grid
   - **When** viewing the Hive Matrix
   - **Then** cell color indicates status: active=green, idle=blue, error=red

3. **Given** agents are coordinating
   - **When** stigmergic connections exist
   - **Then** stigmergic connections are visualized (lines or grouping)

4. **Given** the Hive Matrix is displayed
   - **When** I interact with the grid
   - **Then** I can zoom in/out on the matrix

5. **Given** an agent cell is visible
   - **When** I hover over a cell
   - **Then** hover shows agent details (agent_id, status, target, last_action)

6. **Given** the Hive Matrix implementation
   - **When** running integration tests
   - **Then** integration tests verify matrix rendering

## Tasks / Subtasks

- [x] **Task 1: Create HiveMatrix Widget Base** (AC: #1, #2)
  - [ ] 1.1: Create `src/cyberred/tui/widgets/hive_matrix.py` with `HiveMatrix` class extending `textual.widget.Widget`
  - [ ] 1.2: Add `__init__` with parameters: `grid_size: int = 100`, `cell_size: int = 1`, `name`, `id`, `classes`
  - [ ] 1.3: Add `_agents: dict[str, AgentRow]` to store agent data (reuse `AgentRow` from `agent_list.py`)
  - [ ] 1.4: Add `_grid_width: int`, `_grid_height: int` calculated from total agents (e.g., sqrt for square grid)
  - [ ] 1.5: Add `DEFAULT_CSS` class variable with grid layout styles
  - [ ] 1.6: Implement `compose()` returning grid container with cell placeholders

- [x] **Task 2: Implement Cell Rendering with Status Colors** (AC: #2)
  - [ ] 2.1: Create `HiveCell` inner class extending `textual.widget.Static` for individual cells
  - [ ] 2.2: Add `agent: AgentRow | None` attribute to HiveCell
  - [ ] 2.3: Implement `render()` returning colored block based on agent status
  - [ ] 2.4: Define color mapping per UX spec: `ACTIVE=green`, `IDLE=blue`, `ERROR=red`, `AUTH_PENDING=yellow`, `STALLED=orange`, `CRITICAL_FINDING=magenta`
  - [ ] 2.5: Add TCSS classes: `.hive-cell-active`, `.hive-cell-idle`, `.hive-cell-error`, etc.
  - [ ] 2.6: Implement `watch_agent()` reactive to update cell color on agent status change

- [x] **Task 3: Implement Grid Layout and Density View** (AC: #1)
  - [ ] 3.1: Implement `_calculate_grid_dimensions(agent_count: int) -> tuple[int, int]` for dynamic grid sizing
  - [ ] 3.2: For 10K agents, use 100x100 grid (per spec)
  - [ ] 3.3: Implement `_assign_cell_positions()` to map agents to grid coordinates
  - [ ] 3.4: Add `density_mode: bool` property for high-density visualization (1-char cells vs expanded)
  - [ ] 3.5: Implement grid reflow on terminal resize using `on_resize()` handler

- [x] **Task 4: Implement Stigmergic Connection Visualization** (AC: #3)
  - [ ] 4.1: Add `_connections: dict[str, set[str]]` to track stigmergic agent connections
  - [ ] 4.2: Create `add_connection(agent_id_1: str, agent_id_2: str)` method
  - [ ] 4.3: Create `remove_connection(agent_id_1: str, agent_id_2: str)` method
  - [ ] 4.4: Implement connection visualization via cell grouping (adjacent placement of connected agents)
  - [ ] 4.5: Add `_connection_groups: list[set[str]]` for cluster identification
  - [ ] 4.6: Apply visual indicator for connected groups (shared border color or subtle background tint)
  - [ ] 4.7: Add TCSS class `.hive-cell-connected` for stigmergic connection highlighting

- [x] **Task 5: Implement Zoom In/Out** (AC: #4)
  - [ ] 5.1: Add `_zoom_level: int` property with range 1-5 (1=most zoomed out, 5=most zoomed in)
  - [ ] 5.2: Implement `zoom_in()` method increasing `_zoom_level` (max 5)
  - [ ] 5.3: Implement `zoom_out()` method decreasing `_zoom_level` (min 1)
  - [ ] 5.4: Add keyboard bindings: `+` or `=` for zoom in, `-` for zoom out
  - [ ] 5.5: Implement `_apply_zoom()` adjusting cell size based on zoom level
  - [ ] 5.6: At zoom level 1: 1-char cells, dense overview
  - [ ] 5.7: At zoom level 5: 3x3 char cells with agent ID visible
  - [ ] 5.8: Add mouse wheel zoom support via `on_mouse_scroll_down/up()` handlers

- [x] **Task 6: Implement Hover Details** (AC: #5)
  - [ ] 6.1: Override `on_mouse_move(event: MouseMove)` to detect hovered cell
  - [ ] 6.2: Create `_hovered_agent: AgentRow | None` property
  - [ ] 6.3: Create `HiveTooltip` widget extending `textual.widget.Static` for tooltip display
  - [ ] 6.4: Tooltip displays: agent_id, status (with icon), target, last_action (truncated)
  - [ ] 6.5: Position tooltip near mouse cursor (offset to avoid overlap)
  - [ ] 6.6: Add `_tooltip_visible: bool` reactive property
  - [ ] 6.7: Implement tooltip auto-hide after mouse leaves cell (300ms delay)
  - [ ] 6.8: Add TCSS styling for tooltip: elevated background, border, shadow effect

- [x] **Task 7: Implement Filter Bar** (AC: #1, per UX spec)
  - [ ] 7.1: Create `HiveFilterBar` widget with filter inputs
  - [ ] 7.2: Add filter by state: dropdown/buttons for `ACTIVE`, `IDLE`, `ERROR`, `AUTH_PENDING`, etc.
  - [ ] 7.3: Add filter by target: text input for target IP/hostname pattern
  - [ ] 7.4: Add filter by kill chain phase: dropdown for phase selection
  - [ ] 7.5: Implement `apply_filters()` method that dims/hides non-matching cells
  - [ ] 7.6: Add filter warning indicator: "N agents hidden by current filter"
  - [ ] 7.7: Implement critical finding override: objective-relevant findings ignore filters
  - [ ] 7.8: Add keyboard shortcut `/` to focus filter bar

- [x] **Task 8: Implement Agent Count and Anomaly Count Display** (AC: #1, per UX spec)
  - [ ] 8.1: Add `_agent_count: int` property returning total agents in grid
  - [ ] 8.2: Add `_anomaly_count: int` property returning agents with attention states
  - [ ] 8.3: Create status bar component showing: "Agents: 10,234 | Anomalies: 23"
  - [ ] 8.4: Wire to `AttentionPriority` from `agent_list.py` for anomaly detection
  - [ ] 8.5: Update counts reactively when agents added/removed/status changed

- [ ] **Task 9: Integrate with War Room Layout** (AC: #1)
  - [ ] 9.1: Update `WarRoomLayout` to replace `HiveMatrixPane` placeholder with `HiveMatrix`
  - [ ] 9.2: Add `hive_matrix` property to `WarRoomLayout` for external access
  - [ ] 9.3: Wire daemon client agent updates to `HiveMatrix.update_agent()` method
  - [ ] 9.4: Add TCSS styling for HiveMatrix in `style.tcss`

- [x] **Task 10: Unit Tests** (AC: #1, #2, #3, #4, #5)
  - [ ] 10.1: Create `tests/unit/tui/test_hive_matrix.py`
  - [ ] 10.2: Test `HiveMatrix` initialization with default and custom grid sizes
  - [ ] 10.3: Test `HiveCell` color mapping for all `AgentStatus` values
  - [ ] 10.4: Test `_calculate_grid_dimensions()` for various agent counts (100, 1000, 10000)
  - [ ] 10.5: Test `add_connection()` and `remove_connection()` for stigmergic tracking
  - [ ] 10.6: Test `zoom_in()` / `zoom_out()` boundary conditions (min/max zoom)
  - [ ] 10.7: Test `_apply_zoom()` cell size calculations
  - [ ] 10.8: Test filter application with various criteria
  - [ ] 10.9: Test filter warning message when agents hidden
  - [ ] 10.10: Test critical finding override bypasses filters
  - [ ] 10.11: Test agent/anomaly count calculations
  - [ ] 10.12: Achieve 100% coverage on `hive_matrix.py`

- [x] **Task 11: Integration Tests** (AC: #6)
  - [ ] 11.1: Create `tests/integration/tui/test_hive_matrix_integration.py`
  - [ ] 11.2: Test grid renders correctly with 100 agents
  - [ ] 11.3: Test grid renders correctly with 10,000 agents (<100ms render per NFR4)
  - [ ] 11.4: Test status color updates propagate to cell display
  - [ ] 11.5: Test stigmergic connection grouping visual behavior
  - [ ] 11.6: Test zoom levels change cell display correctly
  - [ ] 11.7: Test hover tooltip displays correct agent details
  - [ ] 11.8: Test filter bar filters grid display correctly
  - [ ] 11.9: Test keyboard shortcuts (`+`, `-`, `/`) work correctly
  - [ ] 11.10: Test mouse wheel zoom functionality
  - [ ] 11.11: Test War Room integration with HiveMatrix in center pane

## Dev Notes

### Architecture Compliance

- **Location:** Create `src/cyberred/tui/widgets/hive_matrix.py` (per architecture spec line 886)
- **Pattern:** Extend Textual widgets, use TCSS for styling, support keyboard + mouse dual-path
- **Performance:** <100ms render at 10K scale per NFR4, O(1) cell lookup using spatial indexing
- **UX Principle:** "Ant colony visualization" - show emergent swarm coordination

### Technical Approach

**Widget Architecture:**
```python
from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar
from textual.widget import Widget
from textual.widgets import Static
from textual.reactive import reactive
from textual.message import Message

from cyberred.tui.widgets.agent_list import AgentRow, AgentStatus, AttentionPriority, get_attention_priority

if TYPE_CHECKING:
    from textual.app import ComposeResult


class HiveCell(Static):
    """Individual cell in the Hive Matrix representing one agent."""
    
    agent: reactive[AgentRow | None] = reactive(None)
    
    DEFAULT_CSS: ClassVar[str] = """
    HiveCell {
        width: 1;
        height: 1;
        content-align: center middle;
    }
    """
    
    _STATUS_COLORS: ClassVar[dict[AgentStatus, str]] = {
        AgentStatus.ACTIVE: "green",
        AgentStatus.IDLE: "blue", 
        AgentStatus.ERROR: "red",
        AgentStatus.AUTH_PENDING: "yellow",
        AgentStatus.STALLED: "orange",
        AgentStatus.CRITICAL_FINDING: "magenta",
    }
    
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


class HiveMatrix(Widget):
    """Visual grid showing agent status and stigmergic connections.
    
    Displays 10K+ agents as a grid with:
    - Status-based cell colors (active=green, idle=blue, error=red)
    - Stigmergic connection visualization via grouping
    - Zoom in/out capability
    - Hover details for agent information
    - Filter bar for state/target/kill-chain filtering
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
    
    class AgentUpdated(Message):
        """Message sent when an agent is updated in the grid."""
        def __init__(self, agent: AgentRow) -> None:
            self.agent = agent
            super().__init__()
    
    def __init__(
        self,
        *,
        grid_size: int = 100,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._agents: dict[str, AgentRow] = {}
        self._cells: dict[str, HiveCell] = {}
        self._connections: dict[str, set[str]] = {}
        self._grid_size = grid_size
        self._zoom_level = 3  # Default middle zoom
        self._hovered_agent: AgentRow | None = None
        self._filters: dict[str, object] = {}
    
    def _calculate_grid_dimensions(self, agent_count: int) -> tuple[int, int]:
        """Calculate grid width and height for given agent count."""
        import math
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
    
    def update_agent(self, agent: AgentRow) -> None:
        """Update or add an agent in the grid."""
        self._agents[agent.agent_id] = agent
        if agent.agent_id in self._cells:
            self._cells[agent.agent_id].agent = agent
        self.post_message(self.AgentUpdated(agent))
    
    def add_connection(self, agent_id_1: str, agent_id_2: str) -> None:
        """Add stigmergic connection between two agents."""
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
        """Remove stigmergic connection between two agents."""
        if agent_id_1 in self._connections:
            self._connections[agent_id_1].discard(agent_id_2)
        if agent_id_2 in self._connections:
            self._connections[agent_id_2].discard(agent_id_1)
    
    def zoom_in(self) -> None:
        """Increase zoom level (max 5)."""
        if self._zoom_level < 5:
            self._zoom_level += 1
            self._apply_zoom()
    
    def zoom_out(self) -> None:
        """Decrease zoom level (min 1)."""
        if self._zoom_level > 1:
            self._zoom_level -= 1
            self._apply_zoom()
    
    def _apply_zoom(self) -> None:
        """Apply current zoom level to cell sizes."""
        # Zoom level 1: 1x1 cells (dense)
        # Zoom level 5: 3x3 cells (detailed)
        cell_size = 1 + (self._zoom_level - 1) // 2
        for cell in self._cells.values():
            cell.styles.width = cell_size
            cell.styles.height = cell_size
```

**Status Color Mapping (per UX spec line 256):**

| Status | Color | TCSS Token | Visual |
|--------|-------|------------|--------|
| ACTIVE | green | `$status-scanning` | █ (green) |
| IDLE | blue | `$status-idle` | █ (blue) |
| ERROR | red | `$danger` | █ (red) |
| AUTH_PENDING | yellow | `$status-thinking` | █ (yellow) |
| STALLED | orange | `$status-paused` | █ (orange) |
| CRITICAL_FINDING | magenta | `$status-exploited` | █ (magenta) |

**Stigmergic Connection Visualization:**
- Connected agents share border color (cyan)
- Connection groups placed adjacent when possible
- Visual clustering shows emergent coordination patterns

**Zoom Levels:**

| Level | Cell Size | Detail |
|-------|-----------|--------|
| 1 | 1x1 | Dense overview, 100x100 = 10K visible |
| 2 | 1x1 | Same density, enhanced colors |
| 3 | 2x2 | Medium detail (default) |
| 4 | 2x2 | Medium detail with borders |
| 5 | 3x3 | Full detail, agent ID visible on hover |

**Filter Bar (per UX spec line 508):**
- Filter by state: `ACTIVE`, `IDLE`, `ERROR`, `AUTH_PENDING`, `STALLED`, `CRITICAL_FINDING`
- Filter by target: IP/hostname pattern matching
- Filter by kill chain phase: Recon, Exploit, Post-Ex, etc.
- Critical finding override: Objective-relevant findings always visible
- Filter warning: "N agents hidden by current filter"

### Existing Code Context (Stories 9.1-9.5)

**VirtualizedAgentList (Story 9.3, 9.4):** Provides `AgentRow`, `AgentStatus`, `AttentionPriority` types and color/icon mappings. Reuse these for consistency.

**WarRoomLayout (Story 9.2):** Has `HiveMatrixPane` placeholder in center pane (50% width). Replace with `HiveMatrix`.

**FindingStream (Story 9.5):** Pattern for extending Textual widgets with reactive properties, custom messages, and TCSS styling.

**style.tcss:** Contains color tokens (`$cyber-green`, `$danger`, etc.) and existing `HiveGrid` styles (lines 62-83) to reference/extend.

### UX Design References

- **UX Spec lines 508-509:** HiveMatrix full component spec:
  > `HiveMatrix` | 10K agent grid with status colors, anomaly bubbling, filter bar (by state/target/kill chain phase), priority queue for critical events, critical finding override (objective-relevant findings ignore filters), filter warning indicator ("N findings hidden by current filter")
- **UX Spec line 256:** Agent Status color tokens: `$status-idle`, `$status-scanning`, `$status-thinking`, `$status-attacking`, `$status-exploited`, `$status-paused`
- **UX Spec lines 392-393:** HIVE MATRIX layout: "agent grid + status colors + agent/anomaly count + filter bar"
- **UX Spec lines 65-66:** Anomaly Bubbling principle (implemented in 9.4, integrate here)
- **UX Spec line 530:** Phase 1 Core components includes HiveMatrix

### Performance Considerations

- **<100ms render at 10K:** Use virtualization pattern - only render visible cells
- **O(1) cell lookup:** Use `dict[str, HiveCell]` for agent_id → cell mapping
- **Spatial indexing:** Grid coordinates for efficient position-based queries
- **Lazy cell creation:** Create cells on-demand as agents are added
- **Efficient reflow:** Batch updates on resize, debounce rapid changes

### Testing Standards

- **Unit tests:** Test all public methods, color mappings, zoom behavior, filter logic
- **Integration tests:** Test visual rendering, hover interaction, War Room integration
- **Performance tests:** Verify <100ms render at 10K scale
- **Coverage:** 100% required per project standards

### Dependencies

- **Story 9.3:** Virtualized Agent List (✅ complete) - provides `AgentRow`, `AgentStatus`, patterns
- **Story 9.4:** Anomaly Bubbling (✅ complete) - provides `AttentionPriority`, attention detection
- **Story 9.5:** Real-Time Finding Stream (✅ complete) - pattern for widget implementation

### Project Structure Notes

- **New file:** `src/cyberred/tui/widgets/hive_matrix.py`
- **Modified:** `src/cyberred/tui/widgets/war_room_layout.py` (replace HiveMatrixPane)
- **Modified:** `src/cyberred/tui/widgets/__init__.py` (add HiveMatrix export)
- **Modified:** `src/cyberred/tui/style.tcss` (add HiveMatrix styles)
- **Test location:** `tests/unit/tui/test_hive_matrix.py`, `tests/integration/tui/test_hive_matrix_integration.py`

### References

- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story-9.6] - Original story definition (lines 3916-3938)
- [Source: _bmad-output/planning-artifacts/ux-design.md#Custom-Components] - HiveMatrix full spec (lines 508-509)
- [Source: _bmad-output/planning-artifacts/ux-design.md#Color-Token-System] - Agent Status colors (line 256)
- [Source: _bmad-output/planning-artifacts/ux-design.md#Chosen-Direction] - HIVE MATRIX layout spec (lines 392-393)
- [Source: _bmad-output/planning-artifacts/architecture.md#Project-Structure] - File location (line 886)
- [Source: _bmad-output/implementation-artifacts/9-5-real-time-finding-stream.md] - Previous story patterns
- [Source: src/cyberred/tui/widgets/agent_list.py] - AgentRow, AgentStatus, AttentionPriority types
- [Source: src/cyberred/tui/style.tcss] - Existing HiveGrid styles (lines 62-83)

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
