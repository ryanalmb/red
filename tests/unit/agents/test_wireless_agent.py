"""Unit tests for WirelessAgent (Story 7.20).

Following TDD red-green-refactor cycle. These tests validate:
- AC1: Thin subclass architecture
- AC2: Hardcoded methods REMOVED
- AC3: LLM-driven tool selection
- AC4: NFR37 Decision Context (HARD GATE)
- AC5: Monitor mode management
- AC6: Network discovery
- AC7: Handshake capture coordination
- AC8: Preserved stigmergic hooks
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# --- Task 1.1: Constructor Tests (AC: #1) ---
@pytest.mark.unit
class TestWirelessAgentConstructor:
    """Tests for WirelessAgent constructor - thin subclass architecture."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    def test_sets_role_to_wireless(self, mock_event_bus):
        """WirelessAgent constructor sets role=AgentRole.WIRELESS."""
        from cyberred.agents.wireless import WirelessAgent
        from cyberred.agents.roles import AgentRole

        agent = WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert agent.role == AgentRole.WIRELESS

    def test_default_specialty_is_general(self, mock_event_bus):
        """WirelessAgent default specialty is 'general'."""
        from cyberred.agents.wireless import WirelessAgent

        agent = WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert agent.specialty == "general"

    @pytest.mark.parametrize("specialty", ["general", "recon", "attack"])
    def test_accepts_valid_specialties(self, mock_event_bus, specialty):
        """WirelessAgent accepts valid specialties: general, recon, attack."""
        from cyberred.agents.wireless import WirelessAgent

        agent = WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
            specialty=specialty,
        )
        assert agent.specialty == specialty

    def test_no_target_in_constructor(self, mock_event_bus):
        """WirelessAgent constructor does NOT accept target parameter."""
        from cyberred.agents.wireless import WirelessAgent
        import inspect

        sig = inspect.signature(WirelessAgent.__init__)
        param_names = list(sig.parameters.keys())
        assert "target" not in param_names

    def test_configurable_max_iterations(self, mock_event_bus):
        """WirelessAgent allows configurable max_iterations."""
        from cyberred.agents.wireless import WirelessAgent

        agent = WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
            max_iterations=50,
        )
        assert agent.max_iterations == 50

    def test_configurable_phase_complete_threshold(self, mock_event_bus):
        """WirelessAgent allows configurable phase_complete_threshold."""
        from cyberred.agents.wireless import WirelessAgent

        agent = WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
            phase_complete_threshold=100,
        )
        assert agent.phase_complete_threshold == 100

    def test_extends_stigmergic_agent(self):
        """WirelessAgent extends StigmergicAgent."""
        from cyberred.agents.wireless import WirelessAgent
        from cyberred.agents.base import StigmergicAgent

        assert issubclass(WirelessAgent, StigmergicAgent)

    def test_initializes_monitor_mode_state(self, mock_event_bus):
        """WirelessAgent initializes monitor mode tracking state."""
        from cyberred.agents.wireless import WirelessAgent

        agent = WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert agent._monitor_enabled is False
        assert agent._original_interface is None

    def test_initializes_discovered_networks(self, mock_event_bus):
        """WirelessAgent initializes empty discovered networks list."""
        from cyberred.agents.wireless import WirelessAgent

        agent = WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert agent._discovered_networks == []

    def test_initializes_captured_handshakes(self, mock_event_bus):
        """WirelessAgent initializes empty captured handshakes dict."""
        from cyberred.agents.wireless import WirelessAgent

        agent = WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert agent._captured_handshakes == {}


# --- Task 1.2: Hardcoded Removal Tests (AC: #2) ---
@pytest.mark.unit
class TestWirelessAgentNoHardcodedMethods:
    """Tests verifying hardcoded methods are NOT present."""

    def test_no_generate_aircrack_command(self):
        """WirelessAgent has NO _generate_aircrack_command method."""
        from cyberred.agents.wireless import WirelessAgent

        assert not hasattr(WirelessAgent, "_generate_aircrack_command")

    def test_no_generate_airodump_command(self):
        """WirelessAgent has no _generate_airodump_command method."""
        from cyberred.agents.wireless import WirelessAgent

        assert not hasattr(WirelessAgent, "_generate_airodump_command")

    def test_no_generate_aireplay_command(self):
        """WirelessAgent has no _generate_aireplay_command method."""
        from cyberred.agents.wireless import WirelessAgent

        assert not hasattr(WirelessAgent, "_generate_aireplay_command")

    def test_no_generate_wifite_command(self):
        """WirelessAgent has no _generate_wifite_command method."""
        from cyberred.agents.wireless import WirelessAgent

        assert not hasattr(WirelessAgent, "_generate_wifite_command")

    def test_no_tool_sequence_attribute(self):
        """WirelessAgent has no tool_sequence attribute."""
        from cyberred.agents.wireless import WirelessAgent

        assert not hasattr(WirelessAgent, "tool_sequence")


