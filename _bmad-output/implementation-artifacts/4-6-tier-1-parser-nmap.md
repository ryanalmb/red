# Story 4.6: Tier 1 Parser - nmap

Status: done

> [!IMPORTANT]
> **TDD CONSTRAINT:** Follow TDD method at all times. All tasks below are strictly marked with [RED], [GREEN], [REFACTOR] phases which must be followed explicitly.

## Story

As a **developer**,
I want **a structured parser for nmap output**,
So that **port scan findings are extracted reliably without LLM (FR33)**.

## Acceptance Criteria

1. **Given** Story 4.5 is complete
   **When** nmap XML output (`-oX`) is passed to the parser
   **Then** parser extracts all open ports with service, version, state

2. **Given** valid nmap XML output
   **When** I parse the output
   **Then** parser extracts host status (up/down)

3. **Given** nmap output contains OS detection
   **When** I parse the output  
   **Then** parser extracts OS detection results if present

4. **Given** nmap output contains NSE script results
   **When** I parse the output
   **Then** parser extracts script output if NSE scripts were run

5. **Given** open ports are found
   **When** examining the findings
   **Then** each finding has `type="open_port"` with port, protocol, service, version

6. **Given** the nmap parser
   **When** running integration tests
   **Then** tests verify against real nmap output from cyber range

7. **Given** the nmap parser module
   **When** running unit tests with coverage
   **Then** unit tests achieve 100% coverage on `src/cyberred/tools/parsers/nmap.py`

## Tasks / Subtasks

### Phase 1: XML Parser Foundation [RED → GREEN → REFACTOR]

- [x] Task 1: Create nmap parser module with ParserFn signature (AC: 1)
  - [x] **[RED]** Write failing test: `nmap_parser(stdout, stderr, exit_code, agent_id, target)` exists and matches `ParserFn` type
  - [x] **[GREEN]** Create `src/cyberred/tools/parsers/nmap.py` with function signature
  - [x] **[REFACTOR]** Add docstring and type hints per architecture standard

