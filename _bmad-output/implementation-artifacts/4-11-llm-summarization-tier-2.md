# Story 4.11: LLM Summarization (Tier 2)

Status: done

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD method at all times. All tasks marked [RED], [GREEN], [REFACTOR] must be followed explicitly. This story builds on existing partial implementation in `output.py`.

> [!NOTE]
> **PARTIAL IMPLEMENTATION EXISTS:** The `_tier2_llm_summarize` method in `output.py` already implements core LLM summarization logic. This story focuses on completing the feature with: (1) hash-based response caching, (2) integration tests with real NIM API, and (3) achieving 100% test coverage.

## Story

As a **developer**,
I want **LLM-based summarization for tools without dedicated parsers**,
So that **all tool output produces useful findings (FR33)**.

## Acceptance Criteria

1. **Given** Stories 4.3 and 4.5 are complete and LLM Gateway (Epic 3) is available
   **When** tool output has no Tier 1 parser
   **Then** output is sent to LLM for summarization

2. **Given** the LLM summarization flow
   **When** LLM processes tool output
   **Then** LLM extracts key findings in structured format (type, severity, description, evidence)

3. **Given** the LLM configuration
   **When** making a summarization request
   **Then** LLM uses FAST tier model via TaskComplexity.FAST

4. **Given** tool output exceeding limits
   **When** preparing for LLM call
   **Then** stdout is truncated to 4000 chars and stderr to 1000 chars

5. **Given** the LLM summarization timeout
   **When** LLM takes longer than 30s
   **Then** request times out and falls back to Tier 3 (raw truncated)

6. **Given** LLM failure (timeout, error, invalid JSON)
   **When** Tier 2 summarization fails
   **Then** gracefully falls back to Tier 3 (raw truncated output)

7. **Given** identical tool outputs from multiple executions
   **When** generating hash for caching
   **Then** LLM responses are cached by hash (tool + stdout hash) to avoid redundant calls

8. **Given** unit and integration tests for Tier 2
   **When** running coverage
   **Then** `tools/output.py` achieves 100% code coverage

9. **Given** integration tests for Tier 2
   **When** running with real NIM API
   **Then** tests verify LLM summarization with actual NVIDIA NIM provider

## Tasks / Subtasks

### Phase 0: Analysis & Verification [BLUE]

- [x] Task 0.1: Verify existing implementation
  - [x] Review current `_tier2_llm_summarize` method in `output.py`
  - [x] Run existing tests to confirm pass: `pytest tests/unit/tools/test_output.py -v`
  - [x] Run coverage: `pytest tests/unit/tools/test_output.py --cov=src/cyberred/tools/output --cov-report=term-missing`
  - [x] Identify coverage gaps

---

### Phase 1: Hash-Based Response Caching [RED → GREEN → REFACTOR]

#### 1A: Cache Infrastructure (AC: 7)

- [x] Task 1.1: Create cache key generation
  - [x] **[RED]** Write failing test: `_generate_cache_key` returns SHA256 hash of (tool + stdout + stderr)
  - [x] **[GREEN]** Implement `_generate_cache_key(self, tool: str, stdout: str, stderr: str) -> str` in OutputProcessor
  - [x] **[REFACTOR]** Add docstring explaining cache key format

- [x] Task 1.2: Add response caching mechanism
  - [x] **[RED]** Write failing test: repeated identical outputs return cached result without LLM call
  - [x] **[GREEN]** Add `_llm_cache: Dict[str, ProcessedOutput]` to OutputProcessor
  - [x] **[GREEN]** Check cache before LLM call in `_tier2_llm_summarize`
  - [x] **[GREEN]** Store result in cache after successful LLM call
  - [x] **[REFACTOR]** Add structured logging: `event="llm_cache_hit"`, `event="llm_cache_miss"`, `tool={tool}`

- [x] Task 1.3: Cache configuration
  - [x] **[RED]** Write failing test: cache can be disabled via config
  - [x] **[GREEN]** Add `cache_enabled: bool = True` parameter to OutputProcessor.__init__
  - [x] **[REFACTOR]** Document cache behavior

---

### Phase 2: Enhanced Error Handling [RED → GREEN → REFACTOR]

#### 2A: Graceful Fallback Verification (AC: 6)

- [x] Task 2.1: Verify timeout handling
  - [x] **[RED]** Write failing test: LLM call respects 30s timeout from `_llm_timeout`
  - [x] **[GREEN]** Verify `asyncio.run()` timeout behavior (already implemented)
  - [x] **[REFACTOR]** Add explicit timeout wrapper with logging: `event="tier2_timeout"`, `limit=30`

