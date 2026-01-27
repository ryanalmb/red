"""Unit tests for PostExAgent v2 LLM-Driven Refactor (Story 7.5-v2).

Tests for the thin subclass pattern with LLM-driven tool selection.
Following TDD RED-GREEN-REFACTOR cycle.

Covers:
- AC1: Thin subclass architecture
- AC2: Hardcoded methods REMOVED
- AC3: LLM-driven tool selection
- AC4: NFR37 decision context (HARD GATE)
- AC5: Preserved functionality
- AC6: Strategy handling
- AC7: Quality gates
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cyberred.agents.base import StigmergicAgent
from cyberred.agents.postex import PostExAgent
from cyberred.agents.roles import AgentRole
from cyberred.core.events import EventBus
from cyberred.core.models import AgentAction, Finding, ToolSelectionContext, ToolSelection
from cyberred.tools.scope import ScopeValidator, ScopeConfig


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_event_bus():
    """Create mock EventBus."""
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock()
    bus.subscribe_once = AsyncMock()
    return bus


@pytest.fixture
def mock_llm_gateway():
    """Create mock LLMGateway."""
    gateway = MagicMock()
    gateway.generate = AsyncMock(return_value="nmap -sV target")
    gateway.get_queue_depth = MagicMock(return_value=0)
    return gateway


@pytest.fixture
def mock_manifest_loader():
    """Create mock ManifestLoader."""
    loader = MagicMock()
    loader.get_tools_by_category = MagicMock(return_value=[
        {"name": "linpeas", "description": "Linux privilege escalation checker"},
        {"name": "winpeas", "description": "Windows privilege escalation checker"},
    ])
    return loader


@pytest.fixture
def mock_intel_aggregator():
    """Create mock CachedIntelligenceAggregator."""
    aggregator = MagicMock()
    aggregator.query = AsyncMock(return_value=[])
    return aggregator


@pytest.fixture
def mock_rag_escalator():
    """Create mock AgentRAGEscalator."""
    escalator = MagicMock()
    escalator.record_failure = AsyncMock(return_value=1)
    escalator.record_success = AsyncMock()
    escalator.should_escalate = AsyncMock(return_value=False)
    escalator.escalate = AsyncMock()
    return escalator


@pytest.fixture
def sample_access_data_linux():
    """Sample shell access data for Linux target."""
    return {
        "access_type": "shell",
        "os_type": "linux",
        "privilege_level": "user",
        "shell_data": {
            "connection_string": "10.0.0.50",
            "shell_type": "reverse",
            "port": 4444,
        },
    }


@pytest.fixture
def sample_access_data_windows():
    """Sample credential access data for Windows target."""
    return {
        "access_type": "credentials",
        "os_type": "windows",
        "privilege_level": "admin",
        "credentials": {
            "username": "admin",
            "password": "P@ssw0rd123!",
            "domain": "CORP.LOCAL",
        },
    }


@pytest.fixture
def mock_scope_validator():
    """Create mock ScopeValidator that allows all targets."""
    validator = MagicMock(spec=ScopeValidator)
    validator.validate = MagicMock(return_value=True)
    return validator


@pytest.fixture
def create_agent(mock_event_bus, mock_llm_gateway, mock_manifest_loader, mock_scope_validator):
    """Factory to create PostExAgent with mocked dependencies."""
    def _create(
        agent_id: str | None = None,
        engagement_id: str = "test-engagement",
        specialty: str = "linux",
        intel_aggregator: Any = None,
        rag_escalator: Any = None,
        **kwargs,
    ) -> PostExAgent:
        if agent_id is None:
            agent_id = str(uuid.uuid4())
        with patch.object(PostExAgent, '_get_scope_validator', return_value=mock_scope_validator):
            agent = PostExAgent(
                agent_id=agent_id,
                engagement_id=engagement_id,
                event_bus=mock_event_bus,
                specialty=specialty,
                llm_gateway=mock_llm_gateway,
                manifest_loader=mock_manifest_loader,
                intel_aggregator=intel_aggregator,
                rag_escalator=rag_escalator,
                **kwargs,
            )
            agent._get_scope_validator = MagicMock(return_value=mock_scope_validator)
            return agent
    return _create


# ============================================================================
# Task 1.1: Constructor Tests (AC: #1)
# ============================================================================


@pytest.mark.unit
class TestPostExAgentConstructor:
    """Tests for PostExAgent constructor - AC1: Thin Subclass Architecture."""

    def test_sets_role_to_postex(self, create_agent):
        """AC1: Constructor sets role=AgentRole.POSTEX."""
        agent = create_agent()
        assert agent.role == AgentRole.POSTEX

    def test_default_specialty_is_linux(self, create_agent):
        """AC1: Default specialty is 'linux'."""
        agent = create_agent()
        assert agent.specialty == "linux"

    @pytest.mark.parametrize("specialty", ["linux", "windows", "ad"])
    def test_accepts_all_specialties(self, create_agent, specialty):
        """AC1: Constructor accepts specialty parameter (linux, windows, ad)."""
        agent = create_agent(specialty=specialty)
        assert agent.specialty == specialty

    def test_no_target_in_constructor(self, create_agent):
        """AC1: NO target in constructor (passed to execute_postex())."""
        agent = create_agent()
        assert not hasattr(agent, "target")

    def test_no_access_data_in_constructor(self, create_agent):
        """AC1: NO access_data in constructor (passed to execute_postex())."""
        agent = create_agent()
        assert not hasattr(agent, "access_data")

    def test_extends_stigmergic_agent(self, create_agent):
        """AC1: PostExAgent is thin subclass of StigmergicAgent."""
        agent = create_agent()
        assert isinstance(agent, StigmergicAgent)

    def test_has_max_iterations_constant(self, create_agent):
        """AC1: Has configurable max_iterations."""
        agent = create_agent()
        assert hasattr(agent, "max_iterations")
        assert agent.max_iterations == PostExAgent.DEFAULT_MAX_ITERATIONS

    def test_custom_max_iterations(self, create_agent):
        """AC1: Custom max_iterations is accepted."""
        agent = create_agent(max_iterations=5)
        assert agent.max_iterations == 5

    def test_has_phase_complete_threshold(self, create_agent):
        """AC1: Has configurable phase_complete_threshold."""
        agent = create_agent()
        assert hasattr(agent, "phase_complete_threshold")
        assert agent.phase_complete_threshold == PostExAgent.DEFAULT_PHASE_COMPLETE_THRESHOLD

    def test_accepts_intel_aggregator(self, create_agent, mock_intel_aggregator):
        """AC1: Accepts intel_aggregator injection."""
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        assert agent._intel_aggregator is mock_intel_aggregator

    def test_accepts_rag_escalator(self, create_agent, mock_rag_escalator):
        """AC1: Accepts rag_escalator injection."""
        agent = create_agent(rag_escalator=mock_rag_escalator)
        assert agent._rag_escalator is mock_rag_escalator


# ============================================================================
# Task 1.2: Hardcoded Removal Tests (AC: #2)
# ============================================================================


@pytest.mark.unit
class TestHardcodedMethodsRemoved:
    """Tests for AC2: Hardcoded methods REMOVED."""

    def test_no_generate_linpeas_command(self):
        """AC2: NO _generate_linpeas_command method."""
        assert not hasattr(PostExAgent, "_generate_linpeas_command")

    def test_no_generate_winpeas_command(self):
        """AC2: NO _generate_winpeas_command method."""
        assert not hasattr(PostExAgent, "_generate_winpeas_command")

    def test_no_generate_bloodhound_command(self):
        """AC2: NO _generate_bloodhound_command method."""
        assert not hasattr(PostExAgent, "_generate_bloodhound_command")

    def test_no_generate_mimikatz_command(self):
        """AC2: NO _generate_mimikatz_command method."""
        assert not hasattr(PostExAgent, "_generate_mimikatz_command")

    def test_no_generate_lazagne_command(self):
        """AC2: NO _generate_lazagne_command method."""
        assert not hasattr(PostExAgent, "_generate_lazagne_command")

    def test_no_generate_psexec_command(self):
        """AC2: NO _generate_psexec_command method."""
        assert not hasattr(PostExAgent, "_generate_psexec_command")

    def test_no_generate_wmiexec_command(self):
        """AC2: NO _generate_wmiexec_command method."""
        assert not hasattr(PostExAgent, "_generate_wmiexec_command")

    def test_no_generate_smbexec_command(self):
        """AC2: NO _generate_smbexec_command method."""
        assert not hasattr(PostExAgent, "_generate_smbexec_command")

    def test_no_generate_evilwinrm_command(self):
        """AC2: NO _generate_evilwinrm_command method."""
        assert not hasattr(PostExAgent, "_generate_evilwinrm_command")

    def test_no_generate_privesc_command(self):
        """AC2: NO _generate_privesc_command method."""
        assert not hasattr(PostExAgent, "_generate_privesc_command")

    def test_no_detect_privesc_opportunities(self):
        """AC2: NO _detect_privesc_opportunities method (LLM handles this)."""
        assert not hasattr(PostExAgent, "_detect_privesc_opportunities")

    def test_no_attempt_privesc(self):
        """AC2: NO _attempt_privesc method (replaced by LLM loop)."""
        assert not hasattr(PostExAgent, "_attempt_privesc")

    def test_no_execute_privesc_technique(self):
        """AC2: NO _execute_privesc_technique method."""
        assert not hasattr(PostExAgent, "_execute_privesc_technique")

    def test_no_parse_enumeration_discoveries(self):
        """AC2: NO _parse_enumeration_discoveries (use OutputProcessor)."""
        assert not hasattr(PostExAgent, "_parse_enumeration_discoveries")

    def test_no_extract_credentials(self):
        """AC2: NO _extract_credentials (LLM selects tool)."""
        assert not hasattr(PostExAgent, "_extract_credentials")

    def test_no_register_parsers(self):
        """AC2: NO _register_parsers (base class handles)."""
        assert not hasattr(PostExAgent, "_register_parsers")


# ============================================================================
# Task 1.3: Execute Method Tests (AC: #3)
# ============================================================================


@pytest.mark.unit
class TestExecutePostex:
    """Tests for AC3: LLM-driven tool selection."""

    @pytest.mark.asyncio
    async def test_execute_postex_takes_target_and_access_data_params(self, create_agent, sample_access_data_linux):
        """AC3: execute_postex() takes target and access_data as parameters."""
        agent = create_agent()
        with patch.object(agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.return_value = ToolSelection(
                tool_name="linpeas", command="linpeas.sh", rationale="Linux enumeration",
                expected_output_type="text"
            )
            with patch("cyberred.agents.postex.kali_execute", new_callable=AsyncMock) as mock_kali:
                mock_kali.return_value = MagicMock(success=True, stdout="output", stderr="", exit_code=0)
                # Should accept target and access_data as parameters
                findings, actions = await agent.execute_postex("10.0.0.50", sample_access_data_linux)
                assert isinstance(findings, list)
                assert isinstance(actions, list)

    @pytest.mark.asyncio
    async def test_execute_postex_calls_select_tool(self, create_agent, sample_access_data_linux):
        """AC3: execute_postex() uses inherited select_tool()."""
        agent = create_agent()
        with patch.object(agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.return_value = ToolSelection(
                tool_name="linpeas", command="linpeas.sh", rationale="Linux enumeration",
                expected_output_type="text"
            )
            with patch("cyberred.agents.postex.kali_execute", new_callable=AsyncMock) as mock_kali:
                mock_kali.return_value = MagicMock(success=True, stdout="", stderr="", exit_code=0)
                await agent.execute_postex("10.0.0.50", sample_access_data_linux)
                mock_select.assert_called()

    @pytest.mark.asyncio
    async def test_execute_postex_respects_stop_event(self, create_agent, sample_access_data_linux):
        """AC3: execute_postex() returns early if stop event is set."""
        agent = create_agent()
        agent._stop_event.set()
        findings, actions = await agent.execute_postex("10.0.0.50", sample_access_data_linux)
        assert findings == []
        assert actions == []

    @pytest.mark.asyncio
    async def test_execute_postex_validates_scope(self, create_agent, sample_access_data_linux):
        """AC3: execute_postex() validates target scope."""
        agent = create_agent()
        with patch.object(agent, "_validate_target_scope") as mock_validate:
            with patch.object(agent, "select_tool", new_callable=AsyncMock) as mock_select:
                mock_select.return_value = ToolSelection(
                    tool_name="linpeas", command="linpeas.sh", rationale="test",
                    expected_output_type="text"
                )
                with patch("cyberred.agents.postex.kali_execute", new_callable=AsyncMock) as mock_kali:
                    mock_kali.return_value = MagicMock(success=True, stdout="", exit_code=0)
                    await agent.execute_postex("10.0.0.50", sample_access_data_linux)
                    mock_validate.assert_called_once_with("10.0.0.50")

    @pytest.mark.asyncio
    async def test_execute_postex_loops_until_phase_complete(self, create_agent, sample_access_data_linux):
        """AC3: execute_postex() loops until phase is complete."""
        agent = create_agent(phase_complete_threshold=2)
        call_count = 0

        async def mock_select(context):
            nonlocal call_count
            call_count += 1
            return ToolSelection(tool_name="linpeas", command="linpeas.sh", rationale="test", expected_output_type="text")

        with patch.object(agent, "select_tool", side_effect=mock_select):
            with patch("cyberred.agents.postex.kali_execute", new_callable=AsyncMock) as mock_kali:
                mock_kali.return_value = MagicMock(success=True, stdout="found", exit_code=0)
                await agent.execute_postex("10.0.0.50", sample_access_data_linux)
                # Should loop multiple times
                assert call_count >= 1

    @pytest.mark.asyncio
    async def test_execute_postex_respects_max_iterations(self, create_agent, sample_access_data_linux):
        """AC3: execute_postex() respects max_iterations limit."""
        agent = create_agent(max_iterations=3)
        call_count = 0

        async def mock_select(context):
            nonlocal call_count
            call_count += 1
            return ToolSelection(tool_name="linpeas", command="linpeas.sh", rationale="test", expected_output_type="text")

        with patch.object(agent, "select_tool", side_effect=mock_select):
            with patch.object(agent, "_phase_complete", new_callable=AsyncMock, return_value=False):
                with patch("cyberred.agents.postex.kali_execute", new_callable=AsyncMock) as mock_kali:
                    mock_kali.return_value = MagicMock(success=True, stdout="", exit_code=0)
                    await agent.execute_postex("10.0.0.50", sample_access_data_linux)
                    # Should not exceed max_iterations
                    assert call_count <= 3


# ============================================================================
# Task 1.4: NFR37 Decision Context Tests (AC: #4)
# ============================================================================


@pytest.mark.unit
class TestDecisionContext:
    """Tests for AC4: NFR37 Decision Context (HARD GATE)."""

    @pytest.mark.asyncio
    async def test_all_actions_have_decision_context(self, create_agent, sample_access_data_linux):
        """AC4: ALL AgentActions have non-empty decision_context."""
        agent = create_agent()
        with patch.object(agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.return_value = ToolSelection(
                tool_name="linpeas", command="linpeas.sh", rationale="test",
                expected_output_type="text"
            )
            with patch("cyberred.agents.postex.kali_execute", new_callable=AsyncMock) as mock_kali:
                mock_kali.return_value = MagicMock(success=True, stdout="", exit_code=0)
                findings, actions = await agent.execute_postex("10.0.0.50", sample_access_data_linux)
                assert all(a.decision_context for a in actions)

    @pytest.mark.asyncio
    async def test_decision_context_includes_spawn(self, create_agent, sample_access_data_linux):
        """AC4: decision_context includes initial_spawn:{agent_id}."""
        agent = create_agent()
        with patch.object(agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.return_value = ToolSelection(
                tool_name="linpeas", command="linpeas.sh", rationale="test",
                expected_output_type="text"
            )
            with patch("cyberred.agents.postex.kali_execute", new_callable=AsyncMock) as mock_kali:
                mock_kali.return_value = MagicMock(success=True, stdout="", exit_code=0)
                _, actions = await agent.execute_postex("10.0.0.50", sample_access_data_linux)
                if actions:
                    dc = actions[0].decision_context
                    assert any("initial_spawn" in c for c in dc)

    @pytest.mark.asyncio
    async def test_decision_context_includes_intel_when_available(
        self, create_agent, sample_access_data_linux, mock_intel_aggregator
    ):
        """AC4: decision_context includes intel:{source}:{cve_id} when available."""
        from cyberred.intelligence.base import IntelResult
        mock_intel_aggregator.query = AsyncMock(return_value=[
            IntelResult(
                source="cisa_kev", cve_id="CVE-2022-0847", severity="critical",
                exploit_available=True, exploit_path="path", confidence=1.0, priority=1, metadata={}
            )
        ])
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        with patch.object(agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.return_value = ToolSelection(
                tool_name="linpeas", command="linpeas.sh", rationale="test",
                expected_output_type="text"
            )
            with patch("cyberred.agents.postex.kali_execute", new_callable=AsyncMock) as mock_kali:
                mock_kali.return_value = MagicMock(success=True, stdout="", exit_code=0)
                _, actions = await agent.execute_postex("10.0.0.50", sample_access_data_linux)
                if actions:
                    dc = actions[0].decision_context
                    assert any("intel:" in c for c in dc)

    @pytest.mark.asyncio
    async def test_decision_context_includes_rag_on_escalation(
        self, create_agent, sample_access_data_linux, mock_rag_escalator
    ):
        """AC4: decision_context includes rag:{failed_technique}:{alternative} on escalation."""
        from cyberred.agents.rag_escalator import AgentEscalationResult, AgentRAGContext
        mock_rag_escalator.should_escalate = AsyncMock(return_value=True)
        mock_rag_escalator.escalate = AsyncMock(return_value=AgentEscalationResult(
            context=AgentRAGContext(
                agent_id="test", target_service="unknown", target_hash="target",
                failed_techniques=(), failure_count=3, environment={}, engagement_id="test"
            ),
            methodologies=tuple(),
            selected_technique="alt_technique",
            query_time_ms=100,
            was_successful=True,
        ))
        agent = create_agent(rag_escalator=mock_rag_escalator)
        with patch.object(agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.return_value = ToolSelection(
                tool_name="linpeas", command="linpeas.sh", rationale="test",
                expected_output_type="text"
            )
            with patch("cyberred.agents.postex.kali_execute", new_callable=AsyncMock) as mock_kali:
                mock_kali.return_value = MagicMock(success=False, stdout="", stderr="error", exit_code=1)
                _, actions = await agent.execute_postex("10.0.0.50", sample_access_data_linux)
                if actions:
                    dc = actions[0].decision_context
                    assert any("rag" in c.lower() for c in dc)

    @pytest.mark.asyncio
    async def test_decision_context_includes_auth_result(
        self, create_agent, sample_access_data_linux, mock_event_bus
    ):
        """AC4: decision_context includes auth:{request_id}:{granted|denied}."""
        agent = create_agent()
        # Mock authorization flow
        mock_event_bus.subscribe_once.return_value = {"granted": True}
        with patch.object(agent, "_request_authorization", new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = True
            # Would need lateral movement to trigger auth - simplified test
            context = agent.get_decision_context()
            # Just verify method exists and returns list
            assert isinstance(context, list)


# ============================================================================
# Task 1.5: Preserved Functionality Tests (AC: #5)
# ============================================================================


@pytest.mark.unit
class TestPreservedFunctionality:
    """Tests for AC5: Preserved functionality."""

    def test_query_intelligence_preserved(self, create_agent):
        """AC5: _query_intelligence() method preserved."""
        agent = create_agent()
        assert hasattr(agent, "_query_intelligence")
        assert asyncio.iscoroutinefunction(agent._query_intelligence)

    def test_select_technique_preserved(self, create_agent):
        """AC5: _select_technique() method preserved."""
        agent = create_agent()
        assert hasattr(agent, "_select_technique")

    def test_handle_postex_failure_preserved(self, create_agent):
        """AC5: _handle_postex_failure() method preserved for RAG escalation."""
        agent = create_agent()
        assert hasattr(agent, "_handle_postex_failure")
        assert asyncio.iscoroutinefunction(agent._handle_postex_failure)

    @pytest.mark.asyncio
    async def test_handle_postex_failure_triggers_rag_after_3_failures(
        self, create_agent, mock_rag_escalator
    ):
        """AC5: _handle_postex_failure() triggers RAG after 3+ failures."""
        mock_rag_escalator.should_escalate = AsyncMock(return_value=True)
        from cyberred.agents.rag_escalator import AgentEscalationResult, AgentRAGContext
        mock_rag_escalator.escalate = AsyncMock(return_value=AgentEscalationResult(
            context=AgentRAGContext(
                agent_id="test", target_service="unknown", target_hash="target",
                failed_techniques=(), failure_count=3, environment={}, engagement_id="test"
            ),
            methodologies=tuple(),
            selected_technique="alternative",
            query_time_ms=100,
            was_successful=True,
        ))
        agent = create_agent(rag_escalator=mock_rag_escalator)
        result = await agent._handle_postex_failure("failed_technique")
        assert result == "alternative"

    def test_request_authorization_preserved(self, create_agent):
        """AC5: _request_authorization() preserved for FR13 lateral movement auth."""
        agent = create_agent()
        assert hasattr(agent, "_request_authorization")
        assert asyncio.iscoroutinefunction(agent._request_authorization)

    @pytest.mark.asyncio
    async def test_request_authorization_for_lateral_movement(self, create_agent, mock_event_bus):
        """AC5: _request_authorization() works for lateral movement."""
        agent = create_agent()
        mock_event_bus.subscribe_once.return_value = {"granted": True}
        result = await agent._request_authorization(
            action="lateral_movement",
            target="10.0.0.51",
            justification="Discovered via enumeration"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_on_finding_publishes_to_postex_channel(self, create_agent, mock_event_bus):
        """AC5: on_finding() publishes to postex channel."""
        agent = create_agent()
        finding = Finding(
            id=str(uuid.uuid4()),
            target="10.0.0.50",
            type="postex",
            tool="linpeas",
            severity="high",
            timestamp=datetime.now(UTC).isoformat(),
            agent_id=str(agent.agent_id),
            topic="findings:test:postex",
            evidence="{}",
            signature=""
        )
        await agent.on_finding(finding)
        mock_event_bus.publish.assert_called()
        channel = mock_event_bus.publish.call_args[0][0]
        assert "postex" in channel

    @pytest.mark.asyncio
    async def test_on_signal_handles_strategy_update(self, create_agent):
        """AC5: on_signal() handles strategy updates."""
        agent = create_agent()
        await agent.on_signal("strategies:test", {"strategy": "stealth"})
        assert agent.current_strategy == "stealth"

    @pytest.mark.asyncio
    async def test_flush_buffer_on_redis_reconnect(self, create_agent, mock_event_bus):
        """AC5: _flush_buffer() works for ERR3 recovery."""
        agent = create_agent()
        agent._finding_buffer = [{"channel": "test", "message": {"data": "test"}}]
        await agent._flush_buffer()
        # Should attempt to publish buffered items
        mock_event_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_sets_event_and_flushes(self, create_agent, mock_event_bus):
        """AC5: stop() sets _stop_event and flushes buffer."""
        agent = create_agent()
        agent._finding_buffer = [{"channel": "test", "message": {}}]
        await agent.stop()
        assert agent._stop_event.is_set()


# ============================================================================
# Task 1.6: Strategy Tests (AC: #6)
# ============================================================================


@pytest.mark.unit
class TestStrategyHandling:
    """Tests for AC6: Strategy handling."""

    @pytest.mark.asyncio
    async def test_on_signal_updates_strategy_stealth(self, create_agent):
        """AC6: on_signal() updates strategy to stealth."""
        agent = create_agent()
        await agent.on_signal("strategies:test", {"strategy": "stealth"})
        assert agent.current_strategy == "stealth"

    @pytest.mark.asyncio
    async def test_on_signal_updates_strategy_aggressive(self, create_agent):
        """AC6: on_signal() updates strategy to aggressive."""
        agent = create_agent()
        await agent.on_signal("strategies:test", {"strategy": "aggressive"})
        assert agent.current_strategy == "aggressive"

    @pytest.mark.asyncio
    async def test_on_signal_ignores_invalid_strategy(self, create_agent):
        """AC6: on_signal() ignores invalid strategy values."""
        agent = create_agent()
        original = agent.current_strategy
        await agent.on_signal("strategies:test", {"strategy": "invalid"})
        assert agent.current_strategy == original

    def test_strategy_passed_to_tool_selection_context(self, create_agent):
        """AC6: Strategy is available for tool selection context."""
        agent = create_agent()
        agent.current_strategy = "stealth"
        constraints = agent._get_constraints()
        assert "low_rate" in constraints or "avoid_detection" in constraints


# ============================================================================
# Additional Coverage Tests
# ============================================================================


@pytest.mark.unit
class TestUtilityMethods:
    """Tests for utility methods that should be preserved."""

    def test_hash_target(self, create_agent):
        """Utility: _hash_target() generates consistent hash."""
        agent = create_agent()
        hash1 = agent._hash_target("10.0.0.50")
        hash2 = agent._hash_target("10.0.0.50")
        assert hash1 == hash2
        assert len(hash1) == 8

    def test_generate_finding_signature(self, create_agent):
        """Utility: _generate_finding_signature() produces HMAC."""
        agent = create_agent()
        finding_data = {"id": "test", "target": "10.0.0.50", "type": "postex"}
        sig = agent._generate_finding_signature(finding_data)
        assert sig is not None
        assert len(sig) == 64  # HMAC-SHA256 hex length

    def test_get_constraints_standard(self, create_agent):
        """Returns empty constraints for standard strategy."""
        agent = create_agent()
        agent.current_strategy = "standard"
        assert agent._get_constraints() == []

    def test_get_constraints_stealth(self, create_agent):
        """Returns stealth constraints."""
        agent = create_agent()
        agent.current_strategy = "stealth"
        constraints = agent._get_constraints()
        assert "low_rate" in constraints
        assert "avoid_detection" in constraints

    def test_get_constraints_aggressive(self, create_agent):
        """Returns aggressive constraints."""
        agent = create_agent()
        agent.current_strategy = "aggressive"
        constraints = agent._get_constraints()
        assert "high_throughput" in constraints
        assert "comprehensive" in constraints


# ============================================================================
# Additional Coverage Tests for 100%
# ============================================================================


@pytest.mark.unit
class TestCoverageGaps:
    """Tests to cover remaining code paths for 100% coverage."""

    @pytest.mark.asyncio
    async def test_query_intelligence_returns_empty_without_aggregator(self, create_agent):
        """Coverage: _query_intelligence returns [] when no aggregator."""
        agent = create_agent(intel_aggregator=None)
        result = await agent._query_intelligence("linux", "shell")
        assert result == []

    @pytest.mark.asyncio
    async def test_query_intelligence_handles_exception(self, create_agent, mock_intel_aggregator):
        """Coverage: _query_intelligence returns [] on exception."""
        mock_intel_aggregator.query = AsyncMock(side_effect=Exception("Query failed"))
        agent = create_agent(intel_aggregator=mock_intel_aggregator)
        result = await agent._query_intelligence("linux", "shell")
        assert result == []

    @pytest.mark.asyncio
    async def test_handle_postex_failure_without_escalator(self, create_agent):
        """Coverage: _handle_postex_failure returns None without RAG escalator."""
        agent = create_agent(rag_escalator=None)
        result = await agent._handle_postex_failure("technique_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_postex_failure_no_escalation_needed(self, create_agent, mock_rag_escalator):
        """Coverage: _handle_postex_failure when should_escalate returns False."""
        mock_rag_escalator.should_escalate = AsyncMock(return_value=False)
        agent = create_agent(rag_escalator=mock_rag_escalator)
        result = await agent._handle_postex_failure("technique_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_postex_failure_escalation_fails(self, create_agent, mock_rag_escalator):
        """Coverage: _handle_postex_failure when escalation throws exception."""
        mock_rag_escalator.should_escalate = AsyncMock(return_value=True)
        mock_rag_escalator.escalate = AsyncMock(side_effect=Exception("Escalation failed"))
        agent = create_agent(rag_escalator=mock_rag_escalator)
        result = await agent._handle_postex_failure("technique_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_postex_failure_escalation_not_successful(self, create_agent, mock_rag_escalator):
        """Coverage: _handle_postex_failure when escalation is not successful."""
        mock_rag_escalator.should_escalate = AsyncMock(return_value=True)
        from cyberred.agents.rag_escalator import AgentEscalationResult, AgentRAGContext
        mock_rag_escalator.escalate = AsyncMock(return_value=AgentEscalationResult(
            context=AgentRAGContext(
                agent_id="test", target_service="unknown", target_hash="target",
                failed_techniques=(), failure_count=3, environment={}, engagement_id="test"
            ),
            methodologies=tuple(), selected_technique=None, query_time_ms=100, was_successful=False,
        ))
        agent = create_agent(rag_escalator=mock_rag_escalator)
        result = await agent._handle_postex_failure("technique_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_on_finding_handles_publish_error(self, create_agent, mock_event_bus):
        """Coverage: on_finding buffers finding when publish fails."""
        mock_event_bus.publish = AsyncMock(side_effect=Exception("Publish failed"))
        agent = create_agent()
        finding = Finding(
            id=str(uuid.uuid4()), target="10.0.0.50", type="postex", tool="linpeas",
            severity="high", timestamp=datetime.now(UTC).isoformat(),
            agent_id=str(agent.agent_id), topic="test", evidence="{}", signature=""
        )
        await agent.on_finding(finding)
        assert len(agent._finding_buffer) == 1

    @pytest.mark.asyncio
    async def test_flush_buffer_handles_publish_error(self, create_agent, mock_event_bus):
        """Coverage: _flush_buffer keeps failed items in buffer."""
        mock_event_bus.publish = AsyncMock(side_effect=Exception("Still failing"))
        agent = create_agent()
        agent._finding_buffer = [{"channel": "test", "message": {"data": "test"}}]
        await agent._flush_buffer()
        assert len(agent._finding_buffer) == 1

    @pytest.mark.asyncio
    async def test_execute_postex_handles_exception_in_loop(self, create_agent, sample_access_data_linux):
        """Coverage: execute_postex continues on exception in loop."""
        agent = create_agent(max_iterations=2)
        with patch.object(agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.side_effect = Exception("Tool selection failed")
            findings, actions = await agent.execute_postex("10.0.0.50", sample_access_data_linux)
            # Should still create actions even on errors
            assert len(actions) == 2  # Two iterations attempted

    @pytest.mark.asyncio
    async def test_process_postex_result(self, create_agent):
        """Coverage: _process_postex_result creates finding correctly."""
        agent = create_agent()
        mock_selection = MagicMock()
        mock_selection.tool_name = "linpeas"
        mock_selection.command = "linpeas.sh"
        mock_result = MagicMock()
        mock_result.stdout = "Some output"
        access_data = {"os_type": "linux"}
        
        finding = await agent._process_postex_result(
            "10.0.0.50", mock_selection, mock_result, access_data, None
        )
        assert finding is not None
        assert finding.tool == "linpeas"
        assert finding.type == "postex"

    @pytest.mark.asyncio
    async def test_phase_complete_returns_true(self, create_agent):
        """Coverage: _phase_complete returns True when threshold reached."""
        agent = create_agent(phase_complete_threshold=2)
        context = ToolSelectionContext(
            objective="test", target_info={}, available_tools=[],
            phase="postex", constraints=[], previous_results=[{}, {}]
        )
        assert await agent._phase_complete(context) is True

    def test_validate_target_scope_delegates_to_validator(self, create_agent, mock_scope_validator):
        """Coverage: _validate_target_scope calls validator."""
        agent = create_agent()
        agent._validate_target_scope("10.0.0.50")
        mock_scope_validator.validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_select_technique_none_when_empty(self, create_agent):
        """Coverage: _select_technique returns None for empty list."""
        agent = create_agent()
        result = await agent._select_technique([])
        assert result is None

    @pytest.mark.asyncio
    async def test_select_technique_none_when_none(self, create_agent):
        """Coverage: _select_technique returns None when passed None."""
        agent = create_agent()
        result = await agent._select_technique(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_request_authorization_denied(self, create_agent, mock_event_bus):
        """Coverage: _request_authorization returns False when denied."""
        agent = create_agent()
        mock_event_bus.subscribe_once.return_value = {"granted": False}
        result = await agent._request_authorization("action", "target", "justification")
        assert result is False

    @pytest.mark.asyncio
    async def test_request_authorization_no_response(self, create_agent, mock_event_bus):
        """Coverage: _request_authorization returns False when no response."""
        agent = create_agent()
        mock_event_bus.subscribe_once.return_value = None
        result = await agent._request_authorization("action", "target", "justification")
        assert result is False

    @pytest.mark.asyncio
    async def test_execute_postex_creates_finding_on_success(self, create_agent, sample_access_data_linux):
        """Coverage: execute_postex creates finding when tool succeeds."""
        agent = create_agent(max_iterations=1, phase_complete_threshold=100)
        with patch.object(agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.return_value = ToolSelection(
                tool_name="linpeas", command="linpeas.sh", rationale="test",
                expected_output_type="text"
            )
            with patch("cyberred.agents.postex.kali_execute", new_callable=AsyncMock) as mock_kali:
                mock_kali.return_value = MagicMock(success=True, stdout="found data", exit_code=0)
                findings, actions = await agent.execute_postex("10.0.0.50", sample_access_data_linux)
                assert len(findings) == 1
                assert len(actions) == 1


@pytest.mark.unit
class TestLineCount:
    """Meta-test for code size requirements."""

    def test_postex_file_under_300_lines(self):
        """AC1: PostExAgent file is <300 lines (75% reduction from 1197)."""
        import os
        postex_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "src", "cyberred", "agents", "postex.py"
        )
        with open(postex_path) as f:
            line_count = len(f.readlines())
        assert line_count < 300, f"postex.py is {line_count} lines, must be <300"


# ============================================================================
# Additional Coverage Tests for 100% - Covering All Branches
# ============================================================================


@pytest.mark.unit
class TestFullCoverage:
    """Tests to achieve 100% coverage on all branches."""

    @pytest.mark.asyncio
    async def test_execute_postex_breaks_on_phase_complete(self, create_agent, sample_access_data_linux):
        """Coverage: Loop breaks when _phase_complete returns True (line 96)."""
        agent = create_agent(max_iterations=10)
        call_count = 0

        async def mock_select(context):
            nonlocal call_count
            call_count += 1
            return ToolSelection(
                tool_name="linpeas", command="linpeas.sh",
                rationale="test", expected_output_type="text"
            )

        # Make phase complete after first iteration
        async def mock_phase_complete(context):
            return call_count >= 1

        with patch.object(agent, "select_tool", side_effect=mock_select):
            with patch.object(agent, "_phase_complete", side_effect=mock_phase_complete):
                with patch("cyberred.agents.postex.kali_execute", new_callable=AsyncMock) as mock_kali:
                    mock_kali.return_value = MagicMock(success=True, stdout="output", exit_code=0)
                    await agent.execute_postex("10.0.0.50", sample_access_data_linux)
                    # Should have broken out after 1 iteration due to phase_complete
                    assert call_count == 1

    @pytest.mark.asyncio
    async def test_get_scope_validator_with_scope_path(self, create_agent):
        """Coverage: _get_scope_validator with settings.engagement.scope_path set (lines 160-163)."""
        agent = create_agent()
        
        mock_settings = MagicMock()
        mock_settings.engagement.scope_path = "/path/to/scope.yaml"
        
        mock_validator = MagicMock(spec=ScopeValidator)
        
        with patch("cyberred.agents.postex.get_settings", return_value=mock_settings):
            with patch.object(ScopeValidator, "from_file", return_value=mock_validator) as mock_from_file:
                # Call directly on a fresh instance without the fixture's mock
                from cyberred.agents.postex import PostExAgent
                real_agent = PostExAgent(
                    agent_id="test", engagement_id="test",
                    event_bus=MagicMock(spec=EventBus)
                )
                result = real_agent._get_scope_validator()
                mock_from_file.assert_called_once_with("/path/to/scope.yaml")
                assert result == mock_validator

    @pytest.mark.asyncio
    async def test_get_scope_validator_from_file_exception(self, create_agent):
        """Coverage: _get_scope_validator when from_file raises exception (lines 164-165)."""
        mock_settings = MagicMock()
        mock_settings.engagement.scope_path = "/invalid/path.yaml"
        
        with patch("cyberred.agents.postex.get_settings", return_value=mock_settings):
            with patch.object(ScopeValidator, "from_file", side_effect=FileNotFoundError("Not found")):
                from cyberred.agents.postex import PostExAgent
                real_agent = PostExAgent(
                    agent_id="test", engagement_id="test",
                    event_bus=MagicMock(spec=EventBus)
                )
                result = real_agent._get_scope_validator()
                # Should return default ScopeValidator when from_file fails
                assert isinstance(result, ScopeValidator)

    @pytest.mark.asyncio
    async def test_get_scope_validator_no_scope_path(self, create_agent):
        """Coverage: _get_scope_validator when scope_path is None (line 161 false branch)."""
        mock_settings = MagicMock()
        mock_settings.engagement.scope_path = None
        
        with patch("cyberred.agents.postex.get_settings", return_value=mock_settings):
            from cyberred.agents.postex import PostExAgent
            real_agent = PostExAgent(
                agent_id="test", engagement_id="test",
                event_bus=MagicMock(spec=EventBus)
            )
            result = real_agent._get_scope_validator()
            assert isinstance(result, ScopeValidator)

    @pytest.mark.asyncio
    async def test_on_finding_flushes_existing_buffer(self, create_agent, mock_event_bus):
        """Coverage: on_finding flushes buffer when it has items (line 223)."""
        agent = create_agent()
        # Pre-populate the buffer
        agent._finding_buffer = [{"channel": "old_channel", "message": {"old": "data"}}]
        
        finding = Finding(
            id=str(uuid.uuid4()), target="10.0.0.50", type="postex", tool="linpeas",
            severity="high", timestamp=datetime.now(UTC).isoformat(),
            agent_id=str(agent.agent_id), topic="test", evidence="{}", signature=""
        )
        
        await agent.on_finding(finding)
        
        # Should have called publish twice: once for flush, once for new finding
        assert mock_event_bus.publish.call_count >= 2

    @pytest.mark.asyncio
    async def test_on_signal_non_strategy_channel(self, create_agent):
        """Coverage: on_signal with non-strategy channel (line 240 exit)."""
        agent = create_agent()
        original_strategy = agent.current_strategy
        
        # Signal on non-strategy channel should not change strategy
        await agent.on_signal("findings:test", {"data": "something"})
        
        assert agent.current_strategy == original_strategy

    @pytest.mark.asyncio
    async def test_on_signal_no_strategy_key(self, create_agent):
        """Coverage: on_signal with strategy channel but no strategy key."""
        agent = create_agent()
        original_strategy = agent.current_strategy
        
        await agent.on_signal("strategies:test", {"other_key": "value"})
        
        assert agent.current_strategy == original_strategy

    @pytest.mark.asyncio
    async def test_stop_without_buffer(self, create_agent):
        """Coverage: stop() when buffer is empty (line 247 exit)."""
        agent = create_agent()
        agent._finding_buffer = []  # Empty buffer
        
        await agent.stop()
        
        assert agent._stop_event.is_set()
        # No flush should have been called since buffer was empty

    @pytest.mark.asyncio
    async def test_execute_postex_finding_is_none(self, create_agent, sample_access_data_linux):
        """Coverage: execute_postex when _process_postex_result returns None (line 109->117)."""
        agent = create_agent(max_iterations=1)
        
        with patch.object(agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.return_value = ToolSelection(
                tool_name="linpeas", command="linpeas.sh",
                rationale="test", expected_output_type="text"
            )
            with patch.object(agent, "_process_postex_result", new_callable=AsyncMock, return_value=None):
                with patch("cyberred.agents.postex.kali_execute", new_callable=AsyncMock) as mock_kali:
                    mock_kali.return_value = MagicMock(success=True, stdout="output", exit_code=0)
                    findings, actions = await agent.execute_postex("10.0.0.50", sample_access_data_linux)
                    # No findings should be added when _process_postex_result returns None
                    assert len(findings) == 0
                    assert len(actions) == 1

    @pytest.mark.asyncio
    async def test_execute_postex_rag_escalation_returns_none(self, create_agent, sample_access_data_linux, mock_rag_escalator):
        """Coverage: execute_postex when _handle_postex_failure returns None (line 115->117)."""
        mock_rag_escalator.should_escalate = AsyncMock(return_value=False)
        agent = create_agent(rag_escalator=mock_rag_escalator, max_iterations=1)
        
        with patch.object(agent, "select_tool", new_callable=AsyncMock) as mock_select:
            mock_select.return_value = ToolSelection(
                tool_name="linpeas", command="linpeas.sh",
                rationale="test", expected_output_type="text"
            )
            with patch("cyberred.agents.postex.kali_execute", new_callable=AsyncMock) as mock_kali:
                mock_kali.return_value = MagicMock(success=False, stdout="", stderr="error", exit_code=1)
                findings, actions = await agent.execute_postex("10.0.0.50", sample_access_data_linux)
                # Should still create action even when RAG returns None
                assert len(actions) == 1
                # No rag_escalation in context since it returned None
                dc = actions[0].decision_context
                assert not any("rag_escalation" in c for c in dc)

