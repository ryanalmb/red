from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Log, Tree, Button, Label
from textual.containers import Container, Grid, Horizontal
from textual.reactive import reactive
from textual.screen import ModalScreen

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
        if category == "AUTH": color = "yellow"
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


class AuthorizationModal(ModalScreen):
    """Modal dialog for HITL target authorization."""
    
    CSS = """
    AuthorizationModal {
        align: center middle;
    }
    
    #auth-dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $warning;
    }
    
    #auth-title {
        text-align: center;
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }
    
    #auth-message {
        text-align: center;
        margin-bottom: 1;
    }
    
    #auth-target {
        text-align: center;
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }
    
    #auth-buttons {
        align: center middle;
        height: auto;
    }
    
    #auth-buttons Button {
        margin: 0 1;
    }
    """
    
    def __init__(self, target: str, message: str, callback=None):
        super().__init__()
        self.target = target
        self.message = message
        self.callback = callback
    
    def compose(self) -> ComposeResult:
        with Container(id="auth-dialog"):
            yield Label("⚠️  TARGET AUTHORIZATION REQUIRED", id="auth-title")
            yield Label(self.message, id="auth-message")
            yield Label(f"Target: {self.target}", id="auth-target")
            with Horizontal(id="auth-buttons"):
                yield Button("✓ Approve", id="btn-approve", variant="success")
                yield Button("✓ Always", id="btn-always", variant="primary")
                yield Button("✗ Deny", id="btn-deny", variant="error")
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        
        if button_id == "btn-approve":
            result = {"target": self.target, "approved": True, "persist": False}
        elif button_id == "btn-always":
            result = {"target": self.target, "approved": True, "persist": True}
        else:  # btn-deny
            result = {"target": self.target, "approved": False, "persist": False}
        
        if self.callback:
            await self.callback(result)
        
        self.dismiss(result)

