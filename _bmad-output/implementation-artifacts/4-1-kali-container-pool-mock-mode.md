# Story 4.1: Kali Container Pool (Mock Mode)

Status: done

## Story

As a **developer**,
I want **a container pool that simulates Kali execution without real containers**,
So that **CI tests can run fast without Docker dependencies (NFR24)**.

> [!IMPORTANT]
> **TDD CONSTRAINT:** Ensure to follow TDD method at all times. All tasks below are strictly marked with [RED], [GREEN], [REFACTOR] phases which must be followed explicitly.

## Acceptance Criteria

1. **Given** the container pool is initialized with `mode="mock"`
   **When** I call `pool.acquire()`
   **Then** a mock container instance is returned immediately (no Docker)

2. **Given** a mock container is acquired
   **When** I call `container.execute(code)`
   **Then** predefined responses are returned from fixture files

3. **Given** fixture files exist in `tests/fixtures/tool_outputs/{tool}.txt`
   **When** mock container executes a recognized tool command
   **Then** the corresponding fixture output is returned

4. **Given** a mock container is in use
   **When** I call `pool.release(container)`
   **Then** the mock container is returned to the pool for reuse

5. **Given** Docker is NOT installed on the system
   **When** I run unit tests with `mode="mock"`
   **Then** all tests pass without Docker dependencies

6. **Given** timing tests are needed
   **When** configurable latency simulation is enabled
   **Then** mock container delays responses by the configured amount

## Tasks / Subtasks

### Phase 1: Core Data Structures [RED → GREEN → REFACTOR]

- [x] Task 1: Create `MockContainer` class (AC: 2)
  - [x] **[RED]** Write failing test for `MockContainer.execute()` returning `ToolResult`
  - [x] **[GREEN]** Implement minimal `MockContainer` with `execute(code: str) -> ToolResult` signature
  - [x] **[REFACTOR]** Extract response loading into helper method (`_load_response`)

- [x] Task 2: Create `ContainerProtocol` ABC (AC: 1, 2)
  - [x] **[RED]** Write test verifying `MockContainer` satisfies `ContainerProtocol`
  - [x] **[GREEN]** Implement `ContainerProtocol` ABC in `protocols/container.py`
    - Must define: `execute(code: str, timeout: int) -> ToolResult`
    - Must define: `start() -> None`
    - Must define: `stop() -> None`
    - Must define: `is_healthy() -> bool`
  - [x] **[REFACTOR]** Ensure protocol is in `protocols/` for reuse

### Phase 2: Fixture Loading System [RED → GREEN → REFACTOR]

- [x] Task 3: Implement fixture file loading (AC: 3)
  - [x] **[RED]** Write failing test for loading `tests/fixtures/tool_outputs/nmap.txt`
  - [x] **[GREEN]** Implement `FixtureLoader` class that reads tool output files (internal, not exported)
  - [x] **[REFACTOR]** Add caching for repeated fixture loads

- [x] Task 4: Create sample fixture files (AC: 3)
  - [x] Create `tests/fixtures/tool_outputs/nmap.txt` with realistic nmap output
  - [x] Create `tests/fixtures/tool_outputs/sqlmap.txt` with realistic sqlmap output
  - [x] Create `tests/fixtures/tool_outputs/nuclei.txt` with realistic nuclei output

- [x] Task 5: Tool command detection (AC: 3)
  - [x] **[RED]** Write failing test for detecting tool name from command string
  - [x] **[GREEN]** Implement regex-based tool detection (e.g., "nmap" from "nmap -sV 192.168.1.1")
  - [x] **[REFACTOR]** Handle edge cases: absolute paths, arguments with tool names

### Phase 3: Container Pool Core [RED → GREEN → REFACTOR]

- [x] Task 6: Create `ContainerPool` class with mock mode (AC: 1, 4)
  - [x] **[RED]** Write failing test for `ContainerPool(mode="mock")` initialization
  - [x] **[GREEN]** Implement pool with `acquire()` returning `MockContainer`
  - [x] **[REFACTOR]** Add type hints and docstrings

