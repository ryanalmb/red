# Story 6.2: ATT&CK-BERT Embedding Model

Status: done

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD methodology at all times. All tasks marked [RED], [GREEN], [REFACTOR] must be followed explicitly. Each task must have a failing test before implementation.

> [!NOTE]
> **DEPENDENCY:** This story requires Story 6.1 (LanceDB Vector Store Setup) to be complete. `RAGStore` expects embeddings of dimension 768.

> [!CAUTION]
> **Epic 5 Action Items MUST BE APPLIED:**
> - **AI-2:** Maintain story status sync between file and sprint-status.yaml
> - **AI-4:** Reduce verbose boilerplate — keep method signatures, remove full implementations in Dev Notes

## Story

As a **developer**,
I want **ATT&CK-BERT embeddings optimized for cybersecurity domain**,
So that **methodology queries have high relevance for offensive security (FR80)**.

## Acceptance Criteria

1. **Given** the embedding module is initialized
   **When** I call `embeddings.encode("lateral movement techniques")`
   **Then** ATT&CK-BERT model generates a 768-dimensional embedding vector
   **And** the model runs on CPU only (no GPU required)

2. **Given** ATT&CK-BERT model is unavailable (not downloaded or corrupted)
   **When** I call `embeddings.encode(text)`
   **Then** fallback to `all-mpnet-base-v2` model
   **And** log warning about fallback activation
   **And** return 768-dimensional embedding (matching LanceDB schema)

3. **Given** the embedding model is loaded
   **When** I encode the same text twice
   **Then** the model is cached in memory (not reloaded)
   **And** subsequent calls return instantly

4. **Given** the embedding module
   **When** I call `embeddings.encode(text)` on a typical query (20-50 words)
   **Then** CPU latency is <100ms per query (Gate check)
   **And** the benchmark test verifies this constraint

5. **Given** the embedding module exports
   **When** I import `from cyberred.rag.embeddings import RAGEmbeddings`
   **Then** the class is available
   **And** it integrates with `RAGStore` for embedding dimension compatibility

6. **Given** integration tests
   **When** I run them with a real model
   **Then** embeddings are generated successfully
   **And** they work with LanceDB similarity search

## Tasks / Subtasks

### Phase 0: Setup [BLUE]

- [x] Task 0.1: Add dependencies to pyproject.toml
  - [x] Add `sentence-transformers>=2.2.0` (required for embedding models)
  - [x] Run: `pip install sentence-transformers>=2.2.0`
  - [x] Verify: `python -c "from sentence_transformers import SentenceTransformer; print('OK')"`

- [x] Task 0.2: Create module structure
  - [x] Create `src/cyberred/rag/embeddings.py`
  - [x] Create `tests/unit/rag/test_embeddings.py`
  - [x] Create `tests/integration/rag/test_embeddings.py`

---

### Phase 1: RAGEmbeddings Core [RED → GREEN → REFACTOR]

#### 1A: Model Initialization (AC: 1, 2, 3)

- [x] Task 1.1: Implement RAGEmbeddings class
  - [x] **[RED]** Write failing test: `RAGEmbeddings()` initializes with ATT&CK-BERT as primary model
  - [x] **[RED]** Write failing test: `RAGEmbeddings()` falls back to all-mpnet-base-v2 if primary unavailable
  - [x] **[RED]** Write failing test: fallback logs warning via structlog
  - [x] **[GREEN]** Implement `RAGEmbeddings` class with model loading:
    ```python
    class RAGEmbeddings:
        PRIMARY_MODEL = "basel/ATTACK-BERT"
        FALLBACK_MODEL = "sentence-transformers/all-mpnet-base-v2"
        EMBEDDING_DIM = 768
        
        def __init__(self) -> None:
            self._model: Optional[SentenceTransformer] = None
            self._model_name: Optional[str] = None
    ```
  - [x] **[REFACTOR]** Add lazy loading (model loads on first `encode()` call)

#### 1B: Model Caching (AC: 3)

