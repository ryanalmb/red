# Story 6.3: RAG Query Interface

Status: done

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD methodology at all times. All tasks marked [RED], [GREEN], [REFACTOR] must be followed explicitly. Each task must have a failing test before implementation.

> [!NOTE]
> **DEPENDENCY:** This story requires Stories 6.1 (LanceDB Vector Store Setup) and 6.2 (ATT&CK-BERT Embedding Model) to be complete. Uses `RAGStore.search()` and `RAGEmbeddings.encode()`.

> [!CAUTION]
> **Epic 5 Action Items MUST BE APPLIED:**
> - **AI-2:** Maintain story status sync between file and sprint-status.yaml
> - **AI-4:** Reduce verbose boilerplate — keep method signatures, remove full implementations in Dev Notes

## Story

As an **agent**,
I want **a semantic search interface for methodology retrieval**,
So that **I can find relevant techniques when standard approaches fail (FR76)**.

## Acceptance Criteria

1. **Given** Stories 6.1 and 6.2 are complete
   **When** I call `rag.query("lateral movement techniques for Windows Server 2022")`
   **Then** query is embedded using ATT&CK-BERT
   **And** similarity search returns top-k results (default: 5)
   **And** results include: text, source, technique_ids, score (relevance)
   **And** results are sorted by score descending

2. **Given** the RAG query interface
   **When** I call `rag.query(text, top_k=10)`
   **Then** it returns up to 10 results

3. **Given** the RAG query interface
   **When** I call `rag.query(text, timeout=5.0)`
   **Then** query timeout is configurable (default: 10s)
   **And** `RAGQueryTimeout` exception raised if exceeded

4. **Given** the RAG query interface
   **When** I call `rag.query(text, filter_source="hacktricks")`
   **Then** results are filtered to only include chunks from that source

5. **Given** the RAG query interface
   **When** I call `rag.query(text, filter_content_type=ContentType.PAYLOAD)`
   **Then** results are filtered to only include chunks of that type

6. **Given** integration tests
   **When** I run them with a populated store
   **Then** queries return relevant methodologies
   **And** results are correctly sorted by relevance

## Tasks / Subtasks

### Phase 0: Setup [BLUE]

- [x] Task 0.1: Verify dependencies
  - [x] Confirm Stories 6.1 and 6.2 are complete (check sprint-status.yaml)
  - [x] Verify: `python -c "from cyberred.rag import RAGStore, RAGEmbeddings"`

- [x] Task 0.2: Create module structure
  - [x] Create `src/cyberred/rag/query.py`
  - [x] Create `tests/unit/rag/test_query.py`
  - [x] Create `tests/integration/rag/test_query.py`

---

### Phase 1: RAGSearchResult Improvement [RED → GREEN → REFACTOR]

#### 1A: Enhance RAGSearchResult Model (AC: 1)

- [x] Task 1.1: Update RAGSearchResult dataclass
  - [x] **[RED]** Write failing test: `RAGSearchResult.content_type` is of type `ContentType` (Enum)
  - [x] **[GREEN]** Update `RAGSearchResult` in `src/cyberred/rag/models.py`:
    - Change `content_type: str` to `content_type: ContentType`
    - Ensure `from_dict`/`to_dict` handle Enum serialization correctly
  - [x] **[REFACTOR]** Add docstring referencing FR83

---

### Phase 2: RAGQueryInterface Core [RED → GREEN → REFACTOR]

#### 2A: Query Initialization (AC: 1, 2)

- [x] Task 2.1: Implement RAGQueryInterface class
  - [x] **[RED]** Write failing test: `RAGQueryInterface(store, embeddings)` initializes
  - [x] **[RED]** Write failing test: `query(text)` returns `List[RAGSearchResult]`
  - [x] **[RED]** Write failing test: `query(text)` embeds text using ATT&CK-BERT
  - [x] **[GREEN]** Implement `RAGQueryInterface.__init__()`:
    ```python
    class RAGQueryInterface:
        DEFAULT_TOP_K = 5
        DEFAULT_TIMEOUT = 10.0
        
        def __init__(
            self, 
            store: RAGStore, 
            embeddings: RAGEmbeddings
        ) -> None:
            self._store = store
            self._embeddings = embeddings
    ```
  - [x] **[REFACTOR]** Add structlog logging for query operations

