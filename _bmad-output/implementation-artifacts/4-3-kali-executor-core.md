# Story 4.3: Kali Executor Core

Status: done

## Story

As an **agent**,
I want **a `kali_execute()` tool that runs code in Kali containers**,
So that **I can execute any of 600+ Kali tools via code generation (FR31, FR32)**.

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD method at all times. All tasks below are strictly marked with [RED], [GREEN], [REFACTOR] phases which must be followed explicitly.

## Acceptance Criteria

1. **Given** container pool is available (Story 4.2)
   **When** I call `kali_execute("nmap -sV 192.168.1.1")`
   **Then** code executes in an isolated Kali container

2. **Given** a command is executed
   **When** execution completes (or times out)
   **Then** result is returned as JSON with `success`, `stdout`, `stderr`, `exit_code`, `duration_ms`

3. **Given** command execution takes too long
   **When** timeout (default 300s) is exceeded
   **Then** execution is cancelled and timeout error is returned

4. **Given** a command is executed
   **When** execution completes successfully or times out
   **Then** container is released back to pool

5. **Given** a command targets an IP or hostname
   **When** `kali_execute()` is called
   **Then** the `ScopeValidator` validates the target BEFORE container execution

6. **Given** a command targets an out-of-scope IP/hostname
   **When** scope validation fails
   **Then** `ScopeViolationError` is raised and NO container execution occurs

7. **Given** integration tests run in cyber range
   **When** real nmap execution occurs
   **Then** actual port scan results are captured

## Tasks / Subtasks

### Phase 1: Core KaliExecutor Class [RED → GREEN → REFACTOR]

- [x] Task 1: Create `KaliExecutor` class skeleton (AC: 1, 2)
  - [x] **[RED]** Write failing test: `KaliExecutor` accepts `ContainerPool` and `ScopeValidator`
  - [x] **[GREEN]** Implement minimal `KaliExecutor.__init__(pool, scope_validator)` signature
  - [x] **[REFACTOR]** Add type hints, docstrings, and optional parameters

- [x] Task 2: Implement `execute()` method (AC: 1, 2, 4)
  - [x] **[RED]** Write failing test: `await executor.execute("echo hello")` returns `ToolResult`
  - [x] **[GREEN]** Implement: acquire container → run command → release container → return result
  - [x] **[REFACTOR]** Clean up error handling (Note: `TaskGroup` not needed for single-command execution)

- [x] Task 3: Implement timeout handling (AC: 3)
  - [x] **[RED]** Write failing test: command exceeding timeout returns `LLMTimeoutError` (or specific timeout result)
  - [x] **[GREEN]** Implement `asyncio.wait_for(container.execute(...), timeout=default_timeout)`
  - [x] **[REFACTOR]** Make timeout configurable per-call and set default (300s)

### Phase 2: Scope Integration [RED → GREEN → REFACTOR]

- [x] Task 4: Integrate `ScopeValidator` pre-execution check (AC: 5)
  - [x] **[RED]** Write failing test: `executor.execute("nmap 192.168.1.1")` calls `scope_validator.validate(command=...)`
  - [x] **[GREEN]** Add `self._scope_validator.validate(command=code)` before container acquire
  - [x] **[REFACTOR]** Scope validation called inline (helper extraction deferred as unnecessary)

- [x] Task 5: Handle scope validation failures (AC: 6)
  - [x] **[RED]** Write failing test: out-of-scope command raises `ScopeViolationError` without container acquisition
  - [x] **[GREEN]** Ensure `ScopeViolationError` propagates without acquiring container
  - [x] **[REFACTOR]** Logging added via structlog for scope validation

### Phase 3: Resource Management [RED → GREEN → REFACTOR]

- [x] Task 6: Ensure container release on exception (AC: 4)
  - [x] **[RED]** Write failing test: container is released even if `execute()` raises exception
  - [x] **[GREEN]** Use `async with self._pool.acquire()` for guaranteed release
  - [x] **[REFACTOR]** ContainerContext pattern used via `async with`

