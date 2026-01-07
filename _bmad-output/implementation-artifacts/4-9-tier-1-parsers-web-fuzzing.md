Status: done

...

## Dev Agent Record

### Agent Model Used

Google Gemini 2.0 (Antigravity)

### Debug Log References

- Integration tests fixed by using valid UUIDs.
- `ffuf` parser required specific JSON key checking for inputs.
- `hydra` parser regex updated to support service names with hyphens (e.g. `http-get`).

### Completion Notes List

- Implemented `common.py` to standardize `create_finding` and `generate_topic`.
- Implemented `ffuf`, `nikto`, `hydra` parsers with 100% test coverage.
- Refactored `nmap`, `nuclei`, `sqlmap` to use `common.py` for consistent ID and Topic generation.
- Added integration tests verifying all 6 parsers against static fixtures.
- All acceptance criteria met.

### File List

| Action | File Path |
|--------|-----------|
| [NEW] | `src/cyberred/tools/parsers/common.py` |
| [NEW] | `src/cyberred/tools/parsers/ffuf.py` |
| [NEW] | `src/cyberred/tools/parsers/nikto.py` |
| [NEW] | `src/cyberred/tools/parsers/hydra.py` |
| [MODIFY] | `src/cyberred/tools/parsers/nmap.py` |
| [MODIFY] | `src/cyberred/tools/parsers/nuclei.py` |
| [MODIFY] | `src/cyberred/tools/parsers/sqlmap.py` |
| [MODIFY] | `src/cyberred/tools/parsers/__init__.py` |
| [NEW] | `tests/unit/tools/parsers/test_common.py` |
| [NEW] | `tests/unit/tools/parsers/test_ffuf.py` |
| [NEW] | `tests/unit/tools/parsers/test_nikto.py` |
| [NEW] | `tests/unit/tools/parsers/test_hydra.py` |
| [NEW] | `tests/integration/tools/test_ffuf_parser.py` |
| [NEW] | `tests/integration/tools/test_nikto_parser.py` |
| [NEW] | `tests/integration/tools/test_hydra_parser.py` |
| [NEW] | `fixtures/tool_outputs/ffuf_results.json` |
| [NEW] | `fixtures/tool_outputs/nikto_results.txt` |
| [NEW] | `fixtures/tool_outputs/hydra_results.txt` |

## Story

As a **developer**,
I want **structured parsers for ffuf, nikto, and hydra** utilizing a shared common library,
So that **web fuzzing, scanning, and credential attacks have reliable parsing (FR33) and architectural compliance**.

## Acceptance Criteria

1. **Given** Story 4.5 is complete
   **When** ffuf JSON output is passed to ffuf parser
   **Then** parser extracts discovered paths with status code, size, words, lines

2. **Given** valid ffuf output
   **When** I parse the output
   **Then** findings have `type="directory"` or `type="file"` and use architecturally compliant topics

3. **Given** nikto output is passed to nikto parser
   **When** I parse the output
   **Then** parser extracts vulnerabilities with OSVDB/CVE references

4. **Given** valid nikto output
   **When** examining findings
   **Then** findings have `type="web_vuln"` and utilize shared finding creation logic

5. **Given** hydra output is passed to hydra parser
   **When** I parse the output
   **Then** parser extracts successful credential pairs

6. **Given** valid hydra output
   **When** examining findings
   **Then** findings have `type="credential"` with critical severity

7. **Given** `src/cyberred/tools/parsers/common.py`
   **When** implementing parsers
   **Then** all parsers import and use `create_finding` and path/topic helpers to avoid duplication

8. **Given** the parsers
   **When** running integration tests
   **Then** tests verify all three parsers against cyber range fixtures

9. **Given** the parser modules
   **When** running unit tests with coverage
   **Then** unit tests achieve 100% coverage on each parser module

## Tasks / Subtasks

### Phase 0: Shared Infrastructure [RED → GREEN → REFACTOR]

