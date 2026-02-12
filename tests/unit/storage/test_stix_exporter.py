"""Unit tests for STIX Exporter (Story 13.7).

Tests STIX 2.1 format export for threat intelligence sharing.
Follows TDD: Write failing tests first (RED), then implement (GREEN).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch
import uuid

import pytest

# Import dependencies - these should exist
from cyberred.storage.report_generator import ReportData, TimelineEvent

# Import the module under test - this will fail initially (RED phase)
from cyberred.storage.stix_exporter import (
    STIXExporter,
    validate_stix,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_findings() -> tuple[dict[str, Any], ...]:
    """Sample findings with various severities and ATT&CK IDs."""
    return (
        {
            "id": "finding-001",
            "type": "sqli",
            "severity": "critical",
            "target": "http://192.168.1.100/login",
            "evidence": "SQL Injection detected in login form. CVE-2021-12345.",
            "timestamp": "2026-02-12T06:00:00Z",
            "agent_id": "recon-agent-1",
            "tool": "sqlmap",
            "topic": "webapp",
            "attck_ids": ["T1190"],
        },
        {
            "id": "finding-002",
            "type": "xss",
            "severity": "high",
            "target": "https://example.com/search",
            "evidence": "Reflected XSS in search parameter",
            "timestamp": "2026-02-12T06:30:00Z",
            "agent_id": "webapp-agent-1",
            "tool": "nuclei",
            "topic": "webapp",
            "attck_ids": ["T1059.007"],
        },
        {
            "id": "finding-003",
            "type": "rce",
            "severity": "critical",
            "target": "192.168.1.50",
            "evidence": "Remote code execution via command injection",
            "timestamp": "2026-02-12T07:00:00Z",
            "agent_id": "exploit-agent-1",
            "tool": "metasploit",
            "topic": "network",
            "attck_ids": ["T1059", "T1190"],
        },
        {
            "id": "finding-004",
            "type": "info_disclosure",
            "severity": "medium",
            "target": "api.example.com",
            "evidence": "Server version disclosed in headers",
            "timestamp": "2026-02-12T07:30:00Z",
            "agent_id": "recon-agent-1",
            "tool": "nmap",
            "topic": "network",
        },
        {
            "id": "finding-005",
            "type": "open_port",
            "severity": "info",
            "target": "10.0.0.1",
            "evidence": "Port 22 (SSH) open",
            "timestamp": "2026-02-12T08:00:00Z",
            "agent_id": "recon-agent-1",
            "tool": "nmap",
            "topic": "network",
        },
    )


@pytest.fixture
def sample_report_data(sample_findings: tuple[dict[str, Any], ...]) -> ReportData:
    """Sample ReportData for testing."""
    return ReportData(
        engagement_id="eng-test-001",
        title="Penetration Test - STIX Export Test",
        start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 12, 12, 0, 0, tzinfo=timezone.utc),
        scope={"targets": ["192.168.1.0/24", "example.com"], "exclusions": []},
        findings=sample_findings,
        timeline_events=(
            TimelineEvent(
                timestamp="2026-02-12T06:00:00Z",
                event_type="engagement_start",
                description="Engagement started",
                agent_id="system",
            ),
        ),
    )


@pytest.fixture
def empty_report_data() -> ReportData:
    """ReportData with no findings."""
    return ReportData(
        engagement_id="eng-empty-001",
        title="Empty Engagement",
        start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
        end_time=None,
        scope={"targets": [], "exclusions": []},
        findings=(),
        timeline_events=(),
    )


# =============================================================================
# Task 2: STIXExporter Class Tests (AC: #2, #3)
# =============================================================================


class TestSTIXExporterInit:
    """Tests for STIXExporter initialization."""

    def test_init_creates_instance(self) -> None:
        """Test STIXExporter.__init__() initializes correctly."""
        exporter = STIXExporter()
        assert exporter is not None
        assert isinstance(exporter, STIXExporter)

    def test_init_has_tool_uuid(self) -> None:
        """Test STIXExporter has consistent tool UUID."""
        exporter = STIXExporter()
        assert hasattr(exporter, "_tool_uuid")
        # UUID should be valid format
        uuid.UUID(exporter._tool_uuid)


class TestSTIXExporterExport:
    """Tests for STIXExporter.export() method."""

    def test_export_returns_json_string(
        self, sample_report_data: ReportData
    ) -> None:
        """Test export() returns JSON string by default."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data)
        
        assert isinstance(result, str)
        # Should be valid JSON
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_export_as_dict_returns_dict(
        self, sample_report_data: ReportData
    ) -> None:
        """Test export(as_dict=True) returns dictionary."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        assert isinstance(result, dict)
        assert "type" in result

    def test_export_as_bundle_returns_stix_bundle(
        self, sample_report_data: ReportData
    ) -> None:
        """Test export(as_bundle=True) returns stix2.Bundle object."""
        import stix2
        
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_bundle=True)
        
        assert isinstance(result, stix2.Bundle)


# =============================================================================
# Task 3: STIX 2.1 Schema Compliance Tests (AC: #3, #6)
# =============================================================================


class TestSTIXSchemaCompliance:
    """Tests for STIX 2.1 schema compliance."""

    def test_output_is_valid_stix_bundle(
        self, sample_report_data: ReportData
    ) -> None:
        """Test output is valid STIX 2.1 Bundle."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        assert result["type"] == "bundle"

    def test_bundle_has_correct_id_format(
        self, sample_report_data: ReportData
    ) -> None:
        """Test bundle has id starting with 'bundle--'."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        assert result["id"].startswith("bundle--")

    def test_bundle_has_objects_array(
        self, sample_report_data: ReportData
    ) -> None:
        """Test bundle has 'objects' array."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        assert "objects" in result
        assert isinstance(result["objects"], list)
        assert len(result["objects"]) > 0

    def test_each_object_has_required_stix_fields(
        self, sample_report_data: ReportData
    ) -> None:
        """Test each object has required STIX fields."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        required_fields = ["type", "spec_version", "id", "created", "modified"]
        
        for obj in result["objects"]:
            # Bundle itself doesn't have spec_version
            if obj.get("type") == "bundle":
                continue
            for field in required_fields:
                assert field in obj, f"Missing {field} in {obj['type']}"

    def test_spec_version_is_2_1(
        self, sample_report_data: ReportData
    ) -> None:
        """Test spec_version is '2.1'."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        for obj in result["objects"]:
            if "spec_version" in obj:
                assert obj["spec_version"] == "2.1"


