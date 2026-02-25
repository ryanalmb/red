import asyncio
import os
import statistics
import threading
from collections import defaultdict, deque
from typing import Optional

import structlog

from cyberred.core.models import ToolResult
from cyberred.tools.container_pool import ContainerPool
from cyberred.tools.scope import ScopeValidator

log = structlog.get_logger(__name__)

DEFAULT_TIMEOUT_SECONDS = 900


class AdaptiveCommandTimeoutPolicy:
    """Adaptive timeout policy based on command behavior classes."""

    def __init__(
        self,
        base_timeout_s: int,
        min_timeout_s: int,
        max_timeout_s: int,
        sample_size: int = 200,
    ) -> None:
        self._base_timeout_s = max(1, int(base_timeout_s))
        self._min_timeout_s = max(1, int(min_timeout_s))
        self._max_timeout_s = max(self._min_timeout_s, int(max_timeout_s))
        self._sample_size = max(10, int(sample_size))
        self._lock = threading.Lock()
        self._durations_s: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self._sample_size)
        )
        self._timeout_flags: dict[str, deque[int]] = defaultdict(
            lambda: deque(maxlen=self._sample_size)
        )

    def classify(self, command: str, segment_count: int) -> str:
        """Classify command into structure-driven execution behavior."""
        token_count = len(command.split())
        has_shell_ops = any(op in command for op in ("|", "&&", "||", ";", "$(", "`"))
        if segment_count > 1 or has_shell_ops:
            return "pipeline"
        if token_count >= 22 or len(command) >= 220:
            return "complex"
        if any(flag in command for flag in (" --help", " --version", " -h ", " -V ")):
            return "short"
        return "standard"

    def resolve_timeout(self, command: str, segment_count: int) -> tuple[int, str]:
        """Resolve timeout budget for a command and return (timeout, class)."""
        behavior = self.classify(command, segment_count)
        multiplier = {
            "short": 0.5,
            "standard": 1.0,
            "complex": 1.7,
            "pipeline": 1.4,
        }.get(behavior, 1.0)
        baseline = max(self._min_timeout_s, int(self._base_timeout_s * multiplier))

        with self._lock:
            durations = list(self._durations_s.get(behavior, ()))
            timeout_flags = list(self._timeout_flags.get(behavior, ()))

        # Uplift from observed runtime distribution.
        if len(durations) >= 5:
            p90_s = statistics.quantiles(durations, n=10)[8]
            baseline = max(baseline, int(p90_s * 1.35))

        if timeout_flags:
            timeout_rate = sum(timeout_flags) / len(timeout_flags)
            if timeout_rate >= 0.35:
                baseline = int(baseline * 1.25)

        resolved = max(self._min_timeout_s, min(self._max_timeout_s, baseline))
        return resolved, behavior

    def record(self, behavior: str, duration_ms: int, timed_out: bool) -> None:
        """Record command outcome for adaptive tuning."""
        duration_s = max(0.001, duration_ms / 1000.0)
        with self._lock:
            self._durations_s[behavior].append(duration_s)
            self._timeout_flags[behavior].append(1 if timed_out else 0)


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
        min_timeout_s = max(10, int(os.getenv("CYBERRED_KALI_TIMEOUT_MIN_S", "300")))
        max_timeout_s = max(min_timeout_s, int(os.getenv("CYBERRED_KALI_TIMEOUT_MAX_S", "3600")))
        self._timeout_policy = AdaptiveCommandTimeoutPolicy(
            base_timeout_s=self._default_timeout,
            min_timeout_s=min_timeout_s,
            max_timeout_s=max_timeout_s,
        )
        
    async def execute(
        self, 
        code: str, 
        timeout: Optional[float] = None
    ) -> ToolResult:
        """Execute code in Kali container.
        
        Per ERR1: Tool execution failures are expected behavior, not exceptions.
        All error paths return ToolResult with success=False and appropriate error_type.
        ScopeViolationError is the only exception that propagates (critical security).
        """
        from cyberred.core.exceptions import ContainerPoolExhausted
        import time

        start_time = time.perf_counter()
        
        # Scope validation BEFORE container acquisition (fail-closed)
        # ScopeViolationError is ALWAYS raised for actual out-of-scope targets.
        # Commands with no detectable network target (local-only) are allowed.
        from cyberred.core.exceptions import ScopeViolationError
        try:
            self._scope_validator.validate(command=code)
        except ScopeViolationError as e:
            if e.scope_rule == "missing_target":
                # No network target found — local-only command, allow it
                log.debug("scope_no_target_allow", command=code[:50])
            else:
                raise
        log.debug("scope_validated", command=code[:50])
        
        # Detect multi-segment commands (pipes/chains) for pipeline execution
        segments = self._scope_validator.split_segments(code)
        is_pipeline = len(segments) > 1
        if timeout is not None and timeout > 0:
            effective_timeout = max(0.05, float(timeout))
            behavior = "explicit"
        else:
            effective_timeout, behavior = self._timeout_policy.resolve_timeout(
                code,
                segment_count=len(segments),
            )

        acquire_timeout = min(float(effective_timeout), 120.0)

        try:
            async with self._pool.acquire(timeout=acquire_timeout) as container:
                try:
                    if is_pipeline:
                        execution_coro = container.execute_pipeline(
                            [s.command for s in segments],
                            timeout=effective_timeout,
                        )
                    else:
                        execution_coro = container.execute(code, timeout=effective_timeout)

                    if behavior == "explicit":
                        result = await asyncio.wait_for(
                            execution_coro,
                            timeout=effective_timeout,
                        )
                    else:
                        result = await execution_coro

                    self._timeout_policy.record(
                        behavior=behavior,
                        duration_ms=result.duration_ms,
                        timed_out=result.error_type == "TIMEOUT",
                    )
                    if result.error_type == "TIMEOUT":
                        log.warning(
                            "kali_execute_timeout",
                            command=code[:50],
                            timeout=effective_timeout,
                            behavior=behavior,
                        )
                    return result
                except asyncio.TimeoutError:
                    # Safety net: container adapters should return ToolResult on timeout.
                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    self._timeout_policy.record(
                        behavior=behavior,
                        duration_ms=duration_ms,
                        timed_out=True,
                    )
                    log.warning(
                        "kali_execute_timeout",
                        command=code[:50],
                        timeout=effective_timeout,
                        behavior=behavior,
                    )
                    return ToolResult(
                        success=False,
                        stdout="",
                        stderr=f"Execution timed out after {effective_timeout}s",
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
    timeout: Optional[float] = None,
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
