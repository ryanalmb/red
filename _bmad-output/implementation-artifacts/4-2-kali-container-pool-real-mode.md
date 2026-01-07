# Story 4.2: Kali Container Pool (Real Mode)

Status: done

## Story

As a **developer**,
I want **a pool of real Kali Linux containers for tool execution**,
So that **integration tests and production run against actual tools (FR35)**.

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD method at all times. All tasks below are strictly marked with [RED], [GREEN], [REFACTOR] phases which must be followed explicitly.

## Acceptance Criteria

1. **Given** Docker is available and `kalilinux/kali-linux-docker` image exists
   **When** I initialize `ContainerPool(mode="real", size=20)`
   **Then** pool pre-warms 20 Kali containers

2. **Given** the pool has available containers
   **When** I call `pool.acquire()`
   **Then** an available container is returned from the pool

3. **Given** all containers in the pool are in use
   **When** I call `pool.acquire()`
   **Then** the call blocks until a container is released (not infinite wait — see timeout in Dev Notes)

4. **Given** I have acquired a container
   **When** I call `pool.release(container)`
   **Then** the container is returned to pool for reuse

5. **Given** containers are created
   **When** I inspect container network configuration
   **Then** each container has network isolation (`network_mode="none"`)

6. **Given** the pool is at 80% queue depth (16/20 containers in use)
   **When** I check `pool.pressure`
   **Then** the property returns a float >= 0.8 indicating backpressure

7. **Given** integration tests run
   **When** a real container executes a tool command
   **Then** the tool output matches real execution (not mock fixtures)

## Tasks / Subtasks

### Phase 1: RealContainer Class [RED → GREEN → REFACTOR]

- [x] Task 1: Create `RealContainer` class skeleton (AC: 5, 7)
  - [x] **[RED]** Write failing test: `RealContainer` uses NET_ADMIN caps and handles image pulling
  - [x] **[GREEN]** Implement `RealContainer` with `cap_add=["NET_ADMIN", "NET_RAW"]` and robust image pull
  - [x] **[REFACTOR]** Extract configuration (image, caps, pull timeout) to class constants

- [x] Task 2: Implement container start/stop lifecycle (AC: 1)
  - [x] **[RED]** Write failing test: `container.start()` starts Docker container, `container.stop()` stops it
  - [x] **[GREEN]** Implement `start()` using `DockerContainer.start()` and `stop()` using `DockerContainer.stop()`
  - [x] **[REFACTOR]** Add proper error handling for Docker unavailable

- [x] Task 3: Implement real command execution (AC: 7)
  - [x] **[RED]** Write failing integration test: `container.execute("echo hello")` returns stdout with "hello"
  - [x] **[GREEN]** Implement `execute()` using `container.exec()` to run commands
  - [x] **[REFACTOR]** Handle timeout, stderr capture, and exit code properly

- [x] Task 4: Implement network isolation (AC: 5)
  - [x] **[RED]** Write failing test: container cannot reach external network (ping fails)
  - [x] **[GREEN]** Configure `DockerContainer` with `network_mode="none"`
  - [x] **[REFACTOR]** Add `is_healthy()` check that verifies container is running

### Phase 2: ContainerPool Real Mode [RED → GREEN → REFACTOR]

- [x] Task 5: Implement real mode pool initialization (AC: 1)
  - [x] **[RED]** Write failing test: `ContainerPool(mode="real", size=5)` creates pool with 5 containers
  - [x] **[GREEN]** Implement real mode branch in `ContainerPool.__init__` to pre-start containers
  - [x] **[REFACTOR]** Make pre-warming async with `asyncio.TaskGroup`

- [x] Task 6: Implement acquire from pre-warmed pool (AC: 2)
  - [x] **[RED]** Write failing test: `await pool.acquire()` returns pre-warmed container from queue
  - [x] **[GREEN]** Implement acquire to get container from `_available` queue
  - [x] **[REFACTOR]** Ensure container health check before returning

- [x] Task 7: Implement blocking acquire with timeout (AC: 3)
  - [x] **[RED]** Write failing test: acquire blocks when pool empty, times out after configurable duration
  - [x] **[GREEN]** Implement `asyncio.wait_for()` with configurable `acquire_timeout_seconds`
  - [x] **[REFACTOR]** Raise `ContainerPoolExhausted` exception on timeout (add to `core/exceptions.py`)

