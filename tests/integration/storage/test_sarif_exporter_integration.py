"""Integration tests for SARIF Exporter (Story 13.6).

Tests full SARIF export cycle with real Jinja2 rendering, JSON parsing,
schema validation, and file I/O. MINIMAL mocks - tests real behavior.

These tests are written FIRST following TDD Red-Green-Refactor cycle.
All tests should FAIL initially (RED phase) since implementation doesn't exist.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


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
def large_report_data():
    """Create ReportData with 100+ findings for performance testing."""
    from cyberred.storage.report_generator import ReportData, TimelineEvent

    findings = []
    finding_types = ["sqli", "xss", "open_port", "info_disclosure", "missing_headers"]
    severities = ["critical", "high", "medium", "low", "info"]

    for i in range(105):
        findings.append({
            "id": f"finding-{i:04d}",
            "type": finding_types[i % len(finding_types)],
            "severity": severities[i % len(severities)],
            "target": f"192.168.1.{i % 256}",
            "evidence": f"Finding evidence #{i}",
            "agent_id": f"agent-{i % 10:02d}",
            "timestamp": f"2024-01-15T{10 + (i // 60):02d}:{i % 60:02d}:00Z",
            "tool": ["nmap", "sqlmap", "nuclei", "nikto"][i % 4],
            "topic": f"findings:eng001:type{i % 5}",
        })

    return ReportData(
        engagement_id="large-engagement",
        title="Large Penetration Test Report",
        start_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2024, 1, 15, 18, 0, 0, tzinfo=timezone.utc),
        scope={"targets": ["192.168.1.0/24"], "exclusions": []},
        findings=tuple(findings),
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


# =============================================================================
# Task 8: Integration Tests (AC: all)
# =============================================================================


class TestSARIFExportFullCycle:
    """Test full SARIF export cycle: create → export → validate."""

    def test_full_export_cycle(self, sample_report_data):
        """Test full cycle: create ReportData → export → validate schema."""
        from cyberred.storage.sarif_exporter import SARIFExporter, validate_sarif

        # Create exporter (uses real Jinja2)
        exporter = SARIFExporter()

        # Export to JSON string (real Jinja2 rendering)
        sarif_json = exporter.export(sample_report_data)

        # Parse JSON (real JSON parsing)
        sarif_dict = json.loads(sarif_json)

        # Validate structure
        assert sarif_dict["version"] == "2.1.0"
        assert len(sarif_dict["runs"]) == 1
        assert len(sarif_dict["runs"][0]["results"]) == 5

        # Validate against schema (real jsonschema validation)
        assert validate_sarif(sarif_json) is True

    def test_exported_sarif_is_valid_json(self, sample_report_data):
        """Test exported SARIF is valid JSON."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        sarif_json = exporter.export(sample_report_data)

        # Should not raise
        parsed = json.loads(sarif_json)
        assert isinstance(parsed, dict)

    def test_sarif_can_be_parsed_and_reexported(self, sample_report_data):
        """Test SARIF can be parsed and re-exported."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        sarif_json = exporter.export(sample_report_data)

        # Parse
        parsed = json.loads(sarif_json)

        # Re-export
        re_exported = json.dumps(parsed, indent=2)

        # Parse again
        re_parsed = json.loads(re_exported)

        # Should be equivalent
        assert re_parsed["version"] == parsed["version"]
        assert len(re_parsed["runs"][0]["results"]) == len(parsed["runs"][0]["results"])


class TestSARIFFileOperations:
    """Test SARIF file save and read operations."""

    def test_file_save_and_read_back(self, sample_report_data, tmp_path: Path):
        """Test SARIF file save and read back."""
        from cyberred.storage.sarif_exporter import SARIFExporter, validate_sarif

        exporter = SARIFExporter()
        sarif_json = exporter.export(sample_report_data)

        # Save to file
        output_path = tmp_path / "report.sarif"
        output_path.write_text(sarif_json, encoding="utf-8")

        # Read back
        read_content = output_path.read_text(encoding="utf-8")

        # Validate read content
        assert validate_sarif(read_content) is True

        # Parse and verify
        parsed = json.loads(read_content)
        assert parsed["version"] == "2.1.0"
        assert len(parsed["runs"][0]["results"]) == 5

    def test_sarif_file_has_correct_encoding(self, sample_report_data, tmp_path: Path):
        """Test SARIF file is saved with UTF-8 encoding."""
        from cyberred.storage.sarif_exporter import SARIFExporter
        from cyberred.storage.report_generator import ReportData, TimelineEvent

        # Create report with Unicode
        unicode_report = ReportData(
            engagement_id="unicode-test",
            title="Test with Unicode: 日本語",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=(
                {
                    "id": "test-id",
                    "type": "info",
                    "severity": "info",
                    "target": "192.168.1.1",
                    "evidence": "Server: 日本語サーバー 中文服务器",
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
        sarif_json = exporter.export(unicode_report)

        # Save with explicit UTF-8
        output_path = tmp_path / "unicode.sarif"
        output_path.write_text(sarif_json, encoding="utf-8")

        # Read back and verify Unicode preserved
        read_content = output_path.read_text(encoding="utf-8")
        assert "日本語" in read_content
        assert "中文服务器" in read_content


class TestSARIFPerformance:
    """Test SARIF export performance with large datasets."""

    def test_export_100_plus_findings(self, large_report_data):
        """Test export with 100+ findings completes in reasonable time."""
        import time
        from cyberred.storage.sarif_exporter import SARIFExporter, validate_sarif

        exporter = SARIFExporter()

        start_time = time.time()
        sarif_json = exporter.export(large_report_data)
        export_time = time.time() - start_time

        # Should complete in under 5 seconds
        assert export_time < 5.0, f"Export took {export_time:.2f}s, expected < 5s"

        # Validate output
        assert validate_sarif(sarif_json) is True

        # Verify all findings exported
        parsed = json.loads(sarif_json)
        assert len(parsed["runs"][0]["results"]) == 105

    def test_export_performance_scales_linearly(self, large_report_data):
        """Test export performance scales reasonably with finding count."""
        import time
        from cyberred.storage.sarif_exporter import SARIFExporter
        from cyberred.storage.report_generator import ReportData

        exporter = SARIFExporter()

        # Measure time for 10 findings
        small_report = ReportData(
            engagement_id="small",
            title="Small",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=large_report_data.findings[:10],
            timeline_events=(),
            metadata={},
        )

        start = time.time()
        exporter.export(small_report)
        time_10 = time.time() - start

        # Measure time for 100 findings
        large_100_report = ReportData(
            engagement_id="large",
            title="Large",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=large_report_data.findings[:100],
            timeline_events=(),
            metadata={},
        )

        start = time.time()
        exporter.export(large_100_report)
        time_100 = time.time() - start

        # 100 findings should take less than 20x the time of 10 findings
        # (allowing for some overhead, but ensuring roughly linear scaling)
        assert time_100 < time_10 * 20, (
            f"Performance doesn't scale: 10 findings={time_10:.3f}s, "
            f"100 findings={time_100:.3f}s"
        )


class TestSARIFSchemaValidationIntegration:
    """Integration tests for SARIF schema validation."""

    def test_validate_against_official_schema(self, sample_report_data):
        """Test output validates against official SARIF 2.1.0 schema."""
        from cyberred.storage.sarif_exporter import SARIFExporter, validate_sarif

        exporter = SARIFExporter()
        sarif_json = exporter.export(sample_report_data)

        # This uses the bundled schema for validation
        result = validate_sarif(sarif_json)
        assert result is True

    def test_validate_multi_finding_report(self, sample_report_data):
        """Test validation with realistic multi-finding report."""
        from cyberred.storage.sarif_exporter import SARIFExporter, validate_sarif

        exporter = SARIFExporter()
        sarif_json = exporter.export(sample_report_data)

        # Parse and verify structure
        parsed = json.loads(sarif_json)

        # Verify all required fields present
        assert "$schema" in parsed
        assert "version" in parsed
        assert "runs" in parsed

        run = parsed["runs"][0]
        assert "tool" in run
        assert "driver" in run["tool"]
        assert "results" in run

        # Validate
        assert validate_sarif(sarif_json) is True

    def test_validate_empty_results(self):
        """Test validation with empty results array."""
        from cyberred.storage.sarif_exporter import SARIFExporter, validate_sarif
        from cyberred.storage.report_generator import ReportData

        empty_report = ReportData(
            engagement_id="empty",
            title="Empty",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=(),
            timeline_events=(),
            metadata={},
        )

        exporter = SARIFExporter()
        sarif_json = exporter.export(empty_report)

        # Empty results should still be valid
        assert validate_sarif(sarif_json) is True

        parsed = json.loads(sarif_json)
        assert parsed["runs"][0]["results"] == []


class TestSARIFExporterModuleExports:
    """Test module exports from storage package."""

    def test_sarif_exporter_exported_from_storage(self):
        """Test SARIFExporter is exported from storage/__init__.py."""
        from cyberred.storage import SARIFExporter

        assert SARIFExporter is not None

    def test_validate_sarif_exported_from_storage(self):
        """Test validate_sarif is exported from storage/__init__.py."""
        from cyberred.storage import validate_sarif

        assert validate_sarif is not None

    def test_exports_in_all_list(self):
        """Test exports are in __all__ list."""
        import cyberred.storage as storage

        assert "SARIFExporter" in storage.__all__
        assert "validate_sarif" in storage.__all__


class TestSARIFDatetimeHandling:
    """Test SARIF export handles datetime objects correctly."""

    def test_datetime_objects_in_findings(self):
        """Test export handles datetime objects in finding timestamp field."""
        from cyberred.storage.sarif_exporter import SARIFExporter, validate_sarif
        from cyberred.storage.report_generator import ReportData

        timestamp_dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        report_data = ReportData(
            engagement_id="datetime-test",
            title="Datetime Test",
            start_time=datetime(2024, 1, 15, tzinfo=timezone.utc),
            end_time=None,
            scope={},
            findings=(
                {
                    "id": "test-id",
                    "type": "sqli",
                    "severity": "high",
                    "target": "http://test.com",
                    "evidence": "Test evidence",
                    "agent_id": "agent-001",
                    "timestamp": timestamp_dt,  # datetime object
                    "tool": "sqlmap",
                    "topic": "test",
                },
            ),
            timeline_events=(),
            metadata={},
        )

        exporter = SARIFExporter()
        # Should not raise TypeError
        sarif_json = exporter.export(report_data)
        
        # Should be valid JSON
        parsed = json.loads(sarif_json)
        
        # Should validate against schema
        assert validate_sarif(sarif_json) is True
        
        # Timestamp should be ISO string
        ts = parsed["runs"][0]["results"][0]["properties"]["timestamp"]
        assert ts == "2024-01-15T10:30:00+00:00"


class TestSARIFResultsContent:
    """Test SARIF results content matches input findings."""

    def test_results_preserve_finding_ids(self, sample_report_data):
        """Test result partialFingerprints preserve finding IDs."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        sarif_dict = exporter.export(sample_report_data, as_dict=True)

        results = sarif_dict["runs"][0]["results"]
        result_finding_ids = {
            r["partialFingerprints"]["finding_id"] for r in results
        }

        input_finding_ids = {f["id"] for f in sample_report_data.findings}

        assert result_finding_ids == input_finding_ids

    def test_results_preserve_targets(self, sample_report_data):
        """Test result locations preserve target URLs."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        sarif_dict = exporter.export(sample_report_data, as_dict=True)

        results = sarif_dict["runs"][0]["results"]
        result_targets = {
            r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
            for r in results
        }

        input_targets = {f["target"] for f in sample_report_data.findings}

        assert result_targets == input_targets

    def test_results_preserve_evidence(self, sample_report_data):
        """Test result message.text contains finding evidence."""
        from cyberred.storage.sarif_exporter import SARIFExporter

        exporter = SARIFExporter()
        sarif_dict = exporter.export(sample_report_data, as_dict=True)

        results = sarif_dict["runs"][0]["results"]

        # Check first result
        first_finding = sample_report_data.findings[0]
        first_result = next(
            r for r in results
            if r["partialFingerprints"]["finding_id"] == first_finding["id"]
        )

        assert first_finding["evidence"] in first_result["message"]["text"]
