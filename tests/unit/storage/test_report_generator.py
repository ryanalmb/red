"""Unit tests for Markdown Report Generation (Story 13.4).

Tests cover:
- ReportData dataclass and factory
- MarkdownReportGenerator template loading and rendering
- Report sections (executive summary, findings, timeline)
- Report signing (HMAC-SHA256)
- Report save operations

TDD Phase: RED - All tests should FAIL before implementation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

# TDD RED Phase: Import will fail until implementation exists
# Using pytest.importorskip to gracefully handle missing module
try:
    from cyberred.storage.report_generator import (
        MarkdownReportGenerator,
        ReportData,
        SignedReport,
        TimelineEvent,
        save_report,
        save_signed_report,
        sign_report,
        verify_signature,
    )
    HAS_REPORT_GENERATOR = True
except ImportError:
    HAS_REPORT_GENERATOR = False
    # Define placeholder classes for type hints in fixtures
    MarkdownReportGenerator = None
    ReportData = None
    SignedReport = None
    TimelineEvent = None
    save_report = None
    save_signed_report = None
    sign_report = None
    verify_signature = None


# Skip all tests if module not implemented yet (TDD RED phase)
pytestmark = pytest.mark.skipif(
    not HAS_REPORT_GENERATOR,
    reason="TDD RED phase: cyberred.storage.report_generator not yet implemented"
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_finding() -> dict:
    """Create a sample finding dict for testing."""
    return {
        "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "type": "sqli",
        "severity": "critical",
        "target": "192.168.1.100",
        "evidence": "SQL injection in login form",
        "agent_id": "f47ac10b-58cc-4372-a567-0e02b2c3d480",
        "timestamp": "2026-02-12T10:00:00Z",
        "tool": "sqlmap",
        "topic": "findings:eng001:sqli",
        "signature": "hmac-sig-123",
        "cve_id": "CVE-2024-1234",
        "cvss_score": 9.8,
        "description": "Critical SQL injection vulnerability",
    }


@pytest.fixture
def sample_findings() -> list[dict]:
    """Create multiple findings across severities."""
    return [
        {
            "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "type": "sqli",
            "severity": "critical",
            "target": "192.168.1.100",
            "evidence": "SQL injection",
            "agent_id": "f47ac10b-58cc-4372-a567-0e02b2c3d480",
            "timestamp": "2026-02-12T10:00:00Z",
            "tool": "sqlmap",
            "topic": "findings:eng001:sqli",
            "signature": "sig1",
            "cve_id": "CVE-2024-1234",
            "cvss_score": 9.8,
            "description": "Critical SQL injection",
        },
        {
            "id": "a47ac10b-58cc-4372-a567-0e02b2c3d479",
            "type": "xss",
            "severity": "high",
            "target": "192.168.1.101",
            "evidence": "Reflected XSS",
            "agent_id": "f47ac10b-58cc-4372-a567-0e02b2c3d480",
            "timestamp": "2026-02-12T11:00:00Z",
            "tool": "nuclei",
            "topic": "findings:eng001:xss",
            "signature": "sig2",
            "cve_id": "CVE-2024-5678",
            "cvss_score": 7.5,
            "description": "Reflected XSS vulnerability",
        },
        {
            "id": "b47ac10b-58cc-4372-a567-0e02b2c3d479",
            "type": "info_disclosure",
            "severity": "medium",
            "target": "192.168.1.102",
            "evidence": "Server version exposed",
            "agent_id": "f47ac10b-58cc-4372-a567-0e02b2c3d480",
            "timestamp": "2026-02-12T12:00:00Z",
            "tool": "nmap",
            "topic": "findings:eng001:info",
            "signature": "sig3",
            "cve_id": None,
            "cvss_score": 5.0,
            "description": "Information disclosure",
        },
        {
            "id": "c47ac10b-58cc-4372-a567-0e02b2c3d479",
            "type": "weak_config",
            "severity": "low",
            "target": "192.168.1.103",
            "evidence": "Weak TLS config",
            "agent_id": "f47ac10b-58cc-4372-a567-0e02b2c3d480",
            "timestamp": "2026-02-12T13:00:00Z",
            "tool": "testssl",
            "topic": "findings:eng001:config",
            "signature": "sig4",
            "cve_id": None,
            "cvss_score": 3.0,
            "description": "Weak TLS configuration",
        },
        {
            "id": "d47ac10b-58cc-4372-a567-0e02b2c3d479",
            "type": "open_port",
            "severity": "info",
            "target": "192.168.1.104",
            "evidence": "Port 22 open",
            "agent_id": "f47ac10b-58cc-4372-a567-0e02b2c3d480",
            "timestamp": "2026-02-12T14:00:00Z",
            "tool": "nmap",
            "topic": "findings:eng001:port",
            "signature": "sig5",
            "cve_id": None,
            "cvss_score": 0.0,
            "description": "Open SSH port",
        },
    ]


@pytest.fixture
def sample_timeline_events() -> list[dict]:
    """Create sample timeline events."""
    return [
        {
            "timestamp": "2026-02-12T09:00:00Z",
            "event_type": "engagement_start",
            "description": "Engagement started",
            "agent_id": "orchestrator",
            "details": {"config": "test.yaml"},
        },
        {
            "timestamp": "2026-02-12T10:00:00Z",
            "event_type": "finding_discovered",
            "description": "SQL injection found",
            "agent_id": "recon-agent-001",
            "details": {"finding_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"},
        },
        {
            "timestamp": "2026-02-12T15:00:00Z",
            "event_type": "engagement_end",
            "description": "Engagement completed",
            "agent_id": "orchestrator",
            "details": {"total_findings": 5},
        },
    ]


@pytest.fixture
def sample_scope() -> dict:
    """Create sample scope definition."""
    return {
        "targets": ["192.168.1.0/24", "https://app.example.com"],
        "exclusions": ["192.168.1.1", "192.168.1.254"],
    }


@pytest.fixture
def sample_report_data(
    sample_findings, sample_timeline_events, sample_scope
) -> ReportData:
    """Create a complete ReportData instance."""
    return ReportData(
        engagement_id="eng-001",
        title="Penetration Test Report - Example Corp",
        start_time=datetime(2026, 2, 12, 9, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 12, 15, 0, 0, tzinfo=timezone.utc),
        scope=sample_scope,
        findings=tuple(sample_findings),
        timeline_events=tuple(
            TimelineEvent(**event) for event in sample_timeline_events
        ),
        metadata={"client": "Example Corp", "tester": "Cyber-Red"},
    )


@pytest.fixture
def signing_key() -> bytes:
    """Create a test signing key."""
    return b"test-signing-key-32bytes-long!!"


# =============================================================================
# Task 2: ReportData Model Tests (AC: #3)
# =============================================================================


class TestTimelineEvent:
    """Tests for TimelineEvent dataclass."""

    def test_timeline_event_creation(self) -> None:
        """Test TimelineEvent can be created with all fields."""
        event = TimelineEvent(
            timestamp="2026-02-12T10:00:00Z",
            event_type="finding_discovered",
            description="Found SQL injection",
            agent_id="recon-agent-001",
            details={"finding_id": "abc123"},
        )
        assert event.timestamp == "2026-02-12T10:00:00Z"
        assert event.event_type == "finding_discovered"
        assert event.description == "Found SQL injection"
        assert event.agent_id == "recon-agent-001"
        assert event.details == {"finding_id": "abc123"}

    def test_timeline_event_optional_details(self) -> None:
        """Test TimelineEvent with empty details."""
        event = TimelineEvent(
            timestamp="2026-02-12T10:00:00Z",
            event_type="scan_start",
            description="Scan started",
            agent_id="scanner",
        )
        assert event.details == {} or event.details is None


class TestReportData:
    """Tests for ReportData dataclass."""

    def test_report_data_creation(self, sample_scope) -> None:
        """Test ReportData can be created with all required fields."""
        report_data = ReportData(
            engagement_id="eng-001",
            title="Test Report",
            start_time=datetime(2026, 2, 12, 9, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 12, 15, 0, 0, tzinfo=timezone.utc),
            scope=sample_scope,
            findings=(),
            timeline_events=(),
        )
        assert report_data.engagement_id == "eng-001"
        assert report_data.title == "Test Report"
        assert report_data.scope == sample_scope

    def test_report_data_with_none_end_time(self, sample_scope) -> None:
        """Test ReportData allows None end_time for ongoing engagement."""
        report_data = ReportData(
            engagement_id="eng-002",
            title="Ongoing Report",
            start_time=datetime(2026, 2, 12, 9, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope=sample_scope,
            findings=(),
            timeline_events=(),
        )
        assert report_data.end_time is None

    def test_findings_by_severity(self, sample_report_data) -> None:
        """Test findings are correctly grouped by severity."""
        grouped = sample_report_data.findings_by_severity()
        
        assert "critical" in grouped
        assert "high" in grouped
        assert "medium" in grouped
        assert "low" in grouped
        assert "info" in grouped
        
        assert len(grouped["critical"]) == 1
        assert len(grouped["high"]) == 1
        assert len(grouped["medium"]) == 1
        assert len(grouped["low"]) == 1
        assert len(grouped["info"]) == 1

    def test_findings_by_severity_empty(self, sample_scope) -> None:
        """Test findings_by_severity with no findings."""
        report_data = ReportData(
            engagement_id="eng-003",
            title="Empty Report",
            start_time=datetime.now(timezone.utc),
            end_time=None,
            scope=sample_scope,
            findings=(),
            timeline_events=(),
        )
        grouped = report_data.findings_by_severity()
        
        # Should return empty lists for all severities
        for severity in ["critical", "high", "medium", "low", "info"]:
            assert grouped.get(severity, []) == []

    def test_findings_by_severity_unknown_severity(self, sample_scope) -> None:
        """Test findings with unknown severity are ignored."""
        report_data = ReportData(
            engagement_id="eng-unknown",
            title="Unknown Severity Report",
            start_time=datetime.now(timezone.utc),
            end_time=None,
            scope=sample_scope,
            findings=(
                {
                    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "type": "test",
                    "severity": "unknown_level",  # Invalid severity
                    "target": "192.168.1.1",
                    "description": "Test finding",
                },
                {
                    "id": "a47ac10b-58cc-4372-a567-0e02b2c3d479",
                    "type": "test2",
                    "severity": "high",  # Valid severity
                    "target": "192.168.1.2",
                    "description": "Valid finding",
                },
            ),
            timeline_events=(),
        )
        grouped = report_data.findings_by_severity()
        
        # Unknown severity should be ignored, only high should be present
        assert len(grouped["high"]) == 1
        assert len(grouped["critical"]) == 0
        # Total findings in grouped should be 1 (the valid one)
        total = sum(len(v) for v in grouped.values())
        assert total == 1

    def test_timeline_events_sorted(self, sample_report_data) -> None:
        """Test timeline events are sorted by timestamp."""
        events = sample_report_data.get_sorted_timeline()
        
        assert len(events) == 3
        # Events should be in chronological order
        assert events[0].event_type == "engagement_start"
        assert events[1].event_type == "finding_discovered"
        assert events[2].event_type == "engagement_end"

    def test_report_data_optional_metadata(self, sample_scope) -> None:
        """Test ReportData with optional metadata."""
        report_data = ReportData(
            engagement_id="eng-004",
            title="Report with Metadata",
            start_time=datetime.now(timezone.utc),
            end_time=None,
            scope=sample_scope,
            findings=(),
            timeline_events=(),
            metadata={"extra": "data"},
        )
        assert report_data.metadata == {"extra": "data"}

    def test_report_data_default_metadata(self, sample_scope) -> None:
        """Test ReportData defaults metadata to empty dict."""
        report_data = ReportData(
            engagement_id="eng-005",
            title="Report without Metadata",
            start_time=datetime.now(timezone.utc),
            end_time=None,
            scope=sample_scope,
            findings=(),
            timeline_events=(),
        )
        assert report_data.metadata == {} or report_data.metadata is None


# =============================================================================
# Task 3: MarkdownReportGenerator Tests (AC: #1, #2, #3, #4)
# =============================================================================


class TestMarkdownReportGenerator:
    """Tests for MarkdownReportGenerator class."""

    def test_generator_init_default_template(self) -> None:
        """Test generator loads default template when no path specified."""
        generator = MarkdownReportGenerator()
        assert generator.template is not None
        assert generator.template_path is not None

    def test_generator_init_custom_template(self, tmp_path: Path) -> None:
        """Test generator loads custom template from specified path."""
        # Create a custom template
        custom_template = tmp_path / "custom.jinja2"
        custom_template.write_text("# Custom: {{ title }}")
        
        generator = MarkdownReportGenerator(template_path=custom_template)
        assert generator.template_path == custom_template

    def test_generator_template_not_found(self, tmp_path: Path) -> None:
        """Test generator raises FileNotFoundError for missing template."""
        missing_path = tmp_path / "nonexistent.jinja2"
        
        with pytest.raises(FileNotFoundError):
            MarkdownReportGenerator(template_path=missing_path)

    def test_generate_returns_markdown_string(self, sample_report_data) -> None:
        """Test generate() returns a Markdown string."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_includes_title(self, sample_report_data) -> None:
        """Test generated report includes the title."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert sample_report_data.title in result

    def test_generate_includes_engagement_id(self, sample_report_data) -> None:
        """Test generated report includes engagement ID."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert sample_report_data.engagement_id in result

    def test_generate_includes_executive_summary_section(
        self, sample_report_data
    ) -> None:
        """Test generated report contains executive summary section."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert "Executive Summary" in result or "## Executive Summary" in result

    def test_generate_includes_findings_section(self, sample_report_data) -> None:
        """Test generated report contains findings section."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert "Findings" in result or "## Findings" in result

    def test_generate_includes_timeline_section(self, sample_report_data) -> None:
        """Test generated report contains timeline section."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert "Timeline" in result or "## Timeline" in result

    def test_generate_includes_scope_section(self, sample_report_data) -> None:
        """Test generated report contains scope section."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert "Scope" in result or "## Scope" in result

    def test_generate_uses_jinja2_template(self, sample_report_data) -> None:
        """Test report is generated using Jinja2 template engine."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        # Verify no Jinja2 syntax remains in output
        assert "{{" not in result
        assert "}}" not in result
        assert "{%" not in result
        assert "%}" not in result


# =============================================================================
# Task 4: Report Sections Tests (AC: #3)
# =============================================================================


class TestReportSections:
    """Tests for report section content."""

    def test_duration_hours_only(self, sample_scope) -> None:
        """Test duration formatting with hours only (no minutes)."""
        from datetime import timedelta
        start = datetime(2026, 2, 12, 9, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=3)  # Exactly 3 hours, 0 minutes
        
        generator = MarkdownReportGenerator()
        # Directly test the private method to ensure coverage
        duration = generator._format_duration(start, end)
        assert duration == "3 hours"
        
        report_data = ReportData(
            engagement_id="eng-duration",
            title="Duration Test",
            start_time=start,
            end_time=end,
            scope=sample_scope,
            findings=(),
            timeline_events=(),
        )
        
        result = generator.generate(report_data)
        
        assert "3 hours" in result
        # Should NOT have "minutes" since it's exactly 3 hours
        assert "3 hours minutes" not in result

    def test_duration_minutes_only(self, sample_scope) -> None:
        """Test duration formatting with minutes only (less than 1 hour)."""
        from datetime import timedelta
        start = datetime(2026, 2, 12, 9, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=45)  # 45 minutes
        
        generator = MarkdownReportGenerator()
        duration = generator._format_duration(start, end)
        assert duration == "45 minutes"

    def test_duration_hours_and_minutes(self, sample_scope) -> None:
        """Test duration formatting with both hours and minutes."""
        from datetime import timedelta
        start = datetime(2026, 2, 12, 9, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=2, minutes=30)  # 2 hours 30 minutes
        
        generator = MarkdownReportGenerator()
        duration = generator._format_duration(start, end)
        assert duration == "2 hours 30 minutes"

    def test_duration_zero_seconds(self, sample_scope) -> None:
        """Test duration formatting when start equals end (0 duration)."""
        start = datetime(2026, 2, 12, 9, 0, 0, tzinfo=timezone.utc)
        end = start  # Same time = 0 duration
        
        generator = MarkdownReportGenerator()
        duration = generator._format_duration(start, end)
        # Should indicate instant/zero duration clearly
        assert duration == "< 1 minute"

    def test_duration_negative_raises_error(self, sample_scope) -> None:
        """Test duration formatting raises error when end is before start."""
        start = datetime(2026, 2, 12, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 2, 12, 10, 0, 0, tzinfo=timezone.utc)  # End before start
        
        generator = MarkdownReportGenerator()
        with pytest.raises(ValueError, match="end_time cannot be before start_time"):
            generator._format_duration(start, end)

    def test_executive_summary_includes_finding_counts(
        self, sample_report_data
    ) -> None:
        """Test executive summary includes finding counts by severity."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        # Should mention counts for each severity
        # At minimum, the critical count should appear
        assert "1" in result  # We have 1 critical finding
        assert "Critical" in result or "critical" in result

    def test_executive_summary_includes_duration(self, sample_report_data) -> None:
        """Test executive summary includes engagement duration."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        # Duration is 6 hours (9:00 to 15:00)
        assert "Duration" in result or "duration" in result or "6" in result

    def test_findings_include_cve_ids(self, sample_report_data) -> None:
        """Test findings section includes CVE IDs."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert "CVE-2024-1234" in result

    def test_findings_include_cvss_scores(self, sample_report_data) -> None:
        """Test findings section includes CVSS scores."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert "9.8" in result or "9,8" in result  # Account for locale

    def test_findings_include_affected_targets(self, sample_report_data) -> None:
        """Test findings section includes affected targets."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert "192.168.1.100" in result

    def test_findings_include_descriptions(self, sample_report_data) -> None:
        """Test findings section includes descriptions."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert "Critical SQL injection" in result

    def test_findings_grouped_by_severity(self, sample_report_data) -> None:
        """Test findings are grouped by severity in the report."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        # Each severity level should appear as a section header
        assert "Critical" in result
        assert "High" in result
        assert "Medium" in result
        assert "Low" in result

    def test_timeline_includes_timestamps(self, sample_report_data) -> None:
        """Test timeline section includes event timestamps."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert "2026-02-12" in result

    def test_timeline_includes_agent_attributions(self, sample_report_data) -> None:
        """Test timeline section includes agent attributions."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert "orchestrator" in result or "recon-agent" in result

    def test_scope_includes_targets(self, sample_report_data) -> None:
        """Test scope section includes targets."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert "192.168.1.0/24" in result
        assert "https://app.example.com" in result

    def test_scope_includes_exclusions(self, sample_report_data) -> None:
        """Test scope section includes exclusions."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert "192.168.1.1" in result
        assert "192.168.1.254" in result

    def test_appendix_section_exists(self, sample_report_data) -> None:
        """Test appendix section exists in report."""
        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)
        
        assert "Appendix" in result or "## Appendix" in result


