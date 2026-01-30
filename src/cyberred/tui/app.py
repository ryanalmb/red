"""Cyber-Red TUI Application.

The main Textual application for the Cyber-Red War Room interface.
Supports two modes:
1. Standalone mode: Uses EventBus for internal event streaming
2. Daemon mode: Uses TUIClient for daemon IPC streaming

Story 9.1: Textual App Foundation
- Responsive breakpoints per UX spec (80x24 min, 100x30 standard, 120x40 optimal)
- Engagement state tracking (RUNNING/PAUSED/STOPPED)
- C2 heartbeat indicator (●/◐/○)
"""

from __future__ import annotations

import time
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

import structlog
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input
from textual.containers import Horizontal, Vertical
from textual.geometry import Size
from textual.reactive import reactive
from textual.css.query import NoMatches
import asyncio

from cyberred.tui.widgets import (
    HiveGrid,
    AttackTree,
    KillChainLog,
    TerminalLog,
    ThinkingLog,
    RAGManagerWidget,
    DirectorDisplayWidget,
    StatusBarWidget,
    AttachProgressIndicator,
    TimelineScrubber,
    DashboardWidget,
)
from cyberred.tui.catchup import CatchupManager, CatchupEvent
from cyberred.tui.screens.authorization import (
    AuthorizationScreen,
    AuthorizationRequest,
)
from cyberred.tui.screens.dropbox import DropBoxScreen
from cyberred.tui.screens.kill_confirm import KillSwitchConfirmScreen
from cyberred.tui.screens.help import HelpScreen
from cyberred.tui.screens.scope_editor import ScopeEditorScreen
from cyberred.tui.screens.data_browser import DataBrowserScreen
from cyberred.daemon.streaming import StreamEventType

if TYPE_CHECKING:
    from cyberred.core.event_bus import EventBus
    from cyberred.core.killswitch import KillSwitch
    from cyberred.tui.daemon_client import TUIClient


# Responsive breakpoint constants per UX spec
# Compact: < 100 columns (single pane focus with tabs)
# Standard: 100-119 columns (all panes visible, compressed)
# Optimal: 120+ columns (full layout)
BREAKPOINT_COMPACT = 100
BREAKPOINT_STANDARD = 120

# Minimum terminal size per UX spec (80x24)
MIN_TERMINAL_WIDTH = 80
MIN_TERMINAL_HEIGHT = 24

# C2 heartbeat latency thresholds (milliseconds) per UX spec
LATENCY_HEALTHY_MS = 500
LATENCY_DEGRADED_MS = 2000


class LayoutMode(Enum):
    """Layout mode based on terminal size breakpoints."""
    COMPACT = "compact"    # < 100 cols: single pane focus with tabs
    STANDARD = "standard"  # 100-119 cols: all panes visible, compressed
    OPTIMAL = "optimal"    # 120+ cols: full layout


class EngagementState(Enum):
    """Engagement state for header display."""
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    FROZEN = "FROZEN"  # Story 10.4: Kill switch activated state


class HeartbeatStatus(Enum):
    """C2 heartbeat status indicator per UX spec.
    
    Latency thresholds:
    - Healthy: <500ms (●)
    - Degraded: 500-2000ms (◐)
    - Critical: >2000ms (○)
    """
    HEALTHY = "●"    # <500ms
    DEGRADED = "◐"   # 500-2000ms
    CRITICAL = "○"   # >2000ms


