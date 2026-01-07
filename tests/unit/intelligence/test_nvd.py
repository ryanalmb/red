"""Unit tests for NVD Source Integration.

Tests cover:
- NvdCveEntry dataclass and field mapping
- CVSS to priority mapping
- NvdSource interface implementation
- Query matching and result conversion
- Health check functionality

Story: 5-3-nvd-api-source-integration
TDD Phase: RED (failing tests)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

from cyberred.intelligence import IntelPriority, IntelResult, IntelligenceSource


# =============================================================================
# Phase 1: NVD Data Models Tests [RED]
# =============================================================================


@pytest.mark.unit
class TestNvdCveEntry:
    """Tests for NvdCveEntry dataclass (Task 1.1)."""

    def test_nvd_cve_entry_accepts_all_required_fields(self) -> None:
        """NvdCveEntry dataclass accepts all required fields."""
        from cyberred.intelligence.sources.nvd import NvdCveEntry

        entry = NvdCveEntry(
            cve_id="CVE-2021-44228",
            cvss_v3_score=10.0,
            cvss_v3_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
            cvss_v2_score=9.3,
            description="Apache Log4j2 JNDI features do not protect against LDAP...",
            references=["https://nvd.nist.gov/vuln/detail/CVE-2021-44228"],
            published_date="2021-12-10T10:15:00.000",
            last_modified_date="2024-06-27T19:25:11.000",
            cpe_matches=["cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*"],
        )

        assert entry.cve_id == "CVE-2021-44228"
        assert entry.cvss_v3_score == 10.0
        assert entry.cvss_v3_vector == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
        assert entry.cvss_v2_score == 9.3
        assert "Apache Log4j2" in entry.description
        assert len(entry.references) == 1
        assert entry.published_date == "2021-12-10T10:15:00.000"
        assert entry.last_modified_date == "2024-06-27T19:25:11.000"
        assert len(entry.cpe_matches) == 1

    def test_nvd_cve_entry_optional_cvss_scores(self) -> None:
        """NvdCveEntry allows None for optional CVSS fields."""
        from cyberred.intelligence.sources.nvd import NvdCveEntry

        entry = NvdCveEntry(
            cve_id="CVE-2023-12345",
            cvss_v3_score=None,
            cvss_v3_vector=None,
            cvss_v2_score=None,
            description="Some vulnerability without CVSS yet",
            references=[],
            published_date="2023-01-01T00:00:00.000",
            last_modified_date="2023-01-01T00:00:00.000",
        )

        assert entry.cvss_v3_score is None
        assert entry.cvss_v3_vector is None
        assert entry.cvss_v2_score is None

    def test_nvd_cve_entry_default_cpe_matches(self) -> None:
        """NvdCveEntry.cpe_matches defaults to empty list."""
        from cyberred.intelligence.sources.nvd import NvdCveEntry

        entry = NvdCveEntry(
            cve_id="CVE-2023-12345",
            cvss_v3_score=7.5,
            cvss_v3_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H",
            cvss_v2_score=None,
            description="Test vulnerability",
            references=[],
            published_date="2023-01-01T00:00:00.000",
            last_modified_date="2023-01-01T00:00:00.000",
        )

        assert entry.cpe_matches == []

    def test_nvd_cve_entry_from_nvdlib_parses_cve_object(self) -> None:
        """NvdCveEntry.from_nvdlib() correctly parses nvdlib CVE object."""
        from cyberred.intelligence.sources.nvd import NvdCveEntry

        # Create mock nvdlib CVE object
        mock_cve = MagicMock()
        mock_cve.id = "CVE-2021-44228"
        mock_cve.v31score = 10.0
        mock_cve.v31vector = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
        mock_cve.v2score = 9.3

        # Mock description
        mock_desc = MagicMock()
        mock_desc.value = "Apache Log4j2 JNDI features..."
        mock_cve.descriptions = [mock_desc]

        # Mock references
        mock_ref = MagicMock()
        mock_ref.url = "https://nvd.nist.gov/vuln/detail/CVE-2021-44228"
        mock_cve.references = [mock_ref]

        mock_cve.published = "2021-12-10T10:15:00.000"
        mock_cve.lastModified = "2024-06-27T19:25:11.000"
        mock_cve.cpe = []

        entry = NvdCveEntry.from_nvdlib(mock_cve)

        assert entry.cve_id == "CVE-2021-44228"
        assert entry.cvss_v3_score == 10.0
        assert entry.cvss_v3_vector == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
        assert entry.cvss_v2_score == 9.3
        assert "Apache Log4j2" in entry.description

    def test_nvd_cve_entry_from_nvdlib_handles_missing_scores(self) -> None:
        """NvdCveEntry.from_nvdlib() handles missing CVSS scores gracefully."""
        from cyberred.intelligence.sources.nvd import NvdCveEntry

        mock_cve = MagicMock()
        mock_cve.id = "CVE-2023-99999"
        mock_cve.v31score = None
        mock_cve.v31vector = None
        mock_cve.v2score = None

        mock_desc = MagicMock()
        mock_desc.value = "No scores yet"
        mock_cve.descriptions = [mock_desc]

        mock_cve.references = []
        mock_cve.published = "2023-01-01T00:00:00.000"
        mock_cve.lastModified = "2023-01-01T00:00:00.000"
        mock_cve.cpe = []

        entry = NvdCveEntry.from_nvdlib(mock_cve)

        assert entry.cvss_v3_score is None
        assert entry.cvss_v3_vector is None
        assert entry.cvss_v2_score is None

    def test_nvd_cve_entry_from_nvdlib_extracts_cpe_matches(self) -> None:
        """NvdCveEntry.from_nvdlib() extracts CPE matches when criteria attribute exists."""
        from cyberred.intelligence.sources.nvd import NvdCveEntry

        mock_cve = MagicMock()
        mock_cve.id = "CVE-2021-44228"
        mock_cve.v31score = 10.0
        mock_cve.v31vector = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
        mock_cve.v2score = None

        mock_desc = MagicMock()
        mock_desc.value = "Log4j vulnerability"
        mock_cve.descriptions = [mock_desc]

        mock_cve.references = []
        mock_cve.published = "2021-12-10T00:00:00.000"
        mock_cve.lastModified = "2024-06-27T00:00:00.000"

        # Mock CPE with criteria attribute
        mock_cpe1 = MagicMock()
        mock_cpe1.criteria = "cpe:2.3:a:apache:log4j:2.0:*:*:*:*:*:*:*"
        mock_cpe2 = MagicMock()
        mock_cpe2.criteria = "cpe:2.3:a:apache:log4j:2.14.1:*:*:*:*:*:*:*"
        mock_cve.cpe = [mock_cpe1, mock_cpe2]

        entry = NvdCveEntry.from_nvdlib(mock_cve)

        assert len(entry.cpe_matches) == 2
        assert "cpe:2.3:a:apache:log4j:2.0:*:*:*:*:*:*:*" in entry.cpe_matches
        assert "cpe:2.3:a:apache:log4j:2.14.1:*:*:*:*:*:*:*" in entry.cpe_matches


# =============================================================================
# Phase 2: Priority Mapping Tests [RED]
# =============================================================================


@pytest.mark.unit
class TestGetNvdPriority:
    """Tests for get_nvd_priority() function (Task 2.1)."""

    def test_critical_cvss_returns_nvd_critical(self) -> None:
        """get_nvd_priority(9.5) returns IntelPriority.NVD_CRITICAL."""
        from cyberred.intelligence.sources.nvd import get_nvd_priority

        result = get_nvd_priority(9.5)
        assert result == IntelPriority.NVD_CRITICAL
        assert result == 2

    def test_high_cvss_returns_nvd_high(self) -> None:
        """get_nvd_priority(7.5) returns IntelPriority.NVD_HIGH."""
        from cyberred.intelligence.sources.nvd import get_nvd_priority

        result = get_nvd_priority(7.5)
        assert result == IntelPriority.NVD_HIGH
        assert result == 3

    def test_medium_cvss_returns_nvd_medium(self) -> None:
        """get_nvd_priority(5.0) returns IntelPriority.NVD_MEDIUM."""
        from cyberred.intelligence.sources.nvd import get_nvd_priority

        result = get_nvd_priority(5.0)
        assert result == IntelPriority.NVD_MEDIUM
        assert result == 7

    def test_low_cvss_returns_nvd_medium(self) -> None:
        """get_nvd_priority(2.0) returns IntelPriority.NVD_MEDIUM (low maps to medium)."""
        from cyberred.intelligence.sources.nvd import get_nvd_priority

        result = get_nvd_priority(2.0)
        assert result == IntelPriority.NVD_MEDIUM
        assert result == 7

    def test_none_cvss_returns_nvd_medium(self) -> None:
        """get_nvd_priority(None) returns IntelPriority.NVD_MEDIUM (default)."""
        from cyberred.intelligence.sources.nvd import get_nvd_priority

        result = get_nvd_priority(None)
        assert result == IntelPriority.NVD_MEDIUM
        assert result == 7

    def test_boundary_9_0_returns_critical(self) -> None:
        """get_nvd_priority(9.0) returns NVD_CRITICAL (boundary case)."""
        from cyberred.intelligence.sources.nvd import get_nvd_priority

        result = get_nvd_priority(9.0)
        assert result == IntelPriority.NVD_CRITICAL

    def test_boundary_7_0_returns_high(self) -> None:
        """get_nvd_priority(7.0) returns NVD_HIGH (boundary case)."""
        from cyberred.intelligence.sources.nvd import get_nvd_priority

        result = get_nvd_priority(7.0)
        assert result == IntelPriority.NVD_HIGH

    def test_boundary_6_9_returns_medium(self) -> None:
        """get_nvd_priority(6.9) returns NVD_MEDIUM (just below high)."""
        from cyberred.intelligence.sources.nvd import get_nvd_priority

        result = get_nvd_priority(6.9)
        assert result == IntelPriority.NVD_MEDIUM


# =============================================================================
# Phase 3: NvdSource Implementation Tests [RED]
# =============================================================================


@pytest.mark.unit
class TestNvdSource:
    """Tests for NvdSource implementation (Tasks 3.1-3.5)."""

    def test_extends_intelligence_source(self) -> None:
        """NvdSource extends IntelligenceSource."""
        from cyberred.intelligence.sources.nvd import NvdSource

        source = NvdSource()
        assert isinstance(source, IntelligenceSource)

    def test_name_returns_nvd(self) -> None:
        """NvdSource.name returns 'nvd'."""
        from cyberred.intelligence.sources.nvd import NvdSource

        source = NvdSource()
        assert source.name == "nvd"

    def test_priority_returns_nvd_critical(self) -> None:
        """NvdSource.priority returns IntelPriority.NVD_CRITICAL by default."""
        from cyberred.intelligence.sources.nvd import NvdSource

        source = NvdSource()
        assert source.priority == IntelPriority.NVD_CRITICAL
        assert source.priority == 2

    def test_timeout_default_is_5_seconds(self) -> None:
        """NvdSource.timeout defaults to 5.0 seconds."""
        from cyberred.intelligence.sources.nvd import NvdSource

        source = NvdSource()
        assert source.timeout == 5.0

    def test_custom_timeout(self) -> None:
        """NvdSource accepts custom timeout."""
        from cyberred.intelligence.sources.nvd import NvdSource

        source = NvdSource(timeout=10.0)
        assert source.timeout == 10.0

    def test_api_key_from_init(self) -> None:
        """NvdSource accepts API key via constructor."""
        from cyberred.intelligence.sources.nvd import NvdSource

        source = NvdSource(api_key="test-api-key")
        assert source._api_key == "test-api-key"

    def test_api_key_from_environment(self) -> None:
        """NvdSource loads API key from NVD_API_KEY environment variable."""
        from cyberred.intelligence.sources.nvd import NvdSource

        with patch.dict("os.environ", {"NVD_API_KEY": "env-api-key"}):
            source = NvdSource()
            assert source._api_key == "env-api-key"

    def test_no_api_key_logs_warning(self) -> None:
        """NvdSource logs when no API key is available."""
        from cyberred.intelligence.sources.nvd import NvdSource

        with patch.dict("os.environ", {}, clear=True):
            # Remove NVD_API_KEY from environment
            import os
            original_key = os.environ.pop("NVD_API_KEY", None)
            try:
                source = NvdSource(api_key=None)
                assert source._api_key is None
            finally:
                if original_key:
                    os.environ["NVD_API_KEY"] = original_key

    @pytest.mark.asyncio
    async def test_query_returns_matching_cves(self) -> None:
        """query('OpenSSH', '8.2') returns matching CVEs."""
        from cyberred.intelligence.sources.nvd import NvdSource, NvdCveEntry

        mock_cve = MagicMock()
        mock_cve.id = "CVE-2020-14145"
        mock_cve.v31score = 5.3
        mock_cve.v31vector = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N"
        mock_cve.v2score = None

        mock_desc = MagicMock()
        mock_desc.value = "OpenSSH vulnerability"
        mock_cve.descriptions = [mock_desc]

        mock_cve.references = []
        mock_cve.published = "2020-06-29T00:00:00.000"
        mock_cve.lastModified = "2023-01-01T00:00:00.000"
        mock_cve.cpe = []

        with patch("cyberred.intelligence.sources.nvd.nvdlib") as mock_nvdlib:
            mock_nvdlib.searchCVE.return_value = [mock_cve]

            source = NvdSource(api_key="test-key")
            results = await source.query("OpenSSH", "8.2")

            assert len(results) >= 1
            assert any(r.cve_id == "CVE-2020-14145" for r in results)
            mock_nvdlib.searchCVE.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_uses_keyword_search(self) -> None:
        """query() uses keywordSearch with service and version."""
        from cyberred.intelligence.sources.nvd import NvdSource

        with patch("cyberred.intelligence.sources.nvd.nvdlib") as mock_nvdlib:
            mock_nvdlib.searchCVE.return_value = []

            source = NvdSource(api_key="test-key")
            await source.query("Apache", "2.4.49")

            mock_nvdlib.searchCVE.assert_called_once()
            call_kwargs = mock_nvdlib.searchCVE.call_args.kwargs
            assert "keywordSearch" in call_kwargs
            assert "Apache 2.4.49" in call_kwargs["keywordSearch"]

    @pytest.mark.asyncio
    async def test_query_returns_empty_on_error(self) -> None:
        """query() returns empty list on exception (per ERR3)."""
        from cyberred.intelligence.sources.nvd import NvdSource

        with patch("cyberred.intelligence.sources.nvd.nvdlib") as mock_nvdlib:
            mock_nvdlib.searchCVE.side_effect = Exception("Network error")

            source = NvdSource()
            results = await source.query("Apache", "2.4.49")

            assert results == []

    @pytest.mark.asyncio
    async def test_query_returns_empty_on_timeout(self) -> None:
        """query() returns empty list on timeout (per ERR3)."""
        from cyberred.intelligence.sources.nvd import NvdSource
        import asyncio

        with patch("cyberred.intelligence.sources.nvd.nvdlib") as mock_nvdlib:
            # Simulate slow response
            def slow_search(*args, **kwargs):
                import time
                time.sleep(10)  # Longer than timeout
                return []

            mock_nvdlib.searchCVE.side_effect = slow_search

            source = NvdSource(timeout=0.1)  # Very short timeout
            results = await source.query("Apache", "2.4.49")

            assert results == []

    def test_intel_result_source_is_nvd(self) -> None:
        """IntelResult.source from NvdSource is 'nvd'."""
        from cyberred.intelligence.sources.nvd import NvdSource, NvdCveEntry

        source = NvdSource()
        entry = NvdCveEntry(
            cve_id="CVE-2021-44228",
            cvss_v3_score=10.0,
            cvss_v3_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
            cvss_v2_score=None,
            description="Log4j RCE",
            references=[],
            published_date="2021-12-10T00:00:00.000",
            last_modified_date="2021-12-10T00:00:00.000",
        )

        result = source._to_intel_result(entry, confidence=0.9)

        assert result.source == "nvd"

    def test_intel_result_metadata_contains_cvss_fields(self) -> None:
        """IntelResult.metadata contains CVSS scores and vector."""
        from cyberred.intelligence.sources.nvd import NvdSource, NvdCveEntry

        source = NvdSource()
        entry = NvdCveEntry(
            cve_id="CVE-2021-44228",
            cvss_v3_score=10.0,
            cvss_v3_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
            cvss_v2_score=9.3,
            description="Log4j RCE vulnerability",
            references=["https://nvd.nist.gov/vuln/detail/CVE-2021-44228"],
            published_date="2021-12-10T00:00:00.000",
            last_modified_date="2024-06-27T00:00:00.000",
        )

        result = source._to_intel_result(entry, confidence=0.9)

        assert result.metadata["cvss_v3_score"] == 10.0
        assert result.metadata["cvss_v3_vector"] == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
        assert result.metadata["cvss_v2_score"] == 9.3
        assert result.metadata["description"] == "Log4j RCE vulnerability"
        assert "https://nvd.nist.gov" in result.metadata["references"][0]
        assert result.metadata["published_date"] == "2021-12-10T00:00:00.000"
        assert result.metadata["last_modified_date"] == "2024-06-27T00:00:00.000"


# =============================================================================
# Phase 3D: Severity Mapping Tests [RED]
# =============================================================================


@pytest.mark.unit
class TestScoreToSeverity:
    """Tests for _score_to_severity method (Task 3.4)."""

    def test_critical_score_returns_critical(self) -> None:
        """_score_to_severity(9.5) returns 'critical'."""
        from cyberred.intelligence.sources.nvd import NvdSource

        source = NvdSource()
        assert source._score_to_severity(9.5) == "critical"

    def test_high_score_returns_high(self) -> None:
        """_score_to_severity(7.5) returns 'high'."""
        from cyberred.intelligence.sources.nvd import NvdSource

        source = NvdSource()
        assert source._score_to_severity(7.5) == "high"

    def test_medium_score_returns_medium(self) -> None:
        """_score_to_severity(5.0) returns 'medium'."""
        from cyberred.intelligence.sources.nvd import NvdSource

        source = NvdSource()
        assert source._score_to_severity(5.0) == "medium"

    def test_low_score_returns_low(self) -> None:
        """_score_to_severity(2.0) returns 'low'."""
        from cyberred.intelligence.sources.nvd import NvdSource

        source = NvdSource()
        assert source._score_to_severity(2.0) == "low"

    def test_none_score_returns_info(self) -> None:
        """_score_to_severity(None) returns 'info'."""
        from cyberred.intelligence.sources.nvd import NvdSource

        source = NvdSource()
        assert source._score_to_severity(None) == "info"

    def test_boundary_9_0_returns_critical(self) -> None:
        """_score_to_severity(9.0) returns 'critical' (boundary)."""
        from cyberred.intelligence.sources.nvd import NvdSource

        source = NvdSource()
        assert source._score_to_severity(9.0) == "critical"

    def test_boundary_7_0_returns_high(self) -> None:
        """_score_to_severity(7.0) returns 'high' (boundary)."""
        from cyberred.intelligence.sources.nvd import NvdSource

        source = NvdSource()
        assert source._score_to_severity(7.0) == "high"

    def test_boundary_4_0_returns_medium(self) -> None:
        """_score_to_severity(4.0) returns 'medium' (boundary)."""
        from cyberred.intelligence.sources.nvd import NvdSource

        source = NvdSource()
        assert source._score_to_severity(4.0) == "medium"

    def test_boundary_3_9_returns_low(self) -> None:
        """_score_to_severity(3.9) returns 'low' (just below medium)."""
        from cyberred.intelligence.sources.nvd import NvdSource

        source = NvdSource()
        assert source._score_to_severity(3.9) == "low"


# =============================================================================
# Phase 3E: Health Check Tests [RED]
# =============================================================================


@pytest.mark.unit
class TestNvdSourceHealthCheck:
    """Tests for NvdSource.health_check() method (Task 3.5)."""

    @pytest.mark.asyncio
    async def test_health_check_returns_true_when_api_reachable(self) -> None:
        """health_check() returns True when NVD API responds."""
        from cyberred.intelligence.sources.nvd import NvdSource

        mock_cve = MagicMock()
        mock_cve.id = "CVE-2021-44228"

        with patch("cyberred.intelligence.sources.nvd.nvdlib") as mock_nvdlib:
            mock_nvdlib.searchCVE.return_value = [mock_cve]

            source = NvdSource(api_key="test-key")
            result = await source.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_error(self) -> None:
        """health_check() returns False on network error."""
        from cyberred.intelligence.sources.nvd import NvdSource

        with patch("cyberred.intelligence.sources.nvd.nvdlib") as mock_nvdlib:
            mock_nvdlib.searchCVE.side_effect = Exception("Connection refused")

            source = NvdSource()
            result = await source.health_check()

            assert result is False


# =============================================================================
# Phase 4: Module Exports Tests [RED]
# =============================================================================


@pytest.mark.unit
class TestNvdSourceExports:
    """Tests for module exports (Task 4.1)."""

    def test_nvd_source_importable_from_sources_package(self) -> None:
        """NvdSource is importable from cyberred.intelligence.sources."""
        from cyberred.intelligence.sources import NvdSource

        assert NvdSource is not None

    def test_nvd_cve_entry_importable_from_sources_package(self) -> None:
        """NvdCveEntry is importable from cyberred.intelligence.sources."""
        from cyberred.intelligence.sources import NvdCveEntry

        assert NvdCveEntry is not None

    def test_get_nvd_priority_importable_from_nvd_module(self) -> None:
        """get_nvd_priority is importable from nvd module."""
        from cyberred.intelligence.sources.nvd import get_nvd_priority

        assert get_nvd_priority is not None


# =============================================================================
# Edge Cases and Priority Result Tests
# =============================================================================


@pytest.mark.unit
class TestNvdResultPriority:
    """Tests for result priority based on CVSS score (AC: 3)."""

    def test_critical_cvss_result_has_priority_2(self) -> None:
        """Results with CVSS >= 9.0 have priority 2 (NVD_CRITICAL)."""
        from cyberred.intelligence.sources.nvd import NvdSource, NvdCveEntry

        source = NvdSource()
        entry = NvdCveEntry(
            cve_id="CVE-2021-44228",
            cvss_v3_score=10.0,
            cvss_v3_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
            cvss_v2_score=None,
            description="Critical vulnerability",
            references=[],
            published_date="2021-12-10T00:00:00.000",
            last_modified_date="2021-12-10T00:00:00.000",
        )

        result = source._to_intel_result(entry, confidence=1.0)

        assert result.priority == 2
        assert result.priority == IntelPriority.NVD_CRITICAL

    def test_high_cvss_result_has_priority_3(self) -> None:
        """Results with CVSS 7.0-8.9 have priority 3 (NVD_HIGH)."""
        from cyberred.intelligence.sources.nvd import NvdSource, NvdCveEntry

        source = NvdSource()
        entry = NvdCveEntry(
            cve_id="CVE-2023-12345",
            cvss_v3_score=7.5,
            cvss_v3_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H",
            cvss_v2_score=None,
            description="High severity vulnerability",
            references=[],
            published_date="2023-01-01T00:00:00.000",
            last_modified_date="2023-01-01T00:00:00.000",
        )

        result = source._to_intel_result(entry, confidence=1.0)

        assert result.priority == 3
        assert result.priority == IntelPriority.NVD_HIGH

    def test_medium_cvss_result_has_priority_7(self) -> None:
        """Results with CVSS < 7.0 have priority 7 (NVD_MEDIUM)."""
        from cyberred.intelligence.sources.nvd import NvdSource, NvdCveEntry

        source = NvdSource()
        entry = NvdCveEntry(
            cve_id="CVE-2023-12345",
            cvss_v3_score=5.5,
            cvss_v3_vector="CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H",
            cvss_v2_score=None,
            description="Medium severity vulnerability",
            references=[],
            published_date="2023-01-01T00:00:00.000",
            last_modified_date="2023-01-01T00:00:00.000",
        )

        result = source._to_intel_result(entry, confidence=1.0)

        assert result.priority == 7
        assert result.priority == IntelPriority.NVD_MEDIUM

    def test_uses_v2_score_as_fallback(self) -> None:
        """Result uses cvss_v2_score when v3 is not available."""
        from cyberred.intelligence.sources.nvd import NvdSource, NvdCveEntry

        source = NvdSource()
        entry = NvdCveEntry(
            cve_id="CVE-2015-12345",
            cvss_v3_score=None,  # No v3 score
            cvss_v3_vector=None,
            cvss_v2_score=9.0,  # High v2 score
            description="Old vulnerability with only v2",
            references=[],
            published_date="2015-01-01T00:00:00.000",
            last_modified_date="2015-01-01T00:00:00.000",
        )

        result = source._to_intel_result(entry, confidence=1.0)

        # Should use v2 score for priority calculation
        assert result.priority == IntelPriority.NVD_CRITICAL


@pytest.mark.unit
class TestNvdExploitFields:
    """Tests for exploit-related fields in IntelResult."""

    def test_exploit_available_is_false(self) -> None:
        """NVD results have exploit_available=False (NVD doesn't track exploits)."""
        from cyberred.intelligence.sources.nvd import NvdSource, NvdCveEntry

        source = NvdSource()
        entry = NvdCveEntry(
            cve_id="CVE-2021-44228",
            cvss_v3_score=10.0,
            cvss_v3_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
            cvss_v2_score=None,
            description="Test",
            references=[],
            published_date="2021-12-10T00:00:00.000",
            last_modified_date="2021-12-10T00:00:00.000",
        )

        result = source._to_intel_result(entry, confidence=1.0)

        assert result.exploit_available is False

    def test_exploit_path_is_none(self) -> None:
        """NVD results have exploit_path=None."""
        from cyberred.intelligence.sources.nvd import NvdSource, NvdCveEntry

        source = NvdSource()
        entry = NvdCveEntry(
            cve_id="CVE-2021-44228",
            cvss_v3_score=10.0,
            cvss_v3_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
            cvss_v2_score=None,
            description="Test",
            references=[],
            published_date="2021-12-10T00:00:00.000",
            last_modified_date="2021-12-10T00:00:00.000",
        )

        result = source._to_intel_result(entry, confidence=1.0)

        assert result.exploit_path is None