- [x] Task 8: Implement release to pool (AC: 4)
  - [x] **[RED]** Write failing test: `pool.release(container)` returns container to available queue
  - [x] **[GREEN]** Implement release that health-checks container before re-adding to pool
  - [x] **[REFACTOR]** If unhealthy, stop and create replacement container

### Phase 3: Backpressure & Metrics [RED → GREEN → REFACTOR]

- [x] Task 9: Implement `pool.pressure` property (AC: 6)
  - [x] **[RED]** Write failing test: pressure returns 0.0 when all available, 0.8 when 80% in use
  - [x] **[GREEN]** Implement property: `1.0 - (available / size)`
  - [x] **[REFACTOR]** Add `pool.in_use_count` and `pool.available_count` properties

- [x] Task 10: Implement pool shutdown/cleanup (AC: all)
  - [x] **[RED]** Write failing test: `await pool.shutdown()` stops all containers gracefully
  - [x] **[GREEN]** Implement shutdown that stops all containers (both available and in-use)
  - [x] **[REFACTOR]** Add async context manager `async with ContainerPool() as pool:`

### Phase 4: Module Exports & Integration [RED → GREEN → REFACTOR]

- [x] Task 11: Export `RealContainer` from `tools/__init__.py` (AC: all)
  - [x] **[RED]** Write failing test: `from cyberred.tools import RealContainer`
  - [x] **[GREEN]** Add export to `src/cyberred/tools/__init__.py`
  - [x] **[REFACTOR]** Verify all public classes exported

- [x] Task 12: Create real mode integration tests (AC: 7)
  - [x] **[RED]** Write integration test: full lifecycle (pool init → acquire → execute nmap → release → shutdown)
  - [x] **[GREEN]** Implement test in `tests/integration/tools/test_container_pool_real.py`
  - [x] **[REFACTOR]** Add `@pytest.mark.integration` marker

### Phase 5: Coverage & Verification

- [x] Task 13: Verify 100% coverage (AC: all)
  - [x] Run `pytest --cov=src/cyberred/tools/container_pool --cov-fail-under=100 tests/unit/tools/`
  - [x] Add any missing unit tests for uncovered lines
  - [x] Document any `# pragma: no cover` exclusions with justification

## Dev Notes

### Architecture Requirements

| Component | Location | Notes |
|-----------|----------|-------|
| RealContainer | `src/cyberred/tools/container_pool.py` | Same file as MockContainer |
| ContainerPool | `src/cyberred/tools/container_pool.py` | Extend existing class |
| ContainerProtocol | `src/cyberred/protocols/container.py` | Already exists (Story 4.1) |
| ContainerPoolExhausted | `src/cyberred/core/exceptions.py` | New exception |

### Real Container Implementation Pattern

```python
from testcontainers.core.container import DockerContainer

class RealContainer(ContainerProtocol):
    """Real Kali container using testcontainers."""
    
    def __init__(self, image: str = "kalilinux/kali-linux-docker"):
        self._image = image
        self._container: Optional[DockerContainer] = None
    
    async def start(self) -> None:
        # Step 1: Ensure image exists (prevent CI first-run timeouts)
        # Use simple docker client or testcontainers internals to pull if missing
        
        # Step 2: Configure container with required privileges
        self._container = DockerContainer(self._image)
        self._container.with_network("none")  # Network isolation
        self._container.with_kwargs(cap_add=["NET_ADMIN", "NET_RAW"]) # Required for nmap -sS etc.
        
        # Step 3: Start
        await asyncio.to_thread(self._container.start)
    
    async def execute(self, code: str, timeout: int = 30) -> ToolResult:
        if not self._container:
            raise RuntimeError("Container not started")
        
        result = await asyncio.wait_for(
            asyncio.to_thread(self._container.exec, code.split()),
            timeout=timeout
        )
        # Parse result into ToolResult
        ...
```

### Pool Pre-Warming Pattern

```python
async def _prewarm_pool(self) -> None:
    """Pre-warm containers using TaskGroup for concurrent startup."""
    async with asyncio.TaskGroup() as tg:
        for _ in range(self._size):
            tg.create_task(self._create_and_add_container())

async def _create_and_add_container(self) -> None:
    container = RealContainer(image=self._image)
    await container.start()
    await self._available.put(container)
```

### Async Patterns (CRITICAL - from Epic 3 learnings)

