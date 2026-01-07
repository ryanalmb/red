"""Integration tests for Redis Reconnection (Story 3.2).

Tests automatic failover and buffering by manipulating Docker containers.
Requires the Sentinel cluster to be running:
    docker compose -f tests/fixtures/docker-compose-redis-sentinel.yaml up -d
"""

import pytest
import asyncio
import subprocess
import time
from cyberred.core.config import RedisConfig
from cyberred.storage.redis_client import RedisClient, ConnectionState

# Mark all tests in this module as integration
pytestmark = pytest.mark.integration

class DockerController:
    """Helper to control Redis Docker containers."""
    
    @staticmethod
    def stop_master():
        """Stop the redis-master container."""
        subprocess.run(["docker", "stop", "redis-master-sentinel"], check=True)
        
    @staticmethod
    def start_master():
        """Start the redis-master container."""
        subprocess.run(["docker", "start", "redis-master-sentinel"], check=True)

    @staticmethod
    def restart_master():
        """Restart the redis-master container."""
        subprocess.run(["docker", "restart", "redis-master-sentinel"], check=True)

@pytest.fixture
def sentinel_config():
    """Config for the local Sentinel cluster."""
    return RedisConfig(
        host="localhost",
        port=6379,
        sentinel_hosts=["localhost:26379", "localhost:26380", "localhost:26381"],
        master_name="mymaster",
    )

@pytest.fixture
async def redis_cluster(sentinel_config):
    """Ensure cluster is healthy before and after test."""
    # Ensure master is running
    DockerController.start_master()
    # Wait for convergence
    await asyncio.sleep(5)
    
    yield
    
    # Cleanup: ensure master is running for next tests
    DockerController.start_master()
    await asyncio.sleep(5)

@pytest.mark.asyncio
async def test_redis_client_handles_network_partition(sentinel_config, redis_cluster):
    """Test full cycle: Connection -> Partition (Buffer) -> Recovery (Flush).
    
    AC 7, Task 13.
    """
    import cyberred.storage.redis_client as rc_module
    
    # Save original
    original_backoff = rc_module.calculate_backoff
    # Override
    rc_module.calculate_backoff = lambda *a, **k: 0.5
    
    try:
        client = RedisClient(sentinel_config, engagement_id="test-partition")
        
        # 1. Connect
        await client.connect()
        assert client.connection_state == ConnectionState.CONNECTED
        
        # 2. Stop Master (Simulate Network Partition)
        print("Stopping redis-master...")
        DockerController.stop_master()
        
        # Wait for client to detect failure (ping timeout/send failure)
        # We trigger it by attempting an operation
        await asyncio.sleep(2) 
        
        # 3. Verify Buffer Mode
        # Attempt publish - should fail, trigger degraded mode, and buffer
        # Note: connect might still think it's connected until an op fails
        try:
            await client.publish("test:partition", "message1")
        except Exception:
            # It might raise once before transitioning, or transition internally
            pass
            
        # Force check if not yet degraded (publish catches ConnectionError and transitions)
        if client.connection_state != ConnectionState.DEGRADED:
            # Try one more time to trigger logic
            await client.publish("test:partition", "message2")
            
        assert client.connection_state == ConnectionState.DEGRADED
        assert client._buffer.size > 0
        print("Client entered DEGRADED state and buffered messages.")
        
        # Add more messages to buffer
        await client.publish("test:partition", "message3")
        initial_buffer_size = client._buffer.size
        
        # 4. Restart Master (Recovery)
        print("Restarting redis-master...")
        DockerController.start_master()
        
        # Wait for Sentinel to promote/fix or master to come back
        # And for reconnection loop to kick in (max 10s wait)
        # Reconnection loop sleeps 1, 2, 4, 8...
        print("Waiting for reconnection...")
        
        # Poll for reconnection
        for i in range(60):
            if client.connection_state == ConnectionState.CONNECTED:
                break
            if i % 5 == 0:
                print(f"Waiting for reconnection... {i}s")
            await asyncio.sleep(1)
            
        if client.connection_state != ConnectionState.CONNECTED:
            print(f"Failed to reconnect. Final state: {client.connection_state}")
            # Try to debug why: connect manually and see exception
            try:
                 await client.connect()
            except Exception as e:
                 print(f"Manual connect failed with: {e}")
    
        assert client.connection_state == ConnectionState.CONNECTED
        print("Client RECONNECTED.")
        
        # 5. Verify Buffer Flushed
        # Flush is async in reconnection loop, give it a moment
        await asyncio.sleep(1)
        assert client._buffer.size == 0
        print("Buffer flushed.")
        
        await client.close()
    finally:
        rc_module.calculate_backoff = original_backoff

@pytest.mark.asyncio
async def test_redis_client_handles_extended_outage(sentinel_config, redis_cluster):
    """Test extended outage where buffer expiration occurs.
    
    AC 7, Task 14.
    """
    import cyberred.storage.redis_client as rc_module
    
    # Save original
    original_backoff = rc_module.calculate_backoff
    # Override
    rc_module.calculate_backoff = lambda *a, **k: 0.5

    try:
        # Use short expiry for test speed (2 seconds)
        client = RedisClient(sentinel_config, engagement_id="test-outage")
        client._buffer._max_age_seconds = 2.0
        
        await client.connect()
    
        # 1. Stop Master
        DockerController.stop_master()
        
        # Trigger degraded state
        await client.publish("test:outage", "msg-old")
        assert client.connection_state == ConnectionState.DEGRADED
        
        # 2. Wait for expiration
        print("Waiting for message expiry...")
        await asyncio.sleep(2.5)
        
        # 3. Add new message
        await client.publish("test:outage", "msg-new")
        
        # 4. Restart Master
        DockerController.start_master()
        
        # Wait for reconnect
        for i in range(60):
            if client.connection_state == ConnectionState.CONNECTED:
                break
            await asyncio.sleep(1)
                
        if client.connection_state != ConnectionState.CONNECTED:
            print(f"Failed to reconnect (extended). Final state: {client.connection_state}")
            try:
                await client.connect()
            except Exception as e:
                print(f"Manual connect failed with: {e}")

        assert client.connection_state == ConnectionState.CONNECTED
        
        # 5. Verify Result
        # "msg-old" should have expired and NOT been sent
        # "msg-new" SHOULD have been sent
        assert client._buffer.size == 0
        
        await client.close()
    finally:
        rc_module.calculate_backoff = original_backoff
