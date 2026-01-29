"""Unit tests for Director Display Widget.

Story 8.11: Director Ensemble TUI Display.

Tests:
- Widget initialization
- Perspective view rendering with mock data
- Expand/collapse state management
- <think> tag visibility toggle
- Strategy message parsing
- Degradation level display
- Confidence color coding
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any, List, Optional

from cyberred.llm.ensemble import (
    DirectorRole,
    SynthesizedStrategy,
    DegradationLevel,
    ATTCKRecommendation,
    CreativeAlternative,
)
from cyberred.tui.widgets.director_display import (
    DirectorDisplayWidget,
    DirectorPerspective,
    parse_strategy_from_dict,
    extract_thinking_content,
)


class TestDirectorPerspective:
    """Tests for DirectorPerspective dataclass."""

    def test_perspective_creation_success(self) -> None:
        """Test creating a successful perspective."""
        perspective = DirectorPerspective(
            role=DirectorRole.STRATEGIST,
            content="Strategic recommendations...",
            latency_ms=1500,
            success=True,
        )
        assert perspective.role == DirectorRole.STRATEGIST
        assert perspective.content == "Strategic recommendations..."
        assert perspective.latency_ms == 1500
        assert perspective.success is True
        assert perspective.error is None
        assert perspective.thinking_content is None

    def test_perspective_creation_with_error(self) -> None:
        """Test creating a failed perspective."""
        perspective = DirectorPerspective(
            role=DirectorRole.ANALYST,
            content="",
            latency_ms=5000,
            success=False,
            error="Timeout after 100s",
        )
        assert perspective.role == DirectorRole.ANALYST
        assert perspective.success is False
        assert perspective.error == "Timeout after 100s"

    def test_perspective_with_thinking_content(self) -> None:
        """Test perspective with extracted <think> tags."""
        perspective = DirectorPerspective(
            role=DirectorRole.CREATIVE,
            content="Creative alternatives...",
            latency_ms=2000,
            success=True,
            thinking_content="Reasoning about evasion techniques...",
        )
        assert perspective.thinking_content == "Reasoning about evasion techniques..."


class TestExtractThinkingContent:
    """Tests for extract_thinking_content function."""

    def test_extract_single_think_block(self) -> None:
        """Test extracting single <think> block."""
        content = """Some text before
<think>
This is my reasoning process.
</think>
Text after."""
        thinking, cleaned = extract_thinking_content(content)
        assert "This is my reasoning process." in thinking
        assert "<think>" not in cleaned
        assert "</think>" not in cleaned
        assert "Some text before" in cleaned
        assert "Text after." in cleaned

    def test_extract_multiple_think_blocks(self) -> None:
        """Test extracting multiple <think> blocks."""
        content = """<think>First thought</think>
