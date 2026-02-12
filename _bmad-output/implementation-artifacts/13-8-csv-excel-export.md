# Story 13.8: CSV/Excel Export

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want **CSV and Excel export for spreadsheet analysis**,
So that **I can manipulate findings in familiar tools (FR38)**.

## Acceptance Criteria

1. **Given** engagement has findings
2. **When** I export with format=csv or format=xlsx
3. **Then** one row per finding with columns: severity, type, target, description, timestamp
4. **And** CSV uses UTF-8 encoding with proper escaping
5. **And** Excel includes formatted headers and auto-filter
6. **And** unit tests verify export accuracy

## Tasks / Subtasks

> [!IMPORTANT]
> **RED-GREEN TDD METHODOLOGY REQUIRED**
> Each task MUST follow strict TDD: Write failing tests FIRST (RED), then implement code to pass (GREEN), then refactor.

### Phase 0: Prerequisites

- [ ] Task 0: Verify Story 13.7 Dependencies (PREREQUISITE) <!-- id: prereq -->
  - [ ] Verify `ReportData`, `Finding` dataclasses exported from `storage/__init__.py`
  - [ ] Verify `pandas` and `openpyxl` are added to pyproject.toml
  - [ ] Verify `src/cyberred/storage/` directory structure
  - [ ] Run: `python -c "from cyberred.storage import ReportData"`
  - [ ] Add dependencies if missing: `pandas>=2.0.0` and `openpyxl>=3.1.0`

### Phase 1: RED — Write Failing Tests First

