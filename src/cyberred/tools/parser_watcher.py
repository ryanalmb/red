
from pathlib import Path
from typing import Dict, Optional

import importlib
import importlib.util
import inspect
import threading

import structlog
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from cyberred.tools.output import OutputProcessor

log = structlog.get_logger()

class ParserWatcher(FileSystemEventHandler):
    """Watches for changes in parser files and reloads them dynamically."""
    
    def __init__(self, parsers_dir: Path, processor: OutputProcessor):
        self._parsers_dir = parsers_dir
        self._processor = processor
        self._observer = None
        self._timers: Dict[str, threading.Timer] = {}
        log.info("parser_watcher_initialized", directory=str(parsers_dir))

    def on_modified(self, event) -> None:
        if event.src_path.endswith('.py') and '__pycache__' not in event.src_path:
            self._schedule_reload(Path(event.src_path))

    def on_created(self, event) -> None:
        if event.src_path.endswith('.py') and '__pycache__' not in event.src_path:
            self._schedule_reload(Path(event.src_path))

    def _schedule_reload(self, path: Path) -> None:
        key = str(path)
        if key in self._timers:
            self._timers[key].cancel()
            
        timer = threading.Timer(0.5, self._reload_parser, args=[path])
        self._timers[key] = timer
        timer.start()

    def on_deleted(self, event) -> None:
        if event.src_path.endswith('.py') and '__pycache__' not in event.src_path:
            module_name = Path(event.src_path).stem
            self._processor.unregister_parser(module_name)
            log.info("parser_deleted", parser=module_name)

    def _reload_parser(self, path: Path) -> bool:
        try:
            module_name = path.stem
            spec = importlib.util.spec_from_file_location(
                module_name, 
                str(path)
            )
            if spec is None or spec.loader is None:
                log.warning("parser_spec_load_failed", path=str(path))
                return False
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            parser_fn = getattr(module, 'parse', None)
            
            if parser_fn and callable(parser_fn):
                # Validate signature
                sig = inspect.signature(parser_fn)
                if len(sig.parameters) < 5:
                    log.warning("invalid_parser_signature", parser=module_name, signature=str(sig))
                    return False
                    
                self._processor.register_parser(module_name, parser_fn)
                log.info("parser_reloaded", parser=module_name)
                return True
            else:
                log.warning("invalid_parser_structure", parser=module_name, reason="missing_parse_function")
                return False
        except Exception as e:
            log.exception("parser_reload_failed", path=str(path), error=str(e))
            return False

    def start(self) -> None:
        """Start the file watcher."""
        if self._observer is None:
            self._observer = Observer()
            self._observer.schedule(self, str(self._parsers_dir), recursive=False)
            self._observer.start()
            log.info("parser_watcher_started")

    def stop(self) -> None:
        """Stop the file watcher."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            log.info("parser_watcher_stopped")
