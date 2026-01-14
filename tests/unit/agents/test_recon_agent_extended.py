import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from cyberred.agents.recon import ReconAgent
from cyberred.core.models import Finding

@pytest.fixture
def mock_dependencies():
    return {
        "event_bus": AsyncMock(),
        "scope_validator": MagicMock(),
        "kali_execute": AsyncMock()
    }

@pytest.fixture
def recon_agent(mock_dependencies):
    import uuid
    with patch("cyberred.agents.recon.ReconAgent._get_scope_validator", return_value=mock_dependencies["scope_validator"]):
        agent = ReconAgent(
            agent_id=str(uuid.uuid4()),  # Must be valid UUID
            engagement_id="test-eng",
            target="192.168.1.1",
            event_bus=mock_dependencies["event_bus"]
        )
        return agent

class TestReconAgentExtended:

    @pytest.mark.asyncio
    async def test_strategy_adaptation_nmap(self, recon_agent):
        """Test nmap command adapts to strategy."""
        # Default behavior (standard)
        cmd_default = recon_agent._generate_nmap_command("192.168.1.1")
        assert "-T4" not in cmd_default and "-T2" not in cmd_default # Assuming standard is T3
        
        # Aggressive
        await recon_agent.on_signal("strategies:test-eng", {"strategy": "aggressive"})
        cmd_aggressive = recon_agent._generate_nmap_command("192.168.1.1")
        assert "-T4" in cmd_aggressive
        
        # Stealth
        await recon_agent.on_signal("strategies:test-eng", {"strategy": "stealth"})
        cmd_stealth = recon_agent._generate_nmap_command("192.168.1.1")
        assert "-T2" in cmd_stealth

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, recon_agent):
        """Test execute_recon stops when agent is stopped."""
        # Setup mock to simulate long running task or multiple steps
        async def delayed_execute(*args, **kwargs):
            await asyncio.sleep(0.01)
            result = MagicMock()
            result.success = True
            result.stdout = "out"
            result.stderr = ""
            result.exit_code = 0
            result.error_type = None
            return result

        mock_processed = MagicMock()
        mock_processed.findings = []

        with patch("cyberred.agents.recon.kali_execute", side_effect=delayed_execute) as mock_exec:
            with patch.object(recon_agent.output_processor, "process", return_value=mock_processed):
                # Start execution task
                task = asyncio.create_task(recon_agent.execute_recon())
                
                # Allow it to run a bit then stop. One tool takes 0.01s.
                # We wait 0.015s to let first one finish maybe.
                await asyncio.sleep(0.015)
                await recon_agent.stop()
                
                findings, actions = await task
                
                # Should not have executed ALL tools (5). Maybe 1 or 2.
                assert mock_exec.call_count < 5

    @pytest.mark.asyncio
    async def test_offline_buffering(self, recon_agent, mock_dependencies):
        """Test findings are buffered if EventBus fails."""
        mock_dependencies["event_bus"].publish.side_effect = Exception("Connection lost")
        
        await recon_agent.on_finding("hash", "type", {"val": 1})
        
        assert len(recon_agent._finding_buffer) == 1
        # buffer structure: {"channel": ch, "message": msg}
        # msg structure: {"agent_id": ..., "data": content}
        buffered_msg = recon_agent._finding_buffer[0]["message"]
        assert buffered_msg["data"]["val"] == 1

    @pytest.mark.asyncio
    async def test_buffer_flush_on_reconnect(self, recon_agent, mock_dependencies):
        """Test buffered findings are flushed on next successful publish."""
        recon_agent._finding_buffer = [{"channel": "c", "message": {"m": 1}}]
        
        # One success
        mock_dependencies["event_bus"].publish.side_effect = None
        
        await recon_agent.on_finding("hash", "type", {"val": 2})
        
        # Should publish the buffered one AND the new one
        assert mock_dependencies["event_bus"].publish.call_count == 2
        assert len(recon_agent._finding_buffer) == 0
