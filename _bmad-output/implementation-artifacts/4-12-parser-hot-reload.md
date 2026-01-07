# Story 4.12: Parser Hot Reload

**Status**: done

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD methodology at all times. All tasks marked [RED], [GREEN], [REFACTOR] must be followed explicitly. Each task must have a failing test before implementation.

> [!NOTE]
> **EXISTING INFRASTRUCTURE:** The `OutputProcessor` class in `output.py` has a `_parsers: Dict[str, ParserFn]` registry used for Tier 1 parsers. This story adds file watching and dynamic reload capabilities without modifying the core parsing logic.

## Story

As an **operator**,
I want **to add or update parsers without restarting the system**,
So that **I can improve parsing mid-engagement (FR34, NFR25)**.

## Acceptance Criteria

1. **Given** Stories 4.5-4.10 are complete (parser registry exists)
   **When** I modify an existing parser file in `tools/parsers/`
   **Then** the system detects the change via file watcher

2. **Given** a parser file modification is detected
   **When** the file watcher triggers
   **Then** the parser is reloaded without stopping the engagement

3. **Given** a parser reload completes
   **When** subsequent tool executions run
   **Then** the new parser version is used for processing

4. **Given** a new parser file is added to `tools/parsers/`
   **When** the watcher detects the new file
   **Then** it is automatically registered in the parser registry

5. **Given** parser reload/registration events
   **When** any parser lifecycle event occurs
   **Then** logs indicate "Parser {name} reloaded" or "Parser {name} registered"

6. **Given** a parser file is deleted
   **When** the watcher detects file removal
   **Then** the parser is unregistered from the registry
   **And** logs indicate "Parser {name} unregistered"

7. **Given** rapid file system events (e.g., save which triggers modify+close)
   **When** multiple events occur for the same file within 500ms
   **Then** only a single reload operation is triggered (debounce)

8. **Given** the hot reload system
   **When** integration tests run
   **Then** tests verify hot reload without engagement interruption

## Tasks / Subtasks

### Phase 0: Analysis & Setup [BLUE]