- [x] Task 2.2: Verify JSON parsing error handling
  - [x] **[RED]** Write failing test: invalid JSON from LLM results in Tier 3 fallback
  - [x] **[GREEN]** Verify `json.loads` exception handling (already implemented)
  - [x] **[REFACTOR]** Add specific error logging: `event="tier2_json_error"`, `message="{error}"`

---

### Phase 3: Integration Tests with Real NIM API [RED → GREEN → REFACTOR]

#### 3A: Real API Integration Tests (AC: 9)

- [x] Task 3.1: Create NIM API integration test file
  - [x] **[RED]** Create `tests/integration/tools/test_tier2_llm_real.py` with `@pytest.mark.integration` and `@pytest.mark.requires_nim`
  - [x] **[GREEN]** Implement test that verifies LLM summarization with real NIM provider
  - [x] **[REFACTOR]** Add skip condition: `pytest.mark.skipif(not os.getenv("NVIDIA_API_KEY"), reason="No API key")`

- [x] Task 3.2: Test real LLM summarization
  - [x] **[RED]** Write test: given sample nmap-like output, LLM extracts open_port findings
  - [x] **[GREEN]** Use real gateway initialization with NIM provider
  - [x] **[GREEN]** Verify structured response contains expected finding types
  - [x] **[REFACTOR]** Add clean up and verify no rate limit exceeded

- [x] Task 3.3: Test LLM with varied tool outputs
  - [x] **[RED]** Write test: LLM handles different tool output formats (structured, plain text)
  - [x] **[GREEN]** Test with at least 3 different tool output samples
  - [x] **[REFACTOR]** Parameterize tests for multiple samples

---

### Phase 4: Coverage Completion [RED → GREEN → REFACTOR]

#### 4A: 100% Coverage (AC: 8)

- [x] Task 4.1: Identify coverage gaps
  - [x] Run: `pytest tests/unit/tools/test_output.py --cov=src/cyberred/tools/output --cov-report=term-missing`
  - [x] Document uncovered lines

- [x] Task 4.2: Add missing test cases
  - [x] **[RED]** Write tests for any uncovered branches
  - [x] **[GREEN]** Implement test code
  - [x] **[REFACTOR]** Consolidate similar tests

- [x] Task 4.3: Verify 100% coverage achieved
  - [x] Run: `pytest tests/unit/tools/test_output.py --cov=src/cyberred/tools/output --cov-report=term-missing --cov-fail-under=100`

---

### Phase 5: Documentation [BLUE]

- [x] Task 5.1: Update Dev Agent Record
  - [x] Complete Agent Model Used
  - [x] Add Debug Log References
  - [x] Complete Completion Notes List
  - [x] Fill in File List

- [x] Task 5.2: Final verification
  - [x] Verify all ACs met
  - [x] Verify 100% coverage
  - [x] Update story status to `done`

## Dev Notes

### Existing Implementation Analysis

