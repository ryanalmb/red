"""Unit tests for HTML Report Generator (Story 13.5).

Tests HTMLReportGenerator, screenshot embedding, dark theme styling,
and self-contained HTML validation.
"""

from __future__ import annotations

import base64
import re
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
def sample_report_data():
    """Create sample ReportData for testing."""
    from cyberred.storage.report_generator import ReportData, TimelineEvent

    return ReportData(
        engagement_id="test-engagement-001",
        title="Test Penetration Test Report",
        start_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc),
        scope={
            "targets": ["192.168.1.0/24", "10.0.0.0/8"],
            "exclusions": ["192.168.1.1"],
        },
        findings=(
            {
                "id": "FIND-001",
                "severity": "critical",
                "title": "SQL Injection",
                "description": "SQL injection in login form",
                "target": "192.168.1.10",
                "tool": "sqlmap",
            },
            {
                "id": "FIND-002",
                "severity": "high",
                "title": "XSS Vulnerability",
                "description": "Reflected XSS in search",
                "target": "192.168.1.10",
                "tool": "nuclei",
            },
            {
                "id": "FIND-003",
                "severity": "medium",
                "title": "Missing Headers",
                "description": "Missing security headers",
                "target": "192.168.1.10",
                "tool": "nikto",
            },
            {
                "id": "FIND-004",
                "severity": "low",
                "title": "Information Disclosure",
                "description": "Server version exposed",
                "target": "192.168.1.10",
                "tool": "nmap",
            },
            {
                "id": "FIND-005",
                "severity": "info",
                "title": "Open Port",
                "description": "Port 22 SSH open",
                "target": "192.168.1.10",
                "tool": "nmap",
            },
        ),
        timeline_events=(
            TimelineEvent(
                timestamp="2024-01-15T10:00:00Z",
                event_type="engagement_start",
                description="Engagement started",
                agent_id="recon-agent-001",
            ),
            TimelineEvent(
                timestamp="2024-01-15T11:30:00Z",
                event_type="finding_discovered",
                description="Critical SQL injection found",
                agent_id="exploit-agent-001",
            ),
        ),
        metadata={"operator": "test-operator"},
    )


@pytest.fixture
def temp_image_dir(tmp_path: Path) -> Path:
    """Create temp directory with test images."""
    # Create a minimal valid PNG (1x1 red pixel)
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )
    
    # Create a minimal valid JPEG
    jpeg_data = base64.b64decode(
        "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
        "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFgAB"
        "AQAAAAAAAAAAAAAAAAAAAAL/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAA/AL//2Q=="
    )
    
    # Create a minimal valid GIF
    gif_data = base64.b64decode(
        "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
    )
    
    # Save test images
    (tmp_path / "screenshot.png").write_bytes(png_data)
    (tmp_path / "evidence.jpg").write_bytes(jpeg_data)
    (tmp_path / "animation.gif").write_bytes(gif_data)
    
    return tmp_path


# =============================================================================
# Task 2: HTMLReportGenerator Tests (AC: #2, #3, #6)
# =============================================================================


class TestHTMLReportGeneratorInit:
    """Test HTMLReportGenerator initialization."""

    def test_init_loads_default_template(self):
        """Test __init__ with no arguments loads default template."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        assert generator.template is not None
        assert generator.template_path.name == "report_html.jinja2"

    def test_init_loads_custom_template(self, tmp_path: Path):
        """Test __init__ with custom template path loads that template."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        # Create custom template
        custom_template = tmp_path / "custom.jinja2"
        custom_template.write_text("<!DOCTYPE html><html><body>{{ title }}</body></html>")

        generator = HTMLReportGenerator(template_path=custom_template)
        assert generator.template is not None
        assert generator.template_path == custom_template

    def test_init_raises_file_not_found_for_missing_template(self):
        """Test __init__ raises FileNotFoundError for missing template."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        with pytest.raises(FileNotFoundError, match="Template not found"):
            HTMLReportGenerator(template_path=Path("/nonexistent/template.jinja2"))


class TestHTMLReportGeneratorGenerate:
    """Test HTMLReportGenerator.generate() method."""

    def test_generate_returns_html_string(self, sample_report_data):
        """Test generate() returns HTML string."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_generated_html_contains_doctype(self, sample_report_data):
        """Test generated HTML contains DOCTYPE declaration."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        assert "<!DOCTYPE html>" in result

    def test_generated_html_contains_html_tag(self, sample_report_data):
        """Test generated HTML contains <html> tag."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        assert "<html" in result
        assert "</html>" in result

    def test_generated_html_contains_body_tag(self, sample_report_data):
        """Test generated HTML contains <body> tag."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        assert "<body>" in result or "<body " in result
        assert "</body>" in result

    def test_generated_html_contains_all_sections(self, sample_report_data):
        """Test generated HTML contains all Markdown report sections."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        # Check for key sections
        assert "executive-summary" in result.lower() or "executive summary" in result.lower()
        assert "scope" in result.lower()
        assert "findings" in result.lower()
        assert "timeline" in result.lower()
        assert "appendix" in result.lower()


