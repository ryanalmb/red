# Story 4.7: Tier 1 Parser - nuclei

Status: done

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD method at all times. All tasks below are strictly marked with [RED], [GREEN], [REFACTOR] phases which must be followed explicitly.

## Story

As a **developer**,
I want **a structured parser for nuclei output**,
So that **vulnerability findings are extracted with CVE and severity (FR33)**.

## Acceptance Criteria

1. **Given** Story 4.5 is complete
   **When** nuclei JSON output (`-j` or `-jsonl`) is passed to the parser
   **Then** parser extracts all template matches

2. **Given** valid nuclei JSON output
   **When** I parse the output
   **Then** each finding includes: template_id, severity, CVE (if present), matched_url, extracted_data

3. **Given** nuclei output contains various template types
   **When** I parse the output
   **Then** findings are typed by nuclei template type (cve, exposure, misconfiguration)

4. **Given** nuclei output contains CVSS scores
   **When** examining the findings
   **Then** CVSS score is included when available

5. **Given** the nuclei parser
   **When** running integration tests
   **Then** tests verify against real nuclei output from cyber range

6. **Given** the nuclei parser module
   **When** running unit tests with coverage
   **Then** unit tests achieve 100% coverage on `src/cyberred/tools/parsers/nuclei.py`

## Tasks / Subtasks

### Phase 1: Parser Module Foundation [RED → GREEN → REFACTOR]

