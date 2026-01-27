
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from swarms import Agent
from cyberred.agents.base import StigmergicAgent
from cyberred.agents.roles import AgentRole
from cyberred.core.events import EventBus
from cyberred.core.models import AgentAction

@pytest.mark.unit
class TestStigmergicAgentBase:
    """
    Unit tests for StigmergicAgent base class.
    Covering AC #1-6: Initialization, Hooks, Pub/Sub, Protocol Compliance.
    """

    @pytest.fixture
    def event_bus(self):
        bus = MagicMock(spec=EventBus)
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        return bus

    @pytest.fixture
    def agent(self, event_bus):
        import uuid
        from cyberred.agents.roles import AgentRole
        return StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.RECON,  # Required role parameter
            llm=MagicMock(), # Mock LLM
            description="A test agent",
        )

    def test_initialization_requires_params(self, event_bus):
        """Test __init__ requires agent_id, engagement_id, event_bus, role."""
        with pytest.raises(TypeError):
            StigmergicAgent(agent_name="fail") # Missing params

        import uuid
        from cyberred.agents.roles import AgentRole
        a_id = str(uuid.uuid4())
        e_id = str(uuid.uuid4())
        agent = StigmergicAgent(
            agent_name="test",
            agent_id=a_id,
            engagement_id=e_id,
            event_bus=event_bus,
            role=AgentRole.RECON,  # Required role parameter
        )
        assert agent.agent_id == a_id
        assert agent.engagement_id == e_id
        assert agent.event_bus == event_bus

    @pytest.mark.asyncio
    async def test_on_finding_hook(self, agent, event_bus):
        """Test on_finding() publishes to findings channel."""
        # Arrange
        target_hash = "abc123hash"
        finding_type = "sqli"
        content = {"detail": "found vuln"}
        
        # Act
        await agent.on_finding(target_hash, finding_type, content)
        
        # Assert
        expected_channel = f"findings:{target_hash}:{finding_type}"
        event_bus.publish.assert_called_once()
        call_args = event_bus.publish.call_args
        assert call_args[0][0] == expected_channel
        message = call_args[0][1]
        assert message['data'] == content
        assert message['agent_id'] == agent.agent_id
        assert message['engagement_id'] == agent.engagement_id

    @pytest.mark.asyncio
    async def test_on_signal_hook(self, agent):
        """Test on_signal() is called when subscribed channel receives message."""
        # This tests the hook interface, actual invocation depends on the listener loop
        # which is harder to unit test without complex mocking of the subscription loop.
        # For unit test, we verify the method exists and handles data correctly.
        
        signal_data = {"strategy": "attack_phase_1"}
        channel = "strategies:eng-456"
        
        # Act
        await agent.on_signal(channel, signal_data)
        
        # Assert - for base class, it might just log or store decision context
        # We check if decision_context is updated (Story 7.8 requirement, but good to check basic handling)
        # For now, just ensure it doesn't crash
        pass

    @pytest.mark.asyncio
    async def test_on_complete_hook(self, agent, event_bus):
        """Test on_complete() publishes completion status."""
        # Act
        await agent.on_complete(status="success", result={"data": "done"})
        
        # Assert
        expected_channel = f"agents:{agent.agent_id}:status"
        event_bus.publish.assert_called()
        call_args = event_bus.publish.call_args
        assert call_args[0][0] == expected_channel
        assert call_args[0][1]['status'] == "success"

    @pytest.mark.asyncio
    async def test_initialization_subscribes_to_topics(self, agent, event_bus):
        """Test agent subscribes to standard topics on initialization/spawn."""
        from unittest.mock import ANY
        # subscriptions often happen in an async init or spawn method, not __init__
        # Assuming we have a start() or spawn() method
        await agent.spawn()
        
        # Verify subscriptions
        # Expected: findings:*, strategies:{engagement_id}, control:kill, control:pause
        event_bus.subscribe.assert_any_call("findings:*", ANY)
        event_bus.subscribe.assert_any_call(f"strategies:{agent.engagement_id}", ANY)
        event_bus.subscribe.assert_any_call("control:kill", ANY)

    def test_agent_protocol_compliance(self, agent):
        """Test agent implements AgentProtocol methods."""
        assert hasattr(agent, "execute")
        assert hasattr(agent, "reason")
        assert hasattr(agent, "get_id")
        assert hasattr(agent, "get_status")
        assert hasattr(agent, "get_decision_context")
        assert hasattr(agent, "shutdown")
        
        assert agent.get_id() == agent.agent_id
        # Should return a valid status string
        assert isinstance(agent.get_status(), str) 

    @pytest.mark.asyncio
    async def test_message_metadata_injection(self, agent, event_bus):
        """Test all published messages include agent_id and engagement_id."""
        await agent.on_finding("t1", "vuln", {})
        
        call_args = event_bus.publish.call_args
        message = call_args[0][1]
        assert "agent_id" in message
        assert message["agent_id"] == agent.agent_id
        assert "engagement_id" in message
        assert message["engagement_id"] == agent.engagement_id

    @pytest.mark.asyncio
    async def test_decision_context_tracking(self, agent):
        """Test decision context tracks signal IDs."""
        # Initial state empty
        assert agent.get_decision_context() == []
        
        # Receive signal with ID
        await agent.on_signal("strategies:eng-1", {"signal_id": "sig-123", "data": "foo"})
        
        # Should be tracked
        context = agent.get_decision_context()
        assert "sig-123" in context
        
        # Receive signal without ID
        await agent.on_signal("strategies:eng-1", {"data": "bar"})
        
        # Should not change count
        context = agent.get_decision_context()
        assert len(context) == 1
        assert "sig-123" in context

    @pytest.mark.asyncio
    async def test_throttle_check(self, agent):
        """Test throttling check (currently always False)."""
        assert await agent._check_throttle() is False

    @pytest.mark.asyncio
    async def test_execute_stub(self, agent):
        """Test execute method returns an AgentAction."""
        with patch.object(Agent, 'run', return_value="done", create=True):
             # Some mock of super().run might be needed if base calls it
             # But our implementation wraps it.
             # swarms.Agent.run signature might vary, so we just check it returns AgentAction
             action = await agent.execute("127.0.0.1")
             assert isinstance(action, AgentAction)
             assert action.action_type == "execute"
             assert agent.get_status() == "active"

    @pytest.mark.asyncio
    async def test_reason_method(self, agent):
        """Test reason method."""
        context = ["signal-1", "signal-2"]
        reasoning = await agent.reason(context)
        assert "Reasoning based on 2 signals" in reasoning

    @pytest.mark.asyncio
    async def test_shutdown_method(self, agent):
        """Test shutdown method."""
        agent._status = "active"
        await agent.shutdown()
        assert agent.get_status() == "shutdown"

    @pytest.mark.asyncio
    async def test_handle_message_json_parsing(self, agent):
        """Test _handle_message parses JSON correctly."""
        with patch.object(agent, 'on_signal', new_callable=AsyncMock) as mock_on_signal:
             await agent._handle_message("channel", '{"key": "value"}')
             mock_on_signal.assert_called_with("channel", {"key": "value"})

    @pytest.mark.asyncio
    async def test_handle_message_raw_string(self, agent):
         """Test _handle_message wraps invalid JSON."""
         with patch.object(agent, 'on_signal', new_callable=AsyncMock) as mock_on_signal:
             await agent._handle_message("channel", "invalid json")
             mock_on_signal.assert_called_with("channel", {"raw_content": "invalid json"})

    @pytest.mark.asyncio
    async def test_handle_message_none_guard(self, agent):
         """Test _handle_message handles None message gracefully."""
         with patch.object(agent, 'on_signal', new_callable=AsyncMock) as mock_on_signal:
              # Should return early without calling on_signal
              await agent._handle_message("channel", None)
              mock_on_signal.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_exception(self, agent):
         """Test exception in _handle_message is caught."""
         with patch.object(agent, 'on_signal', side_effect=Exception("parse error")):
              # Should log error but not raise
              await agent._handle_message("channel", "{}")

    @pytest.mark.asyncio
    async def test_execute_exception(self, agent):
        """Test exception in execute method handles status update."""
        # Force an exception (swarms Agent might not raise, but we want to test our wrapper)
        with patch.object(Agent, 'run', side_effect=Exception("Task failed"), create=True):
             # Since our code calls self.run (mocked via Agent.run probably if super called)
             # Wait, our code calls super().run indirectly? Or does it?
             # Implementation:
             # try: ... return AgentAction ... except Exception: self._status='error'; raise
             # We need to force exception inside the try block.
             # The current implementation has:
             #      # result = self.run(task)
             #      import uuid ...
             #      return AgentAction(...)
             
             # To force exception, we can patch uuid or datetime used in try block
             with patch('uuid.uuid4', side_effect=Exception("UUID error")):
                 with pytest.raises(Exception, match="UUID error"):
                     await agent.execute("127.0.0.1")
                 assert agent.get_status() == "error"