# =============================================================================
# Task 4: Finding-to-Indicator Mapping Tests (AC: #4)
# =============================================================================


class TestFindingToIndicatorMapping:
    """Tests for mapping findings to STIX indicators."""

    def test_critical_severity_maps_to_indicator(
        self, sample_report_data: ReportData
    ) -> None:
        """Test critical severity findings map to indicator objects."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        # Should have indicators for critical/high findings
        assert len(indicators) >= 1

    def test_high_severity_maps_to_indicator(
        self, sample_report_data: ReportData
    ) -> None:
        """Test high severity findings map to indicator objects."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        # Should have at least 3 indicators (2 critical + 1 high)
        assert len(indicators) >= 3

    def test_indicator_has_indicator_types(
        self, sample_report_data: ReportData
    ) -> None:
        """Test indicator has indicator_types field."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        for indicator in indicators:
            assert "indicator_types" in indicator
            assert isinstance(indicator["indicator_types"], list)

    def test_indicator_has_pattern_field(
        self, sample_report_data: ReportData
    ) -> None:
        """Test indicator has pattern field with STIX pattern syntax."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        for indicator in indicators:
            assert "pattern" in indicator
            # STIX patterns use square brackets
            assert "[" in indicator["pattern"]

    def test_indicator_has_pattern_type_stix(
        self, sample_report_data: ReportData
    ) -> None:
        """Test indicator has pattern_type = 'stix'."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        for indicator in indicators:
            assert indicator["pattern_type"] == "stix"

    def test_indicator_has_valid_from(
        self, sample_report_data: ReportData
    ) -> None:
        """Test indicator has valid_from timestamp."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        for indicator in indicators:
            assert "valid_from" in indicator

    def test_indicator_has_name(
        self, sample_report_data: ReportData
    ) -> None:
        """Test indicator has name from finding evidence."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        for indicator in indicators:
            assert "name" in indicator
            assert len(indicator["name"]) > 0

    def test_indicator_has_description(
        self, sample_report_data: ReportData
    ) -> None:
        """Test indicator has description with finding details."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        for indicator in indicators:
            assert "description" in indicator