- [x] Task 1: Create nuclei parser module with ParserFn signature (AC: 1)
  - [x] **[RED]** Write failing test: `nuclei_parser(stdout, stderr, exit_code, agent_id, target)` exists and matches `ParserFn` type
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/nuclei.py` with function signature
  - [x] **[REFACTOR]** Add docstring and type hints per architecture standard

- [x] Task 2: Parse basic nuclei JSON structure (AC: 1)
  - [x] **[RED]** Write failing test: parser returns empty list for invalid/empty JSON
  - [x] **[RED]** Write failing test: parser correctly parses JSON Lines (one JSON object per line)
  - [x] **[GREEN]** Use `json.loads()` to parse each line of stdout
  - [x] **[REFACTOR]** Add error handling for malformed JSON (skip invalid lines, don't raise)

### Phase 2: Template Match Extraction [RED → GREEN → REFACTOR]

- [x] Task 3: Extract template ID and severity (AC: 1, 2)
  - [x] **[RED]** Write failing test: parser extracts `template-id` from JSON object
  - [x] **[RED]** Write failing test: parser extracts `info.severity` and maps to Finding severity
  - [x] **[GREEN]** Parse `template-id` and `info.severity` fields
  - [x] **[REFACTOR]** Map nuclei severity (info/low/medium/high/critical) to Finding severity

- [x] Task 4: Extract CVE information (AC: 2)
  - [x] **[RED]** Write failing test: parser extracts CVE from `info.metadata.cve-id` or `info.classification.cve-id`
  - [x] **[GREEN]** Parse CVE from metadata or classification objects
  - [x] **[REFACTOR]** Handle missing CVE gracefully (empty string)

- [x] Task 5: Extract matched URL and extracted data (AC: 2)
  - [x] **[RED]** Write failing test: parser extracts `matched-at` URL
  - [x] **[RED]** Write failing test: parser extracts `extracted-results` if present
  - [x] **[GREEN]** Parse `matched-at`, `host`, `ip`, `extracted-results` fields
  - [x] **[REFACTOR]** Combine into comprehensive evidence string

### Phase 3: Finding Type Classification [RED → GREEN → REFACTOR]

- [x] Task 6: Classify findings by template type (AC: 3)
  - [x] **[RED]** Write failing test: parser identifies "cve" type from template tags or CVE presence
  - [x] **[RED]** Write failing test: parser identifies "exposure" type from template tags
  - [x] **[RED]** Write failing test: parser identifies "misconfiguration" type from template tags
  - [x] **[GREEN]** Parse `info.tags` array to classify finding type
  - [x] **[REFACTOR]** Implement classification hierarchy: CVE present → "cve", else use tag-based classification
  
- [x] Task 7: Create Finding objects (AC: 2, 3)
  - [x] **[RED]** Write failing test: each nuclei match creates a `Finding` with correct fields
  - [x] **[GREEN]** Create `Finding(type=..., ...)` with UUID, timestamp, topic, empty signature
  - [x] **[REFACTOR]** Include template_id, severity, CVE, matched_url in evidence field

### Phase 4: CVSS Score Extraction [RED → GREEN → REFACTOR]

- [x] Task 8: Extract CVSS score when available (AC: 4)
  - [x] **[RED]** Write failing test: parser extracts CVSS from `info.classification.cvss-score` or `info.metadata.cvss-score`
  - [x] **[GREEN]** Parse CVSS score from classification or metadata
  - [x] **[REFACTOR]** Include CVSS in evidence, handle missing scores gracefully

### Phase 5: Plain Text Output Support [RED → GREEN → REFACTOR]

- [x] Task 9: Support plain text nuclei output (AC: 1 extension)
  - [x] **[RED]** Write failing test: parser detects and parses plain text format (non-JSON)
  - [x] **[GREEN]** Use regex to extract `[timestamp] [template-id] [protocol] [severity] url [extra]`
  - [x] **[REFACTOR]** Auto-detect format (JSON vs plain text) based on content

### Phase 6: Registration & Exports [RED → GREEN → REFACTOR]

- [x] Task 10: Register parser with OutputProcessor (AC: 1)
  - [x] **[RED]** Write failing test: `OutputProcessor.register_parser("nuclei", nuclei_parser)` works
  - [x] **[GREEN]** Import and export `nuclei_parser` from `parsers/__init__.py`
  - [x] **[REFACTOR]** Add auto-registration pattern in parsers module

- [x] Task 11: Export from tools package (AC: 1)
  - [x] **[RED]** Write test: `from cyberred.tools.parsers import nuclei_parser` works
  - [x] **[GREEN]** Add export to `parsers/__init__.py`
  - [x] **[REFACTOR]** Verify `__all__` list

### Phase 7: Integration & Fixtures [RED → GREEN → REFACTOR]

- [x] Task 12: Create JSON test fixtures (AC: 5)
  - [x] Create `tests/fixtures/tool_outputs/nuclei_json_basic.json` (single CVE finding)
  - [x] Create `tests/fixtures/tool_outputs/nuclei_json_multi.json` (multiple findings, various severities)
  - [x] Create `tests/fixtures/tool_outputs/nuclei_json_exposure.json` (exposure/misconfiguration findings)
  - [x] Create `tests/fixtures/tool_outputs/nuclei_plain.txt` (plain text format)

- [x] Task 13: Create integration test (AC: 5)
  - [x] Create `tests/integration/tools/test_nuclei_parser.py`
  - [x] Test full pipeline: JSON fixture → nuclei_parser → valid Findings
  - [x] Verify Finding fields match expected values from fixture

- [x] Task 14: Achieve 100% test coverage (AC: 6)
  - [x] Run `pytest --cov=src/cyberred/tools/parsers/nuclei --cov-report=term-missing`
  - [x] Ensure all lines/branches are covered
  - [x] Add edge case tests (empty input, malformed JSON, missing fields) as needed

### Phase 8: Documentation [BLUE]

- [x] Task 15: Documentation & Handover
  - [x] Update Dev Agent Record in this story file
  - [x] Verify all tasks are marked complete
  - [x] Ensure story status is updated to `review`
  - [x] Complete file list with actions

## Dev Notes

> [!TIP]
> **Quick Reference:** Create `nuclei_parser()` function in `tools/parsers/nuclei.py` that parses nuclei JSON Lines output. Return `List[Finding]` with `type="cve"`, `type="exposure"`, or `type="misconfiguration"`. Register with `OutputProcessor`. Achieve 100% coverage.

### ParserFn Signature (CRITICAL)

The parser MUST follow the exact signature from `parsers/base.py`:

```python
from cyberred.tools.parsers.base import ParserFn