- [x] Task 1.2: Implement model caching
  - [x] **[RED]** Write failing test: model loads only once (singleton pattern)
  - [x] **[RED]** Write failing test: second `encode()` call reuses cached model
  - [x] **[GREEN]** Implement lazy loading with instance caching
  - [x] **[REFACTOR]** Add `is_loaded` property for introspection

---

### Phase 2: Encode Method [RED → GREEN → REFACTOR]

#### 2A: Single Text Encoding (AC: 1)

- [x] Task 2.1: Implement encode() method
  - [x] **[RED]** Write failing test: `encode(text)` returns List[float] of length 768
  - [x] **[RED]** Write failing test: `encode(text)` works for cybersecurity terminology
  - [x] **[RED]** Write failing test: `encode("")` handles empty string gracefully
  - [x] **[GREEN]** Implement `encode()`:
    ```python
    def encode(self, text: str) -> List[float]:
        """Encode text to embedding vector.
        
        Args:
            text: Text to encode (trimmed to 512 tokens internally)
            
        Returns:
            768-dimensional embedding vector as List[float]
        """
    ```
  - [x] **[REFACTOR]** Add device selection (force CPU)

#### 2B: Batch Encoding (AC: 6)

- [x] Task 2.2: Implement batch encoding
  - [x] **[RED]** Write failing test: `encode_batch(texts)` returns List[List[float]]
  - [x] **[RED]** Write failing test: batch encoding is more efficient than sequential
  - [x] **[GREEN]** Implement `encode_batch()`:
    ```python
    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encode multiple texts efficiently.
        
        Args:
            texts: List of texts to encode
            
        Returns:
            List of 768-dimensional embedding vectors
        """
    ```
  - [x] **[REFACTOR]** Add progress logging for large batches (>100 texts)

---

### Phase 3: Fallback Logic [RED → GREEN → REFACTOR]

#### 3A: Graceful Degradation (AC: 2)

- [x] Task 3.1: Implement fallback mechanism
  - [x] **[RED]** Write failing test: if ATT&CK-BERT load fails, fallback is used
  - [x] **[RED]** Write failing test: fallback produces valid 768-dim embeddings
  - [x] **[RED]** Write failing test: fallback logs `rag_embeddings_fallback_activated` warning
  - [x] **[GREEN]** Implement `_load_model()` with try/except fallback:
    ```python
    def _load_model(self) -> None:
        """Load embedding model with fallback support."""
        try:
            self._model = SentenceTransformer(self.PRIMARY_MODEL, device="cpu")
            self._model_name = self.PRIMARY_MODEL
        except Exception as e:
            log.warning("rag_embeddings_fallback_activated", 
                       primary_model=self.PRIMARY_MODEL, error=str(e))
            self._model = SentenceTransformer(self.FALLBACK_MODEL, device="cpu")
            self._model_name = self.FALLBACK_MODEL
    ```
  - [x] **[REFACTOR]** Add `active_model` property to expose which model is in use

---

### Phase 4: Performance Benchmark [RED → GREEN]

#### 4A: CPU Latency Gate (AC: 4)

- [x] Task 4.1: Create benchmark test
  - [x] **[RED]** Write failing test: `BenchmarkEmbeddings` verifies <100ms per query
  - [x] **[GREEN]** Implement benchmark fixture with timing:
    ```python
    @pytest.mark.integration
    def test_embedding_latency_under_100ms(embeddings: RAGEmbeddings) -> None:
        """Gate check: embedding latency must be <100ms on CPU."""
        test_query = "lateral movement techniques for Windows Server 2022"
        
        # Warm up (model loading)
        _ = embeddings.encode(test_query)
        
        # Benchmark
        start = time.perf_counter()
        for _ in range(10):
            _ = embeddings.encode(test_query)
        elapsed_ms = ((time.perf_counter() - start) / 10) * 1000
        
        assert elapsed_ms < 100, f"Latency {elapsed_ms:.1f}ms exceeds 100ms gate"
    ```

---

### Phase 5: Module Exports [RED → GREEN]

#### 5A: Configure Module Exports (AC: 5)

