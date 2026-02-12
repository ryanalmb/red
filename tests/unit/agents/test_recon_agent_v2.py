"""Unit tests for ReconAgent v2 (LLM-driven thin subclass refactor).

Story 7.3-v2: Tests for the refactored ReconAgent that uses LLM-driven
tool selection instead of hardcoded tool sequences.

TDD Phase: RED - These tests will initially FAIL until implementation is updated.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import uuid

from cyberred.agents.recon import ReconAgent
from cyberred.agents.base import StigmergicAgent
from cyberred.agents.roles import AgentRole
from cyberred.core.models import ToolSelection, ToolSelectionContext


@pytest.mark.unit
class TestReconAgentV2Constructor:
    """Tests for ReconAgent v2 constructor (thin subclass pattern)."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def mock_llm_gateway(self):
        gateway = AsyncMock()
        gateway.agent_complete.return_value = MagicMock(
            content='{"tool_name": "nmap", "command": "nmap -sV 10.0.0.1", '
                    '"rationale": "Port scan", "expected_output_type": "xml", '
                    '"confidence": 0.9, "priority": 1, "alternatives": []}'
        )
        return gateway

    @pytest.fixture
    def mock_manifest_loader(self):
        loader = MagicMock()
        loader.get_by_category.return_value = [MagicMock(name="nmap"), MagicMock(name="masscan")]
        return loader

    def test_recon_agent_sets_role_to_recon(self, mock_event_bus):
        """AC: ReconAgent sets role=AgentRole.RECON automatically."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            assert agent.role == AgentRole.RECON

    def test_default_specialty_is_network(self, mock_event_bus):
        """AC: Default specialty is 'network'."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            assert agent.specialty == "network"

    @pytest.mark.parametrize("specialty", ["network", "osint", "dns", "subdomain"])
    def test_accepts_all_four_specialties(self, mock_event_bus, specialty):
        """AC: Agent supports 4 specialties: network, osint, dns, subdomain."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
                specialty=specialty,
            )
            assert agent.specialty == specialty

    def test_accepts_llm_gateway_injection(self, mock_event_bus, mock_llm_gateway):
        """AC: Constructor accepts llm_gateway for dependency injection."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
                llm_gateway=mock_llm_gateway,
            )
            assert agent._llm_gateway is mock_llm_gateway

    def test_accepts_manifest_loader_injection(self, mock_event_bus, mock_manifest_loader):
        """AC: Constructor accepts manifest_loader for dependency injection."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
                manifest_loader=mock_manifest_loader,
            )
            assert agent._manifest is mock_manifest_loader

    def test_loads_prompt_from_library(self, mock_event_bus):
        """AC: PromptLibrary.get(RECON, specialty) provides system prompt."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            with patch("cyberred.agents.base.PromptLibrary.get") as mock_prompt:
                mock_prompt.return_value = "Test recon prompt"
                agent = ReconAgent(
                    agent_id=str(uuid.uuid4()),
                    engagement_id="eng-1",
                    event_bus=mock_event_bus,
                    specialty="osint",
                )
                mock_prompt.assert_called_with(AgentRole.RECON, "osint")


@pytest.mark.unit
class TestReconAgentV2NoHardcodedMethods:
    """Tests verifying removal of hardcoded tool logic."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    def test_no_hardcoded_tool_sequence(self, mock_event_bus):
        """AC: NO hardcoded tool_sequence list exists."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            # Verify no tool_sequence attribute exists
            assert not hasattr(agent, "tool_sequence"), "tool_sequence should be removed"

    def test_no_generate_nmap_command(self, mock_event_bus):
        """AC: NO _generate_nmap_command method exists."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            assert not hasattr(agent, "_generate_nmap_command"), "_generate_nmap_command should be removed"

    def test_no_generate_masscan_command(self, mock_event_bus):
        """AC: NO _generate_masscan_command method exists."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            assert not hasattr(agent, "_generate_masscan_command"), "_generate_masscan_command should be removed"

    def test_no_generate_whatweb_command(self, mock_event_bus):
        """AC: NO _generate_whatweb_command method exists."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            assert not hasattr(agent, "_generate_whatweb_command"), "_generate_whatweb_command should be removed"

    def test_no_generate_wafw00f_command(self, mock_event_bus):
        """AC: NO _generate_wafw00f_command method exists."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            assert not hasattr(agent, "_generate_wafw00f_command"), "_generate_wafw00f_command should be removed"

    def test_no_generate_subfinder_command(self, mock_event_bus):
        """AC: NO _generate_subfinder_command method exists."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            assert not hasattr(agent, "_generate_subfinder_command"), "_generate_subfinder_command should be removed"

    def test_no_generate_tool_command(self, mock_event_bus):
        """AC: NO _generate_tool_command dispatch method exists."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            assert not hasattr(agent, "_generate_tool_command"), "_generate_tool_command should be removed"


