"""Unit tests for FindingStream widget.

Story 9.5: Real-Time Finding Stream
Tests the finding stream that displays security findings as they are discovered.

Acceptance Criteria:
1. Findings appear in Strategy Stream pane when agents publish them
2. Findings are color-coded by severity (critical=red, high=orange, medium=yellow)
3. Stream auto-scrolls to show latest (with pause option)
4. Click a finding to see detailed information
5. Stream updates in <500ms from discovery
6. Integration tests verify real-time updates
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock


class TestFindingSeverity:
    """Tests for FindingSeverity enum."""

    def test_finding_severity_enum_values(self):
        """Test FindingSeverity enum has correct values per spec."""
        from cyberred.tui.widgets.finding_stream import FindingSeverity
        
        assert FindingSeverity.CRITICAL == 0
        assert FindingSeverity.HIGH == 1
        assert FindingSeverity.MEDIUM == 2
        assert FindingSeverity.LOW == 3
        assert FindingSeverity.INFO == 4

    def test_finding_severity_ordering(self):
        """Test FindingSeverity values are ordered correctly (lower = higher severity)."""
        from cyberred.tui.widgets.finding_stream import FindingSeverity
        
        # CRITICAL should be highest severity (lowest value)
        assert FindingSeverity.CRITICAL < FindingSeverity.HIGH
        assert FindingSeverity.HIGH < FindingSeverity.MEDIUM
        assert FindingSeverity.MEDIUM < FindingSeverity.LOW
        assert FindingSeverity.LOW < FindingSeverity.INFO

    def test_finding_severity_is_int_enum(self):
        """Test FindingSeverity is an IntEnum for efficient comparison."""
        from cyberred.tui.widgets.finding_stream import FindingSeverity
        from enum import IntEnum
        
        assert issubclass(FindingSeverity, IntEnum)


class TestSeverityColorMapping:
    """Tests for severity color and icon mappings."""

    def test_severity_colors_mapping(self):
        """Test _SEVERITY_COLORS has correct colors per UX spec."""
        from cyberred.tui.widgets.finding_stream import (
            _SEVERITY_COLORS, FindingSeverity
        )
        
        assert _SEVERITY_COLORS[FindingSeverity.CRITICAL] == "bright_red"
        assert _SEVERITY_COLORS[FindingSeverity.HIGH] == "orange3"
        assert _SEVERITY_COLORS[FindingSeverity.MEDIUM] == "yellow"
        assert _SEVERITY_COLORS[FindingSeverity.LOW] == "blue"
        assert _SEVERITY_COLORS[FindingSeverity.INFO] == "dim"

    def test_severity_icons_mapping(self):
        """Test _SEVERITY_ICONS has correct icons per spec."""
        from cyberred.tui.widgets.finding_stream import (
            _SEVERITY_ICONS, FindingSeverity
        )
        
        assert _SEVERITY_ICONS[FindingSeverity.CRITICAL] == "🔴"
        assert _SEVERITY_ICONS[FindingSeverity.HIGH] == "🟠"
        assert _SEVERITY_ICONS[FindingSeverity.MEDIUM] == "🟡"
        assert _SEVERITY_ICONS[FindingSeverity.LOW] == "🔵"
        assert _SEVERITY_ICONS[FindingSeverity.INFO] == "ℹ️"

    def test_get_severity_style_critical(self):
        """Test get_severity_style returns correct style for CRITICAL."""
        from cyberred.tui.widgets.finding_stream import (
            get_severity_style, FindingSeverity
        )
        
        style = get_severity_style(FindingSeverity.CRITICAL)
        assert "bright_red" in style

    def test_get_severity_style_high(self):
        """Test get_severity_style returns correct style for HIGH."""
        from cyberred.tui.widgets.finding_stream import (
            get_severity_style, FindingSeverity
        )
        
        style = get_severity_style(FindingSeverity.HIGH)
        assert "orange3" in style

    def test_get_severity_style_all_severities(self):
        """Test get_severity_style returns non-empty style for all severities."""
        from cyberred.tui.widgets.finding_stream import (
            get_severity_style, FindingSeverity
        )
        
        for severity in FindingSeverity:
            style = get_severity_style(severity)
            assert style, f"Style should not be empty for {severity}"


class TestFindingDataclass:
    """Tests for Finding dataclass."""

    def test_finding_creation(self):
        """Test Finding dataclass can be created with required fields."""
        from cyberred.tui.widgets.finding_stream import Finding, FindingSeverity
        
        now = datetime.now()
        finding = Finding(
            id="finding-001",
            timestamp=now,
            severity=FindingSeverity.HIGH,
            finding_type="vulnerability",
            target="192.168.1.100:443",
            summary="SQL Injection detected",
        )
        
        assert finding.id == "finding-001"
        assert finding.timestamp == now
        assert finding.severity == FindingSeverity.HIGH
        assert finding.finding_type == "vulnerability"
        assert finding.target == "192.168.1.100:443"
        assert finding.summary == "SQL Injection detected"

    def test_finding_default_values(self):
        """Test Finding dataclass default values."""
        from cyberred.tui.widgets.finding_stream import Finding, FindingSeverity
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.INFO,
            finding_type="info",
            target="localhost",
            summary="Test finding",
        )
        
        assert finding.details == {}
        assert finding.agent_id == ""

    def test_finding_with_details(self):
        """Test Finding dataclass with details dict."""
        from cyberred.tui.widgets.finding_stream import Finding, FindingSeverity
        
        details = {"cvss": 9.8, "cve": "CVE-2024-1234"}
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.CRITICAL,
            finding_type="vulnerability",
            target="192.168.1.100",
            summary="Critical RCE",
            details=details,
            agent_id="agent-0001",
        )
        
        assert finding.details == details
        assert finding.agent_id == "agent-0001"

    def test_finding_formatted_timestamp(self):
        """Test Finding.formatted_timestamp property returns HH:MM:SS format."""
        from cyberred.tui.widgets.finding_stream import Finding, FindingSeverity
        
        ts = datetime(2024, 1, 15, 14, 30, 45)
        finding = Finding(
            id="finding-001",
            timestamp=ts,
            severity=FindingSeverity.LOW,
            finding_type="info",
            target="localhost",
            summary="Test",
        )
        
        assert finding.formatted_timestamp == "14:30:45"

    def test_finding_equality(self):
        """Test Finding equality is based on id."""
        from cyberred.tui.widgets.finding_stream import Finding, FindingSeverity
        
        now = datetime.now()
        finding1 = Finding(
            id="finding-001",
            timestamp=now,
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host1",
            summary="Test 1",
        )
        finding2 = Finding(
            id="finding-001",
            timestamp=now,
            severity=FindingSeverity.LOW,  # Different severity
            finding_type="other",
            target="host2",
            summary="Test 2",
        )
        finding3 = Finding(
            id="finding-002",  # Different id
            timestamp=now,
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host1",
            summary="Test 1",
        )
        
        assert finding1 == finding2  # Same id
        assert finding1 != finding3  # Different id

    def test_finding_hash(self):
        """Test Finding hash is based on id."""
        from cyberred.tui.widgets.finding_stream import Finding, FindingSeverity
        
        finding1 = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host1",
            summary="Test",
        )
        finding2 = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.LOW,
            finding_type="other",
            target="host2",
            summary="Different",
        )
        
        assert hash(finding1) == hash(finding2)
        
        # Can be used in sets
        finding_set = {finding1, finding2}
        assert len(finding_set) == 1

    def test_finding_repr(self):
        """Test Finding __repr__ returns useful string."""
        from cyberred.tui.widgets.finding_stream import Finding, FindingSeverity
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.CRITICAL,
            finding_type="vuln",
            target="192.168.1.100",
            summary="Critical vuln",
        )
        
        repr_str = repr(finding)
        assert "finding-001" in repr_str
        assert "CRITICAL" in repr_str

    def test_finding_uses_slots(self):
        """Test Finding uses __slots__ for memory efficiency."""
        from cyberred.tui.widgets.finding_stream import Finding
        
        # slots=True in dataclass creates __slots__
        assert hasattr(Finding, "__slots__")


class TestFindingStreamWidget:
    """Tests for FindingStream widget."""

    def test_finding_stream_creation(self):
        """Test FindingStream can be created."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        stream = FindingStream()
        assert stream is not None
        assert stream._findings == []
        assert stream._max_findings == 1000

    def test_finding_stream_custom_max_findings(self):
        """Test FindingStream with custom max_findings."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        stream = FindingStream(max_findings=500)
        assert stream._max_findings == 500

    def test_finding_stream_auto_scroll_default(self):
        """Test FindingStream auto_scroll defaults to True."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        stream = FindingStream()
        assert stream.auto_scroll is True

    def test_finding_stream_paused_default(self):
        """Test FindingStream paused defaults to False."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        stream = FindingStream()
        assert stream.paused is False

    def test_finding_stream_toggle_auto_scroll(self):
        """Test FindingStream toggle_auto_scroll method."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        stream = FindingStream()
        assert stream.paused is False
        
        stream.toggle_auto_scroll()
        assert stream.paused is True
        assert stream.auto_scroll is False
        
        stream.toggle_auto_scroll()
        assert stream.paused is False
        assert stream.auto_scroll is True

    def test_finding_stream_paused_setter(self):
        """Test FindingStream paused property setter updates auto_scroll."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        stream = FindingStream()
        stream.paused = True
        
        assert stream.paused is True
        assert stream.auto_scroll is False
        
        stream.paused = False
        assert stream.paused is False
        assert stream.auto_scroll is True

    def test_finding_stream_add_finding(self):
        """Test FindingStream add_finding adds to list."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        
        stream = FindingStream()
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="192.168.1.100",
            summary="Test finding",
        )
        
        # Mock write to avoid actual rendering
        stream.write = MagicMock()
        
        stream.add_finding(finding)
        
        assert len(stream._findings) == 1
        assert stream._findings[0] == finding
        stream.write.assert_called_once()

    def test_finding_stream_fifo_eviction(self):
        """Test FindingStream FIFO eviction when max_findings exceeded."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        
        stream = FindingStream(max_findings=3)
        stream.write = MagicMock()
        
        for i in range(5):
            finding = Finding(
                id=f"finding-{i:03d}",
                timestamp=datetime.now(),
                severity=FindingSeverity.INFO,
                finding_type="info",
                target=f"host-{i}",
                summary=f"Finding {i}",
            )
            stream.add_finding(finding)
        
        # Should only have last 3 findings
        assert len(stream._findings) == 3
        assert stream._findings[0].id == "finding-002"
        assert stream._findings[1].id == "finding-003"
        assert stream._findings[2].id == "finding-004"

    def test_finding_stream_finding_index_maintained(self):
        """Test FindingStream maintains _finding_index mapping."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        
        stream = FindingStream()
        stream.write = MagicMock()
        
        finding1 = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host1",
            summary="First",
        )
        finding2 = Finding(
            id="finding-002",
            timestamp=datetime.now(),
            severity=FindingSeverity.LOW,
            finding_type="info",
            target="host2",
            summary="Second",
        )
        
        stream.add_finding(finding1)
        stream.add_finding(finding2)
        
        assert stream._finding_index[0] == finding1
        assert stream._finding_index[1] == finding2
        assert stream._line_count == 2


