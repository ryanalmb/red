from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input
from textual.containers import Horizontal, Vertical
from src.ui.widgets import HiveGrid, AttackTree, KillChainLog, TerminalLog, ThinkingLog
import asyncio
from src.core.event_bus import EventBus
from src.core.orchestrator import Orchestrator

class CyberRedApp(App):
    CSS_PATH = "style.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
        ("f5", "approvals", "Approvals"),
        ("p", "panic", "PANIC")
    ]

    def __init__(self, event_bus=None):
        super().__init__()
        self.bus = event_bus
        # Orchestrator handles Logic now

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

        yield Input(placeholder="Type command here (e.g., 'Scan 10.0.0.5')...", id="cmd-input")
        yield Footer()

    async def on_input_submitted(self, message: Input.Submitted):
        user_text = message.value
        self.query_one("#cmd-input", Input).value = ""
        self.notify(f"Analyzing: {user_text}...")
        
        # We don't have direct access to Council here (it's in Orchestrator)
        # But we can assume Orchestrator is listening to a different channel?
        # Actually, Orchestrator listens to 'job:new'. 
        # But we need to PARSE the intent first.
        # Ideally, we publish 'cmd:raw' and Orchestrator parses it.
        # But for MVP v2, let's just publish intent if we can parsing here, or publish raw text.
        # Let's publish raw command to 'cmd:input' and have Orchestrator handle parsing.
        
        # But Orchestrator logic in handle_new_job expects a dict.
        # Refactor: Move Intent Parsing to Orchestrator listening on 'cmd:input'.
        # For now, I'll cheat and assume I can't parse here without Council.
        # I'll publish to a special channel 'cmd:nlp' that Orchestrator picks up.
        
        if self.bus:
             await self.bus.publish("cmd:nlp", {"text": user_text})

    async def on_mount(self):
        if self.bus:
            asyncio.create_task(self.bus.subscribe("swarm:status", self.handle_status_update))
            asyncio.create_task(self.bus.subscribe("swarm:log", self.handle_log_update))
            asyncio.create_task(self.bus.subscribe("swarm:terminal", self.handle_terminal_update))
            asyncio.create_task(self.bus.subscribe("swarm:brain", self.handle_brain_update))

    async def handle_status_update(self, data: dict):
        grid = self.query_one("#hive-grid", HiveGrid)
        if data.get("agent_id"): grid.update_agent(data["agent_id"], data["status"])

    async def handle_log_update(self, data: dict):
        log = self.query_one("#kill-chain", KillChainLog)
        log.log_event(data.get("timestamp", "00:00"), data.get("category", "INFO"), data.get("message", ""))

    async def handle_terminal_update(self, data: dict):
        term = self.query_one("#terminal-stream", TerminalLog)
        term.log_stream(data.get("source", "Unknown"), data.get("text", ""))

    async def handle_brain_update(self, data: dict):
        brain = self.query_one("#brain-stream", ThinkingLog)
        brain.log_thought(data.get("category", "INFO"), data.get("text", ""))

    def action_panic(self):
        self.notify("PANIC TRIGGERED!", severity="error")
        if self.bus:
            asyncio.create_task(self.bus.publish("swarm:broadcast", {"command": "ABORT"}))

if __name__ == "__main__":
    app = CyberRedApp()
    app.run()