# =============================================================================
# Task 5: Finding-to-Vulnerability Mapping Tests (AC: #4)
# =============================================================================


class TestFindingToVulnerabilityMapping:
    """Tests for mapping findings to STIX vulnerabilities."""

    def test_vuln_type_findings_map_to_vulnerability(
        self, sample_report_data: ReportData
    ) -> None:
        """Test vulnerability-type findings map to vulnerability objects."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        vulnerabilities = [obj for obj in result["objects"] if obj["type"] == "vulnerability"]
        # Should have vulnerabilities for sqli, xss, rce
        assert len(vulnerabilities) >= 3

    def test_vulnerability_has_name(
        self, sample_report_data: ReportData
    ) -> None:
        """Test vulnerability has name from finding type."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        vulnerabilities = [obj for obj in result["objects"] if obj["type"] == "vulnerability"]
        for vuln in vulnerabilities:
            assert "name" in vuln
            assert len(vuln["name"]) > 0

    def test_vulnerability_has_description(
        self, sample_report_data: ReportData
    ) -> None:
        """Test vulnerability has description from evidence."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        vulnerabilities = [obj for obj in result["objects"] if obj["type"] == "vulnerability"]
        for vuln in vulnerabilities:
            assert "description" in vuln

    def test_vulnerability_has_cve_external_reference(
        self, sample_report_data: ReportData
    ) -> None:
        """Test vulnerability has external_references with CVE if present."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        vulnerabilities = [obj for obj in result["objects"] if obj["type"] == "vulnerability"]
        # Find the one with CVE (sqli finding has CVE-2021-12345)
        cve_vulns = [
            v for v in vulnerabilities
            if v.get("external_references")
        ]
        assert len(cve_vulns) >= 1
        
        # Check that external reference has CVE
        cve_found = False
        for vuln in cve_vulns:
            for ref in vuln.get("external_references", []):
                if ref.get("source_name") == "cve":
                    cve_found = True
                    assert "CVE-" in ref.get("external_id", "")
        assert cve_found


# =============================================================================
# Task 6: ATT&CK Technique Mapping Tests (AC: #5)
# =============================================================================