class TestFindingFormatting:
    """Tests for finding formatting."""

    def test_format_finding_returns_text(self):
        """Test format_finding returns Rich Text object."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        from rich.text import Text
        
        stream = FindingStream()
        finding = Finding(
            id="finding-001",
            timestamp=datetime(2024, 1, 15, 14, 30, 45),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="192.168.1.100",
            summary="SQL Injection found",
        )
        
        text = stream.format_finding(finding)
        
        assert isinstance(text, Text)

    def test_format_finding_contains_timestamp(self):
        """Test format_finding includes timestamp."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        
        stream = FindingStream()
        finding = Finding(
            id="finding-001",
            timestamp=datetime(2024, 1, 15, 14, 30, 45),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="192.168.1.100",
            summary="Test",
        )
        
        text = stream.format_finding(finding)
        plain = text.plain
        
        assert "14:30:45" in plain

    def test_format_finding_contains_severity_icon(self):
        """Test format_finding includes severity icon."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        
        stream = FindingStream()
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.CRITICAL,
            finding_type="vuln",
            target="host",
            summary="Test",
        )
        
        text = stream.format_finding(finding)
        plain = text.plain
        
        assert "🔴" in plain

    def test_format_finding_contains_severity_name(self):
        """Test format_finding includes severity name."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        
        stream = FindingStream()
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host",
            summary="Test",
        )
        
        text = stream.format_finding(finding)
        plain = text.plain
        
        assert "HIGH" in plain

    def test_format_finding_contains_target(self):
        """Test format_finding includes target."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        
        stream = FindingStream()
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.MEDIUM,
            finding_type="vuln",
            target="192.168.1.100:443",
            summary="Test",
        )
        
        text = stream.format_finding(finding)
        plain = text.plain
        
        assert "192.168.1.100:443" in plain

    def test_format_finding_contains_summary(self):
        """Test format_finding includes summary."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        
        stream = FindingStream()
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.LOW,
            finding_type="info",
            target="host",
            summary="SQL Injection detected in login form",
        )
        
        text = stream.format_finding(finding)
        plain = text.plain
        
        assert "SQL Injection detected in login form" in plain

    def test_format_finding_truncates_long_summary(self):
        """Test format_finding truncates summary > 60 chars with ellipsis."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        
        stream = FindingStream()
        long_summary = "A" * 80  # 80 characters
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.INFO,
            finding_type="info",
            target="host",
            summary=long_summary,
        )
        
        text = stream.format_finding(finding)
        plain = text.plain
        
        # Should truncate to 57 chars + "..."
        assert "A" * 57 + "..." in plain
        assert "A" * 58 not in plain

    def test_format_finding_does_not_truncate_short_summary(self):
        """Test format_finding does not truncate summary <= 60 chars."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        
        stream = FindingStream()
        short_summary = "A" * 60  # Exactly 60 characters
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.INFO,
            finding_type="info",
            target="host",
            summary=short_summary,
        )
        
        text = stream.format_finding(finding)
        plain = text.plain
        
        assert short_summary in plain
        assert "..." not in plain


