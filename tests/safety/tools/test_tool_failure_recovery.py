"""Safety Tests for Tool Execution Error Handling (Story 4.13).

These tests verify that agents can continue operating despite tool failures.
Per ERR1: Tool execution failures should return structured results, not exceptions.

All tests marked with @pytest.mark.safety for test infrastructure tagging.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

from cyberred.core.models import ToolResult
from cyberred.tools.container_pool import ContainerPool
from cyberred.tools.kali_executor import KaliExecutor
from cyberred.tools.scope import ScopeValidator


@pytest.fixture
def mock_scope_validator():
    """Create a mock scope validator that always passes."""
    validator = MagicMock(spec=ScopeValidator)
    return validator


@pytest.fixture
def mock_pool():
    """Create a mock container pool."""
    pool = MagicMock(spec=ContainerPool)
    return pool


def _create_mock_container(result: ToolResult) -> AsyncMock:
    """Helper to create mock container with specified result."""
    container = AsyncMock()
    container.execute.return_value = result
    return container


# ============================================================================
# Safety Tests: Agent Continuation After Failures (AC5)
# ============================================================================

@pytest.mark.safety
@pytest.mark.asyncio
async def test_agent_continues_after_timeout(mock_pool, mock_scope_validator):
    """Verify agent receives ToolResult on timeout, not exception.
    
    Per ERR1 & AC5: Agent must be able to continue after timeout.
    """
    executor = KaliExecutor(pool=mock_pool, scope_validator=mock_scope_validator)
    
    # Mock container that times out
    async def timeout_side_effect(*args, **kwargs):
        await asyncio.sleep(1)
        return ToolResult(success=True, stdout="", stderr="", exit_code=0, duration_ms=0)
    
    mock_container = AsyncMock()
    mock_container.execute.side_effect = timeout_side_effect
    
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = mock_container
    acquire_ctx.__aexit__.return_value = None
    mock_pool.acquire.return_value = acquire_ctx
    
    # Execute with short timeout - should NOT raise
    result = await executor.execute("nmap -sV target", timeout=0.05)
    
    # Verify structured result returned
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error_type == "TIMEOUT"
    
    # Agent can continue with another command
    mock_container.execute.side_effect = None
    mock_container.execute.return_value = ToolResult(
        success=True, stdout="second command", stderr="", exit_code=0, duration_ms=100
    )
    
    result2 = await executor.execute("echo hello")
    assert result2.success is True
    assert result2.stdout == "second command"


@pytest.mark.safety
@pytest.mark.asyncio
async def test_agent_continues_after_crash(mock_pool, mock_scope_validator):
    """Verify agent receives ToolResult on container crash, not exception.
    
    Per ERR1 & AC5: Agent must be able to continue after crash.
    """
    executor = KaliExecutor(pool=mock_pool, scope_validator=mock_scope_validator)
    
    # Mock container that crashes
    mock_container = AsyncMock()
    mock_container.execute.side_effect = RuntimeError("Container died")
    
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = mock_container
    acquire_ctx.__aexit__.return_value = None
    mock_pool.acquire.return_value = acquire_ctx
    
    # Execute - should NOT raise
    result = await executor.execute("nmap target")
    
    # Verify structured result returned
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error_type == "EXECUTION_EXCEPTION"
    
    # Agent can continue with another command
    mock_container.execute.side_effect = None
    mock_container.execute.return_value = ToolResult(
        success=True, stdout="recovered", stderr="", exit_code=0, duration_ms=50
    )
    
    result2 = await executor.execute("echo recovered")
    assert result2.success is True


@pytest.mark.safety
@pytest.mark.asyncio
async def test_agent_continues_after_non_zero_exit(mock_pool, mock_scope_validator):
    """Verify agent receives ToolResult on non-zero exit, not exception.
    
    Per ERR1 & AC5: Non-zero exit is expected behavior.
    """
    executor = KaliExecutor(pool=mock_pool, scope_validator=mock_scope_validator)
    
    # Mock container with non-zero exit
    mock_container = AsyncMock()
    mock_container.execute.return_value = ToolResult(
        success=False,
        stdout="",
        stderr="Command failed",
        exit_code=1,
        duration_ms=100,
        error_type="NON_ZERO_EXIT"
    )
    
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = mock_container
    acquire_ctx.__aexit__.return_value = None
    mock_pool.acquire.return_value = acquire_ctx
    
    # Execute - should NOT raise
    result = await executor.execute("false")
    
    # Verify structured result returned
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.exit_code == 1
    
    # Agent can continue
    mock_container.execute.return_value = ToolResult(
        success=True, stdout="next", stderr="", exit_code=0, duration_ms=50
    )
    result2 = await executor.execute("echo next")
    assert result2.success is True


@pytest.mark.safety
@pytest.mark.asyncio
async def test_agent_continues_after_pool_exhausted(mock_scope_validator):
    """Verify agent receives ToolResult on pool exhaustion, not exception.
    
    Per ERR1 & AC5: Pool exhaustion is expected load condition.
    """
    from cyberred.core.exceptions import ContainerPoolExhausted
    
    mock_pool = MagicMock(spec=ContainerPool)
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.side_effect = ContainerPoolExhausted("All containers busy")
    mock_pool.acquire.return_value = acquire_ctx
    
    executor = KaliExecutor(pool=mock_pool, scope_validator=mock_scope_validator)
    
    # Execute - should NOT raise
    result = await executor.execute("nmap target")
    
    # Verify structured result returned
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error_type == "POOL_EXHAUSTED"
    
    # Agent can retry when pool frees up
    mock_container = AsyncMock()
    mock_container.execute.return_value = ToolResult(
        success=True, stdout="done", stderr="", exit_code=0, duration_ms=50
    )
    acquire_ctx.__aenter__.side_effect = None
    acquire_ctx.__aenter__.return_value = mock_container
    
    result2 = await executor.execute("nmap target")
    assert result2.success is True


@pytest.mark.safety
@pytest.mark.asyncio
async def test_no_exception_propagation_all_error_types(mock_pool, mock_scope_validator):
    """Verify NO exceptions escape kali_execute for any error type.
    
    Per ERR1 & AC5: This is the critical safety guarantee.
    """
    from cyberred.tools.kali_executor import kali_execute, initialize_executor
    import cyberred.tools.kali_executor as kali_module
    
    # Reset singleton
    kali_module._executor = None
    initialize_executor(mock_pool, mock_scope_validator)
    
    error_scenarios = [
        # (side_effect, expected_error_type)
        (asyncio.TimeoutError(), "TIMEOUT"),
        (RuntimeError("Crash"), "EXECUTION_EXCEPTION"),
        (ValueError("Bad value"), "EXECUTION_EXCEPTION"),
        (OSError("OS error"), "EXECUTION_EXCEPTION"),
    ]
    
    for side_effect, expected_type in error_scenarios:
        mock_container = AsyncMock()
        mock_container.execute.side_effect = side_effect
        
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__.return_value = mock_container
        acquire_ctx.__aexit__.return_value = None
        mock_pool.acquire.return_value = acquire_ctx
        
        # This MUST NOT raise - it's the critical safety property
        result = await kali_execute("test command")
        
        assert isinstance(result, ToolResult), f"Should return ToolResult for {type(side_effect)}"
        assert result.success is False, f"Should indicate failure for {type(side_effect)}"
        assert result.error_type is not None, f"Should have error_type for {type(side_effect)}"