**✅ DO:**
```python
async def acquire(self, timeout: float = 30.0) -> ContainerProtocol:
    loop = asyncio.get_running_loop()  # Python 3.11+ correct way
    try:
        return await asyncio.wait_for(self._available.get(), timeout=timeout)
    except asyncio.TimeoutError:
        raise ContainerPoolExhausted(f"No container available within {timeout}s")
```

**🚫 DON'T:**
```python
loop = asyncio.get_event_loop()  # DEPRECATED - causes issues
```

Reference: `docs/best-practices/async-patterns.md`

### Environment-Based Image Selection

From `docs/best-practices/kali-containers.md`:

```python
import os

def get_kali_image() -> str:
    env = os.getenv("CYBER_RED_ENV", "dev")
    if env == "prod":
        return "kalilinux/kali-linux-everything"  # 600+ tools
    return "kalilinux/kali-linux-docker"  # Lightweight
```

### Module Export Pattern (CRITICAL - from Epic 3 learnings)

Every story MUST verify exports before marking complete:
```python
# Test: test_tools_exports.py
def test_real_container_exports():
    from cyberred.tools import ContainerPool, MockContainer, RealContainer
    assert RealContainer is not None
```

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| testcontainers | ≥4.0 | Docker container management |
| pytest-asyncio | ≥0.21 | Async test support |
| Docker | 20.10+ | Container runtime |

### Testing Standards

- **100% coverage** on `container_pool.py` (enforced gate)
- **TDD phases** marked in tasks: [RED] → [GREEN] → [REFACTOR]
- **Integration tests require Docker** — use `@pytest.mark.integration`
- **Use existing `kali_container` fixture** from `tests/conftest.py` for pattern reference

### Project Structure Notes

Files to modify/create:
```
src/cyberred/
├── core/
│   └── exceptions.py           # [MODIFY] Add ContainerPoolExhausted
├── tools/
│   ├── __init__.py             # [MODIFY] Add RealContainer export
│   └── container_pool.py       # [MODIFY] Add RealContainer, real mode
tests/
├── unit/
│   └── tools/
│       └── test_container_pool.py       # [MODIFY] Add real mode unit tests
├── integration/
│   └── tools/
│       └── test_container_pool_real.py  # [NEW] Integration tests
```

### References

- **Epic 4 Context:** [epics-stories.md#Story 4.2](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L1709)
- **Architecture:** [architecture.md#tools/](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L814)
- **Previous Story:**  4-2-kali-container-pool-real-mode: review:///root/red/_bmad-output/implementation-artifacts/4-1-kali-container-pool-mock-mode.md)
- **Kali Containers Best Practices:** [kali-containers.md](file:///root/red/docs/best-practices/kali-containers.md)
- **Async Patterns:** [async-patterns.md](file:///root/red/docs/best-practices/async-patterns.md)
- **Existing Kali Fixture:** [test_kali_container.py](file:///root/red/tests/integration/test_kali_container.py)

### Key Learnings from Story 4.1

1. **Export verification is critical** — Add to code review checklist
2. **Use `asyncio.get_running_loop()`** — NOT deprecated `get_event_loop()`
3. **Verify coverage claims before marking done** — Run `pytest --cov` explicitly
4. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases
5. **ContainerContext pattern** — Enables both `await pool.acquire()` and `async with pool.acquire()`

### Backpressure Implementation Notes

- Backpressure at 80% is **informational** — it does NOT block acquire
- Upstream components (KaliExecutor) can check `pool.pressure` to throttle new requests
- Formula: `pressure = 1.0 - (available_count / size)`

## Dev Agent Record

### Agent Model Used

Gemini 2.0 Flash

### Debug Log References

- Container startup image pull issues resolved by pre-pulling in `start()`.
- Timeout handling refined using `asyncio.wait_for`.
- Coverage gaps in `release` and `shutdown` closed with edge case tests.
- **Code Review (2026-01-05):** Added `available_count`/`in_use_count` properties, implemented `duration_ms` timing, replaced print with logging, fixed `is_healthy()` API.

### Completion Notes List

- Achieved 100% test coverage for `container_pool.py` (42 unit tests).
- Integration tests validated against live Docker environment using `kalilinux/kali-rolling`.
- Implemented robust error handling for container lifecycle.
- Code review issues fixed: properties, duration measurement, logging, API consistency.

### File List

- src/cyberred/tools/container_pool.py
- src/cyberred/core/exceptions.py
- src/cyberred/tools/__init__.py
- tests/unit/tools/test_container_pool.py
- tests/integration/tools/test_container_pool_real.py