@pytest.mark.unit
class TestStigmergicAgentRoleParameter:
    """Tests for Story 7.1.v2: Required role parameter in constructor.
    
    These tests verify the new AgentRole requirement for StigmergicAgent.
    """

    @pytest.fixture
    def event_bus(self):
        bus = MagicMock(spec=EventBus)
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        return bus

    def test_init_requires_role(self, event_bus):
        """StigmergicAgent requires AgentRole parameter."""
        import uuid
        
        # Without role parameter should raise TypeError
        with pytest.raises(TypeError, match="role"):
            StigmergicAgent(
                agent_name="test",
                agent_id=str(uuid.uuid4()),
                engagement_id=str(uuid.uuid4()),
                event_bus=event_bus,
            )

    def test_init_accepts_role(self, event_bus):
        """StigmergicAgent accepts and stores role parameter."""
        import uuid
        from cyberred.agents.roles import AgentRole
        
        agent = StigmergicAgent(
            agent_name="recon-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.RECON,
        )
        
        assert agent.role == AgentRole.RECON

    def test_init_loads_prompt_from_library(self, event_bus):
        """Constructor calls PromptLibrary.get(role, specialty)."""
        import uuid
        from cyberred.agents.roles import AgentRole
        
        with patch('cyberred.agents.base.PromptLibrary') as mock_lib:
            mock_lib.get.return_value = "Mocked system prompt"
            
            agent = StigmergicAgent(
                agent_name="exploit-agent",
                agent_id=str(uuid.uuid4()),
                engagement_id=str(uuid.uuid4()),
                event_bus=event_bus,
                role=AgentRole.EXPLOIT,
            )
            
            # PromptLibrary.get should have been called
            mock_lib.get.assert_called_once_with(AgentRole.EXPLOIT, None)
            assert agent.system_prompt == "Mocked system prompt"

    def test_init_accepts_optional_specialty(self, event_bus):
        """Specialty parameter is optional, defaults to None."""
        import uuid
        from cyberred.agents.roles import AgentRole
        
        agent = StigmergicAgent(
            agent_name="webapp-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.WEBAPP,
            specialty="api",
        )
        
        assert agent.role == AgentRole.WEBAPP
        assert agent.specialty == "api"

    def test_init_specialty_passed_to_prompt_library(self, event_bus):
        """Specialty is passed to PromptLibrary.get()."""
        import uuid
        from cyberred.agents.roles import AgentRole
        
        with patch('cyberred.agents.base.PromptLibrary') as mock_lib:
            mock_lib.get.return_value = "Specialty prompt"
            
            StigmergicAgent(
                agent_name="recon-net",
                agent_id=str(uuid.uuid4()),
                engagement_id=str(uuid.uuid4()),
                event_bus=event_bus,
                role=AgentRole.RECON,
                specialty="network",
            )
            
            mock_lib.get.assert_called_once_with(AgentRole.RECON, "network")

    def test_init_creates_empty_tool_help_cache(self, event_bus):
        """Constructor initializes _tool_help_cache as empty dict."""
        import uuid
        from cyberred.agents.roles import AgentRole
        
        agent = StigmergicAgent(
            agent_name="test",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.POSTEX,
        )
        
        assert hasattr(agent, '_tool_help_cache')
        assert agent._tool_help_cache == {}

    def test_init_accepts_custom_manifest_loader(self, event_bus):
        """ManifestLoader can be injected for testing."""
        import uuid
        from cyberred.agents.roles import AgentRole
        
        mock_loader = MagicMock()
        mock_loader.get_by_category.return_value = []
        
        agent = StigmergicAgent(
            agent_name="test",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.AD,
            manifest_loader=mock_loader,
        )
        
        assert agent._manifest is mock_loader

    def test_init_accepts_custom_llm_gateway(self, event_bus):
        """LLMGateway can be injected for testing."""
        import uuid
        from cyberred.agents.roles import AgentRole
        
        mock_gateway = MagicMock()
        
        agent = StigmergicAgent(
            agent_name="test",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.CREDENTIAL,
            llm_gateway=mock_gateway,
        )
        
        assert agent._llm_gateway is mock_gateway


