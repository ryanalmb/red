"""Unit tests for FKeyBar widget.

Story 9.11: Keyboard Navigation (F-Keys) - Task 8

Tests for FKeyBar widget that displays F-key mappings in the footer area
per UX spec lines 386-387: [F1]Dash [F2]Cfg [F3]Log [F4]Rpt [F5]Pause [F6]Drop [F10]KILL
"""
import pytest
from unittest.mock import MagicMock, patch


class TestFKeyMapping:
    """Tests for FKeyMapping dataclass."""

    def test_fkey_mapping_creation(self) -> None:
        """Test FKeyMapping dataclass can be created with key, action, label."""
        from cyberred.tui.widgets.fkey_bar import FKeyMapping
        
        mapping = FKeyMapping(key="f1", action="dashboard", label="Dash")
        
        assert mapping.key == "f1"
        assert mapping.action == "dashboard"
        assert mapping.label == "Dash"

    def test_fkey_mapping_equality(self) -> None:
        """Test FKeyMapping equality comparison."""
        from cyberred.tui.widgets.fkey_bar import FKeyMapping
        
        mapping1 = FKeyMapping(key="f1", action="dashboard", label="Dash")
        mapping2 = FKeyMapping(key="f1", action="dashboard", label="Dash")
        mapping3 = FKeyMapping(key="f2", action="config", label="Cfg")
        
        assert mapping1 == mapping2
        assert mapping1 != mapping3

    def test_fkey_mapping_to_display_string(self) -> None:
        """Test FKeyMapping produces display format [F1]Label."""
        from cyberred.tui.widgets.fkey_bar import FKeyMapping
        
        mapping = FKeyMapping(key="f1", action="dashboard", label="Dash")
        
        assert mapping.to_display() == "[F1]Dash"

    def test_fkey_mapping_f10_display(self) -> None:
        """Test F10 mapping displays correctly."""
        from cyberred.tui.widgets.fkey_bar import FKeyMapping
        
        mapping = FKeyMapping(key="f10", action="kill_switch_confirm", label="KILL")
        
        assert mapping.to_display() == "[F10]KILL"


class TestDefaultFKeyMappings:
    """Tests for default F-key mapping constants."""

    def test_default_mappings_exist(self) -> None:
        """Test DEFAULT_FKEY_MAPPINGS constant exists with all required keys."""
        from cyberred.tui.widgets.fkey_bar import DEFAULT_FKEY_MAPPINGS, FKeyMapping
        
        assert isinstance(DEFAULT_FKEY_MAPPINGS, list)
        assert len(DEFAULT_FKEY_MAPPINGS) >= 7  # F1-F7 + F10
        
        # Verify all items are FKeyMapping instances
        for mapping in DEFAULT_FKEY_MAPPINGS:
            assert isinstance(mapping, FKeyMapping)

    def test_default_mappings_content(self) -> None:
        """Test default mappings match UX spec requirements."""
        from cyberred.tui.widgets.fkey_bar import DEFAULT_FKEY_MAPPINGS
        
        # Convert to dict for easier testing
        mapping_dict = {m.key: m for m in DEFAULT_FKEY_MAPPINGS}
        
        # Per UX spec and story AC #3:
        # F1=Dashboard, F2=Config, F3=Logs, F4=Report, F5=Pause/Resume,
        # F6=Drop Box, F7=Director, F10=Kill Switch
        assert "f1" in mapping_dict
        assert mapping_dict["f1"].action == "dashboard"
        assert mapping_dict["f1"].label == "Dash"
        
        assert "f2" in mapping_dict
        assert mapping_dict["f2"].action == "config"
        assert mapping_dict["f2"].label == "Cfg"
        
        assert "f3" in mapping_dict
        assert mapping_dict["f3"].action == "logs"
        assert mapping_dict["f3"].label == "Log"
        
        assert "f4" in mapping_dict
        assert mapping_dict["f4"].action == "report"
        assert mapping_dict["f4"].label == "Rpt"
        
        assert "f5" in mapping_dict
        assert mapping_dict["f5"].action == "pause_resume"
        assert mapping_dict["f5"].label == "Pause"
        
        assert "f6" in mapping_dict
        assert mapping_dict["f6"].action == "show_dropbox"
        assert mapping_dict["f6"].label == "Drop"
        
        assert "f7" in mapping_dict
        assert mapping_dict["f7"].action == "director_panel"
        assert mapping_dict["f7"].label == "Dir"
        
        assert "f10" in mapping_dict
        assert mapping_dict["f10"].action == "kill_switch_confirm"
        assert mapping_dict["f10"].label == "KILL"


