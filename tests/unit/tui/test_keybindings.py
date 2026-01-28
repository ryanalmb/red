"""Unit tests for keybindings module.

Story 9.11: Keyboard Navigation (F-Keys) - Task 9

Tests for configurable F-key bindings:
- Default mappings loading
- Custom config loading from YAML
- Invalid config handling (warnings, no crash)
- Mapping override precedence
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import yaml


class TestLoadKeybindings:
    """Tests for load_keybindings function."""

    def test_load_keybindings_returns_default_when_no_config(self) -> None:
        """Test load_keybindings returns defaults when config doesn't exist."""
        from cyberred.tui.keybindings import load_keybindings, DEFAULT_FKEY_MAPPINGS
        
        result = load_keybindings(None)
        
        assert result == DEFAULT_FKEY_MAPPINGS

    def test_load_keybindings_returns_default_for_nonexistent_file(self) -> None:
        """Test load_keybindings returns defaults for nonexistent config file."""
        from cyberred.tui.keybindings import load_keybindings, DEFAULT_FKEY_MAPPINGS
        
        result = load_keybindings(Path("/nonexistent/path/config.yaml"))
        
        assert result == DEFAULT_FKEY_MAPPINGS

    def test_load_keybindings_from_valid_yaml(self) -> None:
        """Test load_keybindings loads custom mappings from YAML."""
        from cyberred.tui.keybindings import load_keybindings, FKeyMapping
        
        config_content = {
            "tui": {
                "keybindings": {
                    "f1": {"action": "custom_action", "label": "Custom"},
                    "f2": {"action": "another_action", "label": "Another"},
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_content, f)
            config_path = Path(f.name)
        
        try:
            result = load_keybindings(config_path)
            
            # Should have custom mappings
            assert len(result) >= 2
            
            # Find f1 mapping
            f1_mapping = next((m for m in result if m.key == "f1"), None)
            assert f1_mapping is not None
            assert f1_mapping.action == "custom_action"
            assert f1_mapping.label == "Custom"
        finally:
            config_path.unlink()

    def test_load_keybindings_merges_with_defaults(self) -> None:
        """Test custom config merges with defaults (overrides take precedence)."""
        from cyberred.tui.keybindings import load_keybindings, DEFAULT_FKEY_MAPPINGS
        
        # Override only f1
        config_content = {
            "tui": {
                "keybindings": {
                    "f1": {"action": "overridden", "label": "New"},
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_content, f)
            config_path = Path(f.name)
        
        try:
            result = load_keybindings(config_path)
            
            # f1 should be overridden
            f1_mapping = next((m for m in result if m.key == "f1"), None)
            assert f1_mapping is not None
            assert f1_mapping.action == "overridden"
            
            # Other defaults should still exist
            f2_mapping = next((m for m in result if m.key == "f2"), None)
            assert f2_mapping is not None
            # Default f2 action is "config"
            assert f2_mapping.action == "config"
        finally:
            config_path.unlink()

    def test_load_keybindings_handles_invalid_yaml(self) -> None:
        """Test load_keybindings handles invalid YAML gracefully."""
        from cyberred.tui.keybindings import load_keybindings, DEFAULT_FKEY_MAPPINGS
        
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("invalid: yaml: content: [[[")
            config_path = Path(f.name)
        
        try:
            # Should not crash, should return defaults
            result = load_keybindings(config_path)
            assert result == DEFAULT_FKEY_MAPPINGS
        finally:
            config_path.unlink()

    def test_load_keybindings_warns_on_invalid_mapping(self) -> None:
        """Test load_keybindings logs warning for invalid mapping (AC #5)."""
        from cyberred.tui.keybindings import load_keybindings
        import logging
        
        # Config with invalid mapping (missing required fields)
        config_content = {
            "tui": {
                "keybindings": {
                    "f1": {"action": "valid"},  # Missing label
                    "f2": {"label": "NoAction"},  # Missing action
                    "f3": "not_a_dict",  # Invalid format
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_content, f)
            config_path = Path(f.name)
        
        try:
            with patch("cyberred.tui.keybindings.logger") as mock_logger:
                result = load_keybindings(config_path)
                
                # Should have logged warnings
                assert mock_logger.warning.called
        finally:
            config_path.unlink()

    def test_load_keybindings_empty_config_returns_defaults(self) -> None:
        """Test empty config file returns defaults."""
        from cyberred.tui.keybindings import load_keybindings, DEFAULT_FKEY_MAPPINGS
        
        config_content = {}
        
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_content, f)
            config_path = Path(f.name)
        
        try:
            result = load_keybindings(config_path)
            assert result == DEFAULT_FKEY_MAPPINGS
        finally:
            config_path.unlink()

    def test_load_keybindings_no_tui_section_returns_defaults(self) -> None:
        """Test config without tui section returns defaults."""
        from cyberred.tui.keybindings import load_keybindings, DEFAULT_FKEY_MAPPINGS
        
        config_content = {"other": {"setting": "value"}}
        
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_content, f)
            config_path = Path(f.name)
        
        try:
            result = load_keybindings(config_path)
            assert result == DEFAULT_FKEY_MAPPINGS
        finally:
            config_path.unlink()

    def test_load_keybindings_handles_file_read_error(self) -> None:
        """Test load_keybindings handles generic file read errors gracefully."""
        from cyberred.tui.keybindings import load_keybindings, DEFAULT_FKEY_MAPPINGS
        
        # Create a valid file but mock open to raise IOError
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("valid: yaml")
            config_path = Path(f.name)
        
        try:
            # Patch open in the keybindings module to raise IOError
            with patch("cyberred.tui.keybindings.open", side_effect=IOError("Read error")):
                result = load_keybindings(config_path)
                assert result == DEFAULT_FKEY_MAPPINGS
        finally:
            config_path.unlink()

    def test_load_keybindings_empty_keybindings_section(self) -> None:
        """Test config with empty keybindings section returns defaults."""
        from cyberred.tui.keybindings import load_keybindings, DEFAULT_FKEY_MAPPINGS
        
        # keybindings is None
        config_content = {"tui": {"keybindings": None}}
        
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_content, f)
            config_path = Path(f.name)
        
        try:
            result = load_keybindings(config_path)
            assert result == DEFAULT_FKEY_MAPPINGS
        finally:
            config_path.unlink()

    def test_load_keybindings_keybindings_not_dict(self) -> None:
        """Test config with non-dict keybindings returns defaults."""
        from cyberred.tui.keybindings import load_keybindings, DEFAULT_FKEY_MAPPINGS
        
        # keybindings is a list instead of dict
        config_content = {"tui": {"keybindings": ["f1", "f2"]}}
        
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_content, f)
            config_path = Path(f.name)
        
        try:
            result = load_keybindings(config_path)
            assert result == DEFAULT_FKEY_MAPPINGS
        finally:
            config_path.unlink()

    def test_load_keybindings_non_standard_keys_sorted_last(self) -> None:
        """Test non-standard keys (non-fkey) are sorted to the end."""
        from cyberred.tui.keybindings import load_keybindings
        
        config_content = {
            "tui": {
                "keybindings": {
                    "ctrl_x": {"action": "custom", "label": "Cust"},
                    "f1": {"action": "dashboard", "label": "Dash"},
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_content, f)
            config_path = Path(f.name)
        
        try:
            result = load_keybindings(config_path)
            # Non-standard key should be sorted last
            last_mapping = result[-1]
            assert last_mapping.key == "ctrl_x"
        finally:
            config_path.unlink()


class TestValidateMapping:
    """Tests for mapping validation."""

    def test_validate_mapping_valid(self) -> None:
        """Test valid mapping passes validation."""
        from cyberred.tui.keybindings import validate_mapping
        
        mapping_data = {"action": "dashboard", "label": "Dash"}
        
        result = validate_mapping("f1", mapping_data)
        
        assert result is True

    def test_validate_mapping_missing_action(self) -> None:
        """Test mapping without action fails validation."""
        from cyberred.tui.keybindings import validate_mapping
        
        mapping_data = {"label": "Dash"}
        
        result = validate_mapping("f1", mapping_data)
        
        assert result is False

    def test_validate_mapping_missing_label(self) -> None:
        """Test mapping without label fails validation."""
        from cyberred.tui.keybindings import validate_mapping
        
        mapping_data = {"action": "dashboard"}
        
        result = validate_mapping("f1", mapping_data)
        
        assert result is False

    def test_validate_mapping_not_dict(self) -> None:
        """Test non-dict mapping fails validation."""
        from cyberred.tui.keybindings import validate_mapping
        
        result = validate_mapping("f1", "not_a_dict")
        
        assert result is False

    def test_validate_mapping_none(self) -> None:
        """Test None mapping fails validation."""
        from cyberred.tui.keybindings import validate_mapping
        
        result = validate_mapping("f1", None)
        
        assert result is False


class TestDefaultMappingsExport:
    """Tests for default mappings export."""

    def test_default_fkey_mappings_exported(self) -> None:
        """Test DEFAULT_FKEY_MAPPINGS is exported from module."""
        from cyberred.tui.keybindings import DEFAULT_FKEY_MAPPINGS
        
        assert DEFAULT_FKEY_MAPPINGS is not None
        assert len(DEFAULT_FKEY_MAPPINGS) > 0

    def test_fkey_mapping_exported(self) -> None:
        """Test FKeyMapping is exported from module."""
        from cyberred.tui.keybindings import FKeyMapping
        
        assert FKeyMapping is not None


class TestGetMappingForKey:
    """Tests for getting mapping by key."""

    def test_get_mapping_for_existing_key(self) -> None:
        """Test getting mapping for an existing key."""
        from cyberred.tui.keybindings import get_mapping_for_key, DEFAULT_FKEY_MAPPINGS
        
        result = get_mapping_for_key("f1", DEFAULT_FKEY_MAPPINGS)
        
        assert result is not None
        assert result.key == "f1"

    def test_get_mapping_for_nonexistent_key(self) -> None:
        """Test getting mapping for nonexistent key returns None."""
        from cyberred.tui.keybindings import get_mapping_for_key, DEFAULT_FKEY_MAPPINGS
        
        result = get_mapping_for_key("f99", DEFAULT_FKEY_MAPPINGS)
        
        assert result is None

    def test_get_mapping_for_key_empty_list(self) -> None:
        """Test getting mapping from empty list returns None."""
        from cyberred.tui.keybindings import get_mapping_for_key
        
        result = get_mapping_for_key("f1", [])
        
        assert result is None