- [x] Task 1: Create `parsers/common.py` module (AC: 7)
  - [x] **[RED]** Write failing test: `create_finding` exists and returns valid Finding object
  - [x] **[RED]** Write failing test: `generate_topic(target, type)` returns valid `findings:{hash}:{type}` string
  - [x] **[GREEN]** Implement `create_finding` with standard fields and validation
  - [x] **[GREEN]** Implement `generate_topic` using MD5 hash of target (mod 16 if needed, or simple hash) per architecture
  - [x] **[REFACTOR]** Ensure robust type hinting and docstrings

### Phase 1: ffuf Parser Foundation [RED → GREEN → REFACTOR]

- [x] Task 2: Create ffuf parser module with ParserFn signature (AC: 1)
  - [x] **[RED]** Write failing test: `ffuf_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `ffuf.py` importing `common.create_finding`
  - [x] **[REFACTOR]** Add standard docstrings

- [x] Task 3: Parse ffuf JSON output structure (AC: 1, 2)
  - [x] **[RED]** Write failing test: parser correctly parses `results` array from ffuf JSON
  - [x] **[GREEN]** Use `json.loads()` and `common.create_finding`
  - [x] **[REFACTOR]** Add error handling for malformed JSON

- [x] Task 4: Extract discovered paths from ffuf (AC: 1, 2)
  - [x] **[RED]** Write failing test: parser determines `type="directory"` vs `type="file"`
  - [x] **[GREEN]** Extract fields and call `create_finding(..., type_val=ftype, topic=common.generate_topic(target, ftype))`
  - [x] **[REFACTOR]** Optimize loop

### Phase 2: nikto Parser [RED → GREEN → REFACTOR]

- [x] Task 5: Create nikto parser module (AC: 3)
  - [x] **[RED]** Write failing test: `nikto_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `nikto.py` importing `common`
  - [x] **[REFACTOR]** Standard setup

- [x] Task 6: Parse nikto stdout vulnerabilities (AC: 3, 4)
  - [x] **[RED]** Write failing test: parser extracts OSVDB references
  - [x] **[RED]** Write failing test: parser extracts CVE references
  - [x] **[RED]** Write failing test: parser handles lines without "+" prefix gracefully
  - [x] **[GREEN]** Implement robust regex parsing for nikto output
  - [x] **[REFACTOR]** Use `common.create_finding` with correct severity mapping

### Phase 3: hydra Parser [RED → GREEN → REFACTOR]

- [x] Task 7: Create hydra parser module (AC: 5)
  - [x] **[RED]** Write failing test: `hydra_parser` matches `ParserFn` signature
  - [x] **[GREEN]** Create `hydra.py` using `common`
  - [x] **[REFACTOR]** Standard setup

- [x] Task 8: Extract credentials from hydra (AC: 5, 6)
  - [x] **[RED]** Write failing test: parser extracts credentials from standard hydra success line
  - [x] **[GREEN]** Parse regex and call `common.create_finding(..., type_val="credential", severity="critical")`
  - [x] **[REFACTOR]** Handle minimal output cases

### Phase 4: Refactor Existing & Export [BLUE]

- [x] Task 9: Refactor existing parsers to use `common.py` (AC: 7)
  - [x] **[REFACTOR]** Update `nmap.py` to use `common.create_finding`
  - [x] **[REFACTOR]** Update `nuclei.py` to use `common.create_finding`
  - [x] **[REFACTOR]** Update `sqlmap.py` to use `common.create_finding`
  - [x] Verify 100% coverage is maintained on existing parsers

- [x] Task 10: Register & Export new parsers (AC: 8)
  - [x] Update `parsers/__init__.py` with new exports
  - [x] Verify OutputProcessor integration

### Phase 5: Verification & Tests [RED → GREEN → REFACTOR]

- [x] Task 11: Create comprehensive test fixtures (AC: 8)
  - [x] `fixtures/tool_outputs/ffuf_*.json`
  - [x] `fixtures/tool_outputs/nikto_*.txt`
  - [x] `fixtures/tool_outputs/hydra_*.txt`

