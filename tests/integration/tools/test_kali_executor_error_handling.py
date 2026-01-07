"""Integration tests for KaliExecutor error handling (Story 4.13).

Tests the full executor->pool->container chain with real Docker containers.
"""
import pytest
import asyncio
from unittest.mock import MagicMock

from cyberred.tools.container_pool import ContainerPool
from cyberred.tools.kali_executor import KaliExecutor


@pytest.mark.integration
@pytest.mark.asyncio
async def test_kali_executor_pool_exhausted_returns_tool_result():
    """Test KaliExecutor wraps pool exhaustion in ToolResult.
    
    Per ERR1: Pool exhaustion should return ToolResult, not raise.
    """
    # Create empty pool
    pool = ContainerPool(mode="real", size=0)
    await pool.initialize()
    
    # Use mock scope validator that always passes
    mock_scope = MagicMock()
    mock_scope.validate = MagicMock(return_value=None)
    
    executor = KaliExecutor(pool=pool, scope_validator=mock_scope)
    
    try:
        # Execute with any command - pool is empty so should fail
        result = await executor.execute("echo test", timeout=1)
        
        assert result.success is False
        assert result.error_type == "POOL_EXHAUSTED"
        assert "exhausted" in result.stderr.lower() or "pool" in result.stderr.lower()
        
    finally:
        await pool.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_kali_executor_timeout_returns_tool_result():
    """Test KaliExecutor timeout returns ToolResult.
    
    Per ERR1: Timeout should return ToolResult, not raise.
    """
    async with ContainerPool(mode="real", size=1) as pool:
        # Use mock scope validator that always passes
        mock_scope = MagicMock()
        mock_scope.validate = MagicMock(return_value=None)
        
        executor = KaliExecutor(pool=pool, scope_validator=mock_scope)
        
        # Execute command that will timeout (sleep 5s with 1s timeout)
        result = await executor.execute("sleep 5", timeout=1)
        
        assert result.success is False
        assert result.error_type == "TIMEOUT"
        assert result.exit_code == -1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_kali_executor_success_returns_tool_result():
    """Test KaliExecutor success returns ToolResult with no error_type."""
    async with ContainerPool(mode="real", size=1) as pool:
        # Use mock scope validator that always passes
        mock_scope = MagicMock()
        mock_scope.validate = MagicMock(return_value=None)
        
        executor = KaliExecutor(pool=pool, scope_validator=mock_scope)
        
        # Execute successful command
        result = await executor.execute("echo 'hello world'")
        
        assert result.success is True
        assert result.error_type is None
        assert result.exit_code == 0
        assert "hello world" in result.stdout


@pytest.mark.integration
@pytest.mark.asyncio
async def test_kali_executor_non_zero_exit_returns_tool_result():
    """Test KaliExecutor non-zero exit returns ToolResult with NON_ZERO_EXIT."""
    async with ContainerPool(mode="real", size=1) as pool:
        # Use mock scope validator
        mock_scope = MagicMock()
        mock_scope.validate = MagicMock(return_value=None)
        
        executor = KaliExecutor(pool=pool, scope_validator=mock_scope)
        
        # Execute command that will fail
        result = await executor.execute("ls /nonexistent_path_that_does_not_exist")
        
        assert result.success is False
        assert result.exit_code != 0
        assert result.error_type == "NON_ZERO_EXIT"
