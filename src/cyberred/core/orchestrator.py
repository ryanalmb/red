"""
Orchestrator - Central coordinator for the Cyber-Red system.

The Orchestrator is the main entry point that initializes all components,
manages job queues, and coordinates between agents, tools, and the AI council.

Story 7.26: Wires the stigmergic agent swarm (StigmergicAgent, SwarmRouterWrapper,
DynamicSpawner) into the actual execution flow, replacing the hardcoded GhostAgent
for full engagements while keeping GhostAgent for quick_attack mode.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from cyberred.core.event_bus import EventBus
from cyberred.core.council import CouncilOfExperts
from cyberred.core.worker_pool import WorkerPool
from cyberred.core.tool_orchestrator import ToolOrchestrator
from cyberred.agents.ghost_agent import GhostAgent
from cyberred.core.throttler import SwarmBrain
from cyberred.core.roe_loader import RoELoader
from cyberred.core.models import Scope
from cyberred.orchestration.router import SwarmRouterWrapper
from cyberred.orchestration.spawner import DynamicSpawner
from cyberred.llm import (
    initialize_gateway, get_gateway, shutdown_gateway,
    RateLimiter, ModelRouter, LLMPriorityQueue, RetryPolicy,
    NIMProvider, TaskComplexity,
)
from cyberred.rag.director_client import DirectorRAGClient
from cyberred.core.sharding import ShardedEventBus, ShardAggregator


# Role-specific execute method mapping
# Method names match actual implementations in agent subclasses
_ROLE_EXECUTE_METHODS: dict[str, str] = {
    "recon": "execute_recon",
    "exploit": "execute_exploit",
    "postex": "execute_postex",
    "webapp": "execute_webapp_scan",
    "wireless": "execute_wireless_scan",
    "ad": "execute_ad_attack",
    "credential": "execute_credential_attack",
    "forensics": "execute_forensics_collection",
}


class Orchestrator:
    """
    Central coordinator for the Cyber-Red attack platform.

    Responsibilities:
    - Initialize all core components
    - Manage job queue and agent lifecycle
    - Route commands from TUI to agents
    - Coordinate between AI council and tool execution
    - Spawn and manage stigmergic agent swarms (Story 7.26)
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

        # Tool orchestrator for parallel tool execution (used by GhostAgent fallback)
        self.tool_orchestrator = ToolOrchestrator(
            worker_pool=self.pool,
            event_bus=self.bus
        )

        # AI Council for strategic decisions (used by GhostAgent + NLP dispatch)
        self.council = CouncilOfExperts(
            self.brain,
            self.roe,
            self.bus,
            self.roe_loader
        )

        # Stigmergic swarm components (Story 7.26)
        self.router = SwarmRouterWrapper(swarm_type="ConcurrentWorkflow")
        self.spawner: DynamicSpawner | None = None  # Created per-engagement
        self._swarm_tasks: list[asyncio.Task] = []

        # Active agents (supports both GhostAgent and StigmergicAgent)
        self.agents: dict[Any, Any] = {}
        self.next_agent_id = 1

        # Director RAG swarm failure tracking
        self._swarm_failure_counts: dict[str, int] = {}  # agent_role -> failure_count
        self._swarm_failure_threshold = 3  # trigger pivot after N total role failures
        self._director_rag_client: DirectorRAGClient | None = None  # set in _deploy_stigmergic_swarm

        # Stigmergic sharding (Story 7.13)
        self._sharded_bus: ShardedEventBus | None = None
        self._shard_aggregator: ShardAggregator | None = None

        # Director layer (Stories 8.1–8.11)
        self._director_ensemble: Any = None
        self._finding_aggregator: Any = None
        self._strategy_publisher: Any = None
        self._replan_manager: Any = None
        self._current_phase: str = "recon"

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

        # KaliExecutor initialization deferred to _deploy_stigmergic_swarm()
        # because session_manager replaces self.pool AFTER __init__.

        # Set scope_path in settings so agents can load scope validator
        self._configure_scope_path()

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

    def _init_kali_executor(self) -> None:
        """Initialize the kali_execute() singleton for stigmergic agents.

        Creates a WorkerPoolBridge wrapping self.pool and a ScopeValidator
        from engagement config, then initializes the module-level executor.

        Called from _deploy_stigmergic_swarm() (not __init__) so that
        self.pool is the shared WorkerPool injected by session_manager.
        """
        try:
            from cyberred.tools.kali_executor import initialize_executor, _executor
            if _executor is not None:
                self.logger.info("KaliExecutor already initialized, skipping")
                return

            from cyberred.tools.container_pool import WorkerPoolBridge
            from cyberred.tools.scope import ScopeValidator, ScopeConfig

            # Build scope validator - prefer scope.yaml file, fall back to engagement config
            scope_validator: ScopeValidator
            scope_file_loaded = False

            # Try scope.yaml next to engagement config first
            if self._engagement_config:
                config_path = self._engagement_config.get("engagement_config_path", "")
                if config_path:
                    from pathlib import Path
                    scope_file = Path(config_path).parent / "scope.yaml"
                    if scope_file.exists():
                        scope_validator = ScopeValidator.from_file(scope_file)
                        scope_file_loaded = True
                        self.logger.info(f"KaliExecutor scope loaded from {scope_file}")

            if not scope_file_loaded:
                if self._engagement_config and "scope" in self._engagement_config:
                    scope_data = self._engagement_config["scope"]
                    allowed_targets = scope_data.get("allowed_targets") or scope_data.get("allowed_ips", [])
                    scope_validator = ScopeValidator.from_config({
                        "allowed_targets": allowed_targets,
                        "allowed_ports": scope_data.get("allowed_ports"),
                        "allow_private": scope_data.get("allow_private", True),
                        "allow_loopback": scope_data.get("allow_loopback", False),
                    })
                else:
                    # Permissive default - scope enforcement happens at agent level too
                    scope_validator = ScopeValidator(ScopeConfig(allow_private=True))

            # Bridge to the shared WorkerPool for real Docker execution
            container_pool = WorkerPoolBridge(self.pool)
            initialize_executor(container_pool, scope_validator)
            self.logger.info("KaliExecutor initialized with WorkerPoolBridge (real containers)")
        except Exception as e:
            self.logger.warning(f"KaliExecutor init failed (agents will use fallback): {e}")

    def _configure_scope_path(self) -> None:
        """Set scope_path in global settings so agents can load the scope validator."""
        try:
            from cyberred.core.config import get_settings
            settings = get_settings()

            # If engagement config has a scope_path, use it
            if self._engagement_config:
                scope_path = self._engagement_config.get("scope_path", "")
                if not scope_path:
                    # Try default location next to config file
                    config_path = self._engagement_config.get("engagement_config_path", "")
                    if config_path:
                        from pathlib import Path
                        default_scope = Path(config_path).parent / "scope.yaml"
                        if default_scope.exists():
                            scope_path = str(default_scope)

                if scope_path:
                    settings.engagement.scope_path = scope_path
                    self.logger.info(f"Scope path set: {scope_path}")
        except Exception as e:
            self.logger.warning(f"Failed to configure scope path: {e}")

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
            "text": f"Dispatching command: {text}"
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
        """Handle quick scan commands (no full kill chain). Uses GhostAgent."""
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

        self.logger.info(f"Deployed GhostAgent-{agent_id} for quick scan of {target}")

    async def handle_new_job(self, data: dict):
        """
        Handle new attack job.

        For full attacks: spawns a stigmergic swarm using DynamicSpawner.
        For quick attacks: falls back to GhostAgent.
        """
        target = data.get("target")
        full_attack = data.get("full_attack", True)

        if not target:
            self.logger.warning("Job received without target")
            return

        if not full_attack:
            # Quick mode: use legacy GhostAgent
            await self._deploy_ghost_agent(target, full_attack=False)
            return

        # Full attack mode: use stigmergic swarm
        await self._deploy_stigmergic_swarm(target, data)

    async def _deploy_ghost_agent(self, target: str, full_attack: bool = True) -> None:
        """Deploy a GhostAgent for legacy/quick attack mode."""
        agent_id = self._get_next_agent_id()

        agent = GhostAgent(
            agent_id,
            self.council,
            self.tool_orchestrator,
            self.bus
        )
        self.agents[agent_id] = agent

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

        self.logger.info(f"Deployed GhostAgent-{agent_id} against {target}")

        await self.bus.publish("swarm:log", {
            "category": "DEPLOY",
            "message": f"GhostAgent-{agent_id} deployed against {target}"
        })

    async def _deploy_stigmergic_swarm(self, target: str, job_data: dict) -> None:
        """Deploy a stigmergic agent swarm for full engagement attack.

        Builds a Scope from the target, uses DynamicSpawner to calculate
        the right number and distribution of agents, spawns them, and
        launches their role-specific execution methods.
        """
        engagement_id = self._engagement_id or "default"

        # Initialize kali_execute() singleton now — self.pool has been
        # replaced by session_manager with the shared WorkerPool.
        self._init_kali_executor()

        # Build scope from target(s)
        scope = self._build_scope_from_job(target, job_data)

        # Get LLM gateway for agent tool selection
        llm_gw = None
        manifest = None
        try:
            llm_gw = get_gateway()
        except RuntimeError:
            self.logger.warning("LLM Gateway not available for stigmergic agents")

        try:
            from cyberred.tools.manifest import ManifestLoader
            manifest_path = Path("config/kali-manifest.yaml")
            if manifest_path.exists():
                manifest = ManifestLoader(manifest_path)
        except Exception as e:
            self.logger.warning(f"ManifestLoader init failed: {e}")

        # --- Intelligence Layer ---
        intel_aggregator = None
        try:
            from cyberred.intelligence.aggregator import CachedIntelligenceAggregator
            from cyberred.intelligence.stigmergic import (
                StigmergicIntelligencePublisher,
                StigmergicIntelligenceSubscriber,
            )
            from cyberred.intelligence.sources.cisa_kev import CisaKevSource
            from cyberred.intelligence.sources.exploitdb import ExploitDbSource
            from cyberred.intelligence.sources.metasploit import MetasploitSource
            from cyberred.intelligence.sources.nuclei import NucleiSource

            stig_pub = StigmergicIntelligencePublisher(self.bus)
            stig_sub = StigmergicIntelligenceSubscriber(self.bus)
            await stig_sub.subscribe()

            intel_aggregator = CachedIntelligenceAggregator(
                redis_client=self.bus.redis,
                stigmergic_subscriber=stig_sub,
                stigmergic_publisher=stig_pub,
            )
            # Register available sources (NVD excluded — requires nvdlib)
            for src in (CisaKevSource(), ExploitDbSource(), MetasploitSource(), NucleiSource()):
                intel_aggregator.add_source(src)

            self.logger.info(
                f"Intelligence layer initialized: {len(intel_aggregator._sources)} sources"
            )
        except Exception as e:
            self.logger.warning(f"Intelligence layer init failed (non-fatal): {e}")

        # --- RAG Layer ---
        rag_escalator = None
        director_rag_client = None
        try:
            from cyberred.rag.store import RAGStore
            from cyberred.rag.embeddings import RAGEmbeddings
            from cyberred.rag.query import RAGQueryInterface
            from cyberred.rag.director_client import DirectorRAGClient
            from cyberred.agents.rag_escalator import AgentRAGEscalator

            rag_store = RAGStore()
            rag_embeddings = RAGEmbeddings()
            rag_interface = RAGQueryInterface(rag_store, rag_embeddings)

            rag_escalator = AgentRAGEscalator(rag_interface)
            director_rag_client = DirectorRAGClient(rag_interface)

            self.logger.info("RAG layer initialized (store + embeddings + escalator + director client)")
        except Exception as e:
            self.logger.warning(f"RAG layer init failed (non-fatal): {e}")

        # Wire DirectorRAGClient into WarRoom for strategy enrichment
        if director_rag_client and hasattr(self, 'council'):
            self.council.war_room.set_rag_client(director_rag_client)

        # Store for swarm failure pivot and operator pivot
        if director_rag_client:
            self._director_rag_client = director_rag_client

        # Story 7.13: Create sharded event bus for stigmergic findings
        self._sharded_bus = ShardedEventBus(self.bus)
        self._shard_aggregator = ShardAggregator(
            event_bus=self.bus,
            engagement_id=engagement_id,
        )
        await self._shard_aggregator.start()

        # --- Director Layer (Stories 8.1-8.11) ---
        try:
            from cyberred.llm.ensemble import DirectorEnsemble, DirectorContext, SynthesisInput
            from cyberred.orchestration.aggregator import FindingAggregator
            from cyberred.orchestration.strategy_publisher import StrategyPublisher
            from cyberred.orchestration.replan_triggers import (
                ReplanTriggerManager, ReplanTriggerConfig,
            )

            director_ensemble = DirectorEnsemble()
            finding_aggregator = FindingAggregator(event_bus=self.bus)
            strategy_publisher = StrategyPublisher(event_bus=self.bus)

            async def _handle_replan(trigger):
                await self._director_replan_cycle(
                    trigger, director_ensemble, finding_aggregator,
                    strategy_publisher, engagement_id,
                )

            replan_manager = ReplanTriggerManager(
                event_bus=self.bus,
                on_trigger=_handle_replan,
                config=ReplanTriggerConfig(timer_interval_s=300.0),
            )
            await finding_aggregator.start(engagement_id)
            await replan_manager.start(engagement_id)

            self._director_ensemble = director_ensemble
            self._finding_aggregator = finding_aggregator
            self._strategy_publisher = strategy_publisher
            self._replan_manager = replan_manager
            self._current_phase = "recon"

            # Subscribe to strategies channel for phase transition detection
            await self.bus.subscribe(
                f"strategies:{engagement_id}",
                lambda data: asyncio.ensure_future(
                    self._check_phase_transition(data, engagement_id)
                ),
            )

            self.logger.info("Director layer initialized (ensemble + aggregator + triggers + publisher)")
        except Exception as e:
            self.logger.warning(f"Director layer init failed (non-fatal): {e}")

        # Create spawner for this engagement
        self.spawner = DynamicSpawner(
            router=self.router,
            event_bus=self.bus,
            engagement_id=engagement_id,
            llm_gateway=llm_gw,
            manifest_loader=manifest,
            intel_aggregator=intel_aggregator,
            rag_escalator=rag_escalator,
            sharded_event_bus=self._sharded_bus,
        )
        await self.spawner.start()

        # Spawn initial agent swarm based on scope
        agents = await self.spawner.spawn_initial(scope)

        agent_roles = {}
        for agent in agents:
            role_name = agent.role.value if hasattr(agent, 'role') else 'unknown'
            agent_roles[role_name] = agent_roles.get(role_name, 0) + 1
            # Track in orchestrator agents dict
            self.agents[agent.agent_id] = agent

        self.logger.info(
            f"Stigmergic swarm spawned: {len(agents)} agents, "
            f"roles: {agent_roles}"
        )

        await self.bus.publish("swarm:log", {
            "category": "DEPLOY",
            "message": (
                f"Stigmergic swarm deployed: {len(agents)} agents "
                f"({', '.join(f'{r}={c}' for r, c in agent_roles.items())})"
            ),
        })

        # Initialize each agent (EventBus subscriptions, heartbeat)
        # and launch role-specific execution
        self._active_jobs += len(agents)
        for agent in agents:
            task = asyncio.create_task(
                self._run_stigmergic_agent(agent, target, job_data)
            )
            self._swarm_tasks.append(task)

    async def _run_stigmergic_agent(
        self, agent: Any, target: str, job_data: dict
    ) -> None:
        """Initialize and run a single stigmergic agent.

        Calls agent.spawn() for subscriptions/heartbeat, then dispatches
        to the role-specific execute method (execute_recon, etc.).
        """
        try:
            # Initialize async components (subscriptions, heartbeat)
            await agent.spawn()

            # Determine the role-specific execute method
            role_value = agent.role.value if hasattr(agent, 'role') else 'recon'
            execute_method_name = _ROLE_EXECUTE_METHODS.get(role_value, "execute")

            execute_fn = getattr(agent, execute_method_name, None)
            if execute_fn is None:
                # Fallback to base execute() if subclass method not found
                execute_fn = agent.execute
                execute_method_name = "execute"

            # Build context data from job_data
            context_data = {
                k: v for k, v in job_data.items()
                if k not in ("target", "full_attack")
            }

            # Call the role-specific method
            self.logger.info(
                f"Agent {agent.agent_id} ({role_value}) executing "
                f"{execute_method_name} against {target}"
            )

            await self.bus.publish("swarm:log", {
                "category": "AGENT",
                "message": f"Agent {agent.agent_id[:8]}.. ({role_value}) engaging {target}",
            })

            # Each role-specific method takes (first_arg, context_dict) as positional args.
            # The first arg is typically 'target' but varies by role:
            #   wireless -> 'interface', ad -> 'domain_controller'
            # All accept the context dict as second positional arg.
            if execute_method_name == "execute":
                await execute_fn(f"Attack target {target}")
            else:
                await execute_fn(target, context_data)

            # Agent completed successfully
            await agent.on_complete("success", {"target": target})

        except asyncio.CancelledError:
            self.logger.info(f"Agent {agent.agent_id} cancelled")
        except Exception as e:
            self.logger.error(
                f"Agent {agent.agent_id} failed: {e}", exc_info=True
            )
            try:
                await agent.on_complete("failed", {"error": str(e)})
            except Exception:
                pass
            # Track swarm-level failures for Director RAG pivot
            role_value = agent.role.value if hasattr(agent, 'role') else 'unknown'
            self._swarm_failure_counts[role_value] = self._swarm_failure_counts.get(role_value, 0) + 1
            try:
                await self._check_swarm_failure_pivot(role_value, str(e))
            except Exception:
                pass  # Never let pivot logic break agent lifecycle
        finally:
            self._active_jobs -= 1
            self._jobs_processed += 1

    async def _check_swarm_failure_pivot(self, failed_role: str, error_msg: str) -> None:
        """Check if accumulated swarm failures warrant a Director RAG pivot."""
        total_failures = sum(self._swarm_failure_counts.values())
        if total_failures < self._swarm_failure_threshold or not self._director_rag_client:
            return

        failure_signals = [
            f"{role}: {count} failures"
            for role, count in self._swarm_failure_counts.items()
        ]
        failure_signals.append(f"latest: {failed_role} - {error_msg[:200]}")

        # Collect failed technique IDs from agents
        failed_techniques = []
        for agent in self.agents.values():
            if hasattr(agent, '_failure_counts'):
                failed_techniques.extend(
                    t for t, c in agent._failure_counts.items() if c >= 3
                )

        context = DirectorRAGClient.build_swarm_failure_context(
            failure_signals=failure_signals,
            target_service=None,
            failed_techniques=failed_techniques,
            current_phase=self._get_current_phase(),
            environment=self._get_engagement_environment(),
        )

        pivot_result = await self._director_rag_client.query_strategy_pivot(context)
        if pivot_result.methodologies:
            self.logger.info(
                f"Director RAG pivot: {len(pivot_result.methodologies)} methodologies "
                f"({total_failures} swarm failures)"
            )
            await self._publish_rag_pivot(pivot_result)
            self._swarm_failure_counts.clear()

    def _get_current_phase(self) -> str:
        """Get current engagement phase name."""
        if self._engagement_config:
            return self._engagement_config.get("phase", "reconnaissance")
        return "reconnaissance"

    def _get_engagement_environment(self) -> dict:
        """Get engagement environment metadata for RAG context."""
        env: dict[str, Any] = {}
        if self._engagement_config:
            env["target"] = self._engagement_config.get("target", "")
            env["scope"] = str(self._engagement_config.get("scope", {}))[:200]
        env["active_agents"] = len(self.agents)
        env["total_failures"] = sum(self._swarm_failure_counts.values())
        return env

    async def _publish_rag_pivot(self, pivot_result) -> None:
        """Publish RAG pivot guidance to strategies channel."""
        engagement_id = self._engagement_id or "default"
        await self.bus.publish(f"strategies:pivot:{engagement_id}", {
            "type": "rag_pivot",
            "trigger": pivot_result.query_context.trigger,
            "guidance": pivot_result.actionable_guidance[:3000],
            "technique_ids": pivot_result.technique_ids[:20],
            "query_time_ms": pivot_result.query_time_ms,
            "was_timeout": pivot_result.was_timeout,
        })
        await self.bus.publish("swarm:log", {
            "category": "RAG_PIVOT",
            "message": (
                f"Director RAG pivot ({pivot_result.query_context.trigger}): "
                f"{len(pivot_result.methodologies)} methodologies, "
                f"{len(pivot_result.technique_ids)} techniques"
            ),
        })

    async def _director_replan_cycle(
        self, trigger, ensemble, aggregator, publisher, engagement_id: str,
    ) -> None:
        """Run one Director analysis cycle when a replan trigger fires.

        1. Get aggregated findings from FindingAggregator
        2. Build DirectorContext with findings + trigger metadata
        3. Query all 3 models in parallel via query_all()
        4. Synthesize unified strategy
        5. Publish via StrategyPublisher
        6. Reset aggregation window
        """
        from cyberred.llm.ensemble import DirectorContext, SynthesisInput

        findings_prompt = aggregator.format_for_director()
        summary = aggregator.get_summary()

        context = DirectorContext(
            engagement_id=engagement_id,
            phase=self._current_phase,
            prompt=(
                f"Analyze engagement state and recommend next strategy.\n\n"
                f"{findings_prompt}"
            ),
            findings=[
                {
                    "target": f.target,
                    "type": f.finding_type,
                    "severity": f.severity.name,
                    "category": f.category.name,
                }
                for f in summary.findings[:50]
            ],
            metadata={
                "trigger_type": trigger.trigger_type.value,
                "trigger_metadata": trigger.metadata,
                "total_findings": summary.total_count,
                "active_agents": len(self.agents),
            },
        )

        try:
            result = await ensemble.query_all(context)
            synthesis_input = SynthesisInput(query_result=result)
            strategy = ensemble.synthesize(synthesis_input)

            published = await publisher.publish_strategy(strategy, engagement_id)
            if published:
                self.logger.info(
                    f"Director strategy published: confidence={published.confidence:.2f}, "
                    f"objectives={len(published.objectives)}, "
                    f"trigger={trigger.trigger_type.value}"
                )
                await self.bus.publish("swarm:log", {
                    "category": "DIRECTOR",
                    "message": (
                        f"Strategy published (trigger={trigger.trigger_type.value}, "
                        f"confidence={published.confidence:.2f})"
                    ),
                })

            aggregator.reset_window()
        except Exception as e:
            self.logger.error(f"Director replan cycle failed: {e}")
            await self.bus.publish("swarm:log", {
                "category": "DIRECTOR",
                "message": f"Strategy cycle failed: {e}",
            })

    async def _check_phase_transition(self, data: Any, engagement_id: str) -> None:
        """Check if a published strategy signals a phase transition.

        Detects ENUMERATION_COMPLETE pattern → recon→exploit transition.
        Detects credential/shell findings → exploit→postex transition.
        """
        if isinstance(data, str):
            import json
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return
        if not isinstance(data, dict):
            return

        pattern = data.get("pattern", "")

        if pattern == "enumeration_complete" and self._current_phase == "recon":
            self._current_phase = "exploit"
            await self.bus.publish(f"engagement:{engagement_id}:phase", {
                "from_phase": "recon",
                "to_phase": "exploit",
                "reason": "enumeration_complete",
            })
            self.logger.info("Phase transition: recon → exploit (enumeration_complete)")
            await self.bus.publish("swarm:log", {
                "category": "PHASE",
                "message": "Phase transition: recon → exploit",
            })

        elif pattern in ("credential_pivot", "shell_obtained") and self._current_phase == "exploit":
            self._current_phase = "postex"
            await self.bus.publish(f"engagement:{engagement_id}:phase", {
                "from_phase": "exploit",
                "to_phase": "postex",
                "reason": pattern,
            })
            self.logger.info(f"Phase transition: exploit → postex ({pattern})")
            await self.bus.publish("swarm:log", {
                "category": "PHASE",
                "message": f"Phase transition: exploit → postex ({pattern})",
            })

    def _build_scope_from_job(self, target: str, job_data: dict) -> Scope:
        """Build a Scope object from job data and engagement config.

        Uses engagement config targets if available, otherwise builds
        a minimal scope from the single target.
        """
        networks: list[str] = []
        webapps: list[str] = []

        # If engagement config has full target list, use it
        if self._engagement_config:
            targets = self._engagement_config.get("targets", {})
            for target_name, target_info in targets.items():
                if isinstance(target_info, dict):
                    ip = target_info.get("ip")
                    services = target_info.get("services", [])
                    if ip:
                        networks.append(ip)
                    if "http" in services or "https" in services:
                        webapps.append(ip or target_name)

        # Ensure the current target is included
        if target not in networks:
            networks.append(target)

        return Scope(
            networks=networks,
            webapps=webapps,
        )

    async def handle_stop_agent(self, data: dict):
        """Handle request to stop an agent."""
        agent_id = data.get("agent_id")

        if agent_id in self.agents:
            agent = self.agents[agent_id]
            # StigmergicAgent uses shutdown(), GhostAgent uses pause()
            if hasattr(agent, 'shutdown'):
                await agent.shutdown()
            elif hasattr(agent, 'pause'):
                agent.pause()
            await self.bus.publish("swarm:log", {
                "category": "SYSTEM",
                "message": f"Agent {agent_id} stopped"
            })

    def _get_next_agent_id(self) -> int:
        """Get next available agent ID (for GhostAgent legacy mode)."""
        agent_id = self.next_agent_id
        self.next_agent_id += 1
        if self.next_agent_id > 100:
            self.next_agent_id = 1  # Cycle IDs
        return agent_id

    async def start_swarm(self, scope: Scope, engagement_id: str | None = None) -> list:
        """Start a stigmergic swarm directly (called by SessionManager).

        This method is the direct entry point for SessionManager to spawn
        a swarm without going through the job:new event bus.

        Args:
            scope: Engagement scope with networks, webapps, etc.
            engagement_id: Optional engagement ID override.

        Returns:
            List of spawned agents.
        """
        eid = engagement_id or self._engagement_id or "default"

        llm_gw = None
        manifest = None
        try:
            llm_gw = get_gateway()
        except RuntimeError:
            pass
        try:
            from cyberred.tools.manifest import ManifestLoader
            manifest_path = Path("config/kali-manifest.yaml")
            if manifest_path.exists():
                manifest = ManifestLoader(manifest_path)
        except Exception:
            pass

        self.spawner = DynamicSpawner(
            router=self.router,
            event_bus=self.bus,
            engagement_id=eid,
            llm_gateway=llm_gw,
            manifest_loader=manifest,
        )
        await self.spawner.start()

        agents = await self.spawner.spawn_initial(scope)

        for agent in agents:
            self.agents[agent.agent_id] = agent

        self.logger.info(f"Swarm started: {len(agents)} agents for engagement {eid}")
        return agents

    async def stop_all_agents(self):
        """Emergency stop all agents."""
        self.logger.warning("PANIC: Stopping all agents")

        # Stop Director layer if running
        if self._replan_manager:
            try:
                await self._replan_manager.stop()
            except Exception:
                pass
        if self._finding_aggregator:
            try:
                await self._finding_aggregator.stop()
            except Exception:
                pass

        # Stop shard aggregator if running
        if self._shard_aggregator:
            try:
                await self._shard_aggregator.stop()
            except Exception:
                pass

        # Cancel swarm tasks
        for task in self._swarm_tasks:
            task.cancel()
        self._swarm_tasks.clear()

        for agent_id, agent in self.agents.items():
            if hasattr(agent, 'shutdown'):
                try:
                    await agent.shutdown()
                except Exception:
                    pass
            elif hasattr(agent, 'pause'):
                agent.pause()

        await self.bus.publish("swarm:log", {
            "category": "PANIC",
            "message": "All agents stopped"
        })

    def get_status(self) -> dict:
        """Get orchestrator status."""
        pool_status = self.pool.get_pool_status()

        # Count active stigmergic agents
        stigmergic_count = sum(
            1 for a in self.agents.values()
            if hasattr(a, 'get_status') and callable(a.get_status)
            and isinstance(a.get_status(), str)  # StigmergicAgent returns str
        )

        return {
            "agents": {
                "total": len(self.agents),
                "active": sum(
                    1 for a in self.agents.values()
                    if (hasattr(a, 'is_active') and a.is_active)
                    or (hasattr(a, 'get_status') and a.get_status() == "active")
                ),
                "stigmergic": stigmergic_count,
            },
            "worker_pool": pool_status,
            "tools": self.tool_orchestrator.get_available_tools(),
            "spawner": {
                "active": self.spawner.get_active_count() if self.spawner else 0,
            },
            "stats": {
                "jobs_processed": self._jobs_processed,
                "active_jobs": self._active_jobs
            }
        }

    async def shutdown(self) -> None:
        """Graceful shutdown - stop all agents and LLM gateway."""
        self.logger.info("Orchestrator shutting down...")

        # Cancel swarm tasks
        for task in self._swarm_tasks:
            task.cancel()
        if self._swarm_tasks:
            await asyncio.gather(*self._swarm_tasks, return_exceptions=True)
        self._swarm_tasks.clear()

        # Shutdown all agents
        for agent_id, agent in list(self.agents.items()):
            if hasattr(agent, 'shutdown') and asyncio.iscoroutinefunction(agent.shutdown):
                try:
                    await agent.shutdown()
                except Exception:
                    pass
            elif hasattr(agent, 'is_active'):
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