- [x] Task 2: Parse basic nmap XML structure (AC: 1, 2)
  - [x] **[RED]** Write failing test: parser returns empty list for invalid/empty XML
  - [x] **[RED]** Write failing test: parser correctly parses `<nmaprun>` root element
  - [x] **[GREEN]** Use `xml.etree.ElementTree` to parse XML from stdout
  - [x] **[REFACTOR]** Add error handling for malformed XML (return empty list, don't raise)

### Phase 2: Port Extraction [RED → GREEN → REFACTOR]

- [x] Task 3: Extract open ports from XML (AC: 1, 5)
  - [x] **[RED]** Write failing test: parser extracts port number, protocol, state from `<port>` elements
  - [x] **[GREEN]** Iterate `<port>` elements under `<host>/<ports>`
  - [x] **[REFACTOR]** Filter to only `state="open"` ports

- [x] Task 4: Extract service detection (AC: 1, 5)
  - [x] **[RED]** Write failing test: parser extracts service name and version from `<service>` child
  - [x] **[GREEN]** Parse `<service name= product= version=>` attributes
  - [x] **[REFACTOR]** Handle missing attributes gracefully (empty strings)

- [x] Task 5: Create Finding objects for open ports (AC: 5)
  - [x] **[RED]** Write failing test: each open port creates a `Finding` with correct fields
  - [x] **[GREEN]** Create `Finding(type="open_port", ...)` with UUID, timestamp, topic, empty signature
  - [x] **[REFACTOR]** Include port/protocol/service/version in evidence field

### Phase 3: Host and OS Detection [RED → GREEN → REFACTOR]

- [x] Task 6: Extract host status (AC: 2)
  - [x] **[RED]** Write failing test: parser detects host up/down from `<status state="up/down">` 
  - [x] **[GREEN]** Parse `<host>/<status>` element's state attribute
  - [x] **[REFACTOR]** Create `Finding(type="host_status", ...)` for each host

- [x] Task 7: Extract OS detection results (AC: 3)
  - [x] **[RED]** Write failing test: parser extracts OS family and accuracy from `<osmatch>`
  - [x] **[GREEN]** Parse `<os>/<osmatch name= accuracy=>` elements
  - [x] **[REFACTOR]** Create `Finding(type="os_detection", ...)` with top match

### Phase 4: NSE Script Output [RED → GREEN → REFACTOR]

- [x] Task 8: Extract script output (AC: 4)
  - [x] **[RED]** Write failing test: parser extracts script id and output from `<script>` elements
  - [x] **[GREEN]** Parse `<script id= output=>` attributes under ports and hosts
  - [x] **[REFACTOR]** Create `Finding(type="nse_script", ...)` for each script result

### Phase 5: Grepable Output Support [RED → GREEN → REFACTOR]

- [x] Task 9: Support grepable output format (AC: 1 extension)
  - [x] **[RED]** Write failing test: parser detects and parses `-oG` format
  - [x] **[GREEN]** Use regex to extract `Host: IP ... Ports: port/state/proto/service...`
  - [x] **[REFACTOR]** Auto-detect format (XML vs grepable) based on content

### Phase 6: Registration & Exports [RED → GREEN → REFACTOR]

- [x] Task 10: Register parser with OutputProcessor (AC: 1)
  - [x] **[RED]** Write failing test: `OutputProcessor.register_parser("nmap", nmap_parser)` works
  - [x] **[GREEN]** Import and export `nmap_parser` from `parsers/__init__.py`
  - [x] **[REFACTOR]** Add auto-registration pattern in parsers module

- [x] Task 11: Export from tools package (AC: 1)
  - [x] **[RED]** Write test: `from cyberred.tools.parsers import nmap_parser` works
  - [x] **[GREEN]** Add export to `parsers/__init__.py`
  - [x] **[REFACTOR]** Verify `__all__` list

### Phase 7: Integration & Fixtures [RED → GREEN → REFACTOR]

- [x] Task 12: Create XML test fixtures (AC: 6)
  - [x] Create `tests/fixtures/tool_outputs/nmap_xml_basic.xml` (single host, few ports)
  - [x] Create `tests/fixtures/tool_outputs/nmap_xml_os.xml` (with OS detection)
  - [x] Create `tests/fixtures/tool_outputs/nmap_xml_scripts.xml` (with NSE scripts)
  - [x] Create `tests/fixtures/tool_outputs/nmap_grepable.txt` (grepable format)

- [x] Task 13: Create integration test (AC: 6)
  - [x] Create `tests/integration/tools/test_nmap_parser.py`
  - [x] Test full pipeline: XML fixture → nmap_parser → valid Findings
  - [x] Verify Finding fields match expected values from fixture

- [x] Task 14: Achieve 100% test coverage (AC: 7)
  - [x] Run `pytest --cov=src/cyberred/tools/parsers/nmap --cov-report=term-missing`
  - [x] Add tests for missing branches (error cases, edge cases)
  - [x] Verify 100% coverage on `src/cyberred/tools/parsers/nmap.py` (28 tests passing)

### Phase 8: Documentation [BLUE]

- [x] Task 15: Update Dev Agent Record
  - [x] Document agent model/version
  - [x] Log any blockers, refactorings, decisions
  - [x] Complete file list with actions

## Dev Notes

> [!TIP]
> **Quick Reference:** Create `nmap_parser()` function in `tools/parsers/nmap.py` that parses nmap XML output using `xml.etree.ElementTree`. Return `List[Finding]` with `type="open_port"`, `type="host_status"`, `type="os_detection"`, and `type="nse_script"`. Register with `OutputProcessor`. Achieve 100% coverage.

### ParserFn Signature (CRITICAL)

The parser MUST follow the exact signature from `parsers/base.py`:

```python
from cyberred.tools.parsers.base import ParserFn

# Standard signature: (stdout, stderr, exit_code, agent_id, target) -> List[Finding]
def nmap_parser(
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
    type="open_port",               # "open_port", "host_status", "os_detection", "nse_script"
    severity="info",                # "critical", "high", "medium", "low", "info"
    target=target,                  # From parser argument, validated IP/URL/hostname
    evidence="22/tcp open ssh OpenSSH 8.9",  # Relevant output snippet
    agent_id=agent_id,              # From parser argument, MUST be valid UUID
    timestamp=datetime.now(timezone.utc).isoformat(),  # ISO 8601
    tool="nmap",
    topic=f"findings:{agent_id}:nmap",  # Redis channel pattern
    signature=""                    # Empty string, agent signs before broadcast
)
```

> [!CAUTION]
> **Validation:** The `Finding` dataclass validates `id`, `agent_id` as UUIDs, `timestamp` as ISO 8601, and `target` as valid IP/URL/hostname. Invalid values will raise `ValueError`.

### Nmap XML Structure Reference

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE nmaprun>
<nmaprun scanner="nmap" args="nmap -sV -oX - 192.168.1.1">
  <host>
    <status state="up"/>
    <address addr="192.168.1.1" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" product="OpenSSH" version="8.9"/>
        <script id="ssh-hostkey" output="key data..."/>
      </port>
      <port protocol="tcp" portid="80">
        <state state="open"/>
        <service name="http" product="Apache" version="2.4.52"/>
      </port>
    </ports>
    <os>
      <osmatch name="Linux 5.x" accuracy="95"/>
    </os>
  </host>
</nmaprun>
```

### Implementation Pattern

```python
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List
import structlog

from cyberred.core.models import Finding

log = structlog.get_logger()


def nmap_parser(
    stdout: str, 
    stderr: str, 
    exit_code: int, 
    agent_id: str, 
    target: str
) -> List[Finding]:
    """Parse nmap XML output to structured findings.
    
    Args:
        stdout: Nmap output (XML format from -oX or - for stdout)
        stderr: Nmap stderr (usually empty)
        exit_code: Process exit code
        agent_id: UUID of agent running the tool
        target: Target IP/hostname
        
    Returns:
        List of Finding objects for open ports, host status, OS, scripts
    """
    findings: List[Finding] = []
    
    # Try XML parsing first
    try:
        root = ET.fromstring(stdout)
    except ET.ParseError:
        log.warning("nmap_xml_parse_failed", target=target)
        return []
    
    # Parse each host
    for host in root.findall('host'):
        # Extract host address (override target if found)
        addr_elem = host.find('address')
        host_addr = addr_elem.get('addr', target) if addr_elem is not None else target
        
        # Host status finding
        status_elem = host.find('status')
        if status_elem is not None:
            state = status_elem.get('state', 'unknown')
            findings.append(_create_finding(
                type="host_status",
                severity="info",
                target=host_addr,
                evidence=f"Host is {state}",
                agent_id=agent_id
            ))
        
        # Port findings
        for port in host.findall('.//port'):
            state_elem = port.find('state')
            if state_elem is None or state_elem.get('state') != 'open':
                continue
                
            portid = port.get('portid', '')
            protocol = port.get('protocol', 'tcp')
            
            service_elem = port.find('service')
            service = service_elem.get('name', '') if service_elem is not None else ''
            product = service_elem.get('product', '') if service_elem is not None else ''
            version = service_elem.get('version', '') if service_elem is not None else ''
            
            evidence = f"{portid}/{protocol} open {service}"
            if product:
                evidence += f" {product}"
            if version:
                evidence += f" {version}"
            
            findings.append(_create_finding(
                type="open_port",
                severity="info",
                target=host_addr,
                evidence=evidence,
                agent_id=agent_id
            ))
    
    log.info("nmap_parsed", target=target, findings_count=len(findings))
    return findings


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
        tool="nmap",
        topic=f"findings:{agent_id}:nmap",
        signature=""
    )
