import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from cyberred.core.models import ToolResult
from cyberred.tools.container_pool import ContainerPool
from cyberred.tools.scope import ScopeValidator
from cyberred.core.exceptions import ScopeViolationError
from cyberred.tools.kali_executor import KaliExecutor

@pytest.fixture
def mock_container():
    container = AsyncMock()
    container.execute.return_value = ToolResult(
        success=True, stdout="hello", stderr="", exit_code=0, duration_ms=10
    )
    return container

@pytest.fixture
def mock_pool(mock_container):
    pool = MagicMock(spec=ContainerPool)
    # Async context manager mock for acquire()
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = mock_container
    acquire_ctx.__aexit__.return_value = None
    pool.acquire.return_value = acquire_ctx
    return pool

@pytest.fixture
def mock_scope_validator():
    return MagicMock(spec=ScopeValidator)

@pytest.mark.unit
def test_kali_executor_init(mock_pool, mock_scope_validator):
    if KaliExecutor is None:
        pytest.fail("KaliExecutor class not found")
        
    executor = KaliExecutor(pool=mock_pool, scope_validator=mock_scope_validator)
    # Check private attributes set (convention)
    assert executor._pool == mock_pool
    assert executor._scope_validator == mock_scope_validator

@pytest.mark.asyncio
async def test_execute_success(mock_pool, mock_scope_validator, mock_container):
    executor = KaliExecutor(pool=mock_pool, scope_validator=mock_scope_validator)
    
    result = await executor.execute("echo hello")
    
    assert result.success is True
    assert result.stdout == "hello"
    mock_scope_validator.validate.assert_called_with(command="echo hello") # Task 4
    mock_pool.acquire.assert_called_once()
    mock_container.execute.assert_called_with("echo hello", timeout=300)

@pytest.mark.asyncio
async def test_execute_timeout(mock_pool, mock_scope_validator, mock_container):
    # Set small default time out or pass strictly
    executor = KaliExecutor(pool=mock_pool, scope_validator=mock_scope_validator)
    
    # Mock container execution to hang longer than specified timeout
    async def side_effect(*args, **kwargs):
        await asyncio.sleep(0.2)
        return ToolResult(success=True, stdout="too late", stderr="", exit_code=0, duration_ms=200)
    
    mock_container.execute.side_effect = side_effect
    
    # Execute with very short timeout
    result = await executor.execute("sleep 10", timeout=0.1)
    
    assert result.success is False
    assert "timed out" in result.stderr

@pytest.mark.asyncio
async def test_execute_scope_violation(mock_pool, mock_scope_validator):
    executor = KaliExecutor(pool=mock_pool, scope_validator=mock_scope_validator)
    
    mock_scope_validator.validate.side_effect = ScopeViolationError("Out of scope", "nmap 8.8.8.8", "deny_all")
    
    with pytest.raises(ScopeViolationError):
        await executor.execute("nmap 8.8.8.8")
        
    mock_scope_validator.validate.assert_called_with(command="nmap 8.8.8.8")
    mock_pool.acquire.assert_not_called()

@pytest.mark.asyncio
async def test_execute_exception_returns_tool_result(mock_pool, mock_scope_validator, mock_container):
    """Test that exceptions during execute are wrapped in ToolResult per ERR1."""
    executor = KaliExecutor(pool=mock_pool, scope_validator=mock_scope_validator)
    
    mock_container.execute.side_effect = ValueError("Boom")
    
    # Per ERR1: Should NOT raise, should return ToolResult
    result = await executor.execute("echo crash")
    
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error_type == "EXECUTION_EXCEPTION"
    assert "Boom" in result.stderr
    
    # Verify context manager still exits properly
    mock_pool.acquire.assert_called_once()
    mock_pool.acquire.return_value.__aexit__.assert_called_once()

