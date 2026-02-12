"""Integration tests for HTML Report Generator (Story 13.5).

Tests full report generation cycle with real Jinja2 rendering,
actual image files, and HTML validation.
"""

from __future__ import annotations

import base64
import html.parser
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cyberred.storage.report_generator import ReportData, TimelineEvent


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def realistic_report_data() -> ReportData:
    """Create realistic report data for integration testing."""
    return ReportData(
        engagement_id="eng-2024-001",
        title="Security Assessment Report - Acme Corp",
        start_time=datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2024, 1, 16, 17, 0, 0, tzinfo=timezone.utc),
        scope={
            "targets": [
                "192.168.1.0/24",
                "10.0.0.0/8",
                "webapp.acme.local",
                "api.acme.local",
            ],
            "exclusions": ["192.168.1.1", "192.168.1.254"],
        },
        findings=(
            {
                "id": "FIND-001",
                "severity": "critical",
                "title": "SQL Injection in User Login",
                "description": "The login form is vulnerable to SQL injection attacks. "
                "An attacker can bypass authentication using payload: ' OR '1'='1",
                "target": "webapp.acme.local/login",
                "tool": "sqlmap",
                "evidence": "screenshot_sqli.png",
                "remediation": "Use parameterized queries for all database operations.",
            },
            {
                "id": "FIND-002",
                "severity": "critical",
                "title": "Remote Code Execution via Deserialization",
                "description": "The API endpoint /api/import accepts serialized Java objects "
                "without validation, enabling RCE.",
                "target": "api.acme.local/api/import",
                "tool": "nuclei",
                "evidence": "screenshot_rce.png",
                "remediation": "Disable Java deserialization or use safe alternatives.",
            },
            {
                "id": "FIND-003",
                "severity": "high",
                "title": "Cross-Site Scripting (XSS)",
                "description": "Reflected XSS in the search functionality allows script injection.",
                "target": "webapp.acme.local/search",
                "tool": "nuclei",
                "evidence": "screenshot_xss.png",
                "remediation": "Implement proper output encoding and CSP headers.",
            },
            {
                "id": "FIND-004",
                "severity": "high",
                "title": "Weak SSH Configuration",
                "description": "SSH server allows weak algorithms and password authentication.",
                "target": "192.168.1.10:22",
                "tool": "nmap",
                "remediation": "Disable password auth, use key-based authentication.",
            },
            {
                "id": "FIND-005",
                "severity": "medium",
                "title": "Missing Security Headers",
                "description": "Multiple security headers are missing: X-Frame-Options, "
                "X-Content-Type-Options, Strict-Transport-Security.",
                "target": "webapp.acme.local",
                "tool": "nikto",
                "remediation": "Configure web server to include security headers.",
            },
            {
                "id": "FIND-006",
                "severity": "low",
                "title": "Server Version Disclosure",
                "description": "The server reveals version information in HTTP headers.",
                "target": "webapp.acme.local",
                "tool": "nikto",
                "remediation": "Remove or obfuscate server version headers.",
            },
            {
                "id": "FIND-007",
                "severity": "info",
                "title": "Open Ports Detected",
                "description": "Standard ports found open: 22 (SSH), 80 (HTTP), 443 (HTTPS).",
                "target": "192.168.1.10",
                "tool": "nmap",
            },
        ),
        timeline_events=(
            TimelineEvent(
                timestamp="2024-01-15T09:00:00Z",
                event_type="engagement_start",
                description="Engagement initiated",
                agent_id="system",
            ),
            TimelineEvent(
                timestamp="2024-01-15T09:15:00Z",
                event_type="recon_start",
                description="Reconnaissance phase started",
                agent_id="recon-agent-001",
            ),
            TimelineEvent(
                timestamp="2024-01-15T10:30:00Z",
                event_type="finding_discovered",
                description="SQL Injection vulnerability discovered",
                agent_id="exploit-agent-001",
            ),
            TimelineEvent(
                timestamp="2024-01-15T14:00:00Z",
                event_type="finding_discovered",
                description="RCE vulnerability discovered",
                agent_id="exploit-agent-002",
            ),
            TimelineEvent(
                timestamp="2024-01-16T16:00:00Z",
                event_type="report_generation",
                description="Report generation started",
                agent_id="system",
            ),
            TimelineEvent(
                timestamp="2024-01-16T17:00:00Z",
                event_type="engagement_end",
                description="Engagement completed",
                agent_id="system",
            ),
        ),
        metadata={
            "operator": "security-team",
            "client": "Acme Corp",
            "assessment_type": "Penetration Test",
        },
    )


