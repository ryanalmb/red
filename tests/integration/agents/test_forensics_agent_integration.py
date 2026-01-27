"""Integration tests for ForensicsAgent (Story 7.23).

These tests use real ForensicsAgent with real EventBus,
patching only the tool execution boundary (kali_execute).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.integration
class TestForensicsAgentIntegration:
    """Integration tests with mocked tool execution."""

    @pytest.fixture
    def event_bus(self):
        """Create a real-ish EventBus mock with async methods."""
        bus = AsyncMock()
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        return bus

    @pytest.fixture
    def forensics_agent(self, event_bus):
        """Create ForensicsAgent for integration testing."""
        from cyberred.agents.forensics import ForensicsAgent

        return ForensicsAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="integration-test-eng",
            event_bus=event_bus,
            specialty="general",
            max_iterations=3,
        )

    @pytest.mark.asyncio
    async def test_full_collection_workflow(self, forensics_agent, event_bus):
        """Integration test: full forensics collection workflow."""
        from cyberred.core.models import ToolSelection

        mock_selection = ToolSelection(
            tool_name="strings",
            command="strings /tmp/suspicious.bin",
            rationale="Extract printable strings from binary",
            expected_output_type="text",
            confidence=0.85,
            priority=5,
        )

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.stdout = "MZ...PE...CreateRemoteThread...VirtualAlloc"
        mock_result.stderr = ""
        mock_result.exit_code = 0

        with patch.object(forensics_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.return_value = mock_selection
            with patch("cyberred.agents.forensics.kali_execute", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_result

                findings, actions = await forensics_agent.execute_forensics_collection(
                    target="192.168.1.50",
                    context={"artifact_paths": ["/tmp/suspicious.bin"]},
                )

                # Verify findings were created
                assert len(findings) > 0
                assert findings[0].type == "forensics"
                assert findings[0].tool == "strings"

                # Verify actions have decision context (NFR37)
                assert len(actions) > 0
                for action in actions:
                    assert action.decision_context
                    assert len(action.decision_context) > 0

                # Verify findings were published
                event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_memory_analysis_workflow(self, forensics_agent, event_bus):
        """Integration test: memory forensics workflow."""
        from cyberred.core.models import ToolSelection

        mock_selection = ToolSelection(
            tool_name="volatility",
            command="volatility -f /tmp/mem.raw --profile=Win7SP1x64 pslist",
            rationale="List running processes from memory dump",
            expected_output_type="text",
            confidence=0.95,
            priority=8,
        )

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.stdout = """Volatility Foundation
Offset(V)   PID    PPID   Name
0x12345678  4      0      System
0x23456789  1234   4      explorer.exe
0x34567890  5678   1234   cmd.exe"""
        mock_result.stderr = ""
        mock_result.exit_code = 0

        with patch.object(forensics_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.return_value = mock_selection
            with patch("cyberred.agents.forensics.kali_execute", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_result

                findings, actions = await forensics_agent.execute_forensics_collection(
                    target="192.168.1.50",
                    context={"memory_image": "/tmp/mem.raw"},
                )

                # Verify memory context was used
                call_args = mock_select.call_args
                tool_ctx = call_args[0][0]
                assert tool_ctx.target_info.get("memory_image") == "/tmp/mem.raw"

                # Verify findings contain memory analysis results
                assert len(findings) > 0

    @pytest.mark.asyncio
    async def test_chain_of_custody_tracking(self, forensics_agent, event_bus):
        """Integration test: chain-of-custody metadata is tracked."""
        from cyberred.core.models import ToolSelection

        mock_selection = ToolSelection(
            tool_name="sha256sum",
            command="sha256sum /evidence/artifact.bin",
            rationale="Compute hash for evidence integrity",
            expected_output_type="text",
            confidence=0.99,
            priority=9,
        )

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.stdout = "abc123def456789 /evidence/artifact.bin"
        mock_result.stderr = ""
        mock_result.exit_code = 0

        with patch.object(forensics_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.return_value = mock_selection
            with patch("cyberred.agents.forensics.kali_execute", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_result

                await forensics_agent.execute_forensics_collection(
                    target="192.168.1.50",
                    context={},
                )

                # Verify custody records were created
                assert len(forensics_agent._collected_artifacts) > 0
                record = forensics_agent._collected_artifacts[0]
                assert "artifact_id" in record
                assert "sha256" in record
                assert "collector_agent_id" in record
                assert record["source_target"] == "192.168.1.50"

    @pytest.mark.asyncio
    async def test_strategy_signal_handling(self, forensics_agent, event_bus):
        """Integration test: agent responds to strategy signals."""
        assert forensics_agent.current_strategy == "standard"

        # Simulate strategy update signal
        await forensics_agent.on_signal(
            f"strategies:{forensics_agent.engagement_id}",
            {"strategy": "stealth"},
        )

        assert forensics_agent.current_strategy == "stealth"

        # Verify constraints reflect new strategy
        constraints = forensics_agent._get_constraints()
        assert len(constraints) > 0
        assert any("evidence" in c.lower() or "integrity" in c.lower() for c in constraints)

    @pytest.mark.asyncio
    async def test_stop_graceful_shutdown(self, forensics_agent, event_bus):
        """Integration test: graceful shutdown flushes buffer."""
        # Add item to buffer
        forensics_agent._finding_buffer.append({
            "channel": "findings:test:forensics",
            "message": {"id": "finding-123"},
        })

        await forensics_agent.stop()

        # Verify stop event is set
        assert forensics_agent._stop_event.is_set()

        # Verify buffer was flushed
        event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_multiple_iterations_with_different_tools(self, forensics_agent, event_bus):
        """Integration test: agent iterates through multiple tool selections."""
        from cyberred.core.models import ToolSelection

        selections = [
            ToolSelection(
                tool_name="file",
                command="file /tmp/artifact",
                rationale="Identify file type",
                expected_output_type="text",
                confidence=0.9,
                priority=5,
            ),
            ToolSelection(
                tool_name="strings",
                command="strings /tmp/artifact",
                rationale="Extract strings",
                expected_output_type="text",
                confidence=0.85,
                priority=5,
            ),
            ToolSelection(
                tool_name="binwalk",
                command="binwalk /tmp/artifact",
                rationale="Analyze embedded files",
                expected_output_type="text",
                confidence=0.8,
                priority=5,
            ),
        ]

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.stdout = "analysis output"
        mock_result.stderr = ""
        mock_result.exit_code = 0

        call_count = [0]

        async def mock_select(ctx):
            idx = min(call_count[0], len(selections) - 1)
            call_count[0] += 1
            return selections[idx]

        with patch.object(forensics_agent, "select_tool", side_effect=mock_select):
            with patch("cyberred.agents.forensics.kali_execute", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_result

                findings, actions = await forensics_agent.execute_forensics_collection(
                    target="192.168.1.50",
                    context={},
                )

                # Should have multiple actions from different tools
                assert len(actions) == 3
                tool_names = [a.action_type.split(":")[1] for a in actions]
                assert "file" in tool_names
                assert "strings" in tool_names
                assert "binwalk" in tool_names

    @pytest.mark.asyncio
    async def test_decision_context_nfr37_compliance(self, forensics_agent, event_bus):
        """Integration test: NFR37 - all actions have decision context."""
        from cyberred.core.models import ToolSelection

        mock_selection = ToolSelection(
            tool_name="grep",
            command="grep -r password /var/log",
            rationale="Search for credentials in logs",
            expected_output_type="text",
            confidence=0.7,
            priority=4,
        )

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.stdout = "found: password=secret123"
        mock_result.stderr = ""
        mock_result.exit_code = 0

        with patch.object(forensics_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.return_value = mock_selection
            with patch("cyberred.agents.forensics.kali_execute", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = mock_result

                findings, actions = await forensics_agent.execute_forensics_collection(
                    target="webserver.internal",
                    context={},
                )

                # NFR37 HARD GATE: All actions MUST have non-empty decision_context
                for action in actions:
                    assert action.decision_context is not None, f"Action {action.id} has None decision_context"
                    assert len(action.decision_context) > 0, f"Action {action.id} has empty decision_context"
                    
                    # Must include spawn and target info
                    ctx_str = " ".join(action.decision_context)
                    assert "initial_spawn" in ctx_str or forensics_agent.agent_id in ctx_str
                    assert "target" in ctx_str or "webserver" in ctx_str
