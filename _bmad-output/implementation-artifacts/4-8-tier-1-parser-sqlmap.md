# Story 4.8: Tier 1 Parser - sqlmap

Status: done

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD method at all times. All tasks below are strictly marked with [RED], [GREEN], [REFACTOR] phases which must be followed explicitly.

## Story

As a **developer**,
I want **a structured parser for sqlmap output**,
So that **SQL injection findings include injection type and database details (FR33)**.

## Acceptance Criteria

1. **Given** Story 4.5 is complete
   **When** sqlmap output is passed to the parser
   **Then** parser extracts vulnerable parameters

2. **Given** valid sqlmap output
   **When** I parse the output
   **Then** parser extracts injection types (boolean-blind, time-blind, UNION, stacked, error-based)

3. **Given** sqlmap has detected a database
   **When** I parse the output
   **Then** parser extracts database type and version when detected

4. **Given** sqlmap has performed enumeration
   **When** I parse the output
   **Then** parser extracts table/column enumeration results if performed

5. **Given** SQL injection findings
   **When** examining the findings
   **Then** findings have `type="sqli"` with parameter, injection_type, dbms in evidence

6. **Given** the sqlmap parser
   **When** running integration tests
   **Then** tests verify against real sqlmap output from cyber range

7. **Given** the sqlmap parser module
   **When** running unit tests with coverage
   **Then** unit tests achieve 100% coverage on `src/cyberred/tools/parsers/sqlmap.py`

## Tasks / Subtasks

### Phase 1: Parser Module Foundation [RED → GREEN → REFACTOR]

