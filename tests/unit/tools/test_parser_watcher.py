
import pytest
from pathlib import Path
from unittest.mock import Mock
from cyberred.tools.output import OutputProcessor
# We expect this import to fail initially
try:
    from cyberred.tools.parser_watcher import ParserWatcher
except ImportError:
    ParserWatcher = None
from watchdog.events import FileModifiedEvent, FileCreatedEvent
from unittest.mock import Mock, patch

@pytest.fixture
def mock_processor():
    return Mock(spec=OutputProcessor)

@pytest.fixture
def mock_parsers_dir(tmp_path):
    d = tmp_path / "parsers"
    d.mkdir()
    return d

def test_parser_watcher_init(mock_parsers_dir, mock_processor):
    """Test that ParserWatcher initializes correctly."""
    if ParserWatcher is None:
        pytest.fail("ParserWatcher not implemented")
        
    watcher = ParserWatcher(parsers_dir=mock_parsers_dir, processor=mock_processor)
    assert watcher._parsers_dir == mock_parsers_dir
    assert watcher._processor == mock_processor

def test_on_modified_reloads_parser(mock_parsers_dir, mock_processor):
    """Test that on_modified triggers reload for .py files."""
    watcher = ParserWatcher(parsers_dir=mock_parsers_dir, processor=mock_processor)
    # Mock _reload_parser to verify it's called
    watcher._reload_parser = Mock()
    
    with patch("cyberred.tools.parser_watcher.threading.Timer") as MockTimer:
        timer_instance = MockTimer.return_value
        
        event = FileModifiedEvent(str(mock_parsers_dir / "nmap.py"))
        watcher.on_modified(event)
        
        # Execute timer callback
        args = MockTimer.call_args
        # threading.Timer(0.5, func, args=[path]) -> args=(0.5, func), kwargs={'args': [path]}
        func = args[0][1]
        func_args = args[1].get('args', [])
        func(*func_args)
    
    watcher._reload_parser.assert_called_once_with(Path(event.src_path))

def test_on_modified_ignores_non_py_files(mock_parsers_dir, mock_processor):
    """Test that on_modified ignores non-python files."""
    watcher = ParserWatcher(parsers_dir=mock_parsers_dir, processor=mock_processor)
    watcher._reload_parser = Mock()
    
    event = FileModifiedEvent(str(mock_parsers_dir / "nmap.pyc"))
    watcher.on_modified(event)
    
    watcher._reload_parser.assert_not_called()

def test_watcher_start_stop(mock_parsers_dir, mock_processor):
    """Test start and stop lifecycle."""
    with patch("cyberred.tools.parser_watcher.Observer") as MockObserver:
        mock_observer_instance = MockObserver.return_value
        
        watcher = ParserWatcher(parsers_dir=mock_parsers_dir, processor=mock_processor)
        watcher.start()
        
        MockObserver.assert_called_once()
        mock_observer_instance.schedule.assert_called_once_with(watcher, str(mock_parsers_dir), recursive=False)
        mock_observer_instance.start.assert_called_once()
        
        # Test idempotency (start again should do nothing)
        watcher.start()
        MockObserver.assert_called_once() # Still called once

        watcher.stop()
        mock_observer_instance.stop.assert_called_once()
        mock_observer_instance.join.assert_called_once()
        
        # Test idempotency (stop again should do nothing)
        watcher.stop()
        mock_observer_instance.stop.assert_called_once() # Still called once

def test_reload_parser_spec_failure(mock_parsers_dir, mock_processor):
    """Test that reloading fails when spec cannot be loaded."""
    watcher = ParserWatcher(parsers_dir=mock_parsers_dir, processor=mock_processor)
    parser_file = mock_parsers_dir / "bad_spec.py"
    
    with patch("cyberred.tools.parser_watcher.importlib.util.spec_from_file_location", return_value=None):
        success = watcher._reload_parser(parser_file)
    
    assert success is False
    mock_processor.register_parser.assert_not_called()


def test_reload_parser_success(mock_parsers_dir, mock_processor):
    """Test successful parser reload."""
    watcher = ParserWatcher(parsers_dir=mock_parsers_dir, processor=mock_processor)
    
    # Create a dummy parser file
    parser_file = mock_parsers_dir / "test_parser.py"
    parser_content = (
        "from typing import List, Any\n"
        "def parse(stdout: str, stderr: str, exit_code: int, agent_id: str, target: str) -> List[Any]:\n"
        "    return []\n"
    )
    parser_file.write_text(parser_content)
    
    success = watcher._reload_parser(parser_file)
    
    assert success is True
    # Verify register_parser was called with "test_parser"
    mock_processor.register_parser.assert_called_once()
    args = mock_processor.register_parser.call_args
    assert args[0][0] == "test_parser"  # tool name
    assert callable(args[0][1])         # parser function

def test_reload_parser_invalid_file(mock_parsers_dir, mock_processor):
    """Test graceful handling of invalid parser file."""
    watcher = ParserWatcher(parsers_dir=mock_parsers_dir, processor=mock_processor)
    
    # Create invalid python file
    parser_file = mock_parsers_dir / "invalid.py"
    parser_file.write_text("this is not valid python code")
    
    success = watcher._reload_parser(parser_file)
    
    assert success is False
    mock_processor.register_parser.assert_not_called()

