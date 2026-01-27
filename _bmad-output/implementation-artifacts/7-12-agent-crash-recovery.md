# Story 7.12: Agent Crash Recovery

Status: review

## Story

As a **developer**,
I want **crashed agents to be replaced without losing context**,
So that **engagement continues despite individual failures (ERR5)**.

## Acceptance Criteria

1. **Given** Stories 7.1-7.5 are complete
   - **When** agent process crashes
   - **Then** worker pool detects crash within 30s

2. **Given** an agent crash is detected
   - **When** replacement is needed
   - **Then** replacement agent is spawned with same role and engagement context

3. **Given** a crashed agent had in-progress work
   - **When** replacement agent starts
   - **Then** replacement loads last checkpoint (task, context, findings)

4. **Given** checkpoint data is available
   - **When** replacement agent initializes
   - **Then** replacement resumes from checkpoint state

5. **Given** any agent crash occurs
   - **When** crash is detected
   - **Then** crash is logged with full stack trace

6. **Given** crash recovery system is operational
   - **When** safety tests run
   - **Then** safety tests verify crash recovery works correctly

## Tasks / Subtasks

- [x] Task 1: Create AgentCrashMonitor class (AC: 1)
  - [x] 1.1 Create `src/cyberred/orchestration/crash_monitor.py` module
  - [x] 1.2 Implement crash detection with 30s timeout via heartbeat mechanism
  - [x] 1.3 Track agent health state (healthy, suspected, crashed)
  - [x] 1.4 Subscribe to agent heartbeat events via EventBus

- [x] Task 2: Implement agent heartbeat system (AC: 1)
  - [x] 2.1 Add `send_heartbeat()` method to StigmergicAgent base class
  - [x] 2.2 Add periodic heartbeat task (every 10s) in agent spawn lifecycle
  - [x] 2.3 Include agent_id, engagement_id, task_id in heartbeat payload
  - [x] 2.4 Clean shutdown cancels heartbeat task

- [x] Task 3: Implement checkpoint save on agent state changes (AC: 3, 4)
  - [x] 3.1 Add `save_checkpoint()` method to StigmergicAgent
  - [x] 3.2 Save checkpoint every 60s or on major state change (per story spec)
  - [x] 3.3 Checkpoint includes: agent_id, task_assignment, accumulated context, findings
  - [x] 3.4 Use existing CheckpointManager and AgentState dataclass

- [x] Task 4: Implement agent replacement spawning (AC: 2, 4)
  - [x] 4.1 Add `replace_agent()` method to DynamicSpawner
  - [x] 4.2 Replacement inherits: agent_id, task_assignment, accumulated context
  - [x] 4.3 Load checkpoint data via CheckpointManager.load_agent_state()
  - [x] 4.4 Initialize replacement with restored state via `restore_from_checkpoint()`

- [x] Task 5: Implement crash logging (AC: 5)
  - [x] 5.1 Log crash with full stack trace via structlog
  - [x] 5.2 Publish crash event to EventBus (`agent:crashed` channel)
  - [x] 5.3 Include crash metadata: agent_id, last_action, crash_time, error_info

- [x] Task 6: Write unit tests (AC: 1-5)
  - [x] 6.1 Test crash detection within 30s timeout
  - [x] 6.2 Test replacement agent spawning
  - [x] 6.3 Test checkpoint save/restore cycle
  - [x] 6.4 Test crash logging with full trace
  - [x] 6.5 Test heartbeat mechanism

- [x] Task 7: Write integration tests (AC: 6)
  - [x] 7.1 Test end-to-end crash → detect → replace → resume flow
  - [x] 7.2 Test checkpoint persistence across simulated crashes
  - [x] 7.3 Test multiple concurrent agent crashes

- [x] Task 8: Write safety tests (AC: 6)
  - [x] 8.1 Add test to `tests/safety/` for crash recovery validation
  - [x] 8.2 Verify engagement continues after agent crash
  - [x] 8.3 Verify no data loss from crash recovery

