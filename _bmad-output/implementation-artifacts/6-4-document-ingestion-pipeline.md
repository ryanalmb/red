# Story 6.4: Document Ingestion Pipeline

Status: ready-for-dev

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD methodology at all times. All tasks marked [RED], [GREEN], [REFACTOR] must be followed explicitly. Each task must have a failing test before implementation.

> [!NOTE]
> **DEPENDENCY:** This story requires Stories 6.1 (LanceDB Vector Store Setup), 6.2 (ATT&CK-BERT Embedding Model), and 6.3 (RAG Query Interface) to be complete. Uses `RAGStore.add()`, `RAGEmbeddings.encode_batch()`, and `RAGChunk` dataclass.

> [!CAUTION]
> **Epic 5 Action Items MUST BE APPLIED:**
> - **AI-2:** Maintain story status sync between file and sprint-status.yaml
> - **AI-4:** Reduce verbose boilerplate — keep method signatures, remove full implementations in Dev Notes

## Story

As a **developer**,
I want **a document ingestion pipeline for RAG sources**,
So that **knowledge bases can be loaded and updated (FR77)**.

## Acceptance Criteria

1. **Given** Stories 6.1 and 6.2 are complete
   **When** I call `ingest.process(source, documents)`
   **Then** documents are chunked (512 tokens, 50 token overlap)
   **And** chunks are embedded using ATT&CK-BERT
   **And** chunks are stored in LanceDB with source metadata

2. **Given** ingestion in progress
   **When** upsert occurs for existing source
   **Then** existing chunks from same source are replaced (upsert behavior)

3. **Given** chunking pipeline
   **When** I call `ingest.chunk_document(text, source)`
   **Then** document is split using RecursiveCharacterTextSplitter or equivalent
   **And** chunk size is 512 tokens with 50 token overlap
   **And** each chunk includes `source` metadata

4. **Given** the ingestion pipeline
   **When** processing multiple documents
   **Then** ingestion progress is trackable (for TUI display via callback)
   **And** progress updates include: current document, total documents, chunk count

5. **Given** the ingestion pipeline
   **When** I call `ingest.process(source, documents, incremental=True)`
   **Then** `incremental_ingest` flag avoids re-processing unchanged files
   **And** file hash comparison determines if re-processing needed

6. **Given** Markdown documents with code blocks
   **When** ingesting HackTricks or similar sources
   **Then** code blocks are never split mid-content
   **And** `MarkdownCodeBlockSplitter` preserves code block integrity

7. **Given** integration tests
   **When** I run them with sample documents
   **Then** full ingest cycle completes successfully
   **And** chunks are queryable via `RAGStore.search()`

## Tasks / Subtasks

### Phase 0: Setup [BLUE]

- [ ] Task 0.1: Verify dependencies
  - [ ] Confirm Stories 6.1, 6.2, 6.3 are complete (check sprint-status.yaml)
  - [ ] Verify: `python -c "from cyberred.rag import RAGStore, RAGEmbeddings, RAGChunk, ContentType"`

- [ ] Task 0.2: Create module structure
  - [ ] Create `src/cyberred/rag/ingest.py`
  - [ ] Create `tests/unit/rag/test_ingest.py`
  - [ ] Create `tests/integration/rag/test_ingest.py`

---

### Phase 1: Ingestion Models [RED → GREEN → REFACTOR]

#### 1A: Define IngestionProgress Dataclass (AC: 4)

- [ ] Task 1.1: Create progress tracking model
  - [ ] **[RED]** Write failing test: `IngestionProgress` has fields: `source`, `current_doc`, `total_docs`, `chunks_processed`
  - [ ] **[GREEN]** Implement `IngestionProgress` dataclass in `ingest.py`
  - [ ] **[REFACTOR]** Add docstring referencing FR77

#### 1B: Define IngestionStats Dataclass (AC: 1, 5)

- [ ] Task 1.2: Create ingestion statistics model
  - [ ] **[RED]** Write failing test: `IngestionStats` has fields: `source`, `last_updated`, `chunk_count`, `document_count`, `file_hashes`, `failed_docs` (List[str] of doc IDs)
  - [ ] **[GREEN]** Implement `IngestionStats` dataclass
  - [ ] **[REFACTOR]** Add `to_dict()`/`from_dict()` for persistence

---

### Phase 2: Document Chunking [RED → GREEN → REFACTOR]

#### 2A: Basic Text Splitter (AC: 3)

