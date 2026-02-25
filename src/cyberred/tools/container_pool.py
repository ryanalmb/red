import os
import asyncio
import logging
import shlex
import signal
import time
from pathlib import Path
from typing import Optional, Literal
from cyberred.core.models import ToolResult
from cyberred.core.exceptions import ContainerPoolExhausted
from cyberred.protocols.container import ContainerProtocol

logger = logging.getLogger(__name__)
_TIMEOUT_EXIT_CODES = {124, 137}
_SCANNER_TIMEOUT_GUARD_TOOLS = (
    "nmap",
    "masscan",
    "rustscan",
    "naabu",
    "zmap",
    "zgrab",
    "zgrab2",
)

class ContainerContext:
    def __init__(self, pool: 'ContainerPool', timeout: Optional[float] = None):
        self._pool = pool
        self._timeout = timeout
        self._container: Optional[ContainerProtocol] = None

    def __await__(self):
        return self._acquire().__await__()

    async def __aenter__(self) -> ContainerProtocol:
        self._container = await self._acquire()
        return self._container

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._container:
            await self._pool.release(self._container)
            
    async def _acquire(self) -> ContainerProtocol:
        return await self._pool._acquire_impl(timeout=self._timeout)

class ContainerPool:
    def __init__(self, mode: Literal["mock", "real"] = "mock", size: int = 20, latency_ms: int = 0):
        self._mode = mode
        self._size = size
        self._latency_ms = latency_ms
        self._available: asyncio.Queue[ContainerProtocol] = asyncio.Queue()
        self._all_containers: list[ContainerProtocol] = []
        self._fixture_loader = FixtureLoader()
        
    async def initialize(self) -> None:
        """Initialize the pool, pre-warming containers if in real mode."""
        if self._mode == "real":
            self._all_containers = [] 
            async def _create_and_start_container():
                container = RealContainer()
                await container.start()
                await self._available.put(container)
                self._all_containers.append(container)

            async with asyncio.TaskGroup() as tg:
                for _ in range(self._size):
                    tg.create_task(_create_and_start_container())
        
                     
    async def shutdown(self) -> None:
        """Shutdown all containers in the pool."""
        if self._mode == "real":
             # Stop all tracked containers
             async with asyncio.TaskGroup() as tg:
                 for container in self._all_containers:
                     tg.create_task(container.stop())
             self._all_containers.clear()
             # Also clear queue?
             while not self._available.empty():
                 try:
                     self._available.get_nowait()
                 except asyncio.QueueEmpty:
                     break
                     
    async def __aenter__(self) -> "ContainerPool":
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

    def acquire(self, timeout: Optional[float] = None) -> ContainerContext:
        return ContainerContext(self, timeout=timeout)
        
    async def _acquire_impl(self, timeout: Optional[float] = None) -> ContainerProtocol:
        if self._mode == "mock":
            return MockContainer(fixture_loader=self._fixture_loader, latency_ms=self._latency_ms)
        
        # Real mode: get from queue
        try:
            container = await asyncio.wait_for(self._available.get(), timeout=timeout)
        except asyncio.TimeoutError:
             raise ContainerPoolExhausted(f"Timeout waiting for container (timeout={timeout}s)")
             
        # Ensure health
        if not container.is_healthy():
            try:
                # Try to restart once
                await container.stop()
                await container.start()
            except Exception:
                # If restart fails, we still return it - execution might fail
                pass
                
        return container
        
    @property
    def pressure(self) -> float:
        """Calculate pool pressure (0.0 to 1.0).
        
        Returns:
            float: Ratio of used/unavailable containers to total size.
                   1.0 means pool is empty (full pressure).
                   0.0 means pool is full (no pressure).
        """
        if self._size == 0:
            return 1.0
            
        available = self.available_count
        used = self._size - available
        return used / self._size

    @property
    def available_count(self) -> int:
        """Return count of available containers."""
        return self._available.qsize()

    @property
    def in_use_count(self) -> int:
        """Return count of containers currently in use."""
        return self._size - self.available_count

    async def release(self, container: ContainerProtocol) -> None:
        if self._mode == "mock":
             if self._available.qsize() < self._size:
                 await self._available.put(container)
        # For real containers, we always put them back if they are healthy.
        # If not healthy, we discard them and spawn replacement per AC3.
        elif self._mode == "real":
            if container.is_healthy():
                await self._available.put(container)
            else:
                # Log that a container was unhealthy and discarded
                logger.warning("container_unhealthy_discarded: spawning replacement")
                try:
                    await container.stop()
                except Exception:
                    pass  # Best effort stop
                
                # AC3: Spawn replacement asynchronously to maintain pool size
                asyncio.create_task(self._spawn_replacement())
    
    async def _spawn_replacement(self) -> None:
        """Spawn a replacement container to maintain pool size.
        
        Called when an unhealthy container is discarded from the pool.
        Runs asynchronously in the background.
        """
        try:
            container = RealContainer()
            await container.start()
            await self._available.put(container)
            self._all_containers.append(container)
            logger.info("container_replaced: pool size maintained")
        except Exception as e:
            logger.warning("container_replacement_failed: error=%s", str(e))
            # Don't raise - replacement failure shouldn't crash the system

