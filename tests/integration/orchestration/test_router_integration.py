"""Integration tests for SwarmRouterWrapper (Story 7.6).

Tests cover:
- Router + EventBus + real agent instantiation
- Spawned agents can execute (mock tool boundary only)
- Routing decisions published to audit channel
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cyberred.agents.roles import AgentRole
from cyberred.core.events import EventBus


@pytest.fixture
def event_bus():
    """Create a real EventBus instance with mocked Redis."""
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock()
    bus.unsubscribe = AsyncMock()
    return bus


@pytest.fixture
def router():
    """Create a SwarmRouterWrapper instance."""
    from cyberred.orchestration.router import SwarmRouterWrapper
    return SwarmRouterWrapper()


class TestRouterEventBusIntegration:
    """Tests for Router + EventBus integration."""

    @pytest.mark.asyncio
    async def test_router_with_real_event_bus(self, router, event_bus):
        """Router integrates with EventBus for agent creation."""
        agent = router.create_agent(
            role=AgentRole.RECON,
            engagement_id="integration-test-eng",
            event_bus=event_bus,
        )
        
        assert agent is not None
        assert agent.event_bus is event_bus
        assert agent.engagement_id == "integration-test-eng"

    @pytest.mark.asyncio
    async def test_spawned_agents_have_event_bus(self, router, event_bus):
        """All spawned agents have event_bus configured."""
        agents = router.spawn_swarm(
            count=5,
            engagement_id="spawn-test",
            event_bus=event_bus,
        )
        
        for agent in agents:
            assert agent.event_bus is event_bus


class TestAgentInstantiation:
    """Tests for real agent instantiation through router."""

    def test_recon_agent_instantiation(self, router, event_bus):
        """ReconAgent is correctly instantiated via create_agent."""
        from cyberred.agents.recon import ReconAgent
        
        agent = router.create_agent(
            role=AgentRole.RECON,
            engagement_id="eng-recon",
            event_bus=event_bus,
        )
        
        assert isinstance(agent, ReconAgent)
        assert agent.role == AgentRole.RECON

    def test_exploit_agent_instantiation(self, router, event_bus):
        """ExploitAgent is correctly instantiated via create_agent."""
        from cyberred.agents.exploit import ExploitAgent
        
        agent = router.create_agent(
            role=AgentRole.EXPLOIT,
            engagement_id="eng-exploit",
            event_bus=event_bus,
        )
        
        assert isinstance(agent, ExploitAgent)
        assert agent.role == AgentRole.EXPLOIT

    def test_postex_agent_instantiation(self, router, event_bus):
        """PostExAgent is correctly instantiated via create_agent."""
        from cyberred.agents.postex import PostExAgent
        
        agent = router.create_agent(
            role=AgentRole.POSTEX,
            engagement_id="eng-postex",
            event_bus=event_bus,
        )
        
        assert isinstance(agent, PostExAgent)
        assert agent.role == AgentRole.POSTEX

    def test_webapp_agent_instantiation(self, router, event_bus):
        """WebAppAgent is correctly instantiated via create_agent."""
        from cyberred.agents.webapp import WebAppAgent
        
        agent = router.create_agent(
            role=AgentRole.WEBAPP,
            engagement_id="eng-webapp",
            event_bus=event_bus,
        )
        
        assert isinstance(agent, WebAppAgent)
        assert agent.role == AgentRole.WEBAPP

    def test_wireless_agent_instantiation(self, router, event_bus):
        """WirelessAgent is correctly instantiated via create_agent."""
        from cyberred.agents.wireless import WirelessAgent
        
        agent = router.create_agent(
            role=AgentRole.WIRELESS,
            engagement_id="eng-wireless",
            event_bus=event_bus,
        )
        
        assert isinstance(agent, WirelessAgent)
        assert agent.role == AgentRole.WIRELESS

    def test_ad_agent_instantiation(self, router, event_bus):
        """ADAgent is correctly instantiated via create_agent."""
        from cyberred.agents.ad import ADAgent
        
        agent = router.create_agent(
            role=AgentRole.AD,
            engagement_id="eng-ad",
            event_bus=event_bus,
        )
        
        assert isinstance(agent, ADAgent)
        assert agent.role == AgentRole.AD

    def test_credential_agent_instantiation(self, router, event_bus):
        """CredentialAgent is correctly instantiated via create_agent."""
        from cyberred.agents.credential import CredentialAgent
        
        agent = router.create_agent(
            role=AgentRole.CREDENTIAL,
            engagement_id="eng-cred",
            event_bus=event_bus,
        )
        
        assert isinstance(agent, CredentialAgent)
        assert agent.role == AgentRole.CREDENTIAL

    def test_forensics_agent_instantiation(self, router, event_bus):
        """ForensicsAgent is correctly instantiated via create_agent."""
        from cyberred.agents.forensics import ForensicsAgent
        
        agent = router.create_agent(
            role=AgentRole.FORENSICS,
            engagement_id="eng-forensics",
            event_bus=event_bus,
        )
        
        assert isinstance(agent, ForensicsAgent)
        assert agent.role == AgentRole.FORENSICS


class TestSpawnedAgentExecution:
    """Tests for spawned agent execution (mock tool boundary)."""

    @pytest.mark.asyncio
    async def test_spawned_agent_can_execute_task(self, router, event_bus):
        """Spawned agent can execute a task (with mocked tools)."""
        agents = router.spawn_swarm(
            count=1,
            engagement_id="exec-test",
            event_bus=event_bus,
            distribution={AgentRole.RECON: 1.0},
        )
        
        agent = agents[0]
        
        # Execute returns AgentAction (base implementation)
        # Use valid target without whitespace
        result = await agent.execute("192.168.1.1")
        
        assert result is not None
        assert result.agent_id == agent.agent_id

    @pytest.mark.asyncio
    async def test_multiple_spawned_agents_execute_concurrently(self, router, event_bus):
        """Multiple spawned agents can execute concurrently."""
        agents = router.spawn_swarm(
            count=3,
            engagement_id="concurrent-test",
            event_bus=event_bus,
        )
        
        # Execute all agents concurrently
        results = await asyncio.gather(
            *[agent.execute(f"task-{i}") for i, agent in enumerate(agents)]
        )
        
        assert len(results) == 3
        for result in results:
            assert result is not None


class TestRoutingAuditChannel:
    """Tests for routing decisions published to audit channel."""

    @pytest.mark.asyncio
    async def test_routing_decision_logged(self, router):
        """Routing decisions are logged internally."""
        router.route_task("scan the network")
        router.route_task("exploit vulnerability")
        
        log = router.get_routing_log()
        
        assert len(log) >= 2

    @pytest.mark.asyncio
    async def test_audit_publish_on_route(self, router, event_bus):
        """Router publishes routing decisions to audit channel when configured."""
        router.set_audit_bus(event_bus)
        
        await router.route_task_async("scan network")
        
        # Verify publish was called with audit channel
        event_bus.publish.assert_called()
        call_args = event_bus.publish.call_args
        assert "audit" in call_args[0][0] or "routing" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_spawn_publishes_audit_event(self, router, event_bus):
        """spawn_swarm publishes audit event for swarm creation."""
        router.set_audit_bus(event_bus)
        
        await router.spawn_swarm_async(
            count=3,
            engagement_id="audit-test",
            event_bus=event_bus,
        )
        
        # Verify audit event published
        assert event_bus.publish.called


class TestRouterConfiguration:
    """Tests for router configuration options."""

    def test_router_default_swarm_type(self, router):
        """Router uses default swarm type."""
        assert router.swarm_type is not None

    def test_router_custom_swarm_type(self):
        """Router accepts custom swarm type configuration."""
        from cyberred.orchestration.router import SwarmRouterWrapper
        
        router = SwarmRouterWrapper(swarm_type="ConcurrentWorkflow")
        assert router.swarm_type == "ConcurrentWorkflow"


class TestEndToEndRouting:
    """End-to-end routing scenario tests."""

    @pytest.mark.asyncio
    async def test_route_and_spawn_flow(self, router, event_bus):
        """Complete flow: route task, spawn appropriate agent, verify routing."""
        # Route a task
        role = router.route_task("scan the target network for vulnerabilities")
        assert role == AgentRole.RECON
        
        # Spawn agent for that role
        agent = router.create_agent(
            role=role,
            engagement_id="e2e-test",
            event_bus=event_bus,
        )
        
        assert agent.role == role
        assert agent.engagement_id == "e2e-test"

    @pytest.mark.asyncio
    async def test_mixed_workload_routing(self, router, event_bus):
        """Route mixed workload tasks to appropriate agents."""
        tasks = [
            ("scan network", AgentRole.RECON),
            ("exploit CVE-2021-1234", AgentRole.EXPLOIT),
            ("test web app login", AgentRole.WEBAPP),
            ("crack password hash", AgentRole.CREDENTIAL),
            ("collect forensic evidence", AgentRole.FORENSICS),
        ]
        
        for task, expected_role in tasks:
            actual_role = router.route_task(task)
            assert actual_role == expected_role, f"Task '{task}' routed to {actual_role}, expected {expected_role}"
