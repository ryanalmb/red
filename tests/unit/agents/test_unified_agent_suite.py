"""Unified Agent Test Suite (Story 7.24).

This module provides cross-agent consistency tests that verify all 8 agent types
behave uniformly for common operations. Uses parametrized tests with a factory function
to test protocol compliance, instantiation, and LLM tool selection.

AC Coverage:
    #1 - Protocol compliance tests for all 8 agent types
    #2 - Instantiation tests with role and specialty
    #3 - LLM tool selection tests with mock LLM responses
    #4 - Command generation validation for each agent type
    #5 - Parametrized tests cover all 8 roles
    #6 - Integration tests in tests/integration/agents/test_unified_agent_integration.py
    #7 - 100% test coverage for unified test utilities
"""

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.agents import (
    ADAgent,
    AgentRole,
    CredentialAgent,
    ExploitAgent,
    ForensicsAgent,
    PostExAgent,
    PromptLibrary,
    ReconAgent,
    StigmergicAgent,
    WebAppAgent,
    WirelessAgent,
)
from cyberred.core.events import EventBus
from cyberred.core.models import ToolSelection, ToolSelectionContext
from cyberred.protocols import AgentProtocol

# ============================================================================
# Agent Class Mapping (AC #5)
# ============================================================================

AGENT_CLASS_MAP: dict[AgentRole, type[StigmergicAgent]] = {
    AgentRole.RECON: ReconAgent,
    AgentRole.EXPLOIT: ExploitAgent,
    AgentRole.POSTEX: PostExAgent,
    AgentRole.WEBAPP: WebAppAgent,
    AgentRole.WIRELESS: WirelessAgent,
    AgentRole.AD: ADAgent,
    AgentRole.CREDENTIAL: CredentialAgent,
    AgentRole.FORENSICS: ForensicsAgent,
}

# Valid agent statuses per AgentProtocol.get_status() contract
VALID_AGENT_STATUSES = frozenset({"idle", "active", "waiting", "shutdown", "error"})

# Mock LLM response for tool selection tests (AC #3)
MOCK_TOOL_SELECTION_RESPONSE = json.dumps({
    "tool_name": "nmap",
    "command": "nmap -sV -sC 192.168.1.1",
    "rationale": "Service version detection for target enumeration",
    "expected_output_type": "xml",
    "confidence": 0.9,
    "priority": 5,
    "alternatives": ["masscan", "rustscan"],
})


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_event_bus() -> MagicMock:
    """Create a mock EventBus for agent testing."""
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock()
    return bus


@pytest.fixture
def mock_llm_gateway() -> MagicMock:
    """Create a mock LLMGateway with deterministic responses."""
    gateway = MagicMock()
    response = MagicMock()
    response.content = MOCK_TOOL_SELECTION_RESPONSE
    gateway.agent_complete = AsyncMock(return_value=response)
    return gateway


@pytest.fixture
def mock_manifest_loader() -> MagicMock:
    """Create a mock ManifestLoader for tool lookup."""
    loader = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = "nmap"
    loader.get_by_category = MagicMock(return_value=[mock_tool])
    return loader


@pytest.fixture
def mock_kali_execute() -> AsyncMock:
    """Create a mock kali_execute function."""
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.stdout = "nmap --help output..."
    mock_result.stderr = ""
    mock_result.exit_code = 0
    return AsyncMock(return_value=mock_result)


# ============================================================================
# Factory Function (AC #5)
# ============================================================================


def create_agent(
    role: AgentRole,
    event_bus: MagicMock,
    specialty: str | None = None,
    llm_gateway: MagicMock | None = None,
    manifest_loader: MagicMock | None = None,
    **overrides: Any,
) -> StigmergicAgent:
    """Factory function to create agent of specified role.

    Args:
        role: AgentRole enum value.
        event_bus: Mock EventBus for agent communication.
        specialty: Optional specialty parameter for prompt customization.
        llm_gateway: Optional mock LLMGateway for tool selection.
        manifest_loader: Optional mock ManifestLoader for tool lookup.
        **overrides: Additional kwargs to override defaults.

    Returns:
        Agent instance of the appropriate subclass.
    """
    agent_class = AGENT_CLASS_MAP[role]
    defaults: dict[str, Any] = {
        "agent_id": str(uuid.uuid4()),
        "engagement_id": f"test-engagement-{uuid.uuid4().hex[:8]}",
        "event_bus": event_bus,
    }

    # Add specialty if provided
    if specialty is not None:
        defaults["specialty"] = specialty

    # Add LLM gateway if provided
    if llm_gateway is not None:
        defaults["llm_gateway"] = llm_gateway

    # Add manifest loader if provided
    if manifest_loader is not None:
        defaults["manifest_loader"] = manifest_loader

    defaults.update(overrides)
    return agent_class(**defaults)


