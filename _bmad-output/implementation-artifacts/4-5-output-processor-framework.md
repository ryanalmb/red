# Story 4.5: Output Processor Framework

Status: done

## Story

As a **developer**,
I want **an output processor that routes tool output to appropriate parsers**,
So that **findings are extracted consistently across all tools (FR33)**.

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD method at all times. All tasks below are strictly marked with [RED], [GREEN], [REFACTOR] phases which must be followed explicitly.

## Acceptance Criteria

1. **Given** Story 4.3 is complete
   **When** I import `output_processor` from `cyberred.tools`
   **Then** the OutputProcessor class is available

2. **Given** tool output with stdout, stderr, tool name, and exit_code
   **When** I call `output_processor.process(stdout, stderr, tool, exit_code, agent_id, target)`
   **Then** processor detects tool from command or explicit parameter

3. **Given** a tool with a Tier 1 parser (e.g., nmap)
   **When** I process that tool's output
   **Then** processor routes to the Tier 1 parser and returns structured findings

4. **Given** a tool without a Tier 1 parser
   **When** I process that tool's output
   **Then** processor falls back to Tier 2 (LLM summarization)

5. **Given** LLM is unavailable during Tier 2 processing
   **When** I process tool output
   **Then** processor falls back to Tier 3 (raw truncated output)

6. **Given** processing completes
   **When** examining the result
   **Then** result includes `findings: List[Finding]`, `summary: str`, `raw_truncated: str`

7. **Given** the output processor module
   **When** running unit tests with coverage
   **Then** unit tests verify routing logic with 100% coverage

## Tasks / Subtasks

### Phase 1: Output Processor Core [RED → GREEN → REFACTOR]

- [x] Task 1: Create `ProcessedOutput` dataclass (AC: 6)
  - [x] **[RED]** Write failing test: `ProcessedOutput` has `findings`, `summary`, `raw_truncated` fields
  - [x] **[GREEN]** Implement dataclass in `src/cyberred/tools/output.py`
  - [x] **[REFACTOR]** Add `tier: int` field to indicate which tier produced the result

- [x] Task 2: Create `OutputProcessor` class skeleton (AC: 1, 2)
  - [x] **[RED]** Write failing test: `process(stdout, stderr, tool, exit_code, agent_id, target)` method exists
  - [x] **[GREEN]** Implement minimal class with `process()` returning empty `ProcessedOutput`
  - [x] **[REFACTOR]** Add type hints and docstrings

- [x] Task 3: Implement parser registry pattern (AC: 3)
  - [x] **[RED]** Write failing test: `OutputProcessor.register_parser(tool_name, parser_fn)` registers a parser
  - [x] **[GREEN]** Implement dict-based registry: `{tool_name: parser_function}`
  - [x] **[REFACTOR]** Add `get_registered_parsers()` method for introspection

### Phase 2: Tier-Based Routing [RED → GREEN → REFACTOR]

- [x] Task 4: Implement Tier 1 routing (AC: 3)
  - [x] **[RED]** Write failing test: if parser exists for tool, `process()` uses it
  - [x] **[GREEN]** Check registry, call parser if found, wrap result in `ProcessedOutput`
  - [x] **[REFACTOR]** Log parser selection with structlog

- [x] Task 5: Implement Tier 2 fallback (LLM summarization) (AC: 4)
  - [x] **[RED]** Write failing test: if no parser, falls back to LLM summarization
  - [x] **[GREEN]** Integrate with `LLMGateway` for summarization, parse LLM response
  - [x] **[REFACTOR]** Add `llm_timeout_seconds: int = 30` configuration

- [x] Task 6: Implement Tier 3 fallback (raw truncated) (AC: 5)
  - [x] **[RED]** Write failing test: if LLM unavailable, returns raw truncated output
  - [x] **[GREEN]** Truncate stdout to 4000 chars, return `ProcessedOutput(tier=3)`
  - [x] **[REFACTOR]** Make truncation limit configurable