#### 2B: Query Method (AC: 1, 2, 4, 5)

- [x] Task 2.2: Implement async query method
  - [x] **[RED]** Write failing test: `query(text, top_k=10)` returns up to 10 results
  - [x] **[RED]** Write failing test: results are sorted by score descending
  - [x] **[RED]** Write failing test: `query(text, filter_source="hacktricks")` filters by source
  - [x] **[RED]** Write failing test: `query(text, filter_content_type=ContentType.PAYLOAD)` filters by type
  - [x] **[GREEN]** Implement `query()`:
    ```python
    async def query(
        self,
        text: str,
        top_k: int = 5,
        timeout: float = 10.0,
        filter_source: Optional[str] = None,
        filter_content_type: Optional[ContentType] = None,
    ) -> List[RAGSearchResult]:
        """Semantic search for methodology retrieval.
        
        Args:
            text: Query text (embedded via ATT&CK-BERT)
            top_k: Maximum results to return (default: 5)
            timeout: Query timeout in seconds (default: 10.0)
            filter_source: Optional filter by source name
            filter_content_type: Optional filter by ContentType enum
            
        Returns:
            List of RAGSearchResult sorted by score descending
            
        Raises:
            RAGQueryTimeout: If query exceeds timeout
        """
    ```
  - [x] **[REFACTOR]** Add query timing logs for performance monitoring

---

### Phase 3: Timeout Handling [RED → GREEN → REFACTOR]

#### 3A: Query Timeout (AC: 3)

- [x] Task 3.1: Implement timeout mechanism
  - [x] **[RED]** Write failing test: default timeout is 10.0 seconds
  - [x] **[RED]** Write failing test: `RAGQueryTimeout` raised when timeout exceeded
  - [x] **[RED]** Write failing test: custom timeout (5.0s) is respected
  - [x] **[GREEN]** Implement timeout using `asyncio.wait_for()`:
    ```python
    from cyberred.rag.exceptions import RAGQueryTimeout
    
    async def query(self, text: str, ..., timeout: float = 10.0) -> List[RAGResult]:
        try:
            return await asyncio.wait_for(
                self._execute_query(text, top_k, filter_source, filter_content_type),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            log.warning("rag_query_timeout", query=text[:50], timeout=timeout)
            raise RAGQueryTimeout(f"Query timed out after {timeout}s")
    ```
  - [x] **[GREEN]** Add `RAGQueryTimeout` exception to `src/cyberred/rag/exceptions.py`
  - [x] **[REFACTOR]** Add timeout to structlog context

---

### Phase 4: Verification [BLUE]

#### 4A: Result Integrity (AC: 1)

- [x] Task 4.1: Verify Search Result Propagation
  - [x] Verify `_execute_query` passes through `RAGSearchResult` objects from store correctly
  - [x] Verify `content_type` is correctly preserved as Enum in results
  - [x] **[REFACTOR]** Add query result count to logs

---

### Phase 5: Module Exports [RED → GREEN]

#### 5A: Configure Module Exports (AC: 6)

- [x] Task 5.1: Update module __init__.py
  - [x] **[RED]** Write test: `from cyberred.rag import RAGQueryInterface` works
  - [x] **[GREEN]** Update `src/cyberred/rag/__init__.py`:
    ```python
    from cyberred.rag.query import RAGQueryInterface
    from cyberred.rag.exceptions import RAGQueryTimeout
    
    __all__ = [
        "RAGStore",
        "RAGChunk", 
        "RAGSearchResult",
        "RAGStoreStats",
        "ContentType",
        "RAGEmbeddings",
        "RAGQueryInterface",  # NEW
        "RAGQueryTimeout",    # NEW
    ]
    ```

---