```

### Stub Parser → Production Replacement

The existing `nmap_stub.py` is for testing `OutputProcessor` routing only. This story replaces it with a full implementation:

- **Keep** `nmap_stub.py` for backward compatibility (tests may reference it)
- **Create** `nmap.py` as the production parser
- **Register** `nmap.py` as the default `nmap` parser when parsers are loaded

### Project Structure Notes

Files to create/modify:

```
src/cyberred/tools/parsers/
├── __init__.py          # [MODIFY] Add nmap_parser export
├── base.py              # [UNCHANGED] ParserFn type
├── nmap_stub.py         # [UNCHANGED] Keep for test compatibility  
└── nmap.py              # [NEW] Full nmap XML parser

tests/
├── unit/tools/parsers/
│   └── test_nmap.py     # [NEW] Unit tests for nmap parser
├── integration/tools/
│   └── test_nmap_parser.py  # [NEW] Integration tests
└── fixtures/tool_outputs/
    ├── nmap.txt         # [UNCHANGED] Existing text fixture
    ├── nmap_xml_basic.xml   # [NEW] Basic XML with ports
    ├── nmap_xml_os.xml      # [NEW] XML with OS detection
    └── nmap_xml_scripts.xml # [NEW] XML with NSE scripts
```

### Testing Standards

- **100% coverage** on `parsers/nmap.py` (enforced gate)
- **TDD phases** marked in tasks: [RED] → [GREEN] → [REFACTOR]
- **Unit tests** in `tests/unit/tools/parsers/test_nmap.py`
- **Integration tests** in `tests/integration/tools/test_nmap_parser.py`
- Use `pytest.mark.unit` and `pytest.mark.integration` markers

### Key Learnings from Story 4.5 (Previous Story)

1. **Export verification is critical** — Always test imports work
2. **Use structlog for logging** — NOT `print()` statements
3. **TDD structure works** — Follow [RED]/[GREEN]/[REFACTOR] phases
4. **Verify coverage claims before marking done** — Run `pytest --cov` explicitly
5. **Finding validation is strict** — UUIDs must be valid, timestamps must be ISO 8601
6. **Catch exceptions** — Return empty list on parse errors, don't crash

### Error Handling

| Error | Handling | Notes |
|-------|----------|-------|
| Invalid XML | Return empty list | Log warning, don't raise |
| Missing elements | Skip gracefully | Nmap output varies by scan type |
| Invalid port numbers | Skip port | Log and continue |
| Empty output | Return empty list | Normal for scans with no results |

### References

- **Epic Story:** [epics-stories.md#Story 4.6](file:///root/red/_bmad-output/planning-artifacts/epics-stories.md#L1807)
- **Architecture:** [architecture.md#tools/parsers](file:///root/red/_bmad-output/planning-artifacts/architecture.md#L586)
- **Previous Story 4.5:** [4-5-output-processor-framework.md](file:///root/red/_bmad-output/implementation-artifacts/4-5-output-processor-framework.md)
- **ParserFn Type:** [parsers/base.py](file:///root/red/src/cyberred/tools/parsers/base.py)
- **Finding Model:** [core/models.py](file:///root/red/src/cyberred/core/models.py)
- **Nmap Stub:** [parsers/nmap_stub.py](file:///root/red/src/cyberred/tools/parsers/nmap_stub.py)

## Dev Agent Record

### Agent Model Used

Gemini 2.5 Pro (Code Review Agent)

### Debug Log References

- Coverage Validation: 100% (Passed)
  `pytest --cov=src/cyberred/tools/parsers/nmap --cov-report=term-missing` shows 100% coverage with 28 tests passing.

### Completion Notes List

- **Task 9 Implemented:** Added grepable format auto-detection and parsing with `_is_grepable_format()` and `_parse_grepable()` helper functions.
- **Code Review Fixes Applied:** Fixed all 8 issues from adversarial code review including missing fixtures, coverage gaps, and pytest markers.
- **Test Coverage:** 24 unit tests + 4 integration tests = 28 total tests covering all branches.

### File List

- src/cyberred/tools/parsers/nmap.py [MODIFY] - Added grepable format support
- src/cyberred/tools/parsers/__init__.py [UNCHANGED]
- tests/unit/tools/parsers/test_nmap.py [MODIFY] - Added pytest markers and edge case tests
- tests/integration/tools/test_nmap_parser.py [MODIFY] - Added pytest markers and grepable test
- tests/fixtures/tool_outputs/nmap_xml_basic.xml [UNCHANGED]
- tests/fixtures/tool_outputs/nmap_xml_os.xml [UNCHANGED]
- tests/fixtures/tool_outputs/nmap_xml_scripts.xml [UNCHANGED]
- tests/fixtures/tool_outputs/nmap_grepable.txt [NEW] - Grepable format fixture
- tests/fixtures/tool_outputs/nmap_xml_hostscript_direct.xml [NEW] - Direct host script fixture

