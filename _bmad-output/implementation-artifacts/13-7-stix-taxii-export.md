# Story 13.7: STIX/TAXII Export

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **STIX format export for threat intelligence sharing**,
So that **findings can be shared with STIX-compatible systems (FR39)**.

## Acceptance Criteria

1. **Given** engagement has findings
2. **When** I export with format=stix
3. **Then** output conforms to STIX 2.1 specification
4. **And** findings map to STIX objects (indicator, attack-pattern, vulnerability)
5. **And** ATT&CK technique IDs map to STIX attack-pattern references
6. **And** output validates against STIX schema
7. **And** unit tests verify STIX compliance

## Tasks / Subtasks

> [!IMPORTANT]
> **RED-GREEN TDD METHODOLOGY REQUIRED**
> Each task MUST follow strict TDD: Write failing tests FIRST (RED), then implement code to pass (GREEN), then refactor.

### Phase 0: Prerequisites

- [ ] Task 0: Verify Story 13.6 Dependencies (PREREQUISITE) <!-- id: prereq -->
  - [ ] Verify `ReportData`, `Finding` dataclasses exported from `storage/__init__.py`
  - [ ] Verify `stix2>=3.0.0` is installed (already in pyproject.toml)
  - [ ] Verify `src/cyberred/templates/` directory exists
  - [ ] Run: `python -c "from cyberred.storage import ReportData"`
  - [ ] Run: `python -c "import stix2; print(stix2.__version__)"`

### Phase 1: RED — Write Failing Tests First

