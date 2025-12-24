import asyncio
import logging
from src.core.event_bus import EventBus
from src.core.council import CouncilOfExperts
from src.core.worker_pool import WorkerPool
from src.agents.ghost_agent import GhostAgent
from src.core.throttler import SwarmBrain
from src.core.roe_loader import RoELoader

class Orchestrator:
    def __init__(self, event_bus: EventBus):
        self.bus = event_bus
        self.logger = logging.getLogger("Orchestrator")
        
        # Init Core Components
        self.brain = SwarmBrain(limit=30)
        self.roe = RoELoader().load()
        self.council = CouncilOfExperts(self.brain, self.roe, self.bus)
        self.pool = WorkerPool(event_bus=self.bus, container_prefix="red-kali-worker") # Matches docker-compose
        
        self.agents = {}
        self.next_agent_id = 1

    async def start(self):
        """Starts the Orchestrator loop."""
        self.logger.info("Orchestrator Online.")
        # Listen for jobs
        await self.bus.subscribe("job:new", self.handle_new_job)
        await self.bus.subscribe("cmd:nlp", self.handle_nlp_command)

    async def handle_nlp_command(self, data: dict):
        text = data.get("text")
        if not text: return
        
        # Parse Intent via Council (Dispatcher)
        intent = await self.council.parse_intent(text)
        if "error" in intent:
            await self.bus.publish("swarm:log", {"category": "ERROR", "message": intent["error"]})
            return
            
        target = intent.get("target")
        action = intent.get("action")
        
        await self.bus.publish("swarm:log", {"category": "CMD", "message": f"Engaging {target} ({action})"})
        await self.handle_new_job({"target": target})

    async def handle_new_job(self, data: dict):
        """
        Spawns a GhostAgent for a new target.
        """
        target = data.get("target")
        if not target:
            return

        agent_id = self.next_agent_id
        self.next_agent_id += 1
        if self.next_agent_id > 100: self.next_agent_id = 1 # Cycle
        
        agent = GhostAgent(agent_id, self.council, self.pool, self.bus)
        self.agents[agent_id] = agent
        
        # Run in background
        asyncio.create_task(agent.engage(target))
        self.logger.info(f"Deployed Agent-{agent_id} against {target}")
