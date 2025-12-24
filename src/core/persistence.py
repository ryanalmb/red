import json
import logging
import os
from src.core.event_bus import EventBus

class CampaignManager:
    def __init__(self, event_bus: EventBus):
        self.bus = event_bus
        self.logger = logging.getLogger("CampaignManager")

    async def save_campaign(self, filename="campaign_save.json"):
        """Dumps entire Redis DB to JSON."""
        try:
            data = {}
            keys = await self.bus.redis.keys("*")
            for key in keys:
                val = await self.bus.redis.get(key)
                data[key] = val
            
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)
            
            self.logger.info(f"Campaign saved to {filename}")
            return True
        except Exception as e:
            self.logger.error(f"Save failed: {e}")
            return False

    async def load_campaign(self, filename="campaign_save.json"):
        """Loads JSON into Redis (Flush DB first?)."""
        if not os.path.exists(filename):
            self.logger.error("Save file not found.")
            return False
            
        try:
            with open(filename, "r") as f:
                data = json.load(f)
            
            # await self.bus.redis.flushdb() # Optional: Clear existing state
            
            for key, val in data.items():
                await self.bus.redis.set(key, val)
                
            self.logger.info(f"Campaign loaded from {filename}")
            return True
        except Exception as e:
            self.logger.error(f"Load failed: {e}")
            return False
