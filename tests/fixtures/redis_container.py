"""Pytest fixture for Redis testcontainers.

Provides a real Redis container for integration tests per the NO MOCKS policy.
"""

import time
import pytest
import structlog
from testcontainers.redis import RedisContainer

log = structlog.get_logger()


@pytest.fixture(scope="function")
def redis_container():
    """Provide a real Redis container for integration tests.
    
    This fixture:
    - Starts a Redis container on a random port
    - Provides connection details to tests
    - Cleans up after tests complete
    
    Yields:
        RedisContainer instance with get_container_host_ip() and get_exposed_port(6379)
    """
    container = RedisContainer("redis:7-alpine")
    
    start_time = time.time()
    container.start()
    startup_ms = int((time.time() - start_time) * 1000)
    
    log.info(
        "redis_container_started",
        container_startup_ms=startup_ms,
        host=container.get_container_host_ip(),
        port=container.get_exposed_port(6379),
    )
    
    try:
        yield container
    finally:
        try:
            container.stop()
            log.info("redis_container_stopped")
        except Exception as e:
            log.warning("redis_container_cleanup_error", error=str(e))
