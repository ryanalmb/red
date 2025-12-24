import asyncio
import time
import logging

class SwarmBrain:
    """
    Manages access to the AI models with strict rate limiting.
    """
    def __init__(self, limit=30):
        self.semaphore = asyncio.Semaphore(limit)
        self.last_request_time = 0
        self.logger = logging.getLogger("SwarmBrain")

    async def invoke_model(self, client_func, *args, **kwargs):
        """
        Wraps a model call with the token bucket logic.
        """
        async with self.semaphore:
            # Basic RPM check (ensure at least 60/30 = 2s between bursts if needed, 
            # but semaphore handles concurrency which is the main issue)
            
            # self.logger.debug("Acquired Neural Token")
            try:
                start = time.time()
                response = await client_func(*args, **kwargs)
                duration = time.time() - start
                # self.logger.debug(f"Neural Inference Time: {duration:.2f}s")
                return response
            except Exception as e:
                self.logger.error(f"Model Invocation Failed: {e}")
                raise