## Dev Notes

### Architecture Patterns and Constraints

**Error Handling (ERR5 from architecture):**
- Per `_bmad-output/planning-artifacts/architecture.md`: "Log crash, spawn replacement, resume from checkpoint"
- Agent crash is a recoverable error - engagement MUST continue
- Checkpoint provides cold storage for agent state recovery

**Existing Components to Leverage:**

1. **CheckpointManager** (`src/cyberred/storage/checkpoint.py`):
   - Already has `AgentState` dataclass with: `agent_id`, `agent_type`, `state`, `last_action_id`, `decision_context`
   - `CheckpointData.agents: list[AgentState]` already exists
   - Use `save()` and `load()` methods for persistence

2. **DynamicSpawner** (`src/cyberred/orchestration/spawner.py`):
   - Manages `_active_agents: list[StigmergicAgent]`
   - Has `scale_up()` pattern to follow for `replace_agent()`
   - Integrates with SwarmRouter for agent creation

3. **StigmergicAgent** (`src/cyberred/agents/base.py`):
   - Base class for all agents - add heartbeat and checkpoint methods here
   - Has `_status` attribute for state tracking
   - Has `_decision_context` list that must be preserved

4. **EventBus** (`src/cyberred/core/events.py`):
   - Use for heartbeat pub/sub and crash notifications
   - Pattern: `agent:{agent_id}:heartbeat` for heartbeats
   - Pattern: `agent:crashed` for crash notifications

### Implementation Approach

```python
# New module: src/cyberred/orchestration/crash_monitor.py

from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Optional, Callable, Awaitable
import asyncio
import structlog

from cyberred.core.events import EventBus
from cyberred.storage.checkpoint import CheckpointManager, AgentState

log = structlog.get_logger()

CRASH_DETECTION_TIMEOUT_S = 30  # Per story spec
HEARTBEAT_INTERVAL_S = 10  # 3 missed heartbeats = crash


@dataclass
class AgentHealthState:
    """Track agent health for crash detection."""
    agent_id: str
    engagement_id: str
    last_heartbeat: datetime
    status: str = "healthy"  # healthy, suspected, crashed
    task_id: Optional[str] = None
    consecutive_misses: int = 0


class AgentCrashMonitor:
    """Monitor agent health and trigger replacement on crash.
    
    Implements ERR5: "Log crash, spawn replacement, resume from checkpoint"
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        checkpoint_manager: CheckpointManager,
        on_crash_callback: Callable[[str, str], Awaitable[None]],
    ) -> None:
        self._event_bus = event_bus
        self._checkpoint_manager = checkpoint_manager
        self._on_crash = on_crash_callback
        self._agents: dict[str, AgentHealthState] = {}
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start monitoring agent health."""
        await self._event_bus.subscribe("agent:*:heartbeat", self._handle_heartbeat)
        self._monitor_task = asyncio.create_task(self._monitor_loop())
    
    async def stop(self) -> None:
        """Stop monitoring."""
        if self._monitor_task:
            self._monitor_task.cancel()
    
    async def register_agent(self, agent_id: str, engagement_id: str) -> None:
        """Register new agent for monitoring."""
        self._agents[agent_id] = AgentHealthState(
            agent_id=agent_id,
            engagement_id=engagement_id,
            last_heartbeat=datetime.now(UTC),
        )
    
    async def _handle_heartbeat(self, channel: str, data: dict) -> None:
        """Process agent heartbeat."""
        agent_id = data.get("agent_id")
        if agent_id and agent_id in self._agents:
            state = self._agents[agent_id]
            state.last_heartbeat = datetime.now(UTC)
            state.status = "healthy"
            state.consecutive_misses = 0
            state.task_id = data.get("task_id")
    
    async def _monitor_loop(self) -> None:
        """Periodic health check loop."""
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)
            await self._check_all_agents()
    
    async def _check_all_agents(self) -> None:
        """Check health of all registered agents."""
        now = datetime.now(UTC)
        for agent_id, state in list(self._agents.items()):
            elapsed = (now - state.last_heartbeat).total_seconds()
            
            if elapsed > CRASH_DETECTION_TIMEOUT_S:
                state.status = "crashed"
                log.error(
                    "agent_crash_detected",
                    agent_id=agent_id,
                    engagement_id=state.engagement_id,
                    last_heartbeat=state.last_heartbeat.isoformat(),
                    elapsed_seconds=elapsed,
                )
                await self._on_crash(agent_id, state.engagement_id)
                del self._agents[agent_id]
```