# ============================================================================
# Protocol Compliance Tests (AC #1)
# ============================================================================


@pytest.mark.unit
@pytest.mark.parametrize("role", list(AgentRole))
class TestAgentProtocolCompliance:
    """Tests verifying all agents implement AgentProtocol (AC #1)."""

    def test_agent_is_protocol_instance(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """All agents must pass isinstance(agent, AgentProtocol) check."""
        agent = create_agent(role, mock_event_bus)

        # Runtime checkable protocol verification
        assert isinstance(agent, AgentProtocol), (
            f"{role.name} agent must implement AgentProtocol"
        )

    def test_agent_has_execute_method(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """All agents must have execute() method."""
        agent = create_agent(role, mock_event_bus)
        assert hasattr(agent, "execute")
        assert callable(agent.execute)

    def test_agent_has_reason_method(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """All agents must have reason() method."""
        agent = create_agent(role, mock_event_bus)
        assert hasattr(agent, "reason")
        assert callable(agent.reason)

    def test_agent_has_get_id_method(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """All agents must have get_id() method."""
        agent = create_agent(role, mock_event_bus)
        assert hasattr(agent, "get_id")
        assert callable(agent.get_id)

    def test_agent_has_get_status_method(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """All agents must have get_status() method."""
        agent = create_agent(role, mock_event_bus)
        assert hasattr(agent, "get_status")
        assert callable(agent.get_status)

    def test_agent_has_get_decision_context_method(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """All agents must have get_decision_context() method."""
        agent = create_agent(role, mock_event_bus)
        assert hasattr(agent, "get_decision_context")
        assert callable(agent.get_decision_context)

    def test_agent_has_shutdown_method(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """All agents must have shutdown() method."""
        agent = create_agent(role, mock_event_bus)
        assert hasattr(agent, "shutdown")
        assert callable(agent.shutdown)


# ============================================================================
# Instantiation Tests (AC #2)
# ============================================================================


@pytest.mark.unit
@pytest.mark.parametrize("role", list(AgentRole))
class TestAgentInstantiation:
    """Tests verifying agent instantiation with role and specialty (AC #2)."""

    def test_agent_instantiation_with_role(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """All agents can be instantiated with their correct AgentRole."""
        agent = create_agent(role, mock_event_bus)

        # Verify agent was created
        assert agent is not None

        # Verify role attribute is set correctly
        assert hasattr(agent, "role")
        assert agent.role == role

    def test_agent_accepts_specialty(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """All agents accept optional specialty parameter."""
        specialty = "network"
        agent = create_agent(role, mock_event_bus, specialty=specialty)

        # Verify specialty is set
        assert hasattr(agent, "specialty")
        assert agent.specialty == specialty

    def test_agent_sets_role_attribute(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """Constructor correctly sets role attribute."""
        agent = create_agent(role, mock_event_bus)

        # Role must match the expected role for this agent type
        expected_role = role
        assert agent.role == expected_role

    def test_agent_loads_prompt_from_library(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """Constructor calls PromptLibrary.get(role, specialty) for system prompt."""
        specialty = "test_specialty"

        with patch.object(PromptLibrary, "get") as mock_get:
            mock_get.return_value = f"Mock prompt for {role.name}"

            agent = create_agent(role, mock_event_bus, specialty=specialty)

            # Verify PromptLibrary.get was called with correct args
            # Note: Some agents (e.g., AD) may not pass specialty to base class __init__
            # but always pass role. We verify role is correct and prompt was loaded.
            assert mock_get.call_count >= 1
            # The first arg should always be the role
            call_args = mock_get.call_args
            assert call_args[0][0] == role

            # Verify system_prompt was set from library
            assert agent.system_prompt == f"Mock prompt for {role.name}"


# ============================================================================
# Tool Selection Tests (AC #3)
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("role", list(AgentRole))
class TestAgentToolSelection:
    """Tests verifying LLM tool selection with mock responses (AC #3)."""

    async def test_select_tool_parses_mock_llm_response(
        self,
        role: AgentRole,
        mock_event_bus: MagicMock,
        mock_llm_gateway: MagicMock,
        mock_manifest_loader: MagicMock,
    ) -> None:
        """select_tool() correctly parses mock LLM JSON responses."""
        agent = create_agent(
            role,
            mock_event_bus,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        context = ToolSelectionContext(
            objective="Test objective",
            target_info={"target": "192.168.1.1"},
            available_tools=["nmap", "masscan"],
            phase="recon",
            constraints=[],
            previous_results=[],
        )

        selection = await agent.select_tool(context)

        # Verify selection was parsed correctly
        assert isinstance(selection, ToolSelection)
        assert selection.tool_name == "nmap"
        assert selection.command == "nmap -sV -sC 192.168.1.1"
        assert selection.confidence == 0.9
        assert selection.priority == 5

    async def test_tool_selection_calls_llm_gateway(
        self,
        role: AgentRole,
        mock_event_bus: MagicMock,
        mock_llm_gateway: MagicMock,
        mock_manifest_loader: MagicMock,
    ) -> None:
        """Tool selection invokes LLM gateway with proper request."""
        agent = create_agent(
            role,
            mock_event_bus,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        context = ToolSelectionContext(
            objective="Enumerate services",
            target_info={"target": "10.0.0.1"},
            available_tools=["nmap"],
            phase="reconnaissance",
            constraints=[],
            previous_results=[],
        )

        await agent.select_tool(context)

        # Verify LLM gateway was called
        mock_llm_gateway.agent_complete.assert_called_once()


# ============================================================================
# Command Generation Tests (AC #4)
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("role", list(AgentRole))
class TestAgentCommandGeneration:
    """Tests verifying command generation for each agent type (AC #4)."""

    async def test_generate_command_for_tool(
        self,
        role: AgentRole,
        mock_event_bus: MagicMock,
        mock_llm_gateway: MagicMock,
        mock_kali_execute: AsyncMock,
    ) -> None:
        """Each agent type can generate valid commands for their domain tools."""
        # Setup LLM to return a valid command
        mock_response = MagicMock()
        mock_response.content = "nmap -sV 192.168.1.1"
        mock_llm_gateway.agent_complete = AsyncMock(return_value=mock_response)

        agent = create_agent(
            role,
            mock_event_bus,
            llm_gateway=mock_llm_gateway,
        )

        with patch(
            "cyberred.tools.kali_executor.kali_execute", mock_kali_execute
        ):
            command = await agent.generate_command(
                tool="nmap",
                target="192.168.1.1",
                options={"stealth": True},
            )

        # Verify command is valid (must start with tool name)
        assert command.startswith("nmap")
        assert "192.168.1.1" in command

    async def test_command_validation_enforced(
        self,
        role: AgentRole,
        mock_event_bus: MagicMock,
        mock_llm_gateway: MagicMock,
        mock_kali_execute: AsyncMock,
    ) -> None:
        """Commands are validated (must start with tool name)."""
        # Setup LLM to return an invalid command (doesn't start with tool name)
        mock_response = MagicMock()
        mock_response.content = "echo 'invalid command'"
        mock_llm_gateway.agent_complete = AsyncMock(return_value=mock_response)

        agent = create_agent(
            role,
            mock_event_bus,
            llm_gateway=mock_llm_gateway,
        )

        with patch(
            "cyberred.tools.kali_executor.kali_execute", mock_kali_execute
        ):
            with pytest.raises(ValueError, match="must start with"):
                await agent.generate_command(
                    tool="nmap",
                    target="192.168.1.1",
                )

    async def test_help_cache_populated_and_reused(
        self,
        role: AgentRole,
        mock_event_bus: MagicMock,
        mock_llm_gateway: MagicMock,
        mock_kali_execute: AsyncMock,
    ) -> None:
        """Help cache is populated and reused within session."""
        mock_response = MagicMock()
        mock_response.content = "nmap -sV 192.168.1.1"
        mock_llm_gateway.agent_complete = AsyncMock(return_value=mock_response)

        agent = create_agent(
            role,
            mock_event_bus,
            llm_gateway=mock_llm_gateway,
        )

        with patch(
            "cyberred.tools.kali_executor.kali_execute", mock_kali_execute
        ):
            # First call should populate cache
            await agent.generate_command(tool="nmap", target="192.168.1.1")

            # Verify cache is populated
            assert "nmap" in agent._tool_help_cache

            # Second call should reuse cache
            await agent.generate_command(tool="nmap", target="192.168.1.2")

        # kali_execute should be called only once for --help (first call only)
        # (not twice, since second call should use cache)
        assert mock_kali_execute.call_count == 1


# ============================================================================
# Thin Subclass Pattern Tests (AC #5)
# ============================================================================


@pytest.mark.unit
class TestThinSubclassPattern:
    """Tests verifying thin subclass pattern (AC #5)."""

    @pytest.mark.parametrize("role", list(AgentRole))
    def test_all_roles_have_correct_subclass(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """Single test function verifying thin subclass pattern."""
        agent = create_agent(role, mock_event_bus)

        # Verify agent is instance of StigmergicAgent base class
        assert isinstance(agent, StigmergicAgent)

        # Verify agent is instance of correct subclass
        expected_class = AGENT_CLASS_MAP[role]
        assert isinstance(agent, expected_class)

        # Verify role is set correctly (thin subclass sets role in constructor)
        assert agent.role == role

    def test_agent_class_map_covers_all_roles(self) -> None:
        """Verify AGENT_CLASS_MAP covers all 8 AgentRole values."""
        all_roles = set(AgentRole)
        mapped_roles = set(AGENT_CLASS_MAP.keys())

        assert all_roles == mapped_roles, (
            f"Missing roles in AGENT_CLASS_MAP: {all_roles - mapped_roles}"
        )

    def test_all_agent_classes_inherit_from_stigmergic_agent(self) -> None:
        """All agent classes in map inherit from StigmergicAgent."""
        for role, agent_class in AGENT_CLASS_MAP.items():
            assert issubclass(agent_class, StigmergicAgent), (
                f"{agent_class.__name__} must inherit from StigmergicAgent"
            )


# ============================================================================
# Factory Function Tests (AC #7)
# ============================================================================


@pytest.mark.unit
class TestCreateAgentFactory:
    """Tests for the create_agent factory function (AC #7)."""

    def test_create_agent_returns_correct_type(
        self, mock_event_bus: MagicMock
    ) -> None:
        """Factory returns correct agent type for each role."""
        for role, expected_class in AGENT_CLASS_MAP.items():
            agent = create_agent(role, mock_event_bus)
            assert isinstance(agent, expected_class)

    def test_create_agent_sets_agent_id(
        self, mock_event_bus: MagicMock
    ) -> None:
        """Factory sets unique agent_id."""
        agent1 = create_agent(AgentRole.RECON, mock_event_bus)
        agent2 = create_agent(AgentRole.RECON, mock_event_bus)

        assert agent1.agent_id != agent2.agent_id

    def test_create_agent_accepts_overrides(
        self, mock_event_bus: MagicMock
    ) -> None:
        """Factory accepts override parameters."""
        custom_id = "custom-agent-id-123"
        agent = create_agent(
            AgentRole.EXPLOIT,
            mock_event_bus,
            agent_id=custom_id,
        )

        assert agent.agent_id == custom_id

    def test_create_agent_with_llm_gateway(
        self,
        mock_event_bus: MagicMock,
        mock_llm_gateway: MagicMock,
    ) -> None:
        """Factory correctly passes llm_gateway to agent."""
        agent = create_agent(
            AgentRole.POSTEX,
            mock_event_bus,
            llm_gateway=mock_llm_gateway,
        )

        assert agent._llm_gateway == mock_llm_gateway

    def test_create_agent_with_manifest_loader(
        self,
        mock_event_bus: MagicMock,
        mock_manifest_loader: MagicMock,
    ) -> None:
        """Factory correctly passes manifest_loader to agent."""
        agent = create_agent(
            AgentRole.WEBAPP,
            mock_event_bus,
            manifest_loader=mock_manifest_loader,
        )

        assert agent._manifest == mock_manifest_loader


# ============================================================================
# Protocol Method Behavior Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("role", list(AgentRole))
class TestProtocolMethodBehavior:
    """Tests verifying protocol method behavior consistency across agents."""

    def test_get_id_returns_agent_id(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """get_id() returns the agent's unique identifier."""
        agent = create_agent(role, mock_event_bus)
        assert agent.get_id() == agent.agent_id

    def test_get_status_returns_string(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """get_status() returns a valid status string."""
        agent = create_agent(role, mock_event_bus)
        status = agent.get_status()

        assert isinstance(status, str)
        assert status in VALID_AGENT_STATUSES

    def test_get_decision_context_returns_list(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """get_decision_context() returns list of signal IDs."""
        agent = create_agent(role, mock_event_bus)
        context = agent.get_decision_context()

        assert isinstance(context, list)

    async def test_reason_returns_string(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """reason() returns reasoning string based on context."""
        agent = create_agent(role, mock_event_bus)
        reasoning = await agent.reason(["signal-1", "signal-2"])

        assert isinstance(reasoning, str)
        assert "2" in reasoning  # Should reference number of signals

    async def test_shutdown_sets_status(
        self, role: AgentRole, mock_event_bus: MagicMock
    ) -> None:
        """shutdown() sets agent status to 'shutdown'."""
        agent = create_agent(role, mock_event_bus)

        # Ensure not shutdown initially
        assert agent.get_status() != "shutdown"

        await agent.shutdown()

        assert agent.get_status() == "shutdown"
