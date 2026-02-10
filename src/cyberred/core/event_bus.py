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

    async def psubscribe(self, pattern: str, callback):
        """
        Subscribe to channels matching a glob pattern (Redis PSUBSCRIBE).
        Callback receives (channel, data) where channel is the actual channel name.
        Returns a task that should be added to the main loop.
        """
        async def reader():
            ps = self.redis.pubsub()
            await ps.psubscribe(pattern)
            async for message in ps.listen():
                if message["type"] == "pmessage":
                    try:
                        data = json.loads(message["data"])
                        await callback(message["channel"], data)
                    except json.JSONDecodeError:
                        self.logger.error(f"Invalid JSON in {message['channel']}")
                    except Exception as e:
                        self.logger.error(f"Error in psubscriber {pattern}: {e}")

        return asyncio.create_task(reader())

    async def audit(self, event: dict):
        """Log an audit event to the audit channel.
        
        Audit events are important compliance/security events that need
        to be recorded for later review. They are published to a dedicated
        audit channel.
        
        Args:
            event: The audit event data as a dictionary.
        """
        audit_channel = "audit:events"
        await self.publish(audit_channel, event)
        self.logger.debug(f"Audit event: {event.get('type', 'unknown')}")

    async def close(self):
        await self.redis.close()
