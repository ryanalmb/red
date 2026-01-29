"""TUI Widgets for Cyber-Red War Room.

Story 9.1: Textual App Foundation widgets including:
- StatusBarWidget: F-key navigation, engagement state, C2 heartbeat
- HiveGrid: Agent status grid
- AttackTree: Target hierarchy
- KillChainLog, TerminalLog, ThinkingLog: Log displays
- AuthorizationModal: HITL authorization dialog

Story 9.2: War Room Three-Pane Layout widgets:
- WarRoomLayout: Three-pane container with resize support
- LayoutConfig: Persistent layout configuration
- PaneResized: Message for layout change notification
- TargetsPane, HiveMatrixPane, StrategyStreamPane: Pane placeholders

Story 9.3: Virtualized Agent List (10K+ Scale):
- VirtualizedAgentList: Virtualized list for 10K+ agents
- AgentRow: Data class for agent display
- AgentStatus: Agent status enum
"""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Log, Tree, Button, Label
from textual.containers import Container, Grid, Horizontal
from textual.reactive import reactive
from textual.screen import ModalScreen

from .rag_manager import RAGManagerWidget
from .director_display import DirectorDisplayWidget, DirectorPerspective
from .stale_indicator import StaleStateIndicator
from .attach_progress import AttachProgressIndicator
from .war_room_layout import (
    WarRoomLayout,
    LayoutConfig,
    PaneResized,
    TargetsPane,
    HiveMatrixPane,
    StrategyStreamPane,
    MIN_PANE_WIDTH,
    MAX_PANE_WIDTH,
    RESIZE_STEP,
    DEFAULT_CONFIG_PATH,
)
from .agent_list import (
    VirtualizedAgentList,
    AgentRow,
    AgentStatus,
    format_agent_row,
    get_status_color,
    get_status_icon,
    COLUMN_HEADERS,
    COLUMN_WIDTHS,
)
from .finding_stream import (
    FindingStream,
    FindingDetailModal,
    Finding,
    FindingSeverity,
    get_severity_style,
    _SEVERITY_COLORS,
    _SEVERITY_ICONS,
)
from .hive_matrix import (
    HiveMatrix,
    HiveCell,
    HiveTooltip,
    HiveFilterBar,
    STATUS_COLORS,
)
from .fkey_bar import (
    FKeyBar,
    FKeyMapping,
    DEFAULT_FKEY_MAPPINGS,
)
from .constraints_form import (
    ConstraintsForm,
    TIME_LIMIT_OPTIONS,
    TARGET_LIMIT_MIN,
    TARGET_LIMIT_MAX,
    validate_target_limit,
    validate_host_format,
    parse_hosts_input,
)


class StatusBarWidget(Static):
    """Status bar widget displaying engagement state and C2 heartbeat.
    
    Story 9.1: UX Spec compliant status bar with:
    - F-key navigation hints (F1-F6)
    - Engagement state indicator (RUNNING/PAUSED/STOPPED)
    - C2 heartbeat indicator (●/◐/○)
    - Sticky kill button (always visible)
    
    UX Spec References:
    - Lines 333-334: Header Row layout
    - Lines 360: Heartbeat indicator
    """
    
    DEFAULT_CSS = """
    StatusBarWidget {
        height: 1;
        background: $surface;
    }
    """
    
    engagement_id: reactive[str] = reactive("")
    engagement_state: reactive[str] = reactive("STOPPED")
    heartbeat: reactive[str] = reactive("○")
    pending_auth: reactive[int] = reactive(0)
    
    def __init__(
        self,
        engagement_id: str = "",
        *args,
        **kwargs,
    ) -> None:
        """Initialize StatusBarWidget.
        
        Args:
            engagement_id: Current engagement ID to display.
        """
        super().__init__(*args, **kwargs)
        self.engagement_id = engagement_id
    
    def compose(self) -> ComposeResult:
        """Compose the status bar layout."""
        # Left side: F-keys
        yield Static(
            "[F1]Dash [F2]Cfg [F3]Log [F4]Rpt [F5]Pause [F6]RAG",
            id="status-fkeys",
        )
    
    def render(self) -> str:
        """Render the status bar content.
        
        Returns:
            Formatted status bar string.
        """
        # Format: [F-keys] | STATE | ENGAGEMENT | [AUTH:n] | [●C2] | [ESC]KILL
        fkeys = "[F1]Dash [F2]Cfg [F3]Log [F4]Rpt [F5]Pause [F6]RAG"
        
        # State with color class
        # Story 10.4: Added FROZEN state with bold red styling
        state_colors = {
            "RUNNING": "green",
            "PAUSED": "yellow", 
            "STOPPED": "dim",
            "FROZEN": "bold red",  # Story 10.4: Kill switch activated
        }
        state_color = state_colors.get(self.engagement_state, "dim")
        state_display = f"[{state_color}]{self.engagement_state}[/{state_color}]"
        
        # Engagement ID (truncated if needed)
        eng_display = self.engagement_id[:12] if self.engagement_id else "---"
        
        # Heartbeat with color
        hb_colors = {"●": "green", "◐": "yellow", "○": "red"}
        hb_color = hb_colors.get(self.heartbeat, "red")
        hb_display = f"[{hb_color}]{self.heartbeat}[/{hb_color}]C2"
        
        # Auth count
        auth_display = f"[AUTH:{self.pending_auth}]" if self.pending_auth > 0 else ""
        
        # Kill button (always visible)
        kill_display = "[bold red][ESC]KILL[/bold red]"
        
        return f"{fkeys} | {state_display} | {eng_display} | {auth_display} {hb_display} | {kill_display}"
    
    def update_state(self, state: str) -> None:
        """Update engagement state.
        
        Args:
            state: New state (RUNNING, PAUSED, STOPPED, FROZEN).
            
        Raises:
            ValueError: If state is not a valid engagement state.
        """
        valid_states = {"RUNNING", "PAUSED", "STOPPED", "FROZEN"}
        if state not in valid_states:
            raise ValueError(f"Invalid engagement state: '{state}'. Valid states: {valid_states}")
        self.engagement_state = state
        self.refresh()
    
    def update_heartbeat(self, status: str) -> None:
        """Update C2 heartbeat indicator.
        
        Args:
            status: Heartbeat symbol (●, ◐, ○).
        """
        self.heartbeat = status
        self.refresh()
    
    def update_pending_auth(self, count: int) -> None:
        """Update pending authorization count.
        
        Args:
            count: Number of pending auth requests.
        """
        self.pending_auth = count
        self.refresh()

