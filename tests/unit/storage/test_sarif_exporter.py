"""Unit tests for SARIF Exporter (Story 13.6).

Tests SARIFExporter class, SARIF v2.1.0 schema compliance,
finding-to-result mapping, severity mapping, and rule generation.

These tests are written FIRST following TDD Red-Green-Refactor cycle.
All tests should FAIL initially (RED phase) since implementation doesn't exist.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_findings() -> tuple[dict, ...]:
    """Create sample findings with various severities for testing."""
    return (
        {
            "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "type": "sqli",
            "severity": "critical",
            "target": "http://192.168.1.100/api/users",
            "evidence": "Parameter 'id' is vulnerable to SQL injection",
            "agent_id": "exploit-agent-001",
            "timestamp": "2024-01-15T11:30:00Z",
            "tool": "sqlmap",
            "topic": "findings:eng001:sqli",
        },
        {
            "id": "a1b2c3d4-58cc-4372-a567-0e02b2c3d480",
            "type": "xss",
            "severity": "high",
            "target": "http://192.168.1.100/search",
            "evidence": "Reflected XSS in search parameter",
            "agent_id": "webapp-agent-001",
            "timestamp": "2024-01-15T12:00:00Z",
            "tool": "nuclei",
            "topic": "findings:eng001:xss",
        },
        {
            "id": "b2c3d4e5-58cc-4372-a567-0e02b2c3d481",
            "type": "missing_headers",
            "severity": "medium",
            "target": "http://192.168.1.100",
            "evidence": "Missing X-Frame-Options header",
            "agent_id": "webapp-agent-001",
            "timestamp": "2024-01-15T12:30:00Z",
            "tool": "nikto",
            "topic": "findings:eng001:headers",
        },
        {
            "id": "c3d4e5f6-58cc-4372-a567-0e02b2c3d482",
            "type": "info_disclosure",
            "severity": "low",
            "target": "http://192.168.1.100",
            "evidence": "Server version disclosed: Apache/2.4.41",
            "agent_id": "recon-agent-001",
            "timestamp": "2024-01-15T10:30:00Z",
            "tool": "nmap",
            "topic": "findings:eng001:info",
        },
        {
            "id": "d4e5f6g7-58cc-4372-a567-0e02b2c3d483",
            "type": "open_port",
            "severity": "info",
            "target": "192.168.1.100",
            "evidence": "Port 22/tcp open ssh",
            "agent_id": "recon-agent-001",
            "timestamp": "2024-01-15T10:00:00Z",
            "tool": "nmap",
            "topic": "findings:eng001:ports",
        },
    )


@pytest.fixture
def sample_report_data(sample_findings):
    """Create sample ReportData for SARIF export testing."""
    from cyberred.storage.report_generator import ReportData, TimelineEvent

    return ReportData(
        engagement_id="test-engagement-001",
        title="Test Penetration Test Report",
        start_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc),
        scope={
            "targets": ["192.168.1.0/24"],
            "exclusions": [],
        },
        findings=sample_findings,
        timeline_events=(
            TimelineEvent(
                timestamp="2024-01-15T10:00:00Z",
                event_type="engagement_start",
                description="Engagement started",
                agent_id="recon-agent-001",
            ),
        ),
        metadata={"operator": "test-operator"},
    )


@pytest.fixture
def empty_report_data():
    """Create ReportData with no findings."""
    from cyberred.storage.report_generator import ReportData

    return ReportData(
        engagement_id="empty-engagement",
        title="Empty Report",
        start_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        end_time=None,
        scope={"targets": [], "exclusions": []},
        findings=(),
        timeline_events=(),
        metadata={},
    )


# =============================================================================
# Task 2: SARIFExporter Class Tests (AC: #2, #3)
# =============================================================================


class TestSARIFExporterInit:
    """Test SARIFExporter initialization."""

    def test_init_loads_default_template(self):
        """Test __init__ with no arguments loads default SARIF template."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        assert exporter.template is not None
        assert exporter.template_path.name == "sarif.jinja2"

    def test_init_loads_custom_template(self, tmp_path: Path):
        """Test __init__ with custom template path loads that template."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        # Create custom template
        custom_template = tmp_path / "custom_sarif.jinja2"
        custom_template.write_text('{"version": "2.1.0", "runs": []}')

        exporter = SARIFExporter(template_path=custom_template)
        assert exporter.template_path == custom_template

    def test_init_raises_file_not_found_for_missing_template(self, tmp_path: Path):
        """Test __init__ raises FileNotFoundError for missing template."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        missing_template = tmp_path / "nonexistent.jinja2"
        with pytest.raises(FileNotFoundError):
            SARIFExporter(template_path=missing_template)