# =============================================================================
# Task 3: Screenshot Embedding Tests (AC: #4)
# =============================================================================


class TestEmbedScreenshot:
    """Test embed_screenshot function."""

    def test_embed_png_returns_base64_data_uri(self, temp_image_dir: Path):
        """Test PNG embedding returns base64 data URI."""
        from cyberred.storage.report_generator import embed_screenshot

        result = embed_screenshot(temp_image_dir / "screenshot.png")

        assert result.startswith("data:image/png;base64,")
        # Verify it's valid base64
        b64_part = result.split(",")[1]
        decoded = base64.b64decode(b64_part)
        assert len(decoded) > 0

    def test_embed_jpeg_returns_base64_data_uri(self, temp_image_dir: Path):
        """Test JPEG embedding returns base64 data URI."""
        from cyberred.storage.report_generator import embed_screenshot

        result = embed_screenshot(temp_image_dir / "evidence.jpg")

        assert result.startswith("data:image/jpeg;base64,")

    def test_embed_gif_returns_base64_data_uri(self, temp_image_dir: Path):
        """Test GIF embedding returns base64 data URI."""
        from cyberred.storage.report_generator import embed_screenshot

        result = embed_screenshot(temp_image_dir / "animation.gif")

        assert result.startswith("data:image/gif;base64,")

    def test_embed_nonexistent_raises_file_not_found(self):
        """Test embedding non-existent image raises FileNotFoundError."""
        from cyberred.storage.report_generator import embed_screenshot

        with pytest.raises(FileNotFoundError, match="Image not found"):
            embed_screenshot(Path("/nonexistent/image.png"))

    def test_embed_unsupported_format_raises_value_error(self, tmp_path: Path):
        """Test embedding unsupported format raises ValueError."""
        from cyberred.storage.report_generator import embed_screenshot

        # Create a file with unsupported extension
        unsupported = tmp_path / "image.bmp"
        unsupported.write_bytes(b"fake image data")

        with pytest.raises(ValueError, match="Unsupported image format"):
            embed_screenshot(unsupported)


class TestEmbedScreenshotsInHtml:
    """Test embed_screenshots_in_html function."""

    def test_replaces_img_src_with_base64(self, temp_image_dir: Path):
        """Test function replaces img src with base64 data URI."""
        from cyberred.storage.report_generator import embed_screenshots_in_html

        html = '<img src="screenshot.png" alt="test">'
        result = embed_screenshots_in_html(html, temp_image_dir)

        assert "data:image/png;base64," in result
        assert 'src="screenshot.png"' not in result

    def test_handles_multiple_images(self, temp_image_dir: Path):
        """Test function handles multiple images."""
        from cyberred.storage.report_generator import embed_screenshots_in_html

        html = '<img src="screenshot.png"><img src="evidence.jpg">'
        result = embed_screenshots_in_html(html, temp_image_dir)

        assert "data:image/png;base64," in result
        assert "data:image/jpeg;base64," in result

    def test_skips_already_embedded_images(self, temp_image_dir: Path):
        """Test function skips already embedded images."""
        from cyberred.storage.report_generator import embed_screenshots_in_html

        existing_data_uri = "data:image/png;base64,existingdata"
        html = f'<img src="{existing_data_uri}">'
        result = embed_screenshots_in_html(html, temp_image_dir)

        assert existing_data_uri in result

    def test_keeps_original_if_image_not_found(self, temp_image_dir: Path):
        """Test function keeps original src if image not found."""
        from cyberred.storage.report_generator import embed_screenshots_in_html

        html = '<img src="nonexistent.png">'
        result = embed_screenshots_in_html(html, temp_image_dir)

        assert 'src="nonexistent.png"' in result