Some content
<think>Second thought</think>
More content"""
        thinking, cleaned = extract_thinking_content(content)
        assert "First thought" in thinking
        assert "Second thought" in thinking
        assert "<think>" not in cleaned

    def test_no_think_blocks(self) -> None:
        """Test content without <think> tags."""
        content = "Just regular content without thinking."
        thinking, cleaned = extract_thinking_content(content)
        assert thinking == ""
        assert cleaned == content

    def test_empty_think_block(self) -> None:
        """Test empty <think> block."""
        content = "<think></think>Content"
        thinking, cleaned = extract_thinking_content(content)
        assert thinking == ""
        assert "Content" in cleaned


class TestParseStrategyFromDict:
    """Tests for parse_strategy_from_dict function."""

    def test_parse_full_strategy(self) -> None:
        """Test parsing a complete strategy dictionary."""
        data = {
            "objectives": ["Escalate privileges", "Exfiltrate data"],
            "actions": ["Run linpeas", "Check for weak sudo"],
            "rationale": "Target shows signs of misconfiguration",
            "confidence": 0.85,
            "contributing_roles": ["strategist", "analyst"],
            "avoid_list": ["192.168.1.100"],
            "attck_techniques": [
                {
                    "technique_id": "T1548",
                    "technique_name": "Abuse Elevation Control",
                    "rationale": "Weak sudo config",
                    "phase": "privilege-escalation",
                }
            ],
            "creative_alternatives": [
                {
                    "alternative_id": "ALT-001",
                    "description": "Try kernel exploit",
                    "rationale": "Old kernel version",
                    "novelty_score": 0.7,
                }
            ],
            "risk_warnings": ["High visibility action"],
            "conflicts_resolved": [],
            "degradation_level": "full",
            "missing_perspectives": [],
            "fallback_warnings": [],
        }
        strategy = parse_strategy_from_dict(data)
        assert len(strategy.objectives) == 2
        assert strategy.confidence == 0.85
        assert len(strategy.attck_techniques) == 1
        assert strategy.degradation_level == DegradationLevel.FULL

    def test_parse_degraded_strategy(self) -> None:
        """Test parsing a degraded strategy."""
        data = {
            "objectives": ["Continue recon"],
            "actions": ["Run nmap scan"],
            "rationale": "Limited model availability",
            "confidence": 0.5,
            "contributing_roles": ["strategist"],
            "avoid_list": [],
            "attck_techniques": [],
            "creative_alternatives": [],
            "risk_warnings": [],
            "conflicts_resolved": [],
            "degradation_level": "degraded_pair",
            "missing_perspectives": ["creative"],
            "fallback_warnings": ["Creative model unavailable"],
        }
        strategy = parse_strategy_from_dict(data)
        assert strategy.degradation_level == DegradationLevel.DEGRADED_PAIR
        assert DirectorRole.CREATIVE in strategy.missing_perspectives
        assert len(strategy.fallback_warnings) == 1

    def test_parse_minimal_strategy(self) -> None:
        """Test parsing strategy with minimal fields."""
        data = {
            "objectives": [],
            "actions": [],
            "rationale": "",
            "confidence": 0.0,
            "contributing_roles": [],
        }
        strategy = parse_strategy_from_dict(data)
        assert strategy.objectives == []
        assert strategy.confidence == 0.0


class TestDirectorDisplayWidget:
    """Tests for DirectorDisplayWidget class."""

    def test_widget_initialization(self) -> None:
        """Test widget initialization."""
        widget = DirectorDisplayWidget()
        assert widget._current_strategy is None
        assert widget._perspectives == {}
        assert widget.show_thinking is False
        assert widget.strategist_expanded is True
        assert widget.analyst_expanded is True
        assert widget.creative_expanded is True

    def test_widget_initialization_with_daemon_client(self) -> None:
        """Test widget initialization with daemon client."""
        mock_client = MagicMock()
        widget = DirectorDisplayWidget(daemon_client=mock_client)
        assert widget._daemon_client is mock_client

    def test_toggle_thinking_visibility(self) -> None:
        """Test toggling <think> tag visibility."""
        widget = DirectorDisplayWidget()
        assert widget.show_thinking is False
        widget.show_thinking = True
        assert widget.show_thinking is True

    def test_expand_collapse_strategist(self) -> None:
        """Test expand/collapse state for strategist."""
        widget = DirectorDisplayWidget()
        assert widget.strategist_expanded is True
        widget.strategist_expanded = False
        assert widget.strategist_expanded is False

    def test_expand_collapse_analyst(self) -> None:
        """Test expand/collapse state for analyst."""
        widget = DirectorDisplayWidget()
        assert widget.analyst_expanded is True
        widget.analyst_expanded = False
        assert widget.analyst_expanded is False

    def test_expand_collapse_creative(self) -> None:
        """Test expand/collapse state for creative."""
        widget = DirectorDisplayWidget()
        assert widget.creative_expanded is True
        widget.creative_expanded = False
        assert widget.creative_expanded is False

    def test_update_strategy_from_dict(self) -> None:
        """Test updating strategy from dictionary data."""
        widget = DirectorDisplayWidget()
        data = {
            "objectives": ["Test objective"],
            "actions": ["Test action"],
            "rationale": "Test rationale",
            "confidence": 0.9,
            "contributing_roles": ["strategist", "analyst", "creative"],
            "degradation_level": "full",
            "missing_perspectives": [],
            "fallback_warnings": [],
            "avoid_list": [],
            "attck_techniques": [],
            "creative_alternatives": [],
            "risk_warnings": [],
            "conflicts_resolved": [],
        }
        widget.update_strategy_sync(data)
        assert widget._current_strategy is not None
        assert widget._current_strategy.confidence == 0.9

    def test_update_perspectives_from_strategy(self) -> None:
        """Test updating perspectives from strategy data."""
        widget = DirectorDisplayWidget()
        data = {
            "objectives": ["Test"],
            "actions": [],
            "rationale": "Test",
            "confidence": 0.8,
            "contributing_roles": ["strategist", "analyst"],
            "degradation_level": "degraded_pair",
            "missing_perspectives": ["creative"],
            "fallback_warnings": ["Creative unavailable"],
            "avoid_list": [],
            "attck_techniques": [],
            "creative_alternatives": [],
            "risk_warnings": [],
            "conflicts_resolved": [],
            # Include perspective data
            "perspectives": {
                "strategist": {
                    "content": "Strategic analysis...",
                    "latency_ms": 1200,
                    "success": True,
                },
                "analyst": {
                    "content": "Analysis results...",
                    "latency_ms": 1500,
                    "success": True,
                },
                "creative": {
                    "content": "",
                    "latency_ms": 0,
                    "success": False,
                    "error": "Model unavailable",
                },
            },
        }
        widget.update_strategy_sync(data)
        assert DirectorRole.STRATEGIST in widget._perspectives
        assert DirectorRole.ANALYST in widget._perspectives
        assert widget._perspectives[DirectorRole.STRATEGIST].success is True

    def test_get_confidence_class_high(self) -> None:
        """Test confidence class for high confidence."""
        widget = DirectorDisplayWidget()
        assert widget._get_confidence_class(0.8) == "confidence-high"
        assert widget._get_confidence_class(1.0) == "confidence-high"

    def test_get_confidence_class_medium(self) -> None:
        """Test confidence class for medium confidence."""
        widget = DirectorDisplayWidget()
        assert widget._get_confidence_class(0.5) == "confidence-medium"
        assert widget._get_confidence_class(0.7) == "confidence-medium"

    def test_get_confidence_class_low(self) -> None:
        """Test confidence class for low confidence."""
        widget = DirectorDisplayWidget()
        assert widget._get_confidence_class(0.3) == "confidence-low"
        assert widget._get_confidence_class(0.0) == "confidence-low"

    def test_get_degradation_message_full(self) -> None:
        """Test degradation message for full availability."""
        widget = DirectorDisplayWidget()
        msg = widget._get_degradation_message(DegradationLevel.FULL, [])
        assert msg == ""

    def test_get_degradation_message_degraded(self) -> None:
        """Test degradation message for degraded mode."""
        widget = DirectorDisplayWidget()
        msg = widget._get_degradation_message(
            DegradationLevel.DEGRADED_PAIR,
            [DirectorRole.CREATIVE]
        )
        assert "creative" in msg.lower()
        assert "unavailable" in msg.lower() or "missing" in msg.lower()


class TestDirectorDisplayWidgetRendering:
    """Tests for DirectorDisplayWidget rendering methods."""

    def test_render_perspective_header_strategist(self) -> None:
        """Test rendering strategist header."""
        widget = DirectorDisplayWidget()
        header = widget._render_perspective_header(DirectorRole.STRATEGIST)
        assert "Strategist" in header or "STRATEGIST" in header
        assert "DeepSeek" in header

    def test_render_perspective_header_analyst(self) -> None:
        """Test rendering analyst header."""
        widget = DirectorDisplayWidget()
        header = widget._render_perspective_header(DirectorRole.ANALYST)
        assert "Analyst" in header or "ANALYST" in header
        assert "Kimi" in header

    def test_render_perspective_header_creative(self) -> None:
        """Test rendering creative header."""
        widget = DirectorDisplayWidget()
        header = widget._render_perspective_header(DirectorRole.CREATIVE)
        assert "Creative" in header or "CREATIVE" in header
        assert "MiniMax" in header

    def test_render_no_strategy_placeholder(self) -> None:
        """Test placeholder when no strategy exists."""
        widget = DirectorDisplayWidget()
        content = widget._render_content_or_placeholder()
        assert "awaiting" in content.lower() or "no strategy" in content.lower()

    def test_format_attck_techniques(self) -> None:
        """Test formatting ATT&CK techniques for display."""
        widget = DirectorDisplayWidget()
        techniques = [
            ATTCKRecommendation(
                technique_id="T1548.002",
                technique_name="Bypass User Access Control",
                rationale="UAC misconfigured",
                phase="privilege-escalation",
            ),
        ]
        formatted = widget._format_attck_techniques(techniques)
        assert "T1548.002" in formatted
        assert "Bypass User Access Control" in formatted

    def test_format_creative_alternatives(self) -> None:
        """Test formatting creative alternatives for display."""
        widget = DirectorDisplayWidget()
        alternatives = [
            CreativeAlternative(
                alternative_id="ALT-001",
                description="Use LOLBAS technique",
                rationale="Avoids detection",
                novelty_score=0.8,
            ),
        ]
        formatted = widget._format_creative_alternatives(alternatives)
        assert "ALT-001" in formatted
        assert "LOLBAS" in formatted


class TestDirectorDisplayWidgetAsync:
    """Async tests for DirectorDisplayWidget."""

    @pytest.mark.asyncio
    async def test_update_strategy_async(self) -> None:
        """Test async strategy update."""
        widget = DirectorDisplayWidget()
        data = {
            "objectives": ["Async test"],
            "actions": [],
            "rationale": "Testing async update",
            "confidence": 0.75,
            "contributing_roles": ["strategist"],
            "degradation_level": "full",
            "missing_perspectives": [],
            "fallback_warnings": [],
            "avoid_list": [],
            "attck_techniques": [],
            "creative_alternatives": [],
            "risk_warnings": [],
            "conflicts_resolved": [],
        }
        await widget.update_strategy(data)
        assert widget._current_strategy is not None
        assert widget._current_strategy.confidence == 0.75


class TestDirectorDisplayWidgetActions:
    """Tests for DirectorDisplayWidget action methods."""

    def test_action_toggle_strategist(self) -> None:
        """Test toggle strategist action."""
        widget = DirectorDisplayWidget()
        assert widget.strategist_expanded is True
        widget.action_toggle_strategist()
        assert widget.strategist_expanded is False
        widget.action_toggle_strategist()
        assert widget.strategist_expanded is True

    def test_action_toggle_analyst(self) -> None:
        """Test toggle analyst action."""
        widget = DirectorDisplayWidget()
        assert widget.analyst_expanded is True
        widget.action_toggle_analyst()
        assert widget.analyst_expanded is False

    def test_action_toggle_creative(self) -> None:
        """Test toggle creative action."""
        widget = DirectorDisplayWidget()
        assert widget.creative_expanded is True
        widget.action_toggle_creative()
        assert widget.creative_expanded is False

    def test_action_expand_all(self) -> None:
        """Test expand all action."""
        widget = DirectorDisplayWidget()
        widget.strategist_expanded = False
        widget.analyst_expanded = False
        widget.creative_expanded = False
        widget.action_expand_all()
        assert widget.strategist_expanded is True
        assert widget.analyst_expanded is True
        assert widget.creative_expanded is True

    def test_action_collapse_all(self) -> None:
        """Test collapse all action."""
        widget = DirectorDisplayWidget()
        widget.action_collapse_all()
        assert widget.strategist_expanded is False
        assert widget.analyst_expanded is False
        assert widget.creative_expanded is False

    def test_action_toggle_thinking(self) -> None:
        """Test toggle thinking action."""
        widget = DirectorDisplayWidget()
        assert widget.show_thinking is False
        widget.action_toggle_thinking()
        assert widget.show_thinking is True
        widget.action_toggle_thinking()
        assert widget.show_thinking is False


class TestParseStrategyEdgeCases:
    """Edge case tests for parse_strategy_from_dict."""

    def test_parse_unknown_role(self) -> None:
        """Test parsing with unknown role."""
        data = {
            "objectives": [],
            "actions": [],
            "rationale": "",
            "confidence": 0.0,
            "contributing_roles": ["unknown_role", "strategist"],
            "degradation_level": "full",
            "missing_perspectives": ["invalid_role"],
        }
        strategy = parse_strategy_from_dict(data)
        # Only valid role should be included
        assert DirectorRole.STRATEGIST in strategy.contributing_roles
        assert len(strategy.contributing_roles) == 1

    def test_parse_unknown_degradation_level(self) -> None:
        """Test parsing with unknown degradation level."""
        data = {
            "objectives": [],
            "actions": [],
            "rationale": "",
            "confidence": 0.0,
            "contributing_roles": [],
            "degradation_level": "invalid_level",
        }
        strategy = parse_strategy_from_dict(data)
        # Should default to FULL
        assert strategy.degradation_level == DegradationLevel.FULL

    def test_parse_attck_techniques_with_defaults(self) -> None:
        """Test parsing ATT&CK techniques uses default empty strings."""
        data = {
            "objectives": [],
            "actions": [],
            "rationale": "",
            "confidence": 0.0,
            "contributing_roles": [],
            "attck_techniques": [
                {"technique_id": "T1059", "technique_name": "Shell", "rationale": "test", "phase": "execution"}
            ],
        }
        strategy = parse_strategy_from_dict(data)
        assert len(strategy.attck_techniques) == 1
        assert strategy.attck_techniques[0].technique_id == "T1059"

    def test_parse_creative_alternatives_with_defaults(self) -> None:
        """Test parsing creative alternatives with valid data."""
        data = {
            "objectives": [],
            "actions": [],
            "rationale": "",
            "confidence": 0.0,
            "contributing_roles": [],
            "creative_alternatives": [
                {"alternative_id": "ALT-001", "description": "test", "rationale": "valid", "novelty_score": 0.5}
            ],
        }
        strategy = parse_strategy_from_dict(data)
        assert len(strategy.creative_alternatives) == 1
        assert strategy.creative_alternatives[0].alternative_id == "ALT-001"


class TestDirectorDisplayWidgetFormatting:
    """Tests for formatting methods."""

    def test_format_empty_attck_techniques(self) -> None:
        """Test formatting empty ATT&CK techniques."""
        widget = DirectorDisplayWidget()
        formatted = widget._format_attck_techniques([])
        assert "No ATT&CK" in formatted

    def test_format_attck_without_rationale(self) -> None:
        """Test formatting ATT&CK without rationale."""
        widget = DirectorDisplayWidget()
        techniques = [
            ATTCKRecommendation(
                technique_id="T1059",
                technique_name="Command Interpreter",
                rationale="",  # Empty rationale
                phase="execution",
            ),
        ]
        formatted = widget._format_attck_techniques(techniques)
        assert "T1059" in formatted
        assert "└─" not in formatted  # No rationale line

    def test_format_empty_creative_alternatives(self) -> None:
        """Test formatting empty creative alternatives."""
        widget = DirectorDisplayWidget()
        formatted = widget._format_creative_alternatives([])
        assert "No creative" in formatted

    def test_format_creative_with_low_novelty(self) -> None:
        """Test formatting creative with zero novelty score."""
        widget = DirectorDisplayWidget()
        alternatives = [
            CreativeAlternative(
                alternative_id="ALT-002",
                description="DNS tunneling",
                rationale="Uses covert channel",
                novelty_score=0.0,  # Zero score - no percentage shown
            ),
        ]
        formatted = widget._format_creative_alternatives(alternatives)
        assert "ALT-002" in formatted
        assert "DNS tunneling" in formatted

    def test_get_degradation_message_unavailable(self) -> None:
        """Test degradation message for unavailable level."""
        widget = DirectorDisplayWidget()
        msg = widget._get_degradation_message(
            DegradationLevel.UNAVAILABLE,
            [DirectorRole.STRATEGIST, DirectorRole.ANALYST, DirectorRole.CREATIVE],
        )
        assert "Strategist" in msg
        assert "Analyst" in msg
        assert "Creative" in msg

    def test_get_degradation_message_degraded_single(self) -> None:
        """Test degradation message for single model mode."""
        widget = DirectorDisplayWidget()
        msg = widget._get_degradation_message(
            DegradationLevel.DEGRADED_SINGLE,
            [DirectorRole.ANALYST, DirectorRole.CREATIVE],
        )
        assert "Analyst" in msg
        assert "Creative" in msg


class TestExtractThinkingContentEdgeCases:
    """Edge case tests for extract_thinking_content."""

    def test_extract_nested_think_blocks(self) -> None:
        """Test with text that looks nested (edge case)."""
        content = "<think>outer <think>inner</think> outer</think>"
        thinking, cleaned = extract_thinking_content(content)
        # Regex is non-greedy, so it handles this
        assert "<think>" not in cleaned or "inner" in cleaned

    def test_extract_think_with_newlines(self) -> None:
        """Test with newlines in think block."""
        content = """<think>