- [x] Task 7: Implement `kali_execute()` Swarms-compatible function (AC: 1, 2)
  - [x] **[RED]** Write failing test: `kali_execute("echo hello")` is a standalone async function
  - [x] **[GREEN]** Implement module-level function that wraps `KaliExecutor.execute()`
  - [x] **[REFACTOR]** Support optional parameters: `timeout`, `executor`

### Phase 4: Module Exports & Integration [RED → GREEN → REFACTOR]

- [x] Task 8: Export from `tools/__init__.py` (AC: all)
  - [x] **[RED]** Write failing test: `from cyberred.tools import KaliExecutor, kali_execute`
  - [x] **[GREEN]** Add exports to `src/cyberred/tools/__init__.py`
  - [x] **[REFACTOR]** Verified all public classes exported (including `initialize_executor`)

- [x] Task 9: Create integration tests with nmap (AC: 7)
  - [x] **[RED]** Write integration test: `kali_execute("nmap -sn 127.0.0.1")` returns scan report
  - [x] **[GREEN]** Implement test in `tests/integration/tools/test_kali_executor_IT.py`
  - [x] **[REFACTOR]** Added `@pytest.mark.integration` marker

### Phase 5: Coverage & Verification

- [x] Task 10: Verify 100% coverage (AC: all)
  - [x] Run `pytest --cov=src/cyberred/tools/kali_executor --cov-fail-under=100 tests/unit/tools/`
  - [x] All 7 unit tests pass with 100% coverage
  - [x] No `# pragma: no cover` exclusions needed

## Dev Notes

> [!TIP]
> **Quick Reference:** Create `KaliExecutor` class with `execute()` method that: (1) validates scope, (2) acquires container, (3) runs command, (4) releases container. Export `KaliExecutor` and `kali_execute()` from `tools/__init__.py`. Achieve 100% coverage.

### Epic AC Coverage

All epic acceptance criteria are covered:
- ✅ AC1: Code executes in isolated container
- ✅ AC2: Result returned with `success`, `stdout`, `stderr`, `exit_code`, `duration_ms`
- ✅ AC3: Configurable timeout (default 300s)
- ✅ AC4: Container released after execution
- ✅ AC5-6: Scope validation before execution
- ✅ AC7: Integration tests with real nmap

### Architecture Requirements

| Component | Location | Notes |
|-----------|----------|-------|
| KaliExecutor | `src/cyberred/tools/kali_executor.py` | Main implementation |
| kali_execute() | `src/cyberred/tools/kali_executor.py` | Swarms-compatible function |
| ScopeValidator | `src/cyberred/tools/scope.py` | Already exists (Story 1.8) |
| ContainerPool | `src/cyberred/tools/container_pool.py` | Already exists (Story 4.2) |

### Implementation Pattern

```python
import asyncio
import structlog
from typing import Optional
from cyberred.core.models import ToolResult
from cyberred.core.exceptions import ScopeViolationError
from cyberred.tools.container_pool import ContainerPool
from cyberred.tools.scope import ScopeValidator

log = structlog.get_logger(__name__)

DEFAULT_TIMEOUT_SECONDS = 300

class KaliExecutor:
    """Swarms-native kali_execute() tool implementation.
    
    Executes commands in isolated Kali containers with:
    - Scope validation (fail-closed, pre-execution)
    - Configurable timeout (default 300s)
    - Guaranteed container release (try/finally pattern)
    """
    
    def __init__(
        self, 
        pool: ContainerPool, 
        scope_validator: ScopeValidator,
        default_timeout: int = DEFAULT_TIMEOUT_SECONDS
    ):
        self._pool = pool
        self._scope_validator = scope_validator
        self._default_timeout = default_timeout
    
    async def execute(
        self, 
        code: str, 
        timeout: Optional[int] = None
    ) -> ToolResult:
        """Execute code in Kali container with scope validation.
        
        Args:
            code: Command to execute (e.g., "nmap -sV 192.168.1.1")
            timeout: Execution timeout in seconds (default: 300)
            
        Returns:
            ToolResult with success, stdout, stderr, exit_code, duration_ms
            
        Raises:
            ScopeViolationError: If command targets out-of-scope resources
        """
        timeout = timeout or self._default_timeout
        
        # Step 1: Scope validation BEFORE container acquisition
        self._scope_validator.validate(command=code)
        log.debug("scope_validated", command=code[:50])
        
        # Step 2: Acquire and execute with guaranteed release
        async with self._pool.acquire() as container:
            try:
                result = await asyncio.wait_for(
                    container.execute(code, timeout=timeout),
                    timeout=timeout
                )
                return result
            except asyncio.TimeoutError:
                log.warning("kali_execute_timeout", command=code[:50], timeout=timeout)
                return ToolResult(
                    success=False,
                    stdout="",
                    stderr=f"Execution timed out after {timeout}s",
                    exit_code=-1,
                    duration_ms=timeout * 1000
                )
```

