import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from cyberred.tools.container_pool import (
    MockContainer,
    ContainerPool,
    FixtureLoader,
    ContainerProtocol,
    ContainerContext
)
from cyberred.core.models import ToolResult

@pytest.mark.asyncio
async def test_mock_container_execute():
    """Test that MockContainer.execute returns a ToolResult."""
    container = MockContainer()
    result = await container.execute("nmap -sV 192.168.1.1")
    
    assert isinstance(result, ToolResult)

def test_mock_container_implements_protocol():
    """Verify MockContainer implements ContainerProtocol."""
    assert issubclass(MockContainer, ContainerProtocol)

def test_fixture_loader_loads_file(tmp_path):
    """Test FixtureLoader reads file content."""
    # Setup
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "nmap.txt").write_text("Mock nmap output")
    
    loader = FixtureLoader(fixtures_dir=str(fixtures_dir))
    content = loader.load("nmap.txt")
    
    assert content == "Mock nmap output"

def test_fixture_loader_raises_error_on_missing_file():
    """Test FixtureLoader raises FileNotFoundError."""
    loader = FixtureLoader(fixtures_dir="/tmp/nonexistent")
    with pytest.raises(FileNotFoundError):
        loader.load("missing.txt")

def test_mock_container_detects_tool():
    """Test tool name detection."""
    container = MockContainer()
    
    cases = {
        "nmap -sV target": "nmap",
        "/usr/bin/nmap target": "nmap",
        "sqlmap -u http://target": "sqlmap",
        "./nuclei -t templates": "nuclei",
    }
    
    for cmd, expected in cases.items():
        assert container._detect_tool(cmd) == expected

def test_container_pool_init():
    """Test ContainerPool initialization."""
    from cyberred.tools.container_pool import ContainerPool
    pool = ContainerPool(mode="mock", size=5)
    assert pool._mode == "mock"
    assert pool._size == 5
    assert pool._available.empty()

@pytest.mark.asyncio
async def test_container_pool_acquire():
    """Test acquiring a container from the pool."""
    from cyberred.tools.container_pool import ContainerPool, MockContainer
    pool = ContainerPool(mode="mock")
    container = await pool.acquire()
    assert isinstance(container, MockContainer)

@pytest.mark.asyncio
async def test_container_pool_release():
    """Test releasing a container back to the pool."""
    from cyberred.tools.container_pool import ContainerPool
    pool = ContainerPool(mode="mock", size=1)
    container = await pool.acquire()
    
    # Pool empty after acquire
    assert pool._available.empty()
    
    await pool.release(container)
    
    # Pool has 1 item after release
    assert pool._available.qsize() == 1
    
    # Released item should be reusable
    reused = await pool._available.get()
    assert reused is container

@pytest.mark.asyncio
async def test_container_pool_context_manager():
    """Test using pool.acquire() as an async context manager."""
    from cyberred.tools.container_pool import ContainerPool, MockContainer
    pool = ContainerPool(mode="mock")
    
    async with pool.acquire() as container:
        assert isinstance(container, MockContainer)
        # Should be removed from pool (even if mock creates new, the interface implies management)
        # For mock mode simplistic implementation, we just care that it returns a container
        pass
    
    # After exit, it should be released (if we track it).
    # In our current mock implementation, release puts it in queue.
    # We can verify side effect if we check queue size or modify implementation to reuse.
    # For now, just verifying syntax works is the goal of "Async acquire with context manager".
    pass

@pytest.mark.asyncio
async def test_mock_container_latency():
    """Test that mock container simulates latency."""
    from cyberred.tools.container_pool import MockContainer
    import time
    
    latency_ms = 100
    # Assuming we pass latency configuration somehow, maybe via loader or init?
    # Task 9 AC says "configurable latency". 
    # Let's assume we can pass it to MockContainer explicitly or via Pool.
    # Updated design implies passing it in __init__.
    
    container = MockContainer(latency_ms=latency_ms)
    
    start = time.time()
    await container.execute("nmap target")
    duration = (time.time() - start) * 1000
    
    # Should be at least latency_ms
    assert duration >= latency_ms
    # Allow some buffer but ensuring it did wait
    assert duration < latency_ms + 200 # 200ms buffer for overhead