- [x] Task 1: Create sqlmap parser module with ParserFn signature (AC: 1)
  - [x] **[RED]** Write failing test: `sqlmap_parser(stdout, stderr, exit_code, agent_id, target)` exists and matches `ParserFn` type
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/sqlmap.py` with function signature
  - [x] **[REFACTOR]** Add docstring and type hints per architecture standard

- [x] Task 2: Parse basic sqlmap output structure (AC: 1)
  - [x] **[RED]** Write failing test: parser returns empty list for empty/invalid output
  - [x] **[RED]** Write failing test: parser detects sqlmap banner and processing lines
  - [x] **[GREEN]** Use regex to parse sqlmap stdout format (handle `--batch` non-interactive output)
  - [x] **[REFACTOR]** Add error handling for malformed output (return empty list, don't raise)

### Phase 2: Vulnerability Detection [RED → GREEN → REFACTOR]

- [x] Task 3: Extract vulnerable parameters (AC: 1)
  - [x] **[RED]** Write failing test: parser extracts parameter name from `Parameter: <param> (type)` line
  - [x] **[RED]** Write failing test: parser identifies GET, POST, COOKIE, HEADER injection points
  - [x] **[GREEN]** Parse lines matching `Parameter: (\w+) \((GET|POST|Cookie|Header)\)` regex
  - [x] **[REFACTOR]** Store parameter type for evidence field

- [x] Task 4: Extract injection types (AC: 2)
  - [x] **[RED]** Write failing test: parser extracts "boolean-based blind" from `Type: boolean-based blind`
  - [x] **[RED]** Write failing test: parser extracts "time-based blind" from `Type: time-based blind`
  - [x] **[RED]** Write failing test: parser extracts "UNION query" from `Type: UNION query`
  - [x] **[RED]** Write failing test: parser extracts "stacked queries" from `Type: stacked queries`
  - [x] **[RED]** Write failing test: parser extracts "error-based" from `Type: error-based`
  - [x] **[GREEN]** Parse `Type: (.+)` regex to extract injection type
  - [x] **[REFACTOR]** Normalize injection type names (lowercase, hyphenated)

### Phase 3: Database Detection [RED → GREEN → REFACTOR]

- [x] Task 5: Extract database type (AC: 3)
  - [x] **[RED]** Write failing test: parser extracts DBMS from `back-end DBMS: MySQL`
  - [x] **[RED]** Write failing test: parser handles PostgreSQL, SQLite, MSSQL, Oracle
  - [x] **[GREEN]** Parse `back-end DBMS: (.+)` regex
  - [x] **[REFACTOR]** Normalize DBMS names

- [x] Task 6: Extract database version (AC: 3)
  - [x] **[RED]** Write failing test: parser extracts version from `back-end DBMS: MySQL >= 5.7`
  - [x] **[GREEN]** Parse version info after DBMS name
  - [x] **[REFACTOR]** Include version in evidence field

### Phase 4: Enumeration Results [RED → GREEN → REFACTOR]

- [x] Task 7: Extract database names (AC: 4)
  - [x] **[RED]** Write failing test: parser extracts databases from `available databases` section
  - [x] **[GREEN]** Parse database list with `[*] database_name` pattern
  - [x] **[REFACTOR]** Create Finding for each enumerated database with `type="sqli_db"`

- [x] Task 8: Extract table names (AC: 4)
  - [x] **[RED]** Write failing test: parser extracts tables from database enumeration
  - [x] **[GREEN]** Parse table list with `[*] table_name` pattern under database context
  - [x] **[REFACTOR]** Create Finding for enumerated tables with `type="sqli_table"`

- [x] Task 9: Extract column details (AC: 4)
  - [x] **[RED]** Write failing test: parser extracts columns from table enumeration
  - [x] **[GREEN]** Parse column list with name and type
  - [x] **[REFACTOR]** Create Finding for enumerated columns with `type="sqli_column"`

### Phase 5: Finding Object Creation [RED → GREEN → REFACTOR]

- [x] Task 10: Create Finding objects for SQL injection (AC: 5)
  - [x] **[RED]** Write failing test: each SQLi finding has correct 10 fields
  - [x] **[GREEN]** Create `Finding(type="sqli", ...)` with UUID, timestamp, topic, empty signature
  - [x] **[REFACTOR]** Include parameter, injection_type, dbms in evidence field

- [x] Task 11: Apply correct severity levels (AC: 5)
  - [x] **[RED]** Write failing test: UNION/stacked queries → "critical" severity
  - [x] **[RED]** Write failing test: error-based → "high" severity
  - [x] **[RED]** Write failing test: boolean-blind/time-blind → "high" severity
  - [x] **[GREEN]** Map injection types to severity levels
  - [x] **[REFACTOR]** Document severity mapping rationale

### Phase 6: Registration & Exports [RED → GREEN → REFACTOR]

- [x] Task 12: Register parser with OutputProcessor (AC: 1)
  - [x] **[RED]** Write failing test: `OutputProcessor.register_parser("sqlmap", sqlmap_parser)` works
  - [x] **[GREEN]** Import and export `sqlmap_parser` from `parsers/__init__.py`
  - [x] **[REFACTOR]** Add to auto-registration list

- [x] Task 13: Export from tools package (AC: 1)
  - [x] **[RED]** Write test: `from cyberred.tools.parsers import sqlmap_parser` works
  - [x] **[GREEN]** Add export to `parsers/__init__.py`
  - [x] **[REFACTOR]** Update `__all__` list

### Phase 7: Integration & Fixtures [RED → GREEN → REFACTOR]

- [x] Task 14: Create test fixtures (AC: 6)
  - [x] Create `tests/fixtures/tool_outputs/sqlmap_basic.txt` (single injection point)
  - [x] Create `tests/fixtures/tool_outputs/sqlmap_multi.txt` (multiple injection types)
  - [x] Create `tests/fixtures/tool_outputs/sqlmap_enum.txt` (database/table enumeration)
  - [x] Create `tests/fixtures/tool_outputs/sqlmap_nosqli.txt` (no vulnerabilities found)

- [x] Task 15: Create integration test (AC: 6)
  - [x] Create `tests/integration/tools/test_sqlmap_parser.py`
  - [x] Test full pipeline: fixture → sqlmap_parser → valid Findings
  - [x] Verify Finding fields match expected values from fixture

- [x] Task 16: Achieve 100% test coverage (AC: 7)
  - [x] Run `pytest --cov=src/cyberred/tools/parsers/sqlmap --cov-report=term-missing`
  - [x] Ensure all lines/branches are covered
  - [x] Add edge case tests as needed

### Phase 8: Documentation [BLUE]

- [x] Task 17: Documentation & Handover
  - [x] Update Dev Agent Record in this story file
  - [x] Verify all tasks are marked complete
  - [x] Ensure story status is updated to `review`
  - [x] Complete file list with actions

## Dev Notes

> [!TIP]
> **Quick Reference:** Create `sqlmap_parser()` function in `tools/parsers/sqlmap.py` that parses sqlmap stdout output. Return `List[Finding]` with `type="sqli"`, `type="sqli_db"`, `type="sqli_table"`, `type="sqli_column"`. Register with `OutputProcessor`. Achieve 100% coverage.

### ParserFn Signature (CRITICAL)

The parser MUST follow the exact signature from `parsers/base.py`:

```python
from cyberred.tools.parsers.base import ParserFn

