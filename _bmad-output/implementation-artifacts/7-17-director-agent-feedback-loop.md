# Story 7.17: Director-Agent Feedback Loop Integration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **verified integration between Director strategy and agent behavior**,
So that **agents demonstrably change behavior based on Director guidance**.

## Acceptance Criteria

1. **Given** Director publishes strategy to `strategies:{engagement_id}`
   - **When** agents receive strategy update via EventBus subscription
   - **Then** agents parse and store the EmergentStrategy in their internal state
   - **And** strategy is accessible via `agent._active_strategy` property

2. **Given** agents have received a strategy with `strategy.objectives`
   - **When** agents call `select_tool()` for their next action
   - **Then** agents adjust tool selection priorities based on `strategy.objectives`
   - **And** objectives influence the LLM prompt context for tool selection
   - **And** tool selection rationale references the strategy objective

3. **Given** strategy contains `strategy.avoid_targets` list
   - **When** agent considers targets for next action
   - **Then** agent excludes targets in `avoid_targets` from consideration
   - **And** avoided targets are logged with reason "strategy_avoid_list"

4. **Given** strategy contains `strategy.recommended_techniques` (ATT&CK IDs)
   - **When** agents incorporate strategy into `select_tool()` decisions
   - **Then** agents prioritize tools that map to recommended ATT&CK techniques
   - **And** technique-to-tool mapping uses existing tool manifest metadata

5. **Given** agent behavior changes based on strategy
   - **When** agent takes an action influenced by Director strategy
   - **Then** behavior change is logged in `decision_context` citing `strategy_id`
   - **And** DecisionContextTracker records strategy signal with type "director_strategy"

6. **Given** the need to verify feedback loop effectiveness
   - **When** integration test publishes "prioritize web apps" strategy
   - **Then** test verifies agents shift from network to web tool selection
   - **And** test captures before/after agent actions for comparison

7. **Given** e2e test framework exists
   - **When** e2e test runs feedback loop verification
   - **Then** test captures agent actions before strategy publication
   - **And** test publishes strategy with specific objectives
   - **And** test verifies measurable behavior change in subsequent actions
   - **And** test validates decision_context contains strategy_id

## Tasks / Subtasks