- [ ] Task 1: Create Test File Structure (AC: #7) <!-- id: 0 -->
  - [ ] Create `tests/unit/storage/test_stix_exporter.py`
  - [ ] Import pytest and required testing utilities
  - [ ] Import `ReportData`, `Finding` from appropriate modules
  - [ ] Create fixture for sample findings with various severities and ATT&CK IDs
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 2: Write Failing STIXExporter Class Tests (AC: #2, #3) <!-- id: 1 -->
  - [ ] Test `STIXExporter.__init__()` initializes correctly
  - [ ] Test `export(report_data: ReportData) -> str` returns JSON string
  - [ ] Test `export(report_data: ReportData, as_dict=True)` returns dict
  - [ ] Test `export(report_data: ReportData, as_bundle=True)` returns stix2.Bundle object
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 3: Write Failing STIX 2.1 Schema Compliance Tests (AC: #3, #6) <!-- id: 2 -->
  - [ ] Test output is valid STIX 2.1 Bundle
  - [ ] Test bundle has `type` = "bundle"
  - [ ] Test bundle has `id` starting with "bundle--"
  - [ ] Test bundle has `objects` array
  - [ ] Test each object has required STIX fields: `type`, `spec_version`, `id`, `created`, `modified`
  - [ ] Test `spec_version` is "2.1"
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 4: Write Failing Finding-to-Indicator Mapping Tests (AC: #4) <!-- id: 3 -->
  - [ ] Test critical/high severity findings map to `indicator` objects
  - [ ] Test indicator has `indicator_types` (e.g., ["malicious-activity", "anomalous-activity"])
  - [ ] Test indicator has `pattern` field with STIX pattern syntax
  - [ ] Test indicator has `pattern_type` = "stix"
  - [ ] Test indicator has `valid_from` timestamp
  - [ ] Test indicator has `name` from finding evidence
  - [ ] Test indicator has `description` with finding details
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 5: Write Failing Finding-to-Vulnerability Mapping Tests (AC: #4) <!-- id: 4 -->
  - [ ] Test vulnerability-type findings (sqli, xss, rce, etc.) map to `vulnerability` objects
  - [ ] Test vulnerability has `name` from finding type
  - [ ] Test vulnerability has `description` from evidence
  - [ ] Test vulnerability has `external_references` with CVE if present
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 6: Write Failing ATT&CK Technique Mapping Tests (AC: #5) <!-- id: 5 -->
  - [ ] Test findings with ATT&CK technique IDs (e.g., T1190) map to `attack-pattern` references
  - [ ] Test attack-pattern has `external_references` with MITRE ATT&CK source
  - [ ] Test attack-pattern has `name` matching technique name
  - [ ] Test relationship objects link indicators/vulnerabilities to attack-patterns
  - [ ] Test relationship has `relationship_type` = "indicates" or "uses"
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 7: Write Failing Identity and Report Object Tests (AC: #3) <!-- id: 6 -->
  - [ ] Test bundle includes `identity` object for Cyber-Red tool
  - [ ] Test identity has `identity_class` = "system"
  - [ ] Test identity has `name` = "cyber-red"
  - [ ] Test bundle includes `report` object summarizing engagement
  - [ ] Test report has `published` timestamp
  - [ ] Test report has `object_refs` linking to all other objects
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 8: Write Failing Edge Case Tests (AC: #6) <!-- id: 7 -->
  - [ ] Test empty findings produces valid bundle with just identity
  - [ ] Test findings with special characters (Unicode, newlines)
  - [ ] Test findings without ATT&CK technique IDs
  - [ ] Test findings with None/missing fields handled gracefully
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 9: Write Failing Integration Tests (AC: all) <!-- id: 8 -->
  - [ ] Create `tests/integration/storage/test_stix_exporter_integration.py`
  - [ ] Test full cycle: create ReportData with findings → export → validate STIX
  - [ ] Test exported STIX is valid JSON
  - [ ] Test STIX bundle can be parsed by stix2 library
  - [ ] Test file save and read back
  - [ ] Test with 100+ findings (performance)
  - [ ] Test round-trip: export → parse → re-export produces equivalent output
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

### Phase 2: GREEN — Implement to Pass Tests

- [ ] Task 10: Create STIXExporter Class (AC: #2, #3) <!-- id: 9 -->
  - [ ] Create `src/cyberred/storage/stix_exporter.py`
  - [ ] Implement `STIXExporter` class with `__init__()` method
  - [ ] Implement `export(report_data: ReportData, as_dict: bool = False, as_bundle: bool = False)`
  - [ ] Use `stix2` library for object creation
  - [ ] **Run Task 2 tests — ALL PASSED (GREEN)**

- [ ] Task 11: Implement Identity Object Creation (AC: #3) <!-- id: 10 -->
  - [ ] Implement `_create_identity() -> stix2.Identity`:
    ```python
    def _create_identity(self) -> stix2.Identity:
        """Create Cyber-Red tool identity object."""
        return stix2.Identity(
            id=f"identity--{self._tool_uuid}",
            name="cyber-red",
            identity_class="system",
            description="Cyber-Red Autonomous Penetration Testing Platform",
        )
    ```
  - [ ] **Run Task 7 tests (identity part) — PASSED (GREEN)**

- [ ] Task 12: Implement Finding-to-Indicator Mapping (AC: #4) <!-- id: 11 -->
  - [ ] Implement `_map_finding_to_indicator(finding: dict) -> stix2.Indicator | None`:
    ```python
    def _map_finding_to_indicator(self, finding: dict) -> stix2.Indicator | None:
        """Map high/critical severity finding to STIX indicator."""
        severity = finding.get("severity", "").lower()
        if severity not in ("critical", "high"):
            return None
        
        target = finding.get("target", "")
        finding_type = finding.get("type", "unknown")
        
        # Create STIX pattern based on finding type
        pattern = self._create_pattern(finding_type, target)
        
        return stix2.Indicator(
            name=f"{finding_type} vulnerability on {target}",
            description=finding.get("evidence", ""),
            indicator_types=["malicious-activity"],
            pattern=pattern,
            pattern_type="stix",
            valid_from=finding.get("timestamp", datetime.utcnow().isoformat()),
            created_by_ref=self._identity.id,
        )
    ```
  - [ ] **Run Task 4 tests — ALL PASSED (GREEN)**

- [ ] Task 13: Implement Finding-to-Vulnerability Mapping (AC: #4) <!-- id: 12 -->
  - [ ] Implement `_map_finding_to_vulnerability(finding: dict) -> stix2.Vulnerability`:
    ```python
    VULN_TYPES = {"sqli", "xss", "rce", "lfi", "rfi", "xxe", "ssrf", "idor", "csrf"}
    
    def _map_finding_to_vulnerability(self, finding: dict) -> stix2.Vulnerability | None:
        """Map vulnerability-type finding to STIX vulnerability."""
        finding_type = finding.get("type", "").lower()
        if finding_type not in self.VULN_TYPES:
            return None
        
        external_refs = []
        # Add CVE reference if present in evidence
        cve_match = re.search(r"CVE-\d{4}-\d+", finding.get("evidence", ""))
        if cve_match:
            external_refs.append(stix2.ExternalReference(
                source_name="cve",
                external_id=cve_match.group(0),
            ))
        
        return stix2.Vulnerability(
            name=finding_type.upper(),
            description=finding.get("evidence", ""),
            external_references=external_refs or None,
            created_by_ref=self._identity.id,
        )
    ```
  - [ ] **Run Task 5 tests — ALL PASSED (GREEN)**

- [ ] Task 14: Implement ATT&CK Technique Mapping (AC: #5) <!-- id: 13 -->
  - [ ] Implement `_create_attack_pattern(technique_id: str) -> stix2.AttackPattern`:
    ```python
    def _create_attack_pattern(self, technique_id: str) -> stix2.AttackPattern:
        """Create STIX attack-pattern from ATT&CK technique ID."""
        return stix2.AttackPattern(
            name=f"ATT&CK Technique {technique_id}",
            external_references=[
                stix2.ExternalReference(
                    source_name="mitre-attack",
                    external_id=technique_id,
                    url=f"https://attack.mitre.org/techniques/{technique_id.replace('.', '/')}",
                )
            ],
            created_by_ref=self._identity.id,
        )
    ```
  - [ ] Implement `_create_relationship(source_ref: str, target_ref: str, rel_type: str) -> stix2.Relationship`
  - [ ] **Run Task 6 tests — ALL PASSED (GREEN)**

- [ ] Task 15: Implement Report Object Creation (AC: #3) <!-- id: 14 -->
  - [ ] Implement `_create_report(object_refs: list[str], report_data: ReportData) -> stix2.Report`:
    ```python
    def _create_report(self, object_refs: list[str], report_data: ReportData) -> stix2.Report:
        """Create STIX report summarizing engagement."""
        return stix2.Report(
            name=f"Cyber-Red Engagement: {report_data.engagement_id}",
            published=datetime.utcnow().isoformat() + "Z",
            object_refs=object_refs,
            created_by_ref=self._identity.id,
            report_types=["threat-report"],
        )
    ```
  - [ ] **Run Task 7 tests — ALL PASSED (GREEN)**

- [ ] Task 16: Implement Bundle Assembly and Export (AC: #3, #6) <!-- id: 15 -->
  - [ ] Implement `_assemble_bundle(objects: list) -> stix2.Bundle`
  - [ ] Implement JSON serialization with proper Unicode handling
  - [ ] Add validation using `stix2.parse()` to verify output
  - [ ] **Run Task 3 tests — ALL PASSED (GREEN)**

- [ ] Task 17: Implement Pattern Generation (AC: #4) <!-- id: 16 -->
  - [ ] Implement `_create_pattern(finding_type: str, target: str) -> str`:
    ```python
    def _create_pattern(self, finding_type: str, target: str) -> str:
        """Create STIX pattern from finding type and target.
        
        Returns STIX pattern syntax, e.g.:
        [url:value = 'http://example.com' AND url:x_vulnerability = 'sqli']
        """
        # Determine pattern type based on target format
        if target.startswith(("http://", "https://")):
            return f"[url:value = '{target}']"
        elif re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", target):
            return f"[ipv4-addr:value = '{target}']"
        else:
            return f"[domain-name:value = '{target}']"
    ```
  - [ ] **Run Task 4 tests — ALL PASSED (GREEN)**

- [ ] Task 18: Handle Edge Cases (AC: #6) <!-- id: 17 -->
  - [ ] Handle None/missing fields gracefully with defaults
  - [ ] Handle datetime objects (convert to ISO string)
  - [ ] Handle Unicode and special characters
  - [ ] Handle empty findings list
  - [ ] **Run Task 8 tests — ALL PASSED (GREEN)**

### Phase 3: REFACTOR & Export

- [ ] Task 19: Export from Storage Package (AC: all) <!-- id: 18 -->
  - [ ] Export `STIXExporter`, `validate_stix` from `storage/__init__.py`
  - [ ] Add to `__all__` list
  - [ ] Verify no circular imports

- [ ] Task 20: Create Jinja2 Template (Optional) <!-- id: 19 -->
  - [ ] Create `src/cyberred/templates/stix.jinja2` (if needed for customization)
  - [ ] Template can wrap stix2 library output for consistent formatting

- [ ] Task 21: Validate 100% Test Coverage <!-- id: 20 -->
  - [ ] Run `pytest tests/unit/storage/test_stix_exporter.py --cov=src/cyberred/storage/stix_exporter --cov-report=term-missing --cov-fail-under=100`
  - [ ] Ensure 100% line coverage on new STIX-related code
  - [ ] Add any missing edge case tests

- [ ] Task 22: Run Integration Tests <!-- id: 21 -->
  - [ ] Run `pytest tests/integration/storage/test_stix_exporter_integration.py --cov=src/cyberred/storage/stix_exporter --cov-report=term-missing`
  - [ ] Verify all integration tests pass
  - [ ] Verify minimal/no mocks used (real stix2 library, real JSON parsing)

## Senior Developer Review (AI)

**Reviewer:** Rovo Dev
**Date:** 2026-02-12
**Outcome:** ✅ APPROVED (after fixes)

### Issues Found and Fixed

| # | Severity | Issue | Fix Applied |
|---|----------|-------|-------------|
| 1 | HIGH | IP address regex accepted invalid IPs like 999.999.999.999 | Added octet validation (0-255 range check) |
| 2 | HIGH | Naive datetime handling could cause STIX validation issues | Added timezone check - naive datetimes now assume UTC |
| 3 | MEDIUM | No logging for skipped invalid ATT&CK IDs (per error handling spec) | Added logger.warning() for invalid technique IDs |
| 4 | MEDIUM | Missing test for IP with port extraction | Added test_ip_with_port_extracts_ip_correctly |
| 5 | MEDIUM | Missing test for sub-technique URL format | Added test_sub_technique_url_format |
| 6 | MEDIUM | Missing test for relationship count validation | Added test_relationship_count_matches_indicators_with_attck |
| 7 | LOW | Module docstring implied TAXII support | Clarified STIX-only with note about future TAXII |
| 8 | LOW | Missing test for invalid IP fallback to domain | Added test_invalid_ip_treated_as_domain |
| 9 | LOW | Missing test for naive datetime handling | Added test_naive_datetime_handled_correctly |

### Test Results After Fixes

- **Unit Tests:** 56 passed ✅
- **Integration Tests:** 9 passed ✅
- **Total:** 65 tests
- **Coverage:** 100% on stix_exporter.py (130 statements, 50 branches)

### Files Modified

- `src/cyberred/storage/stix_exporter.py` - Security fixes and logging
- `tests/unit/storage/test_stix_exporter.py` - 6 new tests added
- `tests/integration/storage/test_stix_exporter_integration.py` - 1 new test added

## Dev Notes

### Architecture Context

This story extends Epic 13's reporting capabilities to add STIX format export for threat intelligence sharing:

Per architecture (lines 868-872):
```
├── templates/                    # Output format templates (FR40)
│   ├── report_md.jinja2          # Story 13.4 ✓
│   ├── report_html.jinja2        # Story 13.5 ✓
│   ├── sarif.jinja2              # Story 13.6 ✓
│   └── stix.jinja2               # Story 13.7 (this story)
```

**Why STIX Export is critical:**
- **FR39**: Enables threat intelligence sharing with STIX-compatible systems
- STIX 2.1 is the OASIS standard for threat intelligence exchange
- Enables integration with threat intelligence platforms (MISP, OpenCTI, etc.)
- ATT&CK technique mapping provides tactical context for findings

### STIX 2.1 Specification

STIX (Structured Threat Information Expression) 2.1 key concepts:

**Core Object Types for Cyber-Red:**
- `identity` - Represents Cyber-Red as the producing system
- `indicator` - Observable patterns (high/critical findings)
- `vulnerability` - Known vulnerability types (sqli, xss, rce, etc.)
- `attack-pattern` - ATT&CK techniques referenced by findings
- `relationship` - Links between objects (indicator→attack-pattern)
- `report` - Summary grouping all engagement findings

**Bundle Structure:**
```json
{
  "type": "bundle",
  "id": "bundle--<uuid>",
  "objects": [
    {
      "type": "identity",
      "spec_version": "2.1",
      "id": "identity--<uuid>",
      "created": "2026-02-12T06:00:00.000Z",
      "modified": "2026-02-12T06:00:00.000Z",
      "name": "cyber-red",
      "identity_class": "system"
    },
    {
      "type": "indicator",
      "spec_version": "2.1",
      "id": "indicator--<uuid>",
      "created": "2026-02-12T06:00:00.000Z",
      "modified": "2026-02-12T06:00:00.000Z",
      "name": "SQL Injection on 192.168.1.100",
      "indicator_types": ["malicious-activity"],
      "pattern": "[ipv4-addr:value = '192.168.1.100']",
      "pattern_type": "stix",
      "valid_from": "2026-02-12T06:00:00.000Z",
      "created_by_ref": "identity--<uuid>"
    },
    {
      "type": "attack-pattern",
      "spec_version": "2.1",
      "id": "attack-pattern--<uuid>",
      "created": "2026-02-12T06:00:00.000Z",
      "modified": "2026-02-12T06:00:00.000Z",
      "name": "ATT&CK Technique T1190",
      "external_references": [
        {
          "source_name": "mitre-attack",
          "external_id": "T1190",
          "url": "https://attack.mitre.org/techniques/T1190"
        }
      ]
    },
    {
      "type": "relationship",
      "spec_version": "2.1",
      "id": "relationship--<uuid>",
      "created": "2026-02-12T06:00:00.000Z",
      "modified": "2026-02-12T06:00:00.000Z",
      "relationship_type": "indicates",
      "source_ref": "indicator--<uuid>",
      "target_ref": "attack-pattern--<uuid>"
    }
  ]
}
```

### Finding Type to STIX Object Mapping

| Finding Severity | Finding Type | STIX Object | Rationale |
|------------------|--------------|-------------|-----------|
| critical/high | any | indicator | High-confidence IoC |
| any | sqli, xss, rce, lfi, rfi, xxe, ssrf, idor, csrf | vulnerability | Known vuln class |
| any | with ATT&CK ID | attack-pattern + relationship | Tactical context |
| info/low/medium | any | (included in report only) | Low-confidence |

### Severity to Indicator Type Mapping

| Cyber-Red Severity | STIX Indicator Type |
|--------------------|---------------------|
| critical | malicious-activity |
| high | malicious-activity |
| medium | anomalous-activity |
| low | benign |
| info | unknown |

### File Locations

| Component | Path |
|-----------|------|
| STIX Exporter | `src/cyberred/storage/stix_exporter.py` (new) |
| STIX Template | `src/cyberred/templates/stix.jinja2` (new, optional) |
| Unit Tests | `tests/unit/storage/test_stix_exporter.py` (new) |
| Integration Tests | `tests/integration/storage/test_stix_exporter_integration.py` (new) |

### Dependencies

**Existing Dependencies (already in pyproject.toml):**
- `stix2>=3.0.0` — For STIX 2.1 object creation and validation

**Python Standard Library:**
- `json` — For JSON serialization
- `re` — For regex pattern matching (CVE extraction, target parsing)
- `uuid` — For UUID generation
- `datetime` — For timestamps

**Internal Dependencies:**
- `src/cyberred/storage/report_generator.py` — Story 13.4: `ReportData` dataclass
- `src/cyberred/core/models.py` — `Finding` dataclass
- `src/cyberred/storage/sarif_exporter.py` — Story 13.6: Pattern for exporter classes

### Design Decisions

1. **Use stix2 Library:** Unlike SARIF (Jinja2 template), use the official `stix2` Python library for STIX object creation. This ensures schema compliance and simplifies validation.

2. **Selective Object Creation:** Not all findings become indicators. Only high/critical severity findings warrant indicator objects. All findings are captured in the summary report.

3. **ATT&CK Integration:** When findings have ATT&CK technique IDs (from RAG enrichment), create attack-pattern objects and relationship links.

4. **Identity Object:** Include a single identity object representing Cyber-Red as the producer. All other objects reference this identity.

5. **Pattern Generation:** Generate STIX patterns based on target type (IP, URL, domain). Patterns are intentionally simple for compatibility.

6. **Bundle Format:** Always export as a STIX Bundle containing all objects. Individual object export can be added later if needed.

### stix2 Library Usage

```python
import stix2

# Create identity
identity = stix2.Identity(
    name="cyber-red",
    identity_class="system",
)

# Create indicator
indicator = stix2.Indicator(
    name="SQL Injection vulnerability",
    indicator_types=["malicious-activity"],
    pattern="[ipv4-addr:value = '192.168.1.100']",
    pattern_type="stix",
    valid_from="2026-02-12T06:00:00.000Z",
    created_by_ref=identity.id,
)

# Create bundle
bundle = stix2.Bundle(objects=[identity, indicator])

# Serialize to JSON
json_output = bundle.serialize(pretty=True)

# Parse back (validation)
parsed = stix2.parse(json_output)
```

### Testing Strategy

**Unit Tests (`tests/unit/storage/test_stix_exporter.py`):**
- Test STIXExporter initialization
- Test finding-to-indicator mapping
- Test finding-to-vulnerability mapping
- Test ATT&CK technique mapping
- Test pattern generation
- Test identity and report creation
- Test edge cases (None values, special characters)

**Integration Tests (`tests/integration/storage/test_stix_exporter_integration.py`):**
- Test full export cycle with real stix2 library
- Test STIX bundle validation via stix2.parse()
- Test with realistic finding data
- Test performance with large finding sets
- Test round-trip serialization

### Error Handling

| Error Condition | Exception | Handling |
|-----------------|-----------|----------|
| Invalid finding data | Logged warning, skip object | Continue processing |
| Missing required fields | Use defaults | Graceful degradation |
| stix2 validation error | `stix2.exceptions.InvalidValueError` | Raise with details |
| JSON serialization error | `json.JSONDecodeError` | Should never happen |
| Invalid ATT&CK ID format | Logged warning, skip attack-pattern | Continue processing |

### Previous Story Intelligence

From Story 13.6 (SARIF Export):
- Separate exporter class pattern works well
- Handle None values with `or` pattern: `finding.get("severity") or "medium"`
- Handle datetime objects: check `hasattr(timestamp, "isoformat")`
- Export functions from `storage/__init__.py`
- 100% coverage required on new module

From mitre_attack.py (existing STIX usage):
- stix2 library already used for ATT&CK ingestion
- Pattern: `stix2.parse()` for validation
- ExternalReference pattern for MITRE ATT&CK links

### Project Structure Notes

- Alignment with unified project structure (paths, modules, naming)
- `stix.jinja2` is optional — stix2 library handles serialization
- `stix_exporter.py` is new file in `storage/` module following sarif_exporter.py pattern
- New functions exported from `storage/__init__.py`

### ATT&CK Technique ID Extraction

Findings may have ATT&CK technique IDs from:
1. RAG enrichment (Story 6.9)
2. Manual tagging in evidence field
3. Tool output parsing (nuclei templates often include ATT&CK IDs)

Regex pattern for extraction:
```python
import re
ATTACK_PATTERN = re.compile(r"T\d{4}(?:\.\d{3})?")
# Matches: T1190, T1059.001, etc.
```

### References

- [Epic 13: Evidence, Reporting & Audit](_bmad-output/planning-artifacts/epics-stories.md#epic-13-evidence-reporting--audit)
- [Story 13.7 Requirements](_bmad-output/planning-artifacts/epics-stories.md) - Lines 4924-4944
- [Architecture: Templates Section](_bmad-output/planning-artifacts/architecture.md) - Lines 868-872
- [Story 13.6: SARIF Export](_bmad-output/implementation-artifacts/13-6-sarif-export.md) - Exporter class pattern
- [STIX 2.1 Specification](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html) - Official spec
- [stix2 Python Library](https://stix2.readthedocs.io/) - Library documentation
- [MITRE ATT&CK STIX Data](https://github.com/mitre/cti) - ATT&CK technique format reference
- [src/cyberred/rag/sources/mitre_attack.py](src/cyberred/rag/sources/mitre_attack.py) - Existing STIX usage

## Chat Command Log

<!-- Track key decisions and changes during development -->

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

### Completion Notes List

### File List

- `src/cyberred/storage/stix_exporter.py` (NEW) - Main implementation (123 lines, 100% coverage)
- `src/cyberred/storage/__init__.py` (MODIFIED) - Added STIXExporter, validate_stix exports
- `tests/unit/storage/test_stix_exporter.py` (NEW) - 50 unit tests
- `tests/integration/storage/test_stix_exporter_integration.py` (NEW) - 9 integration tests

### Completion Notes List

- Implemented STIXExporter class using stix2 library (not Jinja2 template - per design decision)
- All 59 tests pass (50 unit + 9 integration)
- 100% code coverage achieved on stix_exporter.py
- STIX 2.1 compliance verified via stix2.parse() validation
- Supports: Identity, Indicator, Vulnerability, Attack-Pattern, Relationship, Report objects
- ATT&CK technique mapping with MITRE external references
- CVE extraction from evidence text
- Handles edge cases: None fields, Unicode, datetime objects, invalid ATT&CK IDs
- Export formats: JSON string (default), dict, stix2.Bundle object