@pytest.mark.asyncio
async def test_real_container_initialization_config():
    """Test RealContainer is initialized with correct docker config."""
    from cyberred.tools.container_pool import RealContainer
    from unittest.mock import patch, MagicMock
    
    # Mock DockerContainer to intercept constructor calls
    with patch("cyberred.tools.container_pool.DockerContainer") as mock_cls:
        container = RealContainer(image="custom/image")
        await container.start()
        
        # Verify DockerContainer initialized with correct image
        mock_cls.assert_called_with("custom/image")
        
        mock_instance = mock_cls.return_value
        
        # Verify network isolation and capabilities
        # Check if with_kwargs was called with cap_add and network_mode
        call_args = mock_instance.with_kwargs.call_args
        assert call_args is not None
        
        # Network mode check
        assert "network_mode" in call_args.kwargs
        assert call_args.kwargs["network_mode"] == "none"
        # Check if with_kwargs was called with cap_add
        call_args = mock_instance.with_kwargs.call_args
        assert call_args is not None
        assert "cap_add" in call_args.kwargs
        caps = call_args.kwargs["cap_add"]
        assert "NET_ADMIN" in caps
        assert "NET_RAW" in caps

@pytest.mark.asyncio
async def test_real_container_start_error_handling():
    """Test RealContainer handles start errors appropriately."""
    from cyberred.tools.container_pool import RealContainer
    from unittest.mock import patch, MagicMock
    
    with patch("cyberred.tools.container_pool.DockerContainer") as mock_cls:
        # Arrange
        mock_instance = mock_cls.return_value
        mock_instance.start.side_effect = Exception("Docker daemon unavailable")
        
        container = RealContainer()
        
        # Act & Assert
        # Should wrap generic exception in something more specific or at least ensure clean failure
        # For now, let's just assert it propagates the exception so we can verify the test fails 
        # (current implementation propagates it, but we want to confirm this behavior or improve it)
        with pytest.raises(Exception, match="Docker daemon unavailable"):
            await container.start()
            
        # If we decided to wrap it in a custom exception later (REFACTOR step), we'd change this test.
        # But for RED phase of "Add error handling", we might want to check for a specific behavior we haven't implemented yet.
        # Let's say we want it to raise a RuntimeError when start fails, wrapping the original.
        
@pytest.mark.asyncio
async def test_real_container_stop_safe():
    """Test RealContainer stop is safe even if container not started or fails."""
    from cyberred.tools.container_pool import RealContainer
    from unittest.mock import patch, MagicMock
    
    container = RealContainer()
    # Should not raise
    await container.stop()
    
    with patch("cyberred.tools.container_pool.DockerContainer"):
        container = RealContainer()
        # Mocking internal container to simulate started state
        container._container = MagicMock()
        container._container.stop.side_effect = Exception("Failed to stop")
        
        # Act & Assert
        # Stop should probably just log error and return, or allow propagation?
        # A "safe" stop typically swallows errors during cleanup or logs them.
        # Let's define the requirement: stop() should not raise if container is already stopped or fails to stop.
        # This implies we need to change implementation (RED).
        await container.stop()

@pytest.mark.asyncio
async def test_real_container_execute_stderr_captured():
    """Test RealContainer separates stdout and stderr."""
    from cyberred.tools.container_pool import RealContainer
    from unittest.mock import patch, MagicMock
    
    container = RealContainer()
    container._container = MagicMock()
    
    # Mock low-level docker client
    wrapped_container = MagicMock()
    container._container.get_wrapped_container.return_value = wrapped_container
    
    # exec_run returns (exit_code, (stdout_bytes, stderr_bytes))
    wrapped_container.exec_run.return_value = (1, (b"standard output", b"error output"))
    
    result = await container.execute("some command")
    
    # Verify demux usage
    wrapped_container.exec_run.assert_called_with(["some", "command"], demux=True)
    
    assert result.stdout == "standard output"
    assert result.stderr == "error output"
    assert result.exit_code == 1
    assert result.success is False

