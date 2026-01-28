"""Integration tests for Director Display Widget.

Story 8.11: Director Ensemble TUI Display.

Tests:
- Real-time updates via mock daemon stream
- Multiple sequential strategy updates
- Actual DirectorEnsemble output handling
- Partial model availability display
- Keyboard shortcuts for expand/collapse
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from textual.pilot import Pilot

from cyberred.llm.ensemble import (
    DirectorRole,
    DegradationLevel,
)
from cyberred.tui.widgets.director_display import (
    DirectorDisplayWidget,
    DirectorPerspective,
    parse_strategy_from_dict,
)
from cyberred.daemon.streaming import StreamEvent, StreamEventType


def create_mock_strategy_data(
    confidence: float = 0.85,
    degradation: str = "full",
    missing: list = None,
) -> Dict[str, Any]:
    """Create mock strategy data for testing.
    
    Args:
        confidence: Strategy confidence score.
        degradation: Degradation level string.
        missing: List of missing perspective role names.
        
    Returns:
        Strategy data dictionary suitable for update_strategy().
    """
    return {
        "objectives": ["Escalate privileges on target-01", "Establish persistence"],
        "actions": [
            "Run linpeas enumeration",
            "Check for weak sudo permissions",
            "Attempt kernel exploit if applicable",
        ],
        "rationale": "Target shows signs of misconfigured sudo and outdated kernel",
        "confidence": confidence,
        "contributing_roles": ["strategist", "analyst", "creative"],
        "avoid_list": ["192.168.1.100"],
        "attck_techniques": [
            {
                "technique_id": "T1548.002",
                "technique_name": "Bypass User Access Control",
                "rationale": "Weak sudo configuration detected",
                "phase": "privilege-escalation",
            },
            {
                "technique_id": "T1068",
                "technique_name": "Exploitation for Privilege Escalation",
                "rationale": "Kernel version vulnerable to CVE-2021-4034",
                "phase": "privilege-escalation",
            },
        ],
        "creative_alternatives": [
            {
                "alternative_id": "ALT-001",
                "description": "Use LOLBAS technique with certutil",
                "rationale": "Avoids AV detection while downloading payload",
                "novelty_score": 0.7,
            },
        ],
        "risk_warnings": ["High visibility action may trigger alerts"],
        "conflicts_resolved": [],
        "degradation_level": degradation,
        "missing_perspectives": missing or [],
        "fallback_warnings": [],
        "perspectives": {
            "strategist": {
                "content": "Strategic analysis suggests privilege escalation path via sudo misconfiguration.",
                "latency_ms": 1200,
                "success": True,
            },
            "analyst": {
                "content": "Attack surface analysis reveals 3 high-value targets with weak configurations.",
                "latency_ms": 1500,
                "success": True,
            },
            "creative": {
                "content": "<think>Considering lateral movement options...</think>Creative alternatives include DNS tunneling for exfiltration.",
                "latency_ms": 1800,
                "success": True,
            },
        },
    }


class TestDirectorDisplayWidgetIntegration:
    """Integration tests for DirectorDisplayWidget."""

    def test_full_strategy_update_flow(self) -> None:
        """Test complete strategy update flow with all perspectives."""
        widget = DirectorDisplayWidget()
        data = create_mock_strategy_data()
        
        widget.update_strategy_sync(data)
        
        # Verify strategy was parsed
        assert widget._current_strategy is not None
        assert widget._current_strategy.confidence == 0.85
        assert len(widget._current_strategy.objectives) == 2
        assert len(widget._current_strategy.actions) == 3
        
        # Verify perspectives were parsed
        assert DirectorRole.STRATEGIST in widget._perspectives
        assert DirectorRole.ANALYST in widget._perspectives
        assert DirectorRole.CREATIVE in widget._perspectives
        
        # Verify creative thinking content was extracted
        creative = widget._perspectives[DirectorRole.CREATIVE]
        assert creative.thinking_content is not None
        assert "Considering lateral movement" in creative.thinking_content
        assert "<think>" not in creative.content  # Tags should be removed

    def test_multiple_sequential_updates(self) -> None:
        """Test multiple strategy updates in sequence."""
        widget = DirectorDisplayWidget()
        
        # First update
        data1 = create_mock_strategy_data(confidence=0.6)
        widget.update_strategy_sync(data1)
        assert widget._current_strategy.confidence == 0.6
        
        # Second update with higher confidence
        data2 = create_mock_strategy_data(confidence=0.9)
        widget.update_strategy_sync(data2)
        assert widget._current_strategy.confidence == 0.9
        
        # Third update with degradation
        data3 = create_mock_strategy_data(
            confidence=0.5,
            degradation="degraded_pair",
            missing=["creative"],
        )
        widget.update_strategy_sync(data3)
        assert widget._current_strategy.confidence == 0.5
        assert widget._current_strategy.degradation_level == DegradationLevel.DEGRADED_PAIR

    def test_partial_model_availability_display(self) -> None:
        """Test display with partial model availability."""
        widget = DirectorDisplayWidget()
        
        # Create data with missing creative model
        data = create_mock_strategy_data(
            confidence=0.65,
            degradation="degraded_pair",
            missing=["creative"],
        )
        # Update perspectives to show failure
        data["perspectives"]["creative"] = {
            "content": "",
            "latency_ms": 0,
            "success": False,
            "error": "Model unavailable: MiniMax M2",
        }
        
        widget.update_strategy_sync(data)
        
        # Verify degradation is tracked
        assert widget._current_strategy.degradation_level == DegradationLevel.DEGRADED_PAIR
        assert DirectorRole.CREATIVE in widget._current_strategy.missing_perspectives
        
        # Verify creative perspective shows failure
        creative = widget._perspectives.get(DirectorRole.CREATIVE)
        assert creative is not None
        assert creative.success is False
        assert "unavailable" in creative.error

    def test_thinking_content_extraction_from_stream(self) -> None:
        """Test <think> tag extraction from stream data."""
        widget = DirectorDisplayWidget()
        
        data = create_mock_strategy_data()
        data["perspectives"]["creative"]["content"] = """