# Standard signature: (stdout, stderr, exit_code, agent_id, target) -> List[Finding]
def sqlmap_parser(
    stdout: str, 
    stderr: str, 
    exit_code: int, 
    agent_id: str, 
    target: str
) -> List[Finding]:
    ...
```

### Finding Model (CRITICAL)

The `Finding` dataclass is defined in [`core/models.py`](file:///root/red/src/cyberred/core/models.py#L97). 

**Required Fields for `Finding`:**
- `id` (UUID), `agent_id` (UUID), `timestamp` (ISO 8601), `target` (IP/URL)
- `type` ("sqli", "sqli_db", "sqli_table", "sqli_column")
- `severity` ("critical", "high", "medium", "low", "info")
- `evidence` (Raw output snippet), `tool` ("sqlmap"), `topic` (Redis channel), `signature` (empty)

> [!CAUTION]
> **Validation:** The `Finding` dataclass strictly validates formats. Invalid values raise `ValueError`.

### SQLmap Output Structure Reference

SQLmap outputs progress messages and findings to stdout. Key patterns to parse:

```
[INFO] testing connection to the target URL
[INFO] testing if the target URL content is stable
[INFO] target URL content is stable
[INFO] testing if GET parameter 'id' is dynamic
[INFO] GET parameter 'id' appears to be dynamic
[INFO] heuristic (basic) test shows that GET parameter 'id' might be injectable
[INFO] testing for SQL injection on GET parameter 'id'
[INFO] testing 'AND boolean-based blind - WHERE or HAVING clause'
[INFO] GET parameter 'id' appears to be 'AND boolean-based blind - WHERE or HAVING clause' injectable
[INFO] testing 'MySQL >= 5.5 AND error-based - WHERE, HAVING, ORDER BY or GROUP BY clause (BIGINT UNSIGNED)'
[INFO] GET parameter 'id' is 'MySQL >= 5.5 AND error-based - WHERE, HAVING, ORDER BY or GROUP BY clause (BIGINT UNSIGNED)' injectable

---
Parameter: id (GET)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE or HAVING clause
    Payload: id=1' AND 5851=5851 AND 'mDWN'='mDWN

    Type: error-based
    Title: MySQL >= 5.5 AND error-based - WHERE, HAVING, ORDER BY or GROUP BY clause (BIGINT UNSIGNED)
    Payload: id=1' AND (SELECT 2*(IF((SELECT * FROM (SELECT CONCAT(0x7162767a71,(SELECT (ELT(2836=2836,1))),0x716a717871,0x78))s), 8446744073709551610, 8446744073709551610))) AND 'cKkH'='cKkH

    Type: time-based blind
    Title: MySQL >= 5.0.12 AND time-based blind (query SLEEP)
    Payload: id=1' AND SLEEP(5) AND 'MhAy'='MhAy

    Type: UNION query
    Title: Generic UNION query (NULL) - 3 columns
    Payload: id=1' UNION ALL SELECT NULL,CONCAT(0x7162767a71,0x4e5a504f5378684f4978656d6141455a745574457a7a51744d5a6d4461756d6e704b637577446779,0x716a717871),NULL-- -
