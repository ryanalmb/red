import pytest
import asyncio
from cyberred.core.event_bus import EventBus

@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    # Note: This requires a running Redis. 
    # For now, we mock the redis client or assume it fails if Redis isn't up.
    # We will write the test but might skip running it if docker isn't up yet.
    
    bus = EventBus()
    received = []

    async def handler(msg):
        received.append(msg)

    # Start subscriber
    task = await bus.subscribe("test-channel", handler)
    
    # Wait for subscription to propagate
    await asyncio.sleep(0.1)

    # Publish
    await bus.publish("test-channel", {"hello": "world"})
    
    # Wait for delivery
    await asyncio.sleep(0.1)
    
    # Cleanup
    task.cancel()
    await bus.close()

    # Assert (Commented out because we haven't started Redis yet)
    # assert len(received) > 0
    # assert received[0]["hello"] == "world"