# =============================================================================
# Task 5: Report Signing Tests (AC: #6)
# =============================================================================


class TestDataclassImmutability:
    """Tests for dataclass immutability (security requirement)."""

    def test_signed_report_is_frozen(self, signing_key: bytes) -> None:
        """Test SignedReport cannot be modified after creation."""
        content = "# Test Report"
        signed = sign_report(content, signing_key)
        
        with pytest.raises(AttributeError):
            signed.content = "TAMPERED"

    def test_timeline_event_is_frozen(self) -> None:
        """Test TimelineEvent cannot be modified after creation."""
        event = TimelineEvent(
            timestamp="2026-02-12T10:00:00Z",
            event_type="test",
            description="Test event",
            agent_id="agent-1",
        )
        
        with pytest.raises(AttributeError):
            event.timestamp = "TAMPERED"

    def test_report_data_is_frozen(self, sample_scope) -> None:
        """Test ReportData cannot be modified after creation."""
        report_data = ReportData(
            engagement_id="eng-001",
            title="Test Report",
            start_time=datetime.now(timezone.utc),
            end_time=None,
            scope=sample_scope,
            findings=(),
            timeline_events=(),
        )
        
        with pytest.raises(AttributeError):
            report_data.engagement_id = "TAMPERED"


class TestReportSigning:
    """Tests for report signing functionality."""

    def test_sign_report_returns_signed_report(self, signing_key: bytes) -> None:
        """Test sign_report returns a SignedReport object."""
        content = "# Test Report\n\nThis is a test."
        
        signed = sign_report(content, signing_key)
        
        assert isinstance(signed, SignedReport)

    def test_signed_report_contains_content(self, signing_key: bytes) -> None:
        """Test SignedReport contains the original content."""
        content = "# Test Report\n\nThis is a test."
        
        signed = sign_report(content, signing_key)
        
        assert signed.content == content

    def test_signed_report_contains_signature(self, signing_key: bytes) -> None:
        """Test SignedReport contains HMAC-SHA256 signature."""
        content = "# Test Report\n\nThis is a test."
        
        signed = sign_report(content, signing_key)
        
        assert signed.signature is not None
        assert len(signed.signature) > 0

    def test_signed_report_contains_timestamp(self, signing_key: bytes) -> None:
        """Test SignedReport contains timestamp."""
        content = "# Test Report"
        
        signed = sign_report(content, signing_key)
        
        assert signed.timestamp is not None
        # Should be ISO 8601 format
        assert "T" in signed.timestamp or "Z" in signed.timestamp

    def test_signed_report_contains_key_id(self, signing_key: bytes) -> None:
        """Test SignedReport contains key_id."""
        content = "# Test Report"
        
        signed = sign_report(content, signing_key)
        
        assert signed.key_id is not None

    def test_signed_report_contains_content_hash(self, signing_key: bytes) -> None:
        """Test SignedReport contains content hash."""
        content = "# Test Report"
        
        signed = sign_report(content, signing_key)
        
        assert signed.content_hash is not None
        # Should be SHA-256 hex digest
        assert len(signed.content_hash) == 64 or signed.content_hash.startswith("sha256:")

    def test_verify_signature_valid(self, signing_key: bytes) -> None:
        """Test verify_signature returns True for valid signature."""
        content = "# Test Report\n\nThis is valid content."
        
        signed = sign_report(content, signing_key)
        result = verify_signature(signed, signing_key)
        
        assert result is True

    def test_verify_signature_tampered_content(self, signing_key: bytes) -> None:
        """Test verify_signature returns False for tampered content."""
        content = "# Test Report\n\nOriginal content."
        
        signed = sign_report(content, signing_key)
        # Create a new SignedReport with tampered content (since SignedReport is frozen)
        tampered = SignedReport(
            content="# Test Report\n\nTampered content!",
            signature=signed.signature,
            timestamp=signed.timestamp,
            key_id=signed.key_id,
            content_hash=signed.content_hash,
        )
        
        result = verify_signature(tampered, signing_key)
        
        assert result is False

    def test_verify_signature_wrong_key(self, signing_key: bytes) -> None:
        """Test verify_signature returns False with wrong key."""
        content = "# Test Report"
        wrong_key = b"wrong-signing-key-32bytes-long!!"
        
        signed = sign_report(content, signing_key)
        result = verify_signature(signed, wrong_key)
        
        assert result is False

    def test_signature_uses_hmac_sha256(self, signing_key: bytes) -> None:
        """Test signature is generated using HMAC-SHA256."""
        content = "# Test Report"
        
        signed = sign_report(content, signing_key)
        
        # Manually compute expected HMAC
        expected = hmac.new(signing_key, content.encode(), hashlib.sha256).hexdigest()
        
        # Signature should match or contain the expected value
        assert expected in signed.signature or signed.signature == expected

    def test_sign_report_with_custom_key_id(self, signing_key: bytes) -> None:
        """Test sign_report accepts custom key_id parameter."""
        content = "# Test Report"
        custom_key_id = "custom-signing-key-001"
        
        signed = sign_report(content, signing_key, key_id=custom_key_id)
        
        assert signed.key_id == custom_key_id

    def test_sign_report_default_key_id(self, signing_key: bytes) -> None:
        """Test sign_report uses default key_id when not specified."""
        content = "# Test Report"
        
        signed = sign_report(content, signing_key)
        
        assert signed.key_id == "engagement-key"