- [ ] Task 1: Create Test File Structure (AC: #6) <!-- id: 0 -->
  - [ ] Create `tests/unit/storage/test_csv_excel_exporter.py`
  - [ ] Import pytest and required testing utilities
  - [ ] Import `ReportData` from appropriate modules
  - [ ] Create fixture for sample findings with various severities, types, and timestamps
  - [ ] Create fixture with edge cases: None values, Unicode characters, newlines, commas
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 2: Write Failing CSVExporter Class Tests (AC: #1, #2, #4) <!-- id: 1 -->
  - [ ] Test `CSVExporter.__init__()` initializes correctly
  - [ ] Test `export(report_data: ReportData) -> str` returns CSV string
  - [ ] Test `export(report_data: ReportData, output_path: Path)` writes to file
  - [ ] Test CSV has header row with correct columns
  - [ ] Test CSV uses UTF-8 encoding
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 3: Write Failing CSV Column Mapping Tests (AC: #3) <!-- id: 2 -->
  - [ ] Test first row is header: `severity,type,target,description,timestamp`
  - [ ] Test each finding produces one row
  - [ ] Test `severity` column contains finding severity (critical, high, medium, low, info)
  - [ ] Test `type` column contains finding type (sqli, xss, rce, etc.)
  - [ ] Test `target` column contains target URL/IP
  - [ ] Test `description` column contains evidence text
  - [ ] Test `timestamp` column contains ISO timestamp
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 4: Write Failing CSV Escaping Tests (AC: #4) <!-- id: 3 -->
  - [ ] Test values containing commas are properly quoted
  - [ ] Test values containing quotes are escaped (doubled)
  - [ ] Test values containing newlines are properly quoted
  - [ ] Test Unicode characters preserved (émojis, CJK, etc.)
  - [ ] Test None values render as empty string
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 5: Write Failing ExcelExporter Class Tests (AC: #1, #2, #5) <!-- id: 4 -->
  - [ ] Test `ExcelExporter.__init__()` initializes correctly
  - [ ] Test `export(report_data: ReportData) -> bytes` returns Excel bytes
  - [ ] Test `export(report_data: ReportData, output_path: Path)` writes to file
  - [ ] Test Excel file can be opened by openpyxl
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 6: Write Failing Excel Formatting Tests (AC: #5) <!-- id: 5 -->
  - [ ] Test Excel has formatted header row (bold)
  - [ ] Test header row has auto-filter enabled
  - [ ] Test column widths are reasonable (not default narrow)
  - [ ] Test worksheet is named "Findings"
  - [ ] Test all data rows present under header
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 7: Write Failing Excel Column Mapping Tests (AC: #3) <!-- id: 6 -->
  - [ ] Test columns match CSV: severity, type, target, description, timestamp
  - [ ] Test each finding produces one row (starting row 2)
  - [ ] Test severity values preserved
  - [ ] Test timestamp values preserved as strings (not Excel dates)
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 8: Write Failing Edge Case Tests (AC: #6) <!-- id: 7 -->
  - [ ] Test empty findings produces valid output with header only
  - [ ] Test findings with None/missing fields handled gracefully
  - [ ] Test findings with datetime objects (not strings)
  - [ ] Test findings with extremely long evidence text
  - [ ] Test 1000+ findings (performance)
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 9: Write Failing Additional Columns Tests (AC: #3) <!-- id: 8 -->
  - [ ] Test optional extended columns: agent_id, tool, topic, attck_id
  - [ ] Test `export(report_data, extended=True)` includes extended columns
  - [ ] Test `export(report_data, extended=False)` uses minimal columns
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

- [ ] Task 10: Write Failing Integration Tests (AC: all) <!-- id: 9 -->
  - [ ] Create `tests/integration/storage/test_csv_excel_exporter_integration.py`
  - [ ] Test full CSV cycle: create ReportData with findings → export → parse back
  - [ ] Test full Excel cycle: create ReportData with findings → export → read with openpyxl
  - [ ] Test CSV round-trip preserves data
  - [ ] Test Excel round-trip preserves data
  - [ ] Test file I/O with real filesystem
  - [ ] Test with realistic engagement data
  - [ ] **Run tests — ALL FAILED (RED confirmed)**

### Phase 2: GREEN — Implement to Pass Tests

- [ ] Task 11: Add Dependencies to pyproject.toml (AC: all) <!-- id: 10 -->
  - [ ] Add `pandas>=2.0.0` to dependencies
  - [ ] Add `openpyxl>=3.1.0` to dependencies
  - [ ] Run `uv sync` to install dependencies
  - [ ] Verify: `python -c "import pandas; import openpyxl; print('OK')"`

- [ ] Task 12: Create CSVExporter Class (AC: #1, #2, #4) <!-- id: 11 -->
  - [ ] Create `src/cyberred/storage/csv_excel_exporter.py`
  - [ ] Implement `CSVExporter` class with `__init__()` method
  - [ ] Implement `export(report_data: ReportData, output_path: Path | None = None, extended: bool = False) -> str`
  - [ ] Use Python `csv` module for proper escaping
  - [ ] Use `io.StringIO` for in-memory string output
  - [ ] **Run Task 2-4 tests — ALL PASSED (GREEN)**

- [ ] Task 13: Implement CSV Column Mapping (AC: #3) <!-- id: 12 -->
  - [ ] Define standard columns: `["severity", "type", "target", "description", "timestamp"]`
  - [ ] Define extended columns: `["severity", "type", "target", "description", "timestamp", "agent_id", "tool", "topic", "attck_id"]`
  - [ ] Implement `_map_finding_to_row(finding: dict, extended: bool) -> list[str]`:
    ```python
    def _map_finding_to_row(self, finding: dict[str, Any], extended: bool = False) -> list[str]:
        """Map finding dict to CSV row values."""
        # Normalize timestamp
        timestamp = finding.get("timestamp", "")
        if hasattr(timestamp, "isoformat"):
            timestamp = timestamp.isoformat()
        elif timestamp is None:
            timestamp = ""
        
        row = [
            finding.get("severity") or "",
            finding.get("type") or "",
            finding.get("target") or "",
            finding.get("evidence") or "",  # 'description' in output
            str(timestamp),
        ]
        
        if extended:
            row.extend([
                finding.get("agent_id") or "",
                finding.get("tool") or "",
                finding.get("topic") or "",
                finding.get("attck_id") or "",
            ])
        
        return row
    ```
  - [ ] **Run Task 3 tests — ALL PASSED (GREEN)**

- [ ] Task 14: Implement CSV UTF-8 and Escaping (AC: #4) <!-- id: 13 -->
  - [ ] Use `csv.writer` with `quoting=csv.QUOTE_MINIMAL` for proper escaping
  - [ ] Ensure UTF-8 encoding by default
  - [ ] Handle None values as empty strings
  - [ ] Handle datetime objects via isoformat conversion
  - [ ] **Run Task 4 tests — ALL PASSED (GREEN)**

- [ ] Task 15: Create ExcelExporter Class (AC: #1, #2, #5) <!-- id: 14 -->
  - [ ] Implement `ExcelExporter` class with `__init__()` method
  - [ ] Implement `export(report_data: ReportData, output_path: Path | None = None, extended: bool = False) -> bytes`
  - [ ] Use `pandas.DataFrame` for data manipulation
  - [ ] Use `openpyxl` engine for Excel output
  - [ ] Use `io.BytesIO` for in-memory bytes output
  - [ ] **Run Task 5 tests — ALL PASSED (GREEN)**

- [ ] Task 16: Implement Excel Formatting (AC: #5) <!-- id: 15 -->
  - [ ] Implement `_format_workbook(workbook: Workbook) -> None`:
    ```python
    def _format_workbook(self, workbook: Workbook) -> None:
        """Apply formatting to Excel workbook."""
        ws = workbook.active
        ws.title = "Findings"
        
        # Header formatting (bold)
        header_font = Font(bold=True)
        for cell in ws[1]:
            cell.font = header_font
        
        # Auto-filter on header row
        ws.auto_filter.ref = ws.dimensions
        
        # Column widths
        column_widths = {
            "A": 12,  # severity
            "B": 15,  # type
            "C": 40,  # target
            "D": 60,  # description
            "E": 25,  # timestamp
            "F": 20,  # agent_id (extended)
            "G": 15,  # tool (extended)
            "H": 20,  # topic (extended)
            "I": 15,  # attck_id (extended)
        }
        for col, width in column_widths.items():
            if col in ws.column_dimensions:
                ws.column_dimensions[col].width = width
    ```
  - [ ] **Run Task 6 tests — ALL PASSED (GREEN)**

- [ ] Task 17: Implement Excel Column Mapping (AC: #3) <!-- id: 16 -->
  - [ ] Reuse column definitions from CSVExporter
  - [ ] Create DataFrame from findings list
  - [ ] Ensure timestamps are strings (not Excel datetime)
  - [ ] **Run Task 7 tests — ALL PASSED (GREEN)**

- [ ] Task 18: Handle Edge Cases (AC: #6) <!-- id: 17 -->
  - [ ] Handle empty findings list (output header only)
  - [ ] Handle None/missing fields with defaults
  - [ ] Handle datetime objects (convert to ISO string)
  - [ ] Handle long text (no truncation)
  - [ ] Test with 1000+ findings for performance
  - [ ] **Run Task 8 tests — ALL PASSED (GREEN)**

- [ ] Task 19: Implement Extended Columns (AC: #3) <!-- id: 18 -->
  - [ ] Add `extended` parameter to export methods
  - [ ] Include additional columns when extended=True
  - [ ] Default to minimal columns (extended=False)
  - [ ] **Run Task 9 tests — ALL PASSED (GREEN)**

### Phase 3: REFACTOR & Export

- [ ] Task 20: Export from Storage Package (AC: all) <!-- id: 19 -->
  - [ ] Export `CSVExporter`, `ExcelExporter` from `storage/__init__.py`
  - [ ] Add to `__all__` list
  - [ ] Verify no circular imports
  - [ ] Run: `python -c "from cyberred.storage import CSVExporter, ExcelExporter"`

- [ ] Task 21: Add Convenience Functions (AC: all) <!-- id: 20 -->
  - [ ] Implement `export_findings_csv(report_data: ReportData, output_path: Path | None = None) -> str`
  - [ ] Implement `export_findings_xlsx(report_data: ReportData, output_path: Path | None = None) -> bytes`
  - [ ] Export convenience functions from `storage/__init__.py`

- [ ] Task 22: Validate 100% Test Coverage <!-- id: 21 -->
  - [ ] Run `pytest tests/unit/storage/test_csv_excel_exporter.py --cov=src/cyberred/storage/csv_excel_exporter --cov-report=term-missing --cov-fail-under=100`
  - [ ] Ensure 100% line coverage on new CSV/Excel exporter code
  - [ ] Add any missing edge case tests

- [ ] Task 23: Run Integration Tests <!-- id: 22 -->
  - [ ] Run `pytest tests/integration/storage/test_csv_excel_exporter_integration.py --cov=src/cyberred/storage/csv_excel_exporter --cov-report=term-missing`
  - [ ] Verify all integration tests pass
  - [ ] Verify minimal/no mocks used (real pandas, real openpyxl, real filesystem)

## Dev Notes

### Architecture Context

This story extends Epic 13's reporting capabilities to add CSV and Excel export for spreadsheet analysis:

Per architecture, Epic 13 components include:
```
├── storage/
│   ├── report_generator.py     # Story 13.4-13.5 ✓
│   ├── sarif_exporter.py       # Story 13.6 ✓
│   ├── stix_exporter.py        # Story 13.7 ✓
│   └── csv_excel_exporter.py   # Story 13.8 (this story)
```

**Why CSV/Excel Export is critical:**
- **FR38**: Multi-format report export
- Operators need to analyze findings in familiar spreadsheet tools (Excel, Google Sheets, LibreOffice Calc)
- CSV enables import into other security tools and SIEMs
- Excel provides formatted output for management reporting

### Export Format Specifications

#### CSV Format

```csv
severity,type,target,description,timestamp
critical,sqli,http://example.com/login,SQL injection in login form,2026-02-12T06:00:00Z
high,xss,http://example.com/search,Reflected XSS in search parameter,2026-02-12T06:15:00Z
```

**CSV Requirements:**
- UTF-8 encoding with BOM for Excel compatibility (optional)
- RFC 4180 compliant
- Comma-separated values
- Double-quote escaping for values containing commas, quotes, or newlines
- Header row required
- One finding per row

#### Excel Format

**Worksheet Structure:**
- Sheet name: "Findings"
- Row 1: Header row (bold, auto-filter enabled)
- Rows 2+: Finding data

**Column Layout (Standard):**

| Column | Header | Width | Content |
|--------|--------|-------|---------|
| A | severity | 12 | critical/high/medium/low/info |
| B | type | 15 | sqli, xss, rce, etc. |
| C | target | 40 | URL or IP address |
| D | description | 60 | Evidence text |
| E | timestamp | 25 | ISO 8601 timestamp |

**Column Layout (Extended):**

| Column | Header | Width | Content |
|--------|--------|-------|---------|
| A-E | (same as standard) | | |
| F | agent_id | 20 | Agent identifier |
| G | tool | 15 | Tool name (nmap, nuclei, etc.) |
| H | topic | 20 | Stigmergic topic |
| I | attck_id | 15 | ATT&CK technique ID |

### Severity to Row Color Mapping (Optional Enhancement)

| Severity | Row Color | Hex |
|----------|-----------|-----|
| critical | Red | #FFCCCC |
| high | Orange | #FFE6CC |
| medium | Yellow | #FFFFCC |
| low | Green | #CCFFCC |
| info | Gray | #E6E6E6 |

*Note: Color formatting is optional and not required for AC compliance.*

### File Locations

| Component | Path |
|-----------|------|
| CSV/Excel Exporter | `src/cyberred/storage/csv_excel_exporter.py` (new) |
| Unit Tests | `tests/unit/storage/test_csv_excel_exporter.py` (new) |
| Integration Tests | `tests/integration/storage/test_csv_excel_exporter_integration.py` (new) |

### Dependencies

**New Dependencies (add to pyproject.toml):**
- `pandas>=2.0.0` — DataFrame for data manipulation
- `openpyxl>=3.1.0` — Excel file creation and formatting

**Python Standard Library:**
- `csv` — CSV file writing with proper escaping
- `io` — StringIO/BytesIO for in-memory output
- `pathlib` — Path handling

**Internal Dependencies:**
- `src/cyberred/storage/report_generator.py` — Story 13.4: `ReportData` dataclass
- `src/cyberred/core/models.py` — `Finding` dataclass
- `src/cyberred/storage/sarif_exporter.py` — Story 13.6: Exporter class pattern

### Design Decisions

1. **Dual Exporter Classes:** Separate `CSVExporter` and `ExcelExporter` classes follow the established pattern from SARIF/STIX exporters.

2. **Pandas for Excel:** Use pandas + openpyxl for Excel generation. Pandas provides clean DataFrame API, openpyxl provides Excel formatting.

3. **Standard vs Extended Columns:** Support both minimal (5 columns) and extended (9 columns) output via `extended` parameter.

4. **String Timestamps:** Keep timestamps as ISO 8601 strings rather than Excel date format to preserve timezone information and milliseconds.

5. **In-Memory and File Output:** Support both returning content (str/bytes) and writing directly to file via optional `output_path` parameter.

6. **Shared Finding Mapping:** Column mapping logic is shared between CSV and Excel exporters to ensure consistency.

### Testing Strategy

**Unit Tests (`tests/unit/storage/test_csv_excel_exporter.py`):**
- Test CSVExporter initialization and export
- Test ExcelExporter initialization and export
- Test column mapping
- Test escaping and encoding
- Test Excel formatting (bold headers, auto-filter)
- Test edge cases (None, Unicode, large data)

**Integration Tests (`tests/integration/storage/test_csv_excel_exporter_integration.py`):**
- Test full CSV export and parse cycle
- Test full Excel export and read cycle
- Test round-trip data preservation
- Test file I/O with real filesystem
- Test with realistic engagement data
- Test performance with 1000+ findings

### Error Handling

| Error Condition | Exception | Handling |
|-----------------|-----------|----------|
| File write error | `IOError` | Raise with path details |
| Invalid finding data | Logged warning | Use default/empty values |
| Missing required fields | Use defaults | Graceful degradation |
| pandas/openpyxl import error | `ImportError` | Clear message about dependencies |

### Previous Story Intelligence

From Story 13.7 (STIX Export):
- Separate exporter class pattern works well
- Handle None values with `or` pattern: `finding.get("severity") or ""`
- Handle datetime objects: check `hasattr(timestamp, "isoformat")`
- Export functions from `storage/__init__.py`
- 100% coverage required on new module

From Story 13.6 (SARIF Export):
- Similar exporter class structure
- `export()` method returns string/dict
- Optional `output_path` parameter for file output
- Jinja2 not needed for CSV/Excel (use pandas/csv module)

### Code Examples

#### CSVExporter Usage

```python
from cyberred.storage import CSVExporter, ReportData
from pathlib import Path

# Create exporter
exporter = CSVExporter()

# Export to string
csv_content = exporter.export(report_data)
print(csv_content)

# Export to file
exporter.export(report_data, output_path=Path("findings.csv"))

# Export with extended columns
csv_extended = exporter.export(report_data, extended=True)
```

#### ExcelExporter Usage

```python
from cyberred.storage import ExcelExporter, ReportData
from pathlib import Path

# Create exporter
exporter = ExcelExporter()

# Export to bytes
xlsx_bytes = exporter.export(report_data)

# Export to file
exporter.export(report_data, output_path=Path("findings.xlsx"))

# Export with extended columns
xlsx_extended = exporter.export(report_data, extended=True)
```

### pandas DataFrame Creation

```python
import pandas as pd
from io import BytesIO

def _create_dataframe(
    self,
    findings: tuple[dict[str, Any], ...],
    extended: bool = False,
) -> pd.DataFrame:
    """Create DataFrame from findings.
    
    Args:
        findings: Tuple of finding dictionaries.
        extended: Whether to include extended columns.
        
    Returns:
        DataFrame with finding data.
    """
    if extended:
        columns = ["severity", "type", "target", "description", "timestamp",
                   "agent_id", "tool", "topic", "attck_id"]
    else:
        columns = ["severity", "type", "target", "description", "timestamp"]
    
    rows = [self._map_finding_to_row(f, extended) for f in findings]
    
    return pd.DataFrame(rows, columns=columns)
```

### openpyxl Formatting

```python
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils.dataframe import dataframe_to_rows

def _apply_formatting(self, workbook: Workbook) -> None:
    """Apply Excel formatting."""
    ws = workbook.active
    ws.title = "Findings"
    
    # Bold header
    for cell in ws[1]:
        cell.font = Font(bold=True)
    
    # Auto-filter
    ws.auto_filter.ref = ws.dimensions
    
    # Column widths
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 15
    ws.column_dimensions["C"].width = 40
    ws.column_dimensions["D"].width = 60
    ws.column_dimensions["E"].width = 25
```

### Project Structure Notes

- Alignment with unified project structure (paths, modules, naming)
- `csv_excel_exporter.py` is new file in `storage/` module following sarif_exporter.py pattern
- New functions exported from `storage/__init__.py`
- No template files needed (unlike SARIF/STIX)

### References

- [Epic 13: Evidence, Reporting & Audit](_bmad-output/planning-artifacts/epics-stories.md#epic-13-evidence-reporting--audit)
- [Story 13.8 Requirements](_bmad-output/planning-artifacts/epics-stories.md) - Lines 4947-4965
- [Story 13.7: STIX Export](_bmad-output/implementation-artifacts/13-7-stix-taxii-export.md) - Previous story pattern
- [Story 13.6: SARIF Export](_bmad-output/implementation-artifacts/13-6-sarif-export.md) - Exporter class pattern
- [pandas Documentation](https://pandas.pydata.org/docs/) - DataFrame and Excel export
- [openpyxl Documentation](https://openpyxl.readthedocs.io/) - Excel formatting
- [RFC 4180: CSV Format](https://tools.ietf.org/html/rfc4180) - CSV standard

## Chat Command Log

<!-- Track key decisions and changes during development -->

## Dev Agent Record

### Agent Model Used

Claude (Anthropic)

### Debug Log References

### Completion Notes List

- All 66 tests pass (50 unit tests + 16 integration tests)
- CSV export with UTF-8 encoding and proper escaping (RFC 4180 compliant)
- Excel export with bold headers, auto-filter, and proper column widths
- Standard columns: severity, type, target, description, timestamp
- Extended columns: + agent_id, tool, topic, attck_id
- Convenience functions: export_findings_csv(), export_findings_xlsx()
- All classes exported from storage/__init__.py

### File List

- `src/cyberred/storage/csv_excel_exporter.py` (new - 364 lines)
- `src/cyberred/storage/__init__.py` (updated - added exports)
- `pyproject.toml` (updated - added pandas>=2.0.0, openpyxl>=3.1.0)
- `tests/unit/storage/test_csv_excel_exporter.py` (existing - 50 tests)
- `tests/integration/storage/test_csv_excel_exporter_integration.py` (existing - 16 tests)