class TestSARIFExporterExport:
    """Test SARIFExporter.export() method."""

    def test_export_returns_json_string(self, sample_report_data):
        """Test export() returns valid JSON string."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data)

        assert isinstance(result, str)
        # Should be valid JSON
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_export_with_as_dict_returns_dict(self, sample_report_data):
        """Test export() with as_dict=True returns dictionary."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        assert isinstance(result, dict)


# =============================================================================
# Task 3: SARIF Schema Compliance Tests (AC: #3, #6)
# =============================================================================


class TestSARIFSchemaCompliance:
    """Test SARIF v2.1.0 schema compliance."""

    def test_output_has_schema_key(self, sample_report_data):
        """Test output has $schema key pointing to SARIF 2.1.0."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        assert "$schema" in result
        assert "sarif-schema-2.1.0" in result["$schema"]

    def test_output_has_version_2_1_0(self, sample_report_data):
        """Test output has version '2.1.0'."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        assert result.get("version") == "2.1.0"

    def test_output_has_runs_array(self, sample_report_data):
        """Test output has 'runs' array with at least one run."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        assert "runs" in result
        assert isinstance(result["runs"], list)
        assert len(result["runs"]) >= 1

    def test_run_has_tool_object(self, sample_report_data):
        """Test run contains 'tool' object with 'driver' info."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        run = result["runs"][0]
        assert "tool" in run
        assert "driver" in run["tool"]

    def test_driver_has_name_cyber_red(self, sample_report_data):
        """Test driver.name is 'cyber-red'."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        driver = result["runs"][0]["tool"]["driver"]
        assert driver.get("name") == "cyber-red"

    def test_driver_has_version(self, sample_report_data):
        """Test driver.version is present."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        driver = result["runs"][0]["tool"]["driver"]
        assert "version" in driver
        assert isinstance(driver["version"], str)

    def test_driver_has_information_uri(self, sample_report_data):
        """Test driver.informationUri points to project URL."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        driver = result["runs"][0]["tool"]["driver"]
        assert "informationUri" in driver

    def test_run_has_results_array(self, sample_report_data):
        """Test run contains 'results' array."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        run = result["runs"][0]
        assert "results" in run
        assert isinstance(run["results"], list)


# =============================================================================
# Task 4: Finding-to-Result Mapping Tests (AC: #4)
# =============================================================================


class TestFindingToResultMapping:
    """Test finding-to-result mapping."""

    def test_each_finding_maps_to_result(self, sample_report_data):
        """Test each Finding maps to one SARIF result."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        results = result["runs"][0]["results"]
        assert len(results) == len(sample_report_data.findings)

    def test_result_has_rule_id(self, sample_report_data):
        """Test result has ruleId derived from finding type."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        sarif_result = result["runs"][0]["results"][0]
        assert "ruleId" in sarif_result
        # First finding type is "sqli"
        assert sarif_result["ruleId"] == "sqli"

    def test_result_has_message_text(self, sample_report_data):
        """Test result has message.text from finding evidence."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        sarif_result = result["runs"][0]["results"][0]
        assert "message" in sarif_result
        assert "text" in sarif_result["message"]

    def test_result_has_level(self, sample_report_data):
        """Test result has level mapped from severity."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        sarif_result = result["runs"][0]["results"][0]
        assert "level" in sarif_result
        # Critical maps to "error"
        assert sarif_result["level"] == "error"

    def test_result_has_locations(self, sample_report_data):
        """Test result has locations array with target."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        sarif_result = result["runs"][0]["results"][0]
        assert "locations" in sarif_result
        assert isinstance(sarif_result["locations"], list)
        assert len(sarif_result["locations"]) > 0

    def test_result_has_partial_fingerprints(self, sample_report_data):
        """Test result has partialFingerprints with finding ID."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        sarif_result = result["runs"][0]["results"][0]
        assert "partialFingerprints" in sarif_result
        assert "finding_id" in sarif_result["partialFingerprints"]

    def test_result_has_properties_with_metadata(self, sample_report_data):
        """Test result has properties with agent_id, tool, timestamp."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        sarif_result = result["runs"][0]["results"][0]
        assert "properties" in sarif_result
        props = sarif_result["properties"]
        assert "agent_id" in props
        assert "tool" in props
        assert "timestamp" in props

    def test_empty_findings_produces_empty_results(self, empty_report_data):
        """Test empty findings produces empty results array."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(empty_report_data, as_dict=True)

        results = result["runs"][0]["results"]
        assert results == []


