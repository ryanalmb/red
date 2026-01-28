# Story 7.15: Emergent Attack Strategy Triggering

Status: done 

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **agent**,
I want **to trigger emergent attack strategies based on collective findings**,
So that **the swarm discovers attack paths no individual agent could find (FR6)**.

## Acceptance Criteria

1. **Given** Stories 7.1-7.8 are complete
   - **When** multiple agents publish related findings
   - **Then** pattern detection identifies emergent opportunities

2. **Given** pattern detection has identified an emergent opportunity
   - **When** `EmergentPatternDetector.detect()` is called with recent findings
   - **Then** detector identifies patterns such as:
     - Multiple agents found same service version → prioritize exploitation
     - Credential found + open SMB → lateral movement opportunity
     - Multiple failed exploits on same target → trigger RAG escalation
     - Service enumeration complete → trigger vulnerability correlation

3. **Given** an emergent pattern has been detected
   - **When** Director synthesizes collective insights
   - **Then** strategy is published to `strategies:{engagement_id}` channel
   - **And** strategy contains: pattern_type, confidence, recommended_actions, contributing_findings

4. **Given** a strategy has been published
   - **When** agents receive strategy via their `strategies:{engagement_id}` subscription
   - **Then** agents incorporate strategy into their next `select_tool()` decisions
   - **And** agents log the strategy_id in their `decision_context`

5. **Given** emergent paths are discovered through pattern detection
   - **When** an agent acts on an emergent strategy
   - **Then** the action is logged with full provenance (pattern_id, contributing_finding_ids)
   - **And** provenance is traceable via DecisionContextTracker

6. **Given** the emergence validation framework exists (Stories 7.9-7.11)
   - **When** emergence tests run
   - **Then** emergent strategy triggering contributes to novel attack chains
   - **And** patterns are validated to produce >20% improvement over isolated agents

## Tasks / Subtasks