# Standard signature: (stdout, stderr, exit_code, agent_id, target) -> List[Finding]
def nuclei_parser(
    stdout: str, 
    stderr: str, 
    exit_code: int, 
    agent_id: str, 
    target: str
) -> List[Finding]:
    ...
```

### Finding Model (CRITICAL)

Each `Finding` requires 10 validated fields:

```python
Finding(
    id=str(uuid.uuid4()),           # MUST be valid UUID
    type="cve",                     # "cve", "exposure", "misconfiguration", "vulnerability"
    severity="critical",            # "critical", "high", "medium", "low", "info"
    target=target,                  # From parser argument, validated IP/URL/hostname
    evidence="CVE-2021-44228 Log4Shell on http://192.168.1.1:8080/",  # Combined finding info
    agent_id=agent_id,              # From parser argument, MUST be valid UUID
    timestamp=datetime.now(timezone.utc).isoformat(),  # ISO 8601
    tool="nuclei",
    topic=f"findings:{agent_id}:nuclei",  # Redis channel pattern
    signature=""                    # Empty string, agent signs before broadcast
)
```

> [!CAUTION]
> **Validation:** The `Finding` dataclass validates `id`, `agent_id` as UUIDs, `timestamp` as ISO 8601, and `target` as valid IP/URL/hostname. Invalid values will raise `ValueError`.

### Nuclei JSON Output Structure Reference

Nuclei outputs one JSON object per line when using `-j` or `-jsonl` flag:

```json
{
  "template-id": "CVE-2021-44228",
  "info": {
    "name": "Apache Log4j RCE",
    "description": "Apache Log4j2 \u003c=2.14.1 JNDI features...",
    "severity": "critical",
    "tags": ["cve", "cve2021", "rce", "apache", "log4j"],
    "reference": ["https://nvd.nist.gov/vuln/detail/CVE-2021-44228"],
    "classification": {
      "cve-id": "CVE-2021-44228",
      "cvss-score": 10.0,
      "cwe-id": "CWE-502"
    },
    "metadata": {
      "max-request": 1,
      "verified": true
    }
  },
  "type": "http",
  "host": "http://192.168.1.1:8080",
  "matched-at": "http://192.168.1.1:8080/api/vulnerable",
  "ip": "192.168.1.1",
  "timestamp": "2025-01-06T02:00:00.000Z",
  "matcher-name": "log4j-rce",
  "extracted-results": ["${jndi:ldap://...}"]
}
```

### Nuclei Plain Text Output Format

```
[2025-01-05 12:00:05] [CVE-2021-44228] [http] [critical] http://192.168.1.1:8080/
[2025-01-05 12:00:05] [tech-detect] [http] [info] http://192.168.1.1:8080/ [Apache/2.4.52]
```

Format: `[timestamp] [template-id] [protocol] [severity] url [extracted_data]`

### Implementation Pattern (Based on nmap.py)

```python
import json
import uuid
import re
from typing import List
from datetime import datetime, timezone
import structlog

from cyberred.core.models import Finding

log = structlog.get_logger()


def nuclei_parser(
    stdout: str, 
    stderr: str, 
    exit_code: int, 
    agent_id: str, 
    target: str
) -> List[Finding]:
    """Parse nuclei JSON or plain text output to structured findings.
    
    Auto-detects format: tries JSON Lines first, falls back to plain text.
    
    Args:
        stdout: Nuclei output (JSON from -j or plain text)
        stderr: Nuclei stderr (usually status messages)
        exit_code: Process exit code
        agent_id: UUID of agent running the tool
        target: Target IP/hostname
        
    Returns:
        List of Finding objects for each template match
    """
    findings: List[Finding] = []
    
    if not stdout.strip():
        return findings
    
    # Auto-detect format
    if _is_json_format(stdout):
        return _parse_json(stdout, agent_id, target)
    else:
        return _parse_plain_text(stdout, agent_id, target)


