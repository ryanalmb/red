import asyncio
import logging
import shlex
import os
from typing import Optional, Dict, Any
from src.core.event_bus import EventBus


class WorkerPool:
    """
    True parallel worker pool using asyncio Queue for work stealing.
    
    This replaces the fake implementation that always used worker-1.
    Now properly distributes work across all available Docker containers.
    """
    
    def __init__(self, event_bus: EventBus = None, pool_size: int = 10, 
                 container_prefix: str = "red-kali-worker"):
        self.bus = event_bus
        self.pool_size = pool_size
        self.container_prefix = container_prefix
        self.logger = logging.getLogger("WorkerPool")
        
        # TRUE work-stealing queue - workers are added when free
        self.available_workers: asyncio.Queue = asyncio.Queue()
        
        # Track worker states for monitoring
        self.worker_states: Dict[str, str] = {}
        
        # Initialization task
        self._initialized = False
        self._init_lock = asyncio.Lock()
        
    async def initialize(self):
        """Initialize the worker pool - must be called before first use."""
        async with self._init_lock:
            if self._initialized:
                return
            
            self.logger.info(f"Initializing worker pool with {self.pool_size} containers...")
            
            # Check Docker access first
            if not await self._check_docker_access():
                self.logger.error("Docker access check failed")
                return
            
            # Discover and add available workers
            available_count = 0
            for i in range(1, self.pool_size + 1):
                container_id = f"{self.container_prefix}-{i}"
                
                if await self._verify_container(container_id):
                    await self.available_workers.put(container_id)
                    self.worker_states[container_id] = "idle"
                    available_count += 1
                    self.logger.info(f"✓ Worker {container_id} ready")
                else:
                    self.logger.warning(f"✗ Worker {container_id} not available")
            
            self._initialized = True
            self.logger.info(f"Worker pool initialized: {available_count}/{self.pool_size} workers available")
            
            if self.bus:
                await self.bus.publish("swarm:log", {
                    "category": "POOL",
                    "message": f"Worker pool ready: {available_count} containers"
                })

    async def _check_docker_access(self) -> bool:
        """Check if we can access Docker."""
        try:
            self.logger.info(f"Checking Docker access. PID: {os.getpid()}, UID: {os.getuid()}")
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/docker", "ps",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                err = stderr.decode()
                self.logger.error(f"Docker Access Check Failed: {err}")
                if self.bus:
                    await self.bus.publish("swarm:log", {
                        "category": "ERROR",
                        "message": f"DOCKER ERROR: {err}. Please run with sudo."
                    })
                return False
            return True
        except Exception as e:
            self.logger.error(f"Docker Check Exception: {e}")
            return False

    async def _verify_container(self, container_id: str) -> bool:
        """Verify a specific container is running and responsive."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/docker", "inspect", "-f", "{{.State.Running}}", container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            return stdout.decode().strip().lower() == "true"
        except Exception as e:
            self.logger.debug(f"Container {container_id} verification failed: {e}")
            return False

    async def acquire_worker(self, timeout: float = 60.0) -> Optional[str]:
        """
        Acquire a free worker from the pool.
        
        Blocks until a worker is available or timeout is reached.
        Returns container_id or None if timeout.
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            container_id = await asyncio.wait_for(
                self.available_workers.get(), 
                timeout=timeout
            )
            self.worker_states[container_id] = "busy"
            self.logger.debug(f"Acquired worker: {container_id}")
            
            if self.bus:
                await self.bus.publish("swarm:worker_status", {
                    "worker_id": container_id,
                    "status": "busy"
                })
            
            return container_id
        except asyncio.TimeoutError:
            self.logger.warning("Timeout waiting for available worker")
            return None

    def release_worker(self, container_id: str):
        """Return a worker to the pool."""
        self.worker_states[container_id] = "idle"
        asyncio.create_task(self._async_release(container_id))

    async def _async_release(self, container_id: str):
        """Async helper to release worker back to queue."""
        await self.available_workers.put(container_id)
        self.logger.debug(f"Released worker: {container_id}")
        
        if self.bus:
            await self.bus.publish("swarm:worker_status", {
                "worker_id": container_id,
                "status": "idle"
            })

    async def execute_task(self, command: str, tool: str, retries: int = 3, 
                          timeout: float = 300.0) -> str:
        """
        Execute a command on an available worker.
        
        Args:
            command: The CLI command to execute
            tool: Name of the tool (for logging)
            retries: Number of retry attempts
            timeout: Command execution timeout
            
        Returns:
            Command output or error string
        """
        if not self._initialized:
            await self.initialize()
        
        # Acquire a worker
        container_id = await self.acquire_worker()
        if not container_id:
            return "ERROR: No workers available (timeout)"
        
        try:
            # Log start with verbose info
            if self.bus:
                await self.bus.publish("swarm:terminal", {
                    "source": container_id.split("-")[-1],  # Just the number
                    "text": f"⚡ [{tool}] Starting on worker-{container_id.split('-')[-1]}"
                })
                await self.bus.publish("swarm:terminal", {
                    "source": container_id.split("-")[-1],
                    "text": f"$ {command}"
                })

            
            # Execute with retries
            for attempt in range(retries):
                try:
                    result = await asyncio.wait_for(
                        self._run_in_docker(container_id, command),
                        timeout=timeout
                    )
                    
                    # strict check for execution error prefix
                    if not result.startswith("ERROR:"):
                        # Success - log output summary
                        source = container_id.split("-")[-1]
                        if self.bus:
                            # Log a success indicator
                            await self.bus.publish("swarm:terminal", {
                                "source": source,
                                "text": f"✓ [{tool}] Complete ({len(result)} bytes)"
                            })
                            # Log truncated output
                            if len(result) > 300:
                                await self.bus.publish("swarm:terminal", {
                                    "source": source,
                                    "text": result[:300] + f"... ({len(result)-300} more bytes)"
                                })
                            elif result.strip():
                                await self.bus.publish("swarm:terminal", {
                                    "source": source,
                                    "text": result
                                })
                        return result
                    
                    # Error but not fatal - log and retry
                    source = container_id.split("-")[-1]
                    if self.bus:
                        await self.bus.publish("swarm:terminal", {
                            "source": source,
                            "text": f"✗ [{tool}] Attempt {attempt+1} failed: {result[:200]}"
                        })

                    
                    # Fail fast on permission denied
                    if "permission denied" in result.lower() and "dial unix" in result.lower():
                        return "ERROR: Docker socket permission denied. Run with sudo."
                    
                except asyncio.TimeoutError:
                    self.logger.warning(f"Command timeout on attempt {attempt + 1}/{retries}")
                    if self.bus:
                        await self.bus.publish("swarm:terminal", {
                            "source": container_id,
                            "text": f"[TIMEOUT] Attempt {attempt + 1}/{retries}"
                        })
                
                except Exception as e:
                    self.logger.error(f"Execution error: {e}")
                
                # Wait before retry
                if attempt < retries - 1:
                    await asyncio.sleep(1)
            
            return f"ERROR: Task failed after {retries} retries. Last error: {result if 'result' in locals() else 'Unknown'}"
            
        finally:
            # Always release the worker
            self.release_worker(container_id)

    async def _run_in_docker(self, container_id: str, command: str) -> str:
        """Execute a command inside a Docker container."""
        try:
            # Safe execution using list args (no shell injection risks)
            args = ["/usr/bin/docker", "exec", container_id] + shlex.split(command)
            
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                return f"ERROR: {stderr.decode()}"
            return stdout.decode()
        except OSError as e:
            return f"ERROR: OS Error {e}"
        except Exception as e:
            return f"ERROR: Exception {e}"

    async def execute_parallel(self, commands: list, tool: str = "parallel") -> list:
        """
        Execute multiple commands in parallel across available workers.
        
        Args:
            commands: List of command strings to execute
            tool: Tool name for logging
            
        Returns:
            List of results in same order as commands
        """
        if not self._initialized:
            await self.initialize()
        
        # Create tasks for all commands
        tasks = [
            asyncio.create_task(self.execute_task(cmd, tool))
            for cmd in commands
        ]
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error strings
        return [
            str(r) if isinstance(r, Exception) else r
            for r in results
        ]

    def get_pool_status(self) -> Dict[str, Any]:
        """Get current status of the worker pool."""
        return {
            "initialized": self._initialized,
            "pool_size": self.pool_size,
            "available": self.available_workers.qsize(),
            "busy": sum(1 for s in self.worker_states.values() if s == "busy"),
            "workers": dict(self.worker_states)
        }