### Swarms-Compatible Function

```python
# Module-level singleton for pool and validator (initialized at startup)
_executor: Optional[KaliExecutor] = None

async def kali_execute(
    code: str,
    timeout: Optional[int] = None,
    executor: Optional[KaliExecutor] = None
) -> ToolResult:
    """Swarms-native kali_execute() tool.
    
    This is the main entry point for agents to execute Kali tools.
    
    Args:
        code: Bash command or Python code to execute
        timeout: Execution timeout (default: 300s)
        executor: Optional custom executor (for testing)
        
    Returns:
        ToolResult with execution results
        
    Example:
        result = await kali_execute("nmap -sV 192.168.1.1")
        if result.success:
            print(result.stdout)
    """
    if executor is None:
        if _executor is None:
            raise RuntimeError("KaliExecutor not initialized. Call initialize_executor() first.")
        executor = _executor
    
    return await executor.execute(code, timeout=timeout)

def initialize_executor(
    pool: ContainerPool,
    scope_validator: ScopeValidator,
    default_timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> None:
    """Initialize the module-level executor singleton."""
    global _executor
    _executor = KaliExecutor(pool, scope_validator, default_timeout)
```

### Async Patterns (CRITICAL - from Epic 3 learnings)

**✅ DO:**
```python
async def execute(self, code: str, timeout: int = 300) -> ToolResult:
    loop = asyncio.get_running_loop()  # Python 3.11+ correct way
    try:
        return await asyncio.wait_for(container.execute(code), timeout=timeout)
    except asyncio.TimeoutError:
        # Handle timeout gracefully
        ...
```

**🚫 DON'T:**
```python
loop = asyncio.get_event_loop()  # DEPRECATED - causes issues
```

### Scope Validation Integration

`ScopeValidator` from `scope.py` already implements:
- NFKC Unicode normalization
- Command injection detection (`;`, `|`, `&&`, `||`, `$()`, backticks)
- Target extraction from command string
- IP/hostname/port validation against scope config

**Usage:**
```python
from cyberred.tools.scope import ScopeValidator

validator = ScopeValidator.from_file("scope.yaml")
validator.validate(command="nmap -sV 192.168.1.1")  # Raises ScopeViolationError if out of scope
```

### Module Export Pattern (CRITICAL - from Epic 3 learnings)

Every story MUST verify exports before marking complete:
```python
# Test: test_tools_exports.py
def test_kali_executor_exports():
    from cyberred.tools import KaliExecutor, kali_execute
    assert KaliExecutor is not None
    assert kali_execute is not None
```

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| structlog | ≥24.1 | Structured logging |
| pytest-asyncio | ≥0.21 | Async test support |
| asyncio (stdlib) | - | Concurrency |

### ToolResult Dataclass Requirement

The `execute()` method MUST return a `ToolResult` with these exact fields:
```python
from cyberred.core.models import ToolResult

# Required signature:
ToolResult(
    success: bool,      # True if exit_code == 0
    stdout: str,        # Captured stdout
    stderr: str,        # Captured stderr
    exit_code: int,     # Process exit code
    duration_ms: int    # Execution time in milliseconds
)
```

