import redis.asyncio as redis
import json
import asyncio
import logging

class EventBus:
    def __init__(self, redis_url="redis://localhost:6379/0"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        self.logger = logging.getLogger("EventBus")

    async def publish(self, channel: str, message: dict):
        """Publish a structured message to a channel."""
        payload = json.dumps(message)
        await self.redis.publish(channel, payload)
        # self.logger.debug(f"Published to {channel}: {payload}")

    async def subscribe(self, channel: str, callback):
        """
        Subscribe to a channel and run callback(message) for each event.
        Returns a task that should be added to the main loop.
        """
        async def reader():
            ps = self.redis.pubsub()
            await ps.subscribe(channel)
            async for message in ps.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await callback(data)
                    except json.JSONDecodeError:
                        self.logger.error(f"Invalid JSON in {channel}")
                    except Exception as e:
                        self.logger.error(f"Error in subscriber {channel}: {e}")

        return asyncio.create_task(reader())

    async def close(self):
        await self.redis.close()
