"""Authorization Request Screen for HITL Authorization.

Story 10.1: Authorization Request Modal

Implements an interruptive modal for authorization requests with:
- Y/N/M/S keybindings (Yes/No/More info/Skip)
- Focus trap (modal captures all input)
- Swarm state snapshot display
- Risk assessment context
- Related findings summary
- Blink animation for pending auth (1s cycle)
- 3s cooldown on consecutive approvals
- "More Info" expansion with ATT&CK mapping
- Auth timeout with configurable auto-deny (default: 30min)
- Auth batching ("Approve all similar?")
- Latency measurement for NFR5 compliance (<500ms)
- Skip queue for deferred authorization

UX Spec References:
- Lines 302-306: Y/N/M/S Authorization Flow
- Lines 510: AuthorizationModal with swarm state snapshot
- Lines 562-563: Modal overlay focus trap
- Lines 604: Blink animation for pending auth (1s cycle)
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Collapsible, Checkbox
from textual.timer import Timer

if TYPE_CHECKING:
    from cyberred.core.models import Finding

# Logger for latency tracking (NFR5)
logger = logging.getLogger(__name__)

# Default auth timeout in seconds (30 minutes per UX spec)
DEFAULT_AUTH_TIMEOUT_SECONDS: float = 30 * 60  # 30 minutes


class AuthorizationType(StrEnum):
    """Type of authorization request."""
    LATERAL_MOVE = "lateral_move"
    SCOPE_EXPANSION = "scope_expansion"


class RiskLevel(StrEnum):
    """Risk level for authorization requests."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AuthorizationDecision(StrEnum):
    """Authorization decision options."""
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    SKIPPED = "SKIPPED"


@dataclass
class SwarmSnapshot:
    """Snapshot of swarm state at authorization request time.
    
    Attributes:
        timestamp: ISO 8601 timestamp of snapshot.
        total_agents: Total number of agents in swarm.
        by_status: Agent counts by status (idle, scanning, etc.).
        by_target: Agent counts by target network/host.
    """
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_agents: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_target: dict[str, int] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SwarmSnapshot":
        """Create SwarmSnapshot from dictionary.
        
        Args:
            data: Dictionary with snapshot data.
            
        Returns:
            SwarmSnapshot instance.
        """
        return cls(
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            total_agents=data.get("total_agents", 0),
            by_status=data.get("by_status", {}),
            by_target=data.get("by_target", {}),
        )


@dataclass
class AuthorizationRequest:
    """Authorization request from an agent.
    
    Attributes:
        id: Unique request identifier.
        request_type: Type of authorization (lateral_move, scope_expansion).
        agent_id: ID of requesting agent.
        target: Target IP/hostname.
        proposed_action: What the agent wants to do.
        risk_level: Risk assessment (LOW/MEDIUM/HIGH/CRITICAL).
        related_findings: Findings that led to this request.
        decision_context: Stigmergic signals influencing the request.
        timestamp: ISO 8601 request time.
        swarm_snapshot: Agent distribution at request time.
        attck_technique: MITRE ATT&CK technique ID if available.
        attck_tactic: MITRE ATT&CK tactic if available.
        origin_time_ns: Monotonic time (ns) when request was created at agent.
            Used for latency measurement (NFR5: <500ms delivery).
    """
    id: str
    request_type: str
    agent_id: str
    target: str
    proposed_action: str
    risk_level: str = RiskLevel.MEDIUM
    related_findings: list[dict[str, Any]] = field(default_factory=list)
    decision_context: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    swarm_snapshot: SwarmSnapshot | None = None
    attck_technique: str | None = None
    attck_tactic: str | None = None
    origin_time_ns: int | None = None  # Monotonic nanoseconds for latency tracking
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuthorizationRequest":
        """Create AuthorizationRequest from dictionary.
        
        Args:
            data: Dictionary with request data.
            
        Returns:
            AuthorizationRequest instance.
        """
        snapshot_data = data.get("swarm_snapshot")
        snapshot = SwarmSnapshot.from_dict(snapshot_data) if snapshot_data else None
        
        return cls(
            id=data.get("id", "unknown"),
            request_type=data.get("request_type", AuthorizationType.LATERAL_MOVE),
            agent_id=data.get("agent_id", "unknown"),
            target=data.get("target", "unknown"),
            proposed_action=data.get("proposed_action", "unknown action"),
            risk_level=data.get("risk_level", RiskLevel.MEDIUM),
            related_findings=data.get("related_findings", []),
            decision_context=data.get("decision_context", []),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            swarm_snapshot=snapshot,
            attck_technique=data.get("attck_technique"),
            attck_tactic=data.get("attck_tactic"),
            origin_time_ns=data.get("origin_time_ns"),
        )