### StigmergicAgent Extensions

```python
# Add to src/cyberred/agents/base.py

class StigmergicAgent(Agent):
    # ... existing code ...
    
    async def spawn(self):
        """Initialize async components and subscriptions."""
        await self._setup_subscriptions()
        await self._start_throttle_monitor()
        await self._start_heartbeat()  # NEW
        self._status = "active"
        self._log.info("agent_spawned", status="active")
    
    async def _start_heartbeat(self) -> None:
        """Start periodic heartbeat task."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    async def _heartbeat_loop(self) -> None:
        """Send heartbeat every 10s."""
        while True:
            await asyncio.sleep(10)
            await self.send_heartbeat()
    
    async def send_heartbeat(self) -> None:
        """Send heartbeat to crash monitor."""
        await self.event_bus.publish(
            f"agent:{self.agent_id}:heartbeat",
            {
                "agent_id": self.agent_id,
                "engagement_id": self.engagement_id,
                "task_id": getattr(self, "_current_task_id", None),
                "status": self._status,
            }
        )
    
    async def save_checkpoint(self, checkpoint_manager: "CheckpointManager") -> None:
        """Save agent state to checkpoint for crash recovery."""
        state = AgentState(
            agent_id=self.agent_id,
            agent_type=self.role.value,
            state={
                "specialty": self.specialty,
                "status": self._status,
                "tool_help_cache": self._tool_help_cache,
                "current_task_id": getattr(self, "_current_task_id", None),
            },
            last_action_id=getattr(self, "_last_action_id", None),
            decision_context=",".join(self._decision_context) if self._decision_context else None,
        )
        await checkpoint_manager.save_agent_state(self.engagement_id, state)
    
    async def restore_from_checkpoint(self, agent_state: AgentState) -> None:
        """Restore agent state from checkpoint."""
        self._status = agent_state.state.get("status", "active")
        self._tool_help_cache = agent_state.state.get("tool_help_cache", {})
        self._current_task_id = agent_state.state.get("current_task_id")
        self._last_action_id = agent_state.last_action_id
        if agent_state.decision_context:
            self._decision_context = agent_state.decision_context.split(",")
        self._log.info("agent_restored_from_checkpoint", last_action=self._last_action_id)
```

### DynamicSpawner Extensions

```python
# Add to src/cyberred/orchestration/spawner.py

async def replace_agent(
    self,
    crashed_agent_id: str,
    engagement_id: str,
    checkpoint_manager: CheckpointManager,
) -> Optional[StigmergicAgent]:
    """Replace crashed agent with checkpoint restoration.
    
    Per ERR5: "Log crash, spawn replacement, resume from checkpoint"
    """
    # Load checkpoint for crashed agent
    agent_state = await checkpoint_manager.load_agent_state(engagement_id, crashed_agent_id)
    
    if not agent_state:
        logger.warning("no_checkpoint_for_crashed_agent", agent_id=crashed_agent_id)
        return None
    
    # Determine role from checkpoint
    role = AgentRole(agent_state.agent_type)
    
    # Spawn replacement with same ID (for continuity)
    replacement = await self.router.create_agent(
        role=role,
        agent_id=crashed_agent_id,  # Inherit ID
        engagement_id=engagement_id,
        event_bus=self.event_bus,
    )
    
    # Restore state from checkpoint
    await replacement.restore_from_checkpoint(agent_state)
    
    # Update active agents list
    self._active_agents = [a for a in self._active_agents if a.agent_id != crashed_agent_id]
    self._active_agents.append(replacement)
    
    await self._log_scaling_decision(
        action="replace_crashed",
        count=1,
        rationale=f"crash_recovery_for_{crashed_agent_id}",
        decision_context=[],
    )
    
    logger.info("agent_replaced", agent_id=crashed_agent_id, role=role.value)
    return replacement
```