@pytest.mark.asyncio
async def test_container_pool_real_init_prewarms():
    """Test ContainerPool in real mode pre-warms containers."""
    from cyberred.tools.container_pool import ContainerPool
    from unittest.mock import patch, MagicMock, AsyncMock
    
    # Mock RealContainer
    with patch("cyberred.tools.container_pool.RealContainer") as mock_rc_cls:
        mock_container = MagicMock()
        mock_container.start = AsyncMock()
        mock_rc_cls.return_value = mock_container
        
        # Act
        pool = ContainerPool(mode="real", size=3)
        await pool.initialize()
        
        # Assert
        assert mock_rc_cls.call_count == 3
        assert mock_container.start.call_count == 3
        # Verify containers added to queue
        assert pool._available.qsize() == 3

@pytest.mark.asyncio
async def test_container_pool_real_acquire():
    """Test acquiring a container in real mode."""
    from cyberred.tools.container_pool import ContainerPool, RealContainer
    from unittest.mock import patch, MagicMock, AsyncMock
    
    with patch("cyberred.tools.container_pool.RealContainer") as mock_rc_cls:
        mock_container = MagicMock()
        mock_container.start = AsyncMock()
        mock_container.is_healthy.return_value = True
        mock_rc_cls.return_value = mock_container
        
        # Initialize pool
        pool = ContainerPool(mode="real", size=1)
        await pool.initialize()
        
        # Act
        acquired = await pool.acquire()
        
        # Assert
        assert acquired == mock_container
        assert pool._available.empty()

@pytest.mark.asyncio
async def test_container_pool_real_acquire_timeout():
    """Test acquire raises error on timeout when empty."""
    from cyberred.tools.container_pool import ContainerPool
    from cyberred.core.exceptions import ContainerPoolExhausted
    import asyncio
    
    # Initialize empty pool
    pool = ContainerPool(mode="real", size=0)
    await pool.initialize()
    
    # Act & Assert
    # We expect it to timeout if we don't have available containers
    # Currently acquire doesn't support timeout, so this should just hang indefinitely if we don't wrap it
    # BUT the goal is to implement timeout IN THE POOL logic.
    # So we call pool.acquire(timeout=0.1) and expect it to handle it.
    # However, signature update is needed. For RED phase, we add the test calling it with kwarg.
    # It will fail with TypeError (unexpected kwarg) or TimeoutError (if we wrap in test)
    
    # To properly testing "Implement blocking acquire with timeout", we should pass timeout to acquire()
    # To properly testing "Implement blocking acquire with timeout", we should pass timeout to acquire()
    with pytest.raises(ContainerPoolExhausted): 
        async with pool.acquire(timeout=0.1):
            pass

@pytest.mark.asyncio
async def test_container_pool_real_release():
    """Test releasing container back to pool handling health."""
    from cyberred.tools.container_pool import ContainerPool, RealContainer
    from unittest.mock import patch, MagicMock, AsyncMock
    
    with patch("cyberred.tools.container_pool.RealContainer") as mock_rc_cls:
        # Arrange
        mock_container = MagicMock()
        mock_container.start = AsyncMock()
        mock_container.is_healthy.return_value = True
        mock_rc_cls.return_value = mock_container
        
        pool = ContainerPool(mode="real", size=1)
        await pool.initialize()
        
        # Act
        acquired = await pool.acquire()
        
        # Test 1: Release healthy container
        await pool.release(acquired)
        assert pool._available.qsize() == 1
        
        # Test 2: Release unhealthy container
        acquired_2 = await pool.acquire()
        mock_container.is_healthy.return_value = False
        mock_container.stop = AsyncMock()
        
        await pool.release(acquired_2)
        assert pool._available.qsize() == 0 
        
        mock_container.stop.assert_called()

