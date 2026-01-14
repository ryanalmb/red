"""Unit tests for agent self-throttling (Story 7.2)."""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pydantic import ValidationError

from cyberred.core.config import Settings, ThrottleConfig, AgentsConfig

@pytest.mark.unit
class TestThrottleConfig:
    """Test ThrottleConfig model."""

    def test_throttle_config_defaults(self):
        """Test ThrottleConfig default values."""
        config = ThrottleConfig()
        assert config.threshold == 0.8
        assert config.check_interval == 5.0
        assert config.max_wait == 300

    def test_throttle_config_validation(self):
        """Test ThrottleConfig validation."""
        # Valid config with percentage threshold
        config = ThrottleConfig(threshold=0.5, check_interval=1.0)
        assert config.threshold == 0.5
        assert config.check_interval == 1.0

        # Valid config with raw count threshold (> 1.0 is now allowed)
        config = ThrottleConfig(threshold=10.0)
        assert config.threshold == 10.0

        # Invalid threshold < 0.0
        with pytest.raises(ValidationError):
            ThrottleConfig(threshold=-0.1)

        # Invalid check_interval <= 0
        with pytest.raises(ValidationError):
            ThrottleConfig(check_interval=0.0)

        # Invalid max_wait <= 0
        with pytest.raises(ValidationError):
            ThrottleConfig(max_wait=0)

    def test_agents_config_structure(self):
        """Test AgentsConfig structure."""
        config = AgentsConfig()
        assert isinstance(config.throttle, ThrottleConfig)

    def test_settings_has_throttle_config(self):
        """Test Settings includes throttle config."""
        settings = Settings()
        assert hasattr(settings, "agents")
        assert isinstance(settings.agents, AgentsConfig)
        assert isinstance(settings.agents.throttle, ThrottleConfig)
        
        # Test defaults
        assert settings.agents.throttle.threshold == 0.8

    def test_hot_reload_paths(self):
        """Test hot reload paths are defined."""
        from cyberred.core.config import HOT_RELOAD_SAFE_PATHS
        assert "agents.throttle.threshold" in HOT_RELOAD_SAFE_PATHS
        assert "agents.throttle.check_interval" in HOT_RELOAD_SAFE_PATHS

