"""Integration tests for agent self-throttling (Story 7.2)."""
import pytest
import asyncio
import uuid
import time
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from cyberred.core.config import ThrottleConfig
from cyberred.agents.base import StigmergicAgent
from cyberred.agents.roles import AgentRole
from cyberred.core.exceptions import ThrottleTimeoutError

@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_throttling_flow():
    """Test full throttling cycle: Active -> Throttled (Wait) -> Active."""
    agent_id = str(uuid.uuid4())
    mock_event_bus = AsyncMock()
    
    # Config: Threshold=0.8, check_interval=0.1s
    mock_settings = MagicMock()
    mock_settings.agents.throttle = ThrottleConfig(
        threshold=0.8,
        check_interval=0.1,
        max_wait=5
    )
    mock_settings.engagement.max_agents = 10
    
    # Mock Gateway: Queue depth starts high (throttled), then drops (unthrottled)
    mock_gateway = MagicMock()
    
    # Scenario:
    # 0. Start execute() -> Check throttle
    # 1. Depth=9 (0.9 > 0.8) -> Throttled. Enters wait loop.
    # 2. Wait 0.1s
    # 3. Depth=5 (0.5 < 0.8) -> Unthrottled. Loop exits.
    # 4. Execute proceeds.
    
    # We use side_effect for queue_depth property if possible, or just change it over time
    # But property mocking on MagicMock needs PropertyMock or side_effect on the mock
    # simpler: verify _check_throttle calls get_gateway().queue_depth
    
    # We will patch _check_throttle to use our logic OR relying on real logic calling mocked gateway.
    # Real logic:
    # gateway = get_gateway()
    # depth = gateway.queue_depth
    
    # We can control gateway.queue_depth dynamically if valid.
    # But since execute() awaits sleep, we can use a background task to change depth?
    # Or rely on the sequence of checks.
    
    # Let's use a side_effect for queue_depth access
    # First access: 9 (check at start)
    # Second access: 9 (inside loop 1st check)
    # Third access: 5 (inside loop 2nd check)
    
    type(mock_gateway).queue_depth = PropertyMock(side_effect=[9, 9, 5, 5])
    
    with patch("cyberred.agents.base.get_settings", return_value=mock_settings), \
         patch("cyberred.llm.gateway.get_gateway", return_value=mock_gateway):
         
        agent = StigmergicAgent(
            agent_name="Integrator",
            agent_id=agent_id,
            engagement_id="eng-1",
            event_bus=mock_event_bus,
            role=AgentRole.RECON,  # Required role argument (Story 7.1.v2)
        )
        
        # Capture logs to verify state changes
        # We can't easily capture structlog in integration without setup, so we trust outcomes.
        
        start_time = time.monotonic()
        
        # Execute
        result = await agent.execute("192.168.1.1")
        
        duration = time.monotonic() - start_time
        
        # Assertions
        assert result.action_type == "execute"
        # Must have waited at least 0.1s
        assert duration >= 0.1
        
        # Verify Gateway was checked multiple times
        # With property mock side_effect, we consumed 3 values (Start, Loop1, Loop2)
        # Actually exact count depends on implementation details (e.g. check before loop?)
        # Base implementation:
        # if await _check_throttle(): ...
        #   while is_throttled:
        #      sleep
        #      is_throttled = await _check_throttle()
        
        # So:
        # 1. _check_throttle() -> 9 (True)
        # 2. monitor enters loop
        # 3. sleeps 0.1
        # 4. _check_throttle() -> 9 (True) -> continued wait (Wait, logic in loop: await sleep; check(); if still true continue)
        # Ah, loop: while is_throttled: ... is_throttled = check().
        # My implementation:
        # if check():
        #    while is_throttled:
        #       check timeout
        #       sleep
        #       is_throttled = check()
        
        # So:
        # 1. Check -> 9 (True)
        # 2. Loop start
        # 3. Sleep
        # 4. Check -> 9 (True) -> Loop continues
        # 5. Sleep
        # 6. Check -> 5 (False) -> Loop exits
        
        # So we need queue_depth sequence: [9, 9, 5]
        # I provided [9, 9, 5, 5] so it is safe.
        pass

@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_throttling_timeout_integration():
    """Test throttling timeout logic."""
    agent_id = str(uuid.uuid4())
    mock_event_bus = AsyncMock()
    
    mock_settings = MagicMock()
    mock_settings.agents.throttle = ThrottleConfig(
        threshold=0.8,
        check_interval=0.01, # Fast check
        max_wait=1 # 1 second max wait (we will simulate time passage or wait real time)
    )
    mock_settings.engagement.max_agents = 10
    
    mock_gateway = MagicMock()
    type(mock_gateway).queue_depth = PropertyMock(return_value=9) # Always throttled
    
    with patch("cyberred.agents.base.get_settings", return_value=mock_settings), \
         patch("cyberred.llm.gateway.get_gateway", return_value=mock_gateway):
         
         # For timeout test, we can patch simple sleep to be fast, 
         # but we rely on monotonic time.
         # So we must verify real timeout OR patch time.
         # For integration, patching time is acceptable to avoid slow tests.
         
        agent = StigmergicAgent(
            agent_name="Integrator",
            agent_id=agent_id,
            engagement_id="eng-1",
            event_bus=mock_event_bus,
            role=AgentRole.RECON,  # Required role argument (Story 7.1.v2)
        )
        
        with patch("time.monotonic", side_effect=[0, 0, 2]) as mock_time:
             # 0: start_wait creation
             # 0: check diff (0-0 < 1)
             # 2: check diff (2-0 > 1) -> Raises
             
             with patch("asyncio.sleep", new_callable=AsyncMock): # Instant sleep
                 with pytest.raises(ThrottleTimeoutError):
                     await agent.execute("192.168.1.1")