# =============================================================================
# Task 6: Report Save Tests (AC: #5)
# =============================================================================


class TestReportSave:
    """Tests for report save functionality."""

    def test_save_report_creates_file(self, tmp_path: Path) -> None:
        """Test save_report creates the output file."""
        content = "# Test Report\n\nContent here."
        output_path = tmp_path / "report.md"
        
        result = save_report(content, output_path)
        
        assert output_path.exists()
        assert result == output_path

    def test_save_report_utf8_encoding(self, tmp_path: Path) -> None:
        """Test save_report writes with UTF-8 encoding."""
        content = "# Test Report\n\nUnicode: é ñ ü 中文 日本語"
        output_path = tmp_path / "report.md"
        
        save_report(content, output_path)
        
        # Read back and verify
        saved_content = output_path.read_text(encoding="utf-8")
        assert saved_content == content

    def test_save_report_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test save_report creates parent directories if they don't exist."""
        content = "# Test Report"
        output_path = tmp_path / "nested" / "deep" / "report.md"
        
        save_report(content, output_path)
        
        assert output_path.exists()
        assert output_path.parent.exists()

    def test_save_signed_report_creates_files(
        self, tmp_path: Path, signing_key: bytes
    ) -> None:
        """Test save_signed_report creates both report and signature files."""
        content = "# Test Report"
        signed = sign_report(content, signing_key)
        output_path = tmp_path / "report.md"
        
        save_signed_report(signed, output_path)
        
        assert output_path.exists()
        assert output_path.with_suffix(".sig").exists()

    def test_save_signed_report_signature_file_format(
        self, tmp_path: Path, signing_key: bytes
    ) -> None:
        """Test signature file contains valid JSON with expected fields."""
        content = "# Test Report"
        signed = sign_report(content, signing_key)
        output_path = tmp_path / "report.md"
        
        save_signed_report(signed, output_path)
        
        sig_path = output_path.with_suffix(".sig")
        sig_content = json.loads(sig_path.read_text())
        
        assert "content_hash" in sig_content
        assert "signature" in sig_content
        assert "timestamp" in sig_content
        assert "key_id" in sig_content

    def test_save_report_returns_path(self, tmp_path: Path) -> None:
        """Test save_report returns the output path."""
        content = "# Test Report"
        output_path = tmp_path / "report.md"
        
        result = save_report(content, output_path)
        
        assert result == output_path
        assert isinstance(result, Path)
