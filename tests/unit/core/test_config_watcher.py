"""Unit tests for ConfigWatcher (Story 2.13).

Tests file watching, debouncing, and lifecycle management.
"""

import tempfile
import time
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pytest

from cyberred.core.config_watcher import ConfigWatcher


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    """Create a temporary config file for testing."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("redis:\n  host: localhost\n")
    return config_file


class TestConfigWatcher:
    """Test ConfigWatcher lifecycle and behavior."""

    def test_watcher_start_stop_lifecycle(self, temp_config_file: Path) -> None:
        """Test watcher can be started and stopped cleanly."""
        callback = MagicMock()
        watcher = ConfigWatcher(
            config_path=temp_config_file,
            callback=callback,
        )
        
        assert not watcher.is_running
        
        watcher.start()
        assert watcher.is_running
        
        watcher.stop()
        assert not watcher.is_running

    def test_watcher_detects_file_change(self, temp_config_file: Path) -> None:
        """Test watcher detects file modifications."""
        callback = MagicMock()
        watcher = ConfigWatcher(
            config_path=temp_config_file,
            callback=callback,
            debounce_seconds=0.1,  # Short debounce for testing
        )
        
        watcher.start()
        try:
            # Modify the file
            time.sleep(0.2)  # Let watcher initialize
            temp_config_file.write_text("redis:\n  host: new-host\n")
            
            # Wait for event to be processed
            time.sleep(0.5)
            
            # Callback should have been called with the path
            assert callback.called
            call_args = callback.call_args[0]
            assert call_args[0] == temp_config_file.resolve()
        finally:
            watcher.stop()

    def test_watcher_debounces_rapid_changes(self, temp_config_file: Path) -> None:
        """Test watcher debounces rapid successive changes."""
        callback = MagicMock()
        watcher = ConfigWatcher(
            config_path=temp_config_file,
            callback=callback,
            debounce_seconds=0.5,  # 500ms debounce
        )
        
        watcher.start()
        try:
            time.sleep(0.2)  # Let watcher initialize
            
            # Make rapid successive changes
            for i in range(5):
                temp_config_file.write_text(f"redis:\n  host: host-{i}\n")
                time.sleep(0.05)  # 50ms between writes
            
            # Wait for debounce to settle
            time.sleep(0.8)
            
            # Should only have called once (first change) or twice at most
            # due to debouncing
            assert callback.call_count <= 2
        finally:
            watcher.stop()

    def test_watcher_handles_missing_file_gracefully(self, tmp_path: Path) -> None:
        """Test watcher raises FileNotFoundError for missing files."""
        callback = MagicMock()
        missing_file = tmp_path / "nonexistent.yaml"
        
        watcher = ConfigWatcher(
            config_path=missing_file,
            callback=callback,
        )
        
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            watcher.start()

    def test_watcher_cannot_start_twice(self, temp_config_file: Path) -> None:
        """Test watcher raises RuntimeError if started twice."""
        callback = MagicMock()
        watcher = ConfigWatcher(
            config_path=temp_config_file,
            callback=callback,
        )
        
        watcher.start()
        try:
            with pytest.raises(RuntimeError, match="already running"):
                watcher.start()
        finally:
            watcher.stop()

    def test_stop_is_idempotent(self, temp_config_file: Path) -> None:
        """Test stop() can be called multiple times safely."""
        callback = MagicMock()
        watcher = ConfigWatcher(
            config_path=temp_config_file,
            callback=callback,
        )
        
        # Stop without starting - should not raise
        watcher.stop()
        
        # Start and stop multiple times
        watcher.start()
        watcher.stop()
        watcher.stop()  # Second stop should be safe
        
        assert not watcher.is_running

    def test_config_path_property(self, temp_config_file: Path) -> None:
        """Test config_path property returns the watched path."""
        callback = MagicMock()
        watcher = ConfigWatcher(
            config_path=temp_config_file,
            callback=callback,
        )
        
        assert watcher.config_path == temp_config_file.resolve()

    def test_callback_error_does_not_crash_watcher(
        self, temp_config_file: Path
    ) -> None:
        """Test watcher continues running even if callback raises."""
        callback = MagicMock(side_effect=ValueError("test error"))
        watcher = ConfigWatcher(
            config_path=temp_config_file,
            callback=callback,
            debounce_seconds=0.1,
        )
        
        watcher.start()
        try:
            time.sleep(0.2)
            temp_config_file.write_text("redis:\n  host: error-trigger\n")
            time.sleep(0.5)
            
            # Watcher should still be running despite callback error
            assert watcher.is_running
            assert callback.called
        finally:
            watcher.stop()

    def test_watcher_ignores_other_files(self, temp_config_file: Path) -> None:
        """Test watcher ignores changes to other files in same dir."""
        callback = MagicMock()
        watcher = ConfigWatcher(
            config_path=temp_config_file,
            callback=callback,
            debounce_seconds=0.1,
        )
        
        watcher.start()
        try:
            time.sleep(0.2)
            
            # Create another file in same dir
            other_file = temp_config_file.parent / "other.yaml"
            other_file.write_text("irrelevant")
            
            # Wait - callback should NOT be called
            time.sleep(0.5)
            
            assert not callback.called
            
            # Now modify actual config
            temp_config_file.write_text("modified")
            time.sleep(0.5)
            assert callback.called
        finally:
            watcher.stop()
