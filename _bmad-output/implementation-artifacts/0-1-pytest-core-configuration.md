# Story 0.1: pytest Core Configuration

Status: done

## Story

As a **developer**,
I want **pytest and pytest-asyncio configured with proper project structure**,
So that **I can write and run async tests from day one**.

## Acceptance Criteria

1. **Given** a fresh clone of the repository
   **When** I run `pytest`
   **Then** pytest discovers tests in `tests/` directory ✅
   
2. **And** pytest-asyncio handles async test functions automatically ✅

3. **And** pytest.ini or pyproject.toml contains proper configuration ✅

4. **And** conftest.py exists with basic shared fixtures ✅

## Tasks / Subtasks

- [x] Task 1: Create project structure and pyproject.toml (AC: 3)
  - [x] Create `src/cyberred/__init__.py` with version
  - [x] Create `pyproject.toml` with pytest configuration
  - [x] Configure asyncio_mode = "auto" for pytest-asyncio
  - [x] Set test discovery pattern to `test_*.py`
  - [x] Add Python 3.11+ requirement

- [x] Task 2: Create test directory structure (AC: 1, 3)
  - [x] Create `tests/` directory
  - [x] Create `tests/__init__.py`
  - [x] Create `tests/unit/` directory placeholder
  - [x] Verify pytest discovers `tests/` directory

- [x] Task 3: Create conftest.py with basic fixtures (AC: 4)
  - [x] Create `tests/conftest.py`
  - [x] Add event_loop fixture for async tests
  - [x] Add basic pytest configuration hooks
  - [x] Document fixture usage

- [x] Task 4: Add pytest-asyncio configuration (AC: 2)
  - [x] Add pytest-asyncio to dependencies
  - [x] Configure asyncio_mode in pyproject.toml
  - [x] Create sample async test to verify

- [x] Task 5: Validate configuration (AC: 1, 2, 3, 4)
  - [x] Run `pytest --collect-only` to verify discovery (12 tests found)
  - [x] Run sample test to verify async works (7/7 passed)
  - [x] Verify fresh clone behavior

## Dev Notes

### Architecture Patterns & Constraints

From [architecture.md](file:///root/red/docs/3-solutioning/architecture.md):

- **Python Version:** 3.11.7+ (10-25% speed improvement, asyncio enhancements, Swarms compatible)
- **Test Runner:** pytest + pytest-asyncio (async-native, industry standard)
- **Test File Naming:** `test_{module}.py` (unit), `test_{feature}_integration.py`, `test_{scenario}_e2e.py`
- **NO MOCKED TESTS:** All tests run against real Kali tools (later epics)
- **100% test coverage:** Hard gate (NFR19, NFR20)

### Project Structure Notes

Per architecture (lines 573-604), the source tree must be:

```
src/cyberred/
├── __init__.py
├── py.typed                      # PEP 561 type marker
├── core/                         # Framework core
├── agents/                       # Agent implementation  
├── tools/                        # Tool integration
├── tui/                          # Textual TUI
└── cli.py                        # Entry point

tests/
├── unit/
├── integration/
└── e2e/
```

### References

- [Source: docs/3-solutioning/architecture.md#Testing Infrastructure]
- [Source: docs/3-solutioning/epics-stories.md#Story 0.1]

---

## Dev Agent Record

### Agent Model Used

Gemini 2.5 (Antigravity)

### Debug Log References

- First test run had pyproject.toml config conflict (`[tool.pytest.asyncio]` conflicts with `[tool.pytest.ini_options]`)
- Fixed by removing duplicate section

### Completion Notes List

- Created `pyproject.toml` with comprehensive Python 3.11+ project configuration
- Created `src/cyberred/__init__.py` (v2.0.0-alpha) and `py.typed` marker
- Refactored project structure to `src/cyberred/` namespace per architecture (moved core, agents, mcp, ui)
- Updated all imports to use `cyberred.*` namespace
- Verified pytest configuration and test discovery match new structure
- Created test directory structure: unit, integration, safety, emergence, e2e, chaos, load
- Created `tests/conftest.py` with event_loop fixture, pytest markers
- Created `tests/unit/test_pytest_config.py` with 7 validation tests covering pytest config and fixtures

### File List

**Configuration & Root:**
- `pyproject.toml`
- `src/cyberred/__init__.py`
- `src/cyberred/py.typed`
- `src/cyberred/main.py` (moved)

**Refactored Source (moved to src/cyberred/):**
- `src/cyberred/core/`
- `src/cyberred/agents/`
- `src/cyberred/mcp/`
- `src/cyberred/ui/`

**Tests:**
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/unit/__init__.py`
- `tests/unit/test_pytest_config.py`
- `tests/integration/__init__.py`
- `tests/safety/__init__.py`
- `tests/emergence/__init__.py`
- `tests/e2e/__init__.py`
- `tests/chaos/__init__.py`
- `tests/load/__init__.py`

### Review History
- **Review 1 (Ag)**: Identified architecture violation (split namespace).
  - **Fix**: Moved all source code to `src/cyberred/` and updated imports. Verified with tests.

