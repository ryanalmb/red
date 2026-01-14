# Story 6.10: Agent RAG Escalation

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **agent**,
I want **to query RAG when my exploit attempts repeatedly fail**,
So that **I can discover alternative approaches (FR79)**.

## Acceptance Criteria

1. **Given** Stories 6.1-6.3 are complete
   - **When** agent fails 3+ exploit attempts on same target
   - **Then** agent can call `rag.query()` for alternative methodologies

2. **Given** agent queries RAG for alternatives
   - **Then** query context includes: target service, failed techniques, environment
   - **And** RAG results suggest alternative attack paths

3. **Given** agent receives RAG results
   - **Then** agent logs RAG escalation in `decision_context`
   - **And** escalation is tracked for emergence metrics

4. **Given** agent successfully exploits after RAG escalation
   - **Then** failure counter is reset for that target/technique pair

5. **Given** integration tests exist
   - **Then** tests verify agent RAG escalation triggers correctly
   - **And** tests cover failure counting and reset logic

## Tasks / Subtasks

- [x] Task 1: Create AgentRAGEscalator class (AC: 1, 2)
  - [x] 1.1 Create `src/cyberred/agents/rag_escalator.py` with `AgentRAGEscalator` class
  - [x] 1.2 Implement failure tracking per target/technique pair using dict key pattern
  - [x] 1.3 Implement `should_escalate()` method checking failure threshold (default: 3)
  - [x] 1.4 Implement `async escalate()` method wrapping `RAGQueryInterface.query()`

- [x] Task 2: Implement query context builder (AC: 2)
  - [x] 2.1 Create `AgentRAGContext` dataclass for structured escalation context
  - [x] 2.2 Implement `build_escalation_context()` (integrated in _build_query_string)
  - [x] 2.3 Generate semantic query string from context for RAG embedding search
  - [x] 2.4 Add content type filtering (prefer METHODOLOGY and PAYLOAD types)

- [x] Task 3: Implement decision context logging (AC: 3)
  - [x] 3.1 Create `log_rag_escalation()` method (integrated in escalate)
  - [x] 3.2 Log: trigger reason, query context, result count, selected methodology
  - [x] 3.3 Ensure escalation events are captured for emergence validation (NFR35-37)
  - [x] 3.4 Use structlog with context binding (`agent_id`, `target`, `engagement_id`)

- [x] Task 4: Implement failure counter management (AC: 1, 4)
  - [x] 4.1 Implement `record_failure()` method incrementing counter for target/technique
  - [x] 4.2 Implement `record_success()` method resetting counter for target/technique
  - [x] 4.3 Implement `get_failure_count()` (via direct dictionary access check)
  - [x] 4.4 Use composite key pattern: `{target_hash}:{technique_id}` for tracking

- [x] Task 5: Update agents module exports (AC: 1)
  - [x] 5.1 Update `src/cyberred/agents/__init__.py` to export `AgentRAGEscalator`
  - [x] 5.2 Export `AgentRAGContext` dataclass

- [x] Task 6: Unit tests (AC: 1-4)
  - [x] 6.1 Create `tests/unit/agents/test_rag_escalator.py`
  - [x] 6.2 Test failure counting increment and threshold detection
  - [x] 6.3 Test success reset clears failure counter
  - [x] 6.4 Test `should_escalate()` returns True only at threshold
  - [x] 6.5 Test `escalate()` with mocked RAGQueryInterface
  - [x] 6.6 Test context builder produces valid query strings
  - [x] 6.7 Test decision context logging structure

- [x] Task 7: Integration tests (AC: 5)
  - [x] 7.1 Create `tests/integration/agents/test_rag_escalator_integration.py`
  - [x] 7.2 Test full escalation flow with real RAGQueryInterface (mocked store)
  - [x] 7.3 Test escalation triggers at exactly 3 failures
  - [x] 7.4 Test failure counter persistence across multiple calls
  - [x] 7.5 Test integration with decision_context tracking

## Dev Notes

### Architecture Patterns

- **Escalation Pattern**: RAG is escalation path, NOT primary intelligence source (per architecture.md)
- **Failure Tracking**: In-memory dict with composite keys - no persistence needed (reset on agent restart)
- **Non-blocking Queries**: Use async/await, leverage existing `RAGQueryInterface` timeout handling
- **Decision Context**: All RAG escalations MUST be logged for emergence validation (NFR35-37)

