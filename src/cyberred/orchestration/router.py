"""SwarmRouter wrapper for task routing and agent spawning (Story 7.6).

This module implements the SwarmRouterWrapper class that composes with the swarms
SwarmRouter to provide:
- Task routing to 8 agent roles based on keywords/context
- Configurable swarm spawning with role distribution
- Agent factory for creating specific agent instances
- NFR37 compliant decision context tracking
- Integration with swarms library SwarmRouter for workflow execution
"""

import threading
import uuid
from typing import TYPE_CHECKING, Any, Literal

import structlog
from swarms import SwarmRouter

from cyberred.agents.ad import ADAgent
from cyberred.agents.credential import CredentialAgent
from cyberred.agents.exploit import ExploitAgent
from cyberred.agents.forensics import ForensicsAgent
from cyberred.agents.postex import PostExAgent
from cyberred.agents.recon import ReconAgent
from cyberred.agents.roles import AgentRole
from cyberred.agents.webapp import WebAppAgent
from cyberred.agents.wireless import WirelessAgent

if TYPE_CHECKING:
    from cyberred.agents.base import StigmergicAgent
    from cyberred.core.events import EventBus

# Valid swarm types from swarms library
SwarmType = Literal[
    "AgentRearrange",
    "MixtureOfAgents",
    "SequentialWorkflow",
    "ConcurrentWorkflow",
    "GroupChat",
    "MultiAgentRouter",
    "AutoSwarmBuilder",
    "HierarchicalSwarm",
    "auto",
    "MajorityVoting",
]

log = structlog.get_logger().bind(component="swarm_router")

# Keyword to AgentRole mapping for deterministic routing (no LLM)
# NOTE: Multi-word keywords MUST come before single-word to ensure correct matching
# (e.g., "active directory" before "domain", "memory dump" before generic keywords)
ROLE_KEYWORDS_MULTI: list[tuple[str, AgentRole]] = [
    # Multi-word keywords (checked first for priority)
    ("active directory", AgentRole.AD),
    ("memory dump", AgentRole.FORENSICS),
    ("dump memory", AgentRole.FORENSICS),  # Alternative word order
    ("scan bluetooth", AgentRole.WIRELESS),  # Bluetooth scan before generic "scan"
    ("bluetooth scan", AgentRole.WIRELESS),
]

ROLE_KEYWORDS: dict[str, AgentRole] = {
    # RECON
    "scan": AgentRole.RECON,
    "reconnaissance": AgentRole.RECON,
    "osint": AgentRole.RECON,
    # EXPLOIT
    "exploit": AgentRole.EXPLOIT,
    "vulnerability": AgentRole.EXPLOIT,
    # POSTEX
    "privilege": AgentRole.POSTEX,
    "escalate": AgentRole.POSTEX,
    "lateral": AgentRole.POSTEX,
    "persist": AgentRole.POSTEX,
    # WEBAPP
    "web": AgentRole.WEBAPP,
    "http": AgentRole.WEBAPP,
    "api": AgentRole.WEBAPP,
    "injection": AgentRole.WEBAPP,
    # WIRELESS
    "wireless": AgentRole.WIRELESS,
    "wifi": AgentRole.WIRELESS,
    "bluetooth": AgentRole.WIRELESS,
    # AD (single-word keywords - "active directory" handled in ROLE_KEYWORDS_MULTI)
    "kerberos": AgentRole.AD,
    "ldap": AgentRole.AD,
    "domain": AgentRole.AD,
    # CREDENTIAL
    "credential": AgentRole.CREDENTIAL,
    "password": AgentRole.CREDENTIAL,
    "hash": AgentRole.CREDENTIAL,
    "brute": AgentRole.CREDENTIAL,
    # FORENSICS (single-word - "memory dump" handled in ROLE_KEYWORDS_MULTI)
    "forensic": AgentRole.FORENSICS,
    "evidence": AgentRole.FORENSICS,
    "artifact": AgentRole.FORENSICS,
    # RECON (lower priority - generic terms)
    "enumerate": AgentRole.RECON,
    "discover": AgentRole.RECON,
    "attack": AgentRole.EXPLOIT,
}