@pytest.mark.unit
class TestAgentThrottleState:
    """Test agent throttling state machine."""

    @pytest.fixture
    def mock_gateway(self):
        """Mock LLMGateway."""
        # Patch where it's defined/imported from because it's imported inside the method
        with patch("cyberred.llm.gateway.get_gateway") as mock_get:
            gateway = MagicMock()
            gateway.queue_depth = 0
            mock_get.return_value = gateway
            yield gateway

    @pytest.fixture
    def mock_settings(self):
        """Mock Settings."""
        # Patching local name in agents.base because it is imported at top level
        with patch("cyberred.agents.base.get_settings") as mock_get:
            settings = MagicMock()
            settings.agents.throttle.threshold = 0.8
            mock_get.return_value = settings
            yield settings

    @pytest.fixture
    def mock_event_bus(self):
        """Mock EventBus."""
        return AsyncMock()

    @pytest.fixture
    def agent(self, mock_event_bus, mock_gateway, mock_settings):
        """Create StigmergicAgent instance."""
        # Avoid circular import issues by importing inside fixture if needed
        from cyberred.agents.base import StigmergicAgent
        import uuid
        agent = StigmergicAgent(
            agent_name="TestAgent",
            agent_id=str(uuid.uuid4()), # Valid UUID
            engagement_id="test-engagement",
            event_bus=mock_event_bus
        )
        return agent

    @pytest.mark.asyncio
    async def test_check_throttle_below_threshold(self, agent, mock_gateway, mock_settings):
        """Test _check_throttle returns False when queue depth is below threshold."""
        # Setup: threshold = 0.8, max_agents = 100 -> target_depth = 80
        mock_settings.agents.throttle.threshold = 0.8
        mock_settings.engagement.max_agents = 100
        
        # Queue depth 50 is below 80 (80% of 100)
        mock_gateway.queue_depth = 50
        result = await agent._check_throttle()
        assert result is False
        
        # Queue depth 79 is still below threshold
        mock_gateway.queue_depth = 79
        result = await agent._check_throttle()
        assert result is False

    @pytest.mark.asyncio
    async def test_check_throttle_logic(self, agent, mock_gateway, mock_settings):
        """Test _check_throttle logic."""
        # Setup: threshold = 0.8, max_agents = 100
        mock_settings.agents.throttle.threshold = 0.8
        mock_settings.engagement.max_agents = 100
        
        # Case 1: Queue depth 79 (below 80% of 100) -> False
        mock_gateway.queue_depth = 79
        assert await agent._check_throttle() is False
        
        # Case 2: Queue depth 80 (at 80% of 100) -> True
        mock_gateway.queue_depth = 80
        assert await agent._check_throttle() is True
        
        # Case 3: Queue depth 81 (above 80% of 100) -> True
        mock_gateway.queue_depth = 81
        assert await agent._check_throttle() is True

    @pytest.mark.asyncio
    async def test_check_throttle_raw_count(self, agent, mock_gateway, mock_settings):
        """Test _check_throttle logic with raw count threshold (> 1.0)."""
        # Setup: threshold = 10.0 (raw count), max_agents ignored
        mock_settings.agents.throttle.threshold = 10.0
        
        # Case 1: Queue depth 9 -> False
        mock_gateway.queue_depth = 9
        assert await agent._check_throttle() is False
        
        # Case 2: Queue depth 10 -> True
        mock_gateway.queue_depth = 10
        assert await agent._check_throttle() is True

    @pytest.mark.asyncio
    async def test_status_transition_on_throttle(self, agent, mock_gateway, mock_settings):
        """Test status changes: active -> waiting -> active during execute()."""
        agent._status = "active"
        mock_settings.agents.throttle.threshold = 5.0  # Raw count 5
        mock_settings.agents.throttle.check_interval = 0.01  # Fast for testing
        mock_settings.agents.throttle.max_wait = 10
        
        # Setup: First check throttled (depth=6 >= 5), second check not throttled (depth=3 < 5)
        call_count = 0
        def queue_depth_side_effect():
            nonlocal call_count
            call_count += 1
            return 6 if call_count <= 2 else 3  # Throttled first, then released
        
        type(mock_gateway).queue_depth = property(lambda self: queue_depth_side_effect())
        
        # Track status changes
        status_history = []
        original_log_info = agent._log.info
        def capture_log(event, **kwargs):
            status_history.append((event, agent._status))
            return original_log_info(event, **kwargs)
        agent._log.info = capture_log
        
        # Execute should transition: active -> waiting -> active
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await agent.execute("192.168.1.1")
        
        # Verify status transitions occurred
        assert any(event == "task_execution_throttled" for event, _ in status_history)
        assert any(event == "task_execution_resumed" for event, _ in status_history)
        assert result.action_type == "execute"
        
        
    @pytest.mark.asyncio
    async def test_monitor_loop_logging(self, agent, mock_gateway, mock_settings):
        """Test monitor loop logs transitions."""
        # Setup
        mock_settings.agents.throttle.check_interval = 0.1
        agent._log = MagicMock()
        
        # Mock _check_throttle to toggle
        # 1. False (init) -> 2. True (throttle) -> 3. False (unthrottle) -> Stop
        # We need to run the loop for a bit. 
        # Since loop is infinite, we need to cancel it or have it check a condition.
        # Task 4 AC: "Test monitor loop exits when agent status is shutdown"
        
        async def mock_check_sequence():
            yield False
            yield True # logs agent_throttled
            yield False # logs agent_unthrottled
            agent._status = "shutdown" # Trigger exit
            yield False

        # We can patch `_check_throttle` or `asyncio.sleep` to control flow
        check_gen = mock_check_sequence()
        
        async def side_effect():
            try:
                val = await check_gen.__anext__()
                return val
            except StopAsyncIteration:
                return False

        with patch.object(agent, '_check_throttle', side_effect=side_effect):
             # Also patch sleep to be instant
             with patch("asyncio.sleep", new_callable=AsyncMock):
                 await agent._throttle_monitor_loop()
        
        # Verify logging calls
        # We expect "agent_throttled" and "agent_unthrottled"
        calls = [c[0][0] for c in agent._log.info.call_args_list]
        assert "agent_throttled" in calls
        assert "agent_unthrottled" in calls

    @pytest.mark.asyncio
    async def test_monitor_loop_shutdown(self, agent):
        """Test monitor loop exits on shutdown status."""
        agent._status = "shutdown"
        # Should exit immediately without any sleep calls
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await agent._throttle_monitor_loop()
            mock_sleep.assert_not_called()
        
        # Verify agent is still in shutdown status
        assert agent._status == "shutdown"

    @pytest.mark.asyncio
    async def test_execute_integration_waiting(self, agent, mock_settings):
        """Test execute waits when throttled."""
        from cyberred.core.exceptions import ThrottleTimeoutError
        
        mock_settings.agents.throttle.max_wait = 1
        
        # Mock _check_throttle: True (throttled) initially, then False
        async def mock_check_sequence():
            yield True  # First check -> throttled
            yield False # Second check -> released
            
        check_gen = mock_check_sequence()
        async def side_effect():
            try:
                val = await check_gen.__anext__()
                return val
            except StopAsyncIteration:
                return False

        with patch.object(agent, '_check_throttle', side_effect=side_effect):
            # Patch sleep to advance "time" or just return
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                # Should wait once then proceed
                # We need to ensure execute actually calls something that confirms it proceeded
                # execute returns AgentAction
                action = await agent.execute("192.168.1.1")
                
                assert action.action_type == "execute"
                # Should have slept once
                mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_execute_timeout(self, agent, mock_settings):
        """Test execute raises ThrottleTimeoutError."""
        from cyberred.core.exceptions import ThrottleTimeoutError
        
        mock_settings.agents.throttle.max_wait = 1
        
        # We need to advance time to trigger timeout
        # Implementation uses __import__("time").monotonic()
        # We can patch time.monotonic
        
        start_time = 0.0
        def tick():
            nonlocal start_time
            start_time += 10.0 # jump ahead 10s
            return start_time
            
        with patch("time.monotonic", side_effect=tick):
             # Always throttled
             with patch.object(agent, '_check_throttle', return_value=True):
                  with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                      with pytest.raises(ThrottleTimeoutError):
                          await agent.execute("192.168.1.1")


