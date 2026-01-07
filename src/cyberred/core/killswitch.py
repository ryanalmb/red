"""Tri-path Kill Switch (Safety-Critical).

This module implements the safety-critical kill switch for Cyber-Red v2.0.
The kill switch halts ALL operations in <1s using three parallel paths:

1. Redis pub/sub: Publishes to `control:kill` channel
2. SIGTERM cascade: Sends SIGTERM to process group
3. Docker API: Calls container.stop() on engagement containers

Architecture Requirements (FR17, FR18, NFR2):
- Kill switch must halt all operations in <1s under 10K agent load
- Must work even if Redis is offline (tri-path redundancy)
- Atomic "engagement frozen" flag prevents new operations

Usage:
    from cyberred.core.killswitch import KillSwitch

    ks = KillSwitch(
        redis_client=redis_client,  # Optional
        docker_client=docker_client,  # Optional
        engagement_id="ministry-2025"
    )

    # Trigger kill switch
    result = await ks.trigger(reason="Operator emergency stop")

    # Check if frozen (for agents)
    ks.check_frozen()  # Raises KillSwitchTriggered if frozen
"""

import asyncio
import functools
import json
import os
import signal
import threading
import time
from typing import Any, Optional

import structlog

from cyberred.core.exceptions import KillSwitchTriggered
from cyberred.core.time import now

# Timing budgets (architecture lines 294-304)
REDIS_TIMEOUT_S = 0.5
SIGTERM_TIMEOUT_S = 0.3
DOCKER_TIMEOUT_S = 0.6


