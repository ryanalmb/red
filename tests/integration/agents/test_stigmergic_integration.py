
import pytest
import asyncio
import json
from testcontainers.redis import RedisContainer
from cyberred.storage.redis_client import RedisClient
from cyberred.core.config import RedisConfig
from cyberred.core.events import EventBus
from cyberred.agents.base import StigmergicAgent
from cyberred.agents.roles import AgentRole
from unittest.mock import MagicMock

@pytest.fixture(scope="module")
def redis_container():
    """Spin up a Redis container for integration tests."""
    with RedisContainer("redis:7.2-alpine") as redis:
        yield redis

@pytest.fixture
async def redis_client(redis_container):
    """Provide a connected RedisClient."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    
    config = RedisConfig(host=host, port=int(port))
    client = RedisClient(config, engagement_id="integration-test")
    await client.connect()
    yield client
    await client.close()

@pytest.fixture
def event_bus(redis_client):
    return EventBus(redis_client)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_stigmergic_coordination(event_bus):
    """
    Test end-to-end stigmergic coordination between two agents.
    Flow:
    1. Agent A and Agent B spawn and subscribe.
    2. Agent A publishes a finding.
    3. Agent B receives the finding via subscription -> on_signal.
    """
    
    # Create Agent A
    agent_a = StigmergicAgent(
        agent_name="Agent A",
        agent_id="agent-a",
        engagement_id="eng-1",
        event_bus=event_bus,
        role=AgentRole.RECON,
        llm=MagicMock()
    )
    await agent_a.spawn()
    
    # Create Agent B
    agent_b = StigmergicAgent(
        agent_name="Agent B",
        agent_id="agent-b",
        engagement_id="eng-1",
        event_bus=event_bus,
        role=AgentRole.EXPLOIT,
        llm=MagicMock()
    )
    
    # Spy on agent_b.on_signal to verify receipt
    # We can't easily use MagicMock on async method if we want original logic too, 
    # but we just want to verify it was called.
    received_signals = []
    original_on_signal = agent_b.on_signal
    
    async def spy_on_signal(channel, data):
        received_signals.append((channel, data))
        await original_on_signal(channel, data)
        
    agent_b.on_signal = spy_on_signal
    
    await agent_b.spawn()
    
    # Wait a moment for subscriptions to sync (Redis is fast but async)
    await asyncio.sleep(0.1)
    
    # Agent A publishes finding
    finding_content = {"vuln": "sqli", "url": "http://example.com"}
    target_hash = "aabbcc"
    await agent_a.on_finding(target_hash, "sqli", finding_content)
    
    # Wait for propagation
    await asyncio.sleep(0.2)
    
    # Assert Agent B received it
    assert len(received_signals) > 0
    channel, data = received_signals[0]
    
    expected_channel = f"findings:{target_hash}:sqli"
    assert channel == expected_channel
    
    # data should be dict (parsed JSON) or dict with raw_content
    # Our base implementation wraps finding data
    # message structure: {agent_id, engagement_id, data: content}
    assert data["agent_id"] == "agent-a"
    assert data["data"]["vuln"] == "sqli"
    
@pytest.mark.integration
@pytest.mark.asyncio
async def test_strategy_broadcast(event_bus):
    """Test strategy broadcast to all agents in engagement."""
    agent = StigmergicAgent(
        agent_name="Strategist",
        agent_id="strat-1",
        engagement_id="eng-1",
        event_bus=event_bus,
        role=AgentRole.RECON,
        llm=MagicMock()
    )
    
    received = []
    agent.on_signal = lambda c, d: received.append((c, d)) # mock async implicitly? No, needs awaitable
    
    async def mock_signal(c, d):
        received.append((c, d))
    agent.on_signal = mock_signal
    
    await agent.spawn()
    await asyncio.sleep(0.1)
    
    # Broadcast strategy
    strategy_channel = "strategies:eng-1"
    strategy_data = {"phase": "active_recon"}
    await event_bus.publish(strategy_channel, strategy_data)
    
    await asyncio.sleep(0.1)
    
    assert len(received) == 1
    assert received[0][0] == strategy_channel
    assert received[0][1]["phase"] == "active_recon"