class CyberRedApp(App):
    """Cyber-Red War Room TUI Application.

    Supports two modes of operation:
    - Standalone: Uses EventBus for internal events (testing, demos)
    - Daemon: Uses TUIClient for daemon IPC streaming (production)
    
    Story 9.1: Responsive breakpoints per UX spec:
    - Compact (<100 cols): Single pane focus with tabs
    - Standard (100-119 cols): All panes visible, compressed
    - Optimal (120+ cols): Full layout
    """

    CSS_PATH = "style.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
        ("escape", "panic", "KILL"),  # Story 9.1: ESC for kill switch per UX spec (immediate, no confirm)
        ("p", "panic", "PANIC"),
        ("f1", "dashboard", "Dashboard"),  # Story 9.1: F1 for dashboard per UX spec
        ("f2", "config", "Config"),  # Story 9.1: F2 for config per UX spec
        ("f3", "logs", "Logs"),  # Story 9.1: F3 for logs per UX spec
        ("f4", "report", "Report"),  # Story 9.1: F4 for report per UX spec
        ("f5", "pause_resume", "Pause/Resume"),  # Story 9.1: F5 for pause per UX spec
        ("ctrl+d", "detach", "Detach"),
        ("f6", "show_dropbox", "Drop Box"),  # Story 9.10: Drop Box Status Panel
        ("f7", "director_panel", "Director"),  # Story 8.11: Director Ensemble Display
        ("f8", "scope_editor", "Scope"),  # Story 10.5: Runtime Scope Adjustment
        ("f9", "data_browser", "Data"),  # Story 11.2: Exfiltrated Data Browser
        ("f10", "kill_switch_confirm", "Kill"),  # Story 9.11: F10 kill switch with confirmation
        ("f11", "rag_panel", "RAG"),  # Story 11.5: RAG Management Panel
        ("question_mark", "help", "Help"),  # Story 9.11: ? for help overlay
        ("ctrl+t", "toggle_thinking", "Toggle Thinking"),  # Story 8.11: Toggle <think> tags
        ("r", "refresh_state", "Refresh"),  # Story 9.7: Refresh stale state
    ]

    # Reactive properties for state tracking (Story 9.1)
    current_layout_mode: reactive[LayoutMode] = reactive(LayoutMode.STANDARD)
    engagement_state: reactive[EngagementState] = reactive(EngagementState.STOPPED)
    heartbeat_status: reactive[HeartbeatStatus] = reactive(HeartbeatStatus.CRITICAL)

    def __init__(
        self,
        event_bus: Optional["EventBus"] = None,
        daemon_client: Optional["TUIClient"] = None,
        engagement_id: Optional[str] = None,
        redis_client: Optional[Any] = None,
        docker_client: Optional[Any] = None,
    ) -> None:
        """Initialize CyberRedApp.

        Args:
            event_bus: EventBus for standalone mode (optional).
            daemon_client: TUIClient for daemon mode (optional).
            engagement_id: Engagement ID when using daemon mode.
            redis_client: Redis client for KillSwitch (optional).
            docker_client: Docker client for KillSwitch (optional).

        Note:
            If daemon_client is provided, it takes precedence over event_bus.
            If redis_client or docker_client is provided, KillSwitch is initialized.
        """
        super().__init__()
        self.bus = event_bus
        self._daemon_client = daemon_client
        self._engagement_id = engagement_id
        self._stream_task: Optional[asyncio.Task] = None
        self._stale_check_task: Optional[asyncio.Task] = None  # Story 9.7: Stale state check
        self._attach_progress: Optional[AttachProgressIndicator] = None  # Story 9.8: Progress indicator
        
        # Story 10.4: Kill switch integration
        self._killswitch: Optional["KillSwitch"] = None
        self._log = structlog.get_logger().bind(component="tui_app")
        
        # Initialize KillSwitch if clients are provided
        if redis_client is not None or docker_client is not None:
            from cyberred.core.killswitch import KillSwitch
            self._killswitch = KillSwitch(
                redis_client=redis_client,
                docker_client=docker_client,
                engagement_id=engagement_id or "unknown",
            )

    @property
    def is_daemon_mode(self) -> bool:
        """Return True if using daemon client for events."""
        return self._daemon_client is not None

    def get_layout_mode(self, size: Size) -> LayoutMode:
        """Determine layout mode based on terminal size.
        
        Story 9.1: Responsive breakpoints per UX spec.
        
        Args:
            size: Terminal size (width, height).
            
        Returns:
            LayoutMode based on terminal width:
            - COMPACT: < 100 columns
            - STANDARD: 100-119 columns
            - OPTIMAL: 120+ columns
        """
        if size.width < BREAKPOINT_COMPACT:
            return LayoutMode.COMPACT
        elif size.width < BREAKPOINT_STANDARD:
            return LayoutMode.STANDARD
        else:
            return LayoutMode.OPTIMAL

    def get_heartbeat_status(self, latency_ms: int) -> HeartbeatStatus:
        """Get heartbeat status based on C2 latency.
        
        Story 9.1: C2 heartbeat indicator per UX spec.
        
        Args:
            latency_ms: Latency in milliseconds.
            
        Returns:
            HeartbeatStatus:
            - HEALTHY: <500ms (●)
            - DEGRADED: 500-2000ms (◐)
            - CRITICAL: ≥2000ms (○)
        """
        if latency_ms < LATENCY_HEALTHY_MS:
            return HeartbeatStatus.HEALTHY
        elif latency_ms < LATENCY_DEGRADED_MS:
            return HeartbeatStatus.DEGRADED
        else:
            return HeartbeatStatus.CRITICAL

    def configure_layout_for_mode(self, mode: LayoutMode) -> None:
        """Configure pane visibility based on layout mode.
        
        Story 9.1: Graceful degradation for compact mode.
        
        Args:
            mode: The layout mode to configure for.
        """
        # In compact mode, hide secondary panes and show tabs
        # In standard/optimal mode, show all panes
        try:
            left_pane = self.query_one("#pane-left", Vertical)
            mid_pane = self.query_one("#pane-mid", Vertical)
            right_pane = self.query_one("#pane-right", Vertical)
            
            if mode == LayoutMode.COMPACT:
                # Compact: Single pane focus - hide left and right, expand middle
                left_pane.display = False
                right_pane.display = False
                mid_pane.display = True
            else:
                # Standard/Optimal: Show all panes
                left_pane.display = True
                mid_pane.display = True
                right_pane.display = True
        except NoMatches:
            # Panes not yet mounted, skip configuration
            pass

    def on_resize(self, event) -> None:
        """Handle terminal resize events.
        
        Story 9.1: Updates layout mode on resize per UX spec breakpoints.
        """
        new_mode = self.get_layout_mode(event.size)
        if new_mode != self.current_layout_mode:
            self.current_layout_mode = new_mode
            self.configure_layout_for_mode(new_mode)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        # Story 9.1: Status bar with F-keys, engagement state, C2 heartbeat
        yield StatusBarWidget(
            engagement_id=self._engagement_id or "",
            id="status-bar",
        )
        
        # Story 9.8: Attach progress indicator (AC #3)
        yield AttachProgressIndicator(id="attach-progress")

        with Horizontal():
            # Left: Target & Matrix
            with Vertical(id="pane-left"):
                yield Static("TARGETS", classes="pane-title")
                yield AttackTree("Scope")
                yield Static("HIVE STATUS", classes="pane-title")
                yield HiveGrid(id="hive-grid")

            # Middle: Brain Stream & Kill Chain & Director
            with Vertical(id="pane-mid"):
                yield Static("BRAIN STREAM", classes="pane-title")
                yield ThinkingLog(id="brain-stream")
                yield Static("KILL CHAIN", classes="pane-title")
                yield KillChainLog(id="kill-chain")
                # Story 11.5: Timeline Scrubber for Strategy Stream (AC #5)
                yield TimelineScrubber(id="timeline-scrubber")
                # Story 8.11: Director Ensemble Display (hidden by default)
                director = DirectorDisplayWidget(daemon_client=self._daemon_client)
                director.display = False
                director.id = "director-display-widget"
                yield director

            # Right: Terminal
            with Vertical(id="pane-right"):
                yield Static("TERMINAL STREAM", classes="pane-title")
                yield TerminalLog(id="terminal-stream")

        yield Input(
            placeholder="Type command here (e.g., 'Scan 10.0.0.5')...",
            id="cmd-input",
        )
        yield Footer()

        # Story 11.6: Dashboard widget (hidden by default, toggled via F1)
        dashboard = DashboardWidget(id="dashboard-widget")
        dashboard.display = False
        yield dashboard

    async def on_input_submitted(self, message: Input.Submitted) -> None:
        user_text = message.value
        self.query_one("#cmd-input", Input).value = ""

        # Handle 'detach' command
        if user_text.strip().lower() == "detach":
            await self.action_detach()
            return

        # Story 10.4: Handle 'kill' command (AC #2)
        if user_text.strip().lower() == "kill":
            self.action_kill_switch_confirm()
            return
        
        # Story 10.4: Handle 'kill!' command (immediate, bypass confirmation)
        if user_text.strip().lower() == "kill!":
            await self.action_panic(trigger_source="command")
            return

        self.notify(f"Analyzing: {user_text}...")

        if self.bus:
            await self.bus.publish("cmd:nlp", {"text": user_text})

    async def on_mount(self) -> None:
        """Set up event subscriptions on mount."""
        if self._daemon_client and self._engagement_id:
            # Daemon mode: stream events from daemon client
            self._stream_task = asyncio.create_task(self._consume_daemon_stream())
        elif self.bus:
            # Standalone mode: subscribe to EventBus channels
            asyncio.create_task(
                self.bus.subscribe("swarm:status", self.handle_status_update)
            )
            asyncio.create_task(
                self.bus.subscribe("swarm:worker_status", self.handle_worker_status)
            )
            asyncio.create_task(
                self.bus.subscribe("swarm:log", self.handle_log_update)
            )
            asyncio.create_task(
                self.bus.subscribe("swarm:terminal", self.handle_terminal_update)
            )
            asyncio.create_task(
                self.bus.subscribe("swarm:brain", self.handle_brain_update)
            )
            asyncio.create_task(
                self.bus.subscribe("hitl:request_auth", self.handle_auth_request)
            )
            asyncio.create_task(
                self.bus.subscribe("orchestrator:tool_start", self.handle_tool_event)
            )
            asyncio.create_task(
                self.bus.subscribe("orchestrator:tool_complete", self.handle_tool_event)
            )

    async def _consume_daemon_stream(self) -> None:
        """Consume streaming events from daemon client.
        
        Story 9.8: Shows progress indicator during attach and displays
        latency on completion (AC #1, #3).
        Story 11.5: Integrates CatchupManager for event replay on reattach (AC #4).
        """
        if not self._daemon_client or not self._engagement_id:
            return

        # Story 9.8: Show progress indicator during attach (AC #3)
        try:
            progress = self.query_one("#attach-progress", AttachProgressIndicator)
            progress.start(self._engagement_id)
        except NoMatches:
            progress = None

        # Story 11.5: Start catch-up replay if there are queued events (AC #4)
        catchup_manager = self._daemon_client.catchup_manager
        if catchup_manager.pending_count > 0:
            self.notify(f"Catching up: {catchup_manager.pending_count} events...", severity="information")
            
            async def catchup_handler(event: CatchupEvent) -> None:
                """Handle replayed catch-up events."""
                await self._handle_catchup_event(event)
            
            def on_catchup_progress(current: int, total: int) -> None:
                """Update progress during catch-up."""
                try:
                    timeline = self.query_one("#timeline-scrubber", TimelineScrubber)
                    timeline.add_marker(f"Catchup {current}/{total}")
                except NoMatches:
                    pass
            
            replayed = await catchup_manager.start_catchup(catchup_handler, on_catchup_progress)
            self.notify(f"Catch-up complete: {replayed} events replayed", severity="information")

        try:
            # Story 9.8: Use incremental sync for faster attach (AC #2)
            async for event in self._daemon_client.attach(
                self._engagement_id,
                sync_mode="incremental",
            ):
                # Story 9.8: Complete progress indicator after first event (initial state)
                if progress and self._daemon_client.attach_latency_ms is not None:
                    latency_ms = self._daemon_client.attach_latency_ms
                    progress.complete(success=True, latency_ms=latency_ms)
                    # Update status bar with latency (AC #3 - Task 3.4)
                    # Story 9.8 Task 3.5: Handle attach timeout (>2s) with warning but continue
                    if latency_ms > 2000.0:
                        self.notify(
                            f"Attached in {latency_ms:.0f}ms (exceeds 2s threshold)",
                            severity="warning"
                        )
                    else:
                        self.notify(f"Attached in {latency_ms:.0f}ms", severity="information")
                    progress = None  # Only show once
                
                await self._handle_stream_event(event)
        except Exception as e:
            # Story 9.8: Show error in progress indicator
            if progress:
                progress.complete(success=False)
            self.notify(f"Stream error: {e}", severity="error")

    async def _handle_stream_event(self, event) -> None:
        """Route daemon stream events to appropriate handlers."""
        if event.event_type == StreamEventType.AGENT_STATUS:
            await self.handle_status_update(event.data)
        elif event.event_type == StreamEventType.FINDING:
            await self._handle_finding(event.data)
        elif event.event_type == StreamEventType.AUTH_REQUEST:
            await self.handle_auth_request(event.data)
        elif event.event_type == StreamEventType.STATE_CHANGE:
            await self._handle_state_change(event.data)
        elif event.event_type == StreamEventType.HEARTBEAT:
            pass  # Just keep-alive, no action needed
        elif event.event_type == StreamEventType.STRATEGY_UPDATE:
            # Story 8.11: Handle Director strategy updates
            await self._handle_strategy_update(event.data)

    async def _handle_finding(self, data: dict) -> None:
        """Handle finding discovery event."""
        log = self.query_one("#kill-chain", KillChainLog)
        severity = data.get("severity", "INFO")
        finding_id = data.get("finding_id", "unknown")
        log.log_event("now", severity, f"Finding: {finding_id}")

    async def _handle_state_change(self, data: dict) -> None:
        """Handle engagement state change event.
        
        Story 10.4: Handles FROZEN state from daemon (AC #6).
        """
        state = data.get("state", "UNKNOWN")
        
        try:
            log = self.query_one("#kill-chain", KillChainLog)
            log.log_event("now", "STATE", f"Engagement: {state}")
        except NoMatches:
            pass

        # Story 10.4: Handle FROZEN state from daemon
        if state == "FROZEN":
            self.engagement_state = EngagementState.FROZEN
            self._update_status_bar_state()
            self.notify("ENGAGEMENT FROZEN - Kill switch activated", severity="error")
            # Update all agents to frozen status
            try:
                grid = self.query_one("#hive-grid", HiveGrid)
                for i in range(1, 101):
                    grid.update_agent(i, "frozen")
            except NoMatches:
                pass
            return

        # Update hive grid with initial agent data if present
        agents = data.get("agents", [])
        try:
            grid = self.query_one("#hive-grid", HiveGrid)
            for agent in agents:
                agent_id = agent.get("id") or agent.get("agent_id")
                status = agent.get("status", "idle")
                if agent_id:
                    grid.update_agent(agent_id, status)
        except NoMatches:
            pass

    async def _handle_strategy_update(self, data: dict) -> None:
        """Handle Director strategy update event (Story 8.11).
        
        Args:
            data: Strategy data from STRATEGY_UPDATE stream event.
        """
        try:
            director_widget = self.query_one("#director-display-widget", DirectorDisplayWidget)
            await director_widget.update_strategy(data)
            # Show notification
            confidence = data.get("confidence", 0.0)
            self.notify(f"Strategy Updated (confidence: {confidence:.0%})", severity="information")
        except NoMatches:
            # Director panel not visible or not found, log but don't error
            pass

    async def _handle_catchup_event(self, event: CatchupEvent) -> None:
        """Handle a replayed catch-up event (Story 11.5: AC #4).
        
        Routes catch-up events to appropriate handlers based on event type.
        Also adds timeline markers for significant events.
        
        Args:
            event: CatchupEvent being replayed
        """
        from cyberred.tui.catchup import CatchupEventType
        
        # Add timeline marker for this event
        try:
            timeline = self.query_one("#timeline-scrubber", TimelineScrubber)
            timeline.add_marker(
                label=f"{event.event_type.value}: {event.source}",
                timestamp=event.timestamp,
            )
        except NoMatches:
            pass
        
        # Route to appropriate handler based on event type
        if event.event_type == CatchupEventType.FINDING:
            await self._handle_finding(event.payload)
        elif event.event_type == CatchupEventType.AUTH_REQUEST:
            await self.handle_auth_request(event.payload)
        elif event.event_type == CatchupEventType.STRATEGY_UPDATE:
            await self._handle_strategy_update(event.payload)
        elif event.event_type == CatchupEventType.AGENT_STATE:
            await self.handle_status_update(event.payload)
        elif event.event_type == CatchupEventType.RAG_UPDATE:
            # RAG updates don't need special handling - state is in RAG store
            pass

    async def handle_status_update(self, data: dict) -> None:
        grid = self.query_one("#hive-grid", HiveGrid)
        agent_id = data.get("agent_id")
        if agent_id:
            grid.update_agent(agent_id, data.get("status", "idle"))

    async def handle_worker_status(self, data: dict) -> None:
        """Handle worker pool status updates."""
        grid = self.query_one("#hive-grid", HiveGrid)
        worker_id = data.get("worker_id", "")
        status = data.get("status", "idle")

        try:
            if "-" in worker_id:
                worker_num = int(worker_id.split("-")[-1])
                grid.update_agent(worker_num, status)
        except (ValueError, IndexError):
            pass

    async def handle_tool_event(self, data: dict) -> None:
        """Handle tool start/complete events - show in terminal."""
        term = self.query_one("#terminal-stream", TerminalLog)
        tool = data.get("tool", "unknown")

        if "target" in data:
            term.log_stream("TOOL", f"Starting {tool} → {data.get('target')}")
        else:
            success = "✓" if data.get("success", False) else "✗"
            findings = data.get("findings_count", 0)
            term.log_stream("TOOL", f"{success} {tool} complete ({findings} findings)")

    async def handle_log_update(self, data: dict) -> None:
        log = self.query_one("#kill-chain", KillChainLog)
        log.log_event(
            data.get("timestamp", "00:00"),
            data.get("category", "INFO"),
            data.get("message", ""),
        )

    async def handle_terminal_update(self, data: dict) -> None:
        term = self.query_one("#terminal-stream", TerminalLog)
        term.log_stream(data.get("source", "Unknown"), data.get("text", ""))

    async def handle_brain_update(self, data: dict) -> None:
        brain = self.query_one("#brain-stream", ThinkingLog)
        brain.log_thought(data.get("category", "INFO"), data.get("text", ""))

    async def handle_auth_request(self, data: dict) -> None:
        """Handle HITL authorization request - show enhanced modal dialog.
        
        Story 10.1: Enhanced authorization with Y/N/M/S options, swarm snapshot,
        risk assessment, and <500ms delivery requirement (NFR5).
        
        Also integrates with anomaly bubbling (Task 6) - sets agent status to
        AUTH_PENDING so it bubbles to the top of HiveMatrix/AgentList.
        """
        target = data.get("target", "Unknown")
        agent_id = data.get("agent_id")
        
        log = self.query_one("#kill-chain", KillChainLog)
        log.log_event("now", "AUTH", f"Authorization requested for: {target}")
        
        # Story 10.1 Task 6: Update agent status to AUTH_PENDING for anomaly bubbling
        if agent_id:
            try:
                grid = self.query_one("#hive-grid", HiveGrid)
                grid.update_agent(agent_id, "auth_pending")
            except NoMatches:
                pass
        
        # Update pending auth count in status bar
        self._pending_auth_count = getattr(self, "_pending_auth_count", 0) + 1
        self._update_status_bar_auth_count(self._pending_auth_count)

        async def send_response(result):
            # Decrement pending auth count
            current = getattr(self, "_pending_auth_count", 1)
            self._pending_auth_count = max(0, current - 1)
            self._update_status_bar_auth_count(self._pending_auth_count)
            
            # Story 10.1 Task 6: Clear AUTH_PENDING status after response
            if agent_id:
                try:
                    grid = self.query_one("#hive-grid", HiveGrid)
                    # Reset to active status after auth decision
                    grid.update_agent(agent_id, "active")
                except NoMatches:
                    pass
            
            if self.bus:
                await self.bus.publish("hitl:auth_response", result)
                if result.get("skipped"):
                    decision = "SKIPPED"
                elif result.get("approved"):
                    decision = "APPROVED"
                else:
                    decision = "DENIED"
                log.log_event("now", "AUTH", f"Target {target}: {decision}")
            
            # Send response to daemon if in daemon mode
            if self._daemon_client:
                try:
                    await self._daemon_client.send_auth_response(result)
                except Exception as e:
                    log.log_event("now", "AUTH", f"Failed to send response: {e}")

        # Create AuthorizationRequest from data
        request = AuthorizationRequest.from_dict(data)
        
        # Push enhanced authorization screen
        screen = AuthorizationScreen(request, callback=send_response)
        self.push_screen(screen)

    async def action_panic(
        self,
        trigger_source: str = "ESC",
        reason: str = "Operator initiated",
    ) -> Optional[dict[str, Any]]:
        """Trigger kill switch to halt all operations.
        
        Story 10.4: Kill Switch TUI Integration (AC #2, #5, #6)
        
        This method:
        1. Calls KillSwitch.trigger() if available (production mode)
        2. Falls back to event bus publish (standalone mode)
        3. Sets engagement state to FROZEN
        4. Updates status bar and logs to kill chain
        5. Logs to audit trail
        
        Args:
            trigger_source: Source of trigger (ESC, F10, command).
            reason: Reason for kill switch activation.
            
        Returns:
            KillSwitch result dict if KillSwitch is available, None otherwise.
        """
        start_time = time.perf_counter()
        result: Optional[dict[str, Any]] = None
        
        self.notify("PANIC TRIGGERED!", severity="error")
        
        # Story 10.4: Use KillSwitch if available
        if self._killswitch is not None:
            result = await self._killswitch.trigger(
                reason=reason,
                triggered_by="operator",
            )
            duration_ms = result.get("duration_ms", 0)
            paths = result.get("paths", {})
            
            # Log to audit trail
            self._log.warning(
                "kill_switch_tui_triggered",
                trigger_source=trigger_source,
                reason=reason,
                duration_ms=duration_ms,
                paths=paths,
                engagement_id=self._engagement_id,
            )
        elif self._daemon_client is not None:
            # Daemon mode: Send kill command to daemon
            await self._daemon_client.send_kill_command()
        elif self.bus is not None:
            # Fallback: Event bus broadcast
            await self.bus.publish("swarm:broadcast", {"command": "ABORT"})
        
        # Set engagement state to FROZEN
        self.engagement_state = EngagementState.FROZEN
        self._update_status_bar_state()
        
        # Log to kill chain
        try:
            log = self.query_one("#kill-chain", KillChainLog)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            log.log_event("now", "KILL", f"ENGAGEMENT FROZEN ({elapsed_ms:.0f}ms)")
        except NoMatches:
            pass
        
        # Update all agents to frozen status
        try:
            grid = self.query_one("#hive-grid", HiveGrid)
            for i in range(1, 101):
                grid.update_agent(i, "frozen")
        except NoMatches:
            pass
        
        # Show notification
        self.notify("ENGAGEMENT FROZEN - Kill switch activated", severity="error")
        
        return result

    async def action_detach(self) -> None:
        """Detach from daemon and exit TUI.
        
        Per Story 9.9 AC #3: Shows "Detached from {engagement_id}" message.
        Cancels stream task and stale check task before detaching.
        """
        if self._daemon_client:
            engagement_id = self._engagement_id or "unknown"
            # Cancel stream task
            if self._stream_task and not self._stream_task.done():
                self._stream_task.cancel()
                try:
                    await self._stream_task
                except asyncio.CancelledError:
                    pass
            # Cancel stale check task if running
            if self._stale_check_task and not self._stale_check_task.done():
                self._stale_check_task.cancel()
                try:
                    await self._stale_check_task
                except asyncio.CancelledError:
                    pass
            # Detach from engagement
            await self._daemon_client.detach()
            # AC #3: Show "Detached from {engagement_id}" message
            self.notify(f"Detached from {engagement_id}")
        self.exit()

    def action_show_dropbox(self) -> None:
        """Show Drop Box status screen (Story 9.10: AC #6).
        
        Per UX spec line 386-387 and 400: F6 Drop Box screen.
        Pushes DropBoxScreen onto the screen stack.
        """
        self.push_screen(DropBoxScreen(daemon_client=self._daemon_client))

    def action_kill_switch_confirm(self) -> None:
        """Show kill switch confirmation modal (Story 9.11: AC #4).
        
        Per UX spec: F10 kill switch requires confirmation.
        ESC bypasses confirmation for emergency use (handled by action_panic).
        """
        async def handle_confirm(confirmed: bool) -> None:
            if confirmed:
                await self.action_panic(trigger_source="F10")
        
        def sync_handle_confirm(confirmed: bool) -> None:
            if confirmed:
                asyncio.create_task(self.action_panic(trigger_source="F10"))
        
        self.push_screen(KillSwitchConfirmScreen(), sync_handle_confirm)

    def action_help(self) -> None:
        """Show help overlay (Story 9.11: AC #3).
        
        Per UX spec line 595: Help is accessible via `?` key.
        """
        self.push_screen(HelpScreen())

    def action_scope_editor(self) -> None:
        """Show scope editor screen (Story 10.5: AC #1).
        
        Per UX spec: F8 opens scope editor for runtime scope adjustment.
        """
        # Note: In production, this would get the ScopeValidator from the engagement
        # For now, we show a notification if no validator is available
        self.notify("Scope Editor - requires active engagement", severity="warning")

    def action_data_browser(self) -> None:
        """Show exfiltrated data browser screen (Story 11.2: AC #7).
        
        Per UX spec: F9 opens data browser for viewing exfiltrated data.
        Screen can be opened from War Room via F-key binding.
        """
        self.push_screen(DataBrowserScreen(daemon_client=self._daemon_client))

    async def action_rag_manager(self) -> None:
        """Open RAG Management modal (legacy method, use action_rag_panel)."""
        await self.action_rag_panel()

    async def action_rag_panel(self) -> None:
        """Open RAG Management panel (F11) - Story 11.5.
        
        Per UX spec: F11 opens RAG Management panel for corpus management.
        Toggle behavior: If already open, close it.
        """
        from textual.screen import ModalScreen
        
        # Toggle if already open
        try:
            existing = self.query_one("#rag-manager-screen")
            if existing:
                self.pop_screen()
                return
        except NoMatches:
            pass
        
        # Create dependencies for widget
        from cyberred.rag.store import RAGStore
        from cyberred.rag.ingest import RAGIngestPipeline
        from cyberred.rag.embeddings import RAGEmbeddings

        # Create modal screen wrapper following Epic 11 patterns
        class RAGManagerScreen(ModalScreen):
            """RAG Manager modal screen (Story 11.5)."""
            
            BINDINGS = [("escape", "dismiss", "Close")]
            
            def compose(self) -> ComposeResult:
                # RAGEmbeddings uses lazy loading (Story 6.2)
                store = RAGStore()
                embeddings = RAGEmbeddings()
                pipeline = RAGIngestPipeline(store, embeddings)
                yield RAGManagerWidget(store, pipeline)

        self.push_screen(RAGManagerScreen(id="rag-manager-screen"))

    async def action_director_panel(self) -> None:
        """Toggle Director Ensemble panel visibility (Story 8.11)."""
        try:
            director = self.query_one("#director-display-widget", DirectorDisplayWidget)
            director.display = not director.display
            if director.display:
                self.notify("Director panel shown (F7 to hide)")
            else:
                self.notify("Director panel hidden (F7 to show)")
        except NoMatches:
            self.notify("Director panel not available", severity="error")

    def action_toggle_thinking(self) -> None:
        """Toggle <think> tag visibility in Director panel (Story 8.11)."""
        try:
            director = self.query_one("#director-display-widget", DirectorDisplayWidget)
            director.show_thinking = not director.show_thinking
            state = "visible" if director.show_thinking else "hidden"
            self.notify(f"Thinking tags now {state}")
        except NoMatches:
            pass

    async def action_refresh_state(self) -> None:
        """Refresh engagement state from daemon (Story 9.7: AC #7).
        
        Manually triggers a state refresh and updates activity time.
        Bound to 'R' key.
        """
        if not self._daemon_client:
            return
        
        if not self._daemon_client.connected:
            return
        
        # Update last activity time to clear stale state using public API
        self._daemon_client.reset_activity_time()
        self.notify("State refreshed", severity="information")

    def action_dashboard(self) -> None:
        """Show dashboard overlay (Story 11.6: AC #1).

        Per UX spec line 401: F1 for Dashboard.
        Toggle behavior: If already shown, hide it.
        """
        try:
            dashboard = self.query_one("#dashboard-widget", DashboardWidget)
            dashboard.display = not dashboard.display
            if dashboard.display:
                self.notify("Dashboard shown (F1 to hide)")
            else:
                self.notify("Dashboard hidden (F1 to show)")
        except NoMatches:
            self.notify("Dashboard not available", severity="error")

    def action_config(self) -> None:
        """Show configuration panel (Story 9.1: F2 keybinding).
        
        Placeholder for configuration modal/panel.
        """
        self.notify("Configuration panel - not yet implemented (F2)", severity="warning")

    def action_logs(self) -> None:
        """Focus logs panel (Story 9.1: F3 keybinding).
        
        Focuses the kill chain log display.
        """
        self.notify("Logs view (F3)", severity="information")
        try:
            log = self.query_one("#kill-chain", KillChainLog)
            log.focus()
        except NoMatches:
            pass

    def action_report(self) -> None:
        """Show report panel (Story 9.1: F4 keybinding).
        
        Placeholder for engagement report generation/viewing.
        """
        self.notify("Report panel - not yet implemented (F4)", severity="warning")

    async def action_pause_resume(self) -> None:
        """Toggle pause/resume engagement state (Story 9.1).
        
        UX Spec: F5 for pause, single keypress instant action.
        """
        if self.engagement_state == EngagementState.RUNNING:
            self.engagement_state = EngagementState.PAUSED
            self.notify("Engagement PAUSED", severity="warning")
            if self.bus:
                await self.bus.publish("swarm:broadcast", {"command": "PAUSE"})
        elif self.engagement_state == EngagementState.PAUSED:
            self.engagement_state = EngagementState.RUNNING
            self.notify("Engagement RESUMED", severity="information")
            if self.bus:
                await self.bus.publish("swarm:broadcast", {"command": "RESUME"})
        
        # Update status bar
        self._update_status_bar_state()

    def _update_status_bar_state(self) -> None:
        """Update status bar with current engagement state."""
        try:
            status_bar = self.query_one("#status-bar", StatusBarWidget)
            status_bar.update_state(self.engagement_state.value)
        except NoMatches:
            pass

    def _update_status_bar_heartbeat(self, latency_ms: int) -> None:
        """Update status bar heartbeat based on C2 latency.
        
        Args:
            latency_ms: C2 latency in milliseconds.
        """
        try:
            status = self.get_heartbeat_status(latency_ms)
            self.heartbeat_status = status
            status_bar = self.query_one("#status-bar", StatusBarWidget)
            status_bar.update_heartbeat(status.value)
        except NoMatches:
            pass

    def _update_status_bar_auth_count(self, count: int) -> None:
        """Update status bar pending authorization count.
        
        Args:
            count: Number of pending auth requests.
        """
        try:
            status_bar = self.query_one("#status-bar", StatusBarWidget)
            status_bar.update_pending_auth(count)
        except NoMatches:
            pass


if __name__ == "__main__":
    app = CyberRedApp()
    app.run()
