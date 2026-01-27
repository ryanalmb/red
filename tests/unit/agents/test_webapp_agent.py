"""Unit tests for WebAppAgent (Story 7.19).

Following TDD red-green-refactor cycle. These tests validate:
- AC1: Thin subclass architecture
- AC2: Hardcoded methods REMOVED
- AC3: LLM-driven tool selection
- AC4: NFR37 Decision Context (HARD GATE)
- AC5: WAF detection & evasion
- AC6: Authenticated testing
- AC7: Preserved stigmergic hooks
"""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# --- Task 1.1: Constructor Tests (AC: #1) ---
@pytest.mark.unit
class TestWebAppAgentConstructor:
    """Tests for WebAppAgent constructor - thin subclass architecture."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    def test_sets_role_to_webapp(self, mock_event_bus):
        """WebAppAgent constructor sets role=AgentRole.WEBAPP."""
        from cyberred.agents.webapp import WebAppAgent
        from cyberred.agents.roles import AgentRole

        agent = WebAppAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert agent.role == AgentRole.WEBAPP

    def test_default_specialty_is_general(self, mock_event_bus):
        """WebAppAgent default specialty is 'general'."""
        from cyberred.agents.webapp import WebAppAgent

        agent = WebAppAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )
        assert agent.specialty == "general"

    @pytest.mark.parametrize("specialty", ["general", "api", "auth"])
    def test_accepts_valid_specialties(self, mock_event_bus, specialty):
        """WebAppAgent accepts valid specialties: general, api, auth."""
        from cyberred.agents.webapp import WebAppAgent

        agent = WebAppAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
            specialty=specialty,
        )
        assert agent.specialty == specialty

    def test_no_target_in_constructor(self, mock_event_bus):
        """WebAppAgent constructor does NOT accept target parameter."""
        from cyberred.agents.webapp import WebAppAgent
        import inspect

        sig = inspect.signature(WebAppAgent.__init__)
        param_names = list(sig.parameters.keys())
        assert "target" not in param_names

    def test_configurable_max_iterations(self, mock_event_bus):
        """WebAppAgent allows configurable max_iterations."""
        from cyberred.agents.webapp import WebAppAgent

        agent = WebAppAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
            max_iterations=50,
        )
        assert agent.max_iterations == 50

    def test_configurable_phase_complete_threshold(self, mock_event_bus):
        """WebAppAgent allows configurable phase_complete_threshold."""
        from cyberred.agents.webapp import WebAppAgent

        agent = WebAppAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
            phase_complete_threshold=100,
        )
        assert agent.phase_complete_threshold == 100

    def test_extends_stigmergic_agent(self):
        """WebAppAgent extends StigmergicAgent."""
        from cyberred.agents.webapp import WebAppAgent
        from cyberred.agents.base import StigmergicAgent

        assert issubclass(WebAppAgent, StigmergicAgent)


# --- Task 1.2: Hardcoded Removal Tests (AC: #2) ---
@pytest.mark.unit
class TestWebAppAgentNoHardcodedMethods:
    """Tests verifying hardcoded methods are NOT present."""

    def test_no_generate_nikto_command(self):
        """WebAppAgent has NO _generate_nikto_command method."""
        from cyberred.agents.webapp import WebAppAgent

        assert not hasattr(WebAppAgent, "_generate_nikto_command")

    def test_no_generate_sqlmap_command(self):
        """WebAppAgent has no _generate_sqlmap_command method."""
        from cyberred.agents.webapp import WebAppAgent

        assert not hasattr(WebAppAgent, "_generate_sqlmap_command")

    def test_no_generate_ffuf_command(self):
        """WebAppAgent has no _generate_ffuf_command method."""
        from cyberred.agents.webapp import WebAppAgent

        assert not hasattr(WebAppAgent, "_generate_ffuf_command")

    def test_no_tool_sequence_attribute(self):
        """WebAppAgent has no tool_sequence attribute."""
        from cyberred.agents.webapp import WebAppAgent

        assert not hasattr(WebAppAgent, "tool_sequence")


# --- Task 1.3: Execute Method Tests (AC: #3) ---
@pytest.mark.unit
class TestWebAppAgentExecute:
    """Tests for execute_webapp_scan method."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def mock_scope_validator(self):
        with patch("cyberred.agents.webapp.ScopeValidator") as mock:
            instance = mock.return_value
            instance.validate.return_value = True
            yield instance

    @pytest.fixture
    def webapp_agent(self, mock_event_bus, mock_scope_validator):
        from cyberred.agents.webapp import WebAppAgent

        return WebAppAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    def test_execute_webapp_scan_takes_target_param(self, webapp_agent):
        """execute_webapp_scan takes target as parameter (not constructor)."""
        from cyberred.agents.webapp import WebAppAgent
        import inspect

        sig = inspect.signature(WebAppAgent.execute_webapp_scan)
        param_names = list(sig.parameters.keys())
        assert "target" in param_names

    @pytest.mark.asyncio
    async def test_execute_webapp_scan_calls_select_tool(self, webapp_agent, mock_scope_validator):
        """execute_webapp_scan uses inherited select_tool()."""
        with patch.object(webapp_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "nikto"
            tool_selection.command = "nikto -h http://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.webapp.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                # Should call execute_webapp_scan with target parameter
                await webapp_agent.execute_webapp_scan("http://target.com", {})

            mock_select.assert_called()

    @pytest.mark.asyncio
    async def test_execute_webapp_scan_respects_stop_event(self, webapp_agent, mock_scope_validator):
        """execute_webapp_scan respects _stop_event."""
        webapp_agent._stop_event.set()

        with patch.object(webapp_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            findings, actions = await webapp_agent.execute_webapp_scan("http://target.com", {})

        # Should exit immediately without calling select_tool
        mock_select.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_webapp_scan_respects_max_iterations(self, webapp_agent, mock_scope_validator):
        """execute_webapp_scan respects max_iterations limit."""
        webapp_agent.max_iterations = 2

        with patch.object(webapp_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "nikto"
            tool_selection.command = "nikto -h http://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.webapp.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                await webapp_agent.execute_webapp_scan("http://target.com", {})

            assert mock_select.call_count <= 2


# --- Task 1.4: NFR37 Decision Context Tests (AC: #4) ---
@pytest.mark.unit
class TestWebAppAgentDecisionContext:
    """Tests for NFR37 decision_context requirements."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def mock_scope_validator(self):
        with patch("cyberred.agents.webapp.ScopeValidator") as mock:
            instance = mock.return_value
            instance.validate.return_value = True
            yield instance

    @pytest.fixture
    def webapp_agent(self, mock_event_bus, mock_scope_validator):
        from cyberred.agents.webapp import WebAppAgent

        return WebAppAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_all_actions_have_decision_context(self, webapp_agent, mock_scope_validator):
        """ALL AgentActions have non-empty decision_context."""
        webapp_agent.max_iterations = 1

        with patch.object(webapp_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "nikto"
            tool_selection.command = "nikto -h http://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.webapp.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                _, actions = await webapp_agent.execute_webapp_scan("http://target.com", {})

        for action in actions:
            assert action.decision_context, "AgentAction must have non-empty decision_context"
            assert len(action.decision_context) > 0

    @pytest.mark.asyncio
    async def test_decision_context_includes_spawn(self, webapp_agent, mock_scope_validator):
        """Decision context includes initial_spawn:{agent_id}."""
        webapp_agent.max_iterations = 1

        with patch.object(webapp_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "nikto"
            tool_selection.command = "nikto -h http://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.webapp.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                _, actions = await webapp_agent.execute_webapp_scan("http://target.com", {})

        for action in actions:
            context_str = " ".join(action.decision_context)
            assert "initial_spawn:" in context_str

    @pytest.mark.asyncio
    async def test_decision_context_includes_waf_when_detected(self, webapp_agent, mock_scope_validator):
        """Decision context includes waf:{waf_type} when WAF detected."""
        webapp_agent.max_iterations = 1
        webapp_agent._waf_detected = True
        webapp_agent._waf_type = "cloudflare"

        with patch.object(webapp_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "nikto"
            tool_selection.command = "nikto -h http://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.webapp.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                _, actions = await webapp_agent.execute_webapp_scan("http://target.com", {})

        for action in actions:
            context_str = " ".join(action.decision_context)
            assert "waf:cloudflare" in context_str

    @pytest.mark.asyncio
    async def test_decision_context_includes_auth_when_credentials(self, webapp_agent, mock_scope_validator):
        """Decision context includes auth:credentials_provided when creds supplied."""
        webapp_agent.max_iterations = 1

        with patch.object(webapp_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            tool_selection = MagicMock()
            tool_selection.tool_name = "nikto"
            tool_selection.command = "nikto -h http://target"
            tool_selection.confidence = 0.9
            mock_select.return_value = tool_selection

            with patch("cyberred.agents.webapp.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                target_info = {"credentials": {"username": "admin", "password": "pass"}}
                _, actions = await webapp_agent.execute_webapp_scan("http://target.com", target_info)

        for action in actions:
            context_str = " ".join(action.decision_context)
            assert "auth:credentials_provided" in context_str


# --- Task 1.5: WAF Detection Tests (AC: #5) ---
@pytest.mark.unit
class TestWebAppAgentWAFDetection:
    """Tests for WAF detection and evasion."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def mock_scope_validator(self):
        with patch("cyberred.agents.webapp.ScopeValidator") as mock:
            instance = mock.return_value
            instance.validate.return_value = True
            yield instance

    @pytest.fixture
    def webapp_agent(self, mock_event_bus, mock_scope_validator):
        from cyberred.agents.webapp import WebAppAgent

        return WebAppAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_detect_waf_sets_flag_on_detection(self, webapp_agent):
        """_detect_waf sets _waf_detected and _waf_type on detection."""
        with patch("cyberred.agents.webapp.kali_execute", new_callable=AsyncMock) as mock_exec:
            result = MagicMock()
            result.success = True
            result.stdout = '[target.com] detected Cloudflare (Cloudflare Inc.)'
            result.stderr = ""
            result.exit_code = 0
            mock_exec.return_value = result

            await webapp_agent._detect_waf("http://target.com")

            assert webapp_agent._waf_detected is True
            assert webapp_agent._waf_type is not None

    @pytest.mark.asyncio
    async def test_detect_waf_handles_no_waf(self, webapp_agent):
        """_detect_waf handles no WAF case."""
        with patch("cyberred.agents.webapp.kali_execute", new_callable=AsyncMock) as mock_exec:
            result = MagicMock()
            result.success = True
            result.stdout = 'No WAF detected by the generic detection'
            result.stderr = ""
            result.exit_code = 0
            mock_exec.return_value = result

            await webapp_agent._detect_waf("http://target.com")

            assert webapp_agent._waf_detected is False

    @pytest.mark.asyncio
    async def test_detect_waf_handles_failure(self, webapp_agent):
        """_detect_waf handles execution failure gracefully."""
        with patch("cyberred.agents.webapp.kali_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = Exception("Connection failed")

            await webapp_agent._detect_waf("http://target.com")

            # Should not crash, defaults to no WAF detected
            assert webapp_agent._waf_detected is False

    def test_get_constraints_includes_waf_evasion(self, webapp_agent):
        """_get_constraints includes WAF evasion when WAF detected."""
        webapp_agent._waf_detected = True
        webapp_agent._waf_type = "cloudflare"

        constraints = webapp_agent._get_constraints()

        assert any("waf" in c.lower() or "evasion" in c.lower() for c in constraints)


# --- Task 1.6: Strategy Tests (AC: #7) ---
@pytest.mark.unit
class TestWebAppAgentStrategy:
    """Tests for strategy handling."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def mock_scope_validator(self):
        with patch("cyberred.agents.webapp.ScopeValidator") as mock:
            instance = mock.return_value
            instance.validate.return_value = True
            yield instance

    @pytest.fixture
    def webapp_agent(self, mock_event_bus, mock_scope_validator):
        from cyberred.agents.webapp import WebAppAgent

        return WebAppAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("strategy", ["stealth", "standard", "aggressive"])
    async def test_on_signal_updates_strategy(self, webapp_agent, strategy):
        """on_signal updates strategy for valid values."""
        channel = "strategies:eng-1"
        data = {"strategy": strategy}

        await webapp_agent.on_signal(channel, data)

        assert webapp_agent.current_strategy == strategy

    @pytest.mark.asyncio
    async def test_on_signal_ignores_invalid_strategy(self, webapp_agent):
        """on_signal ignores invalid strategy values."""
        channel = "strategies:eng-1"
        data = {"strategy": "invalid_strategy"}

        await webapp_agent.on_signal(channel, data)

        assert webapp_agent.current_strategy == "standard"

    @pytest.mark.asyncio
    async def test_on_signal_ignores_non_strategy_channel(self, webapp_agent):
        """on_signal ignores channels that don't contain 'strategies'."""
        # Set a known strategy first
        webapp_agent.current_strategy = "stealth"
        
        # Send signal on a non-strategies channel (covers 204->exit branch)
        channel = "findings:eng-1"
        data = {"strategy": "aggressive"}  # Even with valid strategy data

        await webapp_agent.on_signal(channel, data)

        # Strategy should NOT change since channel doesn't contain "strategies"
        assert webapp_agent.current_strategy == "stealth"

    def test_get_constraints_stealth(self, webapp_agent):
        """_get_constraints returns stealth constraints."""
        webapp_agent.current_strategy = "stealth"

        constraints = webapp_agent._get_constraints()

        assert any("rate" in c.lower() or "detection" in c.lower() or "passive" in c.lower() for c in constraints)

    def test_get_constraints_aggressive(self, webapp_agent):
        """_get_constraints returns aggressive constraints."""
        webapp_agent.current_strategy = "aggressive"

        constraints = webapp_agent._get_constraints()

        assert any("throughput" in c.lower() or "comprehensive" in c.lower() for c in constraints)


# --- Task 1.7: Stigmergic Hook Tests (AC: #7) ---
@pytest.mark.unit
class TestWebAppAgentStigmergicHooks:
    """Tests for preserved stigmergic hooks."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def mock_scope_validator(self):
        with patch("cyberred.agents.webapp.ScopeValidator") as mock:
            instance = mock.return_value
            instance.validate.return_value = True
            yield instance

    @pytest.fixture
    def webapp_agent(self, mock_event_bus, mock_scope_validator):
        from cyberred.agents.webapp import WebAppAgent

        return WebAppAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_on_finding_publishes_to_webapp_channel(self, webapp_agent, mock_event_bus):
        """on_finding publishes to findings:{target_hash}:webapp channel."""
        from cyberred.core.models import Finding
        
        # Use a real Finding object instead of MagicMock
        finding = Finding(
            id=str(uuid.uuid4()),
            type="webapp",
            severity="medium",
            target="http://target.com",
            evidence="Test finding evidence",
            agent_id=webapp_agent.agent_id,
            timestamp="2025-01-21T00:00:00Z",
            tool="nikto",
            topic="findings:test:webapp",
            signature="test-sig-001",
        )

        await webapp_agent.on_finding(finding)

        mock_event_bus.publish.assert_called()
        call_args = mock_event_bus.publish.call_args
        channel = call_args[0][0]
        assert "webapp" in channel

    @pytest.mark.asyncio
    async def test_stop_sets_event(self, webapp_agent):
        """stop() sets _stop_event."""
        await webapp_agent.stop()

        assert webapp_agent._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_flush_buffer_on_reconnect(self, webapp_agent, mock_event_bus):
        """_flush_buffer attempts to publish buffered findings."""
        webapp_agent._finding_buffer = [
            {"channel": "findings:abc:webapp", "message": {"id": "f1"}},
            {"channel": "findings:def:webapp", "message": {"id": "f2"}},
        ]

        await webapp_agent._flush_buffer()

        # Should have attempted to publish both buffered items
        assert mock_event_bus.publish.call_count >= 2


# --- Additional Coverage Tests ---
@pytest.mark.unit
class TestWebAppAgentEdgeCases:
    """Additional tests for edge cases and 100% coverage."""

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def mock_scope_validator(self):
        with patch("cyberred.agents.webapp.ScopeValidator") as mock:
            instance = mock.return_value
            instance.validate.return_value = True
            yield instance

    @pytest.fixture
    def webapp_agent(self, mock_event_bus, mock_scope_validator):
        from cyberred.agents.webapp import WebAppAgent

        return WebAppAgent(
            agent_id=str(uuid.uuid4()),
            engagement_id="eng-1",
            event_bus=mock_event_bus,
        )

    @pytest.mark.asyncio
    async def test_execute_exits_on_phase_complete(self, webapp_agent, mock_scope_validator):
        """execute_webapp_scan exits early when phase is complete."""
        webapp_agent.max_iterations = 5
        webapp_agent.phase_complete_threshold = 0  # Immediately complete

        with patch.object(webapp_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            findings, actions = await webapp_agent.execute_webapp_scan("http://target.com", {})

        # Should exit immediately without calling select_tool
        mock_select.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_creates_finding_on_success(self, webapp_agent, mock_scope_validator, mock_event_bus):
        """execute_webapp_scan creates findings when tool succeeds with output."""
        webapp_agent.max_iterations = 1

        with patch("cyberred.agents.webapp.kali_execute", new_callable=AsyncMock) as mock_exec:
            # First call is for WAF detection, second is for tool execution
            waf_result = MagicMock()
            waf_result.success = True
            waf_result.stdout = "No WAF detected"
            waf_result.stderr = ""

            tool_result = MagicMock()
            tool_result.success = True
            tool_result.stdout = "Found vulnerability: CVE-2024-1234"
            tool_result.stderr = ""
            tool_result.exit_code = 0

            mock_exec.side_effect = [waf_result, tool_result]

            with patch.object(webapp_agent, "select_tool", new_callable=AsyncMock) as mock_select:
                tool_selection = MagicMock()
                tool_selection.tool_name = "nikto"
                tool_selection.command = "nikto -h http://target"
                tool_selection.confidence = 0.9
                mock_select.return_value = tool_selection

                findings, actions = await webapp_agent.execute_webapp_scan("http://target.com", {})

        # Should have created a finding
        assert len(findings) == 1
        assert findings[0].type == "webapp"

    @pytest.mark.asyncio
    async def test_execute_handles_select_tool_exception(self, webapp_agent, mock_scope_validator):
        """execute_webapp_scan handles exceptions during tool selection."""
        webapp_agent.max_iterations = 1

        with patch.object(webapp_agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.side_effect = Exception("LLM unavailable")

            # Should not crash
            findings, actions = await webapp_agent.execute_webapp_scan("http://target.com", {})

        # Should have recorded an action even with error
        assert len(actions) == 1
        assert actions[0].action_type == "webapp:unknown"

    @pytest.mark.asyncio
    async def test_scope_validator_fallback_on_bad_file(self, webapp_agent):
        """_get_scope_validator returns default when file loading fails."""
        with patch("cyberred.agents.webapp.get_settings") as mock_settings:
            mock_settings.return_value.engagement.scope_path = "/nonexistent/path"
            with patch("cyberred.agents.webapp.ScopeValidator") as MockValidator:
                MockValidator.from_file.side_effect = FileNotFoundError("Not found")

                validator = webapp_agent._get_scope_validator()

                # Should return default validator, not crash
                assert validator is not None

    @pytest.mark.asyncio
    async def test_on_finding_flushes_existing_buffer_first(self, webapp_agent, mock_event_bus):
        """on_finding flushes existing buffer before publishing new finding."""
        from cyberred.core.models import Finding
        
        # Pre-populate buffer
        webapp_agent._finding_buffer = [
            {"channel": "findings:old:webapp", "message": {"id": "old"}}
        ]

        # Use a real Finding object
        finding = Finding(
            id=str(uuid.uuid4()),
            type="webapp",
            severity="medium",
            target="http://target.com",
            evidence="New finding evidence",
            agent_id=webapp_agent.agent_id,
            timestamp="2025-01-21T00:00:00Z",
            tool="nikto",
            topic="findings:test:webapp",
            signature="test-sig-new",
        )

        await webapp_agent.on_finding(finding)

        # Should have published both old buffered and new finding
        assert mock_event_bus.publish.call_count >= 2

    @pytest.mark.asyncio
    async def test_on_finding_buffers_on_publish_failure(self, webapp_agent, mock_event_bus):
        """on_finding buffers finding when publish fails."""
        from cyberred.core.models import Finding
        
        mock_event_bus.publish.side_effect = Exception("Network error")

        # Use a real Finding object
        finding = Finding(
            id=str(uuid.uuid4()),
            type="webapp",
            severity="high",
            target="http://target.com",
            evidence="Critical finding evidence",
            agent_id=webapp_agent.agent_id,
            timestamp="2025-01-21T00:00:00Z",
            tool="sqlmap",
            topic="findings:test:webapp",
            signature="test-sig-fail",
        )

        await webapp_agent.on_finding(finding)

        # Should have buffered the finding
        assert len(webapp_agent._finding_buffer) == 1

    @pytest.mark.asyncio
    async def test_flush_buffer_keeps_failed_items(self, webapp_agent, mock_event_bus):
        """_flush_buffer keeps items that fail to publish."""
        mock_event_bus.publish.side_effect = Exception("Network error")

        webapp_agent._finding_buffer = [
            {"channel": "findings:abc:webapp", "message": {"id": "f1"}},
        ]

        await webapp_agent._flush_buffer()

        # Should retain the failed item
        assert len(webapp_agent._finding_buffer) == 1

    @pytest.mark.asyncio
    async def test_stop_flushes_buffer_if_not_empty(self, webapp_agent, mock_event_bus):
        """stop() flushes buffer if it contains items."""
        webapp_agent._finding_buffer = [
            {"channel": "findings:abc:webapp", "message": {"id": "f1"}},
        ]

        await webapp_agent.stop()

        assert webapp_agent._stop_event.is_set()
        mock_event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_detect_waf_sets_unknown_type_for_unrecognized_waf(self, webapp_agent):
        """_detect_waf sets waf_type to 'unknown' for unrecognized WAFs."""
        with patch("cyberred.agents.webapp.kali_execute", new_callable=AsyncMock) as mock_exec:
            result = MagicMock()
            result.success = True
            result.stdout = "[target.com] detected SomeObscureWAF (Unknown Inc.)"
            result.stderr = ""
            result.exit_code = 0
            mock_exec.return_value = result

            await webapp_agent._detect_waf("http://target.com")

            assert webapp_agent._waf_detected is True
            assert webapp_agent._waf_type == "unknown"

    def test_get_constraints_standard_strategy(self, webapp_agent):
        """_get_constraints returns empty list for standard strategy without WAF."""
        webapp_agent.current_strategy = "standard"
        webapp_agent._waf_detected = False

        constraints = webapp_agent._get_constraints()

        assert constraints == []

    def test_hash_target(self, webapp_agent):
        """_hash_target returns consistent 8-char hash."""
        hash1 = webapp_agent._hash_target("http://target.com")
        hash2 = webapp_agent._hash_target("http://target.com")

        assert hash1 == hash2
        assert len(hash1) == 8

    @pytest.mark.asyncio
    async def test_execute_exits_when_stop_set_during_loop(self, webapp_agent, mock_scope_validator):
        """execute_webapp_scan exits when _stop_event is set during iteration."""
        webapp_agent.max_iterations = 10

        call_count = 0

        async def set_stop_after_first(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                webapp_agent._stop_event.set()
            tool_selection = MagicMock()
            tool_selection.tool_name = "nikto"
            tool_selection.command = "nikto -h http://target"
            tool_selection.confidence = 0.9
            return tool_selection

        with patch.object(webapp_agent, "select_tool", side_effect=set_stop_after_first):
            with patch("cyberred.agents.webapp.kali_execute", new_callable=AsyncMock) as mock_exec:
                result = MagicMock()
                result.success = True
                result.stdout = ""
                result.stderr = ""
                result.exit_code = 0
                mock_exec.return_value = result

                findings, actions = await webapp_agent.execute_webapp_scan("http://target.com", {})

        # Should have stopped after 2 iterations
        assert len(actions) <= 3
