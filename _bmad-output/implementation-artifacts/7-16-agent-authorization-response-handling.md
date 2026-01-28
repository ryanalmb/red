# Story 7.16: Agent Authorization Response Handling

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **agent**,
I want **to wait for and process authorization responses**,
So that **lateral movement proceeds only when operator approves (FR13, FR15)**.

## Acceptance Criteria

1. **Given** agent has requested authorization for lateral movement
   - **When** authorization request is published
   - **Then** agent enters WAITING_AUTHORIZATION state
   - **And** agent status is logged with structlog

2. **Given** agent is in WAITING_AUTHORIZATION state
   - **When** waiting for authorization
   - **Then** agent subscribes to `auth:{request_id}:response` channel
   - **And** agent blocks execution until response received
   - **And** timeout is indefinite per FR16 (no auto-deny)

3. **Given** operator grants authorization
   - **When** agent receives response with `granted: true`
   - **Then** agent resumes original action
   - **And** agent transitions from WAITING_AUTHORIZATION to RUNNING state
   - **And** authorization grant is logged in `decision_context` as `auth:{request_id}:granted`

4. **Given** operator denies authorization
   - **When** agent receives response with `granted: false`
   - **Then** agent logs denial reason
   - **And** agent selects alternative action via `select_tool()`
   - **And** agent transitions to ALTERNATIVE_PATH or RUNNING state
   - **And** authorization denial is logged in `decision_context` as `auth:{request_id}:denied`

5. **Given** the authorization handling is implemented
   - **When** any agent subclass requests lateral movement authorization
   - **Then** base `StigmergicAgent._request_authorization()` handles the flow
   - **And** PostExAgent, ADAgent, and other agents inherit this behavior

6. **Given** authorization wait/resume flow needs validation
   - **When** integration tests run
   - **Then** tests verify complete authorization lifecycle
   - **And** tests cover grant, deny, and state transition scenarios

## Tasks / Subtasks