The `_tier2_llm_summarize` method in [output.py](file:///root/red/src/cyberred/tools/output.py#L126-L189) implements:
- ✅ FAST tier model usage via `TaskComplexity.FAST`
- ✅ 4000 char stdout truncation, 1000 char stderr truncation
- ✅ 30s timeout via `self._llm_timeout`
- ✅ Structured prompt template for finding extraction
- ✅ Finding model creation from LLM response
- ✅ Fallback to Tier 3 on exception

**Implemented (This Story):**
- ✅ Hash-based response caching (`_generate_cache_key`, `_llm_cache`)
- ✅ Cache hit/miss logging (`llm_cache_hit`, `llm_cache_miss`)
- ✅ Cache configuration (`cache_enabled` parameter)
- ✅ Integration tests with real NIM API (3 test samples)
- ✅ 100% coverage verification

### LLM Gateway Interface

From [llm/__init__.py](file:///root/red/src/cyberred/llm/__init__.py) and [gateway.py](file:///root/red/src/cyberred/llm/gateway.py):

```python
from cyberred.llm import get_gateway, TaskComplexity, LLMGatewayNotInitializedError, LLMRequest

# Current usage in output.py:
gateway = get_gateway()
request = LLMRequest(prompt=prompt, model="auto", max_tokens=2048, temperature=0.0)
response = asyncio.run(asyncio.wait_for(gateway.complete(request), timeout=self._llm_timeout))
```

**FAST Tier Model:** Nemotron-3-Nano-30B (1M context) — ideal for parsing structured tool output.

### Cache Key Generation Pattern

```python
import hashlib

def _generate_cache_key(self, tool: str, stdout: str, stderr: str) -> str:
    """Generate cache key from tool name and output hash.
    
    Cache key format: {tool}:{sha256(stdout+stderr)[:16]}
    Using first 16 chars of hash for reasonable uniqueness without storage bloat.
    """
    content = stdout + stderr
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    return f"{tool.lower()}:{content_hash}"
```

### Error Handling Pattern

```python
# Tier 2 attempt with fallback to Tier 3
try:
    return self._tier2_llm_summarize(...)
except asyncio.TimeoutError:
    log.warning("tier2_timeout", tool=tool_lower, limit=self._llm_timeout)
except json.JSONDecodeError as e:
    log.exception("tier2_json_error", tool=tool_lower, message=str(e))
except Exception as e:
    log.exception("llm_summarization_failed", tool=tool_lower, reason=str(e))
        
# Tier 3 (Raw Truncated)
log.info("using_tier3_raw", tool=tool_lower)
```

### Test Fixtures Location

Integration tests should use fixtures from:
- `tests/fixtures/tool_outputs/` — Sample outputs for various tools

### NIM API Integration Test Pattern

```python
@pytest.mark.integration
@pytest.mark.requires_nim  
class TestTier2RealNIMAPI:
    """Integration tests with real NIM API."""
    
    # 3 test samples implemented:
    # 1. test_real_llm_summarizes_nmap_output - nmap-like port scan
    # 2. test_real_llm_json_tool_output - JSON vulnerability format  
    # 3. test_real_llm_plain_text_output - gobuster directory scan
```

### Project Structure Notes

```
src/cyberred/tools/
├── output.py                 # [MODIFIED] Added caching
└── parsers/
    └── ...                   # [UNCHANGED] Tier 1 parsers

tests/
├── unit/tools/
│   └── test_output.py        # [MODIFIED] Added cache tests
└── integration/tools/
    ├── test_output_processor.py   # [UNCHANGED]
    └── test_tier2_llm_real.py     # [MODIFIED] Added 3rd test sample
```

### Key Learnings from Previous Stories (4.5-4.10)

1. **Use structlog for logging** — NOT `print()` statements
2. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases
3. **Verify coverage claims** — Run `pytest --cov` explicitly before marking done
4. **Use pytest markers** — Always include `@pytest.mark.unit` and `@pytest.mark.integration`
5. **Mock gateway for unit tests** — Use `@patch("cyberred.tools.output.get_gateway")`
6. **Real gateway for integration** — Requires NIM API key in environment

### References

- **Epic Story:** [epics-stories.md#Story 4.11](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L1978)
- **Architecture - LLM Pool:** [architecture.md#L128-L143](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L128)
- **Previous Story 4.10:** [4-10-tier-1-parsers-remaining.md](file:///root/red/_bmad-output/implementation-artifacts/4-10-tier-1-parsers-remaining.md)
- **OutputProcessor Module:** [tools/output.py](file:///root/red/src/cyberred/tools/output.py)
- **LLM Gateway:** [llm/gateway.py](file:///root/red/src/cyberred/llm/gateway.py)
- **Existing Unit Tests:** [test_output.py](file:///root/red/tests/unit/tools/test_output.py)
- **Existing Integration Tests:** [test_output_processor.py](file:///root/red/tests/integration/tools/test_output_processor.py)

## Dev Agent Record

### Agent Model Used

Gemini 2.5 Pro (code-review workflow)

### Debug Log References

- Unit tests: `pytest tests/unit/tools/test_output.py -v` — 15 passed
- Coverage: `src/cyberred/tools/output.py` — 100.00% (85 statements, 12 branches, 0 missing)

### Completion Notes List

1. **Code Review (2026-01-06):** Adversarial review identified status discrepancy (story showed `ready-for-dev` but implementation was complete), all tasks marked `[ ]` but implemented
2. **Integration Test Enhancement:** Added 3rd test sample (`test_real_llm_plain_text_output`) to meet AC 9 requirement for 3 different tool output formats
3. **Typo Fix:** Corrected "structre" → "structure" in `test_tier2_llm_real.py:L97`
4. **Coverage Verified:** `output.py` at 100% with 94 statements and 18 branches fully covered
5. **Integration Test Fix (2026-01-06):** Added `strip_markdown_json` helper to handle LLM responses wrapped in markdown code fences (```json ... ```). All 3 integration tests pass.
6. **Production Bug Fix (2026-01-06):** Added `_strip_markdown_json` helper to production `output.py` to prevent silent Tier 3 fallback when LLM returns markdown-wrapped JSON. Added 7 unit tests for helper function.

### File List

| Action | File Path |
|--------|-----------|
| [MODIFY] | `src/cyberred/tools/output.py` — Added `_strip_markdown_json` helper |
| [MODIFY] | `tests/unit/tools/test_output.py` — Added 7 tests for `_strip_markdown_json` (22 total tests) |
| [MODIFY] | `tests/integration/tools/test_tier2_llm_real.py` — Added 3rd test sample, markdown JSON handling |