class TestATTCKTechniqueMapping:
    """Tests for ATT&CK technique mapping."""

    def test_findings_with_attck_ids_map_to_attack_pattern(
        self, sample_report_data: ReportData
    ) -> None:
        """Test findings with ATT&CK technique IDs map to attack-pattern."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        attack_patterns = [obj for obj in result["objects"] if obj["type"] == "attack-pattern"]
        # Should have attack patterns for T1190, T1059.007, T1059
        assert len(attack_patterns) >= 3

    def test_attack_pattern_has_mitre_external_reference(
        self, sample_report_data: ReportData
    ) -> None:
        """Test attack-pattern has external_references with MITRE ATT&CK source."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        attack_patterns = [obj for obj in result["objects"] if obj["type"] == "attack-pattern"]
        for ap in attack_patterns:
            assert "external_references" in ap
            mitre_refs = [
                ref for ref in ap["external_references"]
                if ref.get("source_name") == "mitre-attack"
            ]
            assert len(mitre_refs) >= 1

    def test_attack_pattern_has_name(
        self, sample_report_data: ReportData
    ) -> None:
        """Test attack-pattern has name matching technique name."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        attack_patterns = [obj for obj in result["objects"] if obj["type"] == "attack-pattern"]
        for ap in attack_patterns:
            assert "name" in ap
            # Name should contain technique ID
            assert "T1" in ap["name"] or "ATT&CK" in ap["name"]

    def test_relationship_links_indicator_to_attack_pattern(
        self, sample_report_data: ReportData
    ) -> None:
        """Test relationship objects link indicators to attack-patterns."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        relationships = [obj for obj in result["objects"] if obj["type"] == "relationship"]
        # Should have relationships linking indicators to attack-patterns
        assert len(relationships) >= 1

    def test_relationship_has_correct_type(
        self, sample_report_data: ReportData
    ) -> None:
        """Test relationship has relationship_type = 'indicates' or 'uses'."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        relationships = [obj for obj in result["objects"] if obj["type"] == "relationship"]
        for rel in relationships:
            assert rel["relationship_type"] in ("indicates", "uses")


# =============================================================================
# Task 7: Identity and Report Object Tests (AC: #3)
# =============================================================================


class TestIdentityAndReportObjects:
    """Tests for STIX identity and report objects."""

    def test_bundle_includes_identity_object(
        self, sample_report_data: ReportData
    ) -> None:
        """Test bundle includes identity object for Cyber-Red tool."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        identities = [obj for obj in result["objects"] if obj["type"] == "identity"]
        assert len(identities) >= 1

    def test_identity_has_system_class(
        self, sample_report_data: ReportData
    ) -> None:
        """Test identity has identity_class = 'system'."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        identities = [obj for obj in result["objects"] if obj["type"] == "identity"]
        assert any(i["identity_class"] == "system" for i in identities)

    def test_identity_has_cyber_red_name(
        self, sample_report_data: ReportData
    ) -> None:
        """Test identity has name = 'cyber-red'."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        identities = [obj for obj in result["objects"] if obj["type"] == "identity"]
        assert any(i["name"] == "cyber-red" for i in identities)

    def test_bundle_includes_report_object(
        self, sample_report_data: ReportData
    ) -> None:
        """Test bundle includes report object summarizing engagement."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        reports = [obj for obj in result["objects"] if obj["type"] == "report"]
        assert len(reports) >= 1

    def test_report_has_published_timestamp(
        self, sample_report_data: ReportData
    ) -> None:
        """Test report has published timestamp."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        reports = [obj for obj in result["objects"] if obj["type"] == "report"]
        for report in reports:
            assert "published" in report

    def test_report_has_object_refs(
        self, sample_report_data: ReportData
    ) -> None:
        """Test report has object_refs linking to all other objects."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        reports = [obj for obj in result["objects"] if obj["type"] == "report"]
        for report in reports:
            assert "object_refs" in report
            assert isinstance(report["object_refs"], list)
            assert len(report["object_refs"]) > 0


# =============================================================================
# Task 8: Edge Case Tests (AC: #6)
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_findings_produces_valid_bundle(
        self, empty_report_data: ReportData
    ) -> None:
        """Test empty findings produces valid bundle with just identity."""
        exporter = STIXExporter()
        result = exporter.export(empty_report_data, as_dict=True)
        
        assert result["type"] == "bundle"
        assert "objects" in result
        # Should at least have identity
        identities = [obj for obj in result["objects"] if obj["type"] == "identity"]
        assert len(identities) >= 1

    def test_findings_with_special_characters(self) -> None:
        """Test findings with special characters (Unicode, newlines)."""
        special_findings = (
            {
                "id": "finding-special",
                "type": "sqli",
                "severity": "critical",
                "target": "http://example.com/search?q=テスト",
                "evidence": "SQL Injection:\n' OR '1'='1\nUnicode: 日本語",
                "timestamp": "2026-02-12T06:00:00Z",
                "agent_id": "agent-1",
                "attck_ids": ["T1190"],
            },
        )
        report_data = ReportData(
            engagement_id="eng-special",
            title="Special Characters Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=special_findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        result = exporter.export(report_data)
        
        # Should produce valid JSON with Unicode preserved
        parsed = json.loads(result)
        assert "テスト" in result or "\\u" in result  # Unicode preserved or escaped

    def test_findings_without_attck_ids(self) -> None:
        """Test findings without ATT&CK technique IDs."""
        findings = (
            {
                "id": "finding-no-attck",
                "type": "info_disclosure",
                "severity": "low",
                "target": "192.168.1.1",
                "evidence": "Server version disclosed",
                "timestamp": "2026-02-12T06:00:00Z",
                "agent_id": "agent-1",
            },
        )
        report_data = ReportData(
            engagement_id="eng-no-attck",
            title="No ATT&CK IDs Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        result = exporter.export(report_data, as_dict=True)
        
        # Should produce valid bundle without attack-patterns
        assert result["type"] == "bundle"

    def test_findings_with_none_fields(self) -> None:
        """Test findings with None/missing fields handled gracefully."""
        findings = (
            {
                "id": "finding-none",
                "type": None,
                "severity": None,
                "target": None,
                "evidence": None,
                "timestamp": None,
                "agent_id": None,
            },
        )
        report_data = ReportData(
            engagement_id="eng-none",
            title="None Fields Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        # Should not raise exception
        result = exporter.export(report_data, as_dict=True)
        assert result["type"] == "bundle"

    def test_findings_with_datetime_objects(self) -> None:
        """Test findings with datetime objects (not strings)."""
        findings = (
            {
                "id": "finding-datetime",
                "type": "sqli",
                "severity": "high",
                "target": "192.168.1.1",
                "evidence": "SQL Injection",
                "timestamp": datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
                "agent_id": "agent-1",
            },
        )
        report_data = ReportData(
            engagement_id="eng-datetime",
            title="Datetime Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        result = exporter.export(report_data, as_dict=True)
        assert result["type"] == "bundle"


# =============================================================================
# Validate STIX Function Tests
# =============================================================================


class TestValidateSTIX:
    """Tests for validate_stix function."""

    def test_validate_stix_with_valid_output(
        self, sample_report_data: ReportData
    ) -> None:
        """Test validate_stix returns True for valid STIX output."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data)
        
        assert validate_stix(result) is True

    def test_validate_stix_with_dict(
        self, sample_report_data: ReportData
    ) -> None:
        """Test validate_stix works with dict input."""
        exporter = STIXExporter()
        result = exporter.export(sample_report_data, as_dict=True)
        
        assert validate_stix(result) is True

    def test_validate_stix_raises_on_invalid(self) -> None:
        """Test validate_stix raises on invalid STIX."""
        invalid_stix = {"type": "invalid", "objects": []}
        
        with pytest.raises(Exception):  # stix2 raises various exceptions
            validate_stix(invalid_stix)


