"""Dynamic Agent Spawner.

This module implements the dynamic agent scaling logic based on attack surface
size and engagement phase. It ensures the swarm scales to meet workload demands
without exceeding hardware or safety limits.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

import psutil  # type: ignore
from structlog import get_logger

from cyberred.agents.roles import AgentRole
from cyberred.core.events import EventBus
from cyberred.core.models import Scope, Target
from cyberred.orchestration.router import SwarmRouterWrapper

if TYPE_CHECKING:
    from cyberred.agents.base import StigmergicAgent
    from cyberred.storage.checkpoint import CheckpointManager

logger = get_logger()

# Scope heuristics for agent count calculation
SCOPE_HEURISTICS: dict[str, int] = {
    "agents_per_class_c": 10,      # ~10 agents per /24 network
    "agents_per_webapp": 5,        # ~5 agents per web application
    "agents_per_wireless": 3,      # ~3 agents per wireless network
    "agents_per_ad_domain": 8,     # ~8 agents per AD domain
    "minimum_agents": 10,          # Minimum spawn count
    "default_ceiling": 10_000,     # NFR7: 10K ceiling (not hardcoded limit)
    "memory_reserve_mb": 4096,     # Reserved memory for system/Director/Redis
    "agents_per_cpu_core": 100,    # Async IO-bound agents per core
}

# Role distribution per engagement phase
PHASE_DISTRIBUTIONS: dict[str, dict[AgentRole, float]] = {
    "recon": {
        AgentRole.RECON: 0.40,
        AgentRole.EXPLOIT: 0.15,
        AgentRole.WEBAPP: 0.15,
        AgentRole.CREDENTIAL: 0.10,
        AgentRole.POSTEX: 0.05,
        AgentRole.AD: 0.05,
        AgentRole.WIRELESS: 0.05,
        AgentRole.FORENSICS: 0.05,
    },
    "exploit": {
        AgentRole.RECON: 0.10,
        AgentRole.EXPLOIT: 0.30,
        AgentRole.WEBAPP: 0.20,
        AgentRole.CREDENTIAL: 0.20,
        AgentRole.POSTEX: 0.10,
        AgentRole.AD: 0.05,
        AgentRole.WIRELESS: 0.03,
        AgentRole.FORENSICS: 0.02,
    },
    "postex": {
        AgentRole.RECON: 0.05,
        AgentRole.EXPLOIT: 0.10,
        AgentRole.WEBAPP: 0.05,
        AgentRole.CREDENTIAL: 0.15,
        AgentRole.POSTEX: 0.30,
        AgentRole.AD: 0.20,
        AgentRole.WIRELESS: 0.02,
        AgentRole.FORENSICS: 0.13,
    },
}

class DynamicSpawner:
    """Dynamic agent spawner based on attack surface size.

    Implements NFR6 (10K agents) and NFR7 (no artificial limits) by:
    - Calculating initial agent count from scope analysis
    - Scaling up as attack surface expands
    - Adjusting role distribution on phase transitions
    - Respecting hardware limits, not hardcoded caps

    Note:
        Network scope items are counted as individual entries, not by CIDR size.
        A /8 and /24 both count as one network item (~10 agents each).
        For CIDR-aware scaling, pre-process scope to expand large CIDRs.
    """

    def __init__(
        self,
        router: SwarmRouterWrapper,
        event_bus: EventBus,
        engagement_id: str,
        llm_gateway: Optional[Any] = None,
        manifest_loader: Optional[Any] = None,
        intel_aggregator: Optional[Any] = None,
        rag_escalator: Optional[Any] = None,
        sharded_event_bus: Optional[Any] = None,
    ) -> None:
        """Initialize the dynamic spawner.

        Args:
            router: SwarmRouterWrapper for agent creation.
            event_bus: EventBus for events and audit logging.
            engagement_id: ID of the current engagement.
            llm_gateway: Optional LLMGateway for LLM-driven tool selection.
            manifest_loader: Optional ManifestLoader for tool catalog lookup.
            intel_aggregator: Optional CachedIntelligenceAggregator for CVE/threat intel.
            rag_escalator: Optional AgentRAGEscalator for methodology retrieval on failure.
            sharded_event_bus: Optional ShardedEventBus for sharded findings (Story 7.13).
        """
        self.router = router
        self.event_bus = event_bus
        self.engagement_id = engagement_id
        self._llm_gateway = llm_gateway
        self._manifest_loader = manifest_loader
        self._intel_aggregator = intel_aggregator
        self._rag_escalator = rag_escalator
        self._sharded_event_bus = sharded_event_bus
        self._active_agents: list[StigmergicAgent] = []
        self._scaling_log: list[dict[str, Any]] = []
        self._current_phase = "recon"
        self._subscription_initialized = False

        # Subscribe to phase transitions if event loop is running
        # Otherwise, call start() explicitly after entering async context
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._subscribe_phase_transitions())
        except RuntimeError:
            logger.warning(
                "DynamicSpawner initialized outside async context. "
                "Phase transition subscription deferred - call start() in async context."
            )

    async def _subscribe_phase_transitions(self) -> None:
        """Subscribe to phase transition events."""
        await self.event_bus.subscribe(
            f"engagement:{self.engagement_id}:phase",
            self._handle_phase_transition,
        )
        self._subscription_initialized = True

    async def start(self) -> None:
        """Start the spawner and initialize subscriptions.

        Call this method if the spawner was created outside an async context.
        Safe to call multiple times - will only subscribe once.
        """
        if not self._subscription_initialized:
            await self._subscribe_phase_transitions()

    async def _handle_phase_transition(self, channel: str, data: dict[str, Any]) -> None:
        """Handle phase transition events.

        Args:
            channel: Event channel name.
            data: Event payload containing 'phase' key.
        """
        new_phase = data.get("phase")
        if new_phase in PHASE_DISTRIBUTIONS:
            self._current_phase = new_phase
            logger.info(f"Phase transition detected: {new_phase}")
            # Logic to rebalance or just update current phase for future spawns
            # For now, updating state is sufficient per story requirements.

    def calculate_initial_count(self, scope: Scope) -> int:
        """Calculate initial agent count based on scope size.

        Args:
            scope: Engagement scope definition.

        Returns:
            Calculated agent count (min 10, max ceiling).
        """
        count = 0

        # Simple heuristic: count items * weight
        # Note: networks are assumed /24 equivalent for simple heuristic per story
        count += len(scope.networks) * SCOPE_HEURISTICS["agents_per_class_c"]
        count += len(scope.webapps) * SCOPE_HEURISTICS["agents_per_webapp"]
        count += len(scope.wireless) * SCOPE_HEURISTICS["agents_per_wireless"]
        count += len(scope.domains) * SCOPE_HEURISTICS["agents_per_ad_domain"]

        # Enforce minimum
        count = max(count, SCOPE_HEURISTICS["minimum_agents"])

        # Enforce ceiling (hardware or default)
        limit = self.detect_hardware_limit()
        count = min(count, limit)

        return count

    async def spawn_initial(self, scope: Scope) -> list[StigmergicAgent]:
        """Spawn initial agents for engagement start.

        Args:
            scope: Engagement scope.

        Returns:
            List of spawned agents.
        """
        count = self.calculate_initial_count(scope)
        distribution = self.adjust_distribution_for_phase(self._current_phase)

        agents = self.router.spawn_swarm(
            count=count,
            distribution=distribution,
            engagement_id=self.engagement_id,
            event_bus=self.event_bus,
            llm_gateway=self._llm_gateway,
            manifest_loader=self._manifest_loader,
            intel_aggregator=self._intel_aggregator,
            rag_escalator=self._rag_escalator,
            sharded_event_bus=self._sharded_event_bus,
        )

        self._active_agents.extend(agents)
        await self._log_scaling_decision(
            action="spawn_initial",
            count=count,
            rationale="initial_scope_calculation",
            decision_context=[]
        )

        return agents

    async def scale_up(
        self,
        new_targets: list[Target],
        reason: str = "new_targets_discovered",
    ) -> list[StigmergicAgent]:
        """Scale up agent count based on new targets.

        Args:
            new_targets: List of newly discovered targets.
            reason: Reason for scaling.

        Returns:
            List of newly spawned agents.
        """
        # Calculate needed agents for new targets
        count = 0
        for target in new_targets:
            if target.type == "network":
                count += SCOPE_HEURISTICS["agents_per_class_c"]
            elif target.type == "webapp":
                count += SCOPE_HEURISTICS["agents_per_webapp"]
            elif target.type == "wireless":
                count += SCOPE_HEURISTICS["agents_per_wireless"]
            elif target.type == "domain":
                count += SCOPE_HEURISTICS["agents_per_ad_domain"]

        # Check limits
        current_count = len(self._active_agents)
        limit = self.detect_hardware_limit()
        available_slots = max(0, limit - current_count)

        spawn_count = min(count, available_slots)

        if spawn_count <= 0:
            logger.warning("Scaling limit reached, cannot spawn more agents.")
            return []

        distribution = self.adjust_distribution_for_phase(self._current_phase)

        agents = self.router.spawn_swarm(
            count=spawn_count,
            distribution=distribution,
            engagement_id=self.engagement_id,
            event_bus=self.event_bus,
            llm_gateway=self._llm_gateway,
            manifest_loader=self._manifest_loader,
            sharded_event_bus=self._sharded_event_bus,
        )

        self._active_agents.extend(agents)
        await self._log_scaling_decision(
            action="scale_up",
            count=spawn_count,
            rationale=reason,
            decision_context=[]  # Add relevant context if available
        )

        return agents

    def adjust_distribution_for_phase(
        self,
        phase: str,
    ) -> dict[AgentRole, float]:
        """Get adjusted role distribution for engagement phase.

        Args:
            phase: Current engagement phase.

        Returns:
            Role distribution dictionary.
        """
        return PHASE_DISTRIBUTIONS.get(phase, PHASE_DISTRIBUTIONS["recon"])

    def detect_hardware_limit(self) -> int:
        """Calculate max agents based on available hardware.

        Returns:
            Maximum agent count based on hardware, capped at 10K.
        """
        try:
            available_memory_mb = psutil.virtual_memory().available // (1024 * 1024)
            # Reserve memory for system + Director + Redis
            usable_memory_mb = max(0, available_memory_mb - SCOPE_HEURISTICS["memory_reserve_mb"])
            # 1KB per agent = 1MB per 1000 agents
            memory_limit = (usable_memory_mb * 1000) // 1

            # CPU-based limit: async IO-bound agents per core
            cpu_limit = psutil.cpu_count() * SCOPE_HEURISTICS["agents_per_cpu_core"]

            calculated = min(memory_limit, cpu_limit)
            return min(calculated, SCOPE_HEURISTICS["default_ceiling"])
        except Exception as e:
            logger.error(f"Error detecting hardware limit: {e}")
            return SCOPE_HEURISTICS["default_ceiling"]

    def get_active_count(self) -> int:
        """Get current active agent count."""
        return len(self._active_agents)

    def get_scaling_log(self) -> list[dict[str, Any]]:
        """Get history of scaling decisions (NFR37)."""
        return self._scaling_log

    # === Crash Recovery Methods (Story 7.12) ===

    async def replace_agent(
        self,
        crashed_agent_id: str,
        engagement_id: str,
        checkpoint_manager: "CheckpointManager",
    ) -> Optional["StigmergicAgent"]:
        """Replace crashed agent with checkpoint restoration.
        
        Per ERR5: "Log crash, spawn replacement, resume from checkpoint"
        
        Args:
            crashed_agent_id: ID of the crashed agent.
            engagement_id: Engagement ID.
            checkpoint_manager: CheckpointManager for loading state.
            
        Returns:
            Replacement agent if successful, None if no checkpoint found or invalid.
        """
        # Load checkpoint for crashed agent
        agent_state = await checkpoint_manager.load_agent_state(engagement_id, crashed_agent_id)
        
        if not agent_state:
            logger.warning("no_checkpoint_for_crashed_agent", agent_id=crashed_agent_id)
            return None
        
        # Determine role from checkpoint with validation
        try:
            role = AgentRole(agent_state.agent_type)
        except ValueError:
            logger.error(
                "invalid_agent_type_in_checkpoint",
                agent_id=crashed_agent_id,
                agent_type=agent_state.agent_type,
            )
            return None
        
        # Spawn replacement with same ID (for continuity)
        replacement = await self.router.create_agent(
            role=role,
            agent_id=crashed_agent_id,  # Inherit ID
            engagement_id=engagement_id,
            event_bus=self.event_bus,
            sharded_event_bus=self._sharded_event_bus,
        )
        
        # Restore state from checkpoint
        await replacement.restore_from_checkpoint(agent_state)
        
        # Start agent's async components (heartbeat, subscriptions)
        await replacement.spawn()
        
        # Update active agents list
        self._active_agents = [a for a in self._active_agents if a.agent_id != crashed_agent_id]
        self._active_agents.append(replacement)
        
        await self._log_scaling_decision(
            action="replace_crashed",
            count=1,
            rationale=f"crash_recovery_for_{crashed_agent_id}",
            decision_context=[],
        )
        
        logger.info("agent_replaced", agent_id=crashed_agent_id, role=role.value)
        return replacement

    async def _log_scaling_decision(
        self,
        action: str,
        count: int,
        rationale: str,
        decision_context: list[str],
    ) -> None:
        """Log scaling decision for NFR37 compliance.

        Args:
            action: Type of scaling action (spawn_initial, scale_up, etc.).
            count: Number of agents affected.
            rationale: Reason for the scaling decision.
            decision_context: List of IDs of signals that influenced decision.
        """
        decision = {
            "action": action,
            "count": count,
            "rationale": rationale,
            "decision_context": decision_context,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._scaling_log.append(decision)

        # Publish audit event with exception handling
        try:
            await self.event_bus.publish("audit:spawner", decision)
        except Exception as e:
            logger.error(f"Failed to publish audit event: {e}", decision=decision)