- [x] Task 12: Complete Unit & Integration Tests (AC: 9)
  - [x] `tests/unit/tools/parsers/test_common.py` (New!)
  - [x] `tests/unit/tools/parsers/test_ffuf.py`
  - [x] `tests/unit/tools/parsers/test_nikto.py`
  - [x] `tests/unit/tools/parsers/test_hydra.py`
  - [x] Integration tests for all 3

- [x] Task 13: 100% Coverage Gate (AC: 9)
  - [x] Verify `pytest --cov` is 100% for `common.py` and all parsers

### Phase 6: Documentation [BLUE]

- [x] Task 14: Documentation & Handover
  - [x] Update Dev Agent Record
  - [x] Verify all tasks complete

## Dev Notes

> [!TIP]
> **Architecture Update:** This story introduces `src/cyberred/tools/parsers/common.py` to centralize Finding creation and Topic generation. You MUST implement and use this shared module.

### Common Module Specification

```python
# src/cyberred/tools/parsers/common.py
import uuid
import hashlib
from datetime import datetime, timezone
from cyberred.core.models import Finding

def generate_topic(target: str, finding_type: str) -> str:
    """
    Generate architecture-compliant topic: findings:{target_hash}:{type}
    Target hash is first 8 chars of MD5(target).
    """
    target_hash = hashlib.md5(target.encode()).hexdigest()[:8]
    return f"findings:{target_hash}:{finding_type}"

def create_finding(
    type_val: str,
    severity: str,
    target: str,
    evidence: str,
    agent_id: str,
    tool: str,
    topic: str = None
) -> Finding:
    """
    Factory for Finding objects. 
    If topic is None, auto-generates using generate_topic(target, type_val).
    """
    if topic is None:
        topic = generate_topic(target, type_val)
        
    return Finding(
        id=str(uuid.uuid4()),
        type=type_val,
        severity=severity,
        target=target,
        evidence=evidence,
        agent_id=agent_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        tool=tool,
        topic=topic,
        signature=""
    )
```

### Implementation Patterns (Updated)

**nikto_parser** (Robust Regex):
```python
from . import common

def nikto_parser(...):
    # ...
    # Handle standard "+ OSVDB-..." lines
    # Also handle lines that might miss the '+' prefix if output varies
    # Pattern: Optional[+ ](Ref): (Path): (Desc)
    pattern = re.compile(r'(?:\+\s+)?((?:OSVDB|CVE)-\S+):\s+([^:]+):\s+(.+)')
    
    for line in stdout.splitlines():
        match = pattern.search(line)
        if match:
            ref, path, desc = match.groups()
            # Determine severity
            severity = "high" if "CVE" in ref else "medium"
            
            findings.append(common.create_finding(
                type_val="web_vuln",
                severity=severity,
                target=target,
                evidence=f"[{ref}] {path}: {desc}",
                agent_id=agent_id,
                tool="nikto"
            ))
    # ...
```

**hydra_parser** (Critical Credentials):
```python
from . import common

def hydra_parser(...):
    # ...
    # Pattern: [22][ssh] host: 192.168.1.1   login: admin   password: password123
    pattern = re.compile(r'\[(\d+)\]\[(\w+)\]\s+host:\s+(\S+)\s+login:\s+(\S+)\s+password:\s+(\S+)')
    
    for match in pattern.finditer(stdout):
        port, service, host, username, password = match.groups()
        findings.append(common.create_finding(
            type_val="credential",
            severity="critical",
            target=host,
            evidence=f"[{service}:{port}] {username}:{password}",
            agent_id=agent_id,
            tool="hydra"
        ))
    return findings
```

### Reference

- **Architecture:** [architecture.md#Topic Sharding](file:///root/red/_bmad-output/planning-artifacts/architecture.md)
- **Previous Story:** [4-8-tier-1-parser-sqlmap.md](file:///root/red/_bmad-output/implementation-artifacts/4-8-tier-1-parser-sqlmap.md)


