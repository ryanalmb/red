from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Log, Tree
from textual.containers import Container, Grid
from textual.reactive import reactive

class HiveGrid(Grid):
    def compose(self) -> ComposeResult:
        for i in range(1, 101):
            yield Static(f"{i:02}", id=f"agent-{i}", classes="agent-block")

    def update_agent(self, agent_id: int, status: str):
        widget = self.query_one(f"#agent-{agent_id}")
        widget.remove_class("status-idle", "status-scanning", "status-thinking", "status-attacking", "status-paused")
        widget.add_class(f"status-{status}")

class AttackTree(Tree):
    pass

class KillChainLog(Log):
    def log_event(self, timestamp, category, message):
        color = "white"
        if category == "CRITIC": color = "orange"
        if category == "SUCCESS": color = "green"
        if category == "FAIL": color = "red"
        self.write(f"[{timestamp}] [{color}]{category}[/{color}]: {message}")

class TerminalLog(Log):
    def log_stream(self, source, text):
        self.write(f"[{source}] {text}")

class ThinkingLog(Log):
    """Streams the internal monologue of the AI."""
    def log_thought(self, category, text):
        color = "cyan"
        if category == "THINKING": color = "magenta"
        if category == "STRATEGY": color = "blue"
        if category == "CODE": color = "green"
        self.write(f"[{color}]{category}[/{color}]: {text}")
