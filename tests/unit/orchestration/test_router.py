"""Unit tests for SwarmRouterWrapper (Story 7.6).

Tests cover:
- Recognition of all 8 AgentRole values
- Keyword-based routing via route_task()
- Context-based routing (target type)
- spawn_swarm() with default and custom distributions
- create_agent() factory returns correct agent subclass
- NFR37 decision_context tracking
- Invalid role error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cyberred.agents.roles import AgentRole


class TestSwarmRouterWrapperRecognition:
    """Tests for AgentRole recognition."""

    def test_recognizes_all_eight_roles(self):
        """SwarmRouterWrapper recognizes all 8 AgentRole values."""
        from cyberred.orchestration.router import SwarmRouterWrapper

        router = SwarmRouterWrapper()
        
        # All 8 roles should be in the AGENT_CLASSES mapping
        expected_roles = {
            AgentRole.RECON,
            AgentRole.EXPLOIT,
            AgentRole.POSTEX,
            AgentRole.WEBAPP,
            AgentRole.WIRELESS,
            AgentRole.AD,
            AgentRole.CREDENTIAL,
            AgentRole.FORENSICS,
        }
        
        assert set(router.supported_roles) == expected_roles

    def test_agent_classes_mapping_complete(self):
        """AGENT_CLASSES has mapping for every AgentRole."""
        from cyberred.orchestration.router import AGENT_CLASSES
        
        for role in AgentRole:
            assert role in AGENT_CLASSES, f"Missing mapping for {role}"


class TestRouteTaskKeywordBased:
    """Tests for keyword-based routing via route_task()."""

    @pytest.fixture
    def router(self):
        """Create a SwarmRouterWrapper instance."""
        from cyberred.orchestration.router import SwarmRouterWrapper
        return SwarmRouterWrapper()

    @pytest.mark.parametrize("task,expected_role", [
        # RECON keywords
        ("scan the network for open ports", AgentRole.RECON),
        ("enumerate services on target", AgentRole.RECON),
        ("discover hosts in subnet", AgentRole.RECON),
        ("run reconnaissance on domain", AgentRole.RECON),
        ("perform osint gathering", AgentRole.RECON),
        # EXPLOIT keywords
        ("exploit the vulnerability", AgentRole.EXPLOIT),
        ("check for vulnerability CVE-2021-1234", AgentRole.EXPLOIT),
        ("attack the service", AgentRole.EXPLOIT),
        # POSTEX keywords
        ("escalate privileges on host", AgentRole.POSTEX),
        ("perform privilege escalation", AgentRole.POSTEX),
        ("move lateral to next host", AgentRole.POSTEX),
        ("establish persistence", AgentRole.POSTEX),
        # WEBAPP keywords
        ("test web application", AgentRole.WEBAPP),
        ("check http endpoint", AgentRole.WEBAPP),
        ("test api for vulnerabilities", AgentRole.WEBAPP),
        ("find injection points", AgentRole.WEBAPP),
        # WIRELESS keywords
        ("test wireless network", AgentRole.WIRELESS),
        ("crack wifi password", AgentRole.WIRELESS),
        ("scan bluetooth devices", AgentRole.WIRELESS),
        # AD keywords
        ("enumerate active directory", AgentRole.AD),
        ("attack kerberos service", AgentRole.AD),
        ("query ldap for users", AgentRole.AD),
        ("enumerate domain controllers", AgentRole.AD),
        # CREDENTIAL keywords
        ("harvest credentials", AgentRole.CREDENTIAL),
        ("crack password hashes", AgentRole.CREDENTIAL),
        ("extract hash from memory", AgentRole.CREDENTIAL),
        ("brute force login", AgentRole.CREDENTIAL),
        # FORENSICS keywords
        ("perform forensic analysis", AgentRole.FORENSICS),
        ("collect evidence from disk", AgentRole.FORENSICS),
        ("analyze artifact", AgentRole.FORENSICS),
        ("dump memory for analysis", AgentRole.FORENSICS),
    ])
    def test_route_task_keyword_routing(self, router, task, expected_role):
        """route_task() returns correct role for keyword-based routing."""
        result = router.route_task(task)
        assert result == expected_role

    def test_route_task_case_insensitive(self, router):
        """route_task() handles case-insensitive keywords."""
        assert router.route_task("SCAN the network") == AgentRole.RECON
        assert router.route_task("Exploit The Vulnerability") == AgentRole.EXPLOIT

    def test_route_task_default_to_recon(self, router):
        """route_task() defaults to RECON for unrecognized tasks."""
        result = router.route_task("do something unknown")
        assert result == AgentRole.RECON


class TestRouteTaskContextBased:
    """Tests for context-based routing in route_task()."""

    @pytest.fixture
    def router(self):
        """Create a SwarmRouterWrapper instance."""
        from cyberred.orchestration.router import SwarmRouterWrapper
        return SwarmRouterWrapper()

    def test_route_task_webapp_context(self, router):
        """route_task() routes to WEBAPP when target is web application."""
        context = {"target_type": "web_application"}
        result = router.route_task("analyze target", context=context)
        assert result == AgentRole.WEBAPP

    def test_route_task_wireless_context(self, router):
        """route_task() routes to WIRELESS when target type is wireless."""
        context = {"target_type": "wireless_network"}
        result = router.route_task("analyze target", context=context)
        assert result == AgentRole.WIRELESS

    def test_route_task_ad_context(self, router):
        """route_task() routes to AD when target type is active_directory."""
        context = {"target_type": "active_directory"}
        result = router.route_task("analyze target", context=context)
        assert result == AgentRole.AD

    def test_route_task_credential_finding_context(self, router):
        """route_task() routes to CREDENTIAL when finding_type is credential."""
        context = {"finding_type": "credential"}
        result = router.route_task("process finding", context=context)
        assert result == AgentRole.CREDENTIAL

    def test_route_task_keyword_overrides_context(self, router):
        """Keywords take precedence over context for routing."""
        context = {"target_type": "web_application"}
        # Explicit keyword should override context
        result = router.route_task("exploit the vulnerability", context=context)
        assert result == AgentRole.EXPLOIT


class TestSpawnSwarm:
    """Tests for spawn_swarm() method."""

    @pytest.fixture
    def router(self):
        """Create a SwarmRouterWrapper instance."""
        from cyberred.orchestration.router import SwarmRouterWrapper
        return SwarmRouterWrapper()

    @pytest.fixture
    def mock_event_bus(self):
        """Create a mock EventBus."""
        bus = MagicMock()
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        return bus

    def test_spawn_swarm_default_distribution(self, router, mock_event_bus):
        """spawn_swarm() creates agents with default distribution."""
        agents = router.spawn_swarm(
            count=10,
            engagement_id="eng-123",
            event_bus=mock_event_bus,
        )
        
        assert len(agents) == 10
        # All agents should be valid instances
        for agent in agents:
            assert hasattr(agent, "role")
            assert agent.role in AgentRole

    def test_spawn_swarm_custom_distribution(self, router, mock_event_bus):
        """spawn_swarm() respects custom distribution config."""
        custom_dist = {
            AgentRole.RECON: 0.5,
            AgentRole.EXPLOIT: 0.5,
        }
        
        agents = router.spawn_swarm(
            count=10,
            engagement_id="eng-123",
            event_bus=mock_event_bus,
            distribution=custom_dist,
        )
        
        assert len(agents) == 10
        roles = [a.role for a in agents]
        # Should only have RECON and EXPLOIT roles
        assert set(roles) <= {AgentRole.RECON, AgentRole.EXPLOIT}

    def test_spawn_swarm_single_role(self, router, mock_event_bus):
        """spawn_swarm() can create all agents of single role."""
        single_role_dist = {AgentRole.WEBAPP: 1.0}
        
        agents = router.spawn_swarm(
            count=5,
            engagement_id="eng-123",
            event_bus=mock_event_bus,
            distribution=single_role_dist,
        )
        
        assert len(agents) == 5
        assert all(a.role == AgentRole.WEBAPP for a in agents)

    def test_spawn_swarm_engagement_id_propagated(self, router, mock_event_bus):
        """spawn_swarm() propagates engagement_id to all agents."""
        agents = router.spawn_swarm(
            count=3,
            engagement_id="test-engagement-456",
            event_bus=mock_event_bus,
        )
        
        for agent in agents:
            assert agent.engagement_id == "test-engagement-456"


class TestCreateAgent:
    """Tests for create_agent() factory method."""

    @pytest.fixture
    def router(self):
        """Create a SwarmRouterWrapper instance."""
        from cyberred.orchestration.router import SwarmRouterWrapper
        return SwarmRouterWrapper()

    @pytest.fixture
    def mock_event_bus(self):
        """Create a mock EventBus."""
        bus = MagicMock()
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        return bus

    @pytest.mark.parametrize("role,expected_class_name", [
        (AgentRole.RECON, "ReconAgent"),
        (AgentRole.EXPLOIT, "ExploitAgent"),
        (AgentRole.POSTEX, "PostExAgent"),
        (AgentRole.WEBAPP, "WebAppAgent"),
        (AgentRole.WIRELESS, "WirelessAgent"),
        (AgentRole.AD, "ADAgent"),
        (AgentRole.CREDENTIAL, "CredentialAgent"),
        (AgentRole.FORENSICS, "ForensicsAgent"),
    ])
    def test_create_agent_returns_correct_subclass(
        self, router, mock_event_bus, role, expected_class_name
    ):
        """create_agent() returns correct agent subclass for each role."""
        agent = router.create_agent(
            role=role,
            engagement_id="eng-123",
            event_bus=mock_event_bus,
        )
        
        assert agent.__class__.__name__ == expected_class_name
        assert agent.role == role

    def test_create_agent_sets_engagement_id(self, router, mock_event_bus):
        """create_agent() sets engagement_id on agent."""
        agent = router.create_agent(
            role=AgentRole.RECON,
            engagement_id="my-engagement",
            event_bus=mock_event_bus,
        )
        
        assert agent.engagement_id == "my-engagement"

    def test_create_agent_sets_event_bus(self, router, mock_event_bus):
        """create_agent() sets event_bus on agent."""
        agent = router.create_agent(
            role=AgentRole.EXPLOIT,
            engagement_id="eng-123",
            event_bus=mock_event_bus,
        )
        
        assert agent.event_bus is mock_event_bus


class TestDecisionContext:
    """Tests for NFR37 decision_context tracking."""

    @pytest.fixture
    def router(self):
        """Create a SwarmRouterWrapper instance."""
        from cyberred.orchestration.router import SwarmRouterWrapper
        return SwarmRouterWrapper()

    def test_route_task_returns_decision_context(self, router):
        """route_task() includes decision_context in result when requested."""
        role, decision_context = router.route_task(
            "scan the network",
            return_decision_context=True,
        )
        
        assert role == AgentRole.RECON
        assert "routing_rationale" in decision_context
        assert "matched_keyword" in decision_context

    def test_decision_context_includes_routing_rationale(self, router):
        """decision_context includes routing_rationale."""
        _, decision_context = router.route_task(
            "exploit vulnerability",
            return_decision_context=True,
        )
        
        assert "exploit" in decision_context["matched_keyword"].lower()
        assert decision_context["routing_rationale"] is not None

    def test_get_routing_log_returns_history(self, router):
        """get_routing_log() returns history of routing decisions."""
        router.route_task("scan network")
        router.route_task("exploit vuln")
        router.route_task("crack password")
        
        log = router.get_routing_log()
        
        assert len(log) == 3
        assert log[0]["role"] == AgentRole.RECON
        assert log[1]["role"] == AgentRole.EXPLOIT
        assert log[2]["role"] == AgentRole.CREDENTIAL


class TestInvalidRoleHandling:
    """Tests for invalid role error handling."""

    @pytest.fixture
    def router(self):
        """Create a SwarmRouterWrapper instance."""
        from cyberred.orchestration.router import SwarmRouterWrapper
        return SwarmRouterWrapper()

    @pytest.fixture
    def mock_event_bus(self):
        """Create a mock EventBus."""
        bus = MagicMock()
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        return bus

    def test_create_agent_invalid_role_raises_error(self, router, mock_event_bus):
        """create_agent() raises ValueError for invalid role."""
        with pytest.raises(ValueError, match="Invalid role"):
            router.create_agent(
                role="invalid_role",
                engagement_id="eng-123",
                event_bus=mock_event_bus,
            )

    def test_spawn_swarm_invalid_distribution_raises_error(self, router, mock_event_bus):
        """spawn_swarm() raises ValueError for invalid distribution."""
        invalid_dist = {"not_a_role": 1.0}
        
        with pytest.raises(ValueError, match="Invalid role"):
            router.spawn_swarm(
                count=5,
                engagement_id="eng-123",
                event_bus=mock_event_bus,
                distribution=invalid_dist,
            )

    def test_spawn_swarm_empty_distribution_raises_error(self, router, mock_event_bus):
        """spawn_swarm() raises ValueError for empty distribution."""
        with pytest.raises(ValueError, match="Distribution cannot be empty"):
            router.spawn_swarm(
                count=5,
                engagement_id="eng-123",
                event_bus=mock_event_bus,
                distribution={},
            )

    def test_spawn_swarm_zero_weight_distribution_raises_error(self, router, mock_event_bus):
        """spawn_swarm() raises ValueError for zero-weight distribution."""
        from cyberred.agents.roles import AgentRole
        zero_dist = {AgentRole.RECON: 0.0, AgentRole.EXPLOIT: 0.0}
        
        with pytest.raises(ValueError, match="weights must sum to a positive value"):
            router.spawn_swarm(
                count=5,
                engagement_id="eng-123",
                event_bus=mock_event_bus,
                distribution=zero_dist,
            )


class TestRoleKeywordsMapping:
    """Tests for ROLE_KEYWORDS constant."""

    def test_role_keywords_has_all_roles(self):
        """ROLE_KEYWORDS has keywords for all 8 roles."""
        from cyberred.orchestration.router import ROLE_KEYWORDS
        
        roles_in_mapping = set(ROLE_KEYWORDS.values())
        expected_roles = set(AgentRole)
        
        assert roles_in_mapping == expected_roles

    def test_role_keywords_are_lowercase(self):
        """All keywords in ROLE_KEYWORDS are lowercase."""
        from cyberred.orchestration.router import ROLE_KEYWORDS
        
        for keyword in ROLE_KEYWORDS.keys():
            assert keyword == keyword.lower(), f"Keyword '{keyword}' is not lowercase"


class TestRoleDistributionDefaults:
    """Tests for ROLE_DISTRIBUTION_DEFAULTS constant."""

    def test_distribution_has_all_roles(self):
        """ROLE_DISTRIBUTION_DEFAULTS has weights for all 8 roles."""
        from cyberred.orchestration.router import ROLE_DISTRIBUTION_DEFAULTS
        
        assert set(ROLE_DISTRIBUTION_DEFAULTS.keys()) == set(AgentRole)

    def test_distribution_sums_to_one(self):
        """ROLE_DISTRIBUTION_DEFAULTS weights sum to 1.0."""
        from cyberred.orchestration.router import ROLE_DISTRIBUTION_DEFAULTS
        
        total = sum(ROLE_DISTRIBUTION_DEFAULTS.values())
        assert abs(total - 1.0) < 0.001, f"Distribution sums to {total}, expected 1.0"

    def test_distribution_all_positive(self):
        """All weights in ROLE_DISTRIBUTION_DEFAULTS are positive."""
        from cyberred.orchestration.router import ROLE_DISTRIBUTION_DEFAULTS
        
        for role, weight in ROLE_DISTRIBUTION_DEFAULTS.items():
            assert weight > 0, f"Weight for {role} is not positive: {weight}"


class TestContextBasedRoutingDecisionContext:
    """Additional tests for context routing with decision_context."""

    @pytest.fixture
    def router(self):
        """Create a SwarmRouterWrapper instance."""
        from cyberred.orchestration.router import SwarmRouterWrapper
        return SwarmRouterWrapper()

    def test_webapp_context_with_decision_context(self, router):
        """route_task() returns decision_context for webapp context routing."""
        context = {"target_type": "web_application"}
        role, decision = router.route_task(
            "analyze target",
            context=context,
            return_decision_context=True,
        )
        assert role == AgentRole.WEBAPP
        assert "routing_rationale" in decision
        assert "web_application" in decision["routing_rationale"]

    def test_wireless_context_with_decision_context(self, router):
        """route_task() returns decision_context for wireless context routing."""
        context = {"target_type": "wireless_network"}
        role, decision = router.route_task(
            "analyze target",
            context=context,
            return_decision_context=True,
        )
        assert role == AgentRole.WIRELESS
        assert decision["matched_keyword"] is None

    def test_ad_context_with_decision_context(self, router):
        """route_task() returns decision_context for AD context routing."""
        context = {"target_type": "active_directory"}
        role, decision = router.route_task(
            "analyze target",
            context=context,
            return_decision_context=True,
        )
        assert role == AgentRole.AD

    def test_credential_finding_with_decision_context(self, router):
        """route_task() returns decision_context for credential finding routing."""
        context = {"finding_type": "credential"}
        role, decision = router.route_task(
            "process finding",
            context=context,
            return_decision_context=True,
        )
        assert role == AgentRole.CREDENTIAL
        assert "credential" in decision["routing_rationale"]

    def test_default_routing_with_decision_context(self, router):
        """route_task() returns decision_context for default routing."""
        role, decision = router.route_task(
            "do something unknown",
            return_decision_context=True,
        )
        assert role == AgentRole.RECON
        assert "defaulting to RECON" in decision["routing_rationale"]


class TestAsyncMethods:
    """Tests for async methods."""

    @pytest.fixture
    def router(self):
        """Create a SwarmRouterWrapper instance."""
        from cyberred.orchestration.router import SwarmRouterWrapper
        return SwarmRouterWrapper()

    @pytest.fixture
    def mock_event_bus(self):
        """Create a mock EventBus."""
        bus = MagicMock()
        bus.publish = AsyncMock()
        return bus

    @pytest.mark.asyncio
    async def test_route_task_async_without_audit_bus(self, router):
        """route_task_async() works without audit bus."""
        role = await router.route_task_async("scan network")
        assert role == AgentRole.RECON

    @pytest.mark.asyncio
    async def test_spawn_swarm_async_without_audit_bus(self, router, mock_event_bus):
        """spawn_swarm_async() works without audit bus configured."""
        agents = await router.spawn_swarm_async(
            count=2,
            engagement_id="test-eng",
            event_bus=mock_event_bus,
        )
        assert len(agents) == 2

    @pytest.mark.asyncio
    async def test_route_task_async_with_decision_context(self, router):
        """route_task_async() supports return_decision_context parameter."""
        role, decision_context = await router.route_task_async(
            "scan network",
            return_decision_context=True,
        )
        assert role == AgentRole.RECON
        assert "routing_rationale" in decision_context
        assert "matched_keyword" in decision_context

    @pytest.mark.asyncio
    async def test_route_task_async_with_audit_bus_and_decision_context(self, router, mock_event_bus):
        """route_task_async() publishes decision_context to audit bus."""
        router.set_audit_bus(mock_event_bus)
        
        role, decision_context = await router.route_task_async(
            "exploit vulnerability",
            return_decision_context=True,
        )
        
        assert role == AgentRole.EXPLOIT
        mock_event_bus.publish.assert_called_once()
        call_args = mock_event_bus.publish.call_args
        assert "decision_context" in call_args[0][1]


class TestSwarmRouterProperty:
    """Tests for swarm_router property and swarms integration."""

    @pytest.fixture
    def router(self):
        """Create a SwarmRouterWrapper instance."""
        from cyberred.orchestration.router import SwarmRouterWrapper
        return SwarmRouterWrapper()

    def test_swarm_router_lazy_initialized(self, router):
        """swarm_router property is lazy-initialized."""
        # Before access, internal _swarm_router is None
        assert router._swarm_router is None
        
        # Access the property
        sr = router.swarm_router
        
        # After access, internal _swarm_router is set
        assert router._swarm_router is not None
        assert sr is router._swarm_router

    def test_swarm_router_returns_same_instance(self, router):
        """swarm_router property returns same instance on multiple accesses."""
        sr1 = router.swarm_router
        sr2 = router.swarm_router
        assert sr1 is sr2

    def test_swarm_router_uses_swarm_type(self):
        """swarm_router uses configured swarm_type."""
        from cyberred.orchestration.router import SwarmRouterWrapper
        
        router = SwarmRouterWrapper(swarm_type="ConcurrentWorkflow")
        sr = router.swarm_router
        
        assert router.swarm_type == "ConcurrentWorkflow"
        # SwarmRouter stores swarm_type
        assert sr.swarm_type == "ConcurrentWorkflow"

    def test_swarm_type_literal_validation(self):
        """SwarmType accepts valid swarm types."""
        from cyberred.orchestration.router import SwarmRouterWrapper
        
        # Valid types should work
        valid_types = ["SequentialWorkflow", "ConcurrentWorkflow", "MixtureOfAgents"]
        for swarm_type in valid_types:
            router = SwarmRouterWrapper(swarm_type=swarm_type)
            assert router.swarm_type == swarm_type
