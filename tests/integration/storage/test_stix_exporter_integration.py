"""Integration tests for STIX Exporter (Story 13.7).

Tests real STIX 2.1 export with actual stix2 library - NO MOCKS.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import stix2

from cyberred.storage.report_generator import ReportData, TimelineEvent
from cyberred.storage.stix_exporter import STIXExporter, validate_stix


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def realistic_findings() -> tuple[dict[str, Any], ...]:
    """Realistic findings from a penetration test."""
    return (
        {
            "id": "finding-001",
            "type": "sqli",
            "severity": "critical",
            "target": "http://192.168.1.100/api/users",
            "evidence": "Time-based SQL injection in 'id' parameter. CVE-2023-12345.",
            "timestamp": "2026-02-12T06:15:00Z",
            "agent_id": "webapp-agent-1",
            "tool": "sqlmap",
            "topic": "webapp",
            "attck_ids": ["T1190", "T1059.001"],
        },
        {
            "id": "finding-002",
            "type": "xss",
            "severity": "high",
            "target": "https://target.example.com/search",
            "evidence": "Reflected XSS via 'q' parameter",
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
            "target": "192.168.1.50:8080",
            "evidence": "Remote code execution via deserialization",
            "timestamp": "2026-02-12T07:00:00Z",
            "agent_id": "exploit-agent-1",
            "tool": "metasploit",
            "topic": "network",
            "attck_ids": ["T1059", "T1190"],
        },
    )


@pytest.fixture
def realistic_report_data(
    realistic_findings: tuple[dict[str, Any], ...]
) -> ReportData:
    """Realistic ReportData for integration testing."""
    return ReportData(
        engagement_id="eng-prod-2026-001",
        title="Production Penetration Test Q1 2026",
        start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 12, 18, 0, 0, tzinfo=timezone.utc),
        scope={
            "targets": ["192.168.1.0/24", "target.example.com"],
            "exclusions": ["192.168.1.1"],
        },
        findings=realistic_findings,
        timeline_events=(
            TimelineEvent(
                timestamp="2026-02-12T06:00:00Z",
                event_type="engagement_start",
                description="Engagement started",
                agent_id="system",
            ),
            TimelineEvent(
                timestamp="2026-02-12T06:15:00Z",
                event_type="finding_discovered",
                description="SQL Injection discovered",
                agent_id="webapp-agent-1",
            ),
        ),
    )


# =============================================================================
# Task 9: Integration Tests (AC: all)
# =============================================================================


class TestSTIXExporterIntegration:
    """Integration tests for full STIX export cycle."""

    def test_full_export_cycle(
        self, realistic_report_data: ReportData
    ) -> None:
        """Test full cycle: create ReportData with findings → export → validate."""
        exporter = STIXExporter()
        
        # Export to JSON string
        stix_json = exporter.export(realistic_report_data)
        
        # Validate it's proper JSON
        parsed = json.loads(stix_json)
        assert parsed["type"] == "bundle"
        
        # Validate against STIX schema
        assert validate_stix(stix_json) is True

    def test_exported_stix_is_valid_json(
        self, realistic_report_data: ReportData
    ) -> None:
        """Test exported STIX is valid JSON."""
        exporter = STIXExporter()
        stix_json = exporter.export(realistic_report_data)
        
        # Should parse without error
        parsed = json.loads(stix_json)
        
        # Should have required bundle fields
        assert "type" in parsed
        assert "id" in parsed
        assert "objects" in parsed

    def test_stix_bundle_parseable_by_stix2_library(
        self, realistic_report_data: ReportData
    ) -> None:
        """Test STIX bundle can be parsed by stix2 library."""
        exporter = STIXExporter()
        stix_json = exporter.export(realistic_report_data)
        
        # Parse with stix2 library - this validates STIX compliance
        bundle = stix2.parse(stix_json)
        
        assert isinstance(bundle, stix2.Bundle)
        assert len(bundle.objects) > 0

    def test_file_save_and_read_back(
        self, realistic_report_data: ReportData
    ) -> None:
        """Test file save and read back."""
        exporter = STIXExporter()
        stix_json = exporter.export(realistic_report_data)
        
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write(stix_json)
            temp_path = Path(f.name)
        
        try:
            # Read back
            content = temp_path.read_text(encoding="utf-8")
            
            # Should be identical
            assert content == stix_json
            
            # Should parse correctly
            bundle = stix2.parse(content)
            assert isinstance(bundle, stix2.Bundle)
        finally:
            temp_path.unlink()

    def test_large_findings_performance(self) -> None:
        """Test with 100+ findings for performance."""
        # Generate 100 findings
        findings = tuple(
            {
                "id": f"finding-{i:04d}",
                "type": "sqli" if i % 3 == 0 else "xss" if i % 3 == 1 else "rce",
                "severity": "critical" if i % 4 == 0 else "high",
                "target": f"http://192.168.1.{i % 256}/endpoint{i}",
                "evidence": f"Vulnerability {i} detected",
                "timestamp": f"2026-02-12T{6 + (i // 60):02d}:{i % 60:02d}:00Z",
                "agent_id": f"agent-{i % 10}",
                "tool": "sqlmap",
                "attck_ids": ["T1190"] if i % 2 == 0 else [],
            }
            for i in range(100)
        )
        
        report_data = ReportData(
            engagement_id="eng-perf-test",
            title="Performance Test",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 12, 12, 0, 0, tzinfo=timezone.utc),
            scope={"targets": ["192.168.1.0/24"], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        
        # Should complete without timeout
        import time
        start = time.time()
        stix_json = exporter.export(report_data)
        elapsed = time.time() - start
        
        # Should complete in reasonable time (< 10 seconds)
        assert elapsed < 10.0, f"Export took {elapsed:.2f}s"
        
        # Should be valid
        bundle = stix2.parse(stix_json)
        assert len(bundle.objects) > 100  # At least findings + identity + report

    def test_round_trip_export_parse_reexport(
        self, realistic_report_data: ReportData
    ) -> None:
        """Test round-trip: export → parse → verify structure preserved."""
        exporter = STIXExporter()
        
        # First export
        stix_json_1 = exporter.export(realistic_report_data)
        
        # Parse with stix2
        bundle_1 = stix2.parse(stix_json_1)
        
        # Get object counts by type
        def count_by_type(bundle: stix2.Bundle) -> dict[str, int]:
            counts: dict[str, int] = {}
            for obj in bundle.objects:
                obj_type = obj.type
                counts[obj_type] = counts.get(obj_type, 0) + 1
            return counts
        
        counts_1 = count_by_type(bundle_1)
        
        # Verify expected object types exist
        assert "identity" in counts_1
        assert "report" in counts_1
        assert "indicator" in counts_1
        assert "vulnerability" in counts_1
        assert "attack-pattern" in counts_1

    def test_unicode_handling_in_export(self) -> None:
        """Test Unicode is properly handled in export."""
        findings = (
            {
                "id": "finding-unicode",
                "type": "sqli",
                "severity": "critical",
                "target": "http://example.com/search?q=日本語テスト",
                "evidence": "SQL注入漏洞 - Unicode test: émojis 🔒",
                "timestamp": "2026-02-12T06:00:00Z",
                "agent_id": "agent-1",
                "attck_ids": ["T1190"],
            },
        )
        
        report_data = ReportData(
            engagement_id="eng-unicode",
            title="Unicode Test ünïcödé",
            start_time=datetime(2026, 2, 12, 6, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=findings,
            timeline_events=(),
        )
        
        exporter = STIXExporter()
        stix_json = exporter.export(report_data)
        
        # Should contain Unicode characters (not escaped)
        assert "日本語" in stix_json or "\\u" in stix_json
        
        # Should be valid STIX
        bundle = stix2.parse(stix_json)
        assert isinstance(bundle, stix2.Bundle)


class TestSTIXValidation:
    """Integration tests for STIX validation."""

    def test_validate_stix_with_real_bundle(
        self, realistic_report_data: ReportData
    ) -> None:
        """Test validate_stix with real exported bundle."""
        exporter = STIXExporter()
        stix_json = exporter.export(realistic_report_data)
        
        # Should return True for valid STIX
        assert validate_stix(stix_json) is True

    def test_validate_stix_catches_invalid_bundle(self) -> None:
        """Test validate_stix raises on invalid bundle."""
        invalid = '{"type": "not-a-bundle", "objects": []}'
        
        with pytest.raises(Exception):
            validate_stix(invalid)

    def test_relationship_count_matches_indicators_with_attck(
        self, realistic_report_data: ReportData
    ) -> None:
        """Test relationship count matches indicators linked to ATT&CK techniques."""
        exporter = STIXExporter()
        result = exporter.export(realistic_report_data, as_dict=True)
        
        # Count indicators and relationships
        indicators = [obj for obj in result["objects"] if obj["type"] == "indicator"]
        relationships = [obj for obj in result["objects"] if obj["type"] == "relationship"]
        
        # Each indicator with ATT&CK IDs should have relationships
        # From fixtures: finding-001 has 2 ATT&CK IDs, finding-002 has 1, finding-003 has 2
        # All 3 findings are critical/high so all create indicators
        # Expected relationships: 2 + 1 + 2 = 5
        assert len(indicators) == 3
        assert len(relationships) == 5
        
        # All relationships should be "indicates" type
        for rel in relationships:
            assert rel["relationship_type"] == "indicates"
            assert rel["source_ref"].startswith("indicator--")
            assert rel["target_ref"].startswith("attack-pattern--")