@pytest.mark.unit
class TestReconAgentV2LLMSelection:
    """Tests for LLM-driven tool selection."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def mock_llm_gateway(self):
        gateway = AsyncMock()
        gateway.agent_complete.return_value = MagicMock(
            content='{"tool_name": "nmap", "command": "nmap -sV -p- 10.0.0.1", '
                    '"rationale": "Full port scan for service discovery", '
                    '"expected_output_type": "xml", "confidence": 0.95, '
                    '"priority": 1, "alternatives": ["masscan"]}'
        )
        return gateway

    @pytest.fixture
    def mock_manifest_loader(self):
        loader = MagicMock()
        tool1 = MagicMock()
        tool1.name = "nmap"
        tool2 = MagicMock()
        tool2.name = "masscan"
        loader.get_by_category.return_value = [tool1, tool2]
        return loader

    @pytest.fixture
    def mock_kali_execute(self):
        with patch("cyberred.agents.recon.kali_execute") as mock:
            result = MagicMock()
            result.success = True
            result.stdout = "<nmaprun>...</nmaprun>"
            result.stderr = ""
            result.exit_code = 0
            mock.return_value = result
            yield mock

    @pytest.fixture
    def recon_agent_v2(self, mock_event_bus, mock_llm_gateway, mock_manifest_loader):
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
                llm_gateway=mock_llm_gateway,
                manifest_loader=mock_manifest_loader,
            )
            return agent

    @pytest.mark.asyncio
    async def test_execute_recon_calls_select_tool(
        self, recon_agent_v2, mock_llm_gateway, mock_kali_execute
    ):
        """AC: execute_recon() uses inherited select_tool() for tool choice."""
        with patch.object(recon_agent_v2, "_validate_target_scope"):
            with patch.object(recon_agent_v2, "select_tool", new_callable=AsyncMock) as mock_select:
                mock_select.return_value = ToolSelection(
                    tool_name="nmap",
                    command="nmap -sV 10.0.0.1",
                    rationale="Port scan",
                    expected_output_type="xml",
                    confidence=0.9,
                    priority=1,
                    alternatives=[],
                )
                with patch.object(recon_agent_v2, "_phase_complete", new_callable=AsyncMock) as mock_phase:
                    # Complete after first iteration
                    mock_phase.side_effect = [False, True]

                    await recon_agent_v2.execute_recon(target="10.0.0.1")

                    mock_select.assert_called()

    @pytest.mark.asyncio
    async def test_execute_recon_uses_llm_command(
        self, recon_agent_v2, mock_kali_execute
    ):
        """AC: execute_recon() uses LLM-generated command from select_tool()."""
        with patch.object(recon_agent_v2, "_validate_target_scope"):
            with patch.object(recon_agent_v2, "select_tool", new_callable=AsyncMock) as mock_select:
                mock_select.return_value = ToolSelection(
                    tool_name="nmap",
                    command="nmap -sV -T4 10.0.0.1",
                    rationale="Aggressive scan",
                    expected_output_type="xml",
                    confidence=0.9,
                    priority=1,
                    alternatives=[],
                )
                with patch.object(recon_agent_v2, "_phase_complete", new_callable=AsyncMock) as mock_phase:
                    mock_phase.side_effect = [False, True]

                    await recon_agent_v2.execute_recon(target="10.0.0.1")

                    # Verify kali_execute was called with LLM-generated command
                    mock_kali_execute.assert_called_with("nmap -sV -T4 10.0.0.1", timeout=None)

    @pytest.mark.asyncio
    async def test_execute_recon_respects_max_iterations(
        self, recon_agent_v2, mock_kali_execute
    ):
        """AC: Loop respects max_iterations to prevent infinite loops."""
        iteration_count = 0

        async def never_complete(ctx):
            nonlocal iteration_count
            iteration_count += 1
            return False  # Never complete

        with patch.object(recon_agent_v2, "_validate_target_scope"):
            with patch.object(recon_agent_v2, "select_tool", new_callable=AsyncMock) as mock_select:
                mock_select.return_value = ToolSelection(
                    tool_name="nmap",
                    command="nmap 10.0.0.1",
                    rationale="Scan",
                    expected_output_type="text",
                    confidence=0.8,
                    priority=1,
                    alternatives=[],
                )
                with patch.object(recon_agent_v2, "_phase_complete", side_effect=never_complete):
                    await recon_agent_v2.execute_recon(target="10.0.0.1")

                    # Should stop at max_iterations (default 20)
                    assert mock_select.call_count <= 20

    @pytest.mark.asyncio
    async def test_decision_context_tracks_selection_id(
        self, recon_agent_v2, mock_kali_execute
    ):
        """AC (NFR37): Tool selection IDs tracked in decision_context."""
        selection = ToolSelection(
            tool_name="nmap",
            command="nmap 10.0.0.1",
            rationale="Scan",
            expected_output_type="text",
            confidence=0.8,
            priority=1,
            alternatives=[],
        )

        with patch.object(recon_agent_v2, "_validate_target_scope"):
            with patch.object(recon_agent_v2, "select_tool", new_callable=AsyncMock) as mock_select:
                mock_select.return_value = selection
                with patch.object(recon_agent_v2, "_phase_complete", new_callable=AsyncMock) as mock_phase:
                    mock_phase.side_effect = [False, True]

                    findings, actions = await recon_agent_v2.execute_recon(target="10.0.0.1")

                    # All actions should have non-empty decision_context (NFR37)
                    for action in actions:
                        assert action.decision_context, "decision_context must not be empty (NFR37)"


@pytest.mark.unit
class TestReconAgentV2PreservedBehavior:
    """Tests verifying preserved stigmergic hooks and lifecycle methods."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def recon_agent(self, mock_event_bus):
        with patch("cyberred.agents.recon.ScopeValidator"):
            return ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )

    @pytest.mark.asyncio
    async def test_on_finding_publishes(self, recon_agent, mock_event_bus):
        """AC: on_finding() publishes to Redis (unchanged from 7.3)."""
        await recon_agent.on_finding("tgt123", "open_port", {"port": 80})

        mock_event_bus.publish.assert_called()
        call_args = mock_event_bus.publish.call_args
        assert "findings:tgt123:open_port" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_on_signal_handles_strategy(self, recon_agent):
        """AC: on_signal() handles strategy updates (unchanged)."""
        await recon_agent.on_signal("strategies:eng-1", {"strategy": "stealth"})

        assert recon_agent.current_strategy == "stealth"

    async def test_stop_sets_event(self, recon_agent):
        """AC: stop() sets the stop event for graceful shutdown."""
        await recon_agent.stop()

        assert recon_agent._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_finding_buffer_degraded_mode(self, recon_agent, mock_event_bus):
        """AC: Finding buffer works in degraded mode."""
        # Simulate publish failure
        mock_event_bus.publish.side_effect = Exception("Connection lost")

        await recon_agent.on_finding("tgt", "port", {"p": 80})

        # Finding should be buffered
        assert len(recon_agent._finding_buffer) > 0