Line 1
Line 2
Line 3
</think>"""
        thinking, cleaned = extract_thinking_content(content)
        assert "Line 1" in thinking
        assert "Line 2" in thinking
        assert "Line 3" in thinking

    def test_extract_empty_content(self) -> None:
        """Test with empty string."""
        thinking, cleaned = extract_thinking_content("")
        assert thinking == ""
        assert cleaned == ""


class TestRoleInfo:
    """Tests for ROLE_INFO constant."""

    def test_all_roles_have_info(self) -> None:
        """Test all DirectorRole values have ROLE_INFO entries."""
        from cyberred.tui.widgets.director_display import ROLE_INFO
        for role in DirectorRole:
            assert role in ROLE_INFO
            name, model, color = ROLE_INFO[role]
            assert len(name) > 0
            assert len(model) > 0
            assert len(color) > 0


class TestExtractThinkingContentNone:
    """Tests for extract_thinking_content with None input."""

    def test_extract_none_input(self) -> None:
        """Test extract_thinking_content handles None input."""
        thinking, cleaned = extract_thinking_content(None)
        assert thinking == ""
        assert cleaned == ""


class TestDirectorDisplayWidgetWatchers:
    """Tests for watch methods on DirectorDisplayWidget."""

    def test_watch_show_thinking_called(self) -> None:
        """Test watch_show_thinking is called when show_thinking changes."""
        widget = DirectorDisplayWidget()
        # Set up a perspective with thinking content
        widget._perspectives[DirectorRole.CREATIVE] = DirectorPerspective(
            role=DirectorRole.CREATIVE,
            content="Creative content",
            latency_ms=1000,
            success=True,
            thinking_content="Some thinking",
        )
        # Directly call the watcher
        widget.watch_show_thinking(True)
        # Should not raise

    def test_watch_strategist_expanded_no_section(self) -> None:
        """Test watch_strategist_expanded handles missing section gracefully."""
        widget = DirectorDisplayWidget()
        # Widget not composed, so query_one will fail
        # This should NOT raise due to except block
        widget.watch_strategist_expanded(False)

    def test_watch_analyst_expanded_no_section(self) -> None:
        """Test watch_analyst_expanded handles missing section gracefully."""
        widget = DirectorDisplayWidget()
        widget.watch_analyst_expanded(False)

    def test_watch_creative_expanded_no_section(self) -> None:
        """Test watch_creative_expanded handles missing section gracefully."""
        widget = DirectorDisplayWidget()
        widget.watch_creative_expanded(False)


class TestDirectorDisplayWidgetRenderUnifiedStrategy:
    """Tests for _render_unified_strategy method."""

    def test_render_unified_strategy_with_full_data(self) -> None:
        """Test rendering unified strategy with all fields."""
        widget = DirectorDisplayWidget()
        data = {
            "objectives": ["Objective 1", "Objective 2"],
            "actions": ["Action 1", "Action 2"],
            "rationale": "Test rationale",
            "confidence": 0.85,
            "contributing_roles": ["strategist", "analyst", "creative"],
            "degradation_level": "full",
            "missing_perspectives": [],
            "fallback_warnings": [],
            "avoid_list": [],
            "attck_techniques": [],
            "creative_alternatives": [],
            "risk_warnings": ["Warning 1"],
            "conflicts_resolved": [],
        }
        widget.update_strategy_sync(data)
        
        rendered = widget._render_unified_strategy()
        
        assert "UNIFIED STRATEGY" in rendered
        assert "Objective 1" in rendered
        assert "Action 1" in rendered
        assert "Test rationale" in rendered
        assert "85%" in rendered
        assert "Warning 1" in rendered

    def test_render_unified_strategy_no_strategy(self) -> None:
        """Test rendering unified strategy when no strategy exists."""
        widget = DirectorDisplayWidget()
        rendered = widget._render_unified_strategy()
        assert rendered == ""

    def test_render_unified_strategy_empty_lists(self) -> None:
        """Test rendering unified strategy with empty lists."""
        widget = DirectorDisplayWidget()
        data = {
            "objectives": [],
            "actions": [],
            "rationale": "",
            "confidence": 0.0,
            "contributing_roles": [],
            "degradation_level": "full",
            "missing_perspectives": [],
            "fallback_warnings": [],
            "avoid_list": [],
            "attck_techniques": [],
            "creative_alternatives": [],
            "risk_warnings": [],
            "conflicts_resolved": [],
        }
        widget.update_strategy_sync(data)
        
        rendered = widget._render_unified_strategy()
        
        assert "UNIFIED STRATEGY" in rendered
        # Should not have objective/action sections since lists are empty
        assert "🎯 Objectives:" not in rendered
        assert "⚡ Actions:" not in rendered


class TestDirectorDisplayWidgetUpdateMethods:
    """Tests for _update methods."""

    def test_update_perspective_section_success(self) -> None:
        """Test _update_perspective_section with success perspective."""
        widget = DirectorDisplayWidget()
        widget._perspectives[DirectorRole.STRATEGIST] = DirectorPerspective(
            role=DirectorRole.STRATEGIST,
            content="Strategic content here",
            latency_ms=1200,
            success=True,
        )
        # Should not raise without DOM
        widget._update_perspective_section(DirectorRole.STRATEGIST, "strategist-content")

    def test_update_perspective_section_failure(self) -> None:
        """Test _update_perspective_section with failed perspective."""
        widget = DirectorDisplayWidget()
        widget._perspectives[DirectorRole.ANALYST] = DirectorPerspective(
            role=DirectorRole.ANALYST,
            content="",
            latency_ms=5000,
            success=False,
            error="Timeout",
        )
        # Should not raise without DOM
        widget._update_perspective_section(DirectorRole.ANALYST, "analyst-content")

    def test_update_perspective_section_no_perspective(self) -> None:
        """Test _update_perspective_section with no perspective data."""
        widget = DirectorDisplayWidget()
        # No perspective set, should handle gracefully
        widget._update_perspective_section(DirectorRole.CREATIVE, "creative-content")

    def test_update_thinking_display_no_creative(self) -> None:
        """Test _update_thinking_display with no creative perspective."""
        widget = DirectorDisplayWidget()
        widget.show_thinking = True
        # Should not raise without DOM or creative perspective
        widget._update_thinking_display()

    def test_update_thinking_display_with_thinking(self) -> None:
        """Test _update_thinking_display with thinking content."""
        widget = DirectorDisplayWidget()
        widget._perspectives[DirectorRole.CREATIVE] = DirectorPerspective(
            role=DirectorRole.CREATIVE,
            content="Creative content",
            latency_ms=1000,
            success=True,
            thinking_content="Internal reasoning",
        )
        widget.show_thinking = True
        # Should not raise without DOM
        widget._update_thinking_display()

    def test_update_display_no_strategy(self) -> None:
        """Test _update_display with no strategy."""
        widget = DirectorDisplayWidget()
        # Should not raise without DOM
        widget._update_display()

    def test_update_display_with_strategy(self) -> None:
        """Test _update_display with strategy data."""
        widget = DirectorDisplayWidget()
        data = {
            "objectives": ["Test"],
            "actions": [],
            "rationale": "",
            "confidence": 0.7,
            "contributing_roles": ["strategist"],
            "degradation_level": "degraded_pair",
            "missing_perspectives": ["creative"],
            "fallback_warnings": [],
            "avoid_list": [],
            "attck_techniques": [],
            "creative_alternatives": [],
            "risk_warnings": [],
            "conflicts_resolved": [],
        }
        widget.update_strategy_sync(data)
        # Should not raise without DOM
        widget._update_display()


class TestDirectorDisplayWidgetPerspectiveParsing:
    """Tests for perspective parsing edge cases."""

    def test_parse_unknown_perspective_role(self) -> None:
        """Test parsing perspective with unknown role is logged but doesn't crash."""
        widget = DirectorDisplayWidget()
        data = {
            "objectives": ["Test"],
            "actions": [],
            "rationale": "",
            "confidence": 0.5,
            "contributing_roles": [],
            "degradation_level": "full",
            "missing_perspectives": [],
            "fallback_warnings": [],
            "avoid_list": [],
            "attck_techniques": [],
            "creative_alternatives": [],
            "risk_warnings": [],
            "conflicts_resolved": [],
            "perspectives": {
                "unknown_role": {
                    "content": "Some content",
                    "latency_ms": 1000,
                    "success": True,
                },
            },
        }
        # Should not raise
        widget.update_strategy_sync(data)
        # Unknown role should not be in perspectives
        assert len(widget._perspectives) == 0

    def test_parse_creative_without_think_tags(self) -> None:
        """Test parsing creative perspective without <think> tags."""
        widget = DirectorDisplayWidget()
        data = {
            "objectives": [],
            "actions": [],
            "rationale": "",
            "confidence": 0.5,
            "contributing_roles": ["creative"],
            "degradation_level": "full",
            "missing_perspectives": [],
            "fallback_warnings": [],
            "avoid_list": [],
            "attck_techniques": [],
            "creative_alternatives": [],
            "risk_warnings": [],
            "conflicts_resolved": [],
            "perspectives": {
                "creative": {
                    "content": "Creative content without think tags",
                    "latency_ms": 1500,
                    "success": True,
                },
            },
        }
        widget.update_strategy_sync(data)
        
        creative = widget._perspectives.get(DirectorRole.CREATIVE)
        assert creative is not None
        assert creative.thinking_content is None
        assert creative.content == "Creative content without think tags"

    def test_parse_creative_empty_content(self) -> None:
        """Test parsing creative perspective with empty content."""
        widget = DirectorDisplayWidget()
        data = {
            "objectives": [],
            "actions": [],
            "rationale": "",
            "confidence": 0.5,
            "contributing_roles": [],
            "degradation_level": "full",
            "missing_perspectives": [],
            "fallback_warnings": [],
            "avoid_list": [],
            "attck_techniques": [],
            "creative_alternatives": [],
            "risk_warnings": [],
            "conflicts_resolved": [],
            "perspectives": {
                "creative": {
                    "content": "",
                    "latency_ms": 0,
                    "success": False,
                    "error": "Model unavailable",
                },
            },
        }
        widget.update_strategy_sync(data)
        
        creative = widget._perspectives.get(DirectorRole.CREATIVE)
        assert creative is not None
        assert creative.success is False