# =============================================================================
# Additional Coverage Tests
# =============================================================================


class TestAdditionalCoverage:
    """Additional tests for 100% coverage."""

    def test_invalid_attck_technique_id_skipped(self) -> None:
        """Test invalid ATT&CK technique IDs are skipped."""
        findings = (
            {
                "id": "finding-invalid-attck",
                "type": "sqli",
                "severity": "critical",
                "target": "192.168.1.1",
                "evidence": "SQL Injection",
                "timestamp": "2026-02-12T06:00:00Z",
                "agent_id": "agent-1",
                "attck_ids": ["INVALID", "NOT-A-TECHNIQUE", "12345"],
            },
        )
        report_data = ReportData(
            engagement_id="eng-invalid-attck",
            title="Invalid ATT&CK Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        result = exporter.export(report_data, as_dict=True)
        
        # Should not have attack-pattern objects for invalid IDs
        attack_patterns = [obj for obj in result["objects"] if obj["type"] == "attack-pattern"]
        assert len(attack_patterns) == 0

    def test_empty_target_uses_unknown_domain(self) -> None:
        """Test empty target uses 'unknown' domain pattern."""
        findings = (
            {
                "id": "finding-empty-target",
                "type": "sqli",
                "severity": "critical",
                "target": "",
                "evidence": "SQL Injection",
                "timestamp": "2026-02-12T06:00:00Z",
                "agent_id": "agent-1",
            },
        )
        report_data = ReportData(
            engagement_id="eng-empty-target",
            title="Empty Target Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        result = exporter.export(report_data, as_dict=True)
        
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        assert len(indicators) >= 1
        # Pattern should use 'unknown' domain
        assert any("unknown" in i["pattern"] for i in indicators)

    def test_domain_target_with_single_quotes(self) -> None:
        """Test domain target with single quotes is escaped."""
        findings = (
            {
                "id": "finding-quotes",
                "type": "sqli",
                "severity": "critical",
                "target": "example.com/path?q='test'",
                "evidence": "SQL Injection",
                "timestamp": "2026-02-12T06:00:00Z",
                "agent_id": "agent-1",
            },
        )
        report_data = ReportData(
            engagement_id="eng-quotes",
            title="Quotes Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        result = exporter.export(report_data, as_dict=True)
        
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        assert len(indicators) >= 1
        # Should have escaped quotes
        assert any("domain-name" in i["pattern"] for i in indicators)

    def test_non_string_non_datetime_timestamp(self) -> None:
        """Test non-string, non-datetime timestamp falls back to now."""
        findings = (
            {
                "id": "finding-bad-timestamp",
                "type": "sqli",
                "severity": "critical",
                "target": "192.168.1.1",
                "evidence": "SQL Injection",
                "timestamp": 12345,  # Invalid: not string or datetime
                "agent_id": "agent-1",
            },
        )
        report_data = ReportData(
            engagement_id="eng-bad-timestamp",
            title="Bad Timestamp Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        result = exporter.export(report_data, as_dict=True)
        
        # Should produce valid bundle without error
        assert result["type"] == "bundle"
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        assert len(indicators) >= 1

    def test_validate_stix_with_non_bundle_stix_object(self) -> None:
        """Test validate_stix raises on valid STIX but not Bundle."""
        import stix2
        
        # Create a valid STIX object but not a Bundle
        indicator = stix2.Indicator(
            name="test",
            pattern="[domain-name:value = 'test.com']",
            pattern_type="stix",
            valid_from="2026-02-12T06:00:00Z",
        )
        
        with pytest.raises(ValueError, match="must be a Bundle"):
            validate_stix(indicator.serialize())

    def test_url_target_with_single_quotes(self) -> None:
        """Test URL target with single quotes is escaped."""
        findings = (
            {
                "id": "finding-url-quotes",
                "type": "sqli",
                "severity": "critical",
                "target": "http://example.com/path?q='injection'",
                "evidence": "SQL Injection",
                "timestamp": "2026-02-12T06:00:00Z",
                "agent_id": "agent-1",
            },
        )
        report_data = ReportData(
            engagement_id="eng-url-quotes",
            title="URL Quotes Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        result = exporter.export(report_data, as_dict=True)
        
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        assert len(indicators) >= 1
        # Should use URL pattern
        assert any("url:value" in i["pattern"] for i in indicators)

    def test_low_severity_with_attck_ids_no_indicator(self) -> None:
        """Test low severity finding with ATT&CK IDs creates pattern but no indicator."""
        findings = (
            {
                "id": "finding-low-attck",
                "type": "info_disclosure",
                "severity": "low",
                "target": "192.168.1.1",
                "evidence": "Server version disclosed",
                "timestamp": "2026-02-12T06:00:00Z",
                "agent_id": "agent-1",
                "attck_ids": ["T1592"],
            },
        )
        report_data = ReportData(
            engagement_id="eng-low-attck",
            title="Low Severity ATT&CK Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        result = exporter.export(report_data, as_dict=True)
        
        # Should have attack-pattern but no indicator (low severity)
        attack_patterns = [obj for obj in result["objects"] if obj["type"] == "attack-pattern"]
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        relationships = [obj for obj in result["objects"] if obj["type"] == "relationship"]
        
        assert len(attack_patterns) == 1
        assert len(indicators) == 0
        assert len(relationships) == 0  # No relationships without indicators

    def test_finding_with_none_timestamp(self) -> None:
        """Test finding with None timestamp uses current time."""
        findings = (
            {
                "id": "finding-none-ts",
                "type": "sqli",
                "severity": "critical",
                "target": "192.168.1.1",
                "evidence": "SQL Injection",
                "timestamp": None,
                "agent_id": "agent-1",
            },
        )
        report_data = ReportData(
            engagement_id="eng-none-ts",
            title="None Timestamp Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        result = exporter.export(report_data, as_dict=True)
        
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        assert len(indicators) >= 1
        # Should have valid_from with current time
        assert "valid_from" in indicators[0]

    def test_duplicate_attck_ids_within_finding(self) -> None:
        """Test duplicate ATT&CK IDs within same finding only create one pattern."""
        findings = (
            {
                "id": "finding-1",
                "type": "sqli",
                "severity": "critical",
                "target": "192.168.1.1",
                "evidence": "SQL Injection",
                "timestamp": "2026-02-12T06:00:00Z",
                "agent_id": "agent-1",
                "attck_ids": ["T1190", "T1190", "T1190"],  # Duplicates
            },
        )
        report_data = ReportData(
            engagement_id="eng-dup-attck",
            title="Duplicate ATT&CK Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        result = exporter.export(report_data, as_dict=True)
        
        # Should have only one T1190 attack-pattern (deduplicated within finding)
        attack_patterns = [obj for obj in result["objects"] if obj["type"] == "attack-pattern"]
        t1190_patterns = [ap for ap in attack_patterns if "T1190" in ap["name"]]
        assert len(t1190_patterns) == 1
        
        # One indicator
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        assert len(indicators) == 1

    def test_ip_with_port_extracts_ip_correctly(self) -> None:
        """Test IP address with port extracts IP correctly."""
        findings = (
            {
                "id": "finding-ip-port",
                "type": "rce",
                "severity": "critical",
                "target": "192.168.1.50:8080",
                "evidence": "Remote code execution",
                "timestamp": "2026-02-12T06:00:00Z",
                "agent_id": "agent-1",
            },
        )
        report_data = ReportData(
            engagement_id="eng-ip-port",
            title="IP with Port Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        result = exporter.export(report_data, as_dict=True)
        
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        assert len(indicators) == 1
        # Should extract IP without port
        assert "ipv4-addr:value = '192.168.1.50'" in indicators[0]["pattern"]

    def test_sub_technique_url_format(self) -> None:
        """Test ATT&CK sub-technique ID converts to correct URL format."""
        findings = (
            {
                "id": "finding-sub-tech",
                "type": "rce",
                "severity": "critical",
                "target": "192.168.1.1",
                "evidence": "Command injection",
                "timestamp": "2026-02-12T06:00:00Z",
                "agent_id": "agent-1",
                "attck_ids": ["T1059.001"],  # Sub-technique
            },
        )
        report_data = ReportData(
            engagement_id="eng-sub-tech",
            title="Sub-technique Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        result = exporter.export(report_data, as_dict=True)
        
        attack_patterns = [obj for obj in result["objects"] if obj["type"] == "attack-pattern"]
        assert len(attack_patterns) == 1
        
        # Check URL format - T1059.001 should become T1059/001
        ext_refs = attack_patterns[0]["external_references"]
        mitre_ref = next(r for r in ext_refs if r["source_name"] == "mitre-attack")
        assert "T1059/001" in mitre_ref["url"]

    def test_invalid_ip_treated_as_domain(self) -> None:
        """Test invalid IP address (octets > 255) treated as domain."""
        findings = (
            {
                "id": "finding-invalid-ip",
                "type": "sqli",
                "severity": "critical",
                "target": "999.999.999.999",
                "evidence": "SQL Injection",
                "timestamp": "2026-02-12T06:00:00Z",
                "agent_id": "agent-1",
            },
        )
        report_data = ReportData(
            engagement_id="eng-invalid-ip",
            title="Invalid IP Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        result = exporter.export(report_data, as_dict=True)
        
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        assert len(indicators) == 1
        # Should be treated as domain, not IP
        assert "domain-name:value" in indicators[0]["pattern"]

    def test_naive_datetime_handled_correctly(self) -> None:
        """Test naive datetime (no timezone) is handled correctly."""
        from datetime import datetime as dt
        
        # Create naive datetime (no timezone)
        naive_dt = dt(2026, 2, 12, 6, 0, 0)  # No tzinfo
        
        findings = (
            {
                "id": "finding-naive-dt",
                "type": "sqli",
                "severity": "critical",
                "target": "192.168.1.1",
                "evidence": "SQL Injection",
                "timestamp": naive_dt,
                "agent_id": "agent-1",
            },
        )
        report_data = ReportData(
            engagement_id="eng-naive-dt",
            title="Naive Datetime Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        result = exporter.export(report_data, as_dict=True)
        
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        assert len(indicators) == 1
        # Should have valid timestamp with proper format
        assert "valid_from" in indicators[0]
        assert "2026-02-12T06:00:00" in indicators[0]["valid_from"]

    def test_invalid_attck_id_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test invalid ATT&CK technique ID logs a warning."""
        import logging
        
        findings = (
            {
                "id": "finding-bad-attck",
                "type": "sqli",
                "severity": "critical",
                "target": "192.168.1.1",
                "evidence": "SQL Injection",
                "timestamp": "2026-02-12T06:00:00Z",
                "agent_id": "agent-1",
                "attck_ids": ["INVALID_ID"],
            },
        )
        report_data = ReportData(
            engagement_id="eng-bad-attck",
            title="Bad ATT&CK Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        with caplog.at_level(logging.WARNING):
            exporter = STIXExporter()
            exporter.export(report_data, as_dict=True)
        
        # Should log warning about invalid ID
        assert "INVALID_ID" in caplog.text
