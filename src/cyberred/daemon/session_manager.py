"""Session Manager for Multi-Engagement Orchestration.

This module provides the SessionManager class that manages multiple concurrent
engagements, tracking their lifecycle states and enforcing isolation and
resource limits.

NFR34: Support 5+ concurrent engagements.
FR55-FR61: Session persistence and management.

Usage:
    from cyberred.daemon.session_manager import SessionManager

    manager = SessionManager(max_engagements=10)
    engagement_id = manager.create_engagement(Path("config.yaml"))
    manager.start_engagement(engagement_id)
    manager.list_engagements()  # Returns EngagementSummary list
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union, Any, Awaitable, Callable
import re
import secrets

import structlog
import yaml

from cyberred.core.event_bus import EventBus
from cyberred.core.exceptions import (
    ConfigurationError,
    EngagementNotFoundError,
    InvalidStateTransition,
    ResourceLimitError,
)
from cyberred.daemon.state_machine import (
    EngagementState,
    EngagementStateMachine,
)
from cyberred.daemon.preflight import PreFlightRunner

# Import CheckpointManager for conditional use (avoid circular import)
# Import is done conditionally in methods to allow testing without storage module
TYPE_CHECKING = False
if TYPE_CHECKING:
    from cyberred.storage.checkpoint import CheckpointManager



log = structlog.get_logger()

# Valid engagement name pattern: lowercase letters, numbers, hyphens
ENGAGEMENT_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


def validate_engagement_name(name: str) -> bool:
    """Validate engagement name contains only allowed characters.

    Valid names:
    - Start and end with lowercase letter or number
    - Middle can contain lowercase letters, numbers, and hyphens
    - Minimum length: 1 character

    Args:
        name: Engagement name to validate.

    Returns:
        True if valid, False otherwise.
    """
    if not name:
        return False
    return bool(ENGAGEMENT_NAME_PATTERN.match(name))


@dataclass
class EngagementContext:
    """Context for a managed engagement.

    Attributes:
        id: Unique engagement identifier.
        state_machine: Engagement lifecycle state machine.
        config_path: Path to engagement configuration file.
        created_at: UTC timestamp when engagement was created.
        agent_count: Current active agent count (placeholder for Epic 7).
        finding_count: Current finding count (placeholder for Epic 7).
    """

    id: str
    state_machine: EngagementStateMachine
    config_path: Path
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent_count: int = 0
    finding_count: int = 0

    @property
    def state(self) -> EngagementState:
        """Current engagement state."""
        return self.state_machine.current_state

    @property
    def is_active(self) -> bool:
        """Check if engagement is active (INITIALIZING, RUNNING, or PAUSED).

        Active engagements count against the max_engagements limit.
        """
        return self.state in (
            EngagementState.INITIALIZING,
            EngagementState.RUNNING,
            EngagementState.PAUSED,
        )


@dataclass(frozen=True)
class EngagementSummary:
    """Summary of an engagement for listing.

    Immutable dataclass for external consumption via IPC.
    """

    id: str
    state: str
    agent_count: int
    finding_count: int
    created_at: datetime


class SessionManager:
    """Manages multiple concurrent engagements.

    Provides lifecycle operations for engagements while ensuring
    isolation between them and enforcing resource limits.

    Attributes:
        max_engagements: Maximum allowed concurrent active engagements.
    """

    def __init__(
        self, 
        max_engagements: int = 10, 
        max_history: int = 50,
        event_bus: Optional[EventBus] = None,
        checkpoint_manager: Optional[Any] = None,
    ) -> None:
        """Initialize SessionManager.

        Args:
            max_engagements: Maximum concurrent active engagements (default: 10).
            max_history: Maximum total engagements to track (active + stopped) (default: 50).
            event_bus: Optional EventBus for state propagation.
            checkpoint_manager: Optional CheckpointManager for cold state persistence.
        """
        self._max_engagements = max_engagements
        self._max_history = max_history
        self._event_bus = event_bus
        self._checkpoint_manager = checkpoint_manager
        self._engagements: dict[str, EngagementContext] = {}
        # Subscriptions: engagement_id -> {subscription_id -> callback}
        self._subscriptions: dict[str, dict[str, Callable]] = {}

    async def _on_state_change(self, engagement_id: str, old_state: EngagementState, new_state: EngagementState) -> None:
        """Listener callback for state machine changes."""
        if self._event_bus:
            channel = f"engagement:{engagement_id}:state"
            message = {
                "type": "state_change",
                "engagement_id": engagement_id,
                "old_state": str(old_state),
                "new_state": str(new_state),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            try:
                await self._event_bus.publish(channel, message)
                log.debug(
                    "state_change_published", 
                    channel=channel, 
                    from_state=str(old_state), 
                    to_state=str(new_state)
                )
            except Exception as e:
                log.error("state_publish_failed", error=str(e), engagement_id=engagement_id)

    @property
    def max_engagements(self) -> int:
        """Maximum allowed concurrent active engagements."""
        return self._max_engagements

    @property
    def max_history(self) -> int:
        """Maximum total engagements to track."""
        return self._max_history

    @property
    def active_count(self) -> int:
        """Count of currently active engagements (INITIALIZING, RUNNING, or PAUSED)."""
        return sum(1 for e in self._engagements.values() if e.is_active)

    @property
    def remaining_capacity(self) -> int:
        """Remaining capacity for new active engagements."""
        return max(0, self._max_engagements - self.active_count)

    def _generate_id(self, name: str) -> str:
        """Generate unique engagement ID.

        Args:
            name: Base name for engagement.

        Returns:
            Unique ID in format: {name}-{YYYYMMDD-HHMMSS}-{random}
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        suffix = secrets.token_hex(3)  # 6 chars
        return f"{name}-{timestamp}-{suffix}"

    def _prune_history(self) -> None:
        """Prune old completed/stopped engagements if history limit reached."""
        if len(self._engagements) < self._max_history:
            return

        # Find candidates for removal (not active)
        candidates = [
            e for e in self._engagements.values()
            if not e.is_active
        ]
        
        # Sort by creation time (oldest first)
        candidates.sort(key=lambda x: x.created_at)

        # Remove oldest until we are under limit
        # We need to remove enough to make room for 1 new one, so target is max_history - 1
        num_to_remove = len(self._engagements) - self._max_history + 1
        
        for i in range(min(num_to_remove, len(candidates))):
            del self._engagements[candidates[i].id]
            log.info("engagement_pruned", engagement_id=candidates[i].id)

    def create_engagement(self, config_path: Path) -> str:
        """Create a new engagement from configuration.

        Args:
            config_path: Path to engagement YAML configuration.

        Returns:
            Generated engagement ID.

        Raises:
            ConfigurationError: If config is invalid or name is invalid.
            ResourceLimitError: If max_engagements limit reached.
            FileNotFoundError: If config file doesn't exist.
        """
        # Check active capacity
        if self.active_count >= self._max_engagements:
            raise ResourceLimitError(
                message=(
                    f"Maximum active engagements ({self._max_engagements}) reached. "
                    "Stop or complete an existing engagement to create a new one."
                ),
                limit_type="max_engagements",
                current_value=self.active_count,
                max_value=self._max_engagements,
            )

        # Prune history if needed
        self._prune_history()

        # Check total capacity (if pruning didn't help because all are active)
        if len(self._engagements) >= self._max_history:
             raise ResourceLimitError(
                message=(
                    f"Maximum total engagements ({self._max_history}) reached and "
                    "all are active. Cannot create new engagement."
                ),
                limit_type="max_history",
                current_value=len(self._engagements),
                max_value=self._max_history,
             )

        if not config_path.exists():
            raise FileNotFoundError(f"Engagement config not found: {config_path}")

        # Parse name from config or use filename stem
        try:
            with config_path.open() as f:
                config = yaml.safe_load(f) or {}
            name = config.get("name", config_path.stem).lower()
        except yaml.YAMLError as e:
            raise ConfigurationError(
                config_path=str(config_path),
                message=f"Invalid YAML in {config_path}: {e}",
            )

        # Validate name
        if not validate_engagement_name(name):
            raise ConfigurationError(
                config_path=str(config_path),
                key="name",
                message=(
                    f"Invalid engagement name '{name}'. "
                    "Name must contain only lowercase letters, numbers, and hyphens, "
                    "and must start and end with a letter or number."
                ),
            )

        # Generate ID and create context
        engagement_id = self._generate_id(name)
        state_machine = EngagementStateMachine(engagement_id)
        context = EngagementContext(
            id=engagement_id,
            state_machine=state_machine,
            config_path=config_path,
        )

        # Attach state listener for Redis propagation
        # We use a closure or partial to capture the ID, but the listener receives states.
        # However, our _on_state_change needs the ID.
        # StateMachine.add_listener expects (old, new) -> None|Awaitable
        # So we wrap it.
        async def state_listener(old, new, eid=engagement_id):
            await self._on_state_change(eid, old, new)
        
        state_machine.add_listener(state_listener)

        self._engagements[engagement_id] = context

        log.info(
            "engagement_created",
            engagement_id=engagement_id,
            config_path=str(config_path),
            state=str(state_machine.current_state),
        )

        return engagement_id

    def get_engagement(self, engagement_id: str) -> Optional[EngagementContext]:
        """Get engagement context by ID.

        Args:
            engagement_id: Engagement ID to look up.

        Returns:
            EngagementContext if found, None otherwise.
        """
        return self._engagements.get(engagement_id)

    def get_engagement_or_raise(self, engagement_id: str) -> EngagementContext:
        """Get engagement context by ID, raising if not found.

        Args:
            engagement_id: Engagement ID to look up.

        Returns:
            EngagementContext.

        Raises:
            EngagementNotFoundError: If engagement not found.
        """
        context = self.get_engagement(engagement_id)
        if context is None:
            raise EngagementNotFoundError(engagement_id)
        return context

    def list_engagements(self) -> list[EngagementSummary]:
        """List all engagements with summary info.

        Returns:
            List of EngagementSummary, sorted by created_at (newest first).
        """
        summaries = [
            EngagementSummary(
                id=e.id,
                state=str(e.state),
                agent_count=e.agent_count,
                finding_count=e.finding_count,
                created_at=e.created_at,
            )
            for e in self._engagements.values()
        ]
        return sorted(summaries, key=lambda s: s.created_at, reverse=True)

    async def start_engagement(self, engagement_id: str, ignore_warnings: bool = False) -> EngagementState:
        """Start an engagement (INITIALIZING → RUNNING).

        Runs pre-flight checks before starting.

        Args:
            engagement_id: Engagement ID to start.
            ignore_warnings: If True, proceed despite P1 warnings.

        Returns:
            New state (RUNNING).

        Raises:
            EngagementNotFoundError: If engagement not found.
            InvalidStateTransition: If not in INITIALIZING state.
            PreFlightCheckError: If P0 checks fail.
            PreFlightWarningError: If P1 checks warn and not ignore_warnings.
        """
        context = self.get_engagement_or_raise(engagement_id)
        
        # Verify state first
        if context.state != EngagementState.INITIALIZING:
             # Let state machine raise generic error, or check here
             # State machine raises InvalidStateTransition
             pass

        # Load config for pre-flight checks
        # Assuming config is valid YAML since we checked at creation, 
        # but file might have changed. Catch errors.
        try:
            with context.config_path.open() as f:
                config = yaml.safe_load(f) or {}
                # Inject config path for ScopeCheck
                config["scope_path"] = config.get("scope_path") or str(context.config_path.parent / "scope.yaml")
                # Also pass the config path itself if needed
                config["engagement_config_path"] = str(context.config_path)
        except Exception as e:
            raise ConfigurationError(
                config_path=str(context.config_path),
                message=f"Failed to load config for pre-flight: {e}"
            )

        # Run Pre-Flight Checks
        runner = PreFlightRunner()
        results = await runner.run_all(config)

        runner.validate_results(results, ignore_warnings=ignore_warnings)

        # Log check results summary
        log.info(
            "preflight_checks_completed",
            engagement_id=engagement_id,
            results=[{"name": r.name, "status": str(r.status), "priority": str(r.priority)} for r in results]
        )

        context.state_machine.start()

        log.info(
            "engagement_started",
            engagement_id=engagement_id,
            state=str(context.state),
        )

        return context.state

    def pause_engagement(self, engagement_id: str) -> EngagementState:
        """Pause an engagement (RUNNING → PAUSED).

        This is a HOT STATE operation - state is preserved in memory (RAM) only.
        No disk I/O occurs during pause. Resume is instant (<1s per NFR31).

        Args:
            engagement_id: Engagement ID to pause.

        Returns:
            New state (PAUSED).

        Raises:
            EngagementNotFoundError: If engagement not found.
            InvalidStateTransition: If not in RUNNING state.
        """
        context = self.get_engagement_or_raise(engagement_id)
        context.state_machine.pause()

        log.info(
            "engagement_paused",
            engagement_id=engagement_id,
            state=str(context.state),
        )

        return context.state

    def resume_engagement(self, engagement_id: str) -> EngagementState:
        """Resume an engagement (PAUSED → RUNNING).

        This is a HOT STATE operation - resumes from memory (RAM) state.
        No checkpoint reload required. Resume completes in <1s (NFR31).

        Args:
            engagement_id: Engagement ID to resume.

        Returns:
            New state (RUNNING).

        Raises:
            EngagementNotFoundError: If engagement not found.
            InvalidStateTransition: If not in PAUSED state.
        """
        context = self.get_engagement_or_raise(engagement_id)
        context.state_machine.resume()

        log.info(
            "engagement_resumed",
            engagement_id=engagement_id,
            state=str(context.state),
        )

        return context.state

    async def stop_engagement(self, engagement_id: str) -> tuple[EngagementState, Optional[Path]]:
        """Stop an engagement with checkpoint (RUNNING/PAUSED → STOPPED).
        
        This is a COLD STATE operation - full state is persisted to SQLite
        checkpoint file for later recovery. Contrast with pause_engagement()
        which preserves hot state in RAM only.
        
        Args:
            engagement_id: Engagement ID to stop.
            
        Returns:
            Tuple of (new_state, checkpoint_path). checkpoint_path is None
            if no CheckpointManager is configured.
            
        Raises:
            EngagementNotFoundError: If engagement not found.
            InvalidStateTransition: If not in RUNNING or PAUSED state.
        """
        context = self.get_engagement_or_raise(engagement_id)
        
        # Optimization: Pre-check state validity before expensive checkpoint save
        # This prevents wasted I/O if the engagement is already stopped or completed
        from cyberred.daemon.state_machine import is_valid_transition
        if not is_valid_transition(context.state, EngagementState.STOPPED):
             raise InvalidStateTransition(
                engagement_id=engagement_id,
                from_state=str(context.state),
                to_state=str(EngagementState.STOPPED),
            )
        
        # Create checkpoint before state transition
        checkpoint_path: Optional[Path] = None
        if self._checkpoint_manager:
            # Get scope path from config if available
            scope_path = None
            try:
                with context.config_path.open() as f:
                    config = yaml.safe_load(f) or {}
                    scope_path_str = config.get("scope_path")
                    if scope_path_str:
                        scope_path = Path(scope_path_str)
            except Exception:
                pass  # Continue without scope hash if config read fails
            
            checkpoint_path = await self._checkpoint_manager.save(
                engagement_id=engagement_id,
                scope_path=scope_path,
                agents=[],  # Placeholder - actual agent states from Epic 7
                findings=[],  # TODO(Epic-7): Integrate actual findings from agents. NFR12 requires 100% preservation.
            )
            
            log.info(
                "checkpoint_created",
                engagement_id=engagement_id,
                checkpoint_path=str(checkpoint_path),
            )
        
        context.state_machine.stop()

        log.info(
            "engagement_stopped",
            engagement_id=engagement_id,
            state=str(context.state),
            checkpoint_path=str(checkpoint_path) if checkpoint_path else None,
        )

        return context.state, checkpoint_path

    def complete_engagement(self, engagement_id: str) -> EngagementState:
        """Complete an engagement (STOPPED → COMPLETED).

        Args:
            engagement_id: Engagement ID to complete.

        Returns:
            New state (COMPLETED).

        Raises:
            EngagementNotFoundError: If engagement not found.
            InvalidStateTransition: If not in STOPPED state.
        """
        context = self.get_engagement_or_raise(engagement_id)
        context.state_machine.complete()

        log.info(
            "engagement_completed",
            engagement_id=engagement_id,
            state=str(context.state),
        )

        return context.state

    async def remove_engagement(self, engagement_id: str) -> bool:
        """Remove an engagement from tracking and cleanup resources.
        
        Only STOPPED or COMPLETED engagements can be removed.
        Deletes associated checkpoint file to prevent resource leaks (Zombie Checkpoints).

        Args:
            engagement_id: Engagement ID to remove.

        Returns:
            True if removed, False if not found.

        Raises:
            InvalidStateTransition: If engagement is INITIALIZING, RUNNING, or PAUSED.
        """
        context = self.get_engagement(engagement_id)
        if context is None:
            return False

        if context.state not in (EngagementState.STOPPED, EngagementState.COMPLETED):
            raise InvalidStateTransition(
                engagement_id=engagement_id,
                from_state=str(context.state),
                to_state="REMOVED",
                message=(
                    f"Cannot remove engagement in {context.state} state. "
                    "Stop it first."
                ),
            )
        
        # Cleanup checkpoint if exists
        if self._checkpoint_manager:
            await self._checkpoint_manager.delete(engagement_id)

        del self._engagements[engagement_id]

        log.info(
            "engagement_removed",
            engagement_id=engagement_id,
        )

        return True

    def subscribe_to_engagement(
        self,
        engagement_id: str,
        callback: Callable,
    ) -> str:
        """Subscribe to engagement events for TUI streaming.

        Registers a callback to receive StreamEvent notifications for
        the specified engagement. Only RUNNING or PAUSED engagements
        can be subscribed to.

        Args:
            engagement_id: Engagement ID to subscribe to.
            callback: Callable that receives StreamEvent objects.

        Returns:
            Unique subscription ID for later unsubscription.

        Raises:
            EngagementNotFoundError: If engagement not found.
            InvalidStateTransition: If engagement not in RUNNING or PAUSED state.
        """
        context = self.get_engagement_or_raise(engagement_id)

        # Only allow subscription to RUNNING or PAUSED engagements
        if context.state not in (EngagementState.RUNNING, EngagementState.PAUSED):
            raise InvalidStateTransition(
                engagement_id=engagement_id,
                from_state=str(context.state),
                to_state="SUBSCRIBED",
                message=(
                    f"Cannot attach to engagement in {context.state} state. "
                    "Engagement must be RUNNING or PAUSED."
                ),
            )

        # Generate subscription ID
        subscription_id = f"sub-{secrets.token_hex(8)}"

        # Initialize subscription dict for this engagement if needed
        if engagement_id not in self._subscriptions:
            self._subscriptions[engagement_id] = {}

        self._subscriptions[engagement_id][subscription_id] = callback

        log.info(
            "subscription_created",
            engagement_id=engagement_id,
            subscription_id=subscription_id,
        )

        return subscription_id

    def unsubscribe_from_engagement(self, subscription_id: str) -> None:
        """Unsubscribe from engagement events.

        Removes a previously registered subscription. Safe to call
        even if subscription doesn't exist (no-op).

        Args:
            subscription_id: Subscription ID from subscribe_to_engagement.
        """
        # Find and remove subscription across all engagements
        for engagement_id, subs in list(self._subscriptions.items()):
            if subscription_id in subs:
                del subs[subscription_id]
                log.info(
                    "subscription_removed",
                    engagement_id=engagement_id,
                    subscription_id=subscription_id,
                )
                # Clean up empty subscription dicts
                if not subs:
                    del self._subscriptions[engagement_id]
                return

        # Subscription not found - no-op (graceful handling)
        log.debug("subscription_not_found", subscription_id=subscription_id)

    def broadcast_event(self, engagement_id: str, event: Any) -> int:
        """Broadcast an event to all subscribers of an engagement.

        Args:
            engagement_id: Engagement ID to broadcast to.
            event: StreamEvent to broadcast.

        Returns:
            Number of subscribers notified.
        """
        if engagement_id not in self._subscriptions:
            return 0

        subscribers = self._subscriptions[engagement_id]
        count = 0

        for sub_id, callback in list(subscribers.items()):
            try:
                callback(event)
                count += 1
            except Exception as e:
                log.warning(
                    "broadcast_callback_error",
                    engagement_id=engagement_id,
                    subscription_id=sub_id,
                    error=str(e),
                )
                # Remove broken callbacks
                del subscribers[sub_id]

        return count

    def get_subscription_count(self, engagement_id: str) -> int:
        """Get number of active subscriptions for an engagement.

        Args:
            engagement_id: Engagement ID to check.

        Returns:
            Number of active subscriptions.
        """
        if engagement_id not in self._subscriptions:
            return 0
        return len(self._subscriptions[engagement_id])

    # ─────────────────────────────────────────────────────────────────────────
    # Graceful Shutdown Methods (Story 2.11)
    # ─────────────────────────────────────────────────────────────────────────

    def pause_all_engagements(self) -> list[str]:
        """Pause all RUNNING engagements for graceful shutdown.

        Iterates all engagements and pauses those in RUNNING state.
        Continues on individual failures (logs error) to ensure maximum
        state preservation during shutdown.

        Returns:
            List of engagement IDs that were successfully paused.
        """
        paused_ids: list[str] = []

        for engagement_id, context in list(self._engagements.items()):
            if context.state == EngagementState.RUNNING:
                try:
                    self.pause_engagement(engagement_id)
                    paused_ids.append(engagement_id)
                except Exception as e:
                    log.error(
                        "pause_all_engagement_failed",
                        engagement_id=engagement_id,
                        error=str(e),
                    )
                    # Continue with remaining engagements

        log.info(
            "pause_all_completed",
            paused_count=len(paused_ids),
            paused_ids=paused_ids,
        )

        return paused_ids

    async def checkpoint_all_engagements(self) -> tuple[dict[str, Optional[Path]], list[str]]:
        """Checkpoint all PAUSED engagements to STOPPED for graceful shutdown.

        Iterates all engagements and stops (checkpoints) those in PAUSED state.
        Continues on individual failures (logs error) to ensure maximum
        state preservation during shutdown.

        Returns:
            Tuple of (checkpoint_paths, errors):
            - checkpoint_paths: Dict mapping engagement_id to checkpoint_path (None if no manager)
            - errors: List of error messages for failed checkpoints
        """
        checkpoint_paths: dict[str, Optional[Path]] = {}
        errors: list[str] = []

        for engagement_id, context in list(self._engagements.items()):
            if context.state == EngagementState.PAUSED:
                try:
                    _, checkpoint_path = await self.stop_engagement(engagement_id)
                    checkpoint_paths[engagement_id] = checkpoint_path
                except Exception as e:
                    log.error(
                        "checkpoint_all_engagement_failed",
                        engagement_id=engagement_id,
                        error=str(e),
                    )
                    errors.append(f"Checkpoint failed for {engagement_id}: {e}")
                    # Continue with remaining engagements

        log.info(
            "checkpoint_all_completed",
            checkpoint_count=len(checkpoint_paths),
            error_count=len(errors),
        )

        return checkpoint_paths, errors

    async def graceful_shutdown(self) -> "ShutdownResult":
        """Execute graceful shutdown sequence: pause all → checkpoint all.

        This is the main entry point for daemon graceful shutdown. It:
        1. Pauses all RUNNING engagements (fast, RAM-only)
        2. Checkpoints all PAUSED engagements to SQLite (cold state)

        Returns:
            ShutdownResult with paused IDs, checkpoint paths, and any errors.
        """
        # Step 1: Pause all running engagements
        paused_ids = self.pause_all_engagements()

        # Step 2: Checkpoint all paused engagements
        checkpoint_paths, errors = await self.checkpoint_all_engagements()

        log.info(
            "graceful_shutdown_complete",
            paused_count=len(paused_ids),
            checkpoint_count=len(checkpoint_paths),
            error_count=len(errors),
        )

        return ShutdownResult(
            paused_ids=paused_ids,
            checkpoint_paths=checkpoint_paths,
            errors=errors,
        )

    def notify_all_clients(self, event: Any) -> int:
        """Broadcast an event to all subscriptions across all engagements.

        Used during shutdown to notify all TUI clients of impending shutdown.

        Args:
            event: StreamEvent to broadcast to all clients.

        Returns:
            Total number of notifications sent.
        """
        total_count = 0
        broken_subs: list[tuple[str, str]] = []

        for engagement_id, subs in list(self._subscriptions.items()):
            for sub_id, callback in list(subs.items()):
                try:
                    callback(event)
                    total_count += 1
                except Exception as e:
                    log.warning(
                        "notify_all_callback_error",
                        engagement_id=engagement_id,
                        subscription_id=sub_id,
                        error=str(e),
                    )
                    broken_subs.append((engagement_id, sub_id))

        # Remove broken callbacks
        for engagement_id, sub_id in broken_subs:
            if engagement_id in self._subscriptions:
                self._subscriptions[engagement_id].pop(sub_id, None)

        log.info(
            "notify_all_clients_complete",
            notifications_sent=total_count,
            broken_removed=len(broken_subs),
        )

        return total_count

    def disconnect_all_clients(self) -> int:
        """Disconnect all client subscriptions.

        Clears all subscriptions across all engagements. Used during
        shutdown after notifications have been sent.

        Returns:
            Total number of subscriptions cleared.
        """
        total_count = sum(len(subs) for subs in self._subscriptions.values())

        self._subscriptions.clear()

        log.info(
            "disconnect_all_clients_complete",
            subscriptions_cleared=total_count,
        )

        return total_count


@dataclass
class ShutdownResult:
    """Result of graceful shutdown operation.

    Attributes:
        paused_ids: List of engagement IDs that were paused.
        checkpoint_paths: Dict mapping engagement_id to checkpoint path (None if failed).
        errors: List of error messages from shutdown process.
    """

    paused_ids: list[str]
    checkpoint_paths: dict[str, Optional[Path]]
    errors: list[str]