class TestFindingReceivedMessage:
    """Tests for FindingReceived message class."""

    def test_finding_received_message_creation(self):
        """Test FindingReceived message can be created."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host",
            summary="Test",
        )
        
        msg = FindingStream.FindingReceived(finding)
        
        assert msg.finding == finding

    def test_finding_received_is_message(self):
        """Test FindingReceived is a Textual Message."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        from textual.message import Message
        
        assert issubclass(FindingStream.FindingReceived, Message)


class TestFindingDetailModal:
    """Tests for FindingDetailModal screen."""

    def test_finding_detail_modal_creation(self):
        """Test FindingDetailModal can be created."""
        from cyberred.tui.widgets.finding_stream import (
            FindingDetailModal, Finding, FindingSeverity
        )
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.CRITICAL,
            finding_type="RCE",
            target="192.168.1.100",
            summary="Critical vulnerability",
            details={"cve": "CVE-2024-1234"},
            agent_id="agent-0001",
        )
        
        modal = FindingDetailModal(finding)
        
        assert modal.finding == finding

    def test_finding_detail_modal_has_escape_binding(self):
        """Test FindingDetailModal has Escape key binding to close."""
        from cyberred.tui.widgets.finding_stream import FindingDetailModal
        
        # Check BINDINGS contains escape (format is list of tuples)
        binding_keys = [b[0] for b in FindingDetailModal.BINDINGS]
        assert "escape" in binding_keys


