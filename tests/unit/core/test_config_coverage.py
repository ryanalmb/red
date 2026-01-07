"""Targeted coverage tests for config.py (Story 2.13).

Addresses specific lines missed by main unit and integration tests.
"""

import pytest
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

from cyberred.core.config import (
    LoggingConfig,
    Settings,
    load_yaml_file,
    load_engagement_config,
    create_settings,
    get_settings,
    _SettingsHolder,
    ConfigurationError,
)
from cyberred.core.config_watcher import ConfigWatcher


class TestConfigCoverage:
    """Tests targeting specific coverage gaps."""

    def test_logging_config_validate_level_invalid(self) -> None:
        """Test validation of invalid log level."""
        with pytest.raises(ValueError, match="Invalid log level"):
            LoggingConfig(level="INVALID")

    def test_settings_logging_alias_property(self) -> None:
        """Test the .logging property alias."""
        settings = Settings()
        assert settings.logging is settings.logging_config
        assert settings.logging.level == "INFO"

    def test_load_yaml_file_errors(self, tmp_path: Path) -> None:
        """Test load_yaml_file error conditions."""
        # File not found
        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            load_yaml_file(tmp_path / "nonexistent.yaml")
            
        # Invalid YAML
        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text("key: : value")  # Invalid YAML syntax
        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            load_yaml_file(invalid_yaml)

    def test_load_engagement_config_defaults(self, tmp_path: Path) -> None:
        """Test default path logic in load_engagement_config."""
        # We need to mock Path.home() to point to tmp_path for testing defaults
        with patch("pathlib.Path.home", return_value=tmp_path):
            # Create the default structure
            eng_dir = tmp_path / ".cyber-red" / "engagements"
            eng_dir.mkdir(parents=True)
            (eng_dir / "test.yaml").write_text("name: test")
            
            # Load without base_path
            config = load_engagement_config("test")
            assert config == {"name": "test"}
            
            # Test missing file
            assert load_engagement_config("missing") == {}

    def test_create_settings_branches(self, tmp_path: Path) -> None:
        """Test various branches in create_settings."""
        # Test .env loading branch
        config_base = tmp_path / ".cyber-red"
        config_base.mkdir()
        env_file = config_base / ".env"
        env_file.write_text("CYBERRED_TEST_VAR=1")
        
        # Mock load_dotenv to verify it's called
        with patch("cyberred.core.config.load_dotenv") as mock_load_dotenv:
            # We need to trigger the branch where system_config_path is None
            # and it defaults to home().
            with patch("pathlib.Path.home", return_value=tmp_path):
                create_settings()
                mock_load_dotenv.assert_called_with(env_file)

    def test_create_settings_runtime_overrides(self) -> None:
        """Test runtime overrides merging."""
        settings = create_settings(runtime_overrides={"runtime": {"paused": True}})
        assert settings.runtime.paused is True

    def test_settings_holder_reset_stops_watcher(self, tmp_path: Path) -> None:
        """Test reset() stops the watcher."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        
        _SettingsHolder.reset()
        _SettingsHolder.start_watching(config_file)
        
        watcher = _SettingsHolder._watcher
        assert watcher is not None
        assert watcher.is_running
        
        # Check that reset stops it
        _SettingsHolder.reset()
        assert not watcher.is_running
        assert _SettingsHolder._watcher is None

    def test_start_watching_stops_existing(self, tmp_path: Path) -> None:
        """Test start_watching stops any existing watcher."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        
        _SettingsHolder.reset()
        _SettingsHolder.start_watching(config_file)
        first_watcher = _SettingsHolder._watcher
        
        # Start again
        _SettingsHolder.start_watching(config_file)
        second_watcher = _SettingsHolder._watcher
        
        assert first_watcher is not second_watcher
        assert not first_watcher.is_running
        assert second_watcher.is_running
        
        _SettingsHolder.stop_watching()

    def test_handle_config_change_edge_cases(self, tmp_path: Path) -> None:
        """Test edge cases in _handle_config_change."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("redis:\n  port: 6379\n")
        
        # Case: _instance is None
        _SettingsHolder.reset()
        assert _SettingsHolder._instance is None
        # Should return early and not crash
        _SettingsHolder._handle_config_change(config_file)
        
        # Initialize
        _SettingsHolder.get(force_reload=True, system_config_path=config_file)
        
        # Case: Config validation error
        config_file.write_text("redis:\n  port: INVALID\n")
        # Should log error and return
        _SettingsHolder._handle_config_change(config_file)
        # Verify old config still active
        assert _SettingsHolder._instance.redis.port == 6379
        
        # Case: No changes (same file content)
        config_file.write_text("redis:\n  port: 6379\n")
        _SettingsHolder._handle_config_change(config_file)

    def test_get_settings_warning(self) -> None:
        """Test warning when args ignored."""
        _SettingsHolder.get(force_reload=True)
        
        with pytest.warns(RuntimeWarning, match="Arguments provided to get_settings"):
            get_settings(runtime_overrides={"foo": "bar"})