- [x] Task 1: Extend StigmergicAgent strategy handling (AC: #1, #2, #3, #4)
  - [x] 1.1: Add `_active_strategy: EmergentStrategy | None` property to StigmergicAgent
  - [x] 1.2: Implement `_handle_strategy_update()` method to parse and store strategy
  - [x] 1.3: Extend `on_signal()` to detect strategy channel and call `_handle_strategy_update()`
  - [x] 1.4: Implement `_get_strategy_context()` helper for tool selection prompt enrichment
  - [x] 1.5: Write unit tests for strategy storage and retrieval

- [x] Task 2: Implement objective-based priority adjustment (AC: #2)
  - [x] 2.1: Extend `_build_tool_selection_prompt()` to include strategy objectives
  - [x] 2.2: Add objective keywords to tool selection prompt context
  - [x] 2.3: Ensure LLM rationale references strategy objective when applicable
  - [x] 2.4: Write unit tests for objective-influenced tool selection

- [x] Task 3: Implement avoid_targets filtering (AC: #3)
  - [x] 3.1: Add `_is_target_avoided()` method to check against strategy.avoid_targets
  - [x] 3.2: Integrate avoid check into tool selection flow
  - [x] 3.3: Log avoided targets with structured reason field
  - [x] 3.4: Write unit tests for avoid_targets filtering

- [x] Task 4: Implement technique-to-tool prioritization (AC: #4)
  - [x] 4.1: Create `ATTCK_TECHNIQUE_TOOL_MAP` mapping ATT&CK IDs to tool categories
  - [x] 4.2: Implement `_get_technique_tools()` to expand ATT&CK IDs to tool names
  - [x] 4.3: Boost priority of technique-mapped tools in selection context
  - [x] 4.4: Write unit tests for technique-to-tool mapping

- [x] Task 5: Implement decision context tracking for strategies (AC: #5)
  - [x] 5.1: Add "director_strategy" signal type to DecisionContextTracker.SIGNAL_TYPE_WEIGHTS
  - [x] 5.2: Record strategy_id when agent acts on strategy guidance
  - [x] 5.3: Ensure decision_context includes strategy_id for all strategy-influenced actions
  - [x] 5.4: Write unit tests for strategy decision context tracking

- [x] Task 6: Write integration test for feedback loop (AC: #6)
  - [x] 6.1: Create `tests/integration/agents/test_feedback_loop.py`
  - [x] 6.2: Implement test fixture for mock EventBus with strategy publication
  - [x] 6.3: Implement test case: publish "prioritize web apps" → verify agent shift
  - [x] 6.4: Implement test case: publish avoid_targets → verify target exclusion
  - [x] 6.5: Implement test case: publish recommended_techniques → verify tool priority change

- [x] Task 7: Write e2e test for behavior change verification (AC: #7)
  - [x] 7.1: Create `tests/e2e/test_director_feedback_loop.py`
  - [x] 7.2: Implement before/after action capture mechanism
  - [x] 7.3: Implement strategy publication with measurable objectives
  - [x] 7.4: Implement behavior change assertions (tool selection shift)
  - [x] 7.5: Verify decision_context contains strategy_id in all post-strategy actions

- [x] Task 8: Update EmergentStrategy model if needed (AC: #2, #3, #4)
  - [x] 8.1: Ensure EmergentStrategy.objectives is list[str] with clear semantic structure
  - [x] 8.2: Rename `avoid_targets` to match story AC if currently named differently
  - [x] 8.3: Verify recommended_techniques contains valid ATT&CK technique IDs
  - [x] 8.4: Add validation for objectives format

## Dev Notes

### Architecture Context

This story closes the feedback loop between Director strategy synthesis and agent behavior. Story 7.15 implemented strategy creation and publication; this story verifies agents actually consume and act on those strategies.

**Feedback Loop Flow:**
```
Director → EmergentStrategy → strategies:{engagement_id} → Agent.on_signal() 
    → _active_strategy → select_tool() context → behavior change → decision_context
```

**Critical Verification:**
- Agents MUST demonstrably change behavior when strategy is received
- Change must be traceable via decision_context (NFR37)
- Integration tests must prove: strategy A → behavior X; strategy B → behavior Y

### Relevant Architecture Patterns

From architecture.md:
- Stigmergic coordination via Redis Pub/Sub (lines 366-438)
- EventBus channel patterns: `strategies:{engagement_id}`
- Decision context tracking for NFR37 (100% action traceability)
- LLM tool selection with context injection (Story 7.1.v2)

From Story 7.15:
- EmergentStrategy dataclass with objectives, recommended_techniques, avoid_targets
- Strategy publication to `strategies:{engagement_id}` channel
- Agent subscription in `_setup_subscriptions()` (line 156 of base.py)

### ATT&CK Technique to Tool Category Mapping

| ATT&CK Technique | Tool Categories | Example Tools |
|------------------|-----------------|---------------|
| T1046 (Network Service Discovery) | recon, discovery | nmap, masscan |
| T1018 (Remote System Discovery) | recon, enumeration | nbtscan, enum4linux |
| T1021 (Remote Services) | exploit, lateral | crackmapexec, psexec |
| T1078 (Valid Accounts) | credential, auth | hydra, medusa |
| T1190 (Exploit Public-Facing App) | web, exploit | sqlmap, nuclei |
| T1595 (Active Scanning) | recon, scanning | nmap, nikto |
| T1082 (System Discovery) | postex, enum | linpeas, winpeas |

### Source Tree Components

**Modified Files:**
- `src/cyberred/agents/base.py` - Extend strategy handling in StigmergicAgent
- `src/cyberred/orchestration/emergence/tracker.py` - Add "director_strategy" signal type

**New Files:**
- `src/cyberred/agents/strategy_handler.py` - Strategy parsing and context building (optional, can be in base.py)
- `tests/integration/test_feedback_loop.py` - Integration tests for feedback loop
- `tests/e2e/test_director_feedback_loop.py` - E2E tests for behavior verification

**Test Files:**
- `tests/unit/agents/test_strategy_handling.py` - Unit tests for strategy consumption
- `tests/integration/test_feedback_loop.py` - Integration tests per AC#6
- `tests/e2e/test_director_feedback_loop.py` - E2E tests per AC#7

### Implementation Strategy

**Phase 1: Strategy Storage (Task 1)**
```python
# In StigmergicAgent
@property
def _active_strategy(self) -> EmergentStrategy | None:
    """Currently active strategy from Director."""
    return self.__active_strategy

async def _handle_strategy_update(self, data: dict[str, Any]) -> None:
    """Process incoming strategy from Director."""
    strategy = EmergentStrategy.from_json(data)
    self.__active_strategy = strategy
    
    # Record in decision context
    if self._context_tracker:
        self._context_tracker.record_signal(
            agent_id=self.agent_id,
            signal_id=strategy.id,
            signal_type="director_strategy",
            source="director",
            channel=f"strategies:{self.engagement_id}",
        )
    
    self._log.info(
        "strategy_received",
        strategy_id=strategy.id,
        objectives=strategy.objectives,
    )
```

**Phase 2: Tool Selection Integration (Tasks 2-4)**
```python
def _build_tool_selection_prompt(self, context: ToolSelectionContext) -> str:
    """Build LLM prompt with strategy context."""
    base_prompt = super()._build_tool_selection_prompt(context)
    
    if self._active_strategy:
        strategy_context = self._get_strategy_context()
        return f"{base_prompt}\n\n**Director Strategy:**\n{strategy_context}"
    
    return base_prompt

def _get_strategy_context(self) -> str:
    """Build strategy context string for LLM prompt."""
    if not self._active_strategy:
        return ""
    
    parts = []
    if self._active_strategy.objectives:
        parts.append(f"Objectives: {', '.join(self._active_strategy.objectives)}")
    if self._active_strategy.recommended_techniques:
        parts.append(f"Recommended ATT&CK: {', '.join(self._active_strategy.recommended_techniques)}")
    if self._active_strategy.avoid_targets:
        parts.append(f"Avoid targets: {', '.join(self._active_strategy.avoid_targets)}")
    
    return "\n".join(parts)
```

**Phase 3: Avoid Target Filtering (Task 3)**
```python
def _is_target_avoided(self, target: str) -> bool:
    """Check if target is in strategy avoid list."""
    if not self._active_strategy or not self._active_strategy.avoid_targets:
        return False
    
    avoided = target in self._active_strategy.avoid_targets
    if avoided:
        self._log.info(
            "target_avoided",
            target=target,
            reason="strategy_avoid_list",
            strategy_id=self._active_strategy.id,
        )
    return avoided
```

### Testing Standards

- **Unit tests:** 100% coverage of new strategy handling code
- **Integration tests:** Real EventBus with mock Redis, verify strategy propagation
- **E2E tests:** Full agent lifecycle with strategy injection, verify behavior change
- **Coverage gate:** 100% line coverage for modified files
- **TDD required:** Write failing tests first, then implementation

### Key Test Scenarios

1. **Strategy Reception Test:**
   - Publish EmergentStrategy to `strategies:{engagement_id}`
   - Verify agent stores strategy in `_active_strategy`
   - Verify decision_context records strategy_id

2. **Objective Influence Test:**
   - Give agent strategy with objective "prioritize web vulnerabilities"
   - Call `select_tool()` with neutral context
   - Verify tool selection favors web tools (sqlmap, nuclei over nmap)

3. **Avoid Target Test:**
   - Give agent strategy with avoid_targets=["192.168.1.100"]
   - Call `select_tool()` with target "192.168.1.100"
   - Verify target is skipped with logged reason

4. **Technique Prioritization Test:**
   - Give agent strategy with recommended_techniques=["T1190"]
   - Verify web exploitation tools are prioritized

5. **Before/After Behavior Test:**
   - Capture agent tool selection before strategy
   - Publish strategy with "shift to web apps" objective
   - Capture agent tool selection after strategy
   - Assert measurable difference in tool categories selected

### Project Structure Notes

- All strategy handling code in `src/cyberred/agents/base.py` (extend existing)
- Integration tests in `tests/integration/` following existing patterns
- E2E tests in `tests/e2e/` (may need to create directory structure)
- Use pytest fixtures from `tests/conftest.py`
- Follow structlog patterns for all logging

### Dependencies

- **Story 7.15:** EmergentStrategy, EmergentStrategyPublisher (COMPLETE)
- **Story 7.1.v2:** StigmergicAgent with select_tool() (COMPLETE)
- **Story 7.8:** DecisionContextTracker (COMPLETE)
- **Epic 3:** EventBus for pub/sub (COMPLETE)

### References

- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 7.17] - Original story definition
- [Source: _bmad-output/planning-artifacts/architecture.md#lines 366-438] - Stigmergic coordination
- [Source: src/cyberred/orchestration/emergence/strategy.py] - EmergentStrategy implementation
- [Source: src/cyberred/agents/base.py#lines 139-159] - Strategy subscription setup
- [Source: src/cyberred/agents/base.py#lines 607-748] - LLM tool selection methods
- [Source: src/cyberred/orchestration/emergence/tracker.py] - DecisionContextTracker patterns
- [Source: tests/integration/orchestration/emergence/test_emergent_strategy_integration.py] - Existing strategy tests

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

N/A - All tests passed without debug issues

### Completion Notes List

1. **Implementation Already Complete**: The core Story 7.17 implementation was already in place in `base.py` (lines 47-77, 164-165, 331-456, 807-817) and `tracker.py` (line 31). The implementation includes:
   - `ATTCK_TECHNIQUE_TOOL_MAP` constant mapping ATT&CK IDs to tool categories
   - `__active_strategy` property for storing Director strategies
   - `_handle_strategy_update()` method for processing incoming strategies
   - `_get_strategy_context()` for LLM prompt enrichment
   - `_is_target_avoided()` for filtering avoid_targets
   - `_get_technique_tools()` for technique-to-tool mapping
   - Strategy context injection in `_build_tool_selection_prompt()`
   - "director_strategy" signal type in DecisionContextTracker

2. **Test Suite Created**: Comprehensive test coverage added:
   - 29 unit tests in `tests/unit/agents/test_strategy_handling.py`
   - 18 integration tests in `tests/integration/agents/test_feedback_loop.py`
   - 10 e2e tests in `tests/e2e/test_director_feedback_loop.py`
   - Total: 57 tests, all passing

3. **Test Fixes Applied**:
   - Fixed `EmergentPattern` fixture (metadata → recommended_actions)
   - Fixed agent_id format (must be valid UUID)
   - Fixed target validation (must be valid IP/URL/hostname)
   - Fixed EventBus initialization (requires redis_client parameter)
   - Added edge case tests for 100% coverage of Story 7.17 code

### File List

**Modified Files:**
- `tests/unit/agents/test_strategy_handling.py` - Fixed fixture and added 5 edge case tests

**New Files:**
- `tests/integration/agents/test_feedback_loop.py` - 18 integration tests for AC #6
- `tests/e2e/test_director_feedback_loop.py` - 10 e2e tests for AC #7

**Pre-existing Implementation (verified working):**
- `src/cyberred/agents/base.py` - Strategy handling methods (lines 331-456, 807-817)
- `src/cyberred/orchestration/emergence/tracker.py` - director_strategy signal type (line 31)
- `src/cyberred/orchestration/emergence/strategy.py` - EmergentStrategy dataclass
