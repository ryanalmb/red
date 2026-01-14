# Story 6.6: Atomic Red Team Source Integration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **Atomic Red Team test ingestion**,
so that **agents can find executable test procedures for techniques (FR77)**.

## Acceptance Criteria

1. **Given** Story 6.4 (Document Ingestion Pipeline) is complete
2. **When** I call `atomic_red.ingest()`
3. **Then** Atomic Red Team YAML tests are downloaded from GitHub
4. **And** tests are extracted with: technique_id, test_name, description, commands
5. **And** platform compatibility is included (Windows, Linux, macOS)
6. **And** attack_commands and cleanup_commands are captured
7. **And** links to ATT&CK technique IDs are preserved
8. **And** integration tests verify Atomic Red Team ingestion

## Tasks / Subtasks

### DO / DON'T (Guardrails)

- **DO** reuse existing ingestion primitives:
  - `RAGIngestPipeline.process()` for incremental ingest + stats persistence
  - `DocumentChunker` for chunking + stable chunk IDs via `metadata.id`
  - `RAGStore.add()` for upsert semantics (LanceDB `merge_insert("id")`)
- **DO** follow the exact same patterns established in `mitre_attack.py`:
  - Same async function signature: `async def ingest(*, store=None, embeddings=None, incremental=True) -> IngestionStats`
  - Same download+cache pattern with SHA256 hash verification
  - Same document conversion pattern for `RAGIngestPipeline.process()`
- **DON'T** implement a second chunking pipeline or a second vector-store schema
- **DON'T** put this under `src/cyberred/intelligence/sources/` (that package is for Epic 5 HTTP intelligence sources). This story is **RAG** and belongs under `src/cyberred/rag/`
- **DON'T** download the entire repo as a zip - use GitHub raw file access or git sparse checkout for the `atomics/` directory only

### Implementation

- [x] Implement `src/cyberred/rag/sources/atomic_red.py` (AC: 2-7)
  - [x] Public API must support **no-arg call**:
    - `async def ingest(*, store: RAGStore | None = None, embeddings: RAGEmbeddings | None = None, incremental: bool = True, force_refresh: bool = False) -> IngestionStats`
    - Requirement: calling `atomic_red.ingest()` with no args must work (internally defaulting `store=RAGStore()` and `embeddings=RAGEmbeddings()`)
  - [x] Download & cache Atomic Red Team atomics (AC: 3)
    - Strategy options (pick one):
      - **Option A (Recommended):** Clone sparse checkout of `atomics/` directory only ✓ IMPLEMENTED
      - **Option B:** Download atomics index JSON from GitHub API, then fetch individual YAML files
      - **Option C:** Download repo tarball and extract only `atomics/` directory
    - Primary source: `https://github.com/redcanaryco/atomic-red-team`
    - Cache location: `~/.cyber-red/rag/sources/atomic_red/`
    - For re-download avoidance:
      - Store last download timestamp or git commit SHA
      - Support `force_refresh=True` parameter to bypass cache ✓ IMPLEMENTED
  - [x] Parse Atomic Red Team YAML files (AC: 4-7)
    - YAML structure (each file is a technique):
      ```yaml
      attack_technique: T1059.001  # ATT&CK technique ID
      display_name: "PowerShell"
      atomic_tests:
        - name: "Test Name"
          description: "What the test does"
          supported_platforms:
            - windows
            - linux
            - macos
          executor:
            name: powershell|command_prompt|bash|sh|manual
            command: "the attack command"
            cleanup_command: "cleanup command"  # optional
          input_arguments:  # optional
            arg_name:
              description: "what it is"
              type: string|path|url
              default: "default value"
      ```
    - Extract per-test:
      - `technique_id`: ATT&CK ID (e.g., `T1059.001`)
      - `test_name`: from `atomic_tests[].name`
      - `description`: from `atomic_tests[].description`
      - `supported_platforms`: list from `atomic_tests[].supported_platforms`
      - `attack_command`: from `atomic_tests[].executor.command`
      - `cleanup_command`: from `atomic_tests[].executor.cleanup_command` (if present)
      - `executor_type`: from `atomic_tests[].executor.name`
      - `input_arguments`: from `atomic_tests[].input_arguments` (preserve for template substitution reference)
  - [x] Convert parsed YAML to ingestion `documents: List[dict]` for `RAGIngestPipeline.process()` (AC: 7)
    - `source` must be exactly: `"atomic_red"`
    - `documents[i]["metadata"]["id"]` must be **stable across runs**:
      - Recommended: `{technique_id}:{test_index}` (e.g., `T1059.001:0`, `T1059.001:1`)
    - `documents[i]["metadata"]["technique_ids"]` must include the ATT&CK technique ID
    - Required metadata fields:
      - `technique_id`, `test_name`, `supported_platforms`, `executor_type`
    - Recommended document text template (improves embeddings/search quality):
      ```
      Atomic Red Team Test: {test_name}
      Technique: {technique_id} - {display_name}
      Platforms: {platforms}
      Executor: {executor_type}
      
      Description:
      {description}
      
      Attack Command:
      ```{executor_type}
      {attack_command}
      ```
      
      [Cleanup Command: (if present)]
      ```{executor_type}
      {cleanup_command}
      ```
      
      [Input Arguments: (if present)]
      - {arg_name}: {description} (default: {default})
      ```
  - [x] Ingest into store via existing pipeline:
    - `pipeline = RAGIngestPipeline(store, embeddings)`
    - `await pipeline.process(source="atomic_red", documents=documents, incremental=incremental)`

- [x] Update `src/cyberred/rag/sources/__init__.py` (AC: 2)
  - [x] Add import: `from cyberred.rag.sources.atomic_red import ingest as atomic_red_ingest`
  - [x] Add to `__all__`: `"atomic_red_ingest"`

