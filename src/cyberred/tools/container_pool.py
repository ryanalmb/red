import os
import asyncio
import logging
import time
from pathlib import Path
from typing import Optional, Literal
from cyberred.core.models import ToolResult
from cyberred.core.exceptions import ContainerPoolExhausted
from cyberred.protocols.container import ContainerProtocol

logger = logging.getLogger(__name__)

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
        
        # Split command correctly
        cmd = code.split()
        
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