def test_on_created_triggers_load(mock_parsers_dir, mock_processor):
    """Test that on_created triggers load for .py files."""
    watcher = ParserWatcher(parsers_dir=mock_parsers_dir, processor=mock_processor)
    watcher._reload_parser = Mock()
    
    with patch("cyberred.tools.parser_watcher.threading.Timer") as MockTimer:
        timer_instance = MockTimer.return_value
        
        event = FileCreatedEvent(str(mock_parsers_dir / "new_parser.py"))
        watcher.on_created(event)
        
        # Execute timer callback
        args = MockTimer.call_args
        func = args[0][1]
        func_args = args[1].get('args', [])
        func(*func_args)
    
    watcher._reload_parser.assert_called_once_with(Path(event.src_path))

def test_reload_parser_invalid_signature(mock_parsers_dir, mock_processor):
    """Test that parser with invalid signature is skipped."""
    watcher = ParserWatcher(parsers_dir=mock_parsers_dir, processor=mock_processor)
    
    parser_file = mock_parsers_dir / "bad_sig.py"
    # parse function with no args
    parser_content = (
        "from typing import List, Any\n"
        "def parse() -> List[Any]:\n"
        "    return []\n"
    )
    parser_file.write_text(parser_content)
    
    success = watcher._reload_parser(parser_file)
    
    assert success is False
    mock_processor.register_parser.assert_not_called()

def test_on_deleted_removes_parser(mock_parsers_dir, mock_processor):
    """Test that on_deleted triggers unregistration."""
    watcher = ParserWatcher(parsers_dir=mock_parsers_dir, processor=mock_processor)
    from watchdog.events import FileDeletedEvent
    
    event = FileDeletedEvent(str(mock_parsers_dir / "nmap.py"))
    watcher.on_deleted(event)
    
    mock_processor.unregister_parser.assert_called_once_with("nmap")

def test_on_deleted_ignores_non_py(mock_parsers_dir, mock_processor):
    """Test that on_deleted ignores non-py files."""
    watcher = ParserWatcher(parsers_dir=mock_parsers_dir, processor=mock_processor)
    from watchdog.events import FileDeletedEvent
    
    event = FileDeletedEvent(str(mock_parsers_dir / "nmap.pyc"))
    watcher.on_deleted(event)
    
    mock_processor.unregister_parser.assert_not_called()

def test_debouncing_reload(mock_parsers_dir, mock_processor):
    """Test that rapid events are debounced."""
    watcher = ParserWatcher(parsers_dir=mock_parsers_dir, processor=mock_processor)
    watcher._reload_parser = Mock()
    
    # Mock Timer to verify behavior
    with patch("cyberred.tools.parser_watcher.threading.Timer") as MockTimer:
        timer_instance = MockTimer.return_value
        
        event = FileModifiedEvent(str(mock_parsers_dir / "nmap.py"))
        
        # First event
        watcher.on_modified(event)
        
        # Verify timer started
        MockTimer.assert_called_once()
        args = MockTimer.call_args
        assert args[0][0] == 0.5 # 500ms default
        timer_instance.start.assert_called_once()
        
        # Second event immediately
        watcher.on_modified(event)
        
        # Verify previous timer cancelled and new one started
        timer_instance.cancel.assert_called_once()
        assert MockTimer.call_count == 2
        
        # Simulate timer execution
        # Get the function passed to second timer
        func = MockTimer.call_args[0][1]
        func()
        
        watcher._reload_parser.assert_called_once()

def test_reload_parser_missing_parse_function(mock_parsers_dir, mock_processor):
    """Test that parser without parse function is handled."""
    watcher = ParserWatcher(parsers_dir=mock_parsers_dir, processor=mock_processor)
    
    parser_file = mock_parsers_dir / "no_parse.py"
    parser_content = (
        "def other_func():\n"
        "    pass\n"
    )
    parser_file.write_text(parser_content)
    
    success = watcher._reload_parser(parser_file)
    
    assert success is False
    mock_processor.register_parser.assert_not_called()

def test_on_created_ignores_non_py(mock_parsers_dir, mock_processor):
    """Test that on_created ignores non-.py files - covers line 31 exit branch."""
    watcher = ParserWatcher(parsers_dir=mock_parsers_dir, processor=mock_processor)
    watcher._reload_parser = Mock()
    
    event = FileCreatedEvent(str(mock_parsers_dir / "nmap.pyc"))
    watcher.on_created(event)
    
    watcher._reload_parser.assert_not_called()

def test_on_created_ignores_pycache(mock_parsers_dir, mock_processor):
    """Test that on_created ignores __pycache__ files."""
    watcher = ParserWatcher(parsers_dir=mock_parsers_dir, processor=mock_processor)
    watcher._reload_parser = Mock()
    
    event = FileCreatedEvent(str(mock_parsers_dir / "__pycache__" / "nmap.py"))
    watcher.on_created(event)
    
    watcher._reload_parser.assert_not_called()