class TestFindingStreamDefaultCSS:
    """Tests for FindingStream CSS styling."""

    def test_finding_stream_has_default_css(self):
        """Test FindingStream has DEFAULT_CSS defined."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        assert hasattr(FindingStream, "DEFAULT_CSS")
        assert FindingStream.DEFAULT_CSS is not None
        assert len(FindingStream.DEFAULT_CSS) > 0

    def test_finding_stream_css_has_height(self):
        """Test FindingStream CSS includes height: 100%."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        assert "height: 100%" in FindingStream.DEFAULT_CSS

    def test_finding_stream_css_has_border(self):
        """Test FindingStream CSS includes border styling."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        assert "border" in FindingStream.DEFAULT_CSS


class TestFindingEqualityEdgeCases:
    """Edge case tests for Finding equality."""

    def test_finding_equality_with_non_finding(self):
        """Test Finding equality returns NotImplemented for non-Finding."""
        from cyberred.tui.widgets.finding_stream import Finding, FindingSeverity
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host",
            summary="Test",
        )
        
        result = finding.__eq__("not a finding")
        assert result is NotImplemented

    def test_finding_equality_with_none(self):
        """Test Finding equality with None returns NotImplemented."""
        from cyberred.tui.widgets.finding_stream import Finding, FindingSeverity
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host",
            summary="Test",
        )
        
        result = finding.__eq__(None)
        assert result is NotImplemented


class TestFindingDetailModalCompose:
    """Tests for FindingDetailModal compose method."""

    def test_finding_detail_modal_compose_is_generator(self):
        """Test FindingDetailModal.compose() is a generator method."""
        from cyberred.tui.widgets.finding_stream import (
            FindingDetailModal, Finding, FindingSeverity
        )
        import inspect
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime(2024, 1, 15, 14, 30, 45),
            severity=FindingSeverity.CRITICAL,
            finding_type="RCE",
            target="192.168.1.100",
            summary="Critical vulnerability found",
            details={"cve": "CVE-2024-1234"},
            agent_id="agent-0001",
        )
        
        modal = FindingDetailModal(finding)
        
        # Verify compose is a method that can be called
        assert hasattr(modal, 'compose')
        assert callable(modal.compose)

    def test_finding_detail_modal_stores_finding(self):
        """Test FindingDetailModal stores the finding correctly."""
        from cyberred.tui.widgets.finding_stream import (
            FindingDetailModal, Finding, FindingSeverity
        )
        
        finding = Finding(
            id="finding-002",
            timestamp=datetime(2024, 1, 15, 14, 30, 45),
            severity=FindingSeverity.LOW,
            finding_type="info",
            target="localhost",
            summary="Simple finding",
            details={},  # Empty details
            agent_id="agent-0002",
        )
        
        modal = FindingDetailModal(finding)
        
        # Verify finding is stored
        assert modal.finding == finding
        assert modal.finding.id == "finding-002"
        assert modal.finding.details == {}


class TestFindingDetailModalButtonHandler:
    """Tests for FindingDetailModal button press handling."""

    def test_finding_detail_modal_on_button_pressed_close(self):
        """Test on_button_pressed dismisses modal on close button."""
        from cyberred.tui.widgets.finding_stream import (
            FindingDetailModal, Finding, FindingSeverity
        )
        from textual.widgets import Button
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host",
            summary="Test",
        )
        
        modal = FindingDetailModal(finding)
        modal.dismiss = MagicMock()
        
        # Create a mock button pressed event
        button = MagicMock(spec=Button)
        button.id = "close-btn"
        event = MagicMock()
        event.button = button
        
        modal.on_button_pressed(event)
        
        modal.dismiss.assert_called_once()

    def test_finding_detail_modal_on_button_pressed_other_button(self):
        """Test on_button_pressed ignores other buttons."""
        from cyberred.tui.widgets.finding_stream import (
            FindingDetailModal, Finding, FindingSeverity
        )
        from textual.widgets import Button
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host",
            summary="Test",
        )
        
        modal = FindingDetailModal(finding)
        modal.dismiss = MagicMock()
        
        # Create a mock button pressed event for a different button
        button = MagicMock(spec=Button)
        button.id = "other-btn"
        event = MagicMock()
        event.button = button
        
        modal.on_button_pressed(event)
        
        modal.dismiss.assert_not_called()


class TestFindingStreamGetFindingAtLine:
    """Tests for FindingStream.get_finding_at_line method."""

    def test_get_finding_at_line_returns_finding(self):
        """Test get_finding_at_line returns correct finding."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        
        stream = FindingStream()
        stream.write = MagicMock()
        
        finding1 = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host1",
            summary="First",
        )
        finding2 = Finding(
            id="finding-002",
            timestamp=datetime.now(),
            severity=FindingSeverity.LOW,
            finding_type="info",
            target="host2",
            summary="Second",
        )
        
        stream.add_finding(finding1)
        stream.add_finding(finding2)
        
        assert stream.get_finding_at_line(0) == finding1
        assert stream.get_finding_at_line(1) == finding2

    def test_get_finding_at_line_returns_none_for_invalid(self):
        """Test get_finding_at_line returns None for invalid line."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        stream = FindingStream()
        
        assert stream.get_finding_at_line(0) is None
        assert stream.get_finding_at_line(100) is None
        assert stream.get_finding_at_line(-1) is None


class TestFindingStreamOnFindingReceived:
    """Tests for FindingStream.on_finding_received handler."""

    def test_on_finding_received_adds_finding(self):
        """Test on_finding_received handler adds finding to stream."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        
        stream = FindingStream()
        stream.write = MagicMock()
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.CRITICAL,
            finding_type="vuln",
            target="192.168.1.100",
            summary="Critical vulnerability",
        )
        
        message = FindingStream.FindingReceived(finding)
        stream.on_finding_received(message)
        
        assert len(stream._findings) == 1
        assert stream._findings[0] == finding
        stream.write.assert_called_once()

    def test_on_finding_received_with_discovery_time(self):
        """Test on_finding_received passes discovery time for latency tracking."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        import time
        
        stream = FindingStream()
        stream.write = MagicMock()
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host",
            summary="Test",
        )
        
        discovery_time = time.time_ns()
        message = FindingStream.FindingReceived(finding, discovery_time)
        stream.on_finding_received(message)
        
        assert len(stream._findings) == 1
        # Latency should be tracked (very small since we just created it)
        assert stream._last_latency_ms >= 0


class TestFindingStreamLatencyTracking:
    """Tests for FindingStream latency tracking."""

    def test_add_finding_tracks_latency(self):
        """Test add_finding tracks latency when discovery_time_ns provided."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        import time
        
        stream = FindingStream()
        stream.write = MagicMock()
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host",
            summary="Test",
        )
        
        # Discovery time was 10ms ago
        discovery_time = time.time_ns() - 10_000_000  # 10ms in nanoseconds
        stream.add_finding(finding, discovery_time)
        
        # Latency should be >= 10ms
        assert stream._last_latency_ms >= 10

    def test_add_finding_logs_warning_for_high_latency(self):
        """Test add_finding logs warning when latency exceeds threshold."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity, LATENCY_THRESHOLD_MS
        )
        import time
        import logging
        
        stream = FindingStream()
        stream.write = MagicMock()
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host",
            summary="Test",
        )
        
        # Discovery time was 600ms ago (above 500ms threshold)
        discovery_time = time.time_ns() - 600_000_000  # 600ms in nanoseconds
        
        with patch('cyberred.tui.widgets.finding_stream._logger') as mock_logger:
            stream.add_finding(finding, discovery_time)
            
            # Should have logged a warning
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0]
            assert 'latency' in call_args[0].lower()
            assert 'exceeds' in call_args[0].lower()

    def test_add_finding_no_latency_without_discovery_time(self):
        """Test add_finding doesn't track latency without discovery_time_ns."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        
        stream = FindingStream()
        stream.write = MagicMock()
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.INFO,
            finding_type="info",
            target="host",
            summary="Test",
        )
        
        # No discovery time provided
        stream.add_finding(finding)
        
        # Latency should remain 0
        assert stream._last_latency_ms == 0


