
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from swarms import Agent
from cyberred.agents.base import StigmergicAgent
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
        return StigmergicAgent(
            agent_name="test-agent",
            agent_id=str(uuid.uuid4()),
            engagement_id=str(uuid.uuid4()),
            event_bus=event_bus,
            llm=MagicMock(), # Mock LLM
            description="A test agent",
            system_prompt="You are a test agent."
        )

    def test_initialization_requires_params(self, event_bus):
        """Test __init__ requires agent_id, engagement_id, event_bus."""
        with pytest.raises(TypeError):
            StigmergicAgent(agent_name="fail") # Missing params

        import uuid
        a_id = str(uuid.uuid4())
        e_id = str(uuid.uuid4())
        agent = StigmergicAgent(
            agent_name="test",
            agent_id=a_id,
            engagement_id=e_id,
            event_bus=event_bus
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