### Phase 3: Tool Detection & Interface [RED → GREEN → REFACTOR]

- [x] Task 7: Implement tool detection logic (AC: 2)
  - [x] **[RED]** Test: `process()` correctly identifies registered vs unregistered tools
  - [x] **[GREEN]** Implement logic to check registry before routing
  - [x] **[REFACTOR]** Ensure case-insensitive tool name matching

- [x] Task 8: Define standard parser interface (AC: 3)
  - [x] **[RED]** Test: Registry rejects invalid parser signatures (optional, if using strict typing)
  - [x] **[GREEN]** Define `Protocol` or `Callable` type alias for parsers
  - [x] **[REFACTOR]** Update `register_parser` to use type hint

- [x] Task 9: Create stub nmap parser for testing (AC: 3, 7)
  - [x] **[RED]** Write failing test: `nmap_parser` processes output and returns `List[Finding]` with correct ids/topics
  - [x] **[GREEN]** Implement stub function with standard signature
  - [x] **[REFACTOR]** Add to `OutputProcessor` or standalone test helper

### Phase 4: Integration & Exports [RED → GREEN → REFACTOR]

- [x] Task 10: Export from tools/__init__.py (AC: 6)
  - [x] **[RED]** Test: `from cyberred.tools import OutputProcessor` works
  - [x] **[GREEN]** Add exports to `__init__.py`
  - [x] **[REFACTOR]** Verify `__all__` list

- [x] Task 11: Create parsers directory structure (AC: 3)
  - [x] Create `src/cyberred/tools/parsers/__init__.py`
  - [x] Create `src/cyberred/tools/parsers/base.py` for `ParserFn` definitions
  - [x] Refactor `OutputProcessor` to use `ParserFn`

- [x] Task 12: Documentation (AC: 8)
  - [x] **[BLUE]** Update Dev Agent Record
  - [x] **[BLUE]** Create walkthrough artifact

## Dev Agent Record

**Agent Model/Version:** 
- {{agent_model_name_version}} (Gemini 2.0 Flash)

**Key Decisions:**
- Implemented tiered processing logic: Tier 1 (Parser) -> Tier 2 (LLM) -> Tier 3 (Raw).
- Used `callable` for parser interface for flexibility.
- Integrated `structlog` for observability of routing decisions.
- Added `LLMGatewayNotInitializedError` to core exceptions to support robustness.
- Used `AsyncMock` for testing async LLM gateway interactions.

**Blockers:**
- `LLMGatewayNotInitializedError` was missing from codebase, required adding to `core/exceptions.py`.
- `Finding` dataclass validation (`uuid`, `agent_id`) enforced strict format in tests.

**Refactorings:**
- Added logging to `process` method.
- Moved logic to `_tier2_llm_summarize` helper.

- [x] Task 13: Achieve 100% test coverage (AC: 7)
  - [x] Run coverage report
  - [x] Add tests for missing branches (logging failures, empty list)
  - [x] Verify 100% coverage on `src/cyberred/tools/output.py`

- [x] Task 14: Integration test with mock LLM (AC: 4, 5)
  - [x] Create `tests/integration/tools/test_output_processor.py`
  - [x] Test Tier 2 with mock LLM provider
  - [x] Test Tier 3 fallback when LLM fails

## Dev Notes

> [!TIP]
> **Quick Reference:** Create `OutputProcessor` class with `process()` method that routes tool output to Tier 1 (parser), Tier 2 (LLM), or Tier 3 (raw). Use registry pattern for parsers. Export from `tools/__init__.py`. Achieve 100% coverage.

### Epic AC Coverage

All epic acceptance criteria are covered:
- ✅ AC1: Module importable from `cyberred.tools`
- ✅ AC2: `process(stdout, stderr, tool, exit_code, agent_id, target)` detects tool
- ✅ AC3: Routes to Tier 1 parser if available
- ✅ AC4: Falls back to Tier 2 (LLM summarization)
- ✅ AC5: Falls back to Tier 3 (raw truncated) if LLM unavailable
- ✅ AC6: Result includes `findings`, `summary`, `raw_truncated`
- ✅ AC7: Unit tests verify routing logic with 100% coverage