@pytest.mark.unit
class TestThrottleFailOpen:
    """Test fail-open behavior for AC3."""

    @pytest.fixture
    def mock_event_bus(self):
        """Mock EventBus."""
        return AsyncMock()

    @pytest.fixture
    def agent(self, mock_event_bus):
        """Create StigmergicAgent instance."""
        from cyberred.agents.base import StigmergicAgent
        import uuid
        agent = StigmergicAgent(
            agent_name="FailOpenTestAgent",
            agent_id=str(uuid.uuid4()),
            engagement_id="test-engagement",
            event_bus=mock_event_bus
        )
        return agent

    @pytest.mark.asyncio
    async def test_check_throttle_fail_open_on_gateway_error(self, agent):
        """Test _check_throttle returns False (fail-open) when gateway unavailable."""
        # Mock the log to capture calls
        agent._log = MagicMock()
        
        # Mock get_gateway to raise an exception
        with patch("cyberred.llm.gateway.get_gateway", side_effect=Exception("Connection refused")):
            result = await agent._check_throttle()
            
            # Should return False (fail-open) - don't block if we can't check
            assert result is False
            
            # Should have logged a warning
            agent._log.warning.assert_called_once()
            call_args = agent._log.warning.call_args
            assert call_args[0][0] == "throttle_check_failed"
            assert "Connection refused" in call_args[1]["error"]

    @pytest.mark.asyncio
    async def test_check_throttle_fail_open_on_settings_error(self, agent):
        """Test _check_throttle returns False when settings unavailable."""
        with patch("cyberred.llm.gateway.get_gateway") as mock_gateway:
            mock_gateway.return_value.queue_depth = 100
            with patch("cyberred.agents.base.get_settings", side_effect=Exception("Settings error")):
                result = await agent._check_throttle()
                
                # Should return False (fail-open)
                assert result is False