# ============================================================================
# Story 11.1: Per-Perspective Structured Data Tests
# ============================================================================


class TestDirectorPerspectiveStructuredData:
    """Tests for Story 11.1 per-perspective structured data fields."""

    def test_perspective_with_confidence(self) -> None:
        """Test perspective with confidence score."""
        perspective = DirectorPerspective(
            role=DirectorRole.STRATEGIST,
            content="Strategic recommendations...",
            latency_ms=1500,
            success=True,
            confidence=0.85,
        )
        assert perspective.confidence == 0.85

    def test_perspective_with_recommendations(self) -> None:
        """Test strategist perspective with recommendations list."""
        perspective = DirectorPerspective(
            role=DirectorRole.STRATEGIST,
            content="",
            latency_ms=1200,
            success=True,
            confidence=0.9,
            recommendations=["Focus on SSH service", "Escalate via sudo"],
            rationale="Target shows weak sudo configuration",
        )
        assert len(perspective.recommendations) == 2
        assert "Focus on SSH" in perspective.recommendations[0]
        assert perspective.rationale is not None

    def test_perspective_with_attck_techniques(self) -> None:
        """Test strategist perspective with ATT&CK techniques."""
        perspective = DirectorPerspective(
            role=DirectorRole.STRATEGIST,
            content="",
            latency_ms=1200,
            success=True,
            attck_techniques=[
                {"technique_id": "T1548", "technique_name": "Abuse Elevation", "rationale": "Weak sudo"},
            ],
        )
        assert len(perspective.attck_techniques) == 1
        assert perspective.attck_techniques[0]["technique_id"] == "T1548"

    def test_perspective_with_security_gaps(self) -> None:
        """Test analyst perspective with security gaps."""
        perspective = DirectorPerspective(
            role=DirectorRole.ANALYST,
            content="",
            latency_ms=1500,
            success=True,
            risk_level="HIGH",
            security_gaps=[
                {"gap_id": "GAP-001", "description": "Weak SSH config", "severity": "HIGH"},
            ],
        )
        assert perspective.risk_level == "HIGH"
        assert len(perspective.security_gaps) == 1

    def test_perspective_with_alternatives(self) -> None:
        """Test creative perspective with alternatives."""
        perspective = DirectorPerspective(
            role=DirectorRole.CREATIVE,
            content="",
            latency_ms=1800,
            success=True,
            alternatives=[
                {"alternative_id": "ALT-001", "description": "DNS tunneling", "novelty_score": 0.7},
            ],
        )
        assert len(perspective.alternatives) == 1
        assert perspective.alternatives[0]["novelty_score"] == 0.7