# Default spawn distribution weights (must sum to 1.0)
ROLE_DISTRIBUTION_DEFAULTS: dict[AgentRole, float] = {
    AgentRole.RECON: 0.25,  # 25% - initial discovery
    AgentRole.EXPLOIT: 0.20,  # 20% - vulnerability exploitation
    AgentRole.WEBAPP: 0.15,  # 15% - web-focused
    AgentRole.CREDENTIAL: 0.15,  # 15% - credential hunting
    AgentRole.POSTEX: 0.10,  # 10% - post-exploitation
    AgentRole.AD: 0.08,  # 8% - AD environments
    AgentRole.WIRELESS: 0.05,  # 5% - wireless (when applicable)
    AgentRole.FORENSICS: 0.02,  # 2% - evidence collection
}

# Agent class mapping for factory
AGENT_CLASSES: dict[AgentRole, type] = {
    AgentRole.RECON: ReconAgent,
    AgentRole.EXPLOIT: ExploitAgent,
    AgentRole.POSTEX: PostExAgent,
    AgentRole.WEBAPP: WebAppAgent,
    AgentRole.WIRELESS: WirelessAgent,
    AgentRole.AD: ADAgent,
    AgentRole.CREDENTIAL: CredentialAgent,
    AgentRole.FORENSICS: ForensicsAgent,
}

# Context target_type to AgentRole mapping
TARGET_TYPE_ROUTING: dict[str, AgentRole] = {
    "web_application": AgentRole.WEBAPP,
    "wireless_network": AgentRole.WIRELESS,
    "active_directory": AgentRole.AD,
}

# Context finding_type to AgentRole mapping
FINDING_TYPE_ROUTING: dict[str, AgentRole] = {
    "credential": AgentRole.CREDENTIAL,
}