---
[INFO] the back-end DBMS is MySQL
web application technology: PHP 7.4.3, Apache 2.4.41
back-end DBMS: MySQL >= 5.5
```

### Database Enumeration Output

```
available databases [3]:
[*] information_schema
[*] mysql
[*] testdb

Database: testdb
[*] users
[*] products

Table: testdb.users
+----------+-------------+
| Column   | Type        |
+----------+-------------+
| id       | int(11)     |
| username | varchar(50) |
| password | varchar(50) |
+----------+-------------+
```

### Implementation Pattern (Optimized)

Focus on the SQLMap-specific regex logic. Boilerplate (imports, logger) matches `nmap.py` / `nuclei.py`.

```python
# ... standard imports and logger ...
# ... SQLI_SEVERITY_MAP ...

def sqlmap_parser(stdout: str, stderr: str, exit_code: int, agent_id: str, target: str) -> List[Finding]:
    """Parse sqlmap stdout (including --batch mode) to Findings."""
    findings: List[Finding] = []
    if not stdout.strip(): return findings
    
    # 1. Injection Points
    # Split by separator to handle multiple parameters
    param_blocks = re.split(r'---\s*\n', stdout)
    for block in param_blocks:
        # Regex: Parameter: id (GET)
        param_match = re.search(r'Parameter: (\w+) \((\w+)\)', block)
        if param_match:
            p_name, p_type = param_match.groups()
            # Regex: Type: boolean-based blind
            for inj_type in re.findall(r'Type: ([^\n]+)', block):
                 findings.append(_create_finding(
                    type="sqli",
                    severity=_get_severity(inj_type.lower()),
                    target=target,
                    evidence=f"Parameter: {p_name} ({p_type}) | Type: {inj_type}",
                    agent_id=agent_id
                 ))

    # 2. Database Info
    # Regex: back-end DBMS: MySQL >= 5.0
    if dbms := re.search(r'back-end DBMS:\s*(.+)', stdout):
        findings.append(_create_finding("sqli", "info", target, f"DBMS: {dbms.group(1)}", agent_id))

    # 3. Enumeration (DBs, Tables, Columns)
    # Regex: available databases [3]:\n[*] ...
    if dbs_block := re.search(r'available databases \[\d+\]:\n((?:\[\*\] .+\n)+)', stdout):
        for db in re.findall(r'\[\*\] (\S+)', dbs_block.group(1)):
            findings.append(_create_finding("sqli_db", "info", target, f"Database: {db}", agent_id))

    log.info("sqlmap_parsed", count=len(findings))
    return findings
```

### Severity Mapping

| Injection Type | Finding Severity | Rationale |
|----------------|------------------|-----------|
| UNION query | critical | Direct data extraction possible |
| stacked queries | critical | Full DB access, command execution possible |
| error-based | high | Data extraction via error messages |
| boolean-based blind | high | Data extraction possible but slower |
| time-based blind | high | Data extraction possible but very slow |
| Enumeration results | info | Information disclosure only |

### Project Structure Notes

Files to create/modify:

```
src/cyberred/tools/parsers/
├── __init__.py          # [MODIFY] Add sqlmap_parser export
├── base.py              # [UNCHANGED] ParserFn type
├── nmap.py              # [UNCHANGED] Reference implementation
├── nuclei.py            # [UNCHANGED] Reference implementation
└── sqlmap.py            # [NEW] sqlmap stdout parser