- [ ] Task 2.1: Implement RecursiveCharacterTextSplitter
  - [ ] **[RED]** Write failing test: `chunk_document(text)` returns list of chunks
  - [ ] **[RED]** Write failing test: chunk size defaults to 512 (configurable via `config.yaml`)
  - [ ] **[RED]** Write failing test: chunks overlap by 50 tokens
  - [ ] **[GREEN]** Implement `DocumentChunker` class:
    ```python
    class DocumentChunker:
        DEFAULT_CHUNK_SIZE = 512
        DEFAULT_OVERLAP = 50
        
        def chunk_document(
            self,
            text: str,
            source: str,
            content_type: ContentType = ContentType.METHODOLOGY,
            technique_ids: Optional[List[str]] = None,
        ) -> List[RAGChunk]:
    ```
  - [ ] **[REFACTOR]** Add structlog logging for chunk counts

#### 2B: Markdown Code Block Preservation (AC: 6)

- [ ] Task 2.2: Implement MarkdownCodeBlockSplitter
  - [ ] **[NOTE]** optimization: Investigate `RecursiveCharacterTextSplitter.from_language(Language.MARKDOWN)` first. Only implement custom splitter if standard one fails "never split" requirement.
  - [ ] **[RED]** Write failing test: code blocks (``` ... ```) are never split
  - [ ] **[RED]** Write failing test: inline code (`code`) is preserved
  - [ ] **[RED]** Write failing test: oversized code blocks are kept intact (not split)
  - [ ] **[GREEN]** Implement `MarkdownCodeBlockSplitter`:
    ```python
    class MarkdownCodeBlockSplitter:
        def split_preserving_code_blocks(
            self, 
            markdown: str
        ) -> List[str]:
            """Split markdown preserving code block integrity."""
    ```
  - [ ] **[REFACTOR]** Handle nested code blocks correctly

---

### Phase 3: Ingestion Pipeline Core [RED → GREEN → REFACTOR]

#### 3A: RAGIngestPipeline Class (AC: 1, 2)

- [ ] Task 3.1: Implement core ingestion pipeline
  - [ ] **[RED]** Write failing test: `RAGIngestPipeline(store, embeddings)` initializes
  - [ ] **[RED]** Write failing test: `process(source, documents)` returns `IngestionStats`
  - [ ] **[RED]** Write failing test: documents are chunked, embedded, and stored
  - [ ] **[GREEN]** Implement `RAGIngestPipeline`:
    ```python
    class RawDocument(TypedDict):
        text: str
        metadata: Dict[str, Any]

    class RAGIngestPipeline:
        def __init__(
            self,
            store: RAGStore,
            embeddings: RAGEmbeddings,
        ) -> None:
        
        async def process(
            self,
            source: str,
            documents: List[RawDocument],
            content_type: ContentType = ContentType.METHODOLOGY,
            incremental: bool = False,
            progress_callback: Optional[Callable[[IngestionProgress], None]] = None,
        ) -> IngestionStats:
            """Process documents through ingestion pipeline.
            
            Args:
                source: Source identifier (e.g., "hacktricks", "mitre_attack")
                documents: List of {text: str, metadata: dict} documents
                content_type: ContentType enum for these documents
                incremental: If True, skip unchanged files based on hash
                progress_callback: Optional callback for progress updates
                
            Returns:
                IngestionStats with processing results
            """
    ```
  - [ ] **[REFACTOR]** Add batch processing for large document sets

#### 3B: Upsert Behavior (AC: 2)

- [ ] Task 3.2: Implement source-based upsert
  - [ ] **[RED]** Write failing test: re-ingesting same source replaces old chunks
  - [ ] **[RED]** Write failing test: ingesting different sources doesn't affect each other
  - [ ] **[GREEN]** Use `RAGStore.add()` with upsert behavior (merge_insert)
  - [ ] **[REFACTOR]** Add logging for upsert operations

---

### Phase 4: Progress Tracking [RED → GREEN → REFACTOR]

#### 4A: Progress Callback (AC: 4)

- [ ] Task 4.1: Implement progress callback
  - [ ] **[RED]** Write failing test: `progress_callback` is called for each document
  - [ ] **[RED]** Write failing test: callback receives `IngestionProgress` with correct counts
  - [ ] **[RED]** Write failing test: callback works with async pipeline
  - [ ] **[GREEN]** Integrate callback into `process()` method
  - [ ] **[REFACTOR]** Rate-limit callbacks (every 10 documents OR every 100 chunks)

---

### Phase 5: Incremental Ingestion [RED → GREEN → REFACTOR]

