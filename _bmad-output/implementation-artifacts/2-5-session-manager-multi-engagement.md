# Story 2.5: Session Manager (Multi-Engagement)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **to run multiple concurrent engagements**,
So that **I can manage several targets simultaneously (NFR34)**.

## Acceptance Criteria

1. **Given** Stories 2.3 and 2.4 are complete
2. **When** I start multiple engagements
3. **Then** session manager tracks all engagements by ID
4. **And** `sessions.list` returns all engagements with state, agent count, finding count
5. **And** engagements are isolated (no cross-engagement state leakage)
6. **And** resource limits prevent over-allocation
7. **And** integration tests verify multi-engagement isolation

## Tasks / Subtasks

> [!IMPORTANT]
> **MULTI-ENGAGEMENT ORCHESTRATION — Uses EngagementStateMachine (Story 2.4) and integrates with DaemonServer (Story 2.3)**

### Phase 1: Session Manager Core

- [x] Task 1: Create SessionManager class (AC: #3) <!-- id: 0 -->
  - [x] Create `src/cyberred/daemon/session_manager.py`
  - [x] Define `SessionManager` class with `_engagements: dict[str, EngagementContext]`
  - [x] Define `EngagementContext` dataclass holding:
    - `id: str` — Unique engagement identifier
    - `state_machine: EngagementStateMachine` — Lifecycle from Story 2.4
    - `config_path: Path` — Source engagement config
    - `created_at: datetime` — Creation timestamp
    - `agent_count: int` — Current active agent count (placeholder for Epic 7)
    - `finding_count: int` — Current finding count (placeholder for Epic 7)
  - [x] Add `__init__(self, max_engagements: int = 10)` with configurable limit
  - [x] Use `structlog` for all logging with `engagement_id` context binding

- [x] Task 2: Implement engagement ID generation (AC: #3) <!-- id: 1 -->
  - [x] Add `_generate_id(name: str) -> str` private method
  - [x] Format: `{name}-{YYYYMMDD-HHMMSS}` (e.g., `ministry-20260102-143022`)
  - [x] Validate name contains only `[a-z0-9-]` characters
  - [x] Add `validate_engagement_name(name: str) -> bool` utility function
  - [x] Raise `ConfigurationError` if name is invalid

### Phase 2: Engagement Lifecycle Operations

- [x] Task 3: Implement create_engagement method (AC: #2, #3) <!-- id: 2 -->
  - [x] Add `create_engagement(config_path: Path) -> str` method
  - [x] Parse engagement name from config (YAML) or fallback to filename stem
  - [x] Generate unique engagement ID
  - [x] Create `EngagementStateMachine` (starts in `INITIALIZING`)
  - [x] Create `EngagementContext` and add to `_engagements` dict
  - [x] Check `max_engagements` limit, raise `ResourceLimitError` if exceeded
  - [x] Log engagement creation with `engagement_id` and `config_path`
  - [x] Return the generated engagement ID

- [x] Task 4: Implement get_engagement method (AC: #3) <!-- id: 3 -->
  - [x] Add `get_engagement(engagement_id: str) -> Optional[EngagementContext]`
  - [x] Return `None` if engagement not found (don't raise)
  - [x] Add `get_engagement_or_raise(engagement_id: str) -> EngagementContext`
  - [x] Raise `EngagementNotFoundError` if not found (new exception)

- [x] Task 5: Implement list_engagements method (AC: #4) <!-- id: 4 -->
  - [x] Add `list_engagements() -> list[EngagementSummary]`
  - [x] Define `EngagementSummary` dataclass with: `id`, `state`, `agent_count`, `finding_count`, `created_at`
  - [x] Convert each `EngagementContext` to `EngagementSummary`
  - [x] Sort by `created_at` (newest first)

### Phase 3: State Transition Operations

- [x] Task 6: Implement start_engagement method (AC: #2) <!-- id: 5 -->
  - [x] Add `start_engagement(engagement_id: str) -> EngagementState`
  - [x] Get engagement context, raise `EngagementNotFoundError` if missing
  - [x] Call `state_machine.start()` to transition INITIALIZING → RUNNING
  - [x] Return new state
  - [x] Log state transition

- [x] Task 7: Implement pause_engagement method <!-- id: 6 -->
  - [x] Add `pause_engagement(engagement_id: str) -> EngagementState`
  - [x] Get engagement context, call `state_machine.pause()`
  - [x] Return new state (PAUSED)
  - [x] Log state transition

- [x] Task 8: Implement resume_engagement method <!-- id: 7 -->
  - [x] Add `resume_engagement(engagement_id: str) -> EngagementState`
  - [x] Get engagement context, call `state_machine.resume()`
  - [x] Return new state (RUNNING)
  - [x] Log state transition

- [x] Task 9: Implement stop_engagement method <!-- id: 8 -->
  - [x] Add `stop_engagement(engagement_id: str) -> EngagementState`
  - [x] Get engagement context, call `state_machine.stop()`
  - [x] Return new state (STOPPED)
  - [x] Log state transition

- [x] Task 10: Implement remove_engagement method <!-- id: 9 -->
  - [x] Add `remove_engagement(engagement_id: str) -> bool`
  - [x] Only allow removal if state is STOPPED or COMPLETED
  - [x] Raise `InvalidStateTransition` if attempted on RUNNING/PAUSED/INITIALIZING engagement
  - [x] Remove from `_engagements` dict
  - [x] Return `True` on success, `False` if not found

- [x] Task 10b: Implement complete_engagement method <!-- id: 9b -->
  - [x] Add `complete_engagement(engagement_id: str) -> EngagementState`
  - [x] Get engagement context, call `state_machine.complete()`
  - [x] Return new state (COMPLETED)
  - [x] Log state transition

### Phase 4: Isolation & Resource Limits

- [x] Task 11: Implement isolation guarantees (AC: #5) <!-- id: 10 -->
  - [x] Each engagement gets its own `EngagementStateMachine` instance
  - [x] No shared mutable state between engagements in SessionManager
  - [x] `EngagementContext` is a frozen/immutable dataclass for ID and timestamps
  - [x] Add `@dataclass(frozen=True)` for `EngagementSummary`
  - [x] Add property `is_active` to `EngagementContext` (INITIALIZING, RUNNING, or PAUSED states)

- [x] Task 12: Implement resource limits (AC: #6) <!-- id: 11 -->
  - [x] Add `ResourceLimitError` exception to `core/exceptions.py`
  - [x] Add `EngagementNotFoundError` exception to `core/exceptions.py`
  - [x] Enforce `max_engagements` limit in `create_engagement()`
  - [x] Count only active engagements (not STOPPED/COMPLETED) against limit
  - [x] Add `active_count` property to SessionManager
  - [x] Add `remaining_capacity` property to SessionManager

### Phase 5: DaemonServer Integration

- [x] Task 13: Wire SessionManager into DaemonServer (AC: #4) <!-- id: 12 -->
  - [x] Add `session_manager: SessionManager` attribute to `DaemonServer`
  - [x] Initialize in `DaemonServer.__init__()` with default `max_engagements=10`
  - [x] Update `_handle_command()` to delegate to `session_manager`:
    - `SESSIONS_LIST` → `session_manager.list_engagements()`
    - `ENGAGEMENT_START` → Create and start engagement, return ID and state
    - `ENGAGEMENT_PAUSE` → `session_manager.pause_engagement()`
    - `ENGAGEMENT_RESUME` → `session_manager.resume_engagement()`
    - `ENGAGEMENT_STOP` → `session_manager.stop_engagement()`
  - [x] Convert `EngagementSummary` list to JSON-serializable dict for response
  - [x] Update `daemon/__init__.py` to export `SessionManager`, `EngagementContext`, `EngagementSummary`

### Phase 6: Testing

- [x] Task 14: Create unit tests for SessionManager (AC: #7) <!-- id: 13 -->
  - [x] Create `tests/unit/daemon/test_session_manager.py`
  - [x] Test `create_engagement` creates engagement in INITIALIZING state
  - [x] Test `start_engagement` transitions to RUNNING
  - [x] Test `complete_engagement` transitions STOPPED to COMPLETED
  - [x] Test `list_engagements` returns all engagements with correct fields
  - [x] Test `pause_engagement`, `resume_engagement`, `stop_engagement`
  - [x] Test `remove_engagement` only works on STOPPED/COMPLETED
  - [x] Test engagement ID generation format
  - [x] Test invalid engagement name raises `ConfigurationError`
  - [x] Test empty engagement name raises `ConfigurationError`
  - [x] Test `max_engagements` limit raises `ResourceLimitError` (includes INITIALIZING state)
  - [x] Test `active_count` and `remaining_capacity` properties
  - [x] Test duplicate engagement ID handling (if same timestamp)
  - [x] Achieve 100% coverage on `daemon/session_manager.py`

- [x] Task 15: Create integration tests for multi-engagement isolation (AC: #5, #7) <!-- id: 14 -->
  - [x] Create `tests/integration/daemon/test_session_manager_integration.py`
  - [x] Test multiple concurrent engagements run independently
  - [x] Test state change in one engagement doesn't affect others
  - [x] Test resource limit prevents over-allocation
  - [x] Test DaemonServer correctly routes IPC commands to SessionManager

- [x] Task 16: Run full test suite <!-- id: 15 -->
  - [x] Run `pytest tests/unit/daemon/test_session_manager.py -v`
  - [x] Run `pytest --cov=src/cyberred/daemon/session_manager --cov-report=term-missing`
  - [x] Verify 100% coverage on `daemon/session_manager.py`
  - [x] Verify no test regressions (full suite green)

## Dev Notes

### Architecture Context

This story implements the Session Manager per architecture (lines 381-400, 769-774):

```
src/cyberred/daemon/
├── __init__.py
├── ipc.py           # Story 2.2: IPCRequest, IPCResponse, protocol (DONE)
├── server.py        # Story 2.3: Unix socket server (DONE)
├── state_machine.py # Story 2.4: Engagement lifecycle (DONE)
└── session_manager.py  # ← THIS STORY: Multi-engagement management
```

**From Architecture — Daemon Execution Model (lines 381-400):**

```
┌─────────────────────────────────────────────────────────────────┐
│                     CYBER-RED DAEMON (background)                │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    SESSION MANAGER                          │ │
│  │                                                             │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌────────────┐  │ │
│  │  │ Engagement 1    │  │ Engagement 2    │  │ Engagement 3│  │ │
│  │  │ State: RUNNING  │  │ State: PAUSED   │  │ State: STOP │  │ │
│  │  │ Agents: 847     │  │ Agents: 0 (sus) │  │ Agents: 0   │  │ │
│  │  │ Findings: 23    │  │ Findings: 156   │  │ Findings: 89│  │ │
│  │  └─────────────────┘  └─────────────────┘  └────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**From Architecture — Architectural Boundaries (lines 983-984):**
> "**Daemon ↔ Engagements** | Session manager isolates engagements. No cross-engagement state leakage"

### Engagement ID Format

Per architecture and NFR34, engagement IDs follow the format:
```
{name}-{YYYYMMDD-HHMMSS}
```

Examples:
- `ministry-20260102-143022`
- `acme-corp-20260115-091500`
- `pentest-q1-20260301-120000`

### Implementation Pattern

```python
# src/cyberred/daemon/session_manager.py
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import re

import structlog
import yaml

from cyberred.core.exceptions import (
    ConfigurationError,
    EngagementNotFoundError,
    ResourceLimitError,
)
from cyberred.daemon.state_machine import (
    EngagementState,
    EngagementStateMachine,
)


log = structlog.get_logger()

# Valid engagement name pattern: lowercase letters, numbers, hyphens
ENGAGEMENT_NAME_PATTERN = re.compile(r"^[a-z0-9-]+$")


def validate_engagement_name(name: str) -> bool:
    """Validate engagement name contains only allowed characters.
    
    Args:
        name: Engagement name to validate.
        
    Returns:
        True if valid, False otherwise.
    """
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
        """Check if engagement is active (INITIALIZING, RUNNING, or PAUSED)."""
        return self.state in (
            EngagementState.INITIALIZING,
            EngagementState.RUNNING,
            EngagementState.PAUSED,
        )


@dataclass(frozen=True)
class EngagementSummary:
    """Summary of an engagement for listing.
    
    Immutable dataclass for external consumption.
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
    
    def __init__(self, max_engagements: int = 10) -> None:
        """Initialize SessionManager.
        
        Args:
            max_engagements: Maximum concurrent active engagements (default: 10).
        """
        self._max_engagements = max_engagements
        self._engagements: dict[str, EngagementContext] = {}
        
    @property
    def max_engagements(self) -> int:
        """Maximum allowed concurrent active engagements."""
        return self._max_engagements
        
    @property
    def active_count(self) -> int:
        """Count of currently active engagements (RUNNING or PAUSED)."""
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
            Unique ID in format: {name}-{YYYYMMDD-HHMMSS}
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return f"{name}-{timestamp}"
    
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
        # Check capacity BEFORE creating
        if self.active_count >= self._max_engagements:
            raise ResourceLimitError(
                f"Maximum active engagements ({self._max_engagements}) reached. "
                "Stop or complete an existing engagement to create a new one."
            )
        
        if not config_path.exists():
            raise FileNotFoundError(f"Engagement config not found: {config_path}")
            
        # Parse name from config or use filename stem
        try:
            with config_path.open() as f:
                config = yaml.safe_load(f) or {}
            name = config.get("name", config_path.stem).lower()
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {config_path}: {e}")
        
        # Validate name
        if not validate_engagement_name(name):
            raise ConfigurationError(
                f"Invalid engagement name '{name}'. "
                "Name must contain only lowercase letters, numbers, and hyphens."
            )
        
        # Generate ID and create context
        engagement_id = self._generate_id(name)
        state_machine = EngagementStateMachine(engagement_id)
        context = EngagementContext(
            id=engagement_id,
            state_machine=state_machine,
            config_path=config_path,
        )
        
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
    
    def start_engagement(self, engagement_id: str) -> EngagementState:
        """Start an engagement (INITIALIZING → RUNNING).
        
        Args:
            engagement_id: Engagement ID to start.
            
        Returns:
            New state (RUNNING).
            
        Raises:
            EngagementNotFoundError: If engagement not found.
            InvalidStateTransition: If not in INITIALIZING state.
        """
        context = self.get_engagement_or_raise(engagement_id)
        context.state_machine.start()
        
        log.info(
            "engagement_started",
            engagement_id=engagement_id,
            state=str(context.state),
        )
        
        return context.state
    
    def pause_engagement(self, engagement_id: str) -> EngagementState:
        """Pause an engagement (RUNNING → PAUSED).
        
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
    
    def stop_engagement(self, engagement_id: str) -> EngagementState:
        """Stop an engagement (RUNNING/PAUSED → STOPPED).
        
        Args:
            engagement_id: Engagement ID to stop.
            
        Returns:
            New state (STOPPED).
            
        Raises:
            EngagementNotFoundError: If engagement not found.
            InvalidStateTransition: If not in RUNNING or PAUSED state.
        """
        context = self.get_engagement_or_raise(engagement_id)
        context.state_machine.stop()
        
        log.info(
            "engagement_stopped",
            engagement_id=engagement_id,
            state=str(context.state),
        )
        
        return context.state
    
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
    
    def remove_engagement(self, engagement_id: str) -> bool:
        """Remove an engagement from tracking.
        
        Only STOPPED or COMPLETED engagements can be removed.
        
        Args:
            engagement_id: Engagement ID to remove.
            
        Returns:
            True if removed, False if not found.
            
        Raises:
            InvalidStateTransition: If engagement is RUNNING, PAUSED, or INITIALIZING.
        """
        context = self.get_engagement(engagement_id)
        if context is None:
            return False
            
        if context.state not in (EngagementState.STOPPED, EngagementState.COMPLETED):
            from cyberred.core.exceptions import InvalidStateTransition
            raise InvalidStateTransition(
                engagement_id=engagement_id,
                from_state=str(context.state),
                to_state="REMOVED",
                message=f"Cannot remove engagement in {context.state} state. Stop it first.",
            )
        
        del self._engagements[engagement_id]
        
        log.info(
            "engagement_removed",
            engagement_id=engagement_id,
        )
        
        return True
```

### Exception Patterns (for exceptions.py)

```python
class ResourceLimitError(CyberRedError):
    """Resource limit exceeded.
    
    Raised when attempting to allocate resources beyond configured limits,
    such as exceeding maximum concurrent engagements.
    """
    pass


class EngagementNotFoundError(CyberRedError):
    """Engagement not found.
    
    Raised when attempting to operate on an engagement that doesn't exist.
    
    Attributes:
        engagement_id: The ID that was not found.
    """
    
    def __init__(self, engagement_id: str, message: Optional[str] = None) -> None:
        self.engagement_id = engagement_id
        if message is None:
            message = f"Engagement not found: {engagement_id}"
        super().__init__(message)
    
    def context(self) -> dict[str, Any]:
        """Return context for engagement not found."""
        return {"engagement_id": self.engagement_id}
```

### DaemonServer Integration Pattern

Update `_handle_command()` in `server.py`:

```python
def _handle_command(self, request: IPCRequest) -> IPCResponse:
    """Route and handle IPC command."""
    try:
        match request.command:
            case IPCCommand.SESSIONS_LIST:
                summaries = self.session_manager.list_engagements()
                return IPCResponse(
                    request_id=request.request_id,
                    success=True,
                    data={
                        "engagements": [
                            {
                                "id": s.id,
                                "state": s.state,
                                "agent_count": s.agent_count,
                                "finding_count": s.finding_count,
                                "created_at": s.created_at.isoformat(),
                            }
                            for s in summaries
                        ]
                    },
                )
            
            case IPCCommand.ENGAGEMENT_START:
                config_path = Path(request.params.get("config_path", ""))
                engagement_id = self.session_manager.create_engagement(config_path)
                new_state = self.session_manager.start_engagement(engagement_id)
                return IPCResponse(
                    request_id=request.request_id,
                    success=True,
                    data={"id": engagement_id, "state": str(new_state)},
                )
            
            # ... other cases
```

### Dependencies

**Required (no new dependencies):**
- `datetime` (stdlib) — Timestamps
- `pathlib` (stdlib) — Config paths
- `re` (stdlib) — Name validation
- `yaml` (existing) — Config parsing
- `structlog` (existing) — Logging

**Internal dependencies:**
- `cyberred.daemon.state_machine` — `EngagementStateMachine`, `EngagementState`
- `cyberred.core.exceptions` — `ConfigurationError`, `InvalidStateTransition` + new exceptions

### Previous Story Intelligence

**From Story 2.4 (Engagement State Machine):**
- `EngagementStateMachine` class with strict state transitions
- States: `INITIALIZING`, `RUNNING`, `PAUSED`, `STOPPED`, `COMPLETED`
- Convenience methods: `start()`, `pause()`, `resume()`, `stop()`, `complete()`
- Listener support for state change notifications
- Located in `daemon/state_machine.py`

**From Story 2.3 (Unix Socket Server):**
- `DaemonServer` class with `_handle_command()` for IPC routing
- IPC commands: `SESSIONS_LIST`, `ENGAGEMENT_START`, `ENGAGEMENT_PAUSE`, etc.
- Uses `get_settings().storage.base_path` for paths
- Currently has placeholder implementations returning "Not implemented"

**From Story 2.2 (IPC Protocol):**
- `IPCCommand` StrEnum with all command types
- `IPCRequest` and `IPCResponse` dataclasses
- JSON serialization via `encode_message()`/`decode_message()`

### Anti-Patterns to Avoid

1. **NEVER** share mutable state between engagements — each gets own state machine
2. **NEVER** allow removal of active engagements — must be STOPPED/COMPLETED first
3. **NEVER** bypass `max_engagements` limit — always check before create
4. **NEVER** allow invalid engagement names — validate before creating
5. **NEVER** expose internal `_engagements` dict directly — use accessor methods
6. **NEVER** modify `EngagementContext` after creation — use immutable for summaries
7. **NEVER** assume config file exists — always check and raise `FileNotFoundError`

### Test Pattern

```python
# tests/unit/daemon/test_session_manager.py
import pytest
from pathlib import Path
from datetime import datetime

from cyberred.daemon.session_manager import (
    SessionManager,
    EngagementContext,
    EngagementSummary,
    validate_engagement_name,
)
from cyberred.daemon.state_machine import EngagementState
from cyberred.core.exceptions import (
    ConfigurationError,
    EngagementNotFoundError,
    InvalidStateTransition,
    ResourceLimitError,
)


class TestEngagementNameValidation:
    def test_valid_names(self) -> None:
        assert validate_engagement_name("ministry") is True
        assert validate_engagement_name("acme-corp") is True
        assert validate_engagement_name("pentest-2026") is True
        assert validate_engagement_name("test-123-abc") is True
    
    def test_invalid_names(self) -> None:
        assert validate_engagement_name("Ministry") is False  # uppercase
        assert validate_engagement_name("test_name") is False  # underscore
        assert validate_engagement_name("test name") is False  # space
        assert validate_engagement_name("test.name") is False  # dot


class TestSessionManager:
    def test_create_engagement_starts_initializing(self, tmp_path: Path) -> None:
        config = tmp_path / "test.yaml"
        config.write_text("name: test-engagement\n")
        
        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        
        context = manager.get_engagement(engagement_id)
        assert context is not None
        assert context.state == EngagementState.INITIALIZING
    
    def test_max_engagements_limit(self, tmp_path: Path) -> None:
        manager = SessionManager(max_engagements=2)
        
        # Create 2 engagements and start them
        for i in range(2):
            config = tmp_path / f"config{i}.yaml"
            config.write_text(f"name: test{i}\n")
            eid = manager.create_engagement(config)
            manager.start_engagement(eid)
        
        # Third should raise
        config = tmp_path / "config2.yaml"
        config.write_text("name: test2\n")
        with pytest.raises(ResourceLimitError):
            manager.create_engagement(config)
    
    def test_list_engagements_returns_summaries(self, tmp_path: Path) -> None:
        config = tmp_path / "test.yaml"
        config.write_text("name: test\n")
        
        manager = SessionManager()
        engagement_id = manager.create_engagement(config)
        manager.start_engagement(engagement_id)
        
        summaries = manager.list_engagements()
        assert len(summaries) == 1
        assert summaries[0].id == engagement_id
        assert summaries[0].state == "RUNNING"
```

### Project Structure Notes

- Creates `daemon/session_manager.py` in existing `src/cyberred/daemon/` package
- Aligns with architecture project structure (line 773)
- Adds `ResourceLimitError` and `EngagementNotFoundError` to exception hierarchy
- Unit tests go in `tests/unit/daemon/test_session_manager.py`
- Integration tests go in `tests/integration/test_session_manager.py`

### References

- [Architecture: Daemon Execution Model](file:///root/red/docs/3-solutioning/architecture.md#L365-L400)
- [Architecture: Session Manager Diagram](file:///root/red/docs/3-solutioning/architecture.md#L381-L391)
- [Architecture: Daemon Structure](file:///root/red/docs/3-solutioning/architecture.md#L769-L774)
- [Architecture: Daemon ↔ Engagements Boundary](file:///root/red/docs/3-solutioning/architecture.md#L983-L984)
- [Epics: Story 2.5](file:///root/red/docs/3-solutioning/epics-stories.md#L1183-L1203)
- [Previous: Story 2.4 Engagement State Machine](file:///root/red/_bmad-output/implementation-artifacts/2-4-engagement-state-machine.md)
- [Previous: Story 2.3 Unix Socket Server](file:///root/red/_bmad-output/implementation-artifacts/2-3-unix-socket-server.md)

## Dev Agent Record

### Agent Model Used

Antigravity (Google DeepMind Advanced Agentic Coding)

### Debug Log References

None required - all tests pass.

### Completion Notes List

- Implemented full SessionManager class with multi-engagement orchestration
- Added `ResourceLimitError` and `EngagementNotFoundError` to exception hierarchy
- Integrated SessionManager into DaemonServer for real IPC command handling
- All lifecycle methods work: create, start, pause, resume, stop, complete, remove
- Resource limits properly enforce max_engagements (counting INITIALIZING as active)
- 54 unit tests for session_manager.py (100% coverage)
- 9 integration tests for multi-engagement isolation via IPC
- Fixed 5 existing server tests to use new engagement lifecycle
- Full test suite passes: 647 passed, 54 skipped

### File List

- `src/cyberred/daemon/session_manager.py` — NEW: SessionManager, EngagementContext, EngagementSummary
- `src/cyberred/daemon/__init__.py` — MODIFIED: Added SessionManager exports
- `src/cyberred/daemon/server.py` — MODIFIED: Integrated SessionManager, real command handling
- `src/cyberred/core/exceptions.py` — MODIFIED: Added ResourceLimitError, EngagementNotFoundError
- `tests/unit/daemon/test_session_manager.py` — NEW: 54 unit tests
- `tests/integration/daemon/test_session_manager_integration.py` — NEW: 9 integration tests
- `tests/unit/daemon/test_server.py` — MODIFIED: Updated 5 tests for new parameter names
- `tests/integration/daemon/test_server_integration.py` — MODIFIED: Updated 1 test for lifecycle

## Review Findings (2026-01-02)

### Critical Issues Fixed
1. **Engagement ID Collision**: Fixed by adding random 6-char hex suffix to ID generation.
   - Verified by `test_create_engagement_id_unique_rapid_calls`
2. **Daemon Zombie State**: Fixed by adding `shutdown_callback` to `DaemonServer` to signal main loop exit on `DAEMON_STOP`.
   - Verified by `test_daemon_stop_command`

### Medium Issues Fixed
1. **Unbounded Memory**: Fixed by implementing `max_history` (default 50) pruning strategy for stopped/completed engagements.
   - Verified by `TestSessionManagerHistoryPruning`

All tests passed with 100% coverage (within module scope).