### Dependencies

- [x] Verify YAML parsing dependency is available
  - `pyyaml` should already be in `pyproject.toml` dependencies (used by config loader) ✓ VERIFIED

### Tests

- [x] Unit tests for parsing + extraction (`tests/unit/rag/test_atomic_red.py`) (AC: 4-7)
  - [x] Test YAML parsing with sample atomic test file
  - [x] Test technique ID extraction (validates against regex `^T\d{4}(\.\d{3})?$`)
  - [x] Test platform extraction (windows, linux, macos)
  - [x] Test command extraction (attack_command, cleanup_command)
  - [x] Test input_arguments parsing
  - [x] Test document conversion with proper metadata
  - [x] Test stable ID generation (`technique_id:test_index`)
  - [x] Test handling of malformed/missing fields (graceful skip with warning)

- [x] Integration test for end-to-end ingest with **no network** (`tests/integration/rag/test_atomic_red_ingest.py`) (AC: 8)
  - [x] Mock download (use `respx` or fixture files) so tests do not hit GitHub
  - [x] Call `atomic_red.ingest()` and assert:
    - returned `IngestionStats.source == "atomic_red"`
    - store contains chunks where `technique_ids` includes valid ATT&CK ID
    - at least one ingested document includes attack command content
  - [x] Test no-args call works (AC: 2)
  - [x] Test incremental ingest skips unchanged docs
  - [ ] Test platform filtering if implemented (e.g., ingest only Linux tests) - NOT IMPLEMENTED (optional feature)

### Post-ingestion verification (recommended)

- [ ] After real ingestion on a dev machine, run:
  - `pytest tests/integration/rag/test_production_store.py -v`
  - Verify queries like "powershell execution" return Atomic Red Team results

## Dev Notes

- **Existing ingestion "engine" (do not reinvent):**
  - Chunking + chunk IDs: `src/cyberred/rag/ingest.py` (`DocumentChunker._generate_chunk_id()` uses `source:doc_id:index` when `metadata.id` is provided)
  - Incremental ingest: `RAGIngestPipeline.process(..., incremental=True)` loads/saves per-doc hashes to `~/.cyber-red/rag/.rag_stats_atomic_red.json`
  - Upsert semantics: `src/cyberred/rag/store.py` (`RAGStore.add()` uses LanceDB `merge_insert("id")`)

- **Scale expectations:** Atomic Red Team has ~900 techniques with ~1-5 tests each = ~2000-4000 atomic tests. Chunk counts will be in the low thousands.

- **Previous story learnings (from 6-5 MITRE ATT&CK):**
  - Use `asyncio.to_thread()` for CPU-bound parsing to avoid blocking event loop
  - Cache downloaded content with SHA256 hash verification
  - The `metadata.id` field is critical for stable chunk IDs across incremental ingests
  - Run in-thread parsing only after download is complete
  - `httpx.AsyncClient` with reasonable timeout (120s) for large downloads

- **Atomic Red Team specific considerations:**
  - YAML files are located in `atomics/T####/T####.yaml` structure
  - Some techniques have sub-techniques: `atomics/T1059.001/T1059.001.yaml`
  - Commands may contain template variables like `#{input_arg}` - preserve these for reference
  - Some tests are `manual` executor type (no command) - include description but note as manual

### Project Structure Notes

- Correct location in this repo:
  - `src/cyberred/rag/sources/atomic_red.py`
- Avoid confusion with Epic 5 intelligence sources:
  - `src/cyberred/intelligence/sources/` is NOT for RAG ingestion modules

### References

- Story definition: `_bmad-output/planning-artifacts/epics-stories.md` → "Story 6.6: Atomic Red Team Source Integration"
- Previous story (pattern reference): `_bmad-output/implementation-artifacts/6-5-mitre-attck-source-integration.md`
- Ingestion pipeline: `src/cyberred/rag/ingest.py`
- Vector store/upsert: `src/cyberred/rag/store.py`
- RAG models: `src/cyberred/rag/models.py`
- MITRE ATT&CK source (pattern): `src/cyberred/rag/sources/mitre_attack.py`
- Atomic Red Team repo: https://github.com/redcanaryco/atomic-red-team
- Atomic Red Team YAML schema: https://github.com/redcanaryco/atomic-red-team/blob/master/atomic_red_team/atomic_schema.yaml

## Dev Agent Record

### Agent Model Used

Claude (Anthropic) - Rovo Dev

### Debug Log References

N/A

### Completion Notes List

- Implemented sparse git checkout strategy (Option A) for efficient download of only the `atomics/` directory
- Added `force_refresh` parameter to bypass cache and re-download
- Used `asyncio.to_thread()` for CPU-bound YAML parsing to avoid blocking event loop
- Added `validate_technique_id()` function with regex validation for ATT&CK technique IDs
- Implemented graceful handling of malformed YAML files and missing fields with structured logging
- Added special handling for `manual` executor type (no command) with placeholder text
- Document template includes `display_name` when available (e.g., "Technique: T1059.001 - PowerShell")
- All 22 unit and integration tests pass
- Code review performed and all HIGH/MEDIUM/LOW issues fixed

### File List

- `src/cyberred/rag/sources/atomic_red.py` (created) - Main implementation with ingest(), _download_atomics(), _parse_atomic_test_file(), _create_document(), validate_technique_id()
- `src/cyberred/rag/sources/__init__.py` (modified) - Added atomic_red_ingest export
- `tests/unit/rag/test_atomic_red.py` (created) - 18 unit tests covering parsing, validation, malformed handling, manual executor
- `tests/integration/rag/test_atomic_red_ingest.py` (created) - 4 integration tests covering full flow, no-args, incremental, force_refresh

