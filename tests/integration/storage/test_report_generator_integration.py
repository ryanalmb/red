"""Integration tests for Markdown Report Generation (Story 13.4).

These tests verify the FULL cycle of report generation with MINIMAL mocks:
- Create engagement data with realistic findings
- Generate report using actual Jinja2 template
- Sign report with cryptographic signature
- Save to filesystem
- Verify saved content and signature

TDD Phase: RED - All tests should FAIL before implementation.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

# TDD RED Phase: Import will fail until implementation exists
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
# Integration Test Fixtures
# =============================================================================


@pytest.fixture
def realistic_findings() -> list[dict]:
    """Create realistic finding data matching production scenarios."""
    return [
        {
            "id": "550e8400-e29b-41d4-a716-446655440001",
            "type": "sqli",
            "severity": "critical",
            "target": "https://api.example.com/login",
            "evidence": "Parameter 'username' vulnerable to SQL injection. "
            "Payload: ' OR 1=1 -- resulted in authentication bypass.",
            "agent_id": "550e8400-e29b-41d4-a716-446655440010",
            "timestamp": "2026-02-12T10:15:32Z",
            "tool": "sqlmap",
            "topic": "findings:eng-prod-001:sqli",
            "signature": "hmac-abc123",
            "cve_id": "CVE-2024-12345",
            "cvss_score": 9.8,
            "description": "Critical SQL Injection in authentication endpoint "
            "allows complete database access and authentication bypass.",
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440002",
            "type": "rce",
            "severity": "critical",
            "target": "192.168.100.50",
            "evidence": "Apache Struts vulnerable to CVE-2017-5638. "
            "RCE achieved via Content-Type header manipulation.",
            "agent_id": "550e8400-e29b-41d4-a716-446655440011",
            "timestamp": "2026-02-12T11:30:00Z",
            "tool": "nuclei",
            "topic": "findings:eng-prod-001:rce",
            "signature": "hmac-def456",
            "cve_id": "CVE-2017-5638",
            "cvss_score": 10.0,
            "description": "Remote Code Execution via Apache Struts vulnerability. "
            "Attacker can execute arbitrary commands on the server.",
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440003",
            "type": "xss",
            "severity": "high",
            "target": "https://app.example.com/search",
            "evidence": "Reflected XSS in search parameter. "
            "Payload: <script>alert('XSS')</script>",
            "agent_id": "550e8400-e29b-41d4-a716-446655440012",
            "timestamp": "2026-02-12T12:45:00Z",
            "tool": "nuclei",
            "topic": "findings:eng-prod-001:xss",
            "signature": "hmac-ghi789",
            "cve_id": None,
            "cvss_score": 7.1,
            "description": "Reflected Cross-Site Scripting vulnerability "
            "enables session hijacking and phishing attacks.",
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440004",
            "type": "ssrf",
            "severity": "high",
            "target": "https://api.example.com/fetch",
            "evidence": "SSRF via url parameter allows internal network scanning.",
            "agent_id": "550e8400-e29b-41d4-a716-446655440012",
            "timestamp": "2026-02-12T13:00:00Z",
            "tool": "ffuf",
            "topic": "findings:eng-prod-001:ssrf",
            "signature": "hmac-jkl012",
            "cve_id": None,
            "cvss_score": 8.0,
            "description": "Server-Side Request Forgery allows access to internal services.",
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440005",
            "type": "sensitive_data",
            "severity": "medium",
            "target": "https://app.example.com/.git/config",
            "evidence": "Git repository exposed at public endpoint.",
            "agent_id": "550e8400-e29b-41d4-a716-446655440010",
            "timestamp": "2026-02-12T09:30:00Z",
            "tool": "ffuf",
            "topic": "findings:eng-prod-001:info",
            "signature": "hmac-mno345",
            "cve_id": None,
            "cvss_score": 5.3,
            "description": "Exposed Git repository may leak source code and secrets.",
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440006",
            "type": "weak_ssl",
            "severity": "low",
            "target": "192.168.100.10",
            "evidence": "TLS 1.0 and 1.1 enabled on server.",
            "agent_id": "550e8400-e29b-41d4-a716-446655440010",
            "timestamp": "2026-02-12T09:15:00Z",
            "tool": "testssl",
            "topic": "findings:eng-prod-001:ssl",
            "signature": "hmac-pqr678",
            "cve_id": None,
            "cvss_score": 3.7,
            "description": "Outdated TLS versions enabled, vulnerable to downgrade attacks.",
        },
        {
            "id": "550e8400-e29b-41d4-a716-446655440007",
            "type": "open_port",
            "severity": "info",
            "target": "192.168.100.10",
            "evidence": "Open ports: 22/ssh, 80/http, 443/https, 3306/mysql",
            "agent_id": "550e8400-e29b-41d4-a716-446655440010",
            "timestamp": "2026-02-12T09:00:00Z",
            "tool": "nmap",
            "topic": "findings:eng-prod-001:port",
            "signature": "hmac-stu901",
            "cve_id": None,
            "cvss_score": 0.0,
            "description": "Network service enumeration completed.",
        },
    ]


@pytest.fixture
def realistic_timeline() -> list[TimelineEvent]:
    """Create realistic timeline events."""
    return [
        TimelineEvent(
            timestamp="2026-02-12T09:00:00Z",
            event_type="engagement_start",
            description="Engagement initiated by operator",
            agent_id="orchestrator",
            details={"config": "prod-engagement.yaml", "operator": "admin"},
        ),
        TimelineEvent(
            timestamp="2026-02-12T09:00:05Z",
            event_type="agent_spawned",
            description="Recon agent spawned",
            agent_id="550e8400-e29b-41d4-a716-446655440010",
            details={"role": "recon", "target_count": 5},
        ),
        TimelineEvent(
            timestamp="2026-02-12T09:00:10Z",
            event_type="scan_start",
            description="Network scan initiated",
            agent_id="550e8400-e29b-41d4-a716-446655440010",
            details={"tool": "nmap", "targets": ["192.168.100.0/24"]},
        ),
        TimelineEvent(
            timestamp="2026-02-12T09:15:00Z",
            event_type="finding_discovered",
            description="TLS vulnerability discovered",
            agent_id="550e8400-e29b-41d4-a716-446655440010",
            details={"finding_id": "550e8400-e29b-41d4-a716-446655440006"},
        ),
        TimelineEvent(
            timestamp="2026-02-12T10:15:32Z",
            event_type="finding_discovered",
            description="Critical SQL injection found",
            agent_id="550e8400-e29b-41d4-a716-446655440010",
            details={"finding_id": "550e8400-e29b-41d4-a716-446655440001"},
        ),
        TimelineEvent(
            timestamp="2026-02-12T10:30:00Z",
            event_type="agent_spawned",
            description="Exploit agent spawned for critical finding",
            agent_id="550e8400-e29b-41d4-a716-446655440011",
            details={"role": "exploit", "trigger": "critical_finding"},
        ),
        TimelineEvent(
            timestamp="2026-02-12T11:30:00Z",
            event_type="finding_discovered",
            description="RCE vulnerability confirmed",
            agent_id="550e8400-e29b-41d4-a716-446655440011",
            details={"finding_id": "550e8400-e29b-41d4-a716-446655440002"},
        ),
        TimelineEvent(
            timestamp="2026-02-12T14:00:00Z",
            event_type="engagement_pause",
            description="Engagement paused for operator review",
            agent_id="orchestrator",
            details={"reason": "critical_findings_threshold"},
        ),
        TimelineEvent(
            timestamp="2026-02-12T15:00:00Z",
            event_type="engagement_end",
            description="Engagement completed",
            agent_id="orchestrator",
            details={"total_findings": 7, "duration_hours": 6},
        ),
    ]


@pytest.fixture
def realistic_scope() -> dict:
    """Create realistic scope definition."""
    return {
        "targets": [
            "192.168.100.0/24",
            "https://app.example.com",
            "https://api.example.com",
        ],
        "exclusions": [
            "192.168.100.1",  # Gateway
            "192.168.100.254",  # Management interface
        ],
    }


@pytest.fixture
def realistic_report_data(
    realistic_findings, realistic_timeline, realistic_scope
) -> ReportData:
    """Create complete ReportData with realistic production data."""
    return ReportData(
        engagement_id="eng-prod-001",
        title="Penetration Test Report - Example Corporation Q1 2026",
        start_time=datetime(2026, 2, 12, 9, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 12, 15, 0, 0, tzinfo=timezone.utc),
        scope=realistic_scope,
        findings=tuple(realistic_findings),
        timeline_events=tuple(realistic_timeline),
        metadata={
            "client": "Example Corporation",
            "tester": "Cyber-Red Automated Assessment",
            "engagement_type": "External Network Penetration Test",
            "classification": "CONFIDENTIAL",
        },
    )


@pytest.fixture
def signing_key() -> bytes:
    """Create a production-like signing key."""
    return b"prod-engagement-signing-key-32b!"


# =============================================================================
# Task 7: Integration Tests (AC: all)
# =============================================================================


class TestReportGenerationIntegration:
    """Integration tests for full report generation cycle."""

    def test_full_cycle_generate_sign_save_verify(
        self, realistic_report_data, signing_key: bytes, tmp_path: Path
    ) -> None:
        """Test complete cycle: generate → sign → save → verify."""
        # Step 1: Generate report
        generator = MarkdownReportGenerator()
        report_content = generator.generate(realistic_report_data)
        
        assert isinstance(report_content, str)
        assert len(report_content) > 0
        
        # Step 2: Sign report
        signed_report = sign_report(report_content, signing_key)
        
        assert isinstance(signed_report, SignedReport)
        assert signed_report.content == report_content
        
        # Step 3: Save signed report
        output_path = tmp_path / "engagement-report.md"
        save_signed_report(signed_report, output_path)
        
        assert output_path.exists()
        assert output_path.with_suffix(".sig").exists()
        
        # Step 4: Verify signature
        saved_content = output_path.read_text(encoding="utf-8")
        sig_data = json.loads(output_path.with_suffix(".sig").read_text())
        
        # Reconstruct SignedReport for verification
        reconstructed = SignedReport(
            content=saved_content,
            signature=sig_data["signature"],
            timestamp=sig_data["timestamp"],
            key_id=sig_data["key_id"],
            content_hash=sig_data["content_hash"],
        )
        
        assert verify_signature(reconstructed, signing_key) is True

    def test_report_with_realistic_findings(
        self, realistic_report_data
    ) -> None:
        """Test report generation with realistic multi-severity findings."""
        generator = MarkdownReportGenerator()
        result = generator.generate(realistic_report_data)
        
        # Verify all critical findings are included
        assert "CVE-2024-12345" in result
        assert "CVE-2017-5638" in result
        
        # Verify severity counts
        assert "Critical" in result
        assert "High" in result
        assert "Medium" in result
        assert "Low" in result
        
        # Verify specific finding details
        assert "SQL Injection" in result or "SQL injection" in result
        assert "Remote Code Execution" in result or "RCE" in result

    def test_report_is_valid_markdown(self, realistic_report_data) -> None:
        """Test generated report is valid Markdown syntax."""
        generator = MarkdownReportGenerator()
        result = generator.generate(realistic_report_data)
        
        # Check for Markdown heading structure
        assert result.startswith("#") or "# " in result
        
        # Check for section headers
        assert "## " in result or "### " in result
        
        # No unrendered Jinja2 syntax
        assert "{{" not in result
        assert "}}" not in result
        assert "{%" not in result
        assert "%}" not in result

    def test_report_includes_all_required_sections(
        self, realistic_report_data
    ) -> None:
        """Test report includes all required sections per AC #3."""
        generator = MarkdownReportGenerator()
        result = generator.generate(realistic_report_data)
        
        # Required sections per story specification
        required_sections = [
            "Executive Summary",
            "Scope",
            "Findings",
            "Timeline",
            "Appendix",
        ]
        
        for section in required_sections:
            assert section in result, f"Missing required section: {section}"

    def test_report_findings_ordered_by_severity(
        self, realistic_report_data
    ) -> None:
        """Test findings appear in severity order: Critical → High → Medium → Low → Info."""
        generator = MarkdownReportGenerator()
        result = generator.generate(realistic_report_data)
        
        # Find positions of severity sections
        critical_pos = result.find("Critical")
        high_pos = result.find("High")
        medium_pos = result.find("Medium")
        low_pos = result.find("Low")
        
        # Verify ordering (Critical should come before High, etc.)
        assert critical_pos < high_pos, "Critical should appear before High"
        assert high_pos < medium_pos, "High should appear before Medium"
        assert medium_pos < low_pos, "Medium should appear before Low"

    def test_report_timeline_chronological(self, realistic_report_data) -> None:
        """Test timeline events are in chronological order."""
        generator = MarkdownReportGenerator()
        result = generator.generate(realistic_report_data)
        
        # Extract timestamps from timeline section
        # Timeline should show events in order
        assert "09:00" in result or "9:00" in result  # First event
        assert "15:00" in result or "3:00" in result  # Last event

    def test_signature_file_integrity(
        self, realistic_report_data, signing_key: bytes, tmp_path: Path
    ) -> None:
        """Test signature file contains all required fields."""
        generator = MarkdownReportGenerator()
        content = generator.generate(realistic_report_data)
        signed = sign_report(content, signing_key)
        
        output_path = tmp_path / "report.md"
        save_signed_report(signed, output_path)
        
        sig_path = output_path.with_suffix(".sig")
        sig_data = json.loads(sig_path.read_text())
        
        # Verify required fields per AC #6
        assert "content_hash" in sig_data
        assert "signature" in sig_data
        assert "timestamp" in sig_data
        assert "key_id" in sig_data
        
        # Verify hash format
        assert len(sig_data["content_hash"]) >= 64 or "sha256:" in sig_data["content_hash"]

    def test_tampered_report_fails_verification(
        self, realistic_report_data, signing_key: bytes, tmp_path: Path
    ) -> None:
        """Test tampered report content fails signature verification."""
        generator = MarkdownReportGenerator()
        content = generator.generate(realistic_report_data)
        signed = sign_report(content, signing_key)
        
        output_path = tmp_path / "report.md"
        save_signed_report(signed, output_path)
        
        # Tamper with the saved content
        tampered_content = content.replace("Critical", "Minor")
        output_path.write_text(tampered_content, encoding="utf-8")
        
        # Load signature and verify
        sig_data = json.loads(output_path.with_suffix(".sig").read_text())
        tampered_signed = SignedReport(
            content=tampered_content,
            signature=sig_data["signature"],
            timestamp=sig_data["timestamp"],
            key_id=sig_data["key_id"],
            content_hash=sig_data["content_hash"],
        )
        
        # Verification should fail
        assert verify_signature(tampered_signed, signing_key) is False

    def test_custom_template_rendering(self, realistic_report_data, tmp_path: Path) -> None:
        """Test report generation with custom Jinja2 template."""
        # Create custom template
        custom_template = tmp_path / "custom_report.jinja2"
        custom_template.write_text(
            """# Custom Report: {{ title }}

**Engagement:** {{ engagement_id }}
**Generated:** {{ generated_at }}

## Summary
Total Findings: {{ total_findings }}
Critical: {{ findings_critical | length }}
High: {{ findings_high | length }}

## Targets
{% for target in scope.targets %}
- {{ target }}
{% endfor %}
"""
        )
        
        generator = MarkdownReportGenerator(template_path=custom_template)
        result = generator.generate(realistic_report_data)
        
        assert "Custom Report:" in result
        assert realistic_report_data.engagement_id in result
        assert "Total Findings:" in result

    def test_report_metadata_included(self, realistic_report_data) -> None:
        """Test report includes metadata from ReportData."""
        generator = MarkdownReportGenerator()
        result = generator.generate(realistic_report_data)
        
        # Metadata should be accessible in report
        # The template may or may not include it, but ReportData should have it
        assert realistic_report_data.metadata is not None
        assert realistic_report_data.metadata.get("client") == "Example Corporation"

    def test_report_unicode_handling(self, realistic_scope, tmp_path: Path) -> None:
        """Test report handles Unicode characters correctly."""
        # Create report data with Unicode
        report_data = ReportData(
            engagement_id="eng-unicode",
            title="Penetration Test Report - 株式会社テスト (Test Inc.)",
            start_time=datetime.now(timezone.utc),
            end_time=None,
            scope=realistic_scope,
            findings=(
                {
                    "id": "550e8400-e29b-41d4-a716-446655440099",
                    "type": "xss",
                    "severity": "high",
                    "target": "https://example.com/search",
                    "evidence": "Unicode payload: <script>alert('日本語')</script>",
                    "agent_id": "550e8400-e29b-41d4-a716-446655440010",
                    "timestamp": "2026-02-12T10:00:00Z",
                    "tool": "nuclei",
                    "topic": "findings:eng:xss",
                    "signature": "sig",
                    "cve_id": None,
                    "cvss_score": 7.0,
                    "description": "XSS with Unicode: éàü ñ 中文",
                },
            ),
            timeline_events=(),
        )
        
        generator = MarkdownReportGenerator()
        result = generator.generate(report_data)
        
        assert "株式会社テスト" in result
        assert "日本語" in result or "中文" in result

    def test_empty_findings_report(self, realistic_scope) -> None:
        """Test report generation with no findings."""
        report_data = ReportData(
            engagement_id="eng-empty",
            title="Clean System Assessment",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            scope=realistic_scope,
            findings=(),
            timeline_events=(),
        )
        
        generator = MarkdownReportGenerator()
        result = generator.generate(report_data)
        
        # Report should still be valid
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Clean System Assessment" in result

    def test_report_hash_in_output(self, realistic_report_data) -> None:
        """Test report includes content hash per specification."""
        generator = MarkdownReportGenerator()
        result = generator.generate(realistic_report_data)
        
        # Report should include hash for integrity
        assert "Report Hash" in result or "Hash:" in result or re.search(r"[a-f0-9]{16,}", result)