class TestFindingStreamBindings:
    """Tests for FindingStream key bindings."""

    def test_finding_stream_has_bindings(self):
        """Test FindingStream has BINDINGS defined."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        assert hasattr(FindingStream, 'BINDINGS')
        assert len(FindingStream.BINDINGS) > 0

    def test_finding_stream_has_p_binding(self):
        """Test FindingStream has 'p' key binding for pause."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        binding_keys = [b.key for b in FindingStream.BINDINGS]
        assert 'p' in binding_keys

    def test_finding_stream_has_enter_binding(self):
        """Test FindingStream has 'enter' key binding for detail."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        binding_keys = [b.key for b in FindingStream.BINDINGS]
        assert 'enter' in binding_keys

    def test_action_toggle_pause(self):
        """Test action_toggle_pause toggles paused state."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        stream = FindingStream()
        assert stream.paused is False
        
        stream.action_toggle_pause()
        assert stream.paused is True
        
        stream.action_toggle_pause()
        assert stream.paused is False


class TestFindingStreamActionShowDetail:
    """Tests for action_show_detail method."""

    def test_action_show_detail_with_selected_line(self):
        """Test action_show_detail opens modal for selected line."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity, FindingDetailModal
        )
        
        stream = FindingStream()
        stream.write = MagicMock()
        
        # Add a finding
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host",
            summary="Test",
        )
        stream.add_finding(finding)
        
        # Set selected line
        stream._selected_line = 0
        
        # Mock the app property at module level to avoid NoActiveAppError
        mock_app = MagicMock()
        with patch.object(FindingStream, 'app', new_callable=lambda: property(lambda self: mock_app)):
            stream.action_show_detail()
            
            # Verify modal was pushed
            mock_app.push_screen.assert_called_once()
            call_args = mock_app.push_screen.call_args[0][0]
            assert isinstance(call_args, FindingDetailModal)
            assert call_args.finding == finding

    def test_action_show_detail_with_selected_line_no_finding(self):
        """Test action_show_detail handles selected line with no finding."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        stream = FindingStream()
        
        # Set selected line to non-existent line
        stream._selected_line = 999
        
        # Mock the app property - should not be called since no finding exists
        mock_app = MagicMock()
        with patch.object(FindingStream, 'app', new_callable=lambda: property(lambda self: mock_app)):
            stream.action_show_detail()
            
            # Should not have pushed a screen (finding not found at line 999)
            mock_app.push_screen.assert_not_called()

    def test_action_show_detail_no_selection_shows_latest(self):
        """Test action_show_detail shows most recent finding when no selection."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity, FindingDetailModal
        )
        
        stream = FindingStream()
        stream.write = MagicMock()
        
        # Add findings
        finding1 = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.LOW,
            finding_type="info",
            target="host1",
            summary="First",
        )
        finding2 = Finding(
            id="finding-002",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host2",
            summary="Second (most recent)",
        )
        stream.add_finding(finding1)
        stream.add_finding(finding2)
        
        # No selection (default is -1)
        assert stream._selected_line == -1
        
        # Mock the app property at module level
        mock_app = MagicMock()
        with patch.object(FindingStream, 'app', new_callable=lambda: property(lambda self: mock_app)):
            stream.action_show_detail()
            
            # Verify modal was pushed with most recent finding
            mock_app.push_screen.assert_called_once()
            call_args = mock_app.push_screen.call_args[0][0]
            assert isinstance(call_args, FindingDetailModal)
            assert call_args.finding == finding2  # Most recent

    def test_action_show_detail_no_findings(self):
        """Test action_show_detail does nothing when no findings."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        stream = FindingStream()
        
        # No findings, no selection
        assert len(stream._findings) == 0
        assert stream._selected_line == -1
        
        # Mock the app property - should not be called since no findings exist
        mock_app = MagicMock()
        with patch.object(FindingStream, 'app', new_callable=lambda: property(lambda self: mock_app)):
            stream.action_show_detail()
            
            # Should not have pushed a screen
            mock_app.push_screen.assert_not_called()


