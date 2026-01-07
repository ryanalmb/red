# Story 0.2: Test Directory Structure & Fixtures

Status: done

## Story

As a **developer**,
I want **organized test directories with shared fixtures**,
So that **tests are consistent and reusable across the codebase**.

## Acceptance Criteria

1. **Given** Story 0.1 is complete (Pre-requisite met)
   **When** I examine the test directory structure
   **Then** I find `tests/` subdirectories: `unit`, `integration`, `safety`, `emergence`, `e2e`, `chaos`, `load` (Already done in 0.1)
   
2. **And** `tests/fixtures/` directory exists with subdirectories: `engagements/`, `findings/`, `scope/`

3. **And** `tests/conftest.py` provides shared fixtures for all test types (Enhanced from 0.1 if needed)

4. **And** `pyproject.toml` includes `swarms>=8.0.0` dependency ([kyegomez/swarms](https://github.com/kyegomez/swarms))

5. **And** `tests/fixtures/` contains valid sample data files (e.g., `sample_engagement.json`, `sample_finding.json`)

## Tasks / Subtasks

- [x] Task 1: Add `swarms` dependency (AC: 4)
  - [x] Add `swarms>=8.0.0` to `pyproject.toml` dependencies
  - [x] Run `pip install -e .` (or equivalent) to update environment
  - [x] Verify import `import swarms` works

- [x] Task 2: Create fixtures directory structure (AC: 2)
  - [x] Create `tests/fixtures/`
  - [x] Create `tests/fixtures/engagements/`
  - [x] Create `tests/fixtures/findings/`
  - [x] Create `tests/fixtures/scope/`

- [x] Task 3: Create sample fixture data (AC: 5)
  - [x] Create `tests/fixtures/engagements/sample_engagement.json` (Target IP: 127.0.0.1, Port: 80)
  - [x] Create `tests/fixtures/findings/sample_sqli.json` (Severity: High, CWE-89)
  - [x] Create `tests/fixtures/scope/allowlist.yaml` (Sample scope config)

- [x] Task 4: Enhance conftest.py (AC: 3)
  - [x] Add fixture to load sample data from `tests/fixtures/`
  - [x] Ensure `event_loop` fixture is robust for swarms async usage (if specific requirements exist)

- [x] Task 5: Use fixtures in a test (Verification)
  - [x] Create/Update a test to load and verify `sample_engagement.json` via fixture

## Dev Notes

### Architecture Patterns & Constraints

- **Dependency:** `kyegomez/swarms` framework integration.
- **Fixtures:** Store static data in `tests/fixtures/` (JSON/YAML), use `conftest.py` to load them as objects. Do not hardcode large data definition in python files.
- **Project Structure:** `src/cyberred/` is the package root.

### Dependencies

- `swarms>=8.0.0` (Critical for agent framework later)

### References

- [Source: docs/3-solutioning/epics-stories.md#Story 0.2]
- [Source: docs/3-solutioning/architecture.md]

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- Added `swarms>=8.0.0` dependency to `pyproject.toml` (installed v8.7.0)
- Verified `swarms` package availability with `tests/unit/test_deps.py`
- Created fixtures directory structure: `tests/fixtures/{engagements,findings,scope}`
- Created sample fixture data: `sample_engagement.json`, `sample_sqli.json`, `allowlist.yaml`
- Enhanced `tests/conftest.py` with `load_fixture_data` factory and file-based fixtures
- Verified fixtures loading with `tests/unit/test_fixtures.py` (5 tests passed)

### File List

**Configuration & Tests:**
- `pyproject.toml` (Added dependency)
- `tests/conftest.py` (Added fixture loaders)
- `tests/unit/test_deps.py` (New dependency check)
- `tests/unit/test_fixtures.py` (New fixture verification)

**Fixtures Data:**
- `tests/fixtures/__init__.py`
- `tests/fixtures/engagements/__init__.py`
- `tests/fixtures/engagements/sample_engagement.json`
- `tests/fixtures/findings/__init__.py`
- `tests/fixtures/findings/sample_sqli.json`
- `tests/fixtures/scope/__init__.py`
- `tests/fixtures/scope/allowlist.yaml`

### Review History
- **Review 1**: Fixed placeholder test `test_unsupported_format`. Added `__init__.py` to all fixture directories.