### Testing Standards

- **100% coverage** on `kali_executor.py` (enforced gate)
- **TDD phases** marked in tasks: [RED] → [GREEN] → [REFACTOR]
- **Integration tests require Docker** — use `@pytest.mark.integration`
- **Use existing `ContainerPool` and `ScopeValidator`** from previous stories

### Container Pool Initialization

| Test Type | Pool Mode | Notes |
|-----------|-----------|-------|
| Unit tests | Mock pool or `MagicMock` | No Docker required |
| Integration tests | `mode="real"` | Requires Docker, use `@pytest.mark.integration` |

### Project Structure Notes

Files to create/modify:
```
src/cyberred/
├── tools/
│   ├── __init__.py           # [MODIFY] Add KaliExecutor, kali_execute exports
│   └── kali_executor.py      # [NEW] Main implementation
tests/
├── unit/
│   └── tools/
│       └── test_kali_executor.py    # [NEW] Unit tests
├── integration/
│   └── tools/
│       └── test_kali_executor.py    # [NEW] Integration tests with nmap
```

### References

- **Epic 4 Context:** [epics-stories.md#Story 4.3](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L1734)
- **Architecture:** [architecture.md#tools/](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L814)
- **Previous Story 4.2:** [4-2-kali-container-pool-real-mode.md](file:///root/red/_bmad-output/implementation-artifacts/4-2-kali-container-pool-real-mode.md)
- **Scope Validator:** [scope.py](file:///root/red/src/cyberred/tools/scope.py)
- **Container Pool:** [container_pool.py](file:///root/red/src/cyberred/tools/container_pool.py)
- **Async Patterns:** [async-patterns.md](file:///root/red/docs/best-practices/async-patterns.md)

### Key Learnings from Stories 4.1 & 4.2

1. **Export verification is critical** — Add to code review checklist
2. **Use `asyncio.get_running_loop()`** — NOT deprecated `get_event_loop()`
3. **Verify coverage claims before marking done** — Run `pytest --cov` explicitly
4. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases
5. **ContainerContext pattern** — Enables both `await pool.acquire()` and `async with pool.acquire()`
6. **Use structlog for logging** — NOT `print()` statements
7. **Duration measurement** — Use `time.perf_counter()` for accurate timing

### Error Handling (ERR1)

From PRD Error Handling:
- **ERR1**: Tool execution failure — log error, return structured result, agent continues
- Never raise exceptions for tool failures (return `ToolResult(success=False, ...)`)
- Only raise `ScopeViolationError` for scope violations (safety-critical)

### Container Pool Integration

The `ContainerPool` from Story 4.2 provides:
- `async with pool.acquire() as container:` — context manager pattern
- `container.execute(code, timeout)` → `ToolResult`
- Automatic container release on exit (including exceptions)
- Real mode with actual Kali containers

### Swarms Compatibility Note

This implementation should be compatible with Swarms v8.0.0+ framework:
- Function signature: `async def kali_execute(code: str, ...) -> ToolResult`
- Returns structured `ToolResult` dataclass
- Can be registered as a Swarms tool for agent use

## Dev Agent Record

### Agent Model Used

Claude 3.5 Sonnet (Antigravity)

### Debug Log References

- Code review completed 2026-01-05

### Completion Notes List

- All 7 unit tests pass with 100% coverage on `kali_executor.py`
- Integration test passes with real Docker and nmap
- Scope validation integrated pre-execution
- Container release guaranteed via `async with` pattern

### File List

- `src/cyberred/tools/kali_executor.py` [NEW] - KaliExecutor class, kali_execute() function, initialize_executor()
- `src/cyberred/tools/__init__.py` [MODIFY] - Added KaliExecutor, kali_execute, initialize_executor exports
- `tests/unit/tools/test_kali_executor.py` [NEW] - 7 unit tests for all code paths
- `tests/integration/tools/test_kali_executor_IT.py` [NEW] - Integration test with real nmap