#### 5A: File Hash Tracking (AC: 5)

- [ ] Task 5.1: Implement incremental ingestion
  - [ ] **[RED]** Write failing test: `incremental=True` skips unchanged documents
  - [ ] **[RED]** Write failing test: changed documents are re-processed
  - [ ] **[RED]** Write failing test: file hashes are computed and stored
  - [ ] **[GREEN]** Implement hash-based change detection:
    ```python
    def _compute_hash(self, text: str) -> str:
        """Compute SHA-256 hash of document text."""
        
    def _load_stats(self, source: str) -> Optional[IngestionStats]:
        """Load previous ingestion stats for source."""
        
    def _save_stats(self, stats: IngestionStats) -> None:
        """Persist ingestion stats for incremental support."""
    ```
  - [ ] **[REFACTOR]** Store stats in JSON file alongside LanceDB

---

### Phase 6: Module Exports [RED → GREEN]

#### 6A: Configure Module Exports (AC: 7)

- [ ] Task 6.1: Update module __init__.py
  - [ ] **[RED]** Write test: `from cyberred.rag import RAGIngestPipeline` works
  - [ ] **[GREEN]** Update `src/cyberred/rag/__init__.py`:
    ```python
    from cyberred.rag.ingest import (
        RAGIngestPipeline,
        DocumentChunker,
        MarkdownCodeBlockSplitter,
        IngestionProgress,
        IngestionStats,
    )
    
    __all__ = [
        # ... existing exports ...
        "RAGIngestPipeline",
        "DocumentChunker", 
        "MarkdownCodeBlockSplitter",
        "IngestionProgress",
        "IngestionStats",
    ]
    ```

---

### Phase 7: Integration Tests [RED → GREEN]

- [ ] Task 7.1: Create integration tests
  - [ ] Create `tests/integration/rag/test_ingest.py`
  - [ ] **[RED]** Write test: full ingest cycle (chunk → embed → store)
  - [ ] **[RED]** Write test: ingested chunks are queryable via store.search()
  - [ ] **[RED]** Write test: incremental ingest skips unchanged files
  - [ ] **[RED]** Write test: markdown code blocks preserved after full cycle
  - [ ] **[GREEN]** Implement tests with temporary store fixtures
  - [ ] **[REFACTOR]** Add `@pytest.mark.integration` marker

---

### Phase 8: Coverage & Documentation [BLUE]

- [ ] Task 8.1: Verify 100% coverage
  - [ ] Run: `pytest tests/unit/rag/test_ingest.py --cov=src/cyberred/rag/ingest --cov-report=term-missing`
  - [ ] Ensure no untested branches

- [ ] Task 8.2: Update Dev Agent Record
  - [ ] Fill in agent model and completion notes
  - [ ] Run full test suite: `pytest tests/unit/rag/ tests/integration/rag/ -v --tb=short`
  - [ ] Update story status to `done`

## Dev Notes

### Architecture Reference