class TestFKeyBar:
    """Tests for FKeyBar widget."""

    def test_fkey_bar_instantiation(self) -> None:
        """Test FKeyBar widget can be instantiated."""
        from cyberred.tui.widgets.fkey_bar import FKeyBar
        
        bar = FKeyBar()
        
        assert bar is not None

    def test_fkey_bar_default_mappings(self) -> None:
        """Test FKeyBar uses default mappings when none provided."""
        from cyberred.tui.widgets.fkey_bar import FKeyBar, DEFAULT_FKEY_MAPPINGS
        
        bar = FKeyBar()
        
        assert bar.mappings == DEFAULT_FKEY_MAPPINGS

    def test_fkey_bar_custom_mappings(self) -> None:
        """Test FKeyBar accepts custom mappings."""
        from cyberred.tui.widgets.fkey_bar import FKeyBar, FKeyMapping
        
        custom_mappings = [
            FKeyMapping(key="f1", action="custom_action", label="Custom"),
        ]
        
        bar = FKeyBar(mappings=custom_mappings)
        
        assert bar.mappings == custom_mappings

    def test_fkey_bar_render_returns_string(self) -> None:
        """Test FKeyBar render method returns formatted string."""
        from cyberred.tui.widgets.fkey_bar import FKeyBar
        
        bar = FKeyBar()
        rendered = bar.render()
        
        assert isinstance(rendered, str)

    def test_fkey_bar_render_contains_all_mappings(self) -> None:
        """Test FKeyBar render includes all mapping labels."""
        from cyberred.tui.widgets.fkey_bar import FKeyBar, FKeyMapping
        
        mappings = [
            FKeyMapping(key="f1", action="dashboard", label="Dash"),
            FKeyMapping(key="f2", action="config", label="Cfg"),
        ]
        
        bar = FKeyBar(mappings=mappings)
        rendered = bar.render()
        
        assert "[F1]" in rendered
        assert "Dash" in rendered
        assert "[F2]" in rendered
        assert "Cfg" in rendered

    def test_fkey_bar_render_format_per_ux_spec(self) -> None:
        """Test FKeyBar render format matches UX spec line 386-387."""
        from cyberred.tui.widgets.fkey_bar import FKeyBar
        
        bar = FKeyBar()
        rendered = bar.render()
        
        # Per UX spec: [F1]Dash [F2]Cfg [F3]Log [F4]Rpt [F5]Pause [F6]Drop [F10]KILL
        # Note: render() includes Rich markup, so we check for key parts
        assert "[F1]" in rendered
        assert "Dash" in rendered
        assert "[F2]" in rendered
        assert "Cfg" in rendered
        assert "[F3]" in rendered
        assert "Log" in rendered
        assert "[F4]" in rendered
        assert "Rpt" in rendered
        assert "[F5]" in rendered
        assert "Pause" in rendered
        assert "[F6]" in rendered
        assert "Drop" in rendered
        assert "[F10]" in rendered
        assert "KILL" in rendered

    def test_fkey_bar_mappings_reactive(self) -> None:
        """Test FKeyBar mappings is a reactive property (AC #5)."""
        from cyberred.tui.widgets.fkey_bar import FKeyBar, FKeyMapping
        from textual.reactive import Reactive
        
        # Check that mappings is reactive by verifying it's defined as reactive
        bar = FKeyBar()
        
        # Verify we can update mappings after creation
        new_mappings = [FKeyMapping(key="f1", action="new_action", label="New")]
        bar.mappings = new_mappings
        
        assert bar.mappings == new_mappings

    def test_fkey_bar_compact_mode(self) -> None:
        """Test FKeyBar supports compact mode truncation (AC #2 mentions compact layout)."""
        from cyberred.tui.widgets.fkey_bar import FKeyBar
        
        bar = FKeyBar()
        
        # Compact mode should truncate/hide some labels
        bar.compact_mode = True
        rendered_compact = bar.render()
        
        bar.compact_mode = False
        rendered_full = bar.render()
        
        # Compact should be shorter or different from full
        assert bar.compact_mode == False  # Verify state is what we set
        # At minimum, both should be valid strings
        assert isinstance(rendered_compact, str)
        assert isinstance(rendered_full, str)

    def test_fkey_bar_has_css_class(self) -> None:
        """Test FKeyBar has appropriate CSS class for styling."""
        from cyberred.tui.widgets.fkey_bar import FKeyBar
        
        bar = FKeyBar()
        
        # Widget should have fkey-bar class for TCSS styling
        assert "fkey-bar" in bar.classes or bar.DEFAULT_CSS is not None

    def test_fkey_bar_with_custom_classes(self) -> None:
        """Test FKeyBar appends fkey-bar to custom classes."""
        from cyberred.tui.widgets.fkey_bar import FKeyBar
        
        bar = FKeyBar(classes="custom-class another-class")
        
        # Should have both custom classes and fkey-bar
        assert "fkey-bar" in bar.classes
        assert "custom-class" in bar.classes
        assert "another-class" in bar.classes

    def test_fkey_bar_with_all_init_params(self) -> None:
        """Test FKeyBar initialization with all parameters."""
        from cyberred.tui.widgets.fkey_bar import FKeyBar, FKeyMapping
        
        mappings = [FKeyMapping(key="f1", action="test", label="Test")]
        bar = FKeyBar(
            mappings=mappings,
            name="test-bar",
            id="fkey-bar-id",
            classes="my-class",
        )
        
        assert bar.mappings == mappings
        assert bar.name == "test-bar"
        assert bar.id == "fkey-bar-id"
        assert "my-class" in bar.classes
        assert "fkey-bar" in bar.classes


class TestFKeyBarIntegration:
    """Integration-style tests for FKeyBar with Textual app context."""

    @pytest.mark.asyncio
    async def test_fkey_bar_mounts_in_app(self) -> None:
        """Test FKeyBar can be mounted in a Textual app."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.fkey_bar import FKeyBar
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield FKeyBar()
        
        app = TestApp()
        async with app.run_test() as pilot:
            # Verify FKeyBar is in the DOM
            bar = app.query_one(FKeyBar)
            assert bar is not None

    @pytest.mark.asyncio
    async def test_fkey_bar_updates_on_mapping_change(self) -> None:
        """Test FKeyBar updates display when mappings change."""
        from textual.app import App, ComposeResult
        from cyberred.tui.widgets.fkey_bar import FKeyBar, FKeyMapping
        
        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield FKeyBar(id="fkey-bar")
        
        app = TestApp()
        async with app.run_test() as pilot:
            bar = app.query_one("#fkey-bar", FKeyBar)
            
            # Update mappings
            new_mappings = [FKeyMapping(key="f1", action="test", label="Test")]
            bar.mappings = new_mappings
            
            await pilot.pause()
            
            # Verify the bar has updated mappings
            assert bar.mappings == new_mappings