- [x] Task 5.1: Update module __init__.py
  - [x] **[RED]** Write test: `from cyberred.rag.embeddings import RAGEmbeddings` works
  - [x] **[GREEN]** Update `src/cyberred/rag/__init__.py`:
    ```python
    from cyberred.rag.embeddings import RAGEmbeddings
    
    __all__ = [
        "RAGStore",
        "RAGChunk", 
        "RAGSearchResult",
        "RAGStoreStats",
        "ContentType",
        "RAGEmbeddings",  # NEW
    ]
    ```

---

### Phase 6: Integration Tests [RED → GREEN]

- [x] Task 6.1: Create integration tests
  - [x] Create `tests/integration/rag/test_embeddings.py`
  - [x] **[RED]** Write test: embedding generation works with real model
  - [x] **[RED]** Write test: embeddings work with RAGStore.search()
  - [x] **[GREEN]** Implement tests with proper fixtures
  - [x] **[REFACTOR]** Add `@pytest.mark.integration` marker

---

### Phase 7: Coverage & Documentation [BLUE]

- [x] Task 7.1: Verify 100% coverage
  - [x] Run: `pytest tests/unit/rag/test_embeddings.py --cov=src/cyberred/rag/embeddings --cov-report=term-missing`
  - [x] Ensure no untested branches

- [x] Task 7.2: Update Dev Agent Record
  - [x] Fill in agent model and completion notes
  - [x] Run full test suite: `pytest tests/unit/rag/ tests/integration/rag/ -v --tb=short`
  - [x] Update story status to `done`

## Dev Notes

### Architecture Reference