@pytest.mark.asyncio
async def test_kali_execute_standalone(mock_pool, mock_scope_validator):
    from cyberred.tools.kali_executor import kali_execute, initialize_executor 
    import cyberred.tools.kali_executor as kali_exec_module
    
    # Reset global
    kali_exec_module._executor = None
    
    # Pre-init failure
    with pytest.raises(RuntimeError, match="KaliExecutor not initialized"):
        await kali_execute("fail")
        
    # Init
    initialize_executor(mock_pool, mock_scope_validator)
    assert kali_exec_module._executor is not None
    
    # Mock container execution
    mock_container = AsyncMock()
    mock_container.execute.return_value = ToolResult(True, "standalone", "", 0, 0)
    
    # Setup mock pool result
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_container
    mock_ctx.__aexit__.return_value = None
    mock_pool.acquire.return_value = mock_ctx
    
    # Execute
    result = await kali_execute("echo standalone")
    assert result.stdout == "standalone"

@pytest.mark.asyncio
async def test_kali_execute_with_explicit_executor(mock_pool, mock_scope_validator):
    from cyberred.tools.kali_executor import kali_execute, KaliExecutor
    
    # Create explicit executor
    explicit_executor = KaliExecutor(mock_pool, mock_scope_validator)
    
    # Mock container execution
    mock_container = AsyncMock()
    mock_container.execute.return_value = ToolResult(True, "explicit", "", 0, 0)
    
    # Setup mock pool result
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_container
    mock_ctx.__aexit__.return_value = None
    mock_pool.acquire.return_value = mock_ctx
    
    result = await kali_execute("echo explicit", executor=explicit_executor)
    assert result.stdout == "explicit"
    # Verify mock_pool was called (by explicit_executor)
    mock_pool.acquire.assert_called()


# ============================================================================
# Phase 3 Tests: KaliExecutor Error Handling (Story 4.13)
# ============================================================================

@pytest.mark.asyncio
async def test_execute_timeout_has_error_type(mock_pool, mock_scope_validator, mock_container):
    """Test KaliExecutor.execute() timeout result has error_type='TIMEOUT'.
    
    Per ERR1: All error results should have categorization via error_type.
    """
    executor = KaliExecutor(pool=mock_pool, scope_validator=mock_scope_validator)
    
    # Mock container execution to hang longer than specified timeout
    async def side_effect(*args, **kwargs):
        await asyncio.sleep(0.2)
        return ToolResult(success=True, stdout="too late", stderr="", exit_code=0, duration_ms=200)
    
    mock_container.execute.side_effect = side_effect
    
    # Execute with very short timeout
    result = await executor.execute("sleep 10", timeout=0.1)
    
    assert result.success is False
    assert result.error_type == "TIMEOUT"
    assert "timed out" in result.stderr


@pytest.mark.asyncio
async def test_execute_container_pool_exhausted_returns_tool_result(mock_scope_validator):
    """Test ContainerPoolExhausted returns ToolResult, not exception.
    
    Per ERR1: Tool failures should return structured results, not raise.
    """
    from cyberred.tools.kali_executor import KaliExecutor
    from cyberred.core.exceptions import ContainerPoolExhausted
    
    # Create mock pool that raises ContainerPoolExhausted
    mock_pool = MagicMock(spec=ContainerPool)
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.side_effect = ContainerPoolExhausted("Pool empty")
    mock_pool.acquire.return_value = acquire_ctx
    
    executor = KaliExecutor(pool=mock_pool, scope_validator=mock_scope_validator)
    
    # Should NOT raise, should return ToolResult
    result = await executor.execute("nmap target")
    
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error_type == "POOL_EXHAUSTED"
    assert "Pool" in result.stderr or "exhausted" in result.stderr.lower()


@pytest.mark.asyncio
async def test_execute_general_exception_returns_tool_result(mock_pool, mock_scope_validator, mock_container):
    """Test general exceptions in execute are wrapped in ToolResult.
    
    Per ERR1: No exceptions should propagate to agents.
    """
    executor = KaliExecutor(pool=mock_pool, scope_validator=mock_scope_validator)
    
    mock_container.execute.side_effect = RuntimeError("Unexpected error")
    
    # Should NOT raise, should return ToolResult
    result = await executor.execute("echo crash")
    
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error_type == "EXECUTION_EXCEPTION"
    assert "Unexpected error" in result.stderr