@pytest.mark.asyncio
async def test_container_pool_pressure():
    """Test pool pressure calculation."""
    from cyberred.tools.container_pool import ContainerPool, MockContainer
    
    # Mock mode
    pool = ContainerPool(mode="mock", size=10)
    # Mock container acquire mock logic: if successful, decreases queue?
    # Wait, mock implementation of _acquire_impl returns NEW MockContainer (line 40).
    # It does NOT use _available queue for Mock mode in current implementation?
    # Checking implementation: 
    # if self._mode == "mock": return MockContainer(...)
    
    # So pressure for mock mode is always 0? Or undefined?
    # Logic should be consistent. If mock mode doesn't track usage, pressure is 0.
    
    # Let's test Real Mode pressure, as that uses the queue.
    # Testing mock isn't as critical as real implementation.
    
    from unittest.mock import patch, MagicMock, AsyncMock
    with patch("cyberred.tools.container_pool.RealContainer") as mock_rc:
        mock_rc.return_value.start = AsyncMock()
        mock_rc.return_value.is_healthy.return_value = True
        
        pool = ContainerPool(mode="real", size=10)
        await pool.initialize()
        
        # Initial pressure: 0.0 (10/10 available)
        assert pool.pressure == 0.0
        
        # Acquire 5
        acquired_list = []
        for _ in range(5):
            acquired_list.append(await pool.acquire())
            
        # Pressure: 0.5 (5/10 available)
        assert pool.pressure == 0.5
        
        # Release 5
        for c in acquired_list:
            await pool.release(c)
            
        assert pool.pressure == 0.0

@pytest.mark.asyncio
async def test_container_pool_shutdown():
    """Test pool shutdown stops all containers."""
    from cyberred.tools.container_pool import ContainerPool
    from unittest.mock import patch, MagicMock, AsyncMock
    
    with patch("cyberred.tools.container_pool.RealContainer") as mock_rc:
        mock_container = MagicMock()
        mock_container.start = AsyncMock()
        mock_container.stop = AsyncMock()
        mock_rc.return_value = mock_container
        
        # Real mode
        pool = ContainerPool(mode="real", size=5)
        await pool.initialize()
        
        assert pool._available.qsize() == 5
        
        # Shutdown
        await pool.shutdown()
        
        # Verify all stopped
        assert mock_container.stop.call_count == 5
        
        # Verify pool empty/unusable?
        # Maybe qsize is 0
        assert pool._available.empty()
        
        # Verify acquire raises error?
        # with pytest.raises(RuntimeError):
        #    await pool.acquire()

@pytest.mark.asyncio
async def test_container_pool_context_manager_lifecycle():
    """Test ContainerPool used as context manager initializes and shutdowns."""
    from cyberred.tools.container_pool import ContainerPool
    from unittest.mock import patch, MagicMock, AsyncMock
    
    with patch("cyberred.tools.container_pool.RealContainer") as mock_rc:
        mock_container = MagicMock()
        mock_container.start = AsyncMock()
        mock_container.stop = AsyncMock()
        mock_rc.return_value = mock_container
        
        async with ContainerPool(mode="real", size=2) as pool:
             assert pool._available.qsize() == 2
             
        # After exit, shutdown called
        assert mock_container.stop.call_count == 2

