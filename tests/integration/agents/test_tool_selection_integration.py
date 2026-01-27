"""Integration tests for LLM-driven tool selection (Story 7.1-v2).

These tests validate the complete tool selection flow using real
Redis containers and mock LLM responses.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from testcontainers.redis import RedisContainer

from cyberred.agents.base import StigmergicAgent
from cyberred.agents.roles import AgentRole
from cyberred.core.config import RedisConfig
from cyberred.core.events import EventBus
from cyberred.core.exceptions import ToolSelectionError
from cyberred.core.models import ToolSelection, ToolSelectionContext
from cyberred.storage.redis_client import RedisClient


@pytest.fixture(scope="module")
def redis_container():
    """Spin up a Redis container for integration tests."""
    with RedisContainer("redis:7.2-alpine") as redis:
        yield redis


@pytest.fixture
async def redis_client(redis_container):
    """Provide a connected RedisClient."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)

    config = RedisConfig(host=host, port=int(port))
    client = RedisClient(config, engagement_id="tool-selection-test")
    await client.connect()
    yield client
    await client.close()


@pytest.fixture
def event_bus(redis_client):
    """Provide an EventBus connected to Redis."""
    return EventBus(redis_client)


@pytest.fixture
def mock_llm_gateway():
    """Create a mock LLM gateway that returns valid tool selections."""
    gateway = MagicMock()
    gateway.queue_depth = 0

    async def mock_agent_complete(request):
        response = MagicMock()
        response.content = json.dumps({
            "tool_name": "nmap",
            "command": "nmap -sV -sC 192.168.1.1",
            "rationale": "Port scanning is the first step in reconnaissance",
            "expected_output_type": "xml",
            "confidence": 0.95,
            "priority": 8,
            "alternatives": ["masscan", "rustscan"]
        })
        return response

    gateway.agent_complete = mock_agent_complete
    return gateway


@pytest.fixture
def mock_manifest_loader():
    """Create a mock manifest loader with sample tools."""
    loader = MagicMock()

    class MockTool:
        def __init__(self, name):
            self.name = name

    def get_by_category(category):
        tools_by_category = {
            "recon": [MockTool("nmap"), MockTool("masscan"), MockTool("rustscan")],
            "discovery": [MockTool("subfinder"), MockTool("amass")],
            "enumeration": [MockTool("gobuster"), MockTool("ffuf")],
            "exploit": [MockTool("sqlmap"), MockTool("nuclei")],
            "web": [MockTool("nikto"), MockTool("whatweb")],
        }
        return tools_by_category.get(category, [])

    loader.get_by_category = get_by_category
    return loader


