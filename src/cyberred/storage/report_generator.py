"""Markdown Report Generation for Cyber-Red (Story 13.4).

This module provides Markdown report generation using Jinja2 templates.
Reports include executive summary, findings grouped by severity, timeline,
and cryptographic signature for integrity verification.

Usage:
    from cyberred.storage.report_generator import (
        MarkdownReportGenerator,
        ReportData,
        TimelineEvent,
        sign_report,
        save_report,
    )

    # Create report data
    report_data = ReportData(
        engagement_id="eng-001",
        title="Penetration Test Report",
        start_time=datetime.now(timezone.utc),
        end_time=None,
        scope={"targets": ["192.168.1.0/24"], "exclusions": []},
        findings=[...],
        timeline_events=[...],
    )

    # Generate report
    generator = MarkdownReportGenerator()
    content = generator.generate(report_data)

    # Sign and save
    signed = sign_report(content, signing_key)
    save_signed_report(signed, Path("report.md"))
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any

import jinja2


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class TimelineEvent:
    """Timeline event for engagement activity tracking.

    Attributes:
        timestamp: ISO 8601 formatted timestamp.
        event_type: Type of event (engagement_start, finding_discovered, etc.).
        description: Human-readable event description.
        agent_id: ID of agent that triggered the event.
        details: Optional additional event details.
    """

    timestamp: str
    event_type: str
    description: str
    agent_id: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportData:
    """Complete data for report generation.

    Attributes:
        engagement_id: Unique engagement identifier.
        title: Report title.
        start_time: Engagement start time.
        end_time: Engagement end time (None if ongoing).
        scope: Scope definition with targets and exclusions.
        findings: List of finding dictionaries.
        timeline_events: List of TimelineEvent objects.
        metadata: Optional additional metadata.
    """

    engagement_id: str
    title: str
    start_time: datetime
    end_time: datetime | None
    scope: dict[str, Any]
    findings: list[dict[str, Any]]
    timeline_events: list[TimelineEvent]
    metadata: dict[str, Any] = field(default_factory=dict)

    def findings_by_severity(self) -> dict[str, list[dict[str, Any]]]:
        """Group findings by severity level.

        Returns:
            Dictionary mapping severity to list of findings.
        """
        grouped: dict[str, list[dict[str, Any]]] = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
            "info": [],
        }

        for finding in self.findings:
            severity = finding.get("severity", "info").lower()
            if severity in grouped:
                grouped[severity].append(finding)

        return grouped

    def get_sorted_timeline(self) -> list[TimelineEvent]:
        """Get timeline events sorted by timestamp.

        Returns:
            List of TimelineEvent sorted chronologically.
        """
        return sorted(self.timeline_events, key=lambda e: e.timestamp)


@dataclass
class SignedReport:
    """Signed report with cryptographic signature.

    Attributes:
        content: Original report content.
        signature: HMAC-SHA256 signature.
        timestamp: Signing timestamp (ISO 8601).
        key_id: Identifier for the signing key.
        content_hash: SHA-256 hash of content.
    """

    content: str
    signature: str
    timestamp: str
    key_id: str
    content_hash: str


# =============================================================================
# Report Generator
# =============================================================================


class MarkdownReportGenerator:
    """Generates Markdown reports using Jinja2 templates.

    Attributes:
        template: Loaded Jinja2 template.
        template_path: Path to the template file.
    """

    def __init__(self, template_path: Path | None = None) -> None:
        """Initialize the report generator.

        Args:
            template_path: Optional custom template path. If None, uses default.

        Raises:
            FileNotFoundError: If custom template path doesn't exist.
        """
        if template_path is not None:
            if not template_path.exists():
                raise FileNotFoundError(f"Template not found: {template_path}")
            self.template_path = template_path
            # Load custom template
            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(template_path.parent),
                autoescape=False,
                trim_blocks=True,
                lstrip_blocks=True,
            )
            self.template = env.get_template(template_path.name)
        else:
            # Load default template from package
            self.template_path = self._get_default_template_path()
            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(self.template_path.parent),
                autoescape=False,
                trim_blocks=True,
                lstrip_blocks=True,
            )
            self.template = env.get_template(self.template_path.name)

    def _get_default_template_path(self) -> Path:
        """Get path to default template.

        Returns:
            Path to the default report_md.jinja2 template.
        """
        # Use importlib.resources for package resources
        try:
            # Python 3.9+ style
            template_dir = resources.files("cyberred.templates")
            template_path = template_dir.joinpath("report_md.jinja2")
            # Convert to Path for consistency
            return Path(str(template_path))
        except (TypeError, AttributeError):  # pragma: no cover
            # Fallback for older Python or edge cases
            import cyberred.templates
            template_dir = Path(cyberred.templates.__file__).parent
            return template_dir / "report_md.jinja2"

    def generate(self, report_data: ReportData) -> str:
        """Generate Markdown report from data.

        Args:
            report_data: Complete report data.

        Returns:
            Rendered Markdown report string.
        """
        # Prepare template context
        context = self._prepare_context(report_data)

        # Render template
        return self.template.render(**context)

    def _prepare_context(self, report_data: ReportData) -> dict[str, Any]:
        """Prepare template context from report data.

        Args:
            report_data: Report data to convert to context.

        Returns:
            Dictionary of template variables.
        """
        grouped_findings = report_data.findings_by_severity()
        sorted_timeline = report_data.get_sorted_timeline()

        # Calculate duration
        duration = self._format_duration(report_data.start_time, report_data.end_time)

        # Calculate summaries
        tool_summary = self._calculate_tool_summary(report_data.findings)
        agent_summary = self._calculate_agent_summary(sorted_timeline)

        # Generate executive summary
        executive_summary = self._generate_executive_summary(
            report_data, grouped_findings, duration
        )

        # Calculate content hash for report footer
        # We'll compute this after initial render, so use placeholder first
        report_hash = "pending"

        context = {
            "title": report_data.title,
            "engagement_id": report_data.engagement_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "duration": duration,
            "scope": report_data.scope,
            "findings_critical": grouped_findings["critical"],
            "findings_high": grouped_findings["high"],
            "findings_medium": grouped_findings["medium"],
            "findings_low": grouped_findings["low"],
            "findings_info": grouped_findings["info"],
            "total_findings": len(report_data.findings),
            "timeline": [self._format_timeline_event(e) for e in sorted_timeline],
            "executive_summary": executive_summary,
            "tool_summary": tool_summary,
            "agent_summary": agent_summary,
            "metadata": report_data.metadata,
            "report_hash": report_hash,
        }

        # First render to get content for hash
        initial_content = self.template.render(**context)
        # Calculate actual hash
        context["report_hash"] = hashlib.sha256(initial_content.encode()).hexdigest()[:16]

        return context

    def _format_duration(
        self, start_time: datetime, end_time: datetime | None
    ) -> str:
        """Format engagement duration as human-readable string.

        Args:
            start_time: Engagement start time.
            end_time: Engagement end time (None if ongoing).

        Returns:
            Formatted duration string.
        """
        if end_time is None:
            return "Ongoing"

        delta = end_time - start_time
        total_seconds = int(delta.total_seconds())

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0:
            if minutes > 0:
                return f"{hours} hours {minutes} minutes"
            return f"{hours} hours"
        return f"{minutes} minutes"

    def _generate_executive_summary(
        self,
        report_data: ReportData,
        grouped_findings: dict[str, list[dict[str, Any]]],
        duration: str,
    ) -> str:
        """Generate executive summary section.

        Args:
            report_data: Complete report data.
            grouped_findings: Findings grouped by severity.
            duration: Formatted duration string.

        Returns:
            Executive summary text.
        """
        total = len(report_data.findings)
        critical_count = len(grouped_findings["critical"])
        high_count = len(grouped_findings["high"])
        medium_count = len(grouped_findings["medium"])
        low_count = len(grouped_findings["low"])
        info_count = len(grouped_findings["info"])

        summary_lines = [
            f"This penetration test engagement discovered **{total} findings** "
            f"across the defined scope.",
            "",
            "**Finding Summary by Severity:**",
            f"- Critical: {critical_count}",
            f"- High: {high_count}",
            f"- Medium: {medium_count}",
            f"- Low: {low_count}",
            f"- Informational: {info_count}",
            "",
            f"**Duration:** {duration}",
        ]

        if critical_count > 0:
            summary_lines.extend([
                "",
                "⚠️ **Immediate Action Required:** Critical vulnerabilities were discovered "
                "that require urgent remediation.",
            ])

        return "\n".join(summary_lines)

    def _format_timeline_event(self, event: TimelineEvent) -> dict[str, Any]:
        """Format timeline event for template context.

        Args:
            event: TimelineEvent to format.

        Returns:
            Dictionary representation for template.
        """
        return {
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "agent_id": event.agent_id,
            "description": event.description,
            "details": event.details,
        }

    def _calculate_tool_summary(
        self, findings: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Calculate tool execution summary from findings.

        Args:
            findings: List of finding dictionaries.

        Returns:
            Dictionary mapping tool name to execution count.
        """
        tool_counts: dict[str, int] = {}
        for finding in findings:
            tool = finding.get("tool", "unknown")
            tool_counts[tool] = tool_counts.get(tool, 0) + 1
        return tool_counts

    def _calculate_agent_summary(
        self, timeline: list[TimelineEvent]
    ) -> dict[str, int]:
        """Calculate agent activity summary from timeline.

        Args:
            timeline: List of timeline events.

        Returns:
            Dictionary mapping agent ID to action count.
        """
        agent_counts: dict[str, int] = {}
        for event in timeline:
            agent_id = event.agent_id
            agent_counts[agent_id] = agent_counts.get(agent_id, 0) + 1
        return agent_counts