class TestRenderPerspectiveContent:
    """Tests for Story 11.1 perspective content rendering."""

    def test_render_strategist_with_structured_data(self) -> None:
        """Test rendering strategist perspective with structured data."""
        widget = DirectorDisplayWidget()
        perspective = DirectorPerspective(
            role=DirectorRole.STRATEGIST,
            content="fallback content",
            latency_ms=1200,
            success=True,
            confidence=0.85,
            recommendations=["Focus on SSH", "Check sudo"],
            attck_techniques=[
                {"technique_id": "T1548", "technique_name": "Abuse Elevation", "rationale": "Weak sudo"},
            ],
        )
        
        content = widget._render_perspective_content(perspective)
        
        assert "85%" in content
        assert "Recommendations:" in content
        assert "Focus on SSH" in content
        assert "ATT&CK Techniques:" in content
        assert "T1548" in content

    def test_render_analyst_with_structured_data(self) -> None:
        """Test rendering analyst perspective with structured data."""
        widget = DirectorDisplayWidget()
        perspective = DirectorPerspective(
            role=DirectorRole.ANALYST,
            content="fallback content",
            latency_ms=1500,
            success=True,
            confidence=0.75,
            risk_level="HIGH",
            security_gaps=[
                {"gap_id": "GAP-001", "description": "Weak SSH", "severity": "HIGH"},
            ],
        )
        
        content = widget._render_perspective_content(perspective)
        
        assert "75%" in content
        assert "Risk Level: HIGH" in content
        assert "Security Gaps:" in content
        assert "GAP-001" in content

    def test_render_creative_with_structured_data(self) -> None:
        """Test rendering creative perspective with structured data."""
        widget = DirectorDisplayWidget()
        perspective = DirectorPerspective(
            role=DirectorRole.CREATIVE,
            content="fallback content",
            latency_ms=1800,
            success=True,
            confidence=0.65,
            alternatives=[
                {"alternative_id": "ALT-001", "description": "DNS tunneling", "novelty_score": 0.7, "rationale": "Bypass firewall"},
            ],
        )
        
        content = widget._render_perspective_content(perspective)
        
        assert "65%" in content
        assert "Creative Alternatives:" in content
        assert "ALT-001" in content
        assert "70%" in content  # novelty score
        assert "Bypass firewall" in content

    def test_render_fallback_to_raw_content(self) -> None:
        """Test fallback to raw content when no structured data."""
        widget = DirectorDisplayWidget()
        perspective = DirectorPerspective(
            role=DirectorRole.STRATEGIST,
            content="Raw strategist output without structured fields",
            latency_ms=1200,
            success=True,
        )
        
        content = widget._render_perspective_content(perspective)
        
        assert "Raw strategist output" in content

    def test_render_with_rationale(self) -> None:
        """Test rendering perspective with rationale."""
        widget = DirectorDisplayWidget()
        perspective = DirectorPerspective(
            role=DirectorRole.STRATEGIST,
            content="",
            latency_ms=1200,
            success=True,
            confidence=0.8,
            rationale="Based on discovered vulnerabilities",
        )
        
        content = widget._render_perspective_content(perspective)
        
        assert "Rationale:" in content
        assert "Based on discovered" in content