@dataclass
class AuthorizationResponse:
    """Response to an authorization request.
    
    Attributes:
        request_id: ID of the original request.
        decision: Authorization decision (APPROVED/DENIED/SKIPPED).
        operator: Who made the decision.
        timestamp: ISO 8601 decision time.
        constraints: Optional constraints (time_limit, target_limit).
        batch_apply: Whether to apply to similar requests.
    """
    request_id: str
    decision: str
    operator: str = "operator"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    constraints: dict[str, Any] | None = None
    batch_apply: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for transmission.
        
        Returns:
            Dictionary representation.
        """
        return {
            "request_id": self.request_id,
            "decision": self.decision,
            "operator": self.operator,
            "timestamp": self.timestamp,
            "constraints": self.constraints,
            "batch_apply": self.batch_apply,
        }


class SwarmStateSnapshot(Static):
    """Widget displaying swarm state at authorization request time.
    
    Shows agent distribution by status with visual indicators.
    """
    
    DEFAULT_CSS: ClassVar[str] = """
    SwarmStateSnapshot {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        border: solid $primary;
    }
    
    SwarmStateSnapshot .snapshot-title {
        text-style: bold;
        color: $primary;
    }
    
    SwarmStateSnapshot .snapshot-row {
        height: 1;
    }
    """
    
    def __init__(
        self,
        snapshot: SwarmSnapshot | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize SwarmStateSnapshot widget.
        
        Args:
            snapshot: Swarm snapshot data to display.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._snapshot = snapshot
    
    def render(self) -> str:
        """Render the swarm snapshot display."""
        if not self._snapshot:
            return "[dim]No swarm data available[/dim]"
        
        lines = [
            "[bold]📊 Swarm State Snapshot[/bold]",
            f"Total Agents: {self._snapshot.total_agents}",
        ]
        
        # Status breakdown with colors
        status_colors = {
            "idle": "blue",
            "scanning": "cyan",
            "thinking": "magenta",
            "attacking": "yellow",
            "exploited": "green",
            "error": "red",
        }
        
        if self._snapshot.by_status:
            status_parts = []
            for status, count in self._snapshot.by_status.items():
                color = status_colors.get(status, "white")
                status_parts.append(f"[{color}]{status}:{count}[/{color}]")
            lines.append(" | ".join(status_parts))
        
        # Timestamp
        lines.append(f"[dim]@ {self._snapshot.timestamp[:19]}[/dim]")
        
        return "\n".join(lines)


class RiskAssessmentDisplay(Static):
    """Widget displaying risk assessment for authorization request.
    
    Shows target info, proposed action, risk level, and potential impact.
    """
    
    DEFAULT_CSS: ClassVar[str] = """
    RiskAssessmentDisplay {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        border: solid $warning;
    }
    
    RiskAssessmentDisplay.risk-low { border: solid $success; }
    RiskAssessmentDisplay.risk-medium { border: solid $warning; }
    RiskAssessmentDisplay.risk-high { border: solid $error; }
    RiskAssessmentDisplay.risk-critical { border: double $error; }
    """
    
    def __init__(
        self,
        request: AuthorizationRequest,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize RiskAssessmentDisplay widget.
        
        Args:
            request: Authorization request with risk data.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        # Set risk class before super().__init__
        risk_class = f"risk-{request.risk_level.lower()}"
        combined_classes = f"{classes} {risk_class}" if classes else risk_class
        super().__init__(name=name, id=id, classes=combined_classes)
        self._request = request
    
    def render(self) -> str:
        """Render the risk assessment display."""
        risk_colors = {
            RiskLevel.LOW: "green",
            RiskLevel.MEDIUM: "yellow",
            RiskLevel.HIGH: "red",
            RiskLevel.CRITICAL: "bold red",
        }
        risk_icons = {
            RiskLevel.LOW: "🟢",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🔴",
            RiskLevel.CRITICAL: "⚠️",
        }
        
        risk = self._request.risk_level
        color = risk_colors.get(risk, "white")
        icon = risk_icons.get(risk, "⚪")
        
        # Format request type nicely
        req_type = self._request.request_type.replace("_", " ").title()
        
        lines = [
            f"[bold]🎯 {req_type}[/bold]",
            f"Target: [bold]{self._request.target}[/bold]",
            f"Action: {self._request.proposed_action}",
            f"Risk: {icon} [{color}]{risk}[/{color}]",
            f"Agent: {self._request.agent_id}",
        ]
        
        return "\n".join(lines)


class RelatedFindingsDisplay(Static):
    """Widget displaying related findings that led to this request."""
    
    DEFAULT_CSS: ClassVar[str] = """
    RelatedFindingsDisplay {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
    }
    """
    
    def __init__(
        self,
        findings: list[dict[str, Any]],
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize RelatedFindingsDisplay widget.
        
        Args:
            findings: List of related findings.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._findings = findings[:5]  # Show max 5 findings
    
    def render(self) -> str:
        """Render the related findings display."""
        if not self._findings:
            return "[dim]No related findings[/dim]"
        
        lines = ["[bold]📋 Related Findings[/bold]"]
        
        severity_colors = {
            "CRITICAL": "bold red",
            "HIGH": "red",
            "MEDIUM": "yellow",
            "LOW": "green",
            "INFO": "blue",
        }
        
        for finding in self._findings:
            severity = finding.get("severity", "INFO")
            color = severity_colors.get(severity, "white")
            title = finding.get("title", finding.get("finding_id", "Unknown"))
            if len(title) > 40:
                title = title[:37] + "..."
            lines.append(f"  [{color}]•[/{color}] {title}")
        
        return "\n".join(lines)


class MoreInfoSection(Static):
    """Expandable section with detailed authorization context.
    
    Shows finding chain, agent reasoning, and ATT&CK mapping.
    """
    
    DEFAULT_CSS: ClassVar[str] = """
    MoreInfoSection {
        height: auto;
        padding: 1;
        margin-top: 1;
        background: $surface-darken-1;
        border: dashed $primary;
    }
    """
    
    def __init__(
        self,
        request: AuthorizationRequest,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize MoreInfoSection widget.
        
        Args:
            request: Authorization request with detailed context.
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._request = request
    
    def render(self) -> str:
        """Render the more info section."""
        lines = ["[bold]📖 Detailed Context[/bold]", ""]
        
        # ATT&CK mapping
        if self._request.attck_technique or self._request.attck_tactic:
            lines.append("[bold]MITRE ATT&CK:[/bold]")
            if self._request.attck_tactic:
                lines.append(f"  Tactic: {self._request.attck_tactic}")
            if self._request.attck_technique:
                lines.append(f"  Technique: {self._request.attck_technique}")
            lines.append("")
        
        # Decision context (stigmergic signals)
        if self._request.decision_context:
            lines.append("[bold]Agent Reasoning:[/bold]")
            for ctx in self._request.decision_context[:5]:
                lines.append(f"  • {ctx}")
            lines.append("")
        
        # Finding chain
        if self._request.related_findings:
            lines.append("[bold]Finding Chain:[/bold]")
            for i, finding in enumerate(self._request.related_findings[:5], 1):
                title = finding.get("title", finding.get("finding_id", "Unknown"))
                lines.append(f"  {i}. {title}")
        
        if len(lines) == 2:  # Only header
            lines.append("[dim]No additional context available[/dim]")
        
        return "\n".join(lines)


class AuthorizationScreen(ModalScreen[dict[str, Any]]):
    """Enhanced authorization request modal screen.
    
    Story 10.1: Implements interruptive modal for authorization requests with:
    - Y/N/M/S keybindings (Yes/No/More info/Skip)
    - Focus trap (built into ModalScreen)
    - Swarm state snapshot display
    - Risk assessment context
    - Blink animation for pending auth (1s cycle)
    - 3s cooldown on consecutive approvals
    - Auth timeout with configurable auto-deny (default: 30min)
    - Auth batching ("Approve all similar?")
    - Latency measurement for NFR5 (<500ms delivery)
    - Skip queue for deferred authorization
    
    UX Spec References:
    - Lines 302-306: Y/N/M/S quick responses
    - Lines 510: AuthorizationModal spec
    - Lines 562-563: Modal overlay focus trap
    - Lines 604: Blink animation (1s cycle)
    """
    
    TITLE = "Authorization Required"
    
    BINDINGS = [
        Binding("y", "approve", "Yes - Approve", show=True, priority=True),
        Binding("n", "deny", "No - Deny", show=True, priority=True),
        Binding("m", "more_info", "More Info", show=True, priority=True),
        Binding("s", "skip", "Skip for now", show=True, priority=True),
        Binding("b", "toggle_batch", "Batch Apply", show=True, priority=True),
    ]
    
    DEFAULT_CSS: ClassVar[str] = """
    AuthorizationScreen {
        align: center middle;
    }
    
    AuthorizationScreen > #auth-container {
        width: 80;
        max-width: 90%;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        background: $surface;
        border: thick $warning;
    }
    
    AuthorizationScreen #auth-title {
        text-align: center;
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }
    
    AuthorizationScreen #auth-title.blink-on {
        background: $warning;
        color: $surface;
    }
    
    AuthorizationScreen .button-row {
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    
    AuthorizationScreen Button {
        margin: 0 1;
    }
    
    AuthorizationScreen #cooldown-indicator {
        text-align: center;
        color: $error;
        height: 1;
        margin-top: 1;
    }
    
    AuthorizationScreen #timeout-indicator {
        text-align: center;
        color: $warning;
        height: 1;
        margin-top: 1;
    }
    
    AuthorizationScreen #latency-indicator {
        text-align: center;
        color: $success;
        height: 1;
    }
    
    AuthorizationScreen #more-info-container {
        height: auto;
        display: none;
    }
    
    AuthorizationScreen #more-info-container.expanded {
        display: block;
    }
    
    AuthorizationScreen #batch-container {
        height: auto;
        margin-top: 1;
        padding: 0 1;
        border: dashed $primary;
    }
    """
    
    # Reactive properties
    blink_state: reactive[bool] = reactive(False)
    cooldown_remaining: reactive[float] = reactive(0.0)
    more_info_expanded: reactive[bool] = reactive(False)
    timeout_remaining: reactive[float] = reactive(0.0)
    batch_apply: reactive[bool] = reactive(False)
    
    # Class-level cooldown tracking for consecutive approvals
    _last_approval_time: ClassVar[float] = 0.0
    COOLDOWN_SECONDS: ClassVar[float] = 3.0
    
    # Class-level skip queue (shared across instances for Story 10.3)
    _skip_queue: ClassVar[list["AuthorizationRequest"]] = []
    _skip_count: ClassVar[int] = 0
    
    def __init__(
        self,
        request: AuthorizationRequest | dict[str, Any],
        callback: Callable[[dict[str, Any]], Any] | None = None,
        timeout_seconds: float = DEFAULT_AUTH_TIMEOUT_SECONDS,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize AuthorizationScreen.
        
        Args:
            request: Authorization request data (AuthorizationRequest or dict).
            callback: Callback function for response.
            timeout_seconds: Auto-deny timeout in seconds (default: 30 minutes).
            name: Widget name.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        
        if isinstance(request, dict):
            self._request = AuthorizationRequest.from_dict(request)
        else:
            self._request = request
        
        self._callback = callback
        self._timeout_seconds = timeout_seconds
        self._blink_timer: Timer | None = None
        self._cooldown_timer: Timer | None = None
        self._timeout_timer: Timer | None = None
        self._delivery_latency_ms: float | None = None
        
        # Measure delivery latency (NFR5: <500ms)
        self._measure_delivery_latency()
    
    def _measure_delivery_latency(self) -> None:
        """Measure and log delivery latency for NFR5 compliance.
        
        NFR5 requires <500ms from agent request to modal display.
        """
        if self._request.origin_time_ns is not None:
            now_ns = time.monotonic_ns()
            latency_ns = now_ns - self._request.origin_time_ns
            self._delivery_latency_ms = latency_ns / 1_000_000  # Convert to ms
            
            # Log for monitoring
            if self._delivery_latency_ms < 500:
                logger.info(
                    "Auth request delivery latency: %.2fms (NFR5 PASS)",
                    self._delivery_latency_ms
                )
            else:
                logger.warning(
                    "Auth request delivery latency: %.2fms (NFR5 FAIL - exceeds 500ms)",
                    self._delivery_latency_ms
                )
        else:
            self._delivery_latency_ms = None
            logger.debug("Auth request missing origin_time_ns, cannot measure latency")
    
    @property
    def delivery_latency_ms(self) -> float | None:
        """Get the measured delivery latency in milliseconds.
        
        Returns:
            Delivery latency in ms, or None if not measured.
        """
        return self._delivery_latency_ms
    
    @classmethod
    def get_skip_queue(cls) -> list["AuthorizationRequest"]:
        """Get the class-level skip queue for deferred authorizations.
        
        Used by Story 10.3 for pending authorization management.
        
        Returns:
            List of skipped authorization requests.
        """
        return cls._skip_queue.copy()
    
    @classmethod
    def get_skip_count(cls) -> int:
        """Get the total number of times skip has been used.
        
        Returns:
            Total skip count across all instances.
        """
        return cls._skip_count
    
    @classmethod
    def clear_skip_queue(cls) -> None:
        """Clear the skip queue (for testing or after processing)."""
        cls._skip_queue.clear()
        cls._skip_count = 0
    
    def compose(self) -> ComposeResult:
        """Compose the authorization modal layout."""
        with Container(id="auth-container"):
            yield Static(
                "⚠️  AUTHORIZATION REQUIRED  ⚠️",
                id="auth-title",
            )
            
            # Latency indicator (NFR5)
            latency_text = ""
            if self._delivery_latency_ms is not None:
                if self._delivery_latency_ms < 500:
                    latency_text = f"[green]Delivered in {self._delivery_latency_ms:.0f}ms ✓[/green]"
                else:
                    latency_text = f"[red]Delivered in {self._delivery_latency_ms:.0f}ms (slow)[/red]"
            yield Static(latency_text, id="latency-indicator")
            
            # Risk assessment (target, action, risk level)
            yield RiskAssessmentDisplay(self._request, id="risk-display")
            
            # Swarm state snapshot
            yield SwarmStateSnapshot(
                self._request.swarm_snapshot,
                id="swarm-snapshot",
            )
            
            # Related findings
            yield RelatedFindingsDisplay(
                self._request.related_findings,
                id="findings-display",
            )
            
            # More info section (hidden by default)
            with Container(id="more-info-container"):
                yield MoreInfoSection(self._request, id="more-info")
            
            # Batch apply option (UX Spec line 510: "Approve all similar?")
            with Container(id="batch-container"):
                yield Static(
                    "[B] Apply to all similar requests?",
                    id="batch-label",
                )
                yield Static("", id="batch-status")
            
            # Timeout indicator (auto-deny countdown)
            yield Static("", id="timeout-indicator")
            
            # Cooldown indicator
            yield Static("", id="cooldown-indicator")
            
            # Action buttons
            with Horizontal(classes="button-row"):
                yield Button("[Y]es Approve", id="btn-approve", variant="success")
                yield Button("[N]o Deny", id="btn-deny", variant="error")
                yield Button("[M]ore Info", id="btn-more", variant="default")
                yield Button("[S]kip", id="btn-skip", variant="warning")
    
    def on_mount(self) -> None:
        """Start blink animation and timeout on mount."""
        # Start 1s blink cycle per UX spec
        self._blink_timer = self.set_interval(1.0, self._toggle_blink)
        
        # Check if we're in cooldown from previous approval
        self._check_cooldown()
        
        # Start timeout countdown (UX Spec line 510: 30min auto-deny)
        self._start_timeout()
    
    def on_unmount(self) -> None:
        """Clean up timers on unmount."""
        if self._blink_timer:
            self._blink_timer.stop()
        if self._cooldown_timer:
            self._cooldown_timer.stop()
        if self._timeout_timer:
            self._timeout_timer.stop()
    
    def _toggle_blink(self) -> None:
        """Toggle blink state for animation."""
        self.blink_state = not self.blink_state
    
    def watch_blink_state(self, blink: bool) -> None:
        """Update title styling based on blink state."""
        try:
            title = self.query_one("#auth-title", Static)
            if blink:
                title.add_class("blink-on")
            else:
                title.remove_class("blink-on")
        except Exception:
            pass
    
    def _check_cooldown(self) -> None:
        """Check and display cooldown from previous approval."""
        import time
        
        now = time.monotonic()
        elapsed = now - AuthorizationScreen._last_approval_time
        
        if elapsed < self.COOLDOWN_SECONDS:
            self.cooldown_remaining = self.COOLDOWN_SECONDS - elapsed
            self._start_cooldown_timer()
    
    def _start_cooldown_timer(self) -> None:
        """Start cooldown countdown timer."""
        self._cooldown_timer = self.set_interval(0.1, self._update_cooldown)
        self._update_cooldown_display()
        
        # Disable approve button during cooldown
        try:
            btn = self.query_one("#btn-approve", Button)
            btn.disabled = True
        except Exception:
            pass
    
    def _update_cooldown(self) -> None:
        """Update cooldown remaining."""
        self.cooldown_remaining = max(0.0, self.cooldown_remaining - 0.1)
        self._update_cooldown_display()
        
        if self.cooldown_remaining <= 0:
            if self._cooldown_timer:
                self._cooldown_timer.stop()
                self._cooldown_timer = None
            
            # Re-enable approve button
            try:
                btn = self.query_one("#btn-approve", Button)
                btn.disabled = False
            except Exception:
                pass
    
    def _update_cooldown_display(self) -> None:
        """Update cooldown indicator display."""
        try:
            indicator = self.query_one("#cooldown-indicator", Static)
            if self.cooldown_remaining > 0:
                indicator.update(
                    f"⏱️ Cooldown: {self.cooldown_remaining:.1f}s remaining"
                )
            else:
                indicator.update("")
        except Exception:
            pass
    
    def watch_more_info_expanded(self, expanded: bool) -> None:
        """Toggle more info section visibility."""
        try:
            container = self.query_one("#more-info-container", Container)
            if expanded:
                container.add_class("expanded")
            else:
                container.remove_class("expanded")
        except Exception:
            pass
    
    def watch_batch_apply(self, batch: bool) -> None:
        """Update batch status display."""
        try:
            status = self.query_one("#batch-status", Static)
            if batch:
                status.update("[green]✓ Will apply to similar requests[/green]")
            else:
                status.update("[dim]No batch apply[/dim]")
        except Exception:
            pass
    
    def _start_timeout(self) -> None:
        """Start the auto-deny timeout countdown.
        
        Per UX Spec line 510: Configurable auth timeout (default: 30min auto-deny).
        """
        self.timeout_remaining = self._timeout_seconds
        self._timeout_timer = self.set_interval(1.0, self._update_timeout)
        self._update_timeout_display()
    
    def _update_timeout(self) -> None:
        """Update timeout countdown."""
        self.timeout_remaining = max(0.0, self.timeout_remaining - 1.0)
        self._update_timeout_display()
        
        if self.timeout_remaining <= 0:
            # Auto-deny on timeout
            logger.warning(
                "Auth request %s auto-denied after %.0fs timeout",
                self._request.id,
                self._timeout_seconds
            )
            self._send_response(AuthorizationDecision.DENIED, auto_denied=True)
    
    def _update_timeout_display(self) -> None:
        """Update timeout indicator display."""
        try:
            indicator = self.query_one("#timeout-indicator", Static)
            if self.timeout_remaining > 0:
                minutes = int(self.timeout_remaining // 60)
                seconds = int(self.timeout_remaining % 60)
                if self.timeout_remaining <= 60:
                    # Warning color when < 1 minute
                    indicator.update(
                        f"[bold red]⏰ Auto-deny in {seconds}s[/bold red]"
                    )
                elif self.timeout_remaining <= 300:
                    # Warning when < 5 minutes
                    indicator.update(
                        f"[yellow]⏰ Auto-deny in {minutes}m {seconds}s[/yellow]"
                    )
                else:
                    indicator.update(
                        f"[dim]⏰ Timeout: {minutes}m {seconds}s[/dim]"
                    )
            else:
                indicator.update("[bold red]⏰ TIMED OUT[/bold red]")
        except Exception:
            pass
    
    def action_toggle_batch(self) -> None:
        """Toggle batch apply option (B key)."""
        self.batch_apply = not self.batch_apply
    
    def action_approve(self) -> None:
        """Approve the authorization request (Y key)."""
        import time
        
        # Check cooldown
        if self.cooldown_remaining > 0:
            self.app.bell()  # Audio feedback that action is blocked
            return
        
        # Set last approval time for cooldown
        AuthorizationScreen._last_approval_time = time.monotonic()
        
        self._send_response(AuthorizationDecision.APPROVED)
    
    def action_deny(self) -> None:
        """Deny the authorization request (N key)."""
        self._send_response(AuthorizationDecision.DENIED)
    
    def action_more_info(self) -> None:
        """Toggle more info section (M key)."""
        self.more_info_expanded = not self.more_info_expanded
    
    def action_skip(self) -> None:
        """Skip this request for later (S key).
        
        Adds the request to the skip queue for Story 10.3 processing
        and increments the skip count for tracking.
        """
        # Add to class-level skip queue for Story 10.3
        AuthorizationScreen._skip_queue.append(self._request)
        AuthorizationScreen._skip_count += 1
        
        logger.info(
            "Auth request %s skipped (total skips: %d, queue size: %d)",
            self._request.id,
            AuthorizationScreen._skip_count,
            len(AuthorizationScreen._skip_queue)
        )
        
        self._send_response(AuthorizationDecision.SKIPPED)
    
    def _send_response(
        self,
        decision: AuthorizationDecision,
        auto_denied: bool = False,
    ) -> None:
        """Send authorization response and dismiss modal.
        
        Args:
            decision: The authorization decision.
            auto_denied: Whether this was an automatic denial due to timeout.
        """
        response = AuthorizationResponse(
            request_id=self._request.id,
            decision=decision,
            batch_apply=self.batch_apply,
        )
        
        result = response.to_dict()
        
        # Also include original request info for context
        result["target"] = self._request.target
        result["agent_id"] = self._request.agent_id
        result["approved"] = decision == AuthorizationDecision.APPROVED
        result["skipped"] = decision == AuthorizationDecision.SKIPPED
        result["auto_denied"] = auto_denied
        result["batch_apply"] = self.batch_apply
        
        # Include latency measurement if available
        if self._delivery_latency_ms is not None:
            result["delivery_latency_ms"] = self._delivery_latency_ms
        
        if self._callback:
            # Handle both sync and async callbacks
            if asyncio.iscoroutinefunction(self._callback):
                asyncio.create_task(self._callback(result))
            else:
                self._callback(result)
        
        self.dismiss(result)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.
        
        Args:
            event: Button pressed event.
        """
        button_id = event.button.id
        
        if button_id == "btn-approve":
            self.action_approve()
        elif button_id == "btn-deny":
            self.action_deny()
        elif button_id == "btn-more":
            self.action_more_info()
        elif button_id == "btn-skip":
            self.action_skip()


# Backward compatibility alias
AuthorizationModal = AuthorizationScreen