@pytest.mark.unit
class TestThrottleErrorPaths:
    """Test error handling paths in throttle implementation."""

    @pytest.fixture
    def mock_event_bus(self):
        """Mock EventBus."""
        return AsyncMock()

    @pytest.fixture
    def mock_settings(self):
        """Mock Settings."""
        with patch("cyberred.agents.base.get_settings") as mock_get:
            settings = MagicMock()
            settings.agents.throttle.threshold = 0.8
            settings.agents.throttle.check_interval = 0.01
            settings.agents.throttle.max_wait = 10
            settings.engagement.max_agents = 100
            mock_get.return_value = settings
            yield settings

    @pytest.fixture
    def mock_gateway(self):
        """Mock LLMGateway."""
        with patch("cyberred.llm.gateway.get_gateway") as mock_get:
            gateway = MagicMock()
            gateway.queue_depth = 0
            mock_get.return_value = gateway
            yield gateway

    @pytest.fixture
    def agent(self, mock_event_bus, mock_gateway, mock_settings):
        """Create StigmergicAgent instance."""
        from cyberred.agents.base import StigmergicAgent
        import uuid
        agent = StigmergicAgent(
            agent_name="ErrorPathTestAgent",
            agent_id=str(uuid.uuid4()),
            engagement_id="test-engagement",
            event_bus=mock_event_bus
        )
        return agent

    @pytest.mark.asyncio
    async def test_execute_throttle_logic_error_logs_and_continues(self, agent, mock_settings):
        """Test that generic errors in throttle logic are logged but execution continues."""
        # Mock the log to capture calls
        agent._log = MagicMock()
        
        # Make _check_throttle raise a non-ThrottleTimeoutError exception
        with patch.object(agent, '_check_throttle', side_effect=RuntimeError("Unexpected error")):
            # Should NOT raise, should log and continue (fail-open)
            result = await agent.execute("192.168.1.1")
            
            # Execution should complete
            assert result.action_type == "execute"
            
            # Error should have been logged
            agent._log.error.assert_called()
            call_args = agent._log.error.call_args
            assert call_args[0][0] == "throttle_logic_error"

    @pytest.mark.asyncio
    async def test_monitor_loop_error_logs_and_continues(self, agent, mock_settings):
        """Test that monitor loop logs errors and continues with backoff."""
        agent._status = "active"
        agent._log = MagicMock()
        
        # Make _check_throttle raise an error on first call, then succeed
        call_count = 0
        async def check_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Temporary failure")
            # After error, set status to shutdown to exit loop
            agent._status = "shutdown"
            return False
        
        with patch.object(agent, '_check_throttle', side_effect=check_side_effect):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await agent._throttle_monitor_loop()
                
                # Should have slept with backoff (5.0 seconds) at some point
                # Note: may also sleep with check_interval, so check any_call
                assert any(call[0] == (5.0,) for call in mock_sleep.call_args_list), \
                    f"Expected backoff sleep(5.0), got: {mock_sleep.call_args_list}"
                
                # Error should have been logged
                agent._log.error.assert_called()
                call_args = agent._log.error.call_args
                assert call_args[0][0] == "throttle_monitor_error"

    @pytest.mark.asyncio
    async def test_spawn_starts_throttle_monitor(self, agent):
        """Test that spawn() starts the throttle monitor task."""
        assert agent._throttle_monitor_task is None
        
        with patch.object(agent, '_setup_subscriptions', new_callable=AsyncMock):
            with patch.object(agent, '_throttle_monitor_loop', new_callable=AsyncMock) as mock_loop:
                await agent.spawn()
                
                # Monitor task should be created
                assert agent._throttle_monitor_task is not None
                assert agent._status == "active"

    @pytest.mark.asyncio
    async def test_shutdown_cancels_throttle_monitor(self, agent):
        """Test that shutdown() properly cancels the throttle monitor task."""
        # Create a mock task
        mock_task = AsyncMock()
        mock_task.cancel = MagicMock()
        agent._throttle_monitor_task = mock_task
        
        await agent.shutdown()
        
        # Task should be cancelled
        mock_task.cancel.assert_called_once()
        assert agent._throttle_monitor_task is None
        assert agent._status == "shutdown"

    @pytest.mark.asyncio
    async def test_monitor_loop_handles_cancelled_error(self, agent, mock_settings):
        """Test that monitor loop exits cleanly when CancelledError is raised."""
        agent._status = "active"
        
        # Make asyncio.sleep raise CancelledError (simulating task cancellation)
        with patch("asyncio.sleep", side_effect=asyncio.CancelledError()):
            # Should exit cleanly without raising
            await agent._throttle_monitor_loop()
        
        # Loop should have exited (no assertion error means it handled CancelledError)


@pytest.mark.unit
class TestThrottleConfigValidation:
    """Test ThrottleConfig validation edge cases."""

    def test_throttle_config_raw_count_threshold(self):
        """Test ThrottleConfig allows threshold > 1.0 for raw counts."""
        from cyberred.core.config import ThrottleConfig
        
        # Raw count thresholds should be allowed
        config = ThrottleConfig(threshold=5.0)
        assert config.threshold == 5.0
        
        config = ThrottleConfig(threshold=100.0)
        assert config.threshold == 100.0

    def test_throttle_config_percentage_threshold(self):
        """Test ThrottleConfig allows threshold < 1.0 for percentage."""
        from cyberred.core.config import ThrottleConfig
        
        config = ThrottleConfig(threshold=0.5)
        assert config.threshold == 0.5
        
        config = ThrottleConfig(threshold=0.0)
        assert config.threshold == 0.0

    def test_throttle_config_boundary_threshold(self):
        """Test ThrottleConfig boundary at 1.0."""
        from cyberred.core.config import ThrottleConfig
        
        # 1.0 exactly - treated as raw count of 1
        config = ThrottleConfig(threshold=1.0)
        assert config.threshold == 1.0
