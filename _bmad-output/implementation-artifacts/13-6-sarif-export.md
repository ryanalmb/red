# Story 13.6: SARIF Export

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **SARIF format export for CI/CD integration**,
So that **findings integrate with GitHub/Azure DevOps (FR39)**.

## Acceptance Criteria

1. **Given** engagement has findings
2. **When** I export with format=sarif
3. **Then** output conforms to SARIF v2.1.0 schema
4. **And** each finding maps to a SARIF result
5. **And** severity maps to SARIF level (error, warning, note)
6. **And** output validates against sarif-schema-2.1.0.json
7. **And** unit tests verify SARIF compliance

## Tasks / Subtasks

> [!IMPORTANT]
> **RED-GREEN TDD METHODOLOGY REQUIRED**
> Each task MUST follow strict TDD: Write failing tests FIRST (RED), then implement code to pass (GREEN), then refactor.

### Phase 0: Prerequisites

- [x] Task 0: Verify Story 13.4/13.5 Dependencies (PREREQUISITE) <!-- id: prereq -->
  - [x] Verify `ReportData`, `Finding` dataclasses exported from `storage/__init__.py`
  - [x] Verify Jinja2 >= 3.1.0 is installed
  - [x] Verify `src/cyberred/templates/` directory exists
  - [x] Run: `python -c "from cyberred.storage import ReportData"`
  - [x] Run: `python -c "from cyberred.core.models import Finding"`

### Phase 1: RED — Write Failing Tests First