### Architecture Requirements

| Component | Location | Notes |
|-----------|----------|-------|
| OutputProcessor | `src/cyberred/tools/output.py` | Main output processing class |
| ProcessedOutput | `src/cyberred/tools/output.py` | Result dataclass |
| ParserProtocol | `src/cyberred/tools/parsers/base.py` | Parser interface |
| parsers/ | `src/cyberred/tools/parsers/` | Tier 1 parsers (future stories) |

### ProcessedOutput Dataclass

```python
from dataclasses import dataclass, field
from typing import List
from cyberred.core.models import Finding

@dataclass
class ProcessedOutput:
    """Result of processing tool output.
    
    Attributes:
        findings: List of structured Finding objects from parsing.
        summary: Human-readable summary of the output.
        raw_truncated: First 4000 chars of stdout for debugging.
        tier: Which tier produced this result (1, 2, or 3).
    """
    findings: List[Finding] = field(default_factory=list)
    summary: str = ""
    raw_truncated: str = ""
    tier: int = 3  # Default to raw output tier
```

### OutputProcessor Implementation Pattern

```python
import structlog
import uuid
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional
from cyberred.core.models import Finding
from cyberred.llm import get_gateway, LLMGatewayNotInitializedError

log = structlog.get_logger()

# Type alias for parser functions
# (stdout, stderr, exit_code, agent_id, target) -> List[Finding]
ParserFn = Callable[[str, str, int, str, str], List[Finding]]

class OutputProcessor:
    """Routes tool output to appropriate parsers.
    
    Tier hierarchy:
    - Tier 1: Structured parsers (~30 high-frequency tools)
    - Tier 2: LLM summarization (via LLMGateway)
    - Tier 3: Raw truncated output (fallback)
    
    Usage:
        processor = OutputProcessor()
        result = processor.process(stdout, stderr, "nmap", exit_code, agent_id, target)
    """
    
    def __init__(self, max_raw_length: int = 4000, llm_timeout: int = 30):
        self._parsers: Dict[str, ParserFn] = {}
        self._max_raw_length = max_raw_length
        self._llm_timeout = llm_timeout
    
    def register_parser(self, tool_name: str, parser: ParserFn) -> None:
        """Register a Tier 1 parser for a tool."""
        self._parsers[tool_name.lower()] = parser
        log.info("parser_registered", tool=tool_name)
    
    def get_registered_parsers(self) -> List[str]:
        """Return list of tools with registered parsers."""
        return list(self._parsers.keys())
    
    def detect_tool(self, command: str) -> str:
        """Extract tool name from command string."""
        # Get first token
        first_token = command.split()[0] if command.strip() else ""
        # Strip path
        tool_name = first_token.split("/")[-1]
        return tool_name.lower()
    
    def process(
        self, 
        stdout: str, 
        stderr: str, 
        tool: str, 
        exit_code: int,
        agent_id: str,
        target: str
    ) -> ProcessedOutput:
        """Process tool output through tier hierarchy.
        
        Note on Findings:
        - Parsers must generate valid UUIDs for `id`
        - timestamp should be `datetime.now(timezone.utc).isoformat()`
        - topic should be `f"findings:{agent_id}:{tool}"`
        - signature should be empty `""` (Agent signs before broadcast)
        """
        tool = tool.lower()
        raw_truncated = stdout[:self._max_raw_length]
        
        # Tier 1: Try registered parser
        if tool in self._parsers:
            log.info("using_tier1_parser", tool=tool)
            try:
                findings = self._parsers[tool](stdout, stderr, exit_code, agent_id, target)
                return ProcessedOutput(
                    findings=findings,
                    summary=f"Parsed {len(findings)} findings from {tool}",
                    raw_truncated=raw_truncated,
                    tier=1
                )
            except Exception:
                log.exception("parser_failed", tool=tool)
                # Fall through to LLM
        
        # Tier 2: Try LLM summarization
        try:
            return self._tier2_llm_summarize(stdout, stderr, tool, raw_truncated, agent_id, target)
        except Exception:
            try:
                log.exception("llm_summarization_failed", tool=tool)
            except:
                pass # Fallback
        
        # Tier 3: Raw truncated output
        log.info("using_tier3_raw", tool=tool)
        return ProcessedOutput(
            findings=[],
            summary="Raw tool output (no parser or LLM available)",
            raw_truncated=raw_truncated,
            tier=3
        )
    
    def _tier2_llm_summarize(
        self, 
        stdout: str, 
        stderr: str, 
        tool: str,
        raw_truncated: str,
        agent_id: str,
        target: str
    ) -> ProcessedOutput:
        """Use LLM to summarize tool output."""
        # Implementation in Task 5
        raise NotImplementedError("Tier 2 LLM summarization")
```