# =============================================================================
# Task 4: Dark Theme Styling Tests (AC: #5)
# =============================================================================


class TestDarkThemeStyling:
    """Test dark theme CSS in generated HTML."""

    def test_html_includes_style_block(self, sample_report_data):
        """Test HTML includes <style> block in <head>."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        assert "<style>" in result
        assert "</style>" in result

    def test_css_contains_dark_background(self, sample_report_data):
        """Test CSS contains dark theme background color."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        # Check for dark background colors (hex format)
        assert re.search(r"#1e1e1e|#252526|#2d2d2d", result, re.IGNORECASE)

    def test_css_styles_code_blocks(self, sample_report_data):
        """Test CSS styles code blocks appropriately."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        # Check for code/pre styling
        assert "code" in result.lower()
        assert "monospace" in result.lower()

    def test_css_is_embedded_no_external_stylesheet(self, sample_report_data):
        """Test CSS is embedded (no external stylesheet links)."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        # Should NOT have external stylesheet links
        assert 'rel="stylesheet"' not in result or 'href="http' not in result


# =============================================================================
# Task 5: Self-Contained HTML Tests (AC: #6)
# =============================================================================


class TestSelfContainedHtml:
    """Test HTML is self-contained."""

    def test_no_external_stylesheet_links(self, sample_report_data):
        """Test generated HTML has no external stylesheet links."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        # Check for external CSS links
        external_css = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']https?:', result)
        assert len(external_css) == 0

    def test_no_external_script_references(self, sample_report_data):
        """Test generated HTML has no external script references."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        # Check for external script sources
        external_scripts = re.findall(r'<script[^>]+src=["\']https?:', result)
        assert len(external_scripts) == 0

    def test_html_can_be_saved_and_read(self, sample_report_data, tmp_path: Path):
        """Test HTML can be saved and read back."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        # Save to file
        output_file = tmp_path / "report.html"
        output_file.write_text(result, encoding="utf-8")

        # Read back
        content = output_file.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content


# =============================================================================
# Task 6: HTML Structure Tests (AC: #3)
# =============================================================================


class TestHTMLStructure:
    """Test HTML structure matches expected sections."""

    def test_html_contains_executive_summary_section(self, sample_report_data):
        """Test HTML contains executive summary section."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        assert 'id="executive-summary"' in result or "Executive Summary" in result

    def test_html_contains_scope_section(self, sample_report_data):
        """Test HTML contains scope section with targets and exclusions."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        assert 'id="scope"' in result or "Scope" in result
        # Check targets are listed
        assert "192.168.1.0/24" in result
        assert "10.0.0.0/8" in result
        # Check exclusions
        assert "192.168.1.1" in result

    def test_html_contains_findings_grouped_by_severity(self, sample_report_data):
        """Test HTML contains findings grouped by severity."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        # Check severity groupings exist
        assert "critical" in result.lower()
        assert "high" in result.lower()
        assert "medium" in result.lower()
        assert "low" in result.lower()
        # Check finding titles
        assert "SQL Injection" in result

    def test_html_contains_timeline_table(self, sample_report_data):
        """Test HTML contains timeline as HTML table."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        assert 'id="timeline"' in result or "Timeline" in result
        assert "<table" in result
        assert "engagement_start" in result or "Engagement started" in result

    def test_html_contains_appendix(self, sample_report_data):
        """Test HTML contains appendix with tool and agent summaries."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        assert 'id="appendix"' in result or "Appendix" in result

    def test_html_contains_report_hash_in_footer(self, sample_report_data):
        """Test HTML contains report hash in footer."""
        from cyberred.storage.report_generator import HTMLReportGenerator

        generator = HTMLReportGenerator()
        result = generator.generate(sample_report_data)

        # Check for footer with hash
        assert "<footer" in result
        assert "report" in result.lower() and "hash" in result.lower()


# =============================================================================
# Additional Edge Case Tests for 100% Coverage
# =============================================================================