# =============================================================================
# Task 5: Severity Mapping Tests (AC: #5)
# =============================================================================


class TestSeverityMapping:
    """Test severity-to-level mapping."""

    def test_critical_maps_to_error(self, sample_report_data):
        """Test severity 'critical' maps to SARIF level 'error'."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        # Find the critical finding result
        results = result["runs"][0]["results"]
        critical_result = next(r for r in results if r["ruleId"] == "sqli")
        assert critical_result["level"] == "error"

    def test_high_maps_to_error(self, sample_report_data):
        """Test severity 'high' maps to SARIF level 'error'."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        results = result["runs"][0]["results"]
        high_result = next(r for r in results if r["ruleId"] == "xss")
        assert high_result["level"] == "error"

    def test_medium_maps_to_warning(self, sample_report_data):
        """Test severity 'medium' maps to SARIF level 'warning'."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        results = result["runs"][0]["results"]
        medium_result = next(r for r in results if r["ruleId"] == "missing_headers")
        assert medium_result["level"] == "warning"

    def test_low_maps_to_note(self, sample_report_data):
        """Test severity 'low' maps to SARIF level 'note'."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        results = result["runs"][0]["results"]
        low_result = next(r for r in results if r["ruleId"] == "info_disclosure")
        assert low_result["level"] == "note"

    def test_info_maps_to_note(self, sample_report_data):
        """Test severity 'info' maps to SARIF level 'note'."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        results = result["runs"][0]["results"]
        info_result = next(r for r in results if r["ruleId"] == "open_port")
        assert info_result["level"] == "note"

    def test_unknown_severity_defaults_to_warning(self):
        """Test unknown severity defaults to 'warning'."""
        from cyberred.storage.sarif_exporter import SARIFExporter
        from cyberred.storage.report_generator import ReportData

        # Create report with unknown severity
        report_data = ReportData(
            engagement_id="test",
            title="Test",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=(
                {
                    "id": "test-id",
                    "type": "unknown_type",
                    "severity": "unknown_severity",
                    "target": "192.168.1.1",
                    "evidence": "Test",
                    "agent_id": "agent-001",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "tool": "test",
                    "topic": "test",
                },
            ),
            timeline_events=(),
            metadata={},
        )

        exporter = SARIFExporter()
        result = exporter.export(report_data, as_dict=True)

        sarif_result = result["runs"][0]["results"][0]
        assert sarif_result["level"] == "warning"

    def test_none_severity_defaults_to_warning(self):
        """Test None severity defaults to 'warning'."""
        from cyberred.storage.sarif_exporter import SARIFExporter
        from cyberred.storage.report_generator import ReportData

        # Create report with None severity
        report_data = ReportData(
            engagement_id="test",
            title="Test",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=(
                {
                    "id": "test-id",
                    "type": "test_type",
                    "severity": None,  # Explicitly None
                    "target": "192.168.1.1",
                    "evidence": "Test",
                    "agent_id": "agent-001",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "tool": "test",
                    "topic": "test",
                },
            ),
            timeline_events=(),
            metadata={},
        )

        exporter = SARIFExporter()
        result = exporter.export(report_data, as_dict=True)

        sarif_result = result["runs"][0]["results"][0]
        assert sarif_result["level"] == "warning"

    def test_map_severity_to_level_with_none_directly(self):
        """Test _map_severity_to_level handles None directly."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        # Direct call with None - defensive code path
        result = exporter._map_severity_to_level(None)
        assert result == "warning"

    def test_datetime_timestamp_converted_to_iso_string(self):
        """Test datetime objects in timestamp field are converted to ISO strings."""
        from cyberred.storage.sarif_exporter import SARIFExporter
        from cyberred.storage.report_generator import ReportData

        timestamp_dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        report_data = ReportData(
            engagement_id="test",
            title="Test",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=(
                {
                    "id": "test-id",
                    "type": "test_type",
                    "severity": "high",
                    "target": "192.168.1.1",
                    "evidence": "Test",
                    "agent_id": "agent-001",
                    "timestamp": timestamp_dt,  # datetime object, not string
                    "tool": "test",
                    "topic": "test",
                },
            ),
            timeline_events=(),
            metadata={},
        )

        exporter = SARIFExporter()
        result = exporter.export(report_data, as_dict=True)

        sarif_result = result["runs"][0]["results"][0]
        # Should be ISO format string
        assert sarif_result["properties"]["timestamp"] == "2024-01-15T10:30:00+00:00"

    def test_none_timestamp_becomes_empty_string(self):
        """Test None timestamp becomes empty string."""
        from cyberred.storage.sarif_exporter import SARIFExporter
        from cyberred.storage.report_generator import ReportData

        report_data = ReportData(
            engagement_id="test",
            title="Test",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=(
                {
                    "id": "test-id",
                    "type": "test_type",
                    "severity": "high",
                    "target": "192.168.1.1",
                    "evidence": "Test",
                    "agent_id": "agent-001",
                    "timestamp": None,  # Explicitly None
                    "tool": "test",
                    "topic": "test",
                },
            ),
            timeline_events=(),
            metadata={},
        )

        exporter = SARIFExporter()
        result = exporter.export(report_data, as_dict=True)

        sarif_result = result["runs"][0]["results"][0]
        assert sarif_result["properties"]["timestamp"] == ""