class HiveGrid(Grid):
    """Grid display for agent status visualization.
    
    Displays a 10x10 grid of agent status blocks that update
    based on swarm activity.
    """
    
    def compose(self) -> ComposeResult:
        """Compose the grid with 100 agent blocks."""
        for i in range(1, 101):
            yield Static(f"{i:02}", id=f"agent-{i}", classes="agent-block")

    def update_agent(self, agent_id: int, status: str) -> None:
        """Update the visual status of an agent in the grid.
        
        Args:
            agent_id: The agent's numeric ID (1-100).
            status: The new status (idle, scanning, thinking, attacking, paused, exploited).
        """
        widget = self.query_one(f"#agent-{agent_id}")
        widget.remove_class("status-idle", "status-scanning", "status-thinking", "status-attacking", "status-paused")
        widget.add_class(f"status-{status}")

class AttackTree(Tree):
    """Tree widget for displaying target hierarchy and attack paths."""
    pass


class KillChainLog(Log):
    """Log widget for displaying kill chain events with severity coloring."""
    
    def log_event(self, timestamp: str, category: str, message: str) -> None:
        """Log an event to the kill chain display.
        
        Args:
            timestamp: Time of the event (e.g., "now", "00:00").
            category: Event category (CRITIC, SUCCESS, FAIL, AUTH, INFO, STATE).
            message: The event message to display.
        """
        color = "white"
        if category == "CRITIC": color = "orange"
        if category == "SUCCESS": color = "green"
        if category == "FAIL": color = "red"
        if category == "AUTH": color = "yellow"
        self.write(f"[{timestamp}] [{color}]{category}[/{color}]: {message}")


class TerminalLog(Log):
    """Log widget for displaying terminal/tool output streams."""
    
    def log_stream(self, source: str, text: str) -> None:
        """Log terminal output from a source.
        
        Args:
            source: The source of the output (e.g., "TOOL", "nmap").
            text: The output text to display.
        """
        self.write(f"[{source}] {text}")


class ThinkingLog(Log):
    """Log widget for streaming the internal monologue of the AI."""
    
    def log_thought(self, category: str, text: str) -> None:
        """Log an AI thinking/reasoning event.
        
        Args:
            category: Thought category (THINKING, STRATEGY, CODE, INFO).
            text: The thought/reasoning text to display.
        """
        color = "cyan"
        if category == "THINKING": color = "magenta"
        if category == "STRATEGY": color = "blue"
        if category == "CODE": color = "green"
        self.write(f"[{color}]{category}[/{color}]: {text}")


# Story 10.1: AuthorizationModal moved to screens/authorization.py
# Import here for backward compatibility
from cyberred.tui.screens.authorization import (
    AuthorizationScreen as AuthorizationModal,
    AuthorizationRequest,
    AuthorizationResponse,
    AuthorizationType,
    AuthorizationDecision,
    RiskLevel,
    SwarmSnapshot,
)

