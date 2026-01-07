"""Configuration File Watcher for Hot Reload.

Provides filesystem monitoring for config files using watchdog.
Detects changes and triggers callback for hot reload processing.

Story 2.13: Configuration Hot Reload (FR46).

Usage:
    from cyberred.core.config_watcher import ConfigWatcher
    
    def on_change(path: Path) -> None:
        print(f"Config changed: {path}")
    
    watcher = ConfigWatcher(
        config_path=Path("~/.cyber-red/config.yaml"),
        callback=on_change,
    )
    watcher.start()
    # ... later
    watcher.stop()
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

import structlog
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from watchdog.observers import Observer

log = structlog.get_logger()


class ConfigEventHandler(FileSystemEventHandler):
    """Handles file system events for config file changes.
    
    Implements debouncing to handle editors that write multiple times
    during a single save operation.
    """
    
    def __init__(
        self,
        config_path: Path,
        callback: Callable[[Path], None],
        debounce_seconds: float = 1.0,
    ) -> None:
        """Initialize event handler.
        
        Args:
            config_path: Path to the config file to watch.
            callback: Function to call when config changes.
            debounce_seconds: Time to wait for rapid changes to settle.
        """
        super().__init__()
        self._config_path = config_path.resolve()
        self._config_filename = config_path.name
        self._callback = callback
        self._debounce_seconds = debounce_seconds
        self._last_modified: float = 0.0
        self._lock = threading.Lock()
    
    def on_modified(self, event: FileModifiedEvent) -> None:
        """Handle file modification events.
        
        Filters for the specific config file and debounces rapid changes.
        """
        if event.is_directory:
            return
            
        # Check if this is our config file
        event_path = Path(event.src_path).resolve()
        if event_path != self._config_path:
            return
        
        current_time = time.time()
        
        with self._lock:
            # Debounce: ignore if we just processed a change
            if current_time - self._last_modified < self._debounce_seconds:
                log.debug(
                    "config_change_debounced",
                    path=str(event_path),
                    since_last=current_time - self._last_modified,
                )
                return
            
            self._last_modified = current_time
        
        log.debug("config_file_modified", path=str(event_path))
        
        try:
            self._callback(event_path)
        except Exception as e:
            log.error(
                "config_change_callback_error",
                path=str(event_path),
                error=str(e),
            )


class ConfigWatcher:
    """Watches config files for changes and triggers hot reload.
    
    Uses watchdog for cross-platform filesystem events:
    - Linux: inotify
    - macOS: FSEvents
    - Windows: ReadDirectoryChangesW
    
    Attributes:
        config_path: Path to the config file being watched.
        is_running: Whether the watcher is currently active.
    """
    
    def __init__(
        self,
        config_path: Path,
        callback: Callable[[Path], None],
        debounce_seconds: float = 1.0,
    ) -> None:
        """Initialize ConfigWatcher.
        
        Args:
            config_path: Path to the config file to watch.
            callback: Function to call when config changes.
            debounce_seconds: Time to wait for rapid changes to settle.
                Defaults to 1.0 seconds.
        """
        self._config_path = Path(config_path).expanduser().resolve()
        self._callback = callback
        self._debounce_seconds = debounce_seconds
        self._observer: Optional[Observer] = None
        self._running = False
    
    @property
    def config_path(self) -> Path:
        """Get the watched config file path."""
        return self._config_path
    
    @property
    def is_running(self) -> bool:
        """Check if watcher is currently running."""
        return self._running
    
    def start(self) -> None:
        """Start watching the config file for changes.
        
        Creates a background thread that monitors the config file's
        parent directory for modifications.
        
        Raises:
            FileNotFoundError: If config file doesn't exist.
            RuntimeError: If watcher is already running.
        """
        if self._running:
            raise RuntimeError("ConfigWatcher is already running")
        
        if not self._config_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {self._config_path}"
            )
        
        # Watch the parent directory (required for some editors that
        # delete and recreate files during save)
        watch_dir = self._config_path.parent
        
        event_handler = ConfigEventHandler(
            config_path=self._config_path,
            callback=self._callback,
            debounce_seconds=self._debounce_seconds,
        )
        
        self._observer = Observer()
        self._observer.schedule(event_handler, str(watch_dir), recursive=False)
        self._observer.start()
        self._running = True
        
        log.info(
            "config_watcher_started",
            config_path=str(self._config_path),
            watch_dir=str(watch_dir),
        )
    
    def stop(self) -> None:
        """Stop watching the config file.
        
        Stops the background observer thread and waits for it to finish.
        Safe to call even if watcher is not running.
        """
        if not self._running or self._observer is None:
            return
        
        self._observer.stop()
        self._observer.join(timeout=5.0)
        self._observer = None
        self._running = False
        
        log.info("config_watcher_stopped", config_path=str(self._config_path))