# =============================================================================
# Task 6: Rule Generation Tests (AC: #3)
# =============================================================================


class TestRuleGeneration:
    """Test SARIF rule generation."""

    def test_driver_has_rules_array(self, sample_report_data):
        """Test driver.rules array contains rule definitions."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        driver = result["runs"][0]["tool"]["driver"]
        assert "rules" in driver
        assert isinstance(driver["rules"], list)

    def test_rule_has_required_fields(self, sample_report_data):
        """Test each rule has id, name, shortDescription, defaultConfiguration."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        rules = result["runs"][0]["tool"]["driver"]["rules"]
        for rule in rules:
            assert "id" in rule
            assert "name" in rule
            assert "shortDescription" in rule
            assert "defaultConfiguration" in rule

    def test_rule_ids_match_finding_types(self, sample_report_data):
        """Test rule IDs match finding types."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        result = exporter.export(sample_report_data, as_dict=True)

        rules = result["runs"][0]["tool"]["driver"]["rules"]
        rule_ids = {r["id"] for r in rules}

        finding_types = {f["type"] for f in sample_report_data.findings}
        assert rule_ids == finding_types

    def test_duplicate_finding_types_produce_one_rule(self):
        """Test duplicate finding types produce only one rule."""
        from cyberred.storage.sarif_exporter import SARIFExporter
        from cyberred.storage.report_generator import ReportData

        # Two findings with same type
        report_data = ReportData(
            engagement_id="test",
            title="Test",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=(
                {
                    "id": "id-1",
                    "type": "sqli",
                    "severity": "critical",
                    "target": "192.168.1.1",
                    "evidence": "First sqli",
                    "agent_id": "agent-001",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "tool": "sqlmap",
                    "topic": "test",
                },
                {
                    "id": "id-2",
                    "type": "sqli",
                    "severity": "high",
                    "target": "192.168.1.2",
                    "evidence": "Second sqli",
                    "agent_id": "agent-001",
                    "timestamp": "2024-01-15T11:00:00Z",
                    "tool": "sqlmap",
                    "topic": "test",
                },
            ),
            timeline_events=(),
            metadata={},
        )

        exporter = SARIFExporter()
        result = exporter.export(report_data, as_dict=True)

        rules = result["runs"][0]["tool"]["driver"]["rules"]
        # Only one rule for "sqli"
        assert len(rules) == 1
        assert rules[0]["id"] == "sqli"

    def test_default_configuration_uses_highest_severity(self):
        """Test defaultConfiguration.level uses highest severity for type."""
        from cyberred.storage.sarif_exporter import SARIFExporter
        from cyberred.storage.report_generator import ReportData

        # Two sqli findings: one critical, one high
        report_data = ReportData(
            engagement_id="test",
            title="Test",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=(
                {
                    "id": "id-1",
                    "type": "sqli",
                    "severity": "high",
                    "target": "192.168.1.1",
                    "evidence": "High sqli",
                    "agent_id": "agent-001",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "tool": "sqlmap",
                    "topic": "test",
                },
                {
                    "id": "id-2",
                    "type": "sqli",
                    "severity": "critical",
                    "target": "192.168.1.2",
                    "evidence": "Critical sqli",
                    "agent_id": "agent-001",
                    "timestamp": "2024-01-15T11:00:00Z",
                    "tool": "sqlmap",
                    "topic": "test",
                },
            ),
            timeline_events=(),
            metadata={},
        )

        exporter = SARIFExporter()
        result = exporter.export(report_data, as_dict=True)

        rules = result["runs"][0]["tool"]["driver"]["rules"]
        sqli_rule = rules[0]
        # Should use critical (highest) -> error
        assert sqli_rule["defaultConfiguration"]["level"] == "error"

    def test_unknown_severity_in_rule_generation_keeps_first(self):
        """Test unknown severity in duplicate type keeps original severity."""
        from cyberred.storage.sarif_exporter import SARIFExporter
        from cyberred.storage.report_generator import ReportData

        # Two findings of same type: one known severity, one unknown
        report_data = ReportData(
            engagement_id="test",
            title="Test",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=(
                {
                    "id": "id-1",
                    "type": "sqli",
                    "severity": "high",
                    "target": "192.168.1.1",
                    "evidence": "High sqli",
                    "agent_id": "agent-001",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "tool": "sqlmap",
                    "topic": "test",
                },
                {
                    "id": "id-2",
                    "type": "sqli",
                    "severity": "unknown_severity_xyz",  # Unknown severity
                    "target": "192.168.1.2",
                    "evidence": "Unknown sqli",
                    "agent_id": "agent-001",
                    "timestamp": "2024-01-15T11:00:00Z",
                    "tool": "sqlmap",
                    "topic": "test",
                },
            ),
            timeline_events=(),
            metadata={},
        )

        exporter = SARIFExporter()
        result = exporter.export(report_data, as_dict=True)

        # Should produce one rule with "high" severity (keeps original)
        rules = result["runs"][0]["tool"]["driver"]["rules"]
        assert len(rules) == 1
        sqli_rule = rules[0]
        # Should keep high -> error (unknown ignored)
        assert sqli_rule["defaultConfiguration"]["level"] == "error"

    def test_none_type_becomes_unknown(self):
        """Test None type becomes 'unknown'."""
        from cyberred.storage.sarif_exporter import SARIFExporter
        from cyberred.storage.report_generator import ReportData

        report_data = ReportData(
            engagement_id="test",
            title="Test",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=(
                {
                    "id": "test-id",
                    "type": None,  # Explicitly None
                    "severity": "high",
                    "target": "192.168.1.1",
                    "evidence": "Test",
                    "agent_id": "agent-001",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "tool": "test",
                    "topic": "test",
                },
            ),
            timeline_events=(),
            metadata={},
        )

        exporter = SARIFExporter()
        result = exporter.export(report_data, as_dict=True)

        sarif_result = result["runs"][0]["results"][0]
        assert sarif_result["ruleId"] == "unknown"

        rules = result["runs"][0]["tool"]["driver"]["rules"]
        assert len(rules) == 1
        assert rules[0]["id"] == "unknown"
        assert rules[0]["name"] == "Unknown"

    def test_type_to_name_handles_hyphens(self):
        """Test _type_to_name converts hyphens to spaces."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        
        # Test hyphenated type
        assert exporter._type_to_name("cross-site-scripting") == "Cross Site Scripting"
        # Test underscores
        assert exporter._type_to_name("sql_injection") == "Sql Injection"
        # Test mixed
        assert exporter._type_to_name("path-traversal_attack") == "Path Traversal Attack"
        # Test empty string
        assert exporter._type_to_name("") == "Unknown"

    def test_none_severity_in_rule_generation(self):
        """Test None severity in rule generation defaults to medium."""
        from cyberred.storage.sarif_exporter import SARIFExporter
        from cyberred.storage.report_generator import ReportData

        report_data = ReportData(
            engagement_id="test",
            title="Test",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=(
                {
                    "id": "test-id",
                    "type": "test_vuln",
                    "severity": None,  # None severity
                    "target": "192.168.1.1",
                    "evidence": "Test",
                    "agent_id": "agent-001",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "tool": "test",
                    "topic": "test",
                },
            ),
            timeline_events=(),
            metadata={},
        )

        exporter = SARIFExporter()
        result = exporter.export(report_data, as_dict=True)

        rules = result["runs"][0]["tool"]["driver"]["rules"]
        assert len(rules) == 1
        # None severity defaults to medium -> warning
        assert rules[0]["defaultConfiguration"]["level"] == "warning"