@pytest.mark.unit
@pytest.mark.asyncio
async def test_real_container_start_image_logic():
    """Test image pull logic in start()."""
    from cyberred.tools.container_pool import RealContainer
    import sys
    
    # Create valid exception type for mocking
    class MockImageNotFound(Exception):
        pass
        
    mock_docker = MagicMock()
    mock_errors = MagicMock()
    mock_errors.ImageNotFound = MockImageNotFound
    mock_errors.APIError = Exception 
    
    # Mock docker module
    with patch.dict(sys.modules, {'docker': mock_docker, 'docker.errors': mock_errors}):
        
        # Scenario 1: Image exists
        container = RealContainer()
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = "image"
        
        # Mock DockerContainer to avoid actual start
        with patch("cyberred.tools.container_pool.DockerContainer") as mock_dc:
             mock_instance = MagicMock()
             mock_dc.return_value = mock_instance
             await container.start()
             mock_client.images.get.assert_called_with(container._image)
             mock_client.images.pull.assert_not_called()
             
        # Scenario 2: Image Missing (ImageNotFound)
        # We need to reset the side effect
        mock_client.images.get.side_effect = MockImageNotFound("Missing")
        with patch("cyberred.tools.container_pool.DockerContainer") as mock_dc:
             mock_instance = MagicMock()
             mock_dc.return_value = mock_instance
             await container.start()
             mock_client.images.pull.assert_called_with(container._image)
             
        # Scenario 3: Exception during check
        mock_client.images.get.side_effect = Exception("Docker down")
        with patch("cyberred.tools.container_pool.DockerContainer") as mock_dc:
             mock_instance = MagicMock()
             mock_dc.return_value = mock_instance
             # Should pass safely
             await container.start()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_real_container_execute_not_started():
    from cyberred.tools.container_pool import RealContainer
    container = RealContainer()
    with pytest.raises(RuntimeError, match="Container not started"):
        await container.execute("ls")

@pytest.mark.unit
async def test_real_container_is_healthy_error():
    from cyberred.tools.container_pool import RealContainer
    container = RealContainer()
    # No container
    assert not container.is_healthy()
    
    # Container exception
    container._container = MagicMock()
    wrapped = MagicMock()
    container._container.get_wrapped_container.return_value = wrapped
    wrapped.reload.side_effect = Exception("Gone")
    assert not container.is_healthy()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_container_pool_release_cleanup_error():
    """Test cleanup error when releasing unhealthy container."""
    from cyberred.tools.container_pool import ContainerPool
    
    pool = ContainerPool(mode="real")
    mock_container = MagicMock()
    mock_container.is_healthy.return_value = False
    mock_container.stop = AsyncMock(side_effect=Exception("Stop failed"))
    
    # Should not raise
    await pool.release(mock_container)

@pytest.mark.unit
def test_mock_container_tool_detection_edge_cases():
    from cyberred.tools.container_pool import MockContainer
    mc = MockContainer()
    assert mc._detect_tool("") is None
    assert mc._detect_tool("   ") is None
    assert mc._detect_tool(None) is None

@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_container_missing_fixture():
    from cyberred.tools.container_pool import MockContainer
    mc = MockContainer()
    # Uses 'ls' which likely has no fixture unless added
    # But let's use a random name
    result = await mc.execute("random_tool_xyz")
    assert "Mock output (fixture not found)" in result.stdout

@pytest.mark.unit
@pytest.mark.asyncio
async def test_container_pool_restart_unhealthy_logic():
    """Test restart logic when acquiring unhealthy container."""
    from cyberred.tools.container_pool import ContainerPool, RealContainer
    
    pool = ContainerPool(mode="real", size=1)
    
    # Mock container
    mock_container = MagicMock(spec=RealContainer)
    mock_container.is_healthy.side_effect = [False, True] # First check false, second true
    mock_container.stop = AsyncMock()
    mock_container.start = AsyncMock()
    
    # Put in queue
    await pool._available.put(mock_container)
    
    # Acquire
    async with pool.acquire() as c:
        assert c is mock_container
        
    # Verify restart called
    mock_container.stop.assert_called_once()
    mock_container.start.assert_called_once()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_container_pool_restart_unhealthy_failure():
    """Test restart failure is swallowed."""
    from cyberred.tools.container_pool import ContainerPool, RealContainer
    
    pool = ContainerPool(mode="real", size=1)
    mock_container = MagicMock(spec=RealContainer)
    mock_container.is_healthy.return_value = False
    mock_container.stop = AsyncMock()
    mock_container.start = AsyncMock(side_effect=Exception("Restart failed"))
    
    await pool._available.put(mock_container)
    
    async with pool.acquire() as c:
        assert c is mock_container
        # Exception swallowed