- [ ] Task 1: Create EmergentPattern dataclass (AC: #2, #5)
  - [ ] 1.1: Define EmergentPattern with fields: id, pattern_type, confidence, contributing_findings, recommended_actions, timestamp
  - [ ] 1.2: Define PatternType enum: SERVICE_CORRELATION, CREDENTIAL_PIVOT, FAILED_EXPLOIT_ESCALATION, ENUMERATION_COMPLETE, CROSS_AGENT_DISCOVERY
  - [ ] 1.3: Add validation and serialization methods (to_json, from_json)
  - [ ] 1.4: Write unit tests for EmergentPattern model

- [ ] Task 2: Create EmergentPatternDetector class (AC: #1, #2)
  - [ ] 2.1: Implement detector with configurable pattern rules
  - [ ] 2.2: Implement `detect(findings: list[Finding]) -> list[EmergentPattern]` method
  - [ ] 2.3: Implement SERVICE_CORRELATION pattern (same service version across targets)
  - [ ] 2.4: Implement CREDENTIAL_PIVOT pattern (credential + accessible service)
  - [ ] 2.5: Implement FAILED_EXPLOIT_ESCALATION pattern (3+ failures → RAG)
  - [ ] 2.6: Implement ENUMERATION_COMPLETE pattern (recon findings trigger exploit phase)
  - [ ] 2.7: Implement CROSS_AGENT_DISCOVERY pattern (findings from different agent types correlate)
  - [ ] 2.8: Write unit tests for each pattern type

- [ ] Task 3: Create EmergentStrategy dataclass (AC: #3)
  - [ ] 3.1: Define EmergentStrategy with fields: id, engagement_id, pattern, objectives, recommended_techniques, avoid_targets, confidence, timestamp
  - [ ] 3.2: Add serialization for Redis pub/sub compatibility
  - [ ] 3.3: Write unit tests for EmergentStrategy model

- [ ] Task 4: Create EmergentStrategyPublisher class (AC: #3, #4)
  - [ ] 4.1: Implement publisher that converts patterns to strategies
  - [ ] 4.2: Implement `publish_strategy(pattern: EmergentPattern, engagement_id: str)` method
  - [ ] 4.3: Integrate with EventBus for `strategies:{engagement_id}` publication
  - [ ] 4.4: Add confidence threshold filter (only publish patterns with confidence > 0.6)
  - [ ] 4.5: Write unit tests for publisher

- [ ] Task 5: Create EmergentStrategyAggregator class (AC: #1, #2, #3)
  - [ ] 5.1: Implement aggregator that subscribes to findings channels
  - [ ] 5.2: Implement sliding window for recent findings (default: 5 minutes)
  - [ ] 5.3: Implement periodic detection cycle (default: 30 seconds)
  - [ ] 5.4: Integrate detector and publisher into cohesive pipeline
  - [ ] 5.5: Write unit tests for aggregator lifecycle

- [ ] Task 6: Update StigmergicAgent to handle emergent strategies (AC: #4)
  - [ ] 6.1: Extend `on_signal()` to parse EmergentStrategy messages
  - [ ] 6.2: Store active strategy in agent state for `select_tool()` context
  - [ ] 6.3: Update `select_tool()` to consider strategy.recommended_techniques
  - [ ] 6.4: Log strategy_id in decision_context when acting on strategy
  - [ ] 6.5: Write unit tests for strategy handling in agent

- [ ] Task 7: Integrate with DecisionContextTracker (AC: #5)
  - [ ] 7.1: Add "emergent_pattern" signal type to SIGNAL_TYPE_WEIGHTS (weight: 0.95)
  - [ ] 7.2: Record pattern_id when agent receives emergent strategy
  - [ ] 7.3: Ensure provenance chain: pattern_id → strategy_id → action_id
  - [ ] 7.4: Write unit tests for provenance tracking

- [ ] Task 8: Write integration tests (AC: #1, #2, #3, #4, #6)
  - [ ] 8.1: Test pattern detection with multiple correlated findings
  - [ ] 8.2: Test strategy publication and agent reception
  - [ ] 8.3: Test end-to-end: findings → pattern → strategy → agent action
  - [ ] 8.4: Test emergence contribution (novel chains from emergent strategies)

## Dev Notes

### Architecture Context

This story implements the "Emergence = whole > sum of parts" principle from the architecture. The key insight is that patterns across agent findings can reveal attack opportunities that no single agent would discover.

**Pattern Detection Philosophy:**
- Patterns emerge from correlating findings across multiple agents
- Each pattern type represents a specific tactical opportunity
- Confidence scoring prevents false positives from triggering strategies
- The Director (Epic 8) will eventually consume these patterns for higher-level synthesis

**Integration Points:**
- `EventBus` for findings subscription and strategy publication
- `DecisionContextTracker` for NFR37 provenance tracking
- `StigmergicAgent.on_signal()` for strategy reception
- `StigmergicAgent.select_tool()` for strategy-influenced tool selection

### Relevant Architecture Patterns

From architecture.md:
- Stigmergic coordination via Redis Pub/Sub (lines 366-438)
- Finding model with 10 required fields (core/models.py)
- EventBus channel patterns: `findings:{target_hash}:{type}`, `strategies:{engagement_id}`
- Decision context tracking for NFR37 (100% action traceability)

### Source Tree Components

**New Files:**
- `src/cyberred/orchestration/emergence/patterns.py` - EmergentPattern, PatternType, EmergentPatternDetector
- `src/cyberred/orchestration/emergence/strategy.py` - EmergentStrategy, EmergentStrategyPublisher, EmergentStrategyAggregator

**Modified Files:**
- `src/cyberred/orchestration/emergence/__init__.py` - Export new classes
- `src/cyberred/orchestration/emergence/tracker.py` - Add "emergent_pattern" signal type
- `src/cyberred/agents/base.py` - Extend on_signal() and select_tool() for strategy handling

**Test Files:**
- `tests/unit/orchestration/emergence/test_emergent_patterns.py`
- `tests/unit/orchestration/emergence/test_emergent_strategy.py`
- `tests/integration/orchestration/emergence/test_emergent_strategy_integration.py`

### Pattern Type Specifications

| Pattern Type | Trigger Condition | Confidence Calculation | Recommended Action |
|--------------|-------------------|------------------------|-------------------|
| SERVICE_CORRELATION | 2+ agents report same service/version on different targets | 0.7 + (0.1 * additional_matches) | Prioritize known exploits for service |
| CREDENTIAL_PIVOT | Credential finding + accessible service (SMB/SSH/RDP) | 0.8 if service accessible | Attempt authentication with credential |
| FAILED_EXPLOIT_ESCALATION | 3+ exploit failures on same target within 5 min | 0.9 (high confidence) | Trigger RAG escalation per Story 6.10 |
| ENUMERATION_COMPLETE | Recon coverage >80% of scope | 0.6 + (0.1 * coverage_pct) | Transition to exploit phase |
| CROSS_AGENT_DISCOVERY | Findings from 2+ different agent roles correlate | 0.75 base | Spawn specialized agent for intersection |

### Testing Standards

- Unit tests: 100% coverage of new modules
- Integration tests: Real Redis pub/sub with test EventBus
- Emergence tests: Verify patterns contribute to novel attack chains
- Use pytest fixtures from `tests/conftest.py`
- Follow existing patterns in `tests/unit/orchestration/emergence/`

### Project Structure Notes

- All emergence-related code in `src/cyberred/orchestration/emergence/`
- Follow existing dataclass patterns (frozen where appropriate)
- Use structlog for all logging with component binding
- Export all public classes via `__init__.py`

### References

- [Source: _bmad-output/planning-artifacts/epics-stories.md#Story 7.15] - Original story definition
- [Source: _bmad-output/planning-artifacts/architecture.md#lines 366-438] - Stigmergic coordination
- [Source: src/cyberred/orchestration/emergence/tracker.py] - DecisionContextTracker patterns
- [Source: src/cyberred/orchestration/emergence/metrics.py] - EmergenceMetrics patterns
- [Source: src/cyberred/agents/base.py#lines 150-180] - Strategy subscription in StigmergicAgent
- [Source: src/cyberred/core/models.py#Finding] - Finding dataclass reference
- [Source: src/cyberred/core/events.py] - EventBus patterns

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