class TestHTMLReportGeneratorEdgeCases:
    """Edge case tests for HTMLReportGenerator."""

    def test_generate_with_ongoing_engagement(self):
        """Test HTML generation with ongoing engagement (no end_time)."""
        from cyberred.storage.report_generator import (
            HTMLReportGenerator,
            ReportData,
            TimelineEvent,
        )

        report_data = ReportData(
            engagement_id="test-ongoing-001",
            title="Ongoing Test Report",
            start_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            end_time=None,  # Ongoing
            scope={"targets": ["192.168.1.0/24"], "exclusions": []},
            findings=(),
            timeline_events=(
                TimelineEvent(
                    timestamp="2024-01-15T10:00:00Z",
                    event_type="engagement_start",
                    description="Started",
                    agent_id="system",
                ),
            ),
        )

        generator = HTMLReportGenerator()
        result = generator.generate(report_data)

        assert "Ongoing" in result
        assert "<!DOCTYPE html>" in result

    def test_generate_with_no_critical_findings(self):
        """Test HTML generation without critical findings (no warning)."""
        from cyberred.storage.report_generator import (
            HTMLReportGenerator,
            ReportData,
            TimelineEvent,
        )

        report_data = ReportData(
            engagement_id="test-no-critical-001",
            title="No Critical Findings Report",
            start_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            scope={"targets": ["192.168.1.0/24"], "exclusions": []},
            findings=(
                {
                    "id": "FIND-001",
                    "severity": "low",
                    "title": "Minor Issue",
                    "description": "Low severity finding",
                    "target": "192.168.1.10",
                    "tool": "nmap",
                },
            ),
            timeline_events=(
                TimelineEvent(
                    timestamp="2024-01-15T10:00:00Z",
                    event_type="engagement_start",
                    description="Started",
                    agent_id="system",
                ),
            ),
        )

        generator = HTMLReportGenerator()
        result = generator.generate(report_data)

        # Should NOT contain critical warning
        assert "Immediate Action Required" not in result
        assert "<!DOCTYPE html>" in result

    def test_generate_with_hours_only_duration(self):
        """Test HTML generation with duration that's exactly hours (no minutes)."""
        from cyberred.storage.report_generator import (
            HTMLReportGenerator,
            ReportData,
            TimelineEvent,
        )

        report_data = ReportData(
            engagement_id="test-hours-001",
            title="Hours Only Duration Report",
            start_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),  # Exactly 2 hours
            scope={"targets": ["192.168.1.0/24"], "exclusions": []},
            findings=(),
            timeline_events=(),
        )

        generator = HTMLReportGenerator()
        result = generator.generate(report_data)

        assert "2 hours" in result
        assert "minutes" not in result.split("Duration")[1].split("<")[0]

    def test_generate_with_zero_duration(self):
        """Test HTML generation with zero duration (< 1 minute)."""
        from cyberred.storage.report_generator import (
            HTMLReportGenerator,
            ReportData,
            TimelineEvent,
        )

        start = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        report_data = ReportData(
            engagement_id="test-zero-001",
            title="Zero Duration Report",
            start_time=start,
            end_time=start,  # Same time = 0 seconds
            scope={"targets": ["192.168.1.0/24"], "exclusions": []},
            findings=(),
            timeline_events=(),
        )

        generator = HTMLReportGenerator()
        result = generator.generate(report_data)

        assert "&lt; 1 minute" in result or "< 1 minute" in result

    def test_generate_with_negative_duration_raises(self):
        """Test HTML generation with end before start raises error."""
        from cyberred.storage.report_generator import (
            HTMLReportGenerator,
            ReportData,
        )

        report_data = ReportData(
            engagement_id="test-negative-001",
            title="Negative Duration Report",
            start_time=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),  # Before start
            scope={"targets": [], "exclusions": []},
            findings=(),
            timeline_events=(),
        )

        generator = HTMLReportGenerator()
        with pytest.raises(ValueError, match="end_time cannot be before start_time"):
            generator.generate(report_data)

    def test_embed_jpeg_extension(self, tmp_path: Path):
        """Test embedding .jpeg extension (not just .jpg)."""
        from cyberred.storage.report_generator import embed_screenshot

        # Create minimal JPEG
        jpeg_data = base64.b64decode(
            "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
            "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFgAB"
            "AQAAAAAAAAAAAAAAAAAAAAL/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAA/AL//2Q=="
        )
        jpeg_file = tmp_path / "test.jpeg"
        jpeg_file.write_bytes(jpeg_data)

        result = embed_screenshot(jpeg_file)
        assert result.startswith("data:image/jpeg;base64,")

    def test_embed_screenshots_in_html_unsupported_format_keeps_original(self, tmp_path: Path):
        """Test embed_screenshots_in_html keeps original src for unsupported format."""
        from cyberred.storage.report_generator import embed_screenshots_in_html

        # Create a file with unsupported extension that exists
        unsupported_file = tmp_path / "image.bmp"
        unsupported_file.write_bytes(b"fake bmp data")

        html = '<img src="image.bmp" alt="unsupported">'
        result = embed_screenshots_in_html(html, tmp_path)

        # Should keep original src since .bmp is not supported
        assert 'src="image.bmp"' in result

    def test_embed_screenshots_in_html_single_quotes(self, temp_image_dir: Path):
        """Test embed_screenshots_in_html handles single-quoted src attributes."""
        from cyberred.storage.report_generator import embed_screenshots_in_html

        html = "<img src='screenshot.png' alt='test'>"
        result = embed_screenshots_in_html(html, temp_image_dir)

        assert "data:image/png;base64," in result
        assert "src='screenshot.png'" not in result

    def test_generate_with_minutes_only_duration(self):
        """Test HTML generation with duration that's only minutes (no hours)."""
        from cyberred.storage.report_generator import (
            HTMLReportGenerator,
            ReportData,
        )

        report_data = ReportData(
            engagement_id="test-minutes-001",
            title="Minutes Only Duration Report",
            start_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 15, 10, 45, 0, tzinfo=timezone.utc),  # 45 minutes
            scope={"targets": ["192.168.1.0/24"], "exclusions": []},
            findings=(),
            timeline_events=(),
        )

        generator = HTMLReportGenerator()
        result = generator.generate(report_data)

        assert "45 minutes" in result
        assert "hours" not in result.split("Duration")[1].split("<")[0]

    def test_findings_by_severity_handles_unknown_severity(self):
        """Test ReportData.findings_by_severity handles unknown severity values."""
        from cyberred.storage.report_generator import ReportData

        report_data = ReportData(
            engagement_id="test-unknown-sev",
            title="Unknown Severity Report",
            start_time=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            scope={"targets": [], "exclusions": []},
            findings=(
                {"id": "1", "severity": "critical", "title": "Known"},
                {"id": "2", "severity": "UNKNOWN", "title": "Unknown severity"},
                {"id": "3", "severity": "urgent", "title": "Another unknown"},
            ),
            timeline_events=(),
        )

        grouped = report_data.findings_by_severity()

        # Known severity should be grouped
        assert len(grouped["critical"]) == 1
        # Unknown severities should NOT cause errors - they're silently skipped
        # Total in all buckets should be 1 (only critical)
        total = sum(len(v) for v in grouped.values())
        assert total == 1