@pytest.mark.unit
def test_container_pool_zero_size_pressure():
    from cyberred.tools.container_pool import ContainerPool
    pool = ContainerPool(size=0)
    assert pool.pressure == 1.0

@pytest.mark.unit
def test_fixture_loader_cache_hit():
    from cyberred.tools.container_pool import FixtureLoader
    loader = FixtureLoader()
    # Mock cache
    loader._cache["test"] = "content"
    assert loader.load("test") == "content"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_container_stubs():
    from cyberred.tools.container_pool import MockContainer
    mc = MockContainer()
    await mc.start()
    await mc.stop()
    assert mc.is_healthy()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_container_pool_mock_init_shutdown_branches():
    """Ensure mock mode branches are hit."""
    from cyberred.tools.container_pool import ContainerPool
    pool = ContainerPool(mode="mock")
    await pool.initialize()
    await pool.shutdown()
    # Should be no-ops or minimal ops

@pytest.mark.unit
@pytest.mark.asyncio
async def test_shutdown_queue_race():
    """Test shutdown handling QueueEmpty race."""
    from cyberred.tools.container_pool import ContainerPool
    pool = ContainerPool(mode="real")
    # Add item
    await pool._available.put("item")
    
    # Mock get_nowait to raise QueueEmpty even if empty() was false
    # We can't easily mock the method of an instance created inside init without patching properly
    # Or we can just modify the instance
    pool._available.get_nowait = MagicMock(side_effect=asyncio.QueueEmpty)
    
    # Run shutdown
    await pool.shutdown()
    pass # Should not raise

@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_container_execute_no_tool():
    from cyberred.tools.container_pool import MockContainer
    mc = MockContainer()
    result = await mc.execute("")
    assert not result.success
    assert "Could not detect tool" in result.stderr

@pytest.mark.unit
@pytest.mark.asyncio
async def test_container_context_aexit_no_container():
    """Test __aexit__ when no container was acquired."""
    from cyberred.tools.container_pool import ContainerContext, ContainerPool
    pool = ContainerPool()
    ctx = ContainerContext(pool)
    # Manually call aexit (simulating weird state or manual usage)
    await ctx.__aexit__(None, None, None)
    # Should run safely

@pytest.mark.unit
@pytest.mark.asyncio
async def test_container_pool_release_full_mock():
    """Test releasing to a full mock pool."""
    from cyberred.tools.container_pool import ContainerPool, MockContainer
    pool = ContainerPool(mode="mock", size=1)
    c1 = MockContainer()
    c2 = MockContainer()
    
    # Fill pool
    await pool._available.put(c1)
    
    # Release another one (should define behaviour: discard?)
    await pool.release(c2)
    
    # Verify pool size didn't increase beyond limit if implementation prevents it
    assert pool._available.qsize() == 1

@pytest.mark.unit
@pytest.mark.asyncio
async def test_real_container_execute_timeout_coverage():
    """Test timeout handling path in execute() returns ToolResult."""
    from cyberred.tools.container_pool import RealContainer
    import time
    
    container = RealContainer()
    container._container = MagicMock()
    
    # Mock slow execution
    wrapped = MagicMock()
    container._container.get_wrapped_container.return_value = wrapped
    
    # Simulate slow exec
    def slow_exec(*args, **kwargs):
        time.sleep(0.5)
        return (0, (b"output", b""))
    
    wrapped.exec_run.side_effect = slow_exec
    
    # Should return ToolResult with error_type="TIMEOUT", not raise
    result = await container.execute("sleep 1", timeout=0.1)
    
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error_type == "TIMEOUT"
    assert result.exit_code == -1


@pytest.mark.unit
def test_available_count_and_in_use_count():
    """Test the available_count and in_use_count properties."""
    from cyberred.tools.container_pool import ContainerPool
    
    pool = ContainerPool(mode="mock", size=10)
    
    # Initial state
    assert pool.available_count == 0  # Mock mode doesn't prewarm
    assert pool.in_use_count == 10  # All considered "in use" for mock mode metric


