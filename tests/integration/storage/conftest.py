"""Integration test fixtures for storage tests."""

import pytest

from cyberred.core.event_bus import EventBus


@pytest.fixture
async def redis_event_bus(redis_container):
    """Provide EventBus connected to Redis test container.
    
    Args:
        redis_container: Redis container fixture from root conftest.
        
    Yields:
        EventBus instance connected to test Redis.
    """
    # Get Redis connection details
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    
    # Create EventBus with test Redis URL
    redis_url = f"redis://{host}:{port}/0"
    event_bus = EventBus(redis_url=redis_url)
    
    try:
        yield event_bus
    finally:
        # Cleanup
        if hasattr(event_bus, 'close'):
            await event_bus.close()