### Phase 6: Integration Tests [RED → GREEN]

- [x] Task 6.1: Create integration tests
  - [x] Create `tests/integration/rag/test_query.py`
  - [x] **[RED]** Write test: query returns relevant results from populated store
  - [x] **[RED]** Write test: query with filters returns filtered results
  - [x] **[RED]** Write test: empty store returns empty list
  - [x] **[GREEN]** Implement tests with temporary store fixtures
  - [x] **[REFACTOR]** Add `@pytest.mark.integration` marker

---

### Phase 7: Coverage & Documentation [BLUE]

- [x] Task 7.1: Verify 100% coverage
  - [x] Run: `pytest tests/unit/rag/test_query.py --cov=src/cyberred/rag/query --cov-report=term-missing`
  - [x] Ensure no untested branches

- [x] Task 7.2: Update Dev Agent Record
  - [x] Fill in agent model and completion notes
  - [x] Run full test suite: `pytest tests/unit/rag/ tests/integration/rag/ -v --tb=short`
  - [x] Update story status to `done`

## Dev Notes

### Architecture Reference

From [architecture.md#L274-L330](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L274-L330):

**RAG Escalation Layer Integration:**
- Trigger conditions: Intelligence aggregator returns no exploits, agent fails 3+ attempts, Director requests pivot
- Query interface provides semantic search over ~70K vectors
- Results include ATT&CK technique IDs for kill chain correlation (FR84)

**Stack:**
- Vector DB: LanceDB (embedded, no server, disk-based)
- Embedding: ATT&CK-BERT (CPU-only)
- Fallback: all-mpnet-base-v2

### Project Structure (per Architecture)

```
src/cyberred/rag/
├── __init__.py          # Module exports (update)
├── store.py             # RAGStore class (Story 6.1 ✅)
├── models.py            # RAGChunk, RAGSearchResult, ContentType (UPDATE)
├── embeddings.py        # RAGEmbeddings class (Story 6.2 ✅)
├── query.py             # RAGQueryInterface class (THIS STORY)
├── exceptions.py        # RAGQueryTimeout (NEW)
└── ingest.py            # Document ingestion pipeline (Story 6.4)

tests/unit/rag/
├── test_store.py        # (Story 6.1 ✅)
├── test_models.py       # (Story 6.1 ✅)
├── test_embeddings.py   # (Story 6.2 ✅)
└── test_query.py        # (THIS STORY)

tests/integration/rag/
├── test_store.py        # (Story 6.1 ✅)
├── test_embeddings.py   # (Story 6.2 ✅)
└── test_query.py        # (THIS STORY)
```

### Existing Code Patterns to Follow

**From RAGStore.search()** in [store.py](file:///root/red/src/cyberred/rag/store.py):

```python
async def search(
    self, 
    embedding: List[float], 
    top_k: int = 5,
    filter_source: Optional[str] = None,
    filter_content_type: Optional[str] = None,
) -> List[RAGSearchResult]:
```

**From RAGEmbeddings.encode()** in [embeddings.py](file:///root/red/src/cyberred/rag/embeddings.py):

```python
def encode(self, text: str) -> List[float]:
    """Encode text to embedding vector."""
```

**Structlog Pattern** from store.py:

```python
import structlog
log = structlog.get_logger()

log.info("rag_query_start", query=text[:50], top_k=top_k)
log.warning("rag_query_timeout", query=text[:50], timeout=timeout)
```

**Test Pattern** from [test_store.py](file:///root/red/tests/unit/rag/test_store.py):

```python
@pytest.mark.unit
class TestRAGQueryInterface:
    """Tests for RAGQueryInterface class."""
    
    def test_query_returns_rag_results(self) -> None:
        """query() returns List[RAGSearchResult]."""
```

### Key Learnings from Stories 6.1 & 6.2

1. **Use structlog for logging** — NOT `print()` statements
2. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases explicitly
3. **Verify coverage claims** — Run `pytest --cov` before marking done
4. **Use pytest markers** — Always include `@pytest.mark.unit`, `@pytest.mark.integration`
5. **Status sync is critical** — Story file status must match sprint-status.yaml
6. **Async methods** — Use `async def` for I/O operations (consistent with store.search)

### Usage Pattern (Integration)

```python
from cyberred.rag import RAGStore, RAGEmbeddings, RAGQueryInterface

# Initialize components
store = RAGStore()
embeddings = RAGEmbeddings()
rag = RAGQueryInterface(store, embeddings)

# Query with defaults
results = await rag.query("lateral movement techniques for Windows Server 2022")

# Query with filters
results = await rag.query(
    "privilege escalation payloads",
    top_k=10,
    filter_content_type=ContentType.PAYLOAD
)

# Query with timeout
results = await rag.query("credential dumping", timeout=5.0)
```

### Forward References

**Story 6.4 (Ingestion)** will populate the store with documents for query testing
**Story 6.9 (Director RAG)** will use `RAGQueryInterface.query()` for strategic pivot
**Story 6.10 (Agent RAG)** will use `RAGQueryInterface.query()` for escalation

### References

- **Epic 6 Overview:** [epics-stories.md#L2378-L2408](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2378-L2408)
- **Story 6.3 Requirements:** [epics-stories.md#L2438-L2460](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2438-L2460)
- **Architecture - RAG Layer:** [architecture.md#L274-L330](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L274-L330)
- **Story 6.1 (LanceDB):** [6-1-lancedb-vector-store-setup.md](file:///root/red/_bmad-output/implementation-artifacts/6-1-lancedb-vector-store-setup.md)
- **Story 6.2 (ATT&CK-BERT):** [6-2-attck-bert-embedding-model.md](file:///root/red/_bmad-output/implementation-artifacts/6-2-attck-bert-embedding-model.md)
- **Epic 5 Retrospective:** [epic-5-retro-2026-01-08.md](file:///root/red/_bmad-output/implementation-artifacts/epic-5-retro-2026-01-08.md)
- **FR76:** System provides RAG layer for advanced methodology retrieval when intelligence layer exhausted
- **FR83:** RAG queries return methodology with metadata (source, date, technique IDs)

## Dev Agent Record

### Agent Model Used

Gemini 2.0 Flash

### Debug Log References

### Completion Notes List

- Implemented `RAGQueryInterface` in `src/cyberred/rag/query.py` with `asyncio.wait_for` timeout support.
- Updated `RAGSearchResult` to use `ContentType` Enum and handle `to_dict`/`from_dict` serialization correctly.
- Created `src/cyberred/rag/exceptions.py` for `RAGQueryTimeout`.
- Updated `src/cyberred/rag/__init__.py` to export new classes.
- Added comprehensive unit tests in `tests/unit/rag/test_query.py`, `tests/unit/rag/test_search_result_enum.py`, and `tests/unit/rag/test_exports.py`.
- Added end-to-end integration tests in `tests/integration/rag/test_query.py` using real embeddings and LanceDB.
- Verified 100% coverage for the new module.

### Code Review Fixes (2026-01-08)

- Added result count logging (`rag_query_complete`)
- Fixed unused class constants (`DEFAULT_TOP_K`, `DEFAULT_TIMEOUT`) - now used in method signature
- Added tests for `DEFAULT_TIMEOUT`, `DEFAULT_TOP_K`, and `top_k` result limiting
- Removed extra blank line
- Fixed false task completion claim

### File List

| Action | File Path |
|--------|-----------|
| [NEW] | `src/cyberred/rag/query.py` |
| [NEW] | `src/cyberred/rag/exceptions.py` |
| [NEW] | `tests/unit/rag/test_query.py` |
| [NEW] | `tests/unit/rag/test_search_result_enum.py` |
| [NEW] | `tests/unit/rag/test_exports.py` |
| [NEW] | `tests/integration/rag/test_query.py` |
| [MODIFY] | `src/cyberred/rag/models.py` (update RAGSearchResult) |
| [MODIFY] | `src/cyberred/rag/__init__.py` (export new classes) |