### Testing Standards

**Unit Tests Location:** `tests/unit/orchestration/test_crash_monitor.py`
- Mock EventBus, CheckpointManager
- Test heartbeat timeout detection
- Test agent registration/deregistration
- Test crash callback invocation

**Integration Tests Location:** `tests/integration/orchestration/test_crash_recovery.py`
- Use real EventBus with mock Redis
- Test full crash → detect → replace → resume flow
- Test checkpoint persistence

**Safety Tests Location:** `tests/safety/agents/test_agent_crash_recovery.py`
- Verify ERR5 compliance
- Test engagement continuity after crash
- Test no data loss

### Project Structure Notes

New files to create:
- `src/cyberred/orchestration/crash_monitor.py` - Main crash monitoring logic
- `tests/unit/orchestration/test_crash_monitor.py` - Unit tests
- `tests/integration/orchestration/test_crash_recovery.py` - Integration tests  
- `tests/safety/agents/test_agent_crash_recovery.py` - Safety tests

Files to modify:
- `src/cyberred/agents/base.py` - Add heartbeat and checkpoint methods
- `src/cyberred/orchestration/spawner.py` - Add replace_agent() method
- `src/cyberred/storage/checkpoint.py` - Add save_agent_state() and load_agent_state() methods

### References

- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 7.12] - Original story definition
- [Source: _bmad-output/planning-artifacts/architecture.md#Error Handling] - ERR5 specification
- [Source: src/cyberred/storage/checkpoint.py#AgentState] - Existing checkpoint data structures
- [Source: src/cyberred/orchestration/spawner.py#DynamicSpawner] - Spawner patterns
- [Source: src/cyberred/agents/base.py#StigmergicAgent] - Base agent class
- [Source: tests/safety/tools/test_tool_failure_recovery.py] - Related safety test patterns

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

N/A - All tests pass.

### Completion Notes List

- Implemented AgentCrashMonitor class with 30s crash detection timeout and 10s heartbeat interval
- Added heartbeat methods (send_heartbeat, _start_heartbeat, _heartbeat_loop) to StigmergicAgent
- Added checkpoint methods (save_checkpoint, restore_from_checkpoint) to StigmergicAgent
- Added save_agent_state and load_agent_state methods to CheckpointManager
- Added replace_agent method to DynamicSpawner for crash recovery
- All crash detection includes full logging with agent_id, engagement_id, elapsed_seconds, task_id
- Implemented ERR5 pattern: "Log crash, spawn replacement, resume from checkpoint"
- 35 tests pass (26 unit, 4 integration, 5 safety)
- crash_monitor.py has 100% test coverage

### File List

**New Files:**
- src/cyberred/orchestration/crash_monitor.py
- tests/unit/orchestration/test_crash_monitor.py
- tests/integration/orchestration/test_crash_recovery.py
- tests/safety/agents/__init__.py
- tests/safety/agents/test_agent_crash_recovery.py

**Modified Files:**
- src/cyberred/agents/base.py (added heartbeat and checkpoint methods)
- src/cyberred/orchestration/spawner.py (added replace_agent method)
- src/cyberred/orchestration/__init__.py (added crash_monitor exports)
- src/cyberred/storage/checkpoint.py (added save_agent_state, load_agent_state)
- tests/unit/agents/test_stigmergic_base.py (added heartbeat and checkpoint tests)
- tests/unit/orchestration/test_spawner.py (added replace_agent tests)
- tests/unit/storage/test_checkpoint.py (added agent state tests)