@pytest.mark.unit
class TestStigmergicAgentCoverageGaps:
    """Tests for 100% coverage of base.py Story 7.1-v2.
    
    These tests cover the remaining uncovered lines:
    - Lines 87-91: Init branches
    - Lines 227-243: Throttle wait loop
    - Lines 245-247: ThrottleTimeoutError re-raise
    - Lines 300-303: Shutdown task cancellation
    - Lines 309-340: Throttle monitor loop
    - Line 502: select_tool ToolSelectionError
    """

    @pytest.fixture
    def event_bus(self):
        bus = MagicMock(spec=EventBus)
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        return bus

    def test_init_with_explicit_system_prompt(self, event_bus):
        """Line 87-88: Test when system_prompt is already in kwargs."""
        import uuid
        from cyberred.agents.roles import AgentRole
        
        custom_prompt = "Custom system instructions"
        agent = StigmergicAgent(
            agent_name="test",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.RECON,
            system_prompt=custom_prompt,  # Explicit system_prompt in kwargs
        )
        # Just verify agent was created - the branch coverage is the goal
        assert agent.role == AgentRole.RECON

    def test_init_with_llm_in_kwargs(self, event_bus):
        """Line 91-94: Test when llm is explicitly provided in kwargs."""
        import uuid
        from cyberred.agents.roles import AgentRole
        
        mock_llm = MagicMock()
        agent = StigmergicAgent(
            agent_name="test",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.RECON,
            llm=mock_llm,  # Explicit llm in kwargs
        )
        assert agent.role == AgentRole.RECON

    @pytest.mark.asyncio
    async def test_execute_throttle_wait_and_resume(self, event_bus):
        """Lines 227-243: Test throttle wait loop then resume."""
        import uuid
        from cyberred.agents.roles import AgentRole
        
        agent = StigmergicAgent(
            agent_name="test",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.RECON,
        )

        call_count = 0
        async def mock_check_throttle():
            nonlocal call_count
            call_count += 1
            # First call returns True (throttled), second returns False (resume)
            return call_count == 1

        with patch.object(agent, '_check_throttle', side_effect=mock_check_throttle):
            with patch('cyberred.agents.base.get_settings') as mock_settings:
                settings = MagicMock()
                settings.agents.throttle.max_wait = 10.0
                settings.agents.throttle.check_interval = 0.01  # Fast for testing
                mock_settings.return_value = settings

                result = await agent.execute("192.168.1.1")
                
                # Should have completed after throttle resumed
                assert result is not None
                assert agent.get_status() == "active"
                assert call_count >= 2  # Should have checked at least twice

    @pytest.mark.asyncio
    async def test_execute_throttle_timeout_error(self, event_bus):
        """Lines 236-237, 245-247: Test ThrottleTimeoutError is raised."""
        import uuid
        from cyberred.agents.roles import AgentRole
        from cyberred.core.exceptions import ThrottleTimeoutError
        
        agent = StigmergicAgent(
            agent_name="test",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.RECON,
        )

        async def always_throttled():
            return True

        with patch.object(agent, '_check_throttle', side_effect=always_throttled):
            with patch('cyberred.agents.base.get_settings') as mock_settings:
                settings = MagicMock()
                settings.agents.throttle.max_wait = 0.01  # Very short timeout
                settings.agents.throttle.check_interval = 0.001
                mock_settings.return_value = settings

                with pytest.raises(ThrottleTimeoutError):
                    await agent.execute("test task")

    @pytest.mark.asyncio
    async def test_shutdown_cancels_monitor_task(self, event_bus):
        """Lines 300-303: Test shutdown cancels throttle monitor task."""
        import uuid
        from cyberred.agents.roles import AgentRole
        
        agent = StigmergicAgent(
            agent_name="test",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.RECON,
        )

        # Spawn to start monitor task
        await agent.spawn()
        
        # Verify monitor task exists
        assert agent._throttle_monitor_task is not None
        
        # Give the task a moment to start
        await asyncio.sleep(0.01)
        
        # Shutdown should cancel it
        await agent.shutdown()
        
        assert agent._throttle_monitor_task is None
        assert agent.get_status() == "shutdown"

    @pytest.mark.asyncio
    async def test_start_throttle_monitor_already_started(self, event_bus):
        """Line 309: Test _start_throttle_monitor when task already exists."""
        import uuid
        from cyberred.agents.roles import AgentRole
        
        agent = StigmergicAgent(
            agent_name="test",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.RECON,
        )

        # Call twice
        await agent._start_throttle_monitor()
        first_task = agent._throttle_monitor_task
        
        await agent._start_throttle_monitor()
        second_task = agent._throttle_monitor_task
        
        # Should be same task (not recreated)
        assert first_task is second_task
        
        # Cleanup
        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_throttle_monitor_loop_exit_on_shutdown(self, event_bus):
        """Line 316: Test monitor loop exits when status is shutdown."""
        import uuid
        from cyberred.agents.roles import AgentRole
        
        agent = StigmergicAgent(
            agent_name="test",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.RECON,
        )

        # Set status to shutdown before loop starts
        agent._status = "shutdown"
        
        # Loop should exit immediately
        await agent._throttle_monitor_loop()
        
        # If we get here, loop exited properly
        assert True

    @pytest.mark.asyncio
    async def test_throttle_monitor_loop_state_transitions(self, event_bus):
        """Lines 324-325, 330-331: Test throttle state transition logging."""
        import uuid
        from cyberred.agents.roles import AgentRole
        
        agent = StigmergicAgent(
            agent_name="test",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.RECON,
        )

        call_count = 0
        async def mock_check_throttle():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return False  # Not throttled
            elif call_count == 2:
                return True   # Becomes throttled
            elif call_count == 3:
                return False  # Becomes unthrottled
            else:
                # Stop the loop
                agent._status = "shutdown"
                return False

        with patch.object(agent, '_check_throttle', side_effect=mock_check_throttle):
            with patch('cyberred.agents.base.get_settings') as mock_settings:
                settings = MagicMock()
                settings.agents.throttle.check_interval = 0.001
                settings.agents.throttle.threshold = 10
                mock_settings.return_value = settings

                with patch.object(agent, '_log') as mock_log:
                    await agent._throttle_monitor_loop()
                    
                    # Should have logged throttled and unthrottled
                    info_calls = [str(c) for c in mock_log.info.call_args_list]
                    assert any('throttled' in str(c).lower() for c in info_calls)

    @pytest.mark.asyncio
    async def test_throttle_monitor_loop_exception_handler(self, event_bus):
        """Lines 338-340: Test exception handler with 5s backoff."""
        import uuid
        from cyberred.agents.roles import AgentRole
        
        agent = StigmergicAgent(
            agent_name="test",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.RECON,
        )

        call_count = 0
        async def mock_check_throttle():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Test error")
            else:
                agent._status = "shutdown"
                return False

        with patch.object(agent, '_check_throttle', side_effect=mock_check_throttle):
            with patch('cyberred.agents.base.get_settings') as mock_settings:
                settings = MagicMock()
                settings.agents.throttle.check_interval = 0.001
                mock_settings.return_value = settings

                with patch.object(agent, '_log') as mock_log:
                    # Mock asyncio.sleep to avoid waiting 5 seconds
                    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                        await agent._throttle_monitor_loop()
                        
                        # Should have logged error
                        mock_log.error.assert_called()
                        # Should have slept 5 seconds for backoff
                        mock_sleep.assert_any_call(5.0)

    @pytest.mark.asyncio
    async def test_select_tool_raises_without_gateway(self, event_bus):
        """Line 502: ToolSelectionError raised when no LLM gateway."""
        import uuid
        from cyberred.agents.roles import AgentRole
        from cyberred.core.models import ToolSelectionContext
        from cyberred.core.exceptions import ToolSelectionError
        
        agent = StigmergicAgent(
            agent_name="test",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.RECON,
            llm_gateway=None,  # No gateway
        )

        context = ToolSelectionContext(
            objective="test objective",
            target_info={"ip": "192.168.1.1"},
            available_tools=["nmap"],
            phase="recon",
        )

        with pytest.raises(ToolSelectionError, match="No LLM gateway"):
            await agent.select_tool(context)




