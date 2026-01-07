"""Cyber-Red TUI Application.

The main Textual application for the Cyber-Red War Room interface.
Supports two modes:
1. Standalone mode: Uses EventBus for internal event streaming
2. Daemon mode: Uses TUIClient for daemon IPC streaming
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input
from textual.containers import Horizontal, Vertical
import asyncio

from cyberred.tui.widgets import (
    HiveGrid,
    AttackTree,
    KillChainLog,
    TerminalLog,
    ThinkingLog,
    AuthorizationModal,
)
from cyberred.daemon.streaming import StreamEventType

if TYPE_CHECKING:
    from cyberred.core.event_bus import EventBus
    from cyberred.tui.daemon_client import TUIClient


class CyberRedApp(App):
    """Cyber-Red War Room TUI Application.

    Supports two modes of operation:
    - Standalone: Uses EventBus for internal events (testing, demos)
    - Daemon: Uses TUIClient for daemon IPC streaming (production)
    """

    CSS_PATH = "style.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
        ("f5", "approvals", "Approvals"),
        ("p", "panic", "PANIC"),
        ("ctrl+d", "detach", "Detach"),
    ]

    def __init__(
        self,
        event_bus: Optional["EventBus"] = None,
        daemon_client: Optional["TUIClient"] = None,
        engagement_id: Optional[str] = None,
    ) -> None:
        """Initialize CyberRedApp.

        Args:
            event_bus: EventBus for standalone mode (optional).
            daemon_client: TUIClient for daemon mode (optional).
            engagement_id: Engagement ID when using daemon mode.

        Note:
            If daemon_client is provided, it takes precedence over event_bus.
        """
        super().__init__()
        self.bus = event_bus
        self._daemon_client = daemon_client
        self._engagement_id = engagement_id
        self._stream_task: Optional[asyncio.Task] = None

    @property
    def is_daemon_mode(self) -> bool:
        """Return True if using daemon client for events."""
        return self._daemon_client is not None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal():
            # Left: Target & Matrix
            with Vertical(id="pane-left"):
                yield Static("TARGETS", classes="pane-title")
                yield AttackTree("Scope")
                yield Static("HIVE STATUS", classes="pane-title")
                yield HiveGrid(id="hive-grid")

            # Middle: Brain Stream & Kill Chain
            with Vertical(id="pane-mid"):
                yield Static("BRAIN STREAM", classes="pane-title")
                yield ThinkingLog(id="brain-stream")
                yield Static("KILL CHAIN", classes="pane-title")
                yield KillChainLog(id="kill-chain")

            # Right: Terminal
            with Vertical(id="pane-right"):
                yield Static("TERMINAL STREAM", classes="pane-title")
                yield TerminalLog(id="terminal-stream")

        yield Input(
            placeholder="Type command here (e.g., 'Scan 10.0.0.5')...",
            id="cmd-input",
        )
        yield Footer()

    async def on_input_submitted(self, message: Input.Submitted) -> None:
        user_text = message.value
        self.query_one("#cmd-input", Input).value = ""
        self.notify(f"Analyzing: {user_text}...")

        # Handle 'detach' command
        if user_text.strip().lower() == "detach":
            await self.action_detach()
            return

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
        """Consume streaming events from daemon client."""
        if not self._daemon_client or not self._engagement_id:
            return

        try:
            async for event in self._daemon_client.attach(self._engagement_id):
                await self._handle_stream_event(event)
        except Exception as e:
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

    async def _handle_finding(self, data: dict) -> None:
        """Handle finding discovery event."""
        log = self.query_one("#kill-chain", KillChainLog)
        severity = data.get("severity", "INFO")
        finding_id = data.get("finding_id", "unknown")
        log.log_event("now", severity, f"Finding: {finding_id}")

    async def _handle_state_change(self, data: dict) -> None:
        """Handle engagement state change event."""
        state = data.get("state", "UNKNOWN")
        log = self.query_one("#kill-chain", KillChainLog)
        log.log_event("now", "STATE", f"Engagement: {state}")

        # Update hive grid with initial agent data if present
        agents = data.get("agents", [])
        grid = self.query_one("#hive-grid", HiveGrid)
        for agent in agents:
            agent_id = agent.get("id") or agent.get("agent_id")
            status = agent.get("status", "idle")
            if agent_id:
                grid.update_agent(agent_id, status)

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
        """Handle HITL authorization request - show modal dialog."""
        target = data.get("target", "Unknown")
        message = data.get("message", f"Authorize engagement with {target}?")

        log = self.query_one("#kill-chain", KillChainLog)
        log.log_event("now", "AUTH", f"Authorization requested for: {target}")

        async def send_response(result):
            if self.bus:
                await self.bus.publish("hitl:auth_response", result)
                decision = "APPROVED" if result.get("approved") else "DENIED"
                persist_msg = " (Always)" if result.get("persist") else ""
                log.log_event("now", "AUTH", f"Target {target}: {decision}{persist_msg}")

        modal = AuthorizationModal(target, message, callback=send_response)
        self.push_screen(modal)

    def action_panic(self) -> None:
        self.notify("PANIC TRIGGERED!", severity="error")
        if self.bus:
            asyncio.create_task(
                self.bus.publish("swarm:broadcast", {"command": "ABORT"})
            )

    async def action_detach(self) -> None:
        """Detach from daemon and exit TUI."""
        if self._daemon_client:
            self.notify("Detaching...")
            # Cancel stream task
            if self._stream_task and not self._stream_task.done():
                self._stream_task.cancel()
                try:
                    await self._stream_task
                except asyncio.CancelledError:
                    pass
            # Detach from engagement
            await self._daemon_client.detach()
        self.exit()


if __name__ == "__main__":
    app = CyberRedApp()
    app.run()