@pytest.fixture
def evidence_dir_with_images(tmp_path: Path) -> Path:
    """Create evidence directory with test images."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    # Create minimal valid PNG images
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )

    # Create screenshot files
    (evidence_dir / "screenshot_sqli.png").write_bytes(png_data)
    (evidence_dir / "screenshot_rce.png").write_bytes(png_data)
    (evidence_dir / "screenshot_xss.png").write_bytes(png_data)

    return evidence_dir


class SimpleHTMLValidator(html.parser.HTMLParser):
    """Simple HTML validator to check structure."""

    def __init__(self):
        super().__init__()
        self.tags = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)

    def handle_endtag(self, tag):
        if tag in self.tags:
            self.tags.remove(tag)

    def is_valid(self) -> bool:
        """Check if HTML is basically valid."""
        return len(self.errors) == 0


# =============================================================================
# Integration Tests (AC: all)
# =============================================================================


class TestHTMLReportGeneratorIntegration:
    """Integration tests for HTMLReportGenerator."""

    def test_full_generation_cycle(self, realistic_report_data: ReportData, tmp_path: Path):
        """Test full cycle: create report data → generate HTML → save."""
        from cyberred.storage.report_generator import HTMLReportGenerator, save_report

        # Generate HTML report
        generator = HTMLReportGenerator()
        html_content = generator.generate(realistic_report_data)

        # Save report
        output_path = tmp_path / "report.html"
        save_report(html_content, output_path)

        # Verify file was created
        assert output_path.exists()

        # Verify content was saved correctly
        saved_content = output_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in saved_content
        assert realistic_report_data.title in saved_content

    def test_html_with_embedded_screenshots(
        self,
        realistic_report_data: ReportData,
        evidence_dir_with_images: Path,
        tmp_path: Path,
    ):
        """Test HTML generation with embedded screenshots."""
        from cyberred.storage.report_generator import (
            HTMLReportGenerator,
            embed_screenshots_in_html,
        )

        # Generate HTML report
        generator = HTMLReportGenerator()
        html_content = generator.generate(realistic_report_data)

        # Add image references for testing
        html_with_images = html_content.replace(
            "</body>",
            '<img src="screenshot_sqli.png" alt="SQL Injection Evidence"></body>',
        )

        # Embed screenshots
        result = embed_screenshots_in_html(html_with_images, evidence_dir_with_images)

        # Verify images are embedded
        assert "data:image/png;base64," in result
        assert 'src="screenshot_sqli.png"' not in result

    def test_html_is_parseable(self, realistic_report_data: ReportData):
        """Test generated HTML is parseable by standard library."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        html_content = generator.generate(realistic_report_data)

        # Parse with standard library HTML parser
        validator = SimpleHTMLValidator()
        try:
            validator.feed(html_content)
            is_parseable = True
        except Exception:
            is_parseable = False

        assert is_parseable

    def test_html_renders_correctly_with_realistic_data(
        self, realistic_report_data: ReportData
    ):
        """Test HTML renders correctly with realistic finding data."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        html_content = generator.generate(realistic_report_data)

        # Check all findings are rendered
        assert "SQL Injection in User Login" in html_content
        assert "Remote Code Execution" in html_content
        assert "Cross-Site Scripting" in html_content

        # Check severity indicators
        assert "critical" in html_content.lower()
        assert "high" in html_content.lower()
        assert "medium" in html_content.lower()

        # Check timeline events
        assert "engagement_start" in html_content or "Engagement initiated" in html_content

        # Check metadata
        assert realistic_report_data.engagement_id in html_content

    def test_html_file_size_is_reasonable(self, realistic_report_data: ReportData):
        """Test HTML file size is reasonable (< 10MB for typical report)."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        html_content = generator.generate(realistic_report_data)

        # Convert to bytes to get actual size
        content_bytes = html_content.encode("utf-8")
        size_mb = len(content_bytes) / (1024 * 1024)

        # Should be well under 10MB for a typical report without images
        assert size_mb < 1.0, f"Report size {size_mb:.2f}MB exceeds expected limit"

    def test_html_with_large_embedded_images(
        self, realistic_report_data: ReportData, tmp_path: Path
    ):
        """Test HTML generation with larger embedded images stays reasonable."""
        from cyberred.storage.report_generator import (
            HTMLReportGenerator,
            embed_screenshots_in_html,
        )

        # Create a larger but still reasonable test image (~50KB)
        # This is a placeholder - real images would be screenshots
        large_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50000

        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir()
        (evidence_dir / "large_screenshot.png").write_bytes(large_png)

        generator = HTMLReportGenerator()
        html_content = generator.generate(realistic_report_data)

        # Add image reference
        html_with_image = html_content.replace(
            "</body>", '<img src="large_screenshot.png"></body>'
        )

        # This should work (we test it doesn't crash with larger images)
        # Note: Invalid PNG data will cause embed to keep original src
        result = embed_screenshots_in_html(html_with_image, evidence_dir)
        
        # Result should still be valid HTML
        assert "<!DOCTYPE html>" in result

    def test_generate_with_evidence_dir_parameter(
        self,
        realistic_report_data: ReportData,
        evidence_dir_with_images: Path,
    ):
        """Test generate method with evidence_dir parameter."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        
        # If the implementation supports evidence_dir in generate()
        # This tests that integration
        html_content = generator.generate(
            realistic_report_data,
            evidence_dir=evidence_dir_with_images,
        )

        assert isinstance(html_content, str)
        assert "<!DOCTYPE html>" in html_content


class TestHTMLReportSigningIntegration:
    """Integration tests for HTML report signing."""

    def test_sign_html_report(self, realistic_report_data: ReportData):
        """Test signing an HTML report."""
        from cyberred.storage.report_generator import (
            HTMLReportGenerator,
            sign_report,
            verify_signature,
        )

        # Generate HTML
        generator = HTMLReportGenerator()
        html_content = generator.generate(realistic_report_data)

        # Sign the report
        signing_key = b"test-signing-key-32-bytes-long!!"
        signed = sign_report(html_content, signing_key)

        # Verify signature
        assert verify_signature(signed, signing_key)

        # Verify content wasn't modified
        assert signed.content == html_content

    def test_save_signed_html_report(
        self, realistic_report_data: ReportData, tmp_path: Path
    ):
        """Test saving a signed HTML report."""
        from cyberred.storage.report_generator import (
            HTMLReportGenerator,
            sign_report,
            save_signed_report,
        )

        # Generate and sign
        generator = HTMLReportGenerator()
        html_content = generator.generate(realistic_report_data)
        signing_key = b"test-signing-key-32-bytes-long!!"
        signed = sign_report(html_content, signing_key)

        # Save
        output_path = tmp_path / "report.html"
        save_signed_report(signed, output_path)

        # Verify files exist
        assert output_path.exists()
        assert output_path.with_suffix(".sig").exists()

        # Verify content
        saved_content = output_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in saved_content
