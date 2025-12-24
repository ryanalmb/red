import asyncio
import logging

class GenericAdapter:
    """
    The Omni-Tool. Executes ANY command string in the container.
    DANGER: Must be gated by the Critic.
    """
    def __init__(self, worker_pool):
        self.worker_pool = worker_pool
        self.logger = logging.getLogger("GenericAdapter")

    async def execute(self, command: str, tool_name="generic"):
        """
        Executes a raw command.
        """
        self.logger.info(f"Executing Raw Command: {command}")
        
        # Execute via Worker Pool
        output = await self.worker_pool.execute_task(command, tool_name)
        
        return output