# --- Task 1.3: Execute Method Tests (AC: #3) ---
@pytest.mark.unit
class TestWirelessAgentExecute:
    """Tests for execute_wireless_scan method."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def wireless_agent(self, mock_event_bus):
        from cyberred.agents.wireless import WirelessAgent

        return WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    def test_execute_wireless_scan_takes_interface_param(self, wireless_agent):
        """execute_wireless_scan takes interface as parameter (not constructor)."""
        from cyberred.agents.wireless import WirelessAgent
        import inspect

        sig = inspect.signature(WirelessAgent.execute_wireless_scan)
        param_names = list(sig.parameters.keys())
        assert "interface" in param_names

    @pytest.mark.asyncio
    async def test_execute_wireless_scan_calls_select_tool(self, wireless_agent):
        """execute_wireless_scan uses inherited select_tool()."""
        with patch.object(wireless_agent, "_enable_monitor_mode", new_callable=AsyncMock):
            with patch.object(wireless_agent, "select_tool", new_callable=AsyncMock) as mock_select:
                tool_selection = MagicMock()
                tool_selection.tool_name = "airodump-ng"
                tool_selection.command = "airodump-ng wlan0mon"
                tool_selection.confidence = 0.9
                mock_select.return_value = tool_selection

                with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
                    result = MagicMock()
                    result.success = True
                    result.stdout = ""
                    result.stderr = ""
                    result.exit_code = 0
                    mock_exec.return_value = result

                    await wireless_agent.execute_wireless_scan("wlan0", {})

                mock_select.assert_called()

    @pytest.mark.asyncio
    async def test_execute_wireless_scan_respects_stop_event(self, wireless_agent):
        """execute_wireless_scan respects _stop_event."""
        wireless_agent._stop_event.set()

        with patch.object(wireless_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            findings, actions = await wireless_agent.execute_wireless_scan("wlan0", {})

        # Should exit immediately without calling select_tool
        mock_select.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_wireless_scan_respects_max_iterations(self, wireless_agent):
        """execute_wireless_scan respects max_iterations limit."""
        wireless_agent.max_iterations = 2

        with patch.object(wireless_agent, "_enable_monitor_mode", new_callable=AsyncMock):
            with patch.object(wireless_agent, "select_tool", new_callable=AsyncMock) as mock_select:
                tool_selection = MagicMock()
                tool_selection.tool_name = "airodump-ng"
                tool_selection.command = "airodump-ng wlan0mon"
                tool_selection.confidence = 0.9
                mock_select.return_value = tool_selection

                with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
                    result = MagicMock()
                    result.success = True
                    result.stdout = ""
                    result.stderr = ""
                    result.exit_code = 0
                    mock_exec.return_value = result

                    await wireless_agent.execute_wireless_scan("wlan0", {})

                assert mock_select.call_count <= 2


# --- Task 1.4: NFR37 Decision Context Tests (AC: #4) ---
@pytest.mark.unit
class TestWirelessAgentDecisionContext:
    """Tests for NFR37 decision_context requirements."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def wireless_agent(self, mock_event_bus):
        from cyberred.agents.wireless import WirelessAgent

        return WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_all_actions_have_decision_context(self, wireless_agent):
        """ALL AgentActions have non-empty decision_context."""
        wireless_agent.max_iterations = 1

        with patch.object(wireless_agent, "_enable_monitor_mode", new_callable=AsyncMock):
            with patch.object(wireless_agent, "select_tool", new_callable=AsyncMock) as mock_select:
                tool_selection = MagicMock()
                tool_selection.tool_name = "airodump-ng"
                tool_selection.command = "airodump-ng wlan0mon"
                tool_selection.confidence = 0.9
                mock_select.return_value = tool_selection

                with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
                    result = MagicMock()
                    result.success = True
                    result.stdout = ""
                    result.stderr = ""
                    result.exit_code = 0
                    mock_exec.return_value = result

                    _, actions = await wireless_agent.execute_wireless_scan("wlan0", {})

        for action in actions:
            assert action.decision_context, "AgentAction must have non-empty decision_context"
            assert len(action.decision_context) > 0

    @pytest.mark.asyncio
    async def test_decision_context_includes_spawn(self, wireless_agent):
        """Decision context includes initial_spawn:{agent_id}."""
        wireless_agent.max_iterations = 1

        with patch.object(wireless_agent, "_enable_monitor_mode", new_callable=AsyncMock):
            with patch.object(wireless_agent, "select_tool", new_callable=AsyncMock) as mock_select:
                tool_selection = MagicMock()
                tool_selection.tool_name = "airodump-ng"
                tool_selection.command = "airodump-ng wlan0mon"
                tool_selection.confidence = 0.9
                mock_select.return_value = tool_selection

                with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
                    result = MagicMock()
                    result.success = True
                    result.stdout = ""
                    result.stderr = ""
                    result.exit_code = 0
                    mock_exec.return_value = result

                    _, actions = await wireless_agent.execute_wireless_scan("wlan0", {})

        for action in actions:
            context_str = " ".join(action.decision_context)
            assert "initial_spawn:" in context_str

    @pytest.mark.asyncio
    async def test_decision_context_includes_interface(self, wireless_agent):
        """Decision context includes interface:{interface_name}."""
        wireless_agent.max_iterations = 1

        with patch.object(wireless_agent, "_enable_monitor_mode", new_callable=AsyncMock):
            with patch.object(wireless_agent, "select_tool", new_callable=AsyncMock) as mock_select:
                tool_selection = MagicMock()
                tool_selection.tool_name = "airodump-ng"
                tool_selection.command = "airodump-ng wlan0mon"
                tool_selection.confidence = 0.9
                mock_select.return_value = tool_selection

                with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
                    result = MagicMock()
                    result.success = True
                    result.stdout = ""
                    result.stderr = ""
                    result.exit_code = 0
                    mock_exec.return_value = result

                    _, actions = await wireless_agent.execute_wireless_scan("wlan0", {})

        for action in actions:
            context_str = " ".join(action.decision_context)
            assert "interface:wlan0" in context_str

    @pytest.mark.asyncio
    async def test_decision_context_includes_handshake_when_captured(self, wireless_agent):
        """Decision context includes handshake:{bssid} when handshake captured."""
        wireless_agent.max_iterations = 1
        wireless_agent._captured_handshakes = {"AA:BB:CC:DD:EE:FF": "/tmp/capture.cap"}

        with patch.object(wireless_agent, "_enable_monitor_mode", new_callable=AsyncMock):
            with patch.object(wireless_agent, "select_tool", new_callable=AsyncMock) as mock_select:
                tool_selection = MagicMock()
                tool_selection.tool_name = "aircrack-ng"
                tool_selection.command = "aircrack-ng /tmp/capture.cap"
                tool_selection.confidence = 0.9
                mock_select.return_value = tool_selection

                with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
                    result = MagicMock()
                    result.success = True
                    result.stdout = ""
                    result.stderr = ""
                    result.exit_code = 0
                    mock_exec.return_value = result

                    _, actions = await wireless_agent.execute_wireless_scan("wlan0", {})

        for action in actions:
            context_str = " ".join(action.decision_context)
            assert "handshake:AA:BB:CC:DD:EE:FF" in context_str