From [architecture.md#L849-L860](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L849-L860):

**RAG Escalation Layer Structure:**
```
src/cyberred/rag/
├── __init__.py
├── store.py         # RAGStore class (Story 6.1 ✅)
├── models.py        # RAGChunk, RAGSearchResult, ContentType (Story 6.1 ✅)
├── embeddings.py    # RAGEmbeddings class (Story 6.2 ✅)
├── query.py         # RAGQueryInterface class (Story 6.3 ✅)
├── exceptions.py    # RAGQueryTimeout
└── ingest.py        # Document ingestion pipeline (THIS STORY)
```

### Existing Code Patterns to Follow

**From RAGStore.add()** in [store.py](file:///root/red/src/cyberred/rag/store.py):
```python
async def add(self, chunks: List[RAGChunk]) -> int:
    """Add or update chunks in the store."""
    # Uses merge_insert for upsert behavior
```

**From RAGEmbeddings.encode_batch()** in [embeddings.py](file:///root/red/src/cyberred/rag/embeddings.py):
```python
def encode_batch(self, texts: List[str]) -> List[List[float]]:
    """Encode multiple texts efficiently."""
```

**From RAGChunk** in [models.py](file:///root/red/src/cyberred/rag/models.py):
```python
@dataclass
class RAGChunk:
    id: str
    text: str
    source: str
    technique_ids: List[str]
    content_type: ContentType
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
```

**Structlog Pattern** from existing modules:
```python
import structlog
log = structlog.get_logger()

log.info("rag_ingest_start", source=source, doc_count=len(documents))
log.info("rag_ingest_complete", source=source, chunks=chunk_count)
```

### Key Learnings from Stories 6.1-6.3

1. **Use structlog for logging** — NOT `print()` statements
2. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases explicitly
3. **Verify coverage claims** — Run `pytest --cov` before marking done
4. **Use pytest markers** — Always include `@pytest.mark.unit`, `@pytest.mark.integration`
5. **Status sync is critical** — Story file status must match sprint-status.yaml
6. **Async methods** — Use `async def` for I/O operations (consistent with store.add())
7. **ContentType is Enum** — Use `ContentType.METHODOLOGY`, `ContentType.PAYLOAD`, `ContentType.CHEATSHEET`

### Chunking Implementation Notes

**RecursiveCharacterTextSplitter approach:**
- Primary split on paragraph boundaries (`\n\n`)
- Secondary split on sentence boundaries (`. `)
- Tertiary split on words
- Token counting: Use `len(text.split())` as approximation OR tiktoken if precise

**MarkdownCodeBlockSplitter approach:**
- Identify code blocks with regex: ` ```[\s\S]*?``` `
- Extract code blocks as protected regions
- Split remaining text normally
- Reassemble preserving code block positions

### Chunk ID Generation

Use deterministic IDs for upsert behavior:
```python
import hashlib

def generate_chunk_id(source: str, text: str) -> str:
    """Generate deterministic chunk ID for upsert."""
    content = f"{source}:{text[:100]}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

### Usage Pattern (Integration)

```python
from cyberred.rag import (
    RAGStore, 
    RAGEmbeddings, 
    RAGIngestPipeline,
    ContentType,
)

# Initialize components
store = RAGStore()
embeddings = RAGEmbeddings()
pipeline = RAGIngestPipeline(store, embeddings)

# Ingest documents
documents = [
    {"text": "T1059.001: PowerShell execution...", "metadata": {"technique_id": "T1059.001"}},
    {"text": "Lateral movement via WMI...", "metadata": {"technique_id": "T1047"}},
]

stats = await pipeline.process(
    source="mitre_attack",
    documents=documents,
    content_type=ContentType.METHODOLOGY,
    incremental=True,
    progress_callback=lambda p: print(f"Progress: {p.current_doc}/{p.total_docs}")
)

print(f"Ingested {stats.chunk_count} chunks from {stats.document_count} documents")
```

### Forward References

**Story 6.5 (MITRE ATT&CK)** will use `RAGIngestPipeline.process()` with ATT&CK STIX data
**Story 6.6 (Atomic Red Team)** will use `RAGIngestPipeline.process()` with YAML test data
**Story 6.7 (HackTricks)** will use `MarkdownCodeBlockSplitter` for markdown preservation
**Story 6.8 (PayloadsAllTheThings)** will use `ContentType.PAYLOAD` for payload ingestion

### Post-Ingestion Verification

After ingestion completes in production, run smoke tests:
```bash
pytest tests/integration/rag/test_production_store.py -v
```

### References

- **Epic 6 Overview:** [epics-stories.md#L2378-L2408](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2378-L2408)
- **Story 6.4 Requirements:** [epics-stories.md#L2462-L2491](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L2462-L2491)
- **Architecture - RAG Layer:** [architecture.md#L849-L860](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L849-L860)
- **Story 6.1 (LanceDB):** [6-1-lancedb-vector-store-setup.md](file:///root/red/_bmad-output/implementation-artifacts/6-1-lancedb-vector-store-setup.md)
- **Story 6.2 (ATT&CK-BERT):** [6-2-attck-bert-embedding-model.md](file:///root/red/_bmad-output/implementation-artifacts/6-2-attck-bert-embedding-model.md)
- **Story 6.3 (RAG Query):** [6-3-rag-query-interface.md](file:///root/red/_bmad-output/implementation-artifacts/6-3-rag-query-interface.md)
- **Epic 5 Retrospective:** [epic-5-retro-2026-01-08.md](file:///root/red/_bmad-output/implementation-artifacts/epic-5-retro-2026-01-08.md)
- **FR77:** RAG corpus includes MITRE ATT&CK, Atomic Red Team, HackTricks, PayloadsAllTheThings, LOLBAS, GTFOBins

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

| Action | File Path |
|--------|-----------|
| [NEW] | `src/cyberred/rag/ingest.py` |
| [NEW] | `tests/unit/rag/test_ingest.py` |
| [NEW] | `tests/integration/rag/test_ingest.py` |
| [MODIFY] | `src/cyberred/rag/__init__.py` (export new classes) |
