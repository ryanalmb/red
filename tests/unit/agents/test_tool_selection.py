"""Unit tests for StigmergicAgent LLM tool selection methods.

Tests written FIRST as part of TDD RED phase for Story 7.1.v2.
These tests must FAIL until methods are implemented.

Covers:
- select_tool()
- generate_command()
- _get_tool_help()
- _build_tool_selection_prompt()
- _parse_tool_selection()
"""

import asyncio
import uuid
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

import pytest

from cyberred.core.events import EventBus


@pytest.fixture
def mock_event_bus():
    """Create mock EventBus for agent tests."""
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock()
    return bus


@pytest.fixture
def mock_llm_gateway():
    """Create mock LLMGateway for tool selection tests."""
    gateway = MagicMock()
    gateway.complete = AsyncMock()
    gateway.agent_complete = AsyncMock()
    return gateway


@pytest.fixture
def mock_manifest_loader():
    """Create mock ManifestLoader for tool selection tests."""
    loader = MagicMock()
    loader.get_by_category = MagicMock(return_value=[])
    loader.get_all_categories = MagicMock(return_value=["recon", "exploit", "postex"])
    loader.load = MagicMock(return_value=[])
    return loader


@pytest.mark.unit
class TestSelectTool:
    """Tests for select_tool() method."""

    @pytest.mark.asyncio
    async def test_select_tool_returns_tool_selection(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """select_tool returns ToolSelection dataclass."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole
        from cyberred.core.models import ToolSelectionContext, ToolSelection

        # Setup mock LLM response with new field names
        mock_llm_gateway.agent_complete.return_value = MagicMock(
            content='{"tool_name": "nmap", "command": "nmap -sV 192.168.1.0/24", "rationale": "Port scanning", "expected_output_type": "xml", "confidence": 0.9, "priority": 8, "alternatives": []}'
        )

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        context = ToolSelectionContext(
            objective="Scan for open ports",
            target_info={"network": "192.168.1.0/24"},
            available_tools=["nmap", "masscan"],
            phase="recon",
        )

        result = await agent.select_tool(context)

        assert isinstance(result, ToolSelection)
        assert result.tool_name == "nmap"
        assert result.command == "nmap -sV 192.168.1.0/24"
        assert result.rationale == "Port scanning"

    @pytest.mark.asyncio
    async def test_select_tool_queries_llm_with_context(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """LLM receives context in prompt."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole
        from cyberred.core.models import ToolSelectionContext

        mock_llm_gateway.agent_complete.return_value = MagicMock(
            content='{"tool_name": "nmap", "command": "nmap -sV 10.0.0.1", "rationale": "test", "expected_output_type": "xml", "confidence": 0.9, "priority": 5, "alternatives": []}'
        )

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        context = ToolSelectionContext(
            objective="Find vulnerabilities",
            target_info={"ip": "10.0.0.1", "os": "linux"},
            available_tools=["nmap", "nuclei"],
            phase="recon",
        )

        await agent.select_tool(context)

        # Verify LLM was called
        mock_llm_gateway.agent_complete.assert_called_once()
        
        # Check that context info appears in prompt
        call_args = mock_llm_gateway.agent_complete.call_args
        request = call_args[0][0]
        assert "10.0.0.1" in request.prompt or "10.0.0.1" in str(call_args)

    @pytest.mark.asyncio
    async def test_select_tool_uses_role_system_prompt(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """LLM call uses agent's role-specific system prompt."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole
        from cyberred.core.models import ToolSelectionContext

        mock_llm_gateway.agent_complete.return_value = MagicMock(
            content='{"tool_name": "sqlmap", "command": "sqlmap -u http://webapp.local/page?id=1", "rationale": "test", "expected_output_type": "text", "confidence": 0.9, "priority": 7, "alternatives": []}'
        )

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.EXPLOIT,
            specialty="web",
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        context = ToolSelectionContext(
            objective="Exploit web vulnerability",
            target_info={"hostname": "webapp.local"},
            available_tools=["sqlmap", "nuclei"],
            phase="exploit",
        )

        await agent.select_tool(context)

        # Verify LLM was called with system prompt
        call_args = mock_llm_gateway.agent_complete.call_args
        request = call_args[0][0]
        # System prompt should be set (from PromptLibrary)
        assert hasattr(request, 'system_prompt') or 'system' in str(call_args).lower()

    @pytest.mark.asyncio
    async def test_select_tool_tracks_decision_context(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """selection_id added to _decision_context (NFR37)."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole
        from cyberred.core.models import ToolSelectionContext

        mock_llm_gateway.agent_complete.return_value = MagicMock(
            content='{"tool_name": "nuclei", "command": "nuclei -u http://target.com", "rationale": "test", "expected_output_type": "json", "confidence": 0.85, "priority": 6, "alternatives": []}'
        )

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.EXPLOIT,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        context = ToolSelectionContext(
            objective="Find vulns",
            target_info={"hostname": "target.com"},
            available_tools=["nuclei", "nikto"],
            phase="exploit",
        )

        result = await agent.select_tool(context)

        # selection_id should be in decision_context
        assert result.selection_id in agent.get_decision_context()

    @pytest.mark.asyncio
    async def test_select_tool_logs_selection(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """Tool selection is logged with structlog."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole
        from cyberred.core.models import ToolSelectionContext

        mock_llm_gateway.agent_complete.return_value = MagicMock(
            content='{"tool_name": "nmap", "command": "nmap -sV 10.0.0.0/8", "rationale": "test", "expected_output_type": "xml", "confidence": 0.9, "priority": 5, "alternatives": []}'
        )

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        context = ToolSelectionContext(
            objective="Network scan",
            target_info={"network": "10.0.0.0/8"},
            available_tools=["nmap", "masscan"],
            phase="recon",
        )

        with patch.object(agent, '_log') as mock_log:
            await agent.select_tool(context)
            # Should log tool selection
            mock_log.info.assert_called()

    @pytest.mark.asyncio
    async def test_select_tool_raises_on_invalid_tool(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """ToolSelectionError raised if LLM returns invalid tool."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole
        from cyberred.core.models import ToolSelectionContext
        from cyberred.core.exceptions import ToolSelectionError

        # Return invalid JSON
        mock_llm_gateway.agent_complete.return_value = MagicMock(
            content='not valid json'
        )

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        context = ToolSelectionContext(
            objective="test",
            target_info={"hostname": "bad.target"},
            available_tools=["nmap"],
            phase="recon",
        )

        with pytest.raises(ToolSelectionError):
            await agent.select_tool(context)

    @pytest.mark.asyncio
    async def test_select_tool_filters_by_role_categories(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """Only role-appropriate tool categories are offered to LLM."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole
        from cyberred.core.models import ToolSelectionContext

        mock_llm_gateway.agent_complete.return_value = MagicMock(
            content='{"tool_name": "nmap", "command": "nmap -sV 192.168.1.1", "rationale": "test", "expected_output_type": "xml", "confidence": 0.9, "priority": 5, "alternatives": []}'
        )

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        context = ToolSelectionContext(
            objective="scan",
            target_info={"ip": "192.168.1.1"},
            available_tools=[],  # Empty - should be populated from manifest
            phase="recon",
        )

        await agent.select_tool(context)

        # ManifestLoader.get_by_category should be called with recon categories
        mock_manifest_loader.get_by_category.assert_called()


@pytest.mark.unit
class TestGenerateCommand:
    """Tests for generate_command() method."""

    @pytest.mark.asyncio
    async def test_generate_command_returns_string(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """generate_command returns command string."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole

        mock_llm_gateway.agent_complete.return_value = MagicMock(
            content='nmap -sV -p 22,80,443 192.168.1.100'
        )

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        result = await agent.generate_command(
            tool="nmap",
            target="192.168.1.100",
        )

        assert isinstance(result, str)
        assert "nmap" in result
        assert "192.168.1.100" in result

    @pytest.mark.asyncio
    async def test_generate_command_includes_target(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """Generated command includes target specification."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole

        mock_llm_gateway.agent_complete.return_value = MagicMock(
            content='nuclei -u https://target.example.com -t cves/'
        )

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.EXPLOIT,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        result = await agent.generate_command(
            tool="nuclei",
            target="https://target.example.com",
        )

        assert "target.example.com" in result

    @pytest.mark.asyncio
    async def test_generate_command_uses_help_output(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """LLM prompt includes tool's --help output."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole

        mock_llm_gateway.agent_complete.return_value = MagicMock(
            content='nmap -sV 192.168.1.1'
        )

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        # Mock _get_tool_help to return specific output
        agent._get_tool_help = AsyncMock(return_value="Nmap 7.92 - Usage: nmap [options] target")

        await agent.generate_command(tool="nmap", target="192.168.1.1")

        # Verify _get_tool_help was called
        agent._get_tool_help.assert_called_once_with("nmap")

        # LLM prompt should include help output
        call_args = mock_llm_gateway.agent_complete.call_args
        request = call_args[0][0]
        assert "Usage:" in request.prompt or "Usage" in str(call_args)

    @pytest.mark.asyncio
    async def test_generate_command_validates_output(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """Basic validation ensures command starts with tool name."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole

        # Return command that doesn't start with tool name
        mock_llm_gateway.agent_complete.return_value = MagicMock(
            content='wrong_tool -x target'
        )

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        agent._get_tool_help = AsyncMock(return_value="help output")

        # Should raise validation error
        with pytest.raises(ValueError, match="command"):
            await agent.generate_command(tool="nmap", target="192.168.1.1")


@pytest.mark.unit
class TestGetToolHelp:
    """Tests for _get_tool_help() method."""

    @pytest.mark.asyncio
    async def test_get_tool_help_caches_result(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """Second call uses cache, not kali_execute."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        with patch('cyberred.tools.kali_executor.kali_execute', new_callable=AsyncMock) as mock_kali:
            mock_kali.return_value = MagicMock(success=True, stdout="nmap help output")

            # First call
            result1 = await agent._get_tool_help("nmap")
            assert "nmap help output" in result1

            # Second call - should use cache
            result2 = await agent._get_tool_help("nmap")
            assert result1 == result2

            # kali_execute should only be called once
            assert mock_kali.call_count == 1

    @pytest.mark.asyncio
    async def test_get_tool_help_cache_key_is_tool_name(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """Cache key is exactly the tool name."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        with patch('cyberred.tools.kali_executor.kali_execute', new_callable=AsyncMock) as mock_kali:
            mock_kali.return_value = MagicMock(success=True, stdout="help")

            await agent._get_tool_help("nuclei")

            # Cache should have tool name as key
            assert "nuclei" in agent._tool_help_cache

    @pytest.mark.asyncio
    async def test_get_tool_help_truncates_to_80_lines(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """Help output is truncated to 80 lines max."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        # Create 100-line help output
        long_help = "\n".join([f"line {i}" for i in range(100)])

        with patch('cyberred.tools.kali_executor.kali_execute', new_callable=AsyncMock) as mock_kali:
            mock_kali.return_value = MagicMock(success=True, stdout=long_help)

            result = await agent._get_tool_help("bigtool")

            # Should be truncated to 80 lines
            lines = result.strip().split("\n")
            assert len(lines) <= 80

    @pytest.mark.asyncio
    async def test_get_tool_help_handles_missing_tool(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """Graceful fallback if tool has no --help."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        with patch('cyberred.tools.kali_executor.kali_execute', new_callable=AsyncMock) as mock_kali:
            # Simulate tool not found
            mock_kali.return_value = MagicMock(success=False, stdout="", stderr="command not found")

            result = await agent._get_tool_help("nonexistent_tool")

            # Should return fallback message
            assert "No help available" in result or "nonexistent_tool" in result


@pytest.mark.unit
class TestToolSelectionCoverage:
    """Additional tests for 100% coverage of tool selection code paths."""

    @pytest.mark.asyncio
    async def test_parse_tool_selection_with_markdown_code_block(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """_parse_tool_selection handles markdown code blocks."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        # Response with markdown code block
        markdown_response = '''```json
{"tool_name": "nmap", "command": "nmap -sV 192.168.1.1", "rationale": "Port scan", "expected_output_type": "xml", "confidence": 0.9, "priority": 7, "alternatives": []}
```'''

        result = agent._parse_tool_selection(markdown_response)

        assert result.tool_name == "nmap"
        assert result.command == "nmap -sV 192.168.1.1"

    @pytest.mark.asyncio
    async def test_parse_tool_selection_with_triple_backtick_wrapper(
        self, mock_event_bus, mock_llm_gateway, mock_manifest_loader
    ):
        """_parse_tool_selection strips triple backticks correctly."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_llm_gateway,
            manifest_loader=mock_manifest_loader,
        )

        # Response with backticks
        backtick_response = '''```
{"tool_name": "masscan", "command": "masscan -p1-65535 10.0.0.0/8", "rationale": "Fast scan", "expected_output_type": "text", "confidence": 0.85, "priority": 8, "alternatives": ["nmap"]}
```'''

        result = agent._parse_tool_selection(backtick_response)

        assert result.tool_name == "masscan"
        assert "masscan" in result.command

    @pytest.mark.asyncio
    async def test_check_throttle_with_gateway(self, mock_event_bus):
        """_check_throttle returns True when queue depth exceeds threshold."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole

        mock_gateway = MagicMock()
        mock_gateway.queue_depth = 100  # High queue depth

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_gateway,
        )

        # Patch at the module level where the import happens
        import cyberred.llm.gateway as gateway_module
        original_get_gateway = getattr(gateway_module, 'get_gateway', None)
        
        def mock_get_gateway():
            return mock_gateway
        
        gateway_module.get_gateway = mock_get_gateway
        
        try:
            with patch('cyberred.agents.base.get_settings') as mock_settings:
                settings = MagicMock()
                settings.agents.throttle.threshold = 10
                settings.engagement.max_agents = 5
                mock_settings.return_value = settings

                result = await agent._check_throttle()

                assert result is True  # Should be throttled (100 >= 10)
        finally:
            if original_get_gateway:
                gateway_module.get_gateway = original_get_gateway

    @pytest.mark.asyncio
    async def test_check_throttle_with_fractional_threshold(self, mock_event_bus):
        """_check_throttle handles fractional threshold (< 1.0)."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole

        mock_gateway = MagicMock()
        mock_gateway.queue_depth = 3

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=mock_gateway,
        )

        import cyberred.llm.gateway as gateway_module
        original_get_gateway = getattr(gateway_module, 'get_gateway', None)
        
        def mock_get_gateway():
            return mock_gateway
        
        gateway_module.get_gateway = mock_get_gateway
        
        try:
            with patch('cyberred.agents.base.get_settings') as mock_settings:
                settings = MagicMock()
                settings.agents.throttle.threshold = 0.5  # Fractional
                settings.engagement.max_agents = 10  # target_depth = 5
                mock_settings.return_value = settings

                result = await agent._check_throttle()

                # queue_depth (3) < target_depth (5), not throttled
                assert result is False
        finally:
            if original_get_gateway:
                gateway_module.get_gateway = original_get_gateway

    @pytest.mark.asyncio
    async def test_check_throttle_exception_fails_open(self, mock_event_bus):
        """_check_throttle returns False (fail-open) on exception."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
        )

        import cyberred.llm.gateway as gateway_module
        original_get_gateway = getattr(gateway_module, 'get_gateway', None)
        
        def mock_get_gateway():
            raise Exception("Gateway error")
        
        gateway_module.get_gateway = mock_get_gateway
        
        try:
            result = await agent._check_throttle()

            # Fail-open: should return False
            assert result is False
        finally:
            if original_get_gateway:
                gateway_module.get_gateway = original_get_gateway

    @pytest.mark.asyncio
    async def test_execute_throttle_logic_error_continues(self, mock_event_bus):
        """execute() continues when throttle check has non-timeout error."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
        )

        async def mock_check_throttle():
            raise ValueError("Some unexpected error")

        with patch.object(agent, '_check_throttle', side_effect=mock_check_throttle):
            with patch.object(agent, '_log') as mock_log:
                result = await agent.execute("192.168.1.1")

                # Should have logged error but continued
                mock_log.error.assert_called()
                assert result is not None

    @pytest.mark.asyncio
    async def test_generate_command_fallback_without_gateway(
        self, mock_event_bus
    ):
        """generate_command uses fallback when no LLM gateway."""
        from cyberred.agents.base import StigmergicAgent
        from cyberred.agents.roles import AgentRole

        agent = StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=mock_event_bus,
            role=AgentRole.RECON,
            llm_gateway=None,  # No gateway
        )

        # Pre-populate help cache to avoid kali_execute call
        agent._tool_help_cache["nmap"] = "nmap [options] target"

        command = await agent.generate_command(
            tool="nmap",
            target="192.168.1.1"
        )

        # Fallback should return simple command
        assert command == "nmap 192.168.1.1"
