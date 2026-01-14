# Story 6.9: Director Ensemble RAG Integration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **Director Ensemble**,
I want **to query RAG for strategic pivot methodologies**,
so that **I can provide advanced guidance when standard intelligence fails (FR78)**.

## Acceptance Criteria

1. **Given** Stories 6.1-6.3 are complete and Director Ensemble exists
   - **When** Director requests strategy pivot
   - **Then** Director can call `rag.query()` for methodology suggestions

2. **Given** Director receives RAG results
   - **Then** RAG results are incorporated into synthesis
   - **And** results include ATT&CK technique IDs for kill chain correlation (FR84)

3. **Given** RAG query is slow or timing out
   - **Then** RAG query is non-blocking (agents continue if RAG slow)
   - **And** Director receives partial results or graceful degradation

4. **Given** Director needs methodology guidance
   - **When** triggered by: repeated swarm failures, phase transition, or operator request
   - **Then** appropriate query context is constructed
   - **And** results are formatted into actionable agent guidance

5. **Given** integration tests exist
   - **Then** tests verify Director RAG integration end-to-end
   - **And** tests cover timeout scenarios and partial result handling

## Tasks / Subtasks

- [x] Task 1: Create DirectorRAGClient interface (AC: 1, 2)
  - [x] 1.1 Create `src/cyberred/rag/director_client.py` with `DirectorRAGClient` class
  - [x] 1.2 Implement `async query_strategy_pivot()` method wrapping `RAGQueryInterface`
  - [x] 1.3 Add ATT&CK technique ID extraction and kill chain phase correlation
  - [x] 1.4 Format RAG results into Director-consumable `StrategyPivotResult` dataclass

- [x] Task 2: Implement non-blocking query mechanism (AC: 3)
  - [x] 2.1 Create `async query_with_fallback()` with configurable timeout (default: 5s for Director)
  - [x] 2.2 Implement graceful degradation returning empty results on timeout (no exception)
  - [x] 2.3 Add `fire_and_forget_query()` for fully async background queries
  - [x] 2.4 Log RAG escalation events for metrics and debugging

- [x] Task 3: Implement trigger-based query context builder (AC: 4)
  - [x] 3.1 Create `RAGQueryContext` dataclass for structured query context
  - [x] 3.2 Implement `build_swarm_failure_context()` for repeated failure scenario
  - [x] 3.3 Implement `build_phase_transition_context()` for phase change scenario
  - [x] 3.4 Implement `build_operator_request_context()` for manual pivot request
  - [x] 3.5 Add query enrichment with current engagement state

- [x] Task 4: Implement result formatting for Director synthesis (AC: 2, 4)
  - [x] 4.1 Create `format_for_director_synthesis()` to transform RAG results
  - [x] 4.2 Group results by ATT&CK tactic (recon, initial-access, execution, etc.)
  - [x] 4.3 Prioritize results by relevance score and technique applicability
  - [x] 4.4 Generate actionable guidance text for agent consumption

- [x] Task 5: Update RAG module exports (AC: 1)
  - [x] 5.1 Update `src/cyberred/rag/__init__.py` to export `DirectorRAGClient`
  - [x] 5.2 Export `StrategyPivotResult` and `RAGQueryContext` models

- [x] Task 6: Unit tests (AC: 1-4)
  - [x] 6.1 Create `tests/unit/rag/test_director_client.py`
  - [x] 6.2 Test `query_strategy_pivot()` with mocked RAGQueryInterface
  - [x] 6.3 Test timeout handling and graceful degradation
  - [x] 6.4 Test context builders for each trigger type
  - [x] 6.5 Test result formatting and ATT&CK grouping

- [x] Task 7: Integration tests (AC: 5)
  - [x] 7.1 Create `tests/integration/rag/test_director_rag_integration.py`
  - [x] 7.2 Test full query flow with real RAGStore (if populated)
  - [x] 7.3 Test timeout scenarios with artificially slow queries
  - [x] 7.4 Test fire-and-forget query completion

## Dev Notes

### Architecture Patterns

- **Client Adapter Pattern**: `DirectorRAGClient` wraps `RAGQueryInterface` with Director-specific behavior
- **Non-blocking by Default**: All Director RAG queries must not block agent execution
- **Graceful Degradation**: Timeouts return empty results, not exceptions (Director continues without RAG)
- **RAG as Escalation**: RAG is NOT the primary intelligence source - it's used when standard intelligence fails

### Integration Points

```
┌───────────────────┐                    ┌───────────────────┐
│ Director Ensemble │──(strategy pivot)─►│  DirectorRAGClient │
│   (Epic 8)        │                    │  (This Story)      │
└───────────────────┘                    └─────────┬─────────┘
                                                   │
                                                   ▼
                                         ┌───────────────────┐
                                         │  RAGQueryInterface │
                                         │  (Story 6.3)       │
                                         └─────────┬─────────┘
                                                   │
                                                   ▼
                                         ┌───────────────────┐
                                         │    RAGStore       │
                                         │  (LanceDB 6.1)    │
                                         └───────────────────┘
```

### Trigger Conditions (from Architecture)

| Trigger | When | Query Focus |
|---------|------|-------------|
| **Swarm Failures** | 3+ failed exploit attempts on same target | Alternative attack techniques for target service |
| **Phase Transition** | All recon targets exhausted, moving to exploitation | Methodologies for discovered services |
| **Operator Request** | Manual "pivot strategy" command via TUI | General or specified methodology area |

### Key Data Models

