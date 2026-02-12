"""Drop Box Abort & Wipe functionality.

Story 12.10: Drop Box Abort & Wipe
Per FR30: Operator can send abort/wipe command to any drop box
Per ERR4: Drop box connection loss — Log warning, attempt wipe command, mark lost

Abort sequence:
1. Send abort command via C2 with reason
2. Drop box stops all operations immediately
3. Drop box executes secure wipe (overwrite + delete)
4. Drop box initiates self-destruct (exit process, optionally delete binary)
5. Report back to C2 (if connection available)

Security: Sensitive files are overwritten with random data before deletion
         to prevent forensic recovery.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog

from cyberred.c2.protocol import C2Message, C2MessageType, sign_payload

if TYPE_CHECKING:
    from cyberred.c2.server import C2Server
    from cyberred.core.events import EventBus

log = structlog.get_logger()


# =============================================================================
# Enums (Task 1.1, 1.2)
# =============================================================================


class AbortReason(Enum):
    """Reasons for aborting a drop box.

    Per AC#1: Command includes abort reason for audit trail.

    Attributes:
        OPERATOR_INITIATED: Normal operator-triggered abort.
        COMPROMISED: Drop box suspected to be compromised.
        ENGAGEMENT_ENDED: Engagement has concluded.
        EMERGENCY: Emergency abort (fastest path).
    """

    OPERATOR_INITIATED = "operator_initiated"
    COMPROMISED = "compromised"
    ENGAGEMENT_ENDED = "engagement_ended"
    EMERGENCY = "emergency"


class WipeStatus(Enum):
    """Status of the wipe operation.

    Per AC#3 and AC#5: Wipe status is reported and logged.

    Attributes:
        SUCCESS: All sensitive files wiped successfully.
        PARTIAL: Some files wiped, some failed (see errors).
        FAILED: Wipe failed completely.
        IN_PROGRESS: Wipe is currently executing.
        NOT_STARTED: Wipe has not been initiated.
    """

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    NOT_STARTED = "not_started"


# =============================================================================
# Dataclasses (Task 1.3, 1.4, 1.5, 2.1)
# =============================================================================


@dataclass
class AbortCommand:
    """Abort command to send to a drop box.

    Per AC#1: Command includes reason for audit trail.

    Attributes:
        drop_box_id: Identifier of the drop box to abort.
        reason: Why the abort was triggered.
        issued_by: Operator/system that issued the abort.
        timestamp: When the abort was issued (ISO8601).
        delete_binary: Whether to delete the drop box binary after wipe.
    """

    drop_box_id: str
    reason: AbortReason
    issued_by: str
    timestamp: str
    delete_binary: bool = False


@dataclass
class WipeResult:
    """Result of a wipe operation.

    Per AC#3: Wipe completion status is reported back to C2.

    Attributes:
        status: Overall wipe status.
        files_wiped: Number of files successfully wiped.
        files_failed: Number of files that failed to wipe.
        errors: List of error messages for failed files.
        duration_ms: How long the wipe took in milliseconds.
    """

    status: WipeStatus
    files_wiped: int
    files_failed: int
    errors: list[str]
    duration_ms: int


@dataclass
class AbortResult:
    """Overall result of an abort operation.

    Per AC#2, AC#4: Drop box stops operations and initiates self-destruct.

    Attributes:
        drop_box_id: Identifier of the drop box.
        abort_received: Whether the drop box acknowledged the abort command.
        wipe_result: Result of the wipe operation (None if not received).
        self_destruct_initiated: Whether self-destruct was triggered.
        timestamp: When the result was recorded (ISO8601).
    """

    drop_box_id: str
    abort_received: bool
    wipe_result: WipeResult | None
    self_destruct_initiated: bool
    timestamp: str


@dataclass
class AbortControllerConfig:
    """Configuration for AbortController.

    Attributes:
        wipe_timeout_seconds: Maximum time to wait for wipe confirmation.
            Default is 30s, which allows time for wiping typical drop box
            sensitive files (certs, logs, cache) even on slower storage.
        delete_binary_default: Default value for delete_binary option (default: False).
    """

    wipe_timeout_seconds: int = 30
    delete_binary_default: bool = False


# =============================================================================
# Message Protocol Helper (Task 3)
# =============================================================================


def create_abort_command_message(
    drop_box_id: str,
    reason: AbortReason,
    delete_binary: bool,
    secret: bytes,
    message_id: str | None = None,
) -> C2Message:
    """Create an abort command message with signature.

    Per Task 3.2: Abort command payload structure.

    Args:
        drop_box_id: Target drop box identifier.
        reason: Abort reason for audit trail.
        delete_binary: Whether to delete binary after wipe.
        secret: Shared secret for HMAC signing.
        message_id: Optional custom message ID.

    Returns:
        Signed C2Message with abort command payload.
    """
    import uuid

    payload = {
        "command": "abort",
        "args": {
            "drop_box_id": drop_box_id,
            "reason": reason.value,
            "delete_binary": delete_binary,
        },
    }

    return C2Message(
        type=C2MessageType.COMMAND,
        id=message_id or str(uuid.uuid4()),
        timestamp=datetime.now(UTC).isoformat(),
        payload=payload,
        signature=sign_payload(payload, secret),
    )


# =============================================================================
# AbortController (Tasks 2, 5)
# =============================================================================


class AbortController:
    """Controller for abort and wipe operations.

    Per FR30: Operator can send abort/wipe command to any drop box.
    Per ERR4: Handle connection loss during abort (fail-safe wipe).

    Usage:
        controller = AbortController(
            config=AbortControllerConfig(),
            c2_server=c2_server,
            event_bus=event_bus,
        )
        result = await controller.send_abort(
            drop_box_id="drop-box-001",
            reason=AbortReason.OPERATOR_INITIATED,
            issued_by="operator@example.com",
        )
        if result.abort_received:
            print(f"Wipe status: {result.wipe_result.status}")
    """

    def __init__(
        self,
        config: AbortControllerConfig | None = None,
        c2_server: C2Server | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Initialize AbortController.

        Args:
            config: Optional configuration (uses defaults if not provided).
            c2_server: C2Server for sending abort commands.
            event_bus: EventBus for publishing c2.abort.* events.
        """
        self.config = config or AbortControllerConfig()
        self._c2_server = c2_server
        self._event_bus = event_bus

    async def send_abort(
        self,
        drop_box_id: str,
        reason: AbortReason,
        issued_by: str,
        delete_binary: bool | None = None,
    ) -> AbortResult:
        """Send abort command to a drop box.

        Per AC#1: Sends abort command via C2 with reason for audit trail.
        Per AC#6: Handles connection loss (fail-safe wipe, mark as lost).

        Args:
            drop_box_id: Identifier of the drop box to abort.
            reason: Why the abort is being triggered.
            issued_by: Operator/system issuing the abort.
            delete_binary: Whether to delete binary (uses config default if None).

        Returns:
            AbortResult with wipe status and self-destruct info.
        """
        start_time = time.monotonic()
        timestamp = datetime.now(UTC).isoformat()

        if delete_binary is None:
            delete_binary = self.config.delete_binary_default

        log.info(
            "c2_abort_initiated",
            drop_box_id=drop_box_id,
            reason=reason.value,
            issued_by=issued_by,
            delete_binary=delete_binary,
        )

        # Publish abort initiated event (Task 5.1)
        await self._publish_event(
            "c2.abort.initiated",
            {
                "drop_box_id": drop_box_id,
                "reason": reason.value,
                "issued_by": issued_by,
                "timestamp": timestamp,
            },
        )

        # Send abort command to drop box
        try:
            await self._send_abort_command(drop_box_id, reason, delete_binary)
        except Exception as e:
            log.error(
                "c2_abort_send_failed",
                drop_box_id=drop_box_id,
                error=str(e),
            )
            # Even if send fails, mark as lost and return
            await self._handle_connection_lost(drop_box_id, reason)
            return AbortResult(
                drop_box_id=drop_box_id,
                abort_received=False,
                wipe_result=None,
                self_destruct_initiated=False,
                timestamp=timestamp,
            )

        # Wait for wipe confirmation
        try:
            wipe_result = await self._wait_for_wipe_confirmation(drop_box_id)
            abort_received = True
            self_destruct_initiated = True  # Implied by successful wipe

            # Publish wipe completed event (Task 5.2)
            await self._publish_event(
                "c2.abort.wipe_completed",
                {
                    "drop_box_id": drop_box_id,
                    "wipe_status": wipe_result.status.value,
                    "files_wiped": wipe_result.files_wiped,
                    "files_failed": wipe_result.files_failed,
                },
            )

        except asyncio.TimeoutError:
            log.warning(
                "c2_abort_timeout",
                drop_box_id=drop_box_id,
                timeout_seconds=self.config.wipe_timeout_seconds,
            )

            # Connection lost - mark drop box as lost (AC#6)
            await self._handle_connection_lost(drop_box_id, reason)

            # Wipe proceeds anyway on drop box (fail-safe)
            wipe_result = None
            abort_received = False
            self_destruct_initiated = False

        except Exception as e:
            log.error(
                "c2_abort_error",
                drop_box_id=drop_box_id,
                error=str(e),
            )
            await self._handle_connection_lost(drop_box_id, reason)
            wipe_result = None
            abort_received = False
            self_destruct_initiated = False

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        result = AbortResult(
            drop_box_id=drop_box_id,
            abort_received=abort_received,
            wipe_result=wipe_result,
            self_destruct_initiated=self_destruct_initiated,
            timestamp=timestamp,
        )

        # Publish abort completed event (Task 5.4)
        await self._publish_event(
            "c2.abort.completed",
            {
                "drop_box_id": drop_box_id,
                "abort_received": abort_received,
                "wipe_status": wipe_result.status.value if wipe_result else "unknown",
                "self_destruct_initiated": self_destruct_initiated,
                "duration_ms": elapsed_ms,
            },
        )

        log.info(
            "c2_abort_completed",
            drop_box_id=drop_box_id,
            abort_received=abort_received,
            wipe_status=wipe_result.status.value if wipe_result else "unknown",
            duration_ms=elapsed_ms,
        )

        return result

    async def _send_abort_command(
        self,
        drop_box_id: str,
        reason: AbortReason,
        delete_binary: bool,
    ) -> None:
        """Send abort command to drop box via C2 server.

        Args:
            drop_box_id: Target drop box identifier.
            reason: Abort reason.
            delete_binary: Whether to delete binary after wipe.

        Raises:
            RuntimeError: If no C2 server is configured.
        """
        if self._c2_server is None:
            raise RuntimeError("No C2 server configured")

        log.debug(
            "c2_abort_send_command",
            drop_box_id=drop_box_id,
            reason=reason.value,
        )

        await self._c2_server.send_to_drop_box(
            drop_box_id,
            "abort",
            {
                "reason": reason.value,
                "delete_binary": delete_binary,
            },
        )

    async def _wait_for_wipe_confirmation(
        self,
        drop_box_id: str,
    ) -> WipeResult:
        """Wait for wipe confirmation from drop box.

        Per Task 2.4: Wait for wipe result message with timeout.

        Args:
            drop_box_id: Drop box identifier.

        Returns:
            WipeResult from drop box response.

        Raises:
            asyncio.TimeoutError: If no response within timeout.
        """
        if self._c2_server is None:
            raise RuntimeError("No C2 server configured")

        response = await asyncio.wait_for(
            self._c2_server.receive_from_drop_box(drop_box_id, "abort"),
            timeout=self.config.wipe_timeout_seconds,
        )

        if response is None:
            raise RuntimeError("No response received")

        # Parse wipe result from response
        wipe_status_str = response.get("wipe_status", "failed")
        try:
            wipe_status = WipeStatus(wipe_status_str)
        except ValueError:
            wipe_status = WipeStatus.FAILED

        return WipeResult(
            status=wipe_status,
            files_wiped=response.get("files_wiped", 0),
            files_failed=response.get("files_failed", 0),
            errors=response.get("errors", []),
            duration_ms=response.get("duration_ms", 0),
        )

    async def _handle_connection_lost(
        self,
        drop_box_id: str,
        reason: AbortReason,
    ) -> None:
        """Handle connection loss during abort.

        Per AC#6 and ERR4: Mark drop box as 'lost', log warning.

        Args:
            drop_box_id: Drop box identifier.
            reason: Original abort reason.
        """
        log.warning(
            "c2_abort_connection_lost",
            drop_box_id=drop_box_id,
            reason=reason.value,
        )

        # Mark drop box as lost on C2 server (Task 2.5)
        if self._c2_server is not None:
            self._c2_server.mark_as_lost(drop_box_id, f"Connection lost during abort: {reason.value}")

        # Publish connection lost event (Task 5.3)
        await self._publish_event(
            "c2.abort.connection_lost",
            {
                "drop_box_id": drop_box_id,
                "reason": reason.value,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    async def _publish_event(self, channel: str, payload: dict[str, Any]) -> None:
        """Publish event to EventBus if available.

        Args:
            channel: Event channel (e.g., "c2:abort:initiated").
            payload: Event payload dict.
        """
        if self._event_bus:
            try:
                await self._event_bus.publish(channel, payload)
                log.debug(
                    "event_published",
                    channel=channel,
                    drop_box_id=payload.get("drop_box_id"),
                )
            except Exception as e:
                log.warning(
                    "event_publish_failed",
                    channel=channel,
                    error=str(e),
                )