- [x] Task 1: Create Test File Structure (AC: #7) <!-- id: 0 -->
  - [x] Create `tests/unit/storage/test_sarif_exporter.py`
  - [x] Import pytest and required testing utilities
  - [x] Import `ReportData`, `Finding` from appropriate modules
  - [x] Create fixture for sample findings with various severities

- [x] Task 2: Write Failing SARIFExporter Class Tests (AC: #2, #3) <!-- id: 1 -->
  - [x] Test `SARIFExporter.__init__(template_path=None)` loads default template
  - [x] Test `SARIFExporter.__init__(template_path="custom.jinja2")` loads custom template
  - [x] Test `export(report_data: ReportData) -> str` returns JSON string
  - [x] Test `export(report_data: ReportData) -> dict` with `as_dict=True` returns dict
  - [x] Test template not found raises `FileNotFoundError`
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 3: Write Failing SARIF Schema Compliance Tests (AC: #3, #6) <!-- id: 2 -->
  - [x] Test output has required SARIF v2.1.0 top-level keys: `$schema`, `version`, `runs`
  - [x] Test `$schema` points to SARIF 2.1.0 schema URL
  - [x] Test `version` is "2.1.0"
  - [x] Test `runs` is an array with at least one run
  - [x] Test run contains `tool` object with `driver` info
  - [x] Test `driver.name` is "cyber-red"
  - [x] Test `driver.version` matches package version
  - [x] Test `driver.informationUri` points to project URL
  - [x] Test run contains `results` array
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 4: Write Failing Finding-to-Result Mapping Tests (AC: #4) <!-- id: 3 -->
  - [x] Test each Finding maps to one SARIF result
  - [x] Test result has `ruleId` (derived from finding type)
  - [x] Test result has `message.text` (finding description/evidence)
  - [x] Test result has `level` mapped from severity
  - [x] Test result has `locations` array with target information
  - [x] Test result has `partialFingerprints` with finding ID
  - [x] Test result has `properties` with additional metadata (agent_id, tool, timestamp)
  - [x] Test empty findings produces empty results array
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 5: Write Failing Severity Mapping Tests (AC: #5) <!-- id: 4 -->
  - [x] Test severity "critical" maps to SARIF level "error"
  - [x] Test severity "high" maps to SARIF level "error"
  - [x] Test severity "medium" maps to SARIF level "warning"
  - [x] Test severity "low" maps to SARIF level "note"
  - [x] Test severity "info" maps to SARIF level "note"
  - [x] Test unknown severity defaults to "warning"
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 6: Write Failing Rule Definition Tests (AC: #3) <!-- id: 5 -->
  - [x] Test `driver.rules` array contains unique rule definitions
  - [x] Test each rule has `id`, `name`, `shortDescription`, `defaultConfiguration`
  - [x] Test rule IDs match finding types (e.g., "sqli", "xss", "open_port")
  - [x] Test duplicate finding types produce only one rule
  - [x] Test `defaultConfiguration.level` matches highest severity finding of that type
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 7: Write Failing Schema Validation Tests (AC: #6) <!-- id: 6 -->
  - [x] Test output validates against SARIF 2.1.0 JSON schema
  - [x] Use `jsonschema` library for validation
  - [x] Test validation with realistic multi-finding report
  - [x] Test validation with edge cases (special characters, Unicode, long strings)
  - [x] **Run tests — ALL FAILED (RED confirmed)**

- [x] Task 8: Write Failing Integration Tests (AC: all) <!-- id: 7 -->
  - [x] Create `tests/integration/storage/test_sarif_exporter_integration.py`
  - [x] Test full cycle: create ReportData with findings → export → validate schema
  - [x] Test exported SARIF is valid JSON
  - [x] Test SARIF can be parsed and re-exported
  - [x] Test file save and read back
  - [x] Test with 100+ findings (performance)
  - [x] **Run tests — ALL FAILED (RED confirmed)**

### Phase 2: GREEN — Implement to Pass Tests

- [x] Task 9: Create SARIF Template (AC: #3, #6) <!-- id: 8 -->
  - [x] Create `src/cyberred/templates/sarif.jinja2`
  - [x] Template structure following SARIF v2.1.0 schema:
    ```json
    {
      "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
      "version": "2.1.0",
      "runs": [
        {
          "tool": {
            "driver": {
              "name": "cyber-red",
              "version": "{{ version }}",
              "informationUri": "https://github.com/cyber-red/cyber-red",
              "rules": {{ rules | tojson }}
            }
          },
          "results": {{ results | tojson }}
        }
      ]
    }
    ```
  - [x] **Run Task 3 tests — PARTIAL PASS**

- [x] Task 10: Implement SARIFExporter Class (AC: #2, #3) <!-- id: 9 -->
  - [x] Add `SARIFExporter` class to `src/cyberred/storage/sarif_exporter.py` (new file)
  - [x] Implement `__init__(template_path: Path | None = None)`
  - [x] Default template: `sarif.jinja2`
  - [x] Implement `export(report_data: ReportData, as_dict: bool = False) -> str | dict`
  - [x] Implement `_prepare_context(report_data: ReportData) -> dict`
  - [x] **Run Task 2 tests — ALL PASSED (GREEN)**

- [x] Task 11: Implement Finding-to-Result Mapping (AC: #4) <!-- id: 10 -->
  - [ ] Implement `_map_finding_to_result(finding: Finding) -> dict`:
    ```python
    def _map_finding_to_result(self, finding: Finding) -> dict:
        """Map a Cyber-Red Finding to a SARIF result object.
        
        Args:
            finding: The Finding to map.
            
        Returns:
            SARIF result dictionary.
        """
        return {
            "ruleId": finding.type,
            "level": self._map_severity_to_level(finding.severity),
            "message": {
                "text": finding.evidence or f"{finding.type} vulnerability found"
            },
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": finding.target
                        }
                    }
                }
            ],
            "partialFingerprints": {
                "finding_id": finding.id
            },
            "properties": {
                "agent_id": finding.agent_id,
                "tool": finding.tool,
                "timestamp": finding.timestamp,
                "topic": finding.topic
            }
        }
    ```
  - [x] **Run Task 4 tests — ALL PASSED (GREEN)**

- [x] Task 12: Implement Severity Mapping (AC: #5) <!-- id: 11 -->
  - [x] Implement `_map_severity_to_level(severity: str) -> str`:
    ```python
    def _map_severity_to_level(self, severity: str) -> str:
        """Map Cyber-Red severity to SARIF level.
        
        SARIF levels: error, warning, note, none
        Cyber-Red severities: critical, high, medium, low, info
        
        Args:
            severity: Cyber-Red severity string.
            
        Returns:
            SARIF level string.
        """
        mapping = {
            "critical": "error",
            "high": "error",
            "medium": "warning",
            "low": "note",
            "info": "note",
        }
        return mapping.get(severity.lower(), "warning")
    ```
  - [x] **Run Task 5 tests — ALL PASSED (GREEN)**

- [x] Task 13: Implement Rule Generation (AC: #3) <!-- id: 12 -->
  - [ ] Implement `_generate_rules(findings: list[Finding]) -> list[dict]`:
    ```python
    def _generate_rules(self, findings: list[Finding]) -> list[dict]:
        """Generate unique SARIF rule definitions from findings.
        
        Args:
            findings: List of findings.
            
        Returns:
            List of SARIF rule definitions.
        """
        # Group findings by type, track highest severity per type
        type_severities: dict[str, str] = {}
        severity_order = ["info", "low", "medium", "high", "critical"]
        
        for finding in findings:
            current = type_severities.get(finding.type)
            if current is None or severity_order.index(finding.severity.lower()) > severity_order.index(current):
                type_severities[finding.type] = finding.severity.lower()
        
        rules = []
        for rule_type, highest_severity in type_severities.items():
            rules.append({
                "id": rule_type,
                "name": self._type_to_name(rule_type),
                "shortDescription": {
                    "text": f"Detected {rule_type} vulnerability"
                },
                "defaultConfiguration": {
                    "level": self._map_severity_to_level(highest_severity)
                }
            })
        
        return sorted(rules, key=lambda r: r["id"])
    
    def _type_to_name(self, finding_type: str) -> str:
        """Convert finding type to human-readable rule name."""
        return finding_type.replace("_", " ").title()
    ```
  - [x] **Run Task 6 tests — ALL PASSED (GREEN)**

- [x] Task 14: Add Schema Validation (AC: #6) <!-- id: 13 -->
  - [x] Add `jsonschema` to dev dependencies in `pyproject.toml`
  - [x] Implement `validate_sarif(sarif_output: str | dict) -> bool`:
    ```python
    def validate_sarif(sarif_output: str | dict) -> bool:
        """Validate SARIF output against official schema.
        
        Args:
            sarif_output: SARIF JSON string or dict.
            
        Returns:
            True if valid.
            
        Raises:
            jsonschema.ValidationError: If invalid.
        """
        if isinstance(sarif_output, str):
            sarif_output = json.loads(sarif_output)
        
        # Use bundled schema or fetch from cache
        schema = _get_sarif_schema()
        jsonschema.validate(sarif_output, schema)
        return True
    ```
  - [x] Bundle SARIF schema in `src/cyberred/templates/sarif-schema-2.1.0.json`
  - [x] **Run Task 7 tests — ALL PASSED (GREEN)**

### Phase 3: REFACTOR & Export

- [x] Task 15: Export from Storage Package (AC: all) <!-- id: 14 -->
  - [x] Export `SARIFExporter`, `validate_sarif` from `storage/__init__.py`
  - [x] Add to `__all__` list
  - [x] Verify no circular imports

- [x] Task 16: Validate 100% Test Coverage <!-- id: 15 -->
  - [x] Run `pytest tests/unit/storage/test_sarif_exporter.py --cov=src/cyberred/storage/sarif_exporter --cov-report=term-missing --cov-fail-under=100`
  - [x] Ensure 100% line coverage on new SARIF-related code
  - [x] Add any missing edge case tests

- [x] Task 17: Run Integration Tests <!-- id: 16 -->
  - [x] Run `pytest tests/integration/storage/test_sarif_exporter_integration.py --cov=src/cyberred/storage/sarif_exporter --cov-report=term-missing`
  - [x] Verify all integration tests pass
  - [x] Verify minimal/no mocks used (real Jinja2 rendering, real JSON parsing, real schema validation)

## Dev Notes

### Architecture Context

This story extends Epic 13's reporting capabilities to add SARIF format export for CI/CD integration:

Per architecture (lines 868-872):
```
├── templates/                    # Output format templates (FR40)
│   ├── report_md.jinja2          # Story 13.4 ✓
│   ├── report_html.jinja2        # Story 13.5 ✓
│   ├── sarif.jinja2              # Story 13.6 (this story)
│   └── stix.jinja2               # Story 13.7
```

**Why SARIF Export is critical:**
- **FR39**: Enables CI/CD integration with GitHub Security tab and Azure DevOps
- Standard format for static analysis results
- Allows automated security scanning workflows
- Enables findings to appear directly in pull request annotations

### SARIF v2.1.0 Specification

SARIF (Static Analysis Results Interchange Format) is an OASIS standard. Key structure:

```json
{
  "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "cyber-red",
          "version": "2.0.0",
          "informationUri": "https://github.com/cyber-red/cyber-red",
          "rules": [
            {
              "id": "sqli",
              "name": "SQL Injection",
              "shortDescription": { "text": "Detected SQL injection vulnerability" },
              "defaultConfiguration": { "level": "error" }
            }
          ]
        }
      },
      "results": [
        {
          "ruleId": "sqli",
          "level": "error",
          "message": { "text": "Parameter 'id' is vulnerable to SQL injection" },
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": { "uri": "http://192.168.1.100/api/users" }
              }
            }
          ]
        }
      ]
    }
  ]
}
```

### Severity to Level Mapping

| Cyber-Red Severity | SARIF Level | Rationale |
|--------------------|-------------|-----------|
| critical | error | Must be fixed immediately |
| high | error | Security issue requiring attention |
| medium | warning | Should be addressed |
| low | note | For awareness |
| info | note | Informational only |

### File Locations

| Component | Path |
|-----------|------|
| SARIF Exporter | `src/cyberred/storage/sarif_exporter.py` (new) |
| SARIF Template | `src/cyberred/templates/sarif.jinja2` (new) |
| SARIF Schema | `src/cyberred/templates/sarif-schema-2.1.0.json` (new, bundled) |
| Unit Tests | `tests/unit/storage/test_sarif_exporter.py` (new) |
| Integration Tests | `tests/integration/storage/test_sarif_exporter_integration.py` (new) |

### Dependencies

**New Dependencies:**
- `jsonschema>=4.0.0` — For SARIF schema validation (dev dependency for tests)

**Python Standard Library:**
- `json` — For JSON serialization
- `pathlib` — For path handling

**Internal Dependencies:**
- `src/cyberred/storage/report_generator.py` — Story 13.4: `ReportData` dataclass
- `src/cyberred/core/models.py` — `Finding` dataclass
- `src/cyberred/templates/` — Template directory

### Design Decisions

1. **Separate Module:** Create `sarif_exporter.py` as a separate module (not extend `report_generator.py`) because SARIF has fundamentally different structure from Markdown/HTML reports.

2. **Template vs Code:** Use Jinja2 template for overall structure but generate `rules` and `results` arrays in Python for type safety and easier testing.

3. **Schema Bundling:** Bundle SARIF schema locally to enable offline validation and faster tests.

4. **Rule Deduplication:** Generate unique rules from finding types. Track highest severity per type for `defaultConfiguration.level`.

5. **Location Mapping:** Use `physicalLocation.artifactLocation.uri` for targets (URLs/IPs). Could extend to support file:// URIs for file-based findings.

### SARIF GitHub Integration

When SARIF is uploaded to GitHub via Actions:
```yaml
- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v2
  with:
    sarif_file: results.sarif
```

Findings appear in:
- Security tab → Code scanning alerts
- Pull request annotations (if triggered by PR)
- Repository security overview

### Testing Strategy

**Unit Tests (`tests/unit/storage/test_sarif_exporter.py`):**
- Test SARIFExporter initialization
- Test template loading (default + custom)
- Test finding-to-result mapping
- Test severity-to-level mapping
- Test rule generation and deduplication
- Test schema compliance

**Integration Tests (`tests/integration/storage/test_sarif_exporter_integration.py`):**
- Test full export cycle with real Jinja2 rendering
- Test JSON schema validation against official SARIF schema
- Test with realistic finding data
- Test performance with large finding sets

### Error Handling

| Error Condition | Exception | Handling |
|-----------------|-----------|----------|
| Template not found | `FileNotFoundError` | Raise with path |
| Invalid JSON output | `json.JSONDecodeError` | Should never happen with Jinja2 |
| Schema validation failure | `jsonschema.ValidationError` | Raise with details |
| Missing required finding fields | `KeyError` / `AttributeError` | Validate input, provide defaults |

### Previous Story Intelligence

From Story 13.5 (HTML Report with Screenshots):
- Jinja2 templates work well for structured output
- `autoescape=False` needed for JSON output
- Separate exporter class pattern works well
- Keep template simple, do complex logic in Python
- Export functions from `storage/__init__.py`

From Story 13.4 (Markdown Report Generation):
- `ReportData` dataclass contains findings list
- `TimelineEvent` for audit trail (not needed for SARIF)
- Template context preparation is reusable pattern

### Project Structure Notes

- Alignment with unified project structure (paths, modules, naming)
- `sarif.jinja2` goes in existing `templates/` directory
- `sarif_exporter.py` is new file in `storage/` module
- Schema file bundled with templates for offline validation
- New functions exported from `storage/__init__.py`

### References

- [Epic 13: Evidence, Reporting & Audit](_bmad-output/planning-artifacts/epics-stories.md#epic-13-evidence-reporting--audit)
- [Story 13.6 Requirements](_bmad-output/planning-artifacts/epics-stories.md) - Lines 4901-4921
- [Architecture: Templates Section](_bmad-output/planning-artifacts/architecture.md) - Lines 868-872
- [Story 13.5: HTML Report with Screenshots](_bmad-output/implementation-artifacts/13-5-html-report-with-screenshots.md) - Previous story patterns
- [Story 13.4: Markdown Report Generation](_bmad-output/implementation-artifacts/13-4-markdown-report-generation.md) - ReportData, Finding structures
- [SARIF v2.1.0 Specification](https://docs.oasis-open.org/sarif/sarif/v2.1.0/) - Official schema
- [GitHub SARIF Support](https://docs.github.com/en/code-security/code-scanning/integrating-with-code-scanning/sarif-support-for-code-scanning) - Integration docs

## Chat Command Log

<!-- Track key decisions and changes during development -->

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

N/A

### Completion Notes List

- All 55 tests pass (39 unit + 16 integration)
- 100% code coverage on sarif_exporter.py module
- SARIF v2.1.0 schema compliant output
- Unicode properly handled (ensure_ascii=False)
- Severity mapping: critical/high→error, medium→warning, low/info→note
- Rule deduplication with highest severity tracking
- jsonschema>=4.0.0 added to dev/test dependencies
- SARIFExporter and validate_sarif exported from storage package

### File List

- `src/cyberred/storage/sarif_exporter.py` (NEW) - Main implementation
- `src/cyberred/templates/sarif.jinja2` (NEW) - SARIF Jinja2 template
- `src/cyberred/templates/sarif-schema-2.1.0.json` (NEW) - Bundled SARIF schema
- `src/cyberred/storage/__init__.py` (MODIFIED) - Added exports
- `tests/unit/storage/test_sarif_exporter.py` (EXISTS) - Unit tests
- `tests/integration/storage/test_sarif_exporter_integration.py` (EXISTS) - Integration tests
- `pyproject.toml` (MODIFIED) - Added jsonschema dependency

## Senior Developer Review (AI)

**Review Date:** 2026-02-12
**Reviewer:** Rovo Dev (Adversarial Code Review)
**Status:** ✅ APPROVED (after fixes)

### Issues Found and Fixed

| # | Severity | Issue | Fix Applied |
|---|----------|-------|-------------|
| 1 | HIGH | `_generate_rules` crashed with `AttributeError` when `severity` is `None` | Changed `finding.get("severity", "medium").lower()` to `(finding.get("severity") or "medium").lower()` |
| 2 | HIGH | `_map_finding_to_result` failed with `TypeError` when `timestamp` is a `datetime` object | Added datetime detection using `hasattr(timestamp, "isoformat")` and conversion |
| 3 | HIGH | `_map_severity_to_level` crashed when called with `None` severity | Added explicit `if severity is None: return "warning"` guard |
| 4 | HIGH | Missing tests for `None` severity values | Added `test_none_severity_defaults_to_warning`, `test_map_severity_to_level_with_none_directly`, `test_none_severity_in_rule_generation` |
| 5 | HIGH | Missing tests for datetime objects in finding fields | Added `test_datetime_timestamp_converted_to_iso_string`, `test_none_timestamp_becomes_empty_string`, integration test `test_datetime_objects_in_findings` |
| 6 | HIGH | Missing tests for `_type_to_name` edge cases | Added `test_none_type_becomes_unknown`, `test_type_to_name_handles_hyphens` |
| 7 | MEDIUM | Inconsistent `None` handling via `.get()` with defaults | Changed all `.get(key, default)` to `finding.get(key) or default` pattern |
| 8 | MEDIUM | `_type_to_name` didn't convert hyphens to spaces | Added `.replace("-", " ")` to convert hyphens like underscores |

### Test Results After Fix

- **Total Tests:** 63 (46 unit + 17 integration)
- **Passed:** 63
- **Coverage:** 100% on `sarif_exporter.py`

### Files Modified During Review

- `src/cyberred/storage/sarif_exporter.py` - Fixed edge case handling for None values and datetime objects
- `tests/unit/storage/test_sarif_exporter.py` - Added 8 new edge case tests
- `tests/integration/storage/test_sarif_exporter_integration.py` - Added datetime handling integration test

