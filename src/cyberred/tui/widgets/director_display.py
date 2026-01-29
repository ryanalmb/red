"""Director Ensemble Display Widget for TUI.

Story 8.11: Director Ensemble TUI Display.

Displays three Director perspectives and unified synthesis:
- Strategist (DeepSeek): Strategic recommendations, ATT&CK techniques
- Analyst (Kimi K2): Attack surface analysis, security gaps
- Creative (MiniMax): Creative alternatives, evasion techniques
- Unified: Synthesized strategy with objectives and actions

Per FR10: Operators can view strategic reasoning behind decisions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import structlog
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Collapsible, Static

from cyberred.llm.ensemble import (
    ATTCKRecommendation,
    CreativeAlternative,
    DegradationLevel,
    DirectorRole,
    SynthesizedStrategy,
)

if TYPE_CHECKING:
    from cyberred.tui.daemon_client import TUIClient

log = structlog.get_logger()


@dataclass
class DirectorPerspective:
    """Single Director model perspective for display.
    
    Story 11.1: Enhanced with per-perspective structured data display.
    
    Attributes:
        role: The Director role (STRATEGIST, ANALYST, CREATIVE).
        content: The model's response content.
        latency_ms: Response latency in milliseconds.
        success: Whether the query succeeded.
        error: Error message if query failed.
        thinking_content: Extracted <think> tags content for creative role.
        confidence: Per-perspective confidence score (0.0-1.0).
        recommendations: List of recommendations (strategist role).
        rationale: Rationale text for this perspective.
        attck_techniques: ATT&CK techniques (strategist role).
        security_gaps: Security gaps identified (analyst role).
        risk_level: Overall risk level (analyst role).
        alternatives: Creative alternatives (creative role).
    """
    role: DirectorRole
    content: str
    latency_ms: int
    success: bool
    error: Optional[str] = None
    thinking_content: Optional[str] = None
    # Story 11.1: Per-perspective structured fields
    confidence: Optional[float] = None
    recommendations: List[str] = field(default_factory=list)
    rationale: Optional[str] = None
    attck_techniques: List[Dict[str, str]] = field(default_factory=list)
    security_gaps: List[Dict[str, str]] = field(default_factory=list)
    risk_level: Optional[str] = None
    alternatives: List[Dict[str, Any]] = field(default_factory=list)


def extract_thinking_content(content: Optional[str]) -> Tuple[str, str]:
    """Extract <think>...</think> content from response.
    
    Args:
        content: Raw response content that may contain <think> tags.
            Can be None or empty string.
        
    Returns:
        Tuple of (thinking_content, cleaned_content) where:
        - thinking_content: All extracted <think> block contents joined
        - cleaned_content: Original content with <think> blocks removed
    """
    if content is None or content == "":
        return "", ""
    
    # Find all <think>...</think> blocks
    pattern = r"<think>(.*?)</think>"
    matches = re.findall(pattern, content, re.DOTALL)
    
    # Join all thinking content
    thinking = "\n".join(m.strip() for m in matches if m.strip())
    
    # Remove <think> blocks from content
    cleaned = re.sub(pattern, "", content, flags=re.DOTALL)
    cleaned = cleaned.strip()
    
    return thinking, cleaned


def parse_strategy_from_dict(data: Dict[str, Any]) -> SynthesizedStrategy:
    """Parse SynthesizedStrategy from dictionary data.
    
    Args:
        data: Dictionary from JSON/Redis containing strategy fields.
        
    Returns:
        SynthesizedStrategy instance with parsed data.
    """
    # Parse contributing roles
    contributing_roles = []
    for role_str in data.get("contributing_roles", []):
        try:
            contributing_roles.append(DirectorRole(role_str))
        except ValueError:
            log.warning("unknown_director_role", role=role_str)
    
    # Parse degradation level
    degradation_str = data.get("degradation_level", "full")
    try:
        degradation_level = DegradationLevel(degradation_str)
    except ValueError:
        degradation_level = DegradationLevel.FULL
    
    # Parse missing perspectives
    missing_perspectives = []
    for role_str in data.get("missing_perspectives", []):
        try:
            missing_perspectives.append(DirectorRole(role_str))
        except ValueError:
            pass
    
    # Parse ATT&CK techniques
    attck_techniques = []
    for tech_data in data.get("attck_techniques", []):
        attck_techniques.append(ATTCKRecommendation(
            technique_id=tech_data.get("technique_id", ""),
            technique_name=tech_data.get("technique_name", ""),
            rationale=tech_data.get("rationale", ""),
            phase=tech_data.get("phase", ""),
        ))
    
    # Parse creative alternatives
    creative_alternatives = []
    for alt_data in data.get("creative_alternatives", []):
        creative_alternatives.append(CreativeAlternative(
            alternative_id=alt_data.get("alternative_id", ""),
            description=alt_data.get("description", ""),
            rationale=alt_data.get("rationale", ""),
            novelty_score=alt_data.get("novelty_score", 0.0),
        ))
    
    return SynthesizedStrategy(
        objectives=data.get("objectives", []),
        actions=data.get("actions", []),
        rationale=data.get("rationale", ""),
        confidence=data.get("confidence", 0.0),
        contributing_roles=contributing_roles,
        avoid_list=data.get("avoid_list", []),
        attck_techniques=attck_techniques,
        creative_alternatives=creative_alternatives,
        risk_warnings=data.get("risk_warnings", []),
        conflicts_resolved=[],  # Complex parsing skipped for display
        degradation_level=degradation_level,
        missing_perspectives=missing_perspectives,
        fallback_warnings=data.get("fallback_warnings", []),
    )


# Role display names and model info
ROLE_INFO = {
    DirectorRole.STRATEGIST: ("Strategist", "DeepSeek V3.2", "blue"),
    DirectorRole.ANALYST: ("Analyst", "Kimi K2", "cyan"),
    DirectorRole.CREATIVE: ("Creative", "MiniMax M2", "magenta"),
}


class DirectorDisplayWidget(Static):
    """Director Ensemble Display Widget for TUI (FR10).
    
    Displays three Director perspectives and unified synthesis:
    - Strategist (DeepSeek): Strategic recommendations, ATT&CK techniques
    - Analyst (Kimi K2): Attack surface analysis, security gaps
    - Creative (MiniMax): Creative alternatives, evasion techniques
    - Unified: Synthesized strategy with objectives and actions
    
    Attributes:
        show_thinking: Toggle for <think> tags visibility (debug mode).
        strategist_expanded: Expand/collapse state for strategist section.
        analyst_expanded: Expand/collapse state for analyst section.
        creative_expanded: Expand/collapse state for creative section.
    """
    
    # Reactive properties for automatic UI updates
    show_thinking = reactive(False)
    strategist_expanded = reactive(True)
    analyst_expanded = reactive(True)
    creative_expanded = reactive(True)
    
    def __init__(self, daemon_client: Optional["TUIClient"] = None) -> None:
        """Initialize DirectorDisplayWidget.
        
        Args:
            daemon_client: Optional TUIClient for daemon mode streaming.
        """
        super().__init__()
        self._daemon_client = daemon_client
        self._current_strategy: Optional[SynthesizedStrategy] = None
        self._perspectives: Dict[DirectorRole, DirectorPerspective] = {}
        self._log = log.bind(widget="director_display")
    
    def compose(self) -> ComposeResult:
        """Compose the widget layout."""
        with Container(id="director-display"):
            yield Static("⚔️ DIRECTOR ENSEMBLE", id="director-title")
            
            # Unified strategy section at top
            yield Static("", id="unified-strategy", classes="unified-strategy")
            
            # Degradation warning (hidden by default)
            yield Static("", id="degradation-warning", classes="degradation-warning")
            
            # Three perspective sections
            with Collapsible(title=self._render_perspective_header(DirectorRole.STRATEGIST),
                           id="strategist-section", collapsed=False):
                yield Static("", id="strategist-content", classes="perspective-strategist")
            
            with Collapsible(title=self._render_perspective_header(DirectorRole.ANALYST),
                           id="analyst-section", collapsed=False):
                yield Static("", id="analyst-content", classes="perspective-analyst")
            
            with Collapsible(title=self._render_perspective_header(DirectorRole.CREATIVE),
                           id="creative-section", collapsed=False):
                yield Static("", id="creative-content", classes="perspective-creative")
                yield Static("", id="thinking-content", classes="thinking-content")
    
    def on_mount(self) -> None:
        """Handle widget mount - show placeholder if no strategy."""
        self._update_display()
    
    def _render_perspective_header(self, role: DirectorRole) -> str:
        """Render header for a perspective section.
        
        Args:
            role: The Director role.
            
        Returns:
            Formatted header string with role name and model.
        """
        name, model, _ = ROLE_INFO[role]
        return f"{name} ({model})"
    
    def _render_content_or_placeholder(self) -> str:
        """Render placeholder when no strategy exists.
        
        Returns:
            Placeholder message string.
        """
        return "⏳ Awaiting Director synthesis..."
    
    def _get_confidence_class(self, confidence: float) -> str:
        """Get CSS class for confidence level.
        
        Args:
            confidence: Confidence score (0.0-1.0).
            
        Returns:
            CSS class name for confidence color coding.
        """
        if confidence >= 0.75:
            return "confidence-high"
        elif confidence >= 0.5:
            return "confidence-medium"
        else:
            return "confidence-low"
    
    def _get_degradation_message(
        self,
        level: DegradationLevel,
        missing: List[DirectorRole],
    ) -> str:
        """Get degradation warning message.
        
        Args:
            level: Current degradation level.
            missing: List of missing/unavailable roles.
            
        Returns:
            Warning message string (empty if full availability).
        """
        if level == DegradationLevel.FULL:
            return ""
        
        missing_names = [ROLE_INFO[r][0] for r in missing]
        return f"⚠️ Degraded Mode: {', '.join(missing_names)} unavailable"
    
    def _format_attck_techniques(
        self,
        techniques: List[ATTCKRecommendation],
    ) -> str:
        """Format ATT&CK techniques for display.
        
        Args:
            techniques: List of ATT&CK recommendations.
            
        Returns:
            Formatted string with technique details.
        """
        if not techniques:
            return "No ATT&CK techniques recommended"
        
        lines = ["📋 ATT&CK Techniques:"]
        for tech in techniques:
            lines.append(f"  • {tech.technique_id} - {tech.technique_name}")
            if tech.rationale:
                lines.append(f"    └─ {tech.rationale}")
        return "\n".join(lines)
    
    def _format_creative_alternatives(
        self,
        alternatives: List[CreativeAlternative],
    ) -> str:
        """Format creative alternatives for display.
        
        Args:
            alternatives: List of creative alternatives.
            
        Returns:
            Formatted string with alternative details.
        """
        if not alternatives:
            return "No creative alternatives proposed"
        
        lines = ["💡 Creative Alternatives:"]
        for alt in alternatives:
            novelty = f"[{alt.novelty_score:.0%}]" if alt.novelty_score else ""
            lines.append(f"  • {alt.alternative_id}: {alt.description} {novelty}")
            if alt.rationale:
                lines.append(f"    └─ {alt.rationale}")
        return "\n".join(lines)
    
    def _update_display(self) -> None:
        """Update the display with current strategy data."""
        try:
            # Update unified strategy section
            unified_widget = self.query_one("#unified-strategy", Static)
            if self._current_strategy:
                unified_content = self._render_unified_strategy()
                unified_widget.update(unified_content)
            else:
                unified_widget.update(self._render_content_or_placeholder())
            
            # Update degradation warning
            warning_widget = self.query_one("#degradation-warning", Static)
            if self._current_strategy:
                warning = self._get_degradation_message(
                    self._current_strategy.degradation_level,
                    self._current_strategy.missing_perspectives,
                )
                warning_widget.update(warning)
            else:
                warning_widget.update("")
            
            # Update perspective sections
            self._update_perspective_section(DirectorRole.STRATEGIST, "strategist-content")
            self._update_perspective_section(DirectorRole.ANALYST, "analyst-content")
            self._update_perspective_section(DirectorRole.CREATIVE, "creative-content")
            
            # Update thinking content visibility
            self._update_thinking_display()
            
        except Exception as e:
            self._log.error("display_update_failed", error=str(e))
    
    def _render_unified_strategy(self) -> str:
        """Render the unified strategy section.
        
        Returns:
            Formatted unified strategy string.
        """
        if not self._current_strategy:
            return ""
        
        s = self._current_strategy
        confidence_class = self._get_confidence_class(s.confidence)
        
        lines = [
            "═══ UNIFIED STRATEGY ═══",
            "",
            f"Confidence: {s.confidence:.0%} [{confidence_class.split('-')[-1].upper()}]",
            "",
        ]
        
        if s.objectives:
            lines.append("🎯 Objectives:")
            for obj in s.objectives:
                lines.append(f"  • {obj}")
            lines.append("")
        
        if s.actions:
            lines.append("⚡ Actions:")
            for i, action in enumerate(s.actions, 1):
                lines.append(f"  {i}. {action}")
            lines.append("")
        
        if s.rationale:
            lines.append(f"📝 Rationale: {s.rationale}")
            lines.append("")
        
        if s.risk_warnings:
            lines.append("⚠️ Risk Warnings:")
            for warning in s.risk_warnings:
                lines.append(f"  • {warning}")
        
        return "\n".join(lines)
    
    def _update_perspective_section(self, role: DirectorRole, content_id: str) -> None:
        """Update a perspective section with current data.
        
        Story 11.1: Enhanced to show recommendations, rationale, confidence per perspective.
        
        Args:
            role: The Director role.
            content_id: The DOM ID of the content widget.
        """
        try:
            content_widget = self.query_one(f"#{content_id}", Static)
            
            perspective = self._perspectives.get(role)
            if perspective and perspective.success:
                # Story 11.1: Render structured perspective data
                content = self._render_perspective_content(perspective)
                content_widget.update(content)
            elif perspective and not perspective.success:
                content_widget.update(f"❌ Error: {perspective.error or 'Unknown error'}")
            else:
                content_widget.update("No data available")
                
        except Exception as e:
            self._log.debug("perspective_update_failed", role=role.value, error=str(e))
    
    def _render_perspective_content(self, perspective: DirectorPerspective) -> str:
        """Render structured perspective content for display.
        
        Story 11.1: Renders recommendations, rationale, confidence per AC #2.
        
        Args:
            perspective: The DirectorPerspective to render.
            
        Returns:
            Formatted string with structured perspective data.
        """
        lines = []
        
        # Show confidence if available
        if perspective.confidence is not None:
            conf_pct = f"{perspective.confidence:.0%}"
            conf_class = self._get_confidence_class(perspective.confidence)
            conf_label = conf_class.split('-')[-1].upper()
            lines.append(f"📊 Confidence: {conf_pct} [{conf_label}]")
            lines.append("")
        
        # Role-specific structured data
        if perspective.role == DirectorRole.STRATEGIST:
            lines.extend(self._render_strategist_perspective(perspective))
        elif perspective.role == DirectorRole.ANALYST:
            lines.extend(self._render_analyst_perspective(perspective))
        elif perspective.role == DirectorRole.CREATIVE:
            lines.extend(self._render_creative_perspective(perspective))
        
        # Show rationale if available
        if perspective.rationale:
            lines.append("")
            lines.append(f"📝 Rationale: {perspective.rationale}")
        
        # Fallback to raw content if no structured data
        if not lines and perspective.content:
            return perspective.content
        
        return "\n".join(lines) if lines else perspective.content
    
    def _render_strategist_perspective(self, perspective: DirectorPerspective) -> List[str]:
        """Render strategist-specific structured data.
        
        Args:
            perspective: Strategist perspective with recommendations/techniques.
            
        Returns:
            List of formatted lines.
        """
        lines = []
        
        # Recommendations
        if perspective.recommendations:
            lines.append("📋 Recommendations:")
            for i, rec in enumerate(perspective.recommendations[:5], 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")
        
        # ATT&CK Techniques
        if perspective.attck_techniques:
            lines.append("🎯 ATT&CK Techniques:")
            for tech in perspective.attck_techniques[:5]:
                tech_id = tech.get("technique_id", "")
                tech_name = tech.get("technique_name", "")
                lines.append(f"  • {tech_id} - {tech_name}")
                if tech.get("rationale"):
                    lines.append(f"    └─ {tech.get('rationale')}")
        
        return lines
    
    def _render_analyst_perspective(self, perspective: DirectorPerspective) -> List[str]:
        """Render analyst-specific structured data.
        
        Args:
            perspective: Analyst perspective with gaps/risk assessment.
            
        Returns:
            List of formatted lines.
        """
        lines = []
        
        # Risk Level
        if perspective.risk_level:
            risk_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(
                perspective.risk_level.upper(), "⚪"
            )
            lines.append(f"{risk_icon} Risk Level: {perspective.risk_level}")
            lines.append("")
        
        # Security Gaps
        if perspective.security_gaps:
            lines.append("🔓 Security Gaps:")
            for gap in perspective.security_gaps[:5]:
                gap_id = gap.get("gap_id", "")
                desc = gap.get("description", "")
                severity = gap.get("severity", "")
                lines.append(f"  • {gap_id}: {desc} [{severity}]")
        
        return lines
    
    def _render_creative_perspective(self, perspective: DirectorPerspective) -> List[str]:
        """Render creative-specific structured data.
        
        Args:
            perspective: Creative perspective with alternatives.
            
        Returns:
            List of formatted lines.
        """
        lines = []
        
        # Creative Alternatives
        if perspective.alternatives:
            lines.append("💡 Creative Alternatives:")
            for alt in perspective.alternatives[:5]:
                alt_id = alt.get("alternative_id", "")
                desc = alt.get("description", "")
                novelty = alt.get("novelty_score", 0.0)
                novelty_str = f"[{novelty:.0%}]" if novelty else ""
                lines.append(f"  • {alt_id}: {desc} {novelty_str}")
                if alt.get("rationale"):
                    lines.append(f"    └─ {alt.get('rationale')}")
        
        return lines
    
    def _update_thinking_display(self) -> None:
        """Update the thinking content display based on toggle state."""
        try:
            thinking_widget = self.query_one("#thinking-content", Static)
            creative = self._perspectives.get(DirectorRole.CREATIVE)
            
            if self.show_thinking and creative and creative.thinking_content:
                thinking_widget.update(f"🧠 Thinking:\n{creative.thinking_content}")
                thinking_widget.display = True
            else:
                thinking_widget.update("")
                thinking_widget.display = False
                
        except Exception as e:
            self._log.debug("thinking_update_failed", error=str(e))
    
    def update_strategy_sync(self, data: Dict[str, Any]) -> None:
        """Update strategy synchronously (for testing).
        
        Story 11.1: Enhanced to parse per-perspective structured data.
        
        Args:
            data: Strategy data dictionary from stream.
        """
        self._current_strategy = parse_strategy_from_dict(data)
        
        # Parse perspectives if provided
        perspectives_data = data.get("perspectives", {})
        for role_str, persp_data in perspectives_data.items():
            try:
                role = DirectorRole(role_str)
                content = persp_data.get("content", "")
                thinking = ""
                
                # Extract thinking content for creative role
                if role == DirectorRole.CREATIVE and content:
                    thinking, content = extract_thinking_content(content)
                
                # Story 11.1: Parse per-perspective structured fields
                perspective = DirectorPerspective(
                    role=role,
                    content=content,
                    latency_ms=persp_data.get("latency_ms", 0),
                    success=persp_data.get("success", False),
                    error=persp_data.get("error"),
                    thinking_content=thinking if thinking else None,
                    # Per-perspective structured data
                    confidence=persp_data.get("confidence"),
                    recommendations=persp_data.get("recommendations", []),
                    rationale=persp_data.get("rationale"),
                    attck_techniques=persp_data.get("attck_techniques", []),
                    security_gaps=persp_data.get("security_gaps", []),
                    risk_level=persp_data.get("risk_level"),
                    alternatives=persp_data.get("alternatives", []),
                )
                self._perspectives[role] = perspective
            except ValueError:
                self._log.warning("unknown_perspective_role", role=role_str)
        
        self._log.info(
            "strategy_updated",
            confidence=self._current_strategy.confidence,
            degradation=self._current_strategy.degradation_level.value,
        )
    
    async def update_strategy(self, data: Dict[str, Any]) -> None:
        """Update strategy asynchronously from stream event.
        
        Args:
            data: Strategy data dictionary from stream.
        """
        self.update_strategy_sync(data)
        # Trigger display update (in async context, schedule it)
        self.call_after_refresh(self._update_display)
    
    def watch_show_thinking(self, value: bool) -> None:
        """React to show_thinking toggle change.
        
        Args:
            value: New value of show_thinking.
        """
        self._update_thinking_display()
    
    def watch_strategist_expanded(self, value: bool) -> None:
        """React to strategist expanded state change."""
        try:
            section = self.query_one("#strategist-section", Collapsible)
            section.collapsed = not value
        except Exception:
            pass
    
    def watch_analyst_expanded(self, value: bool) -> None:
        """React to analyst expanded state change."""
        try:
            section = self.query_one("#analyst-section", Collapsible)
            section.collapsed = not value
        except Exception:
            pass
    
    def watch_creative_expanded(self, value: bool) -> None:
        """React to creative expanded state change."""
        try:
            section = self.query_one("#creative-section", Collapsible)
            section.collapsed = not value
        except Exception:
            pass
    
    def action_toggle_strategist(self) -> None:
        """Toggle strategist section expand/collapse."""
        self.strategist_expanded = not self.strategist_expanded
    
    def action_toggle_analyst(self) -> None:
        """Toggle analyst section expand/collapse."""
        self.analyst_expanded = not self.analyst_expanded
    
    def action_toggle_creative(self) -> None:
        """Toggle creative section expand/collapse."""
        self.creative_expanded = not self.creative_expanded
    
    def action_expand_all(self) -> None:
        """Expand all perspective sections."""
        self.strategist_expanded = True
        self.analyst_expanded = True
        self.creative_expanded = True
    
    def action_collapse_all(self) -> None:
        """Collapse all perspective sections."""
        self.strategist_expanded = False
        self.analyst_expanded = False
        self.creative_expanded = False
    
    def action_toggle_thinking(self) -> None:
        """Toggle <think> tag visibility."""
        self.show_thinking = not self.show_thinking