def _is_json_format(stdout: str) -> bool:
    """Check if output is nuclei JSON format."""
    first_line = stdout.strip().split('\n')[0]
    return first_line.startswith('{') and first_line.endswith('}')


def _parse_json(stdout: str, agent_id: str, target: str) -> List[Finding]:
    """Parse JSON Lines format output."""
    findings: List[Finding] = []
    
    for line in stdout.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            log.warning("nuclei_json_parse_failed", line=line[:100])
            continue
        
        # Extract fields
        template_id = data.get('template-id', 'unknown')
        info = data.get('info', {})
        severity = info.get('severity', 'info').lower()
        matched_at = data.get('matched-at', target)
        
        # Extract CVE
        cve_id = ""
        classification = info.get('classification', {})
        if classification:
            cve_id = classification.get('cve-id', '')
        if not cve_id:
            metadata = info.get('metadata', {})
            cve_id = metadata.get('cve-id', '')
        
        # Extract CVSS
        cvss_score = ""
        if classification:
            cvss = classification.get('cvss-score')
            if cvss is not None:
                cvss_score = str(cvss)
        
        # Classify finding type
        tags = info.get('tags', [])
        finding_type = _classify_finding_type(cve_id, tags)
        
        # Build evidence
        evidence_parts = [f"Template: {template_id}"]
        if cve_id:
            evidence_parts.append(f"CVE: {cve_id}")
        if cvss_score:
            evidence_parts.append(f"CVSS: {cvss_score}")
        evidence_parts.append(f"URL: {matched_at}")
        
        # Add extracted results if present
        extracted = data.get('extracted-results', [])
        if extracted:
            evidence_parts.append(f"Extracted: {', '.join(extracted)}")
        
        evidence = " | ".join(evidence_parts)
        
        findings.append(_create_finding(
            type=finding_type,
            severity=severity,
            target=target,
            evidence=evidence,
            agent_id=agent_id
        ))
    
    log.info("nuclei_parsed", target=target, findings_count=len(findings))
    return findings


def _classify_finding_type(cve_id: str, tags: List[str]) -> str:
    """Classify finding type based on CVE presence and tags."""
    if cve_id:
        return "cve"
    
    # Check tags for classification
    tag_set = set(t.lower() for t in tags)
    
    if 'exposure' in tag_set or 'exposed' in tag_set:
        return "exposure"
    if 'misconfig' in tag_set or 'misconfiguration' in tag_set:
        return "misconfiguration"
    
    # Default to vulnerability for other security findings
    return "vulnerability"


def _create_finding(
    type: str,
    severity: str,
    target: str,
    evidence: str,
    agent_id: str
) -> Finding:
    """Helper to create Finding with standard fields."""
    return Finding(
        id=str(uuid.uuid4()),
        type=type,
        severity=severity,
        target=target,
        evidence=evidence,
        agent_id=agent_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        tool="nuclei",
        topic=f"findings:{agent_id}:nuclei",
        signature=""
    )
```

### Project Structure Notes

Files to create/modify:

```
src/cyberred/tools/parsers/
├── __init__.py          # [MODIFY] Add nuclei_parser export
├── base.py              # [UNCHANGED] ParserFn type
├── nmap.py              # [UNCHANGED] Reference implementation
└── nuclei.py            # [NEW] Nuclei JSON/plain text parser