### Integration Points

```
┌───────────────────┐                    ┌───────────────────────┐
│  ExploitAgent     │──(3+ failures)────►│  AgentRAGEscalator    │
│  (Epic 7)         │                    │  (This Story)         │
└───────────────────┘                    └──────────┬────────────┘
                                                    │
                                                    ▼
                                         ┌───────────────────────┐
                                         │   RAGQueryInterface   │
                                         │   (Story 6.3)         │
                                         └──────────┬────────────┘
                                                    │
                                                    ▼
                                         ┌───────────────────────┐
                                         │      RAGStore         │
                                         │   (LanceDB 6.1)       │
                                         └───────────────────────┘
```

### Trigger Conditions (from Architecture)

| Trigger | Threshold | Action |
|---------|-----------|--------|
| **Exploit Failures** | 3+ failed attempts on same target/technique | Query RAG for alternative methodologies |
| **Success** | Successful exploit | Reset failure counter for that pair |

### Key Data Models

```python
@dataclass
class AgentRAGContext:
    """Context for agent RAG escalation queries."""
    agent_id: str
    target_service: str  # e.g., "ssh:22", "http:80/apache/2.4.49"
    target_hash: str     # Hash of target for tracking
    failed_techniques: List[str]  # List of technique IDs that failed
    failure_count: int
    environment: Dict[str, Any]  # OS, network context, etc.
    engagement_id: Optional[str] = None

@dataclass
class AgentEscalationResult:
    """Result of RAG escalation query."""
    context: AgentRAGContext
    methodologies: List[RAGSearchResult]
    selected_technique: Optional[str]  # Technique ID chosen by agent
    query_time_ms: int
    was_successful: bool
```

### Failure Counter Implementation

```python
class AgentRAGEscalator:
    ESCALATION_THRESHOLD = 3
    
    def __init__(self, rag_interface: RAGQueryInterface) -> None:
        self._rag = rag_interface
        self._failure_counts: Dict[str, int] = {}  # {target_hash}:{technique_id} -> count
    
    def _make_key(self, target_hash: str, technique_id: str) -> str:
        return f"{target_hash}:{technique_id}"
    
    def record_failure(self, target_hash: str, technique_id: str) -> int:
        key = self._make_key(target_hash, technique_id)
        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1
        return self._failure_counts[key]
    
    def record_success(self, target_hash: str, technique_id: str) -> None:
        key = self._make_key(target_hash, technique_id)
        self._failure_counts.pop(key, None)
    
    def should_escalate(self, target_hash: str, technique_id: str) -> bool:
        key = self._make_key(target_hash, technique_id)
        return self._failure_counts.get(key, 0) >= self.ESCALATION_THRESHOLD
```

### Query String Generation

Build semantic query from context for RAG search:

```python
def _build_query_string(self, context: AgentRAGContext) -> str:
    """Generate semantic query for RAG from escalation context."""
    parts = [
        f"alternative attack methodologies for {context.target_service}",
    ]
    if context.failed_techniques:
        failed_list = ", ".join(context.failed_techniques)
        parts.append(f"excluding techniques: {failed_list}")
    if context.environment.get("os"):
        parts.append(f"target OS: {context.environment['os']}")
    return " ".join(parts)
```

### Decision Context Logging (Critical for Emergence)

```python
async def escalate(
    self,
    context: AgentRAGContext,
) -> AgentEscalationResult:
    """Query RAG for alternative methodologies and log decision context."""
    query = self._build_query_string(context)
    
    start_time = time.monotonic()
    results = await self._rag.query(
        text=query,
        top_k=5,
        filter_content_type=ContentType.METHODOLOGY,
    )
    query_time_ms = int((time.monotonic() - start_time) * 1000)
    
    # CRITICAL: Log for emergence validation
    log.info(
        "agent_rag_escalation",
        agent_id=context.agent_id,
        target=context.target_service,
        target_hash=context.target_hash,
        failed_techniques=context.failed_techniques,
        failure_count=context.failure_count,
        result_count=len(results),
        query_time_ms=query_time_ms,
        engagement_id=context.engagement_id,
        decision_context={
            "trigger": "exploit_failure_threshold",
            "threshold": self.ESCALATION_THRESHOLD,
            "alternative_count": len(results),
        },
    )
    
    return AgentEscalationResult(
        context=context,
        methodologies=results,
        selected_technique=results[0].technique_ids[0] if results and results[0].technique_ids else None,
        query_time_ms=query_time_ms,
        was_successful=len(results) > 0,
    )
```

