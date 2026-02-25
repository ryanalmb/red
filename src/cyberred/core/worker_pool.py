import asyncio
import logging
import shlex
import os
import signal
import time
from typing import Optional, Dict, Any
from cyberred.core.event_bus import EventBus


class WorkerPool:
    """
    True parallel worker pool using asyncio Queue for work stealing.
    
    This replaces the fake implementation that always used worker-1.
    Now properly distributes work across all available Docker containers.
    """
    
    def __init__(self, event_bus: EventBus = None, pool_size: int = 15, 
                 container_prefix: str = "red-kali-worker"):
        self.bus = event_bus
        self.pool_size = pool_size
        self.container_prefix = container_prefix
        self.logger = logging.getLogger("WorkerPool")
        
        # TRUE work-stealing queue - workers are added when free
        self.available_workers: asyncio.Queue = asyncio.Queue()
        
        # Track worker states for monitoring
        self.worker_states: Dict[str, str] = {}
        self._worker_state_since: Dict[str, float] = {}
        self._recovering_workers: set[str] = set()
        
        # Networks that workers have been connected to
        self._connected_networks: set[str] = set()
        
        # Initialization task
        self._initialized = False
        self._init_lock = asyncio.Lock()
        self._recovery_task: asyncio.Task | None = None
        self._recovery_stop = False
        try:
            self._recovery_interval_s = max(
                5.0, float(os.getenv("CYBERRED_WORKER_RECOVERY_INTERVAL_S", "20"))
            )
        except ValueError:
            self._recovery_interval_s = 20.0
        try:
            self._recycling_stuck_s = max(
                30.0, float(os.getenv("CYBERRED_WORKER_RECYCLING_STUCK_S", "90"))
            )
        except ValueError:
            self._recycling_stuck_s = 90.0
        try:
            self._offline_retry_s = max(
                self._recycling_stuck_s,
                float(os.getenv("CYBERRED_WORKER_OFFLINE_RETRY_S", "180")),
            )
        except ValueError:
            self._offline_retry_s = 180.0
        
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
            
            # First try named containers (red-kali-worker-1 .. N)
            available_count = 0
            for i in range(1, self.pool_size + 1):
                container_id = f"{self.container_prefix}-{i}"
                
                if await self._verify_container(container_id):
                    await self.available_workers.put(container_id)
                    self._set_worker_state(container_id, "idle")
                    available_count += 1
                    self.logger.info(f"✓ Worker {container_id} ready")
            
            # If no named workers found, discover running Kali containers by image
            if available_count == 0:
                self.logger.info("No named workers found, discovering Kali containers by image...")
                discovered = await self._discover_kali_containers()
                for container_id in discovered[:self.pool_size]:
                    await self.available_workers.put(container_id)
                    self._set_worker_state(container_id, "idle")
                    available_count += 1
                    self.logger.info(f"✓ Adopted worker {container_id}")
            
            self._initialized = True
            self.logger.info(f"Worker pool initialized: {available_count}/{self.pool_size} workers available")
            if self._recovery_task is None or self._recovery_task.done():
                self._recovery_stop = False
                self._recovery_task = asyncio.create_task(self._worker_recovery_loop())
            
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

    async def _discover_kali_containers(self) -> list[str]:
        """Discover running Kali worker containers by built image.

        Falls back to image-based discovery when named workers
        (red-kali-worker-{N}) are not found.  Only containers running the
        fully-built ``red-kali-worker`` image are adopted — bare
        ``kalilinux/kali-rolling`` base images are rejected because they
        lack the required offensive toolset.

        Returns:
            List of container names running the red-kali-worker image.
        """
        # Built worker image name (matches Dockerfile.kali / docker-compose)
        built_image = "red-kali-worker"
        try:
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/docker", "ps", "--format", "{{.Names}}\t{{.Image}}",
                "--filter", f"ancestor={built_image}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode != 0:
                return []
            names = []
            for line in stdout.decode().strip().splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t")
                name = parts[0].strip()
                image = parts[1].strip() if len(parts) > 1 else ""
                # Only accept containers using the built worker image
                if built_image in image:
                    names.append(name)
                else:
                    self.logger.warning(
                        f"Skipping container {name} (image={image}): "
                        f"bare base image, not the built {built_image} image"
                    )
            self.logger.info(f"Discovered {len(names)} built Kali worker containers")
            return names
        except Exception as e:
            self.logger.warning(f"Kali container discovery failed: {e}")
            return []

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

    async def _run_tool_canary(
        self,
        container_id: str,
        tool: str,
        timeout_s: float = 20.0,
    ) -> bool:
        """Run a lightweight tool canary after recycle."""
        proc: Optional[asyncio.subprocess.Process] = None
        try:
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/docker",
                "exec",
                container_id,
                "sh",
                "-lc",
                f"{tool} --version >/dev/null 2>&1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
            return proc.returncode == 0
        except Exception as e:
            self.logger.warning(f"Tool canary failed for {container_id} ({tool}): {e}")
            if proc is not None and proc.returncode is None:
                try:
                    proc.kill()
                except Exception:
                    pass
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
            self._set_worker_state(container_id, "busy")
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
        self._set_worker_state(container_id, "idle")
        asyncio.create_task(self._async_release(container_id))

    async def recycle_worker(self, container_id: str, reason: str = "unspecified") -> bool:
        """Recycle a worker container instead of returning it directly to the queue."""
        if container_id in self._recovering_workers:
            return False
        self._recovering_workers.add(container_id)
        self._set_worker_state(container_id, "recycling")
        self.logger.warning(f"Recycling worker {container_id} (reason={reason})")
        if self.bus:
            await self.bus.publish("swarm:worker_status", {
                "worker_id": container_id,
                "status": "recycling",
                "reason": reason,
            })

        proc: Optional[asyncio.subprocess.Process] = None
        recycle_reason = reason
        try:
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/docker", "restart", "--time", "2", container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=45.0)
            healthy = proc.returncode == 0 and await self._verify_container(container_id)
            if healthy and ("nmap" in recycle_reason or "scanner_crash" in recycle_reason):
                if not await self._run_tool_canary(container_id, "nmap"):
                    healthy = False
                    recycle_reason = f"{recycle_reason}_nmap_canary_failed"
        except Exception as e:
            self.logger.warning(f"Worker recycle failed for {container_id}: {e}")
            healthy = False
            if proc is not None and proc.returncode is None:
                try:
                    proc.kill()
                except Exception:
                    pass

        try:
            if healthy:
                self._set_worker_state(container_id, "idle")
                await self.available_workers.put(container_id)
                if self.bus:
                    await self.bus.publish("swarm:worker_status", {
                        "worker_id": container_id,
                        "status": "idle",
                        "reason": recycle_reason,
                    })
                self.logger.info(f"Worker recycled and returned: {container_id}")
                return True

            self._set_worker_state(container_id, "offline")
            if self.bus:
                await self.bus.publish("swarm:worker_status", {
                    "worker_id": container_id,
                    "status": "offline",
                    "reason": recycle_reason,
                })
            self.logger.error(f"Worker recycle failed, marked offline: {container_id}")
            return False
        finally:
            self._recovering_workers.discard(container_id)

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
        proc: Optional[asyncio.subprocess.Process] = None
        try:
            # Safe execution using list args (no shell injection risks)
            args = ["/usr/bin/docker", "exec", container_id] + shlex.split(command)
            
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                return f"ERROR: {stderr.decode()}"
            return stdout.decode()
        except asyncio.CancelledError:
            # wait_for(timeout=...) cancels this coroutine; ensure docker exec dies
            if proc is not None:
                await self._terminate_subprocess(proc, command)
            raise
        except OSError as e:
            return f"ERROR: OS Error {e}"
        except Exception as e:
            return f"ERROR: Exception {e}"

    async def _terminate_subprocess(
        self,
        proc: asyncio.subprocess.Process,
        command: str,
    ) -> None:
        """Best-effort terminate for timed-out docker exec subprocess."""
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
            self.logger.warning(f"Failed to terminate timed-out command '{command[:50]}': {e}")
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
            self.logger.warning(f"Failed to kill timed-out command '{command[:50]}': {e}")
            return
        try:
            await asyncio.wait_for(proc.communicate(), timeout=2.0)
        except Exception:
            pass

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
            "workers": dict(self.worker_states),
            "connected_networks": list(self._connected_networks),
        }

    async def shutdown(self) -> None:
        """Stop background recovery loop."""
        self._recovery_stop = True
        if self._recovery_task and not self._recovery_task.done():
            self._recovery_task.cancel()
            try:
                await self._recovery_task
            except asyncio.CancelledError:
                pass
        self._recovery_task = None

    def _set_worker_state(self, container_id: str, state: str) -> None:
        """Set worker state while tracking transition timestamp."""
        self.worker_states[container_id] = state
        self._worker_state_since[container_id] = time.monotonic()

    async def _worker_recovery_loop(self) -> None:
        """Recover workers stuck in recycling/offline states."""
        try:
            while not self._recovery_stop:
                await asyncio.sleep(self._recovery_interval_s)
                if self._recovery_stop:
                    break
                now = time.monotonic()
                for container_id, state in list(self.worker_states.items()):
                    if container_id in self._recovering_workers:
                        continue
                    state_since = float(self._worker_state_since.get(container_id, now))
                    state_age_s = max(0.0, now - state_since)

                    if state == "recycling" and state_age_s >= self._recycling_stuck_s:
                        self.logger.warning(
                            "worker_recycling_stuck_detected",
                            extra={
                                "worker_id": container_id,
                                "state_age_s": round(state_age_s, 1),
                            },
                        )
                        await self.recycle_worker(container_id, reason="stuck_recycling_timeout")
                    elif state == "offline" and state_age_s >= self._offline_retry_s:
                        self.logger.warning(
                            "worker_offline_recovery_attempt",
                            extra={
                                "worker_id": container_id,
                                "state_age_s": round(state_age_s, 1),
                            },
                        )
                        await self.recycle_worker(container_id, reason="offline_retry")
        except asyncio.CancelledError:
            pass

    async def connect_to_network(self, network_name: str) -> int:
        """Connect all workers to a Docker network.

        Used at engagement start to attach workers to the target range
        network. Idempotent — skips workers already on the network.

        Handles containers launched with ``--network none`` by disconnecting
        them from the ``none`` network first (Docker refuses to add a second
        network while ``none`` is attached).

        Args:
            network_name: Docker network name (e.g. 'cyber-range-net').

        Returns:
            Number of workers successfully connected.
        """
        if network_name in self._connected_networks:
            self.logger.info(f"Workers already connected to {network_name}")
            return len(self.worker_states)

        connected = 0
        for container_id in list(self.worker_states.keys()):
            try:
                # First attempt to connect directly
                proc = await asyncio.create_subprocess_exec(
                    "/usr/bin/docker", "network", "connect",
                    network_name, container_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()

                if proc.returncode == 0:
                    connected += 1
                    self.logger.info(f"Connected {container_id} to {network_name}")
                else:
                    err = stderr.decode().strip()
                    # "already exists" means the container is already on this network
                    if "already exists" in err:
                        connected += 1
                        self.logger.debug(f"{container_id} already on {network_name}")
                    elif "none" in err and ("private" in err or "cannot be connected" in err):
                        # Container is on the 'none' network — disconnect first
                        self.logger.info(
                            f"{container_id} on 'none' network, disconnecting first..."
                        )
                        dc_proc = await asyncio.create_subprocess_exec(
                            "/usr/bin/docker", "network", "disconnect",
                            "none", container_id,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        await dc_proc.communicate()
                        # Retry connect
                        retry_proc = await asyncio.create_subprocess_exec(
                            "/usr/bin/docker", "network", "connect",
                            network_name, container_id,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        _, retry_err = await retry_proc.communicate()
                        if retry_proc.returncode == 0:
                            connected += 1
                            self.logger.info(
                                f"Connected {container_id} to {network_name} (after none disconnect)"
                            )
                        else:
                            self.logger.warning(
                                f"Retry failed for {container_id}: {retry_err.decode().strip()}"
                            )
                    else:
                        self.logger.warning(
                            f"Failed to connect {container_id} to {network_name}: {err}"
                        )
            except Exception as e:
                self.logger.warning(f"Error connecting {container_id} to {network_name}: {e}")

        if connected > 0:
            self._connected_networks.add(network_name)
            self.logger.info(
                f"Network {network_name}: {connected}/{len(self.worker_states)} workers connected"
            )
            if self.bus:
                await self.bus.publish("swarm:log", {
                    "category": "POOL",
                    "message": f"Workers connected to network: {network_name} ({connected} workers)",
                })

        return connected

    async def disconnect_from_network(self, network_name: str) -> int:
        """Disconnect all workers from a Docker network.

        Used at engagement stop to clean up network attachments.

        Args:
            network_name: Docker network name to disconnect from.

        Returns:
            Number of workers successfully disconnected.
        """
        if network_name not in self._connected_networks:
            return 0

        disconnected = 0
        for container_id in list(self.worker_states.keys()):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "/usr/bin/docker", "network", "disconnect",
                    network_name, container_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                if proc.returncode == 0:
                    disconnected += 1
            except Exception:
                pass

        self._connected_networks.discard(network_name)
        self.logger.info(f"Disconnected {disconnected} workers from {network_name}")
        return disconnected
