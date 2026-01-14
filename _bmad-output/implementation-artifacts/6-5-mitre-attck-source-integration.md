# Story 6.5: MITRE ATT&CK Source Integration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want MITRE ATT&CK framework ingestion,
so that agents can query technique details and detection methods (FR77).

## Acceptance Criteria

1. **Given** Story 6.4 is complete
2. **When** I call `mitre_attack.ingest()`
3. **Then** ATT&CK Enterprise STIX bundle is downloaded
4. **And** techniques are extracted with: id, name, description, tactics, platforms
5. **And** mitigations and detection methods are included
6. **And** sub-techniques are linked to parent techniques
7. **And** chunks include ATT&CK technique IDs (T####.###)
8. **And** integration tests verify ATT&CK ingestion

## Tasks / Subtasks

### DO / DON’T (Guardrails)

- **DO** reuse existing ingestion primitives:
  - `RAGIngestPipeline.process()` for incremental ingest + stats persistence
  - `DocumentChunker` for chunking + stable chunk IDs via `metadata.id`
  - `RAGStore.add()` for upsert semantics (LanceDB `merge_insert("id")`)
- **DON’T** implement a second chunking pipeline or a second vector-store schema.
- **DON’T** put this under `src/cyberred/intelligence/sources/` (that package is for Epic 5 HTTP intelligence sources). This story is **RAG** and belongs under `src/cyberred/rag/`.

### Implementation

- [x] Create package `src/cyberred/rag/sources/` (AC: 2)
  - [x] Add `src/cyberred/rag/sources/__init__.py`

- [x] Implement `src/cyberred/rag/sources/mitre_attack.py` (AC: 2-7)
  - [x] Public API must support **no-arg call**:
    - `async def ingest(*, store: RAGStore | None = None, embeddings: RAGEmbeddings | None = None, incremental: bool = True) -> IngestionStats`
    - Requirement: calling `mitre_attack.ingest()` with no args must work (internally defaulting `store=RAGStore()` and `embeddings=RAGEmbeddings()`).
  - [x] Download & cache ATT&CK Enterprise bundle (AC: 3)
    - Primary URL (authoritative):
      - `https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json`
    - Cache location (recommended): `~/.cyber-red/rag/sources/mitre_attack/enterprise-attack.json`
    - For re-download avoidance, you may use:
      - HTTP caching (ETag / If-Modified-Since), OR
      - a local file hash check.
    - **Note:** incremental ingest is already handled at the ingestion pipeline layer by per-doc hashes.
  - [x] Parse STIX using `stix2` (AC: 4-6)
    - Technique objects: STIX `attack-pattern`
      - ATT&CK ID: `external_references[].external_id` matching regex `^T\d{4}(\.\d{3})?$`
      - Fields:
        - `name`, `description`
        - tactics: `kill_chain_phases[].phase_name`
        - platforms: `x_mitre_platforms`
        - detection: `x_mitre_detection`
        - sub-technique: `x_mitre_is_subtechnique == true`
        - parent linkage:
          - Prefer `x_mitre_parent_technique_ref` (STIX reference) when present
          - Fallback: derive parent technique id from `T####.###` → `T####`
    - Mitigations: STIX `course-of-action`
      - Link mitigations to techniques via STIX `relationship` objects
        - relationship type typically `mitigates` (course-of-action → attack-pattern)
    - Optional enrichment (only if present in bundle; do not block story on this):
      - `x-mitre-data-component` / `x-mitre-data-source` objects, linked to techniques via relationships
  - [x] Convert parsed STIX to ingestion `documents: List[dict]` for `RAGIngestPipeline.process()` (AC: 7)
    - `source` must be exactly: `"mitre_attack"`
    - `documents[i]["metadata"]["id"]` must be **stable across runs** (required for stable chunk IDs).
      - Recommended: ATT&CK ID (`T1059`/`T1059.001`) when available; otherwise STIX object id.
    - `documents[i]["metadata"]["technique_ids"]` must include at least one valid ATT&CK technique id (regex above).
    - Recommended metadata:
      - `name`, `tactics`, `platforms`, `is_subtechnique`, `parent_technique_id`, `source_url`
    - Recommended document text template (improves embeddings/search quality):
      - Title line: `Technique <TID>: <name>`
      - Sections (when present): Description, Tactics, Platforms, Detection, Mitigations
      - Include mitigation names + descriptions (from course-of-action)
  - [x] Ingest into store via existing pipeline:
    - `pipeline = RAGIngestPipeline(store, embeddings)`
    - `await pipeline.process(source="mitre_attack", documents=documents, incremental=incremental)`

### Dependencies

- [x] Add STIX parsing dependency (AC: 4-6)
  - [x] Add `stix2>=3.0.0` to `pyproject.toml` dependencies
  - [x] If this repo still uses `requirements.txt` for runtime installs, keep it in sync (add `stix2>=3.0.0`).

### Tests

- [x] Unit tests for parsing + linking (AC: 4-7)
  - [x] Technique extraction: id/name/description/tactics/platforms/detection
  - [x] Sub-technique linkage to parent
  - [x] Mitigation linking via relationships
  - [x] Technique id filtering using regex

- [x] Integration test for end-to-end ingest with **no network** (AC: 8)
  - [x] Mock download (recommend `respx` since it is already in optional deps) so tests do not hit GitHub
  - [x] Call `mitre_attack.ingest()` and assert:
    - returned `IngestionStats.source == "mitre_attack"`
    - store contains chunks where `technique_ids` includes a valid `T####` / `T####.###`
    - at least one ingested document includes detection/mitigation content

### Post-ingestion verification (recommended)

- [ ] After real ingestion on a dev machine, run:
  - `pytest tests/integration/rag/test_production_store.py -v`

## Dev Notes

- Existing ingestion “engine” (do not reinvent):
  - Chunking + chunk IDs: `src/cyberred/rag/ingest.py` (`DocumentChunker._generate_chunk_id()` uses `source:doc_id:index` when `metadata.id` is provided)
  - Incremental ingest: `RAGIngestPipeline.process(..., incremental=True)` loads/saves per-doc hashes to `~/.cyber-red/rag/.rag_stats_mitre_attack.json` (location derived from the LanceDB path)
  - Upsert semantics: `src/cyberred/rag/store.py` (`RAGStore.add()` uses LanceDB `merge_insert("id")`)
- Scale expectations (for perf intuition): Enterprise ATT&CK has hundreds of techniques + sub-techniques; chunk counts will typically be in the low-thousands.

### Project Structure Notes

- Correct location in this repo:
  - `src/cyberred/rag/sources/mitre_attack.py`
- Avoid confusion with Epic 5 intelligence sources:
  - `src/cyberred/intelligence/sources/` is not for RAG ingestion modules.

### References

- Story definition: `_bmad-output/planning-artifacts/epics-stories.md` → “Story 6.5: MITRE ATT&CK Source Integration”
- Ingestion pipeline: `src/cyberred/rag/ingest.py`
- Vector store/upsert: `src/cyberred/rag/store.py`
- RAG models (technique IDs): `src/cyberred/rag/models.py`
- MITRE CTI repo: https://github.com/mitre/cti
- Raw Enterprise bundle (primary URL): https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

None required - implementation proceeded without issues.

### Completion Notes List

- ✅ Created `src/cyberred/rag/sources/` package with `__init__.py` exposing `mitre_attack_ingest`
- ✅ Implemented `src/cyberred/rag/sources/mitre_attack.py` with full STIX parsing:
  - Downloads ATT&CK Enterprise STIX bundle from GitHub with local caching
  - Parses techniques (attack-pattern), mitigations (course-of-action), and relationships
  - Extracts: technique IDs, names, descriptions, tactics, platforms, detection methods
  - Links sub-techniques to parent techniques via STIX refs or ID derivation
  - Links mitigations to techniques via relationship objects
  - Converts to RAG documents with stable IDs and proper metadata
  - Integrates with existing `RAGIngestPipeline` for chunking/embedding/storage
- ✅ Added `stix2>=3.0.0` dependency to both `pyproject.toml` and `requirements.txt`
- ✅ Created comprehensive unit tests (24 tests) covering:
  - Technique ID regex validation
  - Technique extraction with all fields
  - Sub-technique parent linkage (both STIX ref and fallback derivation)
  - Mitigation extraction and linking
  - Document conversion with proper metadata
- ✅ Created integration tests (9 tests) with mocked HTTP:
  - Verifies `ingest()` returns correct source name
  - Verifies chunks contain valid technique IDs
  - Verifies detection/mitigation content is included
  - Verifies no-args call works (AC: 2)
  - Verifies incremental ingest skips unchanged docs
  - Verifies revoked techniques are filtered out

### File List

**New Files:**
- `src/cyberred/rag/sources/__init__.py`
- `src/cyberred/rag/sources/mitre_attack.py`
- `tests/unit/rag/test_mitre_attack.py`
- `tests/integration/rag/test_mitre_attack_ingest.py`

**Modified Files:**
- `pyproject.toml` (added stix2>=3.0.0 dependency)
- `requirements.txt` (added stix2>=3.0.0 dependency)
- `src/cyberred/rag/ingest.py` (added doc_id support for stable chunking)
- `tests/integration/rag/test_ingest.py` (updated for ingest pipeline changes)
- `tests/unit/rag/test_ingest.py` (updated for ingest pipeline changes)

## Change Log

- **2026-01-09**: Implemented Story 6.5 - MITRE ATT&CK Source Integration
  - Added RAG sources package with MITRE ATT&CK ingestion module
  - Full STIX parsing for techniques, mitigations, and relationships
  - 24 unit tests + 9 integration tests (all passing)
  - Added stix2 dependency for STIX bundle parsing