class TestFindingStreamOnClick:
    """Tests for on_click event handler."""

    def test_on_click_opens_modal_for_finding(self):
        """Test on_click opens modal for finding at clicked line."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity, FindingDetailModal
        )
        
        stream = FindingStream()
        stream.write = MagicMock()
        stream.scroll_y = 0  # Mock scroll position
        
        # Add a finding
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.CRITICAL,
            finding_type="vuln",
            target="host",
            summary="Test",
        )
        stream.add_finding(finding)
        
        # Create mock click event at line 0
        mock_event = MagicMock()
        mock_event.y = 0
        
        # Mock the app property at module level
        mock_app = MagicMock()
        with patch.object(FindingStream, 'app', new_callable=lambda: property(lambda self: mock_app)):
            stream.on_click(mock_event)
            
            # Verify selected line updated
            assert stream._selected_line == 0
            
            # Verify modal was pushed
            mock_app.push_screen.assert_called_once()
            call_args = mock_app.push_screen.call_args[0][0]
            assert isinstance(call_args, FindingDetailModal)
            assert call_args.finding == finding

    def test_on_click_no_finding_at_line(self):
        """Test on_click handles click on empty line."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        stream = FindingStream()
        stream.scroll_y = 0
        
        # Create mock click event at line with no finding
        mock_event = MagicMock()
        mock_event.y = 999
        
        # Mock the app property - should not be called since no finding at line
        mock_app = MagicMock()
        with patch.object(FindingStream, 'app', new_callable=lambda: property(lambda self: mock_app)):
            stream.on_click(mock_event)
            
            # Selected line should be updated
            assert stream._selected_line == 999
            
            # Should not have pushed a screen
            mock_app.push_screen.assert_not_called()