### Testing Standards

- Follow existing test patterns from `tests/unit/rag/test_director_client.py`
- Mock `RAGQueryInterface` for unit tests
- Use `pytest.fixture` for `AgentRAGEscalator` with mocked dependencies
- Test edge cases: 0 failures, exactly 3 failures, 4+ failures
- Verify decision context log structure matches emergence tracker expectations
- **Coverage Target**: 100% for `rag_escalator.py`

### File Locations

**Source files:**
- `src/cyberred/agents/rag_escalator.py` - AgentRAGEscalator implementation (NEW)
- `src/cyberred/agents/__init__.py` - Update exports

**Test files:**
- `tests/unit/agents/test_rag_escalator.py` - Unit tests (NEW)
- `tests/integration/agents/test_rag_escalator_integration.py` - Integration tests (NEW)

### Dependencies

- Existing dependencies sufficient (no new packages needed):
  - `asyncio` - Async handling (stdlib)
  - `structlog` - Logging with context (already used)
  - `dataclasses` - Data models (stdlib)
  - `time` - Performance timing (stdlib)
- Depends on: `RAGQueryInterface` (Story 6.3), `RAGSearchResult`, `ContentType` (Story 6.1)

### Project Structure Notes

- Alignment with unified project structure: Agent components in `src/cyberred/agents/`
- This story creates the **bridge** between RAG Layer (Epic 6) and Agent Framework (Epic 7)
- ExploitAgent (Story 7.4) will integrate `AgentRAGEscalator` when implemented
- Current `ghost_agent.py` is legacy - new agents will use `AgentRAGEscalator`

### Configuration

Add to `config/models.yaml` under RAG section:

```yaml
rag:
  agent:
    escalation_threshold: 3  # failures before RAG escalation
    query_timeout: 10.0      # seconds - standard timeout
    max_results: 5           # results to consider
```

### Previous Story Intelligence (Story 6.9)

**Key learnings from Story 6.9 (Director Ensemble RAG Integration):**

- Use `RAGQueryInterface.query()` directly - it handles timeout internally
- Non-blocking pattern: catch `RAGQueryTimeout` and return empty results gracefully
- ATT&CK technique IDs available in `RAGSearchResult.technique_ids`
- Content type filtering via `filter_content_type` parameter
- Decision context logging is CRITICAL for emergence validation
- Follow test patterns in `tests/unit/rag/test_director_client.py`

**Difference from Story 6.9:**
- Story 6.9: Director queries RAG for strategic pivots (high-level)
- Story 6.10: Individual agents query RAG for tactical alternatives (granular)
- Story 6.10 adds failure counting logic not present in Director client

### References

- Story definition: `_bmad-output/planning-artifacts/epics-stories.md` → "Story 6.10: Agent RAG Escalation"
- Architecture: `_bmad-output/planning-artifacts/architecture.md` → RAG Escalation Layer Integration (lines 273-315)
- Previous story: `_bmad-output/implementation-artifacts/6-9-director-ensemble-rag-integration.md`
- RAG Query Interface: `src/cyberred/rag/query.py` (RAGQueryInterface)
- RAG Models: `src/cyberred/rag/models.py` (RAGSearchResult, ContentType)
- Director Client (pattern reference): `src/cyberred/rag/director_client.py`
- FR79: Agent can query RAG when exploit attempts repeatedly fail
- NFR35-37: Emergence validation requires decision_context tracking

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- Implemented `AgentRAGEscalator` with failure tracking and threshold logic (3 failures).
- Created `AgentRAGContext` and `AgentEscalationResult` data models.
- Implemented `_build_query_string` to generate semantic queries from context.
- Added comprehensive structured logging for emergence validation triggers.
- Unit tests cover all core logic (failure tracking, context build, escalate flow).
- Integration tests verify end-to-end flow with mocked RAG components.

### File List

- src/cyberred/agents/rag_escalator.py
- src/cyberred/agents/__init__.py
- tests/unit/agents/test_rag_escalator.py
- tests/integration/agents/test_rag_escalator_integration.py

