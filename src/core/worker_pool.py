import asyncio
import logging
from asyncio import Queue
from src.core.event_bus import EventBus

class WorkerPool:
    def __init__(self, event_bus: EventBus = None, pool_size=10, container_prefix="red-kali-worker"):
        self.bus = event_bus
        self.pool_size = pool_size
        self.queue = Queue()
        self.container_prefix = container_prefix
        self.active_workers = 0
        self.logger = logging.getLogger("WorkerPool")

    async def execute_task(self, command: str, tool: str, retries=3):
        await self.queue.put((command, tool))
        container_id = await self._get_free_worker()
        
        # Log Start
        if self.bus:
            await self.bus.publish("swarm:terminal", {
                "source": container_id, "text": f"$ {command}"
            })

        for attempt in range(retries):
            result = await self._run_in_docker(container_id, command)
            if "ERROR" not in result:
                self._release_worker(container_id)
                # Log Output
                if self.bus:
                    await self.bus.publish("swarm:terminal", {
                        "source": container_id, "text": result[:500] # Truncate for TUI
                    })
                return result
            
            # Log Error
            if self.bus:
                await self.bus.publish("swarm:terminal", {
                    "source": container_id, "text": f"[STDERR] {result}"
                })
            
            await asyncio.sleep(1)
            
        self._release_worker(container_id)
        return f"ERROR: Task failed after {retries} retries."

    async def _get_free_worker(self):
        return f"{self.container_prefix}-1"

    async def _run_in_docker(self, container_id, command):
        proc = await asyncio.create_subprocess_shell(
            f"docker exec {container_id} {command}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            return f"ERROR: {stderr.decode()}"
        return stdout.decode()

    def _release_worker(self, container_id):
        pass