# Story 7.1: StigmergicAgent Base Class

**Status:** done
**Estimation:** 3 story points
**Owner:** @antigravity

## Story

As a **developer**,
I want **a base agent class with stigmergic pub/sub hooks**,
So that **all agents can participate in P2P coordination (FR4)**.

## Acceptance Criteria

1. **Given** Epic 3 (event bus) is complete
   - **When** I extend `StigmergicAgent`
   - **Then** agent has `on_finding()` lifecycle hook → publishes to Redis

2. **Given** agent spawns with engagement context
   - **When** stigmergic signal is received on subscribed topic
   - **Then** agent has `on_signal()` lifecycle hook → reacts to swarm state

3. **Given** agent completes a task
   - **When** task execution finishes
   - **Then** agent has `on_complete()` lifecycle hook → updates stigmergic map

4. **Given** agent spawns
   - **When** initialization completes
   - **Then** agent subscribes to relevant topic patterns

5. **Given** any agent message
   - **When** message is published
   - **Then** message includes `agent_id`, `engagement_id` fields

6. **Given** lifecycle hooks are defined
   - **When** unit tests run
   - **Then** all lifecycle hooks fire correctly and are verified

## Tasks / Subtasks

### Phase 1: RED - Write Failing Tests First

- [x] Task 1: Create test file structure (AC: #6)
  - [x] Create `tests/unit/agents/test_stigmergic_base.py`
  - [x] Create `tests/integration/agents/test_stigmergic_integration.py`
  
- [x] Task 2: Write unit tests for StigmergicAgent base class (AC: #1-5)
  - [x] Test `__init__` requires `agent_id`, `engagement_id`, `event_bus`
  - [x] Test `on_finding()` publishes to `findings:{target_hash}:{type}` channel
  - [x] Test `on_signal()` is called when subscribed channel receives message
  - [x] Test `on_complete()` publishes completion status
  - [x] Test agent subscribes to `findings:*`, `strategies:*`, `control:*` on spawn
  - [x] Test all messages include `agent_id` and `engagement_id`
  - [x] Test agent implements `AgentProtocol` (structural subtyping)

- [x] Task 3: Write integration tests (AC: #1-5)
  - [x] Test real Redis pub/sub message flow
  - [x] Test lifecycle hook sequence: spawn → subscribe → execute → on_signal → on_finding → on_complete
  - [x] Test agent receives signals from other agents (P2P coordination)

### Phase 2: GREEN - Implement Minimal Code

- [x] Task 4: Create StigmergicAgent base class (AC: #1-5)
  - [x] Create `src/cyberred/agents/base.py`
  - [x] Extend `swarms.Agent` from kyegomez/swarms v8.0.0+
  - [x] Implement `__init__` with required parameters
  - [x] Implement `on_finding()` lifecycle hook
  - [x] Implement `on_signal()` lifecycle hook
  - [x] Implement `on_complete()` lifecycle hook
  - [x] Implement topic subscription on spawn
  - [x] Ensure all messages include agent metadata

- [x] Task 5: Implement AgentProtocol compliance (AC: #6)
  - [x] Implement `execute()` method (delegates to swarms Agent)
  - [x] Implement `reason()` method
  - [x] Implement `get_id()` method
  - [x] Implement `get_status()` method
  - [x] Implement `get_decision_context()` method
  - [x] Implement `shutdown()` method

- [x] Task 6: Wire EventBus integration (AC: #1-3)
  - [x] Import and use `EventBus` from `core/events.py`
  - [x] Validate channel names per architecture patterns
  - [x] Handle Redis degraded mode gracefully

### Phase 3: REFACTOR - Optimize and Harden

- [x] Task 7: Add decision_context tracking (AC: #6, NFR37)
  - [x] Store signal IDs that influence decisions
  - [x] Return decision_context via `get_decision_context()`
  - [x] Ensure 100% of actions include decision_context

- [x] Task 8: Add self-throttling foundation (prepares Story 7.2)
  - [x] Add `status` property: `idle`, `active`, `waiting`, `shutdown`
  - [x] Add `_check_throttle()` stub method

- [x] Task 9: Documentation and exports (AC: #6)
  - [x] Add comprehensive docstrings
  - [x] Export from `agents/__init__.py`
  - [x] Update `agents/` module README if exists

## Dev Notes

### Architecture Patterns & Constraints

**Framework Integration:**
- **MUST** extend `swarms.Agent` from [kyegomez/swarms](https://github.com/kyegomez/swarms) v8.0.0+
- This is **NOT** OpenAI's experimental "Swarm" project
- Swarms already in `pyproject.toml`: `"swarms>=8.0.0"`

```python
from swarms import Agent  # kyegomez/swarms

class StigmergicAgent(Agent):
    """Base agent with stigmergic pub/sub hooks."""
```

**Lifecycle Flow:**
```
spawn → subscribe → execute → on_signal → on_finding → on_complete
```

**Channel Patterns (from architecture line 686-700):**
| Channel Type | Pattern | Example |
|--------------|---------|---------|
| Findings | `findings:{target_hash}:{type}` | `findings:a1b2c3:sqli` |
| Agent Status | `agents:{agent_id}:status` | `agents:ghost-42:status` |
| Kill Switch | `control:kill` | — |
| Strategies | `strategies:{engagement_id}` | `strategies:ministry-2025` |

**EventBus Integration:**
- Use `EventBus` from `src/cyberred/core/events.py` (Story 3.3)
- Channel validation already implemented via `CHANNEL_PATTERNS`
- HMAC signing handled by underlying `RedisClient` (Story 3.1)

**AgentProtocol Compliance:**
- Must satisfy `AgentProtocol` from `src/cyberred/protocols/agent.py`
- Protocol methods: `execute`, `reason`, `get_id`, `get_status`, `get_decision_context`, `shutdown`
- Uses structural subtyping (no inheritance required, just method signatures)

### Existing Code to Reuse/Extend

| Component | Location | Usage |
|-----------|----------|-------|
| `AgentProtocol` | `src/cyberred/protocols/agent.py` | Interface to implement |
| `EventBus` | `src/cyberred/core/events.py` | Pub/sub wrapper |
| `RedisClient` | `src/cyberred/storage/redis_client.py` | Underlying Redis |
| `AgentAction` | `src/cyberred/core/models.py` | Return type for execute() |
| `GhostAgent` | `src/cyberred/agents/ghost_agent.py` | Reference implementation (legacy) |

### Anti-Patterns to Avoid

1. **DO NOT** fork swarms — extend only
2. **DO NOT** create custom pub/sub — use existing `EventBus`
3. **DO NOT** skip channel validation — use `EventBus._validate_channel()`
4. **DO NOT** forget `decision_context` — NFR37 requires 100% population
5. **DO NOT** hardcode topic patterns — use configurable subscriptions

### Testing Standards

- **100% coverage required** (NFR19/NFR20)
- Use `pytest-asyncio` for async tests
- Mock Redis with `fakeredis` for unit tests
- Use real Redis via `testcontainers` for integration tests
- Test markers: `@pytest.mark.unit`, `@pytest.mark.integration`

### Project Structure Notes

**New Files:**
```
src/cyberred/agents/
├── __init__.py        # Update exports
├── base.py            # NEW: StigmergicAgent base class
├── ghost_agent.py     # Existing (legacy)
└── rag_escalator.py   # Existing (Story 6.10)

tests/unit/agents/
├── test_stigmergic_base.py    # NEW: Unit tests

tests/integration/agents/
├── test_stigmergic_integration.py  # NEW: Integration tests
```

**Naming Conventions:**
- Class: `StigmergicAgent` (PascalCase)
- Module: `base.py` (per architecture line 795)
- Test files mirror source: `test_stigmergic_base.py`

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Agent-Communication-Patterns] — JSON serialization, Redis Pub/Sub
- [Source: _bmad-output/planning-artifacts/architecture.md#Mandatory-Rules-for-AI-Agents] — Rule 1: All agents extend StigmergicAgent
- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story-7.1] — Acceptance criteria, technical notes
- [Source: src/cyberred/protocols/agent.py] — AgentProtocol interface
- [Source: src/cyberred/core/events.py] — EventBus implementation
- [Source: pyproject.toml#L22] — swarms>=8.0.0 dependency

### Epic 6 Learnings Applied

Per Epic 6 Retrospective Action Items:
- **AI-1 (CRITICAL):** Using TDD phased format (RED/GREEN/REFACTOR)
- **AI-2:** Schema design centralized — `AgentAction` already in `core/models.py`
- **AI-3:** Will use shared test fixtures where possible

### Dependencies

**Prerequisites (all complete):**
- Epic 3: Communication Infrastructure ✅
  - Story 3.1: Redis Sentinel Client ✅
  - Story 3.3: Event Bus (Pub/Sub) ✅
  - Story 3.4: Event Bus Streams for Audit ✅

**Blocks:**
- Story 7.2: Agent Self-Throttling
- Story 7.3: ReconAgent Implementation
- Story 7.4: ExploitAgent Implementation
- Story 7.5: PostExAgent Implementation
- Story 7.8: Decision Context Tracking

---

## Dev Agent Record

### Agent Model Used

Gemini 2.0 Flash (Antigravity)

### Debug Log References

- Session logs covering implementation of StigmergicAgent base class.

### Completion Notes List

1. Implemented `StigmergicAgent` in `src/cyberred/agents/base.py` extending `swarms.Agent`.
2. Created comprehensive unit tests in `tests/unit/agents/test_stigmergic_base.py` covering all lifecycle hooks and protocol compliance.
3. Created integration tests in `tests/integration/agents/test_stigmergic_integration.py` verifying real Redis pub/sub coordination.
4. Updated `src/cyberred/core/events.py` to support `strategies:*` channel pattern as required by architecture.
5. Ensured 100% pass rate for all new tests.

### File List

- `src/cyberred/agents/base.py`
- `src/cyberred/agents/__init__.py`
- `src/cyberred/core/events.py`
- `tests/unit/agents/test_stigmergic_base.py`
- `tests/integration/agents/test_stigmergic_integration.py`
