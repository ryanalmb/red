"""
Orchestrator - Central coordinator for the Cyber-Red system.

The Orchestrator is the main entry point that initializes all components,
manages job queues, and coordinates between agents, tools, and the AI council.
"""
import asyncio
import logging
from src.core.event_bus import EventBus
from src.core.council import CouncilOfExperts
from src.core.worker_pool import WorkerPool
from src.core.tool_orchestrator import ToolOrchestrator
from src.agents.ghost_agent import GhostAgent
from src.core.throttler import SwarmBrain
from src.core.roe_loader import RoELoader


class Orchestrator:
    """
    Central coordinator for the Cyber-Red attack platform.
    
    Responsibilities:
    - Initialize all core components
    - Manage job queue and agent lifecycle
    - Route commands from TUI to agents
    - Coordinate between AI council and tool execution
    """
    
    def __init__(self, event_bus: EventBus):
        self.bus = event_bus
        self.logger = logging.getLogger("Orchestrator")
        
        # Initialize Core Components
        self.brain = SwarmBrain(limit=30)
        self.roe_loader = RoELoader()
        self.roe = self.roe_loader.load()
        
        # Worker pool for Docker container management
        self.pool = WorkerPool(
            event_bus=self.bus, 
            pool_size=10,
            container_prefix="red-kali-worker"
        )
        
        # Tool orchestrator for parallel tool execution
        self.tool_orchestrator = ToolOrchestrator(
            worker_pool=self.pool,
            event_bus=self.bus
        )
        
        # AI Council for strategic decisions
        self.council = CouncilOfExperts(
            self.brain, 
            self.roe, 
            self.bus, 
            self.roe_loader
        )
        
        # Active agents
        self.agents = {}
        self.next_agent_id = 1
        
        # Stats
        self._jobs_processed = 0
        self._active_jobs = 0

    async def start(self):
        """Start the Orchestrator and initialize all subsystems."""
        self.logger.info("Orchestrator initializing...")
        
        # Initialize worker pool
        await self.pool.initialize()
        
        # Subscribe to job events
        await self.bus.subscribe("job:new", self.handle_new_job)
        await self.bus.subscribe("cmd:nlp", self.handle_nlp_command)
        await self.bus.subscribe("cmd:quick", self.handle_quick_command)
        await self.bus.subscribe("agent:stop", self.handle_stop_agent)
        
        # Publish ready status
        await self.bus.publish("swarm:log", {
            "category": "SYSTEM",
            "message": f"Orchestrator online. {len(self.tool_orchestrator.get_available_tools())} tools available."
        })
        
        self.logger.info("Orchestrator online.")

    async def handle_nlp_command(self, data: dict):
        """
        Handle natural language commands from the user.
        
        Uses the AI Dispatcher to parse intent and create jobs.
        """
        text = data.get("text", "").strip()
        if not text:
            return
        
        self.logger.info(f"Processing NLP command: {text}")
        
        # Log to brain stream that we're processing
        await self.bus.publish("swarm:brain", {
            "category": "DISPATCH",
            "text": f"🎯 Dispatching command: {text}"
        })
        
        # Parse Intent via Council (Dispatcher)
        intent = await self.council.parse_intent(text)
        self.logger.info(f"Intent parsed: {intent}")
        
        await self.bus.publish("swarm:brain", {
            "category": "DISPATCH",
            "text": f"Intent: {intent}"
        })

        
        if "error" in intent:
            await self.bus.publish("swarm:log", {
                "category": "ERROR",
                "message": f"Parse error: {intent['error']}"
            })
            return
        
        target = intent.get("target")
        action = intent.get("action", "scan")
        
        # Validate target
        if not target or target.lower() in ["none", "null", "", "unknown"]:
            await self.bus.publish("swarm:log", {
                "category": "ERROR",
                "message": f"No valid target found in: {text}"
            })
            return
        
        await self.bus.publish("swarm:log", {
            "category": "CMD",
            "message": f"Engaging {target} (action: {action})"
        })
        
        # Create job
        await self.handle_new_job({
            "target": target,
            "action": action,
            "full_attack": action.lower() in ["attack", "exploit", "hack", "pwn"]
        })

    async def handle_quick_command(self, data: dict):
        """Handle quick scan commands (no full kill chain)."""
        target = data.get("target")
        if not target:
            return
        
        agent_id = self._get_next_agent_id()
        agent = GhostAgent(
            agent_id, 
            self.council, 
            self.tool_orchestrator, 
            self.bus
        )
        self.agents[agent_id] = agent
        
        # Run quick attack in background
        asyncio.create_task(agent.quick_attack(target))
        
        self.logger.info(f"Deployed Agent-{agent_id} for quick scan of {target}")

    async def handle_new_job(self, data: dict):
        """
        Handle new attack job.
        
        Creates a GhostAgent and starts the attack.
        """
        target = data.get("target")
        full_attack = data.get("full_attack", True)
        
        if not target:
            self.logger.warning("Job received without target")
            return
        
        agent_id = self._get_next_agent_id()
        
        agent = GhostAgent(
            agent_id,
            self.council,
            self.tool_orchestrator,
            self.bus
        )
        self.agents[agent_id] = agent
        
        # Run attack in background
        self._active_jobs += 1
        
        async def run_and_cleanup():
            try:
                if full_attack:
                    await agent.engage(target)
                else:
                    await agent.quick_attack(target)
            finally:
                self._active_jobs -= 1
                self._jobs_processed += 1
        
        asyncio.create_task(run_and_cleanup())
        
        self.logger.info(f"Deployed Agent-{agent_id} against {target} (full: {full_attack})")
        
        await self.bus.publish("swarm:log", {
            "category": "DEPLOY",
            "message": f"Agent-{agent_id} deployed against {target}"
        })

    async def handle_stop_agent(self, data: dict):
        """Handle request to stop an agent."""
        agent_id = data.get("agent_id")
        
        if agent_id in self.agents:
            self.agents[agent_id].pause()
            await self.bus.publish("swarm:log", {
                "category": "SYSTEM",
                "message": f"Agent-{agent_id} paused"
            })

    def _get_next_agent_id(self) -> int:
        """Get next available agent ID."""
        agent_id = self.next_agent_id
        self.next_agent_id += 1
        if self.next_agent_id > 100:
            self.next_agent_id = 1  # Cycle IDs
        return agent_id

    async def stop_all_agents(self):
        """Emergency stop all agents."""
        self.logger.warning("PANIC: Stopping all agents")
        
        for agent_id, agent in self.agents.items():
            agent.pause()
        
        await self.bus.publish("swarm:log", {
            "category": "PANIC",
            "message": "All agents stopped"
        })

    def get_status(self) -> dict:
        """Get orchestrator status."""
        pool_status = self.pool.get_pool_status()
        
        return {
            "agents": {
                "total": len(self.agents),
                "active": sum(1 for a in self.agents.values() if a.is_active)
            },
            "worker_pool": pool_status,
            "tools": self.tool_orchestrator.get_available_tools(),
            "stats": {
                "jobs_processed": self._jobs_processed,
                "active_jobs": self._active_jobs
            }
        }
