"""Additional unit tests for ReconAgent to achieve 100% coverage.

These tests cover the gaps identified in code review:
- Lines 135, 143, 158-159, 184, 186, 193, 195, 239-240
- wafw00f/subfinder command generation
- AgentAction with decision_context (NFR37)
- Strategy adaptation for all tools
- Buffer flush partial failure
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone
import uuid

from cyberred.agents.recon import ReconAgent
from cyberred.core.models import Finding, AgentAction, ToolResult


@pytest.fixture
def mock_event_bus():
    return AsyncMock()


@pytest.fixture
def mock_scope_validator():
    with patch("cyberred.agents.recon.ScopeValidator") as mock:
        instance = mock.return_value
        instance.validate.return_value = True
        mock.from_file.return_value = instance
        yield instance


@pytest.fixture
def mock_settings():
    with patch("cyberred.agents.recon.get_settings") as mock:
        settings = MagicMock()
        settings.engagement.scope_path = None
        mock.return_value = settings
        yield mock


@pytest.fixture
def recon_agent(mock_event_bus, mock_scope_validator, mock_settings):
    agent = ReconAgent(
        agent_id=str(uuid.uuid4()),
        engagement_id="eng-test",
        target="192.168.1.10",
        event_bus=mock_event_bus
    )
    return agent


class TestReconAgentCoverage:
    """Tests for 100% coverage of recon.py."""

    # ==========================================================================
    # Tests for wafw00f command generation (Task 3.5)
    # ==========================================================================
    
    def test_generate_wafw00f_command(self, recon_agent):
        """Test wafw00f command generation."""
        cmd = recon_agent._generate_wafw00f_command("example.com")
        assert "wafw00f" in cmd
        assert "example.com" in cmd
    
    # ==========================================================================
    # Tests for subfinder command generation (Task 3.6)
    # ==========================================================================
    
    def test_generate_subfinder_command(self, recon_agent):
        """Test subfinder command generation."""
        cmd = recon_agent._generate_subfinder_command("example.com")
        assert "subfinder" in cmd
        assert "-d" in cmd
        assert "example.com" in cmd

    # ==========================================================================
    # Tests for strategy adaptation - masscan (Lines 184, 186)
    # ==========================================================================
    
    def test_generate_masscan_aggressive(self, recon_agent):
        """Test masscan command with aggressive strategy."""
        recon_agent.current_strategy = "aggressive"
        cmd = recon_agent._generate_masscan_command("192.168.1.10")
        assert "--rate=10000" in cmd
    
    def test_generate_masscan_stealth(self, recon_agent):
        """Test masscan command with stealth strategy."""
        recon_agent.current_strategy = "stealth"
        cmd = recon_agent._generate_masscan_command("192.168.1.10")
        assert "--rate=100" in cmd
    
    def test_generate_masscan_standard(self, recon_agent):
        """Test masscan command with standard strategy (default)."""
        recon_agent.current_strategy = "standard"
        cmd = recon_agent._generate_masscan_command("192.168.1.10")
        assert "--rate=1000" in cmd

    # ==========================================================================
    # Tests for strategy adaptation - whatweb (Lines 193, 195)
    # ==========================================================================
    
    def test_generate_whatweb_aggressive(self, recon_agent):
        """Test whatweb command with aggressive strategy."""
        recon_agent.current_strategy = "aggressive"
        cmd = recon_agent._generate_whatweb_command("192.168.1.10")
        assert "--aggression=3" in cmd
    
    def test_generate_whatweb_stealth(self, recon_agent):
        """Test whatweb command with stealth strategy."""
        recon_agent.current_strategy = "stealth"
        cmd = recon_agent._generate_whatweb_command("192.168.1.10")
        assert "--aggression=1" in cmd
    
    def test_generate_whatweb_standard(self, recon_agent):
        """Test whatweb command with standard strategy (no special args)."""
        recon_agent.current_strategy = "standard"
        cmd = recon_agent._generate_whatweb_command("192.168.1.10")
        assert "--aggression" not in cmd

    # ==========================================================================
    # Tests for _generate_tool_command helper
    # ==========================================================================
    
    def test_generate_tool_command_unknown_tool(self, recon_agent):
        """Test _generate_tool_command returns empty for unknown tool."""
        cmd = recon_agent._generate_tool_command("unknown_tool", "target")
        assert cmd == ""

    @pytest.mark.asyncio
    async def test_execute_recon_skips_unknown_tool(self, recon_agent):
        """Test execute_recon skips tools that return empty commands (line 170 continue)."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.exit_code = 0
        mock_result.error_type = None
        
        mock_processed = MagicMock()
        mock_processed.findings = []
        
        # Count how many times kali_execute is called
        call_count = [0]
        
        async def counting_execute(*args, **kwargs):
            call_count[0] += 1
            return mock_result
        
        with patch("cyberred.agents.recon.kali_execute", side_effect=counting_execute):
            with patch.object(recon_agent.output_processor, "process", return_value=mock_processed):
                # Make _generate_tool_command return empty for first 2 tools
                original_gen = recon_agent._generate_tool_command
                call_idx = [0]
                
                def patched_gen(tool_name, target):
                    call_idx[0] += 1
                    # Return empty for first 2 tools to trigger continue
                    if call_idx[0] <= 2:
                        return ""
                    return original_gen(tool_name, target)
                
                with patch.object(recon_agent, "_generate_tool_command", side_effect=patched_gen):
                    findings, actions = await recon_agent.execute_recon()
                    
                    # Should have skipped first 2 tools, so only 3 kali_execute calls
                    assert call_count[0] == 3
                    # Actions are created for ALL tools including skipped ones (NFR37 compliance)
                    # 5 tools in sequence = 5 actions
                    assert len(actions) == 3  # Only tools that ran get actions
    
    def test_generate_tool_command_all_tools(self, recon_agent):
        """Test _generate_tool_command for all known tools."""
        tools = ["masscan", "nmap", "whatweb", "wafw00f", "subfinder"]
        for tool in tools:
            cmd = recon_agent._generate_tool_command(tool, "192.168.1.10")
            assert tool in cmd or cmd != "", f"Command for {tool} should not be empty"

    # ==========================================================================
    # Tests for execute_recon with findings (Lines 158-159)
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_execute_recon_with_findings(self, recon_agent):
        """Test execute_recon processes and publishes findings."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.stdout = "<xml>nmap output</xml>"
        mock_result.stderr = ""
        mock_result.exit_code = 0
        mock_result.error_type = None
        
        # Create a proper mock finding with model_dump method
        mock_finding = MagicMock()
        mock_finding.id = str(uuid.uuid4())
        mock_finding.type = "open_port"
        mock_finding.model_dump = MagicMock(return_value={"port": 80, "id": mock_finding.id, "type": "open_port"})
        
        mock_processed = MagicMock()
        mock_processed.findings = [mock_finding]
        
        with patch("cyberred.agents.recon.kali_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result
            
            with patch.object(recon_agent.output_processor, "process", return_value=mock_processed):
                findings, actions = await recon_agent.execute_recon()
                
                # Should have findings from each tool iteration that succeeded
                assert len(findings) > 0
                # Should have AgentAction for each tool
                assert len(actions) > 0
                # Each action should have decision_context (NFR37)
                for action in actions:
                    assert action.decision_context, "NFR37: decision_context must not be empty"

    # ==========================================================================
    # Tests for tool execution failure (Line 143)
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_execute_recon_tool_failure_logged(self, recon_agent):
        """Test that tool execution failures are logged."""
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.stdout = ""
        mock_result.stderr = "Connection refused"
        mock_result.exit_code = 1
        mock_result.error_type = "NON_ZERO_EXIT"
        
        mock_processed = MagicMock()
        mock_processed.findings = []
        
        with patch("cyberred.agents.recon.kali_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result
            
            with patch.object(recon_agent.output_processor, "process", return_value=mock_processed):
                with patch.object(recon_agent, "_log") as mock_log:
                    findings, actions = await recon_agent.execute_recon()
                    
                    # Should log warning for each failed tool
                    warning_calls = [c for c in mock_log.warning.call_args_list 
                                   if "tool_execution_failed" in str(c)]
                    assert len(warning_calls) > 0

    # ==========================================================================
    # Tests for AgentAction with decision_context (NFR37)
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_execute_recon_creates_agent_actions(self, recon_agent):
        """Test that execute_recon creates AgentAction for each tool."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.exit_code = 0
        mock_result.error_type = None
        
        mock_processed = MagicMock()
        mock_processed.findings = []
        
        with patch("cyberred.agents.recon.kali_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result
            
            with patch.object(recon_agent.output_processor, "process", return_value=mock_processed):
                findings, actions = await recon_agent.execute_recon()
                
                # 5 tools = 5 actions
                assert len(actions) == 5
                
                # Verify each action has required fields
                for action in actions:
                    assert action.id
                    assert action.agent_id == str(recon_agent.agent_id)
                    assert action.action_type.startswith("recon:")
                    assert action.target == recon_agent.target
                    assert action.timestamp
                    assert action.decision_context  # NFR37: must not be empty
    
    @pytest.mark.asyncio
    async def test_execute_recon_initial_spawn_context(self, recon_agent):
        """Test that initial spawn adds context when decision_context empty."""
        # Clear any existing decision context
        recon_agent._decision_context = []
        
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.exit_code = 0
        mock_result.error_type = None
        
        mock_processed = MagicMock()
        mock_processed.findings = []
        
        with patch("cyberred.agents.recon.kali_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result
            
            with patch.object(recon_agent.output_processor, "process", return_value=mock_processed):
                findings, actions = await recon_agent.execute_recon()
                
                # First action should have initial_spawn context
                assert any("initial_spawn" in ctx for ctx in actions[0].decision_context)

    @pytest.mark.asyncio
    async def test_execute_recon_preserves_signal_context(self, recon_agent):
        """Test that received signals are included in decision_context."""
        # Simulate receiving signals
        recon_agent._decision_context = ["signal-123", "signal-456"]
        
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.exit_code = 0
        mock_result.error_type = None
        
        mock_processed = MagicMock()
        mock_processed.findings = []
        
        with patch("cyberred.agents.recon.kali_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result
            
            with patch.object(recon_agent.output_processor, "process", return_value=mock_processed):
                findings, actions = await recon_agent.execute_recon()
                
                # Actions should include the signal IDs
                assert "signal-123" in actions[0].decision_context
                assert "signal-456" in actions[0].decision_context

    # ==========================================================================
    # Tests for buffer flush partial failure (Lines 239-240)
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_buffer_flush_partial_failure(self, recon_agent, mock_event_bus):
        """Test that partial buffer flush failure retains failed items."""
        # Setup buffer with multiple items
        recon_agent._finding_buffer = [
            {"channel": "c1", "message": {"m": 1}},
            {"channel": "c2", "message": {"m": 2}},
            {"channel": "c3", "message": {"m": 3}},
        ]
        
        # First publish succeeds, second fails, third succeeds
        call_count = [0]
        async def side_effect(channel, message):
            call_count[0] += 1
            if call_count[0] == 2:  # Second call fails
                raise Exception("Connection lost")
        
        mock_event_bus.publish.side_effect = side_effect
        
        await recon_agent._flush_buffer()
        
        # Should have 1 remaining (the failed one)
        assert len(recon_agent._finding_buffer) == 1
        assert recon_agent._finding_buffer[0]["channel"] == "c2"

    @pytest.mark.asyncio
    async def test_buffer_flush_all_fail(self, recon_agent, mock_event_bus):
        """Test buffer flush when all items fail."""
        recon_agent._finding_buffer = [
            {"channel": "c1", "message": {"m": 1}},
            {"channel": "c2", "message": {"m": 2}},
        ]
        
        mock_event_bus.publish.side_effect = Exception("All fail")
        
        await recon_agent._flush_buffer()
        
        # All should remain in buffer
        assert len(recon_agent._finding_buffer) == 2

    @pytest.mark.asyncio  
    async def test_buffer_flush_success_logs(self, recon_agent, mock_event_bus):
        """Test buffer flush logs success count."""
        recon_agent._finding_buffer = [
            {"channel": "c1", "message": {"m": 1}},
            {"channel": "c2", "message": {"m": 2}},
        ]
        
        mock_event_bus.publish.side_effect = None  # All succeed
        
        with patch.object(recon_agent, "_log") as mock_log:
            await recon_agent._flush_buffer()
            
            # Should log buffer_flushed
            mock_log.info.assert_called()
            assert len(recon_agent._finding_buffer) == 0

    # ==========================================================================
    # Tests for on_signal strategy handling (Lines 253, 255)
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_on_signal_invalid_strategy_ignored(self, recon_agent):
        """Test that invalid strategy values are ignored."""
        original_strategy = recon_agent.current_strategy
        
        await recon_agent.on_signal("strategies:eng-test", {"strategy": "invalid_strategy"})
        
        # Strategy should not change
        assert recon_agent.current_strategy == original_strategy

    @pytest.mark.asyncio
    async def test_on_signal_non_strategy_channel(self, recon_agent):
        """Test that non-strategy channels don't affect strategy."""
        original_strategy = recon_agent.current_strategy
        
        await recon_agent.on_signal("findings:hash:type", {"strategy": "aggressive"})
        
        # Strategy should not change (not a strategies channel)
        assert recon_agent.current_strategy == original_strategy

    @pytest.mark.asyncio
    async def test_on_signal_all_valid_strategies(self, recon_agent):
        """Test all valid strategy values."""
        for strategy in ["stealth", "standard", "aggressive"]:
            await recon_agent.on_signal("strategies:eng-test", {"strategy": strategy})
            assert recon_agent.current_strategy == strategy

    # ==========================================================================
    # Tests for graceful stop during recon
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_execute_recon_stops_on_stop_event(self, recon_agent):
        """Test execute_recon respects stop event mid-execution."""
        call_count = [0]
        
        async def slow_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                await recon_agent.stop()  # Stop after first tool
            await asyncio.sleep(0.01)
            result = MagicMock()
            result.success = True
            result.stdout = ""
            result.stderr = ""
            result.exit_code = 0
            result.error_type = None
            return result
        
        mock_processed = MagicMock()
        mock_processed.findings = []
        
        with patch("cyberred.agents.recon.kali_execute", side_effect=slow_execute):
            with patch.object(recon_agent.output_processor, "process", return_value=mock_processed):
                findings, actions = await recon_agent.execute_recon()
                
                # Should not have executed all 5 tools
                assert len(actions) < 5


class TestReconAgentNFR37Compliance:
    """Dedicated tests for NFR37 - 100% decision_context population."""
    
    @pytest.mark.asyncio
    async def test_nfr37_all_actions_have_context(self, recon_agent, mock_event_bus, mock_scope_validator, mock_settings):
        """NFR37: Verify 100% of actions have non-empty decision_context."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_result.exit_code = 0
        mock_result.error_type = None
        
        mock_processed = MagicMock()
        mock_processed.findings = []
        
        with patch("cyberred.agents.recon.kali_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result
            
            with patch.object(recon_agent.output_processor, "process", return_value=mock_processed):
                findings, actions = await recon_agent.execute_recon()
                
                # NFR37 HARD GATE: 100% of actions must have decision_context
                empty_context_count = sum(1 for a in actions if not a.decision_context)
                assert empty_context_count == 0, \
                    f"NFR37 VIOLATION: {empty_context_count}/{len(actions)} actions have empty decision_context"
                
                # Verify the specific structure
                for action in actions:
                    assert isinstance(action.decision_context, list)
                    assert len(action.decision_context) > 0
                    assert all(isinstance(ctx, str) for ctx in action.decision_context)


@pytest.fixture
def recon_agent(mock_event_bus, mock_scope_validator, mock_settings):
    """Create ReconAgent fixture for NFR37 tests."""
    agent = ReconAgent(
        agent_id=str(uuid.uuid4()),
        engagement_id="eng-test",
        target="192.168.1.10",
        event_bus=mock_event_bus
    )
    return agent