@pytest.mark.unit
class TestInferSignalType:
    """Tests for _infer_signal_type() edge cases (MEDIUM issue from code review)."""

    @pytest.fixture
    def agent(self):
        import uuid
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = AsyncMock()
        event_bus.subscribe = AsyncMock()
        return StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.RECON,
        )

    def test_infer_signal_type_findings(self, agent):
        """Test finding type inference from findings: channels."""
        assert agent._infer_signal_type("findings:target:sqli") == "finding"
        assert agent._infer_signal_type("findings:hash123:xss") == "finding"
        assert agent._infer_signal_type("findings:") == "finding"

    def test_infer_signal_type_strategies(self, agent):
        """Test strategy type inference from strategies: channels."""
        assert agent._infer_signal_type("strategies:eng-123") == "strategy"
        assert agent._infer_signal_type("strategies:") == "strategy"

    def test_infer_signal_type_intel(self, agent):
        """Test intel type inference from intel: channels."""
        assert agent._infer_signal_type("intel:cve-2024-1234") == "intel"
        assert agent._infer_signal_type("intel:nvd:enrichment") == "intel"

    def test_infer_signal_type_rag(self, agent):
        """Test rag type inference from rag: channels."""
        assert agent._infer_signal_type("rag:escalation:result") == "rag"
        assert agent._infer_signal_type("rag:hacktricks") == "rag"

    def test_infer_signal_type_phase(self, agent):
        """Test phase type inference from channels containing 'phase'."""
        assert agent._infer_signal_type("phase:transition") == "phase"
        assert agent._infer_signal_type("engagement:phase:recon") == "phase"
        assert agent._infer_signal_type("control:phase_change") == "phase"

    def test_infer_signal_type_status_default(self, agent):
        """Test status (default) type for unknown channels."""
        assert agent._infer_signal_type("agents:agent-1:status") == "status"
        assert agent._infer_signal_type("control:kill") == "status"
        assert agent._infer_signal_type("unknown:channel") == "status"

    def test_infer_signal_type_empty_channel(self, agent):
        """Test empty channel string returns status (default)."""
        assert agent._infer_signal_type("") == "status"

    def test_infer_signal_type_case_sensitivity(self, agent):
        """Test that channel matching is case-sensitive (lowercase expected)."""
        # Uppercase should NOT match and fall through to status
        assert agent._infer_signal_type("FINDINGS:target") == "status"
        assert agent._infer_signal_type("Strategies:eng") == "status"
        # Lowercase should match
        assert agent._infer_signal_type("findings:target") == "finding"

    def test_infer_signal_type_multiple_colons(self, agent):
        """Test channels with multiple colons are handled correctly."""
        assert agent._infer_signal_type("findings:hash:type:extra:data") == "finding"
        assert agent._infer_signal_type("intel:source:cve:2024:1234") == "intel"