@pytest.mark.unit
@pytest.mark.asyncio
async def test_available_count_real_mode():
    """Test available_count for real mode pool."""
    from cyberred.tools.container_pool import ContainerPool
    
    with patch("cyberred.tools.container_pool.RealContainer") as mock_rc:
        mock_container = MagicMock()
        mock_container.start = AsyncMock()
        mock_container.is_healthy.return_value = True
        mock_rc.return_value = mock_container
        
        pool = ContainerPool(mode="real", size=5)
        await pool.initialize()
        
        assert pool.available_count == 5
        assert pool.in_use_count == 0
        
        # Acquire 2
        _ = await pool.acquire()
        _ = await pool.acquire()
        
        assert pool.available_count == 3
        assert pool.in_use_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_real_container_is_healthy_running():
    """Test is_healthy returns True when container is running."""
    from cyberred.tools.container_pool import RealContainer
    
    container = RealContainer()
    container._container = MagicMock()
    
    wrapped = MagicMock()
    container._container.get_wrapped_container.return_value = wrapped
    wrapped.status = "running"
    
    assert container.is_healthy() is True
    wrapped.reload.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio  
async def test_release_unknown_mode_noop():
    """Test release with unknown mode does nothing (fallthrough case)."""
    from cyberred.tools.container_pool import ContainerPool, MockContainer
    
    pool = ContainerPool(mode="mock")
    pool._mode = "unknown"  # Force unknown mode
    
    container = MockContainer()
    
    # Should not raise, just falls through
    await pool.release(container)
    
    # Queue should be unchanged (nothing added)
    assert pool._available.qsize() == 0


# ============================================================================
# Phase 2 Tests: Container Execute Error Handling (Story 4.13)
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_real_container_execute_exception_returns_tool_result():
    """Test RealContainer.execute() wraps exceptions in ToolResult.
    
    Per ERR1: Tool failures are expected behavior, not exceptions.
    Returns ToolResult(success=False, error_type="EXECUTION_EXCEPTION").
    """
    from cyberred.tools.container_pool import RealContainer
    
    container = RealContainer()
    container._container = MagicMock()
    
    wrapped = MagicMock()
    container._container.get_wrapped_container.return_value = wrapped
    wrapped.exec_run.side_effect = Exception("Docker API error")
    
    # Should NOT raise, should return ToolResult
    result = await container.execute("test command")
    
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error_type == "EXECUTION_EXCEPTION"
    assert "Docker API error" in result.stderr


@pytest.mark.unit
@pytest.mark.asyncio
async def test_real_container_execute_timeout_returns_tool_result():
    """Test RealContainer.execute() returns ToolResult on timeout.
    
    Per ERR1: Timeout is expected behavior, returns structured result.
    Returns ToolResult(success=False, error_type="TIMEOUT").
    """
    from cyberred.tools.container_pool import RealContainer
    import time
    
    container = RealContainer()
    container._container = MagicMock()
    
    wrapped = MagicMock()
    container._container.get_wrapped_container.return_value = wrapped
    
    # Simulate slow execution that will timeout
    def slow_exec(*args, **kwargs):
        time.sleep(0.5)
        return (0, (b"output", b""))
    
    wrapped.exec_run.side_effect = slow_exec
    
    # Should NOT raise, should return ToolResult
    result = await container.execute("slow command", timeout=0.1)
    
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error_type == "TIMEOUT"
    assert "timeout" in result.stderr.lower() or "timed out" in result.stderr.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_real_container_execute_container_crashed_returns_tool_result():
    """Test RealContainer.execute() returns ToolResult when container is not running.
    
    Returns ToolResult(success=False, error_type="CONTAINER_CRASHED").
    """
    from cyberred.tools.container_pool import RealContainer
    from docker.errors import NotFound
    
    container = RealContainer()
    container._container = MagicMock()
    
    wrapped = MagicMock()
    container._container.get_wrapped_container.return_value = wrapped
    wrapped.exec_run.side_effect = NotFound("Container not found")
    
    result = await container.execute("test command")
    
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error_type == "CONTAINER_CRASHED"