# =============================================================================
# Task 7: Schema Validation Tests (AC: #6)
# =============================================================================


class TestSchemaValidation:
    """Test SARIF schema validation."""

    def test_validate_sarif_with_valid_output(self, sample_report_data):
        """Test validate_sarif returns True for valid SARIF."""
        from cyberred.storage.sarif_exporter import SARIFExporter, validate_sarif

        exporter = SARIFExporter()
        sarif_output = exporter.export(sample_report_data)

        assert validate_sarif(sarif_output) is True

    def test_validate_sarif_with_dict_input(self, sample_report_data):
        """Test validate_sarif accepts dict input."""
        from cyberred.storage.sarif_exporter import SARIFExporter, validate_sarif

        exporter = SARIFExporter()
        sarif_dict = exporter.export(sample_report_data, as_dict=True)

        assert validate_sarif(sarif_dict) is True

    def test_validate_sarif_raises_on_invalid(self):
        """Test validate_sarif raises ValidationError for invalid SARIF."""
        from cyberred.storage.sarif_exporter import validate_sarif
        import jsonschema

        invalid_sarif = {"invalid": "data"}

        with pytest.raises(jsonschema.ValidationError):
            validate_sarif(invalid_sarif)

    def test_validate_sarif_with_special_characters(self):
        """Test validation with special characters in evidence."""
        from cyberred.storage.sarif_exporter import SARIFExporter, validate_sarif
        from cyberred.storage.report_generator import ReportData

        report_data = ReportData(
            engagement_id="test",
            title="Test with special chars: <>&\"'",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=(
                {
                    "id": "test-id",
                    "type": "xss",
                    "severity": "high",
                    "target": "http://192.168.1.1",
                    "evidence": "<script>alert('xss')</script> & \"quotes\"",
                    "agent_id": "agent-001",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "tool": "nuclei",
                    "topic": "test",
                },
            ),
            timeline_events=(),
            metadata={},
        )

        exporter = SARIFExporter()
        sarif_output = exporter.export(report_data)

        assert validate_sarif(sarif_output) is True

    def test_validate_sarif_with_unicode(self):
        """Test validation with Unicode characters."""
        from cyberred.storage.sarif_exporter import SARIFExporter, validate_sarif
        from cyberred.storage.report_generator import ReportData

        report_data = ReportData(
            engagement_id="test",
            title="Test with Unicode: 日本語 中文 한국어",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=(
                {
                    "id": "test-id",
                    "type": "info",
                    "severity": "info",
                    "target": "192.168.1.1",
                    "evidence": "Server banner: 日本語サーバー",
                    "agent_id": "agent-001",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "tool": "nmap",
                    "topic": "test",
                },
            ),
            timeline_events=(),
            metadata={},
        )

        exporter = SARIFExporter()
        sarif_output = exporter.export(report_data)

        assert validate_sarif(sarif_output) is True

    def test_validate_sarif_with_long_strings(self):
        """Test validation with long string values."""
        from cyberred.storage.sarif_exporter import SARIFExporter, validate_sarif
        from cyberred.storage.report_generator import ReportData

        long_evidence = "A" * 10000  # 10KB of text

        report_data = ReportData(
            engagement_id="test",
            title="Test",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=(
                {
                    "id": "test-id",
                    "type": "info",
                    "severity": "info",
                    "target": "192.168.1.1",
                    "evidence": long_evidence,
                    "agent_id": "agent-001",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "tool": "test",
                    "topic": "test",
                },
            ),
            timeline_events=(),
            metadata={},
        )

        exporter = SARIFExporter()
        sarif_output = exporter.export(report_data)

        assert validate_sarif(sarif_output) is True