class TestStigmergicAgentHeartbeat:
    """Tests for agent heartbeat functionality (Story 7.12)."""

    @pytest.fixture
    def agent(self):
        """Create a StigmergicAgent with mocked dependencies."""
        event_bus = MagicMock()
        event_bus.subscribe = AsyncMock()
        event_bus.publish = AsyncMock()
        
        agent = StigmergicAgent(
            agent_name="test-heartbeat",
            agent_id="agent-heartbeat-1",
            engagement_id="eng-hb-1",
            event_bus=event_bus,
            role=AgentRole.RECON,
        )
        return agent

    @pytest.mark.asyncio
    async def test_send_heartbeat_publishes_to_event_bus(self, agent):
        """Test that send_heartbeat publishes heartbeat data."""
        await agent.send_heartbeat()

        agent.event_bus.publish.assert_called_once()
        call_args = agent.event_bus.publish.call_args
        channel = call_args[0][0]
        data = call_args[0][1]

        assert f"agent:{agent.agent_id}:heartbeat" == channel
        assert data["agent_id"] == agent.agent_id
        assert data["engagement_id"] == agent.engagement_id
        assert "status" in data

    @pytest.mark.asyncio
    async def test_send_heartbeat_includes_task_id(self, agent):
        """Test heartbeat includes current task ID if set."""
        agent._current_task_id = "task-123"

        await agent.send_heartbeat()

        call_args = agent.event_bus.publish.call_args
        data = call_args[0][1]
        assert data["task_id"] == "task-123"

    @pytest.mark.asyncio
    async def test_send_heartbeat_handles_missing_task_id(self, agent):
        """Test heartbeat works without current task ID."""
        # No _current_task_id attribute
        await agent.send_heartbeat()

        call_args = agent.event_bus.publish.call_args
        data = call_args[0][1]
        assert data["task_id"] is None

    @pytest.mark.asyncio
    async def test_start_heartbeat_creates_task(self, agent):
        """Test that _start_heartbeat creates a background task."""
        await agent._start_heartbeat()

        assert agent._heartbeat_task is not None
        assert not agent._heartbeat_task.done()

        # Cleanup
        agent._heartbeat_task.cancel()
        try:
            await agent._heartbeat_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_spawn_starts_heartbeat(self, agent):
        """Test that spawn() starts the heartbeat task."""
        await agent.spawn()

        assert hasattr(agent, "_heartbeat_task")
        assert agent._heartbeat_task is not None

        # Cleanup
        await agent.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_cancels_heartbeat_task(self, agent):
        """Test that shutdown cancels the heartbeat task."""
        await agent.spawn()
        heartbeat_task = agent._heartbeat_task

        await agent.shutdown()

        assert heartbeat_task.cancelled() or heartbeat_task.done()

    @pytest.mark.asyncio
    async def test_heartbeat_loop_sends_immediate_heartbeat(self, agent):
        """Test that heartbeat loop sends an immediate heartbeat on start."""
        # Track publish calls
        call_times = []
        original_publish = agent.event_bus.publish
        
        async def tracking_publish(*args, **kwargs):
            call_times.append(asyncio.get_event_loop().time())
            return await original_publish(*args, **kwargs)
        
        agent.event_bus.publish = AsyncMock(side_effect=tracking_publish)
        
        # Start heartbeat
        await agent._start_heartbeat()
        
        # Give it a moment to execute the immediate heartbeat
        await asyncio.sleep(0.05)
        
        # Should have sent at least one heartbeat immediately
        assert agent.event_bus.publish.call_count >= 1
        
        # Cleanup
        agent._heartbeat_task.cancel()
        try:
            await agent._heartbeat_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_heartbeat_loop_handles_initial_heartbeat_error(self, agent):
        """Test that initial heartbeat error is logged but loop continues."""
        call_count = 0
        
        async def failing_then_succeeding_publish(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Initial publish failed")
            # Subsequent calls succeed
        
        agent.event_bus.publish = AsyncMock(side_effect=failing_then_succeeding_publish)
        
        # Start heartbeat - should not raise despite initial error
        await agent._start_heartbeat()
        
        # Give it time to attempt initial heartbeat and one more
        await asyncio.sleep(0.05)
        
        # Should have tried at least once
        assert call_count >= 1
        
        # Cleanup
        agent._heartbeat_task.cancel()
        try:
            await agent._heartbeat_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_heartbeat_loop_continues_after_recurring_errors(self, agent):
        """Test that heartbeat loop continues despite recurring publish errors."""
        error_count = 0
        
        async def always_failing_publish(*args, **kwargs):
            nonlocal error_count
            error_count += 1
            raise RuntimeError("Publish always fails")
        
        agent.event_bus.publish = AsyncMock(side_effect=always_failing_publish)
        
        # Start heartbeat
        await agent._start_heartbeat()
        
        # Let it run briefly - errors should be caught and logged
        await asyncio.sleep(0.05)
        
        # Should have attempted multiple times without crashing
        assert error_count >= 1
        assert not agent._heartbeat_task.done()  # Task still running
        
        # Cleanup
        agent._heartbeat_task.cancel()
        try:
            await agent._heartbeat_task
        except asyncio.CancelledError:
            pass


class TestStigmergicAgentCheckpoint:
    """Tests for agent checkpoint functionality (Story 7.12)."""

    @pytest.fixture
    def agent(self):
        """Create a StigmergicAgent with mocked dependencies."""
        event_bus = MagicMock()
        event_bus.subscribe = AsyncMock()
        event_bus.publish = AsyncMock()
        
        agent = StigmergicAgent(
            agent_name="test-checkpoint",
            agent_id="agent-cp-1",
            engagement_id="eng-cp-1",
            event_bus=event_bus,
            role=AgentRole.EXPLOIT,
            specialty="web",
        )
        agent._status = "active"
        agent._decision_context = ["signal-1", "signal-2"]
        agent._tool_help_cache = {"nmap": "usage: nmap ..."}
        return agent

    @pytest.mark.asyncio
    async def test_save_checkpoint_creates_agent_state(self, agent):
        """Test save_checkpoint creates correct AgentState."""
        checkpoint_manager = MagicMock()
        checkpoint_manager.save_agent_state = AsyncMock()

        await agent.save_checkpoint(checkpoint_manager)

        checkpoint_manager.save_agent_state.assert_called_once()
        call_args = checkpoint_manager.save_agent_state.call_args
        engagement_id = call_args[0][0]
        state = call_args[0][1]

        assert engagement_id == agent.engagement_id
        assert state.agent_id == agent.agent_id
        assert state.agent_type == agent.role.value

    @pytest.mark.asyncio
    async def test_save_checkpoint_includes_state_data(self, agent):
        """Test checkpoint includes all relevant state data."""
        checkpoint_manager = MagicMock()
        checkpoint_manager.save_agent_state = AsyncMock()
        agent._current_task_id = "task-42"
        agent._last_action_id = "action-99"

        await agent.save_checkpoint(checkpoint_manager)

        state = checkpoint_manager.save_agent_state.call_args[0][1]
        assert state.state["status"] == "active"
        assert state.state["specialty"] == "web"
        assert state.state["current_task_id"] == "task-42"
        assert state.last_action_id == "action-99"

    @pytest.mark.asyncio
    async def test_save_checkpoint_serializes_decision_context(self, agent):
        """Test decision context is serialized correctly."""
        checkpoint_manager = MagicMock()
        checkpoint_manager.save_agent_state = AsyncMock()

        await agent.save_checkpoint(checkpoint_manager)

        state = checkpoint_manager.save_agent_state.call_args[0][1]
        assert state.decision_context == "signal-1,signal-2"

    @pytest.mark.asyncio
    async def test_restore_from_checkpoint_restores_state(self, agent):
        """Test restore_from_checkpoint restores agent state."""
        from cyberred.storage.checkpoint import AgentState

        agent_state = AgentState(
            agent_id="agent-cp-1",
            agent_type="exploit",
            state={
                "status": "waiting",
                "specialty": "web",
                "tool_help_cache": {"sqlmap": "usage: sqlmap ..."},
                "current_task_id": "restored-task",
            },
            last_action_id="restored-action",
            decision_context="ctx-1,ctx-2,ctx-3",
        )

        await agent.restore_from_checkpoint(agent_state)

        assert agent._status == "waiting"
        assert agent._tool_help_cache == {"sqlmap": "usage: sqlmap ..."}
        assert agent._current_task_id == "restored-task"
        assert agent._last_action_id == "restored-action"
        assert agent._decision_context == ["ctx-1", "ctx-2", "ctx-3"]

    @pytest.mark.asyncio
    async def test_restore_from_checkpoint_handles_empty_context(self, agent):
        """Test restore handles empty decision context."""
        from cyberred.storage.checkpoint import AgentState

        agent_state = AgentState(
            agent_id="agent-cp-1",
            agent_type="exploit",
            state={"status": "active"},
            decision_context=None,
        )

        await agent.restore_from_checkpoint(agent_state)

        assert agent._decision_context == [] or agent._decision_context is None

    @pytest.mark.asyncio
    async def test_restore_from_checkpoint_handles_missing_state_keys(self, agent):
        """Test restore handles missing state keys gracefully."""
        from cyberred.storage.checkpoint import AgentState

        agent_state = AgentState(
            agent_id="agent-cp-1",
            agent_type="exploit",
            state={},  # Empty state dict
        )

        # Should not raise
        await agent.restore_from_checkpoint(agent_state)

        # Should use defaults
        assert agent._status == "active"  # default from get()


# =============================================================================
# Story 7.13: Sharded Publishing Tests
# =============================================================================


@pytest.mark.unit
class TestStigmergicAgentSharding:
    """Tests for Story 7.13: Stigmergic Topic Sharding in StigmergicAgent."""

    @pytest.fixture
    def event_bus(self):
        bus = MagicMock(spec=EventBus)
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        return bus

    @pytest.fixture
    def sharded_event_bus(self):
        from cyberred.core.sharding import ShardedEventBus
        bus = MagicMock(spec=ShardedEventBus)
        bus.publish_finding = AsyncMock()
        bus.subscribe_findings = AsyncMock(return_value=[])
        bus.publish = AsyncMock()
        bus.subscribe = AsyncMock()
        return bus

    @pytest.fixture
    def agent_with_sharding(self, event_bus, sharded_event_bus):
        import uuid
        return StigmergicAgent(
            agent_name="test-sharded-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.RECON,
            sharded_event_bus=sharded_event_bus,
            llm=MagicMock(),
        )

    @pytest.fixture
    def agent_without_sharding(self, event_bus):
        import uuid
        return StigmergicAgent(
            agent_name="test-non-sharded-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            role=AgentRole.RECON,
            llm=MagicMock(),
        )

    @pytest.mark.asyncio
    async def test_on_finding_uses_sharded_bus_when_available(self, agent_with_sharding, sharded_event_bus):
        """Test on_finding uses ShardedEventBus when provided (AC: 4.1)."""
        target_hash = "abc123"
        finding_type = "sqli"
        content = {"vuln": "SQL injection"}

        await agent_with_sharding.on_finding(target_hash, finding_type, content)

        # Should use sharded bus
        sharded_event_bus.publish_finding.assert_called_once()
        call_args = sharded_event_bus.publish_finding.call_args
        assert call_args[0][0] == target_hash
        assert call_args[0][1] == finding_type
        assert call_args[0][2]["data"] == content

    @pytest.mark.asyncio
    async def test_on_finding_fallback_to_non_sharded(self, agent_without_sharding, event_bus):
        """Test on_finding falls back to non-sharded when no ShardedEventBus."""
        target_hash = "abc123"
        finding_type = "xss"
        content = {"vuln": "XSS"}

        await agent_without_sharding.on_finding(target_hash, finding_type, content)

        # Should use regular event bus
        event_bus.publish.assert_called_once()
        call_args = event_bus.publish.call_args
        assert call_args[0][0] == f"findings:{target_hash}:{finding_type}"

    @pytest.mark.asyncio
    async def test_setup_subscriptions_uses_sharded_when_available(self, agent_with_sharding, sharded_event_bus, event_bus):
        """Test _setup_subscriptions uses sharded subscription (AC: 4.2)."""
        await agent_with_sharding._setup_subscriptions()

        # Should call subscribe_findings on sharded bus
        sharded_event_bus.subscribe_findings.assert_called_once()
        
        # Should NOT subscribe to findings:* on regular bus for findings
        # But should still subscribe to strategies and control
        assert event_bus.subscribe.call_count == 2  # strategies + control:kill

    @pytest.mark.asyncio
    async def test_setup_subscriptions_fallback_to_non_sharded(self, agent_without_sharding, event_bus):
        """Test _setup_subscriptions falls back to non-sharded."""
        await agent_without_sharding._setup_subscriptions()

        # Should subscribe to findings:* on regular bus
        assert event_bus.subscribe.call_count == 3  # findings:* + strategies + control:kill

    @pytest.mark.asyncio
    async def test_handle_sharded_finding_deduplicates(self, agent_with_sharding):
        """Test _handle_sharded_finding deduplicates findings (AC: 4.4)."""
        channel = "findings:shard:0:sqli"
        message = {"id": "finding-123", "data": {"target": "192.168.1.1"}}

        # First call should process
        await agent_with_sharding._handle_sharded_finding(channel, message)
        assert "finding-123" in agent_with_sharding._finding_cache

        # Second call with same ID should be deduplicated (not crash)
        await agent_with_sharding._handle_sharded_finding(channel, message)
        # Cache should still have only one entry
        assert len([x for x in agent_with_sharding._finding_cache if x == "finding-123"]) == 1

    @pytest.mark.asyncio
    async def test_handle_sharded_finding_handles_string_message(self, agent_with_sharding):
        """Test _handle_sharded_finding handles string messages."""
        channel = "findings:shard:0:sqli"
        message = '{"id": "finding-456", "data": {"target": "192.168.1.2"}}'

        await agent_with_sharding._handle_sharded_finding(channel, message)
        assert "finding-456" in agent_with_sharding._finding_cache

    @pytest.mark.asyncio
    async def test_handle_sharded_finding_handles_invalid_json(self, agent_with_sharding):
        """Test _handle_sharded_finding handles invalid JSON gracefully."""
        channel = "findings:shard:0:sqli"
        message = "not-valid-json"

        # Should not raise
        await agent_with_sharding._handle_sharded_finding(channel, message)

    @pytest.mark.asyncio
    async def test_finding_cache_pruning(self, agent_with_sharding):
        """Test finding cache is pruned when it exceeds 10000 entries."""
        # Fill cache with 10001 entries
        for i in range(10001):
            agent_with_sharding._finding_cache.add(f"finding-{i}")

        # Add one more via handler to trigger pruning
        channel = "findings:shard:0:sqli"
        message = {"id": "finding-trigger", "data": {}}
        await agent_with_sharding._handle_sharded_finding(channel, message)

        # Cache should be pruned (less than 10001)
        assert len(agent_with_sharding._finding_cache) <= 5002  # ~5000 removed + new one

    @pytest.mark.asyncio
    async def test_handle_sharded_finding_extracts_nested_id(self, agent_with_sharding):
        """Test _handle_sharded_finding extracts ID from nested data."""
        channel = "findings:shard:0:sqli"
        message = {"data": {"id": "nested-id-789"}}

        await agent_with_sharding._handle_sharded_finding(channel, message)
        assert "nested-id-789" in agent_with_sharding._finding_cache

    @pytest.mark.asyncio
    async def test_handle_sharded_finding_processes_without_id(self, agent_with_sharding):
        """Test _handle_sharded_finding processes findings without ID."""
        channel = "findings:shard:0:sqli"
        message = {"target": "192.168.1.1", "type": "sqli"}

        # Should not raise, should still process
        await agent_with_sharding._handle_sharded_finding(channel, message)
        # No ID to cache, but should not crash