class KillSwitch:
    """Tri-path kill switch for emergency halt of all operations.

    The kill switch provides three redundant paths:
    - Path 1: Redis pub/sub `control:kill`
    - Path 2: SIGTERM cascade via process group
    - Path 3: Docker API container.stop()

    All paths execute in parallel with individual timeouts to guarantee
    <1s completion even if some paths fail.

    Attributes:
        is_frozen: Whether the engagement is frozen (no new work allowed).
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        docker_client: Optional[Any] = None,
        engagement_id: Optional[str] = None,
    ) -> None:
        """Initialize KillSwitch.

        Args:
            redis_client: Async Redis client (optional - kill switch works without).
            docker_client: Docker client (optional - kill switch works without).
            engagement_id: Engagement identifier for container filtering.
        """
        self._redis_client = redis_client
        self._docker_client = docker_client
        self._engagement_id = engagement_id or "unknown"
        self._frozen = threading.Event()
        self._trigger_time: Optional[float] = None
        self._triggered_by: str = "unknown"
        self._log = structlog.get_logger().bind(
            component="killswitch",
            engagement_id=self._engagement_id,
        )

    @property
    def is_frozen(self) -> bool:
        """Return whether the engagement is frozen."""
        return self._frozen.is_set()

    def reset(self) -> None:
        """Reset the frozen flag (testing only).

        Warning:
            This method should ONLY be used in tests.
            In production, a frozen engagement should stay frozen.
        """
        self._frozen.clear()
        self._trigger_time = None

    async def trigger(
        self,
        reason: str = "Operator initiated",
        triggered_by: str = "operator",
    ) -> dict[str, Any]:
        """Trigger the kill switch to halt all operations.

        This method:
        1. FIRST sets the atomic frozen flag
        2. THEN executes all three paths in parallel
        3. Logs to audit trail

        Args:
            reason: Why the kill switch was triggered.
            triggered_by: Who triggered the kill switch.

        Returns:
            dict with keys: success, duration_ms, paths
        """
        # FIRST: Set atomic frozen flag (BEFORE any path executes)
        self._frozen.set()
        self._triggered_by = triggered_by
        start = time.perf_counter()
        self._trigger_time = start

        self._log.warning(
            "kill_switch_triggered",
            reason=reason,
            triggered_by=triggered_by,
        )

        # SECOND: Execute all paths in parallel with individual timeouts
        path_results: dict[str, Any] = {
            "redis": False,
            "sigterm": False,
            "docker": False,
        }

        # Note: asyncio.gather with return_exceptions=True captures exceptions
        # from the awaited coroutines, so a try/except block here is redundant
        # for handling path failures.
        results = await asyncio.gather(
            asyncio.wait_for(
                self._path_redis(reason, triggered_by),
                timeout=REDIS_TIMEOUT_S,
            ),
            asyncio.wait_for(
                self._path_sigterm(),
                timeout=SIGTERM_TIMEOUT_S,
            ),
            asyncio.wait_for(
                self._path_docker(),
                timeout=DOCKER_TIMEOUT_S,
            ),
            return_exceptions=True,
        )

        # Process results
        for i, (name, result) in enumerate(
            zip(["redis", "sigterm", "docker"], results)
        ):
            if isinstance(result, Exception):
                path_results[name] = False
                self._log.warning(
                    f"kill_switch_path_failed",
                    path=name,
                    error=str(result),
                )
            else:
                path_results[name] = result

        # Calculate duration
        duration_ms = (time.perf_counter() - start) * 1000

        # Log completion
        self._log.info(
            "kill_switch_completed",
            duration_ms=round(duration_ms, 2),
            paths=path_results,
            reason=reason,
            triggered_by=triggered_by,
        )

        return {
            "success": True,  # Flag is set = success (paths are best-effort)
            "duration_ms": duration_ms,
            "paths": path_results,
        }

    async def _path_redis(
        self,
        reason: str,
        triggered_by: str = "operator",
    ) -> bool:
        """Path 1: Publish kill command to Redis pub/sub.

        Args:
            reason: Why the kill switch was triggered.
            triggered_by: Who triggered the kill switch.

        Returns:
            True if successful, False if failed (never raises).
        """
        if self._redis_client is None:
            self._log.warning("kill_switch_redis_skipped", reason="no client")
            return False

        try:
            # Use trusted NTP time
            message = json.dumps({
                "command": "kill",
                "issued_by": triggered_by,
                "timestamp": now().isoformat(),
                "reason": reason,
                "engagement_id": self._engagement_id,
            })

            await self._redis_client.publish("control:kill", message)
            self._log.debug("kill_switch_redis_published")
            return True

        except Exception as e:
            self._log.warning("kill_switch_redis_failed", error=str(e))
            return False

    async def _path_sigterm(self) -> bool:
        """Path 2: Send SIGTERM cascade to process group.

        Returns:
            True if successful, False if failed (never raises).
        """
        try:
            # Get current process group
            pgid = os.getpgid(os.getpid())

            # Send SIGTERM to entire process group
            os.killpg(pgid, signal.SIGTERM)
            self._log.debug("kill_switch_sigterm_sent", pgid=pgid)
            return True

        except ProcessLookupError:
            # Process already dead - that's still a success
            self._log.debug("kill_switch_sigterm_process_gone")
            return True

        except PermissionError as e:
            self._log.warning("kill_switch_sigterm_permission_denied", error=str(e))
            return False

        except Exception as e:
            self._log.warning("kill_switch_sigterm_failed", error=str(e))
            return False

    async def _path_docker(self) -> bool:
        """Path 3: Stop engagement containers via Docker API.

        Excutes blocking Docker logic in a separate thread to prevent
        blocking the asyncio event loop.

        Returns:
            True if successful, False if failed (never raises).
        """
        if self._docker_client is None:
            self._log.warning("kill_switch_docker_skipped", reason="no client")
            return False

        # Run synchronous blocking docker calls in a thread pool
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_docker_stop)

    def _sync_docker_stop(self) -> bool:
        """Synchronous implementation of Docker stop logic (blocking)."""
        try:
            # List containers with engagement label
            containers = self._docker_client.containers.list(
                filters={"label": f"cyberred.engagement_id={self._engagement_id}"}
            )

            if not containers:
                self._log.debug("kill_switch_docker_no_containers")
                return True

            # Stop each container with timeout
            for container in containers:
                try:
                    container.stop(timeout=0.5)
                    self._log.debug(
                        "kill_switch_container_stopped",
                        container_id=container.id[:12],
                    )
                except Exception as stop_error:
                    # Try force kill if stop fails
                    try:
                        container.kill()
                        self._log.debug(
                            "kill_switch_container_killed",
                            container_id=container.id[:12],
                        )
                    except Exception as kill_error:
                        # Container may already be stopped
                        if "NotFound" in str(type(kill_error).__name__):
                            self._log.debug(
                                "kill_switch_container_already_stopped",
                                container_id=container.id[:12],
                            )
                        else:
                            self._log.warning(
                                "kill_switch_container_kill_failed",
                                container_id=container.id[:12],
                                error=str(kill_error),
                            )

            return True

        except Exception as e:
            self._log.warning("kill_switch_docker_failed", error=str(e))
            return False

    def check_frozen(self, triggered_by: str = "system") -> None:
        """Check if engagement is frozen and raise if so.

        This method should be called by agents before each action
        to respect the frozen state.

        Args:
            triggered_by: Who is checking (for exception context).

        Raises:
            KillSwitchTriggered: If engagement is frozen.
        """
        if self._frozen.is_set():
            raise KillSwitchTriggered(
                engagement_id=self._engagement_id,
                triggered_by=triggered_by,
                reason="Engagement frozen",
            )