# =============================================================================
# Report Signing
# =============================================================================


def sign_report(
    report_content: str,
    signing_key: bytes,
    key_id: str = "engagement-key",
) -> SignedReport:
    """Sign report content with HMAC-SHA256.

    Args:
        report_content: Report content to sign.
        signing_key: Key for HMAC signature.
        key_id: Identifier for the signing key.

    Returns:
        SignedReport with signature and metadata.
    """
    # Calculate content hash
    content_hash = hashlib.sha256(report_content.encode()).hexdigest()

    # Generate HMAC-SHA256 signature
    signature = hmac.new(
        signing_key, report_content.encode(), hashlib.sha256
    ).hexdigest()

    # Generate timestamp
    timestamp = datetime.now(timezone.utc).isoformat()

    return SignedReport(
        content=report_content,
        signature=signature,
        timestamp=timestamp,
        key_id=key_id,
        content_hash=content_hash,
    )


def verify_signature(signed_report: SignedReport, key: bytes) -> bool:
    """Verify report signature.

    Args:
        signed_report: SignedReport to verify.
        key: Key to use for verification.

    Returns:
        True if signature is valid, False otherwise.
    """
    # Recalculate signature
    expected_signature = hmac.new(
        key, signed_report.content.encode(), hashlib.sha256
    ).hexdigest()

    # Compare signatures using constant-time comparison
    return hmac.compare_digest(expected_signature, signed_report.signature)


# =============================================================================
# Report Save Functions
# =============================================================================


def save_report(content: str, output_path: Path) -> Path:
    """Save report content to file.

    Args:
        content: Report content to save.
        output_path: Destination path.

    Returns:
        Path to saved file.
    """
    # Create parent directories if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write with UTF-8 encoding
    output_path.write_text(content, encoding="utf-8")

    return output_path


def save_signed_report(signed_report: SignedReport, output_path: Path) -> None:
    """Save signed report and signature file.

    Args:
        signed_report: SignedReport to save.
        output_path: Destination path for report content.
    """
    # Save report content
    save_report(signed_report.content, output_path)

    # Save signature file
    sig_path = output_path.with_suffix(".sig")
    sig_data = {
        "content_hash": signed_report.content_hash,
        "signature": signed_report.signature,
        "timestamp": signed_report.timestamp,
        "key_id": signed_report.key_id,
    }
    sig_path.write_text(json.dumps(sig_data, indent=2), encoding="utf-8")