- [x] Task 0.1: Review existing parser infrastructure
  - [x] Examine `OutputProcessor.register_parser()` in [output.py](file:///root/red/src/cyberred/tools/output.py#L94-L97)
  - [x] Examine `parsers/__init__.py` for current registration pattern
  - [x] Document current parser loading mechanism

- [x] Task 0.2: Setup development environment
  - [x] Install watchdog: `pip install watchdog` (add to pyproject.toml)
  - [x] Verify watchdog works on Linux (inotify backend)

---

### Phase 1: File Watcher Infrastructure [RED → GREEN → REFACTOR]

#### 1A: ParserWatcher Class (AC: 1, 5)

- [x] Task 1.1: Create file watcher module
  - [x] **[RED]** Create `tests/unit/tools/test_parser_watcher.py`
  - [x] **[RED]** Write failing test: `ParserWatcher` initializes with parsers directory path
  - [x] **[GREEN]** Create `src/cyberred/tools/parser_watcher.py`
  - [x] **[GREEN]** Implement `ParserWatcher.__init__(self, parsers_dir: Path, processor: OutputProcessor)`
  - [x] **[REFACTOR]** Add docstring and type hints

- [x] Task 1.2: Implement file event handler
  - [x] **[RED]** Write failing test: `_on_modified` callback receives file path on change
  - [x] **[GREEN]** Implement `watchdog.events.FileSystemEventHandler` subclass
  - [x] **[GREEN]** Filter for `.py` files only (ignore `__pycache__`, `.pyc`)
  - [x] **[REFACTOR]** Add structured logging: `event="parser_file_modified"`, `path={path}`

- [x] Task 1.3: Implement watcher start/stop
  - [x] **[RED]** Write failing test: `start()` begins watching, `stop()` halts watching
  - [x] **[GREEN]** Implement `start()` using `watchdog.observers.Observer`
  - [x] **[GREEN]** Implement `stop()` for clean shutdown
  - [x] **[REFACTOR]** Ensure thread-safe start/stop

---

### Phase 2: Parser Reload Logic [RED → GREEN → REFACTOR]

#### 2A: Module Reload (AC: 2, 3)

- [x] Task 2.1: Implement parser module reload
  - [x] **[RED]** Write failing test: modified parser module is reloaded via `importlib.reload()`
  - [x] **[GREEN]** Implement `_reload_parser(self, module_path: Path) -> bool`
  - [x] **[GREEN]** Use `importlib.util.spec_from_file_location` to load module spec
  - [x] **[GREEN]** Use `importlib.reload()` for existing modules
  - [x] **[GREEN]** Re-register parser with `OutputProcessor.register_parser()`
  - [x] **[REFACTOR]** Add error handling for syntax errors in modified parser

- [x] Task 2.2: Verify reloaded parser is used
  - [x] **[RED]** Write failing test: after reload, new parser function is called
  - [x] **[GREEN]** Ensure `_parsers` dict is updated with new function reference
  - [x] **[REFACTOR]** Add structured logging: `event="parser_reloaded"`, `parser={name}`, `version={hash[:8]}`

---

### Phase 3: New Parser Registration [RED → GREEN → REFACTOR]

#### 3A: Dynamic Parser Discovery (AC: 4, 5)

- [x] Task 3.1: Implement new parser detection
  - [x] **[RED]** Write failing test: new file in parsers/ triggers registration
  - [x] **[GREEN]** Handle `on_created` event in FileSystemEventHandler
  - [x] **[GREEN]** Auto-discover parser function using naming convention (`parse_{tool}` or `parse`)
  - [x] **[GREEN]** Register new parser with `OutputProcessor`
  - [x] **[REFACTOR]** Add structured logging: `event="parser_registered"`, `parser={name}`

- [x] Task 3.2: Parser naming convention validation
  - [x] **[RED]** Write failing test: file without valid parser function is skipped
  - [x] **[GREEN]** Validate module exports `parse` function matching `ParserFn` signature
  - [x] **[REFACTOR]** Log warning for invalid parser files: `event="parser_invalid"`, `path={path}`

- [x] Task 3.3: Parser deletion handling
  - [x] **[RED]** Write failing test: deleting parser file removes it from registry
  - [x] **[GREEN]** Handle `on_deleted` event
  - [x] **[GREEN]** Remove parser from `OutputProcessor` registry
  - [x] **[REFACTOR]** Add structured logging: `event="parser_unregistered"`, `parser={name}`

---

### Phase 4: OutputProcessor Integration [RED → GREEN → REFACTOR]

#### 4A: Watcher Integration (AC: 2, 3, 7)

- [x] Task 4.1: Add watcher to OutputProcessor
  - [x] **[RED]** Write failing test: `OutputProcessor.start_watcher()` starts watching
  - [x] **[GREEN]** Add `start_watcher(self) -> None` method to OutputProcessor
  - [x] **[GREEN]** Add `stop_watcher(self) -> None` method for clean shutdown
  - [x] **[REFACTOR]** Make watcher optional (only when explicitly started)

- [x] Task 4.2: Thread-safe parser updates
  - [x] **[RED]** Write failing test: concurrent parser updates don't corrupt registry
  - [x] **[GREEN]** Add `threading.RLock` around parser registration/lookup
  - [x] **[REFACTOR]** Minimize lock scope for performance

- [x] Task 4.3: Implement event debouncing
  - [x] **[RED]** Write failing test: multiple events in short window trigger single reload
  - [x] **[GREEN]** Add debounce logic (e.g., threading.Timer or timestamp check) to EventHandler
  - [x] **[REFACTOR]** Make debounce interval configurable (default 500ms)

---

### Phase 5: Integration Tests [RED → GREEN → REFACTOR]

#### 5A: Hot Reload Verification (AC: 6)

- [x] Task 5.1: Create integration test file
  - [x] **[RED]** Create `tests/integration/tools/test_parser_hot_reload.py`
  - [x] **[RED]** Add `@pytest.mark.integration` marker

- [x] Task 5.2: Test parser modification reload
  - [x] **[RED]** Write test: modify existing parser, verify new behavior after reload
  - [x] **[GREEN]** Create temp parser file, modify it, verify output changes
  - [x] **[REFACTOR]** Clean up temp files after test

- [x] Task 5.3: Test new parser registration
  - [x] **[RED]** Write test: add new parser file, verify auto-registration
  - [x] **[GREEN]** Create new parser file dynamically, verify it's registered
  - [x] **[REFACTOR]** Verify logging output for registration event

- [x] Task 5.4: Test engagement non-interruption
  - [x] **[RED]** Write test: simulate ongoing processing during reload
  - [x] **[GREEN]** Use threading to process output while reload happens
  - [x] **[GREEN]** Verify no exceptions or data corruption
  - [x] **[REFACTOR]** Add assertions for thread safety

---

### Phase 6: Coverage & Documentation [BLUE]

- [x] Task 6.1: Verify 100% coverage
  - [x] Run: `pytest tests/unit/tools/test_parser_watcher.py --cov=src/cyberred/tools/parser_watcher --cov-report=term-missing --cov-fail-under=100`
  - [x] Document any uncovered edge cases

- [x] Task 6.2: Update Dev Agent Record
  - [x] Complete Agent Model Used
  - [x] Add Debug Log References
  - [x] Complete Completion Notes List
  - [x] Fill in File List

- [x] Task 6.3: Final verification
  - [x] Verify all ACs met
  - [x] Run full test suite: `pytest tests/ -v --tb=short`
  - [x] Update story status to `done`

## Dev Notes

### Technical Implementation

**File Watcher Pattern:**
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

class ParserEventHandler(FileSystemEventHandler):
    def __init__(self, processor: OutputProcessor):
        self._processor = processor
    
    def on_modified(self, event: FileModifiedEvent) -> None:
        if event.src_path.endswith('.py') and '__pycache__' not in event.src_path:
            self._reload_parser(Path(event.src_path))
    
    def on_created(self, event: FileCreatedEvent) -> None:
        if event.src_path.endswith('.py') and '__pycache__' not in event.src_path:
            self._register_new_parser(Path(event.src_path))
```

**Module Reload Pattern:**
```python
import importlib.util
import importlib

def _reload_parser(self, path: Path) -> bool:
    module_name = path.stem  # e.g., "nmap" from "nmap.py"
    spec = importlib.util.spec_from_file_location(
        f"cyberred.tools.parsers.{module_name}", 
        path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Get parser function from module
    parser_fn = getattr(module, 'parse', None)
    if parser_fn and callable(parser_fn):
        self._processor.register_parser(module_name, parser_fn)
        return True
    return False
```

### Existing Parser Registry Interface

From [output.py](file:///root/red/src/cyberred/tools/output.py#L94-L101):

```python
def register_parser(self, tool_name: str, parser: ParserFn) -> None:
    """Register a Tier 1 parser for a tool."""
    self._parsers[tool_name.lower()] = parser
    log.info("parser_registered", tool=tool_name)

def unregister_parser(self, tool_name: str) -> None:
    """Unregister a parser (e.g., on file deletion)."""
    if tool_name.lower() in self._parsers:
        del self._parsers[tool_name.lower()]
        log.info("parser_unregistered", tool=tool_name)
    
def get_registered_parsers(self) -> List[str]:
    """Return list of tools with registered parsers."""
    return list(self._parsers.keys())
```

### Thread Safety Considerations

The `OutputProcessor._parsers` dict is accessed during both:
1. **Reading:** `process()` method checks for parser existence
2. **Writing:** `register_parser()` adds/updates parsers

A `threading.RLock` must be used to protect `self._parsers`. The lock should be acquired during `register_parser()`, `unregister_parser()`, and briefly during `process()` when retrieving the parser function.

### Dependencies

Add to `pyproject.toml`:
```toml
[project.dependencies]
watchdog = "^3.0.0"  # File watching with inotify backend
```

### Logging Pattern

Use structlog consistent with existing codebase:
```python
import structlog
log = structlog.get_logger()

# On file change detection
log.info("parser_file_modified", path=str(path))

# On successful reload
log.info("parser_reloaded", parser=module_name)

# On new parser registration
log.info("parser_registered", parser=module_name)

# On parser unregistration
log.info("parser_unregistered", parser=module_name)

# On error
log.warning("parser_reload_failed", parser=module_name, error=str(e))
```

### Project Structure Notes

**New files:**
```
src/cyberred/tools/
├── parser_watcher.py       # [NEW] File watcher + reload logic
└── parsers/                # [UNCHANGED] Parser modules

tests/
├── unit/tools/
│   └── test_parser_watcher.py    # [NEW] Unit tests
└── integration/tools/
    └── test_parser_hot_reload.py # [NEW] Integration tests
```

### Key Learnings from Previous Stories (4.5-4.11)

1. **Use structlog for logging** — NOT `print()` statements
2. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases explicitly
3. **Verify coverage claims** — Run `pytest --cov` before marking done
4. **Use pytest markers** — Always include `@pytest.mark.unit` and `@pytest.mark.integration`
5. **Thread safety matters** — Daemon runs continuously, parsers must handle concurrent access
6. **Clean test isolation** — Use temp directories for file system tests

### References

- **Epic Story:** [epics-stories.md#Story 4.12](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2003)
- **PRD FR34:** Parser hot reload requirement
- **NFR25:** Zero-downtime parser updates
- **Architecture - Logging:** [architecture.md#L524-L537](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L524)
- **Previous Story 4.11:** [4-11-llm-summarization-tier-2.md](file:///root/red/_bmad-output/implementation-artifacts/4-11-llm-summarization-tier-2.md)
- **OutputProcessor:** [tools/output.py](file:///root/red/src/cyberred/tools/output.py)
- **Parser Base:** [tools/parsers/base.py](file:///root/red/src/cyberred/tools/parsers/base.py)
- **Parser Init:** [tools/parsers/__init__.py](file:///root/red/src/cyberred/tools/parsers/__init__.py)

## Dev Agent Record

### Agent Model Used

Antigravity (Google DeepMind)

### Debug Log References

- `coverage.xml`: Achieved 100% coverage for `parser_watcher.py` and `output.py` (new changes)
- `tests/integration/tools/test_parser_hot_reload.py`: Verification of full Hot Reload cycle

### Completion Notes List

- Implemented standard watchdog pattern with debouncing (500ms)
- Added thread-safe locking to OutputProcessor registry
- Verified full CRUD lifecycle for parsers via integration tests
- Achieved 100% test coverage for new components

---

### Senior Developer Review (AI)

**Review Date:** 2026-01-06  
**Reviewer:** Antigravity (Code Review Workflow)

**Issues Fixed:**
1. ✅ Consolidated duplicate `typing` imports in `parser_watcher.py`
2. ✅ Fixed inconsistent logging in `unregister_parser()` - now only logs when parser is actually removed
3. ✅ Added tests for `on_created` non-.py and `__pycache__` paths to achieve 100% branch coverage
4. ✅ Removed duplicate test calls in unit tests
5. ✅ Filled in Agent Model placeholder
6. ✅ Added `test_lifecycle_logging` integration test for AC5 (logging verification)
7. ✅ Added `test_debounce_rapid_changes` integration test for AC7 (debounce behavior)

**Coverage Verified:**
- `parser_watcher.py`: 100% (71 stmts, 18 branches)
- `output.py` (hot reload changes): 100% (121 stmts, 26 branches)
- All 42 unit tests passing (15 for parser_watcher, 27 for output)
- All 3 integration tests passing

### File List

| Action | File Path |
|--------|-----------|
| [MODIFY] | `pyproject.toml` (Add watchdog dependency) |
| [NEW] | `src/cyberred/tools/parser_watcher.py` |
| [MODIFY] | `src/cyberred/tools/output.py` (Add watcher integration, unregistration, locking) |
| [NEW] | `tests/unit/tools/test_parser_watcher.py` |
| [MODIFY] | `tests/unit/tools/test_output.py` (Add integration edge cases) |
| [NEW] | `tests/integration/tools/test_parser_hot_reload.py` |