class FixtureLoader:
    def __init__(self, fixtures_dir: str = "tests/fixtures/tool_outputs"):
        self.fixtures_dir = Path(fixtures_dir)
        self._cache: dict[str, str] = {}

    def load(self, filename: str) -> str:
        if filename in self._cache:
            return self._cache[filename]
            
        file_path = self.fixtures_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Fixture file not found: {file_path}")
            
        content = file_path.read_text(encoding="utf-8")
        self._cache[filename] = content
        return content


from testcontainers.core.container import DockerContainer

class RealContainer(ContainerProtocol):
    """Real Kali container using testcontainers."""
    
    DEFAULT_IMAGE = "kalilinux/kali-rolling"
    NETWORK_MODE = "none"
    CAPABILITIES = ["NET_ADMIN", "NET_RAW"]

    def __init__(self, image: str = DEFAULT_IMAGE):
        self._image = image
        self._container: Optional[DockerContainer] = None

    async def start(self) -> None:
        # Step 1: Ensure image exists (prevent CI first-run timeouts)
        # Use simple docker client or testcontainers internals to pull if missing
        import docker
        from docker.errors import ImageNotFound, APIError
        
        try:
            client = docker.from_env()
            try:
                # Check if image exists locally
                client.images.get(self._image)
            except ImageNotFound:
                # Pull if missing
                logger.info("Pulling image %s...", self._image)
                client.images.pull(self._image)
        except Exception as e:
            # Fallback: testcontainers may pull on its own
            logger.debug("Pre-pull check failed: %s", e)
            pass
        
        # Step 2: Configure container with required privileges
        self._container = DockerContainer(self._image)
        # self._container.with_network(self.NETWORK_MODE) # Incorrect usage causing AttributeError
        
        # Configure network mode and caps via kwargs
        self._container.with_kwargs(
            network_mode=self.NETWORK_MODE,
            cap_add=self.CAPABILITIES,
            tty=True # Keep running
        )
        
        # Step 3: Start
        await asyncio.to_thread(self._container.start)

    async def stop(self) -> None:
        if self._container:
            try:
                await asyncio.to_thread(self._container.stop)
            except Exception:
                # Log error here if we had a logger, but for now just suppress to ensure safety
                pass
            finally:
                self._container = None

    async def execute(self, code: str, timeout: int = 30) -> ToolResult:
        if not self._container:
            raise RuntimeError("Container not started")
        
        # Split command respecting quotes (shlex handles "arg with spaces")
        try:
            cmd = shlex.split(code)
        except ValueError:
            cmd = code.split()  # Fallback for malformed quotes
        
        def _exec():
            # Use low-level api to get demuxed output (stdout, stderr)
            # testcontainers wrapper .exec() does not support demux
            wrapped = self._container.get_wrapped_container()
            return wrapped.exec_run(cmd, demux=True)

        start_time = time.perf_counter()
        try:
            # exec_run returns ExecResult(exit_code, (stdout, stderr)) in newer docker SDK
            result = await asyncio.wait_for(
                asyncio.to_thread(_exec),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            # Per ERR1: Return structured result, don't raise
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning("container_execute_timeout: command=%s timeout=%s", code[:50], timeout)
            return ToolResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {timeout}s",
                exit_code=-1,
                duration_ms=duration_ms,
                error_type="TIMEOUT"
            )
        except Exception as e:
            # Per ERR1: Wrap all exceptions in ToolResult
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            error_type = "EXECUTION_EXCEPTION"
            
            # Detect container crash (NotFound from docker SDK)
            if "NotFound" in type(e).__name__ or "not found" in str(e).lower():
                error_type = "CONTAINER_CRASHED"
                logger.warning("container_crashed: command=%s error=%s", code[:50], str(e))
            else:
                logger.warning("container_exec_exception: command=%s error=%s", code[:50], str(e))
            
            return ToolResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_ms=duration_ms,
                error_type=error_type
            )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
            
        exit_code = result[0]
        output = result[1]  # (stdout, stderr)
        
        stdout_bytes = output[0] if output else b""
        stderr_bytes = output[1] if output else b""
        
        stdout_str = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr_str = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        # Set error_type for non-zero exit codes
        error_type = None
        if exit_code != 0:
            error_type = "NON_ZERO_EXIT"

        return ToolResult(
            success=exit_code == 0,
            stdout=stdout_str,
            stderr=stderr_str,
            exit_code=exit_code,
            duration_ms=duration_ms,
            error_type=error_type
        )

    async def execute_pipeline(self, segments: list[str], timeout: int = 30) -> ToolResult:
        """Execute a pipeline of commands, reconstructed safely via shlex.

        Each segment has already been validated by the scope validator.
        Segments are re-quoted via shlex.join() and joined with | for
        shell execution, preventing injection in the reconstructed command.

        Args:
            segments: List of command strings (pre-validated by scope).
            timeout: Execution timeout in seconds.

        Returns:
            ToolResult from the pipeline execution.
        """
        if not self._container:
            raise RuntimeError("Container not started")

        # Reconstruct pipeline: re-quote each segment to prevent injection
        safe_parts = []
        for seg in segments:
            try:
                tokens = shlex.split(seg)
                safe_parts.append(shlex.join(tokens))
            except ValueError:
                safe_parts.append(seg)

        shell_cmd = " | ".join(safe_parts)
        cmd = ["sh", "-c", shell_cmd]

        def _exec():
            wrapped = self._container.get_wrapped_container()
            return wrapped.exec_run(cmd, demux=True)

        start_time = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_exec),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning("pipeline_execute_timeout: cmd=%s timeout=%s", shell_cmd[:80], timeout)
            return ToolResult(
                success=False, stdout="", stderr=f"Pipeline timed out after {timeout}s",
                exit_code=-1, duration_ms=duration_ms, error_type="TIMEOUT",
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning("pipeline_exec_exception: cmd=%s error=%s", shell_cmd[:80], str(e))
            return ToolResult(
                success=False, stdout="", stderr=str(e),
                exit_code=-1, duration_ms=duration_ms, error_type="EXECUTION_EXCEPTION",
            )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        exit_code = result[0]
        output = result[1]
        stdout_bytes = output[0] if output else b""
        stderr_bytes = output[1] if output else b""
        stdout_str = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr_str = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        return ToolResult(
            success=exit_code == 0,
            stdout=stdout_str, stderr=stderr_str,
            exit_code=exit_code, duration_ms=duration_ms,
            error_type="NON_ZERO_EXIT" if exit_code != 0 else None,
        )

    def is_healthy(self) -> bool:
        """Check if container is healthy (running).

        Note: Uses sync Docker API call. For async context, consider
        wrapping in asyncio.to_thread() when calling.
        """
        if not self._container:
            return False
        try:
            wrapped = self._container.get_wrapped_container()
            wrapped.reload()
            return wrapped.status == "running"
        except Exception:
            return False


class WorkerPoolBridge:
    """Adapts WorkerPool to ContainerPool interface for KaliExecutor.

    Instead of managing its own Docker containers, this bridge delegates
    execution to the shared WorkerPool that already manages pre-existing
    Kali worker containers (red-kali-worker-{1..N}).

    The bridge does direct ``docker exec`` calls (bypassing WorkerPool.execute_task)
    to get proper stdout/stderr/exit_code separation — execute_task() discards
    stdout on non-zero exit codes which loses valid tool output.
    """

    def __init__(self, worker_pool):
        self.worker_pool = worker_pool  # Mutable — updated by session_manager

    def acquire(self, timeout: Optional[float] = None) -> '_WorkerBridgeContext':
        return _WorkerBridgeContext(self, timeout)

    @property
    def pressure(self) -> float:
        status = self.worker_pool.get_pool_status()
        total = status.get('pool_size', 1) or 1
        busy = status.get('busy', 0)
        return busy / total

    @property
    def available_count(self) -> int:
        return self.worker_pool.available_workers.qsize()

    @property
    def in_use_count(self) -> int:
        status = self.worker_pool.get_pool_status()
        return status.get('busy', 0)


class _WorkerBridgeContext:
    """Async context manager for worker acquisition/release."""

    def __init__(self, bridge: WorkerPoolBridge, timeout: Optional[float] = None):
        self._bridge = bridge
        self._timeout = timeout or 60.0
        self._container_id: Optional[str] = None
        self._container: Optional['_WorkerBridgeContainer'] = None

    async def __aenter__(self) -> '_WorkerBridgeContainer':
        self._container_id = await self._bridge.worker_pool.acquire_worker(
            timeout=self._timeout
        )
        if not self._container_id:
            raise ContainerPoolExhausted("No workers available (timeout)")
        self._container = _WorkerBridgeContainer(self._bridge, self._container_id)
        return self._container

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._container_id:
            recycle = bool(self._container and self._container.needs_recycle)
            if recycle:
                reason = (
                    self._container.recycle_reason
                    if self._container and self._container.recycle_reason
                    else "timeout_cleanup_failed"
                )
                await self._bridge.worker_pool.recycle_worker(
                    self._container_id,
                    reason=reason,
                )
            else:
                self._bridge.worker_pool.release_worker(self._container_id)


class _WorkerBridgeContainer:
    """Wraps docker exec calls against a real worker container, returning ToolResult.

    Bypasses WorkerPool.execute_task() to preserve separate stdout/stderr and
    actual exit codes (execute_task merges them into a lossy string format).
    """

    def __init__(self, bridge: WorkerPoolBridge, container_id: str):
        self._bridge = bridge
        self._container_id = container_id
        self._needs_recycle = False
        self._recycle_reason: str | None = None

    @property
    def needs_recycle(self) -> bool:
        return self._needs_recycle

    @property
    def recycle_reason(self) -> str | None:
        return self._recycle_reason

    def _mark_recycle(self, reason: str) -> None:
        self._needs_recycle = True
        if not self._recycle_reason:
            self._recycle_reason = reason

    def _detect_scanner_crash(
        self,
        command: str,
        stdout: str,
        stderr: str,
        exit_code: int,
    ) -> str | None:
        lowered_command = command.lower()
        if not any(tool in lowered_command for tool in _SCANNER_TIMEOUT_GUARD_TOOLS):
            return None

        combined = f"{stdout}\n{stderr}".lower()
        if "nmap" in lowered_command and (
            exit_code == 139 or "segmentation fault" in combined
        ):
            return "nmap_segfault"

        crash_markers = (
            "segmentation fault",
            "core dumped",
            "double free",
            "stack smashing",
            "fatal signal",
        )
        if any(marker in combined for marker in crash_markers):
            return "scanner_crash"

        if exit_code in {134, 135, 136, 139}:
            return "scanner_crash_exit"
        return None

    async def _terminate_exec_process(
        self,
        proc: asyncio.subprocess.Process,
        command: str,
    ) -> None:
        """Best-effort terminate of timed-out docker exec process tree."""
        if proc.returncode is not None:
            return
        process_group_id: int | None = None
        try:
            if proc.pid:
                process_group_id = os.getpgid(proc.pid)
        except Exception:
            process_group_id = None
        try:
            if process_group_id is not None:
                os.killpg(process_group_id, signal.SIGTERM)
            else:
                proc.terminate()
        except ProcessLookupError:
            return
        except Exception as e:
            logger.warning("bridge_exec_terminate_failed: cmd=%s error=%s", command[:50], str(e))
        try:
            await asyncio.wait_for(proc.communicate(), timeout=2.0)
            return
        except Exception:
            pass
        try:
            if process_group_id is not None:
                os.killpg(process_group_id, signal.SIGKILL)
            else:
                proc.kill()
        except ProcessLookupError:
            return
        except Exception as e:
            logger.warning("bridge_exec_kill_failed: cmd=%s error=%s", command[:50], str(e))
            return
        try:
            await asyncio.wait_for(proc.communicate(), timeout=2.0)
        except Exception:
            pass

    async def _cleanup_timed_out_processes(self, command: str) -> bool:
        lowered = command.lower()
        matched = [tool for tool in _SCANNER_TIMEOUT_GUARD_TOOLS if tool in lowered]

        if matched:
            unique_tools = tuple(dict.fromkeys(matched))
        else:
            unique_tools = _SCANNER_TIMEOUT_GUARD_TOOLS
        tool_args = " ".join(shlex.quote(tool) for tool in unique_tools)
        cleanup_script = (
            f"for tool in {tool_args}; do "
            "pkill -TERM -f \"(^|/)$tool(\\s|$)\" >/dev/null 2>&1 || true; "
            "done; "
            "sleep 1; "
            f"for tool in {tool_args}; do "
            "pkill -KILL -f \"(^|/)$tool(\\s|$)\" >/dev/null 2>&1 || true; "
            "done; "
            "exit 0"
        )
        args = [
            "/usr/bin/docker",
            "exec",
            self._container_id,
            "sh",
            "-lc",
            cleanup_script,
        ]
        proc: Optional[asyncio.subprocess.Process] = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10.0)
            if proc.returncode == 0:
                return True
            logger.warning(
                "timeout_cleanup_failed_nonzero: container=%s cmd=%s rc=%s",
                self._container_id,
                command[:80],
                proc.returncode,
            )
            return False
        except Exception as e:
            logger.warning(
                "timeout_cleanup_exception: container=%s cmd=%s error=%s",
                self._container_id,
                command[:80],
                str(e),
            )
            if proc is not None and proc.returncode is None:
                try:
                    proc.kill()
                except Exception:
                    pass
            return False

    async def execute(self, code: str, timeout: int = 30) -> ToolResult:
        timeout_budget = max(1, int(float(timeout)))
        timeout_grace = max(
            1,
            int(os.getenv("CYBERRED_CONTAINER_TIMEOUT_GRACE_S", "15")),
        )
        outer_timeout = timeout_budget + timeout_grace + 5
        quoted_code = shlex.quote(code)
        wrapped = (
            "if command -v bash >/dev/null 2>&1; then "
            f"exec timeout -k {timeout_grace}s {timeout_budget}s "
            f"bash -o pipefail -lc {quoted_code}; "
            "else "
            f"exec timeout -k {timeout_grace}s {timeout_budget}s "
            f"sh -lc {quoted_code}; "
            "fi"
        )
        args = [
            "/usr/bin/docker",
            "exec",
            self._container_id,
            "sh",
            "-lc",
            wrapped,
        ]

        start_time = time.perf_counter()
        proc: Optional[asyncio.subprocess.Process] = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=outer_timeout
            )
        except asyncio.CancelledError:
            if proc is not None:
                await self._terminate_exec_process(proc, code)
            cleanup_ok = await self._cleanup_timed_out_processes(code)
            self._mark_recycle("cancelled_cleanup_failed" if not cleanup_ok else "cancelled_cleanup")
            raise
        except asyncio.TimeoutError:
            if proc is not None:
                await self._terminate_exec_process(proc, code)
            cleanup_ok = await self._cleanup_timed_out_processes(code)
            self._mark_recycle("timeout_cleanup_failed" if not cleanup_ok else "timeout_recycle")
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning("bridge_execute_timeout: cmd=%s timeout=%s", code[:50], timeout)
            return ToolResult(
                success=False, stdout="", stderr=f"Execution timed out after {timeout_budget}s",
                exit_code=-1, duration_ms=duration_ms, error_type="TIMEOUT",
            )
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            error_type = "EXECUTION_EXCEPTION"
            if "NotFound" in type(e).__name__ or "not found" in str(e).lower():
                error_type = "CONTAINER_CRASHED"
                self._mark_recycle("container_not_found")
            logger.warning("bridge_exec_exception: cmd=%s error=%s", code[:50], str(e))
            return ToolResult(
                success=False, stdout="", stderr=str(e),
                exit_code=-1, duration_ms=duration_ms, error_type=error_type,
            )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        stdout_str = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr_str = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        if proc.returncode in _TIMEOUT_EXIT_CODES:
            cleanup_ok = await self._cleanup_timed_out_processes(code)
            self._mark_recycle("timeout_cleanup_failed" if not cleanup_ok else "timeout_recycle")
            logger.warning(
                "bridge_execute_timeout_exit: cmd=%s timeout=%ss rc=%s",
                code[:50],
                timeout_budget,
                proc.returncode,
            )
            return ToolResult(
                success=False,
                stdout=stdout_str,
                stderr=stderr_str or f"Execution timed out after {timeout_budget}s",
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                error_type="TIMEOUT",
            )

        crash_reason = self._detect_scanner_crash(
            command=code,
            stdout=stdout_str,
            stderr=stderr_str,
            exit_code=proc.returncode,
        )
        if crash_reason:
            self._mark_recycle(crash_reason)
            logger.warning(
                "bridge_execute_scanner_crash: container=%s reason=%s rc=%s cmd=%s",
                self._container_id,
                crash_reason,
                proc.returncode,
                code[:80],
            )

        return ToolResult(
            success=proc.returncode == 0,
            stdout=stdout_str,
            stderr=stderr_str,
            exit_code=proc.returncode,
            duration_ms=duration_ms,
            error_type=(
                "CONTAINER_CRASHED"
                if crash_reason
                else ("NON_ZERO_EXIT" if proc.returncode != 0 else None)
            ),
        )

    async def execute_pipeline(self, segments: list[str], timeout: int = 30) -> ToolResult:
        """Execute a validated pipeline in the worker container via sh -c."""
        safe_parts = []
        for seg in segments:
            try:
                tokens = shlex.split(seg)
                safe_parts.append(shlex.join(tokens))
            except ValueError:
                safe_parts.append(seg)

        shell_cmd = " | ".join(safe_parts)
        return await self.execute(shell_cmd, timeout=timeout)

    def is_healthy(self) -> bool:
        return self._container_id is not None


