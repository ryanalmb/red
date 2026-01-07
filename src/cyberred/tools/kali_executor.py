import asyncio
import structlog
from typing import Optional
from cyberred.core.models import ToolResult
from cyberred.tools.container_pool import ContainerPool
from cyberred.tools.scope import ScopeValidator

log = structlog.get_logger(__name__)

DEFAULT_TIMEOUT_SECONDS = 300

class KaliExecutor:
    """Swarms-native kali_execute() tool implementation."""
    
    def __init__(
        self, 
        pool: ContainerPool, 
        scope_validator: ScopeValidator,
        default_timeout: int = DEFAULT_TIMEOUT_SECONDS
    ):
        self._pool = pool
        self._scope_validator = scope_validator
        self._default_timeout = default_timeout
        
    async def execute(
        self, 
        code: str, 
        timeout: Optional[int] = None
    ) -> ToolResult:
        """Execute code in Kali container.
        
        Per ERR1: Tool execution failures are expected behavior, not exceptions.
        All error paths return ToolResult with success=False and appropriate error_type.
        ScopeViolationError is the only exception that propagates (critical security).
        """
        from cyberred.core.exceptions import ContainerPoolExhausted
        import time
        
        timeout = timeout or self._default_timeout
        start_time = time.perf_counter()
        
        # Scope validation BEFORE container acquisition (fail-closed)
        # ScopeViolationError is ALWAYS raised - security is not "expected failure"
        self._scope_validator.validate(command=code)
        log.debug("scope_validated", command=code[:50])
        
        try:
            async with self._pool.acquire(timeout=timeout) as container:
                try:
                    return await asyncio.wait_for(
                        container.execute(code, timeout=timeout),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    log.warning("kali_execute_timeout", command=code[:50], timeout=timeout)
                    return ToolResult(
                        success=False,
                        stdout="",
                        stderr=f"Execution timed out after {timeout}s",
                        exit_code=-1,
                        duration_ms=duration_ms,
                        error_type="TIMEOUT"
                    )
                except Exception as e:
                    # Per ERR1: Wrap general exceptions, don't propagate
                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    log.warning("kali_execute_exception", command=code[:50], error=str(e))
                    return ToolResult(
                        success=False,
                        stdout="",
                        stderr=str(e),
                        exit_code=-1,
                        duration_ms=duration_ms,
                        error_type="EXECUTION_EXCEPTION"
                    )
        except ContainerPoolExhausted as e:
            # Per ERR1: Pool exhaustion is expected load condition, not exception
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            log.warning("kali_execute_pool_exhausted", command=code[:50], error=str(e))
            return ToolResult(
                success=False,
                stdout="",
                stderr=f"Container pool exhausted: {e}",
                exit_code=-1,
                duration_ms=duration_ms,
                error_type="POOL_EXHAUSTED"
            )

# Module-level singleton
_executor: Optional[KaliExecutor] = None

async def kali_execute(
    code: str,
    timeout: Optional[int] = None,
    executor: Optional[KaliExecutor] = None
) -> ToolResult:
    """Swarms-native kali_execute() tool.
    
    This is the main entry point for agents to execute Kali tools.
    """
    if executor is None:
        if _executor is None:
            raise RuntimeError("KaliExecutor not initialized. Call initialize_executor() first.")
        executor = _executor
    
    return await executor.execute(code, timeout=timeout)

def initialize_executor(
    pool: ContainerPool,
    scope_validator: ScopeValidator,
    default_timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> None:
    """Initialize the module-level executor singleton."""
    global _executor
    _executor = KaliExecutor(pool, scope_validator, default_timeout)
