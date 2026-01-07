"""Integration tests for Configuration Hot Reload (Story 2.13).

Tests the full hot reload pipeline:
1. File modification
2. Watchdog detection
3. Daemon/SettingsHolder handling
4. Config application (or rejection)
"""

import time
import pytest
from pathlib import Path
from typing import Generator

from cyberred.core.config import _SettingsHolder, get_settings, get_reload_status, reset_settings


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """Create a temporary config file."""
    path = tmp_path / "config.yaml"
    path.write_text("llm:\n  timeout: 180\n")
    return path


@pytest.fixture(autouse=True)
def reset_before_test() -> Generator[None, None, None]:
    """Reset settings singleton before each test."""
    reset_settings()
    yield
    reset_settings()


class TestConfigHotReloadIntegration:
    """Integration tests for config hot reload."""

    @pytest.mark.integration
    def test_daemon_reloads_config_on_file_change(self, config_file: Path) -> None:
        """Test daemon reloads config when file changes (safe change)."""
        # Initialize settings with file watching
        settings = get_settings(
            force_reload=True,
            system_config_path=config_file
        )
        
        # Manually start watching (simulating daemon behavior)
        _SettingsHolder.start_watching(config_file)
        
        try:
            assert settings.llm.timeout == 180
            
            # Wait for watcher to stabilize
            time.sleep(0.5)
            
            # Modify config (safe change)
            config_file.write_text("llm:\n  timeout: 300\n")
            
            # Wait for reload (debounce is 1.0s + processing time)
            time.sleep(1.5)
            
            # Verify reload happened
            status = get_reload_status()
            assert status["last_reload"] is not None
            assert status["pending_unsafe_changes"] == []
            
            # Verify new value
            new_settings = get_settings()
            assert new_settings.llm.timeout == 300
            
        finally:
            _SettingsHolder.stop_watching()

    @pytest.mark.integration
    def test_daemon_ignores_unsafe_config_changes(self, config_file: Path) -> None:
        """Test daemon ignores unsafe config changes."""
        # Add initial redis config
        config_file.write_text("redis:\n  port: 6379\n")
        
        # Initialize settings
        settings = get_settings(
            force_reload=True,
            system_config_path=config_file
        )
        
        _SettingsHolder.start_watching(config_file)
        
        try:
            assert settings.redis.port == 6379
            
            time.sleep(0.5)
            
            # Modify config (unsafe change)
            config_file.write_text("redis:\n  port: 6380\n")
            
            # Wait for processing
            time.sleep(1.5)
            
            # Verify NO reload happened to settings object
            current_settings = get_settings()
            assert current_settings.redis.port == 6379
            
            # Verify unsafe change detected
            status = get_reload_status()
            assert "redis.port" in status["pending_unsafe_changes"]
            
        finally:
            _SettingsHolder.stop_watching()