class MockContainer(ContainerProtocol):
    def __init__(self, fixture_loader: Optional['FixtureLoader'] = None, latency_ms: int = 0):
        self._fixture_loader = fixture_loader or FixtureLoader()
        self._latency_ms = latency_ms

    async def execute(self, code: str, timeout: int = 30) -> ToolResult:
        if self._latency_ms > 0:
            await asyncio.sleep(self._latency_ms / 1000.0)

        tool_name = self._detect_tool(code)
        if not tool_name:
             # If no tool detected, return a generic failed result or empty
             return ToolResult(
                 success=False,
                 stdout="",
                 stderr="Could not detect tool command",
                 exit_code=1,
                 duration_ms=0
             )

        return self._load_response(tool_name, code)

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    def is_healthy(self) -> bool:
        return True

    def _detect_tool(self, code: str) -> Optional[str]:
        # Simple heuristic: first word, stripping path
        # handle "nmap -sV" -> "nmap"
        # handle "/usr/bin/nmap" -> "nmap"
        # handle "./nuclei" -> "nuclei"
        if not code:
            return None
        
        parts = code.strip().split()
        if not parts:
            return None
            
        command = parts[0]
        # Get basename
        tool_name = os.path.basename(command)
        return tool_name

    def _load_response(self, tool_name: str, code: str) -> ToolResult:
        fixture_name = f"{tool_name}.txt"
        
        try:
            stdout = self._fixture_loader.load(fixture_name)
        except FileNotFoundError:
             stdout = "Mock output (fixture not found)"
        
        return ToolResult(
            success=True,
            stdout=stdout,
            stderr="",
            exit_code=0,
            duration_ms=0
        )