# ============================================================================
# Phase 4 Tests: Container Replacement on Crash (Story 4.13 AC3)
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_spawn_replacement_called_on_unhealthy_release():
    """Test _spawn_replacement is called when unhealthy container is released.
    
    Per AC3: When container crashes, a replacement container is spawned
    asynchronously to maintain pool size.
    """
    from cyberred.tools.container_pool import ContainerPool, RealContainer
    
    pool = ContainerPool(mode="real", size=1)
    
    # Track _spawn_replacement calls
    spawn_called = []
    original_spawn = pool._spawn_replacement
    
    async def mock_spawn():
        spawn_called.append(True)
        # Don't actually spawn - just track the call
    
    pool._spawn_replacement = mock_spawn
    
    # Create unhealthy mock container
    mock_container = MagicMock(spec=RealContainer)
    mock_container.is_healthy.return_value = False
    mock_container.stop = AsyncMock()
    
    # Release unhealthy container - should trigger spawn
    await pool.release(mock_container)
    
    # Wait for asyncio.create_task to schedule
    await asyncio.sleep(0.1)
    
    # Verify spawn was called
    assert len(spawn_called) == 1, "_spawn_replacement should be called when unhealthy container is released"
    mock_container.stop.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_spawn_replacement_maintains_pool_size():
    """Test pool size is maintained after container crash and replacement.
    
    Per AC3: Replacement container is spawned to maintain pool size.
    """
    from cyberred.tools.container_pool import ContainerPool, RealContainer
    
    with patch("cyberred.tools.container_pool.RealContainer") as mock_rc:
        mock_container = MagicMock()
        mock_container.start = AsyncMock()
        mock_container.stop = AsyncMock()
        mock_container.is_healthy.return_value = True
        mock_rc.return_value = mock_container
        
        pool = ContainerPool(mode="real", size=3)
        await pool.initialize()
        
        initial_size = pool._available.qsize()
        assert initial_size == 3
        
        # Acquire one container
        acquired = await pool.acquire()
        assert pool._available.qsize() == 2
        
        # Make container unhealthy before release
        acquired.is_healthy.return_value = False
        
        # Release unhealthy container
        await pool.release(acquired)
        
        # Wait for async replacement to complete
        await asyncio.sleep(0.1)
        
        # Pool size should be maintained (replacement spawned)
        # The unhealthy container was discarded but replacement added
        assert pool._available.qsize() == 3, "Pool size should be maintained after replacement"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_spawn_replacement_failure_is_logged_not_raised():
    """Test _spawn_replacement failure doesn't crash the system.
    
    Replacement failure should be logged but not propagate exceptions.
    """
    from cyberred.tools.container_pool import ContainerPool, RealContainer
    
    with patch("cyberred.tools.container_pool.RealContainer") as mock_rc:
        # First call for initialization succeeds
        mock_container = MagicMock()
        mock_container.start = AsyncMock()
        mock_container.stop = AsyncMock()
        mock_container.is_healthy.return_value = True
        mock_rc.return_value = mock_container
        
        pool = ContainerPool(mode="real", size=1)
        await pool.initialize()
        
        # Acquire container
        acquired = await pool.acquire()
        acquired.is_healthy.return_value = False
        
        # Make replacement fail
        failing_container = MagicMock()
        failing_container.start = AsyncMock(side_effect=Exception("Docker unavailable"))
        mock_rc.return_value = failing_container
        
        # Release unhealthy container - replacement will fail
        # This should NOT raise
        await pool.release(acquired)
        
        # Wait for async replacement attempt
        await asyncio.sleep(0.1)
        
        # System should still be operational (no exception propagated)
        assert True, "Replacement failure should be handled gracefully"