```python
@dataclass
class RAGQueryContext:
    """Context for Director RAG queries."""
    trigger: Literal["swarm_failure", "phase_transition", "operator_request"]
    target_service: Optional[str] = None
    failed_techniques: List[str] = field(default_factory=list)
    current_phase: Optional[str] = None
    environment: Dict[str, Any] = field(default_factory=dict)
    operator_hint: Optional[str] = None

@dataclass
class StrategyPivotResult:
    """Formatted RAG results for Director synthesis."""
    query_context: RAGQueryContext
    methodologies: List[RAGSearchResult]
    techniques_by_tactic: Dict[str, List[str]]  # tactic -> technique IDs
    actionable_guidance: str
    query_time_ms: int
    was_timeout: bool = False
```

### ATT&CK Tactic Mapping

Group results by kill chain phase for Director synthesis:

```python
TACTIC_PRIORITY = [
    "reconnaissance",
    "resource-development", 
    "initial-access",
    "execution",
    "persistence",
    "privilege-escalation",
    "defense-evasion",
    "credential-access",
    "discovery",
    "lateral-movement",
    "collection",
    "command-and-control",
    "exfiltration",
    "impact",
]
```

### Non-Blocking Implementation

```python
async def query_with_fallback(
    self,
    context: RAGQueryContext,
    timeout: float = 5.0,
) -> StrategyPivotResult:
    """Query RAG with timeout fallback - never blocks Director."""
    try:
        results = await asyncio.wait_for(
            self._execute_query(context),
            timeout=timeout
        )
        return self._format_results(context, results, was_timeout=False)
    except asyncio.TimeoutError:
        log.warning("director_rag_timeout", context=context, timeout=timeout)
        return StrategyPivotResult(
            query_context=context,
            methodologies=[],
            techniques_by_tactic={},
            actionable_guidance="RAG query timed out - proceeding with available intelligence",
            query_time_ms=int(timeout * 1000),
            was_timeout=True,
        )
```

### Testing Standards

- Follow existing test patterns from `test_query.py` and `test_store.py`
- Mock `RAGQueryInterface` for unit tests
- Use `tmp_path` fixture for isolated test directories
- Test timeout scenarios using `asyncio.sleep()` in mocked queries
- Verify ATT&CK technique extraction and tactic grouping
- **Coverage Target**: 100% for `director_client.py`

### File Locations

**Source files:**
- `src/cyberred/rag/director_client.py` - DirectorRAGClient implementation
- `src/cyberred/rag/__init__.py` - Update exports

**Test files:**
- `tests/unit/rag/test_director_client.py` - Unit tests
- `tests/integration/rag/test_director_rag_integration.py` - Integration tests

### Dependencies

- Existing dependencies sufficient (no new packages needed):
  - `asyncio` - Async/timeout handling (stdlib)
  - `structlog` - Logging (already used)
  - `dataclasses` - Data models (stdlib)
- Depends on: `RAGQueryInterface` (Story 6.3), `RAGSearchResult` (Story 6.1)

### Project Structure Notes

- Alignment with unified project structure: All RAG components in `src/cyberred/rag/`
- This story creates the **bridge** between RAG Layer (Epic 6) and Director Ensemble (Epic 8)
- Director Ensemble (Story 8.1+) will import `DirectorRAGClient` when implemented

### Configuration

Add to `config/models.yaml` under RAG section:

```yaml
rag:
  director:
    query_timeout: 5.0  # seconds - shorter than default 10s for responsiveness
    max_results: 10     # more results for synthesis
    fallback_on_timeout: true
```

### References

- Story definition: `_bmad-output/planning-artifacts/epics-stories.md` → "Story 6.9: Director Ensemble RAG Integration"
- Architecture: `_bmad-output/planning-artifacts/architecture.md` → RAG Escalation Layer Integration section (lines 273-315)
- Previous story: `_bmad-output/implementation-artifacts/6-8-payloadsallthethings-lolbas-gtfobins-integration.md`
- RAG Query Interface: `src/cyberred/rag/query.py` (RAGQueryInterface)
- RAG Models: `src/cyberred/rag/models.py` (RAGSearchResult, ContentType)
- RAG Store: `src/cyberred/rag/store.py` (RAGStore)
- Director Ensemble (future): `src/cyberred/llm/ensemble.py` (Epic 8, currently backlog)
- FR78: Director can query RAG for strategic pivot methodologies
- FR84: Results include ATT&CK technique IDs for kill chain correlation

## Dev Agent Record

### Agent Model Used

OpenAI GPT-4 family (via Rovo Dev)

### Debug Log References

- Unit tests: `tests/unit/rag/test_director_client.py`
- Integration tests: `tests/integration/rag/test_director_rag_integration.py`

### Completion Notes List

- Implemented `DirectorRAGClient` adapter over `RAGQueryInterface` with Director-safe, non-blocking behavior.
- Added `RAGQueryContext` and `StrategyPivotResult` dataclasses to carry structured context + formatted output.
- Implemented graceful timeout/fallback behavior (timeouts degrade to empty results rather than raising).
- Implemented ATT&CK tactic grouping (from `RAGSearchResult.metadata["tactics"]`) and a coarse tactic→kill-chain phase correlation.
- Added result formatting into Director-consumable `guidance_text` including top results per tactic and technique IDs.
- Exported new Director RAG types via `cyberred.rag` package.

### File List

- `src/cyberred/rag/director_client.py` (new)
- `src/cyberred/rag/__init__.py` (updated exports)
- `tests/unit/rag/test_director_client.py` (new)
- `tests/integration/rag/test_director_rag_integration.py` (new)

## Change Log

- 2026-01-10: Implemented Director Ensemble RAG integration (Story 6.9) with non-blocking queries, tactic grouping, phase correlation, and tests. Verified 100% coverage for `src/cyberred/rag/director_client.py`.