- [x] Task 7: Implement pool release mechanism (AC: 4)
  - [x] **[RED]** Write failing test for `pool.release(container)` returning container to pool
  - [x] **[GREEN]** Implement release with container reuse
  - [/] **[REFACTOR]** Add validation that released container belongs to pool *(deferred - mock mode creates new containers)*

- [x] Task 8: Implement async acquire with context manager (AC: 1, 4)
  - [x] **[RED]** Write failing test for `async with pool.acquire() as container:`
  - [x] **[GREEN]** Implement `async def acquire()` and `__aenter__`/`__aexit__`
  - [x] **[REFACTOR]** Use `asyncio.get_running_loop()` (NOT `get_event_loop()`)

### Phase 4: Latency Simulation [RED → GREEN → REFACTOR]

- [x] Task 9: Implement configurable latency (AC: 6)
  - [x] **[RED]** Write failing test for `MockContainer(latency_ms=100)` delaying response
  - [x] **[GREEN]** Implement `asyncio.sleep(latency_ms / 1000)` in execute
  - [x] **[REFACTOR]** Make latency configurable per-pool or per-container

### Phase 5: Module Exports & Integration [RED → GREEN → REFACTOR]

- [x] Task 10: Export from `tools/__init__.py` (AC: all)
  - [x] **[RED]** Write failing test for `from cyberred.tools import ContainerPool, MockContainer`
  - [x] **[GREEN]** Add exports to `src/cyberred/tools/__init__.py`
  - [x] **[REFACTOR]** Verify all public classes are exported

- [x] Task 11: Create Mock Component Integration Test (AC: 5)
  - [x] **[RED]** Write integration test that runs full mock pool lifecycle (acquire -> execute -> release)
  - [x] **[GREEN]** Implement test suite in `tests/unit/tools/test_container_pool_lifecycle.py`
  - [x] **[REFACTOR]** Add CI marker `@pytest.mark.unit` (runnable without Docker)

### Phase 6: Coverage & Verification

- [x] Task 12: Verify 100% coverage (AC: all)
  - [x] Run `pytest --cov=src/cyberred/tools/container_pool --cov-fail-under=100`
  - [x] Add any missing tests for uncovered lines
  - [x] Document any `# pragma: no cover` exclusions with justification

## Dev Notes

### Architecture Requirements

| Component | Location | Notes |
|-----------|----------|-------|
| ContainerPool | `src/cyberred/tools/container_pool.py` | Main implementation |
| ContainerProtocol | `src/cyberred/protocols/container.py` | ABC for mock/real containers |
| MockContainer | `src/cyberred/tools/container_pool.py` | Same file as pool |
| FixtureLoader | `src/cyberred/tools/container_pool.py` | Internal helper |
| Test fixtures | `tests/fixtures/tool_outputs/` | Sample tool outputs |

### Async Patterns (CRITICAL - from Epic 3 learnings)

**✅ DO:**
```python
async def acquire(self) -> Container:
    loop = asyncio.get_running_loop()  # Python 3.11+ correct way
    # ...
```

**🚫 DON'T:**
```python
loop = asyncio.get_event_loop()  # DEPRECATED - causes issues
```

Reference: `docs/best-practices/async-patterns.md`

### Module Export Pattern (CRITICAL - from Epic 3 learnings)

Every story MUST verify exports before marking complete:
```python
# Test: test_tools_exports.py
def test_container_pool_exports():
    from cyberred.tools import ContainerPool, MockContainer
    assert ContainerPool is not None
    assert MockContainer is not None
```

### Mock Mode Design

```python
class ContainerPool:
    def __init__(self, mode: Literal["mock", "real"] = "mock", size: int = 20):
        self._mode = mode
        self._size = size
        self._available: asyncio.Queue[Container] = asyncio.Queue()
        
    async def acquire(self) -> Container:
        if self._mode == "mock":
            return MockContainer(fixture_loader=self._fixture_loader)
        # Real mode deferred to Story 4.2
        raise NotImplementedError("Real mode in Story 4.2")
```