From [architecture.md#L274-L330](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L274-L330):

**RAG Escalation Layer Stack:**
- Embedding: ATT&CK-BERT (cybersecurity domain-specific, CPU-only)
- Fallback: all-mpnet-base-v2 (general quality)
- Both models output 768-dimensional vectors

**Configuration** (from architecture.md#L517-L522):

```yaml
rag:
  embedding_model: "basel/ATTACK-BERT"  # CPU-only
  fallback_model: "all-mpnet-base-v2"
```

### sentence-transformers Usage Pattern

```python
from sentence_transformers import SentenceTransformer

# Force CPU execution (no GPU)
model = SentenceTransformer("model-name", device="cpu")

# Single text encoding
embedding = model.encode("text", convert_to_numpy=True).tolist()

# Batch encoding (more efficient)
embeddings = model.encode(["text1", "text2"], convert_to_numpy=True).tolist()
```

### Model Information

| Model | HuggingFace ID | Dim | Notes |
|-------|----------------|-----|-------|
| ATT&CK-BERT | `basel/ATTACK-BERT` | 768 | Cybersecurity domain, may require HuggingFace download |
| all-mpnet-base-v2 | `sentence-transformers/all-mpnet-base-v2` | 768 | General purpose, included with sentence-transformers |

### Project Structure (per Architecture)

```
src/cyberred/rag/
├── __init__.py          # Module exports (update with RAGEmbeddings)
├── store.py             # RAGStore class (Story 6.1 ✅)
├── models.py            # RAGChunk, RAGSearchResult, ContentType (Story 6.1 ✅)
├── embeddings.py        # RAGEmbeddings class (THIS STORY)
├── query.py             # Semantic search interface (Story 6.3)
└── ingest.py            # Document ingestion pipeline (Story 6.4)

tests/unit/rag/
├── test_store.py        # (Story 6.1 ✅)
├── test_models.py       # (Story 6.1 ✅)
└── test_embeddings.py   # (THIS STORY)

tests/integration/rag/
├── test_store.py        # (Story 6.1 ✅)
└── test_embeddings.py   # (THIS STORY)
```

### Dependencies to Add (pyproject.toml)

```toml
[project.dependencies]
sentence-transformers = ">=2.2.0"  # Embedding models
```

> [!IMPORTANT]
> `sentence-transformers` pulls in PyTorch. First run may download ~500MB of model weights.

### Existing Code Patterns to Follow

**Structlog logging** from [rag/store.py](file:///root/red/src/cyberred/rag/store.py):

```python
import structlog
log = structlog.get_logger()

log.warning("rag_embeddings_fallback_activated", primary_model=self.PRIMARY_MODEL, error=str(e))
log.info("rag_embeddings_batch_start", count=len(texts))
```

**Test Pattern** from [tests/unit/rag/test_store.py](file:///root/red/tests/unit/rag/test_store.py):

```python
class TestRAGEmbeddings:
    """Tests for RAGEmbeddings class."""
    
    def test_encode_returns_768_dim_vector(self) -> None:
        """encode() returns 768-dimensional vector."""
        ...
```

### Integration with RAGStore (Story 6.1)

From [store.py](file:///root/red/src/cyberred/rag/store.py):
- `RAGStore.EMBEDDING_DIM = 768` — embedding dimension must match
- `RAGStore.search(embedding, top_k)` expects `List[float]` of length 768
- `RAGChunk.embedding: Optional[List[float]]` expects 768 floats

**Usage Pattern (for Story 6.3):**

```python
embeddings = RAGEmbeddings()
store = RAGStore()

# Encode query and search
query_embedding = embeddings.encode("lateral movement Windows")
results = await store.search(query_embedding, top_k=5)
```

### Key Learnings from Story 6.1

1. **Use structlog for logging** — NOT `print()` statements
2. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases explicitly
3. **Verify coverage claims** — Run `pytest --cov` before marking done
4. **Use pytest markers** — Always include `@pytest.mark.unit`, `@pytest.mark.integration`
5. **Status sync is critical** — Story file status must match sprint-status.yaml

### Forward References

**Story 6.3 (RAG Query)** will use `RAGEmbeddings.encode()` to embed queries before search
**Story 6.4 (Ingestion)** will use `RAGEmbeddings.encode_batch()` for bulk document embedding

### References

- **Epic 6 Overview:** [epics-stories.md#L2378-L2408](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2378-L2408)
- **Story 6.2 Requirements:** [epics-stories.md#L2411-L2435](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2411-L2435)
- **Architecture - RAG Layer:** [architecture.md#L274-L330](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L274-L330)
- **Architecture - Config:** [architecture.md#L517-L522](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L517-L522)
- **Architecture - Project Structure:** [architecture.md#L849-L860](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L849-L860)
- **Story 6.1 (LanceDB):** [6-1-lancedb-vector-store-setup.md](file:///root/red/_bmad-output/implementation-artifacts/6-1-lancedb-vector-store-setup.md)
- **Epic 5 Retrospective:** [epic-5-retro-2026-01-08.md](file:///root/red/_bmad-output/implementation-artifacts/epic-5-retro-2026-01-08.md)
- **sentence-transformers Docs:** https://www.sbert.net/
- **ATT&CK-BERT HuggingFace:** https://huggingface.co/basel/ATTACK-BERT
- **FR80:** RAG uses LanceDB (embedded, self-hosted) with ATT&CK-BERT embeddings (CPU-only)

## Dev Agent Record

### Agent Model Used

Gemini 2.5 Pro (Antigravity)

### Debug Log References

- Fixed `AttributeError: 'list' object has no attribute 'tolist'` by updating mocks in `test_embeddings.py`.
- Fixed `AssertionError` in fallback test by removing duplicate test setup calls.
- Fixed `ImportError` in integration test by importing `ContentType` correctly from `models.py`.
- Verified 100ms latency gate for CPU inference.

### Completion Notes List

- Implemented `RAGEmbeddings` class with lazy loading and singleton caching.
- Integrated `sentence-transformers` with `basel/ATTACK-BERT` (primary) and `all-mpnet-base-v2` (fallback).
- Implemented `encode` and `encode_batch` with efficient list processing.
- Verified 100% test coverage for the module.
- Added integration test to verify compatibility with `RAGStore` schema.

### File List

| Action | File Path |
|--------|-----------|
| [NEW] | `src/cyberred/rag/embeddings.py` |
| [NEW] | `tests/unit/rag/test_embeddings.py` |
| [NEW] | `tests/integration/rag/test_embeddings.py` |
| [MODIFY] | `src/cyberred/rag/__init__.py` (exported RAGEmbeddings) |
| [MODIFY] | `pyproject.toml` (added sentence-transformers) |

### Review Status

- [x] Ready for Design Review
- [x] Ready for Code Review
- [x] Internal QA Passed