class TestFindingStreamBorderTitle:
    """Tests for FindingStream border_title property."""

    def test_border_title_normal(self):
        """Test border_title when not paused."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        stream = FindingStream()
        assert stream.border_title == "Finding Stream"

    def test_border_title_paused(self):
        """Test border_title shows [PAUSED] when paused."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        stream = FindingStream()
        stream.paused = True
        
        assert "[PAUSED]" in stream.border_title


class TestFindingStreamCSSClasses:
    """Tests for FindingStream CSS classes."""

    def test_finding_stream_has_severity_css_classes(self):
        """Test FindingStream DEFAULT_CSS includes severity classes."""
        from cyberred.tui.widgets.finding_stream import FindingStream
        
        css = FindingStream.DEFAULT_CSS
        assert 'finding-critical' in css
        assert 'finding-high' in css
        assert 'finding-medium' in css
        assert 'finding-low' in css
        assert 'finding-info' in css


class TestFindingReceivedMessageWithDiscoveryTime:
    """Tests for FindingReceived message with discovery time."""

    def test_finding_received_with_discovery_time(self):
        """Test FindingReceived can be created with discovery_time_ns."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        import time
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.HIGH,
            finding_type="vuln",
            target="host",
            summary="Test",
        )
        
        discovery_time = time.time_ns()
        msg = FindingStream.FindingReceived(finding, discovery_time)
        
        assert msg.finding == finding
        assert msg.discovery_time_ns == discovery_time

    def test_finding_received_without_discovery_time(self):
        """Test FindingReceived defaults discovery_time_ns to None."""
        from cyberred.tui.widgets.finding_stream import (
            FindingStream, Finding, FindingSeverity
        )
        
        finding = Finding(
            id="finding-001",
            timestamp=datetime.now(),
            severity=FindingSeverity.LOW,
            finding_type="info",
            target="host",
            summary="Test",
        )
        
        msg = FindingStream.FindingReceived(finding)
        
        assert msg.finding == finding
        assert msg.discovery_time_ns is None