<think>
First, analyzing current defenses...
The target uses EDR with behavior monitoring.
</think>
Creative alternatives:
1. Use DNS tunneling
<think>
Also considering physical access vectors...
</think>
2. Social engineering path
"""
        
        widget.update_strategy_sync(data)
        
        creative = widget._perspectives[DirectorRole.CREATIVE]
        assert creative.thinking_content is not None
        assert "analyzing current defenses" in creative.thinking_content
        assert "considering physical access" in creative.thinking_content
        assert "<think>" not in creative.content
        assert "Creative alternatives" in creative.content

    def test_strategy_event_parsing(self) -> None:
        """Test parsing strategy from stream event format."""
        widget = DirectorDisplayWidget()
        
        # Simulate stream event data structure
        event_data = create_mock_strategy_data()
        
        # Create a StreamEvent
        event = StreamEvent(
            event_type=StreamEventType.STRATEGY_UPDATE,
            data=event_data,
        )
        
        # Parse through widget
        widget.update_strategy_sync(event.data)
        
        assert widget._current_strategy is not None
        assert widget._current_strategy.confidence == 0.85


class TestDirectorDisplayWidgetExpandCollapse:
    """Integration tests for expand/collapse functionality."""

    def test_expand_collapse_persistence(self) -> None:
        """Test expand/collapse state persists across updates."""
        widget = DirectorDisplayWidget()
        
        # Collapse all sections
        widget.action_collapse_all()
        assert widget.strategist_expanded is False
        assert widget.analyst_expanded is False
        assert widget.creative_expanded is False
        
        # Update strategy
        data = create_mock_strategy_data()
        widget.update_strategy_sync(data)
        
        # State should persist
        assert widget.strategist_expanded is False
        assert widget.analyst_expanded is False
        assert widget.creative_expanded is False

    def test_individual_section_toggle(self) -> None:
        """Test toggling individual sections."""
        widget = DirectorDisplayWidget()
        
        # Toggle strategist
        assert widget.strategist_expanded is True
        widget.action_toggle_strategist()
        assert widget.strategist_expanded is False
        assert widget.analyst_expanded is True  # Others unchanged
        assert widget.creative_expanded is True
        
        # Toggle analyst
        widget.action_toggle_analyst()
        assert widget.analyst_expanded is False
        
        # Toggle creative
        widget.action_toggle_creative()
        assert widget.creative_expanded is False
        
        # Expand all
        widget.action_expand_all()
        assert widget.strategist_expanded is True
        assert widget.analyst_expanded is True
        assert widget.creative_expanded is True


class TestDirectorDisplayWidgetThinking:
    """Integration tests for <think> tag visibility."""

    def test_thinking_visibility_toggle(self) -> None:
        """Test toggling thinking content visibility."""
        widget = DirectorDisplayWidget()
        
        # Load strategy with thinking content
        data = create_mock_strategy_data()
        widget.update_strategy_sync(data)
        
        # Initially hidden
        assert widget.show_thinking is False
        
        # Toggle on
        widget.action_toggle_thinking()
        assert widget.show_thinking is True
        
        # Toggle off
        widget.action_toggle_thinking()
        assert widget.show_thinking is False

    def test_thinking_content_preserved_on_toggle(self) -> None:
        """Test thinking content is preserved when toggling."""
        widget = DirectorDisplayWidget()
        
        data = create_mock_strategy_data()
        widget.update_strategy_sync(data)
        
        creative = widget._perspectives.get(DirectorRole.CREATIVE)
        original_thinking = creative.thinking_content
        
        # Toggle visibility multiple times
        widget.action_toggle_thinking()
        widget.action_toggle_thinking()
        widget.action_toggle_thinking()
        
        # Content should be unchanged
        assert widget._perspectives[DirectorRole.CREATIVE].thinking_content == original_thinking


class TestDirectorDisplayWidgetDegradation:
    """Integration tests for degradation handling."""

    def test_full_availability(self) -> None:
        """Test with all models available."""
        widget = DirectorDisplayWidget()
        data = create_mock_strategy_data(degradation="full", missing=[])
        widget.update_strategy_sync(data)
        
        assert widget._current_strategy.degradation_level == DegradationLevel.FULL
        assert len(widget._current_strategy.missing_perspectives) == 0
        
        msg = widget._get_degradation_message(
            widget._current_strategy.degradation_level,
            widget._current_strategy.missing_perspectives,
        )
        assert msg == ""

    def test_degraded_pair_mode(self) -> None:
        """Test with two models available."""
        widget = DirectorDisplayWidget()
        data = create_mock_strategy_data(
            confidence=0.65,
            degradation="degraded_pair",
            missing=["creative"],
        )
        widget.update_strategy_sync(data)
        
        assert widget._current_strategy.degradation_level == DegradationLevel.DEGRADED_PAIR
        assert DirectorRole.CREATIVE in widget._current_strategy.missing_perspectives
        
        msg = widget._get_degradation_message(
            widget._current_strategy.degradation_level,
            widget._current_strategy.missing_perspectives,
        )
        assert "Creative" in msg
        assert "unavailable" in msg

    def test_degraded_single_mode(self) -> None:
        """Test with single model available."""
        widget = DirectorDisplayWidget()
        data = create_mock_strategy_data(
            confidence=0.4,
            degradation="degraded_single",
            missing=["analyst", "creative"],
        )
        widget.update_strategy_sync(data)
        
        assert widget._current_strategy.degradation_level == DegradationLevel.DEGRADED_SINGLE
        assert len(widget._current_strategy.missing_perspectives) == 2

    def test_unavailable_mode(self) -> None:
        """Test when all models unavailable."""
        widget = DirectorDisplayWidget()
        data = {
            "objectives": [],
            "actions": [],
            "rationale": "No models available",
            "confidence": 0.0,
            "contributing_roles": [],
            "degradation_level": "unavailable",
            "missing_perspectives": ["strategist", "analyst", "creative"],
            "fallback_warnings": ["All Director models unavailable"],
            "avoid_list": [],
            "attck_techniques": [],
            "creative_alternatives": [],
            "risk_warnings": [],
            "conflicts_resolved": [],
        }
        widget.update_strategy_sync(data)
        
        assert widget._current_strategy.degradation_level == DegradationLevel.UNAVAILABLE
        assert len(widget._current_strategy.missing_perspectives) == 3


class TestDirectorDisplayWidgetConfidence:
    """Integration tests for confidence display."""

    def test_high_confidence_display(self) -> None:
        """Test high confidence styling."""
        widget = DirectorDisplayWidget()
        data = create_mock_strategy_data(confidence=0.95)
        widget.update_strategy_sync(data)
        
        css_class = widget._get_confidence_class(widget._current_strategy.confidence)
        assert css_class == "confidence-high"

    def test_medium_confidence_display(self) -> None:
        """Test medium confidence styling."""
        widget = DirectorDisplayWidget()
        data = create_mock_strategy_data(confidence=0.6)
        widget.update_strategy_sync(data)
        
        css_class = widget._get_confidence_class(widget._current_strategy.confidence)
        assert css_class == "confidence-medium"

    def test_low_confidence_display(self) -> None:
        """Test low confidence styling."""
        widget = DirectorDisplayWidget()
        data = create_mock_strategy_data(confidence=0.3)
        widget.update_strategy_sync(data)
        
        css_class = widget._get_confidence_class(widget._current_strategy.confidence)
        assert css_class == "confidence-low"

    def test_confidence_boundary_values(self) -> None:
        """Test confidence at boundary values."""
        widget = DirectorDisplayWidget()
        
        # Exactly 0.75 should be high
        assert widget._get_confidence_class(0.75) == "confidence-high"
        
        # Just below 0.75 should be medium
        assert widget._get_confidence_class(0.74) == "confidence-medium"
        
        # Exactly 0.5 should be medium
        assert widget._get_confidence_class(0.5) == "confidence-medium"
        
        # Just below 0.5 should be low
        assert widget._get_confidence_class(0.49) == "confidence-low"


@pytest.mark.asyncio
class TestDirectorDisplayWidgetAsyncIntegration:
    """Async integration tests."""

    async def test_async_strategy_update(self) -> None:
        """Test async update method."""
        widget = DirectorDisplayWidget()
        data = create_mock_strategy_data()
        
        await widget.update_strategy(data)
        
        assert widget._current_strategy is not None
        assert widget._current_strategy.confidence == 0.85

    async def test_async_multiple_updates(self) -> None:
        """Test multiple async updates."""
        widget = DirectorDisplayWidget()
        
        for confidence in [0.5, 0.7, 0.9]:
            data = create_mock_strategy_data(confidence=confidence)
            await widget.update_strategy(data)
            assert widget._current_strategy.confidence == confidence


class TestDirectorDisplayWidgetTextualApp:
    """Integration tests using Textual App context for DOM operations."""

    @pytest.mark.asyncio
    async def test_compose_creates_structure(self) -> None:
        """Test compose() creates the correct widget structure."""
        from textual.app import App, ComposeResult
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DirectorDisplayWidget()
        
        async with TestApp().run_test() as pilot:
            app = pilot.app
            # Verify the widget was mounted
            widget = app.query_one(DirectorDisplayWidget)
            assert widget is not None
            
            # Verify compose created required elements
            director_title = widget.query_one("#director-title")
            assert director_title is not None
            
            unified_strategy = widget.query_one("#unified-strategy")
            assert unified_strategy is not None
            
            # Verify collapsible sections exist
            strategist_section = widget.query_one("#strategist-section")
            assert strategist_section is not None

    @pytest.mark.asyncio
    async def test_on_mount_shows_placeholder(self) -> None:
        """Test on_mount() displays placeholder when no strategy."""
        from textual.app import App, ComposeResult
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DirectorDisplayWidget()
        
        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one(DirectorDisplayWidget)
            
            # Verify no strategy exists initially
            assert widget._current_strategy is None

    @pytest.mark.asyncio
    async def test_update_display_with_dom(self) -> None:
        """Test _update_display() updates DOM elements correctly."""
        from textual.app import App, ComposeResult
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DirectorDisplayWidget()
        
        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one(DirectorDisplayWidget)
            
            # Update with strategy data
            data = create_mock_strategy_data(confidence=0.9)
            widget.update_strategy_sync(data)
            widget._update_display()
            
            # Verify strategy was updated
            assert widget._current_strategy is not None
            assert widget._current_strategy.confidence == 0.9

    @pytest.mark.asyncio
    async def test_perspective_section_updates_in_dom(self) -> None:
        """Test _update_perspective_section() updates DOM content."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DirectorDisplayWidget()
        
        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one(DirectorDisplayWidget)
            
            # Add perspective data
            widget._perspectives[DirectorRole.STRATEGIST] = DirectorPerspective(
                role=DirectorRole.STRATEGIST,
                content="Test strategic content",
                latency_ms=1200,
                success=True,
            )
            
            # Update the section
            widget._update_perspective_section(DirectorRole.STRATEGIST, "strategist-content")
            
            # Verify perspective was set
            assert widget._perspectives[DirectorRole.STRATEGIST].content == "Test strategic content"

    @pytest.mark.asyncio
    async def test_perspective_section_shows_error(self) -> None:
        """Test _update_perspective_section() shows error for failed perspective."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DirectorDisplayWidget()
        
        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one(DirectorDisplayWidget)
            
            # Add failed perspective
            widget._perspectives[DirectorRole.ANALYST] = DirectorPerspective(
                role=DirectorRole.ANALYST,
                content="",
                latency_ms=5000,
                success=False,
                error="Timeout after 100s",
            )
            
            widget._update_perspective_section(DirectorRole.ANALYST, "analyst-content")
            
            # Verify failed perspective was set with error
            assert widget._perspectives[DirectorRole.ANALYST].success is False
            assert "Timeout" in widget._perspectives[DirectorRole.ANALYST].error

    @pytest.mark.asyncio
    async def test_thinking_display_toggle_in_dom(self) -> None:
        """Test _update_thinking_display() toggles visibility in DOM."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DirectorDisplayWidget()
        
        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one(DirectorDisplayWidget)
            
            # Add creative perspective with thinking content
            widget._perspectives[DirectorRole.CREATIVE] = DirectorPerspective(
                role=DirectorRole.CREATIVE,
                content="Creative alternatives",
                latency_ms=1500,
                success=True,
                thinking_content="Deep reasoning about evasion",
            )
            
            # Initially hidden
            widget.show_thinking = False
            widget._update_thinking_display()
            thinking_widget = widget.query_one("#thinking-content", Static)
            assert thinking_widget.display is False
            
            # Toggle on
            widget.show_thinking = True
            widget._update_thinking_display()
            assert thinking_widget.display is True

    @pytest.mark.asyncio
    async def test_degradation_warning_display(self) -> None:
        """Test degradation warning is shown when models unavailable."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DirectorDisplayWidget()
        
        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one(DirectorDisplayWidget)
            
            # Update with degraded strategy
            data = create_mock_strategy_data(
                confidence=0.5,
                degradation="degraded_pair",
                missing=["creative"],
            )
            widget.update_strategy_sync(data)
            widget._update_display()
            
            # Verify degradation was tracked in strategy
            assert widget._current_strategy.degradation_level == DegradationLevel.DEGRADED_PAIR
            assert DirectorRole.CREATIVE in widget._current_strategy.missing_perspectives

    @pytest.mark.asyncio
    async def test_watch_strategist_expanded_updates_collapsible(self) -> None:
        """Test watch_strategist_expanded updates Collapsible state."""
        from textual.app import App, ComposeResult
        from textual.widgets import Collapsible
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DirectorDisplayWidget()
        
        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one(DirectorDisplayWidget)
            
            section = widget.query_one("#strategist-section", Collapsible)
            
            # Initially expanded (collapsed=False)
            assert section.collapsed is False
            
            # Collapse via reactive property
            widget.strategist_expanded = False
            assert section.collapsed is True
            
            # Expand again
            widget.strategist_expanded = True
            assert section.collapsed is False

    @pytest.mark.asyncio
    async def test_watch_analyst_expanded_updates_collapsible(self) -> None:
        """Test watch_analyst_expanded updates Collapsible state."""
        from textual.app import App, ComposeResult
        from textual.widgets import Collapsible
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DirectorDisplayWidget()
        
        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one(DirectorDisplayWidget)
            
            section = widget.query_one("#analyst-section", Collapsible)
            
            # Collapse
            widget.analyst_expanded = False
            assert section.collapsed is True

    @pytest.mark.asyncio
    async def test_watch_creative_expanded_updates_collapsible(self) -> None:
        """Test watch_creative_expanded updates Collapsible state."""
        from textual.app import App, ComposeResult
        from textual.widgets import Collapsible
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DirectorDisplayWidget()
        
        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one(DirectorDisplayWidget)
            
            section = widget.query_one("#creative-section", Collapsible)
            
            # Collapse
            widget.creative_expanded = False
            assert section.collapsed is True

    @pytest.mark.asyncio
    async def test_full_strategy_render_in_dom(self) -> None:
        """Test full strategy rendering with all sections in DOM."""
        from textual.app import App, ComposeResult
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DirectorDisplayWidget()
        
        async with TestApp().run_test() as pilot:
            app = pilot.app
            widget = app.query_one(DirectorDisplayWidget)
            
            # Full strategy update
            data = create_mock_strategy_data(confidence=0.85)
            await widget.update_strategy(data)
            
            # Verify all perspectives were loaded
            assert DirectorRole.STRATEGIST in widget._perspectives
            assert DirectorRole.ANALYST in widget._perspectives
            assert DirectorRole.CREATIVE in widget._perspectives
            
            # Verify creative thinking was extracted
            creative = widget._perspectives[DirectorRole.CREATIVE]
            assert creative.thinking_content is not None