tests/
├── unit/tools/parsers/
│   └── test_nuclei.py   # [NEW] Unit tests for nuclei parser
├── integration/tools/
│   └── test_nuclei_parser.py  # [NEW] Integration tests
└── fixtures/tool_outputs/
    ├── nuclei.txt              # [UNCHANGED] Existing plain text fixture
    ├── nuclei_json_basic.json  # [NEW] Single JSON finding
    ├── nuclei_json_multi.json  # [NEW] Multiple findings
    └── nuclei_json_exposure.json  # [NEW] Exposure/misconfig findings
```

### Testing Standards

- **100% coverage** on `parsers/nuclei.py` (enforced gate)
- **TDD phases** marked in tasks: [RED] → [GREEN] → [REFACTOR]
- **Unit tests** in `tests/unit/tools/parsers/test_nuclei.py`
- **Integration tests** in `tests/integration/tools/test_nuclei_parser.py`
- Use `pytest.mark.unit` and `pytest.mark.integration` markers

### Key Learnings from Story 4.6 (Previous Story)

1. **Export verification is critical** — Always test imports work
2. **Use structlog for logging** — NOT `print()` statements
3. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases
4. **Verify coverage claims before marking done** — Run `pytest --cov` explicitly
5. **Finding validation is strict** — UUIDs must be valid, timestamps must be ISO 8601
6. **Catch exceptions** — Return empty list on parse errors, don't crash
7. **Auto-detect format** — nmap parser auto-detects XML vs grepable, nuclei should auto-detect JSON vs plain text
8. **Create _create_finding helper** — Reduces code duplication and ensures consistent Finding creation

### Nuclei Severity Mapping

| Nuclei Severity | Finding Severity |
|-----------------|------------------|
| critical        | critical         |
| high            | high             |
| medium          | medium           |
| low             | low              |
| info            | info             |
| unknown         | info             |

### Error Handling

| Error | Handling | Notes |
|-------|----------|-------|
| Invalid JSON | Skip line | Log warning, continue parsing other lines |
| Missing fields | Use defaults | Empty strings for optional fields |
| Empty output | Return empty list | Normal for scans with no findings |
| Mixed format | Try each line | Some lines may be status, not findings |

### References

- **Epic Story:** [epics-stories.md#Story 4.7](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L1831)
- **Architecture - Finding Model:** [architecture.md#L608](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L608)
- **Previous Story 4.6:** [4-6-tier-1-parser-nmap.md](file:///root/red/_bmad-output/implementation-artifacts/4-6-tier-1-parser-nmap.md)
- **ParserFn Type:** [parsers/base.py](file:///root/red/src/cyberred/tools/parsers/base.py)
- **Finding Model:** [core/models.py](file:///root/red/src/cyberred/core/models.py)
- **Nmap Parser (Reference):** [parsers/nmap.py](file:///root/red/src/cyberred/tools/parsers/nmap.py)

## Development Agent Record

- **Agent:** antigravity
- **Date:** 2026-01-06
- **Result:** Completed all tasks with 100% test coverage. Implemented robust JSON and plain text parsing, including full field extraction and finding classification. Code review fixes applied.

### File List

| Action | File Path |
|--------|-----------|
| [NEW] | `src/cyberred/tools/parsers/nuclei.py` |
| [MODIFY] | `src/cyberred/tools/parsers/__init__.py` |
| [NEW] | `tests/unit/tools/parsers/test_nuclei.py` |
| [NEW] | `tests/integration/tools/test_nuclei_parser.py` |
| [NEW] | `tests/fixtures/tool_outputs/nuclei_json_basic.json` |
| [NEW] | `tests/fixtures/tool_outputs/nuclei_json_multi.json` |
| [NEW] | `tests/fixtures/tool_outputs/nuclei_json_exposure.json` |
| [NEW] | `tests/fixtures/tool_outputs/nuclei_plain.txt` |

### Change Log

| Date | Change | Reason |
|------|--------|--------|
| 2026-01-06 | Initial implementation | Completed all tasks for nuclei parser |
| 2026-01-06 | Code review fixes | Fixed import ordering, added logging consistency, added missing fixture and integration tests |