### Tier 2 LLM Summarization Prompt

```python
TIER2_SUMMARIZATION_PROMPT = """Analyze the following security tool output and extract findings.

Tool: {tool}
Exit Code: {exit_code}

STDOUT:
{stdout}

STDERR:
{stderr}

Respond with a JSON object:
{{
  "findings": [
    {{
      "type": "<finding_type>",
      "severity": "<critical|high|medium|low|info>",
      "description": "<what was found>",
      "evidence": "<relevant output snippet>"
    }}
  ],
  "summary": "<brief summary of the tool execution>"
}}

If no significant findings, respond with empty findings list.
"""
```

### LLM Gateway Integration

The output processor MUST use the existing `LLMGateway` from Epic 3:

```python
from cyberred.llm import get_gateway, TaskComplexity

def _tier2_llm_summarize(self, stdout, stderr, tool, raw_truncated, agent_id, target):
    gateway = get_gateway()  # May raise LLMGatewayNotInitializedError
    
    # Truncate for LLM context
    prompt = TIER2_SUMMARIZATION_PROMPT.format(
        tool=tool,
        exit_code=exit_code,
        stdout=stdout[:4000],
        stderr=stderr[:1000]
    )
    
    # Use FAST tier for parsing efficiency
    response = await gateway.complete(
        prompt=prompt,
        complexity=TaskComplexity.FAST,
        timeout=self._llm_timeout
    )
    
    # Parse JSON response into findings
    # Use agent_id, target, tool to populate Finding mandatory fields
    # Generate id=uuid.uuid4(), timestamp=isoformat(), topic=findings:agent_id:tool, signature=""
    # ...
```

### Key Dependencies from Previous Stories

| Component | Import | Purpose |
|-----------|--------|---------|
| Finding | `from cyberred.core.models import Finding` | Structured finding dataclass |
| LLMGateway | `from cyberred.llm import get_gateway` | Tier 2 summarization |
| TaskComplexity | `from cyberred.llm import TaskComplexity` | Model tier selection |
| structlog | `import structlog` | Structured logging |

### Async Patterns (CRITICAL)

> [!CAUTION]
> The `LLMGateway.complete()` method is async. Handle appropriately:

```python
# Option 1: Make process() async
async def process(self, ...) -> ProcessedOutput:
    ...
    response = await gateway.complete(...)

# Option 2: Sync wrapper (if caller is sync)
import asyncio
response = asyncio.run(gateway.complete(...))
```

Decide based on how agents call `kali_execute()` → check `kali_executor.py` for patterns.

### Module Export Pattern (CRITICAL - from Story 4.4)

Every story MUST verify exports before marking complete:
```python
# Test: test_output_exports.py
def test_output_exports():
    from cyberred.tools import OutputProcessor, ProcessedOutput
    assert OutputProcessor is not None
    assert ProcessedOutput is not None
```