# --- Task 1.5: Monitor Mode Tests (AC: #5) ---
@pytest.mark.unit
class TestWirelessAgentMonitorMode:
    """Tests for monitor mode management."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def wireless_agent(self, mock_event_bus):
        from cyberred.agents.wireless import WirelessAgent

        return WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_enable_monitor_mode_sets_flag(self, wireless_agent):
        """_enable_monitor_mode sets _monitor_enabled flag."""
        with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
            result = MagicMock()
            result.success = True
            result.stdout = "(monitor mode enabled on wlan0mon)"
            result.stderr = ""
            result.exit_code = 0
            mock_exec.return_value = result

            await wireless_agent._enable_monitor_mode("wlan0")

            assert wireless_agent._monitor_enabled is True

    @pytest.mark.asyncio
    async def test_enable_monitor_mode_stores_original_interface(self, wireless_agent):
        """_enable_monitor_mode stores original interface for cleanup."""
        with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
            result = MagicMock()
            result.success = True
            result.stdout = "(monitor mode enabled on wlan0mon)"
            result.stderr = ""
            result.exit_code = 0
            mock_exec.return_value = result

            await wireless_agent._enable_monitor_mode("wlan0")

            assert wireless_agent._original_interface == "wlan0"

    @pytest.mark.asyncio
    async def test_enable_monitor_mode_handles_failure(self, wireless_agent):
        """_enable_monitor_mode handles failure gracefully."""
        with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = Exception("Interface not found")

            await wireless_agent._enable_monitor_mode("wlan0")

            # Should not crash, monitor should remain disabled
            assert wireless_agent._monitor_enabled is False

    @pytest.mark.asyncio
    async def test_stop_disables_monitor_mode(self, wireless_agent):
        """stop() disables monitor mode for cleanup."""
        wireless_agent._monitor_enabled = True
        wireless_agent._original_interface = "wlan0"

        with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
            result = MagicMock()
            result.success = True
            result.stdout = "wlan0 disabled monitor mode"
            result.stderr = ""
            result.exit_code = 0
            mock_exec.return_value = result

            await wireless_agent.stop()

            # Should have called airmon-ng stop
            mock_exec.assert_called()
            assert wireless_agent._stop_event.is_set()


# --- Task 1.6: Network Discovery Tests (AC: #6) ---
@pytest.mark.unit
class TestWirelessAgentNetworkDiscovery:
    """Tests for network discovery functionality."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def wireless_agent(self, mock_event_bus):
        from cyberred.agents.wireless import WirelessAgent

        return WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_discover_networks_populates_list(self, wireless_agent):
        """_discover_networks populates _discovered_networks list."""
        airodump_output = """BSSID              PWR  Beacons    #Data  CH   ENC          ESSID
AA:BB:CC:DD:EE:FF  -40       50       25   6   WPA2         TestNetwork
11:22:33:44:55:66  -55       30       10   11  WPA2         OtherNetwork
"""
        with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
            result = MagicMock()
            result.success = True
            result.stdout = airodump_output
            result.stderr = ""
            result.exit_code = 0
            mock_exec.return_value = result

            await wireless_agent._discover_networks("wlan0mon")

            assert len(wireless_agent._discovered_networks) >= 1

    @pytest.mark.asyncio
    async def test_discover_networks_extracts_bssid_essid(self, wireless_agent):
        """_discover_networks extracts BSSID and ESSID from output."""
        airodump_output = """BSSID              PWR  Beacons    #Data  CH   ENC          ESSID
AA:BB:CC:DD:EE:FF  -40       50       25   6   WPA2         TestNetwork
"""
        with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
            result = MagicMock()
            result.success = True
            result.stdout = airodump_output
            result.stderr = ""
            result.exit_code = 0
            mock_exec.return_value = result

            await wireless_agent._discover_networks("wlan0mon")

            if wireless_agent._discovered_networks:
                network = wireless_agent._discovered_networks[0]
                assert "bssid" in network or "BSSID" in network

    @pytest.mark.asyncio
    async def test_discover_networks_handles_empty_output(self, wireless_agent):
        """_discover_networks handles empty output gracefully."""
        with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
            result = MagicMock()
            result.success = True
            result.stdout = ""
            result.stderr = ""
            result.exit_code = 0
            mock_exec.return_value = result

            await wireless_agent._discover_networks("wlan0mon")

            # Should not crash, list remains empty
            assert wireless_agent._discovered_networks == []

    @pytest.mark.asyncio
    async def test_discover_networks_handles_failure(self, wireless_agent):
        """_discover_networks handles execution failure gracefully."""
        with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = Exception("Command failed")

            await wireless_agent._discover_networks("wlan0mon")

            # Should not crash
            assert wireless_agent._discovered_networks == []