class SwarmRouterWrapper:
    """Wrapper around swarms.SwarmRouter for Cyber-Red task routing.

    Composes with the swarms library SwarmRouter to provide:
    - Deterministic keyword-based and context-based routing to 8 agent roles
    - Swarm spawning with configurable distribution
    - NFR37 compliant decision context tracking
    - Workflow execution via underlying SwarmRouter

    Attributes:
        swarm_type: The swarm execution type (e.g., "SequentialWorkflow").
        supported_roles: List of all supported AgentRole values.
        swarm_router: The underlying swarms.SwarmRouter instance (lazy-initialized).
    """

    def __init__(self, swarm_type: SwarmType = "SequentialWorkflow"):
        """Initialize the SwarmRouterWrapper.

        Args:
            swarm_type: Swarm execution type. Defaults to "SequentialWorkflow".
                Valid types: AgentRearrange, MixtureOfAgents, SequentialWorkflow,
                ConcurrentWorkflow, GroupChat, MultiAgentRouter, AutoSwarmBuilder,
                HierarchicalSwarm, auto, MajorityVoting.
        """
        self.swarm_type: SwarmType = swarm_type
        self._routing_log: list[dict[str, Any]] = []
        self._routing_log_lock = threading.Lock()  # Thread safety for routing log
        self._audit_bus: EventBus | None = None
        self._swarm_router: SwarmRouter | None = None  # Lazy-initialized
        self._log = log.bind(swarm_type=swarm_type)
        self._log.info("swarm_router_initialized")

    @property
    def supported_roles(self) -> list[AgentRole]:
        """Return list of all supported agent roles."""
        return list(AgentRole)

    @property
    def swarm_router(self) -> SwarmRouter:
        """Get or create the underlying SwarmRouter instance.

        Lazy-initializes the SwarmRouter on first access to avoid
        creating it when only using routing functionality.

        Returns:
            The underlying swarms.SwarmRouter instance.
        """
        if self._swarm_router is None:
            self._swarm_router = SwarmRouter(
                name=f"cyber-red-{self.swarm_type}",
                description="Cyber-Red agent swarm router",
                swarm_type=self.swarm_type,
                agents=[],  # Agents added dynamically via spawn_swarm
                verbose=False,
            )
            self._log.info("swarm_router_created", swarm_type=self.swarm_type)
        return self._swarm_router

    def set_audit_bus(self, event_bus: "EventBus") -> None:
        """Set the EventBus for audit logging.

        Args:
            event_bus: EventBus instance for publishing audit events.
        """
        self._audit_bus = event_bus

    def route_task(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        return_decision_context: bool = False,
    ) -> AgentRole | tuple[AgentRole, dict[str, Any]]:
        """Route a task to the appropriate agent role.

        Routing is deterministic (no LLM). Priority:
        1. Keyword matching in task text
        2. Context-based routing (target_type, finding_type)
        3. Default to RECON

        Args:
            task: The task description to route.
            context: Optional context dict with target_type, finding_type, etc.
            return_decision_context: If True, return tuple of (role, decision_context).

        Returns:
            AgentRole for the task, or tuple (AgentRole, decision_context) if requested.
        """
        context = context or {}
        task_lower = task.lower()
        matched_keyword: str | None = None
        routing_rationale: str = ""

        # Priority 1a: Multi-word keyword matching (checked first)
        for keyword, role in ROLE_KEYWORDS_MULTI:
            if keyword in task_lower:
                matched_keyword = keyword
                routing_rationale = f"Keyword '{keyword}' matched in task"
                self._log_routing(task, role, matched_keyword, routing_rationale)
                if return_decision_context:
                    return role, {
                        "matched_keyword": matched_keyword,
                        "routing_rationale": routing_rationale,
                        "role": role.value,
                    }
                return role

        # Priority 1b: Single-word keyword matching
        for keyword, role in ROLE_KEYWORDS.items():
            if keyword in task_lower:
                matched_keyword = keyword
                routing_rationale = f"Keyword '{keyword}' matched in task"
                self._log_routing(task, role, matched_keyword, routing_rationale)
                if return_decision_context:
                    return role, {
                        "matched_keyword": matched_keyword,
                        "routing_rationale": routing_rationale,
                        "role": role.value,
                    }
                return role

        # Priority 2: Context-based routing
        target_type = context.get("target_type")
        if target_type and target_type in TARGET_TYPE_ROUTING:
            role = TARGET_TYPE_ROUTING[target_type]
            routing_rationale = f"Target type '{target_type}' routed to {role.value}"
            self._log_routing(task, role, None, routing_rationale)
            if return_decision_context:
                return role, {
                    "matched_keyword": None,
                    "routing_rationale": routing_rationale,
                    "role": role.value,
                }
            return role

        finding_type = context.get("finding_type")
        if finding_type and finding_type in FINDING_TYPE_ROUTING:
            role = FINDING_TYPE_ROUTING[finding_type]
            routing_rationale = f"Finding type '{finding_type}' routed to {role.value}"
            self._log_routing(task, role, None, routing_rationale)
            if return_decision_context:
                return role, {
                    "matched_keyword": None,
                    "routing_rationale": routing_rationale,
                    "role": role.value,
                }
            return role

        # Default to RECON
        role = AgentRole.RECON
        routing_rationale = "No keyword/context match, defaulting to RECON"
        self._log_routing(task, role, None, routing_rationale)
        if return_decision_context:
            return role, {
                "matched_keyword": None,
                "routing_rationale": routing_rationale,
                "role": role.value,
            }
        return role

    async def route_task_async(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        return_decision_context: bool = False,
    ) -> AgentRole | tuple[AgentRole, dict[str, Any]]:
        """Async version of route_task that publishes to audit bus.

        Args:
            task: The task description to route.
            context: Optional context dict.
            return_decision_context: If True, return tuple of (role, decision_context).

        Returns:
            AgentRole for the task, or tuple (AgentRole, decision_context) if requested.
        """
        result = self.route_task(task, context, return_decision_context)

        # Extract role for audit publishing
        role = result[0] if return_decision_context else result

        # Publish to audit bus if configured
        if self._audit_bus:
            audit_data: dict[str, Any] = {
                "task": task[:200],  # Truncate for audit
                "role": role.value,
                "context": context,
            }
            if return_decision_context:
                audit_data["decision_context"] = result[1]
            await self._audit_bus.publish("audit:routing", audit_data)

        return result

    def _log_routing(
        self,
        task: str,
        role: AgentRole,
        matched_keyword: str | None,
        rationale: str,
    ) -> None:
        """Log a routing decision for NFR37 compliance.

        Thread-safe logging of routing decisions.

        Args:
            task: The routed task.
            role: The assigned role.
            matched_keyword: The keyword that triggered routing (if any).
            rationale: Human-readable routing rationale.
        """
        entry = {
            "task": task[:200],  # Truncate long tasks
            "role": role,
            "matched_keyword": matched_keyword,
            "routing_rationale": rationale,
        }
        with self._routing_log_lock:
            self._routing_log.append(entry)
        self._log.debug(
            "task_routed",
            role=role.value,
            matched_keyword=matched_keyword,
            rationale=rationale,
        )

    def get_routing_log(self) -> list[dict[str, Any]]:
        """Get the history of routing decisions.

        Thread-safe retrieval of routing log.

        Returns:
            List of routing decision records for NFR37 audit.
        """
        with self._routing_log_lock:
            return self._routing_log.copy()

    def create_agent(
        self,
        role: AgentRole,
        engagement_id: str,
        event_bus: "EventBus",
    ) -> "StigmergicAgent":
        """Create an agent instance for the specified role.

        Args:
            role: The AgentRole to instantiate.
            engagement_id: The engagement ID for the agent.
            event_bus: EventBus for agent communication.

        Returns:
            Agent instance of the appropriate subclass.

        Raises:
            ValueError: If role is invalid or not in AGENT_CLASSES.
        """
        if not isinstance(role, AgentRole):
            raise ValueError(f"Invalid role: {role}. Must be an AgentRole enum value.")

        if role not in AGENT_CLASSES:
            raise ValueError(f"Invalid role: {role}. No agent class mapping found.")

        agent_class = AGENT_CLASSES[role]
        # Use full UUID format to satisfy model validation
        agent_id = str(uuid.uuid4())

        # Agent subclasses use (agent_id, engagement_id, event_bus) as positional args
        agent = agent_class(
            agent_id=agent_id,
            engagement_id=engagement_id,
            event_bus=event_bus,
        )

        self._log.info(
            "agent_created",
            agent_id=agent_id,
            role=role.value,
            engagement_id=engagement_id,
        )

        return agent

    def spawn_swarm(
        self,
        count: int,
        engagement_id: str,
        event_bus: "EventBus",
        distribution: dict[AgentRole, float] | None = None,
    ) -> list["StigmergicAgent"]:
        """Spawn a swarm of agents with configurable role distribution.

        Args:
            count: Number of agents to spawn.
            engagement_id: The engagement ID for all agents.
            event_bus: EventBus for agent communication.
            distribution: Optional role distribution weights. Defaults to ROLE_DISTRIBUTION_DEFAULTS.

        Returns:
            List of spawned agent instances.

        Raises:
            ValueError: If distribution contains invalid roles or is empty.
        """
        # Validate distribution is not empty if explicitly provided
        if distribution is not None and not distribution:
            raise ValueError("Distribution cannot be empty")

        dist = distribution or ROLE_DISTRIBUTION_DEFAULTS

        # Validate distribution keys
        for role in dist:
            if not isinstance(role, AgentRole):
                raise ValueError(f"Invalid role in distribution: {role}")

        # Normalize distribution
        total_weight = sum(dist.values())
        if total_weight <= 0:
            raise ValueError("Distribution weights must sum to a positive value")
        normalized = {role: weight / total_weight for role, weight in dist.items()}

        # Calculate agent counts per role
        role_counts: dict[AgentRole, int] = {}
        remaining = count

        # Allocate agents based on distribution
        for role, weight in normalized.items():
            role_count = int(count * weight)
            role_counts[role] = role_count
            remaining -= role_count

        # Distribute remaining agents to highest-weight roles
        # All roles are guaranteed to be in role_counts from the loop above
        sorted_roles = sorted(normalized.keys(), key=lambda r: normalized[r], reverse=True)
        for i in range(remaining):
            role = sorted_roles[i % len(sorted_roles)]
            role_counts[role] += 1

        # Spawn agents
        agents: list[StigmergicAgent] = []
        for role, role_count in role_counts.items():
            for _ in range(role_count):
                agent = self.create_agent(role, engagement_id, event_bus)
                agents.append(agent)

        self._log.info(
            "swarm_spawned",
            count=len(agents),
            engagement_id=engagement_id,
            distribution={r.value: c for r, c in role_counts.items()},
        )

        return agents

    async def spawn_swarm_async(
        self,
        count: int,
        engagement_id: str,
        event_bus: "EventBus",
        distribution: dict[AgentRole, float] | None = None,
    ) -> list["StigmergicAgent"]:
        """Async version of spawn_swarm that publishes to audit bus.

        Args:
            count: Number of agents to spawn.
            engagement_id: The engagement ID for all agents.
            event_bus: EventBus for agent communication.
            distribution: Optional role distribution weights.

        Returns:
            List of spawned agent instances.
        """
        agents = self.spawn_swarm(count, engagement_id, event_bus, distribution)

        # Publish to audit bus if configured
        if self._audit_bus:
            await self._audit_bus.publish(
                "audit:swarm_spawn",
                {
                    "count": len(agents),
                    "engagement_id": engagement_id,
                    "agent_ids": [a.agent_id for a in agents],
                },
            )

        return agents