class TestUpdateStrategySyncStructuredData:
    """Tests for Story 11.1 structured data parsing in update_strategy_sync."""

    def test_parse_structured_perspective_data(self) -> None:
        """Test parsing structured perspective data from stream."""
        widget = DirectorDisplayWidget()
        data = {
            "objectives": ["Test objective"],
            "actions": ["Test action"],
            "rationale": "Test rationale",
            "confidence": 0.8,
            "contributing_roles": ["strategist"],
            "degradation_level": "full",
            "missing_perspectives": [],
            "perspectives": {
                "strategist": {
                    "content": "Strategic analysis...",
                    "latency_ms": 1200,
                    "success": True,
                    "confidence": 0.85,
                    "recommendations": ["Rec 1", "Rec 2"],
                    "rationale": "Strategist rationale",
                    "attck_techniques": [
                        {"technique_id": "T1548", "technique_name": "Abuse Elevation"},
                    ],
                },
                "analyst": {
                    "content": "Analyst analysis...",
                    "latency_ms": 1500,
                    "success": True,
                    "confidence": 0.75,
                    "risk_level": "HIGH",
                    "security_gaps": [
                        {"gap_id": "GAP-001", "description": "Weak config", "severity": "HIGH"},
                    ],
                },
                "creative": {
                    "content": "<think>Thinking...</think>Creative output",
                    "latency_ms": 1800,
                    "success": True,
                    "confidence": 0.65,
                    "alternatives": [
                        {"alternative_id": "ALT-001", "description": "DNS tunneling", "novelty_score": 0.7},
                    ],
                },
            },
        }
        
        widget.update_strategy_sync(data)
        
        # Verify strategist perspective
        strategist = widget._perspectives.get(DirectorRole.STRATEGIST)
        assert strategist is not None
        assert strategist.confidence == 0.85
        assert len(strategist.recommendations) == 2
        assert len(strategist.attck_techniques) == 1
        
        # Verify analyst perspective
        analyst = widget._perspectives.get(DirectorRole.ANALYST)
        assert analyst is not None
        assert analyst.risk_level == "HIGH"
        assert len(analyst.security_gaps) == 1
        
        # Verify creative perspective
        creative = widget._perspectives.get(DirectorRole.CREATIVE)
        assert creative is not None
        assert creative.confidence == 0.65
        assert len(creative.alternatives) == 1
        assert creative.thinking_content is not None
        assert "Thinking" in creative.thinking_content