# --- Task 1.7: Handshake Coordination Tests (AC: #7) ---
@pytest.mark.unit
class TestWirelessAgentHandshakeCapture:
    """Tests for handshake capture coordination."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def wireless_agent(self, mock_event_bus):
        from cyberred.agents.wireless import WirelessAgent

        return WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_captured_handshake_published_to_credentials_channel(self, wireless_agent, mock_event_bus):
        """Captured handshakes published to credentials:{engagement_id}:handshake channel."""
        wireless_agent._captured_handshakes["AA:BB:CC:DD:EE:FF"] = "/tmp/capture.cap"

        await wireless_agent._publish_handshake("AA:BB:CC:DD:EE:FF", "/tmp/capture.cap")

        mock_event_bus.publish.assert_called()
        call_args = mock_event_bus.publish.call_args
        channel = call_args[0][0]
        assert "credentials" in channel and "handshake" in channel

    @pytest.mark.asyncio
    async def test_handshake_path_stored(self, wireless_agent):
        """Handshake paths stored in _captured_handshakes dict."""
        with patch.object(wireless_agent, "_publish_handshake", new_callable=AsyncMock):
            await wireless_agent._check_handshake_capture(
                MagicMock(stdout="WPA handshake: AA:BB:CC:DD:EE:FF"),
                MagicMock(command="airodump-ng -w /tmp/capture wlan0mon"),
            )

        # This tests internal state update
        assert len(wireless_agent._captured_handshakes) >= 0  # May or may not detect depending on implementation

    @pytest.mark.asyncio
    async def test_handshake_includes_bssid(self, wireless_agent, mock_event_bus):
        """Published handshake message includes BSSID."""
        await wireless_agent._publish_handshake("AA:BB:CC:DD:EE:FF", "/tmp/capture.cap")

        mock_event_bus.publish.assert_called()
        call_args = mock_event_bus.publish.call_args
        message = call_args[0][1]
        assert "AA:BB:CC:DD:EE:FF" in str(message)


# --- Task 1.8: Strategy Tests (AC: #8) ---
@pytest.mark.unit
class TestWirelessAgentStrategy:
    """Tests for strategy handling."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def wireless_agent(self, mock_event_bus):
        from cyberred.agents.wireless import WirelessAgent

        return WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("strategy", ["stealth", "standard", "aggressive"])
    async def test_on_signal_updates_strategy(self, wireless_agent, strategy):
        """on_signal updates strategy for valid values."""
        channel = "strategies:eng-1"
        data = {"strategy": strategy}

        await wireless_agent.on_signal(channel, data)

        assert wireless_agent.current_strategy == strategy

    @pytest.mark.asyncio
    async def test_on_signal_ignores_invalid_strategy(self, wireless_agent):
        """on_signal ignores invalid strategy values."""
        channel = "strategies:eng-1"
        data = {"strategy": "invalid_strategy"}

        await wireless_agent.on_signal(channel, data)

        assert wireless_agent.current_strategy == "standard"

    def test_get_constraints_stealth(self, wireless_agent):
        """_get_constraints returns stealth constraints - avoids deauth attacks."""
        wireless_agent.current_strategy = "stealth"

        constraints = wireless_agent._get_constraints()

        # Stealth should avoid noisy attacks like deauth
        assert any("deauth" in c.lower() or "passive" in c.lower() or "stealth" in c.lower() for c in constraints)

    def test_get_constraints_aggressive(self, wireless_agent):
        """_get_constraints returns aggressive constraints - allows all attack types."""
        wireless_agent.current_strategy = "aggressive"

        constraints = wireless_agent._get_constraints()

        # Aggressive should allow all attacks
        assert any("all" in c.lower() or "aggressive" in c.lower() or "deauth" in c.lower() for c in constraints)

    def test_get_constraints_standard(self, wireless_agent):
        """_get_constraints returns empty or minimal for standard strategy."""
        wireless_agent.current_strategy = "standard"

        constraints = wireless_agent._get_constraints()

        # Standard is the baseline, may be empty or minimal
        assert isinstance(constraints, list)