### Project Structure Notes

Files to create/modify:
```
src/cyberred/
├── tools/
│   ├── __init__.py             # [MODIFY] Add OutputProcessor, ProcessedOutput exports
│   ├── output.py               # [NEW] OutputProcessor class, ProcessedOutput dataclass
│   └── parsers/
│       ├── __init__.py         # [NEW] Parser package init
│       └── base.py             # [NEW] ParserProtocol (optional typing)

tests/
├── unit/
│   └── tools/
│       ├── test_output.py      # [NEW] Unit tests for OutputProcessor
│       └── test_output_exports.py  # [NEW] Export verification test
├── integration/
│   └── tools/
│       └── test_output_processor.py  # [NEW] Integration tests with mock LLM
```

### Error Handling

| Error | Handling | Notes |
|-------|----------|-------|
| Parser raises exception | Catch, log, fall through to Tier 2 | ERR1 pattern |
| LLMGatewayNotInitializedError | Catch, fall through to Tier 3 | Graceful degradation |
| LLM timeout | Catch, fall through to Tier 3 | ERR2 pattern |
| Invalid LLM JSON response | Catch, fall through to Tier 3 | Parse error handling |

### Testing Standards

- **100% coverage** on `output.py` (enforced gate)
- **TDD phases** marked in tasks: [RED] → [GREEN] → [REFACTOR]
- **Unit tests mock the LLM Gateway** — use `MockLLMProvider`
- **Integration tests use real mock mode** — verify Tier 2 behavior

### Key Learnings from Story 4.4

1. **Export verification is critical** — Add to code review checklist
2. **Use structlog for logging** — NOT `print()` statements
3. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases
4. **Verify coverage claims before marking done** — Run `pytest --cov` explicitly
5. **Python dataclasses preferred** — Use `@dataclass` with type hints
6. **Catch exceptions in routing** — Let tool failures fail gracefully, not crash

### References

- **Epic 4 Context:** [epics-stories.md#Story 4.5](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L1783)
- **Architecture:** [architecture.md#tools/output.py](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L820)
- **Previous Story 4.4:** [4-4-tool-manifest-generation.md](file:///root/red/_bmad-output/implementation-artifacts/4-4-tool-manifest-generation.md)
- **Core Models:** [core/models.py](file:///root/red/src/cyberred/core/models.py)
- **LLM Gateway:** [llm/__init__.py](file:///root/red/src/cyberred/llm/__init__.py)

## Dev Agent Record

### Agent Model Used

Gemini 2.0 Flash (via code-review workflow)

### Debug Log References

- All 17 tests pass (12 unit + 5 integration)
- 100% coverage on `output.py` and `parsers/base.py`

### Completion Notes List

- Code review identified 8 issues (2 Critical, 2 High, 4 Medium) - all fixed
- Added missing `log.info` calls to `register_parser` and Tier 3 fallback
- Created `test_output_exports.py`, `nmap_stub.py`, integration tests

### File List

| File | Action | Description |
|------|--------|-------------|
| `src/cyberred/tools/output.py` | [MODIFIED] | OutputProcessor class with tiered routing |
| `src/cyberred/tools/parsers/__init__.py` | [NEW] | Parser package init |
| `src/cyberred/tools/parsers/base.py` | [NEW] | ParserFn type alias |
| `src/cyberred/tools/parsers/nmap_stub.py` | [NEW] | Stub nmap parser for testing |
| `src/cyberred/tools/__init__.py` | [MODIFIED] | Added OutputProcessor, ProcessedOutput exports |
| `tests/unit/tools/test_output.py` | [NEW] | Unit tests for OutputProcessor |
| `tests/unit/tools/test_output_exports.py` | [NEW] | Export verification tests |
| `tests/integration/tools/__init__.py` | [NEW] | Integration test package init |
| `tests/integration/tools/test_output_processor.py` | [NEW] | Integration tests with mock LLM |