class TestMarkdownReportGeneratorForComposition:
    """Test MarkdownReportGenerator functionality used by HTMLReportGenerator composition."""

    def test_markdown_generator_custom_template(self, tmp_path: Path):
        """Test MarkdownReportGenerator with custom template path."""
        from cyberred.storage.report_generator import MarkdownReportGenerator

        # Create custom template
        custom_template = tmp_path / "custom_md.jinja2"
        custom_template.write_text("# {{ title }}\nEngagement: {{ engagement_id }}")

        generator = MarkdownReportGenerator(template_path=custom_template)
        assert generator.template is not None
        assert generator.template_path == custom_template

    def test_markdown_generator_generate_returns_string(self, sample_report_data):
        """Test MarkdownReportGenerator.generate() returns rendered string."""
        from cyberred.storage.report_generator import MarkdownReportGenerator

        generator = MarkdownReportGenerator()
        result = generator.generate(sample_report_data)

        assert isinstance(result, str)
        assert len(result) > 0
        assert sample_report_data.title in result

    def test_markdown_generator_missing_template_raises(self):
        """Test MarkdownReportGenerator raises FileNotFoundError for missing template."""
        from cyberred.storage.report_generator import MarkdownReportGenerator

        with pytest.raises(FileNotFoundError, match="Template not found"):
            MarkdownReportGenerator(template_path=Path("/nonexistent/template.jinja2"))