tests/
├── unit/tools/parsers/
│   └── test_sqlmap.py   # [NEW] Unit tests for sqlmap parser
├── integration/tools/
│   └── test_sqlmap_parser.py  # [NEW] Integration tests
└── fixtures/tool_outputs/
    ├── sqlmap_basic.txt      # [NEW] Single injection point
    ├── sqlmap_multi.txt      # [NEW] Multiple injection types
    ├── sqlmap_enum.txt       # [NEW] Database enumeration
    └── sqlmap_nosqli.txt     # [NEW] No vulnerabilities found
```

### Testing Standards

- **100% coverage** on `parsers/sqlmap.py` (enforced gate)
- **TDD phases** marked in tasks: [RED] → [GREEN] → [REFACTOR]
- **Unit tests** in `tests/unit/tools/parsers/test_sqlmap.py`
- **Integration tests** in `tests/integration/tools/test_sqlmap_parser.py`
- Use `pytest.mark.unit` and `pytest.mark.integration` markers

### Key Learnings from Previous Stories (4.6 nmap, 4.7 nuclei)

1. **Export verification is critical** — Always test imports work
2. **Use structlog for logging** — NOT `print()` statements
3. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases
4. **Verify coverage claims before marking done** — Run `pytest --cov` explicitly
5. **Finding validation is strict** — UUIDs must be valid, timestamps must be ISO 8601
6. **Catch exceptions** — Return empty list on parse errors, don't crash
7. **Auto-detect format** — nmap does XML/grepable, nuclei does JSON/plain, sqlmap is stdout-based
8. **Create _create_finding helper** — Reduces code duplication
9. **Use pytest markers** — Always include `@pytest.mark.unit` and `@pytest.mark.integration`
10. **Create fixtures for all edge cases** — Empty output, malformed data, multiple findings

### Error Handling

| Error | Handling | Notes |
|-------|----------|-------|
| Empty output | Return empty list | Normal when no SQLi found |
| No parameter sections | Return empty list | Output may not contain injection findings |
| Malformed regex patterns | Skip and continue | Log warning, parse other sections |
| Missing DBMS info | Skip database finding | DBMS may not always be detected |

### References

- **Epic Story:** [epics-stories.md#Story 4.8](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L1854)
- **Architecture - Finding Model:** [architecture.md#L608](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L608)
- **Previous Story 4.7:** [4-7-tier-1-parser-nuclei.md](file:///root/red/_bmad-output/implementation-artifacts/4-7-tier-1-parser-nuclei.md)
- **Previous Story 4.6:** [4-6-tier-1-parser-nmap.md](file:///root/red/_bmad-output/implementation-artifacts/4-6-tier-1-parser-nmap.md)
- **ParserFn Type:** [parsers/base.py](file:///root/red/src/cyberred/tools/parsers/base.py)
- **Finding Model:** [core/models.py](file:///root/red/src/cyberred/core/models.py)

## Dev Agent Record

### Agent Model Used

gemini-2.5-pro

### Debug Log References

### Completion Notes List

### File List

| Action | File Path |
|--------|-----------|
| [NEW] | `src/cyberred/tools/parsers/sqlmap.py` |
| [MODIFY] | `src/cyberred/tools/parsers/__init__.py` |
| [NEW] | `tests/unit/tools/parsers/test_sqlmap.py` |
| [NEW] | `tests/integration/tools/test_sqlmap_parser.py` |
| [NEW] | `tests/fixtures/tool_outputs/sqlmap_basic.txt` |
| [NEW] | `tests/fixtures/tool_outputs/sqlmap_multi.txt` |
| [NEW] | `tests/fixtures/tool_outputs/sqlmap_enum.txt` |
| [NEW] | `tests/fixtures/tool_outputs/sqlmap_nosqli.txt` |