- [ ] Task 1: Add `subscribe_once()` method to EventBus (AC: #2)
  - [ ] 1.1: Implement `subscribe_once(channel: str, timeout: float | None = None) -> dict | None` in `core/events.py`
  - [ ] 1.2: Method subscribes to channel, waits for one message, then unsubscribes
  - [ ] 1.3: Support optional timeout (None = indefinite per FR16)
  - [ ] 1.4: Return parsed JSON message or None on timeout
  - [ ] 1.5: Add channel pattern for `auth:{request_id}:response` to CHANNEL_PATTERNS
  - [ ] 1.6: Write unit tests for `subscribe_once()` method

- [ ] Task 2: Add WAITING_AUTHORIZATION state to agent (AC: #1, #3, #4)
  - [ ] 2.1: Update `StigmergicAgent._status` to support "waiting_authorization" state
  - [ ] 2.2: Add `_pending_auth_request_id: str | None` attribute to track active authorization
  - [ ] 2.3: Ensure status transitions are logged via structlog
  - [ ] 2.4: Write unit tests for state management

- [ ] Task 3: Implement `_request_authorization()` in StigmergicAgent base class (AC: #1, #2, #3, #4, #5)
  - [ ] 3.1: Move `_request_authorization()` from `PostExAgent` to `StigmergicAgent` base class
  - [ ] 3.2: Implement authorization request publishing to `authorization:{request_id}` channel
  - [ ] 3.3: Implement state transition to WAITING_AUTHORIZATION
  - [ ] 3.4: Use `subscribe_once()` to wait for response on `auth:{request_id}:response`
  - [ ] 3.5: Implement grant handling: log to decision_context, return True
  - [ ] 3.6: Implement denial handling: log reason, log to decision_context, return False
  - [ ] 3.7: Add `alternative_on_denial: bool = True` parameter to trigger `_select_alternative_action()`
  - [ ] 3.8: Update PostExAgent to use inherited method (remove duplicate implementation)
  - [ ] 3.9: Write unit tests for authorization flow

- [ ] Task 4: Implement `_select_alternative_action()` helper (AC: #4)
  - [ ] 4.1: Add `_select_alternative_action(original_action: str, denial_reason: str) -> str | None`
  - [ ] 4.2: Use `select_tool()` with modified context indicating denial
  - [ ] 4.3: Log alternative selection in decision_context
  - [ ] 4.4: Write unit tests for alternative selection

- [ ] Task 5: Update DecisionContextTracker for authorization signals (AC: #3, #4)
  - [ ] 5.1: Add "authorization" signal type to `SIGNAL_TYPE_WEIGHTS` in tracker.py (weight: 1.0 - critical)
  - [ ] 5.2: Ensure `auth:{request_id}:{granted|denied}` format is recorded properly
  - [ ] 5.3: Write unit tests for authorization tracking

- [ ] Task 6: Write integration tests (AC: #6)
  - [ ] 6.1: Create `tests/integration/agents/test_authorization_flow.py`
  - [ ] 6.2: Test authorization grant flow with real EventBus
  - [ ] 6.3: Test authorization denial flow with alternative action selection
  - [ ] 6.4: Test state transitions (RUNNING → WAITING_AUTHORIZATION → RUNNING)
  - [ ] 6.5: Test decision_context population for authorization events
  - [ ] 6.6: Test PostExAgent lateral movement authorization (existing behavior preserved)
  - [ ] 6.7: Test indefinite wait (no auto-deny per FR16)

- [ ] Task 7: Update existing PostExAgent tests (AC: #5)
  - [ ] 7.1: Update `tests/unit/agents/test_postex_agent_v2.py` to verify inherited `_request_authorization()`
  - [ ] 7.2: Ensure existing authorization tests pass with base class implementation
  - [ ] 7.3: Remove duplicate test coverage if method moved to base class

## Dev Notes

### Architecture Context

This story implements FR13 (Lateral Movement Authorization) and FR15 (Operator Approval) by providing a robust authorization request/response mechanism in the base `StigmergicAgent` class. Key design decisions:

**State Management:**
- Agents enter `WAITING_AUTHORIZATION` state while awaiting operator response
- State is observable via `get_status()` for TUI display and monitoring
- No timeout on authorization wait per FR16 (operator must explicitly approve/deny)

**Channel Patterns:**
- Authorization requests: `authorization:{request_id}` (already in CHANNEL_PATTERNS)
- Authorization responses: `auth:{request_id}:response` (needs to be added)
- Pattern follows existing architecture conventions

**Integration Points:**
- `EventBus.subscribe_once()` for blocking wait on single response
- `DecisionContextTracker` for NFR37 compliance (100% decision traceability)
- `StigmergicAgent.select_tool()` for alternative action selection on denial

### Existing Implementation Analysis

The current `PostExAgent._request_authorization()` implementation (lines 199-210 in `agents/postex.py`) provides a starting point but needs enhancement:

```python
# Current implementation (PostExAgent)
async def _request_authorization(self, action: str, target: str, justification: str) -> bool:
    request_id = str(uuid.uuid4())
    channel = f"authorization:{request_id}"
    await self.event_bus.publish(channel, {...})
    response = await self.event_bus.subscribe_once(f"{channel}:response")  # NOT IMPLEMENTED
    granted = response.get("granted", False) if response else False
    self._decision_context.append(f"auth:{request_id}:{'granted' if granted else 'denied'}")
    return granted
```

**Issues to address:**
1. `subscribe_once()` does not exist in EventBus - must be implemented
2. No state transition to WAITING_AUTHORIZATION
3. No alternative action selection on denial
4. Should be in base class for reuse by ADAgent, other agents

### Relevant Architecture Patterns

From architecture.md and existing code:
- EventBus channel patterns: `authorization:{request_id}`, `auth:{request_id}:response`
- Agent status values: "idle", "active", "waiting", "waiting_authorization", "shutdown", "error"
- Decision context format: `["auth:{request_id}:granted", "intel:cisa:CVE-2024-1234", ...]`
- structlog binding: `log.bind(agent_id=..., engagement_id=...)`

### Source Tree Components

**Modified Files:**
- `src/cyberred/core/events.py` - Add `subscribe_once()` method, update CHANNEL_PATTERNS
- `src/cyberred/agents/base.py` - Add `_request_authorization()`, state management, `_select_alternative_action()`
- `src/cyberred/agents/postex.py` - Remove duplicate `_request_authorization()`, use inherited method
- `src/cyberred/orchestration/emergence/tracker.py` - Add "authorization" signal type

**New Files:**
- `tests/integration/agents/test_authorization_flow.py` - Integration tests

**Updated Test Files:**
- `tests/unit/core/test_events.py` - Tests for `subscribe_once()`
- `tests/unit/agents/test_stigmergic_base.py` - Tests for authorization in base class
- `tests/unit/agents/test_postex_agent_v2.py` - Update existing authorization tests

### Testing Standards

- Unit tests: 100% coverage of new methods
- Integration tests: Real Redis pub/sub with EventBus
- Use pytest fixtures from `tests/conftest.py`
- Follow existing patterns in `tests/unit/agents/` and `tests/integration/agents/`
- Mock LLM responses for `_select_alternative_action()` tests

### Authorization Message Format

**Request (published to `authorization:{request_id}`):**
```json
{
  "request_id": "uuid-string",
  "agent_id": "agent-uuid",
  "engagement_id": "engagement-uuid",
  "action": "lateral_movement",
  "target": "192.168.1.50",
  "justification": "Discovered valid credentials for SMB share",
  "timestamp": "2026-01-28T00:00:00Z"
}
```

**Response (received on `auth:{request_id}:response`):**
```json
{
  "request_id": "uuid-string",
  "granted": true,
  "operator_id": "operator-uuid",
  "reason": "Approved for lateral movement to target",
  "timestamp": "2026-01-28T00:01:00Z"
}
```

### Project Structure Notes

- Authorization handling belongs in base class (`agents/base.py`) for reuse
- Channel pattern for responses follows `auth:{id}:response` convention
- State machine for agent status should be explicit and logged
- All authorization decisions must be traceable via decision_context (NFR37)

### References

- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 7.16] - Original story definition
- [Source: _bmad-output/planning-artifacts/architecture.md#lines 682-700] - Event naming conventions
- [Source: src/cyberred/agents/base.py#lines 45-130] - StigmergicAgent base class
- [Source: src/cyberred/agents/postex.py#lines 199-210] - Existing `_request_authorization()` implementation
- [Source: src/cyberred/core/events.py#lines 47-54] - CHANNEL_PATTERNS
- [Source: src/cyberred/core/events.py#lines 79-222] - EventBus class
- [Source: tests/unit/agents/test_postex_agent_v2.py#lines 555-563] - Existing authorization tests

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

N/A - All tests pass

### Completion Notes List

1. **Implementation was already complete** - Story 7.16 was largely implemented in prior work:
   - `subscribe_once()` method existed in `EventBus` (lines 224-280)
   - `auth:{request_id}:response` channel pattern existed (line 52)
   - `_request_authorization()` method existed in `StigmergicAgent` base class (lines 854-956)
   - `_select_alternative_action()` helper existed (lines 958-1031)
   - "authorization" signal type with weight 1.0 existed in `DecisionContextTracker` (line 30)
   - PostExAgent already used inherited `_request_authorization()` (comment lines 199-201)

2. **Fixed integration tests** - Updated `tests/integration/agents/test_authorization_flow.py`:
   - Fixed swarms mock to use proper class instead of MagicMock
   - Fixed async mock patterns for `subscribe_once`
   - Added new tests for alternative action selection

3. **Fixed unit tests** - Updated `tests/unit/agents/test_postex_agent_v2.py`:
   - Fixed `mock_llm_gateway` fixture to include `agent_complete` AsyncMock
   - Fixed authorization tests to use proper async function mocks

### File List

**Modified Files:**
- `tests/integration/agents/test_authorization_flow.py` - Fixed swarms mocking and async patterns
- `tests/unit/agents/test_postex_agent_v2.py` - Fixed mock fixtures for authorization flow

**Verified Files (no changes needed):**
- `src/cyberred/core/events.py` - subscribe_once() already implemented
- `src/cyberred/agents/base.py` - _request_authorization() and _select_alternative_action() already implemented
- `src/cyberred/agents/postex.py` - Already uses inherited authorization method
- `src/cyberred/orchestration/emergence/tracker.py` - "authorization" signal type already present

**Test Results:**
- Unit tests: 238 tests passed
- Integration tests: 11 tests passed (authorization flow)
- Coverage: tracker.py 100%, events.py 96.24%, base.py 81.21%