### Fixture File Format

`tests/fixtures/tool_outputs/nmap.txt`:
```
Starting Nmap 7.94 ( https://nmap.org ) at 2025-01-05 12:00 UTC
Nmap scan report for 192.168.1.1
Host is up (0.001s latency).
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 8.9
80/tcp open  http    Apache httpd 2.4.52
```

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| pytest-asyncio | ≥0.21 | Async test support |
| None (stdlib only) | - | Mock mode has no external deps |

### Testing Standards

- **100% coverage** on `container_pool.py` (enforced gate)
- **TDD phases** marked in tasks: [RED] → [GREEN] → [REFACTOR]
- **No Docker** required for mock mode tests

### Project Structure Notes

Files to create/modify:
```
src/cyberred/
├── protocols/
│   └── container.py          # [NEW] ContainerProtocol ABC
├── tools/
│   ├── __init__.py           # [MODIFY] Add exports
│   └── container_pool.py     # [NEW] ContainerPool, MockContainer
tests/
├── fixtures/
│   └── tool_outputs/         # [NEW] Directory
│       ├── nmap.txt
│       ├── sqlmap.txt
│       └── nuclei.txt
├── unit/
│   └── tools/
│       └── test_container_pool.py  # [NEW] Unit tests
```

### References

- **Epic 4 Context:** [epics-stories.md#Story 4.1](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L1685)
- **Architecture:** [architecture.md#tools/](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L814)
- **Kali Containers Best Practices:** [kali-containers.md](file:///root/red/docs/best-practices/kali-containers.md)
- **Async Patterns:** [async-patterns.md](file:///root/red/docs/best-practices/async-patterns.md)
- **Epic 3 Retrospective:** [epic-3-retro-2026-01-05.md](file:///root/red/_bmad-output/implementation-artifacts/epic-3-retro-2026-01-05.md) — TDD adoption, export verification, async patterns

### Key Learnings from Epic 3

1. **Export verification is critical** — Add to code review checklist (AI-1)
2. **Use `asyncio.get_running_loop()`** — NOT deprecated `get_event_loop()` (AI-2)
3. **Verify coverage claims before marking done** — Run `pytest --cov` explicitly (AI-3)
4. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases

## Dev Agent Record

### Agent Model Used

Gemini 2.5 Pro (Code Review: 2026-01-05)

### Debug Log References

### Completion Notes List

- Task 5: Implemented tool detection in `MockContainer` using `_detect_tool` logic. Handles tool names with/without paths. Refactored `execute` to use this and load fixtures.
- Task 6&7: Implemented `ContainerPool` with mock mode, `acquire`, and `release`. Added tests for init, acquire, and release.
- Task 8: Implemented hybrid `acquire` allowing both `await pool.acquire()` and `async with pool.acquire()` using `ContainerContext`.
- Task 9: Implemented configurable latency simulation in `MockContainer` and `ContainerPool`.
- Task 10: Exported `ContainerPool`, `MockContainer`, and `ContainerContext` from `src/cyberred/tools/__init__.py`.Verified with `test_tools_exports.py`.
- Task 11: Created `tests/unit/tools/test_container_pool_lifecycle.py` validating full lifecycle (Init -> Acquire -> Execute -> Release).
- Task 12: Verified 100% test coverage for `container_pool.py`. (Added `test_container_pool_coverage.py` for edge cases).

### File List

- src/cyberred/protocols/container.py
- src/cyberred/tools/container_pool.py
- src/cyberred/tools/__init__.py
- tests/fixtures/tool_outputs/nmap.txt
- tests/fixtures/tool_outputs/sqlmap.txt
- tests/fixtures/tool_outputs/nuclei.txt
- tests/unit/tools/test_container_pool.py
- tests/unit/tools/test_tools_exports.py
- tests/unit/tools/test_container_pool_lifecycle.py
- tests/unit/tools/test_container_pool_coverage.py

> **Note:** `FixtureLoader` is intentionally NOT exported — it's an internal helper class.