@pytest.mark.unit
class TestReconAgentV2Coverage:
    """Additional tests for 100% coverage on recon.py."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def mock_llm_gateway(self):
        gateway = AsyncMock()
        gateway.agent_complete.return_value = MagicMock(
            content='{"tool_name": "nmap", "command": "nmap -sV 10.0.0.1", '
                    '"rationale": "Port scan", "expected_output_type": "xml", '
                    '"confidence": 0.9, "priority": 1, "alternatives": []}'
        )
        return gateway

    @pytest.fixture
    def mock_kali_execute(self):
        with patch("cyberred.agents.recon.kali_execute") as mock:
            result = MagicMock()
            result.success = True
            result.stdout = "<nmaprun>...</nmaprun>"
            result.stderr = ""
            result.exit_code = 0
            mock.return_value = result
            yield mock

    @pytest.fixture
    def recon_agent(self, mock_event_bus, mock_llm_gateway):
        with patch("cyberred.agents.recon.ScopeValidator"):
            return ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-cov",
                event_bus=mock_event_bus,
                llm_gateway=mock_llm_gateway,
                max_iterations=3,
                phase_complete_threshold=100,
            )

    @pytest.mark.asyncio
    async def test_execute_recon_stop_event_breaks_loop(self, recon_agent, mock_kali_execute):
        """Test that setting stop_event breaks the recon loop."""
        with patch.object(recon_agent, "_validate_target_scope"):
            with patch.object(recon_agent, "select_tool", new_callable=AsyncMock) as mock_select:
                mock_select.return_value = ToolSelection(
                    tool_name="nmap", command="nmap 10.0.0.1", rationale="Scan",
                    expected_output_type="text", confidence=0.8, priority=1, alternatives=[],
                )
                # Set stop event before first iteration completes
                async def set_stop_after_call(*args, **kwargs):
                    recon_agent._stop_event.set()
                    return mock_select.return_value
                
                mock_select.side_effect = set_stop_after_call
                
                findings, actions = await recon_agent.execute_recon(target="10.0.0.1")
                
                # Should have stopped after first iteration
                assert len(actions) <= 1

    @pytest.mark.asyncio
    async def test_execute_recon_phase_complete_breaks_loop(self, recon_agent, mock_kali_execute):
        """Test that phase_complete=True breaks the loop."""
        with patch.object(recon_agent, "_validate_target_scope"):
            with patch.object(recon_agent, "select_tool", new_callable=AsyncMock) as mock_select:
                mock_select.return_value = ToolSelection(
                    tool_name="nmap", command="nmap 10.0.0.1", rationale="Scan",
                    expected_output_type="text", confidence=0.8, priority=1, alternatives=[],
                )
                # Make phase complete immediately
                with patch.object(recon_agent, "_phase_complete", new_callable=AsyncMock) as mock_phase:
                    mock_phase.return_value = True
                    
                    findings, actions = await recon_agent.execute_recon(target="10.0.0.1")
                    
                    # Should have no actions since phase was complete before first iteration
                    assert len(actions) == 0

    @pytest.mark.asyncio
    async def test_execute_recon_tool_execution_failure(self, recon_agent):
        """Test handling of tool execution failure."""
        with patch.object(recon_agent, "_validate_target_scope"):
            with patch.object(recon_agent, "select_tool", new_callable=AsyncMock) as mock_select:
                mock_select.return_value = ToolSelection(
                    tool_name="nmap", command="nmap 10.0.0.1", rationale="Scan",
                    expected_output_type="text", confidence=0.8, priority=1, alternatives=[],
                )
                with patch("cyberred.agents.recon.kali_execute", new_callable=AsyncMock) as mock_exec:
                    # Simulate failure
                    result = MagicMock()
                    result.success = False
                    result.stdout = ""
                    result.stderr = "Connection refused"
                    result.exit_code = 1
                    mock_exec.return_value = result
                    
                    with patch.object(recon_agent, "_phase_complete", new_callable=AsyncMock) as mock_phase:
                        mock_phase.side_effect = [False, True]  # Run one iteration
                        
                        findings, actions = await recon_agent.execute_recon(target="10.0.0.1")
                        
                        # Action should still be created even on failure
                        assert len(actions) == 1

    @pytest.mark.asyncio
    async def test_execute_recon_exception_handling(self, recon_agent, mock_kali_execute):
        """Test that exceptions in select_tool are caught and logged."""
        with patch.object(recon_agent, "_validate_target_scope"):
            with patch.object(recon_agent, "select_tool", new_callable=AsyncMock) as mock_select:
                mock_select.side_effect = Exception("LLM error")
                
                with patch.object(recon_agent, "_phase_complete", new_callable=AsyncMock) as mock_phase:
                    mock_phase.side_effect = [False, True]  # Run one iteration
                    
                    # Should not raise - exception is caught
                    findings, actions = await recon_agent.execute_recon(target="10.0.0.1")
                    
                    # Action created with tool_name="unknown"
                    assert len(actions) == 1
                    assert "unknown" in actions[0].action_type

    @pytest.mark.asyncio
    async def test_execute_recon_publishes_findings(self, recon_agent, mock_event_bus):
        """Test that findings are published via on_finding."""
        with patch.object(recon_agent, "_validate_target_scope"):
            with patch.object(recon_agent, "select_tool", new_callable=AsyncMock) as mock_select:
                mock_select.return_value = ToolSelection(
                    tool_name="nmap", command="nmap 10.0.0.1", rationale="Scan",
                    expected_output_type="xml", confidence=0.8, priority=1, alternatives=[],
                )
                with patch("cyberred.agents.recon.kali_execute", new_callable=AsyncMock) as mock_exec:
                    result = MagicMock()
                    result.success = True
                    result.stdout = "<nmaprun></nmaprun>"
                    result.stderr = ""
                    result.exit_code = 0
                    mock_exec.return_value = result
                    
                    # Mock output processor to return findings
                    finding_id = str(uuid.uuid4())
                    mock_finding = MagicMock()
                    mock_finding.type = "open_port"
                    mock_finding.id = finding_id  # Must be valid UUID
                    mock_finding.model_dump.return_value = {"port": 80}
                    
                    mock_processed = MagicMock()
                    mock_processed.findings = [mock_finding]
                    
                    with patch.object(recon_agent.output_processor, "process", return_value=mock_processed):
                        with patch.object(recon_agent, "_phase_complete", new_callable=AsyncMock) as mock_phase:
                            mock_phase.side_effect = [False, True]
                            
                            findings, actions = await recon_agent.execute_recon(target="10.0.0.1")
                            
                            assert len(findings) == 1
                            assert actions[0].result_finding_id == finding_id
                            mock_event_bus.publish.assert_called()

    def test_get_constraints_stealth(self, mock_event_bus):
        """Test _get_constraints returns stealth constraints."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            agent.current_strategy = "stealth"
            constraints = agent._get_constraints()
            assert "low_rate" in constraints
            assert "avoid_detection" in constraints
            assert "passive_preferred" in constraints

    def test_get_constraints_aggressive(self, mock_event_bus):
        """Test _get_constraints returns aggressive constraints."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            agent.current_strategy = "aggressive"
            constraints = agent._get_constraints()
            assert "high_throughput" in constraints
            assert "comprehensive" in constraints

    def test_get_constraints_standard(self, mock_event_bus):
        """Test _get_constraints returns empty for standard strategy."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            agent.current_strategy = "standard"
            constraints = agent._get_constraints()
            assert constraints == []

    def test_get_scope_validator_with_valid_path(self, mock_event_bus):
        """Test _get_scope_validator loads from file when path exists."""
        with patch("cyberred.agents.recon.ScopeValidator") as MockValidator:
            with patch("cyberred.agents.recon.get_settings") as mock_settings:
                mock_settings.return_value.engagement.scope_path = "/valid/path.yaml"
                MockValidator.from_file.return_value = MagicMock()
                
                agent = ReconAgent(
                    agent_id=str(uuid.uuid4()),
                    engagement_id="eng-1",
                    event_bus=mock_event_bus,
                )
                
                validator = agent._get_scope_validator()
                MockValidator.from_file.assert_called_with("/valid/path.yaml")

    def test_get_scope_validator_no_path(self, mock_event_bus):
        """Test _get_scope_validator returns default when no path configured."""
        with patch("cyberred.agents.recon.ScopeValidator") as MockValidator:
            with patch("cyberred.agents.recon.get_settings") as mock_settings:
                mock_settings.return_value.engagement.scope_path = None
                
                agent = ReconAgent(
                    agent_id=str(uuid.uuid4()),
                    engagement_id="eng-1",
                    event_bus=mock_event_bus,
                )
                
                validator = agent._get_scope_validator()
                # Should create default ScopeValidator
                MockValidator.assert_called()

    @pytest.mark.asyncio
    async def test_flush_buffer_partial_success(self, mock_event_bus):
        """Test _flush_buffer handles partial success."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            
            # Add items to buffer
            agent._finding_buffer = [
                {"channel": "ch1", "message": {"data": 1}},
                {"channel": "ch2", "message": {"data": 2}},
                {"channel": "ch3", "message": {"data": 3}},
            ]
            
            # First succeeds, second fails, third succeeds
            call_count = 0
            async def selective_fail(channel, message):
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise Exception("Network error")
            
            mock_event_bus.publish.side_effect = selective_fail
            
            await agent._flush_buffer()
            
            # Only the failed one should remain
            assert len(agent._finding_buffer) == 1

    @pytest.mark.asyncio
    async def test_flush_buffer_all_fail(self, mock_event_bus):
        """Test _flush_buffer when all publishes fail."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            
            agent._finding_buffer = [
                {"channel": "ch1", "message": {"data": 1}},
                {"channel": "ch2", "message": {"data": 2}},
            ]
            
            mock_event_bus.publish.side_effect = Exception("All fail")
            
            await agent._flush_buffer()
            
            # All should remain
            assert len(agent._finding_buffer) == 2

    @pytest.mark.asyncio
    async def test_on_signal_invalid_strategy_ignored(self, mock_event_bus):
        """Test on_signal ignores invalid strategy values."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            original_strategy = agent.current_strategy
            
            await agent.on_signal("strategies:eng-1", {"strategy": "invalid_strategy"})
            
            # Strategy should not change
            assert agent.current_strategy == original_strategy

    @pytest.mark.asyncio
    async def test_on_signal_no_strategy_key(self, mock_event_bus):
        """Test on_signal handles missing strategy key."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            original_strategy = agent.current_strategy
            
            await agent.on_signal("strategies:eng-1", {"other_key": "value"})
            
            # Strategy should not change
            assert agent.current_strategy == original_strategy

    @pytest.mark.asyncio
    async def test_on_finding_flushes_buffer_first(self, mock_event_bus):
        """Test on_finding attempts to flush buffer before publishing."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            
            # Add item to buffer
            agent._finding_buffer = [{"channel": "old", "message": {"old": True}}]
            
            # All publishes succeed
            mock_event_bus.publish.return_value = None
            
            await agent.on_finding("tgt", "port", {"p": 80})
            
            # Buffer should be empty and new finding published
            assert len(agent._finding_buffer) == 0
            assert mock_event_bus.publish.call_count == 2  # flush + new

    def test_configurable_max_iterations(self, mock_event_bus):
        """Test that max_iterations is configurable."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
                max_iterations=42,
            )
            assert agent.max_iterations == 42

    def test_configurable_phase_complete_threshold(self, mock_event_bus):
        """Test that phase_complete_threshold is configurable."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
                phase_complete_threshold=25,
            )
            assert agent.phase_complete_threshold == 25

    @pytest.mark.asyncio
    async def test_phase_complete_returns_true_when_threshold_reached(self, mock_event_bus):
        """Test _phase_complete returns True when threshold reached."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
                phase_complete_threshold=2,
            )
            
            context = ToolSelectionContext(
                objective="test",
                target_info={},
                available_tools=[],
                phase="recon",
                constraints=[],
                previous_results=[{"r": 1}, {"r": 2}],  # 2 results = threshold
            )
            
            result = await agent._phase_complete(context)
            assert result is True

    @pytest.mark.asyncio 
    async def test_phase_complete_returns_false_below_threshold(self, mock_event_bus):
        """Test _phase_complete returns False below threshold."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
                phase_complete_threshold=10,
            )
            
            context = ToolSelectionContext(
                objective="test",
                target_info={},
                available_tools=[],
                phase="recon",
                constraints=[],
                previous_results=[{"r": 1}],  # 1 result < 10 threshold
            )
            
            result = await agent._phase_complete(context)
            assert result is False

    def test_validate_target_scope_calls_validator(self, mock_event_bus):
        """Test _validate_target_scope calls validator.validate()."""
        mock_validator = MagicMock()
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            with patch.object(agent, "_get_scope_validator", return_value=mock_validator):
                agent._validate_target_scope("192.168.1.1")
                mock_validator.validate.assert_called_once_with(target="192.168.1.1")

    def test_get_scope_validator_file_load_exception(self, mock_event_bus):
        """Test _get_scope_validator handles file load exception."""
        with patch("cyberred.agents.recon.ScopeValidator") as MockValidator:
            with patch("cyberred.agents.recon.get_settings") as mock_settings:
                mock_settings.return_value.engagement.scope_path = "/bad/path.yaml"
                MockValidator.from_file.side_effect = FileNotFoundError("Not found")
                
                agent = ReconAgent(
                    agent_id=str(uuid.uuid4()),
                    engagement_id="eng-1",
                    event_bus=mock_event_bus,
                )
                
                # Should return default validator, not raise
                validator = agent._get_scope_validator()
                MockValidator.from_file.assert_called_with("/bad/path.yaml")

    @pytest.mark.asyncio
    async def test_on_signal_updates_to_stealth(self, mock_event_bus):
        """Test on_signal updates strategy to stealth."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            agent.current_strategy = "standard"
            
            await agent.on_signal("strategies:eng-1", {"strategy": "stealth"})
            
            assert agent.current_strategy == "stealth"

    @pytest.mark.asyncio
    async def test_on_signal_updates_to_aggressive(self, mock_event_bus):
        """Test on_signal updates strategy to aggressive."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            agent.current_strategy = "standard"
            
            await agent.on_signal("strategies:eng-1", {"strategy": "aggressive"})
            
            assert agent.current_strategy == "aggressive"

    @pytest.mark.asyncio
    async def test_on_signal_non_strategy_channel_ignored(self, mock_event_bus):
        """Test on_signal ignores non-strategy channels."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
            )
            original = agent.current_strategy
            
            await agent.on_signal("findings:eng-1", {"strategy": "stealth"})
            
            assert agent.current_strategy == original  # Unchanged

    @pytest.mark.asyncio
    async def test_execute_recon_multiple_findings_only_first_sets_result_id(self, mock_event_bus):
        """Test that only the first finding sets result_finding_id."""
        with patch("cyberred.agents.recon.ScopeValidator"):
            agent = ReconAgent(
                agent_id=str(uuid.uuid4()),
                engagement_id="eng-1",
                event_bus=mock_event_bus,
                max_iterations=1,
            )
            
            with patch.object(agent, "_validate_target_scope"):
                with patch.object(agent, "select_tool", new_callable=AsyncMock) as mock_select:
                    mock_select.return_value = ToolSelection(
                        tool_name="nmap", command="nmap 10.0.0.1", rationale="Scan",
                        expected_output_type="xml", confidence=0.8, priority=1, alternatives=[],
                    )
                    with patch("cyberred.agents.recon.kali_execute", new_callable=AsyncMock) as mock_exec:
                        result = MagicMock()
                        result.success = True
                        result.stdout = "<nmaprun></nmaprun>"
                        result.stderr = ""
                        result.exit_code = 0
                        mock_exec.return_value = result
                        
                        # Mock output processor to return MULTIPLE findings
                        first_finding_id = str(uuid.uuid4())
                        second_finding_id = str(uuid.uuid4())
                        
                        mock_finding1 = MagicMock()
                        mock_finding1.type = "open_port"
                        mock_finding1.id = first_finding_id
                        mock_finding1.model_dump.return_value = {"port": 22}
                        
                        mock_finding2 = MagicMock()
                        mock_finding2.type = "open_port"
                        mock_finding2.id = second_finding_id
                        mock_finding2.model_dump.return_value = {"port": 80}
                        
                        mock_processed = MagicMock()
                        mock_processed.findings = [mock_finding1, mock_finding2]
                        
                        with patch.object(agent.output_processor, "process", return_value=mock_processed):
                            findings, actions = await agent.execute_recon(target="10.0.0.1")
                            
                            # Should have 2 findings but action has first finding's ID
                            assert len(findings) == 2
                            assert len(actions) == 1
                            assert actions[0].result_finding_id == first_finding_id
