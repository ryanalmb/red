"""Pre-flight protocol for drop box validation before operations.

Story 12.9: Pre-Flight Protocol
Per FR26: System can execute deterministic pre-flight protocol
    (PING→EXEC_TEST→STREAM_TEST→NET_ENUM→READY)

Sequence:
- PING: Measure RTT latency to drop box
- EXEC_TEST: Send benign command, validate response
- STREAM_TEST: Bidirectional streaming integrity check
- NET_ENUM: Discover local network interfaces on drop box
- READY: Final state when all steps pass

Timeout: 10s per step (per epics-stories.md Technical Notes)
Failure Policy: Fail on any step → drop box marked NOT READY (fail-fast)
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from cyberred.c2.server import C2Server
    from cyberred.core.events import EventBus

log = structlog.get_logger()


# =============================================================================
# Enums (Task 1.1, 1.4)
# =============================================================================


class PreFlightStep(Enum):
    """Pre-flight validation steps executed in deterministic order.

    Per FR26: PING→EXEC_TEST→STREAM_TEST→NET_ENUM→READY
    READY is the final state, not an executable step.
    """

    PING = "ping"
    EXEC_TEST = "exec_test"
    STREAM_TEST = "stream_test"
    NET_ENUM = "net_enum"
    READY = "ready"


class PreFlightStatus(Enum):
    """Overall pre-flight validation status.

    Attributes:
        READY: All steps passed — drop box is operational.
        NOT_READY: One or more steps failed or timed out.
        IN_PROGRESS: Pre-flight sequence is currently running.
        NOT_STARTED: Pre-flight has not been initiated.
    """

    READY = "ready"
    NOT_READY = "not_ready"
    IN_PROGRESS = "in_progress"
    NOT_STARTED = "not_started"


class StepStatus(Enum):
    """Individual step execution status."""

    PASS = "pass"
    FAIL = "fail"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


# =============================================================================
# Dataclasses (Task 1.2, 1.3, 2.1)
# =============================================================================


@dataclass
class PreFlightStepResult:
    """Result of a single pre-flight step execution.

    Attributes:
        step: Which pre-flight step this result is for.
        status: Outcome of the step (pass/fail/timeout/skipped).
        duration_ms: How long the step took in milliseconds.
        details: Human-readable details about the step result.
        error: Error message if the step failed, None otherwise.
    """

    step: PreFlightStep
    status: StepStatus
    duration_ms: int = 0
    details: str = ""
    error: str | None = None


@dataclass
class PreFlightResult:
    """Overall pre-flight validation result.

    Attributes:
        overall_status: READY if all steps passed, NOT_READY otherwise.
        step_results: Ordered list of individual step results.
        total_duration_ms: Total time for the entire pre-flight sequence.
        drop_box_id: Identifier of the drop box that was validated.
        timestamp: When the pre-flight was executed.
    """

    overall_status: PreFlightStatus
    step_results: list[PreFlightStepResult] = field(default_factory=list)
    total_duration_ms: int = 0
    drop_box_id: str = ""
    timestamp: str = ""


@dataclass
class PreFlightConfig:
    """Configuration for pre-flight protocol.

    Attributes:
        step_timeout_seconds: Maximum time per step before timeout (default: 10s).
    """

    step_timeout_seconds: int = 10


# =============================================================================
# Pre-Flight Protocol (Tasks 2, 3, 4)
# =============================================================================


class PreFlightProtocol:
    """Execute deterministic pre-flight validation for a drop box.

    Per FR26: PING→EXEC_TEST→STREAM_TEST→NET_ENUM→READY sequence.
    Each step has a 10s timeout. Fails fast on first failure.

    Usage:
        protocol = PreFlightProtocol(
            config=PreFlightConfig(),
            c2_server=c2_server,
            event_bus=event_bus,
        )
        result = await protocol.run_preflight("drop-box-001")
        if result.overall_status == PreFlightStatus.READY:
            print("Drop box connected. Pre-flight passed. Ready for objective.")
    """

    # Ordered sequence of executable steps (READY is a state, not a step)
    STEP_SEQUENCE = [
        PreFlightStep.PING,
        PreFlightStep.EXEC_TEST,
        PreFlightStep.STREAM_TEST,
        PreFlightStep.NET_ENUM,
    ]

    def __init__(
        self,
        config: PreFlightConfig | None = None,
        c2_server: C2Server | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Initialize PreFlightProtocol.

        Args:
            config: Optional configuration (uses defaults if not provided).
            c2_server: C2Server for sending commands to drop box.
            event_bus: EventBus for publishing c2.preflight.* events.
        """
        self.config = config or PreFlightConfig()
        self._c2_server = c2_server
        self._event_bus = event_bus

    async def run_preflight(self, drop_box_id: str) -> PreFlightResult:
        """Execute full pre-flight sequence for a drop box.

        Runs steps in deterministic order: PING→EXEC_TEST→STREAM_TEST→NET_ENUM.
        Fails fast: if any step fails or times out, remaining steps are SKIPPED.

        Args:
            drop_box_id: Identifier of the drop box to validate.

        Returns:
            PreFlightResult with overall status and individual step results.
        """
        start_time = time.monotonic()
        timestamp = datetime.now(UTC).isoformat()
        step_results: list[PreFlightStepResult] = []

        log.info("c2_preflight_started", drop_box_id=drop_box_id)

        # Publish started event (Task 4.1)
        await self._publish_event(
            "c2.preflight.started",
            {"drop_box_id": drop_box_id, "timestamp": timestamp},
        )

        # Step executor mapping
        step_executors = {
            PreFlightStep.PING: self._execute_ping,
            PreFlightStep.EXEC_TEST: self._execute_exec_test,
            PreFlightStep.STREAM_TEST: self._execute_stream_test,
            PreFlightStep.NET_ENUM: self._execute_net_enum,
        }

        failed = False
        for step in self.STEP_SEQUENCE:
            if failed:
                # Fail-fast: skip remaining steps (AC #7)
                step_results.append(
                    PreFlightStepResult(
                        step=step,
                        status=StepStatus.SKIPPED,
                        details="Skipped due to previous step failure",
                    )
                )
                continue

            executor = step_executors[step]
            result = await self._execute_with_timeout(executor, drop_box_id, step)
            step_results.append(result)

            # Publish step completed event (Task 4.2)
            await self._publish_event(
                "c2.preflight.step_completed",
                {
                    "drop_box_id": drop_box_id,
                    "step": step.value,
                    "status": result.status.value,
                    "duration_ms": result.duration_ms,
                },
            )

            if result.status != StepStatus.PASS:
                failed = True

        total_duration_ms = int((time.monotonic() - start_time) * 1000)
        overall_status = PreFlightStatus.READY if not failed else PreFlightStatus.NOT_READY

        preflight_result = PreFlightResult(
            overall_status=overall_status,
            step_results=step_results,
            total_duration_ms=total_duration_ms,
            drop_box_id=drop_box_id,
            timestamp=timestamp,
        )

        log.info(
            "c2_preflight_completed",
            drop_box_id=drop_box_id,
            overall_status=overall_status.value,
            total_duration_ms=total_duration_ms,
        )

        # Publish completed event (Task 4.3)
        await self._publish_event(
            "c2.preflight.completed",
            {
                "drop_box_id": drop_box_id,
                "overall_status": overall_status.value,
                "total_duration_ms": total_duration_ms,
            },
        )

        return preflight_result

    # =========================================================================
    # Step Executors (Tasks 2.4-2.7)
    # =========================================================================

    async def _execute_ping(self, drop_box_id: str) -> PreFlightStepResult:
        """Execute PING step — measure RTT latency (AC #2).

        Sends a ping to the drop box and measures round-trip time.

        Args:
            drop_box_id: Drop box to ping.

        Returns:
            PreFlightStepResult with RTT latency in details.
        """
        start = time.monotonic()
        try:
            if self._c2_server is None:
                raise RuntimeError("No C2 server configured")

            # Send ping command and await response
            await self._send_command(drop_box_id, "preflight_ping", {})
            response = await self._receive_response(drop_box_id, "preflight_ping")

            elapsed_ms = int((time.monotonic() - start) * 1000)

            if response and response.get("success"):
                return PreFlightStepResult(
                    step=PreFlightStep.PING,
                    status=StepStatus.PASS,
                    duration_ms=elapsed_ms,
                    details=f"RTT: {elapsed_ms}ms",
                )
            else:
                return PreFlightStepResult(
                    step=PreFlightStep.PING,
                    status=StepStatus.FAIL,
                    duration_ms=elapsed_ms,
                    details="Ping failed — no valid response",
                    error=response.get("error", "Unknown error") if response else "No response",
                )
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return PreFlightStepResult(
                step=PreFlightStep.PING,
                status=StepStatus.FAIL,
                duration_ms=elapsed_ms,
                details="Ping failed",
                error=str(e),
            )

    async def _execute_exec_test(self, drop_box_id: str) -> PreFlightStepResult:
        """Execute EXEC_TEST step — send benign command, validate response (AC #3).

        Sends `echo preflight_test` and validates non-empty, successful response.

        Args:
            drop_box_id: Drop box to test command execution.

        Returns:
            PreFlightStepResult with command output in details.
        """
        start = time.monotonic()
        try:
            if self._c2_server is None:
                raise RuntimeError("No C2 server configured")

            await self._send_command(
                drop_box_id,
                "preflight_exec",
                {"command": "echo preflight_test"},
            )
            response = await self._receive_response(drop_box_id, "preflight_exec")

            elapsed_ms = int((time.monotonic() - start) * 1000)

            if response and response.get("success"):
                output = response.get("output", "")
                if output:
                    return PreFlightStepResult(
                        step=PreFlightStep.EXEC_TEST,
                        status=StepStatus.PASS,
                        duration_ms=elapsed_ms,
                        details=f"Command output: {output}",
                    )
                else:
                    return PreFlightStepResult(
                        step=PreFlightStep.EXEC_TEST,
                        status=StepStatus.FAIL,
                        duration_ms=elapsed_ms,
                        details="Command returned empty output",
                        error="Empty output",
                    )
            else:
                return PreFlightStepResult(
                    step=PreFlightStep.EXEC_TEST,
                    status=StepStatus.FAIL,
                    duration_ms=elapsed_ms,
                    details="Exec test failed",
                    error=response.get("error", "Unknown error") if response else "No response",
                )
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return PreFlightStepResult(
                step=PreFlightStep.EXEC_TEST,
                status=StepStatus.FAIL,
                duration_ms=elapsed_ms,
                details="Exec test failed",
                error=str(e),
            )

    async def _execute_stream_test(self, drop_box_id: str) -> PreFlightStepResult:
        """Execute STREAM_TEST step — test bidirectional streaming (AC #4).

        Sends a known data payload in both directions and verifies integrity
        via SHA-256 hash comparison.

        Args:
            drop_box_id: Drop box to test streaming.

        Returns:
            PreFlightStepResult with streaming integrity status.
        """
        start = time.monotonic()
        try:
            if self._c2_server is None:
                raise RuntimeError("No C2 server configured")

            # Generate test payload and expected hash
            test_payload = "preflight_stream_integrity_test_data"
            expected_hash = hashlib.sha256(test_payload.encode()).hexdigest()

            await self._send_command(
                drop_box_id,
                "preflight_stream",
                {"payload": test_payload, "expected_hash": expected_hash},
            )
            response = await self._receive_response(drop_box_id, "preflight_stream")

            elapsed_ms = int((time.monotonic() - start) * 1000)

            if response and response.get("success"):
                received_hash = response.get("hash", "")
                if received_hash == expected_hash:
                    return PreFlightStepResult(
                        step=PreFlightStep.STREAM_TEST,
                        status=StepStatus.PASS,
                        duration_ms=elapsed_ms,
                        details="Bidirectional streaming verified — hash match",
                    )
                else:
                    return PreFlightStepResult(
                        step=PreFlightStep.STREAM_TEST,
                        status=StepStatus.FAIL,
                        duration_ms=elapsed_ms,
                        details="Stream integrity check failed — hash mismatch",
                        error=f"Expected {expected_hash}, got {received_hash}",
                    )
            else:
                return PreFlightStepResult(
                    step=PreFlightStep.STREAM_TEST,
                    status=StepStatus.FAIL,
                    duration_ms=elapsed_ms,
                    details="Stream test failed",
                    error=response.get("error", "Unknown error") if response else "No response",
                )
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return PreFlightStepResult(
                step=PreFlightStep.STREAM_TEST,
                status=StepStatus.FAIL,
                duration_ms=elapsed_ms,
                details="Stream test failed",
                error=str(e),
            )

    async def _execute_net_enum(self, drop_box_id: str) -> PreFlightStepResult:
        """Execute NET_ENUM step — discover network interfaces (AC #5).

        Requests network interface enumeration from the drop box and
        stores results for engagement context.

        Args:
            drop_box_id: Drop box to enumerate networks.

        Returns:
            PreFlightStepResult with network interface data in details.
        """
        start = time.monotonic()
        try:
            if self._c2_server is None:
                raise RuntimeError("No C2 server configured")

            await self._send_command(
                drop_box_id,
                "preflight_net_enum",
                {},
            )
            response = await self._receive_response(drop_box_id, "preflight_net_enum")

            elapsed_ms = int((time.monotonic() - start) * 1000)

            if response and response.get("success"):
                interfaces = response.get("interfaces", [])
                if interfaces:
                    return PreFlightStepResult(
                        step=PreFlightStep.NET_ENUM,
                        status=StepStatus.PASS,
                        duration_ms=elapsed_ms,
                        details=f"Discovered {len(interfaces)} interface(s)",
                    )
                else:
                    return PreFlightStepResult(
                        step=PreFlightStep.NET_ENUM,
                        status=StepStatus.FAIL,
                        duration_ms=elapsed_ms,
                        details="No network interfaces discovered",
                        error="Empty interface list",
                    )
            else:
                return PreFlightStepResult(
                    step=PreFlightStep.NET_ENUM,
                    status=StepStatus.FAIL,
                    duration_ms=elapsed_ms,
                    details="Network enumeration failed",
                    error=response.get("error", "Unknown error") if response else "No response",
                )
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return PreFlightStepResult(
                step=PreFlightStep.NET_ENUM,
                status=StepStatus.FAIL,
                duration_ms=elapsed_ms,
                details="Network enumeration failed",
                error=str(e),
            )

    # =========================================================================
    # Internal helpers
    # =========================================================================

    async def _execute_with_timeout(
        self,
        executor: Any,
        drop_box_id: str,
        step: PreFlightStep,
    ) -> PreFlightStepResult:
        """Execute a step with per-step timeout (Task 2.8).

        Args:
            executor: Async function to call for the step.
            drop_box_id: Drop box identifier.
            step: Which step is being executed.

        Returns:
            PreFlightStepResult — TIMEOUT status if the step exceeds the timeout.
        """
        start = time.monotonic()
        try:
            return await asyncio.wait_for(
                executor(drop_box_id),
                timeout=self.config.step_timeout_seconds,
            )
        except TimeoutError:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            log.warning(
                "c2_preflight_step_timeout",
                drop_box_id=drop_box_id,
                step=step.value,
                timeout_seconds=self.config.step_timeout_seconds,
            )
            return PreFlightStepResult(
                step=step,
                status=StepStatus.TIMEOUT,
                duration_ms=elapsed_ms,
                details=f"Step timed out after {self.config.step_timeout_seconds}s",
                error="Timeout",
            )

    async def _send_command(
        self,
        drop_box_id: str,
        command: str,
        args: dict[str, Any],
    ) -> None:
        """Send a preflight command to the drop box via C2 server.

        Args:
            drop_box_id: Target drop box identifier.
            command: Preflight command name.
            args: Command arguments.
        """
        if self._c2_server is None:
            raise RuntimeError("No C2 server configured")

        log.debug(
            "c2_preflight_send_command",
            drop_box_id=drop_box_id,
            command=command,
        )
        # Delegate to C2Server's send mechanism
        # The C2Server will create a signed C2Message and send via WebSocket
        await self._c2_server.send_to_drop_box(drop_box_id, command, args)

    async def _receive_response(
        self,
        drop_box_id: str,
        command: str,
    ) -> dict[str, Any] | None:
        """Receive response from drop box for a preflight command.

        Args:
            drop_box_id: Drop box identifier.
            command: Command name to match response against.

        Returns:
            Response payload dict, or None if no response received.
        """
        if self._c2_server is None:
            raise RuntimeError("No C2 server configured")

        log.debug(
            "c2_preflight_await_response",
            drop_box_id=drop_box_id,
            command=command,
        )
        return await self._c2_server.receive_from_drop_box(drop_box_id, command)

    async def _publish_event(self, channel: str, payload: dict[str, Any]) -> None:
        """Publish event to EventBus if available (Task 4).

        Args:
            channel: Event channel (e.g., "c2.preflight.started").
            payload: Event payload dict.
        """
        if self._event_bus:
            try:
                event_channel = channel.replace(".", ":")
                await self._event_bus.publish(event_channel, payload)
                log.debug(
                    "event_published",
                    channel=event_channel,
                    drop_box_id=payload.get("drop_box_id"),
                )
            except Exception as e:
                log.warning(
                    "event_publish_failed",
                    channel=channel,
                    error=str(e),
                )
