"""
Orchestrator - Central coordinator for the Cyber-Red system.

The Orchestrator is the main entry point that initializes all components,
manages job queues, and coordinates between agents, tools, and the AI council.
"""
import asyncio
import logging
import os
from cyberred.core.event_bus import EventBus
from cyberred.core.council import CouncilOfExperts
from cyberred.core.worker_pool import WorkerPool
from cyberred.core.tool_orchestrator import ToolOrchestrator
from cyberred.agents.ghost_agent import GhostAgent
from cyberred.core.throttler import SwarmBrain
from cyberred.core.roe_loader import RoELoader
from cyberred.llm import (
    initialize_gateway, get_gateway, shutdown_gateway,
    RateLimiter, ModelRouter, LLMPriorityQueue, RetryPolicy,
    NIMProvider, TaskComplexity,
)


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

        # Engagement context (set by SessionManager)
        self._engagement_id: str | None = None
        self._engagement_config: dict | None = None

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

        # Initialize LLM Gateway singleton (rate limiting, retry, priority queue)
        try:
            api_key = os.environ.get("NVIDIA_API_KEY", "")
            if not api_key:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.environ.get("NVIDIA_API_KEY", "")

            providers = {
                TaskComplexity.FAST: NIMProvider.for_tier("FAST", api_key),
                TaskComplexity.STANDARD: NIMProvider.for_tier("STANDARD", api_key),
                TaskComplexity.COMPLEX: NIMProvider.for_tier("COMPLEX", api_key),
            }
            router = ModelRouter(providers=providers)
            rate_limiter = RateLimiter(rpm=30, burst=5)
            queue = LLMPriorityQueue()
            retry_policy = RetryPolicy()

            # Load model fallback mapping from config/models.yaml
            fallback_models = {}
            try:
                import yaml
                config_path = "config/models.yaml"
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        models_cfg = yaml.safe_load(f) or {}
                    fallback_cfg = models_cfg.get("fallback", {})
                    # Map primary model -> fallback model for each role
                    role_sections = {
                        "brain": ["architect", "strategist", "ghost"],
                        "governance": ["critic", "dispatcher"],
                        "code_generation": ["engineer", "coder"],
                    }
                    for section, roles in role_sections.items():
                        for role in roles:
                            primary = models_cfg.get(section, {}).get(role)
                            fallback = fallback_cfg.get(role)
                            if primary and fallback and primary != fallback:
                                fallback_models[primary] = fallback
                    self.logger.info(f"Loaded {len(fallback_models)} model fallbacks")
            except Exception as e:
                self.logger.warning(f"Could not load model fallbacks: {e}")

            gateway = initialize_gateway(
                rate_limiter, router, queue, retry_policy, fallback_models
            )
            await gateway.start()
            self.logger.info("LLM Gateway initialized (30 RPM, priority queue active)")
        except RuntimeError:
            self.logger.info("LLM Gateway already initialized (reusing existing)")

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
            # ALWAYS use full War Room attack flow
            "full_attack": True
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

    async def shutdown(self) -> None:
        """Graceful shutdown - stop all agents and LLM gateway."""
        self.logger.info("Orchestrator shutting down...")

        for agent_id, agent in list(self.agents.items()):
            agent.is_active = False
            self.logger.info(f"Stopped agent {agent_id}")

        self.agents.clear()

        # Shutdown LLM Gateway
        try:
            gateway = get_gateway()
            await gateway.stop()
            shutdown_gateway()
            self.logger.info("LLM Gateway shutdown complete")
        except RuntimeError:
            pass  # Gateway was never initialized

        self.logger.info("Orchestrator shutdown complete")