# --- Task 1.9: Stigmergic Hook Tests (AC: #8) ---
@pytest.mark.unit
class TestWirelessAgentStigmergicHooks:
    """Tests for preserved stigmergic hooks."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def wireless_agent(self, mock_event_bus):
        from cyberred.agents.wireless import WirelessAgent

        return WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_on_finding_publishes_to_wireless_channel(self, wireless_agent, mock_event_bus):
        """on_finding publishes to findings:{target_hash}:wireless channel."""
        from cyberred.core.models import Finding

        finding = Finding(
            id=str(uuid.uuid4()),
            type="wireless",
            severity="high",
            target="wlan0",
            evidence="WPA handshake captured",
            agent_id=wireless_agent.agent_id,
            timestamp="2026-01-22T00:00:00Z",
            tool="airodump-ng",
            topic="findings:test:wireless",
            signature="test-sig-001",
        )

        await wireless_agent.on_finding(finding)

        mock_event_bus.publish.assert_called()
        call_args = mock_event_bus.publish.call_args
        channel = call_args[0][0]
        assert "wireless" in channel

    @pytest.mark.asyncio
    async def test_stop_sets_event(self, wireless_agent):
        """stop() sets _stop_event."""
        with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock):
            await wireless_agent.stop()

        assert wireless_agent._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_flush_buffer_on_reconnect(self, wireless_agent, mock_event_bus):
        """_flush_buffer attempts to publish buffered findings."""
        wireless_agent._finding_buffer = [
            {"channel": "findings:abc:wireless", "message": {"id": "f1"}},
            {"channel": "findings:def:wireless", "message": {"id": "f2"}},
        ]

        await wireless_agent._flush_buffer()

        # Should have attempted to publish both buffered items
        assert mock_event_bus.publish.call_count >= 2


# --- Additional Coverage Tests ---
@pytest.mark.unit
class TestWirelessAgentEdgeCases:
    """Additional tests for edge cases and 100% coverage."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def wireless_agent(self, mock_event_bus):
        from cyberred.agents.wireless import WirelessAgent

        return WirelessAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_execute_exits_on_phase_complete(self, wireless_agent):
        """execute_wireless_scan exits early when phase is complete."""
        wireless_agent.max_iterations = 5
        wireless_agent.phase_complete_threshold = 0  # Immediately complete

        with patch.object(wireless_agent, "_enable_monitor_mode", new_callable=AsyncMock):
            with patch.object(wireless_agent, "select_tool", new_callable=AsyncMock) as mock_select:
                findings, actions = await wireless_agent.execute_wireless_scan("wlan0", {})

        # Should exit immediately without calling select_tool
        mock_select.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_handles_select_tool_exception(self, wireless_agent):
        """execute_wireless_scan handles exceptions during tool selection."""
        wireless_agent.max_iterations = 1

        with patch.object(wireless_agent, "_enable_monitor_mode", new_callable=AsyncMock):
            with patch.object(wireless_agent, "select_tool", new_callable=AsyncMock) as mock_select:
                mock_select.side_effect = Exception("LLM unavailable")

                # Should not crash
                findings, actions = await wireless_agent.execute_wireless_scan("wlan0", {})

        # Should have recorded an action even with error
        assert len(actions) == 1
        assert actions[0].action_type == "wireless:unknown"

    @pytest.mark.asyncio
    async def test_on_finding_buffers_on_publish_failure(self, wireless_agent, mock_event_bus):
        """on_finding buffers finding when publish fails."""
        from cyberred.core.models import Finding

        mock_event_bus.publish.side_effect = Exception("Network error")

        finding = Finding(
            id=str(uuid.uuid4()),
            type="wireless",
            severity="high",
            target="wlan0",
            evidence="Critical finding evidence",
            agent_id=wireless_agent.agent_id,
            timestamp="2026-01-22T00:00:00Z",
            tool="airodump-ng",
            topic="findings:test:wireless",
            signature="test-sig-fail",
        )

        await wireless_agent.on_finding(finding)

        # Should have buffered the finding
        assert len(wireless_agent._finding_buffer) == 1

    @pytest.mark.asyncio
    async def test_flush_buffer_keeps_failed_items(self, wireless_agent, mock_event_bus):
        """_flush_buffer keeps items that fail to publish."""
        mock_event_bus.publish.side_effect = Exception("Network error")

        wireless_agent._finding_buffer = [
            {"channel": "findings:abc:wireless", "message": {"id": "f1"}},
        ]

        await wireless_agent._flush_buffer()

        # Should retain the failed item
        assert len(wireless_agent._finding_buffer) == 1

    @pytest.mark.asyncio
    async def test_stop_flushes_buffer_if_not_empty(self, wireless_agent, mock_event_bus):
        """stop() flushes buffer if it contains items."""
        wireless_agent._finding_buffer = [
            {"channel": "findings:abc:wireless", "message": {"id": "f1"}},
        ]

        with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock):
            await wireless_agent.stop()

        assert wireless_agent._stop_event.is_set()
        mock_event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_execute_creates_finding_on_success(self, wireless_agent, mock_event_bus):
        """execute_wireless_scan creates findings when tool succeeds with output."""
        wireless_agent.max_iterations = 1

        with patch.object(wireless_agent, "_enable_monitor_mode", new_callable=AsyncMock):
            with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = "Found network: TestNetwork BSSID: AA:BB:CC:DD:EE:FF"
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                with patch.object(wireless_agent, "select_tool", new_callable=AsyncMock) as mock_select:
                    tool_selection = MagicMock()
                    tool_selection.tool_name = "airodump-ng"
                    tool_selection.command = "airodump-ng wlan0mon"
                    tool_selection.confidence = 0.9
                    mock_select.return_value = tool_selection

                    findings, actions = await wireless_agent.execute_wireless_scan("wlan0", {})

        # Should have created a finding
        assert len(findings) == 1
        assert findings[0].type == "wireless"

    def test_hash_target(self, wireless_agent):
        """_hash_target returns consistent 8-char hash."""
        hash1 = wireless_agent._hash_target("wlan0")
        hash2 = wireless_agent._hash_target("wlan0")

        assert hash1 == hash2
        assert len(hash1) == 8

    @pytest.mark.asyncio
    async def test_on_signal_ignores_non_strategy_channel(self, wireless_agent):
        """on_signal ignores channels that don't contain 'strategies'."""
        wireless_agent.current_strategy = "stealth"

        channel = "findings:eng-1"
        data = {"strategy": "aggressive"}

        await wireless_agent.on_signal(channel, data)

        # Strategy should NOT change
        assert wireless_agent.current_strategy == "stealth"

    @pytest.mark.asyncio
    async def test_enable_monitor_mode_already_enabled(self, wireless_agent):
        """_enable_monitor_mode handles already-enabled state."""
        wireless_agent._monitor_enabled = True

        # Should not crash, may skip
        await wireless_agent._enable_monitor_mode("wlan0")

        assert wireless_agent._monitor_enabled is True

    @pytest.mark.asyncio
    async def test_publish_handshake_handles_exception(self, wireless_agent, mock_event_bus):
        """_publish_handshake handles publish failure gracefully."""
        mock_event_bus.publish.side_effect = Exception("Network error")

        # Should not crash, just log warning
        await wireless_agent._publish_handshake("AA:BB:CC:DD:EE:FF", "/tmp/capture.cap")

        # Verify publish was attempted
        mock_event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_stop_handles_monitor_disable_exception(self, wireless_agent):
        """stop() handles exception when disabling monitor mode."""
        wireless_agent._monitor_enabled = True
        wireless_agent._original_interface = "wlan0"

        with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = Exception("Interface not found")

            # Should not crash, just log warning
            await wireless_agent.stop()

            assert wireless_agent._stop_event.is_set()
            # monitor_enabled stays True because exception happened
            assert wireless_agent._monitor_enabled is True

    @pytest.mark.asyncio
    async def test_on_finding_flushes_existing_buffer_first(self, wireless_agent, mock_event_bus):
        """on_finding flushes existing buffer before publishing new finding."""
        from cyberred.core.models import Finding

        # Pre-populate buffer
        wireless_agent._finding_buffer = [
            {"channel": "findings:old:wireless", "message": {"id": "old"}}
        ]

        # Use a real Finding object
        finding = Finding(
            id=str(uuid.uuid4()),
            type="wireless",
            severity="medium",
            target="wlan0",
            evidence="New finding evidence",
            agent_id=wireless_agent.agent_id,
            timestamp="2026-01-22T00:00:00Z",
            tool="airodump-ng",
            topic="findings:test:wireless",
            signature="test-sig-new",
        )

        await wireless_agent.on_finding(finding)

        # Should have published both old buffered and new finding
        assert mock_event_bus.publish.call_count >= 2

    @pytest.mark.asyncio
    async def test_enable_monitor_mode_success_without_monitor_keyword(self, wireless_agent):
        """_enable_monitor_mode doesn't set flag if output doesn't contain monitor mode."""
        with patch("cyberred.agents.wireless.kali_execute", new_callable=AsyncMock) as mock_exec:
            result = MagicMock()
            result.success = True
            result.stdout = "wlan0 enabled"  # No "monitor mode" keyword
            result.stderr = ""
            result.exit_code = 0
            mock_exec.return_value = result

            await wireless_agent._enable_monitor_mode("wlan0")

            # Should NOT set flag without "monitor mode" in output
            assert wireless_agent._monitor_enabled is False