@pytest.mark.integration
@pytest.mark.asyncio
async def test_select_tool_with_llm_gateway(event_bus, mock_llm_gateway, mock_manifest_loader):
    """Test tool selection with a mocked LLM gateway returns valid ToolSelection."""
    agent = StigmergicAgent(
        agent_name="Recon Agent",
        agent_id="recon-1",
        engagement_id="eng-1",
        event_bus=event_bus,
        role=AgentRole.RECON,
        llm_gateway=mock_llm_gateway,
        manifest_loader=mock_manifest_loader,
        llm=MagicMock()
    )
    await agent.spawn()

    context = ToolSelectionContext(
        objective="Discover open ports on target",
        target_info={"ip": "192.168.1.1", "hostname": "target.local"},
        available_tools=["nmap", "masscan", "rustscan"],
        phase="recon",
        constraints=["stealth"],
        previous_results=[]
    )

    selection = await agent.select_tool(context)

    assert isinstance(selection, ToolSelection)
    assert selection.tool_name == "nmap"
    assert selection.command == "nmap -sV -sC 192.168.1.1"
    assert selection.rationale == "Port scanning is the first step in reconnaissance"
    assert selection.expected_output_type == "xml"
    assert selection.confidence == 0.95
    assert selection.priority == 8
    assert "masscan" in selection.alternatives

    # Verify decision_context tracking (NFR37)
    assert selection.selection_id in agent.get_decision_context()

    await agent.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_select_tool_populates_available_tools_from_manifest(
    event_bus, mock_llm_gateway, mock_manifest_loader
):
    """Test that select_tool populates available_tools from manifest when not provided."""
    agent = StigmergicAgent(
        agent_name="Recon Agent",
        agent_id="recon-2",
        engagement_id="eng-1",
        event_bus=event_bus,
        role=AgentRole.RECON,
        llm_gateway=mock_llm_gateway,
        manifest_loader=mock_manifest_loader,
        llm=MagicMock()
    )
    await agent.spawn()

    # Context without available_tools - should be populated from manifest
    context = ToolSelectionContext(
        objective="Enumerate services",
        target_info={"ip": "10.0.0.1"},
        available_tools=[],  # Empty - should be populated
        phase="recon",
    )

    selection = await agent.select_tool(context)

    assert isinstance(selection, ToolSelection)
    assert selection.tool_name == "nmap"

    await agent.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_select_tool_without_llm_gateway_raises_error(event_bus):
    """Test that select_tool raises ToolSelectionError when no LLM gateway configured."""
    agent = StigmergicAgent(
        agent_name="No LLM Agent",
        agent_id="no-llm-1",
        engagement_id="eng-1",
        event_bus=event_bus,
        role=AgentRole.RECON,
        llm_gateway=None,  # No gateway
        llm=MagicMock()
    )
    await agent.spawn()

    context = ToolSelectionContext(
        objective="Test objective",
        target_info={"ip": "192.168.1.1"},
        available_tools=["nmap"],
        phase="recon",
    )

    with pytest.raises(ToolSelectionError) as exc_info:
        await agent.select_tool(context)

    assert "No LLM gateway configured" in str(exc_info.value)

    await agent.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_select_tool_with_invalid_llm_response(event_bus, mock_manifest_loader):
    """Test that select_tool raises ToolSelectionError on invalid LLM response."""
    gateway = MagicMock()
    gateway.queue_depth = 0

    async def mock_invalid_response(request):
        response = MagicMock()
        response.content = "This is not valid JSON"
        return response

    gateway.agent_complete = mock_invalid_response

    agent = StigmergicAgent(
        agent_name="Bad Response Agent",
        agent_id="bad-resp-1",
        engagement_id="eng-1",
        event_bus=event_bus,
        role=AgentRole.RECON,
        llm_gateway=gateway,
        manifest_loader=mock_manifest_loader,
        llm=MagicMock()
    )
    await agent.spawn()

    context = ToolSelectionContext(
        objective="Test objective",
        target_info={"ip": "192.168.1.1"},
        available_tools=["nmap"],
        phase="recon",
    )

    with pytest.raises(ToolSelectionError) as exc_info:
        await agent.select_tool(context)

    assert "Failed to parse LLM response" in str(exc_info.value)

    await agent.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_command_with_llm_gateway(event_bus, mock_llm_gateway):
    """Test command generation using LLM gateway."""
    # Mock the agent_complete to return a command
    async def mock_command_response(request):
        response = MagicMock()
        response.content = "nmap -sV -sC -oX output.xml 192.168.1.1"
        return response

    mock_llm_gateway.agent_complete = mock_command_response

    agent = StigmergicAgent(
        agent_name="Command Gen Agent",
        agent_id="cmd-gen-1",
        engagement_id="eng-1",
        event_bus=event_bus,
        role=AgentRole.RECON,
        llm_gateway=mock_llm_gateway,
        llm=MagicMock()
    )
    await agent.spawn()

    # Mock _get_tool_help to avoid actual execution
    agent._tool_help_cache["nmap"] = "nmap [options] target"

    command = await agent.generate_command(
        tool="nmap",
        target="192.168.1.1",
        options={"output_format": "xml"}
    )

    assert command.startswith("nmap")
    assert "192.168.1.1" in command

    await agent.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_command_fallback_without_gateway(event_bus):
    """Test command generation fallback when no LLM gateway configured."""
    agent = StigmergicAgent(
        agent_name="Fallback Agent",
        agent_id="fallback-1",
        engagement_id="eng-1",
        event_bus=event_bus,
        role=AgentRole.RECON,
        llm_gateway=None,
        llm=MagicMock()
    )
    await agent.spawn()

    # Mock _get_tool_help to avoid actual execution
    agent._tool_help_cache["nmap"] = "nmap [options] target"

    command = await agent.generate_command(
        tool="nmap",
        target="192.168.1.1"
    )

    # Fallback should return simple command
    assert command == "nmap 192.168.1.1"

    await agent.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tool_selection_with_previous_results(event_bus, mock_manifest_loader):
    """Test tool selection considers previous results in context."""
    gateway = MagicMock()
    gateway.queue_depth = 0

    # Track the prompt sent to LLM
    received_prompts = []

    async def mock_capture_prompt(request):
        received_prompts.append(request.prompt)
        response = MagicMock()
        response.content = json.dumps({
            "tool_name": "nuclei",
            "command": "nuclei -u http://192.168.1.1 -t cves/",
            "rationale": "Based on nmap results showing web server, scan for CVEs",
            "expected_output_type": "json",
            "confidence": 0.9,
            "priority": 7,
            "alternatives": ["nikto"]
        })
        return response

    gateway.agent_complete = mock_capture_prompt

    agent = StigmergicAgent(
        agent_name="Context Agent",
        agent_id="context-1",
        engagement_id="eng-1",
        event_bus=event_bus,
        role=AgentRole.EXPLOIT,
        llm_gateway=gateway,
        manifest_loader=mock_manifest_loader,
        llm=MagicMock()
    )
    await agent.spawn()

    context = ToolSelectionContext(
        objective="Find vulnerabilities in web server",
        target_info={"ip": "192.168.1.1", "ports": [80, 443]},
        available_tools=["nuclei", "nikto", "sqlmap"],
        phase="exploit",
        constraints=["no-dos"],
        previous_results=[
            {"tool": "nmap", "ports": [80, 443], "services": ["http", "https"]}
        ]
    )

    selection = await agent.select_tool(context)

    # Verify previous_results was included in the prompt
    assert len(received_prompts) == 1
    assert "Previous Results" in received_prompts[0]
    assert "nmap" in received_prompts[0]

    assert selection.tool_name == "nuclei"

    await agent.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_role_categories_affect_tool_selection(event_bus, mock_manifest_loader):
    """Test that different roles get different tool categories."""
    gateway = MagicMock()
    gateway.queue_depth = 0

    captured_contexts = []

    async def mock_capture_context(request):
        captured_contexts.append(request.prompt)
        response = MagicMock()
        response.content = json.dumps({
            "tool_name": "test_tool",
            "command": "test_tool target",
            "rationale": "test",
            "expected_output_type": "text",
            "confidence": 0.8,
            "priority": 5,
            "alternatives": []
        })
        return response

    gateway.agent_complete = mock_capture_context

    # Test RECON role
    recon_agent = StigmergicAgent(
        agent_name="Recon",
        agent_id="recon-role-1",
        engagement_id="eng-1",
        event_bus=event_bus,
        role=AgentRole.RECON,
        llm_gateway=gateway,
        manifest_loader=mock_manifest_loader,
        llm=MagicMock()
    )
    await recon_agent.spawn()

    context = ToolSelectionContext(
        objective="Test",
        target_info={"ip": "1.1.1.1"},
        available_tools=[],  # Will be populated from manifest
        phase="recon",
    )

    await recon_agent.select_tool(context)
    await recon_agent.shutdown()

    # Verify recon tools were included (nmap, masscan from recon category)
    recon_prompt = captured_contexts[0]
    assert "nmap" in recon_prompt or "masscan" in recon_prompt

    # Test EXPLOIT role
    captured_contexts.clear()

    exploit_agent = StigmergicAgent(
        agent_name="Exploit",
        agent_id="exploit-role-1",
        engagement_id="eng-1",
        event_bus=event_bus,
        role=AgentRole.EXPLOIT,
        llm_gateway=gateway,
        manifest_loader=mock_manifest_loader,
        llm=MagicMock()
    )
    await exploit_agent.spawn()

    context = ToolSelectionContext(
        objective="Test",
        target_info={"ip": "1.1.1.1"},
        available_tools=[],
        phase="exploit",
    )

    await exploit_agent.select_tool(context)
    await exploit_agent.shutdown()

    # Verify exploit tools were included (sqlmap, nuclei from exploit category)
    exploit_prompt = captured_contexts[0]
    assert "sqlmap" in exploit_prompt or "nuclei" in exploit_prompt
